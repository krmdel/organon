---
name: tool-substack
description: >
  Publish and edit markdown blog posts on Substack as drafts — converts markdown
  to Substack's ProseMirror schema, uploads local images to Substack's CDN,
  pre-renders mermaid diagrams to PNG, and creates or updates drafts via
  Substack's private API. Draft-only by design — publish is always a human click.
  Triggers on: "push to substack", "substack draft", "publish to substack",
  "create substack draft", "send to substack", "substack this post",
  "update substack", "edit substack draft", "list substack drafts".
  Does NOT trigger for: reading existing Substack posts, subscriber
  management, newsletter scheduling. Does NOT publish — only creates/updates
  drafts you review and publish by hand.
---

# tool-substack — Markdown to Substack Draft

Convert a local markdown blog post into a fully-formatted Substack draft with uploaded images, or update an existing draft in place. Ready for human review and publish.

## Outcome

A single command takes a markdown file and produces a Substack draft at `{publication}/publish/post/{id}` with:

- Title and subtitle from frontmatter
- Headings, paragraphs, lists, code blocks, blockquotes, links, bold/italic
- All local images uploaded to Substack's CDN and embedded as `captionedImage` / `image2` nodes
- Fenced mermaid blocks pre-rendered to PNG via `viz-diagram-code` and embedded as images
- Horizontal rules preserved

You then open the draft URL, visually verify, and click Publish yourself. **The skill never publishes automatically.**

## Context Needs

| File | Load level | Purpose |
|------|-----------|---------|
| `.env` | credentials | `SUBSTACK_PUBLICATION_URL`, `SUBSTACK_SESSION_TOKEN`, `SUBSTACK_USER_ID` |
| `context/learnings.md` | `## tool-substack` section | Known friction, manual touch-ups |

## Dependencies

| Name | Required? | What it provides | Without it |
|------|-----------|------------------|------------|
| Python 3.8+ | yes | script runtime | — |
| `markdown-it-py` (pip) | yes | CommonMark parser | fails |
| `requests` (pip) | yes | HTTP client | fails |
| `viz-diagram-code` skill | optional | mermaid → PNG pre-render | fenced mermaid shows as code block |
| `.env` credentials | yes | session auth | fails with extraction guide |

Install: `bash .claude/skills/tool-substack/scripts/setup.sh`

## Step 0: Check credentials

Before any network call, verify all three env vars are set:

```bash
python3 .claude/skills/tool-substack/scripts/substack_ops.py test-auth
```

If any are missing, print the extraction guide (see `references/credentials-guide.md`) and stop. Do NOT guess values. Do NOT proceed.

## Step 1: Understand the request

Ask which markdown file to push if unclear. Default target: the most recent `projects/sci-communication/**/*.md` draft. Confirm the target publication is the sandbox or production Substack — warn if production.

## Step 2: Pre-process mermaid

If the markdown contains ` ```mermaid ` fenced blocks:

1. Offer to pre-render via `viz-diagram-code` (Substack has no mermaid node)
2. If accepted, render each block to PNG, save next to the markdown, replace the fenced block in a **temp copy** of the markdown (never mutate the original) with an image reference
3. If declined, the fenced block ships as a code block labelled `mermaid` — ugly but not broken

## Step 3: Push

```bash
python3 .claude/skills/tool-substack/scripts/substack_ops.py push {markdown_path}
```

The script will:

1. Parse the markdown (frontmatter → `title`, `subtitle`)
2. For each image reference, upload the local PNG to `POST /api/v1/image`, get the CDN URL
3. Convert the body to ProseMirror JSON with CDN URLs substituted
4. POST to `{publication}/api/v1/drafts`
5. Print the draft edit URL

**If any image upload fails**, the script halts before creating the draft. It never ships a draft with broken image refs.

## Step 4: Verify visually

Open the printed draft URL in the browser. Scan top to bottom:

- Title, subtitle correct
- All images rendered at expected positions
- Code blocks have syntax highlighting
- Headings at correct levels
- Links clickable
- No raw markdown leaking through

If something's off, fix the source markdown and use `edit` to update the existing draft in place. Note recurring issues in `context/learnings.md` → `## tool-substack`.

## Step 5: Human publishes

User clicks Publish in the Substack UI. Script is done.

## Safety rules

- Draft only — no programmatic publish
- No mutation of the source markdown (mermaid pre-render uses a temp copy)
- Halt on first image upload failure — never partial-push
- Warn loudly if the target is production, not sandbox
- Credentials never logged, never committed, never printed

## Commands

```bash
# Verify credentials
python3 .claude/skills/tool-substack/scripts/substack_ops.py test-auth

# Convert markdown to ProseMirror JSON (no network — debug)
python3 .claude/skills/tool-substack/scripts/substack_ops.py convert {markdown_path}

# Upload a single image (debug)
python3 .claude/skills/tool-substack/scripts/substack_ops.py upload-image {png_path}

# Full push (creates a new draft)
python3 .claude/skills/tool-substack/scripts/substack_ops.py push {markdown_path}

# List existing drafts (shows id, title, date, edit URL)
python3 .claude/skills/tool-substack/scripts/substack_ops.py list-drafts [--limit N]

# Update an existing draft in place (PUT, re-uploads all images)
python3 .claude/skills/tool-substack/scripts/substack_ops.py edit {draft_id} {markdown_path}
```

## Feedback

Ask after first push: "Did the draft land correctly? Any formatting drift, missing images, or manual touch-ups needed?"

Log answers to `context/learnings.md` → `## tool-substack` with date and specifics.

## Rules

*Updated when the user flags issues. Read before every run.*

## Self-Update

If Substack changes its schema or endpoints — any 4xx/5xx from the API, any rendering drift in the browser — update `## Rules` with the date and the fix, and log to `context/learnings.md`.
