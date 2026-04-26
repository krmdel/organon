# Organon Cheat Sheet

## Daily Operations

| Action | How |
|--------|-----|
| Start working (solo) | `cd ~/Projects/organon && claude` |
| Start working (client) | `cd ~/Projects/organon/clients/client-name && claude` |
| End session | Just say "done" or "that's it" — wrap-up runs automatically |
| Switch clients | End session → new terminal → `cd` into different client folder |
| Quick clear (no save) | `/clear` (end session first to save context) |
| First time with new client | Just open Claude — onboarding runs automatically |

## Client Management

| Action | Command |
|--------|---------|
| Add a new client | `bash scripts/add-client.sh "Client Name"` |
| Update Organon | `git pull origin main && bash scripts/install.sh` |

## Skills

| Action | Command |
|--------|---------|
| List available | `bash scripts/list-skills.sh` |
| Add skill | `bash scripts/add-skill.sh skill-name` |
| Remove skill | `bash scripts/remove-skill.sh skill-name` |

## Scheduled Jobs

The cron dispatcher is installed automatically during setup. Just create jobs and they run on schedule.

| Action | Command |
|--------|---------|
| Run job manually | `bash scripts/run-job.sh job-name` |
| Check job logs | `cat cron/logs/job-name.log` |
| List jobs | `ls cron/jobs/` or ask Claude "what's scheduled?" |

## Projects ([full guide](projects-guide.md))

| Level | Name | How | Where |
|-------|------|-----|-------|
| **1** | Single task | Just ask Claude | `projects/{category}-{type}/` |
| **2** | Planned project | Claude scopes it → project folder with `brief.md` | `projects/briefs/{project-name}/` |
| **3** | GSD project | `/gsd:new-project` → full phased planning | `projects/briefs/{project-name}/` + `.planning/` |

Level 1 output goes to category folders. Level 2/3 output goes inside the project folder alongside `brief.md`. Claude automatically helps you pick the right level when you state your goal. Run `/archive-gsd` when a GSD project is done to free up the workspace.

## Key Paths (within your working folder)

| What | Where |
|------|-------|
| Research profile | `research_context/research-profile.md` |
| Session memory | `context/memory/YYYY-MM-DD.md` |
| Learnings | `context/learnings.md` |
| Single task output | `projects/{category}-{type}/` |
| Project output | `projects/briefs/{project-name}/` (with `brief.md`) |
| Project brief | `projects/briefs/{project-name}/brief.md` |
| GSD planning | `.planning/` (one at a time, at project root) |
| API keys | `.env` |
| Skills | `.claude/skills/` |
| Client instructions | `CLAUDE.md` (in client folder) |
| Shared methodology | `CLAUDE.md` (at Organon repo root — auto-inherited) |

## Where Skills Live

| What | Path |
|------|------|
| Master copy (source of truth) | `.claude/skills/` at root |
| Client working copy | `clients/client-name/.claude/skills/` |
| Skill methodology | `.claude/skills/{skill-name}/SKILL.md` |
| Skill reference material | `.claude/skills/{skill-name}/references/` |
| Available skills catalog | `.claude/skills/_catalog/catalog.json` |

Add/remove/edit skills from the **root**. Every client folder holds a symlink back to the root `.claude/skills/` on Unix, so changes propagate instantly. On Windows, re-run `add-client.sh` against the client to refresh its copy. Client-only skills go in a separate folder (e.g. `clients/{name}/.claude/skills-local/`) and are never touched.

## Rules of Thumb

- Solo user? Work from the root folder. Nothing extra needed.
- Multiple clients? One client folder each, inside `clients/`.
- End session before switching clients — wrap-up runs automatically
- Onboarding runs automatically on first session per client
- Edit skills at the **root** level — clients pick up the change instantly via symlinks (Unix)
- Client-only skills go in `clients/{name}/.claude/skills-local/` — outside the shared symlink
- Edit root CLAUDE.md → all clients see it automatically
- Edit root SOUL.md / USER.md → all clients see it automatically
- Update via `git pull origin main && bash scripts/install.sh`
- Skills always have fallbacks — no API key required to start working
