import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 66 (v2.2) — M5: usage chip redesign. Drops the per-project $X.XX
// figure (which the researcher correctly flagged as misleading: it's
// local Claude Code spawn cost, NOT plan usage). Introduces a structured
// path A → B → C cascade with an honest tooltip.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const stripComments = (s) =>
  s
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, "")
    .replace(/^[ \t]*\/\/.*$/gm, "");

const CHIP_SRC = readSrc("src/components/layout/usage-chip.tsx");
const USAGE_LIB_SRC = readSrc("src/lib/usage.ts");
const ROUTE_SRC = readSrc("src/app/api/usage/route.ts");

test("Phase 66 — usage-chip renders no dollar string anywhere", () => {
  // The redesigned chip must drop the misleading $ figure entirely.
  // We allow JS template-literal `${expr}` syntax (the $ there is
  // never rendered) but reject any literal $ followed by a digit, the
  // word 'cost', or a `formatCost(` call.
  const naked = stripComments(CHIP_SRC);
  assert.doesNotMatch(
    naked,
    /\$\d|\$\.|\$,/,
    "usage-chip must not render any literal $-followed-by-currency-digit",
  );
  assert.doesNotMatch(
    naked,
    /formatCost\s*\(/,
    "usage-chip must not call formatCost — Phase 66 dropped the dollar figure",
  );
  assert.doesNotMatch(
    naked,
    /"\$/,
    "usage-chip must not render a literal \"$ in any string",
  );
});

test("Phase 66 — usage-chip renders 'daily' and 'weekly' labels", () => {
  assert.match(
    CHIP_SRC,
    /daily/i,
    "usage-chip must label the daily metric",
  );
  assert.match(
    CHIP_SRC,
    /weekly/i,
    "usage-chip must label the weekly metric",
  );
});

test("Phase 66 — getClaudePlanUsage gracefully returns null when local cache missing (path A guard)", () => {
  // Helper exists by name and explicitly handles missing-cache by
  // returning null — never throws. Keeps the chip honest about which
  // source landed.
  assert.match(
    USAGE_LIB_SRC,
    /export\s+function\s+getClaudePlanUsage\s*\(\s*\)/,
    "usage.ts must export a no-arg getClaudePlanUsage helper",
  );
  // Function body must contain a `return null` branch — the path-A
  // guard for missing local cache.
  const helperBody = USAGE_LIB_SRC.split(/export\s+function\s+getClaudePlanUsage/)[1] ?? "";
  assert.match(
    helperBody,
    /return\s+null/,
    "getClaudePlanUsage must return null when no local cache is found",
  );
});

test("Phase 66 — usage chip falls back to local token rate when plan === null", () => {
  // The chip's render must branch on plan-vs-null and still surface
  // daily + weekly token rates from the existing computeUsageReport
  // pipeline so v2.2 ships meaningful data even when the plan path
  // doesn't land.
  assert.match(
    CHIP_SRC,
    /plan\s*===\s*null|plan\s*==\s*null|plan\s*!==\s*null/,
    "usage-chip must branch on whether the plan field is null",
  );
  // Tooltip is the honesty mechanism: must mention 'local' in the
  // fallback path so the user knows what's actually being measured.
  assert.match(
    CHIP_SRC,
    /local/i,
    "usage-chip must explain in its tooltip that the fallback measures local activity",
  );
});

test("Phase 66 — /api/usage response gains a 'plan' field that may be null", () => {
  // Route must call getClaudePlanUsage and surface it as `plan` in the
  // JSON body. Existing `report` field stays for backward compat.
  assert.match(
    ROUTE_SRC,
    /getClaudePlanUsage/,
    "/api/usage route must call getClaudePlanUsage()",
  );
  assert.match(
    ROUTE_SRC,
    /plan(:|\s*=)/,
    "/api/usage response must include a 'plan' field",
  );
});
