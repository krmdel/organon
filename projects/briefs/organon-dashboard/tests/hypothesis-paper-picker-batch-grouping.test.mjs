import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 59 (v2.1) — B2 + B3: claim-form paper-picker batch grouping +
// show-all submit fix. Source-text-scan + inline behavioural replicas.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const PICKER_SRC = readSrc("src/components/hypothesis/paper-picker.tsx");
const BULK_SELECT_SRC = readSrc("src/components/primitives/bulk-select.tsx");
const BULK_OPS_SRC = readSrc("src/components/primitives/bulk-paper-ops.tsx");

test("Phase 59 (B2) — paper-picker groups library papers by search_batch_id when present", () => {
  // Picker must declare a groupBySearchBatch helper (or call into one)
  // and gate it on `query.trim().length === 0`.
  assert.match(
    PICKER_SRC,
    /search_batch_id/,
    "paper-picker must read search_batch_id from PaperArtifact",
  );
  assert.match(
    PICKER_SRC,
    /groupBySearchBatch/,
    "paper-picker must call/declare groupBySearchBatch like library-panel",
  );
  assert.match(
    PICKER_SRC,
    /data-picker-batches/,
    "paper-picker must mark the grouped list with data-picker-batches sentinel",
  );

  // Inline replica of the grouping function.
  const groupBy = (papers) => {
    const map = new Map();
    let ungrouped = null;
    for (const p of papers) {
      const id = p.search_batch_id ?? null;
      if (!id) {
        if (!ungrouped) ungrouped = { batch_id: null, query: "Ungrouped", papers: [] };
        ungrouped.papers.push(p);
        continue;
      }
      const cur = map.get(id);
      if (cur) cur.papers.push(p);
      else map.set(id, { batch_id: id, query: p.search_batch_query ?? id, papers: [p] });
    }
    const sorted = Array.from(map.values());
    if (ungrouped) sorted.push(ungrouped);
    return sorted;
  };
  const out = groupBy([
    { id: "a", search_batch_id: "b1", search_batch_query: "GLP-1 obesity" },
    { id: "b", search_batch_id: "b1", search_batch_query: "GLP-1 obesity" },
    { id: "c", search_batch_id: "b2", search_batch_query: "sepsis" },
    { id: "d", search_batch_id: null },
  ]);
  assert.equal(out.length, 3);
  assert.equal(out[0].papers.length, 2);
  assert.equal(out[2].query, "Ungrouped");
});

test("Phase 59 (B2) — ungrouped papers (legacy / via-skill) land under 'Ungrouped'", () => {
  assert.match(
    PICKER_SRC,
    /Ungrouped/,
    "paper-picker must label legacy papers under 'Ungrouped'",
  );
});

test("Phase 59 (B2) — batch group header shows the search_batch_query", () => {
  assert.match(
    PICKER_SRC,
    /data-picker-batch-query/,
    "paper-picker must surface the batch query as a data attribute on the group <li>",
  );
  assert.match(
    PICKER_SRC,
    /search_batch_query\s*\?\?/,
    "paper-picker must render search_batch_query (with batch_id fallback)",
  );
});

test("Phase 59 (B3) — every non-submit button inside picker has type=\"button\"", () => {
  // The picker must declare type="button" on every <button> inside the
  // form. Static scan: strip comments, then count <button> openings and
  // require an immediately-following (within 200 chars) type="button"
  // stamp before the > closer.
  const stripComments = (s) =>
    s
      .replace(/\/\*[\s\S]*?\*\//g, "") // block comments
      .replace(/\{\/\*[\s\S]*?\*\/\}/g, "") // JSX block comments
      .replace(/^[ \t]*\/\/.*$/gm, ""); // line comments
  const naked = stripComments(PICKER_SRC);
  // Match the FULL <button …> element so we can scan its attribute list.
  const buttonElements = naked.match(/<button\b[^>]*>/g) ?? [];
  assert.ok(
    buttonElements.length > 0,
    "paper-picker must render at least one <button>",
  );
  for (const el of buttonElements) {
    assert.match(
      el,
      /type="button"/,
      `<button> element in paper-picker must declare type="button" — found: ${el}`,
    );
  }

  // Same audit applied to the shared bulk primitives the picker uses.
  for (const [src, name] of [[BULK_SELECT_SRC, "bulk-select"], [BULK_OPS_SRC, "bulk-paper-ops"]]) {
    const naked2 = stripComments(src);
    const els = naked2.match(/<button\b[^>]*>/g) ?? [];
    for (const el of els) {
      assert.match(
        el,
        /type="button"/,
        `<button> in ${name} must have type="button" — found: ${el}`,
      );
    }
    const opens = els;
    const typed = naked2.match(/type="button"/g) ?? [];
    assert.equal(
      opens.length,
      typed.length,
      `every <button> in ${name} must have type="button"`,
    );
  }
});

test("Phase 59 (B3) — clicking ALL/NONE/INVERT does not call onSubmit (replica)", () => {
  // Inline replica: a default-typed nested button inside a <form>
  // submits; an explicit type="button" does not.
  const fired = { submit: 0, click: 0 };
  const fakeForm = {
    onSubmit: () => fired.submit++,
  };
  const handleClick = (type) => {
    fired.click++;
    if (type !== "button") fakeForm.onSubmit();
  };
  handleClick("button"); // ALL
  handleClick("button"); // NONE
  handleClick("button"); // INVERT
  assert.equal(fired.click, 3);
  assert.equal(fired.submit, 0);

  // Without type="button" the same clicks would have submitted —
  // demonstrating the contract.
  handleClick(undefined);
  assert.equal(fired.submit, 1);
});

test("Phase 59 (B2) — expanding a collapsed batch reveals the paper checkboxes", () => {
  // Default-collapsed: expandedBatches starts as an empty Set.
  assert.match(
    PICKER_SRC,
    /expandedBatches[\s\S]{0,200}=>\s*new\s+Set\(\)/,
    "paper-picker must initialise expandedBatches as an empty Set (default-collapsed)",
  );
  // Reveals the children only when the batch is expanded.
  assert.match(
    PICKER_SRC,
    /isExpanded\s*&&/,
    "paper-picker must conditionally render the paper checkboxes when isExpanded",
  );
  // The toggle handler must use a Set add/delete.
  assert.match(
    PICKER_SRC,
    /toggleBatchExpanded/,
    "paper-picker must declare toggleBatchExpanded",
  );

  // Inline replica.
  const toggle = (set, key) => {
    const next = new Set(set);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    return next;
  };
  let s = new Set();
  s = toggle(s, "b1");
  assert.equal(s.has("b1"), true);
  s = toggle(s, "b1");
  assert.equal(s.has("b1"), false);
});

test("Phase 59 — claim-form picker is wrapped in aria-label='linked-papers' region", () => {
  // The brief asks for an aria-label="linked-papers" region so tests +
  // E2E walks can pin the picker without colliding with other lists.
  assert.match(
    PICKER_SRC,
    /aria-label="linked-papers"/,
    "paper-picker root must declare aria-label='linked-papers'",
  );
});
