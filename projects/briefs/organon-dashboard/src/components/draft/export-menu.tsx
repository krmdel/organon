"use client";

import { useEffect, useState } from "react";
import {
  listPresets,
  type TypographyPreset,
} from "@/lib/draft/typography-presets";

export type ExportFormat = "markdown" | "pdf" | "html" | "docx" | "substack";

// Phase 17 (v1.1+) — Pandoc preflight panel state (B3). Discriminated by
// the `state` tag so consumers can `switch` over the four branches.
export type PdfPreflightState =
  | null
  | { state: "checking" }
  | { state: "available"; version: string }
  | { state: "unavailable"; install_hint: string; error?: string };

export type PdfPreflightResponse = {
  available: boolean;
  version?: string;
  install_hint: string;
  error?: string;
};

export type ExportMenuProps = {
  onExport: (format: ExportFormat) => Promise<void> | void;
  // Phase 17 (v1.1+) — workspace-owned preflight fetch. When provided,
  // clicking PDF fires the probe first and surfaces the preflight panel
  // before kicking off the export. Fallback: when omitted, PDF goes
  // straight to onExport (same behaviour as pre-Phase-17).
  onPdfPreflight?: () => Promise<PdfPreflightResponse>;
  // Phase 18 (v1.1+) — workspace-owned typography preset state. The
  // dropdown applies to PDF + DOCX only (markdown/html/substack ignore
  // it). When omitted, the menu hides the dropdown entirely.
  presetId?: string;
  onPresetChange?: (id: string) => void;
  // Phase 25 (v1.2) — DR-8+ project-scoped preset slug. When provided,
  // the menu fetches /api/draft/typography-presets?project=<slug> on
  // open so it can label project entries with a "● custom" chip.
  // Builtin-only menus (no project context) skip the fetch and use
  // listPresets() in builtin mode.
  projectSlug?: string;
  busy?: ExportFormat | null;
};

const FORMATS: { value: ExportFormat; label: string; hint: string }[] = [
  { value: "markdown", label: "Markdown", hint: "Always works" },
  { value: "pdf",      label: "PDF",      hint: "Pandoc + xelatex" },
  { value: "html",     label: "HTML",     hint: "Marp" },
  { value: "docx",     label: "DOCX",     hint: "Pandoc" },
  { value: "substack", label: "Substack", hint: "tool-substack — currently markdown stub" },
];

