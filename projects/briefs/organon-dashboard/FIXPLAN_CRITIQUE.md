---
project: organon-dashboard
artifact: adversarial review of FIXPLAN.md
date: 2026-05-06
reviewer: skeptical-engineer pass
verdict: 4 working days is optimistic; several "closed" findings will reopen
---

# FIXPLAN.md adversarial critique

The FIXPLAN claims to close 26 dogfood findings in 4 days across 9 phases and re-run the dogfood as a v1.0 ship gate. After walking each phase against the actual code at `src/`, the actual on-disk dogfood artifacts at `projects/(briefs/)?dogfood-glp1-weight-regain/`, and the symptoms documented in `DOGFOOD_REPORT.md`, the plan has roughly the right shape but several load-bearing claims are speculative or wrong, and at least four findings will not be closed by the work the plan actually does.

The structure below: CRITICAL findings (would re-fail the dogfood ship gate); MAJOR findings (will surface within a week of v1.0); MINOR findings (worth noting).

---

## CRITICAL findings

### C1. Phase 1's diagnosis of #22 split is wrong; the migration alone won't prevent recurrence

- **Frame:** 1 (does the fix close the bug?)
- **Phase / finding:** Phase 1 / Finding #22.
- **The attack.** The plan attributes the dogfood split to slug-interpolated paths in prompts (notably `src/app/api/images/generate/route.ts:45-46`). That is one real bug, but it is **not** what split this dogfood. The data file `data-20260506-a96e4d.csv` and the manuscript `treatment-duration-...` landed under `projects/dogfood-glp1-weight-regain/`, not under `projects/briefs/dogfood-glp1-weight-regain/`. None of those calls go through `/api/images/generate`. The `data/upload.ts` and `draft/store.ts` persisters use `project.path` correctly — verified at `src/lib/data/upload.ts:79-127` and `src/lib/draft/store.ts:43-48`.
  
  The actual root cause is in `src/lib/projects.ts:31-89`: `listProjects()` adds **two** entries with the same slug — one from `projects/{slug}/` (added at lines 43-64) and one from `projects/briefs/{slug}/` (added at lines 66-87). `resolveProject(slug)` (line 92-94) does `find()`, which returns the **first** match — i.e. the non-brief root, because non-briefs are appended before briefs. So as soon as a non-brief sibling directory exists for the same slug (which can happen because the manuscript persister auto-creates `manuscriptsDir(projectPath) = projectPath/manuscripts/` under whichever path resolveProject returned at the time), `resolveProject` permanently flips to the wrong root and every subsequent persister writes to the non-brief side.

  Why it matters: Phase 1's migration script merges + deletes the duplicate, fixing the current split. But `resolveProject` still has the same bug. The very first time a future project gets even a single artifact written outside the brief folder (e.g. a researcher tests `__root__` mistakenly, then renames; or an external tool drops a file there), `resolveProject` again flips and the split returns. The `assertProjectPath` invariant doesn't catch this because every persister IS using `project.path` — `project.path` itself is just the wrong root.

- **Suggested fix.**
  - In `listProjects()`, deduplicate by slug at registration: if both `projects/{slug}/` and `projects/briefs/{slug}/` exist, the brief wins (preferred per Decision D1) and the non-brief is reported as a `migration_required` warning surfaced in the project picker.
  - Or stronger: refuse to start the server if any duplicate-slug pair exists, with a one-line "run scripts/migrate-split-projects.mjs --apply" hint. Loud-failure beats silent-wrong-tree.
  - Whichever approach, the test in T1.4 must include "given two siblings with the same slug, resolveProject returns the brief one" — the plan's test as written ("for every brief in fixtures, assert project.path includes projects/briefs/") doesn't catch this case because no fixture has a duplicate.

- **Kill criterion.** Real if `resolveProject("dogfood-glp1-weight-regain")` returns `projects/dogfood-glp1-weight-regain/` (not the brief) on a fresh repo where the migration hasn't yet run. Verify with a 5-line node script:  `node -e 'console.log(require("./src/lib/projects").resolveProject("dogfood-glp1-weight-regain").path)'`. If it prints the non-brief path, the bug is real.

### C2. Phase 3's timeout doesn't address the actual SIGTERM source

