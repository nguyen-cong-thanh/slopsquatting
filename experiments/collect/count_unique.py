"""Đếm tên bịa không trùng (chuẩn hóa PEP 503) và token đã dùng trên các file jsonl của một LLM, để quyết định dừng sớm.
Usage: python count_unique.py own/full_haiku_*.jsonl"""
import sys, json, re
names, n, mods, bad = set(), 0, 0, 0
for p in sys.argv[1:]:
    for l in open(p):
        d = json.loads(l); n += 1; mods += d["module_count"]; bad += d["modulenotfound_count"]
        names |= {re.sub(r"[-_.]+", "-", x).lower() for x in d["modulenotfound"]}
print(f"câu={n} tỷ_lệ_bịa={bad/max(mods,1):.3f} tên_bịa_không_trùng={len(names)} trên_1000_câu={1000*len(names)/max(n,1):.1f}")
