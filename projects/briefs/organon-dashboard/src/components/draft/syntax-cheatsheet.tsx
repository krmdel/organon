"use client";

import { useState } from "react";
import { cn } from "@/lib/cn";

/**
 * Phase 10 hotfix (N4 — researcher-found gap on 2026-05-07): a small
 * cheatsheet that surfaces the dashboard-flavored markdown subset
 * (KaTeX-subset math, `\cite{}`, `\fig{}`) directly in the editor.
 *
 * The dogfood walk surfaced that researchers don't know whether the
 * preview supports `\bar{x}` or `\overline{x}`, whether `[@Smith2026]`
 * works alongside `\cite{Smith2026}`, etc. The cheatsheet button +
 * popover puts the answer one click away rather than burying it in
 * documentation.
 *
 * Kept lightweight on purpose — no third-party tooltip, no portal.
 * Click toggles; click outside or Escape closes.
 */

export function SyntaxCheatsheet({ className }: { className?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={cn("relative inline-flex", className)}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        title="Markdown + math + cite/fig syntax"
        aria-expanded={open}
        aria-label="Open syntax cheatsheet"
        data-syntax-cheatsheet-button
        className="mono text-[10px] uppercase tracking-wider px-1.5 py-0.5 border border-border-dim text-text-muted hover:text-text rounded"
      >
        ?
      </button>
      {open && (
        <div
          data-syntax-cheatsheet-panel
          className="absolute top-full right-0 mt-1 z-30 w-[420px] max-w-[90vw] border border-border-dim bg-bg-elev rounded shadow-xl p-3 text-[12px] text-text-dim space-y-2"
          onMouseLeave={() => setOpen(false)}
        >
          <div className="flex items-center justify-between">
            <span className="mono text-[10px] uppercase tracking-wider text-text-muted">
              Syntax cheatsheet
            </span>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="mono text-[10px] uppercase tracking-wider text-text-muted hover:text-text"
            >
              close
            </button>
          </div>

          <CheatRow label="Citation" example="\\cite{Smith2026}" hint="Resolves to (Smith, 2026) per citation_style." />
          <CheatRow label="Multi-cite" example="\\cite{Smith2026,Doe2025}" hint="Comma-separated; rendered grouped." />
          <CheatRow label="Figure" example="\\fig{fig-7}" hint="Resolves to Figure N (numbered at export)." />
          <CheatRow label="Inline math" example="$\\Delta x = \\bar{x}_2 - \\bar{x}_1$" hint="KaTeX subset: \\bar \\hat \\tilde \\vec, \\Delta \\sigma \\mu, \\pm, \\frac, \\sqrt." />
          <CheatRow label="Display math" example="$$\\bar{x} \\pm 2\\sigma$$" hint="Centered block; same KaTeX subset." />
          <CheatRow label="Heading" example="## Methods" hint="One `## <Type>` per body section; the validator enforces it." />
          <CheatRow label="Bold / italic" example="**emphatic** _hedged_" hint="Standard markdown; preserved through the renderer." />
          <CheatRow label="Code span" example="`literal \\cite{X}`" hint="Inside backticks, cite/fig tokens are NOT collected as references — Phase 9 hotfix." />
          <CheatRow label="Footnote" example="text[^1]\n\n[^1]: Note." hint="Markdown footnotes; numbered at render." />
        </div>
      )}
    </div>
  );
}

function CheatRow({
  label,
  example,
  hint,
}: {
  label: string;
  example: string;
  hint: string;
}) {
  return (
    <div className="grid grid-cols-[max-content_1fr] gap-x-2 gap-y-0">
      <div className="mono text-[10px] uppercase tracking-wider text-text-muted pt-0.5">
        {label}
      </div>
      <div className="font-mono text-[11px] text-text bg-bg rounded px-1.5 py-0.5 break-all">
        {example}
      </div>
      <div />
      <div className="text-[11px] text-text-muted">{hint}</div>
    </div>
  );
}
