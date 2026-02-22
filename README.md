# CNGOV — Shenzhen Government Document Corpus

A searchable archive of 45,130 Chinese government documents from 20 Shenzhen municipal and district government websites. Includes a crawler pipeline, full-text search, citation network analysis, and an interactive web interface for browsing and verifying documents against original sources.

## What's in the corpus

| Metric | Count |
|--------|-------|
| Documents | 45,130 |
| Government sites | 20 |
| With body text | 6,700 (15%) |
| With document number (文号) | 4,255 |
| Cross-reference citations | ~2,900 edges |
| Raw HTML archived | 6,754 files with SHA-256 hashes |

All documents come from Shenzhen's standardized `gkmlpt` (government open information) platform, which uses a common API across all 20 sites. Documents span 2015-2026 and cover categories like 通知公告, 工作动态, 财政预决算, 招标采购, 规范性文件, and 20+ others.

### Sites

| Key | Name | Docs |
|-----|------|------|
| szlhq | Longhua District | 6,134 |
| mzj | Civil Affairs Bureau | 5,015 |
| ga | Public Security Bureau | 5,010 |
| hrss | Human Resources & Social Security | 3,236 |
| swj | Commerce Bureau | 2,889 |
| jtys | Transport Bureau | 2,843 |
| stic | S&T Innovation Bureau | 2,710 |
| fgw | Development & Reform Commission | 2,552 |
| zjj | Housing & Construction Bureau | 2,353 |
| sf | Justice Bureau | 2,019 |
| szeb | Education Bureau | 1,999 |
| yjgl | Emergency Management Bureau | 1,996 |
| szpsq | Pingshan District | 1,636 |
| wjw | Health Commission | 1,238 |
| szgm | Guangming District | 905 |
| sz | Shenzhen Main Portal | 844 |
| szlh | Luohu District | 759 |
| audit | Audit Bureau | 469 |
| szns | Nanshan District | 309 |
| szft | Futian District | 214 |

## Quick start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the web interface
uvicorn web.app:app --port 8000
# Open http://localhost:8000
```

## Project structure

```
china-governance/
├── crawler.py                  # Document crawler (metadata + body text)
├── analyze.py                  # Cross-reference analysis, citation network
├── export_network.py           # Export citation graph as CSV
│
├── web/                        # FastAPI web application
│   ├── app.py                  #   Entry point, mounts
│   ├── database.py             #   Async SQLite connection (read-only)
│   ├── routers/
│   │   ├── api.py              #   JSON API (/api/v1/...)
│   │   └── pages.py            #   Server-rendered HTML routes
│   ├── services/
│   │   └── documents.py        #   Query logic, FTS5 search, citations
│   └── templates/              #   Jinja2 templates (Tailwind, dark theme)
│       ├── base.html           #   Layout, nav, styles
│       ├── index.html          #   Homepage with corpus stats
│       ├── browse.html         #   Filterable document list
│       ├── document.html       #   Document detail + verification
│       ├── search.html         #   Full-text search results
│       ├── network.html        #   D3.js citation network graph
│       ├── dashboard.html      #   Chart.js analytics dashboard
│       └── compare.html        #   Side-by-side text vs archived HTML
│
├── scripts/                    # One-off maintenance utilities
│   ├── migrate_db.py           #   Add FTS5 index + hash column to DB
│   ├── compute_hashes.py       #   SHA-256 for archived raw HTML files
│   └── check_db.py             #   Database inspection
│
├── deploy/                     # Docker + reverse proxy configuration
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── Caddyfile               #   Caddy (auto-HTTPS, edit domain here)
│
├── docs/                       # Project documentation
│   ├── spec.md                 #   Original project specification
│   ├── conversation.md         #   Initial design conversation
│   ├── strategy/               #   Landscape research, direction options
│   └── implementation/         #   Build plans and session logs
│
├── requirements.txt            # Python dependencies
├── documents.db                # (gitignored) SQLite database, 141 MB
├── raw_html/                   # (gitignored) Archived HTML, 524 MB
├── citation_edges.csv          # (gitignored) Exported citation edges
└── document_nodes.csv          # (gitignored) Exported document nodes
```

## Web interface

The web app is a server-rendered FastAPI application with a dense, data-explorer aesthetic (dark theme, maximum information density).

**Pages:**

- **Homepage** (`/`) — Corpus stats, site list, publication timeline, category breakdown
- **Browse** (`/browse`) — Paginated document table with filters (site, category, year, has 文号)
- **Document** (`/document/{id}`) — Full metadata, body text, verification panel, citation links
- **Search** (`/search?q=`) — Full-text search via SQLite FTS5 with BM25 ranking
- **Network** (`/network`) — Interactive D3.js force-directed citation graph, nodes colored by admin level (central/provincial/municipal/district)
- **Dashboard** (`/dashboard`) — Chart.js visualizations: publication timeline, citation hierarchy breakdown, body text coverage, top-cited documents
- **Compare** (`/compare/{id}`) — Side-by-side view of extracted text vs archived raw HTML

**API endpoints** (all under `/api/v1/`):

| Endpoint | Description |
|----------|-------------|
| `GET /documents` | Paginated document list, filterable |
| `GET /documents/{id}` | Single document with all fields |
| `GET /documents/{id}/citations` | What this doc cites + what cites it |
| `GET /search?q=` | Full-text search with snippets |
| `GET /sites` | List of 20 crawled sites |
| `GET /stats` | Corpus statistics |
| `GET /categories` | Document categories |
| `GET /network` | Citation graph nodes + edges for D3.js |

## Verification

Three layers of content verification against original government websites:

1. **Direct links** — Every document links to its original URL on the government site
2. **SHA-256 hashes** — Archived HTML files are hashed at crawl time; hashes displayed on document pages
3. **Side-by-side comparison** — `/compare/{id}` shows extracted text alongside the archived raw HTML in a sandboxed iframe

Note: All Shenzhen government sites use HTTP only (HTTPS fails). The web app links out to originals rather than iframing them to avoid mixed-content issues.

## Crawler

The crawler targets Shenzhen's `gkmlpt` API, a standardized open government information platform used across all 20 sites.

```bash
# Crawl metadata for all sites
python crawler.py

