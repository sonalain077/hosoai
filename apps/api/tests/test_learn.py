"""Form-learning agent on the real TK05 PDF, with recorded model replies (no real AI)."""

from pathlib import Path

import pymupdf
import pytest

from hosoai.forms.fill import fill_pdf
from hosoai.forms.learn.agent import learn
from hosoai.forms.learn.candidates import extract
from hosoai.forms.learn.fetch import FetchError, download, form_code, form_title
from hosoai.llm import FakeLLMClient
from hosoai.settings import Settings
from hosoai.sources.models import Source
from tests.conftest import FIXTURES

DATA = Settings().data_dir
PDF = DATA / "forms" / "tk05" / "form.pdf"
FONT = DATA / "fonts" / "DejaVuSans.ttf"
SRC = Source(url="https://x.gov.vn/tk05.doc", title="TK05", retrieved_at="2026-10-27T00:00:00Z")


def _learn(fixture: str) -> tuple:  # type: ignore[type-arg]
    return learn(
        form_id="tk05-test",
        code="TK05",
        title="Đơn trình báo mất hộ chiếu phổ thông",
        procedure_slugs=["passport"],
        pdf=PDF,
        original_file=None,
        source=SRC,
        font=FONT,
        llm=FakeLLMClient(FIXTURES / "learn" / f"{fixture}.json"),
        model_name="fake",
        log=lambda *_: None,
    )


def test_candidates_cover_the_form() -> None:
    cands = {c.text.replace("\xa0", " "): c for c in extract(pymupdf.open(PDF))}
    assert cands["1. Họ"].blank == "dots"
    assert cands["2. Giới tính:"].options == ["Nam", "Nữ"]
    assert cands["3. Sinh ngày"].date == "words"
    assert cands["4. Số ĐDCN/CMND (nếu có)"].boxes == 12
    assert cands["Ngày cấp:"].date == "slash"
    assert any(c.blank == "next_line" for c in cands.values())


def test_code_and_title_read_from_the_form() -> None:
    doc = pymupdf.open(PDF)
    assert form_code(doc) == "TK05"
    assert form_title(doc) == "Đơn trình báo mất hộ chiếu phổ thông"


def test_ideal_answer_passes_every_check() -> None:
    spec, report = _learn("tk05-ideal")
    assert report.rejected == {}
    assert len(spec.fields) == 17
    assert spec.status == "draft"
    keys = {f.key: f for f in spec.fields}
    assert keys["family_name"].transform == "family_name"
    assert keys["id_number"].mode == "boxes"
    assert keys["sex"].mode == "choice"
    assert keys["date_of_birth"].separators == ["tháng", "năm"]


def test_bad_answer_is_repaired_through_feedback() -> None:
    spec, report = _learn("tk05-repair")
    assert report.rounds == 2  # first answer had errors, second fixed them
    assert len(spec.fields) == 17


def test_learned_form_fills_cleanly_with_long_values() -> None:
    spec, _ = _learn("tk05-ideal")
    values = {f.key: "Nguyễn Văn Thử Rất Dài Để Kiểm Tra" for f in spec.fields}
    values.update(
        sex="Nam",
        date_of_birth="20/05/1990",
        id_number="012345678901",
        id_issue_date="01/02/2021",
        passport_issue_date="03/04/2020",
        lost_date="25/10/2026",
    )
    pdf = fill_pdf(spec, PDF, FONT, values)
    assert pdf.startswith(b"%PDF")


def test_only_official_hosts_are_downloaded(tmp_path: Path) -> None:
    with pytest.raises(FetchError):
        download("https://example.com/form.doc", tmp_path, "x")
    with pytest.raises(FetchError):
        download("http://dichvucong.bocongan.gov.vn/form.doc", tmp_path, "x")


def test_official_forms_endpoint_marks_known_forms() -> None:
    from fastapi.testclient import TestClient

    from hosoai.main import app

    rows = TestClient(app).get("/procedures/temporary-residence/official-forms").json()
    assert rows and all(r["url"].startswith("https://") for r in rows)
    ct01 = [r for r in rows if r["form_id"] == "ct01"]
    assert ct01 and ct01[0]["status"] == "reviewed"


def test_learn_endpoint_rejects_unknown_procedure_and_index() -> None:
    from fastapi.testclient import TestClient

    from hosoai.main import app, get_llm

    app.dependency_overrides[get_llm] = lambda: FakeLLMClient(
        FIXTURES / "learn" / "tk05-ideal.json"
    )
    try:
        c = TestClient(app)
        assert (
            c.post("/forms/learn", json={"procedure": "nope", "form_index": 0}).status_code == 404
        )
        r = c.post("/forms/learn", json={"procedure": "passport", "form_index": 99})
        assert r.status_code == 422
    finally:
        app.dependency_overrides.pop(get_llm, None)


