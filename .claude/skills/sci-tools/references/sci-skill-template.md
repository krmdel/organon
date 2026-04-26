# Scientific Skill Template

Use this template when creating new scientific skills. Pre-fills conventions
from existing sci-* skills so the scientist answers fewer questions.

## SKILL.md Template

```markdown
---
name: sci-{skill-name}
description: >
  {One paragraph: what it does, when it triggers, what it reads.}
  Triggers on: {comma-separated trigger phrases}.
  Does NOT trigger for: {negative triggers referencing other sci-* skills}.
---

# {Skill Title}

## Outcome

{What the skill produces.} Outputs to `projects/sci-{skill-name}/` with date-stamped filenames.

## Context Needs

| File | Load level | Purpose |
|------|-----------|---------|
| `research_context/research-profile.md` | full | Field, interests for personalization |
| `context/learnings.md` | `## sci-{skill-name}` section | Previous feedback |

## Dependencies

| Skill | Required? | What it provides | Without it |
|-------|-----------|-----------------|------------|
| {dependency} | {Required/Optional} | {what} | {fallback} |

Requires: Python venv with {packages} (shared with sci-data-analysis).
Run `.claude/skills/sci-{skill-name}/scripts/setup.sh` if packages missing.

## Step 0: Auto-Setup

Run `.claude/skills/sci-{skill-name}/scripts/setup.sh` if first invocation.

## Step 1: Detect Intent

Parse user request into mode:
- **mode-a** -- {trigger phrases}
- **mode-b** -- {trigger phrases}

If ambiguous, ask which mode the scientist wants.

## Step 2-N: {Mode Steps}

{Implementation steps per mode.}

## Step N+1: Save & Log

1. Save output to `projects/sci-{skill-name}/{descriptive-name}_{YYYY-MM-DD}.md`
2. Show full absolute file path
3. Log to reproducibility ledger: `repro.repro_logger.log_operation()`
4. Ask: "How did this land? Any adjustments?"
5. Log feedback to `context/learnings.md` under `## sci-{skill-name}`

## Rules

- Always read `research_context/research-profile.md` before generating output
- Always log operations for reproducibility
- Always save output to disk with date-stamped filename
- Show full absolute file path after saving
```

## Folder Structure Template

```
.claude/skills/sci-{skill-name}/
  SKILL.md              # Main skill file (from template above)
  scripts/
    setup.sh            # Auto-setup: check/install deps in shared venv
    {module}_ops.py     # Python backend (if needed)
  references/
    {topic}.md          # Depth material (one file per topic)
```

## setup.sh Template

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
VENV_DIR="$REPO_ROOT/.venv"

echo "=== sci-{skill-name} setup ==="

# Check shared venv exists
if [[ ! -d "$VENV_DIR" ]]; then
    echo "[ERROR] Shared venv not found. Run scripts/setup-science.sh first."
    exit 1
fi

# Check required packages
PACKAGES=({list of packages})
for pkg in "${PACKAGES[@]}"; do
    if "$VENV_DIR/bin/python" -c "import $pkg" 2>/dev/null; then
        echo "[OK] $pkg available"
    else
        echo "Installing $pkg..."
        "$VENV_DIR/bin/pip" install "$pkg" -q
    fi
done

echo "=== sci-{skill-name} setup complete ==="
```

## Registration Checklist

After creating a sci-* skill, verify:
- [ ] Folder name matches `sci-{name}` in kebab-case
- [ ] YAML frontmatter `name` matches folder name exactly
- [ ] Trigger phrases don't conflict with existing sci-* skills
- [ ] Output path uses `projects/sci-{skill-name}/`
- [ ] Context Needs includes `research-profile.md`
- [ ] Reproducibility logging step included
- [ ] setup.sh uses shared venv at `.venv/`
- [ ] Heartbeat reconciliation will auto-register (just create the folder)
