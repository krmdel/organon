// Phase 18 (v1.1+) — Typography / layout preset registry (DR-8).
// Phase 25 (v1.2) — DR-8+ split into client-safe (this file) and
// server-only loader (`typography-presets-loader.ts`). The
// fs-using merge happens in the loader; this module ships the
// canonical builtin list, the type, the validator, and the
// builtin-only fallbacks. The export-menu imports from here only
// (no node:fs in the client bundle).
//
// Markdown / HTML / Substack ignore presets (no pandoc); the dropdown
// only surfaces in the export menu when PDF + DOCX are visible.

export type TypographyPreset = {
  id: string;
  label: string;
  description: string;
  // Args appended to the pandoc argv on a PDF export. Each entry is a
  // single argv element — pandoc's `--variable=key:value` form is one
  // arg, so each variable lives as its own string here.
  pdfArgs: string[];
  // Args appended on a DOCX export. Most presets ship empty here in
  // v1.1; future versions can wire `--reference-doc=...` files in.
  docxArgs: string[];
  // Phase 25 — reserved for v1.3 CSS injection. Loader ignores this
  // field today; the schema reserves it so the project-file shape
  // stays forward-compatible.
  css?: string;
  // Phase 25 — provenance tag. "builtin" for BUILTIN_PRESETS, "project"
  // for entries loaded from `.organon/typography-presets.json`.
  source?: "builtin" | "project";
};

// Order matters: BUILTIN_PRESETS[0] is the canonical default and the
// fallback for getPreset() when an unknown id arrives.
export const BUILTIN_PRESETS: TypographyPreset[] = [
  {
    id: "default",
    label: "Default",
    description: "Pandoc defaults — readable single-column body.",
    pdfArgs: [],
    docxArgs: [],
    source: "builtin",
  },
  {
    id: "two-column",
    label: "Two-column",
    description: "Two-column body for compact layout.",
    pdfArgs: ["--variable=classoption:twocolumn"],
    docxArgs: [],
    source: "builtin",
  },
  {
    id: "nature",
    label: "Venue: Nature",
    description: "Times-family body, 11pt, 1in margins.",
    pdfArgs: [
      "--variable=mainfont:Times New Roman",
      "--variable=fontsize:11pt",
      "--variable=geometry:margin=1in",
    ],
    docxArgs: [],
    source: "builtin",
  },
  {
    id: "science",
    label: "Venue: Science",
    description: "Helvetica body, 10pt, 0.75in margins.",
    pdfArgs: [
      "--variable=mainfont:Helvetica",
      "--variable=fontsize:10pt",
      "--variable=geometry:margin=0.75in",
    ],
    docxArgs: [],
    source: "builtin",
  },
  {
    id: "ieee",
    label: "Venue: IEEE",
    description: "Times-family body, 10pt, two-column, 0.75in margins.",
    pdfArgs: [
      "--variable=mainfont:Times New Roman",
      "--variable=fontsize:10pt",
      "--variable=classoption:twocolumn",
      "--variable=geometry:margin=0.75in",
    ],
    docxArgs: [],
    source: "builtin",
  },
];

export const DEFAULT_PRESET_ID = "default";

/**
 * Phase 25 — duck-type validator. Accepts unknown JSON entries and
 * returns true only when every required field is present + the right
 * type. Drop-not-throw — invalid entries are filtered out by callers.
 *
 * Lives client-side too (no fs) so the API route can reuse it on
 * incoming POST bodies.
 */
export function isValidPreset(x: unknown): x is TypographyPreset {
  if (!x || typeof x !== "object") return false;
  const p = x as Record<string, unknown>;
  if (typeof p.id !== "string" || p.id.length === 0) return false;
  if (typeof p.label !== "string" || p.label.length === 0) return false;
  if (typeof p.description !== "string") return false;
  if (!Array.isArray(p.pdfArgs) || !p.pdfArgs.every((a) => typeof a === "string")) return false;
  if (!Array.isArray(p.docxArgs) || !p.docxArgs.every((a) => typeof a === "string")) return false;
  if (p.css !== undefined && typeof p.css !== "string") return false;
  return true;
}

/**
 * Phase 25 — client-safe builtin-only listing. The export-menu uses
 * this for SSR + initial render; on mount it fetches the merged split
 * from `/api/draft/typography-presets` to pick up project entries.
 */
export function listPresets(): TypographyPreset[] {
  return BUILTIN_PRESETS.slice();
}

/**
 * Phase 18 (v1.1+) — Phase 25 (v1.2): client-safe builtin-only getter.
 * Preserves the v1.1 export name. Server-side callers needing project
 * overrides use `typography-presets-loader.ts::resolvePreset(id, projectPath)`.
 */
export function getPreset(id: string | null | undefined): TypographyPreset {
  if (!id) return BUILTIN_PRESETS[0];
  return BUILTIN_PRESETS.find((p) => p.id === id) ?? BUILTIN_PRESETS[0];
}
