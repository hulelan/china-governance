# RESUME — coverage build-out pickup guide (as of 2026-07-24)

**Read this first to continue the crawler build-out.** It captures the current
state, what's blocking what, and the exact next move for each remaining target.
Companion: `coverage-tracker.md` §8–§9 (the CMS survey) and `todos.md`.

---

## 1. Where we are

**Daily run health:** 521m → 188m after the fleet-wide partial-index dedup fix
(`40b82f3` + `cd5c586`). gkmlpt sweep no longer aborts (FK fix `cb1db78`). Expect
~0 crawler failures now. Tonight's run is the confirmation.

**chinatax:** COMPLETE at ~4,999 unique docs (the "~9,900" was an overcount — fgk
cross-lists docs across categories).

**New crawlers this session (all wired into `daily_sync.sh`):**
- `crawlers/govcms.py` — generic gov list crawler, **13 sites**. See §2.
- `crawlers/elsewhere.py` — elsewhere.news 别处 (VC/AI tech, 64 docs). See §3.

**Landed in production DB already:** elsewhere (64), the first 5 govcms central
(mwr/nbs/mva/mct/mara from the last nightly).
**Lands on the NEXT nightly (added after last run):** govcms mot, cppcc, jilin,
fujian, hunan, shenyang, shandong, jinan. (~1,600 more docs.)

---

## 2. govcms.py — how it works (for adding sites)

