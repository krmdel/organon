"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { cn } from "@/lib/cn";
import { isBiomedicalQuery } from "@/lib/lit/query-class";
import { setCrossRouteQuery } from "@/lib/cross-route-query/store";

// Phase 40 (v1.4) — F3: debounce window for the cross-route query
// persistence. 500ms gives the user a stable typing pause without
// thrashing localStorage on every keystroke.
const CROSS_ROUTE_DEBOUNCE_MS = 500;

export type SearchSource = "pubmed" | "arxiv" | "openalex" | "semanticscholar" | "paperclip";

export type SearchParams = {
  query: string;
  sources: SearchSource[];
  max_results: number;
  publication_date?: string;
  via_skill?: boolean;
};

/**
 * Phase 46 (v1.6) — F9: full-autonomy submission shape. Distinct from
 * SearchParams so callers can route to /api/lit/autonomy when this fires
 * vs. the regular /api/lit/search.
 */
export type AutonomyParams = {
  keywords: string[];
  research_question: string;
};

export type RecentSearchEntry = {
  query: string;
  sources: string[];
  ts: number;
};

export type SearchBarProps = {
  initialQuery?: string;
  initialSources?: SearchSource[];
  onSearch: (params: SearchParams) => void;
  loading?: boolean;
  recentSearches?: RecentSearchEntry[];
  onPickRecent?: (entry: RecentSearchEntry) => void;
  /**
   * Phase 40 (v1.4) — F3: project slug for cross-route query
   * persistence. When supplied, the bar persists the live query
   * (debounced) so /hypothesis can pre-fill the claim textarea.
   * Optional so the surface stays back-compatible.
   */
  project?: string;
  /**
   * Phase 46 (v1.6) — F9: optional autonomy-mode submit handler. When
   * supplied, the bar surfaces an "Autonomy" toggle that reveals a
   * second input for the research question; submitting fires
   * onAutonomySubmit instead of onSearch.
   */
  onAutonomySubmit?: (params: AutonomyParams) => void;
};

// Phase 45 (v1.6) — F8: paperclip joins as a first-class source toggle
// in the bar. The non-arxiv default for biomedical queries auto-includes
// paperclip so the routing layer can short-circuit on threshold.
const ALL_SOURCES: SearchSource[] = ["paperclip", "pubmed", "arxiv", "openalex", "semanticscholar"];
const NON_ARXIV_SOURCES: SearchSource[] = ["paperclip", "pubmed", "openalex", "semanticscholar"];
const SOURCE_LABELS: Record<SearchSource, string> = {
  pubmed: "PubMed",
  arxiv: "arXiv",
  openalex: "OpenAlex",
  semanticscholar: "S2",
  paperclip: "Paperclip",
};

