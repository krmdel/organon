/**
 * Phase 7 (fix-sprint) T6.3 — minimal LaTeX-to-HTML routine.
 *
 * Covers the biomedical-methods 95%: greek letters, basic operators
 * (\pm, \le, \ge, \neq, \approx, …), \frac, \sqrt, \text, super/sub-scripts.
 * Does NOT cover: integrals with bounds, matrices, multi-line equations,
 * macros, \begin/\end environments — anyone who needs those should keep
 * using KaTeX directly via raw HTML, or wait for a v0.4 katex.js vendoring
 * pass (gated on `npm install` being unblocked).
 *
 * The substitution preserves whitespace and inserts unicode glyphs +
 * a thin `<sup>/<sub>/<span class="math …">` wrapper so the same routine
 * works for both the preview HTML render and exported markdown (Pandoc
 * eats `<sup>` cleanly).
 */

const GREEK_LOWER: Record<string, string> = {
  alpha: "α", beta: "β", gamma: "γ", delta: "δ", epsilon: "ε", varepsilon: "ε",
  zeta: "ζ", eta: "η", theta: "θ", vartheta: "ϑ", iota: "ι", kappa: "κ",
  lambda: "λ", mu: "μ", nu: "ν", xi: "ξ", omicron: "ο", pi: "π", varpi: "ϖ",
  rho: "ρ", varrho: "ϱ", sigma: "σ", varsigma: "ς", tau: "τ", upsilon: "υ",
  phi: "φ", varphi: "ϕ", chi: "χ", psi: "ψ", omega: "ω",
};

const GREEK_UPPER: Record<string, string> = {
  Alpha: "Α", Beta: "Β", Gamma: "Γ", Delta: "Δ", Epsilon: "Ε",
  Zeta: "Ζ", Eta: "Η", Theta: "Θ", Iota: "Ι", Kappa: "Κ",
  Lambda: "Λ", Mu: "Μ", Nu: "Ν", Xi: "Ξ", Omicron: "Ο", Pi: "Π",
  Rho: "Ρ", Sigma: "Σ", Tau: "Τ", Upsilon: "Υ", Phi: "Φ", Chi: "Χ",
  Psi: "Ψ", Omega: "Ω",
};

const SYMBOLS: Record<string, string> = {
  pm: "±", mp: "∓", times: "×", div: "÷", cdot: "·", ast: "∗", star: "⋆",
  le: "≤", leq: "≤", ge: "≥", geq: "≥", neq: "≠", ne: "≠",
  ll: "≪", gg: "≫", approx: "≈", sim: "∼", simeq: "≃",
  equiv: "≡", propto: "∝", cong: "≅",
  infty: "∞", aleph: "ℵ",
  to: "→", rightarrow: "→", leftarrow: "←", leftrightarrow: "↔",
  Rightarrow: "⇒", Leftarrow: "⇐", Leftrightarrow: "⇔", mapsto: "↦",
  partial: "∂", nabla: "∇", forall: "∀", exists: "∃",
  in: "∈", notin: "∉", ni: "∋",
  subset: "⊂", supset: "⊃", subseteq: "⊆", supseteq: "⊇",
  cup: "∪", cap: "∩", emptyset: "∅", varnothing: "∅",
  setminus: "∖", oplus: "⊕", otimes: "⊗",
  sum: "∑", prod: "∏", int: "∫", oint: "∮", coprod: "∐",
  ldots: "…", dots: "…", cdots: "⋯", vdots: "⋮", ddots: "⋱",
  perp: "⊥", angle: "∠", triangle: "△",
  hbar: "ℏ", ell: "ℓ", Re: "ℜ", Im: "ℑ",
  langle: "⟨", rangle: "⟩",
};

const ALL_CMDS: Record<string, string> = { ...GREEK_UPPER, ...GREEK_LOWER, ...SYMBOLS };
const SORTED_CMDS = Object.keys(ALL_CMDS).sort((a, b) => b.length - a.length);

const MATH_SENTINEL_PREFIX = "MATH";
const MATH_SENTINEL_SUFFIX = "";

