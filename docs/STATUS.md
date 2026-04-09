# Project Status

*Last updated: 2026-04-07*

## Corpus Summary

| Metric | Value |
|--------|-------|
| Total documents | 138,894 |
| With body text | ~128,857 (93%) |
| Total sites | 66 |
| Algorithmic scores | All docs scored: citation_rank, algo_doc_type (19 types), ai_relevance (0-1) |
| High AI relevance (>=0.5) | 195 docs |
| Medium+ AI relevance (>=0.2) | 2,627 docs |
| Docs with inbound citations | 12,102 |
| Classified (v2 prompt) | ~24,000 (18%). Paused — restart when ready |
| Classified (v1 only) | ~109,000 (have title_en/summary_en but no doc_type/policy_significance) |
| Citations | 227,516 (14,265 LLM-sourced) |

## Production

| Component | State |
|-----------|-------|
| Website | Live at chinagovernance.com. DigitalOcean droplet, nginx + uvicorn + SQLite |
| Droplet | 104.236.88.45 (NYC3, 2 vCPU / 2GB RAM / 2GB swap, $18/mo) |
| Databases | Two SQLite files rsynced from Mac: `documents.db` (~2GB, policy corpus) and `officials.db` (250MB, CCP elite) |
| SSL | Let's Encrypt via certbot, auto-renews. Expires July 4, 2026 |
| DNS | Squarespace. A records for @ and www → 104.236.88.45 |
| Local DB | SQLite `documents.db` on Mac (source of truth) |
| Daily pipeline | Run manually: `nohup ./scripts/daily_sync.sh &`. Crawl → backfill → WAL checkpoint → rsync → restart |
| Telegram | Reports sent after each daily sync run |
| Caching | Homepage/dashboard/chain cached 1hr in-memory. First visitor after restart pays ~10-25s cold load |
| Workers | uvicorn with 2 workers (handles concurrent requests while one is doing heavy query) |
| **Old Railway Postgres** | Decommissioned 2026-04-06. No longer used |
| **Old Singapore droplet** | 152.42.184.25. Still alive, outdated code. Could be used as cold backup |

## Crawlers — Central Government

| Site Key | Name | Docs | Bodies | Body% | Notes |
|----------|------|------|--------|-------|-------|
| mofcom | Ministry of Commerce | 2,940 | 1,281 | 44% | 6 sections. Export control bodies still crawling |
| samr | SAMR (市场监管总局) | 2,544 | 2,356 | 93% | 6 sections. ~15k more in news sections (not yet crawled) |
| ndrc | NDRC | 1,617 | 910 | 56% | Body backfill needed |
| most | MOST (科技部) | 1,495 | 499 | 33% | Slow from US; partial results expected |
| gov | State Council | 1,013 | 1,013 | 100% | — |
| mof | Ministry of Finance | 919 | 912 | 99% | — |
| cac | CAC (网信办) | 747 | 738 | 99% | — |
| mee | Ministry of Ecology | 563 | 494 | 88% | — |
| miit | MIIT (工信部) | 103 | 26 | 25% | Slow from US (~30/day); was faster from droplet |
| sic | State Information Center | 1,117 | 1,117 | 100% | www.sic.gov.cn |
| nda | National Data Administration | 379 | 379 | 100% | 5 sections. Every doc is AI/data policy |

### gkmlpt Sites (Guangdong — `crawlers/gkmlpt.py`)

| Site Key | Name | Docs | Bodies |
|----------|------|------|--------|
| sz | Shenzhen Main Portal | 1,010 | 951 |
| gd | Guangdong Province | 6,179 | 6,017 |
| gz | Guangzhou | 3,656 | 3,555 |
| huizhou | Huizhou | 3,826 | 3,702 |
| jiangmen | Jiangmen | 4,241 | 4,145 |
| jieyang | Jieyang | 5,872 | 5,793 |
| heyuan | Heyuan | 3,777 | 3,269 |
| shanwei | Shanwei | 3,610 | 3,513 |
| zhongshan | Zhongshan | 5,152 | 4,970 |
| zhuhai | Zhuhai | 3,540 | 3,355 |
| yangjiang | Yangjiang | 2,355 | 2,290 |
| shaoguan | Shaoguan | 1,613 | 1,539 |
| yunfu | Yunfu | 658 | 551 |
| shantou | Shantou | 49 | 48 |
| zhaoqing | Zhaoqing | 0 | 0 |

**Known unreachable gkmlpt sites:** Dongguan, Foshan, Meizhou, Maoming, Qingyuan, Bao'an (DNS/timeout/Cloudflare).

### Shenzhen Departments (gkmlpt)

