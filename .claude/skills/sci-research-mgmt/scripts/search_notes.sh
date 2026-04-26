#!/usr/bin/env bash
# search_notes.sh — Grep-based research note search with keyword and tag filtering
# Usage: search_notes.sh [--tag TAG] [--dir DIR] [QUERY]
# Exit code: 0 if matches found, 1 if no matches or directory missing

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
TAG=""
DIR="research/notes"
QUERY=""

# ── Argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag)
      if [[ $# -lt 2 ]]; then echo "Missing value for --tag" >&2; exit 1; fi
      TAG="$2"
      shift 2
      ;;
    --dir)
      if [[ $# -lt 2 ]]; then echo "Missing value for --dir" >&2; exit 1; fi
      DIR="$2"
      shift 2
      ;;
    -*)
      echo "Unknown flag: $1" >&2
      echo "Usage: search_notes.sh [--tag TAG] [--dir DIR] [QUERY]" >&2
      exit 1
      ;;
    *)
      QUERY="$1"
      shift
      ;;
  esac
done

# ── Validate directory ────────────────────────────────────────────────────────
if [ ! -d "$DIR" ]; then
  echo "No notes directory found at '$DIR'." >&2
  echo "Start capturing notes first." >&2
  exit 1
fi

# ── Collect matching files and lines ─────────────────────────────────────────
MATCH_COUNT=0
FILE_COUNT=0

# Build result: collect all matches into a temp file for summary
TMPFILE=$(mktemp)
trap 'rm -f "$TMPFILE"' EXIT

# Discover note files (*.md) sorted by filename (chronological)
while IFS= read -r -d '' NOTE_FILE; do
  FILE_MATCHES=()
  FILE_HAS_MATCH=false

  # Read the file line-by-line to find matching entries
  # We look for ## HH:MM entry headings and their content
  ENTRY_HEADING=""
  ENTRY_TAGS=""
  ENTRY_LINES=()
  IN_ENTRY=false

  while IFS= read -r line; do
    # Detect a new entry heading: ## HH:MM - Title #tags
    if echo "$line" | grep -qE "^## [0-9]{2}:[0-9]{2} - "; then
      # Process previous entry if we have one
      if [ "$IN_ENTRY" = true ] && [ ${#ENTRY_LINES[@]} -gt 0 ]; then
        local_match=false

        # Check tag filter
        if [ -n "$TAG" ]; then
          # Word-boundary tag matching: #TAG followed by whitespace or end of line
          # POSIX-compatible: use [[:space:]] or end-of-string
          if echo "$ENTRY_HEADING" | grep -qE "#${TAG}([[:space:]]|$)"; then
            local_match=true
          fi
        fi

        # Check keyword filter (if no tag filter, or both)
        if [ -n "$QUERY" ] && [ -z "$TAG" ]; then
          local_match=false
          for eline in "${ENTRY_LINES[@]}"; do
            if echo "$eline" | grep -qi "$QUERY"; then
              local_match=true
              break
            fi
          done
        elif [ -n "$QUERY" ] && [ -n "$TAG" ]; then
          # Both tag and keyword: tag must match (already checked), then keyword
          if [ "$local_match" = true ]; then
            local_match=false
            for eline in "${ENTRY_LINES[@]}"; do
              if echo "$eline" | grep -qi "$QUERY"; then
                local_match=true
                break
              fi
            done
          fi
        fi

        if [ "$local_match" = true ]; then
          FILE_MATCHES+=("$ENTRY_HEADING")
          FILE_HAS_MATCH=true
          MATCH_COUNT=$((MATCH_COUNT + 1))
        fi
      fi

      # Start new entry
      ENTRY_HEADING="$line"
      ENTRY_TAGS=$(echo "$line" | grep -oE '#[[:alnum:]_-]+' | tr '\n' ' ' | sed 's/ $//')
      ENTRY_LINES=("$line")
      IN_ENTRY=true

    elif [ "$IN_ENTRY" = true ]; then
      ENTRY_LINES+=("$line")
    fi
  done < "$NOTE_FILE"

  # Process the last entry in the file
  if [ "$IN_ENTRY" = true ] && [ ${#ENTRY_LINES[@]} -gt 0 ]; then
    local_match=false

    if [ -n "$TAG" ]; then
      if echo "$ENTRY_HEADING" | grep -qE "#${TAG}([[:space:]]|$)"; then
        local_match=true
      fi
    fi

    if [ -n "$QUERY" ] && [ -z "$TAG" ]; then
      local_match=false
      for eline in "${ENTRY_LINES[@]}"; do
        if echo "$eline" | grep -qi "$QUERY"; then
          local_match=true
          break
        fi
      done
    elif [ -n "$QUERY" ] && [ -n "$TAG" ]; then
      if [ "$local_match" = true ]; then
        local_match=false
        for eline in "${ENTRY_LINES[@]}"; do
          if echo "$eline" | grep -qi "$QUERY"; then
            local_match=true
            break
          fi
        done
      fi
    fi

    if [ "$local_match" = true ]; then
      FILE_MATCHES+=("$ENTRY_HEADING")
      FILE_HAS_MATCH=true
      MATCH_COUNT=$((MATCH_COUNT + 1))
    fi
  fi

  # Output matches for this file
  if [ "$FILE_HAS_MATCH" = true ]; then
    FILE_COUNT=$((FILE_COUNT + 1))
    echo "$NOTE_FILE:" >> "$TMPFILE"
    for match in "${FILE_MATCHES[@]}"; do
      # Extract timestamp and tags for display
      local_ts=$(echo "$match" | grep -oE "^## [0-9]{2}:[0-9]{2}" | sed 's/## //')
      local_tags=$(echo "$match" | grep -oE '#[[:alnum:]_-]+' | tr '\n' ' ' | sed 's/ $//')
      local_title=$(echo "$match" | sed 's/^## [0-9][0-9]:[0-9][0-9] - //' | sed 's/ #.*//')
      echo "  ${local_ts} ${local_tags} - ${local_title}..." >> "$TMPFILE"
    done
  fi

done < <(find "$DIR" -maxdepth 1 -name "*.md" -print0 | sort -z)

# ── Output results ────────────────────────────────────────────────────────────

if [ $MATCH_COUNT -eq 0 ]; then
  if [ -n "$QUERY" ] && [ -z "$TAG" ]; then
    echo "No notes matching \"$QUERY\". Try a broader search term or different tag."
  elif [ -n "$TAG" ] && [ -z "$QUERY" ]; then
    echo "No notes matching tag #${TAG}. Try a different tag or broader search."
  else
    echo "No notes matching the specified criteria."
  fi
  exit 1
fi

echo "Found $MATCH_COUNT matches across $FILE_COUNT days:"
echo ""
cat "$TMPFILE"

# ── Tag summary ───────────────────────────────────────────────────────────────
echo ""
ALL_TAGS=$(grep -rh '#[[:alnum:]_-]*' "$DIR"/*.md 2>/dev/null | grep -oE '#[[:alnum:]_-]+' | sort | uniq -c | sort -rn | awk '{print $2 " (" $1 ")"}' | tr '\n' ', ' | sed 's/, $//' || true)
if [ -n "$ALL_TAGS" ]; then
  echo "Tags found: $ALL_TAGS"
fi

exit 0
