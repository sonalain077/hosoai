"""A procedure as published by an official portal.

Text is kept as the source wrote it (Vietnamese, verbatim). Plain-language rewriting
happens later and must keep pointing at these items. A section the source page does
not have stays None / empty: we never fill it in.
"""

from pydantic import BaseModel, HttpUrl

from hosoai.sources.models import Source


class SourcedText(BaseModel):
    text: str
    source: Source


class RequiredDocument(BaseModel):
    name: str
    form_name: str | None = None  # template named in the source, if any
    quantity: str | None = None  # as written, e.g. "Bản chính: 1, Bản sao: 0"
    source: Source


class FormFile(BaseModel):
    label: str
    url: HttpUrl
    source: Source


class Procedure(BaseModel):
    slug: str
    title: str
    national_code: str | None
    field: SourcedText | None
    agency: SourcedText | None
    methods: list[SourcedText]
    steps: list[SourcedText]
    processing_time: SourcedText | None
    fee: SourcedText | None
    documents: list[RequiredDocument]
    conditions: SourcedText | None
    legal_basis: list[SourcedText]
    result: SourcedText | None
    forms: list[FormFile]
    warnings: list[str]  # known problems with the source (from the catalog)
    source: Source
