# Scratchpad & Log

Working log of everything attempted, results, and decisions made.

---

## Session Log

### 2026-02-14 — Project Setup

- Initialized git repo, pushed to `https://github.com/hulelan/china-governance.git`
- Read `conversation.md` and `spec.md` — prior research from an earlier session
- Synthesized execution plan into `plan.md`

### 2026-02-15 — Goal 1 Reconnaissance (API Discovery)

Major session. Resolved the single biggest unknown: the gkmlpt API.

### 2026-02-15 — Goals 2-4: Crawler Built & Running

- Built `crawler.py` — full pipeline: discover → list → extract → store
- First metadata crawl: Pingshan 1,636 docs in ~2 minutes
- Main portal full crawl: 844 docs, 635 with body text
- DNS resolution failures during crawl (temporary) — added retry logic
- Analysis: 49% of docs contain cross-references, 1,028 total refs found
- Top cited: State Council 国发〔2012〕52号 (28 citations) — administrative reform

### 2026-02-15 (Session 2) — Scaling to 6 Sites

- Resumed. Fixed: unicode_escape deprecation, 404 retry logic, backfill mode
- Crawled metadata for all 6 configured sites:
  - Shenzhen Main Portal: 844 docs
  - Pingshan District: 1,636 docs
  - S&T Innovation Bureau: 2,710 docs
  - Development & Reform Commission: 2,552 docs
  - Housing & Construction Bureau: 2,353 docs
  - Guangming District: 905 docs
  - **Total: 11,000 documents**
- Backfill of body text running (10,315 docs remaining, ~1.4 hrs estimated)
- Expanded issuer classification: unknown rate dropped from 25% to 9%
- Added citation network analysis to analyze.py

---

## Experiments & Results

#### 2026-02-15 — HTTP Access Test
**What:** Tested curl access to Shenzhen gov sites over HTTP
**Why:** Confirm HTTP works from this machine (prior session tested from a different env)
**How:** `curl -s -o /dev/null -w "%{http_code}" "http://www.szpsq.gov.cn/gkmlpt/content/9/9103/post_9103540.html"`
**Result:** HTTP 200. Full HTML returned.
**Conclusion:** HTTP access works from this machine. No VPN/VPS needed for MVP.

#### 2026-02-15 — Main Portal mpost_ Page Structure
**What:** Fetched the example mpost_ page from sz.gov.cn main portal
**Why:** Determine if main portal uses gkmlpt or a different CMS
**How:** `curl http://www.sz.gov.cn/cn/xxgk/.../mpost_12193340.html`
**Result:** Uses NFCMS CMS (not gkmlpt). Metadata in `<meta>` tags: ArticleTitle, PubDate, ContentSource, ArticleId. Content in div.news_cont_d_wrap. Script sets `NFCMS_SITE_ID=755001, NFCMS_POST_ID=12193340`.
**Conclusion:** Main portal content pages use a DIFFERENT CMS from gkmlpt. BUT the main portal ALSO has a `/gkmlpt/index` endpoint (see below).

#### 2026-02-15 — gkmlpt Content Page _CONFIG Object
**What:** Extracted `window._CONFIG` from gkmlpt content page
**Why:** Check if document data is in JS config (alternative to HTML parsing)
**How:** Regex extraction of _CONFIG from fetched HTML
**Result:** Found `DETAIL` object containing full document metadata (id, title, abstract, content HTML). JSON parse fails at char 19660 due to escaped chars in content field, but structure is confirmed.
**Conclusion:** Two extraction paths available: HTML table parsing OR _CONFIG.DETAIL JSON extraction. HTML table is more reliable; _CONFIG is a bonus.

#### 2026-02-15 — gkmlpt HTML Metadata Table
**What:** Extracted metadata fields from gkmlpt content page HTML
**Why:** Verify all 8 metadata fields are reliably extractable
**How:** String search for Chinese field labels in HTML
**Result:** All 8 fields found: 索引号 (114403006955506492/2021-00426), 分类, 发布机构 (深圳市坪山区人民政府), 成文日期 (2021-09-02), 名称, 文号 (empty), 发布日期 (2021-09-03), 主题词 (工作总结). Zero attachments on this page.
**Conclusion:** Metadata table parsing is straightforward. Fields have consistent labels.

