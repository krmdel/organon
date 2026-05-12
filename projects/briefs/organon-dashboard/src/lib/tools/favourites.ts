import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import path from "node:path";
import { organonRoot } from "../paths";

function favDir(projectPath: string): string {
  const isRoot = path.resolve(projectPath) === path.resolve(organonRoot());
  if (isRoot) return path.join(projectPath, ".organon-dashboard");
  return path.join(projectPath, ".organon-dashboard");
}
function favFile(projectPath: string): string {
  return path.join(favDir(projectPath), "tool-favourites.json");
}

export function readFavourites(projectPath: string): string[] {
  const file = favFile(projectPath);
  if (!existsSync(file)) return [];
  try {
    const raw = JSON.parse(readFileSync(file, "utf8")) as unknown;
    if (Array.isArray(raw)) return raw.filter((s): s is string => typeof s === "string");
  } catch { /* fall through */ }
  return [];
}

export function writeFavourites(projectPath: string, favourites: string[]): void {
  const dir = favDir(projectPath);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  const target = favFile(projectPath);
  const tmp = target + ".tmp";
  writeFileSync(tmp, JSON.stringify(favourites, null, 2), "utf8");
  renameSync(tmp, target);
}
