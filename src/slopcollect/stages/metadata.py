"""Bước metadata: thu thông tin của các gói đang có trên PyPI, rồi tính bảng đặc trưng package_features.

Nguồn (mỗi nguồn lưu bản thô trong metadata_raw, chạy lại thì bỏ qua bản còn mới):
  - pypi_json:       https://pypi.org/pypi/<tên>/json  (phát hành, mô tả, link, người duy trì)
  - pypi_provenance: Simple API JSON của project -> link provenance (PEP 740) của file mới nhất
                     -> kho mã nguồn mà PyPI đã xác minh qua Trusted Publishing
  - pypistats:       https://pypistats.org/api/packages/<tên>/recent  (lượt tải 30 ngày)
  - github:          https://api.github.com/repos/<owner>/<repo>  (sao, ngày tạo; cần GITHUB_TOKEN)
"""

from __future__ import annotations

import json
import logging
import os
import re
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
    pj = raws.get("pypi_json")
    if not pj:
        return 0, {"skipped": "no pypi_json"}
    repo = github_repo_from_urls(_project_urls(pj.get("info", {})))
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


FETCHERS: dict[str, Callable[[str, dict[str, Any], str | None], tuple[int, Any]]] = {
    "pypi_json": _fetch_pypi_json,
    "pypi_provenance": _fetch_provenance,
    "pypistats": _fetch_pypistats,
    "github": _fetch_github,
}


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
    ps = raws.get("pypistats")
    if ps:
        feat["downloads_last_month"] = (ps.get("data") or {}).get("last_month")
    gh = raws.get("github")
    if gh and "stargazers_count" in gh:
        feat.update(github_stars=gh.get("stargazers_count"), github_created_at=gh.get("created_at"), github_archived=int(bool(gh.get("archived"))))
    return feat


FEATURE_COLUMNS = (
    "pypi_name", "summary", "description_len", "first_release_at", "last_release_at", "n_releases", "n_files",
    "all_yanked", "n_owners", "has_organization", "has_project_urls", "github_repo", "provenance_kind",
    "provenance_repo", "source_repo_verified", "downloads_last_month", "github_stars", "github_created_at", "github_archived",
)


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
    srcs = list(sources or FETCHERS)
    for s in srcs:
        if s not in FETCHERS:
            raise ValueError(f"Nguồn metadata không hợp lệ: {s}. Hiện có: {sorted(FETCHERS)}")
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
    if "github" in srcs and not token and github_token_file:
        tf = Path(github_token_file).expanduser()
        if tf.is_file():
            token = tf.read_text(encoding="utf-8").strip() or None
    if "github" in srcs and not token and not github_anonymous:
        log.warning(
            "Bỏ nguồn github: chưa có token (biến %s hoặc file %s); đặt github_anonymous = true để gọi không token, 60 lượt/giờ",
            github_token_env,
            github_token_file,
        )
        srcs.remove("github")

    rate_cfg = {**DEFAULT_RATES, **(rates or {})}
    cutoff = datetime.now(timezone.utc) - timedelta(days=refresh_days)
    summary: dict[str, Any] = {"names": len(names), "snapshot_id": sid}
    for src in srcs:
        fresh = {
            r[0]
            for r in conn.execute("SELECT norm_name, fetched_at FROM metadata_raw WHERE source = ? AND error IS NULL", (src,))
            if (parse_time(r[1]) or cutoff) > cutoff
        }
        todo = [n for n in names if n not in fresh]
        limiter = RateLimiter(rate_cfg.get(src))
        fetch = FETCHERS[src]
        # Nguồn github cần pypi_json đã lưu: đọc trước ở luồng chính (sqlite không dùng chung giữa các luồng).
        cache = {n: load_raws(conn, n) for n in todo} if src == "github" else {}

        def job(name: str, _fetch: Any = fetch, _lim: RateLimiter = limiter, _cache: dict[str, Any] = cache) -> tuple[str, int | None, Any, str | None]:
            _lim.wait()
            try:
                status, data = _fetch(name, _cache.get(name, {}), token)
                return name, status, data, None
            except Exception as e:  # noqa: BLE001 - lưu lỗi, chạy lại lần sau
                return name, None, None, f"{type(e).__name__}: {e}"

        n_ok = n_err = 0
        log.info("metadata %s: %d tên cần lấy", src, len(todo))
        with ThreadPoolExecutor(max_workers=max(1, workers if rate_cfg.get(src, 1) >= 1 else 1)) as pool:
            for i, (name, status, data, err) in enumerate(pool.map(job, todo), 1):
                conn.execute(
                    "INSERT OR REPLACE INTO metadata_raw(norm_name, source, fetched_at, http_status, raw_json, error) VALUES (?,?,?,?,?,?)",
                    (name, src, utcnow(), status, json.dumps(data, ensure_ascii=False) if data is not None else None, err),
                )
                n_ok += err is None
                n_err += err is not None
                if i % 100 == 0:
                    conn.commit()
                    log.info("metadata %s: %d/%d", src, i, len(todo))
        conn.commit()
        summary[src] = {"fetched": n_ok, "errors": n_err, "fresh_skipped": len(names) - len(todo)}

    with conn:
        for n in names:
            store_features(conn, n, compute_features(load_raws(conn, n)))
    summary["features"] = len(names)
    return summary
