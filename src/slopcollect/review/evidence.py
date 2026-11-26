"""Bước 3a–3b của quy trình gán nhãn P3 (docs/du-lieu/quy-trinh-gan-nhan-thu-cong.md): thu bằng chứng, đề xuất nhãn.

Với mỗi tên trong phạm vi duyệt: lấy metadata đã có trong CSDL (PyPI, ClickPy, GitHub), các model đã gợi ý tên và mốc
dữ liệu của chúng, rồi đọc nội dung file phát hành mới nhất (chỉ đọc trong bộ nhớ, không cài, không chạy, không ghi ra
đĩa) để đếm dòng code chức năng và lập dàn ý code (tên file, hàm, lớp) cho người duyệt đối chiếu với mô tả. Từ đó đề
xuất nhãn theo cây quyết định và ghi các điểm người duyệt cần chú ý. Mọi tên trong phiếu đều do người đọc và quyết định
(bước 3c); đề xuất chỉ để đọc nhanh hơn.

  .venv/bin/python -m slopcollect.review.evidence --db data/slop.sqlite --out data/review/review_P3.csv

Kết quả đọc file phát hành được lưu tạm ở data/review/content_cache.jsonl (theo tên file), chạy lại không tải lại.
"""

from __future__ import annotations

import argparse
import ast
import csv
import io
import json
import re
import sqlite3
import tarfile
import urllib.request
import warnings
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from slopcollect.stages.label import LABELER_VERSION
from slopcollect.timing import load_cutoffs, released_before, timing

PROTOCOL = "P3"
FUNC_MIN = 20  # dòng code chức năng
OTHER_MIN = 20  # dòng mã nguồn ngôn ngữ khác
BIN_MIN_KB = 10  # phần mở rộng đã biên dịch
MAX_DOWNLOAD = 50 * 1024 * 1024
# Warehouse (PyPI.org, từ 04/2018) chỉ tạo dự án khi có file tải lên; dự án chỉ có metadata mà không có lần tải lên nào
# (cả bản đã xóa) chỉ có thể tạo trên PyPI cũ, tức trước mốc dữ liệu của mọi model.
LEGACY_BEFORE = "2018-04"
BORDER = (10, 40)  # vùng sát ngưỡng: người duyệt phải xem
HEURISTIC_RULES = ("placeholder", "empty_project", "known_hallucination", "after_model_cutoff", "young_low_downloads")
OTHER_SRC = (".js", ".mjs", ".ts", ".tsx", ".jsx", ".c", ".cc", ".cpp", ".h", ".hpp", ".rs", ".go", ".java", ".kt", ".r", ".jl", ".lua", ".sh")
BIN_EXT = (".so", ".pyd", ".dylib", ".dll")
DEFENSIVE = re.compile(
    r"use [\w.\-]+ instead|install [\w.\-]+ instead|not the (?:correct |right )?(?:package|module|library)|wrong (?:python )?(?:package|library|module)"
    r"|security hold|squatting prevention|reserved (?:by|for)|name reservation|will be released|placeholder for|has been renamed|was renamed"
    r"|moved to|deprecated in favou?r of|please use|not the correct|dependency confusion|slopsquat|typosquat|proof[- ]of[- ]concept|\bpoc\b"
    r"|intentionally contains no|reserved to protect|protect against|security research|research package",
    re.I,
)
# Lời trỏ/giữ chỗ yếu hơn: chỉ dùng khi gói KHÔNG có code chức năng (gói thật đã ngừng phát triển hay có các chữ này).
DEFENSIVE_WEAK = re.compile(
    r"dummy package|points? to|reserved package name|just a placeholder|placeholder package|you (?:might|may) be looking for"
    r"|transitional|decommissioned|obsolete|deprecated|backport|hallucination|registered in good faith|until i rename",
    re.I,
)
UA = {"User-Agent": "slopcollect-review/1 (research; read-only)"}


# ---------- đếm dòng code chức năng ----------

def _excluded_stmt(node: ast.stmt) -> bool:
    if isinstance(node, (ast.Import, ast.ImportFrom, ast.Pass)):
        return True
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, (str, type(Ellipsis))):
        return True  # docstring, chuỗi đứng riêng, ...
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if targets and all(isinstance(t, ast.Name) and t.id.startswith("__") and t.id.endswith("__") for t in targets):
            return True
    return False


warnings.filterwarnings("ignore", category=SyntaxWarning)  # cảnh báo khi phân tích code của gói, không phải lỗi của công cụ


