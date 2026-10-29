"""Learn a scanned (image-only) form: code finds the blanks, the vision model reads labels.

A scanned form has no text layer, so code cannot search for labels. Division of labour,
the same as for text forms (agent.py):
- Code finds every writing line on the page image (dotted line or underline with empty
  space above it) and owns all geometry: where to write and how much fits.
- The vision model only READS: the label printed left of (or above) each line, from a
  small crop of the image. It is never asked for coordinates: in our tests the local 7B
  vision model drifted by several lines when asked to place boxes itself.
- The chat model decides which lines the applicant fills in, names them and links them to
  the profile, with the same prompt and the same label rules as text forms (a clear label
  decides the profile value; a label about another person never takes the applicant's data).
The result is a draft spec with mode="region" fields, waiting for human review.
"""

import base64
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pymupdf
from pydantic import BaseModel

from hosoai.forms.learn.agent import (
    MAX_ROUNDS,
    NUMBERED,
    OTHER_PERSON,
    PROFILE_KEYS,
    SYSTEM_PROMPT,
    LearnReport,
    _parse,
    label_hint,
    name_transform,
)
from hosoai.forms.models import FormField, FormSpec
from hosoai.llm import ChatMessage, LLMClient
from hosoai.sources.models import Source

SCALE = 2.0  # pixels per PDF point when looking for lines
INK = 160  # grey level below which a pixel is ink
MAX_GAP = 7  # pt: largest gap between two dots of the same dotted line
MIN_WRITE = 14  # pt: shortest empty stretch that counts as a place to write
ABOVE = 9  # pt: the space above the line that must be empty to write in
BELOW = 5  # pt: the space under the line that must be (nearly) empty
LINE_HEIGHT = 14  # pt: height of the box we write in, above the line
DATE_PART = 90  # pt: a date part ("…/", "… tháng") is at most this wide
DATE_GAP = 32  # pt: and at most this far from the next part ("/", " tháng ", " năm ")

READ_PROMPT = """This is a crop of a scanned official Vietnamese form. Copy the printed
text exactly as printed, in Vietnamese, with its number if it has one (e.g. "3. Giới tính:").
Reply with the text only. If there is no text, reply with an empty line."""


class Line(BaseModel):
    """A place to write: the empty space above a dotted line or underline."""

    id: str
    page: int
    rect: tuple[float, float, float, float]  # PDF points: where the value goes
    parts: list[tuple[float, float, float, float]] = []  # a date: one box per part
    label: str = ""  # read by the vision model


def is_scanned(doc: pymupdf.Document) -> bool:
    """Image-only pages: almost no text layer, and an image on every page."""
    if len(doc) == 0:
        return False
    pages = [doc[i] for i in range(len(doc))]
    text = sum(len(p.get_text().strip()) for p in pages)
    return text < 30 * len(doc) and all(len(p.get_images()) > 0 for p in pages)


