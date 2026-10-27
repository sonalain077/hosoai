"""Official forms we can fill, described by hand-checked specs in data/forms/<id>/form.json."""

from typing import Literal

from pydantic import BaseModel

from hosoai.sources.models import Source

ProfileKey = Literal[
    "full_name",
    "date_of_birth",
    "sex",
    "id_number",
    "nationality",
    "ethnicity",
    "religion",
    "place_of_birth",
    "hometown",
    "permanent_address",
    "current_address",
    "occupation",
    "phone",
    "email",
    "passport_number",
]


class FormField(BaseModel):
    key: str
    label: str  # exact text printed on the official form; also where we write
    hint: str | None = None  # our own short plain-language gloss, not official text
    profile_key: ProfileKey | None = None
    page: int = 0
    occurrence: int = 0  # which match of `label` on the page (0 = first)
    mode: Literal["after_label", "boxes", "date_parts", "choice", "acroform"] = "after_label"
    separators: list[str] = ["/", "/"]  # date_parts: printed words between day, month, year
    choices: dict[str, str] | None = None  # choice: value -> printed option to tick
    uppercase: bool = False  # the form asks for capital letters
    extra_profile_keys: list[ProfileKey] = []  # joined with " / " (e.g. phone / email)
    widget: str | None = None  # AcroForm field name, for mode="acroform"
    max_chars: int | None = None
    x_offset: float = 0  # extra space after the label (e.g. a superscript note marker)
    font_size: float | None = None  # for lines printed smaller than usual
    from_procedure_title: bool = False  # prefill with the official title of the procedure
    below_x: float | None = None  # dotted line is on the next line, starting at this x (pt)


class FormSpec(BaseModel):
    id: str
    code: str  # e.g. "CT01"
    title: str  # official title of the form
    procedure_slugs: list[str]
    file: str  # PDF next to form.json (converted from the official file)
    original_file: str | None = None  # the official file as downloaded
    source: Source  # where the official form was downloaded
    fields: list[FormField]
    notes: list[str] = []  # known limits of this spec
    preview_pages: int = 1  # pages shown in the on-screen preview


class FormSummary(BaseModel):
    id: str
    code: str
    title: str
    procedure_slugs: list[str]
    source: Source
