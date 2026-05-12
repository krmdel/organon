---
project: organon-dashboard
status: planning
level: 2
created: 2026-05-06
reference_implementation: /Users/keremdelikoyun/Projects/business-os/projects/briefs/agentic-os-dashboard
---

# Organon Dashboard — Implementation Plan

A scientist-facing UI layer for Organon. Lets researchers run literature search, hypothesis generation, data analysis, image generation, and manuscript drafting through a visual dashboard instead of the CLI, with task-specific workspaces, interactive editing on images and articles, and persistent project state.

This plan builds on the existing **AgenticOS dashboard** at `business-os/projects/briefs/agentic-os-dashboard/`, which already has the core mechanics (skill discovery, SSE-streamed `claude -p` execution, run logging, usage tracking, multi-business scope) but is not yet specialized for science.

---

## 1. Top-line recommendation

**Build a sister dashboard at `scientific-os/projects/briefs/organon-dashboard/`** (NOT extend business-os in place). Reasons:

1. **Domain modeling diverges fast.** Business workflows surface KPIs (revenue, conversion, churn). Science workflows surface objects (papers, hypotheses, datasets, figures, manuscripts) with their own relationships. A shared dashboard accumulates conditional logic that nobody wants to maintain.
2. **Different output discipline.** Science outputs need bibliography, figure numbering, reproducibility metadata. Business outputs need branding, tone, audience targeting. The persistence schemas don't compose.
3. **Reuse the architecture, not the code.** Copy the Next.js 16 + App Router + filesystem-only + SSE-streaming pattern, *not* the same repository. ~70% of `lib/` (skills, runs, claude-runner, usage) ports directly with minimal changes; ~30% (businesses → projects, KPIs → research metrics) gets rewritten.
4. **Multi-domain later is easier than de-mixing now.** If you eventually want one dashboard that serves both, build the second one first, find what's actually shared, then extract a common kernel.

The plan below assumes the sister-dashboard route. Variants for the in-place-extend path are noted where they materially differ.

---

## 2. Architecture overview

### 2.1 Tech stack (inherit from AgenticOS)

| Layer | Choice | Rationale |
|---|---|---|
| Framework | Next.js 16 App Router | Same as reference; SSR + Route Handlers + RSC for first-paint research dashboards |
| React | 19 | Same |
| Styling | Tailwind v4 | Same. **Add shadcn/ui** for v0.2 — researcher dashboards need richer components (tables, drawers, command-palette) than vanilla Tailwind comfortably handles |
| Type system | TypeScript 5 | Same |
| State | React hooks → **TanStack Query** in v0.2 | Hooks are fine for v0.1; TanStack Query becomes essential when we have lit search, hypothesis, data analysis all polling and caching independently |
| Data layer | Filesystem + JSONL | Same v0.1; add SQLite (better-sqlite3) in v0.2 for lit search index, hypothesis history, and figure metadata where filesystem queries get expensive |
| Auth | None (local-only) v0.1 | Same. Add Clerk or NextAuth in v0.3 if multi-user / remote deploy is needed |
| Skill execution | SSE-streamed `claude -p` | Same proven pattern |
| Image storage | `projects/{slug}/figures/` + symlinks into dashboard `public/` | Cleanest for in-dashboard rendering without a CDN |

### 2.2 Repo location

