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
    label_en: str | None = None  # our own English label (from the catalog), not official text
    source: Source


class ProcedureStore:
    def __init__(self, parsed_dir: Path, labels_en: dict[str, str] | None = None) -> None:
        self._labels_en = labels_en or {}
        self._by_slug: dict[str, Procedure] = {}
        for path in sorted(parsed_dir.glob("*.json")):
            p = Procedure.model_validate_json(path.read_text("utf-8"))
            self._by_slug[p.slug] = p

    def list(self) -> list[ProcedureSummary]:
        return [
            ProcedureSummary(
                slug=p.slug,
                title=p.title,
                national_code=p.national_code,
                label_en=self._labels_en.get(p.slug),
                source=p.source,
            )
            for p in self._by_slug.values()
        ]

    def summary(self, slug: str) -> ProcedureSummary | None:
        return next((s for s in self.list() if s.slug == slug), None)

    def get(self, slug: str) -> Procedure | None:
        return self._by_slug.get(slug)


@lru_cache
def get_store() -> ProcedureStore:
    from hosoai.settings import Settings
    from hosoai.sources.ingest import load_catalog

    data_dir = Settings().data_dir
    labels = {e.slug: e.title_en for e in load_catalog(data_dir).procedures if e.title_en}
    return ProcedureStore(data_dir / "procedures" / "parsed", labels)
