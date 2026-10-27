from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from hosoai.agent.matcher import MatchResult, match_procedure
from hosoai.llm import LLMClient, OpenAICompatibleClient
from hosoai.procedures.models import Procedure
from hosoai.procedures.store import ProcedureStore, ProcedureSummary, get_store
from hosoai.settings import Settings

app = FastAPI(title="Hồ Sơ AI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=Settings().cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def get_llm() -> LLMClient:
    return OpenAICompatibleClient()


Store = Annotated[ProcedureStore, Depends(get_store)]
LLM = Annotated[LLMClient, Depends(get_llm)]


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
