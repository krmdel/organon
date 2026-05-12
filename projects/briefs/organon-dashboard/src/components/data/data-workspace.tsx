"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type {
  ColumnType,
  DataframeArtifact,
  FigureArtifact,
  StatResultArtifact,
} from "@/lib/artifacts/types";
import type { Recommendation, WizardAnswers } from "@/lib/data/stat-picker";
import type { PlotKind } from "@/lib/data/plot-schemas";
import { FileUploader } from "./file-uploader";
import { DataFileList } from "./data-file-list";
import { DataframePreview } from "./dataframe-preview";
import { StatTestPicker } from "./stat-test-picker";
import { StatRecommendation } from "./stat-recommendation";
import { StatResultCard } from "./stat-result-card";
import { PlotPicker } from "./plot-picker";
import { PlotRenderer } from "./plot-renderer";
import { PlotHistory } from "./plot-history";
import { ChatPanel } from "./chat-panel";
export type DataWorkspaceProps = {
  project: string;
  initialFiles: DataframeArtifact[];
  initialFigures: FigureArtifact[];
  initialResults: StatResultArtifact[];
  initialFileId?: string;
  initialTab?: "preview" | "stats" | "plots" | "chat";
};

type Tab = "preview" | "stats" | "plots" | "chat";

export function DataWorkspace({
  project,
  initialFiles,
  initialFigures,
  initialResults,
  initialFileId,
  initialTab,
}: DataWorkspaceProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [files, setFiles] = useState<DataframeArtifact[]>(initialFiles);
  const [figures, setFigures] = useState<FigureArtifact[]>(initialFigures);
  const [results, setResults] = useState<StatResultArtifact[]>(initialResults);
  const [tab, setTab] = useState<Tab>(initialTab ?? "preview");
  const [activeId, setActiveId] = useState<string | null>(
    initialFileId ?? initialFiles[0]?.id ?? null,
  );
  const [active, setActive] = useState<DataframeArtifact | null>(
    initialFiles.find((f) => f.id === (initialFileId ?? initialFiles[0]?.id)) ?? null,
  );
  const [overrideBusy, setOverrideBusy] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);

  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [recsBusy, setRecsBusy] = useState(false);
  const [runningRec, setRunningRec] = useState<string | null>(null);
  const [activeFigId, setActiveFigId] = useState<string | null>(initialFigures[0]?.id ?? null);
  const [plotBusy, setPlotBusy] = useState(false);
  // Phase 12a (v1.0.1) — D-7 soft archive of stat results.
  const [showArchived, setShowArchived] = useState(false);
  // Phase 12c (v1.0.1) — D-3 picker outcome → result-card mismatch hint.
  const [pickerOutcome, setPickerOutcome] = useState<string | null>(null);

  const refreshFiles = useCallback(async () => {
    try {
      const res = await fetch(`/api/data/files?project=${encodeURIComponent(project)}`);
      const json = await res.json();
      if (Array.isArray(json.files)) setFiles(json.files);
    } catch { /* keep last good */ }
  }, [project]);

  const refreshFigures = useCallback(async () => {
    try {
      const res = await fetch(`/api/data/figures?project=${encodeURIComponent(project)}`);
      const json = await res.json();
      if (Array.isArray(json.figures)) setFigures(json.figures);
    } catch { /* keep last good */ }
  }, [project]);

  const refreshResults = useCallback(async () => {
    try {
      const res = await fetch(`/api/data/results?project=${encodeURIComponent(project)}`);
      const json = await res.json();
      if (Array.isArray(json.results)) setResults(json.results);
    } catch { /* keep last good */ }
  }, [project]);

  const handleDeletePlot = useCallback(
    async (fig_id: string) => {
      const before = figures;
      setFigures((prev) => prev.filter((f) => f.id !== fig_id));
      if (activeFigId === fig_id) setActiveFigId(null);
      try {
        const res = await fetch(
          `/api/figures/${encodeURIComponent(fig_id)}?project=${encodeURIComponent(project)}`,
          { method: "DELETE" },
        );
        if (!res.ok) {
          setFigures(before);
          return;
        }
      } catch {
        setFigures(before);
      }
    },
    [figures, activeFigId, project],
  );

  const writeUrl = useCallback(
    (fileId: string | null) => {
      const sp = new URLSearchParams(Array.from(searchParams.entries()));
      sp.set("project", project);
      if (fileId) sp.set("file", fileId); else sp.delete("file");
      router.replace(`/data?${sp.toString()}`);
    },
    [project, router, searchParams],
  );

  const selectFile = useCallback(
    async (fileId: string) => {
      setActiveId(fileId);
      writeUrl(fileId);
      const cached = files.find((f) => f.id === fileId);
      if (cached) {
        setActive(cached);
        return;
      }
      try {
        const res = await fetch(
          `/api/data/preview/${encodeURIComponent(fileId)}?project=${encodeURIComponent(project)}`,
        );
        const json = await res.json();
        if (res.ok && json.dataframe) setActive(json.dataframe);
      } catch (err) {
        setErrors((e) => [...e, err instanceof Error ? err.message : String(err)]);
      }
    },
    [files, project, writeUrl],
  );

  const handleUploaded = useCallback(
    (df: DataframeArtifact) => {
      setFiles((prev) => [df, ...prev.filter((f) => f.id !== df.id)]);
      setActive(df);
      setActiveId(df.id);
      writeUrl(df.id);
      setTab("preview");
    },
    [writeUrl],
  );

  const handleRemove = useCallback(
    async (fileId: string) => {
      try {
        await fetch(
          `/api/data/preview/${encodeURIComponent(fileId)}?project=${encodeURIComponent(project)}`,
          { method: "DELETE" },
        );
      } catch (err) {
        setErrors((e) => [...e, err instanceof Error ? err.message : String(err)]);
      }
      setFiles((prev) => prev.filter((f) => f.id !== fileId));
      if (activeId === fileId) {
        setActive(null); setActiveId(null); writeUrl(null);
      }
    },
    [activeId, project, writeUrl],
  );

  const handleColumnTypeChange = useCallback(
    async (col: string, next: ColumnType) => {
      if (!active) return;
      setOverrideBusy(true);
      try {
        const overrides: Record<string, string> = { [col]: next };
        const res = await fetch(
          `/api/data/preview/${encodeURIComponent(active.id)}?project=${encodeURIComponent(project)}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ column_overrides: overrides }),
          },
        );
        const json = await res.json();
        if (!res.ok) throw new Error(json?.error ?? `HTTP ${res.status}`);
        setActive(json.dataframe);
        setFiles((prev) => prev.map((f) => (f.id === json.dataframe.id ? json.dataframe : f)));
      } catch (err) {
        setErrors((e) => [...e, err instanceof Error ? err.message : String(err)]);
      } finally {
        setOverrideBusy(false);
      }
    },
    [active, project],
  );

  const handlePickStat = useCallback(
    async (answers: WizardAnswers) => {
      if (!active) return;
      setRecsBusy(true);
      setRecs([]);
      try {
        const res = await fetch("/api/stat-picker", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ project, file_id: active.id, answers }),
        });
        const json = await res.json();
        if (!res.ok) throw new Error(json?.error ?? `HTTP ${res.status}`);
        setRecs(json.recommendations ?? []);
      } catch (err) {
        setErrors((e) => [...e, err instanceof Error ? err.message : String(err)]);
      } finally {
        setRecsBusy(false);
      }
    },
    [active, project],
  );

  const handleRunRec = useCallback(
    async (rec: Recommendation) => {
      if (!active) return;
      setRunningRec(rec.test_name);
      try {
        // Phase 6 (fix-sprint): /api/data/analyze is now direct-Python; the
        // response is a plain {result} JSON, not SSE. The opt-in narrative
        // lives behind the Interpret button on each StatResultCard.
        const res = await fetch("/api/data/analyze", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ project, file_id: active.id, recommendation: rec }),
        });
        const json = await res.json();
        if (!res.ok) {
          throw new Error(json?.error ?? `HTTP ${res.status}`);
        }
        const result = json.result as StatResultArtifact | undefined;
        if (result) {
          setResults((prev) => [result, ...prev.filter((r) => r.id !== result.id)]);
        }
      } catch (err) {
        setErrors((e) => [...e, err instanceof Error ? err.message : String(err)]);
      } finally {
        setRunningRec(null);
      }
    },
    [active, project],
  );

  // Phase 12a (v1.0.1) — D-7 archive / unarchive a stat result.
  const handleArchiveResult = useCallback(
    async (runId: string) => {
      try {
        const res = await fetch(
          `/api/data/results/${encodeURIComponent(runId)}?project=${encodeURIComponent(project)}`,
          { method: "DELETE" },
        );
        const json = await res.json();
        if (!res.ok) throw new Error(json?.error ?? `HTTP ${res.status}`);
        const next = json.result as StatResultArtifact | undefined;
        if (next) {
          setResults((prev) => prev.map((r) => (r.id === next.id ? next : r)));
        }
      } catch (err) {
        setErrors((e) => [...e, err instanceof Error ? err.message : String(err)]);
      }
    },
    [project],
  );

  const handleUnarchiveResult = useCallback(
    async (runId: string) => {
      try {
        const res = await fetch(
          `/api/data/results/${encodeURIComponent(runId)}?project=${encodeURIComponent(project)}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ unarchive: true }),
          },
        );
        const json = await res.json();
        if (!res.ok) throw new Error(json?.error ?? `HTTP ${res.status}`);
        const next = json.result as StatResultArtifact | undefined;
        if (next) {
          setResults((prev) => prev.map((r) => (r.id === next.id ? next : r)));
        }
      } catch (err) {
        setErrors((e) => [...e, err instanceof Error ? err.message : String(err)]);
      }
    },
    [project],
  );

  const handlePlotSubmit = useCallback(
    async (kind: PlotKind, params: Record<string, unknown>) => {
      if (!active) return;
      setPlotBusy(true);
      try {
        const res = await fetch("/api/data/plot", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ project, file_id: active.id, kind, params }),
        });
        const json = await res.json();
        if (!res.ok) {
          const detail = Array.isArray(json.details) ? json.details.join("; ") : "";
          throw new Error(`${json.error}${detail ? `: ${detail}` : ""}`);
        }
        const fig = json.figure as FigureArtifact;
        setFigures((prev) => [fig, ...prev.filter((f) => f.id !== fig.id)]);
        setActiveFigId(fig.id);
      } catch (err) {
        setErrors((e) => [...e, err instanceof Error ? err.message : String(err)]);
      } finally {
        setPlotBusy(false);
      }
    },
    [active, project],
  );

  useEffect(() => {
    if (initialFileId && initialFileId !== activeId) {
      void selectFile(initialFileId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialFileId]);

  const activeFigure = figures.find((f) => f.id === activeFigId) ?? null;

  const TabButton = ({ value, label, count }: { value: Tab; label: string; count?: number }) => (
    <button
      type="button"
      onClick={() => setTab(value)}
      className={`text-xs mono uppercase tracking-wider px-3 py-1.5 border-b-2 ${
        tab === value
          ? "border-accent text-text"
          : "border-transparent text-text-dim hover:text-text"
      }`}
    >
      {label}{typeof count === "number" && count > 0 ? ` (${count})` : ""}
    </button>
  );

  return (
    <div className="flex h-full">
      <aside className="w-72 shrink-0 border-r border-border-dim flex flex-col">
        <div className="px-4 py-4 border-b border-border-dim">
          <FileUploader project={project} onUploaded={handleUploaded} />
        </div>
        <div className="flex-1 overflow-auto">
          <div className="px-4 py-3 mono text-[11px] uppercase tracking-[0.2em] text-text-muted">
            Files ({files.length})
          </div>
          <DataFileList
            files={files}
            activeFileId={activeId}
            onSelect={selectFile}
            onRemove={handleRemove}
          />
        </div>
        <div className="px-4 py-3 border-t border-border-dim flex gap-3">
          <button type="button" onClick={() => void refreshFiles()} className="mono text-[10px] uppercase tracking-wider text-text-muted hover:text-text">↻ files</button>
          <button type="button" onClick={() => void refreshFigures()} className="mono text-[10px] uppercase tracking-wider text-text-muted hover:text-text">↻ figs</button>
          <button type="button" onClick={() => void refreshResults()} className="mono text-[10px] uppercase tracking-wider text-text-muted hover:text-text">↻ results</button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        <div className="px-6 py-5 max-w-[1400px]">
          <header className="mb-5">
            <div className="mono text-[11px] uppercase tracking-[0.2em] text-text-muted">Data</div>
            <h1 className="text-2xl text-text mt-1">{project}</h1>
            <p className="text-sm text-text-dim mt-1">
              Upload tabular data, preview, run guided statistical tests, generate plots.
            </p>
          </header>

          {errors.length > 0 && (
            <div className="mb-4 px-3 py-2 border border-danger/40 bg-danger/10 rounded">
              {errors.map((e, i) => (
                <div key={i} className="mono text-xs text-danger">{e}</div>
              ))}
              <button type="button" onClick={() => setErrors([])} className="mt-1 mono text-[10px] uppercase tracking-wider text-text-muted hover:text-text">dismiss</button>
            </div>
          )}

          {active ? (
            <>
              <div className="border-b border-border-dim mb-4 flex gap-1">
                <TabButton value="preview" label="Preview" />
                <TabButton value="stats" label="Stats" count={results.length} />
                <TabButton value="plots" label="Plots" count={figures.length} />
                <TabButton value="chat" label="Chat" />
              </div>

              {tab === "preview" && (
                <DataframePreview
                  dataframe={active}
                  onColumnTypeChange={handleColumnTypeChange}
                  busy={overrideBusy}
                />
              )}

              {tab === "stats" && (
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-3">
                    <StatTestPicker
                      dataframe={active}
                      onSubmit={handlePickStat}
                      loading={recsBusy}
                      onCurrentOutcomeChange={setPickerOutcome}
                    />
                    {recs.length > 0 && (
                      <div className="space-y-2">
                        {recs.map((r) => (
                          <StatRecommendation
                            key={r.test_name}
                            recommendation={r}
                            onRun={() => handleRunRec(r)}
                            isRunning={runningRec === r.test_name}
                            disabled={runningRec !== null && runningRec !== r.test_name}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="mono text-[11px] uppercase tracking-[0.2em] text-text-muted">
                        Results ({results.filter((r) => !r.archived).length})
                      </div>
                      {results.some((r) => r.archived) ? (
                        <button
                          type="button"
                          onClick={() => setShowArchived((v) => !v)}
                          data-action="toggle-archived"
                          className="mono text-[10px] uppercase tracking-wider text-text-muted hover:text-text"
                        >
                          {showArchived
                            ? `Hide ${results.filter((r) => r.archived).length} archived`
                            : `Show ${results.filter((r) => r.archived).length} archived`}
                        </button>
                      ) : null}
                    </div>
                    {results.filter((r) => showArchived || !r.archived).length === 0 ? (
                      <div className="text-xs text-text-muted px-3 py-4 border border-dashed border-border-dim rounded">
                        No results yet. Pick a test on the left.
                      </div>
                    ) : (
                      results
                        .filter((r) => showArchived || !r.archived)
                        .map((r) => (
                          <StatResultCard
                            key={r.id}
                            result={r}
                            project={project}
                            isArchived={r.archived === true}
                            onArchive={handleArchiveResult}
                            onUnarchive={handleUnarchiveResult}
                            currentPickerOutcome={pickerOutcome}
                          />
                        ))
                    )}
                  </div>
                </div>
              )}

              {tab === "chat" && (
                <ChatPanel
                  project={project}
                  active={active}
                  onArtifactPersisted={(art) => {
                    if (art._artifact === "stat-result") void refreshResults();
                    if (art._artifact === "figure") void refreshFigures();
                  }}
                />
              )}

              {tab === "plots" && (
                <div className="grid grid-cols-[320px_minmax(0,1fr)] gap-4">
                  <div className="space-y-3">
                    <PlotPicker
                      dataframe={active}
                      onSubmit={handlePlotSubmit}
                      loading={plotBusy}
                    />
                    <div className="border border-border-dim rounded bg-bg-elev">
                      <div className="px-3 py-2 mono text-[11px] uppercase tracking-[0.2em] text-text-muted border-b border-border-dim">
                        History ({figures.length})
                      </div>
                      <PlotHistory
                        figures={figures}
                        activeFigId={activeFigId}
                        project={project}
                        onSelect={setActiveFigId}
                        onDelete={handleDeletePlot}
                      />
                    </div>
                  </div>
                  <div>
                    {activeFigure ? (
                      <PlotRenderer figure={activeFigure} project={project} />
                    ) : (
                      <div className="border border-dashed border-border-dim rounded px-8 py-16 text-center">
                        <div className="mono text-[11px] uppercase tracking-[0.2em] text-text-muted">
                          No figure selected
                        </div>
                        <div className="mt-2 text-sm text-text-dim">
                          Pick a plot kind on the left, fill the params, hit Generate.
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="border border-dashed border-border-dim rounded px-8 py-16 text-center">
              <div className="mono text-[11px] uppercase tracking-[0.2em] text-text-muted">
                No file selected
              </div>
              <div className="mt-2 text-sm text-text-dim">
                Drop a CSV / XLSX / JSON in the panel on the left, or pick a file from the list.
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
