"""The intake agent: find the procedure, ask what it needs to know, build a personal dossier.

1. Routing. The matcher (agent/matcher.py) picks the procedure from our official catalog.
   No match -> "not found". Several -> the user chooses. The model never opens a
   procedure we don't have.
2. Case questions. The model reads the official document list and, each turn, replies
   with ONE JSON action:
     ask_user  one short question tied to specific official documents (pauses the loop)
     finish    which documents apply to this person
3. The dossier is built here from the store, by id.

Grounding rules enforced in code, not trusted to the model:
- Text shown to the user (documents, steps, fees...) always comes from the store.
- A document can only be "not_needed" if the model cites one of the user's own words
  (answer 0 is the original request). Otherwise it is downgraded to "unsure".
- Documents the model does not mention are "unsure", never dropped.
"""

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from hosoai.agent.matcher import match_procedure
from hosoai.llm import ChatMessage, LLMClient
from hosoai.procedures.models import Procedure, RequiredDocument
from hosoai.procedures.store import ProcedureStore, ProcedureSummary

MAX_QUESTIONS = 4
MAX_STEPS_PER_TURN = 4  # model replies between two user messages
DOC_PREVIEW_CHARS = 220  # Ollama's default context is small; the model gets a trimmed view

Status = Literal["needed", "not_needed", "unsure"]

SYSTEM_PROMPT = """You help a person in Vietnam prepare the papers for one administrative procedure.
Below are the person's request (answer 0) and the official list of documents (d1, d2...).
Some documents apply only in some cases (age under 14, lost document, applying online,
someone else applying for them...). Find out which documents apply to this person.

Reply with ONE JSON object and nothing else. Two possible actions:

{"action": "ask_user", "question": "<short question>", "options": ["<choice>", "<choice>"],
 "about": ["d1", "d3"]}
  Ask ONE short question, in the language of the request, whose answer decides whether
  the listed documents apply. 2 to 4 short options. Do not ask what answer 0 already says.

{"action": "finish", "documents": {"d1": "needed", "d2": "not_needed"}, "because": {"d2": [1]}}
  Give every document id a status: "needed", "not_needed" or "unsure".
  "because" maps a document id to the answer numbers that justify the status
  (0 = the request). A "not_needed" document MUST have a "because".

Never state fees, deadlines or requirements in a question. Ask at most %d questions,
one at a time. If no document depends on the person's situation, finish right away."""

CHOOSE_QUESTION = "Trường hợp nào đúng với bạn? Which of these is your case?"


# ---------- what the API returns ----------


class DocRef(BaseModel):
    id: str
    name: str


class Question(BaseModel):
    number: int
    kind: Literal["case", "choose_procedure"] = "case"
    text: str
    options: list[str]
    about: list[DocRef] = Field(default_factory=list)  # official documents it decides


class QA(BaseModel):
    number: int  # 0 = the original request
    question: str
    answer: str


class DossierDocument(BaseModel):
    id: str
    status: Status
    document: RequiredDocument  # official text + source, from the store
    because: list[QA] = Field(default_factory=list)


class Dossier(BaseModel):
    procedure: Procedure
    documents: list[DossierDocument]
    answers: list[QA]


class AgentReply(BaseModel):
    session_id: str
    type: Literal["question", "dossier", "not_found"]
    question: Question | None = None
    dossier: Dossier | None = None
    message: str | None = None


NOT_FOUND_MESSAGE = (
    "Chúng tôi không tìm thấy thủ tục này trong các nguồn chính thức hiện có. "
    "We could not find this procedure in the official sources we have."
)


# ---------- session state ----------


class Session(BaseModel):
    id: str
    query: str
    messages: list[ChatMessage] = Field(default_factory=list)
    slug: str | None = None
    choices: list[ProcedureSummary] = Field(default_factory=list)  # when routing is ambiguous
    pending: Question | None = None
    answers: list[QA] = Field(default_factory=list)  # answers[0] is the request
    done: bool = False

    @property
    def questions_asked(self) -> int:
        return sum(1 for a in self.answers if a.number > 0)


def new_session(session_id: str, query: str) -> Session:
    return Session(
        id=session_id,
        query=query,
        answers=[QA(number=0, question="Yêu cầu ban đầu / Your request", answer=query)],
    )


def _doc_id(i: int) -> str:
    return f"d{i + 1}"


def _procedure_view(p: Procedure) -> str:
    lines = [f"PROCEDURE: {p.title}"]
    if p.conditions:
        lines.append(f"Conditions: {p.conditions.text[:300]}")
    if p.methods:
        lines.append("Ways to apply: " + ", ".join(m.text for m in p.methods))
    lines.append("Documents:")
    for i, d in enumerate(p.documents):
        name = d.name if len(d.name) <= DOC_PREVIEW_CHARS else d.name[:DOC_PREVIEW_CHARS] + "…"
        lines.append(f"{_doc_id(i)}: {name}")
    return "\n".join(lines)


# ---------- entry points ----------