#### 2026-02-15 — Playwright API Discovery (FAILED)
**What:** Tried to use Playwright to navigate gkmlpt index page and intercept XHR traffic
**Why:** Discover the API endpoints the Vue.js SPA calls
**How:** Playwright script with `page.on('request')` / `page.on('response')`, tried both `networkidle` and `domcontentloaded` wait strategies
**Result:** All page navigations timed out (20-30s timeout). Pages are too slow to fully load from outside China in a headless browser.
**Conclusion:** Playwright-based API discovery doesn't work from outside China. Need alternative approach.

#### 2026-02-15 — JavaScript Source Code Analysis (BREAKTHROUGH)
**What:** Instead of intercepting live traffic, fetched the Vue.js bundle files directly and searched for API patterns
**Why:** The API endpoints must be hardcoded in the JS source
**How:** Fetched `/gkmlpt/gkml/pc/js/chunk-common.c1553651.js` via curl, searched with regex for URL patterns
**Result:** FOUND THE API. The `fetchPostList` function constructs:
```
/gkmlpt/api/all/{category_id}?page={page_num}&sid={site_id}
```
Other endpoints found: `/frontuc/page/fav`, `/frontuc/page/isfav`, `/jsonp/post/sum`
**Conclusion:** No Playwright needed. The API is a simple GET endpoint with category ID, page number, and site ID.

#### 2026-02-15 — gkmlpt API Testing (MAJOR SUCCESS)
**What:** Tested the discovered API endpoint directly
**Why:** Validate it works and understand the response format
**How:** `curl http://www.szpsq.gov.cn/gkmlpt/api/all/20765?page=0&sid=755041`
**Result:** Returns rich JSON with:
- `classify`: category metadata including `post_count`
- `articles`: array of document objects with 30+ fields each including:
  - `id`, `title`, `document_number` (文号), `publisher`, `keywords`
  - `date`, `created_at`, `display_publish_time`
  - `identifier` (索引号), `classify_main_name`, `classify_genre_name`, `classify_theme_name`
  - `url` (gkmlpt content URL), `post_url` (alternative URL)
  - `attachment` (array of {id, name, type, mime, size, url})
  - `abstract`, `relation` (cross-references, currently "[]")
  - `is_expired`, `is_abolished` (document status)
- Pagination: 100 items per page (pages 0 and 1 return same data; page 2 is next batch)
**Conclusion:** The API returns MORE metadata than what's in the HTML page. This is the primary data source. We only need HTML pages for the full body text.

#### 2026-02-15 — Cross-Site API Validation
**What:** Tested API on main portal and Housing department
**Why:** Confirm the API is universal across gkmlpt sites
**How:** Fetched /gkmlpt/index from sz.gov.cn and zjj.sz.gov.cn, extracted SID and TREE
**Result:**
- Main portal: SID=755001, 12 top-level categories, API works ✅
- Housing (zjj.sz.gov.cn): SID=755029, 10 top-level categories, API works ✅
- Pingshan: SID=755041, 6 top-level categories, API works ✅
**Conclusion:** Same API across all gkmlpt sites. Only SID differs.

#### 2026-02-15 — Navigation Tree (_CONFIG.TREE)
**What:** Extracted full navigation tree from gkmlpt index pages
**Why:** Need category IDs to query the API
**How:** Parse _CONFIG.TREE JSON from /gkmlpt/index HTML
**Result:** Rich hierarchical tree with category IDs, names, parent relationships, and jump_urls to external pages. Pingshan has 6 top-level / 21 leaf categories. Main portal has 12 top-level / 18 leaf categories with content.
**Conclusion:** TREE provides the complete category enumeration needed for listing discovery.

#### 2026-02-15 — Document Counts
**What:** Queried API for every leaf category to get post_count
**Result:**
- Main portal (sz.gov.cn): **4,176 documents** across 18 categories
  - Largest: 政务动态 (2,853), 规范性文件 (422), 市政府文件 (395), 规章 (270)
- Pingshan (szpsq.gov.cn): **~3,400 documents** across 21 categories
  - Largest: 通告、公告 (429), 其他文件 (379), 人大建议 (341), 函 (271)
**Conclusion:** Very manageable scale. A single site has 3-4K documents. Full Shenzhen constellation might be 50-100K.

#### 2026-02-15 — Attachment Prevalence
**What:** Checked attachment data in API responses
**Result:** ~10% of municipal documents have attachments. Attachment format:
```json
{"id": 1658591, "name": "filename.docx", "type": "doc", "mime": "application/msword", "size": "26624", "url": "https://www.sz.gov.cn/attachment/1/1658/1658591/12541123.docx"}
```
Types observed: PDF, DOCX
**Conclusion:** Attachment URLs are in the API response — no need to parse HTML for them. 10% rate means PDF extraction is nice-to-have, not blocking.

