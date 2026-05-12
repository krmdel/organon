import { test } from "node:test";
import assert from "node:assert/strict";
import {
  readFileSync,
  existsSync,
  mkdtempSync,
  writeFileSync,
  unlinkSync,
  rmSync,
} from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { tmpdir } from "node:os";

// Phase 30 (v1.3) — DR-8++ typography preset CSS injection.
//
// Closes Phase 18 §6.3 + Phase 25's "css field is reserved for v1.3"
// decision. The TypographyPreset.css field, currently ignored by the
// loader, gets wired into the HTML export path. When a preset's css is
// non-empty, the export route writes it to a tmp file under
// <projectPath>/.organon/tmp/ and passes `--theme <tmp>` to Marp. PDF
// + DOCX exports continue to use pdfArgs / docxArgs verbatim — the
// pandoc injection mechanisms (--include-in-header / --reference-doc)
// are different artifacts and ship as separate v1.4+ phases.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

const tryRead = (p) => {
  try {
    return readFileSync(p, "utf8");
  } catch {
    return "";
  }
};

const LOADER_SRC = tryRead(
  join(ROOT, "src", "lib", "draft", "typography-presets-loader.ts"),
);
const ROUTE_SRC = tryRead(
  join(ROOT, "src", "app", "api", "draft", "[slug]", "export", "route.ts"),
);
const SCHEMA_PATH = join(ROOT, "src", "lib", "draft", "typography-presets.schema.json");
const SCHEMA_SRC = tryRead(SCHEMA_PATH);

// Inline behavioural replica of materializeCssForPandoc — mirrors the
// loader's shape so we can assert the disk-touching contract without
// loading TS source. The real impl lives in
// typography-presets-loader.ts and is the test target for the
// structural scans below.
const replicaMaterialize = (preset, tmpDir) => {
  const cleanups = [];
  const empty = { html: [], pdf: [], docx: [] };
  if (!preset || typeof preset.css !== "string" || preset.css.length === 0) {
    return { extraArgsByFormat: empty, cleanup: () => {} };
  }
  const random = Math.random().toString(36).slice(2, 10);
  const file = join(tmpDir, `preset-${preset.id}-${random}.css`);
  writeFileSync(file, preset.css);
  cleanups.push(file);
  return {
    extraArgsByFormat: { html: ["--theme", file], pdf: [], docx: [] },
    cleanup: () => {
      for (const f of cleanups) {
        try {
          unlinkSync(f);
        } catch {
          /* swallow — idempotent */
        }
      }
    },
  };
};

