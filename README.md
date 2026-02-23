# CNGOV — Chinese Government Document Corpus

A searchable archive of **46,600+ Chinese government documents** spanning central government to district level, with **14,800+ cross-level citation links** traced between policies. Built for Western China analysts and researchers.

**Live at [chinagovernance.com](https://chinagovernance.com)**

## What's in the corpus

| Layer | Sites | Documents | Source |
|-------|-------|-----------|--------|
| **Central** | State Council, NDRC | 1,500 | gov.cn, ndrc.gov.cn |
| **Municipal** | Shenzhen (14 departments) | 37,384 | gkmlpt API |
| **District** | 6 Shenzhen districts | 16,091 | gkmlpt API |
| **Total** | **22 sites** | **46,600+** | |

Documents span 2015–2026 and cover 20+ categories. **14,834 citation links** connect documents across administrative levels — central policies referenced by provincial directives, cited by municipal implementation plans, enacted at the district level.

## Key features

- **Cross-level policy chains** — Trace how a central government policy (e.g., State Council AI strategy) cascades down through provincial, municipal, and district implementations
- **Citation network** — Interactive D3.js force-directed graph showing which documents cite which, colored by admin level
- **Full-text search** — Search across 46K documents in Chinese
- **Topic chains** — Browse policy chains for AI, digital economy, carbon, housing, education, and health
- **Document detail** — Full metadata, body text, formal + named references with admin level badges, "Referenced By" backlinks
- **Verification** — Every document links to its original government source URL with SHA-256 content hashes

## Quick start

### Local development (SQLite)

```bash
pip install -r requirements.txt

# Run the web interface (uses local documents.db)
uvicorn web.app:app --port 8000
# Open http://localhost:8000
```

### Production (Railway + PostgreSQL)

The app is deployed on [Railway](https://railway.com) with PostgreSQL. Set `DATABASE_URL` to use Postgres, or leave unset to fall back to local SQLite.

```bash
# Push local SQLite data to Postgres
export DATABASE_URL="postgresql://user:pass@host:port/dbname"
pip install psycopg2-binary
python scripts/sqlite_to_postgres.py
```

## Project structure

```
china-governance/
├── crawlers/                   # Multi-platform crawler package
│   ├── base.py                 #   Shared: init_db, fetch, store_document
│   ├── gkmlpt.py               #   Guangdong gkmlpt platform (25 sites)
│   ├── ndrc.py                 #   NDRC static HTML crawler
│   └── gov.py                  #   State Council JSON feed crawler
│
├── analyze.py                  # Citation analysis, named ref patterns
├── export_network.py           # Export citation graph as CSV
│
├── web/                        # FastAPI web application
│   ├── app.py                  #   Entry point
│   ├── database.py             #   Dual-mode: asyncpg (Postgres) / aiosqlite (SQLite)
│   ├── routers/
│   │   ├── api.py              #   JSON API (/api/v1/...)
│   │   └── pages.py            #   Server-rendered HTML routes
│   ├── services/
│   │   ├── documents.py        #   Document queries, search, citations
│   │   └── chain.py            #   Policy chain builder (cross-level)
│   └── templates/              #   Jinja2 templates (Tailwind, dark theme)
│
├── scripts/
│   ├── sqlite_to_postgres.py   #   Migrate data from SQLite → Postgres
│   ├── extract_citations.py    #   Build citations table from body text
│   ├── build_ai_chain.py       #   AI policy chain analysis
│   ├── translate_chain.py      #   LLM translation (GPT / Qwen backends)
│   ├── backfill_ai.py          #   Fetch missing body text for AI docs
│   └── migrate_*.py            #   Database migrations
│
├── Dockerfile                  # Production container
├── railway.json                # Railway deployment config
├── requirements.txt            # Python dependencies
└── documents.db                # (gitignored) Local SQLite database
```

## Web interface

Dark-themed, data-dense web app for exploring Chinese government documents.

**Pages:**

- **Homepage** (`/`) — Corpus stats, site list, category breakdown
- **Browse** (`/browse`) — Paginated document table with filters (site, category, year, has 文号)
- **Document** (`/document/{id}`) — Full metadata, body text, formal + named citations with admin level badges, "Referenced By" backlinks
- **Search** (`/search?q=`) — Full-text search across the corpus
- **Chain** (`/chain/{topic}`) — Cross-level policy chains for 6 topics (AI, digital economy, carbon, housing, education, health)
- **Network** (`/network`) — Interactive D3.js citation network, nodes colored by admin level
- **Dashboard** (`/dashboard`) — Publication timeline, citation hierarchy, body text coverage
- **Analysis** (`/analysis/ai`) — AI policy case study write-up

**API** (all under `/api/v1/`):

| Endpoint | Description |
|----------|-------------|
| `GET /documents` | Paginated, filterable document list |
| `GET /documents/{id}` | Single document with all fields |
| `GET /documents/{id}/citations` | Forward + reverse citation links |
| `GET /search?q=` | Full-text search |
| `GET /sites` | All 22 crawled sites |
| `GET /stats` | Corpus statistics |
| `GET /network` | Citation graph for D3.js |

## Citation analysis

Two types of citations are extracted from document body text:

- **Formal citations** (文号) — e.g., `国发〔2023〕15号` — extracted via regex, classified by admin level prefix
- **Named references** (《》) — e.g., `《新一代人工智能发展规划》` — matched against corpus titles

**Admin level hierarchy:**
- **Central** (国发, 国办, 中发, ...) — State Council / central ministries
- **Provincial** (粤府, 粤办, ...) — Guangdong Province
- **Municipal** (深府, 深发, ...) — Shenzhen City
- **District** (深坪, 深光, ...) — Shenzhen districts

## Crawlers

Three platform-specific crawlers write to the same database. The `site_key` and `admin_level` fields distinguish sources.

```bash
# Guangdong gkmlpt platform (25 sites)
python -m crawlers.gkmlpt --site sz
python -m crawlers.gkmlpt --backfill-bodies --policy-first

# NDRC (5 policy sections)
python -m crawlers.ndrc

# State Council (~1,000 docs)
python -m crawlers.gov
```

## Translation

LLM translation with two backends:

```bash
# OpenAI (GPT-4o-mini) — cheap batch API
python scripts/translate_chain.py --backend openai

# Local open-weights (Qwen 2.5 via Ollama) — free
python scripts/translate_chain.py --backend ollama
```

Both use rich government terminology glossaries and structured JSON output.

## Tech stack

- **Backend**: FastAPI, Python 3.12
- **Database**: PostgreSQL (production), SQLite (local dev)
- **Frontend**: Jinja2 templates, Tailwind CSS, Chart.js, D3.js
- **Hosting**: Railway
- **Crawlers**: aiohttp, BeautifulSoup
- **Translation**: OpenAI API / Ollama (Qwen 2.5)
