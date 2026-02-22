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
