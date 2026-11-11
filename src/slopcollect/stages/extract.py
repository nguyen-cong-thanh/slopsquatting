"""Bước extract: trích tên gói từ câu trả lời, chuẩn hóa theo luật PyPI, lưu vào bảng mentions.

Cách trích của từng tác vụ khai báo trong configs/tasks/<task>.toml (khóa ``extract``).
"""

from __future__ import annotations

from typing import Any

from slopcollect.config import ConfigError
from slopcollect.extract.normalize import is_valid_project_name, normalize_pep426_name, ultranormalize_name
from slopcollect.extract.parsers import EXTRACTORS
from slopcollect.registry import register

# x1: bản đầu. x2: dừng ở ghi chú trong ngoặc sau "pip install"; bảng ánh xạ bổ sung; namespace google.*/azure.*.
EXTRACTOR_VERSION = "x2"


@register("stage", "extract")
def extract(
    ctx: Any,
    version: str = EXTRACTOR_VERSION,
    methods: dict[str, list[str]] | None = None,
    batch: int = 500,
    replace_other_versions: bool = True,
) -> dict[str, Any]:
    """Trích tên cho mọi câu trả lời chưa được trích ở phiên bản ``version``.

    methods: ghi đè cách trích theo tác vụ, ví dụ {spracklen_code_v1 = ["pip_install"]}.
    replace_other_versions: xóa kết quả của các phiên bản bộ trích khác, để không đếm trùng
    (các bước sau đọc mọi dòng trong bảng mentions).
    """
    conn = ctx.conn
    removed = 0
    if replace_other_versions:
        with conn:
            removed = conn.execute("DELETE FROM mentions WHERE extractor_version != ?", (version,)).rowcount
            conn.execute("DELETE FROM extract_done WHERE extractor_version != ?", (version,))
    rows = conn.execute(
        "SELECT g.gen_id, g.task_id, g.response_text, g.finish_reason FROM generations g "
        "WHERE g.error IS NULL AND g.response_text IS NOT NULL AND NOT EXISTS ("
        "SELECT 1 FROM extract_done d WHERE d.gen_id = g.gen_id AND d.extractor_version = ?)",
        (version,),
    ).fetchall()
    n_gen = n_mentions = 0
    per_method: dict[str, int] = {}
    for i, r in enumerate(rows, 1):
        task_methods = (methods or {}).get(r["task_id"])
        if task_methods is None:
            try:
                task_methods = list(ctx.task(r["task_id"]).extract)
            except ConfigError as e:
                raise ConfigError(f"Không đọc được tác vụ '{r['task_id']}' để biết cách trích tên: {e}") from e
        truncated = r["finish_reason"] == "length"
        seen: set[tuple[str, str]] = set()
        for method in task_methods:
            if method not in EXTRACTORS:
                raise ConfigError(f"Cách trích không hợp lệ '{method}'. Hiện có: {sorted(EXTRACTORS)}")
            for f in EXTRACTORS[method](r["response_text"], truncated):
                norm = normalize_pep426_name(f.name)
                if (method, norm) in seen:
                    continue
                seen.add((method, norm))
                conn.execute(
                    "INSERT OR IGNORE INTO mentions(gen_id, extractor_version, method, norm_name, raw, module, ultra_name, valid_name) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (r["gen_id"], version, method, norm, f.raw[:500], f.module, ultranormalize_name(f.name), int(is_valid_project_name(norm))),
                )
                per_method[method] = per_method.get(method, 0) + 1
        conn.execute(
            "INSERT OR REPLACE INTO extract_done(gen_id, extractor_version, n_mentions, run_id) VALUES (?,?,?,?)",
            (r["gen_id"], version, len(seen), ctx.run_id),
        )
        n_gen += 1
        n_mentions += len(seen)
        if i % batch == 0:
            conn.commit()
    conn.commit()
    return {"generations": n_gen, "mentions": n_mentions, "per_method": per_method, "version": version, "removed_old_mentions": removed}
