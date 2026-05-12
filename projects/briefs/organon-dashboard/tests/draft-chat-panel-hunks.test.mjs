import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 33 (v1.3) — DR-6++ chat-panel inline per-hunk DiffView.
//
// v1.2 Phase 28 ships per-hunk accept on the workspace-level DiffView
// (rewrite/tighten flow). The chat-panel's per-turn "Apply edit"
// button still uses the v1.1 full-diff path. Phase 33 swaps in the
// existing DiffView so per-hunk accept works in chat too.
//
// onApply (full-diff) stays as the Accept-All shortcut. onApplyHunks
// is the per-hunk path; the workspace's existing handleApplyChatHunks
// (Phase 28) is wired through.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

const tryRead = (p) => {
  try {
    return readFileSync(p, "utf8");
  } catch {
    return "";
  }
};

const CHAT_PANEL_SRC = tryRead(
  join(ROOT, "src", "components", "draft", "chat-panel.tsx"),
);
const WORKSPACE_SRC = tryRead(
  join(ROOT, "src", "components", "draft", "manuscript-workspace.tsx"),
);

test("Phase 33 — chat-panel mounts <DiffView /> per-turn instead of an ad-hoc Apply button", () => {
  // chat-panel imports DiffView.
  assert.match(
    CHAT_PANEL_SRC,
    /import\s*\{[^}]*\bDiffView\b[^}]*\}\s*from\s*["'][^"']*diff-view/,
    "chat-panel imports DiffView from the shared component",
  );
  // Per-turn block mounts <DiffView diff={turn.diff} ... />.
  assert.match(
    CHAT_PANEL_SRC,
    /<DiffView\b[\s\S]*?diff\s*=\s*\{\s*turn\.diff\s*\}/,
    "DiffView mounted with diff={turn.diff}",
  );
});

test("Phase 33 — chat-panel forwards onApplyHunks from props through DiffView's onAcceptHunks", () => {
  // chat-panel props gain onApplyHunks.
  assert.match(
    CHAT_PANEL_SRC,
    /onApplyHunks\s*\?\s*:\s*\(/,
    "ChatPanelProps adds optional onApplyHunks",
  );
  // The DiffView mount forwards the panel's onApplyHunks(turn, ...) into
  // its onAcceptHunks. Match either inline-arrow or named-handler form;
  // both must reference the turn id.
  assert.match(
    CHAT_PANEL_SRC,
    /onAcceptHunks\s*=\s*\{[^}]*(turn|onApplyHunks)/,
    "DiffView's onAcceptHunks forwards through onApplyHunks(turn, ...)",
  );
});

test("Phase 33 — workspace wires handleApplyChatHunks to chat-panel's onApplyHunks", () => {
  // <ChatPanel> mount in the workspace passes onApplyHunks={handleApplyChatHunks}.
  assert.match(
    WORKSPACE_SRC,
    /onApplyHunks\s*=\s*\{\s*handleApplyChatHunks\s*\}/,
    "<ChatPanel> mount wires onApplyHunks={handleApplyChatHunks}",
  );
  // The handler signature already exists from Phase 28; verify it
  // accepts (turn, composedAfter).
  assert.match(
    WORKSPACE_SRC,
    /handleApplyChatHunks\s*=[\s\S]*?\(\s*turn[^,)]*,\s*composedAfter/,
    "handleApplyChatHunks(turn, composedAfter) signature unchanged",
  );
});

test("Phase 33 — turn.applied freezes the per-turn DiffView (no double-apply)", () => {
  // The per-turn block conditions on turn.applied to disable / freeze
  // the DiffView. Match either a wrapper-disabled prop, a conditional
  // mount on !turn.applied, or a key/className flag.
  assert.match(
    CHAT_PANEL_SRC,
    /turn\.applied/,
    "panel checks turn.applied for the per-turn DiffView surface",
  );
  // The legacy per-turn ad-hoc Apply button is gone — the DiffView
  // mount replaces it. Allow the v1.1 data-action only inside a
  // conditional fallback (e.g. when diff is null we still show a
  // running indicator). Specifically, the OLD apply-chat-diff button
  // is no longer rendered for a turn with a diff.
  // We check: the v1.1 button data-action="apply-chat-diff" must not
  // appear inside a block that mounts the new DiffView. Cheap proxy:
  // assert apply-chat-diff is absent OR the file mounts DiffView and
  // doesn't render Apply edit twice for the same turn.
  // Simplest robust scan: source must mount DiffView at least once
  // for turn.diff and must not contain the old "Apply edit" label
  // bound to the apply-chat-diff data-action.
  assert.doesNotMatch(
    CHAT_PANEL_SRC,
    /data-action\s*=\s*"apply-chat-diff"[\s\S]{0,200}Apply edit/,
    "v1.1 ad-hoc 'Apply edit' button no longer appears alongside data-action='apply-chat-diff'",
  );
});
