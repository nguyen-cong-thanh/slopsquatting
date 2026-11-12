"""Tấn công sát thực tế (mô phỏng): kẻ tấn công đăng ký các biến thể tên bịa mà LLM thật sự gợi ý khi hỏi lại,
rồi làm giả metadata trong phạm vi ngân sách để bộ phát hiện không cảnh báo.

Né thành công ở một lần hỏi (sample) của một câu hỏi khi có ít nhất một tên bịa LLM gợi ý ở lần đó mà:
  1. đăng ký được trên PyPI (luật của warehouse: không trùng, không quá giống tên đã có);
  2. sau khi làm giả metadata, bộ phát hiện không cảnh báo (điểm <= ngưỡng ở mức báo nhầm 1%).
Tỷ lệ né của một câu hỏi = số lần hỏi né thành công / số lần hỏi (10). Báo theo ngân sách và thời gian chờ.

Mọi thứ chỉ là thay giá trị trong bảng dữ liệu: không đăng ký gói, không mua sao hay lượt tải.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from slopcollect.detect.data import META_COLS


@dataclass
class Costs:
    """Chi phí làm giả (USD). Giá trị tạm, cần đối chiếu nguồn trước khi đưa vào báo cáo."""

    usd_per_star: float = 0.10           # sao GitHub mua (giá chợ đen, cần kiểm chứng)
    usd_per_download: float = 0.00002    # tự tải gói bằng máy chủ/CI: gần như miễn phí (1 USD cho 50.000 lượt)
    budgets: list[float] = field(default_factory=lambda: [0, 1, 10, 100, 1000])
    waits_days: list[int] = field(default_factory=lambda: [0, 30, 90, 365])


# Việc làm giả không tốn tiền: link kho GitHub (tự tạo), xác minh nguồn qua Trusted Publishing (tự cấu hình
# trên kho của mình), thêm bản phát hành, mô tả, người duy trì, tổ chức. Kẻ tấn công thử các tổ hợp này.
FREE_CHOICES = {
    "n_releases": [1, 5, 13, 30],
    "n_owners": [1, 2],
    "has_organization": [0, 1],
    "fresh_release": [0, 1],  # 1: vừa phát hành bản mới (days_since_last_release = 0)
}


def _apply_free(base: pd.DataFrame, wait: int, desc_len_log: float, choice: dict[str, int]) -> pd.DataFrame:
    X = base.copy()
    X["age_days"] = X["age_days"] + wait
    X["has_github"] = 1
    X["github_age_days"] = np.maximum(X["github_age_days"].where(X["github_age_days"] >= 0, 0), X["age_days"])
    X["source_repo_verified"] = 1
    X["has_project_urls"] = 1
    X["log_description_len"] = np.maximum(X["log_description_len"], desc_len_log)
    X["n_releases"] = np.maximum(X["n_releases"], choice["n_releases"])
    X["n_files"] = np.maximum(X["n_files"], X["n_releases"] * 2)
    X["n_owners"] = choice["n_owners"]
    X["has_organization"] = choice["has_organization"]
    X["days_since_last_release"] = 0.0 if choice["fresh_release"] else X["age_days"]
    return X


def fake_metadata(model, base: pd.DataFrame, name_feats: pd.DataFrame, costs: Costs, desc_len_log: float) -> dict:
    """Điểm thấp nhất kẻ tấn công đạt được cho mỗi tên, theo (thời gian chờ, ngân sách).

    Kẻ tấn công được hỏi bộ phát hiện bao nhiêu lần tùy ý (giả định mạnh nhất cho kẻ tấn công): với mỗi tên,
    chọn tổ hợp việc miễn phí tốt nhất, rồi chia ngân sách giữa sao GitHub và lượt tải theo 5 tỷ lệ.
    """
    out: dict[tuple[int, float], np.ndarray] = {}
    keys = list(FREE_CHOICES)
    combos = [dict(zip(keys, v)) for v in itertools.product(*FREE_CHOICES.values())]
    for wait in costs.waits_days:
        best_free = None
        best_score = None
        for ch in combos:
            X = _apply_free(base, wait, desc_len_log, ch)
            s = model.score(name_feats.join(X[META_COLS]))
            if best_score is None:
                best_score, best_free = s, [ch] * len(s)
            else:
                better = s < best_score
                best_score = np.where(better, s, best_score)
                best_free = [c if b else o for b, c, o in zip(better, [ch] * len(s), best_free)]
        X0 = pd.concat([_apply_free(base.iloc[[i]], wait, desc_len_log, best_free[i]) for i in range(len(base))])
        for budget in costs.budgets:
            if budget == 0:
                out[(wait, budget)] = best_score
                continue
            scores = []
            for f in (0.0, 0.25, 0.5, 0.75, 1.0):
                X = X0.copy()
                stars = f * budget / costs.usd_per_star
                dls = (1 - f) * budget / costs.usd_per_download
                X["log_stars"] = np.log1p(np.expm1(X["log_stars"]) + stars)
                X["log_downloads"] = np.log1p(np.expm1(X["log_downloads"]) + dls)
                scores.append(model.score(name_feats.join(X[META_COLS])))
            out[(wait, budget)] = np.minimum(best_score, np.min(np.vstack(scores), axis=0))
    return out


def evasion(variants: pd.DataFrame, registrable: pd.Series, evades: pd.Series) -> dict[str, float]:
    """Tỷ lệ né trung bình trên các câu hỏi đã chọn, theo model LLM.

    variants: dòng (original, model_key, prompt_id, sample, variant). evades: tên -> bool (không bị cảnh báo).
    """
    v = variants.copy()
    v["ok"] = v["variant"].map(registrable).fillna(False).astype(bool) & v["variant"].map(evades).fillna(False).astype(bool)
    v["opp"] = v["variant"].map(registrable).fillna(False).astype(bool)
    per_sample = v.groupby(["original", "model_key", "prompt_id", "sample"]).agg(ok=("ok", "max"), opp=("opp", "max")).reset_index()
    # Mẫu số: 10 lần hỏi mỗi câu (kể cả lần không có tên bịa nào).
    per_sel = per_sample.groupby(["original", "model_key", "prompt_id"]).agg(ok=("ok", "sum"), opp=("opp", "sum")).reset_index()
    per_sel["ok"] /= 10
    per_sel["opp"] /= 10
    res = {}
    for m, g in per_sel.groupby("model_key"):
        res[m] = {"selections": int(len(g)), "evasion": round(float(g["ok"].mean()), 4), "opportunity": round(float(g["opp"].mean()), 4)}
    return res
