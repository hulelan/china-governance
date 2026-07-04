# CNGOV — Chinese Government Document Corpus

A searchable archive of **180,000+ Chinese government documents** spanning central
government to district level, with **220,000+ cross-document citation links** traced
between policies. Built for Western China analysts and researchers.

**Live at [chinagovernance.com](https://www.chinagovernance.com)** ·
live counts: [`/api/v1/stats`](https://www.chinagovernance.com/api/v1/stats)

> Corpus size changes daily (the crawlers run nightly), so this README doesn't
> hardcode an exact total — `/api/v1/stats` is the source of truth. `CLAUDE.md`
> keeps a dated snapshot for operators.

## What's in the corpus

Central ministries (State Council, NDRC, MOF, MEE, CAC, MIIT, MOST, SAMR, MOFCOM,
NDA, SIC, MOE…), provinces and municipalities (Guangdong + 16 GD cities, Beijing,
Shanghai, Jiangsu, Zhejiang, Chongqing, Wuhan, Suzhou, Hangzhou, Heilongjiang),
Shenzhen down to the district + department level, plus curated media (Xinhua,
People's Daily, Phoenix, LatePost, 36Kr) and legal sources. ~60 sites total.

Documents span 2015–2026 across 20+ categories, connected by cross-level citation
links — central policies referenced by provincial directives, cited by municipal
implementation plans, enacted at the district level.

## Key features

- **Cross-level policy chains** — trace how a central policy cascades down through
  provincial, municipal, and district implementations
- **Citation network** — interactive D3.js graph of which documents cite which,
  colored by admin level
- **Full-text search** across the Chinese corpus
- **Algorithmic + LLM enrichment** — citation_rank, AI-relevance scoring, English
  titles/summaries, document-type classification
- **Verification** — every document links to its original government source URL

## Quick start

```bash
pip install -r requirements.txt

# Run the web interface (opens documents.db read-only)
uvicorn web.app:app --port 8000
# Open http://localhost:8000
```

The web app is **SQLite-only** and opens the DB read-only (`?mode=ro`), so it's
safe to run alongside the crawlers (WAL mode). Override the path with
`SQLITE_PATH` if needed. See `CLAUDE.md` for the full architecture — in
production the app and crawlers both live on a DigitalOcean droplet, and the
droplet's `documents.db` is the source of truth.

## Project structure

```
china-governance/
├── crawlers/                   # One module per site; base.py = shared infra
│   ├── base.py                 #   Shared: fetch, init_db, next_id + authoring gotchas
│   ├── gkmlpt.py               #   Guangdong gkmlpt platform (many GD sites)
│   └── …                       #   gov, ndrc, mof, mee, cac, miit, most, beijing, …
│
├── analyze.py                  # Shared citation-analysis library (imported by tests + rnd)
│
├── web/                        # FastAPI web application
│   ├── app.py                  #   Entry point
│   ├── database.py             #   SQLite (aiosqlite), read-only
│   ├── routers/  services/  templates/
│
├── scripts/                    # ACTIVE ops scripts (see scripts/README.md)
│   ├── daily_sync.sh           #   Nightly crawl → score → classify → publish
│   ├── classify_documents.py   #   DeepSeek classification
│   ├── compute_scores.py       #   citation_rank / algo_doc_type / ai_relevance
│   └── rnd/                     #   R&D / one-off tools (not the live pipeline)
│
├── requirements.txt
└── documents.db                # (gitignored) SQLite DB — source of truth on the droplet
```

See **`scripts/README.md`** for which scripts are load-bearing vs. R&D.

## Web interface

**Pages:** Homepage (stats), Browse (filterable table), Document detail (metadata,
body, citations, backlinks), Search, Chain (cross-level policy chains), Network
(D3.js citation graph), Dashboard, Analysis.

**API** (all under `/api/v1/`): `GET /documents`, `/documents/{id}`,
`/documents/{id}/citations`, `/search?q=`, `/sites`, `/stats`, `/network`.

## Citation analysis

Two citation types are extracted from body text (see `analyze.py`):

- **Formal citations** (文号) — e.g. `国发〔2023〕15号` — regex-extracted, classified
  by admin-level prefix (国发/中发 = central, 粤府 = provincial, 深府 = municipal, …)
- **Named references** (《》) — e.g. `《新一代人工智能发展规划》` — matched against corpus titles

## Crawlers

Each crawler writes to the same `documents.db`; `site_key` + `admin_level`
distinguish sources. Per-site quirks live in each crawler's docstring; the full
command list is in `CLAUDE.md`.

```bash
python -m crawlers.gkmlpt --site sz     # one Guangdong gkmlpt site
python -m crawlers.ndrc                 # NDRC
python -m crawlers.gov                  # State Council
```

## Tech stack

- **Backend**: FastAPI, Python 3.12
- **Database**: SQLite (WAL, read-only in the app)
- **Frontend**: Jinja2, Tailwind CSS, Chart.js, D3.js
- **Hosting**: DigitalOcean droplet (nginx + certbot + systemd + cron)
- **Crawlers**: requests/aiohttp, BeautifulSoup
- **Enrichment**: DeepSeek API (classification), deep-translator (titles)