- **Frame:** 1 (does the fix close the bug?)
- **Phase / finding:** Phase 3 / Findings #11, #14.
- **The attack.** The plan calls the 3:35 SIGTERM "from elsewhere (likely Next 16 server route default or AbortSignal upstream)" and prescribes an 8-minute runner-side timeout + heartbeat. But `src/app/api/execute/route.ts:39` does `request.signal.addEventListener("abort", () => abort.abort())`, and `abort` is wired into the runner which `child.kill("SIGTERM")` on abort (`src/lib/claude-runner.ts:74-78`). That is the most plausible SIGTERM source: the SSE connection's `request.signal` aborts when the browser disconnects (tab close, navigation, network blip, Chrome MCP automation tearing down the SSE channel), or when React's StrictMode runs an effect's cleanup, or when the user clicks "Generate" twice and the first `AbortController` is replaced (orphaning the prior request which then aborts). The runner-side timeout the plan adds does NOT prevent this — it adds a NEW kill source on top of the existing one.

  Worse: the plan's heartbeat fix is on the SSE channel server-to-client, but the SIGTERM trigger is the client-to-server abort signal. A keepalive on the response stream doesn't keep the request signal alive; it just keeps proxies happy.

- **Suggested fix.**
  - Before adding a runner timeout, instrument `request.signal` to log the abort reason. Add a console.error at `route.ts:39` capturing `signal.aborted`, `signal.reason`, and a stack trace. Run the dogfood council scenario again with this instrumentation and confirm what's actually firing.
  - If the source is the browser disconnect (likely), the fix is to **decouple the runner from the request signal**: kick off `runClaude` without subscribing to `request.signal`, and let the runner finish writing its run log + persisting artifacts even if the SSE channel is gone. The SSE channel just becomes a "tail" of an already-running job. The user can navigate away and come back to `/runs` to see the result.
  - The 8-minute runner timeout is fine as a defensive cap, but it's not the real fix. State this in Decision D3: "Decouple from request.signal; runner is fire-and-forget once started; SSE is a live tail with auto-reconnect."

- **Kill criterion.** Real if a `console.error("[runner abort]", signal.reason, new Error("trace"))` at `route.ts:39` shows the abort firing on the council during a normal run (not at 8 min, but at ~3 min when the Chrome MCP automation moves on, or whenever the browser tab loses focus on macOS Safari behind-tab-throttling). If you instead see exit at the 8 min mark with no upstream abort, the plan's diagnosis is right.

### C3. Phase 4 does not close existing-manuscript cite-key references that were typed against the buggy first-name keys

- **Frame:** 2 (what does the plan miss?)
- **Phase / finding:** Phase 4 / Finding #25 + the dogfood manuscript.
- **The attack.** The plan's Phase 2 backfill rewrites `cite_key` on each paper JSON to surname+year (e.g. `Shah2026`). The plan's Phase 4 renderer accepts `cite_key OR id` for resolution. But the dogfood's existing manuscript `projects/dogfood-glp1-weight-regain/manuscripts/treatment-duration-.../sections/introduction.md` (verified to contain `\cite{Sara2025}` and `\cite{Patrice2026}`) typed against the BUGGY first-name keys. After backfill, `Sara2025` is **neither** the new cite_key (`Berg2025`) **nor** the paper id (`pmid-pmid:41889156` or whatever the OpenAlex equivalent is). So the renderer's "OR" lookup fails for both arms, and the export still yields "[unresolved \cite{Sara2025}]" lines.

  The plan's Phase 9 ship-gate walk in step 13 only types `Berg2025` and `Hubert2026` (the corrected keys), so the new dogfood will pass — but **the existing dogfood manuscript will remain broken**, which means the v1.0 dogfood project on disk will have a known broken manuscript. Either the plan needs an existing-manuscript migration (find every `\cite{X}` token that doesn't resolve, prompt the user to remap), or the plan needs to delete the old manuscript before the new dogfood, which loses the audit trail of what v0.9 produced.

- **Suggested fix.**
  - Add T2.4b: alongside the cite_key backfill, scan every `manuscripts/**/sections/*.md` file for `\cite{X}` and `\fig{X}` tokens. For each X that doesn't resolve to either a cite_key or a paper.id post-backfill, write a one-line warning to `projects/{slug}/manuscripts/{ms-slug}/.cite-migration-pending.md` with the unresolved token, the section it was in, and a fuzzy-match suggestion ("did you mean Berg2025?"). This migration is also dry-run by default.
  - Optional: an interactive remap CLI that walks pending tokens and asks for a target cite_key.
  - Phase 4's renderer should also accept a `cite_alias` list on the manuscript meta, mapping legacy → new keys, so a user can backfill ad-hoc without rewriting their .md files.

- **Kill criterion.** Real if `grep -rn "\\\\cite{Sara2025}" projects/dogfood-glp1-weight-regain/manuscripts/` returns matches AND no migration step rewrites them. Verified: it does (introduction.md line 3).

### C4. Phase 7's "no silent __root__" makes Phase 1 backwards-incompatible

