// Phase 22 (v1.1+) — Whole-paper-aware AI editing context envelope (DR-6).
//
// Builds the bounded context payload the chat route forwards to
// sci-writing in edit-with-chat mode. Caps live at the dashboard
// boundary (NOT inside the skill) so the dashboard owns the
// trade-off between context richness and prompt length.
//
// v1.1 caps (per brief §10.3):
//   - max ~2000 chars per sibling section
//   - max 6 linked papers (most-cited / most-relevant first; v1.1
//     just slices in original order — v1.2 can re-rank).

import type { PaperArtifact, SectionDraftArtifact } from "../artifacts/types";

export const MAX_SIBLING_CHARS = 2000;
export const MAX_LINKED_PAPERS = 6;
export const MAX_SIBLINGS = 16;

// Phase 27 (v1.2) — multi-turn conversation caps. The workspace
// forwards the last MAX_PRIOR_TURNS turns of the in-memory transcript
// (with each diff body summarised to ≤MAX_DIFF_SUMMARY_CHARS) so the
// skill can see the conversation arc without blowing the context
// budget. Caps gate at the dashboard boundary, NOT inside the skill.
export const MAX_PRIOR_TURNS = 6;
export const MAX_DIFF_SUMMARY_CHARS = 400;

// Phase 29 (v1.2) — file-tree referenced files in the chat envelope.
// Researcher-pinned files (sections / figures / stat-results / papers /
// manuscripts) get bounded excerpts forwarded so the skill can quote
// them. Caps gate at the dashboard boundary; the kind discriminator
// is required so the route can pick the right store.
export const MAX_REFERENCED_FILES = 4;
export const MAX_REFERENCED_EXCERPT_CHARS = 1500;

export type ReferencedFileKind =
  | "section"
  | "figure"
  | "stat-result"
  | "paper"
  | "manuscript";

export type ReferencedFile = {
  kind: ReferencedFileKind;
  id: string;
  label: string;
  content_excerpt: string;
};

export type ContextSelection = {
  start: number;
  end: number;
  text: string;
};

export type PriorTurn = {
  prompt: string;
  applied: boolean;
  diff_summary?: string;
};

export type ContextEnvelope = {
  active: {
    section_id: string;
    section_type: string;
    content_md: string;
  };
  selection: ContextSelection | null;
  siblings: Array<{
    section_id: string;
    section_type: string;
    content_md: string;
  }>;
  linked_papers: Array<{
    cite_key: string;
    title: string;
    authors: string[];
  }>;
  prior_turns?: PriorTurn[];
  referenced_files?: ReferencedFile[];
};

export function buildContext(
  section: SectionDraftArtifact,
  siblings: SectionDraftArtifact[],
  library: PaperArtifact[],
  selection?: ContextSelection | null,
  priorTurns?: PriorTurn[] | null,
  referencedFiles?: ReferencedFile[] | null,
): ContextEnvelope {
  // Phase 27: cap the prior_turns slice to the LAST MAX_PRIOR_TURNS
  // turns + trim each diff_summary at MAX_DIFF_SUMMARY_CHARS. The
  // panel keeps the full transcript in-memory; only the recent +
  // summarised tail goes to the skill.
  const cappedPriorTurns: PriorTurn[] | undefined = priorTurns
    ? priorTurns.slice(-MAX_PRIOR_TURNS).map((t) => ({
        prompt: t.prompt,
        applied: !!t.applied,
        diff_summary: t.diff_summary
          ? t.diff_summary.slice(0, MAX_DIFF_SUMMARY_CHARS)
          : undefined,
      }))
    : undefined;
  // Phase 29 — cap referenced_files at MAX_REFERENCED_FILES; trim
  // each content_excerpt at MAX_REFERENCED_EXCERPT_CHARS. Empty
  // input passes through as undefined so v1.1 single-turn callers
  // see the same envelope shape.
  const cappedReferencedFiles: ReferencedFile[] | undefined = referencedFiles
    ? referencedFiles.slice(0, MAX_REFERENCED_FILES).map((r) => ({
        kind: r.kind,
        id: r.id,
        label: r.label,
        content_excerpt: (r.content_excerpt ?? "").slice(
          0,
          MAX_REFERENCED_EXCERPT_CHARS,
        ),
      }))
    : undefined;
  return {
    active: {
      section_id: section.section_id,
      section_type: String(section.section_type),
      // Full content of the active section — the whole point is the
      // skill sees the section being edited in full.
      content_md: section.content_md,
    },
    selection: selection ?? null,
    siblings: siblings.slice(0, MAX_SIBLINGS).map((s) => ({
      section_id: s.section_id,
      section_type: String(s.section_type),
      content_md: (s.content_md ?? "").slice(0, MAX_SIBLING_CHARS),
    })),
    linked_papers: library.slice(0, MAX_LINKED_PAPERS).map((p) => ({
      cite_key: p.cite_key ?? p.id,
      title: p.title ?? "(untitled)",
      authors: Array.isArray(p.authors) ? p.authors.slice(0, 6) : [],
    })),
    ...(cappedPriorTurns && cappedPriorTurns.length > 0
      ? { prior_turns: cappedPriorTurns }
      : {}),
    ...(cappedReferencedFiles && cappedReferencedFiles.length > 0
      ? { referenced_files: cappedReferencedFiles }
      : {}),
  };
}
