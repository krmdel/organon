"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { useRouter, useSearchParams } from "next/navigation";
import type { PaperArtifact } from "@/lib/artifacts/types";
import {
  SearchBar,
  type AutonomyParams,
  type RecentSearchEntry,
  type SearchParams,
  type SearchSource,
} from "./search-bar";
import { PaperCard } from "./paper-card";
import { PaperDetail } from "./paper-detail";
import { LibraryPanel } from "./library-panel";
import {
  pushRecentSearch,
  readRecentSearches,
  type RecentSearch,
} from "@/lib/state/recent-searches";

export type LitWorkspaceProps = {
  project: string;
  initialLibrary: PaperArtifact[];
  initialQuery?: string;
  initialPaperId?: string;
  initialSources?: SearchSource[];
};

type RunState = "idle" | "running" | "error";

export function LitWorkspace({
  project,
  initialLibrary,
  initialQuery,
  initialPaperId,
  initialSources,
}: LitWorkspaceProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [results, setResults] = useState<PaperArtifact[]>([]);
  const [library, setLibrary] = useState<PaperArtifact[]>(initialLibrary);
  const [query, setQuery] = useState(initialQuery ?? "");
  const [sources, setSources] = useState<SearchSource[]>(initialSources ?? [
    "pubmed",
    "arxiv",
    "openalex",
    "semanticscholar",
  ]);
  const [focusedIdx, setFocusedIdx] = useState(0);
  const [detailPaper, setDetailPaper] = useState<PaperArtifact | null>(null);
  const [runState, setRunState] = useState<RunState>("idle");
  const [errors, setErrors] = useState<string[]>([]);
  // Phase 37 (v1.4) — B4: soft per-source warnings (rate-limit) render
  // as a yellow info banner distinct from the red errors toast above.
  const [soft_errors, setSoftErrors] = useState<string[]>([]);
  // Phase 38 (v1.4) — F1: batch metadata for the most recent search.
  // Threaded into handleSave so saved papers cluster in the library
  // under the query that produced them.
  const [searchBatch, setSearchBatch] = useState<{
    batch_id: string;
    query: string;
    added_at: string;
  } | null>(null);
  const [streamingMessage, setStreamingMessage] = useState<string | null>(null);
  const [runStartedAt, setRunStartedAt] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [recentSearches, setRecentSearches] = useState<RecentSearch[]>([]);
  const abortRef = useRef<AbortController | null>(null);
  // Phase 46 (v1.6) — F9: autonomy-mode result state. Holds the
  // (accepted, borderline) partition + variant list returned by the
  // /api/lit/autonomy SSE; switches the result-list rendering to the
  // accepted/borderline panels when populated.
  const [autonomyResult, setAutonomyResult] = useState<{
    accepted: PaperArtifact[];
    borderline: PaperArtifact[];
    variants: string[];
  } | null>(null);
  // Phase 47 (v1.6) — F10: high-confidence-only threshold chip. Filters
  // the visible result list client-side at relevance_score ≥ 0.6.
  // The corpus stays intact server-side; the chip is a UI gate only.
  const [relevanceFilterEnabled, setRelevanceFilterEnabled] = useState(false);
  const RELEVANCE_THRESHOLD = 0.6;
  // Phase 11 (v1.0.1) — auto-run search once on mount when the URL carries a
  // query. The hydration must NOT replay every time the searchParams object
  // changes (handleSearch itself rewrites the URL, which would loop).
  const autoSearchedRef = useRef(false);

  const savedIds = useMemo(() => new Set(library.map((p) => p.id)), [library]);

  // Phase 11 — hydrate the recent-searches dropdown from localStorage on first
  // paint. Project-scoped so cross-project work does not bleed.
  useEffect(() => {
    setRecentSearches(readRecentSearches(project));
  }, [project]);

  // Tick the elapsed-time counter while a run is in progress.
  useEffect(() => {
    if (runState !== "running" || runStartedAt === null) return;
    setElapsed(Math.floor((Date.now() - runStartedAt) / 1000));
    const id = setInterval(() => {
      setElapsed(Math.floor((Date.now() - runStartedAt) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, [runState, runStartedAt]);

  // Pull the saved-papers list from the server. Used to reconcile after a
  // via-skill run auto-persists artifacts to disk.
  const refreshLibrary = useCallback(async () => {
    try {
      const res = await fetch(`/api/lit/library?project=${encodeURIComponent(project)}`);
      const data = await res.json();
      if (Array.isArray(data.papers)) setLibrary(data.papers);
    } catch {
      // keep last good
    }
  }, [project]);

  const cancelRun = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  // Hydrate detail drawer from URL on first paint
  useEffect(() => {
    if (!initialPaperId) return;
    const fromLib = library.find((p) => p.id === initialPaperId);
    if (fromLib) setDetailPaper(fromLib);
  }, [initialPaperId, library]);

  const runDirectSearch = useCallback(
    async (params: SearchParams) => {
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      setRunState("running");
      setRunStartedAt(Date.now());
      setErrors([]);
      setSoftErrors([]);
      setStreamingMessage(null);
      try {
        const res = await fetch("/api/lit/search", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            project,
            query: params.query,
            sources: params.sources,
            max_results: params.max_results,
          }),
          signal: ctrl.signal,
        });
        const data = await res.json();
        if (data.error) {
          setErrors([data.error]);
          setRunState("error");
          return;
        }
        setResults(data.results ?? []);
        if (data.errors) setErrors(data.errors);
        // Phase 37 (v1.4) — B4: soft warnings (rate-limit) into yellow
        // banner; distinct from hard errors above.
        if (data.soft_errors) setSoftErrors(data.soft_errors);
        // Phase 38 (v1.4) — F1: allocate a batch for this search so
        // subsequent Save clicks stamp the same batch_id.
        const newBatchId = `batch_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
        setSearchBatch({
          batch_id: newBatchId,
          query: params.query,
          added_at: new Date().toISOString(),
        });
        setFocusedIdx(0);
        setRunState("idle");
      } catch (err) {
        if (ctrl.signal.aborted) {
          setErrors(["Search cancelled"]);
        } else {
          setErrors([err instanceof Error ? err.message : String(err)]);
        }
        setRunState("error");
      } finally {
        abortRef.current = null;
        setRunStartedAt(null);
      }
    },
    [project],
  );

  const runViaSkill = useCallback(
    async (params: SearchParams) => {
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      setRunState("running");
      setRunStartedAt(Date.now());
      setErrors([]);
      setResults([]);
      setStreamingMessage("Routing through sci-literature-research skill…");
      try {
        const res = await fetch("/api/execute", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            project,
            skill: "sci-literature-research",
            prompt: `Search the literature for: ${params.query}\n\nReturn at most ${params.max_results} results from sources: ${params.sources.join(", ")}.\n\nFor each result, emit the JSON \`_artifact: paper\` line per the protocol in your SKILL.md Step 1.5. Use \`active_project_slug=${project}\` to populate the \`library_path\` field. The Organon Dashboard is running this and needs the artifact lines; do not skip them.`,
          }),
          signal: ctrl.signal,
        });
        if (!res.body) {
          setErrors(["No response stream"]);
          setRunState("error");
          return;
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        const collected: PaperArtifact[] = [];
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const text = decoder.decode(value, { stream: true });
          const events = text.split(/\n\n/);
          for (const block of events) {
            if (!block.trim()) continue;
            const lines = block.split("\n");
            const eventLine = lines.find((l) => l.startsWith("event: "));
            const dataLine = lines.find((l) => l.startsWith("data: "));
            if (!eventLine || !dataLine) continue;
            const event = eventLine.slice(7).trim();
            const data = JSON.parse(dataLine.slice(6));
            if (event === "artifact") {
              // Server already extracted artifacts from stdout via lib/artifacts/parser
              // and emits one synthetic `artifact` event per match. Listening to
              // raw stdout here too would double-count (cardKey duplicates).
              const incoming = data.artifact;
              if (incoming && incoming._artifact === "paper") {
                if (!collected.some((p) => p.id === incoming.id)) {
                  collected.push(incoming);
                }
              }
            } else if (event === "error") {
              setErrors((prev) => [...prev, data.message ?? "skill error"]);
            }
          }
          setResults([...collected]);
        }
        setStreamingMessage(null);
        setRunState("idle");
        // /api/execute auto-persists artifacts; reconcile the LibraryPanel.
        await refreshLibrary();
      } catch (err) {
        if (ctrl.signal.aborted) {
          setErrors(["Run cancelled"]);
        } else {
          setErrors([err instanceof Error ? err.message : String(err)]);
        }
        setRunState("error");
      } finally {
        abortRef.current = null;
        setRunStartedAt(null);
      }
    },
    [project, refreshLibrary],
  );

  const handleSearch = useCallback(
    (params: SearchParams) => {
      setQuery(params.query);
      setSources(params.sources);
      setAutonomyResult(null);
      // Persist query to URL for back/forward / shareable links
      const sp = new URLSearchParams(Array.from(searchParams.entries()));
      sp.set("project", project);
      sp.set("q", params.query);
      sp.set("sources", params.sources.join(","));
      router.replace(`/lit?${sp.toString()}`);

      // Phase 11 — push to the project-scoped recent-searches ring (~10 entries).
      setRecentSearches(
        pushRecentSearch(project, { query: params.query, sources: params.sources }),
      );

      if (params.via_skill) runViaSkill(params);
      else runDirectSearch(params);
    },
    [project, router, searchParams, runDirectSearch, runViaSkill],
  );

  // Phase 46 (v1.6) — F9: autonomy-mode SSE consumer. Streams from
  // /api/lit/autonomy via the streamTaskAsSse helper (Phase 44 substrate),
  // collects the autonomy-result payload, and renders the accepted +
  // borderline panels.
  const handleAutonomySubmit = useCallback(
    async (params: AutonomyParams) => {
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      setRunState("running");
      setRunStartedAt(Date.now());
      setErrors([]);
      setSoftErrors([]);
      setResults([]);
      setAutonomyResult(null);
      setStreamingMessage("Curating literature autonomously…");
      try {
        const res = await fetch("/api/lit/autonomy", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            project,
            keywords: params.keywords,
            research_question: params.research_question,
          }),
          signal: ctrl.signal,
        });
        if (!res.body) {
          setErrors(["No response stream"]);
          setRunState("error");
          return;
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const text = decoder.decode(value, { stream: true });
          const events = text.split(/\n\n/);
          for (const block of events) {
            if (!block.trim()) continue;
            const lines = block.split("\n");
            const eventLine = lines.find((l) => l.startsWith("event: "));
            const dataLine = lines.find((l) => l.startsWith("data: "));
            if (!eventLine || !dataLine) continue;
            const event = eventLine.slice(7).trim();
            const data = JSON.parse(dataLine.slice(6));
            if (event === "autonomy-result") {
              setAutonomyResult({
                accepted: data.accepted ?? [],
                borderline: data.borderline ?? [],
                variants: [],
              });
              setResults([...(data.accepted ?? []), ...(data.borderline ?? [])]);
            } else if (event === "autonomy-variants") {
              setAutonomyResult((cur) =>
                cur ? { ...cur, variants: data.variants ?? [] } : { accepted: [], borderline: [], variants: data.variants ?? [] },
              );
            } else if (event === "warn") {
              setSoftErrors((prev) => [...prev, data.message ?? "warning"]);
            } else if (event === "error") {
              setErrors((prev) => [...prev, data.message ?? "autonomy error"]);
            }
          }
        }
        setStreamingMessage(null);
        setRunState("idle");
      } catch (err) {
        if (ctrl.signal.aborted) {
          setErrors(["Autonomy run cancelled"]);
        } else {
          setErrors([err instanceof Error ? err.message : String(err)]);
        }
        setRunState("error");
      } finally {
        abortRef.current = null;
        setRunStartedAt(null);
      }
    },
    [project],
  );

  // Phase 11 — auto-run search on first mount when the URL carries a query.
  // This is the actual "L-1 fix": navigating Lit → Hypothesis → back to Lit
  // used to land on `?q=GLP-1` with empty results. Now the search re-fires.
  useEffect(() => {
    if (autoSearchedRef.current) return;
    if (!initialQuery) return;
    autoSearchedRef.current = true;
    handleSearch({
      query: initialQuery,
      sources: initialSources ?? ["pubmed", "arxiv", "openalex", "semanticscholar", "paperclip"],
      max_results: 10,
      via_skill: false,
    });
  }, [initialQuery, initialSources, handleSearch]);

  const handlePickRecent = useCallback(
    (entry: RecentSearchEntry) => {
      const validSources = entry.sources.filter((s): s is SearchSource =>
        (["pubmed", "arxiv", "openalex", "semanticscholar", "paperclip"] as const).includes(s as SearchSource),
      );
      handleSearch({
        query: entry.query,
        sources: validSources.length > 0 ? validSources : ["pubmed", "arxiv", "openalex", "semanticscholar", "paperclip"],
        max_results: 10,
        via_skill: false,
      });
    },
    [handleSearch],
  );

  const handleSave = useCallback(
    async (paper: PaperArtifact) => {
      // Optimistic — Phase 38 stamps batch metadata locally so the
      // panel groups it immediately, before the server round-trip.
      const stamped = searchBatch
        ? {
            ...paper,
            saved_at: new Date().toISOString(),
            search_batch_id: searchBatch.batch_id,
            search_batch_query: searchBatch.query,
            search_batch_added_at: searchBatch.added_at,
          }
        : { ...paper, saved_at: new Date().toISOString() };
      setLibrary((cur) => (cur.some((p) => p.id === paper.id) ? cur : [stamped, ...cur]));
      try {
        await fetch("/api/lit/library", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            project,
            paper,
            ...(searchBatch ? { batch: searchBatch } : {}),
          }),
        });
      } catch {
        // Revert on failure
        setLibrary((cur) => cur.filter((p) => p.id !== paper.id));
      }
    },
    [project, searchBatch],
  );

  // Phase 38 (v1.4) — F1: batch + multi-id deletes. Both refresh the
  // library list afterwards so the optimistic state matches disk.
  const handleRemoveBatch = useCallback(
    async (batchId: string) => {
      const prev = library;
      setLibrary((cur) => cur.filter((p) => p.search_batch_id !== batchId));
      try {
        await fetch(
          `/api/lit/library?project=${encodeURIComponent(project)}&batch=${encodeURIComponent(batchId)}`,
          { method: "DELETE" },
        );
      } catch {
        setLibrary(prev);
      }
    },
    [project, library],
  );
  const handleRemoveIds = useCallback(
    async (ids: string[]) => {
      const prev = library;
      const idSet = new Set(ids);
      setLibrary((cur) => cur.filter((p) => !idSet.has(p.id)));
      try {
        await fetch(
          `/api/lit/library?project=${encodeURIComponent(project)}&ids=${encodeURIComponent(ids.join(","))}`,
          { method: "DELETE" },
        );
      } catch {
        setLibrary(prev);
      }
    },
    [project, library],
  );

  const handleUnsave = useCallback(
    async (paper: PaperArtifact) => {
      const prev = library;
      setLibrary((cur) => cur.filter((p) => p.id !== paper.id));
      try {
        await fetch("/api/lit/library", {
          method: "DELETE",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ project, paper_id: paper.id }),
        });
      } catch {
        setLibrary(prev);
      }
    },
    [project, library],
  );

  const handleOpen = useCallback(
    (paper: PaperArtifact) => {
      setDetailPaper(paper);
      const sp = new URLSearchParams(Array.from(searchParams.entries()));
      sp.set("project", project);
      sp.set("paper", paper.id);
      router.replace(`/lit?${sp.toString()}`);
    },
    [project, router, searchParams],
  );

  const handleClose = useCallback(() => {
    setDetailPaper(null);
    const sp = new URLSearchParams(Array.from(searchParams.entries()));
    sp.delete("paper");
    router.replace(`/lit?${sp.toString()}`);
  }, [router, searchParams]);

  // j/k navigation
  useHotkeys(
    "j",
    () => {
      if (results.length === 0) return;
      setFocusedIdx((i) => Math.min(results.length - 1, i + 1));
    },
    { enableOnFormTags: false },
    [results.length],
  );
  useHotkeys(
    "k",
    () => {
      if (results.length === 0) return;
      setFocusedIdx((i) => Math.max(0, i - 1));
    },
    { enableOnFormTags: false },
    [results.length],
  );
  useHotkeys(
    "enter",
    () => {
      if (detailPaper) return; // let drawer handle
      if (results.length === 0) return;
      handleOpen(results[focusedIdx]);
    },
    { enableOnFormTags: false },
    [results, focusedIdx, detailPaper, handleOpen],
  );
  useHotkeys(
    "s",
    () => {
      if (detailPaper) return;
      if (results.length === 0) return;
      const p = results[focusedIdx];
      if (savedIds.has(p.id)) handleUnsave(p);
      else handleSave(p);
    },
    { enableOnFormTags: false },
    [results, focusedIdx, savedIds, detailPaper, handleSave, handleUnsave],
  );

  return (
    <div className="flex h-[calc(100vh-3.5rem)] min-h-0">
      <div className="flex-1 flex flex-col min-w-0">
        <SearchBar
          initialQuery={query}
          initialSources={sources}
          onSearch={handleSearch}
          loading={runState === "running"}
          recentSearches={recentSearches}
          onPickRecent={handlePickRecent}
          project={project}
          onAutonomySubmit={handleAutonomySubmit}
        />
        <div className="flex-1 overflow-auto px-6 py-4">
          {runState === "running" && (
            <div className="flex items-center gap-3 text-sm text-text-muted py-3 mb-3 border border-border-dim rounded px-4">
              <span className="pulse-dot inline-block w-2 h-2 bg-accent rounded-full" />
              <span className="flex-1">
                {streamingMessage ?? "Searching across sources…"}
                {results.length > 0 && (
                  <span className="ml-2 text-text-dim">
                    {results.length} result{results.length !== 1 ? "s" : ""} so far
                  </span>
                )}
              </span>
              <span className="mono text-xs">{formatElapsed(elapsed)}</span>
              <button
                onClick={cancelRun}
                className="px-2 py-1 border border-border rounded mono text-[10px] uppercase tracking-wider text-text-dim hover:text-danger hover:border-danger transition"
              >
                Cancel
              </button>
            </div>
          )}
          {errors.length > 0 && (
            <div className="border border-danger rounded p-3 mb-4 text-sm text-danger">
              {errors.map((e, i) => (
                <div key={i} className="mono text-xs">
                  {e}
                </div>
              ))}
            </div>
          )}
          {soft_errors.length > 0 && (
            <div
              data-soft-errors
              className="border border-warn rounded p-3 mb-4 text-sm text-warn bg-warn-faint"
              title="Rate-limited / partial — search results may be incomplete"
            >
              {soft_errors.map((e, i) => (
                <div key={i} className="mono text-xs">
                  ⏱ {e}
                </div>
              ))}
            </div>
          )}
          {results.length === 0 && runState !== "running" && (
            <EmptyState />
          )}
          {/* Phase 47 (v1.6) — F10: high-confidence-only threshold chip.
              Filters relevance_score ≥ 0.6 client-side. Renders only when
              the active result set has any scored entries. */}
          {results.length > 0 && results.some((p) => typeof p.relevance_score === "number") && (
            <div className="flex items-center gap-3 mb-3 text-xs">
              <label
                className="flex items-center gap-2 cursor-pointer text-text-muted"
                data-relevance-filter
              >
                <input
                  type="checkbox"
                  checked={relevanceFilterEnabled}
                  onChange={(e) => setRelevanceFilterEnabled(e.target.checked)}
                  className="accent-accent"
                />
                high-confidence only (≥ 0.6)
              </label>
              {relevanceFilterEnabled && (
                <span className="mono text-[10px] text-text-muted">
                  showing{" "}
                  {results.filter((p) => (p.relevance_score ?? 0) >= RELEVANCE_THRESHOLD).length}
                  {" "}of {results.length}
                </span>
              )}
            </div>
          )}
          {/* Phase 46 (v1.6) — F9: autonomy result panels. When the
              autonomy run produced an accepted/borderline split, render
              both buckets with section headers; the borderline section
              starts collapsed so the surface stays focused on accepted. */}
          {autonomyResult && (
            <div className="space-y-4 mb-4" data-autonomy-panels>
              <div>
                <div className="mono text-[11px] uppercase tracking-[0.16em] text-text-muted mb-2">
                  Accepted ({autonomyResult.accepted.length})
                </div>
                {autonomyResult.accepted.length === 0 && (
                  <div className="text-xs text-text-muted italic px-1 py-2">
                    No papers cleared the relevance threshold. Open the
                    borderline section below.
                  </div>
                )}
              </div>
              {autonomyResult.borderline.length > 0 && (
                <details className="border-t border-border-dim pt-3">
                  <summary className="mono text-[11px] uppercase tracking-[0.16em] text-text-muted cursor-pointer">
                    Borderline ({autonomyResult.borderline.length}) — below threshold
                  </summary>
                  <div className="mt-2 text-xs text-text-muted">
                    Listed below the accepted section. Use{' '}
                    <span className="mono">s</span> to save individual cards.
                  </div>
                </details>
              )}
              {autonomyResult.variants.length > 0 && (
                <div className="text-[10px] text-text-muted">
                  Searched variants: {autonomyResult.variants.map((v, i) => (
                    <span key={i} className="mono mx-1 px-1 border border-border-dim rounded">
                      {v}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
          {/* Phase 47 (v1.6) — F10: filtered list. The threshold filter
              hides results client-side without mutating `results` so j/k
              navigation + bulk-save semantics see the unfiltered set. */}
          {(relevanceFilterEnabled
            ? results.filter((p) => (p.relevance_score ?? 0) >= RELEVANCE_THRESHOLD)
            : results
          ).map((p, i) => (
            <PaperCard
              key={p.id}
              paper={p}
              isSaved={savedIds.has(p.id)}
              isFocused={i === focusedIdx}
              onOpen={handleOpen}
              onSave={handleSave}
              onUnsave={handleUnsave}
            />
          ))}
        </div>
      </div>
      <LibraryPanel
        papers={library}
        currentProject={project}
        onRemove={(id) => {
          const p = library.find((x) => x.id === id);
          if (p) handleUnsave(p);
        }}
        onOpen={handleOpen}
        onRemoveBatch={handleRemoveBatch}
        onRemoveIds={handleRemoveIds}
      />
      <PaperDetail
        paper={detailPaper}
        isSaved={detailPaper ? savedIds.has(detailPaper.id) : false}
        onClose={handleClose}
        onSave={handleSave}
        onUnsave={handleUnsave}
        onGenerateHypothesis={(p) => {
          // Cross-link to /hypothesis with the paper preselected.
          if (!savedIds.has(p.id)) handleSave(p);
          router.push(
            `/hypothesis?project=${encodeURIComponent(project)}&prefill_paper=${encodeURIComponent(p.id)}`,
          );
        }}
      />
    </div>
  );
}

function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}m ${s.toString().padStart(2, "0")}s`;
}

function EmptyState() {
  return (
    <div className="py-16 text-center max-w-md mx-auto">
      <div className="mono text-[11px] tracking-[0.2em] text-text-muted uppercase mb-2">
        No results yet
      </div>
      <h2 className="text-xl font-semibold mb-3">Search the literature</h2>
      <p className="text-sm text-text-dim leading-relaxed mb-4">
        Federated across PubMed, arXiv, OpenAlex, and Semantic Scholar. Results dedupe by DOI and
        rank by a composite of citations, search position, and recency.
      </p>
      <div className="text-xs text-text-muted">
        Try: <span className="text-text-dim">GLP-1 obesity meta-analysis</span> ·{" "}
        <span className="text-text-dim">CRISPR base editing delivery</span> ·{" "}
        <span className="text-text-dim">retrieval augmented generation</span>
      </div>
    </div>
  );
}
