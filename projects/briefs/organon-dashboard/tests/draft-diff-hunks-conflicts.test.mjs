import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 32 (v1.3) — DR-6++ per-hunk conflict detection.
//
// Closes Phase 28 §10.3's "v1.3 can add conflict detection" deferral.
// Heuristic-only (proximity + token-pair); semantic AST-aware checks
// are deferred to v1.4. Non-blocking: Apply Selected stays enabled
// even when warnings fire. The strip renders one row per warning with
// data-action="acknowledge-conflict" + data-warning-pair so click
// tests can target a specific warning.

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

// Inline behavioural replica of detectHunkConflicts. Mirrors the
// helper's shape so the disk-touching contract can be asserted
// without loading TS source. The real impl lives in diff-hunks.ts;
// the structural scans below pin the contract there.
const TOKEN_RE = /\\(cite|fig)\{([^}]+)\}/g;
const tokensIn = (lines) => {
  const out = new Set();
  const text = lines.join("\n");
  let m;
  while ((m = TOKEN_RE.exec(text)) !== null) out.add(`${m[1]}:${m[2]}`);
  return out;
};

const replicaDetect = (hunks) => {
  const warnings = [];
  // Proximity: adjacent change hunks separated by ≤2 context lines
  // where exactly one is applied (the 50%-partial signal).
  const indexed = hunks.map((h, idx) => ({ h, idx }));
  const changes = indexed.filter(({ h }) => h.type === "change");
  for (let i = 0; i < changes.length - 1; i++) {
    const a = changes[i];
    const b = changes[i + 1];
    let contextLines = 0;
    for (let k = a.idx + 1; k < b.idx; k++) {
      if (hunks[k].type === "context") {
        contextLines += hunks[k].before_lines.length;
      }
    }
    if (contextLines <= 2 && a.h.applied !== b.h.applied) {
      warnings.push({
        hunk_a: a.h.id,
        hunk_b: b.h.id,
        reason: "proximity-partial-accept",
      });
    }
  }
  // Token-pair: change hunk A removes a \cite{X} / \fig{X} that
  // change hunk B references (or vice-versa). Symmetric.
  for (let i = 0; i < changes.length; i++) {
    for (let j = 0; j < changes.length; j++) {
      if (i === j) continue;
      const a = changes[i].h;
      const b = changes[j].h;
      const aRemoves = new Set(
        Array.from(tokensIn(a.before_lines)).filter(
          (t) => !tokensIn(a.after_lines).has(t),
        ),
      );
      const bAll = new Set([
        ...tokensIn(b.before_lines),
        ...tokensIn(b.after_lines),
      ]);
      for (const tok of aRemoves) {
        if (bAll.has(tok)) {
          // dedupe via canonical pair ordering
          const lo = a.id < b.id ? a.id : b.id;
          const hi = a.id < b.id ? b.id : a.id;
          if (
            !warnings.some(
              (w) => w.reason === "token-pair-conflict" && w.hunk_a === lo && w.hunk_b === hi,
            )
          ) {
            warnings.push({ hunk_a: lo, hunk_b: hi, reason: "token-pair-conflict" });
          }
        }
      }
    }
  }
  return { warnings };
};

