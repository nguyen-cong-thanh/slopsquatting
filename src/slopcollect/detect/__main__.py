"""Chạy thử nghiệm bộ phát hiện + tấn công sơ bộ, ghi kết quả JSON và Markdown.

  .venv/bin/python -m slopcollect.detect --db data/slop.sqlite --out data/exports/detector
"""

from __future__ import annotations

import argparse
import json
import logging
import pickle
import sqlite3
import time
from pathlib import Path

import numpy as np
import pandas as pd

from slopcollect.detect import attack as atk
from slopcollect.detect.data import META_COLS, MODELS, SHORT, Dataset, _bucket, describe, load
from slopcollect.detect.models import NameFeaturizer, auc, name_only_models, rate, threshold_at_fpr, tier2_models

log = logging.getLogger("slopdetect")


def _r(x: float) -> float:
    return round(float(x), 4)


def assign_profiles(names: list[str], profiles: pd.DataFrame, seed: int) -> pd.DataFrame:
    """Gán cho mỗi tên bịa một hồ sơ metadata của một gói mới thật (lấy ngẫu nhiên có lặp, cố định theo seed)."""
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(profiles), size=len(names))
    out = profiles.iloc[idx][META_COLS].copy()
    out.index = names
    return out


def name_only(ds: Dataset, nf: NameFeaturizer) -> dict:
    """Bản chỉ dùng tên: tên bịa (mọi loại) với tên thật, cùng lấy từ câu trả lời LLM."""
    n = ds.names[ds.names.label.isin(["real", "hallucinated_absent", "registered_hallucination"])]
    feats = nf.frame(list(n.index))
    X = feats.join(n[["y", "split", "n_llama", "n_deepseek"]])
    res: dict = {}
    for m in name_only_models():
        tr, te = X[X.split == "train"], X[X.split == "test"]
        m.fit(tr, tr["y"].values)
        s = m.score(te)
        neg, pos = s[te.y.values == 0], s[te.y.values == 1]
        thr = threshold_at_fpr(neg)
        r = {"auc": _r(auc(neg, pos)), "tpr_at_1pct_fpr": _r(rate(pos, thr)), "test_real": int(len(neg)), "test_hallucinated": int(len(pos))}
        # Báo nhầm trên tên gói thật không do LLM gợi ý.
        for key, df in (("fpr_new_pkgs", ds.new_pkgs[ds.new_pkgs.half == "eval"]), ("fpr_random_pypi", ds.random_pkgs)):
            r[key] = _r(rate(m.score(nf.frame(list(df.index))), thr))
        # Kiểm thử chéo: huấn luyện trên tên của LLM này, kiểm thử trên tên chỉ LLM kia gợi ý.
        for a, b in (("llama", "deepseek"), ("deepseek", "llama")):
            tr_ab = tr[tr[f"n_{a}"] > 0]
            te_ab = te[(te[f"n_{b}"] > 0) & (te[f"n_{a}"] == 0) | ((te.y == 0) & (te[f"n_{b}"] > 0))]
            mm = type(m)(m.name, m.kind, m.features).fit(tr_ab, tr_ab["y"].values)
            s2 = mm.score(te_ab)
            n2, p2 = s2[te_ab.y.values == 0], s2[te_ab.y.values == 1]
            r[f"cross_{a}_to_{b}"] = {"auc": _r(auc(n2, p2)), "tpr_at_1pct_fpr": _r(rate(p2, threshold_at_fpr(n2))), "test_hallucinated": int(len(p2))}
        res[m.name] = r
        res[m.name]["_model"] = m
        res[m.name]["_thr"] = thr
    return res


