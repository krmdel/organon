"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { useRouter, useSearchParams } from "next/navigation";
import type {
  HypothesisArtifact,
  HypothesisStatus,
  PaperArtifact,
  PersonaCritiqueArtifact,
} from "@/lib/artifacts/types";
import type { Persona } from "@/lib/hypothesis/shared";
import { isPersonaActive } from "@/lib/hypothesis/shared";
import { slugifyPersona } from "@/lib/hypothesis/shared";
import { ClaimForm } from "./claim-form";
import { CouncilFanout } from "./council-fanout";
import { SynthesisCard } from "./synthesis-card";
import { HypothesisHistory } from "./hypothesis-history";
import { LinkedPapersList } from "./linked-papers-list";
import { PersonasEditor } from "./personas-editor";
import { PaperDetailDrawer } from "@/components/primitives/paper-detail-drawer";
import { RunStateCard, type RunState as RunStateUi } from "@/components/primitives/run-state-card";
import { StatusBadge } from "./status-badge";
import { readWipClaim, writeWipClaim } from "@/lib/state/recent-searches";
import {
  clearActiveTask,
  readActiveTask,
  writeActiveTask,
} from "@/lib/state/task-attach";

// Phase 11 (v1.0.1) — server-computed completeness badge for the active
// hypothesis. critiques < expected = "still loading" or "council never
// finished"; synthesis present/absent reflects the reconcile state.
export type HydrationStatus = {
  critiques: number;
  expected: number;
  synthesis: "present" | "absent";
};

export type HypothesisWorkspaceProps = {
  project: string;
  initialHypotheses: HypothesisArtifact[];
  initialLibrary: PaperArtifact[];
  initialPersonas: Persona[];
  initialHypId?: string;
  initialPrefillPaperId?: string;
  initialHydrationStatus?: HydrationStatus | null;
};

// Phase 4 (fix-sprint): expanded state machine — `error` was a single bucket
// that hid timeouts and explicit cancels. The new states map 1:1 to the
// runner's `RunExitReason` so the failure card renders the right copy.
type RunState = "idle" | "running" | "succeeded" | "failed" | "timeout" | "cancelled";

type SseDone = {
  success?: boolean;
  reason?: string;
  exit_code?: number | null;
  message?: string;
};

