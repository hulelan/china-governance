# TODO — scratch consolidation (2026-07-04)

Temporary working list pulled together from the current conversation. Delete/prune
as items land. Grouped by theme, roughly priority-ordered within each.

---

## 1. Pipeline / infrastructure

### 1a. Move the nightly run OFF the Mac  ⭐ (you asked: "is the pull running on our computer?")
**Yes — it is.** Your Mac `crontab` has:
```
0 7 * * * ./scripts/daily_sync.sh >> logs/cron.log 2>&1
```
So `daily_sync.sh` fires on the Mac every day at 07:00 local — *in addition* to the
droplet's own cron (`0 6 * * * … daily_sync.sh`, runs on 104.236.88.45). Two problems:
- **Redundant + taxes your hardware** (crawl + DeepSeek classify + rsync, locally).
- The Mac run has **no `.is_production_droplet` marker**, so its Phase 3 rsyncs the
  local DB *up to the droplet* — which can clobber/conflict with the droplet's own
  authoritative copy.
- The cron uses a **relative path** (`./scripts/…`), so from cron's home-dir CWD it
  likely can't even find the script — probably erroring nightly anyway.
- (The two `~/Library/LaunchAgents/*.plist.disabled` are already disabled — the
  **crontab** is the live local runner.)

**Action:** remove that one crontab line → droplet-only. Zero downside; the droplet
is the source of truth. → *offered to do this immediately.*

#### SCOPE RESULT (2026-07-04): the Mac is already fully substituted — and the cron is BROKEN
- **The Mac cron hasn't actually run in ~5 weeks.** It uses a *relative* path
  (`./scripts/daily_sync.sh`), and cron's CWD is `$HOME`, so it resolves to a
  nonexistent `~/scripts/…` and fails instantly every morning. Evidence: no
  `logs/cron.log` anywhere, and the Mac's `documents.db` mtime is **May 26**
  (untouched since). So it is NOT your battery cause and removing it loses nothing.
- **Coverage substitution: ~complete.** The droplet already runs every universal
  crawler + miit/most/zhejiang/hangzhou + `gkmlpt --sync` (which iterates ALL
  SITES, incl. gd/huizhou/yangjiang). gd is reachable from the droplet (HTTP 200).
- **Only true gap: huizhou + yangjiang.** Both are HARD-BLOCKED from the droplet's
  DigitalOcean IP (huizhou refuses instantly, yangjiang blackholes — fails with
  browser-UA + https too). Classic "CN gov site blocks datacenter IPs, allows
  residential." But the broken Mac cron isn't crawling them either, so this is a
  **pre-existing gap**, not something removal creates. (~6,200 docs combined,
  mostly already captured; only *new* docs are missed.)
- **officials.db** needs the Mac (Excel seed) but is NOT nightly — no impact.
- **Battery culprit is almost certainly iCloud, not the cron.** The project lives
  in `~/Desktop`, which iCloud Desktop-syncs; we hit iCloud `.git/index.lock`
  "Operation timed out" errors twice THIS session — proof iCloud is actively
  churning this directory (3.9GB DB + WAL + .git). → see 1d.

**Revised action:** (1) delete the dead cron line (pure cleanup). (2) Decide
huizhou/yangjiang: accept the gap / occasional manual crawl from a residential IP /
proxy. (3) Chase the real battery drain in 1d.

### 1d. Battery / iCloud — the likely real cause
The repo is under `~/Desktop/claude_code/china-governance`, so iCloud Desktop-sync
is syncing a 3.9GB `documents.db` (+ WAL/shm + `.git`). That's the probable battery/
CPU/network drain (and the source of the `.git/index.lock` timeouts). Options: move
the project out of `~/Desktop`/`~/Documents` (iCloud-synced) to e.g. `~/dev/`, or
exclude it from iCloud. Investigate with `brctl status` / Activity Monitor.

### 1b. Fix crawler timeouts  ⭐ (you asked to fix these)
`CRAWLER_TIMEOUT=1800` (30 min/crawler) in `daily_sync.sh`. Last run: **593 min total**,
**11 crawlers hit the 30-min cap**: cac, samr, mofcom, beijing, shanghai, jiangsu,
suzhou, heilongjiang, xinhua, miit, most.
- **Root cause (hypothesis):** US→China latency from the NYC droplet — these sites are
  slow/large from the US. (miit/most/samr already carry "slow/timeout from US" notes in
  their docstrings.)
- **Options to weigh:**
  - Raise the per-crawler timeout for the known-slow set (simple, but lengthens the run).
  - Ensure each is running in **incremental/`--sync` mode** so it fetches only new docs,
    not the whole listing every night (biggest win if some are doing full re-scans).
  - Stagger/parallelize (careful: SQLite = 2 writers max).
  - Investigate per-crawler: is it the *listing* fetch or *body* fetch that stalls?
- **Needs diagnosis before fixing** — pick 2–3 worst (miit, most, samr) and time them.

