---
project: organon-dashboard
status: tactical-ready
phase: 3
created: 2026-05-06
parent_plan: PLAN.md
siblings: PHASE_1_TASKS.md, PHASE_2_TASKS.md
scope: /data workspace — file upload, dataframe preview, stat test picker, plot picker (PLAN §3 Phase 3)
out_of_scope: Phases 4–6 (PLAN §3.4–§3.6). Open questions Q2, Q3, Q4, Q7, Q8, Q9, Q10 (PLAN §7) — defer.
---

# Organon Dashboard — Phase 3 Tactical Plan

This document is the bridge between **PLAN.md** (strategic, locked) and code, for **Phase 3 only**. It mirrors `PHASE_1_TASKS.md` and `PHASE_2_TASKS.md` in shape.

PLAN.md cited inline as `(PLAN §X.Y)`. Prior phase plans cited as `(P1 §X)` / `(P2 §X)`. Phases 1 + 2 are **shipped + dogfooded** before Phase 3 starts; their structural choices (artifact protocol v2, SSE plumbing, project discovery, claude-runner cwd, DashboardShell, keyboard discipline, persona-config pattern) are inherited verbatim.

## Table of Contents

1. [Phase 3 scope recap](#1-phase-3-scope-recap)
2. [Tactical decisions resolved this document](#2-tactical-decisions-resolved-this-document)
3. [Repository layout for Phase 3](#3-repository-layout-for-phase-3)
4. [Atomic task list (T01–T36)](#4-atomic-task-list)
   - 4.1 [Track A — Bootstrap (T01–T03)](#41-track-a--bootstrap)
   - 4.2 [Track B — Artifact protocol v3 extensions (T04–T08)](#42-track-b--artifact-protocol-v3-extensions)
   - 4.3 [Track C — File upload pipeline (T09–T13)](#43-track-c--file-upload-pipeline)
   - 4.4 [Track D — Dataframe preview (T14–T17)](#44-track-d--dataframe-preview)
   - 4.5 [Track E — Stat test picker wizard (T18–T23)](#45-track-e--stat-test-picker-wizard)
   - 4.6 [Track F — Plot picker (T24–T29)](#46-track-f--plot-picker)
   - 4.7 [Track G — Skill teaching (T30–T32)](#47-track-g--skill-teaching)
   - 4.8 [Track H — Polish + Phase 3 acceptance (T33–T36)](#48-track-h--polish--phase-3-acceptance)
5. [Artifact JSON schemas](#5-artifact-json-schemas)
6. [API contracts](#6-api-contracts)
7. [Component prop contracts](#7-component-prop-contracts)
8. [npm dependencies (delta vs Phase 2)](#8-npm-dependencies-delta-vs-phase-2)
9. [Dev-setup runbook (delta vs Phase 2)](#9-dev-setup-runbook-delta-vs-phase-2)
10. [Phase 3 acceptance gate](#10-phase-3-acceptance-gate)

---

## 1. Phase 3 scope recap

Six deliverables from PLAN §3 Phase 3:

1. `/data` workspace: file uploader (CSV/XLSX/JSON/Parquet), drop zone, project file browser. (Track C)
2. Dataframe preview: first 50 rows + column types + per-column basic stats. (Track D)
3. Stat test picker: guided wizard (compare 2 groups? normality? sample size?) → recommends + runs. (Track E)
4. Plot picker: histogram, scatter, box, violin, heatmap, PCA, line — each with editable parameters in a side panel. (Track F)
5. Plot output: PNG + SVG + the underlying matplotlib/seaborn code, all saved to `projects/{slug}/figures/{fig_id}/`. (Track F)
6. Wired to `sci-data-analysis` (load, analyze, plot) + `sci-hypothesis` (power analysis from Validate Mode). (Track G)

**Out of scope:** image generation + region inpaint (Phase 4), manuscript draft section linking (Phase 5), notebook export (deferred to v0.3 — researchers can copy the generated `.py` sidecar).

The Phase 2 acceptance gate (P2 §10) must be green before Phase 3 starts.

---

## 2. Tactical decisions resolved this document

| # | Decision | Choice | Rationale |
|---|---|---|---|
| D1 | **Mixed orchestration** | Load + preview is **direct API** (`/api/data/load` calls a Python subprocess that runs `data_ops.load_and_profile`). Statistical test runs + plot generation go through **`/api/execute`** (skill-spawn) so the wizard's intent-routing benefits from LLM judgement on assumption checks. | Same channel split as P1 (direct lit search + via-skill toggle): direct paths are fast and deterministic; skill paths get LLM-assisted decisions. |
| D2 | **Raw file storage** | `<projectPath>/data/{file_id}.{ext}` for uploads. The dataframe artifact (preview JSON) lives at `<projectPath>/data/{file_id}.preview.json`. `file_id` = `data-{YYYYMMDD}-{6hex}` derived from `sha1(filename + size + first_kb)`. | Pass-through — no internal Parquet/Arrow normalisation. `sci-data-analysis` already handles CSV/XLSX/JSON/Parquet uniformly. |
| D3 | **Supported formats** | At upload: CSV, XLSX, JSON, Parquet. Validation by extension + magic-byte sniff. Reject + show error for everything else. Max upload size 200 MB (configurable via `DATA_MAX_UPLOAD_MB` env var). | Matches `sci-data-analysis` Step 1 capability. 200 MB ceiling guards against accidental binary uploads; researchers who actually need bigger files can override. |
| D4 | **Preview shape** | First 50 rows + per-column inferred type (numeric / categorical / datetime / text) + per-column stats (count, null_count, mean/std/min/max for numeric; unique_count + top-3 values for categorical; min/max for datetime). Computed server-side via a single Python subprocess call. | Renders fast; cheap to recompute on any column-type override. The 50-row cap matches PLAN §3 Phase 3 acceptance. |
| D5 | **Stat test recommendation logic** | Pure-TS mapping in `lib/data/stat-picker.ts`. Inputs: data shape (extracted from the dataframe artifact) + user wizard answers (groups count? paired? continuous-vs-categorical?). Output: ranked recommendations with reasoning. The skill is invoked **only to RUN** the chosen test (with assumption-check + plain-English interpretation). | Keeps the UI deterministic (same answers → same recommendation, every time). The skill handles the parts that need real numerical work + interpretation. |
| D6 | **Plot picker** | 7 plot kinds: histogram, scatter, box, violin, heatmap, PCA, line. Each kind has a fixed param schema (e.g. histogram: `{x_col, bins?, log_scale?, group_col?}`). UI generates a form from the schema; user edits; submit fires a skill spawn. | Schema-driven form is fewer LOC than per-kind components and easier to extend. |
| D7 | **Code recoverability** | Every plot run also persists the generating Python code as a sidecar at `<projectPath>/figures/{fig_id}/v1.py`. The figure's `index.json` references it. UI shows a "Copy code" button that pulls the file content into the clipboard. | PLAN §5 ("show me the code / data" escape hatch). Researchers paste into their own notebook and the run is reproducible end-to-end. |
| D8 | **Dataframe artifact wire shape** | `_artifact: dataframe` carries the lightweight 50-row preview + schema + per-column stats. NOT the full data — full data lives in the raw file referenced by `data_path`. The 50-row cap means an artifact line is ≤ ~100 KB even on wide tables. | Within the SSE stdout-line budget (P1 stdout chunk ≤ 256 KB). The full dataframe stays on disk; the dashboard reads it lazily for column-type overrides only. |
| D9 | **Figure ID format** | `fig-{YYYYMMDD}-{6hex}` — same shape as `hyp-` from P2 D4. Allocated dashboard-side **before** the skill spawn, embedded in the prompt. Phase 4 inpaint will produce v2/v3/... versions in the same `figures/{fig_id}/` dir. | Keeps Phase 4 layout compatible without changes. |
| D10 | **Stat-result artifact + persistence** | `_artifact: stat-result` carries: test name, test_statistic, p-value, effect size + CI, assumption-check verdicts, plain-English interpretation, code reference. Persists to `<projectPath>/results/{run_id}.json` where `run_id = stat-{YYYYMMDD}-{6hex}`. | Results are first-class artifacts that drafting will cite (Phase 5 `\stat{run_id}` shortcut). Forward-compat for Phase 5 wiring. |

---

## 3. Repository layout for Phase 3

What gets created or extended.

```
scientific-os/projects/briefs/organon-dashboard/src/
├── app/
│   ├── data/page.tsx                       # T14 — replaces P1 stub; server component
│   └── api/
│       ├── data/
│       │   ├── load/route.ts               # T11 — POST: upload + parse + emit dataframe artifact
│       │   ├── preview/[file_id]/route.ts  # T15 — GET: re-fetch preview (e.g. after column override)
│       │   ├── analyze/route.ts            # T20 — POST: fires sci-data-analysis run via /api/execute
│       │   └── plot/route.ts               # T26 — POST: fires plot generation via /api/execute
│       ├── stat-picker/route.ts            # T19 — POST: returns ranked recommendations from wizard answers
│       └── (everything else unchanged)
├── components/
│   ├── data/
│   │   ├── data-workspace.tsx              # T14 — composes the below; client component
│   │   ├── file-uploader.tsx               # T09 — drop zone + project file browser
│   │   ├── data-file-list.tsx              # T10 — list of uploaded files in current project
│   │   ├── dataframe-preview.tsx           # T16 — 50-row table + column header chips
│   │   ├── column-header.tsx               # T17 — per-column type pill + override menu
│   │   ├── stat-test-picker.tsx            # T18 — wizard form
│   │   ├── stat-recommendation.tsx         # T22 — recommendation card + run button
│   │   ├── stat-result-card.tsx            # T23 — renders stat-result artifact
│   │   ├── plot-picker.tsx                 # T24 — kind selector + param form
│   │   ├── plot-renderer.tsx               # T27 — renders figure artifact (PNG inline + SVG link + Copy code)
│   │   └── plot-history.tsx                # T28 — history of plots in current project
│   └── (Phase 1 + 2 unchanged)
└── lib/
    ├── data/
    │   ├── upload.ts                        # T11 — multipart upload handler
    │   ├── load.ts                          # T12 — Python subprocess wrapper (data_ops.load_and_profile)
    │   ├── preview.ts                       # T15 — read/refresh preview artifact
    │   ├── files.ts                         # T13 — list/remove uploaded files
    │   ├── id.ts                            # T11 — allocate file_id + fig_id + run_id
    │   ├── stat-picker.ts                   # T19 — pure-TS recommendation logic (D5)
    │   └── plot-schemas.ts                  # T25 — plot-kind → param schema map
    ├── results/
    │   └── store.ts                         # T29 — read/write stat-result artifacts under results/
    └── (Phase 1 + 2 unchanged)
```

---

## 4. Atomic task list

36 tasks, ≤4h each.

### 4.1 Track A — Bootstrap

| ID | Task | Effort | Risk | Depends on | Notes |
|---|---|---|---|---|---|
| **T01** | Append "Phase 3" callout to `README.md` (P1 T03) — what's new (`/data`, stat picker, plot picker), what's still stubbed (4–6), pointer to this file. | S | 🟢 | — | One paragraph + bullet diff. |
| **T02** | Confirm Phase 2 acceptance gate (P2 §10) is green. If anything regressed, fix before starting Phase 3. | S | 🟢 | — | Don't start Phase 3 on a regressing Phase 2 base. |
| **T03** | Verify the artifact parser already tolerates `_artifact: dataframe`, `stat-result`, `figure` lines (P1 §T37 forward-compat). Add a regression test for all three. | S | 🟢 | T02 | Smoke test for the protocol's forward-compat claim. |

### 4.2 Track B — Artifact protocol v3 extensions

| ID | Task | Effort | Risk | Depends on | Notes |
|---|---|---|---|---|---|
| **T04** | Refine `lib/artifacts/types.ts`: add concrete `DataframeArtifact`, `StatResultArtifact`, `FigureArtifact` interfaces matching §5. Update the discriminated `Artifact` union. | M | 🟢 | T03 | Phase 4 will refine `FigureArtifact` further (versioning); Phase 3 lays the v1 shape. |
| **T05** | Extend `lib/artifacts/persist.ts` dispatcher: add cases for `dataframe`, `stat-result`, `figure` calling new persisters from T13 / T29 / T27-prep. | S | 🟢 | T04, T13, T29 | Three switch-case inserts. |
| **T06** | Extend `lib/artifacts/render.ts`: register `dataframe → <DataframePreview>`, `stat-result → <StatResultCard>`, `figure → <PlotRenderer>`. | S | 🟢 | T16, T23, T27 | Same dispatcher pattern as P2 T07. |
| **T07** | Implement `lib/data/id.ts` — `allocateFileId(filename, size, firstKb): string`, `allocateFigId(): string`, `allocateRunId(prefix): string`. All three follow the `{prefix}-{YYYYMMDD}-{6hex}` shape. | S | 🟢 | T03 | `allocateFileId` is content-addressed (deterministic per file content); `fig` and `run` IDs are time+random. |
| **T08** | Document the three new artifact types in `tests/phase3-artifacts.md` with golden examples for the smoke test. | S | 🟢 | T04 | One example per type. |

### 4.3 Track C — File upload pipeline

| ID | Task | Effort | Risk | Depends on | Notes |
|---|---|---|---|---|---|
| **T09** | Build `<FileUploader>` (client) — HTML5 drop zone + file picker. Validates extension + size client-side. Streams via FormData to `/api/data/load`. | M | 🟡 | — | See §7.1. Drag-and-drop + click-to-pick both work. |
| **T10** | Build `<DataFileList>` (client) — lists uploaded files in `<projectPath>/data/`. Per-row: filename, size, uploaded_at, "Preview" button, "Remove" button. | M | 🟢 | T13 | See §7.2. |
| **T11** | Build `lib/data/upload.ts` — multipart parser + validator (magic-byte sniff). Writes raw file to `<projectPath>/data/{file_id}.{ext}` atomically (tmp + rename). | M | 🟡 | T07 | 200 MB cap (D3) enforced server-side too. Reject early with HTTP 413 if exceeded. |
| **T12** | Build `lib/data/load.ts` — spawns Python subprocess running `data_ops.load_and_profile(path)`. Captures stdout JSON (the `dataframe` artifact body). 30 s timeout. | L | 🟡 | T11 | Subprocess uses the shared sci-data-analysis venv; if missing, return a clean error pointing at `setup.sh`. |
| **T13** | Build `lib/data/files.ts` — `listFiles(projectPath)`, `removeFile(projectPath, file_id)`, `readPreview(projectPath, file_id)`. Atomic writes; idempotent removes. | M | 🟢 | T07 | Mirrors `lib/lit/library.ts` from P1. |

### 4.4 Track D — Dataframe preview

| ID | Task | Effort | Risk | Depends on | Notes |
|---|---|---|---|---|---|
| **T14** | Build `app/data/page.tsx` (server component): reads project from URL/localStorage default, calls `listFiles(projectPath)`, renders `<DataWorkspace>` client. | M | 🟢 | T13 | Server-side hydration — no flash-of-empty file list. |
| **T15** | Build `/api/data/preview/[file_id]/route.ts` — GET: read sidecar `{file_id}.preview.json`. POST: re-run preview (e.g. after a column-type override). | M | 🟢 | T11, T12 | See §6.2. |
| **T16** | Build `<DataframePreview>` (client) — sticky-header table, 50 rows, lazy-render via `<TableRow>` map. Column headers carry the `<ColumnHeader>` chip. | M | 🟢 | T14 | See §7.3. |
| **T17** | Build `<ColumnHeader>` (client) — per-column pill showing inferred type + override menu (numeric / categorical / datetime / text). Override fires re-preview through `/api/data/preview/[file_id]` POST. | M | 🟡 | T15 | See §7.4. Type override is critical when the inference gets a column wrong. |

### 4.5 Track E — Stat test picker wizard

| ID | Task | Effort | Risk | Depends on | Notes |
|---|---|---|---|---|---|
| **T18** | Build `<StatTestPicker>` (client) — multi-step wizard: (1) "what are you comparing?" (group / correlation / regression / contingency / power-analysis), (2) per-branch follow-up (groups count, paired? sample size? expected effect?), (3) Confirm → POST to `/api/stat-picker`. | L | 🟡 | T14 | See §7.5. ≤ 5 questions per branch. Cmd+Enter advances. |
| **T19** | Build `lib/data/stat-picker.ts` — pure-TS mapping (D5). Inputs: dataframe artifact + wizard answers. Outputs: ranked recommendations with reasoning + assumption flags. Unit-test against PHASE_3_TASKS Stat picker fixture set in `tests/phase3-stat-picker-fixtures.json`. | L | 🟡 | T07 | This is the load-bearing pure-logic component. Test coverage > 90%. |
| **T20** | Build `/api/data/analyze/route.ts` — POST: accepts the chosen recommendation + dataset path, fires `sci-data-analysis` via `/api/execute` with the prompt template `"Use sci-data-analysis to run {test_name} on {file_path}: {test_args}; active_project_slug={slug}; run_id={run_id}; emit _artifact: stat-result on completion"`. SSE pass-through. | M | 🔴 | T19, T28 | The `run_id` is pre-allocated server-side (T07). |
| **T21** | Build `/api/stat-picker/route.ts` — POST: thin wrapper over T19 returning `{recommendations: Recommendation[]}`. | S | 🟢 | T19 | See §6.3. |
| **T22** | Build `<StatRecommendation>` (client) — card showing recommended test + reasoning + assumption flags + "Run this test" button. Multiple cards stack if the picker returned multiple recommendations. | M | 🟢 | T18 | See §7.6. |
| **T23** | Build `<StatResultCard>` (client) — renders a `StatResultArtifact`. Sections: test name + statistic + p-value + effect size + CI; assumption verdicts (each with a 🟢/🟡/🔴 pill); plain-English interpretation; "Copy code" + "Cite in draft" (P5 placeholder, disabled). | M | 🟢 | T20 | See §7.7. |

### 4.6 Track F — Plot picker

| ID | Task | Effort | Risk | Depends on | Notes |
|---|---|---|---|---|---|
| **T24** | Build `<PlotPicker>` (client) — kind selector (7 buttons: histogram, scatter, box, violin, heatmap, PCA, line) + dynamic param form generated from `lib/data/plot-schemas.ts`. | L | 🟡 | T25 | See §7.8. |
| **T25** | Build `lib/data/plot-schemas.ts` — schema map per plot kind. Each schema names required + optional params with type hints (`column-name`, `int`, `bool`, `enum`). | M | 🟢 | T03 | Exporters: `getSchema(kind): PlotSchema`, `validateParams(kind, params): {ok, errors}`. |
| **T26** | Build `/api/data/plot/route.ts` — POST: accepts `{kind, params, file_id, project}`. Allocates `fig_id` (T07), fires `sci-data-analysis` via `/api/execute` with prompt template, SSE pass-through. | M | 🔴 | T25, T31 | Skill emits one `_artifact: figure` line at completion (T31). |
| **T27** | Build `<PlotRenderer>` (client) — given a `FigureArtifact`, renders the PNG inline (server-served at `/api/figures/{fig_id}/v1.png`), shows SVG download + "Copy code" button. | M | 🟢 | T26 | The PNG path is served via a thin static-file route (T27-static); SVG and `.py` sidecars too. |
| **T28** | Build `<PlotHistory>` (client) — list of plots generated this session (or persisted to `<projectPath>/figures/`). Click → re-renders in main canvas. | M | 🟢 | T27 | See §7.9. Phase 4 will swap this view for the same component the figures-workspace uses. |
| **T29** | Build `lib/results/store.ts` — read/write `<projectPath>/results/{run_id}.json` for `stat-result` artifacts. | M | 🟢 | T07 | Atomic writes; mirrors P1 lit/library.ts pattern. |

### 4.7 Track G — Skill teaching

| ID | Task | Effort | Risk | Depends on | Notes |
|---|---|---|---|---|---|
| **T30** | Update `.claude/skills/sci-data-analysis/SKILL.md` — add **Step 1.5 (artifact emission)** mirroring P1 T42 / P2 T40. Three emit paths: load → emit `_artifact: dataframe`; analyze → emit `_artifact: stat-result`; plot → emit `_artifact: figure` + write Python code sidecar to `figures/{fig_id}/v1.py`. Backward-compatible CLI markdown stays. | L | 🟡 | T04 | The schema lock is §5; skill update mirrors §5 verbatim. |
| **T31** | Document the **dashboard invocation contract** for sci-data-analysis: when prompt contains `active_project_slug={slug}` AND (`file_id={id}` OR `run_id={id}` OR `fig_id={id}`), use those values + emit JSON-line artifacts referencing them. | M | 🟡 | T30 | Same handshake pattern as P2 T42. |
| **T32** | Update `.claude/skills/sci-hypothesis/SKILL.md` Validate Mode (P2 T40 already added the hypothesis JSON line) — extend to ALSO emit `_artifact: stat-result` when the test runs hit `data_ops.run_statistical_test`. Power analysis emits `_artifact: stat-result` with a `mode: "power"` marker. | M | 🟢 | T30 | Phase 3's "wired to sci-hypothesis for power analysis" deliverable. |

### 4.8 Track H — Polish + Phase 3 acceptance

| ID | Task | Effort | Risk | Depends on | Notes |
|---|---|---|---|---|---|
| **T33** | Extend `<CommandPalette>` (P1 T22) with Phase 3 commands: `Go to Data`, `Upload data`, `Run stat test`, `Generate plot`, `Run sci-data-analysis`. | M | 🟢 | T18, T24 | Static commands. |
| **T34** | Add the `<PaperDetailDrawer>` cross-link from `<StatResultCard>` "Cite in draft" placeholder — disabled in Phase 3 with "Phase 5" tooltip. | S | 🟢 | T23 | Forward-stub. |
| **T35** | Manual test plan walk: upload `patient_data.csv` → 50-row preview within 5 s, types correctly inferred. "Compare control vs treatment" wizard → recommends t-test or Mann-Whitney based on Shapiro–Wilk. Run → result + interpretation + Copy code works. Plot picker → histogram with editable bins → renders within 3 s, saved to `figures/{fig_id}/v1.png`. | M | 🟡 | T17, T20, T26 | Matches PLAN §3 Phase 3 acceptance verbatim. |
| **T36** | Phase 3 ship checklist: README updated, `/data` reachable + functional, `npm run build` + typecheck exit 0, no console errors on cold load, `data/` + `figures/` + `results/` directories created lazily. | S | 🟢 | All preceding | Final gate. |

**Total: 36 tasks. ~5–7 working days.** PLAN §3 budget for Phase 3 = ~2 weeks.

---

## 5. Artifact JSON schemas

### 5.1 `_artifact: dataframe` (Phase 3)

```jsonc
{
  "_artifact": "dataframe",
  "schema_version": 1,
  "id": "data-20260520-9fa321",                  // file_id
  "project_slug": "drug-discovery-llm-eval",
  "filename": "patient_data.csv",
  "format": "csv",                               // "csv" | "xlsx" | "json" | "parquet"
  "size_bytes": 487213,
  "rows_total": 1247,                            // full row count (parsed once at load)
  "columns": [
    {
      "name": "age",
      "type": "numeric",                         // "numeric" | "categorical" | "datetime" | "text"
      "type_inferred_by": "auto",                // "auto" | "user-override"
      "null_count": 12,
      "stats": {"count": 1235, "mean": 54.2, "std": 12.7, "min": 18, "max": 89}
    },
    {
      "name": "treatment",
      "type": "categorical",
      "type_inferred_by": "auto",
      "null_count": 0,
      "stats": {"unique_count": 3, "top": [["control", 624], ["drug-a", 311], ["drug-b", 312]]}
    }
  ],
  "preview_rows": [                              // first 50 rows; values are stringified for safe JSON transport
    {"id": "1", "age": "54", "treatment": "control", "outcome": "responder"}
  ],
  "data_path": "projects/{slug}/data/data-20260520-9fa321.csv",
  "preview_path": "projects/{slug}/data/data-20260520-9fa321.preview.json",
  "uploaded_at": "2026-05-20T10:23:00.000Z",
  "library_path": "projects/{slug}/data/data-20260520-9fa321.preview.json"
}
```

### 5.2 `_artifact: stat-result` (Phase 3)

```jsonc
{
  "_artifact": "stat-result",
  "schema_version": 1,
  "id": "stat-20260520-1c84ee",                  // run_id
  "project_slug": "drug-discovery-llm-eval",
  "file_id": "data-20260520-9fa321",
  "test_name": "ttest_ind",                      // identifier matching data_ops.run_statistical_test
  "test_label": "Two-sample t-test (independent)",
  "mode": "analyze",                             // "analyze" | "power" | "validate"
  "params": {
    "value_col": "outcome_score",
    "group_col": "treatment",
    "alpha": 0.05
  },
  "test_statistic": 3.42,
  "p_value": 0.00067,
  "effect_size": {"name": "cohen_d", "value": 0.41, "ci_low": 0.18, "ci_high": 0.64},
  "n": 1247,
  "assumption_checks": [
    {"name": "normality_shapiro", "verdict": "pass", "p_value": 0.18},
    {"name": "equal_variance_levene", "verdict": "fail", "p_value": 0.001, "note": "Welch correction applied"}
  ],
  "interpretation": "Treatment group had higher outcome scores than control (Cohen's d = 0.41, 95% CI [0.18, 0.64], p < 0.001). Effect size is small-to-medium.",
  "code_path": null,                             // present when mode includes plotting; null for pure stat tests
  "results_path": "projects/{slug}/results/stat-20260520-1c84ee.json",
  "library_path": "projects/{slug}/results/stat-20260520-1c84ee.json",
  "created_at": "2026-05-20T10:25:00.000Z"
}
```

### 5.3 `_artifact: figure` (Phase 3 v1; Phase 4 extends)

```jsonc
{
  "_artifact": "figure",
  "schema_version": 1,
  "id": "fig-20260520-7e1003",                   // fig_id
  "project_slug": "drug-discovery-llm-eval",
  "kind": "plot",                                // "plot" | "image" (Phase 4)
  "version": 1,                                  // Phase 4 adds v2+
  "format": "png",
  "data_source": "data-20260520-9fa321",         // file_id when produced by sci-data-analysis; null for AI-generated
  "params": {"plot_kind": "histogram", "x_col": "age", "bins": 30, "log_scale": false},
  "caption": null,                               // populated on lock (Phase 4)
  "alt_text": null,                              // populated on lock
  "code_path": "projects/{slug}/figures/fig-20260520-7e1003/v1.py",
  "png_path": "projects/{slug}/figures/fig-20260520-7e1003/v1.png",
  "svg_path": "projects/{slug}/figures/fig-20260520-7e1003/v1.svg",
  "thumbnail_path": "projects/{slug}/figures/fig-20260520-7e1003/v1.thumb.png",
  "library_path": "projects/{slug}/figures/fig-20260520-7e1003/v1.png",
  "backend": "matplotlib",                       // "matplotlib" | "seaborn" | "gemini" | "fal-flux-fill" (Phase 4)
  "cost_cents": 0,                               // 0 for matplotlib; > 0 for Phase 4 AI gen
  "parent_version": null,                        // Phase 4 versioning
  "created_at": "2026-05-20T10:26:00.000Z"
}
```

---

## 6. API contracts

### 6.1 `POST /api/data/load`

**Request.** `multipart/form-data` with `file` (the upload), `project` (slug).

**Response 201.** `{"dataframe": DataframeArtifact}` — also persisted server-side; the artifact is also emitted on any active SSE if a skill spawn is in flight.

**Response 400 / 413 / 415.** Error per validation failure.

### 6.2 `GET|POST /api/data/preview/[file_id]`

#### `GET ?project={slug}` — returns the cached preview.
#### `POST ?project={slug}` body `{column_overrides?: {col: type}}` — re-runs preview with overrides; persists.

**Response 200.** `{"dataframe": DataframeArtifact}`.

### 6.3 `POST /api/stat-picker`

**Request.** `{file_id, project, answers: {...wizard fields...}}`.

**Response 200.** `{"recommendations": Recommendation[]}` (≤ 3 items, ranked).

### 6.4 `POST /api/data/analyze`

**Request.** `{project, file_id, recommendation_id, params}`.

**Response.** SSE stream (proxied from `/api/execute`); skill emits one `_artifact: stat-result` event at completion.

### 6.5 `POST /api/data/plot`

**Request.** `{project, file_id, kind, params}`.

**Response.** SSE stream; skill emits one `_artifact: figure` event at completion.

### 6.6 Static-file routes

`GET /api/figures/[fig_id]/v[n].png|svg|py` — serves the file from `<projectPath>/figures/{fig_id}/`. Cache-Control immutable; PNG returns `image/png`, SVG `image/svg+xml`, py `text/plain`.

---

## 7. Component prop contracts

### 7.1 `<FileUploader>`

```typescript
type FileUploaderProps = {
  project: string;
  acceptExtensions?: string[];                  // default ["csv","xlsx","json","parquet"]
  onUploaded: (df: DataframeArtifact) => void;
};
```

### 7.2 `<DataFileList>`

```typescript
type DataFileListProps = {
  files: DataframeArtifact[];
  activeFileId: string | null;
  onSelect: (file_id: string) => void;
  onRemove: (file_id: string) => void;
};
```

### 7.3 `<DataframePreview>`

```typescript
type DataframePreviewProps = {
  dataframe: DataframeArtifact;
  onColumnTypeChange: (col: string, type: ColumnType) => void;
};

type ColumnType = "numeric" | "categorical" | "datetime" | "text";
```

### 7.4 `<ColumnHeader>`

```typescript
type ColumnHeaderProps = {
  name: string;
  type: ColumnType;
  stats: ColumnStats;
  onChangeType: (next: ColumnType) => void;
};
```

### 7.5 `<StatTestPicker>`

```typescript
type StatTestPickerProps = {
  dataframe: DataframeArtifact;
  onSubmit: (answers: WizardAnswers) => void;
  loading?: boolean;
};
```

### 7.6 `<StatRecommendation>`

```typescript
type StatRecommendationProps = {
  recommendation: Recommendation;
  onRun: () => void;
  isRunning: boolean;
};

type Recommendation = {
  test_name: string;
  reasoning: string;
  assumption_flags: { name: string; verdict: "ok" | "warn" | "fail"; note?: string }[];
  rank: number;
};
```

### 7.7 `<StatResultCard>`

```typescript
type StatResultCardProps = {
  result: StatResultArtifact;
  onCopyCode?: () => void;                       // disabled if result.code_path is null
  onCiteInDraft?: () => void;                    // Phase 5; disabled-with-tooltip in Phase 3
};
```

### 7.8 `<PlotPicker>`

```typescript
type PlotPickerProps = {
  dataframe: DataframeArtifact;
  onSubmit: (kind: PlotKind, params: Record<string, unknown>) => void;
  loading?: boolean;
};

type PlotKind = "histogram" | "scatter" | "box" | "violin" | "heatmap" | "pca" | "line";
```

### 7.9 `<PlotRenderer>` + `<PlotHistory>`

```typescript
type PlotRendererProps = {
  figure: FigureArtifact;
  onCopyCode: () => void;
};

type PlotHistoryProps = {
  figures: FigureArtifact[];
  activeFigId: string | null;
  onSelect: (fig_id: string) => void;
};
```

### 7.10 `<DataWorkspace>` (composite)

```typescript
type DataWorkspaceProps = {
  project: string;
  initialFiles: DataframeArtifact[];
  initialFigures: FigureArtifact[];
  initialResults: StatResultArtifact[];
  initialFileId?: string;                        // ?file={id} deep link
};
```

---

## 8. npm dependencies (delta vs Phase 2)

**No new runtime dependencies.** Form generation, drop zone, and table all hand-rolled. SVG rendering is via `<img src="...svg">`; no charting library.

If a Phase 3 implementer wants drag-and-drop to feel snappier, lazy-add `react-dropzone` as a follow-on polish task; it is **not** required for the acceptance gate.

---

## 9. Dev-setup runbook (delta vs Phase 2)

### 9.1 Prerequisites (delta)

| Tool | Version | Check |
|---|---|---|
| Phase 2 acceptance gate | green | T02 |
| `sci-data-analysis` skill venv | populated | `.venv/bin/python -c "import pandas, scipy, matplotlib"` |

If the venv is missing scipy/matplotlib, run `.claude/skills/sci-data-analysis/scripts/setup.sh` once.

### 9.2 Environment variables

| Var | Required | Used by | What it provides | Without it |
|---|---|---|---|---|
| `DATA_MAX_UPLOAD_MB` | Optional | `lib/data/upload.ts` | Override 200 MB upload cap | 200 MB default |

### 9.3 Smoke test post-install

1. `/data` renders. Drop zone present.
2. Drop a CSV → preview appears within 5 s, columns typed correctly.
3. Click a categorical column header → menu shows numeric / categorical / datetime / text. Override → preview re-renders.
4. Click "Stat test" → wizard opens. Answer "compare 2 groups" + "treatment column" + "outcome column" + Confirm → recommendation card.
5. "Run this test" → SSE streams; `<StatResultCard>` lands within 30 s with verdict + interpretation.
6. "Plot" → kind picker + param form. Pick histogram + bins=30 + Generate → image renders within 10 s.
7. `ls projects/{slug}/figures/{fig_id}/` → v1.png + v1.svg + v1.py.
8. "Copy code" → clipboard contains the matplotlib script.

---

## 10. Phase 3 acceptance gate

- [ ] CSV upload → 50-row preview within 5 s; column types correctly inferred for a representative file.
- [ ] Column-type override re-renders preview within 2 s; persists for the session.
- [ ] Stat test picker wizard → at least one ranked recommendation with reasoning + assumption flags.
- [ ] "Run this test" → `<StatResultCard>` shows test statistic + p-value + effect size + plain-English interpretation within 30 s.
- [ ] Plot picker → histogram + scatter + box → all render within 10 s, saved to `figures/{fig_id}/`.
- [ ] Generated `.py` sidecar copies to clipboard and parses cleanly with `python -c "..."`.
- [ ] All Phase 1 + 2 workspaces still functional (no regression).
- [ ] `npm run build` + `npm run typecheck` exit 0.
- [ ] Smoke test §9.3 passes end-to-end.

After ticking all boxes: dogfood ≥ 1 week, then plan Phase 4.

---

*End of Phase 3 tactical plan.*
