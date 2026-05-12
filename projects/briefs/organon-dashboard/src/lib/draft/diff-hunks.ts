// Phase 28 (v1.2) — Per-line diff accept (DR-6+).
//
// Splits a (before, after) diff into hunks at unchanged-line
// boundaries. Each `change` hunk carries an `applied` flag; the
// composer reassembles `after` from `before` + chosen hunks. The
// DiffView renders a per-hunk Accept toggle for each `change` entry;
// the v1.1 "Apply edit" path is preserved as the "Accept all"
// shortcut (sets every change-hunk applied + composes).
//
// Algorithm: pure-JS Myers LCS over lines. No deps. Lines are the
// natural granularity for markdown — char-level diffs would be messy
// inside paragraph wrapping.
//
// Conflicting hunks are NOT detected. Accepting hunk A but not B can
// produce nonsensical text — that's the user's call. v1.3 can add
// conflict detection.

export type HunkType = "context" | "change";

export type Hunk = {
  id: string;
  type: HunkType;
  before_lines: string[];
  after_lines: string[];
  applied: boolean;
};

/**
 * Myers LCS over lines. Returns the index pairs for matched lines
 * (sequence of (i, j) such that a[i] === b[j], increasing in both i
 * and j). Time O(n * m); fine for section-sized diffs (~hundreds of
 * lines max).
 */
function lcsPairs(a: string[], b: string[]): Array<[number, number]> {
  const n = a.length;
  const m = b.length;
  const dp: number[][] = Array.from({ length: n + 1 }, () =>
    Array(m + 1).fill(0),
  );
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      if (a[i] === b[j]) dp[i][j] = dp[i + 1][j + 1] + 1;
      else dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const pairs: Array<[number, number]> = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      pairs.push([i, j]);
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      i++;
    } else {
      j++;
    }
  }
  return pairs;
}

/**
 * Split a (before, after) diff into hunks. Returns the alternating
 * context / change sequence; consecutive context-only matches coalesce,
 * and consecutive change rows coalesce into single change hunks.
 *
 * The default newline is `\n`. Trailing newlines are normalised so
 * before === after on a clean revision returns a single context hunk.
 */
export function splitDiff(before: string, after: string): Hunk[] {
  const a = before.split("\n");
  const b = after.split("\n");
  const pairs = lcsPairs(a, b);
  const hunks: Hunk[] = [];
  let ai = 0;
  let bi = 0;
  let nextChangeId = 0;
  let nextContextId = 0;

  const pushChange = (beforeLines: string[], afterLines: string[]) => {
    if (beforeLines.length === 0 && afterLines.length === 0) return;
    hunks.push({
      id: `change-${nextChangeId++}`,
      type: "change",
      before_lines: beforeLines,
      after_lines: afterLines,
      // v1.2 default: every change hunk is applied so v1.1's "Apply
      // edit" UX continues to work without per-hunk interaction.
      applied: true,
    });
  };
  const pushContext = (lines: string[]) => {
    if (lines.length === 0) return;
    hunks.push({
      id: `context-${nextContextId++}`,
      type: "context",
      before_lines: lines.slice(),
      after_lines: lines.slice(),
      applied: true,
    });
  };

  for (const [pi, pj] of pairs) {
    // Anything between (ai, bi) and the matched pair is a change.
    const beforeChunk = a.slice(ai, pi);
    const afterChunk = b.slice(bi, pj);
    if (beforeChunk.length > 0 || afterChunk.length > 0) {
      pushChange(beforeChunk, afterChunk);
    }
    // The matched pair itself is a context hunk; merge with the
    // previous context hunk if it sits at the tail.
    const tail = hunks[hunks.length - 1];
    if (tail && tail.type === "context") {
      tail.before_lines.push(a[pi]);
      tail.after_lines.push(a[pi]);
    } else {
      pushContext([a[pi]]);
    }
    ai = pi + 1;
    bi = pj + 1;
  }
  // Trailing change after the last matched pair.
  const tailBefore = a.slice(ai);
  const tailAfter = b.slice(bi);
  if (tailBefore.length > 0 || tailAfter.length > 0) {
    pushChange(tailBefore, tailAfter);
  }
  return hunks;
}

/**
 * Reassemble a string from `before` + the chosen hunks. Context hunks
 * always render verbatim. Change hunks render `after_lines` when
 * `applied: true`, `before_lines` otherwise.
 *
 * The `before` argument is unused on the happy path (the hunks already
 * carry both sides) but kept as a defensive reference for future v1.3
 * conflict-detection paths.
 */
