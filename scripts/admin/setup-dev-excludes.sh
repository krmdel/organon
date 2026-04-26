#!/usr/bin/env bash
# =============================================================================
# Setup local git excludes for development
# =============================================================================
# Run this after a fresh clone to prevent personal data from being accidentally
# committed. These rules live in .git/info/exclude (local-only, never pushed).
#
# Usage: bash scripts/admin/setup-dev-excludes.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
EXCLUDE_FILE="$REPO_ROOT/.git/info/exclude"

cat > "$EXCLUDE_FILE" << 'EXCLUDE'
# =============================================================================
# LOCAL EXCLUSIONS — dev machine only
# =============================================================================
# These files are tracked for users (they WANT their data in git) but excluded
# here so personal data never leaks to the upstream/main repo.
#
# This file lives in .git/info/exclude — it is NEVER pushed or shared.
# Re-run: bash scripts/admin/setup-dev-excludes.sh
# =============================================================================

# Personal user data (users track these — we don't)
context/USER.md
context/learnings.md
context/memory/*
research_context/

# Personal project outputs and GSD state
projects/*
!projects/.gitkeep
.planning/

# Personal cron jobs
cron/jobs/claude-code-trending.md
cron/jobs/nano-banana-trending.md
cron/jobs/test-watchdog.md

# Client workspaces (users track these — we don't)
clients/

# WIP / scratch files
scripts/test-parser.ts
docs/kanban.md
EXCLUDE

echo "✓ Local git excludes written to .git/info/exclude"
echo "  Your personal data files will not appear in git status or be staged."
