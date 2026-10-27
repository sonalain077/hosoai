"""The catalog only points at official government pages we know how to parse."""

from urllib.parse import urlparse

from hosoai.settings import Settings
from hosoai.sources.ingest import PARSERS, load_catalog


def test_catalog_entries_are_official_and_parseable() -> None:
    catalog = load_catalog(Settings().data_dir)
    slugs = [e.slug for e in catalog.procedures]
    assert len(slugs) == len(set(slugs)) >= 10
    for entry in catalog.procedures:
        assert entry.source in PARSERS, entry.slug
        host = urlparse(catalog.url(entry)).hostname or ""
        assert host.endswith(".gov.vn"), entry.slug


def test_every_parsed_procedure_cites_an_official_page() -> None:
    from hosoai.procedures.models import Procedure

    data_dir = Settings().data_dir
    catalog = load_catalog(data_dir)
    for entry in catalog.procedures:
        path = data_dir / "procedures" / "parsed" / f"{entry.slug}.json"
        assert path.exists(), f"{entry.slug}: run `python -m hosoai.sources.ingest`"
        p = Procedure.model_validate_json(path.read_text("utf-8"))
        assert p.steps and p.documents, entry.slug
        for item in [*p.steps, *p.documents, *p.legal_basis, *p.methods, *p.forms]:
            assert (item.source.url.host or "").endswith(".gov.vn"), entry.slug
            assert item.source.retrieved_at is not None
