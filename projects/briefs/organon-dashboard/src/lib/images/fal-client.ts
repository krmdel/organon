/**
 * PHASE_4_TASKS.md T11 — TS-side FAL client.
 *
 * Talks to FAL's REST API directly for low-latency region inpainting via
 * FLUX.1 Pro Fill (`fal-ai/flux-pro/v1/fill`, $0.05/MP). The skill-side
 * Python lib at `.claude/skills/viz-nano-banana/lib/fal.py` (deferred to a
 * later batch) covers CLI use of the same endpoint.
 *
 * Auth: standard `Authorization: Key <FAL_KEY>` header. Errors return typed
 * statuses so the route handler can map them onto HTTP responses.
 */

const STORAGE_UPLOAD_ENDPOINT = "https://rest.alpha.fal.ai/storage/upload/initiate";
const FLUX_PRO_FILL_ENDPOINT = "https://fal.run/fal-ai/flux-pro/v1/fill";
const DEFAULT_TIMEOUT_MS = 90_000;

export class FalError extends Error {
  status: number;
  detail?: unknown;
  constructor(message: string, status: number, detail?: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

function falKey(): string {
  const k = process.env.FAL_KEY?.trim();
  if (!k) {
    throw new FalError(
      "FAL_KEY missing. Add it to .env (see .env.example) and restart `npm run dev`.",
      402,
    );
  }
  return k;
}

type StorageInitiateResponse = {
  upload_url: string;
  file_url: string;
};

/**
 * Upload an image/mask blob to FAL's storage. Returns the public file URL the
 * model endpoint can fetch from.
 */
export async function uploadAsset(
  bytes: Uint8Array,
  filename: string,
  contentType: string,
  signal?: AbortSignal,
): Promise<string> {
  const key = falKey();
  const initRes = await fetch(STORAGE_UPLOAD_ENDPOINT, {
    method: "POST",
    headers: {
      Authorization: `Key ${key}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ file_name: filename, content_type: contentType }),
    signal,
  });
  if (!initRes.ok) {
    const text = await initRes.text();
    throw new FalError(`FAL storage initiate failed: ${initRes.status}`, 502, text);
  }
  const { upload_url, file_url } = (await initRes.json()) as StorageInitiateResponse;
  const putRes = await fetch(upload_url, {
    method: "PUT",
    headers: { "Content-Type": contentType },
    body: new Blob([new Uint8Array(bytes)], { type: contentType }),
    signal,
  });
  if (!putRes.ok) {
    throw new FalError(`FAL storage PUT failed: ${putRes.status}`, 502);
  }
  return file_url;
}

export type FluxFillRequest = {
  prompt: string;
  image_url: string;
  mask_url: string;
  num_inference_steps?: number;
  guidance_scale?: number;
  seed?: number;
};

export type FluxFillResponse = {
  images: { url: string; width?: number; height?: number; content_type?: string }[];
  seed?: number;
  timings?: Record<string, number>;
};

export async function callFluxFill(
  req: FluxFillRequest,
  signal?: AbortSignal,
): Promise<FluxFillResponse> {
  const key = falKey();
  const ctrl = new AbortController();
  const linked = signal ? linkSignals(signal, ctrl.signal) : ctrl.signal;
  const timeout = setTimeout(() => ctrl.abort(), DEFAULT_TIMEOUT_MS);
  try {
    const res = await fetch(FLUX_PRO_FILL_ENDPOINT, {
      method: "POST",
      headers: {
        Authorization: `Key ${key}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(req),
      signal: linked,
    });
    if (!res.ok) {
      const text = await res.text();
      throw new FalError(`FAL FLUX Fill ${res.status}`, res.status >= 500 ? 502 : 400, text);
    }
    return (await res.json()) as FluxFillResponse;
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new FalError(`FAL FLUX Fill timed out after ${DEFAULT_TIMEOUT_MS}ms`, 504);
    }
    if (err instanceof FalError) throw err;
    throw new FalError(
      `FAL FLUX Fill request failed: ${err instanceof Error ? err.message : String(err)}`,
      502,
    );
  } finally {
    clearTimeout(timeout);
  }
}

/** Download a generated image (the FAL response includes a public URL). */
export async function downloadAsset(url: string, signal?: AbortSignal): Promise<Uint8Array> {
  const res = await fetch(url, { signal });
  if (!res.ok) {
    throw new FalError(`Asset fetch ${res.status}`, 502);
  }
  return new Uint8Array(await res.arrayBuffer());
}

function linkSignals(a: AbortSignal, b: AbortSignal): AbortSignal {
  if (a.aborted) return a;
  if (b.aborted) return b;
  const c = new AbortController();
  a.addEventListener("abort", () => c.abort(a.reason));
  b.addEventListener("abort", () => c.abort(b.reason));
  return c.signal;
}
