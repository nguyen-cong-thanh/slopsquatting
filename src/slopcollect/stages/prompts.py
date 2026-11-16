"""Bước load_prompts (nạp câu hỏi vào CSDL) và export_prompts (xuất câu hỏi ra JSONL)."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from slopcollect import registry
from slopcollect.registry import register
from slopcollect.util import sha256_hex, stable_order_key, utcnow


@register("stage", "load_prompts")
def load_prompts(ctx: Any, source: str, tags: list[str] | None = None, **source_params: Any) -> dict[str, Any]:
    """Nạp câu hỏi từ một nguồn (spracklen, jsonl, ...). Câu trùng nội dung chỉ lưu một lần, gộp tag."""
    loader = registry.get("source", source)
    conn = ctx.conn
    n_rows = n_new = 0
    now = utcnow()
    for rec in loader(ctx, **source_params):
        n_rows += 1
        pid = sha256_hex(rec["text"])
        cur = conn.execute(
            "INSERT OR IGNORE INTO prompts(prompt_id, text, source, source_ref, language, created_at) VALUES (?,?,?,?,?,?)",
            (pid, rec["text"], rec["source"], rec.get("source_ref"), rec.get("language", "python"), now),
        )
        n_new += cur.rowcount
        for tag in list(rec.get("tags", [])) + list(tags or []):
            conn.execute("INSERT OR IGNORE INTO prompt_tags(prompt_id, tag) VALUES (?,?)", (pid, tag))
    conn.commit()
    n_total = conn.execute("SELECT COUNT(*) FROM prompts").fetchone()[0]
    return {"rows_read": n_rows, "new_prompts": n_new, "prompts_in_db": n_total}


def select_prompts(
    conn: sqlite3.Connection,
    tags: list[str] | None,
    *,
    limit: int | None = None,
    order_seed: str = "slopcollect-v1",
) -> list[sqlite3.Row]:
    """Chọn câu hỏi có ít nhất một tag trong danh sách, theo thứ tự ngẫu nhiên cố định.

    Vì thứ tự cố định, ``limit=200`` luôn là phần đầu của ``limit=2000``: chạy thử rồi
    chạy toàn bộ sẽ tái sử dụng các câu đã hỏi.
    """
    if tags:
        q = (
            "SELECT p.prompt_id, p.text FROM prompts p WHERE EXISTS ("
            "SELECT 1 FROM prompt_tags t WHERE t.prompt_id = p.prompt_id AND t.tag IN "
            f"({','.join('?' * len(tags))}))"
        )
        rows = conn.execute(q, tags).fetchall()
    else:
        rows = conn.execute("SELECT prompt_id, text FROM prompts").fetchall()
    rows.sort(key=lambda r: stable_order_key(order_seed, r["prompt_id"]))
    return rows[:limit] if limit else rows


@register("stage", "export_prompts")
def export_prompts(
    ctx: Any,
    out: str,
    tags: list[str] | None = None,
    limit: int | None = None,
    order_seed: str = "slopcollect-v1",
) -> dict[str, Any]:
    """Xuất câu hỏi (kèm prompt_id và tag) ra JSONL để mang sang máy khác."""
    rows = select_prompts(ctx.conn, tags, limit=limit, order_seed=order_seed)
    path = ctx.path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            meta = ctx.conn.execute(
                "SELECT source, source_ref, language FROM prompts WHERE prompt_id = ?", (r["prompt_id"],)
            ).fetchone()
            ptags = [t[0] for t in ctx.conn.execute("SELECT tag FROM prompt_tags WHERE prompt_id = ? ORDER BY tag", (r["prompt_id"],))]
            f.write(
                json.dumps(
                    {
                        "prompt_id": r["prompt_id"],
                        "text": r["text"],
                        "source": meta["source"],
                        "source_ref": meta["source_ref"],
                        "language": meta["language"],
                        "tags": ptags,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    return {"exported": len(rows), "out": str(path)}
