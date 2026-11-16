"""Bước select_variants: chọn tên bịa để hỏi lại câu hỏi gốc nhiều lần (thu biến thể).

Với mỗi tên được chọn, lấy một câu hỏi gốc đã sinh ra tên đó (cùng model), gắn tag
``sel:<selection_id>:<model_key>`` cho câu hỏi. Bước generate sau đó chạy với tag này và
``n_samples`` > 1 để hỏi lại.
"""

from __future__ import annotations

from typing import Any

from slopcollect.registry import register
from slopcollect.util import stable_order_key


@register("stage", "select_variants")
def select_variants(
    ctx: Any,
    selection_id: str = "variants-v1",
    n: int = 500,
    labels: list[str] | None = None,
    labeler_version: str = "rules-v1",
    models: list[str] | None = None,
    tasks: list[str] | None = None,
    methods: list[str] | None = None,
    seed: str = "variants-v1",
) -> dict[str, Any]:
    """Chọn ``n`` cặp (tên bịa, model), chia đều giữa các model; mỗi cặp gắn với một câu hỏi gốc."""
    conn = ctx.conn
    labs = labels or ["hallucinated_absent", "registered_hallucination"]
    meths = methods or ["pip_install", "llm_list"]
    q = (
        "SELECT DISTINCT v.norm_name, v.model_key, v.prompt_id, l.label FROM v_mentions v "
        "JOIN labels l ON l.norm_name = v.norm_name AND l.labeler_version = ? "
        f"WHERE l.label IN ({','.join('?' * len(labs))}) AND v.method IN ({','.join('?' * len(meths))})"
    )
    args: list[Any] = [labeler_version, *labs, *meths]
    if models:
        q += f" AND v.model_key IN ({','.join('?' * len(models))})"
        args += models
    if tasks:
        q += f" AND v.task_id IN ({','.join('?' * len(tasks))})"
        args += tasks
    rows = conn.execute(q, args).fetchall()

    # Mỗi (tên, model) chọn một câu hỏi cố định.
    by_pair: dict[tuple[str, str], tuple[str, str]] = {}
    for r in sorted(rows, key=lambda r: stable_order_key(seed, r["prompt_id"])):
        by_pair.setdefault((r["norm_name"], r["model_key"]), (r["prompt_id"], r["label"]))
    per_model: dict[str, list[tuple[str, str, str]]] = {}
    for (name, model), (pid, lab) in by_pair.items():
        per_model.setdefault(model, []).append((name, pid, lab))
    for m in per_model:
        per_model[m].sort(key=lambda x: stable_order_key(seed, x[0]))

    # Chia đều theo vòng; model nào hết tên thì nhường cho model khác.
    chosen: list[tuple[str, str, str, str]] = []
    idx = {m: 0 for m in per_model}
    order = sorted(per_model)
    while len(chosen) < n and any(idx[m] < len(per_model[m]) for m in order):
        for m in order:
            if len(chosen) >= n:
                break
            if idx[m] < len(per_model[m]):
                name, pid, lab = per_model[m][idx[m]]
                chosen.append((name, m, pid, lab))
                idx[m] += 1

    with conn:
        # Chọn lại thì thay lựa chọn cũ; nếu chỉ định models thì chỉ thay phần của các model đó
        # (GLM chạy sau, chọn riêng mà không xóa lựa chọn của model khác trong cùng selection_id).
        if models:
            for m in models:
                conn.execute("DELETE FROM selections WHERE selection_id = ? AND model_key = ?", (selection_id, m))
                conn.execute("DELETE FROM prompt_tags WHERE tag = ?", (f"sel:{selection_id}:{m}",))
        else:
            conn.execute("DELETE FROM selections WHERE selection_id = ?", (selection_id,))
            conn.execute("DELETE FROM prompt_tags WHERE tag LIKE ?", (f"sel:{selection_id}:%",))
        for name, model, pid, lab in chosen:
            conn.execute(
                "INSERT OR IGNORE INTO selections(selection_id, norm_name, model_key, prompt_id, label, run_id) VALUES (?,?,?,?,?,?)",
                (selection_id, name, model, pid, lab, ctx.run_id),
            )
            conn.execute("INSERT OR IGNORE INTO prompt_tags(prompt_id, tag) VALUES (?,?)", (pid, f"sel:{selection_id}:{model}"))
    counts: dict[str, int] = {}
    for _, m, _, _ in chosen:
        counts[m] = counts.get(m, 0) + 1
    prompts = {(m, pid) for _, m, pid, _ in chosen}
    return {"selection_id": selection_id, "selected_names": len(chosen), "per_model": counts, "prompts": len(prompts), "candidates": len(by_pair)}
