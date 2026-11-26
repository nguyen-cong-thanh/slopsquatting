"""Bước label: gắn nhãn cho từng tên gói bằng chuỗi luật áp theo thứ tự (luật đầu tiên khớp sẽ quyết định).

Nhãn:
  real                      gói thật: có code khớp mô tả, đã duyệt (chỉ đến từ overrides)
  pre_cutoff_unverified     có trên PyPI, lọt lưới lọc (có từ trước mốc dữ liệu của mọi model đã gợi ý nó), chưa kiểm
                            nội dung; không thể là tên bịa đã bị đăng ký, nhưng cũng không được coi là gói thật
  hallucinated_absent       tên không có trên PyPI (tầng 1 bắt được)
  registered_hallucination  tên có trên PyPI nhưng nghi do người khác đăng ký theo tên bịa (lớp đáng ngờ)
  placeholder               bản giữ chỗ / phòng vệ trỏ sang gói đúng
  known_malicious           có trong danh sách gói độc hại đã biết
  stdlib                    tên module thư viện chuẩn (json, os...): không phải tên bịa, PyPI cấm đăng ký
  unlabeled                 có trên PyPI nhưng chưa có metadata để quyết định
  uncertain                 duyệt tay không kết luận được (quy trình P2, docs/du-lieu/quy-trinh-gan-nhan-thu-cong.md);
                            chỉ đến từ overrides, bị loại khỏi phân tích chính

Các nhãn đoán bằng heuristic được đánh dấu needs_review và xuất ra CSV để duyệt tay. Kết quả duyệt
(cột override_label) được đọc lại qua tham số overrides_csv và áp trước mọi luật khác.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from slopcollect import registry
from slopcollect.db import latest_snapshot
from slopcollect.registry import register
from slopcollect.timing import load_cutoffs, released_before, timing
from slopcollect.util import parse_time, utcnow

DEFAULT_RULES = [
    "override",
    "known_malicious",
    "stdlib_name",
    "absent",
    "missing_metadata",
    "empty_project",
    "placeholder",
    "known_hallucination",
    "after_cutoff",
    "after_model_cutoff",
    "young_low_downloads",
    "pre_cutoff",
]

DEFAULT_PLACEHOLDER_PATTERNS = [
    r"\bdeprecated\b",
    r"\bdummy\b",
    r"\bplace ?holder\b",
    r"\buse [\w.\-]+ instead\b",
    r"\binstall [\w.\-]+ instead\b",
    r"\b(?:has been|was) renamed\b",
    r"\bpoints? to\b",
    r"\breserved\b",
    r"\bsecurity holding\b",
    r"\bdo not (?:use|install)\b",
    r"\bnot the package you\b",
]

# rules-v3 (từ 26/11/2026, quy trình P3): after_model_cutoff chỉ còn là lưới lọc dùng chung tiêu chí thời gian với cây
# quyết định duyệt tay (slopcollect.timing), không tự quyết nhãn nữa. Tên phiên bản giữ nguyên để các phân tích đã có
# đọc nhãn mới; lịch sử thay đổi ở mục 8 của tài liệu quy trình.
# rules-v3 (14/11/2026): thêm after_model_cutoff (gói ra đời sau mốc dữ liệu của mọi model đã gợi ý nó).
# rules-v1: bản đầu. rules-v2: gói thật chỉ bị chiếm quyền vài phiên bản không còn là known_malicious;
# luật placeholder chỉ xét tóm tắt và mô tả ngắn (bản v1 sai khoảng 95% trên mẫu duyệt tay).
LABELER_VERSION = "rules-v3"

LABELS = {"real", "pre_cutoff_unverified", "hallucinated_absent", "registered_hallucination", "placeholder", "known_malicious", "unlabeled", "stdlib", "uncertain"}

Verdict = tuple[str, bool, dict[str, Any]]


@register("label_rule", "override")
def rule_override(info: dict[str, Any], cfg: dict[str, Any]) -> Verdict | None:
    ov = info.get("override")
    return (ov["label"], False, {"note": ov.get("note", "")}) if ov else None


@register("label_rule", "known_malicious")
def rule_known_malicious(info: dict[str, Any], cfg: dict[str, Any]) -> Verdict | None:
    hit = sorted(set(info["lists"]) & set(cfg["malicious_lists"]))
    if not hit:
        return None
    # Gói thật bị chiếm quyền vài phiên bản (litellm, ultralytics...): danh sách chỉ ghi các phiên bản đó,
    # gói vẫn còn trên PyPI với nhiều phiên bản khác. Không coi là gói độc hại; ghi lại làm bằng chứng.
    bad: set[str] = set()
    for lid in hit:
        versions = (info["lists"].get(lid) or {}).get("versions")
        if not versions:  # None hoặc rỗng: mọi phiên bản
            return ("known_malicious", False, {"lists": hit})
        bad |= set(versions)
    n_releases = info["features"].get("n_releases") or 0
    if info["status"]["exists_on_pypi"] and n_releases > len(bad):
        info["compromised"] = {"compromised_versions": sorted(bad), "lists": hit}
        return None
    return ("known_malicious", False, {"lists": hit, "versions": sorted(bad)})


@register("label_rule", "stdlib_name")
def rule_stdlib_name(info: dict[str, Any], cfg: dict[str, Any]) -> Verdict | None:
    # LLM liệt kê module thư viện chuẩn (json, os, subprocess) như một gói: không phải tên bịa,
    # và PyPI cấm đăng ký các tên này nên không bị lợi dụng.
    st = info["status"]
    if not st["exists_on_pypi"] and st["reason"] == "stdlib":
        return ("stdlib", False, {})
    return None


@register("label_rule", "absent")
def rule_absent(info: dict[str, Any], cfg: dict[str, Any]) -> Verdict | None:
    st = info["status"]
    if st["exists_on_pypi"]:
        return None
    return ("hallucinated_absent", False, {"registrable": bool(st["registrable"]), "reason": st["reason"], "similar_to": st["similar_to"]})


@register("label_rule", "missing_metadata")
def rule_missing_metadata(info: dict[str, Any], cfg: dict[str, Any]) -> Verdict | None:
    return ("unlabeled", True, {"why": "chưa có metadata (chạy bước metadata)"}) if not info["features"] else None


@register("label_rule", "empty_project")
def rule_empty_project(info: dict[str, Any], cfg: dict[str, Any]) -> Verdict | None:
    f = info["features"]
    if f.get("n_files") == 0:
        return ("placeholder", True, {"why": "project không có file phát hành nào"})
    return None


@register("label_rule", "placeholder")
def rule_placeholder(info: dict[str, Any], cfg: dict[str, Any]) -> Verdict | None:
    # Chỉ xét phần tóm tắt, và phần mô tả khi mô tả rất ngắn: README dài của gói thật hay có chữ
    # "deprecated"/"reserved" ở đâu đó (peft, natsort, amqp...), không có nghĩa gói là bản giữ chỗ.
    desc = (info.get("description") or "").strip()
    text = f"{info['features'].get('summary') or ''}\n{desc if len(desc) <= cfg['placeholder_max_desc'] else ''}".lower()
    for pat in cfg["placeholder_patterns"]:
        m = re.search(pat, text)
        if m:
            return ("placeholder", True, {"matched": m.group(0), "summary": info["features"].get("summary")})
    return None


@register("label_rule", "known_hallucination")
def rule_known_hallucination(info: dict[str, Any], cfg: dict[str, Any]) -> Verdict | None:
    hit = sorted(set(info["lists"]) & set(cfg["hallucination_lists"]))
    return ("registered_hallucination", True, {"lists": hit}) if hit else None


@register("label_rule", "after_cutoff")
def rule_after_cutoff(info: dict[str, Any], cfg: dict[str, Any]) -> Verdict | None:
    cutoff = parse_time(cfg.get("cutoff_date"))
    first = parse_time(info["features"].get("first_release_at"))
    if cutoff and first and first > cutoff:
        return ("registered_hallucination", True, {"first_release_at": info["features"]["first_release_at"], "cutoff_date": cfg["cutoff_date"]})
    return None


@register("label_rule", "after_model_cutoff")
def rule_after_model_cutoff(info: dict[str, Any], cfg: dict[str, Any]) -> Verdict | None:
    """Lưới lọc theo thời gian (quy trình P3, bước 2): đưa đi duyệt tay mọi tên mà tiêu chí thời gian của cây quyết định
    không kết luận được là "có từ trước mốc" (slopcollect.timing, dùng chung với review.evidence). Luật chỉ lọc, không
    quyết định: nhãn tạm là registered_hallucination, needs_review, và nhãn cuối do người duyệt ghi vào overrides.

    Tên lọt qua lưới (timing = before) có từ trước mốc của mọi model đã gợi ý nó, nên không thể là tên bị chiếm.
    """
    cut = cfg.get("cutoffs")
    models = info.get("models") or set()
    if not cut or not any(m in cut.date for m in models):
        return None  # không model nào có mốc trong configs/cutoffs.toml (vd model giả khi test): luật không áp dụng
    f = info["features"]
    first = parse_time(f.get("first_release_at"))
    verdict, pre = timing(first, models, cut, margin_days=cfg["cutoff_margin_days"])
    if verdict == "before":
        return None
    ev: dict[str, Any] = {"timing": verdict, "first_release_at": f.get("first_release_at"), "models": sorted(models),
                          "pre_registration_models": pre, "released_before_upload": released_before(first, models, cut)}
    return ("registered_hallucination", True, ev)


@register("label_rule", "young_low_downloads")
def rule_young_low_downloads(info: dict[str, Any], cfg: dict[str, Any]) -> Verdict | None:
    f = info["features"]
    first = parse_time(f.get("first_release_at"))
    if not first:
        return None
    young = datetime.now(timezone.utc) - first < timedelta(days=cfg["young_days"])
    dl = f.get("downloads_last_month")
    low = dl is None or dl <= cfg["max_downloads_last_month"]
    if young and low:
        return ("registered_hallucination", True, {"first_release_at": f.get("first_release_at"), "downloads_last_month": dl})
    return None


@register("label_rule", "pre_cutoff")
def rule_pre_cutoff(info: dict[str, Any], cfg: dict[str, Any]) -> Verdict | None:
    """Luật cuối: tên có trên PyPI không bị lưới lọc giữ lại. Không kiểm nội dung (quyết định 26/11/2026), nên không gọi là real."""
    return ("pre_cutoff_unverified", False, info.get("compromised") or {})


def _read_overrides(path: Any) -> dict[str, dict[str, str]]:
    out = {}
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            lab = (row.get("override_label") or "").strip()
            if not lab:
                continue
            if lab not in LABELS:
                raise ValueError(f"{path}: override_label '{lab}' không hợp lệ (hợp lệ: {sorted(LABELS)})")
            out[row["norm_name"]] = {"label": lab, "note": row.get("note", "")}
    return out


REVIEW_COLUMNS = [
    "norm_name", "label", "rule", "summary", "first_release_at", "downloads_last_month", "n_owners",
    "n_releases", "lists", "evidence", "pypi_url", "override_label", "note",
]


@register("stage", "label")
def label(
    ctx: Any,
    labeler_version: str = LABELER_VERSION,
    rules: list[str] | None = None,
    snapshot: str = "latest",
    names_from: str = "mentions",
    cutoff_date: str | None = None,
    young_days: int = 180,
    max_downloads_last_month: int = 1000,
    placeholder_max_desc: int = 400,
    placeholder_patterns: list[str] | None = None,
    hallucination_lists: list[str] | None = None,
    malicious_lists: list[str] | None = None,
    overrides_csv: str | None = "data/review/overrides.csv",
    cutoffs_file: str | None = "configs/cutoffs.toml",
    cutoff_margin_days: int = 30,
    review_csv: str | None = "data/review/needs_review.csv",
) -> dict[str, Any]:
    """Gắn nhãn cho mọi tên đã kiểm tra trong snapshot.

    Quy trình duyệt tay: mở review_csv, điền cột override_label (và note) cho các dòng đã xem,
    lưu thành overrides_csv (file riêng, để lần chạy sau không ghi đè), rồi chạy lại bước label.
    """
    conn = ctx.conn
    sid = latest_snapshot(conn) if snapshot == "latest" else snapshot
    if not sid:
        raise RuntimeError("Chưa có snapshot PyPI: chạy pypi_index và check trước")
    cfg = {
        "cutoff_date": cutoff_date,
        "young_days": young_days,
        "max_downloads_last_month": max_downloads_last_month,
        "placeholder_patterns": placeholder_patterns or DEFAULT_PLACEHOLDER_PATTERNS,
        "placeholder_max_desc": placeholder_max_desc,
        "cutoffs": load_cutoffs(ctx.path(cutoffs_file)) if cutoffs_file and ctx.path(cutoffs_file).exists() else None,
        "cutoff_margin_days": cutoff_margin_days,
        "hallucination_lists": hallucination_lists or ["0pstech", "depscope"],
        "malicious_lists": malicious_lists or ["datadog", "osv_malicious"],
    }
    rule_fns = [(r, registry.get("label_rule", r)) for r in (rules or DEFAULT_RULES)]
    overrides = _read_overrides(ctx.path(overrides_csv)) if overrides_csv and ctx.path(overrides_csv).exists() else {}

    lists: dict[str, dict[str, dict[str, Any]]] = {}  # tên -> {list_id: extra}
    for r in conn.execute("SELECT norm_name, list_id, extra_json FROM known_lists"):
        lists.setdefault(r[0], {})[r[1]] = json.loads(r[2]) if r[2] else {}
    features = {r["norm_name"]: dict(r) for r in conn.execute("SELECT * FROM package_features")}
    descriptions: dict[str, str] = {}
    versions: dict[str, str] = {}
    for r in conn.execute("SELECT norm_name, raw_json FROM metadata_raw WHERE source = 'pypi_json' AND raw_json IS NOT NULL"):
        inf = json.loads(r[1]).get("info", {})
        descriptions[r[0]] = (inf.get("description") or "")[:3000]
        versions[r[0]] = inf.get("version") or ""
    # Model nào đã gợi ý mỗi tên (cho luật after_model_cutoff).
    suggested_by: dict[str, set[str]] = {}
    for r in conn.execute("SELECT DISTINCT m.norm_name, g.model_key FROM mentions m JOIN generations g ON g.gen_id = m.gen_id"):
        suggested_by.setdefault(r[0], set()).add(r[1])

    q = "SELECT * FROM package_status ps WHERE ps.snapshot_id = ?"
    if names_from == "mentions":
        q += " AND EXISTS (SELECT 1 FROM mentions m WHERE m.norm_name = ps.norm_name)"
    elif names_from != "all":
        raise ValueError("names_from phải là 'mentions' hoặc 'all'")
    statuses = conn.execute(q, (sid,)).fetchall()
    counts: dict[str, int] = {}
    review_rows = []
    now = utcnow()
    with conn:
        for st in statuses:
            n = st["norm_name"]
            info = {
                "norm_name": n,
                "status": st,
                "features": features.get(n, {}),
                "lists": lists.get(n, {}),
                "override": overrides.get(n),
                "description": descriptions.get(n),
                "version": versions.get(n),
                "models": suggested_by.get(n, set()),
            }
            for rule_name, fn in rule_fns:
                verdict = fn(info, cfg)
                if verdict:
                    break
            else:
                raise RuntimeError("Không luật nào khớp: thêm luật 'pre_cutoff' vào cuối danh sách rules")
            lab, review, evidence = verdict
            if lab not in LABELS:
                raise ValueError(f"Luật {rule_name} trả nhãn không hợp lệ: {lab}")
            counts[lab] = counts.get(lab, 0) + 1
            conn.execute(
                "INSERT OR REPLACE INTO labels(norm_name, labeler_version, label, rule, needs_review, evidence_json, run_id, labeled_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (n, labeler_version, lab, rule_name, int(review), json.dumps(evidence, ensure_ascii=False, default=str), ctx.run_id, now),
            )
            if review:
                f = info["features"]
                review_rows.append(
                    {
                        "norm_name": n,
                        "label": lab,
                        "rule": rule_name,
                        "summary": f.get("summary"),
                        "first_release_at": f.get("first_release_at"),
                        "downloads_last_month": f.get("downloads_last_month"),
                        "n_owners": f.get("n_owners"),
                        "n_releases": f.get("n_releases"),
                        "lists": ";".join(sorted(info["lists"])),
                        "evidence": json.dumps(evidence, ensure_ascii=False, default=str),
                        "pypi_url": f"https://pypi.org/project/{n}/",
                        "override_label": "",
                        "note": "",
                    }
                )
    if review_csv:
        path = ctx.path(review_csv)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=REVIEW_COLUMNS)
            w.writeheader()
            w.writerows(sorted(review_rows, key=lambda r: (r["label"], r["norm_name"])))
    return {"snapshot_id": sid, "labeler_version": labeler_version, "labels": counts, "needs_review": len(review_rows), "overrides": len(overrides)}
