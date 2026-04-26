# Template Catalog

Templates in `templates/` are reusable Marp frontmatter fragments. Each template defines **both** a visual system (palette, typography, decorative elements) AND a set of layout archetypes (title vs content vs stats vs quote vs closing) that map to markdown via `<!-- _class: NAME -->` directives.

## Layout

```
templates/
├── catalog.json              # registry: id, name, description, best_for, tags
├── _sample-body.md           # generic fallback preview body (4 slides)
├── default.md                # template frontmatter (CSS only)
├── default.sample.md         # OPTIONAL per-template preview body
├── gaia.md
├── uncover.md
├── dark-academia.md
├── mindmaps-boost.md
├── mindmaps-boost.sample.md  # showcases .lead / .stats / .quote / .closing layouts
└── (user-added).md + (user-added).sample.md
```

**Naming rules:**
- `{id}.md` → frontmatter fragment (CSS + theme)
- `{id}.sample.md` → per-template preview body (OPTIONAL). If present, `preview_themes.sh` uses it; otherwise falls back to the shared `_sample-body.md`.
- Files prefixed with `_` are not rendered as templates — they're shared assets.

**Why the `.sample.md` matters:** a minimalist template should *show* massive whitespace + 1 idea/slide. A dashboard template should *show* a packed stats grid. A branded template should *show* corner graphics. If every template uses the same 4-slide generic body, differences are invisible — only color/font changes. The sample file is where layout variety becomes visible.

## Helper scripts

- `scripts/preview_themes.sh` — renders every `{id}.md` with its `{id}.sample.md` (or shared fallback), builds a gallery, serves it.
- `scripts/apply_template.sh <id> <deck.md>` — swaps the frontmatter of an existing deck with the named template, re-renders PDF/PPTX/HTML.
- `scripts/serve_preview.sh <dir>` — starts (or reuses) a local HTTP server. Auto-picks a free port in 8765-8785.

## Learning a new template from a reference

When the user supplies a reference (screenshot, URL, or description), follow this 6-step procedure.

### Step 1: Read the reference — extract *both* visual system AND layout archetypes

