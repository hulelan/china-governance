# QA: gkmlpt `--sync` per-site diff vs. global-id upsert

**Date:** 2026-10-07 · **Verdict: THE BUG FIRES.** Not latent. It fired during the
nightly that was running while this was investigated (timestamps `2026-10-07T06:05`).

## The claim under test

`crawlers/gkmlpt.py::sync_site` scoped its "what is new?" diff to ONE site —
`existing_docs` from `SELECT ... FROM documents WHERE site_key = ?`, then
`db_ids = set(existing_docs.keys())` — while `store_gkmlpt_document` inserted with
an unguarded `ON CONFLICT(id) DO UPDATE SET body_text_cn=..., raw_html_path=...`.
gkmlpt is a shared Guangdong publishing platform, so a post id appearing in a second
site's feed looks NEW to that site, upserts on the primary key, and overwrites the
body of the row owned by the OTHER site while keeping the original `site_key`.

## Evidence

### 1. Ids are NOT per-site namespaced

Per-site `MIN(id)`/`MAX(id)` over the 54 gkmlpt sites in the live corpus are deeply
interleaved, not disjoint (e.g. `zjj` 3,669,909–13,007,479 vs `stic`
5,647,296–13,006,357 vs `npc` reaching 12.7M+). One platform-wide id sequence,
which also overlaps the synthetic ids other crawlers assign. Nothing structural
prevents a collision.

### 2. Live list APIs really do serve ids owned by other sites (decisive test)

Sampled page 1 of every leaf category for 3 sites via the real
`/gkmlpt/api/all/<cat>?page=1&sid=<sid>` endpoint (50 requests, 1 req/s), then
checked each id against the live DB read-only:

| probe site | ids sampled | present in DB | **owned by a DIFFERENT `site_key`** |
|---|---|---|---|
| `zjj` (住建局) | 723 | 720 | **25** |
| `stic` (科创委) | 638 | 632 | **47** |
| `jieyang` | 331 | 202 | **8** |
| **total** | **1,692** | 1,554 | **80 (≈4.7%)** |

Colliding owners: `zjj` → npc 8, cq 4, xinhua 3, zhongshan 2, sz_invest 2, sh 2,
wuhan/suzhou/mee/gov 1 each. `stic` → npc 12, most 9, zhongshan 6, bj 5, miit 3,
cac 3, ndrc 2, mee 2, sh/sf/samr/ifeng/hlj 1 each. `jieyang` → shanwei 5,
jiangmen 3 — i.e. it collides **gkmlpt-on-gkmlpt** as well as gkmlpt-on-other-crawler.

Every one of those 80 is an id that `sync_site` would classify as new for the
probed site and then upsert over another site's row.

### 3. Rows already corrupted in the corpus

The upsert also sets `raw_html_path=excluded.raw_html_path`, which the *second*
writer saved under its OWN site directory. So a row whose `site_key` disagrees with
the site directory in its `raw_html_path` is a row the bug has already overwritten:

**261 such rows corpus-wide.** By victim: `npc` 81, `ndrc` 19, `zhongshan` 17,
`gov` 13, `most` 12, `sh` 12, `szpsq` 9, `bj` 8, `xinhua` 8, `cq` 7, `miit` 7,
`suzhou` 6, … Roughly half have a body under 1,000 chars — the replacement text
is typically much shorter than the law it displaced.

Concrete victim (written at 06:05 UTC on 2026-10-07, mid-nightly):

```
id              = 12728908
site_key        = npc
title           = 包头市人民代表大会常务委员会关于修改《包头市供水条例》《包头市供热条例》的决定
url             = https://flk.npc.gov.cn/detail?id=bb6523f2fd16428db141717cf64a10f3
raw_html_path   = raw_html/zjj/12728908.html     <-- written by the zjj crawler
length(body)    = 189                            <-- the law's text is gone
crawl_timestamp = 2026-10-07T06:05:53+00:00
```

261 is a **lower bound**: it only detects collisions where the second writer had a
non-empty `raw_html_path`.

### 4. The `zjj` symptom is explained

