import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import path from "node:path";
import {
  MAX_PERSONAS,
  getDefaultPersonas,
  getMathTemplatePersonas,
  type Persona,
} from "./shared";

export {
  MAX_PERSONAS,
  getDefaultPersonas,
  getMathTemplatePersonas,
  type Persona,
} from "./shared";

export function hypothesesDir(projectPath: string): string {
  return path.join(projectPath, "hypotheses");
}

export function personasFile(projectPath: string): string {
  return path.join(hypothesesDir(projectPath), "personas.json");
}

function ensureHypothesesDir(projectPath: string): string {
  const dir = hypothesesDir(projectPath);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  return dir;
}

export function listPersonas(projectPath: string): Persona[] {
  const file = personasFile(projectPath);
  if (!existsSync(file)) {
    const defaults = getDefaultPersonas();
    savePersonas(projectPath, defaults);
    return defaults;
  }
  try {
    const raw = readFileSync(file, "utf8");
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return getDefaultPersonas();
    return parsed.map(normalisePersona);
  } catch {
    return getDefaultPersonas();
  }
}

export function savePersonas(projectPath: string, personas: Persona[]): void {
  validatePersonas(personas);
  ensureHypothesesDir(projectPath);
  const target = personasFile(projectPath);
  const tmp = target + ".tmp";
  writeFileSync(tmp, JSON.stringify(personas.map(normalisePersona), null, 2), "utf8");
  renameSync(tmp, target);
}

export function validatePersonas(personas: Persona[]): void {
  if (!Array.isArray(personas) || personas.length === 0) {
    throw new Error("personas: at least one required");
  }
  if (personas.length > MAX_PERSONAS) {
    throw new Error(`personas: max ${MAX_PERSONAS}`);
  }
  const seen = new Set<string>();
  for (const p of personas) {
    if (!p || typeof p.name !== "string" || !p.name.trim()) {
      throw new Error("personas: name required");
    }
    const key = p.name.trim().toLowerCase();
    if (seen.has(key)) throw new Error("personas: duplicate persona name");
    seen.add(key);
  }
}

function normalisePersona(p: Persona): Persona {
  const name = (p.name ?? "").trim();
  return {
    name,
    role: p.role?.trim() || undefined,
    avatar: p.avatar?.trim() || name.slice(0, 1).toUpperCase(),
    // Phase 13a (v1.0.1): read-time backfill — pre-Phase-13a
    // personas.json entries do not carry `active` at all; default to
    // true so existing projects keep firing every persona post-upgrade.
    // Explicit `false` is preserved.
    active: typeof p.active === "boolean" ? p.active : true,
  };
}
