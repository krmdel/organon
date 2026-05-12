import path from "node:path";
import { resolveProjectFromRequest } from "@/lib/projects";
import { organonRoot } from "@/lib/paths";
import {
  getHypothesis,
  listHypotheses,
  saveHypothesis,
} from "@/lib/hypothesis/store";
import { allocateHypothesisId } from "@/lib/hypothesis/id";
import { listPersonas } from "@/lib/hypothesis/personas";
import type { HypothesisArtifact } from "@/lib/artifacts/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const project = resolveProjectFromRequest(request);
  if (!project) {
    return Response.json({ error: "Unknown project" }, { status: 404 });
  }
  const hypotheses = listHypotheses(project.path);
  return Response.json({ project: project.slug, hypotheses, total: hypotheses.length });
}

type CreateBody = {
  project?: string;
  claim?: string;
  paper_ids?: string[];
  claim_short?: string | null;
};

export async function POST(request: Request) {
  let body: CreateBody;
  try {
    body = (await request.json()) as CreateBody;
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const project = resolveProjectFromRequest(request, body.project);
  if (!project) {
    return Response.json({ error: "Unknown project" }, { status: 404 });
  }
  const claim = (body.claim ?? "").trim();
  if (!claim) {
    return Response.json({ error: "claim required" }, { status: 400 });
  }
  const paper_ids = Array.isArray(body.paper_ids)
    ? body.paper_ids.filter((s): s is string => typeof s === "string")
    : [];

  const id = allocateHypothesisId(claim);
  // Guard against the once-in-a-blue-moon collision: if the id is already
  // taken (same ms + same claim), append a counter.
  let finalId = id;
  let counter = 1;
  while (getHypothesis(project.path, finalId)) {
    counter += 1;
    finalId = `${id}-${counter}`;
  }

  const personas = listPersonas(project.path);
  const now = new Date().toISOString();
  const relativePath = path.relative(
    organonRoot(),
    path.join(project.path, "hypotheses", finalId, "hypothesis.json"),
  );

  const record: HypothesisArtifact = {
    _artifact: "hypothesis",
    schema_version: 1,
    id: finalId,
    claim,
    claim_short: body.claim_short?.slice(0, 80) ?? claim.slice(0, 80),
    project_slug: project.slug,
    status: "open",
    paper_ids,
    personas_used: personas.map((p) => p.name),
    critique_files: [],
    synthesis_text: null,
    open_questions: [],
    experiment_design: null,
    council_confidence: null,
    tags: [],
    notes: "",
    created_at: now,
    updated_at: now,
    library_path: relativePath,
  };

  saveHypothesis(project.path, record);
  return Response.json({ hypothesis: record }, { status: 201 });
}
