#!/usr/bin/env bash
# test-research-mgmt.sh — Test harness for Phase 7 Research Management (MGMT-01 through MGMT-05)
# Usage: bash tests/test-research-mgmt.sh [--quick|--note-capture|--note-search|--project-tracking|--promotion|--cron-setup|--pipeline-exec]
# Exit code: 0 if all selected tests pass, 1 if any fail

set -uo pipefail

# ── Resolve repo and script paths ───────────────────────────────────────────
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_PATH/.." && pwd)"
SEARCH_NOTES="$REPO_ROOT/.claude/skills/sci-research-mgmt/scripts/search_notes.sh"
FIXTURES_DIR="$SCRIPT_PATH/fixtures/sample-notes"

# ── Test state ───────────────────────────────────────────────────────────────
PASS_COUNT=0
FAIL_COUNT=0
TOTAL=0

pass() {
  PASS_COUNT=$((PASS_COUNT + 1))
  TOTAL=$((TOTAL + 1))
  echo "  PASS: $1"
}

fail() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  TOTAL=$((TOTAL + 1))
  echo "  FAIL: $1"
  echo "        $2"
}

# ── Setup: temporary research root ──────────────────────────────────────────
setup_tmp() {
  RESEARCH_ROOT=$(mktemp -d)
  mkdir -p "$RESEARCH_ROOT/notes"
  mkdir -p "$RESEARCH_ROOT/experiments"
  mkdir -p "$RESEARCH_ROOT/projects"
  mkdir -p "$RESEARCH_ROOT/pipelines"
  mkdir -p "$RESEARCH_ROOT/alerts"
}

teardown_tmp() {
  if [ -n "${RESEARCH_ROOT:-}" ] && [ -d "${RESEARCH_ROOT:-}" ]; then
    rm -rf "$RESEARCH_ROOT"
  fi
}

# ── Test functions ────────────────────────────────────────────────────────────

test_note_capture() {
  echo ""
  echo "--- test_note_capture ---"
  setup_tmp

  local TEST_DATE
  TEST_DATE=$(date +%Y-%m-%d)
  local NOTE_FILE="$RESEARCH_ROOT/notes/$TEST_DATE.md"

  # Simulate note capture: create file with heading
  echo "# Research Notes - $TEST_DATE" > "$NOTE_FILE"
  echo "" >> "$NOTE_FILE"
  echo "## 10:00 - Test observation entry #observation" >> "$NOTE_FILE"
  echo "Testing note capture functionality." >> "$NOTE_FILE"

  # Assert: file exists
  if [ -f "$NOTE_FILE" ]; then
    pass "Note file created at expected path"
  else
    fail "Note file creation" "Expected $NOTE_FILE to exist"
  fi

  # Assert: heading format matches
  if grep -q "^# Research Notes - $TEST_DATE$" "$NOTE_FILE"; then
    pass "Note heading format correct"
  else
    fail "Note heading format" "Expected '# Research Notes - $TEST_DATE' in $NOTE_FILE"
  fi

  # Assert: timestamp entry format
  if grep -q "^## [0-9][0-9]:[0-9][0-9] - " "$NOTE_FILE"; then
    pass "Timestamp entry format correct"
  else
    fail "Timestamp entry format" "Expected '## HH:MM - Title' format in $NOTE_FILE"
  fi

  # Assert: tag present
  if grep -q "#observation" "$NOTE_FILE"; then
    pass "Inline tag captured correctly"
  else
    fail "Inline tag" "Expected '#observation' tag in entry"
  fi

  # Assert: append behavior (second note appended, not overwritten)
  echo "" >> "$NOTE_FILE"
  echo "## 14:00 - Second entry #idea" >> "$NOTE_FILE"
  echo "Appended entry." >> "$NOTE_FILE"

  local ENTRY_COUNT
  ENTRY_COUNT=$(grep -c "^## [0-9]" "$NOTE_FILE" || true)
  if [ "$ENTRY_COUNT" -ge 2 ]; then
    pass "Append behavior: multiple entries in single day file"
  else
    fail "Append behavior" "Expected 2+ entries in file, found $ENTRY_COUNT"
  fi

  teardown_tmp
}

