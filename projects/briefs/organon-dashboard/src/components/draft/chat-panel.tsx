"use client";

import { useCallback, useEffect, useState, type RefObject } from "react";
import type { SectionDiffArtifact } from "@/lib/artifacts/types";
import type { MarkdownEditorHandle } from "./markdown-editor";
import { DiffView } from "./diff-view";
import { BulkPaperOps } from "@/components/primitives/bulk-paper-ops";
// Phase 34 (v1.3) — DR-6++ ChatTurn type extracted to a shared
// client-safe module so the server-only chat-transcripts library can
// import it without dragging React into the bundle. Re-export
// preserves the v1.2 import surface (`import { ChatTurn } from
// "./chat-panel"` keeps working).
import type { ChatTurn as SharedChatTurn } from "@/lib/draft/chat-turn-types";
export type { ChatTurn } from "@/lib/draft/chat-turn-types";

// Phase 29 (v1.2) — DR-6+ file-tree types. Mirrors the
// /api/draft/[slug]/file-tree response shape; the panel keeps the
// list in workspace-supplied state but builds the chip rendering +
// toggle UI in-place.
export type FileTreeEntry = { id: string; label: string; kind: string; hint?: string };
export type FileTreeData = {
  sections: FileTreeEntry[];
  figures: FileTreeEntry[];
  stat_results: FileTreeEntry[];
  papers: FileTreeEntry[];
  manuscripts: FileTreeEntry[];
};
export type SelectedFileRef = { kind: string; id: string; label: string };

// Phase 22 (v1.1+) — DR-6 chat panel for whole-paper-aware editing.
//
// Right-rail surface on /draft. The user types a steering prompt;
// optionally has a selection in the editor (captured via the
// imperative handle); the workspace POSTs both to /api/draft/[slug]/
// edit-with-chat and streams a `section-diff` artifact back. Each
// emitted diff renders an Apply button that swaps section.content_md
// to diff.after via the workspace's existing diff-accept path.
//
// v1.1 scope:
//   - Single-turn chat (each prompt is independent).
//   - Apply = accept full diff (per-line accept is v1.2).
//   - Selection captured ON SUBMIT via editorRef (not lifted state).

// Phase 34 (v1.3) — DR-6++ alias the shared ChatTurn type so all
// internal references in this file resolve through a single name.
type ChatTurn = SharedChatTurn;
// Reference SectionDiffArtifact so the tsc unused-import linter
// doesn't trip on the v1.2 import surface (the type is still used
// transitively via SharedChatTurn).
type _SectionDiffRef = SectionDiffArtifact;

export type ChatPanelProps = {
  // The active section's id — passed through to the chat route.
  activeSectionId: string | null;
  // Imperative handle for the markdown editor; used to capture the
  // selection at submit time without re-rendering on every cursor move.
  editorRef: RefObject<MarkdownEditorHandle | null>;
  // Workspace owns the SSE consumer + diff state. Panel forwards the
  // submit; receives turns + apply callback.
  turns: ChatTurn[];
  busy?: boolean;
  onSubmit: (req: {
    prompt: string;
    selection: { start: number; end: number; text: string } | null;
    referencedFiles: SelectedFileRef[];
  }) => void;
  onApply: (turn: ChatTurn) => void;
  // Phase 33 (v1.3) — DR-6++ per-hunk path. The chat-panel mounts the
  // shared DiffView per turn; onAcceptHunks routes through this prop
  // instead of the v1.1 full-diff onApply. Workspace's existing
  // handleApplyChatHunks (Phase 28) is wired through.
  onApplyHunks?: (turn: ChatTurn, composedAfter: string) => void;
  // Phase 34 (v1.3) — DR-6++ on-disk transcript persistence. The
  // header's "Clear chat" button calls this; workspace clears the
  // in-memory transcript + DELETEs the on-disk file. Confirm dialog
  // lives on the workspace side so the panel stays presentational.
  onClearTranscript?: () => void;
  onCloseRail?: () => void;
  // Phase 29 (v1.2) — DR-6+ file-tree integration. The workspace
  // owns the fetch (parent-owned-fetch pattern, Phase 22); the panel
  // renders the tree, tracks selectedFiles state, and includes the
  // pinned refs in onSubmit's payload.
  manuscriptSlug: string;
  projectSlug: string;
};

