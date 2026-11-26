"""Độ bền của tên bịa giữa các phiên bản model cùng họ (flows/persistence-api.toml).

Với mỗi cặp (tên bịa, câu hỏi) đã chọn ở variants-v1 cho model gốc, và mỗi phiên bản khác cùng họ
(đã được hỏi đúng câu đó 10 lần):
  - repeat:    tỷ lệ trong 10 lần hỏi có gợi ý đúng tên đó (lần hỏi tính gộp cả ba tác vụ)
  - any:       tỷ lệ cặp mà phiên bản đó gợi ý tên ít nhất một lần trong 10 lần
  - base_repeat / base_any: như trên nhưng của chính model gốc (mốc so sánh)
Theo chiều ngược lại: tên bịa mà phiên bản khác gợi ý trên các câu hỏi đó có bao nhiêu phần cũng là tên
model gốc đã bịa ở bất kỳ câu hỏi nào trong dữ liệu gốc (18.033 câu, lần hỏi 0).

  .venv/bin/python -m slopcollect.detect.persistence --db data/slop.sqlite --out data/exports/persistence
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import pandas as pd

from slopcollect.stages.label import LABELER_VERSION

SELECTION = "variants-v1"
METHODS = ("pip_install", "llm_list")
HALLUCINATED = ("hallucinated_absent", "registered_hallucination")
N_SAMPLES = 10

# Năm model chính (kế hoạch 25/11/2026; MiMo-V2.6-Pro thay GLM 5.3 ngày 26/11/2026), dùng để đếm số model cùng
# bịa ra một tên. Llama 3.1 8B và GLM 5.3 chỉ còn là đối chứng.
MAIN_MODELS = (
    "mistral-small-32-24b-deepinfra",
    "qwen36-35b-a3b-deepinfra",
    "nemotron35-super-deepinfra",
    "deepseek-v41-flash-deepinfra",
    "mimo-v26-pro-deepinfra",
)

# Họ model: bản gốc -> các phiên bản khác cùng cỡ (cũ hơn), kèm thời điểm phát hành khi biết chắc.
# reask: model chứa các lần hỏi lại của chính bản gốc (GLM 5.3 gốc chạy trên máy nội bộ, hỏi lại qua DeepInfra).
FAMILIES = {
    "mistral-small-32-24b-deepinfra": {
        "label": "Mistral Small 3.2 24B (06/2025)",
        "versions": {"mistral-small-24b-2501-deepinfra": "Mistral Small 3 24B 2501 (01/2025)"},
    },
    "qwen36-35b-a3b-deepinfra": {
        "label": "Qwen3.6 35B-A3B",
        "versions": {
            "qwen35-35b-a3b-deepinfra": "Qwen3.5 35B-A3B (02/2026)",
            "qwen3-30b-a3b-deepinfra": "Qwen3 30B-A3B (04/2025)",
        },
    },
    "nemotron35-super-deepinfra": {
        "label": "Nemotron 3.5 Super 120B-A12B",
        "versions": {"nemotron3-super-deepinfra": "Nemotron 3 Super 120B-A12B"},
    },
    "deepseek-v41-flash-deepinfra": {
        "label": "DeepSeek V4.1 Flash 1017 (10/2026)",
        "versions": {
            "deepseek-v4-flash-deepinfra": "DeepSeek V4 Flash (04/2026)",
            "deepseek-v4-flash-0731-deepinfra": "DeepSeek V4 Flash 0731 (07/2026)",
            "deepseek-v3-deepinfra": "DeepSeek V3 (12/2024, khác cỡ)",
            "deepseek-v31-deepinfra": "DeepSeek V3.1 (08/2025, khác cỡ)",
            "deepseek-v32-deepinfra": "DeepSeek V3.2 (12/2025, khác cỡ)",
        },
    },
    "mimo-v26-pro-deepinfra": {
        "label": "MiMo-V2.6-Pro 1T-A42B (09/2026)",
        "versions": {"mimo-v25-pro-deepinfra": "MiMo-V2.5-Pro 1T-A42B (04/2026)"},
    },
    # Đối chứng (bỏ khỏi nhóm chính 26/11/2026 vì chi phí).
    "glm53-internal": {
        "label": "GLM 5.3 (đối chứng)",
        "reask": "glm53-deepinfra",
        "versions": {"glm52-deepinfra": "GLM 5.2 (06/2026)"},
    },
    # Đối chứng (không còn là model chính): không có bản cũ cùng cỡ.
    "llama31-8b-deepinfra": {
        "label": "Llama 3.1 8B (07/2024, đối chứng)",
        "versions": {
            "llama33-70b-deepinfra": "Llama 3.3 70B (12/2024, khác cỡ)",
            "llama4-scout-deepinfra": "Llama 4 Scout (04/2025, khác cỡ)",
        },
    },
}


def _r(x: float) -> float:
    return round(float(x), 4)


def analyse(db: str) -> dict:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=120)
    ph = ",".join("?" * len(METHODS))
    labels = pd.read_sql_query("SELECT norm_name, label FROM labels WHERE labeler_version = ?", conn, params=[LABELER_VERSION])
    hall = set(labels.loc[labels.label.isin(HALLUCINATED), "norm_name"])
    sel = pd.read_sql_query(
        "SELECT norm_name AS name, prompt_id, model_key AS base FROM selections WHERE selection_id = ?", conn, params=[SELECTION]
    )
    out: dict = {"selection": SELECTION, "labeler_version": LABELER_VERSION, "families": {}}
    # Số model chính (năm model, lần hỏi 0) cùng bịa ra mỗi tên.
    n_models = pd.read_sql_query(
        f"SELECT norm_name AS name, COUNT(DISTINCT model_key) AS k FROM v_mentions WHERE method IN ({ph}) AND root_sample_idx = 0 "
        f"AND model_key IN ({','.join('?' * len(MAIN_MODELS))}) GROUP BY 1",
        conn, params=[*METHODS, *MAIN_MODELS],
    ).set_index("name")["k"]
    out["main_models"] = list(MAIN_MODELS)
    for base, fam in FAMILIES.items():
        s = sel[sel.base == base][["name", "prompt_id"]].drop_duplicates()
        prompts = list(s.prompt_id.unique())
        base_rs = fam.get("reask", base)
        models = [base_rs, *fam["versions"]]
        q = (
            f"SELECT model_key, prompt_id, root_sample_idx AS sample, norm_name AS name FROM v_mentions "
            f"WHERE method IN ({ph}) AND model_key IN ({','.join('?' * len(models))}) "
            f"AND prompt_id IN ({','.join('?' * len(prompts))}) AND root_sample_idx < ?"
        )
        m = pd.read_sql_query(q, conn, params=[*METHODS, *models, *prompts, N_SAMPLES]).drop_duplicates()
        # Số lần hỏi thực có cho mỗi (model, câu hỏi): câu trả lời code (lần hỏi gốc) không lỗi.
        gen = pd.read_sql_query(
            f"SELECT model_key, prompt_id, COUNT(DISTINCT sample_idx) AS n FROM generations "
            f"WHERE task_id = 'spracklen_code_v1' AND error IS NULL AND sample_idx < ? "
            f"AND model_key IN ({','.join('?' * len(models))}) AND prompt_id IN ({','.join('?' * len(prompts))}) GROUP BY 1, 2",
            conn, params=[N_SAMPLES, *models, *prompts],
        ).set_index(["model_key", "prompt_id"])["n"]
        base_all = {
            r[0] for r in conn.execute(
                f"SELECT DISTINCT norm_name FROM v_mentions WHERE model_key = ? AND method IN ({ph}) AND root_sample_idx = 0", (base, *METHODS)
            )
        } & hall

        def per_pair(model: str, skip_first: bool = False) -> pd.DataFrame:
            # Bản gốc: bỏ lần hỏi 0, vì tên được chọn từ chính lần đó (luôn trúng).
            mm = m[(m.model_key == model) & (m["sample"] >= (1 if skip_first else 0))]
            hits = mm.merge(s, on=["prompt_id", "name"])
            k = hits.groupby(["name", "prompt_id"])["sample"].nunique().rename("k")
            d = s.set_index(["name", "prompt_id"]).join(k).fillna({"k": 0})
            d["n"] = [gen.get((model, p), 0) - (1 if skip_first else 0) for p in d.index.get_level_values("prompt_id")]
            d = d[d.n > 0].copy()
            d["n_models"] = [n_models.get(x, 0) for x in d.index.get_level_values("name")]
            return d

        def summary(d: pd.DataFrame) -> dict:
            r = {"pairs": int(len(d)), "repeat": _r((d.k / d.n).mean()), "any": _r((d.k > 0).mean())}
            r["any_by_n_models"] = {int(i): {"pairs": int(len(g)), "any": _r((g.k > 0).mean())} for i, g in d.groupby("n_models")}
            return r

        b = per_pair(base_rs, skip_first=True)
        res = {"label": fam["label"], "pairs": int(len(s)), "prompts": len(prompts), "base": summary(b), "versions": {}}
        for v, vlabel in fam["versions"].items():
            d = per_pair(v)
            if not len(d):
                res["versions"][v] = {"label": vlabel, "pairs": 0}
                continue
            mv = m[m.model_key == v]
            v_hall = set(mv.name) & hall
            tasks = {r[0] for r in conn.execute("SELECT DISTINCT task_id FROM generations WHERE model_key = ? AND error IS NULL", (v,))}
            res["versions"][v] = {
                "label": vlabel,
                **summary(d),
                "complete": len(tasks) == 3 and int(len(d)) == int(len(s)) and bool((d.n == N_SAMPLES).all()),
                # Tên bịa phiên bản này gợi ý trên các câu hỏi đó: bao nhiêu cũng là tên bản gốc đã bịa (bất kỳ câu nào).
                "own_hallucinated_names": len(v_hall),
                "own_also_by_base": _r(len(v_hall & base_all) / len(v_hall)) if v_hall else None,
                "hallucination_share_of_mentions": _r(mv.name.isin(hall).mean()),
            }
        out["families"][base] = res
    conn.close()
    return out


def to_md(res: dict) -> str:
    L = ["# Độ bền của tên bịa giữa các phiên bản model\n",
         f"Các cặp (tên bịa, câu hỏi) chọn ở `{res['selection']}`; nhãn `{res['labeler_version']}`; mỗi câu hỏi 10 lần, gộp ba tác vụ.\n",
         "- Lặp lại: tỷ lệ lần hỏi có gợi ý đúng tên bịa đó, trung bình trên các cặp.",
         "- Ít nhất một lần: tỷ lệ cặp mà model gợi ý tên đó ít nhất một lần trong 10 lần.",
         "- Tên bịa của bản này cũng do bản gốc bịa: trên các câu hỏi này, tên bịa phiên bản đó gợi ý có trong tập tên bản gốc đã bịa (18.033 câu, lần hỏi 0).\n"]
    for fam in res["families"].values():
        L.append(f"## {fam['label']}\n\n{fam['pairs']} cặp, {fam['prompts']} câu hỏi.\n")
        L.append("| Model | Lặp lại | Ít nhất một lần | Tỷ lệ lượt gợi ý là tên bịa | Tên bịa của bản này cũng do bản gốc bịa |")
        L.append("|---|---|---|---|---|")
        L.append(f"| {fam['label']} (bản gốc, lần hỏi 1–9) | {fam['base']['repeat']} | {fam['base']['any']} | | |")
        for v in fam["versions"].values():
            if not v.get("pairs"):
                L.append(f"| {v['label']} | chưa có dữ liệu | | | |")
                continue
            note = "" if v.get("complete") else " (chưa đủ dữ liệu)"
            L.append(f"| {v['label']}{note} | {v['repeat']} | {v['any']} | {v['hallucination_share_of_mentions']} | "
                     f"{v['own_also_by_base']} ({v['own_hallucinated_names']} tên) |")
        L.append("\nÍt nhất một lần, theo số model chính (Mistral 3.2, Qwen3.6, Nemotron 3.5, DeepSeek V4.1, MiMo-V2.6-Pro) cùng bịa ra tên:\n")
        rows = [("bản gốc", fam["base"])] + [(v["label"], v) for v in fam["versions"].values() if v.get("pairs")]
        for lab, x in rows:
            L.append(f"- {lab}: " + ", ".join(f"{i} model: {g['any']} ({g['pairs']} cặp)" for i, g in x["any_by_n_models"].items()))
        L.append("")
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/slop.sqlite")
    ap.add_argument("--out", default="data/exports/persistence")
    a = ap.parse_args()
    res = analyse(a.db)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "results.md").write_text(to_md(res), encoding="utf-8")
    print(to_md(res))


if __name__ == "__main__":
    main()
