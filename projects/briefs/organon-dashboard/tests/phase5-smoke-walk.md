# Phase 5 — manual smoke walk (T38)

PHASE_5_TASKS.md §10 acceptance gate. Run after a clean `npm run build` whenever any Phase 5 file changes.

## Prereqs

- Phase 4 acceptance gate green.
- For the rewrite/tighten/check/humanize SSE actions: `claude` binary on PATH (uses claude-runner).
- For PDF/HTML/DOCX export: `pandoc` (and `xelatex` for PDF), `marp` on PATH. Markdown export always works.

## Setup

```bash
cd projects/briefs/organon-dashboard
bash -lc 'set -a; source ../../../.env 2>/dev/null; set +a; npm run dev'
```

Open http://localhost:8769/draft?project=__root__.

## Walk

1. **Empty state** — list shows "No manuscripts yet" + "+ new manuscript" CTA.
2. **Create** — click "+ new manuscript", title "GLP-1 receptor meta-analysis", citation_style APA, Create. Page redirects to `/draft/glp-1-receptor-meta-analysis?project=__root__` and shows the three-pane workspace with 7 default sections (title / abstract / introduction / methods / results / discussion / references).
3. **Edit + save** — click "introduction". Editor populates. Type "GLP-1 receptor agonists are widely used for type-2 diabetes." then Cmd+S. Save badge clears, version bumps from 1 → 2 in the section list.
4. **Live preview** — preview pane updates within ~100 ms with the new text rendered as HTML.
5. **`\fig{}` autocomplete** — in editor, type "Figure: \fig{". Popover appears with the project's figures (will be empty unless Phase 4 generated some). Pick one → it inserts the id + closing brace; preview shows `Fig. 1` caption.
6. **`\cite{}` autocomplete** — type "(\cite{". Popover lists library papers (assumes /lit has saved at least one). Pick one → preview shows (Author, Year) inline AND a References section appears at the bottom of the preview with the bib entry.
7. **Status pill** — click the "draft" pill on a section → advances to "reviewed" → "final" → cycles back to "draft".
8. **Reorder** — hover a section row, click ▲ / ▼ buttons. Section ordering updates; preview re-renders in new order.
9. **ActionBar — tighten** — click "Tighten" on the introduction. SSE pane shows live skill output. Within ~30 s a DiffView lands below the editor with side-by-side before/after + rationale. Click "Reject" → diff dismissed, no change. Click "Tighten" again → "Accept" → editor + section both update; version bumps.
10. **ActionBar — humanize** — click "Humanize" on a different section. Same flow but routes to `tool-humanizer`.
11. **Custom section** — click "+ new" in the section list header, name it "appendix". Section appears at the end with default body "## appendix\n\n_Drafting…_".
12. **Export — markdown** — Export → Markdown → file lands at `projects/__root__/manuscripts/<slug>/exports/<date>_<slug>.md` and the export-log line shows the path. Open it; sections concatenated in order + bibliography appended.
13. **Export — pdf / html / docx** — fire each. If pandoc/marp/xelatex missing, response is 503 with "Pandoc/Marp export failed; install ... or use the markdown export at <path>" — markdown still has the manuscript, no data loss.
14. **Export — substack** — currently returns 501 with the markdown path + a hint to pipe through `tool-substack` manually.
15. **Cmd+K** — palette has Draft group: "Go to Drafts", "New manuscript". Selecting "Go to Drafts" navigates back to the list.
16. **No regressions** — visit /lit, /hypothesis, /data, /figures. All still functional.

## Gate

**All 16 boxes ticked + `npm run build` exits 0 + `npm test` 16/16 green.**

## Known caveats

- `claude -p` cold start adds ~30 s before the first SSE event on action runs.
- Pandoc + Marp aren't installed by the dashboard; users provide them. The route returns a clean 503 + the markdown fallback path.
- Substack export currently emits 501 with a hint — full wiring deferred until `tool-substack` API is exercised through the dashboard route.
- KaTeX math rendering deferred; markdown source can carry $...$ blocks but they render literally for now.
- The hand-rolled markdown renderer in `lib/draft/render.ts` covers paragraphs / headings / **bold** / *italic* / `code` / fenced code / blockquotes / lists / links + custom `\fig{}` `\cite{}` plugins. Tables, footnotes, definition lists deferred.
