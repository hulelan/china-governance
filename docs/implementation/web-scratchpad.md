# Web Frontend — Scratchpad

## Session Log

### 2026-02-15 — Web App Implementation

**Step 0: File Reorganization** — Done
- claude-bureaucracy/ folder with crawler-plan.md, crawler-scratchpad.md, web-plan.md, web-scratchpad.md

**Step 1: DB Migration** — Done
- FTS5 virtual table created (45,130 docs indexed)
- raw_html_sha256 column added
- SHA-256 hashes computed for raw HTML files

**Step 2: Backend** — Done
- FastAPI app: web/app.py, web/database.py
- Services: web/services/documents.py (all query logic)
- API: web/routers/api.py (8 endpoints)
- Pages: web/routers/pages.py (7 routes)

**Step 3: Frontend Pages** — Done
- All 7 pages implemented with Tailwind CSS dark theme
- Homepage: stats cards, sites table, timeline, categories
- Browse: filterable doc list with pagination (903 pages)
- Document detail: metadata + verification + citations + body text
- Search: FTS5 with BM25 ranking, truncated snippets
- Network: D3.js force-directed citation graph (1,526 nodes)
- Dashboard: Chart.js (timeline, hierarchy doughnut, coverage bars) + top cited docs
- Compare: side-by-side extracted text vs archived raw HTML

**Step 4: Verification** — Done
- Direct links to original government sites
- SHA-256 hashes displayed
- Compare view with sandboxed iframe

**Step 5: Citation Network** — Done
- Fixed edge/node ID mismatch (source docs now included as nodes)
- 1,526 nodes, 2,941 edges at min_degree=2
- Interactive: zoom, drag, click for details, filter by site/min citations

**Step 6: Deployment Config** — Done
- requirements.txt, Dockerfile, docker-compose.yml, Caddyfile
- Caddy for auto-HTTPS (uncomment domain when ready)

**Bugs Fixed:**
- Network graph crash: edges referenced numeric IDs but nodes used document number strings
- Search snippets: FTS5 unicode61 tokenizer treats CJK runs as single tokens → 1,400 char snippets; added _truncate_snippet() to cap at 150 chars

**All pages verified working** via Playwright screenshots at http://localhost:8000

### 2026-02-22 — AI Case Study (Steps 1-3, 5)

See `docs/implementation/ai-case-study-plan.md` for details.

- Backfilled body text for 87/113 AI-related documents
- Extracted 57 named + 11 formal citations from AI docs
- Built `/chain/{topic}` page with 6 topic chains (ai, digital, carbon, housing, education, health)
- Built `/analysis/ai` write-up page
- Added `web/services/chain.py` for chain query logic
- Added `web/templates/chain.html` and `web/templates/writeup.html`

### 2026-02-23 — PostgreSQL Migration + Railway Deployment

**Database migration: SQLite → PostgreSQL**
- Rewrote `web/database.py` with dual-mode: `PostgresDB` (asyncpg) for production, `SQLiteDB` (aiosqlite) for local dev
- `SQLiteDB._pg_to_sqlite()` auto-translates Postgres SQL → SQLite (placeholders, date functions, array ops)
- Converted all queries in `web/services/documents.py`, `web/services/chain.py`, `web/routers/pages.py`, `web/routers/api.py` to Postgres-native syntax
- Created `scripts/sqlite_to_postgres.py` — migrated 46,633 documents + 14,834 citations to Railway Postgres (~30 min)

**Deployment to Railway**
- Created `Dockerfile` (python:3.12-slim) after nixpacks failed 3 times
- Created `railway.json` with DOCKERFILE builder config
- Updated `Procfile` and `requirements.txt` (added asyncpg)
- Fixed crash: `web/static` directory missing in Docker → made static mount conditional in `app.py`, added `.gitkeep`
- Fixed port mismatch: Railway sets `PORT=8080`, changed networking config to match

**Custom domain**
- Added `chinagovernance.com` + `www.chinagovernance.com` on Railway
- Squarespace DNS: `www` CNAME → `6vpd3qm8.up.railway.app`, `_railway-verify` TXT record
- Root domain forwarding: `chinagovernance.com` → `https://www.chinagovernance.com` (Squarespace redirect)

**All 9 pages verified returning 200** at china-governance-production.up.railway.app

### 2026-02-23 — Sprint 1: Subsidies Report Pipeline

Plan: `.claude/plans/validated-foraging-clover.md`

**Phase 2: Subsidy analysis pipeline (new code)**

1. **Multi-keyword chain support** (`web/services/chain.py`)
   - Added `"subsidies"` to `TOPIC_KEYWORDS`
   - Added `TOPIC_MULTI_KEYWORDS` dict for broader matching: `["补贴", "资金", "扶持", "奖励", "资助", "引导基金", "专项资金"]`
   - Modified `get_chain()` to accept `topic` param, builds multi-pattern OR query when topic is in `TOPIC_MULTI_KEYWORDS`
   - `/chain/subsidies` now works automatically via existing template

2. **Subsidy data extraction script** (`scripts/extract_subsidy_data.py`) — NEW
   - Regex extraction of yuan amounts (`万元`/`亿元`) with surrounding context
   - Sector keyword matching against 20+ strategic industries
   - Normalizes all amounts to 万元 (1亿 = 10,000万)
   - Creates `subsidy_items` table (document_id, amount_value, amount_raw, amount_context, sector)
   - Dry-run on 14.5% corpus: **222 docs with amounts, 1,926 items, 330 亿元 total, 15+ sectors**
   - Write blocked by concurrent crawler lock — will run after backfill

3. **Subsidy analysis script** (`scripts/analyze_subsidies.py`) — NEW
   - Aggregates by: district, sector, year, central policy linkage, top programs, top documents
   - Outputs `data/subsidy_analysis.json`
   - Human-readable summary printed to stdout

4. **Schema additions**
   - Added `subsidy_items` table to `crawlers/base.py` `init_db()` (SQLite)
   - Added `subsidy_items` table + migration to `scripts/sqlite_to_postgres.py` (PostgreSQL)
   - Added `DROP TABLE IF EXISTS subsidy_items CASCADE` to DROP_SCHEMA

5. **Subsidy web service** (`web/services/subsidies.py`) — NEW
   - 7 async query functions: `get_subsidy_stats()`, `get_subsidy_by_district()`, `get_subsidy_by_sector()`, `get_subsidy_timeline()`, `get_top_subsidy_programs()`, `get_top_subsidy_documents()`, `get_central_subsidy_linkage()`

6. **Subsidies report page** (`web/templates/subsidies_writeup.html`) — NEW
   - Route: `/analysis/subsidies` (added to `web/routers/pages.py`)
   - Nav link: "Subsidies" added to `web/templates/base.html`
   - 5 findings sections with dynamic data tables: implementation gradient (by district), sector concentration, central-to-local linkage, temporal evolution, fiscal specificity gap
   - Graceful fallback if `subsidy_items` table doesn't exist yet
   - Follows same Tailwind dark theme pattern as `writeup.html`

**Files created:** `scripts/extract_subsidy_data.py`, `scripts/analyze_subsidies.py`, `web/services/subsidies.py`, `web/templates/subsidies_writeup.html`
**Files modified:** `web/services/chain.py`, `web/routers/pages.py`, `web/templates/base.html`, `crawlers/base.py`, `scripts/sqlite_to_postgres.py`

**Status:** All code written and imports verified. Blocked on running extraction against DB (crawler holds write lock). Backfill in parallel session hit issues: many gkmlpt pages return empty body text because `extract_body_text()` regex doesn't match all page variants.
