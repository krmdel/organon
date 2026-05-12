/**
 * PHASE_4_TASKS.md T25 — cost in cents per FAL call.
 *
 * FLUX.1 [pro] Fill: $0.05/MP. Round up; the price page rounds to whole-cent
 * billing per call so a 0.42 MP edit shows as 3¢, not 2.1¢.
 */
export function fluxFillCostCents(megapixels: number): number {
  if (!Number.isFinite(megapixels) || megapixels <= 0) return 0;
  return Math.max(1, Math.ceil(megapixels * 5));
}

/**
 * Gemini 3 Pro Image (text-to-image) charges per image generated, not per
 * megapixel. Fixed estimate per call.
 */
export const GEMINI_GEN_COST_CENTS = 4;

/** Convert pixel dimensions to a megapixel count for cost calc. */
export function megapixels(widthPx: number, heightPx: number): number {
  if (widthPx <= 0 || heightPx <= 0) return 0;
  return (widthPx * heightPx) / 1_000_000;
}
