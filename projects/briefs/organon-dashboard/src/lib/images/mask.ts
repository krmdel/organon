/**
 * PHASE_4_TASKS.md T16 — mask validation.
 *
 * The dashboard's mask drawing produces a PNG with alpha. FAL FLUX.1 Pro Fill
 * requires the mask dimensions to match the base image exactly. This module
 * sniffs PNG dimensions from the IHDR chunk and returns a structured verdict.
 *
 * No image library — PNG IHDR is at a fixed byte offset, so 8 bytes of
 * arithmetic suffice. PNG signature: 89 50 4e 47 0d 0a 1a 0a, then 13-byte
 * IHDR chunk at byte 16 (4-byte length + 4-byte "IHDR" + width(4) + height(4)
 * + ...).
 */

const PNG_SIGNATURE = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];

export type PngDimensions = { width: number; height: number };

export class MaskError extends Error {
  status: 400 | 415;
  constructor(message: string, status: 400 | 415 = 400) {
    super(message);
    this.status = status;
  }
}

export function isPng(bytes: Uint8Array): boolean {
  if (bytes.length < 8) return false;
  for (let i = 0; i < 8; i++) {
    if (bytes[i] !== PNG_SIGNATURE[i]) return false;
  }
  return true;
}

/** Parse PNG width + height from the IHDR chunk. Throws MaskError on malformed input. */
export function pngDimensions(bytes: Uint8Array): PngDimensions {
  if (!isPng(bytes)) {
    throw new MaskError("Not a PNG (signature mismatch)", 415);
  }
  if (bytes.length < 24) {
    throw new MaskError("PNG truncated before IHDR", 415);
  }
  const view = new DataView(
    bytes.buffer,
    bytes.byteOffset + 16,
    8,
  );
  return { width: view.getUint32(0, false), height: view.getUint32(4, false) };
}

/** Validate that a mask matches a base image dimension-wise. */
export function assertMaskMatchesBase(
  maskBytes: Uint8Array,
  baseBytes: Uint8Array,
): PngDimensions {
  const m = pngDimensions(maskBytes);
  const b = pngDimensions(baseBytes);
  if (m.width !== b.width || m.height !== b.height) {
    throw new MaskError(
      `Mask is ${m.width}×${m.height} but base is ${b.width}×${b.height}; FAL FLUX Fill requires exact-size masks. Re-draw the mask without resizing.`,
    );
  }
  return m;
}
