# Research Project Template

## File Location

Research projects are stored as individual markdown files in `research/projects/`. One file per project.

Path format: `research/projects/{slug}.md`

Where `{slug}` is lowercase, hyphens only, derived from the project name. Example: "CRISPR Knockdown Study" → `research/projects/crispr-knockdown-study.md`

---

## Template

Create a new project file using this exact YAML frontmatter and markdown body:

```yaml
---
name: {Project Name}
status: active
goal: {One-sentence goal}
pi: {Principal investigator}
collaborators: [{list}]
funding: {Source and grant number}
irb: {IRB number and status, or "not applicable"}
created: {YYYY-MM-DD}
deadline: {YYYY-MM-DD}
milestones:
  - name: {Milestone name}
    date: "{YYYY-MM-DD}"
    status: complete | in-progress | pending
linked_publications: []
datasets: []
linked_outputs: []
---

# {Project Name}

## Progress Notes
- {YYYY-MM-DD}: {Update}
```

---

## Field Rules

All fields are required at creation. `collaborators`, `linked_publications`, `datasets`, and `linked_outputs` can start as empty arrays `[]`.

| Field | Type | Notes |
|-------|------|-------|
| `name` | string | Full project name |
| `status` | enum | `active` \| `paused` \| `complete` \| `archived` |
| `goal` | string | One-sentence research goal |
| `pi` | string | Principal investigator name |
| `collaborators` | array | List of collaborator names, or `[]` |
| `funding` | string | Funding source and grant number, or "unfunded" |
| `irb` | string | IRB protocol number and status, or "not applicable" |
| `created` | date string | `YYYY-MM-DD` format |
| `deadline` | date string | `YYYY-MM-DD` format |
| `milestones` | array | Each milestone has `name`, `date`, `status` |
| `linked_publications` | array | DOIs or file paths to papers, or `[]` |
| `datasets` | array | File paths or dataset identifiers, or `[]` |
| `linked_outputs` | array | Paths to relevant outputs (hypotheses, plots, etc.), or `[]` |

**Milestone date quoting rule:** Milestone dates MUST be quoted strings in YAML to prevent date parsing errors:
```yaml
milestones:
  - name: "Pilot data collection"
    date: "2026-06-01"
    status: pending
```
Not: `date: 2026-06-01` (unquoted dates can be misinterpreted by YAML parsers — per Pitfall 4)

**Status values:**
- `active` — project is currently being worked on
- `paused` — work temporarily halted
- `complete` — all milestones done
- `archived` — no longer active, kept for reference

**Milestone status values:**
- `complete` — milestone finished
- `in-progress` — currently working on this milestone
- `pending` — not yet started

**Progress notes:** Reverse-chronological order (newest first). Add a new entry each time there is meaningful progress.

**Slug rules:** Lowercase letters and hyphens only. Derived from project name. Remove stop words for brevity (optional).

---

## Dashboard Mode

When the scientist asks about "projects" with no specific project name, render the dashboard view.

Parse all files in `research/projects/`, extract YAML frontmatter, and render this table sorted by deadline (ascending):

```markdown
# Research Projects Dashboard

| Project | Status | Next Milestone | Deadline | Progress |
|---------|--------|----------------|----------|----------|
| {name} | **{status}** | {next pending/in-progress milestone name} | {deadline} | {complete}/{total} |

*{N} active projects, {M} paused. Next deadline: {project} in {N} days.*
```

**Column rules:**
- **Project**: Bold the project name for emphasis in context
- **Status**: Use `**bold**` for all status values: `**active**`, `**paused**`, `**complete**`, `**archived**`
- **Next Milestone**: Show the name of the first milestone with status `in-progress` or `pending`. If all milestones are complete, show "All complete"
- **Deadline**: `YYYY-MM-DD` format
- **Progress**: `{complete}/{total}` fraction — count milestones with status `complete` / total milestone count

**Dashboard footer format:**
```
*{N} active projects, {M} paused. Next deadline: {project} in {N} days.*
```
Where `{N} days` is calculated from today's date to the nearest deadline among active projects.

**No projects case:**
```
No research projects yet. Create one by describing your research goal, and I'll set up tracking with milestones and deadlines.
```

---

## Detail Mode

When the scientist asks about a specific project by name or slug, render the detail view.

```markdown
# {Project Name}

**Status:** {status} | **PI:** {pi} | **Deadline:** {deadline}
**Goal:** {goal}
**Funding:** {funding} | **IRB:** {irb}

## Milestone Timeline

- [x] {Milestone name} (due {date}) — complete
- [~] {Milestone name} (due {date}) — in progress
- [ ] {Milestone name} (due {date}) — pending
- [!] {Milestone name} (due {date}) — **OVERDUE** ({N} days ago)

## Recent Progress

- {YYYY-MM-DD}: {Update}
- {YYYY-MM-DD}: {Update}
(last 5 entries)

## Linked Outputs

- `{file path}`
- `{file path}`
```

**Milestone status indicators:**
- `[x]` — complete
- `[~]` — in-progress
- `[ ]` — pending
- `[!]` — overdue: date is before today AND status is not `complete`

**Overdue detection:** Compare milestone `date` to today's date. If date < today and status != `complete`, mark as overdue with `**OVERDUE**` label and days since deadline.

**Recent progress:** Show the 5 most recent progress notes (first 5 entries in reverse-chronological order).

**Linked outputs:** Show all entries from `linked_outputs` array as clickable file paths using backtick formatting.

---

## Milestone Updates

When the scientist marks a milestone complete:

1. Read the project file
2. Find the milestone by name
3. Update its `status` to `complete`
4. Add a progress note entry with today's date
5. Show the next pending milestone

**Confirmation copywriting:**
```
Marked "{milestone}" as complete in {project}. Next: {next_milestone} (due {date}).
```

If there is no next milestone:
```
Marked "{milestone}" as complete in {project}. All milestones complete — consider updating project status to "complete".
```

**Overdue milestone alert:**
```
**OVERDUE:** "{milestone}" in {project} was due {date} ({N} days ago).
```

---

## Copywriting

All Project Mode output uses these exact strings (from UI-SPEC):

| Trigger | Copy |
|---------|------|
| Project created | `Research project "{name}" created at research/projects/{slug}.md.` |
| Dashboard header | `# Research Projects Dashboard` |
| Dashboard footer | `*{N} active projects, {M} paused. Next deadline: {project} in {N} days.*` |
| No projects | `No research projects yet. Create one by describing your research goal, and I'll set up tracking with milestones and deadlines.` |
| Milestone complete | `Marked "{milestone}" as complete in {project}. Next: {next_milestone} (due {date}).` |
| Milestone overdue | `**OVERDUE:** "{milestone}" in {project} was due {date} ({N} days ago).` |
