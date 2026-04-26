# Skill Writing Guide

Reference for writing high-quality SKILL.md files. Read when creating or editing a skill.

---

## Anatomy of a Skill

```
skill-name/
├── SKILL.md (required)
│   ├── YAML frontmatter (name, description required)
│   └── Markdown instructions
└── Bundled Resources (optional)
    ├── scripts/    - Executable code for deterministic/repetitive tasks
    ├── references/ - Docs loaded into context as needed
    └── assets/     - Example outputs, design references, templates, icons, fonts
```

---

## Progressive Disclosure

Skills use a three-level loading system:
1. **Metadata** (name + description) — always in context (~100 words)
2. **SKILL.md body** — in context whenever skill triggers (keep under 200 lines)
3. **Bundled resources** — loaded as needed (unlimited; scripts can run without loading)

**Key patterns:**
- Keep SKILL.md under 200 lines. Move detail to `references/` with explicit pointers.
- Reference files clearly from SKILL.md with guidance on when to read them.
- For large reference files (>300 lines), include a table of contents.

**Domain organisation:** When a skill supports multiple domains/frameworks:
```
cloud-deploy/
├── SKILL.md (workflow + selection)
└── references/
    ├── aws.md
    ├── gcp.md
    └── azure.md
```
Claude reads only the relevant reference file.

---

## Process Step Design

For each step in the skill's methodology, decide:

1. **Human-in-the-loop?** Default autonomous for data gathering and analysis. Default HITL for creative decisions, tone choices, and anything that commits to a direction (e.g., "pick an angle", "approve the voice profile").

2. **Reference files needed?** If yes, create `references/<topic>.md` and point to it: "Read `references/methodology.md` for the full set."

3. **Output format?** Be specific: a markdown file, JSON block, list of options, edit to an existing file. Define in SKILL.md or in a reference file if complex.

4. **Example outputs?** If yes, save to `assets/` and reference from the step: "Match the format shown in `assets/carousel-example.pdf`."

---

## Example Outputs & Design Assets

Every output-producing skill should capture examples in `assets/`. These become the quality benchmark.

During skill creation, ask: "Do you have examples of what great output looks like?"
- Yes → save to `assets/` with descriptive filenames; reference them in SKILL.md.
- No → note in SKILL.md that examples should be added after the first good output.

**What goes in assets/:**
- **Example outputs** — finished deliverables representing the quality bar
- **Design references** — style guides, colour palettes, layout templates
- **Templates** — reusable structures the skill fills in

After a great output, offer: "Want me to save this to the skill's assets folder as a reference for next time?"

---

## Writing Patterns

Prefer the imperative form in instructions.

**Defining output formats:**
```markdown
## Report structure
ALWAYS use this exact template:
# [Title]
## Executive summary
## Key findings
## Recommendations
```

**Examples pattern:**
```markdown
## Commit message format
**Example 1:**
Input: Added user authentication with JWT tokens
Output: feat(auth): implement JWT-based authentication
```

---

## Writing Style

- Explain *why* things are important rather than issuing heavy-handed MUSTs.
- Use theory of mind — make the skill general, not narrow to specific examples.
- Write a draft, then read it with fresh eyes and improve.
- If you find yourself writing ALWAYS/NEVER in all caps, try reframing as reasoning instead.

---

## Principle of Least Surprise

Skills must not contain malware, exploit code, or content that could compromise system security. A skill's contents should not surprise the user in intent. Don't create misleading skills or skills designed to facilitate unauthorized access, data exfiltration, or other malicious activities.

---

## Auto-Setup Convention

Skills needing binaries (`uv`, `yt-dlp`, `ffmpeg`, etc.) include `scripts/setup.sh` that:
- Checks `command -v` first
- Prefers `brew` on macOS with `curl`/`pip` fallback
- Reports per-dependency status
- Never asks for user interaction
- Runs once per machine

---

## Updating an Existing Skill

- **Verify canonical section order first** (before any content changes). Fix structural deviations before addressing the requested changes.
- **Preserve the original name.** Note the directory name and `name` frontmatter — use them unchanged.
- **Copy to a writeable location before editing** if the installed path may be read-only: `cp -r <skill-path> /tmp/skill-name/`, edit there, package from the copy.
