---
phase: fixsprint-01
title: Project resolution helper + listProjects dedup + __root__ stays soft
date: 2026-05-06
fixplan_phase: 1 (revised in FIXPLAN.md Revision 2 — was old Phase 7)
critic_findings_addressed: C1 (resolveProject duplicate-slug bug), C4 (Phase 7 ordering — make __root__ soft, not strict)
estimated_effort: 0.5 day
---

# Phase fixsprint-01 — PLAN

## Phase 0.5 verification (already done)

Verified critic finding C1 against the live repo via
`/tmp/dedup-verify.mjs`. Confirmed:

- 34 total Project entries returned by `listProjects()`
- 33 unique slugs
- 1 duplicate: `dogfood-glp1-weight-regain` (both `projects/{slug}/` and
  `projects/briefs/{slug}/` exist)
- `resolveProject("dogfood-glp1-weight-regain")` returns the **non-brief**
  path (the wrong tree)

So Phase 1 must fix `listProjects()` itself — migration alone can't
prevent recurrence.

## Goal (one sentence)

Every API route resolves the active project through one helper that reads
query string → form body → referer URL → `__root__`, and `listProjects`
returns at most one entry per slug (brief wins when both shapes exist).

## Non-goals (explicit)

- **Do NOT make `__root__` a 400.** That breaks `tests/stress-suite.py` and
  external callers on day 1. Soft default with a `console.warn` is the
  right ergonomics until the migration is done. The strict-mode flip
  lands in Phase 9 ship gate, not here.
- **Do NOT migrate the existing dogfood split.** That's Phase 2's job.
  Phase 1's listProjects dedup makes the dashboard work *correctly* even
  when the split exists; Phase 2 cleans up the split itself.
- **Do NOT touch any persister or path-construction site.** That's Phase 2.

## Tasks

### T1.A — Add `resolveProjectFromRequest` helper

File: `src/lib/projects.ts`

Add at the bottom:

```ts
export function resolveProjectFromRequest(
  request: Request,
  formData?: FormData,
): Project | null {
  const url = new URL(request.url);
  let slug = url.searchParams.get("project");
  if (!slug && formData) {
    const v = formData.get("project");
    if (typeof v === "string" && v) slug = v;
  }
  if (!slug) {
    const ref = request.headers.get("referer");
    if (ref) {
      try { slug = new URL(ref).searchParams.get("project"); } catch { /* ignore */ }
    }
  }
  if (!slug) {
    slug = "__root__";
    console.warn(
      "[projects] No project specified in request — defaulting to __root__. " +
      `Path=${url.pathname}. Add ?project=<slug> or a 'project' form field, ` +
      "or set Referer to include ?project=<slug>.",
    );
  }
  return resolveProject(slug);
}
```

**Read first**: `src/lib/projects.ts` (current shape) — see existing
`resolveProject(slug)` at line 92-94.

**Acceptance**:
- `grep -n 'resolveProjectFromRequest' src/lib/projects.ts` returns at least
  one match.
- The function signature accepts `Request` and optional `FormData`.
- The four resolution priorities (query, form, referer, default) all
  exercise in the unit test.

### T1.B — Fix `listProjects` to dedup by slug

File: `src/lib/projects.ts`

Modify `listProjects()` (currently lines 31-89). After both loops finish
populating `out`, dedup so each slug appears at most once. **Brief wins**
when both shapes exist (per FIXPLAN Decision D1).

```ts
// At the end of listProjects(), after both loops:
const bySlug = new Map<string, Project>();
for (const p of out) {
  const existing = bySlug.get(p.slug);
  if (!existing) {
    bySlug.set(p.slug, p);
    continue;
  }
  // Brief always wins. Log once when we see the conflict.
  if (p.isBrief && !existing.isBrief) {
    console.warn(
      `[projects] Duplicate slug "${p.slug}" — both ` +
      `${existing.path} and ${p.path} exist. Brief wins; ` +
      "run scripts/migrate-split-projects.mjs to merge.",
    );
    bySlug.set(p.slug, p);
  } else if (!p.isBrief && existing.isBrief) {
    console.warn(
      `[projects] Duplicate slug "${p.slug}" — both ` +
      `${existing.path} and ${p.path} exist. Brief wins; ` +
      "run scripts/migrate-split-projects.mjs to merge.",
    );
    // existing already wins (it's the brief)
  }
  // If both are briefs (shouldn't happen) or both are non-briefs (shouldn't happen
  // because readdirSync returns each entry once), keep the first.
}
return [...bySlug.values()];
```

