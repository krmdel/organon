import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 61 (v2.1) — B4: section-list two-row density + ## label.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const SRC = readSrc("src/components/draft/section-list.tsx");

test("Phase 61 — section-list lays out section label on its own row above the action chips", () => {
  // The brief asks for a SECOND row beneath the section label hosting
  // GENERATE / DRAFT / ⚙ src / ▲▼. The new sentinel
  // data-section-actions={id} pins the second row.
  assert.match(
    SRC,
    /data-section-actions=\{id\}/,
    "section-list must mount a second row with data-section-actions={id}",
  );
  assert.match(
    SRC,
    /data-section-label=\{id\}/,
    "section-list must label the heading row with data-section-label={id}",
  );
  // The label row must NOT be the same flex container as the chips —
  // they live in separate <div> children of the <li>.
  assert.match(
    SRC,
    /data-section-label[\s\S]{0,800}data-section-actions/,
    "data-section-label must appear before data-section-actions (label row above)",
  );
});

test("Phase 61 — section labels are not truncated in the new layout", () => {
  // Pre-Phase-61: the label className included `truncate`. The new
  // layout uses break-words so long section ids wrap instead of getting
  // cut off in narrow sidebars.
  // Find the data-section-label div and assert its className contains
  // break-words (not truncate).
  const labelMatch = SRC.match(/data-section-label=\{id\}[\s\S]{0,400}>/);
  assert.ok(labelMatch, "section-list must contain a data-section-label element");
  const labelBlock = labelMatch[0];
  assert.match(
    labelBlock,
    /break-words/,
    "section-label className must use break-words (not truncate)",
  );
  assert.doesNotMatch(
    labelBlock,
    /\btruncate\b/,
    "section-label className must NOT use truncate (would clip long ids)",
  );
});

test("Phase 61 — ⚙ src + GENERATE + DRAFT remain accessible via the same data-* sentinels", () => {
  // The action-chip sentinels from earlier phases must survive the
  // restructure so prior tests + browser E2E walks still pin.
  assert.match(
    SRC,
    /data-section-override-edit=\{id\}/,
    "⚙ src button must keep data-section-override-edit={id}",
  );
  assert.match(
    SRC,
    /<SectionGenerateButton/,
    "GENERATE button (SectionGenerateButton) must remain mounted",
  );
  assert.match(
    SRC,
    /<StatusBadgeSection/,
    "DRAFT badge (StatusBadgeSection) must remain mounted",
  );

  // Section labels render with the "## " prefix per the brief.
  assert.match(
    SRC,
    /## \{sect\.section_id\}/,
    "section label must render as '## {section_id}'",
  );
});
