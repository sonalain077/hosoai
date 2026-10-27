"""Parser for procedure pages on Cổng Dịch vụ công tỉnh Lào Cai (dichvucong.laocai.gov.vn).

Page layout: title in #cttt-wrapper h4, code in .panel-heading strong, general info in a
two-column table under #basic-info, then tabs #step-by-step, #component, #conditional.
Fees on this portal are Lào Cai's own; other provinces may differ.
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

PUBLISHER = "Cổng Dịch vụ công tỉnh Lào Cai"
PROVINCE_WARNING = (
    "Lệ phí theo quy định của tỉnh Lào Cai; mức thu ở tỉnh/thành khác có thể khác. "
    "(Fees are Lào Cai's; other provinces may charge differently.)"
)


def _info_rows(soup: BeautifulSoup) -> dict[str, Tag]:
    out: dict[str, Tag] = {}
    table = soup.select_one("#basic-info table")
    if table is None:
        return out
    for row in table.select("tbody > tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) >= 2:
            out.setdefault(clean(cells[0].get_text(" ")).lower(), cells[1])
    return out


def _fee(rows: dict[str, Tag]) -> str | None:
    parts = []
    for key, label in (("lệ phí", "Lệ phí"), ("phí", "Phí")):
        text = one_text(rows.get(key))
        if text:
            parts.append(f"{label}: {text}")
    return "\n".join(parts) or None


def parse(html: str, *, slug: str, url: str, source: Source, warnings: list[str]) -> Procedure:
    soup = BeautifulSoup(html, "html.parser")
    wrapper = soup.select_one("#cttt-wrapper")
    title_el = wrapper.select_one("h4") if wrapper else None
    code_el = soup.select_one("#cttt-wrapper .panel-heading strong")
    if title_el is None or code_el is None:
        raise ParseError(f"{url}: no title or procedure code; not a procedure page")
    for label in title_el.select("span.label"):
        label.decompose()  # "Toàn trình" / "Một phần" badge
    title = clean(title_el.get_text(" "))
    code = clean(code_el.get_text())
    src = source.model_copy(update={"title": title, "document_number": code})
    rows = _info_rows(soup)
    component = soup.select_one("#component")
    forms = form_links(component, url, src)  # before documents(), which removes tables
    return Procedure(
        slug=slug,
        title=title,
        national_code=code,
        field=sourced(one_text(rows.get("lĩnh vực")), src),
        agency=sourced(one_text(rows.get("cơ quan thực hiện")), src),
        methods=sourced_list(paragraphs(rows.get("cách thức thực hiện")), src),
        steps=sourced_list(paragraphs(soup.select_one("#step-by-step")), src),
        processing_time=sourced(one_text(rows.get("thời hạn giải quyết")), src),
        fee=sourced(_fee(rows), src),
        documents=documents(component, src),
        conditions=sourced(one_text(soup.select_one("#conditional")), src),
        legal_basis=sourced_list(paragraphs(rows.get("căn cứ pháp lý")), src),
        result=sourced(one_text(rows.get("kết quả thực hiện")), src),
        forms=forms,
        warnings=[*warnings, PROVINCE_WARNING],
        source=src,
    )
