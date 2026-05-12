import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 10 (v1.0.1) — DR-3 + DR-5 regression contract.
//
// Scope:
// 1. SectionGenerateButton is visually distinct from StatusBadgeSection.
// 2. /api/draft/[slug]/generate-section spawns sci-writing with the
//    section_type + mode parameters and emits the Phase 4 done contract.
// 3. /api/draft/[slug]/generate-title returns 3–5 candidates with rationale.
// 4. The Draft-all wizard fans out with cap=2 parallelism, sequentially
//    pulling from the section ordering.
// 5. RunStateCard now mounts on /draft (closes the Phase 6 deferred H-5
//    follow-up — the manuscript workspace surfaces generate-run state).
// 6. The propose-title button lives in the manuscript-create form and
//    renders the candidate list with rationale per item.
//
// Same source-text scan pattern as Phase 9's draft-code-spans tests so
// these stay portable across `node --test` (no TS build step needed).

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const BUTTON_SRC = readSrc("src/components/draft/section-generate-button.tsx");
const STATUS_BADGE_SRC = readSrc("src/components/draft/status-badge-section.tsx");
const SECTION_LIST_SRC = readSrc("src/components/draft/section-list.tsx");
const WORKSPACE_SRC = readSrc("src/components/draft/manuscript-workspace.tsx");
const DRAFT_LIST_SRC = readSrc("src/components/draft/draft-list.tsx");
const GENERATE_SECTION_SRC = readSrc("src/app/api/draft/[slug]/generate-section/route.ts");
const GENERATE_TITLE_SRC = readSrc("src/app/api/draft/[slug]/generate-title/route.ts");
const ACTION_SRC = readSrc("src/app/api/draft/[slug]/action/route.ts");
const VALIDATE_SRC = readSrc("src/lib/draft/validate.ts");
const EDITOR_SRC = readSrc("src/components/draft/markdown-editor.tsx");
const CHEATSHEET_SRC = readSrc("src/components/draft/syntax-cheatsheet.tsx");
const SCI_WRITING_SKILL = readFileSync(
  join(ROOT, "..", "..", "..", ".claude", "skills", "sci-writing", "SKILL.md"),
  "utf8",
);

test("section-generate-button is visually distinct from the status badge", () => {
  // The button uses the accent palette + a wand glyph + the literal label
  // "Generate" so a researcher reads it as an action affordance, not a
  // state indicator. The status badge uses small chip styling with the
  // section's status text (draft / reviewed / final).
  assert.match(BUTTON_SRC, /data-section-generate-button/);
  // Accent palette + wand glyph
  assert.match(BUTTON_SRC, /text-accent/);
  assert.match(BUTTON_SRC, /WandGlyph/);
  // Action label, not a state label
  assert.match(BUTTON_SRC, /Generate/);
  assert.match(BUTTON_SRC, /Generating…/);
  // Status badge uses different palette/shape conventions — it shows
  // status text (draft/reviewed/final) and is a small chip, not an
  // action button. Asserting their data-attribute + label tokens are
  // disjoint pins the visual distinction.
  assert.doesNotMatch(STATUS_BADGE_SRC, /data-section-generate-button/);
  assert.doesNotMatch(STATUS_BADGE_SRC, /Generate/);
  // Section list mounts both — the badge AND the generate button — side
  // by side, confirming they coexist as distinct affordances.
  assert.match(SECTION_LIST_SRC, /import \{ SectionGenerateButton \}/);
  assert.match(SECTION_LIST_SRC, /import \{ StatusBadgeSection \}/);
  assert.match(SECTION_LIST_SRC, /<SectionGenerateButton/);
  assert.match(SECTION_LIST_SRC, /<StatusBadgeSection/);
});

