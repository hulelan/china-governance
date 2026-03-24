# Shenzhen News / Investment Portal — Investigation Report

*2026-03-24. Investigation of the Shenzhen investment news pages described in `investment-data-plan.md`.*

## Summary

The four target sections on `sz.gov.cn` use the **NFCMS CMS** (not gkmlpt). They cannot be crawled via the existing gkmlpt API — a new HTML scraping crawler is needed, following the `crawlers/mof.py` pattern.

Network access to `sz.gov.cn` is currently **blocked from the cloud environment** ("Host not allowed" — sandbox restriction). All probing must be done locally or from a machine with access to Chinese government sites.

## Target URLs

| Section | URL | Content Type |
|---------|-----|-------------|
| 投资动态 (Investment News) | `http://www.sz.gov.cn/cn/zjsz/fwts_1_3/tzdt_1/` | FDI news, project signings |
| 统计数据 (Statistics) | `http://www.sz.gov.cn/cn/zjsz/fwts_1_3/tjsj/` | Economic data releases |
| 投资指南 (Investment Guide) | `http://www.sz.gov.cn/cn/zjsz/fwts_1_3/tzzn/` | Sector guides, incentives |
| 营商环境 (Business Env) | `http://www.sz.gov.cn/cn/zjsz/yshj/` | Regulatory reform updates |

## Key Findings

### 1. CMS is NFCMS, NOT gkmlpt

The crawler scratchpad (2026-02-15) documents this clearly:

> Main portal content pages use a DIFFERENT CMS from gkmlpt. [...] Uses NFCMS CMS (not gkmlpt). Metadata in `<meta>` tags: ArticleTitle, PubDate, ContentSource, ArticleId. Content in `div.news_cont_d_wrap`.

The existing gkmlpt API (`/gkmlpt/api/all/{cat_id}?page={page}&sid={sid}`) only covers the 政府信息公开 (government information disclosure) section. The investment/news portal is a completely separate CMS.

### 2. Known NFCMS page structure (from scratchpad)

Individual article pages (`mpost_*.html`) have been probed previously:
- **Meta tags**: `ArticleTitle`, `PubDate`, `ContentSource`, `ArticleId`
- **Body text**: `div.news_cont_d_wrap`
- **CMS identifiers**: `NFCMS_SITE_ID=755001`, `NFCMS_POST_ID={id}`
- The existing gkmlpt body extractor already handles this as a fallback (line 398 in `gkmlpt.py`)

### 3. Network access blocked from this environment

All attempts to fetch `sz.gov.cn` (HTTP and HTTPS) returned:
- **HTTPS**: 403 Forbidden
- **HTTP**: 403 with body "Host not allowed" — sandbox network restriction
- **WebFetch tool**: 403

This is NOT the site blocking us — it's the cloud sandbox. The crawlers work fine when run locally (confirmed by the existing 45K+ Shenzhen documents in the corpus).

### 4. HTTP required (not HTTPS)

From the scratchpad: "HTTP works, HTTPS fails." All existing `SITES` entries in `gkmlpt.py` use `http://` base URLs. The new crawler should also use HTTP.

## What Needs to Be Done Locally

Since the pages can't be probed from this environment, the following must be done **locally** (from a machine that can reach Chinese gov sites):

### Step 1: Probe listing pages
```bash
# Fetch and save each listing page
curl -s -o /tmp/tzdt.html "http://www.sz.gov.cn/cn/zjsz/fwts_1_3/tzdt_1/"
curl -s -o /tmp/tjsj.html "http://www.sz.gov.cn/cn/zjsz/fwts_1_3/tjsj/"
curl -s -o /tmp/tzzn.html "http://www.sz.gov.cn/cn/zjsz/fwts_1_3/tzzn/"
curl -s -o /tmp/yshj.html "http://www.sz.gov.cn/cn/zjsz/yshj/"
```

For each page, determine:
1. **List structure**: `<ul><li>` vs `<div>` vs `<table>`? Look for repeating article items.
2. **Link pattern**: `<a href="...">` — are they relative (`content/mpost_12345.html`) or absolute?
3. **Pagination**: Look for `createPageHTML()` (like NDRC/MOF) or `?page=N` params or `index_N.htm` pattern.
4. **Total count**: Is total page count in HTML or JS variable?

### Step 2: Probe article pages
```bash
# Pick an article link from step 1 and fetch it
curl -s -o /tmp/article.html "http://www.sz.gov.cn/cn/zjsz/fwts_1_3/tzdt_1/content/mpost_XXXXXX.html"
```

Verify:
- `<meta name="ArticleTitle">` present
- `<meta name="PubDate">` present
- `div.news_cont_d_wrap` contains body text
- Any additional metadata (author, source, keywords)

### Step 3: Check for JSON/API endpoints
```bash
# Check if there's a JSON feed (like State Council has)
curl -s "http://www.sz.gov.cn/cn/zjsz/fwts_1_3/tzdt_1/index.json"
# Check for XHR-style API
curl -s "http://www.sz.gov.cn/cn/zjsz/fwts_1_3/tzdt_1/list.json"
```

## Recommended Crawler Architecture

Based on existing patterns (MOF/MEE template):

```python
# crawlers/sz_invest.py — follows crawlers/mof.py pattern

SITE_CFG = {
    "name": "Shenzhen Investment Portal",
    "base_url": "http://www.sz.gov.cn",
    "admin_level": "municipal",
}

SECTIONS = {
    "tzdt": {"path": "/cn/zjsz/fwts_1_3/tzdt_1/", "name": "投资动态"},
    "tjsj": {"path": "/cn/zjsz/fwts_1_3/tjsj/",   "name": "统计数据"},
    "tzzn": {"path": "/cn/zjsz/fwts_1_3/tzzn/",    "name": "投资指南"},
    "yshj": {"path": "/cn/zjsz/yshj/",              "name": "营商环境"},
}

# Pagination: likely index.htm / index_{N}.htm (same as MOF/NDRC)
# Listing parse: regex for <li><a href>...<span>date</span></li>
# Body extract: div.news_cont_d_wrap (already handled in gkmlpt.py:398)
# Meta extract: <meta> tags (ArticleTitle, PubDate, ContentSource)
# site_key: "sz_invest"
```

Key implementation notes:
- Reuse `base.py` utilities (`fetch`, `store_document`, `init_db`, etc.)
- The body extractor in `gkmlpt.py:398` already handles `div.news_cont_d_wrap` — extract this into a shared utility or duplicate in the new crawler
- Use `next_id(conn)` since these pages won't have gkmlpt numeric IDs
- Browser UA may be needed (add to `SITES_NEEDING_BROWSER_UA` equivalent)

## Open Questions (to resolve during local probing)

1. **Pagination style**: Does it use `createPageHTML()` like MOF/NDRC, or something else?
2. **Listing HTML format**: What's the exact `<li>` / `<div>` structure for article lists?
3. **Content volume**: How many articles are in each section? (affects crawl time estimate)
4. **Date range**: How far back do articles go?
5. **Attachments**: Do investment news articles include PDF/DOC attachments?
6. **Same table or separate?**: Investment content is more news/editorial — should it go in the main `documents` table with a distinct `site_key`, or warrant a separate table?
