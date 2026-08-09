# Coverage tracker — national coverage of Chinese government websites

**THE registry.** Single source of truth for what we crawl, what's buildable, and
what's BLOCKED. Goal: full coverage of CN gov sites (34 province-level jurisdictions,
their departments, and cities). Regenerate the reachability/CMS columns anytime with
`scripts/rnd/discovery/coverage_probe.py` (probes each portal from the droplet).

**Status keys:**
- ✅ `CRAWLED` — we have a working crawler + docs
- 🟢 `BUILDABLE` — reachable from the droplet + CMS known → build now
- 🟡 `ANTI-BOT` — reachable but 403/412/406 → needs browser-shaped headers/cookies
- 🔴 `BLOCKED` — IP-blocked from the droplet (000/timeout) → needs a China/residential vantage point
- ❔ `UNKNOWN-CMS` — reachable but CMS not yet characterized

**CMS platforms seen:**
- `gkmlpt` (公开目录平台) — Guangdong ecosystem. Auto-discovers (SID + tree). FREE batch via `crawlers/gkmlpt.py` (add a SITES entry).
- `jpaas` (jpage `dataproxy.jsp`) — Jiangsu, Shandong… Needs multi-site config (webid discoverable, unitid TODO). One crawler → many provinces.
- `col/` — column-based (Yunnan, Beijing 人社局). Characterize per-site.
- static year-archives — Shanghai. Per-portal.

---

## 1. Provincial portals (31 mainland province-level)

> Populated by `coverage_probe.py` (2026-07-15). `http` = status from droplet.

**Survey 2026-07-15 (31 mainland province-level). Tally: 7 CRAWLED · 2 BUILDABLE(CMS
known) · 8 UNKNOWN-CMS(reachable) · 5 ANTI-BOT · 9 BLOCKED.**

| Status | Jurisdictions |
|---|---|
| ✅ CRAWLED (7) | 广东, 北京, 上海, 江苏, 浙江, 黑龙江, 重庆 |
| 🟢 BUILDABLE (2) | **山东 (jpaas → crawlers.jpaas)**, 云南 (col/) |
| ❔ UNKNOWN-CMS, reachable (8) | 天津, 辽宁, 吉林, 福建, 湖南, 西藏, 宁夏, 新疆 |
| 🟡 ANTI-BOT 403/412 (5) | 内蒙古(403), 安徽(403), 河南(403), 湖北(412), 甘肃(412) |
| 🔴 BLOCKED 000 (9) | 河北, 山西, 江西, 广西, 海南, 四川, 贵州, 陕西, 青海 |

So **~10 provinces are buildable from the droplet now** (2 known-CMS + 8 to characterize),
5 might yield to browser headers, and **9 hard-blocked need a China vantage point.**

**jpaas SOLVED (2026-07-15):** `crawlers/jpaas.py` — generic multi-site jpaas crawler
that AUTO-DISCOVERS unitid/webid/columns from any jpaas site's column pages (validated:
js_czt → 45 docs). Covers Jiangsu departments + Shandong + any jpaas province. Add a
`SITES` entry. TODO: discovery currently finds top-nav policy columns (政策解读); deepen
to reach 规范性文件 sub-columns for full doc coverage.

## 2. Provincial departments

- **Guangdong — 20 CRAWLED (gkmlpt, 2026-07-15):** 自然资源厅/人社厅/住建厅/教育厅/科技厅/
  工信厅/公安厅/民政厅/财政厅/生态环境厅/交通运输厅/农业农村厅/商务厅/文旅厅/卫健委/
  应急管理厅/林业局/医保局/发改委/统计局 (`gdnr`, `gdedu`, … in `SITES`).
  TODO: 水利厅/市场监管局/司法厅/审计厅 (correct domains).
- **Jiangsu depts — BUILDABLE (jpaas):** need multi-site refactor of `jiangsu.py` (solve
  unitid). 财政厅/发改委/工信厅/交通厅 reachable + jpaas confirmed.
- **Beijing depts — UNKNOWN-CMS:** 人社局 = col/; others no clear marker. Characterize.
- Other provinces' departments: pending each province's portal build.

