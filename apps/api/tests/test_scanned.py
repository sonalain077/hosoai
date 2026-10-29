"""Scanned (image-only) forms: code finds the lines, the vision model only reads labels.

No real AI: the vision and chat replies are recorded in fixtures/llm/learn/scanned-*.json.
The scanned form is drawn here from fake labels, then turned into an image-only PDF.
"""

from pathlib import Path

import pymupdf
import pytest

from hosoai.evals.run import rasterize
from hosoai.forms.fill import _label_rect, fill_pdf
from hosoai.forms.learn.scanned import find_lines, group_dates, is_scanned, learn_scanned
from hosoai.forms.registry import FormRegistry
from hosoai.llm import ChatMessage, FakeLLMClient
from hosoai.llm.client import to_openai
from hosoai.settings import Settings
from hosoai.sources.models import Source
from tests.conftest import FIXTURES

DATA = Settings().data_dir
FONT = DATA / "fonts" / "DejaVuSans.ttf"
SRC = Source(url="https://x.gov.vn/scan.pdf", title="Scan", retrieved_at="2026-10-29T00:00:00Z")
ROWS = [
    "1. Họ và tên:",
    "2. Số định danh cá nhân:",
    "3. Nơi thường trú:",
    "4. Số điện thoại:",
    "5. Họ tên của cha:",
    "6. Lý do đề nghị:",
]


def _dots(page: pymupdf.Page, x0: float, x1: float, y: float) -> None:
    x = x0
    while x < x1:
        page.draw_circle((x, y), 0.6, color=(0, 0, 0), fill=(0, 0, 0))
        x += 4


def make_scan(path: Path) -> Path:
    """A one-page form with dotted lines and a split date, saved as an image only."""
    doc = pymupdf.open()
    p = doc.new_page(width=595, height=842)
    font = pymupdf.Font(fontfile=str(FONT))

    def text(x: float, y: float, s: str, size: float = 11) -> float:
        p.insert_text((x, y), s, fontsize=size, fontfile=str(FONT), fontname="vi")
        return x + font.text_length(s, fontsize=size)

    text(150, 60, "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", 12)
    text(200, 110, "TỜ KHAI XIN CẤP GIẤY XÁC NHẬN", 13)
    y = 170
    for row in ROWS:
        _dots(p, text(60, y, row) + 4, 540, y)
        y += 40
    # 7. Ngày cấp: ……/……/……
    x = text(60, y, "7. Ngày cấp:") + 4
    for i in range(3):
        _dots(p, x, x + 40, y)
        x += 40
        if i < 2:
            x = text(x + 2, y, "/") + 4
    text(380, y + 70, "Người khai (ký, ghi rõ họ tên)")
    pix = p.get_pixmap(dpi=150, colorspace=pymupdf.csGRAY)
    scan = pymupdf.open()
    page = scan.new_page(width=595, height=842)
    page.insert_image(page.rect, stream=pix.tobytes("png"))
    scan.save(path)
    return path


