"use client";

import { useState } from "react";
import {
  StylePicker,
  styleRequiresSub,
  type Style,
  type SubStyle,
} from "./style-picker";

export type PromptFormProps = {
  onSubmit: (p: { prompt: string; style: Style; sub_style?: SubStyle | null }) => void;
  loading?: boolean;
};

export function PromptForm({ onSubmit, loading }: PromptFormProps) {
  const [prompt, setPrompt] = useState("");
  const [style, setStyle] = useState<Style | null>(null);
  const [subStyle, setSubStyle] = useState<SubStyle | null>(null);
  // Phase 7 T6.9 — Generate stays disabled until sub-style is picked when
  // the chosen style requires one (scientific / technical). Mirrors the
  // server-side 400 check in /api/images/generate.
  const subOk = !styleRequiresSub(style) || !!subStyle;
  const canSubmit = prompt.trim().length > 0 && !!style && subOk && !loading;
  const handleStyleChange = (s: Style) => {
    setStyle(s);
    if (!styleRequiresSub(s)) setSubStyle(null);
  };

  return (
    <div className="border border-border-dim rounded bg-bg-elev px-4 py-3 space-y-3">
      <div className="flex items-center justify-between">
        <div className="mono text-[11px] uppercase tracking-[0.2em] text-text-muted">
          New figure
        </div>
        <button
          type="button"
          onClick={() =>
            canSubmit && onSubmit({ prompt: prompt.trim(), style: style!, sub_style: subStyle })
          }
          disabled={!canSubmit}
          className="text-xs mono uppercase tracking-wider px-3 py-1 border border-accent text-accent hover:bg-accent-faint rounded disabled:opacity-50"
        >
          {loading ? "Generating…" : "Generate"}
        </button>
      </div>
      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder='e.g. "schematic of CRISPR Cas9 binding to target DNA"'
        className="w-full min-h-[88px] bg-bg border border-border-dim rounded px-3 py-2 text-sm text-text focus:border-accent outline-none resize-y"
      />
      <StylePicker
        value={style}
        subValue={subStyle}
        onChange={handleStyleChange}
        onSubChange={setSubStyle}
      />
      {!style && (
        <p className="mono text-[10px] text-text-muted">
          Pick a style — viz-nano-banana never auto-selects.
        </p>
      )}
    </div>
  );
}
