"""Tầng 2 với đặc trưng mốc dữ liệu: ngày gói được đăng ký so với mốc dữ liệu của model đã gợi ý nó.

Mỗi dòng là một cặp (gói, model gợi ý): một gói có thể ra đời trước mốc của model này nhưng sau mốc của
model khác. Đặc trưng reg_minus_cutoff_days = ngày đăng ký - mốc của model (dương: ra đời sau mốc).

Âm: gói thật model đó gợi ý (metadata thật). Dương: tên bịa model đó gợi ý, giả định kẻ tấn công đăng ký với
metadata của một gói mới thật (như tier2 trong __main__). Ngưỡng ở mức báo nhầm 1% gói thật (tập test).

Tấn công:
  - đăng ký mới rồi chờ (như trước): ngày đăng ký không đổi, nên đặc trưng mốc không đổi khi chờ;
  - đăng ký trước mốc (PRE_DAYS ngày trước mốc của model mục tiêu): né được đặc trưng mốc, nhưng kẻ tấn công
    phải đoán tên từ một model cũ hơn và tên phải còn được model mục tiêu gợi ý. Báo tỷ lệ né với điều kiện tên
    còn được gợi ý, và kỳ vọng = tỷ lệ đó x tỷ lệ tên còn được gợi ý ở phiên bản khác (đo trong
    data/exports/persistence, "ít nhất một lần trong 10 lần").

Không đánh giá trên nhãn rules-v3 lấy từ luật after_model_cutoff (vòng lặp): dương là gói tấn công mô phỏng.
"""

from __future__ import annotations

import logging
import time
import tomllib
from pathlib import Path

import numpy as np
import pandas as pd

from slopcollect.detect import attack as atk
from slopcollect.detect.data import META_COLS, MODELS, SHORT, Dataset, _bucket
from slopcollect.detect.models import AGE_COLS, NAME_COLS, Model, NameFeaturizer, auc, rate, threshold_at_fpr

log = logging.getLogger("slopdetect")

CUT_COL = "reg_minus_cutoff_days"
PRE_DAYS = 30
# Tỷ lệ cặp (tên bịa, câu hỏi) mà phiên bản khác cùng họ vẫn gợi ý tên đó ít nhất một lần trong 10 lần
# (data/exports/persistence/results.md, 14/11/2026): Llama 3.3 0.072, Llama 4 Scout 0.064; DeepSeek V3 0.416,
# V3.1 0.396, V3.2 0.424, V4 Flash 0.44. GLM chưa đo.
PERSISTENCE = {"llama31-8b-deepinfra": 0.068, "deepseek-v41-flash-deepinfra": 0.419}


def _r(x: float) -> float:
    return round(float(x), 4)


def load_cutoffs(path: str = "configs/cutoffs.toml") -> dict[str, pd.Timestamp]:
    with open(path, "rb") as f:
        return {m: pd.Timestamp(v["date"]) for m, v in tomllib.load(f).items()}


class CutoffRule:
    """Luật: cảnh báo khi gói được đăng ký muộn hơn mốc dữ liệu của model đã gợi ý nó quá RULE_MARGIN ngày.
    Không học từ dữ liệu, không dùng metadata làm giả được; ngưỡng cố định (không chỉnh theo báo nhầm 1%)."""

    name = "luật: sau mốc của model gợi ý thì cảnh báo"
    fixed_threshold = 0.5

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> "CutoffRule":
        return self

    def score(self, X: pd.DataFrame) -> np.ndarray:
        return (X[CUT_COL].values > RULE_MARGIN).astype(float)


RULE_MARGIN = 30


def models() -> list[Model]:
    no_age = [c for c in META_COLS if c not in AGE_COLS]
    return [
        Model("tên + metadata (GB)", "hgb", NAME_COLS + META_COLS),
        Model("tên + metadata + mốc (GB)", "hgb", NAME_COLS + META_COLS + [CUT_COL]),
        Model("tên + metadata trừ tuổi + mốc (GB)", "hgb", NAME_COLS + no_age + [CUT_COL]),
    ]


def _cut_feature(age_days: pd.Series, now: pd.Timestamp, cutoff: pd.Timestamp) -> pd.Series:
    # Ngày đăng ký = now - age; so với mốc: (now - mốc) - age.
    return (now - cutoff).days - age_days


