# CLAUDE.md

Guidance for Claude Code working in this repository. Organon is an agent-first Claude Code project template: personality in `context/SOUL.md`, user in `context/USER.md`, continuity in `context/memory/`, learnings in `context/learnings.md`, research context in `research_context/`, capabilities in `.claude/skills/`.

Every session starts with `/lets-go`. Two hooks route the model there:

1. `SessionStart` — runs `.claude/hooks_info/lets_go_gate.py SessionStart`. The gate probes `context/.lets-go-onboarded` and emits a state-aware heartbeat reminder (first-run vs. returning vs. stale-profile).
2. `UserPromptSubmit` — re-runs the same gate as belt-and-suspenders. If the onboarding marker is still missing when a prompt arrives (e.g. the user dismissed the project hook-trust prompt on a fresh clone), the gate injects a hard reminder that defers the user's request until `/lets-go` has run.

Everything else is a skill.

---

## Heartbeat

Run at the start of every session, in order:

1. **Load identity** — read `context/SOUL.md`, `context/USER.md`, today's + yesterday's `context/memory/*.md` (pay attention to `### Open threads`), and the last 5–10 entries in `context/learnings.md`. If a user request references work older than 2 days, run `python3 scripts/memory-search.py --query "{topic}"` (supports `--skill`, `--project`, `--date-from/--date-to`).
2. **Load research context** — read `research_context/research-profile.md` and `research_context/research-preferences.md` if they exist. Flag anything older than 30 days ("Your [file] is from [date]. Refresh, or keep going?").
3. **Scan state** — `.claude/skills/` (available skills), `projects/briefs/*/brief.md` (active projects, report if any), cron status files (report enabled jobs + last run if the LaunchAgent `com.organon.{slug}.plist` exists; silent otherwise).
4. **Sync check** — reconcile skills/MCPs/services against this file (see **Reconciliation**). Verify `context/.lets-go-onboarded` is present; if missing, treat the session as first-run and invoke `/lets-go` before doing anything else.
5. **Run `/lets-go`** automatically — it handles first-run onboarding and returning-session recaps. Never prompt the user to type it. If the onboarding gate fires a `[onboarding-gate]` reminder on a user prompt, that reminder is mandatory: defer the user's request until `/lets-go` completes.

### Daily Memory

One file per day: `context/memory/{YYYY-MM-DD}.md`, with numbered `## Session N` blocks appended as new sessions start.

**Session block template** (created by `/lets-go`, updated incrementally during work, finalised by `meta-wrap-up`):

```
## Session N
### Project       # omit for Level 1 single tasks
### Goal          # filled once the user states it
### Deliverables  # path — what it is
### Decisions     # decision + rationale
### Open threads  # unfinished items for the next session
```

**Incremental writes — MANDATORY, not aspirational.** The heartbeat creates the `## Session N` block on session start (via `/lets-go`). After that, the agent must touch the block at every one of these moments:

1. **Goal established** → fill the `### Goal` line as soon as the user states what they want.
2. **After every deliverable save** → append to `### Deliverables` with `path — what it is`. Not at the end of the session; at the end of that one deliverable.
3. **After any non-trivial decision** → append to `### Decisions` with one-line rationale. Examples: choosing a workspace path, swapping a tool, overriding a default, declining a gate offer.
4. **Before a long-running operation** (background agent, test suite, LP solve) → note it under `### Open threads` in case the session is interrupted.

Session crashes, context limits, and mid-session interruptions are the default case, not the exception. A block that is only finalised at wrap-up loses everything before the crash. Treat memory writes like git commits: small, frequent, at every natural checkpoint.

`meta-wrap-up` finalises the **existing** block; it never creates a new one.

**Auto wrap-up:** When the user signals session end ("thanks", "that's it", "done", "bye", "wrap up", etc.), run `meta-wrap-up` automatically. As part of wrap-up, `meta-wrap-up` scans the session + recent memory/learnings for recurring manual patterns (same ad-hoc workflow ≥3 times across sessions). If one surfaces, it proposes skillifying via `meta-skill-creator` before closing. User decides.

### Reconciliation

Compare disk state against this file; fix additions silently, confirm removals.

- **New skill on disk** → add rows to Skill Registry + Context Matrix, add a `## {folder-name}` section to `context/learnings.md` under `# Individual Skills`, update README.md, scan the SKILL.md for `*_API_KEY` / SDK imports / endpoint URLs and if a new external service is found add it to the Service Registry + `.env.example` + README, tell the user what was registered.
- **Skill in CLAUDE.md but folder missing** → ask before removing from registry/matrix/README/learnings.
- **New MCP server in `.claude/settings.json`** → add to README under Connected Tools.
- **Service unused after a skill is removed** → ask before deleting from Service Registry / `.env.example` / README.

---

## Task Routing

