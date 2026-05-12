import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { skillsDir } from "./paths";

export type Skill = {
  name: string;
  category: string;
  description: string;
  slug: string;
};

export type SkillGroup = {
  category: string;
  label: string;
  skills: Skill[];
};

const CATEGORY_LABELS: Record<string, string> = {
  sci: "Science",
  viz: "Visual",
  ops: "Operations",
  tool: "Tools",
  meta: "System / Meta",
  other: "Other",
};

const CATEGORY_ORDER = ["sci", "viz", "ops", "tool", "meta", "other"];

export function listSkills(projectPath?: string): Skill[] {
  // Skills always live at the Organon root's .claude/skills, even when invoked
  // in a project context. Per-project overrides aren't part of Phase 1.
  const dir = skillsDir();
  if (!existsSync(dir)) return [];

  const out: Skill[] = [];
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry);
    try {
      if (!statSync(full).isDirectory()) continue;
    } catch {
      continue;
    }
    const skillMd = path.join(full, "SKILL.md");
    if (!existsSync(skillMd)) continue;

    const skill = parseSkill(skillMd, entry);
    if (skill) out.push(skill);
  }
  // Reference projectPath so future per-project skill folders integrate cleanly.
  void projectPath;
  return out.sort((a, b) => a.name.localeCompare(b.name));
}

export function listSkillGroups(projectPath?: string): SkillGroup[] {
  const skills = listSkills(projectPath);
  const map = new Map<string, Skill[]>();
  for (const s of skills) {
    const arr = map.get(s.category) ?? [];
    arr.push(s);
    map.set(s.category, arr);
  }
  const groups: SkillGroup[] = [];
  for (const cat of CATEGORY_ORDER) {
    if (!map.has(cat)) continue;
    groups.push({
      category: cat,
      label: CATEGORY_LABELS[cat] ?? cat,
      skills: map.get(cat)!,
    });
  }
  return groups;
}

function parseSkill(skillMdPath: string, slug: string): Skill | null {
  const raw = readFileSync(skillMdPath, "utf8");
  const fm = extractFrontmatter(raw);
  if (!fm) return null;

  const name = (fm.name ?? slug).trim();
  const description = (fm.description ?? "").replace(/\s+/g, " ").trim();

  const prefix = name.split("-")[0];
  const category = ["sci", "viz", "ops", "tool", "meta"].includes(prefix) ? prefix : "other";

  return { name, slug, category, description };
}

/**
 * Tiny YAML-frontmatter parser — handles the subset that SKILL.md files use:
 * `key: value` and `key: >\n  multiline value`. Avoids a yaml dep.
 */
function extractFrontmatter(raw: string): Record<string, string> | null {
  if (!raw.startsWith("---")) return null;
  const end = raw.indexOf("\n---", 3);
  if (end === -1) return null;
  const block = raw.slice(3, end).replace(/^\n/, "");

  const result: Record<string, string> = {};
  const lines = block.split("\n");
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const match = line.match(/^([a-zA-Z_][\w-]*)\s*:\s*(.*)$/);
    if (!match) {
      i++;
      continue;
    }
    const [, key, valueRaw] = match;
    if (valueRaw.trim() === ">" || valueRaw.trim() === "|") {
      const buf: string[] = [];
      i++;
      while (i < lines.length && /^\s+/.test(lines[i])) {
        buf.push(lines[i].trim());
        i++;
      }
      result[key] = buf.join(" ");
    } else {
      result[key] = stripQuotes(valueRaw.trim());
      i++;
    }
  }
  return result;
}

function stripQuotes(s: string): string {
  if ((s.startsWith('"') && s.endsWith('"')) || (s.startsWith("'") && s.endsWith("'"))) {
    return s.slice(1, -1);
  }
  return s;
}
