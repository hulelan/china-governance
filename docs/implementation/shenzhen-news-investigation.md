# Shenzhen News / Investment Portal — Investigation Report

*2026-03-24. Investigation of the Shenzhen investment news pages described in `investment-data-plan.md`.*

## Summary

The four target sections on `sz.gov.cn` use the **NFCMS CMS** (not gkmlpt). A new HTML scraping crawler is needed, following the `crawlers/ndrc.py` pattern. Web search confirmed the article URL pattern is `post_{ID}.html` (not `mpost_`), and the sections contain content dating back to at least 2020.

Network access to `sz.gov.cn` is **blocked from the cloud sandbox** ("Host not allowed"), but the crawlers work fine locally. The listing page HTML structure still needs local probing to confirm pagination details.

## Target URLs

| Section | URL | Content Type | Status |
|---------|-----|-------------|--------|
| 投资动态 (Investment News) | `/cn/zjsz/fwts_1_3/tzdt_1/` | FDI news, project signings | Confirmed via search — articles indexed by Google |
| 统计数据 (Statistics) | `/cn/zjsz/fwts_1_3/tjsj/` | Economic data releases | Exists but stats bureau (`tjj.sz.gov.cn`) is the better source |
| 投资指南 (Investment Guide) | `/cn/zjsz/fwts_1_3/tzzn/` | Sector guides, incentives | Not indexed by search engines — may have few/no articles |
| 营商环境 (Business Env) | `/cn/zjsz/yshj/` | Regulatory reform updates | Mostly on `hrss.sz.gov.cn` and `drc.sz.gov.cn` subdomains |

## Key Findings

### 1. Confirmed article URL pattern: `post_{ID}.html`

Web search returned real indexed article URLs. The pattern is **`post_`** (NOT `mpost_` as seen in older scratchpad notes):

```
http://www.sz.gov.cn/cn/zjsz/fwts_1_3/tzdt_1/content/post_12402125.html  (2025-09)
http://www.sz.gov.cn/cn/zjsz/fwts_1_3/tzdt_1/content/post_11988134.html  (2025-02)
http://www.sz.gov.cn/cn/zjsz/fwts_1_3/tzdt_1/content/post_9984966.html   (2022-07)
http://www.sz.gov.cn/cn/zjsz/fwts_1_3/tzdt_1/content/post_8803965.html   (2021-05)
http://www.sz.gov.cn/cn/zjsz/fwts_1_3/tzdt_1/content/post_8358187.html   (2020-12)
http://www.sz.gov.cn/cn/zjsz/fwts_1_3/tzdt_1/content/post_7967584.html   (2020-08)
http://www.sz.gov.cn/cn/zjsz/fwts_1_3/tzdt_1/content/post_7881397.html   (2020-07)
```

The IDs are monotonically increasing and span years, suggesting hundreds of articles.

### 2. CMS is NFCMS, NOT gkmlpt

The crawler scratchpad (2026-02-15) documents this clearly:

> Main portal content pages use a DIFFERENT CMS from gkmlpt. [...] Uses NFCMS CMS (not gkmlpt). Metadata in `<meta>` tags: ArticleTitle, PubDate, ContentSource, ArticleId. Content in `div.news_cont_d_wrap`.

The existing gkmlpt API only covers 政府信息公开. The investment portal is a completely separate CMS.

### 3. NFCMS article page structure (known from prior probing)

- **Meta tags**: `ArticleTitle`, `PubDate`, `ContentSource`, `ArticleId`
- **Body text**: `div.news_cont_d_wrap`
- **CMS identifiers**: `NFCMS_SITE_ID=755001`, `NFCMS_POST_ID={id}`
- The existing gkmlpt body extractor already handles this as a fallback (`gkmlpt.py:398`)

### 4. Pagination: almost certainly `createPageHTML()` + `index_{N}.html`

NFCMS sites universally use this pattern (confirmed by NDRC, MOF, and general NFCMS documentation):
- Page 1: `index.html`
- Page 2+: `index_{N}.html`
- Total pages from: `createPageHTML(totalPages, currentIdx, "index", "html")`

This matches the NDRC crawler (`crawlers/ndrc.py`) exactly.

### 5. 营商环境 and 统计数据 are better sourced elsewhere

Web search revealed:
- **营商环境** content is primarily on department subdomains (`hrss.sz.gov.cn/ztfw/yshj/`, `drc.sz.gov.cn/ztxx/yshj/`), not the main portal
- **统计数据** is primarily on the statistics bureau (`tjj.sz.gov.cn/tjsj/`), which has its own dedicated site with statistical bulletins, analysis reports, and data releases

