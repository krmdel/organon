/**
 * Artifact protocol — typed schemas matching PHASE_1_TASKS.md §5 + PHASE_2_TASKS.md §5.
 *
 * Skills emit one JSON line per artifact on stdout:
 *   {"_artifact":"paper", ...PaperArtifact}
 *
 * The dashboard parses these out of SSE streams and persists them to disk.
 */

export type ArtifactDiscriminator =
  | "paper"
  | "project"
  | "hypothesis"
  | "persona-critique"
  | "figure"
  | "dataframe"
  | "stat-result"
  | "section-draft"
  | "section-diff";

export interface PaperArtifact {
  _artifact: "paper";
  schema_version: 1;
  id: string;
  source_ids: {
    pmid?: string | null;
    arxiv?: string | null;
    openalex?: string | null;
    s2?: string | null;
    paperclip?: string | null;
    doi?: string | null;
  };
  title: string;
  authors: string[];
  year: number;
  journal?: string;
  abstract: string;
  url: string;
  doi_url?: string | null;
  pdf_url?: string | null;
  citation_count?: number | null;
  sources: ("pubmed" | "arxiv" | "openalex" | "semanticscholar" | "paperclip")[];
  code?: {
    available: boolean;
    github_url?: string;
  };
  library_path: string;
  saved_at?: string | null;
  tags?: string[];
  notes?: string;
  /**
   * Phase 3 (fix-sprint): surname-based citation key, e.g. "Shah2026" or
   * "Hubert2026b" (collision-suffix). Computed at savePaper time so the
   * BibTeX export, draft `\cite{<key>}` resolution, and bibliography
   * rendering all share the same handle.
   *
   * Optional + nullable so legacy papers (pre-Phase-3) parse correctly;
   * the backfill script (`scripts/backfill-papers.mjs`) populates this
   * field idempotently.
   */
  cite_key?: string | null;

  /**
   * Phase 38 (v1.4) — F1 group-by-search-batch.
   *
   * Stamped on entries added through addPapersToLibrary so the library
   * panel can group papers by which search call produced them.
   * Optional + nullable: legacy entries (pre-Phase-38) read as null
   * and render under the "Ungrouped" bucket. NEVER write back.
   */
  search_batch_id?: string | null;
  search_batch_query?: string | null;
  search_batch_added_at?: string | null;

  /**
   * Phase 47 (v1.6) — F10: relevance confidence score in [0, 1].
   *
   * Computed by `scoreRelevance(query, paper)` (lib/lit/relevance.ts) at
   * search time using IDF-weighted overlap on title (weight 0.4) +
   * abstract (weight 0.6). Optional + nullable: legacy paper artifacts
   * pre-Phase-47 read as null/undefined and render without the chip.
   * NEVER persisted on save (the score is per-query, not per-paper).
   */
  relevance_score?: number | null;
  relevance_breakdown?: { title: number; abstract: number } | null;
}

export interface ProjectArtifact {
  _artifact: "project";
  schema_version: 1;
  slug: string;
  name: string;
  path: string;
  is_root: boolean;
  is_brief: boolean;
  brief?: {
    status?: string;
    level?: number;
    created?: string;
  };
  papers_count?: number;
  last_modified?: string;
}

export type HypothesisStatus =
  | "open"
  | "synthesized"
  | "supported"
  | "refuted"
  | "archived";

/**
 * PHASE_2_TASKS.md §5.1 — hypothesis record.
 * On disk at: projects/{slug}/hypotheses/{id}/hypothesis.json
 */
export interface HypothesisArtifact {
  _artifact: "hypothesis";
  schema_version: 1;
  id: string;
  claim: string;
  claim_short?: string;
  project_slug: string;
  status: HypothesisStatus;
  paper_ids: string[];
  personas_used: string[];
  critique_files: string[];
  synthesis_text?: string | null;
  open_questions?: string[];
  experiment_design?: Record<string, unknown> | null;
  council_confidence?: "high" | "medium" | "low" | null;
  tags?: string[];
  notes?: string;
  /**
   * Phase 43 (v1.5) — F6 per-persona discard.
   *
   * Persona slugs the user has chosen to exclude from this hypothesis's
   * synthesis. Optional + read-time backfilled to []. Discard is
   * REVERSIBLE — the persona's critique stays on disk; reconcile just
   * filters it out of the synthesis prompt. Scope is the hypothesis,
   * not the project.
   */
  excluded_persona_ids?: string[];
  /**
   * Phase 48 (v1.6) — F11 per-persona deep-research.
   *
   * Map from persona slug → list of paper artifacts that the persona's
   * deep-research run pulled in. Optional + read-time backfilled to {}.
   * Stored as PaperArtifact[] (the same shape as library entries) so
   * the workspace can render them via the existing PaperCard surface.
   *
   * Deduplicate ACROSS personas at render time, not at write time —
   * the same paper can land in all three persona buckets and the panel
   * wants to badge it with each persona that pulled it in.
   */
  additional_papers_by_persona?: Record<string, PaperArtifact[]> | null;
  created_at: string;
  updated_at: string;
  library_path: string;
}

