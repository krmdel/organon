# Running Organon for Multiple Clients

## The Key Principle

Organon has two layers:

1. **Methodology** — CLAUDE.md, SOUL.md, USER.md, skills, scripts. Version-controlled and shared. Lives at the root of your Organon folder.
2. **Client data** — research_context/, memory/, learnings, projects/, cron/jobs/. Unique per client. Lives inside `clients/{client-name}/`.

Everyone starts as a solo operator working from the root folder. When you need a second client, run `add-client.sh` — it creates a client workspace and seeds it with your existing learnings as a starting point.

The root folder keeps its own memory and learnings for system-wide work (building skills, testing methodology, non-client tasks). Client folders each have their own.

---

## How Parent CLAUDE.md Works

Claude Code has a built-in feature: it reads CLAUDE.md files from parent directories and merges them together. This is the foundation of multi-client.

```
organon/
├── CLAUDE.md                    <- Claude Code reads this (parent)
└── clients/
    └── client-one/
        ├── CLAUDE.md            <- Claude Code reads this too (project root)
        └── ...                     Both are merged. Parent provides methodology,
                                    client provides overrides.
```

When you `cd clients/client-one && claude`:
- The root `CLAUDE.md` loads automatically — all methodology, skill registry, context matrix, heartbeat rules
- The client's `CLAUDE.md` adds client-specific instructions on top
- You never need to duplicate or sync the main CLAUDE.md

---

## What's Shared vs What's Separate

| What | Where | How clients get it |
|------|-------|-------------------|
| `CLAUDE.md` (methodology) | Root | Auto-inherited via parent CLAUDE.md — no copy needed |
| `context/SOUL.md` | Root | Read by heartbeat fallback — no copy needed |
| `context/USER.md` | Root | Read by heartbeat fallback — no copy needed |
| `.claude/skills/` | Root + each client | Symlinked on client creation (Unix) — edits to root propagate instantly |
| `scripts/` | Root + each client | Symlinked on client creation (Unix) — edits to root propagate instantly |
| `CLAUDE.md` (client-specific) | Each client | Created by `add-client.sh` — your space for client notes |
| `research_context/` | Each client | Built automatically on first session — unique per researcher |
| `context/learnings.md` | Root + each client | Root has system-wide learnings. Client starts with a copy, then diverges |
| `context/memory/` | Root + each client | Root has system-wide memory. Client has its own session history |
| `projects/` | Each client | Per-client deliverables |
| `.env` | Each client | API keys — usually the same, copied from root on creation |
| `cron/jobs/` | Each client | Per-client scheduled tasks |

### What stays in sync automatically

- **CLAUDE.md methodology** — parent directory inheritance, instant
- **SOUL.md and USER.md** — heartbeat reads from root, instant
- **Skills and scripts** — symlinked from root when `add-client.sh` creates the workspace, so any edit at the root propagates to every client instantly (Unix). On Windows they are copied; re-run `add-client.sh` to refresh, or copy manually.

### What you manage manually

- **Research context** — unique per client, built automatically on first session
- **Learnings** — accumulate independently per client
- **API keys** — copy your `.env` to new clients if needed (done automatically on creation)

---

## How Skills Stay in Sync

Skills live in the root folder as the master copy. Each client folder has a **symlink** (Unix) back to the root `.claude/skills/` directory, so you never need to think about keeping them in sync — any edit at the root is visible inside every client the moment you save the file.

On Windows, `add-client.sh` copies skills instead (symlinks require elevated privileges). You can refresh a Windows client by re-running `bash scripts/add-client.sh "Client Name"` against the existing folder.

### Where to Edit Skills

Always edit skills at the root level. On Unix, the symlink means the client automatically sees the change. On Windows, a root edit only propagates on the next `add-client.sh` refresh.

```
Edit here:     organon/.claude/skills/sci-writing/SKILL.md     ← source of truth
Not here:      organon/clients/client-one/.claude/skills/sci-writing/SKILL.md  ← this is a symlink (Unix) or stale copy (Windows)
```

### Client-Only Skills

If you need a skill that's specific to one client, create it in a separate folder alongside the symlinked `.claude/skills/` — for example, `clients/client-one/.claude/skills-local/`. Client-only skills stay outside the shared symlink and are never touched by root edits.

### Managing Skills

You can ask Claude to list, add, or remove skills — or use these commands from the root folder:

```bash
bash scripts/list-skills.sh              # See what's installed
bash scripts/add-skill.sh skill-name     # Add a skill
bash scripts/remove-skill.sh skill-name  # Remove a skill
```

Every client folder picks up the change instantly on Unix (via the symlink). On Windows, re-run `add-client.sh` against the client to refresh.