`zjj` is pinned at 2,719 rows while the log reports adds, because its genuinely-new
posts resolve to ids already owned by `npc`/`cq`/`xinhua`/… — the upsert updates a
foreign row instead of inserting, so `zjj`'s row count cannot grow. The old
`store_gkmlpt_document` returned `True` on the ON CONFLICT path (it only returned
`False` on `IntegrityError`), so `sync_site` incremented `added` and wrote an
`"added"` row into `document_changes` for documents it never added. **The yield
accounting was indeed claiming documents it did not add.**

### 5. Same hole in `crawlers/base.py`

`base.store_document` (shared by every non-gkmlpt crawler) had the identical
unguarded `ON CONFLICT(id) DO UPDATE`, and the mismatch table shows it firing in
that direction too (`szpsq` ← `raw_html/gov/`, `szft` ← `raw_html/gov/`,
`yunfu` ← `raw_html/gov/`). It also returned `None` unconditionally, so no caller
could tell.

### 6. Ruled out

- **0** URLs are shared across `site_key` corpus-wide (so the URL unique index is
  not catching these; the colliding posts have different URLs).
- Host-mismatch rows on gkmlpt sites (`heyuan` 440, `fgw` 389, `mzj` 276) are
  benign — list items linking out to gov.cn / weixin / Xinhua / CCTV.

## What changed

1. **`crawlers/gkmlpt.py::store_gkmlpt_document`** — added
   `WHERE documents.site_key = excluded.site_key` to the `DO UPDATE`. When the
   guard suppresses the update (`cur.rowcount == 0`) it looks up the real owner,
   logs `ID COLLISION: gkmlpt post <id> ... requested by site 'X' is already owned
   by 'Y' — skipped (body NOT overwritten)`, and returns `False`.
2. **`crawlers/base.py::store_document`** — same guard, same warning; now returns
   `True`/`False` instead of `None` (no caller consumed the old return value).
3. **`crawlers/gkmlpt.py::crawl_site`** — its "do we already have a body?" probe was
   `SELECT body_text_cn FROM documents WHERE id = ?`, site-agnostic, so for a
   colliding id it adopted *another site's* body as this site's. Now scoped with
   `AND site_key = ?`. (Lookup is by primary key, so the `AND url != ''` partial-index
   gotcha does not apply here.)
4. **Yield accounting** — `sync_site` counts `added` only on a real write, tracks a
   new `collided` counter, logs `New: N | Skipped(collision/dup): M | ...`, warns
   when `collided > 0`, and returns `skipped_collision` in its result dict.
   `_record_change(..., "added", ...)` is no longer written for skipped ids.
   `crawl_site` likewise reports `N skipped`.

### Why SKIP rather than merge the cross-post

Because gkmlpt ids are a single platform-wide namespace that also overlaps other
crawlers' synthetic ids, a genuine cross-post and two unrelated documents that
merely share an id are **indistinguishable at insert time** — the one case we can
see (`npc` law vs `zjj` post) is the latter. Preserving the stored row is the only
non-destructive choice; the warning makes real cross-posts visible so a deliberate
dedup/reference design can be built on evidence instead of a guess.

## Not done here (nightly held the lock)

- **The 261 already-corrupted rows are not repaired.** Remediation is a re-crawl of
  the victim documents from their own sites (`npc`, `ndrc`, `gov`, `most`, …),
  which needs a write lock on the live DB. Query to re-derive the list:
  ```sql
  SELECT id, site_key, url FROM documents
  WHERE raw_html_path LIKE 'raw_html/%'
    AND site_key != substr(raw_html_path, 10, instr(substr(raw_html_path,10),'/')-1);
  ```
- The stale `"added"` rows in `document_changes` for never-added documents were
  not pruned.

## Tests

`tests/test_gkmlpt_site_collision.py` — 6 scratch-DB cases: a foreign-owned id must
not clobber the first site's body or `raw_html_path` (via both store functions);
same-site body backfills must still write (via both); a genuinely new id for a
second site still inserts; and the sync accounting must report 1 added / 1 skipped
rather than 2 added. Full suite: **110 passed, 1 skipped**.
