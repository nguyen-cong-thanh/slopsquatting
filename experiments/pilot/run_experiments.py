"""Pilot experiments E0-E4. Usage: python run_experiments.py <dataset.csv> <out_dir>"""
import sys, json, math, re, collections, numpy as np, pandas as pd, torch, torch.nn as nn
from rapidfuzz import process, distance
from sklearn.model_selection import GroupKFold
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import roc_auc_score, average_precision_score
from xgboost import XGBClassifier
torch.manual_seed(0); np.random.seed(0); torch.set_num_threads(4)
D = pd.read_csv(sys.argv[1]); OUT = sys.argv[2]; R = {}
has = lambda g: D.groups.str.contains(g)
ultra = lambda n: re.sub(r"[._-]", "", n).replace("l", "1").replace("i", "1").replace("o", "0")
META = ["age_days","days_since_last","n_releases","n_files","summary_len","desc_len","has_author","has_license","n_requires","n_classifiers","n_urls","has_repo"]

# ---------- name features ----------
POP = sorted(set(D[has("real_ref")].name))
def ent(s): c = collections.Counter(s); return -sum(v/len(s)*math.log2(v/len(s)) for v in c.values())
def near(n):
    m = [x for x in process.extract(n, POP, scorer=distance.Levenshtein.distance, limit=2) if x[0] != n]
    return m[0][1] if m else 99
def namefeat(n):
    t = n.split("-")
    return [len(n), len(t), sum(c.isdigit() for c in n)/len(n), sum(c in "aeiou" for c in n)/len(n), ent(n),
            int(n.startswith(("py", "python-"))), int(bool(re.search(r"-(utils?|lib|sdk|ai|tools?|client|api|helper|kit)$", n))),
            near(n), int(any(p in t for p in ("python", "py"))), max(map(len, t))]
NF = ["len","n_tokens","digit_ratio","vowel_ratio","entropy","py_prefix","generic_suffix","lev_to_popular","py_token","max_token_len"]
D[NF] = np.array([namefeat(n) for n in D.name])

