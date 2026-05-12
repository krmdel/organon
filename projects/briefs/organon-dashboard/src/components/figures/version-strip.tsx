"use client";

import type { FigureArtifact } from "@/lib/artifacts/types";
import { cn } from "@/lib/cn";

export type VersionStripProps = {
  versions: FigureArtifact[];
  activeVersion: number;
  project: string;
  onSelect: (version: number) => void;
};

/**
 * Phase 14c (v1.0.1) — F-3 figure version history strip.
 *
 * Renders v1..vN as a thumbnail strip; v1 is always tagged "original"
 * so a user knows the floor of the edit history at a glance. The
 * latest (highest-numbered) version is the editable head; older
 * versions are read-only — selecting one tells the workspace to lock
 * the canvas (no mask drawing, no edit prompt). The workspace owns
 * the read-only enforcement; this surface just visualises the lineage.
 */
export function VersionStrip({ versions, activeVersion, project, onSelect }: VersionStripProps) {
  if (versions.length === 0) return null;
  // Phase 14c — sorted ascending so v1 (the original) is always
  // leftmost, vN (the editable head) is always rightmost. The caller
  // may pass the array in any order; we own the display order so
  // "original is on the left" stays a contract.
  const sorted = [...versions].sort((a, b) => a.version - b.version);
  const latestVersion = sorted[sorted.length - 1]?.version ?? 1;
  return (
    <div data-version-strip className="flex flex-wrap gap-2">
      {sorted.map((v) => {
        const png = v.png_path.split("/").pop() ?? `v${v.version}.png`;
        const url = `/api/figures/${encodeURIComponent(v.id)}/${encodeURIComponent(png)}?project=${encodeURIComponent(project)}`;
        const isActive = v.version === activeVersion;
        const isOriginal = v.version === 1;
        const isLatest = v.version === latestVersion;
        return (
          <button
            key={v.version}
            type="button"
            onClick={() => onSelect(v.version)}
            data-version={v.version}
            data-original={isOriginal ? "true" : "false"}
            data-latest={isLatest ? "true" : "false"}
            data-active={isActive ? "true" : "false"}
            className={cn(
              "block w-20 overflow-hidden rounded border transition relative",
              isActive ? "border-accent" : "border-border-dim hover:border-accent/50",
            )}
            title={
              isOriginal
                ? `v${v.version} · original${v.locked ? " · locked" : ""}`
                : isLatest
                  ? `v${v.version} · latest${v.locked ? " · locked" : ""}`
                  : `v${v.version}${v.locked ? " · locked" : ""}`
            }
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={url} alt="" className="w-full h-16 object-cover bg-bg" />
            <div className="px-1.5 py-0.5 mono text-[10px] text-text-muted flex items-center justify-between">
              <span>v{v.version}</span>
              {v.locked && <span className="text-good">●</span>}
            </div>
            {(isOriginal || isLatest) && (
              <div
                data-version-label
                className={cn(
                  "absolute top-1 left-1 mono text-[8px] uppercase tracking-wider px-1 py-0.5 rounded",
                  isOriginal ? "bg-bg/80 text-text-muted" : "bg-accent text-bg",
                )}
              >
                {isOriginal ? "orig" : "latest"}
              </div>
            )}
          </button>
        );
      })}
    </div>
  );
}
