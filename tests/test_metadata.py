from __future__ import annotations

import json

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


def test_github_graphql_batch(monkeypatch):
    from slopcollect.stages import metadata as m
    from slopcollect.util import Response

    sent = {}

    def fake_http(url, **kw):
        sent["query"] = kw["json_body"]["query"]
        body = {
            "data": {
                "r0": {"nameWithOwner": "pallets/flask", "stargazerCount": 70000, "createdAt": "2010-04-06T11:11:59Z", "isArchived": False, "isFork": False},
                "r1": None,
                "rateLimit": {"remaining": 4999, "resetAt": "2026-11-12T05:00:00Z"},
            },
            "errors": [{"type": "NOT_FOUND", "path": ["r1"], "message": "Could not resolve"}],
        }
        return Response(200, {}, json.dumps(body).encode())

    monkeypatch.setattr(m, "http_request", fake_http)
    pj = lambda url: {"pypi_json": {"info": {"project_urls": {"Source": url}}}}  # noqa: E731
    cache = {"flask": pj("https://github.com/pallets/flask"), "gone": pj("https://github.com/x/gone"), "nourl": pj("https://example.org"), "nopj": {}}
    got = m._fetch_github_bulk(list(cache), cache, "tok")
    assert got["flask"][0] == 200 and got["flask"][1]["stargazers_count"] == 70000
    assert got["gone"] == (404, {"repo": "x/gone"}, None)
    assert got["nourl"][1] == {"skipped": "no github url"} and got["nopj"][1] == {"skipped": "no pypi_json"}
    assert 'repository(owner: "pallets", name: "flask")' in sent["query"]
    assert m.compute_features({"github": got["flask"][1]})["github_stars"] == 70000
