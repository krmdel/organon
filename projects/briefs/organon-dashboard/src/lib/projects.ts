import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { briefsDir, organonRoot, projectsDir } from "./paths";

export type BriefMeta = {
  status?: string;
  level?: number;
  created?: string;
};

export type Project = {
  slug: string;
  name: string;
  path: string;
  isRoot: boolean;
  isBrief: boolean;
  brief?: BriefMeta;
};

const ROOT_SLUG = "__root__";

/**
 * Discover Organon projects per PHASE_1_TASKS.md D1:
 *  - synthetic `__root__` representing the Organon repo itself
 *  - every non-hidden directory under `<root>/projects/`
 *  - briefs under `<root>/projects/briefs/<slug>/` are surfaced with `isBrief: true`
 *
 * Skipped: hidden dirs (.git, .organon, etc.), `node_modules`, files at the top level
 * of `projects/` (e.g. screenshot PNGs). Synthetic-root entry is always first.
 */
export function listProjects(): Project[] {
  const root = organonRoot();
  const out: Project[] = [
    {
      slug: ROOT_SLUG,
      name: titleCase(path.basename(root)),
      path: root,
      isRoot: true,
      isBrief: false,
    },
  ];

  const pdir = projectsDir();
  if (existsSync(pdir)) {
    const entries = readdirSync(pdir).sort();
    for (const entry of entries) {
      if (shouldSkipEntry(entry)) continue;
      const full = path.join(pdir, entry);
      try {
        if (!statSync(full).isDirectory()) continue;
      } catch {
        continue;
      }
      // Skip the briefs/ container itself — its children are added below.
      if (full === briefsDir()) continue;
      out.push({
        slug: entry,
        name: titleCase(entry),
        path: full,
        isRoot: false,
        isBrief: false,
      });
    }
  }

  const bdir = briefsDir();
  if (existsSync(bdir)) {
    const entries = readdirSync(bdir).sort();
    for (const entry of entries) {
      if (shouldSkipEntry(entry)) continue;
      const full = path.join(bdir, entry);
      try {
        if (!statSync(full).isDirectory()) continue;
      } catch {
        continue;
      }
      const brief = readBriefMeta(path.join(full, "brief.md"));
      out.push({
        slug: entry,
        name: titleCase(entry),
        path: full,
        isRoot: false,
        isBrief: true,
        brief,
      });
    }
  }

  // Phase 1 fix-sprint: dedup by slug. When the same slug exists at both
  // `projects/{slug}/` and `projects/briefs/{slug}/`, the brief wins. Without
  // this, `find((p) => p.slug === slug)` returned whichever was added first
  // (non-brief, since loop 1 runs before loop 2), permanently flipping
  // `resolveProject` to the wrong tree once a stray non-brief sibling appeared.
  // See critic finding C1 in FIXPLAN_CRITIQUE.md.
  const bySlug = new Map<string, Project>();
  for (const p of out) {
    const existing = bySlug.get(p.slug);
    if (!existing) {
      bySlug.set(p.slug, p);
      continue;
    }
    if (p.isBrief && !existing.isBrief) {
      console.warn(
        `[projects] Duplicate slug "${p.slug}" — both ${existing.path} ` +
        `and ${p.path} exist. Brief wins; run scripts/migrate-split-projects.mjs ` +
        "(Phase 2) to merge.",
      );
      bySlug.set(p.slug, p);
    } else if (!p.isBrief && existing.isBrief) {
      console.warn(
        `[projects] Duplicate slug "${p.slug}" — both ${existing.path} ` +
        `and ${p.path} exist. Brief wins; run scripts/migrate-split-projects.mjs ` +
        "(Phase 2) to merge.",
      );
      // existing already wins (it's the brief) — leave map entry as-is.
    }
    // If both are briefs (impossible: readdir is per-dir) or both are non-briefs
    // (impossible for the same reason), keep the first. No warn — it shouldn't happen.
  }
  return [...bySlug.values()];
}

export function resolveProject(slug: string): Project | null {
  return listProjects().find((p) => p.slug === slug) ?? null;
}

