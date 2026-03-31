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

## Recent Completions (2026-03-29/30)

- Classification v2 prompt: doc_type (10 types) + policy_significance + references_json. Eval: 94%/88%
- URL dedup: partial unique index on url, prevents cross-machine duplicates
- Automated pipeline: both Mac + droplet push to Postgres independently, git auto-pull, 30-min timeouts
- 11 new crawlers: ifeng fix, Zhejiang, NDA, Tsinghua AIIG, Chongqing, Wuhan, MOFCOM, SAMR, Xinhua
- Daily manifests (9MB CSV) for data loss detection, body text backfill script
- AI Chain expanded: 287 → 384+ docs (added 算力, 大模型, 生成式, 自动驾驶, 智能网联)
- Paragraph breaks fixed on document pages

## Backlog — What To Do Next

### In Progress
| Task | Status | Notes |
|------|--------|-------|
| Re-classify all 125k docs with v2 prompt | Running on local Mac | ~$55, ~5 days at concurrency 2. New fields: doc_type, policy_significance, references_json |
| Verify droplet cron | Waiting for next run (6 AM UTC) | First run with new code: git pull, timeouts, 7 new crawlers, auto-sync |

### Website
| Task | Priority | Notes |
|------|----------|-------|
| Redesign: white bg, serif text, looser density | High | Move from dark terminal aesthetic to research publication style |
| Surface doc_type + policy_significance in browse/search | Medium | Replace old importance/category filters with new v2 fields |
| Show references_json on document pages | Medium | Clickable links to referenced policies |

### Data Quality
| Task | Priority | Notes |
|------|----------|-------|
| ~~Bidirectional citation chain~~ | **Done** | Tests prove inbound+outbound pattern works. chain.py web service needs update |
| ~~Use references_json to supplement regex citations~~ | **Done** | extract_citations.py now processes references_json as citation_type='llm'. TDD: 8/8 green |
| Update chain.py for bidirectional queries | Medium | Apply the tested inbound pattern to the web service |
| Re-run extract_citations.py after v2 classification | Medium | Will create thousands of new LLM-sourced citations once references_json is populated |
| SAMR full news sections | Low | ~15k more docs across xw_zj, xw_sj, xw_df, xw_mtjj. Run on droplet |
| Xinhua fortune + politics_read | Low | ~1,250 more docs. Run on droplet |

### Source Expansion — Reachable
| Task | Priority | Notes |
|------|----------|-------|
| MOE (www.moe.gov.cn) | Medium | AI in education policies |
| PBoC (www.pbc.gov.cn) | Medium | Fintech/AI regulation |
| TC260 (www.tc260.org.cn) | Medium | AI cybersecurity standards (AJAX API) |
| CSRC (www.csrc.gov.cn) | Low | Capital market fintech pilots |

### Source Expansion — Needs Droplet/China IP
| Task | Priority | Notes |
|------|----------|-------|
| CAICT (www.caict.ac.cn) | High | Critical AI think tank, annual governance blue paper. 412 from US |
| SASAC (www.sasac.gov.cn) | Medium-High | Central enterprise AI+ initiative. Timeout from US |
| Chengdu (www.chengdu.gov.cn) | Medium | Major AI city, 100M yuan annual computing vouchers. DNS timeout |
| Anhui (www.ah.gov.cn) | Medium | iFlytek hub, 1,078+ AI enterprises. WAF blocked |
| NPC law DB (flk.npc.gov.cn) | Medium | AI Law draft when published. SPA needs API reverse-engineering |

## Classification

| Item | Value |
|------|-------|
| Model | DeepSeek API |
| Classified (v1 prompt) | ~109,000 docs |
| Classified (v2 prompt) | Re-classifying all 125k (in progress) |
| Cost | ~$0.50/1k docs |
| Concurrency | Keep at 2 (DeepSeek silently rate-limits with empty responses at higher) |
| Command | `python3 scripts/classify_documents.py --concurrency 2` |