#### DIAGNOSIS (2026-07-05): full-pagination re-walk × NYC latency
The timing-out crawlers loop over their WHOLE listing pagination every run
(`for page in range(2, total_pages+1)` in samr/beijing/shanghai/suzhou/…), fetching
every listing page even when its docs are already stored. From NYC the per-fetch
latency to .gov.cn is high, so walking the full backlog exceeds `CRAWLER_TIMEOUT`
(1800s). `samr` additionally re-fetches now-dead 2023 article URLs (the 404s in the
report) — wasted round-trips. They're mostly reverse-chronological, so the *newest*
docs are usually captured before the timeout (some show +N docs); the cap cuts the
historical tail. But the 0-doc-timeout ones (cac/samr/beijing/jiangsu/suzhou/…) may
be re-walking without reaching new content.

**Proper fix (per-crawler, must be TESTED):** early-exit the listing loop once a full
page yields zero new docs (all URLs already in DB). Since listings are
reverse-chronological, everything past that point is already held. This makes each
crawler truly incremental and should drop nightly time drastically. Some crawlers
already have partial early-exit ("Empty page — stopping"); the timing-out ones need
an *all-already-seen* early-exit added.
**Do this when the droplet is idle** (time a crawler before/after) — NOT a blind
edit to 11 crawlers deployed straight to the nightly. Stopgap if urgent: bump
`CRAWLER_TIMEOUT` for the slow set (but that lengthens the already-~10h run toward
the 24h cron-overlap limit, so early-exit is the real fix).

### 1c. Verify Phase 3 on the droplet isn't rsyncing to itself
Report shows `Droplet: … (rsync: true)`. On the droplet, Phase 3 should checkpoint
in place (no rsync). Confirm the `.is_production_droplet` marker is detected and the
"rsync: true" is just a mislabeled report field, not an actual self-rsync.

---

## 2. Auto-updates / citations (you asked: "is Policy Trace automatic?")

### 2a. Automate citation extraction nightly  ⭐ — and it's ~FREE
Policy Trace / Network / "cited by" are **snapshots**, not live: the `citations` table
is built only by `scripts/rnd/citations/extract_citations.py`, which is NOT in
`daily_sync.sh`. New docs don't appear in chains until it's re-run.
- **Cost to automate: ≈ $0 in API.** Both inputs already exist nightly — body text is
  free (regex), and `references_json` (the LLM part) is already produced by the nightly
  classifier you're paying for. Assembling the table is pure CPU.
- **Action:** add an extraction phase to `daily_sync.sh`. First check whether
  `extract_citations.py` is incremental or rebuilds all ~180k (determines runtime); if
  full-rebuild, consider add-only/incremental mode. → *scoping offered.*

### 2b. Homepage freshness — no action
Homepage content is already auto-fresh (live queries + 1h cache cleared on nightly
restart). Only gap is **SEO/social `<meta>` tags** (see 4a).

---

## 3. Classification

### 3a. Cost / "what's cheapest?" (you asked)
- **For citations specifically, the cheapest is regex — it's free** (no API). It already
  produces ~213k of the ~227k edges. DeepSeek adds only ~14k fuzzy-recall edges.
- **For the LLM path, DeepSeek is the cheap option:** ~$0.28/M input + $1.10/M output
  tokens ≈ **$0.50 / 1,000 docs**. Only other backend wired up is **Ollama** (local =
  "free" but needs a GPU and is slow). No OpenAI in the classifier.
- **Bottom line:** nightly classification is already on the cheapest sensible option;
  and citation automation (2a) needs *no* new spend.

### 3b. Classification errors — investigate?
Last run: **37 classification errors** / 419 new docs (~9%). Historically ~1.4% is the
expected DeepSeek content-filter loss; 9% is higher — worth a look at what's failing
(content filter vs empty responses vs rate-limit). Low urgency.

---

## 4. Website follow-ups (redesign is shipped)

### 4a. SEO / social meta tags
`base.html` has only `<title>` — no `<meta name="description">`, no Open Graph/Twitter
cards. Add per-page description + OG so links preview and search snippets aren't blank.
~20 min, no pipeline cost.

### 4b. IPC body extraction (the 255 empty court docs)
NOT a UA fix — `ipc.court.gov.cn` renders bodies via **PDF.js / client-side JS** (static
HTML is a 269-byte shell). Real task: find the `/article/content/…` data endpoint or
extract the linked PDFs. Scoped scraping job; do when the court corpus matters.

---

## 5. Minor / noise from the last report (likely benign)
- **gkmlpt `UNIQUE constraint failed: documents.url`** — this is the dedup guard working
  as designed (IntegrityError-skip), just surfacing as an "error" line. Consider
  catching it so it stops showing as a failure.
- **mofcom → customs.gov.cn HTTP 412 Precondition Failed** — anti-bot on the customs
  subdomain; needs browser-shaped headers or skip.
