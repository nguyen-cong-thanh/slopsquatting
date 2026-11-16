"""Backend Ollama, gọi API gốc /api/chat (hỗ trợ tắt thinking bằng ``think: false``)."""

from __future__ import annotations

import time
from typing import Any

from slopcollect.backends.base import Backend, BackendError, ChatResult, raise_for_response, split_think_tags
from slopcollect.registry import register
from slopcollect.util import http_request

# Tên tham số chung -> tên trong options của Ollama.
_OPTION_MAP = {"temperature": "temperature", "top_p": "top_p", "top_k": "top_k", "max_tokens": "num_predict"}


@register("backend", "ollama")
class OllamaBackend(Backend):
    def chat(self, messages: list[dict[str, str]], params: dict[str, Any], seed: int | None) -> ChatResult:
        options: dict[str, Any] = {}
        for k, v in params.items():
            if k in _OPTION_MAP and v is not None:
                options[_OPTION_MAP[k]] = v
        if seed is not None:
            options["seed"] = seed
        options.update(self.cfg.extra.get("options", {}))
        body: dict[str, Any] = {
            "model": self.cfg.model,
            "messages": messages,
            "stream": False,
            "options": options,
            "keep_alive": self.cfg.extra.get("keep_alive", "30m"),
        }
        if params.get("think") is not None:
            body["think"] = bool(params["think"])
        url = self.cfg.base_url.rstrip("/") + "/api/chat"
        t0 = time.monotonic()
        resp = http_request(url, method="POST", json_body=body, timeout=self.cfg.timeout_s)
        latency = int((time.monotonic() - t0) * 1000)
        raise_for_response(resp, "ollama /api/chat")
        data = resp.json()
        if "error" in data:
            raise BackendError(f"ollama: {data['error']}", transient=False)
        msg = data.get("message") or {}
        text, inline_think = split_think_tags(msg.get("content") or "")
        reasoning = msg.get("thinking") or inline_think
        return ChatResult(
            text=text,
            reasoning=reasoning,
            finish_reason=data.get("done_reason"),
            tokens_in=data.get("prompt_eval_count"),
            tokens_out=data.get("eval_count"),
            latency_ms=latency,
        )
