"""Luồng end-to-end offline: model giả, snapshot PyPI giả, danh sách tham chiếu giả, metadata giả."""

from __future__ import annotations

import csv
import json

import pyarrow.parquet as pq
import pytest

from slopcollect.backends.fake import FakeBackend
from slopcollect.cli import main
from slopcollect.config import load_flow
from slopcollect.db import connect, merge_from
from slopcollect.pipeline import Context, run_flow, run_stage
from slopcollect.stages import metadata as metadata_stage
from tests.conftest import PROMPTS, fake_pypi_json, fake_pypistats

TASKS = ("spracklen_code_v1", "spracklen_pkgs_for_code_v1", "spracklen_pkgs_for_prompt_v1")


@pytest.fixture(autouse=True)
def offline_metadata(monkeypatch):
    monkeypatch.setitem(metadata_stage.FETCHERS, "pypi_json", fake_pypi_json)
    monkeypatch.setitem(metadata_stage.FETCHERS, "pypistats", fake_pypistats)
    monkeypatch.setitem(metadata_stage.FETCHERS, "pypi_provenance", lambda n, r, t: (200, {"has_provenance": False}))


FLOW = """
[flow]
name = "test"
db = "data/test.sqlite"

[[steps]]
stage = "load_prompts"
source = "jsonl"
path = "fixtures/prompts.jsonl"

[[steps]]
stage = "generate"
model = "fake"
task = "spracklen_code_v1"
tags = ["spracklen"]

[[steps]]
stage = "generate"
model = "fake"
task = "spracklen_pkgs_for_code_v1"
tags = ["spracklen"]

[[steps]]
stage = "generate"
model = "fake"
task = "spracklen_pkgs_for_prompt_v1"
tags = ["spracklen"]

[[steps]]
stage = "extract"

[[steps]]
stage = "known_lists"
paths = {"0pstech" = "fixtures/0pstech.csv", depscope = "fixtures/depscope.json", datadog = "fixtures/datadog.json", osv_malicious = "fixtures/osv.zip"}

[[steps]]
stage = "pypi_index"
source = "file"
path = "fixtures/simple.json"

[[steps]]
stage = "check"

[[steps]]
stage = "metadata"
sources = ["pypi_json", "pypi_provenance", "pypistats"]
rates = {pypistats = 1000.0}

[[steps]]
stage = "label"
cutoff_date = "2025-06-01"
"""


def run_test_flow(root, ctx):
    path = root / "flow.toml"
    path.write_text(FLOW, encoding="utf-8")
    return run_flow(ctx, load_flow(path))


def test_end_to_end(root, ctx):
    results = run_test_flow(root, ctx)
    conn = ctx.conn
    assert results[0]["new_prompts"] == len(PROMPTS)
    for task in TASKS:
        n = conn.execute("SELECT COUNT(*) FROM generations WHERE task_id = ? AND error IS NULL", (task,)).fetchone()[0]
        assert n == len(PROMPTS)
    # Tác vụ hỏi tiếp gắn đúng câu trả lời cha.
    orphans = conn.execute(
        "SELECT COUNT(*) FROM generations g WHERE task_id = 'spracklen_pkgs_for_code_v1' "
        "AND NOT EXISTS (SELECT 1 FROM generations p WHERE p.gen_id = g.parent_gen_id AND p.task_id = 'spracklen_code_v1')"
    ).fetchone()[0]
    assert orphans == 0

    methods = {r[0] for r in conn.execute("SELECT DISTINCT method FROM mentions")}
    assert {"pip_install", "import", "llm_list"} <= methods
    # Bảng module -> gói: import sklearn ứng với scikit-learn.
    assert conn.execute("SELECT 1 FROM mentions WHERE method = 'import' AND module = 'sklearn' AND norm_name = 'scikit-learn'").fetchone()

    labels = dict(conn.execute("SELECT norm_name, label FROM labels").fetchall())
    mentioned = {r[0] for r in conn.execute("SELECT DISTINCT norm_name FROM mentions")}
    assert set(labels) == mentioned  # chỉ gắn nhãn tên LLM đã gợi ý, không gắn tên chỉ có trong danh sách
    assert labels["requests"] == "real"
    assert labels["scikit-learn"] == "real"
    assert labels["vectorcache"] == "hallucinated_absent"
    assert labels["fastyaml-pro"] == "registered_hallucination"  # có trong 0pstech và còn trên PyPI
    assert labels["pandas-easyio"] == "known_malicious"           # OSV MAL-*
    assert labels["evil-pkg"] == "known_malicious"                # DataDog (dù không còn trên PyPI)
    assert "leftpadx" not in labels and "flask-autodoc-gen" not in labels

    # Mọi tên có trên PyPI đều có lý do "existing" (hoặc stdlib); tên vắng mặt thì đăng ký được hoặc có lý do.
    for r in conn.execute("SELECT * FROM package_status"):
        if r["exists_on_pypi"]:
            assert not r["registrable"] and r["reason"] in ("existing", "stdlib")
        else:
            assert bool(r["registrable"]) == (r["reason"] is None)
    review = list(csv.DictReader(open(root / "data/review/needs_review.csv", encoding="utf-8")))
    assert any(r["norm_name"] == "fastyaml-pro" for r in review)


