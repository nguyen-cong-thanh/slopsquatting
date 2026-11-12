"""Bước metadata: thu thông tin của các gói đang có trên PyPI, rồi tính bảng đặc trưng package_features.

Nguồn (mỗi nguồn lưu bản thô trong metadata_raw, chạy lại thì bỏ qua bản còn mới):
  - pypi_json:       https://pypi.org/pypi/<tên>/json  (phát hành, mô tả, link, người duy trì)
  - pypi_provenance: Simple API JSON của project -> link provenance (PEP 740) của file mới nhất
                     -> kho mã nguồn mà PyPI đã xác minh qua Trusted Publishing
  - clickpy:         lượt tải 30 ngày, lấy hàng loạt (1000 tên một truy vấn) từ bản sao công khai
                     bảng lượt tải PyPI trên ClickHouse. Mặc định dùng nguồn này.
  - pypistats:       https://pypistats.org/api/packages/<tên>/recent  (lượt tải 30 ngày; chậm, ~0,5 lượt/giây,
                     chỉ dùng khi ghi rõ trong sources)
Các nguồn chạy song song; github bắt đầu sau khi pypi_json xong.
  - github:          GitHub GraphQL, 100 kho một truy vấn (sao, ngày tạo; cần GITHUB_TOKEN)
  - github_rest:     https://api.github.com/repos/<owner>/<repo>, từng kho một (dùng được không token, 60 lượt/giờ)
"""

from __future__ import annotations

import json
import logging
import os
import queue
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from slopcollect.db import latest_snapshot
from slopcollect.registry import register
from slopcollect.util import NetworkError, RateLimiter, Response, http_request, parse_time, retry, utcnow

log = logging.getLogger("slopcollect")

_GITHUB_RE = re.compile(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)", re.IGNORECASE)
DEFAULT_RATES = {"pypi_json": 10.0, "pypi_provenance": 10.0, "pypistats": 0.5, "github": 1.0}


class _HTTPTransient(Exception):
    pass


def _is_transient(e: BaseException) -> bool:
    return isinstance(e, (NetworkError, _HTTPTransient))


def _get(url: str, headers: dict[str, str] | None = None) -> Response:
    def once() -> Response:
        r = http_request(url, headers=headers, timeout=60)
        if r.transient:
            raise _HTTPTransient(f"HTTP {r.status} {url}")
        return r

    resp, _ = retry(once, attempts=4, is_transient=_is_transient, base_delay=3.0)
    return resp


def github_repos_from_urls(urls: list[str]) -> list[str]:
    out: list[str] = []
    for u in urls:
        m = _GITHUB_RE.search(u or "")
        if m:
            owner, repo = m.group(1), m.group(2)
            repo = re.sub(r"\.git$", "", repo)
            if owner.lower() in ("sponsors", "orgs", "features", "marketplace"):
                continue
            key = f"{owner}/{repo}".lower()
            if key not in out:
                out.append(key)
    return out


def github_repo_from_urls(urls: list[str]) -> str | None:
    repos = github_repos_from_urls(urls)
    return repos[0] if repos else None


def _project_urls(info: dict[str, Any]) -> list[str]:
    return list((info.get("project_urls") or {}).values()) + [info.get("home_page") or "", info.get("download_url") or ""]


def _fetch_pypi_json(name: str, raws: dict[str, Any], token: str | None) -> tuple[int, Any]:
    r = _get(f"https://pypi.org/pypi/{name}/json")
    return r.status, (r.json() if r.ok else None)


def _fetch_provenance(name: str, raws: dict[str, Any], token: str | None) -> tuple[int, Any]:
    r = _get(f"https://pypi.org/simple/{name}/", headers={"Accept": "application/vnd.pypi.simple.v1+json"})
    if not r.ok:
        return r.status, None
    files = [f for f in r.json().get("files", []) if not f.get("yanked")]
    files.sort(key=lambda f: f.get("upload-time") or "")
    with_prov = [f for f in files if f.get("provenance")]
    if not with_prov:
        return 200, {"has_provenance": False, "n_files": len(files)}
    f = with_prov[-1]
    pr = _get(f["provenance"])
    if not pr.ok:
        return pr.status, {"has_provenance": False, "file": f["filename"]}
    bundles = pr.json().get("attestation_bundles", [])
    publishers = [b.get("publisher", {}) for b in bundles]
    return 200, {"has_provenance": True, "file": f["filename"], "publishers": publishers}