1. **System operations first** (table below) — execute directly.
2. **Skill search** — match user phrasing against the Skill Registry triggers. If matched, print the routing notice and invoke.
3. **No direct match? Cascade before custom code:**
   a. **Adjacent skill** — can an existing skill handle this with different inputs? (e.g. "analyse this survey" → `sci-data-analysis`, not a new skill).
   b. **ToolUniverse** — invoke `sci-tools` browse against the 2,200+ biomedical catalog; propose top matches and ask the user to pick.
   c. **Web / MCP** — only if a–b return nothing usable; search explicitly and cite sources.
   d. **New skill** — last resort, via `meta-skill-creator`.
4. Print `--- NO SKILL MATCH ---` only after the cascade returns nothing. Never silently drop to base knowledge + ad-hoc scripts.

**Skill Routing Notice** — print before invoking any skill:

```
--- SKILL ROUTED ---
Skill:   {folder-name}
Trigger: "{matched phrase}"
Reason:  {why this one over alternatives}
---
```

If a skill delegates to another mid-execution, print a second notice. If no match: `--- NO SKILL MATCH ---`.

**Science skill disambiguation** (when multiple `sci-*` could match, apply in order):

1. Data pattern asking what explains it → `sci-hypothesis`
2. Specific stat test / plot / data op → `sci-data-analysis`
3. Find / search papers → `sci-literature-research`
4. Draft / review a manuscript → `sci-writing`
5. Blog / tutorial / lay summary / thread / press release → `sci-communication`
6. Browse biomedical tools / create a new sci skill → `sci-tools`
7. Research notes / projects / scheduled pipelines → `sci-research-mgmt`
8. Trends / hot topics / field pulse → `sci-trending-research`

### Built-in Operations

| User says | Action |
|---|---|
| "add a client", "new client" | `bash scripts/add-client.sh "{name}"`, then show the structure block (below) and the `cd` instruction |
| "remove a skill", "uninstall {skill}" | `bash scripts/remove-skill.sh {skill-name}` |
| "add a skill", "install {skill}" | `bash scripts/add-skill.sh {skill-name}` |
| "list skills" | `bash scripts/list-skills.sh` |
| "search memory", "when did I", "recall" | `python3 scripts/memory-search.py --query "{terms}"` (add `--skill`, `--project`, `--date-from/--date-to` as needed) |

### Before / After Deliverables

- **Before:** load the relevant `research_context/` file and the skill's learnings section. If `research_context/` is missing, offer to build it via `/lets-go` — never block work.
- **After:** ask "How did this land? Any adjustments?"; log feedback to `context/learnings.md` under the skill section.

---

## Multi-Client Architecture

Organon supports multiple clients from a single install. The root holds shared methodology (CLAUDE.md, SOUL.md, skills, scripts). Each client gets a folder under `clients/` with its own research_context, memory, projects, and learnings.

```
organon/                           ← shared methodology
├── clients/
│   └── {slug}/
│       ├── research_context/      ← their profile + preferences
│       ├── context/
│       │   ├── SOUL.md → ../../context/SOUL.md   # inherited
│       │   ├── USER.md             ← unique
│       │   ├── learnings.md        ← unique
│       │   └── memory/             ← unique
│       ├── projects/               ← all outputs
│       ├── cron/                   ← scheduled jobs
│       └── .claude/skills/         ← root skills + client-only overrides
├── context/SOUL.md                 ← shared
└── .claude/skills/                 ← shared — edit once, all clients benefit
```

- **Shared:** skills, CLAUDE.md, SOUL.md (edit at root; every client folder holds a symlink back to the root `.claude/skills/` on Unix, so edits propagate instantly — on Windows, re-run `add-client.sh` to refresh).
- **Unique per client:** research_context, memory, learnings, USER.md, projects.
- **To work with a client:** `cd {absolute path}/clients/{slug} && claude` — `/lets-go` runs on first session. Use `pwd` to get the absolute path; never give a relative `cd`.
- **Client-only skills:** create directly in the client's `.claude/skills/` folder — they survive updates.
- Solo users can ignore `clients/` entirely and work from the root.

Full guide: [docs/multi-client-guide.md](docs/multi-client-guide.md).

---

## Three-Layer Architecture

| Layer | Files | Purpose |
|---|---|---|
| **Agent Identity** | `CLAUDE.md`, `context/SOUL.md`, `context/USER.md`, `context/memory/`, `context/learnings.md` | Who the agent is, who it helps, session continuity |
| **Skills Pack** | `.claude/skills/{category}-{skill-name}/` | Capabilities — grows over time |
| **Research Context** | `research_context/`, `research_artifacts/` | Researcher profile + ingested artifacts |

`.env`, `.mcp.json`, `installed.json`, `context/memory/*`, `projects/*`, `research_context/*.md`, `research_artifacts/` are gitignored.

---

## Skill Categories

| Prefix | Domain |
|---|---|
| `sci` | Science / research |
| `ops` | Operations / scheduling |
| `viz` | Visual / diagrams |
| `meta` | System / meta |
| `tool` | Utility / integration |

