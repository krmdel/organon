import type {
  Artifact,
  DataframeArtifact,
  FigureArtifact,
  HypothesisArtifact,
  PaperArtifact,
  PersonaCritiqueArtifact,
  ProjectArtifact,
  SectionDiffArtifact,
  SectionDraftArtifact,
  StatResultArtifact,
  UnknownArtifact,
} from "./types";

/**
 * Try to parse a single line as an artifact.
 * Returns null for non-JSON / non-artifact lines so callers can skip them
 * without try/catch noise.
 */
export function parseArtifact(line: string): Artifact | null {
  const trimmed = line.trim();
  if (!trimmed.startsWith("{") || !trimmed.endsWith("}")) return null;
  let obj: unknown;
  try {
    obj = JSON.parse(trimmed);
  } catch {
    return null;
  }
  if (!obj || typeof obj !== "object") return null;
  const a = obj as Record<string, unknown>;
  if (typeof a._artifact !== "string") return null;

  switch (a._artifact) {
    case "paper":
      return narrowPaper(a);
    case "project":
      return narrowProject(a);
    case "hypothesis":
      return narrowHypothesis(a);
    case "persona-critique":
      return narrowPersonaCritique(a);
    case "dataframe":
      return narrowDataframe(a);
    case "stat-result":
      return narrowStatResult(a);
    case "figure":
      return narrowFigure(a);
    case "section-draft":
      return narrowSectionDraft(a);
    case "section-diff":
      return narrowSectionDiff(a);
    default:
      return narrowUnknown(a);
  }
}

/**
 * Scan a chunk of stdout text (which may contain partial lines) and yield
 * complete-line artifacts. Returns leftover text the caller should prepend to
 * the next chunk.
 */
export function extractArtifactsFromChunk(
  buffer: string,
  chunk: string,
): { artifacts: Artifact[]; remainder: string } {
  const combined = buffer + chunk;
  const lines = combined.split("\n");
  const remainder = lines.pop() ?? "";
  const artifacts: Artifact[] = [];
  for (const line of lines) {
    const art = parseArtifact(line);
    if (art) artifacts.push(art);
  }
  return { artifacts, remainder };
}

/**
 * Phase 35 (v1.4) — B2 diagnostic surface.
 *
 * When an SSE route's accumulated stdout contains a literal `_artifact`
 * substring but extractArtifactsFromChunk returned nothing across the
 * full run (whitespace-prefixed JSON, slug-mismatch on the route side,
 * malformed JSON, etc.), the caller passes the accumulated stdout +
 * `anyParsed=false` and gets back a debug payload with ±200 chars of
 * context around the substring. Lets the next walk paste the actual
 * culprit instead of guessing.
 *
 * Returns null when:
 *   - any artifact was successfully parsed (anyParsed=true) — no false alarm
 *   - the `_artifact` substring is not present at all — no signal to surface
 */
export type ParseDebugPayload = {
  reason: "artifact-substring-found-but-not-parsed";
  context: string;
  offset: number;
  length: number;
};

export function diagnoseUnparsedArtifact(
  stdoutAccumulated: string,
  anyParsed: boolean,
): ParseDebugPayload | null {
  if (anyParsed) return null;
  const idx = stdoutAccumulated.indexOf('"_artifact"');
  if (idx < 0) return null;
  const start = Math.max(0, idx - 200);
  const end = Math.min(stdoutAccumulated.length, idx + 200);
  return {
    reason: "artifact-substring-found-but-not-parsed",
    context: stdoutAccumulated.slice(start, end),
    offset: idx,
    length: stdoutAccumulated.length,
  };
}

function narrowPaper(a: Record<string, unknown>): PaperArtifact | null {
  if (typeof a.id !== "string") return null;
  if (typeof a.title !== "string") return null;
  if (!Array.isArray(a.authors)) return null;
  if (typeof a.abstract !== "string") return null;
  if (typeof a.url !== "string") return null;
  if (!Array.isArray(a.sources)) return null;
  return a as unknown as PaperArtifact;
}

