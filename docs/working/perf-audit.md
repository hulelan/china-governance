# Performance Audit — chinagovernance.com

Date: 2026-08-26. Method: `curl` timings against uvicorn directly on the droplet
(`http://localhost:8001`, bypassing nginx/auth), each endpoint run cold then warm.
Code read: `web/database.py`, `web/routers/pages.py`, `web/routers/api.py`,
`web/services/documents.py`. Query plans via `sqlite3 "file:documents.db?mode=ro"`
`EXPLAIN QUERY PLAN`. **Investigation only — nothing was changed on the box.**

## Environment facts

- DB `documents.db`: **279,451 docs**, page_size 4096 × page_count 2,528,574 =
  **~10.4 GB on disk** (bigger than the 4 GB "~4GB" note in CLAUDE.md). Box has
  **4 GB RAM** → the DB does **not** fit in OS page cache.
- uvicorn `--workers 2`. **One shared aiosqlite connection per worker**
  (`app.state.db`, opened once in `web/database.py:lifespan`). aiosqlite serves a
  connection from a single background thread, so **all DB queries in a worker are
  serialized** — effective DB concurrency for the whole site is **2**.
- PRAGMAs set by the app: only `cache_size = -32000` (32 MB) on the main conn.
  **No `mmap_size`**, no `synchronous`/`temp_store`/`busy_timeout` tuning.
  journal_mode = WAL (fine for RO readers).
- nginx `gzip on`, but **`gzip_types` is commented out** → only `text/html` is
  compressed. JSON API responses and any JS/CSS are served **uncompressed**.
  `location /static/` has `expires 7d` (assets are CDN-served anyway).
- In-process 1-hour caches exist for `get_stats`/`get_sites`/`get_categories`
  (`documents.py`), `_dashboard_cache`, `_chain_cache`, `lens` service, and
  `_network_cache` (`api.py`). `get_documents` (browse/homepage list) and
  `search_documents` are **NOT** cached.

## Measured timings (seconds)

Cold = first hit after the 11:11 app restart (empty in-proc cache + cold OS page
cache). Warm = repeat.

| Endpoint | Cold | Warm | Notes |
|---|---|---|---|
| `/` | **15.10** | 0.023 | heavy on first build, then 1h-cached |
| `/browse` (no filter) | 0.121 | 0.055 | uses covering `idx_documents_date`, LIMIT 50 |
| `/browse?site=gov` | **14.67** | 0.103 | temp B-tree sort of 20,180 rows (see below) |
| `/browse?ai_min=0.3` | 0.051 | 0.068 | scans date index, filters ai_relevance |
| `/document/2367` | 0.051 | 0.045 | PK lookup, fine |
| `/lens?q=人工智能` | **5.41** | 0.004 | 1h-cached in lens service |
| `/lens?doc=2367` | 0.072 | 0.005 | cached |
| `/structure` | 0.274 | 0.264 | modest |
| `/network` (page) | 0.016 | 0.016 | shell only |
| `/api/v1/network?min_degree=3` | **6.68** | 0.136 | citations⋈documents scan; 1h-cached; 885 KB uncompressed |
| `/api/v1/stats` | 0.002 | 0.002 | cached |
| `/search?q=人工智能` | **2.02** | 0.21 | NOT cached; warm still 0.2s |
| `/search?q=数据` (common term) | — | **0.75** | NOT cached; slow every time (COUNT join) |
| `/officials` | 0.012 | 0.002 | fine |

**Two distinct problems:**

- **(A) Cold-after-restart.** Every heavy endpoint's first hit is multi-second
  because the daily `daily_sync.sh` restart empties both the in-process cache and
  (effectively) the OS page cache for a 10 GB DB on a 4 GB box. `/` 15s,
  `/browse?site=gov` 14.7s, `/api/v1/network` 6.7s, `/lens` 5.4s are all cold disk
  reads. Under bot load these cold reads pin a worker → the "loads forever"
  symptom in CLAUDE.md.
- **(B) Always-slow regardless of cache.** `search_documents` is never cached:
  ~0.2s for a normal term, **~0.75s for a common term** (数据) warm, ~2s cold. The
  browse-by-site page query does a temp B-tree sort (cheap warm, brutal cold).

## Root-cause diagnostics

