---
project: organon-dashboard
status: tactical-ready
phase: 1
created: 2026-05-06
parent_plan: PLAN.md
scope: Skeleton + /lit literature-research workspace MVP (PLAN section 3 Phase 1)
out_of_scope: Phases 2–6 (see PLAN sections 3.2–3.6). Open questions Q2, Q3, Q4, Q7, Q8, Q9, Q10 (PLAN §7) — defer.
---

# Organon Dashboard — Phase 1 Tactical Plan

This document is the bridge between **PLAN.md** (strategic, locked) and code. PLAN.md is the source of truth for what and why; this document is the source of truth for how, in what order, and to what shape, for **Phase 1 only**.

PLAN.md cited inline as `(PLAN §X.Y)`.

## Table of Contents

1. [Phase 1 scope recap](#1-phase-1-scope-recap)
2. [Tactical decisions resolved this document](#2-tactical-decisions-resolved-this-document)
3. [Repository layout for Phase 1](#3-repository-layout-for-phase-1)
4. [Atomic task list (T01–T48)](#4-atomic-task-list)
   - 4.1 [Track A — Repo bootstrap (T01–T05)](#41-track-a--repo-bootstrap)
   - 4.2 [Track B — Library port (T06–T15)](#42-track-b--library-port)
   - 4.3 [Track C — App shell (T16–T22)](#43-track-c--app-shell)
   - 4.4 [Track D — /lit workspace (T23–T36)](#44-track-d--lit-workspace)
   - 4.5 [Track E — Artifact protocol v1 + persistence (T37–T42)](#45-track-e--artifact-protocol-v1--persistence)
   - 4.6 [Track F — Polish + Phase 1 acceptance (T43–T48)](#46-track-f--polish--phase-1-acceptance)
5. [Artifact JSON schemas](#5-artifact-json-schemas)
6. [API contracts](#6-api-contracts)
7. [Component prop contracts](#7-component-prop-contracts)
8. [npm dependencies (locked versions)](#8-npm-dependencies)
9. [Dev-setup runbook](#9-dev-setup-runbook)
10. [Phase 1 acceptance gate](#10-phase-1-acceptance-gate)

---

## 1. Phase 1 scope recap

Six deliverables from PLAN §3 Phase 1, restated for tactical clarity:

1. Repo bootstrapped from AgenticOS dashboard with the `business → project` rename. Ported lib: `skills.ts`, `runs.ts`, `usage.ts`, `claude-runner.ts`, `paths.ts`, `usage-types.ts`, `cn.ts`. (Track A + B)
2. `Project` type + `lib/projects.ts` discovery scanning `<organon-root>/projects/`. (Track B)
3. App shell: left sidebar (Lit / Hypothesis / Data / Tools / Figures / Draft / Crons / Runs links — only Lit active in Phase 1; rest stubbed). Top bar with project picker + Cmd+K palette. (Track C)
4. `/lit` workspace: SearchBar, paper card list, PaperDetail drawer, LibraryPanel (saved papers), BibtexExport button. (Track D)
5. `/api/lit/search` calling the paper-search source modules; saved papers persist to `projects/{slug}/papers/{paper_id}.json`. (Track D + E)
6. Skill output protocol v1: `_artifact: paper` parser + persister. Wired through `/api/execute` SSE so any skill that emits artifact lines appears in the workspace. (Track E)

**Out of scope (deferred to later phases):** hypothesis workspace, council fan-out, data analysis, image generation, manuscript drafting, cron UI, run history drill-down, usage analytics charts. The sidebar links exist but route to placeholder pages.

---

## 2. Tactical decisions resolved this document

These are decisions that PLAN.md left open at the tactical level. Each is locked here so Phase 1 can ship without further deliberation.

| # | Decision | Choice | Rationale |
|---|---|---|---|
| D1 | **Project discovery rule** | Any non-hidden directory under `<organon-root>/projects/` is a discoverable project, plus a synthetic `__root__` representing the Organon repo itself. Briefs at `projects/briefs/<slug>/` are surfaced as a sub-group in the picker. | Mirrors AgenticOS's `__root__` + `clients/<slug>` pattern; works with the existing arena workspaces (`einstein-arena-*`) which have no brief.md. |
| D2 | **Runs storage path** | Per project: `<projectPath>/.organon/runs/<id>.jsonl`. Synthetic root: `<organon-root>/.organon-dashboard/runs/<id>.jsonl`. | Matches AgenticOS's `.agentic-os/runs/` pattern with project-scoped logs. `.organon/` is reserved for dashboard-internal state per project (parallel to `.planning/`). |
| D3 | **Library storage path** | `<projectPath>/papers/<paper_id>.json` per PLAN §6.1. Paper IDs are deterministic: `pmid-{n}`, `arxiv-{n}`, `openalex-W{n}`, `s2-{hash}`, `paperclip-{id}`. | Matches PLAN §3 acceptance ("3 JSON files"). Filesystem-only is fine until ~500 papers/project (PLAN §7 Q6). |
| D4 | **Search backend wiring** | `/api/lit/search` imports the paper-search modules (`pubmed.ts`, `arxiv.ts`, `openalex.ts`, `semanticscholar.ts`, `code-links.ts`) **directly** from `<organon-root>/mcp-servers/paper-search/src/` via TypeScript path mapping. No MCP roundtrip, no `claude -p` spawn. | The MCP server is just a stdio wrapper around these functions. Importing directly removes a process boundary, keeps latency under the 30s PLAN §5.8 budget, and avoids debugging two stdio bridges. The MCP server stays available for CLI use; we share source. |
| D5 | **Skill execution path** | `/api/execute` (the AgenticOS hero-prompt SSE pattern) stays as the **skill execution** entry point and remains exactly as ported. `/api/lit/search` is a **direct API** (no skill spawn) for the workspace's primary action — search-and-render. | Two channels: the direct API for workspace primary actions (fast, deterministic), the SSE channel for arbitrary skill execution (general-purpose). Future workspaces can add their own direct APIs as needed. |
| D6 | **Artifact protocol v1 surface in Phase 1** | Implemented in `lib/artifacts.ts` (parser) and `lib/artifacts/persist.ts` (writer). Wired through `/api/execute` SSE so any skill emitting `_artifact: paper` lines auto-persists. The `/api/lit/search` direct API also emits artifacts in the same shape so renderers are unified. Only the `paper` artifact type is implemented in Phase 1. | PLAN §2.4 says all workspaces eventually consume artifacts via the same protocol. Implementing the parser now (against one type) means Phase 2 just adds a new `_artifact: hypothesis` discriminator to the same dispatcher. |
| D7 | **Project picker default** | First non-root project alphabetically if any exist, else `__root__`. URL param `?project={slug}` overrides. localStorage `organon.dashboard.lastProject` overrides default but not URL. | URL > localStorage > alpha-default is the standard precedence; lets the user share a deep link without overriding their session preference. |
| D8 | **Cmd+K command palette in Phase 1** | Implemented with `cmdk` package. Phase 1 commands: workspace navigation (`Go to Lit`, etc.) + project switching + skill list (read from `/api/skills`). Library/paper/hypothesis search is deferred to Phase 2 (when there's enough corpus to warrant the search work). | Splits the palette plumbing (which is structural) from the cross-workspace search (which depends on Phase 2+ artifacts). |
| D9 | **Server vs client components** | `app/page.tsx`, `app/lit/page.tsx`, `app/api/**/route.ts` are server components / route handlers. All interactive components in `components/` are `"use client"`. Server components do the initial data load (project list, skills list); client components handle interactivity. | Mirrors AgenticOS exactly. Avoids Next.js 16 RSC pitfalls: any component that imports `node:fs` (lib/projects.ts, lib/runs.ts, lib/usage.ts) must stay server-only. |
| D10 | **Tailwind v4 only, no shadcn in Phase 1** | Phase 1 uses raw Tailwind v4 utility classes only. Shadcn/ui is queued for v0.2 (PLAN §2.1 — "Add shadcn/ui for v0.2"). | One source of truth for styling in Phase 1 keeps the port surface small. Adding shadcn means installing it, picking a theme, and porting any AgenticOS components to its primitives — too much for one phase. |

---

## 3. Repository layout for Phase 1

What gets created. Items marked **[stub]** are placeholder pages with a "Coming in Phase N" message; they exist only to make sidebar links resolve.

```
scientific-os/projects/briefs/organon-dashboard/
├── PLAN.md                             # (exists)
├── PHASE_1_TASKS.md                    # (this file)
├── README.md                           # T03
├── .gitignore                          # T01
├── package.json                        # T01
├── package-lock.json                   # T01 (generated)
├── next.config.ts                      # T01
├── tsconfig.json                       # T02 (paths include mcp-servers/paper-search)
├── postcss.config.mjs                  # T01
├── next-env.d.ts                       # T01 (auto-generated)
├── public/
│   └── (empty in Phase 1)
└── src/
    ├── app/
    │   ├── layout.tsx                  # T18 — root shell
    │   ├── globals.css                 # T18 — Tailwind v4 directives
    │   ├── page.tsx                    # T19 — home: project picker + activity overview (lightweight stub)
    │   ├── lit/page.tsx                # T23 — /lit workspace (server component)
    │   ├── hypothesis/page.tsx         # [stub] T22
    │   ├── data/page.tsx               # [stub] T22
    │   ├── tools/page.tsx              # [stub] T22
    │   ├── figures/page.tsx            # [stub] T22
    │   ├── draft/page.tsx              # [stub] T22
    │   ├── crons/page.tsx              # [stub] T22
    │   ├── runs/page.tsx               # [stub] T22
    │   └── api/
    │       ├── projects/route.ts       # T13
    │       ├── skills/route.ts         # T11
    │       ├── runs/route.ts           # T12
    │       ├── usage/route.ts          # T14
    │       ├── execute/route.ts        # T15 — SSE
    │       ├── lit/search/route.ts     # T29
    │       └── lit/library/route.ts    # T34
    ├── components/
    │   ├── shell/
    │   │   ├── sidebar.tsx             # T20 — workspace links
    │   │   ├── topbar.tsx              # T21 — project picker + Cmd+K trigger
    │   │   └── command-palette.tsx     # T22 — cmdk-driven palette
    │   ├── lit/
    │   │   ├── search-bar.tsx          # T24
    │   │   ├── paper-card.tsx          # T25
    │   │   ├── paper-detail.tsx        # T26 — drawer
    │   │   ├── library-panel.tsx       # T27
    │   │   ├── bibtex-export.tsx       # T28
    │   │   └── lit-workspace.tsx       # T23 — composes the above (client component)
    │   └── primitives/
    │       └── (none in Phase 1)
    └── lib/
        ├── cn.ts                       # T06 — clsx wrapper
        ├── paths.ts                    # T07 — agenticOsRoot → organonRoot
        ├── projects.ts                 # T08 — businesses → projects (D1)
        ├── skills.ts                   # T09 — Organon prefix labels
        ├── runs.ts                     # T10 — .agentic-os → .organon (D2)
        ├── claude-runner.ts            # T15-prep — projectPath/projectSlug rename
        ├── usage.ts                    # T14 — pricing constants kept
        ├── usage-types.ts              # T14 — client-safe mirror
        ├── artifacts/
        │   ├── parser.ts               # T37 — _artifact line extraction
        │   ├── persist.ts              # T38 — write to projects/{slug}/papers/...
        │   ├── render.ts               # T39 — type-discriminated renderer (paper only in P1)
        │   └── types.ts                # T37 — TypeScript schemas (PaperArtifact, etc.)
        ├── lit/
        │   ├── search.ts               # T30 — wraps paper-search modules with dedupe + ranking
        │   ├── bibtex.ts               # T28 — paper → BibTeX entry
        │   └── library.ts              # T34 — read/write papers/{paper_id}.json
        └── env.ts                      # T04 — typed access to ORGANON_ROOT, NCBI_API_KEY, etc.
```

---

## 4. Atomic task list

48 tasks. Each is scoped to ≤ 4 hours. IDs are stable; cross-references use `T##`. "Blocks" means the listed tasks cannot start until this one is done. Tracks A-F can run mostly sequentially; some intra-track parallelism is noted.

**Legend.** Effort: S = ≤1h, M = ≤2h, L = ≤4h. Risk: 🟢 low, 🟡 medium, 🔴 high.

### 4.1 Track A — Repo bootstrap

| ID | Task | Effort | Risk | Depends on | Notes |
|---|---|---|---|---|---|
| **T01** | Initialize Next.js 16 project skeleton in `projects/briefs/organon-dashboard/` | M | 🟢 | — | Run `npx create-next-app@16.2.4 . --typescript --tailwind --app --no-eslint --use-npm --no-src-dir=false` then revise to match the layout in §3. Set `dev` script to port `8769`. Commit lockfile. |
| **T02** | Configure `tsconfig.json` with `@/*` and `@paper-search/*` path aliases | S | 🟢 | T01 | `@paper-search/*` → `../../../../mcp-servers/paper-search/src/*` (relative path resolves under monorepo). Verify TS resolves an import like `import { searchPubMed } from "@paper-search/pubmed"`. |
| **T03** | Write `README.md` with Phase 1 scope summary, dev-setup pointer, port number, link to PLAN.md and this file | S | 🟢 | T01 | One screen. Include `npm run dev` quickstart and a "what's stubbed in Phase 1" callout. |
| **T04** | Create `lib/env.ts` with typed access to `ORGANON_ROOT`, `NCBI_API_KEY`, `OPENALEX_API_KEY`, `S2_API_KEY`, `CLAUDE_BIN` | S | 🟢 | T01 | Reads `process.env`, exports getters that throw on missing required vars (only `ORGANON_ROOT` is required and falls back to derived path). API keys are optional with documented fallback. |
| **T05** | Add `.gitignore` entries: `.next/`, `node_modules/`, `.organon/`, `tsconfig.tsbuildinfo` | S | 🟢 | T01 | Confirms dashboard runs don't pollute git. |

### 4.2 Track B — Library port

Direct ports from AgenticOS with the `business → project` rename. Most of these are mechanical s/businesses?/projects?/g passes plus path adjustments.

| ID | Task | Effort | Risk | Depends on | Notes |
|---|---|---|---|---|---|
| **T06** | Port `lib/cn.ts` verbatim | S | 🟢 | T01 | Copy as-is; same clsx + twMerge pattern. |
| **T07** | Port `lib/paths.ts` → rename `agenticOsRoot()` to `organonRoot()`; CLAUDE.md marker stays the same; `clientsDir()` becomes `projectsDir()` returning `<root>/projects/`; `skillsDir()` unchanged. Replace `AGENTIC_OS_ROOT` env var with `ORGANON_ROOT` | S | 🟢 | T04 | Functional behavior identical, just renamed. |
| **T08** | Write `lib/projects.ts` (replaces AgenticOS `lib/businesses.ts`). | M | 🟡 | T07 | Per D1: scan `<root>/projects/` for non-hidden directories. Synthesize `__root__` entry. Detect briefs subgroup at `projects/briefs/<slug>/`. Return `Project[]` with `{slug, name, path, isRoot, isBrief, briefMeta?}`. Read brief.md frontmatter when present (use the same yaml parser from skills.ts to avoid pulling in a yaml lib). See §5 for `_artifact: project` schema this method emits. |
| **T09** | Port `lib/skills.ts` with Organon category labels | S | 🟢 | T07 | Same parser. Replace CATEGORY_LABELS with `{sci: "Science", ops: "Operations", viz: "Visual", meta: "System / Meta", tool: "Tools"}`. Update `order` array to `["sci", "viz", "ops", "tool", "meta", "other"]` matching CLAUDE.md. |
| **T10** | Port `lib/runs.ts` with `.agentic-os/runs` → `.organon/runs` rename; `business → project` field rename in RunEvent and RunSummary types | S | 🟢 | T07 | Per D2. Logic unchanged. |
| **T11** | Port `/api/skills/route.ts` with `business → project` rename in query param + `resolveBusiness → resolveProject` import | S | 🟢 | T08, T09 | One-line param change. |
| **T12** | Port `/api/runs/route.ts` with rename | S | 🟢 | T08, T10 | One-line param change. |
| **T13** | Write `/api/projects/route.ts` (replaces `/api/businesses/route.ts`) | S | 🟢 | T08 | Returns `{projects: [{slug, name, isRoot, isBrief}]}`. See §6.1. |
| **T14** | Port `lib/usage.ts` and `lib/usage-types.ts` verbatim; rename `/api/usage/route.ts` to use `resolveProject` | M | 🟢 | T08 | Pricing table stays; encoded-cwd-path lookup is identical (`~/.claude/projects/`). Phase 1 surfaces usage in topbar, no charts yet. |
| **T15** | Port `lib/claude-runner.ts` and `/api/execute/route.ts` with `business → project` rename | M | 🟢 | T08, T10 | Important: the SSE format stays exactly the same (`event: stdout\ndata: {...}\n\n`) so Phase 1's lit-workspace can listen for `_artifact: paper` events from the existing skill protocol when the user fires `sci-literature-research` from the hero prompt. |

### 4.3 Track C — App shell

| ID | Task | Effort | Risk | Depends on | Notes |
|---|---|---|---|---|---|
| **T16** | Wire Tailwind v4 globals: design tokens (color tokens for `bg-canvas`, `border-border-dim`, `text-text-dim`, mono font var) | S | 🟢 | T01 | Mirror AgenticOS palette so the visual language carries over. Document tokens in a comment block at top of globals.css. |
| **T17** | Add Geist Sans + Geist Mono via `next/font/google` in `app/layout.tsx` | S | 🟢 | T01 | Verbatim from AgenticOS layout.tsx. |
| **T18** | Build `<html>` shell in `app/layout.tsx`: html.lang, classes (font vars + h-full antialiased), Metadata exports (`title: "Organon Dashboard"`, `description: "Scientist-facing UI for Organon"`). | S | 🟢 | T16, T17 | Output = same shape as AgenticOS layout, retitled. |
| **T19** | Build `app/page.tsx` (home): server component, calls `listProjects()` + `listSkillGroups(initial.path)` + `listRuns(initial.path, 5)` + `runActivityByDay(initial.path, 7)`; renders `<HomeShell>` client component that hosts sidebar + topbar + a "Welcome / pick a workspace" hero panel | M | 🟡 | T08, T09, T10, T20, T21 | Phase 1 home is intentionally minimal — just enough to verify the project picker + skill list refresh. Acceptance UI per PLAN §3. |
| **T20** | Implement `<Sidebar>` component (client) with workspace links: Lit (active), Hypothesis, Data, Tools, Figures, Draft, Crons, Runs (each with placeholder badge for non-Phase-1). Active link state from `usePathname()`. | M | 🟢 | T18 | Pure presentational. Uses `next/link`. See §7.1 for prop contract. |
| **T21** | Implement `<Topbar>` (client): project picker dropdown (driven by `/api/projects`), Cmd+K hint button, project name + brief status badge, last-sync timestamp from usage report | M | 🟡 | T13, T14 | URL state sync per D7. localStorage fallback. See §7.2. |
| **T22** | Implement `<CommandPalette>` (client) with cmdk + react-hotkeys-hook. Phase 1 commands: workspace nav + project switch + skill list (calls `/api/skills`). `Cmd+K` opens; `Esc` closes; arrow keys navigate. | L | 🟡 | T11, T13 | Per D8. Skill items, when picked, populate the home hero prompt (or navigate to the workspace if the skill has one). Cross-corpus search (papers, hypotheses) is OUT of scope this phase. |

After T22 the dashboard renders, the project picker switches projects, the sidebar marks the Lit workspace as primary, and Cmd+K is functional. Stubs for `/hypothesis` etc. are pending T22-stub items below; doing them as one batch.

| **T22-STUB** | Add minimal stub pages at `/hypothesis`, `/data`, `/tools`, `/figures`, `/draft`, `/crons`, `/runs` — each is one server component with a "Coming in Phase N" panel + back-to-Lit link | S | 🟢 | T20 | One file each, ~10 lines. Prevents 404 on sidebar link click. |

### 4.4 Track D — /lit workspace

The MVP feature. PLAN §6.1 has the layout sketch; this section turns it into wired components.

| ID | Task | Effort | Risk | Depends on | Notes |
|---|---|---|---|---|---|
| **T23** | Build `app/lit/page.tsx` (server component): reads project from URL/localStorage default, calls `listLibrary(projectPath)`, renders `<LitWorkspace>` client with initial library | M | 🟢 | T08, T34 | Server-side hydration of saved papers means the panel populates on first paint. |
| **T24** | Implement `<SearchBar>` (client) | M | 🟢 | T18 | Controlled input + Submit button + filter chips (year range, source toggles: PubMed/arXiv/OpenAlex/S2/all). `Cmd+Enter` submits per PLAN §4.6. See §7.3. |
| **T25** | Implement `<PaperCard>` (client) | M | 🟢 | T18 | Receives a `PaperArtifact` (§5.1). Renders title, authors (truncated), year, journal, citations, sources, code-link badge, abstract preview (first ~200 chars). Buttons: `Open detail`, `Save`. See §7.4. |
| **T26** | Implement `<PaperDetail>` drawer (client) | L | 🟡 | T25 | Slide-from-right drawer (Tailwind transform + transition; no Headless UI in Phase 1). Tabs: Abstract / Citations / References / Notes / Linked Hypotheses (Linked Hypotheses tab disabled-with-tooltip in Phase 1). Action buttons: `Save to library`, `Cite in current draft section` (disabled), `Generate hypothesis from this paper` (disabled), `Add to project context` (disabled). `Esc` closes. See §7.5. |
| **T27** | Implement `<LibraryPanel>` (client) | M | 🟢 | T25 | Right-column panel showing saved-papers list. Filter: by year, by topic-tag (best-effort from journal). Each entry shows title + year + remove button. Counter: "X of Y saved". |
| **T28** | Implement `<BibtexExport>` button + `lib/lit/bibtex.ts` module | M | 🟢 | T27 | `bibtex.ts` exports `paperToBibtex(paper: PaperArtifact): string` returning `@article{AuthorYear, ...}`. Button on LibraryPanel triggers a blob download `{project-slug}-{YYYY-MM-DD}.bib`. |
| **T29** | Build `/api/lit/search/route.ts` | L | 🟡 | T30, T08 | POST handler accepts `{query, sources?, max_results?, publication_date?}` + project param. Calls `searchPapers` from T30. Returns `{total, results: PaperArtifact[], errors?: string[]}`. See §6.5. |
| **T30** | Implement `lib/lit/search.ts` — direct import of paper-search modules + dedupe + ranking | L | 🟡 | T02, T04 | Per D4. Imports `searchPubMed`, `searchArxiv`, `searchOpenAlex`, `searchSemanticScholar`, `checkPapersWithCode` via `@paper-search/*` aliases. Implements DOI dedupe and the ranking in sci-literature-research SKILL.md Step 1 (composite score `0.4*norm_citations + 0.3*relevance_position + 0.3*recency`). Maps `PaperResult` → `PaperArtifact` (§5.1) by adding deterministic `id` from source+source_id and stable `library_path`. |
| **T31** | Wire SearchBar → /api/lit/search → render PaperCard list inside `<LitWorkspace>` | M | 🟡 | T24, T25, T29 | Loading state, error state, empty state. Persist last query in URL `?q=...&sources=...`. |
| **T32** | Wire `Save to library` action: POST to `/api/lit/library` (T34), optimistic update of LibraryPanel, toast on persist failure | M | 🟡 | T27, T34 | Per PLAN §3 acceptance: 3 saves → 3 JSON files. |
| **T33** | Wire `<PaperDetail>` open/close: card click opens drawer, URL syncs to `?paper={paper_id}` for deep links, browser back closes | M | 🟡 | T26 | History API integration. |
| **T34** | Build `/api/lit/library/route.ts` (GET list, POST save, DELETE remove) | M | 🟢 | T35 | See §6.6. Idempotent saves (writing twice doesn't error). |
| **T35** | Implement `lib/lit/library.ts` (read/write of `papers/{paper_id}.json`) | M | 🟢 | T08 | Functions: `listLibrary(projectPath): PaperArtifact[]`, `savePaper(projectPath, paper): void`, `removePaper(projectPath, paper_id): void`. Atomic writes (`writeFileSync` to temp → rename). Creates `papers/` dir on first save. |
| **T36** | Implement empty-state component for /lit when no library + no recent search | S | 🟢 | T23 | Friendly prompt with example queries. Helps with the cold-start problem. |

### 4.5 Track E — Artifact protocol v1 + persistence

Per D6. Implements the protocol from PLAN §2.4 with one type (`paper`) wired end-to-end. Generalizes for Phase 2+.

| ID | Task | Effort | Risk | Depends on | Notes |
|---|---|---|---|---|---|
| **T37** | Write `lib/artifacts/parser.ts` + `lib/artifacts/types.ts` | M | 🟡 | T01 | Parser scans an SSE stdout stream line-by-line for valid JSON containing an `_artifact` discriminator. Yields typed `Artifact` events. types.ts exports `PaperArtifact`, `Artifact = PaperArtifact \| ...future`. Discriminator-keyed `parseArtifact(line: string): Artifact \| null` with strict type-narrowing. Unit-tested against the schemas in §5. |
| **T38** | Write `lib/artifacts/persist.ts` | M | 🟡 | T37, T35 | Type-discriminated dispatcher. `persistArtifact(projectPath, artifact)`: for `paper`, calls `savePaper`; for everything else in Phase 1, no-op + warn. Returns the resolved on-disk path. |
| **T39** | Write `lib/artifacts/render.ts` (client-side renderer index) | S | 🟢 | T37, T25 | Maps artifact `_artifact` discriminator to React component. Phase 1 only registers `paper → <PaperCard>`. Easy to add new types later. |
| **T40** | Hook artifact parser into `/api/execute` SSE so any artifact line emitted by a skill auto-persists | M | 🟡 | T15, T37, T38 | In `/api/execute`, after appending a stdout chunk to the run log, run `parseArtifact(line)` on each newline-terminated chunk; if non-null, call `persistArtifact(project.path, artifact)`. Send a synthetic SSE event `event: artifact\ndata: {...}` so the client can update without polling. |
| **T41** | Have `/api/lit/search` return artifacts in the same shape (via T30) | S | 🟢 | T29, T30 | Ensures the same `<PaperCard>` renders results regardless of source. T30 should already produce `PaperArtifact[]`; this is a verification + integration test. |
| **T42** | Update `sci-literature-research` skill to emit `_artifact: paper` JSON lines as its last output (PLAN §9.1 row 1) | M | 🟡 | — (skill repo) | One-skill update in `.claude/skills/sci-literature-research/`. Add a final stdout line per result: `console.log(JSON.stringify({_artifact: "paper", ...PaperArtifact_fields}))`. Keeps existing Markdown output for CLI users (backward-compatible). Acceptance: trigger sci-literature-research from `/api/execute` → /lit panel populates. |

### 4.6 Track F — Polish + Phase 1 acceptance

| ID | Task | Effort | Risk | Depends on | Notes |
|---|---|---|---|---|---|
| **T43** | Implement keyboard shortcuts: `Cmd+K` (palette), `Cmd+Enter` (submit search), `Esc` (close drawer), `j/k` (next/prev paper card) | M | 🟢 | T22, T24, T26 | react-hotkeys-hook. Document in a `?` overlay (PLAN §4.6). |
| **T44** | Add a single-line skill-execution overlay (transient toast) for any `/api/execute` run started from CmdK or sidebar | M | 🟡 | T40 | Replaces AgenticOS dedicated-panel pattern (PLAN §4.3). Phase 1 minimum: status (running/done/error) + cancel button + "view log" link. |
| **T45** | Wire the live-test: a "Search via skill" toggle on SearchBar that, when on, fires the skill via `/api/execute` instead of the direct API. Both produce paper artifacts; renderers handle both. | S | 🟢 | T31, T40, T42 | Prove the protocol works for Phase 2+ skills. Defaults OFF (direct API faster). |
| **T46** | Manual test plan walk: type "GLP-1 obesity meta-analysis" → verify ≥10 cards in <30s, click → drawer, save 3 → 3 JSON files at `projects/{slug}/papers/`, BibTeX export downloads valid `.bib`, open .bib in Zotero/BibTeX validator and confirm | M | 🟡 | T28, T32, T33 | Matches PLAN §3 Phase 1 acceptance verbatim. |
| **T47** | Latency audit: measure p50 + p95 of `/api/lit/search` end-to-end with 3 representative queries (oncology meta-analysis / NLP architecture / climate model). PLAN §5.8 budget = 30s. If p95 > 30s, profile and short-list slow source. | M | 🟡 | T31 | Document in `<dashboard>/PHASE_1_PERF.md`. Budget breach is a 🔴 finding that needs a fix before ship. |
| **T48** | Phase 1 ship checklist: README updated, all stub pages reachable, no console errors on cold start, npm run build succeeds, `.organon/` and `papers/` properly gitignored at the project level. | S | 🟢 | All preceding | Final gate before considering Phase 1 done. Triggers PLAN §10 "Show it to one researcher" step. |

**Total: 48 tasks. ~5–7 working days at moderate pace.** PLAN §3 budget for Phase 1 = ~2 weeks, leaves slack for unknowns.

---

## 5. Artifact JSON schemas

Per D6. These define the wire format for `_artifact` lines emitted by skills and the disk format under `projects/{slug}/`. Phase 1 implements one type (`paper`); the others are pre-specified so Phase 2+ extensions don't disturb the protocol.

All schemas use JSON Schema draft 2020-12 conventions in plain English. Required fields are bolded.

### 5.1 `_artifact: paper` (Phase 1)

```jsonc
{
  "_artifact": "paper",                   // discriminator — required
  "schema_version": 1,                    // required, integer; bumps when fields change
  "id": "pmid-37889012",                  // required — deterministic: {source}-{source_id}
  "source_ids": {                         // required — at least one populated
    "pmid": "37889012",                   // optional
    "arxiv": null,                        // optional, e.g. "2402.12345"
    "openalex": null,                     // optional, e.g. "W4393002148"
    "s2": null,                           // optional, Semantic Scholar paperId
    "paperclip": null,                    // optional, paperclip doc_id
    "doi": "10.1056/NEJMoa2206286"        // optional but strongly preferred (used for dedupe)
  },
  "title": "Tirzepatide Once Weekly...",  // required, string
  "authors": ["Jastreboff A.M.", "..."],  // required, array of strings (last-name + initials)
  "year": 2022,                           // required, integer; -1 if unknown
  "journal": "N Engl J Med",              // optional, string; "" if unknown
  "abstract": "BACKGROUND...",            // required, string; "" if unavailable (rare; flag in UI)
  "url": "https://pubmed...",             // required, string; canonical landing page
  "doi_url": "https://doi.org/10....",    // optional, string
  "pdf_url": null,                        // optional, string; OA PDF if known (Unpaywall future)
  "citation_count": 1247,                 // optional, integer; null if unknown
  "sources": ["pubmed", "openalex"],      // required, non-empty array; one per source that returned this paper
  "code": {                               // optional, object — populated only for top-N enriched results
    "available": true,                    // required if `code` present
    "github_url": "https://github.com/..." // optional, string
  },
  "library_path": "projects/{slug}/papers/pmid-37889012.json", // required, string; relative to organon-root
  "saved_at": null,                       // optional, ISO-8601 string; null when in search results, set when saved to library
  "tags": [],                             // optional, array of strings; user-managed in Phase 2+
  "notes": ""                             // optional, string; user-editable in Phase 2+
}
```

**Implementation rules:**
- The same `PaperArtifact` shape appears on the wire (in SSE) and on disk. The only difference: when on disk under `papers/{id}.json`, `saved_at` is non-null.
- Dedup happens by normalized DOI first, then by `(source, source_id)` pair. When two records dedupe, take the one with higher citation_count and union their `sources` arrays.
- `id` is the persistence key. Format: `{source}-{source_id}`. Pick source priority `pmid > arxiv > openalex > s2 > paperclip > doi`. If only DOI is present, `id = "doi-" + slugified-doi`.
- `library_path` is computed at write time and is informational on the wire (not load-bearing).

### 5.2 `_artifact: project` (Phase 1)

Used by `lib/projects.ts` to project the discovered project list onto the wire (used by `/api/projects` response and any future Cmd+K project search).

```jsonc
{
  "_artifact": "project",
  "schema_version": 1,
  "slug": "drug-discovery-llm-eval",      // required; folder basename, kebab-case
  "name": "Drug Discovery LLM Eval",      // required; titleCase(slug) by default, brief.md `project:` overrides
  "path": "/abs/path/to/projects/...",    // required; absolute path
  "is_root": false,                       // required, boolean; true only for the synthetic __root__ entry
  "is_brief": true,                       // required, boolean; true if path is under projects/briefs/
  "brief": {                              // optional, only if brief.md exists
    "status": "active",                   // string; from frontmatter
    "level": 2,                           // integer; 1, 2, or 3
    "created": "2026-04-15"               // ISO date
  },
  "papers_count": 24,                     // optional, integer; cheap-to-compute via fs.readdirSync
  "last_modified": "2026-05-06T14:23:00Z" // optional; max mtime across project subtree (best-effort, capped scan)
}
```

### 5.3 Other artifact types (declared, not implemented in Phase 1)

These are **pre-specified** so Phase 2+ tasks can implement them without protocol-level changes. Persisters and renderers are no-ops in Phase 1 (T38).

| Type | When emitted | On-disk path | Phase that implements |
|---|---|---|---|
| `hypothesis` | sci-hypothesis Generate, sci-council reconcile | `projects/{slug}/hypotheses/{hyp_id}.json` | Phase 2 |
| `persona-critique` | sci-council fanout | `projects/{slug}/hypotheses/{hyp_id}/critiques/{persona}.json` | Phase 2 |
| `figure` | viz-nano-banana, sci-data-analysis plots | `projects/{slug}/figures/{fig_id}/v{N}.png` + sidecar JSON | Phase 3 + 4 |
| `dataframe` | sci-data-analysis load | `projects/{slug}/data/{file_id}.preview.json` | Phase 3 |
| `stat-result` | sci-data-analysis test | `projects/{slug}/results/{run_id}.json` | Phase 3 |
| `section-draft` | sci-writing draft | `projects/{slug}/manuscripts/{doc}/sections/{section_id}.md` | Phase 5 |
| `section-diff` | sci-writing rewrite | (transient SSE only, not persisted) | Phase 5 |

Phase 1 parser MUST tolerate (i.e., ignore-with-warn, not crash) on these other types.

---

## 6. API contracts

All routes are Next.js 16 App Router Route Handlers under `src/app/api/`. Default response is JSON; `/api/execute` uses SSE.

Conventions:
- Errors: `{error: string, code?: string}` with HTTP 4xx/5xx.
- Project param: `?project={slug}` query for GET, `body.project` for POST/DELETE. Defaults to `__root__` on miss. 404 on unknown slug.
- All POST/DELETE routes accept `application/json`.
- All routes are `dynamic = "force-dynamic"` to avoid Next.js cache hits during dev.

### 6.1 `GET /api/projects`

**Request.** No params.

**Response 200.**
```jsonc
{
  "projects": [
    {"slug": "__root__", "name": "Scientific OS", "is_root": true, "is_brief": false},
    {"slug": "organon-dashboard", "name": "Organon Dashboard", "is_root": false, "is_brief": true,
     "brief": {"status": "planning", "level": 2, "created": "2026-05-06"}},
    {"slug": "einstein-arena-prime-number-theorem", "name": "Einstein Arena Prime Number Theorem",
     "is_root": false, "is_brief": false}
  ]
}
```

`papers_count` and `last_modified` are deferred to Phase 6 (cheap to add but Phase 1 doesn't render them).

### 6.2 `GET /api/skills?project={slug}`

**Request.** Query param `project` (string; defaults to `__root__`).

**Response 200.**
```jsonc
{
  "project": "organon-dashboard",
  "groups": [
    {"category": "sci", "label": "Science", "skills": [
      {"name": "sci-literature-research", "slug": "sci-literature-research", "category": "sci",
       "description": "Search, summarize, cite, and analyze trends..."}
    ]},
    {"category": "viz", "label": "Visual", "skills": [...]},
    {"category": "ops", "label": "Operations", "skills": [...]},
    {"category": "tool", "label": "Tools", "skills": [...]},
    {"category": "meta", "label": "System / Meta", "skills": [...]}
  ]
}
```

**Response 404.** `{"error": "Unknown project: <slug>"}`

### 6.3 `GET /api/runs?project={slug}&limit={n}`

**Request.** Query: `project` (default `__root__`), `limit` (default 20, max 500).

**Response 200.**
```jsonc
{
  "project": "organon-dashboard",
  "runs": [
    {"id": "2026-05-06T14-23-00-000Z", "ts": "2026-05-06T14:23:00.000Z",
     "project": "organon-dashboard", "skill": "sci-literature-research",
     "prompt": "search GLP-1 obesity", "status": "ok", "exitCode": 0,
     "durationMs": 18432, "excerpt": "Found 12 papers..."}
  ],
  "weekly": [
    {"date": "2026-04-30", "count": 3},
    {"date": "2026-05-01", "count": 1}
  ]
}
```

### 6.4 `GET /api/usage?project={slug}`

**Request.** Query: `project` (default `__root__`).

**Response 200.** As `UsageReport` from `lib/usage-types.ts` ported verbatim from AgenticOS. Schema unchanged. Wrapper: `{project, report: UsageReport}`.

### 6.5 `POST /api/lit/search`

**Request.**
```jsonc
{
  "project": "organon-dashboard",         // optional; defaults to __root__
  "query": "GLP-1 obesity meta-analysis", // required, string
  "sources": ["pubmed", "openalex"],      // optional; default ["pubmed","arxiv","openalex","semanticscholar"]
  "max_results": 10,                      // optional, 1..50, default 10
  "publication_date": "2024-01-01:"       // optional, "YYYY-MM-DD:YYYY-MM-DD" (open-ended ok)
}
```

**Response 200.**
```jsonc
{
  "project": "organon-dashboard",
  "query": "GLP-1 obesity meta-analysis",
  "total": 12,
  "results": [PaperArtifact, ...],        // dedup + ranked, see §5.1
  "errors": ["S2: rate limit exceeded"]   // optional; per-source non-fatal errors
}
```

**Response 400.** `{"error": "query required"}` on empty query.

### 6.6 `GET|POST|DELETE /api/lit/library`

#### `GET /api/lit/library?project={slug}`

**Response 200.**
```jsonc
{
  "project": "organon-dashboard",
  "papers": [PaperArtifact, ...],         // each with saved_at populated
  "total": 24
}
```

#### `POST /api/lit/library`

**Request.**
```jsonc
{
  "project": "organon-dashboard",         // optional, defaults to __root__
  "paper": PaperArtifact                   // required; full §5.1 shape minus saved_at
}
```

**Response 201.** `{"saved": true, "library_path": "projects/{slug}/papers/{id}.json"}`

**Response 200** (idempotent re-save). Same shape as 201 but `"saved": false, "already_present": true`.

**Response 400.** `{"error": "paper.id required"}`

#### `DELETE /api/lit/library`

**Request.**
```jsonc
{
  "project": "organon-dashboard",
  "paper_id": "pmid-37889012"
}
```

**Response 200.** `{"removed": true}`

**Response 404.** `{"error": "Paper not in library"}`

### 6.7 `POST /api/execute` (port from AgenticOS, project-renamed)

**Request.**
```jsonc
{
  "project": "organon-dashboard",         // optional, defaults to __root__
  "skill": "sci-literature-research",     // optional; if present, wraps prompt with "Use the {skill} skill..."
  "prompt": "search GLP-1 papers"         // required, string
}
```

**Response.** SSE stream. Events:
- `event: start\ndata: {ts, prompt, skill?, project}\n\n`
- `event: stdout\ndata: {ts, chunk}\n\n` (multiple)
- `event: stderr\ndata: {ts, chunk}\n\n` (multiple)
- `event: artifact\ndata: {artifact: PaperArtifact|...}\n\n` (new in T40 — emitted whenever the parser extracts an artifact line)
- `event: exit\ndata: {ts, code: number|null}\n\n`
- `event: done\ndata: {}\n\n`
- `event: error\ndata: {message}\n\n` (on spawn failure)

The artifact event is **additive** to the AgenticOS contract; old clients ignoring unknown events still work.

---

## 7. Component prop contracts

All TypeScript-strict. Client components marked `"use client"` at file top.

### 7.1 `<Sidebar>`

```typescript
type SidebarProps = {
  /** Active workspace path, e.g. "/lit". Drives the highlighted link. */
  activePath: string;
  /** Project slug to append as ?project= on every link. */
  currentProject: string;
};
```

Renders: ordered link list. Items:
1. Lit (active in P1)
2. Hypothesis (badge: "Phase 2")
3. Data (badge: "Phase 3")
4. Tools (badge: "Phase 6")
5. Figures (badge: "Phase 4")
6. Draft (badge: "Phase 5")
7. Crons (badge: "Phase 6")
8. Runs (badge: "Phase 6")

### 7.2 `<Topbar>`

```typescript
type TopbarProps = {
  projects: Project[];                    // from /api/projects, see §5.2
  current: string;                        // current project slug
  onChange: (slug: string) => void;       // called when picker selects new project
  onOpenPalette: () => void;              // triggered by Cmd+K hint button
  usage?: UsageReport | null;             // optional; renders last-sync timestamp + cost
};
```

URL state sync per D7: `onChange` should `router.replace(?project={slug})` and write to `localStorage.organon.dashboard.lastProject`.

### 7.3 `<SearchBar>`

```typescript
type SearchBarProps = {
  initialQuery?: string;                  // hydrated from URL
  initialSources?: SearchSource[];        // default = all 4
  onSearch: (params: SearchParams) => void;
  loading?: boolean;
};

type SearchSource = "pubmed" | "arxiv" | "openalex" | "semanticscholar";

type SearchParams = {
  query: string;
  sources: SearchSource[];
  max_results: number;
  publication_date?: string;
};
```

Submits on Enter; `Cmd+Enter` per PLAN §4.6 also fires.

### 7.4 `<PaperCard>`

```typescript
type PaperCardProps = {
  paper: PaperArtifact;                   // §5.1
  isSaved: boolean;                       // controls Save/Saved label + style
  isFocused: boolean;                     // for j/k keyboard nav highlight
  onOpen: (paper: PaperArtifact) => void;
  onSave: (paper: PaperArtifact) => void;
  onUnsave: (paper: PaperArtifact) => void;
};
```

Renders title (link → onOpen), authors line, year + journal + citations + sources badges, code-link badge if `paper.code?.available`, abstract preview (first ~200 chars), Save/Saved button.

### 7.5 `<PaperDetail>`

```typescript
type PaperDetailProps = {
  paper: PaperArtifact | null;            // null → drawer is closed
  isSaved: boolean;
  onClose: () => void;
  onSave: (paper: PaperArtifact) => void;
  onUnsave: (paper: PaperArtifact) => void;
};
```

Tabs (in Phase 1 — disabled tabs render greyed-out with a "Phase N" tooltip):
- Abstract (active)
- Citations (disabled — Phase 6 will surface citation graph)
- References (disabled — same)
- Notes (disabled — Phase 5 ties to manuscript scratchpad)
- Linked Hypotheses (disabled — Phase 2)

Actions row: Save/Unsave (active), Cite in current draft (disabled), Generate hypothesis (disabled), Add to project context (disabled).

Closes on `Esc` or backdrop click.

### 7.6 `<LibraryPanel>`

```typescript
type LibraryPanelProps = {
  papers: PaperArtifact[];                // saved papers
  currentProject: string;
  onRemove: (paperId: string) => void;
  onOpen: (paper: PaperArtifact) => void;
  onExportBibtex: () => void;
};
```

Filter chips (year range, source) act locally (no fetch).

### 7.7 `<BibtexExport>`

```typescript
type BibtexExportProps = {
  papers: PaperArtifact[];
  filename: string;                       // default: "{project-slug}-{date}.bib"
};
```

Single button. On click: builds BibTeX text via `paperToBibtex` from `lib/lit/bibtex.ts`, creates a Blob, triggers a download. No backend round-trip.

### 7.8 `<CommandPalette>`

```typescript
type CommandPaletteProps = {
  open: boolean;
  onClose: () => void;
  projects: Project[];
  skillsForCurrentProject: SkillGroup[];
  currentProject: string;
};
```

Built on `cmdk`. Three command groups:
1. **Navigate** — workspace links + project switch
2. **Skills** — flat list of all skills (filterable). Picking one navigates to the workspace it owns or, if none, populates the home hero prompt.
3. **Help** — `?` opens shortcut overlay.

### 7.9 `<LitWorkspace>` (composite)

```typescript
type LitWorkspaceProps = {
  project: string;
  initialLibrary: PaperArtifact[];        // hydrated server-side from listLibrary()
  initialQuery?: string;
  initialPaperId?: string;                // for ?paper={id} deep links
};
```

Internal state:
- `query`, `sources`, `results`, `library`, `focusedIdx`, `detailPaper`, `isLoading`, `error`, `searchViaSkill` (T45 toggle)

Sync rules:
- Library changes pushed to localStorage too as cheap optimistic-cache
- URL params `?q`, `?paper`, `?sources` written via `router.replace`
- `j`/`k` move `focusedIdx`; `Enter` opens detail; `s` saves the focused paper

---

## 8. npm dependencies

Locked versions, matching AgenticOS where possible. `npm install` from a clean state should hit these exact resolved versions; deviations require updating this section.

### 8.1 Runtime

```jsonc
{
  "dependencies": {
    "next": "16.2.4",                     // matches AgenticOS
    "react": "19.2.4",                    // matches AgenticOS
    "react-dom": "19.2.4",                // matches AgenticOS
    "cmdk": "1.0.4",                      // command palette (D8, T22)
    "react-hotkeys-hook": "4.6.1"         // keyboard shortcuts (PLAN §4.6, T43)
  }
}
```

**Why not more.** No icon library (use Unicode + CSS), no toast library (build a simple one if needed in T44), no react-query (single-fetch + reload pattern is fine for Phase 1 — TanStack Query lands in v0.2 per PLAN §2.1), no shadcn/ui (PLAN §2.1 — v0.2; D10).

### 8.2 Dev

```jsonc
{
  "devDependencies": {
    "@tailwindcss/postcss": "^4",         // matches AgenticOS
    "@types/node": "^20",                 // matches AgenticOS
    "@types/react": "^19",                // matches AgenticOS
    "@types/react-dom": "^19",            // matches AgenticOS
    "tailwindcss": "^4",                  // matches AgenticOS
    "typescript": "^5"                    // matches AgenticOS
  }
}
```

### 8.3 No dependency on the paper-search package

`/api/lit/search` imports source files directly (D4). The paper-search MCP server's own `node_modules` (zod, the MCP SDK, etc.) is **not** in the dashboard's tree. The TypeScript path alias resolves at compile time and the dependency types come transitively.

If the import fails because the paper-search source files import npm packages that the dashboard doesn't have (e.g., `zod`), T30 has to add those to the dashboard's `package.json`. Concretely the paper-search modules use only Node built-ins + `node:fetch`-equivalent — verify in T30 that no extra deps are needed; if any surface, add the **exact same versions** the paper-search package.json declares.

### 8.4 Scripts

```jsonc
{
  "scripts": {
    "dev": "next dev -p 8769",
    "build": "next build",
    "start": "next start -p 8769",
    "lint": "next lint",
    "typecheck": "tsc --noEmit"
  }
}
```

Port 8769 per D7 — avoids AgenticOS's 8768.

---

## 9. Dev-setup runbook

For a fresh developer / fresh worktree.

### 9.1 Prerequisites

| Tool | Version | Check |
|---|---|---|
| Node.js | ≥ 20 LTS | `node --version` |
| npm | ≥ 10 | `npm --version` |
| Organon repo | cloned and `bash scripts/install.sh` run once | `ls ~/.local/bin/paperclip` (optional) + `ls .mcp.json` |
| Paper-search MCP built | `cd mcp-servers/paper-search && npm install && npm run build` | `ls mcp-servers/paper-search/dist/index.js` |

### 9.2 Environment variables

The dashboard reads these from the **Organon repo `.env`** (loaded via `lib/env.ts`). `.env.example` already documents most of them; any new ones added in this phase are listed here.

| Var | Required | Used by | What it provides | Without it |
|---|---|---|---|---|
| `ORGANON_ROOT` | Optional | `lib/paths.ts` | Override the auto-detected Organon repo root | Falls back to `cwd/../../..` checked against CLAUDE.md |
| `NCBI_API_KEY` | Optional | `lib/lit/search.ts` (PubMed via paper-search modules) | Higher PubMed rate limit (10 req/s vs 3) | Slower searches, more frequent rate-limit errors in /api/lit/search response |
| `OPENALEX_API_KEY` | Optional | `lib/lit/search.ts` (OpenAlex) | Polite-pool access, higher rate limits | Unauthenticated, rate-limited |
| `S2_API_KEY` | Optional | `lib/lit/search.ts` (Semantic Scholar) | Dedicated 1 RPS rate limit | Shared pool, frequent backoffs |
| `CLAUDE_BIN` | Optional | `lib/claude-runner.ts` | Override `claude` binary path (testing) | Uses `claude` from PATH |

No new env vars required — Phase 1 reuses Organon's existing keys via the same `scripts/with-env.sh` mechanism that the MCP servers use. The Next.js process picks them up because it spawns from a shell that has them via `.env`-sourcing or because the developer `source`s them before `npm run dev`.

**Recommended `.env` pattern:** `bash -lc 'set -a; source .env; cd projects/briefs/organon-dashboard; npm run dev'`. Document this command in T03's README.

### 9.3 First-run sequence

```bash
# 1. From Organon repo root, ensure paper-search MCP is built
cd mcp-servers/paper-search
npm install        # only if dist/ is missing or package.json changed
npm run build

# 2. Bootstrap dashboard
cd ../../projects/briefs/organon-dashboard
npm install

# 3. Sanity check: paper-search modules are reachable via the alias
npx tsc --noEmit   # should report 0 errors after T30 lands

# 4. Start dev server
npm run dev
# Listening on http://localhost:8769
```

### 9.4 Smoke test post-install

1. Open `http://localhost:8769` — home renders, project picker shows ≥ 1 project.
2. Click a sidebar link → arrives at workspace; non-Lit links show "Coming in Phase N".
3. Open `/lit` → SearchBar present. Type a query → ≥ 5 paper cards in ≤ 30s.
4. Click a card → drawer slides in. Press `Esc` → closes.
5. Click `Save` on 3 cards → LibraryPanel updates count to 3. `ls projects/{slug}/papers/` → 3 JSON files.
6. Click `Export BibTeX` → file downloads. Open in any BibTeX validator (or paste into Zotero) → no parse errors.
7. Press `Cmd+K` → palette opens. Type a workspace name → navigates.

Any failure here blocks the Phase 1 acceptance gate (T48).

### 9.5 Common failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| `Cannot find module @paper-search/pubmed` | tsconfig `paths` alias not set or relative path wrong | Recheck T02; confirm path resolves from dashboard root |
| `/api/lit/search` returns 0 results with "all sources errored" | Network or env vars missing | Check `.env` is sourced; try a single source via `?sources=pubmed` |
| `Project picker shows only __root__` | `projects/` directory empty or all-hidden | `ls <organon-root>/projects/` — should match D1 rule |
| `Saved papers not persisting` | `papers/` directory write failure | Check perms; T35 should create the dir; verify T48's gitignore |
| `Cmd+K does nothing` | react-hotkeys-hook not bound or `useEffect` not firing | Verify T22 + T43 wiring |

---

## 10. Phase 1 acceptance gate

The full PLAN §3 Phase 1 acceptance criteria, restated as a binary checklist. Phase 1 ships when **every box is ticked**.

- [ ] Researcher types "GLP-1 obesity meta-analysis" into SearchBar.
- [ ] Within 30s, ≥10 paper cards render with title, authors, year, abstract preview.
- [ ] Click a card → drawer shows full abstract, DOI, citation count, link to full text.
- [ ] "Save to library" on 3 cards → `projects/{slug}/papers/` has 3 valid JSON files matching §5.1 schema.
- [ ] "Export BibTeX" downloads a valid `.bib` for the saved set (parses cleanly in any BibTeX validator).
- [ ] All 8 sidebar links navigate without 404; non-Phase-1 links show their "Coming in Phase N" stub.
- [ ] `npm run build` exits 0.
- [ ] `npm run typecheck` exits 0 with strict mode on.
- [ ] No console errors on cold-load of `/`, `/lit`, or any stub page.
- [ ] Smoke test §9.4 passes end-to-end.

After ticking all boxes: hand to the user (or Kerem) for the "show it to one researcher" step (PLAN §10), gather feedback into `context/learnings.md` under `## organon-dashboard`, then plan Phase 2.

---

*End of Phase 1 tactical plan. Next document is `PHASE_2_TASKS.md`, written only after Phase 1 ships and PLAN Q5 (persona set) is resolved.*
