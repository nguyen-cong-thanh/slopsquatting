"""Đặc trưng tên, mô hình và cách đo (tỷ lệ phát hiện khi chỉ báo nhầm 1% tên thật)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from slopcollect.detect.data import META_COLS

AGE_COLS = ("age_days", "days_since_last_release", "github_age_days")
NAME_COLS = [
    "len", "n_tokens", "n_digits", "has_py", "vowel_ratio", "max_token_len",
    "first_token_on_pypi", "all_tokens_on_pypi", "share_tokens_on_pypi", "is_on_pypi_without_sep",
]


class NameFeaturizer:
    """Đặc trưng thủ công của tên, không được dùng việc chính tên đó có trên PyPI hay không.

    Tầng 1 đã tra PyPI; ở tầng 2 mọi tên đều có trên PyPI (kể cả gói của kẻ tấn công sau khi đăng ký), nên
    đặc trưng "tên có trên PyPI" là rò rỉ nhãn. Chỉ xét các token của tên nhiều token, và các tên KHÁC trên PyPI.
    """

    def __init__(self, pypi_names: set[str]):
        from collections import Counter

        self.pypi = pypi_names
        self.nosep_count = Counter(re.sub(r"[-_.]", "", n) for n in pypi_names)

    def frame(self, names: list[str]) -> pd.DataFrame:
        rows = []
        for n in names:
            toks = [t for t in n.split("-") if t]
            multi = len(toks) > 1
            letters = [ch for ch in n if ch.isalpha()]
            on = [t in self.pypi for t in toks] if multi else []
            others_same_letters = self.nosep_count.get(n.replace("-", ""), 0) - (1 if n in self.pypi else 0)
            rows.append({
                "len": len(n),
                "n_tokens": len(toks),
                "n_digits": sum(ch.isdigit() for ch in n),
                "has_py": int(n.startswith("py") or "python" in n),
                "vowel_ratio": sum(ch in "aeiou" for ch in letters) / max(1, len(letters)),
                "max_token_len": max((len(t) for t in toks), default=0),
                "first_token_on_pypi": int(multi and toks[0] in self.pypi),
                "all_tokens_on_pypi": int(multi and all(on)),
                "share_tokens_on_pypi": (sum(on) / len(toks)) if multi else 0.0,
                "is_on_pypi_without_sep": int(multi and others_same_letters > 0),
            })
        return pd.DataFrame(rows, index=names, columns=NAME_COLS)


@dataclass
class Model:
    """Một bộ phát hiện: cho điểm đáng ngờ trong [0, 1] với mỗi dòng (tên + metadata)."""

    name: str
    kind: str                      # "tfidf_lr" | "lr" | "hgb"
    features: list[str]            # cột dùng (với tfidf_lr: không dùng)
    est: Any = None
    tfidf: Any = None
    extra: dict[str, Any] = field(default_factory=dict)

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> "Model":
        w = _balanced_weights(y)
        if self.kind == "tfidf_lr":
            self.tfidf = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=2, sublinear_tf=True)
            M = self.tfidf.fit_transform(list(X.index))
            self.est = LogisticRegression(max_iter=2000, C=4.0, class_weight="balanced").fit(M, y)
        elif self.kind == "lr":
            self.est = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced"))
            self.est.fit(X[self.features].fillna(-1).values, y)
        elif self.kind == "hgb":
            self.est = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08, max_leaf_nodes=31, random_state=0)
            self.est.fit(X[self.features].values, y, sample_weight=w)
        else:
            raise ValueError(self.kind)
        return self

    def score(self, X: pd.DataFrame) -> np.ndarray:
        if self.kind == "tfidf_lr":
            return self.est.predict_proba(self.tfidf.transform(list(X.index)))[:, 1]
        if self.kind == "lr":
            return self.est.predict_proba(X[self.features].fillna(-1).values)[:, 1]
        return self.est.predict_proba(X[self.features].values)[:, 1]


def _balanced_weights(y: np.ndarray) -> np.ndarray:
    pos = max(1, int(y.sum()))
    neg = max(1, int(len(y) - y.sum()))
    return np.where(y == 1, len(y) / (2 * pos), len(y) / (2 * neg))


def threshold_at_fpr(neg_scores: np.ndarray, fpr: float = 0.01) -> float:
    """Ngưỡng để tối đa ``fpr`` tên thật bị báo (điểm > ngưỡng là cảnh báo)."""
    return float(np.quantile(neg_scores, 1 - fpr, method="higher"))


def rate(scores: np.ndarray, thr: float) -> float:
    return float(np.mean(scores > thr)) if len(scores) else float("nan")


def auc(neg: np.ndarray, pos: np.ndarray) -> float:
    from sklearn.metrics import roc_auc_score

    if not len(neg) or not len(pos):
        return float("nan")
    return float(roc_auc_score(np.r_[np.zeros(len(neg)), np.ones(len(pos))], np.r_[neg, pos]))


def name_only_models() -> list[Model]:
    return [
        Model("tên: n-gram ký tự + LR", "tfidf_lr", []),
        Model("tên: đặc trưng thủ công + GB", "hgb", NAME_COLS),
    ]


def tier2_models() -> list[Model]:
    return [
        Model("chỉ tên (GB)", "hgb", NAME_COLS),
        Model("chỉ metadata (GB)", "hgb", META_COLS),
        Model("tên + metadata (LR)", "lr", NAME_COLS + META_COLS),
        Model("tên + metadata (GB)", "hgb", NAME_COLS + META_COLS),
        Model("tên + metadata trừ tuổi (GB)", "hgb", NAME_COLS + [c for c in META_COLS if c not in AGE_COLS]),
    ]
