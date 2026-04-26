#!/usr/bin/env bash
# Organon — reset to clean state
#
# Wipes all user-layer data (.env, research_context/, context/memory/,
# projects/, research_artifacts/, cron logs, installer state, etc.) and
# reverts tracked files (context/USER.md, context/learnings.md, CLAUDE.md
# Developer Profile, .planning/, cron/jobs/) to HEAD. The next /lets-go
# session starts in First-Run mode.
#
# Usage:
#   bash scripts/reset-to-clean.sh            # interactive (prompts for confirmation)
#   bash scripts/reset-to-clean.sh --yes      # skip confirmation
#   bash scripts/reset-to-clean.sh --dry-run  # show what would be deleted, don't delete
#   bash scripts/reset-to-clean.sh --nuke     # also wipe ~/.claude/ auto-memory for this repo

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_DIR"

# --- Safety check: verify we're in the Organon repo ---
if [[ ! -f "CLAUDE.md" ]] || [[ ! -f "context/SOUL.md" ]] || [[ ! -d ".claude/skills/sci-research-profile" ]]; then
  echo "ERROR: This doesn't look like the Organon repo."
  echo "  Expected: CLAUDE.md, context/SOUL.md, .claude/skills/sci-research-profile/"
  echo "  Current:  $REPO_DIR"
  exit 1
fi

# --- Parse args ---
DRY_RUN=false
SKIP_CONFIRM=false
NUKE_CLAUDE_MEMORY=false
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    --yes|-y) SKIP_CONFIRM=true ;;
    --nuke) NUKE_CLAUDE_MEMORY=true ;;
    -h|--help)
      head -15 "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Unknown arg: $arg"
      echo "Run with --help for usage."
      exit 1
      ;;
  esac
done

echo "========================================"
echo "Organon — reset to clean state"
echo "========================================"
echo "Repo: $REPO_DIR"
echo ""

# --- Show what will be deleted (git clean dry-run, excluding .venv) ---
# We preserve .venv/ because it holds Python deps that are expensive to
# reinstall and contain no user data. Every other gitignored file is user
# data and should be wiped.
echo "Files that will be deleted by 'git clean -fdX' (gitignored user data):"
echo "----------------------------------------"
GITCLEAN_PREVIEW=$(git clean -fdXn 2>&1 | grep -v -E '(\.venv|node_modules)' || true)
if [[ -z "$GITCLEAN_PREVIEW" ]]; then
  echo "  (nothing — no gitignored files to remove)"
else
  echo "$GITCLEAN_PREVIEW" | sed 's/^/  /'
fi
echo ""
echo "Preserved (not deleted):"
echo "  .venv/            (Python deps, expensive to reinstall)"
echo "  node_modules/     (if present — GSD CLI deps)"
echo ""

# --- Check for modified tracked files ---
MODIFIED=$(git status --porcelain 2>&1 | grep -E '^( M|M |A |AM)' || true)
if [[ -n "$MODIFIED" ]]; then
  echo "WARNING: you have uncommitted changes to tracked files:"
  echo "$MODIFIED" | sed 's/^/  /'
  echo ""
  echo "These will be REVERTED to HEAD by 'git reset --hard HEAD'."
  echo ""
fi

# --- Check for launchd watchdog ---
PLIST_PATH="$HOME/Library/LaunchAgents/com.organon.watchdog.plist"
WATCHDOG_INSTALLED=false
if [[ -f "$PLIST_PATH" ]]; then
  WATCHDOG_INSTALLED=true
  echo "Detected: Organon watchdog is installed at"
  echo "  $PLIST_PATH"
  echo "It will be UNINSTALLED (daemon stopped and plist removed)."
  echo ""
fi