```
scientific-os/projects/briefs/organon-dashboard/
├── brief.md                    # 1-page summary (separate task)
├── PLAN.md                     # this file
├── package.json
├── next.config.ts
├── tsconfig.json
├── tailwind.config.ts
├── public/
│   └── figures/                # symlinks to project figure outputs
└── src/
    ├── app/
    │   ├── layout.tsx          # root shell: sidebar + topbar
    │   ├── page.tsx            # home: project picker + activity overview
    │   ├── lit/page.tsx        # literature research workspace
    │   ├── hypothesis/page.tsx # hypothesis + council workspace
    │   ├── data/page.tsx       # data + statistical analysis workspace
    │   ├── tools/page.tsx      # ToolUniverse browser + skill catalog
    │   ├── figures/page.tsx    # image + plot generation workspace
    │   ├── draft/page.tsx      # manuscript drafting workspace
    │   ├── crons/page.tsx      # cron / scheduled jobs (deferred)
    │   ├── runs/page.tsx       # run history + drill-down (deferred)
    │   └── api/
    │       ├── projects/route.ts
    │       ├── skills/route.ts
    │       ├── runs/route.ts
    │       ├── usage/route.ts
    │       ├── execute/route.ts          # SSE-stream skill execution
    │       ├── lit/search/route.ts       # paper-search wrapper
    │       ├── lit/library/route.ts      # saved-papers CRUD
    │       ├── hypothesis/[id]/route.ts  # hypothesis history
    │       ├── data/load/route.ts        # CSV/Excel loader
    │       ├── data/analyze/route.ts     # stats + plot generation
    │       ├── tools/route.ts            # ToolUniverse catalog
    │       ├── images/generate/route.ts  # viz-nano-banana wrapper
    │       ├── images/edit/route.ts      # regional inpaint
    │       ├── draft/[slug]/route.ts     # manuscript CRUD
    │       └── crons/route.ts            # cron registry
    ├── components/
    │   ├── shell/
    │   │   ├── sidebar.tsx               # left nav with workspace links
    │   │   ├── topbar.tsx                # project selector + cmd palette
    │   │   └── command-palette.tsx       # Cmd+K to trigger any skill
    │   ├── lit/
    │   │   ├── search-bar.tsx
    │   │   ├── paper-card.tsx
    │   │   ├── paper-detail.tsx
    │   │   ├── library-panel.tsx
    │   │   └── bibtex-export.tsx
    │   ├── hypothesis/
    │   │   ├── hypothesis-form.tsx
    │   │   ├── council-fanout.tsx        # 3-persona side-by-side
    │   │   └── hypothesis-history.tsx
    │   ├── data/
    │   │   ├── file-uploader.tsx
    │   │   ├── dataframe-preview.tsx
    │   │   ├── stat-test-picker.tsx
    │   │   └── plot-renderer.tsx
    │   ├── images/
    │   │   ├── prompt-form.tsx
    │   │   ├── image-canvas.tsx          # mark-region canvas
    │   │   ├── mask-tools.tsx            # circle/lasso/box drawing
    │   │   └── regenerate-controls.tsx
    │   ├── draft/
    │   │   ├── manuscript-editor.tsx
    │   │   ├── section-card.tsx
    │   │   ├── figure-embed.tsx
    │   │   └── live-preview.tsx
    │   └── primitives/
    │       └── (shadcn-installed components)
    └── lib/
        ├── projects.ts                   # discover Organon projects
        ├── skills.ts                     # SAME as agentic-os
        ├── runs.ts                       # SAME pattern, different path
        ├── usage.ts                      # SAME
        ├── claude-runner.ts              # SAME
        ├── lit/                          # paper-search MCP wrapper
        ├── hypothesis/                   # sci-hypothesis + sci-council wrappers
        ├── data/                         # sci-data-analysis wrapper
        ├── images/                       # viz-nano-banana wrapper + masking
        ├── draft/                        # sci-writing wrapper
        └── crons/                        # cron registry reader
```

### 2.3 Data model

The dashboard's mental model is **Project → Workspace → Artifact**.

- **Project** = a research effort with its own scope, context, and outputs. Maps to `projects/{slug}/` in the Organon repo. Examples: `cancer-genomics-survey`, `drug-discovery-llm-eval`.
- **Workspace** = a task-specialized view onto the project. There's one workspace per major scientific verb: lit, hypothesis, data, tools, figures, draft.
- **Artifact** = a typed output that lives in the project: a saved paper, a hypothesis card, a dataset, a generated figure, a manuscript section.

This differs from AgenticOS, which has only Business → Skill → Run. Adding the Workspace layer is what makes the dashboard *feel* scientific rather than generic-agent.

### 2.4 Skill output discipline

A critical change from AgenticOS: skills must **emit structured artifacts**, not just stream stdout into a textarea. The dashboard renders text differently than a paper card differently than a figure differently than a dataframe.

**Convention: skills write a manifest as their last output line.**

```json
{"_artifact": "paper", "id": "PMC10247892", "title": "...", "abstract": "...", "year": 2024, "doi": "10.xxx/yyy", "path": "projects/{slug}/papers/PMC10247892.json"}
{"_artifact": "figure", "id": "fig-2-pca", "kind": "plot", "format": "png", "path": "projects/{slug}/figures/fig-2-pca.png", "caption": "...", "data_source": "..."}
{"_artifact": "hypothesis", "id": "hyp-001", "claim": "...", "evidence_for": [...], "evidence_against": [...], "tests_required": [...]}
```

Dashboard parses the SSE stream, looks for `_artifact` keys, dispatches each to the right renderer + persistence path. Plain stdout still streams to the run log.

**Migration path:** v0.1 just renders raw stream like AgenticOS. v0.2 adds the artifact protocol and rewires renderers. Skills update incrementally — each skill that opts in gets the rich UI for its outputs.

---

## 3. Phased rollout

Six phases, ~2 weeks each at moderate pace. Phase 1 is the MVP that already adds value over the CLI.

