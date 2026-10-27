"""Parser for procedure pages on Cổng Dịch vụ công - Bộ Công an (dichvucong.bocongan.gov.vn).

Page layout: each section is a div.tthc-list-item with a div.item-title (section name)
and a div.tthc-list-item-detail (content).
"""

from bs4 import BeautifulSoup, Tag

from hosoai.procedures.models import Procedure
from hosoai.sources.models import Source
from hosoai.sources.parsers.common import (
    ParseError,
    clean,
    documents,
    form_links,
    one_text,
    paragraphs,
    sourced,
    sourced_list,
)

PUBLISHER = "Cổng Dịch vụ công - Bộ Công an"


def _sections(soup: BeautifulSoup) -> dict[str, Tag]:
    out: dict[str, Tag] = {}
    for item in soup.select("div.tthc-list-item"):
        title = item.select_one("div.item-title")
        detail = item.select_one("div.tthc-list-item-detail")
        if title and detail:
            out.setdefault(clean(title.get_text(" ")).lower(), detail)
    return out


def _fee(sections: dict[str, Tag]) -> str | None:
    parts = []
    for key, label in (("phí", "Phí"), ("lệ phí", "Lệ phí")):
        text = one_text(sections.get(key))
        if text:
            parts.append(f"{label}: {text}")
    return "\n".join(parts) or None


def parse(html: str, *, slug: str, url: str, source: Source, warnings: list[str]) -> Procedure:
    soup = BeautifulSoup(html, "html.parser")
    sections = _sections(soup)
    if "mã thủ tục" not in sections:
        raise ParseError(f"{url}: no 'Mã thủ tục' section; not a procedure page")
    title_el = soup.select_one("div.tthc-title h4")
    if title_el is None:
        raise ParseError(f"{url}: no title")
    title = clean(title_el.get_text(" "))
    code = one_text(sections["mã thủ tục"])
    src = source.model_copy(update={"title": title, "document_number": code})
    g = sections.get
    return Procedure(
        slug=slug,
        title=title,
        national_code=code,
        field=sourced(one_text(g("lĩnh vực")), src),
        agency=sourced(one_text(g("cơ quan thực hiện")), src),
        methods=sourced_list(paragraphs(g("cách thức thực hiện")), src),
        steps=sourced_list(paragraphs(g("trình tự thực hiện")), src),
        processing_time=sourced(one_text(g("thời hạn giải quyết")), src),
        fee=sourced(_fee(sections), src),
        documents=documents(g("thành phần hồ sơ"), src),
        conditions=sourced(one_text(g("yêu cầu - điều kiện")), src),
        legal_basis=sourced_list(paragraphs(g("căn cứ pháp lý")), src),
        result=sourced(one_text(g("kết quả thực hiện")), src),
        forms=form_links(g("biểu mẫu"), url, src),
        warnings=warnings,
        source=src,
    )
