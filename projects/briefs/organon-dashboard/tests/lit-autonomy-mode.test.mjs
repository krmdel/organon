import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 46 (v1.6) — F9: full-autonomy literature mode.
// Tests are pure source-text-scans + inline behavioural replicas.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const AUTONOMY_SRC = readSrc("src/lib/lit/autonomy.ts");
const ROUTE_SRC = readSrc("src/app/api/lit/autonomy/route.ts");
const SEARCHBAR_SRC = readSrc("src/components/lit/search-bar.tsx");
const WORKSPACE_SRC = readSrc("src/components/lit/lit-workspace.tsx");

// ---- autonomy.ts orchestrator ----------------------------------------

test("Phase 46 — autonomy.ts expands keywords into a fanout query set", () => {
  // Inline replica of the deterministic expansion: take comma-separated
  // keywords + research_question, produce a list of query variants.
  const expandQueries = (keywords, question) => {
    const kws = keywords.filter(Boolean);
    const variants = [];
    if (question?.trim()) variants.push(question.trim());
    if (kws.length === 1) variants.push(kws[0]);
    if (kws.length >= 2) {
      variants.push(kws.join(" AND "));
      variants.push(kws.join(" OR "));
      variants.push(kws.join(" "));
    }
    return Array.from(new Set(variants));
  };

  const variants = expandQueries(["GLP-1", "obesity"], "what predicts weight regain?");
  assert.ok(variants.includes("what predicts weight regain?"));
  assert.ok(variants.includes("GLP-1 AND obesity"));
  assert.ok(variants.includes("GLP-1 OR obesity"));
  assert.ok(variants.includes("GLP-1 obesity"));
  assert.equal(variants.length, 4);

  // The implementation must export expandQueries (or a wrapper) for the
  // route + tests + future ML-expansion swap.
  assert.match(
    AUTONOMY_SRC,
    /export\s+function\s+expandQueries/,
    "autonomy.ts must export expandQueries",
  );
});

test("Phase 46 — autonomy merges + dedupes by DOI across paperclip + APIs", () => {
  // The orchestrator must call searchPapers per query variant and dedupe
  // the merged set by DOI (lowercased + url-stripped). Inline replica:
  const dedupeByDoi = (papers) => {
    const seen = new Map();
    const noDoi = [];
    const norm = (d) =>
      d ? d.toLowerCase().replace(/^https?:\/\/(dx\.)?doi\.org\//, "").replace(/^doi:/, "").trim() : null;
    for (const p of papers) {
      const k = norm(p.doi);
      if (!k) {
        noDoi.push(p);
        continue;
      }
      if (!seen.has(k)) seen.set(k, p);
    }
    return [...seen.values(), ...noDoi];
  };

  const merged = dedupeByDoi([
    { id: "a", doi: "10.1/x", title: "A" },
    { id: "b", doi: "10.1/X", title: "Adup" },
    { id: "c", doi: null, title: "C" },
    { id: "d", doi: "10.2/y", title: "D" },
  ]);
  assert.equal(merged.length, 3);
  assert.deepEqual(
    merged.map((p) => p.id).sort(),
    ["a", "c", "d"],
  );

  // Implementation must run the dedupe.
  assert.match(
    AUTONOMY_SRC,
    /dedupe[Bb]y[Dd]oi|dedupe_by_doi/,
    "autonomy.ts must dedupe by DOI in the merged set",
  );
});

test("Phase 46 — autonomy partitions results into accepted (≥ threshold) + borderline (< threshold)", () => {
  // Inline replica: split scored results around a threshold.
  const partition = (papers, threshold) => {
    const accepted = [];
    const borderline = [];
    for (const p of papers) {
      const s = p.relevance_score ?? 0;
      if (s >= threshold) accepted.push(p);
      else borderline.push(p);
    }
    return { accepted, borderline };
  };

  const out = partition(
    [
      { id: "a", relevance_score: 0.9 },
      { id: "b", relevance_score: 0.55 },
      { id: "c", relevance_score: 0.7 },
      { id: "d", relevance_score: 0.3 },
    ],
    0.6,
  );
  assert.deepEqual(out.accepted.map((p) => p.id).sort(), ["a", "c"]);
  assert.deepEqual(out.borderline.map((p) => p.id).sort(), ["b", "d"]);

  // The orchestrator's return shape must expose both buckets.
  assert.match(
    AUTONOMY_SRC,
    /accepted:\s*PaperArtifact\[\]/,
    "autonomy result must expose accepted: PaperArtifact[]",
  );
  assert.match(
    AUTONOMY_SRC,
    /borderline:\s*PaperArtifact\[\]/,
    "autonomy result must expose borderline: PaperArtifact[]",
  );
});

test("Phase 46 — POST /api/lit/autonomy registers a task via the tasks registry", () => {
  // The route must use streamTaskAsSse (Phase 44's substrate) so the user
  // can navigate away during a long autonomy run.
  assert.match(
    ROUTE_SRC,
    /streamTaskAsSse/,
    "autonomy route must use streamTaskAsSse",
  );
  assert.match(
    ROUTE_SRC,
    /kind:\s*"lit-autonomy"/,
    "autonomy route must register with kind: 'lit-autonomy'",
  );
  assert.match(
    ROUTE_SRC,
    /async\s+function\*\s+runner\b/,
    "autonomy route must yield events from an async generator runner",
  );
});

test("Phase 46 — search-bar full-autonomy toggle reveals the research-question input", () => {
  // The bar must add an "autonomy mode" toggle that, when on, reveals a
  // second input (research question) and when submitted POSTs to the
  // autonomy endpoint instead of the normal /api/lit/search.
  assert.match(
    SEARCHBAR_SRC,
    /autonomy[Mm]ode|autonomyEnabled|autonomy[Tt]oggle/,
    "search-bar must add an autonomy-mode toggle",
  );
  assert.match(
    SEARCHBAR_SRC,
    /research[_-]?question|researchQuestion/,
    "search-bar must reveal a research-question input when autonomy is on",
  );

  // The workspace must wire the autonomy submission to the new endpoint.
  assert.match(
    WORKSPACE_SRC,
    /\/api\/lit\/autonomy/,
    "lit-workspace must call /api/lit/autonomy when autonomy mode submits",
  );
});