**Rules:** folder name = `{category}-{skill-name}` in kebab-case; YAML `name` field matches folder exactly; output folders use the same prefix (`projects/{category}-{output-type}/`); learnings sections are `## {folder-name}`; never use `claude` or `anthropic` in a skill name.

---

## Skill Registry

### Foundation

| Skill | Triggers |
|---|---|
| `sci-research-profile` | "research profile", "set up my profile", "who am I as a researcher" (writes `research_context/research-profile.md`) |

### Science

| Skill | Triggers |
|---|---|
| `sci-data-analysis` | "load data", "t-test", "ANOVA", "plot", "clean data", "statistics", "histogram", "scatter", "heatmap" |
| `sci-hypothesis` | "generate hypothesis", "test hypothesis", "what explains this", "design experiment", "power analysis" |
| `sci-literature-research` | "search papers", "PubMed", "arXiv", "literature review", "cite", "BibTeX", "parallel fanout", "fan out search", "concurrent literature search" |
| `sci-writing` | "draft introduction", "write methods", "format citations", "peer review", "write abstract" |
| `sci-communication` | "blog post", "tutorial", "explain this concept", "lay summary", "newsletter", "social thread", "press release", "scicomm" |
| `sci-tools` | "tools for", "browse tools", "ToolUniverse", "biomedical tools", "create a research skill" |
| `sci-research-mgmt` | "research note", "log observation", "research project", "milestones", "paper alerts", "run pipeline" |
| `sci-trending-research` | "what's trending in", "emerging research", "hot topics", "field pulse" |
| `sci-optimization` | "optimize", "linear program", "LP solver", "column generation", "cutting plane", "ULP polish", "competition math" |
| `sci-optimization-recipes` | "optimization recipe", "recipe for", "dinkelbach", "variable neighborhood", "k-climbing", "remez exchange", "cross-resolution transfer", "ulp descent", "lp reformulation", "mpmath lottery", "sigmoid bounding", "incremental o(n) loss" |
| `sci-council` | "research council", "ask the council", "mathematician council", "3 personas", "Gauss Erdős Tao", "fan out personas", "research fan-out" |

### Visual

| Skill | Triggers |
|---|---|
| `viz-nano-banana` | "scientific illustration", "generate an image", "pathway", "cell diagram", "schematic", "infographic" |
| `viz-excalidraw-diagram` | "excalidraw", "hand-drawn diagram", "sketch diagram" |
| `viz-diagram-code` | "mermaid", "flowchart", "sequence diagram", "architecture diagram", "mind map", "timeline diagram" |
| `viz-figure-mirror` | "match this figure style", "figure in the style of", "make my plot look like this paper", "publication figure from reference", "style transfer figure", "reproduce this figure with my data", "NeurIPS-quality version of this chart" |
| `viz-presentation` | "presentation", "slide deck", "slides", "convert to slides", "prepare a talk" |

### Utility

| Skill | Triggers |
|---|---|
| `tool-firecrawl-scraper` | "scrape", "crawl website", "extract from URL" |
| `tool-gdrive` | "push to Drive", "upload to Google Drive", "sync to Drive", "share this file", "stage output", "backup to Drive" |
| `tool-humanizer` | "humanize", "remove AI patterns", "make this sound natural" |
| `tool-obsidian` | "save to obsidian", "add to vault", "log to daily note", "capture to inbox", "search my notes", "open in obsidian" |
| `tool-youtube` | "youtube transcript", "fetch video", "channel videos" |
| `tool-paperclip` | "paperclip", "full-text biomedical", "bioRxiv", "medRxiv", "PMC", "grep papers", "ask-image" |
| `tool-substack` | "push to substack", "substack draft", "publish to substack", "create substack draft", "send to substack", "substack this post" |
| `tool-einstein-arena` | *(implementation layer — scripts called by tool-arena-runner; route all arena work through tool-arena-runner)* |
| `tool-arena-runner` | "arena runner", "arena polish", "tri-verify", "three-method verification", "submit to arena", "check leaderboard", "register agent", "fetch problem", "analyze competitors", "arena playbook", "problem playbook" *(tactical ops only — use `tool-arena-attack-problem` for full campaigns)* |
| `tool-arena-attack-problem` | "attack arena problem", "investigate arena challenge", "work on challenge", "new arena problem", "autonomous arena attack", "take on Einstein Arena challenge", "attack this problem", "bootstrap arena attack", "arena investigate", "full attack pipeline for", "autonomous campaign for" |

### Ops

| Skill | Triggers |
|---|---|
| `ops-cron` | "schedule a job", "recurring task", "cron", "run every day", "watchdog" |
| `ops-ulp-polish` | "ulp polish", "polish to zero", "precision polish", "bridge precision floor", "float64 coordinate descent", "break through 1e-13" |
| `ops-parallel-tempering-sa` | "parallel tempering", "simulated annealing", "PT-SA", "replica exchange", "temperature ladder", "MCMC optimization" |

### Meta