# ---------- char CNN ----------
CH = {c: i+1 for i, c in enumerate("abcdefghijklmnopqrstuvwxyz0123456789-._")}; L = 40
enc = lambda ns: torch.tensor([[CH.get(c, 0) for c in n[:L]] + [0]*(L-len(n[:L])) for n in ns])
class CNN(nn.Module):
    def __init__(s, meta=0):
        super().__init__(); s.emb = nn.Embedding(len(CH)+1, 32, padding_idx=0)
        s.convs = nn.ModuleList([nn.Conv1d(32, 64, k, padding=k//2) for k in (2, 3, 4)])
        s.mlp = nn.Sequential(nn.Linear(meta, 32), nn.ReLU()) if meta else None
        s.fc = nn.Sequential(nn.Dropout(0.3), nn.Linear(192 + (32 if meta else 0), 1))
    def forward(s, x, m=None, e=None):
        h = (s.emb(x) if e is None else e).transpose(1, 2)
        z = torch.cat([torch.relu(c(h)).max(2).values for c in s.convs], 1)
        if s.mlp is not None: z = torch.cat([z, s.mlp(m)], 1)
        return s.fc(z).squeeze(1)
class TorchClf:
    def __init__(s, meta_cols=()): s.mc = list(meta_cols)
    def _m(s, X): return torch.tensor(np.log1p(X[s.mc].clip(lower=0).values), dtype=torch.float32) if s.mc else None
    def fit(s, X, y, ep=12):
        s.net = CNN(len(s.mc)); opt = torch.optim.Adam(s.net.parameters(), 2e-3)
        x, m, y = enc(X.name), s._m(X), torch.tensor(y, dtype=torch.float32); pw = torch.tensor((y == 0).sum()/(y == 1).sum())
        for _ in range(ep):
            s.net.train()
            for b in torch.randperm(len(y)).split(128):
                opt.zero_grad(); nn.functional.binary_cross_entropy_with_logits(s.net(x[b], None if m is None else m[b]), y[b], pos_weight=pw).backward(); opt.step()
        return s
    def score(s, X):
        s.net.eval()
        with torch.no_grad(): return s.net(enc(X.name), s._m(X)).numpy()

class SkClf:
    def __init__(s, kind, cols, tfidf=False): s.k, s.c, s.t = kind, list(cols), tfidf
    def fit(s, X, y):
        w = (y == 0).sum()/(y == 1).sum()
        if s.t:
            s.v = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=2); Z = s.v.fit_transform(X.name)
            s.m = LogisticRegression(C=2, max_iter=3000, class_weight="balanced").fit(Z, y)
        elif s.k == "rf": s.m = RandomForestClassifier(400, min_samples_leaf=2, class_weight="balanced", n_jobs=4, random_state=0).fit(X[s.c].fillna(-1), y)
        else: s.m = XGBClassifier(n_estimators=300, max_depth=5, learning_rate=0.05, subsample=0.8, scale_pos_weight=w, n_jobs=4, random_state=0, eval_metric="logloss").fit(X[s.c].fillna(-1), y)
        return s
    def score(s, X): return s.m.predict_proba(s.v.transform(X.name) if s.t else X[s.c].fillna(-1))[:, 1]

def boot(f, *a, B=500):
    rs = np.random.RandomState(0); v = []
    for _ in range(B):
        idx = [rs.randint(0, len(x), len(x)) for x in a]; v.append(f(*[x[i] for x, i in zip(a, idx)]))
    return [round(float(np.percentile(v, 2.5)), 3), round(float(np.percentile(v, 97.5)), 3)]
tpr_at = lambda pos, neg, fpr=0.01: float((pos > np.quantile(neg, 1-fpr)).mean())
def auc(pos, neg): return roc_auc_score(np.r_[np.ones(len(pos)), np.zeros(len(neg))], np.r_[pos, neg])
def ap(pos, neg): return average_precision_score(np.r_[np.ones(len(pos)), np.zeros(len(neg))], np.r_[pos, neg])

def cv_eval(P, N, held, factory, k=5):
    """GroupKFold on P∪N (group = first name token, keeps near-duplicate names together); held-out sets scored by fold-average."""
    X = pd.concat([P, N]); y = np.r_[np.ones(len(P)), np.zeros(len(N))]; g = X.name.str.split("-").str[0]
    oof = np.zeros(len(X)); hs = {kk: np.zeros(len(v)) for kk, v in held.items()}
    for tr, te in GroupKFold(k).split(X, y, g):
        m = factory().fit(X.iloc[tr], y[tr]); oof[te] = m.score(X.iloc[te])
        for kk, v in held.items(): hs[kk] += m.score(v)/k
    pos, neg = oof[y == 1], oof[y == 0]; prim = hs["primary"]; thr = np.quantile(prim, 0.99)
    r = dict(n_pos=len(P), n_neg=len(N), auc_cv=round(auc(pos, neg), 3), auc_ci=boot(auc, pos, neg), pr_auc_cv=round(ap(pos, neg), 3),
             tpr_at_1fpr_cv=round(tpr_at(pos, neg), 3), tpr_ci=boot(tpr_at, pos, neg),
             tpr_at_1fpr_primary=round(float((pos > thr).mean()), 3), tpr_primary_ci=boot(lambda p, n: float((p > np.quantile(n, .99)).mean()), pos, prim))
    for kk, v in hs.items():
        if kk != "primary": r[f"fpr_{kk}_at_primary_thr"] = round(float((v > thr).mean()), 4)
    return r, oof, y, X, hs

# ===== E0: descriptive =====
H = D[has("halluc")]; seen = pd.to_datetime(H.first_seen, utc=True, errors="coerce")
reg_age = H[(H.on_pypi == 1) & (H.age_days >= 0)]
R["E0"] = dict(n_halluc=len(H), by_src=H.srcs.value_counts().to_dict(), n_real_llm=int(has("real_llm").sum()), n_real_ref=int(has("real_ref").sum()),
    n_malicious=int(has("malicious").sum()), n_random_pypi=int(has("random_pypi").sum()),
    halluc_in_index=int(H.on_pypi.sum()), halluc_with_files=len(reg_age), halluc_index_no_files=int(((H.on_pypi == 1) & ~(H.age_days >= 0)).sum()),
    halluc_registered_after_first_seen=int(((H.on_pypi == 1) & (H.age_days >= 0) & (pd.Timestamp("2026-11-09", tz="UTC") - pd.to_timedelta(H.age_days, "D") > seen)).sum()),
    halluc_research_placeholders=int(H.summary.fillna("").str.contains("research|slopsquat|placeholder|security", case=False).sum()),
    halluc_blocked_by_ultranormalize=int(((H.on_pypi == 0) & (H.ultra_collision > 0)).sum()),
    halluc_registrable=int(((H.on_pypi == 0) & (H.ultra_collision == 0)).sum()),
    malicious_still_in_index=int(D[has("malicious")].on_pypi.sum()), malicious_with_files=int((D[has("malicious")].age_days >= 0).sum()))
TM = [json.loads(l) for l in open(sys.argv[3])] if len(sys.argv) > 3 else []
if TM:
    pm = collections.defaultdict(lambda: [0, 0]); perq = collections.defaultdict(collections.Counter)
    for t in TM:
        pm[t["model"]][0] += t["modulenotfound_count"]; pm[t["model"]][1] += t["module_count"]
        for x in t["modulenotfound"]: perq[t["question_index"]][re.sub(r"[-_.]+", "-", x).lower()] += 1
    allc = collections.Counter(n for c in perq.values() for n in c.elements())
    R["E0"]["trendmicro_halluc_rate_by_model"] = {k: round(a/b, 3) for k, (a, b) in sorted(pm.items(), key=lambda z: -z[1][0]/z[1][1])}
    R["E0"]["trendmicro_questions_with_halluc"] = len(perq)
    R["E0"]["trendmicro_distinct_halluc_per_question_mean"] = round(np.mean([len(c) for c in perq.values()]), 2)
    R["E0"]["trendmicro_halluc_names_shared_by_>=2_models"] = sum(v >= 2 for v in allc.values()); R["E0"]["trendmicro_unique_halluc"] = len(allc)

# ===== E1: tier-1 name-only (hallucinated vs real) =====
P1 = H.drop_duplicates("name"); N1 = D[has("real_ref") & ~has("halluc")]
held1 = dict(primary=D[has("real_llm") & ~has("real_ref") & ~has("halluc")], random_pypi=D[has("random_pypi") & ~has("real_ref")])
models1 = {"LR_char_ngram": lambda: SkClf("lr", [], True), "RF_name_feats": lambda: SkClf("rf", NF), "XGB_name_feats": lambda: SkClf("xgb", NF), "CharCNN": lambda: TorchClf()}
R["E1"] = {}
for k, f in models1.items(): R["E1"][k] = cv_eval(P1, N1, held1, f)[0]; print("E1", k, R["E1"][k], flush=True)

# cross-LLM: train on gpt-* hallucinations, test on other LLMs' hallucinations (same negatives split)
gpt = P1.models.fillna("").str.contains("gpt") & ~P1.models.fillna("").str.contains("gemini|claude")
oth = P1.models.fillna("").str.contains("gemini|claude") & ~P1.models.fillna("").str.contains("gpt")
rs = np.random.RandomState(0); msk = rs.rand(len(N1)) < .8
R["E1_crossLLM"] = {}
for k, f in models1.items():
    m = f().fit(pd.concat([P1[gpt], N1[msk]]), np.r_[np.ones(gpt.sum()), np.zeros(msk.sum())])
    neg, pin, pout = m.score(N1[~msk]), m.score(P1[gpt].sample(frac=1, random_state=0).iloc[:0]), m.score(P1[oth])
    R["E1_crossLLM"][k] = dict(n_train_pos=int(gpt.sum()), n_test_pos_other_llm=int(oth.sum()), auc_other_llm=round(auc(pout, neg), 3), tpr_at_1fpr_other_llm=round(tpr_at(pout, neg), 3), tpr_ci=boot(tpr_at, pout, neg))

# ===== E2: tier-2 registered names, name vs meta vs name+meta =====
withm = D.age_days >= 0
P2 = D[(has("halluc") | has("malicious")) & withm]; N2 = D[(has("real_ref") | has("random_pypi")) & withm & ~has("halluc") & ~has("malicious")]
held2 = dict(primary=D[has("real_llm") & ~has("real_ref") & ~has("random_pypi") & withm], new_pypi=N2[N2.age_days <= 60])
models2 = {"LR_char_ngram[name]": lambda: SkClf("lr", [], True), "XGB[name]": lambda: SkClf("xgb", NF), "XGB[meta]": lambda: SkClf("xgb", META),
           "XGB[name+meta]": lambda: SkClf("xgb", NF + META), "RF[name+meta]": lambda: SkClf("rf", NF + META), "CharCNN+MLP[name+meta]": lambda: TorchClf(META)}
R["E2"] = {}; keep = {}
for k, f in models2.items():
    R["E2"][k], *keep[k] = cv_eval(P2, N2, held2, f); print("E2", k, R["E2"][k], flush=True)
imp = SkClf("xgb", NF + META).fit(pd.concat([P2, N2]), np.r_[np.ones(len(P2)), np.zeros(len(N2))])
R["E2_feature_importance"] = dict(sorted(zip(NF + META, map(float, imp.m.feature_importances_.round(3))), key=lambda z: -z[1])[:10])

# ===== E3: metadata-forging attack (simulated) on XGB[name+meta] =====
X2 = pd.concat([P2, N2]); y2 = np.r_[np.ones(len(P2)), np.zeros(len(N2))]
det = SkClf("xgb", NF + META).fit(X2, y2); thr = np.quantile(det.score(held2["primary"]), .99)
tgt = P2[det.score(P2) > thr].copy(); ref = held2["primary"][META].median()
CHEAP = ["summary_len","desc_len","has_author","has_license","n_requires","n_classifiers","n_urls","has_repo","n_releases","n_files","days_since_last"]
R["E3"] = dict(n_detected_targets=len(tgt), benign_reference="median of primary real (LLM-recommended) packages", curve={})
for days in [0, 7, 30, 90, 180, 365]:
    a = tgt.copy(); a[CHEAP] = np.maximum(a[CHEAP].values, ref[CHEAP].values); a["days_since_last"] = ref["days_since_last"]; a["age_days"] = a.age_days + days
    R["E3"]["curve"][f"wait_{days}d+cheap_meta"] = round(float((det.score(a) <= thr).mean()), 3)
a = tgt.copy(); a["age_days"] += 365; R["E3"]["curve"]["wait_365d_only"] = round(float((det.score(a) <= thr).mean()), 3)

# ===== E4: free char-edit attack (HotFlip-style on CharCNN, name-only tier-1) vs realistic constraints =====
cnn = TorchClf().fit(pd.concat([P1, N1]), np.r_[np.ones(len(P1)), np.zeros(len(N1))]); cnn.net.eval()
t1 = np.quantile(cnn.score(held1["primary"]), .99); tg = P1[cnn.score(P1) > t1].name.tolist()
index = set(D[D.on_pypi == 1].name); uidx = collections.Counter(ultra(n) for n in index)
idx2ch = {v: k for k, v in CH.items()}; Wemb = cnn.net.emb.weight.detach(); halluc_all = set(H.name)
def hotflip(n, k):
    x = enc([n]); cur = n
    for _ in range(k):
        e = cnn.net.emb(x).detach().requires_grad_(True); s = cnn.net(x, e=e); s.backward()
        gain = -(e.grad[0] @ Wemb.T) + (e.grad[0] * e[0]).sum(1, keepdim=True)  # first-order decrease of score per (pos, char)
        gain[:, 0] = -1e9; gain[len(cur):] = -1e9
        p, c = divmod(int(gain.argmax()), gain.shape[1]); x[0, p] = c
        cur = "".join(idx2ch.get(int(i), "") for i in x[0] if int(i))
        with torch.no_grad():
            if cnn.net(x).item() <= t1: return cur, True
    return cur, False
R["E4"] = dict(n_targets=len(tg))
for k in (1, 2, 3):
    res = [hotflip(n, k) for n in tg]; ok = [r for r, s in res if s]
    valid = [r for r in ok if re.fullmatch(r"[a-z0-9]([a-z0-9._-]*[a-z0-9])?", r)]
    regbl = [r for r in valid if r not in index and uidx[ultra(r)] == 0]
    R["E4"][f"k={k}"] = dict(evasion_free=round(len(ok)/len(tg), 3), evasion_valid_name=round(len(valid)/len(tg), 3),
                             evasion_registrable=round(len(regbl)/len(tg), 3), evasion_realistic_llm_name=round(sum(r in halluc_all for r in regbl)/len(tg), 3))
print(json.dumps(R["E4"]))
json.dump(R, open(f"{OUT}/results.json", "w"), indent=1, ensure_ascii=False)
