"""The form-learning agent: propose fields, let code check them, repair, repeat.

Division of labour:
- Code finds every place someone could write (candidates.py) and owns all geometry.
- The model decides which candidates the *applicant* fills in, names them, maps them to
  the profile and writes a short English gloss. It can only refer to candidate ids.
- Code checks every proposal on the real PDF (label found, blank exists, value fits and
  does not cover printed text) and sends precise errors back to the model.
The result is saved as a *draft* spec: usable, clearly marked, waiting for human review.
"""

import json
import math
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, get_args

import pymupdf
from pydantic import BaseModel

from hosoai.forms.fill import MIN_FONT_SIZE, FieldNotFound, _search, fill_pdf
from hosoai.forms.learn.candidates import Candidate, extract
from hosoai.forms.models import FormField, FormSpec, ProfileKey
from hosoai.llm import ChatMessage, LLMClient
from hosoai.sources.models import Source

MAX_ROUNDS = 4
# Values shrink to fit their blank (see fill.py); max_chars is only the hard limit at the
# smallest font size, so normal values are never cut.
CHAR_WIDTH = MIN_FONT_SIZE * 0.64  # generous average width of a character (points)
UPPER_WIDTH = MIN_FONT_SIZE * 0.8  # capitals are wider
PAD = 4  # the filler starts writing 4 pt after the start of the blank
PROFILE_KEYS = list(get_args(ProfileKey))
# Labels about someone other than the applicant: never filled from the applicant's profile.
OTHER_PERSON = re.compile(
    r"\b(cha|mẹ|bố|vợ|chồng|con|chủ hộ|thân nhân|bảo lãnh|giám hộ|người đại diện|"
    r"người được|anh|chị|em|cơ quan, tổ chức|tổ chức bảo lãnh|đdhp|của người)\b",
    re.IGNORECASE,
)
# A numbered item ("12.", "3-") starts a new question; unnumbered blanks after it belong to
# it ("17. Họ tên của cha … Quốc tịch … Số CCCD" are all about the father). A "- " bullet
# also starts a new question.
NUMBERED = re.compile(r"(?:^|\s)\d{1,2}\s?[.\-]\s?\S|^\s*-\s")
# The printed label alone says which profile value answers it. Checked in order, first wins.
# Only unambiguous wording: anything else is left to the model.
PROFILE_HINTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(p, re.IGNORECASE), key)
    for p, key in [
        (r"điện thoại", "phone"),
        (r"\bemail\b|thư điện tử", "email"),
        (r"gọi khác", ""),  # alias names: not the profile name
        (r"^(ngày|tháng|năm|giờ|phút)$", ""),  # date pieces, the signing date
        (r"^(họ,? chữ đệm và tên|họ và tên|họ tên|họ|chữ đệm và tên)\b", "full_name"),
        (r"ngày,? tháng,? năm sinh|sinh ngày", "date_of_birth"),
        (r"giới tính", "sex"),
        (r"\bsố\b.*(định danh|cmnd|cccd|đdcn)", "id_number"),
        (r"\bsố hộ chiếu|hộ chiếu.*\bsố\b", "passport_number"),
        (r"(nơi|địa chỉ) thường trú", "permanent_address"),
        (r"(nơi|chỗ) (ở|cư trú) hiện (tại|nay)|địa chỉ tạm trú tại việt nam", "current_address"),
        (r"nghề nghiệp", "occupation"),
        (r"quốc tịch gốc", ""),
        (r"quốc tịch", "nationality"),
        (r"dân tộc", "ethnicity"),
        (r"tôn giáo", "religion"),
        (r"quê quán", "hometown"),
    ]
]

