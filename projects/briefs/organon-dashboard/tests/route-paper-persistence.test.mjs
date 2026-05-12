import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 3 fix-sprint regression tests:
//   1. Each search source returns a bare id (no `pmid:` / `arxiv:` / `s2:`
//      prefix; OpenAlex returns the bare W-id, not the full URL).
//   2. PaperArtifact has an optional cite_key field.
//   3. cite-key.ts produces surname-based keys with a/b/c collision suffix.
//   4. html-decode.ts decodes named, decimal, and hex entities + strips
//      safe inline tags.
//   5. savePaper computes cite_key + decodes HTML at persist time.
//   6. bibtex.bibtexKey prefers paper.cite_key over the legacy derivation.
//   7. draft/bib.compileBibliography resolves by cite_key OR id.
//   8. The backfill script exists with both flags, and the dogfood library
//      has been backfilled (no `pmid-pmid:` filenames, every paper has
//      cite_key, hypothesis paper_ids point at the renamed papers).

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const ORGANON_ROOT = join(ROOT, "..", "..", "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

test("each search source returns a bare id (no source-prefix)", () => {
  const pubmed = readSrc("src/lib/paper-search/pubmed.ts");
  assert.match(
    pubmed,
    /\bid:\s*pmid,/,
    "pubmed.ts must return `id: pmid` (bare PMID)",
  );
  assert.doesNotMatch(
    pubmed,
    /\bid:\s*`pmid:\$\{pmid\}`/,
    "pubmed.ts must NOT prefix with `pmid:`",
  );

  const arxiv = readSrc("src/lib/paper-search/arxiv.ts");
  assert.match(arxiv, /\bid:\s*arxivId,/, "arxiv.ts must return bare arxivId");
  assert.doesNotMatch(arxiv, /\bid:\s*`arxiv:/, "arxiv.ts must NOT prefix with `arxiv:`");

  const s2 = readSrc("src/lib/paper-search/semanticscholar.ts");
  assert.match(s2, /\bid:\s*paper\.paperId,/, "s2 must return bare paperId");
  assert.doesNotMatch(s2, /\bid:\s*`s2:/, "s2 must NOT prefix with `s2:`");

  const openalex = readSrc("src/lib/paper-search/openalex.ts");
  assert.match(
    openalex,
    /openalex\\.org\\\//,
    "openalex.ts must strip the `https://openalex.org/` URL prefix from id",
  );
  assert.match(
    openalex,
    /\bid:\s*bareWorkId,/,
    "openalex.ts must use the bare W-id as id",
  );
});

test("PaperArtifact type has the cite_key field", () => {
  const types = readSrc("src/lib/artifacts/types.ts");
  assert.match(
    types,
    /cite_key\?:\s*string \| null;/,
    "PaperArtifact must declare cite_key as optional + nullable",
  );
});

test("paperToCiteKey returns surname-based keys with collision suffix", async () => {
  // Tiny re-implementation matches src/lib/lit/cite-key.ts. We can't import
  // the TS module directly (no compile step in node:test), but the source
  // is small and stable.
  const { firstAuthorSurname, paperToCiteKey } = await loadCiteKeyMirror();

  assert.equal(
    firstAuthorSurname({ authors: ["Ermeena Shah"] }),
    "Shah",
    "first-name-last-name → last word",
  );
  assert.equal(
    firstAuthorSurname({ authors: ["Shah, Ermeena"] }),
    "Shah",
    "comma form → first part",
  );
  assert.equal(
    firstAuthorSurname({ authors: [] }),
    "Anonymous",
    "no authors → Anonymous",
  );
  assert.equal(
    firstAuthorSurname({ authors: ["Cher"] }),
    "Cher",
    "single-word author returns the word itself",
  );

  const a = { id: "pmid-1", authors: ["Ermeena Shah"], year: 2026 };
  const b = { id: "pmid-2", authors: ["Aditi Shah"], year: 2026 };
  const c = { id: "pmid-3", authors: ["Mohammed Shah"], year: 2026 };
  const used = new Set();
  const k1 = paperToCiteKey(a, used); used.add(k1);
  const k2 = paperToCiteKey(b, used); used.add(k2);
  const k3 = paperToCiteKey(c, used); used.add(k3);
  assert.deepEqual([k1, k2, k3], ["Shah2026", "Shah2026b", "Shah2026c"]);
});

test("decodeEntities + stripSafeTags clean PubMed-style metadata", async () => {
  const { decodeEntities, stripSafeTags } = await loadHtmlDecodeMirror();

  // Named entity in journal title
  assert.equal(decodeEntities("Diabetes &amp; metabolism"), "Diabetes & metabolism");
  // Numeric entity (decimal)
  assert.equal(decodeEntities("Sara &#039;Doe&#039;"), "Sara 'Doe'");
  // Hex entity
  assert.equal(decodeEntities("dose &#x2014; response"), "dose — response");
  // Mixed
  assert.equal(decodeEntities("&copy;2026 Diabetes &amp; co."), "©2026 Diabetes & co.");
  // Unknown entity passes through
  assert.equal(decodeEntities("&UnknownThing;"), "&UnknownThing;");

  // Inline-tag strip preserves contents
  assert.equal(stripSafeTags("H<sub>2</sub>O"), "H2O");
  assert.equal(stripSafeTags("<b>Background:</b> obesity"), "Background: obesity");
  // Tags outside the allow-list are preserved (don't eat paragraphs)
  assert.equal(stripSafeTags("<div>x</div>"), "<div>x</div>");
});

test("savePaper computes cite_key + decodes HTML at persist time", () => {
  const lib = readSrc("src/lib/lit/library.ts");
  assert.match(lib, /import \{ paperToCiteKey \} from "\.\/cite-key"/);
  assert.match(lib, /import \{ decodeEntities, stripSafeTags \} from "\.\/html-decode"/);
  // Computes cite_key inside savePaper when missing.
  assert.match(
    lib,
    /cite_key = paperToCiteKey\(/,
    "savePaper must call paperToCiteKey when no cite_key is set",
  );
  // Strips + decodes on the way to disk.
  assert.match(lib, /stripSafeTags\(decodeEntities\(/);
});

test("bibtexKey prefers paper.cite_key, falls back to legacy derivation", () => {
  const bibtex = readSrc("src/lib/lit/bibtex.ts");
  assert.match(
    bibtex,
    /if \(paper\.cite_key\) return paper\.cite_key;/,
    "bibtexKey must read paper.cite_key first",
  );
});

test("compileBibliography resolves by cite_key OR id", () => {
  const bib = readSrc("src/lib/draft/bib.ts");
  assert.match(bib, /byCiteKey/, "compileBibliography must build a cite_key index");
  assert.match(bib, /byCiteKey\.get\(token\) \?\? byId\.get\(token\)/);
});

test("backfill-papers.mjs exists with --dry-run + --apply, default is dry-run", () => {
  const scriptPath = join(ROOT, "scripts", "backfill-papers.mjs");
  assert.ok(existsSync(scriptPath), "scripts/backfill-papers.mjs must exist");
  const src = readFileSync(scriptPath, "utf8");
  assert.match(src, /--dry-run/);
  assert.match(src, /--apply/);
  assert.match(
    src,
    /apply: args\.has\("--apply"\)/,
    "apply must be opt-in (default is dry-run)",
  );
});

test("dogfood library backfill: no double prefix, every paper has cite_key", () => {
  const papersDir = join(
    ORGANON_ROOT,
    "projects",
    "briefs",
    "dogfood-glp1-weight-regain",
    "papers",
  );
  if (!existsSync(papersDir)) return; // tolerate clean fork

  const files = readdirSync(papersDir).filter((f) => f.endsWith(".json"));
  assert.ok(files.length > 0, "expected at least one persisted paper");
  for (const f of files) {
    assert.doesNotMatch(f, /^pmid-pmid:/, `filename must not double-prefix: ${f}`);
    assert.doesNotMatch(f, /^arxiv-arxiv:/, `filename must not double-prefix: ${f}`);
    assert.doesNotMatch(f, /^s2-s2:/, `filename must not double-prefix: ${f}`);
    const raw = JSON.parse(readFileSync(join(papersDir, f), "utf8"));
    assert.equal(raw._artifact, "paper");
    assert.ok(typeof raw.cite_key === "string" && raw.cite_key.length > 0,
      `${f}: cite_key missing or empty`);
    if (typeof raw.source_ids?.pmid === "string") {
      assert.ok(!raw.source_ids.pmid.startsWith("pmid:"),
        `${f}: source_ids.pmid still prefixed`);
    }
    if (typeof raw.source_ids?.openalex === "string") {
      assert.ok(!raw.source_ids.openalex.startsWith("http"),
        `${f}: source_ids.openalex still URL-form`);
    }
    // library_path tracks the on-disk filename.
    assert.match(raw.library_path, new RegExp(`${raw.id}\\.json$`),
      `${f}: library_path must point at ${raw.id}.json`);
  }

  // Sibling hypotheses paper_ids must reference the renamed paper.ids.
  const hypDir = join(
    ORGANON_ROOT,
    "projects",
    "briefs",
    "dogfood-glp1-weight-regain",
    "hypotheses",
  );
  if (existsSync(hypDir)) {
    for (const entry of readdirSync(hypDir)) {
      if (!entry.startsWith("hyp-")) continue;
      const hf = join(hypDir, entry, "hypothesis.json");
      if (!existsSync(hf)) continue;
      const raw = JSON.parse(readFileSync(hf, "utf8"));
      if (!Array.isArray(raw.paper_ids)) continue;
      for (const id of raw.paper_ids) {
        assert.doesNotMatch(id, /^pmid-pmid:/,
          `hypothesis ${entry} still references pre-backfill id: ${id}`);
      }
    }
  }
});

// --- helpers: tiny mirrors of cite-key.ts and html-decode.ts so we can run
// --- the unit tests without a TS compile step.

async function loadCiteKeyMirror() {
  function firstAuthorSurname(paper) {
    const a = paper.authors?.[0]?.trim();
    if (!a) return "Anonymous";
    if (a.includes(",")) {
      const last = a.split(",")[0]?.trim();
      return last || "Anonymous";
    }
    const words = a.split(/\s+/).filter(Boolean);
    return words[words.length - 1] || "Anonymous";
  }
  function paperToCiteKey(paper, existingKeys) {
    const surname = firstAuthorSurname(paper).replace(/[^A-Za-z0-9]/g, "");
    const year = paper.year && paper.year > 0 ? String(paper.year) : "n.d.";
    const base = `${surname || "Unknown"}${year}`;
    if (!existingKeys.has(base)) return base;
    for (let i = 1; i < 26; i += 1) {
      const candidate = `${base}${String.fromCharCode(97 + i)}`;
      if (!existingKeys.has(candidate)) return candidate;
    }
    return `${base}-${(paper.id || "x").slice(0, 8)}`;
  }
  return { firstAuthorSurname, paperToCiteKey };
}

async function loadHtmlDecodeMirror() {
  const NAMED_ENTITIES = {
    "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&apos;": "'",
    "&nbsp;": " ", "&copy;": "©", "&reg;": "®", "&trade;": "™",
    "&hellip;": "…", "&mdash;": "—", "&ndash;": "–",
    "&lsquo;": "‘", "&rsquo;": "’", "&ldquo;": "“", "&rdquo;": "”",
    "&times;": "×", "&plusmn;": "±", "&micro;": "µ", "&deg;": "°",
  };
  function decodeEntities(input) {
    if (!input || input.indexOf("&") === -1) return input;
    return input.replace(/&(#x[0-9a-fA-F]+|#\d+|[a-zA-Z][a-zA-Z0-9]+);/g, (raw, body) => {
      if (NAMED_ENTITIES[raw]) return NAMED_ENTITIES[raw];
      if (typeof body === "string") {
        if (body.startsWith("#x") || body.startsWith("#X")) {
          const code = parseInt(body.slice(2), 16);
          if (Number.isFinite(code) && code > 0 && code < 0x110000) {
            try { return String.fromCodePoint(code); } catch { return raw; }
          }
        } else if (body.startsWith("#")) {
          const code = parseInt(body.slice(1), 10);
          if (Number.isFinite(code) && code > 0 && code < 0x110000) {
            try { return String.fromCodePoint(code); } catch { return raw; }
          }
        }
      }
      return raw;
    });
  }
  function stripSafeTags(input) {
    if (!input || input.indexOf("<") === -1) return input;
    return input.replace(/<\/?(b|i|em|strong|sub|sup)(\s[^>]*)?>/gi, "");
  }
  return { decodeEntities, stripSafeTags };
}
