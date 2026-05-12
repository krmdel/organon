"use client";

import { useEffect, useState } from "react";
import {
  MAX_PERSONAS,
  getDefaultPersonas,
  getMathTemplatePersonas,
  type Persona,
} from "@/lib/hypothesis/shared";

export type PersonasEditorProps = {
  initial: Persona[];
  onSave: (personas: Persona[]) => Promise<void> | void;
  onClose?: () => void;
};

export function PersonasEditor({ initial, onSave, onClose }: PersonasEditorProps) {
  const [personas, setPersonas] = useState<Persona[]>(() => initial.map((p) => ({ ...p })));
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setPersonas(initial.map((p) => ({ ...p })));
  }, [initial]);

  const update = (idx: number, patch: Partial<Persona>) => {
    setPersonas((cur) => cur.map((p, i) => (i === idx ? { ...p, ...patch } : p)));
  };

  const remove = (idx: number) => {
    setPersonas((cur) => cur.filter((_, i) => i !== idx));
  };

  const move = (idx: number, dir: -1 | 1) => {
    setPersonas((cur) => {
      const j = idx + dir;
      if (j < 0 || j >= cur.length) return cur;
      const copy = [...cur];
      const tmp = copy[idx];
      copy[idx] = copy[j];
      copy[j] = tmp;
      return copy;
    });
  };

  const add = () => {
    if (personas.length >= MAX_PERSONAS) return;
    // Phase 13a: new personas default to active so the council fanout
    // picks them up on the next run without an extra click.
    setPersonas((cur) => [...cur, { name: `Persona ${cur.length + 1}`, role: "", active: true }]);
  };

  // Phase 13a (H-3): Reset-to-defaults destroys the user's customizations
  // (names, roles, avatars, active flags). Surface a confirm before the
  // clobber so an accidental click does not blow away an entire setup.
  const confirmAndReset = (next: Persona[]) => {
    if (typeof window !== "undefined") {
      const ok = window.confirm(
        "This will reset all personas to the template, including their active state. Continue?",
      );
      if (!ok) return;
    }
    setPersonas(next);
  };

  const handleSave = async () => {
    setError(null);
    const cleaned = personas
      .map((p) => ({
        name: p.name.trim(),
        role: p.role?.trim() || undefined,
        avatar: p.avatar?.trim() || p.name.trim().slice(0, 1).toUpperCase(),
        // Phase 13a (H-4): preserve the active flag on save; default to
        // true if it was somehow undefined (defensive — the editor sets
        // it explicitly on every state mutation).
        active: typeof p.active === "boolean" ? p.active : true,
      }))
      .filter((p) => p.name.length > 0);
    if (cleaned.length === 0) {
      setError("Need at least one persona");
      return;
    }
    const seen = new Set<string>();
    for (const p of cleaned) {
      const key = p.name.toLowerCase();
      if (seen.has(key)) {
        setError(`Duplicate persona: ${p.name}`);
        return;
      }
      seen.add(key);
    }
    setSaving(true);
    try {
      await onSave(cleaned);
      onClose?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="border border-border-dim rounded bg-bg-elev p-4 space-y-4">
      <header className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold">Personas</h3>
          <p className="mono text-[10px] text-text-muted mt-0.5">
            Up to {MAX_PERSONAS}. Each becomes one critique panel during council fanout.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => confirmAndReset(getDefaultPersonas())}
            data-action="reset-defaults"
            className="mono text-[10px] uppercase tracking-wider px-2 py-1 border border-border rounded text-text-dim hover:text-text"
          >
            Defaults
          </button>
          <button
            onClick={() => confirmAndReset(getMathTemplatePersonas())}
            data-action="reset-math-template"
            className="mono text-[10px] uppercase tracking-wider px-2 py-1 border border-border rounded text-text-dim hover:text-text"
          >
            Math template
          </button>
        </div>
      </header>

      <div className="space-y-2">
        {personas.map((p, i) => (
          <div
            key={i}
            className="flex items-center gap-2"
            data-persona-row
            data-active={p.active !== false ? "true" : "false"}
          >
            <div className="flex flex-col">
              <button
                onClick={() => move(i, -1)}
                disabled={i === 0}
                className="text-text-muted hover:text-text disabled:opacity-30 mono text-[10px]"
              >
                ▲
              </button>
              <button
                onClick={() => move(i, 1)}
                disabled={i === personas.length - 1}
                className="text-text-muted hover:text-text disabled:opacity-30 mono text-[10px]"
              >
                ▼
              </button>
            </div>
            {/* Phase 13a (H-4): active checkbox. Unchecked → persona is
                preserved here for restoration but skipped on the next
                council fanout. Distinct from Remove (which deletes the
                row outright). */}
            <label
              className="flex items-center gap-1 cursor-pointer select-none"
              title={p.active !== false ? "Active — fires on next council run" : "Inactive — preserved but skipped"}
            >
              <input
                type="checkbox"
                checked={p.active !== false}
                onChange={(e) => update(i, { active: e.target.checked })}
                data-persona-active-toggle
                className="accent-accent"
              />
              <span className="mono text-[10px] uppercase tracking-wider text-text-muted">
                active
              </span>
            </label>
            <input
              type="text"
              value={p.name}
              onChange={(e) => update(i, { name: e.target.value })}
              placeholder="Name"
              className="w-32 bg-bg-soft border border-border-dim rounded px-2 py-1 text-sm mono outline-none focus:border-accent"
            />
            <input
              type="text"
              value={p.role ?? ""}
              onChange={(e) => update(i, { role: e.target.value })}
              placeholder="Role / lens"
              className="flex-1 bg-bg-soft border border-border-dim rounded px-2 py-1 text-sm outline-none focus:border-accent"
            />
            <input
              type="text"
              value={p.avatar ?? ""}
              onChange={(e) => update(i, { avatar: e.target.value })}
              placeholder="A"
              maxLength={2}
              className="w-10 bg-bg-soft border border-border-dim rounded px-2 py-1 text-sm mono text-center outline-none focus:border-accent"
            />
            <button
              onClick={() => remove(i)}
              className="text-text-muted hover:text-danger mono text-xs px-1"
              aria-label="Remove persona"
            >
              ✕
            </button>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={add}
          disabled={personas.length >= MAX_PERSONAS}
          className="mono text-[10px] uppercase tracking-wider px-3 py-1.5 border border-border rounded text-text-dim hover:text-text disabled:opacity-50 disabled:cursor-not-allowed"
        >
          + Add persona
        </button>
        {error && <span className="text-danger text-xs">{error}</span>}
        <div className="ml-auto flex gap-2">
          {onClose && (
            <button
              onClick={onClose}
              className="mono text-[10px] uppercase tracking-wider px-3 py-1.5 text-text-dim hover:text-text"
            >
              Cancel
            </button>
          )}
          <button
            onClick={handleSave}
            disabled={saving}
            className="mono text-[10px] uppercase tracking-wider px-3 py-1.5 border border-accent rounded text-accent hover:bg-accent hover:text-bg transition disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save personas"}
          </button>
        </div>
      </div>
    </div>
  );
}
