# tool-einstein-arena — smoke transcript (playbook)

Minimal invocation confirming the playbook template is discoverable, copyable, and schema-valid. Does NOT exercise register/submit/fetch (those need live arena credentials and are covered by the scripts' own usage docs).

## Invocation

```bash
# 1. Confirm the template exists
cat .claude/skills/tool-einstein-arena/assets/playbook-template.md | head -20

# 2. Copy into a fresh project slot
mkdir -p /tmp/arena-demo
cp .claude/skills/tool-einstein-arena/assets/playbook-template.md \
   /tmp/arena-demo/PLAYBOOK.md

# 3. Replace placeholders (demo only — in production, fill manually from evidence)
sed -i.bak 's|{Problem Slug}|kissing-d11|g' /tmp/arena-demo/PLAYBOOK.md
sed -i.bak 's|{Approach Tag}|session-1|g' /tmp/arena-demo/PLAYBOOK.md
head -3 /tmp/arena-demo/PLAYBOOK.md

# 4. Run the schema test against both the template AND a populated fill
python3 -m pytest .claude/skills/tool-einstein-arena/tests/test_playbook_structure.py -v
```

## Expected output

```
# kissing-d11 — session-1 Playbook
<!-- fill: short prose tag for this playbook instance ... -->

============================= test session starts ==============================
...
test_template_exists_and_nonempty PASSED
test_template_has_exact_section_order PASSED
test_template_every_section_has_fill_placeholder PASSED
test_option_a_fill_has_exact_section_order PASSED
test_option_a_fill_has_no_unfilled_placeholders PASSED
...
9 passed in 0.01s
```

## Related tests

See `tests/test_playbook_structure.py` for the complete schema contract (7 sections in exact order, `<!-- fill: ... -->` placeholders in every section, size cap 400 lines, no populated-looking rows in the template).

Populated playbooks currently live at:
- `projects/einstein-arena-difference-bases/option_a/PLAYBOOK.md` (original retroactive fill)
- `projects/einstein-arena-first-autocorrelation-inequality/PLAYBOOK.md` (second retroactive fill, 2026-04-22)