### Phase 1 — Skeleton + Lit Research workspace (MVP)
**Why this phase first:** literature search is the most CLI-painful workflow (lots of paste-the-paper-back-and-forth) and the easiest to demo to a non-technical scientist. It also shapes the artifact protocol for later workspaces.

**Deliverables:**
1. Repo bootstrapped from AgenticOS, ported `lib/skills.ts`, `lib/runs.ts`, `lib/usage.ts`, `lib/claude-runner.ts` with `business → project` rename.
2. `Project` type + `lib/projects.ts` discovery (scan `projects/`).
3. App shell: sidebar with Lit / Hypothesis / Data / Tools / Figures / Draft / Crons / Runs links. Top bar with project picker + Cmd+K palette.
4. `/lit` workspace: search bar, paper card list, paper detail drawer, library panel (saved papers), BibTeX export button.
5. Wired to `sci-literature-research` skill via `/api/lit/search`. Saved papers persist to `projects/{slug}/papers/`.
6. Skill output protocol v1: paper artifacts emitted as JSON lines.

**Acceptance:**
- Researcher types "GLP-1 obesity meta-analysis" into search bar.
- Within 30s, ≥10 paper cards render with title, authors, year, abstract preview.
- Click a card → drawer shows full abstract, DOI, citation count, link to full text.
- "Save to library" on 3 cards → `projects/{slug}/papers/` has 3 JSON files.
- "Export BibTeX" downloads a valid `.bib` for the saved set.

### Phase 2 — Hypothesis + Council workspace
**Why next:** hypothesis is the verbal-thinking step researchers most often skip with rigor. The council fan-out (3 personas, side-by-side) is also the most visually distinctive feature in the plan — good demo material.

**Deliverables:**
1. `/hypothesis` workspace: hypothesis form (claim + supporting refs from library), "Generate" button → fans out to 3 personas (Gauss / Erdős / Tao or domain-tuned set).
2. Side-by-side persona panels render each one's critique + counter-evidence + suggested experiments.
3. "Reconcile" button → writes a synthesis card: agreed claim + open questions + experiment design.
4. Hypothesis cards persist to `projects/{slug}/hypotheses/{id}.json` with status (open / refuted / supported / archived).
5. Each card shows linked papers (from library) and linked datasets (from /data).
6. Wired to `sci-hypothesis` + `sci-council` skills.

**Acceptance:**
- Researcher writes a claim, picks 4 papers from library as supporting evidence.
- Generate → 3 persona panels render in parallel within 60s.
- Each panel has ≥2 substantive critiques (not just "looks good").
- Reconcile → produces a synthesis card with at least one explicit open question.
- Hypothesis history page shows all cards with status filters.

### Phase 3 — Data + Statistical Analysis workspace
**Why next:** data is where scientists currently lose the most time to repetitive Excel/Python workflows. Strong leverage.

**Deliverables:**
1. `/data` workspace: file uploader (CSV / XLSX / JSON / Parquet), drop zone + project file browser.
2. Dataframe preview: first 50 rows, column types, basic stats per column.
3. **Stat test picker:** guided wizard ("comparing two groups? testing for normality? what's your sample size?") → recommends the right test + runs it.
4. Plot picker: histogram, scatter, box, violin, heatmap, PCA, line. Each with editable parameters (x/y, group, color, log scale, etc.) in a side panel.
5. Plot output: PNG + SVG + the underlying matplotlib/seaborn code, all saved to `projects/{slug}/figures/`.
6. Wired to `sci-data-analysis` + `sci-hypothesis` (for power analysis).

**Acceptance:**
- Upload a CSV → 50-row preview within 5s, column types correctly inferred.
- "Compare control vs treatment" wizard → recommends t-test or Mann-Whitney based on normality check, runs it, shows result + interpretation in plain English.
- Plot picker → histogram with editable bins → renders within 3s, saved to project.
- All generated code is recoverable from the project (so a researcher can paste it into their own notebook).

### Phase 4 — Image Generation + Interactive Editing
**Why next:** the user explicitly called out the "circle a region, regenerate just that part" UX. This is the most differentiated feature in the plan and the one that turns the dashboard from "skill launcher" into "creative tool."

**Backend split (decided 2026-05-06 after FAL recon):**

| Operation | Backend | Cost | Why this one |
|---|---|---|---|
| Primary text-to-image generation | **Gemini 3 Pro Image** (current `viz-nano-banana`) | ~$0.04/img at 1K | Best text rendering for scientific figures (axis labels, formulas, annotations); existing 6 styles + 6 sci sub-styles already tuned; marginal cost vs FAL alternatives |
| Regional inpainting / mask-based edit | **FAL FLUX.1 [pro] Fill** (`fal-ai/flux-pro/v1/fill`) | $0.05/megapixel | Native mask-input REST API; SOTA inpainting quality in 2026; Gemini doesn't expose mask-based editing at all |

