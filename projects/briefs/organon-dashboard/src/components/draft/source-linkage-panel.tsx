"use client";

import { useMemo, useState } from "react";
import type {
  FigureArtifact,
  HypothesisArtifact,
  PaperArtifact,
} from "@/lib/artifacts/types";
import type { ManuscriptMeta } from "@/lib/draft/store";
import { HypothesisMultiselect } from "@/components/hypothesis/hypothesis-multiselect";
import { CitationGraph } from "./citation-graph";

/**
 * Phase 41 (v1.5) — F4 source-linkage-panel.
 *
 * Surfaces the manuscript's four linkage arrays (Hypotheses · Papers ·
 * Figures · Datasets) with a count + edit affordance + an expandable
 * list. The "edit" button opens a multi-select modal whose Save action
 * PATCHes /api/draft/[slug] with the updated array.
 *
 * Decision (brief §5.3):
 * - Linkage IDs are validated at PATCH time, not at read time. A paper
 *   deleted from the library after being linked stays in the array on
 *   disk but renders as "missing — N of M no longer in library".
 * - Empty linkage → all (backward-compat). Once the user explicitly
 *   edits, generation narrows to the listed subset.
 */

export type DatasetLite = { id: string; filename?: string; rows_total?: number };

export type SourceLinkagePanelProps = {
  project: string;
  manuscript: ManuscriptMeta;
  hypotheses: HypothesisArtifact[];
  library: PaperArtifact[];
  figures: FigureArtifact[];
  datasets: DatasetLite[];
  onLinkageUpdated: (next: ManuscriptMeta) => void;
};

type LinkageField =
  | "linked_hypothesis_ids"
  | "linked_paper_ids"
  | "linked_figure_ids"
  | "linked_dataset_ids";

type SectionDef = {
  key: "hypotheses" | "papers" | "figures" | "datasets";
  label: string;
  field: LinkageField;
  available: { id: string; primary: string; secondary?: string }[];
  selectedIds: string[];
};

