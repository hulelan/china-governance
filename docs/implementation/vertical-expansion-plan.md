# Vertical Expansion: Multi-Platform Crawler for Central-to-Local AI Policy

## Goal

Trace AI policy from State Council down to Shenzhen districts by crawling every layer of government. Requires new crawlers for central government sites plus expanding gkmlpt coverage to provincial level.

## Architecture

```
crawlers/
├── __init__.py
├── base.py          # Shared: init_db, fetch, store_document, save_raw_html
├── gkmlpt.py        # Guangdong gkmlpt platform (existing crawler.py logic)
├── ndrc.py          # NDRC static HTML crawler
└── gov.py           # State Council TRS CMS crawler
```

All crawlers write to the same `documents.db`. The `site_key` and `admin_level` fields distinguish sources. Web app works unchanged.

## Steps

1. Extract `crawlers/base.py` from `crawler.py` (shared utilities)
2. Move gkmlpt logic to `crawlers/gkmlpt.py`, keep `crawler.py` as thin wrapper
3. Add Guangdong Province (SID: 2) + Guangzhou (SID: 200001) + other confirmed gkmlpt cities to SITES
4. Build `crawlers/ndrc.py` — static HTML, predictable `createPageHTML()` pagination
5. Build `crawlers/gov.py` — TRS CMS, `/zhengce/` policy listings

## Session Log

### 2026-02-22

**Step 1: Extract `crawlers/base.py`** — Done. Shared utilities: `init_db()`, `fetch()`, `fetch_json()`, `store_site()`, `store_document()`, `save_raw_html()`, `show_stats()`, `next_id()`. Enhanced `store_document()` to accept a dict (flexible for different CMS schemas). Added `next_id()` for sites without their own numeric IDs.

**Step 2: Create `crawlers/gkmlpt.py`** — Done. Moved all gkmlpt-specific logic from `crawler.py`. `crawler.py` is now a 4-line wrapper. Verified: `python crawler.py --stats` still shows 45,130 Shenzhen docs.

**Step 3: Expand gkmlpt SITES** — Done. Added Guangdong Province (`gd`), Guangzhou (`gz`), Zhuhai, Huizhou, Jiangmen to SITES dict. Not yet crawled (requires network access to Chinese government sites).

**Step 4: Build `crawlers/ndrc.py`** — Done. Probed NDRC site structure:
- 5 sections under `/xxgk/zcfb/`: fzggwl (9 pages), ghxwj (8), ghwb (9), gg (20), tz (20)
- Listing pages use `createPageHTML(totalPages, idx, "index", "html")` pagination
- Document pages have rich `<meta>` tags: `ArticleTitle`, `PubDate`, `ContentSource`, `ColumnName`
- Body text in `div.article_con`
- Smoke test: 500 docs indexed from 通知 section (metadata only)

**Step 5: Build `crawlers/gov.py`** — Done. Probed State Council site structure:
- JSON feed at `/zhengce/zuixin/ZUIXINZHENGCE.json` — 1,015 documents with titles, URLs, dates
- Two document templates: Template A (formal, with metadata table) and Template B (article-style)
- Both share `#UCAP-CONTENT` for body text and `<meta>` tags in `<head>`
- Template A has structured table: 发文字号, 发文机关, 主题分类, 成文日期, 发布日期
- Smoke test: 1,003 docs indexed (metadata only)

**Current state:** 46,633 total documents (45,130 gkmlpt + 500 NDRC + 1,003 State Council). Body text not yet fetched for central sites — run full crawl when ready.