**`/browse?site=gov` page query** — `EXPLAIN QUERY PLAN`:
```
SEARCH d USING INDEX idx_documents_site (site_key=?)
USE TEMP B-TREE FOR ORDER BY
```
`idx_documents_site` is `(site_key)` only; `idx_documents_date` is `(date_written)`
only. There is **no composite `(site_key, date_written)`**, so a site-filtered
browse must read **all 20,180 gov rows** (fetching `date_written` from the main
table row-by-row — cold random reads) and sort them in a temp B-tree, to return 50.
This is the single worst site-filter case and it is exactly the "click a `/browse?site=X`
link" path called out in Known Issues.

**`search_documents` COUNT** (`documents.py:419`) — `EXPLAIN QUERY PLAN`:
```
SCAN s VIRTUAL TABLE INDEX 0:M5
SEARCH d USING INTEGER PRIMARY KEY (rowid=?)
```
The total-count query is
`SELECT COUNT(*) FROM doc_search_seg s JOIN documents d ON d.id=s.rowid WHERE MATCH ?`.
When there is **no date/site filter** the `JOIN documents` is pointless but still
does one PK lookup **per match** — tens of thousands of random row lookups just to
count. For a common term that's the bulk of the 0.75s. (Same pattern in the trigram
COUNT at `documents.py:518`.)

**`/api/v1/network` (no filter)** joins all ~227k `citations` to `documents` and
filters `sd.document_number != ''` (`api.py:176`). Cold that's a 6.7s scan; it is
1h-cached so it mainly hurts right after each restart, and its 885 KB JSON ships
uncompressed.

---

## QUICK SAFE WINS (do these first)

### 1. Add composite index `(site_key, date_written)` — fixes browse-by-site
Eliminates the temp B-tree; the page query becomes an index range scan reading only
50 rows. Expected: `/browse?site=X` cold **14.7s → ~0.1s**, warm 0.1s → ~0.02s, and
far less memory churn per request. Additive index, ~30–60 MB, builds in a minute or
two. Zero query-semantics risk.
```sql
-- run on the droplet against documents.db (needs write; DB is source of truth)
CREATE INDEX IF NOT EXISTS idx_documents_site_date
  ON documents(site_key, date_written DESC);
ANALYZE documents;
```
(Optional, if citation_rank/ai_relevance site-sorts feel slow later:
`idx_documents_site_citrank (site_key, citation_rank DESC)` — but date is the default
sort and by far the common case, so ship the one above first.)

