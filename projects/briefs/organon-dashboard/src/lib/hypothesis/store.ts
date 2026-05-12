import {
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  renameSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import type { HypothesisArtifact, HypothesisStatus } from "../artifacts/types";
import { organonRoot } from "../paths";
import { assertWithinProject } from "../projects";
import { hypothesesDir } from "./personas";

const VALID_STATUSES: ReadonlySet<HypothesisStatus> = new Set([
  "open",
  "synthesized",
  "supported",
  "refuted",
  "archived",
]);

/**
 * D6 status state machine. Returns the next state if the transition is allowed,
 * or null if it is not.
 *
 * Skill-only transitions: open → synthesized. (sci-council can only ratify
 * an open hypothesis; nothing else.)
 *
 * User-only transitions:
 *   - anything → archived (always allowed)
 *   - synthesized → supported|refuted
 *   - supported|refuted → synthesized   (re-evaluate)
 *   - supported ↔ refuted               (Phase 57 — direct flip without
 *                                         a synthesized round-trip)
 *   - archived → open                   (Phase 57 — un-archive)
 */
export function isValidTransition(
  from: HypothesisStatus,
  to: HypothesisStatus,
  source: "user" | "skill",
): boolean {
  if (!VALID_STATUSES.has(to)) return false;
  if (from === to) return true;
  if (to === "archived") return true;
  if (source === "skill") {
    return from === "open" && to === "synthesized";
  }
  // user
  if (from === "synthesized" && (to === "supported" || to === "refuted")) return true;
  if (from === "supported" || from === "refuted") {
    // Phase 57 (v2.1) — A3: allow direct supported ↔ refuted in addition
    // to the existing supported|refuted → synthesized path so the
    // researcher can flip a triage verdict without round-tripping.
    if (to === "synthesized" || to === "supported" || to === "refuted") return true;
  }
  // Phase 57 (v2.1) — A3: archived → open lets the user un-archive a
  // hypothesis they previously dismissed without skill round-trip.
  if (from === "archived" && to === "open") return true;
  return false;
}

export function hypothesisDir(projectPath: string, hypId: string): string {
  return path.join(hypothesesDir(projectPath), hypId);
}

function recordPath(projectPath: string, hypId: string): string {
  return path.join(hypothesisDir(projectPath, hypId), "hypothesis.json");
}

function ensureRecordDir(projectPath: string, hypId: string): string {
  const dir = hypothesisDir(projectPath, hypId);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  return dir;
}

/**
 * Phase 43 (v1.5) — F6: read-time backfill for the new
 * excluded_persona_ids[] field. Same pattern as Phase 41's
 * migrateManuscriptLinkage — defaults missing → [], never writes back.
 *
 * Phase 48 (v1.6) — F11 extension: also backfills the new
 * additional_papers_by_persona map. Default {} so legacy hypotheses
 * pre-Phase-48 read tolerantly. Never writes back.
 */
export function migrateHypothesisExclusions(hyp: HypothesisArtifact): HypothesisArtifact {
  return {
    ...hyp,
    excluded_persona_ids: Array.isArray(hyp.excluded_persona_ids)
      ? hyp.excluded_persona_ids
      : [],
    additional_papers_by_persona:
      hyp.additional_papers_by_persona && typeof hyp.additional_papers_by_persona === "object"
        ? hyp.additional_papers_by_persona
        : {},
  };
}

export function listHypotheses(projectPath: string): HypothesisArtifact[] {
  const dir = hypothesesDir(projectPath);
  if (!existsSync(dir)) return [];
  const out: HypothesisArtifact[] = [];
  for (const entry of readdirSync(dir)) {
    if (!entry.startsWith("hyp-")) continue;
    const file = recordPath(projectPath, entry);
    if (!existsSync(file)) continue;
    try {
      const raw = readFileSync(file, "utf8");
      const obj = JSON.parse(raw);
      if (obj && obj._artifact === "hypothesis") {
        out.push(migrateHypothesisExclusions(obj as HypothesisArtifact));
      }
    } catch {
      /* skip unreadable / malformed */
    }
  }
  out.sort((a, b) => (b.updated_at ?? "").localeCompare(a.updated_at ?? ""));
  return out;
}

export function getHypothesis(
  projectPath: string,
  hypId: string,
): HypothesisArtifact | null {
  const file = recordPath(projectPath, hypId);
  if (!existsSync(file)) return null;
  try {
    const obj = JSON.parse(readFileSync(file, "utf8"));
    if (obj && obj._artifact === "hypothesis") {
      return migrateHypothesisExclusions(obj as HypothesisArtifact);
    }
  } catch {
    return null;
  }
  return null;
}

export function saveHypothesis(
  projectPath: string,
  hyp: HypothesisArtifact,
): string {
  ensureRecordDir(projectPath, hyp.id);
  const target = recordPath(projectPath, hyp.id);
  assertWithinProject(target, projectPath);
  const root = organonRoot();
  const relativePath = path.relative(root, target);

  const stamped: HypothesisArtifact = {
    ...hyp,
    updated_at: new Date().toISOString(),
    library_path: relativePath,
  };

  const tmp = target + ".tmp";
  writeFileSync(tmp, JSON.stringify(stamped, null, 2), "utf8");
  renameSync(tmp, target);
  return relativePath;
}

export function patchHypothesis(
  projectPath: string,
  hypId: string,
  patch: Partial<HypothesisArtifact>,
): HypothesisArtifact | null {
  const current = getHypothesis(projectPath, hypId);
  if (!current) return null;
  const merged: HypothesisArtifact = {
    ...current,
    ...patch,
    id: current.id,
    _artifact: "hypothesis",
    schema_version: 1,
    created_at: current.created_at,
    updated_at: new Date().toISOString(),
  };
  saveHypothesis(projectPath, merged);
  return merged;
}

export function deleteHypothesis(projectPath: string, hypId: string): boolean {
  const dir = hypothesisDir(projectPath, hypId);
  if (!existsSync(dir)) return false;
  rmSync(dir, { recursive: true, force: true });
  return true;
}
