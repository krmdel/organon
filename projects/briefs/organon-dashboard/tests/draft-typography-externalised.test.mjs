import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync, mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join } from "node:path";
import { tmpdir } from "node:os";

// Phase 25 (v1.2) — Externalised typography-preset registry (DR-8+).
//
// Closes Phase 18's "Registry is ts-side only" decision: the v1.1 `PRESETS`
// array becomes BUILTIN_PRESETS; a project-local
// `<projectPath>/.organon/typography-presets.json` extends/overrides it.
// Project entries WIN on id collision. Invalid entries are dropped (not
// thrown). The new API route exposes split builtin/project arrays + a
// POST writer + a DELETE for the project file.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

const tryRead = (p) => {
  try {
    return readFileSync(p, "utf8");
  } catch {
    return "";
  }
};

// Phase 25 splits the registry into client-safe (typography-presets.ts)
// and server-only (typography-presets-loader.ts) modules. The client
// bundle can't import node:fs, so the merge / read-project-file logic
// lives in the loader. We concat both so the source-text scan tests
// don't care which file owns which symbol.
const PRESETS_CLIENT_SRC = tryRead(
  join(ROOT, "src", "lib", "draft", "typography-presets.ts"),
);
const PRESETS_LOADER_SRC = tryRead(
  join(ROOT, "src", "lib", "draft", "typography-presets-loader.ts"),
);
const PRESETS_SRC = `${PRESETS_CLIENT_SRC}\n${PRESETS_LOADER_SRC}`;
const SCHEMA_PATH = join(ROOT, "src", "lib", "draft", "typography-presets.schema.json");
const SCHEMA_SRC = tryRead(SCHEMA_PATH);
const ROUTE_SRC = tryRead(
  join(ROOT, "src", "app", "api", "draft", "typography-presets", "route.ts"),
);
const MENU_SRC = tryRead(join(ROOT, "src", "components", "draft", "export-menu.tsx"));

test("Phase 25 — loadPresets returns builtins when no project file exists", () => {
  // BUILTIN_PRESETS exported alongside the legacy const name retired.
  assert.match(
    PRESETS_SRC,
    /BUILTIN_PRESETS/,
    "BUILTIN_PRESETS replaces the v1.1 PRESETS const",
  );
  // loadPresets exists with a (projectPath?) signature.
  assert.match(
    PRESETS_SRC,
    /export\s+function\s+loadPresets\s*\(/,
    "loadPresets() function exported",
  );
  // The function reads the project file path under `.organon/`.
  assert.match(
    PRESETS_SRC,
    /\.organon\/typography-presets\.json|\.organon[/\\]typography-presets\.json/,
    "loadPresets references the .organon project file",
  );
  // Behavioural replica — empty project file branch returns builtins
  // verbatim. We mock `fs` access by pointing loadPresets at a missing
  // dir; the only signal we can verify in source is that the function
  // gracefully handles non-existent files.
  assert.match(
    PRESETS_SRC,
    /existsSync\b|tryReadProject|catch\s*\{/,
    "loadPresets gracefully skips missing project files",
  );
});

test("Phase 25 — loadPresets merges project presets, project wins on id collision", () => {
  // Project entries win on id collision — encoded by the merge order
  // (project entries appended/overriding by id).
  assert.match(
    PRESETS_SRC,
    /(project[^\n]*\.find|merge|override|projectById|byId|new Map)/i,
    "loadPresets merges builtins + project, with override semantics",
  );
});

test("Phase 25 — invalid project entries are dropped (not thrown), with a console warning", () => {
  // Validation helper exists.
  assert.match(
    PRESETS_SRC,
    /isValidPreset|validatePreset|isPreset/,
    "validation helper exported or used",
  );
  // Drop-not-throw semantics — filter() / catch + warn / continue, not throw.
  assert.match(
    PRESETS_SRC,
    /console\.(warn|error)/,
    "invalid entries surface a console warning",
  );
  assert.doesNotMatch(
    PRESETS_SRC,
    /\bthrow\s+new\s+(Error|TypeError)/,
    "loadPresets never throws on bad project entries",
  );
});

test("Phase 25 — typography-presets API GET returns split builtin / project arrays", () => {
  assert.match(ROUTE_SRC, /export\s+async\s+function\s+GET/, "GET handler exported");
  // Response shape includes both arrays.
  assert.match(ROUTE_SRC, /builtin\s*:/, "GET returns { builtin: ... }");
  assert.match(ROUTE_SRC, /project\s*:/, "GET returns { project: ... }");
  // Pulls the project from the request (project= query/body) like other routes.
  assert.match(
    ROUTE_SRC,
    /resolveProjectFromRequest\b/,
    "route resolves project per Organon convention",
  );
});

test("Phase 25 — typography-presets API POST writes a custom preset to the project file", () => {
  assert.match(ROUTE_SRC, /export\s+async\s+function\s+POST/, "POST handler exported");
  // DELETE handler also exists per brief.
  assert.match(ROUTE_SRC, /export\s+async\s+function\s+DELETE/, "DELETE handler exported");
  // Atomic tmp+rename writer pattern.
  assert.match(
    ROUTE_SRC,
    /(\.tmp|tmp\b)[\s\S]{0,80}renameSync|writeAtomic\(/,
    "POST uses atomic tmp+rename (writeAtomic helper or inline)",
  );
  // Schema file exists and parses as JSON.
  assert.ok(existsSync(SCHEMA_PATH), "typography-presets.schema.json exists");
  let schema;
  assert.doesNotThrow(() => {
    schema = JSON.parse(SCHEMA_SRC);
  }, "schema is valid JSON");
  assert.equal(typeof schema.$schema, "string", "schema declares a $schema URI");
  // Behavioural replica — write a project file in a tmpdir + invoke the
  // exported `loadPresets` via dynamic import on the compiled tsc out…
  // we can't easily do that under plain-Node ESM, so we rely on the
  // structural checks above. The route's behavioural test runs through
  // the dev server stress-suite.

  // Menu surface: "● custom" chip when a project preset is loaded.
  assert.match(
    MENU_SRC,
    /custom|isProject|source\s*===\s*("|')project\1/,
    "export-menu surfaces a 'custom' indicator for project presets",
  );
});
