# Ministry Crawler Expansion — March 13, 2026

## Context
Expanding crawler coverage to national ministries (Tier 3) beyond NDRC and State Council.

## gkmlpt Sync Status (running in background)
Started: 2026-03-13 ~14:30 UTC
Sites completed so far:
- sz, zjj, stic, fgw, hrss, mzj, sf, jtys, swj, zhongshan
- 11/25+ sites done
- Total docs: 70,119 (up from 69,651 pre-sync)
- Note: `zhongshan` appeared — Tier 1 expansion happening in parallel

## Ministry of Finance (MOF) — `crawlers/mof.py`

### Site Recon Findings
- **URL**: www.mof.gov.cn
- **Platform**: Static HTML with `createPageHTML()` pagination (same as NDRC)
- **Listing format**: `<li><a href="..." title='...'>Title</a><span>YYYY-MM-DD</span></li>`
  - Links use subdomains: `gss.mof.gov.cn`, `nys.mof.gov.cn`, `jrs.mof.gov.cn`, etc.
  - Each subdomain = a department within MOF
- **Body text container**: `div.my_conboxzw` with `.TRS_Editor` formatting
- **Metadata**: `<meta name="ArticleTitle/PubDate/ContentSource/Keywords">` tags
- **Doc numbers**: Sometimes in title parentheses, e.g. `(财税〔2026〕88号)`

### Sections Configured
| Key | Name | Type | Pages | Est. docs |
|-----|------|------|-------|-----------|
| zcfb | 政策发布 (Policy Releases) | HTML | 20 | ~500 |
| czxw | 财政新闻 (Finance News) | HTML | 20 | ~500 |
| czwg | 财政文告 (Finance Bulletins) | PDF | multi | ~300 PDFs (back to 2000) |

### Status
- [x] Crawler created: `crawlers/mof.py`
- [x] List-only test passed: 500 links found for zcfb section
- [x] PDF extraction: uses PyMuPDF (`fitz`) for text extraction
- [x] Added `--db` flag for separate DB crawling
- [x] Full crawl completed: 919 docs, 912 with body (99%)
- [x] Re-crawling into fresh documents_ministries.db (previous got corrupted)

### Crawl Results (first run)
- zcfb (政策发布): ~500 docs with body
- czxw (财政新闻): ~400 docs with body
- czwg (财政文告 PDF): PDFs extracted via PyMuPDF

### Key Implementation Details
- PDF bulletins (财政文告) are monthly compilations — each PDF contains multiple regulations
- PDFs stored as single documents (one per PDF file)
- Uses `next_id()` for doc IDs since MOF doesn't have numeric IDs in URLs
- Date parsing handles CST timezone (UTC+8) for `date_written`

## MIIT (Ministry of Industry & IT) — `crawlers/miit.py` (building)

### Site Recon Findings (from background probe)
- **URL**: www.miit.gov.cn
- **BEST TARGET**: Full JSON API with structured metadata!
- **API endpoint**: `GET https://www.miit.gov.cn/search-front-server/api/search/info`
  - `websiteid=110000000000000`, `category=51` (policy docs)
  - `pg=` (page size), `p=` (1-indexed page number), `q=` (search text)
  - `sortFields=[{"name":"deploytime","type":"desc"}]` (URL-encoded)
- **Response fields**: `title_text`, `url`, `cdate` (epoch ms), `filenumbername` (doc number!),
  `publishgroupname`, `typename`, `columnname`
- **Total**: ~272,000 results
- **Detail URL pattern**: `/zwgk/.../art/YYYY/art_UUID.html`
- No HTML parsing needed for listings — all metadata in JSON response

### Status
- [x] Crawler created: `crawlers/mee.py`
- [x] Added `--db` flag for separate DB crawling
- [x] Fixed body extraction bug (regex compilation error on Python 3.14)
- [x] Full crawl completed: 563 docs, 494 with body (88%)
- [x] Re-crawling into fresh documents_ministries.db

### Crawl Results (first run)
- gwywj (国务院有关文件): ~500 docs, 34 pages
- sthjbwj (生态环境部文件): docs crawled
- fl/xzfg/guizhang/bz: smaller regulatory sections

### Bug Fixed
Body extraction regex `r'(.*?)</div>\s*(?:<div\s+class="(?:con_|recommend|page)'`
failed to compile on Python 3.14 (stricter regex parser). Replaced with
`str.find()`-based boundary detection — simpler and faster.

## MEE (Ministry of Ecology & Environment) — Not yet built

### Site Recon Findings
- **URL**: www.mee.gov.cn
- **Listing**: `/xxgk2018/xxgk/xxgk03/index.shtml` (note `.shtml` extension!)
  - Format: `<li><span class="date">YYYY-MM-DD</span><a href="...">title</a></li>`
  - Path-based pagination: `index.shtml`, `index_1.shtml`, `index_2.shtml`
- **Detail pages**: Richest metadata of all 5 ministries — structured table with
  doc number (文号), index code (索引号), publisher (发布机关), category
  - Container: `div.content_top_box`
- **Status**: Static HTML, straightforward but needs category navigation

## MOHURD (Ministry of Housing) — Blocked

### Site Recon Findings
- **URL**: www.mohurd.gov.cn
- **DNS resolution failed** — likely geo-restricted to China-based networks
- **Status**: Needs in-country server access to probe

