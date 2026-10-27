from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from hosoai.procedures.models import Procedure
from hosoai.procedures.store import ProcedureStore, ProcedureSummary, get_store
from hosoai.settings import Settings

app = FastAPI(title="Hồ Sơ AI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=Settings().cors_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)

Store = Annotated[ProcedureStore, Depends(get_store)]


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
