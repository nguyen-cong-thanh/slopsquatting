from __future__ import annotations

import io
import json
import shutil
import zipfile
from pathlib import Path

import pytest

from slopcollect.db import connect
from slopcollect.pipeline import Context
from slopcollect.util import sha256_hex

REPO = Path(__file__).resolve().parents[1]

PROMPTS = [
    "How do I download a web page and parse the HTML?",
    "Read a CSV file and plot a histogram of one column.",
    "Train a classifier on the iris dataset.",
    "Build a small REST API with two endpoints.",
    "Load a YAML config file and validate it.",
    "Generate Python code that caches vectors for similarity search.",
    "Parse command line arguments and print them.",
    "Scrape a table from a website into a dataframe.",
    "Compute summary statistics of a numpy array.",
    "Write unit tests for a function that adds numbers.",
]

PYPI_NAMES = [
    "requests", "numpy", "pandas", "Flask", "scikit-learn", "matplotlib", "beautifulsoup4", "PyYAML",
    "fastyaml-pro",  # tên bịa đã có người đăng ký (giả lập)
    "torch_utilz",   # để kiểm tra luật "quá giống": torch-utilzz không trùng ultranormalize với tên này
    "vect0rcache2",
]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """Thư mục gốc tạm: bản sao configs/ của repo + dữ liệu giả."""
    shutil.copytree(REPO / "configs", tmp_path / "configs")
    # Model giả của test: mỗi câu trả lời đều có một tên bịa, gồm cả tên có trong danh sách tham chiếu.
    (tmp_path / "configs/models/fake.toml").write_text(
        'backend = "fake"\nmodel = "fake-1"\nconcurrency = 4\n[params]\nseed_mode = "per_sample"\n'
        '[extra]\nhallucination_rate = 1.0\n'
        'fake_names = ["vectorcache", "fastyaml-pro", "pandas-easyio", "evil-pkg"]\n',
        encoding="utf-8",
    )
    fx = tmp_path / "fixtures"
    fx.mkdir()
    with open(fx / "prompts.jsonl", "w", encoding="utf-8") as f:
        for i, p in enumerate(PROMPTS):
            f.write(json.dumps({"text": p, "tags": ["spracklen", f"spracklen:T{i % 2}"]}) + "\n")
    (fx / "simple.json").write_text(
        json.dumps({"meta": {"api-version": "1.4", "_last-serial": 1}, "projects": [{"name": n} for n in PYPI_NAMES]}),
        encoding="utf-8",
    )
    (fx / "0pstech.csv").write_text(
        "id,ecosystem,name,purl,risk,registry_status,built_from,models,tasks,first_seen,url\n"
        "A,PyPI,fastyaml-pro,,high,young,,m,t,2026-01-01,u\n"
        "B,npm,leftpadx,,high,nonexistent,,m,t,2026-01-01,u\n",
        encoding="utf-8",
    )
    (fx / "depscope.json").write_text(
        json.dumps({"entries": [{"ecosystem": "pypi", "package_name": "flask-autodoc-gen", "source": "observed"}]}),
        encoding="utf-8",
    )
    (fx / "datadog.json").write_text(json.dumps({"evil-pkg": None}), encoding="utf-8")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("MAL-2026-1.json", json.dumps({"id": "MAL-2026-1", "affected": [{"package": {"ecosystem": "PyPI", "name": "Pandas_EasyIO"}}]}))
        zf.writestr("PYSEC-1.json", json.dumps({"id": "PYSEC-1", "affected": [{"package": {"ecosystem": "PyPI", "name": "requests"}}]}))
    (fx / "osv.zip").write_bytes(buf.getvalue())
    return tmp_path


@pytest.fixture
def ctx(root: Path) -> Context:
    db = root / "data" / "test.sqlite"
    return Context(conn=connect(db), root=root, db_path=db)


def fake_pypi_json(name: str, raws: dict, token: str | None) -> tuple[int, dict]:
    """Thay cho API PyPI trong test: fastyaml-pro mới đăng, ít người duy trì; còn lại là gói lâu năm."""
    young = name == "fastyaml-pro"
    t = "2026-10-01T00:00:00Z" if young else "2015-01-01T00:00:00Z"
    return 200, {
        "info": {
            "name": name,
            "summary": "Fast YAML" if young else f"The {name} package",
            "description": "",
            "project_urls": {"Source": f"https://github.com/example/{name}"},
        },
        "releases": {"1.0": [{"upload_time_iso_8601": t, "yanked": False}]},
        "ownership": {"roles": [{"user": "x", "role": "Owner"}], "organization": None},
    }


def fake_pypistats(name: str, raws: dict, token: str | None) -> tuple[int, dict]:
    return 200, {"data": {"last_month": 10 if name == "fastyaml-pro" else 1_000_000}}


def prompt_id(text: str) -> str:
    return sha256_hex(text)
