# Nightly Phase 1 timing audit

Date: 2026-10-07. Read-only. No crawler was run and no write touched the DB.

This closes the TODO that has sat in CLAUDE.md Open Questions since July 2026
("confirm each runs incremental/`--sync`, time the worst offenders, raise the cap
selectively or optimize"). Everything below is derived from evidence already on
the droplet: 11 nightly logs and 11 nightly manifests.

## Headline

Phase 1 takes 240 to 271 minutes every night and that number is stable. Tonight
it ran 06:00:11 to 10:25:27 (265 min) for 480 new documents out of 249,175 seen.
In the four most recent steady-state nights the whole pipeline added 242 to 300
documents, and roughly 180 of those came from four media crawlers that cost under
15 minutes combined.

Four crawlers hit the 1800s `CRAWLER_TIMEOUT` every single night. Together they
burn 120 of the 252 median minutes and return close to zero new rows.

| night | Phase 1 (min) | crawlers | capped at 1800s |
|---|---|---|---|
| 2026-09-27 | 240.6 | 85 | gkmlpt, dept group, beijing |
| 2026-09-28 | 266.8 | 85 | gkmlpt, dept group, beijing |
| 2026-09-29 | 267.8 | 85 | gkmlpt, dept group, beijing |
| 2026-09-30 | 271.3 | 85 | gkmlpt, dept group, beijing |
| 2026-10-01 | 260.0 | 85 | gkmlpt, dept group, beijing, zhejiang |
| 2026-10-02 | 270.0 | 85 | gkmlpt, dept group, beijing, zhejiang |
| 2026-10-03 | 255.5 | 85 | gkmlpt, dept group, beijing, zhejiang |
| 2026-10-04 | 248.8 | 85 | gkmlpt, dept group, beijing, zhejiang |
| 2026-10-05 | 248.4 | 85 | gkmlpt, dept group, beijing, zhejiang |
| 2026-10-06 | 253.2 | 85 | gkmlpt, dept group, beijing, zhejiang |
| 2026-10-07 | 265.3 | 86 | gkmlpt, dept group, beijing, zhejiang |

The July hypothesis was wrong in its list. It named 11 crawlers hitting the cap
(cac, samr, mofcom, beijing, shanghai, jiangsu, suzhou, heilongjiang, xinhua,
miit, most). Measured today, only 4 do, and 7 of those 11 now finish in under 70
seconds. The cap is not the problem. Three full-archive re-walks and one dead
province are.

## Method (reproducible)

Timings come from the `[HH:MM:SS]   Crawling <name>...` lines that `run_crawler`
writes, differenced against the next such line (or `Phase 1 done`). Yield comes
from differencing the nightly pre-crawl manifests, which is authoritative because
each manifest is `SELECT id, url, site_key, LENGTH(body) FROM documents` with no
filter. The crawlers' own "N new" log lines are NOT authoritative, for a reason
documented under gkmlpt below.

```bash
# wall time per crawler, per night
grep -E '^\[[0-9:]+\]   Crawling |Phase 1 done' logs/daily-2026100*-0600.log

# authoritative new-row yield per site, per night (no DB load)
cd backups && python3 -c "
import csv,collections
def load(d): return {r[0]:r[2] for r in csv.reader(open(f'manifest_{d}.csv',errors='replace')) if len(r)>=3}
a,b=load('20261006'),load('20261007')
print(collections.Counter(b[i] for i in b.keys()-a.keys()).most_common(15))"

# per-site row counts, to prove a site is frozen
cd backups && for d in 20261004 20261005 20261006 20261007; do \
  printf "%s zjj=%s bj=%s\n" $d $(grep -c ',zjj,' manifest_$d.csv) $(grep -c ',bj,' manifest_$d.csv); done
```

## 1. Per-crawler timing table

Medians over the 11 nights. `capped` counts nights at 1800s. `new/run` is the
manifest-diff median, not the crawler's self-report. `s/new doc` divides median
wall time by median yield.

Ranked by wasted time, which is wall time at a median yield of zero.

| rank | crawler | median wall | max | capped | new/run (median) | new (sum of 10 nights) | s per new doc | cause |
|---|---|---|---|---|---|---|---|---|
| 1 | `zhejiang` | 1800s | 1800s | 7/11 | 0 | 0 | infinite | (d) dead, all sections |
| 2 | `govcms --group dept` | 1800s | 1801s | 11/11 | 0 to 1 | low | ~1800 | (b)+(c) 232 sites, cq_* dead |
| 3 | `beijing` | 1800s | 1801s | 11/11 | 0 | 17 | ~1060 | (a) full re-walk, never finishes |
| 4 | `gkmlpt --sync` | 1800s | 1801s | 11/11 | 0 | 19 | ~950 | (a)+bug, reaches 4 of 63 sites |
| 5 | `jiangsu` | 1276s | 1753s | 0 | 0 | 3 | ~4250 | (a) 262 pages, 15,909 links |
| 6 | `mof` | 626s | 693s | 0 | 0 | 12 | ~520 | (a) gazette re-walk |
| 7 | `chongqing` | 577s | 578s | 0 | 0 | 0 | infinite | (a) full re-walk |
| 8 | `most` | 409s | 528s | 0 | 0 | 5 | ~820 | (a) full re-walk |
| 9 | `ipc_court` | 409s | 467s | 0 | 0 | 13 | ~315 | (c) 92 retries/night |
| 10 | `wuhan` | 206s | 232s | 0 | 0 | 0 | infinite | (a) full re-walk |
| 11 | `hangzhou` | 196s | 198s | 0 | 0 | 0 | infinite | (a) full re-walk |
| 12 | `sic` | 168s | 193s | 0 | 0 | 0 | infinite | (a) full re-walk |
| 13 | `govcms (jinan)` | 156s | 256s | 0 | 0 | ~1 | ~1560 | (a) full re-walk |
| 14 | `mee` | 94s | 113s | 0 | 0 | 0 | infinite | (a) full re-walk |
| 15 | `ndrc` | 81s | 111s | 0 | 0 | 0 | infinite | (a) full re-walk |

The productive half of Phase 1, for contrast. These are the crawlers worth their
wall time.

| crawler | median wall | new/run | s per new doc |
|---|---|---|---|
| `govcms --group city2` (71 sites) | 536s | 49 | 11 |
| `govcms --group city` (37 sites) | 607s | 23 | 26 |
| `guancha --deep` | 588s | 39 | 15 |
| `govcms --group city3` (20 sites) | 234s | 12 | 20 |
| `ifeng` | 133s | 52 | 2.6 |
| `xinhua` | 129s | 7 | 18 |
| `stdaily` | 63s | 62 | 1.0 |
| `tsinghua_aiig` | 61s | 26 | 2.3 |
| `govcms (qinghai)` | 40s | 15 | 2.7 |
| `govcms (chinapeace)` | 31s | 12 | 2.6 |

Sum of medians across all 85 crawlers: 15,119s, 252 minutes. The 15 crawlers in
the waste table account for 11,738s, 196 minutes, or 78 percent of Phase 1.

Note on 2026-10-07's 2,513-row jump: it is a first crawl of newly added sites
(`npc_dbgz` 796, `jsrd` 447, `nanjing` 139, `szd_*`/`njd_*` districts, `cppcc` 96),
not steady-state nightly yield. Measured. The honest steady-state figure is the
242 to 300 of 2026-10-03 through 2026-10-06.

## 2. Why each slow one is slow

### zhejiang: (d) dead. Drop it.

Measured, 2026-10-06 run: 22 sections attempted, 21 failed to fetch, 42 retry
lines, 5 of 7 departments reached before the kill, 0 documents stored. Zero new
rows across all 11 nights.

```
09:40:08 [INFO] --- 浙江省发展和改革委员会 / 行政规范性文件 (fzggw/gfxwj) ---
09:40:29 [WARNING]   Retry 1/3 ... <urlopen error _ssl.c:983: The handshake operation timed out>
09:40:50 [WARNING]   Retry 2/3 ... <urlopen error _ssl.c:983: The handshake operation timed out>
09:41:33 [WARNING]   curl_cffi fallback failed ... curl: (28) Connection timed out after 20002 ms
09:41:33 [ERROR] Failed to fetch https://fzggw.zj.gov.cn/col/col1229565788/index.html
```

That is 85 seconds for one dead section URL. Measured. The arithmetic of
`crawlers/base.py` explains it: `fetch(timeout=20, retries=3)` tries two TLS
contexts, then falls back to `_fetch_impersonate` with another 20s budget. 22
sections times 85s is 31 minutes, which is exactly the observed 1800s cap.

Dead hosts, by failure count on 2026-10-06: `fzggw.zj.gov.cn` 28,
`kjt.zj.gov.cn` 24, `jxt.zj.gov.cn` 16, `sft.zj.gov.cn` 12, `sthjt.zj.gov.cn` 4.
All of them. The crawler's own docstring already records that `www.zj.gov.cn` is
WAF-blocked from US IPs and claims the department subdomains are reachable. That
claim is no longer true. The run also got measurably worse on 2026-10-01: wall
time went 1424, 1433, 1432, 1443 and then 1800 for every night since.

### govcms --group dept: (b) genuinely large, plus (c) a dead sub-family.

Measured: `SITES` carries 232 sites tagged `group=dept`. The 2026-10-06 run
completed 160 of them before the kill, so 72 dept sites are never crawled on any
night, and because the iteration order is fixed it is always the same 72.

Yield on 2026-10-06 was one document, `[fj_jtyst] done: 1 new`. Measured.

The failures cluster entirely in the Chongqing bureau family. Failing hosts by
count: `fzggw.cq.gov.cn` 18, `dsjj.cq.gov.cn` 18, `czj.cq.gov.cn` 18,
`cgj.cq.gov.cn` 18, `gbdsj.cq.gov.cn` 8, `gaj.cq.gov.cn` 8, `gxhzs.cq.gov.cn` 7,
`gxq.cq.gov.cn` 4. 136 timeout or failure lines in the span. The non-cq failures
are noise: 2 for `kxjst.jiangsu.gov.cn`, 1 each for two `beijing.gov.cn` bureaus
and `czt.ln.gov.cn`.

### beijing: (a) full re-walk that never completes.

`crawlers/beijing.py:434-450` reads the total page count, then accumulates every
page into one list before any deduplication:

```python
total_pages = _get_total_pages(html)
all_items = _parse_listing(html, first_url)
for page in range(1, total_pages):
    page_url = _section_url(section, page)
    page_html = fetch(page_url)
    all_items.extend(_parse_listing(page_html, page_url))
```

There is no early exit. The dedup is per item, after the walk, at line 459, and
it correctly includes the partial-index predicate:

```python
existing = conn.execute(
    "SELECT id, body_text_cn FROM documents WHERE url = ? AND url != ''", (doc_url,)
).fetchone()
if existing and existing[1]:
    stored += 1
    continue
```

Two consequences, both measured in the 2026-10-06 log. First, the walk enumerates
6,821 documents and the process is killed at `Progress: 2640/6821 stored`, so the
trailing sections are never reached at all on any night. Second, the skip
condition is `existing and existing[1]`, meaning a document already in the DB with
an EMPTY body is re-fetched every single night. The DB says `bj` has 8,490 rows of
which 1,628 have no body, and that 1,628 has not moved. The log shows 712 body
fetches in 1800s, about 2.5s each. That is the actual time sink: Beijing spends
its whole budget re-fetching bodies that do not extract.

`bj` row count across four consecutive manifests: 8490, 8490, 8490, 8490.
Measured. Zero net rows.

### gkmlpt --sync: (a) plus a diff bug that re-fetches 133 bodies nightly.

Measured, 2026-10-06: the sweep reached 4 of the 63 sites in `SITES` and completed
3 of them before the kill.

```
06:00:11 === Sync Shenzhen Main Portal ===      06:01:36  New: 6   | Deleted: 234 | Unchanged: 892
06:01:36 === Sync Housing & Construction ===    06:09:05  New: 133 | Deleted: 122 | Unchanged: 2547
06:09:05 === Sync S&T Innovation Bureau ===     06:24:50  New: 47  | Deleted: 67  | Unchanged: 2465
06:24:50 === Sync Development & Reform Commission ===     (killed)
```

So 59 of 63 gkmlpt sites are not synced on any night, and the order is fixed, so
it is always the same 59.

The reported "New: 133" is a phantom. `zjj` has held exactly 2,719 rows across
2026-10-04, 05, 06 and 07, while the log claims 133 additions on 10-06. Measured.
The inferred mechanism is in `crawlers/gkmlpt.py:941`:

```python
existing_rows = conn.execute(
    """SELECT id, title, ... FROM documents WHERE site_key = ?""", (site_key,))
...
new_ids = api_ids - db_ids
```

`db_ids` is scoped to one `site_key`. A gkmlpt post id that already exists in the
DB under a DIFFERENT `site_key`, which happens for documents cross-posted between
a Shenzhen bureau portal and the main portal, is absent from `db_ids`, so it is
classified new. The insert then takes the `ON CONFLICT(id) DO UPDATE SET
body_text_cn=excluded.body_text_cn` branch at line 720, returns True, increments
`added`, and produces no new row. The body is re-fetched over the network every
night forever, and the other site's `body_text_cn` is overwritten in the process.
Inferred from the code plus the frozen row counts; worth confirming with a direct
query before anyone touches it.

The 234 and 122 "deleted" counts each night are the same instability from the
other side. The listing API's pagination breaks early, visible as dozens of
`API error for category NNN page N: HTTP Error 404` warnings, so a different
subset of the catalogue appears each night and documents flip between deleted and
new. That churn, not new content, is what the sweep is paying for.

### jiangsu: (a) full re-walk of a 16k-link archive.

Same `for page in range(1, total_pages)` shape at `crawlers/jiangsu.py:343`, with
no early exit. Measured on 2026-10-06:

```
08:41:52 [INFO]   262 listing pages
09:02:41 [INFO]   Found 15909 document links
```

21 minutes to enumerate 15,909 links for a median of 0 new rows, 3 over ten
nights. The `jpage` dataproxy endpoint also times out intermittently from NYC
(three `Retry` lines in that span), and the walk then hits a pair of permanently
404 URLs repeatedly: `art_46143_8089016.html` and `art_46143_8089002.html` appear
three times each in the body-fetch phase.

### mof: (a) a gazette archive re-walked nightly.

Measured, 2026-10-06:

```
06:34:35 [INFO] --- Section: 财政文告 (czwg, gazette archive) ---
06:41:26 [INFO]   Done: 0 stored, 0 bodies, 1880 already existed
```

411 seconds, two thirds of mof's run, to re-confirm 1,880 documents it already
has. The `zcfb` and `czxw` sections each report `Done: 500 documents stored,
24 bodies fetched` and `500 stored, 20 bodies`, which is the same empty-body
re-fetch pattern as Beijing on a smaller scale.

### ipc_court: (c) a flaky host, nothing structural.

409s median for 13 documents over ten nights. 92 retry lines per night, split
46 and 46 across `Retry 1/3` and `Retry 2/3`, all against
`https://ipc.court.gov.cn`. Every request to the host needs two attempts. Nothing
in the crawler is wrong; the host is slow from NYC.

### chongqing, wuhan, hangzhou, sic, most, mee, ndrc, govcms (jinan): (a) full re-walk, small archive.

All eight share the exact `for page in range(1, total_pages)` list loop with no
early exit and the same `existing and existing[1]` body-gated skip. Verified by
grep in all eight files. They are cheap individually, 81s to 577s, but they sum to
2,088s, 35 minutes, for a combined median of zero new rows. `cq` additionally
carries 587 bodyless rows of 1,295 and `suzhou` 1,022 of 4,918, so both pay the
nightly body re-fetch tax.

### Dead sections to drop, named

- All of `zhejiang`. 21 of the 22 sections reached fail every night, across
  `fzggw`, `kjt`, `jxt`, `sft` and `sthjt`. The remaining two departments in the
  config, `czt` and `mzt`, are never reached before the kill. Zero documents in
  11 nights.
- The Chongqing bureau subdomains inside `group=dept`: `fzggw.cq.gov.cn`,
  `dsjj.cq.gov.cn`, `czj.cq.gov.cn`, `cgj.cq.gov.cn`, `gbdsj.cq.gov.cn`,
  `gaj.cq.gov.cn`, `gxhzs.cq.gov.cn`, `gxq.cq.gov.cn`.
- The two permanently-404 Jiangsu detail URLs re-requested each night,
  `art_46143_8089016.html` and `art_46143_8089002.html`.
- The gkmlpt listing API's phantom second and third pages, which 404 on nearly
  every category on every site. Cosmetic in cost but they are the reason the
  deleted/new churn exists.

## 3. The early-exit question, concretely

The dedup lookup every one of these crawlers already uses is correct:
`WHERE url = ? AND url != ''`. The partial index `idx_documents_url` is defined
`WHERE url != ''`, so any new early-exit check must carry that predicate too or it
full-scans 323k rows. Verified present in beijing, jiangsu, chongqing, mof, wuhan,
hangzhou, sic and most.

The proposed rule is: while walking listing pages, if every URL on a page is
already in `documents`, stop paginating.

**Safe.** These are 政府信息公开 archives served newest-first by page index, where
page 0 is `index.html` and page N is `index_N.html`, and the crawler never relies
on the full walk for revision detection because its skip test is a plain
URL-presence check that discards everything it already has anyway.

- `beijing` (`bj`). Biggest win. Needs the second fix below to matter.
- `jiangsu` (`js`).
- `chongqing` (`cq`).
- `wuhan` (`wh`).
- `sic`, `most`, `mee`, `ndrc`, `govcms (jinan)`.
- `mof` sections `zcfb` (政策发布) and `czxw` (财政新闻). The `czwg` gazette walker is a different shape
  and wants a highest-issue-seen watermark instead of a page early exit.

The reverse-chronological premise is **inferred** from the CMS dialect, not
measured, because measuring it needs a live fetch and this audit did none. Before
enabling the flag on any site, fetch page 0 and page 1 of one section and confirm
dates descend. That is one `curl` per site.

**Not safe.**

- `gkmlpt --sync`. There is no pagination to exit from. It enumerates a JSON
  catalogue per category and diffs set-wise, and it exists specifically to detect
  changes and deletions, which a presence check cannot do. Its fix is the
  `db_ids` scope bug and a per-site time budget, not an early exit.
- `zhejiang`. The sections it reaches are not paginated at all. The JCMS gateway
  pre-renders page 1 and returns page 1 for every `pageNo` from a US IP, per the
  crawler's own docstring. An early exit would change nothing because nothing is
  fetched successfully in the first place.
- `hangzhou`. Its loop already has conditional breaks at lines 345, 388, 401, 482
  and 497 and computes `total_pages` from a result count. Leave it alone; it costs
  196s.
- `guancha --deep`, `ifeng`, `stdaily`, `xinhua`, `people`, `qbitai`, `36kr`,
  `latepost`, `elsewhere`. News front pages and columnist indexes are not stable
  reverse-chronological lists; items get promoted, pinned and reordered. These are
  also the only crawlers actually producing documents, at 1 to 26 seconds per new
  document. Do not touch them.
- Any site where an older page gets edited in place. The gkmlpt family is exactly
  this case, which is why its sync mode exists.

A separate fix, independent of early exit and larger in effect for Beijing and
MOF: change the skip test from "already stored WITH a body" to "already stored",
and move the retry of bodyless documents to a bounded, separate job with an
attempt counter. Today `if existing and existing[1]: continue` guarantees that
1,628 Beijing rows, 5,388 MIIT rows, 1,022 Suzhou rows and 587 Chongqing rows are
re-fetched every night in perpetuity. `scripts/backfill_from_html.py` already owns
that concern in Phase 1b.

## 4. Recommended plan

Not implemented. Priority order, measured savings against the 252-minute median.

| # | change | saving | risk |
|---|---|---|---|
| 1 | Remove `zhejiang` from the nightly loop. Keep the crawler; run it from a residential or HK vantage, or on a monthly reachability probe. | 30 min | **Low.** It has produced zero rows in 11 nights. Nothing is lost that is not already lost. |
| 2 | Beijing: skip on presence, not on presence-with-body. Add the page early exit. | 28 min | **Medium.** The 1,628 bodyless `bj` rows stop being retried nightly, but they are already not improving. Needs an `extraction_attempts` column or a weekly bounded retry so they are not abandoned silently. |
| 3 | `govcms --group dept`: drop the 8 dead `cq.gov.cn` bureau hosts, then split the remaining ~224 sites into 3 chunks on a 3-night rotation. | 20 min | **Low.** Today 72 of 232 are never crawled at all. Rotation strictly increases coverage while cutting nightly time. |
| 4 | gkmlpt: fix the `db_ids` site scope so cross-posted ids are not re-fetched nightly, and give the sweep a per-site time budget with a rotating start offset so all 63 sites get synced over a few nights. | 20 min | **Medium.** Changes diff semantics. The `document_changes` table and the "deleted" counts will shift. Verify the overwrite of other sites' `body_text_cn` has not already corrupted rows before changing anything. Also confirm the ON CONFLICT path is the real mechanism with a direct query. |
| 5 | Jiangsu: early exit, with a weekly `--max-pages 0` full walk retained for revisions. | 19 min | **Low to medium.** Gated on the one-curl reverse-chronological check. |
| 6 | Move to weekly cadence: `mof`, `chongqing`, `most`, `wuhan`, `sic`, `hangzhou`, `ipc_court`, `mee`, `ndrc`, `govcms (jinan)`. Combined median 2,957s nightly, about 7 min amortized weekly. | 42 min nightly, 35 min amortized | **Low.** Every one of these has a median yield of zero and a ten-night sum of 0 to 13 documents. Worst-case recency loss is 6 days on sources that publish under one document per day. |
| 7 | Per-crawler timeout overrides instead of one global 1800s: 600s for the known-zero-yield set, 1800s retained only for `gkmlpt` and the dept rotation. | 0 directly | **Low.** Bounds the worst case so a newly-hung host cannot quietly eat 30 min. Do this alongside item 1 so a future `zhejiang`-style death costs 10 min, not 30. |
| 8 | Run the independent crawler groups 2-wide. `nproc` is 2, memory is 3.9 GB, and load average during Phase 1 is 0.17, so Phase 1 is entirely network-bound and the CPU is idle. | about 30 min on the residual | **Medium.** CLAUDE.md's SQLite rule is 2 parallel writers safe, 4 or more hits `database is locked`. Cap at 2 and never put two writers on the same `site_key`. `govcms --group city3 --deep --workers 4` already proves intra-crawler concurrency is tolerated. |

Items 1 through 7 total about **152 minutes saved**, taking Phase 1 from roughly
252 minutes to roughly **100 minutes**. Item 8 could take the residual toward 70,
and should be attempted only after 1 through 7 land, because most of what it would
parallelise today is waste.

Safe to do now, in this order: 1, 3, 6, 7. All four are pure subtraction or
rescheduling, none changes extraction logic, and none can lose a document that is
currently being captured.

Risky and needing a verification step first: 2 and 4 both change dedup or diff
semantics and both touch `body_text_cn`; 5 is gated on confirming listing order;
8 is gated on the SQLite writer limit.

## Open items this audit did not settle

- Whether Beijing's and Jiangsu's listing pages are in fact reverse-chronological.
  One `curl` of page 0 and page 1 per site settles it. Not done here because the
  audit was read-only and ran during the nightly.
- Whether the gkmlpt `ON CONFLICT(id) DO UPDATE` path has already overwritten
  `body_text_cn` on rows belonging to a different `site_key`. The frozen row
  counts prove no rows are gained; they do not prove no bodies are being stomped.
- Why `zhejiang` degraded from ~1,430s to a hard 1800s on 2026-10-01. A WAF rule
  change is the obvious guess and is untested.
