"use client";

import { useEffect, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import type { PaperArtifact } from "@/lib/artifacts/types";
import { cn } from "@/lib/cn";

export type PaperDetailDrawerProps = {
  paper: PaperArtifact | null;
  isSaved: boolean;
  onClose: () => void;
  onSave: (paper: PaperArtifact) => void;
  onUnsave: (paper: PaperArtifact) => void;
  /** When provided, enables the "Generate hypothesis from this paper" action. */
  onGenerateHypothesis?: (paper: PaperArtifact) => void;
};

const TABS = [
  { id: "abstract", label: "Abstract", phase: null as string | null },
  { id: "citations", label: "Citations", phase: "Phase 6" },
  { id: "references", label: "References", phase: "Phase 6" },
  { id: "notes", label: "Notes", phase: "Phase 5" },
];

export function PaperDetailDrawer({
  paper,
  isSaved,
  onClose,
  onSave,
  onUnsave,
  onGenerateHypothesis,
}: PaperDetailDrawerProps) {
  const [active, setActive] = useState("abstract");

  useHotkeys("esc", () => paper && onClose(), { enableOnFormTags: true }, [paper]);

  useEffect(() => {
    if (paper) setActive("abstract");
  }, [paper?.id]);

  if (!paper) return null;

  return (
    <>
      <div
        className="fixed inset-0 bg-black/50 z-30 transition-opacity"
        onClick={onClose}
        aria-hidden
      />
      <aside
        className="fixed top-0 right-0 h-full w-full max-w-2xl bg-bg-elev border-l border-border z-40 flex flex-col shadow-2xl drawer-open"
        role="dialog"
        aria-label={paper.title}
      >
        <header className="px-6 py-4 border-b border-border-dim flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h2 className="text-lg font-semibold leading-snug">{paper.title}</h2>
            <div className="text-xs text-text-dim mt-1">
              {paper.authors.slice(0, 6).join(", ")}
              {paper.authors.length > 6 ? " et al." : ""}
            </div>
            <div className="text-xs text-text-muted mt-2 flex flex-wrap gap-2 mono">
              {paper.year > 0 && <span>{paper.year}</span>}
              {paper.journal && <span>·  {paper.journal}</span>}
              {paper.citation_count != null && (
                <span>·  {paper.citation_count.toLocaleString()} citations</span>
              )}
              {paper.source_ids.doi && (
                <a
                  href={`https://doi.org/${paper.source_ids.doi}`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-accent hover:underline"
                >
                  · doi:{paper.source_ids.doi}
                </a>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-text-dim hover:text-text px-2 py-1 mono text-xs"
            aria-label="Close"
          >
            ✕ esc
          </button>
        </header>

        <nav className="px-6 border-b border-border-dim flex gap-1">
          {TABS.map((t) => {
            const isActive = active === t.id;
            const isDisabled = !!t.phase;
            return (
              <button
                key={t.id}
                onClick={() => !isDisabled && setActive(t.id)}
                disabled={isDisabled}
                title={t.phase ? `Coming in ${t.phase}` : undefined}
                className={cn(
                  "px-3 py-2 text-xs mono uppercase tracking-wider transition border-b-2 -mb-[2px]",
                  isActive
                    ? "border-accent text-accent"
                    : isDisabled
                      ? "border-transparent text-text-muted cursor-not-allowed"
                      : "border-transparent text-text-dim hover:text-text",
                )}
              >
                {t.label}
                {t.phase && <span className="ml-1 opacity-50">·{t.phase}</span>}
              </button>
            );
          })}
        </nav>

        <div className="flex-1 overflow-auto px-6 py-5">
          {active === "abstract" && (
            <div className="prose prose-invert max-w-none">
              <p className="text-sm text-text leading-relaxed whitespace-pre-wrap">
                {paper.abstract || <em className="text-text-muted">No abstract available.</em>}
              </p>
            </div>
          )}
        </div>

        <footer className="px-6 py-4 border-t border-border-dim flex items-center gap-3 flex-wrap">
          <button
            onClick={() => (isSaved ? onUnsave(paper) : onSave(paper))}
            className={cn(
              "px-4 py-2 border rounded mono text-xs uppercase tracking-wider transition",
              isSaved
                ? "border-good text-good hover:border-danger hover:text-danger"
                : "border-accent text-accent hover:bg-accent hover:text-bg",
            )}
          >
            {isSaved ? "Saved · click to remove" : "Save to library"}
          </button>
          <a
            href={paper.url}
            target="_blank"
            rel="noreferrer"
            className="px-4 py-2 border border-border rounded mono text-xs uppercase tracking-wider text-text-dim hover:text-text transition"
          >
            Open source ↗
          </a>
          {onGenerateHypothesis && (
            <button
              onClick={() => onGenerateHypothesis(paper)}
              className="px-4 py-2 border border-accent rounded mono text-xs uppercase tracking-wider text-accent hover:bg-accent hover:text-bg transition"
            >
              Generate hypothesis ↗
            </button>
          )}
          <div className="ml-auto flex items-center gap-2">
            <ActionDisabled label="Cite in draft" phase="Phase 5" />
          </div>
        </footer>
      </aside>
    </>
  );
}

function ActionDisabled({ label, phase }: { label: string; phase: string }) {
  return (
    <span
      title={`Coming in ${phase}`}
      className="px-3 py-2 border border-border-dim rounded mono text-[11px] uppercase tracking-wider text-text-muted cursor-not-allowed"
    >
      {label} <span className="opacity-50">·{phase}</span>
    </span>
  );
}

/** Backward-compat alias for /lit imports during the Phase 2 lift. */
export { PaperDetailDrawer as PaperDetail };
