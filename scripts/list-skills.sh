#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) REPO_ROOT="$(cygpath -m "$REPO_ROOT")" ;; esac
PYTHON_CMD="python3"; command -v python3 &>/dev/null || PYTHON_CMD="python"
CATALOG="$REPO_ROOT/.claude/skills/_catalog/catalog.json"
SKILLS_DIR="$REPO_ROOT/.claude/skills"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

if [[ ! -f "$CATALOG" ]]; then
  echo "Error: catalog.json not found at $CATALOG" >&2
  exit 1
fi

echo ""
echo -e "${CYAN}Organon — Installed Skills${NC}"
echo "============================="
echo ""

$PYTHON_CMD -c "
import json, sys, os

catalog_path = sys.argv[1]
skills_dir = sys.argv[2]

with open(catalog_path) as f:
    catalog = json.load(f)

core_skills = catalog.get('core_skills', [])
optional_skills = catalog.get('skills', {})

installed = []
available = []

# Core skills — always shown as installed
for name in sorted(core_skills):
    installed.append((name, True))

# Optional skills — check if directory exists on disk.
# Core skills are also listed under 'skills' in catalog.json; skip
# them here so they aren't reported twice in the INSTALLED section.
core_set = set(core_skills)
for name in sorted(optional_skills.keys()):
    if name in core_set:
        continue
    skill_dir = os.path.join(skills_dir, name)
    info = optional_skills[name]
    services = info.get('requires_services', [])
    desc = info.get('description', '')
    if os.path.isdir(skill_dir):
        installed.append((name, False))
    else:
        available.append((name, desc, services))

# Print installed
print('INSTALLED:')
for name, is_core in installed:
    tag = ' (core)' if is_core else ''
    print(f'  \033[0;32m✓\033[0m {name}{tag}')

# Print available
if available:
    print()
    print('AVAILABLE:')
    # Calculate padding for alignment
    max_len = max(len(name) for name, _, _ in available) if available else 0
    for name, desc, services in available:
        svc_str = ', '.join(services)
        if desc and services:
            hint = f' — {desc} (needs {svc_str})'
        elif desc:
            hint = f' — {desc}'
        elif services:
            hint = f' — (needs {svc_str})'
        else:
            hint = ''
        padding = ' ' * (max_len - len(name))
        print(f'  \033[1;33m○\033[0m {name}{padding}  {hint}')
else:
    print()
    print('All skills are installed.')

print()
" "$CATALOG" "$SKILLS_DIR"
