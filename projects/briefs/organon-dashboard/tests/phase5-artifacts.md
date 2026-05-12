# Phase 5 artifact protocol — golden examples

Two new discriminators: `section-draft` (persisted under
`projects/{slug}/manuscripts/{ms}/sections/{section_id}.json`) and
`section-diff` (transient — UI-only diff returned by sci-writing /
tool-humanizer; never persisted).

## `_artifact: section-draft`

```json
{"_artifact":"section-draft","schema_version":1,"id":"sect-glp1-meta-analysis-introduction","manuscript_slug":"glp1-meta-analysis","section_id":"introduction","section_type":"introduction","status":"draft","content_md":"## Introduction\n\nGLP-1 receptor agonists are widely used. See \\cite{pmid-37889012}.\n","linked_figure_ids":[],"linked_paper_ids":["pmid-37889012"],"version":1,"library_path":"projects/glp1-meta-analysis/manuscripts/glp1-meta-analysis/sections/introduction.md","updated_at":"2026-06-20T14:23:00.000Z"}
```

## `_artifact: section-diff` (transient)

```json
{"_artifact":"section-diff","schema_version":1,"manuscript_slug":"glp1-meta-analysis","section_id":"introduction","action":"tighten","before":"## Introduction\n\nIn this paper, we will discuss...","after":"## Introduction\n\nWe report...","rationale":"Tightened intro by ~22%; preserved citation order.","warnings":[]}
```

---

## Invalid fixtures (must NOT parse)

```json
{"_artifact":"section-draft","manuscript_slug":"x"}
```

```json
{"_artifact":"section-diff","manuscript_slug":"x","section_id":"y"}
```
