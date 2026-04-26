#!/usr/bin/env bash
# Swap the frontmatter of a Marp .md with a named template from templates/.
# Preserves the slide body; rewrites only the frontmatter block (first two `---` delimited sections).
# Re-renders PDF + PPTX + HTML.
#
# Usage:
#   apply_template.sh <template_id> <path/to/deck.md>

set -euo pipefail

TEMPLATE_ID="${1:?need template id (e.g. default, gaia, dark-academia)}"
TARGET="${2:?need path to target .md}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
TEMPLATE_FILE="$SKILL_DIR/templates/${TEMPLATE_ID}.md"

if [[ ! -f "$TEMPLATE_FILE" ]]; then
  echo "ERROR: template not found: $TEMPLATE_FILE" >&2
  echo "Available templates:" >&2
  ls "$SKILL_DIR/templates"/*.md 2>/dev/null | grep -v '/_' | xargs -I{} basename {} .md | sed 's/^/  - /' >&2
  exit 1
fi

if [[ ! -f "$TARGET" ]]; then
  echo "ERROR: target .md not found: $TARGET" >&2
  exit 1
fi

# Extract body (everything after the second `---`)
BODY=$(awk '/^---$/{c++; if(c==2){p=1; next}} p' "$TARGET")

# Rewrite with new frontmatter + body
{
  cat "$TEMPLATE_FILE"
  echo ""
  echo "$BODY"
} > "${TARGET}.new"

mv "${TARGET}.new" "$TARGET"
echo "Applied template '${TEMPLATE_ID}' to $TARGET"

# Re-render
bash "$SCRIPT_DIR/render_presentation.sh" "$TARGET" all
