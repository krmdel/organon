"use client";

import type { FigureArtifact } from "@/lib/artifacts/types";

export type CaptionCardProps = {
  figure: FigureArtifact;
  onLock: () => void;
  onRegenerate: () => void;
  busy?: boolean;
};

export function CaptionCard({ figure, onLock, onRegenerate, busy }: CaptionCardProps) {
  const hasCaption = !!(figure.caption && figure.alt_text);
  return (
    <div className="border border-border-dim rounded bg-bg-elev px-4 py-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="mono text-[10px] uppercase tracking-wider text-text-muted">
            Caption · v{figure.version}
            {figure.locked && <span className="ml-2 text-good">● locked</span>}
          </div>
          <div className="mt-1 text-sm text-text">
            {hasCaption ? figure.caption : "Not generated yet."}
          </div>
          {hasCaption && (
            <div className="mt-2">
              <div className="mono text-[10px] uppercase tracking-wider text-text-muted">Alt text</div>
              <div className="text-xs text-text-dim mt-0.5">{figure.alt_text}</div>
            </div>
          )}
        </div>
        <div className="flex flex-col gap-1.5 shrink-0">
          {!figure.locked ? (
            <button
              type="button"
              onClick={onLock}
              disabled={busy}
              className="text-xs mono uppercase tracking-wider px-3 py-1 border border-accent text-accent hover:bg-accent-faint rounded disabled:opacity-50"
            >
              {busy ? "Locking…" : "Lock + caption"}
            </button>
          ) : (
            <button
              type="button"
              onClick={onRegenerate}
              disabled={busy}
              className="text-xs mono uppercase tracking-wider px-3 py-1 border border-border-dim text-text-dim hover:text-text rounded disabled:opacity-50"
            >
              Re-caption
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
