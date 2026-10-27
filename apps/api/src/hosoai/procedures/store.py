"""Read-only access to the parsed official procedures in data/procedures/parsed/."""

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

from hosoai.procedures.models import Procedure
from hosoai.sources.models import Source


class ProcedureSummary(BaseModel):
    slug: str
    title: str
    national_code: str | None
    source: Source


class ProcedureStore:
    def __init__(self, parsed_dir: Path) -> None:
        self._by_slug: dict[str, Procedure] = {}
        for path in sorted(parsed_dir.glob("*.json")):
            p = Procedure.model_validate_json(path.read_text("utf-8"))
            self._by_slug[p.slug] = p

    def list(self) -> list[ProcedureSummary]:
        return [
            ProcedureSummary(
                slug=p.slug, title=p.title, national_code=p.national_code, source=p.source
            )
            for p in self._by_slug.values()
        ]

    def get(self, slug: str) -> Procedure | None:
        return self._by_slug.get(slug)


@lru_cache
def get_store() -> ProcedureStore:
    from hosoai.settings import Settings

    return ProcedureStore(Settings().data_dir / "procedures" / "parsed")
