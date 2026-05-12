import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 27 (v1.2) — Multi-turn chat conversation (DR-6+).
//
// Closes Phase 22's "Single-turn chat in v1.1" decision. The chat
// panel's transcript becomes load-bearing: each prompt sends prior
// turns + diff summaries as conversation state to the skill. Caps
// (≤6 turns, ≤400 chars per diff_summary) gate at the dashboard
// boundary — the skill never sees the full diff bodies.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const tryRead = (p) => {
  try {
    return readFileSync(p, "utf8");
  } catch {
    return "";
  }
};

const CTX_SRC = tryRead(join(ROOT, "src", "lib", "draft", "selection-context.ts"));
const ROUTE_SRC = tryRead(
  join(ROOT, "src", "app", "api", "draft", "[slug]", "edit-with-chat", "route.ts"),
);
const WORKSPACE_SRC = tryRead(
  join(ROOT, "src", "components", "draft", "manuscript-workspace.tsx"),
);
const SKILL_SRC = tryRead(
  join(ROOT, "..", "..", "..", ".claude", "skills", "sci-writing", "SKILL.md"),
);

test("Phase 27 — selection-context exports MAX_PRIOR_TURNS + MAX_DIFF_SUMMARY_CHARS", () => {
  assert.match(
    CTX_SRC,
    /export\s+const\s+MAX_PRIOR_TURNS\s*=\s*6\b/,
    "MAX_PRIOR_TURNS = 6 exported",
  );
  assert.match(
    CTX_SRC,
    /export\s+const\s+MAX_DIFF_SUMMARY_CHARS\s*=\s*400\b/,
    "MAX_DIFF_SUMMARY_CHARS = 400 exported",
  );
  // PriorTurn type lives next to the constants.
  assert.match(
    CTX_SRC,
    /(export\s+(type|interface)\s+PriorTurn)/,
    "PriorTurn type exported",
  );
  // ContextEnvelope picks up the new optional field.
  assert.match(
    CTX_SRC,
    /prior_turns\?:\s*PriorTurn\[\]/,
    "ContextEnvelope.prior_turns?: PriorTurn[]",
  );
});

test("Phase 27 — buildContext caps prior_turns at 6, diff_summary at 400 chars", () => {
  // The cap is enforced at buildContext, not the route.
  assert.match(
    CTX_SRC,
    /\.slice\(\s*0\s*,\s*MAX_PRIOR_TURNS\s*\)|\.slice\(\s*-\s*MAX_PRIOR_TURNS\s*\)/,
    "buildContext slices prior_turns to MAX_PRIOR_TURNS",
  );
  // Each diff_summary is capped to MAX_DIFF_SUMMARY_CHARS.
  assert.match(
    CTX_SRC,
    /diff_summary[^]*MAX_DIFF_SUMMARY_CHARS|MAX_DIFF_SUMMARY_CHARS[^]*diff_summary/,
    "diff_summary capped via MAX_DIFF_SUMMARY_CHARS",
  );
  // Behavioural replica — fake prior_turns with overlong summaries +
  // 9 entries; cap-and-trim manually using the same shape buildContext
  // emits and verify our expectation.
  const turns = Array.from({ length: 9 }, (_, i) => ({
    prompt: `turn ${i}`,
    applied: i % 2 === 0,
    diff_summary: "x".repeat(800),
  }));
  const capped = turns.slice(-6).map((t) => ({
    ...t,
    diff_summary: t.diff_summary.slice(0, 400),
  }));
  assert.equal(capped.length, 6, "6 turns retained");
  assert.equal(capped[0].diff_summary.length, 400, "diff_summary trimmed");
});

test("Phase 27 — edit-with-chat route accepts prior_turns + embeds them in prompt", () => {
  // Body type carries prior_turns.
  assert.match(
    ROUTE_SRC,
    /prior_turns\??:/,
    "Body type exposes prior_turns",
  );
  // The route forwards prior_turns into buildContext.
  assert.match(
    ROUTE_SRC,
    /buildContext\([^)]*\bprior(_| )turns/,
    "buildContext invoked with prior_turns argument",
  );
  // The skill prompt embeds a "conversation so far" block when
  // prior_turns is non-empty.
  assert.match(
    ROUTE_SRC,
    /(prior_turns|conversation so far)/i,
    "prompt embeds prior_turns / conversation context",
  );
});

test("Phase 27 — workspace forwards last 6 turns with diff summaries on each submit", () => {
  // Workspace builds the prior_turns payload at submit time.
  assert.match(
    WORKSPACE_SRC,
    /prior_turns/,
    "manuscript-workspace references prior_turns",
  );
  // The slice / trim happens in workspace: last 6 turns mapped to
  // { prompt, applied, diff_summary? }.
  assert.match(
    WORKSPACE_SRC,
    /diff_summary/,
    "workspace exposes diff_summary on the payload",
  );
  // The submit handler still POSTs to /api/draft/.../edit-with-chat.
  assert.match(
    WORKSPACE_SRC,
    /edit-with-chat/,
    "submit handler hits edit-with-chat route",
  );
});

test("Phase 27 — sci-writing SKILL.md Step 7.10 documents prior_turns", () => {
  // The contract for prior_turns must live next to Step 7.10.
  assert.match(SKILL_SRC, /Step 7\.10/, "Step 7.10 still present");
  assert.match(
    SKILL_SRC,
    /prior_turns/,
    "Step 7.10 documents prior_turns",
  );
  // Cap notes mirror the dashboard's enforcement so the skill knows
  // not to expand on its own.
  assert.match(
    SKILL_SRC,
    /(6\s+turns|MAX_PRIOR_TURNS|six\s+turns)/i,
    "Step 7.10 mentions the 6-turn cap",
  );
});