**Read first**: `src/lib/projects.ts` lines 1-150 (see how `Project` type
and the two loops construct entries).

**Acceptance**:
- `node /tmp/dedup-verify.mjs` (after pointing at the dashboard's
  compiled or transpiled module) reports 0 duplicate slugs.
- For the dogfood case, `resolveProject("dogfood-glp1-weight-regain")`
  returns the brief path (`projects/briefs/dogfood-glp1-weight-regain`),
  not the non-brief path.
- `console.warn` fires exactly once per duplicate-slug pair on server
  startup.

### T1.C — Replace ad-hoc resolution in 25 API routes

Files: every route under `src/app/api/**/route.ts` that does either:

- `const slug = body.project ?? "__root__";` then `resolveProject(slug)`
- `const slug = searchParams.get("project") ?? "__root__";` then
  `resolveProject(slug)`
- `const slug = String(form.get("project") ?? "__root__");` then
  `resolveProject(slug)`

For each, replace with one call to `resolveProjectFromRequest(request, formData?)`.

The 25 route files (from earlier grep audit):

| File | Existing pattern |
|------|-----------------|
| `data/load/route.ts` | form-body slug |
| `data/files/route.ts` | query-string slug |
| `data/figures/route.ts` | query-string slug |
| `data/results/route.ts` | query-string slug |
| `data/preview/[file_id]/route.ts` | query-string slug |
| `data/plot/route.ts` | query-string slug + body slug |
| `data/analyze/route.ts` | body slug |
| `draft/new/route.ts` | body slug |
| `draft/[slug]/route.ts` | query-string slug |
| `draft/[slug]/sections/route.ts` | query and body |
| `draft/[slug]/sections/[section_id]/route.ts` | query-string |
| `draft/[slug]/action/route.ts` | body slug |
| `draft/[slug]/export/route.ts` | body slug |
| `figures/[fig_id]/[file]/route.ts` | query-string |
| `figures/[fig_id]/mask/[file]/route.ts` | query-string |
| `hypothesis/route.ts` | query and body |
| `hypothesis/[hyp_id]/route.ts` | query-string + body |
| `hypothesis/reconcile/route.ts` | body slug |
| `images/generate/route.ts` | body slug |
| `images/edit/route.ts` | body slug |
| `images/lock/route.ts` | body slug |
| `images/[fig_id]/route.ts` | query-string slug |
| `personas/route.ts` | query and body |
| `execute/route.ts` | body slug |
| `tools/run/route.ts` | body slug |
| `tools/favourites/route.ts` | query-string |

**Read first**: pick three representative routes
(`data/load/route.ts`, `draft/new/route.ts`, `lit/library/route.ts`) and
read fully before editing the rest. Match their existing error-shape
(404 vs 400 on resolution failure).

**Acceptance**:
- `grep -n '"__root__"' src/app/api/**/route.ts` returns ZERO matches
  (the default moves into the helper).
- `grep -rn 'resolveProjectFromRequest' src/app/api/` returns ≥25 matches.
- Existing `npm test` (16 unit tests + 5 parser-phase tests) all pass.
- `npm run typecheck && npm run build` clean.

### T1.D — Regression tests

File: `tests/route-project-resolution.test.mjs` (new)

