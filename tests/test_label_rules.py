from __future__ import annotations

from slopcollect.stages.label import rule_known_malicious, rule_pre_cutoff

CFG = {"malicious_lists": ["datadog", "osv_malicious"]}


def info(lists, exists=True, n_releases=0):
    return {"lists": lists, "status": {"exists_on_pypi": exists}, "features": {"n_releases": n_releases}}


def test_whole_package_malicious():
    # DataDog ghi None: mọi phiên bản độc hại.
    assert rule_known_malicious(info({"datadog": {"versions": None}}, exists=False), CFG)[0] == "known_malicious"
    assert rule_known_malicious(info({"datadog": {"versions": None}}, n_releases=3), CFG)[0] == "known_malicious"


def test_compromised_popular_package_is_real():
    # Gói thật còn trên PyPI, chỉ 2 trong 990 phiên bản bị nhiễm.
    i = info({"osv_malicious": {"versions": ["1.82.7", "1.82.8"]}, "datadog": {"versions": ["1.82.8"]}}, n_releases=990)
    assert rule_known_malicious(i, CFG) is None
    lab, review, ev = rule_pre_cutoff(i, CFG)
    assert lab == "pre_cutoff_unverified" and ev["compromised_versions"] == ["1.82.7", "1.82.8"]


def test_removed_package_with_listed_versions_stays_malicious():
    # Đã bị gỡ khỏi PyPI, hoặc mọi phiên bản còn lại đều bị liệt kê.
    assert rule_known_malicious(info({"osv_malicious": {"versions": ["0.1"]}}, exists=False), CFG)[0] == "known_malicious"
    assert rule_known_malicious(info({"osv_malicious": {"versions": ["0.1", "0.2"]}}, n_releases=2), CFG)[0] == "known_malicious"


def test_hallucination_list_is_not_malicious():
    assert rule_known_malicious(info({"0pstech": {}}), CFG) is None


def test_placeholder_ignores_long_readme():
    from slopcollect.stages.label import DEFAULT_PLACEHOLDER_PATTERNS, rule_placeholder

    cfg = {"placeholder_patterns": DEFAULT_PLACEHOLDER_PATTERNS, "placeholder_max_desc": 400}
    long_readme = "Parameter-efficient fine-tuning. " * 30 + "The old API is deprecated."
    assert rule_placeholder({"features": {"summary": "PEFT"}, "description": long_readme}, cfg) is None
    assert rule_placeholder({"features": {"summary": "DEPRECATED; use python-ldap instead"}, "description": long_readme}, cfg)[0] == "placeholder"
    assert rule_placeholder({"features": {"summary": ""}, "description": "# Security Holding Package\nplaceholder"}, cfg)[0] == "placeholder"


def _cut_info(models, first, **feat):
    return {"models": set(models), "version": feat.pop("version", "1.2.3"),
            "features": {"first_release_at": first, **feat}}


def _cuts():
    from datetime import datetime, timezone

    from slopcollect.timing import Cutoffs

    d = lambda y, m, dd: datetime(y, m, dd, tzinfo=timezone.utc)  # noqa: E731
    return Cutoffs(date={"a": d(2023, 12, 31), "b": d(2025, 12, 31), "u": d(2026, 2, 28), "f": d(2023, 10, 31)},
                   upper={"u"}, released={"a": d(2024, 7, 18), "b": d(2026, 3, 1)})


def test_timing_shared_rule():
    from datetime import datetime, timezone

    from slopcollect.timing import released_before, timing

    c = _cuts()
    t = lambda s: datetime.fromisoformat(s).replace(tzinfo=timezone.utc)  # noqa: E731
    # Trong khoảng đệm 30 ngày sau mốc: có từ trước mốc.
    assert timing(t("2024-01-15"), ["a"], c) == ("before", [])
    # Chỉ cần MỘT model có mốc + đệm sớm hơn lần tải lên (a), dù b có mốc muộn hơn.
    assert timing(t("2025-06-01"), ["a", "b"], c) == ("after", ["a"])
    # Model chưa rõ mốc, không model nào kết luận được "after": không kết luận.
    assert timing(t("2023-06-01"), ["a", "x"], c)[0] == "unknown"
    # Mốc chỉ là giới hạn trên: chỉ kết luận "before" khi gói có trước mốc chính xác sớm nhất (31/10/2023).
    assert timing(t("2025-06-01"), ["u"], c)[0] == "unknown"
    assert timing(t("2023-06-01"), ["u"], c)[0] == "before"
    assert timing(None, ["a"], c)[0] == "unknown"
    assert timing(None, ["a"], c, legacy=True)[0] == "before"
    # Không có ngày tải lên, nhưng dự án đã tồn tại từ 2019 (sự kiện cuối trên PyPI): có từ trước mốc.
    assert timing(None, ["a"], c, exists_by=t("2019-08-15"))[0] == "before"
    # Sự kiện cuối sau mốc: không biết dự án ra đời khi nào, không kết luận được.
    assert timing(None, ["a"], c, exists_by=t("2025-08-15"))[0] == "unknown"
    assert released_before(t("2025-06-01"), ["a", "b"], c) == ["a"]


def test_after_model_cutoff_is_filter_only():
    from slopcollect.stages.label import rule_after_model_cutoff

    cfg = {"cutoffs": _cuts(), "cutoff_margin_days": 30}
    # Có từ trước mốc: lọt lưới (luật sau quyết định, thường là real).
    assert rule_after_model_cutoff(_cut_info(["a"], "2024-01-15T00:00:00Z"), cfg) is None
    # Sau mốc của một model hoặc không kết luận được: luôn đưa đi duyệt tay, kể cả gói có vẻ hợp lệ.
    for models, first in ((["a", "b"], "2025-06-01T00:00:00Z"), (["u"], "2025-06-01T00:00:00Z"), (["a"], None)):
        lab, review, ev = rule_after_model_cutoff(_cut_info(models, first, has_organization=1, downloads_last_month=459353), cfg)
        assert (lab, review) == ("registered_hallucination", True)
    assert ev["timing"] == "unknown"
