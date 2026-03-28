# Guide: Building a Crawler for a New Province (Tier 4)

This guide explains how to add a new non-gkmlpt government site to the corpus.
Use this when expanding to provinces like Zhejiang, Shanghai, Beijing, Jiangsu, etc.
that have their own custom CMS platforms.

## Architecture Overview

```
crawlers/
  base.py          # Shared: DB schema, HTTP, storage (DO NOT MODIFY)
  gkmlpt.py        # Guangdong gkmlpt platform (25 sites, 1 crawler)
  ndrc.py          # NDRC ministry crawler (reference for custom sites)
  gov.py           # State Council crawler (reference for JSON-feed sites)
  mof.py           # Ministry of Finance crawler (HTML + PDF sections)
  mee.py           # Ministry of Ecology and Environment crawler
  your_new.py      # <-- You add this
```

Every crawler imports from `crawlers/base.py` and uses:
- `init_db()` — opens SQLite, creates tables if needed
- `fetch(url)` / `fetch_json(url)` — HTTP with retries + rate limiting
- `store_site(conn, site_key, site_cfg)` — register in `sites` table
- `store_document(conn, site_key, doc)` — upsert into `documents` table
- `save_raw_html(site_key, doc_id, html)` — archive original HTML
- `next_id(conn)` — generate a unique doc ID (for sites without their own)
- `show_stats(conn)` — print DB summary
- `REQUEST_DELAY = 0.5` — seconds between requests (be polite)

## Step-by-Step Process

### Step 1: Recon the target site (30-60 min)

Open the province's government disclosure portal in Chrome. Navigate to the
policy documents section (look for 政策文件, 政府文件, 规范性文件, 政府信息公开).

Open DevTools → Network tab. Then:

1. **Find the listing page URL.** Click through the policy sections.
   Note the URL pattern. Common patterns:
   - Path-based pagination: `/xxgk/zcfb/index.html`, `/xxgk/zcfb/index_1.html`
   - Query-param pagination: `/xxgk/list?page=1&size=20`
   - JSON API: look for XHR requests returning JSON in the Network tab

2. **Check for a JSON API.** Filter Network tab by "XHR" or "Fetch".
   Many sites load content via AJAX even if the page looks static.
   Look for URLs like:
   - `/api/public/...`
   - `/jpaas-httpapi/...`
   - `/inteligent/...`
   - `*.json` files

   **If you find a JSON API, that's the best case.** You can skip HTML parsing
   for listings entirely. See `crawlers/gov.py` for an example.

3. **Identify pagination.** On the listing page, look for:
   - `createPageHTML(totalPages, currentPage, ...)` in the HTML source
   - A page count in the UI ("共 X 页")
   - Next/prev links
   - Infinite scroll (check XHR requests as you scroll)

4. **Check the document detail page.** Click a document and note:
   - URL pattern (e.g., `/zhengce/content/2026-01/15/content_123456.htm`)
   - Where the body text lives (inspect element → find the container div)
   - Where metadata lives (look for `<meta>` tags, structured tables, or JSON-LD)
   - Document number (文号) location — often in a metadata table or the title

5. **Document your findings.** Write them down before coding. Example:

```
Site: Zhejiang Province (www.zj.gov.cn)
Listing: GET /art/2026/1/1/art_1229738896_59046498.html (static HTML)
Pagination: createPageHTML(N, idx, "art_...", "html") → path-based
Detail URL: /art/2026/3/10/art_1229543658_12345678.html
Body: div#zoom > div.content
Metadata: <meta name="ArticleTitle"> etc., plus table.xxgk_table
Doc number: in metadata table row "发文字号"
```

### Step 2: Create the crawler module (~2-4 hours)

Create `crawlers/your_site.py`. Use `crawlers/ndrc.py` as your template.

**Required structure:**