def find_lines(page: pymupdf.Page) -> list[pymupdf.Rect]:
    """Writing lines on a page image, top to bottom, as boxes (PDF points) to write in.

    A writing line is a thin horizontal run of ink (dots with small gaps, or a solid
    underline) with empty space above it and below it. Printed text is tall, so these
    tests cut the run wherever a label sits on it ("Cơ quan cấp: …… có giá trị đến: ……"
    gives two lines; a date "…/…/…" gives three).
    """
    pix = page.get_pixmap(matrix=pymupdf.Matrix(SCALE, SCALE), colorspace=pymupdf.csGRAY)
    w, h, data = pix.width, pix.height, pix.samples
    gap, above, below = int(MAX_GAP * SCALE), int(ABOVE * SCALE), int(BELOW * SCALE)
    min_len = int(MIN_WRITE * SCALE)
    ink_rows = [[data[y * w + x] < INK for x in range(w)] for y in range(h)]

    def empty_below(x0: int, x1: int, y: int) -> bool:
        # under a writing line there is space, not the body of printed letters
        rows = range(y + 3, min(h, y + below))
        dark = sum(1 for yy in rows for x in range(x0, x1) if ink_rows[yy][x])
        return dark <= 0.02 * max(1, (x1 - x0) * len(rows))

    # above[x]: ink pixels in rows [y - above, y - 3) of column x, kept as a sliding window
    above_ink = [0] * w
    window = above - 3  # rows counted in above_ink
    found: list[tuple[int, int, int]] = []  # x0, x1, y in pixels
    for y in range(h):
        if y - 4 >= 0:  # row y-4 enters the window
            for x, v in enumerate(ink_rows[y - 4]):
                above_ink[x] += v
        if y - above - 1 >= 0:  # row y-above-1 leaves it
            for x, v in enumerate(ink_rows[y - above - 1]):
                above_ink[x] -= v
        if y < above:
            continue
        xs = [x for x, v in enumerate(ink_rows[y]) if v]
        if len(xs) < 8:
            continue
        # runs of ink where consecutive ink pixels are at most `gap` apart
        runs: list[tuple[int, int]] = []
        start = prev = xs[0]
        for x in xs[1:]:
            if x - prev > gap:
                runs.append((start, prev))
                start = x
            prev = x
        runs.append((start, prev))
        for a, b in runs:
            if b - a < min_len:
                continue
            # every stretch of the run with nothing printed above it
            x = a
            while x <= b:
                if above_ink[x]:
                    x += 1
                    continue
                x0 = x
                while x <= b and not above_ink[x]:
                    x += 1
                # a cell (digit box, table) has a full vertical border at an end
                walls = [c for c in (x0 - 1, x) if 0 <= c < w and above_ink[c] >= window - 2]
                if x - x0 >= min_len and not walls and empty_below(x0, x, y):
                    found.append((x0, x - 1, y))
    # one line is a few pixels thick: keep the lowest row of each group
    found.sort(key=lambda t: (t[2], t[0]))
    lines: list[tuple[int, int, int]] = []
    for x0, x1, y in found:
        same = [ln for ln in lines if 0 <= y - ln[2] <= 4 and x0 <= ln[1] and ln[0] <= x1]
        for ln in same:
            lines.remove(ln)
            x0, x1 = min(x0, ln[0]), max(x1, ln[1])
        lines.append((x0, x1, y))
    out = []
    for x0, x1, y in sorted(lines, key=lambda t: (round(t[2] / (4 * SCALE)), t[0])):
        bottom = y / SCALE
        out.append(pymupdf.Rect(x0 / SCALE + 1, bottom - LINE_HEIGHT, x1 / SCALE, bottom - 1))
    return out


def _tuple(r: pymupdf.Rect) -> tuple[float, float, float, float]:
    return (r.x0, r.y0, r.x1, r.y1)


def group_dates(boxes: list[pymupdf.Rect]) -> list[list[pymupdf.Rect]]:
    """Short lines on one row, close together, form one date: [day, month, year]."""
    groups: list[list[pymupdf.Rect]] = []
    for b in boxes:
        last = groups[-1][-1] if groups else None
        if (
            last is not None
            and len(groups[-1]) < 3
            and abs(b.y1 - last.y1) < 3
            and 0 <= b.x0 - last.x1 <= DATE_GAP
            and b.width <= DATE_PART
            and last.width <= DATE_PART
        ):
            groups[-1].append(b)
        else:
            groups.append([b])
    # two parts are a date only with a third ("…/…" alone is not)
    out: list[list[pymupdf.Rect]] = []
    for g in groups:
        out += [g] if len(g) in (1, 3) else [[b] for b in g]
    return out


def label_crop(page: pymupdf.Page, box: pymupdf.Rect, start: float | None = None) -> bytes | None:
    """The label of a line: left of it on the same row, or the row above if that is empty.

    start: where the previous line on the same row ends, so the crop holds this label only
    ("5. Số điện thoại: ……… 6. Email: ………" gives "6. Email:" for the second line). The crop
    is one text row high: the label sits on the line, like the dots.
    None: nothing printed between this line and the previous one on its row, so this line
    continues the previous one (e.g. the second half of a date).
    """
    bottom = box.y1 + 1  # the dotted line
    x0 = page.rect.x0 + 20 if start is None else start + 1
    left = pymupdf.Rect(x0, bottom - 13, box.x0, bottom + 3.5)
    if left.width > 15 and _has_ink(page, left):
        clip = left
    elif start is not None:
        return None
    else:
        clip = pymupdf.Rect(page.rect.x0 + 20, bottom - 28, page.rect.x1 - 20, bottom - 11)
    png: bytes = page.get_pixmap(dpi=200, clip=clip).tobytes("png")
    return png