### 2. Enable nginx gzip for JSON/JS/CSS
`gzip_types` is commented out, so only HTML is compressed. Uncomment it so API JSON
(e.g. `/api/v1/network` 885 KB) and any JS/CSS compress ~6–10×. Expected: big-JSON
transfer **885 KB → ~90 KB**; helps every `/api/*` consumer and the network graph.
No app change, reload only.
```nginx
# in the http{} block of nginx.conf (uncomment the existing line), then add min-length:
gzip_types text/plain text/css application/json application/javascript
           text/xml application/xml application/xml+rss text/javascript;
gzip_min_length 1024;
gzip_vary on;
```
`nginx -t && systemctl reload nginx`. (HTML pages are already gzipped, so
`/browse`'s 452 KB HTML is fine over the wire — this is for the JSON/asset paths.)

### 3. SQLite `mmap_size` + bigger `cache_size` — cuts cold-read cost everywhere
The 10 GB DB on a 4 GB box means cold endpoints pay read() syscall overhead per
page. Memory-mapping lets SQLite fault pages in directly and share them, and a
larger page cache keeps hot b-tree/index pages resident between requests. Expected:
noticeable shave on all cold heavy endpoints (the 5–15s first-hits), 0 risk for a
read-only WAL reader. Edit `web/database.py:lifespan` (both connections):
```python
await conn.execute("PRAGMA mmap_size = 4294967296")   # 4 GB memory-map window
await conn.execute("PRAGMA cache_size = -262144")      # 256 MB page cache (was 32 MB)
await conn.execute("PRAGMA temp_store = MEMORY")        # temp B-trees in RAM
```
(Keep the officials conn's cache smaller, e.g. `-32000`.) Watch RSS after deploy —
2 workers × 256 MB cache is fine on 4 GB; mmap is demand-paged and counts against
page cache, not committed RSS.

### 4. Fire a warm-up ping after the daily restart
`daily_sync.sh` Phase 3 restarts uvicorn, which drops all caches; the first real
visitor eats the 15s cold build. Add a curl warm-up right after the restart so the
1h in-proc caches + OS page cache are primed before anyone hits it. No code change.
```bash
# after the uvicorn restart in daily_sync.sh Phase 3:
for p in / /browse "/browse?site=gov" /structure /network \
         "/api/v1/network?min_degree=3" "/api/v1/stats" "/officials"; do
  curl -s -o /dev/null "http://localhost:8001$p"
done
```
Expected: converts the daily 15s "first visitor" penalty into a background cost.

### 5. Drop the pointless JOIN in the search COUNT (small code change)
In `_search_seg_bm25` (`documents.py:419`) and the trigram COUNT (`:518`), when
there is no date/site clause, count straight off the FTS table instead of joining
`documents` per match:
```python
# when date_clause and site_clause are both empty:
total = await db.fetchval(
    "SELECT COUNT(*) FROM doc_search_seg WHERE doc_search_seg MATCH $1", match)
# else keep the existing JOIN form (the JOIN is only needed to filter by d.*)
```
Expected: common-term search **0.75s → ~0.15s** warm, ~2s → ~0.5s cold; every
no-filter search benefits. Low risk (only the count path, results unchanged).

---

## RISKIER / STRUCTURAL (higher payoff, needs care)

### R1. Replace the single shared connection with a small read-only pool
`app.state.db` is one aiosqlite connection → **all queries in a worker serialize on
one thread**. A single 2s search or 6s cold network stalls every other request in
that worker; with only 2 workers the whole site "loads forever" under bot load
(the documented incident). Move to a small pool (e.g. 4 RO connections round-robined,
or a connection-per-request from a bounded pool). This is the **highest-ROI fix for
concurrency/tail latency** but touches `database.py` + every `request.app.state.db`
call site — test carefully. Expected: heavy endpoints stop blocking light ones;
p99 under load drops dramatically. Risk: connection lifecycle bugs, more RAM
(each conn its own cache — size them down, e.g. `-32000` each).

### R2. Cache `get_documents` for the hot default/browse pages
Browse and homepage list aren't cached. A short TTL (e.g. 60–300s) keyed on the
filter tuple + page for the common cases (no filter, single `site=`) would absorb
repeat/bot traffic. Risk: slightly stale listings (acceptable; docs change nightly).

### R3. `--workers 3` on the 2-vCPU box
Already floated in CLAUDE.md. More workers = more concurrent DB threads to ride out
a slow query, but on 2 vCPUs it trades CPU contention for queue depth and adds a 3rd
32 MB→256 MB cache. Only worth it **after** R1; the connection pool is the real fix.
Risk: memory + CPU oversubscription. Measure before/after.

### R4. Pre-aggregate the network graph
`/api/v1/network` rebuilds from a 227k-row citations⋈documents scan on each cache
miss (6.7s cold). A materialized per-target inbound-count table (refreshed in
`daily_sync.sh` Phase 2b after citations rebuild) would make even cold misses instant.
Risk: extra pipeline step to keep in sync.

---

## Top 5 highest-ROI (ordered)

1. **Composite index `(site_key, date_written)`** — `/browse?site=X` cold
   **14.7s → ~0.1s**. One `CREATE INDEX`, zero risk. (Quick win #1)
2. **Connection pool (R1)** — kills the single-connection serialization that causes
   the "loads forever" stalls; biggest concurrency/tail-latency win. (Riskier)
3. **`mmap_size` + 256 MB `cache_size` + `temp_store=MEMORY`** — shaves the daily
   5–15s cold first-hits across all heavy endpoints; 3 PRAGMA lines, zero risk.
   (Quick win #3)
4. **nginx `gzip_types`** — API JSON 885 KB → ~90 KB (and all JS/CSS); one config
   line + reload. (Quick win #2)
5. **Drop the JOIN in search COUNT** — common-term search 0.75s → ~0.15s warm;
   plus a post-restart warm-up ping (#4) to hide the cold penalty. (Quick wins #5 + #4)
