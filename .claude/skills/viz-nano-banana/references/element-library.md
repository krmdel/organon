# Element Library

SVG snippets for decorative elements, badges, figures, and connectors. Use these when building SVG blueprints (Mode B) or as prompt description aids.

---

## Decorative Elements

### 4-Point Star
```xml
<path d="M 0 -8 L 2 -2 L 8 0 L 2 2 L 0 8 L -2 2 L -8 0 L -2 -2 Z"
      fill="#F4C542" transform="translate(X, Y)" />
```

### Sparkle (Cross)
```xml
<g transform="translate(X, Y)" stroke="#F4C542" stroke-width="1.5" stroke-linecap="round">
  <line x1="0" y1="-5" x2="0" y2="5" />
  <line x1="-5" y1="0" x2="5" y2="0" />
</g>
```

### Confetti Piece
```xml
<rect x="0" y="0" width="4" height="10" rx="1" fill="#9B7ED8"
      transform="translate(X, Y) rotate(35)" />
```

### Lightbulb Icon
```xml
<g transform="translate(X, Y)">
  <circle cx="0" cy="0" r="10" stroke="currentColor" stroke-width="2" fill="#F4C542" opacity="0.3" />
  <circle cx="0" cy="0" r="10" stroke="currentColor" stroke-width="2" fill="none" />
  <line x1="-3" y1="10" x2="3" y2="10" stroke="currentColor" stroke-width="1.5" />
  <line x1="0" y1="-14" x2="0" y2="-18" stroke="currentColor" stroke-width="1.5" />
  <line x1="10" y1="-8" x2="14" y2="-11" stroke="currentColor" stroke-width="1.5" />
  <line x1="-10" y1="-8" x2="-14" y2="-11" stroke="currentColor" stroke-width="1.5" />
</g>
```

### Squiggly Underline
```xml
<path d="M X Y q 5 -4 10 0 q 5 4 10 0 q 5 -4 10 0 q 5 4 10 0"
      stroke="currentColor" stroke-width="2" fill="none" />
```

### Small Gear
```xml
<g transform="translate(X, Y) scale(0.6)">
  <circle cx="0" cy="0" r="8" stroke="currentColor" stroke-width="2" fill="none" />
  <circle cx="0" cy="0" r="3" stroke="currentColor" stroke-width="1.5" fill="none" />
  <line x1="0" y1="-8" x2="0" y2="-12" stroke="currentColor" stroke-width="2.5" />
  <line x1="7" y1="-4" x2="10" y2="-6" stroke="currentColor" stroke-width="2.5" />
  <line x1="7" y1="4" x2="10" y2="6" stroke="currentColor" stroke-width="2.5" />
  <line x1="0" y1="8" x2="0" y2="12" stroke="currentColor" stroke-width="2.5" />
  <line x1="-7" y1="4" x2="-10" y2="6" stroke="currentColor" stroke-width="2.5" />
  <line x1="-7" y1="-4" x2="-10" y2="-6" stroke="currentColor" stroke-width="2.5" />
</g>
```

---

## When to Use in Prompts

These snippets are primarily for SVG blueprint mode. When using direct prompt mode, describe the elements in natural language instead:

- Stars/sparkles → "scatter small decorative stars and sparkle marks in the empty space"
- Confetti → "add colorful confetti pieces near the celebration/success area"
- Lightbulb → "place a lightbulb icon next to the idea/insight"
- Gears → "small gear icons near the process/mechanism"
- Squiggly underlines → "wavy underlines beneath key terms"
