# Crawl Log — March 1, 2026

## Goal

Get body text for basically everything. Starting point: 46,636 docs, only 6,819 with body text (14.6%). Target: ~90%+.

## Context

Three code fixes were applied to `crawlers/gkmlpt.py` on Feb 28:
1. **Browser UA for Guangdong Province** — `gd.gov.cn` resets connections with default crawler UA
2. **Two fallback extraction patterns** — Nanshan `tyxxy_main` (126 docs) and gazette `news_cont_d_wrap` (27 docs)
3. **Better backfill logging** — every 20 docs with ETA, configurable `--backfill-delay`

## Session Timeline

### 17:00 — Previous session launched 9 parallel processes

Attempted to run 6 gkmlpt backfill processes + 3 central/provincial crawls simultaneously. **All failed within minutes due to SQLite `database is locked` errors.** SQLite WAL mode helps with concurrent reads but can't handle 9 concurrent writers with heavy I/O.

**Lesson learned:** SQLite is single-writer. Parallel-by-site only works with PostgreSQL or separate DB files. Must run backfill serially.

### ~17:20 — Serial backfill started (accidentally piped through `head -30`)

A serial `python3 -m crawlers.gkmlpt --backfill-bodies --policy-first --backfill-delay 0.3` was started but piped through `head -30`. Despite this, it ran for several minutes before being killed.

**Progress before kill:** 6,909 → 11,067 body texts (+4,158 docs in ~10 min)

### 17:30 — Diagnosed URL filtering issue

The backfill was processing ALL sites (including `ndrc`, `gov`, and docs with external WeChat/Xinhua/CCTV URLs). `extract_body_text()` only works on gkmlpt page HTML. Investigation found:

| URL Pattern | Count | Extractable? |
|-------------|-------|-------------|
| gkmlpt detail pages | 30,071 | Yes |
| WeChat articles | 1,512 | No |
| gov.cn (State Council) | 1,026 | No (different crawler) |
| ndrc.gov.cn | 501 | No (different crawler) |
| Other external (CCTV, Xinhua, etc.) | 2,459 | No |

**Fix applied:** Added URL filter `AND url LIKE '%gkmlpt%'` and site exclusion `AND site_key NOT IN ('ndrc', 'gov')` to `backfill_bodies()`. Also added a docstring documenting this.

### 17:34 — Restarted serial backfill with corrected filter

```bash
python3 -m crawlers.gkmlpt --backfill-bodies --policy-first --backfill-delay 0.3
```

Now targeting **30,071 gkmlpt docs** (was 35,569 with unextractable external URLs).

---

## Progress Checkpoints

| Time | Body text count | % coverage | Delta | Rate | Notes |
|------|----------------|------------|-------|------|-------|
| 17:00 | 6,819 | 14.6% | — | — | Start of session |
| 17:10 | 6,909 | 14.8% | +90 | — | Parallel processes crashed (SQLite locks) |
| 17:20 | 11,067 | 23.7% | +4,158 | ~7/s | Serial backfill before head killed it |
| 17:30 | 11,067 | 23.7% | — | — | Killed, fixed URL filter |
| 17:34 | 11,067 | 23.7% | — | — | Restarted with corrected filter (30,071 gkmlpt docs) |
| 17:39 | 11,152 | 23.9% | +85 | 0.5/s | Running, 53% extraction rate |
| 17:45 | 11,412 | 24.5% | +260 | 0.6/s | 82% extraction rate |
| 17:51 | 11,668 | 25.0% | +256 | 0.7/s | 88% extraction rate |
| 17:56 | 11,855 | 25.4% | +187 | 0.7/s | 90% extraction rate |
| 18:01 | 12,048 | 25.8% | +193 | 0.7/s | 91% rate, 1080/30071 processed |
| 18:07 | 12,280 | 26.3% | +232 | 0.7/s | 92% rate, 1320/30071 processed |
| 18:12 | 12,476 | 26.8% | +196 | 0.7/s | 1540/30071 (5.1%) |
| 18:17 | 12,672 | 27.2% | +196 | 0.7/s | 1740/30071 (5.8%) |
| 18:28 | 12,965 | 27.8% | +293 | 0.7/s | 2100/30071 (7.0%) |
| 18:38 | 13,296 | 28.5% | +331 | 0.6/s | 2480/30071 (8.2%) |
| 18:48 | 13,637 | 29.2% | +341 | 0.6/s | 2840/30071 (9.4%) |
| 21:31 | 18,314 | 39.3% | +4,677 | 0.6/s | 8120/30071 (27%) |
| 00:59 | 24,098 | 51.7% | +5,784 | 0.5/s | **Crashed** at 14300/30071 (48%): `UnicodeEncodeError` (surrogate chars). Fixed + restarted. 16,937 remaining. |
| 06:53 | 30,928 | 66.3% | +6,830 | 0.4/s | 8580/17040 (50%) of restart batch. Some DNS/timeout errors on fgw. |
| 12:50 | 39,007 | 83.6% | +8,079 | — | **DONE.** gkmlpt backfill complete: 14,909/17,040 (87.5%) extracted in restart batch. |