## 3. Municipalities & cities (already crawled)

- Guangdong cities (gkmlpt): 广州/深圳(+districts/depts)/珠海/惠州/江门/中山/汕头/汕尾/
  韶关/河源/阳江/湛江/肇庆/揭阳/云浮/东莞/佛山 (many; some KNOWN_BROKEN).
- Other: 苏州(Suzhou)/武汉(Wuhan)/杭州(Hangzhou).
- **深圳 (Shenzhen)** — main portal + 9 districts + 13 departments + investment portal.

## 4. Central (CRAWLED)

State Council (+ `--library` for the full document DB), NDRC, MOF, MEE, CAC, NDA, SIC,
SAMR, MOFCOM, MIIT, MOST, MOE, NPC(metadata-only), IPC court. Media: Xinhua, People's
Daily, Phoenix, etc.

## 5. 🔴 BLOCKED registry (needs a China / residential vantage point)

The critical list. These are unreachable from the droplet's NYC datacenter IP:
- **Provinces (000/hard-block):** 四川, 河北, + (survey) 安徽, 江西, 陕西, 甘肃, 贵州,
  山西, 内蒙古, 广西, 海南, 青海 — confirm/refine via probe.
- **Anti-bot (403/412 — maybe fixable with headers):** 河南, 湖北.
- **GD cities:** 惠州, 阳江 (datacenter-IP blocked; we hold older docs from residential crawls).
- **NPC full statutory text** — China-IP gated (metadata worldwide).
- **DECISION:** a China vantage point unblocks the hard-blocked majority in ONE move.
  This is the gating factor for NATIONAL coverage — not crawler code.

### Track 2 — China vantage point: options evaluation (2026-07-16)

**Constraint:** DigitalOcean has NO mainland-China region (nearest is Singapore),
so we can't just spin up a "China droplet." The gov sites block by IP
(datacenter/foreign), so we need requests to *originate* from a China-friendly IP.
Ranked by practicality for our use case (OUTBOUND crawling, low bandwidth — text):

1. **DO Singapore droplet — cheapest test, DO IT FIRST (~$6/mo).** We already use DO;
   spin up an SGP1 droplet and re-run `coverage_probe.py`. Singapore has better routing
   to China than NYC and *may* be less throttled — but it's still a datacenter IP, so
   it might not bypass the geo-block. ~1h to test, near-zero commitment. Could partially
   help (better latency even where not blocked → also eases the timeout problem).
2. **China residential proxy (Bright Data / Oxylabs / Smartproxy) — most likely to WORK.**
   Real China *residential* IPs bypass both the datacenter-IP block AND the geo-block.
   No ICP/account hassle. Pay per GB — and our crawls are text (low bandwidth), so cost
   is modest (est. $5-15/GB; a full provincial crawl is maybe hundreds of MB). Architecture:
   route only the BLOCKED-site requests through the proxy (a per-site proxy setting in
   `base.fetch`) — small code change, main pipeline stays on the droplet. **Recommended
   for the blocked set + NPC full-text.**
3. **Mainland China VPS (Alibaba/Tencent/Huawei Cloud) — cheapest + fastest IF we can sign up.**
   ~$5-15/mo, sub-second to gov sites. Outbound crawling does NOT need ICP filing (ICP is
   for HOSTING a public site). Barrier: account creation needs China real-name (phone/ID/
   payment). Run the crawler there, sync the DB back (rsync) or write to a shared DB.
   - **Hong Kong region** (Alibaba/Tencent HK): international-friendly signup, no ICP —
     BUT HK is often treated as FOREIGN by mainland gov sites, so it may NOT bypass the
     block. Cheap to test if we go this route.
4. **China-based collaborator** runs the crawler from a residential connection, ships the
   rows. Free, real residential IP, but manual/not automated (like the officials.db seed).

**Recommendation:** (a) test the DO Singapore droplet first (cheap, informative, also
helps timeouts), then (b) if still blocked, stand up a China residential proxy scoped to
the blocked-site list — smallest architecture change, no account barrier, pay-as-you-go.
Avoid the mainland-VPS account hassle unless we want the full-speed option long-term.

