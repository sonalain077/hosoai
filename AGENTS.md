# AGENTS.md — Hồ Sơ AI

Instructions for AI coding agents (Codex, Claude Code, etc.) working in this repo.
Source of the product spec: `ho so ai.pdf` (repo root). Hackathon: https://codexhackathon.sea.com/

## What we are building (5 lines)

1. A single web app where anyone in Vietnam (citizens, residents, foreigners) describes an administrative procedure in their own words — "I need a new passport", "I want to register my online shop".
2. The agent finds that procedure in the official national procedure database, asks a few short questions to work out which case the user is in, and shows the whole task: required documents, order, processing time, fees, and common reasons files get rejected.
3. Every requirement links to the official rule it came from. If the official source does not say it, the app says "we don't know". It never answers from model memory.
4. The user enters personal details once in a reusable profile. The app shows the real form beside a plain-language list of its fields. Fillable PDFs are filled directly. Scanned-image forms use a vision model to locate each field.
5. The user reviews everything before a file is generated and downloads the real document, ready to hand in. **Nothing is ever submitted on the user's behalf.**

## Non-negotiable rules

These apply to the product's behavior and to the agents writing its code.

1. **Every piece of information has a source.** Each requirement, fee, deadline, document or form field shown to a user must carry a citation (URL + procedure code / legal document number) to an official source. Code that returns procedural info without a `source` field is a bug. Agents writing docs, comments or PR descriptions cite where a claim comes from (file path, URL, or the spec PDF).
2. **Say "I don't know" instead of inventing.** If retrieval finds no official source, return an explicit "not found in official sources" result. Never fill gaps with LLM guesses, made-up fees, made-up document lists, or made-up form fields. The same goes for agents: if you don't know a command, an API or a requirement, say so and ask. Don't guess.
3. **Never submit without human permission.**
   - Product: the app never submits a file to any government system. It only generates documents for the user to download after they review them.
   - Agents: never commit, push, open or merge a PR, deploy, or call an external write API without explicit approval from a human in the current session.
4. Personal data (the profile, ID numbers, scans) stays out of logs, prompts sent to third parties beyond what a task needs, test fixtures, and git. Use fake data in tests.
5. **No paid AI calls in tests or day-to-day development.**
   - Automated tests (`pytest`, `vitest`) never call a real AI service. They use a fake LLM client that returns recorded replies stored in `apps/api/tests/fixtures/llm/`.
   - Local development uses Ollama (free, runs on this machine). Only use a paid key (OpenAI) for final checks and the demo, and only when a human asks for it.
   - Never hard-code a provider. All LLM calls go through one client in `src/hosoai/llm/` that reads `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` and `LLM_VISION_MODEL` from the environment.

## Stack

> The spec PDF does not name a stack. This is the proposed stack for the hackathon. Update this section if the team picks something else.

| Layer | Choice | Why (from the spec) |
|---|---|---|
| Frontend | Next.js (App Router) + TypeScript + Tailwind CSS | Chat intake, checklist view, form beside field list |
| PDF viewing | `react-pdf` (pdf.js) | "You see the real form on screen" |
| Backend API | Python 3.12 + FastAPI + Pydantic | Agent orchestration, PDF work, data models |
| Agent / LLM | Any OpenAI-compatible API: **Ollama `qwen2.5:7b` for dev**, OpenAI for the demo | Find procedure, ask clarifying questions, structured output with sources |
| Vision | **Ollama `qwen2.5vl:7b` for dev**, an OpenAI vision model for the demo | Locate fields on scanned-image forms |
| PDF filling | PyMuPDF (`pymupdf`) | Fill AcroForm fields directly. Draw text at coordinates for scanned forms |
| Data | SQLite (dev) via SQLModel | User profile (entered once, reused), cached procedures + sources |
| Procedure source | Vietnam's National Public Service Portal (Cổng Dịch vụ công quốc gia, https://dichvucong.gov.vn) | The "national database" in the spec. Access method (API vs. scraping) is **not yet confirmed**: check before building on it |
| Python tooling | `uv`, `ruff`, `mypy`, `pytest` | |
| JS tooling | `pnpm`, `eslint`, `prettier`, `vitest` | |

