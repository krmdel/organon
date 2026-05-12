import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 11 (v1.0.1) — Workspace state persistence regression contract.
//
// Scope (V1_0_1_PLAN.md §6):
//   L-1 — /lit re-hydrates query + sources from URL params and auto-runs
//         the search on mount so the results panel is not empty after
//         back/forward navigation.
//   H-1 — /hypothesis restores the WIP claim draft from localStorage when
//         no active hypothesis is selected; the project-scoped key isolates
//         drafts across projects.
//   H-8 — /hypothesis page response computes a HydrationStatus
//         { critiques, expected, synthesis } from the active hypothesis,
//         the critique sidecars on disk, and the configured personas; the
//         workspace renders this as a small badge so a researcher knows
//         whether 2/3 critiques means "still loading" or "council never
//         finished".
//
// Same source-text scan pattern as draft-code-spans / draft-generate so the
// suite stays portable across `node --test` (no TS build step needed).

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const RECENT_SRC = readSrc("src/lib/state/recent-searches.ts");
const SEARCH_BAR_SRC = readSrc("src/components/lit/search-bar.tsx");
const LIT_WORKSPACE_SRC = readSrc("src/components/lit/lit-workspace.tsx");
const LIT_PAGE_SRC = readSrc("src/app/lit/page.tsx");
const HYP_PAGE_SRC = readSrc("src/app/hypothesis/page.tsx");
const HYP_WORKSPACE_SRC = readSrc("src/components/hypothesis/hypothesis-workspace.tsx");
const CLAIM_FORM_SRC = readSrc("src/components/hypothesis/claim-form.tsx");

