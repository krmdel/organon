"use client";

import { useEffect, useMemo, useState } from "react";
import type { ColumnType, DataframeArtifact } from "@/lib/artifacts/types";
import type { ComparisonMode, WizardAnswers } from "@/lib/data/stat-picker";
import { BulkSelect } from "@/components/primitives/bulk-select";

export type StatTestPickerProps = {
  dataframe: DataframeArtifact;
  onSubmit: (answers: WizardAnswers) => void;
  loading?: boolean;
  /**
   * Phase 12c (v1.0.1) — D-3 outcome-mismatch hint. Lets the workspace
   * surface a chip on the result card when the picker's currently-
   * selected outcome diverges from a result's outcome. The picker fires
   * this whenever the mode-specific outcome state changes.
   */
  onCurrentOutcomeChange?: (outcome: string | null) => void;
};

const MODES: { value: ComparisonMode; label: string; hint: string }[] = [
  { value: "group", label: "Compare groups", hint: "Numeric outcome across categorical groups" },
  { value: "correlation", label: "Correlation", hint: "Two numeric variables" },
  { value: "regression", label: "Regression", hint: "Predict one column from others" },
  { value: "contingency", label: "Contingency", hint: "Two categorical variables" },
  { value: "power", label: "Power analysis", hint: "Find required n or achieved power" },
];

function colsByType(df: DataframeArtifact, types: ColumnType[]): string[] {
  return df.columns.filter((c) => types.includes(c.type)).map((c) => c.name);
}

