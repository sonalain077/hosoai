"""Learn an official form linked from a procedure page (shared by the CLI and the API)."""

import re
import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pymupdf

from hosoai.forms.learn.agent import LearnReport, learn
from hosoai.forms.learn.fetch import download, form_code, form_title, to_pdf
from hosoai.forms.models import FormSpec
from hosoai.llm import LLMClient
from hosoai.procedures.models import Procedure
from hosoai.settings import Settings
from hosoai.sources.models import Source


class LearnError(Exception):
    pass


def learn_procedure_form(
    p: Procedure,
    index: int,
    llm: LLMClient,
    settings: Settings,
    *,
    form_id: str | None = None,
    force: bool = False,
    local_file: Path | None = None,
    log: Callable[..., Any] = print,
) -> tuple[FormSpec, LearnReport]:
    """Download p.forms[index], convert it, run the agent, save a draft spec.

    local_file: the same official file, downloaded by a person in a browser, for portals
    that refuse scripted downloads. The source stays the official URL of p.forms[index].
    """
    if not 0 <= index < len(p.forms):
        raise LearnError("no such form on this procedure page")
    link = p.forms[index]
    forms_dir = settings.data_dir / "forms"
    tmp = forms_dir / f".learning-{p.slug}-{index}"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    try:
        if local_file is not None:
            if local_file.suffix.lower() not in (".doc", ".docx", ".pdf"):
                raise LearnError("the file must be the official .doc, .docx or .pdf")
            original = tmp / f"form-official{local_file.suffix.lower()}"
            shutil.copy(local_file, original)
        else:
            original = download(str(link.url), tmp, "form")
        pdf = to_pdf(original, tmp / "form.pdf")
        doc = pymupdf.open(pdf)
        code = form_code(doc) or f"{p.slug}-{index}".upper()
        title = form_title(doc) or link.label
        fid = form_id or re.sub(r"[^a-z0-9-]", "", code.lower()) or f"{p.slug}-{index}"
        final = forms_dir / fid
        if final.exists():
            existing = final / "form.json"
            if existing.exists() and '"status": "reviewed"' in existing.read_text("utf-8"):
                raise LearnError(f"{fid} is human-reviewed; not overwriting it")
            if not force:
                raise LearnError(f"{fid} already exists")
        log(f"Form {code}: {title}")
        spec, report = learn(
            form_id=fid,
            code=code,
            title=title,
            procedure_slugs=[p.slug],
            pdf=pdf,
            original_file=original.name,
            source=Source(
                url=link.url,
                title=f"{title} (Mẫu {code})",
                document_number=f"Mẫu {code}",
                publisher=p.source.publisher,
                retrieved_at=datetime.now(UTC),
            ),
            font=settings.data_dir / "fonts" / "DejaVuSans.ttf",
            llm=llm,
            model_name=settings.llm_model,
            log=log,
        )
        if not spec.fields:
            raise LearnError("the agent could not find any field that passes the checks")
        (tmp / "form.json").write_text(spec.model_dump_json(indent=2), "utf-8")
        shutil.rmtree(final, ignore_errors=True)
        tmp.rename(final)
        return spec, report
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
