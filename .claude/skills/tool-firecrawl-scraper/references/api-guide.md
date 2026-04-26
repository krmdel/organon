# Firecrawl API Guide

**Official Docs**: https://docs.firecrawl.dev
**API Version**: v2
**SDK Versions**: firecrawl-py 4.13.0+, @mendable/firecrawl-js 4.11.1+

---

## Setup

```python
from firecrawl import Firecrawl
import os

app = Firecrawl(api_key=os.environ.get("FIRECRAWL_API_KEY"))
```

```typescript
import FirecrawlApp from '@mendable/firecrawl-js';
const app = new FirecrawlApp({ apiKey: process.env.FIRECRAWL_API_KEY });
```

---

## 1. Scrape (`/v2/scrape`)

Single page → clean structured content.

### Basic

```python
doc = app.scrape(
    url="https://example.com/article",
    formats=["markdown", "html"],
    only_main_content=True
)
print(doc.markdown)
print(doc.metadata)
```

### Output Formats

| Format | Description |
|--------|-------------|
| `markdown` | LLM-optimized content |
| `html` | Full HTML |
| `rawHtml` | Unprocessed HTML |
| `screenshot` | Page capture |
| `links` | All URLs on page |
| `json` | Structured data extraction |
| `summary` | AI-generated summary |
| `branding` | Design system data |
| `changeTracking` | Content change detection |

### Advanced Options

```python
doc = app.scrape(
    url="https://example.com",
    formats=["markdown", "screenshot"],
    only_main_content=True,
    remove_base64_images=True,
    wait_for=5000,           # Wait 5s for JS
    timeout=30000,
    location={"country": "AU", "languages": ["en-AU"]},
    max_age=0,               # Fresh content (no cache)
    store_in_cache=True,
    stealth=True,            # For complex sites (5 credits)
    headers={"User-Agent": "Custom Bot 1.0"}
)
```

### Browser Actions

```python
doc = app.scrape(
    url="https://example.com",
    actions=[
        {"type": "click", "selector": "button.load-more"},
        {"type": "wait", "milliseconds": 2000},
        {"type": "scroll", "direction": "down"},
        {"type": "write", "selector": "input#search", "text": "query"},
        {"type": "press", "key": "Enter"},
        {"type": "screenshot"}
    ]
)
```

### JSON Mode (Structured Extraction)

```python
# With schema
doc = app.scrape(
    url="https://example.com/product",
    formats=["json"],
    json_options={
        "schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "price": {"type": "number"},
                "in_stock": {"type": "boolean"}
            }
        }
    }
)

# Prompt-only (no schema)
doc = app.scrape(
    url="https://example.com/product",
    formats=["json"],
    json_options={
        "prompt": "Extract the product name, price, and availability"
    }
)
```

### Branding Extraction

Extract design system and brand identity:

```python
doc = app.scrape(
    url="https://example.com",
    formats=["branding"]
)

# Returns:
# - Color schemes and palettes
# - Typography (fonts, sizes, weights)
# - Spacing and layout metrics
# - UI component styles
# - Logo and imagery URLs
# - Brand personality traits
```

---

## 2. Crawl (`/v2/crawl`)

All accessible pages from a starting URL.

```python
result = app.crawl(
    url="https://docs.example.com",
    limit=100,
    max_depth=3,
    allowed_domains=["docs.example.com"],
    exclude_paths=["/api/*", "/admin/*"],
    scrape_options={
        "formats": ["markdown"],
        "only_main_content": True
    }
)

for page in result.data:
    print(f"Scraped: {page.metadata.source_url}")
```

### Async Crawl

```python
job = app.start_crawl(
    url="https://docs.example.com",
    limit=1000,
    webhook="https://your-domain.com/webhook"
)
print(f"Job ID: {job.id}")

# Poll for status
status = app.check_crawl_status(job.id)
```

---

## 3. Map (`/v2/map`)

Discover all URLs on a site without scraping content.

```python
urls = app.map(url="https://example.com")
print(f"Found {len(urls)} pages")
```

Use for: sitemap discovery, crawl planning, website audits.