## Repo structure

```
.
├── AGENTS.md              # this file (source of truth for agents)
├── CLAUDE.md              # imports AGENTS.md
├── ho so ai.pdf           # product spec
├── apps/
│   ├── web/               # Next.js frontend
│   │   ├── app/           # routes: / (ask), /procedure/[id], /forms/[id], /profile
│   │   ├── components/    # Chat, Checklist, SourceLink, FormViewer, FieldList
│   │   └── lib/           # API client, types shared with backend
│   └── api/               # FastAPI backend
│       ├── src/hosoai/
│       │   ├── main.py            # FastAPI app + routes
│       │   ├── llm/               # the only LLM client (reads LLM_* env vars) + fake client for tests
│       │   ├── agent/             # orchestration, tools, prompts
│       │   ├── sources/           # official-source retrieval + citation model
│       │   ├── procedures/        # procedure + requirement models
│       │   ├── forms/             # AcroForm filling, vision field detection, rendering
│       │   └── profile/           # reusable personal-details store
│       └── tests/
│           └── fixtures/llm/      # recorded LLM replies used by the fake client
├── data/
│   └── forms/             # official blank forms (PDF) + their source URLs
└── .env.example           # LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, LLM_VISION_MODEL, DATABASE_URL
```

Every model holding procedural info (requirement, fee, timeline, form) includes a `source: Source` field (`url`, `title`, `document_number`, `retrieved_at`). Keep it that way.

## Commands

### Free local AI setup (once)

Install Ollama from https://ollama.com, then:
```bash
ollama pull qwen2.5:7b      # chat + tool calling (~5 GB, needs ~8 GB free RAM)
ollama pull qwen2.5vl:7b    # vision, for scanned forms
cp .env.example .env
```

`.env` for development (free):
```bash
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama          # any value works with Ollama
LLM_MODEL=qwen2.5:7b        # or qwen2.5:7b-16k: needs a 16k context, see README "Local model"
LLM_VISION_MODEL=qwen2.5vl:7b
```

For the demo only, switch to OpenAI: `LLM_BASE_URL=https://api.openai.com/v1`, set a real `LLM_API_KEY`, and pick the models. Code stays the same.

### Backend (`apps/api`)
```bash
cd apps/api
uv sync                                         # install
uv run uvicorn hosoai.main:app --reload --port 8000   # run
uv run pytest                                   # test
uv run ruff check . && uv run ruff format --check .   # lint
uv run mypy src                                 # type-check
uv run python -m hosoai.sources.ingest          # re-fetch official procedure pages (network)
uv run python -m hosoai.sources.ingest --offline  # re-parse saved pages only
```

Procedure data: `data/procedures/catalog.json` lists the official pages (Bộ Công an portal + Lào Cai provincial portal; dichvucong.gov.vn blocks bots). Raw pages are saved in `data/sources/raw/`, parsed results in `data/procedures/parsed/<slug>.json`.

### Frontend (`apps/web`)
```bash
cd apps/web
pnpm install          # install
pnpm dev              # run on http://localhost:3000
pnpm test             # test (vitest)
pnpm lint             # lint (eslint)
pnpm typecheck        # tsc --noEmit
```

Before saying a task is done, run the test and lint commands for every app you touched and report the results. Don't hide failures.

## Testing priorities

- Every procedure answer has a source. Missing source → test fails.
- "Unknown" path: a query with no official match returns "I don't know", not a generated answer.
- Form filling: AcroForm values land in the right fields. Scanned-form text lands inside the detected boxes.
- No code path calls a government submission endpoint.
- No test makes a network call to an AI service. The fake LLM client is the default in the test config.
