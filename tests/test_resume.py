"""Chạy dài: chờ khi backend mất kết nối, chạy lại khi lỗi, xem tiến độ."""

from __future__ import annotations

import threading

import pytest

from slopcollect.backends.base import BackendError
from slopcollect.backends.fake import FakeBackend
from slopcollect.cli import main
from slopcollect.pipeline import run_stage
from tests.conftest import PROMPTS

FAST = {"max_attempts": 1, "outage_wait_s": 0.05, "pause_after_failures": 2}


class Flaky:
    """Thay FakeBackend.chat: lỗi tạm thời ở ``fail_calls`` lần gọi đầu tiên (hoặc với câu chứa ``marker``)."""

    def __init__(self, fail_calls: int = 0, marker: str | None = None, transient: bool = True):
        self.fail_calls = fail_calls
        self.marker = marker
        self.transient = transient
        self.calls = 0
        self.lock = threading.Lock()
        self.orig = FakeBackend.chat

    def __call__(self, backend, messages, params, seed):
        with self.lock:
            self.calls += 1
            n = self.calls
        text = "\n".join(m["content"] for m in messages)
        if n <= self.fail_calls or (self.marker and self.marker in text):
            raise BackendError("mất kết nối giả lập", transient=self.transient)
        return self.orig(backend, messages, params, seed)

    def method(self):
        """Hàm gán vào lớp FakeBackend (đối tượng callable không tự gắn thành method)."""
        return lambda backend, messages, params, seed: self(backend, messages, params, seed)


@pytest.fixture
def loaded(ctx):
    run_stage(ctx, "load_prompts", {"source": "jsonl", "path": "fixtures/prompts.jsonl"})
    return ctx


def test_outage_pauses_without_writing_errors(loaded, monkeypatch):
    flaky = Flaky(fail_calls=12)  # nhiều lần lỗi liên tiếp = backend mất kết nối
    monkeypatch.setattr(FakeBackend, "chat", flaky.method())
    res = run_stage(loaded, "generate", {"model": "fake", "task": "spracklen_code_v1", **FAST})
    assert res["ok"] == len(PROMPTS) and res["failed"] == 0
    assert loaded.conn.execute("SELECT COUNT(*) FROM generations WHERE error IS NOT NULL").fetchone()[0] == 0
    assert flaky.calls > len(PROMPTS)


def test_outage_gives_up_after_max_hours(loaded, monkeypatch):
    monkeypatch.setattr(FakeBackend, "chat", Flaky(fail_calls=10**6).method())
    with pytest.raises(RuntimeError, match="mất kết nối"):
        run_stage(loaded, "generate", {"model": "fake", "task": "spracklen_code_v1", **FAST, "max_outage_hours": 0.0001})
    assert loaded.conn.execute("SELECT COUNT(*) FROM generations").fetchone()[0] == 0


def test_single_flaky_prompt_is_recorded_after_requeues(loaded, monkeypatch):
    # Chỉ một câu lỗi tạm thời mãi, các câu khác thành công: không coi là mất kết nối.
    monkeypatch.setattr(FakeBackend, "chat", Flaky(marker="YAML config").method())
    res = run_stage(loaded, "generate", {"model": "fake", "task": "spracklen_code_v1", **FAST, "pause_after_failures": 5, "max_requeues": 2})
    assert res["ok"] == len(PROMPTS) - 1 and res["failed"] == 1
    row = loaded.conn.execute("SELECT error FROM generations WHERE error IS NOT NULL").fetchone()
    assert "mất kết nối giả lập" in row["error"]


