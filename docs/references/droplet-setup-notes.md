# Singapore Droplet — Setup & Operations Notes

*Created 2026-03-27. Documents the DigitalOcean droplet setup, connectivity findings, and daily sync pipeline.*

## Infrastructure

- **Provider:** DigitalOcean
- **Region:** SGP1 (Singapore)
- **Specs:** 1 vCPU, 1GB RAM, 25GB disk, Ubuntu 24.04 LTS
- **IP:** 152.42.184.25
- **Purpose:** Always-on crawling + classification + Postgres sync

## Setup

Setup script: `scripts/setup_droplet.sh` — installs Python, clones repo, creates venv, installs deps, sets up cron.

```bash
ssh root@152.42.184.25
bash <(curl -s https://raw.githubusercontent.com/hulelan/china-governance/main/scripts/setup_droplet.sh)
```

Initial DB seeded via rsync from Mac (~1.5GB, ~60 min over the wire):
```bash
rsync -avz --progress documents.db "root@152.42.184.25:/root/china-governance/"
```

## Daily Sync Pipeline

Cron runs `scripts/daily_sync.sh` at **6 AM SGT** (22:00 UTC previous day):

1. **Crawl** all sources (gkmlpt --sync, central ministries, provinces, sz_invest)
2. **Classify** new docs via DeepSeek API (concurrency 2)
3. **Sync** to Railway Postgres via `sync_classifications.py`

Manual run:
```bash
cd /root/china-governance && source .venv/bin/activate && source .env
./scripts/daily_sync.sh          # Full pipeline
./scripts/daily_sync.sh --crawl  # Crawl only
```

## Connectivity from Singapore

### What works perfectly
- **All gkmlpt sites** (HTTP) — zero errors, good speed
- **Central ministries** (gov.cn, ndrc.gov.cn, mof.gov.cn, mee.gov.cn) — work fine
- **Province crawlers** (beijing, shanghai, jiangsu) — work fine
- **DeepSeek API** — no issues from Singapore

### Known issues

**IPv6 failures (FIXED):** Chinese .gov.cn sites return AAAA DNS records but don't actually serve traffic over IPv6 from overseas. Python tries IPv6 first, fails with "Network is unreachable", then retries on IPv4. Fixed by monkey-patching `socket.getaddrinfo` in `crawlers/base.py` to force IPv4. Zero errors after fix.

**TLS handshake retries (sz_invest only):** The HTTPS sections (sz.gov.cn, fgw.sz.gov.cn, lg.gov.cn) hit `curl rc=35` (SSL handshake failure) on first attempt but succeed on retry 2-3. This is a server-side TLS negotiation issue — the `sz_invest` crawler uses `curl -sk` subprocess which handles it via retries. Not worth fixing further — adds ~30s total to the crawl.

**Sites that are unreachable everywhere (not Singapore-specific):**
- Dongguan, Foshan, Meizhou, Maoming, Qingyuan — DNS/timeout/Cloudflare blocks
- Bao'an district — gkmlpt endpoint unreachable
- These fail from Mac too, not a Singapore issue

## Development Workflow

```
Your Mac (development):
  1. Write/test new crawlers locally
  2. git push to main

Droplet (production):
  3. Daily cron does git pull → crawl → classify → sync to Postgres
  4. Website auto-updates
```

### Moving local crawl results to droplet

**Option A — Full DB sync (simple, ~60 min):**
```bash
rsync -avz --progress documents.db "root@152.42.184.25:/root/china-governance/"
```

**Option B — Separate DB merge (fast, for small batches):**
```bash
# On Mac: crawl to temp DB
python3 -m crawlers.new_thing --db documents_new.db

# Rsync small file
rsync -avz documents_new.db "root@152.42.184.25:/root/china-governance/"

# On droplet: merge
ssh root@152.42.184.25 "cd /root/china-governance && source .venv/bin/activate && python3 scripts/merge_db.py documents_new.db"
```

**Option C — Let droplet recrawl (easiest):**
Just push the new crawler code. The daily cron will crawl it fresh. No rsync needed.

## Environment Variables (.env)

```
DEEPSEEK_API_KEY=sk-...       # For classification
DATABASE_URL=postgresql://... # Railway Postgres for production sync
TELEGRAM_BOT_TOKEN=...        # Crawler bot notifications (optional)
TELEGRAM_USER_ID=...          # Telegram user for notifications (optional)
```

## Resource Usage

- **Disk:** documents.db is ~1.5GB, raw_html can grow. 25GB total, plenty of room.
- **RAM:** Crawling uses ~50MB. Classification (API calls) uses ~30MB. Well within 1GB.
- **CPU:** Crawling is I/O-bound (waiting on HTTP). Never exceeds 15% CPU.
- **Bandwidth:** ~150KB/s peak during crawls. Well within DO limits.
- **Runtime:** Full daily sync takes ~30-60 min (crawl) + ~10 min (classify new) + ~5 min (Postgres sync).