Architecture pattern: lift-and-shift `lib/fal.py` from business-os (`/Users/keremdelikoyun/Projects/business-os/.claude/skills/ops-media-pipeline/lib/fal.py`) into Organon. Register only `flux-pro-fill` initially — defer the rest of FAL's 14-model registry until Organon actually needs video, character LoRAs, or Seedream-style ref-locked editing.

**Deliverables:**
1. `/figures` workspace: prompt form + style picker (scientific / notebook / comic / color / mono / technical — matching `viz-nano-banana` styles).
2. Generated image renders in a canvas component.
3. **Mask tools:** circle / freehand lasso / rectangle. User draws on canvas → mask is captured as PNG with alpha channel + downsampled to match the source image dimensions.
4. **Regional regenerate:** "Change just this part" with a new prompt for the masked region. Sends original image + mask + new prompt to the inpaint endpoint.
5. **Dual-backend skill wiring:**
   - `viz-nano-banana --mode generate` (existing) → Gemini 3 Pro Image
   - `viz-nano-banana --mode edit --image X.png --mask Y.png --prompt "..."` (new) → routes to FAL FLUX.1 [pro] Fill via the ported `lib/fal.py`
6. **Inpainting API:** `/api/images/edit` accepts `{base_image, mask, prompt, project, fig_id}`. Validates mask dimensions match base image, uploads both to FAL's media URL service, calls FLUX Fill, persists result + version metadata to `projects/{slug}/figures/{fig-id}/v{N}.png`.
7. Version history per figure: every generate / edit creates a new version, rendered in a thumbnail strip. Click any thumbnail to revert. Each version stores: prompt, mask (if edit), backend, cost in cents, parent version, created timestamp.
8. "Lock figure" button → freezes the version, generates the caption + alt text via `sci-writing`.

**Open questions resolved this phase (none remaining for backend choice):**
- ~~Which image model handles regional inpainting cleanly~~ → **FAL FLUX.1 [pro] Fill** (decision 2026-05-06)

**Template compatibility note:** the existing 6 styles + 6 sci sub-styles in `viz-nano-banana/references/` are **Gemini-tuned prompts** and stay Gemini-only. They do NOT 1:1 transfer to FLUX. For inpainting we don't reuse them — the user marks a region and provides only the change description ("make this protein look more like a clamp"). Templates would only matter if we later add FAL as a primary text-to-image backend, which is out of scope until quality justifies the prompt-retune cost (~3 days × 36 templates).

**Acceptance:**
- Generate "schematic of CRISPR Cas9 binding to target DNA, scientific style" → image renders within 30s.
- Draw a lasso around the Cas9 protein region → "make it look more like a clamp" → only that region changes; rest is preserved within visual tolerance.
- Version history shows all 3+ versions; click an old version → main canvas reverts.
- "Lock + caption" → caption includes the regenerated detail.

### Phase 5 — Manuscript Drafting workspace with live preview
**Why next:** drafting is where everything comes together. By this point lit, hypothesis, data, and figures are all working — drafting wires them into a single document.

**Deliverables:**
1. `/draft/{slug}` workspace: section list (left), editor (center), live preview (right).
2. Section types: title, abstract, introduction, methods, results, discussion, references. Each section is a card with status (draft / reviewed / final).
3. Editor: textarea (markdown) with figure-embed shortcuts. `/fig-2` autocompletes to the figure card from the figures workspace; the figure renders inline both in editor and preview.
4. Live preview: full manuscript with embedded figures, citations resolved (from library), figure numbering automatic.
5. Section-level actions: "rewrite for clarity" (sci-writing), "tighten" (sci-writing), "check claims" (sci-writing review mode), "humanize" (tool-humanizer).
6. Bibliography auto-generated from saved papers used in `\cite{...}` blocks.
7. Export: Markdown, PDF (via Marp or Pandoc), Substack (via tool-substack).

**Acceptance:**
- Create a manuscript with 5 sections, embed 3 figures, cite 12 papers from the library.
- Live preview shows the document with figure numbering (Fig. 1, Fig. 2, Fig. 3) and reference list compiled from library entries.
- Edit Section 3 paragraph 2 → preview updates within 1s with the new text + figures still in place.
- "Rewrite for clarity" on Section 3 → diff view; accept or reject.
- Export to PDF → file in `projects/{slug}/exports/{date}_manuscript.pdf`, opens in a new tab.

### Phase 6 — Tools, Crons, Runs, Usage polish
**Why last:** these are infrastructure-tab features that researchers visit occasionally, not daily. They're important but not story-driving.

