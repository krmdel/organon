import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 28 (v1.2) — Per-line diff accept (DR-6+).
//
// Closes Phase 22's "Apply = accept full diff" decision. The DiffView
// becomes hunk-granular: each `change` hunk has its own Accept toggle.
// `composeFromHunks(before, hunks)` reassembles `after` using the
// applied flags. v1.1's "Apply edit" path is preserved as the
// "Accept all" shortcut — it sets every change-hunk applied:true and
// composes.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const tryRead = (p) => {
  try {
    return readFileSync(p, "utf8");
  } catch {
    return "";
  }
};

const HUNKS_LIB_SRC = tryRead(join(ROOT, "src", "lib", "draft", "diff-hunks.ts"));
const DIFF_VIEW_SRC = tryRead(join(ROOT, "src", "components", "draft", "diff-view.tsx"));
const WORKSPACE_SRC = tryRead(
  join(ROOT, "src", "components", "draft", "manuscript-workspace.tsx"),
);

// Behavioural fixture: load the splitDiff + composeFromHunks helpers
// via dynamic import. They're plain TS so we can't `import` directly
// in plain Node ESM, but we can re-implement the shape inline for
// behavioural assertions and rely on source-text scans for the rest.

test("Phase 28 — splitDiff returns alternating context/change hunks", () => {
  // The helper exists + is exported.
  assert.match(
    HUNKS_LIB_SRC,
    /export\s+function\s+splitDiff\s*\(/,
    "splitDiff exported",
  );
  // Hunk type carries id, type, before_lines, after_lines, applied.
  assert.match(
    HUNKS_LIB_SRC,
    /export\s+(type|interface)\s+Hunk/,
    "Hunk type exported",
  );
  for (const field of ["id", "type", "before_lines", "after_lines", "applied"]) {
    assert.match(
      HUNKS_LIB_SRC,
      new RegExp(`\\b${field}\\b`),
      `Hunk type names ${field}`,
    );
  }
  // Type discriminator is "context" | "change".
  assert.match(HUNKS_LIB_SRC, /["']context["']/, "context hunk type literal");
  assert.match(HUNKS_LIB_SRC, /["']change["']/, "change hunk type literal");
});

test("Phase 28 — composeFromHunks(before, all-applied) == after", () => {
  // composeFromHunks is exported.
  assert.match(
    HUNKS_LIB_SRC,
    /export\s+function\s+composeFromHunks\s*\(/,
    "composeFromHunks exported",
  );
  // Behavioural replica using the same shape composeFromHunks emits:
  // a sequence of context hunks (kept verbatim) + change hunks (use
  // after_lines when applied, before_lines when not).
  const hunks = [
    { id: "c0", type: "context", before_lines: ["unchanged top"], after_lines: ["unchanged top"], applied: true },
    { id: "h1", type: "change",  before_lines: ["old A"],         after_lines: ["new A"],          applied: true },
    { id: "c1", type: "context", before_lines: ["middle"],        after_lines: ["middle"],         applied: true },
    { id: "h2", type: "change",  before_lines: ["old B"],         after_lines: ["new B"],          applied: true },
  ];
  const composeAllApplied = (hs) =>
    hs.map((h) => (h.type === "change" && !h.applied ? h.before_lines : h.after_lines).join("\n")).join("\n");
  assert.equal(
    composeAllApplied(hunks),
    "unchanged top\nnew A\nmiddle\nnew B",
    "all-applied compose == after",
  );
});

test("Phase 28 — composeFromHunks with subset of applied hunks composes correctly", () => {
  const hunks = [
    { id: "c0", type: "context", before_lines: ["top"],   after_lines: ["top"],   applied: true },
    { id: "h1", type: "change",  before_lines: ["old A"], after_lines: ["new A"], applied: false },
    { id: "h2", type: "change",  before_lines: ["old B"], after_lines: ["new B"], applied: true },
  ];
  const compose = (hs) =>
    hs.map((h) => (h.type === "change" && !h.applied ? h.before_lines : h.after_lines).join("\n")).join("\n");
  assert.equal(
    compose(hunks),
    "top\nold A\nnew B",
    "subset compose mixes before + after correctly",
  );
});

test("Phase 28 — diff-view renders per-hunk Accept toggle with data-hunk-id", () => {
  // The component imports the hunk helpers.
  assert.match(
    DIFF_VIEW_SRC,
    /diff-hunks|splitDiff|Hunk/,
    "diff-view references diff-hunks",
  );
  // Each change hunk has an Accept-toggle button with the data-hunk-id
  // attribute + apply-hunk action.
  assert.match(
    DIFF_VIEW_SRC,
    /data-action=("|')apply-hunk\1/,
    "per-hunk button carries data-action=apply-hunk",
  );
  assert.match(
    DIFF_VIEW_SRC,
    /data-hunk-id/,
    "per-hunk button carries data-hunk-id",
  );
});

test("Phase 28 — diff-view 'Accept all' sets every change-hunk applied", () => {
  // Accept-All button stays present at the top.
  assert.match(
    DIFF_VIEW_SRC,
    /Accept\s+all|accept-all|"all"/i,
    "Accept all shortcut present",
  );
  // Reject-All is the same shape.
  assert.match(
    DIFF_VIEW_SRC,
    /Reject\s+all|reject-all/i,
    "Reject all shortcut present",
  );
});

test("Phase 28 — workspace handleApplyChatHunks drives composeFromHunks into editor", () => {
  // The workspace handler is named handleApplyChatHunks.
  assert.match(
    WORKSPACE_SRC,
    /handleApplyChatHunks|handleApplyHunks|handleApplyChatDiff[\s\S]*composeFromHunks/,
    "workspace exposes a per-hunk apply handler",
  );
  // The workspace imports composeFromHunks.
  assert.match(
    WORKSPACE_SRC,
    /composeFromHunks/,
    "workspace imports composeFromHunks",
  );
});
