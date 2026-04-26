# SVG Construction Guide

For Mode B (SVG Blueprint) — when you need precise layout control before describing the composition to Gemini. The SVG is a planning tool, not sent to the model.

---

## ViewBox Sizing

Match the viewBox to aspect ratio:

| Aspect | ViewBox | Best for |
|--------|---------|----------|
| Wide (16:9) | `0 0 900 550` | Pipelines, flows, timelines, presentations |
| Square (1:1) | `0 0 800 800` | Social posts, hub diagrams, Instagram |
| Tall (9:16) | `0 0 500 900` | Vertical flows, mobile-first, stories |
| Standard (4:3) | `0 0 900 650` | General-purpose, balanced layouts |

Always use `style="max-width: 100%; height: auto"` for responsive scaling.

---

## Hand-Drawn Path Technique

To make paths feel sketchy, add slight control point offsets (1-3px):

**Mechanical (avoid):**
```xml
<line x1="100" y1="200" x2="400" y2="200" />
```

**Hand-drawn (prefer):**
```xml
<path d="M 100 200 Q 250 197 400 201" />
```

For rectangles, use paths with slightly wobbly corners instead of `<rect>`:
```xml
<path d="M 58 50 L 248 52 Q 252 52 252 58 L 250 148 Q 250 152 246 152 L 52 150 Q 48 150 48 146 L 50 56 Q 50 52 54 52 Z"
      stroke="#2D2D2D" stroke-width="2.5" fill="none" />
```

The key: 1-3px of imperfection — enough to read as hand-drawn, not enough to look broken.

---

## Curved Arrow Construction

```xml
<path d="M 100 300 C 200 310, 300 180, 390 200"
      stroke="#4BA3D4" stroke-width="4" fill="none" />
<polygon points="390,200 378,192 380,206" fill="#4BA3D4" />
```

Use quadratic bezier curves (`Q`) for organic feel — never straight lines between distant elements.

---

## Badge / Pill Construction

```xml
<g transform="translate(50, 100)">
  <rect width="120" height="30" rx="15" fill="#EF6351" stroke="#2D2D2D" stroke-width="1.5" />
  <text x="60" y="20" text-anchor="middle" font-size="13" font-weight="800" fill="#FFFFFF">Label</text>
</g>
```

Min width 80px, height 28-32px. Each item in a list gets a DIFFERENT accent color.

---

## Stick Figure Construction

```xml
<g transform="translate(200, 150)">
  <circle cx="0" cy="0" r="12" stroke="#2D2D2D" stroke-width="2" fill="#4BA3D4" />
  <line x1="0" y1="12" x2="0" y2="45" stroke="#2D2D2D" stroke-width="2.5" />
  <line x1="0" y1="22" x2="-18" y2="10" stroke="#2D2D2D" stroke-width="2" />
  <line x1="0" y1="22" x2="18" y2="10" stroke="#2D2D2D" stroke-width="2" />
  <line x1="0" y1="45" x2="-12" y2="65" stroke="#2D2D2D" stroke-width="2" />
  <line x1="0" y1="45" x2="12" y2="65" stroke="#2D2D2D" stroke-width="2" />
</g>
```

Color each figure differently for different stakeholders. Pose arms for expression (raised = celebration, pointing = direction).

---

## Typography

| Role | Size | Weight | Color |
|------|------|--------|-------|
| Titles | 28-36 | 900 | `#2D2D2D` |
| Subtitles | 14-16 | 600 | `#2D2D2D` opacity 0.7 |
| Body | 12-14 | 400 | `#2D2D2D` |
| Badge text | 13-15 | 800 | `#FFFFFF` |
| Caption | 10 | 400 | `#2D2D2D` opacity 0.4 |

Font stack: `'Comic Neue', 'Segoe Print', 'Patrick Hand', system-ui, sans-serif`

---

## Using the Blueprint

After building the SVG, translate it into a detailed prompt for Gemini:
1. Describe each major element's position ("top-left", "center", "bottom-right")
2. Note relative sizes ("the hub is twice as large as the satellites")
3. Specify connections ("curved arrow from A to B, dashed line from B to C")
4. Include text labels exactly as written in the SVG
5. Describe decorative elements and their placement
