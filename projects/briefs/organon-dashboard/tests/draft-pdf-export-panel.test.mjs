import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 17 (v1.1+) — Pandoc PDF export preflight panel (B3).
//
// The existing 503 "Pandoc not installed" path becomes an inline preflight
// panel: clicking PDF fires a dryrun=1 probe against the export route
// (which only runs `pandoc --version`, no manuscript assembly). The route
// returns { available, version?, install_hint, error? } and the menu
// surfaces install instructions per platform with a "Run anyway"
// affordance for when the user wants to try the export anyway, and a
// "Switch to Markdown" affordance so the user can opt out cleanly.
//
// Tests follow the source-text-scan pattern used by Phases 9–16: plain
// Node ESM, no TS imports, regex over readFileSync output.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const ROUTE_SRC = readFileSync(
  join(ROOT, "src", "app", "api", "draft", "[slug]", "export", "route.ts"),
  "utf8",
);
const MENU_SRC = readFileSync(
  join(ROOT, "src", "components", "draft", "export-menu.tsx"),
  "utf8",
);

test("Phase 17 — export route handles dryrun=1 with pandoc version probe", () => {
  // The dryrun branch is single-route — no new route per the brief's
  // §5.3 decision ("Dryrun is a single shared route, not a new route").
  assert.match(
    ROUTE_SRC,
    /searchParams\.get\("dryrun"\)\s*===\s*"1"/,
    "route must branch on ?dryrun=1",
  );
  // The branch must be gated on format === "pdf" so other formats keep
  // their existing behaviour. The regex requires the dryrun check to
  // appear within 300 chars of a `format === "pdf"` test (after body
  // parse, before the manuscript fetch).
  assert.match(
    ROUTE_SRC,
    /format === "pdf"[\s\S]{0,300}?searchParams\.get\("dryrun"\)/,
    "dryrun is only meaningful when format === pdf",
  );
  // Probe shells pandoc with --version.
  assert.match(
    ROUTE_SRC,
    /spawn\("pandoc",\s*\[\s*"--version"/,
    "version probe spawns pandoc --version",
  );
  // Response shape carries available + install_hint at minimum (and
  // version when available).
  assert.match(ROUTE_SRC, /\bavailable\b/);
  assert.match(ROUTE_SRC, /\binstall_hint\b/);
});

test("Phase 17 — export route emits per-platform install_hint when pandoc unavailable", () => {
  // Per brief §5.3: install hints are per-platform, NOT generic.
  // Detect via process.platform: darwin / linux / win32 + fallback.
  assert.match(ROUTE_SRC, /process\.platform/);
  assert.match(ROUTE_SRC, /brew install pandoc/, "macOS hint must mention brew");
  assert.match(ROUTE_SRC, /apt-get install pandoc/, "linux hint must mention apt-get");
  assert.match(ROUTE_SRC, /choco install pandoc/, "windows hint must mention choco");
});

test("Phase 17 — export-menu surfaces preflight panel state machine", () => {
  // The menu tracks the preflight state with discriminated branches.
  assert.match(MENU_SRC, /pdfPreflight/, "tracks pdfPreflight state");
  assert.match(MENU_SRC, /checking/, "checking branch");
  assert.match(MENU_SRC, /available/, "available branch");
  assert.match(MENU_SRC, /unavailable/, "unavailable branch");
  // Preflight fires via a callback prop so the workspace owns the fetch
  // (parent-owned-fetch pattern from Phase 10).
  assert.match(MENU_SRC, /onPdfPreflight/, "callback prop for the preflight fetch");
  // Surfaces install hint to the user when unavailable.
  assert.match(MENU_SRC, /install_hint/, "menu reads install_hint on unavailable");
});

test("Phase 17 — export-menu offers 'run anyway' when unavailable but user insists", () => {
  // Per brief §5.3: do NOT silently fall through to markdown — surface
  // the failure inline AND offer 'run anyway'.
  assert.match(MENU_SRC, /run anyway/i, "run anyway affordance");
  // And a 'switch to markdown' affordance so the user can opt out
  // cleanly. The literal label is required so a click-test can pin it.
  assert.match(MENU_SRC, /switch to markdown/i, "switch-to-markdown affordance");
});
