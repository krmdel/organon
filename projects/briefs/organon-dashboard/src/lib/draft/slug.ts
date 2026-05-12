/**
 * PHASE_5_TASKS.md T07 — manuscript slug allocator.
 * Slug = lowercased, hyphenated form of the title, ≤ 60 chars, with a
 * collision suffix if needed.
 */
export function allocateManuscriptSlug(
  title: string,
  existing: string[],
): string {
  const base = title
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60) || "manuscript";
  if (!existing.includes(base)) return base;
  for (let n = 2; n < 1000; n++) {
    const candidate = `${base}-${n}`;
    if (!existing.includes(candidate)) return candidate;
  }
  return `${base}-${Date.now()}`;
}
