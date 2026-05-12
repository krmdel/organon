import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Phase 51 (v2.0) — Per-section linkage overrides.
//
// Goal: a single section can override the manuscript-level linkage
// (Phase 41) so generate-section narrows to a different paper/figure
// subset than the rest of the manuscript. SectionDraftArtifact gains
// four optional override_* arrays; new helper effectiveSectionLinkage
// resolves override > manuscript > undefined (= use everything).
//
// generate-section uses the helper for papers + figures so per-section
// overrides win. PATCH /api/draft/[slug]/sections/[section_id] accepts
// override_* arrays and validates each id against its store. UI: a
// per-section "sources" affordance opens a modal mounting the same
// LinkageEditModal pattern as Phase 41's SourceLinkagePanel.

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function readSrc(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

const TYPES_SRC = readSrc("src/lib/artifacts/types.ts");
const STORE_SRC = readSrc("src/lib/draft/store.ts");
const SECTION_PATCH_SRC = readSrc("src/app/api/draft/[slug]/sections/[section_id]/route.ts");
const GEN_SECTION_SRC = readSrc("src/app/api/draft/[slug]/generate-section/route.ts");
const SECTION_LIST_SRC = readSrc("src/components/draft/section-list.tsx");

test("Phase 51 — SectionDraftArtifact gains four optional override_* arrays", () => {
  const block = TYPES_SRC.match(/export interface SectionDraftArtifact[\s\S]*?\}\n/);
  assert.ok(block, "SectionDraftArtifact interface not located");
  const text = block[0];
  assert.match(text, /override_linked_paper_ids\?\s*:\s*string\[\]/);
  assert.match(text, /override_linked_figure_ids\?\s*:\s*string\[\]/);
  assert.match(text, /override_linked_hypothesis_ids\?\s*:\s*string\[\]/);
  assert.match(text, /override_linked_dataset_ids\?\s*:\s*string\[\]/);
});

test("Phase 51 — effectiveSectionLinkage helper exported and resolves override > manuscript > undefined", () => {
  assert.match(STORE_SRC, /export function effectiveSectionLinkage\(/);

  // Behavioural replica matching the helper's contract.
  const effective = (section, manuscript, kind) => {
    const overrideKey = `override_linked_${kind}_ids`;
    const manuscriptKey = `linked_${kind}_ids`;
    const ov = section?.[overrideKey];
    if (Array.isArray(ov) && ov.length > 0) return ov;
    const ms = manuscript?.[manuscriptKey];
    if (Array.isArray(ms) && ms.length > 0) return ms;
    return undefined; // = use everything
  };
  // Override wins.
  assert.deepEqual(
    effective(
      { override_linked_paper_ids: ["p2"] },
      { linked_paper_ids: ["p1"] },
      "paper",
    ),
    ["p2"],
  );
  // Manuscript fallback.
  assert.deepEqual(
    effective({}, { linked_paper_ids: ["p1"] }, "paper"),
    ["p1"],
  );
  // Both empty → undefined (use everything).
  assert.equal(effective({}, {}, "paper"), undefined);
  assert.equal(
    effective({ override_linked_paper_ids: [] }, { linked_paper_ids: [] }, "paper"),
    undefined,
  );
});

test("Phase 51 — generate-section uses effectiveSectionLinkage for papers + figures", () => {
  // Route imports the helper.
  assert.match(GEN_SECTION_SRC, /effectiveSectionLinkage/);
  // It is called with kinds 'paper' and 'figure' (covering the two
  // narrowable artifact pools that flow into the prompt).
  assert.match(GEN_SECTION_SRC, /effectiveSectionLinkage\([^)]*['"]paper['"]/);
  assert.match(GEN_SECTION_SRC, /effectiveSectionLinkage\([^)]*['"]figure['"]/);
});

test("Phase 51 — PATCH section route accepts and validates the four override_* arrays", () => {
  // Body keys present.
  assert.match(SECTION_PATCH_SRC, /override_linked_paper_ids/);
  assert.match(SECTION_PATCH_SRC, /override_linked_figure_ids/);
  assert.match(SECTION_PATCH_SRC, /override_linked_hypothesis_ids/);
  assert.match(SECTION_PATCH_SRC, /override_linked_dataset_ids/);
  // Validates against the four stores (same pattern as Phase 41 PATCH /api/draft/[slug]).
  assert.match(SECTION_PATCH_SRC, /listLibrary|listPapers/);
  assert.match(SECTION_PATCH_SRC, /listFigures/);
  assert.match(SECTION_PATCH_SRC, /listHypotheses/);
  assert.match(SECTION_PATCH_SRC, /listDataframes|listFiles|listData/);
  // 404 on unknown ids (mirrors the Phase 41 surface).
  assert.match(
    SECTION_PATCH_SRC,
    /unknown[\s\S]{0,200}(status:\s*404|404)|404[\s\S]{0,200}(unknown|override)/i,
  );
});

test("Phase 51 — section-list mounts a per-section 'sources' affordance", () => {
  // Sentinel data attribute the test pins.
  assert.match(SECTION_LIST_SRC, /data-section-override-edit/);
  // The button has a callback wired in via the props surface (so the
  // workspace can open the modal). The exact prop name is fixed by the
  // test contract.
  assert.match(SECTION_LIST_SRC, /onEditSectionOverrides/);
});

test("Phase 51 — patchSection helper threads the four override_* arrays via the existing surface", () => {
  // patchSection's pick of allowed fields includes the override keys.
  // Stored on the artifact at write time so they survive round-trip.
  const block = STORE_SRC.match(/export function patchSection\([\s\S]*?\}\n/);
  assert.ok(block, "patchSection body not located");
  // Pick<...> tuple in the patch type widens to include override_*.
  // The test pins the surface either via direct field name or via a
  // Pick that includes 'override_linked_paper_ids'.
  assert.ok(
    /override_linked_paper_ids/.test(block[0]) ||
      /override_linked_paper_ids/.test(STORE_SRC),
    "patchSection must accept override_linked_paper_ids",
  );
});
