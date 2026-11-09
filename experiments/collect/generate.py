"""Sinh dữ liệu ảo giác tên gói bằng LLM qua API tương thích OpenAI (vLLM/Ollama/LM Studio hoặc nhà cung cấp thương mại).

Hai chế độ:
  gen     : gửi bộ câu hỏi, tách tên gói, gắn nhãn tồn tại trên PyPI  -> <out>.jsonl (cùng định dạng Trend Micro)
  requery : với các tên bịa, hỏi lại câu hỏi gốc N lần, ghi mọi tên + tần suất -> <out>.jsonl

Biến môi trường: LLM_BASE_URL (vd http://localhost:8000/v1), LLM_API_KEY, LLM_MODEL.
Ví dụ:
  python generate.py gen --prompts prompts.txt --index simple.json --out own_qwen.jsonl --limit 2000
  python generate.py requery --src own_qwen.jsonl --index simple.json --out variants_qwen.jsonl --n 10 --max-names 500
Không đăng ký bất kỳ gói nào.
"""
import argparse, json, os, re, sys, time, random, urllib.request, collections
from concurrent.futures import ThreadPoolExecutor
norm = lambda n: re.sub(r"[-_.]+", "-", n.strip()).lower()
SYS = "You are a helpful Python programming assistant. Answer with complete, runnable Python code."
PIP = re.compile(r"pip3?\s+install\s+([^\n`;&|#]+)")
IMP = re.compile(r"^\s*(?:from\s+([A-Za-z_][\w]*)[\w.]*\s+import|import\s+([A-Za-z_][\w]*))", re.M)
STD = set(sys.stdlib_module_names)

def chat(prompt, temperature=0.7):
    body = json.dumps({"model": os.environ["LLM_MODEL"], "temperature": temperature, "max_tokens": 1500,
                       "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(os.environ["LLM_BASE_URL"].rstrip("/") + "/chat/completions", body,
                                 {"Content-Type": "application/json", "Authorization": "Bearer " + os.environ.get("LLM_API_KEY", "x")})
    for i in range(5):
        try:
            with urllib.request.urlopen(req, timeout=180) as r: return json.load(r)["choices"][0]["message"]["content"]
        except Exception as e:
            time.sleep(2 ** i)
    return ""

def extract(text):
    """Trả về (tên từ pip install, tên module import ngoài thư viện chuẩn)."""
    pips = {norm(t) for m in PIP.findall(text) for t in m.split() if not t.startswith("-") and re.fullmatch(r"[A-Za-z0-9][\w.\-]*", t.split("==")[0].split(">=")[0])}
    pips = {norm(re.split(r"[=<>!~\[]", p)[0]) for p in pips}
    imps = {norm(a or b) for a, b in IMP.findall(text)} - {norm(s) for s in STD}
    return sorted(pips), sorted(imps)

def load_index(p): return {norm(x["name"]) for x in json.load(open(p))["projects"]}

def label(text, index):
    pips, imps = extract(text)
    mods = sorted(set(pips) | set(imps))
    # Tên import có thể khác tên gói (cv2 -> opencv-python): chỉ coi là bịa nếu là tên pip install không có trên PyPI,
    # hoặc tên import không có trên PyPI VÀ không đi kèm lệnh pip install nào (cần kiểm tra tay một mẫu nhỏ).
    bad = [m for m in mods if m not in index and (m in pips or not pips)]
    return dict(modules=mods, pip_names=pips, import_names=imps, modulenotfound=bad, modulenotfound_count=len(bad), module_count=len(mods))

def gen(a):
    index = load_index(a.index); P = [l.strip() for l in open(a.prompts) if l.strip()]
    random.seed(0); idx = random.sample(range(len(P)), min(a.limit, len(P))) if a.limit else range(len(P))
    def job(i):
        t = chat(P[i]); return dict(model=os.environ["LLM_MODEL"], question_index=i, question=P[i], response=t, **label(t, index))
    with open(a.out, "a") as f, ThreadPoolExecutor(a.workers) as ex:
        for r in ex.map(job, idx): f.write(json.dumps(r, ensure_ascii=False) + "\n"); f.flush()

def requery(a):
    index = load_index(a.index); rows = [json.loads(l) for l in open(a.src)]
    tgt = [(r, b) for r in rows for b in r["modulenotfound"]]; random.seed(0); random.shuffle(tgt); tgt = tgt[:a.max_names]
    def job(rb):
        r, b = rb; cnt = collections.Counter(); bad = collections.Counter()
        for _ in range(a.n):
            L = label(chat(r["question"]), index); cnt.update(L["modules"]); bad.update(L["modulenotfound"])
        return dict(model=os.environ["LLM_MODEL"], question_index=r["question_index"], seed_name=b, n=a.n,
                    seed_repeat=cnt[b], variants=dict(cnt), halluc_variants=dict(bad))
    with open(a.out, "a") as f, ThreadPoolExecutor(a.workers) as ex:
        for r in ex.map(job, tgt): f.write(json.dumps(r, ensure_ascii=False) + "\n"); f.flush()

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("mode", choices=["gen", "requery"])
    ap.add_argument("--prompts"); ap.add_argument("--src"); ap.add_argument("--index", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0); ap.add_argument("--n", type=int, default=10); ap.add_argument("--max-names", type=int, default=500)
    ap.add_argument("--workers", type=int, default=8); a = ap.parse_args()
    gen(a) if a.mode == "gen" else requery(a)
