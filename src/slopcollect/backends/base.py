"""Giao diện chung của backend LLM."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from slopcollect.config import ModelConfig
from slopcollect.util import NetworkError, Response


class BackendError(Exception):
    """Lỗi từ backend. transient=True: nên thử lại (quá tải, timeout, lỗi 5xx).

    fatal=True: lỗi về tài khoản (hết tiền 402, sai khóa 401, không có quyền 403). Mọi câu sau đều sẽ
    lỗi như vậy, nên bước generate dừng ngay thay vì ghi lỗi cho từng câu.
    """

    def __init__(self, message: str, *, transient: bool, fatal: bool = False):
        super().__init__(message)
        self.transient = transient
        self.fatal = fatal


class FatalBackendError(Exception):
    """Dừng cả luồng: lỗi tài khoản/khóa API, chạy lại cũng không khỏi cho tới khi người dùng xử lý."""


FATAL_STATUSES = {401, 402, 403}


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
        """Khóa API: biến môi trường api_key_env trước, rồi file api_key_file. Không cấu hình gì thì không gửi khóa."""
        if not self.cfg.api_key_env and not self.cfg.api_key_file:
            return None
        if self.cfg.api_key_env and os.environ.get(self.cfg.api_key_env):
            return os.environ[self.cfg.api_key_env].strip()
        if self.cfg.api_key_file:
            path = Path(self.cfg.api_key_file).expanduser()
            if path.is_file():
                key = path.read_text(encoding="utf-8").strip()
                if key:
                    return key
        raise BackendError(
            f"Không tìm thấy khóa API: đặt biến {self.cfg.api_key_env or '(không)'} hoặc tạo file {self.cfg.api_key_file or '(không)'}",
            transient=False,
        )


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
    raise BackendError(f"{what}: HTTP {resp.status}: {detail}", transient=resp.transient, fatal=resp.status in FATAL_STATUSES)
