import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 61 (v2.1) — C1: sources panel help-text + per-kind <details>.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const SRC = readSrc("src/components/draft/source-linkage-panel.tsx");

test("Phase 61 — source-linkage-panel header includes the 'feed every section's prompt' help line", () => {
  // The cryptic one-liner moved out; the new help paragraph reads
  // researcher-readably. The data-sources-help sentinel pins it for E2E.
  assert.match(
    SRC,
    /data-sources-help/,
    "panel must mark the help paragraph with data-sources-help",
  );
  assert.match(
    SRC,
    /feed every section/i,
    "help-text must mention 'feed every section' so the researcher knows what 'sources' does",
  );
  assert.match(
    SRC,
    /Empty linkage/,
    "help-text must mention 'Empty linkage' (defaults-to-everything semantics)",
  );
  assert.match(
    SRC,
    /per-section[\s\S]{0,200}override/,
    "help-text must point at the per-section override escape hatch",
  );
});

test("Phase 61 — panel mounts a <details> block with per-kind explanation", () => {
  assert.match(
    SRC,
    /data-sources-help-details/,
    "panel must mount a data-sources-help-details element",
  );
  assert.match(
    SRC,
    /<details/,
    "panel must use a <details> element for the expandable per-kind block",
  );
  assert.match(
    SRC,
    /<summary/,
    "the <details> block must include a <summary> trigger",
  );
  // Each of the four linkage kinds must appear in the explanation.
  for (const kind of ["Hypotheses", "Papers", "Figures", "Datasets"]) {
    assert.match(
      SRC,
      new RegExp(kind),
      `details block must explain '${kind}'`,
    );
  }
});
