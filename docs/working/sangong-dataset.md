# 三公经费: a validated spending panel, and four rounds of phantoms

*A table-aware parser for the 公开07 "三公"经费 table yields **1,640 accounting-validated rows**
from 1,318 documents and 533 units, 2011-2026. On a **fixed-unit** panel the series is roughly
flat (**−5.1%** 2020-2024, with the median **rising** 21.90 → 23.09万元), while the same data read
as "all disclosures per year" falls **31%**. The decline is composition, not austerity. The
headline here is as much methodological: the documents' own accounting identity validated **four
successive versions** of this parser, three of which were substantially wrong. Supersedes the
160-row feasibility note in `sangong-feasibility.md`.*

## 1. What the dataset is

`scripts/rnd/analysis/sangong_table.py` parses the published 公开07 表. Its columns carry
accounting identities that **the documents assert themselves**:

    合计 == 因公出国 + 公务用车小计 + 公务接待        公务用车小计 == 购置费 + 运行费

Only rows satisfying `total == out + car + host` (±0.05万元) are emitted, so **the reported n is
the validated n** — the acceptance criterion the feasibility note asked for. 3,032 of 4,350
candidate documents are rejected outright.

| | |
|---|---|
| validated rows | **1,640** (from 1,318 documents; layout C yields one row per sub-unit) |
| distinct units | 533 by title stem |
| fiscal years | 2011-2026; **dense only 2020-2024** (1,394 of 1,640 rows) |
| total 万元 | **median 19.24** · p90 198.00 · max 5,548.20 |
| composition | **公务用车 74%** · 因公出国 16% · 公务接待 9% |

Three layouts exist and one **reverses the column order** (layout C prints 接待 before 用车), so
the parser is label-anchored with candidate search rather than positional, and lets the identity
choose which candidate combination balances.

## 2. The finding, and the control that produces it

| year | fixed-unit panel (n=34, present in all five years) | all disclosures that year |
|---|---|---|
| 2020 | median 21.90 · mean 97.26 · sum 3307.0 | n=102 · median 18.39 · mean 93.93 |
| 2021 | median 19.20 · mean 100.04 · sum 3401.4 | n=214 · median 14.23 · mean 67.38 |
| 2022 | median 20.10 · mean 98.65 · sum 3354.2 | n=214 · median 18.66 · mean 77.64 |
| 2023 | median 21.69 · mean 90.23 · sum 3067.9 | n=186 · median 19.92 · mean 54.43 |
| 2024 | median 23.09 · mean 92.31 · sum 3138.4 | n=220 · median 18.74 · mean 64.46 |

**Fixed units: −5.1% over five years**, with the median *rising* and 16 of 34 units up.
**Unbalanced: means fall 31%.** The gap is the mechanism: 三公 disclosure is an obligation that
propagated *downward* through the 2020s, so each year adds small units (街道办, 事业单位) whose
budgets are a fraction of a bureau's. A mean over "all disclosures in year Y" therefore measures
**disclosure compliance**, not spending. Only 34 of 533 units publish in all five years, which is
itself a result: the panel is shallow because the obligation is young.

This is the `panel.py` fixed-site discipline applied to a different unit of analysis, and it
changed the sign here as it did for the attention series. **The contrast is the robust part**: it
survived all four cleanup rounds below and strengthened, while the fixed-panel magnitude moved
from +0.2% to −5.1% as phantoms were removed. Quote the contrast, not the point estimate.

## 3. Four parser versions, and why the validator kept certifying wrong ones

| version | rows | what was wrong |
|---|---|---|
| positional, 12 columns after a marker run | 58 | three layouts exist and **layout C reverses 接待/用车** |
| label-anchored | **0** | a full-body offset used as an index into a 900-char slice |
| candidate search | 3,874 | the **年度 column** parsed as money — 因公出国 76%, p90 exactly 2022.00 |
| + bare integers in [1990, 2035] excluded | 3,643 | enumerators `1,2,3` sit **below** that window |
| + header-row guard | 1,775 | a layout-A header whose first figure is `07` evaded it |
| + column-number-run floor | 1,715 | **narrative** item numbers (`1.因公出国… 2.公务接待…`) |
| + granularity bound (final) | **1,640** | — |

