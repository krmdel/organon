#!/usr/bin/env bash
# Create a new client workspace under clients/.
# Usage: bash scripts/add-client.sh "Client Name"

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [[ $# -lt 1 ]]; then
  echo "Usage: bash scripts/add-client.sh \"Client Name\""
  echo ""
  echo "Creates a client workspace under clients/ with skills, scripts,"
  echo "and empty directories for brand context, memory, and projects."
  exit 1
fi

CLIENT_NAME="$1"

# Convert to slug: lowercase, spaces to hyphens, strip non-alphanumeric
CLIENT_SLUG=$(echo "$CLIENT_NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-')

CLIENT_DIR="${PROJECT_DIR}/clients/${CLIENT_SLUG}"

if [[ -d "$CLIENT_DIR" ]]; then
  echo "Error: Client folder already exists: clients/${CLIENT_SLUG}/"
  echo "To start over, remove it first and re-run this script."
  exit 1
fi

echo "Creating client workspace: clients/${CLIENT_SLUG}/"

# Create directory structure
mkdir -p "${CLIENT_DIR}/research_context"
mkdir -p "${CLIENT_DIR}/context/memory"
mkdir -p "${CLIENT_DIR}/projects"
mkdir -p "${CLIENT_DIR}/cron/jobs"
mkdir -p "${CLIENT_DIR}/cron/logs"
mkdir -p "${CLIENT_DIR}/cron/status"
mkdir -p "${CLIENT_DIR}/cron/templates"

# Link skills from root so edits to the shared methodology propagate
# automatically (per CLAUDE.md Multi-Client Architecture). Symlink on
# Unix; fall back to copy on Windows (mklink requires admin / different
# syntax) and warn the user to re-sync after root updates.
if [[ -d "${PROJECT_DIR}/.claude/skills" ]]; then
  mkdir -p "${CLIENT_DIR}/.claude"
  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*)
      cp -R "${PROJECT_DIR}/.claude/skills" "${CLIENT_DIR}/.claude/skills"
      echo "  Copied skills (Windows — re-run add-client or copy manually after root updates)"
      ;;
    *)
      ( cd "${CLIENT_DIR}/.claude" && ln -sf "../../../.claude/skills" skills )
      echo "  Linked skills → ../../../.claude/skills (inherited from root)"
      ;;
  esac
fi

# Copy Claude Code settings if they exist
if [[ -f "${PROJECT_DIR}/.claude/settings.json" ]]; then
  cp "${PROJECT_DIR}/.claude/settings.json" "${CLIENT_DIR}/.claude/settings.json"
  echo "  Copied Claude Code settings"
fi

# Copy hooks_info if it exists (required by hooks in settings.json)
if [[ -d "${PROJECT_DIR}/.claude/hooks_info" ]]; then
  cp -R "${PROJECT_DIR}/.claude/hooks_info" "${CLIENT_DIR}/.claude/hooks_info"
  echo "  Copied hooks_info"
fi

# Copy scripts from root
cp -R "${PROJECT_DIR}/scripts" "${CLIENT_DIR}/scripts"
echo "  Copied scripts"

# Copy cron templates if they exist
if [[ -d "${PROJECT_DIR}/cron/templates" ]]; then
  cp -R "${PROJECT_DIR}/cron/templates/." "${CLIENT_DIR}/cron/templates/"
  echo "  Copied cron templates"
fi

# Create client-specific CLAUDE.md
cat > "${CLIENT_DIR}/CLAUDE.md" <<CLAUDE
# Client: ${CLIENT_NAME}

Add client-specific instructions here. These layer on top of the root CLAUDE.md methodology — they don't replace it.

## Client-Specific Instructions

-

## Notes

-
CLAUDE
echo "  Created client CLAUDE.md"

# Seed learnings from root (so clients start with accumulated knowledge)
if [[ -f "${PROJECT_DIR}/context/learnings.md" ]]; then
  cp "${PROJECT_DIR}/context/learnings.md" "${CLIENT_DIR}/context/learnings.md"
  echo "  Seeded learnings.md from root (will diverge per-client from here)"
else
  cat > "${CLIENT_DIR}/context/learnings.md" <<LEARNINGS
# Learnings

## General

### What works well

### What doesn't work well

## Individual Skills
LEARNINGS
  echo "  Created learnings.md"
fi

# Inherit SOUL.md via symlink (per CLAUDE.md Multi-Client Architecture).
# Edits to the root SOUL.md propagate to all clients automatically.
# Use a relative symlink so the client workspace is portable if the
# enclosing repo path changes.
if [[ -f "${PROJECT_DIR}/context/SOUL.md" ]]; then
  ( cd "${CLIENT_DIR}/context" && ln -sf "../../../context/SOUL.md" SOUL.md )
  echo "  Linked SOUL.md → ../../../context/SOUL.md (inherited from root)"
else
  echo "  Warning: root context/SOUL.md missing — client SOUL.md not linked"
fi

# Fresh USER.md template — clients start blank and /lets-go populates it.
if [[ -f "${PROJECT_DIR}/context/USER.md" ]]; then
  cp "${PROJECT_DIR}/context/USER.md" "${CLIENT_DIR}/context/USER.md"
  echo "  Copied USER.md template (client will fill it on first /lets-go)"
fi

# Create .gitkeep files to preserve empty directories
touch "${CLIENT_DIR}/research_context/.gitkeep"
touch "${CLIENT_DIR}/context/memory/.gitkeep"
touch "${CLIENT_DIR}/projects/.gitkeep"
touch "${CLIENT_DIR}/cron/jobs/.gitkeep"

# Copy .env if one exists at root
if [[ -f "${PROJECT_DIR}/.env" ]]; then
  cp "${PROJECT_DIR}/.env" "${CLIENT_DIR}/.env"
  echo "  Copied .env (API keys)"
fi

echo ""
echo "Client workspace ready: clients/${CLIENT_SLUG}/"
echo ""
echo "Next steps:"
echo "  cd ${PROJECT_DIR}/clients/${CLIENT_SLUG}"
echo "  claude"
echo "  Claude will automatically walk you through building the research profile."
