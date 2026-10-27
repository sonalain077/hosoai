"""Form filling on a synthetic form (labels + dotted lines + ID boxes). Fake data only."""

import json
from collections.abc import Iterator
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from hosoai.forms.fill import fill_pdf
from hosoai.forms.models import FormSpec
from hosoai.forms.registry import FormRegistry, get_forms
from hosoai.main import app
from hosoai.settings import Settings

FONT = Settings().data_dir / "fonts" / "DejaVuSans.ttf"
client = TestClient(app)

SPEC = {
    "id": "test-form",
    "code": "TEST01",
    "title": "Tờ khai thử nghiệm",
    "procedure_slugs": ["temporary-residence"],
    "file": "form.pdf",
    "source": {
        "url": "https://example.gov.vn/form.doc",
        "title": "Tờ khai thử nghiệm",
        "retrieved_at": "2026-10-27T00:00:00Z",
    },
    "fields": [
        {"key": "name", "label": "1. Họ, chữ đệm và tên:", "profile_key": "full_name"},
        {"key": "dob", "label": "2. Ngày, tháng, năm sinh:", "profile_key": "date_of_birth"},
        {
            "key": "id",
            "label": "3. Số định danh cá nhân:",
            "profile_key": "id_number",
            "mode": "boxes",
        },
        {"key": "reason", "label": "4. Nội dung đề nghị:"},
    ],
}


