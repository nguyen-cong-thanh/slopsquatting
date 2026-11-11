"""Các bộ trích tên gói từ câu trả lời của LLM.

Ba cách đầu bám theo Spracklen và cộng sự (2025):
  - pip_install: lệnh cài đặt trong câu trả lời (Spracklen chỉ lấy tên đầu tiên sau ``pip install``;
    ở đây lấy đủ mọi tên, bỏ tùy chọn, phiên bản, đường dẫn).
  - llm_list: câu trả lời dạng danh sách gói cách nhau bởi dấu phẩy (cho hai tác vụ hỏi lại
    "cần gói nào để chạy code" và "gói nào hữu ích cho bài toán").
Cách bổ sung:
  - import: đọc lệnh import trong code (ast, lỗi cú pháp thì dùng regex), bỏ thư viện chuẩn, đổi tên
    module sang tên gói bằng bảng của pipreqs. Cách này lẫn cả module cục bộ do LLM tự đặt
    (``utils``, ``config``), nên ghi riêng method để lọc khi phân tích.
  - requirements: khối code giống file requirements.txt.
"""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

_FENCE_RE = re.compile(r"```[ \t]*([A-Za-z0-9_+.-]*)[^\n]*\n(.*?)(?:```|\Z)", re.DOTALL)


def code_blocks(text: str) -> list[tuple[str, str]]:
    """Các khối code ```lang ... ``` (kể cả khối bị cắt cụt ở cuối). Không có khối nào thì coi cả văn bản là code."""
    blocks = [(m.group(1).lower(), m.group(2)) for m in _FENCE_RE.finditer(text)]
    if not blocks and text.strip():
        blocks = [("", text)]
    return blocks


@dataclass(frozen=True)
class Found:
    method: str
    name: str  # tên gói như đã trích (chưa chuẩn hóa)
    raw: str  # đoạn văn bản gốc
    module: str | None = None


# ---------------------------------------------------------------- pip install

_INSTALL_RE = re.compile(
    r"(?:^|(?<=[\s;&|`'\"(!%$]))"
    r"(?P<cmd>(?:python[0-9.]*\s+-m\s+)?(?:uv\s+)?pip[0-9.]*\s+install|uv\s+add|poetry\s+add|pipenv\s+install|pdm\s+add)"
    r"(?P<args>[^\n`;&|#]*)",
    re.IGNORECASE | re.MULTILINE,
)
# Tùy chọn của pip có đối số đi kèm: bỏ luôn token sau.
_OPTS_WITH_VALUE = {
    "-r", "--requirement", "-c", "--constraint", "-e", "--editable", "-i", "--index-url",
    "--extra-index-url", "-f", "--find-links", "-t", "--target", "--prefix", "--root", "--python",
    "--platform", "--trusted-host", "--python-version", "--implementation", "--abi", "--src",
    "--upgrade-strategy", "--group", "-G", "--source", "--proxy", "--cert", "--client-cert",
}
_STOPWORDS = {
    "and", "or", "then", "to", "first", "if", "in", "with", "using", "the", "package", "packages",
    "library", "libraries", "module", "command", "via", "it", "this", "these", "them", "for", "as",
    "is", "are", "you", "your", "also", "by", "on", "from", "run", "running", "e.g.", "i.e.",
}
_SPEC_SPLIT = re.compile(r"\s*(?:===|==|>=|<=|~=|!=|<|>|@|;)")
_NAME_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _clean_requirement(token: str) -> str | None:
    t = token.strip().strip("'\"`,()")
    if not t or t.startswith(("-", ".", "/", "~", "$", "{", "<")):
        return None
    low = t.lower()
    if "://" in t or low.startswith(("git+", "file:")) or low.endswith((".whl", ".tar.gz", ".zip", ".txt", ".toml", ".cfg")):
        return None
    t = _SPEC_SPLIT.split(t, maxsplit=1)[0]
    t = re.sub(r"\[.*?\]$", "", t).strip().rstrip(".:,")
    return t if _NAME_TOKEN.match(t) else None


def find_pip_installs(text: str) -> list[Found]:
    out: list[Found] = []
    for m in _INSTALL_RE.finditer(text):
        args = m.group("args").split()
        skip_next = False
        for tok in args:
            if skip_next:
                skip_next = False
                continue
            if tok.startswith("-"):
                if tok.split("=", 1)[0] in _OPTS_WITH_VALUE and "=" not in tok:
                    skip_next = True
                continue
            word = tok.lower().strip(".,:")
            if word in ("and", "or", "&"):
                continue  # "pip install requests and numpy"
            if word in _STOPWORDS:
                break  # hết phần tên gói trong câu văn
            name = _clean_requirement(tok)
            if name is None:
                # Gặp từ không phải tên gói trong câu văn: dừng lại; trong lệnh (token nhìn như đối số) thì bỏ qua.
                if re.match(r"^[A-Za-z]", tok) and not any(c in tok for c in "/:=<>@[$"):
                    break
                continue
            out.append(Found("pip_install", name, (m.group("cmd") + m.group("args")).strip()))
    return out


