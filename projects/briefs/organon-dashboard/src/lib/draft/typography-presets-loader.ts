// Phase 25 (v1.2) — DR-8+ server-only loader for the typography
// preset registry. Reads `<projectPath>/.organon/typography-presets.json`
// and merges with BUILTIN_PRESETS (project entries override builtins
// on id collision). Permissive validation — invalid entries are
// dropped with a console.warn, never thrown.
//
// Splitting the loader out keeps `node:fs` out of the client bundle;
// the export-menu only imports the client-safe builtin shim from
// `typography-presets.ts` and fetches project entries via the
// `/api/draft/typography-presets` route.

import { existsSync, mkdirSync, readFileSync, unlinkSync, writeFileSync } from "node:fs";
import { randomBytes } from "node:crypto";
import path from "node:path";
import {
  BUILTIN_PRESETS,
  isValidPreset,
  type TypographyPreset,
} from "./typography-presets";

/**
 * Phase 25 — project file path. Centralised so the route + loader
 * agree on the location.
 */
export function projectPresetsPath(projectPath: string): string {
  return path.join(projectPath, ".organon", "typography-presets.json");
}

/**
 * Phase 25 — read + parse the project file. Missing file → `[]`.
 * Malformed JSON, unexpected shape, or parse error → `[]` plus a
 * console warning. Never throws.
 */
export function readProjectPresets(projectPath: string): TypographyPreset[] {
  const file = projectPresetsPath(projectPath);
  if (!existsSync(file)) return [];
  try {
    const raw = readFileSync(file, "utf8");
    const parsed = JSON.parse(raw) as { presets?: unknown };
    const list = Array.isArray(parsed?.presets) ? parsed.presets : [];
    const valid: TypographyPreset[] = [];
    for (const entry of list) {
      if (isValidPreset(entry)) {
        valid.push({ ...entry, source: "project" });
      } else {
        console.warn(
          `[typography-presets] Dropping invalid project entry in ${file}: ${JSON.stringify(entry).slice(0, 120)}`,
        );
      }
    }
    return valid;
  } catch (err) {
    console.warn(
      `[typography-presets] Failed to read ${file}: ${err instanceof Error ? err.message : String(err)}`,
    );
    return [];
  }
}

/**
 * Phase 25 — merge BUILTIN_PRESETS with project entries; project
 * entries override builtins on id collision. Builtin order is
 * preserved; new project ids are appended after the builtins.
 */
export function loadPresets(projectPath?: string | null): TypographyPreset[] {
  if (!projectPath) return BUILTIN_PRESETS.slice();
  const projectEntries = readProjectPresets(projectPath);
  if (projectEntries.length === 0) return BUILTIN_PRESETS.slice();
  const projectById = new Map(projectEntries.map((p) => [p.id, p]));
  const merged: TypographyPreset[] = BUILTIN_PRESETS.map((b) => projectById.get(b.id) ?? b);
  for (const p of projectEntries) {
    if (!BUILTIN_PRESETS.some((b) => b.id === p.id)) merged.push(p);
  }
  return merged;
}

/**
 * Phase 25 — split view used by the typography-presets API GET route.
 * Surfaces builtins + project entries separately so the menu can label
 * project entries with a "● custom" chip.
 */
export function loadPresetsSplit(
  projectPath?: string | null,
): { builtin: TypographyPreset[]; project: TypographyPreset[] } {
  const builtin = BUILTIN_PRESETS.slice();
  const project = projectPath ? readProjectPresets(projectPath) : [];
  return { builtin, project };
}

/**
 * Phase 25 — server-side preset resolver that respects project
 * overrides. Renamed from `getPreset` to avoid colliding with the
 * client-safe getPreset in `typography-presets.ts` (the export-menu
 * imports that one; this one only runs server-side via API routes).
 *
 * Unknown id falls back to the merged list's head (BUILTIN_PRESETS[0]
 * unless a project preset overrode the default id). Stale preset_ids
 * from localStorage must not fail an export.
 */
export function resolvePreset(
  id: string | null | undefined,
  projectPath?: string | null,
): TypographyPreset {
  const all = loadPresets(projectPath);
  if (!id) return all[0];
  return all.find((p) => p.id === id) ?? all[0];
}

// Phase 25 — server-side alias preserving the v1.1 export name. The
// export route imports `getPreset` from this loader (not from the
// client-safe registry) when it needs project overrides.
export const getPreset = resolvePreset;

/**
 * Phase 30 (v1.3) — DR-8++ result shape returned by
 * materializeCssForPandoc. Each format's argv slice is appended to
 * the export tool's argv:
 * - html → Marp `--theme <tmp.css>`
 * - pdf  → empty (pandoc xelatex needs --include-in-header which
 *          targets a different artifact; deferred to v1.4)
 * - docx → empty (pandoc DOCX needs --reference-doc which targets a
 *          different artifact; deferred to v1.4)
 *
 * cleanup() unlinks the materialised tmp file. Idempotent + safe on
 * missing path so try/finally callers don't have to track state.
 */
export type MaterializedCss = {
  extraArgsByFormat: { html: string[]; pdf: string[]; docx: string[] };
  cleanup: () => void;
};

/**
 * Phase 30 (v1.3) — materialise `preset.css` to a tmp file and return
 * per-format argv slices. When preset.css is unset / empty, returns
 * empty arg arrays + a no-op cleanup.
 *
 * Tmp files live under `<tmpDir>/preset-<id>-<random>.css` so concurrent
 * exports never collide. The caller is responsible for invoking
 * cleanup() in a try/finally — failure to do so leaks the tmp file.
 */
export function materializeCssForPandoc(
  preset: TypographyPreset,
  tmpDir: string,
): MaterializedCss {
  const empty: MaterializedCss = {
    extraArgsByFormat: { html: [], pdf: [], docx: [] },
    cleanup: () => {},
  };
  if (!preset || typeof preset.css !== "string" || preset.css.length === 0) {
    return empty;
  }
  if (!existsSync(tmpDir)) mkdirSync(tmpDir, { recursive: true });
  const random = randomBytes(6).toString("hex");
  const file = path.join(tmpDir, `preset-${preset.id}-${random}.css`);
  writeFileSync(file, preset.css);
  return {
    extraArgsByFormat: { html: ["--theme", file], pdf: [], docx: [] },
    cleanup: () => {
      try {
        if (existsSync(file)) unlinkSync(file);
      } catch {
        // idempotent — never throw out of cleanup
      }
    },
  };
}
