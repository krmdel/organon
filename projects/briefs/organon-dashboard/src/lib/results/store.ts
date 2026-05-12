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
import type { StatResultArtifact } from "../artifacts/types";

export function resultsDir(projectPath: string): string {
  return path.join(projectPath, "results");
}

function ensureResultsDir(projectPath: string): string {
  const dir = resultsDir(projectPath);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  return dir;
}

export function listResults(projectPath: string): StatResultArtifact[] {
  const dir = resultsDir(projectPath);
  if (!existsSync(dir)) return [];
  const out: StatResultArtifact[] = [];
  for (const f of readdirSync(dir)) {
    if (!f.endsWith(".json")) continue;
    try {
      const obj = JSON.parse(readFileSync(path.join(dir, f), "utf8"));
      if (obj && obj._artifact === "stat-result") out.push(obj as StatResultArtifact);
    } catch {
      /* skip */
    }
  }
  out.sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""));
  return out;
}

export function readResult(
  projectPath: string,
  runId: string,
): StatResultArtifact | null {
  const target = path.join(resultsDir(projectPath), `${runId}.json`);
  if (!existsSync(target)) return null;
  try {
    const obj = JSON.parse(readFileSync(target, "utf8"));
    if (obj && obj._artifact === "stat-result") return obj as StatResultArtifact;
  } catch {
    /* fall through */
  }
  return null;
}

export function saveResult(
  projectPath: string,
  artifact: StatResultArtifact,
): string {
  ensureResultsDir(projectPath);
  const target = path.join(resultsDir(projectPath), `${artifact.id}.json`);
  assertWithinProject(target, projectPath);
  const stamped: StatResultArtifact = {
    ...artifact,
    library_path: path.relative(organonRoot(), target),
    results_path: path.relative(organonRoot(), target),
  };
  const tmp = target + ".tmp";
  writeFileSync(tmp, JSON.stringify(stamped, null, 2), "utf8");
  renameSync(tmp, target);
  return stamped.library_path;
}

/**
 * Phase 12a (v1.0.1) — D-7 soft archive / unarchive a stat result.
 * Toggles the `archived` flag on disk; the file is never unlinked. The
 * `archived_at` timestamp lets a future "permanently delete after N days"
 * sweep be implemented without re-stamping every result.
 *
 * Returns the updated artifact, or null if the run does not exist.
 */
export function archiveResult(
  projectPath: string,
  runId: string,
): StatResultArtifact | null {
  return _setArchived(projectPath, runId, true);
}

export function unarchiveResult(
  projectPath: string,
  runId: string,
): StatResultArtifact | null {
  return _setArchived(projectPath, runId, false);
}

function _setArchived(
  projectPath: string,
  runId: string,
  archived: boolean,
): StatResultArtifact | null {
  const target = path.join(resultsDir(projectPath), `${runId}.json`);
  assertWithinProject(target, projectPath);
  if (!existsSync(target)) return null;
  let obj: StatResultArtifact;
  try {
    obj = JSON.parse(readFileSync(target, "utf8")) as StatResultArtifact;
  } catch {
    return null;
  }
  if (obj._artifact !== "stat-result") return null;
  const next: StatResultArtifact = {
    ...obj,
    archived,
    archived_at: archived ? new Date().toISOString() : null,
  };
  const tmp = target + ".tmp";
  writeFileSync(tmp, JSON.stringify(next, null, 2), "utf8");
  renameSync(tmp, target);
  return next;
}
