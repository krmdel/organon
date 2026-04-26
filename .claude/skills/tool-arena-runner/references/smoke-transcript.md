# tool-arena-runner — smoke transcript

Minimal invocation demonstrating the three subcommands' help output and a `recon` dry-run against a tmp project dir. Does NOT hit the live arena (that requires credentials and is covered by `tool-einstein-arena`).

## Invocation

```bash
# 1. Top-level help
python3 .claude/skills/tool-arena-runner/scripts/arena_runner.py --help

# 2. Recon: bootstrap a fresh arena project folder
mkdir -p /tmp/arena-kissing-d12
python3 .claude/skills/tool-arena-runner/scripts/arena_runner.py recon \
  --slug kissing-d12 \
  --project-dir /tmp/arena-kissing-d12
ls /tmp/arena-kissing-d12/
head -3 /tmp/arena-kissing-d12/PLAYBOOK.md

# 3. Recon idempotence (second run — should NOT overwrite)
python3 .claude/skills/tool-arena-runner/scripts/arena_runner.py recon \
  --slug kissing-d12 \
  --project-dir /tmp/arena-kissing-d12 \
  2>&1 | grep -iE "exists|skip"

# 4. Tri-verify help (no live verifier needed)
python3 .claude/skills/tool-arena-runner/scripts/arena_runner.py tri-verify --help | head -5
```

## Expected output

```
usage: arena_runner.py [-h] {polish,tri-verify,recon} ...
...
<!-- recon-slug: kissing-d12 -->
# kissing-d12 — {Approach Tag} Playbook
<!-- fill: short prose tag ... -->

PLAYBOOK.md
NOTES.md

[recon] PLAYBOOK.md already exists — skipping (safe — existing file preserved)
[recon] NOTES.md already exists — skipping
...
usage: arena_runner.py tri-verify [-h] --solution SOLUTION ...
```

Invariants the smoke test confirms:

- `--help` routes to argparse and prints the three subcommand names.
- `recon` creates `PLAYBOOK.md` (copied from `tool-einstein-arena/assets/playbook-template.md`) and `NOTES.md`.
- Running `recon` twice on the same folder preserves both files and prints a warning.
- Every subcommand has its own `--help` routing.

## Related tests

- `tests/test_arena_runner.py::test_cli_help_lists_subcommands`
- `tests/test_arena_runner.py::test_recon_creates_expected_layout`
- `tests/test_arena_runner.py::test_recon_idempotent`
- `tests/test_arena_runner.py::test_unknown_subcommand`
