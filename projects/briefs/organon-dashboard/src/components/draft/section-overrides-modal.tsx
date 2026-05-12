"use client";

import { useState } from "react";
import type {
  FigureArtifact,
  HypothesisArtifact,
  PaperArtifact,
  SectionDraftArtifact,
} from "@/lib/artifacts/types";
import type { ManuscriptMeta } from "@/lib/draft/store";
import type { DatasetLite } from "./source-linkage-panel";

/**
 * Phase 51 (v2.0) — Per-section linkage override editor modal.
 *
 * Lets the researcher narrow generation for a single section to a
 * different paper/figure/hypothesis/dataset subset than the
 * manuscript-level linkage. Empty arrays clear the override (the
 * section falls back to manuscript-level linkage; if that is also
 * empty, generation uses everything).
 */

type Tab = "papers" | "figures" | "hypotheses" | "datasets";

export type SectionOverridesModalProps = {
  section: SectionDraftArtifact | null;
  manuscript: ManuscriptMeta;
  hypotheses: HypothesisArtifact[];
  library: PaperArtifact[];
  figures: FigureArtifact[];
  datasets: DatasetLite[];
  onSave: (overrides: {
    override_linked_paper_ids?: string[];
    override_linked_figure_ids?: string[];
    override_linked_hypothesis_ids?: string[];
    override_linked_dataset_ids?: string[];
  }) => Promise<void>;
  onCancel: () => void;
};

