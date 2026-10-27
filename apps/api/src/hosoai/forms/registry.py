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

    def list(self) -> list[FormSummary]:
        return [FormSummary.model_validate(s.model_dump()) for s in self._specs.values()]

    def get(self, form_id: str) -> FormSpec | None:
        return self._specs.get(form_id)

    def pdf_path(self, spec: FormSpec) -> Path:
        return self.dir / spec.id / spec.file


def format_profile_value(field: FormField, profile: ProfileData) -> str:
    if field.profile_key is None:
        return ""
    value = getattr(profile, field.profile_key)
    if value is None:
        return ""
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return str(value)


def prefill(spec: FormSpec, profile: ProfileData) -> dict[str, str]:
    return {f.key: format_profile_value(f, profile) for f in spec.fields}


@lru_cache
def get_forms() -> FormRegistry:
    from hosoai.settings import Settings

    return FormRegistry(Settings().data_dir / "forms")
