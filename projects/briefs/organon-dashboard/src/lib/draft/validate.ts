import type { SectionType } from "../artifacts/types";
import { stripCodeRegions } from "./code-aware";

/**
 * Phase 10 hotfix (B2 — researcher-found regression on 2026-05-07):
 *
 * The dogfood walk surfaced that generate-section + dashboard-action
 * could write content meant for one section into another section's
 * slot. Repro: stand on the title section, click Generate; the skill
 * emits abstract-shaped markdown; the route's artifact narrowing only
 * checked `section_id` matched and accepted the body. Result: the
 * title slot stored ## Abstract content, and a subsequent Rewrite
 * legitimately rewrote that polluted body, presenting a "rewriting
 * the title produces an abstract" surprise.
 *
 * The fix is structural: at the persistence boundary (route-level)
 * validate that the emitted content_md's heading shape matches the
 * declared section_type. This is the contract that lets the skill
 * be wrong without corrupting state — the route refuses to persist
 * a mismatched body and the UI surfaces a `validation-failed` warning
 * instead of "Section drafted." reassurance.
 *
 * Validation rules (per section_type):
 *   title         — must start with `# ` (h1), no `## `, ≤ 500 chars
 *   abstract      — must contain `## Abstract` (case-insensitive)
 *   introduction  — must contain `## Introduction` (case-insensitive)
 *   methods       — must contain `## Methods` (case-insensitive)
 *   results       — must contain `## Results` (case-insensitive)
 *   discussion    — must contain `## Discussion` (case-insensitive)
 *   references    — never validated (auto-populated, not generated)
 *   custom        — any heading shape OK; only checks non-empty
 *
 * Code-region stripping: headings inside fenced code blocks or inline
 * backticks don't count. Phase 9's code-aware helper already handles
 * the strip; reusing it keeps the contract aligned with parse +
 * resolve + render.
 */

export type ValidationResult =
  | { ok: true }
  | { ok: false; reason: string };

const TITLE_MAX_CHARS = 500;

const SECTION_HEADING_RE: Partial<Record<SectionType, RegExp>> = {
  abstract:     /^##\s+abstract\b/im,
  introduction: /^##\s+introduction\b/im,
  methods:      /^##\s+methods\b/im,
  results:      /^##\s+results\b/im,
  discussion:   /^##\s+discussion\b/im,
};

/** True if `content_md` looks like a body for `section_type`. */
export function validateGeneratedContent(
  contentMd: string,
  sectionType: SectionType,
): ValidationResult {
  const stripped = stripCodeRegions(contentMd).trim();
  if (stripped.length === 0) {
    return { ok: false, reason: "Generated content is empty (no prose outside code regions)." };
  }

  switch (sectionType) {
    case "title": {
      // Title is special: a single-line `# <title>` plus optional author /
      // affiliation lines. Reject if it looks like a body section (## Abstract,
      // ## Methods, etc.) or if it's longer than the title-shape budget.
      if (contentMd.length > TITLE_MAX_CHARS) {
        return {
          ok: false,
          reason: `Title body must be ≤ ${TITLE_MAX_CHARS} chars; got ${contentMd.length}. The skill likely returned a section body in the title slot.`,
        };
      }
      if (!/^#\s+\S/m.test(stripped)) {
        return {
          ok: false,
          reason: "Title body must start with an h1 heading (`# Title`); none found.",
        };
      }
      // The h1 must come before any h2. If there's an h2 anywhere it's
      // probably a body section that bled into the title slot.
      const firstH1 = stripped.search(/^#\s+\S/m);
      const firstH2 = stripped.search(/^##\s+\S/m);
      if (firstH2 >= 0 && (firstH1 < 0 || firstH2 < firstH1)) {
        return {
          ok: false,
          reason: "Title body contains an h2 heading; the skill likely emitted a section body in the title slot.",
        };
      }
      return { ok: true };
    }
    case "references":
      // The references body is regenerated from \cite{} blocks at export
      // time. Generate is disallowed at the UI layer; reaching this branch
      // means a route accepted it anyway. Reject defensively.
      return {
        ok: false,
        reason: "References section is auto-populated from \\cite{} blocks; generate is not supported here.",
      };
    case "custom":
      // Custom sections may use any heading shape — only require non-empty
      // (already checked above).
      return { ok: true };
    default: {
      const re = SECTION_HEADING_RE[sectionType];
      if (!re) return { ok: true };
      if (!re.test(stripped)) {
        return {
          ok: false,
          reason: `Generated content is missing the expected \`## ${capitalize(sectionType)}\` heading; the skill likely targeted the wrong section.`,
        };
      }
      return { ok: true };
    }
  }
}

function capitalize(s: string): string {
  return s.length === 0 ? s : s[0].toUpperCase() + s.slice(1);
}

/**
 * Fallback content extractor — when the skill exits clean but emits no
 * valid section-draft JSON line, scan the accumulated stdout for the
 * largest unfenced markdown body that has the right heading shape.
 *
 * This is a defensive recovery, not a contract: the gate still warns
 * the user that the skill misbehaved (no first-class section-draft
 * artifact). Returns null if nothing usable found.
 */
export function extractFallbackContent(
  stdout: string,
  sectionType: SectionType,
): string | null {
  if (sectionType === "references") return null;

  // Strip JSON-line residue (the skill may have emitted partial JSON in
  // stdout) by dropping any line that starts with `{` and ends with `}`.
  const lines = stdout.split("\n").filter((l) => {
    const t = l.trim();
    return !(t.startsWith("{") && t.endsWith("}"));
  });
  const text = lines.join("\n");

  // For title: pick the first `# ` line + optional follow-on lines until
  // a blank.
  if (sectionType === "title") {
    const m = text.match(/^#\s+\S[^\n]*(?:\n[^\n#]+)*/m);
    return m ? m[0].trim() : null;
  }

  // For body sections: pick the largest unfenced block that opens with
  // the matching `## ` heading and runs until either EOF, the next `## `
  // heading, or a triple-newline boundary.
  const re = SECTION_HEADING_RE[sectionType];
  if (!re) return null;
  const stripped = stripCodeRegions(text);
  const startMatch = stripped.match(re);
  if (!startMatch || startMatch.index == null) return null;
  const after = stripped.slice(startMatch.index);
  const nextH2 = after.slice(2).search(/\n##\s+\S/);
  const body = nextH2 < 0 ? after : after.slice(0, 2 + nextH2);
  const trimmed = body.trim();
  return trimmed.length > 20 ? trimmed : null;
}
