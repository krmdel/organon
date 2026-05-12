"use client";

import { useState } from "react";
import type { FigureArtifact } from "@/lib/artifacts/types";

export type PlotRendererProps = {
  figure: FigureArtifact;
  project: string;
};

export function PlotRenderer({ figure, project }: PlotRendererProps) {
  const [copied, setCopied] = useState(false);
  const fileName = (p: string | null | undefined): string =>
    p ? p.split("/").pop() ?? "" : "";
  const fileUrl = (basename: string) =>
    `/api/figures/${encodeURIComponent(figure.id)}/${encodeURIComponent(basename)}?project=${encodeURIComponent(project)}`;

  const pngUrl = fileUrl(fileName(figure.png_path) || "v1.png");
  const svgUrl = figure.svg_path ? fileUrl(fileName(figure.svg_path)) : null;
  const codeUrl = figure.code_path ? fileUrl(fileName(figure.code_path)) : null;

  const copyCode = async () => {
    if (!codeUrl) return;
    try {
      const res = await fetch(codeUrl);
      const text = await res.text();
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard failure — silent */
    }
  };

  return (
    <div className="border border-border-dim rounded bg-bg-elev overflow-hidden">
      <div className="px-4 py-2 border-b border-border-dim flex items-center justify-between">
        <div>
          <div className="mono text-[10px] uppercase tracking-wider text-text-muted">
            Figure · {figure.id}
          </div>
          <div className="text-sm text-text mt-0.5">
            {String(figure.params.plot_kind ?? figure.kind)} · {figure.backend}
          </div>
        </div>
        <div className="flex gap-2">
          {svgUrl && (
            <a
              href={svgUrl}
              target="_blank"
              rel="noopener"
              className="text-xs mono uppercase tracking-wider px-2 py-1 border border-border-dim text-text-dim hover:text-text rounded"
            >
              SVG
            </a>
          )}
          {codeUrl && (
            <button
              type="button"
              onClick={copyCode}
              className="text-xs mono uppercase tracking-wider px-2 py-1 border border-border-dim text-text-dim hover:text-text rounded"
            >
              {copied ? "✓ copied" : "Copy code"}
            </button>
          )}
        </div>
      </div>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={pngUrl}
        alt={figure.alt_text ?? `Figure ${figure.id}`}
        className="w-full bg-bg"
      />
    </div>
  );
}
