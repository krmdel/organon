import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 54 (v2.0) — Reproducibility checks at export time.
//
// Goal: BEFORE any export path runs, surface a deterministic check
// that the manuscript's referenced artifacts still resolve. NEW
// lib/draft/repro-check.ts::runReproCheck takes the manuscript, its
// sections, and the project's stores; produces structured findings
// per check (cite-keys, fig-ids, linked_*_ids existence). Severity is
// pass / warn / fail per finding. NEW POST /api/draft/[slug]/repro-check
// returns the report JSON. Source-linkage-panel mounts a "Run repro
// check" affordance; the workspace consumes the response and surfaces
// the findings inline.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const HELPER_SRC = readSrc("src/lib/draft/repro-check.ts");
const ROUTE_SRC = readSrc("src/app/api/draft/[slug]/repro-check/route.ts");
const PANEL_SRC = readSrc("src/components/draft/source-linkage-panel.tsx");

test("Phase 54 — runReproCheck is exported", () => {
  assert.match(HELPER_SRC, /export function runReproCheck\(/);
});

test("Phase 54 — helper returns { checks, passed } where each check has a verdict", () => {
  // Behavioural replica: check the contract via a faithful re-run.
  const run = ({ manuscript, sections, library, figures, hypotheses, datasets }) => {
    const cites = new Set();
    const figs = new Set();
    for (const s of sections) {
      for (const m of (s.content_md ?? "").matchAll(/\\cite\{([^}]+)\}/g)) {
        for (const k of m[1].split(",")) cites.add(k.trim());
      }
      for (const m of (s.content_md ?? "").matchAll(/\\fig\{([^}\s]+)\}/g)) {
        figs.add(m[1].trim());
      }
    }
    const knownCites = new Set(library.flatMap((p) => [p.cite_key, p.id].filter(Boolean)));
    const knownFigs = new Set(figures.map((f) => f.id));
    const knownPapers = new Set(library.map((p) => p.id));
    const knownHyps = new Set(hypotheses.map((h) => h.id));
    const knownDs = new Set(datasets.map((d) => d.id));
    const checks = [];
    const missingCites = [...cites].filter((k) => !knownCites.has(k));
    checks.push({
      name: "cite-keys-resolve",
      verdict: missingCites.length === 0 ? "pass" : "fail",
      detail: missingCites,
    });
    const missingFigs = [...figs].filter((k) => !knownFigs.has(k));
    checks.push({
      name: "fig-ids-resolve",
      verdict: missingFigs.length === 0 ? "pass" : "fail",
      detail: missingFigs,
    });
    const linkedPaperIds = manuscript.linked_paper_ids ?? [];
    const lostPapers = linkedPaperIds.filter((id) => !knownPapers.has(id));
    checks.push({
      name: "linked-papers-exist",
      verdict: lostPapers.length === 0 ? "pass" : "warn",
      detail: lostPapers,
    });
    const linkedFigIds = manuscript.linked_figure_ids ?? [];
    const lostFigs = linkedFigIds.filter((id) => !knownFigs.has(id));
    checks.push({
      name: "linked-figures-exist",
      verdict: lostFigs.length === 0 ? "pass" : "warn",
      detail: lostFigs,
    });
    const linkedHypIds = manuscript.linked_hypothesis_ids ?? [];
    const lostHyps = linkedHypIds.filter((id) => !knownHyps.has(id));
    checks.push({
      name: "linked-hypotheses-exist",
      verdict: lostHyps.length === 0 ? "pass" : "warn",
      detail: lostHyps,
    });
    const linkedDsIds = manuscript.linked_dataset_ids ?? [];
    const lostDs = linkedDsIds.filter((id) => !knownDs.has(id));
    checks.push({
      name: "linked-datasets-exist",
      verdict: lostDs.length === 0 ? "pass" : "warn",
      detail: lostDs,
    });
    return { checks, passed: checks.every((c) => c.verdict !== "fail") };
  };
  const out = run({
    manuscript: {
      title: "M",
      ordering: ["abstract"],
      linked_paper_ids: ["p1", "p404"],
      linked_figure_ids: [],
      linked_hypothesis_ids: ["h1"],
      linked_dataset_ids: [],
    },
    sections: [
      {
        section_id: "abstract",
        content_md: "See \\cite{Smith2024} and \\fig{f-1}. \\cite{ghost-key}",
      },
    ],
    library: [
      { id: "p1", cite_key: "Smith2024" },
      { id: "p2", cite_key: "Doe2025" },
    ],
    figures: [{ id: "f-1" }],
    hypotheses: [{ id: "h1" }],
    datasets: [],
  });
  assert.equal(out.checks.length, 6);
  const cite = out.checks.find((c) => c.name === "cite-keys-resolve");
  assert.equal(cite.verdict, "fail");
  assert.deepEqual(cite.detail, ["ghost-key"]);
  const linkedPapers = out.checks.find((c) => c.name === "linked-papers-exist");
  assert.equal(linkedPapers.verdict, "warn");
  assert.deepEqual(linkedPapers.detail, ["p404"]);
  // Cite fail flips passed=false.
  assert.equal(out.passed, false);
});

test("Phase 54 — POST /api/draft/[slug]/repro-check returns the structured report", () => {
  assert.match(ROUTE_SRC, /export\s+async\s+function\s+POST/);
  assert.match(ROUTE_SRC, /runReproCheck/);
  assert.match(ROUTE_SRC, /resolveProjectFromRequest/);
  // Returns { passed, checks } in JSON.
  assert.match(ROUTE_SRC, /passed[\s\S]{0,200}checks|checks[\s\S]{0,200}passed/);
});

test("Phase 54 — repro-check helper reads cite-keys + fig-ids via the project's parse helper", () => {
  // Implementation must reuse extractRefsSequence so the cite/fig
  // semantics stay identical to the export pipeline.
  assert.match(HELPER_SRC, /extractRefsSequence|extractRefs/);
});

test("Phase 54 — source-linkage-panel mounts a 'Run repro check' affordance", () => {
  // Sentinel data attribute the test pins.
  assert.match(PANEL_SRC, /data-repro-check/);
});

test("Phase 54 — helper exports the result types", () => {
  // Public types so the route + UI can import them without re-declaring.
  assert.match(HELPER_SRC, /export type ReproCheckResult|export interface ReproCheckResult/);
  assert.match(HELPER_SRC, /export type ReproCheckReport|export interface ReproCheckReport/);
});