| Site Key | Name | Docs | Bodies |
|----------|------|------|--------|
| szdp | Dapeng New District | 8,586 | 8,447 |
| szlhq | Longhua District | 6,280 | 6,051 |
| ga | Public Security Bureau | 5,093 | 5,014 |
| mzj | Civil Affairs Bureau | 4,847 | 4,481 |
| szlg | Longgang District | 3,893 | 3,699 |
| hrss | Human Resources & Social Security | 3,106 | 2,831 |
| swj | Commerce Bureau | 2,920 | 2,561 |
| jtys | Transport Bureau | 2,903 | 2,601 |
| stic | S&T Innovation Bureau | 2,362 | 1,688 |
| fgw | Development & Reform Commission | 1,953 | 1,142 |
| zjj | Housing & Construction | 2,388 | 2,143 |
| sf | Justice Bureau | 2,033 | 1,781 |
| szeb | Education Bureau | 2,012 | 1,894 |
| yjgl | Emergency Management | 2,018 | 1,837 |
| wjw | Health Commission | 1,262 | 1,212 |
| szgm | Guangming District | 913 | 810 |
| szlh | Luohu District | 762 | 707 |
| audit | Audit Bureau | 475 | 424 |
| szns | Nanshan District | 309 | 205 |
| szft | Futian District | 211 | 116 |
| szpsq | Pingshan District | 1,635 | 1,279 |
| szyantian | Yantian District | 0 | 0 |

### Other Provinces/Municipalities

| Site Key | Name | Docs | Bodies | Body% | Notes |
|----------|------|------|--------|-------|-------|
| hlj | Heilongjiang | 2,265 | 2,247 | 99% | JSON API, 8 sections |
| sh | Shanghai | 3,830 | 3,826 | 100% | — |
| bj | Beijing | 1,781 | 1,761 | 99% | — |
| js | Jiangsu | 1,041 | 1,041 | 100% | — |
| wuhan | Wuhan | 999 | 958 | 96% | 5 sections incl. AI industry portal |
| cq | Chongqing | 697 | 697 | 100% | — |
| suzhou | Suzhou | 4,841 | 3,817 | 79% | JSON API, body backfill may help |
| zj | Zhejiang (Depts) | 70 | 47 | 67% | Page 1 only from US; full pagination needs Chinese IP |
| hangzhou | Hangzhou | 0 | 0 | — | JCMS, page 1 only from US |
| sz_invest | Shenzhen Investment | 1,731 | 1,727 | 100% | — |

### Media & Research

| Site Key | Name | Docs | Bodies | Body% | Notes |
|----------|------|------|--------|-------|-------|
| xinhua | Xinhua (新华社) | 2,556 | 2,531 | 99% | **5 sections (closed homepage gap 04-07):** tech, fortune, politics_docs, politics_read, **general** (homepage scrape covering 时政/国内/国际/domestic/world). The first 4 use Xinhua's JSON datasource feeds; `general` scrapes the xinhuanet.com homepage HTML for `/{YYYYMMDD}/{uuid}/c.html` URLs. ~147 URLs discovered per fetch but only ~8 are live (Xinhua deletes general-news articles after ~6 weeks). |
| stdaily | Science & Technology Daily (科技日报) | 200 | 200 | 100% | Official MOST newspaper — effectively a central-government voice on tech/AI/innovation policy. Discovery via `sitemap.xml` (~200 recent URLs) + homepage (`--deep`). **No browsable historical archive** — only rolling last ~4 days per fetch |
| guancha | Guancha / Observer Network (观察者网) | 710 | 667 | 94% | Influential nationalist-aligned commentary site. Homepage (~185 links) + 7 section pages + columnist pages (`--deep`, ~700/run). **43 docs (~6%) are intentionally title-only** — empirical survey: 38 paywalled member content (`paywall_member`), 3 Xinhua SPA mirrors (`redirect_xinhua`), ~2 untagged variants. Stored as title-only rows tagged via `classify_genre_name` so the gap is filterable rather than hidden. Author slugs stored in `classify_theme_name` for future author-citation analysis. |
| people | People's Daily (人民日报) | 1,102 | 1,102 | 100% | 17 editorial sections from opinion.people.com.cn |
| ifeng | Phoenix/风声 | 180 | 180 | 100% | Added tech section |
| latepost | LatePost (晚点) | 94 | 94 | 100% | ~94 recent articles, no pagination |
| tsinghua_aiig | Tsinghua AIIG | 57 | 43 | 75% | 14 WeChat links (no body) |
| 36kr | 36Kr (36氪) | 10 | 10 | 100% | RSS feed, ~10-30 items per fetch |

## Daily Pipeline

Run manually on Mac: `nohup ./scripts/daily_sync.sh > logs/daily_$(date +%Y%m%d_%H%M).log 2>&1 &`

Auto-run not working yet — macOS blocks cron/launchd from accessing ~/Desktop without Full Disk Access for `/usr/sbin/cron`. To fix: System Settings → Privacy & Security → Full Disk Access → add /usr/sbin/cron.

