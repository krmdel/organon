# Organon Dashboard

A scientist-facing UI for Organon. Run literature search, hypothesis generation, data analysis, image generation, and manuscript drafting from a browser instead of the CLI.

This repo lives inside the Organon monorepo at `projects/briefs/organon-dashboard/`. Strategic plan: [PLAN.md](./PLAN.md). Tactical phase plans: [PHASE_1_TASKS.md](./PHASE_1_TASKS.md) (shipped), [PHASE_2_TASKS.md](./PHASE_2_TASKS.md), [PHASE_3_TASKS.md](./PHASE_3_TASKS.md), [PHASE_4_TASKS.md](./PHASE_4_TASKS.md), [PHASE_5_TASKS.md](./PHASE_5_TASKS.md), [PHASE_6_TASKS.md](./PHASE_6_TASKS.md).

---

## Quickstart

```bash
# from Organon repo root, build the paper-search MCP source once:
cd mcp-servers/paper-search && npm install && npm run build

# then bootstrap the dashboard:
cd ../../projects/briefs/organon-dashboard
npm install

# load Organon's .env (NCBI_API_KEY, OPENALEX_API_KEY, S2_API_KEY, …) and start dev:
bash -lc 'set -a; source ../../../.env 2>/dev/null; set +a; npm run dev'
```

Dashboard runs on **http://localhost:8769** (AgenticOS dashboard owns 8768 — keep them disjoint).

## What works in Phases 1–6 (v1.0 candidate)

- Project picker scans `<organon-root>/projects/` and shows every directory plus a synthetic `__root__` for the Organon repo itself.
- `/lit` workspace: federated search across PubMed / arXiv / OpenAlex / Semantic Scholar with DOI dedupe + composite ranking. BibTeX export. Cross-link "Generate hypothesis from this paper" → /hypothesis with paper preselected.
- `/hypothesis` workspace: claim form + library paper picker, 3-persona council fanout (Skeptic / Methodologist / Domain-expert by default; one-click swap to Gauss / Erdős / Tao for math). Reconcile → synthesis card. Status state machine. Per-project `hypotheses/personas.json` is editable inline.
- `/data` workspace: file uploader (CSV / XLSX / JSON, 200 MB cap), 50-row dataframe preview with per-column type inference + override, stat test picker wizard with assumption-aware recommendations, plot picker (histogram / scatter / box / violin / heatmap / PCA / line) with editable params and `.py` sidecar export.
- `/figures` workspace: prompt + style picker (6 styles, scientific sub-styles), Gemini-based generation via `viz-nano-banana`, region inpaint with circle / lasso / rectangle mask tools via FAL FLUX.1 Pro Fill, version history thumbnail strip, lock + auto-caption + alt-text via `sci-writing` caption mode.
- `/draft` workspace: per-project manuscript list → three-pane editor (sections / markdown editor / live preview). `\fig{fig-id}` embeds a figure with auto-numbered caption; `\cite{paper-id}` resolves to (Author, Year) inline + appears in the auto-bibliography. ActionBar fires sci-writing or tool-humanizer; diff view accepts/rejects. Export to Markdown (always), PDF/HTML/DOCX (if Pandoc + Marp installed), Substack (stub).
- `/tools` workspace (Phase 6): aggregated catalog (local Organon skills + MCP server entries from `.mcp.json`). Per-project favourites pinned at the top. Click a skill → form-based prompt input → SSE stream of skill output + emitted artifacts. MCP entries surface a CLI-invocation hint (MCPs aren't directly invokable from the dashboard process).
- `/crons` workspace (Phase 6): read-only status board for `cron/jobs/*.md`. Pulls schedule + active flag + last-run + fail-count from `cron/status/*.json` + matches `~/Library/LaunchAgents/com.organon.*.plist` to flag installed jobs.
- `/runs` workspace (Phase 6): full run history (last 200 entries) per project. Click a row → drawer with full prompt + stdout + stderr + duration + linked-artifact links (papers / hypotheses / figures jump back to their workspaces).
- `/usage` page (Phase 6): real SVG charts (daily token bars + by-model pie) reading from `~/.claude/projects/<encoded-cwd>/*.jsonl`. Replaces P1 placeholder.
- `Cmd+K` command palette: cross-corpus search (papers + hypotheses + figures + sections + manuscripts) above the static navigate / quick-action / skill / project groups. Type-color-coded hits. Backed by `/api/search`.
- `/api/execute` SSE stream with `_artifact: paper / hypothesis / persona-critique / dataframe / stat-result / figure / section-draft / section-diff` extraction + auto-persist (section-diff is transient — UI-only).

## What's deferred to v1.0 polish

- Cron enable / disable / run-now from the UI (Phase 6 ships read-only).
- ToolUniverse 2,000+ catalog fetch — currently the catalog draws from local skills + MCP server entries. Live ToolUniverse browse waits until the dashboard can spawn `uvx`.
- Markdown editor: KaTeX / tables / footnotes (renderer is hand-rolled; current subset is paragraphs / headings / **bold** / *italic* / `code` / fenced code / blockquotes / lists / links + the custom `\fig{}` + `\cite{}` plugins).
- Substack export through `tool-substack` — currently returns 501 with a hint.

See `PHASE_6_TASKS.md` §10 for the current acceptance gate and `PLAN.md` §8 for the v1.0 ship criteria.

## Environment variables

| Var | Required? | Used for | Without it |
|---|---|---|---|
| `ORGANON_ROOT` | optional | overrides auto-detection (cwd ⇒ ../../..) | falls back to derived path |
| `NCBI_API_KEY` | optional | higher PubMed rate limit (10 r/s vs 3) | unauthenticated PubMed |
| `OPENALEX_API_KEY` | optional | OpenAlex polite-pool access | rate-limited |
| `S2_API_KEY` | optional | Semantic Scholar dedicated rate limit | shared-pool 429s |
| `CLAUDE_BIN` | optional | overrides `claude` binary path | `claude` from PATH |

Read from the Organon repo's `.env` — no separate dashboard env file.

## Smoke test

After `npm run dev` is up:

1. Home renders, project picker shows ≥ 1 project.
2. Click `/lit` → SearchBar visible.
3. Type a query → ≥ 5 paper cards in ≤ 30s.
4. Click a card → drawer slides in. `Esc` closes it.
5. Click `Save` on 3 cards → `ls projects/{slug}/papers/` shows 3 JSON files.
6. Click `Export BibTeX` → file downloads, parses cleanly.
7. `Cmd+K` opens palette.

If any step fails, see PHASE_1_TASKS.md §9.5 (Common failure modes).

## Layout

```
src/
├── app/                 # routes
│   ├── api/             # JSON + SSE handlers
│   └── {workspace}/     # one folder per sidebar link
├── components/
│   ├── shell/           # sidebar, topbar, palette
│   └── lit/             # /lit-specific components
└── lib/
    ├── artifacts/       # _artifact protocol parser/persist/render
    ├── lit/             # search + library + bibtex helpers
    └── *.ts             # ports of AgenticOS dashboard's lib/
```