def _has_ink(page: pymupdf.Page, rect: pymupdf.Rect) -> bool:
    pix = page.get_pixmap(matrix=pymupdf.Matrix(SCALE, SCALE), clip=rect, colorspace=pymupdf.csGRAY)
    return sum(1 for b in pix.samples if b < INK) > 20


def read_lines(doc: pymupdf.Document, llm: LLMClient, log: Any) -> list[Line]:
    lines: list[Line] = []
    for page in (doc[i] for i in range(len(doc))):
        groups = group_dates(find_lines(page))
        for n, group in enumerate(groups):
            box = group[0]
            before = [g[-1].x1 for g in groups[:n] if abs(g[-1].y1 - box.y1) < 3]
            crop = label_crop(page, box, max(before, default=None))
            if crop is None and lines and lines[-1].page == page.number:
                prev = lines[-1]  # continuation: one field, one box per part
                parts = prev.parts or [prev.rect]
                lines[-1] = prev.model_copy(
                    update={
                        "rect": _tuple(pymupdf.Rect(prev.rect) | group[-1]),
                        "parts": parts + [_tuple(b) for b in group],
                    }
                )
                continue
            if crop is None:
                continue
            img = base64.b64encode(crop).decode()
            text = llm.chat(
                [ChatMessage(role="user", content=READ_PROMPT, images=[img])], vision=True
            )
            label = " ".join(text.strip().strip('"').split())[:120]
            lines.append(
                Line(
                    id=f"L{len(lines) + 1}",
                    page=page.number,
                    rect=_tuple(box | group[-1]),
                    parts=[_tuple(b) for b in group] if len(group) > 1 else [],
                    label=label,
                )
            )
            log(f'   L{len(lines)} page {page.number + 1}: "{label}"')
    return lines


def line_facts(lines: list[Line]) -> dict[str, tuple[str | None, bool]]:
    """Per line: the profile key its label asks for ("" = none), and "about another person".

    Same rules as text forms: unnumbered lines belong to the numbered item above them.
    """
    out: dict[str, tuple[str | None, bool]] = {}
    owner_other = False
    for ln in lines:
        own_other = bool(OTHER_PERSON.search(ln.label))
        if NUMBERED.search(ln.label):
            owner_other = own_other
        other = own_other or owner_other
        out[ln.id] = (None if other else label_hint(ln.label), other)
    return out


def _describe(lines: list[Line], known: dict[str, tuple[str | None, bool]]) -> str:
    out = []
    for ln in lines:
        hint, other = known[ln.id]
        extra = (
            "other person"
            if other
            else "profile=null"
            if hint == ""
            else f"profile={hint}"
            if hint
            else ""
        )
        kind = "date=3 parts" if ln.parts else "line"
        out.append(f'{ln.id} [{kind}{", " + extra if extra else ""}] "{ln.label}"')
    return "\n".join(out)