function applyCommands(s: string): string {
  let out = s;
  // \frac{a}{b} → stacked fraction (sup/sub trick — Pandoc-safe).
  out = out.replace(/\\frac\{([^{}]*)\}\{([^{}]*)\}/g, (_, num, den) =>
    `<span class="frac"><sup>${applyCommands(num)}</sup>⁄<sub>${applyCommands(den)}</sub></span>`);
  // \sqrt{x} → √(overlined x).
  out = out.replace(/\\sqrt\{([^{}]*)\}/g, (_, body) =>
    `<span class="sqrt">√<span class="sqrt-arg" style="border-top:1px solid currentColor">${applyCommands(body)}</span></span>`);
  // \text{...} (typeset roman in math) — strip the wrapper.
  out = out.replace(/\\text\{([^{}]*)\}/g, (_, body) => body);
  // \mathrm/\mathbf/\mathit/\mathbb — drop wrapper, keep inner. (Browsers
  // will inherit the parent style; we don't ship math fonts.)
  out = out.replace(/\\(?:mathrm|mathbf|mathit|mathbb|mathcal|mathfrak|mathsf|mathtt)\{([^{}]*)\}/g,
    (_, body) => body);
  // Phase 15a (DR-2) accents: \ddot first (longer form claims first), then
  // \bar / \hat / \tilde / \vec / \dot. The brief's design rule:
  // single-char body uses a pure unicode combining glyph (no CSS needed);
  // multi-char body wraps in a span class. We detect single-char by visible
  // glyph count after recursive applyCommands resolution, so \bar{\alpha}
  // (resolves to single Greek letter) takes the combining path.
  const accent = (body: string, combining: string, multiClass: string): string => {
    const inner = applyCommands(body);
    const visible = inner.replace(/<[^>]+>/g, "");
    const charCount = [...visible].length;
    return charCount === 1
      ? `${inner}${combining}`
      : `<span class="${multiClass}">${inner}</span>`;
  };
  out = out.replace(/\\ddot\{([^{}]*)\}/g, (_, body) => accent(body, "̈", "ddot"));
  out = out.replace(/\\ddot\s*([a-zA-Z])/g, (_, ch) => `${ch}̈`);
  out = out.replace(/\\bar\{([^{}]*)\}/g, (_, body) => accent(body, "̄", "overline"));
  out = out.replace(/\\bar\s*([a-zA-Z])/g, (_, ch) => `${ch}̄`);
  out = out.replace(/\\hat\{([^{}]*)\}/g, (_, body) => accent(body, "̂", "hat"));
  out = out.replace(/\\hat\s*([a-zA-Z])/g, (_, ch) => `${ch}̂`);
  out = out.replace(/\\tilde\{([^{}]*)\}/g, (_, body) => accent(body, "̃", "tilde"));
  out = out.replace(/\\tilde\s*([a-zA-Z])/g, (_, ch) => `${ch}̃`);
  out = out.replace(/\\vec\{([^{}]*)\}/g, (_, body) => accent(body, "⃗", "vec"));
  out = out.replace(/\\vec\s*([a-zA-Z])/g, (_, ch) => `${ch}⃗`);
  out = out.replace(/\\dot\{([^{}]*)\}/g, (_, body) => accent(body, "̇", "dot"));
  out = out.replace(/\\dot\s*([a-zA-Z])/g, (_, ch) => `${ch}̇`);
  // Multi-letter commands → unicode glyphs (longest match first).
  for (const key of SORTED_CMDS) {
    out = out.replace(new RegExp(`\\\\${key}(?![a-zA-Z])`, "g"), ALL_CMDS[key]);
  }
  // ^{...} super and ^single
  out = out.replace(/\^\{([^{}]*)\}/g, (_, x) => `<sup>${x}</sup>`);
  out = out.replace(/\^([a-zA-Z0-9])/g, (_, x) => `<sup>${x}</sup>`);
  // _{...} sub and _single
  out = out.replace(/_\{([^{}]*)\}/g, (_, x) => `<sub>${x}</sub>`);
  out = out.replace(/_([a-zA-Z0-9])/g, (_, x) => `<sub>${x}</sub>`);
  return out;
}

/**
 * Render a single LaTeX expression. `display=true` wraps it in a centered
 * block; otherwise inline. Inputs are taken raw (NOT html-escaped) — the
 * caller is expected to scan + sentinel before any escapeHtml pass.
 */
export function renderMath(latex: string, display: boolean): string {
  const inner = applyCommands(latex.trim());
  const cls = display
    ? "math math-display block text-center my-2 text-text"
    : "math math-inline text-text";
  return `<span class="${cls}">${inner}</span>`;
}

/**
 * Replace every `$...$` (inline) and `$$...$$` (display) span with a
 * sentinel placeholder; return the text plus a sentinel→HTML map. The
 * caller substitutes the sentinels back AFTER running its own escape +
 * markdown pipeline so math output isn't re-mangled.
 *
 * The sentinel uses control character 0x01 so it can't collide with user
 * markdown (markdown forbids 0x01 in well-formed text).
 */
export function applyMath(s: string): { text: string; mapping: Map<string, string> } {
  const map = new Map<string, string>();
  let counter = 0;
  // $$...$$ first (greedy across whitespace, but not across blank lines).
  let out = s.replace(/\$\$([^$]+?)\$\$/g, (_, latex) => {
    const sentinel = `${MATH_SENTINEL_PREFIX}${counter++}${MATH_SENTINEL_SUFFIX}`;
    map.set(sentinel, renderMath(String(latex), true));
    return sentinel;
  });
  // $...$ inline. Reject patterns where $ is immediately preceded/followed by
  // a digit (so dollar amounts like "$5 to $10" survive).
  out = out.replace(/(^|[^\d\\])\$([^$\n]+?)\$(?!\d)/g, (_, lead, latex) => {
    const sentinel = `${MATH_SENTINEL_PREFIX}${counter++}${MATH_SENTINEL_SUFFIX}`;
    map.set(sentinel, renderMath(String(latex), false));
    return `${lead}${sentinel}`;
  });
  return { text: out, mapping: map };
}

/**
 * Substitute sentinels back with their rendered HTML. Order doesn't matter —
 * each sentinel is unique.
 */
export function substituteMath(html: string, mapping: Map<string, string>): string {
  let out = html;
  for (const [sentinel, rendered] of mapping) {
    out = out.split(sentinel).join(rendered);
  }
  return out;
}
