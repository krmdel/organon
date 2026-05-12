#!/usr/bin/env python3
"""
lets_go_gate.py — Onboarding gate for Organon.

Fires on SessionStart and UserPromptSubmit. Probes the
context/.lets-go-onboarded marker and injects state-aware reminders
that route the model to /lets-go.

- SessionStart      : always emits a heartbeat reminder. The wording is
                      state-aware (first-run vs. returning vs. stale).
- UserPromptSubmit  : emits a hard reminder only when the marker is
                      missing or research_context/research-profile.md
                      is missing. This is the belt-and-suspenders gate
                      that catches the case where SessionStart was
                      skipped (e.g. user did not approve the hook on
                      the first run of a fresh clone).

Output is JSON on stdout per the Claude Code hook spec
(hookSpecificOutput.additionalContext). Always exits 0 so the gate
never hard-blocks the user — it only injects strong context.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

STALE_DAYS = 30

HEARTBEAT_INTRO = (
    "[heartbeat] Run the CLAUDE.md heartbeat now: load context/SOUL.md "
    "+ USER.md + latest context/memory/*.md + last 5-10 learnings.md "
    "entries + research_context/*.md."
)


def project_dir() -> Path:
    pdir = os.environ.get("CLAUDE_PROJECT_DIR")
    if pdir:
        return Path(pdir)
    return Path(__file__).resolve().parents[2]


def marker_present(root: Path) -> bool:
    return (root / "context" / ".lets-go-onboarded").is_file()


def profile_state(root: Path) -> str:
    profile = root / "research_context" / "research-profile.md"
    if not profile.is_file():
        return "missing"
    age_days = (time.time() - profile.stat().st_mtime) / 86400
    return "stale" if age_days > STALE_DAYS else "fresh"


def session_start_message(root: Path) -> str:
    if not marker_present(root):
        return (
            HEARTBEAT_INTRO
            + " FIRST-RUN MODE: context/.lets-go-onboarded is MISSING."
            " You MUST invoke /lets-go now to run first-run onboarding"
            " BEFORE answering any user prompt. Do not skip this step,"
            " even if the user opens with an unrelated request."
        )
    state = profile_state(root)
    if state == "missing":
        return (
            HEARTBEAT_INTRO
            + " RETURNING MODE: onboarding marker is present but"
            " research_context/research-profile.md is missing. Invoke"
            " /lets-go to rebuild research context before executing the"
            " user's request."
        )
    if state == "stale":
        return (
            HEARTBEAT_INTRO
            + " RETURNING MODE: research_context/research-profile.md is"
            f" older than {STALE_DAYS} days. Surface a one-line refresh"
            " prompt to the user, then run /lets-go for the recap."
        )
    return (
        HEARTBEAT_INTRO
        + " RETURNING MODE: invoke /lets-go for the recap"
        " (silent context load + open-threads check + goal question)."
    )


def user_prompt_message(root: Path):
    if not marker_present(root):
        return (
            "[onboarding-gate] context/.lets-go-onboarded is MISSING."
            " Before answering this prompt, invoke /lets-go to complete"
            " first-run onboarding. Defer the user's current request"
            " until /lets-go finishes. This gate fires on every prompt"
            " until onboarding is marked complete."
        )
    if profile_state(root) == "missing":
        return (
            "[onboarding-gate] research_context/research-profile.md is"
            " missing. Invoke /lets-go (returning mode) to rebuild it"
            " before producing personalised output."
        )
    return None


def emit(event: str, message: str) -> None:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": message,
        }
    }
    sys.stdout.write(json.dumps(payload))
    sys.stdout.write("\n")


def main(argv) -> int:
    if len(argv) < 2:
        return 0
    event = argv[1]
    root = project_dir()
    try:
        if event == "SessionStart":
            emit(event, session_start_message(root))
        elif event == "UserPromptSubmit":
            msg = user_prompt_message(root)
            if msg is not None:
                emit(event, msg)
    except Exception as exc:
        sys.stderr.write(f"[lets_go_gate] non-fatal error: {exc}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