def _fetch_pypistats(name: str, raws: dict[str, Any], token: str | None) -> tuple[int, Any]:
    r = _get(f"https://pypistats.org/api/packages/{name}/recent")
    return r.status, (r.json() if r.ok else None)


def _fetch_github(name: str, raws: dict[str, Any], token: str | None) -> tuple[int, Any]:
    if not raws.get("pypi_json") and "github_repo" not in raws:
        return 0, {"skipped": "no pypi_json"}
    repo = _github_repo_of(raws)
    if not repo:
        return 0, {"skipped": "no github url"}
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = _get(f"https://api.github.com/repos/{repo}", headers=headers)
    if r.status == 403 and "rate limit" in r.body.decode("utf-8", "replace").lower():
        raise RuntimeError("Hết lượt gọi GitHub API (đặt GITHUB_TOKEN hoặc giảm tốc độ)")
    data = r.json() if r.ok else None
    return r.status, ({"repo": repo, **{k: data.get(k) for k in ("full_name", "stargazers_count", "created_at", "archived", "fork")}} if data else {"repo": repo})


CLICKPY_URL = "https://sql-clickhouse.clickhouse.com/?user=demo"
_SAFE_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def _fetch_clickpy_bulk(names: list[str]) -> dict[str, tuple[int | None, Any, str | None]]:
    """Lượt tải 30 ngày của nhiều gói trong một truy vấn.

    ClickPy (ClickHouse) là bản sao công khai của bảng lượt tải PyPI trên BigQuery, cùng nguồn với
    pypistats, khóa theo tên đã chuẩn hóa. Cửa sổ: 30 ngày tính tới ngày mới nhất có trong bảng.
    pypistats giới hạn tốc độ theo IP và khuyên dùng BigQuery khi lấy hàng loạt.
    """
    safe = [n for n in names if _SAFE_NAME.match(n)]
    out: dict[str, tuple[int | None, Any, str | None]] = {n: (None, None, "tên có ký tự lạ, bỏ qua") for n in names if n not in set(safe)}
    if not safe:
        return out
    # Ngày mới nhất lấy qua một gói luôn có lượt tải mỗi ngày: đọc theo khóa (project, date) nên rẻ.
    # Không dùng max(date) trên cả bảng: phải quét >1 tỷ dòng, chạm giới hạn đọc của máy chủ
    # (read_overflow_mode = break) và mọi tổng bị cắt ngang mà không báo lỗi.
    end = _clickpy_query("SELECT toString(max(date)) FROM pypi.pypi_downloads_per_day WHERE project = 'requests'")[0][0]
    mirrors = ",".join(f"'{m}'" for m in MIRROR_INSTALLERS)
    rows = _clickpy_query(
        f"SELECT project, sumIf(count, installer NOT IN ({mirrors})), sum(count) "
        "FROM pypi.pypi_downloads_per_day_by_version_by_installer_by_type "
        f"WHERE date > toDate('{end}') - 30 AND date <= toDate('{end}') "
        "AND project IN (" + ",".join(f"'{n}'" for n in safe) + ") GROUP BY project"
    )
    got = {p: (int(a), int(b)) for p, a, b in rows}
    # Tên không có dòng nào trong cửa sổ: 0 lượt tải.
    for n in safe:
        no_mirror, total = got.get(n, (0, 0))
        out[n] = (200, {"downloads_30d": no_mirror, "downloads_30d_with_mirrors": total, "window_end": end, "source": "clickpy"}, None)
    return out


# Công cụ sao chép toàn bộ PyPI: tải mọi gói, kể cả gói không ai dùng. Bỏ đi như pypistats (mirrors=false)
# để lượt tải phản ánh người dùng thật; thêm Nexus (cũng là kho trung gian).
MIRROR_INSTALLERS = ("bandersnatch", "z3c.pypimirror", "Artifactory", "devpi", "Nexus")


CLICKPY_MAX_ROWS_READ = 500_000_000  # máy chủ dừng đọc (không báo lỗi) ở 1 tỷ dòng


