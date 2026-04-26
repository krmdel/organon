#!/usr/bin/env bash
# setup.sh — Auto-install mermaid-cli and its rendering dependencies
# Run once per machine. Skips if everything is already installed.

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; }

ERRORS=0

# ── Node.js check ──────────────────────────────────────────────────────
if ! command -v node &>/dev/null; then
  fail "Node.js is not installed. Install it first: https://nodejs.org/"
  exit 1
fi
ok "Node.js $(node --version)"

if ! command -v npm &>/dev/null; then
  fail "npm is not installed. It should come with Node.js."
  exit 1
fi
ok "npm $(npm --version)"

# ── mermaid-cli (mmdc) ────────────────────────────────────────────────
if npx mmdc --version &>/dev/null 2>&1; then
  ok "mermaid-cli (mmdc) already available via npx"
else
  warn "mermaid-cli not found — installing @mermaid-js/mermaid-cli globally..."
  if npm install -g @mermaid-js/mermaid-cli; then
    ok "mermaid-cli installed"
  else
    fail "Failed to install @mermaid-js/mermaid-cli"
    ERRORS=$((ERRORS + 1))
  fi
fi

# ── Puppeteer Chrome browser ──────────────────────────────────────────
# mmdc uses Puppeteer under the hood for rendering SVG/PNG.
# Ensure Chrome is available to Puppeteer.
if npx puppeteer browsers install chrome &>/dev/null 2>&1; then
  ok "Puppeteer Chrome browser ready"
else
  warn "Puppeteer Chrome install had issues — mmdc may still work with system Chrome"
fi

# ── Verify full pipeline ─────────────────────────────────────────────
echo ""
echo "Verifying render pipeline..."
TMPDIR_CHECK=$(mktemp -d)
echo 'flowchart LR
    A[Test] --> B[OK]' > "$TMPDIR_CHECK/test.mmd"

if npx mmdc -i "$TMPDIR_CHECK/test.mmd" -o "$TMPDIR_CHECK/test.svg" -t neutral &>/dev/null 2>&1; then
  ok "Render pipeline works (SVG output verified)"
else
  fail "Render pipeline test failed — check mmdc installation"
  ERRORS=$((ERRORS + 1))
fi
rm -rf "$TMPDIR_CHECK"

# ── Summary ──────────────────────────────────────────────────────────
echo ""
if [ "$ERRORS" -eq 0 ]; then
  ok "All dependencies ready. viz-diagram-code is good to go."
else
  fail "$ERRORS dependency issue(s) found. Fix them and re-run this script."
  exit 1
fi
