#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) REPO_ROOT="$(cygpath -m "$REPO_ROOT")" ;; esac
PYTHON_CMD="python3"; command -v python3 &>/dev/null || PYTHON_CMD="python"
CATALOG="$REPO_ROOT/.claude/skills/_catalog/catalog.json"
INSTALLED_JSON="$REPO_ROOT/.claude/skills/_catalog/installed.json"
SKILLS_DIR="$REPO_ROOT/.claude/skills"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

if [[ ! -f "$CATALOG" ]]; then
  echo -e "${RED}Error:${NC} catalog.json not found at $CATALOG" >&2
  exit 1
fi

# Validate argument
if [[ -z "${1:-}" ]]; then
  echo -e "${RED}Usage:${NC} bash scripts/remove-skill.sh <skill-name>"
  exit 1
fi

SKILL_NAME="$1"

# Defense-in-depth: strict format guard on SKILL_NAME before it ever
# reaches rm -rf. The Python catalog lookup below is the primary
# defense, but if that ever gets bypassed (edited, catalog corruption,
# etc.) we still refuse names containing slashes, dots, or anything
# outside the [a-z0-9-] skill-slug alphabet. Prevents path traversal
# like `../../../etc` from ever deleting anything outside .claude/skills/.
if [[ ! "$SKILL_NAME" =~ ^[a-z][a-z0-9-]*$ ]]; then
  echo -e "${RED}Error:${NC} invalid skill name '$SKILL_NAME'."
  echo "Skill names must match [a-z][a-z0-9-]* — lowercase letters, digits, and hyphens only."
  exit 1
fi

# Phase 1: validate and check deps, outputs action or exits
DEPENDENTS=$($PYTHON_CMD -c "
import json, sys, os

skill_name = sys.argv[1]
catalog_path = sys.argv[2]
skills_dir = sys.argv[3]

with open(catalog_path) as f:
    catalog = json.load(f)

core_skills = catalog.get('core_skills', [])
optional_skills = catalog.get('skills', {})
all_known = set(core_skills) | set(optional_skills.keys())

# Validate skill exists
if skill_name not in all_known:
    print(f'ERROR:not_found', end='')
    sys.exit(0)

# Block core skill removal
if skill_name in core_skills:
    print(f'ERROR:core', end='')
    sys.exit(0)

# Check if installed
skill_dir = os.path.join(skills_dir, skill_name)
if not os.path.isdir(skill_dir):
    print(f'ERROR:not_installed', end='')
    sys.exit(0)

# Reverse dependency check: find installed skills that depend on this one
dependents = []
for name, info in optional_skills.items():
    if name == skill_name:
        continue
    dep_dir = os.path.join(skills_dir, name)
    if not os.path.isdir(dep_dir):
        continue
    deps = info.get('dependencies', [])
    if skill_name in deps:
        dependents.append(name)

if dependents:
    print(','.join(dependents), end='')
else:
    print('OK', end='')
" "$SKILL_NAME" "$CATALOG" "$SKILLS_DIR" | tr -d '\r')

# Handle error cases
case "$DEPENDENTS" in
  ERROR:not_found)
    echo -e "${RED}Error:${NC} \"$SKILL_NAME\" is not in the catalog."
    exit 1
    ;;
  ERROR:core)
    echo -e "${RED}Error:${NC} \"$SKILL_NAME\" is a core skill and cannot be removed."
    exit 1
    ;;
  ERROR:not_installed)
    echo -e "${YELLOW}$SKILL_NAME${NC} is not currently installed."
    exit 0
    ;;
esac

# Handle dependents warning
if [[ "$DEPENDENTS" != "OK" ]]; then
  echo -e "${YELLOW}Warning:${NC} The following installed skills depend on ${CYAN}$SKILL_NAME${NC}:"
  IFS=',' read -ra DEP_LIST <<< "$DEPENDENTS"
  for dep in "${DEP_LIST[@]}"; do
    echo "  - $dep"
  done
  read -rp "Remove anyway? (y/N) " confirm
  if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
  fi
fi

# Remove the directory
rm -rf "$SKILLS_DIR/$SKILL_NAME/"
echo -e "${GREEN}✓${NC} Removed $SKILL_NAME"

# Update installed.json
$PYTHON_CMD -c "
import json, sys, os

skill_name = sys.argv[1]
installed_path = sys.argv[2]

if os.path.exists(installed_path):
    with open(installed_path) as f:
        state = json.load(f)
else:
    state = {'installed_skills': [], 'removed_skills': []}

installed = set(state.get('installed_skills', []))
removed = set(state.get('removed_skills', []))

installed.discard(skill_name)
removed.add(skill_name)

state['installed_skills'] = sorted(installed)
state['removed_skills'] = sorted(removed)

with open(installed_path, 'w') as f:
    json.dump(state, f, indent=2)
    f.write('\n')
" "$SKILL_NAME" "$INSTALLED_JSON"

echo ""
echo -e "Removed ${CYAN}$SKILL_NAME${NC}. Next Claude Code session will clean up CLAUDE.md references."
