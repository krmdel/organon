import {
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import { assertWithinProject } from "../projects";

// Phase 14b (v1.0.1) — F-2 figure annotations persistence.
//
// Annotations live alongside the figure version PNGs at:
//   projects/{slug}/figures/{fig_id}/annotations.json
//
// The file is a single JSON document carrying every stroke for the
// figure (strokes are not versioned per FAL fill — annotations are
// metadata layered on top of the latest version, NOT bound to a
// specific version). Round-trip preserves stroke order so the ERASER's
// last-drawn-first hit test stays deterministic.

export type Pt = { x: number; y: number };

export type AnnotationStroke =
  | {
      kind: "pen";
      id: string;
      color: string;
      thickness: number;
      points: Pt[];
      t: string;
    }
  | {
      kind: "arrow";
      id: string;
      color: string;
      thickness: number;
      from: Pt;
      to: Pt;
      t: string;
    }
  | {
      kind: "text";
      id: string;
      color: string;
      size: number;
      at: Pt;
      text: string;
      t: string;
    };

export type FigureAnnotationsArtifact = {
  _artifact: "figure-annotations";
  schema_version: 1;
  fig_id: string;
  strokes: AnnotationStroke[];
  updated_at: string;
};

const FIGURES_DIR_NAME = "figures";

export function annotationsFile(projectPath: string, figId: string): string {
  return path.join(projectPath, FIGURES_DIR_NAME, figId, "annotations.json");
}

export function readAnnotations(
  projectPath: string,
  figId: string,
): FigureAnnotationsArtifact {
  const file = annotationsFile(projectPath, figId);
  if (!existsSync(file)) {
    return {
      _artifact: "figure-annotations",
      schema_version: 1,
      fig_id: figId,
      strokes: [],
      updated_at: new Date().toISOString(),
    };
  }
  try {
    const raw = readFileSync(file, "utf8");
    const obj = JSON.parse(raw);
    if (
      obj &&
      obj._artifact === "figure-annotations" &&
      obj.fig_id === figId &&
      Array.isArray(obj.strokes)
    ) {
      return obj as FigureAnnotationsArtifact;
    }
  } catch {
    /* fall through to empty */
  }
  return {
    _artifact: "figure-annotations",
    schema_version: 1,
    fig_id: figId,
    strokes: [],
    updated_at: new Date().toISOString(),
  };
}

export function writeAnnotations(
  projectPath: string,
  figId: string,
  strokes: AnnotationStroke[],
): FigureAnnotationsArtifact {
  const target = annotationsFile(projectPath, figId);
  assertWithinProject(target, projectPath);
  const dir = path.dirname(target);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  const stamped: FigureAnnotationsArtifact = {
    _artifact: "figure-annotations",
    schema_version: 1,
    fig_id: figId,
    strokes,
    updated_at: new Date().toISOString(),
  };
  const tmp = target + ".tmp";
  writeFileSync(tmp, JSON.stringify(stamped, null, 2), "utf8");
  renameSync(tmp, target);
  return stamped;
}