export function SearchBar({
  initialQuery = "",
  initialSources = ALL_SOURCES,
  onSearch,
  loading,
  recentSearches,
  onPickRecent,
  project,
  onAutonomySubmit,
}: SearchBarProps) {
  const [query, setQuery] = useState(initialQuery);
  const [sources, setSources] = useState<SearchSource[]>(initialSources);
  const [maxResults, setMaxResults] = useState(10);
  const [viaSkill, setViaSkill] = useState(false);
  const [recentOpen, setRecentOpen] = useState(false);
  // Phase 46 (v1.6) — F9: full-autonomy mode. When toggled on AND a
  // handler was supplied, submitting fires onAutonomySubmit instead of
  // onSearch. The query input doubles as the comma-separated keyword
  // list when autonomy is active; a second textarea captures the
  // research question.
  const [autonomyEnabled, setAutonomyEnabled] = useState(false);
  const [researchQuestion, setResearchQuestion] = useState("");
  const recentRef = useRef<HTMLDivElement>(null);
  const hasRecents = !!recentSearches && recentSearches.length > 0 && !!onPickRecent;
  // Close the dropdown on outside click so it behaves like a native menu.
  useEffect(() => {
    if (!recentOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (!recentRef.current) return;
      if (recentRef.current.contains(e.target as Node)) return;
      setRecentOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [recentOpen]);
  // Phase 7 T6.10 — track whether the user manually toggled any source.
  // While untouched, the source set auto-derives from the biomedical
  // classifier on the live query (so typing "GLP-1" silently drops arXiv
  // before the user fires the search). The first toggle locks the user's
  // choice — we never auto-flip after that.
  const [sourcesTouched, setSourcesTouched] = useState(false);
  const biomedical = useMemo(() => isBiomedicalQuery(query), [query]);
  useEffect(() => {
    if (sourcesTouched) return;
    setSources(biomedical ? NON_ARXIV_SOURCES : ALL_SOURCES);
  }, [biomedical, sourcesTouched]);

  // Sync external changes (back-forward navigation)
  useEffect(() => {
    setQuery(initialQuery);
  }, [initialQuery]);

  // Phase 40 (v1.4) — F3: debounced cross-route persistence. The
  // hypothesis claim-form reads this value on mount and pre-fills an
  // empty claim textarea so a researcher's lit query carries through
  // to the next stage. Skip when project is unset (back-compat).
  useEffect(() => {
    if (!project) return;
    const t = setTimeout(() => {
      setCrossRouteQuery(project, query, "lit");
    }, CROSS_ROUTE_DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [project, query]);

  // Cmd+Enter submits
  useHotkeys(
    "mod+enter",
    () => {
      if (query.trim()) submit();
    },
    { enableOnFormTags: true },
    [query, sources, maxResults, viaSkill],
  );

  const submit = () => {
    if (!query.trim()) return;
    if (autonomyEnabled && onAutonomySubmit) {
      // Phase 46 (v1.6) — F9: keywords carried in the query input as
      // comma-separated tokens; research_question is the dedicated input.
      const keywords = query
        .split(",")
        .map((s) => s.trim())
        .filter((s) => s.length > 0);
      onAutonomySubmit({ keywords, research_question: researchQuestion.trim() });
      return;
    }
    onSearch({
      query: query.trim(),
      sources: sources.length > 0 ? sources : ALL_SOURCES,
      max_results: maxResults,
      via_skill: viaSkill,
    });
  };

  const toggleSource = (s: SearchSource) => {
    setSourcesTouched(true);
    setSources((cur) => (cur.includes(s) ? cur.filter((x) => x !== s) : [...cur, s]));
  };

  return (
    <div className="border-b border-border-dim bg-bg-elev px-6 py-4">
      <div className="flex items-center gap-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.metaKey && !e.ctrlKey) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder={
            autonomyEnabled
              ? "Keywords (comma-separated) — e.g. GLP-1, obesity, weight regain"
              : "e.g. GLP-1 obesity meta-analysis"
          }
          className="flex-1 px-4 py-2 bg-bg border border-border rounded text-text placeholder:text-text-muted focus:border-accent focus:outline-none"
          disabled={loading}
        />
        <button
          onClick={submit}
          disabled={loading || !query.trim()}
          className={cn(
            "px-4 py-2 border rounded text-sm transition mono uppercase tracking-wider",
            loading
              ? "border-border text-text-muted cursor-wait"
              : "border-accent bg-accent-faint text-accent hover:bg-accent hover:text-bg",
          )}
        >
          {loading ? (autonomyEnabled ? "Curating…" : "Searching…") : autonomyEnabled ? "Curate" : "Search"}
        </button>
      </div>
      {/* Phase 46 (v1.6) — F9: full-autonomy mode reveals a research-question
          input below the keyword bar. Submitting fires onAutonomySubmit
          which the workspace routes to /api/lit/autonomy. */}
      {autonomyEnabled && (
        <div className="mt-3" data-autonomy-question>
          <textarea
            value={researchQuestion}
            onChange={(e) => setResearchQuestion(e.target.value)}
            placeholder="Research question — what are you trying to answer?"
            rows={2}
            className="w-full px-3 py-2 bg-bg border border-border rounded text-sm text-text placeholder:text-text-muted focus:border-accent focus:outline-none"
            disabled={loading}
          />
        </div>
      )}
      <div className="flex items-center gap-3 mt-3 flex-wrap">
        <span className="mono text-[10px] uppercase tracking-[0.16em] text-text-muted">
          Sources
        </span>
        {/* Phase 45 (v1.6) — F8: biomedical-detected caption surfaces when
            the classifier auto-toggled paperclip on (i.e. user hasn't
            manually overridden the source set). */}
        {biomedical && !sourcesTouched && (
          <span
            data-biomedical-caption
            className="mono text-[10px] uppercase tracking-[0.14em] text-accent"
            title="Paperclip biomedical full-text corpus auto-on; routing primary"
          >
            🩺 biomedical detected
          </span>
        )}
        {ALL_SOURCES.map((s) => {
          const enabled = sources.includes(s);
          const dimmed = s === "arxiv" && !enabled && biomedical && !sourcesTouched;
          return (
            <button
              key={s}
              onClick={() => toggleSource(s)}
              title={dimmed ? "arXiv off — query looks biomedical. Click to include." : undefined}
              className={cn(
                "px-2 py-1 border rounded text-xs transition",
                enabled
                  ? "border-accent text-accent bg-accent-faint"
                  : dimmed
                    ? "border-border-dim text-text-muted/70 italic hover:text-text"
                    : "border-border-dim text-text-muted hover:text-text",
              )}
            >
              {SOURCE_LABELS[s]}
              {dimmed && <span className="ml-1 mono text-[9px]">·off</span>}
            </button>
          );
        })}
        <span className="mono text-[10px] uppercase tracking-[0.16em] text-text-muted ml-2">
          Limit
        </span>
        <input
          type="number"
          min={1}
          max={50}
          value={maxResults}
          onChange={(e) => setMaxResults(Math.max(1, Math.min(50, Number(e.target.value) || 10)))}
          className="w-16 px-2 py-1 bg-bg border border-border-dim rounded text-xs text-text"
        />
        {hasRecents && (
          <div ref={recentRef} className="relative ml-2">
            <button
              type="button"
              data-recent-searches-button
              onClick={() => setRecentOpen((o) => !o)}
              className="px-2 py-1 border border-border-dim rounded mono text-[10px] uppercase tracking-wider text-text-muted hover:text-text transition"
            >
              Recent ▾
            </button>
            {recentOpen && (
              <div
                data-recent-searches-panel
                className="absolute left-0 top-full mt-1 z-10 w-72 max-h-64 overflow-auto bg-bg-elev border border-border rounded shadow-lg"
              >
                {recentSearches!.map((entry) => (
                  <button
                    key={`${entry.ts}-${entry.query}`}
                    type="button"
                    onClick={() => {
                      setRecentOpen(false);
                      setQuery(entry.query);
                      setSourcesTouched(true);
                      const valid = entry.sources.filter((s): s is SearchSource =>
                        ALL_SOURCES.includes(s as SearchSource),
                      );
                      if (valid.length > 0) setSources(valid);
                      onPickRecent!(entry);
                    }}
                    className="w-full text-left px-3 py-2 text-xs hover:bg-bg-soft border-b border-border-dim last:border-b-0"
                  >
                    <div className="text-text truncate">{entry.query}</div>
                    <div className="mono text-[9px] text-text-muted mt-0.5">
                      {entry.sources.join(", ")}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
        {/* Phase 46 (v1.6) — F9: autonomy-mode toggle. Only renders when
            the parent supplies onAutonomySubmit. */}
        {onAutonomySubmit && (
          <label
            className="flex items-center gap-2 ml-2 text-xs text-text-muted cursor-pointer"
            data-autonomy-toggle
          >
            <input
              type="checkbox"
              checked={autonomyEnabled}
              onChange={(e) => setAutonomyEnabled(e.target.checked)}
              className="accent-accent"
            />
            autonomy (curate ≥ threshold)
          </label>
        )}
        <label className="flex items-center gap-2 ml-auto text-xs text-text-muted cursor-pointer">
          <input
            type="checkbox"
            checked={viaSkill}
            onChange={(e) => setViaSkill(e.target.checked)}
            className="accent-accent"
          />
          via skill (slower, exercises full pipeline)
        </label>
      </div>
    </div>
  );
}
