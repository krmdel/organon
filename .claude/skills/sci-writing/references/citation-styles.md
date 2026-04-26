# Citation Style Guide

Reference for formatting citations in the four most common scientific citation styles. Used by the sci-writing skill when formatting citations from .bib files.

---

## Citation Marker Format

When drafting manuscripts, use these markers for citations that will be formatted later:

- **Single citation:** `[@Key]` -- e.g., `[@Smith2024]`
- **Multiple citations:** `[@Key1; @Key2]` -- e.g., `[@Smith2024; @Doe2023]`
- **Narrative citation:** `@Key` inline -- e.g., `@Smith2024 demonstrated that...`

Key matching is **case-insensitive** against .bib entry keys. When no exact match is found, the formatter suggests the closest matching key (Levenshtein distance).

---

## APA 7th Edition

The most common style in psychology, education, and social sciences. Increasingly used in biomedical research.

### In-Text Citations

| Authors | Parenthetical | Narrative |
|---------|---------------|-----------|
| 1 author | (Smith, 2024) | Smith (2024) reported... |
| 2 authors | (Smith & Doe, 2024) | Smith and Doe (2024) found... |
| 3+ authors | (Smith et al., 2024) | Smith et al. (2024) showed... |

**Multiple citations:** Alphabetical by first author, separated by semicolons.
- (Doe, 2023; Lee, 2024; Smith, 2024)

**Same author, same year:** Add lowercase letter suffix.
- (Smith, 2024a, 2024b)

**Page numbers (direct quotes):** (Smith, 2024, p. 42) or (Smith, 2024, pp. 42-45)

### Bibliography Entry Formats

**Journal article:**
```
Author, A. A., & Author, B. B. (Year). Title of article. *Journal Name*, *Volume*(Issue), Pages. https://doi.org/xxx
```