def _clickpy_query(sql: str) -> list[list[Any]]:
    body = (sql + " FORMAT JSONCompact").encode("utf-8")

    def once() -> Response:
        r = http_request(CLICKPY_URL, method="POST", body=body, timeout=120)
        if r.transient:
            raise _HTTPTransient(f"HTTP {r.status} ClickPy")
        return r

    r, _ = retry(once, attempts=4, is_transient=_is_transient, base_delay=3.0)
    if not r.ok:
        raise RuntimeError(f"ClickPy HTTP {r.status}: {r.body[:300].decode('utf-8', 'replace')}")
    js = r.json()
    rows_read = (js.get("statistics") or {}).get("rows_read", 0)
    if rows_read >= CLICKPY_MAX_ROWS_READ:
        raise RuntimeError(f"ClickPy đọc {rows_read} dòng, có thể đã bị cắt ngang: kết quả không tin được")
    return js.get("data", [])


def _github_repo_of(raws: dict[str, Any]) -> str | None:
    if "github_repo" in raws:
        return raws["github_repo"]
    pj = raws.get("pypi_json")
    return github_repo_from_urls(_project_urls(pj.get("info", {}))) if pj else None


def _fetch_github_bulk(names: list[str], cache: dict[str, Any], token: str | None) -> dict[str, tuple[int | None, Any, str | None]]:
    """Như _fetch_github nhưng gộp tối đa 100 kho vào một truy vấn GraphQL (mỗi truy vấn tốn ~1 điểm trong 5000 điểm/giờ).

    GraphQL bắt buộc có token. Kho không còn: 404 như REST. Kho đổi tên: GraphQL tự theo tên mới.
    """
    if not token:
        raise RuntimeError("GitHub GraphQL cần token: đặt GITHUB_TOKEN hoặc dùng nguồn github_rest")
    out: dict[str, tuple[int | None, Any, str | None]] = {}
    alias: dict[str, tuple[str, str]] = {}
    for i, n in enumerate(names):
        raws = cache.get(n, {})
        if not raws.get("pypi_json") and "github_repo" not in raws:
            out[n] = (0, {"skipped": "no pypi_json"}, None)
            continue
        repo = _github_repo_of(raws)
        if not repo:
            out[n] = (0, {"skipped": "no github url"}, None)
            continue
        alias[f"r{i}"] = (n, repo)
    if not alias:
        return out
    parts = []
    for a, (_, repo) in alias.items():
        owner, name = repo.split("/", 1)
        parts.append(f"{a}: repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) {{ nameWithOwner stargazerCount createdAt isArchived isFork }}")
    query = "query { " + " ".join(parts) + " rateLimit { remaining resetAt } }"

    def once() -> Response:
        r = http_request(
            "https://api.github.com/graphql",
            method="POST",
            headers={"Authorization": f"Bearer {token}"},
            json_body={"query": query},
            timeout=120,
        )
        if r.transient:
            raise _HTTPTransient(f"HTTP {r.status} GitHub GraphQL")
        return r

    r, _ = retry(once, attempts=4, is_transient=_is_transient, base_delay=5.0)
    if not r.ok:
        raise RuntimeError(f"GitHub GraphQL HTTP {r.status}: {r.body[:300].decode('utf-8', 'replace')}")
    js = r.json()
    data = js.get("data") or {}
    if not data and js.get("errors"):
        raise RuntimeError(f"GitHub GraphQL: {js['errors'][0].get('message', js['errors'][0])}")
    errs = {e["path"][0]: e for e in js.get("errors") or [] if e.get("path")}
    for a, (n, repo) in alias.items():
        d = data.get(a)
        if d:
            out[n] = (200, {"repo": repo, "full_name": d["nameWithOwner"], "stargazers_count": d["stargazerCount"],
                            "created_at": d["createdAt"], "archived": d["isArchived"], "fork": d["isFork"]}, None)
        elif errs.get(a, {}).get("type") == "NOT_FOUND":
            out[n] = (404, {"repo": repo}, None)
        else:
            out[n] = (None, None, f"GitHub GraphQL: {errs.get(a, {}).get('message', 'không có dữ liệu')}")
    remaining = (data.get("rateLimit") or {}).get("remaining")
    if remaining is not None and remaining < 50:
        reset = parse_time(data["rateLimit"].get("resetAt"))
        wait = max(0.0, (reset - datetime.now(timezone.utc)).total_seconds()) + 5 if reset else 60.0
        log.warning("GitHub GraphQL còn %d điểm: chờ %.0f giây", remaining, wait)
        time.sleep(wait)
    return out


