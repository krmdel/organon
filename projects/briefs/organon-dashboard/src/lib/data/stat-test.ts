import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { organonRoot } from "../paths";
import { saveResult } from "../results/store";
import type { StatResultArtifact } from "../artifacts/types";

const TIMEOUT_MS = 60_000;

function venvPython(): string | null {
  const candidate = path.join(organonRoot(), ".venv", "bin", "python");
  return existsSync(candidate) ? candidate : null;
}

function runStatTestScript(): string {
  return path.join(
    organonRoot(),
    "projects",
    "briefs",
    "organon-dashboard",
    "scripts",
    "run_stat_test.py",
  );
}

export class StatTestError extends Error {
  status: 400 | 500 | 501 | 504;
  constructor(message: string, status: 400 | 500 | 501 | 504 = 500) {
    super(message);
    this.status = status;
  }
}

export type StatTestOpts = {
  /** Absolute path to the data file. May be empty for power-only tests. */
  dataPath: string;
  /** file_id (empty string for power tests). */
  fileId: string;
  runId: string;
  projectSlug: string;
  projectPath: string;
  /** scipy-side test name from stat-picker (e.g. "ttest_ind", "power_t_test"). */
  testName: string;
  /** Original test_label (e.g. "Two-sample t-test (Welch)"). */
  testLabel: string;
  params: Record<string, unknown>;
};

/**
 * Phase 6 (fix-sprint) — direct-Python stat test runner.
 *
 * Spawns scripts/run_stat_test.py with cwd=organonRoot, 60-second timeout,
 * parses the single JSON line on stdout into a StatResultArtifact, and
 * persists via saveResult. Mirrors the plot.ts shape so a regression in
 * one is visible in the other.
 */
export async function runStatTest(opts: StatTestOpts): Promise<StatResultArtifact> {
  const py = venvPython();
  if (!py) {
    throw new StatTestError(
      "Python venv missing. Run: bash .claude/skills/sci-data-analysis/scripts/setup.sh",
    );
  }
  const script = runStatTestScript();
  if (!existsSync(script)) {
    throw new StatTestError(`run_stat_test.py not found at ${script}`);
  }

  const root = organonRoot();
  const args = [
    script,
    "--run-id", opts.runId,
    "--project-slug", opts.projectSlug,
    "--file-id", opts.fileId,
    "--test", opts.testName,
    "--params-json", JSON.stringify(opts.params),
  ];
  if (opts.dataPath) {
    args.push("--data-path", opts.dataPath);
  }

  const child = spawn(py, args, { cwd: root, stdio: ["ignore", "pipe", "pipe"] });
  let stdout = "";
  let stderr = "";
  child.stdout.on("data", (c: Buffer) => { stdout += c.toString("utf8"); });
  child.stderr.on("data", (c: Buffer) => { stderr += c.toString("utf8"); });

  const code = await new Promise<number | null>((resolve, reject) => {
    const timer = setTimeout(() => {
      child.kill("SIGKILL");
      reject(new StatTestError(`run_stat_test.py timed out after ${TIMEOUT_MS}ms`, 504));
    }, TIMEOUT_MS);
    child.on("error", (err) => {
      clearTimeout(timer);
      reject(new StatTestError(`spawn failed: ${err.message}`));
    });
    child.on("close", (c) => {
      clearTimeout(timer);
      resolve(c);
    });
  });

  if (code !== 0) {
    const trimmed = stderr.trim();
    // run_stat_test.py emits {"error": "..."} on stderr for ValueError + dispatch errors.
    let message = trimmed.split("\n").slice(-3).join("\n") || `exited ${code}`;
    try {
      const parsed = JSON.parse(trimmed.split("\n").pop() ?? "");
      if (parsed && typeof parsed.error === "string") message = parsed.error;
    } catch { /* fall back to raw stderr tail */ }
    // exit code 2 is the param/data-shape error contract; 1 is generic failure;
    // logistic_regression returns its own message via _err — treat as 501.
    if (message.includes("requires statsmodels")) {
      throw new StatTestError(message, 501);
    }
    const status: 400 | 500 = code === 2 ? 400 : 500;
    throw new StatTestError(message, status);
  }

  const line = stdout.split("\n").map((l) => l.trim()).find((l) => l.startsWith("{"));
  if (!line) throw new StatTestError("run_stat_test.py emitted no JSON line");
  let artifact: StatResultArtifact;
  try {
    artifact = JSON.parse(line) as StatResultArtifact;
  } catch {
    throw new StatTestError("run_stat_test.py emitted unparseable JSON");
  }
  if (artifact._artifact !== "stat-result") {
    throw new StatTestError(`run_stat_test.py emitted wrong artifact kind: ${artifact._artifact}`);
  }
  // Override the test_label from the picker (the picker's label may include
  // human-friendly punctuation like "Two-sample t-test (Welch)").
  artifact.test_label = opts.testLabel || artifact.test_label;

  saveResult(opts.projectPath, artifact);
  return artifact;
}
