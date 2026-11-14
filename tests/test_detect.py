from __future__ import annotations

import pandas as pd
import pytest

pytest.importorskip("sklearn")

from slopcollect.detect.attack import evasion  # noqa: E402
from slopcollect.detect.data import cluster_key  # noqa: E402
from slopcollect.detect.models import threshold_at_fpr  # noqa: E402


def test_cluster_key_groups_variants():
    assert cluster_key("py-vector-cache") == cluster_key("vectorcache") == cluster_key("vector_cache-python")
    assert cluster_key("torch-nn") != cluster_key("torch")


def test_evasion_counts_samples_out_of_ten():
    # Câu hỏi có 10 lần hỏi; tên "a" (đăng ký được, không bị bắt) xuất hiện ở lần 0 và 3,
    # "b" (bị bắt) ở lần 5, "c" (không đăng ký được) ở lần 7.
    v = pd.DataFrame(
        [("a", "m", "p", s, x) for s, x in [(0, "a"), (3, "a"), (5, "b"), (7, "c")]],
        columns=["original", "model_key", "prompt_id", "sample", "variant"],
    )
    reg = pd.Series({"a": True, "b": True, "c": False})
    ev = pd.Series({"a": True, "b": False, "c": True})
    r = evasion(v, reg, ev)["m"]
    assert r["evasion"] == 0.2      # lần 0 và 3
    assert r["opportunity"] == 0.3  # lần 0, 3, 5 (c không đăng ký được)


def test_threshold_keeps_fpr():
    import numpy as np

    neg = np.linspace(0, 1, 1001)
    thr = threshold_at_fpr(neg, 0.01)
    assert (neg > thr).mean() <= 0.01


def test_cut_feature_sign_and_wait_invariance():
    from slopcollect.detect.tier2_cutoff import _cut_feature

    now, cut = pd.Timestamp("2026-11-12"), pd.Timestamp("2023-12-31")
    age = pd.Series([10.0, 2000.0])  # đăng ký 10 ngày trước (sau mốc) / 2000 ngày trước (trước mốc)
    f = _cut_feature(age, now, cut)
    assert f.iloc[0] > 0 and f.iloc[1] < 0
    # Chờ thêm w ngày: tuổi và "now" cùng tăng w, đặc trưng không đổi.
    w = 365
    assert (_cut_feature(age + w, now + pd.Timedelta(days=w), cut) == f).all()
