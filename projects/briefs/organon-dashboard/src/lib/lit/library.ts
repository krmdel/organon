import { existsSync, mkdirSync, readFileSync, readdirSync, renameSync, unlinkSync, writeFileSync } from "node:fs";
import path from "node:path";
import type { PaperArtifact } from "../artifacts/types";
import { organonRoot } from "../paths";
import { assertWithinProject } from "../projects";
import { paperToCiteKey } from "./cite-key";
import { decodeEntities, stripSafeTags } from "./html-decode";

export function libraryDir(projectPath: string): string {
  return path.join(projectPath, "papers");
}

function ensureLibraryDir(projectPath: string): string {
  const dir = libraryDir(projectPath);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  return dir;
}

export function listLibrary(projectPath: string): PaperArtifact[] {
  const dir = libraryDir(projectPath);
  if (!existsSync(dir)) return [];
  const out: PaperArtifact[] = [];
  for (const f of readdirSync(dir)) {
    if (!f.endsWith(".json")) continue;
    const full = path.join(dir, f);
    try {
      const raw = readFileSync(full, "utf8");
      const obj = JSON.parse(raw);
      if (obj && obj._artifact === "paper") out.push(obj as PaperArtifact);
    } catch {
      /* skip unreadable / malformed */
    }
  }
  // Newest saved first
  out.sort((a, b) => (b.saved_at ?? "").localeCompare(a.saved_at ?? ""));
  return out;
}

export function savePaper(projectPath: string, paper: PaperArtifact): string {
  ensureLibraryDir(projectPath);
  const target = path.join(libraryDir(projectPath), `${paper.id}.json`);
  assertWithinProject(target, projectPath);
  const root = organonRoot();
  const relativePath = path.relative(root, target);

  // Phase 3 (fix-sprint): compute cite_key now if the artifact doesn't carry
  // one. Read every existing paper in this library and exclude this paper's
  // own current cite_key (so re-saving the same paper is idempotent — it
  // doesn't promote itself from "Smith2026" to "Smith2026b").
  let cite_key: string | null | undefined = paper.cite_key ?? null;
  if (!cite_key) {
    const siblings = listLibrary(projectPath).filter((p) => p.id !== paper.id);
    const existingKeys = new Set<string>();
    for (const s of siblings) {
      if (s.cite_key) existingKeys.add(s.cite_key);
    }
    cite_key = paperToCiteKey(paper, existingKeys);
  }

  // Phase 3 (fix-sprint): decode HTML entities in journal/abstract once at
  // persist time. Some sources (PubMed XML especially) ship `&amp;`,
  // `&lt;sub&gt;`, `&#x2014;` etc. Letting them through corrupts
  // BibTeX export and the draft preview equally.
  const journal = paper.journal != null
    ? stripSafeTags(decodeEntities(paper.journal))
    : paper.journal;
  const abstract = stripSafeTags(decodeEntities(paper.abstract));

  const stamped: PaperArtifact = {
    ...paper,
    journal,
    abstract,
    cite_key,
    saved_at: paper.saved_at ?? new Date().toISOString(),
    library_path: relativePath,
  };

  // Atomic write: temp file → rename.
  const tmp = target + ".tmp";
  writeFileSync(tmp, JSON.stringify(stamped, null, 2), "utf8");
  renameSync(tmp, target);
  return relativePath;
}

export function isSaved(projectPath: string, paperId: string): boolean {
  return existsSync(path.join(libraryDir(projectPath), `${paperId}.json`));
}

export function removePaper(projectPath: string, paperId: string): boolean {
  const target = path.join(libraryDir(projectPath), `${paperId}.json`);
  if (!existsSync(target)) return false;
  unlinkSync(target);
  return true;
}

/**
 * Phase 38 (v1.4) — F1 group-by-search-batch.
 *
 * Save a list of papers stamped with shared batch metadata so the
 * library panel can group them visually + offer a single delete-batch
 * affordance. Returns each paper's library_path.
 *
 * Pre-existing entries with the same id are overwritten (re-save is
 * idempotent — same shape as savePaper). The batch metadata cascades
 * onto every entry in the call.
 */
export function addPapersToLibrary(
  projectPath: string,
  papers: PaperArtifact[],
  batchMeta: { batch_id: string; query: string; added_at: string },
): string[] {
  return papers.map((p) =>
    savePaper(projectPath, {
      ...p,
      search_batch_id: batchMeta.batch_id,
      search_batch_query: batchMeta.query,
      search_batch_added_at: batchMeta.added_at,
    }),
  );
}

/**
 * Phase 38 (v1.4) — F1 batch delete.
 *
 * Removes every library entry stamped with the given batch_id. Returns
 * the list of removed paper ids.
 */
export function removeBatchFromLibrary(
  projectPath: string,
  batchId: string,
): string[] {
  const removed: string[] = [];
  for (const p of listLibrary(projectPath)) {
    if (p.search_batch_id === batchId) {
      if (removePaper(projectPath, p.id)) removed.push(p.id);
    }
  }
  return removed;
}