def tier2(ds: Dataset, nf: NameFeaturizer, seed: int = 7) -> dict:
    """Tầng 2: gói có trên PyPI. Âm: gói thật LLM gợi ý (metadata thật). Dương: tên bịa, giả định kẻ tấn công vừa
    đăng ký, metadata lấy từ một gói mới thật (mô phỏng). Ngưỡng đặt ở mức báo nhầm 1% gói thật LLM gợi ý (test)."""
    n = ds.names
    prof = ds.new_pkgs[ds.new_pkgs.half == "profile"]
    prof_tr = prof[[_bucket(x, "prof") < 0.5 for x in prof.index]]
    prof_te = prof[[_bucket(x, "prof") >= 0.5 for x in prof.index]]

    real = n[(n.label == "real") & n.age_days.notna()]
    hall = n[n.label == "hallucinated_absent"]
    observed = n[(n.label == "registered_hallucination") & n.age_days.notna()]

    def build(split: str, profiles: pd.DataFrame, s: int) -> pd.DataFrame:
        r = real[real.split == split]
        h = hall[hall.split == split]
        neg = nf.frame(list(r.index)).join(r[META_COLS])
        pos = nf.frame(list(h.index)).join(assign_profiles(list(h.index), profiles, s))
        neg["y"], pos["y"] = 0, 1
        return pd.concat([neg, pos])

    tr, te = build("train", prof_tr, seed), build("test", prof_te, seed + 1)
    sets = {
        "new_pkgs": nf.frame(list(ds.new_pkgs[ds.new_pkgs.half == "eval"].index)).join(ds.new_pkgs[ds.new_pkgs.half == "eval"][META_COLS]),
        "random_pypi": nf.frame(list(ds.random_pkgs.index)).join(ds.random_pkgs[META_COLS]),
        "observed": nf.frame(list(observed.index)).join(observed[META_COLS]),
    }
    res: dict = {"train": {"real": int((tr.y == 0).sum()), "simulated": int((tr.y == 1).sum())},
                 "test": {"real": int((te.y == 0).sum()), "simulated": int((te.y == 1).sum())},
                 "observed_registered_hallucinations": int(len(sets["observed"]))}
    for m in tier2_models():
        m.fit(tr, tr["y"].values)
        s = m.score(te)
        neg, pos = s[te.y.values == 0], s[te.y.values == 1]
        thr = threshold_at_fpr(neg)
        res[m.name] = {
            "auc": _r(auc(neg, pos)),
            "tpr_at_1pct_fpr": _r(rate(pos, thr)),
            "fpr_new_pkgs": _r(rate(m.score(sets["new_pkgs"]), thr)),
            "fpr_random_pypi": _r(rate(m.score(sets["random_pypi"]), thr)),
            "detect_observed": _r(rate(m.score(sets["observed"]), thr)) if len(sets["observed"]) else None,
            "_model": m,
            "_thr": thr,
        }
    res["_prof_te"] = prof_te
    res["_desc_len_log"] = float(np.median(real["log_description_len"]))
    return res


def run_attack(ds: Dataset, nf: NameFeaturizer, t2: dict, names_res: dict, costs: atk.Costs) -> dict:
    v = ds.variants
    status = ds.names["registrable"].fillna(0).astype(bool)
    # Tên chưa có trong bảng names (chưa gắn nhãn) coi như không đăng ký được.
    registrable = pd.Series({x: bool(status.get(x, False)) for x in v["variant"].unique()})
    cand = [x for x in registrable.index if registrable[x]]
    nfe = nf.frame(cand)
    out: dict = {"variants_registrable": len(cand), "variants_total": int(len(registrable)), "costs": costs.__dict__}

    # Bản chỉ dùng tên: kẻ tấn công không cần làm giả gì, chỉ chọn biến thể mô hình không bắt.
    out["name_only"] = {}
    for name, r in names_res.items():
        sc = pd.Series(r["_model"].score(nfe), index=cand)
        out["name_only"][name] = atk.evasion(v, registrable, sc <= r["_thr"])

    base = assign_profiles(cand, t2["_prof_te"], 99)
    out["tier2"] = {}
    for name in ("tên + metadata (GB)", "tên + metadata (LR)", "chỉ metadata (GB)", "tên + metadata trừ tuổi (GB)"):
        r = t2[name]
        t0 = time.time()
        fresh = pd.Series(r["_model"].score(nfe.join(base[META_COLS])), index=cand)
        curves = {"no_faking": atk.evasion(v, registrable, fresh <= r["_thr"])}
        best = atk.fake_metadata(r["_model"], base, nfe, costs, t2["_desc_len_log"])
        for (wait, budget), s in best.items():
            curves[f"wait{wait}_usd{budget:g}"] = atk.evasion(v, registrable, pd.Series(s, index=cand) <= r["_thr"])
        out["tier2"][name] = curves
        log.info("tấn công %s: %.0f giây", name, time.time() - t0)
    return out


