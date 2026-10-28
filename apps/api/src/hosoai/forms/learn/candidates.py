"""Deterministic first pass: where could someone write on this form?

A candidate is printed text followed by something to fill in on the same line: a run of
dots (…… / ......), underscores, drawn character boxes or tick boxes (□). We also record
the geometry the filler needs (where the blank starts, how wide it is), so the model
never has to guess coordinates.
"""

import re
from typing import Literal

import pymupdf
from pydantic import BaseModel

from hosoai.forms.fill import _boxes_after, _search

Blank = Literal["dots", "boxes", "checkbox", "next_line", "none"]
DateHint = Literal["slash", "words"] | None

_MARKER = re.compile(r"[.…_]{3,}|[.…]*…[.…]*")  # dot/ellipsis/underscore runs
_TICK = "□☐"
_GAP = re.compile(r"[ \xa0]{4,}")
_TRIM = " \xa0;,"  # spaces (incl. non-breaking) and separators around a label
_LONE_OPTION = re.compile(r"\s*[^\s□☐:]+(?:[ \xa0][^\s□☐:]+){0,2}\s*[□☐]\s*")  # "nhiều lần □"


class Candidate(BaseModel):
    id: str
    page: int
    text: str  # printed text before the blank, as on the form
    line_text: str  # the whole printed line, for context
    blank: Blank
    blank_x0: float = 0
    blank_x1: float = 0
    label_x0: float = 0
    label_x1: float = 0
    y1: float = 0
    date: DateHint = None
    options: list[str] = []  # checkbox options printed before each □
    boxes: int = 0  # drawn character boxes after the text


class _Char(BaseModel):
    c: str
    x0: float
    x1: float
    y1: float


def _lines(page: pymupdf.Page) -> list[list[_Char]]:
    """Characters grouped into visual lines (spans with the same baseline)."""
    chars: list[_Char] = []
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                for c in span["chars"]:
                    x0, _, x1, y1 = c["bbox"]
                    chars.append(_Char(c=c["c"], x0=x0, x1=x1, y1=y1))
    chars += _drawn_ticks(page, chars)
    chars.sort(key=lambda ch: (round(ch.y1), ch.x0))
    lines: list[list[_Char]] = []
    for ch in chars:
        if lines and abs(lines[-1][-1].y1 - ch.y1) < 5:
            lines[-1].append(ch)
        else:
            lines.append([ch])
    return [sorted(line, key=lambda ch: ch.x0) for line in lines]


def _options(seg: str) -> tuple[str, list[str]]:
    """'Giới tính:  Nam □  Nữ □' -> ('Giới tính:', ['Nam', 'Nữ']).

    Options are the words before each tick. For the first one: the text after the colon,
    or else the last word.
    """
    parts = re.split(r"[□☐]", seg)[:-1]
    first = parts[0]
    if ":" in first:
        head, opt = first.rsplit(":", 1)
        head += ":"
    else:
        head, _, opt = first.rstrip(_TRIM).rpartition(" ")
    options = [o.strip(_TRIM + ":") for o in [opt, *parts[1:]]]
    return head.strip(_TRIM), [re.sub(r"[ \xa0]+", " ", o) for o in options if o]


def _drawn_ticks(page: pymupdf.Page, chars: list[_Char]) -> list[_Char]:
    """Tick boxes drawn as small squares (not typed as □) become a □ character.

    Only isolated squares right after a word count: rows of touching squares are digit
    boxes (see fill._boxes_after).
    """
    squares = [
        d["rect"]
        for d in page.get_drawings()
        if 6 <= d["rect"].width <= 14 and abs(d["rect"].width - d["rect"].height) < 2
    ]
    out = []
    for r in squares:
        if any(
            o is not r and abs(o.y1 - r.y1) < 2 and o.x0 - 4 < r.x1 and r.x0 < o.x1 + 4
            for o in squares
        ):
            continue  # part of a row of boxes
        on_line = [c for c in chars if c.y1 - 14 < r.y1 < c.y1 + 3]
        before = [c for c in on_line if c.x1 <= r.x0 + 1 and r.x0 - c.x1 < 12 and c.c.strip()]
        inside = [c for c in on_line if c.x0 < r.x1 and r.x0 < c.x1 and c.c.strip()]
        if before and not inside:
            out.append(_Char(c="□", x0=r.x0, x1=r.x1, y1=before[-1].y1))
    return out