## 6. Build queue (reachable, do now)
1. **jpaas multi-site crawler** — unblocks Jiangsu depts + Shandong (+ likely more). Highest multiplier.
2. **Reachable unknown-CMS provinces** — characterize + build: 湖南/福建/辽宁/吉林/天津/云南(col)/新疆/宁夏/西藏.
3. **GD leftover depts** — 水利厅/市场监管局/司法厅/审计厅 (find domains).
4. **Anti-bot retry** — 河南/湖北 with browser headers+cookies.

## 7. Central-apparatus build-out (2026-07-21)

Probed all 46 reachable-uncrawled entities in `coverage.csv` by CMS. Reachability
was never the blocker — all return HTTP 200 — but the central bodies are
deliberately **heterogeneous** (no single discovery unlocks them like gkmlpt does
Guangdong / jpaas does Jiangsu). CMS split: ~27 custom, ~11 col-based, ~8 TRS/WCM.

**Built this round:**
- `crawlers/trs.py` (generic TRS "recordset" dialect: list embedded in
  `/col/colN/index.html`, encrypted-param `<nextgroup>` pagination) →
  **医保局 nhsa (150)**, **广电总局 nrta (45)**. The ~9 col-based sites (全国政协,
  济南, 郑州, 无锡, 沈阳, 福州, 银川, 云南) are reachable via this crawler but each
  needs a small per-site fix (CPPCC = cert hostname mismatch [now handled by
  base.py's TLS ctx, but returns transient 502]; 济南 = slow multi-column discover).
- `crawlers/spp.py` — 最高检 法律法规库, static `.shtml`, date-in-URL, body in
  `<div id="fontzoom">`. **40 docs** (Constitution, major laws, 2026 judicial
  interpretations), all with body. Live + nightly.
- `crawlers/csrc.py` — 证监会 政策法规库, per-article extraction from the zcfgk hub
  (~150 links). **CSRC throttles bursts** (serves the 208 KB index after a fast
  run); crawler uses browser UA + 2 s delay and safe-skips throttled responses.
  Initial backfill deferred to the nightly (fresh IP, few new docs/day stays under
  the throttle). Live + nightly.

**Remaining high-value bespoke (harder — API/JS reverse-engineering each):**
- **税务总局 chinatax** — the 法规库 (`fgk.chinatax.gov.cn`) is a **search-API DB**;
  list loads via `search5/html/searchResult.html?searchWord=…` (JSON endpoint).
  TODO: find + call the search JSON API, page through results.
- **央行 PBOC** — hardest. Node-path structure (`/tiaofasi/NNN/index.html`); the
  document list is **not adjacent to anchors in the static HTML** (likely a
  companion data file or unusual markup). TODO: capture the real list source
  (network trace) before writing a parser.

### Update — all 4 high-value bespoke bodies built (2026-07-21)

- **最高检 SPP** (`crawlers/spp.py`): 40 docs. ✓
- **证监会 CSRC** (`crawlers/csrc.py`): 143 docs. ✓
- **央行 PBOC** (`crawlers/pbc.py`): 27 docs (条法司 规范性文件 + 部门规章; date from
  URL node-id, body in `<div id="zoom">`). ✓
- **税务总局 chinatax** (`crawlers/chinatax.py`): 3-layer defense decoded (C3VK
  cookie + layui + `getFileListByCodeId` JSON API keyed by UUID channelId). ~9,900
  docs across 8 listflfg categories; **initial backfill runs in the background**
  (bodies via C3VK, ~hours). If it dies, resume with `python -m crawlers.chinatax
  --full` (pages every category fully + skip-held dedup — a plain restart would
  early-exit at the newest held docs). Nightly runs incremental (early-exit). ✓

All wired into daily_sync.sh Phase 1 (sequential — no writer contention) + CLAUDE.md.

---

## 8. Generic gov "t-date" crawler + fleet perf fixes (2026-07-23)

**`crawlers/govcms.py` — NEW generic crawler** for the central-ministry "t-date
list" dialect (`/SECTION/YYYYMM/tYYYYMMDD_ID.html`, server-rendered list pages).
The central-cluster analog of gkmlpt: add a site via `SITES` config, `--discover`
maps its sub-sections, and a general "innermost `<div>` with the most `<p>`-text"
body extractor handles per-template container variation (TRS_Editor / TRS_UEDITOR /
xxgk / #UCAP-CONTENT). Reuses `gov._extract_metadata_table`.

**5 central bodies live (wired into nightly + coverage):**
- 水利部 MWR (`/zw/zcfg/{fl,bmgz,gfxwj}/`) — 56 docs, 95% body
- 农业部 MARA (`/gk/zcfg/`) — 25 docs, 100% body
- 文旅部 MCT (`/whzx/ggtz/`) — 20 docs (公告通知, short)
- 统计局 NBS (`/xw/tjxw/tzgg/`, `/sj/zxfb/`) — 18 docs, 89% (misses = cross-domain)
- 退役军人部 MVA (`/gongkai/zfxxgkpt/zhengce/gfxwj/`) — 15 docs, 100% body

**Central bodies still to add** (JS-nav / different scheme — need section discovery
via article-URL derivation): MOT, MOHRSS, CNIPA, GAS, MEM, NIA, CPPCC, 中央政法委,
12371. One-offs (not t-date): NEA (hash-urls), NFGA (.jhtml), NFRA (SPA).

**Fleet perf/correctness fixes (the daily-run killers):**
- **Partial-index dedup fix, fleet-wide (41 queries / 31 crawlers).** Every
  incremental crawler's `WHERE url = ?` pre-check omitted `AND url != ''`, so it
  full-scanned the 224k-row table (SQLite won't use the partial `idx_documents_url`
  without the predicate). Proven `SCAN → SEARCH USING INDEX`. This was the dominant
  cost behind the ~8.7h daily run + 1800s crawler timeouts. Fixed (cd5c586, 40b82f3).
- **gkmlpt IntegrityError fix (785ef2d).** A same-URL-under-new-id collision threw an
  uncaught `IntegrityError` that aborted the whole 40-site sweep (→ 0 docs nightly).
  Now caught + skipped.
- **chinatax --full backfill** completing (2,567 → ~9,900) after the dedup fix
  un-stalled it.

## 9. Remaining-target CMS survey (2026-07-24) — "are there more Jinan-like cases?"

Fingerprinted + article-URL-derived every remaining reachable-uncrawled target.
**Yes — client-rendered (browser-needed) cases are common.** Three tiers:

**A. Static ARTICLE urls, but CLIENT-RENDERED section lists → homepage-snapshot only:**
- 无锡: `/doc/YYYY/MM/DD/<id>.shtml` (46 homepage links; sections 404 or 3-byte stubs)
- 12371 党员网: `/YYYY/MM/DD/ARTI<id>.shtml` (21 links)
- 西安: `/xw/.../<id>.html`, `/gk/zcfg/szfbgtwj/<id>.html`
- 辽宁: `/web/.../<id>/index.shtml` (92 links; homepage has API marker)
- 天津: `/YYYYMM/tYYYYMMDD_<id>` (37 homepage links; sections client-rendered)
  → These are crawlable ONLY as a rolling homepage snapshot (~20-90 recent docs,
    no pagination/history) unless the browser reveals the section list API.

**B. CLIENT-RENDERED / SPA shells → need browser network inspection (Jinan-class):**
- 郑州 (0 static links), MOHRSS (987 B shell), NFRA (215 B), 南京 (618 B),
  CNIPA (10 KB), MEM, NIA, 新疆; NFGA 林草局 = Hanweb (same as Jinan)

**C. Server-rendered homepage but 0 recognized article links → unknown format, inspect:**
- GAS 体育, NEA 能源, 政法委 (big homepages; their own URL scheme in sections)

**TAKEAWAY (answers "are there more Jinan-like cases?"): YES — nearly all of them.**
The generic static-crawler tail is EXHAUSTED. Every remaining reachable target either
renders its section lists client-side (tiers A/B — need the browser network-inspection
step, ideally once to crack a shared CMS like Hanweb) or uses an undiscovered per-site
URL scheme (tier C). Only shallow homepage-snapshot crawls are possible without the
browser. Recommended next: connect the Chrome extension, crack Hanweb's datacall once
(unlocks Jinan + NFGA + others), then tackle tier C by format.

## 10. Tier-C crack attempts + media round (2026-07-30) — outcomes

Worked the §9 tier-C list ("server-rendered homepage, own URL scheme") plus a
reliable-media pass. Net: one gov crack, one gov defer, one big media win.

**Two new reusable govcms dialects (committed):**
- `_ART_CONTENT_RE` generalized to `(?:content|c)_\d+` — matches the TRS
  `…/YYYY-MM/DD/content_ID.shtml` family AND the older `…/c_ID.htm`.
- `_ART_NEA_RE` — the `/YYYYMMDD/<hex>/c.html` family.
  → These help any future TRS-platform gov site, independent of NEA's fate.

**✅ 中央政法委 (chinapeace) — CRACKED, 95 docs live, wired into nightly.**
Server-rendered `content_N` sections (~99 links/section). This was the payoff of
the generalized dialect. Moves 政法委 out of tier C (§9) → done.

**⏸️ NEA 国家能源局 — DEFERRED (vantage problem, not code).** The dialect + config
are built and committed, but the droplet's DigitalOcean IP serves NEA's *homepage*
(200) while its *section list* pages (`/n/xwzx/index.htm`, `/n/policy/zxwj.htm`, …)
return **404 intermittently** — classic CN-gov datacenter-IP geo-fence (homepage
whitelisted, deep paths not). Configured in `govcms.SITES` but **NOT wired into
`daily_sync.sh`** (would just log 0). Salvageable only as a homepage snapshot
(~30 recent docs) or from a residential/China vantage. Stays in the BLOCKED-class
bucket (§5) in spirit.

**✅ 量子位 QbitAI (`crawlers/qbitai.py`) — ~3,000 docs, ~100% body, wired.** WP REST
API (`/wp-json/wp/v2/posts`) → bodies inline, no per-article fetch. Newest-first
incremental early-exit; `--full` backfills. Added to the media loop in
`daily_sync.sh`. This is the reliably-productive direction.

**Conclusion — reliable-from-droplet gov tail is now EXHAUSTED.** After 政法委, what
remains is exactly two vantage-point problems, both outside the droplet:
  (a) browser-gated SPAs (tiers A/B §9 + MOHRSS/CNIPA/南京/郑州) → need the Chrome
      extension to reveal section-list APIs (crack Hanweb once = several sites).
  (b) IP-flaky sites (NEA + the §5 BLOCKED provinces) → need a residential/China IP.
More govcms dialects won't move either. Media (WP/RSS: 虎嗅, 雷峰网, 机器之心) remains
the low-friction, high-yield path from here.

## 11. Province re-sweep (2026-07-31) — "gov tail exhausted" was WRONG

Re-probed the reachable-but-uncrawled **provincial** portals from the droplet
(§10's "exhausted" claim only looked at central bodies). Found **4 more buildable
provinces**. Three corrections + the new targets:

**Correction A — the govcms build-out landed better than the docs said.** Live
droplet counts (2026-07-31): chinapeace **151** (§10 said 95 — nightly kept
crawling), qbitai **3,022**, mot **1,018**, shandong **493**, cppcc 92, fujian 72,
jilin 64, shenyang 59, nhsa 155, nrta 46, elsewhere 74. Underperformers: jinan **4**
(Hanweb client-render), nea **0** (deferred, correct).

**Correction B — the anti-bot five need a BROWSER, not headers.** Tested 河南/安徽/
内蒙古 (still **403**) and 湖北/甘肃 (still **412**) with full Chrome headers +
zh-CN + keep-alive. `412 Precondition Failed` = a JS/cookie challenge (Incapsula-
class), not a UA gap. So §1/§5's "maybe fixable with headers" is now **tested
false** — they belong with the SPA/browser tier, not the quick-win tier.

**Correction C — 4 reachable provinces were never characterized → now are:**
| Province | Homepage | Section CMS | Verdict |
|---|---|---|---|
| **辽宁 Liaoning** | 200, web-idx | `/web/…/<ts-id>/index.shtml`, 20 gov-doc + 42 news links **server-rendered** | ✅ **DONE** — new `_ART_WEB_RE` dialect; **62 docs / 60 body live** |
| **西藏 Xizang** | 200, 55 t-date on homepage | 政策规章 `/zwgk/zfxxgk/fdzdgknr/zc/gz/`, 政务要闻, 公示公告 | ✅ **DONE** — t-date (dialect A), config-only; **64 docs / 63 body** |
| **宁夏 Ningxia** | 200, 69 t-date on homepage | 政策 `/zwgk/zc/`, 政策解读 `/zwxx_11337/zcjd/`, 通知公告 | ✅ **DONE** — t-date (dialect A), config-only; **45 docs / 45 body** |
| **云南 Yunnan** | 200, t-date + col | `/zwgk/*` policy subtree **403-fenced to datacenter IP**; only `/ywdt/` news reachable | ⏸️ defer — needs residential IP/browser for policy sections |
| **新疆 Xinjiang** | 200 | sections `.shtml` but 0 static article urls (client-render) | ⏸️ defer — Jinan-class, homepage-snapshot only |

**Revised conclusion:** the reliable-gov tail is NOT exhausted — it just moved from
central bodies to the **unknown-CMS provinces** (§1's "❔ reachable" row). Three new
provinces landed this round: **辽宁** (web-idx, new dialect) + **西藏/宁夏** (t-date,
config-only) = **~171 provincial gov docs, 98–100% body coverage**, all wired into
`daily_sync.sh`'s govcms loop. 云南 turned out to be datacenter-IP-fenced on its
policy subtree (news-only from the droplet) → deferred with 新疆 to the browser/
residential-IP tier.

**Section-rediscovery round (2026-08-01):** probed 天津 + 青岛 (homepage t-date, but
their obvious section paths weren't list pages). Learned real dirs from homepage
t-date link paths, then found the browsable bare-dir/index list page for each:
| City | Result |
|---|---|
| **青岛 Qingdao** | ✅ **DONE** — 市政府规范性文件 `/zwgk/zdgk/fgwj/zcwj/szfgw/` (177, **100% body**) + 政务要闻/公告公示 news. Config-only (dialect A), `municipal`. The old 政策解读 index (`/zwgk/xxgk/bgt/gkml/zcjd/`) is an archived dead list (articles 302→404) — deliberately excluded. |
| **天津 Tianjin** | ⏸️ defer — all 7 section dirs are JS-built (Hanweb datacall, like 济南); no browsable list URL. Needs browser network inspection. |

**Reachable-gov tail status:** worked through. The config-only provincial/municipal
frontier is now built out (辽宁/西藏/宁夏/青岛 this stretch). What remains needs a
different tool, not more crawler config: 天津 (Hanweb datacall → browser), 云南 policy
+ 新疆 (datacenter-IP/client-render → residential IP/browser), and the anti-bot five
(河南/湖北/安徽/内蒙古/甘肃, 403/412 even with Chrome headers → cookie-challenge browser).

## 12. Downward expansion — cities + departments (2026-08-02)

Probed the sub-units under the newly-added provinces (辽宁/西藏/宁夏): prefecture
cities (own domains) + provincial departments (`*.<prov>.gov.cn` subdomains), for
reachability + article-URL dialect. `enum_subsites.py` (homepage reachability +
t-date/art dialect) then `ln_dept_sections.py` (section rediscovery on the
buildable depts).

**Finding: it splits sharply BY PROVINCE — 辽宁 is browser-tier, but 西藏
departments are a large config-only win.** (An early version of this section
concluded "downward = browser-tier" from 辽宁 alone, before the 西藏/宁夏 enum
finished. That was the same scope-too-narrow error as §10/§11 — corrected below.)

**辽宁 (homepage links 271 gov hosts):**
| Layer | Status |
|---|---|
| Prefecture cities | **Mostly datacenter-fenced from the droplet.** 大连/鞍山/本溪/葫芦岛 = unreachable (DO NYC IP blocked). 朝阳/丹东/抚顺/阜新 = 200 but homepage-shallow (no t-date/art on homepage → need section probe). Separate city domains block the datacenter IP *harder* than the province portal does. → browser/residential-IP tier. |
| Provincial departments | **Reachable** (share the province's IP-allowlisting) but their list pages are **web-idx / Hanweb-datacall templates, not browsable bare-dir indexes.** ~6 expose articles on the homepage (gxt 工信厅 /art/, rst 人社厅, sthj 生态环境厅, whly 文旅厅 /art/, wsb 卫健委, mzw — all t-date/art), but section-root list pages 404 → each needs per-site list-endpoint discovery (browser network inspection), not a config add. |

**西藏 departments — a large config-only win (the 辽宁 conclusion did NOT generalize):**
Unlike 辽宁, 西藏 department subdomains (`*.xizang.gov.cn`) expose t-date DIRECTLY on
their homepages (td=44–185) AND their section list pages server-render at
`<section>/index.html`. So they're plain dialect-A config adds. **Built 20 西藏 depts**
as `xz_*` sites (round 1: 发改委 商务厅 自然资源厅 交通厅 司法厅 人社厅 卫健委 水利厅 农业农村厅
统计局 民政厅; round 2 via `dept_autoconfig.py`: 公安厅 科技厅 文旅厅 医保局 民委 投资促进局
生态环境厅 体育局 退役军人厅). Skipped: 住建厅 (no index.html list), 4 驻外办事处 liaison
offices (thin), wsb (unreachable), gdj (empty title). All tagged `group:"dept"` and
crawled via the new `govcms --group dept` (one command, scales cleanly).
`scripts/rnd/`-style helper `dept_autoconfig.py` emits ready SITES entries from a
subdomain list (title→name, ranks policy sections, confirms index.html render).

**宁夏 departments — ALSO a config-only win (earlier "404" was a probe BUG):**
The initial read said 宁夏 dept section roots 404 (like 辽宁). That was a FALSE
NEGATIVE: the probe concatenated homepage-relative dirs (`./yxxw/`) onto the host
without normalizing, yielding a trailing-dot FQDN (`fzggw.nx.gov.cn.`). That
trailing dot happens to resolve on 西藏's servers (so 西藏 probes worked) but errors
on 宁夏's — so 宁夏 looked dead when it wasn't. After normalizing `./x/`→`/x/`, 宁夏
depts render cleanly at `<section>/index.html`. **Built 19 宁夏 depts** (发改委 财政厅
科技厅 工信厅 教育厅 民政厅 司法厅 人社厅 自然资源厅 生态环境厅 住建厅 交通厅 审计厅 农业农村厅
商务厅 文旅厅 卫健委 医保局 应急管理厅) via `dept_autoconfig.py` — **952 docs, 96% body**,
richer than 西藏 (~50 docs/dept). gat/scjg/gzw hit transient errors, retry later.
Lesson: normalize relative URLs before probing — a trailing-dot host is a silent
per-server false negative. `dept_autoconfig.py` fixed to emit absolute paths.

**Takeaway (corrected):** the config-only frontier is NOT exhausted — the 西藏
department tier alone is ~28 addable sites. What genuinely needs the **browser tier**
(real JS + cookies + residential IP): 天津 + 辽宁 departments (datacall lists),
datacenter-fenced cities (大连 etc.), 云南 policy, 新疆, the anti-bot five. What's
buildable-next WITHOUT a browser: remaining 西藏 depts, 宁夏 depts (after section
probe), and likely other provinces' department subdomains (same pattern).
(Full sub-unit host record: `logs/enum_sub.log` on the droplet.)

**No-browser attempt at the datacall lists (2026-08-02):** tried to crack 天津's
client-side list endpoint by static JS analysis (no browser) — `datacall_probe.py`
+ `datacall_js.py`. Confirmed the CMS is **南威/Nanwei IGS** (`.jhtml` JSON
interface, `siteId=34`, e.g. `/igs/front/term/type.jhtml?code=…` for search). The
list-data XHR is NOT in the section HTML or the main mixin JS (`N_new_mixin-*`,
`N-QT.js` are UI-only); it's buried across further minified JS (`ta_Info.js`,
`articleReader.js`). Reconstructing it statically is possible but low-ROI vs. just
loading the page in a browser and reading the list XHR from the Network panel.
Confirms 天津 (and the 辽宁 datacall departments) are genuinely browser-tier.

## 13. Browser tier + districts + web platform (2026-08-08/09)

**Browser tier connected (Claude-in-Chrome).** Runs the user's residential Chrome —
real JS, cookies, non-datacenter IP. Used as a **key-cutter**: find *what* to crawl,
then the droplet crawls it.

- **海淀 Haidian cracked.** Its policy docs live on the `zyk.bjhd.gov.cn` content
  subdomain (the `www` homepage's t-date links were service-subdomain noise; `www`
  policy sections return 13-byte stubs). `zyk` IS droplet-reachable → config-only
  t-date add (`bjd_haidian`). Browser found it in one page-load after hours of ssh
  probing failed.

**District tier (22 sites, ~870 docs).** Beijing 海淀 + 通州/大兴/平谷/门头沟/西城
(the latter 5 needed 4 NEW url dialects: numid/tsid/hexmon/pnidpv — 0 duplicate
matches, 92-100% body). Other cities (t-date, config-only): 南京 鼓楼/江宁, 武汉
江汉/武昌/东湖高新/江岸/硚口/洪山, 重庆 渝中/九龙坡 (njd_/whd_/cqd_). Guangzhou districts =
Guangdong service platform (gkmlpt, not govcms); 苏州/天津/成都 districts = browser-tier.

**Central bodies.** cnipa 知识产权局 (/art/; needed the base.fetch gunzip fix — CNIPA
force-gzips). dangyuan 共产党员网 12371 (new ARTI dialect, 604-link 政策文件). NFRA/MOHRSS
= SPA/anti-bot (browser-tier).

**Web platform (3 subagent builds, all deployed).**
- **Search relevance = word-segmented BM25** (`doc_search_seg`, jieba). Was trigram
  substring ordered by DATE (no relevance); now bm25()-ranked (人工智能 → AI-literacy
  policy framework first, not a news blurb). Primer: `docs/research/search-primer.md`.
- **Source-type ontology** (`data/source_ontology.yaml` + `web/services/ontology.py`):
  hierarchical source TYPES (central/local/news/research), "exclude news" on search +
  browse. 32k news vs 218k non-news.
- **Network graph**: 5-6s → ~0.3s warm (bounded+cached server-side, SVG→Canvas).
- Fixed: structure page linked `/browse?site_key=` but the route param is `site` →
  filter was silently dropped (clicking MOF showed everything). Now `/browse?site=`.

**Province coverage reality (the honest finding).** Tier-1 (北上广深) all covered;
~14/34 provincial units crawled. The gap is **datacenter-IP-BLOCKED province portals**
— e.g. 四川/河北 are genuinely unroutable from the droplet (Errno 101); 湖北's homepage
is 412 and only its `/zwgk/hbyw/` news subtree is droplet-reachable (policy `/xxgk/` =
412). **Browser recon does NOT unlock these for the droplet crawler** — the browser
(residential IP) reads them, but the crawler (datacenter IP) still hits the WAF on the
useful sections. Real unlock = a **residential fetch vantage**: (a) residential proxy
for the crawler, or (b) local `govcms --site <prov>` from a residential machine →
merge up. DECISION PENDING.

**Ops lesson (recurring this session).** Single-box contention on the droplet caused:
deploy-hygiene aborts (dirty working tree from scratch `cp`s silently blocked
`git pull`), fujian WAF blocks (my own probes re-triggering a ~1-min IP block), and
the BM25 build's `database is locked` (crawl + index-build writing at once). TODO: a
build/crawl lock so index builds never overlap crawls; stop leaving the droplet tree dirty.
