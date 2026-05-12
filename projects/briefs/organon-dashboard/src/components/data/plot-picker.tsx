"use client";

import { useEffect, useMemo, useState } from "react";
import type { DataframeArtifact } from "@/lib/artifacts/types";
import { PLOT_SCHEMAS, type PlotKind, type PlotParamField } from "@/lib/data/plot-schemas";

export type PlotPickerProps = {
  dataframe: DataframeArtifact;
  onSubmit: (kind: PlotKind, params: Record<string, unknown>) => void;
  loading?: boolean;
};

const KINDS: PlotKind[] = ["histogram", "scatter", "box", "violin", "heatmap", "pca", "line"];

export function PlotPicker({ dataframe, onSubmit, loading }: PlotPickerProps) {
  const [kind, setKind] = useState<PlotKind>("histogram");
  const schema = PLOT_SCHEMAS[kind];
  const [params, setParams] = useState<Record<string, unknown>>({});

  const colsByType = useMemo(() => {
    const out: Record<string, string[]> = {};
    for (const c of dataframe.columns) {
      out[c.type] = out[c.type] ? [...out[c.type], c.name] : [c.name];
    }
    return out;
  }, [dataframe]);

  // When kind changes, seed defaults so the form lands on something runnable.
  // Phase 7 T6.7 — pick DISTINCT columns when multiple required `column`
  // fields share a filter (the scatter X+Y case). Without this, scatter
  // seeded both X and Y to the same column, which is never useful and
  // forces the researcher to flip one of them on every plot.
  useEffect(() => {
    const seed: Record<string, unknown> = {};
    const usedColumns = new Set<string>();
    for (const f of schema.fields) {
      if (f.default !== undefined) {
        seed[f.name] = f.default;
      } else if (f.required && f.type === "column") {
        const candidates = (f.column_filter ?? []).flatMap((t) => colsByType[t] ?? []);
        const distinct = candidates.find((c) => !usedColumns.has(c));
        const pick = distinct ?? candidates[0];
        if (pick !== undefined) {
          seed[f.name] = pick;
          usedColumns.add(pick);
        }
      } else if (f.required && f.type === "columns") {
        const candidates = (f.column_filter ?? []).flatMap((t) => colsByType[t] ?? []);
        seed[f.name] = candidates.slice(0, 2);
        for (const c of candidates.slice(0, 2)) usedColumns.add(c);
      } else if (f.type === "bool") {
        seed[f.name] = false;
      }
    }
    setParams(seed);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind, dataframe.id]);

  const set = (name: string, value: unknown) => setParams((p) => ({ ...p, [name]: value }));
  const inputCls = "mt-1 bg-bg border border-border-dim text-sm text-text px-2 py-1 rounded focus:border-accent outline-none";

  function renderField(f: PlotParamField) {
    const candidates = (f.column_filter ?? []).flatMap((t) => colsByType[t] ?? []);
    if (f.type === "column") {
      return (
        <select
          value={(params[f.name] as string) ?? ""}
          onChange={(e) => set(f.name, e.target.value || undefined)}
          className={inputCls + " w-full"}
        >
          {!f.required && <option value="">(none)</option>}
          {candidates.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      );
    }
    if (f.type === "columns") {
      const selected = (params[f.name] as string[]) ?? [];
      return (
        <div className="mt-1 max-h-32 overflow-auto border border-border-dim rounded p-2 space-y-1 bg-bg">
          {candidates.map((c) => (
            <label key={c} className="flex items-center gap-2 text-sm text-text-dim">
              <input
                type="checkbox"
                checked={selected.includes(c)}
                onChange={(e) =>
                  set(
                    f.name,
                    e.target.checked ? [...selected, c] : selected.filter((x) => x !== c),
                  )
                }
                className="accent-accent"
              />
              {c}
            </label>
          ))}
          {f.hint && <div className="mono text-[10px] text-text-muted mt-1">{f.hint}</div>}
        </div>
      );
    }
    if (f.type === "int") {
      return (
        <input
          type="number"
          step="1"
          value={(params[f.name] as number) ?? ""}
          onChange={(e) => set(f.name, e.target.value ? Number(e.target.value) : undefined)}
          className={inputCls + " w-full"}
        />
      );
    }
    if (f.type === "bool") {
      return (
        <label className="flex items-center gap-2 text-sm text-text-dim">
          <input
            type="checkbox"
            checked={Boolean(params[f.name])}
            onChange={(e) => set(f.name, e.target.checked)}
            className="accent-accent"
          />
          {f.label}
        </label>
      );
    }
    return null;
  }

  return (
    <div className="border border-border-dim rounded bg-bg-elev px-4 py-3">
      <div className="flex items-center justify-between">
        <div className="mono text-[11px] uppercase tracking-[0.2em] text-text-muted">
          Plot picker
        </div>
        <button
          type="button"
          onClick={() => onSubmit(kind, params)}
          disabled={loading}
          className="text-xs mono uppercase tracking-wider px-3 py-1 border border-accent text-accent hover:bg-accent-faint rounded disabled:opacity-50"
        >
          {loading ? "Plotting…" : "Generate"}
        </button>
      </div>

      <div className="mt-3 flex flex-wrap gap-1">
        {KINDS.map((k) => (
          <button
            key={k}
            type="button"
            onClick={() => setKind(k)}
            className={`text-xs mono uppercase tracking-wider px-2 py-1 border rounded ${
              kind === k
                ? "border-accent text-accent bg-accent-faint"
                : "border-border-dim text-text-dim hover:text-text hover:border-accent/50"
            }`}
          >
            {k}
          </button>
        ))}
      </div>

      <p className="text-xs text-text-muted mt-2">{schema.description}</p>

      <div className="mt-2 space-y-2">
        {schema.fields.map((f) =>
          f.type === "bool" ? (
            <div key={f.name}>{renderField(f)}</div>
          ) : (
            <div key={f.name}>
              <div className="mono text-[10px] uppercase tracking-wider text-text-muted">
                {f.label}{f.required ? "" : " · optional"}
              </div>
              {renderField(f)}
            </div>
          ),
        )}
      </div>
    </div>
  );
}
