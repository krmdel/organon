import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const TYPES_SRC = readFileSync(
  join(__dirname, "..", "src", "lib", "artifacts", "types.ts"),
  "utf8",
);
const FIXTURES = readFileSync(join(__dirname, "phase4-artifacts.md"), "utf8");

function extractFences(md) {
  const blocks = [];
  const re = /```json\n([\s\S]*?)\n```/g;
  let m;
  while ((m = re.exec(md))) blocks.push(JSON.parse(m[1].trim()));
  return blocks;
}

const [v1, v2, v3] = extractFences(FIXTURES);

test("FigureArtifact v2 fields are declared on the type", () => {
  for (const field of ["mask_path", "locked", "parent_version"]) {
    assert.match(
      TYPES_SRC,
      new RegExp(`\\b${field}\\??:`),
      `types.ts must declare ${field} on FigureArtifact`,
    );
  }
});

test("v1 figure (Gemini generate) has parent_version=null and no mask_path", () => {
  assert.equal(v1._artifact, "figure");
  assert.equal(v1.version, 1);
  assert.equal(v1.parent_version, null);
  assert.equal(v1.mask_path, null);
  assert.equal(v1.backend, "gemini");
  assert.equal(v1.kind, "image");
  assert.equal(v1.locked, false);
});

test("v2 figure (FAL inpaint) carries parent_version + mask_path + cost", () => {
  assert.equal(v2._artifact, "figure");
  assert.equal(v2.version, 2);
  assert.equal(v2.parent_version, 1);
  assert.equal(typeof v2.mask_path, "string");
  assert.match(v2.mask_path, /\/mask\/v2\.png$/);
  assert.equal(v2.backend, "fal-flux-fill");
  assert.equal(typeof v2.cost_cents, "number");
  assert.ok(v2.cost_cents > 0);
  assert.equal(v2.locked, false);
});

test("locked figure has caption + alt_text + locked=true", () => {
  assert.equal(v3.locked, true);
  assert.equal(typeof v3.caption, "string");
  assert.ok(v3.caption.length > 20);
  assert.equal(typeof v3.alt_text, "string");
  assert.ok(v3.alt_text.length > 10);
});

test("FigureBackend union includes the four Phase 1+3+4 backends", () => {
  for (const b of ["matplotlib", "seaborn", "gemini", "fal-flux-fill"]) {
    assert.match(
      TYPES_SRC,
      new RegExp(`["']${b}["']`),
      `FigureBackend must include "${b}"`,
    );
  }
});
