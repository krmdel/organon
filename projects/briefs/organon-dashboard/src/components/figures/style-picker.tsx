"use client";

import { cn } from "@/lib/cn";

export type Style = "scientific" | "notebook" | "comic" | "color" | "mono" | "technical";
export type SubStyle = "publication" | "conceptual" | "schematic" | "data-driven";

export type StylePickerProps = {
  value: Style | null;
  subValue?: SubStyle | null;
  onChange: (s: Style) => void;
  onSubChange?: (s: SubStyle) => void;
};

const STYLES: { value: Style; label: string; hint: string }[] = [
  { value: "scientific", label: "scientific", hint: "Publication figures, schematics, mechanisms" },
  { value: "notebook",   label: "notebook",   hint: "Educational, hand-drawn sketchnote" },
  { value: "comic",      label: "comic",      hint: "Sequence / story panels" },
  { value: "color",      label: "color",      hint: "Editorial / outreach infographic" },
  { value: "mono",       label: "mono",       hint: "Minimalist / technical / dark mode" },
  { value: "technical",  label: "technical",  hint: "Architecture, workflow, annotation" },
];

const SUB_STYLES: { value: SubStyle; label: string }[] = [
  { value: "publication", label: "Publication" },
  { value: "conceptual",  label: "Conceptual" },
  { value: "schematic",   label: "Schematic" },
  { value: "data-driven", label: "Data-driven" },
];

// Phase 7 T6.9 — these styles MUST have a sub-style for the
// viz-nano-banana skill to produce a coherent prompt. The PromptForm reads
// this list to gate the GENERATE button; the server route rejects with 400
// if `sub_style` is missing for any of them.
export const STYLES_REQUIRING_SUB: Style[] = ["scientific", "technical"];

export function styleRequiresSub(style: Style | null | undefined): boolean {
  return !!style && STYLES_REQUIRING_SUB.includes(style);
}

export function StylePicker({ value, subValue, onChange, onSubChange }: StylePickerProps) {
  const subRequired = styleRequiresSub(value);
  return (
    <div className="space-y-3">
      <div>
        <div className="mono text-[10px] uppercase tracking-wider text-text-muted">Style (required)</div>
        <div className="mt-1 grid grid-cols-2 gap-1.5">
          {STYLES.map((s) => (
            <button
              key={s.value}
              type="button"
              onClick={() => onChange(s.value)}
              className={cn(
                "text-left text-sm px-3 py-2 rounded border transition",
                value === s.value
                  ? "border-accent bg-accent-faint text-text"
                  : "border-border-dim text-text-dim hover:border-accent/50 hover:text-text",
              )}
            >
              <div>{s.label}</div>
              <div className="mono text-[10px] text-text-muted truncate">{s.hint}</div>
            </button>
          ))}
        </div>
      </div>
      {subRequired && onSubChange && (
        <div>
          <div className="mono text-[10px] uppercase tracking-wider text-text-muted">
            Sub-style {!subValue && <span className="text-danger normal-case">*</span>}
          </div>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {SUB_STYLES.map((s) => (
              <button
                key={s.value}
                type="button"
                onClick={() => onSubChange(s.value)}
                className={cn(
                  "text-xs mono uppercase tracking-wider px-2 py-1 border rounded",
                  subValue === s.value
                    ? "border-accent text-accent bg-accent-faint"
                    : "border-border-dim text-text-dim hover:text-text hover:border-accent/50",
                )}
              >
                {s.label}
              </button>
            ))}
          </div>
          {!subValue && (
            <p className="mono text-[10px] text-text-muted mt-1">
              Pick a sub-style — the prompt is too underspecified without one.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
