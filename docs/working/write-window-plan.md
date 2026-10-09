# The write window: what runs on 2026-10-09 after ~10:45 UTC, and in what order

*Written 2026-10-09 01:10 UTC, because the scheduling arithmetic has a consequence that is easy to
miss and costs a full day if missed.*

## The arithmetic

| fact | value |
|---|---|
| now | 2026-10-09 01:05 UTC |
| classifier (`pid 520616`) | 14,600 / 23,710, **ETA 577 min** → finishes ≈ **10:45 UTC** |
| sync lock held since | 2026-10-08 06:00:02 (`/tmp/china-governance-daily-sync.lock.d`) |
| next cron | **06:00 UTC 2026-10-09** |
| droplet HEAD | `f86a0cf` — iteration 76, i.e. **none of today's code** |

**The 06:00 cron will find the lock held and skip.** The `mkdir` lock exists precisely so a
classification drain that exceeds 24h does not get a second classifier piled on it, and it is doing
its job. But the consequence is that the next nightly to actually run is **06:00 UTC 2026-10-10**.

**So every fix shipped on 2026-10-08 takes effect on 10-10, not 10-09, unless the window between
~10:45 UTC and 06:00 UTC is used.** That window is ~19 hours and it is the only chance to land the
day's work a day earlier. What is waiting:

## Order (each step's reason is why it must precede the next)

```bash
ssh root@104.236.88.45
cd /root/china-governance
git pull                       # f86a0cf -> today's HEAD. Nothing below exists without this.
```

1. **`python3 scripts/body_ledger.py --init-schema && --seed`** (~1-2 min, **no network**). Must
   precede any crawl, or the first crawl pays the fetches the ledger exists to stop. Expect ~8,369
   rows capped and ~11,573 `html_missing` left at `attempts=0` (`prereg-next-rebuild.md` P3).
2. **`python3 -m crawlers.pbc`** (~10 min). 31 → ~541 documents from the 条法司 sections plus the
   capped 沟通交流 walk. Independent of everything below; do it before the citations rebuild so its
   titles are in the index (P4).
3. **The second Wuxi merge** — ~1,707 municipal rows from `documents_wuxi.db` via `merge_db.py`.
   Must precede `build_doc_identity`, or the merged rows get no identity row.
4. **`python3 scripts/trim_body_tails.py --dry-run`** then `--apply`. Must precede the BM25 rebuild
   (trim first, then ONE index rebuild, not two). `--revert` undoes every audited change.
5. **The owed rebuild, in this order** — each reads the previous one's output:
   `build_doc_identity.py --write --force` → `build_instrument_succession.py --write --force` →
   `extract_citations.py` → `build_site_stats.py` (now also writes **`doc_len`**, which step 6
   needs) → `build_diffusion_events.py --write` → `build_tracker_rollup.py` →
   `validate_cascades.py`.
6. **`python3 scripts/build_search_index_seg.py`** — once, after the trim.

## The predictions this window tests

All four are registered in `prereg-next-rebuild.md` **before** the fact, which is the only way to
tell a fix from a regression:

- **P1 + P6 land together and their falls ADD**: the org-stub gate (~4,570 edges) plus the
  instance-title denylist (~391) ≈ **4,960 fewer resolved edges**, resolution 52.97% → ~52.1%.
  **A rise falsifies both.** Do not read either number alone.
- **P2**: `localized_of` **+1,336** (2,014 → ≈3,350) with 0 removed, `genre='implementing'` +1,336,
  `diffusion_events` byte-identical, `validate_cascades` 15/15.
- **P4**: `pbc` 31 → ~541, oldest **1993-01-14**; and the named test — 人民币银行结算账户管理办法
  (22 citers), 非金融机构支付服务管理办法 (18), 商业银行服务价格管理办法 (14), 金融租赁公司管理办法
  (11) should drop out of the unresolved head. **If resolution rises and none of those four resolve,
  the demand list was wrong about what PBC publishes** — the more interesting outcome.
- **P5**: the instrument-pooling gap (11,891 families / 28,225 documents inside the 400d window)
  either collapses (it was staleness) or holds (a real defect worth real work).

## If the window is missed

Nothing breaks. The 10-10 nightly git-pulls and runs all of it in order, since `daily_sync.sh`
already sequences `build_site_stats` (377) before `build_tracker_rollup` (394). The cost is one
day's delay on: PBC's 510 documents, the two resolution corrections, the tracker's intensity
columns having any data, and Beijing's ~760 nightly wasted fetches continuing.

**The one thing that would be lost rather than delayed** is nothing — every item above is
idempotent or re-runnable. That is worth stating, because it means the window is an optimisation,
not a deadline.