def decide(
    lines: list[Line], llm: LLMClient, title: str, log: Any
) -> tuple[list[FormField], list[str], dict[str, str], int]:
    """The chat model picks and names the applicant's fields; code checks every answer."""
    by_id = {ln.id: ln for ln in lines}
    known = line_facts(lines)
    messages = [
        ChatMessage(role="system", content=SYSTEM_PROMPT % ", ".join(PROFILE_KEYS)),
        ChatMessage(
            role="user",
            content=f"Form: {title}\n\nCandidates (labels read from a scanned image):\n"
            f"{_describe(lines, known)}",
        ),
    ]
    best: dict[str, FormField] = {}
    errors: dict[str, str] = {}
    skipped: list[str] = []
    rounds = 0
    for rounds in range(1, MAX_ROUNDS + 1):
        reply = llm.chat(messages)
        messages.append(ChatMessage(role="assistant", content=reply[:4000]))
        data = _parse(reply)
        if data is None or not isinstance(data.get("fields"), list):
            messages.append(ChatMessage(role="user", content="Reply with the JSON object only."))
            continue
        skipped = [s for s in data.get("skip", []) if isinstance(s, str) and s in by_id]
        errors = {}
        accepted: dict[str, FormField] = {}
        keys: set[str] = set()
        for item in data["fields"]:
            if not isinstance(item, dict):
                continue
            lid = item.get("c")
            if not isinstance(lid, str) or lid not in by_id:
                errors[str(lid)] = "unknown candidate id"
                continue
            key = item.get("key")
            if not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,40}", key):
                errors[lid] = "key must be snake_case English"
                continue
            if key in keys:
                errors[lid] = f"key {key!r} is already used by another field; pick a new one"
                continue
            hint, other = known[lid]
            profile = item.get("profile")
            if isinstance(profile, str) and profile.strip().lower() in ("", "null", "none"):
                profile = None
            if profile not in (None, *PROFILE_KEYS):
                errors[lid] = f"profile must be one of {PROFILE_KEYS} or null"
                continue
            if other and profile is not None:
                errors[lid] = "this field is about another person: profile must be null"
                continue
            if hint:  # a clear label decides the profile value
                profile = hint
            elif hint == "":
                profile = None
            ln = by_id[lid]
            accepted[lid] = FormField(
                key=key,
                label=ln.label or lid,
                hint=item["hint"] if isinstance(item.get("hint"), str) else None,
                profile_key=profile,
                page=ln.page,
                mode="region",
                rect=ln.rect,
                parts=ln.parts,
                uppercase=item.get("upper") is True,
                transform=name_transform(ln.label) if profile == "full_name" else None,
            )
            keys.add(key)
        for lid in skipped:
            hint, other = known[lid]
            if hint and not other and lid not in errors:
                errors[lid] = f"the applicant fills this in: add it with profile {hint!r}"
        missing = [ln.id for ln in lines if ln.id not in accepted and ln.id not in skipped]
        missing = [m for m in missing if m not in errors]
        log(f"Round {rounds}: {len(accepted)} fields accepted, {len(errors)} errors.")
        if len(accepted) >= len(best):
            best = accepted
        if not errors and not missing:
            break
        feedback = [
            f'{lid} "{by_id[lid].label if lid in by_id else "?"}": {e}' for lid, e in errors.items()
        ]
        feedback += [f"{m}: not decided; put it in fields or skip" for m in missing]
        messages.append(
            ChatMessage(
                role="user",
                content="Checks:\n" + "\n".join(feedback) + "\nReply with the full corrected JSON.",
            )
        )
    order = {ln.id: i for i, ln in enumerate(lines)}
    fields = [best[lid] for lid in sorted(best, key=order.__getitem__)]
    return fields, skipped, errors, rounds


def learn_scanned(
    *,
    form_id: str,
    code: str,
    title: str,
    procedure_slugs: list[str],
    pdf: Path,
    original_file: str | None,
    source: Source,
    llm: LLMClient,
    model_name: str,
    log: Any = print,
) -> tuple[FormSpec, LearnReport]:
    doc = pymupdf.open(pdf)
    lines = read_lines(doc, llm, log)
    log(f"Scanned form: {len(lines)} writing lines on {len(doc)} page(s).")
    fields, skipped, rejected, rounds = decide(lines, llm, title, log) if lines else ([], [], {}, 0)
    spec = FormSpec(
        id=form_id,
        code=code,
        title=title,
        procedure_slugs=procedure_slugs,
        file=pdf.name,
        original_file=original_file,
        source=source,
        fields=fields,
        notes=[
            "Tờ khai này là bản scan: vị trí các dòng cần điền do máy tự tìm trên ảnh, nhãn của "
            "mỗi dòng do trợ lý AI đọc từ ảnh, chưa có người duyệt. Hãy kiểm tra kỹ bản xem trước.",
        ],
        preview_pages=len(doc),
        status="draft",
        learned={
            "model": model_name,
            "method": "scanned: lines found by code, labels read by the vision model",
            "at": datetime.now(UTC).isoformat(timespec="seconds"),
            "rounds": rounds,
            "candidates": len(lines),
            "rejected": rejected,
        },
    )
    report = LearnReport(
        form_id=form_id,
        model=model_name,
        rounds=rounds,
        candidates=len(lines),
        accepted=[f.key for f in fields],
        skipped=skipped,
        rejected=rejected,
    )
    return spec, report
