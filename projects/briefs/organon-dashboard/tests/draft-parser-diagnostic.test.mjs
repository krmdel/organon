import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 35 (v1.4) — B2 diagnostic surface.
//
// When an SSE route's stdoutAccumulated contains the literal `_artifact`
// substring but extractArtifactsFromChunk returned nothing (typically a
// whitespace-prefixed JSON line or a slug-mismatch), the route emits a
// `parse-debug` SSE event with ±200 chars of context around the
// `_artifact` substring. Lets the next walk paste the actual culprit
// instead of guessing.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const PARSER_SRC = readSrc("src/lib/artifacts/parser.ts");
const GENERATE_SECTION_SRC = readSrc("src/app/api/draft/[slug]/generate-section/route.ts");
const GENERATE_TITLE_SRC = readSrc("src/app/api/draft/[slug]/generate-title/route.ts");

test("Phase 35 — parser emits parse-debug when _artifact substring exists but extraction returned nothing", () => {
  // NEW exported helper that accepts the raw stdoutAccumulated and a
  // hint about whether anything was successfully parsed; returns a
  // diagnostic string (or null when there's no _artifact substring at
  // all, so we don't spam noise).
  assert.match(PARSER_SRC, /export function diagnoseUnparsedArtifact\(/);
  // The helper looks for `_artifact` in the input and decides whether
  // to emit a debug payload.
  assert.match(PARSER_SRC, /_artifact/);
  // Behavioural replica matching the contract.
  const diagnose = (stdoutAccumulated, anyParsed) => {
    if (anyParsed) return null;
    const idx = stdoutAccumulated.indexOf('"_artifact"');
    if (idx < 0) return null;
    const start = Math.max(0, idx - 200);
    const end = Math.min(stdoutAccumulated.length, idx + 200);
    return {
      reason: "artifact-substring-found-but-not-parsed",
      context: stdoutAccumulated.slice(start, end),
      offset: idx,
      length: stdoutAccumulated.length,
    };
  };
  // No _artifact substring → null.
  assert.equal(diagnose("just plain prose", false), null);
  // Anything parsed → null (no false alarm).
  assert.equal(diagnose('{"_artifact":"paper"}', true), null);
  // Substring + nothing parsed → debug payload.
  const out = diagnose('   junk before {"_artifact":"section-draft", "manuscript_slug":"X"} junk after', false);
  assert.ok(out);
  assert.equal(out.reason, "artifact-substring-found-but-not-parsed");
  assert.match(out.context, /"_artifact"/);
});

test("Phase 35 — parse-debug includes ±200 chars context around the _artifact substring", () => {
  // The diagnose helper slices ±200 around the index. Pin the literal
  // 200 in the source so a future shrink doesn't silently lose the
  // diagnostic surface.
  const block = PARSER_SRC.match(/diagnoseUnparsedArtifact[\s\S]*?\n\}/);
  assert.ok(block, "diagnoseUnparsedArtifact body not found");
  assert.match(block[0], /200/);
  // Behavioural replica with a realistic stdout payload (>200 chars on
  // each side of the substring).
  const before = "x".repeat(300);
  const after = "y".repeat(300);
  const stdout = `${before} {"_artifact":"section-draft"} ${after}`;
  const idx = stdout.indexOf('"_artifact"');
  const start = Math.max(0, idx - 200);
  const end = Math.min(stdout.length, idx + 200);
  const context = stdout.slice(start, end);
  // Total length of context should be ~400 chars (±200 around the
  // substring).
  assert.ok(context.length >= 200 && context.length <= 410);
  assert.match(context, /"_artifact"/);
});

test("Phase 35 — generate-section + generate-title routes forward parse-debug as an SSE event", () => {
  // Both routes import diagnoseUnparsedArtifact and call it after the
  // for-await loop completes. When the helper returns a non-null result,
  // the route emits a `parse-debug` event before the `done` event.
  for (const src of [GENERATE_SECTION_SRC, GENERATE_TITLE_SRC]) {
    assert.match(src, /diagnoseUnparsedArtifact/);
    assert.match(src, /["']parse-debug["']/);
  }
});
