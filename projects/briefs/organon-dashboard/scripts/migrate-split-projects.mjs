#!/usr/bin/env node
/**
 * scripts/migrate-split-projects.mjs — Phase 2 (fix-sprint).
 *
 * Walks <root>/projects/ for slugs that exist at BOTH:
 *   - projects/<slug>/                   (non-brief, plain project dir)
 *   - projects/briefs/<slug>/            (brief project dir)
 *
 * For each duplicate pair, plans (and optionally applies) a merge that
 * collapses the non-brief tree into the brief tree. The brief always wins
 * (the dashboard's listProjects() dedup picks the brief), so the brief
 * directory is the canonical destination.
 *
 * Per-file resolution rules:
 *   - file in src only   → MOVE src/file → dst/file
 *   - file in src + dst, identical bytes (sha-256)
 *                        → REMOVE src/file (no overwrite needed)
 *   - file in src + dst, different bytes
 *                        → prefer newer mtime; if within 60s, WARN and SKIP
 *
 * After per-file resolution, src directories that became empty are removed.
 * The src project root is removed only if it is fully empty after the merge.
 *
 * Usage:
 *   node scripts/migrate-split-projects.mjs            # default --dry-run
 *   node scripts/migrate-split-projects.mjs --dry-run
 *   node scripts/migrate-split-projects.mjs --apply
 *
 * Exit code: 0 always, except on hard errors (unreadable file, FS denied).
 *
 * Design constraints:
 * - Pure Node 20+ stdlib (no npm deps; CLAUDE.md disallows installs).
 * - Deterministic output: same FS state in → same plan out.
 * - Idempotent: running twice in --apply produces no-op the second time.
 */

import {
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  renameSync,
  rmdirSync,
  statSync,
  unlinkSync,
} from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";

const TIE_WINDOW_MS = 60_000;

function organonRoot() {
  // The dashboard lives at <root>/projects/briefs/organon-dashboard/.
  // This script lives at <dashboard>/scripts/migrate-split-projects.mjs.
  const here = path.dirname(new URL(import.meta.url).pathname);
  const candidate = path.resolve(here, "..", "..", "..", "..");
  if (existsSync(path.join(candidate, "CLAUDE.md"))) return candidate;
  // Fallback: assume cwd is repo root
  return process.cwd();
}

function parseArgs(argv) {
  const args = new Set(argv.slice(2));
  if (args.has("--apply") && args.has("--dry-run")) {
    console.error("error: pass --apply OR --dry-run, not both.");
    process.exit(2);
  }
  return { apply: args.has("--apply") };
}

function findDuplicateSlugs(root) {
  const projectsDir = path.join(root, "projects");
  const briefsDir = path.join(projectsDir, "briefs");
  const briefSlugs = new Set();
  if (existsSync(briefsDir)) {
    for (const entry of readdirSync(briefsDir)) {
      const full = path.join(briefsDir, entry);
      try {
        if (statSync(full).isDirectory()) briefSlugs.add(entry);
      } catch { /* ignore */ }
    }
  }
  const dups = [];
  if (!existsSync(projectsDir)) return dups;
  for (const entry of readdirSync(projectsDir)) {
    if (entry === "briefs") continue;
    if (!briefSlugs.has(entry)) continue;
    const srcPath = path.join(projectsDir, entry);
    try {
      if (!statSync(srcPath).isDirectory()) continue;
    } catch { continue; }
    dups.push({
      slug: entry,
      src: srcPath,
      dst: path.join(briefsDir, entry),
    });
  }
  return dups.sort((a, b) => a.slug.localeCompare(b.slug));
}

