# Visual Patterns and Layout

How to choose shapes, structure diagrams, and make the layout do the thinking.

---

## Pattern Library

Pick the pattern that mirrors how the concept actually behaves. If a concept spawns multiple outputs, it gets a fan-out — not a labelled box.

| Concept behaviour | Pattern | Shape |
|-------------------|---------|-------|
| Produces multiple outputs | **Fan-out** — central node with arrows radiating outward | Radial from centre |
| Combines inputs into one | **Convergence** — multiple arrows funnelling to a single target | Funnel or merge point |
| Has parent-child structure | **Tree** — trunk lines + branch lines + free-floating labels | Lines, not boxes |
| Happens in sequence | **Timeline** — a spine line with small dots at intervals, labels beside each | Line + dots + text |
| Repeats or improves | **Cycle** — elements in sequence with an arrow returning to the start | Loop back |
| Represents fuzzy state | **Cloud** — overlapping ellipses of varied sizes | Ellipse cluster |
| Transforms input to output | **Assembly line** — before, process box, after | Linear flow |
| Compares two things | **Side-by-side** — parallel structures with visual contrast | Mirror layout |
| Separates into phases | **Gap** — deliberate whitespace or a divider between sections | Visual break |

For multi-concept diagrams, each major concept should use a **different** pattern. A diagram where every concept is a rectangle in a grid isn't arguing anything — it's just formatted text.

---

## Shape Vocabulary

Shape choice communicates what something *is* before anyone reads the label.

| Concept type | Shape | Reasoning |
|-------------|-------|-----------|
| Labels, descriptions, detail text | **None** (free-floating text) | Font size and colour create hierarchy |
| Section titles, annotations | **None** (free-floating text) | A heading doesn't need a box |
| Markers on a timeline | Small ellipse (10-20px) | Visual anchor, not a container |
| Starting point, trigger, input | Ellipse | Soft, origin-like |
| End state, output, result | Ellipse | Completion, destination |
| Decision, branch, condition | Diamond | Universal decision symbol |
| Process, action, step | Rectangle | Contained, bounded action |
| Fuzzy state, context, memory | Overlapping ellipses | Formless, cloud-like |
| Hierarchy node | Lines + text (no boxes) | Structure lives in the lines |

**Default to no container.** Add a shape only when the shape itself carries meaning. Target fewer than 30% of text elements inside containers.

---

## Container vs Free-Floating Text

Not every label needs a rectangle around it.

**Use a container when:**
- It's the focal point of a section
- Arrows need to connect to it
- It needs visual grouping with siblings
- The shape itself communicates something (diamond = decision)
- It represents a distinct entity in the system

**Use free-floating text when:**
- It's a label or description for something nearby
- It's a section title, subtitle, or annotation
- Font size and colour alone create sufficient hierarchy
- It's supporting detail or metadata

**The container test**: for each boxed element, ask "Would removing the box lose any meaning?" If not, remove it.

---

## Colour as Meaning

All colour assignments come from `color-palette.md`. Key principles:

- Each semantic purpose (start, end, decision, AI, error) has a dedicated fill/stroke pair
- Free-floating text uses colour for hierarchy — titles, subtitles, and details each at a different shade
- Evidence artifacts (code snippets, JSON) use dark backgrounds with coloured text
- Always pair a darker stroke with a lighter fill for contrast
- Don't invent new colours — if a concept doesn't fit an existing semantic category, use Primary/Neutral

---

## Layout Principles

### Hierarchy through scale

The most important element is the largest. A rough sizing guide:
- **Hero element**: ~300x150 — the visual anchor
- **Primary elements**: ~180x90
- **Secondary**: ~120x60
- **Small/supporting**: ~60x40

### Whitespace signals importance

The most important element has the most empty space around it (200px+). Crowding everything equally makes nothing stand out.

### Flow direction

Guide the eye predictably. Left-to-right or top-to-bottom for sequences. Radial for hub-and-spoke. If two things happen in order, the first one appears before the second in the reading direction.

### Connections are mandatory

Position alone doesn't communicate a relationship. If A relates to B, draw an arrow or line between them.

---

## Lines as Structural Elements

Lines (type: `line`, not arrows) are powerful as primary structure — often cleaner than boxes:

- **Timelines**: horizontal or vertical line with small dot markers at intervals, free-floating labels beside each dot
- **Trees**: vertical trunk + horizontal branches, free-floating text at each node
- **Dividers**: thin dashed lines separating sections
- **Flow spines**: a central line that elements relate to

Lines + free-floating text usually produces a cleaner diagram than boxes + contained text.

---

## Modern Aesthetics

### Roughness
- `roughness: 0` — clean, crisp edges. Default for professional/technical diagrams.
- `roughness: 1` — hand-drawn feel. Use for brainstorming or informal sketches.

### Stroke width
- `1` — thin, elegant. Good for dividers, subtle connections.
- `2` — standard. Good for shapes and primary arrows.
- `3` — bold. Use sparingly for emphasis on the main flow.

### Small markers over full shapes
Small dots (10-20px ellipses) work well as timeline markers, bullet points, connection nodes, and visual anchors for free-floating text — without the visual weight of full shapes.
