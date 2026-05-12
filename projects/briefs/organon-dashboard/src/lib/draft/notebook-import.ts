/**
 * Phase 52 (v2.0) — Notebook integration.
 *
 * Pure parser turning a Jupyter `.ipynb` JSON payload into a markdown
 * string suitable for a manuscript section. Cells flatten as follows:
 *   - markdown cells   → preserved verbatim (trimmed end)
 *   - code cells       → fenced ```python block; outputs (stream,
 *                        text/plain, text/markdown) appended below
 *   - raw cells        → skipped (researcher-private noise)
 *
 * Image outputs (image/png, etc.) are not embedded in v2.0 — they
 * surface as a "[image output omitted]" sentinel so downstream
 * skill-driven figure imports can replace them later.
 */

export interface NotebookParseResult {
  markdown: string;
  cell_count: number;
  has_outputs: boolean;
}

interface NotebookCell {
  cell_type?: string;
  source?: string | string[];
  outputs?: NotebookOutput[];
}

interface NotebookOutput {
  output_type?: string;
  text?: string | string[];
  data?: Record<string, string | string[]>;
  name?: string;
}

interface NotebookJson {
  cells?: NotebookCell[];
}

function joinSource(src: unknown): string {
  if (Array.isArray(src)) return src.join("");
  if (typeof src === "string") return src;
  return "";
}

function fenceBlock(content: string, lang: string = ""): string {
  const fence = lang ? "```" + lang : "```";
  return `${fence}\n${content.replace(/\n+$/, "")}\n\`\`\``;
}

export function parseNotebook(input: string | NotebookJson | unknown): NotebookParseResult {
  let obj: NotebookJson;
  if (typeof input === "string") {
    try {
      obj = JSON.parse(input) as NotebookJson;
    } catch {
      return { markdown: "", cell_count: 0, has_outputs: false };
    }
  } else if (input && typeof input === "object") {
    obj = input as NotebookJson;
  } else {
    return { markdown: "", cell_count: 0, has_outputs: false };
  }

  const cells = Array.isArray(obj.cells) ? obj.cells : [];
  const parts: string[] = [];
  let hasOutputs = false;

  for (const cell of cells) {
    const src = joinSource(cell?.source).trimEnd();
    if (cell?.cell_type === "markdown") {
      if (src.trim().length > 0) parts.push(src);
    } else if (cell?.cell_type === "code") {
      if (src.trim().length > 0) parts.push(fenceBlock(src, "python"));
      const outputs = Array.isArray(cell.outputs) ? cell.outputs : [];
      for (const out of outputs) {
        if (out?.output_type === "stream") {
          const text = joinSource(out.text).trimEnd();
          if (text.length > 0) {
            hasOutputs = true;
            parts.push(fenceBlock(text));
          }
        } else if (
          out?.output_type === "execute_result" ||
          out?.output_type === "display_data"
        ) {
          const data = out.data ?? {};
          if (data["text/markdown"] !== undefined) {
            const md = joinSource(data["text/markdown"]).trimEnd();
            if (md.length > 0) {
              hasOutputs = true;
              parts.push(md);
            }
          } else if (data["text/plain"] !== undefined) {
            const tp = joinSource(data["text/plain"]).trimEnd();
            if (tp.length > 0) {
              hasOutputs = true;
              parts.push(fenceBlock(tp));
            }
          } else if (data["image/png"] !== undefined || data["image/jpeg"] !== undefined) {
            hasOutputs = true;
            parts.push("_[image output omitted — re-render via figures workflow]_");
          }
        }
      }
    }
    // 'raw' and unknown cell types are intentionally skipped.
  }

  return {
    markdown: parts.join("\n\n"),
    cell_count: cells.length,
    has_outputs: hasOutputs,
  };
}
