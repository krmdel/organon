import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 13a (v1.0.1) — persona editor + active toggle.
//
// Scope (NEXT_SESSION_phase13-16.md §8):
//   H-3 — Reset-to-defaults surfaces a confirm before clobbering names /
//         roles / avatars / active flags.
//   H-4 — Persona schema carries `active: boolean` (default true via
//         read-time backfill in normalisePersona). Per-persona checkbox
//         in the editor. Persona-strip header dims + line-throughs
//         inactive personas. Council fanout filters by `active === true`.
//
// Source-text scan pattern (mirrors draft-code-spans / state-persistence)
// so the suite stays portable across `node --test` with no TS build step.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const SHARED_SRC = readSrc("src/lib/hypothesis/shared.ts");
const PERSONAS_LIB_SRC = readSrc("src/lib/hypothesis/personas.ts");
const EDITOR_SRC = readSrc("src/components/hypothesis/personas-editor.tsx");
const WORKSPACE_SRC = readSrc("src/components/hypothesis/hypothesis-workspace.tsx");

test("Phase 13a — Persona type carries optional active flag + isPersonaActive guard", () => {
  // The optional `active?: boolean` field must be on the Persona type
  // export so the editor + workspace can both read it without casting.
  assert.match(SHARED_SRC, /export type Persona = \{[\s\S]+?active\?: boolean;[\s\S]+?\}/);

  // The single-source-of-truth predicate must default to true on
  // missing / undefined / null — anything other than literal `false`.
  // Bare-truthy (`p.active`) would silently drop legacy personas.
  assert.match(
    SHARED_SRC,
    /export function isPersonaActive\(p: Persona\): boolean \{[\s\S]+?return p\.active !== false;[\s\S]+?\}/,
  );

  // Default templates carry `active: true` explicitly so a fresh project
  // never relies on the read-time backfill.
  assert.match(SHARED_SRC, /name: "Skeptic",[\s\S]+?active: true/);
  assert.match(SHARED_SRC, /name: "Methodologist",[\s\S]+?active: true/);
  assert.match(SHARED_SRC, /name: "Domain-expert",[\s\S]+?active: true/);
  assert.match(SHARED_SRC, /name: "Gauss",[\s\S]+?active: true/);
});

test("Phase 13a — listPersonas read-time backfill defaults missing active to true", () => {
  // normalisePersona must fold the active flag into every parsed entry.
  // The conditional `typeof p.active === "boolean"` keeps `false`
  // explicit while defaulting unset / wrong-typed fields to true.
  assert.match(
    PERSONAS_LIB_SRC,
    /active: typeof p\.active === "boolean" \? p\.active : true/,
  );
  // listPersonas pipes JSON entries through normalisePersona — confirm
  // the read path applies the backfill, not just save.
  assert.match(PERSONAS_LIB_SRC, /return parsed\.map\(normalisePersona\)/);
  // savePersonas re-normalises so a round-trip never loses the flag.
  assert.match(PERSONAS_LIB_SRC, /personas\.map\(normalisePersona\)/);
});

test("Phase 13a — personas-editor exposes an active checkbox per row", () => {
  // The checkbox lives on every persona row with a stable data-attribute
  // hook so click-tests can flip it without depending on copy.
  assert.match(EDITOR_SRC, /data-persona-active-toggle/);
  assert.match(EDITOR_SRC, /type="checkbox"/);
  assert.match(EDITOR_SRC, /checked=\{p\.active !== false\}/);
  assert.match(EDITOR_SRC, /onChange=\{\(e\) => update\(i, \{ active: e\.target\.checked \}\)\}/);
  // Each row carries data-active so a future visual regression can
  // assert at the row level instead of digging into the input.
  assert.match(EDITOR_SRC, /data-persona-row/);
  assert.match(EDITOR_SRC, /data-active=\{p\.active !== false \? "true" : "false"\}/);
  // Add-persona button defaults active to true so a freshly added
  // persona fires on the next council fanout without an extra click.
  assert.match(EDITOR_SRC, /\{ name: `Persona \$\{cur\.length \+ 1\}`, role: "", active: true \}/);
});

test("Phase 13a — Reset-to-defaults surfaces a confirm before clobbering active flags", () => {
  // confirmAndReset wraps both Defaults + Math-template buttons; an
  // accidental click does NOT silently overwrite the user's setup.
  assert.match(
    EDITOR_SRC,
    /const confirmAndReset = \(next: Persona\[\]\) => \{[\s\S]+?window\.confirm\(/,
  );
  assert.match(EDITOR_SRC, /onClick=\{\(\) => confirmAndReset\(getDefaultPersonas\(\)\)\}/);
  assert.match(EDITOR_SRC, /onClick=\{\(\) => confirmAndReset\(getMathTemplatePersonas\(\)\)\}/);
  // data-action hooks pin the buttons so a future click-test can drive
  // them without depending on copy.
  assert.match(EDITOR_SRC, /data-action="reset-defaults"/);
  assert.match(EDITOR_SRC, /data-action="reset-math-template"/);
});

test("Phase 13a — workspace strip dims + line-throughs inactive personas", () => {
  // The chip render branches on isPersonaActive — inactive picks up the
  // opacity-50 + line-through pair so the user sees at a glance which
  // personas the next council run will fire.
  assert.match(WORKSPACE_SRC, /import \{ isPersonaActive \} from "@\/lib\/hypothesis\/shared"/);
  assert.match(WORKSPACE_SRC, /const active = isPersonaActive\(p\);/);
  assert.match(WORKSPACE_SRC, /data-persona-chip/);
  assert.match(WORKSPACE_SRC, /data-persona-active=\{active \? "true" : "false"\}/);
  assert.match(WORKSPACE_SRC, /opacity-50 line-through/);
});

test("Phase 13a — council fanout filters to active personas only", () => {
  // The active-persona filter MUST run before the prompt is composed —
  // an inactive persona never enters the prompt's `personas=` list.
  assert.match(
    WORKSPACE_SRC,
    /const activePersonas = personas\.filter\(isPersonaActive\)/,
  );
  // The prompt's persona list and the count both come from the
  // filtered set.
  assert.match(WORKSPACE_SRC, /const personasList = activePersonas\.map\(\(p\) => p\.name\)\.join\(", "\)/);
  assert.match(WORKSPACE_SRC, /fan out \$\{activePersonas\.length\} personas on this hypothesis/);
});

test("Phase 13a — hydration badge `expected` reflects active count, not full personas length", () => {
  // The badge denominator switched from personas.length to the active
  // count so it does NOT pin at "2/3" when one persona is deactivated.
  assert.match(
    WORKSPACE_SRC,
    /const activePersonaCount = useMemo\([\s\S]+?personas\.filter\(isPersonaActive\)\.length,[\s\S]+?\[personas\],[\s\S]+?\)/,
  );
  assert.match(WORKSPACE_SRC, /expected: activePersonaCount/);
});