---

## Scenario 1: Solo Researcher

```
~/Projects/organon/
├── CLAUDE.md
├── context/
│   ├── SOUL.md
│   ├── USER.md
│   ├── learnings.md              <- your accumulated learnings
│   └── memory/                   <- your session history
├── research_context/
├── .claude/skills/
├── projects/
├── cron/jobs/
└── .env
```

**This is the default. You're already here.** You work directly in the root folder. No clients/ directory needed. Everything in this guide is optional until you need a second client.

---

## Scenario 2: Multiple Clients

One Organon installation. One folder per research group/lab. You `cd` into a client folder and open Claude Code there.

```
~/Projects/organon/                         <- your single installation
├── CLAUDE.md                                  <- shared methodology (auto-inherited)
├── context/
│   ├── SOUL.md                                <- shared personality (auto-inherited)
│   ├── USER.md                                <- shared operator profile (auto-inherited)
│   ├── learnings.md                           <- system-wide learnings (non-client work)
│   └── memory/                                <- system-wide session history
├── .claude/skills/                            <- master copy of all skills
├── scripts/                                   <- master copy of all scripts
│
├── clients/
│   ├── client-one/                            <- you work HERE
│   │   ├── CLAUDE.md                          <- client-specific instructions
│   │   ├── .claude/skills/                    <- copied from root, auto-synced
│   │   ├── scripts/                           <- copied from root, auto-synced
│   │   ├── research_context/                  <- Research profile and preferences
│   │   ├── context/
│   │   │   ├── learnings.md                   <- Client One feedback (seeded from root)
│   │   │   └── memory/                        <- Client One session history
│   │   ├── projects/                          <- Client One deliverables
│   │   ├── cron/
│   │   │   ├── jobs/                          <- Client One scheduled tasks
│   │   │   ├── logs/
│   │   │   └── status/
│   │   └── .env                               <- API keys
│   │
│   └── client-two/                            <- same structure
│       └── ...
```

### Adding a New Client

```bash
cd ~/Projects/organon
bash scripts/add-client.sh "Client One"
```

This creates `clients/client-one/` with:
- Skills and scripts copied from root
- Learnings seeded from your root `context/learnings.md` (so the client starts with your accumulated knowledge, then diverges)
- Empty research_context/, projects/, memory/ directories
- A starter CLAUDE.md for client-specific instructions
- A copy of your .env (if one exists at the root)

Then start working:

```bash
cd clients/client-one
claude
```

Claude automatically detects it's a new client and walks you through building the research profile. The heartbeat picks up SOUL.md and USER.md from the root, loads the client's research context and memory, and you're ready to go.

### What Claude Sees When You Open a Client Folder

When you `cd clients/client-one && claude`:

1. **CLAUDE.md (root)** — loaded automatically via parent directory inheritance. All methodology, skill registry, heartbeat rules, context matrix.
2. **CLAUDE.md (client)** — loaded from the client folder. Client-specific instructions layered on top.
3. **context/SOUL.md** — the heartbeat reads this from the root (two directories up). Shared personality.
4. **context/USER.md** — same as SOUL.md, read from root. Your operator profile.
5. **research_context/** — read from the client folder. This client's research profile.
6. **context/memory/** — read from the client folder. This client's session history.
7. **context/learnings.md** — read from the client folder. This client's accumulated feedback.
8. **.claude/skills/** — loaded from the client folder. Skills are identical across clients but must exist locally for Claude Code to discover them.

### The Client CLAUDE.md

Each client gets its own `CLAUDE.md`. This is where you put client-specific instructions that go beyond brand context. It layers on top of the root methodology — it doesn't replace it.

Examples of what goes here:

```markdown
# Client: Client One

## Client-Specific Instructions
- This client prefers formal British English
- Always include regulatory disclaimers on financial content
- Their approval process requires draft -> review -> final versions
- Primary contact: Sarah (Marketing Director)

## Active Campaigns
- Q1 product launch — landing page + email sequence
- LinkedIn thought leadership series (weekly)
```

Leave it minimal or fill it out — either way, the root CLAUDE.md provides all the methodology.

### Updating

```bash
cd ~/Projects/organon
git pull origin main
bash scripts/install.sh    # re-run for any new dependencies
```

That's it. All client folders pick up the new skills and scripts instantly on Unix (via the symlinks from `add-client.sh`) — no per-client sync step. On Windows, re-run `add-client.sh` against each client to refresh their copies. Client data (`research_context/`, `context/memory/`, `context/learnings.md`, `projects/`) is gitignored and is never touched by a pull.

### Sharing API Keys

If all clients use the same API keys, just copy your `.env`:

```bash
cp .env clients/client-two/.env
```

The `add-client.sh` script does this automatically when creating a new client (if a root `.env` exists).

### Cron Across Clients

Each client can have its own cron dispatcher. The dispatcher name is derived from the folder path, so they don't conflict:

```bash
cd clients/client-one && bash scripts/install-crons.sh
cd clients/client-two && bash scripts/install-crons.sh
```

Manage all dispatchers:

```bash
# Install all
for dir in clients/*/; do (cd "$dir" && bash scripts/install-crons.sh); done

