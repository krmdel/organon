# Daily Note Template

## File Location

`research/notes/YYYY-MM-DD.md` -- one file per day, append if exists

---

## Format

```
# Research Notes - {YYYY-MM-DD}

## {HH:MM} - {Title} {#tags}
{Free-form content. No required fields beyond timestamp and text.}

## {HH:MM} - {Title} {#tags}
{Next entry.}
```

---

## Rules

- **Timestamp format:** 24-hour `HH:MM` (e.g., `09:00`, `14:30`)
- **Tags:** inline, space-separated, always prefixed with `#`
- **Supported tags:** `#idea, #experiment, #observation, #meeting` (and any custom tags)
- **No required sections** beyond timestamp header and free-form content
- **If file already exists for today:** append new entry (do not overwrite)
- **One file per day:** all entries for a given date go in the same file
- **Title:** free-form 1-5 words after the timestamp (not enforced, just suggested)

---

## First-Use Message

`Created research notebook at research/notes/. Your first note is ready.`

---

## Confirmation Message

`Logged to research/notes/{date}.md at {HH:MM}.`

---

## Tag Reference

| Tag | Use for |
|-----|---------|
| `#observation` | Experimental results, data patterns, direct observations |
| `#experiment` | Ideas or entries to promote to a formal experiment log |
| `#idea` | Hypotheses, speculative thoughts, design concepts |
| `#meeting` | Lab meetings, collaborator discussions, progress reviews |
| Custom tags | Any domain-specific tag (e.g., `#protocol`, `#analysis`, `#review`) |

---

## Example

```markdown
# Research Notes - 2026-04-03

## 09:00 - Unexpected folding pattern #observation #experiment
Noticed unexpected protein folding pattern in sample batch 3.
Temperature was 2C above protocol spec. May explain anomaly.

## 11:30 - Experimental design idea #idea
Could test temperature gradient effect on folding rate.
Would need batches at 4C, 8C, 12C with n=30 per condition.
```
