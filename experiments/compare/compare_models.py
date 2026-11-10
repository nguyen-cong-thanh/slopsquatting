"""So sánh nhiều LLM trên cùng bộ câu hỏi: tỷ lệ tên bịa (KTC Wilson 95%), số tên bịa không trùng,
độ trùng tên giữa các LLM (Jaccard), và (tùy chọn) ma trận phát hiện chéo LLM.
Đầu vào: các file jsonl định dạng Trend Micro / generate.py (mỗi dòng: model, modules, modulenotfound).
Usage: python compare_models.py <out_dir> file1.jsonl [file2.jsonl ...] [--detect] [--min-names 30]
Đầu ra: model_summary.csv, jaccard.csv, fig_halluc_rate.png, fig_jaccard.png, [cross_llm.csv, fig_cross_llm.png]
"""
import sys, json, re, math, collections, argparse, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
norm = lambda n: re.sub(r"[-_.]+", "-", n).lower()
BLUE, INK, INK2, SURF = "#2a78d6", "#0b0b0b", "#52514e", "#fcfcfb"
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]   # một sắc độ, nhạt -> đậm
plt.rcParams.update({"font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
                     "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.dpi": 200})

def wilson(k, n, z=1.96):
    if n == 0: return 0, 0, 0
    p = k / n; d = 1 + z*z/n; c = (p + z*z/(2*n)) / d; h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return p, max(0, c-h), min(1, c+h)

ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("files", nargs="+")
ap.add_argument("--detect", action="store_true"); ap.add_argument("--min-names", type=int, default=30); a = ap.parse_args()
S = collections.defaultdict(lambda: dict(resp=0, mods=0, bad=0, H=set(), R=set()))
for p in a.files:
    for l in open(p):
        d = json.loads(l); s = S[d["model"]]; bad = {norm(x) for x in d["modulenotfound"]}
        s["resp"] += 1; s["mods"] += d["module_count"]; s["bad"] += d["modulenotfound_count"]
        s["H"] |= bad; s["R"] |= {norm(x) for x in d["modules"]} - bad
rows = []
for m, s in S.items():
    p, lo, hi = wilson(s["bad"], s["mods"])
    rows.append(dict(model=m, responses=s["resp"], suggestions=s["mods"], halluc_rate=round(p, 4), ci_low=round(lo, 4), ci_high=round(hi, 4),
                     unique_halluc=len(s["H"]), unique_halluc_per_1000=round(1000*len(s["H"])/max(s["resp"], 1), 1), unique_real=len(s["R"])))
T = pd.DataFrame(rows).sort_values("halluc_rate"); T.to_csv(f"{a.out}/model_summary.csv", index=False)

# Hình 1: tỷ lệ tên bịa theo LLM (một chuỗi -> một màu; thanh lỗi = KTC 95%)
fig, ax = plt.subplots(figsize=(6, 0.28*len(T) + 1))
ax.barh(T.model, 100*T.halluc_rate, color=BLUE, height=0.6)
ax.errorbar(100*T.halluc_rate, T.model, xerr=[100*(T.halluc_rate-T.ci_low), 100*(T.ci_high-T.halluc_rate)], fmt="none", ecolor=INK2, elinewidth=1, capsize=2)
ax.set_xlabel("Tỷ lệ tên gói bịa trên lượt gợi ý (%), KTC Wilson 95%"); ax.grid(axis="x", color="#e4e3df", lw=0.6); ax.set_axisbelow(True)
for sp in ("top", "right"): ax.spines[sp].set_visible(False)
fig.tight_layout(); fig.savefig(f"{a.out}/fig_halluc_rate.png"); plt.close(fig)

