#!/usr/bin/env python3
"""PreToolUse hook — sci-writing fabrication verification gate.

Fires BEFORE a Write/Edit/MultiEdit on a watched manuscript and simulates
the proposed post-write content against `verify_ops.py`. CRITICAL findings
or contract refusals cause exit 2, which blocks the tool call — the file
on disk is never modified.

Why PreToolUse, not PostToolUse:
  PostToolUse runs after the write lands. Exit 2 only feeds advisory text
  back to the model, which can ignore it. PreToolUse exit 2 actually
  cancels the write, so the gate becomes load-bearing instead of advisory.

Simulation strategy:
  - Write: proposed content = tool_input["content"] verbatim.
  - Edit:  proposed content = current file with old_string → new_string
           (first occurrence unless replace_all=True).
  - MultiEdit: apply edits sequentially, same rules.
  Proposed content is written to a sibling tempfile in the same directory
  as the real target so that:
    (a) the sibling .bib is discovered by the same scope rules, and
    (b) the temp manuscript's `<path>.citations.json` sidecar can be
        staged by copying the real sidecar (if any) to the temp path,
        preserving verify_ops' sidecar contract without touching the
        real file.

Fail-closed policy (T1.2):
  - Any internal exception, subprocess failure, timeout, or refused
    contract → exit 2 (block). The previous exit 0 fail-open path is
    gone. A broken gate is treated as a rejection, not a pass.

Scope rules (unchanged):
  - Only Write / Edit / MultiEdit on `.md` files under
    `projects/sci-writing/**` or `projects/sci-communication/**`.
  - Sidecar / audit artifacts (`.citations.json`, `*-verification.md`,
    `*-review.md`, `*-audit.md`) are skipped — they are outputs of the
    gate, not inputs to it.

Claude Code PreToolUse protocol:
  - stdin: JSON event (tool_name, tool_input, ...)
  - exit 0: allow the tool call
  - exit 2: block the tool call and surface stderr to the model
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path


PROJECT_ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path(__file__).resolve().parents[2]))
VERIFY_OPS = PROJECT_ROOT / ".claude/skills/sci-writing/scripts/verify_ops.py"

# A4: Primary watched prefixes (unchanged — always gated regardless of bib).
WATCHED_PREFIXES = (
    "projects/sci-writing/",
    "projects/sci-communication/",
    "projects/briefs/",
)

VERIFY_TIMEOUT_SECONDS = 120


# ---------------------------------------------------------------------------
# Event parsing
# ---------------------------------------------------------------------------


def _read_event() -> dict:
    try:
        return json.loads(sys.stdin.read() or "{}")
    except Exception:
        return {}


def _tool_name(event: dict) -> str:
    return event.get("tool_name") or event.get("tool") or ""


def _tool_input(event: dict) -> dict:
    return event.get("tool_input") or event.get("input") or {}


def _extract_path(event: dict) -> str | None:
    tool = _tool_name(event)
    if tool not in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        return None
    ti = _tool_input(event)
    # NotebookEdit uses notebook_path; the others use file_path/path.
    return (
        ti.get("file_path")
        or ti.get("path")
        or ti.get("notebook_path")
    )


def _is_watched_notebook(abs_path: Path) -> bool:
    """B1 (Phase 9): NotebookEdit gate.

    Returns True if the notebook is in a watched workspace (primary prefix
    or sibling-bib). When True, the hook refuses NotebookEdit so a writer
    cannot circumvent the verify_gate by routing draft markdown through a
    notebook cell instead of through Write/Edit on the .md file.
    Simulating arbitrary cell-source insertion into the rendered markdown
    is out of scope for the gate — refusing is the conservative default.
    """
    if abs_path.suffix.lower() != ".ipynb":
        return False
    try:
        rel = abs_path.resolve().relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return False
    rel_str = rel.as_posix()
    if rel_str.startswith(WATCHED_PREFIXES):
        return True
    return _has_sibling_bib(abs_path)


def _has_sibling_bib(abs_path: Path) -> bool:
    """A4: return True if any sibling *.bib file exists next to abs_path."""
    parent = abs_path.parent
    try:
        return any(parent.glob("*.bib"))
    except OSError:
        return False


def _is_watched(abs_path: Path) -> bool:
    try:
        rel = abs_path.resolve().relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return False
    rel_str = rel.as_posix()

    if abs_path.suffix.lower() != ".md":
        return False
    name = abs_path.name.lower()
    if name.endswith(".citations.json"):
        return False
    if any(name.endswith(suffix) for suffix in ("-verification.md", "-review.md", "-audit.md")):
        return False

    # Primary prefixes are always watched (no sibling-bib requirement).
    if rel_str.startswith(WATCHED_PREFIXES):
        return True

    # A4: any .md that has a sibling .bib is watched, regardless of path.
    # This catches projects/briefs/organon-whitepaper/, docs/, papers/2026/<slug>/,
    # and any custom directory the user passes to sci-communication.
    if _has_sibling_bib(abs_path):
        return True

    return False


# ---------------------------------------------------------------------------
# Content simulation
# ---------------------------------------------------------------------------


class SimulationError(RuntimeError):
    """Raised when the proposed tool call cannot be simulated (malformed
    input, old_string not found, etc.). Fail-closed: treated as a block."""


def _simulate_content(tool: str, tool_input: dict, target: Path) -> str:
    if tool == "Write":
        content = tool_input.get("content")
        if content is None:
            raise SimulationError("Write tool_input missing 'content'")
        return content

    if tool == "Edit":
        old = tool_input.get("old_string")
        new = tool_input.get("new_string")
        if old is None or new is None:
            raise SimulationError("Edit tool_input missing old_string/new_string")
        if not target.exists():
            raise SimulationError(f"Edit target does not exist: {target}")
        current = target.read_text(encoding="utf-8")
        if old not in current:
            raise SimulationError("Edit old_string not found in current file")
        if tool_input.get("replace_all"):
            return current.replace(old, new)
        return current.replace(old, new, 1)

    if tool == "MultiEdit":
        edits = tool_input.get("edits") or []
        if not edits:
            raise SimulationError("MultiEdit tool_input missing 'edits'")
        if not target.exists() and not any(
            e.get("old_string") == "" for e in edits[:1]
        ):
            raise SimulationError(f"MultiEdit target does not exist: {target}")
        current = target.read_text(encoding="utf-8") if target.exists() else ""
        for i, e in enumerate(edits):
            old = e.get("old_string")
            new = e.get("new_string")
            if old is None or new is None:
                raise SimulationError(f"MultiEdit edit #{i} missing fields")
            if old and old not in current:
                raise SimulationError(f"MultiEdit edit #{i} old_string not found")
            if e.get("replace_all"):
                current = current.replace(old, new)
            else:
                current = current.replace(old, new, 1) if old else (new + current)
        return current

    raise SimulationError(f"Unsupported tool '{tool}'")


# ---------------------------------------------------------------------------
# Tempfile staging
# ---------------------------------------------------------------------------


def _find_sibling_bib(md_path: Path) -> Path | None:
    for bib in sorted(md_path.parent.glob("*.bib")):
        return bib
    return None


def _find_sibling_quotes(md_path: Path) -> Path | None:
    """Locate the upstream {slug}.quotes.json seed next to the draft so
    verify_ops can run Phase H (upstream provenance trace). Without this,
    the gate silently skips the fabrication check that prevents a writer
    from inventing a quote outside the researcher's seed pool.
    """
    for q in sorted(md_path.parent.glob("*.quotes.json")):
        return q
    return None


def _snapshot(path: Path) -> tuple[int, int] | None:
    """Capture (size, mtime_ns) of `path` or None if it doesn't exist.

    Used to enforce the self-loop invariant (see _assert_no_real_mutation):
    verify_ops.py must never touch the real target file — only the staged
    tempfile. If the snapshot changes between gate entry and gate exit,
    the invariant is broken and we fail closed.
    """
    try:
        st = path.stat()
    except FileNotFoundError:
        return None
    return (st.st_size, st.st_mtime_ns)


def _assert_no_real_mutation(target: Path, before: tuple[int, int] | None) -> None:
    """Invariant: verify_ops.py must not mutate the real target file.

    The hook's safety model depends on this: we stage a sibling tempfile,
    run verify_ops against the temp, and let verify_ops rewrite the temp
    with auto-fixes (citation marker normalisation, etc.). The REAL file
    on disk must be untouched — the whole point of PreToolUse is to
    preview without committing. If verify_ops ever grew a code path that
    wrote back to the absolute input path, this assertion would catch it
    on the next gate run. Fail-closed: a broken invariant raises
    RuntimeError, the caller surfaces it as exit 2, and nothing lands.
    """
    after = _snapshot(target)
    if before == after:
        return
    raise RuntimeError(
        f"self-loop invariant violated: {target} changed during gate run "
        f"(size/mtime {before} → {after}). verify_ops must only write to "
        f"the staged tempfile, never the real target."
    )


def _stage_preview(target: Path, proposed: str) -> tuple[Path, list[Path]]:
    """Write `proposed` to a sibling temp .md next to `target` so that
    sibling-based discovery (.bib, .citations.json) keeps working.

    Returns (temp_md, cleanup_paths). Caller must remove cleanup_paths
    in a finally block, regardless of outcome.
    """
    suffix = f".gate-preview-{uuid.uuid4().hex[:10]}.md"
    temp_md = target.with_name(target.stem + suffix)
    cleanup: list[Path] = [temp_md]
    temp_md.write_text(proposed, encoding="utf-8")

    real_sidecar = Path(str(target) + ".citations.json")
    if real_sidecar.exists():
        temp_sidecar = Path(str(temp_md) + ".citations.json")
        shutil.copyfile(real_sidecar, temp_sidecar)
        cleanup.append(temp_sidecar)

    return temp_md, cleanup


def _cleanup(paths: list[Path]) -> None:
    for p in paths:
        try:
            p.unlink()
        except FileNotFoundError:
            pass
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _block(message: str) -> int:
    print(message, file=sys.stderr)
    return 2


def main() -> int:
    event = _read_event()
    tool = _tool_name(event)
    target = _extract_path(event)
    if not target:
        return 0

    md_path = Path(target)
    if not md_path.is_absolute():
        md_path = (PROJECT_ROOT / md_path).resolve()

    # B1 (Phase 9): NotebookEdit on a watched-workspace .ipynb is refused.
    # The gate's content-simulation logic only handles markdown Write/Edit
    # on .md files; rendering a notebook cell change into the equivalent
    # markdown to verify is out of scope. Refusing keeps the contract
    # mechanically sound: a writer cannot route around the citation gate
    # by burying claims in a notebook cell. Notebooks outside watched
    # workspaces (no sibling .bib, not under primary prefixes) pass through.
    if tool == "NotebookEdit":
        if _is_watched_notebook(md_path):
            return _block(
                "[verify-gate] refused: NotebookEdit on a watched "
                f"workspace ({md_path}). Notebook cells cannot be "
                "verified by the citation gate. Export the cell content "
                "to a sibling .md and edit through Write/Edit, OR move "
                "the notebook outside the watched workspace if it is "
                "not part of the citable manuscript."
            )
        return 0

    if not _is_watched(md_path):
        return 0

    # C2: humanize_lock enforcement. If the workspace has a
    # .pipeline_state.json marking the draft as finalized with the
    # humanize lock still set, refuse the write outright — the
    # conductor must run `auditor_pipeline.py post-humanize` first
    # (which clears the lock on pass, or flips to refused on fail).
    # This closes the gap where a humanizer pass could silently break
    # the verbatim-quote contract and ship because the conductor
    # forgot to run post-humanize.
    state_json = md_path.parent / ".pipeline_state.json"
    if state_json.exists():
        try:
            state_data = json.loads(state_json.read_text(encoding="utf-8"))
        except Exception:
            state_data = {}
        if state_data.get("humanize_lock") and state_data.get("phase") == "finalized":
            return _block(
                "[verify-gate] refused: humanize_lock is set on this "
                f"workspace ({state_json.parent.name}). The auditor "
                "pipeline finalized the draft, so any further "
                "Write/Edit on the .md must be followed by "
                "`auditor_pipeline.py post-humanize <category> "
                f"{state_json.parent.name}` to re-verify the draft "
                "against the sidecar. If you don't intend to run the "
                "humanizer, call post-humanize anyway — it clears the "
                "lock on pass."
            )

    # Snapshot the real target BEFORE we run any verification. On exit we
    # re-snapshot and assert it is byte-for-byte unchanged — this enforces
    # the self-loop invariant (verify_ops must only touch the staged
    # tempfile). See _assert_no_real_mutation for the full rationale.
    real_before = _snapshot(md_path)

    # Simulate the proposed post-write content
    try:
        proposed = _simulate_content(tool, _tool_input(event), md_path)
    except SimulationError as exc:
        return _block(
            f"[verify-gate] refused: could not simulate proposed {tool} on "
            f"{md_path}: {exc}\nFix the tool call or read the current file first."
        )
    except Exception as exc:
        return _block(f"[verify-gate] refused: simulation error ({exc})")

    # Stage sibling tempfile + sidecar
    try:
        temp_md, cleanup = _stage_preview(md_path, proposed)
    except Exception as exc:
        return _block(f"[verify-gate] refused: could not stage preview ({exc})")

    try:
        bib = _find_sibling_bib(md_path)
        quotes = _find_sibling_quotes(md_path)

        # Pure-expertise support: when no sibling .bib exists, omit --bib
        # entirely. verify_ops will detect zero `[@Key]` markers and run
        # in pure-expertise mode (Phases B, D, E only). If the draft DOES
        # contain markers without a bib, verify_ops exits 3 (REFUSED)
        # with a clear error — we surface that as exit 2 below.
        verify_cmd = [
            sys.executable,
            str(VERIFY_OPS),
            str(temp_md),
            "--no-fix",
        ]
        if bib is not None:
            verify_cmd.extend(["--bib", str(bib)])
        if quotes is not None:
            verify_cmd.extend(["--quotes", str(quotes)])

        try:
            result = subprocess.run(
                verify_cmd,
                capture_output=True,
                text=True,
                timeout=VERIFY_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return _block(
                f"[verify-gate] refused: verify_ops.py timed out after "
                f"{VERIFY_TIMEOUT_SECONDS}s on {md_path}. Fail-closed policy: "
                "a hung verifier blocks the save."
            )
        except FileNotFoundError as exc:
            return _block(
                f"[verify-gate] refused: verify_ops.py not found at "
                f"{VERIFY_OPS} ({exc})."
            )
        except Exception as exc:
            return _block(
                f"[verify-gate] refused: verify_ops.py failed to start "
                f"({exc}). Fail-closed policy."
            )

        if result.returncode == 0:
            return 0

        banner = "[verify-gate] sci-writing verification gate BLOCKED this save"
        verdict = (
            "REFUSED — contract failure (missing bib/sidecar)"
            if result.returncode == 3
            else f"BLOCKED — exit {result.returncode}"
        )
        detail = ((result.stdout or "") + (result.stderr or "")).strip()
        # Replace temp path with real path in the feedback so the model
        # isn't confused by the sibling preview filename.
        detail = detail.replace(str(temp_md), str(md_path))
        return _block(
            f"{banner}\n"
            f"File: {md_path}\n"
            f"Bib: {str(bib) if bib else '(none found in sibling directory)'}\n"
            f"Quotes: {str(quotes) if quotes else '(none found — Phase H upstream provenance skipped)'}\n"
            f"Verdict: {verdict}\n\n"
            f"{detail}\n\n"
            "The file on disk was NOT modified. Fix the issues above and "
            "retry. If no bib exists yet, run sci-literature-research cite "
            "mode first."
        )
    finally:
        _cleanup(cleanup)
        # Self-loop invariant check — run this AFTER cleanup so the
        # assertion sees the same on-disk state the caller will see.
        # If verify_ops ever mutates the real target, fail closed.
        try:
            _assert_no_real_mutation(md_path, real_before)
        except RuntimeError as exc:
            print(f"[verify-gate] refused: {exc}", file=sys.stderr)
            # os._exit so no other `return 0` path can override us.
            os._exit(2)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # last-ditch fail-closed
        print(f"[verify-gate] refused: unhandled exception ({exc})", file=sys.stderr)
        sys.exit(2)
