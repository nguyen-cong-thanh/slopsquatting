"""Pilot: build tier-1/tier-2 dataset from public sources + live PyPI metadata.
Usage: python build_dataset.py <ext_dir> <work_dir>
Outputs <work_dir>/dataset.csv (one row per normalized name). Never registers anything.
"""
import csv, json, re, sys, random, collections, datetime as dt, urllib.request
from concurrent.futures import ThreadPoolExecutor
EXT, WORK = sys.argv[1], sys.argv[2]
norm = lambda n: re.sub(r"[-_.]+", "-", n.strip()).lower()          # PEP 503
def ultra(n):                                                       # warehouse ultranormalize_name
    n = re.sub(r"[._-]", "", n.lower()); return n.replace("l", "1").replace("i", "1").replace("o", "0")
VALID = re.compile(r"^[a-z0-9]([a-z0-9._-]*[a-z0-9])?$")

rows = {}   # name -> dict
def add(name, group, src, model="", q="", seen=""):
    n = norm(name)
    if not VALID.match(n): return
    r = rows.setdefault(n, dict(name=n, groups=set(), srcs=set(), models=set(), qs=set(), hits=0, seen=""))
    if seen and (not r["seen"] or seen < r["seen"]): r["seen"] = seen
    r["groups"].add(group); r["srcs"].add(src); r["hits"] += 1
    if model: r["models"].add(model)
    if q != "": r["qs"].add(str(q))

for r in csv.DictReader(open(f"{EXT}/slopsquatting-dataset/slopsquatting.csv")):
    if r["ecosystem"] == "PyPI": add(r["name"], "halluc", "0pstech", r["models"], r["tasks"][:80], r["first_seen"][:10])
import glob   # Trend Micro + dữ liệu tự sinh (experiments/collect/generate.py gen) đặt trong <ext>/own/*.jsonl
for path in [f"{EXT}/slopsquatting/slopsquatting.jsonl"] + sorted(glob.glob(f"{EXT}/own/*.jsonl")):
    src = "trendmicro" if "/slopsquatting/" in path else "own"
    for l in open(path):
        d = json.loads(l); bad = {norm(x) for x in d["modulenotfound"]}
        for m in d["modules"]:
            add(m, "halluc" if norm(m) in bad else "real_llm", src, d["model"], d["question_index"])
for e in json.load(open(f"{EXT}/depscope-hallucinations-dataset/snapshots/2026-09-20.json"))["entries"]:
    if e["ecosystem"] == "pypi": add(e["package_name"], "halluc", "depscope")
for n in open(f"{WORK}/ossf_pypi.txt"): add(n, "malicious", "ossf")
for l in open(f"{EXT}/PackageHallucination/Mitigation/Data/pypi_descriptions.jsonl"):  # Spracklen RAG reference packages
    if json.loads(l).get("package"): add(json.loads(l)["package"], "real_ref", "spracklen_rag")

index = {norm(p["name"]) for p in json.load(open(f"{WORK}/simple.json"))["projects"]}
ultra_index = collections.Counter(ultra(n) for n in index)
random.seed(0)
for n in random.sample(sorted(index), 10000): add(n, "random_pypi", "pypi_index")

def meta(n):
    try:
        with urllib.request.urlopen(f"https://pypi.org/pypi/{n}/json", timeout=30) as f: d = json.load(f)
    except Exception as ex: return n, None
    info, rel = d["info"], d.get("releases", {})
    ups = [f["upload_time_iso_8601"] for fs in rel.values() for f in fs]
    now = dt.datetime(2026, 11, 9, tzinfo=dt.timezone.utc)
    age = lambda s: (now - dt.datetime.fromisoformat(s.replace("Z", "+00:00"))).days
    urls = " ".join([info.get("home_page") or ""] + list((info.get("project_urls") or {}).values())).lower()
    return n, dict(
        age_days=age(min(ups)) if ups else -1, days_since_last=age(max(ups)) if ups else -1,
        n_releases=len([v for v, fs in rel.items() if fs]), n_files=len(ups),
        summary_len=len(info.get("summary") or ""), desc_len=len(info.get("description") or ""),
        has_author=int(bool(info.get("author") or info.get("author_email") or info.get("maintainer_email"))),
        has_license=int(bool(info.get("license") or info.get("license_expression"))),
        n_requires=len(info.get("requires_dist") or []), n_classifiers=len(info.get("classifiers") or []),
        n_urls=len(info.get("project_urls") or {}), has_repo=int(bool(re.search(r"github\.com|gitlab\.com|bitbucket", urls))),
        summary=(info.get("summary") or "")[:200].replace("\n", " "))

todo = [n for n in rows if n in index]
print("names", len(rows), "registered->fetch", len(todo), flush=True)
with ThreadPoolExecutor(24) as ex: M = dict(ex.map(meta, todo))
cols = ["age_days","days_since_last","n_releases","n_files","summary_len","desc_len","has_author","has_license","n_requires","n_classifiers","n_urls","has_repo","summary"]
with open(f"{WORK}/dataset.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["name","groups","srcs","models","qs","hits","on_pypi","ultra_collision","first_seen"] + cols)
    for n, r in rows.items():
        m = M.get(n) or {}
        coll = ultra_index[ultra(n)] - (n in index)       # other registered names that would block registration
        w.writerow([n, "|".join(sorted(r["groups"])), "|".join(sorted(r["srcs"])), "|".join(sorted(r["models"])),
                    len(r["qs"]), r["hits"], int(n in index), coll, r["seen"]] + [m.get(c, "") for c in cols])
print("done")
