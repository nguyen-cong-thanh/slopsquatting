"""Bước pypi_samples: lấy các tập tên mẫu trên PyPI không do LLM gợi ý, lưu vào bảng name_samples.

  - pypi_new:    gói phát hành lần đầu trong một khoảng thời gian (theo ClickPy, bảng pypi.projects:
                 mỗi file phát hành một dòng). Dùng làm hồ sơ metadata "gói mới" khi mô phỏng gói của
                 kẻ tấn công, và để đo báo nhầm trên gói thật mới đăng.
  - pypi_random: gói lấy ngẫu nhiên từ snapshot PyPI, để đo báo nhầm trên gói bất kỳ.

Chỉ giữ tên còn trên PyPI ở snapshot mới nhất (gói mới bị gỡ, thường là rác hoặc độc hại, được đếm riêng).
Chọn ngẫu nhiên nhưng cố định theo ``seed``: chạy lại ra cùng một tập.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from slopcollect.db import latest_snapshot
from slopcollect.registry import register
from slopcollect.stages.metadata import _clickpy_query
from slopcollect.util import stable_order_key, utcnow

log = logging.getLogger("slopcollect")


def _store(conn: Any, sample_id: str, rows: list[tuple[str, dict[str, Any]]]) -> None:
    now = utcnow()
    with conn:
        conn.execute("DELETE FROM name_samples WHERE sample_id = ?", (sample_id,))
        conn.executemany(
            "INSERT INTO name_samples(sample_id, norm_name, extra_json, created_at) VALUES (?,?,?,?)",
            [(sample_id, n, json.dumps(extra, ensure_ascii=False), now) for n, extra in rows],
        )


@register("stage", "pypi_samples")
def pypi_samples(
    ctx: Any,
    new_from: str = "2026-08-01",
    new_to: str = "2026-11-01",
    n_new: int = 3000,
    n_random: int = 10000,
    seed: str = "samples-v1",
    new_id: str = "pypi_new",
    random_id: str = "pypi_random",
) -> dict[str, Any]:
    conn = ctx.conn
    sid = latest_snapshot(conn)
    if not sid:
        raise RuntimeError("Chưa có snapshot PyPI: chạy pypi_index trước")
    summary: dict[str, Any] = {"snapshot_id": sid}

    if n_new:
        # Máy chủ giới hạn 10.000 dòng kết quả: lấy mẫu ngẫu nhiên phía máy chủ, gấp đôi số cần để bù tên đã bị gỡ.
        limit = min(9000, n_new * 2)
        rows = _clickpy_query(
            "SELECT n, toString(min(upload_time)) AS first FROM "
            "(SELECT lower(replaceRegexpAll(name, '[-_.]+', '-')) AS n, upload_time FROM pypi.projects) "
            f"GROUP BY n HAVING first >= '{new_from}' AND first < '{new_to}' "
            f"ORDER BY cityHash64(concat(n, '{seed}')) LIMIT {limit}"
        )
        total = _clickpy_query(
            "SELECT count() FROM (SELECT lower(replaceRegexpAll(name, '[-_.]+', '-')) AS n, min(upload_time) AS first "
            f"FROM pypi.projects GROUP BY n HAVING first >= '{new_from}' AND first < '{new_to}')"
        )[0][0]
        present = {
            r[0]
            for r in conn.execute(
                f"SELECT norm_name FROM pypi_index WHERE snapshot_id = ? AND norm_name IN ({','.join('?' * len(rows))})",
                (sid, *[n for n, _ in rows]),
            )
        } if rows else set()
        kept = sorted(((n, first) for n, first in rows if n in present), key=lambda x: stable_order_key(seed, x[0]))[:n_new]
        _store(conn, new_id, [(n, {"first_upload": first, "window": [new_from, new_to]}) for n, first in kept])
        summary[new_id] = {
            "in_window": int(total),
            "fetched": len(rows),
            "removed_from_pypi": len(rows) - len(present),
            "kept": len(kept),
        }

    if n_random:
        names = [r[0] for r in conn.execute("SELECT norm_name FROM pypi_index WHERE snapshot_id = ?", (sid,))]
        chosen = sorted(names, key=lambda n: stable_order_key(seed, n))[:n_random]
        _store(conn, random_id, [(n, {}) for n in chosen])
        summary[random_id] = {"population": len(names), "kept": len(chosen)}
    return summary