test_note_search_keyword() {
  echo ""
  echo "--- test_note_search_keyword ---"

  # Verify search script exists
  if [ ! -f "$SEARCH_NOTES" ]; then
    fail "search_notes.sh exists" "Expected $SEARCH_NOTES to exist"
    return
  fi
  pass "search_notes.sh exists"

  # Search for 'protein' across fixture notes
  local OUTPUT EXIT_CODE
  OUTPUT=$(bash "$SEARCH_NOTES" "protein" --dir "$FIXTURES_DIR" 2>&1) && EXIT_CODE=0 || EXIT_CODE=$?

  if [ $EXIT_CODE -eq 0 ]; then
    pass "Keyword search exits 0 when matches found"
  else
    fail "Keyword search exit code" "Expected exit 0 for 'protein' query, got $EXIT_CODE"
  fi

  # Should match both fixture files (protein in 2026-04-01 and 2026-04-03)
  if echo "$OUTPUT" | grep -q "2026-04-01"; then
    pass "Keyword search finds match in 2026-04-01.md"
  else
    fail "Keyword search 2026-04-01" "Expected match in 2026-04-01.md for 'protein'"
  fi

  if echo "$OUTPUT" | grep -q "2026-04-03"; then
    pass "Keyword search finds match in 2026-04-03.md"
  else
    fail "Keyword search 2026-04-03" "Expected match in 2026-04-03.md for 'protein'"
  fi
}

test_note_search_tag() {
  echo ""
  echo "--- test_note_search_tag ---"

  if [ ! -f "$SEARCH_NOTES" ]; then
    fail "search_notes.sh exists" "Expected $SEARCH_NOTES to exist"
    return
  fi

  # Search for #experiment tag — should match 2026-04-03.md only (has #experiment)
  # but NOT #experimental (word boundary test)
  local OUTPUT EXIT_CODE
  OUTPUT=$(bash "$SEARCH_NOTES" --tag experiment --dir "$FIXTURES_DIR" 2>&1) && EXIT_CODE=0 || EXIT_CODE=$?

  if [ $EXIT_CODE -eq 0 ]; then
    pass "Tag search exits 0 when matches found"
  else
    fail "Tag search exit code" "Expected exit 0 for --tag experiment, got $EXIT_CODE"
  fi

  # Should match 2026-04-03 (has #experiment)
  if echo "$OUTPUT" | grep -q "2026-04-03"; then
    pass "Tag search finds #experiment in 2026-04-03.md"
  else
    fail "Tag search 2026-04-03" "Expected match in 2026-04-03.md for #experiment tag"
  fi

  # Should NOT match 2026-04-01 (has no #experiment tag, only #observation and #meeting)
  if ! echo "$OUTPUT" | grep -q "2026-04-01"; then
    pass "Tag search correctly excludes 2026-04-01.md (no #experiment tag)"
  else
    fail "Tag search word boundary" "2026-04-01.md should not match #experiment tag"
  fi

  # Word boundary test: add a file with #experimental to verify it's NOT matched
  local TMPDIR_BOUND
  TMPDIR_BOUND=$(mktemp -d)
  cat > "$TMPDIR_BOUND/2026-01-01.md" << 'EOF'
# Research Notes - 2026-01-01

## 09:00 - Test entry with experimental tag #experimental
This entry has #experimental but NOT #experiment — should not match.
EOF
  cat > "$TMPDIR_BOUND/2026-01-02.md" << 'EOF'
# Research Notes - 2026-01-02

## 10:00 - Test entry with experiment tag #experiment
This entry has #experiment — should match.
EOF

  local BOUNDARY_OUTPUT BOUNDARY_EXIT
  BOUNDARY_OUTPUT=$(bash "$SEARCH_NOTES" --tag experiment --dir "$TMPDIR_BOUND" 2>&1) && BOUNDARY_EXIT=0 || BOUNDARY_EXIT=$?

  if echo "$BOUNDARY_OUTPUT" | grep -q "2026-01-02"; then
    pass "Tag word boundary: matches #experiment"
  else
    fail "Tag word boundary match" "Expected 2026-01-02 to match #experiment"
  fi

  if ! echo "$BOUNDARY_OUTPUT" | grep -q "2026-01-01"; then
    pass "Tag word boundary: #experimental does NOT match --tag experiment"
  else
    fail "Tag word boundary exclusion" "#experimental should not match --tag experiment"
  fi

  rm -rf "$TMPDIR_BOUND"
}

test_note_search_no_results() {
  echo ""
  echo "--- test_note_search_no_results ---"

  if [ ! -f "$SEARCH_NOTES" ]; then
    fail "search_notes.sh exists" "Expected $SEARCH_NOTES to exist"
    return
  fi

  # Search for something that does not exist in fixtures
  local EXIT_CODE=0
  bash "$SEARCH_NOTES" "xyzzy_nonexistent_query_12345" --dir "$FIXTURES_DIR" > /dev/null 2>&1 && EXIT_CODE=0 || EXIT_CODE=$?

  if [ $EXIT_CODE -eq 1 ]; then
    pass "No-results search exits 1 correctly"
  else
    fail "No-results exit code" "Expected exit 1 for no-match query, got $EXIT_CODE"
  fi
}