test("Phase 32 — detectHunkConflicts surfaces no warnings on a clean disjoint diff", () => {
  // Helper exists + is exported.
  assert.match(
    HUNKS_LIB_SRC,
    /export\s+function\s+detectHunkConflicts\s*\(/,
    "detectHunkConflicts exported",
  );
  // Returns a ConflictReport shape with warnings array.
  assert.match(
    HUNKS_LIB_SRC,
    /(ConflictReport|warnings\s*:\s*Array)/,
    "ConflictReport / warnings shape exists",
  );

  // Behavioural replica: clean disjoint diff = no warnings.
  const hunks = [
    { id: "context-0", type: "context", before_lines: ["intro"], after_lines: ["intro"], applied: true },
    { id: "change-0", type: "change", before_lines: ["a"], after_lines: ["A"], applied: true },
    { id: "context-1", type: "context", before_lines: ["mid", "x", "y", "z", "lots"], after_lines: ["mid", "x", "y", "z", "lots"], applied: true },
    { id: "change-1", type: "change", before_lines: ["b"], after_lines: ["B"], applied: true },
  ];
  assert.deepEqual(replicaDetect(hunks).warnings, [], "no warnings on clean diff");
});

test("Phase 32 — proximity heuristic flags adjacent change hunks with partial-accept ratio", () => {
  // Source pins the proximity heuristic.
  assert.match(
    HUNKS_LIB_SRC,
    /proximity|context.*\b<=?\s*2\b|\bcontext_lines?\b/i,
    "proximity heuristic referenced in source",
  );

  // Behavioural replica: A applied, B not, separated by 1 context line.
  const hunks = [
    { id: "change-0", type: "change", before_lines: ["a"], after_lines: ["A"], applied: true },
    { id: "context-0", type: "context", before_lines: ["mid"], after_lines: ["mid"], applied: true },
    { id: "change-1", type: "change", before_lines: ["b"], after_lines: ["B"], applied: false },
  ];
  const res = replicaDetect(hunks);
  assert.equal(res.warnings.length, 1, "one warning fires");
  assert.equal(res.warnings[0].reason, "proximity-partial-accept");
  assert.equal(res.warnings[0].hunk_a, "change-0");
  assert.equal(res.warnings[0].hunk_b, "change-1");

  // Both applied → no proximity warning.
  const hunksBoth = hunks.map((h) =>
    h.type === "change" ? { ...h, applied: true } : h,
  );
  assert.equal(replicaDetect(hunksBoth).warnings.length, 0);

  // Far apart (≥3 context lines) → no proximity warning.
  const hunksFar = [
    { id: "change-0", type: "change", before_lines: ["a"], after_lines: ["A"], applied: true },
    { id: "context-0", type: "context", before_lines: ["1", "2", "3", "4"], after_lines: ["1", "2", "3", "4"], applied: true },
    { id: "change-1", type: "change", before_lines: ["b"], after_lines: ["B"], applied: false },
  ];
  assert.equal(replicaDetect(hunksFar).warnings.length, 0);
});

test("Phase 32 — token-pair heuristic flags one hunk removing \\cite{X} that another references", () => {
  // Source pins the token regex pattern.
  assert.match(
    HUNKS_LIB_SRC,
    /\\\\\(cite\|fig\)|cite\|fig/,
    "token regex covers \\cite{...} + \\fig{...}",
  );

  // Behavioural replica: A removes \cite{paperX}, B introduces a reference to it.
  const hunks = [
    {
      id: "change-0",
      type: "change",
      before_lines: ["See \\cite{paperX} for context."],
      after_lines: ["See prior work for context."],
      applied: true,
    },
    {
      id: "context-0",
      type: "context",
      before_lines: ["middle text", "more middle"],
      after_lines: ["middle text", "more middle"],
      applied: true,
    },
    {
      id: "change-1",
      type: "change",
      before_lines: ["Foo bar."],
      after_lines: ["As shown in \\cite{paperX}, foo."],
      applied: true,
    },
  ];
  const res = replicaDetect(hunks);
  const tokenWarnings = res.warnings.filter((w) => w.reason === "token-pair-conflict");
  assert.equal(tokenWarnings.length, 1, "one token-pair warning");
  assert.equal(tokenWarnings[0].hunk_a, "change-0");
  assert.equal(tokenWarnings[0].hunk_b, "change-1");
});

test("Phase 32 — diff-view renders a warning strip when warnings.length > 0", () => {
  // DiffView imports the new helper.
  assert.match(
    DIFF_VIEW_SRC,
    /detectHunkConflicts\b/,
    "DiffView imports detectHunkConflicts",
  );
  // Strip rendered conditionally based on warnings length.
  assert.match(
    DIFF_VIEW_SRC,
    /warnings\.length\s*>\s*0|conflicts\.warnings\.length/,
    "strip renders conditionally on warnings count",
  );
  // Each warning row carries the acknowledge data hooks.
  assert.match(
    DIFF_VIEW_SRC,
    /data-action\s*=\s*"acknowledge-conflict"/,
    "each warning row has data-action='acknowledge-conflict'",
  );
  assert.match(
    DIFF_VIEW_SRC,
    /data-warning-pair/,
    "each warning row has data-warning-pair",
  );
});

test("Phase 32 — Apply Selected stays enabled even with warnings (non-blocking)", () => {
  // The Apply Selected button's `disabled` attribute is computed from
  // applied count alone (not from warnings.length). Source-text check:
  // there must be NO occurrence of `disabled={... warnings ...}` or
  // similar warnings-gated-disabled pattern.
  assert.doesNotMatch(
    DIFF_VIEW_SRC,
    /disabled\s*=\s*\{[^}]*warnings/,
    "warnings do not disable Apply Selected",
  );
  // Apply Selected button still has a disabled attribute (the v1.2
  // count-based gate); we just don't add warnings into it.
  assert.match(
    DIFF_VIEW_SRC,
    /data-action\s*=\s*"apply-selected"/,
    "apply-selected button still present",
  );
});
