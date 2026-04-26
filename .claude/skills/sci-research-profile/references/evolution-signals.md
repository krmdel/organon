# Profile Evolution Signals

This document defines what signals trigger profile updates, what auto-updates vs requires user approval, and what NEVER changes automatically.

## What Auto-Updates (No Approval Needed)

**Research Activity Log** (`## Research Activity Log` section at end of profile)
- One row per session date
- Format: `| Date | Skills Used | Topics | Notes |`
- Always added by `scripts/profile-evolve.py` during meta-wrap-up Step 3g
- Idempotent: re-running for the same date replaces the row, doesn't duplicate

This is a factual record. The user is welcome to read it, but they don't need to approve each row.

## What Requires User Approval

### Keywords (in Research Focus → Keywords)
A topic is **proposed** as a new keyword when:
- It appears in 2+ historical sessions AND today's session
- It's not already in the existing Keywords list (case-insensitive)
- It's not a stopword or generic phrase

Example: If "local AI deployment" appears in sessions on April 1, April 9, and April 13 — and isn't already a keyword — propose adding it.

### Active Questions (in Research Focus → Active Questions)
An emergent question is proposed when:
- The user has explored the same area from multiple angles across sessions
- E.g., asked about "OpenClaw architecture", then "OpenClaw market positioning", then "OpenClaw competitors" → suggest active question: "How will local AI tools like OpenClaw reshape the SaaS market?"

Auto-detection of emergent questions is hard. The script flags candidates; the user confirms.

## What NEVER Auto-Updates

These fields are sacrosanct — only the user (via `sci-research-profile`) can change them:

- **Core Identity**: Name, Institution, Department, Career Stage
- **Citation Style**: Preferred citation format
- **Tool Ecosystem**: Languages, statistical tools — these change deliberately, not from session signals

Even if the script detects a contradiction (e.g., user says "I work at MIT now"), the script does NOT modify the field. It surfaces the observation in the meta-wrap-up summary so the user can manually run `sci-research-profile` to update.

## Topic Frequency Threshold

The default minimum is **2 sessions** (configurable via `min_count` parameter in `find_recurring_topics()`).

Rationale:
- 1 session = could be a one-off research detour, not a real interest shift
- 2 sessions = pattern emerging
- 3+ sessions = strong signal (these appear higher in proposals)

## How Keywords Are Extracted

The script extracts candidate topics from:
- Capitalized phrases (e.g., "Local AI", "OpenClaw", "CRISPR Cas9")
- Quoted phrases
- Multi-word proper nouns

Filtered out:
- Stopwords (the, and, for, etc.)
- Short fragments (<4 chars)
- Generic terms ("Session", "Goal", "Notes")

## Failure Modes

The script handles these gracefully:
- **No profile** → skip with reason; meta-wrap-up reports skip
- **No memory for date** → skip
- **Memory search returns empty** → still update activity log, no proposals
- **Profile parsing error** → log warning, don't corrupt profile

`scripts/profile-evolve.py` is best-effort. A failure does not block meta-wrap-up.