---

## 4. Search (`/search`)

Web search + optional scrape in one operation.

```python
# Basic search
results = app.search(query="React server components", limit=10)

# Search + scrape results
results = app.search(
    query="React server components tutorial",
    limit=5,
    scrape_options={"formats": ["markdown"], "only_main_content": True}
)

# With filters
results = app.search(
    query="machine learning papers",
    limit=20,
    sources=["web", "news"],
    categories=["github", "research", "pdf"],
    location={"country": "US"},
    tbs="qdr:m",  # Past month (h=hour, d=day, w=week, y=year)
    timeout=30000
)
```

Cost: 2 credits per 10 results + scraping costs if enabled.

---

## 5. Extract (`/v2/extract`)

AI-powered structured data extraction.

```python
from pydantic import BaseModel

class Product(BaseModel):
    name: str
    price: float
    description: str
    in_stock: bool

# Single page
result = app.extract(
    urls=["https://example.com/product"],
    schema=Product,
    system_prompt="Extract product information"
)

# Domain-wide (wildcard)
result = app.extract(
    urls=["example.com/*"],
    schema=Product,
    system_prompt="Extract all products"
)

# Prompt-only (no schema)
result = app.extract(
    urls=["https://example.com/about"],
    prompt="Extract company name, founding year, and key executives"
)
```

---

## 6. Agent (`/agent`)

Autonomous web data gathering without requiring specific URLs.

```python
result = app.agent(
    prompt="Find pricing for top 3 headless CMS platforms and compare features"
)

# With schema
result = app.agent(
    prompt="Find pricing for Contentful, Sanity, and Strapi",
    schema=CMSPricing
)

# Focus on specific URLs
result = app.agent(
    prompt="Extract enterprise pricing details",
    urls=["https://contentful.com/pricing", "https://sanity.io/pricing"]
)
```

Models: `spark-1-mini` (default, cheaper) | `spark-1-pro` (complex tasks, 60% more)

Note: Research Preview. 5 free daily requests, then credit-based.

---

## 7. Batch Scrape

Multiple URLs in a single operation.

```python
results = app.batch_scrape(
    urls=["https://example.com/page1", "https://example.com/page2"],
    formats=["markdown"],
    only_main_content=True
)

# Async with webhook
job = app.start_batch_scrape(
    urls=url_list,
    formats=["markdown"],
    webhook="https://your-domain.com/webhook"
)
```

---

## 8. Change Tracking

Monitor content changes over time.

```python
doc = app.scrape(
    url="https://example.com/pricing",
    formats=["markdown", "changeTracking"]
)

print(doc.change_tracking.status)  # new, same, changed, removed
print(doc.change_tracking.diff)    # Line-by-line changes (diff mode)
```

Modes: `diff` (git-diff style, default) | `json` (structured comparison, 5 credits)

---

## Cloudflare Workers

SDK cannot run in Workers. Use REST API directly:

```typescript
const response = await fetch('https://api.firecrawl.dev/v2/scrape', {
    method: 'POST',
    headers: {
        'Authorization': `Bearer ${env.FIRECRAWL_API_KEY}`,
        'Content-Type': 'application/json',
    },
    body: JSON.stringify({ url, formats: ['markdown'], onlyMainContent: true })
});
```

---

## Pricing

| Tier | Credits/Month | Price |
|------|---------------|-------|
| Free | 500 | $0 |
| Hobby | 3,000 | $19/mo |
| Standard | 100,000 | $99/mo |
| Growth | 500,000 | $399/mo |

**Credit costs**: Scrape 1 (basic) / 5 (stealth) | Crawl 1/page | Search 2/10 results | Extract 5/page | Agent dynamic | Change Tracking JSON +5

---

## Official Links

- Docs: https://docs.firecrawl.dev
- Python SDK: https://docs.firecrawl.dev/sdks/python
- Node.js SDK: https://docs.firecrawl.dev/sdks/node
- API Reference: https://docs.firecrawl.dev/api-reference
- GitHub: https://github.com/mendableai/firecrawl
- Dashboard: https://www.firecrawl.dev/app