| Skill | Triggers |
|---|---|
| `meta-skill-creator` | "create a skill", "build a skill", "new skill", "optimize skill" |
| `meta-wrap-up` | auto-triggered on session-end signals ("thanks", "done", "wrap up", "that's it") |

*Optional skills are auto-registered by Reconciliation when their folders appear on disk. Install via `bash scripts/add-skill.sh <name>`. See `.claude/skills/_catalog/catalog.json` for the full list.*

---

## Context Matrix

Which `research_context/` files each skill reads.

| Skill | research-profile.md | learnings section |
|---|:---:|---|
| `sci-research-profile` | **writes** | `## sci-research-profile` |
| `sci-data-analysis` | field, preferences | `## sci-data-analysis` |
| `sci-hypothesis` | field, research questions | `## sci-hypothesis` |
| `sci-literature-research` | field, interests, journals | `## sci-literature-research` |
| `sci-writing` | field, writing style | `## sci-writing` |
| `sci-communication` | field, expertise, preferences | `## sci-communication` |
| `sci-tools` | field, tools ecosystem | `## sci-tools` |
| `sci-research-mgmt` | field, projects | `## sci-research-mgmt` |
| `sci-trending-research` | field, interests | `## sci-trending-research` |
| `sci-council` | field (optional, for persona calibration) | `## sci-council` |
| `viz-presentation` | field, expertise | `## viz-presentation` |
| `meta-wrap-up` | writes Activity Log only (via `scripts/profile-evolve.py`) | `## meta-wrap-up` |
| `viz-nano-banana` | — | `## viz-nano-banana` |
| `viz-diagram-code` | — | `## viz-diagram-code` |
| `viz-figure-mirror` | — | `## viz-figure-mirror` |
| `viz-excalidraw-diagram` | — | `## viz-excalidraw-diagram` |
| `meta-skill-creator` | — | `## meta-skill-creator` |
| `ops-cron` | — | `## ops-cron` |
| `ops-ulp-polish` | — | `## ops-ulp-polish` |
| `tool-firecrawl-scraper` | — | `## tool-firecrawl-scraper` |
| `tool-gdrive` | — | `## tool-gdrive` |
| `tool-humanizer` | — | `## tool-humanizer` |
| `tool-obsidian` | — | `## tool-obsidian` |
| `tool-youtube` | — | `## tool-youtube` |
| `tool-paperclip` | field, interests (optional) | `## tool-paperclip` |
| `tool-substack` | — | `## tool-substack` |
| `tool-einstein-arena` | — | `## tool-einstein-arena` |
| `tool-arena-runner` | — | `## tool-arena-runner` |
| `tool-arena-attack-problem` | — | `## tool-arena-attack-problem` |
| `sci-optimization` | — | `## sci-optimization` |
| `sci-optimization-recipes` | — | `## sci-optimization-recipes` |
| `ops-parallel-tempering-sa` | — | `## ops-parallel-tempering-sa` |

**Learnings rule:** every skill reads + writes its own section in `context/learnings.md`. Cross-skill insights go under `# General → ## What works well / ## What doesn't work well`. Skill-specific entries go under `# Individual Skills → ## {folder-name}`.

---

## Output Standards

- **Level 1 (single task):** `projects/{category}-{type}/{YYYY-MM-DD}_{name}.md`
- **Paper + auditor pipelines** (`sci-writing` draft, `sci-writing` review, and all `sci-communication` modes) write into a `projects/{category}/{slug}/` **workspace subdirectory** — not flat date-stamped files. The workspace holds the draft, bib, citations sidecar, audit/review artifacts, and the `.pipeline_state.json` state file. See `.claude/skills/sci-writing/references/{paper,auditor}-pipeline.md` for the contract.
- **Level 2 (planned project):** `projects/briefs/{project-name}/` with a `brief.md` (goal / deliverables / acceptance criteria / timeline / dependencies, one page max). All outputs live inside the project folder, never scattered.
- **Level 3 (GSD project):** same as Level 2, plus `.planning/` at repo root. All source code, configs, deps, and build artifacts go **inside** the project folder — never at the Organon repo root. One GSD project at a time per workspace; run `/archive-gsd` before starting another.
- Filename format: `{YYYY-MM-DD}_{descriptive-name}.md` (date-first, descending sort = newest first).
- Default format: markdown.
- Folders created on first use — no empty pre-scaffolding.
- **Auto-download binary outputs.** After saving any non-markdown file (PNG, PDF, SVG, video, etc.), `cp {path} ~/Downloads/`.
- **Show the clickable absolute path** after every save: "Saved to `/abs/path/to/file.md`".
- **Auto-open in IDE — cross-platform cascade.** After saving a previewable deliverable (`.md`, `.pdf`, `.docx`, `.xlsx`, `.csv`, `.tsv`, `.json`, `.svg`, `.png`, `.ipynb`), open it in the active editor as a new tab by trying in order:
  1. `$EDITOR {path}` if `$EDITOR` names a known IDE binary (`cursor`, `code`, `windsurf`, `codium`).
  2. `cursor {path}` → `code {path}` → `windsurf {path}` → `codium {path}` on PATH.
  3. macOS .app fallbacks: `/Applications/Cursor.app/Contents/Resources/app/bin/cursor`, `/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code`, `/Applications/Windsurf.app/Contents/Resources/app/bin/windsurf`.
  4. Windows fallbacks: `%LOCALAPPDATA%\Programs\cursor\cursor.exe`, `%LOCALAPPDATA%\Programs\Microsoft VS Code\bin\code.cmd`.
  5. If none work → the user is probably running Claude Code on a CLI-only machine. Do NOT silently fail; show the clickable absolute path and explicitly offer: *"No IDE detected. Want me to open this in your default browser instead?"* (obey the answer; remember it for the session).
  Batch rule: if one operation produces ≥3 files, prompt once — "Open all N in editor? (y/n)" — instead of opening each. Skip for ephemeral/debug files, `.planning/`, cron status, and research_context writes. First-time setup: run `bash scripts/setup-ide-previews.sh` to install the IDE extensions that render markdown-with-mermaid, docx, xlsx, pdf, and csv inline (Cursor, VS Code, and Windsurf all share the VS Code extension format).