/**
 * PHASE_2_TASKS.md §5.2 — persona critique sidecar.
 * On disk at: projects/{slug}/hypotheses/{hyp_id}/critiques/{persona_slug}.json
 */
export interface PersonaCritiqueArtifact {
  _artifact: "persona-critique";
  schema_version: 1;
  hypothesis_id: string;
  persona: string;
  persona_slug: string;
  confidence: "high" | "medium" | "low";
  critiques: string[];
  counter_evidence: string[];
  suggested_experiments: string[];
  raw_council_block?: string;
  supporting_paper_ids?: string[];
  library_path: string;
  created_at: string;
}

/**
 * PHASE_3_TASKS.md §5.1 — dataframe preview emitted on file upload + load.
 * On disk at: projects/{slug}/data/{file_id}.preview.json
 */
export type ColumnType = "numeric" | "categorical" | "datetime" | "text";

export interface NumericColumnStats {
  count: number;
  mean: number;
  std: number;
  min: number;
  max: number;
}

export interface CategoricalColumnStats {
  unique_count: number;
  top: [string, number][];
}

export interface DatetimeColumnStats {
  count: number;
  min: string;
  max: string;
}

export interface TextColumnStats {
  count: number;
  unique_count?: number;
  avg_length?: number;
}

export type ColumnStats =
  | NumericColumnStats
  | CategoricalColumnStats
  | DatetimeColumnStats
  | TextColumnStats;

export interface DataframeColumn {
  name: string;
  type: ColumnType;
  type_inferred_by: "auto" | "user-override";
  null_count: number;
  stats: ColumnStats;
}

export interface DataframeArtifact {
  _artifact: "dataframe";
  schema_version: 1;
  id: string;
  project_slug: string;
  filename: string;
  format: "csv" | "xlsx" | "json" | "parquet";
  size_bytes: number;
  rows_total: number;
  columns: DataframeColumn[];
  preview_rows: Record<string, string>[];
  data_path: string;
  preview_path: string;
  uploaded_at: string;
  library_path: string;
}

/**
 * PHASE_3_TASKS.md §5.2 — stat-test result emitted by sci-data-analysis
 * (analyze mode) and sci-hypothesis (validate / power modes).
 * On disk at: projects/{slug}/results/{run_id}.json
 */
export type StatResultMode = "analyze" | "power" | "validate";
export type AssumptionVerdict = "pass" | "warn" | "fail";

export interface AssumptionCheck {
  name: string;
  verdict: AssumptionVerdict;
  p_value?: number;
  note?: string;
}

export interface EffectSize {
  name: string;
  value: number;
  ci_low?: number;
  ci_high?: number;
}

export interface StatResultArtifact {
  _artifact: "stat-result";
  schema_version: 1;
  id: string;
  project_slug: string;
  file_id: string | null;
  test_name: string;
  test_label: string;
  mode: StatResultMode;
  params: Record<string, unknown>;
  test_statistic?: number | null;
  p_value: number | null;
  effect_size?: EffectSize | null;
  n: number;
  assumption_checks?: AssumptionCheck[];
  interpretation: string;
  code_path?: string | null;
  results_path: string;
  library_path: string;
  created_at: string;
  /**
   * Phase 12a (v1.0.1) — soft-archive flag. False/undefined for active
   * results that render in the workspace; true when the researcher × the
   * card. The result file stays on disk; list views filter it out unless
   * the "Show N archived" toggle is on. No hard-delete path for v1.0.1.
   */
  archived?: boolean;
  archived_at?: string | null;
}

/**
 * PHASE_3_TASKS.md §5.3 — figure record emitted on plot generation.
 * Phase 3 covers v1 (matplotlib/seaborn plots from sci-data-analysis).
 * Phase 4 will add image generation backends + version chains.
 * On disk at: projects/{slug}/figures/{fig_id}/v{n}.{png|svg|py}
 */
export type FigureKind = "plot" | "image";
export type FigureBackend =
  | "matplotlib"
  | "seaborn"
  | "gemini"
  | "fal-flux-fill";

