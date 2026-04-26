# /lets-go

The single entry point for Scientific-OS. Detects state and routes accordingly.
Every session starts here — the heartbeat in CLAUDE.md runs this automatically.

## Mode Detection

**First-run mode** if `context/.lets-go-onboarded` is **missing**.
**Returning mode** if it exists.

The marker file is the single source of truth. It is written at the end
of first-run mode (Step 5 below) and never auto-removed — clearing it
means "redo onboarding next session", which a user can do intentionally
by `rm context/.lets-go-onboarded`.

Do NOT use the USER.md template fields to infer first-run state. That
approach used to re-trigger onboarding on every fresh clone because the
template ships with `- Name:` blank, and any user who partially filled
but never completed onboarding would loop. The marker file fixes this:
presence = done, absence = run onboarding.

When the marker is missing but other evidence suggests a partial prior
run (populated USER.md, existing research-profile.md), say so and ask
whether to resume where things left off or start fresh — don't just
blow through onboarding.

## Always (both modes)

1. Read `context/SOUL.md` — how you behave
2. Read `context/USER.md` — who you're helping
3. Read today's / yesterday's `context/memory/*.md` — pay attention to `### Open threads`
4. Create or append today's memory file: `context/memory/{YYYY-MM-DD}.md` per CLAUDE.md's Daily Memory rules
5. Read `context/learnings.md` silently (last 5–10 entries under relevant skill sections)
6. Read `research_context/research-profile.md` and `research_context/research-preferences.md` silently if they exist

---

# First-Run Mode

## Step 0: Create `research_artifacts/` and welcome

**Before asking anything**, create the scaffold at the repo root. Users will drop files flat into `research_artifacts/` and you classify them in Step 0.5. Links are collected in chat, not by hand-editing files.

Use `mkdir -p` via Bash to create:

```
research_artifacts/
  README.md          -- instructions (overwrite each run)
  papers/            -- Claude-managed, published papers and preprints
  manuscripts/       -- Claude-managed, in-progress drafts
  notebooks/         -- Claude-managed, analysis code / Jupyter
  datasets/          -- Claude-managed, data files or pointers
  references/        -- Claude-managed, bibliographies, ref lists
  links.md           -- populated from chat
  notes.md           -- free-form user override
  _processed/        -- archive of ingested files
```

**Write `research_artifacts/README.md`** with a short explainer (what goes where, that classification is automatic, that the folder is gitignored, the supported file types: `.md .txt .pdf .docx .ipynb .csv .xlsx .png .jpg`, and that `/lets-go ingest` can be re-run later to pick up new drops).

**Write `research_artifacts/links.md`** with a minimal header:
```markdown
# Academic links for Scientific-OS to scan
# Populated by Claude during /lets-go. One URL per line. Lines starting with # are comments.
```

**Write `research_artifacts/notes.md`** with a template covering: research focus in your own words, active questions, things you refuse (proprietary tools, closed-access journals, etc.), anything a future session should remember.

**Verify `.gitignore`** contains `/research_artifacts/` anchored to repo root. If not, append it.

**Then show the welcome:**

> Welcome to Scientific-OS. I've created a `research_artifacts/` folder at the repo root.
>
> **Step 1 — get your research materials to me.** Pick whichever is easiest:
>
> - **Drop files into `research_artifacts/`** — any format: PDF, DOCX, MD, TXT, IPYNB, CSV, XLSX, or screenshots.
> - **Drag files into this chat.** Most terminals will insert the file path. I'll copy it into `research_artifacts/` for you.
> - **Paste a path** like `/Users/you/Downloads/my-paper.pdf` and I'll read it directly.
> - **Paste text content** — abstracts, methods sections, notes — I'll save them as a file.
> - **Paste screenshots** of figures or profile pages.
>
> Don't worry about subfolders — I'll read each file, figure out what it is (paper, manuscript, notebook, dataset, reference list), and move it into the right place.
>
> **Minimum useful set:** one recent paper or manuscript of yours. Everything else (notebooks, datasets, reference lists, writing samples) helps me tune every skill to your actual work, but is optional.
>
> **Step 2** — I'll ask for your academic links in chat after your files are in.
>
> **Step 3** — Say `ready` when you're done with files.
>
> Everything stays on your machine. `research_artifacts/` is gitignored.

