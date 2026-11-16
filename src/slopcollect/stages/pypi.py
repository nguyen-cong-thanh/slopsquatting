"""Bước pypi_index (snapshot danh sách tên PyPI) và check (tên có tồn tại / đăng ký mới được không)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from slopcollect.db import latest_snapshot
from slopcollect.extract.normalize import RULES_VERSION, check_registrable, normalize_pep426_name, stdlib_prohibited, ultranormalize_name
from slopcollect.registry import register
from slopcollect.util import http_request, parse_time, utcnow

log = logging.getLogger("slopcollect")

SIMPLE_URL = "https://pypi.org/simple/"
SIMPLE_JSON = "application/vnd.pypi.simple.v1+json"


@register("stage", "pypi_index")
def pypi_index(
    ctx: Any,
    source: str = "simple_api",
    url: str = SIMPLE_URL,
    path: str | None = None,
    max_age_hours: float = 24,
    force: bool = False,
    keep: int = 2,
) -> dict[str, Any]:
    """Lưu snapshot toàn bộ tên project trên PyPI (Simple API JSON, PEP 691).

    source = "file": đọc từ file JSON cùng định dạng (dùng cho test/offline).
    keep: giữ danh sách tên của ``keep`` snapshot gần nhất (snapshot cũ hơn chỉ giữ thông tin tóm tắt).
    """
    conn = ctx.conn
    last = conn.execute("SELECT snapshot_id, fetched_at FROM pypi_snapshots ORDER BY fetched_at DESC LIMIT 1").fetchone()
    if last and not force:
        age = datetime.now(timezone.utc) - (parse_time(last["fetched_at"]) or datetime.min.replace(tzinfo=timezone.utc))
        if age < timedelta(hours=max_age_hours):
            return {"snapshot_id": last["snapshot_id"], "skipped": f"snapshot mới {age} < {max_age_hours} giờ"}

    if source == "file":
        if not path:
            raise ValueError("source = 'file' cần path")
        data = json.loads(ctx.path(path).read_text(encoding="utf-8"))
    elif source == "simple_api":
        log.info("tải danh sách tên từ %s", url)
        resp = http_request(url, headers={"Accept": SIMPLE_JSON}, timeout=600)
        if not resp.ok:
            raise RuntimeError(f"Tải {url} thất bại: HTTP {resp.status}")
        data = resp.json()
    else:
        raise ValueError(f"source không hợp lệ: {source}")

    meta = data.get("meta", {})
    projects = data["projects"]
    fetched = utcnow()
    serial = meta.get("_last-serial")
    snapshot_id = f"pypi-{fetched.replace(':', '').replace('-', '')[:15]}-{serial or 'na'}"
    rows = {}
    for p in projects:
        name = p["name"]
        rows.setdefault(normalize_pep426_name(name), (name, ultranormalize_name(name)))
    with conn:
        conn.execute(
            "INSERT INTO pypi_snapshots(snapshot_id, fetched_at, source, api_version, last_serial, n_projects) VALUES (?,?,?,?,?,?)",
            (snapshot_id, fetched, source if source != "file" else f"file:{path}", meta.get("api-version"), serial, len(rows)),
        )
        conn.executemany(
            "INSERT INTO pypi_index(snapshot_id, norm_name, name, ultra_name) VALUES (?,?,?,?)",
            ((snapshot_id, n, name, u) for n, (name, u) in rows.items()),
        )
        old = [r[0] for r in conn.execute("SELECT snapshot_id FROM pypi_snapshots ORDER BY fetched_at DESC LIMIT -1 OFFSET ?", (keep,))]
        for sid in old:
            conn.execute("DELETE FROM pypi_index WHERE snapshot_id = ?", (sid,))
    return {"snapshot_id": snapshot_id, "projects": len(rows), "pruned_snapshots": len(old)}


@register("stage", "check")
def check(ctx: Any, snapshot: str = "latest", include_lists: bool = False, recheck: bool = False) -> dict[str, Any]:
    """Với mỗi tên LLM đã gợi ý: có trên PyPI không, đăng ký mới được không.

    include_lists = true: kiểm tra thêm mọi tên trong các danh sách tham chiếu (nhiều tên, ít khi cần).
    """
    conn = ctx.conn
    sid = latest_snapshot(conn) if snapshot == "latest" else snapshot
    if not sid:
        raise RuntimeError("Chưa có snapshot PyPI: chạy bước pypi_index trước")
    if not conn.execute("SELECT 1 FROM pypi_index WHERE snapshot_id = ? LIMIT 1", (sid,)).fetchone():
        raise RuntimeError(f"Snapshot {sid} không còn danh sách tên (đã bị dọn)")

    q = "SELECT DISTINCT norm_name FROM mentions"
    if include_lists:
        q += " UNION SELECT DISTINCT norm_name FROM known_lists"
    names = [r[0] for r in conn.execute(q)]
    if not recheck:
        checked = {r[0] for r in conn.execute("SELECT norm_name FROM package_status WHERE snapshot_id = ?", (sid,))}
        names = [n for n in names if n not in checked]

    std = stdlib_prohibited()

    def exists(norm: str) -> bool:
        return conn.execute("SELECT 1 FROM pypi_index WHERE snapshot_id = ? AND norm_name = ?", (sid, norm)).fetchone() is not None

    def similar(ultra: str) -> str | None:
        row = conn.execute("SELECT name FROM pypi_index WHERE snapshot_id = ? AND ultra_name = ? LIMIT 1", (sid, ultra)).fetchone()
        return row[0] if row else None

    now = utcnow()
    counts: dict[str, int] = {}
    with conn:
        for n in names:
            ex = exists(n)
            r = check_registrable(n, exists=lambda _n, _ex=ex: _ex, similar=similar, stdlib=std)
            key = "exists" if ex else ("absent_registrable" if r.registrable else f"absent_{r.reason}")
            counts[key] = counts.get(key, 0) + 1
            conn.execute(
                "INSERT OR REPLACE INTO package_status(norm_name, snapshot_id, exists_on_pypi, registrable, reason, similar_to, rules_version, checked_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (n, sid, int(ex), int(r.registrable), r.reason, r.similar_to, RULES_VERSION, now),
            )
    return {"snapshot_id": sid, "checked": len(names), **counts}
