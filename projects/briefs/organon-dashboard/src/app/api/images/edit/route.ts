import { existsSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import path from "node:path";
import { resolveProjectFromRequest } from "@/lib/projects";
import { organonRoot } from "@/lib/paths";
import {
  appendVersion,
  ensureMaskDir,
  getMainVersion,
  maskPath,
  pngPath,
} from "@/lib/images/versions";
import { assertMaskMatchesBase, MaskError, pngDimensions } from "@/lib/images/mask";
import { callFluxFill, downloadAsset, FalError, uploadAsset } from "@/lib/images/fal-client";
import { fluxFillCostCents, megapixels } from "@/lib/images/pricing";
import type { FigureArtifact } from "@/lib/artifacts/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 120;

export async function POST(request: Request) {
  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return Response.json({ error: "Invalid multipart body" }, { status: 400 });
  }
  const formProject = form.get("project");
  const project = resolveProjectFromRequest(
    request,
    typeof formProject === "string" ? formProject : null,
  );
  if (!project) return Response.json({ error: "Unknown project" }, { status: 404 });

  const figId = String(form.get("fig_id") ?? "");
  const prompt = String(form.get("prompt") ?? "").trim();
  if (!figId) return Response.json({ error: "fig_id required" }, { status: 400 });
  if (!prompt) return Response.json({ error: "prompt required" }, { status: 400 });

  const mask = form.get("mask");
  if (!mask || typeof mask === "string") {
    return Response.json({ error: "mask file required" }, { status: 400 });
  }
  const maskBytes = new Uint8Array(await (mask as File).arrayBuffer());

  const main = getMainVersion(project.path, figId);
  if (!main) return Response.json({ error: "fig_id has no v1 yet — generate first" }, { status: 404 });
  const basePath = pngPath(project.path, figId, main.version);
  if (!existsSync(basePath)) {
    return Response.json({ error: "main version PNG missing on disk" }, { status: 410 });
  }
  const baseBytes = new Uint8Array(readFileSync(basePath));

  let dims;
  try {
    dims = assertMaskMatchesBase(maskBytes, baseBytes);
  } catch (err) {
    if (err instanceof MaskError) {
      return Response.json({ error: err.message }, { status: err.status });
    }
    throw err;
  }

  const nextVersion = main.version + 1;
  const root = organonRoot();
  const newMaskPath = maskPath(project.path, figId, nextVersion);
  const newPngPath = pngPath(project.path, figId, nextVersion);

  // Persist mask early so the user can audit + re-fire on transient FAL failures.
  ensureMaskDir(project.path, figId);
  const maskTmp = newMaskPath + ".tmp";
  writeFileSync(maskTmp, maskBytes);
  renameSync(maskTmp, newMaskPath);

  try {
    const baseUrl = await uploadAsset(baseBytes, `${figId}_v${main.version}.png`, "image/png");
    const maskUrl = await uploadAsset(maskBytes, `${figId}_mask_v${nextVersion}.png`, "image/png");
    const fluxRes = await callFluxFill({ prompt, image_url: baseUrl, mask_url: maskUrl });
    const first = fluxRes.images?.[0];
    if (!first?.url) {
      return Response.json({ error: "FAL FLUX returned no images" }, { status: 502 });
    }
    const outBytes = await downloadAsset(first.url);
    if (outBytes.length === 0) return Response.json({ error: "empty FAL image" }, { status: 502 });
    const outDims = pngDimensions(outBytes);

    const pngTmp = newPngPath + ".tmp";
    writeFileSync(pngTmp, outBytes);
    renameSync(pngTmp, newPngPath);

    const mp = megapixels(outDims.width, outDims.height);
    const artifact: FigureArtifact = {
      _artifact: "figure",
      schema_version: 1,
      id: figId,
      project_slug: project.slug,
      kind: "image",
      version: nextVersion,
      format: "png",
      data_source: null,
      params: {
        prompt,
        style: null,
        mask_megapixels: Math.round(megapixels(dims.width, dims.height) * 100) / 100,
      },
      caption: null,
      alt_text: null,
      code_path: null,
      png_path: path.relative(root, newPngPath),
      svg_path: null,
      thumbnail_path: null,
      library_path: path.relative(root, newPngPath),
      backend: "fal-flux-fill",
      cost_cents: fluxFillCostCents(mp),
      parent_version: main.version,
      mask_path: path.relative(root, newMaskPath),
      locked: false,
      created_at: new Date().toISOString(),
    };
    appendVersion(project.path, artifact);

    return Response.json({ figure: artifact }, { status: 201 });
  } catch (err) {
    if (err instanceof FalError) {
      return Response.json({ error: err.message, detail: err.detail }, { status: err.status });
    }
    if (err instanceof MaskError) {
      return Response.json({ error: err.message }, { status: err.status });
    }
    return Response.json(
      { error: err instanceof Error ? err.message : "edit failed" },
      { status: 500 },
    );
  }
}
