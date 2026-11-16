"""Gộp bộ câu hỏi Python của Spracklen và cộng sự (SO_*.json, LLM_*.json), bỏ trùng -> prompts.txt (một câu/dòng)."""
import json, sys, glob, re
d = sys.argv[1]  # .../PackageHallucination/Data/Python
seen, out = set(), []
for p in sorted(glob.glob(f"{d}/*.json")):
    for line in open(p):  # một chuỗi JSON mỗi dòng
        if not line.strip(): continue
        q = json.loads(line)
        q = re.sub(r"^\d+\.\s*", "", re.sub(r"\s+", " ", q if isinstance(q, str) else json.dumps(q))).strip().strip('"')
        for q in re.split(r'"\s+\d+\.\s+"', q):  # vài dòng chứa nhiều câu đánh số
            q = q.strip().strip('"')
            if q and q.lower() not in seen: seen.add(q.lower()); out.append(q)
open(sys.argv[2], "w").write("\n".join(out)); print(len(out), "prompts")
