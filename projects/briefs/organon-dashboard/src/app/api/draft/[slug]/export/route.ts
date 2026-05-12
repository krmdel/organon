import { existsSync, mkdirSync, renameSync, writeFileSync } from "node:fs";
import { spawn } from "node:child_process";
import path from "node:path";
import { resolveProjectFromRequest } from "@/lib/projects";
import { getManuscript, listSections, manuscriptDir } from "@/lib/draft/store";
import { listLibrary } from "@/lib/lit/library";
import { listFigures } from "@/lib/figures/store";
import { assembleMarkdown } from "@/lib/draft/render";
import { getPreset, materializeCssForPandoc } from "@/lib/draft/typography-presets-loader";
import { organonRoot } from "@/lib/paths";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 60;

type RouteContext = { params: Promise<{ slug: string }> };
type Format = "markdown" | "pdf" | "html" | "docx" | "substack";
const FORMATS: Format[] = ["markdown", "pdf", "html", "docx", "substack"];

// Phase 5 (fix-sprint): pass `force: true` to ship the export with a
// "Missing from library" footer instead of failing 422 on unresolved
// `\cite{}` / `\fig{}` tokens.
// Phase 18 (v1.1+): preset_id selects a typography preset that appends
// pandoc args on PDF + DOCX exports. Unknown ids fall back to default
// (see getPreset). Markdown / HTML / Substack ignore preset_id.
type Body = { project?: string; format?: Format; force?: boolean; preset_id?: string };

function exportsDir(projectPath: string, slug: string): string {
  const dir = path.join(manuscriptDir(projectPath, slug), "exports");
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  return dir;
}

// Phase 30 (v1.3) — DR-8++ tmp dir for materialised preset CSS. Lives
// under <projectPath>/.organon/tmp/ so it shares the .organon namespace
// with typography-presets.json. Auto-created on first use.
function presetTmpDir(projectPath: string): string {
  const dir = path.join(projectPath, ".organon", "tmp");
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  return dir;
}

function writeAtomic(target: string, content: string | Uint8Array): void {
  const tmp = target + ".tmp";
  writeFileSync(tmp, content);
  renameSync(tmp, target);
}

async function runCmd(cmd: string, args: string[], cwd: string, stdin?: string): Promise<{ code: number; stderr: string }> {
  return new Promise((resolve) => {
    const child = spawn(cmd, args, { cwd, stdio: ["pipe", "ignore", "pipe"] });
    let stderr = "";
    child.stderr.on("data", (c: Buffer) => { stderr += c.toString("utf8"); });
    child.on("error", () => resolve({ code: -1, stderr: `spawn error: ${cmd}` }));
    child.on("close", (code) => resolve({ code: code ?? -1, stderr }));
    if (stdin) {
      child.stdin.write(stdin);
      child.stdin.end();
    } else {
      child.stdin.end();
    }
  });
}

// Phase 17 (v1.1+) — Pandoc preflight (B3).
// Per-platform install hint surfaced when the dryrun probe fails. The
// hint is the single source of truth for the menu panel; do not rephrase
// it client-side.
function pandocInstallHint(): string {
  switch (process.platform) {
    case "darwin":
      return "brew install pandoc && brew install --cask basictex";
    case "linux":
      return "apt-get install pandoc texlive-xetex";
    case "win32":
      return "choco install pandoc miktex";
    default:
      return "Install pandoc + xelatex from https://pandoc.org/installing.html";
  }
}

type PandocProbe = { available: boolean; version?: string; error?: string };