def functional_lines(src: str) -> int:
    """Số dòng mã nguồn khác nhau có câu lệnh, trừ import, docstring, pass/..., gán __x__ (mục 4 của quy trình)."""
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return sum(1 for ln in src.splitlines() if ln.strip() and not ln.strip().startswith("#"))
    lines: set[int] = set()

    def visit(body: list[ast.stmt]) -> None:
        for st in body:
            if _excluded_stmt(st):
                continue
            # Câu lệnh ghép (def, class, if, for, try, with, match): tính dòng đầu rồi duyệt thân;
            # câu lệnh đơn: tính mọi dòng nó chiếm.
            children = list(ast.iter_child_nodes(st))
            nested = [c for c in children if isinstance(c, ast.stmt)]
            blocks = [c for c in children if isinstance(c, (ast.ExceptHandler, ast.match_case))]
            if nested or blocks:
                lines.add(st.lineno)
                visit(nested)
                for b in blocks:
                    visit(b.body)
            else:
                lines.update(range(st.lineno, (getattr(st, "end_lineno", None) or st.lineno) + 1))

    visit(tree.body)
    return len(lines)


VENDOR_DIRS = {"site-packages", ".tox", "venv", ".venv", "node_modules", ".ccls-cache", "__pycache__", ".git"}


def _is_vendored(path: str) -> bool:
    """Thư mục môi trường ảo, cache hay thư viện của người khác bị đóng gói lẫn vào: không phải code của gói."""
    return any(seg in VENDOR_DIRS for seg in path.split("/"))


def _is_test(path: str) -> bool:
    p = path.lower()
    name = p.rsplit("/", 1)[-1]
    return "/tests/" in f"/{p}" or "/test/" in f"/{p}" or name.startswith("test_") or name in ("setup.py", "conftest.py")


def analyse_archive(filename: str, data: bytes) -> dict[str, Any]:
    files: list[tuple[str, int, bytes | None]] = []
    if filename.endswith((".whl", ".zip", ".egg")):
        z = zipfile.ZipFile(io.BytesIO(data))
        for i in z.infolist():
            if not i.is_dir():
                want = i.filename.endswith((".py", ".pyi", *OTHER_SRC)) and i.file_size < 2_000_000
                files.append((i.filename, i.file_size, z.read(i) if want else None))
    else:
        t = tarfile.open(fileobj=io.BytesIO(data))
        for m in t.getmembers():
            if m.isfile():
                want = m.name.endswith((".py", ".pyi", *OTHER_SRC)) and m.size < 2_000_000
                f = t.extractfile(m) if want else None
                files.append((m.name, m.size, f.read() if f else None))
    func = other = 0
    bin_kb = 0.0
    py_files = 0
    mods: list[str] = []
    names: list[str] = []
    for path, size, raw in files:
        if path.endswith(BIN_EXT) or ((".data/scripts/" in path or "/bin/" in path) and size >= 1_000_000):
            bin_kb += size / 1024  # phần mở rộng đã biên dịch, hoặc tệp thực thi đóng kèm (>= 1 MB)
        if raw is None or _is_test(path) or _is_vendored(path):
            continue
        txt = raw.decode("utf-8", "replace")
        if path.endswith((".py", ".pyi")):
            py_files += 1
            func += functional_lines(txt)
            mods.append(path.split("/", 1)[-1] if path.count("/") > 1 and filename.endswith((".tar.gz", ".tgz", ".tar.bz2")) else path)
            names += _top_names(txt)
        else:
            other += sum(1 for ln in txt.splitlines() if ln.strip() and not ln.strip().startswith(("//", "#", "/*", "*")))
    others = [p for p, _, r in files if r is not None and not p.endswith((".py", ".pyi")) and not _is_test(p) and not _is_vendored(p)]
    outline = f"py: {', '.join(mods[:12])}{' …' if len(mods) > 12 else ''}"
    if names:
        outline += f" | tên: {', '.join(dict.fromkeys(names))}"[:600]
    if others:
        outline += f" | khác: {', '.join(others[:6])}"
    return {"n_archive_files": len(files), "py_files": py_files, "func_lines": func, "other_src_lines": other, "bin_kb": round(bin_kb, 1),
            "outline": outline[:900], "n_vendored": sum(1 for p, _, _ in files if _is_vendored(p))}


def _top_names(src: str) -> list[str]:
    """Tên hàm và lớp ở cấp module (kèm phương thức của lớp): để người duyệt so chức năng của code với mô tả."""
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return []
    out = []
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(n.name)
        elif isinstance(n, ast.ClassDef):
            meths = [m.name for m in n.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and not m.name.startswith("__")]
            out.append(f"{n.name}({', '.join(meths[:6])})" if meths else n.name)
    return out


