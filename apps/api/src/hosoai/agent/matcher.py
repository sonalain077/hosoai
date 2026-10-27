"""Match a user's own words to a procedure we hold official data for.

The LLM only *chooses* among known procedure slugs. It never writes procedural
content. Anything it returns that is not a known slug is dropped, and if nothing
is left the answer is an explicit "not found in official sources".
"""

import json
import re
from typing import Literal

from pydantic import BaseModel

from hosoai.llm import ChatMessage, LLMClient
from hosoai.procedures.store import ProcedureStore, ProcedureSummary

MAX_CANDIDATES = 3

NOT_FOUND_MESSAGE = (
    "Chúng tôi không tìm thấy thủ tục này trong các nguồn chính thức hiện có. "
    "We could not find this procedure in the official sources we have."
)

SYSTEM_PROMPT = """You route requests about Vietnamese administrative procedures.
You are given a numbered list of procedures (slug, official Vietnamese title, short English label)
and a user request written in any language.

Pick the procedure(s) from the list that the user needs.
- Only use slugs that appear in the list. Never invent a slug.
- If one procedure clearly fits, return just that one.
- If the request fits several (e.g. new vs. replacement ID card), return up to 3, best first.
- If nothing in the list fits, return an empty list. Do not guess.

Reply with JSON only, no other text: {"slugs": ["..."]}"""


class MatchResult(BaseModel):
    status: Literal["matched", "ambiguous", "not_found"]
    candidates: list[ProcedureSummary]
    message: str | None = None


def _catalog_text(store: ProcedureStore) -> str:
    lines = []
    for i, p in enumerate(store.list(), 1):
        label = f" | {p.label_en}" if p.label_en else ""
        lines.append(f"{i}. {p.slug} | {p.title}{label}")
    return "\n".join(lines)


def _parse_slugs(reply: str) -> list[str]:
    found = re.search(r"\{.*\}", reply, re.DOTALL)
    if not found:
        return []
    try:
        data = json.loads(found.group(0))
    except json.JSONDecodeError:
        return []
    slugs = data.get("slugs") if isinstance(data, dict) else None
    if not isinstance(slugs, list):
        return []
    return [s for s in slugs if isinstance(s, str)]


def match_procedure(query: str, store: ProcedureStore, llm: LLMClient) -> MatchResult:
    reply = llm.chat(
        [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(
                role="user",
                content=f"Procedures:\n{_catalog_text(store)}\n\nUser request:\n{query}",
            ),
        ]
    )
    candidates: list[ProcedureSummary] = []
    for slug in _parse_slugs(reply):
        summary = store.summary(slug)
        if summary and summary not in candidates:
            candidates.append(summary)
    candidates = candidates[:MAX_CANDIDATES]

    if not candidates:
        return MatchResult(status="not_found", candidates=[], message=NOT_FOUND_MESSAGE)
    status: Literal["matched", "ambiguous"] = "matched" if len(candidates) == 1 else "ambiguous"
    return MatchResult(status=status, candidates=candidates)
