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

**CONFIRMED 2026-10-09 06:00:01 UTC**, verbatim from `logs/cron.log`:
`[Fri Oct  9 06:00:01 UTC 2026] Another daily_sync is already running
(/tmp/china-governance-daily-sync.lock.d). Exiting.` No `daily-20261009-*.log` exists. The lock is
still the one taken at 2026-10-08 06:00:02, and at 06:07 the classifier read 19,200/23,710 with 286
minutes left — window opening ≈**10:53 UTC**.

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

   **Scope, measured read-only 2026-10-09** (306s over 62,591 prefiltered bodies): **33,418 carry a
   trailing chrome block** → `trim=32,808`, `flagged=610`. The 610 are *all-chrome* bodies (nothing
   but widget text) and are **flagged, not trimmed**, which is the right call — a body that is
   entirely chrome needs re-extraction or a ledger entry, not truncation to empty.

   **The safety case is the marker census.** All 16 markers are unambiguously page furniture, none
   overlapping document content: 扫一扫在手机打开当前页 22,922 · CODE(js/css) 11,083 · 分享到 6,004 ·
   相关解读 3,157 · 网站导航 2,802 · 微博 1,473 · 相关文档 1,308 · 打印本页 1,261 · 【关闭】 1,032 ·
   下一篇 779 · 微信 457 · 上一篇 367 · 【打印】 266 · 关闭窗口 190 · 相关链接 151 · QQ空间 4.
   Concentrated in `gov` (12,763 of the 扫一扫 rows), `js` (5,231), `suzhou` (3,741), `most` (1,059).

   **The part to hand-check before `--apply`.** Trim size is overwhelmingly small — 20,227 of
   32,808 remove under 5% of the body — but the tail of the distribution is not:

   | removed share | <2% | 2-5% | 5-10% | 10-25% | 25-50% | **50-90%** | **≥90%** |
   |---|---|---|---|---|---|---|---|
   | suffix rows | 13,743 | 6,484 | 3,854 | 3,912 | 3,574 | **1,147** | **94** |

   **1,241 rows (3.8%) lose more than half their body.** "The body really was mostly chrome" and
   "the detector over-reached" produce the *same number*, so these need eyes, not a percentage.

   **Hand-checked 2026-10-09 via `--dump-tsv`, and the trim is correct.** Read the 8 most
   aggressive rows (tail_share 0.97-0.99) with their kept and removed text: every removal is
   unmistakable CSS/JS (`.m-share{float: left;…}`, `/*分享*/`, `var zcJSON = [{…`) and every kept
   fragment is real text. `xjboz/900138943` goes 25,234 → 115 chars and the 25k was a JS sidebar
   tree; five `bjd_tongzhou` rows go ~2,000 → ~58 chars and the 2,000 was a share-widget stylesheet.
   **Nothing to fix in the detector.**

   ***But the check found something else, and it changes how to run this step.*** The kept bodies in
   those bands are tiny:

   | band | rows | median kept | **kept < 200 chars** |
   |---|---|---|---|
   | ≥90% | 95 | 214 | **43 (45%)** |
   | 50-90% | 1,148 | 422 | **423 (36%)** |
   | rest | 31,565 | 1,335 | 1,110 (3%) |

   1,576 documents end up with under 200 characters. **I first read that as 1,576 effectively
   bodiless rows; measured properly it is 163**, and the correction matters because it changes this
   from a significant problem to a minor one. Stripping the title *and* the metadata boilerplate
   (日期 / 来源 / 字号 / 打印 …) and then asking whether any content remains gives **163 content-free
   rows**; the other ~1,400 are short but genuine (title + date + source + a line of notice).

   **A length cutoff cannot separate them.** The content-free set spans **26-158 characters**, and
   any cutoff capturing it also captures **758 rows that do have content** — so the 200-char
   threshold was ~90% false positives. The criterion must be functional, not a length. The real 163
   look like `习近平同阿塞拜疆总统阿利耶夫通电话` + date + 来源：新华社 + 字号 widgets: gov.cn news
   stubs whose body never extracted. They still carry the double invisibility that hid 360
   attachment-only `pbc` rows (CLAUDE.md's marker-table) — a useless but non-empty body is invisible
   to every filter that tests for emptiness — but at 163 rows it is a follow-up, not a blocker.

   **Two consequences for this step:**
   1. **Do NOT pass `--no-reextract`.** I used it in the dry-run for speed, which is why the report
      says `Re-extraction outcome: not tried=33418`. The script's `reextract` remedy re-reads saved
      HTML with the site's own extractor and is precisely the fix for a title-only body. Run it as
      `--apply` plain.
   2. **The residue after re-extraction belongs in `body_fetch_failures`** as `empty_extraction`,
      so it is tracked rather than looking fine. The trim script does not write ledger rows today;
      that is a small, deliberate follow-up (logged below), not something to bolt on mid-window.
      Top sites in the affected bands: cppcc 312, suzhou 291, bjb_wjw 64, bjd_tongzhou 48,
      bjd_fangshan 45.

   `--revert` undoes every audited change, so `--apply` is recoverable either way.
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
- **P7**: the body-tail trim removes **~195 resolved edges** whose reference text occurs *only*
  inside a 相关链接 / 上一篇 tail (368 edges on 319 documents, measured read-only 2026-10-09). These
  are spurious by construction — the reference exists nowhere in the document's real text.

**The single most likely misreading of this window.** P1 (~4,570), P6 (~391) and P7 (~195) are all
precision fixes that *remove* edges, and if the window is used they land in **one** rebuild:
**≈5,156 fewer resolved edges**, resolution 52.97% → ≈52.1%. Every previous resolution change in
this project was an **increase**, so seeing ~5,100 edges vanish will look like a regression and is
not one. And P4 (the PBC backfill) *raises* resolution in the same window, partially offsetting
them — so **the net resolution number is not interpretable at all.** Check each fix by its own named
test, never by the total.

## If the window is missed

Nothing breaks. The 10-10 nightly git-pulls and runs all of it in order, since `daily_sync.sh`
already sequences `build_site_stats` (377) before `build_tracker_rollup` (394). The cost is one
day's delay on: PBC's 510 documents, the two resolution corrections, the tracker's intensity
columns having any data, and Beijing's ~760 nightly wasted fetches continuing.

**The one thing that would be lost rather than delayed** is nothing — every item above is
idempotent or re-runnable. That is worth stating, because it means the window is an optimisation,
not a deadline.
