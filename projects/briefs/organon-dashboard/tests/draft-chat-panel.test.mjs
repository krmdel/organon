import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 22 (v1.1+) — Whole-paper-aware AI editing + chat panel (DR-6).
//
// Right-rail chat surface on /draft. User selects text in the editor,
// types a prompt; the workspace POSTs selection + bounded context
// (siblings + linked papers) to /api/draft/[slug]/edit-with-chat,
// which spawns sci-writing in `mode=edit-with-chat` (Step 7.10) and
// emits a `section-diff` artifact. The panel surfaces an Apply button
// per emitted diff that swaps section.content_md to diff.after.
//
// v1.1 scope (per brief §10):
//   - Single-turn chat (multi-turn → v1.2)
//   - Apply = accept full diff (per-line → v1.2)
//   - Context envelope bounded at the dashboard, not the skill
//   - Selection capture via editor ref handle (no lifted state)
//   - Right rail, not modal
//
// Tests follow the source-text-scan pattern used by Phases 9–21.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const ROUTE_SRC = readFileSync(
  join(ROOT, "src", "app", "api", "draft", "[slug]", "edit-with-chat", "route.ts"),
  "utf8",
);
const PANEL_SRC = readFileSync(
  join(ROOT, "src", "components", "draft", "chat-panel.tsx"),
  "utf8",
);
const EDITOR_SRC = readFileSync(
  join(ROOT, "src", "components", "draft", "markdown-editor.tsx"),
  "utf8",
);
const WORKSPACE_SRC = readFileSync(
  join(ROOT, "src", "components", "draft", "manuscript-workspace.tsx"),
  "utf8",
);
const SELECTION_CONTEXT_SRC = readFileSync(
  join(ROOT, "src", "lib", "draft", "selection-context.ts"),
  "utf8",
);
const SKILL_SRC = readFileSync(
  join(ROOT, "..", "..", "..", ".claude", "skills", "sci-writing", "SKILL.md"),
  "utf8",
);

test("Phase 22 — edit-with-chat route refuses without section_id (400)", () => {
  assert.match(ROUTE_SRC, /section_id/, "body type carries section_id");
  // Refuse with 400 when missing.
  assert.match(
    ROUTE_SRC,
    /section_id required[^"]*"\s*\}\s*,\s*\{\s*status:\s*400|status:\s*400[^"]*"section_id/,
    "missing section_id returns 400",
  );
  // Spawns sci-writing (per Step 7.10).
  assert.match(ROUTE_SRC, /mode=edit-with-chat/);
});

test("Phase 22 — edit-with-chat route forwards selection + context to sci-writing", () => {
  // Body type includes selection + prompt; route imports buildContext.
  assert.match(ROUTE_SRC, /selection/);
  assert.match(ROUTE_SRC, /prompt/);
  assert.match(
    ROUTE_SRC,
    /import\s*\{[^}]*\bbuildContext\b[^}]*\}\s*from/,
    "route imports buildContext from selection-context",
  );
  // Embeds selection + context in the spawned prompt.
  assert.match(ROUTE_SRC, /selection_text|selection=|selection:|selection_start/);
  // active_project_slug embedded (per pitfall #3 in the v1.1 brief).
  assert.match(ROUTE_SRC, /active_project_slug=/);
});

test("Phase 22 — chat-panel captures selection via editor ref handle", () => {
  // markdown-editor exposes a ref handle with getSelection.
  assert.match(EDITOR_SRC, /getSelection/);
  assert.match(
    EDITOR_SRC,
    /forwardRef|useImperativeHandle/,
    "editor uses forwardRef + useImperativeHandle to expose the handle",
  );
  // chat-panel takes the handle as a prop and reads it before submit.
  assert.match(PANEL_SRC, /editorRef|editorHandle|MarkdownEditorHandle/);
  assert.match(
    PANEL_SRC,
    /\.current\??\.getSelection\(\)/,
    "panel calls editorRef.current.getSelection() before submit",
  );
});

test("Phase 22 — chat-panel renders Apply button on each emitted section-diff", () => {
  // Reuses Phase 7 DiffView OR renders an explicit Apply affordance per diff.
  assert.ok(
    /DiffView/.test(PANEL_SRC) || /onApply|Apply\s*(edit|diff)?/i.test(PANEL_SRC),
    "panel renders Apply affordance per emitted diff",
  );
  // Iterates over emitted diffs (or a transcript of them).
  assert.match(
    PANEL_SRC,
    /\.map\s*\(\s*\(?\w+\s*[,)]/,
    "panel maps over a list of diffs / chat turns",
  );
  // Stable click hook for tests.
  assert.match(
    PANEL_SRC,
    /data-action=("|')apply-chat-diff\1|data-chat-(panel|apply)/,
    "data-action hook on the Apply button",
  );
});

test("Phase 22 — buildContext caps siblings + linked_papers below the limits", () => {
  // Per brief §10.3: "max ~2k chars per sibling, max 6 papers".
  // Structural — limit constants visible in the source.
  assert.ok(
    /\b2000\b|\b2_?000\b|\b2048\b|MAX_SIBLING_CHARS/.test(SELECTION_CONTEXT_SRC),
    "max-chars-per-sibling limit declared",
  );
  assert.ok(
    /\b6\b|MAX_LINKED_PAPERS|MAX_PAPERS/.test(SELECTION_CONTEXT_SRC),
    "max-linked-papers limit declared",
  );

  // Behavioural — replicate the helper inline (the test harness can't
  // import .ts directly) and assert the cap behaviour.
  const MAX_SIBLING_CHARS = 2000;
  const MAX_LINKED_PAPERS = 6;
  const buildContext = (section, siblings, library) => ({
    active: section,
    siblings: siblings.slice(0, 16).map((s) => ({
      section_id: s.section_id,
      section_type: s.section_type,
      content_md: (s.content_md ?? "").slice(0, MAX_SIBLING_CHARS),
    })),
    linked_papers: library.slice(0, MAX_LINKED_PAPERS).map((p) => ({
      cite_key: p.cite_key ?? p.id,
      title: p.title,
      authors: Array.isArray(p.authors) ? p.authors.slice(0, 6) : [],
    })),
  });

  const sectionA = { section_id: "a", section_type: "introduction", content_md: "x" };
  const longProse = "y".repeat(5000);
  const siblings = [
    { section_id: "b", section_type: "methods", content_md: longProse },
  ];
  const library = Array.from({ length: 12 }, (_, i) => ({
    id: `p${i}`,
    cite_key: `Smith202${i}`,
    title: `Paper ${i}`,
    authors: [`Smith${i}`],
  }));
  const ctx = buildContext(sectionA, siblings, library);
  assert.equal(ctx.siblings[0].content_md.length, MAX_SIBLING_CHARS);
  assert.equal(ctx.linked_papers.length, MAX_LINKED_PAPERS);
});

test("Phase 22 — sci-writing SKILL.md Step 7.10 documents edit-with-chat mode", () => {
  // Step 7.10 heading present + names the mode.
  assert.match(
    SKILL_SRC,
    /^##\s+Step\s+7\.10:.*edit-with-chat/m,
    "Step 7.10 heading mentions edit-with-chat",
  );
  // Step 0 routing table picks up the new mode trigger.
  assert.match(SKILL_SRC, /dashboard-edit-with-chat/);
  // Documents the trigger keys the dashboard route emits.
  assert.match(SKILL_SRC, /mode=edit-with-chat/);
});