test("/api/draft/[slug]/generate-section spawns sci-writing with section_type + mode params", () => {
  // Skill identity
  assert.match(GENERATE_SECTION_SRC, /skill: "sci-writing"/);
  // Phase 1 invariant: cwd is organonRoot, project communicated via prompt
  assert.match(GENERATE_SECTION_SRC, /active_project_slug=\$\{project\.slug\}/);
  assert.match(GENERATE_SECTION_SRC, /manuscript_slug=\$\{slug\}/);
  assert.match(GENERATE_SECTION_SRC, /section_id=\$\{body\.section_id\}/);
  assert.match(GENERATE_SECTION_SRC, /section_type=\$\{sectionType\}/);
  assert.match(GENERATE_SECTION_SRC, /mode=generate-section/);
  // Linked-context shape — what the skill needs to draft
  assert.match(GENERATE_SECTION_SRC, /linked_papers=/);
  assert.match(GENERATE_SECTION_SRC, /linked_stat_results=/);
  assert.match(GENERATE_SECTION_SRC, /linked_figures=/);
  assert.match(GENERATE_SECTION_SRC, /existing_sections=/);
  // Persists section-draft via the same store path so version + sidecar
  // stay consistent with the rest of the dashboard. Phase 44 introduced
  // a `proj` non-null alias inside the detached runner; either form
  // satisfies the contract.
  assert.match(GENERATE_SECTION_SRC, /saveSection\((project|proj)\.path/);
  assert.match(GENERATE_SECTION_SRC, /version:\s*(section|sec)\.version \+ 1/);
});

test("/api/draft/[slug]/generate-section emits the standard runner exit contract (Phase 4)", () => {
  const src = GENERATE_SECTION_SRC;
  // Same lastExit pattern as data/interpret + draft/[slug]/action.
  assert.match(src, /let lastExit:[\s\S]+?\| null = null;/);
  assert.match(src, /if \(evt\.type === "exit"\) lastExit = evt;/);
  // The done payload carries success / reason / exit_code / message.
  // Phase 10 hotfix: reason is now a computed local with the same
  // `lastExit?.reason ?? "failed"` floor — the contract is preserved
  // even though the literal expression moved out of the send() call.
  assert.match(src, /success: lastExit\?\.success \?\? false/);
  assert.match(src, /lastExit\?\.reason \?\? "failed"/);
  assert.match(src, /\breason,?\s*\n\s*exit_code:/);
  assert.match(src, /exit_code: lastExit\?\.code \?\? null/);
  assert.match(src, /message: lastExit\?\.message/);
  // SSE wire format — headers and content type
  assert.match(src, /Content-Type": "text\/event-stream/);
});

test("/api/draft/[slug]/generate-title returns 3-5 candidates with rationale", () => {
  const src = GENERATE_TITLE_SRC;
  assert.match(src, /skill: "sci-writing"/);
  assert.match(src, /mode=generate-title/);
  // Narrowing accepts only the bounded candidate count
  assert.match(src, /candidates\.length >= 3/);
  assert.match(src, /candidates\.length <= 5/);
  // Each candidate carries title + rationale strings
  assert.match(src, /typeof \(c as \{ title\?: unknown \}\)\.title === "string"/);
  assert.match(src, /typeof \(c as \{ rationale\?: unknown \}\)\.rationale === "string"/);
  // Phase 4 done-event contract
  assert.match(src, /success: lastExit\?\.success \?\? false/);
  assert.match(src, /reason: lastExit\?\.reason \?\? "failed"/);
  assert.match(src, /exit_code: lastExit\?\.code \?\? null/);
  // SKILL.md documents the contract on the writer side
  assert.match(SCI_WRITING_SKILL, /Step 7\.8/);
  assert.match(SCI_WRITING_SKILL, /title-candidates/);
  assert.match(SCI_WRITING_SKILL, /3 to 5 candidates/);
});

test("Draft-all wizard fans out sequentially with cap=2 parallelism", () => {
  // Cap declared as a constant so a future tweak is reviewable in one
  // place. Anything other than 2 here will turn this test red — the
  // research rationale is "cap=2 to avoid LLM rate limits" (plan §5.1).
  assert.match(WORKSPACE_SRC, /DRAFT_ALL_PARALLEL_CAP\s*=\s*2/);
  // Wizard handler uses the cap to bound the worker count.
  assert.match(WORKSPACE_SRC, /Math\.min\(DRAFT_ALL_PARALLEL_CAP, targets\.length\)/);
  // Sequential queue inside each worker — pop next, await, repeat.
  assert.match(WORKSPACE_SRC, /const launch = async \(\): Promise<void>/);
  assert.match(WORKSPACE_SRC, /while \(queue\.length > 0\)/);
  assert.match(WORKSPACE_SRC, /await generateOneSection\(next\)/);
  // Surfaces a header-level "Draft all sections" button.
  assert.match(WORKSPACE_SRC, /data-draft-all-button/);
  assert.match(WORKSPACE_SRC, /Draft all sections/);
  // References section is skipped — that body is auto-populated from
  // \cite{} blocks at export time, not drafted by the LLM.
  assert.match(WORKSPACE_SRC, /id === "references"/);
});

test("RunStateCard now mounts on /draft (closes Phase 6 deferred H-5 follow-up)", () => {
  // Import + mount in the manuscript workspace.
  assert.match(WORKSPACE_SRC, /import \{ RunStateCard, type RunState \}/);
  assert.match(WORKSPACE_SRC, /<RunStateCard/);
  // Drives state through the documented union — at least running +
  // succeeded + failed must be reachable from the generate flow.
  assert.match(WORKSPACE_SRC, /setGenerateRunState\("running"\)/);
  assert.match(WORKSPACE_SRC, /setGenerateRunState\("succeeded"\)/);
  assert.match(WORKSPACE_SRC, /setGenerateRunState\("failed"\)/);
  // Elapsed counter is wired so the card's mm:ss display advances.
  assert.match(WORKSPACE_SRC, /generateStartRef\.current = Date\.now\(\)/);
  assert.match(WORKSPACE_SRC, /elapsedMs=\{generateElapsed\}/);
  // Retry/Dismiss handlers are wired (RunStateCard's contract requires
  // them on failed/timeout to render the buttons).
  assert.match(WORKSPACE_SRC, /onRetry=/);
  assert.match(WORKSPACE_SRC, /onDismiss=/);
});

test("Propose-title button lives in the manuscript-create form with candidate list", () => {
  // Button surface
  assert.match(DRAFT_LIST_SRC, /data-propose-title-button/);
  assert.match(DRAFT_LIST_SRC, /Propose title/);
  // Candidate list renders title + rationale per item
  assert.match(DRAFT_LIST_SRC, /data-title-candidates/);
  assert.match(DRAFT_LIST_SRC, /candidates\.map/);
  assert.match(DRAFT_LIST_SRC, /\{c\.title\}/);
  assert.match(DRAFT_LIST_SRC, /\{c\.rationale\}/);
  // Selecting a candidate populates the title input directly — no extra
  // confirmation hop. The plan §5.1 requires "user picks → field is
  // populated" not a modal.
  assert.match(DRAFT_LIST_SRC, /setTitle\(c\.title\)/);
  // POSTs to the generate-title route; uses the SSE pattern so the
  // candidates can arrive via either the artifact event or the done
  // event's echoed candidates field.
  assert.match(DRAFT_LIST_SRC, /\/generate-title/);
  assert.match(DRAFT_LIST_SRC, /title-candidates/);
});

// ---------------------------------------------------------------------
// Phase 10 hotfix (2026-05-07) regression contract.
//
// Scope:
//   B1 — honest done-state when the skill exits clean but emits no
//        valid section-draft (route adds reason="succeeded-no-artifact"
//        + fallback-content recovery; UI surfaces it as failed).
//   B2 — section_type validation: rejects misrouted bodies before
//        persisting them to the wrong slot.
//   N1 — "Draft all sections" button has a tooltip listing the inputs.
//   N2-lite — optional "instructions" textbox flows through both
//        /generate-section and /action POST bodies.
//   N3 — autosave debounce on the editor.
//   N4 — syntax cheatsheet button + popover content.
// ---------------------------------------------------------------------

test("validate.ts rejects misrouted body content per section_type", () => {
  // Title slot: must have h1, must NOT have h2, must be ≤ 500 chars.
  assert.match(VALIDATE_SRC, /case "title":/);
  assert.match(VALIDATE_SRC, /TITLE_MAX_CHARS\s*=\s*500/);
  assert.match(VALIDATE_SRC, /\^#\\s\+\\S/);
  assert.match(VALIDATE_SRC, /Title body contains an h2 heading/);
  // Body sections each have a heading regex pinned to the section name.
  for (const section of ["abstract", "introduction", "methods", "results", "discussion"]) {
    assert.ok(
      VALIDATE_SRC.includes(`${section}:`),
      `validate must define heading regex for ${section}`,
    );
  }
  // References slot is explicitly refused (auto-populated, not generated).
  assert.match(VALIDATE_SRC, /case "references":/);
  assert.match(VALIDATE_SRC, /auto-populated from \\\\cite/);
  // Custom slot is permissive (only checks non-empty).
  assert.match(VALIDATE_SRC, /case "custom":/);
  // Public surface: validateGeneratedContent returns ValidationResult.
  assert.match(VALIDATE_SRC, /export function validateGeneratedContent\(/);
  assert.match(VALIDATE_SRC, /\| \{ ok: true \}/);
  assert.match(VALIDATE_SRC, /\| \{ ok: false; reason: string \}/);
  // Fallback extractor exported separately.
  assert.match(VALIDATE_SRC, /export function extractFallbackContent\(/);
});

test("/generate-section validates emitted content + tracks persistence (B1 + B2)", () => {
  const src = GENERATE_SECTION_SRC;
  // Imports the validator + fallback helper.
  assert.match(src, /import \{[\s\S]+?validateGeneratedContent[\s\S]+?\} from "@\/lib\/draft\/validate"/);
  assert.match(src, /extractFallbackContent/);
  // Persists ONLY when validation passes.
  assert.match(src, /verdict\.ok/);
  assert.match(src, /validationFailures\.push/);
  // Sends a `warning` event with kind="validation-failed" on rejection.
  assert.match(src, /kind: "validation-failed"/);
  // Fallback path on success-without-artifact: tries fallback, sends
  // kind="fallback-content" warning if recovered.
  assert.match(src, /lastExit\?\.success/);
  assert.match(src, /extractFallbackContent\(stdoutAccumulated, sectionType\)/);
  assert.match(src, /kind: "fallback-content"/);
  // Done event carries persisted + reason in the new shape:
  // - reason="validation-failed" when exit-clean + only validation rejections
  // - reason="succeeded-no-artifact" when exit-clean + nothing emitted at all
  // - reason="succeeded-via-fallback" when exit-clean + fallback recovered
  assert.match(src, /"validation-failed"/);
  assert.match(src, /"succeeded-no-artifact"/);
  assert.match(src, /"succeeded-via-fallback"/);
  assert.match(src, /persisted: persisted \?/);
  assert.match(src, /used_fallback: usedFallback/);
  // Idempotency: only the first valid artifact is persisted (skill may
  // emit more than one in the stream — we don't bump the version twice).
  assert.match(src, /art\.section_id === body\.section_id &&\s*\n\s*!persisted/);
  // SECTION_SHAPE hint travels in the prompt so the skill knows the slot.
  assert.match(src, /SECTION_SHAPE: \$\{sectionShapeHint\}/);
});

test("/generate-section + /action accept optional instructions (N2-lite)", () => {
  // Generate-section route.
  assert.match(GENERATE_SECTION_SRC, /instructions\?: string;/);
  assert.match(GENERATE_SECTION_SRC, /userInstructions = \(body\.instructions \?\? ""\)\.trim\(\)/);
  assert.match(GENERATE_SECTION_SRC, /user_instructions=/);
  // Action route — reused for Rewrite/Tighten/Check/Humanize.
  assert.match(ACTION_SRC, /instructions\?: string;/);
  assert.match(ACTION_SRC, /userInstructions = \(body\.instructions \?\? ""\)\.trim\(\)/);
  assert.match(ACTION_SRC, /user_instructions=/);
  // Action route now carries section_type so the skill can apply the
  // SECTION_SHAPE guard the same way generate-section does.
  assert.match(ACTION_SRC, /section_type=\$\{section\.section_type\}/);
  assert.match(ACTION_SRC, /SECTION_SHAPE/);
  // Workspace forwards aiInstructions on both flows.
  assert.match(WORKSPACE_SRC, /aiInstructions, setAiInstructions/);
  assert.match(WORKSPACE_SRC, /instructions: aiInstructions\.trim\(\) \|\| undefined/);
  // Workspace renders an explicit textbox with a toggle.
  assert.match(WORKSPACE_SRC, /data-instructions-toggle/);
  assert.match(WORKSPACE_SRC, /data-instructions-textarea/);
});

test("Workspace surfaces honest done-state on succeeded-no-artifact (B1)", () => {
  // Tracks `persisted` from the done event; success without persistence
  // is rendered as failed, with the reason copy distinguishing the soft
  // failure shape.
  assert.match(WORKSPACE_SRC, /persisted = data\.persisted != null/);
  assert.match(WORKSPACE_SRC, /!success \|\| !persisted/);
  assert.match(WORKSPACE_SRC, /succeeded-no-artifact/);
  assert.match(WORKSPACE_SRC, /Generate ran but emitted no draft/);
  // Validation-failed reason has its own copy so the user sees what
  // happened, not just "failed".
  assert.match(WORKSPACE_SRC, /validation-failed/);
  assert.match(WORKSPACE_SRC, /didn't match the .+ section shape/);
  // Warnings the route emits on validation/fallback are surfaced into
  // the workspace error pane.
  assert.match(WORKSPACE_SRC, /data\?\.kind === "validation-failed"/);
  assert.match(WORKSPACE_SRC, /data\?\.kind === "fallback-content"/);
});

test("Draft-all button has a tooltip describing the inputs (N1)", () => {
  // The title attribute mentions every context source the route pulls
  // so a researcher can predict what the wizard does without reading
  // the route source.
  assert.match(WORKSPACE_SRC, /data-draft-all-button/);
  assert.match(WORKSPACE_SRC, /title="Drafts every section[\s\S]+linked papers[\s\S]+stat-results[\s\S]+figure artifacts[\s\S]+manuscript brief[\s\S]+sibling sections/);
});

test("Markdown editor autosaves on debounced inactivity (N3)", () => {
  // 1500 ms debounce constant exists with a clear name.
  assert.match(EDITOR_SRC, /AUTOSAVE_DEBOUNCE_MS\s*=\s*1500/);
  // Debounce is wired through a setTimeout that fires onSave.
  assert.match(EDITOR_SRC, /setTimeout\(\(\) => \{[\s\S]+?onSaveRef\.current\(\)/);
  // The "unsaved" indicator now mentions autosave so users don't think
  // they're losing work.
  assert.match(EDITOR_SRC, /unsaved · autosaves/);
  // Cleanup on unmount + on content prop change so we don't fire stale
  // saves after a section switch.
  assert.match(EDITOR_SRC, /clearTimeout\(autosaveTimer\.current\)/);
});

test("Syntax cheatsheet button + popover surfaces KaTeX + cite/fig examples (N4)", () => {
  // Button presence + data-attribute for click-test stability.
  assert.match(EDITOR_SRC, /import \{ SyntaxCheatsheet \}/);
  assert.match(EDITOR_SRC, /<SyntaxCheatsheet/);
  assert.match(CHEATSHEET_SRC, /data-syntax-cheatsheet-button/);
  assert.match(CHEATSHEET_SRC, /data-syntax-cheatsheet-panel/);
  // Each load-bearing syntax example appears.
  for (const example of [
    /Citation/, /\\\\cite\{Smith2026\}/,
    /Figure/, /\\\\fig\{fig-7\}/,
    /Inline math/, /\\\\bar\{x\}/,
    /Display math/, /\\\\bar\{x\} \\\\pm 2\\\\sigma/,
    /Heading/, /## Methods/,
    /Code span/, /Phase 9 hotfix/,
  ]) {
    assert.match(CHEATSHEET_SRC, example);
  }
});

test("sci-writing SKILL.md documents both new modes (Step 7.7 + 7.8)", () => {
  // Section-mode contract is the load-bearing bit — without it the
  // skill won't know what to emit when the route fires the prompt.
  assert.match(SCI_WRITING_SKILL, /Step 7\.7/);
  assert.match(SCI_WRITING_SKILL, /mode=generate-section/);
  assert.match(SCI_WRITING_SKILL, /\\cite\{cite_key\}/);
  assert.match(SCI_WRITING_SKILL, /\\fig\{fig_id\}/);
  // Title-mode constraint: 3–5, distinct, plain text, no superlatives
  assert.match(SCI_WRITING_SKILL, /Step 7\.8/);
  assert.match(SCI_WRITING_SKILL, /3 to 5 candidates/);
  // Step 0 routing table picks up the new modes
  assert.match(SCI_WRITING_SKILL, /dashboard-generate-section/);
  assert.match(SCI_WRITING_SKILL, /dashboard-generate-title/);
  // Phase 10 hotfix additions: per-section_type heading-shape table +
  // user_instructions documentation.
  assert.match(SCI_WRITING_SKILL, /Per-section_type heading-shape contract/);
  assert.match(SCI_WRITING_SKILL, /SECTION_SHAPE/);
  assert.match(SCI_WRITING_SKILL, /user_instructions/);
});
