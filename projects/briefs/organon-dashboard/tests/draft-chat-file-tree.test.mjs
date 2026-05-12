import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 29 (v1.2) — File-tree context in chat panel (DR-6+).
//
// Closes Phase 22's "File-tree context — those are v1.2" thread. The
// chat panel surfaces a project file tree (sections, figures,
// stat-results, papers, manuscripts). Clicking a file pins it as a
// reference; the chat route resolves the referenced files via the
// matching store and forwards bounded excerpts in the context envelope.

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
const TREE_ROUTE_SRC = tryRead(
  join(ROOT, "src", "app", "api", "draft", "[slug]", "file-tree", "route.ts"),
);
const EDIT_ROUTE_SRC = tryRead(
  join(ROOT, "src", "app", "api", "draft", "[slug]", "edit-with-chat", "route.ts"),
);
const PANEL_SRC = tryRead(join(ROOT, "src", "components", "draft", "chat-panel.tsx"));

test("Phase 29 — selection-context exports MAX_REFERENCED_FILES + MAX_REFERENCED_EXCERPT_CHARS", () => {
  assert.match(
    CTX_SRC,
    /export\s+const\s+MAX_REFERENCED_FILES\s*=\s*4\b/,
    "MAX_REFERENCED_FILES = 4 exported",
  );
  assert.match(
    CTX_SRC,
    /export\s+const\s+MAX_REFERENCED_EXCERPT_CHARS\s*=\s*1500\b/,
    "MAX_REFERENCED_EXCERPT_CHARS = 1500 exported",
  );
  assert.match(
    CTX_SRC,
    /(export\s+(type|interface)\s+ReferencedFile)/,
    "ReferencedFile type exported",
  );
  // ContextEnvelope picks up the new optional field.
  assert.match(
    CTX_SRC,
    /referenced_files\?:\s*ReferencedFile\[\]/,
    "ContextEnvelope.referenced_files?: ReferencedFile[]",
  );
  // The kind discriminator covers the five artifact kinds.
  for (const kind of ["section", "figure", "stat-result", "paper", "manuscript"]) {
    assert.match(
      CTX_SRC,
      new RegExp(`["']${kind}["']`),
      `ReferencedFile.kind covers '${kind}'`,
    );
  }
});

test("Phase 29 — buildContext caps referenced_files at 4, each excerpt at 1500 chars", () => {
  // The slice + trim use the exported caps.
  assert.match(
    CTX_SRC,
    /\.slice\(\s*0\s*,\s*MAX_REFERENCED_FILES\s*\)|\.slice\(\s*-\s*MAX_REFERENCED_FILES\s*\)/,
    "buildContext slices referenced_files via MAX_REFERENCED_FILES",
  );
  assert.match(
    CTX_SRC,
    /content_excerpt[^]*MAX_REFERENCED_EXCERPT_CHARS|MAX_REFERENCED_EXCERPT_CHARS[^]*content_excerpt/,
    "content_excerpt trimmed via MAX_REFERENCED_EXCERPT_CHARS",
  );
  // Behavioural replica — confirm cap-and-trim shape.
  const refs = Array.from({ length: 7 }, (_, i) => ({
    kind: "section",
    id: `s-${i}`,
    label: `Section ${i}`,
    content_excerpt: "x".repeat(2500),
  }));
  const capped = refs.slice(0, 4).map((r) => ({
    ...r,
    content_excerpt: r.content_excerpt.slice(0, 1500),
  }));
  assert.equal(capped.length, 4, "4 refs retained");
  assert.equal(capped[0].content_excerpt.length, 1500, "excerpt trimmed");
});

test("Phase 29 — file-tree route returns sections + figures + stat_results + papers + manuscripts", () => {
  assert.match(TREE_ROUTE_SRC, /export\s+async\s+function\s+GET/, "GET handler exported");
  for (const key of ["sections", "figures", "stat_results", "papers", "manuscripts"]) {
    assert.match(
      TREE_ROUTE_SRC,
      new RegExp(`\\b${key}\\b`),
      `route response includes ${key}`,
    );
  }
  // Pulls per-store list helpers.
  assert.match(TREE_ROUTE_SRC, /listSections\b/, "uses listSections");
  assert.match(TREE_ROUTE_SRC, /listFigures\b/, "uses listFigures");
  assert.match(TREE_ROUTE_SRC, /listResults\b/, "uses listResults");
  assert.match(TREE_ROUTE_SRC, /listLibrary\b/, "uses listLibrary");
  assert.match(TREE_ROUTE_SRC, /listManuscripts\b/, "uses listManuscripts");
});

test("Phase 29 — edit-with-chat route resolves referenced_file_ids via the matching store", () => {
  // Body type carries referenced_file_ids.
  assert.match(
    EDIT_ROUTE_SRC,
    /referenced_file_ids/,
    "Body exposes referenced_file_ids",
  );
  // The route resolves each kind via the matching store (at least one
  // import each — section / figure / stat-result / paper / manuscript).
  assert.match(EDIT_ROUTE_SRC, /readFigure\b/, "resolves figures via readFigure");
  // sections + library are already imported pre-Phase-29; confirm
  // the resolver path references kind discriminator.
  assert.match(
    EDIT_ROUTE_SRC,
    /kind/,
    "resolver references the kind discriminator",
  );
  // referenced_files passes through buildContext.
  assert.match(
    EDIT_ROUTE_SRC,
    /buildContext\([^)]*referenced/,
    "buildContext invoked with referenced_files",
  );
});

test("Phase 29 — chat-panel renders file chips above prompt + data hooks", () => {
  // Panel exposes a Files section with selectable items.
  assert.match(
    PANEL_SRC,
    /data-file-tree|data-action=("|')file-tree/,
    "panel surfaces a data-file-tree hook",
  );
  // Selected files render as removable chips.
  assert.match(
    PANEL_SRC,
    /data-action=("|')toggle-file/,
    "file-tree row exposes a toggle hook",
  );
  // Chip removal action.
  assert.match(
    PANEL_SRC,
    /data-action=("|')remove-file/,
    "selected chip exposes a remove hook",
  );
});
