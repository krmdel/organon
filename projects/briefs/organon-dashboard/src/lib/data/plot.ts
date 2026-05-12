import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { organonRoot } from "../paths";
import { figureDir } from "../figures/store";
import { saveFigure } from "../figures/store";
import type { FigureArtifact } from "../artifacts/types";
import type { PlotKind } from "./plot-schemas";

const TIMEOUT_MS = 60_000;

function venvPython(): string | null {
  const candidate = path.join(organonRoot(), ".venv", "bin", "python");
  return existsSync(candidate) ? candidate : null;
}

function plotScript(): string {
  return path.join(
    organonRoot(),
    "projects",
    "briefs",
    "organon-dashboard",
    "scripts",
    "generate_plot.py",
  );
}

export class PlotError extends Error {
  status: 500 | 504;
  constructor(message: string, status: 500 | 504 = 500) {
    super(message);
    this.status = status;
  }
}

export type PlotOpts = {
  rawPath: string;
  fileId: string;
  figId: string;
  projectSlug: string;
  projectPath: string;
  kind: PlotKind;
  params: Record<string, unknown>;
};

export async function generatePlot(opts: PlotOpts): Promise<FigureArtifact> {
  const py = venvPython();
  if (!py) {
    throw new PlotError(
      "Python venv missing. Run: bash .claude/skills/sci-data-analysis/scripts/setup.sh",
    );
  }
  const script = plotScript();
  if (!existsSync(script)) {
    throw new PlotError(`generate_plot.py not found at ${script}`);
  }

  const root = organonRoot();
  const outDir = figureDir(opts.projectPath, opts.figId);
  const rel = (abs: string) => path.relative(root, abs);
  const dataPathRel = rel(opts.rawPath);
  const pngPath = rel(path.join(outDir, "v1.png"));
  const svgPath = rel(path.join(outDir, "v1.svg"));
  const thumbPath = rel(path.join(outDir, "v1.thumb.png"));
  const codePath = rel(path.join(outDir, "v1.py"));
  const libPath = pngPath;

  const args = [
    script,
    "--path", opts.rawPath,
    "--fig-id", opts.figId,
    "--project-slug", opts.projectSlug,
    "--file-id", opts.fileId,
    "--out-dir", outDir,
    "--kind", opts.kind,
    "--params", JSON.stringify(opts.params),
    "--library-path", libPath,
    "--code-path", codePath,
    "--png-path", pngPath,
    "--svg-path", svgPath,
    "--thumb-path", thumbPath,
    "--data-path", dataPathRel,
  ];

  const child = spawn(py, args, { cwd: root, stdio: ["ignore", "pipe", "pipe"] });
  let stdout = "";
  let stderr = "";
  child.stdout.on("data", (c: Buffer) => { stdout += c.toString("utf8"); });
  child.stderr.on("data", (c: Buffer) => { stderr += c.toString("utf8"); });

  const code = await new Promise<number | null>((resolve, reject) => {
    const timer = setTimeout(() => {
      child.kill("SIGKILL");
      reject(new PlotError(`generate_plot.py timed out after ${TIMEOUT_MS}ms`, 504));
    }, TIMEOUT_MS);
    child.on("error", (err) => {
      clearTimeout(timer);
      reject(new PlotError(`spawn failed: ${err.message}`));
    });
    child.on("close", (c) => {
      clearTimeout(timer);
      resolve(c);
    });
  });

  if (code !== 0) {
    const tail = stderr.split("\n").slice(-5).join("\n").trim() || "(no stderr)";
    throw new PlotError(`generate_plot.py exited ${code}: ${tail}`);
  }

  const line = stdout.split("\n").map((l) => l.trim()).find((l) => l.startsWith("{"));
  if (!line) throw new PlotError("generate_plot.py emitted no JSON line");
  let artifact: FigureArtifact;
  try {
    artifact = JSON.parse(line) as FigureArtifact;
  } catch {
    throw new PlotError("generate_plot.py emitted unparseable JSON");
  }
  if (artifact._artifact !== "figure") {
    throw new PlotError(`generate_plot.py emitted wrong artifact kind: ${artifact._artifact}`);
  }

  saveFigure(opts.projectPath, artifact);
  return artifact;
}
