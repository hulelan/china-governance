# 44.5% of citation weight sits on undated documents

Measured 2026-10-09 while checking a limitation I had written into
`docs/research/export-control-regime.md`. The limitation was real; its stated cause was wrong.

## 1. The finding

| | documents | citations |
|---|---|---|
| cited documents with `date_written = 0` | **22,214** (50.1% of cited) | **120,361** (44.5%) |
| all cited documents | 44,364 | 270,695 |
| recoverable by pooling (a dated copy exists in the same `instrument_id`) | 2,201 | 26,443 |

Corpus-wide the undated share is **116,282 of 346,955 documents (33.5%)**.

The affected documents are not marginal. By inbound: 城市、镇控制性详细规划编制审批办法 **918**,
深圳市人民政府令 650, 土地管理法实施条例 539, 中国共产党纪律处分条例 488,
粤港澳大湾区发展规划纲要 389, the 十五五 and 十四五 规划纲要 383 and 377,
国务院关于深入实施“人工智能+”行动的意见 323.

## 2. It is NOT the cause I first wrote down

`export-control-regime.md` §8 said the regime's second anchor instrument "cannot appear in its own
time series". Checking every copy of three anchors shows that is the right worry with the wrong
cause — **the instrument is dated and the pooling works**:

| copy | site | date | inbound | role |
|---|---|---|---|---|
| 12731181 | npc | 2024-09-29 | 0 | canonical |
| 12701941 | mofcom | 2024-10-18 | 0 | mirror |
| 12704311 | mofcom | 2024-10-22 | 0 | mirror |
| **12651059** | gov | **UNDATED** | **107** | mirror |

All five copies of 两用物项出口管制条例 share `instrument_id 12731181`, and the canonical copy
carries the correct promulgation date. 商用密码管理条例 (canonical 2023-04-26, 27 citations on an
undated mirror) and 稀土管理条例 (canonical 2024-06-21, 3 on an undated mirror) repeat the shape.

