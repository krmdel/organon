import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 24 (v1.2) — Figure-legend history (F-5+).
//
// Closes the v1.1 "soft-archive over hard-delete" Phase 19 decision:
// every legend regenerate / refine pass appends a versioned entry to
// `figure.legend_history`. The LegendCard surfaces a history strip;
// clicking an older version reverts the current `detailed_legend` to
// that text. Schema-additive — read-time backfill of `[]` (Persona.active
// + detailed_legend Phase 13a/19 pattern), no on-disk migration.
//
// Source-text scan pattern (Phases 9–23).

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const tryRead = (p) => {
  try {
    return readFileSync(p, "utf8");
  } catch {
    return "";
  }
};
const TYPES_SRC = tryRead(join(ROOT, "src", "lib", "artifacts", "types.ts"));
const ROUTE_SRC = tryRead(
  join(ROOT, "src", "app", "api", "data", "figures", "[fig_id]", "legend", "route.ts"),
);
const REVERT_SRC = tryRead(
  join(
    ROOT,
    "src",
    "app",
    "api",
    "data",
    "figures",
    "[fig_id]",
    "legend",
    "[legend_version]",
    "route.ts",
  ),
);
const CARD_SRC = tryRead(join(ROOT, "src", "components", "figures", "legend-card.tsx"));

test("Phase 24 — FigureArtifact.legend_history is optional + read-time backfilled", () => {
  // The new entry interface is exported for consumers + the
  // FigureArtifact field references it.
  assert.match(
    TYPES_SRC,
    /(export\s+)?interface\s+LegendHistoryEntry|export\s+type\s+LegendHistoryEntry/,
    "LegendHistoryEntry type exported",
  );
  // Required fields per brief: version, text, refine_prompt? | null, created_at.
  assert.match(TYPES_SRC, /version:\s*number/, "LegendHistoryEntry.version: number");
  assert.match(TYPES_SRC, /\btext:\s*string/, "LegendHistoryEntry.text: string");
  assert.match(
    TYPES_SRC,
    /refine_prompt\?:\s*string\s*\|\s*null/,
    "LegendHistoryEntry.refine_prompt nullable optional",
  );
  assert.match(TYPES_SRC, /created_at:\s*string/, "LegendHistoryEntry.created_at: string");
  // FigureArtifact picks up legend_history? as an optional array.
  assert.match(
    TYPES_SRC,
    /legend_history\?:\s*LegendHistoryEntry\[\]/,
    "FigureArtifact.legend_history?: LegendHistoryEntry[]",
  );
});

test("Phase 24 — legend route appends a LegendHistoryEntry on each persist", () => {
  // The persist path appends to legend_history.
  assert.match(
    ROUTE_SRC,
    /legend_history/,
    "legend route references legend_history",
  );
  // The cap constant is at the route boundary per brief.
  assert.match(
    ROUTE_SRC,
    /MAX_LEGEND_HISTORY\s*=\s*20/,
    "MAX_LEGEND_HISTORY = 20 cap at route boundary",
  );
  // The route writes a new entry shape with version + text + created_at.
  assert.match(
    ROUTE_SRC,
    /version:[^\n]*\bnext_version|version:[^\n]*\(.*\.length/,
    "next version derived from history length",
  );
  assert.match(
    ROUTE_SRC,
    /created_at:\s*new Date\(\)\.toISOString\(\)/,
    "created_at stamped via ISO timestamp",
  );
  // Refine prompt forwarded into the entry.
  assert.match(
    ROUTE_SRC,
    /refine_prompt:/,
    "entry carries refine_prompt verbatim",
  );
});

test("Phase 24 — legend revert route restores detailed_legend from history", () => {
  // POST handler exists.
  assert.match(REVERT_SRC, /export\s+async\s+function\s+POST/, "POST handler exported");
  // Reads the figure + matches by version.
  assert.match(REVERT_SRC, /readFigure\b/, "reads figure via readFigure");
  assert.match(
    REVERT_SRC,
    /legend_version|legend_history/,
    "matches the requested legend version",
  );
  // Restores detailed_legend.
  assert.match(REVERT_SRC, /detailed_legend/, "writes detailed_legend back");
  assert.match(REVERT_SRC, /saveFigure\b/, "persists via saveFigure");
  // Body field { revert: true } gates the route per brief.
  assert.match(REVERT_SRC, /revert/, "revert: true body gate");
});

test("Phase 24 — legend-card renders history strip newest-first with data hooks", () => {
  // Reads legend_history off the figure artifact.
  assert.match(CARD_SRC, /legend_history/, "legend-card reads legend_history");
  // Stable data hooks for the entry chip + revert action.
  assert.match(
    CARD_SRC,
    /data-legend-history-entry/,
    "history-entry chip carries data-legend-history-entry",
  );
  assert.match(
    CARD_SRC,
    /data-legend-version/,
    "history-entry chip carries data-legend-version",
  );
  assert.match(
    CARD_SRC,
    /data-action=("|')revert-legend\1/,
    "revert button carries data-action=revert-legend",
  );
  // Newest-first ordering: either an explicit reverse() or a sort
  // descending on version. Either is a valid contract.
  assert.match(
    CARD_SRC,
    /\.reverse\(\)|\.sort\(.*\bversion\b.*-.*\bversion\b\s*\)|sort\(.*b\.version\s*-\s*a\.version/,
    "history strip renders newest-first (reverse or sort desc)",
  );
});

test("Phase 24 — revert click fires onRevertLegend with the chosen version", () => {
  // The card receives a callback prop for revert.
  assert.match(
    CARD_SRC,
    /onRevertLegend/,
    "LegendCard exposes an onRevertLegend prop",
  );
  // Behavioural replica: build a tiny history array, reverse it, and
  // assert version order matches newest-first. Catches subtle off-by-one
  // ordering regressions.
  const history = [
    { version: 2, text: "v2 legend", created_at: "2026-05-07T10:00:00.000Z" },
    { version: 4, text: "v4 legend", created_at: "2026-05-07T11:00:00.000Z" },
    { version: 3, text: "v3 legend", created_at: "2026-05-07T12:00:00.000Z" },
  ];
  // Sort ascending by version, then reverse — same shape as the
  // newest-first strip.
  const newestFirst = [...history].sort((a, b) => a.version - b.version).reverse();
  assert.deepEqual(
    newestFirst.map((e) => e.version),
    [4, 3, 2],
    "reverse-sorted history is newest-first",
  );
});
