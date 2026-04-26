# BibTeX Format Reference

## Entry Types

### Journal Articles (`@article`)
Use when the paper has a `journal` field (published in a peer-reviewed journal).

```bibtex
@article{Smith2024,
  title     = {{A Novel Approach to Gene Expression Analysis}},
  author    = {Smith, John and Doe, Jane and Zhang, Wei},
  journal   = {Nature Methods},
  year      = {2024},
  doi       = {10.1038/s41592-024-00001-0},
  url       = {https://doi.org/10.1038/s41592-024-00001-0},
}
```

### arXiv Preprints (`@misc`)
Use when the paper has an arXiv ID but no journal (preprint not yet published).

```bibtex
@misc{Johnson2024,
  title         = {{Transformer Models for Protein Structure Prediction}},
  author        = {Johnson, Alice and Brown, Robert},
  year          = {2024},
  eprint        = {2401.12345},
  archiveprefix = {arXiv},
  primaryclass  = {q-bio.BM},
}
```

### Conference Papers (`@inproceedings`)
Use when the paper has a `booktitle` field (presented at a conference).

```bibtex
@inproceedings{Lee2023,
  title     = {{Efficient Sampling Methods for Single-Cell RNA-seq}},
  author    = {Lee, Min-Ho and Park, Soo-Jin},
  booktitle = {Proceedings of ISMB 2023},
  year      = {2023},
  doi       = {10.1093/bioinformatics/btad001},
  url       = {https://doi.org/10.1093/bioinformatics/btad001},
}
```

## Citation Key Generation

1. Take the first author's last name + publication year
2. Normalize the last name:
   - Strip diacritics (accented characters to ASCII equivalents)
   - Remove spaces and hyphens within the name
   - Capitalize first letter, lowercase rest
3. On collision (same key already exists in .bib file): append lowercase letter suffix
   - First occurrence: `Smith2024`
   - Second: `Smith2024a`
   - Third: `Smith2024b`

**Examples:**
- John Smith, 2024 -> `Smith2024`
- Anna van der Berg, 2023 -> `VanDerBerg2023`
- Sean O'Brien, 2024 (first) -> `OBrien2024`
- Sean O'Brien, 2024 (second) -> `OBrien2024a`
- Jose Garcia-Lopez, 2023 -> `GarciaLopez2023`

## LaTeX Special Character Escaping

Apply these escapes to title and author fields before writing BibTeX:

| Character | Escape |
|-----------|--------|
| `&` | `\&` |
| `%` | `\%` |
| `#` | `\#` |
| `_` | `\_` |
| `{` | `\{` |
| `}` | `\}` |
| `~` | `\textasciitilde{}` |
| `^` | `\textasciicircum{}` |

**Note:** Do NOT escape characters inside the outer `{}` delimiters of BibTeX field values -- only escape characters that are part of the actual text content (titles, author names).

## Field Mapping from PaperResult

| BibTeX Field | Source | Notes |
|-------------|--------|-------|
| `title` | PaperResult.title | Wrap in `{{}}` for capitalization preservation |
| `author` | PaperResult.authors | Join with ` and `, format each as `Last, First` |
| `journal` | PaperResult.journal | Only for @article entries |
| `year` | PaperResult.year | String format |
| `doi` | PaperResult.doi | Strip `https://doi.org/` prefix if present |
| `url` | Derived | `https://doi.org/{doi}` or PaperResult.url |
| `eprint` | Derived from arXiv ID | Only for @misc arXiv entries |
| `archiveprefix` | Literal `arXiv` | Only for @misc arXiv entries |
| `primaryclass` | Derived from arXiv category | Only for @misc arXiv entries |

## Example with Special Characters

```bibtex
@article{Mueller2024,
  title     = {{Single-cell RNA-seq reveals T\&NK cell dynamics in tumor microenvironment}},
  author    = {M{\"u}ller, Hans and O'Connor, Sarah and Garcia-Lopez, Maria},
  journal   = {Cell Reports},
  year      = {2024},
  doi       = {10.1016/j.celrep.2024.001},
  url       = {https://doi.org/10.1016/j.celrep.2024.001},
}
```

## Quotes sidecar (v1)

Every `.bib` emitted by cite mode is paired with a `{bib-stem}.quotes.json`
file in the same directory. It is the **upstream seed** of real source
text consumed by downstream agents (sci-writer, sci-auditor) so they
never fabricate a supporting quote from memory.

### Schema

```json
{
  "version": 1,
  "source": "sci-literature-research cite mode",
  "generated_at": "2026-04-13T10:30:00Z",
  "quotes": [
    {
      "key": "Mali2013",
      "doi": "10.1038/nature12373",
      "candidate_quotes": [
        {
          "text": "RNA-guided Cas9 enables precise editing of the human genome.",
          "source_anchor": "10.1038/nature12373",
          "source_type": "doi",
          "confidence": "abstract"
        }
      ]
    }
  ]
}
```

### Field rules

- `version` — always `1` for the current schema.
- `source` — free-text label identifying the producing skill/mode.
- `quotes[].key` — must match a BibTeX key in the sibling `.bib`.
- `quotes[].candidate_quotes[]` — up to 3 per key. Each quote must include:
  - `text`: verbatim sentence from the abstract or full text. Never paraphrased.
  - `source_anchor`: DOI (e.g. `10.1038/nature12373`) for `source_type: "doi"`, or a Paperclip URL `https://citations.gxl.ai/papers/<doc_id>#L<n>` for `source_type: "paperclip"`.
  - `source_type`: `"doi"` or `"paperclip"`.
  - `confidence`: `"abstract"`, `"full-text"`, or `"title"` (last-resort fallback when no body is available).

### How to write it

Always use `scripts/quotes_ops.py build_quotes_sidecar(entries, bib_path)`
— do not hand-author this file. The helper normalizes sentence splits,
caps candidates per key, and enforces the schema so downstream skills can
trust it without revalidating.

### Downstream contract

- `sci-writer` and `sci-auditor` read `candidate_quotes[].text` when filling
  out their draft `.citations.json` sidecars. They copy — they do not invent.
- The mechanical gate (`verify_ops.py` phase G) enforces that every
  `[@Key]` in a manuscript has a sidecar claim whose `source_anchor` is
  either a valid DOI or a `citations.gxl.ai` Paperclip URL in the
  documented format.