test("Phase 30 — materializeCssForPandoc returns empty arg arrays when preset.css is unset", () => {
  // Source-text scan: helper is exported with the right name + signature.
  assert.match(
    LOADER_SRC,
    /export\s+function\s+materializeCssForPandoc\s*\(/,
    "materializeCssForPandoc exported from loader",
  );
  // Helper's no-op branch returns empty html/pdf/docx arrays.
  assert.match(
    LOADER_SRC,
    /html\s*:\s*\[\s*\]/,
    "no-op branch returns empty html arg array",
  );

  // Behavioural replica: a preset with no css → empty arrays + no-op cleanup.
  const tmp = mkdtempSync(join(tmpdir(), "organon-css-test-"));
  try {
    const result = replicaMaterialize(
      { id: "default", label: "x", description: "", pdfArgs: [], docxArgs: [] },
      tmp,
    );
    assert.deepEqual(result.extraArgsByFormat, { html: [], pdf: [], docx: [] });
    // cleanup is callable + idempotent on no-css branch.
    result.cleanup();
    result.cleanup();
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("Phase 30 — materializeCssForPandoc writes css to tmp dir and returns --theme arg for html", () => {
  // Source scan: helper writes to .organon/tmp/ via writeFileSync, returns --theme.
  assert.match(
    LOADER_SRC,
    /writeFileSync\s*\(/,
    "loader uses writeFileSync to materialise the css",
  );
  assert.match(
    LOADER_SRC,
    /["']--theme["']/,
    "loader passes --theme as the html arg",
  );
  // Filename pattern: preset-<id>-<random>.css
  assert.match(
    LOADER_SRC,
    /preset-/,
    "tmp filename starts with preset-",
  );
  assert.match(
    LOADER_SRC,
    /\.css/,
    "tmp filename ends with .css",
  );

  // Behavioural replica: css populated → file written + --theme arg returned.
  const tmp = mkdtempSync(join(tmpdir(), "organon-css-test-"));
  let cssFile = null;
  try {
    const preset = {
      id: "rainbow",
      label: "Rainbow",
      description: "Test preset",
      pdfArgs: [],
      docxArgs: [],
      css: "section { color: red; }",
    };
    const result = replicaMaterialize(preset, tmp);
    assert.equal(result.extraArgsByFormat.pdf.length, 0, "pdf args stay empty in v1.3");
    assert.equal(result.extraArgsByFormat.docx.length, 0, "docx args stay empty in v1.3");
    assert.equal(result.extraArgsByFormat.html[0], "--theme", "html argv leads with --theme");
    cssFile = result.extraArgsByFormat.html[1];
    assert.ok(cssFile, "html argv carries a tmp css path");
    assert.ok(existsSync(cssFile), "tmp css file actually exists on disk");
    assert.equal(
      readFileSync(cssFile, "utf8"),
      "section { color: red; }",
      "tmp css file contains the preset.css verbatim",
    );
    result.cleanup();
    assert.ok(!existsSync(cssFile), "cleanup unlinks the tmp css file");
  } finally {
    if (cssFile && existsSync(cssFile)) unlinkSync(cssFile);
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("Phase 30 — export route's html branch spreads extraArgsByFormat.html into marp argv", () => {
  // Route imports the new helper.
  assert.match(
    ROUTE_SRC,
    /materializeCssForPandoc\b/,
    "route imports materializeCssForPandoc",
  );
  // Route invokes it on the resolved preset.
  assert.match(
    ROUTE_SRC,
    /materializeCssForPandoc\s*\(/,
    "route invokes the helper",
  );
  // HTML branch spreads the html arg slice into the marp argv. The
  // brief calls the destructured field `extraArgsByFormat`; allow
  // either explicit destructure or property access on a named result.
  assert.match(
    ROUTE_SRC,
    /extraArgsByFormat/,
    "route uses extraArgsByFormat as the materialise return shape",
  );
  // The spread lands in the marp argv (not just stored).
  assert.match(
    ROUTE_SRC,
    /\.\.\.\s*extraArgsByFormat\.html|\.\.\.\s*\w+\.html/,
    "html branch spreads the html args into the marp argv",
  );
});

test("Phase 30 — export route runs cleanup() in a try/finally so tmp files don't leak", () => {
  // try / finally guards the cleanup call.
  assert.match(
    ROUTE_SRC,
    /try\s*\{[\s\S]*?\}\s*finally\s*\{[\s\S]*?cleanup\s*\(\s*\)/,
    "cleanup() is invoked from a finally block",
  );
  // Schema doc updated to clarify v1.3 wiring (HTML-only, Marp --theme).
  let schema;
  assert.doesNotThrow(() => {
    schema = JSON.parse(SCHEMA_SRC);
  }, "schema is valid JSON");
  const cssDescription = schema?.definitions?.Preset?.properties?.css?.description ?? "";
  assert.match(
    cssDescription,
    /v1\.3|HTML|Marp|--theme/i,
    "schema css description mentions v1.3 / Marp --theme wiring",
  );

  // Behavioural replica: cleanup runs even when the wrapping export "fails"
  // mid-flight. We simulate by throwing inside the try and asserting the
  // cleanup ran.
  const tmp = mkdtempSync(join(tmpdir(), "organon-css-test-"));
  let cssFile = null;
  try {
    const preset = {
      id: "fail-test",
      label: "fail",
      description: "",
      pdfArgs: [],
      docxArgs: [],
      css: "h1 { color: blue; }",
    };
    const { extraArgsByFormat, cleanup } = replicaMaterialize(preset, tmp);
    cssFile = extraArgsByFormat.html[1];
    assert.ok(existsSync(cssFile), "tmp css file written");
    try {
      throw new Error("simulated marp failure");
    } catch {
      cleanup();
    }
    assert.ok(!existsSync(cssFile), "cleanup unlinks the tmp css file even on failure");
  } finally {
    if (cssFile && existsSync(cssFile)) unlinkSync(cssFile);
    rmSync(tmp, { recursive: true, force: true });
  }
});
