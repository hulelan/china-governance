# Project Status

*Last updated: 2026-03-28*

## Corpus Summary

| Metric | Value |
|--------|-------|
| Total documents | 114,230 |
| With body text | 104,318 (91.3%) |
| Total sites | 48 |
| Classified (English title/summary/category) | ~110,000 |

## Production

| Component | State |
|-----------|-------|
| Website | Live at chinagovernance.com (Railway) |
| Database | PostgreSQL on Railway (last synced 2026-03-27, 111,938 docs) |
| Local DB | SQLite `documents.db` (~1GB, source of truth) |
| Local → Production gap | ~2,300 docs (new crawlers not yet synced) |

## Droplet (Singapore, DigitalOcean)

| Item | Value |
|------|-------|
| IP | 152.42.184.25 |
| Spec | 1 vCPU, 1GB RAM, 25GB disk |
| Daily cron | 6 AM SGT: gkmlpt --sync, sz_invest |
| TODO | Add MIIT, MOST, 36kr, latepost to daily cron |

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

### Non-gkmlpt Shenzhen

| Site Key | Name | Crawler | Docs | Bodies |
|----------|------|---------|------|--------|
| sz_invest | Shenzhen Investment Portal | `crawlers/sz_invest.py` | 1,731 | 1,727 |

## Crawlers — Media

| Site Key | Name | Crawler | Docs | Bodies | Notes |
|----------|------|---------|------|--------|-------|
| latepost | LatePost (晚点) | `crawlers/latepost.py` | 85 | 85 | 163.com channel page, ~85 recent articles |
| 36kr | 36Kr (36氪) | `crawlers/36kr.py` | 10 | 10 | RSS feed, ~10-30 items per fetch |
| ifeng | Phoenix/风声 | `crawlers/ifeng.py` | 6 | 6 | Column ID needs fix (targets military, not 风声 policy commentary) |

## Not Yet Built / Geo-Blocked

| Source | Reachable from US? | Reachable from droplet? | Research done? | Notes |
|--------|-------------------|------------------------|----------------|-------|
| Zhejiang (www.zj.gov.cn) | No (WAF blocked) | Likely yes | Yes — JCMS API documented | Dept subdomains (fzggw, kjt) work from US |
| Anhui (www.ah.gov.cn) | No (QAX GeoBL) | Unknown | Yes — AJAX API documented | Custom CMS, POST /site/label/8888 |
| Hefei (www.hefei.gov.cn) | No (DNS fail) | Unknown | Partial | Same CMS as Anhui likely |
| NPC (www.npc.gov.cn) | No (timeout) | Unknown | No | — |
| SASAC (www.sasac.gov.cn) | No (timeout) | Unknown | No | — |
| DRC (www.drc.gov.cn) | Yes | Yes | Partial | GBK encoded, no crawler built |
| CAICT (www.caict.ac.cn) | 412 error | Unknown | No | Needs specific headers |
| Caixin (www.caixin.com) | Yes | Yes | No | Paywalled |
| Yicai (www.yicai.com) | Yes | Yes | No | — |

## Classification

| Item | Value |
|------|-------|
| Model | DeepSeek API |
| Classified | ~110,000 docs |
| Unclassified | ~4,000 (new crawls) |
| Cost | ~$0.50/1k docs |
| Concurrency | Keep at 2 (DeepSeek silently rate-limits with empty responses at higher) |
| Command | `python3 scripts/classify_documents.py --concurrency 2` |
