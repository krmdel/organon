#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Organon — Smart Update
# =============================================================================
# Check for updates, pull safely, and never overwrite user data.
#
# Usage:
#   bash scripts/update.sh              # check + update interactively
#   bash scripts/update.sh --check      # only check, don't update
#   bash scripts/update.sh --yes        # update without prompting
#
# User data files are backed up before pull and restored after, so your
# learnings, profile, research notes, and cron state survive every update.
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

# --- Safety check ---
if [[ ! -f "CLAUDE.md" ]] || [[ ! -f "context/SOUL.md" ]]; then
  echo "ERROR: This doesn't look like the Organon repo."
  exit 1
fi

# --- Parse args ---
CHECK_ONLY=false
SKIP_CONFIRM=false
for arg in "$@"; do
  case "$arg" in
    --check) CHECK_ONLY=true ;;
    --yes|-y) SKIP_CONFIRM=true ;;
    -h|--help)
      head -12 "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Unknown arg: $arg — run with --help"
      exit 1
      ;;
  esac
done

# --- User data files to protect ---
# These are tracked files that contain user-specific data accumulated over time.
# Gitignored files (.env, context/memory/*, projects/*, research_context/*.md)
# are already safe — git pull never touches them.
USER_DATA_FILES=(
  "context/USER.md"
  "context/learnings.md"
  "cron/status/dispatcher.json"
  "cron/watchdog.state.json"
)

# User data directories: protect all contents (notes, experiments, etc.)
USER_DATA_DIRS=(
  "research/notes"
  "research/experiments"
  "research/projects"
)

# --- Fetch latest ---
echo "Checking for updates..."
git fetch origin 2>/dev/null

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main 2>/dev/null || echo "")

if [[ -z "$REMOTE" ]]; then
  echo "Could not reach origin/main. Check your network connection."
  exit 1
fi

if [[ "$LOCAL" == "$REMOTE" ]]; then
  echo "Already up to date."
  exit 0
fi

# --- Show what's new ---
BEHIND=$(git rev-list --count HEAD..origin/main)
AHEAD=$(git rev-list --count origin/main..HEAD)

echo ""
echo "Updates available:"
echo "  $BEHIND new commit(s) from upstream"
if [[ "$AHEAD" -gt 0 ]]; then
  echo "  $AHEAD local commit(s) ahead of upstream"
fi
echo ""

echo "Changes in this update:"
echo "----------------------------------------"
# Show changed files, grouped by type
CHANGED_FILES=$(git diff --name-only HEAD..origin/main 2>/dev/null || true)
if [[ -n "$CHANGED_FILES" ]]; then
  SKILLS_CHANGED=$(echo "$CHANGED_FILES" | grep "^\.claude/skills/" | wc -l | tr -d ' ')
  SCRIPTS_CHANGED=$(echo "$CHANGED_FILES" | grep "^scripts/" | wc -l | tr -d ' ')
  TESTS_CHANGED=$(echo "$CHANGED_FILES" | grep "^tests/" | wc -l | tr -d ' ')
  MCP_CHANGED=$(echo "$CHANGED_FILES" | grep "^mcp-servers/" | wc -l | tr -d ' ')
  DOCS_CHANGED=$(echo "$CHANGED_FILES" | grep -E "^(docs/|README\.md|CLAUDE\.md)" | wc -l | tr -d ' ')
  OTHER_CHANGED=$(echo "$CHANGED_FILES" | grep -v -E "^(\.claude/skills/|scripts/|tests/|mcp-servers/|docs/|README\.md|CLAUDE\.md)" | wc -l | tr -d ' ')

  [[ "$SKILLS_CHANGED" -gt 0 ]] && echo "  Skills:      $SKILLS_CHANGED file(s)"
  [[ "$SCRIPTS_CHANGED" -gt 0 ]] && echo "  Scripts:     $SCRIPTS_CHANGED file(s)"
  [[ "$TESTS_CHANGED" -gt 0 ]] && echo "  Tests:       $TESTS_CHANGED file(s)"
  [[ "$MCP_CHANGED" -gt 0 ]] && echo "  MCP servers: $MCP_CHANGED file(s)"
  [[ "$DOCS_CHANGED" -gt 0 ]] && echo "  Docs:        $DOCS_CHANGED file(s)"
  [[ "$OTHER_CHANGED" -gt 0 ]] && echo "  Other:       $OTHER_CHANGED file(s)"
fi
echo "----------------------------------------"

# --- Check-only mode ---
if [[ "$CHECK_ONLY" == "true" ]]; then
  echo ""
  echo "Run 'bash scripts/update.sh' to apply this update."
  exit 0
fi

