import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 61 (v2.1) — A4: successful generate-section retry clears stale
// failure messages BEFORE the success state lands; editor scrolls into
// view so the freshly-drafted content is visible.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const WORKSPACE_SRC = readSrc("src/components/draft/manuscript-workspace.tsx");
const EDITOR_SRC = readSrc("src/components/draft/markdown-editor.tsx");

test("Phase 61 — successful generate-section retry clears stale failure messages BEFORE rendering success", () => {
  // handleGenerateSection must call setErrors([]) at the top of the
  // handler so a previous failed attempt's messages don't survive.
  // It must also clear setGenerateRunMessage(null) before the run.
  const handlerMatch = WORKSPACE_SRC.match(
    /const\s+handleGenerateSection\s*=\s*useCallback\([\s\S]*?,\s*\[[^\]]*\]\s*\);/,
  );
  assert.ok(handlerMatch, "handleGenerateSection must exist as a useCallback");
  const handler = handlerMatch[0];
  assert.match(
    handler,
    /setErrors\(\[\]\)/,
    "handleGenerateSection must call setErrors([]) to clear stale errors before retry",
  );
  assert.match(
    handler,
    /setGenerateRunMessage\(null\)/,
    "handleGenerateSection must clear setGenerateRunMessage(null) before retry",
  );
  // The clear must happen BEFORE the await on generateOneSection so
  // a successful retry never renders against a stale toast.
  const idxClearErrors = handler.search(/setErrors\(\[\]\)/);
  const idxAwait = handler.search(/await\s+generateOneSection/);
  assert.ok(idxClearErrors > 0 && idxAwait > 0, "both anchors must be present");
  assert.ok(
    idxClearErrors < idxAwait,
    "setErrors([]) must be called BEFORE await generateOneSection(sectionId)",
  );
});

test("Phase 61 — workspace scrolls editor to the persisted section after a successful generate", () => {
  // The editor handle gains a scrollIntoView() method.
  assert.match(
    EDITOR_SRC,
    /scrollIntoView:\s*\(\)\s*=>/,
    "MarkdownEditorHandle must expose scrollIntoView",
  );
  // useImperativeHandle must implement it.
  assert.match(
    EDITOR_SRC,
    /scrollIntoView:\s*\(\)\s*=>\s*\{[\s\S]{0,200}ta\.scrollIntoView/,
    "scrollIntoView impl must call ta.scrollIntoView() on the textarea",
  );
  // The workspace handler must call editorRef.current.scrollIntoView()
  // when the just-generated section is the active one.
  assert.match(
    WORKSPACE_SRC,
    /editorRef\.current\.scrollIntoView\(\)/,
    "handleGenerateSection must call editorRef.current.scrollIntoView() on success",
  );
  assert.match(
    WORKSPACE_SRC,
    /sectionId\s*===\s*activeId\s*&&\s*editorRef\.current/,
    "scroll guard must check sectionId === activeId before firing",
  );
});