## MOFCOM (Ministry of Commerce) — Not yet built

### Site Recon Findings
- **URL**: www.mofcom.gov.cn (old /article/zwgk/ → 404, restructured to /zwgk/zcfb/)
- **API**: `GET /api-gateway/jpaas-publish-server/front/page/build/unit`
  - Params: `webId`, `pageId=fc8bdff48fa345a48b651c1285b70b8f`, `pageNo=N`, `rows=15`
  - Total: ~2,285 docs
  - Catch: returns pre-rendered HTML inside JSON (`data.html`), not structured data
  - Still need to parse `<ul class="txtList_01"><li>...</li></ul>` from response
- **Detail URL**: `/zwgk/zcfb/art/YYYY/art_UUID.html`
- **Doc numbers**: Embedded in title text, not separate field
- **Status**: API-based but HTML-in-JSON adds complexity

## Practical Build Order (by ease × value)
1. **MIIT** — real JSON API, ~272k docs, structured metadata ← building next
2. **MOFCOM** — API (HTML-in-JSON), ~2.3k docs
3. **MOF** — static HTML, ~1k+ docs ← currently crawling
4. **MEE** — static HTML, rich metadata, category hierarchy
5. **MOHURD** — blocked outside China

## Tier 4 Guide
Created `docs/implementation/new-province-crawler-guide.md` — step-by-step instructions
for building crawlers for non-gkmlpt provinces (Zhejiang, Shanghai, Beijing, etc.).
Includes: architecture overview, recon process, code template, date handling, testing checklist.

Note: The guide's target sites table was updated by another user/agent to mark
Zhejiang, Shanghai, and Beijing as implemented.

## MEE (Ministry of Ecology & Environment) — `crawlers/mee.py` (built)

### Site Recon Findings
- **URL**: www.mee.gov.cn
- **Platform**: Static HTML with `.shtml` extension
- **Listing format**: `<li><span class="date">YYYY-MM-DD</span><a href="...">Title</a></li>`
- **Pagination**: path-based `index_PAGEID_N.shtml` (page ID varies per section)
  - `countPage` var in JS gives total pages
- **Body text**: `div.content_body_box` (contains TRS_Editor markup)
- **Metadata**: Rich `<meta>` tags in `<head>`:
  - `ArticleTitle`, `PubDate`, `ContentSource`, `Keywords`, `ColumnName`, `contentid`
- **Doc numbers**: Embedded in body text (first few lines), NOT in separate field
  - Example: `国办发〔2026〕6号` found via regex on body head

### Sections Configured
| Key | Path | Name | Pages | Est. docs |
|-----|------|------|-------|-----------|
| gwywj | /zcwj/gwywj/ | 国务院有关文件 | 34 | ~500 |
| sthjbwj | /zcwj/sthjbwj/ | 生态环境部文件 | ? | ? |
| fl | /ywgz/fgbz/fl/ | 法律 | ? | ? |
| xzfg | /ywgz/fgbz/xzfg/ | 行政法规 | 3 | ~45 |
| guizhang | /ywgz/fgbz/guizhang/ | 规章 | ? | ? |
| bz | /ywgz/fgbz/bz/ | 标准 | ? | ? |

### Status
- [x] Crawler created: `crawlers/mee.py`
- [ ] List-only test (blocked by DB lock from Zhongshan crawl)
- [ ] Full crawl with body text

## MIIT Findings — Deprioritized

MIIT's API (`/search-front-server/api/search/info`) proved less useful than expected:
- Returns only 6 basic fields: `cdate`, `title_text`, `title`, `url`, `jsearch_url`, `jsearch_date`
- **No document numbers**, publisher, or category in API response
- `category=51` returns ALL site content (272k results), not just policy docs
- Connection is flaky (drops connections intermittently)
- Site is fully JS-rendered — no static HTML fallback
- **Decision**: Skip MIIT for now; would need in-browser automation or finding
  the correct API parameters to filter to policy documents only

## Merge Status (COMPLETE)
Merged `documents_ministries.db` → `documents.db` on 2026-03-14:
- 1 new site added (MEE)
- 1,040 new documents merged (442 duplicates skipped)
- MOF body text backfill completed: 436 docs updated (grabbed lock window during Shantou crawl)
- Main DB: **103,421 documents** across **38 sites**

### Final Coverage
| Site | Docs | With body | Coverage |
|------|------|-----------|----------|
| MOF  | 919  | 912       | 99%      |
| MEE  | 563  | 494       | 87%      |

### Post-merge TODO
- [ ] Run `python3 -m analysis.citations --site mof`
- [ ] Run `python3 -m analysis.citations --site mee`

## Crawl Concurrency Issue
SQLite allows only one writer at a time. Zhongshan (Tier 1) crawl is holding
the DB lock, preventing MOF and MEE crawlers from running. Solutions:
1. Queue crawlers sequentially (current approach)
2. Migrate to local Postgres (handles concurrent writes natively)

## Next Steps
1. Wait for Zhongshan crawl to finish (DB lock release)
2. Run MOF full crawl with body text (`python -m crawlers.mof`)
3. Run MEE crawl (`python -m crawlers.mee`)
4. Resume gkmlpt sync for remaining 14 sites
5. Run NDRC and gov sync
6. Investigate MOFCOM crawler (has API but returns HTML-in-JSON)
7. Revisit MIIT if a proper API filter is found
