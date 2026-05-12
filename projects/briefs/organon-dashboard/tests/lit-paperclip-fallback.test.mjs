import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 55 (v2.1) — A1: paperclip MCP auth + cleaner fallback banner.
// Source-text-scan TDD per the v1.x–v2.0 methodology; no live HTTP calls.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const PAPERCLIP_SRC = readSrc("src/lib/lit/paperclip-search.ts");
const SEARCH_SRC = readSrc("src/lib/lit/search.ts");
const ENV_SRC = readSrc("src/lib/env.ts");
const ENV_EXAMPLE = readSrc("../../../.env.example");

test("Phase 55 — env.ts exposes paperclipApiKey() + paperclipDisabled() helpers", () => {
  assert.match(
    ENV_SRC,
    /export\s+function\s+paperclipApiKey\s*\(/,
    "env.ts must export a paperclipApiKey() helper that reads PAPERCLIP_API_KEY",
  );
  assert.match(
    ENV_SRC,
    /process\.env\.PAPERCLIP_API_KEY/,
    "paperclipApiKey must read from process.env.PAPERCLIP_API_KEY",
  );
  assert.match(
    ENV_SRC,
    /export\s+function\s+paperclipDisabled\s*\(/,
    "env.ts must export a paperclipDisabled() helper that reads PAPERCLIP_DISABLED",
  );
  assert.match(
    ENV_SRC,
    /process\.env\.PAPERCLIP_DISABLED/,
    "paperclipDisabled must read from process.env.PAPERCLIP_DISABLED",
  );
});

test("Phase 55b — auth header attached as X-API-Key when PAPERCLIP_API_KEY is set", () => {
  // Wrapper imports the helper.
  assert.match(
    PAPERCLIP_SRC,
    /paperclipApiKey/,
    "paperclip-search.ts must import paperclipApiKey from env",
  );
  // Phase 55b — paperclip's gxl.ai endpoint authenticates via X-API-Key,
  // not Authorization: Bearer. Live-walk against /docs confirmed Bearer
  // returns 401 "Invalid authentication token" while X-API-Key returns 200.
  assert.match(
    PAPERCLIP_SRC,
    /["']X-API-Key["']\s*\]\s*=\s*apiKey/,
    "paperclip-search.ts must stamp X-API-Key header (not Authorization: Bearer)",
  );
  // The Bearer scheme MUST NOT be used — it gets rejected by paperclip.
  assert.doesNotMatch(
    PAPERCLIP_SRC,
    /Authorization[^\n]*Bearer\s+\$\{/,
    "paperclip-search.ts must not stamp Authorization: Bearer (paperclip rejects it)",
  );

  // Inline replica: header construction is gated on key presence.
  const buildHeaders = (apiKey) => {
    const h = { "Content-Type": "application/json", Accept: "application/json, text/event-stream" };
    if (apiKey) h["X-API-Key"] = apiKey;
    return h;
  };
  assert.equal(buildHeaders(undefined)["X-API-Key"], undefined);
  assert.equal(buildHeaders("gxl_xxx")["X-API-Key"], "gxl_xxx");
});

test("Phase 55b — wrapper calls the 'paperclip' tool with a CLI-style command argument", () => {
  // Live-walk found the public MCP server exposes ONE tool named
  // 'paperclip' that takes { command: "<cli string>" } — not a 'search'
  // tool with { query, n }. The wrapper must use the right shape or
  // every call returns -32602 "Unknown tool: search".
  assert.match(
    PAPERCLIP_SRC,
    /name:\s*"paperclip"/,
    "paperclip-search.ts must call the 'paperclip' MCP tool",
  );
  assert.match(
    PAPERCLIP_SRC,
    /arguments:\s*\{\s*command\s*\}/,
    "paperclip-search.ts must pass arguments: { command }",
  );
  // The command must be CLI-style: search "<query>" -n <N>.
  assert.match(
    PAPERCLIP_SRC,
    /search\s+"\$\{safeQuery\}"\s+-n\s+\$\{/,
    "paperclip-search.ts must build a CLI-style 'search \"...\" -n N' command",
  );
});

test("Phase 55b — parsePaperclipText extracts paper blocks from the CLI response", () => {
  // Source-text exposure of the parser export.
  assert.match(
    PAPERCLIP_SRC,
    /export\s+function\s+parsePaperclipText/,
    "paperclip-search.ts must export parsePaperclipText for direct testing",
  );

  // Replica of the parser's block-detection rule (numbered indented head).
  const text = `Found 2 papers  [s_aaa]

  1. First paper title
     Author One, Author Two
     bio_xxx · bioRxiv · 2025-11-29
     https://doi.org/10.1234/example
     "Abstract one."

  2. Second paper title
     Author Three
     pmc_yyy · PMC · 2024-01-15
     https://doi.org/10.4321/example2
     "Abstract two."
`;
  const blocks = [];
  let cur = [];
  for (const ln of text.split(/\r?\n/)) {
    if (/^\s{2}\d+\.\s/.test(ln)) {
      if (cur.length) blocks.push(cur);
      cur = [ln];
    } else if (cur.length) {
      cur.push(ln);
    }
  }
  if (cur.length) blocks.push(cur);
  assert.equal(blocks.length, 2, "parser must split on numbered indented heads");
});

test("Phase 55 — PAPERCLIP_DISABLED=1 short-circuits the wrapper without HTTP call", () => {
  // The wrapper exports a sentinel error class so callers can handle the
  // disabled path without surfacing a noisy banner.
  assert.match(
    PAPERCLIP_SRC,
    /class\s+PaperclipDisabledError/,
    "paperclip-search.ts must export a PaperclipDisabledError sentinel",
  );
  // And short-circuits BEFORE calling fetch when paperclipDisabled() returns true.
  assert.match(
    PAPERCLIP_SRC,
    /paperclipDisabled\s*\(\s*\)/,
    "paperclip-search.ts must call paperclipDisabled() at the top of the wrapper",
  );
  // Wrapper must throw the sentinel before fetch when disabled.
  const idxDisabled = PAPERCLIP_SRC.search(/paperclipDisabled\s*\(\s*\)/);
  const idxFetch = PAPERCLIP_SRC.search(/await\s+fetch\s*\(/);
  assert.ok(idxDisabled > 0, "paperclipDisabled() must appear");
  assert.ok(idxFetch > 0, "fetch() must appear");
  assert.ok(idxDisabled < idxFetch, "paperclipDisabled() must be checked BEFORE fetch()");
});

test("Phase 55 — soft_errors message reads 'temporarily unavailable', not raw 'HTTP 401'", () => {
  // The user-facing banner must NOT leak HTTP plumbing.
  assert.match(
    SEARCH_SRC,
    /temporarily unavailable/,
    "search.ts must surface the cleaner 'temporarily unavailable' banner copy",
  );
  // And must recognise auth failures (HTTP 401/403) so the cleaner copy fires.
  assert.match(
    SEARCH_SRC,
    /HTTP\\s4\(0\[13\]\)|HTTP\s*4\[03\]|4\(0\[13\]\)/,
    "search.ts must classify auth-style failures (4xx) for the cleaner banner",
  );

  // Inline replica of the banner-classification logic.
  const classify = (msg) => {
    const auth = /HTTP\s4(0[13])/i.test(msg) || /temporarily unavailable/i.test(msg);
    return auth
      ? "paperclip: temporarily unavailable — using PubMed/arXiv/OpenAlex/S2 instead"
      : `paperclip: ${msg} — falling back to API tier`;
  };
  const fromWrapper = "paperclip temporarily unavailable (HTTP 401)";
  assert.match(classify(fromWrapper), /temporarily unavailable/);
  assert.doesNotMatch(classify(fromWrapper), /HTTP 401/);
  assert.match(classify("paperclip transport: ECONNREFUSED"), /falling back to API tier/);
});

test("Phase 55 — PaperclipDisabledError is silenced (no soft_errors entry)", () => {
  // search.ts must recognise the sentinel and skip the soft_errors push.
  assert.match(
    SEARCH_SRC,
    /PaperclipDisabledError/,
    "search.ts must import + reference PaperclipDisabledError",
  );
  assert.match(
    SEARCH_SRC,
    /e\s+instanceof\s+PaperclipDisabledError/,
    "search.ts must instanceof-check PaperclipDisabledError before pushing soft_errors",
  );

  // Inline replica: when sentinel fires, soft_errors stays empty.
  const handle = (e) => {
    const soft_errors = [];
    if (e && e.name === "PaperclipDisabledError") {
      // silent
    } else {
      soft_errors.push(`paperclip: ${e.message}`);
    }
    return soft_errors;
  };
  const sentinel = Object.assign(new Error("paperclip disabled"), { name: "PaperclipDisabledError" });
  assert.deepEqual(handle(sentinel), []);
  assert.deepEqual(handle(new Error("ECONNREFUSED")), ["paperclip: ECONNREFUSED"]);
});

test("Phase 55 — .env.example documents PAPERCLIP_API_KEY + PAPERCLIP_DISABLED", () => {
  assert.match(
    ENV_EXAMPLE,
    /^PAPERCLIP_API_KEY=/m,
    ".env.example must declare PAPERCLIP_API_KEY",
  );
  assert.match(
    ENV_EXAMPLE,
    /^PAPERCLIP_DISABLED=/m,
    ".env.example must declare PAPERCLIP_DISABLED",
  );
});
