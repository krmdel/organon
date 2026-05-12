# Phase 3 — manual smoke walk (T35)

PHASE_3_TASKS.md §10 acceptance gate; mirrors §9.3 dev-setup smoke. Run after a clean `npm run build` whenever any Phase 3 file changes.

## Setup

```bash
cd projects/briefs/organon-dashboard
bash -lc 'set -a; source ../../../.env 2>/dev/null; set +a; npm run dev'
```

Open http://localhost:8769/data?project=__root__.

Use a representative CSV (the team default is `/tmp/sample_data.csv`; any file with ≥ 1 numeric, ≥ 1 categorical, and ≥ 1 datetime-shaped column passes the gate):

```csv
id,age,treatment,outcome_score,recorded_at
1,54,control,0.42,2026-04-01T10:00:00
2,38,drug-a,0.81,2026-04-01T10:05:00
…
```

## Walk

1. **Upload** — drag the CSV onto the drop zone. Preview lands within 5 s. **Pass** if all 5 columns appear with the right type chip (`id` numeric, `age` numeric, `treatment` categorical, `outcome_score` numeric, `recorded_at` datetime).
2. **Override** — click the `treatment` type chip → choose `text`. Preview re-renders within 2 s; chip now reads `text`. Click again → restore to `categorical`.
3. **Stat picker** — click the **Stats** tab. Wizard defaults to "Compare groups" with `outcome_score` + `treatment`. Click **Recommend**. **Pass** if 2 cards land (Welch t-test rank 1, Mann–Whitney rank 2). Each card has a reasoning paragraph + assumption flags (`min_group_n`, `normality_shapiro`, `equal_variance_levene`).
4. **Run a test** — click **Run** on the t-test card. SSE stream pane shows live skill output. **Pass** if a `<StatResultCard>` lands within ~30 s with: test statistic, p-value, n, assumption verdicts, plain-English interpretation. The result also persists to `projects/__root__/results/stat-{date}-{hex}.json` — `cat` it to verify schema.
5. **Plot picker** — click the **Plots** tab. `histogram` is preselected with `x_col=age`, `bins=30`. Click **Generate**. **Pass** if a PNG renders inline within 10 s and a thumbnail appears in History. `ls projects/__root__/figures/fig-{date}-{hex}/` shows v1.png + v1.svg + v1.py + v1.thumb.png.
6. **Copy code** — click **Copy code** on the rendered figure. Paste into a scratch file. **Pass** if the file runs (`python <file>`) and produces an `output.png` matching the dashboard's render.
7. **History** — generate two more plots (e.g. `scatter` + `heatmap`). **Pass** if all three show up in History; clicking each swaps the main canvas.
8. **Cmd+K** — press Cmd+K. **Pass** if the new Data group appears with: "Go to Data · upload", "Run stat test", "Generate plot". Selecting the latter two navigates to /data with the right tab pre-selected.
9. **Sidebar refresh** — click the `↻ figs` and `↻ results` buttons in the sidebar footer. Both lists re-fetch without a page reload.
10. **No regressions** — visit /lit, /hypothesis. Both still load + functional.

## Gate

**All 10 boxes ticked + `npm run build` exits 0 + `npm test` 6/6 green.**

## Known caveats

- Parquet not yet supported (skill / venv don't have pyarrow). Drop a `.parquet` returns 415.
- `/api/data/analyze` goes through `claude -p`; cold start can take 20–40 s before the first SSE event lands.
- The "Cite in draft" button on result cards is a Phase 5 forward-stub, intentionally disabled.
