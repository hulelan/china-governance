# CLAUDE.md — Operational Guide

## What This Project Is

Chinese government document corpus + web app. Crawls policy documents from central (State Council, NDRC, MOF, MEE) through provincial (Guangdong) to municipal (Shenzhen + 16 other Guangdong cities) and district level. Live at [chinagovernance.com](https://www.chinagovernance.com).

## Current Corpus (April 2026)

- **135,480 documents**, 62 sites, 93% body text coverage (126,027 with body)
- **Algorithmic scoring** on all docs: citation_rank (PageRank-like), algo_doc_type (19 types from regex), ai_relevance (0-1 keyword density). 195 high-AI docs, 2,627 medium+, 12,102 with inbound citations.
- **24k classified (v2 prompt)** with doc_type, policy_significance, references_json; ~109k have v1 fields (title_en/summary_en/importance)
- Shenzhen (municipal + 9 districts + 13 departments + investment portal), Guangdong Province, 16 other Guangdong cities
- Central: State Council, NDRC, MOF, MEE, CAC, NDA, SIC, SAMR, MOFCOM, MIIT, MOST
- Provinces: Beijing (1,801), Shanghai (3,830), Jiangsu (1,048), Heilongjiang (2,265), Chongqing (697), Zhejiang (70)
- Municipalities: Wuhan (999), Suzhou (4,841), Hangzhou (new)
- Media: Xinhua (1,504), People's Daily (1,102), Phoenix/凤凰网 (180, incl. tech + 9 regional channels), LatePost (94), 36Kr (10), Tsinghua AIIG (57)
- Legal: Supreme Court IP Tribunal (ipc.court.gov.cn, crawler built, pending first deep run)
- 227,516 cross-document citations (14,265 LLM-sourced)
- Stored in `documents.db` (SQLite, ~3.9GB). **As of June 2026 the authoritative
  copy lives on the droplet, not the Mac** — see Architecture below.
- Title translations: ~99.7% of titles have `title_en` (free Google/deep-translator
  pass). References: `references_source` on ~133k docs (`regex_v1` + `deepseek_v2`).
- Corpus counts above are an April-2026 snapshot (~135k); the live total is
  higher (**~277k as of Aug 2026**, after the citation-driven historical backfill —
  see the Research layer below). Check `/api/v1/stats` for the current number.

**Aug 2026 additions (this build-out):**
- **Provincial department tier** (119 sites, ~10.8k docs) via `govcms --group dept`:
  西藏 (xz_*, 20), 宁夏 (nx_*, 19), 福建 (fj_*, 38), 重庆 bureaus (cq_*, 40+). Plus
  province portals 辽宁/西藏/宁夏/青岛.
- **District tier** (22 sites, ~870 docs): Beijing 海淀 (bjd_haidian, on the
  `zyk.bjhd.gov.cn` content subdomain — found via browser network inspection) +
  5 more BJ districts (通州/大兴/平谷/门头沟/西城, needing 4 new URL dialects) +
  Nanjing/Wuhan/Chongqing districts (njd_/whd_/cqd_).
- **Central**: cnipa (知识产权局, /art/), dangyuan (共产党员网 12371, new ARTI dialect).
- **Web features**: `/collections/oil` (topical collection, live corpus + curated
  annotations), source-type **ontology** (`data/source_ontology.yaml` + "exclude
  news" filter on search/browse), **BM25 relevance** search (below), Canvas-rendered
  network graph (bounded + cached, ~5s→0.3s).
- **Research layer (2026-08-22 — pivot from crawl-volume to analysis).** Goal
  clarified: political-science research on China as a bureaucracy (institutional /
  comparative governance). See `memory/project_research_pivot.md`. Shipped:
  - **Policy Lens** — `/lens` (`web/services/lens.py`, `templates/lens.html`): a
    topic/document dossier. `?q=<topic>` → attention timeline, admin-level &
    genre & issuer breakdowns, most-cited anchor docs (title-match only, no body
    scans, 1h cache). `?doc=<id>` → outbound/inbound citation neighborhood.
  - **Policy Tracker (2026-10-01)** — `/tracker?topic=<area>&weeks=<n>`
    (`web/services/tracker.py`, `templates/tracker.html`): the LIVE daily/weekly
    layer (`docs/research/daily-tracker-concept.md`). Reads only two nightly
    precomputed tables, so pages render in ~0.03s: `diffusion_events` (the
    auto-matcher — each sub-national doc → the central instrument it implements,
    match_type citation/title_reissue/topic_genre + lag_days; built by
    `scripts/rnd/analysis/build_diffusion_events.py --write`, validated to
    reproduce the hand-built cascades in `consumption-diffusion.md`) and
    `tracker_weekly` (per topic × ISO week × admin_level new-doc + cascade counts,
    `scripts/build_tracker_rollup.py`). Both rebuild in `daily_sync.sh` Phase 2c
    after citations/scores/topics. Anchor set excludes `npc` 地方法规 (they're
    local 人大 regs mis-leveled as central) and explainer representatives. Known
    gap: `diffusion_events.topic` stores only the anchor's FIRST topic tag; the
    tracker service compensates with a cached anchor→topics map. **A consequence measured
    2026-10-07:** since a cascade is labelled by its ANCHOR's `topics_algo`, and the
    mirror-determinism fix changed which copy of a text is the anchor for ~18.8k titles, every
    topic-labelled aggregate shifted by RELABELLING rather than by any denominator effect. It
    flipped which policy area is slowest in `policy-tempo.md`: Culture's cascade count FELL
    48 → 26 while its denominator rose 743 → 765, so Culture replaced Tourism as slowest. Treat
    any topic-level series as sensitive to anchor selection, and re-base it after an identity
    change instead of assuming only the counts moved.
  - **Per-document identity layer (2026-10-06)** — `doc_identity` side table
    (`scripts/build_doc_identity.py`, nightly Phase 2b LAST step, `--force` because the
    nightly holds the lock; ~37s, one transaction): `admin_level_doc` + `level_source`
    (per-DOCUMENT level from issuer/文号/npc-publisher/title-cue, falling back to the
    site; 98% precision; 21% of docs differ from their site's level, incl. all 28.6k npc
    地方法规 which are provincial/municipal, not central), `instrument_id` +
    `instrument_role` (canonical|mirror|unique; mirror promulgations of one text pooled by
    normalized title-core within ±400d, edition-aware — 政府信息公开条例 is 2 instruments,
    2007 and 2019), `genre` (promulgation|implementing|explainer|readout|news|other, 88%),
    `date_quality` (good|crawl_stamped|missing; `crawl_stamped` fires only when ≥70% of a site's
    modal-crawl-day docs are dated THAT day, currently 0 docs. The earlier "76 sites / 29k
    crawl-stamped" was a false positive of a ≥70%-in-crawl-year rule that caught shallow
    archives; hand-checked 2026-10-07, see `corpus-lessons.md` A4. The rule also sums bulk
    DATE-days (≥20 docs & ≥10% of a site on one day, day-01 exempt, ≥50% total) to catch a
    source CMS's page-regeneration stamps, the Suzhou shape: 3,354 docs sat on two 页面生成时间
    dates and were redated from the article header / 发文日期 / URL month. `scripts/redate_from_html.py
    --site X [--dry-run]` re-parses saved HTML for dates without a recrawl, routing site_key →
    the crawler's own dater (`SITE_DATERS`), same pattern as `backfill_from_html.py` for bodies.
    Month-precision fallbacks land on day 01 and still read `good`; there is no precision column),
    `lead_issuer` (from `doc_issuers`), `localized_of` (the in-chain higher-level doc whose
    stem a sub-national promulgation re-issues; set on the 2,583 docs re-typed `implementing`.
    The flip requires the parent to be CENTRAL or in the doc's own province/city chain via
    `data/city_province.csv`, and the stem must not be a housekeeping genre like 议事规则 /
    三定规定 — a 60-doc hand-check (`docs/working/qa-genre-flip.md`) found the earlier
    any-higher-text rule 80% precise, every error out-of-chain or housekeeping).
    Rationale: `docs/research/corpus-lessons.md` A1-A5
    — the replications showed level/instrument/genre/date/issuer were inferred or
    per-site. `build_diffusion_events.py` now reads level, pooling and the implementing
    flag FROM this table (its own derivations were deleted). Prefer joining `doc_identity`
    over `sites.admin_level` / `algo_doc_type` in any new analysis.
  - **Identity-layer additions (2026-10-07)** — `doc_identity` gained `province` (2-letter
    code per DOCUMENT from lead_issuer / 文号 agency / publisher / masthead / `localize()`, so
    the 28.6k npc 地方法规 and other sub-national docs on national sites join provincial
    chains; `build_diffusion_events` and `pairs.py` prefer it over the site map in
    `scripts/rnd/analysis/geo.py`, which itself derives a site's province from `sites.name` ×
    `data/city_province.csv` with the hand table as override) and `instrument_kind`
    (framework | housekeeping | other, from the issuance wrapper + title core; replaces the
    matcher's `is_framework` regex gate, which a 60-doc hand-check found 23% precise,
    `docs/working/qa-framework-gate.md`). `localized_of` is now date-ordered: the trigger must
    be dated ≤ the doc + 7 d (+31 d for month-precision dates) and the NEAREST earlier in-chain
    parent wins (488 reversed edges were later central re-issuances, not re-posts); flips
    2,592 → 1,958. Resolver: `data/instrument_aliases.csv` (cited-as → held title, applied only
    when the ref has no exact candidate), HTML-entity unescape of refs, and the title index
    floor lowered 8 → 5 chars (1,661 short held titles like 广东省公路条例 were never candidates).
    Research infrastructure: `scripts/rnd/analysis/pairs.py` builds the union pair set
    (citation ∪ title_reissue ∪ localized_of) with the memos' fidelity scores in code
    (`docs/research/pair-channels.md`: the citation-only relay figures are floors, +0.2 pt).
    New memos: `fidelity-jiangsu` (nested findings replicate on Jiangsu, on one city),
    `policy-tempo` (B7: the tracker is an instrument for burstiness and level timing, not yet
    for cross-area tempo), `bottom-up-channel`, `pair-channels`.
  - **Instrument succession (2026-10-06)** — `instrument_succession(instrument_id,
    successor_id, relation, confidence, evidence, lag_days)` (`scripts/build_instrument_succession.py
    --write --force`, Phase 2b right after doc_identity, ~70s). Relations: superseded_by_stated
    (body 废止 sentences naming the predecessor, 0.95), revised_edition (same title-core minus
    edition markers, 0.85/0.70), renamed (same lead issuer, 0.65), pilot_to_national (the
    successor detector, 0.70-0.93). Strict date ordering → a DAG; one successor per predecessor
    per relation. 12,820 rows; hand-checked 75-85% strict / 85-95% lenient per relation. Why:
    `doc_identity.instrument_id` pools COPIES of one text but not EDITIONS or renamings, which
    is where the pilots-that-scale gap lived (`successor-detector.md`); with this table 11.3% of
    central pilots have a visible successor vs 5.9% by the pilot rule alone.
  - **Nightly validation (2026-10-06)** — `scripts/validate_cascades.py`, Phase 2d after
    the 2c rebuilds: 15 read-only checks (known cascades GD 52d / JS 82d / BJ 116d; 城乡规划法
    inbound band; AI+ implementing vs mentions; proxy-target guards; table sanity; top-5
    rank are formal instruments). The 城乡规划法 check is now TWO checks, `cxgh_edges`
    (`COUNT(*)` edge rows, what `citation_rank` weights) and `cxgh_citers`
    (`COUNT(DISTINCT source_id)`, self-cites dropped, = `doc_inbound.inbound`), because the
    single check printed "inbound citations" while counting edges and that ambiguity caused a
    false alarm on 2026-10-07 (someone compared yesterday's `edges` against today's `inbound`
    and read a healthy +16 as a 235-citer drop). Keep both: the gap between them IS the
    duplicate-edge overhang (251 citers carry 2+ edges), which is now monitored instead of
    invisible. The **AI+ check** was split the same way on 2026-10-07 and for the same reason:
    `aiplus_implementing` counts only the CONFIRMED tiers (`citation` + `title_reissue`, 29 on
    the current build, matching what the AI memos quote), `aiplus_topic_genre` carries a loose
    ceiling for the matcher's "probable-but-unconfirmed" tier, and the source gate compares
    mentions against the confirmed count. It had FAILED at 131 on a rebuild where the cascade
    had not changed: 102 of the 131 were `topic_genre`, which is gated on the anchor's
    `citation_rank >= TOPIC_ANCHOR_CR` and switched on when the mirror fix consolidated AI+
    edges onto the pool's canonical copy. **The general lesson, now three times over: when a
    nightly check fails, first ask whether its metric conflates two things.** Fails loudly
    (exit 1, `🧪 Validation:` Telegram line)
    but never aborts publish. `--set NAME=VALUE` overrides a threshold for testing. Run it
    after ANY resolver/matcher/identity change.
  - **Research memo reader (2026-10-01)** — `/research` (index, curated by the
    volume's structure) and `/research/<slug>` (`web/services/research.py`,
    `templates/research.html`, `research_doc.html`): renders `docs/research/*.md`
    via python-markdown (tables, fenced code; `name.md` cross-links rewritten to
    `/research/<name>`), 1h cache keyed by mtime, slug locked to `^[a-z0-9-]+$`
    inside `docs/research/` (traversal → 404). The research memos are committed
    and deployed; add a new memo by dropping a `.md` in `docs/research/` and
    (optionally) adding its slug to the curated order in `research.py`.
  - **Genre typer** — `scripts/rnd/classification/genre_typer.py` (wired into
    `compute_scores.classify_doc_type`): strips HTML/文号/date tails + adds ~11
    genres; cut `algo_doc_type='other'` from ~50% → ~37.6%.
  - **Docs**: `docs/research/research-agenda.md` (12 tiered research questions +
    operationalizations) and `docs/research/consumption-diffusion.md` (worked
    proof: the 2024–26 以旧换新/提振消费 top-down cascade — GD +20d, ~49d median lag).
  - **Citation-driven crawl queue** — `scripts/rnd/discovery/build_citation_crawl_queue.py`
    + `docs/working/citation-crawl-queue.csv`: ranks the ~219k UNRESOLVED citation
    edges into ~125k distinct missing documents by inbound demand, so the citation
    graph itself is the "what to crawl next" list.
  - **Historical backfill (2026-08-23)** — fleet-fixed 6 crawlers to reach archives
    they under-crawled; recovered **+13,165 docs** (263,805→276,970) and **+16,119
    resolved citations** (→248,115). Per-institution: Beijing 5,721 (Pager pagination
    fix, zcjd archive to 2006), Jiangsu 4,116 (`_get_total_pages` placeholder-cap fix,
    to 2003), MOF 1,880 (财政部文告 gazette walker, 2000–), Chongqing 584 (废止失效
    metadata), Shanghai 156 (沪府办规), Shenzhen 94 (gkmlpt `--search` JSONP index).
    **KEY FINDING — the coverage ceiling is real:** resolution % held ~flat
    (52.05→52.16) despite +16k resolved, because the 13k new docs brought +30k of
    their OWN citations (many dangling). The absolute resolved count, not the %, is
    the honest metric. **(Corrected 2026-10-07, `docs/working/a6-recoverable-head.md`.)**
    Of the four "delisted" head items only 苏住建规〔2011〕4号 is truly gone. 深圳市行政听证办法
    (2006) and 深财规〔2023〕3号 (采购供应商信用信息管理办法) live in the Shenzhen 政府公报
    archive `sz.gov.cn/zfgb/<year>/` — **both are now HELD (2026-10-07)**: `crawlers/sz_gazette.py`
    walks that archive through NFCMS JSON and brought in **11,450 documents spanning **31.4 continuous years, 1995-04 to 2026-09** (corrected 2026-10-07 by `sz-gazette-scoping.md`: the 59 pre-1995 rows sit in retrospective compilation issues printed 2002-03, and the platform's earliest real issue folder is `zfgb/1995/gb68`, so issues 1-67 were never published; dates themselves are sound, 文号 year matches date year on 921 of 930 rows for 1987-2001), including `4952494` 《深圳市行政听证办法》 市政府令第157号 and
    `10832248` 深财规〔2023〕3号, together ~167 citers of demand. **Of the four, only
    苏住建规〔2011〕4号 is still genuinely gone.** (byte-checked; http only, https fails from Python);
    广东省控规条例 was ALREADY HELD under its full title 广东省城市控制性详细规划管理条例 and
    is resolved by a row in `data/instrument_aliases.csv` (340 citers, zero crawl). The
    top-400 unresolved head: 29% confirmed reachable from NYC, 43% likely, 16% is the
    部门规章 wall (ministerial 令 not in gov.cn's library, ministries blocked → HK / 北大法宝),
    10% queue noise (permit names, GB standards). The queue's `coverage_status`/demand are noisy
    (false-`have`, already-resolved, delisted), so per-institution investigation
    (not blind mass-crawl) is required — Chongqing was ~98% already complete.
- **base.fetch() now gunzips** gzip/deflate responses (some gov servers force-gzip).
- **Coverage audit**: `docs/working/coverage.csv` (rebuild via
  `scripts/rnd/discovery/build_coverage_csv.py`) — ~14/34 provincial units crawled;
  the gap is mostly **datacenter-IP-BLOCKED** province portals (the droplet's NYC IP;
  need a residential fetch vantage — browser reads them but the crawler still hits
  the WAF on policy sections). Tier-1 (北上广深) all covered.
- **Source ACCESS map (what we CAN/CANNOT reach)**: `docs/working/source-access-map.md`
  — the authoritative, living reachability record (Tier A crawled / B reachable-new /
  C proxy-gated / D anti-bot / E SPA-search-gated / F dead). **Refresh** it by re-running
  `scripts/rnd/discovery/reachability_sweep.sh <list>` ON THE DROPLET (its NYC IP is the
  vantage). KEY METHOD: HTTP 200 is unreliable for CN gov sites (200 + 160-byte redirect
  stub / ~1KB anti-bot shell) — always byte-check + follow redirects. Reachable-new
  targets found 2026-09: 青海/云南/新疆 provinces + 民委 NEAC (no proxy needed).

## Key Commands

### Crawling
```bash
python3 -m crawlers.gkmlpt --list-sites        # Show all gkmlpt sites
python3 -m crawlers.gkmlpt --site sz            # Crawl one site
python3 -m crawlers.gkmlpt --backfill-bodies    # Backfill missing body text
python3 -m crawlers.gkmlpt --sync               # Incremental sync (detect new/changed)
python3 -m crawlers.gkmlpt --stats              # Show DB stats

python3 -m crawlers.ndrc                        # NDRC crawler
python3 -m crawlers.gov                         # State Council crawler
python3 -m crawlers.mof                         # Ministry of Finance
python3 -m crawlers.mee                         # Ministry of Ecology & Environment

python3 -m crawlers.beijing                     # Beijing (5 sections)
python3 -m crawlers.shanghai                    # Shanghai (6 sections, year archives)
python3 -m crawlers.jiangsu                     # Jiangsu (jpage API)
python3 -m crawlers.zhejiang                    # Zhejiang (dept subdomains, IPv6)
python3 -m crawlers.zhejiang --dept fzggw       # One department only
python3 -m crawlers.chongqing                   # Chongqing (3 sections, 697 docs)
python3 -m crawlers.wuhan                       # Wuhan (5 sections + AI portal)
python3 -m crawlers.nda                         # National Data Administration (5 sections, 379 docs)
python3 -m crawlers.sic                         # State Information Center (1,117 docs)
python3 -m crawlers.ipc_court                   # Supreme Court IP Tribunal (~75 recent, --deep for full 5k)
python3 -m crawlers.spp                          # Supreme People's Procuratorate 最高检 (法律法规库, ~40 docs)
python3 -m crawlers.csrc                         # Securities regulator 证监会 (政策法规库, ~150 docs)
python3 -m crawlers.chinatax                     # Tax admin 税务总局 政策法规库 (~9,900 docs; C3VK cookie + JSON API)
python3 -m crawlers.chinatax --max-docs 500      # Bounded backfill chunk
python3 -m crawlers.pbc                          # People's Bank of China 央行 条法司 (规范性文件+部门规章)
python3 -m crawlers.trs --site nhsa             # TRS WCM central bodies (医保局 NHSA, 广电 NRTA)
python3 -m crawlers.trs --list-sites            # Generic TRS "recordset" crawler (encrypted-param dialect)
python3 -m crawlers.govcms --list-sites         # Generic gov "t-date list" crawler (central ministries)
python3 -m crawlers.govcms --site mwr           # 水利部 (also: provinces liaoning/xizang/ningxia/qingdao t-date, cnipa 知识产权局 /art/, dangyuan 共产党员网 ARTI dialect)
python3 -m crawlers.govcms --group dept       # Crawl all department-tier + district sites (group=dept, ~140 sites) in one pass
# Dialects (crawlers/govcms.py): (A) t-date /tYYYYMMDD_ID (B) /art/ (C) content_N/c_N
#   (D) NEA hex/c.html (E) web-idx (辽宁) (F) ARTI (12371) (G) numid (H) tsid (I) hexmon
#   (J) pnidpv — G-J added for Beijing districts (通州/大兴/平谷/门头沟/西城).
# Dept families (group=dept): xz_/nx_/fj_/cq_ = 117 dept sites; bjd_/njd_/whd_/cqd_ = 22 districts.
# NOTE base.fetch() gunzips gzip/deflate responses (CNIPA & others force-gzip).
python3 -m crawlers.govcms --site mwr --discover # Map a site's t-date sub-sections (config aid)
python3 -m crawlers.tsinghua_aiig               # Tsinghua AI Governance Institute

python3 -m crawlers.moe                         # Ministry of Education (7 sections, WAS search system)
python3 -m crawlers.moe --section a16            # S&T Dept only (AI+Education, ~344 docs)
python3 -m crawlers.npc                          # National Laws Database (29k laws, metadata only)

python3 -m crawlers.sz_invest                   # Shenzhen non-gkmlpt (investment news, DRC, Longgang AI)
python3 -m crawlers.sz_invest --section fgw_xwdt  # DRC news only
python3 -m crawlers.sz_invest --section lg_ai     # Longgang AI/robotics only

python3 -m crawlers.stdaily                     # Science & Technology Daily (MOST newspaper, sitemap-based)
python3 -m crawlers.stdaily --deep              # Sitemap + homepage discovery
python3 -m crawlers.guancha                     # Guancha / Observer Network (homepage only, ~185 articles)
python3 -m crawlers.guancha --deep              # + section pages + all columnists (~400 articles)

python3 -m crawlers.elsewhere                    # elsewhere.news 别处 (VC/AI-tech news; Next.js+Supabase, HTML-scraped)
python3 -m crawlers.chinalawtranslate           # English translations of Chinese laws (~1,100 posts via WP API)
python3 -m crawlers.chinalawtranslate --category internet  # One category only
python3 scripts/match_clt_translations.py       # Link CLT posts to native docs by source URL
```

### English Translations
- CLT posts are stored under `site_key=chinalawtranslate`. Each post's `relation`
  field holds `cn_source=<original CN URL>;lang_ratio=<0-1>` so the matcher can
  link them to native CAC/SC/MIIT docs. About 67/466 source URLs match a native
  doc; URL normalization strips http/https since CLT mostly uses http while
  native crawlers use https.
- WP API quirk: CloudFlare 502s on `per_page=100` requests that include the
  `content` field. Drop to per_page=20 and use browser-shaped headers.

### Classification (DeepSeek API)
```bash
export DEEPSEEK_API_KEY="sk-..."
python3 scripts/classify_documents.py --dry-run --limit 5   # Test
python3 scripts/classify_documents.py --concurrency 2       # Full run (~$0.50/1k docs)
```

### Algorithmic Scoring (no LLM needed)
```bash
python3 scripts/compute_scores.py               # Compute citation_rank, algo_doc_type, ai_relevance for all docs
python3 scripts/compute_scores.py --dry-run     # Preview without saving
python3 scripts/compute_scores.py --stats       # Show score distributions
```

### Body Text Backfill (from saved HTML)
```bash
python3 scripts/backfill_from_html.py            # Re-extract body text from saved raw HTML
python3 scripts/backfill_from_html.py --site most  # One site only
python3 scripts/backfill_from_html.py --dry-run  # Preview
```

### PDF Attachment Extraction
```bash
python3 scripts/extract_pdf_text.py              # Extract text from PDF attachments
python3 scripts/extract_pdf_text.py --site gd    # One site only
python3 scripts/extract_pdf_text.py --dry-run    # Preview
```

### Separate DB Workflow (avoid lock contention)
```bash
python3 -m crawlers.beijing --db documents_new.db   # Write to separate DB
python3 scripts/merge_db.py documents_new.db         # Merge into documents.db
```

### Web App (local)
```bash
uvicorn web.app:app --reload --port 8001  # Local dev (SQLite, read-only)
# The app is SQLite-only (Postgres/Railway support removed June 2026). It opens
# documents.db read-only (?mode=ro) — safe to run alongside crawlers (WAL mode).
# UI redesigned July 2026 to an "Archive/Record" aesthetic — the design system
# lives in web/templates/base.html (IBM Plex + Noto Serif SC, paper/teal/oxblood,
# ruled catalog tables). The former Inbox/Changes/Coverage pages are consolidated
# into /admin (old routes still work, off the primary nav). In production uvicorn
# serves on port 8001 behind nginx.
# Override the DB path with SQLITE_PATH if needed.
```

**Search = FTS5 trigram index** (`doc_search`, built by `scripts/build_search_index.py`).
Search was a `LIKE '%q%'` full scan over ~240k rows run twice (rows+COUNT), ~6.5s each;
now an indexed substring lookup (~0.1s warm). Trigram tokenizer handles Chinese (no
word boundaries). Three triggers keep it synced as crawlers write — new docs are
searchable immediately, no nightly rebuild. `search_documents()` uses `MATCH` for
queries ≥3 chars (trigram min), else falls back to LIKE. **The index lives inside
documents.db; if the DB is ever rebuilt/restored, re-run `python3 scripts/build_search_index.py`
once (~22 min, one-time).** Cold first-access to a common term after a rebuild can be
slow on the 2GB-RAM droplet (page cache) — it warms quickly.

**Relevance ranking = word-segmented BM25** (`doc_search_seg`, built by
`scripts/build_search_index_seg.py`; requires `jieba`). The trigram index matches
Chinese substrings but `bm25()` over trigrams is noise, so search used to fall back
to date order. `doc_search_seg` is a second FTS5 index over jieba-**segmented** words
(contentless, `unicode61`), letting `search_documents()` rank by real `bm25()` with a
title boost + recency tiebreak. Path chain: segmented-BM25 → trigram substring → LIKE
(each falls through on 0 hits, so recall never regresses; if `doc_search_seg` is absent
the code behaves exactly as the old trigram path). One-time build ~1h, incremental
re-runs are cheap (only new ids — ~8s for a day's docs). **Wired into `daily_sync.sh`
Phase 2c** (after all writers, before the Phase 3 WAL checkpoint) so BM25 stays fresh
and the WAL never bloats (segmentation is Python, so it can't be a SQL trigger like
`doc_search`; the builder itself ends with `wal_checkpoint(TRUNCATE)` on success — a
KILLED build skips that and leaves a big WAL, so a manual run must be allowed to finish
or be followed by a checkpoint). See `docs/research/search-primer.md` + `search-proposal.md`.

### Daily Crawl + Sync (runs ON the droplet via cron)
```bash
# Automated: droplet cron runs daily_sync.sh at 06:00 UTC.
#   crontab on droplet:
#     PATH=/root/china-governance/.venv/bin:/usr/local/bin:/usr/bin:/bin
#     0 6 * * * cd /root/china-governance && ./scripts/daily_sync.sh >> logs/cron.log 2>&1

# What daily_sync.sh does (on the droplet):
# 0. git pull (auto-updates code on non-Mac hosts)
# 1. Crawls all sites (gkmlpt, central ministries, provinces, media)
# 2. Backfills body text + computes algorithmic scores
# 3. Classifies unclassified docs via DeepSeek (Phase 2)
# 4. Phase 3: WAL checkpoint + restart web app IN PLACE (no rsync — it's the
#    source of truth). Detected via .is_production_droplet marker.
# 5. Sends Telegram report

# Run/inspect manually on the droplet:
ssh root@104.236.88.45 'cd /root/china-governance && \
  PATH=/root/china-governance/.venv/bin:$PATH nohup ./scripts/daily_sync.sh \
  > logs/manual_$(date +%Y%m%d_%H%M).log 2>&1 &'
ssh root@104.236.88.45 'tail -f /root/china-governance/logs/daily-*.log'

# Lock: /tmp/china-governance-daily-sync.lock.d (mkdir-based). If a run is
# killed -9, the lock dir can go stale — rmdir it manually before re-running.
```

### Deploy to Production
```bash
# Production = the droplet (104.236.88.45, NYC3, 2 vCPU / 4GB).
# The droplet IS the source of truth, so "deploy" is mostly just code + restart.

# Deploy CODE changes (the normal case):
ssh root@104.236.88.45 'cd /root/china-governance && git pull && systemctl restart chinagovernance'
# (daily_sync.sh also git-pulls automatically at the start of each run.)

# Push DATA up from the Mac (RARE — only if you crawled/built locally, e.g.
# a fresh officials.db). This OVERWRITES the droplet's live file, so be sure
# the Mac copy is actually newer:
sqlite3 documents.db "PRAGMA wal_checkpoint(TRUNCATE);"  # Flush WAL first!
rsync -az documents.db root@104.236.88.45:/root/china-governance/documents.db
ssh root@104.236.88.45 'systemctl restart chinagovernance'
# NOTE: macOS ships rsync 2.6.9 — do NOT use --info=progress2 (unsupported,
# silently prints usage and transfers nothing). Use --progress or --stats.

# Verify production:
curl -s "https://www.chinagovernance.com/api/v1/stats" | python3 -m json.tool
```

## Scripts Layout (reorganized July 2026)

- **`scripts/*.py` / `*.sh` (flat)** = ACTIVE — wired into `daily_sync.sh` or a
  documented command here (`daily_sync.sh`, `backfill_from_html.py`,
  `compute_scores.py`, `classify_documents.py`, `extract_pdf_text.py`,
  `merge_db.py`, `match_clt_translations.py`, + officials.db builders
  `compute_overlaps.py` / `fix_baike_collisions.py`).
- **`scripts/rnd/<theme>/`** = R&D / one-off tools, NOT in the pipeline (citations,
  references, translation, subsidies, discovery, backfill, eval, crawl-runners).
  These resolve the repo root via `Path(__file__).parents[3]`.
- **`scripts/README.md`** is the index (ACTIVE vs R&D + what each does).
- `analyze.py` (repo root) is a shared analysis library (citation regexes), used
  by tests + `rnd/citations/`. Not a runnable script.

## Architecture

**As of June 2026 the droplet is the source of truth.** The pipeline was moved
off the Mac because macOS-specific failures (launchd not firing when the Mac
slept, an iCloud Desktop-sync `.pyc` deadlock, and a nightly 2GB rsync across
the Pacific) kept breaking the daily runs. See `docs/` history / git log around
the move for the full diagnosis.

```
Droplet (104.236.88.45, NYC3, 2 vCPU / 4GB RAM / 2GB swap):
   crawlers/ → documents.db (SQLite, SOURCE OF TRUTH) → uvicorn (read-only ?mode=ro)
   cron (06:00 UTC) → scripts/daily_sync.sh → crawl + classify + publish in place
   nginx + certbot (HTTPS) ───────────────────────────────────────┘

Mac (dev only, OPTIONAL): git push code; pull a DB copy when developing locally.
```

- **The droplet's `documents.db` is the source of truth.** Crawlers run *on the
  droplet* (via cron) and write to the same file the web app reads. No rsync in
  the steady state — "publish" is just a local WAL checkpoint + uvicorn restart.
- **`daily_sync.sh` detects which machine it is** via a `.is_production_droplet`
  marker file (gitignored, present only on the droplet):
  - On the droplet: Phase 3 checkpoints the WAL and restarts the web app locally.
    It must NOT rsync to itself (would corrupt the live file).
  - On the Mac (no marker): Phase 3 rsyncs *up to* the droplet, as the old flow
    did. This path is now a manual fallback only — the Mac launchd job is
    disabled (`~/Library/LaunchAgents/com.claude.china-governance-sync.plist.disabled`).
- **Cron on the droplet** runs `daily_sync.sh` at 06:00 UTC. The crontab sets
  `PATH=/root/china-governance/.venv/bin:...` so bare `python3` resolves to the
  venv (where crawler deps live). An atomic `mkdir` lock prevents overlapping
  runs (a classification drain can exceed 24h; the next cron skips while locked).
- **Env on the droplet**: `/root/china-governance/.env` holds the keys (chmod
  600). `DATABASE_URL` is intentionally EMPTY there so the web app uses local
  SQLite. `daily_sync.sh` does `set -a; source .env; set +a` so child processes
  (crawlers, classifier) inherit `DEEPSEEK_API_KEY`.
- Web app caches heavy queries (stats, sites, categories) for 1 hour in-memory;
  the Phase 3 restart clears that cache so new docs appear.
- SSL via Let's Encrypt (certbot auto-renews). Expires July 4, 2026.
- The Mac's local `documents.db` is now a stale snapshot. To develop locally,
  pull fresh: `rsync -az root@104.236.88.45:/root/china-governance/documents.db ./`
- **Railway Postgres removed (June 2026).** The web app is SQLite-only; all the
  Postgres sync scripts and the asyncpg dependency were deleted. NOTE: the
  Railway DB credential was committed to this PUBLIC repo's history (in the old
  `scripts/setup_droplet.sh`), so it must be considered compromised — the Railway
  project should be deleted/rotated to invalidate it.

### Off-droplet backups (DigitalOcean Spaces)

The droplet's `documents.db` is the ONLY full copy of the corpus (the Mac copy
was deleted; `backups/*.csv` are recovery *manifests*, not the data). To remove
that single point of failure, `daily_sync.sh` Phase 3c backs both DBs up
off-droplet after each publish:

- **`scripts/backup_db.py`** — `VACUUM INTO` (consistent snapshot, not a torn
  `cp` of the live WAL DB) → gzip → upload to **DO Spaces** (`china-governance-backups`,
  nyc3, S3-compatible). Backs up BOTH `documents.db` (~4GB → ~1.9GB gz) and
  `officials.db` (the hardest to reproduce — needs the Mac Excel seed).
- **Retention:** `daily/` keeps 7, `weekly/` keeps 4 (Monday promotes to weekly).
  Pruning needs the Spaces key to have **Delete** perm (it's a Limited-Access key
  scoped to this one bucket).
- **Creds:** `SPACES_KEY` / `SPACES_SECRET` in the droplet `.env` (chmod 600);
  `SPACES_REGION` (default nyc3) / `SPACES_BUCKET` (default `china-governance-backups`)
  optional. Phase 3c SKIPS cleanly if the keys are absent (so a Mac run is a no-op).
- **Report:** the nightly Telegram report shows `Backup → Spaces: true/false`.
- **Restore:** download `daily/documents-YYYYMMDD.db.gz` → `gunzip` → it's a plain
  SQLite file. Point `SQLITE_PATH` at it, or replace `documents.db` + restart.
  Verified 2026-07-13: a downloaded backup passes `PRAGMA quick_check` and matches
  the live row count.
- Manual run: `set -a; source .env; set +a; python3 scripts/backup_db.py`
  (`--dry-run` = VACUUM+gzip locally, no upload; `--db documents.db` = one DB).

### officials.db (separate dataset — Officials page)

`officials.db` (~250MB, 2,181 officials) is a SEPARATE SQLite file the web app
opens read-only alongside `documents.db` (`web/database.py:OFFICIALS_PATH`).
Tables: `officials`, `career_records`, `overlaps`.

- **Built by `crawlers/baike.py`** — crawls Baidu Baike (baike.baidu.com) bios
  of CPC Central Committee members, extracts career text.
  - `python3 -m crawlers.baike` (crawl) → `--parse` (extract career_records)
  - `scripts/compute_overlaps.py` builds the `overlaps` table
  - `scripts/fix_baike_collisions.py` fixes name-collision mismatches
- **Seed input**: `~/Downloads/CPC_Elite_Leadership_Database.xlsx` (manual,
  Mac-local, NOT in the repo). The crawler reads this list to know whom to crawl.
- **NOT part of the daily pipeline** — `daily_sync.sh` only checkpoints it, never
  rebuilds it. The live copy is a static April-7 snapshot. To refresh: rebuild on
  the Mac (needs the Excel seed), then manually push:
  `rsync -az officials.db root@104.236.88.45:/root/china-governance/officials.db`
  and restart the web app.

### Scoring Pipeline (no LLM)

Three algorithmic scores computed locally via `scripts/compute_scores.py`:
- **citation_rank**: Weighted inbound citation count (central=3x, provincial=2x, municipal=1.5x). PageRank-like.
- **algo_doc_type**: 19 document types from title regex (regulation, policy_issuance, action_plan, subsidy, explainer, etc.)
- **ai_relevance**: 0.0-1.0 keyword density score. Weighted terms (人工智能=10, 大模型=9, 算力=7...) with diversity bonus. Normalized by doc length.

Browse page supports filtering by doc type, AI relevance threshold, and sorting by citation rank or AI relevance.
- **Raw inbound beside rank (2026-10-06):** `doc_inbound(doc_id PK, inbound, edges)` is
  built by `scripts/build_site_stats.py` (one `GROUP BY target_id` pass over `citations`,
  ~1s, nightly Phase 2c after the citations rebuild); `inbound` = distinct citing docs,
  self-cites dropped. Shown next to `citation_rank` on browse/document/lens/annotations
  ("3307.5 · 2143 cited"), `?sort=inbound` on browse and `/api/v1/documents?sort=`. Why:
  the 3x-central weighting in `citation_rank` still shapes the top-30 (19/30 overlap with
  the raw ranking, `docs/research/citation-network-structure.md`); readers should see both.

### Classification (DeepSeek API)

Documents are classified via DeepSeek API (`scripts/classify_documents.py`) — adds English title, summary, doc_type, policy_significance, references_json. Cost: ~$0.50/1k docs, concurrency 2 max (higher silently rate-limits with empty responses, not 429s).

**(2026-10-07) A THIRD of all classification calls were failing silently, and had been since
the 07-25 `deepseek-v4-flash` migration** (20-37% err in every nightly log back through
mid-September). Root cause, proven by probe in `docs/working/qa-classification-failures.md`:
v4-flash is a **reasoning** model and bills reasoning tokens against `max_tokens`, which was
2,000 — so 19 of 20 sampled calls returned `finish_reason="length"` with
`reasoning_tokens == completion_tokens == 2000` and **empty content**. It was a coin flip on
reasoning length, not a document property: documents that succeeded one night failed 9/10 on
re-send, and body length/site/script do not discriminate (the prompt hard-truncates bodies to
1,500 chars, so context overflow was never possible). The code then treated empty content as a
content filter and skipped it silently ("likely content filter. Skip silently."), leaving
`classified_at = ''` so the document was re-sent every night forever. **Fixed (`1511b81`):**
`max_tokens` 2,000 → **12,000** with one 24,000 retry on `finish_reason="length"`; every
failure now carries a reason (`empty_content_length`, `content_risk`, `json_unsalvageable`,
`http_error`, `timeout`, `rate_limit_exhausted`), logged at WARNING with the doc id and tallied
in the progress line; failures persist to **`classify_failures(doc_id, reason, attempts,
first_seen, last_seen)`** (a side table, not a `documents` column — see the compute_scores
overflow-page lesson below), where `content_risk` is terminal and `attempts >= 3` is skipped
unless `--retry-failed`. `--init-schema` creates the table; `--dry-run` now opens the DB
read-only. Validated live: 4 of 5 previously-failing documents classified on the FIRST call at
12,000. Cost: +$0.0031/doc (~+$225/yr of productive spend, replacing ~$160/yr of pure waste);
`max_tokens` is a ceiling, so the ~70% of documents that already finish under 2,000 cost the
same as before. A one-off `--retry-failed` backfill of the ~1,864 unclassified docs is ~$11. As of June 2026 the droplet's nightly `daily_sync.sh` Phase 2 runs this UNBOUNDED (no `--limit`), so it drains the full backlog (~156k docs, ~$78, ~40h) on the first reliable run, then only touches new docs. The `mkdir` lock keeps the next day's cron from piling a second classifier on top.

## A recurring bug shape: a hand-maintained table silently bounds a measurement

Five times now a result has turned out to describe one of our own lookup tables rather than the
corpus. The table is never wrong about what it contains; it is wrong about what it OMITS, and the
omission is invisible because the code returns a clean answer either way.

| table | what it omitted | the measurement it silently bounded |
|---|---|---|
| `data/source_ontology.yaml` | 231 of 510 site keys | "Other / unclassified" held 22k docs and the exclude-news filter missed them (fixed 2026-10-07 with an `admin_level` fallback) |
| `geo.DISTRICT_CITY` | every Wuxi division | 1,163 Wuxi district docs had NO province, so the same-province gate dropped them from every provincial comparison |
| the 文号 registry (via `AMBIGUOUS_DOCNUM_PREFIXES`) | 无锡 has no entry at all | `惠府` resolved to 惠州市, putting 22 Wuxi docs in Guangdong |
| `build_doc_identity.KNOWN_LOCALITIES` (54 names, seeded from `_PROV_MUNI` + the 文号 registry) | `无锡市`, because Wuxi has no 文号 entry | `localize()` cannot place a Wuxi title, so `localized_of` fires on **2** Wuxi pairs against **44** Suzhou — and `pair-channels.md`'s renaming-channel floor is therefore a floor on the TABLE, not on the corpus (found 2026-10-08) |
| `citations` title index / `_best_core` floors | short folded titles | see the length-floor section below |

**Rule:** when a per-jurisdiction or per-site number looks like a finding, check whether the
jurisdiction is in every table the path touches before believing it. The tell is an ordering that
reverses when you change denominator: Wuxi titles carry their city name MORE often than Suzhou's
(43.2% vs 54.1% lack it) yet Wuxi's renaming channel fires 20x less, which is impossible as a fact
about Wuxi and obvious as a fact about a 54-name set. Prefer deriving these tables from a table
that is already complete (`CITY_PROVINCE`, `sites.admin_level`) over hand-maintaining a second one,
and where a hand list must exist, make the unmapped case return None loudly rather than guessing.

## A recurring bug shape: length floors measured on a NORMALIZED string

Four separate bugs this project has shipped are the same mistake (the fourth was predicted
here before it was found, which is the point of naming a pattern): **a minimum-length guard applied to a string AFTER normalization stripped
characters from it.** Chinese statute names are the trap, because `中华人民共和国` is 7 characters
and every normalizer folds it away.

| where | the floor | what it silently refused |
|---|---|---|
| `extract_citations.TitleMatcher` exact tier | `len(ref) >= 8` | 城乡规划法 (5 after folding) never got an exact match, so containment won and credited the law's 2,139 citations to a provincial doc that merely embedded its name (the Oct 2026 "proxy target" bug) |
| `extract_citations` title index | `WHERE LENGTH(title) >= 8` | 1,661 held titles of 5-7 chars were never candidates at all (广东省公路条例 held 0 citers while sitting in the corpus 4 times) |
| `build_doc_identity._best_core` | `KEY_MIN = 6` on the folded core | every national statute got NO `instrument_key`, so all copies stayed `instrument_role='unique'` and nothing pooled (found 2026-10-07) |
| `citation-network-structure.md` Appendix pooling (analysis code, not production) | a 5-char floor on the folded title | 民法典 and 预算法 fold to 3 characters once 中华人民共和国 is stripped, so the memo's own pooled authority statistics never pooled them (found 2026-10-08 during the A1 re-base). Note the resolver's title index is safe here because its `LENGTH(title) >= 5` floor reads the RAW title, 10 characters for 中华人民共和国民法典 |

**Rule:** measure a length floor on the string the user wrote, not on the string your
normalizer produced; or exempt the shapes you know fold short (`法|法典|条例|修正案`) with an
explicit gate. If you add such a gate, check what else it admits — the 2026-10-07 fix had to
exclude `中华人民共和国国务院令` because 20 *unrelated* State Council orders share that one title,
so the 令/声明 is the vehicle, not a name.

A second, related lesson from the same fix: a window measured from "the latest copy of any
level" lets a low-level repost **bridge** two editions. A 北京市统计局 repost of 监察法 put the
2024 amendment 212 days after the 2018 edition's tail and merged them. Measure an edition window
from its **anchor** (the latest copy at or above the edition's own level): a bureau's repost
cannot open an edition, so it must not extend one.

## SQLite Concurrency Rules

- **WAL mode** is enabled. Multiple readers + 1 writer works fine.
- **`busy_timeout=30000`** (30s) is set in `crawlers/base.py`.
- **Writer count is not the limit — transaction HOLD TIME is.** Two writers are
  fine only if both commit quickly. A crawler that commits every 20–50 docs with
  multi-second HTTP fetches between rows holds the write lock for minutes, and
  `busy_timeout=30000` is then just a 30-second delay before `database is locked`
  (measured 2026-10-07: 9/13 `gkmlpt --backfill-bodies` runs died on their UPDATE
  while `crawlers.gov --library --deep` was writing — after paying for the fetch).
  So: **do not start a second writer against `documents.db` while a long-running
  deep crawl or the nightly is in flight** — use the `--db documents_new.db` +
  `merge_db.py` workflow instead. Any loop that writes rows it paid network time
  to obtain MUST use `base.write_with_retry` / `commit_with_retry` (bounded
  backoff → log → skip the row), commit incrementally, and exit non-zero when
  anything was skipped, so a wrapper `for` loop cannot swallow the failure.
  `busy_timeout` itself was audited on every connection in `crawlers/` and
  `scripts/` and was never the gap; `tests/test_write_contention.py` now has a
  static scan that fails if a new `sqlite3.connect` appears without it.
- Web app opens DB read-only (`?mode=ro`) — never blocks crawlers.
- **Partial index gotcha**: `idx_documents_url` is defined as `WHERE url != ''`. SQLite will NOT use this index for queries that omit that predicate. Always include `AND url != ''` in WHERE clauses that filter by URL, or expect a full table scan.

## Adding a New gkmlpt Site

gkmlpt is Guangdong-only. Just add to the `SITES` dict in `crawlers/gkmlpt.py`:
```python
"newcity": {
    "name": "City Name",
    "base_url": "http://www.example.gov.cn",
    "admin_level": "municipal",  # or "district", "department"
},
```
Then: `python3 -m crawlers.gkmlpt --site newcity`

## Adding a New Ministry/Province

Requires a new crawler module. See `crawlers/mof.py` or `crawlers/mee.py` as templates.
Guide: `docs/implementation/new-province-crawler-guide.md`

## Open Questions / Unknowns

> **Practice:** whenever a question comes up that we can't answer from the code
> or current knowledge, log it here (with the date and what we *do* know). When
> it gets resolved, move the answer into the relevant section above and delete
> the entry. This is the project's running "things we're unsure about" list.

- **(mostly RESOLVED 2026-07) Droplet reachability of `gd`/`huizhou`/`yangjiang`.**
  `gd.gov.cn` IS reachable from the NYC droplet (HTTP 200) and is already covered
  by nightly `gkmlpt --sync` (which iterates ALL `SITES`, applying the browser UA
  for `gd`). **`huizhou` + `yangjiang` are hard-blocked from the droplet's
  DigitalOcean IP** (connection refused / blackholed, even with browser UA +
  https) — classic "CN gov site blocks datacenter IPs, allows residential." Only
  a residential IP could reach them. The Mac's nightly cron was BROKEN anyway
  (relative-path bug → hadn't run since ~May 26) and is being removed, so the
  `IS_MAC` block in `daily_sync.sh` is now effectively dead. **DECISION NEEDED:**
  accept the huizhou/yangjiang gap, crawl them occasionally from a residential IP,
  or proxy. (See `docs/working/todos.md` §1a.)
- **(RESOLVED 2026-07) Citations rebuilt nightly** — `extract_citations.py` is now
  wired into `daily_sync.sh` Phase 2b (after classification), so `/chain`, the
  network, "cited by", and `citation_rank` stay current. Pure CPU, ~$0.
- **(RESOLVED 2026-07-14) Citation rebuild sped up ~49× via an indexed resolver.**
  `extract_citations.py`'s named/LLM resolution WAS O(docs × titles) — each `《》`/LLM
  ref substring-scanned ALL ~200k titles — so at ~208k docs a full rebuild took **4.4h**
  and silently blew past the Phase 2b timeout, leaving `citations`/`citation_rank`
  stale. Fixed with `TitleMatcher` (n-gram inverted index + substring-gen): a rebuild
  now runs in **~5.4 min** with **byte-identical resolved counts** (validated on the
  live corpus: formal 24,327 / named 86,830 / llm 44,896). Phase 2b timeout left at
  10800s as generous headroom. Parity-tested (0 mismatches / 6k synthetic queries).
  **(2026-08-10 recall upgrade — see coverage-tracker §14)** the matcher now
  NORMALIZES titles + 文号 (folds `《》`/brackets/whitespace, strips `中华人民共和国`)
  on both sides, so the resolved counts intentionally went UP (named→114,966,
  llm→66,423, formal→29,545; docs-with-inbound ~12,102→35,880) — the old
  "byte-identical" baseline no longer applies.
  **(2026-08-22 round-2 + DIAGNOSIS)** Citation resolution sits at a **~51%
  ceiling that is COVERAGE-bound, not matching-bound.** A full audit of the ~219k
  unresolved edges found re-running the resolver on them resolves **0** — the
  overwhelming majority are genuine coverage gaps (the cited doc isn't in the
  corpus: other-city municipal docs, 1990s–2000s historical docs, never-crawled
  central docs, foreign laws, and non-document refs like "中央经济工作会议").
  Resolution can't exceed ~52–54% by matching alone; **it only rises by ingesting
  the cited documents** — i.e. the unresolved refs are a prioritized crawl shopping
  list (ties into the coverage campaign). A conservative round-2 matcher fix
  (`_agg_docnum`/`_core_docnum` 文号 folding + `resolve_ref` 《》 title-core
  fallback, length-gated ≥10, zero-regression) recovers the fixable minority:
  **+2,803 edges → 51.5%**. Applied by nightly Phase 2b.
  **(2026-10-01 proxy-target fix.)** The resolver was crediting citations of a national law
  to whichever corpus doc EMBEDS the law's name (河南省实施《城乡规划法》办法 held 2,139
  inbound + the corpus-max `citation_rank`; the law itself held 0) because `TitleMatcher`
  gated its exact tier on `len(ref) >= 8` and short law names (城乡规划法 = 5 chars) never
  got an exact chance. Fix (commits `cd42903`, `c979a82`): exact normalized-title / title-
  core matches win before any containment; mirror tie-break by level then id; 1-tuple caller
  compat. `tests/test_citation_proxy_fix.py` (6 cases). Resolved edges 279,409 → **287,607**
  (+8,198, no loss); top-30 by `citation_rank` is now framework laws. Earlier "byte-identical
  resolved counts" baselines are superseded. NOTE: ~2% of unresolved
  named refs are **character-scrambled inside `body_text_cn`** (anti-scraping
  artifact) — unrecoverable without re-extracting those bodies.
- **(RESOLVED 2026-10-07) Crawler timeouts / why Phase 1 takes four hours.** Measured
  per-crawler over 11 nightlies in `docs/working/nightly-phase1-timing.md`. The 2026-07
  guess above was wrong on the list: only **4** crawlers hit the 1800s cap, not 11, and 7
  of the 11 it named now finish in under 70s. The real shape: Phase 1 runs **240-271 min
  to add ~250 documents**, and **15 crawlers whose MEDIAN new-doc yield is zero account for
  196 of the 252 median minutes**. Worst: `zhejiang` 1800s capped 7/11 nights for ZERO rows
  in 11 nights (nothing paginates from a US IP); `govcms --group dept` capped 11/11 while
  reaching only 160 of 232 sites; `beijing` capped 11/11, killed at 2,640/6,821 items, 17
  new docs in 10 nights; `gkmlpt --sync` capped 11/11, reaching 4 of 63 sites; `jiangsu`
  1276s walking 262 pages for 3 new docs. Phase 1 is purely network-bound (load average
  0.17 on 2 vCPU). Compounding it, these crawlers skip only on "already stored WITH a
  body", so 1,628 `bj` + 5,388 `miit` + 1,022 `suzhou` rows are re-fetched every night
  forever (miit's are anti-bot stubs that can never gain a body from NYC).
  **Shipped (`36fba8a`):** `run_crawler_t <seconds>` per-crawler caps (`run_crawler` is
  that with the 1800s default), `run_weekly <dow>` for the zero-yield walkers one weekday
  each (sic, ipc_court, chongqing, wuhan, most, hangzhou), and `zhejiang` off the nightly
  path to a Monday probe under a 600s cap. Central ministries (gov/ndrc/mof/mee/cac/miit)
  deliberately stay NIGHTLY: the product is a daily tracker, so their cost belongs to an
  early-exit fix, not to cadence. **Still open** (each needs its named verification first):
  skip-on-presence for `beijing`, the `gkmlpt` per-site diff scope, a `jiangsu` early exit
  gated on confirming listing pages are reverse-chronological, dept-group rotation in 3
  chunks (which would *increase* coverage), and 2-wide parallelism (bounded by the
  2-writer SQLite rule). Together those would take Phase 1 to roughly 100 min.
- **(2026-06) Is DeepSeek `references_json` worth the cost over regex refs?**
  We have regex-extracted `references_source` on ~133k docs (`regex_v1`). A
  sample comparison found ~72% overlap with DeepSeek's refs. Open question
  whether the DeepSeek pass adds enough citation quality to justify classifying
  the long tail for references specifically (vs. other classification fields).

## Known Issues

- **(2026-08-11) Bot/scraper overload can hang the site ("loads forever").** The app
  runs `uvicorn --workers 2` on a 2-vCPU box. A scraper walking `/raw_html/` (the
  ~252k-page raw-HTML mirror) sequentially by id — plus a `57.141.20.0/24` cluster
  spreading requests across the subnet to dodge per-IP limits — saturated both workers,
  so real requests (e.g. a `/browse?site=X` click) queued and timed out. The DB/queries
  are fine (site filter is 0.02s via `idx_documents_site`); it's pure serving capacity.
  **Mitigations in place:** nginx per-IP rate limiting (`/etc/nginx/conf.d/ratelimit.conf`
  — `perip` 10r/s, `rawhtml` 2r/s, a `harvester` geo-zone throttling known bulk
  sources to 1r/s; 429 on exceed) wired into `location /` and `location /raw_html/`;
  `robots.txt` disallows `/raw_html`, `/cms_files`, `/api`. To lift/adjust a throttle,
  edit `ratelimit.conf` (the `geo $harvester` list) + `nginx -t && systemctl reload nginx`.
  GOTCHA: nginx (`www-data`) can't traverse into `/root`, so anything it serves by
  `alias` from `/root/china-governance/...` returns **403** — `robots.txt` is therefore
  served from `/var/www/robots.txt` (a copy; re-copy from `web/static/robots.txt` after
  editing). The same 403 affects the `location /static/` alias (pre-existing; assets
  come from CDN so it doesn't break rendering). Right after an app restart the 1h query
  cache is COLD, so the first hit to heavy endpoints (/network, /officials, the sites
  aggregate) is slow and — under bot load — can block a worker until warm; this looks
  like a hang but self-resolves. If it recurs hard, consider `--workers 3`.
- **(2026-09-28 — MEASURED root cause of "loads forever", supersedes the bot framing
  above for the current site.)** Two independent profiles (`docs/working/perf-diagnosis.md`,
  `perf-endpoint-baseline.md`, `perf-query-profile.md`) found the "loads forever" is NOT
  bot load (Basic Auth now bounces bots: ~2,500 × 401/day, ~0 reach the app). It is
  `get_sites` (`web/services/documents.py:366`): `sites LEFT JOIN documents GROUP BY
  site_key` with `SUM(CASE WHEN body_text_cn != '')` makes SQLite build an AUTOMATIC
  COVERING INDEX pulling `body_text_cn` for all 313k rows (~4GB overflow through the 32MB
  cache), so `/` is **~72s cold / ~30ms warm** and does NOT warm up. The 1h cache is
  **per-worker on 2 workers**, so it recomputes per worker per hour and starves the site to
  one worker while it runs. FIX = precompute a `site_stats` table nightly (an index can't
  help; the aggregate must read the body column). Also: `classify_main_name` has NO index
  (`idx_documents_category` is on `category_id`, a look-alike trap), so the categories facet
  + category browse filter full-scan (1.3-5.7s); `CREATE INDEX idx_documents_classify_main
  ON documents(classify_main_name)` fixes both. Everything else (<250ms) is healthy. See
  the fix plan in `perf-diagnosis.md`. **All three fixes shipped:** `site_stats` (74s → 2.3s),
  the index, and `corpus_stats` (commit `ebf1dc8`, same single scan in `build_site_stats.py`,
  read by `get_stats` with a live-query fallback) → `/` cold **0.23s**, `/browse` **0.35s**.
  Both tables rebuild nightly in Phase 2c.
- **(2026-08-11) The public site is PRIVATE — behind HTTP Basic Auth.** nginx
  server-level `auth_basic` on the chinagovernance :443 block; creds in
  `/etc/nginx/.htpasswd` (user `admin`, apr1 hash — NOT in the repo). This supersedes
  the bot mitigations above (moot while private, kept as defense-in-depth).
  `/.well-known/acme-challenge/` is exempted so certbot renewals still work.
  `daily_sync` is unaffected (its checks curl `localhost:8001`, bypassing nginx; only
  the Telegram report's `/document/` hyperlinks now require the login). Manage:
  - Change/add a user: `htpasswd -B /etc/nginx/.htpasswd <user>` (apache2-utils) or
    `H=$(openssl passwd -apr1); echo "user:$H" >> /etc/nginx/.htpasswd`; then
    `nginx -t && systemctl reload nginx`.
  - Make PUBLIC again: comment out the two `auth_basic` lines in
    `/etc/nginx/sites-enabled/chinagovernance`, then `nginx -t && systemctl reload nginx`.


- **Broken/unreliable gkmlpt sites** (Dongguan, Foshan, Bao'an, Shantou, Zhaoqing,
  Zhanjiang, Chaozhou, Yantian, gd-partial): the authoritative list with per-site
  reasons now lives in code — `crawlers/gkmlpt.py` → `KNOWN_BROKEN`. A bulk
  `--sync` still attempts them and they simply fail; a manual `--site X` can retry
  one if it recovers. (Meizhou/Maoming/Qingyuan were removed from the SITES dict.)
- **Per-crawler quirks** (MIIT/MOST/SAMR US-timeouts, CAC zcfg 404, CLT WP 502,
  etc.) now live in each crawler's docstring, not here — grep the crawler file.
- **`daily_sync.sh` report says `rsync: true` on the droplet even though NO rsync
  happens.** Marker-gated Phase 3 publishes in place (WAL checkpoint + restart);
  the `RSYNC_OK` variable is just a mislabeled "publish succeeded" flag. Cosmetic
  — rename `RSYNC_OK` → `PUBLISH_OK`. (No actual self-rsync, so no corruption risk.)
- **A broken Mac `crontab` line** (`0 7 * * * ./scripts/daily_sync.sh …`) used a
  relative path and silently failed for weeks (cron CWD = `$HOME`). Being removed
  — the droplet is the sole runner. The Mac is dev-only; nothing schedules there.
- **(RESOLVED 2026-08-10) `compute_scores.py` re-score was slow (~78 min) + WAL-heavy
  (~5GB).** It wrote all ~252k score updates in ONE `executemany`+commit; because an
  `UPDATE ... SET score` rewrites the WHOLE record (incl. `body_text_cn` overflow
  pages), touching every row rewrote ~5GB of unchanged body text into one transaction
  the app's read connection pinned (no mid-pass checkpoint → reads slowed
  quadratically). Fix (all score-preserving): (1) diff computed scores vs stored and
  UPDATE only CHANGED rows — a full re-score now writes ~hundreds of rows, not 252k;
  (2) batched commits (5k) + periodic PASSIVE checkpoint + final TRUNCATE cap the WAL;
  (3) stream the body cursor instead of `fetchall()` (was materializing ~4GB on a 4GB
  box); (4) an ANY-term regex precheck skips the 40-term scan for docs with no AI
  terms. Verified: a re-score right after a full run wrote **354/252,318 rows
  (251,964 unchanged), WAL 0, ~1–2 min** vs the old ~78min/5GB.
