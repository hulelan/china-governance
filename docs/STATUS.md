# Project Status

*Last updated: 2026-03-29*

## Corpus Summary

| Metric | Value |
|--------|-------|
| Total documents | 125,126 |
| With body text | ~114,400 (91.4%) |
| Total sites | 59 |
| Classified (English title/summary/category) | ~109,000 |
| Unclassified | ~12,300 (new crawlers) |

## Production

| Component | State |
|-----------|-------|
| Website | Live at chinagovernance.com (Railway) |
| Database | PostgreSQL on Railway (synced 2026-03-30, 125,126 docs) |
| Local DB | SQLite `documents.db` (~1GB, source of truth) |
| Local → Production gap | 0 (fully synced 2026-03-30) |

## Droplet (Singapore, DigitalOcean)

| Item | Value |
|------|-------|
| IP | 152.42.184.25 |
| Spec | 1 vCPU, 1GB RAM, 25GB disk |
| Daily cron | 6 AM SGT: gkmlpt --sync, sz_invest |
| Auto-sync | `daily_sync.sh` pushes to Postgres after each crawl run |
| Auto-pull | `git pull` runs before each cron — new crawlers deploy automatically |
| Raw HTML | Disabled via `SKIP_RAW_HTML=1` to save disk |

## Crawlers — Government

| Site Key | Name | Crawler | Docs | Bodies | Issues |
|----------|------|---------|------|--------|--------|
| gov | State Council | `crawlers/gov.py` | 1,005 | 1,005 | — |
| ndrc | NDRC | `crawlers/ndrc.py` | 1,617 | 907 | — |
| mof | Ministry of Finance | `crawlers/mof.py` | 919 | 912 | — |
| mee | Ministry of Ecology | `crawlers/mee.py` | 563 | 494 | — |
| cac | CAC (网信办) | `crawlers/cac.py` | 747 | 738 | — |
| most | MOST (科技部) | `crawlers/most.py` | 1,495 | 499 | tztg/kjbgz body extraction needs droplet re-run |
| miit | MIIT (工信部) | `crawlers/miit.py` | 40 | 12 | API flaky from US, re-run from droplet |
| nda | National Data Administration | `crawlers/nda.py` | 34 | 34 | 100% AI/data relevance |
| mofcom | Ministry of Commerce | `crawlers/mofcom.py` | 2,948 | 2,756 | Export control + trade policy, 6 sections |
| samr | SAMR (市场监管总局) | `crawlers/samr.py` | 2,544 | 2,356 | 6 sections (policy + news + media focus) |

### gkmlpt Sites (Guangdong — `crawlers/gkmlpt.py`)

| Site Key | Name | Docs | Bodies |
|----------|------|------|--------|
| sz | Shenzhen Main Portal | 1,007 | 948 |
| gd | Guangdong Province | 6,169 | 6,007 |
| gz | Guangzhou | 3,647 | 3,546 |
| huizhou | Huizhou | 3,826 | 3,702 |
| jiangmen | Jiangmen | 4,228 | 4,132 |
| jieyang | Jieyang | 5,872 | 5,793 |
| heyuan | Heyuan | 3,757 | 3,248 |
| shanwei | Shanwei | 3,186 | 3,184 |
| zhongshan | Zhongshan | 2,347 | 2,344 |
| zhuhai | Zhuhai | 3,517 | 3,335 |
| yangjiang | Yangjiang | 2,355 | 2,290 |
| shaoguan | Shaoguan | 1,607 | 1,533 |
| yunfu | Yunfu | 658 | 549 |
| shantou | Shantou | 49 | 48 |
| zhaoqing | Zhaoqing | 0 | 0 |

**Known unreachable gkmlpt sites:** Dongguan, Foshan, Meizhou, Maoming, Qingyuan, Bao'an (DNS/timeout/Cloudflare).

### Shenzhen Departments (gkmlpt)

| Site Key | Name | Docs | Bodies |
|----------|------|------|--------|
| szdp | Dapeng New District | 8,587 | 8,447 |
| szlhq | Longhua District | 6,254 | 6,024 |
| ga | Public Security Bureau | 5,049 | 4,969 |
| mzj | Civil Affairs Bureau | 5,032 | 4,464 |
| szlg | Longgang District | 3,893 | 3,699 |
| hrss | Human Resources & Social Security | 3,254 | 2,820 |
| swj | Commerce Bureau | 2,909 | 2,549 |
| jtys | Transport Bureau | 2,876 | 2,573 |
| stic | S&T Innovation Bureau | 2,734 | 1,672 |
| fgw | Development & Reform Commission | 2,568 | 1,128 |
| zjj | Housing & Construction | 2,387 | 2,111 |
| sf | Justice Bureau | 2,028 | 1,760 |
| szeb | Education Bureau | 2,010 | 1,888 |
| yjgl | Emergency Management | 2,009 | 1,827 |
| wjw | Health Commission | 1,243 | 1,177 |
| szgm | Guangming District | 908 | 807 |
| szlh | Luohu District | 761 | 706 |
| audit | Audit Bureau | 475 | 422 |
| szns | Nanshan District | 310 | 205 |
| szft | Futian District | 214 | 115 |
| szpsq | Pingshan District | 1,640 | 1,279 |
| szyantian | Yantian District | 0 | 0 |

