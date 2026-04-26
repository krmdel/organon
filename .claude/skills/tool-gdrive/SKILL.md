---
name: tool-gdrive
description: >
  Stage Organon deliverables into Google Drive via the desktop app's
  local sync folder. Zero OAuth, zero API keys — files copied into the sync
  folder upload automatically. Auto-categorizes by extension (data, figures,
  manuscripts, presentations, papers, notes). Use when: "push to Drive",
  "upload to Google Drive", "sync this to Drive", "share this file", "stage
  output for collaborators", "backup to Drive". Does NOT trigger for Google
  Docs/Sheets programmatic editing — that needs a separate API-based skill.
  Requires Google Drive desktop app installed and signed in.
---

# Tool: Google Drive (desktop sync)

Stage files into a shared `organon/` folder inside your Google Drive "My Drive" so collaborators can view, comment, and download without extra tooling. This skill is **local-only** — it moves bytes into the desktop app's sync folder, and the app handles the upload + share-link generation.

## When to use

- Sharing a CSV, figure, or manuscript with a collaborator who lives in Drive/Sheets/Docs
- Cloud-backing an output that matters beyond the session
- Making a local deliverable accessible from phone / web / another machine

## When NOT to use

- Programmatic Google Docs editing with track-changes → needs a `tool-gworkspace` skill with OAuth
- Sheets formula / named-range manipulation → same
- Real-time collaboration on a live doc → use the Drive web UI

## Commands

All go through `scripts/gdrive_ops.py`. The script takes these subcommands:

### `status` — Check mount
```bash
python3 .claude/skills/tool-gdrive/scripts/gdrive_ops.py status
```
Confirms Google Drive desktop is running and shows the staging root path.

### `stage` — Copy a file to Drive
```bash
python3 .claude/skills/tool-gdrive/scripts/gdrive_ops.py stage path/to/file.csv
python3 .claude/skills/tool-gdrive/scripts/gdrive_ops.py stage fig.png --category figures
python3 .claude/skills/tool-gdrive/scripts/gdrive_ops.py stage draft.md --rename "manuscript_v2.md"
```
Auto-categorizes by extension:

| Extensions | Category |
|---|---|
| `.csv .xlsx .json .tsv .parquet` | `data/` |
| `.png .jpg .svg .tif` | `figures/` |
| `.pdf .md .docx .tex` | `manuscripts/` |
| `.pptx .key` | `presentations/` |
| `.bib` | `papers/` |
| anything else | `notes/` |

On collision, appends a Unix timestamp to the filename.

### `list` — Show staged files
```bash
python3 .claude/skills/tool-gdrive/scripts/gdrive_ops.py list
python3 .claude/skills/tool-gdrive/scripts/gdrive_ops.py list --category figures
```

### `link` — Get a file:// URL
```bash
python3 .claude/skills/tool-gdrive/scripts/gdrive_ops.py link "/path/to/staged/file.csv"
```
Returns a `file://` URL that opens the synced file in Finder. For a shareable web link, right-click the file in Drive → "Get link".

## Integration with other skills

When another skill produces a deliverable and the user wants it in Drive, invoke `stage` after the file is saved. Typical flow:

1. `sci-data-analysis` saves `analysis_20260413.csv`
2. User says "push this to Drive"
3. This skill stages → `~/Google Drive/My Drive/organon/data/analysis_20260413.csv`
4. Desktop app uploads in background
5. Report the `file://` URL so the user can open it in Finder

## Dependencies

| Required | What it provides | Fallback |
|---|---|---|
| Google Drive desktop app | Local sync folder that the OS writes to like any other directory | None — skill errors cleanly with install URL |

No Python packages beyond the stdlib. Runs under plain `python3`.

## Graceful degradation

If Google Drive desktop is not mounted, `stage` exits with a clear error pointing at the install URL. No partial writes, no silent failures. The skill works standalone without `research_context/` — it simply passes files through regardless of the researcher profile.

## Output

Files land in `<My Drive>/organon/<category>/<filename>`. Desktop app sync is near-instant on a good connection; expect the file to appear in `drive.google.com` within seconds.

## Troubleshooting

- **"Google Drive desktop not detected"**: check `ls ~/Library/CloudStorage/` — you should see a `GoogleDrive-<email>` entry. If missing, the app is not installed or not signed in.
- **File staged but not appearing online**: open the Drive menubar app, check the sync queue. Paused sync is the usual culprit.
- **"Permission denied"**: Drive desktop owns the folder; make sure the running shell has access to `~/Library/CloudStorage/` (Full Disk Access in System Settings → Privacy).
- **Wrong category**: pass `--category` explicitly to override the extension mapping.
