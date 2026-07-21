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
  higher (~180k as of June 2026). Check `/api/v1/stats` for the current number.

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

### Classification (DeepSeek API)

Documents are classified via DeepSeek API (`scripts/classify_documents.py`) — adds English title, summary, doc_type, policy_significance, references_json. Cost: ~$0.50/1k docs, concurrency 2 max (higher silently rate-limits with empty responses, not 429s). As of June 2026 the droplet's nightly `daily_sync.sh` Phase 2 runs this UNBOUNDED (no `--limit`), so it drains the full backlog (~156k docs, ~$78, ~40h) on the first reliable run, then only touches new docs. The `mkdir` lock keeps the next day's cron from piling a second classifier on top.

## SQLite Concurrency Rules

- **WAL mode** is enabled. Multiple readers + 1 writer works fine.
- **`busy_timeout=30000`** (30s) is set in `crawlers/base.py`.
- **2 parallel writers** is the safe max. 4+ writers will hit `database is locked`.
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
- **(2026-07) Crawler timeouts.** `CRAWLER_TIMEOUT=1800` (30 min/crawler). Recent
  runs see ~11 crawlers hit the cap (cac, samr, mofcom, beijing, shanghai,
  jiangsu, suzhou, heilongjiang, xinhua, miit, most) → ~10h total run. Likely
  US→China latency from NYC. TODO: confirm each runs incremental/`--sync`, time
  the worst offenders, raise the cap selectively or optimize.
- **(2026-06) Is DeepSeek `references_json` worth the cost over regex refs?**
  We have regex-extracted `references_source` on ~133k docs (`regex_v1`). A
  sample comparison found ~72% overlap with DeepSeek's refs. Open question
  whether the DeepSeek pass adds enough citation quality to justify classifying
  the long tail for references specifically (vs. other classification fields).

## Known Issues

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
