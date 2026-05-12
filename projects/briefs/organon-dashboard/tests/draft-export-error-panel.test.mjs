import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 16 (v1.0.1) — Expandable export error panel (EX-1).
//
// When /api/draft/[slug]/export returns 422 with `unresolved_cites` +
// `unresolved_figs`, the workspace builds a per-token entry list with
// the host section located by `findSectionForToken` and renders the
// ExportErrorPanel. Each entry exposes a "fix in editor" button that
// calls handleSelect on the workspace's section list.
//
// Source-text scan + behavioural mirror pattern (consistent with
// state-persistence, draft-code-spans, draft-math-accents).

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const PANEL_SRC = readFileSync(
  join(ROOT, "src", "components", "draft", "export-error-panel.tsx"),
  "utf8",
);
const WORKSPACE_SRC = readFileSync(
  join(ROOT, "src", "components", "draft", "manuscript-workspace.tsx"),
  "utf8",
);
const ROUTE_SRC = readFileSync(
  join(ROOT, "src", "app", "api", "draft", "[slug]", "export", "route.ts"),
  "utf8",
);

test("export-error-panel exports the documented contract", () => {
  assert.match(PANEL_SRC, /export type ExportErrorEntry =/);
  assert.match(PANEL_SRC, /token: string/);
  assert.match(PANEL_SRC, /kind: "cite" \| "fig"/);
  assert.match(PANEL_SRC, /targetSectionId: string \| null/);
  assert.match(PANEL_SRC, /export type ExportErrorPanelProps =/);
  assert.match(PANEL_SRC, /entries: ExportErrorEntry\[\]/);
  assert.match(PANEL_SRC, /onJumpToSection: \(sectionId: string\) => void/);
  assert.match(PANEL_SRC, /onDismiss: \(\) => void/);
});

test("export-error-panel renders pill + expandable list with click-to-toggle", () => {
  // Pill button toggles the expanded state; aria-expanded is exposed
  // for accessibility-first click tests.
  assert.match(PANEL_SRC, /data-export-error-pill/);
  assert.match(PANEL_SRC, /aria-expanded=\{expanded\}/);
  assert.match(PANEL_SRC, /onClick=\{\(\) => setExpanded\(\(v\) => !v\)\}/);
  // Expanded body lists each entry with kind-badge + token + section hint.
  assert.match(PANEL_SRC, /data-export-error-list/);
  assert.match(PANEL_SRC, /data-export-error-entry/);
  assert.match(PANEL_SRC, /data-entry-kind=\{entry\.kind\}/);
  assert.match(PANEL_SRC, /data-entry-token=\{entry\.token\}/);
});

test("each unresolved entry has a 'fix in editor' button with the target id", () => {
  // Action button on every row, action label + target section id pinned
  // on data-attributes so click-tests can locate by attribute alone.
  assert.match(PANEL_SRC, /data-action="fix-in-editor"/);
  assert.match(PANEL_SRC, /data-target-section-id=\{entry\.targetSectionId \?\? ""\}/);
  // Button is disabled when the parent could not locate a host section.
  assert.match(PANEL_SRC, /disabled=\{!entry\.targetSectionId\}/);
  // Click handler routes through onJumpToSection only when target exists.
  assert.match(PANEL_SRC, /entry\.targetSectionId\s*\?\s*onJumpToSection\(entry\.targetSectionId\)/);
});

test("panel exposes a dismiss action that the workspace uses to clear state", () => {
  assert.match(PANEL_SRC, /data-action="dismiss-export-error"/);
  assert.match(PANEL_SRC, /onClick=\{onDismiss\}/);
});

