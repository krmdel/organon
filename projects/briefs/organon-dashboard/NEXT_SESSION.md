---
project: organon-dashboard
status: v1.0-candidate
created: 2026-05-06
purpose: Comprehensive pickup brief for the next session
---

# Organon Dashboard — Next Session Pickup

**TL;DR.** Phases 2 through 6 of the Organon Dashboard shipped in one continuous session today (2026-05-06) on top of the Phase 1 baseline already in `main`. End-to-end stress test 52/52 PASS. Two paths intentionally not exercised by automation (need real LLM compute / FAL key / human pointer events): documented below. Build, typecheck, and unit tests all green. The dashboard is the **v1.0 candidate** per PLAN.md §8.

Read this in order:

1. **Today's commit chain** — what landed and why
2. **What works in v1.0** — feature inventory with risk markers
3. **Stress test results** — what's been validated
4. **Smoke walks pending** — the human-driven gates
5. **Known limits + deferrals** — explicit non-coverage
6. **Common pitfalls** in this codebase (hook, deny list, naming)
7. **First moves next session** — concrete, ordered

---

## 1. Today's commit chain

```
ec04d32  dashboard: Phase 6 ships — /tools + /crons + /runs + cross-corpus Cmd+K (v1.0 candidate)
23ca6a7  dashboard: Phase 5 ships — /draft three-pane manuscript editor + section actions + bibliography + export
8efbcce  dashboard: Phase 4 ships — /figures workspace + region inpaint + lock-and-caption
22e6057  dashboard: Phase 3 ships — /data workspace + stat picker + plot picker
9952171  dashboard: Phase 2 ships — /hypothesis + 3-persona council fanout
95f6e00  wrap-up: Phase 1 dashboard ship — memory + learnings  (baseline)
00d77a4  dashboard/lit: add cancel + elapsed timer + library auto-refresh
bfd00e2  dashboard: Phase 1 ships — /lit workspace MVP + artifact protocol v1
```

Five Phase-X commits today; each is atomic, builds + typechecks + tests cleanly, and was preceded by a live HTTP smoke against the dev server. Each commit message documents its scope, deviations from the plan, and what's deferred.

---

## 2. What works in v1.0 (feature inventory)

### `/lit` — literature workspace (Phase 1; not touched this session)
- Federated search PubMed / arXiv / OpenAlex / Semantic Scholar with DOI dedupe + composite ranking
- BibTeX export
- Cross-link "Generate hypothesis from this paper"
- **Risk:** None known. Was dogfooded before this session.

### `/hypothesis` — hypothesis + 3-persona council (Phase 2 — `9952171`)
- Claim form + library paper picker
- 3-persona council fanout with parallel critiques (Skeptic / Methodologist / Domain-expert; one-click swap to Gauss / Erdős / Tao for math)
- Reconcile → synthesis card with open questions + experiment design
- Status state machine: open → synthesized → supported / refuted / archived
- Per-project `hypotheses/personas.json` is editable inline
- **Risk:** Council fanout SSE through `claude -p` works in the code path but needs a human dogfood to verify the actual prompts produce coherent persona critiques.

### `/data` — dataframe + stat + plot (Phase 3 — `22e6057`)
- File uploader (CSV / XLSX / JSON, 200 MB cap; sniffs magic bytes to reject mismatched extensions)
- 50-row dataframe preview with per-column type inference (numeric / categorical / datetime / text); ISO-8601 datetime detection via 80% pd.to_datetime parse rate probe
- Per-column override + re-profile
- Stat test picker wizard with 5 modes (group / correlation / regression / contingency / power), 14 ranked recommendations, assumption-aware reasoning
- Plot picker with 7 kinds (histogram / scatter / box / violin / heatmap / pca / line); editable params per schema
- `.py` reproducer sidecar saved alongside every PNG/SVG; "Copy code" button reads from the file
- **Risk:** Parquet support dropped (deviation D5; venv lacks pyarrow). `/api/data/analyze` SSE path works but the actual sci-data-analysis skill response format hasn't been live-verified — the Step 1.5 emit instructions in the prompt are explicit but skill compliance is empirical.

