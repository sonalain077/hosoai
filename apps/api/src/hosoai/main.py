import uuid
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlmodel import Session as DbSession

from hosoai.agent import loop
from hosoai.agent.matcher import MatchResult, match_procedure
from hosoai.agent.sessions import SessionStore, get_sessions
from hosoai.forms.fill import FieldNotFound, fill_pdf, render_page_png
from hosoai.forms.learn.agent import LearnReport
from hosoai.forms.learn.fetch import FetchError
from hosoai.forms.learn.service import LearnError, learn_procedure_form
from hosoai.forms.models import FormSpec, FormSummary
from hosoai.forms.registry import FormRegistry, get_forms, prefill
from hosoai.llm import LLMClient, OpenAICompatibleClient
from hosoai.procedures.models import Procedure
from hosoai.procedures.store import ProcedureStore, ProcedureSummary, get_store
from hosoai.profile.models import ProfileData, agent_facts
from hosoai.profile.store import get_db, load_profile, save_profile
from hosoai.settings import Settings

app = FastAPI(title="Hồ Sơ AI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=Settings().cors_origins,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["*"],
)


def get_llm() -> LLMClient:
    return OpenAICompatibleClient()


Store = Annotated[ProcedureStore, Depends(get_store)]
LLM = Annotated[LLMClient, Depends(get_llm)]
Sessions = Annotated[SessionStore, Depends(get_sessions)]
Db = Annotated[DbSession, Depends(get_db)]
Forms = Annotated[FormRegistry, Depends(get_forms)]


class AskRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/procedures")
def list_procedures(store: Store) -> list[ProcedureSummary]:
    return store.list()


@app.get("/procedures/{slug}")
def get_procedure(slug: str, store: Store) -> Procedure:
    procedure = store.get(slug)
    if procedure is None:
        # Never improvise: unknown slug means we have no official source for it.
        raise HTTPException(
            status_code=404,
            detail={
                "code": "not_found_in_official_sources",
                "message": "Không tìm thấy thủ tục này trong nguồn chính thức.",
                "slug": slug,
            },
        )
    return procedure


@app.post("/ask")
def ask(body: AskRequest, store: Store, llm: LLM) -> MatchResult:
    """Find which procedure(s) the user means. Returns candidates with their sources only."""
    return match_procedure(body.query, store, llm)


def _with_forms(reply: loop.AgentReply, forms: FormRegistry) -> loop.AgentReply:
    if reply.dossier is not None:
        reply.dossier.forms = forms.for_procedure(reply.dossier.procedure.slug)
    return reply


class AgentStart(BaseModel):
    query: str = Field(min_length=1, max_length=1000)


class AgentAnswer(BaseModel):
    answer: str = Field(min_length=1, max_length=500)


@app.post("/agent")
def agent_start(
    body: AgentStart, store: Store, llm: LLM, sessions: Sessions, db: Db, forms: Forms
) -> loop.AgentReply:
    """Start a conversation. The agent finds the procedure and may ask a first question."""
    facts = agent_facts(load_profile(db), date.today())
    session = loop.new_session(uuid.uuid4().hex, body.query, facts)
    sessions.put(session)
    return _with_forms(loop.start(session, store, llm), forms)


@app.post("/agent/{session_id}")
def agent_answer(
    session_id: str, body: AgentAnswer, store: Store, llm: LLM, sessions: Sessions, forms: Forms
) -> loop.AgentReply:
    """Answer the pending question. Returns the next question or the personal dossier."""
    session = sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail={"code": "session_not_found"})
    if session.pending is None or session.done:
        raise HTTPException(status_code=409, detail={"code": "no_pending_question"})
    try:
        return _with_forms(loop.answer(session, body.answer, store, llm), forms)
    except ValueError as e:
        raise HTTPException(
            status_code=422, detail={"code": "invalid_answer", "message": str(e)}
        ) from e


@app.get("/profile")
def get_profile(db: Db) -> ProfileData:
    return load_profile(db)


@app.put("/profile")
def put_profile(body: ProfileData, db: Db) -> ProfileData:
    """Replace the saved profile. Stored locally only (SQLite); never logged."""
    return save_profile(db, body)


class FormDetail(BaseModel):
    spec: FormSpec
    values: dict[str, str]  # prefilled from the saved profile; the user reviews them


class FillRequest(BaseModel):
    values: dict[str, str]
    reviewed: bool  # the user confirmed they checked every value


def _form_or_404(forms: FormRegistry, form_id: str) -> FormSpec:
    spec = forms.get(form_id)
    if spec is None:
        raise HTTPException(status_code=404, detail={"code": "form_not_found"})
    return spec


