# Layout Patterns

Choose a layout based on how the concept behaves, not what it is. The layout should make the argument visible before anyone reads the labels.

---

## Flow / Pipeline

Left-to-right or top-to-bottom sequence of steps.

```
[Input] ---> [Process 1] ---> [Process 2] ---> [Output]
```

**Best for:** architectures, pipelines, workflows, build processes, timelines
**Prompt hint:** "Show as a left-to-right flow with arrows connecting each stage"
**Optional:** loop arrows returning from later to earlier stages for iterative processes

---

## Fan-Out / Divergence

One source element with multiple outputs branching away.

```
              /--> [Option A]
[Source] ----/--> [Option B]
              \--> [Option C]
```

**Best for:** framework comparisons, decision trees, one-to-many relationships
**Prompt hint:** "Central element with radiating arrows to multiple outcomes, each in a different color"

---

## Convergence / Funnel

Multiple inputs flowing into one output.

```
[Input A] --\
[Input B] ---\---> [Result]
[Input C] --/
```

**Best for:** aggregation, synthesis, merging concepts, "best of" summaries
**Prompt hint:** "Multiple inputs funneling into a single result at the center-right"

---

## Panel Grid

Multiple independent scenes in a grid layout.

```
[Scene 1] | [Scene 2]
----------|----------
[Scene 3] | [Scene 4]
```

**Best for:** use cases, pattern categories, comparison of scenarios, step sequences
**Prompt hint:** "2x2 grid (or 1x3, 2x3) with each panel showing a different scenario"
**Note:** each panel gets its own mini-illustration with a connecting theme

---

## Central Hub

One dominant central element with satellites around it.

```
        [A]
         |
  [B] -- [HUB] -- [C]
         |
        [D]
```

**Best for:** ecosystem diagrams, feature maps, stakeholder views, technology stacks
**Prompt hint:** "Large central element surrounded by smaller connected elements"

---

## Before / After

Two-panel comparison with a transformation in between.

```
[Before State] ==transform==> [After State]
```

**Best for:** improvement stories, refactoring, migration narratives, problem/solution
**Prompt hint:** "Split into two halves — left shows the problem, right shows the solution, with a transformation arrow between"

---

## Choosing the Right Layout

| If the concept... | Use |
|-------------------|-----|
| Has sequential steps | Flow/Pipeline |
| Produces multiple outputs | Fan-Out |
| Combines multiple inputs | Convergence |
| Compares independent items | Panel Grid |
| Has a central thing with satellites | Central Hub |
| Shows transformation | Before/After |

For multi-concept visuals, combine patterns — e.g., a hub at the center with a flow coming in from the left.
