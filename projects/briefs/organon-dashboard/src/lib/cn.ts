/**
 * Minimal classnames helper. Filters falsy and joins with spaces.
 * Avoids pulling in `clsx` for a 3-line utility.
 */
export function cn(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}