/**
 * Resolve the active project from an incoming request. Priority order:
 *   1. URL query string `?project=<slug>`
 *   2. Body slug — caller passes the already-extracted value from either
 *      a parsed JSON body's `project` field OR a multipart form field.
 *      The helper is body-shape-agnostic by design; caller does the parse.
 *   3. Referer URL's `?project=<slug>`
 *   4. Strict mode (Phase 8): return null. The route's existing
 *      `if (!project) return 404` arm refuses the write.
 *
 * Phase 1 (fix-sprint) consolidated ad-hoc resolution across 25 API routes
 * with a soft `__root__` default + console.warn. Phase 8 (fix-sprint) flips
 * to strict mode: silent `__root__` scribbles are exactly the class of bug
 * Phases 2 + 3 spent atomic commits closing. The audit confirmed every
 * client caller already passes `project=` (query or body); flipping the
 * default surfaces any future regression as an explicit 404 rather than a
 * cross-project write.
 */
export function resolveProjectFromRequest(
  request: Request,
  bodyProject?: string | null,
): Project | null {
  const url = new URL(request.url);
  let slug: string | null = url.searchParams.get("project");
  if (!slug && typeof bodyProject === "string" && bodyProject) {
    slug = bodyProject;
  }
  if (!slug) {
    const ref = request.headers.get("referer");
    if (ref) {
      try {
        const fromRef = new URL(ref).searchParams.get("project");
        if (fromRef) slug = fromRef;
      } catch {
        /* malformed referer — ignore */
      }
    }
  }
  if (!slug) {
    // Phase 8 strict mode. Caller MUST supply project via query / body / referer.
    // Returning null lets the route's `if (!project) return 404` arm refuse
    // the request without falling through to a silent `__root__` default.
    return null;
  }
  return resolveProject(slug);
}

/**
 * Phase 2 (fix-sprint) invariant: a write-target absolute path must live
 * under the resolved project root. Catches any future caller that constructs
 * a destination via slug interpolation (e.g. `projects/${slug}/figures/...`)
 * instead of `project.path` + the per-domain helpers (`figureDir`,
 * `libraryDir`, …). No-op when the path is already correct, throws otherwise.
 *
 * Call from every persister immediately before the atomic write. The cost is
 * one `path.resolve` + one prefix check per write; negligible against the
 * filesystem operation that follows.
 */
export function assertWithinProject(target: string, projectPath: string): void {
  const t = path.resolve(target);
  const p = path.resolve(projectPath);
  if (t === p) return;
  if (!t.startsWith(p + path.sep)) {
    throw new Error(
      `Path-construction bug: ${t} is not within project ${p}. ` +
      "Build paths from project.path via figureDir/libraryDir/etc., " +
      "never via slug interpolation.",
    );
  }
}

function shouldSkipEntry(name: string): boolean {
  return (
    name.startsWith(".") ||
    name.startsWith("#") ||
    name === "node_modules" ||
    name.endsWith(".md") ||
    name.endsWith(".png") ||
    name.endsWith(".jpg") ||
    name.endsWith(".pdf")
  );
}

function readBriefMeta(briefPath: string): BriefMeta | undefined {
  if (!existsSync(briefPath)) return undefined;
  let raw: string;
  try {
    raw = readFileSync(briefPath, "utf8");
  } catch {
    return undefined;
  }
  if (!raw.startsWith("---")) return undefined;
  const end = raw.indexOf("\n---", 3);
  if (end === -1) return undefined;
  const block = raw.slice(3, end).replace(/^\n/, "");

  const meta: BriefMeta = {};
  for (const line of block.split("\n")) {
    const m = line.match(/^([a-zA-Z_][\w-]*)\s*:\s*(.*)$/);
    if (!m) continue;
    const [, key, valueRaw] = m;
    const value = stripQuotes(valueRaw.trim());
    if (key === "status") meta.status = value;
    else if (key === "level") {
      const n = Number(value);
      if (Number.isFinite(n)) meta.level = n;
    } else if (key === "created") meta.created = value;
  }
  return meta;
}

function stripQuotes(s: string): string {
  if ((s.startsWith('"') && s.endsWith('"')) || (s.startsWith("'") && s.endsWith("'"))) {
    return s.slice(1, -1);
  }
  return s;
}

function titleCase(slug: string): string {
  return slug
    .split(/[-_]/)
    .filter(Boolean)
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(" ");
}
