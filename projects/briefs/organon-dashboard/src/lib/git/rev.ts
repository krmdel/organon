import { execSync } from "node:child_process";
import { organonRoot } from "../paths";

let cached: { rev: string; ts: number } | null = null;
const TTL_MS = 30_000;

export function gitRevShort(): string {
  const now = Date.now();
  if (cached && now - cached.ts < TTL_MS) return cached.rev;
  try {
    const rev = execSync("git rev-parse --short HEAD", {
      cwd: organonRoot(),
      stdio: ["ignore", "pipe", "ignore"],
      encoding: "utf8",
      timeout: 2000,
    }).trim();
    cached = { rev, ts: now };
    return rev;
  } catch {
    return "unknown";
  }
}
