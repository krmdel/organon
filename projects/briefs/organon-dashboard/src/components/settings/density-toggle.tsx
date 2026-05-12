"use client";

import { useEffect, useState } from "react";

// Phase 65 (v2.2) — M4: dashboard density toggle. Four discrete levels
// drive the --font-scale CSS variable on <html>. Tailwind 4 rem-based
// classes scale automatically; no per-component override needed beyond
// the cascade in globals.css.
//
// Persistence: localStorage key 'organon.density'. The pre-hydration
// inline script in src/app/layout.tsx mirrors this on first paint to
// avoid the flash-of-default-density.

const DENSITY_LEVELS = [
  { value: "compact", label: "S", title: "Compact (15px)" },
  { value: "default", label: "M", title: "Default (17px)" },
  { value: "comfortable", label: "L", title: "Comfortable (19px)" },
  { value: "large", label: "XL", title: "Large (21px)" },
] as const;

export type Density = (typeof DENSITY_LEVELS)[number]["value"];

const STORAGE_KEY = "organon.density";

function readPersistedDensity(): Density {
  if (typeof window === "undefined") return "default";
  try {
    const v = window.localStorage.getItem(STORAGE_KEY);
    if (v === "compact" || v === "default" || v === "comfortable" || v === "large") {
      return v;
    }
  } catch { /* private mode / disabled */ }
  return "default";
}

export function DensityToggle() {
  const [density, setDensity] = useState<Density>("default");

  // Hydrate from localStorage / pre-hydration script result on mount.
  useEffect(() => {
    const fromStorage = readPersistedDensity();
    const fromAttr = document.documentElement.getAttribute("data-density") as Density | null;
    setDensity(fromAttr ?? fromStorage);
  }, []);

  const apply = (next: Density) => {
    setDensity(next);
    if (typeof document !== "undefined") {
      if (next === "default") {
        document.documentElement.removeAttribute("data-density");
      } else {
        document.documentElement.setAttribute("data-density", next);
      }
    }
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch { /* private mode */ }
  };

  return (
    <div
      data-density-toggle
      className="hidden md:inline-flex items-center gap-0.5 border border-border-dim rounded mono text-[10px] uppercase tracking-wider"
      role="group"
      aria-label="Dashboard density"
    >
      {DENSITY_LEVELS.map((opt) => {
        const active = density === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => apply(opt.value)}
            data-density-option={opt.value}
            data-active={active ? "true" : "false"}
            title={opt.title}
            className={
              active
                ? "px-2 py-0.5 text-accent bg-accent-faint"
                : "px-2 py-0.5 text-text-muted hover:text-text"
            }
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