def test_fields_about_other_people_never_use_the_applicants_profile() -> None:
    from hosoai.forms.learn.agent import consistency
    from hosoai.forms.learn.candidates import Candidate

    def cand(text: str) -> Candidate:
        return Candidate(id="c1", page=0, text=text, line_text=text, blank="dots")

    item = {"key": "x", "profile": "full_name"}
    for label in (
        "17. Họ, chữ đệm và tên của cha",
        "Họ tên mẹ",
        "11. Họ, chữ đệm và tên chủ hộ:",
        "2- Thân nhân bảo lãnh (Họ tên):",
    ):
        assert consistency(item, cand(label)), label
    assert consistency(item, cand("1. Họ, chữ đệm và tên:")) is None


def _facts_by_label(form: str, file: str) -> dict[str, list]:  # type: ignore[type-arg]
    from hosoai.forms.learn.agent import facts

    cands = extract(pymupdf.open(DATA / "forms" / form / file))
    known = facts(cands)
    out: dict[str, list] = {}  # type: ignore[type-arg]
    for c in cands:
        out.setdefault(c.text.replace("\xa0", " "), []).append(known[c.id])
    return out


def test_label_tells_which_profile_value_goes_where() -> None:
    f = _facts_by_label("ct01", "CT01.pdf")
    assert f["3. Giới tính:"][0].hint == "sex"
    assert f["6. Email:"][0].hint == "email"
    assert f["9. Nơi ở hiện tại:"][0].hint == "current_address"
    assert f["10. Nghề nghiệp,  nơi làm việc:"][0].hint == "occupation"
    assert f["8. Nơi tạm trú:"][0].hint is None  # unclear: left to the model


def test_sub_fields_belong_to_the_person_of_their_item() -> None:
    f = _facts_by_label("cco1", "form.pdf")
    # "17. Họ tên của cha … Quốc tịch … Số CCCD": all about the father
    assert all(x.other for x in f["Quốc tịch:"])
    assert all(x.other for x in f["Số CCCD/CMND"])
    assert f["8. Quốc tịch:"][0].hint == "nationality"
    assert f["5. Số CMND/CCCD"][0].hint == "id_number"
    na5 = _facts_by_label("na5", "NA5.pdf")
    assert na5["4- Quốc tịch gốc:"][0].no_profile
    assert all(x.other for x in na5["Cấp ngày:"])  # the sponsor's document


def test_wrong_profile_for_a_clear_label_is_rejected() -> None:
    from hosoai.forms.learn.agent import Facts, consistency
    from hosoai.forms.learn.candidates import Candidate

    # a shifted answer: the label says sex, the model's key says id_number
    c = Candidate(id="c4", page=0, text="3. Giới tính:", line_text="", blank="dots")
    assert consistency({"key": "id_number", "profile": "sex"}, c, Facts(hint="sex"))
    assert consistency({"key": "sex", "profile": "sex"}, c, Facts(hint="sex")) is None
    sign = Candidate(id="c21", page=0, text="ngày", line_text="Làm tại…ngày", blank="dots")
    assert consistency({"key": "date", "profile": "date_of_birth"}, sign, Facts())
    nat = Candidate(id="c5", page=0, text="4- Quốc tịch gốc:", line_text="", blank="dots")
    assert consistency({"key": "x", "profile": "nationality"}, nat, Facts(no_profile=True))


def test_name_split_is_read_from_the_label() -> None:
    from hosoai.forms.learn.agent import name_transform

    assert name_transform("1. Họ") == "family_name"
    assert name_transform("Chữ đệm và tên") == "given_names"
    assert name_transform("1. Họ, chữ đệm và tên:") is None


def test_drawn_tick_boxes_are_options() -> None:
    cands = {c.text: c for c in extract(pymupdf.open(DATA / "forms" / "na5" / "NA5.pdf"))}
    assert cands["2- Giới tính:"].blank == "checkbox"
    assert cands["2- Giới tính:"].options == ["Nam", "Nữ"]
    assert cands["3- Sinh ngày"].date == "words"  # no longer glued to "Nữ"


def test_form_code_fixes_letter_o_misprint() -> None:
    class _Page:
        def get_text(self) -> str:
            return "TỜ KHAI\nMẫu CCO1 ban hành kèm theo"

    assert form_code([_Page()]) == "CC01"  # type: ignore[arg-type]
