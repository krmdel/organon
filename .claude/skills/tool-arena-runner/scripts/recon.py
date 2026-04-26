#!/usr/bin/env python3
"""Recon — bootstrap a new arena project directory.

Creates:
    {project_dir}/PLAYBOOK.md  (copy of playbook-template.md with slug header)
    {project_dir}/NOTES.md     (canned fetch-problem pointers)

Idempotent: if PLAYBOOK.md already exists, it is NOT overwritten — we print a
warning, set playbook_skipped=True, and continue. NOTES.md is also preserved
if it already exists.
"""
from __future__ import annotations

import sys
from pathlib import Path


NOTES_TEMPLATE = """\
# {slug} — Recon Notes

<!-- Live scratch pad for this arena problem. Append everything non-trivial here. -->

## Getting started

Use `tool-einstein-arena` to fetch the full problem spec:

```bash
python3 .claude/skills/tool-einstein-arena/scripts/fetch_problem.py {slug}
python3 .claude/skills/tool-einstein-arena/scripts/analyze_competitors.py \\
    --problem-id <id> --top 10
```

Local layout expected by `tool-arena-runner polish`:

```
{project_dir}/
├── PLAYBOOK.md           # 7-section campaign log (do not rename sections)
├── NOTES.md              # this file
├── evaluator.py          # defines eval_fn(V) -> float (lower is better)
├── solutions/
│   ├── best.json         # warm-start, consumed by polish
│   └── polished.json     # arena-runner output
└── logs/
```

## Verifier

- [ ] Copy verifier from fetched problem
- [ ] Wrap in `float_score` / `mpmath_score` / `extra_score` callables so
      `tool-arena-runner tri-verify` can call them.

## Leaderboard snapshot

<!-- Paste the top-5 scores the first time you recon this problem. Update as
     competitors submit. -->

## Open questions

<!-- Anything blocking submission. -->
"""


def _prepend_header(template_text: str, slug: str) -> str:
    """Prepend a one-line slug header so each generated PLAYBOOK is identifiable.

    The template's own `{Problem Slug}` placeholder stays — the scientist fills
    it during their first pass. We just drop a leading comment line that
    encodes the slug for automated audits.
    """
    header = f"<!-- recon-slug: {slug} -->\n"
    return header + template_text


def recon(slug: str, project_dir: Path, template_path: Path) -> dict:
    """Bootstrap {project_dir} with PLAYBOOK.md + NOTES.md.

    Returns a dict summarising actions taken:
        {
            "playbook": <path>,
            "notes": <path>,
            "playbook_skipped": bool,
            "notes_skipped": bool,
        }
    """
    project_dir = Path(project_dir)
    template_path = Path(template_path)

    if not template_path.is_file():
        raise FileNotFoundError(
            f"playbook template not found: {template_path} "
            "(expected tool-einstein-arena/assets/playbook-template.md)"
        )

    project_dir.mkdir(parents=True, exist_ok=True)

    playbook_path = project_dir / "PLAYBOOK.md"
    notes_path = project_dir / "NOTES.md"

    playbook_skipped = False
    if playbook_path.exists():
        print(
            f"[recon] PLAYBOOK.md already exists at {playbook_path} — "
            "not overwriting. Delete the file manually if you want a fresh copy.",
            file=sys.stderr,
        )
        playbook_skipped = True
    else:
        template_text = template_path.read_text()
        playbook_path.write_text(_prepend_header(template_text, slug))
        print(f"[recon] wrote {playbook_path}")

    notes_skipped = False
    if notes_path.exists():
        print(
            f"[recon] NOTES.md already exists at {notes_path} — not overwriting.",
            file=sys.stderr,
        )
        notes_skipped = True
    else:
        notes_path.write_text(
            NOTES_TEMPLATE.format(slug=slug, project_dir=str(project_dir))
        )
        print(f"[recon] wrote {notes_path}")

    return {
        "playbook": playbook_path,
        "notes": notes_path,
        "playbook_skipped": playbook_skipped,
        "notes_skipped": notes_skipped,
    }


if __name__ == "__main__":  # pragma: no cover - invoked by arena_runner.py
    import argparse

    p = argparse.ArgumentParser(description="Bootstrap an arena project directory")
    p.add_argument("--slug", required=True)
    p.add_argument("--project-dir", required=True)
    p.add_argument("--template", required=True)
    args = p.parse_args()
    recon(
        slug=args.slug,
        project_dir=Path(args.project_dir),
        template_path=Path(args.template),
    )