def _text_pieces(text: str, a: int, b: int) -> list[tuple[str, int, int]]:
    """Printed text between blanks; two labels on one line may be split only by spaces.

    Tick options stay with their question: "Giới tính:    Nam □    Nữ □  Sinh ngày" gives
    "Giới tính: Nam □ Nữ □" and "Sinh ngày".
    """
    spans: list[tuple[int, int]] = []
    start = a
    for gap in _GAP.finditer(text, a, b):
        if gap.start() > start:
            spans.append((start, gap.start()))
        start = gap.end()
    if start < b:
        spans.append((start, b))
    # cut after the last tick of a run, then glue lone "Option □" pieces to the one before
    cut: list[tuple[int, int]] = []
    for s, e in spans:
        ticks = [m.end() for m in re.finditer(r"[□☐]", text[s:e])]
        last = s + ticks[-1] if ticks else e
        if last < e and text[last:e].strip():  # text after the last tick: another label
            rest = last + len(text[last:e]) - len(text[last:e].lstrip())
            cut += [(s, last), (rest, e)]
        else:
            cut.append((s, e))
    out: list[tuple[str, int, int]] = []
    for s, e in cut:
        if out and _LONE_OPTION.fullmatch(text[s:e]):
            out[-1] = ("text", out[-1][1], e)
        else:
            out.append(("text", s, e))
    return out


def findable(page: pymupdf.Page, label: str) -> str | None:
    """The longest start of `label` that search can find on the page.

    Extraction can differ from the printed sequence (a superscript "(1)" in the middle of
    "Kính gửi(1):", odd spaces), so we trim from the end until the text is found.
    """
    variants = [label, label.replace("\xa0", " ")]
    for v in variants:
        t = v
        while len(t) >= 2:
            if _search(page, t):
                return t
            t = t[:-1].rstrip(" \xa0:;,")
    return None


def _is_marker(text: str) -> bool:
    return bool(text.strip()) and all(c in ".…_ " for c in text)


def extract(pdf: pymupdf.Document) -> list[Candidate]:
    out: list[Candidate] = []
    for page_no in range(len(pdf)):
        page: pymupdf.Page = pdf[page_no]
        lines = _lines(page)
        for li, line in enumerate(lines):
            text = "".join(ch.c for ch in line)
            if not text.strip() or _is_marker(text):
                continue
            # split the line into printed segments and blanks
            pieces: list[tuple[str, int, int]] = []  # (kind, start, end) over `line`
            i = 0

            for m in _MARKER.finditer(text):
                if m.start() > i:
                    pieces += _text_pieces(text, i, m.start())
                pieces.append(("blank", m.start(), m.end()))
                i = m.end()
            if i < len(text):
                pieces += _text_pieces(text, i, len(text))

            texts = [p for p in pieces if p[0] == "text"]
            for k, (kind, s, e) in enumerate(pieces):
                if kind != "text":
                    continue
                seg = text[s:e]
                label = seg.strip(_TRIM)
                if not re.search(r"[^\W\d_]", label):  # needs at least one letter
                    continue
                nxt = pieces[k + 1] if k + 1 < len(pieces) else None
                last_char = line[s + len(seg.rstrip(_TRIM)) - 1]
                cand = Candidate(
                    id=f"c{len(out) + 1}",
                    page=page_no,
                    text=label,
                    line_text=text.strip(),
                    blank="none",
                    label_x1=last_char.x1,
                    y1=line[s].y1,
                )
                label_rect = pymupdf.Rect(line[s].x0, line[s].y1 - 12, last_char.x1, line[s].y1)
                drawn = _boxes_after(page, label_rect)
                first_blank_x = line[nxt[1]].x0 if nxt is not None and nxt[0] == "blank" else 1e9
                drawn = [b for b in drawn if b.x1 <= first_blank_x + 1]
                if len(drawn) >= 6:
                    cand.blank, cand.boxes = "boxes", len(drawn)
                elif any(t in seg for t in _TICK):
                    cand.blank = "checkbox"
                    cand.text, cand.options = _options(seg)
                elif nxt is not None and nxt[0] == "blank":
                    cand.blank = "dots"
                    cand.blank_x0 = line[nxt[1]].x0
                    cand.blank_x1 = line[nxt[2] - 1].x1
                else:
                    if li + 1 < len(lines) and _is_marker("".join(c.c for c in lines[li + 1])):
                        nl = lines[li + 1]
                        cand.blank = "next_line"
                        cand.blank_x0, cand.blank_x1 = nl[0].x0, nl[-1].x1
                # date hints from what follows on the same line
                following = [text[a:b].strip(_TRIM).lower() for (_, a, b) in texts if a > s][:2]
                if following[:2] == ["tháng", "năm"]:
                    cand.date = "words"
                elif nxt is not None and nxt[0] == "blank":
                    rest = text[nxt[1] :]
                    if re.match(r"[.…_ ]*/[.…_ ]*/", rest):
                        cand.date = "slash"
                if cand.blank != "none" or cand.date:
                    found = findable(page, cand.text)
                    if found is None:
                        continue  # can't be located again when filling; not usable
                    hits = [r for r in _search(page, found) if abs(r.y1 - cand.y1) < 4]
                    hit = min(hits, key=lambda r: abs(r.x0 - line[s].x0), default=None)
                    if hit is None:
                        continue
                    cand.text = found
                    cand.label_x0, cand.label_x1 = hit.x0, hit.x1  # where search will find it
                    out.append(cand)
    return out