```python
"""
Province Name (省名) crawler.

Crawls policy documents from www.example.gov.cn.
[Describe the site structure briefly.]

Usage:
    python -m crawlers.your_site                # Crawl all sections
    python -m crawlers.your_site --stats        # Show database stats
    python -m crawlers.your_site --list-only    # List without fetching bodies
"""

import argparse
import re
import time
from urllib.parse import urljoin

from crawlers.base import (
    REQUEST_DELAY, fetch, fetch_json, init_db, log,
    next_id, save_raw_html, show_stats, store_document, store_site,
)

SITE_KEY = "zj"  # Short unique key — used in DB and URLs
SITE_CFG = {
    "name": "Zhejiang Province",
    "base_url": "https://www.zj.gov.cn",
    "admin_level": "provincial",  # central/provincial/municipal/district/department
}

# Define document sections/categories to crawl
SECTIONS = {
    "zcfg": "政策法规",   # Policies & Regulations
    "gfxwj": "规范性文件", # Normative Documents
    # ...
}
```

**Key functions to implement:**

```python
def _section_url(section: str, page: int) -> str:
    """Build listing page URL for a section + page number."""
    ...

def _get_total_pages(html: str) -> int:
    """Extract total page count from listing page HTML."""
    ...

def _parse_listing(html: str, base_url: str) -> list[dict]:
    """Parse listing HTML and return list of {url, title, date_str}."""
    ...

def _extract_body(html: str) -> str:
    """Extract plain text body from document detail page HTML."""
    # 1. Find the content container (div.article, div#zoom, etc.)
    # 2. Replace <br> with \n
    # 3. Strip all HTML tags
    # 4. Clean whitespace
    # 5. Unescape HTML entities
    ...

def _extract_meta(html: str) -> dict:
    """Extract metadata from detail page (doc_number, publisher, date, etc.)."""
    ...
```

**The main crawl loop:**

```python
def crawl_section(conn, section, section_name, fetch_bodies=True):
    log.info(f"--- Section: {section_name} ({section}) ---")

    html = fetch(_section_url(section, 0))
    total_pages = _get_total_pages(html)
    all_items = _parse_listing(html, _section_url(section, 0))

    for page in range(1, total_pages):
        page_html = fetch(_section_url(section, page))
        all_items.extend(_parse_listing(page_html, _section_url(section, page)))
        time.sleep(REQUEST_DELAY)

    log.info(f"  Found {len(all_items)} document links")

    stored = 0
    for item in all_items:
        # Skip if already have body text
        existing = conn.execute(
            "SELECT id, body_text_cn FROM documents WHERE url = ?", (item["url"],)
        ).fetchone()
        if existing and existing[1]:
            stored += 1
            continue

        doc_id = existing[0] if existing else next_id(conn)
        body_text = ""

        if fetch_bodies:
            try:
                doc_html = fetch(item["url"])
                body_text = _extract_body(doc_html)
                meta = _extract_meta(doc_html)
                save_raw_html(SITE_KEY, doc_id, doc_html)
            except Exception as e:
                log.warning(f"  Failed: {item['url']}: {e}")
            time.sleep(REQUEST_DELAY)

        store_document(conn, SITE_KEY, {
            "id": doc_id,
            "title": item["title"],
            "document_number": meta.get("document_number", ""),
            "publisher": meta.get("publisher", ""),
            "date_published": item["date_str"],
            "body_text_cn": body_text,
            "url": item["url"],
            "classify_main_name": section_name,
            "raw_html_path": ...,
        })
        stored += 1

        if stored % 20 == 0:
            conn.commit()
            log.info(f"  Progress: {stored}/{len(all_items)}")

    conn.commit()
    return stored
```

### Step 3: Handle `date_written` correctly (important!)

The `date_written` field must be a **Unix timestamp at midnight CST (UTC+8)**.
This is critical for the web app's date filtering to work.

```python
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))

def _parse_date(date_str: str) -> int:
    """Convert date string to Unix timestamp at midnight CST.

    Handle common formats: YYYY-MM-DD, YYYY/MM/DD, YYYY年MM月DD日
    """
    date_str = date_str.replace("/", "-").replace("年", "-").replace("月", "-").replace("日", "")
    try:
        dt = datetime.strptime(date_str.strip(), "%Y-%m-%d").replace(tzinfo=CST)
        return int(dt.timestamp())
    except ValueError:
        return 0
```

Always pass `"date_written": _parse_date(some_date_string)` to `store_document()`.

### Step 4: Test incrementally

```bash
# 1. Test listing parsing first (no body fetching)
python -m crawlers.your_site --list-only

# 2. Crawl one section with bodies
python -m crawlers.your_site --section zcfg

# 3. Check stats
python -m crawlers.your_site --stats

# 4. Spot-check a few documents in the web app
uvicorn web.app:app --port 8080
# Navigate to /browse?site=your_site_key
```

