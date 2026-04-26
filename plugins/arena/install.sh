#!/usr/bin/env bash
# Arena plugin installer — copies skills + agents into the Organon install.
# Run from your Organon repo root: bash plugins/arena/install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SKILLS_DST="$REPO_ROOT/.claude/skills"
AGENTS_DST="$REPO_ROOT/.claude/agents"

echo "[arena-plugin] Installing from $SCRIPT_DIR"
echo "[arena-plugin] Organon root: $REPO_ROOT"

SKILLS=(
    tool-einstein-arena
    tool-arena-runner
    tool-arena-attack-problem
    sci-optimization
    sci-optimization-recipes
    ops-parallel-tempering-sa
    ops-ulp-polish
)

AGENTS=(
    arena-literature-agent
    arena-historian-agent
    arena-pattern-scout-agent
    arena-router-agent
    arena-critic-agent
    arena-critic-loop
    arena-rigor-agent
    arena-mutator
)

# --- Skills ---
echo ""
echo "[arena-plugin] Installing skills..."
for skill in "${SKILLS[@]}"; do
    src="$REPO_ROOT/.claude/skills/$skill"
    if [ -d "$src" ]; then
        echo "  [ok] $skill (already present)"
    else
        echo "  [!] $skill not found at $src — skipping"
    fi
done

# --- Agents ---
echo ""
echo "[arena-plugin] Installing agents..."
for agent in "${AGENTS[@]}"; do
    src="$REPO_ROOT/.claude/agents/$agent.md"
    if [ -f "$src" ]; then
        echo "  [ok] $agent (already present)"
    else
        echo "  [!] $agent.md not found — skipping"
    fi
done

# --- Verify arena-framework ---
echo ""
echo "[arena-plugin] Verifying arena-framework..."
FRAMEWORK="$REPO_ROOT/plugins/arena/arena-framework/src/arena_framework"
if [ -d "$FRAMEWORK" ]; then
    echo "  [ok] arena-framework found"
else
    echo "  [error] arena-framework not found at $FRAMEWORK"
    exit 1
fi

# --- Python smoke test ---
echo ""
echo "[arena-plugin] Running Python smoke import..."
python3 -c "
import sys
sys.path.insert(0, '$REPO_ROOT/plugins/arena/arena-framework/src')
from arena_framework.recon import Recon
from arena_framework.hypothesize import synthesize, CouncilOutputs
from arena_framework.orchestrator import AttackOrchestrator
print('  [ok] arena_framework imports OK')
"

# --- Per-skill setup ---
echo ""
echo "[arena-plugin] Running skill setup checks..."
for skill in "${SKILLS[@]}"; do
    setup="$REPO_ROOT/.claude/skills/$skill/scripts/setup.sh"
    if [ -f "$setup" ]; then
        bash "$setup" && echo "  [ok] $skill setup" || echo "  [warn] $skill setup reported issues"
    fi
done

echo ""
echo "[arena-plugin] Installation complete."
echo ""
echo "Next steps:"
echo "  1. Register your agent:   /tool-arena-runner register"
echo "  2. Fetch a problem:       /tool-arena-runner fetch <problem-slug>"
echo "  3. Full attack:           /tool-arena-attack-problem attack <problem-slug>"
