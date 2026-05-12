"use client";

import type { PaperArtifact } from "@/lib/artifacts/types";
import { cn } from "@/lib/cn";

export type LinkedPapersListProps = {
  paperIds: string[];
  library: PaperArtifact[];
  onOpenPaper?: (paper: PaperArtifact) => void;
};

export function LinkedPapersList({ paperIds, library, onOpenPaper }: LinkedPapersListProps) {
  if (paperIds.length === 0) {
    return (
      <div className="text-xs text-text-muted italic">No linked papers.</div>
    );
  }
  const byId = new Map(library.map((p) => [p.id, p]));
  return (
    <div className="flex flex-wrap gap-1.5">
      {paperIds.map((id) => {
        const paper = byId.get(id);
        if (!paper) {
          return (
            <span
              key={id}
              title="Removed from library"
              className="inline-flex items-center mono text-[10px] uppercase tracking-wider px-2 py-0.5 border border-border-dim rounded text-text-muted line-through"
            >
              {id}
            </span>
          );
        }
        const label = `${paper.authors[0]?.split(" ")[0] ?? paper.id}${paper.year > 0 ? " " + paper.year : ""}`;
        return (
          <button
            key={id}
            onClick={() => onOpenPaper?.(paper)}
            disabled={!onOpenPaper}
            title={paper.title}
            className={cn(
              "inline-flex items-center mono text-[10px] uppercase tracking-wider px-2 py-0.5 border border-accent text-accent rounded transition",
              onOpenPaper ? "hover:bg-accent hover:text-bg" : "cursor-default",
            )}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
