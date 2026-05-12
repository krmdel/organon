# Phase 3 artifact protocol — golden examples

Reference fixtures for the three new `_artifact` discriminators introduced in Phase 3. Schemas are locked in `PHASE_3_TASKS.md` §5; this file is the runnable companion.

The smoke test at `tests/parser-phase3.test.mjs` parses each fenced JSON block below and asserts the parser narrows it to the right artifact type.

---

## `_artifact: dataframe`

```json
{"_artifact":"dataframe","schema_version":1,"id":"data-20260520-9fa321","project_slug":"drug-discovery-llm-eval","filename":"patient_data.csv","format":"csv","size_bytes":487213,"rows_total":1247,"columns":[{"name":"age","type":"numeric","type_inferred_by":"auto","null_count":12,"stats":{"count":1235,"mean":54.2,"std":12.7,"min":18,"max":89}},{"name":"treatment","type":"categorical","type_inferred_by":"auto","null_count":0,"stats":{"unique_count":3,"top":[["control",624],["drug-a",311],["drug-b",312]]}}],"preview_rows":[{"id":"1","age":"54","treatment":"control","outcome":"responder"}],"data_path":"projects/drug-discovery-llm-eval/data/data-20260520-9fa321.csv","preview_path":"projects/drug-discovery-llm-eval/data/data-20260520-9fa321.preview.json","uploaded_at":"2026-05-20T10:23:00.000Z","library_path":"projects/drug-discovery-llm-eval/data/data-20260520-9fa321.preview.json"}
```

## `_artifact: stat-result`

```json
{"_artifact":"stat-result","schema_version":1,"id":"stat-20260520-1c84ee","project_slug":"drug-discovery-llm-eval","file_id":"data-20260520-9fa321","test_name":"ttest_ind","test_label":"Two-sample t-test (independent)","mode":"analyze","params":{"value_col":"outcome_score","group_col":"treatment","alpha":0.05},"test_statistic":3.42,"p_value":0.00067,"effect_size":{"name":"cohen_d","value":0.41,"ci_low":0.18,"ci_high":0.64},"n":1247,"assumption_checks":[{"name":"normality_shapiro","verdict":"pass","p_value":0.18},{"name":"equal_variance_levene","verdict":"fail","p_value":0.001,"note":"Welch correction applied"}],"interpretation":"Treatment group had higher outcome scores than control (Cohen's d = 0.41, 95% CI [0.18, 0.64], p < 0.001). Effect size is small-to-medium.","code_path":null,"results_path":"projects/drug-discovery-llm-eval/results/stat-20260520-1c84ee.json","library_path":"projects/drug-discovery-llm-eval/results/stat-20260520-1c84ee.json","created_at":"2026-05-20T10:25:00.000Z"}
```

## `_artifact: figure`

```json
{"_artifact":"figure","schema_version":1,"id":"fig-20260520-7e1003","project_slug":"drug-discovery-llm-eval","kind":"plot","version":1,"format":"png","data_source":"data-20260520-9fa321","params":{"plot_kind":"histogram","x_col":"age","bins":30,"log_scale":false},"caption":null,"alt_text":null,"code_path":"projects/drug-discovery-llm-eval/figures/fig-20260520-7e1003/v1.py","png_path":"projects/drug-discovery-llm-eval/figures/fig-20260520-7e1003/v1.png","svg_path":"projects/drug-discovery-llm-eval/figures/fig-20260520-7e1003/v1.svg","thumbnail_path":"projects/drug-discovery-llm-eval/figures/fig-20260520-7e1003/v1.thumb.png","library_path":"projects/drug-discovery-llm-eval/figures/fig-20260520-7e1003/v1.png","backend":"matplotlib","cost_cents":0,"parent_version":null,"created_at":"2026-05-20T10:26:00.000Z"}
```

---

## Invalid fixtures (must NOT parse)

These exercise the parser's tolerance for malformed input. Each MUST return `null` from `parseArtifact`, never throw.

```json
{"_artifact":"dataframe"}
```

```json
{"_artifact":"stat-result","id":42}
```

```json
{"_artifact":"figure","id":"fig-x","project_slug":"p"}
```

Last block above lacks `kind` + `version` — parser narrower must reject.