export function ExportMenu({
  onExport,
  onPdfPreflight,
  presetId,
  onPresetChange,
  projectSlug,
  busy,
}: ExportMenuProps) {
  const [open, setOpen] = useState(false);
  const [pdfPreflight, setPdfPreflight] = useState<PdfPreflightState>(null);
  // Phase 25 (v1.2) — fetched split builtin / project list. Falls back
  // to the builtin-only listPresets() when no projectSlug is wired or
  // the fetch fails.
  const [presets, setPresets] = useState<TypographyPreset[]>(() => listPresets());
  const showPresetPicker = typeof presetId === "string" && typeof onPresetChange === "function";

  useEffect(() => {
    if (!showPresetPicker || !projectSlug) return;
    let cancelled = false;
    void (async () => {
      try {
        const res = await fetch(
          `/api/draft/typography-presets?project=${encodeURIComponent(projectSlug)}`,
        );
        if (!res.ok) return;
        const json = (await res.json()) as {
          builtin?: TypographyPreset[];
          project?: TypographyPreset[];
        };
        if (cancelled) return;
        const builtin = (json.builtin ?? []).map((p) => ({ ...p, source: "builtin" as const }));
        const project = (json.project ?? []).map((p) => ({ ...p, source: "project" as const }));
        const projectById = new Map(project.map((p) => [p.id, p]));
        const merged: TypographyPreset[] = builtin.map((b) => projectById.get(b.id) ?? b);
        for (const p of project) {
          if (!builtin.some((b) => b.id === p.id)) merged.push(p);
        }
        setPresets(merged);
      } catch {
        /* fall through to builtin-only */
      }
    })();
    return () => { cancelled = true; };
  }, [showPresetPicker, projectSlug]);

  async function runPdfPreflight(): Promise<void> {
    if (!onPdfPreflight) {
      // No workspace-side probe wired — fall through to direct export.
      setOpen(false);
      await onExport("pdf");
      return;
    }
    setPdfPreflight({ state: "checking" });
    try {
      const res = await onPdfPreflight();
      if (res.available) {
        setPdfPreflight({ state: "available", version: res.version ?? "" });
        setOpen(false);
        await onExport("pdf");
        // Reset after a successful export attempt — the panel only
        // sticks while we still need the user to make a decision.
        setPdfPreflight(null);
      } else {
        setPdfPreflight({
          state: "unavailable",
          install_hint: res.install_hint,
          error: res.error,
        });
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "preflight failed";
      setPdfPreflight({
        state: "unavailable",
        install_hint: "",
        error: msg,
      });
    }
  }

  async function runAnyway(): Promise<void> {
    setPdfPreflight(null);
    setOpen(false);
    await onExport("pdf");
  }

  async function switchToMarkdown(): Promise<void> {
    setPdfPreflight(null);
    setOpen(false);
    await onExport("markdown");
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        disabled={!!busy}
        className="text-xs mono uppercase tracking-wider px-3 py-1 border border-accent text-accent hover:bg-accent-faint rounded disabled:opacity-50"
      >
        {busy ? `Exporting ${busy}…` : "Export ▾"}
      </button>
      {open && !busy && (
        <div className="absolute right-0 z-10 mt-1 w-64 border border-border bg-bg-elev rounded shadow-2xl">
          {showPresetPicker && (
            <div className="px-3 py-2 border-b border-border-dim">
              <label
                htmlFor="export-preset-picker"
                className="block mono text-[10px] uppercase tracking-wider text-text-muted"
              >
                Style (PDF + DOCX)
              </label>
              <select
                id="export-preset-picker"
                data-preset-picker
                value={presetId}
                onChange={(e) => onPresetChange?.(e.target.value)}
                className="mt-1 w-full bg-bg-soft border border-border-dim rounded text-sm px-2 py-1 text-text"
              >
                {presets.map((p) => (
                  <option
                    key={p.id}
                    value={p.id}
                    data-preset-source={p.source ?? "builtin"}
                  >
                    {p.source === "project" ? `${p.label} ● custom` : p.label}
                  </option>
                ))}
              </select>
            </div>
          )}
          <ul>
          {FORMATS.map((f) => (
            <li key={f.value}>
              <button
                type="button"
                data-format={f.value}
                onClick={async () => {
                  if (f.value === "pdf") {
                    await runPdfPreflight();
                  } else {
                    setOpen(false);
                    await onExport(f.value);
                  }
                }}
                className="w-full text-left px-3 py-2 text-sm hover:bg-bg-soft border-b border-border-dim last:border-b-0"
              >
                <div className="text-text">{f.label}</div>
                <div className="mono text-[10px] text-text-muted">{f.hint}</div>
              </button>
            </li>
          ))}
          </ul>
        </div>
      )}
      {/* Phase 17 (v1.1+) — preflight panel surface. Stays visible until
          the user picks an action (Run anyway / Switch to Markdown /
          Dismiss). The `checking` state is brief — usually < 100ms. */}
      {pdfPreflight && (
        <div
          data-pdf-preflight
          data-pdf-preflight-state={pdfPreflight.state}
          className="absolute right-0 z-20 mt-1 w-80 border border-border bg-bg-elev rounded shadow-2xl p-3 text-xs"
        >
          {pdfPreflight.state === "checking" && (
            <div className="text-text-muted mono">Checking pandoc…</div>
          )}
          {pdfPreflight.state === "available" && (
            <div className="text-text">
              <div className="mono uppercase tracking-wider text-[10px] text-accent">Pandoc OK</div>
              <div className="mt-1">Version {pdfPreflight.version}. Exporting…</div>
            </div>
          )}
          {pdfPreflight.state === "unavailable" && (
            <div>
              <div className="mono uppercase tracking-wider text-[10px] text-danger">
                Pandoc not detected
              </div>
              <p className="mt-2 text-text">
                The PDF export needs pandoc + xelatex. Install via:
              </p>
              <pre
                data-pdf-install-hint
                className="mt-2 px-2 py-1 bg-bg-soft border border-border-dim rounded mono text-[11px] whitespace-pre-wrap"
              >
                {pdfPreflight.install_hint || "(no platform-specific hint available)"}
              </pre>
              {pdfPreflight.error && (
                <div className="mt-2 mono text-[10px] text-text-muted">{pdfPreflight.error}</div>
              )}
              <div className="mt-3 flex gap-2">
                <button
                  type="button"
                  data-action="run-anyway"
                  onClick={runAnyway}
                  className="px-2 py-1 border border-border text-text-muted hover:text-text rounded text-[11px]"
                >
                  Run anyway
                </button>
                <button
                  type="button"
                  data-action="switch-to-markdown"
                  onClick={switchToMarkdown}
                  className="px-2 py-1 border border-accent text-accent hover:bg-accent-faint rounded text-[11px]"
                >
                  Switch to Markdown
                </button>
                <button
                  type="button"
                  data-action="dismiss-preflight"
                  onClick={() => setPdfPreflight(null)}
                  className="ml-auto px-2 py-1 text-text-muted hover:text-text rounded text-[11px]"
                >
                  Dismiss
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
