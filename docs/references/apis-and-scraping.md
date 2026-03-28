# APIs and Web Scraping

Reference notes on how websites serve data and how our crawlers interact with them.

## What is an API?

An **API** (Application Programming Interface) is a structured way for programs to talk to each other. A **web API** is a URL endpoint that returns raw data (usually JSON) instead of an HTML page meant for human eyes.

```
Browser visits:  https://www.163.com/dy/article/KOASJO7O0531M1CO.html
                 -> returns HTML with headers, ads, CSS, JavaScript, article text mixed together

API call:        https://dy.163.com/v2/article/list.do?wemediaId=...&pageNo=1
                 -> returns clean JSON: {"code": 1, "data": {"list": [...]}}
```

## Do all websites have APIs?

**No.** There's a spectrum:

| Type | Description | Example |
|------|-------------|---------|
| **Public API** | Documented, intended for external use | GitHub API, Twitter/X API |
| **Internal API** | Powers the site's own frontend, undocumented | 163.com's `dy.163.com/v2/article/list.do` — exists but returns empty without proper session cookies |
| **Server-rendered HTML** | No API at all, content is in the HTML | Government sites (gkmlpt), LatePost's channel page on 163.com |
| **Client-rendered / JS-heavy** | API exists but only works within the browser context | Many modern SPAs, "load more" buttons |

## Our crawlers and the spectrum

### Government sites (easy to crawl)

- Server-rendered HTML with stable URL patterns
- Minimal anti-bot measures (public access is the point)
- Often have sitemaps or predictable pagination
- gkmlpt sites expose a JSON API (`/inteligent/...`) — a true public API

### News sites like 163.com (medium difficulty)

- **Article pages** are server-rendered with structured metadata:
  - `<meta property="og:title">` for title
  - `<meta property="article:published_time">` for date
  - `<div class="post_body">` for body text
  - These exist because the site *wants* search engines to index the content
- **Listing pages** are partially JS-rendered:
  - The channel page serves ~85 articles in HTML
  - Deeper pagination requires JavaScript execution
- **Internal APIs** exist but require session cookies or referrer headers that browsers set automatically

### WeChat / App-only content (hard to crawl)

- Everything loaded via JavaScript with authentication
- No stable public URLs
- Anti-bot measures are aggressive

## Key concepts

- **Scraping** = parsing HTML meant for browsers. This is what most of our crawlers do.
- **API consumption** = calling structured endpoints meant for programs. The gkmlpt crawler does this.
- **Both** produce the same result: structured data in `documents.db`.

## How 163.com article scraping works

The LatePost crawler (`crawlers/latepost.py`) uses this approach:

1. **Discovery**: Fetch `163.com/dy/media/T1596162548889.html` (LatePost's channel page). All article URLs are embedded in the HTML and share the publisher segment `0531M1CO`.

2. **Extraction**: For each article URL, extract:
   - Title from `<meta property="og:title">`
   - Date from `<meta property="article:published_time">`
   - Body text from `<div class="post_body">`, stripped of HTML tags
   - Keywords from `<meta name="keywords">`

3. **Limitation**: Only ~85 recent articles are available on the channel page (no pagination API). The crawler runs incrementally — new articles appear at the top, already-crawled ones are skipped.



# Original Text
  What is an API?

  An API (Application Programming Interface) is a structured way for programs to talk to each other. A web
   API is a URL endpoint that returns raw data (usually JSON) instead of an HTML page meant for human
  eyes.

  For example:
  Browser visits:  https://www.163.com/dy/article/KOT4Q4Q90531M1CO.html
                   → returns HTML with headers, ads, CSS, JavaScript, article text all mixed together

  API call:        https://dy.163.com/v2/article/list.do?wemediaId=...&pageNo=1
                   → returns clean JSON: {"code": 1, "data": {"list": [...]}}

  Do all websites have APIs?

  No. There's a spectrum:

  ┌───────────────────────────────┬────────────────────────────────────┬──────────────────────────────┐
  │             Type              │              Example               │         What we saw          │
  ├───────────────────────────────┼────────────────────────────────────┼──────────────────────────────┤
  │ Public API (documented,       │ Twitter/X API, GitHub API          │ None from 163.com for        │
  │ intended for external use)    │                                    │ LatePost                     │
  ├───────────────────────────────┼────────────────────────────────────┼──────────────────────────────┤
  │ Internal API (powers the      │                                    │ It exists but returned empty │
  │ site's own frontend,          │ The dy.163.com/v2/article/list.do  │  — likely requires cookies   │
  │ undocumented)                 │ endpoint we found                  │ or auth tokens from their    │
  │                               │                                    │ frontend                     │
  ├───────────────────────────────┼────────────────────────────────────┼──────────────────────────────┤
  │ Server-rendered HTML (no API  │ The LatePost channel page we       │ The HTML contains the        │
  │ at all)                       │ successfully scraped               │ article list directly — no   │
  │                               │                                    │ API needed                   │
  ├───────────────────────────────┼────────────────────────────────────┼──────────────────────────────┤
  │ Client-rendered / JS-heavy    │                                    │ The "load more" on 163.com   │
  │ (API exists but only works    │ Many modern SPAs                   │ likely works this way        │
  │ within the browser)           │                                    │                              │
  └───────────────────────────────┴────────────────────────────────────┴──────────────────────────────┘

  What happened with our 163.com exploration

  We tried three approaches — this illustrates the spectrum well:

  1. Internal API (dy.163.com/v2/article/list.do) — We found it, it responded with {"code": 1} (success),
  but the list was always empty. This likely means it requires session cookies or a referrer header that
  the browser sets automatically. This is common — companies expose APIs for their own frontend but don't
  want outsiders using them.
  2. Server-rendered HTML (the channel page) — This worked. The server sends complete HTML with 85 article
   links embedded. No JavaScript needed. This is the "old school" web and it's the easiest to crawl.
  3. Article pages (individual articles) — Also server-rendered. We could extract the title from <meta
  property="og:title">, the date from <meta property="article:published_time">, and body text from <div
  class="post_body">. These meta tags exist because 163.com wants search engines (Google, Baidu) to index
  their content.

  Why some sites are easy to crawl and others aren't

  Easy to crawl                              Hard to crawl
  ─────────────────────────────────────────────────────────
  Government sites          News sites          SPAs / Apps
  (your current corpus)     (163.com)           (WeChat articles)

  - Server-rendered HTML    - Mix of HTML +     - Everything loaded
  - Stable URL patterns       internal APIs       via JavaScript
  - No anti-bot measures    - Some anti-bot     - Auth required
  - Often have sitemaps     - Rate limiting     - No stable URLs

  Your government crawlers work so well because government sites are designed for public access and almost
   always server-render their HTML. 163.com sits in the middle — the article pages are scrapable, but the
  listing/discovery layer partially relies on JavaScript.

  The key concepts for your project

  - Scraping (what your crawlers do) = parsing HTML meant for browsers
  - API consumption = calling structured endpoints meant for programs
  - Both can fill your database — the storage format in documents.db is the same either way

  For LatePost on 163.com, scraping the server-rendered HTML is the right approach. 