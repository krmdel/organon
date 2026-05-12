"use client";

import { useCallback, useState } from "react";
import type { DataframeArtifact } from "@/lib/artifacts/types";

// Phase 21 (v1.1+) — D-6 chat-driven data analysis panel.
//
// Natural-language prompt → SSE round-trip via /api/data/chat → streams
// the routed skill's output and persists the emitted artifact via the
// existing parser + persister. Transcript is in-memory only (per
// brief §9.3 — "ephemeral, not persisted").
//
// Mounted by data-workspace's Chat tab; tab is gated on an active file
// at the workspace level.

export type ChatTranscriptEntry = {
  id: string;
  prompt: string;
  intent: "hypothesis" | "data-analysis" | "checking";
  streaming: string;
  done: boolean;
  success?: boolean;
  artifactId?: string | null;
};

export type ChatPanelProps = {
  project: string;
  active: DataframeArtifact;
  // Workspace owns the artifact state; the panel surfaces a callback
  // so the Stats / Plots tabs refresh when an artifact lands.
  onArtifactPersisted?: (artifact: { _artifact: string; id: string }) => void;
};

export function ChatPanel({ project, active, onArtifactPersisted }: ChatPanelProps) {
  const [prompt, setPrompt] = useState("");
  const [transcript, setTranscript] = useState<ChatTranscriptEntry[]>([]);
  const [busy, setBusy] = useState(false);

  const updateEntry = useCallback(
    (id: string, patch: Partial<ChatTranscriptEntry>) => {
      setTranscript((prev) =>
        prev.map((e) => (e.id === id ? { ...e, ...patch } : e)),
      );
    },
    [],
  );

  const handleSubmit = useCallback(async () => {
    const trimmed = prompt.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setPrompt("");
    const entryId = `chat-${Date.now()}`;
    setTranscript((prev) => [
      ...prev,
      {
        id: entryId,
        prompt: trimmed,
        intent: "checking",
        streaming: "",
        done: false,
      },
    ]);
    try {
      const res = await fetch(
        `/api/data/chat?project=${encodeURIComponent(project)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ project, file_id: active.id, prompt: trimmed }),
        },
      );
      if (!res.ok) {
        const j = await res.json();
        throw new Error(j?.error ?? `HTTP ${res.status}`);
      }
      // Stream consumer — minimal SSE parser walking the response
      // body. Same shape as existing /api/draft consumers.
      const reader = res.body?.getReader();
      if (!reader) throw new Error("no SSE body");
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() ?? "";
        for (const evt of events) {
          const dataLine = evt.split("\n").find((l) => l.startsWith("data:"));
          if (!dataLine) continue;
          try {
            const data = JSON.parse(dataLine.slice(5).trim());
            if (typeof data?.intent === "string" && (data.intent === "hypothesis" || data.intent === "data-analysis")) {
              updateEntry(entryId, { intent: data.intent });
            }
            if (typeof data?.chunk === "string") {
              updateEntry(entryId, {
                streaming: (transcript.find((e) => e.id === entryId)?.streaming ?? "") + data.chunk,
              });
            }
            if (data?.artifact && typeof data.artifact === "object") {
              const art = data.artifact as { _artifact?: string; id?: string };
              if (art._artifact && art.id) {
                onArtifactPersisted?.({ _artifact: art._artifact, id: art.id });
                updateEntry(entryId, { artifactId: art.id });
              }
            }
            if (typeof data?.success === "boolean" && data?.intent !== undefined) {
              // done event — has both `success` and `intent` set.
              updateEntry(entryId, { done: true, success: data.success });
            }
          } catch { /* skip malformed event */ }
        }
      }
    } catch (err) {
      updateEntry(entryId, {
        done: true,
        success: false,
        streaming: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setBusy(false);
    }
  }, [active.id, busy, onArtifactPersisted, project, prompt, transcript, updateEntry]);

  return (
    <div data-chat-panel className="border border-border-dim rounded bg-bg-elev flex flex-col h-[600px]">
      <div className="px-3 py-2 border-b border-border-dim mono text-[10px] uppercase tracking-wider text-text-muted">
        Chat · {active.filename ?? active.id}
      </div>
      <div data-chat-transcript className="flex-1 overflow-auto px-3 py-3 space-y-3">
        {transcript.length === 0 && (
          <div className="text-xs text-text-muted italic">
            Ask a question about this dataframe — e.g. "is BMI different between groups",
            "plot weight loss vs time", "summary statistics for adherence".
          </div>
        )}
        {transcript.map((entry) => (
          <div key={entry.id} className="space-y-1">
            <div className="text-xs text-text">
              <span className="mono text-[10px] uppercase tracking-wider text-text-muted mr-2">
                you
              </span>
              {entry.prompt}
            </div>
            <div className="text-xs text-text-dim">
              <span className="mono text-[10px] uppercase tracking-wider text-text-muted mr-2">
                {entry.intent === "checking" ? "routing…" : entry.intent}
              </span>
              <span data-chat-streaming>
                {entry.streaming ||
                  (entry.done
                    ? entry.success
                      ? "(done)"
                      : "(failed)"
                    : "(running…)")}
              </span>
            </div>
            {entry.artifactId && (
              <div className="mono text-[10px] text-accent">
                ↳ artifact persisted: {entry.artifactId}
              </div>
            )}
          </div>
        ))}
      </div>
      <div className="px-3 py-2 border-t border-border-dim flex gap-2">
        <input
          data-chat-prompt
          type="text"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void handleSubmit();
            }
          }}
          disabled={busy}
          placeholder="Ask about the data…"
          className="flex-1 bg-bg-soft border border-border-dim rounded text-sm px-2 py-1 text-text disabled:opacity-50"
        />
        <button
          type="button"
          data-action="chat-submit"
          onClick={() => void handleSubmit()}
          disabled={busy || !prompt.trim()}
          className="text-xs mono uppercase tracking-wider px-3 py-1 border border-accent text-accent hover:bg-accent-faint rounded disabled:opacity-50"
        >
          {busy ? "…" : "Send"}
        </button>
      </div>
    </div>
  );
}
