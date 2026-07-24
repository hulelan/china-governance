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

**A. STATIC, date-in-URL → buildable now (per-site regex):**
- 无锡: `/doc/YYYY/MM/DD/<id>.shtml` (46 homepage links) + `/fzlm/zfgb/` 政府公报
- 12371 党员网: `/YYYY/MM/DD/ARTI<id>.shtml` (21 links)
- 西安: `/xw/.../<id>.html`, `/gk/zcfg/szfbgtwj/<id>.html` (no date in URL — row date needed)
- 辽宁: `/web/.../<id>/index.shtml` (92 links, no date in URL; homepage has API marker)

**B. CLIENT-RENDERED / SPA shells → need browser network inspection (Jinan-class):**
- 天津 (homepage aggregates 37 t-date links but every section list = client-rendered)
- 郑州 (0 static links), MOHRSS (987 B shell), NFRA (215 B), 南京 (618 B),
  CNIPA (10 KB), MEM, NIA, 新疆
- NFGA 林草局 = Hanweb (same as Jinan)

**C. Server-rendered homepage but 0 recognized article links → unknown format, inspect:**
- GAS 体育, NEA 能源, 政法委 (big homepages, no t-date/art/doc links found — likely
  their own URL scheme in sections; needs per-site format discovery)

**Takeaway:** the generic-crawler tail is exhausted; each remaining site is its own
regex (tier A) or needs the browser step (tier B, Hanweb/SPA). Tier A ≈ 4 quick
bespoke builds; tier B waits on the Chrome extension being connected.