def _pick_file(raw: dict) -> dict | None:
    urls = raw.get("urls") or []
    if not urls:  # phiên bản mới nhất không có file: lấy bản gần nhất có file
        for v in sorted(raw.get("releases", {}), key=lambda v: max((f.get("upload_time") or "" for f in raw["releases"][v]), default=""), reverse=True):
            if raw["releases"][v]:
                urls = raw["releases"][v]
                break
    if not urls:
        return None
    wheels = [u for u in urls if u["filename"].endswith(".whl")]
    pure = [u for u in wheels if u["filename"].endswith("-none-any.whl")]
    return (pure or wheels or urls)[0]


def fetch_content(raw: dict, cache: dict[str, dict]) -> dict[str, Any]:
    f = _pick_file(raw)
    if f is None:
        return {"content": "no_files"}
    key = f["filename"]
    if key in cache and ("n_vendored" in cache[key] or cache[key].get("content") != "ok"):
        return cache[key]
    if (f.get("size") or 0) > MAX_DOWNLOAD:
        res = {"content": "too_large", "file": key, "file_kb": round(f["size"] / 1024)}
    else:
        try:
            data = urllib.request.urlopen(urllib.request.Request(f["url"], headers=UA), timeout=60).read()
            res = {"content": "ok", "file": key, "file_kb": round(len(data) / 1024, 1), **analyse_archive(key, data)}
        except Exception as e:  # noqa: BLE001 — ghi lỗi để người duyệt biết
            res = {"content": "error", "file": key, "error": str(e)[:200]}
    cache[key] = res
    return res


# ---------- phạm vi và bằng chứng từ CSDL ----------

