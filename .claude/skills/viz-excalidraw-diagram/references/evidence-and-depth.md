# Evidence Artifacts and Depth Layers

How to build comprehensive, educational diagrams that teach — not just label.

---

## Depth Assessment

Every diagram sits somewhere on a spectrum. Get the level right before designing.

### Simple / Conceptual

Abstract shapes, labels, relationships. The right choice when:
- Explaining a mental model or philosophy
- The audience already knows the technical details
- The concept *is* the abstraction (e.g. separation of concerns, feedback loops)

These diagrams are quicker to build and easier to scan. Don't add technical depth that doesn't serve the purpose.

### Comprehensive / Technical

Concrete examples, real data, actual names from the spec. The right choice when:
- Diagramming a real system, protocol, or architecture
- The diagram will be used to teach (video, blog post, documentation)
- The audience needs to see what things actually look like, not just what they're called
- Multiple technologies integrate and the connections matter

Comprehensive diagrams take longer but deliver more lasting value. They require evidence artifacts (below) and usually benefit from multi-zoom layering.

---

## Evidence Artifacts

Concrete examples embedded in the diagram that prove accuracy and help viewers learn. Choose whichever types are relevant to the subject:

| Type | When to use | How to render |
|------|-------------|---------------|
| Code snippets | APIs, integrations, implementation detail | Dark rectangle + syntax-coloured text (see color-palette.md) |
| Data / JSON samples | Data formats, schemas, payloads | Dark rectangle + coloured text |
| Event sequences | Protocols, workflows, lifecycles | Timeline pattern (line + dots + labels) |
| UI mockups | Showing actual output or results | Nested rectangles mimicking the real interface |
| Sample input content | Showing what enters a system | Rectangle with visible sample content |
| Real API / method names | Function calls, endpoints | Use the actual names from documentation |

The principle: **show what things look like**, not just what they're called. A box labelled "API Response" teaches nothing. A dark rectangle containing `{ "status": "ok", "events": [...] }` teaches the shape of the data.

---

## Multi-Zoom Architecture

Comprehensive diagrams work at multiple levels simultaneously — like a map that shows both country borders and street names.

### Level 1: Summary Flow

A simplified overview showing the full pipeline or process at a glance. Often placed at the top or as a visual spine through the diagram.

Think: `Input -> Processing -> Output` or `Client -> Server -> Database` — the 10-second understanding.

### Level 2: Section Boundaries

Labelled regions that group related components. These create visual "rooms" that help viewers understand what belongs together.

Group by responsibility (Backend / Frontend), by phase (Setup / Execution / Cleanup), by team, or by whatever boundary is most meaningful to the subject.

### Level 3: Detail Inside Sections

Evidence artifacts, code snippets, and concrete examples within each section. This is where the educational value lives. Inside a "Backend" section, show the actual API response format — not just a box labelled "API Response".

**For comprehensive diagrams, aim to include all three levels.** The summary gives context, the sections organise, and the details teach.

---

## Simple vs Comprehensive — Quick Reference

| Simple | Comprehensive |
|--------|---------------|
| Generic labels: "Input", "Process", "Output" | Shows what input/output actually looks like |
| Named boxes: "API", "Database", "Client" | Named boxes + real request/response examples |
| "Events" or "Messages" label | Timeline with actual event names from the spec |
| "UI" or "Dashboard" rectangle | Mockup showing real UI elements |
| ~30 seconds to explain | ~2-3 minutes of educational content |
| Viewer learns the structure | Viewer learns the structure *and* the details |

Simple diagrams are fine for abstract concepts and quick overviews. Comprehensive diagrams are needed for technical architectures, tutorials, and educational content where the diagram itself should teach.
