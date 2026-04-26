---
name: tool-humanizer
description: >
  Remove AI-generated writing patterns and restore natural human voice.
  Detects and fixes 50+ AI tells: inflated symbolism, promotional language,
  hedging, corporate buzzwords, robotic structure, em dash overuse, rule of
  three, vague attributions, negative parallelisms, conjunctive phrase abuse.
  Three modes: quick (obvious patterns), standard (full scan + score),
  deep (voice-matched using research_context/research-profile.md).
  Called automatically by sci-communication as a post-processing step for
  blog posts, social threads, and newsletters.
  Also invoked standalone: "humanize this", "de-AI this", "make this sound
  human", "remove AI patterns", "clean up this writing".
  Does NOT trigger for formal academic writing (sci-writing handles that).
  Does NOT trigger for content that is intentionally formal or academic.
---

# Humanizer

Strip AI-generated patterns from text. Make it sound like a person wrote it.

## Outcome

Input text returned with AI patterns removed, scored before and after on a 0-10 human-ness scale. Change log shows exactly what was fixed. Output either replaces the original or is saved alongside it.

## Context Needs

| File | Load level | How it shapes this skill |
|------|-----------|--------------------------|
| `research_context/research-profile.md` | full | Replacements use the researcher's actual vocabulary, rhythm, and connectors instead of generic "human" phrasing |
| `research_context/samples.md` | tone refs | Reference for what on-voice sounds like |
| `context/learnings.md` | `## tool-humanizer` section | Patterns the user cares about most, false positives to skip |

Load if they exist. Works standalone with generic replacements.

---

## Instructions

### Step 1: Detect Mode

Choose from context or ask: *"Quick pass, full cleanup, or voice-matched?"*

| Mode | What happens | Best for |
|------|-------------|----------|
| `quick` | Remove obvious AI cliches + buzzwords. Single pass, no scoring. | Fast social edits, internal docs |
| `standard` | Full pattern scan (50+ detections) + human-ness score + change log | Any content going public |
| `deep` | Full scan + replace with voice-profile patterns. Loads `research_context/research-profile.md` | Blog posts, landing pages, emails — anything that must match the researcher's voice |

**Default: `standard`.** When called by another skill as a post-processing step, use `deep` if voice-profile exists, `standard` if not.

### Step 2: Load Context

If mode is `deep`, load `research_context/research-profile.md`. Extract:
- Preferred vocabulary (use these as replacements)
- Avoided words (flag these as AI tells even if not in pattern library)
- Linguistic habits (connectors, intensifiers, rhythm patterns)
- Samples for tone reference

Read `context/learnings.md` → `## tool-humanizer` for known false positives or priority patterns.

### Step 3: Score Original

Rate the input text 0-10 on the human-ness scale:

| Score | Meaning |
|-------|---------|
| 0-3 | Obviously AI — multiple cliches, robotic structure, hedging everywhere |
| 4-5 | AI-heavy — some human touches but needs major work |
| 6-7 | Mixed — could go either way, lacks distinctive voice |
| 8-9 | Human-like — natural voice, minimal AI patterns |
| 10 | Indistinguishable from a skilled human writer |

Scoring factors:
- AI pattern count per 500 words (fewer = better)
- Sentence length variance (higher variance = more human)
- Specificity ratio (concrete terms vs vague qualifiers)
- Structural variety (not every paragraph same shape)

### Step 4: Apply Pattern Detection + Removal

Read `references/pattern-library.md` for the full detection list. Categories:

1. **AI cliches & openers** — "In today's fast-paced world", "Let's dive in", "It's no secret"
2. **Hedging language** — "It's important to note", "arguably", "one might argue"
3. **Corporate buzzwords** — "leverage", "utilize", "facilitate", "optimize"
4. **Robotic structure** — rhetorical Q+A, obsessive parallelism, always-three lists, "Here are the top X"
5. **Overused transitions** — "Moreover", "Furthermore", "Additionally", "Nevertheless"
6. **Promotional inflation** — "transformative", "game-changer", "unprecedented"
7. **Wikipedia AI tells** — inflated symbolism, em dash overuse, rule of three, vague attributions, negative parallelisms, superficial -ing analyses, excessive conjunctive phrases
8. **Vocabulary tells** — "delve", "tapestry", "multifaceted", "landscape", "nuanced", "foster", "realm"

Read `references/replacement-guide.md` for what to replace with.

### Step 5: Enhance Human Markers

After removing AI patterns, add natural voice signals:

- **Varied sentence rhythm** — break up same-length sentences
- **Contractions** — "it's" not "it is" (unless formal context)
- **Active voice** — flip passive constructions
- **Confident assertions** — remove hedging unless genuinely uncertain
- **Specific examples** — flag vague references for the user to make specific

In `deep` mode, apply voice-profile patterns:
- Insert preferred connectors and transitions
- Match sentence length patterns from samples
- Use researcher's vocabulary as replacements for generic terms

### Step 6: Score Revised + Output

Score the revised text. Show the change summary:

```
ORIGINAL: 4.2/10
REVISED:  8.4/10

Changes:
  [N] AI cliches removed
  [N] buzzwords replaced
  [N] hedging phrases cut
  [N] structural patterns fixed
  [N] voice markers added

Flags for review:
  [paragraph/line] — [what needs manual attention]
```

If called standalone, present the cleaned text directly.
If called as a post-processing step by another skill, return the cleaned text silently (the calling skill handles output).

### Step 7: Log Learnings

If the user gives feedback ("that was too aggressive", "keep the em dashes", "good catch on X"), log to `context/learnings.md` → `## tool-humanizer`.

---

## Pipeline Mode

When called by another skill (not standalone), this skill:
1. Receives text as input
2. Runs Steps 2-6 silently
3. Returns cleaned text
4. Only shows the score summary if the change was significant (delta > 2 points)

The calling skill is responsible for saving the final output.

---

## Rules

*Updated automatically when the user flags issues. Read before every run.*

---

## Self-Update

If the user flags an issue — too aggressive, missed a pattern, false positive — update the `## Rules` section immediately with the correction and today's date. Also log to `context/learnings.md` under `## tool-humanizer`.

## Scoring Thresholds

| Score | Label | Action |
|-------|-------|--------|
| 90-100 | Clean | No changes needed |
| 70-89 | Light | Fix flagged patterns only |
| 50-69 | Moderate | Rewrite flagged sentences |
| 0-49 | Heavy | Full rewrite recommended |
