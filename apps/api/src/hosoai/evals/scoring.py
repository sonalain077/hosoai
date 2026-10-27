"""Pure scoring functions for the evals (unit-tested, no model needed)."""

import re
import time
from statistics import median
from typing import Literal

from pydantic import BaseModel

from hosoai.llm import ChatMessage, LLMClient

Category = Literal["direct", "paraphrase", "ambiguous", "out_of_scope", "off_topic", "adversarial"]


class RoutingCase(BaseModel):
    id: str
    category: Category
    lang: str
    query: str
    expected: list[str]  # acceptable slugs, best first; empty = must answer "not found"
    allow_not_found: bool = False
    note: str | None = None


class RoutingOutcome(BaseModel):
    case_id: str
    category: Category
    lang: str
    candidates: list[str]  # what the user would see (after guardrails)
    raw_slugs: list[str]  # what the model actually returned
    invented: list[str]  # raw slugs that are not in our catalog (dropped by guardrails)
    valid_json: bool
    raw_reply: str = ""  # first 300 characters, for diagnosis
    correct: bool
    latency_s: float


class RecordingLLM:
    """Wraps a client to keep raw replies and timing."""

    def __init__(self, inner: LLMClient) -> None:
        self.inner = inner
        self.replies: list[str] = []
        self.seconds: list[float] = []

    def chat(self, messages: list[ChatMessage], *, vision: bool = False) -> str:
        t = time.perf_counter()
        reply = self.inner.chat(messages, vision=vision)
        self.seconds.append(time.perf_counter() - t)
        self.replies.append(reply)
        return reply


def score_routing(
    case: RoutingCase,
    candidates: list[str],
    raw_slugs: list[str],
    valid_json: bool,
    catalog: set[str],
    latency_s: float,
) -> RoutingOutcome:
    if not case.expected:
        correct = not candidates
    elif not candidates:
        correct = case.allow_not_found
    else:
        correct = candidates[0] in case.expected
    return RoutingOutcome(
        case_id=case.id,
        category=case.category,
        lang=case.lang,
        candidates=candidates,
        raw_slugs=raw_slugs,
        invented=[s for s in raw_slugs if s not in catalog],
        valid_json=valid_json,
        correct=correct,
        latency_s=latency_s,
    )


def rate(n: int, d: int) -> float:
    return round(100 * n / d, 1) if d else 0.0


def summarize_routing(outcomes: list[RoutingOutcome]) -> dict[str, object]:
    in_scope = [o for o in outcomes if o.category in ("direct", "paraphrase", "ambiguous")]
    must_refuse = [o for o in outcomes if o.category in ("out_of_scope", "off_topic")]
    adversarial = [o for o in outcomes if o.category == "adversarial"]
    by_cat: dict[str, str] = {}
    for cat in sorted({o.category for o in outcomes}):
        group = [o for o in outcomes if o.category == cat]
        by_cat[cat] = f"{sum(o.correct for o in group)}/{len(group)}"
    by_lang: dict[str, str] = {}
    for lang in sorted({o.lang for o in in_scope}):
        group = [o for o in in_scope if o.lang == lang]
        by_lang[lang] = f"{sum(o.correct for o in group)}/{len(group)}"
    lat = sorted(o.latency_s for o in outcomes)
    return {
        "cases": len(outcomes),
        "accuracy_in_scope_pct": rate(sum(o.correct for o in in_scope), len(in_scope)),
        "correct_not_found_pct": rate(sum(o.correct for o in must_refuse), len(must_refuse)),
        "wrong_procedure_on_out_of_scope": sum(1 for o in must_refuse if o.candidates),
        "missed_in_scope_as_not_found": sum(1 for o in in_scope if not o.candidates),
        "adversarial_correct": f"{sum(o.correct for o in adversarial)}/{len(adversarial)}",
        "model_invented_slugs": sum(len(o.invented) for o in outcomes),
        "invented_slugs_shown_to_user": sum(
            1 for o in outcomes for s in o.candidates if s in o.invented
        ),
        "invalid_json_replies": sum(not o.valid_json for o in outcomes),
        "by_category": by_cat,
        "by_language_in_scope": by_lang,
        "latency_median_s": round(median(lat), 2) if lat else 0,
        "latency_p95_s": round(lat[int(0.95 * (len(lat) - 1))], 2) if lat else 0,
    }


# ---------- baseline: plain chatbot asked for fees ----------

_AMOUNT = re.compile(r"(?<![\d/])(\d{1,3}(?:[.,\s]\d{3})+|\d{4,})(?!\d)")


def amounts(text: str) -> set[int]:
    """Money-like numbers in a text: 160.000 / 160,000 / 160000 -> 160000.

    Skips legal references such as 44/2023/TT-BTC (digits after "/") and bare years.
    """
    found: set[int] = set()
    for m in _AMOUNT.finditer(text):
        value = int(re.sub(r"[.,\s]", "", m.group(1)))
        if 1900 <= value <= 2100 and len(m.group(1)) == 4:
            continue  # a year
        if value >= 1000:
            found.add(value)
    return found


class FeeOutcome(BaseModel):
    slug: str
    official_amounts: list[int]
    official_has_fee_text: bool
    baseline_amounts: list[int]
    unsupported_amounts: list[int]  # stated by the chatbot, absent from the official text


def score_fee(slug: str, official_text: str | None, baseline_reply: str) -> FeeOutcome:
    official = amounts(official_text or "")
    said = amounts(baseline_reply)
    return FeeOutcome(
        slug=slug,
        official_amounts=sorted(official),
        official_has_fee_text=official_text is not None,
        baseline_amounts=sorted(said),
        unsupported_amounts=sorted(said - official),
    )


def summarize_fees(outcomes: list[FeeOutcome]) -> dict[str, object]:
    with_number = [o for o in outcomes if o.baseline_amounts]
    wrong = [o for o in with_number if o.unsupported_amounts]
    return {
        "procedures": len(outcomes),
        "chatbot_gave_an_amount": len(with_number),
        "chatbot_amount_not_in_official_source": len(wrong),
        "chatbot_unsupported_pct_of_answers_with_amount": rate(len(wrong), len(with_number)),
        "hosoai_amounts_not_in_source": 0,  # Hồ Sơ AI shows the official fee text verbatim
    }