def test_check_uses_pypi_rules(root, ctx):
    run_stage(ctx, "pypi_index", {"source": "file", "path": "fixtures/simple.json"})
    cases = {
        "vectorcache": (0, 1, None),         # vắng mặt, đăng ký được
        "vect0rcache-2": (0, 0, "similar"),  # ultranormalize trùng "vect0rcache2" đã có
        "torch-ut1lz": (0, 0, "similar"),    # trùng "torch_utilz" sau khi đổi l/i -> 1
        "pyyaml": (1, 0, "existing"),
        "asyncio": (0, 0, "stdlib"),
        "-bad-": (0, 0, "invalid"),
    }
    for i, name in enumerate(cases):
        ctx.conn.execute(
            "INSERT INTO mentions(gen_id, extractor_version, method, norm_name, raw, ultra_name, valid_name) VALUES (?,?,?,?,?,?,?)",
            (f"g{i}", "x1", "llm_list", name, name, name, 1),
        )
    run_stage(ctx, "check", {})
    got = {r["norm_name"]: (r["exists_on_pypi"], r["registrable"], r["reason"]) for r in ctx.conn.execute("SELECT * FROM package_status")}
    assert got == cases


def test_rerun_is_idempotent(root, ctx):
    run_test_flow(root, ctx)
    counts = {t: ctx.conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("prompts", "generations", "mentions", "labels")}
    again = run_test_flow(root, ctx)
    assert all(r.get("todo", 0) == 0 for r in again if "todo" in r)
    assert again[4]["generations"] == 0  # extract: không còn gì mới
    assert counts == {t: ctx.conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in counts}


def test_limit_prefix_is_stable(root, ctx):
    run_stage(ctx, "load_prompts", {"source": "jsonl", "path": "fixtures/prompts.jsonl"})
    first = run_stage(ctx, "generate", {"model": "fake", "task": "spracklen_code_v1", "tags": ["spracklen"], "limit": 4})
    assert first["todo"] == 4
    more = run_stage(ctx, "generate", {"model": "fake", "task": "spracklen_code_v1", "tags": ["spracklen"], "limit": 7})
    assert more["already_done"] == 4 and more["todo"] == 3


def test_param_change_creates_new_generations(root, ctx):
    run_stage(ctx, "load_prompts", {"source": "jsonl", "path": "fixtures/prompts.jsonl"})
    run_stage(ctx, "generate", {"model": "fake", "task": "spracklen_code_v1", "limit": 3})
    other = run_stage(ctx, "generate", {"model": "fake", "task": "spracklen_code_v1", "limit": 3, "params": {"temperature": 0.2}})
    assert other["todo"] == 3


def test_local_model_config_overrides_repo_file(root):
    from slopcollect.config import load_model

    assert load_model(root, "glm53-internal").base_url == "http://localhost:8000/v1"
    local = root / "configs/models/glm53-internal.local.toml"
    local.write_text('backend = "openai_compat"\nmodel = "zai/GLM-5.3"\nbase_url = "http://10.0.0.5:8000/v1"\n', encoding="utf-8")
    m = load_model(root, "glm53-internal")
    assert (m.base_url, m.model, m.key) == ("http://10.0.0.5:8000/v1", "zai/GLM-5.3", "glm53-internal")


