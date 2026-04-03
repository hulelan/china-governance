# Project Status

*Last updated: 2026-04-03*

## Corpus Summary

| Metric | Value |
|--------|-------|
| Total documents | 135,419+ |
| With body text | 123,510 (91.2%) |
| Total sites | 61+ |
| Classified (v2 prompt) | ~24,000 (18%). Paused — restart when ready |
| Classified (v1 only) | ~109,000 (have title_en/summary_en but no doc_type/policy_significance) |
| Citations | 227,516 (14,265 LLM-sourced) |

## Production

| Component | State |
|-----------|-------|
| Website | Live at chinagovernance.com (Railway) |
| Database | PostgreSQL on Railway (synced 2026-04-01: 133,050 docs) |
| Local DB | SQLite `documents.db` (~1GB, source of truth) |
| Daily pipeline | Mac launchd at 7:00 AM: crawl → classify (if key set) → sync to Postgres |
| Telegram | Reports sent after each daily sync run |

## Droplet (Singapore, DigitalOcean) — Status Unknown

| Item | Value |
|------|-------|
| IP | 152.42.184.25 |
| Spec | 1 vCPU, 1GB RAM, 25GB disk |
| Status | **Assumed down.** Mac now runs all crawlers including droplet-only ones (miit/most/zhejiang/hangzhou) |
| Raw HTML | Disabled via `SKIP_RAW_HTML=1` to save disk |

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
| xinhua | Xinhua (新华社) | 1,504 | 1,496 | 99% | tech + politics. fortune/politics_read sections not yet crawled |
| people | People's Daily (人民日报) | 1,102 | 1,102 | 100% | 17 editorial sections from opinion.people.com.cn |
| ifeng | Phoenix/风声 | 180 | 180 | 100% | Added tech section |
| latepost | LatePost (晚点) | 94 | 94 | 100% | ~94 recent articles, no pagination |
| tsinghua_aiig | Tsinghua AIIG | 57 | 43 | 75% | 14 WeChat links (no body) |
| 36kr | 36Kr (36氪) | 10 | 10 | 100% | RSS feed, ~10-30 items per fetch |

## Daily Pipeline

Runs on Mac via launchd (`com.claude.china-governance-sync`) at 7:00 AM daily.

**Phase 1 — Crawl (all 28 crawlers):**
- Central: gov, ndrc, mof, mee, cac, nda, sic, samr, mofcom
- Provinces: beijing, shanghai, jiangsu, chongqing, wuhan, suzhou, heilongjiang
- Guangdong gkmlpt: 40+ sites via `--sync`, plus gd/huizhou/yangjiang individually
- Slow-from-US: miit, most, zhejiang, hangzhou (partial data, better than nothing)
- Research: tsinghua_aiig
- Shenzhen non-gkmlpt: sz_invest
- Media: 36kr, latepost, ifeng, xinhua, people

**Phase 2 — Classify** (skipped if `DEEPSEEK_API_KEY` not in `.env`):
- DeepSeek API, concurrency 2
- Adds title_en, summary_en, doc_type, policy_significance, references_json

**Phase 3 — Sync to Postgres:**
- `sqlite_to_postgres.py` pushes new docs (ON CONFLICT DO NOTHING)
- `backfill_bodies.py` fills body text for docs synced before bodies were fetched
- Verifies local vs Postgres counts match

**Reporting:** Telegram message with per-crawler results, doc counts, errors.

**30-min timeout** per crawler to prevent pipeline stalls.

## Recent Completions (2026-03-29 — 04-03)