- **Rich previews with Mermaid.** For any markdown deliverable that contains Mermaid diagrams (blog posts, whitepapers, tutorials, architecture docs), the IDE's built-in markdown preview usually handles them after `setup-ide-previews.sh` runs. When the user needs a standalone shareable HTML (e.g. a whitepaper with 7+ diagrams), use `python3 scripts/preview-md.py <path>` — it prefers the IDE, falls back to browser, and skips cleanly in headless / CI environments.
- **Drive push prompt.** After saving any deliverable that a collaborator might want, offer Drive staging — see **Drive Push Gate** below.
- **Project containment:** the Organon repo root is the operating system, not a dumping ground. Run `npm`/`python`/etc. from the project folder.

**Brief frontmatter:**
```yaml
---
project: q2-product-launch
status: active
level: 2
created: 2026-03-24
---
```

### Humanizer Gate

Before `tool-humanizer`, always ask the user. After drafting publishable text:

```
Your [blog / article / thread] is ready. Run it through the humanizer to remove AI writing patterns?
- Yes — polish the voice
- No — keep as-is
```

- **sci-writing** (formal academic): suggest skipping.
- **sci-communication** (blog / thread / newsletter): suggest applying.
- Uses `deep` mode when `research_context/research-profile.md` exists, `standard` otherwise.
- Only show the score delta if > 2 points.
- New skills that produce publishable text must include a humanizer confirmation step.

### Drive Push Gate

After saving a deliverable that a collaborator might care about (data files, figures, manuscript drafts, slide decks, reference lists, curated notes), offer Drive staging **once per deliverable**:

```
Saved to /abs/path/to/file.ext
Push to Google Drive for sharing/backup?
- Yes — stage to ~/Google Drive/My Drive/organon/{category}/
- No — keep local only
```

- **Always offer** for sci-data-analysis outputs, sci-writing manuscripts, viz-* figures/diagrams/decks, sci-literature-research BibTeX, sci-communication posts.
- **Never offer** for ephemeral/debug files, research_context/ writes, cron status files, test fixtures, or anything under `.planning/`.
- **Skip the prompt entirely** if `tool-gdrive status` reports Drive desktop is not mounted — proceed silently with local-only save.
- On "yes", run: `python3 .claude/skills/tool-gdrive/scripts/gdrive_ops.py stage {path}` and report the destination path in the response.
- Batch multiple deliverables from one operation into a single prompt ("Push all 3 figures to Drive?") — don't interrupt 3 times.
- Respect a session-wide "no, don't ask again for this session" once the user says it.
- New skills that produce shareable deliverables must wire through this gate — refer to it by name, don't duplicate the logic.

### Obsidian Sync Gate

**Obsidian is optional.** Check `tool-obsidian status` at the start of the session (or lazily on first use). If it returns `installed: false`, skip every prompt in this gate — framework is unaffected.

When Obsidian IS detected, after a skill produces a **knowledge artifact** (a markdown note a researcher would add to their personal knowledge base), offer:

```
Saved to /abs/path/to/notes.md
Also save to your Obsidian vault for the knowledge graph?
- Yes — write to <vault>/organon/{category}/
- No  — keep in Organon only
```

- **Always offer** for: `sci-literature-research` paper summaries (→ `paper-notes/`), `sci-hypothesis` experiment designs (→ `experiments/`), `sci-research-mgmt` research notes (→ `inbox/` or typed category), `meta-wrap-up` session summaries (→ `daily/`), `sci-data-analysis` written observations (→ `data-notes/`).
- **Never offer** for: binary files (CSVs, PDFs, images — those go through the Drive Push Gate), Organon framework files (`context/memory/`, `.planning/`, cron status), test fixtures.
- **Batch** multiple notes from one operation into a single prompt — don't interrupt repeatedly.
- **Invoke via**: `python3 .claude/skills/tool-obsidian/scripts/obsidian_ops.py write "<title>" --body "..." --category <cat> [--tags ...] [--link-to ...]`.
- **Complements Drive Push Gate, doesn't replace it.** Drive handles binaries/sharing; Obsidian handles knowledge/search. A manuscript draft might legitimately go to both.
- **Respect session opt-out** same as the Drive gate.
- New skills that produce knowledge artifacts must check `tool-obsidian status` and wire through this gate.