Handles server-rendered gov list pages. Two article-URL dialects:
- **t-date**: `…/YYYYMM/tYYYYMMDD_ID.html` (most central ministries)
- **/art/**: `…/art/YYYY/M/D/art_NUM_NUM.html` (Shandong) AND
  `…/art/YYYY/art_<hex>.html` (Jinan/Hanweb) — M/D optional.

To add a site: `SITES["key"] = {name, base_url, admin_level, sections:[...]}`.
`--discover` maps a section root's sub-sections; a section that lists articles is
a leaf. Body extraction = "innermost `<div>` with the most `<p>`-text" (handles
template variation). Reuses `gov._extract_metadata_table`. Deep pagination
(`index_N.html`) is usually a broken stub, so it's page-0-reliable (`--deep` is
best-effort). Commits every 20 docs (long sections survive interrupts).

**Then also:** add the site to the `daily_sync.sh` govcms loop + set its site_key
in `scripts/rnd/discovery/build_coverage_csv.py` (CENTRAL/PROVINCES list) so
coverage.csv marks it CRAWLED.

Discovery technique that found the section paths: **derive sections from article
URLs** — fetch homepage, collect t-date/`/art/` links, group by parent dir; those
dirs are the sections (used to crack MOT/CPPCC/provinces where JS-nav hid the menu).

## 3. elsewhere.py — JS-site technique (for future modern sites)

elsewhere.news is Next.js + Supabase but SERVER-rendered. Playbook that worked:
1. `curl` the HTML → fingerprint the framework (`_next/static`, `supabase`, etc.).
2. Supabase REST is service_role-gated (anon → 401), so DON'T use the API — scrape
   the rendered HTML: `og:title`, `article:published_time`, `article:author`, and
   the `<article>` body (strip `<script>` first so the JSON-LD block doesn't leak).
3. Article links = 2-segment `/zh/<section>/<slug>` from homepage + section indexes.

**Generalizable rule:** if a JS app's data path (API URL + key) sits STATICALLY in
a bundle, crack it like elsewhere. If it's built at runtime (Hanweb, §5), you need
the browser.

---

## 4. THE BLOCKING MAP — what's left + what each needs

From the CMS survey (`coverage-tracker.md` §9). **The generic static-crawler tail is
exhausted** — everything easy (server-rendered lists) is already crawled. What
remains splits three ways:

### Tier A — static article URLs, but CLIENT-RENDERED section lists
Homepage aggregates article links (crawlable as a rolling snapshot, ~20–90 recent
docs, NO pagination/history); the section list pages are client-rendered.
- 无锡 `/doc/YYYY/MM/DD/<id>.shtml` (46 homepage links; sections 404 / 3-byte stubs)
- 12371 党员网 `/YYYY/MM/DD/ARTI<id>.shtml` (21 links)
- 天津 `/YYYYMM/tYYYYMMDD_<id>` (37 homepage links; sections client-rendered)
- 西安 `/xw/…/<id>.html`, `/gk/zcfg/szfbgtwj/<id>.html`
- 辽宁 `/web/…/<id>/index.shtml` (92 links; homepage has an API marker — maybe
  crackable like elsewhere; INSPECT its bundles for a static list API first)

**What we'd DO for Tier A** (two options):
  (a) **Homepage-snapshot crawler** — a govcms-like crawler that only reads each
      site's homepage/aggregator, extracts the per-site article URL (regex per
      format above), stores them. Low yield (~40/site) but grows incrementally and
      needs NO browser. ~1–2h to build a small `snapshot` crawler covering all of
      Tier A (config = {site: (homepage_url, article_regex, date_from_url?)}).
  (b) **Full crawler via browser** — use the Chrome tools to capture each site's
      section-list API (same as Tier B), then paginate it. Higher yield, needs the
      extension connected. Prefer (a) now, (b) later.
  → 辽宁 is the exception: check for a static in-JS list API (elsewhere-style)
    before treating it as browser-only — its homepage carried an `/api/` marker.

### Tier B — SPA shells / Hanweb → NEED the browser network-inspection step
Pure client-render; nothing useful in static HTML or (for Hanweb) greppable in JS.
- 郑州 (0 static links), MOHRSS (987-byte shell!), NFRA (215 B), 南京 (618 B),
  CNIPA (10 KB), MEM, NIA, 新疆
- **NFGA 林草局 = Hanweb** — same CMS as Jinan.

**What we'd DO for Tier B — the high-leverage move:**
  Crack **Hanweb's datacall ONCE** via the browser (see §5), build a
  `crawlers/hanweb.py` datacall crawler, and it unlocks Jinan + NFGA + likely
  several Tier-A cities that are Hanweb underneath. One crack → many sites.

### Tier C — server-rendered homepage but UNKNOWN article-URL format
Big homepages, but no t-date/`/art/`/`/doc/` links found — their own scheme.
- GAS 体育, NEA 能源, 政法委
**What we'd DO:** per-site, fetch homepage + a policy section, dump ALL article-ish
hrefs, learn the format, add a regex (like we did for 无锡/12371/西安 above), then
check if sections server-render (→ govcms) or client-render (→ Tier A/B).

---

## 5. Hanweb datacall — investigation state (resume here for the browser step)

Jinan (and NFGA) run **Hanweb CMS** (南威/政务云; markers: `hanweb.min.css`,
`<meta name="ColId">`, `/jcms1/…`, `/jact/`). Policy columns (通知公告 col44545,
政府文件, 政府公报) are ~4KB shells that render lists client-side.

**What I confirmed (non-browser attempts, all exhausted):**
- Static HTML: no list, only `<meta name="ColId" content="44545">`.
- JS bundles (`/cms_files/jcms1/web1/site/script/1361/*.js`, layui, require.js):
  the one `server/index.do` found = the 智能问答 chatbot widget, NOT the list.
  The datacall URL is built AT RUNTIME by require.js modules — not greppable.
- Saw `/jact/front/datacall/showJsContent.do?iid=<N>` on a NEWS column (iid=2327),
  but `iid` for the policy columns isn't in their static shells, and a bare
  showJsContent.do?iid=2327 returned a 678-byte stub.

**EXACT next step (needs Chrome extension connected — it wasn't this session):**
1. Connect the Claude Chrome extension (claude.ai/chrome), same account as Claude Code.
2. `tabs_context_mcp` → `navigate` to `http://www.jinan.gov.cn/col/col44545/index.html`.
3. `read_network_requests` (urlPattern `datacall` or `.do` or `/jact/`) → find the
   XHR that returns the 通知公告 list (note its full URL + params: iid/colid/webid/
   page/size).
4. Replay that endpoint with the right params; parse the returned list (likely HTML
   fragment or JSON with `/art/…art_<hex>.html` links + dates).
5. Build `crawlers/hanweb.py`: config {site: base_url} + per-column datacall params;
   reuse govcms `_extract_body` for article bodies. Test on Jinan, then add NFGA.
   NOTE: a residential Chrome may reach gov sites the NYC droplet can't — bonus.

---

## 6. Gotchas that bit us (don't rediscover)

- **Partial-index dedup**: every `WHERE url = ?` MUST include `AND url != ''` or it
  full-scans the 224k-row table. See memory `project_partial_index_dedup_stall`.
- **scp-blocks-git**: DON'T scp test crawlers into the droplet repo dir — a left-over
  modified/deleted tracked file silently blocks `git pull` and strands the droplet
  commits behind. Test against `/tmp` copies, or `git checkout -- <file>` before pull.
- **macOS has no `timeout`** — don't wrap Mac-local test runs in `timeout`; use the
  droplet or `gtimeout`.
- **coverage.csv regen is slow** (~20 min; re-probes ~110 domains incl. blocked ones
  at 4 schemes × 12s). It reads the LOCAL/droplet DB — run it ON THE DROPLET (current
  DB), then scp the result to the Mac + commit; `git checkout` the droplet's copy so
  the next pull is clean. daily_sync.sh does NOT regenerate it.
- **Coverage counts** for sites added after the last nightly show empty until they
  crawl; re-run the regen after a nightly to finalize counts.