export function SectionOverridesModal(props: SectionOverridesModalProps) {
  const { section, manuscript, hypotheses, library, figures, datasets, onSave, onCancel } = props;
  const [tab, setTab] = useState<Tab>("papers");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [paperIds, setPaperIds] = useState<Set<string>>(
    () => new Set(section?.override_linked_paper_ids ?? []),
  );
  const [figureIds, setFigureIds] = useState<Set<string>>(
    () => new Set(section?.override_linked_figure_ids ?? []),
  );
  const [hypIds, setHypIds] = useState<Set<string>>(
    () => new Set(section?.override_linked_hypothesis_ids ?? []),
  );
  const [datasetIds, setDatasetIds] = useState<Set<string>>(
    () => new Set(section?.override_linked_dataset_ids ?? []),
  );

  if (!section) return null;

  const tabs: { key: Tab; label: string; count: number }[] = [
    { key: "papers", label: "Papers", count: paperIds.size },
    { key: "figures", label: "Figures", count: figureIds.size },
    { key: "hypotheses", label: "Hypotheses", count: hypIds.size },
    { key: "datasets", label: "Datasets", count: datasetIds.size },
  ];

  const handleSave = async () => {
    setBusy(true);
    setError(null);
    try {
      await onSave({
        override_linked_paper_ids: Array.from(paperIds),
        override_linked_figure_ids: Array.from(figureIds),
        override_linked_hypothesis_ids: Array.from(hypIds),
        override_linked_dataset_ids: Array.from(datasetIds),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const renderTab = () => {
    if (tab === "papers") {
      return (
        <PickerList
          available={library.map((p) => ({
            id: p.id,
            primary: p.title,
            secondary: `${p.authors?.[0] ?? "?"} · ${p.year}`,
          }))}
          selected={paperIds}
          onToggle={(id) =>
            setPaperIds((prev) => {
              const next = new Set(prev);
              if (next.has(id)) next.delete(id);
              else next.add(id);
              return next;
            })
          }
          onAll={() => setPaperIds(new Set(library.map((p) => p.id)))}
          onNone={() => setPaperIds(new Set())}
          fallbackHint={
            (manuscript.linked_paper_ids ?? []).length > 0
              ? `Empty → fall back to manuscript (${(manuscript.linked_paper_ids ?? []).length} linked)`
              : "Empty → use everything in the project"
          }
        />
      );
    }
    if (tab === "figures") {
      return (
        <PickerList
          available={figures.map((f) => ({
            id: f.id,
            primary: f.caption ?? f.id,
            secondary: `v${f.version} · ${f.kind}`,
          }))}
          selected={figureIds}
          onToggle={(id) =>
            setFigureIds((prev) => {
              const next = new Set(prev);
              if (next.has(id)) next.delete(id);
              else next.add(id);
              return next;
            })
          }
          onAll={() => setFigureIds(new Set(figures.map((f) => f.id)))}
          onNone={() => setFigureIds(new Set())}
          fallbackHint={
            (manuscript.linked_figure_ids ?? []).length > 0
              ? `Empty → fall back to manuscript (${(manuscript.linked_figure_ids ?? []).length} linked)`
              : "Empty → use everything in the project"
          }
        />
      );
    }
    if (tab === "hypotheses") {
      return (
        <PickerList
          available={hypotheses.map((h) => ({
            id: h.id,
            primary: h.claim_short ?? h.claim ?? h.id,
            secondary: h.status,
          }))}
          selected={hypIds}
          onToggle={(id) =>
            setHypIds((prev) => {
              const next = new Set(prev);
              if (next.has(id)) next.delete(id);
              else next.add(id);
              return next;
            })
          }
          onAll={() => setHypIds(new Set(hypotheses.map((h) => h.id)))}
          onNone={() => setHypIds(new Set())}
          fallbackHint={
            (manuscript.linked_hypothesis_ids ?? []).length > 0
              ? `Empty → fall back to manuscript (${(manuscript.linked_hypothesis_ids ?? []).length} linked)`
              : "Empty → not used by generation today"
          }
        />
      );
    }
    return (
      <PickerList
        available={datasets.map((d) => ({
          id: d.id,
          primary: d.filename ?? d.id,
          secondary: typeof d.rows_total === "number" ? `${d.rows_total} rows` : undefined,
        }))}
        selected={datasetIds}
        onToggle={(id) =>
          setDatasetIds((prev) => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
          })
        }
        onAll={() => setDatasetIds(new Set(datasets.map((d) => d.id)))}
        onNone={() => setDatasetIds(new Set())}
        fallbackHint={
          (manuscript.linked_dataset_ids ?? []).length > 0
            ? `Empty → fall back to manuscript (${(manuscript.linked_dataset_ids ?? []).length} linked)`
            : "Empty → not used by generation today"
        }
      />
    );
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-6"
      data-section-overrides-modal
      onClick={onCancel}
    >
      <div
        className="bg-bg-elev border border-accent/40 rounded p-4 w-full max-w-2xl max-h-[80vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="mono text-[10px] uppercase tracking-wider mb-3 flex items-center justify-between">
          <span>Section sources — {section.section_id}</span>
          <button
            type="button"
            onClick={onCancel}
            className="text-text-muted hover:text-text"
          >
            ✕
          </button>
        </header>

        <nav className="flex gap-2 mb-3 border-b border-border-dim">
          {tabs.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              className={`mono text-[10px] uppercase tracking-wider px-2 py-1 ${
                tab === t.key
                  ? "border-b-2 border-accent text-accent"
                  : "text-text-muted hover:text-text"
              }`}
            >
              {t.label} ({t.count})
            </button>
          ))}
        </nav>

        <div className="flex-1 min-h-0 overflow-auto">{renderTab()}</div>

        {error && <div className="mono text-[10px] text-danger mt-2">{error}</div>}

        <footer className="flex justify-end gap-2 mt-3 pt-3 border-t border-border-dim">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="text-[10px] mono uppercase tracking-wider px-2 py-1 border border-border-dim text-text-dim rounded"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={busy}
            className="text-[10px] mono uppercase tracking-wider px-2 py-1 border border-accent text-accent hover:bg-accent-faint rounded disabled:opacity-50"
          >
            {busy ? "Saving…" : "Save overrides"}
          </button>
        </footer>
      </div>
    </div>
  );
}

type PickerProps = {
  available: { id: string; primary: string; secondary?: string }[];
  selected: Set<string>;
  onToggle: (id: string) => void;
  onAll: () => void;
  onNone: () => void;
  fallbackHint: string;
};

function PickerList(props: PickerProps) {
  const { available, selected, onToggle, onAll, onNone, fallbackHint } = props;
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="mono text-[10px] text-text-muted">{fallbackHint}</div>
        <div className="flex gap-1">
          <button
            type="button"
            onClick={onAll}
            className="text-[10px] mono uppercase tracking-wider px-2 py-0.5 border border-border-dim text-text-dim rounded"
          >
            ALL
          </button>
          <button
            type="button"
            onClick={onNone}
            className="text-[10px] mono uppercase tracking-wider px-2 py-0.5 border border-border-dim text-text-dim rounded"
          >
            NONE
          </button>
        </div>
      </div>
      {available.length === 0 ? (
        <div className="text-xs text-text-muted py-2">No items in this project yet.</div>
      ) : (
        <ul className="divide-y divide-border-dim">
          {available.map((a) => (
            <li key={a.id}>
              <label className="flex items-start gap-2 px-2 py-1 hover:bg-bg-soft cursor-pointer">
                <input
                  type="checkbox"
                  checked={selected.has(a.id)}
                  onChange={() => onToggle(a.id)}
                  className="mt-1"
                />
                <span className="flex-1 text-xs">
                  <div className="text-text">{a.primary}</div>
                  {a.secondary && (
                    <div className="mono text-[10px] text-text-muted">{a.secondary}</div>
                  )}
                </span>
              </label>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
