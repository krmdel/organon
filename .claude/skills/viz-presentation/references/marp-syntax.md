# Marp Markdown Syntax Reference

Complete reference for writing Marp presentation markdown files.

## Frontmatter

Every Marp presentation starts with YAML frontmatter:

```yaml
---
marp: true
theme: default
paginate: true
math: katex
header: 'Presentation Title'
footer: 'Author Name — Conference 2026'
style: |
  section {
    font-family: 'Helvetica Neue', Arial, sans-serif;
  }
  h1 {
    color: #2d5986;
  }
---
```

Required: `marp: true`. Everything else is optional.

## Slide Separation

Use `---` on its own line to separate slides:

```markdown
# Slide 1

Content here.

---

# Slide 2

More content.
```

## Directives

Per-slide directives go in HTML comments. Underscore prefix = this slide only:

- `<!-- _class: lead -->` — centered title slide
- `<!-- _class: invert -->` — dark background emphasis slide
- `<!-- _backgroundColor: #f0f4f8 -->` — custom background color
- `<!-- _color: white -->` — text color override
- `<!-- _paginate: false -->` — hide page number (use on title slide)
- `<!-- _header: '' -->` — hide header on this slide
- `<!-- _footer: '' -->` — hide footer on this slide

Global directives (no underscore) apply to all subsequent slides:

- `<!-- class: lead -->` — all following slides use lead class
- `<!-- paginate: true -->` — enable pagination from this point

## Images

Standard markdown images with Marp size extensions:

- Standard: `![alt](path.png)`
- Width: `![w:600](path.png)`
- Height: `![h:400](path.png)`
- Both: `![w:600 h:400](path.png)`

### Background Images

- Full background: `![bg](path.png)` — fills entire slide
- Right split: `![bg right:40%](path.png)` — image on right 40%, content on left
- Left split: `![bg left:50%](path.png)` — image on left 50%, content on right
- Fit to slide: `![bg fit](path.png)` — scale to fit without cropping
- Contain: `![bg contain](path.png)` — fit within bounds
- Cover: `![bg cover](path.png)` — fill and crop if needed
- Multiple backgrounds: stack multiple `![bg]` tags for side-by-side columns

```markdown
![bg](image1.png)
![bg](image2.png)
![bg](image3.png)
```

This creates a three-column background layout.

### Background with opacity

```markdown
![bg opacity:.3](path.png)
```

## Math (KaTeX)

Requires `math: katex` in frontmatter.

- Inline: `$E = mc^2$`
- Block (centered, large):
```
$$
\int_0^\infty f(x)\,dx = \frac{\pi}{2}
$$
```

Common scientific math:
- Fractions: `$\frac{a}{b}$`
- Subscripts/superscripts: `$x_i^2$`
- Greek: `$\alpha, \beta, \gamma, \Delta$`
- Sums: `$\sum_{i=1}^{n} x_i$`
- Matrices: `$\begin{bmatrix} a & b \\ c & d \end{bmatrix}$`

## Code Blocks

Standard fenced code blocks with language tags for syntax highlighting:

````markdown
```python
def hello():
    print("Hello, world!")
```
````

Supported languages: python, javascript, typescript, bash, r, julia, rust, go, sql, yaml, json, html, css, latex, and many more.

For long code, keep to max 15 lines per slide. Split across slides if needed.

## Speaker Notes

HTML comments at the end of a slide become speaker notes:

```markdown
# My Slide Title

- Key point 1
- Key point 2

<!--
These are speaker notes.
They appear in presenter view but not on the slide.
Multiple lines are supported.

You can include detailed explanations here that you want to SAY
but don't need to SHOW on the slide.
-->
```

## Two-Column Layout

Use HTML with `--html` flag enabled:

```html
<div style="display: flex; gap: 2em;">
<div style="flex: 1;">

### Left Column
- Point 1
- Point 2

</div>
<div style="flex: 1;">

### Right Column
- Point 3
- Point 4

</div>
</div>
```

Note: blank lines before/after markdown content inside HTML divs are required for proper rendering.

## Auto-Scaling Text

```markdown
<!-- _class: lead -->
# <!-- fit --> This Title Auto-Scales to Fit the Slide
```

The `<!-- fit -->` directive makes text scale to fill available width.

## Per-Slide Custom Styling

```markdown
<!-- _style: "font-size: 0.8em;" -->
```

Useful for slides with more content that needs smaller text.

## Themes

| Theme | Look | Best for |
|-------|------|----------|
| `default` | Clean, light, sans-serif | General talks, tutorials |
| `gaia` | Modern, colored headers, professional | Research presentations, conferences |
| `uncover` | Minimal, generous whitespace | Keynotes, concept talks |
| Custom CSS | Full control over every element | Branded/institutional talks |

### Using a Custom Theme

Create a `.css` file:

```css
/* @theme scientific */
@import 'default';

section {
  font-family: 'Palatino', 'Georgia', serif;
  background-color: #fafafa;
}

h1 {
  color: #1a365d;
  border-bottom: 2px solid #2d5986;
}

code {
  background-color: #f0f4f8;
}
```

Reference in render script: `render_presentation.sh input.md pdf ./custom-theme.css`

## Tables

Standard markdown tables work:

```markdown
| Method | Accuracy | F1 Score |
|--------|----------|----------|
| Baseline | 0.72 | 0.68 |
| Ours | **0.89** | **0.85** |
```

## Lists

- Unordered: `- item` or `* item`
- Ordered: `1. item`
- Nested: indent with 2-4 spaces
- Fragment animation (appears one by one): use `*` list markers

## Emoji

Marp supports emoji shortcodes: `:rocket:`, `:chart_with_upwards_trend:`, `:microscope:`

## Useful Patterns for Science Presentations

### Title slide
```markdown
<!-- _class: lead -->
<!-- _paginate: false -->

# Paper Title Here

**Author Name** | Lab/Institution
Conference Name — Date
```

### Results slide with figure
```markdown
## Key Finding: Treatment Improves Outcome by 40%

![bg right:50% w:90%](results_plot.png)

- Statistically significant ($p < 0.001$)
- Effect size: Cohen's $d = 0.82$
- Consistent across subgroups

<!--
Walk through the figure: x-axis shows treatment duration,
y-axis shows outcome measure. Note the divergence at week 4.
-->
```

### Methods overview
```markdown
## Methods

<div style="display: flex; gap: 2em;">
<div style="flex: 1;">

### Data Collection
- N = 500 participants
- Randomized controlled trial
- 12-week follow-up

</div>
<div style="flex: 1;">

### Analysis
- Mixed-effects model
- Intent-to-treat analysis
- Multiple comparison correction

</div>
</div>
```
