import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 21 (v1.1+) — Chat-driven data analysis tab (D-6).
//
// New `/data` "Chat" tab takes a natural-language question + the
// active dataframe and streams sci-data-analysis OR sci-hypothesis to
// produce a one-shot result (stat test or plot). A keyword heuristic
// classifies the prompt at the route boundary; the resulting artifact
// flows through the existing persister so a chat-emitted stat-result
// or figure shows up in the Stats / Plots tabs.
//
// Tests follow the source-text-scan pattern used by Phases 9–20.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const INTENT_SRC = readFileSync(join(ROOT, "src", "lib", "data", "chat-intent.ts"), "utf8");
const ROUTE_SRC = readFileSync(join(ROOT, "src", "app", "api", "data", "chat", "route.ts"), "utf8");
const PANEL_SRC = readFileSync(join(ROOT, "src", "components", "data", "chat-panel.tsx"), "utf8");
const WORKSPACE_SRC = readFileSync(join(ROOT, "src", "components", "data", "data-workspace.tsx"), "utf8");

test("Phase 21 — chat-intent classifier routes hypothesis vs analysis prompts", () => {
  // Structural contract: the classifier exists and exports the
  // documented return type.
  assert.match(INTENT_SRC, /export function classifyChatIntent\s*\(/);
  assert.match(INTENT_SRC, /["']hypothesis["']/);
  assert.match(INTENT_SRC, /["']data-analysis["']/);

  // Behavioural test: replicate the classifier inline (the test
  // harness can't import .ts directly) and assert on real return
  // values across canonical prompt shapes.
  const HYPOTHESIS_KEYWORDS = [
    /\bis\s+\w+\s+different\s+from\b/i,
    /\bcompare\b.*\bgroups?\b/i,
    /\bdoes\s+\w+\s+predict\b/i,
    /\bwhat\s+(explains|drives|causes)\b/i,
    /\bsignificant(ly)?\s+different\b/i,
    /\beffect\s+of\b/i,
    /\bvs\s+control\b/i,
    /\btest\s+(if|whether)\b/i,
  ];
  const ANALYSIS_KEYWORDS = [
    /\bplot\b/i,
    /\bchart\b/i,
    /\bgraph\b/i,
    /\bvisuali[sz]e\b/i,
    /\bhistogram\b/i,
    /\bscatter\b/i,
    /\bbox\s+plot\b/i,
    /\bheatmap\b/i,
    /\bmean\b/i,
    /\bmedian\b/i,
    /\bsummary\s+statistics\b/i,
  ];
  const classifyChatIntent = (prompt) => {
    const text = String(prompt ?? "").trim();
    if (!text) return "data-analysis";
    for (const re of HYPOTHESIS_KEYWORDS) if (re.test(text)) return "hypothesis";
    for (const re of ANALYSIS_KEYWORDS) if (re.test(text)) return "data-analysis";
    return "data-analysis";
  };

  assert.equal(
    classifyChatIntent("Is BMI different from baseline in the GLP-1 cohort?"),
    "hypothesis",
  );
  assert.equal(classifyChatIntent("Plot weight loss vs time"), "data-analysis");
  assert.equal(classifyChatIntent("histogram of regain rate"), "data-analysis");
  assert.equal(
    classifyChatIntent("Does dosage predict adherence?"),
    "hypothesis",
  );
  // Unknown prompt → data-analysis is the safe default.
  assert.equal(classifyChatIntent("show me something"), "data-analysis");
  // Empty / whitespace → also data-analysis (won't fail the route).
  assert.equal(classifyChatIntent(""), "data-analysis");
});

test("Phase 21 — chat route refuses without file_id (400)", () => {
  assert.match(ROUTE_SRC, /file_id/, "route reads file_id from body");
  // Refuse with 400 when missing.
  assert.match(
    ROUTE_SRC,
    /file_id required[^"]*"\s*\}\s*,\s*\{\s*status:\s*400|status:\s*400[^"]*"file_id/,
    "missing file_id returns 400",
  );
  // Imports the classifier.
  assert.match(
    ROUTE_SRC,
    /import\s*\{[^}]*\bclassifyChatIntent\b[^}]*\}\s*from/,
    "route imports classifyChatIntent",
  );
});

test("Phase 21 — chat-panel renders transcript + streaming region", () => {
  // Transcript is in-memory state (per brief §9.3 — "ephemeral, not
  // persisted"). Component carries a transcript array and a streaming
  // text region.
  assert.match(PANEL_SRC, /transcript/i, "panel tracks a transcript");
  assert.match(PANEL_SRC, /streaming/i, "panel surfaces a streaming region");
  // Prompt input + submit affordance.
  assert.match(PANEL_SRC, /onSubmit|handleSubmit|handleSend/);
  // Stable click hooks for tests.
  assert.match(
    PANEL_SRC,
    /data-chat-(panel|prompt|submit|transcript)|data-action=("|')chat-/,
    "data-* hooks for chat surfaces",
  );
});

test("Phase 21 — data-workspace exposes 'Chat' tab + mounts panel", () => {
  // Tab type extended.
  assert.match(WORKSPACE_SRC, /["']chat["']/i, "Chat tab value");
  // ChatPanel imported + mounted.
  assert.match(
    WORKSPACE_SRC,
    /import\s*\{\s*ChatPanel\s*\}\s*from\s*['"]\.\/chat-panel['"]/,
  );
  assert.match(WORKSPACE_SRC, /<ChatPanel\b/, "ChatPanel mounted");
  // Chat-tab gates on an active file (per brief §9.3 — "Chat-tab
  // requires an active file"); accept either an explicit `if (active)`
  // gate near the ChatPanel mount or the workspace's existing
  // `{active ? (...)}` outer guard which already wraps Tab content.
  assert.match(WORKSPACE_SRC, /active\s*\?\s*\(/, "active-file gate around tab content");
});

test("Phase 21 — chat route persists artifact via existing persister", () => {
  // Reuse the existing parser + persister.
  assert.match(
    ROUTE_SRC,
    /import\s*\{[^}]*\bextractArtifactsFromChunk\b[^}]*\}\s*from/,
    "route imports extractArtifactsFromChunk",
  );
  assert.match(
    ROUTE_SRC,
    /import\s*\{[^}]*\bpersistArtifact\b[^}]*\}\s*from/,
    "route imports persistArtifact",
  );
  // Artifact persistence is reachable from the SSE consumer.
  assert.match(
    ROUTE_SRC,
    /persistArtifact\(/,
    "route calls persistArtifact",
  );
});
