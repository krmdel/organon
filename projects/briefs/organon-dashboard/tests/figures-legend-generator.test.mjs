import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 19 (v1.1+) — Figure-legend generator (F-5).
//
// The figures workspace gains a "Generate detailed legend" surface on
// LOCKED figures only (an unlocked figure could mutate via a future
// edit, invalidating the legend). The new SSE route at
// /api/data/figures/[fig_id]/legend spawns sci-writing in
// `mode=generate-figure-legend`, persists the multi-paragraph legend
// onto figure.detailed_legend, and the LegendCard surface offers
// Generate / Regenerate / Refine-with-prompt iteration.
//
// Tests follow the source-text-scan pattern used by Phases 9–18: plain
// Node ESM, no TS imports, regex over readFileSync output.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const ROUTE_SRC = readFileSync(
  join(ROOT, "src", "app", "api", "data", "figures", "[fig_id]", "legend", "route.ts"),
  "utf8",
);
const CARD_SRC = readFileSync(
  join(ROOT, "src", "components", "figures", "legend-card.tsx"),
  "utf8",
);
const WORKSPACE_SRC = readFileSync(
  join(ROOT, "src", "components", "figures", "figures-workspace.tsx"),
  "utf8",
);
const SKILL_SRC = readFileSync(
  join(ROOT, "..", "..", "..", ".claude", "skills", "sci-writing", "SKILL.md"),
  "utf8",
);

test("Phase 19 — legend route refuses unlocked figures (409)", () => {
  // Per brief §7.3: "Only locked figures generate legends. A legend
  // bound to an unlocked v1 would invalidate as soon as the user does
  // an edit pass. Refuse with 409."
  assert.match(ROUTE_SRC, /\bfig_id\b/, "route handles fig_id param");
  assert.match(
    ROUTE_SRC,
    /locked/,
    "route checks figure.locked before generating",
  );
  // 409 is the conflict status for "figure must be locked first".
  assert.match(
    ROUTE_SRC,
    /status:\s*409/,
    "unlocked-figure branch returns 409",
  );
  // Spawns sci-writing in generate-figure-legend mode (parent-owned SSE).
  assert.match(
    ROUTE_SRC,
    /mode=generate-figure-legend/,
    "prompt names the new mode",
  );
  // Carries active_project_slug (per pitfall #3 in the v1.1 brief).
  assert.match(
    ROUTE_SRC,
    /active_project_slug=/,
    "prompt embeds active_project_slug",
  );
});

test("Phase 19 — legend-card renders existing detailed_legend + Generate / Regenerate buttons", () => {
  // Reads the legend off the figure artifact.
  assert.match(CARD_SRC, /detailed_legend/, "card reads detailed_legend");
  // Presentational button affordances.
  assert.match(CARD_SRC, /Generate/, "Generate button label");
  assert.match(CARD_SRC, /Regenerate/, "Regenerate button label");
  // Refine-with-prompt is the iterative-edit surface.
  assert.match(
    CARD_SRC,
    /refine|Refine/,
    "Refine-with-prompt affordance",
  );
  // Stable click hooks for future tests.
  assert.match(
    CARD_SRC,
    /data-action=("|')generate-legend\1|data-action=("|')regenerate-legend\2/,
    "data-action hook on the generate / regenerate button",
  );
});

test("Phase 19 — figures-workspace mounts legend-card only when activeFigure.locked", () => {
  // Imports the new component.
  assert.match(
    WORKSPACE_SRC,
    /import\s*\{\s*LegendCard\s*\}\s*from\s*['"]\.\/legend-card['"]/,
    "workspace imports LegendCard",
  );
  // Guarded mount — only renders when the active figure is locked.
  // Accept either a JSX guard `activeFigure.locked && <LegendCard ...>`
  // or a precomputed flag passed as the prop.
  assert.ok(
    /activeFigure\.locked\s*&&\s*<LegendCard/.test(WORKSPACE_SRC) ||
      /isLocked\s*&&\s*<LegendCard/.test(WORKSPACE_SRC),
    "LegendCard mount is gated on the figure being locked",
  );
});

test("Phase 19 — sci-writing SKILL.md Step 7.9 documents generate-figure-legend mode", () => {
  // Step 7.9 heading present.
  assert.match(
    SKILL_SRC,
    /^##\s+Step\s+7\.9:.*generate-figure-legend/m,
    "Step 7.9 heading mentions generate-figure-legend",
  );
  // Step 0 routing table picks up the new mode trigger.
  assert.match(
    SKILL_SRC,
    /dashboard-generate-figure-legend/,
    "Step 0 routing table entry",
  );
  // Documents the trigger keys the dashboard route emits.
  assert.match(
    SKILL_SRC,
    /mode=generate-figure-legend/,
    "trigger key documented",
  );
});