@app.get("/forms")
def list_forms(forms: Forms) -> list[FormSummary]:
    return forms.list()


@app.get("/forms/{form_id}")
def get_form(
    form_id: str, forms: Forms, db: Db, store: Store, procedure: str | None = None
) -> FormDetail:
    """Form + values prefilled from the profile (and the procedure's official title)."""
    spec = _form_or_404(forms, form_id)
    p = store.get(procedure) if procedure in spec.procedure_slugs else None
    return FormDetail(spec=spec, values=prefill(spec, load_profile(db), p.title if p else None))


@app.get("/forms/{form_id}/blank.pdf")
def blank_form(form_id: str, forms: Forms) -> FileResponse:
    spec = _form_or_404(forms, form_id)
    return FileResponse(forms.pdf_path(spec), media_type="application/pdf")


class PreviewRequest(BaseModel):
    values: dict[str, str]


def _filled(spec: FormSpec, forms: FormRegistry, values: dict[str, str]) -> bytes:
    font = Settings().data_dir / "fonts" / "DejaVuSans.ttf"
    try:
        return fill_pdf(spec, forms.pdf_path(spec), font, values)
    except FieldNotFound as e:
        raise HTTPException(
            status_code=500, detail={"code": "field_not_found", "message": str(e)}
        ) from e


def _png(pdf: bytes | Path, page: int) -> Response:
    try:
        return Response(content=render_page_png(pdf, page), media_type="image/png")
    except IndexError as e:
        raise HTTPException(status_code=404, detail={"code": "page_not_found"}) from e


@app.get("/forms/{form_id}/pages/{page}.png")
def blank_page(form_id: str, page: int, forms: Forms) -> Response:
    spec = _form_or_404(forms, form_id)
    return _png(forms.pdf_path(spec), page)


@app.post("/forms/{form_id}/preview/{page}.png")
def preview_page(form_id: str, page: int, body: PreviewRequest, forms: Forms) -> Response:
    """Image of a filled page, for review before download."""
    spec = _form_or_404(forms, form_id)
    return _png(_filled(spec, forms, body.values), page)


@app.post("/forms/{form_id}/fill")
def fill_form(form_id: str, body: FillRequest, forms: Forms) -> Response:
    """Return the filled PDF for the user to download. Nothing is submitted anywhere."""
    if not body.reviewed:
        raise HTTPException(status_code=422, detail={"code": "not_reviewed"})
    spec = _form_or_404(forms, form_id)
    pdf = _filled(spec, forms, body.values)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{spec.code}-da-dien.pdf"'},
    )


class OfficialForm(BaseModel):
    index: int
    label: str  # as linked on the official procedure page
    url: str
    form_id: str | None  # set when the app can already fill it
    status: str | None  # "reviewed" | "draft"


@app.get("/procedures/{slug}/official-forms")
def official_forms(slug: str, store: Store, forms: Forms) -> list[OfficialForm]:
    """Forms linked from the official page, and which ones the app can already fill."""
    p = store.get(slug)
    if p is None:
        raise HTTPException(status_code=404, detail={"code": "not_found_in_official_sources"})
    known = {}
    for summary in forms.list():
        spec = forms.get(summary.id)
        if spec is not None:
            known[str(spec.source.url)] = spec
    out = []
    for i, f in enumerate(p.forms):
        spec = known.get(str(f.url))
        out.append(
            OfficialForm(
                index=i,
                label=f.label,
                url=str(f.url),
                form_id=spec.id if spec else None,
                status=spec.status if spec else None,
            )
        )
    return out


class LearnRequest(BaseModel):
    procedure: str
    form_index: int = Field(ge=0)
    force: bool = False


class LearnResult(BaseModel):
    form: FormSummary
    report: LearnReport


@app.post("/forms/learn")
def learn_form(body: LearnRequest, store: Store, llm: LLM) -> LearnResult:
    """Let the form-learning agent read an official form. Takes 20-90 s with a local model.

    Downloads only files linked from the official procedure page (.gov.vn). The result is a
    DRAFT spec: every field was checked on the official PDF, but no human has reviewed it.
    """
    p = store.get(body.procedure)
    if p is None:
        raise HTTPException(status_code=404, detail={"code": "not_found_in_official_sources"})
    try:
        spec, report = learn_procedure_form(
            p, body.form_index, llm, Settings(), force=body.force, log=lambda *_: None
        )
    except (FetchError, LearnError) as e:
        raise HTTPException(
            status_code=422, detail={"code": "cannot_learn", "message": str(e)}
        ) from e
    get_forms.cache_clear()
    return LearnResult(form=FormSummary.model_validate(spec.model_dump()), report=report)
