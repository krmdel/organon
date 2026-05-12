/**
 * PHASE_6_TASKS.md T25 — in-memory cross-corpus search index.
 *
 * Sources: papers, hypotheses, figures, sections.
 * Scope: a single project (or __root__ via the synthetic project).
 * Refresh policy: rebuilt on demand; ~500-row scan budget < 50 ms.
 */

import { listLibrary } from "../lit/library";
import { listHypotheses } from "../hypothesis/store";
import { listFigures } from "../figures/store";
import { listManuscripts, listSections } from "../draft/store";
import { scoreText } from "./score";

export type SearchHit = {
  type: "paper" | "hypothesis" | "figure" | "section" | "manuscript";
  id: string;
  title: string;
  subtitle?: string;
  href: string;
  score: number;
  matched: string[];
};

export type IndexEntry = {
  type: SearchHit["type"];
  id: string;
  title: string;
  subtitle?: string;
  href: string;
  haystack: string;
};

export function buildIndex(projectPath: string, projectSlug: string): IndexEntry[] {
  const out: IndexEntry[] = [];

  for (const p of listLibrary(projectPath)) {
    out.push({
      type: "paper",
      id: p.id,
      title: p.title,
      subtitle: `${p.authors.slice(0, 2).join(", ")}${p.authors.length > 2 ? "…" : ""} · ${p.year ?? "?"}`,
      href: `/lit?project=${encodeURIComponent(projectSlug)}&paper=${encodeURIComponent(p.id)}`,
      haystack: [p.id, p.title, p.authors.join(" "), p.journal ?? "", p.abstract ?? ""].join(" "),
    });
  }

  for (const h of listHypotheses(projectPath)) {
    out.push({
      type: "hypothesis",
      id: h.id,
      title: h.claim_short ?? h.claim,
      subtitle: `${h.status} · ${h.personas_used.join(", ")}`,
      href: `/hypothesis?project=${encodeURIComponent(projectSlug)}&hyp=${encodeURIComponent(h.id)}`,
      haystack: [h.id, h.claim, h.synthesis_text ?? "", (h.tags ?? []).join(" ")].join(" "),
    });
  }

  for (const f of listFigures(projectPath)) {
    out.push({
      type: "figure",
      id: f.id,
      title: String(f.params?.prompt ?? f.kind),
      subtitle: `${f.backend} · v${f.version}`,
      href: `/figures?project=${encodeURIComponent(projectSlug)}&fig=${encodeURIComponent(f.id)}`,
      haystack: [f.id, String(f.params?.prompt ?? ""), f.caption ?? "", f.alt_text ?? ""].join(" "),
    });
  }

  for (const m of listManuscripts(projectPath)) {
    out.push({
      type: "manuscript",
      id: m.slug,
      title: m.title,
      subtitle: `${m.citation_style} · ${m.ordering.length} sections`,
      href: `/draft/${encodeURIComponent(m.slug)}?project=${encodeURIComponent(projectSlug)}`,
      haystack: [m.slug, m.title, (m.authors ?? []).join(" "), m.target_journal ?? ""].join(" "),
    });
    for (const s of listSections(projectPath, m.slug)) {
      out.push({
        type: "section",
        id: `${m.slug}/${s.section_id}`,
        title: `${m.title} → ${s.section_id}`,
        subtitle: `${s.section_type} · ${s.status} · v${s.version}`,
        href: `/draft/${encodeURIComponent(m.slug)}?project=${encodeURIComponent(projectSlug)}&section=${encodeURIComponent(s.section_id)}`,
        haystack: [s.section_id, s.section_type, s.content_md].join(" "),
      });
    }
  }

  return out;
}

export function searchIndex(
  index: IndexEntry[],
  query: string,
  opts: { types?: SearchHit["type"][]; limit?: number } = {},
): SearchHit[] {
  const limit = opts.limit ?? 25;
  const allowed = opts.types ? new Set(opts.types) : null;
  const ql = query.trim();
  if (!ql) return [];
  const hits: SearchHit[] = [];
  for (const e of index) {
    if (allowed && !allowed.has(e.type)) continue;
    const titleScore = scoreText(`${e.id} ${e.title}`, ql);
    const bodyScore = scoreText(e.haystack, ql);
    const score = Math.max(titleScore.score, bodyScore.score * 0.85);
    const matched = titleScore.matched.length > 0 ? titleScore.matched : bodyScore.matched;
    if (score > 0) {
      hits.push({
        type: e.type,
        id: e.id,
        title: e.title,
        subtitle: e.subtitle,
        href: e.href,
        score,
        matched,
      });
    }
  }
  hits.sort((a, b) => b.score - a.score || a.id.localeCompare(b.id));
  return hits.slice(0, limit);
}
