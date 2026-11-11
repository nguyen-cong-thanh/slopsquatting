from __future__ import annotations

from slopcollect.extract.parsers import (
    code_blocks,
    find_imports,
    find_pip_installs,
    find_requirements,
    module_to_package,
    parse_package_list,
)


def names(found):
    return [f.name for f in found]


def test_pip_install_variants():
    text = """
To run this you need:
```bash
pip install requests numpy==1.26 "pandas>=2" scikit-learn[alldeps] -U
python -m pip install --upgrade flask
pip3 install -r requirements.txt fastyaml
!pip install vectorcache
uv pip install torch-utilzz
poetry add httpx
```
You can also pip install beautifulsoup4 and lxml first.
"""
    assert names(find_pip_installs(text)) == [
        "requests", "numpy", "pandas", "scikit-learn", "flask", "fastyaml", "vectorcache", "torch-utilzz", "httpx",
        "beautifulsoup4", "lxml",
    ]


def test_pip_install_stops_at_parenthetical_note():
    text = "pip install djangorestframework (Note: Usually it's django-extensions)"
    assert names(find_pip_installs(text)) == ["djangorestframework"]
    assert names(find_pip_installs("pip install foo bar. Note: restart the server")) == ["foo", "bar"]


def test_imports_extra_mapping_and_namespaces():
    text = """```python
import aws_cdk as cdk
from mpl_toolkits.mplot3d import Axes3D
import win32com.client
from google.oauth2 import service_account
from google.cloud import storage, bigquery
from google import genai
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential
import google_auth2
```"""
    assert [f.name for f in find_imports(text)] == [
        "aws-cdk-lib", "matplotlib", "pywin32", "google-auth", "google-cloud-storage", "google-cloud-bigquery",
        "google-genai", "azure-storage-blob", "azure-identity", "google_auth2",
    ]


def test_pip_install_skips_paths_urls_and_editable():
    text = "pip install -e . git+https://github.com/a/b.git ./local_pkg dist/x-1.0-py3-none-any.whl realpkg"
    assert names(find_pip_installs(text)) == ["realpkg"]


def test_pip_install_inline_code():
    assert names(find_pip_installs("Run `pip install pyyaml` then import yaml.")) == ["pyyaml"]


def test_requirements_block():
    text = "Create requirements.txt:\n```\nrequests==2.31.0\nnumpy>=1.20\n# comment\nfastapi[all]\n```\n"
    assert names(find_requirements(text)) == ["requests", "numpy", "fastapi"]


def test_requirements_ignores_python_block():
    text = "requirements:\n```python\nimport os\n```"
    assert find_requirements(text) == []


def test_imports_ast_stdlib_and_mapping():
    text = """```python
import os, sys
import numpy as np
from sklearn.model_selection import train_test_split
from . import local
from bs4 import BeautifulSoup
import yaml
import vectorcache.core
```"""
    found = find_imports(text)
    assert [(f.module, f.name) for f in found] == [
        ("numpy", "numpy"),
        ("sklearn", "scikit_learn"),
        ("bs4", "beautifulsoup4"),
        ("yaml", "PyYAML"),
        ("vectorcache", "vectorcache"),
    ]


def test_imports_regex_fallback_on_syntax_error():
    text = "```python\nimport requests\nfrom flask import Flask\ndef broken(:\n```"
    assert [f.module for f in find_imports(text)] == ["requests", "flask"]


def test_imports_skip_non_python_blocks():
    assert find_imports("```bash\nimport something\n```") == []


def test_ambiguous_module_mapping_is_not_guessed():
    mapping = module_to_package()
    ambiguous = [m for m, p in mapping.items() if p is None]
    assert ambiguous, "bảng pipreqs có module trỏ tới nhiều gói"
    mod = ambiguous[0]
    assert [f.name for f in find_imports(f"import {mod}")] == [mod]


def test_code_blocks_unterminated_and_plain():
    assert code_blocks("```python\nimport x\n") == [("python", "import x\n")]
    assert code_blocks("import x") == [("", "import x")]


def test_llm_list_formats():
    assert names(parse_package_list("numpy, pandas, scikit-learn")) == ["numpy", "pandas", "scikit-learn"]
    assert names(parse_package_list("1. numpy\n2. `pandas`\n- requests>=2.0\n* fastapi[all]")) == [
        "numpy", "pandas", "requests", "fastapi",
    ]
    assert names(parse_package_list("None")) == []
    assert names(parse_package_list("python, os module, pip install requests")) == ["requests"]


def test_llm_list_truncated_drops_last_item():
    assert names(parse_package_list("numpy, pandas, scik", truncated=True)) == ["numpy", "pandas"]
    assert names(parse_package_list("numpy, pandas, scik", truncated=False)) == ["numpy", "pandas", "scik"]
