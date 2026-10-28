"""Run the evals against the configured model (LLM_* env vars; Ollama by default).

    uv run python -m hosoai.evals.run                 # all parts
    uv run python -m hosoai.evals.run --part routing  # routing | fees | agent | forms

Writes data/evals/results/<model>-<date>.json and .md. Calls a real model: never run in CI.
"""

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hosoai.agent import loop
from hosoai.agent.matcher import _parse_slugs, match_procedure
from hosoai.evals.scoring import (
    FeeOutcome,
    RecordingLLM,
    RoutingCase,
    RoutingOutcome,
    rate,
    score_fee,
    score_routing,
    summarize_fees,
    summarize_routing,
)
from hosoai.llm import ChatMessage, LLMClient, OpenAICompatibleClient
from hosoai.procedures.store import ProcedureStore, get_store
from hosoai.settings import Settings

FEE_PROMPT = (
    "Lệ phí (phí) của thủ tục hành chính sau ở Việt Nam là bao nhiêu? "
    "Trả lời ngắn gọn, nêu số tiền cụ thể.\nThủ tục: {title}"
)


def _is_json(reply: str) -> bool:
    """Parseable JSON object or list ("[]" is a fine way to say "nothing matches")."""
    found = re.search(r"\{.*\}|\[.*\]", reply, re.DOTALL)
    if not found:
        return False
    try:
        return isinstance(json.loads(found.group(0)), dict | list)
    except json.JSONDecodeError:
        return False


def load_cases(path: Path) -> list[RoutingCase]:
    lines = path.read_text("utf-8").splitlines()
    return [RoutingCase.model_validate_json(line) for line in lines if line.strip()]


def run_routing(
    cases: list[RoutingCase], store: ProcedureStore, llm: LLMClient
) -> list[RoutingOutcome]:
    catalog = {p.slug for p in store.list()}
    out = []
    for case in cases:
        rec = RecordingLLM(llm)
        result = match_procedure(case.query, store, rec)
        raw = rec.replies[-1] if rec.replies else ""
        valid = _is_json(raw)
        o = score_routing(
            case,
            [c.slug for c in result.candidates],
            _parse_slugs(raw),
            valid,
            catalog,
            sum(rec.seconds),
        )
        o.raw_reply = raw[:300]
        print(
            f"  {'✓' if o.correct else '✗'} {case.id} [{case.category}] {case.query[:50]!r} "
            f"-> {o.candidates or 'not_found'}"
        )
        out.append(o)
    return out


def run_fees(store: ProcedureStore, llm: LLMClient) -> list[FeeOutcome]:
    out = []
    for summary in store.list():
        p = store.get(summary.slug)
        assert p is not None
        reply = llm.chat([ChatMessage(role="user", content=FEE_PROMPT.format(title=p.title))])
        o = score_fee(p.slug, p.fee.text if p.fee else None, reply)
        print(
            f"  {p.slug}: chatbot {o.baseline_amounts} official {o.official_amounts} "
            f"{'⚠ unsupported ' + str(o.unsupported_amounts) if o.unsupported_amounts else ''}"
        )
        out.append(o)
    return out


def run_agent(
    cases: list[RoutingCase], store: ProcedureStore, llm: LLMClient
) -> list[dict[str, Any]]:
    """Full conversations with a simulated user who always picks the first option."""
    out = []
    for case in cases:
        rec = RecordingLLM(llm)
        session = loop.new_session(case.id, case.query)
        reply = loop.start(session, store, rec)
        questions = 0
        while reply.type == "question" and reply.question and questions < 6:
            questions += 1
            reply = loop.answer(session, reply.question.options[0], store, rec)
        # Invariant: every document shown is the official text, untouched.
        verbatim = True
        statuses: dict[str, int] = {}
        if reply.dossier:
            official = store.get(reply.dossier.procedure.slug)
            assert official is not None
            for d, src in zip(reply.dossier.documents, official.documents, strict=True):
                verbatim &= d.document == src
                statuses[d.status] = statuses.get(d.status, 0) + 1
        row = {
            "case_id": case.id,
            "query": case.query,
            "result": reply.type,
            "procedure": reply.dossier.procedure.slug if reply.dossier else None,
            "questions": questions,
            "statuses": statuses,
            "guardrail_events": session.events,
            "documents_verbatim": verbatim,
            "llm_calls": len(rec.replies),
            "seconds": round(sum(rec.seconds), 2),
        }
        print(
            f"  {case.id} -> {row['result']} {row['procedure'] or ''} q={questions} "
            f"events={session.events}"
        )
        out.append(row)
    return out


