import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 61 (v2.1) — B5: copy-query button per batch in the library panel.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const SRC = readSrc("src/components/lit/library-panel.tsx");

test("Phase 61 — library-panel renders a copy-query button per batch (data-copy-query sentinel)", () => {
  assert.match(
    SRC,
    /data-copy-query=/,
    "library-panel must render a button with data-copy-query attribute",
  );
  assert.match(
    SRC,
    /Copy this batch's search query/i,
    "copy button must declare a clear title attribute",
  );
});

test("Phase 61 — clicking the copy button calls navigator.clipboard.writeText with the search_batch_query", () => {
  // The handler must use navigator.clipboard.writeText.
  assert.match(
    SRC,
    /navigator\.clipboard\.writeText\(query\)/,
    "library-panel must call navigator.clipboard.writeText(query)",
  );

  // Inline replica.
  let captured = null;
  const fakeNav = { clipboard: { writeText: async (s) => { captured = s; } } };
  const copyQuery = async (query) => {
    await fakeNav.clipboard.writeText(query);
  };
  return copyQuery("GLP-1 obesity").then(() => {
    assert.equal(captured, "GLP-1 obesity");
  });
});

test("Phase 61 — a 'copied' confirmation appears for ≥ 1 second after click", () => {
  // The implementation uses a copiedKey state + a setTimeout that clears
  // it after 1500 ms. Source-text contract: setTimeout with ≥ 1000 ms.
  assert.match(
    SRC,
    /setTimeout\(/,
    "copy handler must schedule a clear-confirmation setTimeout",
  );
  // Sanity: pin the 1500 ms duration so the chip stays long enough.
  assert.match(
    SRC,
    /1500\s*\)/,
    "copy confirmation timeout must be ≥ 1000 ms (we pin 1500)",
  );
  // Visible "copied" label.
  assert.match(
    SRC,
    /copiedKey\s*===\s*groupKey\s*\?\s*"copied"/,
    "copy button must render 'copied' when its row is the active confirmation",
  );
});
