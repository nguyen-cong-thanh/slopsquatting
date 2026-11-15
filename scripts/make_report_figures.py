"""Vẽ các hình đen trắng cho báo cáo tiến độ (docs/bao-cao/bao-cao-tien-do-15-11.md) vào docs/images/.

Đọc số liệu thật: CSDL data/slop.sqlite (chỉ đọc), data/exports/detector/results.json và
data/exports/persistence/results.json. Chạy lại khi dữ liệu hoặc kết quả thay đổi:

  uv sync --group notebook
  uv run python scripts/make_report_figures.py
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "images"
DB = ROOT / "data" / "slop.sqlite"
LABELS_VERSION = "rules-v3"
HALLUCINATED = ("hallucinated_absent", "registered_hallucination")
MODELS = {"llama31-8b-deepinfra": "Llama 3.1 8B", "deepseek-v41-flash-deepinfra": "DeepSeek V4.1 Flash", "glm53-internal": "GLM 5.3"}
# Đen trắng: mỗi model một kiểu tô / kiểu nét cố định.
BAR = {
    "Llama 3.1 8B": dict(color="black", edgecolor="black"),
    "DeepSeek V4.1 Flash": dict(color="white", edgecolor="black", hatch="////"),
    "GLM 5.3": dict(color="#bdbdbd", edgecolor="black"),
}
LINE = {"Llama 3.1 8B": dict(color="black", ls="-"), "DeepSeek V4.1 Flash": dict(color="black", ls="--"), "GLM 5.3": dict(color="black", ls=":")}

plt.rcParams.update({
    "font.family": "DejaVu Serif", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#dddddd", "grid.linewidth": 0.6, "axes.axisbelow": True,
    "savefig.dpi": 200, "savefig.bbox": "tight", "hatch.linewidth": 0.8,
})


def pct(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def mentions(conn: sqlite3.Connection) -> pd.DataFrame:
    m = pd.read_sql_query(
        "SELECT v.model_key, v.prompt_id, v.norm_name, l.label FROM v_mentions v "
        "JOIN labels l ON l.norm_name = v.norm_name AND l.labeler_version = ? "
        "WHERE v.root_sample_idx = 0 AND v.method IN ('pip_install', 'llm_list') AND v.model_key IN (?, ?, ?)",
        conn, params=[LABELS_VERSION, *MODELS],
    )
    m = m[m["label"] != "stdlib"].copy()
    m["model"] = m["model_key"].map(MODELS)
    m["h"] = m["label"].isin(HALLUCINATED)
    return m


def fig_rates(m: pd.DataFrame) -> None:
    """Hình 1: tỷ lệ lượt gợi ý là tên bịa, tỷ lệ câu hỏi có tên bịa."""
    names = list(MODELS.values())
    a = [m[m.model == n]["h"].mean() * 100 for n in names]
    b = [m[m.model == n].groupby("prompt_id")["h"].any().mean() * 100 for n in names]
    fig, axes = plt.subplots(1, 2, figsize=(8, 3))
    for ax, vals, title in [(axes[0], a, "Lượt gợi ý là tên bịa"), (axes[1], b, "Câu hỏi có ít nhất một tên bịa")]:
        for i, (n, v) in enumerate(zip(names, vals)):
            ax.bar(i, v, width=0.6, **BAR[n])
            ax.text(i, v + max(vals) * 0.02, f"{pct(v)}%", ha="center", va="bottom", fontsize=9)
        ax.set_xticks(range(3), [n.replace(" Flash", "\nFlash") for n in names], fontsize=9)
        ax.set_ylabel("%")
        ax.set_title(title, fontsize=10)
        ax.set_ylim(0, max(vals) * 1.15)
    fig.tight_layout()
    fig.savefig(OUT / "bc-hinh-1-ty-le-ten-bia.png")
    plt.close(fig)


def fig_growth(m: pd.DataFrame) -> None:
    """Hình 2: số tên bịa không trùng tích lũy theo số câu hỏi (thứ tự câu hỏi ngẫu nhiên cố định)."""
    rng = np.random.default_rng(0)
    prompts = m["prompt_id"].unique()
    order = pd.Series(np.arange(len(prompts)), index=rng.permutation(prompts))
    fig, ax = plt.subplots(figsize=(7, 3.2))
    for n in MODELS.values():
        g = m[(m.model == n) & m.h]
        first = g.assign(pos=g["prompt_id"].map(order)).groupby("norm_name")["pos"].min().sort_values()
        ax.plot(first.values, np.arange(1, len(first) + 1), lw=1.8, label=n, **LINE[n])
        ax.annotate(f"{len(first):,}".replace(",", "."), (first.values[-1], len(first)), xytext=(4, 0),
                    textcoords="offset points", va="center", fontsize=9)
    ax.set_xlabel("Số câu hỏi đã hỏi")
    ax.set_ylabel("Số tên bịa không trùng")
    ax.legend(frameon=False)
    ax.set_xlim(0, len(prompts) * 1.1)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"{x:,.0f}".replace(",", ".")))
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"{x:,.0f}".replace(",", ".")))
    fig.savefig(OUT / "bc-hinh-2-tang-truong-ten-bia.png")
    plt.close(fig)


def fig_wait(det: dict) -> None:
    """Hình 3: tỷ lệ né theo thời gian chờ, tầng 2 tên và metadata (GB), 0 USD; mức trần nét chấm."""
    curves = det["attack"]["tier2"]["tên + metadata (GB)"]
    waits = [0, 30, 90, 365]
    fig, ax = plt.subplots(figsize=(7, 3.2))
    for mk, n in MODELS.items():
        ys = [curves[f"wait{w}_usd0"][mk]["evasion"] * 100 for w in waits]
        ceil = curves["wait0_usd0"][mk]["opportunity"] * 100
        ax.plot(range(4), ys, marker="o", ms=6, mfc="white", lw=1.8, label=n, **LINE[n])
        ax.axhline(ceil, color="#888888", lw=0.8, ls=(0, (1, 2)))
        ax.text(3.08, ceil, f"trần {pct(ceil)}%", fontsize=8, va="center", color="#555555")
    ax.set_xticks(range(4), [f"{w} ngày" for w in waits])
    ax.set_xlabel("Thời gian chờ sau khi đăng ký")
    ax.set_ylabel("Tỷ lệ né (%)")
    ax.set_ylim(0, 100)
    ax.set_xlim(-0.2, 3.6)
    ax.legend(frameon=False, loc="upper left")
    fig.savefig(OUT / "bc-hinh-3-tan-cong-cho.png")
    plt.close(fig)


def fig_persistence(pers: dict) -> None:
    """Hình 4: tỷ lệ cặp được gợi ý lại ở các phiên bản DeepSeek, theo số model chính cùng bịa ra tên."""
    fam = pers["families"]["deepseek-v41-flash-deepinfra"]
    rows = [("V4.1 Flash\n(gốc, 10/2026)", fam["base"])] + [
        (v["label"].replace("DeepSeek ", "").replace(" (", "\n("), v) for v in fam["versions"].values()
    ]
    groups = {1: dict(color="white", edgecolor="black", hatch="////"), 2: dict(color="#bdbdbd", edgecolor="black"), 3: dict(color="black", edgecolor="black")}
    fig, ax = plt.subplots(figsize=(8, 3.4))
    w = 0.26
    for j, (k, style) in enumerate(groups.items()):
        ys = [x["any_by_n_models"][str(k)]["any"] * 100 for _, x in rows]
        ax.bar(np.arange(len(rows)) + (j - 1) * w, ys, width=w, label=f"tên do {k} model bịa", **style)
    ax.set_xticks(range(len(rows)), [r[0] for r in rows], fontsize=8)
    ax.set_ylabel("% cặp được gợi ý lại")
    ax.set_ylim(0, 100)
    ax.legend(frameon=False, ncol=3, loc="upper right", fontsize=8)
    fig.savefig(OUT / "bc-hinh-4-do-ben-deepseek.png")
    plt.close(fig)


def fig_detectors(det: dict) -> None:
    """Hình 5: tỷ lệ né với kẻ tấn công bắt chước gói thật, chờ 365 ngày, 10 USD, theo bộ phát hiện."""
    key = "bắt chước gói thật, đăng ký mới, chờ 365 ngày, 10 USD"
    rows = [
        ("Tên và metadata", det["tier2_cutoff"], "tên + metadata (GB)"),
        ("Thêm đặc trưng mốc", det["tier2_cutoff"], "tên + metadata + mốc (GB)"),
        ("Bỏ tuổi gói, thêm mốc", det["tier2_cutoff"], "tên + metadata trừ tuổi + mốc (GB)"),
        ("Tên và metadata,\ncó mẫu tấn công", det["tier2_cutoff_adv"], "tên + metadata (GB)"),
        ("Thêm đặc trưng mốc,\ncó mẫu tấn công", det["tier2_cutoff_adv"], "tên + metadata + mốc (GB)"),
        ("Bỏ tuổi gói, thêm mốc,\ncó mẫu tấn công", det["tier2_cutoff_adv"], "tên + metadata trừ tuổi + mốc (GB)"),
        ("Luật mốc", det["tier2_cutoff"], "luật: sau mốc của model gợi ý thì cảnh báo"),
    ]
    fig, ax = plt.subplots(figsize=(8, 4.6))
    h = 0.26
    y = np.arange(len(rows))[::-1]
    for j, (mk, n) in enumerate(MODELS.items()):
        xs = [src["attack"]["by_model"][name][key][mk]["evasion"] * 100 for _, src, name in rows]
        ax.barh(y + (1 - j) * h, xs, height=h, label=n, **BAR[n])
    ax.set_yticks(y, [r[0] for r in rows], fontsize=8.5)
    ax.set_xlabel("Tỷ lệ né (%)")
    ax.set_xlim(0, 100)
    ax.legend(frameon=False, ncol=3, loc="lower center", bbox_to_anchor=(0.45, -0.28), fontsize=8.5)
    ax.grid(axis="y", visible=False)
    fig.savefig(OUT / "bc-hinh-5-bo-phat-hien-bat-chuoc.png")
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=120)
    m = mentions(conn)
    conn.close()
    det = json.loads((ROOT / "data/exports/detector/results.json").read_text(encoding="utf-8"))
    pers = json.loads((ROOT / "data/exports/persistence/results.json").read_text(encoding="utf-8"))
    fig_rates(m)
    fig_growth(m)
    fig_wait(det)
    fig_persistence(pers)
    fig_detectors(det)
    print("Đã ghi", sorted(p.name for p in OUT.glob("bc-hinh-*.png")))


if __name__ == "__main__":
    main()
