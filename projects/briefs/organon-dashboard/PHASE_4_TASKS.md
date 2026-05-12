---
project: organon-dashboard
status: tactical-ready
phase: 4
created: 2026-05-06
parent_plan: PLAN.md
siblings: PHASE_1_TASKS.md, PHASE_2_TASKS.md, PHASE_3_TASKS.md
scope: /figures workspace + interactive region inpaint (PLAN §3 Phase 4)
out_of_scope: Phases 5–6 (PLAN §3.5–§3.6).
---

# Organon Dashboard — Phase 4 Tactical Plan

Bridge between PLAN.md and code, for **Phase 4 only**. Mirrors P1/P2/P3 shape. Phases 1–3 are shipped + dogfooded before Phase 4 starts.

## Table of Contents

1. [Phase 4 scope recap](#1-phase-4-scope-recap)
2. [Tactical decisions](#2-tactical-decisions)
3. [Repository layout](#3-repository-layout)
4. [Atomic task list (T01–T35)](#4-atomic-task-list)
5. [Artifact JSON schemas](#5-artifact-json-schemas)
6. [API contracts](#6-api-contracts)
7. [Component prop contracts](#7-component-prop-contracts)
8. [npm dependencies](#8-npm-dependencies)
9. [Dev-setup runbook](#9-dev-setup-runbook)
10. [Phase 4 acceptance gate](#10-phase-4-acceptance-gate)

---

## 1. Phase 4 scope recap

Eight deliverables from PLAN §3 Phase 4:

1. `/figures` workspace: prompt form + style picker (scientific / notebook / comic / color / mono / technical) matching `viz-nano-banana` styles.
2. Generated image renders in a canvas component.
3. Mask tools: circle / freehand lasso / rectangle. Drawn on canvas → captured as PNG with alpha + downsampled to source image dimensions.
4. Regional regenerate: "change just this part" with new prompt for masked region. Sends original + mask + new prompt to inpaint endpoint.
5. Dual-backend skill wiring: `viz-nano-banana --mode generate` → Gemini 3 Pro Image (existing); `viz-nano-banana --mode edit --image X --mask Y --prompt "..."` → FAL FLUX.1 [pro] Fill (new).
6. Inpainting API: `/api/images/edit` accepts `{base_image, mask, prompt, project, fig_id}`; validates mask dimensions; uploads to FAL media URL; calls FLUX Fill; persists `figures/{fig_id}/v{N}.png`.
7. Version history per figure (thumbnail strip; click to revert; metadata sidecar).
8. "Lock figure" → freezes version, generates caption + alt text via `sci-writing`.

---

## 2. Tactical decisions

| # | Decision | Choice | Rationale |
|---|---|---|---|
| D1 | **Backend split** | Gemini 3 Pro Image for primary text-to-image (existing `viz-nano-banana` path); FAL FLUX.1 [pro] Fill (`fal-ai/flux-pro/v1/fill`, $0.05/MP) for regional inpaint. Locked in PLAN §3 Phase 4 table 2026-05-06. | Best text-rendering for sci figures (Gemini); SOTA mask-input inpainting (FLUX Fill); Gemini doesn't expose mask-based editing. |
| D2 | **FAL lib lift** | Port `lib/fal.py` from `business-os/.claude/skills/ops-media-pipeline/lib/fal.py` into Organon at `.claude/skills/viz-nano-banana/lib/fal.py`. Strip non-image kinds (video, training, LoRA); register only `flux-pro-fill`. Add the FLUX Fill endpoint + payload helper not present in business-os. | Lift the auth + retry + error-handling spine; trim what we don't need. Single skill is the consumer in Phase 4. |
| D3 | **Mask format** | PNG with alpha channel; dimensions exactly match base image (no resize). Validation server-side; mismatch → 400. | FAL FLUX Fill requires exact-size mask. Auto-resize would silently degrade quality on the boundary. |
| D4 | **Mask tool UX** | HTML5 `<canvas>` overlay above the image canvas. Three tool modes: circle (drag from center), freehand lasso (mousedown/mousemove path → close), rectangle (drag bounding box). All produce a binary alpha PNG via `canvas.toBlob('image/png')`. Toolbar buttons toggle mode. `Esc` clears the current mask. | Native canvas; no `react-konva` or other lib (D9). |
| D5 | **Versioning** | Each generate or edit creates `figures/{fig_id}/v{N}.png` + `v{N}.json` sidecar (metadata: prompt, mask path if edit, backend, cost_cents, parent_version, created). The "main" version is the highest N. Thumbnail strip in UI orders ascending. | Simple monotonic versioning; no symlinks (P1 D-style filesystem-only). |
| D6 | **Cost gate** | Pre-fire confirmation: "This edit will cost ~$0.05" with "don't ask again this session" toggle. Default ON. Cumulative session cost shown in topbar. | Iterative editing can run up costs fast; cost transparency is a researcher-trust feature. |
| D7 | **Lock + caption** | "Lock figure" marks the current version locked (UI badge + edit disabled). Then fires `sci-writing` in caption pseudo-mode (one prompt: image path + figure context) → returns caption + alt text. Both persist to the version sidecar. | Forces the accessibility metadata before figure leaves the workspace. PLAN §6.5 ("Caption + alt text generated on lock"). |
| D8 | **Style picker confirmation gate** | Match `viz-nano-banana` Step 3 — style picker is a **confirmation gate**, not auto-pick. User must explicitly select scientific / notebook / comic / color / mono / technical. Sub-style for scientific (publication / conceptual / etc.) confirmed inline. | Existing skill convention; PLAN §6.5 callout; user feedback memory `feedback_mandatory_confirmations.md` ("NEVER skip figure style"). |
| D9 | **No new client libs** | Mask drawing on raw canvas; no `react-konva` / `fabric.js`. Toolbar with Tailwind. Image renderer is `<img>` + absolutely-positioned overlay canvas. | Phase 4's mask tools are simple shapes; a full canvas lib would be over-engineering for circle/lasso/rectangle. |
| D10 | **Out of scope** | Animated GIFs, video, character LoRAs, Seedream-style ref-locked editing, multi-mask compositions, multi-frame storyboards. | Defer until quality justifies the prompt-retune cost (~3 days × 36 templates per PLAN §3 Phase 4 note). |

---

## 3. Repository layout

```
src/
├── app/
│   ├── figures/page.tsx                         # T13 — replaces P1 stub
│   └── api/
│       └── images/
│           ├── generate/route.ts                # T23 — fires viz-nano-banana --mode generate
│           ├── edit/route.ts                    # T24 — fires viz-nano-banana --mode edit (FAL Fill)
│           ├── lock/route.ts                    # T26 — fires sci-writing caption pseudo-mode
│           └── (versions served via existing /api/figures/[fig_id]/v[n].png from P3 T27-static)
├── components/figures/
│   ├── figures-workspace.tsx                    # T13 — composes
│   ├── prompt-form.tsx                          # T14 — claim + style picker
│   ├── style-picker.tsx                         # T15 — 6 styles + sub-style confirm
│   ├── image-canvas.tsx                         # T17 — renders current version + overlay
│   ├── mask-tools.tsx                           # T18 — circle / lasso / rectangle toolbar
│   ├── version-strip.tsx                        # T20 — thumbnail history
│   ├── caption-card.tsx                         # T22 — lock + caption + alt text
│   └── cost-gate-modal.tsx                      # T19 — D6 confirmation
└── lib/
    └── images/
        ├── fal-client.ts                        # T11 — TS wrapper around FAL REST (auth, retry, upload)
        ├── mask.ts                              # T16 — canvas → PNG conversion + dimension check
        ├── versions.ts                          # T21 — read/write figures/{fig_id}/v{N}.* + sidecar
        └── pricing.ts                           # T25 — cost_cents per call
```

`viz-nano-banana` skill gets new `--mode edit` flag + lifted `lib/fal.py`.

---

## 4. Atomic task list

35 tasks.

### 4.1 Track A — Bootstrap + FAL setup (T01–T05)

| ID | Task | Effort | Risk |
|---|---|---|---|
| **T01** | Append "Phase 4" callout to README. | S | 🟢 |
| **T02** | Confirm Phase 3 acceptance gate green. | S | 🟢 |
| **T03** | Add `FAL_KEY` to `.env.example` + Service Registry in CLAUDE.md (entry: "FAL — `fal-ai/flux-pro/v1/fill`, $0.05/MP, used by `viz-nano-banana --mode edit`"). | S | 🟢 |
| **T04** | Verify `FAL_KEY` is set in user's `.env`. If missing, fail fast with a "set FAL_KEY in .env to enable Phase 4 inpaint" message in the dashboard's startup log. | S | 🟢 |
| **T05** | Forward-compat parser test: inject a forged `_artifact: figure` line with v2 fields (parent_version, mask_path, backend="fal-flux-fill") and assert no crash + correct typing. | S | 🟢 |

### 4.2 Track B — FAL lib port (T06–T12)

| ID | Task | Effort | Risk |
|---|---|---|---|
| **T06** | Lift `lib/fal.py` from `business-os/.claude/skills/ops-media-pipeline/lib/fal.py` into `.claude/skills/viz-nano-banana/lib/fal.py`. | M | 🟡 |
| **T07** | Strip non-image kinds (video, training, LoRA, image-to-video). Keep only image text-to-image and image-edit families. | M | 🟢 |
| **T08** | Add a `flux_pro_fill_payload(prompt, image_url, mask_url, ...)` helper + `FLUX_PRO_FILL_ENDPOINT = "https://fal.run/fal-ai/flux-pro/v1/fill"`. Register `"flux-pro-fill"` in `MODELS`. | M | 🟡 |
| **T09** | Add a media-upload helper using FAL's `/storage/upload` endpoint for the base image + mask. | M | 🟡 |
| **T10** | Update `viz-nano-banana/SKILL.md` to document the new `--mode edit` flag + payload contract. | M | 🟢 |
| **T11** | Build TS-side client `lib/images/fal-client.ts` that talks to the SAME endpoints — used by `/api/images/edit` directly without spawning Python (`fal.py` is for CLI usage; the dashboard hits FAL via fetch in TS for lower latency on regional edits). | L | 🟡 |
| **T12** | Smoke test FAL with a 2 MP test image + 256-byte test mask + 5-word prompt; assert returned URL resolves. | S | 🟡 |

### 4.3 Track C — /figures workspace UI (T13–T22)

| ID | Task | Effort | Risk |
|---|---|---|---|
| **T13** | Build `app/figures/page.tsx` (server) + `<FiguresWorkspace>` client. Reads project, lists `figures/` dir, renders. | M | 🟢 |
| **T14** | `<PromptForm>` — prompt textarea + `<StylePicker>` slot + Generate button. | M | 🟢 |
| **T15** | `<StylePicker>` — 6 main styles (radio) + scientific sub-style picker if scientific selected. Confirmation gate (D8). | M | 🟢 |
| **T16** | `lib/images/mask.ts` — canvas → PNG blob; dimension validator; downsample (only if explicit user opt-in). | M | 🟢 |
| **T17** | `<ImageCanvas>` — renders current version's PNG with overlay `<canvas>` for mask drawing. Aspect-ratio preserved. | L | 🟡 |
| **T18** | `<MaskTools>` — toolbar (circle / lasso / rectangle / clear). State uplifted. | L | 🟡 |
| **T19** | `<CostGateModal>` — D6 pre-fire confirm with session-toggle. | M | 🟢 |
| **T20** | `<VersionStrip>` — thumbnail history; click to switch active version; mark locked versions. | M | 🟢 |
| **T21** | `lib/images/versions.ts` — read/write `figures/{fig_id}/v{N}.*` + sidecars; `getMainVersion(fig_id)`, `appendVersion(...)`, `setLocked(fig_id, version)`. | M | 🟢 |
| **T22** | `<CaptionCard>` — shows caption + alt text after lock; "Regenerate caption" button. | M | 🟢 |

### 4.4 Track D — API contracts (T23–T27)

| ID | Task | Effort | Risk |
|---|---|---|---|
| **T23** | `/api/images/generate` — POST: fires `viz-nano-banana --mode generate` via `/api/execute`; allocates `fig_id` (P3 T07); skill emits `_artifact: figure` v1. | M | 🟡 |
| **T24** | `/api/images/edit` — POST: validates mask dim (D3); calls FAL Fill via `lib/images/fal-client.ts` (T11); on success appends version + emits SSE `event: artifact` with the new figure version. | L | 🔴 |
| **T25** | `lib/images/pricing.ts` — `flux_fill_cost_cents(megapixels): number` returning `Math.ceil(megapixels * 5)`. Unit-tested. | S | 🟢 |
| **T26** | `/api/images/lock` — POST: spawns `sci-writing` caption pseudo-mode; persists caption + alt text to version sidecar. | M | 🟡 |
| **T27** | Static-file route extension (P3 T27-static): also serve `/api/figures/[fig_id]/mask/v[n].png` for verification. | S | 🟢 |

### 4.5 Track E — Skill teaching (T28–T31)

| ID | Task | Effort | Risk |
|---|---|---|---|
| **T28** | Update `.claude/skills/viz-nano-banana/SKILL.md` — Step 1.5 (artifact emission) emits `_artifact: figure` v1 (generate path) or v(N+1) (edit path). The edit path includes `parent_version`, `backend: "fal-flux-fill"`, `cost_cents`, `mask_path`. | L | 🟡 |
| **T29** | Add the `--mode edit` flag handling: load image from `--image` path, load mask from `--mask` path, validate dims, call `flux_pro_fill_payload`, write output to `figures/{fig_id}/v{N+1}.png`, write sidecar. | L | 🟡 |
| **T30** | Update `.claude/skills/sci-writing/SKILL.md` — caption pseudo-mode: emit `_artifact: figure` patch with `caption` + `alt_text` populated; do NOT emit a section-draft (that's Phase 5). | M | 🟢 |
| **T31** | Skill-contract smoke test: round-trip for generate + edit + lock; assert artifacts persist + sidecars correct. | M | 🟡 |

### 4.6 Track F — Polish + acceptance (T32–T35)

| ID | Task | Effort | Risk |
|---|---|---|---|
| **T32** | Extend `<CommandPalette>` with: `Go to Figures`, `New figure`, `Edit current figure region`, `Lock current figure`. | S | 🟢 |
| **T33** | Hook the Figures workspace into `<PaperDetail>`'s "Generate hypothesis from this paper" — actually no-op for Phase 4; placeholder remains. (Cross-link is Phase 5 job.) | S | 🟢 |
| **T34** | Manual test plan walk: Generate "schematic of CRISPR Cas9 binding to target DNA, scientific style" → image renders within 30 s. Lasso around Cas9 → "make it look more like a clamp" → only that region changes. Version history shows 3+ versions; click old → reverts. Lock → caption + alt text appear. | M | 🟡 |
| **T35** | Phase 4 ship checklist: README updated, `/figures` reachable + functional, build + typecheck clean, no console errors, `figures/{fig_id}/` directories created lazily, FAL_KEY present check. | S | 🟢 |

**Total: 35 tasks. ~6–8 working days.**

---

## 5. Artifact JSON schemas

Phase 3 already defined `_artifact: figure` v1 (§5.3 of PHASE_3). Phase 4 extends:

```jsonc
{
  "_artifact": "figure",
  "schema_version": 1,                           // unchanged
  "id": "fig-20260601-3a7c91",
  "version": 2,                                  // ≥ 2 means edit applied
  "kind": "image",                               // "plot" (Phase 3) | "image" (Phase 4)
  "backend": "fal-flux-fill",                    // "matplotlib" | "seaborn" | "gemini" | "fal-flux-fill"
  "parent_version": 1,                           // null for v1; required for v2+
  "params": {
    "prompt": "make this protein look more like a clamp",
    "style": null,                               // edit mode does not re-apply style
    "mask_megapixels": 0.42
  },
  "mask_path": "projects/{slug}/figures/fig-.../mask/v2.png",  // only when version ≥ 2
  "cost_cents": 3,                               // Phase 4 populates from pricing.ts
  "locked": false,                               // T20 + T26 set true on lock
  "caption": null,                               // populated on lock
  "alt_text": null,                              // populated on lock
  "png_path": "projects/{slug}/figures/fig-.../v2.png",
  "library_path": "projects/{slug}/figures/fig-.../v2.png",
  "code_path": null,                             // null for AI-generated; matplotlib code lives only on plot kind
  "data_source": null,                           // null for AI-generated
  "created_at": "2026-06-01T14:23:00.000Z"
}
```

Other types unchanged.

---

## 6. API contracts

### 6.1 `POST /api/images/generate`

**Request.** `{project, prompt, style, sub_style?, fig_id?}` — fig_id optional; if absent, server allocates.

**Response.** SSE; skill emits `_artifact: figure` v1.

### 6.2 `POST /api/images/edit`

**Request.** `multipart/form-data` with `prompt`, `mask` (PNG), `fig_id`, `project`. Base image read server-side from the latest version of `fig_id`.

**Response.** SSE — emits `_artifact: figure` v(N+1) on completion. Errors: 400 (mask dim mismatch), 402 (FAL_KEY missing), 502 (FAL upstream), 504 (timeout > 90s).

### 6.3 `POST /api/images/lock`

**Request.** `{project, fig_id, version}`.

**Response.** SSE; sci-writing caption pseudo-mode emits a figure patch with caption + alt_text. Updates sidecar.

---

## 7. Component prop contracts

### 7.1 `<PromptForm>` / `<StylePicker>` / `<ImageCanvas>` / `<MaskTools>` / `<VersionStrip>` / `<CaptionCard>` / `<CostGateModal>`

```typescript
type PromptFormProps = { onSubmit: (p: { prompt: string; style: Style; sub_style?: SubStyle }) => void; loading?: boolean };
type StylePickerProps = { value: Style | null; onChange: (s: Style) => void; subStyle?: SubStyle | null; onSubChange?: (s: SubStyle) => void };
type Style = "scientific" | "notebook" | "comic" | "color" | "mono" | "technical";
type SubStyle = "publication" | "conceptual" | "schematic" | "data-driven";  // applies only when Style=scientific
type ImageCanvasProps = { figure: FigureArtifact; mode: "view" | "mask"; onMaskChange?: (blob: Blob) => void; tool: MaskTool };
type MaskTool = "circle" | "lasso" | "rectangle" | "none";
type MaskToolsProps = { active: MaskTool; onChange: (t: MaskTool) => void; onClear: () => void };
type VersionStripProps = { versions: FigureArtifact[]; activeVersion: number; onSelect: (v: number) => void };
type CaptionCardProps = { figure: FigureArtifact; onLock: () => void; onRegenerate: () => void };
type CostGateModalProps = { estimateCents: number; open: boolean; onConfirm: (rememberSession: boolean) => void; onCancel: () => void };
```

### 7.2 `<FiguresWorkspace>` (composite)

```typescript
type FiguresWorkspaceProps = {
  project: string;
  initialFigures: FigureArtifact[];              // grouped by fig_id, latest version first
  initialFigId?: string;                         // ?fig={id} deep link
};
```

---

## 8. npm dependencies

**No new runtime dependencies.** Native canvas + `<img>` + Tailwind. FAL client is `fetch` + FormData.

---

## 9. Dev-setup runbook

### 9.1 Prerequisites (delta)

| Tool | Version | Check |
|---|---|---|
| Phase 3 acceptance gate | green | T02 |
| `FAL_KEY` | set | `grep FAL_KEY .env` |
| `viz-nano-banana` skill | installed | `ls .claude/skills/viz-nano-banana/SKILL.md` |
| Python venv with PIL/numpy (for skill-side mask sanity check) | populated | `.claude/skills/viz-nano-banana/.venv/bin/python -c "import PIL"` |

### 9.2 Smoke test

1. `/figures` renders. Click "New figure" → prompt form.
2. Enter "schematic of CRISPR Cas9 binding to target DNA" + style=scientific → confirm sub-style → Generate → image appears within 30 s.
3. Click "Edit region" → mask tools enabled. Lasso around protein → "make it look more like a clamp" → CostGate confirm → image v2 renders within 30 s; only the masked region changed.
4. Version strip shows v1, v2. Click v1 → main canvas reverts.
5. Lock current → caption + alt text populate within 15 s.
6. `ls projects/{slug}/figures/{fig_id}/` → v1.png + v1.json + v2.png + v2.json + mask/v2.png.

---

## 10. Phase 4 acceptance gate

- [ ] Generate "schematic of CRISPR Cas9..." → renders within 30 s.
- [ ] Lasso + "make it look more like a clamp" → only that region changes; rest preserved within visual tolerance.
- [ ] Version history shows ≥ 3 versions; click old → reverts.
- [ ] "Lock + caption" → caption includes the regenerated detail.
- [ ] Cost gate fires + can be dismissed for the session.
- [ ] FAL errors (timeout, key missing) surface as readable UI errors.
- [ ] All Phase 1/2/3 workspaces still functional.
- [ ] `npm run build` + typecheck exit 0.
- [ ] Smoke test §9.2 passes end-to-end.

After ticking: dogfood ≥ 1 week, then plan Phase 5.

---

*End of Phase 4 tactical plan.*
