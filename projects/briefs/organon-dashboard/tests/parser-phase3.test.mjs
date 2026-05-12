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
const FIXTURES = readFileSync(join(__dirname, "phase3-artifacts.md"), "utf8");

function extractFences(md) {
  const blocks = [];
  const re = /```json\n([\s\S]*?)\n```/g;
  let m;
  while ((m = re.exec(md))) blocks.push(m[1].trim());
  return blocks;
}

const allBlocks = extractFences(FIXTURES);
const validIdx = allBlocks.findIndex((b) => b.includes("data-20260520-9fa321") && b.includes("dataframe"));
assert.notStrictEqual(validIdx, -1, "fixture file shape changed — could not locate dataframe golden");

const validBlocks = allBlocks.slice(0, 3); // dataframe / stat-result / figure
const invalidBlocks = allBlocks.slice(3); // malformed sentinels

test("ArtifactDiscriminator union covers Phase 3 types", () => {
  for (const t of ["dataframe", "stat-result", "figure"]) {
    assert.match(
      TYPES_SRC,
      new RegExp(`["']${t}["']`),
      `types.ts must list "${t}" in ArtifactDiscriminator`,
    );
  }
});

test("parser.ts has switch arms for the three Phase 3 types", () => {
  for (const t of ["dataframe", "stat-result", "figure"]) {
    assert.match(
      PARSER_SRC,
      new RegExp(`case ["']${t}["']`),
      `parser.ts must route "${t}" through a dedicated narrower (no longer narrowUnknown)`,
    );
  }
});

test("golden dataframe fixture parses + has required schema fields", () => {
  const obj = JSON.parse(validBlocks[0]);
  assert.equal(obj._artifact, "dataframe");
  assert.equal(obj.schema_version, 1);
  for (const k of [
    "id",
    "project_slug",
    "filename",
    "format",
    "rows_total",
    "columns",
    "preview_rows",
    "data_path",
    "library_path",
  ]) {
    assert.ok(k in obj, `dataframe missing required field: ${k}`);
  }
  assert.ok(Array.isArray(obj.columns) && obj.columns.length > 0);
  assert.ok(Array.isArray(obj.preview_rows));
});

test("golden stat-result fixture parses + has required schema fields", () => {
  const obj = JSON.parse(validBlocks[1]);
  assert.equal(obj._artifact, "stat-result");
  assert.equal(obj.schema_version, 1);
  for (const k of [
    "id",
    "project_slug",
    "test_name",
    "test_label",
    "mode",
    "params",
    "p_value",
    "n",
    "interpretation",
    "results_path",
    "library_path",
  ]) {
    assert.ok(k in obj, `stat-result missing required field: ${k}`);
  }
  assert.ok(["analyze", "power", "validate"].includes(obj.mode));
});

test("golden figure fixture parses + has required schema fields", () => {
  const obj = JSON.parse(validBlocks[2]);
  assert.equal(obj._artifact, "figure");
  assert.equal(obj.schema_version, 1);
  for (const k of [
    "id",
    "project_slug",
    "kind",
    "version",
    "format",
    "params",
    "code_path",
    "png_path",
    "library_path",
    "backend",
  ]) {
    assert.ok(k in obj, `figure missing required field: ${k}`);
  }
  assert.ok(["plot", "image"].includes(obj.kind));
  assert.ok(Number.isInteger(obj.version) && obj.version >= 1);
});

test("invalid fixtures have insufficient fields (parser narrowers must reject)", () => {
  for (const block of invalidBlocks) {
    const obj = JSON.parse(block);
    const requiredByType = {
      dataframe: ["id", "project_slug", "columns", "preview_rows"],
      "stat-result": ["id", "project_slug", "test_name"],
      figure: ["id", "project_slug", "kind", "version"],
    };
    const required = requiredByType[obj._artifact];
    const missing = required.filter((k) => !(k in obj));
    assert.ok(
      missing.length > 0,
      `invalid fixture for ${obj._artifact} accidentally has all required fields: ${block}`,
    );
  }
});
