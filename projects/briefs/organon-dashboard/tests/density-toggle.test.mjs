import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 65 (v2.2) — M4: dashboard density toggle. CSS --font-scale on
// :root + four data-density variants. Tailwind 4 rem-based classes
// scale automatically. localStorage persisted across reloads via a
// pre-hydration inline script in <head>.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const CSS_SRC = readSrc("src/app/globals.css");
const TOGGLE_SRC = readSrc("src/components/settings/density-toggle.tsx");
const LAYOUT_SRC = readSrc("src/app/layout.tsx");

test("Phase 65 — globals.css declares --font-scale on :root and four data-density variants", () => {
  // Root scale anchors the cascade.
  assert.match(
    CSS_SRC,
    /:root\s*\{[^}]*--font-scale\s*:\s*15px/,
    "globals.css :root must declare --font-scale: 15px (matches today's body size)",
  );
  // Four discrete levels — compact / default / comfortable / large.
  assert.match(
    CSS_SRC,
    /\[data-density=("|')compact("|')\][^{]*\{[^}]*--font-scale/,
    "globals.css must declare --font-scale for [data-density='compact']",
  );
  assert.match(
    CSS_SRC,
    /\[data-density=("|')comfortable("|')\][^{]*\{[^}]*--font-scale/,
    "globals.css must declare --font-scale for [data-density='comfortable']",
  );
  assert.match(
    CSS_SRC,
    /\[data-density=("|')large("|')\][^{]*\{[^}]*--font-scale/,
    "globals.css must declare --font-scale for [data-density='large']",
  );
});

test("Phase 65 — body font-size resolves to var(--font-scale)", () => {
  // Body must derive from the cascade — no fixed px on body.
  assert.match(
    CSS_SRC,
    /body[^{]*\{[\s\S]*?font-size:\s*var\(--font-scale\)/,
    "globals.css must set body font-size to var(--font-scale)",
  );
  // No leftover hard-coded body { font-size: 15px } from before the
  // toggle — would freeze the cascade.
  const bodyMatch = CSS_SRC.match(/html,?\s*body\s*\{[^}]*\}/);
  if (bodyMatch) {
    assert.doesNotMatch(
      bodyMatch[0],
      /font-size:\s*\d+px/,
      "body block must not retain a fixed px font-size",
    );
  }
});

test("Phase 65 — DensityToggle component reads/writes localStorage 'organon.density' and sets <html data-density>", () => {
  // Component file exists.
  assert.match(
    TOGGLE_SRC,
    /export\s+function\s+DensityToggle/,
    "density-toggle.tsx must export DensityToggle",
  );
  // Sentinel for E2E walks.
  assert.match(
    TOGGLE_SRC,
    /data-density-toggle/,
    "DensityToggle must render the data-density-toggle sentinel on its root",
  );
  // localStorage key namespaced under organon.
  assert.match(
    TOGGLE_SRC,
    /organon\.density/,
    "DensityToggle must persist to localStorage key 'organon.density'",
  );
  // Sets the attribute on documentElement.
  assert.match(
    TOGGLE_SRC,
    /document\.documentElement\.setAttribute\(\s*("|')data-density("|')/,
    "DensityToggle must set <html data-density=...> when the user picks a level",
  );
  // Layout wires a pre-hydration script that reads the same key on first
  // paint to avoid the flash-of-default-density.
  assert.match(
    LAYOUT_SRC,
    /organon\.density/,
    "layout.tsx must read 'organon.density' in a pre-hydration inline script",
  );
});
