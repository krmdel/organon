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
import type { PersonaCritiqueArtifact } from "../artifacts/types";
import { organonRoot } from "../paths";
import { assertWithinProject } from "../projects";
import { hypothesisDir } from "./store";

export function critiquesDir(projectPath: string, hypId: string): string {
  return path.join(hypothesisDir(projectPath, hypId), "critiques");
}

function critiqueFile(
  projectPath: string,
  hypId: string,
  personaSlug: string,
): string {
  return path.join(critiquesDir(projectPath, hypId), `${personaSlug}.json`);
}

function ensureCritiquesDir(projectPath: string, hypId: string): string {
  const dir = critiquesDir(projectPath, hypId);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  return dir;
}

export function listCritiques(
  projectPath: string,
  hypId: string,
): PersonaCritiqueArtifact[] {
  const dir = critiquesDir(projectPath, hypId);
  if (!existsSync(dir)) return [];
  const out: PersonaCritiqueArtifact[] = [];
  for (const f of readdirSync(dir)) {
    if (!f.endsWith(".json")) continue;
    const full = path.join(dir, f);
    try {
      const obj = JSON.parse(readFileSync(full, "utf8"));
      if (obj && obj._artifact === "persona-critique") {
        out.push(obj as PersonaCritiqueArtifact);
      }
    } catch {
      /* skip */
    }
  }
  out.sort((a, b) => (a.created_at ?? "").localeCompare(b.created_at ?? ""));
  return out;
}

export function saveCritique(
  projectPath: string,
  critique: PersonaCritiqueArtifact,
): string {
  ensureCritiquesDir(projectPath, critique.hypothesis_id);
  const target = critiqueFile(projectPath, critique.hypothesis_id, critique.persona_slug);
  assertWithinProject(target, projectPath);
  const root = organonRoot();
  const relativePath = path.relative(root, target);

  const stamped: PersonaCritiqueArtifact = {
    ...critique,
    library_path: relativePath,
    created_at: critique.created_at ?? new Date().toISOString(),
  };

  const tmp = target + ".tmp";
  writeFileSync(tmp, JSON.stringify(stamped, null, 2), "utf8");
  renameSync(tmp, target);
  return relativePath;
}

export function deleteCritique(
  projectPath: string,
  hypId: string,
  personaSlug: string,
): boolean {
  const target = critiqueFile(projectPath, hypId, personaSlug);
  if (!existsSync(target)) return false;
  unlinkSync(target);
  return true;
}