def test_perf_options_do_not_change_identity(root):
    from slopcollect.config import identity_hash, load_model, load_task

    model = load_model(root, "qwen35-4b-kali")
    task = load_task(root, "spracklen_code_v1")
    base, _ = identity_hash(model, task, {})
    for change in ({"num_gpu": 99}, {"num_thread": 8}):
        m2 = model.__class__(**{**model.__dict__, "extra": {**model.extra, "options": {**model.extra["options"], **change}}})
        assert identity_hash(m2, task, {})[0] == base
    m3 = model.__class__(**{**model.__dict__, "extra": {**model.extra, "options": {**model.extra["options"], "num_ctx": 4096}}})
    assert identity_hash(m3, task, {})[0] != base


def test_followup_uses_only_current_parent_config(root, ctx):
    run_stage(ctx, "load_prompts", {"source": "jsonl", "path": "fixtures/prompts.jsonl"})
    # Câu trả lời cha của một cấu hình cũ (temperature khác) không được dùng làm đầu vào.
    run_stage(ctx, "generate", {"model": "fake", "task": "spracklen_code_v1", "limit": 3, "params": {"temperature": 0.2}})
    res = run_stage(ctx, "generate", {"model": "fake", "task": "spracklen_pkgs_for_code_v1"})
    assert res["parents"] == 0 and res["todo"] == 0
    run_stage(ctx, "generate", {"model": "fake", "task": "spracklen_code_v1", "limit": 3})
    res = run_stage(ctx, "generate", {"model": "fake", "task": "spracklen_pkgs_for_code_v1"})
    assert res["parents"] == 3 and res["todo"] == 3
    res = run_stage(ctx, "generate", {"model": "fake", "task": "spracklen_pkgs_for_code_v1", "parent_params": {"temperature": 0.2}})
    assert res["parents"] == 3 and res["todo"] == 3


def test_errors_are_stored_and_retried(root, ctx, monkeypatch):
    run_stage(ctx, "load_prompts", {"source": "jsonl", "path": "fixtures/prompts.jsonl"})
    monkeypatch.setattr(FakeBackend, "fail_when_contains", ("YAML config",))
    res = run_stage(ctx, "generate", {"model": "fake", "task": "spracklen_code_v1"})
    assert res["failed"] == 1 and res["ok"] == len(PROMPTS) - 1
    err = ctx.conn.execute("SELECT gen_id, error FROM generations WHERE error IS NOT NULL").fetchone()
    assert "lỗi giả lập" in err["error"]
    monkeypatch.setattr(FakeBackend, "fail_when_contains", ())
    res2 = run_stage(ctx, "generate", {"model": "fake", "task": "spracklen_code_v1"})
    assert res2["todo"] == 1 and res2["ok"] == 1
    row = ctx.conn.execute("SELECT error, attempts, response_text FROM generations WHERE gen_id = ?", (err["gen_id"],)).fetchone()
    assert row["error"] is None and row["attempts"] == 2 and row["response_text"]


def test_merge_two_machines(root, ctx, monkeypatch):
    # Máy A: 6 câu đầu. Máy B: cả 10 câu, nhưng một câu lỗi ở máy A thì máy B thành công.
    run_stage(ctx, "load_prompts", {"source": "jsonl", "path": "fixtures/prompts.jsonl"})
    monkeypatch.setattr(FakeBackend, "fail_when_contains", ("YAML config",))
    run_stage(ctx, "generate", {"model": "fake", "task": "spracklen_code_v1"})
    monkeypatch.setattr(FakeBackend, "fail_when_contains", ())
    other_db = root / "data" / "other.sqlite"
    other = Context(conn=connect(other_db), root=root, db_path=other_db)
    run_stage(other, "load_prompts", {"source": "jsonl", "path": "fixtures/prompts.jsonl"})
    run_stage(other, "generate", {"model": "fake", "task": "spracklen_code_v1", "limit": 6})
    run_stage(other, "generate", {"model": "fake", "task": "spracklen_code_v1"})
    other.conn.close()

    added = merge_from(ctx.conn, other_db)
    assert added["generations"] == 1  # chỉ câu lỗi được thay bằng bản thành công
    assert ctx.conn.execute("SELECT COUNT(*) FROM generations WHERE error IS NOT NULL").fetchone()[0] == 0
    assert ctx.conn.execute("SELECT COUNT(*) FROM generations").fetchone()[0] == len(PROMPTS)
    again = merge_from(ctx.conn, other_db)
    assert sum(again.values()) == 0


