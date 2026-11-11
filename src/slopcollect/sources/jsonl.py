"""Nguồn câu hỏi từ file JSONL, mỗi dòng: {"text", "tags"?, "source"?, "source_ref"?, "language"?, "prompt_id"?}.

Dùng để mang câu hỏi sang máy không có Internet (file do bước export_prompts tạo ra)
và cho các bộ câu hỏi tự tạo sau này.
"""

from __future__ import annotations

import json
from typing import Any, Iterator

from slopcollect.registry import register
from slopcollect.util import sha256_hex


@register("source", "jsonl")
def load(ctx: Any, path: str, source: str | None = None, tags: list[str] | None = None) -> Iterator[dict[str, Any]]:
    with open(ctx.path(path), encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            obj = json.loads(line)
            text = obj["text"]
            if "prompt_id" in obj and obj["prompt_id"] != sha256_hex(text):
                raise ValueError(f"{path}:{line_no}: prompt_id không khớp nội dung (file bị sửa hoặc lỗi mã hóa)")
            yield {
                "text": text,
                "source": source or obj.get("source", "jsonl"),
                "source_ref": obj.get("source_ref", f"{path}:{line_no}"),
                "language": obj.get("language", "python"),
                "tags": list(obj.get("tags", [])) + list(tags or []),
            }
