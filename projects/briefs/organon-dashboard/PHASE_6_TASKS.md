---
project: organon-dashboard
status: tactical-ready
phase: 6
created: 2026-05-06
parent_plan: PLAN.md
siblings: PHASE_1..5_TASKS.md
scope: /tools, /crons, /runs, real /usage charts, Cmd+K cross-corpus search (PLAN §3 Phase 6)
out_of_scope: v1.0 ship is the next milestone after Phase 6.
---

# Organon Dashboard — Phase 6 Tactical Plan

Bridge between PLAN.md and code, for **Phase 6 only**. Final phase before v1.0 ship. Phases 1–5 shipped + dogfooded before Phase 6 starts.

## Table of Contents

1. [Phase 6 scope recap](#1-phase-6-scope-recap)
2. [Tactical decisions](#2-tactical-decisions)
3. [Repository layout](#3-repository-layout)
4. [Atomic task list (T01–T32)](#4-atomic-task-list)
5. [Artifact JSON schemas](#5-artifact-json-schemas)
6. [API contracts](#6-api-contracts)
7. [Component prop contracts](#7-component-prop-contracts)
8. [npm dependencies](#8-npm-dependencies)
9. [Dev-setup runbook](#9-dev-setup-runbook)
10. [Phase 6 acceptance gate](#10-phase-6-acceptance-gate)

---

## 1. Phase 6 scope recap

Five deliverables from PLAN §3 Phase 6:

1. `/tools` workspace: search-and-trigger over the ToolUniverse 2,200+ catalog. Filter by domain (drug / disease / genomics / etc.), favourites, run with form-based input.
2. `/crons` workspace: list of scheduled jobs from `cron/jobs/`. Status indicators (last run, next run, failures). One-click enable / disable / run-now.
3. `/runs` workspace: full run history with drill-down. Click a run → prompt, output, exit code, duration, token cost, linked artifacts.
4. Usage analytics: real charts (replace placeholder SVG) — daily / weekly / monthly view, by skill, by model.
5. Cmd+K command palette: search across **everything** (papers, hypotheses, figures, sections, skills) with project-scoped filtering.

---

## 2. Tactical decisions

| # | Decision | Choice | Rationale |
|---|---|---|---|
| D1 | **ToolUniverse browser** | Surface the catalog via the existing `tooluniverse` MCP server (already in `.mcp.json`). Form-based input derived from the tool's JSON schema. Initial fetch is cached to `<projectPath>/.organon-dashboard/tooluniverse-catalog.json` for 24 hours. | Existing MCP works; cache prevents 2,200-row scrolls from re-fetching on every visit. |
| D2 | **Crons read-only in Phase 6** | UI reads `cron/jobs/*.md` + `cron/status/*.json` files. Enable / disable / run-now are deferred to v1.0 polish. Phase 6 ships READ-ONLY status board. | Write-side requires LaunchAgent / Task Scheduler integration which has cross-platform pitfalls; not worth holding the phase. |
| D3 | **Runs drill-down** | Click a run row → modal/drawer showing prompt + full stdout/stderr + exit code + duration + token cost + links to any artifacts the run produced. Reads `.organon/runs/{id}.jsonl` directly. | All data already on disk from Phase 1's run logger. Drill-down is pure UI layer over existing data. |
| D4 | **Usage charts** | Hand-rolled SVG charts (no `chart.js` / `recharts` dependency). Daily bars + weekly aggregate + by-skill stacked bar. The data shape is small (1 row per run); a 200-LOC SVG renderer is fewer maintenance dependencies than a charting library. | One fewer npm dep; the visual surface is small; SVG renders crisply on any DPI. |
| D5 | **Cmd+K cross-corpus search** | Local in-memory index built on workspace mount (or workspace switch). Index sources: `papers/*.json`, `hypotheses/*/hypothesis.json`, `figures/*/v{N}.json`, `manuscripts/*/sections/*.md`. Tokenization: lowercase + word-split. Match: substring + prefix scoring. Refreshed on artifact change via filesystem watch (`fs.watch`). | Filesystem-only fits PLAN §7 Q6 default ("filesystem JSON for v0.1"). SQLite migration deferred until ≥ 500 papers/project. |
| D6 | **Skill versioning metadata** | Run records include `git_rev` (HEAD short sha at run time). Surfaced in `/runs` drill-down. No new tracking system. | Pulls reproducibility metadata from the existing git history without writing a new ledger. |
| D7 | **MCP integration** | Treat MCP tools (`paperclip`, `paper-search`, `tooluniverse`) as another category in `/tools` UI; same form-based wrapper. Auto-discovered from `.mcp.json`. | Uniform UI for tool execution regardless of source. |
| D8 | **Tool favourites** | Per-project file at `<projectPath>/.organon-dashboard/tool-favourites.json` (array of tool names). Top 5–10 pinned in `/tools`. | Per-project because a clinical project's favourites differ from a math project's. |
| D9 | **Out of scope (v0.x)** | Multi-user shared favourites, tool authorship/auditing, scheduled-from-UI cron creation, paper bibliometric graph, citation-graph in `<PaperDetail>`. | All deferred to v1.x. Phase 6 already covers a lot of surface. |
| D10 | **Index refresh strategy** | The cmdk index lives in memory; rebuilt on workspace mount. Filesystem-watch deltas (best-effort) refresh during the session. Stale-on-window-blur is acceptable. | A 500-row index rebuilds in < 50 ms; not worth a service-worker / IndexedDB layer for Phase 6. |

---

## 3. Repository layout

```
src/
├── app/
│   ├── tools/page.tsx                          # T07 — replaces P1 stub
│   ├── crons/page.tsx                          # T13 — replaces P1 stub
│   ├── runs/page.tsx                           # T17 — replaces P1 stub
│   └── api/
│       ├── tools/
│       │   ├── catalog/route.ts                # T08 — ToolUniverse + MCP catalog
│       │   ├── run/route.ts                    # T11 — execute a tool with form params
│       │   └── favourites/route.ts             # T12 — get/set per-project favourites
│       ├── crons/route.ts                      # T14 — list jobs + status
│       ├── runs/[id]/route.ts                  # T18 — single run drill-down
│       └── search/route.ts                     # T26 — cmdk cross-corpus search
├── components/
│   ├── tools/
│   │   ├── tools-workspace.tsx                 # T07
│   │   ├── tool-search.tsx                     # T09 — search + filter
│   │   ├── tool-card.tsx                       # T10
│   │   ├── tool-form.tsx                       # T11 — JSON-schema-driven form
│   │   └── tool-favourites.tsx                 # T12
│   ├── crons/
│   │   ├── crons-workspace.tsx                 # T13
│   │   ├── cron-row.tsx                        # T15
│   │   └── cron-status-pill.tsx                # T16
│   ├── runs/
│   │   ├── runs-workspace.tsx                  # T17
│   │   ├── run-row.tsx                         # T19
│   │   └── run-detail-drawer.tsx               # T20 — full drill-down
│   ├── usage/
│   │   ├── usage-workspace.tsx                 # T21 — replaces P1 placeholder
│   │   ├── usage-charts.tsx                    # T22 — hand-rolled SVG
│   │   └── usage-table.tsx                     # T23
│   └── shell/command-palette.tsx               # T27 — extended with cross-corpus
└── lib/
    ├── tools/
    │   ├── catalog.ts                          # T08 — fetch + cache MCP catalog
    │   └── favourites.ts                       # T12
    ├── crons/
    │   └── reader.ts                           # T14 — parse cron/jobs/*.md + status/*.json
    ├── search/
    │   ├── index.ts                            # T25 — in-memory index build
    │   ├── score.ts                            # T26 — substring + prefix scoring
    │   └── watch.ts                            # T28 — fs.watch deltas
    └── git/
        └── rev.ts                              # T29 — git rev-parse HEAD short
```

---

## 4. Atomic task list

32 tasks.

### 4.1 Track A — Bootstrap (T01–T03)

| ID | Task | Effort | Risk |
|---|---|---|---|
| **T01** | README append. | S | 🟢 |
| **T02** | Phase 5 gate confirmation. | S | 🟢 |
| **T03** | Forward-compat: ensure all Phase 6 routes use the same project-param + dynamic conventions. | S | 🟢 |

### 4.2 Track B — /tools workspace (T04–T12)

| ID | Task | Effort | Risk |
|---|---|---|---|
| **T04** | `lib/tools/catalog.ts` — fetch MCP `tooluniverse` catalog + cache in `.organon-dashboard/tooluniverse-catalog.json` (24h TTL). | M | 🟡 |
| **T05** | Catalog augmentation — also include local Organon skills + the other MCPs (paperclip, paper-search) so `/tools` is one search surface. | M | 🟢 |
| **T06** | `<ToolsWorkspace>` server component + page. | M | 🟢 |
| **T07** | `<ToolSearch>` — search box + domain filter chips (drug / disease / genomics / etc.). | M | 🟢 |
| **T08** | `<ToolCard>` — name, description, source (local skill / paperclip / tooluniverse / paper-search), favourite toggle. | S | 🟢 |
| **T09** | `<ToolForm>` — JSON-schema-driven form. Generates inputs per param type (string / number / enum / file). | L | 🟡 |
| **T10** | `/api/tools/catalog/route.ts` — returns the cached catalog. | S | 🟢 |
| **T11** | `/api/tools/run/route.ts` — POST: executes a tool. For local skills, fires via `/api/execute`. For MCP tools, calls the MCP directly. SSE stream pass-through. | L | 🔴 |
| **T12** | `<ToolFavourites>` + `/api/tools/favourites/route.ts` — get/set per-project pinned tools. | M | 🟢 |

### 4.3 Track C — /crons workspace (T13–T16)

| ID | Task | Effort | Risk |
|---|---|---|---|
| **T13** | `<CronsWorkspace>` server component + page. | M | 🟢 |
| **T14** | `lib/crons/reader.ts` + `/api/crons/route.ts` — list `cron/jobs/*.md` + per-job status from `cron/status/{job-id}.json`. | M | 🟢 |
| **T15** | `<CronRow>` — name, schedule, last run, next run, success/failure pill. | S | 🟢 |
| **T16** | `<CronStatusPill>` — green / amber / red based on last-run status. | S | 🟢 |

### 4.4 Track D — /runs drill-down (T17–T20)

| ID | Task | Effort | Risk |
|---|---|---|---|
| **T17** | `<RunsWorkspace>` server component + page. | M | 🟢 |
| **T18** | `/api/runs/[id]/route.ts` — single-run detail (full stdout/stderr from `.organon/runs/{id}.jsonl`). | M | 🟢 |
| **T19** | `<RunRow>` — extends P1 run-summary row with click-to-detail. | S | 🟢 |
| **T20** | `<RunDetailDrawer>` — slide-from-right drawer; full prompt + output + duration + token cost + linked artifacts (parsed from stdout). | L | 🟡 |

### 4.5 Track E — /usage real charts (T21–T24)

| ID | Task | Effort | Risk |
|---|---|---|---|
| **T21** | `<UsageWorkspace>` server component + page. | M | 🟢 |
| **T22** | `<UsageCharts>` — hand-rolled SVG: daily bar chart (last 14 days), by-skill stacked bar, by-model pie. | L | 🟡 |
| **T23** | `<UsageTable>` — top-10 most-expensive runs of the period; sortable. | M | 🟢 |
| **T24** | Replace the P1 placeholder SVG in topbar with a tiny inline 7-day sparkline reading the same data. | S | 🟢 |

### 4.6 Track F — Cmd+K cross-corpus (T25–T29)

| ID | Task | Effort | Risk |
|---|---|---|---|
| **T25** | `lib/search/index.ts` — build the in-memory index from artifact files. ~500-row scan budget < 50 ms. | M | 🟡 |
| **T26** | `lib/search/score.ts` — substring + prefix scoring. Fuzz-tested against representative queries. | M | 🟢 |
| **T27** | `<CommandPalette>` extension — paper / hypothesis / figure / section results above the existing static commands. Result types color-coded. | L | 🟡 |
| **T28** | `lib/search/watch.ts` — fs.watch deltas to refresh the index. Fallback to mount-time only if `fs.watch` unavailable on platform. | M | 🟡 |
| **T29** | `lib/git/rev.ts` — `gitRevShort()` returning short sha; used by run logger to stamp each run with the current git HEAD. | S | 🟢 |

### 4.7 Track G — Polish + acceptance (T30–T32)

| ID | Task | Effort | Risk |
|---|---|---|---|
| **T30** | `/api/search` — REST endpoint mirroring the cmdk surface (used by future scripts; cmdk uses local index, this is for headless callers). | M | 🟢 |
| **T31** | Manual test plan walk: ToolUniverse search "BLAST" → form → submit → result. Crons page shows the locally-installed scheduled jobs. Click a 3-day-old run from `/runs` → reproduces full prompt and output. Cmd+K + "fig-2-pca" → jumps directly to that figure in `/figures`. | M | 🟡 |
| **T32** | Phase 6 ship checklist + v1.0 readiness review (PLAN §8 acceptance criteria). | M | 🟡 |

**Total: 32 tasks. ~6–8 working days.**

---

## 5. Artifact JSON schemas

No new artifact types in Phase 6. The phase reads existing artifacts (papers, hypotheses, figures, sections) for the cmdk index and surfaces existing run records.

The catalog cache file (`tooluniverse-catalog.json`) is not an artifact — it is dashboard-internal state.

---

## 6. API contracts

### 6.1 `GET /api/tools/catalog`

Returns: `{tools: ToolCatalogEntry[]}` aggregated across local skills + MCP servers + ToolUniverse.

### 6.2 `POST /api/tools/run`

`{tool_id, params}` → SSE if a skill spawn; JSON for MCP single-call. Skill spawns route to `/api/execute`.

### 6.3 `GET|PUT /api/tools/favourites?project={slug}`

Returns: `{favourites: string[]}`. PUT body: `{favourites: string[]}`.

### 6.4 `GET /api/crons?project={slug}`

Returns: `{jobs: [{id, name, schedule, last_run, next_run, status}]}`.

### 6.5 `GET /api/runs/[id]?project={slug}`

Returns full run record: `{id, prompt, stdout_chunks: [], stderr_chunks: [], exit_code, duration_ms, token_cost_cents, git_rev, linked_artifacts: []}`.

### 6.6 `GET /api/search?project={slug}&q={query}&types={paper,hypothesis,figure,section}`

Returns: `{results: SearchHit[]}` ranked by score. Mirrors what cmdk does locally.

---

## 7. Component prop contracts

(Compact form.)

- `<ToolsWorkspace>(props: {project, catalog, favourites})`
- `<ToolSearch>(props: {tools, onFilter, query, domain})`
- `<ToolForm>(props: {tool: ToolCatalogEntry, onRun})`
- `<CronsWorkspace>(props: {jobs})`
- `<RunsWorkspace>(props: {project, runs})`
- `<RunDetailDrawer>(props: {run, onClose})`
- `<UsageWorkspace>(props: {report: UsageReport})`
- `<UsageCharts>(props: {report})`

---

## 8. npm dependencies

**No new runtime dependencies.** SVG charts hand-rolled. Search index pure TS.

---

## 9. Dev-setup runbook

### 9.1 Prerequisites (delta)

| Tool | Version | Check |
|---|---|---|
| Phase 5 acceptance gate | green | T02 |
| `tooluniverse` MCP | installed (uvx) | `.mcp.json` entry present |
| `git` | ≥ 2.30 | `git --version` (used by `lib/git/rev.ts`) |

### 9.2 Smoke test

1. `/tools` renders; ≥ 100 tools visible (Organon skills + at least one MCP source).
2. Search "BLAST" → ToolUniverse BLAST entry visible. Click → form. Submit → result.
3. `/crons` lists locally-installed scheduled jobs from `~/Library/LaunchAgents/com.organon.*.plist`.
4. `/runs` shows last 50 runs. Click an old run → drawer with full output.
5. Cmd+K + "GLP-1" → returns paper + hypothesis + section results all in one list.
6. Cmd+K + a figure id → jumps to `/figures?fig={id}`.

---

## 10. Phase 6 acceptance gate

- [ ] ToolUniverse search "BLAST" → form → submit → result renders.
- [ ] `/crons` shows locally-installed jobs from `~/Library/LaunchAgents/com.organon.*.plist`.
- [ ] Click a 3-day-old run from `/runs` → reproduces the full prompt and output.
- [ ] Cmd+K + "fig-2-pca" → jumps directly to that figure in `/figures`.
- [ ] `/usage` shows real charts (not placeholder SVG).
- [ ] All Phase 1–5 workspaces still functional.
- [ ] `npm run build` + typecheck exit 0.
- [ ] Smoke test §9.2 passes.

After ticking: declare v1.0 candidate per PLAN §8. End-to-end ship test (PLAN §8 list of researcher workflow steps) is the final v1.0 gate, not Phase 6's gate.

---

*End of Phase 6 tactical plan. Final phase before v1.0 ship.*
