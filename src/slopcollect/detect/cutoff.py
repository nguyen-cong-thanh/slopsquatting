"""Gói có trên PyPI mà LLM gợi ý dù gói ra đời sau mốc dữ liệu (knowledge cutoff) của chính model đó.

Model không thể biết một gói ra đời sau mốc của nó. Nếu vẫn gợi ý đúng tên, thì tên đó do model bịa ra và
về sau mới có người đăng ký (tình cờ trùng, đăng ký giữ chỗ, hoặc slopsquatting). Ngày ra đời là lần tải
file lên sớm nhất, kể cả bản đã xóa (first_release_at sau khi có nguồn clickpy_history).

Mốc dữ liệu (CUTOFFS): chính thức nếu hãng công bố; nếu không, theo thông tin cộng đồng (chưa kiểm chứng),
và khi các nguồn lệch nhau thì lấy mốc muộn hơn (ít gắn cờ hơn).

  .venv/bin/python -m slopcollect.detect.cutoff --db data/slop.sqlite --out data/exports/cutoff
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import pandas as pd

from slopcollect.stages.label import LABELER_VERSION

METHODS = ("pip_install", "llm_list")
MARGIN_DAYS = 30  # gói phát hành ngay sau mốc vẫn có thể đã có trên GitHub trước đó

# model -> (mốc, loại nguồn, ghi chú nguồn). Kiểm tra ngày 14/11/2026.
CUTOFFS: dict[str, tuple[str, str, str]] = {
    "llama31-8b-deepinfra": ("2023-12-31", "chính thức", "Meta model card Llama 3.1: pretraining data cutoff December 2023"),
    "llama33-70b-deepinfra": ("2023-12-31", "chính thức", "Meta model card Llama 3.3: pretraining data cutoff December 2023"),
    "llama4-scout-deepinfra": ("2024-08-31", "chính thức", "Meta, trang model Llama 4: knowledge cutoff August 2024"),
    "deepseek-v3-deepinfra": ("2024-07-31", "cộng đồng", "DataLearner: mốc chính thức cuối cùng của DeepSeek là 07/2024 (V3-0324)"),
    "deepseek-v31-deepinfra": ("2025-07-31", "cộng đồng", "OpenRouter 03/2025, Digit 07/2025; lấy 07/2025"),
    "deepseek-v41-flash-deepinfra": ("2026-03-31", "cộng đồng", "\"đầu 2026\" (gradually.ai, model tự khai bằng tiếng Anh); lấy hết 03/2026"),
    "glm53-internal": ("2025-12-31", "cộng đồng", "innfactory: cuối 2025 (Roboflow 03/2026 là cho bản Flash)"),
    "glm53-deepinfra": ("2025-12-31", "cộng đồng", "như glm53-internal"),
}


def analyse(db: str) -> dict:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=120)
    models = list(CUTOFFS)
    d = pd.read_sql_query(
        f"SELECT v.model_key AS m, v.norm_name AS n, COUNT(DISTINCT v.prompt_id) AS prompts, l.label, "
        f"pf.first_release_at AS first, pf.downloads_last_month AS dl, pf.n_releases, pf.summary "
        f"FROM v_mentions v JOIN labels l ON l.norm_name = v.norm_name AND l.labeler_version = ? "
        f"JOIN package_features pf ON pf.norm_name = v.norm_name AND pf.pypi_name IS NOT NULL "
        f"WHERE v.method IN ({','.join('?' * len(METHODS))}) AND v.model_key IN ({','.join('?' * len(models))}) "
        f"GROUP BY 1, 2",
        conn, params=[LABELER_VERSION, *METHODS, *models],
    )
    conn.close()
    d["first"] = pd.to_datetime(d["first"], utc=True, errors="coerce")
    out: dict = {"labeler_version": LABELER_VERSION, "margin_days": MARGIN_DAYS, "models": {}}
    for m, g in d.groupby("m"):
        cut, kind, note = CUTOFFS[m]
        after = g[g["first"] > pd.Timestamp(cut, tz="UTC") + pd.Timedelta(days=MARGIN_DAYS)]
        out["models"][m] = {
            "cutoff": cut, "cutoff_source": kind, "cutoff_note": note,
            "existing_names": int(len(g)),
            "after_cutoff": int(len(after)),
            "after_cutoff_share": round(len(after) / len(g), 4) if len(g) else None,
            "after_by_label": {k: int(v) for k, v in after["label"].value_counts().items()},
            "after_with_1000_downloads": int((after["dl"].fillna(0) > 1000).sum()),
            "after_in_3plus_prompts": int((after["prompts"] >= 3).sum()),
            "top": [
                {"name": r.n, "prompts": int(r.prompts), "first": r.first.strftime("%Y-%m-%d"), "downloads_30d": None if pd.isna(r.dl) else int(r.dl),
                 "label": r.label, "summary": (r.summary or "")[:80]}
                for r in after.sort_values(["prompts", "dl"], ascending=False).head(15).itertuples()
            ],
        }
    return out


def to_md(res: dict) -> str:
    L = ["# Gói LLM gợi ý nhưng ra đời sau mốc dữ liệu của model\n",
         f"Ngày ra đời = lần tải file lên sớm nhất (kể cả bản đã xóa). Tính là sau mốc nếu muộn hơn mốc {res['margin_days']} ngày. "
         f"Nhãn `{res['labeler_version']}`.\n",
         "| Model | Mốc | Nguồn mốc | Tên có trên PyPI | Ra đời sau mốc | Tỷ lệ | > 1000 lượt tải/tháng | Ở ≥ 3 câu hỏi | Theo nhãn |",
         "|---|---|---|---|---|---|---|---|---|"]
    for m, x in res["models"].items():
        L.append(f"| {m} | {x['cutoff']} | {x['cutoff_source']} | {x['existing_names']} | {x['after_cutoff']} | {x['after_cutoff_share']} | "
                 f"{x['after_with_1000_downloads']} | {x['after_in_3plus_prompts']} | {x['after_by_label']} |")
    L.append("\nNguồn mốc: " + "; ".join(f"{m}: {x['cutoff_note']}" for m, x in res["models"].items()) + "\n")
    for m, x in res["models"].items():
        L.append(f"\n## {m}: gợi ý ở nhiều câu hỏi nhất\n")
        L.append("| Tên | Số câu hỏi | Ra đời | Lượt tải 30 ngày | Nhãn | Tóm tắt |")
        L.append("|---|---|---|---|---|---|")
        for t in x["top"]:
            L.append(f"| {t['name']} | {t['prompts']} | {t['first']} | {t['downloads_30d']} | {t['label']} | {t['summary']} |")
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/slop.sqlite")
    ap.add_argument("--out", default="data/exports/cutoff")
    a = ap.parse_args()
    res = analyse(a.db)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "results.md").write_text(to_md(res), encoding="utf-8")
    print(to_md(res))


if __name__ == "__main__":
    main()
