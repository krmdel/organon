import { existsSync, mkdirSync, renameSync, writeFileSync } from "node:fs";
import path from "node:path";
import { allocateFileId } from "./id";
import { dataDir, ensureDataDir } from "./files";

export const SUPPORTED_EXTENSIONS = ["csv", "xlsx", "xls", "json"] as const;
export type SupportedExtension = (typeof SUPPORTED_EXTENSIONS)[number];

export function maxUploadBytes(): number {
  const env = process.env.DATA_MAX_UPLOAD_MB;
  const mb = env ? Number(env) : 200;
  if (!Number.isFinite(mb) || mb <= 0) return 200 * 1024 * 1024;
  return Math.floor(mb * 1024 * 1024);
}

export function extensionOf(filename: string): string {
  const dot = filename.lastIndexOf(".");
  if (dot < 0) return "";
  return filename.slice(dot + 1).toLowerCase();
}

export function isSupportedExtension(ext: string): ext is SupportedExtension {
  return (SUPPORTED_EXTENSIONS as readonly string[]).includes(ext);
}

/** Sniff the first 16 bytes for a magic-byte signature. Returns null when no signature matches. */
export function sniffMagicBytes(head: Uint8Array): "xlsx" | "xls" | "csv-or-json" | "parquet" | null {
  // XLSX is a ZIP container — starts with PK\x03\x04
  if (head.length >= 4 && head[0] === 0x50 && head[1] === 0x4b && head[2] === 0x03 && head[3] === 0x04) {
    return "xlsx";
  }
  // Old XLS = OLE compound (D0 CF 11 E0 A1 B1 1A E1)
  if (
    head.length >= 8 &&
    head[0] === 0xd0 && head[1] === 0xcf && head[2] === 0x11 && head[3] === 0xe0 &&
    head[4] === 0xa1 && head[5] === 0xb1 && head[6] === 0x1a && head[7] === 0xe1
  ) {
    return "xls";
  }
  // Parquet — starts with "PAR1"
  if (head.length >= 4 && head[0] === 0x50 && head[1] === 0x41 && head[2] === 0x52 && head[3] === 0x31) {
    return "parquet";
  }
  // ASCII text: cheap predicate — first byte is printable / whitespace
  const b0 = head[0];
  if (b0 >= 0x20 && b0 <= 0x7e) return "csv-or-json";
  if (b0 === 0x09 || b0 === 0x0a || b0 === 0x0d) return "csv-or-json";
  return null;
}

export type UploadValidationError =
  | { ok: false; status: 400; message: string }
  | { ok: false; status: 413; message: string }
  | { ok: false; status: 415; message: string };

export type ValidatedUpload = {
  ok: true;
  fileId: string;
  ext: SupportedExtension;
  filename: string;
  sizeBytes: number;
  uploadedAt: string;
  rawPath: string;
  rawPathRelative: string;
  bytes: Uint8Array;
};

/**
 * Validate + persist an uploaded file. Atomic write (tmp + rename). Returns
 * either a typed error or the validated descriptor including the absolute raw
 * path written. Caller (load.ts) is responsible for spawning the Python
 * profiler subsequently.
 */
export async function validateAndStoreUpload(opts: {
  file: File;
  projectPath: string;
  organonRoot: string;
}): Promise<ValidatedUpload | UploadValidationError> {
  const { file, projectPath, organonRoot } = opts;
  const filename = file.name || "upload";
  const ext = extensionOf(filename);
  if (!isSupportedExtension(ext)) {
    return {
      ok: false,
      status: 415,
      message: `Unsupported extension ".${ext}". Allowed: ${SUPPORTED_EXTENSIONS.join(", ")}.`,
    };
  }
  const max = maxUploadBytes();
  if (file.size > max) {
    return {
      ok: false,
      status: 413,
      message: `File ${file.size} bytes exceeds limit ${max} bytes (override DATA_MAX_UPLOAD_MB).`,
    };
  }

  const buf = new Uint8Array(await file.arrayBuffer());
  if (buf.length === 0) {
    return { ok: false, status: 400, message: "Empty file body." };
  }

  const magic = sniffMagicBytes(buf.slice(0, 16));
  // Strict: extension must agree with magic when magic is recognizable.
  if (magic === "xlsx" && ext !== "xlsx") {
    return { ok: false, status: 415, message: "Body is XLSX but extension is not .xlsx." };
  }
  if (magic === "xls" && ext !== "xls") {
    return { ok: false, status: 415, message: "Body is legacy XLS but extension is not .xls." };
  }
  if ((ext === "csv" || ext === "json") && magic !== null && magic !== "csv-or-json") {
    return {
      ok: false,
      status: 415,
      message: `Extension .${ext} expects text body but file looks binary.`,
    };
  }

  ensureDataDir(projectPath);
  const fileId = allocateFileId(filename, file.size, buf.slice(0, 1024));
  const rawPath = path.join(dataDir(projectPath), `${fileId}.${ext}`);
  const tmp = rawPath + ".tmp";
  writeFileSync(tmp, buf);
  if (!existsSync(path.dirname(rawPath))) {
    mkdirSync(path.dirname(rawPath), { recursive: true });
  }
  renameSync(tmp, rawPath);

  return {
    ok: true,
    fileId,
    ext,
    filename,
    sizeBytes: file.size,
    uploadedAt: new Date().toISOString(),
    rawPath,
    rawPathRelative: path.relative(organonRoot, rawPath),
    bytes: buf,
  };
}