**The actual defect: `doc_inbound` is computed per DOCUMENT, so citation weight lands on whichever
copy the citing text resolved to — frequently an undated mirror — while the dated canonical reads
inbound 0.** The weight exists and the date exists, never on the same row. Anything joining
citation weight to a date (an influence series, an age-controlled authority measure, "when did this
instrument start being cited") silently drops it.

**`build_diffusion_events` is NOT affected** and this was checked, not assumed: anchor 12650908
(the AI+ instrument, itself `date_written = 0`) carries **228 events with lags 2-408 days and zero
nulls**. An epoch-0 anchor would have produced ~20,000-day lags, so the matcher is already
resolving a real date. The exposure is in `doc_inbound` / `citation_rank` and in ad-hoc analysis.

## 3. Why the fix is NOT to overwrite `date_written`

116,281 of the 116,282 undated rows looked fixable in SQL. **That number is wrong** — the honest
count is **106,732**, and the 9,550-row gap is a SQLite type-comparison trap (see §5).

More importantly, `date_published` is a **different quantity** from `date_written` — web posting
versus issuance — and over all 229,208 rows where both exist:

| exactly 0 | within ±1d | within ±7d | written EARLIER | written LATER |
|---|---|---|---|---|
| 83.1% | 86.4% | 92.7% | 16.0% | 0.9% |

Median 0, but p1 = **−1,802 days**: historical archives post documents years after issuance. And
the gap is a **site convention**, not noise —

| site | pairs | median gap | within ±1d |
|---|---|---|---|
| npc / stdaily / guancha / bj / miit / xinhua / js | 5.2k-27k each | 0 | **100%** |
| szlhq | 6,280 | 0 | 95% |
| zhongshan | 5,152 | 0 | 67% |
| jieyang | 5,872 | 0 | 60% |
| **gd** | 6,213 | **−3** | **46%** |

So overwriting `date_written` would import posting dates into an issuance column, silently moving
every existing series, and would be worst exactly where the convention diverges.

**Decision: add a DERIVED column, do not overwrite.** `doc_identity` already carries
`date_quality`, and CLAUDE.md already says to prefer joining `doc_identity` over the raw columns in
new analysis. So the fix is `date_effective` + `date_source` (`written` | `published` | `display` |
`none`) in `build_doc_identity.py`, letting an analysis opt in and letting a reader see which rows
rest on a posting date. Nothing existing changes until it opts in.

A second, independent improvement: roll `doc_inbound` up to `instrument_id` so pooled citation
weight can be read against the canonical copy's date. That alone recovers 2,201 documents and
26,443 citations without any date inference at all, and it is the more defensible half.

## 4. Status — the pooled half is SHIPPED and measured

`instrument_inbound(instrument_id, inbound, edges, copies, cited_copies, dated_id, date_written)`
is built inside `scripts/build_site_stats.py` (3.5s on the live corpus), so it is already nightly:
Phase 2c runs that script after Phase 2b produces `doc_identity`, and the builder **skips cleanly**
when `doc_identity` is absent so a fresh DB still works. Additive — `doc_inbound` keeps its
per-document meaning and nothing reads the new table until it opts in.

Built: **42,512 instruments, 22,854 with a dated copy, 19,658 wholly undated.**

| | per-document (`doc_inbound`) | instrument grain (`instrument_inbound`) |
|---|---|---|
| cited units | 44,364 | 42,512 |
| citations | 270,695 | 261,824 |
| **date-readable citations** | 150,299 (**55.5%**) | 168,961 (**64.5%**) |

**+18,662 citations became date-readable with no date inference at all**, and **8,871 pool-level
self-citations were removed** — a mirror citing its own sibling is the same text citing itself,
which `doc_inbound` cannot detect because `source_id != target_id` holds for every such edge.

The three anchors that started this now read against real dates: 两用物项出口管制条例 **107 pooled
inbound, 6 copies, 1 cited copy, dated 2024-09-29**; 商用密码管理条例 27 / 6 copies / 2023-04-26;
稀土管理条例 3 / 4 copies / 2024-06-21.

**A sub-finding worth keeping.** 政府信息公开条例 pools **19 copies** and shows 1,907 pooled inbound
against **2,143** on its canonical copy alone. Pooled weight is LOWER, which is correct: **236 of
that instrument's apparent citers were its own mirrors**, about 11% of its count. The most-copied
instrument in the corpus had its citation total inflated by siblings citing siblings, invisibly.

**Still not done:** the `date_effective` / `date_source` half (the 106,732 rows whose only date is a
posting date) is designed in §3 but not built. It requires the opt-in semantics described there, and
it should not be confused with this change, which infers nothing.

## 5. Two measurement errors I made here, both worth keeping

**An integer 0 counts as "present" in SQLite.** `display_publish_time` is `typeof='integer'` on all
116,281 rows and is integer **0** on 104,776. SQLite compares an integer against a text literal by
TYPE ORDER, so `COALESCE(display_publish_time,'') != ''` is TRUE for integer zero. SQL said 116,281
fixable; Python, where `0` is falsy, said 106,732. Python was right. This is the sibling of the
documented double-quote trap: both are SQLite answering a different question cleanly. **Compare
against the type you expect** (`display_publish_time > 0`), never against `''`.

**An unordered `LIMIT` is not a sample.** My first agreement check used `LIMIT 4000` with no
`ORDER BY` and reported **68.8%** agreement, which read as "date_published is unreliable". SQLite
returned the first 4,000 rows in rowid order — a slice dominated by low-id sites, and `gd` runs at
median −3 days with 46% within ±1. The full 229,208-pair population agrees **83.1%** exactly. I had
diagnosed a data problem that was a sampling problem, which is the per-site panel lesson
(`panel.py`, `rmb-coverage.md` §4) in a new costume: **the slice you get for free is never the
slice you want.**