---

## Per-Site Status

| Site | Missing | Notes |
|------|---------|-------|
| mzj (Civil Affairs) | 3,313 | gkmlpt — will backfill |
| ga (Public Security) | 3,245 | gkmlpt — will backfill |
| hrss (HR & Social Security) | 3,010 | gkmlpt — will backfill |
| swj (Commerce) | 2,845 | gkmlpt — will backfill |
| jtys (Transport) | 2,792 | gkmlpt — will backfill |
| stic (S&T Innovation) | 2,539 | gkmlpt — will backfill |
| fgw (Dev & Reform) | 2,338 | gkmlpt — will backfill |
| zjj (Housing) | 2,098 | gkmlpt — will backfill |
| yjgl (Emergency Mgmt) | 1,918 | gkmlpt — will backfill |
| szeb (Education) | 1,893 | gkmlpt — will backfill |
| szlhq (Longhua District) | 1,842 | gkmlpt — will backfill |
| sf (Justice) | 1,724 | gkmlpt — will backfill |
| szpsq (Pingshan District) | 1,423 | gkmlpt — will backfill |
| wjw (Health Commission) | 1,141 | gkmlpt — will backfill |
| gov (State Council) | 985 | Separate crawler needed |
| szgm (Guangming District) | 519 | gkmlpt — will backfill |
| ndrc | 500 | Separate crawler needed |
| audit | 468 | gkmlpt — will backfill |
| szlh (Luohu District) | 391 | gkmlpt — will backfill |
| sz (Municipal) | 208 | gkmlpt — will backfill |
| szns (Nanshan District) | 202 | gkmlpt — will backfill |
| szft (Futian District) | 175 | Mixed — some gkmlpt, some external |

---

## Pending After gkmlpt Backfill

1. **NDRC body text** — `python3 -m crawlers.ndrc` (500 docs, needs to run alone)
2. **State Council body text** — `python3 -m crawlers.gov` (1,005 docs, needs to run alone)
3. **Guangdong Province** — `python3 -m crawlers.gkmlpt --site gd` (never crawled, needs browser UA)
4. **Citation re-extraction** — `python3 scripts/extract_citations.py --force`

## Technical Notes

- **SQLite concurrency:** WAL mode allows concurrent reads but only one writer at a time. `busy_timeout=30000` (30s) isn't enough when 9 processes compete. Need PostgreSQL for true parallelism.
- **gkmlpt URL pattern:** All gkmlpt detail pages have `/gkmlpt/content/{cat}/{subcat}/post_{id}.html` in URL
- **External URLs:** ~5,500 docs have external URLs (WeChat, Xinhua, CCTV, People's Daily, etc.) — these will never have body text extracted and represent the ~10% gap in our target
- **Backfill is resumable:** Re-running the command picks up where it left off (queries for `body_text_cn = ''`)
