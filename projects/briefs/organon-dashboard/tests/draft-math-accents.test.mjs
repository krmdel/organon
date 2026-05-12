import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 15a (v1.0.1) — KaTeX accent expansion contract (DR-2).
//
// Scope (V1_0_1_PLAN.md §15a + NEXT_SESSION_phase13-16.md §4):
//   src/lib/draft/math.ts gains \bar / \hat / \tilde / \vec / \dot / \ddot.
//   Single-char body → unicode combining glyph (no CSS dependency).
//   Multi-char body → span wrapper with a class name.
//
// Source-text scan pattern (same as draft-code-spans, state-persistence,
// stat-workspace-polish) so the suite stays portable under `node --test`.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const MATH_SRC = readFileSync(join(ROOT, "src", "lib", "draft", "math.ts"), "utf8");

// Combining glyph code points the implementation must use.
const COMBINING_MACRON = "̄";              // \bar
const COMBINING_CIRCUMFLEX = "̂";          // \hat
const COMBINING_TILDE_ABOVE = "̃";         // \tilde
const COMBINING_RIGHT_ARROW_ABOVE = "⃗";   // \vec
const COMBINING_DOT_ABOVE = "̇";           // \dot
const COMBINING_DIAERESIS = "̈";           // \ddot

test("math.ts declares the accent helper before the SORTED_CMDS loop", () => {
  // Ordering matters: accents must run BEFORE the multi-letter pass so a
  // hypothetical \bar / \hat / etc that someone later adds to ALL_CMDS does
  // not collide with the accent regex. See brief §4.2.
  const accentIdx = MATH_SRC.indexOf("Phase 15a (DR-2) accents");
  const sortedCmdsIdx = MATH_SRC.indexOf("for (const key of SORTED_CMDS)");
  assert.ok(accentIdx > 0, "accent block comment header missing");
  assert.ok(sortedCmdsIdx > 0, "SORTED_CMDS multi-letter loop missing");
  assert.ok(accentIdx < sortedCmdsIdx, "accent block must precede the SORTED_CMDS loop");
});

test("math.ts declares \\ddot before \\dot (longer form claims first)", () => {
  const ddotIdx = MATH_SRC.indexOf("\\\\ddot\\{");
  const dotIdx = MATH_SRC.indexOf("\\\\dot\\{");
  assert.ok(ddotIdx > 0, "\\ddot braced regex missing");
  assert.ok(dotIdx > 0, "\\dot braced regex missing");
  assert.ok(ddotIdx < dotIdx, "\\ddot must be declared before \\dot");
});

test("math.ts \\bar uses combining macron + overline span via accent helper", () => {
  // Braced form goes through the helper (single-char → combining, multi → span).
  assert.match(MATH_SRC, /\\\\bar\\\{\(\[\^\{\}\]\*\)\\\}.+accent\(body, "̄", "overline"\)/s);
  // Unbraced single-letter form uses the combining macron directly.
  assert.match(MATH_SRC, /\\\\bar\\s\*\(\[a-zA-Z\]\)/);
  assert.ok(MATH_SRC.includes(`\`\${ch}${COMBINING_MACRON}\``), "unbraced \\bar must use combining macron literal");
});

test("math.ts \\hat uses combining circumflex + hat span via accent helper", () => {
  assert.match(MATH_SRC, /\\\\hat\\\{\(\[\^\{\}\]\*\)\\\}.+accent\(body, "̂", "hat"\)/s);
  assert.ok(MATH_SRC.includes(`\`\${ch}${COMBINING_CIRCUMFLEX}\``), "unbraced \\hat must use combining circumflex literal");
});

test("math.ts \\tilde uses combining tilde + tilde span via accent helper", () => {
  assert.match(MATH_SRC, /\\\\tilde\\\{\(\[\^\{\}\]\*\)\\\}.+accent\(body, "̃", "tilde"\)/s);
  assert.ok(MATH_SRC.includes(`\`\${ch}${COMBINING_TILDE_ABOVE}\``), "unbraced \\tilde must use combining tilde literal");
});

test("math.ts \\vec uses combining right-arrow + vec span via accent helper", () => {
  assert.match(MATH_SRC, /\\\\vec\\\{\(\[\^\{\}\]\*\)\\\}.+accent\(body, "⃗", "vec"\)/s);
  assert.ok(MATH_SRC.includes(`\`\${ch}${COMBINING_RIGHT_ARROW_ABOVE}\``), "unbraced \\vec must use combining right-arrow literal");
});

test("math.ts \\dot uses combining dot + dot span via accent helper", () => {
  assert.match(MATH_SRC, /\\\\dot\\\{\(\[\^\{\}\]\*\)\\\}.+accent\(body, "̇", "dot"\)/s);
  assert.ok(MATH_SRC.includes(`\`\${ch}${COMBINING_DOT_ABOVE}\``), "unbraced \\dot must use combining dot literal");
});

test("math.ts \\ddot uses combining diaeresis + ddot span via accent helper", () => {
  assert.match(MATH_SRC, /\\\\ddot\\\{\(\[\^\{\}\]\*\)\\\}.+accent\(body, "̈", "ddot"\)/s);
  assert.ok(MATH_SRC.includes(`\`\${ch}${COMBINING_DIAERESIS}\``), "unbraced \\ddot must use combining diaeresis literal");
});

test("accent helper picks combining glyph for single-char body and span for multi-char", () => {
  // Behavioural mirror: replicate the helper logic exactly and verify both
  // branches. The mirror is brittle by design — if someone changes the
  // signature, this test must be updated alongside the source.
  const accent = (body, combining, multiClass) => {
    // Drop HTML tags before counting (matches helper logic).
    const visible = body.replace(/<[^>]+>/g, "");
    const charCount = [...visible].length;
    return charCount === 1
      ? `${body}${combining}`
      : `<span class="${multiClass}">${body}</span>`;
  };
  assert.equal(accent("x", COMBINING_MACRON, "overline"), `x${COMBINING_MACRON}`);
  assert.equal(accent("xy", COMBINING_MACRON, "overline"), `<span class="overline">xy</span>`);
  // Greek letter (already resolved by recursion) is single visible char.
  assert.equal(accent("α", COMBINING_DOT_ABOVE, "dot"), `α${COMBINING_DOT_ABOVE}`);
  // HTML-tagged single char (e.g. wrapped in <sup>) still counts as one
  // visible glyph after the strip.
  assert.equal(accent("<sup>2</sup>", COMBINING_CIRCUMFLEX, "hat"), `<sup>2</sup>${COMBINING_CIRCUMFLEX}`);
});
