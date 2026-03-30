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
python3 -m crawlers.nda                           # National Data Administration

# Provinces
python3 -m crawlers.beijing                       # Beijing
python3 -m crawlers.shanghai                      # Shanghai
python3 -m crawlers.jiangsu                       # Jiangsu
python3 -m crawlers.zhejiang                      # Zhejiang (dept subdomains)
python3 -m crawlers.zhejiang --dept fzggw         # One department only
python3 -m crawlers.zhejiang --list-depts         # Show all departments
python3 -m crawlers.chongqing                     # Chongqing (3 sections)
python3 -m crawlers.wuhan                         # Wuhan (5 sections + AI portal)

# Research institutions
python3 -m crawlers.tsinghua_aiig                 # Tsinghua AI Governance Institute

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

- **Technique:** ishare API (`shankapi.ifeng.com/season/ishare/getShareListData/7408/doc/{page}/...`). JSONP response with `base62Id` for article URLs. Body from CSS-module hashed classes (`index_text_*`).
- **Scope:** ~100 articles across 10 API pages. Run regularly for incremental capture.

### Zhejiang Departments (`crawlers/zhejiang.py`)

- **Technique:** Static HTML listing pages + JCMS API. Department subdomains (fzggw, kjt, jxt, sft, sthjt) accessible from US over IPv6.
- **Departments:** fzggw (发改委), kjt (科技厅), jxt (教育厅), sft (司法厅), sthjt (生态环境厅)
- **Known limitation:** JCMS API pagination returns page 1 from US regardless of `pageNo`. Full corpus (~5,600 docs) requires Chinese IP. From US, captures ~226 docs (page 1 of each section).
- **IPv6:** These sites are IPv6-only from the US. The crawler calls `allow_ipv6("zj.gov.cn")` to bypass the default IPv4 restriction.

### NDA (`crawlers/nda.py`)

- **Technique:** Static HTML listing pages at `/sjj/zwgk/zcfb/list/index_pc_N.html`. JS pagination with `totalData` variable.
- **Scope:** 34 policy documents — every one is about AI and data governance.
- **Body:** `div.article`, document numbers extracted from body text.

### Chongqing (`crawlers/chongqing.py`)

- **Technique:** Static HTML with TRS CMS. Two listing formats: table rows (`zcwjk-list-c`) for normative docs, anchor links (`listpc-item`) for regulations.
- **Sections:** szfbgt (市政府办公厅文件), szf (市政府文件), zfgz (政府规章)
- **Scope:** ~697 documents across 3 sections.

### Wuhan (`crawlers/wuhan.py`)

- **Technique:** Mixed — main sections use JS `document.writeln()` rendering, AI portal uses standard HTML. Body in `div.trs_editor_view`.
- **Sections:** gfxwj (规范性文件), szfwj (市政府文件), ai_zcwj/ai_gzdt/ai_gzcg (AI产业专栏)
- **Scope:** ~999 documents. Has a dedicated AI industry portal at `/ztzl/25zt/rgzncy/`.

### Tsinghua AIIG (`crawlers/tsinghua_aiig.py`)

- **Technique:** University CMS, static HTML. 5 sections: annual reports, research reports, monographs, academic papers, governance watch.
- **Scope:** ~57 items. WeChat-linked items (governance watch) store metadata only.
- **admin_level:** `research` (not government).

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

### Duplicate documents from multiple machines
**Cause:** `next_id()` generates MAX(id)+1 locally, so Mac and droplet can assign different IDs to the same document.
**Fix:** A partial unique index on `url` (`WHERE url != ''`) prevents duplicates. `store_document()` catches the `IntegrityError` and silently skips. The Postgres schema has the same unique index. Safe to run the same crawler from multiple machines.

### Geo-blocked sites
Sites behind WAF (Zhejiang main, Anhui, Hefei) or with DNS that doesn't resolve outside China.
**Fix:** Run from a China-adjacent or China-based IP. The Singapore droplet works for some but not all.

## Production Pipeline

Both the Mac and the Singapore droplet run `scripts/daily_sync.sh` on a schedule. Each crawls what it can reach and pushes directly to Railway Postgres. No manual merge needed.

### How it works
1. **Droplet** (daily cron, 6 AM UTC): Runs `git pull`, crawls all universal sites + droplet-only sites (miit, most, zhejiang), classifies, pushes to Postgres.
2. **Mac** (launchd, 7:03 AM ET): Crawls all universal sites + Mac-only sites (gd, huizhou, yangjiang), classifies, pushes to Postgres.
3. **Dedup:** URL uniqueness index in both SQLite and Postgres prevents duplicates. `ON CONFLICT DO NOTHING` skips existing docs.
4. **Postgres is source of truth.** Local SQLite files are caches for crawling.

### Location constraints
| Crawler | Mac (US) | Droplet (SG) |
|---------|----------|-------------|
| miit, most, zhejiang | Timeout/partial | Works |
| gkmlpt (gd, huizhou, yangjiang) | Works | Connection reset |
| Everything else | Works | Works |

### Safety net
- **Daily manifest** (`backups/manifest_YYYYMMDD.csv`): Lightweight snapshot of every doc's id, url, site_key, and body length (~9MB). Compared against yesterday's — if doc count drops, a warning appears in the log and Telegram report. Kept for 14 days.
- **Body text backfill** (`scripts/backfill_bodies.py`): Runs after every Postgres sync. Pushes body text for docs that were originally synced before bodies were fetched.
- **Post-sync verification**: Compares local SQLite count vs Postgres count. Warns on mismatch.
- **Recovery**: Every doc has a URL — if data is lost, re-crawl from the manifest. No need for full DB backups.

### Adding a new crawler
1. Write the crawler module
2. Add a `run_crawler` line to `daily_sync.sh` (in the universal, Mac-only, or droplet-only section)
3. `git push` — the droplet auto-pulls before each cron run