FETCHERS: dict[str, Callable[[str, dict[str, Any], str | None], tuple[int, Any]]] = {
    "pypi_json": _fetch_pypi_json,
    "pypi_provenance": _fetch_provenance,
    "pypistats": _fetch_pypistats,
    "github_rest": _fetch_github,
}
# Nguồn lấy hàng loạt: nhận (danh sách tên, dữ liệu thô đã lưu, token), trả {tên: (http_status, dữ liệu, lỗi)}.
BULK_FETCHERS: dict[str, Callable[[list[str], dict[str, Any], str | None], dict[str, tuple[int | None, Any, str | None]]]] = {
    "clickpy": lambda names, cache, token: _fetch_clickpy_bulk(names),
    "github": _fetch_github_bulk,
}
BULK_BATCH = {"clickpy": 1000, "github": 100}
# Mặc định: lượt tải từ ClickPy và GitHub qua GraphQL, đều lấy hàng loạt (vài phút cho hàng chục nghìn tên)
# thay vì pypistats (~0,5 lượt/giây) và GitHub REST (~1 lượt/giây).
DEFAULT_SOURCES = ["pypi_json", "pypi_provenance", "clickpy", "github"]
DEPENDS = {"github": "pypi_json", "github_rest": "pypi_json"}  # github đọc link kho mã từ pypi_json đã lưu
NEEDS_RAWS = {"github", "github_rest"}


def compute_features(raws: dict[str, Any]) -> dict[str, Any]:
    """Tính đặc trưng từ dữ liệu thô của các nguồn."""
    feat: dict[str, Any] = {}
    repos: list[str] = []
    pj = raws.get("pypi_json")
    if pj:
        info = pj.get("info", {})
        releases = pj.get("releases", {})
        times = [f.get("upload_time_iso_8601") for files in releases.values() for f in files if f.get("upload_time_iso_8601")]
        all_files = [f for files in releases.values() for f in files]
        ownership = pj.get("ownership")
        owners = (ownership or {}).get("roles") or []
        repos = github_repos_from_urls(_project_urls(info))
        feat.update(
            pypi_name=info.get("name"),
            summary=(info.get("summary") or "")[:500],
            description_len=len(info.get("description") or ""),
            first_release_at=min(times) if times else None,
            last_release_at=max(times) if times else None,
            n_releases=sum(1 for files in releases.values() if files),
            n_files=len(all_files),
            all_yanked=int(bool(all_files) and all(f.get("yanked") for f in all_files)),
            # Gói thuộc tổ chức có thể không có người duy trì cá nhân: n_owners = 0, has_organization = 1.
            n_owners=len({r.get("user") for r in owners}) if ownership is not None else None,
            has_organization=int((ownership or {}).get("organization") is not None),
            has_project_urls=int(bool(info.get("project_urls"))),
            github_repo=repos[0] if repos else None,
        )
    prov = raws.get("pypi_provenance")
    if prov is not None:
        pubs = prov.get("publishers") or []
        if pubs:
            p = pubs[0]
            feat["provenance_kind"] = p.get("kind")
            repo = p.get("repository")
            feat["provenance_repo"] = repo.lower() if isinstance(repo, str) else None
        else:
            feat["provenance_kind"] = None
            feat["provenance_repo"] = None
        # Giống cách PyPI đánh dấu "verified": một link của project trỏ đúng kho đã phát hành qua Trusted Publishing.
        feat["source_repo_verified"] = int(bool(feat.get("provenance_repo")) and feat["provenance_repo"] in repos)
    cp = raws.get("clickpy")
    ps = raws.get("pypistats")
    if cp and cp.get("downloads_30d") is not None:
        feat["downloads_last_month"] = cp["downloads_30d"]
    elif ps:
        feat["downloads_last_month"] = (ps.get("data") or {}).get("last_month")
    gh = raws.get("github") or raws.get("github_rest")
    if gh and "stargazers_count" in gh:
        feat.update(github_stars=gh.get("stargazers_count"), github_created_at=gh.get("created_at"), github_archived=int(bool(gh.get("archived"))))
    return feat


FEATURE_COLUMNS = (
    "pypi_name", "summary", "description_len", "first_release_at", "last_release_at", "n_releases", "n_files",
    "all_yanked", "n_owners", "has_organization", "has_project_urls", "github_repo", "provenance_kind",
    "provenance_repo", "source_repo_verified", "downloads_last_month", "github_stars", "github_created_at", "github_archived",
)


