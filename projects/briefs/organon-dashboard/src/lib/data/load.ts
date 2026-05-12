import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { organonRoot } from "../paths";
import { savePreview } from "./files";
import type { DataframeArtifact } from "../artifacts/types";

const PROFILE_TIMEOUT_MS = 30_000;

function venvPython(): string | null {
  const root = organonRoot();
  const candidate = path.join(root, ".venv", "bin", "python");
  if (existsSync(candidate)) return candidate;
  return null;
}

function profileScript(): string {
  return path.join(
    organonRoot(),
    "projects",
    "briefs",
    "organon-dashboard",
    "scripts",
    "profile_dataframe.py",
  );
}

export class ProfileError extends Error {
  status: 500 | 504;
  constructor(message: string, status: 500 | 504 = 500) {
    super(message);
    this.status = status;
  }
}

export type ProfileOpts = {
  rawPath: string;
  fileId: string;
  filename: string;
  projectSlug: string;
  projectPath: string;
  uploadedAt: string;
  columnOverrides?: Record<string, string>;
};

/**
 * Spawn `python scripts/profile_dataframe.py` and parse the JSON line on
 * stdout. Persists the artifact to `<projectPath>/data/{file_id}.preview.json`
 * before returning. Throws ProfileError on subprocess failure / timeout.
 */
export async function loadAndProfile(opts: ProfileOpts): Promise<DataframeArtifact> {
  const py = venvPython();
  if (!py) {
    throw new ProfileError(
      "Python venv missing. Run: bash .claude/skills/sci-data-analysis/scripts/setup.sh",
    );
  }
  const script = profileScript();
  if (!existsSync(script)) {
    throw new ProfileError(`profile_dataframe.py not found at ${script}`);
  }

  const root = organonRoot();
  const dataPathRel = path.relative(
    root,
    path.join(opts.projectPath, "data", `${opts.fileId}.${path.extname(opts.rawPath).slice(1)}`),
  );
  const previewPathRel = path.relative(
    root,
    path.join(opts.projectPath, "data", `${opts.fileId}.preview.json`),
  );

  const args = [
    script,
    "--path", opts.rawPath,
    "--file-id", opts.fileId,
    "--project-slug", opts.projectSlug,
    "--filename", opts.filename,
    "--library-path", previewPathRel,
    "--data-path", dataPathRel,
    "--preview-path", previewPathRel,
    "--uploaded-at", opts.uploadedAt,
    "--column-overrides", JSON.stringify(opts.columnOverrides ?? {}),
  ];

  const child = spawn(py, args, { cwd: root, stdio: ["ignore", "pipe", "pipe"] });

  let stdout = "";
  let stderr = "";
  child.stdout.on("data", (chunk: Buffer) => { stdout += chunk.toString("utf8"); });
  child.stderr.on("data", (chunk: Buffer) => { stderr += chunk.toString("utf8"); });

  const exitCode = await new Promise<number | null>((resolve, reject) => {
    const timer = setTimeout(() => {
      child.kill("SIGKILL");
      reject(new ProfileError(`profile_dataframe.py timed out after ${PROFILE_TIMEOUT_MS}ms`, 504));
    }, PROFILE_TIMEOUT_MS);
    child.on("error", (err) => {
      clearTimeout(timer);
      reject(new ProfileError(`spawn failed: ${err.message}`));
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      resolve(code);
    });
  });

  if (exitCode !== 0) {
    const tail = stderr.split("\n").slice(-5).join("\n").trim() || "(no stderr)";
    throw new ProfileError(`profile_dataframe.py exited ${exitCode}: ${tail}`);
  }

  const line = stdout.split("\n").map((l) => l.trim()).find((l) => l.startsWith("{"));
  if (!line) {
    throw new ProfileError("profile_dataframe.py emitted no JSON line on stdout");
  }
  let artifact: DataframeArtifact;
  try {
    artifact = JSON.parse(line) as DataframeArtifact;
  } catch {
    throw new ProfileError("profile_dataframe.py emitted unparseable JSON");
  }
  if (artifact._artifact !== "dataframe") {
    throw new ProfileError(`profile_dataframe.py emitted wrong artifact kind: ${artifact._artifact}`);
  }

  savePreview(opts.projectPath, artifact);
  return artifact;
}
