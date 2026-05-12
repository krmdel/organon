// Phase 20 (v1.1+) — Figure drag-drop placement helper (DR-7).
//
// Inserts a `\fig{<fig_id>}` token at the given source line of a
// section's content_md. Idempotent on duplicate drops near the same
// location: if the same fig token is already present within ±1 line
// of the target, the call no-ops. This catches the typical "drop
// twice" UX where the second drop lands one line below the first
// insert.
//
// Different fig_ids on the same line DO insert (intentional placement
// of a sister figure adjacent to its sibling is a real workflow).
//
// Pure function — no DOM, no React. Lives in src/lib/draft so both
// the workspace's drop handler and any future server-side automation
// can use the same insertion semantics.

export function insertFigAtLine(
  contentMd: string,
  line: number,
  figId: string,
): string {
  const figToken = `\\fig{${figId}}`;
  const lines = contentMd.split("\n");
  const total = lines.length;
  if (total === 0) return contentMd;
  // Clamp the 1-indexed line into [1, total]. Out-of-range drops are
  // expected when a drop near the end of a long section maps to a
  // ghost source-line; clamping makes the helper safe to call with any
  // resolved value.
  const idx = Math.max(1, Math.min(line, total)) - 1;
  // Idempotent: if the same fig token is already within ±1 line of
  // the target, no-op. The ±1 window catches the second of two drops
  // at the same UI target — the first insert lands at idx + 1, so a
  // second click would otherwise duplicate.
  for (let j = Math.max(0, idx - 1); j <= Math.min(total - 1, idx + 1); j++) {
    if (lines[j]?.includes(figToken)) return contentMd;
  }
  // Insert the fig token as its own line directly after the target.
  // Keeping it on a standalone line means cite/fig resolvers see the
  // token cleanly; the inline-paragraph case is rare enough to defer.
  lines.splice(idx + 1, 0, figToken);
  return lines.join("\n");
}
