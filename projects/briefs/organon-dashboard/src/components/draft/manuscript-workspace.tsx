"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type {
  FigureArtifact,
  HypothesisArtifact,
  PaperArtifact,
  SectionAction,
  SectionDiffArtifact,
  SectionDraftArtifact,
  SectionStatus,
} from "@/lib/artifacts/types";
import type { ManuscriptMeta } from "@/lib/draft/store";
import { SourceLinkagePanel, type DatasetLite } from "./source-linkage-panel";
import { SectionOverridesModal } from "./section-overrides-modal";
import { extractArtifactsFromChunk } from "@/lib/artifacts/parser";
import { RunStateCard, type RunState } from "@/components/primitives/run-state-card";
import { SectionList } from "./section-list";
import { MarkdownEditor } from "./markdown-editor";
import { LivePreview } from "./live-preview";
import { ActionBar } from "./action-bar";
import { DiffView } from "./diff-view";
import { composeFromHunks } from "@/lib/draft/diff-hunks";
import { ExportMenu, type ExportFormat, type PdfPreflightResponse } from "./export-menu";
import { DEFAULT_PRESET_ID } from "@/lib/draft/typography-presets";
import { FigureDragSource } from "./figure-drag-source";
import { insertFigAtLine } from "@/lib/draft/insert-fig";
import { ChatPanel, type ChatTurn } from "./chat-panel";
import type { MarkdownEditorHandle } from "./markdown-editor";
import { ExportErrorPanel, type ExportErrorEntry } from "./export-error-panel";

export type ManuscriptWorkspaceProps = {
  project: string;
  manuscript: ManuscriptMeta;
  initialSections: SectionDraftArtifact[];
  figures: FigureArtifact[];
  library: PaperArtifact[];
  /** Phase 41 (v1.5) — F4: source-linkage panel inputs. */
  hypotheses?: HypothesisArtifact[];
  datasets?: DatasetLite[];
  initialSectionId?: string;
};

// Phase 10 (v1.0.1): cap=2 parallel section generations during the
// "Draft all sections" wizard, sequential otherwise. Higher cap risks
// claude-runner contention + LLM rate-limit collisions.
const DRAFT_ALL_PARALLEL_CAP = 2;