### Other Provinces

| Site Key | Name | Crawler | Docs | Bodies | Issues |
|----------|------|---------|------|--------|--------|
| bj | Beijing Municipality | `crawlers/beijing.py` | 1,781 | 1,761 | — |
| sh | Shanghai Municipality | `crawlers/shanghai.py` | 3,830 | 3,826 | — |
| js | Jiangsu Province | `crawlers/jiangsu.py` | 1,041 | 1,041 | — |
| zj | Zhejiang Province (Depts) | `crawlers/zhejiang.py` | ~226 | TBD | Page 1 only from US; full pagination needs Chinese IP |
| cq | Chongqing Municipality | `crawlers/chongqing.py` | 697 | 697 | 3 sections (normative docs + regulations) |
| wuhan | Wuhan Municipality | `crawlers/wuhan.py` | 999 | 956 | 5 sections incl. AI industry portal |

### Non-gkmlpt Shenzhen

| Site Key | Name | Crawler | Docs | Bodies |
|----------|------|---------|------|--------|
| sz_invest | Shenzhen Investment Portal | `crawlers/sz_invest.py` | 1,731 | 1,727 |

## Crawlers — Media

| Site Key | Name | Crawler | Docs | Bodies | Notes |
|----------|------|---------|------|--------|-------|
| latepost | LatePost (晚点) | `crawlers/latepost.py` | 85 | 85 | 163.com channel page, ~85 recent articles |
| 36kr | 36Kr (36氪) | `crawlers/36kr.py` | 10 | 10 | RSS feed, ~10-30 items per fetch |
| ifeng | Phoenix/风声 | `crawlers/ifeng.py` | 100 | 100 | ishare API (account 7408), 10 pages of articles |
| xinhua | Xinhua (新华社) | `crawlers/xinhua.py` | 1,251 | 1,243 | JSON datasource feeds — tech + politics sections |

## Crawlers — Research

| Site Key | Name | Crawler | Docs | Bodies | Notes |
|----------|------|---------|------|--------|-------|
| tsinghua_aiig | Tsinghua AIIG | `crawlers/tsinghua_aiig.py` | 57 | 43 | AI governance think tank, 14 WeChat links (no body) |

## Not Yet Built / Geo-Blocked

| Source | Reachable? | Priority | Notes |
|--------|-----------|----------|-------|
| SAMR (www.samr.gov.cn) | Yes | **Built** | `crawlers/samr.py` — 6 sections, jpaas CMS |
| Xinhua (www.news.cn) | Yes | **Built** | `crawlers/xinhua.py` — 4 sections, JSON feeds |
| MOE (www.moe.gov.cn) | Yes | Medium | AI in education policies |
| PBoC (www.pbc.gov.cn) | Yes | Medium | Fintech/AI regulation |
| TC260 (www.tc260.org.cn) | Yes | Medium | AI cybersecurity standards (AJAX API) |
| CAICT (www.caict.ac.cn) | 412 from US | High | Critical AI think tank — needs droplet |
| SASAC (www.sasac.gov.cn) | Timeout | Medium-High | Central enterprise AI+ initiative — needs droplet |
| NPC law DB (flk.npc.gov.cn) | Yes (SPA) | Medium | AI Law draft when published |
| Chengdu (www.chengdu.gov.cn) | No (DNS) | Medium | Major AI city — geo-blocked |
| Anhui (www.ah.gov.cn) | No (WAF) | Medium | iFlytek hub — geo-blocked |
| Sichuan (www.sc.gov.cn) | Partial | Low-Medium | Site structure changed, needs re-research |
| Tianjin (www.tj.gov.cn) | No (403) | Low | Blocked from US |

## Backlog — Classification & Chain Improvements

| Task | Priority | Notes |
|------|----------|-------|
| Classify ~12,300 new docs | High | Droplet auto-classifies on next cron (~$6). Or set DEEPSEEK_API_KEY locally |
| Fix classification prompt | High | 3 biases: media=always low, explainers=overrated, district promo=overrated |
| Add `doc_type` field | Medium | policy / explainer / media_report / personnel / procurement |
| Add `references` extraction | Medium | LLM extracts policy names from media (regex misses informal refs) |
| Bidirectional citation chain | Medium | Currently outbound-only; inbound citations would enrich AI chain |
| Build eval set + iterate prompt | Medium | 25-item eval set built, test before re-classifying |

## Classification

| Item | Value |
|------|-------|
| Model | DeepSeek API |
| Classified | ~109,000 docs |
| Unclassified | ~16,000 (new crawlers: MOFCOM, SAMR, Xinhua, Chongqing, Wuhan, NDA, Tsinghua) |
| Cost | ~$0.50/1k docs |
| Concurrency | Keep at 2 (DeepSeek silently rate-limits with empty responses at higher) |
| Command | `python3 scripts/classify_documents.py --concurrency 2` |
