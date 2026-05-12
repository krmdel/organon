import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 34 (v1.3) — DR-6++ on-disk chat transcript persistence.
//
// Closes Phase 27 §9.3's "No on-disk transcript persistence — same as
// v1.1" deferral. Per-manuscript scope (NOT per-section).
//
// Storage: <projectPath>/.organon/chat-transcripts/{slug}.json
// Cap: MAX_TRANSCRIPT_TURNS = 200 (older drop on append). Atomic
// tmp+rename writer; missing/malformed file → []. Hydration
// non-blocking — workspace mounts even if GET fails.
//
// ChatTurn type extracted from chat-panel.tsx → shared client-safe
// module so chat-transcripts.ts (server, node:fs) can import without
// dragging React into the bundle.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

const tryRead = (p) => {
  try {
    return readFileSync(p, "utf8");
  } catch {
    return "";
  }
};

const TYPES_SRC = tryRead(
  join(ROOT, "src", "lib", "draft", "chat-turn-types.ts"),
);
const LIB_SRC = tryRead(
  join(ROOT, "src", "lib", "draft", "chat-transcripts.ts"),
);
const ROUTE_SRC = tryRead(
  join(ROOT, "src", "app", "api", "draft", "[slug]", "chat-transcript", "route.ts"),
);
const WORKSPACE_SRC = tryRead(
  join(ROOT, "src", "components", "draft", "manuscript-workspace.tsx"),
);
const CHAT_PANEL_SRC = tryRead(
  join(ROOT, "src", "components", "draft", "chat-panel.tsx"),
);

test("Phase 34 — chat-transcripts.ts exports readTranscript / appendTurn / clearTranscript", () => {
  // The server-only lib exists and exports the three operations.
  assert.match(LIB_SRC, /export\s+function\s+readTranscript\s*\(/, "readTranscript exported");
  assert.match(LIB_SRC, /export\s+function\s+appendTurn\s*\(/, "appendTurn exported");
  assert.match(LIB_SRC, /export\s+function\s+clearTranscript\s*\(/, "clearTranscript exported");
  // Storage path lives under .organon/chat-transcripts/.
  assert.match(
    LIB_SRC,
    /chat-transcripts/,
    "library uses chat-transcripts directory",
  );
  // ChatTurn type extracted to a shared client-safe module so the
  // server lib can import without React bundling.
  assert.match(
    TYPES_SRC,
    /export\s+(type|interface)\s+ChatTurn/,
    "ChatTurn type lives in chat-turn-types.ts",
  );
  // The new server lib imports the type from the shared module
  // (NOT from chat-panel.tsx — that would drag React server-side).
  assert.match(
    LIB_SRC,
    /from\s*["'][^"']*chat-turn-types/,
    "chat-transcripts imports ChatTurn from chat-turn-types",
  );
  // chat-panel.tsx now re-exports ChatTurn from the shared module to
  // preserve the v1.2 import surface.
  assert.match(
    CHAT_PANEL_SRC,
    /from\s*["'][^"']*chat-turn-types/,
    "chat-panel re-exports ChatTurn from the shared module",
  );
});

test("Phase 34 — readTranscript returns [] when file is missing or malformed", () => {
  // Source-text scan: existsSync gate + try/catch fallback to [].
  assert.match(
    LIB_SRC,
    /existsSync\s*\(/,
    "readTranscript checks file existence first",
  );
  assert.match(
    LIB_SRC,
    /try\s*\{[\s\S]*JSON\.parse[\s\S]*?\}\s*catch/,
    "readTranscript wraps JSON.parse in try/catch",
  );
  // Returns [] (not throws) on missing file. Cheap source check —
  // the function body should contain at least one `return []`.
  assert.match(
    LIB_SRC,
    /return\s*\[\s*\]/,
    "readTranscript falls back to []",
  );
  // No throws inside — drop-not-throw semantics.
  assert.doesNotMatch(
    LIB_SRC,
    /\bthrow\s+new\s+(Error|TypeError)/,
    "library never throws on bad files",
  );
});

test("Phase 34 — appendTurn caps at MAX_TRANSCRIPT_TURNS = 200 (older drop)", () => {
  // The cap constant is named + valued.
  assert.match(
    LIB_SRC,
    /MAX_TRANSCRIPT_TURNS\s*=\s*200\b/,
    "MAX_TRANSCRIPT_TURNS = 200 declared",
  );
  // The append path slices to the cap (or compares length and drops).
  assert.match(
    LIB_SRC,
    /(slice\s*\(-MAX_TRANSCRIPT_TURNS\)|slice\s*\(\s*-\s*200\b)|MAX_TRANSCRIPT_TURNS\s*[\)\]]?\s*\)?\s*\.slice/,
    "append path slices to keep the most recent 200",
  );
  // Atomic write: tmp+rename pattern. Same shape as Phase 25's
  // writeAtomic in /api/draft/typography-presets/route.ts.
  assert.match(
    LIB_SRC,
    /\.tmp[\s\S]{0,80}renameSync/,
    "appendTurn writes atomically via tmp+rename",
  );
});

test("Phase 34 — chat-transcript route GET / POST / DELETE wired with resolveProjectFromRequest", () => {
  // Three handlers exported.
  assert.match(ROUTE_SRC, /export\s+async\s+function\s+GET\b/, "GET handler exported");
  assert.match(ROUTE_SRC, /export\s+async\s+function\s+POST\b/, "POST handler exported");
  assert.match(ROUTE_SRC, /export\s+async\s+function\s+DELETE\b/, "DELETE handler exported");
  // Project resolution is the canonical helper, not ad-hoc.
  assert.match(
    ROUTE_SRC,
    /resolveProjectFromRequest\b/,
    "route uses resolveProjectFromRequest (per Organon convention)",
  );
  // Pulls slug from the dynamic segment.
  assert.match(
    ROUTE_SRC,
    /params\s*:\s*Promise<\s*\{\s*slug\s*:\s*string\s*\}\s*>/,
    "route signature pulls slug from the dynamic segment",
  );
});

test("Phase 34 — workspace hydrates chatTurns from GET /chat-transcript on mount", () => {
  // Hydration effect mounts a GET against the new route. Two-stage
  // check — the URL appears in source AND fetch( is invoked nearby
  // (within 200 chars in either direction).
  assert.match(
    WORKSPACE_SRC,
    /chat-transcript/,
    "workspace references the chat-transcript route",
  );
  assert.match(
    WORKSPACE_SRC,
    /fetch\([\s\S]{0,200}chat-transcript|chat-transcript[\s\S]{0,200}\)/,
    "workspace invokes fetch on chat-transcript URL",
  );
  // Workspace POSTs each completed turn to the route.
  assert.match(
    WORKSPACE_SRC,
    /chat-transcript[\s\S]{0,400}method\s*:\s*["']POST["']|method\s*:\s*["']POST["'][\s\S]{0,400}chat-transcript/,
    "workspace POSTs each completed turn to /chat-transcript",
  );
});

test("Phase 34 — chat-panel exposes data-action='chat-clear' header button", () => {
  // The header carries a data-action="chat-clear" button wired through
  // a new onClearTranscript prop.
  assert.match(
    CHAT_PANEL_SRC,
    /data-action\s*=\s*"chat-clear"/,
    "chat-panel renders a chat-clear header button",
  );
  assert.match(
    CHAT_PANEL_SRC,
    /onClearTranscript\s*\?\s*:\s*\(/,
    "ChatPanelProps adds optional onClearTranscript",
  );
});
