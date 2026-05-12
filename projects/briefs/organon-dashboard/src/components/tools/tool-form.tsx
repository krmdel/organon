"use client";

import { useState } from "react";
import type { ToolCatalogEntry } from "@/lib/tools/catalog";

export type ToolFormProps = {
  tool: ToolCatalogEntry;
  project: string;
  onResultStream: (chunk: string) => void;
  onArtifact: (artifact: { _artifact?: string; id?: string }) => void;
};

export function ToolForm({ tool, project, onResultStream, onArtifact }: ToolFormProps) {
  const [prompt, setPrompt] = useState("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRun = async () => {
    if (!prompt.trim()) return;
    setRunning(true);
    setError(null);
    try {
      const res = await fetch("/api/tools/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project, tool_id: tool.id, prompt: prompt.trim() }),
      });
      if (!res.ok) {
        const j = await res.json();
        throw new Error(j?.error ?? `HTTP ${res.status}`);
      }
      if (!res.body) throw new Error("no SSE body");
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
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
            if (data.chunk) onResultStream(data.chunk);
            if (data.artifact) onArtifact(data.artifact);
            if (data.message) setError(String(data.message));
          } catch { /* not JSON */ }
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="border border-border-dim rounded bg-bg-elev px-4 py-3">
      <div className="flex items-center justify-between">
        <div>
          <div className="mono text-[11px] uppercase tracking-[0.2em] text-text-muted">
            Run · {tool.name}
          </div>
          <div className="mono text-[10px] text-text-muted">
            {tool.source === "mcp" ? "MCP server (CLI hint only)" : `local skill · ${tool.id}`}
          </div>
        </div>
        <button
          type="button"
          onClick={handleRun}
          disabled={running || !prompt.trim() || tool.source === "mcp"}
          className="text-xs mono uppercase tracking-wider px-3 py-1 border border-accent text-accent hover:bg-accent-faint rounded disabled:opacity-50"
          title={tool.source === "mcp" ? "MCP tools are CLI-invokable only" : undefined}
        >
          {running ? "Running…" : "Run"}
        </button>
      </div>
      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder={tool.source === "mcp"
          ? "MCP tools are not invokable from the dashboard; this surface lets you preview the trigger phrasing."
          : `Describe the task for ${tool.name}…`}
        className="mt-3 w-full min-h-[88px] bg-bg border border-border-dim rounded px-3 py-2 text-sm text-text focus:border-accent outline-none resize-y"
      />
      {error && <div className="mt-2 mono text-xs text-danger">⚠ {error}</div>}
    </div>
  );
}
