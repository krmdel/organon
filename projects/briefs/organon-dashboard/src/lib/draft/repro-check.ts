/**
 * Phase 54 (v2.0) — Reproducibility checks.
 *
 * Pure resolver that walks a manuscript + its sections + the project's
 * stores and reports whether every cite_key, fig_id, and linked_*_id
 * still resolves. Designed to fire BEFORE export so a researcher can
 * see what would silently degrade in the rendered output.
 *
 * Severity ladder:
 *   - "pass": every reference resolves.
 *   - "warn": linkage array points at a deleted artifact (won't break
 *     export, but shows up as missing in the manuscript subset).
 *   - "fail": cite_key or fig_id in section text doesn't resolve
 *     (export would emit unresolved-cite / unresolved-fig markers).
 *
 * The report's `passed` field is true iff no check has verdict "fail";
 * "warn" findings are advisory.
 */

import type {
  FigureArtifact,
  HypothesisArtifact,
  PaperArtifact,
  SectionDraftArtifact,
} from "../artifacts/types";
import type { ManuscriptMeta } from "./store";
import { extractRefsSequence } from "./parse";

export type ReproCheckVerdict = "pass" | "warn" | "fail";

export interface ReproCheckResult {
  name:
    | "cite-keys-resolve"
    | "fig-ids-resolve"
    | "linked-papers-exist"
    | "linked-figures-exist"
    | "linked-hypotheses-exist"
    | "linked-datasets-exist";
  label: string;
  verdict: ReproCheckVerdict;
  detail: string[];
}

export interface ReproCheckReport {
  manuscript_slug: string;
  passed: boolean;
  ran_at: string;
  checks: ReproCheckResult[];
}

export interface ReproCheckInput {
  manuscript: ManuscriptMeta;
  sections: SectionDraftArtifact[];
  library: PaperArtifact[];
  figures: FigureArtifact[];
  hypotheses: HypothesisArtifact[];
  datasets: { id: string }[];
}

export function runReproCheck(input: ReproCheckInput): ReproCheckReport {
  const { manuscript, sections, library, figures, hypotheses, datasets } = input;

  // Walk sections in manuscript order so the cite/fig sequence matches
  // the export numbering.
  const orderedSections = manuscript.ordering
    .map((id) => sections.find((s) => s.section_id === id))
    .filter((s): s is SectionDraftArtifact => Boolean(s));
  const refs = extractRefsSequence(orderedSections.map((s) => ({ content_md: s.content_md })));

  const knownCiteKeys = new Set<string>();
  for (const p of library) {
    if (p.cite_key) knownCiteKeys.add(p.cite_key);
    if (p.id) knownCiteKeys.add(p.id);
  }
  const knownFigIds = new Set(figures.map((f) => f.id));
  const knownPaperIds = new Set(library.map((p) => p.id));
  const knownHypIds = new Set(hypotheses.map((h) => h.id));
  const knownDatasetIds = new Set(datasets.map((d) => d.id));

  const missingCites = refs.citations.filter((k) => !knownCiteKeys.has(k));
  const missingFigs = refs.figures.filter((k) => !knownFigIds.has(k));

  const linkedPaperIds = manuscript.linked_paper_ids ?? [];
  const linkedFigIds = manuscript.linked_figure_ids ?? [];
  const linkedHypIds = manuscript.linked_hypothesis_ids ?? [];
  const linkedDsIds = manuscript.linked_dataset_ids ?? [];

  const lostPapers = linkedPaperIds.filter((id) => !knownPaperIds.has(id));
  const lostFigs = linkedFigIds.filter((id) => !knownFigIds.has(id));
  const lostHyps = linkedHypIds.filter((id) => !knownHypIds.has(id));
  const lostDs = linkedDsIds.filter((id) => !knownDatasetIds.has(id));

  const checks: ReproCheckResult[] = [
    {
      name: "cite-keys-resolve",
      label: "Cite keys resolve to library entries",
      verdict: missingCites.length === 0 ? "pass" : "fail",
      detail: missingCites,
    },
    {
      name: "fig-ids-resolve",
      label: "Figure refs resolve to figures",
      verdict: missingFigs.length === 0 ? "pass" : "fail",
      detail: missingFigs,
    },
    {
      name: "linked-papers-exist",
      label: "Linked papers still in library",
      verdict: lostPapers.length === 0 ? "pass" : "warn",
      detail: lostPapers,
    },
    {
      name: "linked-figures-exist",
      label: "Linked figures still in store",
      verdict: lostFigs.length === 0 ? "pass" : "warn",
      detail: lostFigs,
    },
    {
      name: "linked-hypotheses-exist",
      label: "Linked hypotheses still in store",
      verdict: lostHyps.length === 0 ? "pass" : "warn",
      detail: lostHyps,
    },
    {
      name: "linked-datasets-exist",
      label: "Linked datasets still in store",
      verdict: lostDs.length === 0 ? "pass" : "warn",
      detail: lostDs,
    },
  ];

  return {
    manuscript_slug: manuscript.slug,
    passed: checks.every((c) => c.verdict !== "fail"),
    ran_at: new Date().toISOString(),
    checks,
  };
}