**Deliverables:**
1. `/tools` workspace: search-and-trigger interface for the ToolUniverse 2,000+ catalog. Filter by domain (drug, disease, genomics, etc.), favourite tools, run a tool with form-based input.
2. `/crons` workspace: list of scheduled jobs from `cron/jobs/`. Status indicators (last run, next run, failures). One-click enable / disable / run-now.
3. `/runs` workspace: full run history with drill-down. Click a run → see prompt, output, exit code, duration, token cost, linked artifacts.
4. Usage analytics: real charts (replace placeholder SVG) — daily / weekly / monthly view, by skill, by model.
5. Cmd+K command palette: search across everything (papers, hypotheses, figures, sections, skills) with project-scoped filtering.

**Acceptance:**
- ToolUniverse search "BLAST" → shows the BLAST tool with a form (sequence input, database, threshold) → submit → result renders.
- Crons page shows the locally-installed scheduled jobs from `~/Library/LaunchAgents/com.organon.*.plist`.
- Click a 3-day-old run from `/runs` → reproduces the full prompt and output.
- Cmd+K + "fig-2-pca" → jumps directly to that figure in `/figures`.

---

## 4. Cross-cutting features

These cut across all workspaces and need to be designed once.

### 4.1 Project picker

Every workspace operates within a project context. Top-bar dropdown shows all `projects/{slug}/`. Picking one updates URL state (`/lit?project=cancer-genomics-survey`). Project state is persisted via URL params + localStorage fallback.

**New project flow:** "+ New Project" → modal with name + research question + optional `research_context/` import. Creates the directory, scaffolds standard subdirs (`papers/`, `hypotheses/`, `data/`, `figures/`, `manuscripts/`), opens the Lit workspace.

### 4.2 Project context panel (persistent)

Always-visible right-side drawer (collapsible) that shows the current project's:
- 3 most recent papers from library
- 3 most recent hypotheses
- 3 most recent figures
- Word count of all draft sections combined

This panel is the equivalent of "what was I just working on" — turns the dashboard from a tool collection into a workspace.

### 4.3 Skill execution as a transient overlay

When the user triggers any skill (search, generate hypothesis, run analysis, draft section), a transient overlay shows:
- Status (running / streaming / done)
- Live stdout/stderr (collapsible)
- Token usage running total
- Cancel button

When done, the overlay collapses to a small badge in the top-right; clicking it reopens the run log. This replaces the AgenticOS pattern of dedicating the entire main panel to the run output, which doesn't scale when the user is also viewing a paper or editing a draft.

### 4.4 Artifact protocol v1

Documented in section 2.4. Implementation:
- `lib/artifacts.ts` — parser for `_artifact` JSON lines from skill stdout
- `lib/artifacts/persist.ts` — writes each artifact type to its canonical path under `projects/{slug}/`
- `lib/artifacts/render.ts` — type-discriminated renderer (paper, hypothesis, figure, dataset, section)

Every workspace component consumes artifacts via `useArtifacts({ project, type })`.

### 4.5 Cmd+K command palette

Global shortcut. Input field with fuzzy search across:
- All skills (with prefilled prompts)
- All papers in current project
- All hypotheses in current project
- All figures in current project
- All draft sections in current project
- Workspace-switch commands ("Go to Lit", "Go to Drafting")

