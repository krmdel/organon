"use client";

import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import type { FigureArtifact, PaperArtifact } from "@/lib/artifacts/types";
import { EmbedAutocomplete, type AutocompleteKind } from "./embed-autocomplete";
import { SyntaxCheatsheet } from "./syntax-cheatsheet";

// Phase 22 (v1.1+) — DR-6 chat-panel selection capture. The chat panel
// reads the editor's current selection via this imperative handle
// instead of lifting selection into workspace state (too noisy for
// every keystroke). Returns null when there's no live selection range.
export type MarkdownEditorHandle = {
  getSelection: () => { start: number; end: number; text: string } | null;
  /** Phase 61 (v2.1) — A4: scroll the editor textarea into view + focus
   *  it so a freshly-drafted section is visible after generate-section
   *  succeeds. No-op when the textarea isn't mounted. */
  scrollIntoView: () => void;
};

// Phase 10 hotfix (N3 — researcher-found pain on 2026-05-07): debounced
// autosave so a navigation-after-edit no longer loses work. 1500 ms
// matches "stopped typing for ~1.5 s = ready to save" without rate-
// limiting the API.
const AUTOSAVE_DEBOUNCE_MS = 1500;

export type MarkdownEditorProps = {
  content: string;
  onChange: (next: string) => void;
  onSave: () => void;
  saving?: boolean;
  figures: FigureArtifact[];
  library: PaperArtifact[];
};

export const MarkdownEditor = forwardRef<MarkdownEditorHandle, MarkdownEditorProps>(function MarkdownEditor(props, fwdRef) {
  const ref = useRef<HTMLTextAreaElement | null>(null);
  useImperativeHandle(fwdRef, (): MarkdownEditorHandle => ({
    getSelection: () => {
      const ta = ref.current;
      if (!ta) return null;
      const start = ta.selectionStart ?? 0;
      const end = ta.selectionEnd ?? 0;
      if (end <= start) return null;
      return { start, end, text: ta.value.slice(start, end) };
    },
    scrollIntoView: () => {
      const ta = ref.current;
      if (!ta) return;
      try {
        ta.scrollIntoView({ behavior: "smooth", block: "start" });
      } catch {
        // older browsers — fall back to instant scroll.
        ta.scrollIntoView();
      }
    },
  }), []);
  const [autocomplete, setAutocomplete] = useState<{ kind: AutocompleteKind; query: string; insertAt: number } | null>(null);
  const [dirty, setDirty] = useState(false);
  // Phase 10 hotfix (N3): autosave timer + last-saved indicator.
  const autosaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onSaveRef = useRef(props.onSave);
  useEffect(() => { onSaveRef.current = props.onSave; }, [props.onSave]);
  const [lastAutoSaveAt, setLastAutoSaveAt] = useState<number | null>(null);

  useEffect(() => {
    setDirty(false);
    if (autosaveTimer.current) {
      clearTimeout(autosaveTimer.current);
      autosaveTimer.current = null;
    }
  }, [props.content]);

  // Phase 10 hotfix (N3): debounced autosave on edit. Schedules a save
  // 1.5 s after the last keystroke; pressing Save manually clears the
  // timer because props.content updates → resets dirty → useEffect above
  // fires.
  useEffect(() => {
    if (!dirty) return;
    if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
    autosaveTimer.current = setTimeout(() => {
      onSaveRef.current();
      setLastAutoSaveAt(Date.now());
    }, AUTOSAVE_DEBOUNCE_MS);
    return () => {
      if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
    };
  }, [dirty, props.content]);

  // Scan caret context — if user is typing inside `\fig{...` or `\cite{...`,
  // pop the autocomplete with the in-progress query.
  const updateAutocomplete = (text: string, caret: number) => {
    const before = text.slice(0, caret);
    const figIdx = before.lastIndexOf("\\fig{");
    const citeIdx = before.lastIndexOf("\\cite{");
    let kind: AutocompleteKind | null = null;
    let openAt = -1;
    if (figIdx > citeIdx && figIdx >= 0) { kind = "fig"; openAt = figIdx + 5; }
    else if (citeIdx >= 0) { kind = "cite"; openAt = citeIdx + 6; }
    if (kind === null) { setAutocomplete(null); return; }
    const queryRegion = before.slice(openAt);
    if (queryRegion.includes("}") || /\s/.test(queryRegion)) { setAutocomplete(null); return; }
    setAutocomplete({ kind, query: queryRegion, insertAt: openAt });
  };

  const onChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const next = e.target.value;
    setDirty(true);
    props.onChange(next);
    updateAutocomplete(next, e.target.selectionStart);
  };

  const onSelect = (e: React.SyntheticEvent<HTMLTextAreaElement>) => {
    updateAutocomplete(e.currentTarget.value, e.currentTarget.selectionStart);
  };

  const handlePick = (id: string) => {
    if (!autocomplete) return;
    const ta = ref.current;
    if (!ta) return;
    const value = ta.value;
    const before = value.slice(0, autocomplete.insertAt);
    // Insert the picked id, append "}", and place caret after it.
    const after = value.slice(autocomplete.insertAt + autocomplete.query.length);
    const inserted = `${id}}`;
    const next = `${before}${inserted}${after}`;
    props.onChange(next);
    setDirty(true);
    setAutocomplete(null);
    requestAnimationFrame(() => {
      ta.focus();
      const caret = autocomplete.insertAt + inserted.length;
      ta.setSelectionRange(caret, caret);
    });
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
      e.preventDefault();
      props.onSave();
    }
  };

  return (
    <div className="relative h-full flex flex-col">
      <div className="px-3 py-2 mono text-[10px] uppercase tracking-wider text-text-muted border-b border-border-dim flex items-center justify-between">
        <span>Editor</span>
        <span className="flex items-center gap-2">
          {dirty
            ? <span className="text-text-muted" title="Autosaving in 1.5 s of inactivity">● unsaved · autosaves</span>
            : lastAutoSaveAt != null
              ? <span className="text-text-muted" title="Autosaved on last pause">✓ autosaved</span>
              : null}
          <SyntaxCheatsheet />
          <button
            type="button"
            onClick={props.onSave}
            disabled={props.saving}
            className="mono text-[10px] uppercase tracking-wider px-2 py-0.5 border border-accent text-accent hover:bg-accent-faint rounded disabled:opacity-50"
            title="Save (Cmd+S)"
          >
            {props.saving ? "saving…" : "save"}
          </button>
        </span>
      </div>
      <textarea
        ref={ref}
        value={props.content}
        onChange={onChange}
        onSelect={onSelect}
        onKeyDown={onKeyDown}
        spellCheck={false}
        className="flex-1 w-full bg-bg text-text mono text-[13px] leading-relaxed px-4 py-3 outline-none resize-none border-0"
      />
      {autocomplete && (
        <EmbedAutocomplete
          kind={autocomplete.kind}
          query={autocomplete.query}
          figures={props.figures}
          library={props.library}
          onPick={handlePick}
          onClose={() => setAutocomplete(null)}
        />
      )}
    </div>
  );
});