SYSTEM_PROMPT = """You prepare an official Vietnamese form so an app can pre-fill it.
You get the places on the form where something can be written ("candidates"), each with an
id, its printed label and the kind of blank. Decide which ones the APPLICANT fills in.

Reply with ONE JSON object, nothing else:
{"fields": [{"c": "<candidate id>", "key": "<snake_case_english_name>",
             "profile": "<profile key or null>",
             "upper": <true if the form asks for capital letters>,
             "hint": "<2-6 word English explanation>"}],
 "skip": ["<candidate id>", ...]}

Rules:
- Use only candidate ids from the list. Every candidate goes in "fields" or "skip".
- Keep in "fields" EVERY blank the applicant writes, also when the profile can't fill it
  (dates of entry or loss, border gate, purpose, reasons, document type and issuer, the
  sponsor's details): the user types those in. Most candidates are fields.
- Skip: parts filled by officials, the place/date of signing ("Làm tại … ngày … tháng …
  năm"), signatures, and pieces like "tháng" / "năm" / "giờ" that belong to the field before
  them (a candidate marked date=words already covers its tháng and năm).
- "profile": the applicant's saved data that answers this field, one of: %s.
  A candidate marked profile=<key> asks for exactly that: use that key. Map every other
  field that asks for the applicant's own identity, birth, address, job or contact
  details. Use null for things the profile can't know (dates of loss, reasons, the office
  addressed) and for ANY field about another person: head of household (chủ hộ), father
  (cha/bố), mother (mẹ), spouse (vợ/chồng), child (con), relative (thân nhân), sponsor
  (người bảo lãnh), guardian, representative. Candidates marked "other person" are such.
- Each field needs its own key: for another person's details name the person, e.g.
  "head_of_household_name", "father_nationality".
- Check each candidate id against ITS OWN label before answering; do not shift by one.
- Set "upper" true only if the form or its notes ask for capital letters (chữ in hoa).
"""


class LearnReport(BaseModel):
    form_id: str
    model: str
    rounds: int
    candidates: int
    accepted: list[str]  # field keys
    skipped: list[str]  # candidate ids the model chose to skip
    rejected: dict[str, str]  # candidate id -> last error
    vision_checks: dict[str, str] = {}  # field key -> "ok" | "doubt: ..."


class Facts(BaseModel):
    """What code can tell from the printed form alone, per candidate."""

    hint: str | None = None  # profile key the label asks for
    other: bool = False  # about someone other than the applicant
    no_profile: bool = False  # the label rules out the profile ("Quốc tịch gốc", alias names)


def _strip_number(text: str) -> str:
    return re.sub(r"^\s*[\d\s.\-]*", "", text.replace("\xa0", " ")).strip(" :;,")


def label_hint(text: str) -> str | None:
    """The profile key the label asks for, "" if it rules the profile out, None if unclear."""
    t = _strip_number(text)
    for pattern, key in PROFILE_HINTS:
        if pattern.search(t):
            return key
    return None


def name_transform(text: str) -> str | None:
    """A blank that asks only for part of the name."""
    t = _strip_number(text).lower()
    if t == "họ":
        return "family_name"
    if t == "chữ đệm và tên":
        return "given_names"
    return None


def facts(cands: list[Candidate]) -> dict[str, Facts]:
    out: dict[str, Facts] = {}
    owner_other = False
    for c in cands:
        own_other = bool(OTHER_PERSON.search(c.text))
        if NUMBERED.search(c.text):
            owner_other = own_other  # a new numbered item
        other = own_other or owner_other
        hint = None if other else label_hint(c.text)
        out[c.id] = Facts(hint=hint or None, other=other, no_profile=hint == "")
    return out


def _candidate_lines(cands: list[Candidate], known: dict[str, Facts] | None = None) -> str:
    out = []
    for c in cands:
        extra = []
        f = (known or {}).get(c.id)
        if f and f.other:
            extra.append("other person")
        elif f and f.no_profile:
            extra.append("profile=null")
        elif f and f.hint:
            extra.append(f"profile={f.hint}")
        if c.date:
            extra.append(f"date={c.date}")
        if c.options:
            extra.append("options=" + "/".join(c.options))
        if c.boxes:
            extra.append(f"{c.boxes} digit boxes")
        context = f'   (line: "{c.line_text[:90]}")' if len(c.text) < 12 else ""
        out.append(
            f'{c.id} [{c.blank}{", " + ", ".join(extra) if extra else ""}] "{c.text}"{context}'
        )
    return "\n".join(out)


