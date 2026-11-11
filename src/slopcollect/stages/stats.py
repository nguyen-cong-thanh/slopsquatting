"""Bước stats: số liệu để chốt quy mô sau khi chạy thử (mục "Bước tiếp theo" của báo cáo 07/11/2026).

1. Tốc độ sinh và thời gian ước tính cho toàn bộ bộ câu hỏi.
2. Số tên không trùng; tỷ lệ tên không có trên PyPI (theo lượt gợi ý và theo tên).
3. Đường số tên bịa không trùng tăng theo số câu hỏi.
4. Tỷ lệ tên bịa đã có người đăng ký; lý do không đăng ký được.
5. Số biến thể khi hỏi lại cùng một câu (nếu đã chạy select_variants + generate n_samples > 1).
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from slopcollect.config import ConfigError
from slopcollect.db import latest_snapshot
from slopcollect.registry import register
from slopcollect.util import stable_order_key, utcnow

HALLUCINATED = ("hallucinated_absent", "registered_hallucination")
CHECKPOINTS = (10, 25, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 18033)


def _generation_stats(ctx: Any, n_full: int) -> dict[str, Any]:
    conn = ctx.conn
    rows = conn.execute(
        "SELECT model_key, task_id, COUNT(*) AS n, SUM(error IS NULL) AS ok, SUM(error IS NOT NULL) AS err, "
        "COUNT(DISTINCT prompt_id) AS prompts, AVG(CASE WHEN error IS NULL THEN latency_ms END) AS avg_latency_ms, "
        "SUM(CASE WHEN error IS NULL THEN tokens_out END) AS tok_out, SUM(CASE WHEN error IS NULL THEN latency_ms END) AS lat_ms, "
        "AVG(CASE WHEN error IS NULL THEN tokens_out END) AS avg_tokens_out, "
        "SUM(finish_reason = 'length') AS truncated "
        "FROM generations GROUP BY model_key, task_id ORDER BY model_key, task_id"
    ).fetchall()
    out: dict[str, Any] = {}
    for r in rows:
        m = out.setdefault(r["model_key"], {"tasks": {}, "seconds_per_prompt": 0.0})
        per_prompt = (r["avg_latency_ms"] or 0) / 1000 * (r["ok"] / max(r["prompts"], 1))
        m["tasks"][r["task_id"]] = {
            "generations": r["n"],
            "ok": r["ok"],
            "errors": r["err"],
            "prompts": r["prompts"],
            "avg_latency_s": round((r["avg_latency_ms"] or 0) / 1000, 2),
            "avg_tokens_out": round(r["avg_tokens_out"] or 0, 1),
            "tokens_per_s": round((r["tok_out"] or 0) / ((r["lat_ms"] or 0) / 1000), 1) if r["lat_ms"] else None,
            "truncated_by_max_tokens": r["truncated"],
        }
        m["seconds_per_prompt"] += per_prompt
    for key, m in out.items():
        try:
            conc = ctx.model(key).concurrency
        except ConfigError:
            conc = 1
        m["concurrency"] = conc
        m["eta_hours_full"] = round(n_full * m["seconds_per_prompt"] / conc / 3600, 1)
        m["seconds_per_prompt"] = round(m["seconds_per_prompt"], 2)
    return out


@register("stage", "stats")
def stats(
    ctx: Any,
    out: str = "data/exports/stats",
    labeler_version: str = "rules-v1",
    snapshot: str = "latest",
    methods: list[str] | None = None,
    order_seed: str = "slopcollect-v1",
    n_full: int = 18033,
    selection_id: str | None = None,
) -> dict[str, Any]:
    conn = ctx.conn
    meths = methods or ["pip_install", "llm_list"]
    sid = latest_snapshot(conn) if snapshot == "latest" else snapshot
    res: dict[str, Any] = {"generated_at": utcnow(), "snapshot_id": sid, "methods": meths, "labeler_version": labeler_version}
    res["generation"] = _generation_stats(ctx, n_full)

    ph = ",".join("?" * len(meths))
    mention_rows = conn.execute(
        f"SELECT v.model_key, v.method, v.norm_name, v.prompt_id, v.root_sample_idx, v.task_id, v.parent_gen_id, "
        f"ps.exists_on_pypi, ps.registrable, ps.reason, l.label "
        f"FROM v_mentions v "
        f"LEFT JOIN package_status ps ON ps.norm_name = v.norm_name AND ps.snapshot_id = ? "
        f"LEFT JOIN labels l ON l.norm_name = v.norm_name AND l.labeler_version = ? "
        f"WHERE v.method IN ({ph})",
        (sid, labeler_version, *meths),
    ).fetchall()

    per_model: dict[str, Any] = {}
    by_model: dict[str, list[Any]] = defaultdict(list)
    for r in mention_rows:
        by_model[r["model_key"]].append(r)
    for model, rows in by_model.items():
        # Tên module thư viện chuẩn (json, os...) không tính là tên bịa: bỏ khỏi cả tử số và mẫu số.
        checked = [r for r in rows if r["exists_on_pypi"] is not None and not (not r["exists_on_pypi"] and r["reason"] == "stdlib")]
        absent = [r for r in checked if not r["exists_on_pypi"]]
        names = {r["norm_name"] for r in rows}
        absent_names = {r["norm_name"] for r in absent}
        labels: dict[str, int] = defaultdict(int)
        for n, lab in {(r["norm_name"], r["label"]) for r in rows}:
            labels[lab or "chưa_gắn_nhãn"] += 1
        hall = labels.get("hallucinated_absent", 0) + labels.get("registered_hallucination", 0)
        reasons: dict[str, int] = defaultdict(int)
        for n, reg, reason in {(r["norm_name"], r["registrable"], r["reason"]) for r in absent}:
            reasons["registrable" if reg else reason] += 1
        per_method = {}
        for meth in meths:
            mr = [r for r in checked if r["method"] == meth]
            per_method[meth] = {
                "mentions": len(mr),
                "absent_share_by_mention": round(sum(not r["exists_on_pypi"] for r in mr) / len(mr), 4) if mr else None,
            }
        # Đường tăng số tên bịa không trùng theo số câu hỏi (thứ tự câu hỏi giống bước generate).
        prompt_names: dict[str, set[str]] = defaultdict(set)
        for r in absent:
            prompt_names[r["prompt_id"]].add(r["norm_name"])
        prompts_done = sorted(
            {r[0] for r in conn.execute("SELECT DISTINCT prompt_id FROM generations WHERE model_key = ? AND error IS NULL AND parent_gen_id IS NULL", (model,))},
            key=lambda p: stable_order_key(order_seed, p),
        )
        curve = []
        seen: set[str] = set()
        for i, pid in enumerate(prompts_done, 1):
            seen.update(prompt_names.get(pid, ()))
            if i in CHECKPOINTS or i == len(prompts_done):
                curve.append({"prompts": i, "unique_absent_names": len(seen)})
        per_model[model] = {
            "mentions": len(rows),
            "unique_names": len(names),
            "unique_absent_names": len(absent_names),
            "absent_share_by_mention": round(len(absent) / len(checked), 4) if checked else None,
            "absent_share_by_name": round(len(absent_names) / len({r["norm_name"] for r in checked}), 4) if checked else None,
            "per_method": per_method,
            "labels_by_name": dict(labels),
            "registered_share_of_hallucinated": round(labels.get("registered_hallucination", 0) / hall, 4) if hall else None,
            "absent_registrability": dict(reasons),
            "curve": curve,
        }
    res["per_model"] = per_model
    res["variants"] = _variant_stats(conn, selection_id, labeler_version, meths) if selection_id else None

    path = ctx.path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.with_suffix(".json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    path.with_suffix(".md").write_text(_markdown(res), encoding="utf-8")
    return {"out": str(path.with_suffix(".md")), "models": list(per_model)}


def _variant_stats(conn: Any, selection_id: str, labeler_version: str, meths: list[str]) -> dict[str, Any]:
    sel = conn.execute("SELECT norm_name, model_key, prompt_id FROM selections WHERE selection_id = ?", (selection_id,)).fetchall()
    ph = ",".join("?" * len(meths))
    out_rows = []
    for s in sel:
        samples = {
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT sample_idx FROM generations WHERE model_key = ? AND prompt_id = ? AND parent_gen_id IS NULL AND error IS NULL",
                (s["model_key"], s["prompt_id"]),
            )
        }
        rows = conn.execute(
            f"SELECT v.norm_name, v.root_sample_idx, l.label FROM v_mentions v "
            f"LEFT JOIN labels l ON l.norm_name = v.norm_name AND l.labeler_version = ? "
            f"WHERE v.model_key = ? AND v.prompt_id = ? AND v.method IN ({ph})",
            (labeler_version, s["model_key"], s["prompt_id"], *meths),
        ).fetchall()
        with_orig = {r["root_sample_idx"] for r in rows if r["norm_name"] == s["norm_name"]}
        hall_names = {r["norm_name"] for r in rows if r["label"] in HALLUCINATED}
        out_rows.append({"samples": len(samples), "orig_repeat": len(with_orig), "distinct_hallucinated": len(hall_names)})
    n = len(out_rows)
    if not n:
        return {"selection_id": selection_id, "selected": 0}
    return {
        "selection_id": selection_id,
        "selected": n,
        "mean_samples": round(sum(r["samples"] for r in out_rows) / n, 2),
        "mean_orig_repeat_share": round(sum(r["orig_repeat"] / r["samples"] for r in out_rows if r["samples"]) / n, 4),
        "share_orig_in_all_samples": round(sum(r["orig_repeat"] == r["samples"] for r in out_rows if r["samples"]) / n, 4),
        "share_orig_only_once": round(sum(r["orig_repeat"] <= 1 for r in out_rows) / n, 4),
        "mean_distinct_hallucinated_per_prompt": round(sum(r["distinct_hallucinated"] for r in out_rows) / n, 2),
    }


def _markdown(res: dict[str, Any]) -> str:
    lines = [f"# Thống kê thu thập dữ liệu\n\nTạo lúc {res['generated_at']} · snapshot PyPI `{res['snapshot_id']}` · cách trích: {', '.join(res['methods'])}\n"]
    lines.append("## Tốc độ sinh\n")
    lines.append("| Model | Tác vụ | Thành công | Lỗi | Câu hỏi | Độ trễ TB (s) | Token ra TB | Token/s | Bị cắt |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for model, m in res["generation"].items():
        for task, t in m["tasks"].items():
            lines.append(
                f"| {model} | {task} | {t['ok']} | {t['errors']} | {t['prompts']} | {t['avg_latency_s']} | {t['avg_tokens_out']} | {t['tokens_per_s']} | {t['truncated_by_max_tokens']} |"
            )
    lines.append("")
    for model, m in res["generation"].items():
        lines.append(f"- **{model}:** {m['seconds_per_prompt']} giây/câu hỏi (mọi tác vụ), song song {m['concurrency']} → toàn bộ ước tính **{m['eta_hours_full']} giờ**.")
    lines.append("\n## Tên gói\n")
    lines.append("| Model | Lượt gợi ý | Tên không trùng | Tên không có trên PyPI | Tỷ lệ theo lượt | Tỷ lệ theo tên | Tỷ lệ tên bịa đã có người đăng ký |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for model, m in res["per_model"].items():
        lines.append(
            f"| {model} | {m['mentions']} | {m['unique_names']} | {m['unique_absent_names']} | {m['absent_share_by_mention']} | {m['absent_share_by_name']} | {m['registered_share_of_hallucinated']} |"
        )
    for model, m in res["per_model"].items():
        lines.append(f"\n### {model}\n")
        lines.append(f"- Nhãn (theo tên): {json.dumps(m['labels_by_name'], ensure_ascii=False)}")
        lines.append(f"- Tên không có trên PyPI, đăng ký mới được hay không: {json.dumps(m['absent_registrability'], ensure_ascii=False)}")
        lines.append(f"- Theo cách trích: {json.dumps(m['per_method'], ensure_ascii=False)}")
        lines.append("- Số tên bịa không trùng theo số câu hỏi: " + ", ".join(f"{c['prompts']}→{c['unique_absent_names']}" for c in m["curve"]))
    if res.get("variants"):
        lines.append("\n## Biến thể khi hỏi lại\n")
        lines.append("```json\n" + json.dumps(res["variants"], ensure_ascii=False, indent=2) + "\n```")
    return "\n".join(lines) + "\n"
