"""Bước known_lists: tải các danh sách tham chiếu, chỉ giữ phần PyPI.

  - 0pstech:       tên bịa do LLM gợi ý, kiểm tra định kỳ (CC BY 4.0)
  - depscope:      tên bịa quan sát từ agent lập trình (snapshot mới nhất)
  - datadog:       gói độc hại PyPI đã bị phát hiện (manifest của DataDog)
  - osv_malicious: gói độc hại PyPI trong OSV (mã MAL-*, nhập từ OpenSSF malicious-packages)

Mỗi danh sách là một plugin ``list_source``; thêm danh sách mới không cần sửa bước này.
Có thể đọc từ file cục bộ thay vì tải: ``paths = {datadog = "duong/dan/manifest.json"}``.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import zipfile
from pathlib import Path
from typing import Any, Iterator

from slopcollect import registry
from slopcollect.extract.normalize import normalize_pep426_name
from slopcollect.registry import register
from slopcollect.util import http_request, utcnow

log = logging.getLogger("slopcollect")


def _download(url: str, timeout: float = 300) -> bytes:
    log.info("tải %s", url)
    r = http_request(url, timeout=timeout)
    if not r.ok:
        raise RuntimeError(f"Tải {url} thất bại: HTTP {r.status}")
    return r.body


def _read(ctx: Any, path: str | None, url: str, cache_name: str) -> bytes:
    if path:
        return ctx.path(path).read_bytes()
    data = _download(url)
    cache = ctx.path(Path("data/raw/lists") / cache_name)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(data)
    return data


@register("list_source", "0pstech")
def opstech(ctx: Any, path: str | None = None) -> Iterator[tuple[str, dict[str, Any]]]:
    url = "https://raw.githubusercontent.com/0pstech/slopsquatting-dataset/HEAD/slopsquatting.csv"
    text = _read(ctx, path, url, "0pstech.csv").decode("utf-8")
    for row in csv.DictReader(io.StringIO(text)):
        if row.get("ecosystem") == "PyPI":
            yield row["name"], {k: row.get(k) for k in ("id", "registry_status", "models", "first_seen", "risk")}


@register("list_source", "depscope")
def depscope(ctx: Any, path: str | None = None) -> Iterator[tuple[str, dict[str, Any]]]:
    if path:
        data = json.loads(ctx.path(path).read_text(encoding="utf-8"))
    else:
        api = "https://api.github.com/repos/cuttalo/depscope-hallucinations-dataset/contents/snapshots"
        listing = json.loads(_download(api))
        latest = sorted(x["name"] for x in listing if x["name"].endswith(".json"))[-1]
        raw = _download(f"https://raw.githubusercontent.com/cuttalo/depscope-hallucinations-dataset/HEAD/snapshots/{latest}")
        cache = ctx.path("data/raw/lists/depscope.json")
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(raw)
        data = json.loads(raw)
    for e in data.get("entries", []):
        if e.get("ecosystem") == "pypi":
            yield e["package_name"], {k: e.get(k) for k in ("source", "first_seen_at", "hit_count", "likely_real_alternative")}


@register("list_source", "datadog")
def datadog(ctx: Any, path: str | None = None) -> Iterator[tuple[str, dict[str, Any]]]:
    url = "https://raw.githubusercontent.com/DataDog/malicious-software-packages-dataset/HEAD/samples/pypi/manifest.json"
    data = json.loads(_read(ctx, path, url, "datadog_pypi_manifest.json"))
    for name, versions in data.items():
        yield name, {"versions": versions}


@register("list_source", "osv_malicious")
def osv_malicious(ctx: Any, path: str | None = None) -> Iterator[tuple[str, dict[str, Any]]]:
    url = "https://osv-vulnerabilities.storage.googleapis.com/PyPI/all.zip"
    blob = _read(ctx, path, url, "osv_pypi_all.zip")
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        for member in zf.namelist():
            if not Path(member).name.startswith("MAL-"):
                continue
            rec = json.loads(zf.read(member))
            if rec.get("withdrawn"):
                continue
            for aff in rec.get("affected", []):
                pkg = aff.get("package", {})
                if pkg.get("ecosystem") == "PyPI" and pkg.get("name"):
                    yield pkg["name"], {"id": rec.get("id"), "published": rec.get("published")}


@register("stage", "known_lists")
def known_lists(ctx: Any, lists: list[str] | None = None, paths: dict[str, str] | None = None) -> dict[str, Any]:
    """Tải lại từng danh sách và thay toàn bộ nội dung cũ của danh sách đó."""
    conn = ctx.conn
    names = lists or ["0pstech", "depscope", "datadog", "osv_malicious"]
    summary = {}
    for list_id in names:
        loader = registry.get("list_source", list_id)
        items: dict[str, tuple[str, dict[str, Any]]] = {}
        for raw_name, extra in loader(ctx, path=(paths or {}).get(list_id)):
            items.setdefault(normalize_pep426_name(raw_name), (raw_name, extra))
        now = utcnow()
        with conn:
            conn.execute("DELETE FROM known_lists WHERE list_id = ?", (list_id,))
            conn.executemany(
                "INSERT INTO known_lists(list_id, norm_name, raw_name, extra_json, fetched_at) VALUES (?,?,?,?,?)",
                ((list_id, n, raw, json.dumps(extra, ensure_ascii=False), now) for n, (raw, extra) in items.items()),
            )
        summary[list_id] = len(items)
    return summary
