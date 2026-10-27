"""Fetch the official pages listed in data/procedures/catalog.json and save parsed procedures.

    uv run python -m hosoai.sources.ingest              # fetch all, then parse
    uv run python -m hosoai.sources.ingest --offline    # re-parse saved pages, no network
    uv run python -m hosoai.sources.ingest --only passport

Raw pages are kept in data/sources/raw/<source>/<page_id>.html with a .meta.json next to
them (url, retrieved_at, sha256), so every parsed fact can be traced back to the exact
page we read. This only reads public pages; it never submits anything.
"""

import argparse
import hashlib
import json
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

from hosoai.procedures.models import Procedure
from hosoai.settings import Settings
from hosoai.sources import quality
from hosoai.sources.models import Source
from hosoai.sources.parsers import bca, laocai
from hosoai.sources.parsers.common import ParseError

USER_AGENT = (
    "Mozilla/5.0 (compatible; HoSoAI/0.1; hackathon project reading public procedure pages)"
)
DELAY_SECONDS = 3.0  # be gentle with government servers
RETRIES = 3

Parser = Callable[..., Procedure]
PARSERS: dict[str, tuple[Parser, str]] = {
    "bca": (bca.parse, bca.PUBLISHER),
    "laocai": (laocai.parse, laocai.PUBLISHER),
}


class CatalogSource(BaseModel):
    name: str
    url_template: str


class CatalogEntry(BaseModel):
    slug: str
    title_vi: str
    title_en: str | None = None  # our own short label for matching/navigation, not official text
    source: str
    page_id: str
    warning: str | None = None


class Catalog(BaseModel):
    sources: dict[str, CatalogSource]
    procedures: list[CatalogEntry]

    def url(self, entry: CatalogEntry) -> str:
        return self.sources[entry.source].url_template.format(page_id=entry.page_id)


class RawPage(BaseModel):
    url: str
    retrieved_at: datetime
    status_code: int
    sha256: str


def load_catalog(data_dir: Path) -> Catalog:
    return Catalog.model_validate_json(
        (data_dir / "procedures" / "catalog.json").read_text("utf-8")
    )


def _raw_paths(data_dir: Path, entry: CatalogEntry) -> tuple[Path, Path]:
    base = data_dir / "sources" / "raw" / entry.source / entry.page_id
    return base.with_suffix(".html"), base.with_suffix(".meta.json")


def fetch(client: httpx.Client, url: str, entry: CatalogEntry, data_dir: Path) -> None:
    """Download one page and save it. Retries because these servers often return 502/empty."""
    parse, publisher = PARSERS[entry.source]
    last_error = ""
    for attempt in range(RETRIES):
        if attempt:
            time.sleep(DELAY_SECONDS * (attempt + 1))
        try:
            resp = client.get(url)
        except httpx.HTTPError as e:
            last_error = repr(e)
            continue
        html = resp.text
        try:  # only keep the page if it really is a procedure page
            parse(
                html, slug=entry.slug, url=url, source=_source(url, entry, publisher), warnings=[]
            )
        except ParseError as e:
            last_error = f"HTTP {resp.status_code}: {e}"
            continue
        html_path, meta_path = _raw_paths(data_dir, entry)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html, "utf-8")
        meta = RawPage(
            url=url,
            retrieved_at=datetime.now(UTC),
            status_code=resp.status_code,
            sha256=hashlib.sha256(html.encode()).hexdigest(),
        )
        meta_path.write_text(meta.model_dump_json(indent=2), "utf-8")
        return
    raise RuntimeError(f"{entry.slug}: could not fetch {url} ({last_error})")


def _source(url: str, entry: CatalogEntry, publisher: str, at: datetime | None = None) -> Source:
    return Source(
        url=url,
        title=entry.title_vi,
        publisher=publisher,
        retrieved_at=at or datetime.now(UTC),
    )


def parse_saved(entry: CatalogEntry, catalog: Catalog, data_dir: Path) -> Procedure:
    html_path, meta_path = _raw_paths(data_dir, entry)
    if not html_path.exists():
        raise FileNotFoundError(
            f"{entry.slug}: no saved page at {html_path}; run without --offline"
        )
    meta = RawPage.model_validate_json(meta_path.read_text("utf-8"))
    parse, publisher = PARSERS[entry.source]
    procedure = parse(
        html_path.read_text("utf-8"),
        slug=entry.slug,
        url=meta.url,
        source=_source(meta.url, entry, publisher, meta.retrieved_at),
        warnings=[entry.warning] if entry.warning else [],
    )
    return quality.check(procedure)


def run(data_dir: Path, *, offline: bool, only: set[str] | None) -> dict[str, Any]:
    catalog = load_catalog(data_dir)
    entries = [e for e in catalog.procedures if not only or e.slug in only]
    out_dir = data_dir / "procedures" / "parsed"
    out_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"ok": [], "failed": {}}
    with httpx.Client(
        headers={"User-Agent": USER_AGENT}, timeout=60, follow_redirects=True
    ) as client:
        for i, entry in enumerate(entries):
            try:
                if not offline:
                    if i:
                        time.sleep(DELAY_SECONDS)
                    fetch(client, catalog.url(entry), entry, data_dir)
                proc = parse_saved(entry, catalog, data_dir)
            except (RuntimeError, ParseError, FileNotFoundError) as e:
                report["failed"][entry.slug] = str(e)
                print(f"FAIL {entry.slug}: {e}", file=sys.stderr)
                continue
            (out_dir / f"{entry.slug}.json").write_text(proc.model_dump_json(indent=2), "utf-8")
            report["ok"].append(entry.slug)
            print(
                f"ok   {entry.slug}: {len(proc.steps)} steps, {len(proc.documents)} documents, "
                f"{len(proc.forms)} forms, fee={'yes' if proc.fee else 'NOT FOUND'}"
            )
    return report


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--offline", action="store_true", help="re-parse saved pages, no network")
    ap.add_argument("--only", nargs="*", help="slugs to process (default: all)")
    args = ap.parse_args()
    report = run(
        Settings().data_dir, offline=args.offline, only=set(args.only) if args.only else None
    )
    print(json.dumps({"ok": len(report["ok"]), "failed": report["failed"]}, ensure_ascii=False))
    sys.exit(1 if report["failed"] else 0)


if __name__ == "__main__":
    main()
