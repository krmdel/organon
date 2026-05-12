import { createHash } from "node:crypto";

// Re-export the client-safe slug helper.
export { slugifyPersona } from "./shared";

/**
 * PHASE_2_TASKS.md D4 — pre-allocated hypothesis IDs.
 * Format: hyp-{YYYYMMDD}-{6-char-hex} where hex = first 6 chars of sha1(claim + iso_timestamp).
 */
export function allocateHypothesisId(claim: string, now: Date = new Date()): string {
  const iso = now.toISOString();
  const date = iso.slice(0, 10).replace(/-/g, "");
  const hash = createHash("sha1").update(`${claim}|${iso}`).digest("hex").slice(0, 6);
  return `hyp-${date}-${hash}`;
}