def _t(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def serial_calibration(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    """(last_serial, ngày tải lên) của các gói chỉ có đúng một file: serial của PyPI tăng theo thời gian, nên đây là bảng
    đổi serial ra ngày."""
    pairs = []
    for (rj,) in conn.execute("SELECT raw_json FROM metadata_raw WHERE source = 'pypi_json' AND http_status = 200 AND raw_json IS NOT NULL"):
        d = json.loads(rj)
        files = [f for v in (d.get("releases") or {}).values() for f in v]
        if len(files) == 1 and d.get("last_serial"):
            pairs.append((int(d["last_serial"]), files[0]["upload_time"][:10]))
    return sorted(pairs)


def serial_date(serial: int | None, calib: list[tuple[int, str]]) -> datetime | None:
    """Ngày muộn nhất mà sự kiện có serial này có thể xảy ra: ngày của điểm hiệu chuẩn đầu tiên có serial >= nó."""
    if not serial or not calib:
        return None
    import bisect

    i = bisect.bisect_left(calib, (serial, ""))
    return None if i >= len(calib) else _t(calib[i][1])


def fetch_serials(names: list[str], cache_path: Path, workers: int = 8) -> dict[str, int | None]:
    """_last-serial của dự án từ Simple API (JSON), cho các dự án không có ngày tải lên đầu tiên."""
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}

    def get(n: str) -> tuple[str, int | None]:
        req = urllib.request.Request(f"https://pypi.org/simple/{n}/", headers={**UA, "Accept": "application/vnd.pypi.simple.v1+json"})
        try:
            d = json.loads(urllib.request.urlopen(req, timeout=60).read())
            return n, (d.get("meta") or {}).get("_last-serial")
        except Exception:  # noqa: BLE001 — 404: dự án không còn
            return n, None

    todo = [n for n in names if n not in cache]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        cache.update(dict(pool.map(get, todo)))
    cache_path.write_text(json.dumps(cache, indent=0), encoding="utf-8")
    return {n: cache.get(n) for n in names}


def scope(conn: sqlite3.Connection, overrides: dict[str, dict]) -> list[str]:
    q = f"SELECT norm_name FROM labels WHERE labeler_version = ? AND rule IN ({','.join('?' * len(HEURISTIC_RULES))})"
    names = {r[0] for r in conn.execute(q, (LABELER_VERSION, *HEURISTIC_RULES))}
    # Gói luật gắn real nhưng tóm tắt có lời phòng vệ/nghiên cứu (vd "Benign slopsquatting research package").
    for n, raw in conn.execute(
        "SELECT l.norm_name, m.raw_json FROM labels l JOIN metadata_raw m ON m.norm_name = l.norm_name AND m.source = 'pypi_json' "
        "WHERE l.labeler_version = ? AND l.label = 'real' AND m.raw_json IS NOT NULL", (LABELER_VERSION,)
    ):
        summary = ((json.loads(raw).get("info") or {}).get("summary") or "")
        if DEFENSIVE.search(summary):
            names.add(n)
    return sorted(names | set(overrides))


def collect(db: str, cutoffs_file: str, overrides_csv: str, cache_file: str, workers: int = 8) -> list[dict[str, Any]]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=120)
    conn.row_factory = sqlite3.Row
    overrides = {r["norm_name"]: r for r in csv.DictReader(open(overrides_csv, encoding="utf-8"))} if Path(overrides_csv).exists() else {}
    cut = load_cutoffs(cutoffs_file)
    names = scope(conn, overrides)
    cache: dict[str, dict] = {}
    cp = Path(cache_file)
    if cp.exists():
        for ln in cp.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                d = json.loads(ln)
                cache[d["key"]] = d["res"]
    n_cached = len(cache)

    models: dict[str, set[str]] = {}
    ph = ",".join("?" * len(names))
    for r in conn.execute(f"SELECT DISTINCT norm_name, model_key FROM v_mentions WHERE norm_name IN ({ph})", names):
        models.setdefault(r[0], set()).add(r[1])
    lab = {r[0]: (r[1], r[2]) for r in conn.execute(f"SELECT norm_name, label, rule FROM labels WHERE labeler_version = ? AND norm_name IN ({ph})", (LABELER_VERSION, *names))}
    feat = {r["norm_name"]: dict(r) for r in conn.execute(f"SELECT * FROM package_features WHERE norm_name IN ({ph})", names)}
    raw: dict[str, dict[str, Any]] = {}
    for r in conn.execute(f"SELECT norm_name, source, http_status, raw_json FROM metadata_raw WHERE norm_name IN ({ph})", names):
        raw.setdefault(r[0], {})[r[1]] = (r[2], json.loads(r[3]) if r[3] else None)
    calib = serial_calibration(conn)
    conn.close()
    no_date = [n for n in names if not (feat.get(n) or {}).get("first_release_at")]
    serials = fetch_serials(no_date, Path(cache_file).with_name("serial_cache.json"), workers)

    def one(n: str) -> dict[str, Any]:
        f = feat.get(n, {})
        pj_status, pj = raw.get(n, {}).get("pypi_json", (None, None))
        info = (pj or {}).get("info") or {}
        gh = (raw.get(n, {}).get("github", (None, None))[1]) or {}
        ms = sorted(models.get(n, set()))
        known = [m for m in ms if m in cut.date]
        latest = max((cut.date[m] for m in known), default=None)
        earliest = min((cut.date[m] for m in known), default=None)
        first = _t(f.get("first_release_at"))
        legacy = pj_status == 200 and not first and (f.get("n_files") or 0) == 0
        # Cùng một hàm với lưới lọc ở bước label (slopcollect.timing): after / before / unknown.
        exists_by = serial_date(serials.get(n), calib) if not first else None
        verdict, pre = timing(first, ms, cut, legacy=legacy, exists_by=exists_by)
        rel = released_before(first, ms, cut)
        text = f"{info.get('summary') or ''}\n{(info.get('description') or '')[:3000]}"
        dm = DEFENSIVE.search(text)
        dw = DEFENSIVE_WEAK.search(text)
        content = fetch_content(pj, cache) if pj and pj_status == 200 else {"content": "api_404" if pj_status == 404 else "no_metadata"}
        ov = overrides.get(n) or {}
        return {
            "norm_name": n,
            "current_label": lab.get(n, ("", ""))[0],
            "current_rule": lab.get(n, ("", ""))[1],
            "old_override": ov.get("override_label", ""),
            "old_note": ov.get("note", ""),
            "models": ";".join(ms),
            "latest_cutoff": latest.date().isoformat() if latest else "",
            "first_upload": first.date().isoformat() if first else (f"trước {LEGACY_BEFORE} (chỉ metadata)" if legacy else ""),
            "earliest_cutoff": earliest.date().isoformat() if earliest else "",
            "pre_registration_models": ";".join(pre),
            "released_before_upload": ";".join(rel),
            "exists_by": exists_by.date().isoformat() if exists_by else "",
            "after_cutoff": {"after": "yes", "before": "no"}.get(verdict, ""),
            "n_deps": len(info.get("requires_dist") or []),
            "pypi_api": pj_status or "",
            "summary": (info.get("summary") or "")[:200],
            "desc_len": f.get("description_len") or 0,
            "desc_head": re.sub(r"\s+", " ", (info.get("description") or ""))[:300],
            "version": info.get("version") or "",
            "n_releases": f.get("n_releases") or 0,
            "n_files": f.get("n_files") if f.get("n_files") is not None else "",
            "downloads_30d": f.get("downloads_last_month") or 0,
            "n_owners": f.get("n_owners") or "",
            "has_org": f.get("has_organization") or 0,
            "author": (info.get("author") or "")[:60],
            "home": json.dumps(info.get("project_urls") or info.get("home_page") or "", ensure_ascii=False)[:200],
            "github": gh.get("full_name") or f.get("github_repo") or "",
            "github_stars": gh.get("stargazers_count", ""),
            "repo_verified": f.get("source_repo_verified") or 0,
            "defensive_hint": dm.group(0) if dm else "",
            "defensive_weak": dw.group(0) if dw else "",
            **{k: content.get(k, "") for k in ("content", "file", "file_kb", "py_files", "func_lines", "other_src_lines", "bin_kb", "n_vendored", "outline", "error")},
        }

    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(one, names))
    with cp.open("w", encoding="utf-8") as fh:
        for k, v in cache.items():
            fh.write(json.dumps({"key": k, "res": v}, ensure_ascii=False) + "\n")
    print(f"{len(rows)} tên; file phát hành: {len(cache) - n_cached} tải mới, {n_cached} lấy từ cache")
    return rows


