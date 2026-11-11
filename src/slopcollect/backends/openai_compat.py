"""Backend theo chuẩn OpenAI /v1/chat/completions (vLLM, SGLang, GLM nội bộ, OpenRouter, ...)."""

from __future__ import annotations

import time
from typing import Any

from slopcollect.backends.base import Backend, BackendError, ChatResult, raise_for_response, split_think_tags
from slopcollect.registry import register
from slopcollect.util import http_request

# Cách tắt/bật thinking khác nhau theo server; chọn bằng extra.think_style trong file model.
#   chat_template_kwargs: vLLM / SGLang (Qwen3, GLM-4.5+ ...) -> {"chat_template_kwargs": {"enable_thinking": bool}}
#   zhipu: API kiểu Zhipu/Z.ai -> {"thinking": {"type": "enabled" | "disabled"}}
#   none: không gửi gì


def _think_fields(style: str, think: bool) -> dict[str, Any]:
    if style == "chat_template_kwargs":
        return {"chat_template_kwargs": {"enable_thinking": think}}
    if style == "zhipu":
        return {"thinking": {"type": "enabled" if think else "disabled"}}
    if style == "none":
        return {}
    raise BackendError(f"think_style không hợp lệ: {style}", transient=False)


@register("backend", "openai_compat")
class OpenAICompatBackend(Backend):
    def chat(self, messages: list[dict[str, str]], params: dict[str, Any], seed: int | None) -> ChatResult:
        extra = self.cfg.extra
        body: dict[str, Any] = {"model": self.cfg.model, "messages": messages, "stream": False}
        for k in ("temperature", "top_p", "max_tokens"):
            if params.get(k) is not None:
                body[k] = params[k]
        # top_k không thuộc chuẩn OpenAI nhưng vLLM/SGLang nhận; tắt bằng extra.send_top_k = false.
        if params.get("top_k") is not None and extra.get("send_top_k", True):
            body["top_k"] = params["top_k"]
        if seed is not None and extra.get("send_seed", True):
            body["seed"] = seed
        if params.get("think") is not None:
            body.update(_think_fields(extra.get("think_style", "chat_template_kwargs"), bool(params["think"])))
        body.update(extra.get("extra_body", {}))

        headers = {}
        key = self.api_key()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        url = self.cfg.base_url.rstrip("/") + "/chat/completions"
        t0 = time.monotonic()
        resp = http_request(url, method="POST", json_body=body, headers=headers, timeout=self.cfg.timeout_s)
        latency = int((time.monotonic() - t0) * 1000)
        raise_for_response(resp, "chat/completions")
        data = resp.json()
        if data.get("error"):
            raise BackendError(f"chat/completions: {data['error']}", transient=False)
        try:
            choice = data["choices"][0]
        except (KeyError, IndexError):
            raise BackendError(f"Phản hồi không có choices: {str(data)[:300]}", transient=True) from None
        msg = choice.get("message") or {}
        text, inline_think = split_think_tags(msg.get("content") or "")
        reasoning = msg.get("reasoning_content") or msg.get("reasoning") or inline_think
        usage = data.get("usage") or {}
        return ChatResult(
            text=text,
            reasoning=reasoning,
            finish_reason=choice.get("finish_reason"),
            tokens_in=usage.get("prompt_tokens"),
            tokens_out=usage.get("completion_tokens"),
            latency_ms=latency,
        )