- **Frame:** 3 (new bug introduced) + 4 (ordering).
- **Phase / finding:** Phase 7 ordering vs Phase 1.
- **The attack.** Phase 7 says "make `__root__` an explicit opt-in (`?project=__root__`), not the silent default. Routes return 400 if no project resolution succeeds." 19+ API routes currently have `body.project ?? "__root__"` as the silent default (verified — every `app/api/**/route.ts` reads it that way). Flipping that to 400 means:
  - Every existing UI smoke walk's "use the dashboard with no project picker selected" path breaks. The PHASE_6 stress suite test "concurrent uploads land 2 distinct file_ids" sends no `project` field; this regresses.
  - The dogfood's stress-suite cleanup at the end of `tests/stress-suite.py` writes to `__root__` to verify cleanup-on-repo-root paths; verified the doc note at NEXT_SESSION.md §5 ("when project=`__root__`, the dashboard writes outputs at `<repo>/figures/`...").
  - Any external script (cron, MCP integration, third-party uploader) that ever worked POST-ing without a project field will start 400-ing on day-1 of v1.0.

  Phase 7 is also listed AFTER Phase 1 ("listed late because the fix is tiny"). But Phase 1's migration assumes the canonical project root is fully resolvable; Phase 1 doesn't define what `__root__` means. If Phase 1 ships before Phase 7, the migration script (T1.3) walks `projects/{slug}/` looking for splits, but `__root__`-written debris (`<repo>/figures/`, `<repo>/data/`) is at the actual repo root, not under `projects/`. The migration ignores this debris. Then Phase 7 makes it impossible to reach `__root__` anymore so the debris is orphaned.

- **Suggested fix.**
  - **Reorder.** Phase 7 should be Phase 1 in this sprint, BEFORE the migration. The migration then has a clean contract: every artifact has a non-`__root__` project. Or: Phase 7 keeps `__root__` as the opt-in but adds a dashboard-visible "REPO ROOT — do not use for real work" warning banner whenever the active project is `__root__`.
  - The migration script needs an additional clause: "If `<repo>/(figures|data|results|manuscripts)/` exists and contains files, prompt the user to assign them to a project or delete them."
  - The stress suite's cleanup needs to be re-validated against Phase 7's stricter behavior: every test that writes to `__root__` must explicitly pass `?project=__root__`.

- **Kill criterion.** Real if after Phase 7 lands, `python3 tests/stress-suite.py` without further changes drops below 52/52 PASS. Verified: stress-suite.py:122 uses POST `/api/data/load` without a project param.

### C5. Phase 5 stat tests will produce results that disagree with the existing skill — silently

- **Frame:** 3 (new bug) + 1 (closes the bug?)
- **Phase / finding:** Phase 5 / Finding #13.
- **The attack.** The plan's `run_stat_test.py` claims to support 11+ tests "matches stat-picker recommendations." The stat-picker (`src/lib/data/stat-picker.ts`) emits `test_name` values: `ttest_rel`, `wilcoxon`, `ttest_ind`, `mannwhitneyu`, `anova_oneway`, `kruskal_wallis`, `friedman`, `pearson`, `spearman`, `logistic_regression`, `linear_regression`, `chi2_contingency`, `fisher_exact`, `power_*`. The existing skill (`.claude/skills/sci-data-analysis/scripts/data_ops.py:155-309`) supports only 6: `ttest_ind`, `ttest_paired`, `anova`, `chi_square`, `pearson`, `spearman`. **Test names already disagree** between picker and skill (`ttest_rel` vs `ttest_paired`, `chi2_contingency` vs `chi_square`, `anova_oneway` vs `anova`).

  The plan blithely assumes the new direct-Python script will "match stat-picker recommendations." But to truly match, the script must:
  - Implement Welch t (already part of `ttest_ind` if equal_var=False; OK), Mann-Whitney U, Kruskal-Wallis, Wilcoxon signed-rank, Friedman, Logistic regression, Linear regression OLS, Fisher exact, and the 5+ power-analysis modes — none of which exist in the current skill.
  - Match the picker's name strings, not the skill's.
  - Emit assumption_checks[] in the schema the persister expects (verified `src/lib/artifacts/types.ts:188`).

  This is not "factor a runStatTestDirect from existing skill." It's "implement 8 new statistical tests + power analysis from scratch + match a contract that doesn't currently exist." The plan estimates this as half a day. That is wrong by 2-3x.

  Secondary concern: when the picker recommends a test the script doesn't yet support (e.g. Friedman), the script must fail loudly with a clear "test not implemented" message and the UI must surface it. The plan doesn't enumerate this failure mode; it just shows a `runStatTest` happy-path.

