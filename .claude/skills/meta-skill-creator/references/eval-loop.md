# Eval Loop — Running and Evaluating Test Cases

Full procedure for running test cases and iterating on skills. One continuous sequence — don't stop partway.

Put results in `<skill-name>-workspace/` as a sibling to the skill directory. Within the workspace, organize by `iteration-<N>/`, then `eval-<ID>/` or a descriptive name per test case.

---

## Step 1: Spawn All Runs in the Same Turn

For each test case, spawn two subagents simultaneously — one with the skill, one as baseline. Never run with-skill first and baseline later.

**With-skill run:**
```
Execute this task:
- Skill path: <path-to-skill>
- Task: <eval prompt>
- Input files: <eval files if any, or "none">
- Save outputs to: <workspace>/iteration-<N>/eval-<ID>/with_skill/outputs/
- Outputs to save: <what the user cares about>
```

**Baseline run:**
- **New skill**: no skill. Same prompt, save to `without_skill/outputs/`.
- **Improving existing skill**: old version. Snapshot with `cp -r <skill-path> <workspace>/skill-snapshot/`, point baseline at snapshot, save to `old_skill/outputs/`.

Write `eval_metadata.json` for each test case:
```json
{
  "eval_id": 0,
  "eval_name": "descriptive-name",
  "prompt": "The user's task prompt",
  "assertions": []
}
```

---

## Step 2: Draft Assertions While Runs Are in Progress

Don't wait idle — draft quantitative assertions and explain them to the user. Good assertions are objectively verifiable with descriptive names. Subjective outputs (writing style, design quality) need human judgment, not forced assertions.

Update `eval_metadata.json` and `evals/evals.json` with assertions once drafted. See `references/schemas.md` for the full schema.

---

## Step 3: Capture Timing Data

When each subagent task completes, the notification contains `total_tokens` and `duration_ms`. Save immediately to `timing.json` in the run directory:
```json
{
  "total_tokens": 84852,
  "duration_ms": 23332,
  "total_duration_seconds": 23.3
}
```
This is the only opportunity — it doesn't persist elsewhere.

---

## Step 4: Grade, Aggregate, and Launch the Viewer

1. **Grade each run**: spawn a grader subagent (reads `agents/grader.md`). Save results to `grading.json`. Use `text`, `passed`, and `evidence` field names (not `name`/`met`/`details`). For checkable assertions, write and run a script rather than eyeballing.

2. **Aggregate into benchmark**:
   ```bash
   python -m scripts.aggregate_benchmark <workspace>/iteration-N --skill-name <name>
   ```
   Produces `benchmark.json` and `benchmark.md` with pass_rate, time, tokens per configuration.

3. **Analyst pass**: read the benchmark and surface patterns — non-discriminating assertions (always pass), high-variance evals (possibly flaky), time/token tradeoffs. See `agents/analyzer.md` for what to look for.

4. **Launch the viewer**:
   ```bash
   nohup python <skill-creator-path>/eval-viewer/generate_review.py \
     <workspace>/iteration-N \
     --skill-name "my-skill" \
     --benchmark <workspace>/iteration-N/benchmark.json \
     > /dev/null 2>&1 &
   VIEWER_PID=$!
   ```
   For iteration 2+: also pass `--previous-workspace <workspace>/iteration-<N-1>`.

   **Headless / no display:** use `--static <output_path>` to write a standalone HTML file. Feedback downloads as `feedback.json` when user clicks "Submit All Reviews".

   **IMPORTANT:** Always generate the eval viewer BEFORE making corrections yourself. Get the user's eyes on examples first.

5. **Tell the user**: "I've opened the results in your browser. 'Outputs' tab: click through test cases and leave feedback. 'Benchmark' tab: quantitative comparison. Come back when you're done."

---

## Step 5: Read the Feedback

When the user is done, read `feedback.json`:
```json
{
  "reviews": [
    {"run_id": "eval-0-with_skill", "feedback": "the chart is missing axis labels"},
    {"run_id": "eval-1-with_skill", "feedback": ""}
  ],
  "status": "complete"
}
```
Empty feedback = user thought it was fine. Focus improvements on test cases with complaints.

Kill the viewer server: `kill $VIEWER_PID 2>/dev/null`

---

## Improving the Skill

**How to think about improvements:**

1. **Generalize from feedback.** The skill will run across many different prompts — avoid overfitting to the test cases. Instead of rigid MUSTs, explain the *why* so the model can reason about edge cases.

2. **Keep the prompt lean.** Read transcripts, not just final outputs. Remove steps that produce unproductive work.

3. **Explain the why.** Today's LLMs have good theory of mind. When given reasoning, they go beyond rote instructions. Reframe ALWAYS/NEVER into explanations of why something matters.

4. **Look for repeated work across test cases.** If all 3 test runs independently wrote a `create_docx.py`, that script should be in `scripts/` and referenced from the skill.

**The iteration loop:**
1. Apply improvements to the skill.
2. Rerun all test cases into `iteration-<N+1>/` (with baselines).
3. Launch reviewer with `--previous-workspace` pointing at prior iteration.
4. Wait for user review; read new feedback; repeat.

Keep going until: user is happy, all feedback is empty, or no meaningful progress.

---

## Advanced: Blind Comparison

For rigorous A/B comparison between two skill versions: give two outputs to an independent agent without revealing which is which; let it judge quality; analyze why the winner won. Read `agents/comparator.md` and `agents/analyzer.md` for details. Optional — most users won't need it; the human review loop is usually sufficient.

---

## Environment-Specific Adaptations

### Claude.ai (no subagents)

- **Test cases**: Run each test prompt yourself (you read the SKILL.md and follow instructions). One at a time. Skip baselines.
- **Results**: If no browser is available, present results directly in conversation. Show prompt + output for each test case. Ask for feedback inline.
- **Benchmarking**: Skip quantitative benchmarking — no baselines means no comparison.
- **Description optimization**: Skip — requires `claude -p` CLI, available only in Claude Code.
- **Blind comparison**: Skip — requires subagents.
- **Packaging**: Works anywhere with Python.

### Cowork (subagents available, no browser)

- Use `--static <output_path>` for the eval viewer (no display). The user downloads `feedback.json` by clicking "Submit All Reviews" in the HTML file.
- Description optimization (`run_loop.py`) works fine — uses `claude -p` via subprocess.
- Packaging works.
- **Reminder**: Even in Cowork, generate the eval viewer BEFORE evaluating inputs yourself.
- **Updating existing skills**: Verify canonical section order before content changes. Preserve the original `name`. Copy to `/tmp/` before editing if the installed path is read-only.
