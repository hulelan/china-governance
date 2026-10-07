# A6 — the recoverable head of the citation-crawl queue (2026-10-07)

**Question.** Citation resolution is coverage-bound (~51%); the only lever is ingesting
cited-but-missing instruments. `citation-crawl-queue.csv` ranks ~125k missing documents by
inbound demand but is noisy. Which part of its HEAD can actually be fetched from the NYC
droplet, from where, and with which existing crawler? (corpus-lessons A6 prep; read-only —
no DB writes, no crawler runs, 137 bounded HTTP probes at 1 req/s, every body byte-counted.)

**Companion table:** `a6-recoverable-head.csv` — one row per INSTRUMENT (234 rows covering all
400 queue rows), with `demand` = distinct citing docs (union across merged rows), `edges` =
unresolved citation rows, `status`, `candidate_url`, `reachable`, `bytes`, `fetcher`.

## Method

1. Rebuilt the queue read-only on the live DB (`build_citation_crawl_queue.py --db … --out /tmp`):
   264,511 unresolved edges → 151,687 actionable targets. Took the top 400 rows
   (18,951 row-demand; **15,814 distinct citers / 20,635 edges** after merging editions).
2. De-noised: re-ran the resolver's exact/core tiers (`TitleMatcher.resolve_exact` + the 文号
   chain, same tables as `extract_all`) on every row against CURRENT titles → **1/400 now
   resolves** (食品经营许可和备案管理办法). The nightly resolver has already taken the fixable
   matches; the head is genuinely absent. Pulled ±70-char body context for all 47 文号-only
   rows to name the instrument (e.g. 粤自然资发〔2021〕3号 = 省自然资源厅 关于加强和改进控制性详细
   规划管理若干指导意见). Grouped the 400 rows into **234 instruments**, edition-aware
   (惠府令第39/67/86号 are three editions of one family; 征地补偿保护标准 2006/2011/2016 kept apart).
3. Located URLs with the dialects we already have: gov.cn `search-gov/data` (`t=zhengcelibrary_zy
   | gw | bm`, `searchfield=title`), `search.gd.gov.cn/jsonp/site/<SID>` (gkmlpt `--search`
   path; SIDs gd=2, zhongshan=760001, sz=755001, gdnr=153, dpxq=755038), flk `law-search`.
   Reachability = status + byte count + a sample content-page GET per source kind.

## Headline: 29% confirmed, ~43% likely, 16% is the 部门规章 wall

| status | citers | share | instruments | meaning |
|---|---:|---:|---:|---|
| **located** | 4,186 | 26.5% | 49 | exact URL found this run; host byte-checked (29–170 KB pages) |
| **alias-fix** | 423 | 2.7% | 3 | ALREADY IN CORPUS (npc) — resolver name-variant miss, zero crawl |
| source-verified | 2,248 | 14.2% | 62 | not individually probed; same archive as the located siblings |
| probed-miss | 2,149 | 13.6% | 23 | host reachable, searched, instrument NOT found (likely never web-published / pre-migration) |
| **bm-miss** | 2,596 | 16.4% | 58 | central **部门规章** (公安部令/人社部令/住建部令…) — not in gov.cn's 部门文件 library; issuing ministries mostly blocked from NYC |
| nondoc | 1,645 | 10.4% | 8 | permit names, GB standards, treaties, serial 公告, forms — queue noise |
| gap | 1,336 | 8.4% | 18 | origin site is crawled; doc sits in an uncrawled section (bj 规自委, js 失效库, xz_sti, nx_jst, chinatax backlog…) |
| blocked | 539 | 3.4% | 2 | huizhou / yangjiang hosts blackholed (0 bytes) — HK/residential only |
| nonpublic | 416 | 2.6% | 8 | 机构改革方案 / 中发〔2015〕9号 / 深改委 方案 — never published |
| delisted | 251 | 1.6% | 2 | 苏住建规〔2011〕4号 family (CLAUDE.md finding stands); 治安管理处罚条例 (law renamed) |

- **Confirmed recoverable from NYC: 4,609 citers (29.1%), 5,736 edges.**
- **Likely recoverable (adding unprobed siblings of confirmed archives): 6,857 citers (43.4%), 8,211 edges.**
- **Not reachable from NYC (blocked + delisted + nonpublic): 1,206 citers (7.6%).** The single
  largest item is 惠州市加强建设项目征地拆迁管理规定 — **513 distinct citers** across 3 editions, all
  from `huizhou` (its own 征地 公告 corpus) — HK/residential vantage only.
