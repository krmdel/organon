"use client";

import type { DataframeArtifact } from "@/lib/artifacts/types";
import { cn } from "@/lib/cn";

export type DataFileListProps = {
  files: DataframeArtifact[];
  activeFileId: string | null;
  onSelect: (fileId: string) => void;
  onRemove: (fileId: string) => void;
};

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function formatRelative(iso: string | undefined): string {
  if (!iso) return "";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const diff = Date.now() - t;
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function DataFileList({
  files,
  activeFileId,
  onSelect,
  onRemove,
}: DataFileListProps) {
  if (files.length === 0) {
    return (
      <div className="px-4 py-6 text-xs text-text-muted">
        No files yet. Drop a CSV / XLSX / JSON above to get started.
      </div>
    );
  }

  return (
    <ul className="divide-y divide-border-dim">
      {files.map((f) => {
        const isActive = f.id === activeFileId;
        return (
          <li
            key={f.id}
            className={cn(
              "group px-4 py-3 cursor-pointer transition",
              isActive ? "bg-accent-faint" : "hover:bg-bg-soft",
            )}
            onClick={() => onSelect(f.id)}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <div
                  className={cn(
                    "text-sm truncate",
                    isActive ? "text-text" : "text-text-dim",
                  )}
                  title={f.filename}
                >
                  {f.filename}
                </div>
                <div className="mono text-[11px] text-text-muted mt-0.5">
                  {f.rows_total.toLocaleString()} rows · {f.columns.length} cols ·{" "}
                  {formatBytes(f.size_bytes)} · {formatRelative(f.uploaded_at)}
                </div>
              </div>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  if (window.confirm(`Remove ${f.filename} and its preview?`)) {
                    onRemove(f.id);
                  }
                }}
                className="opacity-0 group-hover:opacity-100 text-text-muted hover:text-danger text-xs mono px-1.5 py-0.5"
                title="Remove file"
              >
                ×
              </button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
