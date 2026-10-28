"""Loads form specs from data/forms/*/form.json and prepares prefilled values."""

from datetime import date
from functools import lru_cache
from pathlib import Path

from hosoai.forms.models import FormField, FormSpec, FormSummary
from hosoai.profile.models import ProfileData


class FormRegistry:
    def __init__(self, forms_dir: Path) -> None:
        self.dir = forms_dir
        self._specs: dict[str, FormSpec] = {}
        for path in sorted(forms_dir.glob("*/form.json")):
            spec = FormSpec.model_validate_json(path.read_text("utf-8"))
            self._specs[spec.id] = spec

    def for_procedure(self, slug: str) -> list[FormSummary]:
        return [f for f in self.list() if slug in f.procedure_slugs]

    def list(self) -> list[FormSummary]:
        return [FormSummary.model_validate(s.model_dump()) for s in self._specs.values()]

    def get(self, form_id: str) -> FormSpec | None:
        return self._specs.get(form_id)

    def pdf_path(self, spec: FormSpec) -> Path:
        return self.dir / spec.id / spec.file


def _one(profile: ProfileData, key: str) -> str:
    value = getattr(profile, key)
    if value is None:
        return ""
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return str(value)


def format_profile_value(field: FormField, profile: ProfileData) -> str:
    if field.profile_key is None:
        return ""
    keys = [field.profile_key, *field.extra_profile_keys]
    text = " / ".join(v for v in (_one(profile, k) for k in keys) if v)
    if field.transform and text:
        words = text.split()
        text = words[0] if field.transform == "family_name" else " ".join(words[1:])
    return text.upper() if field.uppercase else text


def prefill(
    spec: FormSpec, profile: ProfileData, procedure_title: str | None = None
) -> dict[str, str]:
    values = {f.key: format_profile_value(f, profile) for f in spec.fields}
    if procedure_title:
        for f in spec.fields:
            if f.from_procedure_title:
                values[f.key] = procedure_title
    return values


@lru_cache
def get_forms() -> FormRegistry:
    from hosoai.settings import Settings

    return FormRegistry(Settings().data_dir / "forms")
