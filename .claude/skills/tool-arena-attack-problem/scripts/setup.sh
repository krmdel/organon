#!/usr/bin/env bash
# arena-attack-problem setup -- verifies runtime deps are reachable.
# Idempotent: does not install anything without user consent.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

echo "[setup] arena-attack-problem"
echo "[setup]   repo root: $REPO_ROOT"

# 1. arena-framework package importable from the skill.
if [ ! -d "$REPO_ROOT/plugins/arena/arena-framework/src/arena_framework" ]; then
    echo "[setup]   ERROR: arena-framework not found at $REPO_ROOT/plugins/arena/arena-framework"
    exit 1
fi
echo "[setup]   arena-framework: OK"

# 2. tool-einstein-arena present.
if [ ! -d "$REPO_ROOT/.claude/skills/tool-einstein-arena" ]; then
    echo "[setup]   ERROR: tool-einstein-arena skill missing"
    exit 1
fi
echo "[setup]   tool-einstein-arena: OK"

# 3. All 5 recon agents present.
missing=0
for agent in arena-literature-agent arena-historian-agent arena-pattern-scout-agent arena-rigor-agent arena-critic-agent; do
    if [ ! -f "$REPO_ROOT/.claude/agents/$agent.md" ]; then
        echo "[setup]   ERROR: missing agent spec $agent.md"
        missing=1
    fi
done
[ $missing -eq 0 ] && echo "[setup]   5 recon agents: OK"

# 4. Python smoke-import.
python3 -c "
import sys
sys.path.insert(0, '$REPO_ROOT/plugins/arena/arena-framework/src')
from arena_framework.recon import Recon
from arena_framework.hypothesize import synthesize, CouncilOutputs
from arena_framework.orchestrator import AttackOrchestrator
print('[setup]   Python imports: OK')
"

echo "[setup] done"
