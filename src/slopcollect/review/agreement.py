"""Mẫu cho người duyệt thứ hai và đo mức đồng ý (quy trình P3, bước 4).

  # Tạo mẫu phân tầng ~100 tên, ẩn nhãn của người duyệt thứ nhất:
  .venv/bin/python -m slopcollect.review.agreement sample --out data/review/R2_sample_P3.csv
  # Sau khi người thứ hai điền cột r2_label (và r2_criterion, r2_note):
  .venv/bin/python -m slopcollect.review.agreement kappa --r2 data/review/R2_sample_P3.csv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from pathlib import Path

LABELS = ("real", "registered_hallucination", "placeholder", "uncertain")
QUOTA = {"real": 30, "registered_hallucination": 30, "placeholder": 30, "uncertain": 10}
# Cột bằng chứng đưa cho người thứ hai (không có nhãn, mã tiêu chí, ghi chú hay nhãn cũ của người thứ nhất).
EVIDENCE = [
    "norm_name", "models", "earliest_cutoff", "latest_cutoff", "first_upload", "exists_by", "after_cutoff", "pre_registration_models",
    "released_before_upload", "pypi_api",
    "summary", "desc_len", "desc_head", "version", "n_releases", "n_files", "n_deps", "downloads_30d", "n_owners",
    "has_org", "author", "home", "github", "github_stars", "repo_verified", "defensive_hint", "defensive_weak",
    "content", "file", "file_kb", "py_files", "func_lines", "other_src_lines", "bin_kb", "n_vendored", "outline",
]


def _key(seed: str, name: str) -> str:
    return hashlib.sha256(f"{seed}|{name}".encode()).hexdigest()


def sample(review_csv: str, overrides_csv: str, out: str, seed: str = "R2-P3") -> None:
    ev = {r["norm_name"]: r for r in csv.DictReader(open(review_csv, encoding="utf-8"))}
    r1 = {r["norm_name"]: r for r in csv.DictReader(open(overrides_csv, encoding="utf-8")) if r.get("protocol") == "P3"}
    chosen: list[str] = []
    for lab, k in QUOTA.items():
        pool = sorted((n for n, r in r1.items() if r["override_label"] == lab and n in ev), key=lambda n: _key(seed, n))
        chosen += pool[:k]
    chosen.sort(key=lambda n: _key(seed + "-order", n))  # trộn thứ tự để không lộ nhãn theo nhóm
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["id", "pypi_url", *EVIDENCE, "r2_label", "r2_criterion", "r2_note"])
        w.writeheader()
        for i, n in enumerate(chosen, 1):
            w.writerow({"id": i, "pypi_url": f"https://pypi.org/project/{n}/", **{c: ev[n].get(c, "") for c in EVIDENCE},
                        "r2_label": "", "r2_criterion": "", "r2_note": ""})
    print(f"{len(chosen)} tên -> {out}; phân bố nhãn R1 (ẩn trong file): {dict(Counter(r1[n]['override_label'] for n in chosen))}")


def cohen_kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def kappa(r2_csv: str, overrides_csv: str) -> None:
    r1 = {r["norm_name"]: r["override_label"] for r in csv.DictReader(open(overrides_csv, encoding="utf-8"))}
    rows = [r for r in csv.DictReader(open(r2_csv, encoding="utf-8-sig")) if (r.get("r2_label") or "").strip()]
    bad = [r["r2_label"] for r in rows if r["r2_label"].strip() not in LABELS]
    if bad:
        raise SystemExit(f"r2_label không hợp lệ: {sorted(set(bad))} (hợp lệ: {LABELS})")
    a = [r1[r["norm_name"]] for r in rows]
    b = [r["r2_label"].strip() for r in rows]
    agree = sum(x == y for x, y in zip(a, b))
    print(f"{len(rows)} tên có nhãn R2; đồng ý {agree} ({agree / len(rows):.1%}); Cohen's kappa = {cohen_kappa(a, b):.3f}")
    print("Bảng chéo (hàng R1, cột R2):")
    print("R1 \\ R2".ljust(26) + "".join(l[:12].rjust(13) for l in LABELS))
    for x in LABELS:
        print(x.ljust(26) + "".join(str(sum(1 for p, q in zip(a, b) if p == x and q == y)).rjust(13) for y in LABELS))
    print("Lệch nhau:", ", ".join(r["norm_name"] for r, p, q in zip(rows, a, b) if p != q) or "không")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--review", default="data/review/review_P3.csv")
    s.add_argument("--overrides", default="data/review/overrides.csv")
    s.add_argument("--out", default="data/review/R2_sample_P3.csv")
    k = sub.add_parser("kappa")
    k.add_argument("--r2", default="data/review/R2_sample_P3.csv")
    k.add_argument("--overrides", default="data/review/overrides.csv")
    a = ap.parse_args()
    if a.cmd == "sample":
        sample(a.review, a.overrides, a.out)
    else:
        kappa(a.r2, a.overrides)


if __name__ == "__main__":
    main()
