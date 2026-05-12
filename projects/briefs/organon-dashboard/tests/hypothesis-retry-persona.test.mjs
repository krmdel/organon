import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 13b (v1.0.1) — per-persona retry route + replace-by-key consumer.
//
// Scope (NEXT_SESSION_phase13-16.md §10):
//   H-5 — empty / missing critique surfaces a Retry button on the
//         persona panel; replace-by-key consumer (already in workspace)
//         swaps only the targeted critique on artifact arrival.
//   U4  — single-persona retry route at
//         /api/hypothesis/[hyp_id]/retry-persona; refuses on archived
//         + terminal statuses (synthesized/supported/refuted) + on
//         inactive personas; existing siblings preserved.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const ROUTE_SRC = readSrc(
  "src/app/api/hypothesis/[hyp_id]/retry-persona/route.ts",
);
const PANEL_SRC = readSrc("src/components/hypothesis/persona-panel.tsx");
const FANOUT_SRC = readSrc("src/components/hypothesis/council-fanout.tsx");
const WORKSPACE_SRC = readSrc(
  "src/components/hypothesis/hypothesis-workspace.tsx",
);

test("Phase 13b — retry-persona route refuses archived + terminal + inactive personas", () => {
  // POST handler with the standard project resolution + persona_slug
  // body parameter.
  assert.match(ROUTE_SRC, /export async function POST/);
  assert.match(ROUTE_SRC, /persona_slug\?: string/);
  assert.match(ROUTE_SRC, /resolveProjectFromRequest\(request, body\.project\)/);

  // archived → 409. The council loop is closed once a hypothesis is
  // archived; retry would resurrect a dead record.
  assert.match(
    ROUTE_SRC,
    /hypothesis\.status === "archived"[\s\S]+?status: 409/,
  );
  // synthesized / supported / refuted → 409. Synthesis already
  // consumed the critiques; retrying would invalidate it without UX.
  assert.match(
    ROUTE_SRC,
    /hypothesis\.status === "synthesized"[\s\S]+?hypothesis\.status === "supported"[\s\S]+?hypothesis\.status === "refuted"[\s\S]+?status: 409/,
  );

  // Persona must exist in personas.json AND be active (Phase 13a flag).
  assert.match(ROUTE_SRC, /listPersonas\(project\.path\)/);
  assert.match(ROUTE_SRC, /Persona not found in project[\s\S]+?status: 404/);
  assert.match(
    ROUTE_SRC,
    /!isPersonaActive\(target\)[\s\S]+?status: 409/,
  );
});

test("Phase 13b — retry route uses display name in prompt + drops non-target artifacts", () => {
  // sci-council's contract uses display names, not slugs. The prompt
  // composes `personas=[Display Name]` from the resolved persona.
  assert.match(ROUTE_SRC, /personas=\[\$\{target\.name\}\]/);
  // The single-persona contract is enforced at persistence — drop any
  // critique whose slug doesn't match the target + drop any non-
  // critique artifact (no full re-fanout).
  assert.match(
    ROUTE_SRC,
    /art\.persona_slug !== personaSlug\)\s*\{?\s*continue/,
  );
  assert.match(
    ROUTE_SRC,
    /art\._artifact !== "persona-critique"\)\s*\{?\s*continue/,
  );
  // active_project_slug is embedded in the prompt for the runner cwd
  // contract (claude-runner cwd is organonRoot, not project.path).
  assert.match(ROUTE_SRC, /active_project_slug=\$\{project\.slug\}/);
});

test("Phase 13b — persona-panel renders Retry button for empty + missing critiques on active personas", () => {
  // isCritiqueEmpty helper exported for the test + reuse.
  assert.match(
    PANEL_SRC,
    /export function isCritiqueEmpty\(c: PersonaCritiqueArtifact \| null\): boolean/,
  );
  // Retry only renders when the persona is active (Phase 13a) AND
  // the critique is empty / missing AND the parent passed onRetryPersona.
  assert.match(
    PANEL_SRC,
    /const showRetry = personaActive && \(empty \|\| missing\) && !!onRetryPersona;/,
  );
  // Two retry surfaces — missing-critique branch + empty-critique
  // banner — both carry data-action="retry-persona" + the slug for
  // click-test stability.
  const retryButtons = PANEL_SRC.match(/data-action="retry-persona"/g) ?? [];
  assert.equal(retryButtons.length, 2, "expected 2 retry buttons (missing + empty branches)");
  assert.match(PANEL_SRC, /data-persona-slug=\{slug\}/);
  // In-flight disables the button + flips the label.
  assert.match(PANEL_SRC, /retryInFlight \? "Retrying…" : `Retry \$\{persona\.name\}`/);
});

test("Phase 13b — council-fanout pipes onRetryPersona + retryingSlug down to PersonaPanel", () => {
  assert.match(FANOUT_SRC, /onRetryPersona\?: \(personaSlug: string\) => void/);
  assert.match(FANOUT_SRC, /retryingSlug\?: string \| null/);
  assert.match(
    FANOUT_SRC,
    /<PersonaPanel[\s\S]+?onRetryPersona=\{onRetryPersona\}[\s\S]+?retryingSlug=\{retryingSlug\}/,
  );
});

test("Phase 13b — workspace owns retry POST + uses existing replace-by-slug consumer", () => {
  // retryPersona callback gates on activeHypothesis + a single in-flight
  // retry at a time + the existing abortRef.
  assert.match(
    WORKSPACE_SRC,
    /const retryPersona = useCallback\([\s\S]+?async \(personaSlug: string\)/,
  );
  // POST target carries the ?project= query param (Phase 8 strict mode).
  assert.match(
    WORKSPACE_SRC,
    /retry-persona\?project=\$\{encodeURIComponent\(project\)\}/,
  );
  // Body shape pins the route contract: persona_slug + project echo.
  assert.match(
    WORKSPACE_SRC,
    /body: JSON\.stringify\(\{ project, persona_slug: personaSlug \}\)/,
  );
  // SSE drained through consumeSse — the existing handler already does
  // replace-by-slug for persona-critique artifacts, so retry is just a
  // single-event-stream invocation of the same consumer.
  assert.match(WORKSPACE_SRC, /await consumeSse\(res, ctrl,/);
  // CouncilFanout receives the callback through ActiveHypothesis.
  assert.match(WORKSPACE_SRC, /onRetryPersona=\{retryPersona\}/);
  assert.match(WORKSPACE_SRC, /retryingSlug=\{retryingSlug\}/);
});

test("Phase 13b — existing consumeSse already does replace-by-slug for persona-critique", () => {
  // Phase 13b deliberately reuses the existing artifact handler — no
  // new logic in consumeSse. Pin the contract so a future refactor
  // doesn't accidentally regress the replace-by-key behaviour.
  assert.match(
    WORKSPACE_SRC,
    /a\._artifact === "persona-critique"[\s\S]+?cur\.filter\(\(x\) => x\.persona_slug !== c\.persona_slug\)[\s\S]+?\[\.\.\.filtered, c\]/,
  );
});
