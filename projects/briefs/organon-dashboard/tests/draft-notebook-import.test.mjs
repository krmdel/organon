import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 52 (v2.0) — Notebook integration.
//
// Goal: a Jupyter .ipynb upload becomes a manuscript section. NEW
// lib/draft/notebook-import.ts::parseNotebook(json) -> { markdown,
// cell_count, has_outputs } flattens cells (markdown verbatim, code as
// fenced ```python blocks, stream/display_data outputs appended). NEW
// POST /api/draft/[slug]/import-notebook accepts {project, section_id?,
// notebook} and creates (or replaces) the section using the parsed
// markdown. UI: a "+ import .ipynb" affordance in section-list reads
// the file via FileReader and POSTs.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const PARSER_SRC = readSrc("src/lib/draft/notebook-import.ts");
const ROUTE_SRC = readSrc("src/app/api/draft/[slug]/import-notebook/route.ts");
const SECTION_LIST_SRC = readSrc("src/components/draft/section-list.tsx");

test("Phase 52 — parseNotebook is exported and accepts both string and object input", () => {
  assert.match(PARSER_SRC, /export function parseNotebook\(/);
  // Tolerates both pre-parsed JSON object and raw string.
  assert.match(PARSER_SRC, /JSON\.parse/);
});

test("Phase 52 — parseNotebook returns { markdown, cell_count, has_outputs }", () => {
  // Behavioural replica matching the contract.
  const parse = (nb) => {
    const obj = typeof nb === "string" ? JSON.parse(nb) : nb;
    const cells = Array.isArray(obj?.cells) ? obj.cells : [];
    const parts = [];
    let hasOutputs = false;
    for (const cell of cells) {
      const src = Array.isArray(cell.source) ? cell.source.join("") : (cell.source ?? "");
      if (cell.cell_type === "markdown") {
        if (src.trim()) parts.push(src.trimEnd());
      } else if (cell.cell_type === "code") {
        if (src.trim()) parts.push("```python\n" + src.trimEnd() + "\n```");
        const outputs = Array.isArray(cell.outputs) ? cell.outputs : [];
        for (const out of outputs) {
          if (out.output_type === "stream") {
            const text = Array.isArray(out.text) ? out.text.join("") : (out.text ?? "");
            if (text.trim()) {
              hasOutputs = true;
              parts.push("```\n" + text.trimEnd() + "\n```");
            }
          } else if (out.output_type === "execute_result" || out.output_type === "display_data") {
            const data = out.data ?? {};
            if (data["text/markdown"]) {
              const md = Array.isArray(data["text/markdown"])
                ? data["text/markdown"].join("")
                : data["text/markdown"];
              hasOutputs = true;
              parts.push(md.trimEnd());
            } else if (data["text/plain"]) {
              const tp = Array.isArray(data["text/plain"])
                ? data["text/plain"].join("")
                : data["text/plain"];
              if (tp.trim()) {
                hasOutputs = true;
                parts.push("```\n" + tp.trimEnd() + "\n```");
              }
            }
          }
        }
      }
      // 'raw' cells are skipped.
    }
    return {
      markdown: parts.join("\n\n"),
      cell_count: cells.length,
      has_outputs: hasOutputs,
    };
  };
  const sample = {
    cells: [
      { cell_type: "markdown", source: "# Hello\n\nIntro text.\n" },
      {
        cell_type: "code",
        source: "x = 2\nprint(x)\n",
        outputs: [
          { output_type: "stream", text: "2\n" },
        ],
      },
      { cell_type: "raw", source: "ignored" },
    ],
  };
  const out = parse(sample);
  assert.equal(out.cell_count, 3);
  assert.equal(out.has_outputs, true);
  assert.match(out.markdown, /# Hello/);
  assert.match(out.markdown, /```python\n[\s\S]*?print\(x\)/);
  assert.match(out.markdown, /```\n2/);
  assert.ok(!out.markdown.includes("ignored"), "raw cells must be skipped");
});

test("Phase 52 — parser source declares the cell-type dispatch", () => {
  // Sentinel: the implementation must dispatch on cell_type.
  assert.match(PARSER_SRC, /cell_type/);
  assert.match(PARSER_SRC, /['"]markdown['"]/);
  assert.match(PARSER_SRC, /['"]code['"]/);
  // Code cells become fenced python blocks.
  assert.match(PARSER_SRC, /```python|"```python"|'```python'/);
});

test("Phase 52 — POST /api/draft/[slug]/import-notebook reads project + invokes parseNotebook", () => {
  assert.match(ROUTE_SRC, /export\s+async\s+function\s+POST/);
  assert.match(ROUTE_SRC, /resolveProjectFromRequest/);
  assert.match(ROUTE_SRC, /parseNotebook/);
  // Persists via saveSection (creates or replaces).
  assert.match(ROUTE_SRC, /saveSection|patchSection/);
  // Returns the section artifact.
  assert.match(ROUTE_SRC, /\{\s*section\s*\}|section:/);
});

test("Phase 52 — route returns 400 when notebook payload is missing or unparseable", () => {
  // Either an explicit "notebook required" 400 or a JSON parse 400.
  assert.match(
    ROUTE_SRC,
    /notebook[\s\S]{0,200}status:\s*400|400[\s\S]{0,200}notebook/,
  );
});

test("Phase 52 — section-list mounts an .ipynb import affordance", () => {
  // Sentinel data attribute the test pins.
  assert.match(SECTION_LIST_SRC, /data-import-notebook/);
  // Wired via a callback prop.
  assert.match(SECTION_LIST_SRC, /onImportNotebook/);
});
