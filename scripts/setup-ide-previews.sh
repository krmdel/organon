#!/usr/bin/env bash
set -euo pipefail

# Installs IDE extensions so Cursor/VS Code can preview and edit the file
# formats Organon skills produce (docx, xlsx, pdf, csv, etc.).
# Idempotent: extensions already present are skipped by the CLI.

EXTENSIONS=(
  "cweijan.vscode-office"        # .docx + .xlsx + .pptx viewer/editor
  "tomoki1207.pdf"               # .pdf viewer
  "mechatroner.rainbow-csv"      # CSV/TSV rainbow columns + query
  "janisdd.vscode-edit-csv"      # CSV grid editor
  "grapecity.gc-excelviewer"     # Excel/CSV grid preview
  "ms-toolsai.jupyter"           # .ipynb (usually already installed)
  "ms-vscode.live-server"        # live HTML preview for viz-presentation decks
)

detect_cli() {
  if command -v cursor >/dev/null 2>&1; then
    echo "cursor"; return
  fi
  if command -v code >/dev/null 2>&1; then
    echo "code"; return
  fi
  # macOS fallback: look inside the app bundles
  for path in \
    "/Applications/Cursor.app/Contents/Resources/app/bin/cursor" \
    "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"; do
    if [[ -x "$path" ]]; then echo "$path"; return; fi
  done
  echo ""
}

CLI="$(detect_cli)"
if [[ -z "$CLI" ]]; then
  echo "[ERROR] Neither 'cursor' nor 'code' CLI found on PATH." >&2
  echo "        In Cursor/VS Code run: Shell Command: Install 'cursor'/'code' command in PATH" >&2
  exit 1
fi

echo "[INFO] Using '$CLI' CLI to install preview extensions"
echo

installed=()
failed=()
for ext in "${EXTENSIONS[@]}"; do
  printf "  %-40s " "$ext"
  if "$CLI" --install-extension "$ext" --force >/dev/null 2>&1; then
    echo "ok"
    installed+=("$ext")
  else
    echo "FAILED"
    failed+=("$ext")
  fi
done

echo
echo "[INFO] Installed: ${#installed[@]} / ${#EXTENSIONS[@]}"
if (( ${#failed[@]} > 0 )); then
  echo "[WARN] Failed: ${failed[*]}" >&2
  exit 1
fi
