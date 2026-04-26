# Styling Guide

Themes, color palettes, layout tips, and advanced styling for Mermaid diagrams.

---

## Theme Selection

| Theme | Best for | Look |
|-------|----------|------|
| `neutral` | Scientific papers, formal tutorials | Clean, muted colors |
| `default` | Blog posts, general content | Bright, accessible |
| `forest` | Biology, environmental science | Green-heavy, natural |
| `dark` | Presentations, dark-mode content | Dark background |

Set theme at the top of any .mmd file:
```
%%{init: {'theme': 'neutral'}}%%
```

Override specific theme variables for fine control:
```
%%{init: {'theme': 'neutral', 'themeVariables': {'primaryColor': '#4472C4', 'edgeLabelBackground': '#fff'}}}%%
```

---

## Color Palettes for Science

### Pastel scientific palette (default recommendation)

Soft colors that print well in both color and grayscale. Good contrast with
dark text and borders.

```
classDef input fill:#f9d5e5,stroke:#333,color:#333
classDef process fill:#d5e8f9,stroke:#333,color:#333
classDef output fill:#e8f5e9,stroke:#333,color:#333
classDef highlight fill:#fff3cd,stroke:#333,color:#333
classDef error fill:#f8d7da,stroke:#333,color:#333
classDef neutral fill:#f5f5f5,stroke:#333,color:#333
```

### Publication palette (matches common journal styles)

Bold colors for presentations and journal figures. White text on dark
backgrounds — high contrast.

```
classDef primary fill:#4472C4,stroke:#2F5496,color:#fff
classDef secondary fill:#ED7D31,stroke:#C55A11,color:#fff
classDef tertiary fill:#A5A5A5,stroke:#7B7B7B,color:#fff
classDef accent fill:#FFC000,stroke:#BF9000,color:#333
classDef success fill:#70AD47,stroke:#548235,color:#fff
classDef danger fill:#FF0000,stroke:#C00000,color:#fff
```

### Biology / life sciences palette

Organic colors suited for biological diagrams.

```
classDef dna fill:#8ecae6,stroke:#219ebc,color:#333
classDef protein fill:#ffb703,stroke:#fb8500,color:#333
classDef cell fill:#a8dadc,stroke:#457b9d,color:#333
classDef tissue fill:#e9c46a,stroke:#f4a261,color:#333
classDef organism fill:#2a9d8f,stroke:#264653,color:#fff
```

### Monochrome palette (for papers with no-color requirements)

```
classDef dark fill:#333,stroke:#000,color:#fff
classDef medium fill:#999,stroke:#666,color:#fff
classDef light fill:#ddd,stroke:#999,color:#333
classDef white fill:#fff,stroke:#333,color:#333
```

---

## Layout Tips

### Direction choices

- **TB** (top-bottom) — pipelines, sequential processes, hierarchies
- **LR** (left-right) — timelines, comparisons, cause-effect chains
- **BT** (bottom-top) — rarely used, but good for "building up" metaphors
- **RL** (right-left) — rarely used

### Grouping with subgraphs

Subgraphs create visual groups. Use them to:
- Show system layers (frontend / backend / storage)
- Group experiment phases
- Create side-by-side comparisons

```
subgraph "Group Title"
    direction TB
    A --> B --> C
end
```

Adding `direction TB` inside a subgraph overrides the parent direction —
useful for LR layouts where you want vertical flow within each group.

### Keep text short

- Node labels: under 25 characters
- Use `<br/>` for line breaks in long labels
- Move details to notes or annotations outside the diagram
- Example: `A[Feature<br/>Extraction]` instead of `A[Extract Features from Raw Data]`

### Connecting tips

- Use `&` to fan-in or fan-out: `A & B --> C`
- Avoid crossing arrows — rearrange node order if lines cross
- Use invisible nodes for spacing: `X[ ] ~~~ Y` (tilde links are invisible)

---

## Text Formatting in Nodes

| Need | Syntax | Example |
|------|--------|---------|
| Line break | `<br/>` | `A[Line 1<br/>Line 2]` |
| Emphasis | ALL CAPS | `A[IMPORTANT STEP]` |
| Icons | Unicode chars | `A[Pass &#10003;]` or `A[Fail &#10007;]` |
| Arrows in text | Unicode | `A[Input &#10230; Output]` |
| Subscript/super | Not supported | Use `<br/>` with smaller context |

Common Unicode for scientific diagrams:
- Check mark: &#10003; (use in source as the character directly)
- Cross mark: &#10007;
- Right arrow: &#10230;
- Plus-circle: &#10753;
- Alpha/Beta/Gamma: use the Greek letters directly in UTF-8

---

## Custom CSS for Advanced Styling

Create a .css file alongside your .mmd file for advanced control.
The render script auto-detects and applies it.

Example `diagram.css`:
```css
/* Custom font */
.node rect, .node circle, .node polygon {
    rx: 8px;
    ry: 8px;
}

/* Softer edges */
.edgePath path {
    stroke-width: 2px;
}

/* Subgraph titles */
.cluster-label {
    font-weight: bold;
    font-size: 14px;
}

/* Arrow labels */
.edgeLabel {
    font-size: 12px;
    background-color: white;
    padding: 2px 4px;
}
```

Save as `{diagram-name}.css` next to the `.mmd` file. The render script
picks it up automatically via `--cssFile`.

---

## Render Quality Tips

- SVG is always preferred for web — scales to any size
- PNG is rendered at 2x scale (via `-s 2` flag) for retina clarity
- Use `transparent` background for SVG (composites well) and `white` for PNG
- For dark-theme diagrams, switch PNG background to match: edit render script or use custom CSS
