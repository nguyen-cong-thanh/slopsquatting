"""Số liệu của quy trình gán nhãn (P3) cho bài báo: số nhãn, mã tiêu chí, độ nhạy của nhãn S theo mốc dữ liệu.

  .venv/bin/python -m slopcollect.review.summary
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from collections import Counter
from datetime import datetime, timezone

from slopcollect.stages.label import LABELER_VERSION
from slopcollect.timing import load_cutoffs, released_before, timing

MARGINS = (30, 90, 180, 365, 730)


def _d(s: str) -> datetime | None:
    return datetime.fromisoformat(s[:10]).replace(tzinfo=timezone.utc) if s and s[:4].isdigit() else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/slop.sqlite")
    ap.add_argument("--cutoffs", default="configs/cutoffs.toml")
    ap.add_argument("--overrides", default="data/review/overrides.csv")
    ap.add_argument("--review", default="data/review/review_P3.csv")
    a = ap.parse_args()

    conn = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    labels = Counter(r[0] for r in conn.execute("SELECT label FROM labels WHERE labeler_version = ?", (LABELER_VERSION,)))
    pending = conn.execute("SELECT COUNT(*) FROM labels WHERE labeler_version = ? AND needs_review = 1", (LABELER_VERSION,)).fetchone()[0]
    conn.close()
    ov = list(csv.DictReader(open(a.overrides, encoding="utf-8")))
    ev = {r["norm_name"]: r for r in csv.DictReader(open(a.review, encoding="utf-8"))}
    cut = load_cutoffs(a.cutoffs)

    print(f"Tổng số tên: {sum(labels.values())}; còn chờ duyệt: {pending}")
    for k, v in labels.most_common():
        print(f"  {k:26s} {v}")
    print(f"\nĐã duyệt (overrides): {len(ov)}; theo cách duyệt: {dict(Counter(r.get('review_mode', '') for r in ov))}")
    print("Mã tiêu chí:", dict(Counter(r.get("criterion", "") for r in ov).most_common()))

    s_names = [r["norm_name"] for r in ov if r["override_label"] == "registered_hallucination"]
    print(f"\nNhãn S (registered_hallucination): {len(s_names)}")
    rows = [(n, _d(ev[n]["first_upload"]), ev[n]["models"].split(";")) for n in s_names if n in ev]
    sure = [n for n, first, ms in rows if released_before(first, ms, cut)]
    print(f"  đăng ký sau ngày PHÁT HÀNH của ít nhất một model đã gợi ý (chắc chắn): {len(sure)}")
    print("  độ nhạy theo khoảng đệm sau mốc dữ liệu (số tên vẫn có kết luận 'after'):")
    for m in MARGINS:
        k = sum(1 for _, first, ms in rows if timing(first, ms, cut, margin_days=m)[0] == "after")
        print(f"    {m:4d} ngày: {k}")


if __name__ == "__main__":
    main()
