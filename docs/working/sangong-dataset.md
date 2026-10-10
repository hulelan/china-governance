# 三公经费: a validated spending panel, and the validator that wasn't enough

*A table-aware parser for the 公开07 "三公"经费 table yields **1,775 accounting-validated
rows** from 1,366 documents and 470 units, 2011-2026. On a **fixed-unit** panel the series
is **flat** (+0.2% 2020-2024, median rising 20.07 → 23.09万元), while the same data read
as "all disclosures per year" falls 16%. The decline is composition, not austerity. Supersedes
the 160-row feasibility note in `sangong-feasibility.md`.*

## 1. What the dataset is

`scripts/rnd/analysis/sangong_table.py` parses the published 公开07 表 schema. Its 12 columns
carry four accounting identities that **the documents assert themselves**:

    c1 == c2 + c3 + c6      c3 == c4 + c5          (预算数: 合计, 出国, 用车[购置+运行], 接待)
    c7 == c8 + c9 + c12     c9 == c10 + c11        (决算数: the same, executed)

Only rows satisfying `total == out + car + host` (±0.05万元) are emitted, so **the reported n
is the validated n** — the acceptance criterion the feasibility note asked for. 2,984 of 4,350
candidate documents are rejected outright.

| | |
|---|---|
| validated rows | **1,775** (from 1,366 documents; layout C yields one row per sub-unit) |
| distinct units | 470 by title stem |
| fiscal years | 2011-2026; **dense only 2020-2024** (1,501 of 1,775 rows) |
| total 万元 | p05 1.00 · p25 4.85 · **median 13.74** · p75 44.73 · p95 386.64 · max 5,548.20 |
| composition | **公务用车 78%** · 公务接待 10% · 因公出国 12% |

Three layouts exist and one **reverses the column order** (layout C prints 接待 before 用车),
so the parser is label-anchored with candidate search rather than positional, and lets the
identity choose which candidate combination balances.

## 2. The finding, and the control that produces it

| year | fixed-unit panel (n=38, present in all five years) | all disclosures that year |
|---|---|---|
| 2020 | median 20.07 · mean 87.64 · sum 3330.1 | n=119 · median 13.96 · mean 76.21 |
| 2021 | median 19.20 · mean 91.58 · sum 3480.0 | n=218 · median 13.28 · mean 65.32 |
| 2022 | median 18.91 · mean 89.31 · sum 3393.9 | n=215 · median 17.99 · mean 75.53 |
| 2023 | median 21.69 · mean 84.55 · sum 3212.8 | n=187 · median 19.25 · mean 52.52 |
| 2024 | median 23.09 · mean 87.81 · sum 3336.8 | n=220 · median 17.84 · mean 63.74 |

**Fixed units: +0.2% over five years**, with 19 of 38 units up. **Unbalanced: means fall 16%.**
The gap is the mechanism: 三公 disclosure is an obligation that propagated *downward* through
the 2020s, so each year adds small units (街道办, 事业单位) whose budgets are a fraction of a
bureau's. A mean over "all disclosures in year Y" therefore measures **disclosure compliance**,
not spending. Only 38 of 470 units publish in all five years, which is itself the result: the
panel is shallow because the obligation is young.

This is the `panel.py` fixed-site discipline applied to a different unit of analysis. It changed
the sign here exactly as it did for the attention series.

## 3. The validator was not sufficient, and that is the transferable lesson

The run before the final fix reported **3,643 rows** with composition 公务用车 60% / 因公出国
32%, and I recorded that composition as confirming a falsifiable prediction. **Both numbers were
wrong.** A header-row guard removed 1,868 rows, of which **1,317 had `out == car == host`**; the
removed set's composition reads 出国 **91%**. The rows were built from **table column numbers and
一、二、三 enumerators**: `3 = 1 + 1 + 1` satisfies the identity perfectly.

Four parser versions, each failing differently:

| version | result | cause |
|---|---|---|
| positional, 12 columns after a marker run | 58 rows | three layouts exist and **layout C reverses 接待/用车** |
| label-anchored | **0 rows** | a full-body offset used as an index into a 900-char slice |
| candidate search | 3,874 rows, 出国 76%, p90 exactly **2022.00** | the 年度 column parsed as money |
| + bare integers in [1990, 2035] excluded | 3,643 rows | enumerators `1,2,3` sit **below** that window |
| + header-row guard (final) | **1,775 rows** | — |

**The lesson:** `total == out + car + host` is **scale-free**, so it cannot separate a real row
from a consistently wrong extraction. I patched the year-shaped hole and concluded the hole was
closed, when the actual fix was not a wider number filter but **table geometry** — two or more
field labels between the anchor and the first figure means a header row, whose labels then point
at the *next* row's figures. A validator checking a relation among extracted values says nothing
about whether the extraction picked the right values.

The guard's bar is **two** labels, not one, because layout B legitimately prints exactly one
(`一、因公出国（境）支出 300 …`) before its first figure.

## 4. What this panel cannot answer

* **The 2012 austerity campaign is not testable.** It is the natural treatment date and the
  feasibility note named it as step 3, but 2011-2019 holds 237 rows against 1,501 for 2020-2024,
  and no fixed-unit panel spans the 2012 boundary. Disclosure began in earnest after the
  obligation matured, so the pre-period does not exist in the corpus rather than being merely thin.
* **It is a Shenzhen panel, not a national one.** The top ten sites (szdp 338, szlhq 216, swj 182,
  szeb 171, hrss 88, jtys 85, wjw 82, sf 78, mzj 76, szlg 75) hold 1,401 of 1,775 rows. Read the
  flat result as a claim about one municipality's bureaus, and widen before generalising.
* **预算 versus 决算 is captured but not yet separated.** The schema's two halves (planned, executed)
  are the austerity question worth asking — whether restraint appears as lower plans or as
  underspending against plan — and the parser currently emits whichever half balances first.
  Splitting them is the obvious next step and needs no new extraction.
* **6 rows still carry `out == car == host`** and 68 sit under 1万元. Both are plausible for small
  units and neither is large enough to move the panel, but they are the residue to spot-check first
  if a figure looks wrong.

## 5. Reproducing

```bash
python3 scripts/rnd/analysis/sangong_table.py                  # the report above
python3 scripts/rnd/analysis/sangong_table.py --csv out.csv     # the panel
python3 scripts/rnd/analysis/sangong_table.py --rejects 20      # why rows fail
python3 -m pytest tests/test_sangong_table.py                   # 11 tests, one per trap
```

`tests/test_sangong_table.py` pins each failure above as its own case, including the premise
checks (a bare year is rejected; `2022.00` with a decimal is still money; a phantom header row
does not become a sub-unit).
