"""Write values onto an official form PDF.

Three ways, picked per field:
- acroform:    the PDF has real form fields; set them by name.
- after_label: text PDF with a printed label followed by a dotted line; write after the label.
- boxes:       one character per printed box (e.g. the 12-digit ID number). Boxes may be
               drawn as rectangles or as table cells (vertical lines).
- date_parts:  "dd/mm/yyyy" written around the slashes already printed after the label.
Scanned (image-only) forms would need the vision model to find boxes; none of our forms
need that yet.
"""

import unicodedata
from pathlib import Path

import pymupdf

from hosoai.forms.models import FormField, FormSpec

FONT_SIZE = 10.5
INK = (0.12, 0.25, 0.65)  # ballpoint blue, so filled values are easy to review


class FieldNotFound(Exception):
    pass


def _nfd(text: str) -> str:
    return unicodedata.normalize("NFD", text)


def _search_normalized(page: pymupdf.Page, label: str) -> list[pymupdf.Rect]:
    """Fallback search over characters, comparing with accents normalized.

    Word files mix composed and decomposed Vietnamese accents ("í" vs "i" + U+0301),
    which page.search_for does not match.
    """
    target = _nfd(label)  # decomposed form, so partial matches are real prefixes
    hits: list[pymupdf.Rect] = []
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            chars = [c for span in line["spans"] for c in span["chars"]]
            for start in range(len(chars)):
                text = ""
                for end in range(start, len(chars)):
                    text += chars[end]["c"]
                    norm = _nfd(text)
                    if not target.startswith(norm):
                        break
                    if norm == target:
                        rect = pymupdf.Rect(chars[start]["bbox"])
                        for c in chars[start : end + 1]:
                            rect |= pymupdf.Rect(c["bbox"])
                        hits.append(rect)
                        break
    return hits


def _label_rect(page: pymupdf.Page, f: FormField) -> pymupdf.Rect:
    hits = page.search_for(f.label) or _search_normalized(page, f.label)
    if len(hits) <= f.occurrence:
        raise FieldNotFound(f"{f.key}: label {f.label!r} not found on page {f.page}")
    rect: pymupdf.Rect = hits[f.occurrence]
    return rect


def _boxes_after(page: pymupdf.Page, label: pymupdf.Rect) -> list[pymupdf.Rect]:
    """Character boxes on the label's line, right of the label, left to right."""
    boxes: list[pymupdf.Rect] = []
    verticals: list[tuple[float, float, float]] = []  # x, y_top, y_bottom
    mid = (label.y0 + label.y1) / 2
    for d in page.get_drawings():
        for item in d["items"]:
            if item[0] == "re":
                r = pymupdf.Rect(item[1])
                if 6 <= r.width <= 30 and 6 <= r.height <= 40 and r.x0 >= label.x1 - 1:
                    if r.y0 - 3 <= mid <= r.y1 + 3:
                        boxes.append(r)
            elif item[0] == "l":
                a, b = item[1], item[2]
                top, bottom = min(a.y, b.y), max(a.y, b.y)
                if abs(a.x - b.x) < 1 and 6 <= bottom - top <= 40 and a.x >= label.x1 - 1:
                    if top - 3 <= mid <= bottom + 3:
                        verticals.append((a.x, top, bottom))
    if not boxes and verticals:  # table cells: boxes sit between consecutive vertical lines
        xs: list[tuple[float, float, float]] = []
        for v in sorted(verticals):
            if not xs or v[0] - xs[-1][0] > 2:
                xs.append(v)
        for left, right in zip(xs, xs[1:], strict=False):
            if 6 <= right[0] - left[0] <= 30:
                boxes.append(pymupdf.Rect(left[0], left[1], right[0], left[2]))
    boxes.sort(key=lambda r: r.x0)
    # drop duplicates drawn twice (fill + stroke)
    unique: list[pymupdf.Rect] = []
    for r in boxes:
        if not unique or abs(r.x0 - unique[-1].x0) > 2:
            unique.append(r)
    return unique


def fill_pdf(spec: FormSpec, pdf: Path, font: Path, values: dict[str, str]) -> bytes:
    """Return the filled PDF. Unknown keys and empty values are ignored."""
    doc = pymupdf.open(pdf)
    by_key = {f.key: f for f in spec.fields}
    for key, raw in values.items():
        f = by_key.get(key)
        value = (raw or "").strip()
        if f is None or not value:
            continue
        if f.max_chars:
            value = value[: f.max_chars]
        page = doc[f.page]

        if f.mode == "acroform":
            widget = next((w for w in page.widgets() if w.field_name == f.widget), None)
            if widget is None:
                raise FieldNotFound(f"{f.key}: widget {f.widget!r} not found")
            widget.field_value = value
            widget.update()
            continue

        label = _label_rect(page, f)
        size = f.font_size or FONT_SIZE

        def write(
            x: float, y: float, text: str, page: pymupdf.Page = page, size: float = size
        ) -> None:
            page.insert_text(
                (x, y), text, fontsize=size, fontfile=str(font), fontname="vi", color=INK
            )

        if f.mode == "date_parts":
            parts = value.split("/")
            slashes = sorted(
                (r for r in page.search_for("/") if abs(r.y1 - label.y1) < 4 and r.x0 > label.x1),
                key=lambda r: r.x0,
            )[:2]
            if len(parts) != 3 or len(slashes) < 2:
                raise FieldNotFound(f"{f.key}: expected dd/mm/yyyy and two printed slashes")
            starts = [label.x1 + f.x_offset, slashes[0].x1 + 2, slashes[1].x1 + 2]
            for x, part in zip(starts, parts, strict=True):
                write(x + 4, label.y1 - 2, part)
            continue

        if f.mode == "boxes":
            boxes = _boxes_after(page, label)
            if len(boxes) < len(value):
                raise FieldNotFound(f"{f.key}: {len(boxes)} boxes for {len(value)} characters")
            for ch, box in zip(value, boxes, strict=False):
                write(box.x0 + box.width * 0.3, box.y1 - box.height * 0.28, ch)
            continue

        if f.below_x is not None:
            write(f.below_x + 2, label.y1 + label.height - 2.5, value)
        else:
            write(label.x1 + f.x_offset + 4, label.y1 - 2.5, value)
    out: bytes = doc.tobytes(garbage=3, deflate=True)
    doc.close()
    return out


def render_page_png(pdf: bytes | Path, page: int = 0, dpi: int = 110) -> bytes:
    """PNG of one page, for previews (many browsers cannot show a PDF inline)."""
    doc = pymupdf.open(pdf) if isinstance(pdf, Path) else pymupdf.open(stream=pdf, filetype="pdf")
    try:
        if not 0 <= page < len(doc):
            raise IndexError(page)
        png: bytes = doc[page].get_pixmap(dpi=dpi).tobytes("png")
        return png
    finally:
        doc.close()