function narrowProject(a: Record<string, unknown>): ProjectArtifact | null {
  if (typeof a.slug !== "string") return null;
  if (typeof a.name !== "string") return null;
  if (typeof a.path !== "string") return null;
  return a as unknown as ProjectArtifact;
}

function narrowHypothesis(a: Record<string, unknown>): HypothesisArtifact | null {
  if (typeof a.id !== "string") return null;
  if (typeof a.claim !== "string") return null;
  if (typeof a.project_slug !== "string") return null;
  if (typeof a.status !== "string") return null;
  if (!Array.isArray(a.paper_ids)) return null;
  if (!Array.isArray(a.personas_used)) return null;
  if (!Array.isArray(a.critique_files)) return null;
  return a as unknown as HypothesisArtifact;
}

function narrowPersonaCritique(a: Record<string, unknown>): PersonaCritiqueArtifact | null {
  if (typeof a.hypothesis_id !== "string") return null;
  if (typeof a.persona !== "string") return null;
  if (typeof a.persona_slug !== "string") return null;
  if (!Array.isArray(a.critiques)) return null;
  if (!Array.isArray(a.counter_evidence)) return null;
  if (!Array.isArray(a.suggested_experiments)) return null;
  return a as unknown as PersonaCritiqueArtifact;
}

function narrowDataframe(a: Record<string, unknown>): DataframeArtifact | null {
  if (typeof a.id !== "string") return null;
  if (typeof a.project_slug !== "string") return null;
  if (typeof a.filename !== "string") return null;
  if (typeof a.format !== "string") return null;
  if (typeof a.rows_total !== "number") return null;
  if (!Array.isArray(a.columns)) return null;
  if (!Array.isArray(a.preview_rows)) return null;
  if (typeof a.data_path !== "string") return null;
  if (typeof a.library_path !== "string") return null;
  return a as unknown as DataframeArtifact;
}

function narrowStatResult(a: Record<string, unknown>): StatResultArtifact | null {
  if (typeof a.id !== "string") return null;
  if (typeof a.project_slug !== "string") return null;
  if (typeof a.test_name !== "string") return null;
  if (typeof a.test_label !== "string") return null;
  if (typeof a.mode !== "string") return null;
  if (typeof a.params !== "object" || a.params === null) return null;
  if (typeof a.n !== "number") return null;
  if (typeof a.interpretation !== "string") return null;
  if (typeof a.results_path !== "string") return null;
  if (typeof a.library_path !== "string") return null;
  return a as unknown as StatResultArtifact;
}

function narrowFigure(a: Record<string, unknown>): FigureArtifact | null {
  if (typeof a.id !== "string") return null;
  if (typeof a.project_slug !== "string") return null;
  if (typeof a.kind !== "string") return null;
  if (typeof a.version !== "number") return null;
  if (typeof a.format !== "string") return null;
  if (typeof a.params !== "object" || a.params === null) return null;
  if (typeof a.png_path !== "string") return null;
  if (typeof a.library_path !== "string") return null;
  if (typeof a.backend !== "string") return null;
  return a as unknown as FigureArtifact;
}

function narrowSectionDraft(a: Record<string, unknown>): SectionDraftArtifact | null {
  // Minimal contract: section_id + section_type + content_md. The other
  // fields (id, manuscript_slug, status, version, library_path) get
  // filled by the generate-section route from existing section state, so
  // the sci-writing skill is allowed to emit a slim artifact carrying
  // only what it produces. Strict narrowing here would silently drop
  // every skill-emitted draft and surface as "succeeded-no-artifact".
  if (typeof a.section_id !== "string") return null;
  if (typeof a.section_type !== "string") return null;
  if (typeof a.content_md !== "string") return null;
  return a as unknown as SectionDraftArtifact;
}

function narrowSectionDiff(a: Record<string, unknown>): SectionDiffArtifact | null {
  if (typeof a.manuscript_slug !== "string") return null;
  if (typeof a.section_id !== "string") return null;
  if (typeof a.action !== "string") return null;
  if (typeof a.before !== "string") return null;
  if (typeof a.after !== "string") return null;
  return a as unknown as SectionDiffArtifact;
}

function narrowUnknown(a: Record<string, unknown>): UnknownArtifact {
  return a as unknown as UnknownArtifact;
}