# --- Check for ~/.claude/ auto-memory ---
CLAUDE_MEMORY_DIR="$HOME/.claude/projects"
CLAUDE_REPO_MEMORY=""
if [[ -d "$CLAUDE_MEMORY_DIR" ]]; then
  for candidate in "$CLAUDE_MEMORY_DIR"/*scientific-os*; do
    if [[ -d "$candidate" ]]; then
      CLAUDE_REPO_MEMORY="$candidate"
      break
    fi
  done
fi
if [[ -n "$CLAUDE_REPO_MEMORY" ]]; then
  if [[ "$NUKE_CLAUDE_MEMORY" == "true" ]]; then
    echo "Detected: Claude Code auto-memory for this repo at"
    echo "  $CLAUDE_REPO_MEMORY"
    echo "It will be BACKED UP to ${CLAUDE_REPO_MEMORY}.backup-$(date +%Y%m%d-%H%M%S)"
    echo "(--nuke flag set, so cross-session memory will be wiped)"
    echo ""
  else
    echo "Note: Claude Code auto-memory for this repo exists at"
    echo "  $CLAUDE_REPO_MEMORY"
    echo "Leaving it untouched. Pass --nuke to also wipe it (backs up first)."
    echo ""
  fi
fi

# --- Dry run mode: stop here ---
if [[ "$DRY_RUN" == "true" ]]; then
  echo "========================================"
  echo "DRY RUN — nothing deleted."
  echo "========================================"
  exit 0
fi

# --- Confirmation ---
if [[ "$SKIP_CONFIRM" != "true" ]]; then
  echo "========================================"
  echo "This is DESTRUCTIVE. Type 'reset' to proceed, anything else to abort."
  echo "========================================"
  read -r -p "> " REPLY
  if [[ "$REPLY" != "reset" ]]; then
    echo "Aborted."
    exit 0
  fi
  echo ""
fi

# --- Execute ---
echo "Resetting..."

# 1. Uninstall watchdog if present (before wiping files)
if [[ "$WATCHDOG_INSTALLED" == "true" ]]; then
  echo "  - Uninstalling watchdog daemon..."
  if bash "$REPO_DIR/scripts/uninstall-watchdog.sh" >/dev/null 2>&1; then
    echo "    ok"
  else
    echo "    WARNING: uninstall script failed, removing plist manually"
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    rm -f "$PLIST_PATH"
  fi
fi

# 2. Reset tracked files to HEAD (reverts USER.md, learnings.md, CLAUDE.md
#    Developer Profile, .planning/, cron/jobs/ to committed templates)
echo "  - Resetting tracked files to HEAD (git reset --hard HEAD)..."
git reset --hard HEAD >/dev/null

# 3. Temporarily stash .venv and node_modules (git clean -X can't exclude in -X mode)
VENV_BACKUP=""
if [[ -d ".venv" ]]; then
  VENV_BACKUP="/tmp/organon-venv-$$"
  echo "  - Preserving .venv -> $VENV_BACKUP ..."
  mv .venv "$VENV_BACKUP"
fi
NODE_MODULES_BACKUP=""
if [[ -d "node_modules" ]]; then
  NODE_MODULES_BACKUP="/tmp/organon-node-modules-$$"
  echo "  - Preserving node_modules -> $NODE_MODULES_BACKUP ..."
  mv node_modules "$NODE_MODULES_BACKUP"
fi

# 4. Remove all gitignored files and directories
echo "  - Removing gitignored user data (git clean -fdX)..."
git clean -fdX >/dev/null

# 5. Restore preserved directories
if [[ -n "$VENV_BACKUP" ]] && [[ -d "$VENV_BACKUP" ]]; then
  echo "  - Restoring .venv..."
  mv "$VENV_BACKUP" .venv
fi
if [[ -n "$NODE_MODULES_BACKUP" ]] && [[ -d "$NODE_MODULES_BACKUP" ]]; then
  echo "  - Restoring node_modules..."
  mv "$NODE_MODULES_BACKUP" node_modules
fi

# 6. Optionally back up Claude Code auto-memory
if [[ "$NUKE_CLAUDE_MEMORY" == "true" ]] && [[ -n "$CLAUDE_REPO_MEMORY" ]]; then
  BACKUP="${CLAUDE_REPO_MEMORY}.backup-$(date +%Y%m%d-%H%M%S)"
  echo "  - Backing up Claude auto-memory to $BACKUP..."
  mv "$CLAUDE_REPO_MEMORY" "$BACKUP"
fi

# --- Post-reset verification ---
echo ""
echo "Verifying clean state..."

PROBLEMS=0

check_gone() {
  local path="$1"
  local label="$2"
  if [[ -e "$path" ]]; then
    echo "  WARN: $label still exists at $path"
    PROBLEMS=$((PROBLEMS + 1))
  fi
}

check_gone ".env" ".env"
check_gone ".mcp.json" ".mcp.json"
check_gone "research_artifacts" "research_artifacts/"
check_gone ".claude/skills/_catalog/installed.json" "installed.json"

# research_context/*.md and context/memory/*.md and projects/* should be empty
LEFTOVER_RC=$(find research_context -maxdepth 1 -name '*.md' 2>/dev/null || true)
if [[ -n "$LEFTOVER_RC" ]]; then
  echo "  WARN: research_context/ still has .md files:"
  echo "$LEFTOVER_RC" | sed 's/^/    /'
  PROBLEMS=$((PROBLEMS + 1))
fi
LEFTOVER_MEM=$(find context/memory -maxdepth 1 -name '*.md' 2>/dev/null || true)
if [[ -n "$LEFTOVER_MEM" ]]; then
  echo "  WARN: context/memory/ still has .md files:"
  echo "$LEFTOVER_MEM" | sed 's/^/    /'
  PROBLEMS=$((PROBLEMS + 1))
fi
LEFTOVER_PROJ=$(find projects -mindepth 1 -maxdepth 1 ! -name '.gitkeep' 2>/dev/null || true)
if [[ -n "$LEFTOVER_PROJ" ]]; then
  echo "  WARN: projects/ still has entries:"
  echo "$LEFTOVER_PROJ" | sed 's/^/    /'
  PROBLEMS=$((PROBLEMS + 1))
fi

# Check git tree is clean
TREE_STATE=$(git status --porcelain)
if [[ -n "$TREE_STATE" ]]; then
  echo "  WARN: git tree not clean:"
  echo "$TREE_STATE" | sed 's/^/    /'
  PROBLEMS=$((PROBLEMS + 1))
fi

# Check HEAD matches upstream (informational only)
LOCAL_HEAD=$(git rev-parse HEAD)
UPSTREAM_HEAD=$(git rev-parse '@{u}' 2>/dev/null || echo "no-upstream")
if [[ "$UPSTREAM_HEAD" != "no-upstream" ]] && [[ "$LOCAL_HEAD" != "$UPSTREAM_HEAD" ]]; then
  echo "  NOTE: HEAD ($LOCAL_HEAD) differs from upstream ($UPSTREAM_HEAD)."
  echo "        Not a problem for the reset — just FYI."
fi

echo ""
if [[ "$PROBLEMS" -eq 0 ]]; then
  echo "========================================"
  echo "DONE. Clean state verified."
  echo "========================================"
  echo ""
  echo "Next steps:"
  echo "  1. (Optional) Pull latest framework changes from upstream:"
  echo "       git fetch origin              # see what's new"
  echo "       git pull origin main          # apply updates"
  echo "       bash scripts/install.sh       # re-run setup for any new deps"
  echo "  2. Close this terminal session (or type 'exit' if you're in Claude Code)"
  echo "  3. Open a fresh Claude Code session:  cd $REPO_DIR && claude"
  echo "  4. Your first message: /lets-go"
  echo ""
else
  echo "========================================"
  echo "DONE with $PROBLEMS warning(s). Check above."
  echo "========================================"
  exit 1
fi
