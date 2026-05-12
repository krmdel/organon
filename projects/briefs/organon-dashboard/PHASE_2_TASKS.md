---
project: organon-dashboard
status: tactical-ready
phase: 2
created: 2026-05-06
parent_plan: PLAN.md
sibling: PHASE_1_TASKS.md
scope: /hypothesis workspace + 3-persona council fanout (PLAN §3 Phase 2)
out_of_scope: Phases 3–6 (PLAN §3.3–§3.6). Open questions Q2, Q3, Q4, Q7, Q8, Q9, Q10 (PLAN §7) — defer.
---

# Organon Dashboard — Phase 2 Tactical Plan

This document is the bridge between **PLAN.md** (strategic, locked) and code, for **Phase 2 only**. It mirrors `PHASE_1_TASKS.md` in shape: scope recap, decisions table, atomic tasks (T01..TXX) dependency-ordered, JSON schemas, API contracts, component prop contracts, npm deps, runbook, acceptance gate.

PLAN.md cited inline as `(PLAN §X.Y)`. Phase 1 plan cited as `(P1 §X)`. Phase 1 is **shipped** and not re-litigated here — its structural choices (artifact protocol v1, SSE plumbing, project discovery, claude-runner cwd, DashboardShell + Sidebar + Topbar + CommandPalette, keyboard discipline) are inherited verbatim.

Phase 2 starts only after Phase 1 has been in real use for ≥1 week (PLAN §10). This document writes the plan; implementation waits on that gate.

## Table of Contents

