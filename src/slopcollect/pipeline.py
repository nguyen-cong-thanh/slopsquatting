"""Chạy luồng: mỗi bước là một plugin ``stage``, nhận Context và tham số từ file TOML."""

from __future__ import annotations

import inspect
import json
import logging
import socket
import sqlite3
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from slopcollect import __version__, registry
from slopcollect.config import FlowConfig, ModelConfig, TaskConfig, load_model, load_task
from slopcollect.util import canonical_json, sha256_hex, utcnow

log = logging.getLogger("slopcollect")


@dataclass
class Context:
    conn: sqlite3.Connection
    root: Path
    db_path: Path
    run_id: str = ""
    flow: str | None = None
    host: str = field(default_factory=socket.gethostname)
    _models: dict[str, ModelConfig] = field(default_factory=dict)
    _tasks: dict[str, TaskConfig] = field(default_factory=dict)

    def path(self, p: str | Path) -> Path:
        q = Path(p)
        return q if q.is_absolute() else self.root / q

    def model(self, key: str) -> ModelConfig:
        if key not in self._models:
            self._models[key] = load_model(self.root, key)
        return self._models[key]

    def task(self, task_id: str) -> TaskConfig:
        if task_id not in self._tasks:
            self._tasks[task_id] = load_task(self.root, task_id)
        return self._tasks[task_id]


def code_version(root: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode == 0 and out.stdout.strip():
            dirty = subprocess.run(
                ["git", "-C", str(root), "status", "--porcelain", "--", "src", "configs", "flows"],
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout.strip()
            return f"{out.stdout.strip()}{'+dirty' if dirty else ''} ({__version__})"
    except (OSError, subprocess.SubprocessError):
        pass
    return __version__


def _check_params(name: str, fn: Any, params: dict[str, Any]) -> None:
    sig = inspect.signature(fn)
    if any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values()):
        return
    allowed = [p for p in sig.parameters if p != "ctx"]
    unknown = sorted(set(params) - set(allowed))
    if unknown:
        raise TypeError(f"Bước '{name}' không có tham số {unknown}. Tham số hợp lệ: {allowed}")


def run_stage(
    ctx: Context,
    stage: str,
    params: dict[str, Any],
    *,
    step_index: int | None = None,
) -> dict[str, Any]:
    fn = registry.get("stage", stage)
    _check_params(stage, fn, params)
    run_id = f"{utcnow().replace(':', '').replace('-', '')[:15]}-{uuid.uuid4().hex[:6]}"
    ctx.run_id = run_id
    params_json = canonical_json(params)
    ctx.conn.execute(
        "INSERT INTO runs(run_id, flow, step_index, stage, params_json, config_hash, host, code_version, started_at, status) "
        "VALUES (?,?,?,?,?,?,?,?,?, 'running')",
        (
            run_id,
            ctx.flow,
            step_index,
            stage,
            params_json,
            sha256_hex(stage, params_json)[:16],
            ctx.host,
            code_version(ctx.root),
            utcnow(),
        ),
    )
    ctx.conn.commit()
    log.info("▶ bước %s%s %s", f"{step_index}. " if step_index else "", stage, params_json)
    status = "failed"
    summary: dict[str, Any] = {}
    try:
        summary = fn(ctx, **params) or {}
        status = "ok"
        return summary
    except KeyboardInterrupt:
        status = "interrupted"
        raise
    finally:
        ctx.conn.commit()
        ctx.conn.execute(
            "UPDATE runs SET finished_at = ?, status = ?, summary_json = ? WHERE run_id = ?",
            (utcnow(), status, json.dumps(summary, ensure_ascii=False, default=str), run_id),
        )
        ctx.conn.commit()
        if status == "ok":
            log.info("✔ %s: %s", stage, json.dumps(summary, ensure_ascii=False, default=str))


def run_flow(
    ctx: Context,
    flow: FlowConfig,
    *,
    only: list[str] | None = None,
    skip: list[str] | None = None,
) -> list[dict[str, Any]]:
    ctx.flow = flow.name
    results = []
    for i, step in enumerate(flow.steps, 1):
        params = {k: v for k, v in step.items() if k not in ("stage", "name")}
        name = step.get("name", step["stage"])
        selectors = {name, step["stage"], str(i)}
        if only and not selectors & set(only):
            continue
        if skip and selectors & set(skip):
            continue
        results.append(run_stage(ctx, step["stage"], params, step_index=i))
    return results