**WAIT for `ready`.** If the user says they have no files, skip straight to Step 0.25.

**While waiting, handle file paths as they arrive.** Scan each message for:
1. Absolute paths (`/Users/…`, `/home/…`, `~/…`)
2. Drag-inserted paths (may have escaped spaces `\ `)
3. Relative paths (`./`, `../`)

For each path: verify with `test -f "{path}"`, then `cp "{src}" "research_artifacts/{basename}"` (not `mv` — keep the original), confirm briefly: "Copied `{basename}` → `research_artifacts/`. Keep going, or say `ready`."

For **pasted text** that's obviously prose (abstract, methods, notes): ask "Looks like {type}. Save it to `research_artifacts/`? What should I name it?" On confirmation, Write to `research_artifacts/pasted-{type}-{YYYY-MM-DD}.md`.

For **pasted screenshots**: ask "What is this — figure, profile page, handwritten notes?" and save to `research_artifacts/{type}-{YYYY-MM-DD}.png`.

Loop until the user says `ready` / `done` / `continue`, then proceed.

---

## Step 0.25: Collect academic links

Ask in two rounds so you never exceed 4 questions at once.

**Round 1 — core profiles:**

> Now your academic presence. Paste any of these you have (one per line, skip what you don't have):
>
> - ORCID
> - Google Scholar
> - ResearchGate
> - Lab / group website
> - Personal academic page
> - GitHub (if you publish code)
> - Paste all at once, I'll parse.

Parse all URLs. Append to `research_artifacts/links.md` under category headers:

```markdown
# Academic profiles
https://orcid.org/0000-0000-0000-0000
https://scholar.google.com/citations?user=XXXX

# Lab and personal pages
https://lab.example.edu/people/kerem

# Code
https://github.com/krmdel
```

**Round 2 — extras:**

> Anything else I should scan? Specific papers (DOIs or preprint URLs), conference talks, datasets you maintain, a blog, a podcast, or a bioRxiv/arXiv profile? Paste URLs or say `none`.

Append under `# Talks, publications, extras`.

---

## Step 0.5: Ingest and classify

Now read every dropped file, classify it, extract structured data, and scan every link. **Do not skip to profile questions until this is summarised and confirmed.**

### A. Discover and classify files

Glob `research_artifacts/*.{md,txt,pdf,docx,ipynb,csv,xlsx,png,jpg,jpeg}` (top level only — don't re-scan subfolders).

For each file:

1. **Read** it (Read tool handles PDF / DOCX / IPYNB / images).
2. **Classify** into one of:
   - **paper** — has Abstract / Introduction / Methods / Results / Discussion / References sections; DOI; author list; venue metadata; filename contains `paper`/`preprint`/`pmc`/`arxiv`/`biorxiv`.
   - **manuscript** — word count 2k+, in-progress signals (`DRAFT`, `TODO`, `TBD`, review comments), no publication metadata yet, filename contains `manuscript`/`draft`.
   - **notebook** — `.ipynb`, or `.py`/`.R` with rich markdown comments; has cells / code blocks / plotting; filename contains `notebook`/`analysis`/`pipeline`.
   - **dataset** — `.csv`/`.xlsx`/`.parquet`, or README pointing to GEO/TCGA/UniProt/SRA/Zenodo; tabular content.
   - **reference-list** — bibliography, `.bib`, ref list, citation dump.
   - **notes** — freeform markdown without publication structure.
3. **Ambiguous?** Ask: "I see `{filename}`. Is this a {best guess} or {second guess}?" Wait for the answer.
4. **Move** into the matching subfolder: `mv "research_artifacts/{filename}" "research_artifacts/{category}/{filename}"`.
5. **Confirm briefly:** "`{filename}` → {category}".

Never classify `README.md`, `links.md`, `notes.md` — they stay at the top level.

### B. Extract structured data

For each file now in its subfolder:

- **papers/**: title, authors, DOI, venue, year, keywords, methods summary, key finding (1 sentence), dataset/tool mentions. Used to pre-fill research-profile + seed `research-artifacts.md`.
- **manuscripts/**: title, status estimate, target venue if mentioned, main hypotheses / research questions.
- **notebooks/**: languages used, imported libraries (these seed Tool Ecosystem), methods implemented, metrics computed.
- **datasets/**: name, size, organism/domain if inferrable, relevant paper or source.
- **references/**: list of cited works, recurring authors, venue patterns (these hint at preferred journals).
- **notes/**: treated as authoritative override — applied last.

### C. Scan links from `research_artifacts/links.md`

For each non-comment URL:

1. **Try WebFetch first.** Works for ORCID public pages, Scholar profiles, GitHub, lab pages, personal sites, DOIs that resolve to publisher landing pages, bioRxiv/arXiv abstracts.
2. **ORCID** — extract employment, education, works list, keywords.
3. **Google Scholar** — extract publications (title + venue + year), citation count, h-index, co-authors.
4. **ResearchGate** — often bot-blocked. If WebFetch fails, skip with a note and ask the user to paste their top 3 paper titles.
5. **Lab / personal sites** — extract bio, research themes, group members, recent news, publication list.
6. **GitHub** — profile page + top pinned repos: languages, stars, descriptions, last commit date.
7. **bioRxiv / arXiv / DOI landing pages** — abstract, authors, date, venue.

**Firecrawl fallback:** if WebFetch returns empty / login-wall / JS-heavy content, check `.env` for `FIRECRAWL_API_KEY`:
- **Present** → run `tool-firecrawl-scraper` with the URL. Extract same fields.
- **Missing** → tell the user once: "`{url}` needs a stronger scraper. Add `FIRECRAWL_API_KEY` to `.env` (free tier at firecrawl.dev — 500 credits/month) and I'll retry. For now I'll work with what I have."

Never block on a single failed link. Log failures to a running list.

### D. Read `research_artifacts/notes.md` last

This wins over anything inferred elsewhere.

### E. Summarize and confirm

Show a compact summary:

> Here's what I pulled from `research_artifacts/`:
>
> **Files:**
> - {filename} → paper ({title}, {venue} {year}, methods: {short})
> - {filename} → notebook ({main methods / libraries})
> - {filename} → dataset ({name})
> - … etc
>
> **Links scanned:**
> - ORCID: {name}, {N works}, {affiliation}
> - Scholar: {N publications}, h-index {N}
> - Lab page: {group name}, {research themes}
> - GitHub: {N repos, main languages}
>
> **Scan failures:** {list or "none"}
>
> **notes.md:** {key points or "empty"}
>
> Anything I misclassified or missed before I build your profile?

**WAIT for confirmation or corrections.** Then move processed files to `research_artifacts/_processed/{YYYY-MM-DD}/{category}/` preserving structure — do not delete originals. Append scanned URLs to `research_artifacts/_processed/scanned-links.txt`.

---

## Step 1: Core Identity

**Pre-fill everything you already know** from ORCID / Scholar / lab page / paper metadata. Only ask what's still missing.

> Quick intro — I've got {name}, {affiliation} from your {source}. Confirm your current role: PhD Student, Postdoc, Assistant Prof, Associate Prof, Full Prof, Research Scientist, Industry Researcher, or something else?

Extract: **Name**, **Institution**, **Department**, **Career Stage**.

If career stage is already in ORCID employment → skip the question, just confirm.

---

## Step 2: Research Focus

**Pre-fill from papers + lab page.** Show what you inferred and ask them to keep / edit / add.

> Based on your papers I'd frame your focus as:
>
> - **Primary field:** {inferred}
> - **Subfields:** {list}
> - **Keywords:** {list}
> - **Active questions (top 3):**
>   1. {inferred from most recent paper / manuscript}
>   2. {inferred}
>   3. {inferred}
>
> Keep, edit, or add to each. One message is fine.

---

## Step 3: Preferences

> How should I handle writing for you?
>
> 1. **Preferred journals** (for lit search + submission targeting) — your references show {inferred list}, keep?
> 2. **Citation style** — APA / Nature / IEEE / Vancouver / Chicago / other?
> 3. **Writing conventions** — voice (active / passive), Oxford comma, US / UK English, anything else I should lock in?

Parse each numbered reply.

---

## Step 4: Tool Ecosystem

> Your notebooks show {inferred languages / libraries}. Confirm and fill gaps:
>
> - **Languages:** {inferred}
> - **Statistical tools:** {inferred or "?"}
> - **Databases / corpora:** {inferred from paper mentions or "?"}
> - **Workflow / infra:** Nextflow, Snakemake, Docker, HPC, other?

---

## Step 5: Populate `context/USER.md`

Overwrite the template with actual data. Use the structure:

```markdown
# USER.md

## About
- **Name:** {name}
- **Affiliation:** {institution} — {department}
- **Career Stage:** {stage}
- **Website / ORCID:** {links}

## Research Identity
- **Focus:** {1-sentence summary}
- **Active Questions:** {top 3}
- **Methods:** {computational / wet-lab / mixed}

## Working Style
- **Approach:** {data-first / hypothesis-first / iterative} — observed from conversation
- **Output preferences:** {citation style, voice, figure style}

## Notes
- {anything from notes.md, timezone, constraints}

---
*Populated by /lets-go on {date}. Update via `/lets-go update` or ask me to change it.*
```

---

## Step 6: Write `research_context/` files

Create the `research_context/` directory if missing, then write three files.

**`research_context/research-profile.md`** — full schema from `sci-research-profile/references/profile-schema.md`. Fill every section from Steps 1-4. Unknown fields → `Not specified` (downstream skills treat this as absent and fall back to generic behaviour).

**`research_context/research-artifacts.md`** — indexed list of everything ingested in Step 0.5:

```markdown
# Research Artifacts Index

## Published Papers
- **{title}** ({year}) — {venue} — DOI: {doi}
  - Methods: {short}
  - Key finding: {1 sentence}

## Manuscripts in Progress
- **{title}** — {status estimate}
  - Target venue: {venue or "?"}

## Notebooks & Code
- **{filename}** — {languages}, {libraries}, {methods}

## Datasets
- **{name}** — {size or source}

## External links
- ORCID: {url}
- Scholar: {url}
- GitHub: {url}
- Lab: {url}
```

**`research_context/research-preferences.md`:**

```markdown
# Research Preferences

## Journals
{list or "any"}

## Citation style
{style}

## Writing conventions
{voice, language variant, conventions}

## Tool preferences
- **Prefer:** {list}
- **Avoid:** {list or "none"}

## Access constraints
{open-access only / proprietary OK / anything else}

## Publication timeline
{target submission window or "none"}
```

Also ensure `context/learnings.md` has `## sci-research-profile` and a section per installed skill under `# Individual Skills` — create empty sections if missing.

---

## Step 7: Environment check

Scan `.env.example` for documented keys. Check which are present in `.env`. List missing ones **once, without blocking**:

> A few optional integrations available. None are required — everything works without them, they just unlock extras:
>
> - `FIRECRAWL_API_KEY` — advanced scraping for JS-heavy academic sites (free 500/mo at firecrawl.dev)
> - `OPENAI_API_KEY` — Reddit / community signal extraction with real engagement metrics
> - `GEMINI_API_KEY` — scientific illustrations via `viz-nano-banana`
> - … (scan `.env.example`, mention only the ones that are missing)

Skip the whole step silently if everything is present.

---

## Step 8: Show results and skill showcase

Show actual excerpts, not just filenames:

> Here's what I built:
>
> **Your research profile:** {2-sentence excerpt — field, active questions}
> **Your artifacts:** {N papers, N manuscripts, N notebooks indexed}
> **Your preferences:** {citation style, preferred journals, tools}
>
> Everything's saved in `research_context/` and `context/USER.md`.

Then scan `.claude/skills/` dynamically, group by category (Research & Discovery / Data & Analysis / Writing & Communication / Visualization / Utility / Meta), and present what's available **framed around this specific researcher's work**:

```
Here's what I can do for your research:

**Research & Discovery**
- sci-literature-research — {tuned description mentioning their field}
- sci-trending-research — {tuned description}

**Data & Analysis**
- sci-data-analysis — {tuned}
- sci-hypothesis — {tuned}

**Writing & Communication**
- sci-writing — {tuned}
- sci-communication — {tuned}

**Visualization**
- viz-nano-banana, viz-diagram-code, viz-excalidraw-diagram, viz-presentation

**Management**
- sci-research-mgmt — notes, milestones, pipelines
```

End with **one** recommendation:

> Given you're {specific situation from profile}, I'd start with {skill} — {concrete reason}.

Do **not** present a menu and ask them to pick. Recommend.

## Step 9: Mark onboarding complete (H2)

**Write the first-run marker** `context/.lets-go-onboarded` with a
single line: the ISO-8601 timestamp of completion plus the git SHA
this onboarding ran against. Example contents:

```
2026-04-14T12:34:56Z f600cfc
```

The presence of this file is how **Mode Detection** tells first-run
from returning on the next session — do NOT skip this step. If the
marker already exists from a partial prior run, overwrite it; the new
content records the most recent successful onboarding.

---

# Returning Mode

## Step 1: Silent context load

(Already loaded by the "Always" block above — SOUL, USER, memory, learnings, profile, preferences.)

Additional checks:
- **Stale profile?** If `research_context/research-profile.md` is > 30 days old → note once at the end, don't block.
- **Unprocessed drops?** If `research_artifacts/` has files at the top level not in `_processed/` → surface: "New files in `research_artifacts/` — want me to ingest them first?"
- **Open threads from last session** → pull from the last memory block's `### Open threads`.
- **Bib-audit banner** → if `cron/status/sci-writing-bib-audit.json` exists, read it. If `result` is not `"success"` or `fail_count > 0`, surface a one-line warning: `⚠ Citation audit last ran {last_run} — result: {result}`. Also glob `projects/sci-writing/bib-audit_*.md` and pick the most recent file; if it exists, extract the Summary totals (Total CRITICAL / Total MAJOR) and surface them as: `Citation audit {date}: {N} CRITICAL, {N} MAJOR findings` (skip silently when count is 0/0). Never block work — this is informational only.

## Step 2: Recap + capabilities + goal question

Open with three things, short:

**1. Last session recap (1-2 sentences)** — pull from most recent `context/memory/*.md`. What was worked on, what was produced, any open threads. Skip if no memory.

**2. High-level capabilities (2-5 lines, grouped by outcome not skill name)** — scan installed skills, translate to plain language:

```
Right now I can help with:
- Research & discovery — literature search, trending topics, hypothesis work
- Data & analysis — statistical tests, plots, data cleaning
- Writing — manuscripts, blog posts, slide decks
- Visual output — diagrams, illustrations, presentations
- Management — notes, projects, scheduling, pipelines
```

Only show categories with ≥1 installed skill. If only foundation + meta are installed, keep it to one line.

**3. Goal question** — contextual:
- If open threads exist: "Want to pick up {open thread}, or something different?"
- If session recap exists: "Keep going on {last work}, or new direction?"
- Otherwise: "What are you working on today?"

## Step 3: Route or recommend

- **Clear task stated** → route to the matching skill per CLAUDE.md Task Routing, print the skill routing notice, execute.
- **Unsure** → recommend the highest-leverage next step based on open threads, stale scans, or patterns in `context/learnings.md`. Don't present a skill menu.

Mention stale files or gaps only if directly relevant to the stated goal. Frame as opportunity, not failure.

**Do NOT:**
- Summarise their research profile back to them unprompted
- Default to recommending profile refreshes
- List individual skill names unless asked
- Block work because research context is missing

---

# Anti-Patterns

1. Never ask more than 4 questions before doing work.
2. Never present all questions at once — ask one, wait, then the next.
3. Never present a skill menu — recommend, don't ask.
4. Never rebuild `research_context/` without explicitly asking first.
5. Never give generic recommendations — tie them to the specific research.
6. Never silently produce generic output when context is missing — note the gap once with opportunity framing.
7. Never use a hardcoded skill list — always scan `.claude/skills/` dynamically.
8. Never claim partial scraped data is complete. If WebFetch returned a login wall or empty body, say so and ask for the Firecrawl key or a paste.
9. Never delete anything from `research_artifacts/`. Move to `_processed/`, keep originals.
10. Frame gaps as opportunities, not failures.
