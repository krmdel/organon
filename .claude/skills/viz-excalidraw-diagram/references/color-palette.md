# Color Palette & Brand Style

**This is the single source of truth for all colors and brand-specific styles.** To customize diagrams for your own brand, edit this file — everything else in the skill is universal.

Style: Warm PaperBanana editorial — hand-drawn feel, warm cream background, playful but professional.

---

## Shape Colors (Semantic)

Colors encode meaning, not decoration. Each semantic purpose has a fill/stroke pair. All shapes use dark charcoal ink outlines for that hand-drawn editorial feel.

| Semantic Purpose | Fill | Stroke |
|------------------|------|--------|
| Primary/Neutral | `#EF6351` | `#2D2D2D` |
| Secondary | `#4BA3D4` | `#2D2D2D` |
| Tertiary | `#6BBF6A` | `#2D2D2D` |
| Start/Trigger | `#F4C542` | `#2D2D2D` |
| End/Success | `#6BBF6A` | `#2D2D2D` |
| Warning/Reset | `#EF6351` | `#2D2D2D` |
| Decision | `#F4C542` | `#2D2D2D` |
| AI/LLM | `#9B7ED8` | `#2D2D2D` |
| Inactive/Disabled | `#F2918C` | `#2D2D2D` (use dashed stroke) |
| Error | `#EF6351` | `#2D2D2D` |
| Highlight/Accent | `#9B7ED8` | `#2D2D2D` |
| Soft/Gentle | `#F2918C` | `#2D2D2D` |

**Named palette:**

| Role | Hex | Usage |
|------|-----|-------|
| Background | `#FDF6E3` | Warm cream canvas |
| Ink/outlines | `#2D2D2D` | All strokes, text outlines |
| Coral red | `#EF6351` | Primary elements, warnings |
| Sky blue | `#4BA3D4` | Secondary elements, arrows |
| Soft green | `#6BBF6A` | Success, growth, tertiary |
| Golden yellow | `#F4C542` | Highlights, triggers, decisions |
| Lavender | `#9B7ED8` | Special callouts, AI/LLM |
| Salmon pink | `#F2918C` | Gentle emphasis, inactive |
| White | `#FFFFFF` | Badge text on colored fills |

**Rule**: All shapes use `#2D2D2D` (dark charcoal) stroke. Use color on fills to differentiate. Roughness: 1 for hand-drawn feel.

---

## Text Colors (Hierarchy)

Use color on free-floating text to create visual hierarchy without containers.

| Level | Color | Use For |
|-------|-------|---------|
| Title | `#2D2D2D` | Section headings, major labels |
| Subtitle | `#EF6351` | Subheadings, secondary labels |
| Body/Detail | `#2D2D2D` | Descriptions, annotations, metadata |
| On light fills | `#2D2D2D` | Text inside light-colored shapes |
| On dark fills | `#ffffff` | Text inside dark-colored shapes |

---

## Evidence Artifact Colors

Used for code snippets, data examples, and other concrete evidence inside technical diagrams.

| Artifact | Background | Text Color |
|----------|-----------|------------|
| Code snippet | `#2D2D2D` | `#F4C542` (golden) |
| JSON/data example | `#2D2D2D` | `#6BBF6A` (green) |

---

## Default Stroke & Line Colors

| Element | Color |
|---------|-------|
| Arrows | `#2D2D2D` (charcoal ink) |
| Structural lines (dividers, trees, timelines) | `#2D2D2D` |
| Marker dots (fill + stroke) | Fill: `#EF6351`, Stroke: `#2D2D2D` |

---

## Background

| Property | Value |
|----------|-------|
| Canvas background | `#FDF6E3` |

---

## Style Notes

- `roughness: 1` on all shapes for hand-drawn quality
- `strokeWidth: 2` for bold charcoal outlines
- `fontFamily: 3` (monospace) for labels — feels like handwritten notes
- Organic, slightly imperfect feel — this is editorial illustration, not engineering blueprint
