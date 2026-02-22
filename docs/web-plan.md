# Web Frontend for China Governance Document Corpus

## Context

We have a working crawler pipeline with 45,130 Chinese government documents from 20 Shenzhen sites stored in SQLite (50MB). The user wants an interactive website that displays this data, is deployable on a custom URL, and lets users verify content against the original government websites.

## Step 0: Reorganize Project Files

Rename old crawler-phase planning docs and create a `claude-bureaucracy/` folder:

```
claude-bureaucracy/
  crawler-plan.md          # (renamed from plan.md)
  crawler-scratchpad.md    # (renamed from scratchpad.md)
  web-plan.md              # New — this plan, copied into repo
  web-scratchpad.md        # New — working log for web implementation
```

## Step 1: Database Preparation

**Files:** `scripts/migrate_db.py`, `scripts/compute_hashes.py`

- Add `raw_html_sha256` TEXT column to `documents` table
- Create FTS5 virtual table indexing `title`, `body_text_cn`, `document_number`, `keywords`, `publisher`
- Compute SHA-256 hashes for all ~1,763 raw HTML files and store in DB

## Step 2: Backend (FastAPI + aiosqlite)

**Files:** `web/app.py`, `web/database.py`, `web/models.py`, `web/services/`, `web/routers/`

- FastAPI app serving JSON API + Jinja2 server-rendered pages
- Read-only SQLite connection (crawler writes separately)
- **API endpoints:**
  - `GET /api/v1/documents` — paginated, filterable by site/category/date/keyword
  - `GET /api/v1/documents/{id}` — single doc with all fields
  - `GET /api/v1/documents/{id}/citations` — what this doc cites + what cites it
  - `GET /api/v1/search?q=` — FTS5 full-text search with BM25 ranking + snippets
  - `GET /api/v1/sites` — list of 20 crawled sites
  - `GET /api/v1/stats` — corpus statistics
  - `GET /api/v1/network` — citation graph (nodes + edges JSON)
  - `GET /api/v1/verify/{id}` — SHA-256 hash + raw HTML

**Reuse from existing code:**
- `analyze.py:23-28` — `REF_PATTERN` regex for citation extraction
- `analyze.py:32-98` — `ISSUER_LEVELS` dict + `classify_issuer()` + `get_admin_level()`
- `crawler.py:79-133` — database schema (must match exactly)

## Step 3: Frontend Pages (Jinja2 + Tailwind CSS + Alpine.js)

**Files:** `web/templates/`, `web/static/`

| Page | Route | Purpose |
|------|-------|---------|
| Homepage | `/` | Corpus stats, quick search, navigation |
| Browse | `/browse` | Filterable doc list (site, category, date, has 文号) |
| Document | `/document/{id}` | Full doc view + metadata + citations + verification links |
| Search | `/search?q=` | FTS5 results with highlighting |
| Network | `/network` | D3.js citation graph (nodes colored by admin level) |
| Dashboard | `/dashboard` | Timeline, cross-ref hierarchy, top-cited docs, coverage |
| Compare | `/compare/{id}` | Side-by-side: our text vs archived raw HTML |

**Design:** Super dense, data-explorer style. Maximum information density — compact tables, small fonts, split panes, minimal whitespace. Think Bloomberg Terminal for Chinese government docs.
**Styling:** Tailwind CSS via CDN (no build step). Dark-ish neutral palette, monospace for doc numbers.
**Interactivity:** Alpine.js for filters, D3.js for network graph, Chart.js for dashboard charts.

## Step 4: Verification Feature (3 layers)

1. **Direct links** — every document shows a "View on original site" link to the `url` field (opens in new tab)
2. **SHA-256 hash** — display hash of archived HTML; user can re-fetch original and compare
3. **Side-by-side comparison** — `/compare/{id}` shows our extracted text next to the raw archived HTML in a sandboxed iframe

Note: Original sites use HTTP only (HTTPS fails). Our site will use HTTPS. So we link out rather than iframe the original — mixed content would be blocked by browsers.

## Step 5: Citation Network Visualization

**File:** `web/static/js/network.js` (~250 lines of D3.js)

- Force-directed graph, ~1,946 edges
- Nodes colored by admin level: central (red), provincial (orange), municipal (blue), district (green)
- Node size = citation count
- Click node → side panel with document details
- Filters: site, admin level, date range, min degree
- Default view: nodes with degree >= 2 to avoid clutter

## Step 6: Deployment Config

**Files:** `Dockerfile`, `docker-compose.yml`, `Caddyfile`, `requirements.txt`

```
requirements.txt: fastapi, uvicorn[standard], aiosqlite, jinja2, python-multipart
```

Docker Compose: FastAPI container + Caddy for auto-HTTPS. User changes domain in `Caddyfile` when ready.

For local dev: `uvicorn web.app:app --reload --port 8000`

## Build Order

1. Step 0 — file reorganization (2 min)
2. Step 1 — DB migration + hashes (scripts, ~5 min)
3. Step 2 — FastAPI skeleton + document/stats services → homepage renders
4. Step 3 — Browse + Document detail + Search pages
5. Step 4 — Verification/compare view
6. Step 5 — Citation network (D3.js)
7. Step 3 continued — Dashboard page
8. Step 6 — Docker deployment config

Steps 2-4 produce a functional, deployable website. Steps 5-7 add the differentiated features.

## Verification

- `uvicorn web.app:app --reload` and visit http://localhost:8000
- Homepage shows 45,130 docs across 20 sites
- `/browse` lists documents, filters work
- `/document/{id}` shows full text + "View on original site" link works
- `/search?q=深圳` returns ranked results with highlights
- `/compare/{id}` shows side-by-side comparison
- `/network` renders D3.js citation graph
- `/dashboard` shows timeline + cross-reference charts