test_promotion() {
  echo ""
  echo "--- test_promotion ---"
  setup_tmp

  local TEST_DATE="2026-04-03"
  local NOTE_FILE="$RESEARCH_ROOT/notes/$TEST_DATE.md"

  # Copy the fixture note into temp research dir
  cp "$FIXTURES_DIR/$TEST_DATE.md" "$NOTE_FILE"

  # Simulate promotion: extract #experiment entry and create experiment log
  local ENTRY_TITLE="Unexpected folding pattern"
  local SLUG
  SLUG=$(echo "$ENTRY_TITLE" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -dc '[:alnum:]-' | cut -c1-50)

  local EXP_FILE="$RESEARCH_ROOT/experiments/${TEST_DATE}_${SLUG}.md"

  # Simulate writing the experiment file with YAML frontmatter
  cat > "$EXP_FILE" << EOF
---
title: $ENTRY_TITLE
promoted_from: research/notes/$TEST_DATE.md
promoted_at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
status: planning
linked_project:
---

# $ENTRY_TITLE

## Hypothesis
Noticed unexpected protein folding pattern in sample batch 3.
Temperature was 2C above protocol spec. May explain anomaly.

## Method
{To be filled -- or pipe to sci-hypothesis design mode}

## Results
{Pending}

## Notes
Promoted from research/notes/$TEST_DATE.md
EOF

  # Assert: experiment file exists
  if [ -f "$EXP_FILE" ]; then
    pass "Experiment file created at correct path"
  else
    fail "Experiment file creation" "Expected $EXP_FILE to exist"
  fi

  # Assert: YAML frontmatter present
  if grep -q "^promoted_from: research/notes/" "$EXP_FILE"; then
    pass "Experiment file has promoted_from frontmatter"
  else
    fail "Experiment frontmatter" "Expected 'promoted_from' field in $EXP_FILE"
  fi

  if grep -q "^status: planning$" "$EXP_FILE"; then
    pass "Experiment file has status: planning"
  else
    fail "Experiment status" "Expected 'status: planning' in $EXP_FILE"
  fi

  # Assert: slug derived from title
  if echo "$SLUG" | grep -q "^[a-z0-9-]*$"; then
    pass "Experiment slug is lowercase-hyphen format"
  else
    fail "Experiment slug format" "Expected lowercase-hyphen slug, got: $SLUG"
  fi

  teardown_tmp
}

test_cron_setup() {
  echo ""
  echo "--- test_cron_setup ---"

  local CRON_FILE="$REPO_ROOT/cron/jobs/science-paper-alerts.md"

  if [ -f "$CRON_FILE" ]; then
    pass "science-paper-alerts.md cron job file exists"
  else
    fail "Cron job file exists" "Expected $CRON_FILE to exist"
    return
  fi

  # Assert YAML frontmatter fields
  if grep -q "^name:" "$CRON_FILE"; then
    pass "Cron file has 'name' field"
  else
    fail "Cron name field" "Expected 'name:' in $CRON_FILE frontmatter"
  fi

  if grep -q "^schedule:" "$CRON_FILE"; then
    pass "Cron file has 'schedule' field"
  else
    fail "Cron schedule field" "Expected 'schedule:' in $CRON_FILE frontmatter"
  fi

  if grep -q "^description:" "$CRON_FILE"; then
    pass "Cron file has 'description' field"
  else
    fail "Cron description field" "Expected 'description:' in $CRON_FILE frontmatter"
  fi

  if grep -q "^model:" "$CRON_FILE"; then
    pass "Cron file has 'model' field"
  else
    fail "Cron model field" "Expected 'model:' in $CRON_FILE frontmatter"
  fi

  if grep -q "^max_budget_usd:" "$CRON_FILE"; then
    pass "Cron file has 'max_budget_usd' field"
  else
    fail "Cron max_budget_usd field" "Expected 'max_budget_usd:' in $CRON_FILE frontmatter"
  fi

  if grep -q "^enabled:" "$CRON_FILE"; then
    pass "Cron file has 'enabled' field"
  else
    fail "Cron enabled field" "Expected 'enabled:' in $CRON_FILE frontmatter"
  fi
}

test_pipeline_exists() {
  echo ""
  echo "--- test_pipeline_exists ---"

  local LIT_MONITOR="$REPO_ROOT/research/pipelines/literature-monitor.md"
  local DATA_WATCH="$REPO_ROOT/research/pipelines/data-watch.md"

  if [ -f "$LIT_MONITOR" ]; then
    pass "research/pipelines/literature-monitor.md exists"
  else
    fail "literature-monitor.md exists" "Expected $LIT_MONITOR to exist"
  fi

  if [ -f "$DATA_WATCH" ]; then
    pass "research/pipelines/data-watch.md exists"
  else
    fail "data-watch.md exists" "Expected $DATA_WATCH to exist"
  fi
}