# ---------------------------------------------------------------- requirements.txt

_REQ_LINE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*((?:===|==|>=|<=|~=|!=|<|>)\s*[^\s;#]+(?:\s*,\s*(?:===|==|>=|<=|~=|!=|<|>)\s*[^\s;#]+)*)?\s*(;.*)?(#.*)?$")


def find_requirements(text: str) -> list[Found]:
    out: list[Found] = []
    for m in _FENCE_RE.finditer(text):
        lang, body = m.group(1).lower(), m.group(2)
        before = text[max(0, m.start() - 200) : m.start()].lower()
        if lang not in ("", "txt", "text", "requirements", "pip", "plaintext"):
            continue
        if lang not in ("requirements", "pip") and "requirements" not in before:
            continue
        lines = [ln for ln in body.splitlines() if ln.strip() and not ln.strip().startswith("#")]
        if not lines or not all(_REQ_LINE.match(ln) for ln in lines):
            continue
        for ln in lines:
            out.append(Found("requirements", _REQ_LINE.match(ln).group(1), ln.strip()))
    return out


# ---------------------------------------------------------------- import


@lru_cache(maxsize=1)
def _stdlib_modules() -> frozenset[str]:
    names = set(sys.stdlib_module_names) | {"__future__"}
    try:  # gộp mọi phiên bản Python để kết quả không phụ thuộc phiên bản đang chạy
        import stdlib_list  # type: ignore[import-not-found]

        for v in stdlib_list.short_versions:
            names.update(m.split(".")[0] for m in stdlib_list.stdlib_list(v))
    except ImportError:
        pass
    return frozenset(names)


@lru_cache(maxsize=1)
def module_to_package() -> dict[str, str | None]:
    """Bảng module -> gói của pipreqs. Module ứng với nhiều gói khác nhau thì ghi None (không đoán)."""
    text = resources.files("slopcollect.extract").joinpath("data/pipreqs_mapping.txt").read_text(encoding="utf-8")
    seen: dict[str, set[str]] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        mod, pkg = line.strip().split(":", 1)
        seen.setdefault(mod, set()).add(pkg)
    return {m: (next(iter(p)) if len(p) == 1 else None) for m, p in seen.items()}


_IMPORT_RE = re.compile(r"^\s*import\s+([A-Za-z_][\w.]*(?:\s+as\s+\w+)?(?:\s*,\s*[A-Za-z_][\w.]*(?:\s+as\s+\w+)?)*)", re.MULTILINE)
_FROM_RE = re.compile(r"^\s*from\s+([A-Za-z_][\w.]*)\s+import\b", re.MULTILINE)


def _top_modules(code: str) -> list[str]:
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        mods = []
        for m in _IMPORT_RE.finditer(code):
            for part in m.group(1).split(","):
                mods.append(part.split()[0])
        mods += [m.group(1) for m in _FROM_RE.finditer(code)]
        return [m.split(".")[0] for m in mods]
    mods: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods += [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            mods.append(node.module.split(".")[0])
    return mods


def find_imports(text: str) -> list[Found]:
    out: list[Found] = []
    std = _stdlib_modules()
    mapping = module_to_package()
    for lang, code in code_blocks(text):
        if lang not in ("", "python", "py", "python3", "ipython", "jupyter"):
            continue
        for mod in dict.fromkeys(_top_modules(code)):
            if mod in std:
                continue
            pkg = mapping.get(mod) or mod
            out.append(Found("import", pkg, f"import {mod}", module=mod))
    return out


# ---------------------------------------------------------------- llm_list

_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s*")
_DROP = {"none", "nan", "python", "python3", "pip", "n/a"}


def parse_package_list(text: str, *, truncated: bool = False) -> list[Found]:
    """Đọc câu trả lời dạng "pkg1, pkg2, pkg3". Nếu bị cắt do hết max_tokens thì bỏ mục cuối (có thể dở dang)."""
    t = text.replace("```", "\n")
    parts = [p for p in re.split(r"[,\n;]+", t) if p.strip()]
    if truncated and parts:
        parts = parts[:-1]
    out: list[Found] = []
    for p in parts:
        raw = p.strip()
        s = _BULLET.sub("", raw)
        s = s.strip().strip("`'\"*").strip()
        s = re.sub(r"^pip3?\s+install\s+", "", s, flags=re.IGNORECASE)
        s = _SPEC_SPLIT.split(s, maxsplit=1)[0]
        s = re.sub(r"\[.*?\]$", "", s).strip().rstrip(".:")
        if not s or " " in s or s.lower() in _DROP:
            continue
        if not _NAME_TOKEN.match(s):
            continue
        out.append(Found("llm_list", s, raw))
    return out


EXTRACTORS = {
    "pip_install": lambda text, truncated: find_pip_installs(text),
    "requirements": lambda text, truncated: find_requirements(text),
    "import": lambda text, truncated: find_imports(text),
    "llm_list": lambda text, truncated: parse_package_list(text, truncated=truncated),
}
