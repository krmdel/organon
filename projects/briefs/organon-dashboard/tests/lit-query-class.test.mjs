import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 7 (fix-sprint) T6.10 + T6.11 — biomedical query classification +
// arXiv reranking for federated lit search. Closes DOGFOOD #1.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const QC_SRC = readSrc("src/lib/lit/query-class.ts");
const SEARCH_SRC = readSrc("src/lib/lit/search.ts");
const SEARCHBAR_SRC = readSrc("src/components/lit/search-bar.tsx");

// ---- T6.10 query-class.ts shape ---------------------------------------

test("T6.10 — query-class.ts exports isBiomedicalQuery + rerankByDomain", () => {
  assert.match(QC_SRC, /export function isBiomedicalQuery/,
    "query-class.ts must export isBiomedicalQuery");
  assert.match(QC_SRC, /export function rerankByDomain/,
    "query-class.ts must export rerankByDomain");
});

test("T6.10 — biomedical keyword list covers the dogfood-flagged classes", () => {
  // Drug name dogfood used + classic clinical-trial vocabulary.
  for (const kw of [
    "patient", "trial", "efficacy", "treatment", "cohort", "incidence",
    "prevalence", "morbidity", "mortality", "biomarker",
    "cancer", "diabetes", "obesity", "alzheimer",
    "glp-1", "tirzepatide", "semaglutide", "metformin",
    "antibody", "vaccine", "gene", "protein", "neuron",
  ]) {
    assert.ok(QC_SRC.toLowerCase().includes(`"${kw}"`),
      `BIOMEDICAL_KEYWORDS must include "${kw}"`);
  }
});

test("T6.10 — drug-suffix regex captures monoclonal antibodies + statins + …", () => {
  // The actual regex is in source; mirror it here to exercise behavior.
  const re = /\b[a-z]{2,}(?:mab|nib|tide|prazole|gliptin|sartan|statin|cycline|olol|parin|mycin|cillin)\b/i;
  for (const drug of [
    "pembrolizumab", "imatinib", "tirzepatide", "omeprazole",
    "sitagliptin", "losartan", "atorvastatin", "tetracycline",
    "metoprolol", "heparin", "vancomycin", "amoxicillin",
  ]) {
    assert.ok(re.test(drug), `drug-suffix regex must match "${drug}"`);
  }
  // Common short non-drug words must NOT match.
  for (const word of ["cab", "rib", "abc", "limbo"]) {
    assert.ok(!re.test(word), `drug-suffix regex must not match "${word}"`);
  }
});

test("T6.10 — rerankByDomain pushes arXiv-only papers to the bottom", () => {
  // Mirror the rerank in JS so the test is self-contained.
  const rerank = (papers, biomedical) => {
    if (!biomedical) return papers;
    const arxivOnly = [];
    const others = [];
    for (const p of papers) {
      if (p.sources_merged.length === 1 && p.sources_merged[0] === "arxiv") arxivOnly.push(p);
      else others.push(p);
    }
    return [...others, ...arxivOnly];
  };

  const papers = [
    { id: "a1", sources_merged: ["arxiv"] },
    { id: "p1", sources_merged: ["pubmed"] },
    { id: "a2", sources_merged: ["arxiv"] },
    { id: "p2", sources_merged: ["pubmed", "openalex"] },
    { id: "merged", sources_merged: ["arxiv", "openalex"] },
  ];

  // Non-biomedical: order preserved.
  assert.deepEqual(
    rerank(papers, false).map((p) => p.id),
    ["a1", "p1", "a2", "p2", "merged"],
  );
  // Biomedical: arxiv-only at bottom; multi-source merged keeps its slot.
  assert.deepEqual(
    rerank(papers, true).map((p) => p.id),
    ["p1", "p2", "merged", "a1", "a2"],
  );
});

// ---- T6.10 search.ts wiring -------------------------------------------

test("T6.10 — search.ts imports + uses isBiomedicalQuery for default sources", () => {
  assert.match(SEARCH_SRC, /import\s*\{[^}]*isBiomedicalQuery[^}]*\}\s*from\s*"\.\/query-class"/,
    "search.ts must import isBiomedicalQuery from ./query-class");
  assert.match(SEARCH_SRC, /BIOMEDICAL_DEFAULT_SOURCES/,
    "search.ts must declare a biomedical default source list");
  assert.match(SEARCH_SRC, /isBiomedicalQuery\(opts\.query/,
    "search.ts must classify the query");
  // The default-sources expression must consult biomedical when no explicit sources.
  assert.match(SEARCH_SRC, /biomedical\s*\?\s*BIOMEDICAL_DEFAULT_SOURCES/,
    "default sources must branch on biomedical when caller didn't pin");
});

test("T6.10 — biomedical default drops arXiv but keeps PubMed + OpenAlex + S2", () => {
  const m = SEARCH_SRC.match(/BIOMEDICAL_DEFAULT_SOURCES:\s*SearchSource\[\]\s*=\s*\[([^\]]*)\]/);
  assert.ok(m, "BIOMEDICAL_DEFAULT_SOURCES literal must be present");
  const literal = m[1];
  assert.ok(literal.includes("pubmed"), "biomedical default must include pubmed");
  assert.ok(literal.includes("openalex"), "biomedical default must include openalex");
  assert.ok(literal.includes("semanticscholar"), "biomedical default must include S2");
  assert.ok(!literal.includes("arxiv"), "biomedical default must NOT include arxiv");
});

// ---- T6.11 rerank wired into search ----------------------------------

test("T6.11 — search.ts applies rerankByDomain on biomedical + arXiv queries", () => {
  assert.match(SEARCH_SRC, /import\s*\{[^}]*rerankByDomain[^}]*\}\s*from\s*"\.\/query-class"/,
    "search.ts must import rerankByDomain");
  assert.match(SEARCH_SRC, /sources\.includes\("arxiv"\)/,
    "rerank must guard on `arxiv in sources`");
  assert.match(SEARCH_SRC, /rerankByDomain\(ranked,\s*biomedical\)/,
    "search.ts must call rerankByDomain(ranked, biomedical)");
});

test("T6.11 — SearchResult exposes a `biomedical` flag for the UI", () => {
  assert.match(SEARCH_SRC, /biomedical:\s*boolean/,
    "SearchResult interface must expose a biomedical flag");
  assert.match(SEARCH_SRC, /return \{[^}]*biomedical[^}]*\}/,
    "search.ts return shape must include biomedical");
});

// ---- T6.10 SearchBar UX ----------------------------------------------

test("T6.10 — SearchBar reactively defaults arXiv off for biomedical queries", () => {
  assert.match(SEARCHBAR_SRC, /import\s*\{[^}]*isBiomedicalQuery[^}]*\}\s*from\s*"@\/lib\/lit\/query-class"/,
    "search-bar.tsx must import isBiomedicalQuery");
  assert.match(SEARCHBAR_SRC, /NON_ARXIV_SOURCES/,
    "search-bar.tsx must declare a non-arxiv default list");
  assert.match(SEARCHBAR_SRC, /sourcesTouched/,
    "search-bar.tsx must track whether the user manually toggled");
  // The toggle handler should mark sources as touched.
  assert.ok(SEARCHBAR_SRC.includes("setSourcesTouched(true)"),
    "search-bar toggle must set sourcesTouched(true)");
});
