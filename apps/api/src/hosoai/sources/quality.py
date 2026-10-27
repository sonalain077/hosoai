"""Sanity checks on parsed official pages.

Some portal pages are broken at the source (e.g. the fee box shows the processing time).
We never show such text as if it were the official fee: we drop it and say why, quoting
the original so a human can check.
"""

import re

from hosoai.procedures.models import Procedure

_DAYS = re.compile(r"ngày làm việc", re.IGNORECASE)
_BARE_NUMBER = re.compile(r"^\s*\d{1,3}\s*$")
_MONEY = re.compile(r"\d[\d.,]*\s*(đồng|đ\b|vnđ|vnd|usd)", re.IGNORECASE)
_METHODS_ONLY = ("trực tiếp trực tuyến", "trực tiếp", "trực tuyến")


def fee_problem(text: str) -> str | None:
    """Why this fee text can't be a fee, or None if it looks plausible."""
    values = [line.split(":", 1)[1] for line in text.splitlines() if ":" in line]
    if _DAYS.search(text) and not _MONEY.search(text):
        return "mục phí hiển thị thời hạn giải quyết thay vì mức phí"
    if any(_BARE_NUMBER.match(v) for v in values):
        return "mục phí chỉ ghi một con số, không có đơn vị"
    if any(v.strip().lower() in _METHODS_ONLY for v in values):
        return "mục phí hiển thị cách thức nộp thay vì mức phí"
    return None


def check(p: Procedure) -> Procedure:
    if p.fee is not None:
        reason = fee_problem(p.fee.text)
        if reason:
            original = " / ".join(p.fee.text.splitlines())[:160]
            warning = (
                f"Trang chính thức bị lỗi ở mục phí, lệ phí ({reason}): «{original}». "
                "Không xác định được mức phí từ nguồn này; hãy hỏi cơ quan tiếp nhận hồ sơ."
            )
            p = p.model_copy(update={"fee": None, "warnings": [*p.warnings, warning]})
    return p
