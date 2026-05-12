"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { FigureArtifact } from "@/lib/artifacts/types";
import { extractArtifactsFromChunk } from "@/lib/artifacts/parser";
import { fluxFillCostCents, megapixels } from "@/lib/images/pricing";
import { PromptForm } from "./prompt-form";
import { ImageCanvas } from "./image-canvas";
import { MaskTools, type MaskTool } from "./mask-tools";
import { VersionStrip } from "./version-strip";
import { CaptionCard } from "./caption-card";
import { LegendCard } from "./legend-card";
import { CostGateModal } from "./cost-gate-modal";
import { StepIndicator, FIGURE_STEP_LABELS, type Step } from "./step-indicator";
import { AnnotateTools, type AnnotateTool } from "./annotate-tools";
import { AnnotationLayer } from "./annotation-layer";
import type { AnnotationStroke } from "@/lib/figures/annotations";
import type { Style, SubStyle } from "./style-picker";
import { subscribeToTask, type TaskStreamEvent } from "@/lib/state/task-attach";

export type FiguresWorkspaceProps = {
  project: string;
  initialFigures: FigureArtifact[];
  initialFigId?: string;
};

type RunState = "idle" | "generating" | "editing" | "locking";

export function FiguresWorkspace({ project, initialFigures, initialFigId }: FiguresWorkspaceProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [figures, setFigures] = useState<FigureArtifact[]>(initialFigures);
  const [activeFigId, setActiveFigId] = useState<string | null>(
    initialFigId ?? initialFigures[0]?.id ?? null,
  );
  const [versions, setVersions] = useState<FigureArtifact[]>([]);
  const [activeVersion, setActiveVersion] = useState<number | null>(null);
  const [tool, setTool] = useState<MaskTool>("none");
  const [maskBlob, setMaskBlob] = useState<Blob | null>(null);
  const [editPrompt, setEditPrompt] = useState("");
  const [run, setRun] = useState<RunState>("idle");
  const [stream, setStream] = useState<string | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [gateOpen, setGateOpen] = useState(false);
  const [estimateCents, setEstimateCents] = useState(5);
  const [skipGate, setSkipGate] = useState(false);
  const [sessionCostCents, setSessionCostCents] = useState(0);
  const pendingEdit = useRef<null | (() => Promise<void>)>(null);
  // Phase 14b (v1.0.1) — F-2 ANNOTATE vs MASK mode separation.
  // Mode toggle is exclusive: ANNOTATE strokes never trigger inpaint;
  // EDIT WITH AI surfaces the mask toolbar + prompt-form. Switching
  // modes preserves both states (annotations + mask both stay).
  const [figureMode, setFigureMode] = useState<"edit-with-ai" | "annotate">(
    "edit-with-ai",
  );
  const [annotateTool, setAnnotateTool] = useState<AnnotateTool>("none");
  const [annotateColor, setAnnotateColor] = useState<string>("#ef4444");
  const [annotateThickness, setAnnotateThickness] = useState<number>(3);
  const [annotations, setAnnotations] = useState<AnnotationStroke[]>([]);
  const annotationsHydratedFigRef = useRef<string | null>(null);
  // Phase 19 (v1.1+) — F-5 detailed-legend SSE state. Streaming text
  // is surfaced live in the LegendCard until the route emits the
  // figure-legend artifact, at which point figures[] is updated and
  // streamingLegend resets.
  const [legendBusy, setLegendBusy] = useState<boolean>(false);
  const [streamingLegend, setStreamingLegend] = useState<string | null>(null);
  // Phase 64 (v2.2) — M3: in-panel re-attach for in-flight figure-
  // generate tasks discovered via /api/tasks?project=<slug> on mount.
  // Each card stays in the panel until its task either lands a figure
  // (success → prepended to figures + removed) or fails (status flips
  // to "failed" with a Retry affordance).
  type RunningFigureTask = {
    task_id: string;
    prompt: string;
    style?: Style | null;
    sub_style?: SubStyle | null;
    status: "running" | "failed";
    error?: string;
  };
  const [runningTasks, setRunningTasks] = useState<RunningFigureTask[]>([]);
  const reattachedTaskIdsRef = useRef<Set<string>>(new Set());
  const [collapsedDates, setCollapsedDates] = useState<Set<string>>(new Set());

  const figureGroups = useMemo(() => {
    const buckets = new Map<string, FigureArtifact[]>();
    for (const f of figures) {
      const key = (f.created_at ?? "").slice(0, 10) || "unknown";
      const arr = buckets.get(key);
      if (arr) arr.push(f);
      else buckets.set(key, [f]);
    }
    return Array.from(buckets.entries())
      .map(([date, figs]) => ({ date, figures: figs }))
      .sort((a, b) => (a.date < b.date ? 1 : -1));
  }, [figures]);
  const newestFigureDate = figureGroups[0]?.date ?? null;
  const isDateExpanded = (date: string) => {
    const baseOpen = date === newestFigureDate;
    const flipped = collapsedDates.has(date);
    return baseOpen ? !flipped : flipped;
  };
  const toggleDate = (date: string) => {
    setCollapsedDates((prev) => {
      const next = new Set(prev);
      if (next.has(date)) next.delete(date);
      else next.add(date);
      return next;
    });
  };

  const activeFigure = useMemo(
    () =>
      versions.find((v) => v.version === activeVersion) ??
      versions[versions.length - 1] ??
      null,
    [versions, activeVersion],
  );

  // Phase 14c (v1.0.1) — F-3 read-only enforcement when viewing a
  // historical version. Latest version = highest version number; any
  // earlier version locks the canvas + hides the editing affordances.
  // The user can still flip back to latest to resume editing.
  const latestVersion = useMemo(
    () =>
      versions.length > 0
        ? Math.max(...versions.map((v) => v.version))
        : 1,
    [versions],
  );
  const isViewingHistorical =
    !!activeFigure && activeFigure.version < latestVersion;

  // Phase 14a (v1.0.1) — F-4 guided-flow step indicator. Derive five
  // canonical step states from existing workspace state; the indicator
  // is visualisation-only (progressive disclosure is enforced
  // separately). Order: Generate · Mask · Edit prompt · Apply edit ·
  // Lock + caption.
  const figureSteps = useMemo<Step[]>(() => {
    const hasFigure = !!activeFigure;
    const hasMask = !!maskBlob;
    const hasEditPrompt = editPrompt.trim().length > 0;
    const hasNewerVersion = (activeFigure?.version ?? 1) >= 2;
    const isLocked = !!activeFigure?.locked;
    return [
      { label: FIGURE_STEP_LABELS[0], complete: hasFigure, available: true },
      { label: FIGURE_STEP_LABELS[1], complete: hasMask, available: hasFigure },
      { label: FIGURE_STEP_LABELS[2], complete: hasEditPrompt, available: hasMask },
      { label: FIGURE_STEP_LABELS[3], complete: hasNewerVersion, available: hasMask && hasEditPrompt },
      { label: FIGURE_STEP_LABELS[4], complete: isLocked, available: hasFigure },
    ];
  }, [activeFigure, maskBlob, editPrompt]);

  const writeUrl = useCallback(
    (figId: string | null) => {
      const sp = new URLSearchParams(Array.from(searchParams.entries()));
      sp.set("project", project);
      if (figId) sp.set("fig", figId); else sp.delete("fig");
      router.replace(`/figures?${sp.toString()}`);
    },
    [project, router, searchParams],
  );

  const refreshFigures = useCallback(async () => {
    try {
      const res = await fetch(`/api/data/figures?project=${encodeURIComponent(project)}`);
      const json = await res.json();
      if (Array.isArray(json.figures)) setFigures(json.figures);
    } catch { /* keep last good */ }
  }, [project]);

  // Phase 63 (v2.2) — M2: optimistic delete with restore-on-failure.
  // Mirrors the Phase 62 DraftList handler. Cascades to mask + version
  // files via the route's recursive rmSync.
  const handleDeleteFigure = useCallback(
    async (fig_id: string) => {
      const before = figures;
      setFigures((prev) => prev.filter((f) => f.id !== fig_id));
      try {
        const res = await fetch(
          `/api/figures/${encodeURIComponent(fig_id)}?project=${encodeURIComponent(project)}`,
          { method: "DELETE" },
        );
        if (!res.ok) {
          setFigures(before);
          let msg = `Delete failed (${res.status})`;
          try {
            const j = await res.json();
            if (j?.error) msg = j.error;
          } catch { /* keep generic */ }
          setErrors((e) => [...e, msg]);
          return;
        }
        if (activeFigId === fig_id) {
          setActiveFigId(null);
          setVersions([]);
          setActiveVersion(null);
          const sp = new URLSearchParams(Array.from(searchParams.entries()));
          sp.set("project", project);
          sp.delete("fig");
          router.replace(`/figures?${sp.toString()}`);
        }
      } catch (err) {
        setFigures(before);
        setErrors((e) => [...e, err instanceof Error ? err.message : String(err)]);
      }
    },
    [figures, activeFigId, project, router, searchParams],
  );

  const loadVersions = useCallback(
    async (figId: string) => {
      try {
        const res = await fetch(
          `/api/images/${encodeURIComponent(figId)}?project=${encodeURIComponent(project)}`,
        );
        const json = await res.json().catch(() => ({}));
        if (res.ok && Array.isArray(json.versions) && json.versions.length > 0) {
          setVersions(json.versions);
          setActiveVersion(json.versions[json.versions.length - 1]?.version ?? null);
          return;
        }
        // Phase 7 T6.8 — legacy single-version figures written by /data
        // (matplotlib plots) have a library_path but no figures/<fig_id>/
        // versions directory. Synthesize a v1 from the figures-list entry
        // so the workspace can still display + caption them.
        const fallback = figures.find((f) => f.id === figId);
        if (fallback) {
          const synthetic: FigureArtifact = {
            ...fallback,
            version: fallback.version ?? 1,
            locked: fallback.locked ?? true,
          };
          setVersions([synthetic]);
          setActiveVersion(synthetic.version);
          return;
        }
        setErrors((e) => [...e, json?.error ?? `versions HTTP ${res.status}`]);
      } catch (err) {
        setErrors((e) => [...e, err instanceof Error ? err.message : String(err)]);
      }
    },
    [project, figures],
  );

  useEffect(() => {
    if (activeFigId) void loadVersions(activeFigId);
    else { setVersions([]); setActiveVersion(null); }
  }, [activeFigId, loadVersions]);

  // Phase 14b — hydrate annotations from disk on figure switch.
  // Strokes are figure-scoped, NOT version-scoped (annotations live
  // alongside the figure, not bound to any single FAL fill).
  useEffect(() => {
    if (!activeFigId) {
      setAnnotations([]);
      annotationsHydratedFigRef.current = null;
      return;
    }
    if (annotationsHydratedFigRef.current === activeFigId) return;
    annotationsHydratedFigRef.current = activeFigId;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(
          `/api/data/figures/${encodeURIComponent(activeFigId)}/annotations?project=${encodeURIComponent(project)}`,
        );
        if (!res.ok) {
          if (!cancelled) setAnnotations([]);
          return;
        }
        const json = await res.json();
        if (cancelled) return;
        if (json?.annotations?.strokes && Array.isArray(json.annotations.strokes)) {
          setAnnotations(json.annotations.strokes as AnnotationStroke[]);
        } else {
          setAnnotations([]);
        }
      } catch {
        if (!cancelled) setAnnotations([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeFigId, project]);

  // Phase 14b — persist annotations on every change. Debounce-free
  // because the SVG layer only emits stroke-level mutations (one stroke
  // per pointer-up; one delete per ERASER click) — POST volume stays
  // bounded.
  const updateAnnotations = useCallback(
    (next: AnnotationStroke[]) => {
      setAnnotations(next);
      if (!activeFigId) return;
      void fetch(
        `/api/data/figures/${encodeURIComponent(activeFigId)}/annotations?project=${encodeURIComponent(project)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ project, strokes: next }),
        },
      ).catch(() => {
        /* swallow — strokes stay in memory; next pointer-up retries */
      });
    },
    [activeFigId, project],
  );

  const selectFigure = useCallback(
    (figId: string) => {
      setActiveFigId(figId);
      setMaskBlob(null);
      setEditPrompt("");
      writeUrl(figId);
    },
    [writeUrl],
  );

  const consumeSse = useCallback(async (res: Response) => {
    if (!res.body) return;
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
          if (data.chunk) {
            setStream(data.chunk.split("\n").slice(-5).join("\n"));
            const { artifacts } = extractArtifactsFromChunk("", data.chunk);
            for (const art of artifacts) {
              if (art._artifact === "figure") {
                const fig = art as FigureArtifact;
                setVersions((prev) => {
                  const filtered = prev.filter((v) => v.version !== fig.version);
                  return [...filtered, fig].sort((a, b) => a.version - b.version);
                });
                setActiveVersion(fig.version);
                if (!activeFigId) selectFigure(fig.id);
              }
            }
          }
          if (data.fig_id && !activeFigId) selectFigure(data.fig_id);
          if (data.message) setErrors((e) => [...e, data.message]);
          if (data.artifact?._artifact === "figure") {
            const fig = data.artifact as FigureArtifact;
            setVersions((prev) => {
              const filtered = prev.filter((v) => v.version !== fig.version);
              return [...filtered, fig].sort((a, b) => a.version - b.version);
            });
            setActiveVersion(fig.version);
            if (!activeFigId) selectFigure(fig.id);
          }
        } catch { /* ignore */ }
      }
    }
  }, [activeFigId, selectFigure]);

  // Phase 64 (v2.2) — M3: subscribe to a single figure-generate task and
  // route its events into workspace state. Successful task-done with a
  // figure artifact prepends to figures + drops the running placeholder.
  // Failure flips status to "failed" so the card surfaces a Retry button
  // (handled inline in the running-tasks render).
  const attachToFigureTask = useCallback(
    (task: RunningFigureTask) => {
      if (reattachedTaskIdsRef.current.has(task.task_id)) return;
      reattachedTaskIdsRef.current.add(task.task_id);
      let landedFigure = false;
      const handler = (evt: TaskStreamEvent) => {
        if (evt.type === "artifact") {
          const art = evt.artifact as { _artifact?: string } | null;
          if (art && art._artifact === "figure") {
            const fig = art as unknown as FigureArtifact;
            landedFigure = true;
            setFigures((prev) => [fig, ...prev.filter((f) => f.id !== fig.id)]);
            setRunningTasks((prev) => prev.filter((t) => t.task_id !== task.task_id));
          }
        } else if (evt.type === "done") {
          if (evt.success === false || (!landedFigure && evt.success !== true)) {
            setRunningTasks((prev) =>
              prev.map((t) =>
                t.task_id === task.task_id
                  ? { ...t, status: "failed", error: evt.message ?? evt.reason ?? "Generation failed" }
                  : t,
              ),
            );
          } else if (landedFigure) {
            // already pruned above; defensive prune in case the artifact
            // event landed before the task-completed sentinel.
            setRunningTasks((prev) => prev.filter((t) => t.task_id !== task.task_id));
          }
        } else if (evt.type === "error") {
          setRunningTasks((prev) =>
            prev.map((t) =>
              t.task_id === task.task_id
                ? { ...t, status: "failed", error: evt.message }
                : t,
            ),
          );
        }
      };
      return subscribeToTask(task.task_id, handler);
    },
    [],
  );

  // Phase 64 (v2.2) — M3: mount-time discovery of in-flight tasks. The
  // header tasks-panel polls the same endpoint every 5s; here we hit it
  // once on mount + on project change so the figures workspace's left
  // panel mirrors the global view for the figure surface only.
  useEffect(() => {
    let cancelled = false;
    const teardowns: Array<() => void> = [];
    void (async () => {
      try {
        const res = await fetch(`/api/tasks?project=${encodeURIComponent(project)}`);
        if (!res.ok) return;
        const json = (await res.json()) as { running?: Array<{ task_id: string; kind: string; payload?: Record<string, unknown> | null }> };
        if (cancelled || !Array.isArray(json.running)) return;
        const figureTasks = json.running.filter((t) => t.kind === "figure-generate");
        const fresh: RunningFigureTask[] = figureTasks.map((t) => ({
          task_id: t.task_id,
          prompt:
            typeof t.payload?.prompt === "string"
              ? (t.payload.prompt as string)
              : "Generating figure…",
          style:
            (t.payload?.style as Style | undefined) ?? null,
          sub_style:
            (t.payload?.sub_style as SubStyle | undefined) ?? null,
          status: "running",
        }));
        if (fresh.length === 0) return;
        setRunningTasks((prev) => {
          const known = new Set(prev.map((t) => t.task_id));
          return [...prev, ...fresh.filter((t) => !known.has(t.task_id))];
        });
        for (const t of fresh) {
          const teardown = attachToFigureTask(t);
          if (teardown) teardowns.push(teardown);
        }
      } catch {
        /* leave panel without re-attached cards on transient failure */
      }
    })();
    return () => {
      cancelled = true;
      for (const t of teardowns) t();
    };
  }, [project, attachToFigureTask]);

  const handleGenerate = useCallback(
    async (p: { prompt: string; style: Style; sub_style?: SubStyle | null }) => {
      setRun("generating");
      setStream("Spawning viz-nano-banana…");
      try {
        const res = await fetch("/api/images/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ project, prompt: p.prompt, style: p.style, sub_style: p.sub_style ?? null }),
        });
        if (!res.ok) {
          const j = await res.json();
          throw new Error(j?.error ?? `HTTP ${res.status}`);
        }
        await consumeSse(res);
        await refreshFigures();
      } catch (err) {
        setErrors((e) => [...e, err instanceof Error ? err.message : String(err)]);
      } finally {
        setStream(null);
        setRun("idle");
      }
    },
    [project, consumeSse, refreshFigures],
  );

  const fireEdit = useCallback(async () => {
    if (!activeFigId || !maskBlob || !editPrompt.trim()) return;
    setRun("editing");
    setStream("Calling FAL FLUX.1 Pro Fill…");
    try {
      const form = new FormData();
      form.set("project", project);
      form.set("fig_id", activeFigId);
      form.set("prompt", editPrompt.trim());
      form.set("mask", maskBlob, "mask.png");
      const res = await fetch("/api/images/edit", { method: "POST", body: form });
      const json = await res.json();
      if (!res.ok) throw new Error(json?.error ?? `HTTP ${res.status}`);
      const fig = json.figure as FigureArtifact;
      setVersions((prev) => [...prev.filter((v) => v.version !== fig.version), fig].sort((a, b) => a.version - b.version));
      setActiveVersion(fig.version);
      setSessionCostCents((c) => c + (fig.cost_cents ?? 0));
      setMaskBlob(null);
      setEditPrompt("");
      setTool("none");
      await refreshFigures();
    } catch (err) {
      setErrors((e) => [...e, err instanceof Error ? err.message : String(err)]);
    } finally {
      setStream(null);
      setRun("idle");
    }
  }, [activeFigId, editPrompt, maskBlob, project, refreshFigures]);

  const handleSubmitEdit = useCallback(async () => {
    if (!activeFigId || !maskBlob || !editPrompt.trim() || !activeFigure) return;
    // Estimate cost from base image MP — proxy via mask MP rounded up.
    const cents = fluxFillCostCents(megapixels(1024, 1024));  // ~5 cents default
    setEstimateCents(cents);
    if (skipGate) {
      await fireEdit();
    } else {
      pendingEdit.current = fireEdit;
      setGateOpen(true);
    }
  }, [activeFigId, activeFigure, editPrompt, maskBlob, skipGate, fireEdit]);

  const handleLock = useCallback(async () => {
    if (!activeFigId || activeVersion === null) return;
    setRun("locking");
    setStream("Calling sci-writing for caption + alt text…");
    try {
      const res = await fetch("/api/images/lock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project, fig_id: activeFigId, version: activeVersion }),
      });
      if (!res.ok) {
        const j = await res.json();
        throw new Error(j?.error ?? `HTTP ${res.status}`);
      }
      await consumeSse(res);
      await loadVersions(activeFigId);
    } catch (err) {
      setErrors((e) => [...e, err instanceof Error ? err.message : String(err)]);
    } finally {
      setStream(null);
      setRun("idle");
    }
  }, [activeFigId, activeVersion, consumeSse, loadVersions, project]);

  // Phase 19 (v1.1+) — F-5 detailed-legend generation. Spawns
  // sci-writing in generate-figure-legend mode; persists the legend
  // onto figure.detailed_legend via the route, then refreshes versions
  // so the LegendCard picks up the new value.
  const handleGenerateLegend = useCallback(
    async (opts?: { refine_prompt?: string }) => {
      if (!activeFigId || !activeFigure?.locked) return;
      setLegendBusy(true);
      setStreamingLegend(null);
      try {
        const res = await fetch(
          `/api/data/figures/${encodeURIComponent(activeFigId)}/legend?project=${encodeURIComponent(project)}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              project,
              ...(opts?.refine_prompt ? { refine_prompt: opts.refine_prompt } : {}),
            }),
          },
        );
        if (!res.ok) {
          const j = await res.json();
          throw new Error(j?.error ?? `HTTP ${res.status}`);
        }
        await consumeSse(res);
        await loadVersions(activeFigId);
      } catch (err) {
        setErrors((e) => [...e, err instanceof Error ? err.message : String(err)]);
      } finally {
        setLegendBusy(false);
        setStreamingLegend(null);
      }
    },
    [activeFigId, activeFigure?.locked, consumeSse, loadVersions, project],
  );

  // Phase 24 (v1.2) — F-5+ revert active legend to a history entry's
  // text. Workspace owns the fetch + state pump; legend-card stays
  // presentational. Refreshes versions so the strip + legend pick up
  // the new value.
  const handleRevertLegend = useCallback(
    async (version: number) => {
      if (!activeFigId || !activeFigure?.locked) return;
      setLegendBusy(true);
      try {
        const res = await fetch(
          `/api/data/figures/${encodeURIComponent(activeFigId)}/legend/${version}?project=${encodeURIComponent(project)}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ project, revert: true }),
          },
        );
        if (!res.ok) {
          const j = await res.json();
          throw new Error(j?.error ?? `HTTP ${res.status}`);
        }
        await loadVersions(activeFigId);
      } catch (err) {
        setErrors((e) => [...e, err instanceof Error ? err.message : String(err)]);
      } finally {
        setLegendBusy(false);
      }
    },
    [activeFigId, activeFigure?.locked, loadVersions, project],
  );

  const figurePngUrl = activeFigure
    ? `/api/figures/${encodeURIComponent(activeFigure.id)}/${encodeURIComponent(
        (activeFigure.png_path.split("/").pop() ?? `v${activeFigure.version}.png`),
      )}?project=${encodeURIComponent(project)}`
    : null;

  return (
    <div className="flex h-full">
      <aside className="w-72 shrink-0 border-r border-border-dim flex flex-col">
        <div className="px-4 py-4 border-b border-border-dim">
          <PromptForm onSubmit={handleGenerate} loading={run === "generating"} />
        </div>
        <div className="flex-1 overflow-auto">
          <div className="px-4 py-3 mono text-[11px] uppercase tracking-[0.2em] text-text-muted flex items-center justify-between">
            <span>Figures ({figures.length})</span>
            {sessionCostCents > 0 && (
              <span className="mono text-[10px] text-text-muted normal-case tracking-normal">
                ~${(sessionCostCents / 100).toFixed(2)}/session
              </span>
            )}
          </div>
          {/* Phase 64 (v2.2) — M3: in-flight figure-generate tasks
              re-attached on mount. Cards live above the figure list so
              the user always sees what's running for this project. */}
          {runningTasks.length > 0 && (
            <ul className="divide-y divide-border-dim border-b border-border-dim">
              {runningTasks.map((rt) => (
                <li key={rt.task_id}>
                  <div
                    data-figure-running={rt.task_id}
                    data-status={rt.status}
                    className="flex items-center gap-3 px-3 py-2"
                  >
                    <div
                      className={`w-12 h-12 rounded flex items-center justify-center ${rt.status === "failed" ? "bg-danger/10" : "bg-bg-soft"}`}
                    >
                      <span
                        className={`w-2 h-2 rounded-full ${rt.status === "failed" ? "bg-danger" : "bg-accent animate-pulse"}`}
                      />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="mono text-[11px] text-text-muted truncate">
                        {rt.status === "failed" ? "Failed" : "Generating…"}
                      </div>
                      <div className="text-xs text-text-dim truncate" title={rt.prompt}>
                        {rt.prompt.length > 60 ? rt.prompt.slice(0, 59) + "…" : rt.prompt}
                      </div>
                      {rt.status === "failed" && rt.error && (
                        <div className="mono text-[10px] text-danger truncate" title={rt.error}>
                          {rt.error}
                        </div>
                      )}
                    </div>
                    {rt.status === "failed" && (
                      <button
                        type="button"
                        data-figure-retry={rt.task_id}
                        onClick={() => {
                          setRunningTasks((prev) =>
                            prev.filter((t) => t.task_id !== rt.task_id),
                          );
                          reattachedTaskIdsRef.current.delete(rt.task_id);
                          void handleGenerate({
                            prompt: rt.prompt,
                            style: (rt.style ?? "scientific") as Style,
                            sub_style: rt.sub_style ?? null,
                          });
                        }}
                        className="mono text-[10px] uppercase tracking-wider px-2 py-0.5 border border-accent rounded text-accent hover:bg-accent-faint"
                        title="Retry this generation"
                      >
                        Retry
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() =>
                        setRunningTasks((prev) =>
                          prev.filter((t) => t.task_id !== rt.task_id),
                        )
                      }
                      className="mono text-[14px] text-text-muted hover:text-text"
                      title="Dismiss"
                      aria-label="Dismiss running task card"
                    >
                      ×
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
          {figures.length === 0 && runningTasks.length === 0 ? (
            <div className="px-4 py-3 text-xs text-text-muted">
              No figures yet. Generate one with the form above.
            </div>
          ) : figures.length === 0 ? null : (
            <ul>
              {figureGroups.map((g) => {
                const open = isDateExpanded(g.date);
                return (
                  <li key={g.date}>
                    <div className="group/header px-3 py-2 flex items-center gap-2 bg-bg-soft border-b border-border-dim">
                      <button
                        type="button"
                        onClick={() => toggleDate(g.date)}
                        className="mono text-[10px] text-text-muted hover:text-text"
                        title={open ? "Collapse" : "Expand"}
                      >
                        {open ? "▾" : "▸"}
                      </button>
                      <div className="flex-1 min-w-0">
                        <div className="mono text-[10px] uppercase tracking-[0.15em] text-text-muted">
                          {g.date}
                        </div>
                        <div className="mono text-[10px] text-text-muted">
                          {g.figures.length} figure{g.figures.length === 1 ? "" : "s"}
                        </div>
                      </div>
                      <button
                        type="button"
                        data-figure-delete-date={g.date}
                        onClick={(e) => {
                          e.stopPropagation();
                          e.preventDefault();
                          if (
                            typeof window !== "undefined" &&
                            window.confirm(
                              `Delete all ${g.figures.length} figure${g.figures.length === 1 ? "" : "s"} from ${g.date}? This cannot be undone.`,
                            )
                          ) {
                            for (const f of g.figures) void handleDeleteFigure(f.id);
                          }
                        }}
                        className="mono text-[14px] leading-none text-text-muted opacity-0 group-hover/header:opacity-100 hover:text-danger transition"
                        title={`Delete all ${g.figures.length} figure${g.figures.length === 1 ? "" : "s"} from ${g.date}`}
                        aria-label={`Delete all figures from ${g.date}`}
                      >
                        ×
                      </button>
                    </div>
                    {open && (
                      <ul className="divide-y divide-border-dim">
              {g.figures.map((f) => {
                const png = f.png_path.split("/").pop() ?? "v1.png";
                const url = `/api/figures/${encodeURIComponent(f.id)}/${encodeURIComponent(png)}?project=${encodeURIComponent(project)}`;
                const active = f.id === activeFigId;
                return (
                  <li key={f.id}>
                    <div className={`group flex items-stretch ${active ? "bg-accent-faint" : "hover:bg-bg-soft"}`}>
                      <button
                        type="button"
                        onClick={() => selectFigure(f.id)}
                        className="flex items-center gap-3 flex-1 min-w-0 px-3 py-2 text-left"
                      >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={url} alt="" className="w-12 h-12 object-cover bg-bg rounded" />
                        <div className="min-w-0 flex-1">
                          <div className="mono text-[11px] text-text-muted truncate">{f.id}</div>
                          <div className="text-xs text-text-dim truncate">
                            {String(f.params?.prompt ?? f.kind)}
                          </div>
                        </div>
                      </button>
                      {/* Phase 63 (v2.2) — M2: sibling × delete affordance.
                          Sibling not nested so the click never bubbles
                          into selectFigure. */}
                      <button
                        type="button"
                        data-figure-delete={f.id}
                        onClick={(e) => {
                          e.stopPropagation();
                          e.preventDefault();
                          const label = String(f.params?.prompt ?? f.id);
                          if (
                            typeof window !== "undefined" &&
                            window.confirm(
                              `Delete figure "${label}"? This cannot be undone.`,
                            )
                          ) {
                            void handleDeleteFigure(f.id);
                          }
                        }}
                        className="px-2 mono text-[14px] text-text-muted opacity-0 group-hover:opacity-100 hover:text-danger transition"
                        title="Delete figure (cannot be undone)"
                        aria-label={`Delete figure ${f.id}`}
                      >
                        ×
                      </button>
                    </div>
                  </li>
                );
              })}
                      </ul>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        <div className="px-6 py-5 max-w-[1400px]">
          <header className="mb-5">
            <div className="mono text-[11px] uppercase tracking-[0.2em] text-text-muted">Figures</div>
            <h1 className="text-2xl text-text mt-1">{project}</h1>
            <p className="text-sm text-text-dim mt-1">
              Generate via Gemini, edit regions via FAL FLUX.1 Pro Fill, lock + auto-caption via sci-writing.
            </p>
          </header>

          {/* Phase 14a (v1.0.1) — F-4 guided-flow step indicator. Derived
              live from workspace state; the indicator is visualisation-
              only — progressive disclosure is still enforced by the
              workspace itself. */}
          <StepIndicator steps={figureSteps} />


          {errors.length > 0 && (
            <div className="mb-4 px-3 py-2 border border-danger/40 bg-danger/10 rounded">
              {errors.map((e, i) => (
                <div key={i} className="mono text-xs text-danger">{e}</div>
              ))}
              <button
                type="button"
                onClick={() => setErrors([])}
                className="mt-1 mono text-[10px] uppercase tracking-wider text-text-muted hover:text-text"
              >dismiss</button>
            </div>
          )}

          {activeFigure && figurePngUrl ? (
            <div className="space-y-4">
              {/* Phase 14b (v1.0.1) — F-2 mode toggle. ANNOTATE strokes
                  never POST to FAL Fill; EDIT WITH AI surfaces the
                  existing mask + prompt-form pipeline. Switching modes
                  preserves both states (annotations + mask). */}
              <div
                data-figure-mode-toggle
                data-mode={figureMode}
                className="flex items-center gap-1"
              >
                <button
                  type="button"
                  onClick={() => setFigureMode("edit-with-ai")}
                  data-mode-option="edit-with-ai"
                  data-active={figureMode === "edit-with-ai" ? "true" : "false"}
                  className={
                    figureMode === "edit-with-ai"
                      ? "text-xs mono uppercase tracking-wider px-3 py-1.5 border border-accent rounded text-accent bg-accent-faint"
                      : "text-xs mono uppercase tracking-wider px-3 py-1.5 border border-border-dim rounded text-text-dim hover:text-text"
                  }
                >
                  Edit with AI
                </button>
                <button
                  type="button"
                  onClick={() => setFigureMode("annotate")}
                  data-mode-option="annotate"
                  data-active={figureMode === "annotate" ? "true" : "false"}
                  className={
                    figureMode === "annotate"
                      ? "text-xs mono uppercase tracking-wider px-3 py-1.5 border border-accent rounded text-accent bg-accent-faint"
                      : "text-xs mono uppercase tracking-wider px-3 py-1.5 border border-border-dim rounded text-text-dim hover:text-text"
                  }
                >
                  Annotate
                </button>
              </div>
              {/* Phase 14c (v1.0.1) — F-3 historical-view banner. When
                  the user picks an older version from the version
                  strip, the canvas locks and the editing surfaces hide.
                  Switching back to latest re-enables editing. */}
              {isViewingHistorical && (
                <div
                  data-historical-banner
                  className="border border-warn/40 rounded bg-warn/5 px-3 py-2 mono text-[10px] uppercase tracking-wider text-text-dim flex items-center justify-between gap-2"
                >
                  <span>
                    Viewing v{activeFigure.version} (read-only) — switch to v{latestVersion} to edit
                  </span>
                  <button
                    type="button"
                    onClick={() => setActiveVersion(latestVersion)}
                    data-action="goto-latest"
                    className="px-2 py-0.5 border border-accent rounded text-accent hover:bg-accent hover:text-bg transition"
                  >
                    Go to v{latestVersion}
                  </button>
                </div>
              )}
              <div className="flex items-center justify-between gap-2 flex-wrap">
                {isViewingHistorical ? (
                  <div className="mono text-[10px] uppercase tracking-wider text-text-muted">
                    Read-only view — editing tools hidden
                  </div>
                ) : figureMode === "edit-with-ai" ? (
                  <MaskTools
                    active={tool}
                    onChange={setTool}
                    onClear={() => setMaskBlob(null)}
                    hasMask={!!maskBlob}
                  />
                ) : (
                  <AnnotateTools
                    active={annotateTool}
                    onChange={setAnnotateTool}
                    color={annotateColor}
                    onColorChange={setAnnotateColor}
                    thickness={annotateThickness}
                    onThicknessChange={setAnnotateThickness}
                    onClearAll={() => updateAnnotations([])}
                    hasStrokes={annotations.length > 0}
                  />
                )}
                <div className="mono text-[10px] uppercase tracking-wider text-text-muted">
                  v{activeFigure.version} · {activeFigure.backend}
                  {activeFigure.cost_cents > 0 && ` · ${activeFigure.cost_cents}¢`}
                </div>
              </div>
              {figureMode === "edit-with-ai" ? (
                <ImageCanvas
                  figure={activeFigure}
                  pngUrl={figurePngUrl}
                  tool={isViewingHistorical ? "none" : tool}
                  onMaskChange={setMaskBlob}
                />
              ) : (
                <AnnotationLayer
                  figure={activeFigure}
                  pngUrl={figurePngUrl}
                  tool={isViewingHistorical ? "none" : annotateTool}
                  color={annotateColor}
                  thickness={annotateThickness}
                  strokes={annotations}
                  onChange={updateAnnotations}
                />
              )}
              {!isViewingHistorical && figureMode === "edit-with-ai" && tool !== "none" && (
                <div className="border border-border-dim rounded bg-bg-elev px-4 py-3 space-y-2">
                  <div className="mono text-[11px] uppercase tracking-[0.2em] text-text-muted">
                    Edit prompt
                  </div>
                  <textarea
                    value={editPrompt}
                    onChange={(e) => setEditPrompt(e.target.value)}
                    placeholder="What should the masked region become?"
                    className="w-full min-h-[64px] bg-bg border border-border-dim rounded px-3 py-2 text-sm text-text focus:border-accent outline-none resize-y"
                  />
                  <div className="flex justify-end">
                    <button
                      type="button"
                      onClick={handleSubmitEdit}
                      disabled={!maskBlob || !editPrompt.trim() || run !== "idle"}
                      className="text-xs mono uppercase tracking-wider px-3 py-1 border border-accent text-accent hover:bg-accent-faint rounded disabled:opacity-50"
                    >
                      {run === "editing" ? "Editing…" : "Apply edit"}
                    </button>
                  </div>
                </div>
              )}
              <CaptionCard
                figure={activeFigure}
                onLock={handleLock}
                onRegenerate={handleLock}
                busy={run === "locking"}
              />
              {/* Phase 19 (v1.1+) — F-5 detailed legend mounted only when
                  the active figure is locked. An unlocked figure could
                  mutate via a future edit, invalidating the legend. */}
              {activeFigure.locked && <LegendCard
                figure={activeFigure}
                onGenerateLegend={handleGenerateLegend}
                onRevertLegend={handleRevertLegend}
                busy={legendBusy}
                streamingLegend={streamingLegend}
              />}
              {/* Phase 14c (v1.0.1) — F-3 always render the strip when
                  ≥1 version exists. v1 ("original") is always
                  retrievable; older versions are read-only. */}
              {versions.length >= 1 && (
                <div>
                  <div className="mono text-[11px] uppercase tracking-[0.2em] text-text-muted mb-2 flex items-center gap-2">
                    <span>Versions ({versions.length})</span>
                    {isViewingHistorical && (
                      <span className="text-warn normal-case tracking-normal">
                        viewing v{activeFigure.version} of {latestVersion}
                      </span>
                    )}
                  </div>
                  <VersionStrip
                    versions={versions}
                    activeVersion={activeFigure.version}
                    project={project}
                    onSelect={(v) => setActiveVersion(v)}
                  />
                </div>
              )}
              {stream && (
                <pre className="mono text-[11px] text-text-muted bg-bg-elev border border-border-dim rounded p-3 max-h-32 overflow-auto whitespace-pre-wrap">
                  {stream}
                </pre>
              )}
            </div>
          ) : (
            <div className="border border-dashed border-border-dim rounded px-8 py-16 text-center">
              <div className="mono text-[11px] uppercase tracking-[0.2em] text-text-muted">
                {figures.length === 0 ? "No figures yet" : "Pick a figure"}
              </div>
              <div className="mt-2 text-sm text-text-dim">
                {figures.length === 0
                  ? "Use the prompt form on the left to generate your first one."
                  : "Click a figure in the list to load its versions."}
              </div>
            </div>
          )}
        </div>
      </main>

      <CostGateModal
        open={gateOpen}
        estimateCents={estimateCents}
        onConfirm={(remember) => {
          setGateOpen(false);
          if (remember) setSkipGate(true);
          if (pendingEdit.current) void pendingEdit.current();
          pendingEdit.current = null;
        }}
        onCancel={() => {
          setGateOpen(false);
          pendingEdit.current = null;
        }}
      />
    </div>
  );
}
