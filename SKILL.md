# Skill: Writing a Chinese Government Site Crawler

## When to Use

When the user wants to crawl a new Chinese government website that is NOT on the gkmlpt platform.

## Before You Start

1. **Check if it's gkmlpt first.** Fetch `https://{domain}/gkmlpt/index`. If it returns a gkmlpt page, just add the site to `SITES` dict in `crawlers/gkmlpt.py` — no new crawler needed.
2. **Check if it's already crawled.** Run: `sqlite3 documents.db "SELECT site_key, COUNT(*) FROM documents WHERE url LIKE '%{domain}%' GROUP BY site_key;"`

## Step 1: Probe the listing page (5 min)

Use `curl -sk` (not Python requests — many .gov.cn sites have TLS issues that crash Python's SSL):

```bash
curl -sk "https://{domain}/{section_path}/" -o /tmp/probe.html
```

Extract three things:
1. **Article link pattern**: `grep -o 'content/post_[0-9]*' /tmp/probe.html | head -5`
2. **Pagination**: Look for `createPageHTML(N,` or `index_N.html` links
3. **List item structure**: Find the HTML wrapping each article link

### Common patterns we've seen:

| Site type | List structure |
|-----------|---------------|
| sz.gov.cn main | `<li><span class="number">N</span><span class="tit"><a href="URL" title="TITLE">...</a></span><span>DATE</span></li>` |
| fgw.sz.gov.cn | `<a href="URL" title="TITLE"><span class="zyzp-text">TEXT</span><span class="zyzp-time">DATE</span></a>` |
| lg.gov.cn | `<li><a href="URL" title="TITLE">TEXT</a><span>DATE</span></li>` |
| NDRC | `<li><a href="URL" title="TITLE">TEXT</a>...<span>YYYY/MM/DD</span></li>` |

## Step 2: Probe the article page (5 min)

Fetch one article and find the body container:

```bash
curl -sk "https://{domain}/{path}/content/post_XXXXX.html" -o /tmp/article.html
```

Search for body selectors in order of likelihood:
- `news_cont_d_wrap` (sz.gov.cn main portal)
- `articleBox` (fgw.sz.gov.cn)
- `content_article` (lg.gov.cn / district sites)
- `article_con` (NDRC)
- `TRS_Editor` (older CMS)
- `Custom_UnionStyle` (some provincial sites)

Also check for metadata: `来源：` (publisher), `<meta name="PubDate">` (date).

## Step 3: Write the crawler (20 min)

Use `crawlers/ndrc.py` as the template. Copy and modify:

1. **SITE_KEY, SITE_CFG** — new site_key, name, base_url, admin_level
2. **SECTIONS dict** — paths and Chinese names for each section
3. **`_section_url()`** — build listing URLs (usually `{base}{path}index.html` / `index_{N}.html`)
4. **`_parse_listing()`** — regex for the list item pattern you found in Step 1
5. **`_extract_body()`** — regex for the body selector you found in Step 2
6. **`_fetch()`** — if the site has TLS issues (BAD_ECPOINT error), use `subprocess.run(["curl", "-sk", ...])` instead of urllib/requests

### Key rules:
- Always use `store_document()` from `crawlers.base` — don't write raw SQL
- Always check existing before inserting: `SELECT id, body_text_cn FROM documents WHERE url = ?`
- Commit every 20 docs and log progress
- Sleep `REQUEST_DELAY` between requests
- Use `save_raw_html()` to archive the original HTML

## Step 4: Test (5 min)

```bash
# List-only first (no body fetch, fast)
python3 -m crawlers.{name} --list-only

# Then full crawl
python3 -m crawlers.{name}
```

Verify: `sqlite3 documents.db "SELECT COUNT(*), SUM(CASE WHEN body_text_cn <> '' THEN 1 ELSE 0 END) FROM documents WHERE site_key = '{key}';"`

## Common Gotchas

1. **TLS/SSL errors with .gov.cn**: Python 3.14's SSL rejects older TLS configs (BAD_ECPOINT). Use curl subprocess.
2. **createPageHTML vs actual pages**: The JS function takes total_pages but pagination is 0-indexed. Page 0 = `index.html`, page 1 = `index_1.html`.
3. **Date formats vary**: sz.gov.cn uses `YYYY-MM-DD`, NDRC uses `YYYY/MM/DD`. Normalize to `YYYY-MM-DD`.
4. **Some sections look empty but use JS rendering**: If curl returns HTML with 0 article links but the browser shows articles, the site uses AJAX/JS pagination — need a different approach (check for API endpoints in the page source).
5. **Don't duplicate gkmlpt docs**: If the domain also has gkmlpt, use a different site_key (e.g., `sz_invest` not `sz`) to avoid overlap.
6. **SQLite lock contention**: Never run two crawlers writing to `documents.db` simultaneously. Use `--db documents_new.db` and merge later if needed.

## File Locations

- **Template crawler**: `crawlers/ndrc.py` (cleanest example)
- **Base utilities**: `crawlers/base.py` (fetch, store_document, init_db, etc.)
- **Database**: `documents.db` (SQLite, WAL mode)
- **Guide**: `docs/implementation/new-province-crawler-guide.md`
