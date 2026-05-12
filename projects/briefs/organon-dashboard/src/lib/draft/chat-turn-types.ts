// Phase 34 (v1.3) — DR-6++ shared ChatTurn type.
//
// Extracted from `src/components/draft/chat-panel.tsx` so the
// server-only chat-transcripts library (node:fs) can import without
// dragging React into the bundle. The chat-panel re-exports from
// here to preserve the v1.2 import surface.
//
// CRITICAL: this file is client-safe. Do not import from React, Next,
// or any node:* module here. If a downstream consumer needs richer
// typing, prefer extending in the consumer over polluting this shim.

import type { SectionDiffArtifact } from "@/lib/artifacts/types";

export type ChatTurn = {
  id: string;
  prompt: string;
  selectionText: string | null;
  diff: SectionDiffArtifact | null;
  streaming: string;
  done: boolean;
  applied: boolean;
};