### Figure Proposal Gate

Fires in TWO timing modes. Both apply when `sci-writing` or `sci-communication` is producing drafts.

**(a) Hero offer — before drafting starts, for long-form documents.** If the output is a whitepaper, tutorial, review article, press release, or any document expected to have ≥ 5 sections, offer a single **hero illustration** at the top before any section is drafted:

```
This [whitepaper / tutorial / review] would benefit from a cover illustration
that sets the tone. Add one?
- scientific (publication-quality, Conceptual Figure sub-style)
- color     (editorial / warm hand-drawn, for casual outreach)
- notebook  (hand-drawn sketchnote)
- skip hero
```

Route approved choice to `viz-nano-banana` with the chosen style. Confirm sub-style per `viz-nano-banana` Step 3. Skip offer entirely for short-form content (social threads, newsletters, one-page explainers).

**(b) Per-section offer — during drafting.** After each major section (`##` heading) passes the accuracy gate, scan it for claims a visual would strengthen (trends, mechanisms, comparisons, workflows, architectures). Make **one** routed offer per qualifying section — never batch the whole draft, never interrupt mid-paragraph:

```
This [section] mentions [X]. Add a figure?
- plot from data     → sci-data-analysis
- diagram/workflow   → viz-diagram-code
- illustration       → viz-nano-banana  (confirm style per its Step 3)
- hand-drawn sketch  → viz-excalidraw-diagram
- skip this / skip rest
```

**Shared rules:**
- `skip rest` opts out for the remainder of the draft — respect it for both hero and per-section.
- Figures land in `projects/{category}/{slug}/figures/` and are embedded by relative path.
- Any Mermaid diagram produced through this gate MUST pass `scripts/preview-md.py --lint-only` before render — Mermaid v10+ breaks on unquoted `*`, `?`, `:`, `/`, `<br/>` in labels (see `viz-diagram-code` Step 2 for the quoting rule).
- After inserting any figure, re-save so the IDE auto-preview picks up the change.
- New writing-oriented skills must wire through this gate.

---

## Building New Skills

Always ask for reference skills before building. Use `meta-skill-creator` to scaffold.

```
.claude/skills/{category}-{skill-name}/
├── SKILL.md       ← YAML frontmatter + methodology (~200 lines max)
├── references/    ← depth material, one topic per file
├── scripts/       ← executables incl. setup.sh
└── assets/        ← examples, templates
```

**YAML frontmatter:** under 1024 chars (~100 words), include trigger phrases AND negative triggers, no XML brackets.

**Auto-setup convention:** skills needing binaries (`uv`, `yt-dlp`, `ffmpeg`, etc.) include `scripts/setup.sh` that checks `command -v` first, prefers `brew` on macOS with `curl`/`pip` fallback, reports per-dependency status, never asks for user interaction, runs once per machine.

**Dependencies:** declare a `## Dependencies` table in SKILL.md (Required / Optional, what it provides, fallback without it). Utility (`tool-`) skills never depend on execution skills.

**Registration checklist:**
- [ ] Folder = `{category}-{skill-name}` kebab-case; YAML `name` matches folder
- [ ] Row in Skill Registry + Context Matrix
- [ ] SKILL.md < 200 lines, frontmatter < 1024 chars
- [ ] References self-contained
- [ ] Declare `projects/` output folder (same category prefix)
- [ ] If external API: ensure key in Service Registry + `.env.example` + README
- [ ] If publishable text output: include humanizer confirmation step
- [ ] If shareable deliverable output: route through the Drive Push Gate
- [ ] If draft/writing output: route through the Figure Proposal Gate
- [ ] If no direct trigger match: follow the Task Routing cascade (adjacent skill → ToolUniverse → web → new skill)

---

## Graceful Degradation

