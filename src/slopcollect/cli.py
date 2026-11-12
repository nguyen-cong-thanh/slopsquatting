"""Dòng lệnh.

  python -m slopcollect run flows/pilot.toml               chạy cả luồng
  python -m slopcollect run flows/local-full.toml --keep-going   chạy dài: tự chạy lại khi lỗi cho tới khi xong
  python -m slopcollect status flows/local-full.toml       tiến độ: đã xong / còn lại / lỗi / thời gian còn lại
  python -m slopcollect run flows/pilot.toml --only generate
  python -m slopcollect stage generate model=qwen35-4b-kali task=spracklen_code_v1 limit=20
  python -m slopcollect merge data/glm.sqlite              gộp CSDL mang từ máy khác về
  python -m slopcollect info                               đếm số dòng các bảng
  python -m slopcollect ping qwen35-4b-kali                gửi một câu hỏi ngắn để thử kết nối model
  python -m slopcollect list                               liệt kê bước, backend, nguồn, luật có sẵn
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

from slopcollect import registry
from slopcollect.backends.base import FatalBackendError
from slopcollect.config import ConfigError, FlowConfig, load_flow, parse_cli_value
from slopcollect.db import connect, connect_readonly
from slopcollect.pipeline import Context, run_flow, run_stage
from slopcollect.util import NetworkError

DEFAULT_DB = "data/slop.sqlite"
log = logging.getLogger("slopcollect")

# Lỗi có thể tự hết khi chạy lại (mạng, máy chủ, khóa CSDL); lỗi cấu hình thì không chạy lại.
_RESTARTABLE = (NetworkError, RuntimeError, OSError, sqlite3.OperationalError)


def _sigterm(signum: int, frame: Any) -> None:
    # kill <pid> được xử lý như Ctrl-C: lưu các câu đã xong rồi thoát.
    raise KeyboardInterrupt


def run_keep_going(ctx: Context, flow: FlowConfig, *, only: list[str] | None, skip: list[str] | None, retry_wait: float, max_passes: int) -> None:
    """Chạy luồng cho tới khi không còn câu lỗi. Tiến trình gặp lỗi tạm thời thì chờ rồi chạy lại."""
    passes = crashes = 0
    while True:
        try:
            results = run_flow(ctx, flow, only=only, skip=skip)
            crashes = 0
        except _RESTARTABLE as e:
            crashes += 1
            if crashes >= 20:
                log.error("Lỗi lặp lại %d lần liên tiếp, dừng hẳn: %s", crashes, e)
                raise
            log.error("Lỗi: %s: %s. Chạy lại sau %.0f giây (lần %d).", type(e).__name__, e, retry_wait, crashes)
            time.sleep(retry_wait)
            continue
        failed = sum(int(r.get("failed", 0)) for r in results if isinstance(r, dict))
        if failed == 0:
            log.info("Luồng %s đã xong, không còn câu lỗi.", flow.name)
            return
        passes += 1
        if passes >= max_passes:
            log.warning("Sau %d lượt vẫn còn %d câu lỗi; dừng. Xem bảng generations (cột error).", passes, failed)
            return
        log.info("Còn %d câu lỗi: chạy lại lượt %d sau %.0f giây.", failed, passes + 1, retry_wait)
        time.sleep(retry_wait)


def print_status(ctx: Context, flow: FlowConfig) -> None:
    """Tiến độ từng bước generate của luồng (không gọi LLM, không ghi CSDL)."""
    gen = registry.get("stage", "generate")
    rows = []
    for i, step in enumerate(flow.steps, 1):
        if step["stage"] != "generate":
            continue
        params = {k: v for k, v in step.items() if k not in ("stage", "name")}
        s = gen(ctx, **{**params, "dry_run": True})
        errors = ctx.conn.execute(
            "SELECT COUNT(*) FROM generations WHERE model_key = ? AND task_id = ? AND params_hash = ? AND error IS NOT NULL",
            (s["model"], s["task"], s["params_hash"]),
        ).fetchone()[0]
        lat = ctx.conn.execute(
            "SELECT AVG(latency_ms) FROM (SELECT latency_ms FROM generations WHERE model_key = ? AND task_id = ? AND params_hash = ? "
            "AND error IS NULL ORDER BY created_at DESC LIMIT 200)",
            (s["model"], s["task"], s["params_hash"]),
        ).fetchone()[0]
        conc = params.get("concurrency") or ctx.model(s["model"]).concurrency
        eta_h = s["todo"] * (lat or 0) / 1000 / conc / 3600 if lat else None
        rows.append((i, step.get("name", "generate"), s["model"], s["task"], s["items"], s["already_done"], s["todo"], errors, eta_h))
    if not rows:
        print("Luồng không có bước generate.")
        return
    print(f"{'#':>2} {'bước':16} {'model':16} {'tác vụ':30} {'tổng':>7} {'xong':>7} {'còn':>7} {'lỗi':>5} {'còn ~giờ':>9}")
    total_eta = 0.0
    for i, name, model, task, items, done, todo, errors, eta_h in rows:
        total_eta += eta_h or 0
        eta = f"{eta_h:.1f}" if eta_h is not None else "?"
        print(f"{i:>2} {name:16.16} {model:16.16} {task:30.30} {items:>7} {done:>7} {todo:>7} {errors:>5} {eta:>9}")
    print(f"Tổng thời gian còn lại ước tính: ~{total_eta:.1f} giờ (theo độ trễ trung bình 200 câu gần nhất; '?' = chưa có số đo).")


def _setup_logging(verbose: bool, log_file: str | None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
    )


def _parse_params(items: list[str]) -> dict:
    params = {}
    for it in items:
        if "=" not in it:
            raise SystemExit(f"Tham số phải có dạng khóa=giá_trị: {it}")
        k, v = it.split("=", 1)
        params[k.strip()] = parse_cli_value(v.strip())
    return params


def _context(root: Path, db: str, *, readonly: bool = False) -> Context:
    db_path = Path(db) if Path(db).is_absolute() else root / db
    conn = connect_readonly(db_path) if readonly else connect(db_path)
    return Context(conn=conn, root=root, db_path=db_path)


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < (3, 11):
        print("Cần Python >= 3.11 (dùng tomllib).", file=sys.stderr)
        return 2
    ap = argparse.ArgumentParser(prog="slopcollect", description="Thu thập tên gói do LLM gợi ý (đề tài slopsquatting)")
    ap.add_argument("--root", default=".", help="thư mục gốc chứa configs/ và flows/ (mặc định: thư mục hiện tại)")
    ap.add_argument("--db", default=None, help=f"file SQLite (mặc định: theo file luồng, hoặc {DEFAULT_DB})")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--log-file", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="chạy một luồng TOML")
    p_run.add_argument("flow")
    p_run.add_argument("--only", nargs="*", help="chỉ chạy các bước này (tên, stage hoặc số thứ tự)")
    p_run.add_argument("--skip", nargs="*", help="bỏ qua các bước này")
    p_run.add_argument("--keep-going", action="store_true", help="tự chạy lại khi lỗi cho tới khi không còn câu lỗi (dùng cho chạy dài)")
    p_run.add_argument("--retry-wait", type=float, default=120.0, help="số giây chờ trước khi chạy lại (mặc định 120)")
    p_run.add_argument("--max-passes", type=int, default=5, help="số lượt tối đa để thử lại câu lỗi (mặc định 5)")

    p_status = sub.add_parser("status", help="tiến độ các bước generate của một luồng")
    p_status.add_argument("flow")

    p_stage = sub.add_parser("stage", help="chạy một bước với tham số khóa=giá_trị (giá trị theo cú pháp TOML)")
    p_stage.add_argument("name")
    p_stage.add_argument("params", nargs="*")

    p_merge = sub.add_parser("merge", help="gộp các file SQLite khác vào CSDL")
    p_merge.add_argument("paths", nargs="+")

    sub.add_parser("info", help="số dòng mỗi bảng")

    p_ping = sub.add_parser("ping", help="thử kết nối một model")
    p_ping.add_argument("model")
    p_ping.add_argument("--prompt", default="Write one line of Python that prints hello.")

    sub.add_parser("list", help="liệt kê plugin có sẵn")

    args = ap.parse_args(argv)
    _setup_logging(args.verbose, args.log_file)
    root = Path(args.root).resolve()
    try:
        signal.signal(signal.SIGTERM, _sigterm)
    except ValueError:  # không ở luồng chính (ví dụ khi gọi từ test)
        pass

    try:
        if args.cmd == "list":
            for kind in registry.KINDS:
                print(f"{kind}: {', '.join(registry.names(kind))}")
            return 0

        if args.cmd == "ping":
            ctx = Context(conn=None, root=root, db_path=Path(":memory:"))  # type: ignore[arg-type]
            mcfg = ctx.model(args.model)
            backend = registry.get("backend", mcfg.backend)(mcfg)
            params = {k: v for k, v in mcfg.params.items() if k != "seed_mode"}
            params["max_tokens"] = min(int(params.get("max_tokens", 64)), 64)
            res = backend.chat([{"role": "user", "content": args.prompt}], params, seed=1)
            print(json.dumps(res.__dict__, ensure_ascii=False, indent=2))
            return 0

        if args.cmd == "run":
            flow = load_flow(Path(args.flow))
            ctx = _context(root, args.db or flow.db)
            if args.keep_going:
                run_keep_going(ctx, flow, only=args.only, skip=args.skip, retry_wait=args.retry_wait, max_passes=args.max_passes)
            else:
                run_flow(ctx, flow, only=args.only, skip=args.skip)
            return 0

        if args.cmd == "status":
            flow = load_flow(Path(args.flow))
            ctx = _context(root, args.db or flow.db, readonly=True)
            print_status(ctx, flow)
            return 0

        ctx = _context(root, args.db or DEFAULT_DB, readonly=args.cmd == "info")
        if args.cmd == "stage":
            print(json.dumps(run_stage(ctx, args.name, _parse_params(args.params)), ensure_ascii=False, indent=2, default=str))
        elif args.cmd == "merge":
            print(json.dumps(run_stage(ctx, "merge", {"paths": args.paths}), ensure_ascii=False, indent=2))
        elif args.cmd == "info":
            tables = [r[0] for r in ctx.conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
            for t in tables:
                print(f"{t:20s} {ctx.conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]:>10}")
        return 0
    except KeyboardInterrupt:
        logging.getLogger("slopcollect").warning("Đã dừng. Chạy lại cùng lệnh để tiếp tục từ chỗ dừng.")
        return 130
    except FatalBackendError as e:
        # Không tự chạy lại (kể cả với --keep-going): cần người dùng nạp tiền / sửa khóa API.
        logging.getLogger("slopcollect").error("%s", e)
        return 3
    except (ConfigError, KeyError, TypeError, ValueError, RuntimeError, FileNotFoundError) as e:
        logging.getLogger("slopcollect").error("%s: %s", type(e).__name__, e)
        if args.verbose:
            raise
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