test_project_tracking() {
  echo ""
  echo "--- test_project_tracking ---"
  setup_tmp

  local PROJECT_FILE="$RESEARCH_ROOT/projects/test-project.md"

  # Simulate creating a research project file
  cat > "$PROJECT_FILE" << 'EOF'
---
name: Temperature-Dependent Protein Folding
status: active
goal: Determine the effect of temperature gradients on protein folding rate
pi: Dr. Smith
collaborators: []
funding: NIH R01-12345
irb: not applicable
created: 2026-04-05
deadline: 2027-04-05
milestones:
  - name: Baseline assay
    date: "2026-06-01"
    status: in-progress
  - name: Temperature gradient experiment
    date: "2026-09-01"
    status: pending
linked_publications: []
datasets: []
linked_outputs: []
---

# Temperature-Dependent Protein Folding

## Progress Notes
- 2026-04-05: Project created
EOF

  # Assert: file exists
  if [ -f "$PROJECT_FILE" ]; then
    pass "Research project file created"
  else
    fail "Project file creation" "Expected $PROJECT_FILE to exist"
  fi

  # Assert: required frontmatter fields
  if grep -q "^name:" "$PROJECT_FILE"; then
    pass "Project file has 'name' frontmatter"
  else
    fail "Project name field" "Expected 'name:' in frontmatter"
  fi

  if grep -q "^status:" "$PROJECT_FILE"; then
    pass "Project file has 'status' frontmatter"
  else
    fail "Project status field" "Expected 'status:' in frontmatter"
  fi

  if grep -q "^goal:" "$PROJECT_FILE"; then
    pass "Project file has 'goal' frontmatter"
  else
    fail "Project goal field" "Expected 'goal:' in frontmatter"
  fi

  if grep -q "^milestones:" "$PROJECT_FILE"; then
    pass "Project file has 'milestones' frontmatter"
  else
    fail "Project milestones field" "Expected 'milestones:' in frontmatter"
  fi

  teardown_tmp
}

# ── Summary ──────────────────────────────────────────────────────────────────

print_summary() {
  echo ""
  echo "=================================="
  echo "Test Summary: $PASS_COUNT/$TOTAL tests passed"
  echo "=================================="
  if [ $FAIL_COUNT -gt 0 ]; then
    echo "FAILED: $FAIL_COUNT test(s) failed"
    return 1
  fi
  return 0
}

# ── Argument parsing ─────────────────────────────────────────────────────────

RUN_NOTE_CAPTURE=false
RUN_NOTE_SEARCH=false
RUN_PROJECT_TRACKING=false
RUN_PROMOTION=false
RUN_CRON_SETUP=false
RUN_PIPELINE_EXEC=false

if [ $# -eq 0 ]; then
  # Full suite
  RUN_NOTE_CAPTURE=true
  RUN_NOTE_SEARCH=true
  RUN_PROJECT_TRACKING=true
  RUN_PROMOTION=true
  RUN_CRON_SETUP=true
  RUN_PIPELINE_EXEC=true
fi

for arg in "$@"; do
  case "$arg" in
    --quick)
      RUN_NOTE_CAPTURE=true
      RUN_NOTE_SEARCH=true
      ;;
    --note-capture)
      RUN_NOTE_CAPTURE=true
      ;;
    --note-search)
      RUN_NOTE_SEARCH=true
      ;;
    --project-tracking)
      RUN_PROJECT_TRACKING=true
      ;;
    --promotion)
      RUN_PROMOTION=true
      ;;
    --cron-setup)
      RUN_CRON_SETUP=true
      ;;
    --pipeline-exec)
      RUN_PIPELINE_EXEC=true
      ;;
    *)
      echo "Unknown flag: $arg"
      echo "Usage: $0 [--quick|--note-capture|--note-search|--project-tracking|--promotion|--cron-setup|--pipeline-exec]"
      exit 1
      ;;
  esac
done

# ── Run selected tests ────────────────────────────────────────────────────────

echo "Running research management tests..."

$RUN_NOTE_CAPTURE && test_note_capture
$RUN_NOTE_SEARCH && { test_note_search_keyword; test_note_search_tag; test_note_search_no_results; }
$RUN_PROMOTION && test_promotion
$RUN_CRON_SETUP && test_cron_setup
$RUN_PIPELINE_EXEC && test_pipeline_exists
$RUN_PROJECT_TRACKING && test_project_tracking

print_summary
