import { createHash, randomBytes } from "node:crypto";

/**
 * PHASE_3_TASKS.md D2 + T07 — content-addressed file IDs.
 * Format: data-{YYYYMMDD}-{6-char-hex} where hex = first 6 chars of
 * sha1(filename + size + first_kb). Same content twice yields the same id,
 * which lets the upload pipeline detect duplicates.
 */
export function allocateFileId(
  filename: string,
  size: number,
  firstKb: Uint8Array | string,
  now: Date = new Date(),
): string {
  // Phase 12c (v1.0.1) — D-4: local date for consistency with allocateRunId.
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  const date = `${y}${m}${d}`;
  const fp =
    typeof firstKb === "string"
      ? firstKb
      : Buffer.from(firstKb).toString("base64");
  const hash = createHash("sha1")
    .update(`${filename}|${size}|${fp}`)
    .digest("hex")
    .slice(0, 6);
  return `data-${date}-${hash}`;
}

/** Time + random fig ID. Format: fig-{YYYYMMDD}-{6-char-hex}. */
export function allocateFigId(now: Date = new Date()): string {
  return allocateRunId("fig", now);
}

/**
 * Generic time + random run ID. Format: {prefix}-{YYYYMMDD}-{6-char-hex}.
 * Used for fig IDs (prefix=fig), stat-result run IDs (prefix=stat), and any
 * future Phase-3+ artifact whose ID is allocated server-side at spawn time.
 *
 * Phase 12c (v1.0.1) — D-4: the date segment uses the *local* date, not
 * UTC. Researchers think in local time; rendering the run-id alongside a
 * local-time `created_at` was producing "yesterday's" runs at 02:00 SGT.
 * Existing runs on disk keep their UTC date (no migration); the list
 * view sorts by `created_at` ISO timestamp, not by id.
 */
export function allocateRunId(prefix: string, now: Date = new Date()): string {
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  const date = `${y}${m}${d}`;
  const hex = randomBytes(3).toString("hex");
  return `${prefix}-${date}-${hex}`;
}
