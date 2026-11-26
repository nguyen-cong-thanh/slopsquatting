"""Tiêu chí thời gian dùng chung cho lưới lọc (bước label) và cây quyết định duyệt tay (review.evidence).

Hai nơi phải gọi cùng một hàm để một tên không thể lọt lưới mà theo cây quyết định lại là tên đáng ngờ
(quy trình P3, docs/du-lieu/quy-trinh-gan-nhan-thu-cong.md, mục 1 và 5).

Câu hỏi: model đã nói ra cái tên này trước khi có người đăng ký nó trên PyPI chưa?
  after   có ít nhất một model đã gợi ý tên mà mốc dữ liệu + MARGIN_DAYS sớm hơn lần tải lên đầu tiên
  before  gói có từ trước mốc của mọi model đã gợi ý nó (model có thể đã thấy tên trên PyPI)
  unknown không kết luận được (thiếu ngày tải lên, model chưa rõ mốc, hoặc mốc chỉ là giới hạn trên)

Ngoài mốc dữ liệu (ước lượng, có thể lệch), còn có ngày phát hành model (released): trọng số không thể chứa dữ
liệu sinh ra sau ngày đó, nên gói ra đời sau ngày phát hành của một model đã gợi ý tên là bằng chứng chắc chắn.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

MARGIN_DAYS = 30


def _d(s: str) -> datetime:
    return datetime.fromisoformat(str(s)).replace(tzinfo=timezone.utc)


@dataclass
class Cutoffs:
    date: dict[str, datetime] = field(default_factory=dict)  # mốc dữ liệu
    upper: set[str] = field(default_factory=set)  # mốc chỉ là giới hạn trên
    released: dict[str, datetime] = field(default_factory=dict)  # ngày phát hành trọng số

    @property
    def floor(self) -> datetime | None:
        """Mốc sớm nhất đã biết chính xác (không phải giới hạn trên); giả định mốc thật của mọi model không sớm hơn."""
        exact = [v for k, v in self.date.items() if k not in self.upper]
        return min(exact) if exact else None


def load_cutoffs(path: str | Path) -> Cutoffs:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    return Cutoffs(
        date={m: _d(v["date"]) for m, v in data.items()},
        upper={m for m, v in data.items() if v.get("bound") == "upper"},
        released={m: _d(v["released"]) for m, v in data.items() if v.get("released")},
    )


def timing(first: datetime | None, models: Iterable[str], cut: Cutoffs, legacy: bool = False,
           exists_by: datetime | None = None, margin_days: int = MARGIN_DAYS) -> tuple[str, list[str]]:
    """(after | before | unknown, các model có mốc + đệm sớm hơn lần tải lên đầu tiên).

    legacy: dự án chỉ có metadata, chưa từng có lần tải lên (chỉ sinh ra trên PyPI cũ, trước 04/2018) -> before.
    exists_by: khi không biết ngày tải lên đầu tiên, một ngày mà dự án chắc chắn đã tồn tại (ngày của sự kiện cuối cùng
    trên PyPI, ước từ _last-serial). Chỉ dùng để kết luận before: dự án có thể đã ra đời sớm hơn nhiều, nên không
    chứng minh được after.
    """
    ms = sorted(set(models))
    if legacy:
        return "before", []
    if not first and exists_by:
        v, _ = timing(exists_by, ms, cut, margin_days=margin_days)
        return ("before", []) if v == "before" else ("unknown", [])
    known = [m for m in ms if m in cut.date]
    if not first or not known:
        return "unknown", []
    pre = [m for m in known if first > cut.date[m] + timedelta(days=margin_days)]
    if pre:
        return "after", pre
    if len(known) < len(ms):
        return "unknown", []  # có model chưa rõ mốc
    floor = cut.floor
    if any(m in cut.upper for m in known) and (floor is None or first > floor):
        return "unknown", []  # mốc chỉ là giới hạn trên: không chứng minh được gói có trước mốc thật
    return "before", []


def released_before(first: datetime | None, models: Iterable[str], cut: Cutoffs) -> list[str]:
    """Các model đã gợi ý tên mà được phát hành trước lần tải lên đầu tiên của gói (bằng chứng chắc chắn)."""
    if not first:
        return []
    return sorted(m for m in set(models) if m in cut.released and first > cut.released[m])