# Uninstall all
for dir in clients/*/; do (cd "$dir" && bash scripts/uninstall-crons.sh); done
```

---

## Scenario 3: One Lab, Multiple Workstreams

One folder, multiple Claude Code windows open at the same time.

```
~/Projects/organon/
├── research_context/               <- one lab
├── context/memory/                 <- captures all sessions
└── projects/
    ├── sci-writing/                <- Window 1: manuscript drafting
    ├── sci-data-analysis/          <- Window 2: data analysis
    └── sci-literature-research/    <- Window 3: literature review
```

### When This Works

- Same lab, different tasks running in parallel
- Writing in one window, data analysis in another, literature review in a third
- `projects/` already separates output by category prefix — no collisions
- Memory files capture multiple sessions per day (`## Session 1`, `## Session 2`, etc.)

### When to Use Multi-Client Instead

- Genuinely different research groups or collaborations
- Work where you need clean separation between projects
- Different data handling requirements per group

---

## Session Management

### Where You Work

| Scenario | Working directory | How to start |
|----------|------------------|-------------|
| Solo / one business | `~/Projects/organon/` | `cd ~/Projects/organon && claude` |
| Multi-client | `~/Projects/organon/clients/client-one/` | `cd ~/Projects/organon/clients/client-one && claude` |

You always `cd` into the folder you're working in, then run `claude`. Everything else is picked up automatically.

### Key Commands

| Command | What it does | When to use |
|---------|-------------|-------------|
| **Onboarding** | Builds research profile | Runs automatically on first session per client |
| **Wrap-up** | Finalizes session block in memory, captures learnings | Runs automatically when you signal you're done |
| **/clear** | Resets Claude's context without saving | When you want a fresh start (end session first) |

### Switching Between Clients

```bash
# In your current Claude window: say "done" or "that's it" — wrap-up runs automatically

# Open a new terminal window
cd ~/Projects/organon/clients/client-two
claude
```

Each window is fully isolated. Different research context, different memory, different output. No bleed between clients.

---

## Projects

For how projects work within a workspace (single tasks, planned projects, GSD projects), see [docs/projects-guide.md](projects-guide.md).

The project system works the same whether you're in the root folder or a client folder — all paths are relative to your working directory.

---

## FAQ

**Can I share learnings across clients?**
Not automatically. Each client's `context/learnings.md` accumulates feedback tuned to that research group. When you create a new client, it starts with a copy of your root learnings so you don't lose general knowledge — but from there it diverges.

**Can I share skills across clients?**
Already handled. Skills live in the root `.claude/skills/` as the master copy. Each client folder holds a symlink back to it (Unix), so they all see the same skills automatically.

**What if I want to customize a shared skill?**
Edit it at the root level — the change is visible instantly in every client (Unix symlink) or on the next `add-client.sh` refresh (Windows).

**What if I need a skill for just one client?**
Put it in a separate folder alongside the symlinked `.claude/skills/`, for example `clients/client-one/.claude/skills-local/`. Anything outside the shared symlink stays client-scoped and is never touched by root edits.

**Do I need separate API keys per client?**
Usually no — the same Firecrawl, OpenAI, or YouTube key works across all clients. Copy the same `.env` file. Only separate them if a client has their own API accounts.

**What if I edit CLAUDE.md at the root?**
All clients see the change immediately on their next session — parent CLAUDE.md inheritance is automatic. No syncing needed.

**What if I edit SOUL.md or USER.md?**
Edit at the root. All clients pick it up automatically — the heartbeat reads these from the root directory. If you want a different personality for one client, put a `context/SOUL.md` in that client's folder and the heartbeat will use the local copy instead.

**Where does the global `~/.claude/` fit in?**
That's Claude Code's own configuration — model defaults, plugins, MCP servers. Organon lives entirely at the project level. The global config is separate and shared across all your Claude Code usage.

**Can I go back to single-client mode?**
Yes. Just work from the root folder. The `clients/` directory doesn't interfere with solo use — both modes coexist.

**How many clients can I run?**
As many as you want. Each client folder is lightweight — skills and scripts are small files, and client data (research context, memory, output) grows modestly over time. The limiting factor is your Claude plan credits, not disk space.
