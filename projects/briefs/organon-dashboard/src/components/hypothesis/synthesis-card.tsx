"use client";

import { useMemo, useState } from "react";
import type { HypothesisArtifact } from "@/lib/artifacts/types";
import { StatusBadge } from "./status-badge";

export type SynthesisCardProps = {
  hypothesis: HypothesisArtifact;
  onMarkSupported: () => void;
  onMarkRefuted: () => void;
  onArchive: () => void;
  /**
   * Phase 13c (v1.0.1) — H-7 apply paper-set recommendation.
   * Caller owns the POST + workspace state refresh; we just emit the
   * intent (drop ids + retain ids) once the user confirms.
   */
  onApplyRecommendation?: (drop: string[], retain: string[]) => Promise<void>;
};

// Phase 13c (v1.0.1) — H-6 structured synthesis render.
//
// The skill MAY emit synthesis_text as a JSON object carrying:
//   - proposed_experiment.stages[]   (numbered, collapsible)
//   - papers_to_drop_from_linked_set (string[])
//   - papers_to_retain_as_evidence   (string[])
//   - reconciled_claim               (free-text fallback)
//
// Permissive parse: unknown shapes silently fall back to the raw-text
// render so a misbehaving skill never blanks the synthesis card.
type ProposedExperimentStage = {
  title?: string;
  description?: string;
};
type Synthesis = {
  reconciled_claim?: string;
  proposed_experiment?: { stages?: ProposedExperimentStage[] };
  papers_to_drop_from_linked_set?: string[];
  papers_to_retain_as_evidence?: string[];
};

function parseSynthesis(text: string | null | undefined): Synthesis | null {
  if (!text) return null;
  const trimmed = text.trim();
  if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) return null;
  try {
    const obj = JSON.parse(trimmed) as unknown;
    if (!obj || typeof obj !== "object" || Array.isArray(obj)) return null;
    return obj as Synthesis;
  } catch {
    return null;
  }
}

function asStringArray(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  return v.filter((x): x is string => typeof x === "string");
}