# --- Confirmation ---
if [[ "$SKIP_CONFIRM" != "true" ]]; then
  echo ""
  echo "Your data is safe — USER.md, learnings.md, research notes, and"
  echo "cron state will be backed up and restored automatically."
  echo ""
  read -r -p "Apply update? [y/N] " REPLY
  if [[ ! "$REPLY" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
  fi
fi

# --- Backup user data ---
BACKUP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/organon-update-XXXXXX")
echo ""
echo "Backing up user data to $BACKUP_DIR ..."

BACKED_UP=0
for f in "${USER_DATA_FILES[@]}"; do
  if [[ -f "$f" ]]; then
    mkdir -p "$BACKUP_DIR/$(dirname "$f")"
    cp "$f" "$BACKUP_DIR/$f"
    BACKED_UP=$((BACKED_UP + 1))
  fi
done

for d in "${USER_DATA_DIRS[@]}"; do
  if [[ -d "$d" ]]; then
    FILE_COUNT=$(find "$d" -type f ! -name '.gitkeep' 2>/dev/null | wc -l | tr -d ' ')
    if [[ "$FILE_COUNT" -gt 0 ]]; then
      mkdir -p "$BACKUP_DIR/$d"
      cp -r "$d"/* "$BACKUP_DIR/$d/" 2>/dev/null || true
      BACKED_UP=$((BACKED_UP + FILE_COUNT))
    fi
  fi
done

echo "  $BACKED_UP file(s) backed up"

# --- Check for local modifications to framework files ---
# If user modified tracked framework files (not user data), warn them
DIRTY_FRAMEWORK=$(git diff --name-only 2>/dev/null | grep -v -E "^(context/USER\.md|context/learnings\.md|cron/status/|cron/watchdog\.state\.json|research/notes/|research/experiments/|research/projects/)" || true)
if [[ -n "$DIRTY_FRAMEWORK" ]]; then
  echo ""
  echo "WARNING: You have local changes to framework files:"
  echo "$DIRTY_FRAMEWORK" | sed 's/^/  /'
  echo ""
  echo "These will be stashed (git stash) and can be re-applied after update."
  echo "To re-apply: git stash pop"
  git stash push -m "organon-update-$(date +%Y%m%d-%H%M%S)" -- $(echo "$DIRTY_FRAMEWORK") 2>/dev/null || true
fi

# --- Pull ---
echo ""
echo "Pulling updates..."

# Temporarily reset user data files to HEAD so merge doesn't conflict
for f in "${USER_DATA_FILES[@]}"; do
  if [[ -f "$f" ]]; then
    git checkout HEAD -- "$f" 2>/dev/null || true
  fi
done

if git merge origin/main --no-edit 2>&1; then
  echo "  Merge successful"
else
  echo ""
  echo "ERROR: Merge conflict. Your backup is safe at $BACKUP_DIR"
  echo "Resolve conflicts, then restore your data:"
  echo "  cp $BACKUP_DIR/context/USER.md context/USER.md"
  echo "  cp $BACKUP_DIR/context/learnings.md context/learnings.md"
  exit 1
fi

# --- Restore user data ---
echo ""
echo "Restoring user data..."

for f in "${USER_DATA_FILES[@]}"; do
  if [[ -f "$BACKUP_DIR/$f" ]]; then
    cp "$BACKUP_DIR/$f" "$f"
    echo "  Restored $f"
  fi
done

for d in "${USER_DATA_DIRS[@]}"; do
  if [[ -d "$BACKUP_DIR/$d" ]]; then
    mkdir -p "$d"
    cp -r "$BACKUP_DIR/$d"/* "$d/" 2>/dev/null || true
    RESTORED_COUNT=$(find "$BACKUP_DIR/$d" -type f ! -name '.gitkeep' 2>/dev/null | wc -l | tr -d ' ')
    echo "  Restored $d/ ($RESTORED_COUNT files)"
  fi
done

# --- Post-update tasks ---
echo ""
echo "Running post-update checks..."

# Check if new skills appeared
NEW_SKILLS=$(python3 scripts/reconcile.py 2>&1 || true)
if echo "$NEW_SKILLS" | grep -q "New on disk"; then
  echo "  New skills detected — run reconciliation in your next Claude session"
fi

# Check if install.sh needs re-running (new deps)
INSTALL_CHANGED=$(git diff --name-only "$LOCAL"..HEAD -- scripts/install.sh scripts/setup.sh scripts/setup-science.sh 2>/dev/null || true)
if [[ -n "$INSTALL_CHANGED" ]]; then
  echo ""
  echo "  The installer was updated. Run this to pick up new dependencies:"
  echo "    bash scripts/install.sh"
fi

# Check if MCP server source changed (needs rebuild)
MCP_SRC_CHANGED=$(git diff --name-only "$LOCAL"..HEAD -- mcp-servers/ 2>/dev/null | grep '\.ts$' || true)
if [[ -n "$MCP_SRC_CHANGED" ]]; then
  echo ""
  echo "  MCP server source changed. Rebuilding..."
  (cd mcp-servers/paper-search && npm run build 2>/dev/null) && echo "    paper-search rebuilt" || echo "    WARNING: rebuild failed — run 'cd mcp-servers/paper-search && npm run build' manually"
fi

# --- Done ---
echo ""
echo "========================================"
echo "Update complete!"
echo "========================================"
echo ""
echo "Your data was preserved:"
echo "  context/USER.md        — your profile"
echo "  context/learnings.md   — accumulated feedback"
echo "  research/              — notes, experiments, projects"
echo "  cron state             — dispatcher + watchdog"
echo ""
echo "Backup saved at: $BACKUP_DIR"
echo "  (safe to delete once you've verified everything works)"
