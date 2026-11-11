"""Bước generate: gửi câu hỏi cho LLM và lưu câu trả lời thô.

- Mỗi lần gọi có khóa gen_id = băm(câu hỏi, câu trả lời cha, model, tác vụ, tham số, lần hỏi),
  nên chạy lại chỉ gọi các câu chưa có (hoặc đã lỗi).
- Chạy song song theo ``concurrency`` của model; ghi CSDL ở luồng chính.
- Ctrl-C: lưu những câu đã xong rồi dừng.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import Any

from slopcollect import registry
from slopcollect.backends.base import ChatResult, is_transient
from slopcollect.config import effective_params, identity_hash
from slopcollect.registry import register
from slopcollect.stages.prompts import select_prompts
from slopcollect.util import canonical_json, retry, sha256_hex, utcnow

log = logging.getLogger("slopcollect")


@dataclass
class _Item:
    gen_id: str
    prompt_id: str
    parent_gen_id: str | None
    sample_idx: int
    seed: int | None
    messages: list[dict[str, str]]


def _seed_for(gen_id: str, mode: str) -> int | None:
    if mode == "none":
        return None
    if mode == "per_sample":
        return int(gen_id[:8], 16) % (2**31 - 1)
    raise ValueError(f"seed_mode không hợp lệ: {mode} (per_sample | none)")


@register("stage", "generate")
def generate(
    ctx: Any,
    model: str,
    task: str,
    tags: list[str] | None = None,
    limit: int | None = None,
    n_samples: int = 1,
    order_seed: str = "slopcollect-v1",
    params: dict[str, Any] | None = None,
    parent_params: dict[str, Any] | None = None,
    concurrency: int | None = None,
    max_attempts: int = 4,
    retry_errors: bool = True,
    progress_every: int = 20,
    dry_run: bool = False,
    pause_after_failures: int = 3,
    outage_wait_s: float = 60.0,
    max_outage_hours: float = 24.0,
    max_requeues: int = 2,
) -> dict[str, Any]:
    """Sinh câu trả lời cho các câu hỏi có tag ``tags`` (tối đa ``limit`` câu), mỗi câu ``n_samples`` lần.

    Mất kết nối backend: khi ``pause_after_failures`` câu liên tiếp lỗi tạm thời (mạng, timeout, 5xx),
    bước này tạm dừng, cứ ``outage_wait_s`` giây thử lại một câu, và KHÔNG ghi lỗi cho câu nào;
    sau ``max_outage_hours`` giờ vẫn không nối lại được thì dừng hẳn. Một câu lẻ lỗi tạm thời được
    đưa lại hàng đợi tối đa ``max_requeues`` lần rồi mới ghi là lỗi (lần chạy sau sẽ thử lại).
    """
    mcfg = ctx.model(model)
    tcfg = ctx.task(task)
    eff = effective_params(mcfg, tcfg, params)
    seed_mode = eff.pop("seed_mode", "per_sample")
    phash, ident = identity_hash(mcfg, tcfg, {**eff, "seed_mode": seed_mode})
    params_json = canonical_json(ident)
    conn = ctx.conn

    prompts = select_prompts(conn, tags, limit=limit, order_seed=order_seed)
    items: list[_Item] = []
    summary_parent: dict[str, Any] = {}
    if tcfg.input == "prompt":
        for p in prompts:
            for s in range(n_samples):
                gid = sha256_hex(p["prompt_id"], "", model, task, phash, str(s))
                items.append(_Item(gid, p["prompt_id"], None, s, _seed_for(gid, seed_mode), tcfg.render(prompt=p["text"], response=None)))
    else:
        # Hỏi tiếp trên câu trả lời của tác vụ cha, cùng model, và chỉ của cấu hình cha hiện hành
        # (đổi tham số tác vụ cha -> câu trả lời cũ không còn được dùng làm đầu vào).
        ptask = ctx.task(tcfg.parent_task)
        pparams = effective_params(mcfg, ptask, parent_params)
        pseed = pparams.pop("seed_mode", "per_sample")
        parent_hash, _ = identity_hash(mcfg, ptask, {**pparams, "seed_mode": pseed})
        texts = {p["prompt_id"]: p["text"] for p in prompts}
        parents = conn.execute(
            "SELECT gen_id, prompt_id, response_text FROM generations "
            "WHERE task_id = ? AND model_key = ? AND params_hash = ? AND error IS NULL AND response_text IS NOT NULL "
            "ORDER BY prompt_id, sample_idx",
            (tcfg.parent_task, model, parent_hash),
        ).fetchall()
        summary_parent = {"parent_params_hash": parent_hash, "parents": len(parents)}
        for par in parents:
            if par["prompt_id"] not in texts:
                continue
            for s in range(n_samples):
                gid = sha256_hex(par["prompt_id"], par["gen_id"], model, task, phash, str(s))
                msgs = tcfg.render(prompt=texts[par["prompt_id"]], response=par["response_text"])
                items.append(_Item(gid, par["prompt_id"], par["gen_id"], s, _seed_for(gid, seed_mode), msgs))

    done = {r[0] for r in conn.execute("SELECT gen_id FROM generations WHERE model_key = ? AND task_id = ? AND error IS NULL", (model, task))}
    errored = {r[0] for r in conn.execute("SELECT gen_id FROM generations WHERE model_key = ? AND task_id = ? AND error IS NOT NULL", (model, task))}
    todo = [it for it in items if it.gen_id not in done and (retry_errors or it.gen_id not in errored)]
    summary: dict[str, Any] = {
        "model": model,
        "task": task,
        "params_hash": phash,
        "prompts_selected": len(prompts),
        "items": len(items),
        "already_done": len(items) - len(todo),
        "todo": len(todo),
        **summary_parent,
    }
    if dry_run or not todo:
        return summary

    backend = registry.get("backend", mcfg.backend)(mcfg)
    workers = concurrency or mcfg.concurrency

    def call(it: _Item) -> tuple[_Item, ChatResult | None, str | None, int, bool]:
        def once() -> ChatResult:
            return backend.chat(it.messages, eff, it.seed)

        try:
            res, attempts = retry(
                once,
                attempts=max_attempts,
                is_transient=is_transient,
                on_retry=lambda i, e: log.warning("thử lại %s (lần %d): %s", it.gen_id[:10], i, e),
            )
            return it, res, None, attempts, False
        except Exception as e:  # noqa: BLE001 - mọi lỗi đều ghi lại để chạy lại sau
            transient = is_transient(e)
            return it, None, f"{type(e).__name__}: {e}", max_attempts if transient else 1, transient

    ok = failed = 0
    tok_out = lat = 0
    t_start = time.monotonic()
    now_host = ctx.host

    def write(it: _Item, res: ChatResult | None, err: str | None, attempts: int) -> None:
        conn.execute(
            "INSERT INTO generations(gen_id, prompt_id, parent_gen_id, task_id, model_key, backend, model_name, params_json, "
            "params_hash, sample_idx, seed, response_text, reasoning_text, finish_reason, tokens_in, tokens_out, latency_ms, "
            "error, attempts, host, run_id, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(gen_id) DO UPDATE SET response_text = excluded.response_text, reasoning_text = excluded.reasoning_text, "
            "finish_reason = excluded.finish_reason, tokens_in = excluded.tokens_in, tokens_out = excluded.tokens_out, "
            "latency_ms = excluded.latency_ms, error = excluded.error, attempts = generations.attempts + excluded.attempts, "
            "host = excluded.host, run_id = excluded.run_id, created_at = excluded.created_at "
            "WHERE generations.error IS NOT NULL",
            (
                it.gen_id,
                it.prompt_id,
                it.parent_gen_id,
                task,
                model,
                mcfg.backend,
                mcfg.model,
                params_json,
                phash,
                it.sample_idx,
                it.seed,
                res.text if res else None,
                res.reasoning if res else None,
                res.finish_reason if res else None,
                res.tokens_in if res else None,
                res.tokens_out if res else None,
                res.latency_ms if res else None,
                err,
                attempts,
                now_host,
                ctx.run_id,
                utcnow(),
            ),
        )

    def progress() -> None:
        n = ok + failed
        elapsed = time.monotonic() - t_start
        rate = n / elapsed if elapsed else 0.0
        eta_min = (len(todo) - n) / rate / 60 if rate else float("inf")
        tps = tok_out / (lat / 1000) if lat else 0.0
        log.info(
            "%s/%s: %d/%d xong (%d lỗi) · %.1f câu/phút · %.1f token/s · còn ~%.0f phút",
            model,
            task,
            n,
            len(todo),
            failed,
            rate * 60,
            tps,
            eta_min,
        )

    pending: set[Future] = set()
    queue = deque(todo)
    interrupted = False
    commit_every_s = 15.0
    last_commit = time.monotonic()
    requeues: dict[str, int] = {}
    consecutive_transient = 0
    outage_since: float | None = None  # thời điểm bắt đầu mất kết nối
    paused_until = 0.0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        try:
            while queue or pending:
                now = time.monotonic()
                # Khi mất kết nối: chỉ gửi một câu để thăm dò, sau mỗi khoảng chờ.
                cap = 1 if outage_since is not None else workers * 2
                if now >= paused_until:
                    while queue and len(pending) < cap:
                        pending.add(pool.submit(call, queue.popleft()))
                if not pending:
                    time.sleep(min(5.0, max(0.05, paused_until - now)))
                    continue
                finished, pending = wait(pending, timeout=5, return_when=FIRST_COMPLETED)
                for fut in finished:
                    it, res, err, attempts, transient = fut.result()
                    if err and transient:
                        consecutive_transient += 1
                        in_outage = outage_since is not None or consecutive_transient >= pause_after_failures
                        if in_outage or requeues.get(it.gen_id, 0) < max_requeues:
                            if not in_outage:
                                requeues[it.gen_id] = requeues.get(it.gen_id, 0) + 1
                            queue.appendleft(it)
                            if in_outage:
                                t = time.monotonic()
                                if outage_since is None:
                                    outage_since = t
                                    conn.commit()
                                    log.warning("Backend không phản hồi (%s). Tạm dừng, thử lại mỗi %.0f giây; không ghi lỗi.", err[:200], outage_wait_s)
                                elif t - outage_since > max_outage_hours * 3600:
                                    raise RuntimeError(f"Backend mất kết nối hơn {max_outage_hours} giờ: {err[:200]}")
                                paused_until = t + outage_wait_s
                            continue
                    elif not err:
                        consecutive_transient = 0
                        if outage_since is not None:
                            log.info("Backend đã trả lời lại sau %.0f phút mất kết nối.", (time.monotonic() - outage_since) / 60)
                            outage_since = None
                            paused_until = 0.0
                    write(it, res, err, attempts)
                    if err:
                        failed += 1
                        log.warning("lỗi %s: %s", it.gen_id[:10], err[:300])
                    else:
                        ok += 1
                        tok_out += res.tokens_out or 0
                        lat += res.latency_ms or 0
                    if (ok + failed) % progress_every == 0:
                        progress()
                    # Ghi CSDL theo thời gian (không phụ thuộc progress_every) để dừng đột ngột không mất nhiều.
                    if time.monotonic() - last_commit >= commit_every_s:
                        conn.commit()
                        last_commit = time.monotonic()
        except KeyboardInterrupt:
            interrupted = True
            log.warning("Dừng theo yêu cầu: lưu %d câu đã xong, hủy các câu đang chờ.", ok + failed)
            queue.clear()
            for fut in pending:
                fut.cancel()
            pool.shutdown(wait=False, cancel_futures=True)
        finally:
            conn.commit()
    if (ok + failed) % progress_every:
        progress()
    summary.update({"ok": ok, "failed": failed, "elapsed_s": round(time.monotonic() - t_start, 1)})
    if interrupted:
        raise KeyboardInterrupt
    return summary
