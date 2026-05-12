/**
 * PHASE_4_TASKS.md T21 — version store for /figures.
 *
 * Layout (matches PLAN §3 Phase 4):
 *   <projectPath>/figures/<fig_id>/
 *     index.json               -- pointer to current/main version (Phase 3 wrote this)
 *     v1.png  v1.json          -- generate output + sidecar
 *     v2.png  v2.json          -- edit output + sidecar
 *     mask/v2.png              -- the mask used for v2
 *     ...
 *
 * The "main" version is whichever v{N}.json has the highest N. The Phase 3
 * `index.json` is preserved + updated whenever a new version lands so the
 * existing `listFigures()` keeps returning the latest version per figure.
 */

import {
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  renameSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import { organonRoot } from "../paths";
import { assertWithinProject } from "../projects";
import { figureDir, saveFigure } from "../figures/store";
import type { FigureArtifact } from "../artifacts/types";

function sidecarPath(projectPath: string, figId: string, version: number): string {
  return path.join(figureDir(projectPath, figId), `v${version}.json`);
}

function maskDir(projectPath: string, figId: string): string {
  return path.join(figureDir(projectPath, figId), "mask");
}

function ensureDir(p: string): void {
  if (!existsSync(p)) mkdirSync(p, { recursive: true });
}

function rel(absPath: string): string {
  return path.relative(organonRoot(), absPath);
}

export function listVersions(
  projectPath: string,
  figId: string,
): FigureArtifact[] {
  const dir = figureDir(projectPath, figId);
  if (!existsSync(dir)) return [];
  const out: FigureArtifact[] = [];
  for (const f of readdirSync(dir)) {
    const m = f.match(/^v(\d+)\.json$/);
    if (!m) continue;
    try {
      const obj = JSON.parse(readFileSync(path.join(dir, f), "utf8"));
      if (obj && obj._artifact === "figure") out.push(obj as FigureArtifact);
    } catch {
      /* skip */
    }
  }
  out.sort((a, b) => a.version - b.version);
  return out;
}

export function getMainVersion(
  projectPath: string,
  figId: string,
): FigureArtifact | null {
  const versions = listVersions(projectPath, figId);
  if (versions.length === 0) return null;
  return versions[versions.length - 1];
}

export function readVersion(
  projectPath: string,
  figId: string,
  version: number,
): FigureArtifact | null {
  const target = sidecarPath(projectPath, figId, version);
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
 * Persist a figure version. Writes both the per-version sidecar
 * (v{N}.json) and updates the index.json (used by Phase 3's listFigures
 * to surface the latest per-figure entry in /data/plots history). Atomic
 * tmp+rename writes throughout.
 */
export function appendVersion(
  projectPath: string,
  artifact: FigureArtifact,
): string {
  ensureDir(figureDir(projectPath, artifact.id));
  const sidecar = sidecarPath(projectPath, artifact.id, artifact.version);
  assertWithinProject(sidecar, projectPath);
  const stamped: FigureArtifact = {
    ...artifact,
    library_path: artifact.library_path ?? rel(path.join(figureDir(projectPath, artifact.id), `v${artifact.version}.png`)),
  };
  const tmp = sidecar + ".tmp";
  writeFileSync(tmp, JSON.stringify(stamped, null, 2), "utf8");
  renameSync(tmp, sidecar);

  // Keep the Phase 3 index.json pointed at the latest version so existing
  // listFigures() consumers (the /data plot history) see this figure.
  saveFigure(projectPath, stamped);
  return rel(sidecar);
}

export function setLocked(
  projectPath: string,
  figId: string,
  version: number,
  patch: { caption: string; alt_text: string },
): FigureArtifact | null {
  const existing = readVersion(projectPath, figId, version);
  if (!existing) return null;
  const updated: FigureArtifact = {
    ...existing,
    caption: patch.caption,
    alt_text: patch.alt_text,
    locked: true,
  };
  appendVersion(projectPath, updated);
  return updated;
}

export function ensureMaskDir(projectPath: string, figId: string): string {
  const dir = maskDir(projectPath, figId);
  ensureDir(dir);
  return dir;
}

export function maskPath(projectPath: string, figId: string, version: number): string {
  return path.join(maskDir(projectPath, figId), `v${version}.png`);
}

export function pngPath(projectPath: string, figId: string, version: number): string {
  return path.join(figureDir(projectPath, figId), `v${version}.png`);
}
