#!/usr/bin/env node
/**
 * scripts/backfill-papers.mjs — Phase 3 (fix-sprint).
 *
 * One-time backfill for paper JSONs persisted before Phase 3:
 *   1. Strip the redundant source-prefix from `id` and `source_ids.<source>`
 *      (`pmid-pmid:41889156` → `pmid-41889156`,
 *       `s2-s2:abc...`        → `s2-abc...`,
 *       `arxiv-arxiv:2401...` → `arxiv-2401...`,
 *       `openalex-https://openalex.org/W4400000000` → `openalex-W4400000000`).
 *   2. Decode HTML entities + strip safe-inline tags in `journal` and
 *      `abstract` (PubMed XML and OpenAlex both ship encoded fields).
 *   3. Compute `cite_key` (surname-based, collision-aware: a/b/c suffix per
 *      library) for every paper that doesn't already have one.
 *   4. Update `library_path` to match the renamed id.
 *   5. Rename the on-disk JSON file to match the new id.
 *   6. Update sibling hypotheses/<hyp_id>/hypothesis.json `paper_ids` to
 *      track renames.
 *
 * Walks every `<root>/projects/**\/papers/*.json` under the organon root.
 * Idempotent: re-running after --apply finds nothing to do.
 *
 * Usage:
 *   node scripts/backfill-papers.mjs              # default --dry-run
 *   node scripts/backfill-papers.mjs --dry-run
 *   node scripts/backfill-papers.mjs --apply
 *
 * Pure Node 20+ stdlib (no npm deps; CLAUDE.md disallows installs).
 */