def _link_cache(conn: Any, names: list[str]) -> dict[str, Any]:
    """Kho GitHub của từng tên, để nguồn github không phải đọc lại bản thô pypi_json (có gói hàng MB, đọc hết mất vài phút).

    Lấy từ package_features.github_repo nếu đặc trưng đã tính sau lần lấy pypi_json mới nhất; còn lại mới đọc link từ bản thô.
    """
    want = set(names)
    out: dict[str, Any] = {}
    q = (
        "SELECT f.norm_name, f.github_repo FROM package_features f JOIN metadata_raw r ON r.norm_name = f.norm_name "
        "AND r.source = 'pypi_json' AND r.raw_json IS NOT NULL WHERE f.pypi_name IS NOT NULL AND f.computed_at >= r.fetched_at"
    )
    for n, repo in conn.execute(q):
        if n in want:
            out[n] = {"github_repo": repo}
    q = (
        "SELECT json_extract(raw_json, '$.info.project_urls'), json_extract(raw_json, '$.info.home_page'), "
        "json_extract(raw_json, '$.info.download_url') FROM metadata_raw WHERE norm_name = ? AND source = 'pypi_json' AND raw_json IS NOT NULL"
    )
    for n in want - set(out):
        row = conn.execute(q, (n,)).fetchone()
        if row:
            urls, home, dl = row
            out[n] = {"pypi_json": {"info": {"project_urls": json.loads(urls) if urls else None, "home_page": home, "download_url": dl}}}
    return out


def load_raws(conn: Any, name: str) -> dict[str, Any]:
    out = {}
    for r in conn.execute("SELECT source, raw_json FROM metadata_raw WHERE norm_name = ? AND raw_json IS NOT NULL", (name,)):
        out[r[0]] = json.loads(r[1])
    return out


def store_features(conn: Any, name: str, feat: dict[str, Any]) -> None:
    cols = ["norm_name", "computed_at", *FEATURE_COLUMNS]
    vals = [name, utcnow(), *(feat.get(c) for c in FEATURE_COLUMNS)]
    conn.execute(f"INSERT OR REPLACE INTO package_features({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", vals)


