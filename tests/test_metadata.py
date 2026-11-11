from __future__ import annotations

from slopcollect.stages.metadata import compute_features, github_repo_from_urls


def test_org_owned_and_verified_repo_any_url():
    raws = {
        "pypi_json": {
            "info": {
                "name": "Flask",
                "summary": "web",
                "description": "x" * 10,
                "project_urls": {"Donate": "https://palletsprojects.com/donate", "Docs": "https://github.com/pallets/docs", "Source": "https://github.com/pallets/flask/"},
            },
            "releases": {
                "0.1": [{"upload_time_iso_8601": "2010-04-16T14:29:37Z", "yanked": False}],
                "3.0": [{"upload_time_iso_8601": "2023-09-30T00:00:00Z", "yanked": False}, {"upload_time_iso_8601": "2023-09-30T00:00:01Z", "yanked": False}],
                "9.9": [],
            },
            "ownership": {"organization": "pallets", "roles": []},
        },
        "pypi_provenance": {"has_provenance": True, "publishers": [{"kind": "GitHub", "repository": "pallets/flask"}]},
        "pypistats": {"data": {"last_month": 123}},
    }
    f = compute_features(raws)
    assert f["n_owners"] == 0 and f["has_organization"] == 1
    assert f["github_repo"] == "pallets/docs"  # link GitHub đầu tiên
    assert f["source_repo_verified"] == 1      # nhưng link Source khớp kho phát hành
    assert f["n_releases"] == 2 and f["n_files"] == 3
    assert f["first_release_at"].startswith("2010") and f["last_release_at"].startswith("2023")
    assert f["downloads_last_month"] == 123


def test_no_ownership_field_is_unknown_and_no_provenance_unverified():
    f = compute_features({"pypi_json": {"info": {}, "releases": {}}, "pypi_provenance": {"has_provenance": False}})
    assert f["n_owners"] is None
    assert f["source_repo_verified"] == 0
    assert f["n_releases"] == 0 and f["all_yanked"] == 0


def test_github_url_parsing():
    assert github_repo_from_urls(["https://github.com/sponsors/x", "git+https://github.com/Foo/Bar.git#egg=bar"]) == "foo/bar"
    assert github_repo_from_urls(["https://gitlab.com/a/b"]) is None