export function SynthesisCard({
  hypothesis,
  onMarkSupported,
  onMarkRefuted,
  onArchive,
  onApplyRecommendation,
}: SynthesisCardProps) {
  const [stagesOpen, setStagesOpen] = useState(true);
  const [applying, setApplying] = useState(false);
  const [applyError, setApplyError] = useState<string | null>(null);

  const synthesis = useMemo(
    () => parseSynthesis(hypothesis.synthesis_text),
    [hypothesis.synthesis_text],
  );

  if (hypothesis.status === "open") {
    return (
      <div className="border border-dashed border-border-dim rounded p-6 text-center text-sm text-text-muted">
        Synthesis appears here once you click <span className="text-accent">Reconcile</span>.
        Critiques must be present.
      </div>
    );
  }

  // Phase 13c — extract structured fields. proposed_experiment may live
  // in either the parsed synthesis JSON OR in the artifact's
  // experiment_design Record (back-compat with skill emits that use the
  // legacy field). Prefer the parsed shape.
  const stages = synthesis?.proposed_experiment?.stages ?? [];
  const designStages = (() => {
    if (stages.length > 0) return stages;
    const d = hypothesis.experiment_design;
    if (!d || typeof d !== "object" || Array.isArray(d)) return [];
    const inner = (d as Record<string, unknown>).proposed_experiment;
    if (!inner || typeof inner !== "object" || Array.isArray(inner)) return [];
    const innerStages = (inner as Record<string, unknown>).stages;
    if (!Array.isArray(innerStages)) return [];
    return innerStages.filter(
      (s): s is ProposedExperimentStage =>
        typeof s === "object" && s !== null && !Array.isArray(s),
    );
  })();
  const renderStages: ProposedExperimentStage[] = stages.length > 0 ? stages : designStages;

  const drop = asStringArray(synthesis?.papers_to_drop_from_linked_set);
  const retain = asStringArray(synthesis?.papers_to_retain_as_evidence);
  const applyDisabled = drop.length === 0 && retain.length === 0;

  // Reconciled claim — prefer the parsed JSON's `reconciled_claim`,
  // fall back to the raw synthesis_text when it is plain prose.
  const reconciled =
    synthesis?.reconciled_claim ??
    (synthesis ? "" : hypothesis.synthesis_text ?? "(no synthesis text emitted by the skill)");

  const openQs = hypothesis.open_questions ?? [];

  // Legacy free-text experiment_design fallback (when not structured).
  const legacyDesignBlock =
    renderStages.length === 0 && hypothesis.experiment_design ? hypothesis.experiment_design : null;

  const handleApply = async () => {
    if (!onApplyRecommendation || applyDisabled) return;
    if (typeof window !== "undefined") {
      const ok = window.confirm(
        `Apply: drop ${drop.length}, retain ${retain.length}? This updates the hypothesis's linked papers.`,
      );
      if (!ok) return;
    }
    setApplying(true);
    setApplyError(null);
    try {
      await onApplyRecommendation(drop, retain);
    } catch (err) {
      setApplyError(err instanceof Error ? err.message : "Apply failed");
    } finally {
      setApplying(false);
    }
  };

  return (
    <div className="border border-violet-400/40 rounded bg-violet-500/5 p-5 space-y-5" data-synthesis-card>
      <header className="flex items-center justify-between gap-3">
        <h3 className="text-sm mono uppercase tracking-wider text-violet-300">
          Synthesis
        </h3>
        <StatusBadge status={hypothesis.status} size="md" />
      </header>

      {reconciled && (
        <section>
          <h4 className="mono text-[10px] uppercase tracking-wider text-text-muted mb-1">
            Reconciled claim
          </h4>
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{reconciled}</p>
        </section>
      )}

      {openQs.length > 0 && (
        <section>
          <h4 className="mono text-[10px] uppercase tracking-wider text-text-muted mb-1">
            Open questions
          </h4>
          <ul className="list-disc pl-4 space-y-1 text-sm">
            {openQs.map((q, i) => (
              <li key={i}>{q}</li>
            ))}
          </ul>
        </section>
      )}

      {renderStages.length > 0 && (
        <section data-section="proposed-experiment">
          <button
            onClick={() => setStagesOpen((v) => !v)}
            data-action="toggle-stages"
            className="flex items-center gap-1 mono text-[10px] uppercase tracking-wider text-text-muted hover:text-text mb-1"
          >
            <span>{stagesOpen ? "▼" : "▶"}</span>
            <span>Proposed experiment ({renderStages.length} stage{renderStages.length === 1 ? "" : "s"})</span>
          </button>
          {stagesOpen && (
            <ol
              data-stages-list
              className="list-decimal pl-5 space-y-2 text-sm marker:text-text-muted"
            >
              {renderStages.map((stage, i) => (
                <li key={i} data-stage-index={i + 1}>
                  {stage.title && (
                    <div className="font-medium">{stage.title}</div>
                  )}
                  {stage.description && (
                    <p className="text-text-dim leading-relaxed whitespace-pre-wrap">
                      {stage.description}
                    </p>
                  )}
                </li>
              ))}
            </ol>
          )}
        </section>
      )}

      {legacyDesignBlock && (
        <section>
          <h4 className="mono text-[10px] uppercase tracking-wider text-text-muted mb-1">
            Proposed experiment (legacy shape)
          </h4>
          <pre className="text-[11px] bg-bg-soft border border-border-dim rounded p-3 whitespace-pre-wrap text-text-dim mono">
            {typeof legacyDesignBlock === "string"
              ? legacyDesignBlock
              : JSON.stringify(legacyDesignBlock, null, 2)}
          </pre>
        </section>
      )}

      {(drop.length > 0 || retain.length > 0) && (
        <section
          data-section="paper-set-recommendation"
          className="border border-violet-400/30 rounded bg-violet-500/10 p-3 space-y-2"
        >
          <h4 className="mono text-[10px] uppercase tracking-wider text-text-muted">
            Paper-set recommendation
          </h4>
          {drop.length > 0 && (
            <div>
              <div className="mono text-[10px] uppercase tracking-wider text-danger">
                Drop ({drop.length})
              </div>
              <ul
                data-drop-list
                className="list-disc pl-4 text-[12px] text-text-dim mono break-all"
              >
                {drop.map((id) => (
                  <li key={id} data-paper-id={id}>{id}</li>
                ))}
              </ul>
            </div>
          )}
          {retain.length > 0 && (
            <div>
              <div className="mono text-[10px] uppercase tracking-wider text-good">
                Retain ({retain.length})
              </div>
              <ul
                data-retain-list
                className="list-disc pl-4 text-[12px] text-text-dim mono break-all"
              >
                {retain.map((id) => (
                  <li key={id} data-paper-id={id}>{id}</li>
                ))}
              </ul>
            </div>
          )}
          <div className="flex items-center gap-2 pt-1">
            <button
              onClick={handleApply}
              disabled={applyDisabled || applying || !onApplyRecommendation}
              data-action="apply-recommendation"
              className="px-3 py-1.5 border border-accent rounded mono text-[10px] uppercase tracking-wider text-accent hover:bg-accent hover:text-bg transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {applying ? "Applying…" : "Apply"}
            </button>
            {applyError && (
              <span className="text-[11px] text-danger" data-apply-error>
                {applyError}
              </span>
            )}
          </div>
        </section>
      )}

      {hypothesis.council_confidence && (
        <div className="mono text-[10px] uppercase tracking-wider text-text-muted">
          Council confidence: <span className="text-text">{hypothesis.council_confidence}</span>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-border-dim">
        <button
          onClick={onMarkSupported}
          disabled={hypothesis.status === "supported"}
          className="px-3 py-1.5 border border-good rounded mono text-[10px] uppercase tracking-wider text-good hover:bg-good hover:text-bg transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Mark supported
        </button>
        <button
          onClick={onMarkRefuted}
          disabled={hypothesis.status === "refuted"}
          className="px-3 py-1.5 border border-danger rounded mono text-[10px] uppercase tracking-wider text-danger hover:bg-danger hover:text-bg transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Mark refuted
        </button>
        <button
          onClick={onArchive}
          disabled={hypothesis.status === "archived"}
          className="px-3 py-1.5 border border-border rounded mono text-[10px] uppercase tracking-wider text-text-dim hover:text-text transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Archive
        </button>
      </div>
    </div>
  );
}