Built with [cmdk](https://github.com/pacocoursey/cmdk). One of the highest UX-leverage features for power users.

### 4.6 Keyboard discipline

Researchers come from terminal-and-LaTeX backgrounds. Reasonable defaults:
- `Cmd+K` — command palette
- `Cmd+S` — save draft section
- `Cmd+Enter` — submit current form / regenerate
- `Cmd+/` — toggle preview pane
- `j/k` — next/prev item in any list view
- `Esc` — close drawer / exit edit mode

Implemented via `react-hotkeys-hook` or similar.

---

## 5. Researcher UX principles

These are the rules that should keep the design honest as it grows.

1. **The researcher's mental model is the project, not the skill.** Sidebar is workspaces, not skills. Skills are surfaced only when you're doing the verb the skill supports.
2. **Fast feedback over fancy interactions.** A 3-second response that surfaces a real result beats a 30-second fancy animation.
3. **Everything must persist to the project workspace.** If a figure or hypothesis only lives in the dashboard's memory, it's a tool failure. The CLI workflow has been the source of truth; the dashboard is a view onto it.
4. **No modal dialogs for primary work.** Modals are for confirmations and one-line forms. Drafting, editing, generating — all happens in dedicated workspace panes.
5. **Everything has a "show me the code / data" escape hatch.** A scientist must be able to download the underlying CSV, copy the matplotlib code, view the raw skill prompt. Trust requires transparency.
6. **Citations are first-class.** Anywhere a paper is referenced (lit search, hypothesis, draft), the citation is a link back to the library. No copy-paste of bibliographic data.
7. **Reproducibility is opinionated.** Every figure has its data source. Every hypothesis has its supporting papers. Every claim in a draft has its citation. The dashboard shouldn't let you bypass these.
8. **Latency budget.** Search ≤ 30s. Plot generation ≤ 10s. Figure generation ≤ 60s. Draft section rewrite ≤ 30s. Live preview update ≤ 500ms. If we exceed budget, surface progress rather than a spinner.

---

## 6. Per-workspace deep dives

### 6.1 Lit Research workspace (`/lit`)

**Layout:**

```
┌─────────────────────────────────────────────────────────┐
│ [search bar: "GLP-1 obesity meta-analysis"]   [Search]  │
├──────────────────────────────────┬──────────────────────┤
│ Results (12 of 87)               │ Library (24 saved)   │
│                                  │                      │
│ ┌─ Card 1 ───────────────────┐  │ • Wilding 2021 ...   │
│ │ Title, authors, year, DOI  │  │ • Davies 2023 ...    │
│ │ Abstract preview (3 lines) │  │ • [+ Export BibTeX]  │
│ │ [Save] [Open detail]       │  │                      │
│ └────────────────────────────┘  │ Filter: [year][topic]│
│ ┌─ Card 2 ───────────────────┐  │                      │
│ ...                              │                      │
└──────────────────────────────────┴──────────────────────┘
```

**Detail drawer** (slide from right when card clicked):
- Full title, authors with affiliations, year, journal, DOI link, citation count
- Full abstract (formatted)
- Tabs: Abstract / Citations / References / Notes / Linked Hypotheses
- Actions: Save to library, Cite in current draft section, Generate hypothesis from this paper, Add to project context

**Search backends:**
- `paper-search` MCP server (already in Organon) — federated PubMed / arXiv / OpenAlex / Semantic Scholar
- `paperclip` MCP server — full-text 8M+ biomedical papers
- Toggle between abstract-only (broader) and full-text-only (narrower) search

**Library is just `projects/{slug}/papers/{id}.json` files.** No DB needed for v0.1. Switch to SQLite (FTS5 index) when library exceeds ~500 papers per project.

### 6.2 Hypothesis workspace (`/hypothesis`)

**Layout:**

```
┌─────────────────────────────────────────────────────────┐
│ [Hypothesis: "GLP-1 agonists reduce CV mortality..."]   │
│ [Linked papers: 4 from library]      [Generate via 3-persona council] │
├──────────────────────┬──────────────────┬──────────────┤
│ Gauss               │ Erdős            │ Tao          │
│ ──────              │ ─────            │ ───          │
│ • Algebraic critique│ • Probabilistic  │ • Harmonic   │
│ • Counter-evidence  │ • Counter        │ • Counter    │
│ • Suggested test    │ • Suggested test │ • Suggested  │
│                     │                  │              │
│ [Strength: 7/10]    │ [Strength: 4/10] │ [Strength: 6]│
└──────────────────────┴──────────────────┴──────────────┘
[Reconcile → synthesis card]   [Save hypothesis]
```

**Persona set is configurable per domain.** The Gauss/Erdős/Tao set is good for math; for clinical research a useful default would be Skeptic / Methodologist / Domain-expert.

**Synthesis card** (after reconcile): single-page summary of agreed claim, contested points, open questions, and proposed next experiment with sample size.

### 6.3 Data + Statistical Analysis workspace (`/data`)

**Layout:**

```
┌─────────────────────────────────────────────────────────┐
│ [Drop file here, or pick from project]                  │
├──────────────────────────────────────────────────────────┤
│ patient_data.csv   |  1,247 rows × 12 cols              │
│ ┌──────┬──────┬──────┬────────┐                         │
│ │ id   │ age  │ trt  │ outcome│   (preview, 50 rows)    │
│ └──────┴──────┴──────┴────────┘                         │
├────────────────────────┬─────────────────────────────────┤
│ Test picker            │ Plot picker                     │
│ ─────                  │ ─────                           │
│ [Compare 2 groups]     │ [Histogram] [Scatter] [Box]     │
│  → t-test or MWU?      │ [Violin] [Heatmap] [PCA]        │
│ [Test for trend]       │                                 │
│ [Power analysis]       │ x: [age▾]  y: [outcome▾]        │
│                        │ group: [trt▾]                   │
│ [Run]                  │ [Generate]                      │
├────────────────────────┴─────────────────────────────────┤
│ Result: t = 3.42, p = 0.0007, Cohen's d = 0.41           │
│ Plain-language: "Treatment group had higher outcomes... "│
│ [Save to project] [Copy code] [Cite in draft]            │
└──────────────────────────────────────────────────────────┘
```

**Stat test picker is the most-research-friendly feature in this workspace.** It captures researcher intent ("compare two groups") and translates to the right test — including the pre-condition checks (normality, equal variance) that researchers routinely skip.

### 6.4 Tools workspace (`/tools`)

Largely a port of the AgenticOS skills grid but with three additions:
1. **ToolUniverse 2,000+ catalog browser** alongside the local Organon skills. Same UI; tools are just a wider source.
2. **Form-based input** for tools that take structured arguments (e.g., BLAST takes sequence + database). Auto-derived from the tool's JSON schema.
3. **Tool favourites** per project — the 5–10 tools most used in this project pinned at the top.

### 6.5 Figures workspace (`/figures`)

Already covered in detail in Phase 4. Key additions to make explicit:

- **Prompt form pattern matches `viz-nano-banana` Step 3:** style picker is a confirmation gate, not a freeform input.
- **Mask tools UX:** circle / lasso / box are the user-facing options. Internally all of them produce a binary mask as PNG, then upload to FAL FLUX.1 [pro] Fill via the new `--mode edit` path.
- **Dual backend, transparent to user:** the workspace shows one "Generate" and one "Edit selected region" button. The user never picks Gemini-vs-FAL — the dashboard routes by intent. Backend used is logged in version metadata for cost auditing and reproducibility.
- **Versions are first-class:** every generate or edit produces a versioned artifact under `projects/{slug}/figures/{fig-id}/v{N}.png`. The "main" version is a symlink. Researchers can compare versions side-by-side. Each version's sidecar JSON records `{backend, prompt, mask_path?, cost_cents, parent_version, created}` so reproducibility audits don't have to dig through run logs.
- **Caption + alt text generated on lock:** prevents the researcher from skipping accessibility metadata.
- **Cost gate (recommended, not blocking):** show the user "this edit will cost ~$0.05" before firing the FAL call, with a "don't ask again this session" toggle. Inpainting is cheap per call but adds up across iterative edits.

### 6.6 Manuscript Drafting workspace (`/draft/{slug}`)

The most ambitious workspace. Three-pane layout with section list, markdown editor, live preview.

**Critical UX decisions:**

1. **Section as the unit of edit.** You can't edit "the manuscript" as a single document; you edit one section at a time. This keeps the live preview deterministic and the AI rewrite operations scoped.
2. **Live preview is the primary view, not a debug tool.** The researcher should be looking at the preview while typing in the editor. Editor and preview scroll-synced.
3. **Figures embed by ID, not by path.** `\fig{fig-2-pca}` resolves to the linked figure card from the figures workspace, with current version, caption, alt text, and proper numbering. Renumbering happens automatically.
4. **Citations embed by paper ID, not by author-year string.** `\cite{PMC10247892}` resolves from the library. Bibliography auto-generated.
5. **Section actions are scoped:** "rewrite for clarity" only acts on the active section. The user always sees what's being rewritten before accepting.
6. **Diff-and-accept pattern:** every AI rewrite produces a diff. The researcher accepts, rejects, or edits the suggestion. Never auto-applies.

**Export pipeline:** Markdown source is canonical. PDF via Pandoc (academic), HTML via Marp (for reading), Substack via tool-substack (for blog version), DOCX via Pandoc (for collaboration with non-technical co-authors).

---

## 7. Open questions to resolve before / during implementation

Each of these blocks specific phase deliverables and needs a call.

| # | Question | Blocks | Default if unresolved |
|---|---|---|---|
| 1 | ~~Image model for inpainting~~ → **RESOLVED 2026-05-06: FAL FLUX.1 [pro] Fill.** Native mask-input REST API, $0.05/MP, SOTA quality. Gemini stays for text-to-image generation. Architecture lifted from business-os `lib/fal.py`. | ~~Phase 4~~ | n/a |
| 2 | **Live preview rendering — server-side (Pandoc) or client-side (markdown-it + KaTeX)?** | Phase 5 | Client-side for editor preview (snappy), server-side for PDF export only |
| 3 | **Auth in v1 or defer?** | All | Defer. Local-only is fine for the user persona. Add Clerk in v2 if remote/multi-user need surfaces. |
| 4 | **One dashboard for both business-os and Organon, or two?** | All | **Two.** See section 1. Revisit after both are mature. |
| 5 | **Persona set for /hypothesis council** — mathematical (Gauss/Erdős/Tao) or domain-tuned? | Phase 2 | Make it configurable per project; default to Skeptic/Methodologist/Domain-expert; allow swap to math set for math problems. |
| 6 | **SQLite for lit search index — when?** | Phase 1 | Filesystem JSON for v0.1. Add SQLite when search latency exceeds 2s on a typical project library. |
| 7 | **Multi-user / shared projects?** | All | Out of scope for v1. Single-researcher local-only. |
| 8 | **Cron UI design** — replicate macOS Calendar or simple table? | Phase 6 | Simple table (last run, next run, status, actions). Calendar is overkill for ~5–10 jobs. |
| 9 | **Skill versioning / rollback** — does the dashboard show which skill version produced an artifact? | Phase 6 | Yes, but as metadata only. Run history captures the skill SHA. |
| 10 | **MCP integration** — does the dashboard surface MCP tool catalog separately from Organon skills? | Phase 6 | Treat MCP tools as another category in the Tools workspace; same UI. |

---

## 8. Acceptance criteria for v1 ship

The dashboard ships v1 when:

1. A scientist with no CLI knowledge can complete a full research workflow:
   - Create a new project
   - Search and save 10 papers
   - Generate a hypothesis with the 3-persona council
   - Upload a CSV, run a stat test, generate a plot
   - Generate a figure, edit a region, lock it
   - Draft a 5-section manuscript with embedded figures and citations
   - Export the manuscript as PDF
2. All artifacts persist to `projects/{slug}/` and are reproducible from CLI alone.
3. Latency budgets in section 5.8 are met for the typical case.
4. Cmd+K palette navigates to any artifact in any workspace.
5. Each workspace has at least one keyboard shortcut for its primary action.
6. The dashboard runs locally with `npm run dev`, no external services required (beyond what skills already need: API keys for image gen, MCP servers).

---

## 9. Dependencies and integration points

### 9.1 Skills that need updates

Each of these skills needs minor updates to emit artifacts on stdout per the v1 protocol (section 2.4):

| Skill | Change |
|---|---|
| `sci-literature-research` | Emit `_artifact: paper` lines for each result |
| `sci-hypothesis` | Emit `_artifact: hypothesis` for the generated card |
| `sci-council` | Emit `_artifact: persona-critique` per persona panel |
| `sci-data-analysis` | Emit `_artifact: dataframe` (preview) + `_artifact: figure` (plot output) + `_artifact: stat-result` (test outcome) |
| `viz-nano-banana` | Add `--mode edit --image X --mask Y --prompt "..."` flag that routes to FAL FLUX.1 [pro] Fill via ported `lib/fal.py`; existing `--mode generate` stays on Gemini 3 Pro Image; emit `_artifact: figure` with version metadata (backend, prompt, mask path, cost_cents, parent_version) |
| `sci-writing` | Emit `_artifact: section-draft` and `_artifact: section-diff` |

Each update is small (few lines of stdout formatting) and backward-compatible (CLI still works without dashboard).

### 9.2 Cron + MCP integration

- **Cron registry:** `cron/jobs/*.md` files with frontmatter. Dashboard reads this directly (read-only in v1; write/enable/disable in v2).
- **MCP servers:** dashboard does not host MCPs — Organon's `.mcp.json` configures them, and the `claude -p` invocation that the dashboard spawns inherits them. So MCPs Just Work.

### 9.3 Auth and secrets

Same as AgenticOS v0.1: dashboard reads `.env` at project root for any secrets the skills need. No secrets in dashboard's own code or storage.

---

## 10. Recommended next session task

Don't try to implement all six phases in one go. The right entry point:

1. **Ship Phase 1 standalone** (~2 weeks) — bootstrap the repo, port lib/, build the lit-research workspace end-to-end, ship it as v0.1.
2. **Show it to one researcher** (or yourself in a non-launch session) and watch them use it. Adjust before Phase 2.
3. **Phase 2 only after Phase 1 is in real use for ≥1 week.** Real use surfaces the structural problems that planning misses.

A reasonable next session would be: scaffold the repo, port `lib/skills.ts`, `lib/runs.ts`, `lib/usage.ts`, `lib/claude-runner.ts` from AgenticOS with the project rename, and stand up `/lit` page-empty. That alone is one focused session of work and gets you to "I can see the dashboard responds to my project picker" within a few hours.

---

## 11. References

- AgenticOS dashboard reference implementation: `/Users/keremdelikoyun/Projects/business-os/projects/briefs/agentic-os-dashboard/`
- Organon repo (this repo): `/Users/keremdelikoyun/Projects/scientific-os/`
- Organon skills inventory: `.claude/skills/` (~30 skills as of 2026-05-06)
- ToolUniverse: 2,000+ biomedical tools via `sci-tools` skill
- MCP servers: `paperclip`, `paper-search`, `tooluniverse` (per `.mcp.json`)

---

*End of plan.*
