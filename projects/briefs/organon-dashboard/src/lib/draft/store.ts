import {
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  renameSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import { organonRoot } from "../paths";
import { assertWithinProject } from "../projects";
import type {
  SectionDraftArtifact,
  SectionStatus,
  SectionType,
} from "../artifacts/types";

export type CitationStyle = "apa" | "nature" | "ieee" | "vancouver";

export type ManuscriptMeta = {
  slug: string;
  title: string;
  authors: string[];
  target_journal: string | null;
  citation_style: CitationStyle;
  /** Ordered list of section_ids matching files under sections/ */
  ordering: string[];
  created_at: string;
  updated_at: string;
  /**
   * Phase 41 (v1.5) — F4 source linkage.
   *
   * Optional arrays binding the manuscript to its source artifacts.
   * Empty (or undefined post-backfill → []) means "use everything in
   * the project" (backward-compat with v1.4 manuscripts where
   * generate-section pulled `listLibrary()` / `listFigures()`).
   * Non-empty narrows generation to the listed subset.
   *
   * Read-time backfilled by `migrateManuscriptLinkage`; never written
   * back to disk for legacy manuscripts (same pattern as Phase 35's
   * `migrateManuscriptOrdering`).
   */
  linked_hypothesis_ids?: string[];
  linked_paper_ids?: string[];
  linked_figure_ids?: string[];
  linked_dataset_ids?: string[];
};

// Phase 7 T6.2 — placeholders are plain prose. No `<span class="…">…</span>`
// markup that survives literally in markdown export. Cite/fig hints are
// shown in inline backticks since the live-preview renders them as
// inline-code (the right hint without burning HTML escapes).
//
// Phase 35 (v1.4) — B1: dropped the legacy "title" entry. Title is
// ManuscriptMeta.title metadata; AI candidates flow through
// /api/draft/[slug]/generate-title (Step 7.8). sci-writing's Step 7.7
// only handles body section types, so the legacy entry produced
// "succeeded-no-artifact" runs. Read-time backfill in
// migrateManuscriptOrdering filters legacy "title" from existing
// ordering[] without writing back.
const DEFAULT_SECTIONS: { id: string; type: SectionType; title: string; body: string }[] = [
  { id: "abstract", type: "abstract", title: "Abstract", body: "## Abstract\n\n_~150–250 words._\n" },
  { id: "introduction", type: "introduction", title: "Introduction", body: "## Introduction\n\nMotivate the question. Cite prior work with `\\cite{paper-id}`.\n" },
  { id: "methods", type: "methods", title: "Methods", body: "## Methods\n\nDescribe materials, procedure, and statistical tests. Inline math via `$\\Delta$` or display via `$$\\bar{x} \\pm 2 \\sigma$$`.\n" },
  { id: "results", type: "results", title: "Results", body: "## Results\n\nReport findings; embed plots with `\\fig{fig-id}`.\n" },
  { id: "discussion", type: "discussion", title: "Discussion", body: "## Discussion\n\nInterpret + caveat + future work.\n" },
  { id: "references", type: "references", title: "References", body: "## References\n\n_Auto-populated from `\\cite{}` blocks._\n" },
];

/**
 * Phase 35 (v1.4) — B1: pure helper that filters legacy "title" entries
 * out of an ordering array. Used by migrateManuscriptOrdering at read
 * time so existing manuscript.json files keep working without a
 * write-time migration that could lose user content.
 */
export function filterLegacyOrdering(ordering: string[]): string[] {
  if (!Array.isArray(ordering)) return [];
  return ordering.filter((id) => id !== "title");
}

/**
 * Phase 35 (v1.4) — B1: read-time backfill. Returns a NEW meta with
 * ordering filtered. Never writes; same locality pattern as Phase 12c
 * run-id locality. Existing sections/title.md files stay on disk
 * untouched (orphaned but harmless).
 */
export function migrateManuscriptOrdering(meta: ManuscriptMeta): ManuscriptMeta {
  return {
    ...meta,
    ordering: filterLegacyOrdering(meta.ordering ?? []),
  };
}

/**
 * Phase 41 (v1.5) — F4 source linkage read-time backfill. Returns a
 * NEW meta with each missing linkage array defaulted to []. Never
 * writes; pre-Phase-41 manuscripts on disk surface as `linked_*_ids
 * = []` after this pass, which `generate-section` / `generate-title`
 * interpret as "use everything in the project" (backward-compat).
 */
export function migrateManuscriptLinkage(meta: ManuscriptMeta): ManuscriptMeta {
  return {
    ...meta,
    linked_hypothesis_ids: Array.isArray(meta.linked_hypothesis_ids) ? meta.linked_hypothesis_ids : [],
    linked_paper_ids: Array.isArray(meta.linked_paper_ids) ? meta.linked_paper_ids : [],
    linked_figure_ids: Array.isArray(meta.linked_figure_ids) ? meta.linked_figure_ids : [],
    linked_dataset_ids: Array.isArray(meta.linked_dataset_ids) ? meta.linked_dataset_ids : [],
  };
}

export function manuscriptsDir(projectPath: string): string {
  return path.join(projectPath, "manuscripts");
}
export function manuscriptDir(projectPath: string, slug: string): string {
  return path.join(manuscriptsDir(projectPath), slug);
}
function metaPath(projectPath: string, slug: string): string {
  return path.join(manuscriptDir(projectPath, slug), "manuscript.json");
}
function sectionsDir(projectPath: string, slug: string): string {
  return path.join(manuscriptDir(projectPath, slug), "sections");
}
function sectionFile(projectPath: string, slug: string, sectionId: string): string {
  return path.join(sectionsDir(projectPath, slug), `${sectionId}.md`);
}
function sidecarFile(projectPath: string, slug: string, sectionId: string): string {
  return path.join(sectionsDir(projectPath, slug), `${sectionId}.json`);
}

function ensureDir(p: string): void {
  if (!existsSync(p)) mkdirSync(p, { recursive: true });
}
function writeAtomic(target: string, content: string | Uint8Array): void {
  const tmp = target + ".tmp";
  writeFileSync(tmp, content);
  renameSync(tmp, target);
}

export function listManuscripts(projectPath: string): ManuscriptMeta[] {
  const dir = manuscriptsDir(projectPath);
  if (!existsSync(dir)) return [];
  const out: ManuscriptMeta[] = [];
  for (const entry of readdirSync(dir)) {
    const sub = path.join(dir, entry);
    try {
      if (!statSync(sub).isDirectory()) continue;
    } catch { continue; }
    const meta = path.join(sub, "manuscript.json");
    if (!existsSync(meta)) continue;
    try {
      const obj = JSON.parse(readFileSync(meta, "utf8"));
      if (obj && typeof obj.slug === "string") {
        // Phase 35 (v1.4) + Phase 41 (v1.5) — read-time backfills:
        // ordering filter (B1) + linkage default (F4).
        out.push(migrateManuscriptLinkage(migrateManuscriptOrdering(obj as ManuscriptMeta)));
      }
    } catch { /* skip */ }
  }
  out.sort((a, b) => (b.updated_at ?? "").localeCompare(a.updated_at ?? ""));
  return out;
}

export function getManuscript(projectPath: string, slug: string): ManuscriptMeta | null {
  const target = metaPath(projectPath, slug);
  if (!existsSync(target)) return null;
  try {
    const obj = JSON.parse(readFileSync(target, "utf8"));
    if (obj && obj.slug === slug) {
      // Phase 35 + Phase 41 — backfill ordering + linkage at read.
      return migrateManuscriptLinkage(migrateManuscriptOrdering(obj as ManuscriptMeta));
    }
  } catch { /* fall through */ }
  return null;
}

export function createManuscript(
  projectPath: string,
  slug: string,
  opts: {
    title: string;
    authors?: string[];
    target_journal?: string | null;
    citation_style?: CitationStyle;
    linked_hypothesis_ids?: string[];
    linked_paper_ids?: string[];
    linked_figure_ids?: string[];
    linked_dataset_ids?: string[];
  },
): { meta: ManuscriptMeta; sections: SectionDraftArtifact[] } {
  ensureDir(sectionsDir(projectPath, slug));
  const now = new Date().toISOString();
  const meta: ManuscriptMeta = {
    slug,
    title: opts.title,
    authors: opts.authors ?? [],
    target_journal: opts.target_journal ?? null,
    citation_style: opts.citation_style ?? "apa",
    ordering: DEFAULT_SECTIONS.map((s) => s.id),
    created_at: now,
    updated_at: now,
    linked_hypothesis_ids: opts.linked_hypothesis_ids ?? [],
    linked_paper_ids: opts.linked_paper_ids ?? [],
    linked_figure_ids: opts.linked_figure_ids ?? [],
    linked_dataset_ids: opts.linked_dataset_ids ?? [],
  };
  const metaTarget = metaPath(projectPath, slug);
  assertWithinProject(metaTarget, projectPath);
  writeAtomic(metaTarget, JSON.stringify(meta, null, 2));
  const sections: SectionDraftArtifact[] = [];
  for (const s of DEFAULT_SECTIONS) {
    const body = s.body.replace("{{title}}", opts.title);
    writeAtomic(sectionFile(projectPath, slug, s.id), body);
    const sidecar: SectionDraftArtifact = {
      _artifact: "section-draft",
      schema_version: 1,
      id: `sect-${slug}-${s.id}`,
      manuscript_slug: slug,
      section_id: s.id,
      section_type: s.type,
      status: "draft",
      content_md: body,
      linked_figure_ids: [],
      linked_paper_ids: [],
      version: 1,
      library_path: path.relative(
        organonRoot(),
        sectionFile(projectPath, slug, s.id),
      ),
      updated_at: now,
    };
    writeAtomic(sidecarFile(projectPath, slug, s.id), JSON.stringify(sidecar, null, 2));
    sections.push(sidecar);
  }
  return { meta, sections };
}

export function updateManuscript(
  projectPath: string,
  slug: string,
  patch: Partial<Omit<ManuscriptMeta, "slug" | "created_at">>,
): ManuscriptMeta | null {
  const existing = getManuscript(projectPath, slug);
  if (!existing) return null;
  const updated: ManuscriptMeta = {
    ...existing,
    ...patch,
    slug: existing.slug,
    created_at: existing.created_at,
    updated_at: new Date().toISOString(),
  };
  writeAtomic(metaPath(projectPath, slug), JSON.stringify(updated, null, 2));
  return updated;
}

export function listSections(
  projectPath: string,
  slug: string,
): SectionDraftArtifact[] {
  const dir = sectionsDir(projectPath, slug);
  if (!existsSync(dir)) return [];
  const out: SectionDraftArtifact[] = [];
  for (const f of readdirSync(dir)) {
    if (!f.endsWith(".json")) continue;
    try {
      const obj = JSON.parse(readFileSync(path.join(dir, f), "utf8"));
      if (obj && obj._artifact === "section-draft") out.push(obj as SectionDraftArtifact);
    } catch { /* skip */ }
  }
  return out;
}

export function getSection(
  projectPath: string,
  slug: string,
  sectionId: string,
): SectionDraftArtifact | null {
  const target = sidecarFile(projectPath, slug, sectionId);
  if (!existsSync(target)) return null;
  try {
    const obj = JSON.parse(readFileSync(target, "utf8"));
    if (obj && obj._artifact === "section-draft") return obj as SectionDraftArtifact;
  } catch { /* fall through */ }
  return null;
}

/** Persist a section. Re-derives content_md from the sidecar payload + writes both files atomically. */
export function saveSection(
  projectPath: string,
  artifact: SectionDraftArtifact,
): string {
  ensureDir(sectionsDir(projectPath, artifact.manuscript_slug));
  const file = sectionFile(projectPath, artifact.manuscript_slug, artifact.section_id);
  const sidecar = sidecarFile(projectPath, artifact.manuscript_slug, artifact.section_id);
  assertWithinProject(file, projectPath);
  assertWithinProject(sidecar, projectPath);
  writeAtomic(file, artifact.content_md);
  const stamped: SectionDraftArtifact = {
    ...artifact,
    library_path: path.relative(organonRoot(), file),
    updated_at: new Date().toISOString(),
  };
  writeAtomic(sidecar, JSON.stringify(stamped, null, 2));
  // Bump manuscript updated_at on every section save.
  const meta = getManuscript(projectPath, artifact.manuscript_slug);
  if (meta) updateManuscript(projectPath, artifact.manuscript_slug, {});
  return stamped.library_path;
}

export function patchSection(
  projectPath: string,
  slug: string,
  sectionId: string,
  patch: Partial<Pick<
    SectionDraftArtifact,
    | "content_md"
    | "status"
    | "linked_figure_ids"
    | "linked_paper_ids"
    | "section_type"
    | "override_linked_paper_ids"
    | "override_linked_figure_ids"
    | "override_linked_hypothesis_ids"
    | "override_linked_dataset_ids"
  >>,
): SectionDraftArtifact | null {
  const existing = getSection(projectPath, slug, sectionId);
  if (!existing) return null;
  const next: SectionDraftArtifact = {
    ...existing,
    ...patch,
    version: existing.version + (patch.content_md && patch.content_md !== existing.content_md ? 1 : 0),
  };
  saveSection(projectPath, next);
  return next;
}

export function deleteSection(
  projectPath: string,
  slug: string,
  sectionId: string,
): boolean {
  const file = sectionFile(projectPath, slug, sectionId);
  const sidecar = sidecarFile(projectPath, slug, sectionId);
  let removed = false;
  if (existsSync(file)) { rmSync(file); removed = true; }
  if (existsSync(sidecar)) { rmSync(sidecar); removed = true; }
  const meta = getManuscript(projectPath, slug);
  if (meta) {
    updateManuscript(projectPath, slug, {
      ordering: meta.ordering.filter((id) => id !== sectionId),
    });
  }
  return removed;
}

/**
 * Phase 51 (v2.0) — Per-section linkage override resolver. Returns the
 * id list to narrow the named artifact pool against, or undefined when
 * "use everything" is the right call.
 *
 * Resolution order:
 *   1. section.override_linked_<kind>_ids (non-empty) — section wins.
 *   2. manuscript.linked_<kind>_ids (non-empty) — manuscript-wide.
 *   3. undefined — use everything.
 */
export type LinkageKind = "paper" | "figure" | "hypothesis" | "dataset";

export function effectiveSectionLinkage(
  section: SectionDraftArtifact | null | undefined,
  manuscript: ManuscriptMeta | null | undefined,
  kind: LinkageKind,
): string[] | undefined {
  const overrideKey = `override_linked_${kind}_ids` as const;
  const manuscriptKey = `linked_${kind}_ids` as const;
  const ov = section ? (section as unknown as Record<string, unknown>)[overrideKey] : undefined;
  if (Array.isArray(ov) && ov.length > 0) {
    return ov.filter((s): s is string => typeof s === "string");
  }
  const ms = manuscript
    ? (manuscript as unknown as Record<string, unknown>)[manuscriptKey]
    : undefined;
  if (Array.isArray(ms) && ms.length > 0) {
    return ms.filter((s): s is string => typeof s === "string");
  }
  return undefined;
}

/**
 * Phase 50 (v2.0) — Reverse linkage. Returns the manuscripts whose
 * `linked_hypothesis_ids[]` includes the given hypothesis id. Reads via
 * listManuscripts so the read-time backfill (migrateManuscriptLinkage)
 * normalises legacy manuscripts.
 */
export function findManuscriptsByHypothesisId(
  projectPath: string,
  hyp_id: string,
): ManuscriptMeta[] {
  return listManuscripts(projectPath).filter(
    (m) => Array.isArray(m.linked_hypothesis_ids) && m.linked_hypothesis_ids.includes(hyp_id),
  );
}

/**
 * Phase 62 (v2.2) — M1: hard delete a manuscript dir + all its sections.
 * Idempotent (`force: true`); no-op when the dir is already gone.
 * No tombstone, no soft-delete: researcher said "discard or remove".
 */
export function deleteManuscript(projectPath: string, slug: string): void {
  const target = manuscriptDir(projectPath, slug);
  assertWithinProject(target, projectPath);
  rmSync(target, { recursive: true, force: true });
}

export function existingSlugs(projectPath: string): string[] {
  const dir = manuscriptsDir(projectPath);
  if (!existsSync(dir)) return [];
  return readdirSync(dir).filter((entry) => {
    try {
      return statSync(path.join(dir, entry)).isDirectory();
    } catch { return false; }
  });
}
