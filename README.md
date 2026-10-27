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

## Coverage

**17 procedures**, parsed from the Bộ Công an public service portal and the Lào Cai provincial portal: passport, ID card (new, exchange, reissue), permanent and temporary residence, criminal record, first vehicle registration, foreigner temporary residence card, foreigner stay extension, birth, death and marriage registration, marital status certificate, certified copies, household business registration and work permits for foreign workers.

**2 fillable official forms:**

| Form | Used for | Official version |
|---|---|---|
| **CT01**: Tờ khai thay đổi thông tin cư trú | Temporary and permanent residence | Thông tư 56/2021/TT-BCA |
| **NA5**: Tờ khai đề nghị cấp thị thực, gia hạn tạm trú | Foreigner stay extension | Thông tư 04/2015/TT-BCA |

Both are the files currently published on the Bộ Công an portal for these procedures. Sections such as household members, sponsors and signatures are left for the user to complete by hand; the form page says so.

> The national portal (dichvucong.gov.vn) blocks automated access, so procedure data comes from the Bộ Công an and Lào Cai portals. For Lào Cai procedures, fees are provincial and may differ elsewhere. Known issues with a source (e.g. an outdated fee note) are shown to the user as warnings.

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
- LibreOffice is needed only to add new forms (`sudo apt install libreoffice-writer-nogui`)

### 1. Local model (once)

```bash
ollama pull qwen2.5:7b          # ~5 GB, needs ~8 GB free RAM
cp .env.example .env            # defaults point at Ollama
```

Start Ollama with a larger context window. The default 4096 tokens silently truncates long procedures:

```bash
OLLAMA_CONTEXT_LENGTH=16384 ollama serve
```

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

1. Download the official file linked from the procedure page into `data/forms/<id>/`.
2. Convert it: `soffice --headless --convert-to pdf --outdir data/forms/<id> data/forms/<id>/<file>.doc`.
3. Write `form.json` with the **exact** labels printed on the form, the `source` URL and the procedure slugs it belongs to.
4. Run `uv run pytest`. The real-form test fails if any label can't be found on the PDF.

## Limitations

- The local 7B model sometimes asks clumsy questions or over-uses the original request as a reason. Stronger models do noticeably better. Every reason shown is a quote of the user's own words, so mistakes stay visible.
- Two forms so far. Scanned (image-only) forms would need the vision model to locate fields, and none of the current forms require it.
- One local user. Sessions live in memory and the profile in a local SQLite file.
- Official sources can lag behind new laws. The app shows what the portal publishes, plus any known warnings, and asks users to check with the receiving office before filing.

## Data and licences

Procedure text and forms come from Vietnamese public service portals and are cited on every item. The Bộ Công an portal asks that reuse cite *"Cổng Dịch vụ công - Bộ Công an"*. DejaVu Sans is distributed under its free font licence (see `data/fonts/README.txt`).
