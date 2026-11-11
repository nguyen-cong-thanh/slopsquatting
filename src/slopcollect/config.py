"""Đọc cấu hình TOML: model (configs/models), tác vụ hỏi LLM (configs/tasks), luồng (flows)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from slopcollect.util import canonical_json, sha256_hex


class ConfigError(Exception):
    pass


def load_toml(path: Path) -> dict[str, Any]:
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        raise ConfigError(f"Không tìm thấy file cấu hình: {path}") from None
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"Lỗi cú pháp TOML trong {path}: {e}") from None


def parse_cli_value(text: str) -> Any:
    """Đọc giá trị dạng TOML từ dòng lệnh (``limit=200``, ``tags=["a"]``); không được thì giữ chuỗi."""
    try:
        return tomllib.loads(f"v = {text}")["v"]
    except tomllib.TOMLDecodeError:
        return text


# Tham số chỉ ảnh hưởng cách gọi, không ảnh hưởng nội dung câu trả lời -> không đưa vào khóa băm.
_NON_IDENTITY_MODEL_KEYS = {"base_url", "concurrency", "timeout_s", "api_key_env", "description", "keep_alive"}


@dataclass(frozen=True)
class ModelConfig:
    key: str
    backend: str
    model: str
    base_url: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)
    concurrency: int = 1
    timeout_s: float = 600.0
    api_key_env: str | None = None
    description: str = ""


@dataclass(frozen=True)
class TaskConfig:
    """Một kiểu câu hỏi gửi LLM.

    input = "prompt": hỏi trực tiếp từ câu hỏi gốc.
    input = "generation": hỏi tiếp trên câu trả lời của tác vụ ``parent_task`` (ví dụ: hỏi
    "cần gói nào để chạy đoạn code này").
    """

    id: str
    input: str
    user: str
    system: str = ""
    parent_task: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    extract: tuple[str, ...] = ()
    strip_input: bool = True
    description: str = ""

    def render(self, *, prompt: str, response: str | None) -> list[dict[str, str]]:
        # Dùng replace thay cho format vì câu hỏi có thể chứa dấu ngoặc nhọn.
        # Thay {response} trước {prompt} để nội dung câu hỏi không bị thay lần hai.
        user = self.user
        if response is not None:
            user = user.replace("{response}", response.strip() if self.strip_input else response)
        user = user.replace("{prompt}", prompt.strip() if self.strip_input else prompt)
        msgs = []
        if self.system:
            msgs.append({"role": "system", "content": self.system})
        msgs.append({"role": "user", "content": user})
        return msgs


@dataclass(frozen=True)
class FlowConfig:
    name: str
    db: str
    steps: list[dict[str, Any]]
    description: str = ""
    path: Path | None = None


def _models_dir(root: Path) -> Path:
    return root / "configs" / "models"


def _tasks_dir(root: Path) -> Path:
    return root / "configs" / "tasks"


def load_model(root: Path, key: str) -> ModelConfig:
    """Đọc configs/models/<key>.toml. Nếu có <key>.local.toml (không đưa lên git) thì dùng file đó thay thế,
    để mỗi máy đặt địa chỉ/tên model riêng mà không sửa file trong repo."""
    local = _models_dir(root) / f"{key}.local.toml"
    path = local if local.exists() else _models_dir(root) / f"{key}.toml"
    raw = load_toml(path)
    missing = [k for k in ("backend", "model") if k not in raw]
    if missing:
        raise ConfigError(f"{path}: thiếu khóa {missing}")
    known = {"key", "backend", "model", "base_url", "params", "extra", "concurrency", "timeout_s", "api_key_env", "description"}
    unknown = set(raw) - known
    if unknown:
        raise ConfigError(f"{path}: khóa không hợp lệ {sorted(unknown)}")
    if raw.get("key", key) != key:
        raise ConfigError(f"{path}: key = {raw['key']!r} phải trùng tên file ({key!r})")
    return ModelConfig(
        key=key,
        backend=raw["backend"],
        model=raw["model"],
        base_url=raw.get("base_url", ""),
        params=dict(raw.get("params", {})),
        extra=dict(raw.get("extra", {})),
        concurrency=int(raw.get("concurrency", 1)),
        timeout_s=float(raw.get("timeout_s", 600)),
        api_key_env=raw.get("api_key_env"),
        description=raw.get("description", ""),
    )


def load_task(root: Path, task_id: str) -> TaskConfig:
    path = _tasks_dir(root) / f"{task_id}.toml"
    raw = load_toml(path)
    if raw.get("id", task_id) != task_id:
        raise ConfigError(f"{path}: id = {raw['id']!r} phải trùng tên file ({task_id!r})")
    inp = raw.get("input", "prompt")
    if inp not in ("prompt", "generation"):
        raise ConfigError(f"{path}: input phải là 'prompt' hoặc 'generation'")
    if inp == "generation" and not raw.get("parent_task"):
        raise ConfigError(f"{path}: input = 'generation' cần parent_task")
    if "user" not in raw:
        raise ConfigError(f"{path}: thiếu 'user' (mẫu câu hỏi)")
    return TaskConfig(
        id=task_id,
        input=inp,
        user=raw["user"],
        system=raw.get("system", ""),
        parent_task=raw.get("parent_task"),
        params=dict(raw.get("params", {})),
        extract=tuple(raw.get("extract", ())),
        strip_input=bool(raw.get("strip_input", True)),
        description=raw.get("description", ""),
    )


def load_flow(path: Path) -> FlowConfig:
    raw = load_toml(path)
    flow = raw.get("flow", {})
    steps = raw.get("steps", [])
    if not isinstance(steps, list) or not steps:
        raise ConfigError(f"{path}: cần ít nhất một [[steps]]")
    for i, s in enumerate(steps, 1):
        if "stage" not in s:
            raise ConfigError(f"{path}: bước {i} thiếu 'stage'")
    return FlowConfig(
        name=flow.get("name", path.stem),
        db=flow.get("db", "data/slop.sqlite"),
        steps=[dict(s) for s in steps],
        description=flow.get("description", ""),
        path=path,
    )


def effective_params(model: ModelConfig, task: TaskConfig, overrides: dict[str, Any] | None) -> dict[str, Any]:
    """Tham số sinh cuối cùng: mặc định của model < tham số của tác vụ < ghi đè trong luồng."""
    params = {**model.params, **task.params, **(overrides or {})}
    return params


# Tùy chọn Ollama chỉ ảnh hưởng tốc độ / phần cứng, không ảnh hưởng nội dung câu trả lời.
_PERF_ONLY_OPTIONS = {"num_gpu", "num_thread", "num_batch", "main_gpu", "use_mmap", "use_mlock", "low_vram"}


def _identity_extra(extra: dict[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in extra.items() if k not in _NON_IDENTITY_MODEL_KEYS}
    if isinstance(out.get("options"), dict):
        out["options"] = {k: v for k, v in out["options"].items() if k not in _PERF_ONLY_OPTIONS}
    return out


def identity_hash(model: ModelConfig, task: TaskConfig, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Khóa nhận diện một cấu hình sinh. Đổi model, tham số, mẫu câu hỏi -> khóa khác -> gọi lại LLM.

    Tùy chọn chỉ về hiệu năng (số lớp lên GPU, số luồng CPU...) không nằm trong khóa: chỉnh chúng
    giữa chừng không làm mất các câu đã sinh.
    """
    ident = {
        "backend": model.backend,
        "model": model.model,
        "params": params,
        "extra": _identity_extra(model.extra),
        "task": {
            "id": task.id,
            "system": task.system,
            "user": task.user,
            "input": task.input,
            "parent_task": task.parent_task,
            "strip_input": task.strip_input,
        },
    }
    return sha256_hex(canonical_json(ident))[:16], ident
