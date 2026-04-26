# Scientific Illustration Styles

Prompt templates for scientific illustrations via Gemini. Each sub-style is a set of prompt instructions that produce consistent, publication-appropriate visuals.

## General Scientific Principles

All scientific illustrations should:
- Use clean, labeled elements (no ambiguous symbols)
- Include a white or light background (journal-friendly)
- Use consistent color coding (blues for processes, reds for inhibition, greens for activation)
- Avoid unnecessary decorative elements
- Include clear directional arrows where applicable
- Use legible sans-serif labels (Arial/Helvetica convention)

---

## Experimental Setup

**When:** Lab equipment, experimental protocols, instrument layouts, sample preparation steps

**Prompt template:**
```
Create a clean scientific illustration showing {USER_CONTENT}. Style: technical diagram on white background. Show equipment and components as simplified but recognizable illustrations with labeled parts. Use thin black outlines, subtle color fills (light blue for liquids, light gray for equipment, light green for biological samples). Include directional arrows showing the workflow flow from left to right. All labels in sans-serif font. Publication-quality, suitable for a methods section figure.
```

**Key characteristics:**
- Left-to-right workflow flow
- Simplified but recognizable equipment
- Thin black outlines with subtle color fills
- Labels on every component
- Suitable for methods section figures

---

## Biological Pathway

**When:** Signaling cascades, metabolic pathways, gene regulation, immune response pathways

**Prompt template:**
```
Create a scientific pathway diagram showing {USER_CONTENT}. Style: clean biomedical illustration on white background. Represent proteins/molecules as labeled rounded rectangles or circles. Use arrow types: solid arrows for activation/conversion, flat-head arrows (--|) for inhibition, dashed arrows for indirect effects. Color coding: blue for kinases, green for receptors, red for transcription factors, yellow for second messengers. Group related components in light-shaded boxes. All labels in clear sans-serif font. Publication-quality, suitable for a review article figure.
```

**Key characteristics:**
- Rounded rectangles/circles for molecules
- Three arrow types: solid (activation), flat-head (inhibition), dashed (indirect)
- Consistent color coding by molecule type
- Light-shaded grouping boxes
- Suitable for review articles

---

## Cell Diagram

**When:** Cell cross-sections, organelle structure, membrane transport, cellular processes

**Prompt template:**
```
Create a scientific cell biology illustration showing {USER_CONTENT}. Style: textbook-quality cross-section on white background. Show cell membrane as a phospholipid bilayer where relevant. Organelles as simplified but anatomically recognizable shapes. Use consistent color coding: blue for nucleus, green for mitochondria, purple for ER, yellow for Golgi. Include labeled callout lines. Scale bar if applicable. Publication-quality, suitable for a cell biology figure.
```

**Key characteristics:**
- Phospholipid bilayer membrane rendering
- Anatomically recognizable organelle shapes
- Consistent organelle color coding
- Labeled callout lines
- Scale bar when applicable

---

## Molecular Mechanism

**When:** Protein-protein interactions, enzyme mechanisms, drug binding, receptor activation

**Prompt template:**
```
Create a scientific molecular illustration showing {USER_CONTENT}. Style: schematic molecular diagram on white background. Represent molecules as simplified 3D shapes or ribbon diagrams. Show binding events with lock-and-key or induced-fit style. Use arrows for conformational changes or reaction steps. Color coding: blue for protein A, orange for protein B, red for small molecules/ligands. Include step numbers for sequential processes. Labels in sans-serif font. Publication-quality.
```

**Key characteristics:**
- Simplified 3D shapes or ribbon diagrams
- Lock-and-key or induced-fit binding representation
- Step numbers for sequential processes
- Distinct colors per interacting molecule
- Conformational change arrows

---

## Flowchart

**When:** Experimental workflows, analysis pipelines, decision trees, algorithms, research methodology

**Prompt template:**
```
Create a scientific flowchart showing {USER_CONTENT}. Style: clean process diagram on white background. Use standard shapes: rounded rectangles for processes, diamonds for decisions, parallelograms for inputs/outputs, rectangles for data. Connect with straight arrows (no curved connectors). Color coding: light blue for processing steps, light green for start/end, light yellow for decisions, light gray for data. Left-to-right or top-to-bottom flow. All text in sans-serif font. Publication-quality.
```

**Key characteristics:**
- Standard flowchart shapes (rounded rect, diamond, parallelogram)
- Straight arrow connectors
- Color-coded by element type
- Left-to-right or top-to-bottom flow
- Suitable for methods or supplementary figures

---

## Conceptual Figure

**When:** Abstract concepts, theoretical frameworks, model overviews, review article summary figures

**Prompt template:**
```
Create a scientific conceptual figure illustrating {USER_CONTENT}. Style: clean abstract illustration on white background. Use geometric shapes, icons, and spatial relationships to represent concepts. Minimize text — let visual hierarchy convey relationships. Use a restrained color palette (3-4 colors max). Include directional elements (arrows, gradients) to show relationships and flow. Balance between visual appeal and scientific accuracy. Publication-quality, suitable for a graphical abstract or review figure.
```

**Key characteristics:**
- Geometric shapes and icons for abstract concepts
- Minimal text, visual hierarchy emphasis
- Restrained color palette (3-4 colors)
- Directional elements for relationships
- Suitable for graphical abstracts

---

## Biomedical-Specific Sub-Styles

### Anatomical Diagram

**When:** Organ systems, tissue cross-sections, surgical approaches, anatomical landmarks

**Prompt template:**
```
Create a clean anatomical illustration showing {USER_CONTENT}. Style: medical illustration on white background with labeled structures. Use standard anatomical color conventions. Include cross-section views where helpful. Labels with leader lines, sans-serif font. Publication-quality.
```

### Statistical Result Visualization

**When:** Key statistical findings as visual elements, effect size displays, significance annotations

**Prompt template:**
```
Create a scientific figure showing {USER_CONTENT}. Style: data presentation graphic on white background. Show key statistical results as annotated visual elements (significance bars, effect size indicators). Use APA-style formatting conventions. Publication-quality.
```

---

## Prompt Construction Tips for Scientific Illustrations

When combining a sub-style template with the user's content:

1. **Replace `{USER_CONTENT}`** with a detailed description of the specific scientific content
2. **Be precise about biology** — name specific proteins, pathways, or structures rather than using generic terms
3. **Specify the audience** — "for a Nature paper" vs "for a teaching slide" changes the detail level
4. **Include scale context** — molecular, cellular, tissue, or organ level
5. **Name the key message** — what should a reader understand at a glance?
6. **Reference style preferences** — check `context/learnings.md` -> `## viz-nano-banana` for any previously logged scientist preferences before constructing the prompt