import {
  existsSync,
  readFileSync,
  readdirSync,
  renameSync,
  statSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";

// --- Helpers (mirrored from src/lib/lit/cite-key.ts + html-decode.ts so this
// --- script doesn't need a TS build step. Keep in sync if either changes.

const NAMED_ENTITIES = {
  "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&apos;": "'",
  "&nbsp;": " ", "&copy;": "©", "&reg;": "®", "&trade;": "™",
  "&hellip;": "…", "&mdash;": "—", "&ndash;": "–",
  "&lsquo;": "‘", "&rsquo;": "’", "&ldquo;": "“", "&rdquo;": "”",
  "&times;": "×", "&plusmn;": "±", "&micro;": "µ", "&deg;": "°",
};

function decodeEntities(input) {
  if (!input || input.indexOf("&") === -1) return input;
  return input.replace(/&(#x[0-9a-fA-F]+|#\d+|[a-zA-Z][a-zA-Z0-9]+);/g, (raw, body) => {
    if (NAMED_ENTITIES[raw]) return NAMED_ENTITIES[raw];
    if (typeof body === "string") {
      if (body.startsWith("#x") || body.startsWith("#X")) {
        const code = parseInt(body.slice(2), 16);
        if (Number.isFinite(code) && code > 0 && code < 0x110000) {
          try { return String.fromCodePoint(code); } catch { return raw; }
        }
      } else if (body.startsWith("#")) {
        const code = parseInt(body.slice(1), 10);
        if (Number.isFinite(code) && code > 0 && code < 0x110000) {
          try { return String.fromCodePoint(code); } catch { return raw; }
        }
      }
    }
    return raw;
  });
}

function stripSafeTags(input) {
  if (!input || input.indexOf("<") === -1) return input;
  return input.replace(/<\/?(b|i|em|strong|sub|sup)(\s[^>]*)?>/gi, "");
}

function firstAuthorSurname(paper) {
  const a = paper.authors?.[0]?.trim();
  if (!a) return "Anonymous";
  if (a.includes(",")) {
    const last = a.split(",")[0]?.trim();
    return last || "Anonymous";
  }
  const words = a.split(/\s+/).filter(Boolean);
  return words[words.length - 1] || "Anonymous";
}

function paperToCiteKey(paper, existingKeys) {
  const surname = firstAuthorSurname(paper).replace(/[^A-Za-z0-9]/g, "");
  const year = paper.year && paper.year > 0 ? String(paper.year) : "n.d.";
  const base = `${surname || "Unknown"}${year}`;
  if (!existingKeys.has(base)) return base;
  for (let i = 1; i < 26; i += 1) {
    const candidate = `${base}${String.fromCharCode(97 + i)}`;
    if (!existingKeys.has(candidate)) return candidate;
  }
  return `${base}-${(paper.id || "x").slice(0, 8)}`;
}

// --- Source-prefix normalization

const PREFIX_FIXES = [
  // [source, oldPrefixedRegex, replacement]
  // Old `id` form: `pmid-pmid:NNN` → `pmid-NNN`. The colon and second
  // `pmid:` are the redundant bits.
  { source: "pmid", re: /^pmid-pmid:/, fix: "pmid-" },
  { source: "arxiv", re: /^arxiv-arxiv:/, fix: "arxiv-" },
  { source: "s2", re: /^s2-s2:/, fix: "s2-" },
  // OpenAlex full URL form → bare W-id form.
  { source: "openalex", re: /^openalex-https?:\/\/openalex\.org\//i, fix: "openalex-" },
];

function normalizeId(oldId) {
  for (const f of PREFIX_FIXES) {
    if (f.re.test(oldId)) {
      return { newId: oldId.replace(f.re, f.fix), changed: true, source: f.source };
    }
  }
  return { newId: oldId, changed: false, source: null };
}

function normalizeSourceIds(sourceIds) {
  if (!sourceIds || typeof sourceIds !== "object") return { fixed: sourceIds, changed: false };
  const out = { ...sourceIds };
  let changed = false;
  if (typeof out.pmid === "string" && out.pmid.startsWith("pmid:")) {
    out.pmid = out.pmid.slice("pmid:".length);
    changed = true;
  }
  if (typeof out.arxiv === "string" && out.arxiv.startsWith("arxiv:")) {
    out.arxiv = out.arxiv.slice("arxiv:".length);
    changed = true;
  }
  if (typeof out.s2 === "string" && out.s2.startsWith("s2:")) {
    out.s2 = out.s2.slice("s2:".length);
    changed = true;
  }
  if (typeof out.openalex === "string") {
    const m = out.openalex.match(/^https?:\/\/openalex\.org\/(.+)$/i);
    if (m) {
      out.openalex = m[1];
      changed = true;
    }
  }
  return { fixed: out, changed };
}

// --- FS walk

function organonRoot() {
  const here = path.dirname(new URL(import.meta.url).pathname);
  const candidate = path.resolve(here, "..", "..", "..", "..");
  if (existsSync(path.join(candidate, "CLAUDE.md"))) return candidate;
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

function listProjectPapersDirs(root) {
  // Returns the set of every `projects/**/papers/` dir we can find,
  // i.e. `projects/<slug>/papers/` and `projects/briefs/<slug>/papers/`.
  const out = [];
  const projectsDir = path.join(root, "projects");
  if (!existsSync(projectsDir)) return out;
  const briefsDir = path.join(projectsDir, "briefs");

  const scan = (parent) => {
    let entries;
    try {
      entries = readdirSync(parent, { withFileTypes: true });
    } catch {
      return;
    }
    for (const e of entries) {
      if (!e.isDirectory()) continue;
      if (e.name === "node_modules" || e.name.startsWith(".")) continue;
      const full = path.join(parent, e.name);
      if (full === briefsDir) continue;
      const candidate = path.join(full, "papers");
      if (existsSync(candidate)) {
        try { if (statSync(candidate).isDirectory()) out.push({ projectPath: full, papersDir: candidate }); }
        catch { /* ignore */ }
      }
    }
  };
  scan(projectsDir);
  scan(briefsDir);
  return out.sort((a, b) => a.papersDir.localeCompare(b.papersDir));
}

// --- Per-library plan

function planLibrary(papersDir) {
  const files = readdirSync(papersDir).filter((f) => f.endsWith(".json"));
  const papers = [];
  for (const f of files.sort()) {
    const full = path.join(papersDir, f);
    let raw;
    try {
      raw = JSON.parse(readFileSync(full, "utf8"));
    } catch (err) {
      console.warn(`  [SKIP] ${f}: parse failed (${err.message})`);
      continue;
    }
    if (raw?._artifact !== "paper" || typeof raw.id !== "string") continue;
    papers.push({ file: f, full, paper: raw });
  }

  // Pass 1: id rename + source_ids fix.
  const renames = new Map(); // oldId → newId
  const updates = []; // { full, oldFile, newFile, newPaper, changes: [...] }

  for (const { file, full, paper } of papers) {
    const changes = [];
    const { newId, changed: idChanged } = normalizeId(paper.id);
    const { fixed: newSourceIds, changed: srcChanged } = normalizeSourceIds(paper.source_ids);
    let newPaper = { ...paper };
    if (idChanged) {
      changes.push(`id ${paper.id} → ${newId}`);
      newPaper.id = newId;
      renames.set(paper.id, newId);
    }
    if (srcChanged) {
      changes.push("source_ids prefix stripped");
      newPaper.source_ids = newSourceIds;
    }

    // HTML entity decode
    if (typeof newPaper.journal === "string") {
      const cleaned = stripSafeTags(decodeEntities(newPaper.journal));
      if (cleaned !== newPaper.journal) {
        changes.push("journal HTML entities decoded");
        newPaper.journal = cleaned;
      }
    }
    if (typeof newPaper.abstract === "string") {
      const cleaned = stripSafeTags(decodeEntities(newPaper.abstract));
      if (cleaned !== newPaper.abstract) {
        changes.push("abstract HTML entities decoded");
        newPaper.abstract = cleaned;
      }
    }

    // library_path tracks the renamed file
    const oldFile = full;
    const newFile = path.join(papersDir, `${newPaper.id}.json`);
    if (newFile !== oldFile) {
      // library_path may also be wrong now — recompute relative to organon root
      const root = organonRoot();
      const newRel = path.relative(root, newFile);
      if (newPaper.library_path !== newRel) {
        changes.push(`library_path → ${newRel}`);
        newPaper.library_path = newRel;
      }
    }

    updates.push({ file, oldFile, newFile, newPaper, changes });
  }

  // Pass 2: cite_key. Process in deterministic order so collision suffix
  // assignment is reproducible (sort by year ASC, then id ASC).
  updates.sort((a, b) => {
    const ay = a.newPaper.year ?? 0;
    const by = b.newPaper.year ?? 0;
    if (ay !== by) return ay - by;
    return a.newPaper.id.localeCompare(b.newPaper.id);
  });
  const usedKeys = new Set(
    updates
      .map((u) => u.newPaper.cite_key)
      .filter((k) => typeof k === "string" && k.length > 0),
  );
  for (const u of updates) {
    if (typeof u.newPaper.cite_key === "string" && u.newPaper.cite_key.length > 0) continue;
    const key = paperToCiteKey(u.newPaper, usedKeys);
    u.newPaper.cite_key = key;
    u.changes.push(`cite_key = ${key}`);
    usedKeys.add(key);
  }

  // Re-sort updates by oldFile name for stable output.
  updates.sort((a, b) => a.oldFile.localeCompare(b.oldFile));
  return { updates, renames };
}

function applyLibrary(updates) {
  for (const u of updates) {
    if (u.changes.length === 0) continue;
    // Write new file atomically.
    const tmp = u.newFile + ".tmp";
    writeFileSync(tmp, JSON.stringify(u.newPaper, null, 2), "utf8");
    renameSync(tmp, u.newFile);
    // Remove old file if name changed.
    if (u.oldFile !== u.newFile) {
      try { unlinkSync(u.oldFile); } catch { /* ignore */ }
    }
  }
}

// --- Hypothesis paper_ids tracking

function listHypothesisFiles(projectPath) {
  const dir = path.join(projectPath, "hypotheses");
  if (!existsSync(dir)) return [];
  const out = [];
  for (const entry of readdirSync(dir)) {
    if (!entry.startsWith("hyp-")) continue;
    const file = path.join(dir, entry, "hypothesis.json");
    if (existsSync(file)) out.push(file);
  }
  return out;
}

function planHypothesisRenames(hypFiles, renames) {
  const plan = [];
  for (const file of hypFiles) {
    let raw;
    try { raw = JSON.parse(readFileSync(file, "utf8")); }
    catch { continue; }
    if (!Array.isArray(raw.paper_ids)) continue;
    const newIds = raw.paper_ids.map((id) => renames.get(id) ?? id);
    const changed = newIds.some((id, i) => id !== raw.paper_ids[i]);
    if (changed) {
      plan.push({ file, oldIds: raw.paper_ids, newIds, raw });
    }
  }
  return plan;
}

function applyHypothesisRenames(plan) {
  for (const p of plan) {
    const updated = { ...p.raw, paper_ids: p.newIds };
    const tmp = p.file + ".tmp";
    writeFileSync(tmp, JSON.stringify(updated, null, 2), "utf8");
    renameSync(tmp, p.file);
  }
}

// --- main

function main() {
  const { apply } = parseArgs(process.argv);
  const root = organonRoot();
  console.log(`organon-root: ${root}`);
  console.log(`mode: ${apply ? "APPLY" : "DRY-RUN"}`);

  const libs = listProjectPapersDirs(root);
  if (libs.length === 0) {
    console.log("\nNo papers/ directories found. Nothing to do.");
    return;
  }

  const rel = (abs) => path.relative(root, abs);
  let totalPaperChanges = 0;
  let totalHypChanges = 0;

  for (const { projectPath, papersDir } of libs) {
    const { updates, renames } = planLibrary(papersDir);
    const changedUpdates = updates.filter((u) => u.changes.length > 0);
    if (changedUpdates.length === 0) {
      // Still surface the library so the user sees we walked it.
      continue;
    }
    console.log(`\n${rel(papersDir)}:`);
    for (const u of changedUpdates) {
      const renameStr = u.oldFile !== u.newFile
        ? `${path.basename(u.oldFile)} → ${path.basename(u.newFile)}`
        : path.basename(u.oldFile);
      console.log(`  ${renameStr}`);
      for (const c of u.changes) console.log(`    · ${c}`);
    }
    totalPaperChanges += changedUpdates.length;

    // Hypothesis paper_ids that point at renamed papers.
    const hypFiles = listHypothesisFiles(projectPath);
    const hypPlan = planHypothesisRenames(hypFiles, renames);
    if (hypPlan.length > 0) {
      console.log(`  hypotheses/ paper_ids tracking renames:`);
      for (const h of hypPlan) {
        console.log(`    ${rel(h.file)}`);
        for (let i = 0; i < h.oldIds.length; i += 1) {
          if (h.oldIds[i] !== h.newIds[i]) {
            console.log(`      paper_ids[${i}]: ${h.oldIds[i]} → ${h.newIds[i]}`);
          }
        }
      }
      totalHypChanges += hypPlan.length;
    }

    if (apply) {
      applyLibrary(changedUpdates);
      applyHypothesisRenames(hypPlan);
    }
  }

  if (!apply) {
    console.log(`\nDry-run complete. ${totalPaperChanges} paper change(s), ${totalHypChanges} hypothesis update(s). Re-run with --apply to perform the backfill.`);
  } else {
    console.log(`\nApply complete. ${totalPaperChanges} paper change(s), ${totalHypChanges} hypothesis update(s).`);
  }
}

main();
