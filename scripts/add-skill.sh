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

# --list flag: delegate to list-skills.sh
if [[ "${1:-}" == "--list" ]]; then
  bash "$REPO_ROOT/scripts/list-skills.sh"
  exit 0
fi

# Validate argument
if [[ -z "${1:-}" ]]; then
  echo -e "${RED}Usage:${NC} bash scripts/add-skill.sh <skill-name>"
  echo "       bash scripts/add-skill.sh --list"
  exit 1
fi

SKILL_NAME="$1"

# Use Python to validate, resolve deps, and do the work
$PYTHON_CMD -c "
import json, sys, os, subprocess

skill_name = sys.argv[1]
catalog_path = sys.argv[2]
installed_path = sys.argv[3]
skills_dir = sys.argv[4]
repo_root = sys.argv[5]

with open(catalog_path) as f:
    catalog = json.load(f)

core_skills = catalog.get('core_skills', [])
optional_skills = catalog.get('skills', {})
all_known = set(core_skills) | set(optional_skills.keys())

# Validate skill exists in catalog
if skill_name not in all_known:
    print(f'\033[0;31mError:\033[0m \"{skill_name}\" is not in the catalog.')
    print(f'Run: bash scripts/list-skills.sh')
    sys.exit(1)

# Block if core skill
if skill_name in core_skills:
    print(f'\033[1;33m{skill_name}\033[0m is a core skill — always installed.')
    sys.exit(0)

# Block if already installed (directory exists)
skill_dir = os.path.join(skills_dir, skill_name)
if os.path.isdir(skill_dir):
    print(f'\033[1;33m{skill_name}\033[0m is already installed.')
    sys.exit(0)

# Resolve dependencies recursively
def get_deps(name, seen=None):
    if seen is None:
        seen = set()
    if name in seen or name not in optional_skills:
        return []
    seen.add(name)
    deps = optional_skills[name].get('dependencies', [])
    result = []
    for d in deps:
        result.extend(get_deps(d, seen))
        result.append(d)
    return result

deps = get_deps(skill_name)
# Filter to only those not already on disk
to_install = []
for d in deps:
    d_dir = os.path.join(skills_dir, d)
    if not os.path.isdir(d_dir) and d not in core_skills:
        to_install.append(d)
to_install.append(skill_name)
# Deduplicate while preserving order
seen = set()
unique_install = []
for s in to_install:
    if s not in seen:
        seen.add(s)
        unique_install.append(s)

# Restore each from git
for name in unique_install:
    path = f'.claude/skills/{name}/'
    result = subprocess.run(
        ['git', 'checkout', 'HEAD', '--', path],
        cwd=repo_root,
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f'\033[0;31mError:\033[0m Failed to restore {name} from git.')
        print(result.stderr.strip())
        sys.exit(1)
    tag = ' (dependency)' if name != skill_name else ''
    print(f'\033[0;32m✓\033[0m Restored {name}{tag}')

# Update installed.json
if os.path.exists(installed_path):
    with open(installed_path) as f:
        state = json.load(f)
else:
    state = {'installed_skills': [], 'removed_skills': []}

installed_set = set(state.get('installed_skills', []))
removed_set = set(state.get('removed_skills', []))

for name in unique_install:
    installed_set.add(name)
    removed_set.discard(name)

state['installed_skills'] = sorted(installed_set)
state['removed_skills'] = sorted(removed_set)

with open(installed_path, 'w') as f:
    json.dump(state, f, indent=2)
    f.write('\n')

print()
print(f'\033[0;32mInstalled {skill_name}.\033[0m Start a new Claude Code session — it will auto-register.')

# Remind about required services
info = optional_skills.get(skill_name, {})
services = info.get('requires_services', [])
if services:
    print()
    print(f'\033[1;33mNote:\033[0m {skill_name} uses external services. Add these to your .env:')
    for svc in services:
        print(f'  • {svc}')
" "$SKILL_NAME" "$CATALOG" "$INSTALLED_JSON" "$SKILLS_DIR" "$REPO_ROOT"