test("lit page hydrates URL params + lit-workspace auto-runs search on mount (L-1)", () => {
  // page.tsx pulls q + sources from searchParams and forwards as initial props.
  // This survived Phase 1; Phase 11's contribution is the AUTO-RUN.
  assert.match(LIT_PAGE_SRC, /typeof sp\.q === "string"/);
  assert.match(LIT_PAGE_SRC, /typeof sp\.sources === "string"/);
  assert.match(LIT_PAGE_SRC, /initialQuery=\{initialQuery\}/);
  assert.match(LIT_PAGE_SRC, /initialSources=\{initialSources\}/);
  // Workspace consumes saved papers from initialLibrary (server-loaded).
  assert.match(LIT_PAGE_SRC, /initialLibrary=\{library\}/);

  // Auto-search-on-mount — the load-bearing Phase 11 piece. Uses a ref to
  // prevent the URL-replace loop the handleSearch callback would otherwise
  // trigger when searchParams updates.
  assert.match(LIT_WORKSPACE_SRC, /autoSearchedRef = useRef\(false\)/);
  assert.match(LIT_WORKSPACE_SRC, /autoSearchedRef\.current = true/);
  assert.match(LIT_WORKSPACE_SRC, /if \(!initialQuery\) return;/);
  assert.match(LIT_WORKSPACE_SRC, /handleSearch\(\{[\s\S]+?query: initialQuery/);

  // Saved-papers panel rendered from server-hydrated library state, sourced
  // from initialLibrary prop (round-trip preserved through state).
  assert.match(LIT_WORKSPACE_SRC, /useState<PaperArtifact\[\]>\(initialLibrary\)/);
});

test("recent-searches localStorage ring is project-scoped, capped at 10, dedups by query", () => {
  // Project-scoped key: every accessor namespaces by the project slug so
  // cross-project drafts cannot collide.
  assert.match(RECENT_SRC, /STORAGE_PREFIX\s*=\s*"organon:"/);
  assert.match(RECENT_SRC, /lit:recent:\$\{project\}/);
  // Cap = 10 declared as a constant; tests would catch a silent drift.
  assert.match(RECENT_SRC, /RECENT_SEARCHES_MAX\s*=\s*10/);
  assert.match(RECENT_SRC, /\.slice\(0, RECENT_SEARCHES_MAX\)/);
  // Dedup by trimmed lowercase query so "GLP-1" and "glp-1 " collapse.
  assert.match(RECENT_SRC, /\.toLowerCase\(\)/);
  assert.match(RECENT_SRC, /cur\.filter\(\(e\) => e\.query\.trim\(\)\.toLowerCase\(\) !== dedupKey\)/);
  // SSR-safe: every accessor checks typeof window first.
  for (const fn of ["readRecentSearches", "pushRecentSearch", "readWipClaim", "writeWipClaim"]) {
    assert.ok(RECENT_SRC.includes(`export function ${fn}`), `must export ${fn}`);
  }
  assert.match(RECENT_SRC, /typeof window === "undefined"/);
  // Quota / private-mode degrade silently — never throws into the workspace.
  assert.match(RECENT_SRC, /catch \{[\s\S]+?\/\* quota[\s\S]+?\*\//);

  // Behaviour mirror in plain JS — confirms the cap + dedup math even
  // though the source is a TS file we cannot import directly.
  const cap = 10;
  let buf = [];
  const push = (q) => {
    const key = q.trim().toLowerCase();
    buf = [{ query: q, ts: Date.now() }, ...buf.filter((e) => e.query.trim().toLowerCase() !== key)].slice(0, cap);
  };
  for (let i = 0; i < 25; i += 1) push(`q-${i}`);
  assert.equal(buf.length, cap, "ring must cap at 10");
  // Re-pushing an existing query moves it to head, length unchanged.
  push("q-23");
  assert.equal(buf.length, cap);
  assert.equal(buf[0].query, "q-23");

  // Workspace + search-bar wire the ring through.
  assert.match(LIT_WORKSPACE_SRC, /import \{[\s\S]+?pushRecentSearch[\s\S]+?readRecentSearches[\s\S]+?\} from "@\/lib\/state\/recent-searches"/);
  assert.match(LIT_WORKSPACE_SRC, /pushRecentSearch\(project, \{ query: params\.query, sources: params\.sources \}\)/);
  assert.match(SEARCH_BAR_SRC, /recentSearches\?: RecentSearchEntry\[\]/);
  assert.match(SEARCH_BAR_SRC, /onPickRecent\?: \(entry: RecentSearchEntry\) => void/);
  assert.match(SEARCH_BAR_SRC, /data-recent-searches-button/);
  assert.match(SEARCH_BAR_SRC, /data-recent-searches-panel/);
});

test("hypothesis-workspace persists WIP claim to localStorage and re-hydrates on mount (H-1)", () => {
  // ClaimForm exposes onClaimChange so the workspace owns the persistence
  // decision (single source of truth for the localStorage write).
  assert.match(CLAIM_FORM_SRC, /onClaimChange\?: \(claim: string\) => void/);
  assert.match(CLAIM_FORM_SRC, /onClaimChange\?\.\(e\.target\.value\)/);

  // Workspace imports the helpers + uses them.
  assert.match(HYP_WORKSPACE_SRC, /import \{ readWipClaim, writeWipClaim \} from "@\/lib\/state\/recent-searches"/);
  // Hydration on first paint: only when no active hypothesis claims the slot.
  assert.match(HYP_WORKSPACE_SRC, /wipClaimHydratedRef = useRef\(false\)/);
  assert.match(HYP_WORKSPACE_SRC, /if \(initialHypId\) return;/);
  assert.match(HYP_WORKSPACE_SRC, /readWipClaim\(project\)/);
  // Persistence on every keystroke via onClaimChange.
  assert.match(HYP_WORKSPACE_SRC, /handleClaimChange = useCallback\(/);
  assert.match(HYP_WORKSPACE_SRC, /writeWipClaim\(project, next\)/);
  // Submit clears the scratchpad — the new hypothesis takes over.
  assert.match(HYP_WORKSPACE_SRC, /writeWipClaim\(project, ""\)/);
  // ClaimForm receives the change emitter.
  assert.match(HYP_WORKSPACE_SRC, /onClaimChange=\{handleClaimChange\}/);
});

test("hypothesis page server response computes hydrationStatus from active hypothesis + critiques + personas (H-8)", () => {
  // Page-level: pulls hyp_id from URL, looks up hypothesis + critiques +
  // personas server-side, computes the badge value before the first paint.
  assert.match(HYP_PAGE_SRC, /import \{ getHypothesis, listHypotheses \} from "@\/lib\/hypothesis\/store"/);
  assert.match(HYP_PAGE_SRC, /import \{ listCritiques \} from "@\/lib\/hypothesis\/critiques"/);
  assert.match(HYP_PAGE_SRC, /let initialHydrationStatus: HydrationStatus \| null = null/);
  assert.match(HYP_PAGE_SRC, /getHypothesis\(project\.path, initialHypId\)/);
  assert.match(HYP_PAGE_SRC, /listCritiques\(project\.path, initialHypId\)\.length/);
  // Synthesis presence derived from synthesis_text — not from a separate
  // file probe — so the server response stays a single read pass.
  assert.match(HYP_PAGE_SRC, /active\.synthesis_text \? "present" : "absent"/);
  assert.match(HYP_PAGE_SRC, /critiques: critiqueCount,?/);
  assert.match(HYP_PAGE_SRC, /expected,?/);
  assert.match(HYP_PAGE_SRC, /initialHydrationStatus=\{initialHydrationStatus\}/);

  // Workspace surface — type export + prop + render.
  assert.match(HYP_WORKSPACE_SRC, /export type HydrationStatus = \{[\s\S]+?critiques: number;[\s\S]+?expected: number;[\s\S]+?synthesis: "present" \| "absent";[\s\S]+?\}/);
  assert.match(HYP_WORKSPACE_SRC, /initialHydrationStatus\?: HydrationStatus \| null/);
  // Live derivation — once critiques + personas are in client state, the
  // badge updates without waiting for a server round-trip.
  assert.match(HYP_WORKSPACE_SRC, /hydrationStatus: HydrationStatus \| null = useMemo/);
  assert.match(HYP_WORKSPACE_SRC, /critiques: critiques\.length/);
  // Phase 13a (v1.0.1) — `expected` switched from full personas count to
  // the active-only count so the badge does not pin at "2/3" when one
  // persona is deactivated.
  assert.match(HYP_WORKSPACE_SRC, /expected: activePersonaCount/);
  assert.match(HYP_WORKSPACE_SRC, /activeHypothesis\.synthesis_text \? "present" : "absent"/);
  // Render — chip with data-attributes for click-test stability.
  assert.match(HYP_WORKSPACE_SRC, /<HydrationBadge status=\{hydrationStatus\} \/>/);
  assert.match(HYP_WORKSPACE_SRC, /data-hydration-status/);
  assert.match(HYP_WORKSPACE_SRC, /data-critiques=\{status\.critiques\}/);
  assert.match(HYP_WORKSPACE_SRC, /data-expected=\{status\.expected\}/);
  assert.match(HYP_WORKSPACE_SRC, /data-synthesis=\{status\.synthesis\}/);
});
