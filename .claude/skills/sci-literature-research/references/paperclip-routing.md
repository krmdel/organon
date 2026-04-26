# Paperclip CLI — Routing & Command Catalog

Paperclip is a local CLI binary (`~/.local/bin/paperclip`) that gives Claude Code access to 8M+ full-text biomedical papers from bioRxiv, medRxiv, and PubMed Central. The dedicated `tool-paperclip` skill at `.claude/skills/tool-paperclip/SKILL.md` documents every command in detail.

This file defines **when** to delegate to it from `sci-literature-research` and gives a quick command reference for routing decisions.

---

## When to Route to Paperclip

**Calibrated rule (updated 2026-04-14 after coverage test — see `paperclip-coverage-test.md` for data):**

The coverage test revealed two facts that override any "paperclip-first" intuition:

1. **Paperclip alone misses the biomedical canon.** For "KRAS G12C resistance" it returned recent preprints but missed Awad 2021 NEJM (1118 cites) and Hallin 2019 Cancer Discovery (1259 cites). For "scRNA-seq tumor heterogeneity" it missed Tirosh 2016 Science (5083 cites) and Patel 2014 Science (4290 cites). Paperclip's hybrid search skews toward recent + lexically-close preprints. Federated (via OpenAlex citation-ranking) surfaces the seminal high-citation papers.
2. **Paperclip returns keyword-collision noise on non-biomedical queries.** "Gravitational wave binary black holes" returned a termite paper about "acoustic black holes in wood" and an Antarctic cryoconite metabolomics paper. Paperclip's corpus is strictly biomedical — any non-biomedical query is unsafe.

**Correct routing:**

| Query shape | Route | Why |
|---|---|---|
| **Biomedical discovery/review** (genes, drugs, diseases, clinical, life sciences) | **BOTH**, dedupe by DOI | Paperclip: recency + full-text. Federated: seminal canon via citation ranking. Neither alone is complete. |
| **Biomedical deep capability** (regex grep, `map` across papers, figure analysis, SQL metadata filter, section reading) | **Paperclip only** | Federated can't do these — it's the only reason to use paperclip exclusively. |
| **Biomedical systematic review / manuscript drafting** | **BOTH**, dedupe by DOI, then apply paperclip deep ops on the merged set | Missing papers in a systematic review is a failure mode. Use both upstream, then use paperclip for grounded quotes via `citations.gxl.ai`. |
| **Explicitly non-biomedical** (ML, physics, CS, math, economics with no life-science angle) | **Federated only** | Paperclip returns noise from keyword collisions. Do not query paperclip at all. |
| **Cross-disciplinary** (e.g., "ML for drug discovery", "physics-informed biology") | **BOTH**, dedupe by DOI | Paperclip covers biomedical side, federated (via arXiv) covers ML/physics side. |
| **Paperclip unreachable** | **Federated fallback** | Graceful degradation, tell the user. |

**Biomedical signal detection (for routing decision):**
- Mentions: genes, proteins, pathways, diseases, drugs, MeSH terms, clinical trials, cell types, organisms, biomarkers, techniques (CRISPR, scRNA-seq, IHC, mass spec, AlphaFold), anatomy, physiology, pharmacology
- Author affiliations in life sciences
- Topic categorized under biology, medicine, biochemistry, pharmacology, immunology, neuroscience, genetics, molecular biology, clinical research
- **Ambiguous case → BOTH, dedupe by DOI.** Cheap insurance.

**Why "BOTH, dedupe by DOI" is the default for biomedical:**
- Paperclip's advantage: most recent preprints, full-text grep/map/figure/SQL capability, line-anchored `citations.gxl.ai` URLs
- Federated (OpenAlex) advantage: citation-count ranking surfaces the seminal/landmark papers, cross-disciplinary arXiv coverage
- The overlap is small; the complement is valuable; dedupe is cheap (one hash lookup per DOI)

---

## Paperclip Command Quick Reference

