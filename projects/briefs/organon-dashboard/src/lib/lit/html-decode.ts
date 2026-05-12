/**
 * Phase 3 (fix-sprint) — zero-dependency HTML entity decode for paper
 * metadata. PubMed E-utils returns abstracts and journal names with
 * encoded entities (`&amp;`, `&lt;sub&gt;...`, `&#x2014;`, `&#039;`),
 * and a smaller share comes through OpenAlex/S2/arXiv. We decode and
 * strip safe inline tags once at savePaper time so every downstream
 * consumer (BibTeX, draft preview, rendered bibliography, hypothesis
 * paper picker) sees plain UTF-8 text.
 *
 * Closes dogfood Finding #3.
 */

const NAMED_ENTITIES: Record<string, string> = {
  "&amp;": "&",
  "&lt;": "<",
  "&gt;": ">",
  "&quot;": '"',
  "&apos;": "'",
  "&nbsp;": " ",
  "&copy;": "©",
  "&reg;": "®",
  "&trade;": "™",
  "&hellip;": "…",
  "&mdash;": "—",
  "&ndash;": "–",
  "&lsquo;": "‘",
  "&rsquo;": "’",
  "&ldquo;": "“",
  "&rdquo;": "”",
  "&times;": "×",
  "&plusmn;": "±",
  "&micro;": "µ",
  "&deg;": "°",
};

/**
 * Decode HTML entities. Handles the named entities above plus numeric
 * (`&#N;`) and hexadecimal (`&#xN;`) forms. Unknown entities pass through
 * unchanged so we don't mangle text that contains literal `&Other;`.
 */
export function decodeEntities(input: string): string {
  if (!input || input.indexOf("&") === -1) return input;
  return input.replace(/&(#x[0-9a-fA-F]+|#\d+|[a-zA-Z][a-zA-Z0-9]+);/g, (raw, body) => {
    if (NAMED_ENTITIES[raw]) return NAMED_ENTITIES[raw];
    if (typeof body === "string") {
      if (body.startsWith("#x") || body.startsWith("#X")) {
        const code = parseInt(body.slice(2), 16);
        if (Number.isFinite(code) && code > 0 && code < 0x110000) {
          try { return String.fromCodePoint(code); } catch { return raw; }
        }
      } else if (body.startsWith("#")) {
        const code = parseInt(body.slice(1), 10);
        if (Number.isFinite(code) && code > 0 && code < 0x110000) {
          try { return String.fromCodePoint(code); } catch { return raw; }
        }
      }
    }
    return raw;
  });
}

/**
 * Strip the safe-inline-tag set that PubMed/OpenAlex use in abstracts:
 * b, i, em, strong, sub, sup. We preserve their contents (no greedy
 * `<.+?>` strip — that would eat author affiliations encoded as
 * `<sup>1</sup>` and similar). Tags outside this allow-list pass
 * through unchanged so a malformed payload doesn't lose paragraphs.
 */
export function stripSafeTags(input: string): string {
  if (!input || input.indexOf("<") === -1) return input;
  return input.replace(/<\/?(b|i|em|strong|sub|sup)(\s[^>]*)?>/gi, "");
}
