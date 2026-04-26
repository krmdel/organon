# Description Optimization

The `description` field in SKILL.md frontmatter is the primary mechanism that determines whether Claude invokes a skill. After creating or improving a skill, offer to optimize it for better triggering accuracy.

---

## How Skill Triggering Works

Skills appear in Claude's `available_skills` list with name + description. Claude consults a skill based on that description — but only for tasks it can't easily handle alone. Simple one-step queries ("read this PDF") may not trigger a skill even if the description matches perfectly; complex, multi-step queries reliably trigger when the description matches. Design eval queries to be substantive enough that a skill would genuinely help.

---

## Step 1: Generate Trigger Eval Queries

Create 20 eval queries — a mix of should-trigger and should-not-trigger. Save as JSON:

```json
[
  {"query": "the user prompt", "should_trigger": true},
  {"query": "another prompt", "should_trigger": false}
]
```

Queries must be realistic and specific: include file paths, personal context about the user's job, column names, company names, URLs, a bit of backstory. Mix lengths. Focus on edge cases, not clear-cut cases.

**Bad:** `"Format this data"`, `"Create a chart"`
**Good:** `"ok so my boss just sent me this xlsx file (its in my downloads, called something like 'Q4 sales final FINAL v2.xlsx') and she wants me to add a column that shows the profit margin as a percentage. The revenue is in column C and costs are in column D i think"`

**Should-trigger (8–10 queries):** different phrasings of the same intent — formal and casual. Include cases where the user doesn't explicitly name the skill but clearly needs it. Uncommon use cases. Cases where this skill competes with another but should win.

**Should-not-trigger (8–10 queries):** the most valuable are near-misses — queries sharing keywords or concepts with the skill but actually needing something different. Adjacent domains, ambiguous phrasing where a naive keyword match would trigger but shouldn't. Never make these obviously irrelevant.

---

## Step 2: Review with User

1. Read the template from `assets/eval_review.html`.
2. Replace placeholders:
   - `__EVAL_DATA_PLACEHOLDER__` → the JSON array (no quotes — it's a JS variable assignment)
   - `__SKILL_NAME_PLACEHOLDER__` → the skill's name
   - `__SKILL_DESCRIPTION_PLACEHOLDER__` → the current description
3. Write to `/tmp/eval_review_<skill-name>.html` and open: `open /tmp/eval_review_<skill-name>.html`
4. The user can edit queries, toggle should-trigger, add/remove entries, then click "Export Eval Set".
5. Check `~/Downloads/` for the most recent `eval_set.json` (may be `eval_set (1).json` etc.).

This step matters — bad eval queries lead to bad descriptions.

---

## Step 3: Run the Optimization Loop

Tell the user: "This will take some time — I'll run the optimization loop in the background and check periodically."

Save the eval set to the workspace, then run in the background:

```bash
python -m scripts.run_loop \
  --eval-set <path-to-trigger-eval.json> \
  --skill-path <path-to-skill> \
  --model <model-id-powering-this-session> \
  --max-iterations 5 \
  --verbose
```

Use the model ID from the system prompt so the triggering test matches what the user actually experiences.

While running, periodically tail the output to report iteration and score progress.

The loop automatically:
- Splits eval set into 60% train / 40% held-out test
- Evaluates current description (each query run 3 times for reliable trigger rate)
- Calls Claude to propose improvements based on failures
- Re-evaluates on train + test
- Iterates up to 5 times
- Returns `best_description` selected by test score (not train score, to avoid overfitting)

---

## Step 4: Apply the Result

Take `best_description` from the JSON output and update the skill's SKILL.md frontmatter. Show the user before/after and report the scores.
