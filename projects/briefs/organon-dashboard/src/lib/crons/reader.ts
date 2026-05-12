import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";
import { organonRoot } from "../paths";

export type CronJob = {
  id: string;
  name: string;
  schedule: string | null;
  active: boolean;
  prompt_excerpt: string;
  source_path: string;
  status: CronJobStatus | null;
  launch_agent: string | null;
};

export type CronJobStatus = {
  last_run: string | null;
  next_run: string | null;
  result: "success" | "failure" | "running" | null;
  fail_count: number;
  last_log_excerpt: string;
  raw_path: string;
};

const FRONTMATTER_RE = /^---\n([\s\S]*?)\n---/;

function parseFrontmatter(md: string): Record<string, string> {
  const m = md.match(FRONTMATTER_RE);
  if (!m) return {};
  const out: Record<string, string> = {};
  for (const line of m[1].split("\n")) {
    const idx = line.indexOf(":");
    if (idx < 1) continue;
    const k = line.slice(0, idx).trim();
    const v = line.slice(idx + 1).trim().replace(/^["']|["']$/g, "");
    if (k) out[k] = v;
  }
  return out;
}

function bodyAfterFrontmatter(md: string): string {
  const m = md.match(FRONTMATTER_RE);
  return m ? md.slice(m[0].length).trim() : md.trim();
}

export function jobsDir(): string {
  return path.join(organonRoot(), "cron", "jobs");
}
export function statusDir(): string {
  return path.join(organonRoot(), "cron", "status");
}

function readStatus(jobId: string): CronJobStatus | null {
  const file = path.join(statusDir(), `${jobId}.json`);
  if (!existsSync(file)) return null;
  try {
    const raw = JSON.parse(readFileSync(file, "utf8")) as Partial<CronJobStatus> & {
      [key: string]: unknown;
    };
    return {
      last_run: (raw.last_run as string) ?? null,
      next_run: (raw.next_run as string) ?? null,
      result: ((raw.result as CronJobStatus["result"]) ?? null),
      fail_count: typeof raw.fail_count === "number" ? raw.fail_count : 0,
      last_log_excerpt:
        typeof raw.last_log_excerpt === "string" ? raw.last_log_excerpt : "",
      raw_path: file,
    };
  } catch {
    return null;
  }
}

function detectLaunchAgent(jobId: string): string | null {
  const home = homedir();
  const candidates = [
    path.join(home, "Library", "LaunchAgents", `com.organon.${jobId}.plist`),
    path.join(home, "Library", "LaunchAgents", `com.scientific-os.${jobId}.plist`),
  ];
  for (const c of candidates) {
    if (existsSync(c)) return c;
  }
  return null;
}

export function listCronJobs(): CronJob[] {
  const dir = jobsDir();
  if (!existsSync(dir)) return [];
  const out: CronJob[] = [];
  for (const f of readdirSync(dir)) {
    if (!f.endsWith(".md")) continue;
    const full = path.join(dir, f);
    try {
      if (!statSync(full).isFile()) continue;
    } catch { continue; }
    let md = "";
    try { md = readFileSync(full, "utf8"); } catch { continue; }
    const meta = parseFrontmatter(md);
    const id = (meta.id ?? meta.name ?? f.replace(/\.md$/, "")).trim();
    const body = bodyAfterFrontmatter(md);
    out.push({
      id,
      name: meta.name ?? id,
      schedule: meta.schedule ?? meta.cron ?? null,
      active: (meta.active ?? "true").toLowerCase() === "true",
      prompt_excerpt: body.slice(0, 240).replace(/\s+/g, " "),
      source_path: full,
      status: readStatus(id),
      launch_agent: detectLaunchAgent(id),
    });
  }
  out.sort((a, b) => a.id.localeCompare(b.id));
  return out;
}