@register("stage", "metadata")
def metadata(
    ctx: Any,
    sources: list[str] | None = None,
    snapshot: str = "latest",
    names_from: str = "mentions",
    refresh_days: float = 30,
    limit: int | None = None,
    workers: int = 4,
    rates: dict[str, float] | None = None,
    github_token_env: str = "GITHUB_TOKEN",
    github_token_file: str | None = "~/.config/github/token",
    github_anonymous: bool = False,
) -> dict[str, Any]:
    """Thu metadata cho các tên đang tồn tại trên PyPI (theo snapshot), rồi tính lại package_features.

    names_from: "mentions" (tên LLM gợi ý), "all" (thêm cả tên trong danh sách tham chiếu).
    """
    conn = ctx.conn
    srcs = list(sources or DEFAULT_SOURCES)
    for s in srcs:
        if s not in FETCHERS and s not in BULK_FETCHERS:
            raise ValueError(f"Nguồn metadata không hợp lệ: {s}. Hiện có: {sorted([*FETCHERS, *BULK_FETCHERS])}")
    sid = latest_snapshot(conn) if snapshot == "latest" else snapshot
    if not sid:
        raise RuntimeError("Chưa có snapshot PyPI: chạy pypi_index và check trước")
    q = "SELECT ps.norm_name FROM package_status ps WHERE ps.snapshot_id = ? AND ps.exists_on_pypi = 1"
    if names_from == "mentions":
        q += " AND EXISTS (SELECT 1 FROM mentions m WHERE m.norm_name = ps.norm_name)"
    names = sorted(r[0] for r in conn.execute(q, (sid,)))
    if limit:
        names = names[:limit]

    # Token GitHub: biến môi trường trước, rồi tới file (chỉ đọc khi cần nguồn github).
    token = os.environ.get(github_token_env)
    gh_srcs = [s for s in srcs if s in ("github", "github_rest")]
    if gh_srcs and not token and github_token_file:
        tf = Path(github_token_file).expanduser()
        if tf.is_file():
            token = tf.read_text(encoding="utf-8").strip() or None
    for g in gh_srcs:
        if token or (github_anonymous and g == "github_rest"):
            continue
        log.warning(
            "Bỏ nguồn %s: chưa có token (biến %s hoặc file %s); không token thì dùng nguồn github_rest với github_anonymous = true (60 lượt/giờ)",
            g,
            github_token_env,
            github_token_file,
        )
        srcs.remove(g)

    rate_cfg = {**DEFAULT_RATES, **(rates or {})}
    cutoff = datetime.now(timezone.utc) - timedelta(days=refresh_days)
    summary: dict[str, Any] = {"names": len(names), "snapshot_id": sid}

    # Các nguồn gọi tới máy chủ khác nhau nên chạy song song, mỗi nguồn một luồng với giới hạn tốc độ riêng.
    # Chỉ luồng chính ghi CSDL (sqlite không dùng chung giữa các luồng); nguồn phụ thuộc (github cần
    # pypi_json) bắt đầu khi nguồn kia xong.
    results: queue.Queue = queue.Queue()
    stop = threading.Event()
    done_marker = object()

    def produce(src: str, todo: list[str], cache: dict[str, Any]) -> None:
        try:
            if src in BULK_FETCHERS:
                size = BULK_BATCH.get(src, 100)
                for i in range(0, len(todo), size):
                    if stop.is_set():
                        return
                    chunk = todo[i : i + size]
                    try:
                        got = BULK_FETCHERS[src](chunk, cache, token)
                    except Exception as e:  # noqa: BLE001 - lưu lỗi, chạy lại lần sau
                        got = {n: (None, None, f"{type(e).__name__}: {e}") for n in chunk}
                    for n in chunk:
                        results.put((src, n, *got.get(n, (None, None, "không có kết quả"))))
                return
            limiter = RateLimiter(rate_cfg.get(src))
            fetch = FETCHERS[src]

            def job(name: str) -> tuple[str, int | None, Any, str | None] | None:
                if stop.is_set():
                    return None
                limiter.wait()
                try:
                    status, data = fetch(name, cache.get(name, {}), token)
                    return name, status, data, None
                except Exception as e:  # noqa: BLE001 - lưu lỗi, chạy lại lần sau
                    return name, None, None, f"{type(e).__name__}: {e}"

            with ThreadPoolExecutor(max_workers=max(1, workers if rate_cfg.get(src, 1) >= 1 else 1)) as pool:
                for item in pool.map(job, todo):
                    if item is not None:
                        results.put((src, *item))
        finally:
            results.put((src, done_marker, None, None, None))

    counts: dict[str, list[int]] = {}

    def start(src: str) -> None:
        fresh = {
            r[0]
            for r in conn.execute("SELECT norm_name, fetched_at FROM metadata_raw WHERE source = ? AND error IS NULL", (src,))
            if (parse_time(r[1]) or cutoff) > cutoff
        }
        todo = [n for n in names if n not in fresh]
        cache = _link_cache(conn, todo) if src in NEEDS_RAWS else {}
        counts[src] = [0, 0, len(todo), len(names) - len(todo)]  # ok, lỗi, cần lấy, còn mới
        log.info("metadata %s: %d tên cần lấy", src, len(todo))
        threading.Thread(target=produce, args=(src, todo, cache), name=f"metadata-{src}", daemon=True).start()

    waiting = [s for s in srcs if DEPENDS.get(s) in srcs]
    running = 0
    for s in srcs:
        if s not in waiting:
            start(s)
            running += 1
    last_commit = time.monotonic()
    try:
        while running:
            src, name, status, data, err = results.get()
            if name is done_marker:
                running -= 1
                ok, bad, total, _ = counts[src]
                log.info("metadata %s: xong %d/%d (lỗi %d)", src, ok + bad, total, bad)
                for w in [w for w in waiting if DEPENDS[w] == src]:
                    waiting.remove(w)
                    conn.commit()
                    start(w)
                    running += 1
                continue
            conn.execute(
                "INSERT OR REPLACE INTO metadata_raw(norm_name, source, fetched_at, http_status, raw_json, error) VALUES (?,?,?,?,?,?)",
                (name, src, utcnow(), status, json.dumps(data, ensure_ascii=False) if data is not None else None, err),
            )
            c = counts[src]
            c[0 if err is None else 1] += 1
            if (c[0] + c[1]) % 500 == 0:
                log.info("metadata %s: %d/%d", src, c[0] + c[1], c[2])
            if time.monotonic() - last_commit > 15:
                conn.commit()
                last_commit = time.monotonic()
    finally:
        stop.set()
        conn.commit()
    for src, (ok, bad, _, fresh_n) in counts.items():
        summary[src] = {"fetched": ok, "errors": bad, "fresh_skipped": fresh_n}

    with conn:
        for n in names:
            store_features(conn, n, compute_features(load_raws(conn, n)))
    summary["features"] = len(names)
    return summary