**Recommendation**: Focus `sz_invest` crawler on **投资动态 (tzdt)** first — it has the most content on the main portal. Consider dedicated crawlers for `tjj.sz.gov.cn` and `hrss.sz.gov.cn` later.

### 6. Network access blocked from cloud sandbox

"Host not allowed" — all `.gov.cn` domains are blocked in this environment. The crawlers work fine locally (confirmed by 45K+ existing Shenzhen documents).

### 7. HTTP required (not HTTPS)

From the scratchpad: "HTTP works, HTTPS fails." All existing `SITES` entries in `gkmlpt.py` use `http://` base URLs.

## What Needs Local Probing

The only remaining unknown is the **listing page HTML structure**. Run locally:

```bash
# Fetch the listing page
curl -s -o /tmp/tzdt.html "http://www.sz.gov.cn/cn/zjsz/fwts_1_3/tzdt_1/"

# Check for createPageHTML pagination
grep -o 'createPageHTML([^)]*' /tmp/tzdt.html

# Check list item structure
grep -B1 -A2 '<li>' /tmp/tzdt.html | head -30

# Check if JSON API exists
curl -s -o /dev/null -w "%{http_code}" "http://www.sz.gov.cn/cn/zjsz/fwts_1_3/tzdt_1/index.json"
```

Key questions to answer:
1. Exact `<li>` HTML structure (href, title, date span format)
2. Total page count from `createPageHTML()`
3. Whether listing page uses `index.html` or bare directory `/`

## Recommended Crawler Architecture

Based on the NDRC crawler pattern (which handles the same NFCMS `createPageHTML` pagination):

```python
# crawlers/sz_invest.py — follows crawlers/ndrc.py pattern

SITE_KEY = "sz_invest"
SITE_CFG = {
    "name": "Shenzhen Investment Portal",
    "base_url": "http://www.sz.gov.cn",
    "admin_level": "municipal",
}

SECTIONS = {
    "tzdt": {"path": "/cn/zjsz/fwts_1_3/tzdt_1/", "name": "投资动态"},
    # Add more sections after confirming they have content:
    # "tzzn": {"path": "/cn/zjsz/fwts_1_3/tzzn/", "name": "投资指南"},
}
```

**Pagination** (copy from `ndrc.py`):
```python
def _section_url(base_path: str, page: int = 0) -> str:
    if page == 0:
        return f"http://www.sz.gov.cn{base_path}index.html"
    return f"http://www.sz.gov.cn{base_path}index_{page}.html"

def _get_total_pages(html: str) -> int:
    m = re.search(r"createPageHTML\((\d+),", html)
    return int(m.group(1)) if m else 1
```

**Listing parse** (adapt regex after local probing confirms `<li>` structure):
```python
def _parse_listing(html: str, base_url: str) -> list[dict]:
    items = []
    for m in re.finditer(
        r'<li>\s*<a\s+href="([^"]+)"[^>]*>([^<]+)</a>'
        r'.*?<span[^>]*>(\d{4}-\d{2}-\d{2})</span>\s*</li>',
        html, re.DOTALL,
    ):
        href, title, date_str = m.group(1), m.group(2), m.group(3)
        items.append({"url": urljoin(base_url, href), "title": title.strip(), "date_str": date_str})
    return items
```

**Body/meta extraction** (reuse from NDRC/gkmlpt):
```python
def _extract_body(html: str) -> str:
    # div.news_cont_d_wrap (same as gkmlpt.py:398 fallback)
    m = re.search(r'<div\s+class="news_cont_d_wrap">(.*?)</div>\s*</div>', html, re.DOTALL)
    ...

def _extract_meta(html: str) -> dict:
    # Same <meta> tag extraction as ndrc.py
    meta = {}
    for name in ("ArticleTitle", "PubDate", "ContentSource", "Keywords"):
        m = re.search(rf'<meta\s+name="{name}"\s+content="([^"]*)"', html)
        if m: meta[name] = m.group(1).strip()
    return meta
```

**Storage**: Use `store_document()` from `base.py` with `site_key="sz_invest"`, `next_id()` for IDs.

## Implementation Estimate

- **Effort**: ~1-2 hours (mostly copy-paste from `ndrc.py` + adapt listing regex after local probe)
- **Content volume**: Estimated 200-500 articles in 投资动态 (based on date range 2020-2025 and ~7 articles found in search)
- **Dependencies**: One local `curl` command to confirm listing page structure

## Open Questions

1. **Listing HTML format**: What's the exact `<li>` structure? (must probe locally)
2. **Content volume**: How many total pages? (from `createPageHTML(N, ...)`)
3. **Same table or separate?**: Recommend same `documents` table with `site_key="sz_invest"` — keeps the web app working without changes
4. **Recurring crawls?**: These are news articles updated regularly. Consider adding to `--sync` workflow.
