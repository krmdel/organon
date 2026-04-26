# Contributing to Organon

## Before You Contribute

You need a working Organon install. If you haven't set one up yet, follow the [README](README.md) — it takes about five minutes. Every contribution you submit should be tested against your own instance first. Don't submit something you haven't run yourself.

## Not a Developer? You Can Still Contribute.

You don't need to write code. If you have a research workflow, a use case, or a prompt sequence that Organon doesn't handle well — that's a contribution.

1. **Open a [Non-Technical Contribution](../../issues/new) issue.** Describe your workflow or idea in plain language. A concrete example beats a vague description every time.
2. **A maintainer picks it up.** They'll work with you to shape it into a skill or improvement — writing the SKILL.md, wiring the triggers, running the tests.
3. **You get full credit.** Your name goes in the `author` field of the skill's YAML frontmatter and in `CONTRIBUTORS.md`.

**Other ways to contribute without code:**
- Report bugs or unclear skill behavior
- Test a skill on your own research domain and report what broke
- Suggest improvements to existing skills or documentation
- Share a use case that exposes a gap in the skill pack

---

## What Can You Contribute?

| Type | What belongs here | Status |
|------|-------------------|--------|
| **New skill** | A new `{category}-{name}/` folder under `.claude/skills/` | Open |
| **Skill improvement** | Better methodology, additional references, bug fix in an existing skill | Open |
| **Core framework** | Changes to `CLAUDE.md`, `context/SOUL.md`, routing logic, heartbeat | **Curated** — discuss in an issue first |
| **Scripts** | New utility scripts under `scripts/` | Open for additions; curated for changes to `install.sh` and `update.sh` |
| **Documentation** | README, `docs/`, guides | Open |
| **Bug reports** | Anything broken — skill routing, hook behavior, MCP server, cron dispatcher | Open |

Not sure where yours fits? Open a discussion issue first.

---

## Skill Categories

| Prefix | Domain | Examples |
|--------|--------|---------|
| `sci-` | Science / research | `sci-literature-research`, `sci-hypothesis` |
| `ops-` | Operations / scheduling | `ops-cron`, `ops-ulp-polish` |
| `viz-` | Visual / diagrams | `viz-nano-banana`, `viz-diagram-code` |
| `tool-` | Utility / integration | `tool-paperclip`, `tool-gdrive` |
| `meta-` | System / meta | `meta-skill-creator`, `meta-wrap-up` |

**Rules:**
- Folder name must be `{category}-{skill-name}` in kebab-case
- The YAML `name` field in `SKILL.md` must match the folder name exactly
- Output folders follow the same prefix: `projects/{category}-{output-type}/`
- Never use `claude` or `anthropic` in a skill name

---

## Required Files for a New Skill

Every skill lives in its own folder under `.claude/skills/`:

```
.claude/skills/{category}-{skill-name}/
├── SKILL.md          ← required: YAML frontmatter + methodology
├── references/       ← depth material, one topic per file
├── scripts/          ← executables, including setup.sh if needed
└── assets/           ← examples, templates
```

Only `SKILL.md` is mandatory. Add `references/`, `scripts/`, and `assets/` as needed.

---

## SKILL.md Standards

`SKILL.md` must have YAML frontmatter followed by the skill methodology. Keep the whole file under 200 lines.

**Frontmatter requirements** (under 1024 characters / ~100 words):

```yaml
---
name: {category}-{skill-name}
description: >
  One-paragraph description of what the skill does, who it's for,
  and what it produces. Include trigger phrases (what the user says
  to invoke it) and negative triggers (what should NOT invoke it).
---
```

**Methodology requirements:**

- `## Outcome` — what the skill produces, where outputs land
- `## Context Needs` — which `research_context/` files it reads and why
- `## Dependencies` — table of required/optional skills or tools, with fallback behavior if absent
- One `## Step N` heading per phase of execution — keep steps numbered and ordered
- `## Rules` — a self-updating section the skill appends corrections to after user feedback
- No hardcoded paths, emails, or credentials anywhere in the file

**Trigger phrases must be concrete.** "search papers", "PubMed", "literature review" — not vague like "research stuff". Negative triggers must be explicit too: list what NOT to route here.

**Graceful degradation is mandatory.** Every external service the skill calls must have a documented fallback for when the API key is absent. Skills must never break on a missing key.

---

## Registration Checklist

When you add a new skill, update these four places in `CLAUDE.md`:

- [ ] Row in the **Skill Registry** table (skill name + trigger phrases)
- [ ] Row in the **Context Matrix** table (which `research_context/` files it reads)
- [ ] Entry in `context/learnings.md` under `# Individual Skills` (can be an empty `## {folder-name}` section — the skill populates it over time)
- [ ] Entry in `.claude/skills/_catalog/catalog.json`