def _assign(names: list[str], profiles: pd.DataFrame, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    out = profiles.iloc[rng.integers(0, len(profiles), size=len(names))][META_COLS].copy()
    out.index = names
    return out


AUG_WAITS = [0, 30, 90, 365]
AUG_BUDGETS = [0, 10, 100, 1000]


def augment(pos: pd.DataFrame, costs: atk.Costs, desc_len_log: float, k: int, seed: int) -> pd.DataFrame:
    """Huấn luyện có mẫu tấn công: k bản biến đổi ngẫu nhiên cho mỗi gói tấn công mô phỏng (chờ, làm giả miễn phí,
    mua sao/lượt tải). Ngày đăng ký không đổi nên đặc trưng mốc giữ nguyên."""
    import itertools

    rng = np.random.default_rng(seed)
    keys = list(atk.FREE_CHOICES)
    combos = [dict(zip(keys, v)) for v in itertools.product(*atk.FREE_CHOICES.values())]
    out = []
    for _ in range(k):
        w = rng.choice(AUG_WAITS, size=len(pos))
        c = rng.integers(0, len(combos), size=len(pos))
        b = rng.choice(AUG_BUDGETS, size=len(pos)).astype(float)
        f = rng.choice([0.0, 0.25, 0.5, 0.75, 1.0], size=len(pos))
        P = pos.reset_index(drop=False)
        parts = []
        for (wi, ci), idx in P.groupby([w, c]).groups.items():
            g = P.loc[idx].copy()
            g[META_COLS] = atk._apply_free(g[META_COLS], int(wi), desc_len_log, combos[ci])[META_COLS].values
            parts.append(g)
        A = pd.concat(parts).loc[P.index]
        A["log_stars"] = np.log1p(np.expm1(A["log_stars"]) + f * b / costs.usd_per_star)
        A["log_downloads"] = np.log1p(np.expm1(A["log_downloads"]) + (1 - f) * b / costs.usd_per_download)
        out.append(A.set_index(A.columns[0]))
    return pd.concat(out)


MIMIC_K = 20  # số hồ sơ gói thật kẻ tấn công thử cho mỗi tên (chọn hồ sơ cho điểm thấp nhất, trong ngân sách)


def mimic_scores(mdl, nfe: pd.DataFrame, base: pd.DataFrame, extra: pd.DataFrame, real: pd.DataFrame, costs: atk.Costs,
                 wait: int, budget: float, rng: np.random.Generator, age_override: float | None = None) -> np.ndarray:
    """Kẻ tấn công bắt chước gói thật (ngoài cách làm giả dùng khi huấn luyện): chép mọi metadata làm giả được từ một
    gói thật LLM gợi ý; tuổi = tuổi lúc đăng ký + thời gian chờ (hoặc age_override khi đăng ký trước mốc); kho GitHub
    không thể cũ hơn gói; sao và lượt tải (1 tháng) phải mua theo giá trong costs, vượt ngân sách thì không dùng được hồ sơ đó."""
    best = np.full(len(nfe), np.inf)
    age = (base["age_days"].values + wait) if age_override is None else np.full(len(nfe), age_override)
    for _ in range(MIMIC_K):
        P = real.iloc[rng.integers(0, len(real), size=len(nfe))][META_COLS].reset_index(drop=True)
        cost = np.expm1(P["log_stars"].values) * costs.usd_per_star + np.expm1(P["log_downloads"].values) * costs.usd_per_download
        X = P.copy()
        X.index = nfe.index
        X["age_days"] = age
        X["github_age_days"] = np.where(P["has_github"].values == 1, np.minimum(P["github_age_days"].values, age), -1.0)
        X["days_since_last_release"] = np.minimum(P["days_since_last_release"].values, age)
        s = mdl.score(nfe.join(extra).join(X[META_COLS]))
        best = np.where(cost <= budget, np.minimum(best, s), best)
    return best


def run(ds: Dataset, nf: NameFeaturizer, costs: atk.Costs, cutoffs: dict[str, pd.Timestamp], seed: int = 7,
        adversarial: bool = False, k: int = 3) -> dict:
    now = pd.Timestamp(ds.now)
    now = now.tz_convert(None) if now.tzinfo else now
    n = ds.names
    prof = ds.new_pkgs[ds.new_pkgs.half == "profile"]
    prof_tr = prof[[_bucket(x, "prof") < 0.5 for x in prof.index]]
    prof_te = prof[[_bucket(x, "prof") >= 0.5 for x in prof.index]]
    use = [m for m in MODELS if m in cutoffs]

    def rows(split: str, profiles: pd.DataFrame, s: int) -> pd.DataFrame:
        parts = []
        for i, m in enumerate(use):
            col = f"n_{SHORT[m]}"
            real = n[(n.label == "real") & n.age_days.notna() & (n[col] > 0) & (n.split == split)]
            hall = n[(n.label == "hallucinated_absent") & (n[col] > 0) & (n.split == split)]
            neg = nf.frame(list(real.index)).join(real[META_COLS])
            pos = nf.frame(list(hall.index)).join(_assign(list(hall.index), profiles, s + 17 * i))
            for d, y in ((neg, 0), (pos, 1)):
                d[CUT_COL] = _cut_feature(d["age_days"], now, cutoffs[m])
                d["y"], d["model"] = y, m
            parts += [neg, pos]
        return pd.concat(parts)

    tr, te = rows("train", prof_tr, seed), rows("test", prof_te, seed + 1)
    desc_len_log = float(np.median(n[(n.label == "real") & n.age_days.notna()]["log_description_len"]))
    if adversarial:
        aug = augment(tr[tr.y == 1], costs, desc_len_log, k, seed + 2)
        tr = pd.concat([tr, aug])
    fpr_sets = {"new_pkgs": ds.new_pkgs[ds.new_pkgs.half == "eval"], "random_pypi": ds.random_pkgs}
    res: dict = {
        "adversarial": adversarial,
        "rows": {"train": {"real": int((tr.y == 0).sum()), "simulated": int((tr.y == 1).sum())},
                 "test": {"real": int((te.y == 0).sum()), "simulated": int((te.y == 1).sum())}},
        "cutoffs": {SHORT[m]: str(cutoffs[m].date()) for m in use},
        "real_after_cutoff_share": {SHORT[m]: _r((te[(te.model == m) & (te.y == 0)][CUT_COL] > 0).mean()) for m in use},
        "models": {},
    }
    fitted = {}
    for mdl in [*models(), CutoffRule()]:
        mdl.fit(tr, tr["y"].values)
        s = mdl.score(te)
        neg, pos = s[te.y.values == 0], s[te.y.values == 1]
        thr = getattr(mdl, "fixed_threshold", None)
        thr = threshold_at_fpr(neg) if thr is None else thr
        r = {"auc": _r(auc(neg, pos)), "tpr_at_1pct_fpr": _r(rate(pos, thr)), "fpr_llm_real": _r(rate(neg, thr)),
             "fpr_llm_real_by_model": {SHORT[m]: _r(rate(s[(te.y.values == 0) & (te.model.values == m)], thr)) for m in use}}
        # Báo nhầm trên gói thật không do LLM gợi ý: coi như được từng model gợi ý, lấy trung bình.
        for key, df in fpr_sets.items():
            X = nf.frame(list(df.index)).join(df[META_COLS])
            r[f"fpr_{key}"] = _r(np.mean([rate(mdl.score(X.assign(**{CUT_COL: _cut_feature(X["age_days"], now, cutoffs[m])})), thr) for m in use]))
        r["tpr_by_model"] = {SHORT[m]: _r(rate(s[(te.y.values == 1) & (te.model.values == m)], thr)) for m in use}
        res["models"][mdl.name] = r
        fitted[mdl.name] = (mdl, thr)

    # Tấn công trên các biến thể đăng ký được, theo từng model mục tiêu.
    v = ds.variants
    status = n["registrable"].fillna(0).astype(bool)
    registrable = pd.Series({x: bool(status.get(x, False)) for x in v["variant"].unique()})
    attack: dict = {"pre_days": PRE_DAYS, "persistence": {SHORT[m]: p for m, p in PERSISTENCE.items()}, "by_model": {}}
    for name, (mdl, thr) in fitted.items():
        t0 = time.time()
        curves: dict[str, dict] = {}
        for m in use:
            vm = v[v.model_key == m]
            cand = [x for x in vm["variant"].unique() if registrable.get(x, False)]
            if not cand:
                continue
            nfe = nf.frame(cand)
            base = _assign(cand, prof_te, 99)
            # (a) đăng ký mới rồi chờ: ngày đăng ký cố định -> đặc trưng mốc theo tuổi hồ sơ lúc đăng ký.
            extra = pd.DataFrame({CUT_COL: _cut_feature(base["age_days"], now, cutoffs[m])}, index=cand)
            best = atk.fake_metadata(mdl, base, nfe, costs, desc_len_log, extra=extra)
            for (wait, budget), sc in best.items():
                if budget not in (0, 10, 1000):
                    continue
                key = f"đăng ký mới, chờ {wait} ngày, {budget:g} USD"
                curves.setdefault(key, {}).update(atk.evasion(vm, registrable, pd.Series(sc, index=cand) <= thr))
            # (b) đăng ký trước mốc PRE_DAYS ngày: tuổi lúc bị kiểm tra = now - (mốc - PRE_DAYS).
            pre = base.copy()
            pre["age_days"] = float((now - cutoffs[m]).days + PRE_DAYS)
            extra_pre = pd.DataFrame({CUT_COL: float(-PRE_DAYS)}, index=cand)
            best_pre = atk.fake_metadata(mdl, pre, nfe, costs, desc_len_log, extra=extra_pre, waits=[0])
            # (c) bắt chước gói thật (ngoài cách làm giả lúc huấn luyện), đăng ký mới rồi chờ / đăng ký trước mốc.
            real_m = te[(te.y == 0) & (te.model == m)]
            rng = np.random.default_rng(123)
            for wait in (0, 365):
                for budget in (0, 10, 1000):
                    sc = mimic_scores(mdl, nfe, base, extra, real_m, costs, wait, budget, rng)
                    curves.setdefault(f"bắt chước gói thật, đăng ký mới, chờ {wait} ngày, {budget:g} USD", {}).update(
                        atk.evasion(vm, registrable, pd.Series(sc, index=cand) <= thr))
            for budget in (0, 1000):
                sc = mimic_scores(mdl, nfe, base, extra_pre, real_m, costs, 0, budget, rng, age_override=float((now - cutoffs[m]).days + PRE_DAYS))
                ev = atk.evasion(vm, registrable, pd.Series(sc, index=cand) <= thr)
                curves.setdefault(f"bắt chước gói thật, đăng ký trước mốc {PRE_DAYS} ngày, {budget:g} USD (nếu tên còn được gợi ý)", {}).update(ev)
            for budget in (0, 1000):
                ev = atk.evasion(vm, registrable, pd.Series(best_pre[(0, budget)], index=cand) <= thr)
                key = f"đăng ký trước mốc {PRE_DAYS} ngày, {budget:g} USD (nếu tên còn được gợi ý)"
                curves.setdefault(key, {}).update(ev)
                if m in PERSISTENCE:
                    e = dict(ev[m])
                    e["evasion"] = _r(e["evasion"] * PERSISTENCE[m])
                    e["opportunity"] = _r(e["opportunity"] * PERSISTENCE[m])
                    curves.setdefault(f"đăng ký trước mốc {PRE_DAYS} ngày, {budget:g} USD (kỳ vọng, nhân tỷ lệ tên còn được gợi ý)", {})[m] = e
        attack["by_model"][name] = curves
        log.info("tấn công (mốc) %s: %.0f giây", name, time.time() - t0)
    res["attack"] = attack
    return res


def to_md(res: dict) -> str:
    short = list(res["cutoffs"])
    title = "Tầng 2 với đặc trưng mốc dữ liệu" + (", huấn luyện có mẫu tấn công" if res.get("adversarial") else "")
    L = [f"\n## {title} (ngày đăng ký so với mốc của model đã gợi ý)\n",
         f"Mốc: {res['cutoffs']}. Mỗi dòng là một cặp (gói, model gợi ý). Train {res['rows']['train']}, test {res['rows']['test']}.",
         f"Tỷ lệ gói thật (test) ra đời sau mốc của model đã gợi ý nó: {res['real_after_cutoff_share']}.\n",
         "| Mô hình | AUC | Phát hiện | Báo nhầm gói thật LLM gợi ý (theo model) | Báo nhầm gói mới | Báo nhầm gói ngẫu nhiên | Phát hiện theo model |",
         "|---|---|---|---|---|---|---|"]
    for k, r in res["models"].items():
        L.append(f"| {k} | {r['auc']} | {r['tpr_at_1pct_fpr']} | {r['fpr_llm_real']} {r['fpr_llm_real_by_model']} | {r['fpr_new_pkgs']} | {r['fpr_random_pypi']} | {r['tpr_by_model']} |")
    a = res["attack"]
    L.append(f"\nTấn công (tỷ lệ né; cơ hội = chỉ cần đăng ký được). Tỷ lệ tên còn được gợi ý ở phiên bản khác: {a['persistence']}.\n")
    model_keys = [m for m in MODELS if SHORT[m] in short]
    for name, curves in a["by_model"].items():
        L.append(f"\n### {name}\n")
        L.append("| Kịch bản | " + " | ".join(SHORT[m] for m in model_keys) + " |")
        L.append("|---|" + "---|" * len(model_keys))
        for k, r in curves.items():
            L.append(f"| {k} | " + " | ".join(str(r.get(m, {}).get("evasion", "")) for m in model_keys) + " |")
    return "\n".join(L) + "\n"