Research context **enhances**, never gates. No `research_context/` → standalone mode (ask what's needed, produce solid generic output). Partial → use what exists, default the rest. Full → fully personalised.

---

## External Services & API Keys

Stored in `.env` (gitignored). `.env.example` is the template.

### Service Registry

| Service | Key | Used by | Enables | Fallback |
|---|---|---|---|---|
| Firecrawl | `FIRECRAWL_API_KEY` | `tool-firecrawl-scraper`, `sci-communication`, `/lets-go` link scan | JS-heavy site scraping, anti-bot bypass, content extraction | WebFetch, then ask for manual paste |
| OpenAI | `OPENAI_API_KEY` | `sci-trending-research` | Reddit search with real engagement metrics | WebSearch (no metrics) |
| xAI | `XAI_API_KEY` | `sci-trending-research` | X/Twitter search with real engagement | WebSearch (no metrics) |
| YouTube Data v3 | `YOUTUBE_API_KEY` | `tool-youtube` | Channel listing, @handle resolution | Transcript mode still works via yt-dlp |
| Google Gemini | `GEMINI_API_KEY` | `viz-nano-banana` | Image generation (Gemini 3 Pro Image) | None — free tier available |
| Paperclip | OAuth (CLI one-time) **or** HTTP MCP server at `https://paperclip.gxl.ai/mcp` (configured in `.mcp.json`) | `tool-paperclip`, `sci-literature-research`, `sci-hypothesis`, `sci-communication` | 8M+ full-text biomedical papers: `search`, `grep`, `map`, `ask-image`, `sql`, `lookup` + `citations.gxl.ai` line anchors | Federated search (paper-search MCP) |
| Papers With Code | public API | `sci-literature-research` | Code repo links in results | Results without code links |
| NCBI (PubMed) | `NCBI_API_KEY` in `.env` (source before `claude` start — see MCP note below) | `paper-search` MCP server (used by `sci-literature-research`, `sci-hypothesis`) | Higher PubMed rate limit (10 req/s vs 3 req/s) | Unauthenticated PubMed (rate-limited) |
| OpenAlex | `OPENALEX_API_KEY` in `.env` (same sourcing requirement) | `paper-search` MCP server | Polite pool access, higher rate limit, citation-ranked search | Unauthenticated OpenAlex (rate-limited) |
| Substack | `SUBSTACK_PUBLICATION_URL` + `SUBSTACK_SESSION_TOKEN` (`substack.sid` cookie) + `SUBSTACK_USER_ID` in `.env` | `tool-substack` | Markdown → draft post on Substack: upload images to CDN, pre-render mermaid, POST to private `/api/v1/drafts`. Draft-only — publish is always a human click. | Copy-paste into Substack editor manually |
| Unpaywall | `UNPAYWALL_EMAIL` in `.env` — any valid email (used as polite-pool identifier in the Unpaywall REST API `?email=` param) | `sci-writing` (Tier D full-text fetch, future) | Open-access PDF URL resolution for full-text claim verification | Skips full-text fetch; falls back to abstract-level quote check (MAJOR instead of CRITICAL for missing passage) |

**MCP servers (`.mcp.json`):**
- `paperclip` (HTTP) — biomedical corpus at `https://paperclip.gxl.ai/mcp`
- `paper-search` (local node) — federated PubMed/arXiv/OpenAlex/Semantic Scholar; launched via `scripts/with-env.sh` which sources `.env` before exec, so `NCBI_API_KEY` + `OPENALEX_API_KEY` are always picked up
- `tooluniverse` (uvx) — Harvard ToolUniverse catalog, used optionally by `sci-tools`

**`.env` loading for MCP servers:** `.mcp.json` routes local MCP commands through `scripts/with-env.sh`, a tiny shim that sources the repo `.env` and then execs the real command. This means cloning the repo, running `bash scripts/install.sh`, and populating `.env` is enough — no shell-rc changes, no `set -a; source .env` before launching `claude`. If you add a new MCP server that needs secrets, route it through the shim the same way:
```json
"my-server": {
  "command": "bash",
  "args": ["scripts/with-env.sh", "node", "mcp-servers/my-server/dist/index.js"]
}
```
Verify with `/doctor` — no "Missing environment variables" warning on `paper-search` means the shim is working. If it fails, check that `scripts/with-env.sh` is executable (`chmod +x`) — `install.sh` handles this on fresh clones.

**Rules for skills using external services:**
1. Check `.env` before every call. Never assume the key is present.
2. If missing, explain once (what it does, what's missed, signup URL, "add `KEY=...` to `.env`").
3. Always have a fallback. Skills never break on a missing key.
4. Don't block — proceed with the fallback and note what would improve.
5. Update `.env.example` when adding a new service.

---

## Permissions

`.claude/settings.json` allows: `cat`, `ls`, `npm run *`, basic git, edits to `/src/**`.
Denies: package installs, `rm`/`curl`/`wget`/`ssh`, reading `.env`/`.env.local`/credential files. `.env.example` is readable + editable (template, not secrets).

**Scope note — the deny list is advisory, not a sandbox.** `Read(.env)` and the credential denies only filter tool calls that Claude invokes (Read, Grep, Bash `cat`, etc.). They do NOT stop standalone Python or shell scripts from reading those files directly — scripts run outside the tool-use permission layer. Several skill scripts legitimately load `.env` this way to pick up their own API keys (e.g. `viz-nano-banana/scripts/generate_image.py::_load_dotenv` walks up for `GEMINI_API_KEY`). Treat the deny list as "keep Claude's own tool calls out of secrets", not as isolation. Never commit a key to the repo and never paste one into a chat.

---

## GSD Workflow

Before using Edit / Write / other file-changing tools on substantial work, start through a GSD command so planning artifacts and execution context stay in sync:

- `/gsd:quick` — small fixes, doc updates, ad-hoc
- `/gsd:debug` — investigation / bug fixing
- `/gsd:execute-phase` — planned phase work

Don't make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.

---

<!-- GSD:project-start source:PROJECT.md -->
## Project

**Organon** — a CLI-based Agentic OS for Scientists that automates daily research workflows (literature review, data analysis, paper writing, figure generation, hypothesis testing). Named after Aristotle's collection of works on the tools of correct reasoning — a fitting metaphor for a composable skill-pack architecture that helps scientists think rigorously. Scientists interact via Claude Code slash commands; multi-step workflows compose via skills.

**Core value:** end-to-end research workflows through simple CLI commands — less time on repetitive tasks, more on discovery.

**Constraints:**
- Preserve the skill/hook/cron/MCP architecture — extend, don't rewrite
- CLI-first via slash commands
- Local files as primary data source (CSV, Excel, PDF, images)
- Model-agnostic
- Breadth over depth for v1
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

- **Languages:** Bash (orchestration), Python 3.8+ (skills, data), Markdown (content), YAML (frontmatter + cron), JSON (catalog/settings)
- **Runtime:** Claude Code (agent), Bash 3+, `uv` for Python deps (pip fallback), `brew`/`winget`/`choco` for system deps, `npm` for GSD CLI
- **Skills validate inline** — no centralised test framework
- **Optional deps** (all with graceful fallbacks): `yt-dlp`, Firecrawl SDK, OpenAI API, xAI API, YouTube Data API, Google Gemini
- **Platform:** macOS (tested, LaunchAgents cron dispatcher), Windows (Task Scheduler), Linux (systemd/cron). ~500MB base + ~100MB per skill. Network required for external APIs.
- **Config files:** `.env` (secrets), `.claude/settings.json` (permissions + hooks), `.claude/skills/_catalog/catalog.json` (registry), `CLAUDE.md` / `context/SOUL.md` / `context/USER.md`
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

- **Files:** Python = `snake_case.py`; shell = `kebab-case.sh`; docs = `UPPERCASE.md`; tests = `test_*.py`
- **Code style:** PEP 8 (4-space indent); type hints encouraged; `snake_case` vars + functions; `UPPERCASE` module constants; `PascalCase` dataclasses; private helpers with `_` prefix
- **Errors:** specific exceptions before broad; custom types with attributes; log to stderr with tagged prefixes (`[DEBUG]`, `[ERROR]`); early returns; `sys.exit(0|1)`
- **Shell:** `#!/usr/bin/env bash` + `set -euo pipefail`; `SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"`; detect platform via `uname`; POSIX where possible
- **Imports:** relative with dots inside `lib/` (e.g. `from . import models`); absolute paths via `Path(__file__).resolve()` for script dirs
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

**Pattern:** agent-first (persistent assistant with personality + memory, not a chatbot). Composable skills (independently versioned, self-improving via learnings). Three layers: Agent Identity + Skills Pack + Research Context. Multi-tenant ready. Continuous learning via feedback loop.

**Layers:**
- **Agent Identity** — `context/` — SOUL, USER, memory, learnings. Foundation; loaded by the heartbeat at session start.
- **Skills Pack** — `.claude/skills/` — category-prefixed folders + `_catalog/`. Reads identity + research context + external services.
- **Research Context** — `research_context/` — profile, preferences, artifacts index. Reads by most `sci-*` skills.
- **Orchestration** — `CLAUDE.md` (heartbeat + routing), `cron/`, `scripts/`. Routes user requests and runs background jobs.
- **Outputs** — `projects/{category}/` for single tasks, `projects/briefs/{name}/` for planned/GSD projects.

**Entry points:**
- **Session start** → heartbeat (above) → auto-runs `/lets-go`
- **Skill routing** → CLAUDE.md Task Routing section → match trigger → print notice → execute
- **Built-ins** → `scripts/{add,remove,list}-skill.sh`, `scripts/add-client.sh`, `scripts/memory-search.py`
- **Cron dispatcher** → `scripts/run-crons.sh` every 60s via launchd/Task Scheduler → parse `cron/jobs/*.md` → run headless `claude -p`

**Data flow:**
- `context/memory/{date}.md` — numbered session blocks written incrementally, finalised by `meta-wrap-up`
- `context/learnings.md` — per-skill feedback accumulates across sessions
- `research_context/*.md` — versioned, never auto-overwritten; refresh prompt at 30 days
- `cron/status/*.json` + `cron/logs/*.log` — per-job run state

**Error handling:** missing context → graceful degradation (never gate); no matching skill → explicit notice + choice (find/build or handle with base knowledge); missing API key → documented fallback; malformed memory → log + continue.
<!-- GSD:architecture-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` — do not edit manually.
<!-- GSD:profile-end -->