def _make_form(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    y = 100
    for f in SPEC["fields"]:
        label = f["label"]  # type: ignore[index]
        page.insert_text(
            (50, y),
            f"{label} ........................................",
            fontfile=str(FONT),
            fontname="vi",
            fontsize=11,
        )
        if f.get("mode") == "boxes":  # type: ignore[union-attr]
            for i in range(12):
                page.draw_rect(pymupdf.Rect(220 + i * 16, y - 11, 234 + i * 16, y + 3))
        y += 40
    doc.save(path)


@pytest.fixture
def forms_dir(tmp_path: Path) -> Iterator[Path]:
    d = tmp_path / "test-form"
    d.mkdir()
    (d / "form.json").write_text(json.dumps(SPEC, ensure_ascii=False), "utf-8")
    _make_form(d / "form.pdf")
    registry = FormRegistry(tmp_path)
    app.dependency_overrides[get_forms] = lambda: registry
    yield d
    app.dependency_overrides.pop(get_forms, None)


def _words_right_of(pdf: bytes, label: str) -> str:
    page = pymupdf.open(stream=pdf, filetype="pdf")[0]
    rect = page.search_for(label)[0]
    words = [w for w in page.get_text("words") if w[0] >= rect.x1 and abs(w[3] - rect.y1) < 6]
    return " ".join(w[4] for w in sorted(words, key=lambda w: w[0]))


def test_values_land_after_their_labels(forms_dir: Path) -> None:
    spec = FormSpec.model_validate(SPEC)
    pdf = fill_pdf(
        spec, forms_dir / "form.pdf", FONT, {"name": "Nguyễn Văn Thử", "reason": "Đăng ký tạm trú"}
    )
    assert "Nguyễn Văn Thử" in _words_right_of(pdf, "1. Họ, chữ đệm và tên:")
    assert "Đăng ký tạm trú" in _words_right_of(pdf, "4. Nội dung đề nghị:")
    assert "Nguyễn" not in _words_right_of(pdf, "2. Ngày, tháng, năm sinh:")


def test_id_number_goes_one_digit_per_box(forms_dir: Path) -> None:
    spec = FormSpec.model_validate(SPEC)
    pdf = fill_pdf(spec, forms_dir / "form.pdf", FONT, {"id": "012345678901"})
    page = pymupdf.open(stream=pdf, filetype="pdf")[0]
    digits = sorted(
        (w for w in page.get_text("words") if w[4].isdigit() and len(w[4]) == 1), key=lambda w: w[0]
    )
    assert "".join(w[4] for w in digits) == "012345678901"
    for i, w in enumerate(digits):  # each digit inside its own box
        assert 220 + i * 16 <= w[0] and w[2] <= 234 + i * 16


def test_api_prefills_from_profile_and_requires_review(forms_dir: Path) -> None:
    client.put("/profile", json={"full_name": "Nguyễn Văn Thử", "date_of_birth": "1990-05-20"})
    detail = client.get("/forms/test-form").json()
    assert detail["values"]["name"] == "Nguyễn Văn Thử"
    assert detail["values"]["dob"] == "20/05/1990"
    assert detail["values"]["reason"] == ""
    assert detail["spec"]["source"]["url"].endswith(".doc")

    values = {**detail["values"], "reason": "Đăng ký tạm trú"}
    assert (
        client.post("/forms/test-form/fill", json={"values": values, "reviewed": False}).status_code
        == 422
    )
    r = client.post("/forms/test-form/fill", json={"values": values, "reviewed": True})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "20/05/1990" in _words_right_of(r.content, "2. Ngày, tháng, năm sinh:")


def test_blank_pdf_and_unknown_form(forms_dir: Path) -> None:
    assert client.get("/forms/test-form/blank.pdf").content.startswith(b"%PDF")
    assert client.get("/forms/nope").status_code == 404
    assert [f["id"] for f in client.get("/forms").json()] == ["test-form"]


def test_no_code_path_submits_to_government() -> None:
    """The app only generates files. No route or module posts to a government host."""
    src = Path(__file__).parents[1] / "src" / "hosoai"
    for py in src.rglob("*.py"):
        if py.name == "ingest.py":  # read-only GETs of public procedure pages
            continue
        text = py.read_text("utf-8")
        assert "httpx.post" not in text and "requests.post" not in text, py


def test_real_form_specs_match_their_official_pdfs() -> None:
    """Every shipped form: official source, PDF present, every label found, fills cleanly."""
    from hosoai.forms.registry import FormRegistry
    from hosoai.procedures.store import get_store

    registry = FormRegistry(Settings().data_dir / "forms")
    summaries = registry.list()
    assert summaries, "no forms shipped in data/forms"
    store = get_store()
    for summary in summaries:
        spec = registry.get(summary.id)
        assert spec is not None
        assert (spec.source.url.host or "").endswith(".gov.vn"), spec.id
        for slug in spec.procedure_slugs:
            assert store.get(slug) is not None, f"{spec.id}: unknown procedure {slug}"
        sample = {
            f.key: (
                "012345678901"
                if f.mode == "boxes"
                else "20/05/1990"
                if f.mode == "date_parts"
                else next(iter(f.choices or {"Thử": ""}))
                if f.mode == "choice"
                else "Thử"
            )
            for f in spec.fields
        }
        pdf = fill_pdf(spec, registry.pdf_path(spec), FONT, sample)  # raises if a label is missing
        assert pdf.startswith(b"%PDF")


def test_previews_are_png_images(forms_dir: Path) -> None:
    blank = client.get("/forms/test-form/pages/0.png")
    assert blank.status_code == 200 and blank.content.startswith(b"\x89PNG")
    filled = client.post("/forms/test-form/preview/0.png", json={"values": {"name": "Thử"}})
    assert filled.status_code == 200 and filled.content.startswith(b"\x89PNG")
    assert filled.content != blank.content
    assert client.get("/forms/test-form/pages/9.png").status_code == 404


def test_request_field_prefilled_with_official_procedure_title() -> None:
    detail = client.get("/forms/ct01?procedure=temporary-residence").json()
    assert detail["values"]["request"] == "Đăng ký tạm trú"
    # a procedure the form doesn't belong to is ignored
    assert client.get("/forms/ct01?procedure=passport").json()["values"]["request"] == ""


def _na5() -> tuple[FormSpec, Path]:
    registry = FormRegistry(Settings().data_dir / "forms")
    spec = registry.get("na5")
    assert spec is not None
    return spec, registry.pdf_path(spec)


def _word_after(pdf: bytes, page_no: int, label: str, text: str) -> tuple[float, float]:
    page = pymupdf.open(stream=pdf, filetype="pdf")[page_no]
    rect = page.search_for(label)[-1]
    hits = [w for w in page.get_text("words") if w[4] == text and abs(w[3] - rect.y1) < 6]
    assert hits, f"{text!r} not on the line of {label!r}"
    return hits[0][0], rect.x1


def test_na5_ticks_the_right_box() -> None:
    spec, pdf_path = _na5()
    for value, other in (("Nam", "Nữ"), ("Nữ", "Nam")):
        pdf = fill_pdf(spec, pdf_path, FONT, {"sex": value})
        page = pymupdf.open(stream=pdf, filetype="pdf")[0]
        label = page.search_for("2- Giới tính:")[0]
        x_mark = next(w for w in page.get_text("words") if w[4] == "X")
        opt = next(r for r in page.search_for(value) if abs(r.y1 - label.y1) < 4)
        not_opt = next(r for r in page.search_for(other) if abs(r.y1 - label.y1) < 4)
        assert opt.x1 <= x_mark[0] <= opt.x1 + 20  # right after the chosen option
        assert not (not_opt.x1 <= x_mark[0] <= not_opt.x1 + 20)


def test_na5_dates_and_split_labels() -> None:
    spec, pdf_path = _na5()
    pdf = fill_pdf(
        spec,
        pdf_path,
        FONT,
        {"date_of_birth": "20/05/1990", "entry_date": "15/08/2026", "reason": "Du lịch"},
    )
    # day after "Sinh ngày", month after "tháng", year after "năm"
    x_day, label_end = _word_after(pdf, 0, "3- Sinh ngày", "20")
    assert x_day >= label_end
    # "8- Nhập cảnh…" is printed in two fonts: the day must still come after the whole label
    x_entry, entry_end = _word_after(pdf, 0, "Nhập cảnh Việt Nam ngày:", "15")
    assert x_entry >= entry_end
    # "3- Lý do Reason(s)": italic part included in the label
    x_reason, reason_end = _word_after(pdf, 1, "Reason(s)", "Du")
    assert x_reason >= reason_end