export function composeFromHunks(_before: string, hunks: Hunk[]): string {
  const out: string[] = [];
  for (const h of hunks) {
    if (h.type === "context") {
      out.push(...h.before_lines);
      continue;
    }
    if (h.applied) {
      out.push(...h.after_lines);
    } else {
      out.push(...h.before_lines);
    }
  }
  return out.join("\n");
}

/**
 * Convenience: flip a single hunk's `applied` flag and return a new
 * array. The DiffView's per-hunk Accept toggle drives this.
 */
export function toggleHunkApplied(hunks: Hunk[], id: string): Hunk[] {
  return hunks.map((h) =>
    h.type === "change" && h.id === id ? { ...h, applied: !h.applied } : h,
  );
}

/**
 * Convenience: set every change hunk's `applied` to a fixed value.
 * Backs the "Accept all" / "Reject all" shortcuts in the DiffView.
 */
export function setAllChangeHunksApplied(hunks: Hunk[], applied: boolean): Hunk[] {
  return hunks.map((h) =>
    h.type === "change" ? { ...h, applied } : h,
  );
}

// Phase 32 (v1.3) — DR-6++ per-hunk conflict detection.
//
// Heuristic-only — proximity + token-pair. Semantic AST-aware checks
// are deferred to v1.4. Non-blocking by design: the DiffView surfaces
// warnings but Apply Selected stays enabled. The user's call.
//
// Heuristics shipped in v1.3:
//   (a) proximity: two adjacent change hunks separated by ≤2 context
//       lines where exactly one is applied (the partial-accept signal).
//   (b) token-pair: change hunk A removes a \cite{X} / \fig{X} token
//       that change hunk B references (or vice-versa); symmetric.
// Heuristic deferred to v1.4:
//   (c) identifier conflict: A renames a heading via "# old → # new"
//       while B references the old heading.

export type ConflictReason = "proximity-partial-accept" | "token-pair-conflict";

export type ConflictWarning = {
  hunk_a: string;
  hunk_b: string;
  reason: ConflictReason;
};

export type ConflictReport = {
  warnings: ConflictWarning[];
};

const TOKEN_RE = /\\(cite|fig)\{([^}]+)\}/g;

function tokensIn(lines: string[]): Set<string> {
  const out = new Set<string>();
  const text = lines.join("\n");
  let m: RegExpExecArray | null;
  TOKEN_RE.lastIndex = 0;
  while ((m = TOKEN_RE.exec(text)) !== null) {
    out.add(`${m[1]}:${m[2]}`);
  }
  return out;
}

export function detectHunkConflicts(hunks: Hunk[]): ConflictReport {
  const warnings: ConflictWarning[] = [];

  // (a) proximity. Walk consecutive change hunks; sum context_lines
  // between them. Fire when total ≤ 2 AND applied flags differ.
  const indexed = hunks.map((h, idx) => ({ h, idx }));
  const changes = indexed.filter(({ h }) => h.type === "change");
  for (let i = 0; i < changes.length - 1; i++) {
    const a = changes[i];
    const b = changes[i + 1];
    let contextLines = 0;
    for (let k = a.idx + 1; k < b.idx; k++) {
      if (hunks[k].type === "context") {
        contextLines += hunks[k].before_lines.length;
      }
    }
    if (contextLines <= 2 && a.h.applied !== b.h.applied) {
      warnings.push({
        hunk_a: a.h.id,
        hunk_b: b.h.id,
        reason: "proximity-partial-accept",
      });
    }
  }

  // (b) token-pair. For each ordered pair (A, B), check whether A
  // removes a token that B references anywhere. Pairs are deduped by
  // canonical (lo, hi) ordering so each token-pair conflict surfaces
  // once.
  const seen = new Set<string>();
  for (let i = 0; i < changes.length; i++) {
    for (let j = 0; j < changes.length; j++) {
      if (i === j) continue;
      const a = changes[i].h;
      const b = changes[j].h;
      const aBefore = tokensIn(a.before_lines);
      const aAfter = tokensIn(a.after_lines);
      const aRemoves = new Set<string>();
      for (const t of aBefore) if (!aAfter.has(t)) aRemoves.add(t);
      if (aRemoves.size === 0) continue;
      const bAll = new Set<string>([...tokensIn(b.before_lines), ...tokensIn(b.after_lines)]);
      for (const tok of aRemoves) {
        if (bAll.has(tok)) {
          const lo = a.id < b.id ? a.id : b.id;
          const hi = a.id < b.id ? b.id : a.id;
          const key = `${lo}::${hi}::${tok}`;
          if (seen.has(key)) continue;
          seen.add(key);
          warnings.push({ hunk_a: lo, hunk_b: hi, reason: "token-pair-conflict" });
        }
      }
    }
  }

  return { warnings };
}
