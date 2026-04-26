# Firecrawl Known Issues

10 documented issues with prevention strategies. Read before any Firecrawl integration.

---

## Issue #1: Stealth Mode Pricing Change (May 2025)

**Error**: Unexpected credit costs when using stealth mode
**Why**: Stealth costs **5 credits per request** (was included in standard pricing)
**Fix**: Use auto mode (default) — only charges stealth credits if basic fails

```python
# RECOMMENDED: auto mode (default)
doc = app.scrape(url, formats=['markdown'])

# Or conditionally enable stealth
try:
    doc = app.scrape(url, formats=['markdown'], proxy='basic')
except Exception as e:
    if e.status_code in [401, 403, 500]:
        doc = app.scrape(url, formats=['markdown'], proxy='stealth')
```

Options: `auto` (default, 5 credits only if stealth needed) | `basic` (1 credit) | `stealth` (5 credits always)

---

## Issue #2: v2.0.0 Method Renames

**Error**: `AttributeError: 'FirecrawlApp' object has no attribute 'scrape_url'`
**Fix**: Use v2 method names

| Old (v1) | New (v2) |
|----------|----------|
| `scrape_url()` | `scrape()` |
| `crawl_url()` | `crawl()` / `start_crawl()` |
| `asyncCrawlUrl()` | `startCrawl()` |
| `checkCrawlStatus()` | `getCrawlStatus()` |

---

## Issue #3: v2.0.0 Format Changes

**Error**: `'extract' is not a valid format`
**Fix**: `"extract"` renamed to `"json"` in v2

```python
# v2 JSON extraction
doc = app.scrape(
    url="https://example.com",
    formats=[{"type": "json", "prompt": "Extract title"}]
)

# v2 Screenshot as object
formats=[{"type": "screenshot", "fullPage": True, "quality": 80}]
```

---

## Issue #4: v2.0.0 Crawl Parameter Renames

**Error**: `'allowBackwardCrawling' is not a valid parameter`
**Fix**: Use new parameter names

| Old | New |
|-----|-----|
| `allowBackwardCrawling` | `crawlEntireDomain` |
| `maxDepth` | `maxDiscoveryDepth` |
| `ignoreSitemap` (bool) | `sitemap` ("only" / "skip" / "include") |

---

## Issue #5: v2.0.0 Default Behavior Changes

**Error**: Stale cached content returned unexpectedly
**Why**: `maxAge` defaults to 2 days in v2 (cached by default). `blockAds`, `skipTlsVerification`, `removeBase64Images` enabled by default.

```python
# Force fresh data
doc = app.scrape(url, formats=['markdown'], max_age=0)

# Disable cache entirely
doc = app.scrape(url, formats=['markdown'], store_in_cache=False)
```

---

## Issue #6: Job Status Race Condition

**Error**: `"Job not found"` when checking crawl status immediately after creation
**Why**: Database replication delay
**Fix**: Wait 1-3 seconds before first status check

```python
import time

job = app.start_crawl(url="https://docs.example.com")
time.sleep(2)  # Required delay
status = app.get_crawl_status(job.id)
```

---

## Issue #7: DNS Errors Return HTTP 200

**Error**: DNS failures return `success: false` with HTTP 200
**Fix**: Check `success` field, not HTTP status

```typescript
const result = await app.scrape('https://nonexistent.com');
if (!result.success) {
    if (result.code === 'SCRAPE_DNS_RESOLUTION_ERROR') {
        console.error('DNS resolution failed');
    }
    throw new Error(result.error);
}
```

Note: DNS errors still charge 1 credit.

---

## Issue #8: Bot Detection Still Charges Credits

**Error**: Cloudflare error page returned as "successful" scrape
**Fix**: Validate content isn't an error page

```python
doc = app.scrape(url="https://protected-site.com", formats=["markdown"])

if "cloudflare" in doc.markdown.lower() or "access denied" in doc.markdown.lower():
    doc = app.scrape(url, formats=["markdown"], stealth=True)
```

Cost: Basic charges 1 credit even on failure, stealth retry adds 5 credits.

---

## Issue #9: Self-Hosted Anti-Bot Weakness

**Error**: `"All scraping engines failed!"`
**Why**: Self-hosted lacks advanced anti-fingerprinting present in cloud service
**Fix**: Use Firecrawl cloud for sites with strong anti-bot measures

---

## Issue #10: Cache Performance

**Problem**: Not leveraging cache makes requests up to 500% slower
**Fix**: Match cache strategy to content type

```python
# Real-time data (prices, stock)
doc = app.scrape(url, formats=["markdown"], max_age=0)

# News/blogs (10-minute cache)
doc = app.scrape(url, formats=["markdown"], max_age=600000)

# Static content (use default 2-day cache)
doc = app.scrape(url, formats=["markdown"])

# One-time scrape
doc = app.scrape(url, formats=["markdown"], store_in_cache=False)
```
