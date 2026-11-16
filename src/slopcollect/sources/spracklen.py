"""Bộ câu hỏi Python của Spracklen và cộng sự (USENIX Security 2025), repo Spracks/PackageHallucination (MIT).

Bốn file: LLM_AT, LLM_LY (câu hỏi do LLM sinh), SO_AT, SO_LY (câu hỏi Stack Overflow).
Tổng 19.084 dòng, 18.033 câu không trùng (đã kiểm tra ngày 11/11/2026).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Iterator

from slopcollect.registry import register
from slopcollect.util import http_request

log = logging.getLogger("slopcollect")

REPO = "Spracks/PackageHallucination"
PINNED_COMMIT = "bd3031cce6a0007997a0604d3ad3365031ed79b2"  # 2026-08-14
FILES = ("LLM_AT.json", "LLM_LY.json", "SO_AT.json", "SO_LY.json")


def _download(dest: Path, commit: str, files: tuple[str, ...]) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for name in files:
        target = dest / name
        if target.exists() and target.stat().st_size > 0:
            continue
        url = f"https://raw.githubusercontent.com/{REPO}/{commit}/Data/Python/{name}"
        log.info("tải %s", url)
        resp = http_request(url, timeout=300)
        if not resp.ok:
            raise RuntimeError(f"Tải {url} thất bại: HTTP {resp.status}")
        tmp = target.with_suffix(".part")
        tmp.write_bytes(resp.body)
        tmp.replace(target)
    (dest / "SOURCE.txt").write_text(f"https://github.com/{REPO}/tree/{commit}/Data/Python\n", encoding="utf-8")


@register("source", "spracklen")
def load(
    ctx: Any,
    path: str = "data/raw/spracklen",
    download: bool = True,
    commit: str = PINNED_COMMIT,
    files: list[str] | None = None,
) -> Iterator[dict[str, Any]]:
    files_t = tuple(files or FILES)
    dest = ctx.path(path)
    if download:
        _download(dest, commit, files_t)
    for name in files_t:
        subset = name.removesuffix(".json")
        with open(dest / name, encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                if not line.strip():
                    continue
                obj = json.loads(line)
                # File SO_* lưu mỗi dòng dạng {"0": "..."}; file LLM_* lưu chuỗi JSON.
                text = next(iter(obj.values())) if isinstance(obj, dict) else obj
                if not isinstance(text, str) or not text.strip():
                    continue
                yield {
                    "text": text,
                    "source": "spracklen",
                    "source_ref": f"{commit[:12]}:{name}:{line_no}",
                    "language": "python",
                    "tags": ["spracklen", f"spracklen:{subset}"],
                }