export function HypothesisWorkspace({
  project,
  initialHypotheses,
  initialLibrary,
  initialPersonas,
  initialHypId,
  initialPrefillPaperId,
  initialHydrationStatus,
}: HypothesisWorkspaceProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [hypotheses, setHypotheses] = useState<HypothesisArtifact[]>(initialHypotheses);
  const [library, setLibrary] = useState<PaperArtifact[]>(initialLibrary);
  const [personas, setPersonas] = useState<Persona[]>(initialPersonas);
  const [activeId, setActiveId] = useState<string | null>(initialHypId ?? null);
  const [critiques, setCritiques] = useState<PersonaCritiqueArtifact[]>([]);
  const [genState, setGenState] = useState<RunState>("idle");
  const [reconcileState, setReconcileState] = useState<RunState>("idle");
  const [errors, setErrors] = useState<string[]>([]);
  const [streamingMsg, setStreamingMsg] = useState<string | null>(null);
  // Phase 4: terminal-state copy + elapsed timing for RunStateCard.
  const [runFailureMsg, setRunFailureMsg] = useState<string | null>(null);
  const [runStartedAt, setRunStartedAt] = useState<number | null>(null);
  const [now, setNow] = useState<number>(() => Date.now());
  const lastGenParamsRef = useRef<{ claim: string; paper_ids: string[] } | null>(null);
  const [filterStatus, setFilterStatus] = useState<HypothesisStatus[]>([]);
  const [filterQuery, setFilterQuery] = useState("");
  const [editingPersonas, setEditingPersonas] = useState(false);
  const [focusedIdx, setFocusedIdx] = useState(0);
  const [detailPaper, setDetailPaper] = useState<PaperArtifact | null>(null);
  const [prefillPaperIds, setPrefillPaperIds] = useState<string[]>(
    initialPrefillPaperId ? [initialPrefillPaperId] : [],
  );
  const [prefillClaim, setPrefillClaim] = useState("");
  const [personasChangedDuringRun, setPersonasChangedDuringRun] = useState(false);
  // Phase 13b (v1.0.1) — H-5 + U4 per-persona retry.
  // The slug whose retry is in-flight; CouncilFanout disables that
  // panel's button + flips its label while the SSE stream is open.
  const [retryingSlug, setRetryingSlug] = useState<string | null>(null);
  // Phase 11 (v1.0.1) — workspace state persistence.
  // 1. WIP claim restore: when the user types a claim then navigates away,
  //    pull it back on mount. Cleared on successful generate-council submit.
  // 2. Hydration badge: server-computed initial value seeds the first paint;
  //    after that, derive live from {critiques, personas, activeHypothesis}.
  const wipClaimHydratedRef = useRef(false);
  useEffect(() => {
    if (wipClaimHydratedRef.current) return;
    wipClaimHydratedRef.current = true;
    if (initialHypId) return; // active hypothesis takes precedence
    const restored = readWipClaim(project);
    if (restored) setPrefillClaim(restored);
  }, [project, initialHypId]);
  const handleClaimChange = useCallback(
    (next: string) => {
      writeWipClaim(project, next);
    },
    [project],
  );

  const abortRef = useRef<AbortController | null>(null);

  const activeHypothesis = useMemo(
    () => (activeId ? hypotheses.find((h) => h.id === activeId) ?? null : null),
    [activeId, hypotheses],
  );

  const loadCritiques = useCallback(
    async (hyp_id: string) => {
      try {
        const res = await fetch(
          `/api/hypothesis/${encodeURIComponent(hyp_id)}?project=${encodeURIComponent(project)}`,
        );
        const data = await res.json();
        if (Array.isArray(data.critiques)) setCritiques(data.critiques);
      } catch {
        // keep last good
      }
    },
    [project],
  );

  // Hydrate critiques on first load + when active hypothesis changes
  useEffect(() => {
    if (activeId) loadCritiques(activeId);
    else setCritiques([]);
  }, [activeId, loadCritiques]);

  // Phase 36 (v1.4) — re-attach effect declared further below, after
  // consumeSse/applyDone/refreshHypotheses are in scope. The Set ref is
  // declared up here so other effects can reference it if needed.
  const reattachRef = useRef<Set<string>>(new Set());

  const refreshHypotheses = useCallback(async () => {
    try {
      const res = await fetch(`/api/hypothesis?project=${encodeURIComponent(project)}`);
      const data = await res.json();
      if (Array.isArray(data.hypotheses)) setHypotheses(data.hypotheses);
    } catch {
      // ignore
    }
  }, [project]);

  const handleSelect = useCallback(
    (hyp_id: string) => {
      setActiveId(hyp_id);
      const sp = new URLSearchParams(Array.from(searchParams.entries()));
      sp.set("project", project);
      sp.set("hyp", hyp_id);
      router.replace(`/hypothesis?${sp.toString()}`);
    },
    [project, router, searchParams],
  );

  const handleNew = useCallback(() => {
    setActiveId(null);
    setCritiques([]);
    const sp = new URLSearchParams(Array.from(searchParams.entries()));
    sp.set("project", project);
    sp.delete("hyp");
    router.replace(`/hypothesis?${sp.toString()}`);
  }, [project, router, searchParams]);

  const cancelRun = useCallback(() => abortRef.current?.abort(), []);

  // Phase 4: tick a 250 ms clock while a run is active so RunStateCard's
  // elapsed counter updates.
  useEffect(() => {
    if (genState !== "running" && reconcileState !== "running") return;
    const id = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(id);
  }, [genState, reconcileState]);

  // Drain an SSE response and update workspace state for hypothesis + persona-critique events.
  // Phase 4 (fix-sprint): also captures the terminal `done` event so the
  // caller can map runner reason → UI state.
  // Phase 36 (v1.4): optional onTaskStarted callback fires on the
  // task-started / task-attached event so the caller can persist
  // task_id to localStorage.
  const consumeSse = useCallback(
    async (
      res: Response,
      ctrl: AbortController,
      onError: (msg: string) => void,
      onTaskStarted?: (task_id: string) => void,
    ): Promise<SseDone | null> => {
      if (!res.body) {
        onError("No response stream");
        return null;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let doneSummary: SseDone | null = null;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        if (ctrl.signal.aborted) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() ?? "";
        for (const block of events) {
          if (!block.trim()) continue;
          const lines = block.split("\n");
          const eventLine = lines.find((l) => l.startsWith("event: "));
          const dataLine = lines.find((l) => l.startsWith("data: "));
          if (!eventLine || !dataLine) continue;
          const event = eventLine.slice(7).trim();
          let data: {
            artifact?: unknown;
            message?: string;
            success?: boolean;
            reason?: string;
            exit_code?: number | null;
            task_id?: string;
          } = {};
          try {
            data = JSON.parse(dataLine.slice(6));
          } catch {
            continue;
          }
          if (event === "task-started" || event === "task-attached") {
            // Phase 36 (v1.4): hand the task_id back so the caller
            // can persist to localStorage for re-attach on remount.
            if (typeof data.task_id === "string" && onTaskStarted) {
              onTaskStarted(data.task_id);
            }
          } else if (event === "task-completed") {
            // Registry's terminal sentinel — server-side stream closes
            // immediately after; treat as a no-op for the client.
            continue;
          } else if (event === "done") {
            doneSummary = {
              success: data.success,
              reason: data.reason,
              exit_code: data.exit_code,
              message: data.message,
            };
          } else if (event === "artifact") {
            const a = data.artifact as
              | HypothesisArtifact
              | PersonaCritiqueArtifact
              | { _artifact?: string }
              | undefined;
            if (!a || typeof a !== "object" || !("_artifact" in a)) continue;
            if (a._artifact === "hypothesis") {
              const h = a as HypothesisArtifact;
              setHypotheses((cur) => mergeHypothesis(cur, h));
              if (h.id === activeId || !activeId) setActiveId(h.id);
            } else if (a._artifact === "persona-critique") {
              const c = a as PersonaCritiqueArtifact;
              setCritiques((cur) => {
                const filtered = cur.filter((x) => x.persona_slug !== c.persona_slug);
                return [...filtered, c];
              });
            }
          } else if (event === "stdout") {
            // Keep a tiny streaming hint while the skill emits markdown
            setStreamingMsg("Skill running…");
          } else if (event === "error") {
            onError(typeof data.message === "string" ? data.message : "skill error");
          }
        }
      }
      return doneSummary;
    },
    [activeId],
  );

  // Phase 4: map runner reason → workspace RunState + failure message.
  const applyDone = useCallback(
    (
      done: SseDone | null,
      setState: (s: RunState) => void,
      cancelled = false,
    ) => {
      if (cancelled) {
        setState("cancelled");
        setRunFailureMsg("Cancelled by you.");
        return;
      }
      if (!done) {
        setState("failed");
        setRunFailureMsg("Connection lost — your run may have completed; refresh to check.");
        return;
      }
      if (done.success === true) {
        setState("succeeded");
        setRunFailureMsg(null);
        return;
      }
      const reason = done.reason ?? "failed";
      switch (reason) {
        case "timeout":
          setState("timeout");
          setRunFailureMsg(done.message ?? "Run timed out. The skill may need a longer cap or the LLM is stuck.");
          break;
        case "cancelled":
          setState("cancelled");
          setRunFailureMsg(done.message ?? "Cancelled by you.");
          break;
        case "spawn-error":
          setState("failed");
          setRunFailureMsg(done.message ?? "Could not start the skill subprocess. Is `claude` on PATH?");
          break;
        default:
          setState("failed");
          setRunFailureMsg(
            done.message
              ?? (done.exit_code != null
                ? `Skill subprocess exited with code ${done.exit_code}.`
                : "Skill subprocess failed."),
          );
          break;
      }
    },
    [],
  );

  // Phase 36 (v1.4) — re-attach to in-flight reconcile tasks on mount
  // / active-hypothesis change. If localStorage has a task_id, GET
  // /api/tasks/{task_id}/stream and drain through consumeSse. On 404
  // the registry already evicted (likely a dashboard restart); clear
  // silently. The Set ref deduplicates within a session so we don't
  // keep re-attaching the same task on dependency churn.
  useEffect(() => {
    if (!activeId) return;
    const cacheKey = `reconcile:${activeId}`;
    if (reattachRef.current.has(cacheKey)) return;
    const task_id = readActiveTask(project, "reconcile", activeId);
    if (!task_id) return;
    reattachRef.current.add(cacheKey);
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setReconcileState("running");
    setStreamingMsg("Re-attaching to in-flight reconcile…");
    setRunStartedAt(Date.now());
    void (async () => {
      try {
        const res = await fetch(`/api/tasks/${encodeURIComponent(task_id)}/stream`, {
          signal: ctrl.signal,
        });
        if (res.status === 404) {
          clearActiveTask(project, "reconcile", activeId);
          setReconcileState("idle");
          setStreamingMsg(null);
          return;
        }
        const done = await consumeSse(
          res,
          ctrl,
          (msg) => setErrors((prev) => [...prev, msg]),
        );
        clearActiveTask(project, "reconcile", activeId);
        await refreshHypotheses();
        applyDone(done, setReconcileState);
      } catch (err) {
        if (!ctrl.signal.aborted) {
          setErrors((prev) => [
            ...prev,
            err instanceof Error ? err.message : String(err),
          ]);
        }
      } finally {
        abortRef.current = null;
        setStreamingMsg(null);
      }
    })();
  }, [activeId, project, consumeSse, refreshHypotheses, applyDone]);

  const runCouncilGenerate = useCallback(
    async (params: { claim: string; paper_ids: string[] }) => {
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      lastGenParamsRef.current = params;
      setGenState("running");
      setErrors([]);
      setRunFailureMsg(null);
      setCritiques([]);
      setStreamingMsg("Allocating hypothesis id…");
      setPersonasChangedDuringRun(false);
      setRunStartedAt(Date.now());

      try {
        // 1. Allocate id + create stub record server-side
        const createRes = await fetch("/api/hypothesis", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ project, claim: params.claim, paper_ids: params.paper_ids }),
          signal: ctrl.signal,
        });
        const createData = await createRes.json();
        if (!createRes.ok || !createData.hypothesis) {
          setErrors([createData.error ?? "Failed to allocate hypothesis"]);
          applyDone({ success: false, reason: "failed", message: createData.error }, setGenState);
          return;
        }
        const hyp = createData.hypothesis as HypothesisArtifact;
        setHypotheses((cur) => mergeHypothesis(cur, hyp));
        setActiveId(hyp.id);
        // URL sync
        const sp = new URLSearchParams(Array.from(searchParams.entries()));
        sp.set("project", project);
        sp.set("hyp", hyp.id);
        router.replace(`/hypothesis?${sp.toString()}`);

        // 2. Fire sci-council via /api/execute with the dashboard contract.
        setStreamingMsg("Running sci-council fanout…");
        // Phase 13a (H-4): only active personas fan out. Inactive ones
        // stay in personas.json (history + restoration) but do not fire
        // until the user toggles them back on.
        const activePersonas = personas.filter(isPersonaActive);
        const personasList = activePersonas.map((p) => p.name).join(", ");
        const prompt = [
          `Use the sci-council skill to fan out ${activePersonas.length} personas on this hypothesis.`,
          `active_project_slug=${project}`,
          `hypothesis_id=${hyp.id}`,
          `claim=${params.claim}`,
          `personas=[${personasList}]`,
          `linked_papers=[${params.paper_ids.join(", ")}]`,
          "For EACH persona emit one _artifact: persona-critique JSON line on stdout (schema: PHASE_2_TASKS.md §5.2).",
          "After all personas have spoken, emit ONE _artifact: hypothesis line linking the critique sidecars (status='open', critique_files populated by the dashboard's persister).",
          "Keep the existing markdown synthesis output for CLI users — the JSON lines are additive.",
        ].join("\n");

        const res = await fetch("/api/execute", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ project, skill: "sci-council", prompt }),
          signal: ctrl.signal,
        });
        const done = await consumeSse(res, ctrl, (msg) =>
          setErrors((prev) => [...prev, msg]),
        );
        await loadCritiques(hyp.id);
        await refreshHypotheses();
        setStreamingMsg(null);
        applyDone(done, setGenState);
      } catch (err) {
        if (ctrl.signal.aborted) {
          applyDone(null, setGenState, true);
        } else {
          setErrors([err instanceof Error ? err.message : String(err)]);
          applyDone(
            { success: false, reason: "failed", message: err instanceof Error ? err.message : String(err) },
            setGenState,
          );
        }
      } finally {
        abortRef.current = null;
        setStreamingMsg(null);
      }
    },
    [project, personas, router, searchParams, consumeSse, loadCritiques, refreshHypotheses, applyDone],
  );

  const runReconcile = useCallback(async () => {
    if (!activeHypothesis) return;
    if (critiques.length === 0) {
      setErrors(["Need ≥1 critique to reconcile"]);
      return;
    }
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setReconcileState("running");
    setErrors([]);
    setRunFailureMsg(null);
    setStreamingMsg("Reconciling critiques into a synthesis…");
    setRunStartedAt(Date.now());
    try {
      const res = await fetch("/api/hypothesis/reconcile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project, hyp_id: activeHypothesis.id }),
        signal: ctrl.signal,
      });
      // Phase 36 (v1.4): capture task_id from task-started so we can
      // re-attach after navigation. Persist to localStorage; clear on
      // done.
      const hypId = activeHypothesis.id;
      const done = await consumeSse(
        res,
        ctrl,
        (msg) => setErrors((prev) => [...prev, msg]),
        (task_id) => writeActiveTask(project, "reconcile", hypId, task_id),
      );
      clearActiveTask(project, "reconcile", hypId);
      await refreshHypotheses();
      applyDone(done, setReconcileState);
    } catch (err) {
      if (ctrl.signal.aborted) applyDone(null, setReconcileState, true);
      else {
        setErrors([err instanceof Error ? err.message : String(err)]);
        applyDone(
          { success: false, reason: "failed", message: err instanceof Error ? err.message : String(err) },
          setReconcileState,
        );
      }
    } finally {
      abortRef.current = null;
      setStreamingMsg(null);
    }
  }, [activeHypothesis, critiques.length, project, consumeSse, refreshHypotheses, applyDone]);

  // Phase 48 (v1.6) — F11: per-persona deep-research trigger. Drains
  // the registry-backed SSE; the route persists results onto the
  // hypothesis record so refreshHypotheses() picks them up.
  const [deepResearchRunning, setDeepResearchRunning] = useState(false);

  // Phase 50 (v2.0) — Reverse linkage. List of manuscripts whose
  // linked_hypothesis_ids[] includes the active hypothesis id.
  // Refreshed when the active hypothesis changes; stale-tolerant.
  const [linkedFromManuscripts, setLinkedFromManuscripts] = useState<
    { slug: string; title: string }[]
  >([]);
  useEffect(() => {
    if (!activeId) {
      setLinkedFromManuscripts([]);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const res = await fetch(
          `/api/hypothesis/${encodeURIComponent(activeId)}/manuscripts?project=${encodeURIComponent(project)}`,
        );
        const data = await res.json();
        if (cancelled) return;
        if (Array.isArray(data.manuscripts)) {
          setLinkedFromManuscripts(
            data.manuscripts.map((m: { slug: string; title?: string }) => ({
              slug: m.slug,
              title: m.title ?? m.slug,
            })),
          );
        }
      } catch {
        if (!cancelled) setLinkedFromManuscripts([]);
      }
    })();
    return () => { cancelled = true; };
  }, [activeId, project]);
  const runDeepResearch = useCallback(async () => {
    if (!activeHypothesis) return;
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setDeepResearchRunning(true);
    setErrors([]);
    setStreamingMsg("Running per-persona deep research…");
    try {
      const res = await fetch(
        `/api/hypothesis/${encodeURIComponent(activeHypothesis.id)}/deep-research?project=${encodeURIComponent(project)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ project }),
          signal: ctrl.signal,
        },
      );
      await consumeSse(res, ctrl, (msg) => setErrors((prev) => [...prev, msg]));
      await refreshHypotheses();
    } catch (err) {
      if (!ctrl.signal.aborted) {
        setErrors([err instanceof Error ? err.message : String(err)]);
      }
    } finally {
      abortRef.current = null;
      setDeepResearchRunning(false);
      setStreamingMsg(null);
    }
  }, [activeHypothesis, project, consumeSse, refreshHypotheses]);

  // Phase 13c (v1.0.1) — H-7 apply paper-set recommendation. The
  // synthesis-card emits the user-confirmed (drop, retain) intent; the
  // workspace owns the POST + optimistic state update so the linked-
  // papers list refreshes without a server round-trip.
  const applyRecommendation = useCallback(
    async (drop: string[], retain: string[]): Promise<void> => {
      if (!activeHypothesis) return;
      const prev = activeHypothesis;
      const dropSet = new Set(drop);
      const optimistic = prev.paper_ids.filter((id) => !dropSet.has(id));
      for (const id of retain) {
        if (!optimistic.includes(id)) optimistic.push(id);
      }
      setHypotheses((cur) =>
        cur.map((h) => (h.id === prev.id ? { ...h, paper_ids: optimistic } : h)),
      );
      try {
        const res = await fetch(
          `/api/hypothesis/${encodeURIComponent(prev.id)}/apply-recommendation?project=${encodeURIComponent(project)}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ project, drop, retain }),
          },
        );
        const data = await res.json();
        if (!res.ok) {
          setHypotheses((cur) =>
            cur.map((h) => (h.id === prev.id ? prev : h)),
          );
          throw new Error(data.error ?? "Apply failed");
        }
        setHypotheses((cur) =>
          cur.map((h) => (h.id === prev.id ? data.hypothesis : h)),
        );
      } catch (err) {
        setHypotheses((cur) => cur.map((h) => (h.id === prev.id ? prev : h)));
        throw err;
      }
    },
    [activeHypothesis, project],
  );

  // Phase 13b (v1.0.1) — H-5 + U4 single-persona retry.
  // Fires /retry-persona, drains the SSE through the existing consumeSse
  // (which already does replace-by-slug for persona-critique artifacts),
  // and clears the in-flight slug on done.
  const retryPersona = useCallback(
    async (personaSlug: string) => {
      if (!activeHypothesis) return;
      if (retryingSlug) return; // single retry in flight at a time
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      setRetryingSlug(personaSlug);
      try {
        const res = await fetch(
          `/api/hypothesis/${encodeURIComponent(activeHypothesis.id)}/retry-persona?project=${encodeURIComponent(project)}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ project, persona_slug: personaSlug }),
            signal: ctrl.signal,
          },
        );
        if (!res.ok) {
          let errMsg = `Retry failed (${res.status})`;
          try {
            const data = await res.json();
            if (data?.error) errMsg = data.error;
          } catch {
            /* keep generic */
          }
          setErrors((prev) => [...prev, errMsg]);
          return;
        }
        // Phase 36 (v1.4): persist task_id so a navigate-away keeps
        // the per-persona retry running.
        const retryScope = `${activeHypothesis.id}:${personaSlug}`;
        await consumeSse(
          res,
          ctrl,
          (msg) => setErrors((prev) => [...prev, msg]),
          (task_id) => writeActiveTask(project, "retry-persona", retryScope, task_id),
        );
        clearActiveTask(project, "retry-persona", retryScope);
        // Reload critiques from disk so the SSE-replaced state is
        // reconciled against the persisted artifact.
        await loadCritiques(activeHypothesis.id);
      } catch (err) {
        if (!ctrl.signal.aborted) {
          setErrors((prev) => [
            ...prev,
            err instanceof Error ? err.message : String(err),
          ]);
        }
      } finally {
        abortRef.current = null;
        setRetryingSlug(null);
      }
    },
    [activeHypothesis, retryingSlug, project, consumeSse, loadCritiques],
  );

  // Phase 43 (v1.5) — F6: optimistic toggle of excluded_persona_ids on
  // the active hypothesis. PATCH the new array; on success the server
  // echoes the merged record. Reversible: discard then restore is a
  // pure array round-trip.
  const toggleDiscardPersona = useCallback(
    async (personaSlug: string, next: boolean) => {
      if (!activeHypothesis) return;
      const prev = activeHypothesis;
      const cur = Array.isArray(prev.excluded_persona_ids)
        ? prev.excluded_persona_ids
        : [];
      const set = new Set(cur);
      if (next) set.add(personaSlug); else set.delete(personaSlug);
      const nextIds = Array.from(set);
      setHypotheses((cur) =>
        cur.map((h) =>
          h.id === prev.id ? { ...h, excluded_persona_ids: nextIds } : h,
        ),
      );
      try {
        const res = await fetch(
          `/api/hypothesis/${encodeURIComponent(prev.id)}`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              project,
              patch: { excluded_persona_ids: nextIds },
            }),
          },
        );
        const data = await res.json();
        if (!res.ok) throw new Error(data?.error ?? `HTTP ${res.status}`);
        if (data?.hypothesis) {
          setHypotheses((cur) =>
            cur.map((h) => (h.id === prev.id ? data.hypothesis : h)),
          );
        }
      } catch (err) {
        // Rollback on failure.
        setHypotheses((cur) =>
          cur.map((h) => (h.id === prev.id ? prev : h)),
        );
        setErrors((p) => [
          ...p,
          err instanceof Error ? err.message : String(err),
        ]);
      }
    },
    [activeHypothesis, project],
  );

  // Phase 58 (v2.1) — B1: hypothesis × delete from the History sidebar.
  // The DELETE route already exists at /api/hypothesis/[hyp_id]; this
  // wires the UI affordance. Optimistic — prune in-memory first, refresh
  // from disk if the route fails. If the deleted hypothesis is the active
  // one, clear activeId + URL hyp param so the user lands on the new
  // claim form.
  const handleDeleteHypothesis = useCallback(
    async (hyp_id: string) => {
      try {
        const res = await fetch(
          `/api/hypothesis/${encodeURIComponent(hyp_id)}?project=${encodeURIComponent(project)}`,
          { method: "DELETE" },
        );
        if (!res.ok) {
          let errMsg = `Delete failed (${res.status})`;
          try {
            const data = await res.json();
            if (data?.error) errMsg = data.error;
          } catch {
            /* keep generic */
          }
          setErrors((prev) => [...prev, errMsg]);
          return;
        }
        setHypotheses((prev) => prev.filter((h) => h.id !== hyp_id));
        if (activeId === hyp_id) {
          setActiveId(null);
          setCritiques([]);
          const sp = new URLSearchParams(Array.from(searchParams.entries()));
          sp.set("project", project);
          sp.delete("hyp");
          router.replace(`/hypothesis?${sp.toString()}`);
        }
      } catch (err) {
        setErrors((prev) => [
          ...prev,
          err instanceof Error ? err.message : String(err),
        ]);
      }
    },
    [project, activeId, router, searchParams],
  );

  const setStatus = useCallback(
    async (next: HypothesisStatus) => {
      if (!activeHypothesis) return;
      const prev = activeHypothesis;
      // Optimistic
      setHypotheses((cur) =>
        cur.map((h) => (h.id === prev.id ? { ...h, status: next } : h)),
      );
      try {
        const res = await fetch(
          `/api/hypothesis/${encodeURIComponent(prev.id)}`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ project, patch: { status: next } }),
          },
        );
        const data = await res.json();
        if (!res.ok) {
          setErrors([data.error ?? "Status change failed"]);
          setHypotheses((cur) =>
            cur.map((h) => (h.id === prev.id ? prev : h)),
          );
          return;
        }
        setHypotheses((cur) =>
          cur.map((h) => (h.id === prev.id ? data.hypothesis : h)),
        );
      } catch (err) {
        setErrors([err instanceof Error ? err.message : String(err)]);
        setHypotheses((cur) => cur.map((h) => (h.id === prev.id ? prev : h)));
      }
    },
    [activeHypothesis, project],
  );

  const savePersonas = useCallback(
    async (next: Persona[]) => {
      const res = await fetch("/api/personas", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project, personas: next }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "save failed");
      setPersonas(data.personas);
      if (genState === "running") setPersonasChangedDuringRun(true);
    },
    [project, genState],
  );

  // j/k history nav
  useHotkeys(
    "j",
    () => setFocusedIdx((i) => Math.min(i + 1, hypotheses.length - 1)),
    { enableOnFormTags: false },
    [hypotheses.length],
  );
  useHotkeys(
    "k",
    () => setFocusedIdx((i) => Math.max(i - 1, 0)),
    { enableOnFormTags: false },
    [],
  );
  useHotkeys(
    "enter",
    () => {
      const h = hypotheses[focusedIdx];
      if (h) handleSelect(h.id);
    },
    { enableOnFormTags: false },
    [focusedIdx, hypotheses, handleSelect],
  );

  const isRunning = genState === "running";
  const elapsedHint = streamingMsg ? streamingMsg : null;

  // Phase 11 — live hydration derived from in-memory state. Falls back to
  // the initial server-computed value before the SSE stream replaces it.
  // Phase 13a (H-4): expected = count of ACTIVE personas, not the full
  // configured set. An inactive persona never fires, so the badge would
  // forever show "2/3" if the third was deactivated. Inactive count
  // surfaces as a separate hint instead.
  const activePersonaCount = useMemo(
    () => personas.filter(isPersonaActive).length,
    [personas],
  );
  const hydrationStatus: HydrationStatus | null = useMemo(() => {
    if (activeHypothesis) {
      return {
        critiques: critiques.length,
        expected: activePersonaCount,
        synthesis: activeHypothesis.synthesis_text ? "present" : "absent",
      };
    }
    return initialHydrationStatus ?? null;
  }, [activeHypothesis, critiques.length, activePersonaCount, initialHydrationStatus]);

  // Phase 4: which run-state should the card show? Prefer gen state when
  // the user is in the new-claim flow, reconcile state otherwise.
  const cardState: RunStateUi =
    genState === "running" ? "running"
      : reconcileState === "running" ? "running"
        : genState === "failed" || reconcileState === "failed" ? "failed"
          : genState === "timeout" || reconcileState === "timeout" ? "timeout"
            : genState === "cancelled" || reconcileState === "cancelled" ? "cancelled"
              : genState === "succeeded" || reconcileState === "succeeded" ? "succeeded"
                : "idle";
  const cardLabel = reconcileState === "running"
    ? "reconcile"
    : genState !== "idle" ? "council fanout" : undefined;
  const cardElapsed =
    runStartedAt && (genState === "running" || reconcileState === "running")
      ? now - runStartedAt
      : undefined;
  const handleRetry = useCallback(() => {
    if (lastGenParamsRef.current && (genState === "failed" || genState === "timeout" || genState === "cancelled")) {
      void runCouncilGenerate(lastGenParamsRef.current);
    } else if (reconcileState === "failed" || reconcileState === "timeout" || reconcileState === "cancelled") {
      void runReconcile();
    }
  }, [genState, reconcileState, runCouncilGenerate, runReconcile]);
  const handleDismiss = useCallback(() => {
    setRunFailureMsg(null);
    if (genState !== "running") setGenState("idle");
    if (reconcileState !== "running") setReconcileState("idle");
  }, [genState, reconcileState]);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_22rem] gap-6 p-6 max-w-[1700px] mx-auto">
      {/* Main column */}
      <div className="space-y-6 min-w-0">
        {/* Personas chip strip */}
        <div className="flex items-center gap-3 flex-wrap">
          <span className="mono text-[10px] uppercase tracking-wider text-text-muted">
            Personas:
          </span>
          {personas.map((p) => {
            const active = isPersonaActive(p);
            return (
              <span
                key={p.name}
                data-persona-chip
                data-persona-active={active ? "true" : "false"}
                className={
                  // Phase 13a (H-4): inactive personas dim to half-opacity
                  // and pick up a strikethrough so the user sees at a
                  // glance which set the next council run will fire.
                  active
                    ? "mono text-[10px] uppercase tracking-wider px-2 py-0.5 border border-border-dim rounded text-text-dim"
                    : "mono text-[10px] uppercase tracking-wider px-2 py-0.5 border border-border-dim rounded text-text-muted opacity-50 line-through"
                }
                title={
                  active
                    ? p.role
                    : `${p.role ?? "(no role)"} — INACTIVE (skipped on next run)`
                }
              >
                {p.name}
              </span>
            );
          })}
          <button
            onClick={() => setEditingPersonas((e) => !e)}
            className="mono text-[10px] uppercase tracking-wider text-accent hover:underline"
          >
            ⚙ {editingPersonas ? "close" : "edit"}
          </button>
          {personasChangedDuringRun && (
            <span className="mono text-[10px] text-warn">
              · personas changed; current run still uses the previous set
            </span>
          )}
          {hydrationStatus && activeHypothesis && (
            <HydrationBadge status={hydrationStatus} />
          )}
        </div>

        {editingPersonas && (
          <PersonasEditor
            initial={personas}
            onSave={savePersonas}
            onClose={() => setEditingPersonas(false)}
          />
        )}

        {/* Active hypothesis OR new-claim form */}
        {!activeHypothesis ? (
          <>
            <h2 className="text-base font-semibold">New hypothesis</h2>
            <ClaimForm
              initialClaim={prefillClaim}
              initialPaperIds={prefillPaperIds}
              library={library}
              loading={isRunning}
              onSubmit={async (params) => {
                setPrefillClaim(params.claim);
                setPrefillPaperIds(params.paper_ids);
                // Phase 11 — clear the WIP scratchpad once the claim is
                // committed via generate. The new hypothesis takes over.
                writeWipClaim(project, "");
                await runCouncilGenerate(params);
              }}
              onCancel={cancelRun}
              onClaimChange={handleClaimChange}
              project={project}
            />
          </>
        ) : (
          <ActiveHypothesis
            hypothesis={activeHypothesis}
            critiques={critiques}
            personas={personas}
            isRunning={genState === "running"}
            isReconciling={reconcileState === "running"}
            library={library}
            project={project}
            linkedFromManuscripts={linkedFromManuscripts}
            onReconcile={runReconcile}
            onArchive={() => setStatus("archived")}
            onMarkSupported={() => setStatus("supported")}
            onMarkRefuted={() => setStatus("refuted")}
            onChangeStatus={setStatus}
            onOpenPaper={(p) => setDetailPaper(p)}
            onApplyRecommendation={applyRecommendation}
            onRetryPersona={retryPersona}
            retryingSlug={retryingSlug}
            onToggleDiscard={toggleDiscardPersona}
            onNew={handleNew}
            onRunDeepResearch={runDeepResearch}
            isDeepResearchRunning={deepResearchRunning}
          />
        )}

        {/* Phase 4 (fix-sprint): structured run-state card replaces the
            old silent-error text. Shows running/succeeded/failed/timeout/
            cancelled with inline Cancel/Retry. */}
        <RunStateCard
          state={cardState}
          label={cardLabel}
          message={runFailureMsg ?? elapsedHint ?? undefined}
          elapsedMs={cardElapsed}
          onCancel={cancelRun}
          onRetry={handleRetry}
          onDismiss={handleDismiss}
        />
        {errors.length > 0 && (
          <div className="space-y-1">
            {errors.map((e, i) => (
              <div key={i} className="mono text-[11px] text-danger">
                ! {e}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* History sidebar */}
      <aside className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">History</h3>
          <button
            onClick={handleNew}
            className="mono text-[10px] uppercase tracking-wider px-2 py-1 border border-accent rounded text-accent hover:bg-accent hover:text-bg transition"
          >
            + New
          </button>
        </div>
        <HypothesisHistory
          hypotheses={hypotheses}
          filterStatus={filterStatus}
          filterQuery={filterQuery}
          activeId={activeId}
          focusedIdx={focusedIdx}
          onFilterStatus={setFilterStatus}
          onFilterQuery={setFilterQuery}
          onSelect={handleSelect}
          onDelete={handleDeleteHypothesis}
        />
      </aside>

      <PaperDetailDrawer
        paper={detailPaper}
        isSaved={library.some((p) => p.id === detailPaper?.id)}
        onClose={() => setDetailPaper(null)}
        onSave={() => undefined}
        onUnsave={() => undefined}
      />
    </div>
  );
}

function mergeHypothesis(
  cur: HypothesisArtifact[],
  next: HypothesisArtifact,
): HypothesisArtifact[] {
  const idx = cur.findIndex((h) => h.id === next.id);
  if (idx === -1) return [next, ...cur];
  const copy = [...cur];
  copy[idx] = { ...copy[idx], ...next };
  return copy;
}

// Phase 11 (v1.0.1) — hydration completeness chip. Green when critiques are
// fully loaded AND synthesis exists; amber when partial; muted when none.
function HydrationBadge({ status }: { status: HydrationStatus }) {
  const complete = status.expected > 0 && status.critiques >= status.expected;
  const synthesisPresent = status.synthesis === "present";
  const tone = complete && synthesisPresent
    ? "border-accent text-accent"
    : complete
      ? "border-violet-400 text-violet-300"
      : "border-border-dim text-text-muted";
  return (
    <span
      data-hydration-status
      data-critiques={status.critiques}
      data-expected={status.expected}
      data-synthesis={status.synthesis}
      className={`mono text-[10px] uppercase tracking-wider px-2 py-0.5 border rounded ${tone}`}
      title="Loaded data completeness — critiques received vs personas configured, synthesis state"
    >
      {status.critiques}/{status.expected} critiques · synth {status.synthesis}
    </span>
  );
}

function ActiveHypothesis({
  hypothesis,
  critiques,
  personas,
  isRunning,
  isReconciling,
  library,
  project,
  linkedFromManuscripts,
  onReconcile,
  onArchive,
  onMarkSupported,
  onMarkRefuted,
  onChangeStatus,
  onOpenPaper,
  onApplyRecommendation,
  onRetryPersona,
  retryingSlug,
  onToggleDiscard,
  onNew,
  onRunDeepResearch,
  isDeepResearchRunning,
}: {
  hypothesis: HypothesisArtifact;
  critiques: PersonaCritiqueArtifact[];
  personas: Persona[];
  isRunning: boolean;
  isReconciling: boolean;
  library: PaperArtifact[];
  project: string;
  /** Phase 50 (v2.0) — Reverse linkage. Manuscripts whose
   * linked_hypothesis_ids[] includes this hypothesis. */
  linkedFromManuscripts: { slug: string; title: string }[];
  onReconcile: () => void;
  onArchive: () => void;
  onMarkSupported: () => void;
  onMarkRefuted: () => void;
  onChangeStatus: (s: HypothesisStatus) => void;
  onOpenPaper: (p: PaperArtifact) => void;
  onApplyRecommendation: (drop: string[], retain: string[]) => Promise<void>;
  onRetryPersona: (personaSlug: string) => void;
  retryingSlug: string | null;
  /** Phase 43 (v1.5) — F6: per-persona discard toggle. */
  onToggleDiscard: (personaSlug: string, next: boolean) => void;
  onNew: () => void;
  /** Phase 48 (v1.6) — F11: per-persona deep-research trigger. */
  onRunDeepResearch: () => void;
  isDeepResearchRunning: boolean;
}) {
  // Phase 43 (v1.5) — F6: derive included-of-total persona counts for
  // the reconcile button caption. Uses the slug-based discard set
  // matched against persona display names → slugifyPersona.
  const excluded = Array.isArray(hypothesis.excluded_persona_ids)
    ? hypothesis.excluded_persona_ids
    : [];
  const excludedSet = new Set(excluded);
  const includedCount = personas.filter(
    (p) => !excludedSet.has(slugifyPersona(p.name)),
  ).length;
  const totalPersonas = personas.length;
  const reconcileCaption = excludedSet.size > 0
    ? ` (${includedCount} of ${totalPersonas} personas)`
    : "";
  return (
    <div className="space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="text-base font-semibold leading-snug">
              {hypothesis.claim}
            </h2>
            <StatusBadge status={hypothesis.status} onChange={onChangeStatus} size="md" />
          </div>
          <div className="mono text-[10px] text-text-muted mt-1">
            {hypothesis.id} · {hypothesis.paper_ids.length} papers ·{" "}
            {hypothesis.critique_files?.length ?? 0} critiques · created{" "}
            {hypothesis.created_at.slice(0, 10)}
          </div>
          <div className="mt-2">
            <LinkedPapersList
              paperIds={hypothesis.paper_ids}
              library={library}
              onOpenPaper={onOpenPaper}
            />
          </div>
        </div>
        <button
          onClick={onNew}
          className="mono text-[10px] uppercase tracking-wider text-text-dim hover:text-text px-2 py-1"
        >
          ↩ New
        </button>
      </header>

      {linkedFromManuscripts.length > 0 && (
        <section
          data-linked-from-manuscripts
          className="border border-border-dim rounded bg-bg-elev px-4 py-3"
        >
          <div className="mono text-[10px] uppercase tracking-[0.2em] text-text-muted mb-2">
            Linked from {linkedFromManuscripts.length} manuscript{linkedFromManuscripts.length === 1 ? "" : "s"}
          </div>
          <ul className="space-y-1">
            {linkedFromManuscripts.map((m) => (
              <li key={m.slug} className="text-xs">
                <a
                  href={`/draft?slug=${encodeURIComponent(m.slug)}&project=${encodeURIComponent(project)}`}
                  className="text-accent hover:underline"
                >
                  {m.title}
                </a>
              </li>
            ))}
          </ul>
        </section>
      )}

      <CouncilFanout
        personas={personas}
        critiques={critiques}
        hypothesisId={hypothesis.id}
        isRunning={isRunning}
        onRetryPersona={onRetryPersona}
        retryingSlug={retryingSlug}
        excludedPersonaIds={excluded}
        onToggleDiscard={onToggleDiscard}
        additionalPapersByPersona={hypothesis.additional_papers_by_persona ?? null}
        onOpenPaper={onOpenPaper}
      />

      {/* Phase 48 (v1.6) — F11: per-persona deep-research action.
          POSTs to /api/hypothesis/{id}/deep-research; the route registers
          a task in the registry (Phase 44 substrate) so the run survives
          navigation. Result lands on additional_papers_by_persona on the
          hypothesis record; CouncilFanout renders the deep-research
          section per persona card. */}
      {hypothesis.status !== "archived" && (
        <button
          type="button"
          onClick={onRunDeepResearch}
          disabled={isDeepResearchRunning}
          data-action="deep-research"
          className="mono text-[10px] uppercase tracking-wider px-3 py-1.5 border border-accent rounded text-accent hover:bg-accent hover:text-bg transition disabled:opacity-50 disabled:cursor-not-allowed"
          title="Each persona runs a literature search biased to its viewpoint (skeptic → refute, methodologist → measurement, domain-expert → consensus)"
        >
          {isDeepResearchRunning
            ? "Running deep research…"
            : hypothesis.additional_papers_by_persona
              ? "Re-run deep research"
              : "Run per-persona deep research"}
        </button>
      )}

      <div className="flex items-center gap-3 flex-wrap">
        <button
          onClick={onReconcile}
          disabled={isReconciling || critiques.length === 0 || hypothesis.status === "archived" || includedCount === 0}
          className="px-4 py-2 border border-violet-400 rounded mono text-xs uppercase tracking-wider text-violet-300 hover:bg-violet-400 hover:text-bg transition disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {isReconciling
            ? `Reconciling${reconcileCaption}…`
            : hypothesis.status === "open"
              ? `Reconcile → synthesis${reconcileCaption}`
              : `Re-run reconcile${reconcileCaption}`}
        </button>
        {hypothesis.status === "open" && (
          <span className="mono text-[10px] text-text-muted">
            requires ≥1 critique
          </span>
        )}
        {excludedSet.size > 0 && (
          <span className="mono text-[10px] text-text-muted">
            {excludedSet.size} discarded · click Restore on a card to re-include
          </span>
        )}
      </div>

      <SynthesisCard
        hypothesis={hypothesis}
        onMarkSupported={onMarkSupported}
        onMarkRefuted={onMarkRefuted}
        onArchive={onArchive}
        onApplyRecommendation={onApplyRecommendation}
      />
    </div>
  );
}