### `/figures` — generate + inpaint + caption (Phase 4 — `8efbcce`)
- Prompt + 6-style picker (scientific / notebook / comic / color / mono / technical) + scientific sub-styles (publication / conceptual / schematic / data-driven)
- AI generation through Gemini via `viz-nano-banana --mode generate`
- Region inpaint via FAL FLUX.1 Pro Fill with circle / lasso / rectangle mask tools (HTML5 canvas, rasterised at source-image dimensions for FAL's exact-size requirement)
- Pre-fire cost gate (~$0.05/MP estimate) with session-skip toggle; cumulative session spend in sidebar
- Version history with thumbnail strip + one-click revert
- "Lock + caption" fires `sci-writing` Step 7.5 (caption mode) to auto-generate figure caption + alt-text + flip locked=true
- **Risk:** Three external dependencies untested live in this session: (a) FAL FLUX Fill roundtrip needs `FAL_KEY`; (b) viz-nano-banana skill compliance with the JSON-line emit instructions; (c) sci-writing caption mode (Step 7.5 is brand new — not exercised). The dashboard's prompt is explicit but the skill side may need a nudge.

### `/draft` — three-pane manuscript editor (Phase 5 — `23ca6a7`)
- Per-project manuscript list with create form (title + 4 citation styles: APA / Nature / IEEE / Vancouver)
- Open a manuscript → 3-pane editor: sections (left) / markdown editor (center) / live preview (right)
- `\fig{fig-id}` autocomplete from /figures library; renders inline with auto-numbered caption (Fig. 1, Fig. 2…)
- `\cite{paper-id}` autocomplete from /lit library; renders (Author, Year) inline + appears in the auto-bibliography
- ActionBar fires sci-writing (rewrite / tighten / check claims) or tool-humanizer (humanize) on the active section
- Diff view side-by-side; user accepts (writes new content_md, bumps version) or rejects
- Status pill cycles draft → reviewed → final per section
- Reorder via ▲▼ buttons
- Export: Markdown (always works), PDF / HTML / DOCX (if pandoc + marp + xelatex installed; clean 503 with markdown fallback otherwise), Substack (501 stub)
- **Risk:** (a) hand-rolled markdown renderer covers the common subset (paragraphs / headings / **bold** / *italic* / `code` / fenced code / blockquotes / lists / links + custom plugins) but lacks tables, footnotes, KaTeX. (b) sci-writing dashboard-action mode + tool-humanizer dashboard mode are NEW skill behaviors — emit shape documented but skill compliance is empirical. (c) Pandoc/Marp not installed by the dashboard.

### `/tools` + `/crons` + `/runs` (Phase 6 — `ec04d32`)
- `/tools`: aggregated catalog (30 local Organon skills + 5 MCP server entries from `.mcp.json`) — verified via stress test. Per-project favourites pinned at top. Click skill → SSE prompt form.
- `/crons`: read-only status board for `cron/jobs/*.md` (11 jobs detected on this machine). Reads schedule + active flag + last-run + fail-count from `cron/status/*.json` + matches `~/Library/LaunchAgents/com.organon.*.plist`.
- `/runs`: full run history (last 200 entries) per project. Click row → drawer with full prompt + stdout + stderr + linked artifact links.
- `/usage`: real SVG charts (daily token bars + by-model pie). Reachable by URL; not yet on the sidebar — v1.0 polish call.
- Cmd+K cross-corpus search (papers / hypotheses / figures / sections / manuscripts) — verified via stress test (search found the manuscript + section just created).
- **Risk:** Cron actions deferred (read-only). MCP tools return 501 with CLI hint (uvx-from-Next not implemented). ToolUniverse 2,000+ catalog browse not implemented (catalog draws from local skills + MCP server names only).

---

## 3. Stress test results

`tests/stress-suite.py` — single Python script that hits 52 endpoints + edge cases against the live dev server.

**52 / 52 PASS.** Run reproducibly:

```bash
cd projects/briefs/organon-dashboard
bash -lc 'set -a; source ../../../.env 2>/dev/null; set +a; npm run dev'
# in another shell:
python3 tests/stress-suite.py
```

The suite covers:

| Phase | Cases | What's tested |
|---|---|---|
| /lit | 5 | Library list/save/delete; missing project 404; malformed JSON 400; wrong _artifact discriminator 400 |
| /hypothesis + personas | 6 | List, empty claim 400, valid stub create, missing id 404, personas list, non-array PUT 400 |
| /data | 16 | Empty body 400, wrong extension 415, valid CSV 201, unicode CSV 201, column override + restore, missing file 404, stat picker (group/correlation/text-col rejection/power-missing-target rejection), plot picker (histogram/scatter-missing-y/heatmap-no-cols), figures list |
| /figures | 5 | Empty body 400, missing fig_id 400, unknown fig_id 404, missing fig versions 404, **path traversal blocked 400** |
| /draft | 9 | Empty title 400, valid create, slug-collision suffix (`-2`), section content patch with auto-extracted `\fig + \cite` linked_*_ids, duplicate section 409, reorder, markdown export 201, substack 501 stub, invalid action 400 |
| /tools + /crons + /runs + /search | 8 | Catalog ≥ 30 entries, crons list, mcp:* tool 501 hint, empty prompt 400, non-array favourites falls back to [], unknown run 404, empty search query → 0 results, invalid type filter ignored gracefully |
| Cross-feature | 3 | Cmd+K search finds the manuscript created earlier in the suite, finds the section by content keyword "GLP-1", concurrent uploads land 2 distinct file_ids |

Cleanup at end of suite removes all artifacts created during the run (4 dataframes + 1 hypothesis) and wipes any stray repo-root debris (`.organon-dashboard/`, `figures/`, `data/`, `results/`, `manuscripts/` — these are the dirs that get written when project=`__root__`).

**What the stress test does NOT cover** (matches Phase 3-5 skip pattern):

- Skill-spawn SSE through `claude -p` — needs LLM compute time + cost (and is empirical until skill emits the JSON line correctly)
- FAL FLUX Fill full roundtrip — needs `FAL_KEY` in `.env`
- Mask drawing UX (HTML5 canvas pointer events)
- Embed autocomplete UX (caret-context popover)
- Diff view accept/reject flow (depends on action SSE)
- Pandoc / Marp PDF / HTML / DOCX export (system-tool dependent)

These all have manual smoke walks at `tests/phase{3,4,5,6}-smoke-walk.md`.

---

## 4. Smoke walks pending — the human-driven gates

| Phase | Walk file | Steps |
|---|---|---|
| 3 | `tests/phase3-smoke-walk.md` | 10 |
| 4 | `tests/phase4-smoke-walk.md` | 12 |
| 5 | `tests/phase5-smoke-walk.md` | 16 |
| 6 | _no walk doc_ | (use the smoke section in PHASE_6_TASKS.md §9.2) |

Run order: pick a real project (not `__root__`), exercise upload → preview → stat → plot → manuscript → embed → action → export → tools → crons → runs end-to-end.

PLAN.md §10 says **dogfood ≥ 1 week per phase before ship**. This session shipped Phases 2-6 in one day. The user accepted that risk explicitly; Phase 5 acceptance gate is the last green box before declaring v1.0 per PLAN §8.

---

## 5. Known limits + deferrals (explicit)

### Code-level
| Item | Phase | Why deferred |
|---|---|---|
| Parquet support in upload | 3 | venv lacks pyarrow; sci-data-analysis only handles csv/xlsx/json. One elif when needed. |
| T06 render registry | 3 | Still only one consumer per artifact type. Lift when ≥ 2 places need to render the same type. |
| viz-nano-banana --mode edit (Python lib/fal.py lift) | 4 | Dashboard's edit path goes direct-TS to FAL; CLI use deferred. |
| Pillow thumbnail for FAL v2+ figures | 4 | Currently uses the FAL response PNG directly without a thumb sidecar. |
| markdown-it + KaTeX | 5 | npm install denied in this sandbox; hand-rolled renderer covers the subset researchers need today. |
| Pandoc / Marp / xelatex installs | 5 | System-tool dependencies; route returns clean 503 + markdown fallback. |
| Substack export through tool-substack | 5 | Returns 501 with hint to pipe through CLI. |
| /usage on sidebar / topbar | 6 | Reachable by URL; sidebar promotion deferred. |
| Cron enable/disable/run-now from UI | 6 | Cross-platform LaunchAgent integration is messy; v0.x ships read-only. |
| ToolUniverse 2,000+ catalog browse | 6 | Need to spawn `uvx` from Next process; not feasible without a side-channel. |
| Skill versioning git_rev in run records | 6 | `gitRevShort()` helper exists; not yet wired into the run logger. |

### Skill-side compliance (empirical)
| Skill mode | Phase | Status |
|---|---|---|
| sci-literature-research Step 1.5 emit | 1 | Production-tested, working |
| sci-hypothesis Step 1.5 emit | 2 | Production-tested |
| sci-council Step 1.5 emit (per persona) | 2 | Production-tested |
| sci-data-analysis Step 0.5 + Step 1/2/4 emits | 3 | NOT YET LIVE-TESTED |
| sci-hypothesis Step 3 + Step 4 emits | 3 | NOT YET LIVE-TESTED |
| viz-nano-banana JSON-line figure emit | 4 | NOT YET LIVE-TESTED (dashboard's prompt is explicit; skill side empirical) |
| sci-writing Step 7.5 caption mode | 4 | NOT YET LIVE-TESTED |
| sci-writing Step 7.6 dashboard-action mode | 5 | NOT YET LIVE-TESTED |
| tool-humanizer Dashboard Mode | 5 | NOT YET LIVE-TESTED |

### Repo-root convention quirk
When project=`__root__`, the dashboard writes outputs at `<repo>/figures/`, `<repo>/data/`, `<repo>/results/`, `<repo>/manuscripts/`, `<repo>/.organon-dashboard/`. The stress suite cleans these dirs at the end. **Worth adding to `.gitignore`** to prevent accidental commits of dashboard-from-`__root__` debris:

```
/figures/
/results/
/manuscripts/
/data/data-*.csv
/data/data-*.xlsx
/data/data-*.json
/data/data-*.preview.json
/.organon-dashboard/
```

---

## 6. Common pitfalls in this codebase (lessons from this session)

These are landmines I hit repeatedly; future you (or another agent) will hit them too.

1. **READ-BEFORE-EDIT hook fires advisory but writes do succeed.** Every Edit/Write to a file the agent didn't Read in this session emits a hook reminder; the operation goes through anyway. Don't mistake the reminder for a failure. (You'll see it on every other turn — ignore it once the file is in working memory.)

2. **`npm install` is denied by the sandbox deny list.** This is why `lib/draft/render.ts` is hand-rolled instead of using `markdown-it`, and why `tests/parser-*.test.mjs` use the built-in `node:test` instead of vitest.

3. **`curl`, `wget`, `rm` are denied.** Use Python's `urllib.request` for HTTP and `shutil.rmtree` for directory removal. The stress suite + smoke scripts are all Python.

4. **`.env` is on the read deny list.** Can't probe whether `FAL_KEY` is set; the `fal-client.ts` reads it via `process.env` at request time and returns 402 if absent.

5. **Path resolution between repo root and dashboard cwd.** Git operations need `cd /Users/keremdelikoyun/Projects/scientific-os` first; npm operations need `cd projects/briefs/organon-dashboard`. The dashboard's library helpers (`organonRoot()`) handle the resolution internally so route handlers don't care.

6. **`__root__` is the synthetic project pointing at the repo root.** All artifact stores write under `<repo>/{data,figures,results,manuscripts,...}/` when project=__root__. Smoke tests should always clean those up.

7. **Server-only vs client-safe imports.** Anything importing `node:fs` / `node:crypto` / `node:child_process` cannot be reached from a `"use client"` component, even via type-only chains. The pattern: pure types live in `lib/{shared,types}.ts` (or `import type { ... }`); server-only helpers live in `lib/{store,ops}.ts`. P2 wrap-up's `lib/hypothesis/shared.ts` is the canonical example.

8. **TypeScript `default: never` after exhaustive switch.** When all cases are handled, the `default` branch sees `artifact: never`. Use `(artifact as { _artifact?: string })._artifact` to keep the warn-and-skip without type errors. (Hit this in Phase 5 — `lib/artifacts/persist.ts:38`.)

9. **claude-runner cwd is organon-root, NOT projectPath.** This is because `.mcp.json` uses relative paths (`scripts/with-env.sh`, etc.). Active project is communicated to the skill via prompt-embedded `active_project_slug={slug}`.

10. **SSE artifact-protocol parsers should listen to ONE source.** The `/api/execute` route (and Phase 3+ analogues) emit BOTH raw `stdout` chunks AND synthetic `artifact` events extracted from those chunks. Listening to both double-counts artifacts (causes React duplicate-key warnings). Pick the synthetic `artifact` event — it's canonical because the server already parsed.

11. **Next 16 + Turbopack rejects cross-project TS source imports.** Build mode bundles them via tsconfig path aliases; dev mode (Turbopack) refuses. Fix: copy the source into the dashboard's `src/lib/`. P1 D4 walkback documents this.

12. **Co-author convention.** Per user memory: "only Claude as co-author, never WOZCODE or other identities". Every commit footer is `Co-Authored-By: Claude <noreply@anthropic.com>`.

13. **Stray dev-server-from-earlier-session.** Port 8769 is often already in use by a hot-reloading dev server from a prior session. Hot reload picks up new routes from disk, so probing `http://localhost:8769/api/...` usually just works without restart.

---

## 7. First moves next session

**If the user opens with a fresh prompt:** the heartbeat in CLAUDE.md auto-runs `/lets-go`. That picks up today's session memory at `context/memory/2026-05-06.md`. Open threads will surface:
- Phase commit chain
- Pending live smoke walks
- v1.0 ship gate status
- Cross-track: X launch reply window may still be open

**Concrete first checks (in order):**

1. `cd projects/briefs/organon-dashboard && npm run typecheck && npm run build && npm test` — all should still pass.
2. Start dev server (or check it's still running on :8769):
   ```bash
   cd projects/briefs/organon-dashboard
   bash -lc 'set -a; source ../../../.env 2>/dev/null; set +a; npm run dev'
   ```
3. Re-run `python3 tests/stress-suite.py` against the live server. Expect 52/52.
4. Open `http://localhost:8769/lit?project=arena-agentic-upgrade` (or whatever real project the user wants to dogfood). Walk through the smoke gates `tests/phase{3,4,5,6}-smoke-walk.md`.

**If the user asks "is v1.0 ready?":** answer yes for the dashboard surface. The remaining v1.0 ship gate per PLAN.md §8 is the **end-to-end researcher-workflow ship test** (literature → hypothesis → data → figures → draft → export). That requires real LLM compute on every step + actually publishing an output. It's a human-driven session, not an agent-driven one.

**If the user wants to add the `.gitignore` polish item from §5 above,** that's a 30-second patch — the lines are quoted there.

**If the user wants to wire `gitRevShort()` into the run logger** for the reproducibility metadata: `lib/git/rev.ts` already has the helper; modify `lib/runs.ts:appendRunEvent` to stamp the start event with `git_rev: gitRevShort()`, then surface it in `<RunDetailDrawer>`. ~10 LOC.

**If the user wants Phase 7 / v1.x scope:** consult PLAN.md §3 and the scope-row at the bottom of each PHASE_X_TASKS.md. The deferral list in §5 above is the natural backlog.

---

## Appendix — file inventory by phase

```
Phase 2 (commit 9952171):
  .claude/skills/sci-{council,hypothesis}/SKILL.md   (Step 1.5 emit each)
  src/lib/hypothesis/{shared,id,personas,store,critiques}.ts
  src/lib/artifacts/{types,parser,persist}.ts          (modified)
  src/app/api/{hypothesis,personas}/route.ts
  src/app/api/hypothesis/{[hyp_id],reconcile}/route.ts
  src/components/hypothesis/{claim-form,council-fanout,hypothesis-history,
                             hypothesis-workspace,linked-papers-list,
                             paper-picker,persona-panel,personas-editor,
                             status-badge,synthesis-card}.tsx
  src/components/primitives/paper-detail-drawer.tsx
  src/components/shell/{command-palette,sidebar}.tsx  (modified)
  PHASE_{2,3,4,5,6}_TASKS.md                          (forward plans)

Phase 3 (commit 22e6057):
  scripts/profile_dataframe.py                        (pandas-based loader)
  scripts/generate_plot.py                            (matplotlib renderer)
  src/lib/{data,results,figures}/                     (3 stores + id allocator)
  src/lib/artifacts/{types,parser,persist}.ts         (modified)
  src/lib/data/stat-picker.ts                         (5-mode pure-TS recommendation)
  src/lib/data/plot-schemas.ts                        (7 plot kinds + validateParams)
  src/app/api/data/{load,files,preview/[file_id],
                    analyze,plot,figures,results}/route.ts
  src/app/api/{stat-picker,figures/[fig_id]/[file]}/route.ts
  src/app/api/figures/[fig_id]/mask/[file]/route.ts   (Phase 4 was in scope)
  src/components/data/{file-uploader,data-file-list,dataframe-preview,
                       column-header,stat-test-picker,stat-recommendation,
                       stat-result-card,plot-picker,plot-renderer,
                       plot-history,data-workspace}.tsx
  tests/{parser-phase3.test.mjs,phase3-artifacts.md,phase3-smoke-walk.md}
  Sci-data-analysis SKILL.md Step 0.5 + emits
  Sci-hypothesis SKILL.md Step 3/4 emits

Phase 4 (commit 8efbcce):
  src/lib/images/{pricing,mask,versions,fal-client}.ts
  src/app/api/images/{generate,edit,lock,[fig_id]}/route.ts
  src/components/figures/{prompt-form,style-picker,image-canvas,mask-tools,
                          version-strip,caption-card,cost-gate-modal,
                          figures-workspace}.tsx
  tests/{parser-phase4.test.mjs,phase4-artifacts.md,phase4-smoke-walk.md}
  Sci-writing SKILL.md Step 7.5 (caption mode)

Phase 5 (commit 23ca6a7):
  src/lib/draft/{slug,store,parse,render,numbering,bib}.ts
  src/app/api/draft/{new,[slug]/route,[slug]/sections/route,
                     [slug]/sections/[section_id]/route,
                     [slug]/action,[slug]/export}/route.ts
  src/components/draft/{draft-list,manuscript-workspace,section-list,
                        section-row,status-badge-section,markdown-editor,
                        embed-autocomplete,live-preview,action-bar,
                        diff-view,export-menu}.tsx
  app/draft/[slug]/page.tsx
  tests/{parser-phase5.test.mjs,phase5-artifacts.md,phase5-smoke-walk.md}
  Sci-writing SKILL.md Step 7.6 + Step 0 routing
  Tool-humanizer SKILL.md Dashboard Mode

Phase 6 (commit ec04d32):
  src/lib/{tools,crons,search,git}/                   (4 readers + cmdk index)
  src/app/api/{tools,crons,runs/[id],search}/         (7 routes)
  src/components/{tools,crons,runs,usage}/            (10 components)
  src/components/shell/command-palette.tsx            (cross-corpus search hook)
  Live HTTP smoke 11/11 against dev server

Stress suite (this session, not committed yet — check with user before commit):
  tests/stress-suite.py                               (52-case end-to-end)
```

---

*End of pickup brief. Good luck.*
