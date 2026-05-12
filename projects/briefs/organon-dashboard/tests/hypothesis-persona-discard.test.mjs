import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 43 (v1.5) — F6 per-persona / per-critique discard before
// synthesis. Researchers want to drop unhelpful personas before
// reconcile fires, instead of being forced to synthesize all of them.
//
// Decisions (brief §7.3):
// - Discard, NOT delete. Excluded personas stay on disk; toggle is
//   reversible by the user.
// - Discard scope is the hypothesis (not the project): two hypotheses
//   can include/exclude different personas independently.
// - Reconcile prompt logs how many personas were excluded.
// - Restore is on the dimmed card itself.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const TYPES_SRC = readSrc("src/lib/artifacts/types.ts");
const HYP_ROUTE_SRC = readSrc("src/app/api/hypothesis/[hyp_id]/route.ts");
const RECONCILE_ROUTE_SRC = readSrc("src/app/api/hypothesis/reconcile/route.ts");
const PERSONA_PANEL_SRC = readSrc("src/components/hypothesis/persona-panel.tsx");
const WORKSPACE_SRC = readSrc("src/components/hypothesis/hypothesis-workspace.tsx");

test("Phase 43 — hypothesis state accepts excluded_persona_ids[] (default [])", () => {
  // The HypothesisArtifact type carries an optional excluded_persona_ids
  // array. Optional so legacy hypothesis.json files keep parsing; a
  // read-time helper defaults missing → [] (same pattern as Phase 41).
  assert.match(
    TYPES_SRC,
    /interface HypothesisArtifact[\s\S]*?excluded_persona_ids\??\s*:\s*string\[\]/,
  );

  // Behavioural replica of the read-time backfill.
  const backfill = (hyp) => ({
    ...hyp,
    excluded_persona_ids: Array.isArray(hyp.excluded_persona_ids)
      ? hyp.excluded_persona_ids
      : [],
  });
  const before = { id: "hyp-1", claim: "x" };
  const after = backfill(before);
  assert.deepEqual(after.excluded_persona_ids, []);
  assert.notEqual(after, before);
});

test("Phase 43 — PATCH /api/hypothesis/[hyp_id] writes excluded_persona_ids", () => {
  // The PATCH handler whitelists the new field alongside status / notes /
  // tags / claim_short. The whitelist appears as `safePatch.excluded_persona_ids`.
  assert.match(HYP_ROUTE_SRC, /excluded_persona_ids/);
  assert.match(HYP_ROUTE_SRC, /safePatch\.excluded_persona_ids/);
});

test("Phase 43 — reconcile filters out excluded personas from the synthesis prompt", () => {
  // The route reads hypothesis.excluded_persona_ids and narrows the
  // critiques list before composing the prompt. The prompt also
  // surfaces an explicit "excluded_personas=[...]" line so the skill
  // (and any forensic ledger) sees the exclusion is deliberate.
  assert.match(RECONCILE_ROUTE_SRC, /excluded_persona_ids/);
  assert.match(RECONCILE_ROUTE_SRC, /critiques[\s\S]{0,400}filter\(/);
  assert.match(RECONCILE_ROUTE_SRC, /excluded_personas/);

  // Behavioural replica of the filter.
  const filterCritiques = (critiques, excluded) => {
    const set = new Set(excluded);
    return critiques.filter((c) => !set.has(c.persona_slug));
  };
  const out = filterCritiques(
    [
      { persona_slug: "skeptic" },
      { persona_slug: "methodologist" },
      { persona_slug: "domain-expert" },
    ],
    ["methodologist"],
  );
  assert.equal(out.length, 2);
  assert.equal(out.find((c) => c.persona_slug === "methodologist"), undefined);
});

test("Phase 43 — persona-panel renders a discard button per card", () => {
  // The panel exposes a "Discard" affordance with a stable data-action
  // hook. Discarded panels render dimmed (e.g. with opacity-50 or a
  // dedicated `data-discarded` attr); the same button toggles back to
  // "Restore" once excluded.
  assert.match(PERSONA_PANEL_SRC, /data-action="persona-discard"/);
  // The panel accepts `excluded` + `onToggleDiscard` props from the caller.
  assert.match(PERSONA_PANEL_SRC, /onToggleDiscard/);
  assert.match(PERSONA_PANEL_SRC, /excluded[\s\S]{0,80}boolean/);
  // Discarded card surfaces a data attr so tests + screen-readers can
  // detect the dimmed state.
  assert.match(PERSONA_PANEL_SRC, /data-discarded/);
});

test("Phase 43 — synthesis-card surfaces the included-of-total count", () => {
  // The reconcile button (in the active-hypothesis workspace) shows
  // "Reconcile (M of N personas)" when at least one persona is
  // excluded. Pin the surface via a regex for the chrome shape, since
  // the exact JSX uses a template literal.
  assert.match(
    WORKSPACE_SRC,
    /Reconcile[\s\S]{0,400}of\s*\$\{[^}]*\}\s*personas?/i,
  );
  // Behavioural replica of the count formula.
  const includedCount = (personas, excluded) => {
    const set = new Set(excluded);
    return personas.filter((p) => !set.has(p.slug)).length;
  };
  assert.equal(
    includedCount(
      [{ slug: "a" }, { slug: "b" }, { slug: "c" }],
      ["b"],
    ),
    2,
  );
});
