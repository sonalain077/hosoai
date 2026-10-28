"""Teach the app an official form linked from a procedure page.

    uv run python -m hosoai.forms.learn --procedure passport            # lists its forms
    uv run python -m hosoai.forms.learn --procedure passport --form 0   # learn the first one
    uv run python -m hosoai.forms.learn --procedure passport --form 0 --file ~/Downloads/x.doc
        # same, from the official file saved in a browser (portals that block scripts)

Downloads the official file, converts it, runs the form-learning agent with the configured
model (LLM_* env vars), and saves a DRAFT spec in data/forms/<id>/.
"""

import argparse
import json
import sys
from pathlib import Path

from hosoai.forms.learn.fetch import FetchError
from hosoai.forms.learn.service import LearnError, learn_procedure_form
from hosoai.llm import OpenAICompatibleClient
from hosoai.procedures.store import get_store
from hosoai.settings import Settings


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--procedure", required=True)
    ap.add_argument("--form", type=int, help="index in the procedure's list of forms")
    ap.add_argument("--id", help="id for data/forms/<id> (default: the form code)")
    ap.add_argument("--file", type=Path, help="the official file, downloaded by hand")
    ap.add_argument("--force", action="store_true", help="re-learn a draft that already exists")
    args = ap.parse_args()

    settings = Settings()
    p = get_store().get(args.procedure)
    if p is None:
        sys.exit(f"unknown procedure {args.procedure!r}")
    if args.form is None:
        for i, f in enumerate(p.forms):
            print(f"[{i}] {f.label[:80]}\n    {f.url}")
        return
    try:
        spec, report = learn_procedure_form(
            p,
            args.form,
            OpenAICompatibleClient(settings),
            settings,
            form_id=args.id,
            force=args.force,
            local_file=args.file,
        )
    except (FetchError, LearnError) as e:
        sys.exit(f"cannot learn this form: {e}")
    print(json.dumps(report.model_dump(), ensure_ascii=False, indent=2))
    print(f"\nSaved draft spec: data/forms/{spec.id}/form.json ({len(spec.fields)} fields)")


if __name__ == "__main__":
    main()
