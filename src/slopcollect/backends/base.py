"""Giao diện chung của backend LLM."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

from slopcollect.config import ModelConfig
from slopcollect.util import NetworkError, Response


class BackendError(Exception):
    """Lỗi từ backend. transient=True: nên thử lại (quá tải, timeout, lỗi 5xx)."""

    def __init__(self, message: str, *, transient: bool):
        super().__init__(message)
        self.transient = transient


def is_transient(e: BaseException) -> bool:
    if isinstance(e, BackendError):
        return e.transient
    return isinstance(e, NetworkError)


@dataclass
class ChatResult:
    text: str
    reasoning: str | None = None
    finish_reason: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    latency_ms: int | None = None


class Backend:
    """Backend nhận danh sách message và tham số sinh, trả về ChatResult."""

    def __init__(self, cfg: ModelConfig):
        self.cfg = cfg

    def chat(self, messages: list[dict[str, str]], params: dict[str, Any], seed: int | None) -> ChatResult:
        raise NotImplementedError

    def api_key(self) -> str | None:
        if not self.cfg.api_key_env:
            return None
        key = os.environ.get(self.cfg.api_key_env)
        if not key:
            raise BackendError(f"Chưa đặt biến môi trường {self.cfg.api_key_env}", transient=False)
        return key


_THINK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL)


def split_think_tags(text: str) -> tuple[str, str | None]:
    """Một số server trả phần suy nghĩ trong thẻ <think>...</think> ngay trong content: tách ra."""
    found = _THINK_RE.findall(text)
    if not found:
        # Trường hợp chỉ có thẻ đóng (template đã chèn sẵn thẻ mở).
        if "</think>" in text and "<think>" not in text:
            head, _, tail = text.partition("</think>")
            return tail.lstrip(), head.strip() or None
        return text, None
    return _THINK_RE.sub("", text).lstrip(), "\n".join(s.strip() for s in found) or None


def raise_for_response(resp: Response, what: str) -> None:
    if resp.ok:
        return
    detail = resp.body[:500].decode("utf-8", "replace")
    raise BackendError(f"{what}: HTTP {resp.status}: {detail}", transient=resp.transient)