function listFilesRecursive(dir) {
  const out = [];
  const stack = [dir];
  while (stack.length > 0) {
    const cur = stack.pop();
    let entries;
    try {
      entries = readdirSync(cur, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const e of entries) {
      const full = path.join(cur, e.name);
      if (e.isDirectory()) {
        stack.push(full);
      } else if (e.isFile()) {
        out.push(full);
      } // skip symlinks etc — we don't expect any
    }
  }
  return out.sort();
}

function sha256(filePath) {
  const buf = readFileSync(filePath);
  return createHash("sha256").update(buf).digest("hex");
}

function planForPair(pair, rel) {
  const srcFiles = listFilesRecursive(pair.src);
  const actions = [];
  for (const srcFile of srcFiles) {
    const relPath = path.relative(pair.src, srcFile);
    const dstFile = path.join(pair.dst, relPath);
    if (!existsSync(dstFile)) {
      actions.push({ kind: "MOVE", srcFile, dstFile, rel: relPath });
      continue;
    }
    let srcStat, dstStat;
    try {
      srcStat = statSync(srcFile);
      dstStat = statSync(dstFile);
    } catch (err) {
      actions.push({ kind: "ERROR", srcFile, dstFile, rel: relPath, message: err.message });
      continue;
    }
    if (srcStat.size === dstStat.size && sha256(srcFile) === sha256(dstFile)) {
      actions.push({ kind: "DUPLICATE_REMOVE", srcFile, dstFile, rel: relPath });
      continue;
    }
    const srcMs = srcStat.mtimeMs;
    const dstMs = dstStat.mtimeMs;
    if (Math.abs(srcMs - dstMs) < TIE_WINDOW_MS) {
      actions.push({
        kind: "TIE_SKIP",
        srcFile,
        dstFile,
        rel: relPath,
        srcMs,
        dstMs,
        message: `mtimes within ${TIE_WINDOW_MS}ms (Δ=${Math.round(Math.abs(srcMs - dstMs))}ms); resolve manually then re-run`,
      });
      continue;
    }
    if (srcMs > dstMs) {
      actions.push({ kind: "OVERWRITE_NEWER_SRC", srcFile, dstFile, rel: relPath });
    } else {
      actions.push({ kind: "DST_NEWER_REMOVE_SRC", srcFile, dstFile, rel: relPath });
    }
  }
  return actions;
}

function ensureDirSync(dir) {
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
}

function applyAction(act) {
  switch (act.kind) {
    case "MOVE": {
      ensureDirSync(path.dirname(act.dstFile));
      renameSync(act.srcFile, act.dstFile);
      return;
    }
    case "DUPLICATE_REMOVE":
    case "DST_NEWER_REMOVE_SRC": {
      unlinkSync(act.srcFile);
      return;
    }
    case "OVERWRITE_NEWER_SRC": {
      unlinkSync(act.dstFile);
      ensureDirSync(path.dirname(act.dstFile));
      renameSync(act.srcFile, act.dstFile);
      return;
    }
    case "TIE_SKIP":
    case "ERROR":
      return; // intentionally no-op
    default:
      throw new Error(`unknown action kind: ${act.kind}`);
  }
}

function pruneEmptyDirs(rootPath) {
  // Walk depth-first; remove any empty directory.
  const stack = [{ p: rootPath, visited: false }];
  const order = [];
  while (stack.length > 0) {
    const top = stack[stack.length - 1];
    if (!top.visited) {
      top.visited = true;
      let entries;
      try {
        entries = readdirSync(top.p, { withFileTypes: true });
      } catch {
        stack.pop();
        continue;
      }
      for (const e of entries) {
        if (e.isDirectory()) stack.push({ p: path.join(top.p, e.name), visited: false });
      }
    } else {
      order.push(top.p);
      stack.pop();
    }
  }
  for (const p of order) {
    try {
      const entries = readdirSync(p);
      if (entries.length === 0) rmdirSync(p);
    } catch { /* ignore */ }
  }
  // And the root itself
  try {
    if (existsSync(rootPath) && readdirSync(rootPath).length === 0) {
      rmdirSync(rootPath);
    }
  } catch { /* ignore */ }
}

function summarizePlan(pair, actions, rel) {
  const counts = {
    MOVE: 0, DUPLICATE_REMOVE: 0, OVERWRITE_NEWER_SRC: 0,
    DST_NEWER_REMOVE_SRC: 0, TIE_SKIP: 0, ERROR: 0,
  };
  for (const a of actions) counts[a.kind]++;
  const blocked = counts.TIE_SKIP + counts.ERROR;
  const safe = counts.MOVE + counts.DUPLICATE_REMOVE +
               counts.OVERWRITE_NEWER_SRC + counts.DST_NEWER_REMOVE_SRC;
  console.log(`\n${pair.slug}: ${rel(pair.src)} → ${rel(pair.dst)}`);
  console.log(`  ${actions.length} files: ${safe} safe, ${blocked} blocked`);
  for (const a of actions) {
    if (a.kind === "TIE_SKIP" || a.kind === "ERROR") {
      console.log(`  [${a.kind}] ${a.rel} — ${a.message}`);
    } else {
      console.log(`  [${a.kind}] ${a.rel}`);
    }
  }
}

function main() {
  const { apply } = parseArgs(process.argv);
  const root = organonRoot();
  console.log(`organon-root: ${root}`);
  console.log(`mode: ${apply ? "APPLY" : "DRY-RUN"}`);

  const pairs = findDuplicateSlugs(root);
  if (pairs.length === 0) {
    console.log("\nNo duplicate slugs found. Nothing to do.");
    return;
  }
  console.log(`\nFound ${pairs.length} duplicate slug(s):`);
  for (const p of pairs) console.log(`  ${p.slug}`);

  const rel = (abs) => path.relative(root, abs);
  let totalApplied = 0;
  let totalBlocked = 0;
  for (const pair of pairs) {
    const actions = planForPair(pair, rel);
    summarizePlan(pair, actions, rel);

    if (!apply) continue;

    let applied = 0;
    let blocked = 0;
    for (const act of actions) {
      if (act.kind === "TIE_SKIP" || act.kind === "ERROR") {
        blocked++;
        continue;
      }
      try {
        applyAction(act);
        applied++;
      } catch (err) {
        console.error(`  apply-failed: [${act.kind}] ${act.rel} — ${err.message}`);
        blocked++;
      }
    }
    pruneEmptyDirs(pair.src);
    const remaining = existsSync(pair.src);
    console.log(`  applied: ${applied}, blocked: ${blocked}, src-remaining: ${remaining}`);
    if (remaining) {
      try {
        const left = listFilesRecursive(pair.src);
        if (left.length > 0) {
          console.log(`  src has ${left.length} unresolved file(s); re-run after manual resolution.`);
        }
      } catch { /* ignore */ }
    }
    totalApplied += applied;
    totalBlocked += blocked;
  }

  if (!apply) {
    console.log(`\nDry-run complete. Re-run with --apply to perform the merge.`);
  } else {
    console.log(`\nApply complete. ${totalApplied} action(s) applied, ${totalBlocked} blocked.`);
  }
}

main();
