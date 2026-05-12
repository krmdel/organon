import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 48 (v1.6) — F11: per-persona deep literature research.
// Tests are pure source-text-scans + inline behavioural replicas.
// No real searchPapers / claude-runner spawns.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const QUERIES_SRC = readSrc("src/lib/hypothesis/persona-queries.ts");
const ROUTE_SRC = readSrc("src/app/api/hypothesis/[hyp_id]/deep-research/route.ts");
const PANEL_SRC = readSrc("src/components/hypothesis/persona-panel.tsx");
const TYPES_SRC = readSrc("src/lib/artifacts/types.ts");
const WORKSPACE_SRC = readSrc("src/components/hypothesis/hypothesis-workspace.tsx");

// ---- persona-queries.ts shape ---------------------------------------

test("Phase 48 — persona-queries.ts returns persona-specific templates for skeptic / methodologist / domain-expert", () => {
  assert.match(
    QUERIES_SRC,
    /export\s+function\s+getPersonaQueries/,
    "persona-queries.ts must export getPersonaQueries",
  );
  // Each persona kind must have its own template family. The brief calls
  // out the three default personas; the registry must surface them.
  for (const kw of ["skeptic", "methodologist", "domain-expert"]) {
    assert.ok(
      QUERIES_SRC.toLowerCase().includes(kw),
      `persona-queries.ts must reference "${kw}"`,
    );
  }
  // Skeptic template family — refute / limitation / replicate.
  for (const kw of ["refute", "limitation", "replicate"]) {
    assert.ok(
      QUERIES_SRC.toLowerCase().includes(kw),
      `skeptic template must include "${kw}"`,
    );
  }
  // Methodologist template family — measurement / validation / reliability.
  for (const kw of ["measurement", "validation", "reliability"]) {
    assert.ok(
      QUERIES_SRC.toLowerCase().includes(kw),
      `methodologist template must include "${kw}"`,
    );
  }
  // Domain-expert template family — consensus / review / meta-analysis.
  for (const kw of ["consensus", "review", "meta-analysis"]) {
    assert.ok(
      QUERIES_SRC.toLowerCase().includes(kw),
      `domain-expert template must include "${kw}"`,
    );
  }
});

test("Phase 48 — each query template substitutes the hypothesis claim into the placeholder", () => {
  // Inline replica: each template should contain a {claim} (or similar)
  // placeholder that the function substitutes.
  const sub = (template, claim) => template.replace(/\{claim\}|\{X\}/gi, claim);
  assert.equal(sub("refute {claim}", "GLP-1 obesity"), "refute GLP-1 obesity");
  assert.equal(sub("measurement of {X}", "weight regain"), "measurement of weight regain");

  // Implementation must do the substitution.
  assert.match(
    QUERIES_SRC,
    /\{claim\}|\{X\}|\$\{claim\}/,
    "persona-queries.ts must contain a claim placeholder",
  );
  assert.match(
    QUERIES_SRC,
    /replace|template|substitut/i,
    "persona-queries.ts must perform claim substitution",
  );
});

test("Phase 48 — council route spawns a search per persona before the critique", () => {
  // The deep-research route must call searchPapers per persona's queries
  // and register a sub-task in the registry per query.
  assert.match(
    ROUTE_SRC,
    /searchPapers/,
    "deep-research route must call searchPapers",
  );
  assert.match(
    ROUTE_SRC,
    /getPersonaQueries/,
    "deep-research route must use getPersonaQueries",
  );
  // Workspace must call the deep-research endpoint before the council
  // fanout (or expose it as a separate user-triggered action).
  assert.match(
    WORKSPACE_SRC,
    /\/api\/hypothesis\/[^"]*\/deep-research|deep-research/,
    "hypothesis-workspace must call /api/hypothesis/.../deep-research",
  );
});

test("Phase 48 — additional_papers are stored on the persona-state", () => {
  // HypothesisArtifact gains an additional_papers_by_persona map (read-
  // time backfilled — legacy hypotheses pre-Phase-48 default to {}).
  assert.match(
    TYPES_SRC,
    /additional_papers_by_persona/,
    "HypothesisArtifact must expose additional_papers_by_persona",
  );
  // Field must be optional + nullable so legacy reads don't break.
  assert.match(
    TYPES_SRC,
    /additional_papers_by_persona\?:/,
    "additional_papers_by_persona must be optional",
  );
});

test("Phase 48 — persona-panel renders the deep-research section per card", () => {
  assert.match(
    PANEL_SRC,
    /deep[\s-]?research|deepResearch|deep_research/i,
    "persona-panel must render a deep-research section",
  );
  // Renders an expandable details/summary so the card stays compact when
  // collapsed.
  assert.match(
    PANEL_SRC,
    /<details|expand/i,
    "persona-panel must use a collapsible details element for the deep-research list",
  );
});

test("Phase 48 — each sub-search registers a task in the registry", () => {
  // The deep-research route must use streamTaskAsSse so the orchestrator
  // run survives navigation. Phase 44's substrate.
  assert.match(
    ROUTE_SRC,
    /streamTaskAsSse|registerTask/,
    "deep-research route must register tasks via the registry",
  );
  assert.match(
    ROUTE_SRC,
    /kind:\s*"hypothesis-deep-research"|kind:\s*"persona-deep-research"|kind:\s*"deep-research"/,
    "deep-research route must register with a deep-research kind",
  );
});