- SIC crawler (1,117 docs from www.sic.gov.cn)
- NDA expanded to 5 sections (34 → 379 docs)
- ifeng tech section added (80 articles, total now 180)
- Incremental Postgres sync fix
- Classification v2 prompt: doc_type (10 types) + policy_significance + references_json. Eval: 94%/88%
- URL dedup: partial unique index on url, prevents cross-machine duplicates (also cleaned ~1,300 existing dupes)
- Automated pipeline: Mac launchd daily at 7 AM, Telegram reports, 30-min timeouts
- 14 new crawlers: ifeng fix, Zhejiang, NDA, Tsinghua AIIG, Chongqing, Wuhan, MOFCOM, SAMR, Xinhua, People's Daily, Suzhou, Hangzhou, Heilongjiang
- Daily manifests (CSV) for data loss detection, body text backfill script
- AI Chain expanded: 287 → 384+ docs (added 算力, 大模型, 生成式, 自动驾驶, 智能网联)
- Bidirectional citation chain (TDD: 8/8 tests green)
- LLM-extracted references integrated into citation extraction (227k total citations)
- Paragraph breaks fixed on document pages
- Mac hostname fix + timeout fallback for macOS

## Backlog — What To Do Next

### In Progress
| Task | Status | Notes |
|------|--------|-------|
| Re-classify all docs with v2 prompt | **Paused** (24k/135k done) | Add `DEEPSEEK_API_KEY` to `.env` to enable in daily pipeline |
| Daily pipeline | **Running** | Mac launchd at 7 AM. All 28 crawlers + Postgres sync |

### Website
| Task | Priority | Notes |
|------|----------|-------|
| Redesign: white bg, serif text, looser density | High | Branch `redesign/warm-serif` started. Move from dark terminal aesthetic to research publication style |
| Surface doc_type + policy_significance in browse/search | Medium | Replace old importance/category filters with new v2 fields |
| Show references_json on document pages | Medium | Clickable links to referenced policies |

### Data Quality
| Task | Priority | Notes |
|------|----------|-------|
| Translate high-significance docs to English | High | Full body translation for original_policy + policy_significance=high docs. DeepSeek or dedicated translation API |
| Update chain.py for bidirectional queries | Medium | Code tested (8/8 green), needs deployment to web service |
| Re-run extract_citations.py after classification finishes | Medium | More references_json = more LLM citations |
| SAMR full news sections | Low | ~15k more docs across xw_zj, xw_sj, xw_df, xw_mtjj |
| Xinhua fortune + politics_read | Low | ~1,250 more docs |

### Source Discovery (`scripts/discover_sources.py`)
| Task | Priority | Notes |
|------|----------|-------|
| Web search discovery | High | Use Baidu/Google for `site:gov.cn 人工智能 政策` to find domains we don't know about |
| Periodic discovery runs | Medium | Run discover_sources.py in daily pipeline to detect new AI content on known sites |

### Source Expansion

**Reachable from US, not yet built:**
| Site | Level | AI Hits | Priority | Notes |
|------|-------|---------|----------|-------|
| CAS (www.cas.cn) | Central | 2 | Medium | Chinese Academy of Sciences |
| SASAC (www.sasac.gov.cn) | Central | 1 | Medium-High | Now reachable (was timing out) |
| Jiangxi (www.jx.gov.cn) | Province | 2 | Low | |
| Shandong (www.shandong.gov.cn) | Province | 2 | Low | Empty stub in crawlers/ |
| Jinan (www.jinan.gov.cn) | Municipal | 2 | Low | Shandong capital |

**Reachable, not yet scanned for AI:**
MOE, PBoC, TC260, CSRC, NBS, Sichuan, Nanjing, Ningbo, Qingdao, Wuxi, Xi'an, Xiamen, Zhengzhou + others (33 total reachable)

**Unreachable from US (19 sites):**
Anhui, Chengdu, Hebei, Henan, Hubei, Gansu, Guangxi, Inner Mongolia, Tianjin, Xinjiang, Changsha, Hefei + others

**Discovery tool:** `python3 scripts/discover_sources.py --quick` (reachability) or without flag (deep scan with AI term search)

## Classification

| Item | Value |
|------|-------|
| Model | DeepSeek API |
| Classified (v1 prompt) | ~109,000 docs |
| Classified (v2 prompt) | 24k/133k done (paused) |
| Cost | ~$0.50/1k docs |
| Concurrency | Keep at 2 (DeepSeek silently rate-limits with empty responses at higher) |
| To enable | Add `DEEPSEEK_API_KEY=sk-...` to `.env` — daily pipeline will auto-classify |
