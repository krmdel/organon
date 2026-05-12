// Phase 34 (v1.3) — DR-6++ on-disk chat transcript persistence.
//
// Per-manuscript scope (NOT per-section). Storage:
//   <projectPath>/.organon/chat-transcripts/{slug}.json
// Cap: MAX_TRANSCRIPT_TURNS = 200 (soft archive — older drop on
// append; same shape as Phase 24's MAX_LEGEND_HISTORY=20 but scaled
// up because turns are smaller). Atomic writes via tmp + rename
// (same pattern as Phase 25's writeAtomic).
//
// Drop-not-throw on bad files: missing / malformed JSON / unexpected
// shape returns [] so a corrupted file doesn't break the chat session.
// The DELETE handler is the only hard-clear path.

import {
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import type { ChatTurn } from "./chat-turn-types";

export const MAX_TRANSCRIPT_TURNS = 200;

function transcriptDir(projectPath: string): string {
  return path.join(projectPath, ".organon", "chat-transcripts");
}

function transcriptPath(projectPath: string, slug: string): string {
  return path.join(transcriptDir(projectPath), `${slug}.json`);
}

export function readTranscript(projectPath: string, slug: string): ChatTurn[] {
  const file = transcriptPath(projectPath, slug);
  if (!existsSync(file)) return [];
  try {
    const raw = readFileSync(file, "utf8");
    const parsed = JSON.parse(raw) as { turns?: unknown };
    if (!parsed || !Array.isArray(parsed.turns)) return [];
    // Permissive validation — accept any object that looks like a turn,
    // drop entries that don't. Same drop-not-throw shape as Phase 25.
    const valid: ChatTurn[] = [];
    for (const entry of parsed.turns) {
      if (
        entry
        && typeof entry === "object"
        && typeof (entry as { id?: unknown }).id === "string"
        && typeof (entry as { prompt?: unknown }).prompt === "string"
      ) {
        valid.push(entry as ChatTurn);
      }
    }
    return valid;
  } catch {
    return [];
  }
}

function writeAtomic(target: string, content: string): void {
  const dir = path.dirname(target);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  const tmp = target + ".tmp";
  writeFileSync(tmp, content, "utf8");
  renameSync(tmp, target);
}

export function appendTurn(projectPath: string, slug: string, turn: ChatTurn): void {
  const existing = readTranscript(projectPath, slug);
  const next = [...existing, turn].slice(-MAX_TRANSCRIPT_TURNS);
  writeAtomic(
    transcriptPath(projectPath, slug),
    JSON.stringify({ turns: next }, null, 2),
  );
}

export function clearTranscript(projectPath: string, slug: string): void {
  const file = transcriptPath(projectPath, slug);
  try {
    if (existsSync(file)) unlinkSync(file);
  } catch {
    // idempotent — never throw out of clear
  }
}
