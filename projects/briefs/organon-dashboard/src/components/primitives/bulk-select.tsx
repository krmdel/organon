"use client";

import { useMemo } from "react";

/**
 * Phase 12c (v1.0.1) — D-8 shared bulk-select header.
 *
 * Three buttons (All / None / Invert) + a count chip. Component owns NO
 * list rendering — the caller renders the list and the checkboxes; this
 * is the header row that drives mass selection. Keeping the contract
 * narrow lets Phase 13d (H-2 hypothesis paper-picker bulk-select) reuse
 * the same primitive without coupling to either domain's row shape.
 *
 * Usage (regression column-picker, see stat-test-picker.tsx):
 *   <BulkSelect
 *     items={availablePredictors}
 *     keyOf={(c) => c}
 *     selectedKeys={new Set(predictorCols)}
 *     onChange={(next) => setPredictorCols(Array.from(next))}
 *     label="columns"
 *   />
 */
export type BulkSelectProps<T> = {
  items: T[];
  selectedKeys: Set<string>;
  keyOf: (item: T) => string;
  onChange: (next: Set<string>) => void;
  className?: string;
  /** Used in the count chip — "Selected: N of M {label}". Defaults to "items". */
  label?: string;
};

export function BulkSelect<T>({
  items,
  selectedKeys,
  keyOf,
  onChange,
  className,
  label = "items",
}: BulkSelectProps<T>) {
  const allKeys = useMemo(() => items.map(keyOf), [items, keyOf]);
  const total = allKeys.length;
  const selectedCount = useMemo(
    () => allKeys.filter((k) => selectedKeys.has(k)).length,
    [allKeys, selectedKeys],
  );

  const selectAll = () => onChange(new Set(allKeys));
  const selectNone = () => onChange(new Set<string>());
  const invert = () => {
    const next = new Set<string>();
    for (const k of allKeys) {
      if (!selectedKeys.has(k)) next.add(k);
    }
    onChange(next);
  };

  const btnCls =
    "mono text-[10px] uppercase tracking-wider px-2 py-0.5 border border-border-dim rounded text-text-dim hover:border-accent hover:text-accent disabled:opacity-40 disabled:cursor-not-allowed";

  return (
    <div
      className={`flex items-center justify-between gap-2 text-xs ${className ?? ""}`}
      data-testid="bulk-select"
    >
      <div className="flex gap-1.5">
        <button
          type="button"
          onClick={selectAll}
          disabled={selectedCount === total || total === 0}
          data-action="bulk-all"
          className={btnCls}
        >
          All
        </button>
        <button
          type="button"
          onClick={selectNone}
          disabled={selectedCount === 0}
          data-action="bulk-none"
          className={btnCls}
        >
          None
        </button>
        <button
          type="button"
          onClick={invert}
          disabled={total === 0}
          data-action="bulk-invert"
          className={btnCls}
        >
          Invert
        </button>
      </div>
      <span
        className="mono text-[10px] tracking-wider text-text-muted"
        data-testid="bulk-count"
        data-selected={selectedCount}
        data-total={total}
      >
        Selected: {selectedCount} of {total} {label}
      </span>
    </div>
  );
}