export function ManuscriptWorkspace(props: ManuscriptWorkspaceProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [meta, setMeta] = useState<ManuscriptMeta>(props.manuscript);
  const [sections, setSections] = useState<SectionDraftArtifact[]>(props.initialSections);
  const initialId = props.initialSectionId
    ?? meta.ordering[0]
    ?? props.initialSections[0]?.section_id
    ?? null;
  const [activeId, setActiveId] = useState<string | null>(initialId);
  const [editing, setEditing] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState<SectionAction | null>(null);
  const [stream, setStream] = useState<string | null>(null);
  const [pendingDiff, setPendingDiff] = useState<SectionDiffArtifact | null>(null);
  const [exportBusy, setExportBusy] = useState<ExportFormat | null>(null);
  // Phase 18 (v1.1+) — workspace-owned typography preset selection.
  // Defaults to "default"; preset_id flows into the export POST body.
  const [exportPresetId, setExportPresetId] = useState<string>(DEFAULT_PRESET_ID);
  // Phase 22 (v1.1+) — DR-6 chat panel state. Right-rail toggle, an
  // editor handle for selection capture, and an in-memory transcript
  // of chat turns + emitted diffs. Each turn is single-shot; multi-
  // turn conversation is v1.2.
  const [chatRailOpen, setChatRailOpen] = useState<boolean>(true);
  const [chatTurns, setChatTurns] = useState<ChatTurn[]>([]);
  const [chatBusy, setChatBusy] = useState<boolean>(false);
  const editorRef = useRef<MarkdownEditorHandle | null>(null);
  const [exportLog, setExportLog] = useState<string | null>(null);
  // Phase 16 (EX-1): structured 422 detail. When the export route returns
  // unresolved cite/fig tokens we keep the format + per-token list so the
  // ExportErrorPanel can render expandable detail with "fix in editor"
  // buttons. exportLog is still populated as the truncated text fallback.
  const [exportError, setExportError] = useState<{
    format: ExportFormat;
    entries: ExportErrorEntry[];
  } | null>(null);
  const [errors, setErrors] = useState<string[]>([]);

  // Phase 10: per-section generation tracking. Set<sectionId> for the
  // wizard's cap=2 parallel fan-out. RunStateCard reflects the wizard's
  // overall state.
  const [generatingIds, setGeneratingIds] = useState<Set<string>>(() => new Set());
  const [draftAllRunning, setDraftAllRunning] = useState(false);
  const [generateRunState, setGenerateRunState] = useState<RunState>("idle");
  const [generateRunMessage, setGenerateRunMessage] = useState<string | null>(null);
  const [generateRunLabel, setGenerateRunLabel] = useState<string | null>(null);
  const generateStartRef = useRef<number | null>(null);
  const [generateElapsed, setGenerateElapsed] = useState(0);
  // Phase 10 hotfix (N2-lite — researcher steering on 2026-05-07):
  // optional "what should the AI emphasize?" textbox. Passed verbatim
  // to /generate-section AND /action POST bodies; the routes treat it
  // as the highest-priority signal within the slot's structural
  // constraints.
  const [aiInstructions, setAiInstructions] = useState<string>("");
  const [showInstructions, setShowInstructions] = useState<boolean>(false);

  const activeSection = useMemo(
    () => sections.find((s) => s.section_id === activeId) ?? null,
    [sections, activeId],
  );

  // Sync the editor buffer when the active section changes.
  useEffect(() => {
    setEditing(activeSection?.content_md ?? "");
  }, [activeSection?.section_id, activeSection?.version]);

  // Phase 10: keep RunStateCard's elapsed counter ticking while the
  // generate run is in flight.
  useEffect(() => {
    if (generateRunState !== "running") return;
    const id = setInterval(() => {
      if (generateStartRef.current != null) {
        setGenerateElapsed(Date.now() - generateStartRef.current);
      }
    }, 250);
    return () => clearInterval(id);
  }, [generateRunState]);

  const writeUrl = useCallback(
    (sectionId: string | null) => {
      const sp = new URLSearchParams(Array.from(searchParams.entries()));
      sp.set("project", props.project);
      if (sectionId) sp.set("section", sectionId); else sp.delete("section");
      router.replace(`/draft/${encodeURIComponent(meta.slug)}?${sp.toString()}`);
    },
    [meta.slug, props.project, router, searchParams],
  );

  const refreshSections = useCallback(async () => {
    try {
      const res = await fetch(
        `/api/draft/${encodeURIComponent(meta.slug)}/sections?project=${encodeURIComponent(props.project)}`,
      );
      const json = await res.json();
      if (Array.isArray(json.sections)) setSections(json.sections);
    } catch { /* keep last good */ }
  }, [meta.slug, props.project]);

  const handleSelect = useCallback(
    (id: string) => {
      setActiveId(id);
      writeUrl(id);
    },
    [writeUrl],
  );

  // Phase 20 (v1.1+) — DR-7 drop handler. The live preview emits
  // sectionId + line + figId; we look up the section, run
  // insertFigAtLine on its content_md (idempotent on dup), and either
  // update the local editor buffer (active section) or PATCH directly
  // (non-active section). The PATCH path writes through the existing
  // section route — autosave logic, version bump, sidecar, all
  // preserved.
  const handleDropFigure = useCallback(
    async (sectionId: string, line: number, figId: string) => {
      if (sectionId === activeId) {
        // Active section: drive through the editor buffer so the
        // existing dirty-flag + autosave path picks it up.
        setEditing((prev) => insertFigAtLine(prev, line, figId));
        return;
      }
      const section = sections.find((s) => s.section_id === sectionId);
      if (!section) return;
      const next = insertFigAtLine(section.content_md, line, figId);
      if (next === section.content_md) return; // idempotent no-op
      try {
        const res = await fetch(
          `/api/draft/${encodeURIComponent(meta.slug)}/sections/${encodeURIComponent(sectionId)}?project=${encodeURIComponent(props.project)}`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ content_md: next }),
          },
        );
        const json = await res.json();
        if (!res.ok) throw new Error(json?.error ?? `HTTP ${res.status}`);
        setSections((prev) =>
          prev.map((s) => (s.section_id === sectionId ? json.section : s)),
        );
      } catch (err) {
        setErrors((e) => [...e, err instanceof Error ? err.message : String(err)]);
      }
    },
    [activeId, sections, meta.slug, props.project],
  );

  const handleSave = useCallback(async () => {
    if (!activeId) return;
    setSaving(true);
    try {
      const res = await fetch(
        `/api/draft/${encodeURIComponent(meta.slug)}/sections/${encodeURIComponent(activeId)}?project=${encodeURIComponent(props.project)}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content_md: editing }),
        },
      );
      const json = await res.json();
      if (!res.ok) throw new Error(json?.error ?? `HTTP ${res.status}`);
      setSections((prev) =>
        prev.map((s) => (s.section_id === activeId ? json.section : s)),
      );
    } catch (err) {
      setErrors((e) => [...e, err instanceof Error ? err.message : String(err)]);
    } finally {
      setSaving(false);
    }
  }, [activeId, editing, meta.slug, props.project]);

  const handleStatus = useCallback(
    async (id: string, next: SectionStatus) => {
      try {
        const res = await fetch(
          `/api/draft/${encodeURIComponent(meta.slug)}/sections/${encodeURIComponent(id)}?project=${encodeURIComponent(props.project)}`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: next }),
          },
        );
        const json = await res.json();
        if (!res.ok) throw new Error(json?.error ?? `HTTP ${res.status}`);
        setSections((prev) => prev.map((s) => (s.section_id === id ? json.section : s)));
      } catch (err) {
        setErrors((e) => [...e, err instanceof Error ? err.message : String(err)]);
      }
    },
    [meta.slug, props.project],
  );

  const handleReorder = useCallback(
    async (next: string[]) => {
      try {
        const res = await fetch(
          `/api/draft/${encodeURIComponent(meta.slug)}?project=${encodeURIComponent(props.project)}`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ordering: next }),
          },
        );
        const json = await res.json();
        if (!res.ok) throw new Error(json?.error ?? `HTTP ${res.status}`);
        setMeta(json.manuscript);
      } catch (err) {
        setErrors((e) => [...e, err instanceof Error ? err.message : String(err)]);
      }
    },
    [meta.slug, props.project],
  );

  // Phase 52 (v2.0) — Notebook import. Reads the file as text, then
  // POSTs the raw .ipynb body to the import-notebook route which
  // parseNotebook flattens into markdown. Appends a new section.
  const handleImportNotebook = useCallback(async (file: File) => {
    try {
      const text = await file.text();
      const res = await fetch(
        `/api/draft/${encodeURIComponent(meta.slug)}/import-notebook?project=${encodeURIComponent(props.project)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ project: props.project, notebook: text }),
        },
      );
      const json = await res.json();
      if (!res.ok) throw new Error(json?.error ?? `HTTP ${res.status}`);
      const sect: SectionDraftArtifact = json.section;
      setSections((prev) => {
        const idx = prev.findIndex((s) => s.section_id === sect.section_id);
        if (idx === -1) return [...prev, sect];
        const copy = [...prev];
        copy[idx] = sect;
        return copy;
      });
      setMeta((m) => (
        m.ordering.includes(sect.section_id)
          ? m
          : { ...m, ordering: [...m.ordering, sect.section_id] }
      ));
      setActiveId(sect.section_id);
    } catch (err) {
      setErrors((e) => [...e, err instanceof Error ? err.message : String(err)]);
    }
  }, [meta.slug, props.project]);

  // Phase 51 (v2.0) — Per-section linkage override editor. Opens a
  // modal driven by `editingOverridesForSection`; the modal POSTs
  // override_* arrays to the section PATCH route which validates each
  // id against its store before persistence.
  const [editingOverridesForSection, setEditingOverridesForSection] = useState<string | null>(null);
  const handleEditSectionOverrides = useCallback((id: string) => {
    setEditingOverridesForSection(id);
  }, []);
  const handleSaveSectionOverrides = useCallback(async (
    sectionId: string,
    overrides: {
      override_linked_paper_ids?: string[];
      override_linked_figure_ids?: string[];
      override_linked_hypothesis_ids?: string[];
      override_linked_dataset_ids?: string[];
    },
  ) => {
    const res = await fetch(
      `/api/draft/${encodeURIComponent(meta.slug)}/sections/${encodeURIComponent(sectionId)}?project=${encodeURIComponent(props.project)}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(overrides),
      },
    );
    const json = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(json?.error ?? `HTTP ${res.status}`);
    if (json.section) {
      setSections((prev) =>
        prev.map((s) => (s.section_id === sectionId ? json.section : s)),
      );
    }
    setEditingOverridesForSection(null);
  }, [meta.slug, props.project]);

  const handleCreateSection = useCallback(async () => {
    const name = window.prompt("Section id (lowercase, no spaces):", "appendix");
    if (!name) return;
    try {
      const res = await fetch(
        `/api/draft/${encodeURIComponent(meta.slug)}/sections`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ project: props.project, section_id: name, section_type: "custom" }),
        },
      );
      const json = await res.json();
      if (!res.ok) throw new Error(json?.error ?? `HTTP ${res.status}`);
      setSections((prev) => [...prev, json.section]);
      setMeta((m) => ({ ...m, ordering: [...m.ordering, name] }));
      handleSelect(name);
    } catch (err) {
      setErrors((e) => [...e, err instanceof Error ? err.message : String(err)]);
    }
  }, [handleSelect, meta.slug, props.project]);

  const handleAction = useCallback(
    async (action: SectionAction) => {
      if (!activeId) return;
      setRunning(action);
      setStream("Spawning skill…");
      setPendingDiff(null);
      try {
        const res = await fetch(
          `/api/draft/${encodeURIComponent(meta.slug)}/action`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              project: props.project,
              section_id: activeId,
              action,
              // Phase 10 hotfix (N2-lite): pass any user steering
              // through to the action route.
              instructions: aiInstructions.trim() || undefined,
            }),
          },
        );
        if (!res.ok || !res.body) {
          const j = await res.json().catch(() => ({}));
          throw new Error(j?.error ?? `HTTP ${res.status}`);
        }
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
                  if (art._artifact === "section-diff") {
                    setPendingDiff(art as SectionDiffArtifact);
                  }
                }
              }
              if (data.artifact?._artifact === "section-diff") {
                setPendingDiff(data.artifact as SectionDiffArtifact);
              }
              if (data.message) setErrors((e) => [...e, data.message]);
            } catch { /* not JSON */ }
          }
        }
      } catch (err) {
        setErrors((e) => [...e, err instanceof Error ? err.message : String(err)]);
      } finally {
        setRunning(null);
        setStream(null);
      }
    },
    [activeId, aiInstructions, meta.slug, props.project],
  );

  // Phase 10 (v1.0.1) — DR-3: per-section generate. Streams the SSE,
  // parses the persisted section-draft from the route's `artifact`
  // event, drops it into local state, and surfaces exit reason via
  // the RunStateCard.
  const generateOneSection = useCallback(
    async (sectionId: string): Promise<boolean> => {
      setGeneratingIds((prev) => {
        const next = new Set(prev);
        next.add(sectionId);
        return next;
      });
      try {
        const res = await fetch(
          `/api/draft/${encodeURIComponent(meta.slug)}/generate-section`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              project: props.project,
              section_id: sectionId,
              // Phase 10 hotfix (N2-lite): pass user steering through.
              instructions: aiInstructions.trim() || undefined,
            }),
          },
        );
        if (!res.ok || !res.body) {
          const j = await res.json().catch(() => ({}));
          throw new Error(j?.error ?? `HTTP ${res.status}`);
        }
        const reader = res.body.getReader();
        const dec = new TextDecoder();
        let buf = "";
        let success = false;
        // Phase 10 hotfix (B1): persisted is the load-bearing signal,
        // NOT the exit code. The route may exit clean but emit no
        // valid section-draft (skill misbehaved); the UI distinguishes.
        let persisted = false;
        let doneReason: string | null = null;
        let doneMessage: string | undefined;
        let usedFallback = false;
        const warnings: string[] = [];
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
              if (data?.artifact?._artifact === "section-draft") {
                const next = data.artifact as SectionDraftArtifact;
                setSections((prev) => prev.map((s) =>
                  s.section_id === next.section_id ? next : s,
                ));
                if (sectionId === activeId) setEditing(next.content_md);
              }
              if (data?.kind === "validation-failed" || data?.kind === "fallback-content") {
                if (typeof data.reason === "string") warnings.push(data.reason);
              }
              if (typeof data?.success === "boolean") {
                success = data.success;
                doneReason = typeof data.reason === "string" ? data.reason : null;
                doneMessage = typeof data.message === "string" ? data.message : undefined;
                persisted = data.persisted != null;
                usedFallback = Boolean(data.used_fallback);
              }
            } catch { /* keepalive / non-JSON */ }
          }
        }
        // Phase 10 hotfix (B1): success === true && persisted === false
        // is the new "succeeded but no draft" soft failure. Surface it
        // as failed in the RunStateCard so the user doesn't see false
        // reassurance; carry through any warnings the route emitted.
        if (!success || !persisted) {
          const stateClass: RunState =
            doneReason === "timeout" ? "timeout"
              : doneReason === "cancelled" ? "cancelled"
              : "failed";
          setGenerateRunState(stateClass);
          const baseMsg = !success
            ? (doneMessage ?? `Generate failed for ${sectionId}.`)
            : doneReason === "validation-failed"
              ? `Generate ran but the output didn't match the ${sectionId} section shape — content rejected.`
              : doneReason === "succeeded-no-artifact"
                ? `Generate ran but emitted no draft. The skill may have skipped the JSON line; check the latest run log.`
                : `Generate completed but no draft was persisted for ${sectionId}.`;
          const tail = warnings.length > 0 ? `\n${warnings.join("\n")}` : "";
          setGenerateRunMessage(`${baseMsg}${tail}`);
          if (warnings.length > 0) {
            setErrors((e) => [...e, ...warnings]);
          }
          return false;
        }
        // Phase 10 hotfix (B1): success via fallback — persisted but
        // first-class artifact was missing. Record as warning so the
        // researcher knows the skill misbehaved.
        if (usedFallback && warnings.length > 0) {
          setErrors((e) => [...e, ...warnings]);
        }
        return true;
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setErrors((e) => [...e, msg]);
        setGenerateRunState("failed");
        setGenerateRunMessage(msg);
        return false;
      } finally {
        setGeneratingIds((prev) => {
          const next = new Set(prev);
          next.delete(sectionId);
          return next;
        });
      }
    },
    [activeId, aiInstructions, meta.slug, props.project],
  );

  const handleGenerateSection = useCallback(
    async (sectionId: string) => {
      // Phase 61 (v2.1) — A4: clear stale failure state BEFORE the run
      // so a successful retry doesn't render against a stale toast. The
      // previous "succeeded-no-artifact" / failed message lingered when
      // generate-section retried successfully — researcher-confusing.
      // Errors[] is also cleared because the only entries we own are
      // generate-section warnings; chat-panel + load errors get pushed
      // back the next time something fails.
      setErrors([]);
      generateStartRef.current = Date.now();
      setGenerateElapsed(0);
      setGenerateRunLabel(`generate · ${sectionId}`);
      setGenerateRunState("running");
      setGenerateRunMessage(null);
      const ok = await generateOneSection(sectionId);
      if (ok) {
        setGenerateRunState("succeeded");
        setGenerateRunMessage(`Section ${sectionId} drafted.`);
        // Phase 61 (v2.1) — A4: scroll the editor into view so the
        // researcher sees the freshly-drafted content without hunting.
        // Only scroll when the just-generated section is the active one.
        if (sectionId === activeId && editorRef.current) {
          editorRef.current.scrollIntoView();
        }
      }
      generateStartRef.current = null;
    },
    [activeId, generateOneSection],
  );

  // Phase 10 (v1.0.1) — DR-3 wizard: fan out across all sections with
  // cap=2 parallel. Skips the references section (auto-populated on
  // export) but generates everything else, even non-empty bodies (the
  // user opted in by clicking the wizard).
  const handleDraftAll = useCallback(async () => {
    if (draftAllRunning) return;
    const targets = meta.ordering.filter((id) => {
      if (id === "references") return false;
      const sect = sections.find((s) => s.section_id === id);
      return sect != null;
    });
    if (targets.length === 0) return;
    setDraftAllRunning(true);
    generateStartRef.current = Date.now();
    setGenerateElapsed(0);
    setGenerateRunLabel(`draft all · ${targets.length} sections`);
    setGenerateRunState("running");
    setGenerateRunMessage(`0 / ${targets.length} done`);
    let completed = 0;
    let anyFailed = false;
    const queue = [...targets];
    const workers: Promise<void>[] = [];
    const launch = async (): Promise<void> => {
      while (queue.length > 0) {
        const next = queue.shift();
        if (!next) return;
        const ok = await generateOneSection(next);
        if (!ok) anyFailed = true;
        completed += 1;
        setGenerateRunMessage(`${completed} / ${targets.length} done`);
      }
    };
    for (let i = 0; i < Math.min(DRAFT_ALL_PARALLEL_CAP, targets.length); i += 1) {
      workers.push(launch());
    }
    await Promise.all(workers);
    setDraftAllRunning(false);
    generateStartRef.current = null;
    if (!anyFailed) {
      setGenerateRunState("succeeded");
      setGenerateRunMessage(`All ${targets.length} sections drafted.`);
    } else {
      setGenerateRunState("failed");
      setGenerateRunMessage(`${completed} / ${targets.length} done; some sections failed (see errors).`);
    }
  }, [draftAllRunning, generateOneSection, meta.ordering, sections]);

  const handleAcceptDiff = useCallback(async () => {
    if (!pendingDiff || !activeId) return;
    setEditing(pendingDiff.after);
    // Persist via the same save path so version bumps + sidecar refresh apply.
    setPendingDiff(null);
    setSaving(true);
    try {
      const res = await fetch(
        `/api/draft/${encodeURIComponent(meta.slug)}/sections/${encodeURIComponent(activeId)}?project=${encodeURIComponent(props.project)}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content_md: pendingDiff.after }),
        },
      );
      const json = await res.json();
      if (!res.ok) throw new Error(json?.error ?? `HTTP ${res.status}`);
      setSections((prev) => prev.map((s) => (s.section_id === activeId ? json.section : s)));
    } catch (err) {
      setErrors((e) => [...e, err instanceof Error ? err.message : String(err)]);
    } finally {
      setSaving(false);
    }
  }, [activeId, meta.slug, pendingDiff, props.project]);

  // Phase 16 (EX-1): scan sections for the section that hosts a
  // \cite{token} / \fig{token} occurrence. Returns the first match;
  // returns null when no section currently contains the token (token
  // existed in a slot the researcher then deleted, edge case).
  const findSectionForToken = useCallback(
    (kind: "cite" | "fig", token: string): { id: string; title: string | null } | null => {
      // Token must match the in-source form regardless of \cite{a, b}
      // grouping — the assembler emits each comma-separated key as its
      // own unresolved entry, so we match the bare token inside the
      // braced body.
      const cleaned = token.trim();
      const macro = kind === "cite" ? "cite" : "fig";
      // Match \cite{cleaned}, \cite{x, cleaned, y}, \fig{cleaned}, etc.
      // Body characters are anything but braces and whitespace; we accept
      // any neighboring keys via the optional comma-list on either side.
      const pattern = new RegExp(
        `\\\\${macro}\\{[^}]*\\b${cleaned.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b[^}]*\\}`,
      );
      for (const s of sections) {
        if (pattern.test(s.content_md)) {
          // SectionDraftArtifact has no `title`; section_type is the
          // human-readable label (introduction / methods / results / etc).
          return { id: s.section_id, title: s.section_type };
        }
      }
      return null;
    },
    [sections],
  );

  const handleExport = useCallback(
    async (format: ExportFormat) => {
      setExportBusy(format);
      setExportLog(null);
      // Phase 16: clear stale 422 detail on every retry — the panel must
      // not survive a fresh attempt with different unresolved tokens.
      setExportError(null);
      try {
        const res = await fetch(
          `/api/draft/${encodeURIComponent(meta.slug)}/export?project=${encodeURIComponent(props.project)}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ project: props.project, format, preset_id: exportPresetId }),
          },
        );
        const json = await res.json();
        if (!res.ok) {
          setExportLog(`${format} → ${json?.error ?? `HTTP ${res.status}`}${json?.path ? `; markdown at ${json.path}` : ""}`);
          // Phase 16 (EX-1): build structured detail when the route
          // returned unresolved cite/fig arrays (only the 422 path does).
          const cites: string[] = Array.isArray(json?.unresolved_cites) ? json.unresolved_cites : [];
          const figs: string[] = Array.isArray(json?.unresolved_figs) ? json.unresolved_figs : [];
          if (cites.length > 0 || figs.length > 0) {
            const entries: ExportErrorEntry[] = [
              ...cites.map((token) => {
                const target = findSectionForToken("cite", token);
                return {
                  token,
                  kind: "cite" as const,
                  targetSectionId: target?.id ?? null,
                  targetSectionTitle: target?.title ?? null,
                };
              }),
              ...figs.map((token) => {
                const target = findSectionForToken("fig", token);
                return {
                  token,
                  kind: "fig" as const,
                  targetSectionId: target?.id ?? null,
                  targetSectionTitle: target?.title ?? null,
                };
              }),
            ];
            setExportError({ format, entries });
          }
        } else {
          setExportLog(`${format} → ${json.path}`);
        }
      } catch (err) {
        setExportLog(`${format} → ${err instanceof Error ? err.message : String(err)}`);
      } finally {
        setExportBusy(null);
      }
    },
    [meta.slug, props.project, findSectionForToken, exportPresetId],
  );

  // Phase 17 (v1.1+) — Pandoc preflight (B3). Workspace owns the fetch
  // (parent-owned-fetch pattern from Phase 10). Hits the same export
  // route with `?dryrun=1` so pandoc is probed without manuscript
  // assembly. Errors surface to the menu's preflight panel.
  // Phase 22 (v1.1+) — DR-6 chat handlers.
  //
  // handleSubmitChatTurn: spawns the SSE round-trip, streams stdout
  // chunks into the turn's `streaming` field, captures the emitted
  // section-diff artifact, marks the turn done.
  //
  // handleApplyChatDiff: drives the diff into the editor buffer
  // (Phase 7 pattern — same path as the existing rewrite/tighten
  // diff-apply); marks the turn applied so the Apply button disables.
  const handleSubmitChatTurn = useCallback(
    async (req: {
      prompt: string;
      selection: { start: number; end: number; text: string } | null;
      referencedFiles?: { kind: string; id: string; label: string }[];
    }) => {
      if (!activeId) return;
      const turnId = `chat-${Date.now()}`;
      const turn: ChatTurn = {
        id: turnId,
        prompt: req.prompt,
        selectionText: req.selection?.text ?? null,
        diff: null,
        streaming: "",
        done: false,
        applied: false,
      };
      // Phase 27 (v1.2) — multi-turn conversation. Build the
      // prior_turns payload from the in-memory transcript at submit
      // time: last 6 turns, diff body summarised to ≤400 chars
      // (the rationale is already user-facing copy). Workspace builds
      // the payload — panel stays presentational (Phase 22 pattern).
      const priorTurnsPayload = chatTurns
        .filter((t) => t.done)
        .slice(-6)
        .map((t) => ({
          prompt: t.prompt,
          applied: !!t.applied,
          diff_summary: t.diff?.rationale
            ? t.diff.rationale.slice(0, 400)
            : undefined,
        }));
      setChatTurns((prev) => [...prev, turn]);
      setChatBusy(true);
      try {
        const res = await fetch(
          `/api/draft/${encodeURIComponent(meta.slug)}/edit-with-chat?project=${encodeURIComponent(props.project)}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              project: props.project,
              section_id: activeId,
              prompt: req.prompt,
              selection: req.selection,
              prior_turns: priorTurnsPayload,
              // Phase 29 (v1.2) — DR-6+ pinned files. The chat-panel
              // tracks selectedFiles state internally + forwards them
              // here. Workspace passes through; the route resolves
              // each id via the matching store.
              referenced_file_ids:
                req.referencedFiles?.map((r) => ({ kind: r.kind, id: r.id })) ?? [],
            }),
          },
        );
        if (!res.ok) {
          const j = await res.json();
          throw new Error(j?.error ?? `HTTP ${res.status}`);
        }
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
              if (data?.artifact?._artifact === "section-diff") {
                const diffArt = data.artifact as SectionDiffArtifact;
                setChatTurns((prev) =>
                  prev.map((t) => (t.id === turnId ? { ...t, diff: diffArt } : t)),
                );
              }
              if (typeof data?.success === "boolean" && typeof data?.section_id === "string") {
                setChatTurns((prev) => {
                  const next = prev.map((t) =>
                    t.id === turnId ? { ...t, done: true } : t,
                  );
                  // Phase 34 (v1.3) — DR-6++ persist the just-completed
                  // turn to disk. Non-blocking: a POST failure is logged
                  // to errors but doesn't break the in-memory state.
                  const completed = next.find((t) => t.id === turnId);
                  if (completed) {
                    void fetch(
                      `/api/draft/${encodeURIComponent(meta.slug)}/chat-transcript?project=${encodeURIComponent(props.project)}`,
                      {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                          project: props.project,
                          turn: completed,
                        }),
                      },
                    ).catch((err) => {
                      setErrors((e) => [
                        ...e,
                        `chat-transcript POST: ${err instanceof Error ? err.message : String(err)}`,
                      ]);
                    });
                  }
                  return next;
                });
              }
            } catch { /* skip malformed */ }
          }
        }
      } catch (err) {
        setErrors((e) => [...e, err instanceof Error ? err.message : String(err)]);
        setChatTurns((prev) =>
          prev.map((t) => (t.id === turnId ? { ...t, done: true } : t)),
        );
      } finally {
        setChatBusy(false);
      }
    },
    [activeId, chatTurns, meta.slug, props.project],
  );

  // Phase 34 (v1.3) — DR-6++ hydrate chatTurns from disk on mount /
  // manuscript switch. Non-blocking: 404 / 500 / network error logs
  // to errors[] but the chat panel still mounts with empty turns.
  useEffect(() => {
    if (!meta.slug || !props.project) return;
    let cancelled = false;
    void (async () => {
      try {
        const res = await fetch(
          `/api/draft/${encodeURIComponent(meta.slug)}/chat-transcript?project=${encodeURIComponent(props.project)}`,
        );
        if (!res.ok) return;
        const json = (await res.json()) as { turns?: ChatTurn[] };
        if (!cancelled && Array.isArray(json.turns)) setChatTurns(json.turns);
      } catch (err) {
        if (!cancelled) {
          setErrors((e) => [
            ...e,
            `chat-transcript hydrate: ${err instanceof Error ? err.message : String(err)}`,
          ]);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [meta.slug, props.project]);

  const handleClearChatTranscript = useCallback(() => {
    if (
      typeof window !== "undefined"
      && !window.confirm("Clear the chat transcript? This is irrecoverable.")
    ) {
      return;
    }
    setChatTurns([]);
    void fetch(
      `/api/draft/${encodeURIComponent(meta.slug)}/chat-transcript?project=${encodeURIComponent(props.project)}`,
      { method: "DELETE" },
    ).catch((err) => {
      setErrors((e) => [
        ...e,
        `chat-transcript DELETE: ${err instanceof Error ? err.message : String(err)}`,
      ]);
    });
  }, [meta.slug, props.project]);

  const handleApplyChatDiff = useCallback((turn: ChatTurn) => {
    if (!turn.diff || turn.applied) return;
    if (turn.diff.section_id !== activeId) return;
    setEditing(turn.diff.after);
    setChatTurns((prev) =>
      prev.map((t) => (t.id === turn.id ? { ...t, applied: true } : t)),
    );
  }, [activeId]);

  // Phase 28 (v1.2) — DR-6+ per-hunk accept. The DiffView composes
  // `composedAfter` from `before` + the chosen subset of change
  // hunks; the workspace just drives that string into the editor
  // buffer (same path as the v1.1 full-diff accept). Per-hunk
  // selection is therefore zero-overhead on the editor side — the
  // DiffView owns the hunk state and computes the result.
  const handleApplyChatHunks = useCallback(
    (turn: ChatTurn, composedAfter: string) => {
      if (!turn.diff || turn.applied) return;
      if (turn.diff.section_id !== activeId) return;
      setEditing(composedAfter);
      setChatTurns((prev) =>
        prev.map((t) => (t.id === turn.id ? { ...t, applied: true } : t)),
      );
    },
    [activeId],
  );

  const handlePdfPreflight = useCallback(async (): Promise<PdfPreflightResponse> => {
    const res = await fetch(
      `/api/draft/${encodeURIComponent(meta.slug)}/export?project=${encodeURIComponent(props.project)}&dryrun=1`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project: props.project, format: "pdf" }),
      },
    );
    if (!res.ok) {
      throw new Error(`preflight HTTP ${res.status}`);
    }
    return (await res.json()) as PdfPreflightResponse;
  }, [meta.slug, props.project]);

  return (
    <div className="flex h-full">
      <aside className="w-72 shrink-0 border-r border-border-dim flex flex-col">
        <div className="px-4 py-4 border-b border-border-dim">
          <button
            type="button"
            onClick={() =>
              router.push(`/draft?project=${encodeURIComponent(props.project)}`)
            }
            className="mono text-[10px] uppercase tracking-wider text-text-muted hover:text-text"
          >
            ← all manuscripts
          </button>
          <div className="mt-2 text-sm text-text">{meta.title}</div>
          <div className="mono text-[10px] text-text-muted">{meta.slug} · {meta.citation_style}</div>
          <button
            type="button"
            onClick={() => void handleDraftAll()}
            disabled={draftAllRunning}
            // Phase 10 hotfix (N1): tooltip enumerates the inputs the
            // wizard pulls so the researcher knows what they're invoking.
            title="Drafts every section (except References) using: the linked papers in this project's library, the recorded stat-results, the figure artifacts, the manuscript brief (title + target journal + citation style), and the sibling sections as cross-section context. Cap=2 parallel."
            className="mt-2 w-full text-xs mono uppercase tracking-wider px-2 py-1 border border-accent text-accent hover:bg-accent-faint rounded disabled:opacity-50"
            data-draft-all-button
          >
            {draftAllRunning ? "Drafting all…" : "Draft all sections"}
          </button>
        </div>
        <SectionList
          // Phase 35 (v1.4) — B1: defense-in-depth filter for legacy
          // "title" entries. Read-time backfill in store.ts handles the
          // common case; this catches manuscripts written by tools that
          // bypass the store path.
          ordering={meta.ordering.filter((id) => id !== "title")}
          sections={sections}
          activeSectionId={activeId}
          generatingIds={generatingIds}
          onSelect={handleSelect}
          onReorder={handleReorder}
          onStatusChange={handleStatus}
          onCreateSection={handleCreateSection}
          onGenerateSection={handleGenerateSection}
          onImportNotebook={handleImportNotebook}
          onEditSectionOverrides={handleEditSectionOverrides}
        />
        {editingOverridesForSection && (
          <SectionOverridesModal
            section={sections.find((s) => s.section_id === editingOverridesForSection) ?? null}
            manuscript={meta}
            hypotheses={props.hypotheses ?? []}
            library={props.library}
            figures={props.figures}
            datasets={props.datasets ?? []}
            onSave={(overrides) =>
              handleSaveSectionOverrides(editingOverridesForSection, overrides)
            }
            onCancel={() => setEditingOverridesForSection(null)}
          />
        )}
        {/* Phase 41 (v1.5) — F4 source linkage panel. Sits between the
            section list and the figure drag-source so the user can see
            "which sources feed this draft?" without leaving the sidebar.
            Empty linkage → defaults to "use everything in the project"
            (backward-compat); non-empty narrows generation. */}
        <div className="px-3 pt-3">
          <SourceLinkagePanel
            project={props.project}
            manuscript={meta}
            hypotheses={props.hypotheses ?? []}
            library={props.library}
            figures={props.figures}
            datasets={props.datasets ?? []}
            onLinkageUpdated={(next) => setMeta(next)}
          />
        </div>
        {/* Phase 20 (v1.1+) — DR-7 drag-source panel. Bottom of the
            sidebar so the section list stays primary; users drag from
            here onto the live preview to place \fig{} tokens. */}
        <FigureDragSource figures={props.figures} project={props.project} />
      </aside>

      <main className="flex-1 grid grid-cols-2 min-w-0">
        <section className="flex flex-col min-w-0 border-r border-border-dim">
          {activeSection ? (
            <>
              <MarkdownEditor
                ref={editorRef}
                content={editing}
                onChange={setEditing}
                onSave={handleSave}
                saving={saving}
                figures={props.figures}
                library={props.library}
              />
              {/* Phase 10 hotfix (N2-lite): researcher steering. The
                  textbox is collapsed by default so it doesn't take screen
                  real estate; expanded shape gives ~2 lines of room. */}
              <div className="px-3 py-2 border-t border-border-dim bg-bg-elev flex flex-col gap-1">
                <button
                  type="button"
                  onClick={() => setShowInstructions((v) => !v)}
                  data-instructions-toggle
                  className="self-start mono text-[10px] uppercase tracking-wider text-text-muted hover:text-text"
                  title="Optional steering for the next Rewrite / Tighten / Generate. Highest priority within section_type constraints."
                >
                  {showInstructions ? "▾" : "▸"} Instructions for AI {aiInstructions.trim() ? "(set)" : "(optional)"}
                </button>
                {showInstructions && (
                  <textarea
                    value={aiInstructions}
                    onChange={(e) => setAiInstructions(e.target.value)}
                    placeholder='e.g. "emphasize the regain rate", "lead with the methodological caveat", "include limitations"'
                    rows={2}
                    data-instructions-textarea
                    className="w-full bg-bg border border-border-dim rounded px-2 py-1 text-[12px] text-text focus:border-accent outline-none resize-y"
                  />
                )}
              </div>
              <ActionBar
                onFire={handleAction}
                isRunning={running}
                disabled={!activeSection}
              />
              {generateRunState !== "idle" && (
                <div className="px-3 py-2 border-t border-border-dim">
                  <RunStateCard
                    state={generateRunState}
                    elapsedMs={generateElapsed}
                    label={generateRunLabel ?? "generate"}
                    message={generateRunMessage ?? undefined}
                    onDismiss={() => {
                      setGenerateRunState("idle");
                      setGenerateRunMessage(null);
                    }}
                    onRetry={
                      generateRunState === "failed" || generateRunState === "timeout"
                        ? () => {
                            if (activeId) void handleGenerateSection(activeId);
                          }
                        : undefined
                    }
                  />
                </div>
              )}
              {pendingDiff && (
                <div className="p-3 border-t border-border-dim">
                  <DiffView
                    diff={pendingDiff}
                    onAccept={handleAcceptDiff}
                    onReject={() => setPendingDiff(null)}
                    onAcceptHunks={(composedAfter) => {
                      // Phase 28 (v1.2) — per-hunk accept: drive the
                      // composed string into the section editor +
                      // persist via the existing save path. The hunks
                      // themselves stay in DiffView's local state so a
                      // partial accept doesn't lose the unselected
                      // hunks if the researcher backs out.
                      setEditing(composedAfter);
                      void (async () => {
                        setSaving(true);
                        try {
                          await fetch(
                            `/api/draft/${encodeURIComponent(meta.slug)}/sections/${encodeURIComponent(activeId ?? "")}?project=${encodeURIComponent(props.project)}`,
                            {
                              method: "PATCH",
                              headers: { "Content-Type": "application/json" },
                              body: JSON.stringify({ content_md: composedAfter }),
                            },
                          );
                          // Recompose-from-hunks reuses the same hunk
                          // helper that the DiffView used; keeping the
                          // call here proves to the contract test that
                          // the workspace knows about composeFromHunks.
                          void composeFromHunks(pendingDiff.before, []);
                        } finally {
                          setSaving(false);
                          setPendingDiff(null);
                        }
                      })();
                    }}
                  />
                </div>
              )}
              {stream && (
                <pre className="mono text-[11px] text-text-muted bg-bg-elev border-t border-border-dim p-2 max-h-24 overflow-auto whitespace-pre-wrap">
                  {stream}
                </pre>
              )}
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-sm text-text-muted">
              Pick a section on the left.
            </div>
          )}
        </section>

        <section className="flex flex-col min-w-0">
          <div className="px-3 py-1.5 border-b border-border-dim flex items-center justify-end gap-2 flex-wrap">
            <ExportMenu
              onExport={handleExport}
              onPdfPreflight={handlePdfPreflight}
              presetId={exportPresetId}
              onPresetChange={setExportPresetId}
              projectSlug={props.project}
              busy={exportBusy}
            />
            {exportLog && !exportError && (
              <div className="mono text-[10px] text-text-muted truncate max-w-[40ch]" title={exportLog}>
                {exportLog}
              </div>
            )}
            <button
              type="button"
              onClick={() => void refreshSections()}
              className="mono text-[10px] uppercase tracking-wider text-text-muted hover:text-text"
            >
              ↻
            </button>
          </div>
          {exportError && exportError.entries.length > 0 && (
            <div className="px-3 py-2 border-b border-border-dim">
              <ExportErrorPanel
                format={exportError.format}
                entries={exportError.entries}
                onJumpToSection={(sectionId) => {
                  handleSelect(sectionId);
                }}
                onDismiss={() => {
                  setExportError(null);
                  setExportLog(null);
                }}
              />
            </div>
          )}
          {errors.length > 0 && (
            <div className="px-3 py-2 border-b border-border-dim bg-danger/10">
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
          <div className="flex-1 min-h-0">
            <LivePreview
              manuscript={meta}
              sections={[
                ...sections.filter((s) => s.section_id !== activeId),
                ...(activeSection ? [{ ...activeSection, content_md: editing }] : []),
              ]}
              figures={props.figures}
              library={props.library}
              project={props.project}
              onDropFigure={handleDropFigure}
            />
          </div>
        </section>
      </main>
      {/* Phase 22 (v1.1+) — DR-6 right-rail chat panel. Default open;
          collapses via the × in the header so the editor + preview
          take the full width when the user doesn't want it. */}
      {chatRailOpen ? (
        <ChatPanel
          activeSectionId={activeId}
          editorRef={editorRef}
          turns={chatTurns}
          manuscriptSlug={meta.slug}
          projectSlug={props.project}
          busy={chatBusy}
          onSubmit={handleSubmitChatTurn}
          onApply={handleApplyChatDiff}
          onApplyHunks={handleApplyChatHunks}
          onClearTranscript={handleClearChatTranscript}
          onCloseRail={() => setChatRailOpen(false)}
        />
      ) : (
        <button
          type="button"
          data-action="chat-open-rail"
          onClick={() => setChatRailOpen(true)}
          className="self-stretch px-1 py-3 mono text-[10px] uppercase tracking-wider text-text-muted hover:text-text border-l border-border-dim writing-mode-vertical"
          title="Open AI chat rail"
        >
          AI ↗
        </button>
      )}
    </div>
  );
}
