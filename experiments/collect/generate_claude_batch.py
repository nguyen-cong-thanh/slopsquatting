"""Sinh dữ liệu với LLM thương mại Claude qua Message Batches API (giảm 50% chi phí), dùng SDK chính thức `anthropic`.

Đầu ra cùng định dạng với generate.py nên build_dataset.py đọc được trực tiếp (đặt file vào <ext>/own/).
Xác thực: biến môi trường ANTHROPIC_API_KEY (hoặc hồ sơ `ant auth login`).

  # 1) Gửi lô sinh dữ liệu (gen) hoặc hỏi lại (requery)
  python generate_claude_batch.py submit-gen --prompts prompts.txt --limit 500 --manifest pilot_haiku.manifest.json
  python generate_claude_batch.py submit-requery --src own/full_haiku.jsonl --n 10 --max-names 500 --manifest var_haiku.manifest.json
  # 2) Chờ lô xong (thường < 1 giờ, tối đa 24 giờ) rồi thu kết quả, gắn nhãn
  python generate_claude_batch.py collect --manifest pilot_haiku.manifest.json --index simple.json --out own/pilot_haiku.jsonl

Lưu ý phương pháp: API hiện không nhận temperature/top_p, nên biến thể khi hỏi lại đến từ cách lấy mẫu mặc định của mô hình.
Ghi lại model, effort và ngày chạy trong báo cáo.
"""
import argparse, json, random, collections, time
import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request
from generate import SYS, label, load_index

def params(model, prompt, effort, max_tokens):
    p = dict(model=model, max_tokens=max_tokens, system=SYS, messages=[{"role": "user", "content": prompt}])
    if effort: p["output_config"] = {"effort": effort}
    return MessageCreateParamsNonStreaming(**p)

def submit(client, a, items):
    """items: list of (custom_id, prompt, meta). Gửi theo lô ≤ 100.000 yêu cầu."""
    ids = []
    for s in range(0, len(items), 100_000):
        chunk = items[s:s + 100_000]
        b = client.messages.batches.create(requests=[Request(custom_id=c, params=params(a.model, p, a.effort, a.max_tokens)) for c, p, _ in chunk])
        ids.append(b.id); print("batch", b.id, len(chunk), "requests")
    json.dump(dict(model=a.model, effort=a.effort, mode=a.mode, batch_ids=ids, created=time.strftime("%Y-%m-%d"),
                   items={c: m for c, _, m in items}), open(a.manifest, "w"), ensure_ascii=False)

def collect(client, a):
    man = json.load(open(a.manifest)); index = load_index(a.index)
    for bid in man["batch_ids"]:
        st = client.messages.batches.retrieve(bid)
        if st.processing_status != "ended": raise SystemExit(f"{bid} chưa xong: {st.processing_status}, đang xử lý {st.request_counts.processing}")
    texts, usage, failed = {}, collections.Counter(), []
    for bid in man["batch_ids"]:
        for r in client.messages.batches.results(bid):          # kết quả về theo thứ tự bất kỳ: dùng custom_id
            if r.result.type == "succeeded":
                msg = r.result.message
                texts[r.custom_id] = "".join(b.text for b in msg.content if b.type == "text")
                usage["input"] += msg.usage.input_tokens; usage["output"] += msg.usage.output_tokens
            else: failed.append((r.custom_id, r.result.type))
    with open(a.out, "w") as f:
        if man["mode"] == "submit-gen":
            for c, m in man["items"].items():
                if c in texts: f.write(json.dumps(dict(model=man["model"], question_index=m["q"], question=m["question"], response=texts[c], **label(texts[c], index)), ensure_ascii=False) + "\n")
        else:
            groups = collections.defaultdict(list)
            for c, m in man["items"].items():
                if c in texts: groups[m["key"]].append(label(texts[c], index))
            for key, Ls in groups.items():
                m = next(v for v in man["items"].values() if v["key"] == key)
                cnt = collections.Counter(x for L in Ls for x in L["modules"]); bad = collections.Counter(x for L in Ls for x in L["modulenotfound"])
                f.write(json.dumps(dict(model=man["model"], question_index=m["q"], seed_name=m["seed"], n=len(Ls), seed_repeat=cnt[m["seed"]],
                                        variants=dict(cnt), halluc_variants=dict(bad)), ensure_ascii=False) + "\n")
    print(json.dumps(dict(ok=len(texts), failed=len(failed), failed_types=dict(collections.Counter(t for _, t in failed)), usage_tokens=dict(usage))))

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("mode", choices=["submit-gen", "submit-requery", "collect"])
    ap.add_argument("--model", default="claude-haiku-5-5"); ap.add_argument("--effort", choices=["low", "medium", "high"], default=None)
    ap.add_argument("--max-tokens", type=int, default=8000); ap.add_argument("--manifest", required=True)
    ap.add_argument("--prompts"); ap.add_argument("--src"); ap.add_argument("--index"); ap.add_argument("--out")
    ap.add_argument("--limit", type=int, default=0); ap.add_argument("--n", type=int, default=10); ap.add_argument("--max-names", type=int, default=500)
    a = ap.parse_args(); client = anthropic.Anthropic()
    if a.mode == "collect": collect(client, a)
    elif a.mode == "submit-gen":
        P = [l.strip() for l in open(a.prompts) if l.strip()]; random.seed(0)
        idx = random.sample(range(len(P)), min(a.limit, len(P))) if a.limit else range(len(P))
        submit(client, a, [(f"q{i}", P[i], dict(q=i, question=P[i])) for i in idx])
    else:
        rows = [json.loads(l) for l in open(a.src)]; tgt = [(r, b) for r in rows for b in r["modulenotfound"]]
        random.seed(0); random.shuffle(tgt); tgt = tgt[:a.max_names]
        submit(client, a, [(f"v{j}-r{k}", r["question"], dict(key=j, q=r["question_index"], seed=b)) for j, (r, b) in enumerate(tgt) for k in range(a.n)])
