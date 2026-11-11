"""Backend giả, trả lời tất định theo băm của câu hỏi. Dùng cho test và chạy thử offline."""

from __future__ import annotations

import random
import time
from typing import Any

from slopcollect.backends.base import Backend, BackendError, ChatResult
from slopcollect.registry import register
from slopcollect.util import sha256_hex

DEFAULT_REAL = ["requests", "numpy", "pandas", "flask", "scikit-learn", "matplotlib", "beautifulsoup4", "pyyaml"]
DEFAULT_FAKE = ["vectorcache", "fastyaml-pro", "flask-autodoc-gen", "pandas-easyio", "torch-utilzz"]
# Tên module khác tên gói, để kiểm tra bước ánh xạ module -> gói.
_MODULE_OF = {"scikit-learn": "sklearn", "beautifulsoup4": "bs4", "pyyaml": "yaml"}


@register("backend", "fake")
class FakeBackend(Backend):
    # Test có thể gán tập câu hỏi sẽ lỗi (lỗi tạm thời) để kiểm tra chạy tiếp.
    fail_when_contains: tuple[str, ...] = ()

    def chat(self, messages: list[dict[str, str]], params: dict[str, Any], seed: int | None) -> ChatResult:
        text = "\n".join(m["content"] for m in messages)
        for marker in self.fail_when_contains:
            if marker in text:
                raise BackendError("fake: lỗi giả lập", transient=False)
        if self.cfg.extra.get("delay_s"):
            time.sleep(float(self.cfg.extra["delay_s"]))  # mô phỏng độ trễ (test dừng / chạy tiếp)
        rng = random.Random(sha256_hex(text, str(seed)))
        real = list(self.cfg.extra.get("real_names", DEFAULT_REAL))
        fake = list(self.cfg.extra.get("fake_names", DEFAULT_FAKE))
        rate = float(self.cfg.extra.get("hallucination_rate", 0.3))
        names = rng.sample(real, k=min(3, len(real)))
        if rng.random() < rate:
            names.append(rng.choice(fake))
        if "separated by commas" in text:
            out = ", ".join(names)
        else:
            imports = "\n".join(f"import {_MODULE_OF.get(n, n.replace('-', '_'))}" for n in names)
            out = (
                f"```bash\npip install {' '.join(names)}\n```\n\n"
                f"```python\n{imports}\nimport os\nfrom collections import Counter\n\n"
                "def main():\n    return Counter(os.listdir('.'))\n```\n"
            )
        return ChatResult(text=out, finish_reason="stop", tokens_in=len(text) // 4, tokens_out=len(out) // 4, latency_ms=1)
