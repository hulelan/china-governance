# Sync Runbook

Step-by-step guide for crawling new data and publishing to production. Covers the common pitfalls we've hit.

> **Architecture note (June 2026):** Railway/Postgres was removed. The droplet's
> `documents.db` is now the **source of truth** and the web app reads it directly
> (SQLite, `?mode=ro`). There is no more "sync to Postgres" step — crawlers run
> *on the droplet* via cron (`scripts/daily_sync.sh`) and "publish" is just a local
> WAL checkpoint + `systemctl restart chinagovernance`. See CLAUDE.md → Architecture
> for the authoritative flow. The crawler-authoring pitfalls below are still valid.

## Quick Sync (existing sites, no schema changes)

For pulling in updated body text, new docs from existing crawlers, or PDF extractions:

```bash
# 1. Run your crawl/extraction against documents.db directly (on the droplet)
python3 -m crawlers.gkmlpt --site sz
python3 scripts/extract_pdf_text.py --site sz

# 2. Publish in place (droplet is the source of truth — no rsync/Postgres)
sqlite3 documents.db "PRAGMA wal_checkpoint(TRUNCATE);"
systemctl restart chinagovernance

# 3. Verify
curl -s "https://www.chinagovernance.com/api/v1/stats" | python3 -m json.tool
```

## Media Sources (LatePost)

LatePost articles are crawled from 163.com (NetEase). They use `admin_level = "media"` in the sites table, which separates them from government documents on the website via the Source filter.

```bash
# 1. Crawl LatePost (incremental — skips already-crawled articles)
python3 -m crawlers.latepost

# 2. List available articles without fetching
python3 -m crawlers.latepost --list-only

# 3. Publish (droplet only — WAL checkpoint + restart, see Quick Sync above)
sqlite3 documents.db "PRAGMA wal_checkpoint(TRUNCATE);" && systemctl restart chinagovernance
```

**Limitations:** The 163.com channel page only shows ~85 recent articles (no pagination API). Run regularly to capture new articles. The crawler is fully incremental — re-running skips articles already in the database.

## Adding New Sites (new crawlers, new site_keys)

New sites need no special publish step — because the web app reads `documents.db`
directly, once the rows are in the DB they're live after a restart.

```bash
# 1. Crawl to a separate DB to avoid lock contention
python3 -m crawlers.beijing --db documents_new.db

# 2. Merge into main DB
python3 scripts/merge_db.py documents_new.db --dry-run   # preview first
python3 scripts/merge_db.py documents_new.db              # merge

# 3. Publish (droplet only — WAL checkpoint + restart)
sqlite3 documents.db "PRAGMA wal_checkpoint(TRUNCATE);" && systemctl restart chinagovernance

# 4. Verify
curl -s "https://www.chinagovernance.com/api/v1/stats" | python3 -m json.tool
```

## Pitfalls We've Hit

### 1. Database locked errors
**Cause:** Two writers on documents.db at the same time (e.g., crawl + sync, or two crawlers).

**Prevention:**
- Never run two write operations against documents.db simultaneously
- Use `--db documents_new.db` for new crawls, then merge after
- Keep crawler concurrency low (2 writers max — see CLAUDE.md → SQLite Concurrency Rules)

**Recovery:** Just re-run the failed command after the other finishes.

### 2. Body extraction returns 0 for all docs
**Cause:** The CSS selector for the body container doesn't match the site's HTML.

**Diagnosis:**
```bash
# Fetch a doc and check what divs exist
python3 -c "
from crawlers.base import fetch
import re
html = fetch('URL_OF_A_DOC')
ids = re.findall(r'<div[^>]*id=[\"\\']([^\"\\']*)[\"\\'\\']', html)
classes = re.findall(r'<div[^>]*class=[\"\\']([^\"\\']*)[\"\\'\\']', html)
print('IDs:', ids[:15])
print('Classes:', [c for c in classes[:20] if c.strip()])
"
```
Then update `_extract_body()` in the crawler with the correct selector.

### 3. Regex hangs on large pages
**Cause:** `re.DOTALL` with `.*?` on pages with 1000+ elements causes O(n²) backtracking.

**Fix:** Extract the target container first (e.g., `.default_news` section), then run patterns on the smaller substring. Check for element presence before running expensive patterns.

### 4. WebFetch/AI reports wrong HTML structure
**Cause:** The AI model summarizing HTML may report `<div>` when it's actually `<p>`, or say dates are plain text when they're in `<span>`.

**Fix:** Always verify with `repr()` of raw HTML from `crawlers.base.fetch()`, not from WebFetch summaries.

## Classifying New Documents

After crawling new docs, classify them with DeepSeek API to add English titles, summaries, importance, categories, and topics. Classifications land directly in `documents.db` — no separate push step. (On the droplet, `daily_sync.sh` Phase 2 runs this automatically for unclassified docs.)

```bash
# 1. Set API key (get one at https://platform.deepseek.com)
export DEEPSEEK_API_KEY="sk-..."

# 2. Dry run — check output quality on a few docs
python3 scripts/classify_documents.py --dry-run --limit 5

# 3. Run classification (resumable — skips already-classified docs)
#    Concurrency 2 is the HARD MAX. Higher silently returns empty responses
#    (not 429s) — the script default is 2 and warns if you override it.
python3 scripts/classify_documents.py --concurrency 2

# 4. Publish (droplet only — WAL checkpoint + restart)
sqlite3 documents.db "PRAGMA wal_checkpoint(TRUNCATE);" && systemctl restart chinagovernance

# 5. Verify
curl -s "https://www.chinagovernance.com/api/v1/stats" | python3 -m json.tool
```

### What it extracts per document
| Field | Description |
|-------|-------------|
| `title_en` | English translation of the title |
| `summary_en` | 1-2 sentence English summary |
| `importance` | `high` / `medium` / `low` — see rubric in `docs/implementation/classification-plan.md` |
| `category` | One of: `major_policy`, `regulation`, `normative`, `budget`, `personnel`, `administrative`, `report`, `subsidy`, `other` |
| `policy_area` | Chinese topic label (e.g., "人工智能") |
| `topics` | JSON array of English topic tags |

### Cost & speed
- **DeepSeek API**: ~$0.49 per 1,000 docs, ~0.5 docs/sec at concurrency 2
- **~1.4% of docs** will fail (DeepSeek content filter) — acceptable loss
- Full corpus (110k docs) costs ~$50 and takes ~6 hours
- Script is resumable — safe to interrupt and restart

## Checklist

Before syncing to production:
- [ ] Crawl/extraction completed without errors
- [ ] `python3 -m crawlers.gkmlpt --stats` shows expected counts
- [ ] No other process is writing to documents.db
- [ ] After sync, verify with the `/api/v1/stats` endpoint
