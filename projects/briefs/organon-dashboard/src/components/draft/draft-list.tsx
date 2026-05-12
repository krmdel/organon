"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { ManuscriptMeta, CitationStyle } from "@/lib/draft/store";
import type { HypothesisArtifact } from "@/lib/artifacts/types";
import { HypothesisMultiselect } from "@/components/hypothesis/hypothesis-multiselect";

export type DraftListProps = {
  project: string;
  manuscripts: ManuscriptMeta[];
  /** Phase 42 (v1.5) — F5: hypotheses available for the link picker. */
  hypotheses?: HypothesisArtifact[];
};

const STYLES: { value: CitationStyle; label: string }[] = [
  { value: "apa",       label: "APA — (Author, Year)" },
  { value: "nature",    label: "Nature — [n]" },
  { value: "ieee",      label: "IEEE — [n]" },
  { value: "vancouver", label: "Vancouver — [n]" },
];

// Phase 10 (v1.0.1) — DR-5 propose-title: surface 3–5 candidate titles
// emitted by sci-writing in title-generate mode. Candidates land via the
// SSE `artifact` event from /api/draft/[slug]/generate-title; the user
// picks one and the form populates the title field.
type TitleCandidate = { title: string; rationale: string };

export function DraftList({ project, manuscripts, hypotheses }: DraftListProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [title, setTitle] = useState("");
  const [style, setStyle] = useState<CitationStyle>("apa");
  const [error, setError] = useState<string | null>(null);
  // Phase 62 (v2.2) — M1: local manuscript list state for optimistic
  // delete prune. Re-syncs when the SSR-supplied prop changes (e.g.
  // after navigation back from /draft/[slug]).
  const [items, setItems] = useState<ManuscriptMeta[]>(manuscripts);
  useEffect(() => { setItems(manuscripts); }, [manuscripts]);
  // Phase 62 — track the active manuscript when present in the URL via
  // ?slug=... so deleting the active one navigates the user back to a
  // clean list view.
  const activeSlug = searchParams.get("slug");
  // Phase 42 (v1.5) — F5: optional linked hypothesis ids selected at
  // create time. Empty = "use everything" (backward-compat with v1.4).
  const [linkedHypothesisIds, setLinkedHypothesisIds] = useState<string[]>([]);

  // Phase 10: propose-title state. Candidates flow into the same form
  // surface as the title input — no modal, no extra hop.
  const [candidates, setCandidates] = useState<TitleCandidate[]>([]);
  const [titleBusy, setTitleBusy] = useState(false);
  const [titleStatus, setTitleStatus] = useState<string | null>(null);

  const handleCreate = async () => {
    setError(null);
    setBusy(true);
    try {
      const res = await fetch("/api/draft/new", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project,
          title: title.trim(),
          citation_style: style,
          linked_hypothesis_ids: linkedHypothesisIds,
        }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json?.error ?? `HTTP ${res.status}`);
      router.push(
        `/draft/${encodeURIComponent(json.manuscript.slug)}?project=${encodeURIComponent(project)}`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  // Phase 10: ask the most recent manuscript (if any) for title candidates.
  // No active manuscript → propose against the most recently updated one;
  // empty list → ask the user to create a draft first.
  //
  // The SSE route streams stdout chunks + emits the candidates as an
  // `artifact` event with `{ artifact: { _artifact: "title-candidates", ... } }`,
  // and the terminal `done` event echoes the candidates back via
  // `data.candidates` for a deterministic post-stream read.
  const handleProposeTitle = async () => {
    if (manuscripts.length === 0) {
      setTitleStatus("Create a manuscript first — title proposals run against an existing manuscript's brief and library.");
      return;
    }
    const target = manuscripts[0];
    setTitleBusy(true);
    setTitleStatus(`Asking sci-writing to propose titles for ${target.slug}…`);
    setCandidates([]);
    try {
      const res = await fetch(
        `/api/draft/${encodeURIComponent(target.slug)}/generate-title`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ project }),
        },
      );
      if (!res.ok || !res.body) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j?.error ?? `HTTP ${res.status}`);
      }
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      let received: TitleCandidate[] | null = null;
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const events = buf.split("\n\n");
        buf = events.pop() ?? "";
        for (const evt of events) {
          const dataLine = evt.split("\n").find((l) => l.startsWith("data:"));
          if (!dataLine) continue;
          try {
            const data = JSON.parse(dataLine.slice(5).trim());
            if (data?.artifact?._artifact === "title-candidates") {
              received = data.artifact.candidates as TitleCandidate[];
            }
            if (Array.isArray(data?.candidates)) {
              received = data.candidates as TitleCandidate[];
            }
          } catch { /* keepalive / non-JSON */ }
        }
      }
      if (received && received.length >= 3 && received.length <= 5) {
        setCandidates(received);
        setTitleStatus(`${received.length} candidates ready — pick one or keep typing your own.`);
      } else {
        setTitleStatus("No candidates returned — try again or keep typing your own title.");
      }
    } catch (err) {
      setTitleStatus(err instanceof Error ? err.message : String(err));
    } finally {
      setTitleBusy(false);
    }
  };

  // Phase 62 (v2.2) — M1: optimistic delete with restore-on-failure.
  // Mirrors Phase 58's hypothesis handler: optimistic prune, fetch
  // DELETE, restore the row if the route fails, and clear the active
  // ?slug=... param if the deleted manuscript was the active one.
  const handleDeleteManuscript = async (slug: string) => {
    const before = items;
    setItems((prev) => prev.filter((m) => m.slug !== slug));
    try {
      const res = await fetch(
        `/api/draft/${encodeURIComponent(slug)}?project=${encodeURIComponent(project)}`,
        { method: "DELETE" },
      );
      if (!res.ok) {
        setItems(before);
        let msg = `Delete failed (${res.status})`;
        try {
          const j = await res.json();
          if (j?.error) msg = j.error;
        } catch { /* keep generic */ }
        setError(msg);
        return;
      }
      if (activeSlug === slug) {
        const sp = new URLSearchParams(Array.from(searchParams.entries()));
        sp.set("project", project);
        sp.delete("slug");
        router.replace(`/draft?${sp.toString()}`);
      }
    } catch (err) {
      setItems(before);
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <div className="px-6 py-5 max-w-[1100px]">
      <header className="mb-5 flex items-start justify-between">
        <div>
          <div className="mono text-[11px] uppercase tracking-[0.2em] text-text-muted">Draft</div>
          <h1 className="text-2xl text-text mt-1">{project}</h1>
          <p className="text-sm text-text-dim mt-1">
            Manuscripts scoped to this project. Three-pane editor: sections / markdown / live preview.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setCreating((c) => !c)}
          className="text-xs mono uppercase tracking-wider px-3 py-1 border border-accent text-accent hover:bg-accent-faint rounded"
        >
          {creating ? "Cancel" : "+ new manuscript"}
        </button>
      </header>

      {creating && (
        <div className="border border-border-dim rounded bg-bg-elev px-4 py-3 mb-4 space-y-3">
          <div>
            <div className="mono text-[10px] uppercase tracking-wider text-text-muted flex items-center justify-between">
              <span>Title</span>
              <button
                type="button"
                onClick={() => void handleProposeTitle()}
                disabled={titleBusy}
                className="text-[10px] mono uppercase tracking-wider px-2 py-0.5 border border-accent/60 text-accent hover:bg-accent-faint rounded disabled:opacity-50"
                data-propose-title-button
              >
                {titleBusy ? "Proposing…" : "✦ Propose title"}
              </button>
            </div>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              autoFocus
              placeholder='e.g. "GLP-1 receptor agonists meta-analysis (2025)"'
              className="mt-1 w-full bg-bg border border-border-dim rounded px-3 py-2 text-sm text-text focus:border-accent outline-none"
            />
            {titleStatus && (
              <div className="mt-1 mono text-[10px] text-text-muted">{titleStatus}</div>
            )}
            {candidates.length > 0 && (
              <ul
                className="mt-2 border border-border-dim rounded bg-bg divide-y divide-border-dim"
                data-title-candidates
              >
                {candidates.map((c, i) => (
                  <li key={i}>
                    <button
                      type="button"
                      onClick={() => {
                        setTitle(c.title);
                        setTitleStatus(`Selected candidate ${i + 1}.`);
                      }}
                      className="w-full text-left px-3 py-2 hover:bg-bg-soft"
                    >
                      <div className="text-sm text-text">{c.title}</div>
                      <div className="mono text-[10px] text-text-muted mt-0.5">{c.rationale}</div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <div className="mono text-[10px] uppercase tracking-wider text-text-muted">Citation style</div>
            <select
              value={style}
              onChange={(e) => setStyle(e.target.value as CitationStyle)}
              className="mt-1 w-full bg-bg border border-border-dim rounded px-3 py-2 text-sm text-text focus:border-accent outline-none"
            >
              {STYLES.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
          {/* Phase 42 (v1.5) — F5 multi-hypothesis picker. Inline picker
              at create-time; same primitive renders in a modal from the
              SourceLinkagePanel for edit-time. Empty selection is fine —
              the manuscript falls back to "use all hypotheses" until the
              user narrows. */}
          <div>
            <div className="mono text-[10px] uppercase tracking-wider text-text-muted">
              Linked hypotheses (optional)
            </div>
            <div className="mt-1">
              <HypothesisMultiselect
                hypotheses={hypotheses ?? []}
                selectedIds={linkedHypothesisIds}
                onChange={setLinkedHypothesisIds}
              />
            </div>
          </div>
          {error && <div className="mono text-xs text-danger">{error}</div>}
          <div className="flex justify-end">
            <button
              type="button"
              onClick={handleCreate}
              disabled={busy || !title.trim()}
              className="text-xs mono uppercase tracking-wider px-3 py-1 border border-accent text-accent hover:bg-accent-faint rounded disabled:opacity-50"
            >
              {busy ? "Creating…" : "Create + open"}
            </button>
          </div>
        </div>
      )}

      {items.length === 0 ? (
        <div className="border border-dashed border-border-dim rounded px-8 py-16 text-center">
          <div className="mono text-[11px] uppercase tracking-[0.2em] text-text-muted">No manuscripts yet</div>
          <div className="mt-2 text-sm text-text-dim">
            Click "+ new manuscript" to scaffold one with default sections.
          </div>
        </div>
      ) : (
        <ul className="border border-border-dim rounded divide-y divide-border-dim bg-bg-elev">
          {items.map((m) => (
            <li key={m.slug}>
              <div className="group flex items-stretch hover:bg-bg-soft">
                <button
                  type="button"
                  onClick={() =>
                    router.push(
                      `/draft/${encodeURIComponent(m.slug)}?project=${encodeURIComponent(project)}`,
                    )
                  }
                  className="flex-1 min-w-0 text-left px-4 py-3 flex items-center gap-3"
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-text truncate">{m.title}</div>
                    <div className="mono text-[10px] text-text-muted">
                      {m.slug} · {m.citation_style} · {m.ordering.length} sections
                    </div>
                  </div>
                  <div className="mono text-[10px] text-text-muted">
                    {m.updated_at?.slice(0, 10)}
                  </div>
                </button>
                {/* Phase 62 (v2.2) — M1: sibling × delete affordance.
                    Sibling not nested so the click never bubbles into
                    the row's onSelect navigation. */}
                <button
                  type="button"
                  data-manuscript-delete={m.slug}
                  onClick={(e) => {
                    e.stopPropagation();
                    e.preventDefault();
                    if (
                      typeof window !== "undefined" &&
                      window.confirm(
                        `Delete manuscript "${m.title}"? This cannot be undone.`,
                      )
                    ) {
                      void handleDeleteManuscript(m.slug);
                    }
                  }}
                  className="px-3 mono text-[14px] text-text-muted opacity-0 group-hover:opacity-100 hover:text-danger transition"
                  title="Delete manuscript (cannot be undone)"
                  aria-label={`Delete manuscript ${m.title}`}
                >
                  ×
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
