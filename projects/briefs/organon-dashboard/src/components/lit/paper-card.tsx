"use client";

import type { PaperArtifact } from "@/lib/artifacts/types";
import { cn } from "@/lib/cn";

export type PaperCardProps = {
  paper: PaperArtifact;
  isSaved: boolean;
  isFocused: boolean;
  onOpen: (paper: PaperArtifact) => void;
  onSave: (paper: PaperArtifact) => void;
  onUnsave: (paper: PaperArtifact) => void;
};

const SOURCE_BADGES: Record<string, string> = {
  pubmed: "PubMed",
  arxiv: "arXiv",
  openalex: "OpenAlex",
  semanticscholar: "S2",
  paperclip: "Paperclip",
};

export function PaperCard({ paper, isSaved, isFocused, onOpen, onSave, onUnsave }: PaperCardProps) {
  const authors = paper.authors.slice(0, 3).join(", ") + (paper.authors.length > 3 ? " et al." : "");
  const abstractPreview = (paper.abstract || "").slice(0, 240).replace(/\s+/g, " ").trim();
  const more = (paper.abstract || "").length > 240;

  return (
    <article
      className={cn(
        "border border-border-dim rounded p-4 mb-3 transition",
        isFocused && "border-accent",
        !isFocused && "hover:border-border",
      )}
    >
      <div className="flex items-start justify-between gap-4 mb-2">
        <button
          onClick={() => onOpen(paper)}
          className="text-left text-text font-semibold hover:text-accent transition leading-snug"
        >
          {paper.title}
        </button>
        <button
          onClick={() => (isSaved ? onUnsave(paper) : onSave(paper))}
          className={cn(
            "shrink-0 px-3 py-1 text-xs mono uppercase tracking-wider border rounded transition",
            isSaved
              ? "border-good text-good hover:border-danger hover:text-danger"
              : "border-border text-text-dim hover:border-accent hover:text-accent",
          )}
        >
          {isSaved ? "Saved" : "Save"}
        </button>
      </div>
      <div className="text-xs text-text-dim mb-2">{authors || "Unknown author"}</div>
      <div className="flex items-center gap-2 flex-wrap mb-3 text-xs">
        {paper.year > 0 && <span className="text-text-muted mono">{paper.year}</span>}
        {paper.journal && <span className="text-text-muted">·  {paper.journal}</span>}
        {paper.citation_count != null && (
          <span className="text-text-muted mono">·  {paper.citation_count.toLocaleString()} cites</span>
        )}
        {/* Phase 47 (v1.6) — F10: relevance confidence chip. Hides when
            relevance_score is null/undefined (legacy / non-search reads). */}
        {typeof paper.relevance_score === "number" && (
          <span
            data-relevance-chip
            className={cn(
              "px-1.5 py-0.5 border rounded mono text-[10px] uppercase tracking-wider",
              paper.relevance_score >= 0.6
                ? "border-good text-good"
                : paper.relevance_score >= 0.4
                  ? "border-border text-text-muted"
                  : "border-border-dim text-text-muted/70",
            )}
            title={
              paper.relevance_breakdown
                ? `Title overlap ${(paper.relevance_breakdown.title * 100).toFixed(0)}% · Abstract overlap ${(paper.relevance_breakdown.abstract * 100).toFixed(0)}%`
                : "Relevance score"
            }
          >
            ● {paper.relevance_score.toFixed(2)}
          </span>
        )}
        {paper.sources.map((s) => (
          <span
            key={s}
            className="px-1.5 py-0.5 border border-border-dim rounded mono text-[10px] uppercase tracking-wider text-text-dim"
          >
            {SOURCE_BADGES[s] ?? s}
          </span>
        ))}
        {paper.code?.available && (
          <a
            href={paper.code.github_url}
            target="_blank"
            rel="noreferrer"
            className="px-1.5 py-0.5 border border-good text-good rounded mono text-[10px] uppercase tracking-wider hover:bg-good hover:text-bg transition"
          >
            Code ✓
          </a>
        )}
      </div>
      {abstractPreview && (
        <p className="text-sm text-text-dim leading-relaxed">
          {abstractPreview}
          {more && (
            <button
              onClick={() => onOpen(paper)}
              className="ml-2 text-accent hover:underline text-xs"
            >
              more
            </button>
          )}
        </p>
      )}
    </article>
  );
}
