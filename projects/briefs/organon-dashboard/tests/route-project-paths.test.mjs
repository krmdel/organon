import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 2 fix-sprint regression tests:
//   1. assertWithinProject helper exists and rejects out-of-project paths.
//   2. Every persister imports + calls the invariant before its atomic write.
//   3. No source file under src/app/api/ or src/lib/ contains a
//      slug-interpolated `projects/${...}` template-literal path string.
//   4. The migration script exposes --dry-run + --apply, lives at
//      scripts/migrate-split-projects.mjs.
//   5. Runtime: the dogfood project resolves to the brief tree only;
//      the non-brief sibling has been removed.
//
// Same source-text + tiny FS pattern as Phase 1's regression test.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const ORGANON_ROOT = join(ROOT, "..", "..", "..");
const PROJECTS_SRC = readFileSync(join(ROOT, "src", "lib", "projects.ts"), "utf8");

const PERSISTERS = [
  // [file, callsite count expected]
  ["src/lib/lit/library.ts", 1],
  ["src/lib/data/files.ts", 1],
  ["src/lib/figures/store.ts", 1],
  ["src/lib/results/store.ts", 1],
  ["src/lib/hypothesis/store.ts", 1],
  ["src/lib/hypothesis/critiques.ts", 1],
  ["src/lib/draft/store.ts", 3],          // metaPath + sectionFile + sidecar
  ["src/lib/images/versions.ts", 1],      // appendVersion sidecar
];

test("assertWithinProject is exported with the expected signature", () => {
  assert.match(
    PROJECTS_SRC,
    /export function assertWithinProject\(\s*target: string,\s*projectPath: string,?\s*\): void/,
    "signature must accept (target, projectPath) and return void",
  );
  // Implementation must resolve both paths and use a startsWith + sep check.
  assert.match(
    PROJECTS_SRC,
    /path\.resolve\(target\)/,
    "must resolve the target path",
  );
  assert.match(
    PROJECTS_SRC,
    /path\.resolve\(projectPath\)/,
    "must resolve the project path",
  );
  assert.match(
    PROJECTS_SRC,
    /\.startsWith\(p \+ path\.sep\)/,
    "must use prefix-with-separator check (avoids /a-foo matching /a)",
  );
  assert.match(
    PROJECTS_SRC,
    /throw new Error\(/,
    "must throw on out-of-project paths",
  );
});

test("every persister imports + calls assertWithinProject", () => {
  for (const [relFile, expectedCalls] of PERSISTERS) {
    const src = readFileSync(join(ROOT, relFile), "utf8");
    assert.match(
      src,
      /import \{[^}]*assertWithinProject[^}]*\} from "\.\.\/projects"/,
      `${relFile} must import assertWithinProject from ../projects`,
    );
    const calls = src.match(/assertWithinProject\(/g) ?? [];
    // The import line uses the bare identifier (no `(`), so the regex only
    // counts true callsites. Expect at least the documented count per file.
    assert.ok(
      calls.length >= expectedCalls,
      `${relFile} expected ≥ ${expectedCalls} callsite(s); saw ${calls.length}`,
    );
  }
});

test("no slug-interpolated `projects/${...}` paths in src/app/api or src/lib", () => {
  const offenders = [];
  // Match `projects/${...}` inside any string-context template literal.
  // This is the exact bug we shipped Phase 2 to kill: see route.ts:44-45 pre-fix.
  const re = /projects\/\$\{[^}]+\}/g;

  function scan(dir) {
    for (const entry of readdirSync(dir)) {
      const full = join(dir, entry);
      const stat = statSync(full);
      if (stat.isDirectory()) {
        scan(full);
        continue;
      }
      if (!entry.endsWith(".ts") && !entry.endsWith(".tsx")) continue;
      const src = readFileSync(full, "utf8");
      // Strip `// ...` line comments and `/* ... */` block comments so JSDoc
      // examples don't false-positive. We don't strip strings — that's the
      // whole point: a `projects/${slug}/...` STRING is the bug.
      const stripped = src
        .replace(/\/\*[\s\S]*?\*\//g, "")
        .replace(/\/\/[^\n]*/g, "");
      const matches = stripped.match(re);
      if (matches) {
        offenders.push({ file: full.replace(ROOT + "/", ""), matches });
      }
    }
  }
  scan(join(ROOT, "src", "app", "api"));
  scan(join(ROOT, "src", "lib"));

  assert.deepEqual(
    offenders,
    [],
    `Slug-interpolated path strings still present:\n${JSON.stringify(offenders, null, 2)}`,
  );
});

test("migrate-split-projects.mjs exists with --dry-run and --apply modes", () => {
  const scriptPath = join(ROOT, "scripts", "migrate-split-projects.mjs");
  assert.ok(existsSync(scriptPath), "scripts/migrate-split-projects.mjs must exist");
  const src = readFileSync(scriptPath, "utf8");
  assert.match(src, /--dry-run/, "must mention --dry-run");
  assert.match(src, /--apply/, "must mention --apply");
  // Apply path must be opt-in (not the default).
  assert.match(
    src,
    /apply: args\.has\("--apply"\)/,
    "apply must be a boolean flag, dry-run is the default",
  );
});

test("dogfood split has been resolved (brief only, no non-brief sibling)", () => {
  // Post-migration, the brief tree exists and is canonical.
  const briefPath = join(ORGANON_ROOT, "projects", "briefs", "dogfood-glp1-weight-regain");
  const nonBriefPath = join(ORGANON_ROOT, "projects", "dogfood-glp1-weight-regain");
  // Brief should still be there.
  assert.ok(existsSync(briefPath), "brief project tree must exist post-migration");
  // Non-brief sibling must be gone.
  assert.equal(
    existsSync(nonBriefPath),
    false,
    "non-brief sibling tree must be removed after migration",
  );
  // Brief tree should now hold the merged artifacts.
  for (const dir of ["data", "figures", "manuscripts", "results", "papers", "hypotheses"]) {
    assert.ok(
      existsSync(join(briefPath, dir)),
      `brief tree must contain merged ${dir}/ after migration`,
    );
  }
});
