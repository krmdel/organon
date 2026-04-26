# Paperclip vs Federated Coverage Test

Run date: 2026-04-14 · 6 queries × 2 systems (paperclip CLI + paper-search MCP)

This test directly compares Paperclip (`~/.local/bin/paperclip search`) against the federated `paper-search` MCP (PubMed + arXiv + OpenAlex + Semantic Scholar) across a stratified query set. The results inform the routing rules in `paperclip-routing.md`.

## Results matrix

| # | Query | Type | Paperclip top 5 | Federated top 5–15 | Verdict |
|---|---|---|---|---|---|
| 1 | CRISPR base editing off-target effects | Biomedical, deep | 5 recent preprints + 1 PMC review (2024–25). All directly relevant. Full-text anchors available. | 15 mixed: arXiv ML methods papers + **Zuo 2019 Science (784 cites)** + **Grünewald 2019 Nature (669 cites)** + PMC reviews. | **BOTH** — paperclip missed the field-defining classics. |
| 2 | KRAS G12C inhibitor resistance mechanisms | Biomedical, shallow | 5 biomedical (M1C NSCLC preprint, Dunnett-Kane 2021 PMC, MRTX1133 preprint). | 15+ with **Awad 2021 NEJM (1118 cites)**, **Hallin 2019 Cancer Discovery (1259 cites)**, **Huang 2021 STTT (991 cites)**, Suzuki 2021 Clin Cancer Res. | **Federated wins on seminal canon**; paperclip adds recent preprints. |
| 3 | single-cell RNA-seq tumor heterogeneity | Biomedical, discovery | 5 biomedical (GBCD method preprint, PMC Sci Rep 2019, Front Immunol 2026 lung review, brain tumor preprint). | 15+ with **Tirosh 2016 Science melanoma atlas (5083 cites)**, **Patel 2014 Science GBM (4290 cites)**, **SCENIC Nature Methods 2017 (6675 cites)**, HoneyBADGER Genome Research. | **Federated wins decisively on seminal atlas papers** — paperclip missed them all. |
| 4 | diffusion models for protein design | Cross-disciplinary | 4 biomedical preprints (all-atom discrete diffusion, ESM2 hybrid, AAV capsid). | 15+ with **RFdiffusion Nature 2023 (1723 cites)**, **AlphaFold 3 Nature 2024 (12008 cites)**, Luo 2022 antibody diffusion. | **Federated wins decisively** — paperclip missed RFdiffusion and AlphaFold 3, the two landmark papers. |
| 5 | transformer attention interpretability | Non-biomedical (pure ML) | 4 biomedical-adjacent (genomic transformer, BERTology-meets-biology, rs-fMRI epilepsy, sentiment). Tangential for pure ML query. | 15 pure ML interpretability (**Chefer 2021 CVPR**, **Hao 2021 AAAI self-attention attribution**, Transformer Interpretability Beyond Attention Visualization). | **Federated wins decisively** — paperclip cannot serve non-biomedical queries. |
| 6 | gravitational wave detection binary black holes | Non-biomedical (physics) | 5 with **massive noise**: a termite paper about *acoustic* black holes in wood, an Antarctic cryoconite metabolomics paper. Only 2–3 partially relevant physics hits. | 15+ pure physics/astronomy (primordial black holes, supermassive BHs, PTA follow-up). | **Federated wins decisively** — paperclip returned keyword-collision noise. **Paperclip is actively harmful here.** |

## Key findings

### 1. Paperclip ≠ complete replacement for biomedical search
For biomedical queries, Paperclip and federated search are **complementary, not redundant**:
- Paperclip's hybrid BM25+vector ranking surfaces *recent, lexically-close* papers (especially bioRxiv/medRxiv preprints that federated sources lag on).
- OpenAlex's citation-count ranking surfaces the *seminal high-citation canon* that Paperclip's ranking misses.
- Overlap between the two result sets is small (estimated 0–10% across tested queries).

**Implication:** For any biomedical discovery / review task, run **both, deduplicate by DOI**. Neither alone is sufficient.

### 2. Paperclip is biomedical-only — non-biomedical queries return noise
On Q5 (transformer attention interpretability), Paperclip returned only biomedical-adjacent transformer papers, missing the actual interpretability canon. On Q6 (gravitational waves), Paperclip returned a termite paper about "acoustic black holes in wood" and an Antarctic metabolomics paper via pure keyword overlap. These are not edge cases — they're what happens whenever Paperclip is asked something outside its corpus.

**Implication:** For explicitly non-biomedical queries (pure ML/physics/CS/math/econ), **do not query Paperclip at all**. Route straight to federated.

### 3. Paperclip's irreplaceable value is deep capability, not discovery
Paperclip's unique advantages are:
- `grep` sub-second regex across 8M full-text papers
- `map` parallel LLM readers across search results
- `ask-image` figure analysis
- `sql` metadata filtering on the `documents` table
- Full-text section reading, `citations.gxl.ai` line anchors for sidecar quote verification

**None of these are discovery advantages** — they're *capability* advantages that apply *after* you have a paper set. For biomedical systematic reviews and manuscript drafting, the right pattern is:
1. **BOTH** (discover via paperclip + federated, dedupe by DOI)
2. **Paperclip deep ops** (grep/map/ask-image/sql) on the merged set to extract claims with line-anchored citations

## Routing decision (calibrated)

| Query shape | Route | Why |
|---|---|---|
| Biomedical discovery/review | **BOTH**, dedupe by DOI | Paperclip: recency + full-text. Federated: seminal canon. |
| Biomedical deep capability (grep/map/figure/SQL/sections) | **Paperclip only** | Federated can't do these. |
| Biomedical manuscript / systematic review | **BOTH**, then paperclip deep ops on merged set | Missing papers is a failure mode for reviews. |
| Explicitly non-biomedical | **Federated only** | Paperclip returns noise. |
| Cross-disciplinary | **BOTH**, dedupe by DOI | Paperclip for bio side, federated for ML/physics side. |
| Paperclip unreachable | **Federated fallback** | Graceful degradation. |

## How to reproduce

```bash
# Paperclip (CLI)
paperclip search "<query>" -n 5

# Federated (via MCP — load tools first in Claude Code)
# ToolSearch select:mcp__paper-search__search_papers,mcp__paper-search__get_paper_details
# then call mcp__paper-search__search_papers with source="all" max_results=5
```

Compare result sets. Flag DOI overlap. Inspect whether either system missed high-citation papers (OpenAlex citation count is the signal) or recent preprints (bioRxiv/medRxiv dates are the signal).
