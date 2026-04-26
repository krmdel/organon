---
name: tool-obsidian
description: >
  Optional knowledge-base integration. Writes well-formed markdown notes
  (with YAML frontmatter, tags, and [[wikilinks]]) into a local Obsidian
  vault so the user's graph picks them up. Zero plugins required —
  filesystem-only passthrough. Categories: data-notes, paper-notes, daily,
  experiments, drafts, inbox. Auto-detects vault via OBSIDIAN_VAULT env var,
  Obsidian's vault registry, or common paths. Use when: "save to obsidian",
  "add to vault", "log to daily note", "capture to inbox", "search my notes",
  "open in obsidian". Does NOT trigger for Organon's own
  context/memory/ — that stays local. Skill is OPTIONAL — framework works
  without Obsidian installed.
---

# Tool: Obsidian (local vault passthrough)

Push Organon knowledge artifacts into the user's Obsidian vault so they land in their existing knowledge graph — search, backlinks, tags, daily notes, graph view — all handled by Obsidian itself. This skill is **optional**: if no vault is detected, the framework keeps working without it and the skill exits cleanly.

## When to use

- Long-term research notes that the user wants alongside their personal knowledge base
- Daily session summaries that should link to other notes via `[[wikilinks]]`
- Paper notes from `sci-literature-research` that reference other papers, authors, methods
- Experiment logs from `sci-hypothesis` that link to related experiments and datasets
- Quick inbox capture for ideas the user wants to triage in Obsidian later

## When NOT to use

- Organon's own `context/memory/{date}.md` session log — that's framework-internal, not knowledge-base material
- Binary deliverables (CSVs, PDFs, figures) — route those to `tool-gdrive` instead
- Research projects with milestones — those belong in `sci-research-mgmt`
- If the user has no Obsidian vault — skip silently, framework is unaffected

## Vault detection (in order)

1. **`OBSIDIAN_VAULT`** environment variable (override) — set in `.env` for explicit control
2. **macOS vault registry** — `~/Library/Application Support/obsidian/obsidian.json` (most-recently-opened vault wins)
3. **Common paths** — `~/Documents/Obsidian/*`, `~/Obsidian/*`, `~/Vaults/*` (picks first child with `.obsidian/` directory)

If none found → skill exits with a clear message pointing at the override. Framework continues normally.

## Commands

All commands go through `scripts/obsidian_ops.py`:

### `status` — Check vault detection
```bash
python3 .claude/skills/tool-obsidian/scripts/obsidian_ops.py status
python3 .claude/skills/tool-obsidian/scripts/obsidian_ops.py status --json
```

### `write` — Create a new note
```bash
python3 .claude/skills/tool-obsidian/scripts/obsidian_ops.py write "My Paper Notes" \
  --body "## Key findings\n- Finding 1\n- Finding 2" \
  --category paper-notes \
  --tags "immunotherapy,review" \
  --link-to "Doudna 2024,CRISPR delivery" \
  --source "https://doi.org/10.1101/2024.10.18.619117"
```
- Auto-generates YAML frontmatter with `title`, `created`, `tags`, `source`, `links`
- Converts `--link-to` values into Obsidian `[[wikilinks]]` in the frontmatter
- Collision → appends `-1`, `-2`, ... (unless `--overwrite`)
- Body can come from `--body`, `--from-file`, or stdin

### `append` — Add to an existing note
```bash
echo "new observation" | obsidian_ops.py append paper-notes/doudna-2024.md --heading "Follow-up"
```

### `daily` — Append to today's daily note
```bash
python3 .claude/skills/tool-obsidian/scripts/obsidian_ops.py daily \
  --body "Ran t-test on experiment_42 — p=0.003" \
  --heading "Session notes"
```
Daily notes live at `<vault>/organon/daily/YYYY-MM-DD.md`. Created on first use per day.

### `list` — Show staged notes
```bash
python3 .claude/skills/tool-obsidian/scripts/obsidian_ops.py list
python3 .claude/skills/tool-obsidian/scripts/obsidian_ops.py list --category experiments
```

### `search` — Filesystem search across notes
```bash
python3 .claude/skills/tool-obsidian/scripts/obsidian_ops.py search "CRISPR delivery"
python3 .claude/skills/tool-obsidian/scripts/obsidian_ops.py search "p-value" --category experiments
```
Case-insensitive; matches filename or body. Returns a snippet of the first match per note. For heavier queries (backlinks, tag graphs, Dataview), open the vault in Obsidian.

### `link` — Get an `obsidian://` URI
```bash
python3 .claude/skills/tool-obsidian/scripts/obsidian_ops.py link /path/to/vault/organon/paper-notes/foo.md
# → obsidian://open?vault=MyVault&file=organon/paper-notes/foo
```
Clicking the URI opens the note directly in Obsidian.

## Categories

| Category | What goes here |
|---|---|
| `data-notes/` | Observations from `sci-data-analysis` (trends, anomalies, cleaned-dataset commentary) |
| `paper-notes/` | Literature notes from `sci-literature-research` with backlinks to authors/methods |
| `daily/` | Session summaries from `meta-wrap-up`, dated `YYYY-MM-DD.md` |
| `experiments/` | Hypothesis + experiment design notes from `sci-hypothesis` |
| `drafts/` | In-progress manuscript drafts from `sci-writing` |
| `inbox/` | Unsorted / quick capture — triage in Obsidian later |

## Integration with other skills

This skill is **optional** — other skills should check `status` first, and only write if Obsidian is detected. Typical pattern:

```python
# Inside another skill after producing a result:
# 1. Check Obsidian availability
status_result = run("obsidian_ops.py", "status", "--json")
if status_result["installed"]:
    # 2. Offer to the user
    prompt = "Also save this to your Obsidian vault?"
    # 3. On yes, write with appropriate category and tags
```

The **Obsidian Sync Gate** in `CLAUDE.md` (parallel to the Drive Push Gate) governs when to ask.

## Dependencies

| Required | What it provides | Fallback |
|---|---|---|
| Obsidian vault (any form) | Where notes are written | None — skill exits with OPTIONAL banner; framework is unaffected |

No plugins, no API keys, no OAuth. Pure filesystem. Compatible with Obsidian sync, iCloud-synced vaults, and plain local vaults.

## Graceful degradation

Every command calls `find_vault()` first. If detection fails:
- `status` returns `installed: False` with an explanation
- `write`, `append`, `daily`, `search`, `list` all exit with `SystemExit` and a message pointing at the `OBSIDIAN_VAULT` env var override
- No partial writes, no garbage files

The user can enable the skill at any time by setting `OBSIDIAN_VAULT=/path/to/vault` in `.env` — no code changes, no restart.

## Troubleshooting

- **"Obsidian vault not detected"**: set `OBSIDIAN_VAULT=/absolute/path/to/vault` in `.env` or open the vault in Obsidian at least once (registers it in `obsidian.json`)
- **Notes not appearing in Obsidian graph**: Obsidian re-indexes on file changes; give it a second, or reopen the vault
- **Wikilinks not resolving**: note titles in `--link-to` must match existing note filenames (minus `.md`) — Obsidian handles the rest
- **Wrong vault picked**: Organon picks the most-recently-opened vault by default — override with `OBSIDIAN_VAULT` if you have multiple