Full docs in `.claude/skills/tool-paperclip/SKILL.md`. Brief summary for routing:

| Command | Use case | Example |
|---------|----------|---------|
| `paperclip search "query"` | Discovery (hybrid BM25 + vector) | `paperclip search "CRISPR Cas9 off-target T cells" -n 20` |
| `paperclip search --since 30d` | Recent biomedical papers only | `paperclip search "AlphaFold" --since 30d` |
| `paperclip grep "regex" /papers/` | Sub-second corpus regex | `paperclip grep "CD8\+ T cells.*exhaustion" /papers/` |
| `paperclip lookup doi <DOI>` | Look up by DOI | `paperclip lookup doi 10.1101/2024.01.15.575613` |
| `paperclip lookup pmc <ID>` | Look up by PMC ID | `paperclip lookup pmc PMC7194329` |
| `paperclip sql "SELECT ..."` | Metadata filtering on `documents` | `paperclip sql "SELECT title, doi FROM documents WHERE journal_title='Nature Methods' AND pub_year=2024 LIMIT 10"` |
| `paperclip cat /papers/<id>/meta.json` | Read paper metadata | `paperclip cat /papers/PMC10791696/meta.json` |
| `paperclip ls /papers/<id>/sections/` | List section files | `paperclip ls /papers/PMC10791696/sections/` |
| `paperclip ask-image <id>/figures/<file> "question"` | Vision analysis of a figure | `paperclip ask-image PMC10791696/figures/fig2.tif "What does this western blot show?"` |
| `paperclip map "question"` | LLM reader across last search results | `paperclip map "What sample sizes were used?"` |
| `paperclip pull <id>` | Download a full paper locally | `paperclip pull PMC10791696` |

**Important: Use `paperclip` directly, not `paperclip bash 'cat ...'`.** Only use `paperclip bash '...'` when you need pipes or `> /.gxl/` redirection.

---

## Display Format for Paperclip Results

Format the same as federated search results, but add a `[Paperclip]` source badge:

```
[N]. **Title** (Year) [Paperclip]
Authors (first 3, then "et al.")
Journal | DOI: 10.xxxx/yyyyy
> Snippet from search result
```

For grep results, show the matched line in context with the doc_id:

```
[N]. **Title** — match in {section}
> ...context line containing the regex match...
doc_id: PMC10791696
```

---

## Citations from Paperclip

**MUST use the `citations.gxl.ai` URL format.** Each cited claim needs a numbered marker `[1]`, `[2]`, etc. and a REFERENCES block at the end:

```
--------
REFERENCES

[1] Authors. "Title." *Journal* vol, pages (year). doi:XX.XXXX/XXXXXXX
    https://citations.gxl.ai/papers/<doc_id>#L<line1>,L<line2>
```

- `<doc_id>` = the directory name under `/papers/` (e.g. `PMC10791696`, `bio_214f7ec77685`)
- Line numbers come from `L<n>` prefixes in `content.lines`
- Single line: `#L45` — range: `#L45-L52` — multiple: `#L45,L120,L210`
- Get authors/title/DOI/date from `meta.json`
- Use Nature citation style (Authors. "Title." *Journal* vol, pages (year). doi:XXXX)

The full citation contract is in `tool-paperclip/SKILL.md` § Citations — read that section before generating any references.

---

## Combining Paperclip + Federated Search

For queries that span biomedical AND non-biomedical (e.g., "computational drug discovery using transformers"):
1. `paperclip search "biomedical aspect"` for depth in life sciences
2. `search_papers` (federated MCP) for cross-disciplinary coverage (catches arXiv ML papers Paperclip misses)
3. Deduplicate by DOI when merging
4. Add source badges showing where each paper came from

---

## Graceful Degradation

If `paperclip` CLI fails, isn't authenticated, or returns no results, fall back to federated search and tell the user:

> "Paperclip didn't return results — using federated search across PubMed, arXiv, OpenAlex, and Semantic Scholar instead."

Never block work because Paperclip is unavailable.
