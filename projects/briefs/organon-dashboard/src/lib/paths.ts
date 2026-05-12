import { existsSync } from "node:fs";
import path from "node:path";
import { organonRootEnv } from "./env";

/**
 * Resolves the Organon repo root.
 *
 * The dashboard project lives at `<root>/projects/briefs/organon-dashboard/`,
 * so the root is three levels up from the workspace this Next.js process runs
 * in. CLAUDE.md at the candidate path confirms it.
 *
 * Override with `ORGANON_ROOT` env var when running the dashboard from
 * elsewhere or against a fixture during tests.
 */
export function organonRoot(): string {
  const fromEnv = organonRootEnv();
  if (fromEnv) return path.resolve(fromEnv);

  const projectCwd = process.cwd();
  const candidate = path.resolve(projectCwd, "..", "..", "..");
  const marker = path.join(candidate, "CLAUDE.md");
  if (existsSync(marker)) return candidate;
  return projectCwd;
}

export function projectsDir(): string {
  return path.join(organonRoot(), "projects");
}

export function briefsDir(): string {
  return path.join(projectsDir(), "briefs");
}

export function skillsDir(rootOrProjectPath?: string): string {
  const base = rootOrProjectPath ?? organonRoot();
  return path.join(base, ".claude", "skills");
}
