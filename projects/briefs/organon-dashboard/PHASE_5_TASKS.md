---
project: organon-dashboard
status: tactical-ready
phase: 5
created: 2026-05-06
parent_plan: PLAN.md
siblings: PHASE_1_TASKS.md, PHASE_2_TASKS.md, PHASE_3_TASKS.md, PHASE_4_TASKS.md
scope: /draft/{slug} workspace — three-pane manuscript editor with live preview (PLAN §3 Phase 5)
out_of_scope: Phase 6.
---

# Organon Dashboard — Phase 5 Tactical Plan

Bridge between PLAN.md and code, for **Phase 5 only**. Mirrors P1–P4 shape. Phases 1–4 shipped + dogfooded before Phase 5 starts.

## Table of Contents

1. [Phase 5 scope recap](#1-phase-5-scope-recap)
2. [Tactical decisions](#2-tactical-decisions)
3. [Repository layout](#3-repository-layout)
4. [Atomic task list (T01–T38)](#4-atomic-task-list)
5. [Artifact JSON schemas](#5-artifact-json-schemas)
6. [API contracts](#6-api-contracts)
7. [Component prop contracts](#7-component-prop-contracts)
8. [npm dependencies](#8-npm-dependencies)
9. [Dev-setup runbook](#9-dev-setup-runbook)
10. [Phase 5 acceptance gate](#10-phase-5-acceptance-gate)

---

## 1. Phase 5 scope recap

Seven deliverables from PLAN §3 Phase 5:

1. `/draft/{slug}` workspace: section list (left), markdown editor (center), live preview (right).
2. Section types: title, abstract, introduction, methods, results, discussion, references. Each is a card with status (draft / reviewed / final).
3. Editor: textarea with figure-embed shortcuts. `\fig{fig-id}` autocompletes from /figures; the figure renders inline both in editor and preview.
4. Live preview: full manuscript with embedded figures, citations resolved, figure numbering automatic.
5. Section-level actions: "rewrite for clarity" (sci-writing), "tighten", "check claims", "humanize" (tool-humanizer).
6. Bibliography auto-generated from saved papers used in `\cite{paper-id}` blocks.
7. Export: Markdown, PDF (Pandoc), HTML (Marp), Substack (`tool-substack`), DOCX (Pandoc).

---

## 2. Tactical decisions

| # | Decision | Choice | Rationale |
|---|---|---|---|
| D1 | **Section as the unit of edit** | Each section is a separate file at `<projectPath>/manuscripts/{doc_slug}/sections/{section_id}.md`. Manuscript metadata at `manuscript.json`. Editor edits one section at a time; you cannot select across sections. | PLAN §6.6 (1). Keeps live preview deterministic + scopes AI rewrite operations. |
| D2 | **Live preview rendering** | Client-side via `markdown-it` + `markdown-it-katex` + custom plugins for `\fig{}` + `\cite{}`. Server-side Pandoc only at export time. | PLAN §7 Q2 default. Snappy + offline-capable for editing; Pandoc is an export-time concern. |
| D3 | **Embed shortcuts** | `\fig{fig-id}` resolves to a figure card with version=main, embedded as `<img src=...>` + auto-numbered figure caption (Fig. 1, Fig. 2, ...). `\cite{paper-id}` resolves to inline (Author, Year) + adds to bibliography. Renumbering happens at preview/export time, never persisted into source. | PLAN §6.6 (3, 4). |
| D4 | **Editor stack** | Plain `<textarea>` with monospace font + scroll-sync to preview. No Monaco / no CodeMirror in Phase 5; can land in v0.3 polish. | Smallest dependency surface. The preview is the rendered view; the editor doesn't need rich syntax highlighting to be useful. |
| D5 | **Section action UX** | Each action (rewrite / tighten / check claims / humanize) fires `sci-writing` (or `tool-humanizer`) via `/api/execute` with the section text + active-project context. Skill emits `_artifact: section-diff` (transient SSE only, NOT persisted). UI shows diff view; user accepts or rejects. Accept → writes new section content + bumps version. | PLAN §6.6 (5, 6). Diff-and-accept matches the reproducibility-is-opinionated principle. |
| D6 | **Bibliography auto-generation** | At preview AND export time, scan all sections for `\cite{paper-id}`, dedupe, resolve from the project library (P1 `lib/lit/library.ts`), generate BibTeX block + in-text reference list. No manual bib management. | PLAN §6.6 (4). Single source of truth. |
| D7 | **Export pipeline** | Markdown source is canonical. PDF via Pandoc (`pandoc -f markdown -t pdf`). HTML via Marp (slide / reading). Substack via `tool-substack`. DOCX via Pandoc (`pandoc -f markdown -t docx`). All export via `/api/draft/[slug]/export` with `format=pdf|html|substack|docx`. | PLAN §6.6 export pipeline. Pandoc is the workhorse. |
| D8 | **Section status state machine** | `draft` (default) → `reviewed` → `final`. User-driven; no auto-promotion. UI shows colored pill per section in the section list. | Matches the manuscript-mental-model researchers already have. |
| D9 | **Manuscript metadata** | `manuscript.json` carries title, authors, target_journal, citation_style ("apa" / "nature" / "ieee" / "vancouver"), section ordering (array of section_ids), and a `linked_artifacts` map for fast lookup of all `\fig{}` + `\cite{}` references. | The linked_artifacts cache lets the export step skip the parse-all-sections step on every export. Refreshed on save. |
| D10 | **Out of scope** | Collaborative editing, comments, track changes, journal-specific style sheets beyond the four cited above, LaTeX direct editing, image upload from drafting (use /figures workspace). | Defer to v0.3+. Plenty of value at single-user single-document Phase 5. |

---

## 3. Repository layout

```
src/
├── app/
│   ├── draft/page.tsx                          # T13 — manuscript list (project-scoped)
│   ├── draft/[slug]/page.tsx                   # T14 — single manuscript editor
│   └── api/draft/
│       ├── [slug]/
│       │   ├── route.ts                        # T28 — get/patch manuscript metadata
│       │   ├── sections/route.ts               # T29 — list/create sections
│       │   ├── sections/[section_id]/route.ts  # T30 — get/patch/delete one section
│       │   ├── action/route.ts                 # T31 — fire section action via /api/execute
│       │   └── export/route.ts                 # T35 — Pandoc/Marp/Substack
│       └── new/route.ts                        # T27 — create new manuscript
├── components/draft/
│   ├── draft-list.tsx                          # T13 — manuscript list page
│   ├── manuscript-workspace.tsx                # T14 — composes 3 panes; client
│   ├── section-list.tsx                        # T15 — left pane
│   ├── section-row.tsx                         # T16 — one entry in section list
│   ├── status-badge-section.tsx                # T17 — draft / reviewed / final pill
│   ├── markdown-editor.tsx                     # T18 — center pane textarea + autocomplete
│   ├── embed-autocomplete.tsx                  # T19 — \fig + \cite popover
│   ├── live-preview.tsx                        # T22 — right pane markdown-it render
│   ├── figure-embed.tsx                        # T20 — inline figure renderer
│   ├── citation-inline.tsx                     # T21 — (Author, Year) inline ref
│   ├── bibliography.tsx                        # T23 — appended to preview + export
│   ├── action-bar.tsx                          # T24 — rewrite / tighten / check / humanize
│   ├── diff-view.tsx                           # T25 — accept/reject panel
│   └── export-menu.tsx                         # T26 — PDF/HTML/Substack/DOCX
└── lib/draft/
    ├── store.ts                                # T07 — manuscript + section CRUD
    ├── parse.ts                                # T08 — extract \fig + \cite refs
    ├── render.ts                               # T09 — markdown-it pipeline
    ├── numbering.ts                            # T10 — figure + reference auto-numbering
    ├── bib.ts                                  # T11 — paper → BibTeX (reuses P1 bibtex.ts) + APA/Nature/IEEE/Vancouver formatters
    └── slug.ts                                 # T07 — manuscript slug allocator
```

---

## 4. Atomic task list

38 tasks.

### 4.1 Track A — Bootstrap (T01–T03)

| ID | Task | Effort | Risk |
|---|---|---|---|
| **T01** | README append. | S | 🟢 |
| **T02** | Phase 4 gate confirmation. | S | 🟢 |
| **T03** | Forward-compat parser test for `_artifact: section-draft` + `section-diff`. | S | 🟢 |

### 4.2 Track B — Artifact protocol v5 extensions (T04–T06)

| ID | Task | Effort | Risk |
|---|---|---|---|
| **T04** | Refine `lib/artifacts/types.ts` for concrete `SectionDraftArtifact` + `SectionDiffArtifact`. | M | 🟢 |
| **T05** | Extend persister: `section-draft → saveSection()`; `section-diff → no-op` (transient only). | S | 🟢 |
| **T06** | Extend renderer: `section-draft → <MarkdownEditor>` (when received from skill). | S | 🟢 |

### 4.3 Track C — Manuscript storage (T07–T11)

| ID | Task | Effort | Risk |
|---|---|---|---|
| **T07** | `lib/draft/store.ts` + `slug.ts`: `listManuscripts(projectPath)`, `createManuscript(projectPath, title)`, `getManuscript(projectPath, slug)`, `updateManuscript(...)`, `listSections(projectPath, slug)`, `getSection(...)`, `saveSection(...)`, `deleteSection(...)`. Atomic writes; lazy dir create. | L | 🟡 |
| **T08** | `lib/draft/parse.ts` — extract `\fig{...}` and `\cite{...}` refs from markdown. Returns `{figures: string[], citations: string[]}`. | M | 🟢 |
| **T09** | `lib/draft/render.ts` — markdown-it pipeline with custom rules for `\fig` + `\cite`. Returns HTML + extracted-refs metadata. | L | 🟡 |
| **T10** | `lib/draft/numbering.ts` — assigns Fig. 1 / Fig. 2 / [1] / [2] in source order across all sections. Pure function from `{sections, ordering, citation_style}` to `{figureNumbers, citationNumbers}`. | M | 🟢 |
| **T11** | `lib/draft/bib.ts` — reuse P1 `paperToBibtex` + add `formatCitationInText(paper, style)` for APA/Nature/IEEE/Vancouver. | M | 🟢 |

### 4.4 Track D — Workspace UI (T12–T26)

| ID | Task | Effort | Risk |
|---|---|---|---|
| **T12** | `app/draft/page.tsx` — project-scoped manuscript list + "New manuscript" button. | M | 🟢 |
| **T13** | `<DraftList>` — table view of manuscripts (title, # sections, last_modified). | M | 🟢 |
| **T14** | `app/draft/[slug]/page.tsx` (server) + `<ManuscriptWorkspace>` (client) — three-pane composer. | L | 🟡 |
| **T15** | `<SectionList>` — left pane; section types + status pills; reorder via up/down buttons. | M | 🟢 |
| **T16** | `<SectionRow>` — single row; click to switch active section. | S | 🟢 |
| **T17** | `<StatusBadgeSection>` — draft / reviewed / final pill; click to advance. | S | 🟢 |
| **T18** | `<MarkdownEditor>` — center pane textarea with monospace font + scroll-sync. Submits on Cmd+S. | M | 🟢 |
| **T19** | `<EmbedAutocomplete>` — popover on `\fig{` or `\cite{`. Source: figures + library. Tab to insert. | L | 🟡 |
| **T20** | `<FigureEmbed>` — inline figure rendering in preview (via dynamic `<img src=/api/figures/...>`). | M | 🟢 |
| **T21** | `<CitationInline>` — (Author, Year) span; clickable to jump to bibliography. | S | 🟢 |
| **T22** | `<LivePreview>` — right pane; markdown-it render with figure/citation plugins; scroll-synced to editor. | L | 🟡 |
| **T23** | `<Bibliography>` — appended to preview; built from referenced citations via `lib/draft/bib.ts`. | M | 🟢 |
| **T24** | `<ActionBar>` — rewrite / tighten / check claims / humanize buttons; each fires `/api/draft/[slug]/action`. | M | 🟢 |
| **T25** | `<DiffView>` — shows the diff returned by the skill; accept (writes new section content) / reject. | L | 🟡 |
| **T26** | `<ExportMenu>` — dropdown PDF / HTML / Substack / DOCX → calls `/api/draft/[slug]/export`. | M | 🟡 |

### 4.5 Track E — API contracts (T27–T31)

| ID | Task | Effort | Risk |
|---|---|---|---|
| **T27** | `POST /api/draft/new` — create new manuscript with default sections (title, abstract, intro, methods, results, discussion, references). | M | 🟢 |
| **T28** | `GET|PATCH /api/draft/[slug]` — manuscript metadata. | M | 🟢 |
| **T29** | `GET|POST /api/draft/[slug]/sections` — list / create. | M | 🟢 |
| **T30** | `GET|PATCH|DELETE /api/draft/[slug]/sections/[section_id]` — per-section CRUD. | M | 🟢 |
| **T31** | `POST /api/draft/[slug]/action` — fires the requested action (rewrite/tighten/check/humanize) via `/api/execute`; SSE pass-through. | M | 🔴 |

### 4.6 Track F — Skill teaching (T32–T34)

| ID | Task | Effort | Risk |
|---|---|---|---|
| **T32** | `.claude/skills/sci-writing/SKILL.md` — Step 1.5 emits `_artifact: section-draft` (full mode) and `_artifact: section-diff` (rewrite/tighten modes). | L | 🟡 |
| **T33** | Document the dashboard invocation contract — when prompt has `active_project_slug={slug}` AND `manuscript_slug={slug}` AND `section_id={id}` AND `action={rewrite|tighten|check|humanize}`, emit JSON-line artifacts. | M | 🟡 |
| **T34** | `.claude/skills/tool-humanizer/SKILL.md` — emit `_artifact: section-diff` when invoked with the dashboard-contract markers. | M | 🟢 |

### 4.7 Track G — Export pipeline (T35–T36)

| ID | Task | Effort | Risk |
|---|---|---|---|
| **T35** | `POST /api/draft/[slug]/export` — assembles canonical markdown (sections in order + bibliography + figure embeds), shells out to Pandoc / Marp / `tool-substack`. Writes output to `<projectPath>/exports/{date}_{format}.{ext}`. | L | 🔴 |
| **T36** | Pandoc + Marp pre-flight check (`bash scripts/setup-export.sh` — installs `pandoc` + `@marp-team/marp-cli` if missing). Skips silently if both already on PATH. | M | 🟢 |

### 4.8 Track H — Polish + acceptance (T37–T38)

| ID | Task | Effort | Risk |
|---|---|---|---|
| **T37** | Extend `<CommandPalette>` with: `Go to Drafts`, `New manuscript`, `Open manuscript {title}`, action shortcuts. | S | 🟢 |
| **T38** | Phase 5 ship checklist + manual test plan. | M | 🟡 |

**Total: 38 tasks. ~7–9 working days.**

---

## 5. Artifact JSON schemas

### 5.1 `_artifact: section-draft`

```jsonc
{
  "_artifact": "section-draft",
  "schema_version": 1,
  "id": "sect-20260620-3a7c91",
  "manuscript_slug": "glp1-meta-analysis",
  "section_id": "introduction",
  "section_type": "introduction",
  "status": "draft",
  "content_md": "# Introduction\n\nGLP-1 receptor agonists are...",
  "linked_figure_ids": ["fig-20260601-3a7c91"],
  "linked_paper_ids": ["pmid-37889012"],
  "version": 1,
  "library_path": "projects/{slug}/manuscripts/glp1-meta-analysis/sections/introduction.md",
  "updated_at": "2026-06-20T14:23:00.000Z"
}
```

### 5.2 `_artifact: section-diff` (transient — NOT persisted)

```jsonc
{
  "_artifact": "section-diff",
  "schema_version": 1,
  "manuscript_slug": "glp1-meta-analysis",
  "section_id": "introduction",
  "action": "rewrite",                           // "rewrite" | "tighten" | "check" | "humanize"
  "before": "...original markdown...",
  "after": "...rewritten markdown...",
  "rationale": "Tightened by 18%; preserved all citations + claims.",
  "warnings": []
}
```

The diff is shown in the UI; user accepts (→ writes via `section-draft` patch) or rejects (→ discard).

---

## 6. API contracts

### 6.1 `POST /api/draft/new`

`{project, title, target_journal?, citation_style?}` → returns new manuscript with default sections + slug.

### 6.2 `GET|PATCH /api/draft/[slug]`

Manuscript metadata: title, authors, target_journal, citation_style, ordering, section status map.

### 6.3 `GET|POST /api/draft/[slug]/sections`

List → array of `SectionDraftArtifact`. POST → create new section.

### 6.4 `GET|PATCH|DELETE /api/draft/[slug]/sections/[section_id]`

Section content + status. PATCH accepts content_md, status changes, linked_figure_ids edits.

### 6.5 `POST /api/draft/[slug]/action`

`{section_id, action: "rewrite"|"tighten"|"check"|"humanize"}` → SSE; skill emits `_artifact: section-diff`. Client renders diff view + on accept patches the section.

### 6.6 `POST /api/draft/[slug]/export`

`{format: "pdf"|"html"|"substack"|"docx"}` → returns `{path: "..."}` + the file is also auto-downloaded.

---

## 7. Component prop contracts

(Compact form; full TypeScript definitions assembled at implementation time.)

- `<DraftList>(props: {manuscripts: ManuscriptMeta[]; onOpen, onCreate})`
- `<ManuscriptWorkspace>(props: {project, slug, manuscript, sections, library, figures})`
- `<SectionList>(props: {sections, activeSectionId, onSelect, onReorder})`
- `<MarkdownEditor>(props: {content, onChange, onSave, library, figures})`
- `<LivePreview>(props: {sections, ordering, library, figures, citation_style})`
- `<ActionBar>(props: {onRewrite, onTighten, onCheck, onHumanize, isRunning})`
- `<DiffView>(props: {diff: SectionDiffArtifact, onAccept, onReject})`
- `<ExportMenu>(props: {slug, onExport: (format) => void})`

---

## 8. npm dependencies

| Package | Version | Why |
|---|---|---|
| `markdown-it` | ^14 | Core markdown render |
| `markdown-it-katex` | ^2 | LaTeX math in preview |

Pandoc + Marp are system tools (installed via `scripts/setup-export.sh`), not npm.

---

## 9. Dev-setup runbook

### 9.1 Prerequisites (delta)

| Tool | Version | Check |
|---|---|---|
| Phase 4 acceptance gate | green | T02 |
| `pandoc` | ≥ 3 | `pandoc --version` |
| `marp-cli` | ≥ 4 | `marp --version` |
| LaTeX (for Pandoc PDF) | TeX Live or BasicTeX | `xelatex --version` |

### 9.2 Smoke test

1. Create manuscript "GLP-1 meta-analysis" → 7 default sections.
2. Edit Introduction → preview renders within 200 ms.
3. Embed `\fig{fig-20260601-...}` in Methods → preview shows the figure with "Fig. 1" caption.
4. Embed `\cite{pmid-...}` ×3 in Results → preview shows (Author, Year) inline; bibliography appears at bottom with 3 entries.
5. ActionBar → "tighten" Discussion → diff lands within 30 s; accept → section content updates.
6. Export → PDF → file appears in `<projectPath>/exports/` and auto-opens.
7. Export → Substack → draft created on Substack (or noop if `tool-substack` keys missing).

---

## 10. Phase 5 acceptance gate

- [ ] Manuscript with 5 sections, embedded 3 figures, cited 12 papers from library.
- [ ] Live preview shows figure numbering (Fig. 1, Fig. 2, Fig. 3) + reference list compiled.
- [ ] Edit Section 3 paragraph 2 → preview updates within 1 s with new text + figures still in place.
- [ ] "Rewrite for clarity" on Section 3 → diff view; accept or reject.
- [ ] Export to PDF → file in `projects/{slug}/exports/{date}_manuscript.pdf`, opens in new tab.
- [ ] All Phase 1–4 workspaces still functional.
- [ ] `npm run build` + typecheck exit 0.
- [ ] Smoke test §9.2 passes.

After ticking: dogfood ≥ 1 week, then plan Phase 6.

---

*End of Phase 5 tactical plan.*