- **Suggested fix.**
  - Add a T5.0: "Reconcile picker test-name vocabulary with the new script's vocabulary. List every (picker.test_name, script-handler) tuple. For tests not yet implemented, document what the picker should recommend instead and update the picker." This is half a day on its own.
  - Set Phase 5 effort to 1 full day, not the 0.5 day implied by the timeline table.
  - For tests beyond the existing 6 (Mann-Whitney, Kruskal-Wallis, Wilcoxon, Linear/Logistic regression, Fisher exact, Power analysis): each gets its own unit test in T5.5. The plan's T5.5 fixture only covers Pearson; expand to one test per supported test type.
  - The "AI interpretation" follow-up button (T5.4) must NOT use the existing skill's `Step 4 Validate` — that step's prompt assumes the skill ran the test itself. Either factor a "interpret existing result" prompt, or scope T5.4 out of v1.0.

- **Kill criterion.** Real if a 30-minute audit of `stat-picker.ts` test_name strings vs `data_ops.py` test_type strings produces a disagreement table with ≥3 mismatches. Verified above.

---

## MAJOR findings

### M1. Phase 1's migration mtime tiebreaker is wrong direction for the dogfood case

- **Frame:** 3 (new bug introduced).
- **Phase / finding:** Phase 1 / T1.3.
- **The attack.** The plan says "for every child dir present in BOTH, prefer the newer mtime; print a warning if mtimes within 60s." For the actual dogfood, both copies of `data-20260506-a96e4d.csv` are byte-identical (verified MD5: `38c9fc6a510839df003b750e55d2a4ec`), but mtimes differ by ~5 min (1778058353 vs 1778058080). The newer mtime is on the **non-brief** side, which is the side we want to delete. So "prefer newer" picks the wrong winner: the file the migration keeps is the one that should go away. The brief side's older mtime is the canonical copy.
- **Suggested fix.** Tiebreaker should be: hash-equal → keep brief side, delete non-brief side. Hash-different → prompt the user with a diff. Mtime is a noisy signal and should only be the tiebreaker as a fallback when both sides have content the user didn't realize was different.
- **Kill criterion.** Real if running the dry-run migration on this dogfood prints "newer file in non-brief root, will use that as canonical" for `data-20260506-a96e4d.csv`. Verified mtimes above support this.

### M2. Phase 1's `assertProjectPath` invariant is fail-loud and will brick the dashboard if any single legacy artifact lingers

- **Frame:** 3 (new bug).
- **Phase / finding:** Phase 1 / T1.2.
- **The attack.** Throwing on every persist write means a single legacy artifact in the wrong tree breaks all subsequent persist operations. After the migration, if even one cron job or background script writes to the OLD non-brief tree (because it had a hardcoded path baked in at v0.9), the next `savePaper`/`saveResult` may pick that up while listing or hashing and trigger the assertion. There's no warn-once-per-bad-path or recover-and-continue path. The plan calls this an "invariant" but invariants are for "throw if your code has a bug"; this is "throw if anything anywhere on disk has a bug" — much wider scope.
- **Suggested fix.** Two-tier: throw only when the in-memory persist call itself constructs an out-of-bounds path (a code bug in this build). Warn-once when listing the directory finds an out-of-bounds artifact, and surface in the project picker as a "Project state has X stray files; run scripts/migrate-split-projects.mjs --check" hint.
- **Kill criterion.** Real if a future bug somewhere unrelated drops a single misplaced JSON in the `papers/` dir and the entire `/lit` workspace 500s on load. Plausible.

### M3. Phase 2's cite_key generation is not stable across paper additions and deletions

- **Frame:** 1 (does the fix actually fix the bug?).
- **Phase / finding:** Phase 2 / Finding #25 / T2.3 / T2.4.
- **The attack.** `paperToCiteKey(paper, existingKeys)` computes the suffix by examining `existingKeys` at the moment of save. But:
  - **Add A → A gets `Hubert2026`. Add B → B sees `{Hubert2026}` → B gets `Hubert2026b`. Delete A → key Hubert2026 is now free. Add C (different paper, also Hubert) → C gets `Hubert2026`. Re-add A → A gets `Hubert2026b` (or `c` if it sees both B and C). Now any draft that cited `Hubert2026` resolves to C, not the original A.** Latent corruption.
  - **Backfill (T2.4) does not specify the order of papers it processes.** `readdir` order is filesystem-dependent. Two backfill runs against the same `papers/` directory (e.g. dev machine + CI) can produce different cite_key assignments for surname collisions. Result: cite-keys are not reproducible between machines, breaking any build-then-export pipeline.
- **Suggested fix.**
  - Make cite_key deterministic from paper.id + library state hash, not insertion order. E.g. for a collision, sort the colliding papers by paper.id and assign suffixes in that fixed order.
  - On backfill, sort the JSONs lexicographically before processing.
  - On delete, mark the cite_key as "tombstoned" — never reuse it (write a `.cite-key-tombstones.json` per project).
- **Kill criterion.** Real if you can produce two papers Smith2026 with surname collision, save → delete first → save a third paper with surname Smith → re-save the first → and the cite_key field on the original first paper has changed value.

