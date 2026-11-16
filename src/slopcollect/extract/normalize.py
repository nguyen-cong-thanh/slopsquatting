"""Luật tên gói chép từ mã nguồn PyPI (pypi/warehouse, commit dd5954ec6fe2914e7e4c4c8bd22d07d209a54e4d, 10/11/2026).

- normalize_pep426_name: warehouse/migrations/versions/3af8d0006ba_normalize_runs_of_characters_to_a_.py
      lower(regexp_replace(name, '(\\.|_|-)+', '-', 'ig'))
  Trùng với packaging.utils.canonicalize_name (PEP 503).
- ultranormalize_name: warehouse/migrations/versions/d18d443f89f0_ultranormalize_name_function.py
      lower(regexp_replace(regexp_replace(regexp_replace(name, '(\\.|_|-)', '', 'ig'),
                                          '(l|L|i|I)', '1', 'ig'), '(o|O)', '0', 'ig'))
- PROJECT_NAME_RE: warehouse/utils/project.py
- check_project_name: warehouse/packaging/services.py (ProjectService.check_project_name). Thứ tự:
      1. tên không hợp lệ        -> invalid
      2. trùng thư viện chuẩn    -> stdlib   (STDLIB_PROHIBITED dựng từ gói stdlib-list)
      3. đã có project cùng tên  -> existing (so bằng normalize_pep426_name)
      4. nằm trong danh sách cấm -> prohibited (bảng nội bộ của PyPI, không công khai: KHÔNG kiểm tra được)
      5. quá giống project khác  -> similar  (so bằng ultranormalize_name)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from itertools import chain
from typing import Callable, Iterable, Iterator

RULES_VERSION = "warehouse-dd5954ec"

PROJECT_NAME_RE = re.compile(r"^([A-Z0-9]|[A-Z0-9][A-Z0-9._-]*[A-Z0-9])\Z", re.IGNORECASE | re.ASCII)

_SEP_RUNS = re.compile(r"[-_.]+")
_SEP = re.compile(r"[._-]")
_ONE = re.compile(r"[lLiI]")
_ZERO = re.compile(r"[oO]")


def normalize_pep426_name(name: str) -> str:
    return _SEP_RUNS.sub("-", name).lower()


def ultranormalize_name(name: str) -> str:
    s = _SEP.sub("", name)
    s = _ONE.sub("1", s)
    s = _ZERO.sub("0", s)
    return s.lower()


def is_valid_project_name(name: str) -> bool:
    return PROJECT_NAME_RE.match(name) is not None


def _namespace_stdlib_list(module_list: Iterable[str]) -> Iterator[str]:
    for module_name in module_list:
        parts = module_name.split(".")
        for i, _part in enumerate(parts):
            yield ".".join(parts[: i + 1])


@lru_cache(maxsize=1)
def stdlib_prohibited() -> frozenset[str]:
    """Tập tên bị cấm vì trùng thư viện chuẩn, dựng giống hệt STDLIB_PROHIBITED của warehouse."""
    try:
        import stdlib_list  # type: ignore[import-not-found]
    except ImportError as e:  # pragma: no cover - thông báo cài đặt
        raise RuntimeError("Bước check cần gói stdlib-list (uv sync --extra pypi hoặc pip install stdlib-list==0.12.0)") from e
    return frozenset(
        normalize_pep426_name(s.rstrip("-_.").lstrip("-_."))
        for s in chain.from_iterable(
            _namespace_stdlib_list(stdlib_list.stdlib_list(version)) for version in stdlib_list.short_versions
        )
    )


@dataclass(frozen=True)
class Registrability:
    registrable: bool
    reason: str | None = None
    similar_to: str | None = None


def check_registrable(
    name: str,
    *,
    exists: Callable[[str], bool],
    similar: Callable[[str], str | None],
    stdlib: frozenset[str] | None = None,
) -> Registrability:
    """Tên có đăng ký mới được trên PyPI không, theo đúng thứ tự kiểm tra của warehouse.

    exists(norm_name): đã có project với normalize_pep426_name này.
    similar(ultra_name): trả về tên một project có cùng ultranormalize_name, hoặc None.
    """
    if not is_valid_project_name(name):
        return Registrability(False, "invalid")
    std = stdlib if stdlib is not None else stdlib_prohibited()
    if normalize_pep426_name(name) in std:
        return Registrability(False, "stdlib")
    if exists(normalize_pep426_name(name)):
        return Registrability(False, "existing")
    # Bước 4 (danh sách cấm) không kiểm tra được: dữ liệu không công khai.
    other = similar(ultranormalize_name(name))
    if other is not None:
        return Registrability(False, "similar", other)
    return Registrability(True)
