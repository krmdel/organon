"use client";

import { useEffect, useRef, useState } from "react";
import type { PaperArtifact } from "@/lib/artifacts/types";
import { PaperPicker } from "./paper-picker";
import { getCrossRouteQuery } from "@/lib/cross-route-query/store";

export type ClaimFormProps = {
  initialClaim?: string;
  initialPaperIds?: string[];
  library: PaperArtifact[];
  loading?: boolean;
  onSubmit: (params: { claim: string; paper_ids: string[] }) => Promise<void> | void;
  onCancel?: () => void;
  // Phase 11 (v1.0.1) — emits every keystroke so the workspace can persist
  // the WIP claim to localStorage. Optional so the prop stays backward
  // compatible with anywhere ClaimForm renders without persistence.
  onClaimChange?: (claim: string) => void;
  /**
   * Phase 40 (v1.4) — F3: project slug enables cross-route pre-fill
   * from the most recent /lit query. Optional so the surface stays
   * back-compatible.
   */
  project?: string;
};

export function ClaimForm({
  initialClaim = "",
  initialPaperIds = [],
  library,
  loading,
  onSubmit,
  onCancel,
  onClaimChange,
  project,
}: ClaimFormProps) {
  const [claim, setClaim] = useState(initialClaim);
  const [paperIds, setPaperIds] = useState<string[]>(initialPaperIds);
  // Phase 40 (v1.4) — F3: caption shown above the textarea when the
  // pre-fill came from a cross-route lit query. Cleared when the user
  // types over it.
  const [crossRouteHint, setCrossRouteHint] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const crossRoutePulledRef = useRef(false);

  useEffect(() => {
    setClaim(initialClaim);
  }, [initialClaim]);
  useEffect(() => {
    setPaperIds(initialPaperIds);
  }, [initialPaperIds.join("|")]);

  // Phase 40 (v1.4) — F3: pre-fill from /lit cross-route query on
  // first paint when the textarea is empty. Single-fire ref so a
  // re-render doesn't re-pull. Never overwrites user-typed content.
  useEffect(() => {
    if (crossRoutePulledRef.current) return;
    if (!project) return;
    const stored = getCrossRouteQuery(project);
    // Pre-fill ONLY when claim.trim().length === 0 — never overwrite
    // user-typed content. The crossRoutePulledRef latches once we
    // either pre-fill OR detect non-empty content so subsequent
    // re-renders don't double-trigger.
    if (claim.trim().length === 0) {
      if (stored && stored.query.trim().length > 0) {
        crossRoutePulledRef.current = true;
        setClaim(stored.query);
        setCrossRouteHint(`from lit search · "${stored.query.slice(0, 60)}${stored.query.length > 60 ? "…" : ""}"`);
      }
    } else {
      crossRoutePulledRef.current = true;
    }
  }, [project, claim]);

  const canSubmit = claim.trim().length > 0 && !loading;

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!canSubmit) return;
    onSubmit({ claim: claim.trim(), paper_ids: paperIds });
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="mono text-[10px] uppercase tracking-wider text-text-muted block mb-1">
          Claim
        </label>
        {crossRouteHint && (
          <div
            data-cross-route-hint
            className="mono text-[10px] text-text-muted mb-1"
            title="Pre-filled from your most recent /lit search"
          >
            ↳ {crossRouteHint}
          </div>
        )}
        <textarea
          ref={textareaRef}
          value={claim}
          onChange={(e) => {
            setClaim(e.target.value);
            onClaimChange?.(e.target.value);
            if (crossRouteHint) setCrossRouteHint(null);
          }}
          onKeyDown={onKeyDown}
          rows={3}
          placeholder="State the hypothesis as a falsifiable claim. e.g. GLP-1 agonists reduce CV mortality at 18-month follow-up."
          className="w-full bg-bg-elev border border-border-dim rounded px-3 py-2 text-sm leading-relaxed outline-none focus:border-accent transition resize-y"
          disabled={loading}
        />
      </div>

      <div>
        <label className="mono text-[10px] uppercase tracking-wider text-text-muted block mb-1">
          Linked papers · {paperIds.length} selected
        </label>
        <PaperPicker library={library} value={paperIds} onChange={setPaperIds} />
        {paperIds.length === 0 && (
          <p className="mono text-[10px] text-text-muted mt-1">
            No papers selected — council can still run, but supporting evidence will be empty.
          </p>
        )}
      </div>

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={!canSubmit}
          className={
            !canSubmit
              ? "px-4 py-2 border border-border rounded mono text-xs uppercase tracking-wider text-text-muted cursor-not-allowed"
              : "px-4 py-2 border border-accent rounded mono text-xs uppercase tracking-wider text-accent hover:bg-accent hover:text-bg transition"
          }
        >
          {loading ? "Generating…" : "Generate via council ↗"}
        </button>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            disabled={!loading}
            className="px-3 py-2 mono text-xs uppercase tracking-wider text-text-dim hover:text-text disabled:text-text-muted disabled:cursor-not-allowed"
          >
            Cancel
          </button>
        )}
        <span className="mono text-[10px] text-text-muted ml-auto">⌘ + ↵ to submit</span>
      </div>
    </form>
  );
}