### M4. Phase 4's 422-on-unresolved-cites is more strict than current behavior; existing manuscripts will fail to export

- **Frame:** 3 (new bug).
- **Phase / finding:** Phase 4 / T4.3.
- **The attack.** Today, `assembleMarkdown` (verified at `src/lib/draft/render.ts:210-225`) just concatenates raw `content_md` and adds a "Missing from library: X" entry for unresolved cites in the bibliography. This is broken (DOGFOOD #24) but the export ALWAYS succeeds and writes a file. The plan flips this: 422 + list of unresolved keys, with `?force=true` opt-in to ship anyway.

  After Phase 4, any manuscript with even one typo or dead reference will not export at all. Researchers iterating on a draft (where one cite was renamed but the section wasn't yet updated) get a hard 422 instead of a usable export-with-warnings. This is a regression from "I get my draft as a file with one weird footer" to "I get nothing."

  The plan mentions `?force=true` but doesn't specify the UI surface. The export menu (`src/components/draft/export-menu.tsx`) needs a "Export anyway with warnings" affordance, or the user has to know about a query-string flag, which is hostile.

- **Suggested fix.**
  - Default behavior: 200 with a `warnings: ["unresolved cite-key: Sara2025", ...]` field in the response and a `Missing references` footer in the markdown. Same as today.
  - Strict mode is opt-IN, not opt-out: `?strict=true` returns 422 for CI / publish flows.
  - The export menu needs to surface warnings prominently (red badge on the export status indicator) so users are NOT silently shipping broken exports.
- **Kill criterion.** Real if the dogfood ship-gate step 15 says "export as markdown; pass criterion: zero Missing from library lines AND zero unresolved \cite tokens" — but the existing dogfood manuscript with `\cite{Sara2025}` would 422 unless someone deletes it first. Phase 9 doesn't address this.

### M5. Phase 3's blanket 8-minute timeout is wrong granularity for stat tests and figure gen

- **Frame:** 3 (new bug introduced).
- **Phase / finding:** Phase 3 / T3.1 / Decision D3.
- **The attack.** Decision D3 says "default 8 minutes for council/stat/figure (each is bounded by the skill's own internal step count)." But:
  - Stat tests (Phase 5 makes them ~5s direct-Python) — an 8-minute timeout means a stuck stat test waits 8 minutes before the user sees Failed. The user will refresh first. Stat-test timeout should be ≤30s.
  - Figure gen (Gemini) typically returns in 30-90s — 8 min is fine, but if the Gemini API hangs at the network layer, a 2-3 min cap is more humane.
  - Council fanout (3 personas, sequential markdown emit) — 8 min may be too short for actual ELI5 + critique generation if the model is rate-limited.

  Each route has different SLOs. A single global default forces the worst combination of "false-positive fail" and "user has already given up."

- **Suggested fix.** Per-route timeout, set in route module: `analyze` 30s, `images/generate` 180s, `images/edit` 300s, `hypothesis` (council POST) 600s, `draft/[slug]/action` 300s. Document in T3.1.
- **Kill criterion.** Real if Phase 5 lands and a healthy 5s stat test ever blocks the UI for >30s when it dies due to a bad arg.

### M6. Phase 6 biomedical-query heuristic is brittle for the actual dogfood query

- **Frame:** 1 (closes the bug?).
- **Phase / finding:** Phase 6 / T6.6 / Finding #1.
- **The attack.** The plan's heuristic: "if query contains any of {drug names, disease names, 'patient', 'trial', 'efficacy', 'treatment', ...}, default arXiv to off." The dogfood query was "GLP-1 weight regain after discontinuation" — none of those keywords appear. "GLP-1" is a drug-class abbreviation but the heuristic would need explicit knowledge of every such abbreviation. The plan's fallback ("project's brief.md `level` and `field`") is gated on the brief author setting `field: biomedical`, which most briefs don't.
- **Suggested fix.**
  - Use a small classifier instead of a keyword list — e.g. "if any of the top-10 PubMed results have a citation_count > 0 and the top-10 arXiv results don't, the query is biomedical." This works post-search, so just drop arXiv from the rerank.
  - Or simpler: for brief projects, ALWAYS rerank arXiv to the bottom unless the user explicitly checks an arXiv source filter. Let non-brief projects keep the current uniform ordering.
- **Kill criterion.** Real if the dogfood ship-gate step 2 ("arXiv pre-disabled OR arXiv results ranked below PubMed/OpenAlex") fails on a fresh query with the heuristic enabled. Verified: the dogfood query has no plan-listed keywords.

### M7. Phase 2's investigation step for Finding #5 is a bet, not a fix

- **Frame:** 1 (closes the bug?).
- **Phase / finding:** Phase 2 / T2.1 / Finding #5.
- **The attack.** The plan says "Likely root cause: the OpenAlex artifact has no `source_ids.pmid` and the persister's filename derivation works fine, but the client-side POST is not happening for non-PubMed entries. Check `components/lit/save-button.tsx`." Verified at `src/components/lit/lit-workspace.tsx:223-239` (`handleSave`): it does NOT filter by source. Every paper goes through `fetch("/api/lit/library", { method: "POST", body: JSON.stringify({ project, paper }) })` regardless of source. The plan's diagnosis is wrong.

  The actual root cause is unknown without instrumentation. Plausible alternatives:
  - The `narrowPaper` parser (`src/lib/artifacts/parser.ts:77-85`) requires `abstract: string`. Some OpenAlex/S2 results have null abstracts. But search.ts:206 forces `abstract: p.abstract || ""`, so that shouldn't fail.
  - The user clicked SAVE before the optimistic update reconciled with the server, and the server response actually came back failing silently (the catch block at `lit-workspace.tsx:233` reverts UI but doesn't log).
  - The dogfood report's "9 papers" count includes results that the user never clicked SAVE on (just the library counter on the federated search page).

  Phase 2's commit says "Phase 2 persistence — all sources persist." Without diagnosing the actual cause, this commit is aspirational.

- **Suggested fix.**
  - T2.0: instrument `handleSave` to log every POST + every response. Re-run a one-shot dogfood `/lit` save on a fresh OpenAlex paper. Capture the actual failure mode. THEN write the fix.
  - Make the failure visible in the UI: if the POST returns non-2xx, show a red banner on the paper card with the error message and revert the SAVED badge. Currently a swallowed catch reverts state without telling the user.
- **Kill criterion.** Real if a manual repro on a fresh OpenAlex search of an arbitrary biomedical query saves a paper, and the file fails to appear in `papers/` despite the UI showing SAVED. Plausible from the dogfood report.

### M8. Phase 2's HTML-entity decode is incomplete

- **Frame:** 1 (closes the bug?).
- **Phase / finding:** Phase 2 / T2.5 / Finding #3.
- **The attack.** The plan's `ENTITIES` map covers `&amp; &lt; &gt; &quot; &#39; &nbsp;` but PubMed efetch returns way more: `&prime;`, `&micro;`, `&alpha;`, `&beta;`, `&gamma;`, `&plusmn;`, `&deg;`, numeric entities like `&#x03B1;`, etc. The plan's regex `/&[a-z#0-9]+;/g` matches them but the lookup returns the literal entity (no fallback decode), leaving them in the saved JSON.
- **Suggested fix.** Either:
  - Use a more complete entity table (~50 common ones in PubMed-land); the `he` library would be ideal but `npm install` is denied. Inline the table.
  - Decode numeric entities (`&#NNN;` and `&#xHH;`) via `String.fromCodePoint`. Trivial fallback that handles the long tail.
- **Kill criterion.** Real if any saved paper's `journal` or `abstract` field contains a literal `&prime;` or `&micro;` after Phase 2. Easy to grep.

### M9. Phase 3's run-detail "Rerun" button on /runs is risky without a confirmation gate

- **Frame:** 3 (new bug).
- **Phase / finding:** Phase 3 / T3.5.
- **The attack.** The plan adds a "rerun" affordance on `/runs` rows that "re-emits the start event's prompt." But the start event captures the FULL prompt with the original `figId` / `runId` / `hypothesis_id` baked in. Re-running with the same IDs means writing v2/v3 over an old artifact. For figure gen this is fine (versions are appended). For stat results it's overwrite. For council critiques, the personas see a hypothesis with existing critique_files and may cascade weirdly. The plan doesn't say the rerun allocates fresh IDs.
- **Suggested fix.** Rerun should allocate a fresh `run_id` / `fig_id` / `hypothesis_id` and surface a "this is a new run; old run still in /runs history" toast. Or better: rerun is greyed out for runs that already have artifacts, with a "New run with same prompt" affordance instead.
- **Kill criterion.** Real if Phase 3 lands and a user rerunning a stat-test row from /runs silently overwrites the prior `stat-20260506-XXXXXX.json`. Need to read T3.5's actual implementation.

### M10. Phase 8 estimate of "half a day" for the regression suite is unrealistic given the scope

- **Frame:** 4 (pacing).
- **Phase / finding:** Phase 8.
- **The attack.** Phase 8 lists 13 new test specs across 5+ test files, plus extending stress-suite.py to 60+ cases, plus authoring a 25-step smoke-walk doc. Realistic effort:
  - 13 test cases × ~30 min each = 6.5 hours.
  - 8+ stress-suite cases (failure modes are often slow to set up) = 2-3 hours.
  - 25-step smoke walk doc with pass/fail criteria, screenshots optional but expected = 2 hours.
  - Total: ~1.5 working days, not 0.5.
- **Suggested fix.** Re-estimate Phase 8 to 1.5 days. The timeline table at line 1062-1074 then sums to 5 days, not 4. Adjust expectations accordingly OR drop the smoke-walk doc to a v1.0.1 follow-up.
- **Kill criterion.** Real if you actually try this in 4 hours and ship 5 of 13 tests. Likely.

### M11. Phase 3 effort estimate (1 day) is too short for the surface area

- **Frame:** 4 (pacing).
- **Phase / finding:** Phase 3.
- **The attack.** Phase 3 touches: claude-runner.ts (timeout + heartbeat events), 6 SSE-using API routes (forward heartbeat/timeout/exit), the shared SSE consumer (or each component's), 4+ workspace components for failure-state UI + Cancel + Retry, `/runs` page + run-detail components, plus the test harness binary + unit tests. That's at least 12 files across server, client, and test infra. The Phase 3 fanout is the single biggest change in this sprint.
- **Suggested fix.** 1.5 days minimum. Or: split Phase 3 into 3a (server-side: timeout, heartbeat, exit code propagation) and 3b (client-side: failure UI, Cancel + Retry, /runs filter). 3a alone unblocks visibility for the dogfood; 3b is polish.
- **Kill criterion.** Real if Phase 3 ships in 1 day and has stub UI ("Failed" text but no Retry/Cancel) deferred to Phase 6. Likely.

### M12. The plan's stress-suite extension claim ("60+/60+ PASS") doesn't enumerate the new failure-mode tests

- **Frame:** 2 (what does the plan miss?).
- **Phase / finding:** Phase 8 / T8.2.
- **The attack.** T8.2 lists three new cases (multipart upload without project → 400, export with unresolved cite → 422, mocked figure-gen non-zero exit → SSE failure event). That's 52 + 3 = 55, not 60+. The "60+" target implies more cases the plan doesn't enumerate. If Phase 8 ships with only 55 the metric is unmet.
- **Suggested fix.** Either drop the "60+" target or enumerate the additional 5+ cases. Candidates: `pmid-pmid:` regression test, OpenAlex paper persistence test, cite_key generation collision test, scatter Y-default test, sub-style-required validation test, biomedical-rerank test.
- **Kill criterion.** Real if Phase 8 stress-suite reports 55-58/55-58 PASS instead of 60+. Mechanical.

### M13. SIGTERM exit code (143) interacts with the existing `code === 0 ? "ok" : "error"` logic in /runs

- **Frame:** 1 (does the fix close the bug?).
- **Phase / finding:** Phase 3 / T3.5 + existing code at `src/lib/runs.ts:101`.
- **The attack.** `readRunSummary` already maps `code === 0 → "ok"` and otherwise → `"error"`. So /runs ALREADY shows the council fanout as `error` status. The dogfood reporter saw "Running sci-council fanout…" indefinitely, but `/runs` should have already labelled the run as error (it did the kill at 3:35 and the exit event was logged). So the bug isn't /runs labelling; it's the per-workspace component (council card) not consuming the `exit` event from the SSE stream. Phase 3's claim that `/runs` needs "red left-border + rerun button" is pure-polish; the actual missing piece is at the per-workspace component level.
- **Suggested fix.** Reword Phase 3's framing: T3.4 (workspace-component failure UI) is the critical fix for the dogfood; T3.5 (/runs polish) is a nice-to-have. Spend the time accordingly.
- **Kill criterion.** Real if `/runs` for the dogfood council run already shows status=error today. Need to start the dev server and check, but the existing readRunSummary code path supports it.

---

## MINOR findings

### m1. Phase 1's grep audit command is buggy

The audit command at line 149 of FIXPLAN.md: `grep -rn "projects/.{project.slug.}\|projects/.\{slug.}" src/` has shell-escaping issues that may produce zero matches even when matches exist. The actual problematic pattern verified at `src/app/api/images/generate/route.ts:45-46` uses `projects/${project.slug}/...`. A correct grep is `grep -rn 'projects/\${' src/` (verified — returns the two image-route hits). Fix the audit command.

### m2. Decision D1 Option A "audit every prompt template" scope is understated

D1's con-column says "Requires `Project.path` consistency audit across every persister and every prompt template." There are roughly 22 API routes and ≥18 persister calls. The audit is a half-day on its own; D1 doesn't budget for it.

### m3. Phase 6 T6.4 "tolerate single-version plot" silently fixes a different bug

The plan at line 768-775 says `/figures` workspace shows "fig_id has no versions" for plots created by `/data`. Verified the error at `src/app/api/images/[fig_id]/route.ts:17`. But the actual root cause is the API: `listVersions(project.path, fig_id)` reads `v{N}.json` files, which `/data`-generated plots don't write (they write `index.json` only). Phase 6's "treat the missing versions field as `[{version: 1, ...}]`" fix is at the component layer, not the API. So the API still 404s; the component just renders a fallback. That's defensible UX-wise but means the test in T8.1 ("legacy single-version figures render") covers the component path, not the API path.

### m4. Phase 9 ship-gate step 8 stat-test pass criterion is unverifiable today

Step 8 says "result card renders in under 10 seconds with r ≈ -0.43, p < 0.001, n=60." Verified the cohort CSV exists at `projects/briefs/dogfood-glp1-weight-regain/glp1_regain_cohort.csv` but the actual r-value depends on the synthetic-data generator's seed. The dogfood report quotes the numbers from a successful run, but if the file is regenerated for any reason the criterion is wrong. The plan should either commit the exact CSV (it's already on disk — fine) or compute the expected r from the actual file.

### m5. The plan never addresses run-history retention

`/runs` lists "last 200 entries" (per NEXT_SESSION.md §2). After a re-dogfood + stress-suite run, that 200 fills up fast. The plan doesn't add a "old runs" archive or rotation. Minor but the runs.jsonl files accumulate forever in `.organon/runs/`.

### m6. "Substack export beyond the 501 stub" is listed as out of scope

That's fine, but the dogfood didn't actually exercise it (DOGFOOD_REPORT lists it under the export menu's "stub" label). Either reword the v1.0 acceptance to "every export format other than Substack works" or drop Substack from the export menu UI for v1.0 to avoid researcher confusion.

### m7. The plan does not mention git_rev stamping in run logs

NEXT_SESSION.md §5 lists "Skill versioning git_rev in run records" as deferred. The dogfood post-mortem would have benefited from knowing exactly which commit produced each run. ~10 LOC, mentioned in NEXT_SESSION.md, not in FIXPLAN. Worth adding a line.

### m8. Phase 9 "Outcome doc" duplicates DOGFOOD_REPORT.md structure unnecessarily

The plan ends with `tests/v1-ship-gate-RESULT.md` written after the dogfood. That's a fine artifact, but it's the same shape as DOGFOOD_REPORT.md (26 findings). Better: append the result as a new section to the existing DOGFOOD_REPORT.md so the v0.9 → v1.0 delta is one document, not two parallel reports.

### m9. The plan's commit count is "8 atomic commits" but lists 9 phases ending in a commit

Phase 0 is decisions only (no commit), Phases 1-8 each end in a commit, Phase 9 is the ship gate (one commit). That's 8 fix commits + 1 ship-gate commit = 9 commits, not 8. Minor count error.

---

## Summary table — what does NOT close as written

| Finding | Plan's claim | Reality |
|---|---|---|
| #5 OpenAlex persistence | "client-side POST not happening" | Verified false — handleSave POSTs unconditionally. Real cause unknown. |
| #14 silent SIGTERM | runner timeout + heartbeat | Most likely cause is request.signal abort, not runner timeout. |
| #22 split projects | slug-interpolation in image-generate prompts | Not the actual root cause for the dogfood split; resolveProject collision is. |
| #25 cite_key broken | backfill at persist time | Backfill doesn't migrate existing manuscripts that still type the old buggy keys. |
| #1 arXiv noise | drug/disease keyword heuristic | Dogfood query has no listed keywords; heuristic doesn't fire. |
| #13 stat-test slow | direct-Python script | Plan estimates 0.5 day for 8+ new test implementations; real estimate ≥1 day. |

## Verdict

The plan is structurally sound and the priorities are right (Phase 3 + Phase 5 are the biggest wins, as the plan states). But three of the nine phases (1, 2, 3) misdiagnose root causes in ways that mean the proposed fix would close the symptom in a fresh repro and reopen it within a week of real use. Two phases (5, 8) are under-budgeted by 1.5-2x. One ordering decision (Phase 7 last) creates backwards-incompatibility on day-1.

**Recommended replan before implementation:**
1. Add a Phase 0.5 "diagnose" bullet that runs each speculative root-cause through actual instrumentation before writing the fix code — specifically for #5 (OpenAlex persistence), #14 (SIGTERM source), and #22 (resolveProject vs prompt interpolation).
2. Move Phase 7 to first (or fold into Phase 1), with the migration script handling repo-root debris.
3. Re-budget: Phase 3 and Phase 5 each +0.5 day; Phase 8 +1 day; total 5-5.5 days, not 4.
4. Add T2.4b (manuscript cite-key migration) and T1.0 (resolveProject dedup) to close C1 and C3.

If those four changes are made, the v1.0 ship gate is realistic. As written, expect Phase 9's dogfood re-run to surface 4-6 of the original findings still open.
