# Crawling Runbook

How to run each crawler, add new sites, and handle common issues.

## Quick Reference

```bash
# gkmlpt (Guangdong sites)
python3 -m crawlers.gkmlpt --list-sites          # Show all sites
python3 -m crawlers.gkmlpt --site sz              # Crawl one site
python3 -m crawlers.gkmlpt --backfill-bodies      # Backfill missing body text
python3 -m crawlers.gkmlpt --sync                 # Incremental sync (new/changed)

# Central ministries
python3 -m crawlers.ndrc                          # NDRC
python3 -m crawlers.gov                           # State Council
python3 -m crawlers.mof                           # Ministry of Finance
python3 -m crawlers.mee                           # Ministry of Ecology & Environment
python3 -m crawlers.most                          # Ministry of Science & Technology
python3 -m crawlers.cac                           # Cyberspace Administration of China
python3 -m crawlers.miit                          # Ministry of Industry & IT

# Provinces
python3 -m crawlers.beijing                       # Beijing
python3 -m crawlers.shanghai                      # Shanghai
python3 -m crawlers.jiangsu                       # Jiangsu

# Non-gkmlpt Shenzhen
python3 -m crawlers.sz_invest                     # Investment news, DRC, Longgang AI

# Media
python3 -m crawlers.latepost                      # LatePost (163.com)
python3 -m crawlers.36kr                          # 36Kr (RSS feed)
python3 -m crawlers.ifeng                         # Phoenix/风声 (ifeng.com)
```

All crawlers support `--stats`, `--list-only`, `--db <path>` flags.

## Per-Crawler Details

### gkmlpt Sites (`crawlers/gkmlpt.py`)

- **Technique:** JSON API at `{base_url}/inteligent/...`
- **Scope:** Guangdong province only (21 confirmed sites, 6 unreachable)
- **Adding a site:** Add to `SITES` dict in `crawlers/gkmlpt.py`:
  ```python
  "newcity": {"name": "City Name", "base_url": "http://www.example.gov.cn", "admin_level": "municipal"}
  ```
- **Known issues:** Dongguan, Foshan, Meizhou, Maoming, Qingyuan, Bao'an unreachable

### NDRC (`crawlers/ndrc.py`)

- **Technique:** Static HTML listing pages with `createPageHTML()` pagination
- **Sections:** Policy releases, interpretations, notices

### State Council (`crawlers/gov.py`)

- **Technique:** JSON API at `sousuo.www.gov.cn`
- **Sections:** Policies (zhengce), regulations (fagui)

### MOF (`crawlers/mof.py`)

- **Technique:** Static HTML + PDF extraction (财政文告 bulletins)
- **Sections:** zcfb (政策发布), czxw (财政新闻), czwg (财政文告/PDF)

### MEE (`crawlers/mee.py`)

- **Technique:** Static HTML with `.shtml` extension, path-based pagination (`index_PAGEID_N.shtml`)
- **Sections:** gwywj, sthjbwj, fl, xzfg, guizhang, bz

### MOST (`crawlers/most.py`)

- **Technique:** Static HTML, TRS CMS. Two listing formats: table (xxgk sections with `data_list`) and list (`info_list2`). Body in `div#Zoom`.
- **Sections:** gfxwj (规范性文件), zcjd (政策解读), tztg (通知通告), kjbgz (科技部工作)
- **Pagination:** `index.html` → `index_1.html` → `index_{N-1}.html`. Total pages in `pagination_script_config.total`.
- **Known issues:** tztg and kjbgz body fetching hangs from US (timeout). Run from droplet.

### CAC (`crawlers/cac.py`)

- **Technique:** JSON API via `POST https://www.cac.gov.cn/cms/JsonList` with `channelCode`, `perPage`, `pageno` parameters.
- **Sections:** wxfb (网信发布, code A093702), zcfg (政策法规, code A093703)
- **Article page:** Title in `h1.title`, date in `span#pubtime`, body in `div#BodyLabel`
- **Known issues:** HTML listing page for zcfg returns 404 (API works fine)

### MIIT (`crawlers/miit.py`)

- **Technique:** Elasticsearch search API at `https://www.miit.gov.cn/search-front-server/api/search/info`
- **Parameters:** `websiteid=110000000000000`, `category` (51=wjfb, 183=zcfb, 163=zcjd), `pg=15`, `p=N`
- **Sections:** wjfb (文件发布), zcfb (政策发布), zcjd (政策解读)
- **Known issues:** API frequently times out from US. 2,621 docs found in wjfb alone. Must run from droplet.

### Beijing (`crawlers/beijing.py`)

- **Technique:** Static HTML, 5 sections
- **Body coverage:** 99%

### Shanghai (`crawlers/shanghai.py`)

- **Technique:** Static HTML, 6 sections with year-based archive pages
- **Body coverage:** 99%

### Jiangsu (`crawlers/jiangsu.py`)

- **Technique:** jpage API
- **Body coverage:** 100%

### LatePost (`crawlers/latepost.py`)

- **Technique:** Scrapes 163.com channel page (`dy/media/T1596162548889.html`) for article URLs. Body from `div.post_body`.
- **Scope:** ~85 recent articles. No pagination — run regularly for incremental capture.
- **Publisher segment:** `0531M1CO` in all article URLs

### 36Kr (`crawlers/36kr.py`)

- **Technique:** RSS feed at `36kr.com/feed`. Article content from `window.initialState.articleDetail`.
- **Scope:** ~10-30 items per RSS fetch. Only full articles (`/p/` URLs), skips newsflashes.
- **Note:** Homepage has WAF, but RSS and article pages work with browser UA.

### Phoenix/风声 (`crawlers/ifeng.py`)

- **Technique:** Scrapes ifeng.com channel page for article URLs. Body from CSS-module hashed classes (`index_text_*`).
- **TODO:** Column ID `14-35083` targets military articles. Need correct ID for 风声 domestic policy commentary.

## Common Issues

### Database locked
**Cause:** Two writers on documents.db simultaneously.
**Fix:** Never run two crawlers in parallel. Use `--db documents_new.db` for the second, then `scripts/merge_db.py`.

### IPv6 failures
**Cause:** Many .gov.cn sites unreachable over IPv6.
**Fix:** The base crawler monkey-patches to force IPv4. If still failing, check `crawlers/base.py` IPv4 patch.

### Timeouts on MIIT/MOST
**Cause:** US→China network latency.
**Fix:** Run from the droplet (Singapore, lower latency to .gov.cn sites).

### Geo-blocked sites
Sites behind WAF (Zhejiang main, Anhui, Hefei) or with DNS that doesn't resolve outside China.
**Fix:** Run from a China-adjacent or China-based IP. The Singapore droplet works for some but not all.