export function SourceLinkagePanel(props: SourceLinkagePanelProps) {
  const {
    project,
    manuscript,
    hypotheses,
    library,
    figures,
    datasets,
    onLinkageUpdated,
  } = props;

  const [openSection, setOpenSection] = useState<SectionDef["key"] | null>(null);
  const [editingField, setEditingField] = useState<LinkageField | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Phase 53 (v2.0) — Citation graph toggle. Hidden by default; opens
  // a read-only SVG visualisation of manuscript ↔ linked artifacts.
  const [graphOpen, setGraphOpen] = useState(false);
  // Phase 54 (v2.0) — Reproducibility check report. POSTs to the new
  // route and surfaces the per-check verdicts inline. Null when never
  // run; cleared when the user closes the panel.
  type ReproReport = {
    passed: boolean;
    checks: { name: string; label?: string; verdict: "pass" | "warn" | "fail"; detail: string[] }[];
    ran_at?: string;
  };
  const [reproReport, setReproReport] = useState<ReproReport | null>(null);
  const [reproRunning, setReproRunning] = useState(false);
  const runReproCheck = async () => {
    setReproRunning(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/draft/${encodeURIComponent(manuscript.slug)}/repro-check?project=${encodeURIComponent(project)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ project }),
        },
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.error ?? `HTTP ${res.status}`);
      setReproReport(data as ReproReport);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setReproRunning(false);
    }
  };

  const sections: SectionDef[] = useMemo(() => [
    {
      key: "hypotheses",
      label: "Hypotheses",
      field: "linked_hypothesis_ids",
      available: hypotheses.map((h) => ({
        id: h.id,
        primary: h.claim_short ?? h.claim ?? h.id,
        secondary: h.status,
      })),
      selectedIds: manuscript.linked_hypothesis_ids ?? [],
    },
    {
      key: "papers",
      label: "Papers",
      field: "linked_paper_ids",
      available: library.map((p) => ({
        id: p.id,
        primary: p.title,
        secondary: `${(p.authors?.[0] ?? "?")} · ${p.year}`,
      })),
      selectedIds: manuscript.linked_paper_ids ?? [],
    },
    {
      key: "figures",
      label: "Figures",
      field: "linked_figure_ids",
      available: figures.map((f) => ({
        id: f.id,
        primary: f.caption ?? f.id,
        secondary: `v${f.version} · ${f.kind}`,
      })),
      selectedIds: manuscript.linked_figure_ids ?? [],
    },
    {
      key: "datasets",
      label: "Datasets",
      field: "linked_dataset_ids",
      available: datasets.map((d) => ({
        id: d.id,
        primary: d.filename ?? d.id,
        secondary: typeof d.rows_total === "number" ? `${d.rows_total} rows` : undefined,
      })),
      selectedIds: manuscript.linked_dataset_ids ?? [],
    },
  ], [manuscript, hypotheses, library, figures, datasets]);

  const persistLinkage = async (field: LinkageField, ids: string[]) => {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/draft/${encodeURIComponent(manuscript.slug)}?project=${encodeURIComponent(project)}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ [field]: ids }),
        },
      );
      const json = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(json?.error ?? `HTTP ${res.status}`);
      if (json?.manuscript) onLinkageUpdated(json.manuscript);
      setEditingField(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section
      className="border border-border-dim rounded bg-bg-elev px-4 py-3 mb-3"
      data-source-linkage-panel
    >
      <header className="flex items-center justify-between mb-2 gap-2">
        <div className="mono text-[10px] uppercase tracking-[0.2em] text-text-muted">
          Sources
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            data-graph-toggle
            onClick={() => setGraphOpen((g) => !g)}
            className="mono text-[10px] uppercase tracking-wider px-2 py-0.5 border border-accent/60 text-accent hover:bg-accent-faint rounded"
            title="Toggle citation graph (Phase 53)"
          >
            {graphOpen ? "Hide graph" : "View graph"}
          </button>
          <button
            type="button"
            data-repro-check
            onClick={() => void runReproCheck()}
            disabled={reproRunning}
            className="mono text-[10px] uppercase tracking-wider px-2 py-0.5 border border-accent/60 text-accent hover:bg-accent-faint rounded disabled:opacity-50"
            title="Re-resolve cite-keys, fig-ids, and linked artifact ids (Phase 54)"
          >
            {reproRunning ? "Checking…" : "Repro check"}
          </button>
        </div>
      </header>

      {/* Phase 61 (v2.1) — C1: better help-text. The previous one-liner
          ("Empty → use everything. Non-empty narrows generation.") was
          cryptic. Replace with a researcher-readable summary + per-kind
          <details> block explaining how each linkage feeds generation. */}
      <p
        data-sources-help
        className="text-[12px] text-text-dim mb-2 leading-snug"
      >
        These artifacts feed every section&apos;s prompt. Empty linkage → use
        everything in this project. Tighten via the per-section
        {" "}<span className="mono text-[11px]">⚙ src</span>{" "}
        override (Phase 51) when one section needs different evidence.
      </p>
      <details
        data-sources-help-details
        className="mb-3 mono text-[11px] text-text-muted"
      >
        <summary className="cursor-pointer hover:text-text">
          how each kind shapes the prompt
        </summary>
        <ul className="mt-2 space-y-1 pl-4 list-disc">
          <li>
            <strong className="text-text-dim">Hypotheses:</strong> claim_short
            + status + council_confidence; sci-writing anchors framings + cites
            them in Discussion.
          </li>
          <li>
            <strong className="text-text-dim">Papers:</strong> trimmed to
            cite_key + title + year; fed to every section as the citation pool.
          </li>
          <li>
            <strong className="text-text-dim">Figures:</strong> caption + kind;
            rendered inline in Results / Methods when the section references
            them.
          </li>
          <li>
            <strong className="text-text-dim">Datasets:</strong> filename +
            row count; surfaced in Methods so sample-size + provenance language
            stays accurate.
          </li>
        </ul>
      </details>

      {reproReport && (
        <div
          className={`mb-3 border rounded p-3 ${
            reproReport.passed
              ? "border-accent/40 bg-bg"
              : "border-danger/60 bg-bg"
          }`}
        >
          <div className="mono text-[10px] uppercase tracking-wider mb-2 flex items-center justify-between">
            <span className={reproReport.passed ? "text-accent" : "text-danger"}>
              Repro check {reproReport.passed ? "passed" : "FAILED"}
            </span>
            <button
              type="button"
              onClick={() => setReproReport(null)}
              className="text-text-muted hover:text-text"
            >
              dismiss
            </button>
          </div>
          <ul className="space-y-1">
            {reproReport.checks.map((c) => (
              <li key={c.name} className="text-xs flex items-start gap-2">
                <span
                  className={
                    c.verdict === "pass"
                      ? "text-accent"
                      : c.verdict === "warn"
                        ? "text-yellow-400"
                        : "text-danger"
                  }
                >
                  {c.verdict === "pass" ? "✓" : c.verdict === "warn" ? "!" : "✗"}
                </span>
                <span className="flex-1">
                  <span className="text-text">{c.label ?? c.name}</span>
                  {c.detail.length > 0 && (
                    <span className="mono text-[10px] text-text-muted ml-2">
                      ({c.detail.length}: {c.detail.slice(0, 4).join(", ")}
                      {c.detail.length > 4 ? `, +${c.detail.length - 4} more` : ""})
                    </span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {graphOpen && (
        <div className="mb-3">
          <CitationGraph
            manuscript={manuscript}
            hypotheses={hypotheses}
            library={library}
            figures={figures}
            datasets={datasets}
          />
        </div>
      )}

      <ul className="divide-y divide-border-dim">
        {sections.map((s) => {
          const present = new Set(s.available.map((a) => a.id));
          const missing = s.selectedIds.filter((id) => !present.has(id));
          const expanded = openSection === s.key;
          return (
            <li
              key={s.key}
              className="py-2"
              data-linkage-section={s.key}
            >
              <div className="flex items-center justify-between gap-2">
                <button
                  type="button"
                  onClick={() => setOpenSection(expanded ? null : s.key)}
                  className="flex-1 text-left flex items-center gap-2"
                >
                  <span className="text-text">{s.label}</span>
                  <span className="mono text-[10px] text-text-muted">
                    {s.selectedIds.length} linked
                    {missing.length > 0
                      ? ` · ${missing.length} missing`
                      : s.selectedIds.length === 0
                        ? " (defaults to all)"
                        : ""}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => setEditingField(s.field)}
                  data-linkage-edit={s.key}
                  className="text-[10px] mono uppercase tracking-wider px-2 py-0.5 border border-accent/60 text-accent hover:bg-accent-faint rounded"
                >
                  edit
                </button>
              </div>
              {expanded && s.selectedIds.length > 0 && (
                <ul className="mt-2 space-y-1 pl-3">
                  {s.selectedIds.map((id) => {
                    const item = s.available.find((a) => a.id === id);
                    return (
                      <li
                        key={id}
                        className={`text-xs ${item ? "text-text-dim" : "text-danger"}`}
                      >
                        {item ? item.primary : `${id} (missing)`}
                      </li>
                    );
                  })}
                </ul>
              )}
              {editingField === s.field && (
                s.key === "hypotheses" ? (
                  <HypothesisLinkageEditModal
                    hypotheses={hypotheses}
                    initial={s.selectedIds}
                    busy={busy}
                    error={error}
                    onCancel={() => {
                      setEditingField(null);
                      setError(null);
                    }}
                    onSave={(ids) => void persistLinkage(s.field, ids)}
                  />
                ) : (
                  <LinkageEditModal
                    label={s.label}
                    available={s.available}
                    initial={s.selectedIds}
                    busy={busy}
                    error={error}
                    onCancel={() => {
                      setEditingField(null);
                      setError(null);
                    }}
                    onSave={(ids) => void persistLinkage(s.field, ids)}
                  />
                )
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

type LinkageEditModalProps = {
  label: string;
  available: { id: string; primary: string; secondary?: string }[];
  initial: string[];
  busy: boolean;
  error: string | null;
  onCancel: () => void;
  onSave: (ids: string[]) => void;
};

function LinkageEditModal(props: LinkageEditModalProps) {
  const { label, available, initial, busy, error, onCancel, onSave } = props;
  const [selected, setSelected] = useState<Set<string>>(() => new Set(initial));

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };
  const all = () => setSelected(new Set(available.map((a) => a.id)));
  const none = () => setSelected(new Set());

  return (
    <div className="mt-3 border border-accent/40 rounded bg-bg p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="mono text-[10px] uppercase tracking-wider text-text-muted">
          Edit linked {label.toLowerCase()}
        </div>
        <div className="flex gap-1">
          <button
            type="button"
            onClick={all}
            className="text-[10px] mono uppercase tracking-wider px-2 py-0.5 border border-border-dim text-text-dim rounded"
          >
            ALL
          </button>
          <button
            type="button"
            onClick={none}
            className="text-[10px] mono uppercase tracking-wider px-2 py-0.5 border border-border-dim text-text-dim rounded"
          >
            NONE
          </button>
        </div>
      </div>
      {available.length === 0 ? (
        <div className="text-xs text-text-muted py-2">
          No {label.toLowerCase()} in this project yet.
        </div>
      ) : (
        <ul className="max-h-64 overflow-y-auto divide-y divide-border-dim">
          {available.map((a) => (
            <li key={a.id}>
              <label className="flex items-start gap-2 px-2 py-1 hover:bg-bg-soft cursor-pointer">
                <input
                  type="checkbox"
                  checked={selected.has(a.id)}
                  onChange={() => toggle(a.id)}
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
      {error && <div className="mono text-[10px] text-danger mt-2">{error}</div>}
      <div className="flex justify-end gap-2 mt-3">
        <button
          type="button"
          onClick={onCancel}
          disabled={busy}
          className="text-[10px] mono uppercase tracking-wider px-2 py-0.5 border border-border-dim text-text-dim rounded"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={() => onSave(Array.from(selected))}
          disabled={busy}
          className="text-[10px] mono uppercase tracking-wider px-2 py-0.5 border border-accent text-accent hover:bg-accent-faint rounded disabled:opacity-50"
        >
          {busy ? "Saving…" : "Save"}
        </button>
      </div>
    </div>
  );
}

// Phase 42 (v1.5) — F5: hypothesis-specific edit modal that mounts the
// shared HypothesisMultiselect. Distinct from the generic
// LinkageEditModal so the hypothesis surface gets the richer card
// shape (claim_short + status) without leaking those fields into the
// generic dispatch.
type HypothesisLinkageEditModalProps = {
  hypotheses: HypothesisArtifact[];
  initial: string[];
  busy: boolean;
  error: string | null;
  onCancel: () => void;
  onSave: (ids: string[]) => void;
};

function HypothesisLinkageEditModal(props: HypothesisLinkageEditModalProps) {
  const { hypotheses, initial, busy, error, onCancel, onSave } = props;
  const [selected, setSelected] = useState<string[]>(initial);

  return (
    <div className="mt-3 border border-accent/40 rounded bg-bg p-3">
      <div className="mono text-[10px] uppercase tracking-wider text-text-muted mb-2">
        Edit linked hypotheses
      </div>
      <HypothesisMultiselect
        hypotheses={hypotheses}
        selectedIds={selected}
        onChange={setSelected}
      />
      {error && <div className="mono text-[10px] text-danger mt-2">{error}</div>}
      <div className="flex justify-end gap-2 mt-3">
        <button
          type="button"
          onClick={onCancel}
          disabled={busy}
          className="text-[10px] mono uppercase tracking-wider px-2 py-0.5 border border-border-dim text-text-dim rounded"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={() => onSave(selected)}
          disabled={busy}
          className="text-[10px] mono uppercase tracking-wider px-2 py-0.5 border border-accent text-accent hover:bg-accent-faint rounded disabled:opacity-50"
        >
          {busy ? "Saving…" : "Save"}
        </button>
      </div>
    </div>
  );
}
