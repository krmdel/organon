"use client";

import type { ToolCatalogEntry } from "@/lib/tools/catalog";
import { cn } from "@/lib/cn";

export type ToolCardProps = {
  tool: ToolCatalogEntry;
  isFavourite: boolean;
  onSelect: () => void;
  onToggleFavourite: () => void;
  active?: boolean;
};

const SOURCE_TONE: Record<string, string> = {
  skill: "border-accent text-accent",
  mcp:   "border-good text-good",
};

export function ToolCard({ tool, isFavourite, onSelect, onToggleFavourite, active }: ToolCardProps) {
  return (
    <li
      className={cn(
        "group px-3 py-2 cursor-pointer border-b border-border-dim",
        active ? "bg-accent-faint" : "hover:bg-bg-soft",
      )}
      onClick={onSelect}
    >
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className={cn("text-sm truncate", active ? "text-text" : "text-text-dim")}>{tool.name}</span>
            <span className={cn("mono text-[10px] uppercase tracking-wider px-1.5 py-0.5 border rounded", SOURCE_TONE[tool.source] ?? "border-border-dim text-text-muted")}>
              {tool.source}
            </span>
          </div>
          <div className="mono text-[10px] text-text-muted mt-0.5 truncate">{tool.category} · {tool.id}</div>
          <div className="text-xs text-text-dim mt-1 line-clamp-2">{tool.description}</div>
        </div>
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onToggleFavourite(); }}
          className={cn(
            "mono text-sm px-1",
            isFavourite ? "text-accent" : "text-text-muted hover:text-text opacity-0 group-hover:opacity-100",
          )}
          title={isFavourite ? "Unpin" : "Pin to favourites"}
        >
          {isFavourite ? "★" : "☆"}
        </button>
      </div>
    </li>
  );
}