#### 2026-02-15 — 文号 Format Patterns
**What:** Observed document number formats in API responses
**Result:** Examples: "深府规〔2026〕1号", "深府规〔2025〕10号", "深坪发改规〔2026〕2号"
Pattern: `{issuing_body_abbreviation}〔{year}〕{number}号`
**Conclusion:** Consistent format. Regex extractable for cross-referencing.

---

## Open Questions

1. ~~What is the gkmlpt JSON API endpoint structure?~~ **RESOLVED** ✅
2. Full verified subdomain list? (Goal 1, Task 2) — NOT YET DONE
3. ~~Does main portal metadata match gkmlpt format?~~ **RESOLVED** — Main portal ALSO has gkmlpt ✅
4. ~~What % of documents are PDF/DOC attachments?~~ **RESOLVED** — ~10%, URLs in API ✅
5. Rate limiting behavior? (empirical — test during Goal 2)
6. ~~文号 format patterns for cross-referencing?~~ **RESOLVED** ✅
7. LLM cost estimate at MVP scale? (test during Goal 5)

---

## Resolved Questions

- **SSL access:** HTTP works, HTTPS fails. Use HTTP. (from prior session)
- **JS rendering for content pages:** Not needed — server-rendered HTML. (from prior session)
- **Legal risk:** Minimal — public disclosure mandate, polite crawling. (from prior session)
- **gkmlpt scope:** Province-wide Guangdong standard, not Shenzhen-specific. (from prior session)
- **gkmlpt API:** `/gkmlpt/api/all/{category_id}?page={page_num}&sid={site_id}` — returns rich JSON ✅
- **Main portal CMS:** Uses NFCMS for content pages BUT also has /gkmlpt/index with working API ✅
- **Attachment prevalence:** ~10%, attachment URLs included in API response ✅
- **Playwright necessity:** NOT NEEDED. Pure HTTP API discovered via JS source analysis ✅
- **文号 format:** `{body}〔{year}〕{number}号` — regex extractable ✅
- **Document scale:** Main portal ~4K docs, Pingshan ~3.4K docs. Full constellation est. 50-100K ✅

---

## Architecture Decisions (Updated Based on Findings)

### Crawler Architecture (Revised)

The API discovery eliminates the need for Playwright entirely. The crawler is now:

```
For each target site:
  1. HTTP GET /gkmlpt/index → extract SID and TREE from _CONFIG
  2. For each leaf category in TREE:
     a. HTTP GET /gkmlpt/api/all/{cat_id}?page=1&sid={SID}
     b. Read post_count from response
     c. Paginate: pages 1 through ceil(post_count/100)
     d. Collect all article metadata from API responses
  3. For each article:
     a. HTTP GET the content URL → extract full body text
     b. (Optional) Download attachments
  4. Store: metadata + body text + raw HTML in SQLite
```

### What We Don't Need

- ❌ Playwright / headless browser
- ❌ Scrapy (simple requests + json is sufficient)
- ❌ HTML metadata parsing for listing (API provides richer data)
- ❌ Separate parser for different departments (same API everywhere)

### What We DO Need

- ✅ Simple HTTP client (requests or urllib)
- ✅ JSON parser (built-in)
- ✅ HTML parser for body text extraction only (BeautifulSoup)
- ✅ SQLite for structured storage
- ✅ Rate limiting / polite delays

---

## Useful References

- **API endpoint:** `/gkmlpt/api/all/{category_id}?page={page_num}&sid={site_id}`
- **Example API call:** `http://www.szpsq.gov.cn/gkmlpt/api/all/20765?page=1&sid=755041`
- **gkmlpt index page:** `http://www.szpsq.gov.cn/gkmlpt/index` (contains _CONFIG with SID + TREE)
- **Main portal SID:** 755001
- **Pingshan SID:** 755041
- **Housing & Construction SID:** 755029
- **S&T Innovation SID:** 755018
- **Development & Reform SID:** 755529
- **Guangming District SID:** 755046
- **JS bundle with API code:** `/gkmlpt/gkml/pc/js/chunk-common.c1553651.js`
- Example gkmlpt content page: `http://www.szpsq.gov.cn/gkmlpt/content/9/9103/post_9103540.html`
- Example main portal content: `http://www.sz.gov.cn/cn/xxgk/zfxxgj/sldzc/szfld/lwp/jqhd/content/mpost_12193340.html`