export interface FigureArtifact {
  _artifact: "figure";
  schema_version: 1;
  id: string;
  project_slug: string;
  kind: FigureKind;
  version: number;
  format: "png" | "svg" | "jpg";
  data_source: string | null;
  params: Record<string, unknown>;
  caption?: string | null;
  alt_text?: string | null;
  code_path?: string | null;
  png_path: string;
  svg_path?: string | null;
  thumbnail_path?: string | null;
  library_path: string;
  backend: FigureBackend;
  cost_cents: number;
  parent_version?: number | null;
  /** Phase 4 — only present when version ≥ 2 (region inpaint applied). */
  mask_path?: string | null;
  /** Phase 4 — true after the user pins this version. Edits disabled while locked. */
  locked?: boolean;
  /** Phase 19 (v1.1+) — multi-paragraph detailed legend, only generated for locked figures. */
  detailed_legend?: string | null;
  /**
   * Phase 24 (v1.2) — legend history. Each regenerate / refine pass
   * appends a versioned entry. Optional + read-time backfilled to `[]`
   * for legacy figures (Persona.active / detailed_legend pattern;
   * Phases 13a / 19). Capped at MAX_LEGEND_HISTORY at the route
   * boundary; older entries drop on append.
   */
  legend_history?: LegendHistoryEntry[];
  created_at: string;
}

/**
 * Phase 24 (v1.2) — legend history entry. Stored on the figure
 * artifact alongside `detailed_legend`. Initial Generate (version 1)
 * does NOT create an entry (too noisy); the strip surfaces from
 * version 2 onward, but the persistence path always appends so a
 * future v1.3 surface could expose v1 too.
 */
export interface LegendHistoryEntry {
  version: number;
  text: string;
  refine_prompt?: string | null;
  created_at: string;
}

/**
 * PHASE_5_TASKS.md §5.1 — manuscript section payload.
 * On disk at: projects/{slug}/manuscripts/{manuscript_slug}/sections/{section_id}.md
 * The .md content is canonical; this artifact is the metadata shell.
 */
export type SectionType =
  | "title"
  | "abstract"
  | "introduction"
  | "methods"
  | "results"
  | "discussion"
  | "references"
  | "custom";

export type SectionStatus = "draft" | "reviewed" | "final";

export interface SectionDraftArtifact {
  _artifact: "section-draft";
  schema_version: 1;
  id: string;
  manuscript_slug: string;
  section_id: string;
  section_type: SectionType;
  status: SectionStatus;
  content_md: string;
  linked_figure_ids?: string[];
  linked_paper_ids?: string[];
  /**
   * Phase 51 (v2.0) — Per-section linkage overrides. When non-empty,
   * the section narrows the corresponding artifact pool BEFORE
   * generation runs (one level finer than Phase 41's manuscript-wide
   * linkage). Empty (or undefined post-backfill) → fall back to
   * manuscript.linked_*_ids; if that's also empty → use everything.
   *
   * Distinct from `linked_paper_ids` / `linked_figure_ids` above which
   * track cite-keys/fig-ids that the section's content currently uses
   * (computed from extractRefs at write time). Overrides are intent;
   * the existing fields are derived state.
   */
  override_linked_paper_ids?: string[];
  override_linked_figure_ids?: string[];
  override_linked_hypothesis_ids?: string[];
  override_linked_dataset_ids?: string[];
  version: number;
  library_path: string;
  updated_at: string;
}

/** PHASE_5_TASKS.md §5.2 — transient diff. NOT persisted. */
export type SectionAction = "rewrite" | "tighten" | "check" | "humanize";

export interface SectionDiffArtifact {
  _artifact: "section-diff";
  schema_version: 1;
  manuscript_slug: string;
  section_id: string;
  action: SectionAction;
  before: string;
  after: string;
  rationale: string;
  warnings?: string[];
}

/** Phase 6+ types declared so the parser can ignore-with-warn rather than crash. */
export interface UnknownArtifact {
  _artifact: Exclude<
    ArtifactDiscriminator,
    | "paper"
    | "project"
    | "hypothesis"
    | "persona-critique"
    | "dataframe"
    | "stat-result"
    | "figure"
    | "section-draft"
    | "section-diff"
  >;
  schema_version: number;
  [key: string]: unknown;
}

export type Artifact =
  | PaperArtifact
  | ProjectArtifact
  | HypothesisArtifact
  | PersonaCritiqueArtifact
  | DataframeArtifact
  | StatResultArtifact
  | FigureArtifact
  | SectionDraftArtifact
  | SectionDiffArtifact
  | UnknownArtifact;
