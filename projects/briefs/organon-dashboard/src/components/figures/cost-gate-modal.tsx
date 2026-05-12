"use client";

import { useEffect, useState } from "react";

export type CostGateModalProps = {
  open: boolean;
  estimateCents: number;
  onConfirm: (rememberSession: boolean) => void;
  onCancel: () => void;
};

export function CostGateModal({ open, estimateCents, onConfirm, onCancel }: CostGateModalProps) {
  const [remember, setRemember] = useState(false);
  useEffect(() => {
    if (!open) setRemember(false);
  }, [open]);
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4"
      onClick={onCancel}
    >
      <div
        className="w-full max-w-sm rounded border border-border bg-bg-elev p-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mono text-[10px] uppercase tracking-[0.2em] text-text-muted">
          Pre-fire confirmation
        </div>
        <div className="text-base text-text mt-2">
          This edit will cost ~${(estimateCents / 100).toFixed(2)} (FAL FLUX.1 Pro Fill).
        </div>
        <p className="mt-1 text-xs text-text-dim">
          The cost is a function of the masked region size. Cumulative session
          spend is shown in the topbar.
        </p>
        <label className="mt-3 flex items-center gap-2 text-xs text-text-dim">
          <input
            type="checkbox"
            checked={remember}
            onChange={(e) => setRemember(e.target.checked)}
            className="accent-accent"
          />
          Don't ask again this session
        </label>
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="text-xs mono uppercase tracking-wider px-3 py-1 border border-border-dim text-text-dim hover:text-text rounded"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onConfirm(remember)}
            className="text-xs mono uppercase tracking-wider px-3 py-1 border border-accent text-accent hover:bg-accent-faint rounded"
          >
            Confirm + edit
          </button>
        </div>
      </div>
    </div>
  );
}
