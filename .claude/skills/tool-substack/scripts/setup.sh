#!/usr/bin/env bash
# Verify uv is available — tool-substack uses `uv run --with ...` to pull
# markdown-it-py and requests on demand, so nothing is installed globally.
set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
    echo "[tool-substack setup] ERROR: 'uv' not found." >&2
    echo "Install via: brew install uv   (or see https://docs.astral.sh/uv/)" >&2
    exit 1
fi

# Smoke-test the ephemeral env so the user knows deps are resolvable.
uv run --with markdown-it-py --with requests python3 - <<'PY'
import markdown_it, requests  # noqa: F401
print("[tool-substack setup] ok ✓  markdown-it-py + requests resolve via uv")
PY
