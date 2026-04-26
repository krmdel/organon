---
name: tool-firecrawl-scraper
description: >
  Convert websites into LLM-ready data with Firecrawl API. Scrape, crawl,
  map, search, extract, agent, batch, change tracking, and branding
  extraction. Handles JavaScript rendering, anti-bot bypass, PDF/DOCX
  parsing. Requires FIRECRAWL_API_KEY in .env. Used by other skills
  (sci-communication, sci-trending-research) as a scraping backend when
  default web tools fail. Use when: scraping websites, crawling sites,
  web search + scrape, autonomous data gathering, monitoring content
  changes, extracting structured data. Does NOT trigger for general
  browsing or simple URL fetching that WebFetch can handle.
---

# Firecrawl Web Scraper

**API Version**: v2 | **Python SDK**: firecrawl-py 4.13.0+ | **JS SDK**: @mendable/firecrawl-js 4.11.1+

## Outcome

Website content converted into clean markdown, structured JSON, or extracted data. This skill is both **standalone** (user asks to scrape) and a **backend for other skills** (e.g., `sci-communication` for URL-based content).

## Context Needs

| File | Load level | Purpose |
|------|-----------|---------|
| `context/learnings.md` | `## tool-firecrawl-scraper` section | Known issues, cost patterns |

No research_context files needed — this is a utility skill.

## Step 1: Check API Key

Requires `FIRECRAWL_API_KEY` in `.env` (get one at https://www.firecrawl.dev/app).

**Before any Firecrawl call**, check `.env` for the key. If missing, follow the External Services rules in CLAUDE.md:
1. Explain what Firecrawl would do for this specific task
2. Tell them how to get it: "Add `FIRECRAWL_API_KEY=fc-your-key` to your `.env` file. Free tier at firecrawl.dev gives 500 credits/month."
3. Offer the fallback: what can be done without it (WebFetch, manual paste, etc.)
4. Don't block — proceed with the fallback if they don't add the key

## Step 2: Choose the Right Endpoint

| Endpoint | Purpose | Credits | When to use |
|----------|---------|---------|-------------|
| `scrape` | Single page → markdown/HTML/JSON | 1 (5 stealth) | Articles, product pages, about pages |
| `crawl` | Full site | 1/page | Docs sites, archives |
| `map` | URL discovery (no content) | 1 | Sitemap discovery, crawl planning |
| `search` | Web search + optional scrape | 2/10 results | Research with live data |
| `extract` | Structured data with schema | 5/page | Prices, contacts, specs |
| `agent` | Autonomous AI gathering | Dynamic | No URLs known, complex tasks |
| `batch-scrape` | Multiple URLs | 1/page | Bulk processing |
| `branding` | Brand identity extraction | 1 | Colors, fonts, logos, brand traits |

For detailed API usage, code examples, and parameters, read `references/api-guide.md`.

## Step 3: Execute the Request

Always prefer the cheapest approach:
1. Try `WebFetch` first (free) — only fall back to Firecrawl if it fails
2. Use cache defaults (2-day) for static content; `max_age=0` only for real-time data
3. Use `map` before `crawl` to scope the job and avoid over-crawling
4. Batch URLs together with `batch-scrape` instead of individual scrapes

For branding extraction (key capability for brand-related skills):
```python
doc = app.scrape(url="https://example.com", formats=["branding"])
```
Read `references/api-guide.md` § Branding Extraction for full details.

## Step 4: Validate and Return

Before processing results:
1. Use auto mode (default) — only charges stealth credits if basic fails
2. Validate content isn't an error page before processing
3. Check `success` field in response, not just HTTP status

For the full list of 10 known issues and their solutions, read `references/known-issues.md`.

Read `references/known-issues.md` § Stealth Mode Pricing for credit cost details.

---

## Rules

*Updated automatically when the user flags issues. Read before every run.*

---

## Self-Update

If the user flags an issue — wrong endpoint, bad code, cost surprise — update the `## Rules` section immediately with the correction and today's date.

---

## Troubleshooting

- **WebFetch works fine**: Don't use Firecrawl. It's for JS-heavy sites, bot protection, and structured extraction.
- **Stealth mode surprise**: Auto mode tries basic first, only charges stealth credits if basic fails. Read `references/known-issues.md` for details.
- **Empty content returned**: The page may be behind authentication or geo-restricted. Check the `success` field and error message.
- **High credit usage on crawl**: Always run `map` first to see the site structure and scope the crawl.