async function pandocVersionProbe(): Promise<PandocProbe> {
  return new Promise((resolve) => {
    const child = spawn("pandoc", ["--version"], { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (c: Buffer) => { stdout += c.toString("utf8"); });
    child.stderr.on("data", (c: Buffer) => { stderr += c.toString("utf8"); });
    child.on("error", (err) => resolve({ available: false, error: err.message }));
    child.on("close", (code) => {
      if (code === 0) {
        // First line of `pandoc --version` is "pandoc 3.1.x" (or platform variant).
        const firstLine = stdout.split("\n")[0]?.trim() ?? "";
        const m = firstLine.match(/pandoc\s+(\S+)/i);
        resolve({ available: true, version: m?.[1] ?? firstLine });
      } else {
        resolve({ available: false, error: stderr.trim() || `pandoc exit ${code}` });
      }
    });
  });
}

export async function POST(request: Request, { params }: RouteContext) {
  const { slug } = await params;
  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const project = resolveProjectFromRequest(request, body.project);
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });
  const format = body.format ?? "markdown";
  if (!FORMATS.includes(format)) return Response.json({ error: "Unsupported format" }, { status: 400 });

  // Phase 17 (v1.1+) — preflight branch (B3). When the menu wants to know
  // whether pandoc is installed without committing to an export, it
  // POSTs `{ format: "pdf" }` to `?dryrun=1`. We probe `pandoc --version`
  // and return the discovery payload — never assemble the manuscript.
  if (format === "pdf" && new URL(request.url).searchParams.get("dryrun") === "1") {
    const probe = await pandocVersionProbe();
    return Response.json(
      { ...probe, install_hint: pandocInstallHint() },
      { status: 200 },
    );
  }

  const meta = getManuscript(project.path, slug);
  if (!meta) return Response.json({ error: "manuscript not found" }, { status: 404 });
  const sections = listSections(project.path, slug);
  const library = listLibrary(project.path);
  const figures = listFigures(project.path);

  // Phase 5 (fix-sprint): single resolution pass for cite + fig tokens.
  // 422 on unresolved unless body.force === true, in which case the
  // unresolved tokens stay as `[unresolved \cite{...}]` breadcrumbs and
  // the response carries a `warnings` array.
  const assembled = assembleMarkdown(meta, sections, library, figures);
  if (
    !body.force
    && (assembled.unresolvedCites.length > 0 || assembled.unresolvedFigs.length > 0)
  ) {
    return Response.json(
      {
        error: "Manuscript has unresolved citation or figure tokens. Add the missing entries to the library, edit the section to remove them, or re-export with force=true.",
        unresolved_cites: assembled.unresolvedCites,
        unresolved_figs: assembled.unresolvedFigs,
      },
      { status: 422 },
    );
  }
  const md = assembled.md;
  const warnings: string[] = [];
  if (assembled.unresolvedCites.length > 0) {
    warnings.push(`Unresolved cite tokens (${assembled.unresolvedCites.length}): ${assembled.unresolvedCites.join(", ")}`);
  }
  if (assembled.unresolvedFigs.length > 0) {
    warnings.push(`Unresolved fig tokens (${assembled.unresolvedFigs.length}): ${assembled.unresolvedFigs.join(", ")}`);
  }
  const date = new Date().toISOString().slice(0, 10);
  const out = exportsDir(project.path, slug);
  const root = organonRoot();
  const mdPath = path.join(out, `${date}_${slug}.md`);
  writeAtomic(mdPath, md);

  if (format === "markdown") {
    return Response.json({
      format,
      path: path.relative(root, mdPath),
      url: null,
      warnings,
    }, { status: 201 });
  }

  if (format === "substack") {
    return Response.json({
      error: "Substack export not yet wired in dashboard. Pipe the markdown through tool-substack manually:",
      path: path.relative(root, mdPath),
      hint: `python3 .claude/skills/tool-substack/scripts/substack_ops.py push ${path.relative(root, mdPath)}`,
    }, { status: 501 });
  }

  // Phase 18 (v1.1+): pull pandoc args from the named preset and spread
  // them into the argv. Unknown ids fall back to default.
  // Phase 25 (v1.2): forward project.path so project-local overrides
  // win on id collision (resolvePreset reads .organon/typography-
  // presets.json server-side).
  // Phase 30 (v1.3): materialise preset.css to a tmp file and pass
  // `--theme <tmp>` to Marp (HTML branch only). PDF + DOCX continue to
  // use pdfArgs / docxArgs verbatim — different injection mechanisms,
  // deferred to v1.4. Cleanup runs in try/finally so the tmp file
  // never leaks even on marp/pandoc failure.
  const preset = getPreset(body.preset_id, project.path);
  const { extraArgsByFormat, cleanup } = materializeCssForPandoc(
    preset,
    presetTmpDir(project.path),
  );

  try {
    if (format === "html") {
      const target = path.join(out, `${date}_${slug}.html`);
      const res = await runCmd(
        "marp",
        [path.basename(mdPath), "-o", path.basename(target), ...extraArgsByFormat.html],
        out,
      );
      if (res.code !== 0) {
        return Response.json({
          error: `Marp export failed (${res.code}). Install via 'npm i -g @marp-team/marp-cli' or use the markdown export at ${path.relative(root, mdPath)}.`,
          stderr: res.stderr.split("\n").slice(-5).join("\n"),
        }, { status: 503 });
      }
      return Response.json({ format, path: path.relative(root, target), warnings }, { status: 201 });
    }

    // pdf or docx — Pandoc
    const ext = format === "pdf" ? "pdf" : "docx";
    const target = path.join(out, `${date}_${slug}.${ext}`);
    const args = format === "pdf"
      ? ["-f", "markdown", "-t", "pdf", "-o", path.basename(target), "--pdf-engine=xelatex", ...preset.pdfArgs, ...extraArgsByFormat.pdf]
      : ["-f", "markdown", "-t", "docx", "-o", path.basename(target), ...preset.docxArgs, ...extraArgsByFormat.docx];
    const res = await runCmd("pandoc", args, out, md);
    if (res.code !== 0) {
      return Response.json({
        error: `Pandoc ${format} export failed (${res.code}). Install pandoc${format === "pdf" ? " + xelatex" : ""} or use the markdown export at ${path.relative(root, mdPath)}.`,
        stderr: res.stderr.split("\n").slice(-5).join("\n"),
      }, { status: 503 });
    }
    return Response.json({ format, path: path.relative(root, target), warnings }, { status: 201 });
  } finally {
    cleanup();
  }
}
