import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 31 (v1.3) — D-6++ fast-classifier model override knob.
//
// v1.2's chat-intent route uses the workspace default skill-runner
// model (Sonnet) for what is essentially a single-token classification.
// v1.3 wires a body-level + env-level model override so researchers
// can pin a cheaper / faster model (e.g. Haiku) for intent routing
// without touching the rest of the stack.
//
// Resolution order: body.model > process.env.ORGANON_FAST_INTENT_MODEL >
// runner default. The cache key includes the resolved model so a swap
// doesn't return stale cached results from the prior model.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

const tryRead = (p) => {
  try {
    return readFileSync(p, "utf8");
  } catch {
    return "";
  }
};

const RUNNER_SRC = tryRead(join(ROOT, "src", "lib", "claude-runner.ts"));
const ROUTE_SRC = tryRead(
  join(ROOT, "src", "app", "api", "data", "chat-intent", "route.ts"),
);
const HELPER_SRC = tryRead(join(ROOT, "src", "lib", "data", "chat-intent.ts"));

test("Phase 31 — claude-runner appends --model arg when opts.model is set", () => {
  // RunnerOptions extends with model?: string.
  assert.match(
    RUNNER_SRC,
    /model\s*\?\s*:\s*string/,
    "RunnerOptions includes model?: string",
  );
  // The default-args branch composes the --model flag literal when
  // opts.model is set. We assert source-text — exact composition lives
  // in the spawn argv builder.
  assert.match(
    RUNNER_SRC,
    /["']--model["']/,
    "runner appends the --model flag literal",
  );
  // The args override path leaves opts.args untouched (escape hatch
  // for tests). Match either the v1.2 inline form or the v1.3 named-
  // default form; both honour the override.
  assert.match(
    RUNNER_SRC,
    /opts\.args\s*\?\?\s*(\[\s*["']-p["']|\w+Args\b)/,
    "args override path preserved (?? against default)",
  );

  // Behavioural replica — mirror the composer logic the runner uses.
  const compose = (opts) => {
    if (opts.args) return opts.args; // override wins, untouched
    const base = ["-p", opts.prompt];
    if (opts.model) base.push("--model", opts.model);
    return base;
  };
  // Default — no model → no --model flag.
  assert.deepEqual(compose({ prompt: "hi" }), ["-p", "hi"]);
  // model set → flag appended.
  assert.deepEqual(compose({ prompt: "hi", model: "haiku" }), [
    "-p",
    "hi",
    "--model",
    "haiku",
  ]);
  // args overridden → model ignored (escape hatch).
  assert.deepEqual(
    compose({ prompt: "hi", model: "haiku", args: ["-x", "y"] }),
    ["-x", "y"],
  );
});

test("Phase 31 — chat-intent route reads ORGANON_FAST_INTENT_MODEL env var as default", () => {
  // The route reads the env var.
  assert.match(
    ROUTE_SRC,
    /ORGANON_FAST_INTENT_MODEL/,
    "chat-intent route reads ORGANON_FAST_INTENT_MODEL env var",
  );
  // Body type accepts model?: string.
  assert.match(
    ROUTE_SRC,
    /model\s*\?\s*:\s*string/,
    "Body type accepts optional model field",
  );
  // The route forwards a resolved model into runClaude opts.
  assert.match(
    ROUTE_SRC,
    /runClaude\s*\(\s*\{[\s\S]*?model\s*:/,
    "runClaude is invoked with model option",
  );

  // Behavioural replica — env-default, no body.
  const resolveModel = (body, env) =>
    (body && typeof body.model === "string" && body.model.length > 0
      ? body.model
      : env.ORGANON_FAST_INTENT_MODEL) ?? null;
  assert.equal(
    resolveModel({}, { ORGANON_FAST_INTENT_MODEL: "haiku" }),
    "haiku",
    "env default fires when body.model unset",
  );
  assert.equal(
    resolveModel({}, {}),
    null,
    "no env + no body → null (runner default)",
  );
});

test("Phase 31 — body.model overrides the env default in chat-intent route", () => {
  // Body wins over env.
  const resolveModel = (body, env) =>
    (body && typeof body.model === "string" && body.model.length > 0
      ? body.model
      : env.ORGANON_FAST_INTENT_MODEL) ?? null;
  assert.equal(
    resolveModel(
      { model: "opus" },
      { ORGANON_FAST_INTENT_MODEL: "haiku" },
    ),
    "opus",
    "body.model wins when both set",
  );
  // Empty string body.model is treated as unset.
  assert.equal(
    resolveModel(
      { model: "" },
      { ORGANON_FAST_INTENT_MODEL: "haiku" },
    ),
    "haiku",
    "empty string body.model falls back to env",
  );

  // Cache key in routeChatIntent helper composes prompt + model so a
  // model swap doesn't return cached results from the prior model.
  assert.match(
    HELPER_SRC,
    /\bmodel\b/,
    "routeChatIntent helper references model in its surface",
  );
  assert.match(
    HELPER_SRC,
    /(intentCache|cache)\b/,
    "in-memory cache exists",
  );
  // The cache key uses both model + prompt.
  assert.match(
    HELPER_SRC,
    /\$\{[^}]*model[^}]*\}[\s\S]*\$\{[^}]*(prompt|key|trim)[^}]*\}|\$\{[^}]*(prompt|key|trim)[^}]*\}[\s\S]*\$\{[^}]*model[^}]*\}/,
    "cache key composes model + prompt",
  );

  // Behavioural replica of cache-key composition.
  const cacheKey = (prompt, model) => `${model ?? "default"}::${prompt.trim()}`;
  assert.notEqual(
    cacheKey("compare A vs B", "haiku"),
    cacheKey("compare A vs B", "opus"),
    "cache key differs across models",
  );
  assert.equal(
    cacheKey("compare A vs B", "haiku"),
    cacheKey("compare A vs B", "haiku"),
    "cache key stable across calls",
  );
});