def _notes(doc: pymupdf.Document) -> str:
    text = "\n".join(doc[i].get_text() for i in range(len(doc)))
    m = re.search(r"(Ghi chú|Chú thích|Lưu ý)\s*:?(.*)", text, re.DOTALL)
    return m.group(2).strip()[:900] if m else ""


def _parse(reply: str) -> dict[str, Any] | None:
    found = re.search(r"\{.*\}", reply, re.DOTALL)
    if not found:
        return None
    try:
        data = json.loads(found.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _occurrence(page: pymupdf.Page, c: Candidate) -> int | None:
    """Which match of the label text on the page is this candidate."""
    hits = _search(page, c.text)
    for i, r in enumerate(hits):
        if abs(r.y1 - c.y1) < 4 and abs(r.x0 - c.label_x0) < 2:
            return i
    return None


def _date_pieces(cands: list[Candidate]) -> dict[str, str]:
    """Candidates that are the 'tháng'/'năm' parts of a date written with words."""
    consumed: dict[str, str] = {}
    for i, c in enumerate(cands):
        if c.date == "words":
            for nxt in cands[i + 1 : i + 3]:
                if nxt.page == c.page and abs(nxt.y1 - c.y1) < 4:
                    consumed[nxt.id] = c.id
    return consumed


def consistency(item: dict[str, Any], c: Candidate, f: Facts | None = None) -> str | None:
    """Cheap checks that a proposal agrees with itself and with the candidate."""
    profile, key = item.get("profile"), item.get("key")
    other = (f is not None and f.other) or OTHER_PERSON.search(c.text)
    if other and profile is not None:
        return "this field is about another person, not the applicant; profile must be null"
    if f is not None and f.no_profile and profile is not None:
        return "the profile does not hold this value; profile must be null"
    if profile == "date_of_birth" and "sinh" not in c.text.lower():
        return "only a label about birth (sinh) takes the date of birth; profile must be null"
    if key in PROFILE_KEYS and profile != key:
        return f"key {key!r} is a profile field; set profile to {key!r} or rename the key"
    if c.blank == "checkbox" and set(c.options) <= {"Nam", "Nữ"} and profile != "sex":
        return "options Nam/Nữ are the applicant's sex; set profile to 'sex'"
    return None


def _sample(f: FormField, c: Candidate) -> str:
    if f.mode == "boxes":
        return "012345678901"[: c.boxes]
    if f.mode == "date_parts":
        return "20/05/1990"
    if f.mode == "choice":
        return c.options[0]
    return "Nguyễn Văn Thử Mẫu Ví Dụ"


def build_field(item: dict[str, Any], c: Candidate, page: pymupdf.Page) -> FormField:
    """Turn a model proposal into a FormField; geometry comes only from the candidate."""
    occ = _occurrence(page, c)
    if occ is None:
        raise ValueError("label could not be located on the page")
    kw: dict[str, Any] = {
        "key": item["key"],
        "label": c.text,
        "hint": (item.get("hint") or None),
        "profile_key": item.get("profile") or None,
        "transform": item.get("transform") or None,
        "uppercase": bool(item.get("upper")),
        "page": c.page,
        "occurrence": occ,
    }
    width = UPPER_WIDTH if kw["uppercase"] else CHAR_WIDTH
    if c.blank == "boxes":
        kw.update(mode="boxes", max_chars=c.boxes)
    elif c.blank == "checkbox":
        kw.update(mode="choice", choices={o: o for o in c.options})
    elif c.date:
        kw.update(
            mode="date_parts",
            separators=["tháng", "năm"] if c.date == "words" else ["/", "/"],
            x_offset=max(0.0, c.blank_x0 - c.label_x1 - 4),
        )
    elif c.blank == "next_line":
        room = c.blank_x1 - c.blank_x0 - PAD
        kw.update(below_x=c.blank_x0, fit_width=room, max_chars=math.floor(room / width))
    else:
        kw.update(
            x_offset=max(0.0, c.blank_x0 - c.label_x1 - 4),
            fit_width=c.blank_x1 - c.blank_x0 - PAD,
            max_chars=max(1, math.floor((c.blank_x1 - c.blank_x0 - PAD) / width)),
        )
    return FormField.model_validate(kw)


def _chars(page: pymupdf.Page) -> list[tuple[str, pymupdf.Rect]]:
    out = []
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                for c in span["chars"]:
                    out.append((c["c"], pymupdf.Rect(c["bbox"])))
    return out


def _overlaps_print(filled: bytes, blank: pymupdf.Document, page_no: int) -> bool:
    """True if the filled value covers printed characters other than dots/underscores."""
    before = _chars(blank[page_no])
    seen = {(c, round(r.x0), round(r.y1)) for c, r in before}
    after = _chars(pymupdf.open(stream=filled, filetype="pdf")[page_no])
    added = [r for c, r in after if (c, round(r.x0), round(r.y1)) not in seen and c.strip()]
    printed = [r for c, r in before if c.strip() and c not in ".…_/:"]
    for r in added:
        inner = pymupdf.Rect(r.x0 + 0.8, r.y0 + 2.5, r.x1 - 0.8, r.y1 - 2.5)
        if any(inner.intersects(p) for p in printed):
            return True
    return False


def check_field(
    f: FormField, c: Candidate, spec: FormSpec, pdf: Path, font: Path, blank: pymupdf.Document
) -> str | None:
    """None if the field can be filled cleanly, else a short error for the model."""
    one = spec.model_copy(update={"fields": [f]})
    try:
        filled = fill_pdf(one, pdf, font, {f.key: _sample(f, c)})
    except FieldNotFound as e:
        return f"could not place a value: {e}"
    if f.mode in ("after_label", "date_parts") and _overlaps_print(filled, blank, f.page):
        return "a value written there would cover printed text"
    return None


def learn(
    *,
    form_id: str,
    code: str,
    title: str,
    procedure_slugs: list[str],
    pdf: Path,
    original_file: str | None,
    source: Source,
    font: Path,
    llm: LLMClient,
    model_name: str,
    log: Any = print,
) -> tuple[FormSpec, LearnReport]:
    doc = pymupdf.open(pdf)
    cands = extract(doc)
    by_id = {c.id: c for c in cands}
    known = facts(cands)
    consumed = _date_pieces(cands)
    log(f"Found {len(cands)} places to write on {len(doc)} page(s).")

    base = FormSpec(
        id=form_id,
        code=code,
        title=title,
        procedure_slugs=procedure_slugs,
        file=pdf.name,
        original_file=original_file,
        source=source,
        fields=[],
        preview_pages=len(doc),
        status="draft",
    )
    messages = [
        ChatMessage(role="system", content=SYSTEM_PROMPT % ", ".join(PROFILE_KEYS)),
        ChatMessage(
            role="user",
            content=f"Form: {title}\n\nCandidates:\n{_candidate_lines(cands, known)}\n\n"
            f"Notes printed on the form:\n{_notes(doc)}",
        ),
    ]
    accepted: dict[str, FormField] = {}
    best: dict[str, FormField] = {}  # the round with the most fields that passed the checks
    rejected: dict[str, str] = {}
    skipped: list[str] = []
    rounds = 0
    for rounds in range(1, MAX_ROUNDS + 1):
        reply = llm.chat(messages)
        messages.append(ChatMessage(role="assistant", content=reply[:4000]))
        data = _parse(reply)
        if data is None or not isinstance(data.get("fields"), list):
            messages.append(ChatMessage(role="user", content="Reply with the JSON object only."))
            log(f"Round {rounds}: reply was not valid JSON, asking again.")
            continue
        skipped = [s for s in data.get("skip", []) if isinstance(s, str) and s in by_id]
        errors: dict[str, str] = {}
        keys_seen: set[str] = set()
        accepted = {}
        for item in data["fields"]:
            if not isinstance(item, dict):
                continue
            cid = item.get("c")
            if not isinstance(cid, str) or cid not in by_id:
                errors[str(cid)] = "unknown candidate id"
                continue
            if cid in consumed:
                errors[cid] = f"part of the date field {consumed[cid]}; skip it"
                continue
            key = item.get("key")
            if not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,40}", key):
                errors[cid] = "key must be snake_case English"
                continue
            if key in keys_seen:
                errors[cid] = f"key {key!r} is already used by another field; pick a new one"
                continue
            if item.get("profile") not in (None, *PROFILE_KEYS):
                errors[cid] = f"profile must be one of {PROFILE_KEYS} or null"
                continue
            # the model sometimes writes "null" as text
            if isinstance(item.get("profile"), str) and item["profile"].strip().lower() in (
                "",
                "null",
                "none",
            ):
                item["profile"] = None
            c = by_id[cid]
            # a clear label decides the profile value itself (a wrong key still shows a
            # shifted answer: see consistency)
            if known[cid].hint:
                item["profile"] = known[cid].hint
            # a split name is read from the label, never from the model
            item["transform"] = (
                name_transform(c.text) if item.get("profile") == "full_name" else None
            )
            hint = consistency(item, c, known[cid])
            if hint:
                errors[cid] = hint
                continue
            try:
                f = build_field(item, c, doc[c.page])
            except (ValueError, KeyError) as e:
                errors[cid] = str(e)
                continue
            problem = check_field(f, c, base, pdf, font, doc)
            if problem:
                errors[cid] = problem
                continue
            keys_seen.add(key)
            accepted[cid] = f
        for cid in skipped:
            c, k = by_id[cid], known[cid]
            if cid in errors or cid in consumed:
                continue
            if c.blank == "checkbox" and set(c.options) <= {"Nam", "Nữ"} and not k.other:
                errors[cid] = "Nam/Nữ is the applicant's sex; fill it with profile 'sex'"
            elif k.hint:
                errors[cid] = f"the applicant fills this in: add it with profile {k.hint!r}"
        missing = [
            c.id
            for c in cands
            if c.id not in accepted
            and c.id not in skipped
            and c.id not in errors
            and c.id not in consumed
        ]
        log(
            f"Round {rounds}: {len(accepted)} fields pass the checks, {len(errors)} errors, "
            f"{len(missing)} candidates not decided."
        )
        for cid, err in errors.items():
            log(f'   {cid} "{by_id[cid].text if cid in by_id else "?"}": {err}')
        rejected = errors
        if len(accepted) >= len(best):
            best = dict(accepted)
        if not errors and not missing:
            break

        def said(cid: str) -> str:
            return f'{cid} "{by_id[cid].text}"' if cid in by_id else cid

        feedback = [f"{said(cid)}: {err}" for cid, err in errors.items()]
        feedback += [f"{said(cid)}: not decided; put it in fields or skip" for cid in missing]
        messages.append(
            ChatMessage(
                role="user",
                content="Checks on the real form:\n"
                + "\n".join(feedback)
                + "\nReply with the full corrected JSON (fields and skip).",
            )
        )

    order = {c.id: i for i, c in enumerate(cands)}
    fields = [best[cid] for cid in sorted(best, key=order.__getitem__)]
    report = LearnReport(
        form_id=form_id,
        model=model_name,
        rounds=rounds,
        candidates=len(cands),
        accepted=[f.key for f in fields],
        skipped=skipped,
        rejected=rejected,
    )
    spec = base.model_copy(
        update={
            "fields": fields,
            "notes": [
                "Tờ khai này do trợ lý AI tự đọc từ tệp chính thức; các ô đã được kiểm tra tự "
                "động trên tệp gốc nhưng chưa có người duyệt. Hãy kiểm tra kỹ bản xem trước.",
            ],
            "learned": {
                "model": model_name,
                "at": datetime.now(UTC).isoformat(timespec="seconds"),
                "rounds": rounds,
                "candidates": len(cands),
                "rejected": rejected,
            },
        }
    )
    return spec, report
