"""Parsers read official pages into Procedures. No network: fixtures are saved copies of
public pages from dichvucong.bocongan.gov.vn and dichvucong.laocai.gov.vn."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from hosoai.procedures.models import Procedure
from hosoai.sources.models import Source
from hosoai.sources.parsers import bca, laocai
from hosoai.sources.parsers.common import ParseError

HTML = Path(__file__).parent / "fixtures" / "html"
BCA_URL = "https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=29497"
LC_URL = "https://dichvucong.laocai.gov.vn/trang-chu/tra-cuu/chi-tiet-thu-tuc?ma-thu-tuc=47907"


def _src(url: str) -> Source:
    return Source(url=url, title="catalog title", retrieved_at=datetime(2026, 10, 26, tzinfo=UTC))  # type: ignore[arg-type]


def _bca(html: str | None = None) -> Procedure:
    html = html or (HTML / "bca-29497.html").read_text("utf-8")
    return bca.parse(html, slug="passport", url=BCA_URL, source=_src(BCA_URL), warnings=[])


def _laocai(html: str | None = None) -> Procedure:
    html = html or (HTML / "laocai-47907.html").read_text("utf-8")
    return laocai.parse(html, slug="birth", url=LC_URL, source=_src(LC_URL), warnings=[])


def _all_sources(p: Procedure) -> list[Source]:
    items = [p.field, p.agency, p.processing_time, p.fee, p.conditions, p.result]
    sources = [i.source for i in items if i is not None]
    for group in (p.methods, p.steps, p.legal_basis, p.documents, p.forms):
        sources += [i.source for i in group]
    return [p.source, *sources]


@pytest.mark.parametrize("parse", [_bca, _laocai])
def test_every_item_cites_the_page_it_came_from(parse) -> None:  # type: ignore[no-untyped-def]
    p = parse()
    for s in _all_sources(p):
        assert str(s.url) == str(p.source.url)
        assert s.document_number == p.national_code
        assert s.title == p.title  # title from the page, not the catalog


def test_bca_passport() -> None:
    p = _bca()
    assert p.title == "Cấp hộ chiếu phổ thông ở trong nước (thực hiện tại cấp tỉnh)"
    assert p.national_code == "1.001456"
    assert [m.text for m in p.methods] == ["Trực tiếp", "Trực tuyến", "Dịch vụ bưu chính"]
    assert p.steps[0].text.startswith("Bước 1")
    assert p.processing_time and "08 Ngày làm việc" in p.processing_time.text
    assert p.fee and "160.000" in p.fee.text
    assert len(p.documents) == 7
    tk01 = [d for d in p.documents if d.form_name and "TK01 MỚI" in d.form_name]
    assert tk01 and tk01[0].quantity == "Bản chính: 1, Bản sao: 0"
    assert any("49/2019/QH14" in lb.text for lb in p.legal_basis)
    assert [str(f.url) for f in p.forms] == [
        "https://dichvucong.bocongan.gov.vn/public_dir/tttl/01/2024/08/MauTK05tt31e02d0_1723631335.doc"
    ]


def test_laocai_birth_registration() -> None:
    p = _laocai()
    assert p.title == "Thủ tục đăng ký khai sinh"
    assert p.national_code == "1.001193.000.00.00.H38"
    assert p.field and p.field.text == "Hộ Tịch"
    assert p.fee and "8.000 đồng" in p.fee.text
    assert any("120/2025/NĐ-CP" in lb.text for lb in p.legal_basis)
    assert any(
        lb.text.startswith("Luật Hộ tịch năm 2014") for lb in p.legal_basis
    )  # no broken lines
    assert any("Giấy chứng sinh" in d.name for d in p.documents)
    assert p.forms and str(p.forms[0].url).endswith("TKngkkhaisinh.doc")
    assert any("Lào Cai" in w for w in p.warnings)  # province-specific fee warning


def test_missing_section_stays_empty_not_invented() -> None:
    html = (HTML / "bca-29497.html").read_text("utf-8").replace(">Thời hạn giải quyết<", ">XX<")
    assert _bca(html).processing_time is None


@pytest.mark.parametrize("parse", [_bca, _laocai])
def test_non_procedure_page_is_rejected(parse) -> None:  # type: ignore[no-untyped-def]
    bot_check = "<html><head><script>window['bobcmn']='...TSPD...'</script></head></html>"
    with pytest.raises(ParseError):
        parse(bot_check)


def test_documents_from_table_and_paragraphs() -> None:
    from bs4 import BeautifulSoup

    from hosoai.sources.parsers.common import documents

    html = """<div><table>
      <tr><td>Tên giấy tờ</td><td>Mẫu đơn, tờ khai</td><td>Số lượng</td></tr>
      <tr><td>Giấy đề nghị</td><td>Mau1.doc</td><td>Bản chính: 1<br>Bản sao: 0</td></tr>
    </table><p>- Ảnh 4x6</p></div>"""
    docs = documents(BeautifulSoup(html, "html.parser").div, _src(LC_URL))
    assert [(d.name, d.form_name, d.quantity) for d in docs] == [
        ("Giấy đề nghị", "Mau1.doc", "Bản chính: 1, Bản sao: 0"),
        ("Ảnh 4x6", None, None),
    ]