**Every one of those versions passed the accounting identity on every row it emitted.** The
identity is **scale-free**: `3 == 1 + 1 + 1` satisfies it exactly, so a parse built from the
table's own column indices validates perfectly. The proof that the 1,868 rows removed at round 5
were artifacts is not the identity but **repetition**: the row `7.0 1.0 3.0 3.0` appeared verbatim
for 江门市政府办公室, 大鹏新区发展和财政局, 深圳市住房和建设局 and 广州市人民政府办公厅.
Unrelated units cannot coincidentally spend identical amounts, so those numbers are the 公开07
**schema** (合计 = 出国 + 用车小计 + 接待, read as indices 7 = 1 + 3 + 3).

The three bounds that do the work are the ones **the identity cannot express**:

* `MAX_WANYUAN = 100_000` — a scale ceiling. The first version accepted 3,439,824.70万元.
* bare integers in [1990, 2035] are not money — the 年度 column.
* `MARKER_MAX = 12` — a **granularity** floor: a row with all four figures whole and ≤ 12 is
  markers. Published 三公 figures carry two decimals by convention; indices never do. The tell
  that these were not simply small units: **广州市人民政府机关事务管理局** — the body that
  manages the government car fleet — came out at 3.0万元, and 韶关市人民政府办公室 at 10.0
  against 83.6 in a year that parsed cleanly. Rows under 12万元 **with** decimals are untouched
  (p25 of the panel is 4.85万元).

## 4. The selection rule is an assumption, and it is load-bearing

**80.3% of anchor segments admit more than one balancing combination**, and `parse()` takes the
**first in document order**. That is a positional assumption, which the candidate-search design
was supposed to avoid. It matters: on the round-5 data the fixed panel reads **+0.2%** under
first-pick and **+51.6%** under last-pick.

First-pick is nevertheless the defensible rule, on two pieces of evidence rather than plausibility:

1. Under last-pick and max-pick the fixed panel's median is **exactly 100.00** in four consecutive
   years, which cannot be a spending distribution — those rules are reading 执行率/增减% **percentage
   columns**.
2. The table's **second, independent** identity (`car == buy + run`) confirms the first-pick row
   **2.3× more often** than the last-pick row (46.8% vs 20.6% of the 5,352 ambiguous segments that
   carry a split). Figures drawn from one column satisfy both identities; figures mixed across
   columns satisfy the first by coincidence and the second only by a second coincidence. *Measured
   on the round-5 parser, so read the ratio as the evidence, not the levels.*

Still: **fewer than half** of ambiguous first-pick rows are confirmed by the split. A
column-aware parser — one that locates the year headers and reads the column beneath the title's
year — is what would remove the assumption, and it is the single highest-value improvement left.

## 5. What this panel cannot answer

* **The 2012 austerity campaign is not testable.** It is the natural treatment date and the
  feasibility note named it as step 3, but 2011-2019 holds 246 rows against 1,394 for 2020-2024,
  and no fixed-unit panel spans the 2012 boundary. Disclosure began in earnest after the
  obligation matured, so the pre-period is **absent**, not merely thin.
* **It is a Shenzhen panel, not a national one.** The top ten sites (szdp 315, szlhq 202, szeb 162,
  swj 159, jtys 84, wjw 82, hrss 76, sf 76, mzj 70, szlg 68) hold 1,294 of 1,640 rows. Read the
  flat result as a claim about one municipality's bureaus, and widen before generalising.
* **预算 versus 决算 cannot be separated, and the cheap route is closed.** Tagging rows by document
  genre gives 1,658 执行 against 78 计划 rows and only **14** unit-years with both — median ratio
  0.778 but mean 4.400 with p90 7.927, i.e. noise. The within-document route needs the
  column-aware parser from §4, because the two halves are two *columns*, not two documents. Worth
  doing: whether restraint appears as lower plans or as underspending against plan is the
  substantive question here.
* **Unit declarations are not a problem** (942 documents declare 万元 in the anchor segment, **1**
  declares 元), which was worth checking because mixing them is a 10,000× error.

## 6. Reproducing

```bash
python3 scripts/rnd/analysis/sangong_table.py                  # the report above
python3 scripts/rnd/analysis/sangong_table.py --csv out.csv     # the panel
python3 scripts/rnd/analysis/sangong_table.py --rejects 20      # why rows fail
python3 -m pytest tests/test_sangong_table.py                   # 15 tests, one per trap
```

`tests/test_sangong_table.py` pins each failure above as its own case, including the premise
checks: a bare year is rejected while `2022.00` with a decimal is still money; a phantom header
row does not become a sub-unit; a `1 2 3 4 …` run yields the data row beneath it and never
`7.0 1.0 3.0 3.0`; a narrative `1.因公出国… 2.公务接待…` enumeration is rejected; and a small
total **with** decimals (7.14万元) is kept, so the granularity bound is not a scale bound.