```js
import { test } from "node:test";
import assert from "node:assert/strict";

// Module-under-test path. We import via the compiled output if possible;
// otherwise we test the helper's logic via a small in-test re-implementation
// because the route-test setup needs Next infra. Real route integration
// goes through stress-suite.py.
//
// What we CAN unit-test in pure Node:
// - resolveProjectFromRequest priority order
// - listProjects dedup behavior
// (Both are pure functions of fs state + Request shape.)

import { resolveProjectFromRequest, listProjects } from "../src/lib/projects.ts";

test("resolveProjectFromRequest priority: query > form > referer > __root__", () => {
  // 1. query wins over form
  {
    const req = new Request("http://x/api?project=alpha", { method: "POST" });
    const fd = new FormData();
    fd.set("project", "beta");
    const p = resolveProjectFromRequest(req, fd);
    assert.equal(p?.slug, "alpha");
  }
  // 2. form wins over referer
  {
    const req = new Request("http://x/api", {
      method: "POST",
      headers: { Referer: "http://x/app?project=charlie" },
    });
    const fd = new FormData();
    fd.set("project", "beta");
    const p = resolveProjectFromRequest(req, fd);
    assert.equal(p?.slug, "beta");
  }
  // 3. referer wins over __root__
  {
    const req = new Request("http://x/api", {
      method: "POST",
      headers: { Referer: "http://x/app?project=charlie" },
    });
    const p = resolveProjectFromRequest(req);
    assert.equal(p?.slug, "charlie");
  }
  // 4. __root__ when nothing
  {
    const req = new Request("http://x/api", { method: "POST" });
    const p = resolveProjectFromRequest(req);
    assert.equal(p?.slug, "__root__");
  }
});

test("listProjects dedups by slug, brief wins", () => {
  // Live test against the actual repo state — this works because Phase 1
  // does not migrate the dogfood split. After Phase 2, this test still
  // passes (no duplicates → dedup is a no-op).
  const all = listProjects();
  const slugs = new Set();
  for (const p of all) {
    assert.ok(!slugs.has(p.slug),
      `Duplicate slug ${p.slug} in listProjects output`);
    slugs.add(p.slug);
  }
  // If the dogfood split still exists, the brief should win.
  const dogfood = all.find((p) => p.slug === "dogfood-glp1-weight-regain");
  if (dogfood) {
    assert.ok(dogfood.isBrief,
      `Expected dogfood slug to resolve to brief; got non-brief ${dogfood.path}`);
  }
});
```

**Read first**: `tests/parser-phase3.test.mjs` for the existing test
shape (uses node:test + node:assert/strict, same conventions).

**Acceptance**:
- `npm test` runs the new file and reports 2/2 PASS.
- The first test exercises all 4 resolution priorities.
- The second test asserts brief wins for the dogfood split.

## Verification checklist

- [ ] `node /tmp/dedup-verify.mjs` reports 0 duplicate slugs after listProjects fix
  (this verifies the runtime behavior, since the test file imports a TS module
  that may not run directly via node:test without compilation)
- [ ] `npm test` clean (existing 16 + new 2 tests = 18 PASS)
- [ ] `npm run typecheck` clean
- [ ] `npm run build` clean
- [ ] `grep '__root__"' src/app/api/**/route.ts` returns 0 matches
- [ ] Manual smoke: start dev server, `curl http://localhost:8769/api/lit/library`
  returns 404 (no project) WITH a `[projects]` warning in the dev server log
- [ ] Manual smoke: `curl 'http://localhost:8769/api/lit/library?project=dogfood-glp1-weight-regain'`
  returns 200 with the brief's papers (not the non-brief tree's).

## Commit message

```
dashboard: Phase 1 (fix-sprint) — project resolution helper + listProjects dedup

- New resolveProjectFromRequest(request, formData?) helper with priority:
  query string → form body → referer → __root__ (soft default with warn)
- listProjects() now dedups by slug; brief wins when both shapes exist
  (closes critic finding C1: resolveProject was returning non-brief for
  dogfood-glp1-weight-regain because the brief was added second to the
  list and find() returned the first match)
- 25 API routes converted to use the helper (closes finding #12 / #17)
- New tests/route-project-resolution.test.mjs (2 tests, both pass)
- __root__ stays soft (logs warning, doesn't 400) — strict mode is a
  Phase 9 ship-gate decision, not Phase 1 (closes critic finding C4)

Phase 0.5 verification confirmed the duplicate-slug bug exists today
(see /tmp/dedup-verify.mjs output in PHASE_FIXSPRINT_01_PLAN.md).
```