**Phase 1 — Crawl (~60 crawlers, 4-5 hours):**
- Central: gov, ndrc, mof, mee, cac, nda, sic, samr, mofcom, ipc_court
- Provinces: beijing, shanghai, jiangsu, chongqing, wuhan, suzhou, heilongjiang
- Guangdong gkmlpt: 40+ sites via `--sync`, plus gd/huizhou/yangjiang individually
- Slow-from-US: miit, most, zhejiang, hangzhou (partial data)
- Research: tsinghua_aiig
- Shenzhen non-gkmlpt: sz_invest
- Media: 36kr, latepost, ifeng, xinhua, people

**Phase 2 — Classify** (skipped if `DEEPSEEK_API_KEY` not in `.env`)

**Phase 3 — Rsync to production:**
- WAL checkpoint → rsync documents.db → restart uvicorn on droplet
- Verifies doc count on droplet matches local

**Reporting:** Telegram message with per-crawler results, doc counts, errors.
Note: `UNIQUE constraint failed: documents.url` errors in the report are harmless — just duplicate docs from incremental re-crawls.

**30-min timeout** per crawler to prevent pipeline stalls.

## Crawler Coverage — What We Get vs Miss

Each site has many sections; we only crawl the policy-relevant ones.

| Site | Sections We Crawl | What We Miss |
|------|-------------------|--------------|
| **SAMR** (6 sections) | 总局文件, 政策解读, 新闻(总局/司局/地方/媒体聚焦) | Technical standards, enforcement case databases, product recall lists |
| **MOFCOM** (6 sections) | 政策发布 + 5 export control sections (国内/国际动态, 各方观点, 常见问题, 政策法规) | Trade statistics, FDI data, press conferences, anti-dumping rulings |
| **MIIT** (3 sections) | 文件发布, 政策发布, 政策解读 | Industry data/reports, telecom licenses, project approvals, spectrum allocation |
| **NDRC** | 政策文件, 政策解读, 新闻发布 | Project approval lists, price monitoring, bond issuance data |
| **MOF** | 财政政策, 政策解读 | Budget data, bond auction results, accounting standards |
| **MEE** | 政策法规, 环评审批 | Air/water quality data, emissions monitoring, enforcement actions |
| **CAC** | 政策法规 | Takedown notices, app store reviews, content moderation decisions |
| **NDA** (5 sections) | 政策发布, 通知公告, 政策解读, 专家解读, 公开内容 | (Comprehensive — small site, we get most of it) |
| **SIC** (6 sections) | 数字中国, 信息化, 电子政务, 宏观分析, 新闻, 成果 | (Comprehensive) |
| **Suzhou** (6 sections) | 全部政策文件, 市政府/办公室文件, 规章, 人事, 其他 | City news, economic development reports, public service announcements |
| **gkmlpt sites** (40+) | 政府信息公开目录 (standard Guangdong transparency API) | Non-transparency content (news, services) |
| **Beijing** (5 sections) | 政策文件 across multiple categories | 工作动态 (work updates) section not yet crawled |
| **Shanghai** (6 sections) | Year-archive policy documents | Municipal news, district-level content |
| **Xinhua** | 5 sections: 科技 (tech), 财经 (fortune), 中央文件发布 (politics_docs), 中央文件解读 (politics_read), **首页综合 (general — homepage scrape, added 04-07)** | Each JSON section feed caps at ~1,000 items (~4–5 months); homepage section captures ~147 stories per fetch with no historical pagination. |
| **People's Daily** | 17 opinion editorial sections from opinion.people.com.cn | Main news (people.cn), regional editions, peopleapp.com (SPA, needs API work) |
| **ifeng** | 风声 + tech + 9 regional channels | Financial news, entertainment, video content |
| **stdaily** | Rolling last ~4 days via `sitemap.xml` (~200 recent URLs), homepage with `--deep` | **No historical archive** — no browsable month/year index, no pagination. Coverage accumulates only by running daily. Older content reachable only if we guess content IDs or use Wayback |
| **guancha** | Homepage (~185 links) + 7 in-section pages (politics/economy/internation/qiche/kegongliliang/xinzhiguanchasuo/xinqiang) + all columnist pages with `--deep` | **No pagination** on section pages. Politics-speech pages have title + date but **no body** (Guancha redirects to Xinhua via JS). Sections `society`/`military`/`zhongguo` fall back to homepage |

**General pattern:** We crawl **policy documents and interpretations** (政策文件 + 政策解读). We skip **data/statistics**, **enforcement actions**, **news/media**, and **public services**. This is intentional — policy docs are the core research value.

## Officials Database (officials.db — 250MB)

Separate SQLite database for CCP elite career data. Lives alongside documents.db
on Mac and droplet. Both rsynced together during daily sync.

