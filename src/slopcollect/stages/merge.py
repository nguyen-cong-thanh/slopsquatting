"""Bước merge: gộp file SQLite mang về từ máy khác (ví dụ máy chạy GLM) vào CSDL hiện tại."""

from __future__ import annotations

from typing import Any

from slopcollect.db import merge_from
from slopcollect.registry import register


@register("stage", "merge")
def merge(ctx: Any, paths: list[str]) -> dict[str, Any]:
    out = {}
    for p in paths:
        path = ctx.path(p)
        if path.resolve() == ctx.db_path.resolve():
            raise ValueError(f"Không thể gộp CSDL vào chính nó: {path}")
        added = merge_from(ctx.conn, path)
        out[str(p)] = {k: v for k, v in added.items() if v}
    return out