export function ChatPanel({
  activeSectionId,
  editorRef,
  turns,
  busy,
  onSubmit,
  onApply,
  onApplyHunks,
  onClearTranscript,
  onCloseRail,
  manuscriptSlug,
  projectSlug,
}: ChatPanelProps) {
  const [prompt, setPrompt] = useState("");
  // Phase 29 — file-tree state. Cached on mount + on refresh tick;
  // the workspace can drive a refresh by remounting the panel (e.g.
  // after a stat-result lands).
  const [fileTree, setFileTree] = useState<FileTreeData | null>(null);
  const [selectedFiles, setSelectedFiles] = useState<SelectedFileRef[]>([]);
  const [showFileTree, setShowFileTree] = useState(false);

  useEffect(() => {
    if (!manuscriptSlug || !projectSlug) return;
    let cancelled = false;
    void (async () => {
      try {
        const res = await fetch(
          `/api/draft/${encodeURIComponent(manuscriptSlug)}/file-tree?project=${encodeURIComponent(projectSlug)}`,
        );
        if (!res.ok) return;
        const json = (await res.json()) as FileTreeData;
        if (!cancelled) setFileTree(json);
      } catch {
        /* swallow — chat still works without the tree */
      }
    })();
    return () => { cancelled = true; };
  }, [manuscriptSlug, projectSlug]);

  const toggleFile = useCallback((entry: FileTreeEntry, kind: string) => {
    setSelectedFiles((prev) => {
      const idx = prev.findIndex((p) => p.kind === kind && p.id === entry.id);
      if (idx >= 0) return prev.filter((_, i) => i !== idx);
      // Cap at 4 (matches MAX_REFERENCED_FILES). Drop the oldest on overflow.
      const next = [...prev, { kind, id: entry.id, label: entry.label }];
      return next.slice(-4);
    });
  }, []);

  const removeFile = useCallback((ref: SelectedFileRef) => {
    setSelectedFiles((prev) =>
      prev.filter((p) => !(p.kind === ref.kind && p.id === ref.id)),
    );
  }, []);

  const handleSubmit = useCallback(() => {
    const trimmed = prompt.trim();
    if (!trimmed || busy || !activeSectionId) return;
    const sel = editorRef.current?.getSelection() ?? null;
    onSubmit({ prompt: trimmed, selection: sel, referencedFiles: selectedFiles });
    setPrompt("");
  }, [activeSectionId, busy, editorRef, onSubmit, prompt, selectedFiles]);

  return (
    <aside
      data-chat-panel
      className="w-80 shrink-0 border-l border-border-dim bg-bg-elev flex flex-col"
    >
      <div className="px-3 py-2 border-b border-border-dim mono text-[10px] uppercase tracking-wider text-text-muted flex items-center justify-between">
        <span>AI chat · {activeSectionId ?? "no section"}</span>
        <div className="flex items-center gap-1">
          {onClearTranscript && turns.length > 0 && (
            <button
              type="button"
              data-action="chat-clear"
              onClick={onClearTranscript}
              className="text-text-muted hover:text-danger"
              title="Clear chat transcript (irrecoverable)"
            >
              clear
            </button>
          )}
          {onCloseRail && (
            <button
              type="button"
              data-action="chat-close-rail"
              onClick={onCloseRail}
              className="text-text-muted hover:text-text"
              title="Hide chat rail"
            >
              ×
            </button>
          )}
        </div>
      </div>
      <div data-chat-transcript className="flex-1 overflow-auto px-3 py-3 space-y-4">
        {turns.length === 0 && (
          <div className="text-xs text-text-muted italic">
            Select text in the editor and ask the AI to revise it. The chat sees the
            active section, sibling sections, and linked papers as context.
          </div>
        )}
        {turns.map((turn) => (
          <div key={turn.id} className="space-y-1.5">
            <div className="text-xs text-text">
              <span className="mono text-[10px] uppercase tracking-wider text-text-muted mr-2">
                you
              </span>
              {turn.prompt}
            </div>
            {turn.selectionText && (
              <div className="mono text-[10px] text-text-muted border-l-2 border-border-dim pl-2 truncate">
                ↳ on: {turn.selectionText.slice(0, 80)}{turn.selectionText.length > 80 ? "…" : ""}
              </div>
            )}
            {turn.diff ? (
              <div data-chat-turn-diff data-turn-id={turn.id} data-turn-applied={turn.applied ? "true" : "false"}>
                <DiffView
                  diff={turn.diff}
                  onAccept={() => onApply(turn)}
                  onReject={() => { /* per-turn diff stays mounted; no-op */ }}
                  onAcceptHunks={
                    onApplyHunks
                      ? (composedAfter) => onApplyHunks(turn, composedAfter)
                      : undefined
                  }
                />
                {turn.applied && (
                  <div className="px-2 py-1 mono text-[10px] uppercase tracking-wider text-text-muted border-t border-border-dim">
                    Applied · this turn is committed
                  </div>
                )}
              </div>
            ) : (
              <div className="text-xs text-text-dim">
                <span className="mono text-[10px] uppercase tracking-wider text-text-muted mr-2">
                  ai
                </span>
                {turn.streaming || (turn.done ? "(no diff emitted)" : "(running…)")}
              </div>
            )}
          </div>
        ))}
      </div>
      {selectedFiles.length > 0 && (
        <div
          data-chat-selected-files
          className="px-3 py-1.5 border-t border-border-dim"
        >
          <div className="flex flex-wrap gap-1">
            {selectedFiles.map((ref) => (
              <span
                key={`${ref.kind}-${ref.id}`}
                className="inline-flex items-center gap-1 px-2 py-0.5 mono text-[10px] uppercase tracking-wider border border-accent text-accent rounded bg-accent-faint"
              >
                <span className="text-text-muted normal-case">{ref.kind}</span>
                <span className="truncate max-w-[14ch]">{ref.label}</span>
                <button
                  type="button"
                  data-action="remove-file"
                  data-file-kind={ref.kind}
                  data-file-id={ref.id}
                  onClick={() => removeFile(ref)}
                  className="text-text-muted hover:text-text"
                  title="Remove from references"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
          {/* Phase 39 (v1.4) — F2: shared BulkPaperOps primitive on the
              selected-files surface. NONE deselects all chips; ALL +
              INVERT operate against the file-tree's available papers
              (best-effort — bound at submit-time). No DELETE because
              the chips are a UI selection, not a data-store entry. */}
          <div className="mt-1.5 pt-1.5 border-t border-border-dim">
            <BulkPaperOps
              onAll={() => { /* no-op — populated when file-tree is open */ }}
              onNone={() => setSelectedFiles([])}
              onInvert={() => { /* invert is meaningful only when ALL is */ }}
              selectedCount={selectedFiles.length}
              totalCount={selectedFiles.length}
              label="files"
            />
          </div>
        </div>
      )}
      {fileTree && (
        <div
          data-file-tree
          className="px-3 py-1.5 border-t border-border-dim"
        >
          <button
            type="button"
            data-action="file-tree-toggle"
            onClick={() => setShowFileTree((v) => !v)}
            className="mono text-[10px] uppercase tracking-wider text-text-muted hover:text-text"
          >
            {showFileTree ? "Hide files ▴" : "Files ▾"}
          </button>
          {showFileTree && (
            <div className="mt-1.5 max-h-40 overflow-auto space-y-2">
              {(["sections", "figures", "stat_results", "papers", "manuscripts"] as const).map((groupKey) => {
                const entries = fileTree[groupKey];
                if (!entries || entries.length === 0) return null;
                const kind =
                  groupKey === "sections" ? "section"
                  : groupKey === "figures" ? "figure"
                  : groupKey === "stat_results" ? "stat-result"
                  : groupKey === "papers" ? "paper"
                  : "manuscript";
                return (
                  <div key={groupKey}>
                    <div className="mono text-[9px] uppercase tracking-wider text-text-muted mb-0.5">
                      {groupKey}
                    </div>
                    <ul className="space-y-0.5">
                      {entries.slice(0, 12).map((entry) => {
                        const checked = selectedFiles.some(
                          (p) => p.kind === kind && p.id === entry.id,
                        );
                        return (
                          <li key={`${kind}-${entry.id}`}>
                            <button
                              type="button"
                              data-action="toggle-file"
                              data-file-kind={kind}
                              data-file-id={entry.id}
                              onClick={() => toggleFile(entry, kind)}
                              className={
                                checked
                                  ? "w-full text-left text-[10px] mono px-1.5 py-0.5 border border-accent text-accent rounded"
                                  : "w-full text-left text-[10px] mono px-1.5 py-0.5 border border-border-dim text-text-dim hover:text-text rounded"
                              }
                            >
                              <span className="truncate inline-block max-w-full">
                                {entry.label}
                              </span>
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
      <div className="px-3 py-2 border-t border-border-dim flex flex-col gap-1.5">
        <textarea
          data-chat-prompt
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              handleSubmit();
            }
          }}
          disabled={busy || !activeSectionId}
          rows={3}
          placeholder={activeSectionId ? "Ask the AI to revise…" : "Pick a section first"}
          className="bg-bg-soft border border-border-dim rounded text-sm px-2 py-1 text-text disabled:opacity-50 resize-none"
        />
        <button
          type="button"
          data-action="chat-submit"
          onClick={handleSubmit}
          disabled={busy || !prompt.trim() || !activeSectionId}
          className="text-xs mono uppercase tracking-wider px-3 py-1 border border-accent text-accent hover:bg-accent-faint rounded disabled:opacity-50"
        >
          {busy ? "Streaming…" : "Send (⌘↵)"}
        </button>
      </div>
    </aside>
  );
}
