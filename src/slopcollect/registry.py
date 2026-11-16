"""Registry plugin: bước xử lý, backend LLM, nguồn câu hỏi, nguồn danh sách, luật gắn nhãn.

Thêm một loại mới = viết một hàm/class và gắn decorator ``@register(kind, name)``;
không phải sửa các bước khác. File luồng (TOML) gọi plugin theo tên.
"""

from __future__ import annotations

import importlib
from typing import Any, Callable

KINDS = ("stage", "backend", "source", "list_source", "label_rule")

_REGISTRY: dict[str, dict[str, Any]] = {k: {} for k in KINDS}

# Các module chứa plugin có sẵn; chỉ được import thư viện chuẩn ở cấp module.
_BUILTIN_MODULES = (
    "slopcollect.backends.ollama",
    "slopcollect.backends.openai_compat",
    "slopcollect.backends.fake",
    "slopcollect.sources.spracklen",
    "slopcollect.sources.jsonl",
    "slopcollect.stages.prompts",
    "slopcollect.stages.generate",
    "slopcollect.stages.extract",
    "slopcollect.stages.pypi",
    "slopcollect.stages.metadata",
    "slopcollect.stages.lists",
    "slopcollect.stages.label",
    "slopcollect.stages.select",
    "slopcollect.stages.merge",
    "slopcollect.stages.export",
    "slopcollect.stages.stats",
)
_loaded = False


def register(kind: str, name: str) -> Callable[[Any], Any]:
    if kind not in _REGISTRY:
        raise ValueError(f"Loại plugin không hợp lệ: {kind}")

    def deco(obj: Any) -> Any:
        if name in _REGISTRY[kind] and _REGISTRY[kind][name] is not obj:
            raise ValueError(f"Trùng tên plugin {kind}:{name}")
        _REGISTRY[kind][name] = obj
        return obj

    return deco


def load_builtins() -> None:
    global _loaded
    if _loaded:
        return
    for mod in _BUILTIN_MODULES:
        importlib.import_module(mod)
    _loaded = True


def get(kind: str, name: str) -> Any:
    load_builtins()
    try:
        return _REGISTRY[kind][name]
    except KeyError:
        available = ", ".join(sorted(_REGISTRY[kind])) or "(trống)"
        raise KeyError(f"Không có {kind} tên '{name}'. Hiện có: {available}") from None


def names(kind: str) -> list[str]:
    load_builtins()
    return sorted(_REGISTRY[kind])
