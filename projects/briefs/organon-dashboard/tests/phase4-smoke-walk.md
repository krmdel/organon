# Phase 4 — manual smoke walk (T34)

PHASE_4_TASKS.md §10 acceptance gate. Run after a clean `npm run build` whenever any Phase 4 file changes.

## Prereqs

- `FAL_KEY` set in `.env` (see `.env.example`). Without it, `/api/images/edit` returns 402 with a clear message; generate + lock still work.
- `GEMINI_API_KEY` set (used by `viz-nano-banana`).
- Phase 3 acceptance gate green (the dashboard reuses Phase 3's figure store).

## Setup

```bash
cd projects/briefs/organon-dashboard
bash -lc 'set -a; source ../../../.env 2>/dev/null; set +a; npm run dev'
```

Open http://localhost:8769/figures?project=__root__.

## Walk

1. **Generate** — type "schematic of CRISPR Cas9 binding to target DNA" in the prompt form. Pick `scientific` style, sub-style `schematic`, click **Generate**. **Pass** if the image renders within 30 s and the new figure shows up in the left list. SSE pane shows live skill output during the wait.
2. **Cold canvas** — without picking a tool, the image displays. Mask tools say "View" and the canvas does not capture pointer events.
3. **Lasso edit** — click **Lasso**, drag around the protein region, release. A red translucent fill appears. Type "make this look more like a clamp" in the edit prompt that appears below the canvas. Click **Apply edit**. Cost gate fires showing ~$0.05.
4. **Cost gate** — confirm. **Pass** if v2 lands within ~30 s, the canvas swaps to v2, and the version strip shows v1 + v2 thumbnails.
5. **Cost gate skip** — repeat the lasso + apply, this time tick "Don't ask again this session" before confirm. Subsequent edits skip the modal.
6. **Mask dim mismatch** — manually shrink the mask via devtools (or just rely on the ImageCanvas exporting at source dims) — the route returns 400 with the helpful message ("Mask is X×Y but base is W×H...").
7. **FAL key missing** — temporarily remove `FAL_KEY` from `.env`, restart dev. Apply edit returns 402 with "FAL_KEY missing. Add it to .env". Restore key.
8. **Revert via version strip** — click the v1 thumbnail. Canvas swaps back to v1. Click v2 → forward.
9. **Lock + caption** — with v2 active, click **Lock + caption**. SSE pane shows sci-writing output. **Pass** if the CaptionCard populates with caption + alt text within ~20 s and shows the green `● locked` indicator.
10. **Mask static-file route** — open `http://localhost:8769/api/figures/<fig_id>/mask/v2.png?project=__root__` directly. **Pass** if the mask image renders (white-on-black grayscale).
11. **Cmd+K** — press Cmd+K. **Pass** if the new Figures group lists "Go to Figures", "New figure (prompt)", "Edit current figure region", "Lock current figure + caption". Selecting any navigates to /figures.
12. **No regressions** — visit /lit, /hypothesis, /data. All still functional.

## Gate

**All 12 boxes ticked + `npm run build` exits 0 + `npm test` 11/11 green.**

## Known caveats

- The viz-nano-banana skill invocation through `claude -p` cold-starts ~20-40 s before the first SSE event. UI shows the streaming pane during this wait.
- Cost gate estimates a flat ~$0.05; actual cost reported by FAL after the call lands in the figure sidecar's `cost_cents` field. Session sum in topbar adjusts.
- Mask drawing is rasterised at the source image dimensions, not the displayed dimensions — drawn precision matches what FAL receives.
- T28-T29 (viz-nano-banana --mode edit for direct CLI editing) deferred until a CLI use case surfaces. Dashboard's `/api/images/edit` calls FAL directly via TS instead of going through the skill.
- Pillow thumbnail generation for v2+ uses the FAL response PNG directly without a thumbnail variant; future polish: generate a thumb sidecar via Pillow on the dashboard side.