- **samr / xinhua 404s** — individual dead article URLs; expected attrition, not a bug.

## Queued crawl targets (2026-07-23)
- [ ] elsewhere.news/zh — Chinese-language news aggregator (media crawler, like xinhua/guancha). Investigate structure + build crawler.
- [ ] GOAL: bespoke crawlers for EVERY reachable-uncrawled entity in coverage.csv (central + provincial + city, http 200). ~40+ sites, each needs real per-site reverse-engineering (col/ labels were false positives).

## Build-out progress (2026-07-23 session)
DONE this session:
- 3 critical perf/correctness fixes: fleet-wide dedup index (40b82f3), 6-crawler dedup (cd5c586), gkmlpt IntegrityError (785ef2d). Daily run should drop from 8.7h.
- crawlers/govcms.py NEW — generic gov "t-date list" crawler. 5 central bodies live: mwr(56) nbs(18) mva(15) mct(20) mara(25). Wired into nightly + coverage.
- chinatax --full backfill running (2567 -> ~9900).

govcms EXPANSION TODO (reachable central bodies still needing sections found):
- JS-nav / different URL scheme (need deeper probe): MOT, MOHRSS, CNIPA, GAS, MEM, NIA, CPPCC, 中央政法委, 12371, NEA(hash-urls), NFGA(.jhtml), NFRA(SPA)
- Then provinces/cities tier (26 reachable): 山东 辽宁 吉林 福建 湖南 云南 西藏 新疆 + capitals (济南 郑州 沈阳 福州 长春 南京 西安 拉萨 乌鲁木齐 银川 海口 天津 石家庄) + 无锡 青岛
- elsewhere.news/zh (media crawler, Next.js JSON API)

## Session 2026-07-23/24 continued
- Daily run 521m -> 188m (dedup index fix confirmed in 07-23 report). Still ~3h — more headroom (network latency).
- gkmlpt FK fix (cb1db78): url-collision skip now also skips _record_change (FK to documents.id). Was aborting the sweep.
- coverage.csv regenerated: CRAWLED 100->110, central 20->27.
- shandong: jpaas discover fixed (http not https) but crawl=0 docs — jpaas.discover finds 政务公开 meta-columns not the 省政府文件 doc list (col 320658). NEEDS jpaas column-depth fix before wiring. NOT in nightly.
- STILL TODO: qingdao/tianjin/mohrss govcms section rediscovery; 济南/郑州/无锡 col (bespoke); non-t-date central (cnipa/gas/mem/nia/政法委/12371/nea/nfga/nfra); elsewhere.news; jpaas depth fix (unlocks shandong + more provinces).

## Session 2026-07-24 — govcms /art/ + col-city findings
- govcms +/art/ dialect (ee44a57): unlocked 山东 (490 docs, ~80% body). govcms now 12 sites.
- 济南/郑州/无锡 are NOT quick govcms adds: their policy columns list via JS (static /col/ index HTML has 0 /art/ or t-date links). 济南's 16-art cols are NEWS feeds not policy. Need browser network inspection to find the JSON list API → bespoke crawler.
- REMAINING (all need bespoke reverse-engineering, no quick wins left):
  - JS-list col cities: 济南 郑州 无锡 (find data API)
  - non-t-date central bodies: MOHRSS(人社部,major) CNIPA GAS MEM NIA 政法委 12371 NEA NFGA NFRA
  - govcms section rediscovery: qingdao tianjin (t-date on homepage, wrong section dirs)
  - other provinces/cities: 辽宁 新疆 南京 西安 (no-tdate)
  - elsewhere.news/zh (Next.js JSON API — media)

## elsewhere.news DONE (2026-07-24, e939fc9)
- crawlers/elsewhere.py: 64 docs, 97% body. Next.js+Supabase (anon 401 → scrape server-rendered HTML). Technique proven: inspect framework → find data path → crawl. Live + nightly.
- JS-site playbook: curl HTML → detect framework (_next/supabase/etc.) → check if server-rendered (scrape) vs client-fetched (find JSON API in bundles / browser network tab).
- Next JS targets: 济南/郑州/无锡 (gov, likely need browser network inspection for their list API); other media.

## Jinan (2026-07-24, 4a2ec44) — PARTIAL
- Jinan runs Hanweb CMS. Extended govcms /art/ regex to match Hanweb's
  /art/YYYY/art_<hex>.html (durable generalization; shandong regression clean).
- Wired jinan 政策解读 columns (col118736/col121799) — server-rendered, small.
- NOT DONE: jinan's high-value policy columns (通知公告 col44545, 政府文件, 政府公报)
  are 4KB shells that render lists CLIENT-SIDE via Hanweb datacall (ColId meta,
  no list in static HTML, list endpoint constructed at runtime by layui/hanweb JS).
  → NEXT: browser network inspection (Chrome tools) to capture the datacall list
  endpoint, then build a Hanweb-datacall crawler (would generalize to many Hanweb
  gov sites — a big unlock).
