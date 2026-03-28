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

## Media Sources (LatePost)

LatePost articles are crawled from 163.com (NetEase). They use `admin_level = "media"` in the sites table, which separates them from government documents on the website via the Source filter.

```bash
# 1. Crawl LatePost (incremental — skips already-crawled articles)
python3 -m crawlers.latepost

# 2. List available articles without fetching
python3 -m crawlers.latepost --list-only

# 3. Sync to production
DATABASE_URL="postgresql://postgres:yNpVZKsSVTBvGNozjIbgBsKsQAnrJQdF@gondola.proxy.rlwy.net:48854/railway" \
  python3 scripts/sqlite_to_postgres.py
```

**Limitations:** The 163.com channel page only shows ~85 recent articles (no pagination API). Run regularly to capture new articles. The crawler is fully incremental — re-running skips articles already in the database.

## Adding New Sites (new crawlers, new site_keys)

The incremental sync handles new sites — it uses `INSERT ... ON CONFLICT DO NOTHING` for sites, categories, and documents. Use `--drop` only if the schema has changed (new columns added to the CREATE TABLE in `sqlite_to_postgres.py`).

```bash
# 1. Crawl to a separate DB to avoid lock contention
python3 -m crawlers.beijing --db documents_new.db

# 2. Merge into main DB
python3 scripts/merge_db.py documents_new.db --dry-run   # preview first
python3 scripts/merge_db.py documents_new.db              # merge

# 3. Sync to production (incremental works for new sites)
DATABASE_URL="postgresql://postgres:yNpVZKsSVTBvGNozjIbgBsKsQAnrJQdF@gondola.proxy.rlwy.net:48854/railway" \
  python3 scripts/sqlite_to_postgres.py

# 4. Verify
curl -s "https://china-governance-production.up.railway.app/api/v1/stats" | python3 -m json.tool
```

**When to use `--drop`:** Rarely needed. The incremental sync now auto-adds missing columns via ALTER TABLE. Use `--drop` only when you need to push updated data for existing docs (e.g., body text backfill) or to fix a corrupted Postgres state.

## Pitfalls We've Hit

### 1. Database locked errors
**Cause:** Two writers on documents.db at the same time (e.g., crawl + sync, or two crawlers).

**Prevention:**
- Never run two write operations against documents.db simultaneously
- Use `--db documents_new.db` for new crawls, then merge after
- The production sync (`sqlite_to_postgres.py`) reads SQLite — it won't lock the DB itself, but if it's running while a crawler writes, the crawler may fail

**Recovery:** Just re-run the failed command after the other finishes.

### 2. Incremental sync doesn't update existing docs
**Cause:** `sqlite_to_postgres.py` uses `ON CONFLICT DO NOTHING` — it inserts new rows but won't update body text or metadata for docs already in Postgres.

**Fix:** Use `--drop` for a full rebuild when you need to push updated body text for existing docs (e.g., after PDF extraction or body backfill). New sites and new docs work fine with incremental.

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

## Classifying New Documents

After crawling new docs, classify them with DeepSeek API to add English titles, summaries, importance, categories, and topics. Then push to Postgres.

```bash
# 1. Set API key (get one at https://platform.deepseek.com)
export DEEPSEEK_API_KEY="sk-..."

# 2. Dry run — check output quality on a few docs
python3 scripts/classify_documents.py --dry-run --limit 5

# 3. Run classification (resumable — skips already-classified docs)
#    Concurrency 2 is the safe max to avoid DeepSeek rate limit issues.
#    Concurrency 5 is faster but may hit empty-response errors.
python3 scripts/classify_documents.py --concurrency 2

# 4. Push classifications to Postgres (no full rebuild needed)
DATABASE_URL="postgresql://postgres:yNpVZKsSVTBvGNozjIbgBsKsQAnrJQdF@gondola.proxy.rlwy.net:48854/railway" \
  python3 scripts/sync_classifications.py

# 5. Verify
curl -s "https://china-governance-production.up.railway.app/api/v1/stats" | python3 -m json.tool
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

### sync_classifications.py details
1. ALTER TABLEs to add any missing classification columns
2. Batch-UPDATEs classification fields for existing docs (temp table + bulk UPDATE)
3. Syncs sites/categories (ON CONFLICT DO NOTHING)
4. INSERTs any new docs not yet in Postgres
5. Verifies final counts

Much faster than `--drop` since it only touches classification columns, not the full document payload.

## Checklist

Before syncing to production:
- [ ] Crawl/extraction completed without errors
- [ ] `python3 -m crawlers.gkmlpt --stats` shows expected counts
- [ ] No other process is writing to documents.db
- [ ] After sync, verify with the `/api/v1/stats` endpoint
