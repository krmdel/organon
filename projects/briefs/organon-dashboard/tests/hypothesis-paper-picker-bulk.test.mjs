import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 13d (v1.0.1) — Hypothesis paper-picker bulk-select (H-2).
//
// PaperPicker reuses the BulkSelect primitive (Phase 12c D-8) so the
// hypothesis form gets All / None / Invert + count chip without
// branching the primitive's contract. The brief (NEXT_SESSION_phase13-16
// §7) explicitly forbids forking the primitive — this test pins the
// reuse pattern.
//
// Source-text scan + behavioural mirror pattern (consistent with
// state-persistence, draft-code-spans, draft-export-error-panel).

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const PICKER_SRC = readFileSync(
  join(ROOT, "src", "components", "hypothesis", "paper-picker.tsx"),
  "utf8",
);
const BULK_SRC = readFileSync(
  join(ROOT, "src", "components", "primitives", "bulk-select.tsx"),
  "utf8",
);

test("paper-picker imports BulkSelect from the shared primitive (no fork)", () => {
  assert.match(
    PICKER_SRC,
    /import \{ BulkSelect \} from "@\/components\/primitives\/bulk-select"/,
  );
  // The primitive itself ships with the documented selection API — the
  // picker must not reach for a renamed copy.
  assert.match(BULK_SRC, /export function BulkSelect</);
  assert.match(BULK_SRC, /selectedKeys: Set<string>/);
});

test("paper-picker wires BulkSelect against the full library, keyed by paper id", () => {
  // Items are the full library (not the filtered subset) so "All"
  // semantics stay predictable across active search queries.
  assert.match(PICKER_SRC, /<BulkSelect[\s\S]+?items=\{library\}/);
  assert.match(PICKER_SRC, /keyOf=\{\(p\) => p\.id\}/);
  assert.match(PICKER_SRC, /selectedKeys=\{selected\}/);
  assert.match(PICKER_SRC, /label="papers"/);
});

test("paper-picker preserves library order when emitting selected ids", () => {
  // The on-change adapter filters library by selected-set membership
  // rather than spreading Array.from(set) — Set iteration order is
  // insertion order, which is NOT the library order. The filter
  // approach guarantees the caller receives ids in library order.
  assert.match(
    PICKER_SRC,
    /onChange\(library\.filter\(\(p\) => next\.has\(p\.id\)\)\.map\(\(p\) => p\.id\)\)/,
  );
});

test("BulkSelect 'All' / 'None' / 'Invert' adapter behaves correctly when called from the picker", () => {
  // Behavioural mirror: re-implement the adapter the picker passes to
  // BulkSelect.onChange and verify the round-trip preserves library
  // order on All, empties on None, and flips on Invert.
  const library = [
    { id: "p1", title: "alpha" },
    { id: "p2", title: "beta" },
    { id: "p3", title: "gamma" },
  ];
  const adapter = (next) =>
    library.filter((p) => next.has(p.id)).map((p) => p.id);

  // All: BulkSelect emits the full id set.
  assert.deepEqual(
    adapter(new Set(library.map((p) => p.id))),
    ["p1", "p2", "p3"],
  );
  // None: BulkSelect emits an empty set.
  assert.deepEqual(adapter(new Set()), []);
  // Invert from {p1, p3} starts as {p2}; library order preserved.
  const before = new Set(["p1", "p3"]);
  const inverted = new Set();
  for (const p of library) {
    if (!before.has(p.id)) inverted.add(p.id);
  }
  assert.deepEqual(adapter(inverted), ["p2"]);
});

test("paper-picker still renders the existing search input + checkbox list (no regression)", () => {
  // Sanity: the BulkSelect addition must not displace the existing
  // surface. Search input, count chip, and the visible checkbox row
  // stay where they were.
  assert.match(PICKER_SRC, /placeholder="Filter library by title \/ journal \/ year"/);
  assert.match(PICKER_SRC, /\{value\.length\}\/\{library\.length\}/);
  assert.match(PICKER_SRC, /<input[\s\S]+?type="checkbox"/);
});
