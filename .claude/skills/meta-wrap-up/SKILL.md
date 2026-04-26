---
name: meta-wrap-up
description: >
  End-of-session checklist that reviews deliverables, collects feedback,
  fixes skills, updates learnings, and commits work. Use when the user
  says "wrap up", "close session", "end session", "wrap things up",
  "we're done", "that's it for today", "session done", or invokes
  /wrap-up. Run at the end of any working session or after completing
  a major deliverable. Does NOT trigger for content writing, voice
  extraction, positioning, or audience research.
---

# Wrap-Up

End-of-session checklist. Five steps: review what was done, collect feedback, apply fixes, commit everything, show usage.

## Outcome

- Updated `context/learnings.md` with session feedback
- Updated `context/memory/{today}.md` with session log (4-section format)
- Updated `context/USER.md` if new preferences were observed
- Proposed `context/SOUL.md` updates if behaviour corrections were observed
- Direct fixes applied to any skills that need them
- CLAUDE.md Skill Registry, Context Matrix, and README.md synced
- Clean git commit of all session work

## Context Needs

| File | Load level | How it shapes this skill |
|------|-----------|--------------------------|
| `context/learnings.md` | `## meta-wrap-up` section | Check for previous wrap-up insights |
| `context/USER.md` | Full | Check if preferences need updating |
| `context/SOUL.md` | Full | Check if behaviour rules need updating based on session corrections |
| All `research_context/` files | Scan only | Files created or modified this session |

Load if they exist. Proceed without them if not.

## Step 1: Review Deliverables

1. Run `git status` and `git diff --stat` to see all changes.
2. List every file created or modified, grouped by location:
   - `research_context/` — foundation files written or updated
   - `projects/` — deliverables produced
   - `.claude/skills/` — skills created or modified
   - Other locations — flag for file placement check
3. **File placement check:** Verify outputs follow naming conventions (`projects/{category}-{type}/`, `{YYYY-MM-DD}_{name}.md`). Fix misplaced files now.

## Step 2: Collect Feedback

Ask the user (skip any that don't apply):
1. **What worked well?**
2. **What didn't work?**
3. **Any specific skill issues?**

For short sessions: "Anything to note before I wrap up?"

## Step 3: Apply Changes

### 3a: Update Learnings

Log to `context/learnings.md`:
- Skill-specific → `# Individual Skills → ## {skill-folder-name}`
- Cross-skill → `# General → ## What works well / ## What doesn't work well`

Dedup guard: scan the section first. Format: `- {YYYY-MM-DD}: {What happened and what was learned}`

### 3b: Fix Skills Directly

If feedback points to a specific skill issue, edit the SKILL.md or reference file directly. Don't just log it; fix it. Log the change to the skill's learnings section.

### 3c: Finalise Daily Memory

One file per day: `context/memory/{YYYY-MM-DD}.md`. Wrap-up **finalises the existing block** — never creates a new one.

Find the current `## Session N` block and fill in:

```
## Session N

### Goal
[One line — what the user set out to do]

### Deliverables
- `path/to/file` — what it is

### Decisions
- [Decision and rationale]

### Open threads
- [Anything unfinished for the next session]
```

Never leave placeholders. Omit sections that don't apply.

After finalising, rebuild the index:
```
python3 scripts/memory-search.py --rebuild-index
```

### 3d: Evolve SOUL.md

Review the session for behaviour corrections. If a pattern points to a missing rule in `context/SOUL.md`, **propose** the specific change to the user — only apply on approval. Skip for one-off corrections.

### 3e: Update User Preferences

If you noticed new patterns about how the user works, update `context/USER.md`. Don't ask for small Notes additions; do ask before changing core preferences.

### 3f: Skill & MCP Sync

Run CLAUDE.md Reconciliation:
- **Skills**: compare `.claude/skills/` against CLAUDE.md Skill Registry + Context Matrix. Add missing rows; ask before removing deleted skills.
- **Services**: scan new/modified skills for API key deps. Add new services to Service Registry + `.env.example` + README.
- **MCPs**: compare `.claude/settings.json` against README.md Connected Tools. Add undocumented; ask before removing.

Log sync actions in the session summary under **Registry sync**.

### 3g: Research Profile Evolution

If `research_context/research-profile.md` exists, run:
```
python3 scripts/profile-evolve.py
```
Always appends today's row to `## Research Activity Log`. If it proposes new keywords (topic recurs 2+ sessions), present them for user approval before adding.

### 3h: Pattern Detection → Skillification Proposal

Scan for recurring manual workflows (same multi-step pattern ≥3 times across sessions, no matching skill). If one surfaces:
- Name the workflow, sessions where it appeared, shape (inputs → steps → output)
- Propose: skill name, triggers, output path
- Offer: build now via `meta-skill-creator` / queue for next session / skip

At most **one** proposal per wrap-up. Never auto-build — user decides. Check Skill Registry first to avoid duplicating an existing skill.

## Step 4: Commit & Push

1. Stage all changes from the session.
2. Commit with a message summarising the work.
3. Push to remote.

## Session Summary

Present in this exact format after all steps:

```
--- Session Summary ---

Deliverables:
- {file path} — {what it is}

Learnings logged:
- {skill-name}: {one-line summary}
- General: {one-line summary if cross-skill insight}

Skills modified:
- {skill-name}: {what and why}  (or "None")

Registry sync:
- {what changed}  (or "No drift detected")

Memory:
- Daily log: context/memory/{YYYY-MM-DD}.md
- SOUL.md: {proposed change, or "No evolution needed"}
- User prefs: {what was updated, or "No changes"}

Committed: {commit hash} — {commit message}
---
```

---

## Step 5: Show Usage

Tell the user to run `/usage` to check their plan usage and remaining capacity.

---

## Rules

*Updated automatically when the user flags issues. Read before every run.*

- 2026-03-10: Daily memory file must contain real content, never placeholders. One file per day with `## Session N` blocks. Fill in goal and what happened — don't leave heartbeat scaffolding as-is.

---

## Self-Update

If the user flags an issue with the wrap-up process, update the `## Rules` section immediately with the correction and today's date.

---

## Troubleshooting

**No feedback:** Log "No feedback — routine session" with date. Still do file placement check and commit.
**Multiple skills used:** Collect feedback per skill; log to each skill's section separately.
**User skips steps:** Minimum useful wrap-up is Step 3a + Step 4.
