import re
from urllib.parse import urljoin

from bs4 import Tag

from hosoai.procedures.models import FormFile, RequiredDocument, SourcedText
from hosoai.sources.models import Source

FORM_EXTENSIONS = (".doc", ".docx", ".pdf", ".xls", ".xlsx")


class ParseError(Exception):
    """The page is not a procedure page we can read (blocked, error page, layout changed)."""


def clean(text: str) -> str:
    text = text.replace("\xa0", " ").replace("‎", "")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{2,}", "\n", text).strip()


BULLET = re.compile(r"^[-–•]\s*")


def block_text(el: Tag) -> str:
    """Text of one block. Only <br> breaks lines; inline tags (<a>, <strong>) don't."""
    for br in el.find_all("br"):
        br.replace_with("\n")
    lines = [BULLET.sub("", line) for line in clean(el.get_text("")).split("\n")]
    return "\n".join(line for line in lines if line)


def paragraphs(el: Tag | None) -> list[str]:
    """Text blocks of an element, one per <p>/<li>/<tr>, or one per line as a fallback."""
    if el is None:
        return []
    blocks = [
        b
        for b in el.find_all(["p", "li", "tr"])
        if not b.find(["p", "li", "tr"])  # innermost blocks only
    ]
    if blocks:
        texts = [block_text(b) for b in blocks]
    else:
        texts = block_text(el).split("\n")
    return [t for t in texts if t and t not in {"*", "+"}]


HEADER_CELLS = {"tên giấy tờ", "mẫu đơn, tờ khai", "số lượng"}


def documents(el: Tag | None, source: Source) -> list[RequiredDocument]:
    """Required documents, written either as a table (name | form | quantity) or as paragraphs."""
    if el is None:
        return []
    docs: list[RequiredDocument] = []
    for table in el.find_all("table"):
        for row in table.find_all("tr"):
            if row.find("th"):
                continue
            cells = [block_text(td) for td in row.find_all("td", recursive=False)]
            if not cells or not cells[0] or cells[0].lower() in HEADER_CELLS:
                continue
            docs.append(
                RequiredDocument(
                    name=cells[0],
                    form_name=(cells[1] or None) if len(cells) > 1 else None,
                    quantity=(cells[2].replace("\n", ", ") or None) if len(cells) > 2 else None,
                    source=source,
                )
            )
        table.extract()  # remaining text is the non-table part
    docs += [RequiredDocument(name=p, source=source) for p in paragraphs(el)]
    return docs


def one_text(el: Tag | None) -> str | None:
    """All text of an element as one string, or None when the element is missing or empty."""
    text = "\n".join(paragraphs(el))
    return text or None


def sourced(text: str | None, source: Source) -> SourcedText | None:
    return SourcedText(text=text, source=source) if text else None


def sourced_list(texts: list[str], source: Source) -> list[SourcedText]:
    return [SourcedText(text=t, source=source) for t in texts]


def form_links(el: Tag | None, base_url: str, source: Source) -> list[FormFile]:
    if el is None:
        return []
    forms: list[FormFile] = []
    for a in el.find_all("a", href=True):
        href = str(a["href"])
        if not href.lower().split("?")[0].endswith(FORM_EXTENSIONS):
            continue
        label = clean(a.get_text(" ")) or href.rsplit("/", 1)[-1]
        if label.lower() in {"tải về", "download"}:
            # BCA puts the description in a sibling <span> and "Tải về" in the link
            prev = a.find_previous_sibling("span")
            label = clean(prev.get_text(" ")) if prev else href.rsplit("/", 1)[-1]
        forms.append(FormFile(label=label, url=urljoin(base_url, href), source=source))
    return forms