@pytest.fixture(scope="module")
def scan(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_scan(tmp_path_factory.mktemp("scan") / "form.pdf")


def _learn(scan: Path, fixture: str) -> tuple:  # type: ignore[type-arg]
    llm = FakeLLMClient(FIXTURES / "learn" / f"{fixture}.json")
    spec, report = learn_scanned(
        form_id="scan-test",
        code="X01",
        title="Tờ khai xin cấp giấy xác nhận",
        procedure_slugs=[],
        pdf=scan,
        original_file=None,
        source=SRC,
        llm=llm,
        model_name="fake",
        log=lambda *_: None,
    )
    return spec, report, llm


def test_scanned_forms_are_recognised(scan: Path) -> None:
    assert is_scanned(pymupdf.open(scan))
    assert not is_scanned(pymupdf.open(DATA / "forms" / "ct01" / "CT01.pdf"))


def test_code_finds_every_writing_line(scan: Path) -> None:
    page = pymupdf.open(scan)[0]
    groups = group_dates(find_lines(page))
    assert len(groups) == len(ROWS) + 1  # the title and the signature line are not lines
    assert len(groups[-1]) == 3  # the date: day, month, year boxes
    for g in groups:
        for box in g:  # each box is empty: nothing printed where we will write
            assert page.get_pixmap(clip=box + (0, 0, 0, -3)).color_count() <= 2


def test_lines_on_a_scanned_official_form_match_the_reviewed_spec(tmp_path: Path) -> None:
    """Rasterize CT01: every line the human spec writes on is found by code alone."""
    registry = FormRegistry(DATA / "forms")
    human = registry.get("ct01")
    assert human is not None
    scan = pymupdf.open(rasterize(registry.pdf_path(human), tmp_path / "ct01-scan.pdf"))
    text_pdf = pymupdf.open(registry.pdf_path(human))
    boxes = {i: find_lines(scan[i]) for i in range(len(scan))}
    line_fields = [f for f in human.fields if f.mode in ("after_label", "date_parts")]
    for f in line_fields:
        r = _label_rect(text_pdf[f.page], f)
        x = f.below_x + 2 if f.below_x is not None else r.x1 + f.x_offset + 6
        y = r.y1 + r.height - 4 if f.below_x is not None else r.y1 - 4
        assert any((b + (-4, -4, 4, 4)).contains(pymupdf.Point(x, y)) for b in boxes[f.page]), f.key


def test_vision_reads_labels_and_chat_model_decides(scan: Path) -> None:
    spec, report, llm = _learn(scan, "scanned-ideal")
    n = len(ROWS) + 1
    assert llm.vision == [True] * n + [False]  # label reads, then one decision
    assert all(len(c[0].images) == 1 for c in llm.calls[:n])  # one crop per read
    assert not llm.calls[n][-1].images  # the decision never sees an image
    keys = {f.key: f for f in spec.fields}
    assert spec.status == "draft" and report.rejected == {}
    assert all(f.mode == "region" and f.rect for f in spec.fields)
    assert keys["full_name"].profile_key == "full_name"
    assert keys["father_name"].profile_key is None  # another person
    assert keys["id_issue_date"].parts and len(keys["id_issue_date"].parts) == 3
    assert spec.learned and "vision" in str(spec.learned["method"])


def test_wrong_profile_links_are_sent_back(scan: Path) -> None:
    """The model links the father to the applicant's name and skips the phone: both fixed."""
    spec, report, llm = _learn(scan, "scanned-repair")
    assert report.rounds == 2
    feedback = llm.calls[-1][-1].content
    assert "another person" in feedback
    assert "add it with profile 'phone'" in feedback
    keys = {f.key: f for f in spec.fields}
    assert keys["father_name"].profile_key is None
    assert keys["phone"].profile_key == "phone"


def test_values_land_inside_the_found_boxes(scan: Path, tmp_path: Path) -> None:
    spec, _, _ = _learn(scan, "scanned-ideal")
    values = {
        "full_name": "Nguyễn Văn Thử",
        "id_number": "012345678901",
        "phone": "0900000000",
        "id_issue_date": "01/02/2021",
        "reason": "Một lý do rất dài để kiểm tra việc thu nhỏ chữ cho vừa với dòng kẻ chấm",
    }
    out = tmp_path / "filled.pdf"
    out.write_bytes(fill_pdf(spec, scan, FONT, values))
    page = pymupdf.open(out)[0]
    keys = {f.key: f for f in spec.fields}
    for key in ("full_name", "id_number", "phone"):
        rect = pymupdf.Rect(keys[key].rect)
        assert page.get_textbox(rect + (-1, -1, 1, 1)).strip() == values[key]
    for part, piece in zip(keys["id_issue_date"].parts, ["01", "02", "2021"], strict=True):
        assert page.get_textbox(pymupdf.Rect(part) + (-1, -1, 1, 1)).strip() == piece
    reason = page.get_textbox(pymupdf.Rect(keys["reason"].rect) + (-1, -1, 1, 1)).strip()
    assert reason == values["reason"]  # shrunk to fit, not cut


def test_images_are_sent_in_the_openai_format() -> None:
    m = ChatMessage(role="user", content="read this", images=["QUJD"])
    msg = to_openai(m)
    assert msg["content"][0] == {"type": "text", "text": "read this"}
    assert msg["content"][1]["image_url"]["url"] == "data:image/png;base64,QUJD"
    assert to_openai(ChatMessage(role="user", content="hi")) == {"role": "user", "content": "hi"}
