#!/usr/bin/env bash
# Thin wrapper that runs substack_ops.py under `uv run` so the skill's
# dependencies resolve without touching the system Python.
#
# Usage:
#   bash .claude/skills/tool-substack/scripts/run.sh test-auth
#   bash .claude/skills/tool-substack/scripts/run.sh convert path/to/post.md
#   bash .claude/skills/tool-substack/scripts/run.sh push path/to/post.md
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPS="$SCRIPT_DIR/substack_ops.py"

exec uv run --with markdown-it-py --with requests python3 "$OPS" "$@"