def _md(res: dict) -> str:
    L = ["# Thử nghiệm bộ phát hiện và tấn công (sơ bộ)\n", f"Snapshot PyPI `{res['data']['snapshot_id']}`. Ngưỡng của mọi mô hình: báo nhầm 1% tên thật do LLM gợi ý (tập test).\n"]
    L.append("## Dữ liệu\n\n```json\n" + json.dumps(res["data"], ensure_ascii=False, indent=2) + "\n```\n")
    L.append("## Chỉ dùng tên: tên bịa và tên thật\n")
    L.append("| Mô hình | AUC | Phát hiện @1% báo nhầm | Báo nhầm gói mới | Báo nhầm gói ngẫu nhiên | Llama→DeepSeek | DeepSeek→Llama |")
    L.append("|---|---|---|---|---|---|---|")
    for k, r in res["name_only"].items():
        L.append(f"| {k} | {r['auc']} | {r['tpr_at_1pct_fpr']} | {r['fpr_new_pkgs']} | {r['fpr_random_pypi']} | "
                 f"{r['cross_llama_to_deepseek']['tpr_at_1pct_fpr']} | {r['cross_deepseek_to_llama']['tpr_at_1pct_fpr']} |")
    t = res["tier2"]
    L.append(f"\n## Tầng 2: gói có trên PyPI\n\nTrain {t['train']}, test {t['test']}; tên bịa đã có người đăng ký (thật): {t['observed_registered_hallucinations']}.\n")
    L.append("| Mô hình | AUC | Phát hiện @1% báo nhầm | Báo nhầm gói mới | Báo nhầm gói ngẫu nhiên | Bắt tên bịa đã đăng ký thật |")
    L.append("|---|---|---|---|---|---|")
    for k, r in t.items():
        if isinstance(r, dict) and "auc" in r:
            L.append(f"| {k} | {r['auc']} | {r['tpr_at_1pct_fpr']} | {r['fpr_new_pkgs']} | {r['fpr_random_pypi']} | {r['detect_observed']} |")
    a = res["attack"]
    L.append(f"\n## Tấn công sát thực tế\n\nBiến thể đăng ký được: {a['variants_registrable']}/{a['variants_total']}. Chi phí: {a['costs']}.\n")
    L.append("Tỷ lệ né = trung bình trên các câu hỏi đã chọn của tỷ lệ lần hỏi mà LLM gợi ý ít nhất một tên kẻ tấn công đã đăng ký và bộ phát hiện không cảnh báo. "
             "Cơ hội = như trên nhưng không có bộ phát hiện (chỉ cần đăng ký được).\n")
    for name, r in a["name_only"].items():
        L.append(f"- Chỉ dùng tên, {name}: " + ", ".join(f"{SHORT[m]} {x['evasion']} (cơ hội {x['opportunity']})" for m, x in r.items()))
    for name, curves in a["tier2"].items():
        L.append(f"\n### {name}\n")
        L.append("| Kịch bản | " + " | ".join(SHORT[m] for m in MODELS) + " |")
        L.append("|---|" + "---|" * len(MODELS))
        for k, r in curves.items():
            L.append(f"| {k} | " + " | ".join(str(r.get(m, {}).get("evasion", "")) for m in MODELS) + " |")
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/slop.sqlite")
    ap.add_argument("--out", default="data/exports/detector")
    ap.add_argument("--reuse", action="store_true", help="dùng lại bảng dữ liệu đã dựng (dataset.pkl) thay vì đọc lại CSDL")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    t0 = time.time()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cache = out / "dataset.pkl"
    if args.reuse and cache.exists():
        ds = pickle.loads(cache.read_bytes())
    else:
        ds = load(args.db)
        cache.write_bytes(pickle.dumps(ds))
    log.info("dữ liệu: %s", json.dumps(describe(ds), ensure_ascii=False))
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True, timeout=120)
    pypi = {r[0] for r in conn.execute("SELECT norm_name FROM pypi_index WHERE snapshot_id = ?", (ds.snapshot_id,))}
    conn.close()
    nf = NameFeaturizer(pypi)
    names_res = name_only(ds, nf)
    log.info("chỉ dùng tên xong (%.0f giây)", time.time() - t0)
    t2 = tier2(ds, nf)
    log.info("tầng 2 xong (%.0f giây)", time.time() - t0)
    attack_res = run_attack(ds, nf, t2, names_res, atk.Costs())
    clean = lambda d: {k: (clean(v) if isinstance(v, dict) else v) for k, v in d.items() if not k.startswith("_")}  # noqa: E731
    res = {"data": describe(ds), "name_only": clean(names_res), "tier2": clean(t2), "attack": attack_res}
    (out / "results.json").write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (out / "results.md").write_text(_md(res), encoding="utf-8")
    log.info("xong (%.0f giây): %s", time.time() - t0, out / "results.md")


if __name__ == "__main__":
    main()