| Metric | Value |
|--------|-------|
| Total officials | 2,181 unique CC members (7th–20th Congress, 1945-2022) |
| Politburo members | 145 |
| PSC members | 45 |
| Baike pages crawled | 2,155 / 2,181 (98.8% success) |
| Failed | 26 (no Baike page or disambiguation issue) |
| Career records parsed | 17,727 from 1,628 officials |
| Overlaps computed | 5,121 (pairs who served in same org with time overlap) |
| Source data | CPC_Elite_Leadership_Database.xlsx (Jonathon P Sine) |

**Tables:**
- `officials` — name, birth year, home province, CC membership, Baike HTML + career text
- `career_records` — (official_id, position, organization, province, admin_level, start/end year/month)
- `overlaps` — (official_a, official_b, organization, overlap_start_year, overlap_end_year, overlap_months)

**Pipeline:**
```
CPC_Elite_Leadership_Database.xlsx
    ↓ load_members_from_excel() (openpyxl)
officials table
    ↓ crawlers/baike.py — scrapes baike.baidu.com/item/{name_cn}
baike_html + baike_career_text
    ↓ parse_career_text() — regex for 3 date formats
career_records table
    ↓ scripts/compute_overlaps.py — pairwise overlap by shared normalized org
overlaps table
    ↓ aiosqlite read-only in FastAPI lifespan
API: /api/v1/officials/network + /api/v1/officials/{id}
    ↓ D3.js force-directed graph
Page: /officials
```

**Live at:** https://www.chinagovernance.com/officials
- Filters: min overlap months, year range, Politburo only
- Click node → career history + top 15 overlaps
- PSC = red, Politburo = orange, CC = blue

**Parser coverage:**
- 76% of officials have parsed records (1,628 / 2,155)
- Missing: old leaders (pre-1978) with narrative biographies
- Works on 3 Baike formats: `YYYY.MM-YYYY.MM position`, `YYYY-YYYY年 position`, `YYYY年M月 position`

**Overlap logic:**
- Skips non-org entries (joining party, education, birth)
- Groups by normalized org key (first 4+ chars ending at position marker)
- Pairs with overlapping date ranges become edges
- No end date → assume 4 years (typical CCP term length)
- Province-only overlaps excluded (too broad to be meaningful)

## Recent Completions (2026-04-05 — 04-07)

