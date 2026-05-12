import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PARSER_SRC = readFileSync(
  join(__dirname, "..", "src", "lib", "artifacts", "parser.ts"),
  "utf8",
);
const TYPES_SRC = readFileSync(
  join(__dirname, "..", "src", "lib", "artifacts", "types.ts"),
  "utf8",
);
const FIXTURES = readFileSync(join(__dirname, "phase5-artifacts.md"), "utf8");

function extractFences(md) {
  const blocks = [];
  const re = /```json\n([\s\S]*?)\n```/g;
  let m;
  while ((m = re.exec(md))) blocks.push(JSON.parse(m[1].trim()));
  return blocks;
}

const blocks = extractFences(FIXTURES);
const validDraft = blocks[0];
const validDiff = blocks[1];
const invalidDraft = blocks[2];
const invalidDiff = blocks[3];

test("ArtifactDiscriminator union covers section types", () => {
  for (const t of ["section-draft", "section-diff"]) {
    assert.match(TYPES_SRC, new RegExp(`["']${t}["']`),
      `types.ts must list "${t}" in ArtifactDiscriminator`);
  }
});

test("parser.ts has switch arms for both Phase 5 types", () => {
  for (const t of ["section-draft", "section-diff"]) {
    assert.match(PARSER_SRC, new RegExp(`case ["']${t}["']`),
      `parser.ts must route "${t}" through a dedicated narrower`);
  }
});

test("section-draft golden has required fields", () => {
  for (const k of [
    "id", "manuscript_slug", "section_id", "section_type", "status",
    "content_md", "version", "library_path", "updated_at",
  ]) {
    assert.ok(k in validDraft, `section-draft missing ${k}`);
  }
  assert.ok(["draft", "reviewed", "final"].includes(validDraft.status));
});

test("section-diff golden has required fields", () => {
  for (const k of ["manuscript_slug", "section_id", "action", "before", "after"]) {
    assert.ok(k in validDiff, `section-diff missing ${k}`);
  }
  assert.ok(["rewrite", "tighten", "check", "humanize"].includes(validDiff.action));
});

test("invalid fixtures lack required fields", () => {
  assert.ok(!("section_id" in invalidDraft), "invalid draft must lack section_id");
  assert.ok(!("before" in invalidDiff), "invalid diff must lack before");
});
