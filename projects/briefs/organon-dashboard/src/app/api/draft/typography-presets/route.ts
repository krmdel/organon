import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import path from "node:path";
import { resolveProjectFromRequest } from "@/lib/projects";
import {
  isValidPreset,
  type TypographyPreset,
} from "@/lib/draft/typography-presets";
import {
  loadPresetsSplit,
  projectPresetsPath,
} from "@/lib/draft/typography-presets-loader";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Phase 25 (v1.2) — DR-8+ project-local typography preset CRUD.
 *
 * GET   → { builtin: TypographyPreset[], project: TypographyPreset[] }
 *         so the menu can chip "custom" entries.
 * POST  → { preset: TypographyPreset } appends or upserts the project
 *         file (atomic tmp+rename). Project ids override builtins.
 * DELETE?id=foo → removes one entry from the project file. Builtins
 *         are immutable (404 when id is a builtin and no project entry
 *         exists). Atomic write.
 */

type ProjectFile = { presets: TypographyPreset[] };

function readProjectFile(projectPath: string): ProjectFile {
  const file = projectPresetsPath(projectPath);
  if (!existsSync(file)) return { presets: [] };
  try {
    const raw = readFileSync(file, "utf8");
    const parsed = JSON.parse(raw) as ProjectFile;
    if (!parsed || !Array.isArray(parsed.presets)) return { presets: [] };
    return { presets: parsed.presets.filter(isValidPreset) };
  } catch {
    return { presets: [] };
  }
}

function writeAtomic(target: string, content: string): void {
  const dir = path.dirname(target);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  const tmp = target + ".tmp";
  writeFileSync(tmp, content, "utf8");
  renameSync(tmp, target);
}

function stripSource(p: TypographyPreset): TypographyPreset {
  const { source: _source, ...rest } = p;
  return rest;
}

export async function GET(request: Request) {
  const project = resolveProjectFromRequest(request);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  const split = loadPresetsSplit(project.path);
  return Response.json(split, { status: 200 });
}

export async function POST(request: Request) {
  let body: { project?: string; preset?: TypographyPreset } = {};
  try {
    body = (await request.json()) as { project?: string; preset?: TypographyPreset };
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const project = resolveProjectFromRequest(request, body.project);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  if (!body.preset || !isValidPreset(body.preset)) {
    return Response.json(
      { error: "Body.preset is required and must match the TypographyPreset shape" },
      { status: 400 },
    );
  }
  const file = projectPresetsPath(project.path);
  const current = readProjectFile(project.path);
  const incoming = stripSource(body.preset);
  const next: TypographyPreset[] = [
    ...current.presets.filter((p) => p.id !== incoming.id),
    incoming,
  ];
  writeAtomic(file, JSON.stringify({ presets: next.map(stripSource) }, null, 2));
  return Response.json({ ok: true, preset: incoming, project_file: file }, { status: 201 });
}

export async function DELETE(request: Request) {
  const project = resolveProjectFromRequest(request);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  const id = new URL(request.url).searchParams.get("id");
  if (!id) return Response.json({ error: "Query param ?id= is required" }, { status: 400 });
  const file = projectPresetsPath(project.path);
  const current = readProjectFile(project.path);
  if (!current.presets.some((p) => p.id === id)) {
    return Response.json({ error: `No project preset with id=${id}` }, { status: 404 });
  }
  const next = current.presets.filter((p) => p.id !== id).map(stripSource);
  writeAtomic(file, JSON.stringify({ presets: next }, null, 2));
  return Response.json({ ok: true, removed: id, project_file: file }, { status: 200 });
}
