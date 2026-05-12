import {
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  renameSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import { organonRoot } from "../paths";
import { assertWithinProject } from "../projects";
import type { DataframeArtifact } from "../artifacts/types";

export function dataDir(projectPath: string): string {
  return path.join(projectPath, "data");
}

export function ensureDataDir(projectPath: string): string {
  const dir = dataDir(projectPath);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  return dir;
}

function previewPath(projectPath: string, fileId: string): string {
  return path.join(dataDir(projectPath), `${fileId}.preview.json`);
}

function rawFilePathByPrefix(projectPath: string, fileId: string): string | null {
  const dir = dataDir(projectPath);
  if (!existsSync(dir)) return null;
  const prefix = `${fileId}.`;
  for (const f of readdirSync(dir)) {
    if (f === `${fileId}.preview.json`) continue;
    if (f.startsWith(prefix)) return path.join(dir, f);
  }
  return null;
}

export function listFiles(projectPath: string): DataframeArtifact[] {
  const dir = dataDir(projectPath);
  if (!existsSync(dir)) return [];
  const out: DataframeArtifact[] = [];
  for (const f of readdirSync(dir)) {
    if (!f.endsWith(".preview.json")) continue;
    const full = path.join(dir, f);
    try {
      const raw = readFileSync(full, "utf8");
      const obj = JSON.parse(raw);
      if (obj && obj._artifact === "dataframe") out.push(obj as DataframeArtifact);
    } catch {
      /* skip unreadable / malformed */
    }
  }
  out.sort((a, b) => (b.uploaded_at ?? "").localeCompare(a.uploaded_at ?? ""));
  return out;
}

export function readPreview(
  projectPath: string,
  fileId: string,
): DataframeArtifact | null {
  const target = previewPath(projectPath, fileId);
  if (!existsSync(target)) return null;
  try {
    const raw = readFileSync(target, "utf8");
    const obj = JSON.parse(raw);
    if (obj && obj._artifact === "dataframe") return obj as DataframeArtifact;
  } catch {
    /* fall through */
  }
  return null;
}

export function savePreview(
  projectPath: string,
  artifact: DataframeArtifact,
): string {
  ensureDataDir(projectPath);
  const target = previewPath(projectPath, artifact.id);
  assertWithinProject(target, projectPath);
  const root = organonRoot();
  const stamped: DataframeArtifact = {
    ...artifact,
    library_path: path.relative(root, target),
    preview_path: path.relative(root, target),
  };
  const tmp = target + ".tmp";
  writeFileSync(tmp, JSON.stringify(stamped, null, 2), "utf8");
  renameSync(tmp, target);
  return stamped.library_path;
}

export function rawFilePath(
  projectPath: string,
  fileId: string,
): string | null {
  return rawFilePathByPrefix(projectPath, fileId);
}

export function removeFile(projectPath: string, fileId: string): boolean {
  const preview = previewPath(projectPath, fileId);
  const raw = rawFilePathByPrefix(projectPath, fileId);
  let removed = false;
  if (existsSync(preview)) {
    unlinkSync(preview);
    removed = true;
  }
  if (raw && existsSync(raw)) {
    unlinkSync(raw);
    removed = true;
  }
  return removed;
}
