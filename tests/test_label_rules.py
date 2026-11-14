from __future__ import annotations

from slopcollect.stages.label import rule_known_malicious, rule_real

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
    lab, review, ev = rule_real(i, CFG)
    assert lab == "real" and ev["compromised_versions"] == ["1.82.7", "1.82.8"]


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