def start(session: Session, store: ProcedureStore, llm: LLMClient) -> AgentReply:
    """Route the request to a procedure, then let the agent work on it."""
    match = match_procedure(session.query, store, llm)
    if match.status == "not_found":
        return _not_found(session)
    if match.status == "ambiguous":
        session.choices = match.candidates
        session.pending = Question(
            number=0,
            kind="choose_procedure",
            text=CHOOSE_QUESTION,
            options=[c.title for c in match.candidates],
        )
        return AgentReply(session_id=session.id, type="question", question=session.pending)
    return _open(session, match.candidates[0].slug, store, llm)


def answer(session: Session, text: str, store: ProcedureStore, llm: LLMClient) -> AgentReply:
    """Record the user's answer to the pending question, then let the agent continue."""
    q = session.pending
    if q is None or session.done:
        raise ValueError("No question is waiting for an answer")

    if q.kind == "choose_procedure":
        chosen = next((c for c in session.choices if text in (c.title, c.slug)), None)
        if chosen is None:
            raise ValueError("Answer must be one of the offered procedures")
        session.pending = None
        session.choices = []
        return _open(session, chosen.slug, store, llm)

    session.answers.append(QA(number=q.number, question=q.text, answer=text))
    session.pending = None
    session.messages.append(ChatMessage(role="user", content=f"Answer {q.number}: {text}"))
    return _run(session, store, llm)


# ---------- the loop ----------


def _open(session: Session, slug: str, store: ProcedureStore, llm: LLMClient) -> AgentReply:
    p = store.get(slug)
    if p is None:
        return _not_found(session)
    session.slug = p.slug
    session.messages = [
        ChatMessage(role="system", content=SYSTEM_PROMPT % MAX_QUESTIONS),
        ChatMessage(
            role="user", content=f"Answer 0 (the request): {session.query}\n\n{_procedure_view(p)}"
        ),
    ]
    return _run(session, store, llm)


def _parse_action(reply: str) -> dict[str, Any] | None:
    found = re.search(r"\{.*\}", reply, re.DOTALL)
    if not found:
        return None
    try:
        data = json.loads(found.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) and isinstance(data.get("action"), str) else None


def _feedback(session: Session, content: str) -> None:
    session.messages.append(ChatMessage(role="user", content=f"SYSTEM: {content}"))


def _run(session: Session, store: ProcedureStore, llm: LLMClient) -> AgentReply:
    p = store.get(session.slug) if session.slug else None
    if p is None:
        return _not_found(session)

    for _ in range(MAX_STEPS_PER_TURN):
        raw = llm.chat(session.messages)
        action = _parse_action(raw)
        if action is None:
            session.messages.append(ChatMessage(role="assistant", content=raw[:500]))
            _feedback(session, "Invalid reply. Answer with ONE JSON object with an 'action'.")
            continue
        session.messages.append(ChatMessage(role="assistant", content=json.dumps(action)))

        if action["action"] == "ask_user":
            if session.questions_asked >= MAX_QUESTIONS:
                _feedback(session, "You have asked enough questions. Reply with finish now.")
                continue
            question = _question(session, action, p)
            if question is None:
                _feedback(session, "ask_user needs a 'question' and 2 to 4 'options'.")
                continue
            session.pending = question
            return AgentReply(session_id=session.id, type="question", question=question)

        if action["action"] == "finish":
            docs, because = action.get("documents"), action.get("because")
            return _finish(
                session,
                p,
                docs if isinstance(docs, dict) else {},
                because if isinstance(because, dict) else {},
            )

        _feedback(session, f"Unknown action {action['action']!r}. Use ask_user or finish.")

    # The model never settled: show the full official list, nothing excluded.
    return _finish(session, p, {}, {})


def _question(session: Session, action: dict[str, Any], p: Procedure) -> Question | None:
    text = action.get("question")
    options = action.get("options")
    if not isinstance(text, str) or not text.strip() or not isinstance(options, list):
        return None
    opts = [o.strip() for o in options if isinstance(o, str) and o.strip()][:4]
    if len(opts) < 2:
        return None
    about_ids = action.get("about") if isinstance(action.get("about"), list) else []
    ids = {_doc_id(i): d for i, d in enumerate(p.documents)}
    about = [DocRef(id=i, name=ids[i].name) for i in dict.fromkeys(about_ids or []) if i in ids]
    return Question(
        number=session.questions_asked + 1, text=text.strip(), options=opts, about=about
    )


def _finish(
    session: Session, p: Procedure, statuses: dict[str, Any], because: dict[str, Any]
) -> AgentReply:
    by_number = {a.number: a for a in session.answers}
    out: list[DossierDocument] = []
    for i, d in enumerate(p.documents):
        doc_id = _doc_id(i)
        status = statuses.get(doc_id)
        if status not in ("needed", "not_needed", "unsure"):
            status = "unsure"
        cited = because.get(doc_id) if isinstance(because.get(doc_id), list) else []
        reasons = [by_number[n] for n in dict.fromkeys(cited or []) if n in by_number]
        if status == "not_needed" and not reasons:
            status = "unsure"  # can't drop a document without the user's own words behind it
        out.append(DossierDocument(id=doc_id, status=status, document=d, because=reasons))
    session.done = True
    return AgentReply(
        session_id=session.id,
        type="dossier",
        dossier=Dossier(procedure=p, documents=out, answers=session.answers),
    )


def _not_found(session: Session) -> AgentReply:
    session.done = True
    return AgentReply(session_id=session.id, type="not_found", message=NOT_FOUND_MESSAGE)
