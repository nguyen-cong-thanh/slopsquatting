"""Người duyệt thứ hai (R2): tạo phiếu duyệt mù và đo mức đồng ý (quy trình P3, bước 4).

Phiếu gồm hai phần, trộn lẫn và ẩn nhãn của người duyệt thứ nhất (R1):
  - mẫu ngẫu nhiên phân tầng 100 tên (30 real, 30 registered_hallucination, 30 placeholder, 10 uncertain):
    chỉ phần này dùng để tính Cohen's kappa báo cáo trong bài, vì nó đại diện cho toàn bộ dữ liệu;
  - các tên khó (lớp S, D, U/M, tên R1 quyết định khác đề xuất của máy, gói real dưới 40 dòng code):
    dùng để sửa nhãn; tên hai người lệch nhau được bàn để thống nhất.
Phần nào chứa tên nào được ghi ở file khóa riêng (…_key.csv), không gửi cho R2.

  .venv/bin/python -m slopcollect.review.agreement sample              # -> data/review/R2_P3.csv + R2_P3_key.csv
  .venv/bin/python -m slopcollect.review.agreement sample --no-hard    # chỉ mẫu ngẫu nhiên 100 tên
  .venv/bin/python -m slopcollect.review.agreement sample --all        # duyệt kép toàn bộ (cách đang dùng)
  .venv/bin/python -m slopcollect.review.agreement kappa               # sau khi R2 điền r2_label, r2_criterion, r2_note
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from pathlib import Path

LABELS = ("real", "registered_hallucination", "placeholder", "uncertain")
QUOTA = {"real": 30, "registered_hallucination": 30, "placeholder": 30, "uncertain": 10}
HARD_FUNC_MAX = 40  # gói real dưới ngưỡng này (và không có mã khác/biên dịch) được coi là sát ngưỡng
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


def hard_groups(o: dict, e: dict) -> list[str]:
    """Lý do một tên thuộc nhóm khó (rỗng nếu không thuộc)."""
    g = []
    c = o["criterion"]
    if c in ("U", "M"):
        g.append("uncertain")
    if c == "S":
        g.append("S")
    if c == "D":
        g.append("D")
    if c != e.get("proposed_criterion"):
        g.append("khac_de_xuat")
    if (c == "R" and int(e.get("func_lines") or 0) < HARD_FUNC_MAX and int(e.get("other_src_lines") or 0) < 20
            and float(e.get("bin_kb") or 0) < 10):
        g.append("sat_nguong")
    return g


def sample(review_csv: str, overrides_csv: str, out: str, with_hard: bool = True, seed: str = "R2-P3", all_names: bool = False) -> None:
    ev = {r["norm_name"]: r for r in csv.DictReader(open(review_csv, encoding="utf-8"))}
    r1 = {r["norm_name"]: r for r in csv.DictReader(open(overrides_csv, encoding="utf-8")) if r.get("protocol") == "P3"}
    rand: list[str] = []
    for lab, k in QUOTA.items():
        pool = sorted((n for n, r in r1.items() if r["override_label"] == lab and n in ev), key=lambda n: _key(seed, n))
        rand += pool[:k]
    hard = {n: hard_groups(r, ev[n]) for n, r in r1.items() if n in ev} if with_hard else {}
    hard = {n: g for n, g in hard.items() if g}
    if all_names:  # duyệt kép toàn bộ: R2 đọc mọi tên R1 đã đọc
        rand = []
        hard = {n: hard_groups(r, ev[n]) for n, r in r1.items() if n in ev}
    chosen = sorted(set(rand) | set(hard), key=lambda n: _key(seed + "-order", n))  # trộn để không lộ nhóm
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["id", "pypi_url", *EVIDENCE, "r2_label", "r2_criterion", "r2_note"])
        w.writeheader()
        for i, n in enumerate(chosen, 1):
            w.writerow({"id": i, "pypi_url": f"https://pypi.org/project/{n}/", **{c: ev[n].get(c, "") for c in EVIDENCE},
                        "r2_label": "", "r2_criterion": "", "r2_note": ""})
    key = Path(out).with_name(Path(out).stem + "_key.csv")
    with open(key, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "norm_name", "random_sample", "hard_groups"])
        w.writeheader()
        for i, n in enumerate(chosen, 1):
            w.writerow({"id": i, "norm_name": n, "random_sample": int(n in rand), "hard_groups": ";".join(hard.get(n, []))})
    print(f"{len(chosen)} tên -> {out} (ngẫu nhiên {len(rand)}, khó {len(hard)}, trùng {len(set(rand) & set(hard))}); khóa -> {key}")
    print("nhóm khó:", dict(Counter(g for gs in hard.values() for g in gs)))


def cohen_kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def _report(title: str, rows: list[dict], r1: dict[str, str]) -> None:
    if not rows:
        print(f"{title}: chưa có tên nào được điền")
        return
    a = [r1[r["norm_name"]] for r in rows]
    b = [r["r2_label"].strip() for r in rows]
    agree = sum(x == y for x, y in zip(a, b))
    print(f"\n{title}: {len(rows)} tên; đồng ý {agree} ({agree / len(rows):.1%}); Cohen's kappa = {cohen_kappa(a, b):.3f}")
    print("R1 \\ R2".ljust(26) + "".join(lab[:12].rjust(13) for lab in LABELS))
    for x in LABELS:
        print(x.ljust(26) + "".join(str(sum(1 for p, q in zip(a, b) if p == x and q == y)).rjust(13) for y in LABELS))
    print("Lệch nhau:", ", ".join(r["norm_name"] for r, p, q in zip(rows, a, b) if p != q) or "không")


def kappa(r2_csv: str, overrides_csv: str) -> None:
    r1 = {r["norm_name"]: r["override_label"] for r in csv.DictReader(open(overrides_csv, encoding="utf-8"))}
    rows = [r for r in csv.DictReader(open(r2_csv, encoding="utf-8-sig")) if (r.get("r2_label") or "").strip()]
    bad = [r["r2_label"] for r in rows if r["r2_label"].strip() not in LABELS]
    if bad:
        raise SystemExit(f"r2_label không hợp lệ: {sorted(set(bad))} (hợp lệ: {LABELS})")
    key = Path(r2_csv).with_name(Path(r2_csv).stem + "_key.csv")
    if not key.exists():  # phiếu cũ chỉ có mẫu ngẫu nhiên
        _report("Mẫu ngẫu nhiên", rows, r1)
        return
    k = {r["norm_name"]: r for r in csv.DictReader(open(key, encoding="utf-8"))}
    if not any(r["random_sample"] == "1" for r in k.values()):  # phiếu duyệt kép toàn bộ
        _report("Toàn bộ phiếu (duyệt kép)", rows, r1)
        _report("Riêng các tên khó", [r for r in rows if k[r["norm_name"]]["hard_groups"]], r1)
        return
    _report("Mẫu ngẫu nhiên (số liệu báo cáo trong bài)", [r for r in rows if k[r["norm_name"]]["random_sample"] == "1"], r1)
    _report("Nhóm khó (dùng để sửa nhãn, không dùng làm kappa)", [r for r in rows if k[r["norm_name"]]["hard_groups"]], r1)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--review", default="data/review/review_P3.csv")
    s.add_argument("--overrides", default="data/review/overrides.csv")
    s.add_argument("--out", default="data/review/R2_P3.csv")
    s.add_argument("--no-hard", action="store_true", help="chỉ mẫu ngẫu nhiên 100 tên")
    s.add_argument("--all", action="store_true", help="duyệt kép toàn bộ các tên R1 đã đọc")
    k = sub.add_parser("kappa")
    k.add_argument("--r2", default="data/review/R2_P3.csv")
    k.add_argument("--overrides", default="data/review/overrides.csv")
    a = ap.parse_args()
    if a.cmd == "sample":
        sample(a.review, a.overrides, a.out, with_hard=not a.no_hard, all_names=a.all)
    else:
        kappa(a.r2, a.overrides)


if __name__ == "__main__":
    main()
