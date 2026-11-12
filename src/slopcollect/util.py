"""Các hàm nhỏ dùng chung: băm, thời gian, HTTP, giới hạn tốc độ. Chỉ dùng thư viện chuẩn."""

from __future__ import annotations

import hashlib
import json
import logging
import random
import socket
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar

log = logging.getLogger("slopcollect")

USER_AGENT = "slopcollect/0.1 (academic research on package hallucination)"

T = TypeVar("T")


def sha256_hex(*parts: str) -> str:
    """Băm nhiều chuỗi, có ký tự phân cách để ("ab","c") khác ("a","bc")."""
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x1f")
    return h.hexdigest()


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class NetworkError(Exception):
    """Lỗi mạng (timeout, không kết nối được). Luôn coi là lỗi tạm thời."""


@dataclass
class Response:
    status: int
    headers: dict[str, str]
    body: bytes

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    @property
    def transient(self) -> bool:
        return self.status == 429 or self.status >= 500


def http_request(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    json_body: Any = None,
    body: bytes | None = None,
    timeout: float = 60.0,
) -> Response:
    """Gửi một request HTTP. Trả về Response với mọi mã trạng thái; chỉ ném NetworkError khi lỗi mạng."""
    hdrs = {"User-Agent": USER_AGENT}
    if headers:
        hdrs.update(headers)
    data = body
    if json_body is not None:
        data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return Response(resp.status, dict(resp.headers.items()), resp.read())
    except urllib.error.HTTPError as e:
        body = e.read() if e.fp is not None else b""
        return Response(e.code, dict(e.headers.items()) if e.headers else {}, body)
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as e:
        raise NetworkError(f"{method} {url}: {e}") from e


def retry(
    fn: Callable[[], T],
    *,
    attempts: int,
    is_transient: Callable[[BaseException], bool],
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    on_retry: Callable[[int, BaseException], None] | None = None,
) -> tuple[T, int]:
    """Chạy fn, thử lại khi lỗi tạm thời (backoff mũ có nhiễu). Trả về (kết quả, số lần đã thử)."""
    for i in range(1, attempts + 1):
        try:
            return fn(), i
        except BaseException as e:  # noqa: BLE001 - phân loại bằng is_transient
            if isinstance(e, KeyboardInterrupt) or i == attempts or not is_transient(e):
                raise
            if on_retry:
                on_retry(i, e)
            delay = min(max_delay, base_delay * (2 ** (i - 1))) * (0.5 + random.random())
            time.sleep(delay)
    raise AssertionError("unreachable")


class RateLimiter:
    """Giới hạn số request mỗi giây, an toàn khi dùng từ nhiều luồng."""

    def __init__(self, per_second: float | None):
        self.interval = 1.0 / per_second if per_second else 0.0
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self) -> None:
        if not self.interval:
            return
        with self._lock:
            now = time.monotonic()
            start = max(now, self._next)
            self._next = start + self.interval
        if start > now:
            time.sleep(start - now)


def stable_order_key(seed: str, item_id: str) -> str:
    """Thứ tự ngẫu nhiên nhưng cố định: lấy N phần tử đầu luôn ra cùng một tập con."""
    return sha256_hex(seed, item_id)
