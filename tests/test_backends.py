from __future__ import annotations

from slopcollect.backends.openai_compat import render_raw_prompt

GLM = {
    "prefix": "[gMASK]<sop>",
    "system": "<|system|>{content}",
    "user": "<|user|>{content}",
    "assistant": "<|assistant|>\n<think></think>{content}",
    "generation": "<|assistant|>\n<think></think>",
}


def test_raw_prompt_glm_without_thinking():
    p = render_raw_prompt([{"role": "user", "content": "Which packages?"}], GLM)
    assert p == "[gMASK]<sop><|user|>Which packages?<|assistant|>\n<think></think>"


def test_raw_prompt_with_system_and_history():
    msgs = [{"role": "system", "content": "S"}, {"role": "user", "content": "U"}, {"role": "assistant", "content": "A"}, {"role": "user", "content": "V"}]
    assert render_raw_prompt(msgs, GLM) == "[gMASK]<sop><|system|>S<|user|>U<|assistant|>\n<think></think>A<|user|>V<|assistant|>\n<think></think>"
