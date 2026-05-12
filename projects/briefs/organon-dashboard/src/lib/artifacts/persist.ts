import { savePaper } from "../lit/library";
import { saveCritique } from "../hypothesis/critiques";
import { getHypothesis, patchHypothesis, saveHypothesis } from "../hypothesis/store";
import { savePreview } from "../data/files";
import { saveResult } from "../results/store";
import { saveFigure } from "../figures/store";
import { saveSection } from "../draft/store";
import type { Artifact, HypothesisArtifact, PersonaCritiqueArtifact } from "./types";

/**
 * Persist an artifact to disk under its project's canonical path.
 * Returns the relative-to-organon-root path it was written to, or null if no
 * persister is registered for this artifact type yet.
 */
export function persistArtifact(projectPath: string, artifact: Artifact): string | null {
  switch (artifact._artifact) {
    case "paper":
      return savePaper(projectPath, artifact);
    case "project":
      return null;
    case "hypothesis":
      return persistHypothesis(projectPath, artifact);
    case "persona-critique":
      return persistCritique(projectPath, artifact);
    case "dataframe":
      return savePreview(projectPath, artifact);
    case "stat-result":
      return saveResult(projectPath, artifact);
    case "figure":
      return saveFigure(projectPath, artifact);
    case "section-draft":
      return saveSection(projectPath, artifact);
    case "section-diff":
      // Transient — UI-only. Routes consume via SSE without persisting.
      return null;
    default: {
      const tag = (artifact as { _artifact?: string })._artifact ?? "unknown";
      console.warn(
        `[artifacts] No persister for _artifact=${tag}; ignoring (Phase 5)`,
      );
      return null;
    }
  }
}

function persistHypothesis(projectPath: string, hyp: HypothesisArtifact): string {
  const existing = getHypothesis(projectPath, hyp.id);
  if (!existing) return saveHypothesis(projectPath, hyp);
  // Merge skill-emitted update onto the existing record. The skill is the
  // authority on synthesis_text, status transitions open → synthesized,
  // critique_files, council_confidence, etc. The dashboard's user-driven
  // fields (notes, tags) survive.
  const merged: HypothesisArtifact = {
    ...existing,
    ...hyp,
    notes: hyp.notes ?? existing.notes,
    tags: hyp.tags ?? existing.tags,
    created_at: existing.created_at,
  };
  return saveHypothesis(projectPath, merged);
}

function persistCritique(
  projectPath: string,
  critique: PersonaCritiqueArtifact,
): string {
  const path = saveCritique(projectPath, critique);
  // Link the sidecar into the parent hypothesis record.
  const parent = getHypothesis(projectPath, critique.hypothesis_id);
  if (parent) {
    const set = new Set(parent.critique_files ?? []);
    set.add(path);
    patchHypothesis(projectPath, critique.hypothesis_id, {
      critique_files: Array.from(set),
    });
  }
  return path;
}