If your skill uses an external API:
- [ ] Add the key name to the **Service Registry** table in `CLAUDE.md`
- [ ] Add `KEY_NAME=` to `.env.example`
- [ ] Document the signup URL and free-tier availability in SKILL.md

If your skill produces publishable text:
- [ ] Include a humanizer confirmation step (see `tool-humanizer` docs and the **Humanizer Gate** in `CLAUDE.md`)

If your skill produces shareable deliverables:
- [ ] Wire through the **Drive Push Gate** (see `CLAUDE.md`)

If your skill uses an external binary (`uv`, `ffmpeg`, etc.):
- [ ] Include `scripts/setup.sh` that checks `command -v` first, uses `brew` on macOS with `curl`/`pip` fallback, never asks for user interaction

---

## Auto-Setup Convention

Skills that need system dependencies ship a `scripts/setup.sh` that:

1. Checks `command -v` before installing anything
2. Prefers `brew` on macOS, falls back to `curl` / `pip`
3. Reports per-dependency status on stdout
4. Never prompts for user input
5. Is safe to run multiple times

---

## PR Format

**Title:** `[{category}] Short description`

Examples:
- `[sci] add sci-protocol-design skill for experimental design`
- `[tool] add tool-zotero integration for reference management`
- `[fix] sci-writing step 0 routing drops review mode`
- `[docs] improve install instructions for Windows`

**Description must include:**
- What the skill/fix does
- What it requires (external APIs, system tools)
- Confirmation that you tested it on your own Organon instance and what you tested
- For new skills: the trigger phrases you validated

---

## The Review Process

1. You submit a PR
2. CI runs the automated checks (see below) — all must pass
3. A maintainer reviews for quality, methodology soundness, and fit with the framework
4. Expect 3–7 days for human review

---

## What Gets Rejected

- Contains credentials, API keys, or hardcoded secrets
- SKILL.md over 200 lines or frontmatter over 1024 characters
- Trigger phrases are too vague to route reliably, or duplicate an existing skill's triggers without explanation
- No fallback behavior for missing API keys
- Modifies `context/SOUL.md`, the heartbeat order in `CLAUDE.md`, or core routing logic without a prior discussion issue
- Changes `scripts/install.sh` or `scripts/update.sh` without a prior discussion issue
- Output paths don't follow the `projects/{category}-{type}/` convention
- Breaks existing tests in `tests/`

---

## Automated Checks

Every PR is validated by CI. All must pass:

1. **Folder structure** — skill folder is under `.claude/skills/` with correct `{category}-{name}` naming
2. **SKILL.md present** — every skill folder has a `SKILL.md`
3. **Frontmatter valid** — YAML parses cleanly, `name` field matches folder name, length under 1024 chars
4. **No credentials** — no API keys, tokens, or secrets in any file
5. **Catalog entry** — `.claude/skills/_catalog/catalog.json` includes the new skill
6. **CLAUDE.md registration** — Skill Registry and Context Matrix rows exist for the new skill
7. **Learnings section** — `context/learnings.md` has a `## {folder-name}` section under `# Individual Skills`
8. **Output path convention** — any `projects/` path referenced in SKILL.md uses the correct category prefix
9. **No binary blobs** — no files over 1 MB, no `.exe`, `.dmg`, `.zip`, `.tar.gz`
10. **Test suite** — `pytest tests/ -x` passes with no new failures

---

## Contributor Ladder

| Level | What it means | How you get here |
|-------|---------------|-----------------|
| **Community Member** | You use Organon and participate in issues | Show up — report bugs, share workflows, ask questions |
| **Contributor** | At least one merged contribution (code or non-code) | Submit a PR or have a mentor submit one with your attribution |
| **Regular** | Consistent, trusted contributor | 3+ merged contributions, or sustained help reviewing or testing others' work |
| **Maintainer** | Review PRs, mentor contributors, shape the roadmap | Invited by existing maintainers based on sustained, quality involvement |

Non-code contributions count at every level. Testing a skill on your research domain, mentoring a non-technical contributor, improving documentation, and triaging issues all count toward progression.

---

## Code Style

- **Python:** PEP 8, 4-space indent, type hints encouraged, `snake_case` for vars and functions, `UPPERCASE` for module constants
- **Shell:** `#!/usr/bin/env bash` + `set -euo pipefail`, detect platform via `uname`, POSIX where possible
- **Markdown:** ATX headings, fenced code blocks with language tags, one blank line between sections
- **No comments** explaining *what* the code does — only *why*, when the reason is non-obvious

---

## Getting Help

- Open an issue with the `question` label
- Check `context/learnings.md` — it accumulates session-specific knowledge that may already cover your question
- Read `CLAUDE.md` end-to-end — the routing, gate, and architecture decisions are all documented there

---

*Organon is named after Aristotle's treatises on the tools of correct reasoning. Contributions that sharpen the instrument are always welcome.*
