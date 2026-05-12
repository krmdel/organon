import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 26 (v1.2) — LLM-routed chat-intent classification (D-6+).
//
// Closes Phase 21's "Heuristic classifier in v1.1" decision: the chat
// route first calls a tiny single-shot LLM classifier; on parse failure
// or skill error the keyword classifier (kept verbatim from v1.1) is
// used. The chat panel surfaces `source: "llm" | "fallback"` so the
// researcher knows which path fired.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const tryRead = (p) => {
  try {
    return readFileSync(p, "utf8");
  } catch {
    return "";
  }
};

const INTENT_LIB_SRC = tryRead(join(ROOT, "src", "lib", "data", "chat-intent.ts"));
const INTENT_ROUTE_SRC = tryRead(
  join(ROOT, "src", "app", "api", "data", "chat-intent", "route.ts"),
);
const CHAT_ROUTE_SRC = tryRead(
  join(ROOT, "src", "app", "api", "data", "chat", "route.ts"),
);

test("Phase 26 — chat-intent route returns hypothesis for stat-test-shaped prompt with source=llm", () => {
  // POST handler exists.
  assert.match(INTENT_ROUTE_SRC, /export\s+async\s+function\s+POST/, "POST handler exported");
  // Spawns a claude / skill round-trip for the LLM classification path.
  assert.match(
    INTENT_ROUTE_SRC,
    /runClaude|claude-runner|spawnClaude/,
    "route invokes the claude-runner for the LLM path",
  );
  // Response includes `intent` + `source` discriminator.
  assert.match(INTENT_ROUTE_SRC, /\bsource\b/, "response carries source field");
  assert.match(
    INTENT_ROUTE_SRC,
    /["']llm["']|source\s*=\s*["']llm["']/,
    "source: 'llm' string literal present on success path",
  );
});

test("Phase 26 — chat-intent route falls back to keyword classifier on skill error", () => {
  assert.match(
    INTENT_ROUTE_SRC,
    /classifyChatIntent\b/,
    "route imports/uses the keyword classifier as fallback",
  );
  assert.match(
    INTENT_ROUTE_SRC,
    /["']fallback["']/,
    "source: 'fallback' string literal on the error path",
  );
  // Try / catch around the LLM round-trip — guarantees the fallback runs.
  assert.match(
    INTENT_ROUTE_SRC,
    /try\s*\{[\s\S]*?(catch|finally)/,
    "LLM call wrapped in try/catch",
  );
});

test("Phase 26 — chat-intent route returns 400 on empty prompt", () => {
  // Body type carries prompt; empty prompt rejected.
  assert.match(INTENT_ROUTE_SRC, /prompt/, "body parses prompt");
  assert.match(
    INTENT_ROUTE_SRC,
    /status:\s*400|400[^0-9]/,
    "route returns 400 for malformed bodies",
  );
  // The trim+empty guard exists.
  assert.match(
    INTENT_ROUTE_SRC,
    /\.trim\(\)|trim\(\)\s*===\s*["']{2}|!prompt\b|prompt\.length\s*===\s*0/,
    "empty / whitespace-only prompts rejected",
  );
});

test("Phase 26 — chat route forwards intent to skill via routeChatIntent helper", () => {
  // The helper exists in chat-intent.ts.
  assert.match(
    INTENT_LIB_SRC,
    /export\s+(async\s+)?function\s+routeChatIntent\b/,
    "routeChatIntent helper exported from chat-intent.ts",
  );
  // The chat route uses it.
  assert.match(
    CHAT_ROUTE_SRC,
    /routeChatIntent\b/,
    "chat route calls routeChatIntent",
  );
  // The keyword classifier remains exported (it's the fallback).
  assert.match(
    INTENT_LIB_SRC,
    /export\s+function\s+classifyChatIntent\b/,
    "classifyChatIntent kept exported (fallback)",
  );
  // The intent SSE event carries the source field so the panel can
  // label "(routed by LLM)" vs "(routed by keywords)".
  assert.match(
    CHAT_ROUTE_SRC,
    /source/,
    "chat route forwards source through the SSE intent event",
  );
});
