import {
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  renameSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import { organonRoot } from "../paths";
import { assertWithinProject } from "../projects";
import type { FigureArtifact } from "../artifacts/types";

export function figuresDir(projectPath: string): string {
  return path.join(projectPath, "figures");
}

export function figureDir(projectPath: string, figId: string): string {
  return path.join(figuresDir(projectPath), figId);
}

function ensureFigureDir(projectPath: string, figId: string): string {
  const dir = figureDir(projectPath, figId);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  return dir;
}

function indexPath(projectPath: string, figId: string): string {
  return path.join(figureDir(projectPath, figId), "index.json");
}

export function listFigures(projectPath: string): FigureArtifact[] {
  const dir = figuresDir(projectPath);
  if (!existsSync(dir)) return [];
  const out: FigureArtifact[] = [];
  for (const entry of readdirSync(dir)) {
    const sub = path.join(dir, entry);
    try {
      if (!statSync(sub).isDirectory()) continue;
    } catch {
      continue;
    }
    const idx = path.join(sub, "index.json");
    if (!existsSync(idx)) continue;
    try {
      const obj = JSON.parse(readFileSync(idx, "utf8"));
      if (obj && obj._artifact === "figure") out.push(obj as FigureArtifact);
    } catch {
      /* skip */
    }
  }
  out.sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""));
  return out;
}

export function readFigure(
  projectPath: string,
  figId: string,
): FigureArtifact | null {
  const target = indexPath(projectPath, figId);
  if (!existsSync(target)) return null;
  try {
    const obj = JSON.parse(readFileSync(target, "utf8"));
    if (obj && obj._artifact === "figure") return obj as FigureArtifact;
  } catch {
    /* fall through */
  }
  return null;
}

/**
 * Phase 63 (v2.2) — M2: hard delete a figure dir + cascade to mask +
 * iteration files. Idempotent (`force: true`); no-op when the dir is
 * already gone. Mirrors deleteManuscript.
 */
export function deleteFigure(projectPath: string, figId: string): void {
  const target = figureDir(projectPath, figId);
  assertWithinProject(target, projectPath);
  rmSync(target, { recursive: true, force: true });
}

export function saveFigure(
  projectPath: string,
  artifact: FigureArtifact,
): string {
  ensureFigureDir(projectPath, artifact.id);
  const target = indexPath(projectPath, artifact.id);
  assertWithinProject(target, projectPath);
  const stamped: FigureArtifact = {
    ...artifact,
    library_path: path.relative(organonRoot(), target),
  };
  const tmp = target + ".tmp";
  writeFileSync(tmp, JSON.stringify(stamped, null, 2), "utf8");
  renameSync(tmp, target);
  return stamped.library_path;
}