Use the `Read` tool on the screenshot file. If the reference is a URL, capture a screenshot via `/tmp/fc-screenshot.py {url} {out.png}` (the Firecrawl helper writes to disk so Claude's vision can see it) — fall back to asking the user to paste a screenshot if that fails.

**Extract two layers. Do not skip the second — this is where most templates fall flat.**

**Layer 1: Visual system**
- **Background**: solid color (hex), gradient (direction + stops), or texture
- **Primary text color**: body copy
- **Accent color(s)**: 1-2 colors used for headings / bold / key numbers
- **Font family**: serif vs sans-serif vs mono. Name a likely font — Inter, Bricolage Grotesque, IBM Plex, Georgia, Satoshi, etc. If the reference uses a proprietary face, pick the closest open-source match.
- **Font weights present**: often 3 weights — body (400), heading (700-900), italic accent (300-400)
- **Decorative elements**: corner blobs, background shapes, rules, page-number styling, header bands, icons, illustrations — **report what you see and where (top-right, bottom-left, full-bleed, etc.)**

**Layer 2: Layout archetypes**

For each distinct slide type in the reference, note:

| Slide type | Observables to capture |
|---|---|
| **Title / lead** | Title position (centered / bottom-left / top-center / overlay on image)? Title size (approximate px)? Subtitle treatment? Any top-right annotation ("presentation begins here", date, slide N/N)? |
| **Content** | Heading position (top-left / top-center)? Bullets or paragraphs? Single column or split? Density? |
| **Stats / data** | Grid? 3-up? Big numbers with small labels? Number color vs body color? |
| **Quote** | Centered? Left border? Attribution placement? Italic? |
| **Figure-dominant** | Image position (center / right-half / full-bleed)? Caption treatment? |
| **Section break** | Big single-word / phrase? Negative space? Decoration contrast? |
| **Closing** | "Thank you"? Repeat of title style? Contact info placement? |

If the reference only shows one slide type, ask the user whether other archetypes exist or if the template is single-layout only.

### Step 2: Name + classify

Ask the user (batched in one message):
- **id** — short kebab-case identifier
- **description** — one sentence
- **best_for** — audience / use case

### Step 3: Write `templates/{id}.md` with named layout classes

Use this scaffold. **Every layout archetype you observed becomes a `section.CLASS` rule.** Do not dump everything into generic `section`.

```markdown
---
marp: true
theme: default            # or: gaia, uncover
paginate: true
math: katex
style: |
  /* =========================================================================
     {Template Name} — {one-line description}
     Layouts: lead, content (default), stats, quote, figure, closing
     Decorative: {list any corner blobs, background shapes, etc.}
     ========================================================================= */

  /* Font loading — @import goes at top of style */
  @import url('https://fonts.googleapis.com/css2?family={font}&display=swap');

  /* Base slide (the default "content" archetype) */
  section {
    background: {fill};
    color: {primary-text};
    font-family: '{font}', -apple-system, sans-serif;
    font-size: 26px;
    padding: {v}px {h}px;
    position: relative;      /* enables absolute positioning for decorations */
    overflow: hidden;        /* decorative blobs stay in-slide */
  }

  /* Decorative elements via pseudo-elements (if reference has corner shapes) */
  section::before {
    content: '';
    position: absolute;
    width: {size}px; height: {size}px;
    top: {top}px; right: {right}px;
    background: radial-gradient(circle at center, {color1} 0%, transparent 70%);
    border-radius: 50%;
    z-index: 0;
    pointer-events: none;
  }
  section > * { position: relative; z-index: 1; }   /* keep content above blobs */

  /* Typography */
  h1, h2 { color: {accent-1}; margin-top: 0; letter-spacing: -0.02em; }
  h1 { font-size: {title-size}px; font-weight: 900; line-height: 1.0; }
  h2 { font-size: {heading-size}px; font-weight: 800; }
  strong { color: {accent-2}; }
  em { color: {muted}; font-style: italic; }

  /* --- Layout archetypes --- */

  /* Lead (title) — adjust to match reference: bottom-left / centered / etc. */
  section.lead {
    padding: 0;
    display: flex;
    flex-direction: column;
    justify-content: {flex-end | center | flex-start};
  }
  section.lead h1 { font-size: {lead-title-size}px; padding: 0 80px 60px 80px; }
  section.lead h2 {
    /* If reference has a top-right italic annotation, position absolutely: */
    position: absolute; top: 70px; right: 80px;
    font-size: 20px; font-style: italic; color: {muted};
    text-align: right; max-width: 320px;
  }

  /* Stats — 3-up grid with big colored numbers */
  section.stats .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 40px; }
  section.stats .stat-num { font-size: 88px; font-weight: 900; color: {accent-2}; line-height: 1; }
  section.stats .stat-label { font-size: 16px; color: {muted}; }

  /* Quote — centered pull quote */
  section.quote { display: flex; align-items: center; justify-content: center; }
  section.quote blockquote {
    border-left: 6px solid {accent-2};
    padding: 20px 40px;
    font-size: 44px; font-weight: 500; line-height: 1.2; max-width: 900px;
  }

  /* Closing — mirror of lead or distinct "thank you" layout */
  section.closing { /* ... */ }

  /* Tables + images + code (keep safety net) */
  table { border-collapse: collapse; margin: 0 auto; }
  th { background: {accent-2}; color: {fill}; padding: 12px 20px; }
  td { padding: 10px 20px; border-bottom: 1px solid {faint}; }
  img[alt~="center"] { display: block; margin: 0 auto; }
  section img { max-height: 470px; max-width: 100%; object-fit: contain; }
  footer { color: {muted}; font-size: 14px; }
---
```

**CSS rules for robustness:**
- **Always keep `section img { max-height: 470px; object-fit: contain }`** — prevents figure overflow.
- **Always set `position: relative` + `overflow: hidden` on `section`** when using `::before`/`::after` blobs.
- **Always wrap content with `section > * { position: relative; z-index: 1 }`** so decorations stay behind text.
- **Never hard-code body font below 22px** — unreadable in PDF export.
- **Avoid `background-image: url(remote)`** without `@import url(...)` — offline PDF export fails silently.

### Step 4: Write `templates/{id}.sample.md`

**This is the step most skills skip — don't.** The sample body exercises every layout class the template defines. Without it, the gallery preview will look identical to every other template (same 4 slides of the generic `_sample-body.md`).

Structure:

```markdown

<!-- _class: lead -->

## {Optional top-right italic label, e.g. "Here is where your presentation begins"}

# {Template Showcase Title}

> {Optional author line via blockquote}

---

## {A content slide that looks the way this template's content slides want to look}

Body prose that fits the template's density. **Bold** and *italic* used naturally.

*Template-specific caption or emphasis*

---

<!-- _class: stats -->

## {Stats slide heading, if template has stats layout}

<div class="stats-grid">
  <div>
    <div class="stat-num">{big number}</div>
    <div class="stat-label">{small description}</div>
  </div>
  <!-- ×3 -->
</div>

---

<!-- _class: quote -->

> {A real or illustrative quote that fits the template's voice}
>
> — {Attribution}

---

{Table slide exercising the th/td styling, or a figure slide, or both}

---

<!-- _class: closing -->

## {Closing label}

# {Closing headline that mirrors the lead}
```

Include ONLY the layout classes the template defines. If the template has no `stats` class, skip the stats slide. If it has no `closing`, use `lead` styling for the final slide.

### Step 5: Register in `catalog.json`

Append:

```json
{
  "id": "{id}",
  "name": "{Human Readable Name}",
  "description": "{one sentence}",
  "best_for": "{audience / use case}",
  "base_theme": "default",
  "tags": ["{tag1}", "{tag2}"]
}
```

### Step 6: Preview + confirm

Run `bash scripts/preview_themes.sh` — the new template appears in the gallery rendered against its own `{id}.sample.md`, so layout differences are immediately visible.

Open the gallery in Chrome. Compare to the reference. If visual intent doesn't match, iterate:
- Palette wrong? Adjust hex values in `{id}.md`
- Layout wrong? Adjust `section.CLASS` rules OR update `{id}.sample.md` to use different class names
- Decorative element missing? Add `::before`/`::after` blobs

Ask: *"Does this match the style? Want to adopt it for the current deck, or keep refining?"*

If adopted → `apply_template.sh {id} {deck.md}` on the active deck.

## Extraction heuristics by reference type

| Reference type | Likely layout archetypes |
|---|---|
| **Academic IEEE/ACM template** | `lead`, `content` (left-aligned, dense), `figure`, `closing` — single accent, serif body |
| **VC pitch deck** | `lead` (bold centered), `stats` (3-up), `quote` (customer), `closing` — 2 strong accents, massive whitespace |
| **Product demo** | `lead` (dark hero), `content` (code-heavy), `figure` (screenshot), `closing` — mono font, bright accent |
| **Lecture / educational** | `lead`, `content` (large type), `figure`, `quote` (key takeaway) — lots of whitespace, minimal color |
| **Editorial / SlidesGo-style** | `lead` (bottom-left anchor + top-right italic), decorative blobs, `stats`, `quote`, `closing` (mirror of lead) — warm palette, display typeface |
| **Poster / research summary** | Dense single-slide with multi-column — often skip archetypes entirely |
| **Dashboard / analytics** | `stats` dominant, `content` with embedded charts, minimal `lead` — neutral palette |