- **Queue noise (nondoc): 10.4%.** `is_actionable()` should additionally drop permit names
  (…许可证/意见书/合格证), GB codes, 条约, and MIIT serial 公告 batches.

### Two CLAUDE.md "delisted" verdicts are wrong
深圳市行政听证办法 (2006) and 深圳市财政局政府采购供应商信用信息管理办法 (深财规〔2023〕3号) are both in
the **Shenzhen 政府公报 archive** `sz.gov.cn/zfgb/<year>/gb<issue>/content/post_<id>.html`
(1989–2026). The corpus holds only **35** `/zfgb/` URLs because gkmlpt is a different section.
Byte-checked: 行政听证办法 = 66,443 B with body. 10 of 11 probed Shenzhen instruments live there.
(The 苏住建规 delisting finding stands.)

### Per-source breakdown (citers located / all in that kind)

| source kind | located | all | what it is | existing fetcher |
|---|---:|---:|---|---|
| gov.cn **中央文件** `zhengcelibrary_zy` | 1,479 | 2,577 | 566-doc library of 中共中央/中办国办 docs. **Not crawled**: `gov.py LIBRARY_CATEGORIES` has only gw+bm; corpus holds 498 `/zhengce/<date>/` pages. 21/24 probed instruments found by exact title. | `gov.py --library` after adding `"zy": "zhengcelibrary_zy"` (same JSON shape, same `_extract_*`) |
| sz.gov.cn **政府公报** `/zfgb/` | 980 | 1,583 | 1989–2026 gazette; holds the "delisted" Shenzhen 规章/规范性文件. HTTPS fails from Python urllib (`SSL BAD_ECPOINT`) — use http as `gkmlpt sz` already does. | new section walker (issue index → content pages); or `gkmlpt --site sz --search <kw>` which indexes it |
| gd.gov.cn **省政府公报** `/zwgk/gongbao/` + gdnr | 572 | 1,870 | 粤自然资发〔2021〕3号 (240 citers) is on nr.gd.gov.cn (crawled site, missed doc); 粤司规〔2019〕3号 in 公报 2020/1 (170 KB). Corpus holds **1** gongbao URL. | `gkmlpt --site gdnr --search 控制性详细规划`; gd 公报 = new section |
| zs.gov.cn **dept sub-sites** `/zslyj/gkmlpt` | 554 | 1,305 | 中山 自然资源局 has its own gkmlpt under `/zslyj/` (also `/zsdfz/`, `/zshpz/` …). Corpus holds **2** zslyj URLs vs 5,152 zhongshan gkmlpt. 2023版 标准与准则 (257) + 控规实施细则 (225) + 城市设计指引 (72) are there. | `gkmlpt` with `base_url=http://www.zs.gov.cn/zslyj` (discover_site on the sub-path) |
| gov.cn 国务院公文 `gw` | 361 | 714 | 2000s 国发/国令 docs are present (2008-03-28 dump pages); 1997/1998 absent. 7/10 probed found, none held → the `--deep` walk never completed. | `gov.py --library gw --deep` (pcode fills 文号 before body fetch) |
| gov.cn 部门文件 `bm` | 240 | 3,077 | title-search found the instrument itself in **2/37** — 部门规章 and pre-2008 ministry docs are not in this library (and `t=gongbao` title search returned 0). | — (HK vantage / 北大法宝 project) |
| dpxq.gov.cn `/ztzl/gfxwjk/` | 129 | 129 | 大鹏新区 规范性文件库 (0 held); SID 755038. | small new section |
| flk / npc | 423 alias | 588 | 广东省控制性详细规划管理条例 (340!) is held as **广东省城市控制性详细规划管理条例**; 广东省实施《土地管理法》办法 held, cited with `&lt;…&gt;`; 广东省公路条例 held ×4 yet unresolved. | resolver fixes, no crawl |

## Bounded fetch plan (writer agent, after the nightly; ~1–2 h total, all NYC-reachable)

