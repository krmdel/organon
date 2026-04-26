#!/usr/bin/env bash
# Organon end-to-end test runner (see tests/e2e/).
#
# Usage:
#   scripts/run-e2e.sh                   # full suite (192 tests, ~16s)
#   scripts/run-e2e.sh -m "not slow"     # skip > 5s tests (CI-fast path)
#   scripts/run-e2e.sh -m "not needs_arena_data"  # fresh-clone safe subset
#   scripts/run-e2e.sh tests/e2e/test_e2e_ulp_polish.py  # one module
#
# Any flags after the script name are forwarded verbatim to pytest.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"
exec python3 -m pytest tests/e2e/ "$@"
