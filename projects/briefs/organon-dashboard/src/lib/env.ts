/**
 * Typed access to environment variables the dashboard cares about.
 * Read at request time so a developer adding a key to .env doesn't have to
 * restart the dev server beyond the next request.
 */

export function organonRootEnv(): string | undefined {
  return process.env.ORGANON_ROOT;
}

export function ncbiApiKey(): string | undefined {
  return process.env.NCBI_API_KEY;
}

export function openalexApiKey(): string | undefined {
  return process.env.OPENALEX_API_KEY;
}

export function s2ApiKey(): string | undefined {
  return process.env.S2_API_KEY;
}

// Phase 55 (v2.1) — A1: paperclip auth + opt-out.
export function paperclipApiKey(): string | undefined {
  const key = process.env.PAPERCLIP_API_KEY;
  return key && key.length > 0 ? key : undefined;
}

export function paperclipDisabled(): boolean {
  const v = process.env.PAPERCLIP_DISABLED;
  return v === "1" || v === "true";
}

export function claudeBin(): string {
  return process.env.CLAUDE_BIN || "claude";
}
