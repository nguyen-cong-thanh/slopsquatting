"""Đếm dòng code chức năng và cây quyết định của quy trình gán nhãn (P3)."""

import io
import zipfile

from slopcollect.review.evidence import analyse_archive, functional_lines, propose


def test_functional_lines_excludes_imports_docstrings_dunders():
    src = '"""Doc."""\nimport os\nfrom x import y\n__version__ = "1"\n__all__ = ["a"]\n'
    assert functional_lines(src) == 0


def test_functional_lines_counts_compound_and_multiline():
    src = (
        "class A:\n"
        '    """doc"""\n'
        "    x = 1\n"
        "    def f(self):\n"
        "        # comment\n"
        "        return self.x\n"
        "\n"
        "try:\n"
        "    import y\n"
        "except ImportError:\n"
        "    y = None\n"
        "d = {\n"
        "    'a': 1,\n"
        "}\n"
    )
    # class, x = 1, def, return, try, y = None, và 3 dòng của d = {...}
    assert functional_lines(src) == 9


def test_functional_lines_syntax_error_fallback():
    assert functional_lines("def f(:\n  # c\n  return 1\n") == 2


def _wheel(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for p, s in files.items():
            z.writestr(p, s)
    return buf.getvalue()


def test_analyse_archive_skips_tests_and_setup():
    data = _wheel({
        "pkg/__init__.py": "x = 1\n",
        "pkg/tests/test_a.py": "\n".join(f"a{i} = {i}" for i in range(50)),
        "setup.py": "\n".join(f"b{i} = {i}" for i in range(50)),
        "pkg/web/app.js": "// c\nconst a = 1;\nconst b = 2;\n",
        "venv/lib/python3.11/site-packages/x/core.py": "\n".join(f"c{i} = {i}" for i in range(50)),
    })
    r = analyse_archive("pkg-1.0-py3-none-any.whl", data)
    assert r["func_lines"] == 1
    assert r["other_src_lines"] == 2
    assert r["n_vendored"] == 1


def _row(**kw):
    base = {"content": "ok", "func_lines": 0, "other_src_lines": 0, "bin_kb": 0, "after_cutoff": "yes",
            "defensive_hint": "", "old_override": "", "current_label": "registered_hallucination"}
    base.update(kw)
    return base


def test_propose_tree():
    assert propose(_row(func_lines=25))[:2] == ("real", "R")
    assert propose(_row(func_lines=3))[:2] == ("registered_hallucination", "S")
    assert propose(_row(func_lines=3, after_cutoff="no"))[:2] == ("placeholder", "E")
    assert propose(_row(content="api_404", after_cutoff=""))[:2] == ("uncertain", "U")
    assert propose(_row(func_lines=2, defensive_hint="use yara-python instead"))[:2] == ("placeholder", "D")
    # Gói có code chức năng mà có lời trỏ sang gói khác: vẫn đề xuất real, nhưng bắt người duyệt xem.
    lab, crit, eyes = propose(_row(func_lines=200, defensive_hint="moved to"))
    assert (lab, crit) == ("real", "R") and any("phòng vệ" in e for e in eyes)


def test_cohen_kappa():
    from slopcollect.review.agreement import cohen_kappa

    assert cohen_kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"]) == 1.0
    # đồng ý 50%, mỗi người chia đều hai nhãn: kappa = 0
    assert abs(cohen_kappa(["a", "a", "b", "b"], ["a", "b", "a", "b"])) < 1e-9