### Step 5: Wire up for production

1. The web app auto-discovers sites from the `sites` table — no changes needed
   to `web/` code. New sites appear in all dropdowns and filters automatically.

2. Add citation extraction by running the analyzer after crawling:
   ```bash
   python -m analysis.citations --site your_site_key
   ```

3. To add to the production Postgres DB, the crawler needs a Postgres mode or
   you can export from SQLite and import. Currently crawlers only write to
   SQLite (`documents.db`), and the web app reads from Postgres in production
   via `DATABASE_URL` env var.

## Common Patterns by Province

### JSON API Sites (easiest custom crawlers)
Some provinces serve document lists via JSON API even though the page renders
with JavaScript. Look for XHR requests in DevTools. Example:

```python
# If the site has a JSON listing API
data = fetch_json("https://www.example.gov.cn/api/docs?page=1&size=20")
for item in data["data"]["list"]:
    title = item["title"]
    url = item["url"]
    date = item["publishDate"]
```

### Static HTML Sites (like NDRC)
Pages are pre-rendered HTML. Parse with regex. This is the `crawlers/ndrc.py` pattern.
Look for `createPageHTML()` or similar JS pagination helpers.

### JavaScript-Rendered Sites (hardest)
If the Network tab shows the initial HTML is basically empty and content loads
via JS, you have two options:

1. **Find the underlying API** — almost always exists. Filter Network by XHR
   and look for the data source. This is the preferred approach.
2. **Use Playwright/Selenium** — last resort. Add `playwright` to deps and
   render pages headlessly. This is slow and fragile. Avoid if possible.

## Implemented Crawlers

| Crawler | Platform | Sites | Docs | Body % |
|---------|----------|-------|------|--------|
| `crawlers/gkmlpt.py` | Guangdong gkmlpt | 42 sites | ~96k | 91% |
| `crawlers/ndrc.py` | NDRC static HTML | 1 | 1,617 | 95% |
| `crawlers/gov.py` | State Council | 1 | 1,005 | 90% |
| `crawlers/mof.py` | Ministry of Finance | 1 | 919 | 93% |
| `crawlers/mee.py` | Ministry of Ecology & Environment | 1 | 563 | 88% |
| `crawlers/beijing.py` | Beijing custom CMS | 5 sections | 1,781 | 99% |
| `crawlers/shanghai.py` | Shanghai year-archives | 6 sections | 3,830 | 99% |
| `crawlers/jiangsu.py` | Jiangsu jpage API | 1 section | 1,041 | 0% (needs body fix) |

## Province Crawlers — Status

| Province | Crawler | Status | Docs | Notes |
|----------|---------|--------|------|-------|
| Beijing | `crawlers/beijing.py` | **Working** | 1,781 | 3 HTML template patterns, client-side pagination |
| Shanghai | `crawlers/shanghai.py` | **Working** | 3,830 | Year-based archives, jQuery pagination |
| Jiangsu | `crawlers/jiangsu.py` | **Partial** | 1,041 | jpage API works; body extraction needs debugging; 3/4 sections need template fix |
| Zhejiang | `crawlers/zhejiang.py` | **Blocked** | 0 | Unreachable from US |
| Sichuan | `crawlers/sichuan.py` | **Blocked** | 0 | Unreachable from US |
| Shandong | `crawlers/shandong.py` | **Blocked** | 0 | SSL handshake failure |

*Beijing + Shanghai docs are in `documents_new.db`. Merge into main DB with `python3 scripts/merge_db.py documents_new.db`.*

## Checklist

- [ ] Recon: found listing URL pattern and pagination mechanism
- [ ] Recon: found detail page body text container
- [ ] Recon: found metadata fields (doc number, publisher, date)
- [ ] Created `crawlers/your_site.py` with SITE_KEY and SITE_CFG
- [ ] Implemented `_parse_listing()` and verified with `--list-only`
- [ ] Implemented `_extract_body()` and `_extract_meta()`
- [ ] `date_written` uses Unix timestamp at midnight CST
- [ ] Tested with `--stats` — doc counts look reasonable
- [ ] Spot-checked documents in web app at `/browse?site=your_key`
- [ ] Committed and pushed