def test_out_of_credit_stops_without_recording_errors(root, monkeypatch):
    # Hết tiền (402) sau 4 câu: lưu 4 câu thành công, không ghi lỗi cho câu nào, --keep-going không chạy lại.
    state = {"n": 0}
    lock = threading.Lock()
    orig = FakeBackend.chat

    def chat(backend, messages, params, seed):
        with lock:
            state["n"] += 1
            n = state["n"]
        if n > 4:
            raise BackendError("HTTP 402: You need positive balance", transient=False, fatal=True)
        return orig(backend, messages, params, seed)

    monkeypatch.setattr(FakeBackend, "chat", chat)
    flow = root / "flow.toml"
    flow.write_text(
        '[flow]\nname = "t"\ndb = "data/f.sqlite"\n'
        '[[steps]]\nstage = "load_prompts"\nsource = "jsonl"\npath = "fixtures/prompts.jsonl"\n'
        '[[steps]]\nstage = "generate"\nmodel = "fake"\ntask = "spracklen_code_v1"\nconcurrency = 1\n',
        encoding="utf-8",
    )
    assert main(["--root", str(root), "run", str(flow), "--keep-going", "--retry-wait", "0"]) == 3
    import sqlite3

    c = sqlite3.connect(root / "data/f.sqlite")
    assert c.execute("SELECT COUNT(*) FROM generations WHERE error IS NULL").fetchone()[0] == 4
    assert c.execute("SELECT COUNT(*) FROM generations WHERE error IS NOT NULL").fetchone()[0] == 0
    calls = state["n"]
    # Sau khi nạp tiền: chạy lại hoàn tất phần còn lại.
    monkeypatch.setattr(FakeBackend, "chat", orig)
    assert main(["--root", str(root), "run", str(flow)]) == 0
    assert c.execute("SELECT COUNT(*) FROM generations WHERE error IS NULL").fetchone()[0] == len(PROMPTS)
    assert calls <= 6  # dừng ngay, không bắn thêm hàng loạt request


def test_keep_going_retries_errors_until_done(root, monkeypatch):
    # Lượt 1: một câu lỗi hẳn (không tạm thời). Lượt 2: hết lỗi -> --keep-going chạy lại và xong.
    state = {"pass": 0}
    orig = FakeBackend.chat

    def chat(backend, messages, params, seed):
        text = "\n".join(m["content"] for m in messages)
        if state["pass"] == 0 and "YAML config" in text:
            state["pass"] = 1
            raise BackendError("lỗi một lần", transient=False)
        return orig(backend, messages, params, seed)

    monkeypatch.setattr(FakeBackend, "chat", chat)
    flow = root / "flow.toml"
    flow.write_text(
        '[flow]\nname = "t"\ndb = "data/k.sqlite"\n'
        '[[steps]]\nstage = "load_prompts"\nsource = "jsonl"\npath = "fixtures/prompts.jsonl"\n'
        '[[steps]]\nstage = "generate"\nmodel = "fake"\ntask = "spracklen_code_v1"\n',
        encoding="utf-8",
    )
    assert main(["--root", str(root), "run", str(flow), "--keep-going", "--retry-wait", "0"]) == 0
    import sqlite3

    c = sqlite3.connect(root / "data/k.sqlite")
    assert c.execute("SELECT COUNT(*) FROM generations WHERE error IS NULL").fetchone()[0] == len(PROMPTS)
    assert c.execute("SELECT attempts FROM generations WHERE attempts > 1").fetchone()[0] == 2


def test_status_reports_progress(root, capsys):
    flow = root / "flow.toml"
    flow.write_text(
        '[flow]\nname = "t"\ndb = "data/s.sqlite"\n'
        '[[steps]]\nstage = "load_prompts"\nsource = "jsonl"\npath = "fixtures/prompts.jsonl"\n'
        '[[steps]]\nname = "gen-code"\nstage = "generate"\nmodel = "fake"\ntask = "spracklen_code_v1"\nlimit = 4\n',
        encoding="utf-8",
    )
    assert main(["--root", str(root), "run", str(flow)]) == 0
    flow.write_text(flow.read_text(encoding="utf-8").replace("limit = 4", "limit = 10"), encoding="utf-8")
    capsys.readouterr()
    assert main(["--root", str(root), "status", str(flow)]) == 0
    out = capsys.readouterr().out
    line = next(ln for ln in out.splitlines() if "gen-code" in ln)
    assert line.split()[4:7] == ["10", "4", "6"]  # tổng, xong, còn