def run_forms(llm: LLMClient, model_name: str) -> list[dict[str, Any]]:
    """Re-learn the human-reviewed forms and compare with the reviewed specs."""
    import unicodedata

    from hosoai.forms.learn.agent import learn
    from hosoai.forms.registry import FormRegistry

    def norm(t: str) -> str:
        t = unicodedata.normalize("NFC", t).replace("\xa0", " ")
        return re.sub(r"\s+", " ", t).strip(" :-").lower()

    settings = Settings()
    registry = FormRegistry(settings.data_dir / "forms")
    rows = []
    for summary in registry.list():
        human = registry.get(summary.id)
        if human is None or human.status != "reviewed":
            continue
        learned, report = learn(
            form_id=f"{human.id}-relearn",
            code=human.code,
            title=human.title,
            procedure_slugs=human.procedure_slugs,
            pdf=registry.pdf_path(human),
            original_file=None,
            source=human.source,
            font=settings.data_dir / "fonts" / "DejaVuSans.ttf",
            llm=llm,
            model_name=model_name,
            log=lambda *_: None,
        )

        def match(label: str, page: int, fields: Any = learned.fields) -> Any:
            for f in fields:
                a, b = norm(f.label), norm(label)
                # prefix, not substring: "1. họ tên" must not match "11. họ tên chủ hộ"
                same = a.startswith(b) or b.startswith(a)
                if f.page == page and same and min(len(a), len(b)) >= 4:
                    return f
            return None

        found = mapped = with_profile = 0
        misses: list[str] = []
        wrong: list[str] = []  # filled from the profile with a value that does not belong
        for hf in human.fields:
            lf = match(hf.label, hf.page)
            if lf is not None:
                found += 1
                if lf.profile_key and lf.profile_key != hf.profile_key:
                    wrong.append(f"{hf.label} <- {lf.profile_key}")
            else:
                misses.append(hf.label)
            if hf.profile_key:
                with_profile += 1
                mapped += lf is not None and lf.profile_key == hf.profile_key
        row = {
            "form": human.code,
            "human_fields": len(human.fields),
            "learned_fields": len(learned.fields),
            "human_fields_found": found,
            "profile_mappings_correct": f"{mapped}/{with_profile}",
            "wrong_profile_fills": len(wrong),
            "rounds": report.rounds,
            "missed_labels": misses,
            "wrong_fills": wrong,
        }
        print(
            f"  {human.code}: found {found}/{len(human.fields)} human fields, "
            f"profile mapping {mapped}/{with_profile}, wrong fills {len(wrong)}, "
            f"rounds {report.rounds}"
        )
        rows.append(row)
    return rows


def summarize_agent(rows: list[dict[str, Any]]) -> dict[str, object]:
    events: dict[str, int] = {}
    for r in rows:
        for e in r["guardrail_events"]:
            events[e] = events.get(e, 0) + 1
    dossiers = [r for r in rows if r["result"] == "dossier"]
    return {
        "conversations": len(rows),
        "ended_with_dossier": len(dossiers),
        "avg_questions": round(sum(r["questions"] for r in rows) / len(rows), 2) if rows else 0,
        "model_mistakes_caught_by_guardrails": sum(events.values()),
        "mistakes_by_type": dict(sorted(events.items(), key=lambda kv: -kv[1])),
        "documents_shown_verbatim_from_source_pct": rate(
            sum(r["documents_verbatim"] for r in dossiers), len(dossiers)
        ),
        "avg_seconds_per_conversation": round(sum(r["seconds"] for r in rows) / len(rows), 1)
        if rows
        else 0,
    }


def to_markdown(model: str, when: str, summary: dict[str, Any]) -> str:
    lines = [f"# Hồ Sơ AI evaluation: `{model}`", "", f"Run: {when}", ""]
    for part, values in summary.items():
        lines += [f"## {part}", "", "| metric | value |", "|---|---|"]
        for k, v in values.items():
            lines.append(
                f"| {k} | {json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else v} |"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--part", choices=["routing", "fees", "agent", "forms", "all"], default="all")
    ap.add_argument("--limit", type=int, default=None, help="only the first N cases")
    args = ap.parse_args()

    settings = Settings()
    store = get_store()
    llm = OpenAICompatibleClient(settings)
    cases = load_cases(settings.data_dir / "evals" / "routing.jsonl")[: args.limit]
    when = datetime.now(UTC).strftime("%Y-%m-%dT%H%MZ")
    summary: dict[str, Any] = {}
    details: dict[str, Any] = {}

    if args.part in ("routing", "all"):
        print("Routing:")
        r = run_routing(cases, store, llm)
        summary["routing"] = summarize_routing(r)
        details["routing"] = [o.model_dump() for o in r]
    if args.part in ("fees", "all"):
        print("Fees, plain chatbot vs official source:")
        f = run_fees(store, llm)
        summary["fees_vs_plain_chatbot"] = summarize_fees(f)
        details["fees"] = [o.model_dump() for o in f]
    if args.part in ("agent", "all"):
        print("Agent conversations:")
        in_scope = [c for c in cases if c.expected]
        a = run_agent(in_scope, store, llm)
        summary["agent"] = summarize_agent(a)
        details["agent"] = a

    if args.part in ("forms", "all"):
        print("Form learning vs human-reviewed specs:")
        rows = run_forms(llm, settings.llm_model)
        summary["form_learning"] = {
            r["form"]: {
                k: v for k, v in r.items() if k not in ("form", "missed_labels", "wrong_fills")
            }
            for r in rows
        }
        details["form_learning"] = rows

    out_dir = settings.data_dir / "evals" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"{settings.llm_model.replace(':', '-').replace('/', '-')}-{when}"
    payload = {"model": settings.llm_model, "run": when, "summary": summary, "details": details}
    (out_dir / f"{name}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), "utf-8"
    )
    (out_dir / f"{name}.md").write_text(to_markdown(settings.llm_model, when, summary), "utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nSaved {out_dir / name}.json/.md")


if __name__ == "__main__":
    main()
