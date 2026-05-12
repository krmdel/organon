"use client";

import { useCallback, useRef, useState } from "react";
import type { DataframeArtifact } from "@/lib/artifacts/types";
import { cn } from "@/lib/cn";

const ACCEPT = ".csv,.xlsx,.xls,.json";

export type FileUploaderProps = {
  project: string;
  onUploaded: (df: DataframeArtifact) => void;
};

export function FileUploader({ project, onUploaded }: FileUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<string | null>(null);

  const upload = useCallback(
    async (file: File) => {
      setError(null);
      setBusy(true);
      setProgress(`Uploading ${file.name} (${(file.size / 1024).toFixed(0)} KB)…`);
      try {
        const form = new FormData();
        form.set("file", file);
        form.set("project", project);
        const res = await fetch("/api/data/load", { method: "POST", body: form });
        const json = await res.json();
        if (!res.ok) throw new Error(json?.error ?? `HTTP ${res.status}`);
        if (!json?.dataframe) throw new Error("server returned no dataframe");
        onUploaded(json.dataframe as DataframeArtifact);
        setProgress(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        setProgress(null);
      } finally {
        setBusy(false);
      }
    },
    [project, onUploaded],
  );

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return;
      // Sequential — keeps server log readable + avoids contention on the venv.
      void Array.from(files).reduce(
        (acc, f) => acc.then(() => upload(f)),
        Promise.resolve(),
      );
    },
    [upload],
  );

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        handleFiles(e.dataTransfer.files);
      }}
      className={cn(
        "rounded border-2 border-dashed transition px-6 py-8 text-center",
        dragOver
          ? "border-accent bg-accent-faint text-text"
          : "border-border-dim bg-bg-elev text-text-dim",
        busy && "opacity-70 pointer-events-none",
      )}
    >
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        multiple
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
      {/* Phase 12c (v1.0.1) — D-5: cloud-up upload glyph (Lucide-style
         inline SVG so we don't pull in a new icon dep). Stroke-based so
         it inherits color from the parent container, dim resting state
         on text-text-muted. */}
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="w-7 h-7 mx-auto mb-2 text-text-muted"
        aria-hidden="true"
        data-testid="upload-icon"
      >
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        <polyline points="17 8 12 3 7 8" />
        <line x1="12" y1="3" x2="12" y2="15" />
      </svg>
      <div className="mono text-[11px] uppercase tracking-[0.2em] text-text-muted mb-2">
        Drop or pick
      </div>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        className="text-sm text-text underline decoration-dotted"
        disabled={busy}
      >
        choose a file
      </button>
      <div className="mt-1 text-xs text-text-muted">
        CSV / XLSX / XLS / JSON · up to 200 MB
      </div>
      {progress && (
        <div className="mt-3 text-xs text-text-dim mono">{progress}</div>
      )}
      {error && (
        <div className="mt-3 text-xs text-danger mono">⚠ {error}</div>
      )}
    </div>
  );
}