# Hình 2: độ trùng tên bịa giữa các LLM (Jaccard), thang một sắc độ
M = list(T.model); n = len(M)
J = np.array([[len(S[x]["H"] & S[y]["H"]) / max(len(S[x]["H"] | S[y]["H"]), 1) for y in M] for x in M])
pd.DataFrame(J, index=M, columns=M).round(3).to_csv(f"{a.out}/jaccard.csv")
def heat(Mx, labels, title, fname, vmax=None, fmt="{:.2f}", xl="", yl=""):
    from matplotlib.colors import ListedColormap
    fig, ax = plt.subplots(figsize=(0.45*len(labels) + 2.5, 0.45*len(labels) + 1.5))
    cm = ListedColormap(SEQ); cm.set_bad(SURF)          # ô NaN (đường chéo bị che) để trống
    im = ax.imshow(Mx, cmap=cm, vmin=0, vmax=vmax or max(np.nanmax(Mx), 1e-9))
    ax.set_xticks(range(len(labels)), labels, rotation=60, ha="right"); ax.set_yticks(range(len(labels)), labels)
    ax.set_xticks(np.arange(-.5, len(labels)), minor=True); ax.set_yticks(np.arange(-.5, len(labels)), minor=True)
    ax.grid(which="minor", color=SURF, lw=2); ax.tick_params(which="minor", length=0)   # khe 2px giữa các ô
    if len(labels) <= 10:
        for i in range(len(labels)):
            for j in range(len(labels)):
                v = Mx[i, j]
                if np.isnan(v): continue
                ax.text(j, i, fmt.format(v), ha="center", va="center", fontsize=7, color=SURF if v > 0.6*(vmax or np.nanmax(Mx)) else INK)
    ax.set_xlabel(xl); ax.set_ylabel(yl); ax.set_title(title, color=INK, fontsize=9); fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout(); fig.savefig(f"{a.out}/{fname}"); plt.close(fig)
Jm = J.copy(); np.fill_diagonal(Jm, np.nan)          # che đường chéo (luôn = 1) để thang màu dành cho các cặp
heat(Jm, M, "Độ trùng tên bịa giữa các LLM (Jaccard, đường chéo bỏ trống)", "fig_jaccard.png")
pairs = sorted(((Jm[i, j], M[i], M[j]) for i in range(n) for j in range(i+1, n)), reverse=True)[:5]
print("Cặp trùng nhiều nhất:", "; ".join(f"{x} – {y}: {v:.2f}" for v, x, y in pairs))

# Hình 3 (tùy chọn): ma trận phát hiện chéo LLM — huấn luyện trên tên của LLM hàng, kiểm thử trên LLM cột (TPR@1%FPR)
if a.detect:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    E = [m for m in M if len(S[m]["H"]) >= a.min_names and len(S[m]["R"]) >= 5*a.min_names]
    if len(E) >= 2:
        C = np.zeros((len(E), len(E)))
        for i, x in enumerate(E):
            for j, y in enumerate(E):
                Hx, Rx = sorted(S[x]["H"]), sorted(S[x]["R"])
                Hy, Ry = sorted(S[y]["H"] - S[x]["H"]), sorted(S[y]["R"] - S[x]["R"])   # chỉ tên chưa thấy khi huấn luyện
                if i == j:   # cùng LLM: chia 70/30 theo thứ tự xáo cố định
                    rs = np.random.RandomState(0); hp, rp = rs.permutation(len(Hx)), rs.permutation(len(Rx))
                    Hy, Ry = [Hx[k] for k in hp[int(.7*len(Hx)):]], [Rx[k] for k in rp[int(.7*len(Rx)):]]
                    Hx, Rx = [Hx[k] for k in hp[:int(.7*len(Hx))]], [Rx[k] for k in rp[:int(.7*len(Rx))]]
                v = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1); X = v.fit_transform(Hx + Rx)
                clf = LogisticRegression(C=2, max_iter=3000, class_weight="balanced").fit(X, [1]*len(Hx) + [0]*len(Rx))
                ph, pr = clf.predict_proba(v.transform(Hy))[:, 1], clf.predict_proba(v.transform(Ry))[:, 1]
                C[i, j] = float((ph > np.quantile(pr, .99)).mean()) if len(Hy) and len(Ry) else np.nan
        pd.DataFrame(C, index=E, columns=E).round(3).to_csv(f"{a.out}/cross_llm.csv")
        heat(np.nan_to_num(C), E, "Phát hiện chéo LLM: TPR@1%FPR", "fig_cross_llm.png", vmax=1, xl="LLM kiểm thử", yl="LLM huấn luyện")
    else: print(f"bỏ qua --detect: cần ≥ 2 LLM có ≥ {a.min_names} tên bịa và ≥ {5*a.min_names} tên thật")
print(T.to_string(index=False))
