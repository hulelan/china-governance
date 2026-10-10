# 三公经费 as a panel: feasible, not yet built

**Status: FEASIBILITY RESULT, not a finding.** Measured 2026-10-09 after
`extract_pdf_text.py` added body text to 1,950 attachment-only documents. Recorded so the
next person starts from what is proven rather than re-deriving it — and so nobody mistakes
160 validated rows for a dataset.

## Why this is worth wanting

三公经费 — 因公出国（境）费, 公务用车费, 公务接待费 — is the canonical Chinese
fiscal-transparency metric: disclosure is mandated in departmental budgets and final
accounts, and it was the explicit target of the post-2012 austerity campaign. A
department-year panel would be a political-economy object with a clean treatment date.

## What the corpus now holds

- **4,378 documents** mention 三公 with more than 1,500 characters of body, **2014-2026**
  (89-766 per year; the post-2021 jump is this session's PDF extraction).
- **2,327 departmental budget / final-account documents** over 1,500 characters, of which
  **100%** carry money figures (万元/亿元) and **100%** carry budget section headers.
- Concentrated on szdp 646, szlhq 332, wjw 289, swj 214, jtys 147, sf 132, zjj 104,
  stic 92, plus jiangmen and shaoguan.

## The dataset has a built-in validator, and that is the useful part

The documents assert an accounting identity:
**因公出国 + 公务用车 + 公务接待 = the disclosed 三公 total.** That is not a heuristic
imposed from outside; it is a check the source provides. Applying it to a naive regex
extraction:

| | rows |
|---|---|
| identity **holds** (components sum to the total, ±1 rounding unit) | **160** |
| all four numbers found but the sum **disagrees** | 187 |
| total or a component **not found** | 4,031 |

So **46% of rows with all four numbers are self-consistent**, and 160 rows survive overall.
**That is a demonstration, not a panel**, and it should not be written up as a finding.

## Why the 4,031 fail, and what would fix it

The failures are **not** mostly missing data. They are two things:

1. **Narrative reports.** `预算执行情况和预算草案的报告` documents are prose carrying dozens of
   unrelated figures, and a regex grabs the wrong one. The identity catches this loudly —
   e.g. one row parsed 公务接待 = 4,411.91 against a total of 4,411.91 (the same number), and
   another gave 公务接待 747 against a total of 575, which is impossible.
2. **Flowed tables.** The figures live in budget tables
   (`财政拨款"三公"经费支出决算表`) that PDF extraction renders as flowing text with the
   column structure gone. Regex over a flowed table is weak by construction.

**What would make this a dataset: table-aware parsing, not a better regex.** The budget tables
have a fixed, published row/column schema (表一 收入支出决算总表 … 表七/表九
"三公"经费支出决算表), so the right approach is to locate the named table and read its cells,
rather than to search the whole body. The structured `部门决算` documents extract cleanly
today — the gd 省府办公厅 2014 row validates to the cent — so the schema is reachable.

## What the validated rows already show (illustrative, n is tiny)

韶关市人民政府办公室, one office, its own disclosed figures:

| year | 三公 total (万元) | 出国 | 公务用车 | 公务接待 |
|---|---|---|---|---|
| 2015 | **164.14** | 22.05 | 131.95 | 10.15 |
| 2016 | 65.88 | 11.74 | 48.09 | 6.04 |
| 2017 | 43.14 | 12.47 | 28.11 | 2.56 |
| 2023 | **26.00** | 1.00 | 24.50 | 0.50 |

A **74% fall in two years** and 84% over eight. That is the austerity campaign in one
office's accounts — and at n=1 office it is an illustration of what a panel would measure,
nothing more. Do not cite it as a finding.

## Next step, stated concretely

1. Write a table locator: find `"三公"经费` + `决算表`/`预算表` and read the cells that follow,
   rather than regexing the body.
2. Keep the identity as the acceptance test — report the validated count as the n, always.
3. Only then ask the research question (does the 2012 campaign show up as a level shift, and
   does it differ by kind of body — the `fidelity-provincial.md` city-government-versus-bureau
   axis is available here too).
