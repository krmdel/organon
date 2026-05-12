"use client";

import { useMemo } from "react";
import type { ColumnType, DataframeArtifact } from "@/lib/artifacts/types";
import { ColumnHeader } from "./column-header";

export type DataframePreviewProps = {
  dataframe: DataframeArtifact;
  onColumnTypeChange?: (col: string, next: ColumnType) => void;
  busy?: boolean;
};

export function DataframePreview({
  dataframe,
  onColumnTypeChange,
  busy,
}: DataframePreviewProps) {
  const columnNames = useMemo(() => dataframe.columns.map((c) => c.name), [dataframe]);
  const previewCount = dataframe.preview_rows.length;
  const totalRows = dataframe.rows_total;

  return (
    <div className="border border-border-dim rounded overflow-hidden bg-bg-elev">
      <div className="px-4 py-3 border-b border-border-dim flex items-center justify-between">
        <div>
          <div className="text-sm text-text">{dataframe.filename}</div>
          <div className="mono text-[11px] text-text-muted mt-0.5">
            {totalRows.toLocaleString()} rows × {dataframe.columns.length} columns
            {previewCount < totalRows && ` · showing first ${previewCount}`}
          </div>
        </div>
        <div className="mono text-[10px] uppercase tracking-wider text-text-muted">
          {dataframe.format}
        </div>
      </div>
      <div className="overflow-auto max-h-[60vh]">
        <table className="w-full border-collapse">
          <thead className="sticky top-0 bg-bg-elev z-10">
            <tr>
              {dataframe.columns.map((col) => (
                <th
                  key={col.name}
                  className="border-b border-border-dim align-bottom"
                >
                  <ColumnHeader
                    column={col}
                    onChangeType={
                      onColumnTypeChange
                        ? (next) => onColumnTypeChange(col.name, next)
                        : undefined
                    }
                    busy={busy}
                  />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {dataframe.preview_rows.map((row, idx) => (
              <tr
                key={idx}
                className={idx % 2 === 0 ? "bg-bg" : "bg-bg-elev"}
              >
                {columnNames.map((name) => (
                  <td
                    key={name}
                    className="px-3 py-1.5 mono text-[11px] text-text-dim border-b border-border-dim/30 whitespace-nowrap max-w-[280px] overflow-hidden text-ellipsis"
                    title={row[name] ?? ""}
                  >
                    {row[name] === "" ? (
                      <span className="text-text-muted italic">—</span>
                    ) : (
                      row[name]
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
