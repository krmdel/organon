"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { ToolCatalogEntry } from "@/lib/tools/catalog";
import { ToolCard } from "./tool-card";
import { ToolForm } from "./tool-form";

export type ToolsWorkspaceProps = {
  project: string;
  initialCatalog: ToolCatalogEntry[];
  initialFavourites: string[];
};

export function ToolsWorkspace(props: ToolsWorkspaceProps) {
  const [catalog] = useState<ToolCatalogEntry[]>(props.initialCatalog);
  const [favs, setFavs] = useState<Set<string>>(new Set(props.initialFavourites));
  const [query, setQuery] = useState("");
  const [activeId, setActiveId] = useState<string | null>(null);
  const [stream, setStream] = useState<string>("");
  const [artifacts, setArtifacts] = useState<{ _artifact?: string; id?: string }[]>([]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return catalog;
    return catalog.filter((t) => {
      return (
        t.name.toLowerCase().includes(q)
        || t.id.toLowerCase().includes(q)
        || t.description.toLowerCase().includes(q)
        || t.category.toLowerCase().includes(q)
      );
    });
  }, [catalog, query]);

  const favouritesList = useMemo(
    () => filtered.filter((t) => favs.has(t.id)),
    [filtered, favs],
  );

  const active = activeId ? catalog.find((t) => t.id === activeId) ?? null : null;

  const persistFavs = useCallback(async (next: Set<string>) => {
    setFavs(next);
    try {
      await fetch(`/api/tools/favourites?project=${encodeURIComponent(props.project)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ favourites: Array.from(next) }),
      });
    } catch { /* keep local */ }
  }, [props.project]);

  useEffect(() => {
    if (!active) setStream("");
  }, [active]);

  return (
    <div className="flex h-full">
      <aside className="w-[26rem] shrink-0 border-r border-border-dim flex flex-col">
        <div className="px-4 py-3 border-b border-border-dim">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search skills + MCP servers…"
            className="w-full bg-bg border border-border-dim rounded px-3 py-2 text-sm text-text focus:border-accent outline-none"
          />
          <div className="mt-1 mono text-[10px] uppercase tracking-wider text-text-muted">
            {filtered.length} of {catalog.length} tools
          </div>
        </div>
        {favouritesList.length > 0 && (
          <>
            <div className="px-4 py-2 mono text-[10px] uppercase tracking-[0.2em] text-text-muted">
              Pinned
            </div>
            <ul>
              {favouritesList.map((t) => (
                <ToolCard
                  key={`fav-${t.id}`}
                  tool={t}
                  isFavourite
                  active={activeId === t.id}
                  onSelect={() => setActiveId(t.id)}
                  onToggleFavourite={() => {
                    const next = new Set(favs); next.delete(t.id);
                    void persistFavs(next);
                  }}
                />
              ))}
            </ul>
            <div className="border-t border-border-dim" />
          </>
        )}
        <div className="flex-1 overflow-auto">
          <ul>
            {filtered.map((t) => (
              <ToolCard
                key={t.id}
                tool={t}
                isFavourite={favs.has(t.id)}
                active={activeId === t.id}
                onSelect={() => setActiveId(t.id)}
                onToggleFavourite={() => {
                  const next = new Set(favs);
                  if (next.has(t.id)) next.delete(t.id); else next.add(t.id);
                  void persistFavs(next);
                }}
              />
            ))}
          </ul>
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        <div className="px-6 py-5 max-w-[1100px]">
          <header className="mb-5">
            <div className="mono text-[11px] uppercase tracking-[0.2em] text-text-muted">Tools</div>
            <h1 className="text-2xl text-text mt-1">{props.project}</h1>
            <p className="text-sm text-text-dim mt-1">
              Run any registered Organon skill or browse the connected MCP servers. Favourites are per-project.
            </p>
          </header>
          {active ? (
            <div className="space-y-4">
              <ToolForm
                tool={active}
                project={props.project}
                onResultStream={(c) => setStream((s) => (s + c).slice(-4000))}
                onArtifact={(a) => setArtifacts((prev) => [a, ...prev].slice(0, 20))}
              />
              {stream && (
                <pre className="mono text-[11px] text-text-muted bg-bg-elev border border-border-dim rounded p-3 max-h-64 overflow-auto whitespace-pre-wrap">
                  {stream}
                </pre>
              )}
              {artifacts.length > 0 && (
                <div className="border border-border-dim rounded bg-bg-elev px-4 py-3">
                  <div className="mono text-[11px] uppercase tracking-[0.2em] text-text-muted">
                    Emitted artifacts ({artifacts.length})
                  </div>
                  <ul className="mt-2 space-y-1 text-xs">
                    {artifacts.map((a, i) => (
                      <li key={i} className="mono text-text-dim">
                        <span className="text-good">{a._artifact}</span>{a.id ? ` · ${a.id}` : ""}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <div className="border border-dashed border-border-dim rounded px-8 py-16 text-center">
              <div className="mono text-[11px] uppercase tracking-[0.2em] text-text-muted">No tool selected</div>
              <div className="mt-2 text-sm text-text-dim">
                Pick a skill on the left, type a prompt, hit Run.
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