def test_variants_select_stats_export(root, ctx):
    run_test_flow(root, ctx)
    sel = run_stage(ctx, "select_variants", {"selection_id": "v1", "n": 3})
    assert sel["selected_names"] == min(3, sel["candidates"]) and sel["selected_names"] > 0
    tag = "sel:v1:fake"
    gen = run_stage(ctx, "generate", {"model": "fake", "task": "spracklen_code_v1", "tags": [tag], "n_samples": 4})
    # Mỗi câu đã có lần hỏi 0, thêm 3 lần.
    assert gen["already_done"] == sel["prompts"] and gen["todo"] == 3 * sel["prompts"]
    run_stage(ctx, "extract", {})
    st = run_stage(ctx, "stats", {"out": "data/exports/stats", "selection_id": "v1"})
    data = json.loads((root / "data/exports/stats.json").read_text(encoding="utf-8"))
    assert data["variants"]["mean_samples"] == 4
    assert data["per_model"]["fake"]["unique_names"] > 0
    assert (root / "data/exports/stats.md").read_text(encoding="utf-8").startswith("# Thống kê")
    assert st["models"] == ["fake"]

    out = run_stage(ctx, "export", {"out_dir": "data/exports/pq"})
    names = pq.read_table(root / "data/exports/pq/dataset_names.parquet").to_pylist()
    assert {"norm_name", "label", "exists_on_pypi", "n_owners"} <= set(names[0])
    assert out["rows"]["dataset_mentions"] == ctx.conn.execute("SELECT COUNT(*) FROM mentions").fetchone()[0]
    csv_out = run_stage(ctx, "export", {"out_dir": "data/exports/csv", "format": "csv", "tables": ["labels"]})
    assert csv_out["rows"]["labels"] > 0


def test_export_prompts_roundtrip(root, ctx):
    run_stage(ctx, "load_prompts", {"source": "jsonl", "path": "fixtures/prompts.jsonl"})
    run_stage(ctx, "export_prompts", {"out": "data/exports/p.jsonl", "tags": ["spracklen:T0"]})
    other_db = root / "data" / "b.sqlite"
    other = Context(conn=connect(other_db), root=root, db_path=other_db)
    res = run_stage(other, "load_prompts", {"source": "jsonl", "path": "data/exports/p.jsonl"})
    assert res["new_prompts"] == 5
    tags = {r[0] for r in other.conn.execute("SELECT DISTINCT tag FROM prompt_tags")}
    assert tags == {"spracklen", "spracklen:T0"}


def test_tampered_prompt_file_is_rejected(root, ctx):
    run_stage(ctx, "load_prompts", {"source": "jsonl", "path": "fixtures/prompts.jsonl"})
    run_stage(ctx, "export_prompts", {"out": "data/exports/p.jsonl"})
    p = root / "data/exports/p.jsonl"
    lines = p.read_text(encoding="utf-8").splitlines()
    obj = json.loads(lines[0])
    obj["text"] += " (edited)"
    lines[0] = json.dumps(obj)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="prompt_id"):
        run_stage(ctx, "load_prompts", {"source": "jsonl", "path": "data/exports/p.jsonl"})


def test_unknown_stage_param_is_reported(root, ctx):
    with pytest.raises(TypeError, match="limt"):
        run_stage(ctx, "generate", {"model": "fake", "task": "spracklen_code_v1", "limt": 3})


def test_cli_run_and_info(root, capsys):
    (root / "flow.toml").write_text(FLOW.split("[[steps]]\nstage = \"extract\"")[0], encoding="utf-8")
    assert main(["--root", str(root), "run", str(root / "flow.toml")]) == 0
    assert main(["--root", str(root), "--db", "data/test.sqlite", "info"]) == 0
    out = capsys.readouterr().out
    assert "generations" in out
    assert main(["--root", str(root), "--db", "data/test.sqlite", "stage", "generate", "model=fake", "task=spracklen_code_v1", "dry_run=true"]) == 0