1. **gov.cn 中央文件** — add `"zy": "zhengcelibrary_zy"` to `crawlers/gov.py LIBRARY_CATEGORIES`;
   run `python3 -m crawlers.gov --library --categories zy --deep`. Expect **≤566 docs**, resolving
   ~**1,700 edges / 1,480 citers** confirmed (2,980 edges if the unprobed zy groups are there too).
   Rebuild citations (`extract_citations.py`) and run `validate_cascades.py` after.
2. **gov.cn 国务院公文 deep re-walk** — `python3 -m crawlers.gov --library --categories gw --deep
   --list-only` first (pcode resolves 文号 cites with no body fetch), then bodies for new ids.
   Expect a few hundred new 2000s docs; **~400 edges** from the head alone.
3. **Shenzhen 政府公报** — walk `http://www.sz.gov.cn/zfgb/<year>/` issue indexes (1989–2026) with
   the gkmlpt `sz` extractors (same CMS, `post_<id>.html`); http only. Expect **several thousand**
   docs; head alone = **~1,470 edges / 980 citers**; the broader pool is the 14,932 distinct
   Shenzhen-family citers with unresolved edges.
4. **Zhongshan dept gkmlpt** — register `zs_lyj` (`http://www.zs.gov.cn/zslyj`) in `gkmlpt.SITES`
   (dept level) and crawl; also `--search` for the 2023版 标准与准则 / 控规实施细则. Expect
   ~6k docs (mostly 征地/控规 公告), **~610 edges** from the head.
5. **Guangdong**: `python3 -m crawlers.gkmlpt --site gdnr --search 控制性详细规划` (240 citers in one
   doc); then a `gd.gov.cn/zwgk/gongbao/` issue walker (省政府公报, ~1 URL held) and `dpxq
   /ztzl/gfxwjk/` (129 citers). **Zero-crawl resolver fixes** in the same pass: alias
   广东省控制性详细规划管理条例→广东省城市控制性详细规划管理条例 (340 citers), HTML-entity unescape of
   refs (`&lt;&gt;`→〈〉, 42), and inspect why 广东省公路条例 (held ×4) stays unresolved (41).

Expected total from steps 1–5: **~5,700 edges confirmed (up to ~8,200)** against a 264k
unresolved pool, i.e. +2–3 points of resolution from the head alone — and, more importantly,
four whole archives (中央文件, 深圳公报, 广东公报, 中山 dept gkmlpt) whose long tails are not in
the top-400 at all.

## What is NOT recoverable from NYC (do not blind-crawl)

- **部门规章 wall (16.4%)** — 公务员录用体检通用标准 (192+97+36), 事业单位公开招聘违纪违规行为处理规定
  (157), 机动车登记规定 (5 article refs, ~230), 律师事务所年度检查考核办法 (155), 人防工程监理资质办法 (85)…
  The issuing ministries (人社部, 公安部, 住建部, 民政部, 卫健委, 国土/自然资源部) are blackholed or
  WAF-blocked from the droplet and gov.cn's library does not carry their 规章. This is the
  HK-VPS / 北大法宝 bucket (`hk-vps-runbook.md`).
- **Blocked hosts (3.4%)** — huizhou (513), yangjiang (26).
- **Never published (2.6%)** — 2009 机构改革方案 (省/市委 文件), 中发〔2015〕9号, 京津冀纲要, 深改委 方案.
- **Probed-miss (13.6%)** — mostly pre-2018 国土资源厅 docs (征地补偿保护标准 2006/2011/2016, 410
  citers) that did not survive the nr.gd.gov.cn migration, and 2013-era 中山 府办 通知 / 总体规划
  texts that were never posted. Candidates for the same offline-source project.

## Probe ledger
137 HTTP requests from `104.236.88.45` (cap 150), 1 req/s: 4 dialect tests + 1 flk + 6 SID
pages + 2 full-param tests + 115 instrument probes + 8 follow-ups (byte-checks, `t=gongbao` test,
3 full-text GD searches). Scripts (scratch, not committed): `a6_denoise.py` (resolver re-run,
`?mode=ro`), `a6_ctx.py` (文号 context), `a6_instruments.py` (grouping), `a6_probe.py`,
`a6_build.py`. No DB writes, no crawler runs, CLAUDE.md / daily_sync.sh / crawlers untouched.
