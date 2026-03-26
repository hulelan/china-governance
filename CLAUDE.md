# CLAUDE.md — Operational Guide

## What This Project Is

Chinese government document corpus + web app. Crawls policy documents from central (State Council, NDRC, MOF, MEE) through provincial (Guangdong) to municipal (Shenzhen + 16 other Guangdong cities) and district level. Live at [chinagovernance.com](https://www.chinagovernance.com).

## Current Corpus (March 2026)

- **111,653 documents**, 44 sites, 92% body text coverage
- **110k+ classified** with English titles, summaries, importance, categories, topics (via DeepSeek API)
- Shenzhen (municipal + 9 districts + 13 departments + investment portal), Guangdong Province, 16 other Guangdong cities
- Central: State Council, NDRC, MOF, MEE
- Provinces: Beijing (1,781), Shanghai (3,830), Jiangsu (1,041)
- Non-gkmlpt content: Shenzhen investment news, DRC overseas investment, Longgang AI/robotics
- All stored in local `documents.db` (SQLite, ~1GB)

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

python3 -m crawlers.sz_invest                   # Shenzhen non-gkmlpt (investment news, DRC, Longgang AI)
python3 -m crawlers.sz_invest --section fgw_xwdt  # DRC news only
python3 -m crawlers.sz_invest --section lg_ai     # Longgang AI/robotics only
```

### Classification (DeepSeek API)
```bash
export DEEPSEEK_API_KEY="sk-..."
python3 scripts/classify_documents.py --dry-run --limit 5   # Test
python3 scripts/classify_documents.py --concurrency 2       # Full run (~$0.50/1k docs)
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
uvicorn web.app:app --reload --port 8000        # Start local dev server
# Opens SQLite in read-only mode — safe to run alongside crawlers (WAL mode)
```

### Deploy to Production
```bash
# Incremental sync (fast — only inserts new docs, skips existing)
DATABASE_URL="postgresql://postgres:yNpVZKsSVTBvGNozjIbgBsKsQAnrJQdF@gondola.proxy.rlwy.net:48854/railway" \
  python3 scripts/sqlite_to_postgres.py

# Push classifications + new docs (no full rebuild needed)
DATABASE_URL="postgresql://postgres:yNpVZKsSVTBvGNozjIbgBsKsQAnrJQdF@gondola.proxy.rlwy.net:48854/railway" \
  python3 scripts/sync_classifications.py

# Full rebuild (slow — drops all tables, re-inserts everything. Rarely needed.)
DATABASE_URL="postgresql://postgres:yNpVZKsSVTBvGNozjIbgBsKsQAnrJQdF@gondola.proxy.rlwy.net:48854/railway" \
  python3 scripts/sqlite_to_postgres.py --drop

# Verify production
curl -s "https://china-governance-production.up.railway.app/api/v1/stats" | python3 -m json.tool
```

## Architecture

```
Local:      crawlers/ → documents.db (SQLite, source of truth)
                            ↓ scripts/sqlite_to_postgres.py
Production: Railway Postgres ← web app (FastAPI + Jinja2 + D3.js)
```

- **Local SQLite** is the source of truth. Crawlers write here.
- **Railway Postgres** is the production mirror. The live website reads from this.
- Sync is manual: `sync_classifications.py` for classification updates + new docs, `sqlite_to_postgres.py --drop` for full rebuild.
- Web app uses `DATABASE_URL` env var for Postgres, falls back to local SQLite.
- Documents are classified via DeepSeek API (`scripts/classify_documents.py`) — adds English title, summary, category, importance, topics to each doc.

## SQLite Concurrency Rules

- **WAL mode** is enabled. Multiple readers + 1 writer works fine.
- **`busy_timeout=30000`** (30s) is set in `crawlers/base.py`.
- **2 parallel writers** is the safe max. 4+ writers will hit `database is locked`.
- Web app opens DB read-only (`?mode=ro`) — never blocks crawlers.

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

## Known Issues

- **Dongguan, Foshan, Meizhou, Maoming, Qingyuan, Bao'an**: gkmlpt endpoints unreachable (DNS/timeout/Cloudflare). Added to SITES dict but will fail.
- **Shantou**: Only 49 docs crawled (interrupted). Needs re-run.
- **Zhaoqing, Zhanjiang, Chaozhou, Yantian**: 0 docs — crawl failed due to SQLite lock contention. Need sequential re-run.
- **Guangdong Province (gd)**: Partial crawl (6,169 docs). Needs browser UA for full corpus.
