#!/usr/bin/env bash
# setup.sh -- Download ToolUniverse catalog for sci-tools skill.
# Downloads ~2,200 biomedical tools as local JSON for instant offline search.
# Supports --refresh flag to force re-download.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
DATA_DIR="$REPO_ROOT/data"
CATALOG_FILE="$DATA_DIR/tooluniverse-catalog.json"

echo "=== sci-tools setup ==="

# Check uvx availability
if ! command -v uvx &>/dev/null; then
    echo "[WARN] uvx not found. Cannot download catalog."
    echo "Install uv first: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Create data directory if needed
mkdir -p "$DATA_DIR"

# Download catalog if not present or if --refresh flag passed
if [[ ! -f "$CATALOG_FILE" ]] || [[ "${1:-}" == "--refresh" ]]; then
    echo "Downloading ToolUniverse catalog (~2,200 tools)..."
    uvx --from tooluniverse tu list --raw --mode custom \
        --fields name description type category \
        --limit 9999 > "$CATALOG_FILE.tmp"

    # Validate JSON before replacing
    if python3 -c "import json; json.load(open('$CATALOG_FILE.tmp'))" 2>/dev/null; then
        mv "$CATALOG_FILE.tmp" "$CATALOG_FILE"
        # Inject refreshed_at timestamp (matches catalog_ops.refresh_catalog() behavior)
        python3 -c "
import json
from datetime import datetime
p='$CATALOG_FILE'
d=json.load(open(p))
d['refreshed_at']=datetime.now().isoformat()
json.dump(d,open(p,'w'),indent=2)
"
        TOOL_COUNT=$(python3 -c "import json; print(json.load(open('$CATALOG_FILE'))['total_tools'])")
        echo "[OK] Catalog downloaded: $TOOL_COUNT tools"
    else
        rm -f "$CATALOG_FILE.tmp"
        echo "[ERROR] Downloaded catalog is not valid JSON"
        exit 1
    fi
else
    echo "[OK] Catalog already exists at $CATALOG_FILE"
fi

echo "=== sci-tools setup complete ==="
