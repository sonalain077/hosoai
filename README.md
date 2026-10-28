# Hồ Sơ AI

**Describe a Vietnamese administrative procedure in your own words. Get the exact papers you need, each one linked to the official rule, and the official form filled in from your profile.**

Built for the [Codex Hackathon](https://codexhackathon.sea.com/). Product spec: [`ho so ai.pdf`](ho%20so%20ai.pdf).

---

## Why

Paperwork in Vietnam (residence registration, ID cards, passports, visas, business registration) starts with three questions: *which procedure is mine, which documents do I need in my case, and how do I fill in the form?* The answers are spread across government portals and Word files written in legal Vietnamese. Foreigners and first-timers get files rejected for missing a document that only applied to their case.

## What it does

1. **You describe what you need**, in Vietnamese, English or another language: *"Tôi muốn đăng ký tạm trú ở phòng trọ mới thuê"*, *"My visa is about to expire"*.
2. **The agent finds the procedure** in the official data. If nothing matches, it says so instead of guessing.
3. **It asks a few short questions** (at most 4) about your situation: age, lost or renewed document, applying online or in person… Each question shows which official documents it decides.
4. **You get a personal dossier**: documents to prepare, documents to double-check, and documents you probably don't need, with your own answer quoted as the reason. Steps, processing time, fees and legal basis are one click away.
5. **The official form is filled in for you** from a profile you enter once. You see the real form next to a plain-language list of its fields, preview the result, confirm you checked it, and download the PDF.
6. **Nothing is ever submitted on your behalf.** You print, sign and hand it in yourself.

## Grounding rules

These rules are enforced in code and covered by tests. The LLM is not trusted to follow them on its own.

| Rule | How |
|---|---|
| Every piece of information has a source | Each step, document, fee, deadline and form field carries a `source` (URL, procedure code or form number, date read). The UI shows it. |
| "I don't know" instead of inventing | The LLM only *chooses* among procedures and document IDs we hold. Text shown to users always comes from the official data, never from the model. Unknown request → explicit "not found in official sources". |
| A document is only dropped with a reason | The agent can mark a document "not needed" only by citing one of the user's own answers. Otherwise it stays visible as "check this". |
| Minimal personal data to the model | The agent sees only age and nationality from the profile, never names, ID numbers or addresses. |
| No submission | The app only generates files for download. A test checks that no code path posts to a government host. |

## Evaluation

The evaluation runs on a free local model (`qwen2.5:7b` through Ollama) against a hand-labelled set of **66 requests** in Vietnamese, English, French, Korean and Chinese ([`data/evals/routing.jsonl`](data/evals/routing.jsonl)). The set includes real procedures we do *not* cover, off-topic requests and prompt-injection attempts.

| | Result |
|---|---|
| Right procedure, in-scope requests (50) | **95.8–100 %** across runs |
| Correct "not in official sources" for uncovered or off-topic requests (14) | **13/14**. The one miss routes "set up a limited company" to *household business*. |
| Prompt-injection attempts resisted | **4/4** |
| Invented procedures shown to users | **0**. The model invented 0–1 per run; guardrails dropped them. |
| Model mistakes caught by guardrails in 50 full conversations | **144** (mostly trying to drop a document without any user answer behind it) |
| Documents shown word-for-word from the official source | **100 %** |

**Plain chatbot vs. Hồ Sơ AI on fees.** Asked directly *"what is the fee for <procedure>?"*, the same model gave a money amount for 13 of the 17 procedures, and **none of the 13 amounts appear in the official source**. It charged 50,000 VND for a first ID card and 100,000–150,000 VND to register a marriage, though both are free according to the official pages. Its passport fee changed between runs (80,000, then 120,000 VND); the official page says 160,000. Hồ Sơ AI shows the official fee text verbatim, or says the source doesn't state it. Some official pages only point to a circular instead of stating an amount, so an amount missing from the source is *unverifiable*, not always wrong.

**What the evaluation caught and we fixed:**
- **A prompt bug.** The procedure list given to the model was numbered, so it sometimes answered "13" instead of `passport`. In-scope accuracy went from 83 % to 95–100 % once fixed.
- **Broken official pages.** On four procedures, the fee box of the official page shows processing times ("07 Ngày làm việc") or a bare "1" instead of a fee. Ingestion now detects this. It doesn't show that text as a fee and warns the user, quoting the original.

Run it yourself (calls the configured model, roughly 5 minutes on Ollama):

```bash
cd apps/api
uv run python -m hosoai.evals.run            # or --part routing|fees|agent
```

Results are written to `data/evals/results/<model>-<date>.json` and `.md`. Scoring logic is unit-tested in `tests/test_evals.py`.

## Coverage

**17 procedures**, parsed from the Bộ Công an public service portal and the Lào Cai provincial portal: passport, ID card (new, exchange, reissue), permanent and temporary residence, criminal record, first vehicle registration, foreigner temporary residence card, foreigner stay extension, birth, death and marriage registration, marital status certificate, certified copies, household business registration and work permits for foreign workers.

**Fillable official forms:**

| Form | Used for | Status |
|---|---|---|
| **CT01**: Tờ khai thay đổi thông tin cư trú (Thông tư 56/2021/TT-BCA) | Temporary and permanent residence | human-reviewed |
| **NA5**: Tờ khai đề nghị cấp thị thực, gia hạn tạm trú (Thông tư 04/2015/TT-BCA) | Foreigner stay extension | human-reviewed |
| **TK05**: Đơn trình báo mất hộ chiếu phổ thông (Thông tư 31/2023/TT-BCA) | Passport (lost passport) | draft, learned by the agent |
| **CC01**: Tờ khai căn cước công dân | Citizen ID card | draft, learned by the agent |

All are the files currently linked from the Bộ Công an portal for these procedures. Any other form linked from a procedure page can be learned on demand (see below). Sections such as household members, sponsors and signatures are left for the user to complete by hand; the form page says so.

> The national portal (dichvucong.gov.vn) blocks automated access, so procedure data comes from the Bộ Công an and Lào Cai portals. For Lào Cai procedures, fees are provincial and may differ elsewhere. Known issues with a source (e.g. an outdated fee note) are shown to the user as warnings.

## The form-learning agent

Every procedure page links official forms, usually Word files. Instead of describing each one by hand, the app can **learn a form it has never seen**. On a procedure page, click **"Để trợ lý AI đọc tờ khai này"**; it takes 20–90 s with the local model.

1. **Fetch.** It downloads only files linked from the official page, only from `.gov.vn` hosts (redirects included), and only if the result really is a Word or PDF file. LibreOffice converts it to PDF.
2. **Find every place to write, in code.** This step finds labels followed by dots, character boxes (drawn rectangles or table cells), tick boxes (□), dates written `…/…/…` or `ngày… tháng… năm…`, and blanks on the next line. Code owns all the geometry: where to write and how much fits. It copes with superscripts inside labels, non-breaking spaces and Word's decomposed accents.
3. **The model decides what each place means.** It picks which blanks the applicant fills in (not the officials), names them, links them to the saved profile, splits the name into *Họ* and *Chữ đệm và tên* when the form does, and writes a short English gloss. It can only refer to candidate IDs.
4. **Code checks every proposal on the real PDF and sends errors back.** Checks include: the label isn't found, the value would cover printed text, the proposal is inconsistent (a field named `phone` not linked to the profile phone), or the field is about *another person* (father, mother, head of household, sponsor) but linked to the applicant's profile. The model gets up to 4 rounds to fix them.
5. **The result is saved as a draft.** The form page says it was read by AI and not yet reviewed.

Values that are too long for a blank are written smaller rather than cut. A value is cut only as a last resort, and the preview shows it.

**How well it works with `qwen2.5:7b`**, re-learning the two human-reviewed forms and comparing with the human specs (`uv run python -m hosoai.evals.run --part forms`):

| Form | Human fields found | Profile links correct | Wrong profile values |
|---|---|---|---|
| CT01 | 13–14 / 15 | 9 / 9 | 0 |
| NA5 | 16–19 / 21 | 8 / 8 | 0 |

Before the label checks below, the same model got 3–4 / 9 on CT01: it often shifted its answers by one line (the sex field linked to the ID number). Now code reads what it can from the printed label alone and the model handles the rest:
- a clear label sets the profile value (*Giới tính* → sex, *Email* → email). A model key that disagrees with its label is sent back as an error, which catches shifted answers;
- unnumbered blanks belong to the numbered item above them, so *Quốc tịch* and *Số CCCD* under "17. Họ tên của cha" are the father's and never take the applicant's data;
- the *Họ* / *Chữ đệm và tên* split is read from the label;
- only a label about birth (*sinh*) takes the date of birth.

The 7B model still sometimes skips a blank the applicant should fill in (an issue date, the purpose of entry). Learned forms stay drafts until a human reviews them. Switching to a stronger model is a `.env` change.

Some portal links (newer `/tttl/...` paths) answer scripts with 403. Download the file in a browser and learn it from disk: `uv run python -m hosoai.forms.learn --procedure <slug> --form <i> --file <path>`. The source stays the official URL.

## Architecture

```
 Browser (Next.js)                      API (FastAPI)                         Data
 ─────────────────                      ─────────────                         ────
 Ask ──────────── POST /agent ───────▶  matcher: request → procedure ◀────── data/procedures/parsed/*.json
 Answer ───────── POST /agent/{id} ──▶  agent loop: ask_user | finish          (official text + source per item)
 Dossier ◀─────── dossier + forms ────  grounding checks, built from store
 Profile ──────── GET/PUT /profile ──▶  SQLite (local only) ─────────────────▶ hosoai.db (git-ignored)
 Form page ────── GET /forms/{id} ───▶  prefill from profile ◀─────────────── data/forms/<id>/form.json + PDF
 Preview/Download POST …/preview, /fill  PyMuPDF writes onto the official PDF
                                               │
                                        LLM client (any OpenAI-compatible API)
                                        Ollama qwen2.5:7b in dev, OpenAI for the demo
```

- **Procedure data**: `python -m hosoai.sources.ingest` fetches the official pages, keeps the raw HTML in `data/sources/raw/`, and parses each one into structured JSON with a source on every item.
- **Agent**: routing goes through a dedicated matcher. The case-questions loop then replies with one JSON action per turn, and the code validates every reply. If the model returns malformed output or loops, the app falls back safely to the full official list or to "not found".
- **Forms**: each official `.doc` is converted to PDF once, with LibreOffice. A hand-checked `form.json` lists the exact labels printed on the form. The filler writes after a label, one digit per printed box, around printed date separators (`/` or `ngày… tháng… năm…`), or ticks a drawn checkbox. It handles labels printed in two fonts and Word's decomposed Vietnamese accents.

## Run it locally

### Requirements

- [uv](https://docs.astral.sh/uv/) (Python 3.12), Node.js 20+ and [pnpm](https://pnpm.io/)
- [Ollama](https://ollama.com) for a free local LLM
- LibreOffice, to learn new forms (`sudo apt install libreoffice-writer-nogui`)

### 1. Local model (once)

```bash
ollama pull qwen2.5:7b          # ~5 GB, needs ~8 GB free RAM
cp .env.example .env            # defaults point at Ollama
```

Start Ollama with a larger context window. The default 4096 tokens silently truncates long procedures:

```bash
OLLAMA_CONTEXT_LENGTH=16384 ollama serve
```

If Ollama runs as a system service, make a 16k variant of the model instead (no sudo needed) and set `LLM_MODEL=qwen2.5:7b-16k` in `.env`:

```bash
printf 'FROM qwen2.5:7b\nPARAMETER num_ctx 16384\n' > Modelfile
ollama create qwen2.5:7b-16k -f Modelfile
```

Check with `curl -s localhost:11434/api/ps`: `context_length` should be 16384.

### 2. API (port 8000)

```bash
cd apps/api
uv sync
uv run uvicorn hosoai.main:app --reload --port 8000
```

### 3. Web app (port 3000)

```bash
cd apps/web
pnpm install
pnpm dev
```

Open <http://localhost:3000>.

### Try it

1. **Hồ sơ cá nhân** (top right): fill in a profile. Fake data is fine.
2. On the home page, try:
   - `Tôi muốn đăng ký tạm trú ở phòng trọ mới thuê` → questions → dossier → **Điền tờ khai CT01**
   - `My visa is about to expire` → dossier → **Điền tờ khai NA5**
   - `Je veux un permis de pêche` → "not found in official sources"
3. On a form: check the fields, click **Xem trước** (preview), tick the review box, then **Tải tờ khai (PDF)** (download).

### Using OpenAI instead of Ollama

Change `.env` only; the code is provider-agnostic:

```bash
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=<chat model>
LLM_VISION_MODEL=<vision model>
```

## Tests and checks

Tests never call a real AI service. They replay recorded model replies from `apps/api/tests/fixtures/llm/`.

```bash
# API
cd apps/api
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy src

# Web
cd apps/web
pnpm test && pnpm lint && pnpm typecheck
```

The tests cover:
- every procedure item cites an official `.gov.vn` page;
- unknown requests return "not found";
- invented procedure slugs or document IDs are dropped, and a document can't be excluded without the user's own answer;
- the agent never receives names, ID numbers or addresses;
- values land after the right labels on the real CT01 and NA5 forms, ID digits land one per box, and the correct checkbox is ticked;
- no code path submits to a government host.

## Project structure

```
apps/
  api/src/hosoai/
    agent/        matcher (request → procedure), agent loop, sessions
    llm/          the only LLM client (OpenAI-compatible) + fake client for tests
    sources/      official page ingestion and parsers (Bộ Công an, Lào Cai)
    procedures/   procedure models and store
    profile/      personal details (SQLite)
    forms/        form specs, PDF filling, previews
    main.py       HTTP routes
  web/
    app/          / (ask), /procedure/[slug], /forms/[id], /profile
    components/   AgentChat, DossierView, FormFiller, ProfileForm, SourceNote…
data/
  procedures/     catalog.json (official pages) + parsed/*.json
  sources/raw/    official pages as fetched
  forms/<id>/     official .doc, converted PDF, form.json (labels + sources)
  fonts/          DejaVu Sans (Vietnamese glyphs for filled values)
```

### Adding a form

Let the agent draft it, then review it:

```bash
cd apps/api
uv run python -m hosoai.forms.learn --procedure passport            # list the official forms
uv run python -m hosoai.forms.learn --procedure passport --form 0   # learn one (draft)
```

Review `data/forms/<id>/form.json`: check labels, profile links and hints against the preview, then set `"status": "reviewed"`. Run `uv run pytest`; the real-form test fails if any label can't be found on the PDF. Reviewed forms are never overwritten by the agent.

## Limitations

- The local 7B model sometimes asks clumsy questions or over-uses the original request as a reason. Stronger models do noticeably better. Every reason shown is a quote of the user's own words, so mistakes stay visible.
- Learned forms are drafts: placement is checked by code, but the meaning of each field needs a human review, especially with a small model.
- Scanned (image-only) forms are not supported yet. They would need the vision model to find fields, and every form linked so far is a text document.
- Some portals don't serve the file itself (Lào Cai shows a viewer page; some Bộ Công an links answer "Access Denied"). The agent refuses those instead of guessing.
- One local user. Sessions live in memory and the profile in a local SQLite file.
- Official sources can lag behind new laws. The app shows what the portal publishes, plus any known warnings, and asks users to check with the receiving office before filing.

## Data and licences

Procedure text and forms come from Vietnamese public service portals and are cited on every item. The Bộ Công an portal asks that reuse cite *"Cổng Dịch vụ công - Bộ Công an"*. DejaVu Sans is distributed under its free font licence (see `data/fonts/README.txt`).
