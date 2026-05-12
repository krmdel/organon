# Phase 4 artifact protocol — v2 figure golden examples

Phase 4 extends `_artifact: figure` with `mask_path`, `locked`, and `parent_version` populated for inpaint versions. Discriminator + schema_version unchanged. The smoke test at `tests/parser-phase4.test.mjs` parses each fenced JSON block below.

---

## `_artifact: figure` v1 (Gemini text-to-image generate)

```json
{"_artifact":"figure","schema_version":1,"id":"fig-20260601-3a7c91","project_slug":"crispr-cas9-figs","kind":"image","version":1,"format":"png","data_source":null,"params":{"prompt":"schematic of CRISPR Cas9 binding to target DNA","style":"scientific","sub_style":"schematic"},"caption":null,"alt_text":null,"code_path":null,"png_path":"projects/crispr-cas9-figs/figures/fig-20260601-3a7c91/v1.png","svg_path":null,"thumbnail_path":"projects/crispr-cas9-figs/figures/fig-20260601-3a7c91/v1.thumb.png","library_path":"projects/crispr-cas9-figs/figures/fig-20260601-3a7c91/v1.png","backend":"gemini","cost_cents":4,"parent_version":null,"mask_path":null,"locked":false,"created_at":"2026-06-01T14:23:00.000Z"}
```

## `_artifact: figure` v2 (FAL FLUX.1 Pro Fill region inpaint)

```json
{"_artifact":"figure","schema_version":1,"id":"fig-20260601-3a7c91","project_slug":"crispr-cas9-figs","kind":"image","version":2,"format":"png","data_source":null,"params":{"prompt":"make the protein look more like a clamp","style":null,"mask_megapixels":0.42},"caption":null,"alt_text":null,"code_path":null,"png_path":"projects/crispr-cas9-figs/figures/fig-20260601-3a7c91/v2.png","svg_path":null,"thumbnail_path":"projects/crispr-cas9-figs/figures/fig-20260601-3a7c91/v2.thumb.png","library_path":"projects/crispr-cas9-figs/figures/fig-20260601-3a7c91/v2.png","backend":"fal-flux-fill","cost_cents":3,"parent_version":1,"mask_path":"projects/crispr-cas9-figs/figures/fig-20260601-3a7c91/mask/v2.png","locked":false,"created_at":"2026-06-01T14:25:30.000Z"}
```

## `_artifact: figure` v3 locked (sci-writing caption applied)

```json
{"_artifact":"figure","schema_version":1,"id":"fig-20260601-3a7c91","project_slug":"crispr-cas9-figs","kind":"image","version":2,"format":"png","data_source":null,"params":{"prompt":"make the protein look more like a clamp","style":null,"mask_megapixels":0.42},"caption":"Schematic of CRISPR Cas9 binding to target DNA, with the protein rendered as a clamp around the duplex. The PAM site is indicated below the cleavage point.","alt_text":"Diagram of a clamp-shaped Cas9 protein engaging double-stranded DNA at a PAM motif.","code_path":null,"png_path":"projects/crispr-cas9-figs/figures/fig-20260601-3a7c91/v2.png","svg_path":null,"thumbnail_path":"projects/crispr-cas9-figs/figures/fig-20260601-3a7c91/v2.thumb.png","library_path":"projects/crispr-cas9-figs/figures/fig-20260601-3a7c91/v2.png","backend":"fal-flux-fill","cost_cents":0,"parent_version":1,"mask_path":"projects/crispr-cas9-figs/figures/fig-20260601-3a7c91/mask/v2.png","locked":true,"created_at":"2026-06-01T14:27:00.000Z"}
```