# Crawl a specific site
python crawler.py --site sz

# Backfill body text (prioritize docs with 文号)
python crawler.py --backfill-bodies --policy-first
```

**API pattern:** `https://{site}.sz.gov.cn/gkmlpt/api/all/{category_id}?page={n}&sid={sid}`

Body text extraction fetches individual document pages and parses the HTML for the main content section.

## Analysis

Cross-reference analysis extracts 文号 (document numbers) from body text using regex, classifies them by administrative level, and builds a citation network.

```bash
# Full analysis
python analyze.py

# Citation network analysis
python analyze.py --network

# Resolve citations against corpus
python analyze.py --resolve

# Export graph as CSV
python export_network.py
```

**Administrative hierarchy detected in citations:**
- **Central** (国发, 国办, 中发, ...) — State Council / central ministries
- **Provincial** (粤府, 粤办, ...) — Guangdong Province
- **Municipal** (深府, 深发, ...) — Shenzhen City
- **District** (深坪, 深光, ...) — Shenzhen districts

## Deployment

### Local development

```bash
pip install -r requirements.txt
uvicorn web.app:app --reload --port 8000
```

### Docker

```bash
docker compose -f deploy/docker-compose.yml up -d
# Serves on port 80 (HTTP) via Caddy
```

### Production with custom domain

1. Edit `deploy/Caddyfile` — uncomment your domain, comment out the `:80` block:
   ```
   yourdomain.com {
       reverse_proxy web:8000
   }
   ```
2. Ensure ports 80 and 443 are open
3. `docker compose -f deploy/docker-compose.yml up -d` — Caddy handles TLS certificates automatically

## Database schema

The SQLite database follows the crawler's schema:

```sql
-- Core document table
CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    title TEXT, body_text_cn TEXT, document_number TEXT,
    publisher TEXT, date_written TEXT, date_published TEXT,
    url TEXT, site_key TEXT, classify_main_name TEXT,
    keywords TEXT, identifier TEXT, raw_html_path TEXT,
    raw_html_sha256 TEXT
);

-- FTS5 full-text search index
CREATE VIRTUAL TABLE documents_fts USING fts5(
    title, body_text_cn, document_number, keywords, publisher,
    content=documents, content_rowid=id,
    tokenize='unicode61'
);

-- Site registry
CREATE TABLE sites (
    site_key TEXT PRIMARY KEY,
    name TEXT, base_url TEXT, admin_level TEXT, sid TEXT
);
```