test("manuscript-workspace owns the structured exportError state alongside exportLog", () => {
  // New state shape declared with the documented fields.
  assert.match(WORKSPACE_SRC, /const \[exportError, setExportError\] = useState</);
  assert.match(WORKSPACE_SRC, /format: ExportFormat;\s*entries: ExportErrorEntry\[\];/s);
  // The fallback truncated text is suppressed when the structured panel
  // is showing — avoids double-reporting on the same failure.
  assert.match(WORKSPACE_SRC, /\{exportLog && !exportError && \(/);
});

test("handleExport parses unresolved_cites + unresolved_figs and clears stale state on retry", () => {
  // Read both arrays from the 422 response and convert each token to a
  // per-entry record routed through findSectionForToken.
  assert.match(WORKSPACE_SRC, /Array\.isArray\(json\?\.unresolved_cites\)/);
  assert.match(WORKSPACE_SRC, /Array\.isArray\(json\?\.unresolved_figs\)/);
  assert.match(WORKSPACE_SRC, /findSectionForToken\("cite", token\)/);
  assert.match(WORKSPACE_SRC, /findSectionForToken\("fig", token\)/);
  // Every retry clears stale 422 detail before the new fetch.
  assert.match(WORKSPACE_SRC, /setExportError\(null\);/);
});

test("findSectionForToken matches \\cite{token} and \\fig{token} bodies including comma lists", () => {
  // Behavioural mirror: re-implement the function and verify it locates
  // the section regardless of whether the token sits alone or in a
  // comma-separated body.
  const findSectionForToken = (kind, token, sections) => {
    const cleaned = token.trim();
    const macro = kind === "cite" ? "cite" : "fig";
    const escaped = cleaned.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const pattern = new RegExp(`\\\\${macro}\\{[^}]*\\b${escaped}\\b[^}]*\\}`);
    for (const s of sections) {
      if (pattern.test(s.content_md)) {
        return { id: s.section_id, title: s.section_type };
      }
    }
    return null;
  };

  const sections = [
    {
      section_id: "intro",
      section_type: "introduction",
      content_md: "First mention of \\cite{Smith2026} in intro.",
    },
    {
      section_id: "methods",
      section_type: "methods",
      content_md: "We follow \\cite{Brown2023, Wales2007} closely.",
    },
    {
      section_id: "results",
      section_type: "results",
      content_md: "See \\fig{fig-3} for the comparison.",
    },
  ];

  // Single-key citation in a section.
  assert.deepEqual(
    findSectionForToken("cite", "Smith2026", sections),
    { id: "intro", title: "introduction" },
  );
  // Comma-list citation; the second token still hits the methods section.
  assert.deepEqual(
    findSectionForToken("cite", "Wales2007", sections),
    { id: "methods", title: "methods" },
  );
  // Figure macro.
  assert.deepEqual(
    findSectionForToken("fig", "fig-3", sections),
    { id: "results", title: "results" },
  );
  // No host section — token does not appear anywhere.
  assert.equal(findSectionForToken("cite", "Ghost9999", sections), null);
});

test("findSectionForToken does not false-match a substring of another token", () => {
  // Guard: ensure word boundaries protect against `Smith2026` matching
  // when the body actually contains `Smith2026Extended`.
  const findSectionForToken = (kind, token, sections) => {
    const cleaned = token.trim();
    const macro = kind === "cite" ? "cite" : "fig";
    const escaped = cleaned.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const pattern = new RegExp(`\\\\${macro}\\{[^}]*\\b${escaped}\\b[^}]*\\}`);
    for (const s of sections) {
      if (pattern.test(s.content_md)) {
        return { id: s.section_id, title: s.section_type };
      }
    }
    return null;
  };

  const sections = [
    {
      section_id: "intro",
      section_type: "introduction",
      content_md: "Cites \\cite{Smith2026Extended} only.",
    },
  ];

  // The shorter `Smith2026` should NOT match the longer `Smith2026Extended`
  // — \b boundaries enforce whole-token-only matching for typical
  // alphanumeric/underscore-separated keys. (Hyphenated keys still match
  // because '-' is a non-word character; the dashboard's CITE_RE shape
  // accepts hyphens too — this is tested via "fig-3" above.)
  assert.equal(findSectionForToken("cite", "Smith2026", sections), null);
});

test("export route 422 response shape carries unresolved_cites + unresolved_figs", () => {
  // Sanity: the route still returns the snake_case keys the workspace
  // expects. If this changes, both the route and the parser need to
  // move together.
  assert.match(ROUTE_SRC, /unresolved_cites: assembled\.unresolvedCites/);
  assert.match(ROUTE_SRC, /unresolved_figs: assembled\.unresolvedFigs/);
  assert.match(ROUTE_SRC, /\{ status: 422 \}/);
});
