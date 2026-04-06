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
python3 -m crawlers.zhejiang                    # Zhejiang (dept subdomains, IPv6)
python3 -m crawlers.zhejiang --dept fzggw       # One department only
python3 -m crawlers.chongqing                   # Chongqing (3 sections, 697 docs)
python3 -m crawlers.wuhan                       # Wuhan (5 sections + AI portal)
python3 -m crawlers.nda                         # National Data Administration (5 sections, 379 docs)
python3 -m crawlers.sic                         # State Information Center (1,117 docs)
python3 -m crawlers.ipc_court                   # Supreme Court IP Tribunal (~75 recent, --deep for full 5k)
python3 -m crawlers.tsinghua_aiig               # Tsinghua AI Governance Institute

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
DATABASE_URL="" uvicorn web.app:app --reload --port 8001  # Local dev (SQLite)
# IMPORTANT: blank DATABASE_URL forces SQLite. If .env has DATABASE_URL set,
# the app will try to connect to Postgres (slow/broken for local dev).
# Opens SQLite in read-only mode — safe to run alongside crawlers (WAL mode)
```

### Daily Crawl + Sync
```bash
# Run manually (takes 4-5 hours):
nohup ./scripts/daily_sync.sh > logs/daily_$(date +%Y%m%d_%H%M).log 2>&1 &

# What it does:
# 1. Crawls all 62 sites (gkmlpt, central ministries, provinces, media)
# 2. Backfills missing body text
# 3. WAL checkpoint → rsync documents.db to droplet → restart web app
# 4. Sends Telegram report

# Check progress:
tail -f logs/daily_*.log

# Auto-run not yet working — macOS blocks cron/launchd from accessing
# ~/Desktop without Full Disk Access for /usr/sbin/cron.
# To fix: System Settings → Privacy & Security → Full Disk Access → add /usr/sbin/cron
# Then: crontab -e and add:
#   0 7 * * * cd ~/Desktop/claude_code/china-governance && ./scripts/daily_sync.sh >> logs/cron.log 2>&1
```

### Deploy to Production
```bash
# Production is a DigitalOcean droplet (104.236.88.45, NYC3, 2CPU/2GB).
# Deployment = rsync the SQLite DB + restart the web app.

# Manual sync (if daily_sync.sh didn't run):
sqlite3 documents.db "PRAGMA wal_checkpoint(TRUNCATE);"  # Flush WAL first!
rsync -az documents.db root@104.236.88.45:/root/china-governance/documents.db
ssh root@104.236.88.45 'systemctl restart chinagovernance'

# Pull code changes to droplet:
ssh root@104.236.88.45 'cd /root/china-governance && git pull && systemctl restart chinagovernance'

# Verify production:
curl -s "https://www.chinagovernance.com/api/v1/stats" | python3 -m json.tool
```

## Architecture

```
Local Mac:  crawlers/ → documents.db (SQLite, source of truth, ~2GB)
                            ↓ rsync (incremental, ~50MB delta)
Production: DigitalOcean droplet (104.236.88.45, NYC3)
            nginx + certbot (HTTPS) → uvicorn (2 workers) → SQLite (read-only)
```

- **Local SQLite** is the source of truth. Crawlers write here.
- **Droplet** serves a read-only copy synced via rsync. No Postgres.
- Sync flow: WAL checkpoint → rsync main DB file → restart uvicorn.
- Web app caches heavy queries (stats, sites, categories) for 1 hour in-memory.
- SSL via Let's Encrypt (certbot auto-renews). Expires July 4, 2026.
- Droplet: 2 vCPU / 2GB RAM / 2GB swap / $18/mo.
- **Old Railway Postgres** still exists but is no longer used. Can be decommissioned.

### Scoring Pipeline (no LLM)

Three algorithmic scores computed locally via `scripts/compute_scores.py`:
- **citation_rank**: Weighted inbound citation count (central=3x, provincial=2x, municipal=1.5x). PageRank-like.
- **algo_doc_type**: 19 document types from title regex (regulation, policy_issuance, action_plan, subsidy, explainer, etc.)
- **ai_relevance**: 0.0-1.0 keyword density score. Weighted terms (人工智能=10, 大模型=9, 算力=7...) with diversity bonus. Normalized by doc length.

Browse page supports filtering by doc type, AI relevance threshold, and sorting by citation rank or AI relevance.

### Classification (DeepSeek API)

Documents are classified via DeepSeek API (`scripts/classify_documents.py`) — adds English title, summary, doc_type, policy_significance, references_json. Paused at 24k/135k. Cost: ~$0.50/1k docs, concurrency 2 max.

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