- **Officials page: PSC mobility + governments view** (2026-04-07): `/officials` now has a two-tab layout. **Network Graph** (existing) + new **PSC Mobility** tab — a horizontal bar chart of how many distinct provinces each of the 45 Standing Committee members served in across their career (Zhu De 8, Deng 7, Zhou Enlai 7, Li Keqiang 6, Xi Jinping 5: Shaanxi→Hebei→Fujian→Zhejiang→Shanghai). Bars click through to the shared detail panel. The detail panel was also enhanced with a **Governments served in** section that groups each official's career by organization/province and lists the OTHER officials we have records for who also served in that government — e.g., clicking Xi Jinping surfaces Cai Qi (current PSC colleague) as a Fujian-era co-official from 1985-2000. New API endpoints: `GET /api/v1/officials/psc/provinces`, and `/officials/{id}` now also returns a `governments` array.
- **Xinhua general-news section** (2026-04-07): `crawlers/xinhua.py` now has a 5th section, `general`, that scrapes the xinhuanet.com homepage HTML for top-level article URLs (`/{YYYYMMDD}/{uuid}/c.html`). These are the domestic/world/时政 stories that no JSON datasource covers. **Discovers ~147 URLs per fetch but only ~8 are live** — Xinhua's general-news content has ~6-week retention; the homepage HTML still references deleted articles via static carousels. Yield: ~8 fresh articles/run × daily = ~2,800/year. First run captured oil-price regulation, anti-poverty employment, satellite mission identifiers — substantive central-voice content. Closes the long-standing "Xinhua general-news section" backlog item.
- **Wayback backfill script** (2026-04-07): `scripts/wayback_backfill.py` discovers historical URLs via the Internet Archive CDX API, tries each live URL first (most 2024+ stdaily content is still live), falls back to Wayback snapshots via `web.archive.org/web/{ts}if_/`, and rejects stub pages (15175-byte 404 + 稿件详情 placeholder) on both paths. Verified end-to-end with 50 stdaily articles. CDX reports ~5k discoverable URLs/year per site.
- **Guancha redirect tagging** (2026-04-07): An empirical survey of 44 empty-body guancha pages found **82% are paywalled member content** (`user.guancha.cn/main/content`), ~14% are CCTV 天天学习 Xi-speech program redirects, and ~4% are Xinhua SPA mirrors. Rather than dropping these from the corpus, `crawlers/guancha.py` now stores them as title-only rows with `classify_genre_name` set to one of `paywall_member` / `redirect_cctv` / `redirect_xinhua` so the corpus retains a record that the article existed and the gap is filterable.
- **Two new media crawlers** (2026-04-07): `crawlers/stdaily.py` for 科技日报 (Science & Technology Daily — MOST's official newspaper, `admin_level=central`) and `crawlers/guancha.py` for 观察者网 (Guancha / Observer Network, `admin_level=media`). Both added to `daily_sync.sh`. stdaily discovers via `sitemap.xml` (rolling ~200 URLs/4 days). guancha runs in `--deep` mode covering homepage + 7 section pages + all columnist pages (~690 URLs/run). Neither site has pagination or a historical archive — coverage will accumulate via daily runs.
- **Guancha author-slug capture**: Columnist sections (CamelCase slugs like `GuanJinRong`, `TuZhuXi`) are stored in `classify_theme_name` to enable future analysis of which named authors get referenced in policy docs vs which remain uncited. Tracked as a research analysis task.
- **Officials Network live** (2026-04-07): `/officials` page shows CCP elite career overlap graph. 5,121 overlaps from 17,727 career records. D3.js force-directed, filterable by overlap duration, year range, Politburo-only. Click node → full career + top overlaps.
- **compute_overlaps.py**: Groups career records by normalized org key, computes pairwise overlaps with realistic end-date inference (4-year default), filters out non-org entries (party-joining, education, birth).
- **Officials crawler**: `crawlers/baike.py` scraped Baidu Baike for 2,155/2,181 CC members (98.8% success). Parses 3 Baike career formats via regex, no LLM needed. 17,727 career records extracted.
- **Web app opens 2 SQLite DBs**: `documents.db` for policy corpus, `officials.db` for elite career data. Lifespan handler opens both read-only, separate aiosqlite connections.
- **daily_sync.sh rsyncs officials.db too**: WAL checkpoint + rsync for both DBs.
- **VPS migration complete**: Railway Postgres → DigitalOcean droplet (104.236.88.45, NYC3). SQLite served directly via rsync. No more Postgres timeouts.
- **Daily pipeline rsyncs to droplet**: WAL checkpoint → rsync → restart. First successful end-to-end run Apr 6 (+616 new docs).
- **Performance fixes**: Homepage/dashboard/chain cached 1hr, dashboard uses citations table (was loading 1GB of body text), network API rewritten to use citations table.
- **Network page improved**: Default date range 2024+, policy type filter (19 types + untyped), min citations raised to 3.
- **Dashboard ZeroDivisionError fixed**: Sites with 0 docs no longer crash the page.
- **Chain renamed to "Policy Trace"**: User-facing rename in nav, headings, titles.
- **SQLite `!= ALL()` translation**: Fixed chain page crash — added `NOT IN` conversion for Postgres→SQLite queries.

## Recent Completions (2026-03-29 — 04-05)

- **Website redesign**: All 13 templates rewritten. White/serif research theme, flipped document layout (body left, metadata right), proper Chinese typography (line-height 1.9). Merged to main, live on production.
- **Algorithmic document scoring**: citation_rank (PageRank-like, weighted by source level), algo_doc_type (19 types from title regex), ai_relevance (0-1 keyword density). 51 docs identified as both high-AI and frequently cited — the core AI policy reading list. Browse page supports filtering/sorting by all three.
- **Body text backfill**: `backfill_from_html.py` re-extracted 1,703 bodies from saved raw HTML (MOST +685, NDRC +690, heyuan +229). Coverage 91% → 93%.
- **MOST body extraction fix**: Added TRS_UEDITOR and `text wide` content div support (was only looking for `id=Zoom`).
- **SIC crawler** (1,117 docs from www.sic.gov.cn — digital economy, informatization, e-gov, macro analysis)
- **NDA expanded** to 5 sections (34 → 379 docs)
- **ifeng expanded**: tech section (+80), 9 regional channels (hlj, ah, jl, sd, gd, js, hn, hb, cq)
- **IPC Court crawler** built (ipc.court.gov.cn — Supreme Court IP Tribunal, ~5k articles, pending deep run)
- **Incremental Postgres sync**: `sqlite_to_postgres.py` only sends docs with id > max Postgres id (was re-sending all 135k every time)
- **Daily pipeline fixes**: hostname detection via `uname` (was hardcoded, kept changing), macOS `timeout` fallback, mofcom added to crawler list
- **launchd issue found**: macOS blocks `/bin/bash` without Full Disk Access. Manual runs for now.
- Classification v2 prompt, URL dedup, 14+ new crawlers, bidirectional citations, LLM citation integration (from prior sessions)

## Backlog — What To Do Next

### Infrastructure
| Task | Priority | Notes |
|------|----------|-------|
| ~~Migrate off Railway Postgres~~ | **Done** | Replaced with DigitalOcean droplet + rsync (2026-04-06) |
| Set up cron auto-run | Medium | Grant Full Disk Access to `/usr/sbin/cron`, add crontab entry. Currently running manually. |
| Run IPC Court deep crawl | Medium | `python3 -m crawlers.ipc_court --deep` — iterates all ~5k article IDs. Run when DB is free. |
| Re-classify all docs with v2 prompt | **Paused** (24k/137k) | Add `DEEPSEEK_API_KEY` to `.env` to enable. ~$55 remaining, ~4 days at concurrency 2 |
| Back up documents.db offsite | Medium | rsync to Singapore droplet or external drive. Mac is single point of failure for 2 years of crawl data. |
| Decommission Railway | Low | Old Postgres still exists. Can be deleted to stop billing. |

### Website
| Task | Priority | Notes |
|------|----------|-------|
| ~~Redesign~~ | **Done** | White/serif research theme, merged to main |
| ~~Surface scores in browse/search~~ | **Done** | Doc type filter, AI relevance filter, citation rank sort |
| Show references_json on document pages | Medium | Clickable links to referenced policies |
| Semantic search (embeddings) | Medium | Generate embeddings for all docs, enable "similar documents" and meaning-based search. ~$1 GPU job. |

### Data Quality
| Task | Priority | Notes |
|------|----------|-------|
| Translate high-significance docs to English | High | Full body translation for AI policy docs. DeepSeek or dedicated translation API |
| Update chain.py for bidirectional queries | Medium | Code tested (8/8 green), needs deployment to web service |
| Re-run extract_citations.py after classification finishes | Medium | More references_json = more LLM citations |
| Reduce "other" doc type bucket | Low | 68k docs classified as "other" — need more title regex patterns |
| SAMR full news sections | Low | ~15k more docs across xw_zj, xw_sj, xw_df, xw_mtjj |
| ~~Xinhua general-news section~~ | **Done 04-07** | Homepage scrape added as 5th xinhua section. ~147 URLs/run. |
| **stdaily Wayback backfill** | Medium | `python3 scripts/wayback_backfill.py --site stdaily --from 2020 --to 2025`. Expected ~20-25k articles. CDX reports ~5k URLs/year. Runs ~6-10 hours; live URLs work for most 2024+ content, Wayback fills the rest. Verified end-to-end with `--limit 50`. |
| **guancha Wayback backfill** | Medium | `python3 scripts/wayback_backfill.py --site guancha --from 2020 --to 2025`. Slower than stdaily because Wayback CDX rate-limits guancha aggressively (frequent 503s). Plan as multi-day patient run with longer delays. Expected ~10-15k articles. |
| stdaily / guancha rolling daily accumulation | (Auto) | Already running via `daily_sync.sh`. ~200 stdaily + ~700 guancha URLs discovered per run, ~10-30 net new per day. |
| ~~guancha: fetch body for politics-speech pages~~ | **Wontfix** | Survey showed 82% of empty-body guancha pages are paywalled member content (not politics speeches). The remaining ~18% redirect to Xinhua/CCTV SPAs that need a headless browser. Title-only rows are now tagged via `classify_genre_name` for filterable corpus visibility. Higher-value coverage of Xi speeches now comes from the new xinhua `general` section. |

### Officials Network Improvements
| Task | Priority | Notes |
|------|----------|-------|
| Cross-link officials ↔ documents | **High** | Match document publishers/signatories against officials table. Show which policies each person authored/signed during their tenure. |
| Add missing collision twins | Medium | Excel had 31 name collisions (e.g., two 李强s, three 刘伟s) but the original `baike.py` loader deduplicated by `name_cn` alone, silently keeping only the first occurrence. Loader is now fixed to use `(name_cn, birth_year)`, and `scripts/fix_baike_collisions.py` already repaired the 12 Frankenstein rows where career data was stitched to the wrong metadata. Still TODO: add the ~19-30 missing twin rows + fetch Baidu Baike for each via disambiguation (bare URL `/item/{name}` serves the more-famous twin, so the other needs a numbered `/item/{name}/{disambig_id}` URL). Requires schema migration to drop the legacy `name_cn UNIQUE` constraint on existing DBs. |
| Better org normalization | Medium | 32 provinces detected, but admin_level detection is only 42% accurate. More regex patterns for 部/委/局/院. |
| Parse narrative biographies | Medium | 527 officials have 0 career records (mostly pre-1978 leaders with prose bios). Could use DeepSeek to extract. |
| Add search by name | Medium | Currently no way to find a specific person. Add search box. |
| Timeline slider | Medium | Show network state at year X (animate through years). |
| Faction detection | Low | Color-code by faction (Shanghai clique, Youth League, etc.) using clustering. |
| Cross-link to documents | Medium | "Policies issued during 李强's tenure in Zhejiang (2012-2017)" |
| **Brookings-style biography generator** | Medium-High | Auto-generate per-official analyst bios in the Brookings "20th Party Congress Leadership" format (e.g. [Ding Xuexiang PDF](https://www.brookings.edu/wp-content/uploads/2022/10/20thpartycongress_ding_xuexiang.pdf)). Four-stage plan (v0 mechanical → v1 patron-client → v2 policy preferences → v3 political prospects) with cost/feasibility analysis for each stage, algorithm sketches, prompt templates, and a regression test using the Xi-Ding patron relationship. **Full design doc:** [docs/working/brookings-bio-generator.md](working/brookings-bio-generator.md). v0 is LLM-free and can ship as a weekend job for all 1,628 officials with substantive career data. |

### Source Expansion

**Not yet built:**
| Site | Level | Priority | Notes |
|------|-------|----------|-------|
| peopleapp.com | Media | High | People's Daily app. Nuxt.js SPA — article SSR works, column listing needs API reverse-engineering |
| Beijing /ywdt/gzdt/ section | Municipal | Medium | Work updates section not covered by current Beijing crawler |
| **NDRC / MOST / MIIT section expansion** | Medium | We already crawl each of these (`crawlers/ndrc.py`, `crawlers/most.py`, `crawlers/miit.py`) but only cover policy-document sections. Each ministry has additional sections we skip: news/工作动态 updates, 新闻发布会 press conferences, 领导活动 leadership activity, 司局 department pages, 地方动态 local updates. Investigate what's missing per ministry and add sections. MIIT note: runs from the droplet only (US → China times out). |
| **NDA leader-activity section + CAC original-draft section** | Medium-High | Surfaced by the [AI Governance Link Audit](working/ai-governance-link-audit.md). NDA's `/sjj/jgsz/jld/*/llhldhd/` paths (per-leader activity feeds like the Liu Liehong speeches at China Development Forum) are skipped by the current crawler — add that section. CAC systematically captures `解读` (interpretations) but misses the `征求意见稿` (draft for public comment) documents they interpret — investigate which CAC section holds originals and add it. Both issues were caught by a single real-world citation audit of an AI-governance Substack post; 2 specific URLs (NDA Liu Liehong 2026-03-23 speech, CAC 2025-12-27 chatbot measures draft) are ready for one-off ingest as part of the fix. |
| **CSTC (中国科协 — cast.org.cn)** | Central (S&T) | Medium | China Association for Science and Technology. Umbrella body for ~200 national scientific societies (physics, chemistry, informatics, AI, etc.) and a major soft-power vector for Party-science coordination. Important to include for research on how the Party-state mobilizes scientific expertise for policy. |
| **NVDB + CNCERT + TC260 — cybersecurity/standards layer** | Medium-High | Surfaced by the [AI Governance Link Audit](working/ai-governance-link-audit.md). Three authoritative cybersecurity bodies that are *completely absent* from the corpus and that AI-governance research heavily cites: **NVDB** (`nvdb.org.cn` — 国家漏洞库, National Vulnerability Database), **CNCERT** (`cert.org.cn` — 国家互联网应急中心), **TC260** (`tc260.org.cn` — 全国信息安全标准化技术委员会, source of Chinese AI safety draft practice guides). Build `crawlers/nvdb.py`, `crawlers/cncert.py`, `crawlers/tc260.py` — each ~200 lines using the existing ministry-crawler pattern. Closes the single biggest topical gap for AI safety / cybersecurity research. |
| **WeChat public-account strategy** | High | Surfaced by the [AI Governance Link Audit](working/ai-governance-link-audit.md). **>40% of citations in serious Chinese AI-governance writing are `mp.weixin.qq.com/s/{id}` URLs** — AIIA, CAICT, MSS, CNCERT, MPS, TC260 all publish primarily via WeChat public accounts (公众号). Our corpus has 493 WeChat docs only as side-effects of other crawlers (local govt sites linking out). No dedicated WeChat strategy yet. Options: headless-browser with logged-in cookies (fragile), manual curation of 5-10 priority accounts (MVP — recommended starting point), RSS mirrors (quality varies), or paid WeChat data provider. Start with manual MVP seeded from the link-audit doc's citation list. |
| **S&T organization expansion** | Central (S&T) | Medium | Beyond the existing CAS-only entry, we should add: CAE (中国工程院 — www.cae.cn), CAST (中国科协 — cast.org.cn, see above), NSFC (国家自然科学基金委 — www.nsfc.gov.cn), plus major CAS institutes (e.g., CASIA, ICT, SIAT). Together these cover the scientific-research decision-making layer that connects the bureaucracy to the research community. |
| CAS (www.cas.cn) | Central (S&T) | Medium | Chinese Academy of Sciences. Part of S&T expansion above. |
| SASAC (www.sasac.gov.cn) | Central | Medium-High | Now reachable (was timing out) |
| Shandong (www.shandong.gov.cn) | Province | Low | Empty stub in crawlers/ |
| Jiangxi, Jinan | Province/Municipal | Low | |

**Party vs state organization distinction** (Medium): Add an `org_type` dimension to the sites table (values: `party`, `state`, `hybrid`, `media`, `research`). China's Party and State are parallel structures — e.g., **Party organs** include CCP Central Committee offices (中办, 中组部, 中宣部, 中央政法委, 中央军委), provincial Party committees, discipline inspection commissions; **State organs** include State Council ministries (NDRC, MOF, MEE, MIIT, MOST), provincial governments, NPC/CPPCC, courts/procuratorates. Our current corpus is 95%+ State organs because Party organs are less publicly transparent. This dimension should be surfaced as a filter on `/browse` and `/dashboard` so users can compare Party vs State discourse, and should be the starting point for a "Party organ crawl expansion" sub-initiative (中央政法委 chinapeace.gov.cn is one confirmed reachable Party target). Also relevant to the Brookings-style biography task above — many officials move between parallel Party and State roles, and analysts distinguish them.

**Reachable, not yet scanned for AI:**
MOE, PBoC, TC260, CSRC, NBS, Sichuan, Nanjing, Ningbo, Qingdao, Wuxi, Xi'an, Xiamen, Zhengzhou + others (33 total reachable)

**Unreachable from US (19 sites):**
Anhui, Chengdu, Hebei, Henan, Hubei, Gansu, Guangxi, Inner Mongolia, Tianjin, Xinjiang, Changsha, Hefei + others

**Discovery tool:** `python3 scripts/discover_sources.py --quick` (reachability) or without flag (deep scan with AI term search)

### Research Analyses

Open research questions we plan to investigate over the corpus:

| Question | Notes |
|----------|-------|
| **Referenced vs non-referenced authors** | For media sources where we capture named author bylines (guancha columnists, Xinhua, People's Daily, ifeng), compare which authors get **cited in policy documents** vs which remain uncited. Which columnists shape official narratives? Which are pure commentary with no policy footprint? Requires: (1) reliable author extraction per source, (2) citation matching — since policy docs typically cite by doc number not author, this needs fuzzy name + org matching. Start with guancha columnists (stored in `classify_theme_name` for the guancha site). |
| **Policy language genealogy** | How do phrases/slogans in central policy documents propagate into provincial and municipal docs? Track n-gram diffusion with dates. |
| **AI policy acceleration curve** | Rate of AI-tagged policy issuance over time, by level. Use `ai_relevance` + `date_written`. |

## Classification

| Item | Value |
|------|-------|
| Model | DeepSeek API |
| Classified (v1 prompt) | ~109,000 docs |
| Classified (v2 prompt) | 24k/135k done (paused) |
| Cost | ~$0.50/1k docs |
| Concurrency | Keep at 2 (DeepSeek silently rate-limits with empty responses at higher) |
| To enable | Add `DEEPSEEK_API_KEY=sk-...` to `.env` — daily pipeline will auto-classify |

## Future: ML & Interpretability

Long-term ambitions for the corpus beyond crawling and classification.

### Semantic Search & Embeddings
- Generate embeddings for all 135k docs using a Chinese embedding model (BGE-M3 or similar)
- Enable "similar documents" and meaning-based search on the website
- Cluster documents by topic without keyword matching
- Cost: ~$1 GPU job on Modal or RunPod. Store in SQLite or vector DB.
- **This is the highest-impact ML project** — transforms navigation of the corpus

### Fine-tune a Chinese Policy Classifier
- Train a small model (Qwen-7B or Yi-6B) on our labeled data (24k v2-classified docs) to replace DeepSeek API
- Would eliminate the $0.50/1k API cost and run locally
- Need: A10 GPU for a few hours (~$5-20 on Lambda/RunPod)
- Could also classify doc_type and ai_relevance more accurately than regex

### Interpretability Over the Corpus
- Analyze how policy language propagates from central → local (do districts copy-paste or adapt?)
- Track evolution of key terms (人工智能, 新质生产力, 算力) over time and across admin levels
- Identify which central policies generate the most local implementation activity
- Map the "influence graph" — which ministries' language appears most in local docs

### Compute Options
| Provider | Use case | Cost |
|----------|----------|------|
| Modal | Embeddings, batch inference (serverless GPU, pay-per-second) | ~$1/job |
| RunPod | Fine-tuning, longer GPU sessions | $0.20-0.50/hr |
| Lambda | Serious training (H100) | $2-3/hr |
| Google Colab | Quick experiments | Free (T4) / $10/mo (A100) |