export function StatTestPicker({
  dataframe,
  onSubmit,
  loading,
  onCurrentOutcomeChange,
}: StatTestPickerProps) {
  const [mode, setMode] = useState<ComparisonMode>("group");
  // group
  const numericCols = useMemo(() => colsByType(dataframe, ["numeric"]), [dataframe]);
  const categoricalCols = useMemo(() => colsByType(dataframe, ["categorical"]), [dataframe]);
  const numOrCat = useMemo(() => colsByType(dataframe, ["numeric", "categorical"]), [dataframe]);

  const [valueCol, setValueCol] = useState<string>(numericCols[0] ?? "");
  const [groupCol, setGroupCol] = useState<string>(categoricalCols[0] ?? "");
  const [paired, setPaired] = useState(false);
  // correlation
  const [xCol, setXCol] = useState<string>(numericCols[0] ?? "");
  const [yCol, setYCol] = useState<string>(numericCols[1] ?? numericCols[0] ?? "");
  // regression
  const [targetCol, setTargetCol] = useState<string>(numericCols[0] ?? "");
  const [predictorCols, setPredictorCols] = useState<string[]>(
    numericCols.slice(1, 3),
  );
  // contingency
  const [rowCol, setRowCol] = useState<string>(categoricalCols[0] ?? "");
  const [colCol, setColCol] = useState<string>(categoricalCols[1] ?? categoricalCols[0] ?? "");
  // power
  const [testKind, setTestKind] = useState<"t-test" | "anova" | "correlation" | "chi2">("t-test");
  const [effect, setEffect] = useState(0.5);
  const [alpha, setAlpha] = useState(0.05);
  const [powerTarget, setPowerTarget] = useState<number | undefined>(0.8);
  const [n, setN] = useState<number | undefined>(undefined);

  const submit = () => {
    if (loading) return;
    if (mode === "group") onSubmit({ mode, value_col: valueCol, group_col: groupCol, paired });
    else if (mode === "correlation") onSubmit({ mode, x_col: xCol, y_col: yCol });
    else if (mode === "regression")
      onSubmit({ mode, target_col: targetCol, predictor_cols: predictorCols });
    else if (mode === "contingency") onSubmit({ mode, row_col: rowCol, col_col: colCol });
    else
      onSubmit({
        mode,
        test_kind: testKind,
        effect_size: effect,
        alpha,
        power_target: powerTarget,
        n,
      });
  };

  // Phase 12c (v1.0.1) — D-3 emit the picker's current outcome whenever
  // the mode-specific outcome state changes. Workspace renders a hint on
  // any result card whose outcome diverges. Group / regression treat the
  // value/target column as the outcome; correlation has no single
  // outcome (two symmetric variables) so we emit null and the hint is
  // suppressed.
  useEffect(() => {
    if (!onCurrentOutcomeChange) return;
    const out =
      mode === "group" ? valueCol :
      mode === "regression" ? targetCol :
      mode === "contingency" ? rowCol :
      null;
    onCurrentOutcomeChange(out || null);
  }, [mode, valueCol, targetCol, rowCol, onCurrentOutcomeChange]);

  // D-8: keep the BulkSelect's selection in sync with the array state.
  const availablePredictors = useMemo(
    () => numOrCat.filter((c) => c !== targetCol),
    [numOrCat, targetCol],
  );
  const predictorSelection = useMemo(
    () => new Set(predictorCols),
    [predictorCols],
  );

  const Label = (props: { children: React.ReactNode }) => (
    <div className="mono text-[10px] uppercase tracking-wider text-text-muted mt-2">
      {props.children}
    </div>
  );
  const inputCls =
    "mt-1 bg-bg border border-border-dim text-sm text-text px-2 py-1 rounded focus:border-accent outline-none";

  return (
    <div className="border border-border-dim rounded bg-bg-elev px-4 py-3">
      <div className="flex items-center justify-between">
        <div className="mono text-[11px] uppercase tracking-[0.2em] text-text-muted">
          Stat picker
        </div>
        <button
          type="button"
          onClick={submit}
          disabled={loading}
          className="text-xs mono uppercase tracking-wider px-3 py-1 border border-accent text-accent hover:bg-accent-faint rounded disabled:opacity-50"
        >
          {loading ? "Picking…" : "Recommend"}
        </button>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2">
        {MODES.map((m) => (
          <button
            key={m.value}
            type="button"
            onClick={() => setMode(m.value)}
            className={`text-left px-3 py-2 rounded border text-sm transition ${
              mode === m.value
                ? "border-accent bg-accent-faint text-text"
                : "border-border-dim text-text-dim hover:border-accent/50 hover:text-text"
            }`}
          >
            <div>{m.label}</div>
            <div className="mono text-[10px] text-text-muted">{m.hint}</div>
          </button>
        ))}
      </div>

      {mode === "group" && (
        <div className="mt-2">
          <Label>Numeric outcome</Label>
          <select
            value={valueCol}
            onChange={(e) => setValueCol(e.target.value)}
            className={inputCls + " w-full"}
          >
            {numericCols.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <Label>Group column</Label>
          <select
            value={groupCol}
            onChange={(e) => setGroupCol(e.target.value)}
            className={inputCls + " w-full"}
          >
            {categoricalCols.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <label className="mt-2 flex items-center gap-2 text-sm text-text-dim">
            <input
              type="checkbox"
              checked={paired}
              onChange={(e) => setPaired(e.target.checked)}
              className="accent-accent"
            />
            Paired / repeated measures
          </label>
        </div>
      )}

      {mode === "correlation" && (
        <div className="mt-2">
          <Label>X (numeric)</Label>
          <select value={xCol} onChange={(e) => setXCol(e.target.value)} className={inputCls + " w-full"}>
            {numericCols.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <Label>Y (numeric)</Label>
          <select value={yCol} onChange={(e) => setYCol(e.target.value)} className={inputCls + " w-full"}>
            {numericCols.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
      )}

      {mode === "regression" && (
        <div className="mt-2">
          <Label>Target column</Label>
          <select
            value={targetCol}
            onChange={(e) => setTargetCol(e.target.value)}
            className={inputCls + " w-full"}
          >
            {numOrCat.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <Label>Predictor columns</Label>
          <div className="mt-1 px-2 pt-1.5">
            <BulkSelect
              items={availablePredictors}
              keyOf={(c) => c}
              selectedKeys={predictorSelection}
              onChange={(next) =>
                setPredictorCols(availablePredictors.filter((c) => next.has(c)))
              }
              label="columns"
            />
          </div>
          <div className="mt-1 max-h-32 overflow-auto border border-border-dim rounded p-2 space-y-1">
            {availablePredictors.map((c) => (
              <label key={c} className="flex items-center gap-2 text-sm text-text-dim">
                <input
                  type="checkbox"
                  checked={predictorCols.includes(c)}
                  onChange={(e) =>
                    setPredictorCols((prev) =>
                      e.target.checked ? [...prev, c] : prev.filter((x) => x !== c),
                    )
                  }
                  className="accent-accent"
                />
                {c}
              </label>
            ))}
          </div>
        </div>
      )}

      {mode === "contingency" && (
        <div className="mt-2">
          <Label>Row column</Label>
          <select value={rowCol} onChange={(e) => setRowCol(e.target.value)} className={inputCls + " w-full"}>
            {categoricalCols.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <Label>Column column</Label>
          <select value={colCol} onChange={(e) => setColCol(e.target.value)} className={inputCls + " w-full"}>
            {categoricalCols.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
      )}

      {mode === "power" && (
        <div className="mt-2 grid grid-cols-2 gap-2">
          <div>
            <Label>Test kind</Label>
            <select value={testKind} onChange={(e) => setTestKind(e.target.value as typeof testKind)} className={inputCls + " w-full"}>
              <option value="t-test">t-test</option>
              <option value="anova">anova</option>
              <option value="correlation">correlation</option>
              <option value="chi2">chi-squared</option>
            </select>
          </div>
          <div>
            <Label>Effect size</Label>
            <input type="number" step="0.05" value={effect} onChange={(e) => setEffect(Number(e.target.value))} className={inputCls + " w-full"} />
          </div>
          <div>
            <Label>Alpha</Label>
            <input type="number" step="0.005" value={alpha} onChange={(e) => setAlpha(Number(e.target.value))} className={inputCls + " w-full"} />
          </div>
          <div>
            <Label>Target power (if solving for n)</Label>
            <input type="number" step="0.05" value={powerTarget ?? ""} onChange={(e) => setPowerTarget(e.target.value ? Number(e.target.value) : undefined)} className={inputCls + " w-full"} />
          </div>
          <div className="col-span-2">
            <Label>n (if solving for power)</Label>
            <input type="number" step="1" value={n ?? ""} onChange={(e) => setN(e.target.value ? Number(e.target.value) : undefined)} className={inputCls + " w-full"} />
          </div>
        </div>
      )}
    </div>
  );
}