**Rules:**
- Authors: Last, F. M. format -- list ALL authors (no et al. in reference list)
- Use ampersand (&) before the final author
- Only the first word of the title is capitalized (plus proper nouns)
- Journal name: italicized, title case
- Volume: italicized; issue in parentheses, not italicized
- DOI as full URL (https://doi.org/...)
- Hanging indent (0.5 inch)

**Book:**
```
Author, A. A. (Year). *Title of book* (Edition). Publisher. https://doi.org/xxx
```

**Conference paper:**
```
Author, A. A. (Year, Month Day-Day). Title of presentation [Type]. Conference Name, Location. https://doi.org/xxx
```

**Preprint:**
```
Author, A. A. (Year). Title of preprint. *Repository Name*. https://doi.org/xxx
```

### Example Bibliography

```
Doe, J. A., & Lee, M. (2023). Single-cell approaches to understanding tumor heterogeneity. *Nature Reviews Cancer*, *23*(4), 241-258. https://doi.org/10.1038/s41568-023-00001-0

Smith, J., Doe, J. A., & Zhang, W. (2024). A novel approach to gene expression analysis. *Nature Methods*, *21*(2), 112-125. https://doi.org/10.1038/s41592-024-00001-0
```

---

## Nature

Used by Nature family journals. Numeric citation style with concise bibliography format.

### In-Text Citations

**Superscript numbers** in order of first appearance:

- Single: ... as reported previously^1^.
- Multiple: ... consistent with prior work^1,2^.
- Range: ... well-established findings^1-3^.

**Alternative rendering (markdown-safe):** Use bracketed numbers when superscript is unavailable: [1], [1,2], [1-3].

**Numbering rule:** Assigned sequentially as they appear in the text. First cited = 1, second = 2, etc. Re-use the same number for subsequent citations of the same source.

### Bibliography Entry Formats

**Journal article:**
```
N. Author, A. A., Author, B. B. & Author, C. C. Title of article. *Journal* **Volume**, Pages (Year).
```

**Rules:**
- Number prefix matching in-text order
- Authors: Last, F. F. format, comma separated, ampersand before last
- Title: sentence case (capitalize first word only + proper nouns)
- Journal name: italicized, abbreviated per ISO 4
- Volume: bold
- Year in parentheses at end
- No DOI in print format (include for online-only)

**Book:**
```
N. Author, A. A. *Title of Book* (Publisher, Year).
```

### Example Bibliography

```
1. Smith, J., Doe, J. A. & Zhang, W. A novel approach to gene expression analysis. *Nat. Methods* **21**, 112-125 (2024).
2. Doe, J. A. & Lee, M. Single-cell approaches to understanding tumor heterogeneity. *Nat. Rev. Cancer* **23**, 241-258 (2023).
```

---

## IEEE

Used in engineering, computer science, and technology journals. Numeric citation style with distinct formatting.

### In-Text Citations

**Square brackets** with numbers in order of first appearance:

- Single: ... as described in [1].
- Multiple (non-consecutive): ... prior methods [1], [3], [5].
- Range (consecutive): ... established techniques [1]-[3].

**Numbering rule:** Same as Nature -- sequential by first appearance. Re-use numbers for repeated citations.

### Bibliography Entry Formats

**Journal article:**
```
[N] F. A. Last and F. A. Last, "Title of article," *Journal*, vol. X, no. Y, pp. Z-Z, Month Year, doi: xxx.
```

**Rules:**
- Number in square brackets
- Authors: initials first, then last name (F. A. Last)
- "and" between last two authors (not ampersand)
- Title in double quotes, sentence case
- Journal name: italicized, abbreviated
- Include vol., no., pp. when available
- Month and year
- doi without URL prefix

**Conference paper:**
```
[N] F. A. Last, "Title of paper," in *Proc. Conference Name*, City, Country, Year, pp. Z-Z.
```

**Book:**
```
[N] F. A. Last, *Title of Book*, Edition. City, Country: Publisher, Year.
```

### Example Bibliography

```
[1] J. Smith, J. A. Doe, and W. Zhang, "A novel approach to gene expression analysis," *Nat. Methods*, vol. 21, no. 2, pp. 112-125, Feb. 2024, doi: 10.1038/s41592-024-00001-0.
[2] J. A. Doe and M. Lee, "Single-cell approaches to understanding tumor heterogeneity," *Nat. Rev. Cancer*, vol. 23, no. 4, pp. 241-258, Apr. 2023, doi: 10.1038/s41568-023-00001-0.
```

---

## Vancouver

Used in biomedical and health sciences journals. Similar to IEEE but with distinct author formatting. Required by ICMJE-compliant journals.

### In-Text Citations

**Parenthetical numbers** in order of first appearance:

- Single: ... as reported previously (1).
- Multiple (non-consecutive): ... prior studies (1,3,5).
- Range (consecutive): ... well-documented findings (1-3).

**Numbering rule:** Sequential by first appearance, same as Nature and IEEE.

### Bibliography Entry Formats

**Journal article:**
```
N. Last F, Last F. Title of article. Journal. Year;Volume(Issue):Pages. doi: xxx
```

**Rules:**
- Number followed by period
- Authors: Last name then initials with NO periods (Last F, not Last, F.)
- List up to 6 authors, then "et al."
- No italics on journal name
- Journal abbreviated per MEDLINE/Index Medicus
- Semicolon after year
- Colon before page numbers
- Period at end

**Book:**
```
N. Last F, Last F. Title of book. Edition. Place: Publisher; Year.
```

**Conference paper:**
```
N. Last F. Title of paper. In: Editor F, editor. Title of proceedings; Year Month Day; City, Country. Place: Publisher; Year. p. Pages.
```

### Example Bibliography

```
1. Smith J, Doe JA, Zhang W. A novel approach to gene expression analysis. Nat Methods. 2024;21(2):112-125. doi: 10.1038/s41592-024-00001-0
2. Doe JA, Lee M. Single-cell approaches to understanding tumor heterogeneity. Nat Rev Cancer. 2023;23(4):241-258. doi: 10.1038/s41568-023-00001-0
```

---

## Style Selection Guide

| Field / Journal Family | Recommended Style |
|------------------------|-------------------|
| Psychology, Education, Social Sciences | APA 7th |
| Nature, Science, Cell family journals | Nature |
| IEEE Transactions, ACM, CS conferences | IEEE |
| Medical journals (NEJM, Lancet, BMJ, JAMA) | Vancouver |
| Multidisciplinary (PNAS, PLOS ONE) | Check journal guidelines (usually Nature or Vancouver) |

When the user does not specify a style, ask. If they specify a journal name instead of a style, map it to the correct style using this table or the journal's author guidelines.

---

## Quick Comparison

| Feature | APA 7th | Nature | IEEE | Vancouver |
|---------|---------|--------|------|-----------|
| In-text format | (Author, Year) | Superscript number | [Number] | (Number) |
| Author list | All authors | All authors | All authors | Up to 6, then et al. |
| Title case | Sentence case | Sentence case | Sentence case | Sentence case |
| Journal format | Italic, full name | Italic, abbreviated | Italic, abbreviated | Plain, abbreviated |
| Volume format | Italic | Bold | vol. X | Plain |
| DOI format | Full URL | Optional | doi: xxx | doi: xxx |
| Ordering | Alphabetical by author | Order of appearance | Order of appearance | Order of appearance |
