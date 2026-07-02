# assets

Bundled examples and templates for the skill.

## `example/` — a worked reference→output pair

A complete, self-contained demo of the figure-mirror loop. Use it to see what a
well-formed input looks like and what the skill produces.

| File | What it is |
|------|------------|
| `reference.png` | The L1 **style anchor** — a two-series line+marker figure (teal/coral palette, horizontal-only dashed grid, despined, sans type, frameless upper-left legend). |
| `data.csv` | The user's **different** data (`epoch, ResNet, ViT`, 8 rows) — a separate study, not the reference's numbers. |
| `figure.py` | The skill's output: a self-contained matplotlib script (inline DATA SECTOR, `pdf.fonttype = 42`) rendering `data.csv` in the reference's visual register. Run it: `python3 figure.py`. |
| `figure.png` | The rendered result — the user's data wearing the reference's style. |
| `comparison.png` | Side-by-side (reference \| output) for a quick read of the match. |

**How it was produced (the loop, end-to-end):** iter 0 cleared the mechanical floor but
the Reviewer returned `close` — it caught a real serif-vs-sans typographic drift (the
serif `PUBLICATION_RCPARAMS` default had overridden the sans reference). iter 1 fixed the
font class while holding the preserve list, and the Reviewer returned `ship`. The output
PDF is Type-42 (camera-ready, copy-pasteable) and the script reads no external file.

This is a demonstration artifact; the skill is fully functional without it.
