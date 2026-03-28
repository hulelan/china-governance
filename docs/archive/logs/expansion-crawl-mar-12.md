# Geographic Expansion Crawl — March 12, 2026

## Goal
Expand gkmlpt corpus from 23 sites to 37 sites by adding all remaining Guangdong cities and Shenzhen districts with working gkmlpt endpoints.

## Probe Results (Tier 1 — Guangdong gkmlpt)

### Working (14 new sites)
| Site Key | City | Base URL | SID |
|----------|------|----------|-----|
| zhongshan | Zhongshan | www.zs.gov.cn | 760001 |
| shantou | Shantou | www.shantou.gov.cn | 754001 |
| zhaoqing | Zhaoqing | www.zhaoqing.gov.cn | 758001 |
| shaoguan | Shaoguan | www.sg.gov.cn | 751001 |
| heyuan | Heyuan | www.heyuan.gov.cn | 762001 |
| shanwei | Shanwei | www.shanwei.gov.cn | 660001 |
| yangjiang | Yangjiang | www.yangjiang.gov.cn | 662001 |
| zhanjiang | Zhanjiang | www.zhanjiang.gov.cn | 759001 |
| chaozhou | Chaozhou | www.chaozhou.gov.cn | 768001 |
| jieyang | Jieyang | www.jieyang.gov.cn | 663001 |
| yunfu | Yunfu | www.yunfu.gov.cn | 766001 |
| szyantian | Yantian District (SZ) | www.yantian.gov.cn | 755042 |
| szlg | Longgang District (SZ) | www.lg.gov.cn | 755043 |
| szdp | Dapeng New District (SZ) | www.dpxq.gov.cn | 755038 |

### Failed (6 — not added)
| City | URL | Reason |
|------|-----|--------|
| Dongguan | www.dg.gov.cn | DNS resolution failed |
| Foshan | www.foshan.gov.cn | Connection refused |
| Meizhou | www.meizhou.gov.cn | HTTP 521 (Cloudflare), no SID |
| Maoming | www.maoming.gov.cn | Read timeout |
| Qingyuan | www.qingyuan.gov.cn | HTTP 404 |
| Bao'an (SZ) | www.baoan.gov.cn | DNS resolution failed |

## Probe Results (Tier 2 — Other Provinces)

**Result: 0 out of 28 provinces/municipalities have gkmlpt.**

gkmlpt is confirmed as a Guangdong-specific platform tied to `cloud.gd.gov.cn`. All 28 provincial/municipal sites tested (including Beijing, Shanghai, Zhejiang, Jiangsu, Sichuan, etc.) returned 404, 403, or redirect-to-homepage responses for `/gkmlpt/index`.

Expanding to other provinces requires writing custom crawler modules per province.

## Crawl Progress

### Phase 1: Sequential (Zhongshan only)
- Started: Mar 13 10:59 EDT
- Completed: Mar 13 ~22:30 EDT (~12 hours)
- Result: **2,347 docs, 2,344 bodies (100%)**

### Phase 2: 4-worker parallel (13 remaining sites)
- Started: Mar 13 23:05 EDT
- Result: **W3 succeeded, W1/W2/W4 crashed with `database is locked`**
- 4 concurrent SQLite writers exceeded busy_timeout (30s) — same issue as original 9-worker backfill
- W3 completed all 4 sites (heyuan, shanwei, jieyang, yunfu): **13,473 docs**
- W1/W2/W4 failed on 9 sites total (crashed immediately on first write collision)

| Site | Worker | Docs | Bodies | Status |
|------|--------|------|--------|--------|
| zhongshan | sequential | 2,347 | 2,344 | done |
| heyuan | W3 | 3,757 | 3,246 | done (86%) |
| shanwei | W3 | 3,186 | 3,184 | done (100%) |
| jieyang | W3 | 5,872 | 5,793 | done (99%) |
| yunfu | W3 | 658 | 549 | done (83%) |
| shantou | W1 | 0 | 0 | FAILED — retrying |
| zhanjiang | W1 | 0 | 0 | FAILED — retrying |
| chaozhou | W1 | 0 | 0 | FAILED — retrying |
| zhaoqing | W2 | 0 | 0 | FAILED — retrying |
| shaoguan | W2 | 0 | 0 | FAILED — retrying |
| yangjiang | W2 | 0 | 0 | FAILED — retrying |
| szyantian | W4 | 0 | 0 | FAILED — retrying |
| szlg | W4 | 0 | 0 | FAILED — retrying |
| szdp | W4 | 0 | 0 | FAILED — retrying |

### Phase 3: 2-worker retry (9 failed sites)
- Started: Mar 14 ~00:00 EDT
- Workers: A (shantou, zhanjiang, chaozhou, zhaoqing, szyantian) / B (shaoguan, yangjiang, szlg, szdp)
- Result: **5 succeeded, 4 still failed (db locked again on worker A)**
- Succeeded: shaoguan (1,607), yangjiang (2,355), szlg (3,893), szdp (8,587) + partially shantou retry
- Still failed: shantou, zhaoqing, zhanjiang, chaozhou, szyantian

### Phase 4: Sequential retry (5 remaining failed sites)
- Started: Mar 15
- Sites: shantou, zhaoqing, zhanjiang, chaozhou, szyantian
- Status: **running** (sequential = guaranteed no lock contention)

### Running totals
- **Expansion docs**: 32,262 (9/14 sites done)
- **Overall DB**: 103,421 docs, 94,135 bodies (91.0%)
- Crossed **100k docs** and **91% body text coverage**

## Pre-crawl Stats
- **Total docs**: 69,673
- **Body texts**: 62,064 (89.1%)
- **Sites configured**: 37 (23 existing + 14 new)