1. [Phase 2 scope recap](#1-phase-2-scope-recap)
2. [Tactical decisions resolved this document](#2-tactical-decisions-resolved-this-document)
3. [Repository layout for Phase 2](#3-repository-layout-for-phase-2)
4. [Atomic task list (T01–T46)](#4-atomic-task-list)
   - 4.1 [Track A — Bootstrap + decisions land (T01–T04)](#41-track-a--bootstrap--decisions-land)
   - 4.2 [Track B — Artifact protocol v2 extensions (T05–T10)](#42-track-b--artifact-protocol-v2-extensions)
   - 4.3 [Track C — Personas config + editor (T11–T16)](#43-track-c--personas-config--editor)
   - 4.4 [Track D — /hypothesis workspace (T17–T32)](#44-track-d--hypothesis-workspace)
   - 4.5 [Track E — API contracts (T33–T39)](#45-track-e--api-contracts)
   - 4.6 [Track F — Skill teaching (T40–T43)](#46-track-f--skill-teaching)
   - 4.7 [Track G — Polish + Phase 2 acceptance (T44–T46)](#47-track-g--polish--phase-2-acceptance)
5. [Artifact JSON schemas](#5-artifact-json-schemas)
6. [API contracts](#6-api-contracts)
7. [Component prop contracts](#7-component-prop-contracts)
8. [npm dependencies (delta vs Phase 1)](#8-npm-dependencies-delta-vs-phase-1)
9. [Dev-setup runbook (delta vs Phase 1)](#9-dev-setup-runbook-delta-vs-phase-1)
10. [Phase 2 acceptance gate](#10-phase-2-acceptance-gate)

---

## 1. Phase 2 scope recap

Six deliverables from PLAN §3 Phase 2, restated for tactical clarity:

1. `/hypothesis` workspace: hypothesis form (claim text + supporting-papers picker pulling from the project's library), "Generate via council" button. (Track D)
2. 3 persona panels render side-by-side: each shows that persona's critique + counter-evidence + suggested experiments. Configurable persona set per project (PLAN §7 Q5 resolved 2026-05-06: per-project `hypotheses/personas.json`, default Skeptic/Methodologist/Domain-expert, math swap to Gauss/Erdős/Tao). (Track C + D)
3. "Reconcile" button → produces a synthesis card: agreed claim + open questions + proposed experiment design. (Track D + F)
4. Hypothesis records persist to `projects/{slug}/hypotheses/{hyp_id}/hypothesis.json` with status (open / synthesized / supported / refuted / archived). Critiques persist as sidecars under the same directory. (Track B + E)
5. Each card shows linked papers (resolved from library by ID). Linked datasets surface as a disabled "Phase 3" badge. (Track D)
6. Wired to `sci-hypothesis` (Generate + future Validate) and `sci-council` (3-persona fan-out). Both teach the artifact protocol v2 emission pattern (P1 §T42 model). (Track F)

**Out of scope (deferred to later phases):** linked datasets (Phase 3), auto-experiment-design from reconcile (Phase 3 wires `sci-data-analysis` for power analysis), figure attachment to hypotheses (Phase 4), export-to-manuscript (Phase 5), council fan-out across more than 3 personas (deferred until breadth need surfaces).

The Phase 1 acceptance gate (P1 §10) must be green before Phase 2 starts.

---

## 2. Tactical decisions resolved this document

These are decisions PLAN.md left at the strategic level and PHASE_1_TASKS.md pre-specified in §5.3. Each is locked here so Phase 2 can ship without further deliberation. **Not re-litigation of Phase 1 decisions** — those remain locked.

| # | Decision | Choice | Rationale |
|---|---|---|---|
| D1 | **Orchestration channel for Generate + Reconcile** | Both fire through `/api/execute` (the SSE skill-spawn path from P1 §T15). The dashboard never orchestrates the per-persona fan-out — `sci-council` runs the parallel fan-out internally per its own `references/synthesis-protocol.md`. The dashboard is a UI + persistence layer that listens for `_artifact` events on the SSE stream. | Two reasons. (a) The council fan-out is LLM-driven (3 personas, opinionated, parallel) and already implemented in `sci-council` — re-implementing the orchestration in TS would duplicate methodology. (b) The cwd fix from P1 (claude-runner spawns from organon-root with `active_project_slug={slug}` in the prompt — see `context/learnings.md` 2026-05-06) means a single `claude -p` call with the right prompt does everything. |
| D2 | **Persona config storage** | Per-project file at `<projectPath>/hypotheses/personas.json`. Read once on workspace mount. If absent, the workspace writes a default of `[{name:"Skeptic"}, {name:"Methodologist"}, {name:"Domain-expert"}]`. A "Use math template" one-click swap rewrites it to `[{name:"Gauss"}, {name:"Erdős"}, {name:"Tao"}]`. Editable via a small inline UI: rename, reorder, replace; max 5 entries. | Resolves PLAN §7 Q5. Per-project rather than global because clinical, ML, and math projects co-exist in `projects/`. JSON file rather than DB to match P1 D2 (filesystem-only) and keep CLI-editability. |
| D3 | **Hypothesis on-disk layout** | Per hypothesis: a directory `<projectPath>/hypotheses/{hyp_id}/` containing `hypothesis.json` (the record) + `critiques/{persona-slug}.json` (one sidecar per persona). The flat-file forward-spec in P1 §5.3 (`hypotheses/{hyp_id}.json`) is **refined** here to a directory layout — the per-hypothesis dir cleanly accommodates Phase 3+ siblings (`experiments/{run_id}.json`, future linked-dataset receipts) without flat-file collisions. P1 §5.3 was a placeholder; this is the implementation. | Avoids the "is `hypotheses/{hyp_id}.json` a file or a folder?" ambiguity. Self-contained-per-hypothesis directories are easier for the user to grep, copy, and inspect from the CLI. |
| D4 | **Hypothesis ID format** | `hyp-{YYYYMMDD}-{6-char-hash}` where hash = first 6 hex chars of `sha1(claim + iso_timestamp)`. Pre-allocated by the dashboard on Generate-button click, **before** the skill spawn, and passed into the prompt as `hypothesis_id={hyp_id}`. The skill embeds that exact ID in every artifact line it emits, so the dashboard can attribute critiques to the right hypothesis without disambiguation. | Pre-allocation removes the post-hoc id-reconciliation problem (multiple hypothesis cards with the same claim happen — drafts, retries, re-runs). Date-prefix + hash is human-greppable + collision-resistant for the foreseeable future. |
| D5 | **Reconcile is a SECOND call** | Generate-via-council and Reconcile are two separate `/api/execute` invocations, not one. Generate emits 3 `persona-critique` artifacts + 1 `hypothesis` artifact (status `open`). The user reviews the critiques in the workspace; only then does Reconcile fire a second call (`sci-hypothesis` synthesis pseudo-mode), which emits an updated `hypothesis` artifact (status `synthesized`, with `synthesis_text`, `open_questions[]`, `experiment_design`). | Some hypotheses get killed at the critique-review gate. Forcing reconcile to be a separate user action saves a council call's worth of LLM budget on dead hypotheses, and matches the cognitive flow ("I read the critiques, now I commit to synthesizing"). |
| D6 | **Hypothesis status state machine** | `open` (just generated; critiques attached) → `synthesized` (reconcile fired; synthesis card present) → `supported` or `refuted` (user mark after later validation; Phase 3 wires `sci-hypothesis` Validate Mode). Any state → `archived` (user moves to history-only; renders dimmed in list view). Transitions are user-driven; the skill never sets `supported` / `refuted` itself. | Matches PLAN §3 Phase 2 deliverable 4. The `synthesized` intermediate state is added here because `open → supported/refuted` skips the synthesis check the dashboard wants to surface as an explicit step. |
| D7 | **Linked papers are referenced by ID, never embedded** | The `paper_ids: string[]` field in the hypothesis record stores only `PaperArtifact.id` values (e.g., `pmid-37889012`). The workspace resolves the embedding view-side via `listLibrary(projectPath)` (P1 `lib/lit/library.ts` — already implemented). If a paper has been removed from the library, the card renders the id as a tombstone with a "removed from library" tooltip; nothing crashes. | Single source of truth. Embedding the full PaperArtifact would create a stale-snapshot problem the moment the user enriches notes/tags. Tombstone-on-missing matches researcher mental model better than auto-pruning the link. |
| D8 | **Persona panel layout — width-responsive** | 3-column CSS grid above 1024px, vertical stack below. Each persona panel is a fixed-height card with a header (persona name + 1-letter avatar emoji + confidence pill) and a scrollable body containing 3 sub-sections in this order: **Critiques** (bullet list, 2–4 items), **Counter-evidence** (bullet list, 1–3 items), **Suggested experiments** (numbered list, 1–3 items). Schema in §5.2. | The PLAN §3 Phase 2 spec calls out "critique + counter-evidence + suggested experiments" as the three sub-fields. The council schema in `sci-council/references/synthesis-protocol.md` returns ranked approaches; this Phase 2 contract layers the dashboard's three-bucket presentation **on top of** the existing schema (the skill emits both — see T40 / §5.2). |
| D9 | **Cmd+K extensions** | Phase 2 adds new commands to the existing `<CommandPalette>` (P1 T22): `Go to Hypothesis`, `New hypothesis`, `Filter hypotheses by status:open|synthesized|supported|refuted|archived`, plus skill direct-fire entries for `sci-hypothesis` + `sci-council`. The cmdk plumbing itself is not touched. Cross-corpus search (papers, hypotheses) of the kind P1 D8 deferred is **still** out of scope until Phase 6 — the new entries are static commands, not live search. | Reuses Phase 1's structural cmdk install. Live cross-corpus search is a separate ergonomic concern that has its own scope (indexing, latency, tokenization) and lands in Phase 6. |
| D10 | **No new state library, no shadcn yet** | Phase 2 stays on hooks + URL state + localStorage like Phase 1. TanStack Query (PLAN §2.1, queued for v0.2) is **not** introduced in Phase 2. Shadcn/ui is **not** introduced in Phase 2 (P1 D10 still applies). | Adding a state library or component primitives library mid-phase changes too many knobs at once. Defer both to a dedicated v0.2 cleanup phase after Phase 2 ships. |

---

## 3. Repository layout for Phase 2

What gets created or extended. Items marked **[P1]** already exist from Phase 1 and are touched, not rewritten. Items marked **[stub]** carry over from Phase 1's stub set and are upgraded in this phase.

```
scientific-os/projects/briefs/organon-dashboard/
├── PLAN.md                                  # [P1]
├── PHASE_1_TASKS.md                         # [P1] shipped
├── PHASE_2_TASKS.md                         # (this file)
├── README.md                                # [P1] T03 — append "Phase 2 ships /hypothesis"
└── src/
    ├── app/
    │   ├── hypothesis/
    │   │   └── page.tsx                     # T17 — replaces P1 stub; server component
    │   └── api/
    │       ├── execute/route.ts             # [P1] T15 — UNCHANGED (artifact dispatcher already type-discriminated)
    │       ├── hypothesis/
    │       │   ├── route.ts                 # T33 — list/save/update hypothesis records
    │       │   ├── [hyp_id]/route.ts        # T34 — get/patch/delete one hypothesis
    │       │   └── reconcile/route.ts       # T35 — fires the reconcile claude -p call (proxy onto /api/execute pattern)
    │       └── personas/route.ts            # T36 — read/write personas.json
    ├── components/
    │   ├── shell/
    │   │   ├── command-palette.tsx          # [P1] T22 — extended in T44 with new commands
    │   │   └── (others unchanged)           # [P1]
    │   └── hypothesis/
    │       ├── hypothesis-workspace.tsx     # T17 — composes the below; client component
    │       ├── claim-form.tsx               # T18 — claim textarea + paper picker + Generate button
    │       ├── paper-picker.tsx             # T19 — multiselect over library entries
    │       ├── council-fanout.tsx           # T20 — 3-column grid of <PersonaPanel>
    │       ├── persona-panel.tsx            # T21 — single persona card (critiques / counter / experiments)
    │       ├── synthesis-card.tsx           # T22 — reconcile output card
    │       ├── hypothesis-history.tsx       # T23 — table of all hypotheses with status filters
    │       ├── hypothesis-row.tsx           # T24 — one row in history; click to detail
    │       ├── status-badge.tsx             # T25 — pill for open / synthesized / supported / refuted / archived
    │       ├── personas-editor.tsx          # T26 — inline editor for hypotheses/personas.json
    │       └── linked-papers-list.tsx       # T27 — resolves paper_ids[] against library, renders chip list with tombstones
    └── lib/
        ├── artifacts/
        │   ├── parser.ts                    # [P1] UNCHANGED — already tolerates Phase 2 types
        │   ├── persist.ts                   # T05 — extend dispatcher for hypothesis + persona-critique
        │   ├── render.ts                    # T07 — register hypothesis + persona-critique → renderers
        │   └── types.ts                     # T06 — replace UnknownArtifact with concrete HypothesisArtifact + PersonaCritiqueArtifact
        ├── hypothesis/
        │   ├── store.ts                     # T08 — read/write hypotheses/{hyp_id}/hypothesis.json
        │   ├── critiques.ts                 # T09 — read/write hypotheses/{hyp_id}/critiques/{persona}.json
        │   ├── id.ts                        # T10 — pre-allocate hyp_id (D4)
        │   └── personas.ts                  # T11 — read/write hypotheses/personas.json (D2)
        └── (everything else unchanged from P1)
```

The `personas-editor.tsx`, `claim-form.tsx`, `paper-picker.tsx`, and the directory at `src/lib/hypothesis/` are net-new. Everything else is either P1-existing-touched or P1-existing-unchanged.

---

## 4. Atomic task list

46 tasks. Each scoped to ≤ 4 hours. IDs are stable; cross-references use `T##`. "Depends on" lists prerequisites; tracks A–G can run mostly sequentially with intra-track parallelism noted.

**Legend.** Effort: S = ≤1h, M = ≤2h, L = ≤4h. Risk: 🟢 low, 🟡 medium, 🔴 high.

### 4.1 Track A — Bootstrap + decisions land

| ID | Task | Effort | Risk | Depends on | Notes |
|---|---|---|---|---|---|
| **T01** | Append a "Phase 2" callout to `README.md` (P1 T03) — what's new (`/hypothesis`, council fan-out), what's still stubbed (Phases 3–6), pointer to this file. | S | 🟢 | — | One paragraph + a "what changed since Phase 1" bullet list. |
| **T02** | Confirm Phase 1 acceptance gate (P1 §10) is green on the live working tree: 10 boxes ticked + smoke test §9.4 passes. If anything regressed, fix before starting Phase 2. | S | 🟢 | — | Don't start Phase 2 on a regressing Phase 1 base. |
| **T03** | Verify `/api/execute` parser already tolerates `_artifact: hypothesis` and `_artifact: persona-critique` lines (P1 §T37 spec said "ignore-with-warn"). Add a regression test that injects a forged stdout chunk with both new types and asserts no crash + expected console.warn. | S | 🟢 | T02 | Smoke regression for the protocol's forward-compat claim. |
| **T04** | Lock the per-project hypothesis directory convention by adding to root `.gitignore` (already excludes `projects/**/.organon/`): no new entry needed for `projects/**/hypotheses/` since project artifacts are already part of the working tree (PLAN §5.3). Document in README that the dashboard creates `hypotheses/` lazily. | S | 🟢 | T01 | Sanity check; almost always a no-op. |

### 4.2 Track B — Artifact protocol v2 extensions

Per D3 + D8. Reuses the parser/persist/SSE plumbing from P1 verbatim — only the dispatcher and the type unions are touched.

| ID | Task | Effort | Risk | Depends on | Notes |
|---|---|---|---|---|---|
| **T05** | Extend `lib/artifacts/persist.ts` dispatcher: add `case "hypothesis"` → calls `saveHypothesis()` from T08; add `case "persona-critique"` → calls `saveCritique()` from T09. Existing `paper` and `project` cases unchanged. | S | 🟢 | T08, T09 | One switch-case insert per type; the warn-fallback for unknown types stays for Phases 3+. |
| **T06** | Refine `lib/artifacts/types.ts`: replace the `UnknownArtifact` placeholder with concrete `HypothesisArtifact` and `PersonaCritiqueArtifact` interfaces matching §5.1 + §5.2. Other Phase 3+ types remain UnknownArtifact. Update the discriminated `Artifact` union. | M | 🟡 | T05 | Keep `schema_version: 1` for both new types (forward bump only when fields change). |
| **T07** | Extend `lib/artifacts/render.ts`: register `hypothesis → <HypothesisHistoryRow>` (T24) and `persona-critique → <PersonaPanel>` (T21). The render index is consumed by future workspaces that mount artifacts of arbitrary type; in Phase 2 the consumers are scoped to `/hypothesis`. | S | 🟢 | T06, T21, T24 | Allow list-of-artifact rendering via the same dispatcher as Phase 1's PaperCard. |
| **T08** | Implement `lib/hypothesis/store.ts`: `listHypotheses(projectPath): HypothesisArtifact[]`, `getHypothesis(projectPath, hyp_id)`, `saveHypothesis(projectPath, h: HypothesisArtifact): string`, `updateHypothesisStatus(projectPath, hyp_id, status, patch?)`, `deleteHypothesis(projectPath, hyp_id)`. Atomic writes (temp+rename, P1 lib/lit/library.ts pattern). Creates `hypotheses/{hyp_id}/` lazily on first save. | M | 🟢 | T06 | Read scans `hypotheses/*/hypothesis.json`; ignore unreadable / malformed entries. |
| **T09** | Implement `lib/hypothesis/critiques.ts`: `listCritiques(projectPath, hyp_id)`, `saveCritique(projectPath, c: PersonaCritiqueArtifact): string`, `deleteCritique(projectPath, hyp_id, persona_slug)`. Sidecar path: `hypotheses/{hyp_id}/critiques/{persona-slug}.json`. Persona slug = `slugify(persona.name)` (lowercase, kebab-case, ASCII-only). | M | 🟢 | T06, T08 | Slug collisions resolved by appending `-2`, `-3`, etc.; unlikely in practice (max 5 personas per project). |
| **T10** | Implement `lib/hypothesis/id.ts`: `allocateHypothesisId(claim: string): string` returning `hyp-{YYYYMMDD}-{6-char-hex}` per D4. Use the Web Crypto API (`crypto.subtle.digest`) on Node 20+. Pure function; no FS. Unit-tested for determinism (same input → same id) and uniqueness across realistic claim corpora. | S | 🟢 | T01 | The 6-char prefix is collision-resistant for ≤ ~16M hypotheses per day; sufficient. |

### 4.3 Track C — Personas config + editor

Per D2. The personas list is a per-project file edited via the workspace; the dashboard reads on mount and writes on edit.

| ID | Task | Effort | Risk | Depends on | Notes |
|---|---|---|---|---|---|
| **T11** | Implement `lib/hypothesis/personas.ts`: `listPersonas(projectPath): Persona[]`, `savePersonas(projectPath, ps: Persona[])`, `getDefaultPersonas(): Persona[]` (Skeptic/Methodologist/Domain-expert), `getMathTemplatePersonas(): Persona[]` (Gauss/Erdős/Tao). On read: if file missing, write defaults and return them. Atomic writes. | M | 🟢 | T01 | `Persona = {name: string, role?: string, avatar?: string}`. Avatar is a 1-character emoji or letter; if missing, derive from `name[0]`. |
| **T12** | Build `<PersonasEditor>` (T26 file) — a small inline UI with: list of current personas (drag-handle stub for reorder, name field, role field, remove button), `+ Add persona` button (cap = 5), `Use math template` button (one-click swap), `Reset to defaults` button. Save on blur or explicit save; no inline-save spinner — POST to `/api/personas` (T36) and toast on failure. | L | 🟡 | T11, T36 | See §7.6. Drag-reorder can be a Phase-2-polish item if `react-dnd` integration drags scope; the v1 of this editor is up-down arrow buttons. |
| **T13** | Wire `<PersonasEditor>` into the `<HypothesisWorkspace>` as a collapsible drawer in the right column. Default collapsed. The current persona names render as a header chip strip ("Personas: Skeptic · Methodologist · Domain-expert · ⚙ Edit"). | S | 🟢 | T12, T17 | Visible by default on first project visit (unconfigured projects); collapsed thereafter. localStorage flag. |
| **T14** | Add a unit test that confirms `getDefaultPersonas()` and `getMathTemplatePersonas()` are pure, immutable, and the slugify rule produces stable persona-slug values for `Erdős` (→ `erdos`), `Tao` (→ `tao`), `Domain-expert` (→ `domain-expert`). | S | 🟢 | T11 | The slug is the persistence key for critiques (T09); regressions here corrupt sidecars. |
| **T15** | Add a "personas-changed" runtime check to the workspace: if the user edits personas while a council fan-out is in flight, warn ("Personas change applied — current run will still use the old set"). | S | 🟢 | T12 | Avoids a confusing UX where critique sidecars come back tagged with old persona slugs after the user changed the list mid-run. |
| **T16** | Document the persona JSON shape and the math-template swap in the project README and in the inline editor's help tooltip. | S | 🟢 | T01, T12 | One paragraph in README + one tooltip line. |

### 4.4 Track D — /hypothesis workspace

The MVP feature. PLAN §6.2 has the layout sketch; this section turns it into wired components.

| ID | Task | Effort | Risk | Depends on | Notes |
|---|---|---|---|---|---|
| **T17** | Build `app/hypothesis/page.tsx` (server component): reads project from URL/localStorage default, calls `listHypotheses(projectPath)` + `listLibrary(projectPath)` + `listPersonas(projectPath)`, renders `<HypothesisWorkspace>` client component with initial state. | M | 🟢 | T08, T11 | Server-side hydration of saved hypotheses + library means the workspace populates on first paint; no flash-of-empty. |
| **T18** | Implement `<ClaimForm>` (client) — claim textarea (markdown ok, ~3 lines tall), `<PaperPicker>` slot, "Generate via council" submit button. Submits with `Cmd+Enter` (P1 §4.6). Validates: claim is non-empty + ≥ 1 paper picked (warn-but-allow if 0 papers). | M | 🟢 | T17, T19 | See §7.1. |
| **T19** | Implement `<PaperPicker>` (client) — multiselect over the project's library. Search box (substring match on title/journal/year), checkbox-style entries, selected-chip strip below. State is uplifted to the workspace. | M | 🟡 | T17 | Reuse PaperArtifact from `@/lib/artifacts/types`. ~50 LOC; no external multiselect lib. See §7.2. |
| **T20** | Implement `<CouncilFanout>` (client) — the wrapper that grids 3 `<PersonaPanel>` components above 1024px, stacks them below. Receives `critiques: PersonaCritiqueArtifact[]` and `personas: Persona[]`; maps personas[i] → critiques.find(c => c.persona_slug === slug(persona[i])). If a critique is missing for a persona, renders an empty-state ("Awaiting Erdős…" with spinner if run in progress, "No critique returned" if run is done and the persona failed). | M | 🟡 | T17, T21 | See §7.3. |
| **T21** | Implement `<PersonaPanel>` (client) — single persona card. Header (avatar + name + confidence pill). Body: 3 sub-sections from PersonaCritiqueArtifact (`critiques[]`, `counter_evidence[]`, `suggested_experiments[]`). "View raw" button reveals the original ranked-approaches block from `sci-council` schema (collapsed by default). | M | 🟡 | T20 | See §7.4. |
| **T22** | Implement `<SynthesisCard>` (client) — renders the synthesis fields from the hypothesis record after Reconcile (`synthesis_text`, `open_questions[]`, `experiment_design`). Disabled-with-tooltip if status === "open". Edit button is a Phase 5 placeholder. | M | 🟢 | T17 | See §7.5. |
| **T23** | Build `<HypothesisHistory>` (client) — table view of all hypotheses for the current project. Columns: claim (truncated), status pill, # critiques, # linked papers, created. Filters: status (multiselect) + search (substring on claim). | M | 🟢 | T17, T24, T25 | See §7.7. j/k keyboard nav on rows reuses P1's pattern. |
| **T24** | Implement `<HypothesisRow>` (client) — single row in the history table; click → opens detail (workspace switches focus to that hypothesis, URL `?hyp={id}`). | S | 🟢 | T17 | Pure presentational. |
| **T25** | Implement `<StatusBadge>` (client) — pill component for the 5 states (D6). Color tokens: open=blue, synthesized=violet, supported=green, refuted=red, archived=grey. Same Tailwind v4 palette as P1. | S | 🟢 | T17 | Single file, ~30 LOC. |
| **T26** | (Implemented in Track C T12) — `<PersonasEditor>`. Cross-listed for clarity. | — | — | T12 | No-op here. |
| **T27** | Implement `<LinkedPapersList>` (client) — receives `paper_ids: string[]` and `library: PaperArtifact[]`, renders chip strip. Missing paper → tombstone chip ("removed from library", greyed). Click chip → opens P1's `<PaperDetail>` drawer (cross-workspace link). | M | 🟡 | T17 | Cross-workspace coupling: the drawer component is in `components/lit/`; to render here, we either lift `<PaperDetail>` to `components/primitives/` or duplicate it. **Lock**: lift to `components/primitives/paper-detail-drawer.tsx` (one move; no behavior change). |
| **T28** | Wire ClaimForm submit → `/api/hypothesis` (POST T33) + then `/api/execute` with prompt template `"Use sci-council on hypothesis {id}: claim={claim}; linked_papers=[{ids}]; personas=[{names}]; active_project_slug={slug}"`. SSE events with `_artifact: hypothesis` (status=open) and `_artifact: persona-critique` (3 of them) auto-persist via P1 T40 dispatcher (extended in T05). Workspace UI updates as artifacts arrive. | L | 🔴 | T18, T20, T28-prompt-template, T05 | The prompt template is the contract between dashboard and skill (T40). Verify alignment between this template and `sci-council/SKILL.md` Step 1. |
| **T29** | Wire Reconcile button → `/api/hypothesis/reconcile` (POST T35) which fires `/api/execute` with prompt `"Use sci-hypothesis to synthesize hypothesis {id}: critiques=[…ids…]; active_project_slug={slug}"`. Skill emits one updated `_artifact: hypothesis` (status=synthesized + synthesis_text + open_questions + experiment_design). Workspace receives via SSE; row + synthesis card update. | L | 🔴 | T22, T29-prompt-template, T05 | Reconcile **does not** re-run the personas; it consumes the persisted critiques as input. |
| **T30** | Wire status transitions: `<StatusBadge>` is clickable → dropdown to mark `supported`, `refuted`, or `archived`. Calls `/api/hypothesis/{hyp_id}` PATCH (T34). Optimistic update, toast on failure. | M | 🟢 | T25, T34 | D6 transitions enforced server-side: `open → synthesized` is skill-only; `synthesized → supported/refuted/archived` is user-only; `open → archived` is allowed (kill before reconcile). |
| **T31** | URL state sync: `?hyp={id}` selects active hypothesis on cold load + browser back; deep-linkable. localStorage `organon.dashboard.hypothesis.lastHyp` mirrors but does not override URL (P1 D7 precedence). | S | 🟢 | T17 | Reuses P1's URL+localStorage pattern. |
| **T32** | Empty-state for `/hypothesis` when the project has no hypotheses + no library: friendly prompt with "Save 4 papers to your library first" link to `/lit?project={slug}`. Helps cold-start the workflow. | S | 🟢 | T17 | One illustrative call-to-action, ~20 LOC. |

### 4.5 Track E — API contracts

| ID | Task | Effort | Risk | Depends on | Notes |
|---|---|---|---|---|---|
| **T33** | Build `app/api/hypothesis/route.ts` — GET list, POST save (D4 pre-allocation flow returns the allocated id + library_path). See §6.1. | M | 🟢 | T08, T10 | POST allocates the id server-side via T10; returns it in the response so the client uses the same id when firing the skill. |
| **T34** | Build `app/api/hypothesis/[hyp_id]/route.ts` — GET, PATCH, DELETE. PATCH handles status transitions per D6; rejects invalid transitions with 409. | M | 🟢 | T08, T33 | See §6.2. |
| **T35** | Build `app/api/hypothesis/reconcile/route.ts` — POST `{project, hyp_id}` → spawns the reconcile skill via the same `/api/execute` SSE plumbing. Streams the SSE stream back to the client unchanged. | M | 🟡 | T15-prep, T08 | See §6.3. Implementation is a thin proxy onto `/api/execute` with a prompt-template wrapper; no new spawn machinery. |
| **T36** | Build `app/api/personas/route.ts` — GET, PUT. Validates: ≤ 5 personas, names non-empty, names unique within project. | M | 🟢 | T11 | See §6.4. |
| **T37** | Update `/api/runs` (P1 §6.3) to surface a `hypothesis_id?: string` field in run records when present (parsed from prompt). Helps `/runs` workspace eventually correlate runs with hypotheses (Phase 6). | S | 🟢 | — | Forward-compat; non-blocking for Phase 2. |
| **T38** | Verify `/api/execute` (P1) emits `event: artifact\ndata: ...` for the new types end-to-end: spawn `sci-hypothesis` from a smoke test prompt that triggers Generate Mode → assert ≥ 1 `_artifact: hypothesis` event arrives at the SSE client. | S | 🟢 | T03, T40 | Wired by P1 T40; this is the integration test. |
| **T39** | Add a `dynamic = "force-dynamic"` declaration to all new route files (matches P1 convention). | S | 🟢 | T33–T36 | One-line top-of-file. |

### 4.6 Track F — Skill teaching

The artifact protocol v2 emission pattern is the same one P1 T42 used for `sci-literature-research` (Step 1.5: emit `{"_artifact":"...",...}` JSON line per record). New skills, same convention. CLI users still see the existing markdown.

| ID | Task | Effort | Risk | Depends on | Notes |
|---|---|---|---|---|---|
| **T40** | Update `.claude/skills/sci-hypothesis/SKILL.md` — add **Step 1.5 (artifact emission)** mirroring `sci-literature-research/SKILL.md` Step 1.5: emit one `{"_artifact":"hypothesis", ...HypothesisArtifact}` JSON line on stdout for each hypothesis the skill produces (Generate Mode: 3–5 records; Validate Mode: 1 patch with status update; reconcile pseudo-mode: 1 record with status="synthesized"). Use `active_project_slug` and `hypothesis_id` from the prompt to populate `id` and on-disk paths. Backward-compatible with CLI users. | M | 🟡 | T06, T08 | The schema lock is §5.1 in this document; the skill update mirrors §5.1 verbatim. |
| **T41** | Update `.claude/skills/sci-council/SKILL.md` — add **Step 1.5 (artifact emission)** that emits one `{"_artifact":"persona-critique", ...PersonaCritiqueArtifact}` JSON line per persona, plus (when invoked with `hypothesis_id` in the prompt) a final `{"_artifact":"hypothesis", ...}` line that records the council's confidence header and links the critique sidecars by persona slug. Existing markdown synthesis output stays for CLI. | M | 🟡 | T06, T09 | The PersonaCritique schema in §5.2 maps the council's existing `references/synthesis-protocol.md` 3-ranked-approaches blob into the dashboard's three-bucket view (`critiques[]` / `counter_evidence[]` / `suggested_experiments[]`). The mapping is documented in the skill update so the same fan-out output serves both CLI and dashboard. |
| **T42** | Define + document the **dashboard invocation contract** in both SKILL.md files: when the prompt contains `active_project_slug={slug}` AND `hypothesis_id={id}` AND `personas=[{names}]` AND `linked_papers=[{ids}]`, the skill MUST (a) emit JSON-line artifacts for every record it produces, (b) use the provided `hypothesis_id` rather than minting a new one, (c) reference the linked-paper ids verbatim in the supporting-evidence block, (d) honor the persona name list (don't substitute a different set). | M | 🟡 | T40, T41 | This is the load-bearing handshake between dashboard and skills. Without it, the dashboard cannot attribute artifacts to the right hypothesis. |
| **T43** | Smoke-test the contract by firing both skills directly from `claude -p` with a hand-built prompt and asserting: stdout contains the expected JSON lines, and after persistence the `hypotheses/{hyp_id}/` directory contains 1 hypothesis record + 3 critique sidecars (Council Generate path) or 1 updated record (Reconcile path). | M | 🟡 | T40, T41, T42 | Document the test prompts in a `tests/phase2-skill-contract.md` reference so regressions are catchable. |

### 4.7 Track G — Polish + Phase 2 acceptance

| ID | Task | Effort | Risk | Depends on | Notes |
|---|---|---|---|---|---|
| **T44** | Extend `<CommandPalette>` (P1 T22) with the Phase 2 commands per D9: `Go to Hypothesis`, `New hypothesis (open /hypothesis with claim form focused)`, `Filter hypotheses by status:open/synthesized/supported/refuted/archived`, `Run sci-hypothesis (generate)`, `Run sci-council`. | M | 🟢 | T17, T22-P1 | Static command list — no live cross-corpus search (Phase 6). |
| **T45** | Manual test plan walk: write a claim in `<ClaimForm>`, pick 4 papers from library, click Generate → 3 persona panels render in parallel within 60s, each with ≥2 substantive critiques. Click Reconcile → synthesis card lands within 30s with ≥1 explicit open question. Mark hypothesis `supported` → status pill updates + filter still works. Hypothesis history shows the new record + filter status:supported returns it. | M | 🟡 | T28, T29, T30, T44 | Matches PLAN §3 Phase 2 acceptance verbatim. |
| **T46** | Phase 2 ship checklist: README updated, `/hypothesis` reachable + functional, no console errors on cold start, `npm run build` + `npm run typecheck` exit 0, `hypotheses/` directory properly created lazily, all D6 status transitions work end-to-end, persona editor saves correctly. | S | 🟢 | All preceding | Final gate before Phase 2 is considered done. Triggers PLAN §10 "use it for ≥1 week before Phase 3" step. |

**Total: 46 tasks. ~6–8 working days at moderate pace.** PLAN §3 budget for Phase 2 = ~2 weeks, leaves slack for the 🔴 risk items (T28 + T29 are the integration cliffs).

---

## 5. Artifact JSON schemas

These refine the forward-declaration in PHASE_1_TASKS.md §5.3. Phase 1's `paper` and `project` shapes are unchanged; only `hypothesis` and `persona-critique` are touched.

### 5.1 `_artifact: hypothesis` (Phase 2)

Refines the PHASE_1 §5.3 forward-spec (`hypothesis` row). On-disk path lands under `hypotheses/{hyp_id}/hypothesis.json` per D3.

```jsonc
{
  "_artifact": "hypothesis",                     // discriminator — required
  "schema_version": 1,                           // required, integer
  "id": "hyp-20260506-3a7c91",                   // required — D4 format: hyp-{YYYYMMDD}-{6-hex}
  "claim": "GLP-1 agonists reduce CV mortality at 18-month follow-up.",  // required, string; markdown ok
  "claim_short": "GLP-1 agonists ↓ CV mortality (18mo)",  // optional, 80-char summary for table view
  "project_slug": "drug-discovery-llm-eval",     // required
  "status": "open",                              // required — "open" | "synthesized" | "supported" | "refuted" | "archived" (D6)
  "paper_ids": ["pmid-37889012", "doi-10-1056-nejmoa2206286"],  // required, array; references PaperArtifact.id (D7)
  "personas_used": ["Skeptic", "Methodologist", "Domain-expert"],  // required when status >= open; the persona names this hypothesis was generated against
  "critique_files": [                            // required when status >= open; relative paths, populated as critiques persist
    "hypotheses/hyp-20260506-3a7c91/critiques/skeptic.json",
    "hypotheses/hyp-20260506-3a7c91/critiques/methodologist.json",
    "hypotheses/hyp-20260506-3a7c91/critiques/domain-expert.json"
  ],
  "synthesis_text": null,                        // optional, markdown; populated on reconcile
  "open_questions": [],                          // optional, array<string>; populated on reconcile (≥1 per D6 acceptance)
  "experiment_design": null,                     // optional, object; populated on reconcile (free-form per sci-hypothesis Design Mode shape)
  "council_confidence": null,                    // optional, "high" | "medium" | "low" — synthesised by sci-council
  "tags": [],                                    // optional, user-managed; pre-allocated for Phase 5+
  "notes": "",                                   // optional, user-editable scratchpad
  "created_at": "2026-05-12T14:23:00.000Z",      // required, ISO-8601
  "updated_at": "2026-05-12T14:25:11.000Z",      // required, ISO-8601 — bumps on every status / synthesis change
  "library_path": "projects/{slug}/hypotheses/hyp-20260506-3a7c91/hypothesis.json"  // required; relative to organon-root
}
```

**Implementation rules:**
- The `id` is allocated by the dashboard via T10 **before** the skill spawn. The skill receives it in the prompt and emits it back verbatim (D4).
- `critique_files` is computed by the dashboard at persistence time (T05); the skill does NOT need to know the on-disk paths. The skill emits the persona-critique records; the dashboard's persister wires up the path field.
- `paper_ids` are unique. Order is user-meaningful (top = primary supporting reference); the skill MUST preserve order in its supporting-evidence block.
- The persisted file always has `updated_at >= created_at`. On Reconcile, `updated_at` bumps; `created_at` does not.

### 5.2 `_artifact: persona-critique` (Phase 2)

```jsonc
{
  "_artifact": "persona-critique",               // discriminator — required
  "schema_version": 1,                           // required
  "hypothesis_id": "hyp-20260506-3a7c91",        // required — links to the parent hypothesis
  "persona": "Skeptic",                          // required — the human-readable persona name (matches one of HypothesisArtifact.personas_used)
  "persona_slug": "skeptic",                     // required — slugify(persona) per T11
  "confidence": "medium",                        // required — "high" | "medium" | "low"
  "critiques": [                                 // required, array of strings; ≥2 per PLAN §3 Phase 2 acceptance
    "Sample size (N=247) underpowered for the proposed CV mortality endpoint at 18mo.",
    "Selection bias: cohort excludes patients with chronic kidney disease, narrowing generalizability."
  ],
  "counter_evidence": [                          // required, array of strings; ≥1 if cited; [] if none
    "Husain 2019 (LEADER) shows GLP-1 effect attenuates beyond 24mo follow-up."
  ],
  "suggested_experiments": [                     // required, array of strings; ≥1
    "Pre-registered subgroup analysis stratified by baseline eGFR.",
    "Sensitivity analysis under MAR/MNAR missingness assumptions."
  ],
  "raw_council_block": "...",                    // optional — verbatim ranked-approaches text from sci-council schema, for the 'View raw' button
  "supporting_paper_ids": [                      // optional — paper ids the persona cited explicitly; subset of HypothesisArtifact.paper_ids + the persona's own additions
    "pmid-30415602"
  ],
  "library_path": "projects/{slug}/hypotheses/hyp-20260506-3a7c91/critiques/skeptic.json",  // required, populated by dashboard at persist
  "created_at": "2026-05-12T14:23:42.000Z"       // required, ISO-8601
}
```

**Mapping rules (sci-council ranked-approaches → 3-bucket view):**
- The council's per-persona output has 3 ranked approaches with `{description, P_BEAT, effort, dead_end_caveats}` (per `sci-council/references/synthesis-protocol.md`).
- For the dashboard's hypothesis-mode view: each approach's primary text becomes a **suggested experiment**; each `dead_end_caveat` is appended to **critiques**; any explicit "but this prior work shows otherwise" claim becomes **counter-evidence**.
- The skill is responsible for performing this mapping + emitting both forms (the dashboard's 3-bucket schema + the original ranked-approaches blob in `raw_council_block`). T41 documents this in `sci-council/SKILL.md`.

### 5.3 Updates to PHASE_1 §5.3 forward-declaration

| Type | PHASE_1 §5.3 path | Refined path (this document) |
|---|---|---|
| `hypothesis` | `projects/{slug}/hypotheses/{hyp_id}.json` | `projects/{slug}/hypotheses/{hyp_id}/hypothesis.json` (D3) |
| `persona-critique` | `projects/{slug}/hypotheses/{hyp_id}/critiques/{persona}.json` | unchanged in shape; `{persona}` is `slugify(name)` per T11 |

The other Phase 3+ types (`figure`, `dataframe`, `stat-result`, `section-draft`, `section-diff`) remain forward-declared; the parser still tolerates them.

---

## 6. API contracts

All routes are Next.js 16 App Router Route Handlers under `src/app/api/`. Default response is JSON; spawn endpoints are SSE. Conventions inherited from P1 §6 (project param, error shape, dynamic).

### 6.1 `GET|POST /api/hypothesis`

#### `GET /api/hypothesis?project={slug}`

**Response 200.**
```jsonc
{
  "project": "drug-discovery-llm-eval",
  "hypotheses": [HypothesisArtifact, ...],   // newest first by updated_at
  "total": 7
}
```

#### `POST /api/hypothesis`

Pre-allocates a hypothesis id (T10) + writes a stub record (status="open", `personas_used` from current personas.json, empty `critique_files`, empty synthesis fields). The client uses the returned id when firing the skill.

**Request.**
```jsonc
{
  "project": "drug-discovery-llm-eval",
  "claim": "GLP-1 agonists reduce CV mortality at 18-month follow-up.",
  "paper_ids": ["pmid-37889012", "doi-10-1056-nejmoa2206286"]
}
```

**Response 201.** `{hypothesis: HypothesisArtifact}` — full record with allocated id.

**Response 400.** `{"error": "claim required"}` on empty claim.

### 6.2 `GET|PATCH|DELETE /api/hypothesis/[hyp_id]`

#### `GET /api/hypothesis/{hyp_id}?project={slug}`

**Response 200.** `{hypothesis: HypothesisArtifact, critiques: PersonaCritiqueArtifact[]}` — combined view.

**Response 404.** `{"error": "Hypothesis not found"}`

#### `PATCH /api/hypothesis/{hyp_id}`

User-driven status transitions + free-form note edits (no skill invocation here).

**Request.**
```jsonc
{
  "project": "drug-discovery-llm-eval",
  "patch": {
    "status": "supported",                      // optional; D6 transitions enforced
    "notes": "Replicated in 2026-04 cohort.",   // optional
    "tags": ["cv-outcomes", "real-world-data"]  // optional
  }
}
```

**Response 200.** `{hypothesis: HypothesisArtifact}` (post-patch).

**Response 409.** `{"error": "Invalid status transition: open → supported"}` on disallowed D6 path.

#### `DELETE /api/hypothesis/{hyp_id}`

Removes the hypothesis directory and all critique sidecars. Confirmation enforced client-side; idempotent.

**Response 200.** `{"removed": true}` even if the directory was already absent.

### 6.3 `POST /api/hypothesis/reconcile`

Thin proxy onto `/api/execute` with the reconcile prompt template (D5).

**Request.**
```jsonc
{
  "project": "drug-discovery-llm-eval",
  "hyp_id": "hyp-20260506-3a7c91"
}
```

**Response.** SSE stream — same event shape as `/api/execute` (P1 §6.7), passed through unchanged. The skill emits one `_artifact: hypothesis` event with status="synthesized" and the dashboard's persister updates the on-disk record.

**Response 400.** `{"error": "hyp_id required"}`

**Response 409.** `{"error": "Hypothesis must have ≥1 critique to reconcile"}` — guards against running reconcile on a generate-failure record.

### 6.4 `GET|PUT /api/personas`

#### `GET /api/personas?project={slug}`

**Response 200.**
```jsonc
{
  "project": "drug-discovery-llm-eval",
  "personas": [
    {"name": "Skeptic", "role": "challenges every claim", "avatar": "S"},
    {"name": "Methodologist", "role": "checks study design", "avatar": "M"},
    {"name": "Domain-expert", "role": "field-specific knowledge", "avatar": "D"}
  ]
}
```

If the file is missing, the route writes the defaults from T11 and returns them.

#### `PUT /api/personas`

**Request.**
```jsonc
{
  "project": "drug-discovery-llm-eval",
  "personas": [
    {"name": "Gauss", "role": "algebraic / number-theoretic", "avatar": "G"},
    {"name": "Erdős", "role": "probabilistic / extremal", "avatar": "E"},
    {"name": "Tao", "role": "harmonic / arithmetic-combinatorics", "avatar": "T"}
  ]
}
```

**Response 200.** `{personas: Persona[]}` (echo).

**Response 400.** `{"error": "personas: max 5"}` or `{"error": "duplicate persona name"}` or `{"error": "name required"}`.

### 6.5 `POST /api/execute` (P1, unchanged)

The Phase 1 contract (P1 §6.7) is reused as-is. The artifact event type is already type-discriminated; new types (`hypothesis`, `persona-critique`) are dispatched by the persister extension in T05.

---

## 7. Component prop contracts

All TypeScript-strict. Client components marked `"use client"`. Phase 1 prop contracts (P1 §7) unchanged.

### 7.1 `<ClaimForm>`

```typescript
type ClaimFormProps = {
  initialClaim?: string;                        // hydrated from URL or draft
  initialPaperIds?: string[];                   // hydrated from URL or draft
  library: PaperArtifact[];                     // for the picker
  onSubmit: (params: { claim: string; paper_ids: string[] }) => Promise<void>;
  loading?: boolean;
};
```

Submits on `Cmd+Enter` (P1 §4.6). Empty claim disables submit; 0 papers warn-but-allow.

### 7.2 `<PaperPicker>`

```typescript
type PaperPickerProps = {
  library: PaperArtifact[];
  value: string[];                              // selected paper_ids
  onChange: (ids: string[]) => void;
};
```

Internal: search box (substring match), checkbox list (paginated to 50 with "show more"), selected-chip strip. No external multiselect lib.

### 7.3 `<CouncilFanout>`

```typescript
type CouncilFanoutProps = {
  personas: Persona[];                          // from personas.json
  critiques: PersonaCritiqueArtifact[];         // some may be missing during a live run
  hypothesisId: string;
  isRunning: boolean;
};
```

Layout per D8: 3-column grid above 1024px, vertical stack below. Missing-persona slot renders empty-state (spinner if `isRunning`, "No critique returned" otherwise).

### 7.4 `<PersonaPanel>`

```typescript
type PersonaPanelProps = {
  persona: Persona;
  critique: PersonaCritiqueArtifact | null;     // null while pending
  isRunning: boolean;
};
```

Header: avatar + name + confidence pill (color from D6 + role tooltip). Body sub-sections in fixed order: Critiques / Counter-evidence / Suggested experiments. "View raw" reveals `raw_council_block` (collapsible).

### 7.5 `<SynthesisCard>`

```typescript
type SynthesisCardProps = {
  hypothesis: HypothesisArtifact;               // null synthesis fields → empty-state
  onMarkSupported: () => void;
  onMarkRefuted: () => void;
  onArchive: () => void;
};
```

Renders only when `status !== "open"`. Shows synthesis_text (markdown), open_questions list, experiment_design summary. Mark-supported / mark-refuted / archive buttons → PATCH `/api/hypothesis/{hyp_id}` (T34).

### 7.6 `<PersonasEditor>`

```typescript
type PersonasEditorProps = {
  initial: Persona[];
  onSave: (personas: Persona[]) => Promise<void>;
  onClose: () => void;
};

type Persona = {
  name: string;
  role?: string;
  avatar?: string;                              // 1-char emoji or letter
};
```

UI: list of current personas with up/down + remove + role-input. `+ Add` button (cap 5, disabled at limit). `Use math template` and `Reset to defaults` shortcuts. Save on explicit click; closes on success.

### 7.7 `<HypothesisHistory>`

```typescript
type HypothesisHistoryProps = {
  hypotheses: HypothesisArtifact[];
  library: PaperArtifact[];                     // for resolving paper-count column
  filter: { status: HypothesisStatus[]; query: string };
  onFilterChange: (f: { status: HypothesisStatus[]; query: string }) => void;
  onSelect: (hyp_id: string) => void;
  focusedIdx: number;                           // for j/k nav
};

type HypothesisStatus = "open" | "synthesized" | "supported" | "refuted" | "archived";
```

Columns: claim (truncated 80 chars) · status pill · #critiques · #linked-papers · created. j/k moves focus; Enter selects.

### 7.8 `<HypothesisRow>`

```typescript
type HypothesisRowProps = {
  hypothesis: HypothesisArtifact;
  paperCount: number;                            // pre-resolved by parent
  isFocused: boolean;
  onClick: () => void;
};
```

Single row. Click → `onClick`. Focus highlight via `aria-selected` + tw class.

### 7.9 `<StatusBadge>`

```typescript
type StatusBadgeProps = {
  status: HypothesisStatus;
  onChange?: (next: HypothesisStatus) => void;  // omitted = read-only pill
};
```

When `onChange` is provided, click → dropdown with valid D6 transitions only.

### 7.10 `<LinkedPapersList>`

```typescript
type LinkedPapersListProps = {
  paperIds: string[];
  library: PaperArtifact[];
  onOpenPaper?: (paper: PaperArtifact) => void; // null/missing → no-op (Phase 2 always provides)
};
```

Resolves each id against library; missing → tombstone chip. Click chip → opens `<PaperDetailDrawer>` (T27 lift).

### 7.11 `<HypothesisWorkspace>` (composite)

```typescript
type HypothesisWorkspaceProps = {
  project: string;
  initialHypotheses: HypothesisArtifact[];
  initialLibrary: PaperArtifact[];
  initialPersonas: Persona[];
  initialHypId?: string;                       // for ?hyp={id} deep links
};
```

Internal state mirrors P1 `<LitWorkspace>` patterns: URL sync on `?hyp`, j/k focus on history rows, Cmd+Enter submits ClaimForm, Esc closes drawers/editors.

---

## 8. npm dependencies (delta vs Phase 1)

**No new runtime dependencies.** Everything Phase 2 needs is in P1 §8.1: cmdk + react-hotkeys-hook + Tailwind v4 + Next 16 + React 19. The persona-editor and council-fanout components are built on raw Tailwind + native `<select>`/`<input>`. The drag-reorder UX in `<PersonasEditor>` (T12) uses up/down arrow buttons — no `react-dnd` or `@dnd-kit/*`.

If a Phase 2 implementer wants drag-and-drop reorder, that becomes a follow-on polish task; out of scope for the Phase 2 acceptance gate.

**No new dev dependencies.** TypeScript-strict + Next.js test infra unchanged.

---

## 9. Dev-setup runbook (delta vs Phase 1)

For a fresh developer starting Phase 2 work after Phase 1 has shipped.

### 9.1 Prerequisites (delta)

| Tool | Version | Check |
|---|---|---|
| Phase 1 acceptance gate (P1 §10) | green | T02 |
| `sci-hypothesis` skill | installed | `ls .claude/skills/sci-hypothesis/SKILL.md` |
| `sci-council` skill | installed | `ls .claude/skills/sci-council/SKILL.md` |

Both skills exist on disk in the current Organon install; Phase 2 only modifies their SKILL.md (T40 + T41) and adds a smoke-test reference (T43).

### 9.2 Environment variables

No new env vars. The skills reuse the existing keys (`NCBI_API_KEY` and friends) for any literature-side calls during Generate Mode.

### 9.3 First-run sequence (delta)

```bash
# 1. From Organon repo root, confirm Phase 1 dashboard runs cleanly
cd projects/briefs/organon-dashboard
npm run typecheck && npm run build && npm run dev
# Listening on http://localhost:8769 — open /lit, save 4 papers to a project's library

# 2. Visit /hypothesis (replaces the Phase 1 stub)
open http://localhost:8769/hypothesis?project={slug}

# 3. The personas.json file is created lazily on first visit — verify
ls projects/{slug}/hypotheses/personas.json
cat projects/{slug}/hypotheses/personas.json
# Should show the default Skeptic / Methodologist / Domain-expert set

# 4. Smoke test the contract: fire sci-council via /api/execute with a hand-built prompt
#    (doc'd in tests/phase2-skill-contract.md per T43)
```

### 9.4 Smoke test post-install

1. `/hypothesis` renders. Personas chip strip shows the default three.
2. Claim textarea + paper picker functional. Pick 4 papers from library → chip strip shows 4.
3. Click Generate → SSE stream opens, `<CouncilFanout>` shows 3 spinners, then 3 persona panels populate within 60s.
4. Each panel has ≥2 critiques (D8 + PLAN acceptance).
5. `ls projects/{slug}/hypotheses/{hyp_id}/` → `hypothesis.json` + `critiques/skeptic.json` (or matching slug) + 2 more critique sidecars.
6. Click Reconcile → synthesis card lands within 30s; ≥1 entry in `open_questions[]`.
7. Click status pill → mark `supported` → status badge updates + the row in History reflects it.
8. Cmd+K → "Filter hypotheses by status:supported" → only that hypothesis in the table.

Any failure here blocks T46 (Phase 2 acceptance).

### 9.5 Common failure modes (delta)

| Symptom | Likely cause | Fix |
|---|---|---|
| "Generate" fires but no persona panels populate | Skill teaching (T40/T41) not landed; only markdown in stdout | Verify SKILL.md Step 1.5 added; rerun T43 smoke test |
| `_artifact: persona-critique` parse error in `/api/execute` logs | `persona_slug` missing or `hypothesis_id` mismatch | Check the dashboard prompt template (T28) — every required field present? |
| Critique sidecars present but `<CouncilFanout>` shows empty slots | Persona name mismatch between persona-critique line and personas.json | T15 warning is the canonical heuristic; also verify slugify rule (T14) |
| Reconcile fires but synthesis card empty | sci-hypothesis emitted markdown only, no JSON line for the synthesized hypothesis | T40 missing Step 1.5 for reconcile path; rerun T43 |
| Persona editor save → 400 | name uniqueness check in T36 | Check for duplicate persona names; the editor itself should disable Save in this state but the API also enforces |
| `hyp_id` collisions across two simultaneous Generate clicks | T10 hash uses `claim + iso_timestamp` — same millisecond + same claim = same id | Astonishingly rare; if observed, append the user's session id to the hash input |

---

## 10. Phase 2 acceptance gate

PLAN §3 Phase 2 acceptance criteria, restated as a binary checklist. Phase 2 ships when **every box is ticked**.

- [ ] Researcher writes a claim into `<ClaimForm>` and picks 4 papers from library as supporting evidence.
- [ ] Generate → 3 persona panels render in parallel within 60s.
- [ ] Each panel has ≥2 substantive critiques (not just "looks good") — manual quality check on a real claim.
- [ ] Reconcile → produces a synthesis card with at least one explicit `open_question`.
- [ ] Hypothesis history table shows the new card with a status filter (open / synthesized / supported / refuted / archived).
- [ ] Status transitions follow D6: `open → archived` and `synthesized → supported|refuted|archived` accepted; invalid transitions return 409.
- [ ] Persona editor saves correctly: rename, reorder (or up/down), reset-to-default, math-template-swap all persist to `hypotheses/personas.json` and survive page reload.
- [ ] All sidebar links navigate without 404; Phase 1 workspaces still functional (no Phase 1 regression).
- [ ] `npm run build` exits 0.
- [ ] `npm run typecheck` exits 0 with strict mode on.
- [ ] No console errors on cold-load of `/hypothesis`, `/lit`, or `/`.
- [ ] Smoke test §9.4 passes end-to-end.
- [ ] T43 skill-contract smoke (Generate path + Reconcile path) is documented in `tests/phase2-skill-contract.md` and reproducible.

After ticking all boxes: hand to Kerem for the "use it for ≥1 week before Phase 3" step (PLAN §10), gather feedback into `context/learnings.md` under `## organon-dashboard`, then plan Phase 3 (Data + Statistical Analysis workspace).

---

*End of Phase 2 tactical plan. Next document is `PHASE_3_TASKS.md`, written only after Phase 2 ships and Phase 3 unblockers are clear.*
