"""Luật tên của PyPI. Các ca kiểm thử đầu chép từ warehouse tests/unit/packaging/test_services.py
(commit dd5954ec6fe2914e7e4c4c8bd22d07d209a54e4d)."""

from __future__ import annotations

import pytest
from packaging.utils import canonicalize_name

from slopcollect.extract.normalize import (
    check_registrable,
    normalize_pep426_name,
    stdlib_prohibited,
    ultranormalize_name,
)


def registry_of(*names: str):
    norms = {normalize_pep426_name(n) for n in names}
    ultras = {ultranormalize_name(n): n for n in names}
    return {"exists": lambda n: n in norms, "similar": lambda u: ultras.get(u)}


# ---- chép từ warehouse

@pytest.mark.parametrize("name", ["", ".,;", "_z", "İnspect"])
def test_warehouse_invalid(name):
    assert check_registrable(name, **registry_of()).reason == "invalid"


@pytest.mark.parametrize("name", ["uu", "cgi", "nis", "mailcap"])
def test_warehouse_stdlib(name):
    assert check_registrable(name, **registry_of()).reason == "stdlib"


def test_warehouse_already_exists():
    reg = registry_of("foo")
    assert check_registrable("foo", **reg).reason == "existing"
    assert check_registrable("Foo", **reg).reason == "existing"


def test_warehouse_too_similar():
    r = check_registrable("foo", **registry_of("f00"))
    assert r.reason == "similar" and r.similar_to == "f00"


def test_warehouse_too_similar_multiple_existing():
    r = check_registrable("foo", **registry_of("f00", "f0o"))
    assert r.reason == "similar" and r.similar_to in ("f00", "f0o")


def test_warehouse_ok():
    assert check_registrable("foo", **registry_of()).registrable


def test_warehouse_typo_check_does_not_block():
    # warehouse chỉ gắn cờ "numpi" cho quản trị viên sau khi tạo, không từ chối đăng ký.
    assert check_registrable("numpi", **registry_of("numpy")).registrable


# ---- ca tự viết

@pytest.mark.parametrize("name", ["Vector_Cache", "vector.cache", "vector-cache", "vector..cache", "VECTOR_-_cache"])
def test_pep503_forms_collapse(name):
    assert normalize_pep426_name(name) == "vector-cache"


@pytest.mark.parametrize("name", ["Vector_Cache", "a..b", "A-B_c.D", "x", "Foo___Bar", "requests", "-weird-"])
def test_matches_packaging_canonicalize(name):
    assert normalize_pep426_name(name) == canonicalize_name(name)


def test_ultranormalize_order_and_case():
    assert ultranormalize_name("Il0o-x") == "1100x"
    assert ultranormalize_name("I.L_i-l") == "1111"
    assert ultranormalize_name("torch-utils") == ultranormalize_name("TORCH_UT1LS")


@pytest.mark.parametrize("name", ["asyncio", "xml.dom", "xml-dom", "Tkinter", "distutils"])
def test_stdlib_names_blocked(name):
    assert normalize_pep426_name(name) in stdlib_prohibited()


def test_check_order_stdlib_before_existing():
    # dataclasses vừa là thư viện chuẩn vừa có trên PyPI (bản backport): warehouse báo stdlib trước.
    assert check_registrable("dataclasses", **registry_of("dataclasses")).reason == "stdlib"


def test_existing_before_similar():
    assert check_registrable("f00", **registry_of("f00", "foo")).reason == "existing"
