# Sync Runbook

Step-by-step guide for crawling new data and pushing to production. Covers the common pitfalls we've hit.

## Quick Sync (existing sites, no schema changes)

For pushing updated body text, new docs from existing crawlers, or PDF extractions:

```bash
# 1. Run your crawl/extraction against documents.db directly
python3 -m crawlers.gkmlpt --site sz
python3 scripts/extract_pdf_text.py --site sz

# 2. Incremental sync to production (fast — only inserts new rows)
DATABASE_URL="postgresql://postgres:yNpVZKsSVTBvGNozjIbgBsKsQAnrJQdF@gondola.proxy.rlwy.net:48854/railway" \
  python3 scripts/sqlite_to_postgres.py

# 3. Verify
curl -s "https://china-governance-production.up.railway.app/api/v1/stats" | python3 -m json.tool
```

## Adding New Sites (new crawlers, new site_keys)

The incremental sync **only inserts docs for sites that already exist in Postgres**. New site_keys require a full rebuild.

```bash
# 1. Crawl to a separate DB to avoid lock contention
python3 -m crawlers.beijing --db documents_new.db

# 2. Merge into main DB
python3 scripts/merge_db.py documents_new.db --dry-run   # preview first
python3 scripts/merge_db.py documents_new.db              # merge

# 3. Full rebuild to production (required for new sites)
DATABASE_URL="postgresql://postgres:yNpVZKsSVTBvGNozjIbgBsKsQAnrJQdF@gondola.proxy.rlwy.net:48854/railway" \
  python3 scripts/sqlite_to_postgres.py --drop

# 4. Verify
curl -s "https://china-governance-production.up.railway.app/api/v1/stats" | python3 -m json.tool
```

## Pitfalls We've Hit

### 1. Database locked errors
**Cause:** Two writers on documents.db at the same time (e.g., crawl + sync, or two crawlers).

**Prevention:**
- Never run two write operations against documents.db simultaneously
- Use `--db documents_new.db` for new crawls, then merge after
- The production sync (`sqlite_to_postgres.py`) reads SQLite — it won't lock the DB itself, but if it's running while a crawler writes, the crawler may fail

**Recovery:** Just re-run the failed command after the other finishes.

### 2. Incremental sync doesn't push new sites
**Cause:** `sqlite_to_postgres.py` (without `--drop`) only inserts docs for site_keys already in Postgres.

**Fix:** Use `--drop` for a full rebuild whenever you've added new site_keys. This drops all Postgres tables and re-inserts everything from SQLite.

### 3. Body extraction returns 0 for all docs
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

### 4. Regex hangs on large pages
**Cause:** `re.DOTALL` with `.*?` on pages with 1000+ elements causes O(n²) backtracking.

**Fix:** Extract the target container first (e.g., `.default_news` section), then run patterns on the smaller substring. Check for element presence before running expensive patterns.

### 5. WebFetch/AI reports wrong HTML structure
**Cause:** The AI model summarizing HTML may report `<div>` when it's actually `<p>`, or say dates are plain text when they're in `<span>`.

**Fix:** Always verify with `repr()` of raw HTML from `crawlers.base.fetch()`, not from WebFetch summaries.

## Checklist

Before syncing to production:
- [ ] Crawl/extraction completed without errors
- [ ] `python3 -m crawlers.gkmlpt --stats` shows expected counts
- [ ] No other process is writing to documents.db
- [ ] If new site_keys were added, use `--drop` (not incremental)
- [ ] After sync, verify with the `/api/v1/stats` endpoint
