# Style Templates

Each style below is a complete prompt template. When generating, combine the style prefix with the user's specific content description.

---

## technical

**Medium:** High-fidelity digital screenshots or photorealistic renders overlaid with digital marker/pen annotations.

**Prompt prefix:**
```
Create a high-fidelity digital image with realistic rendering overlaid with hand-drawn marker annotations. The core content (UI elements, dashboards, logos, technical diagrams) should be rendered with sharp, realistic edges. The annotations should be loose, gestural, "red-lining" style — circles, arrows, and handwritten notes in a single high-contrast color (red marker). Background: clean, subtle technical grid paper or very clean white digital whiteboard surface. Style: "The CTO's marked-up schematics" — an engineer explaining architecture.
```

**Key characteristics:**
- Realistic core content with sharp edges
- Annotations use a single high-contrast brand color (red pen/highlighter)
- Grid paper or white whiteboard background
- Loose, gestural annotation style — circles, arrows, handwritten notes

**EXCEPTION:** For carousel slides, this style applies ONLY to the illustration. Text on the slide must remain clean digital text.

---

## notebook

**Medium:** Realistic open notebook page with handwritten sketchnotes.

**Prompt prefix:**
```
Create a realistic, open notebook page. Convert the content into handwritten 'sketchnotes' using bullet points, highlighters, and margin doodles. Use a grid or dot-grid paper background and include a pen on the side for scale.
```

**Key characteristics:**
- Realistic notebook/paper texture
- Handwritten sketchnote style — bullet points, highlighters, margin doodles
- Grid or dot-grid paper background
- Pen placed on the side for scale

**Text rules (critical):**
- Only include text if it significantly improves clarity or impact
- Text must be minimal to increase readability
- Text must be 100% typo-free, grammatically correct, plain standard English
- Avoid special characters, symbols, or broken glyphs
- If there is any uncertainty about spelling, spacing, or rendering, omit text entirely

---

## comic

**Medium:** Black and white comic strip storyboard.

**Prompt prefix:**
```
Create a black and white comic strip storyboard. The panels should visualize the following as a sequence of events or steps. Use simple character sketches, speech bubbles, and narrative captions in a loose, hand-drawn style on white paper.
```

**Key characteristics:**
- Black and white only
- Comic strip panel layout
- Simple character sketches
- Speech bubbles and narrative captions
- Loose, hand-drawn style on white paper

**Text rules (critical):**
- Text must be minimal to increase readability
- Text must be 100% typo-free, grammatically correct, plain standard English
- Avoid special characters, symbols, broken glyphs, or uncommon fonts
- Prefer clean typography with excellent legibility
- If there is any uncertainty about spelling, spacing, or rendering, omit text entirely

---

## color

**Medium:** Hand-drawn warm illustrated infographic inspired by PaperBanana editorial style.

**Prompt prefix:**
```
Create a hand-drawn illustrated infographic with a warm, editorial magazine quality. Use a warm cream background. Color palette: coral red for primary elements, sky blue for secondary, soft green for tertiary, golden yellow for highlights, lavender purple for special callouts, salmon pink for gentle emphasis. All elements should have dark charcoal ink outlines. Include playful decorative elements scattered throughout: small stars, sparkles, confetti pieces, squiggly underlines. Text should use a handwritten/comic style font feel. All shapes should have a slightly imperfect, hand-drawn quality with organic curves rather than mechanical straight lines. The overall feel should be playful, warm, and magazine-quality — like an editorial illustration from a tech blog.
```

**Color palette:**
| Role | Hex | Usage |
|------|-----|-------|
| Background | `#FDF6E3` | Warm cream base |
| Ink/outlines | `#2D2D2D` | All strokes, text |
| Primary | `#EF6351` | Coral red — main elements |
| Secondary | `#4BA3D4` | Sky blue — arrows, secondary |
| Tertiary | `#6BBF6A` | Soft green — success, growth |
| Highlight | `#F4C542` | Golden yellow — stars, lightbulbs |
| Accent | `#9B7ED8` | Lavender purple — callouts |
| Soft | `#F2918C` | Salmon pink — gentle emphasis |
| Badge text | `#FFFFFF` | White text on colored badges |

**Key characteristics:**
- Warm cream background, never transparent
- Each list/fan item uses a different accent color
- Dark charcoal ink outlines on everything (2-3px)
- Organic curves — bezier paths with slight wobble
- Decorative elements: stars, sparkles, confetti, squiggly underlines (8-15 per diagram)
- Stick figures with colored bodies for different stakeholders
- Speech bubbles, badges/pills with rounded corners
- The final/result element gets sparkles and a glow effect

---

## mono

**Medium:** Clean black-and-white sketchy ink style.

**Prompt prefix:**
```
Create a clean black-and-white sketchy ink diagram. Use only black ink on white/transparent background — no color at all. Thick outlines (varying weight for hierarchy), dashed connectors for secondary relationships, crosshatch fills for emphasis. Generous whitespace between elements. Section labels should be uppercase and bold. Use a panel/grid composition when showing multiple related concepts. The style should feel like a well-crafted whiteboard sketch or academic paper diagram — clear information hierarchy with no color distraction.
```

**Key characteristics:**
- No color ever — black ink only
- Contrast via stroke weight (thin 1px to bold 3.5px) and opacity
- Generous whitespace — more space than color style needs
- UPPERCASE bold section labels
- Crosshatch/scribble fill for emphasis
- Panel grids for multiple concepts (2x2, 1x3, etc.)
- Dashed lines for secondary connections
- Works on both light and dark backgrounds

---

## Prompt Construction Tips

When combining a style prefix with user content:

1. **Be spatially specific** — "top-left corner shows X, center contains Y, bottom has Z"
2. **Describe visual hierarchy** — "the main concept is large and central, supporting details are smaller around it"
3. **Name relationships** — "an arrow flows from A to B", "B is contained inside C"
4. **Specify text carefully** — keep it minimal, spell-check everything, prefer labels over sentences
5. **Include the number of elements** — "3 panels", "5 branching arrows", "4 steps in sequence"
6. **Describe the story** — what should the viewer understand at a glance?