# ---------- đề xuất nhãn theo cây quyết định (mục 5 của quy trình) ----------

def has_function(r: dict[str, Any]) -> bool | None:
    if r["content"] == "too_large":
        return True  # file > 50 MB: coi là có nội dung, người duyệt xác nhận
    if r["content"] != "ok":
        return None if r["content"] in ("error",) else False
    return (r["func_lines"] or 0) >= FUNC_MIN or (r["other_src_lines"] or 0) >= OTHER_MIN or (r["bin_kb"] or 0) >= BIN_MIN_KB


def propose(r: dict[str, Any]) -> tuple[str, str, list[str]]:
    """(nhãn đề xuất, mã tiêu chí, lý do người duyệt phải xem)."""
    eyes: list[str] = []
    fn = has_function(r)
    if fn is False and int(r.get("n_deps") or 0) > 0:
        eyes.append(f"không có code nhưng khai báo {r['n_deps']} phụ thuộc: gói meta?")
    if r["defensive_hint"]:
        eyes.append(f"dấu hiệu phòng vệ: '{r['defensive_hint']}'")
    if r["content"] == "error":
        eyes.append("không đọc được file phát hành")
    if r["content"] == "ok" and BORDER[0] <= (r["func_lines"] or 0) <= BORDER[1] and (r["other_src_lines"] or 0) < OTHER_MIN and (r["bin_kb"] or 0) < BIN_MIN_KB:
        eyes.append(f"sát ngưỡng ({r['func_lines']} dòng)")
    if fn is None:
        lab, crit = "uncertain", "U"
    elif fn:
        lab, crit = "real", "R"
        if not (r.get("summary") or "").strip() and int(r.get("desc_len") or 0) < 50:
            eyes.append("không có mô tả: đối chiếu code với tên gói")
    elif r["after_cutoff"] == "yes":
        lab, crit = "registered_hallucination", "S"
    elif r["after_cutoff"] == "no":
        lab, crit = "placeholder", "E"
    else:
        lab, crit = "uncertain", "U"
    if (r["defensive_hint"] or r.get("defensive_weak")) and fn is False:
        lab, crit = "placeholder", "D"
        if not r["defensive_hint"]:
            eyes.append(f"lời giữ chỗ/trỏ sang gói khác (yếu): '{r['defensive_weak']}'")  # đề xuất; người duyệt đọc nguyên văn để xác nhận
    old = r["old_override"] or r["current_label"]
    if lab != old:
        eyes.append(f"khác nhãn cũ ({old})")
    if lab == "uncertain":
        eyes.append("không chắc")
    return lab, crit, eyes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/slop.sqlite")
    ap.add_argument("--cutoffs", default="configs/cutoffs.toml")
    ap.add_argument("--overrides", default="data/review/overrides.csv")
    ap.add_argument("--cache", default="data/review/content_cache.jsonl")
    ap.add_argument("--out", default="data/review/review_P3.csv")
    a = ap.parse_args()
    rows = collect(a.db, a.cutoffs, a.overrides, a.cache)
    for r in rows:
        lab, crit, eyes = propose(r)
        r.update(proposed_label=lab, proposed_criterion=crit, must_review="; ".join(eyes))
    cols = list(rows[0])
    with open(a.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    from collections import Counter

    print("đề xuất:", dict(Counter((r["proposed_label"], r["proposed_criterion"]) for r in rows)))
    print("phải xem:", sum(1 for r in rows if r["must_review"]), "/", len(rows))
    print("ghi", a.out)


if __name__ == "__main__":
    main()
