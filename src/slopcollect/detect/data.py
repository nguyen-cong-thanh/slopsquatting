"""Dựng bảng dữ liệu cho bộ phát hiện từ CSDL thu thập.

Mỗi tên một dòng: nhãn, model đã gợi ý, nhóm tên gần giống (để chia tập), phần tách train/test,
và metadata (nếu tên có trên PyPI). Tên thật và tên bịa lấy từ cùng các câu trả lời của LLM.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from slopcollect.stages.label import LABELER_VERSION

MODELS = ("llama31-8b-deepinfra", "deepseek-v41-flash-deepinfra", "glm53-internal")
SHORT = {"llama31-8b-deepinfra": "llama", "deepseek-v41-flash-deepinfra": "deepseek", "glm53-internal": "glm"}
METHODS = ("pip_install", "llm_list")
HALLUCINATED = ("hallucinated_absent", "registered_hallucination")
SELECTION = "variants-v1"

META_COLS = [
    "age_days", "log_downloads", "n_releases", "n_files", "log_stars", "has_github", "github_age_days",
    "source_repo_verified", "n_owners", "has_organization", "log_description_len", "has_project_urls",
    "days_since_last_release",
]


def cluster_key(name: str) -> str:
    """Nhóm tên gần giống: chỉ giữ chữ cái, bỏ tiền tố/hậu tố "python"/"py". Biến thể cùng gốc vào chung một nhóm."""
    k = re.sub(r"[^a-z]", "", name.lower())
    for p in ("python", "py"):
        if k.startswith(p) and len(k) > len(p) + 2:
            k = k[len(p):]
            break
    for s in ("python", "py"):
        if k.endswith(s) and len(k) > len(s) + 2:
            k = k[: -len(s)]
            break
    return k or name


def _bucket(key: str, seed: str) -> float:
    return int(hashlib.sha256(f"{seed}|{key}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def _days(ts: str | None, now: datetime) -> float:
    if not ts:
        return np.nan
    t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (now - t).total_seconds() / 86400


@dataclass
class Dataset:
    names: pd.DataFrame        # tên do LLM gợi ý: real / hallucinated / ..., có cột split
    new_pkgs: pd.DataFrame     # gói mới đăng thật (tập pypi_new), cột half = "profile" | "eval"
    random_pkgs: pd.DataFrame  # gói ngẫu nhiên trên PyPI
    variants: pd.DataFrame     # (selection, prompt, model, sample, variant name) từ các lần hỏi lại
    snapshot_id: str
    now: datetime


def metadata_frame(conn: sqlite3.Connection, names: list[str], now: datetime) -> pd.DataFrame:
    """Đặc trưng metadata dạng số cho các tên có trong package_features."""
    rows = []
    q = (
        "SELECT norm_name, first_release_at, last_release_at, n_releases, n_files, downloads_last_month, github_stars, "
        "github_repo, github_created_at, source_repo_verified, n_owners, has_organization, description_len, has_project_urls "
        "FROM package_features WHERE pypi_name IS NOT NULL AND norm_name IN ({})"
    )
    for i in range(0, len(names), 900):
        chunk = names[i : i + 900]
        rows += conn.execute(q.format(",".join("?" * len(chunk))), chunk).fetchall()
    out = []
    for r in rows:
        out.append({
            "norm_name": r[0],
            "age_days": _days(r[1], now),
            "days_since_last_release": _days(r[2], now),
            "n_releases": r[3] or 0,
            "n_files": r[4] or 0,
            "log_downloads": np.log1p(r[5] or 0),
            "log_stars": np.log1p(r[6] or 0),
            "has_github": int(bool(r[7])),
            "github_age_days": _days(r[8], now) if r[8] else -1.0,
            "source_repo_verified": int(r[9] or 0),
            "n_owners": r[10] if r[10] is not None else -1,
            "has_organization": int(r[11] or 0),
            "log_description_len": np.log1p(r[12] or 0),
            "has_project_urls": int(r[13] or 0),
        })
    df = pd.DataFrame(out, columns=["norm_name", *META_COLS])
    return df.dropna(subset=["age_days"]).set_index("norm_name")


def load(db: str, *, seed: str = "split-v1", test_share: float = 0.25) -> Dataset:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=120)
    sid = conn.execute("SELECT snapshot_id FROM pypi_snapshots ORDER BY fetched_at DESC LIMIT 1").fetchone()[0]
    now = datetime.strptime(sid.split("-")[1], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
    ph_m, ph_t = ",".join("?" * len(MODELS)), ",".join("?" * len(METHODS))

    # Tên do LLM gợi ý (chỉ hai cách trích của Spracklen), model nào gợi ý, ở bao nhiêu câu hỏi.
    ment = pd.read_sql_query(
        f"SELECT v.norm_name, v.model_key, COUNT(DISTINCT v.prompt_id) AS n_prompts FROM v_mentions v "
        f"WHERE v.model_key IN ({ph_m}) AND v.method IN ({ph_t}) GROUP BY 1, 2",
        conn, params=[*MODELS, *METHODS],
    )
    labels = pd.read_sql_query("SELECT norm_name, label FROM labels WHERE labeler_version = ?", conn, params=[LABELER_VERSION])
    status = pd.read_sql_query(
        "SELECT norm_name, exists_on_pypi, registrable, reason FROM package_status WHERE snapshot_id = ?", conn, params=[sid]
    )
    by_name = ment.pivot_table(index="norm_name", columns="model_key", values="n_prompts", fill_value=0)
    by_name.columns = [f"n_{SHORT[c]}" for c in by_name.columns]
    names = by_name.join(labels.set_index("norm_name")).join(status.set_index("norm_name"))
    names = names[names["label"].isin(["real", *HALLUCINATED, "placeholder"])].copy()
    names["y"] = names["label"].isin(HALLUCINATED).astype(int)
    for m in MODELS:  # model chưa có dữ liệu vẫn có cột
        names[f"n_{SHORT[m]}"] = names.get(f"n_{SHORT[m]}", 0)
    names["n_models"] = sum((names[f"n_{SHORT[m]}"] > 0).astype(int) for m in MODELS)
    names["cluster"] = [cluster_key(n) for n in names.index]

    # Các lần hỏi lại: mọi tên bịa xuất hiện, theo lần hỏi gốc (sample) của câu hỏi đã chọn.
    variants = pd.read_sql_query(
        f"SELECT s.norm_name AS original, s.model_key, s.prompt_id, v.root_sample_idx AS sample, v.norm_name AS variant "
        f"FROM selections s JOIN v_mentions v ON v.prompt_id = s.prompt_id AND v.model_key = s.model_key "
        f"WHERE s.selection_id = ? AND v.method IN ({ph_t})",
        conn, params=[SELECTION, *METHODS],
    )
    lab = labels.set_index("norm_name")["label"]
    variants = variants[variants["variant"].map(lab).isin(HALLUCINATED)].drop_duplicates()

    # Chia tập theo nhóm tên gần giống. Mọi tên bịa xuất hiện trong các lần hỏi lại (kho biến thể của kẻ
    # tấn công) ép vào tập test, để tấn công chỉ đánh giá trên tên mô hình chưa thấy khi huấn luyện.
    attack_clusters = {cluster_key(n) for n in set(variants["variant"]) | set(variants["original"])}
    names["split"] = [
        "test" if (c in attack_clusters or _bucket(c, seed) < test_share) else "train" for c in names["cluster"]
    ]

    meta = metadata_frame(conn, list(names.index), now)
    names = names.join(meta)

    def sample_frame(sample_id: str) -> pd.DataFrame:
        ids = [r[0] for r in conn.execute("SELECT norm_name FROM name_samples WHERE sample_id = ?", (sample_id,))]
        df = metadata_frame(conn, ids, now)
        df["cluster"] = [cluster_key(n) for n in df.index]
        return df

    new_pkgs = sample_frame("pypi_new")
    new_pkgs["half"] = ["profile" if _bucket(n, seed + "-new") < 0.5 else "eval" for n in new_pkgs.index]
    random_pkgs = sample_frame("pypi_random")
    # Bỏ khỏi tập đo báo nhầm những gói trùng tên LLM đã gợi ý (đã có trong names).
    random_pkgs = random_pkgs[~random_pkgs.index.isin(names.index)]
    new_pkgs = new_pkgs[~new_pkgs.index.isin(names.index)]
    conn.close()
    return Dataset(names=names, new_pkgs=new_pkgs, random_pkgs=random_pkgs, variants=variants, snapshot_id=sid, now=now)


def describe(ds: Dataset) -> dict:
    n = ds.names
    return {
        "snapshot_id": ds.snapshot_id,
        "names": {
            split: {lab: int(c) for lab, c in g["label"].value_counts().items()} for split, g in n.groupby("split")
        },
        "real_with_metadata": int(n[(n.label == "real") & n.age_days.notna()].shape[0]),
        "new_pkgs": {h: int(c) for h, c in ds.new_pkgs["half"].value_counts().items()},
        "random_pkgs": int(len(ds.random_pkgs)),
        "variant_rows": int(len(ds.variants)),
        "selections": int(ds.variants[["original", "model_key", "prompt_id"]].drop_duplicates().shape[0]),
    }


if __name__ == "__main__":
    import sys

    print(json.dumps(describe(load(sys.argv[1] if len(sys.argv) > 1 else "data/slop.sqlite")), indent=2, ensure_ascii=False))
