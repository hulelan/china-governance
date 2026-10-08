# The 文号 denominator in a second city: Wuxi against Shenzhen (2026-10-08)

*`wenhao-denominator.md` read the 文号 serial as a register count and found Shenzhen's 深府 series fell
from 276-365 a year in the late 1990s to 83-105 in the 2020s, and 深府办 collapsed to 3-24. It closed
on a warning: n = 1, on a special economic zone, "the method generalizes, the result does not." Wuxi
(无锡) is an ordinary Jiangsu prefecture-level city that has just been crawled to depth. This memo runs
the same estimators on it. The headline: over the window both cities can be measured on, 2010-2025,
the decline replicates in proportion. Wuxi's government register falls −6.8%/yr against Shenzhen's
−6.0%/yr, and its office series falls −12.6%/yr against −14.9%/yr. It does not replicate in timing or
depth. Wuxi held level until 2018 and then stepped down in 2019, where Shenzhen fell gradually from
2012. Wuxi's office series fell by three quarters, not nine tenths, so there is no collapse. One measured
trap sits in the middle of the series: in 2018 Wuxi moved its upward 请示 out of 锡政发 into a new 锡政呈
register, and read naively that relabelling looks like an 85% fall in one year.*

**Scope.** `site_key='wuxi'` plus the seven district and county-level-city sites `wxd_liangxi`,
`wxd_xishan`, `wxd_huishan`, `wxd_binhu`, `wxd_xinwu`, `wxd_jiangyin`, `wxd_yixing`, read-only from two
files on the droplet: `file:documents.db?mode=ro` (the first merge) and `file:documents_wuxi.db?mode=ro`
(the crawl's own file, which also holds the rows awaiting the second merge). Run `nice -n 19` on
2026-10-08 between 10:00 and 10:30 UTC, while the nightly held the lock. None of these rows is in
`doc_identity` or `citations` yet. Nothing here needs them: the method uses `document_number`,
`date_published`, and 文号 strings found in body text. Shenzhen figures are copied from
`wenhao-denominator.md` §4 unchanged. Labels: *measured* = a query in §8, *inferred* = my reading of
a measured pattern.

---

## 1. Coverage depth comes first

### 1.1 Which file each figure comes from (measured)

| file | `wuxi` rows | district rows | role here |
|---|---:|---:|---|
| `documents.db` | 2,209 | 2,668 | every held serial in the four government series |
| `documents_wuxi.db` | 3,865 | 2,668 (identical) | the second-merge rows, plus all body-text citations |
| union by `(site_key, url)` | **3,916** | 2,668 | the analysis universe |

The second file holds 1,707 `wuxi` URLs that `documents.db` does not (the merge log pre-registered
about 1,787). 51 `documents.db` rows have URLs the second file lacks. The district rows are the same in
both files.

**The 1,707 second-merge rows add zero serials to 锡政发, 锡政办发, 锡政规 or 锡政办规.** *Measured.*
They are departmental: 565 carry no 文号, and the rest are 锡民地函 (241), 锡房交付 (128), 锡金监复
(104), 锡建质安 (54), 锡建建市 (41) and similar bureau series, 739 of them dated 2020 and 537 dated
2021. So every government-series table below would be identical on `documents.db` alone. The second
file matters only for the departmental inventory in §2 and as a body-text source in §1.3.

### 1.2 文号 coverage per site and per year (measured)

| site | docs | with 文号 | parse as (prefix, year, serial) |
|---|---:|---:|---:|
| wuxi | 3,916 | 2,903 (74.1%) | 2,849 (72.8%) |
| wxd_jiangyin | 756 | 663 (87.7%) | 663 |
| wxd_xishan | 450 | 322 (71.6%) | 309 |
| wxd_liangxi | 209 | 131 (62.7%) | 130 |
| wxd_binhu | 83 | 44 (53.0%) | 44 |
| wxd_huishan | 47 | 22 (46.8%) | 22 |
| wxd_yixing | 36 | 27 (75.0%) | 27 |
| wxd_xinwu | 1,087 | 12 (1.1%) | 11 |

The header-table fix in `c524768` worked where it applies. 文号 coverage is 74% on the municipal site
and 88% on Jiangyin. 新吴区 is the exception at 1.1%: its pages carry no 文号 field, so it contributes
only body-text citations. *Measured.*

The municipal site's depth by `date_published` year (docs / with 文号 / parsed):

| years | docs per year | parsed 文号 per year |
|---|---|---|
| 1993-2006 | 1 to 18 | 0 to 7 |
| 2007-2010 | 18 to 99 | 12 to 44 |
| 2011-2019 | 41 to 138 | 28 to 106 |
| 2020-2021 | 790, 629 | 705, 531 |
| 2022-2025 | 185 to 423 | 124 to 313 |

**The held corpus is shallow before 2011 and thin before 2007.** The 2020-2021 spike is the
departmental 信息公开 sections, which begin in 2019-2020. *Measured.*

### 1.3 A second sample: serials cited in body text

The crawl held too few pre-2013 government documents for the Shenzhen estimator to work on held rows
alone (锡政发 held k is 1 to 6 per year before 2013). So I added a second, independent sample. Every 文号
of the form 锡政发〔yyyy〕N号 that appears in the title or body of any document, other than the document's
own 文号, is a real serial: the issuing office assigned it. Sources are the whole of `documents_wuxi.db`
and every `documents.db` row that the FTS index `doc_search` matches on 锡政发 / 锡政办 / 锡政规 /
锡政呈 / 锡政函 / 锡政复 / 锡政字, which brings in 132 citations from the Jiangsu provincial site `js`
(provincial 批复 quoting the city's 请示 by number). *Measured:* 430 cited 锡政发 serials, 357 of them
not held; 402 cited 锡政办发 serials, 276 not held. Cleanup catalogues (文件清理目录 listing documents
by number with an 适用期) are the richest single source.

This is a different selection mechanism from the held set. The held set is what the city chose to
publish online. The cited set is what later documents chose to cite. §3 tests whether either is
serial-blind, and whether they agree.

### 1.4 Earliest usable year per series (measured)

| series | held, k ≥ 3 from | held, k ≥ 8 from | held ∪ cited, k ≥ 4 from |
|---|---|---|---|
| 锡政发 | 2003 (gap 2012) | 2013 | 1985 (k 4 to 12 to 1999) |
| 锡政办发 | 2007 | 2007 (except 2010, k = 4) | 2000 (k 3 to 7 through 2005) |
| 锡政呈 | never held | . | 2018 (cited only, k 2 to 11) |
| 锡政规 | 2011 | . | 2011 |

**The usable comparison window is 2010-2025.** Within it, 锡政发 has union k ≥ 8 in every year
2010-2024 and 锡政办发 has k ≥ 15 in every year 2010-2025. 锡政呈 is the weak component (k 2 to 11). 2000-2009 is a band estimate on the government series (k 4 to 28,
inclusion 1 to 6%), and 1985-1999 is a floor with a wide band (k 4 to 12). Shenzhen's comparison values
for 2010-2025 are its post-seam single regime, where it fell −5.9%/yr (深府) and −14.3%/yr (深府办) on
2010-2026. This memo recomputes Shenzhen on 2010-2025 so both cities use the same years: −6.0%/yr and
−14.9%/yr.

---

## 2. The series inventory

### 2.1 Exclusions (measured)

The Shenzhen exclusion rules, applied unchanged. Of 4,124 non-empty 文号 across the eight sites, 4,055
parse as (prefix, year, serial). The other 69 are excluded:

| shape | rows | why |
|---|---:|---|
| 政府令第N号 (mayor's orders) | 21 | One continuous series (observed 38 to 183), not annual. |
| 公告第N号 / bare 第N号 | 5 | Per-term announcement counters. |
| bare year (`2023`, `2018年`) | 13 | Xishan field holds a year, not a number. |
| other | 30 | Field labels (`备注`, `文件名称`), a title, `1`, and 5 malformed numbers like `锡政办发20130265号` |

The five malformed numbers (锡政发 2011 #128, 锡政办发 2013 #263, #265, #269, 锡委办发 2013 #129) all fall
below their year's observed maximum, so leaving them out changes no estimate. No issue numbers (总第N期)
leaked into `document_number`. Full-width digits (锡府办［２０１９］３３号) and spaced forms
(城 发 〔 2 0 2 2 〕 5 8 号) were NFKC-normalized and parsed. *Measured.*

The 文号 year is used, not the publication year, as in Shenzhen. On 锡政发 and 锡政办发 they agree on 715
of 767 rows; 38 are published the year after their 文号 (December documents posted in January), 5 two to
three years later, and 9 are reposts 6 to 16 years later.

### 2.2 Series with 15 or more distinct held serials

`held` = distinct serials held, `medIncl%` = median across years of held ÷ N̂_max. Classes by the
Shenzhen rule: **floor** = maximum serial under 30 and median inclusion ≥ 50%; **trendable** = eight or
more years with three or more held; **thin** = everything else.

| series | site | held | yrs | span | maxser | medIncl% | class |
|---|---|---:|---:|---|---:|---:|---|
| 锡政办发 | wuxi | 475 | 27 | 2000-2026 | 369 | 9.3 | trendable |
| 澄政发 | jiangyin | 338 | 13 | 2011-2023 | 192 | 24.4 | trendable |
| 澄政办发 | jiangyin | 323 | 8 | 2012-2023 | 133 | 48.9 | thin (short) |
| 锡民地函 | wuxi | 247 | 4 | 2020-2025 | 144 | 56.8 | thin (short) |
| 锡政发 | wuxi | 239 | 30 | 1993-2025 | 480 | 1.9 | trendable |
| 锡房交付 | wuxi | 196 | 7 | 2020-2026 | 70 | 89.5 | thin (short) |
| 锡金监复 | wuxi | 178 | 5 | 2019-2023 | 65 | 89.1 | thin (short) |
| 锡府办 | xishan | 164 | 15 | 2012-2026 | 99 | 14.2 | trendable |
| 锡府发 | xishan | 132 | 15 | 2012-2026 | 111 | 18.6 | trendable |
| 锡建建市 | wuxi | 132 | 8 | 2019-2026 | 38 | 73.8 | thin (short) |
| 锡建质安 | wuxi | 97 | 8 | 2019-2026 | 62 | 37.1 | thin (short) |
| 梁政办发 | liangxi | 78 | 8 | 2018-2025 | 90 | 16.3 | thin |
| 锡人社发 | wuxi | 64 | 8 | 2019-2026 | 157 | 11.7 | thin |
| 锡发改价格 | wuxi | 50 | 8 | 2019-2026 | 26 | 43.9 | trendable |
| 锡财购 | wuxi | 49 | 7 | 2020-2026 | 23 | 27.3 | thin (short) |
| 锡政规 | wuxi | 49 | 15 | 2011-2025 | 9 | 100.0 | floor |
| 梁政发 | liangxi | 47 | 8 | 2018-2025 | 89 | 9.1 | thin |
| 锡政复 | wuxi | 46 | 6 | 2013-2021 | 102 | 12.7 | thin |
| 锡人社函 | wuxi | 46 | 6 | 2020-2025 | 201 | 3.6 | thin |
| 锡财会 | wuxi | 44 | 7 | 2020-2026 | 27 | 42.9 | thin (short) |
| 锡建设 | wuxi | 29 | 7 | 2020-2026 | 29 | 22.5 | thin (short) |
| 锡供 | wuxi | 24 | 6 | 2020-2025 | 48 | 11.2 | thin |
| 锡滨政办发 | binhu | 23 | 6 | 2021-2026 | 64 | 6.5 | thin |
| 锡建开 | wuxi | 23 | 6 | 2019-2025 | 75 | 100.0 | thin (short) |
| 宜政规发 | yixing | 22 | 8 | 2016-2025 | 5 | 88.1 | floor |
| 锡建办函 | wuxi | 22 | 2 | 2021-2022 | 119 | 11.6 | thin |
| 锡建房市 | wuxi | 18 | 7 | 2020-2026 | 9 | 40.0 | thin (short) |
| 锡教发 | wuxi | 17 | 4 | 2019-2022 | 126 | 5.5 | thin |
| 锡建发 | wuxi | 17 | 5 | 2020-2025 | 59 | 13.9 | thin |
| 锡政通 | wuxi | 16 | 6 | 2005-2012 | 9 | 33.8 | thin |
| 锡政告 | wuxi | 16 | 9 | 2013-2024 | 7 | 20.0 | thin |
| 惠府办 | huishan | 15 | 4 | 2020-2026 | 42 | 12.3 | thin |
| 锡滨政发 | binhu | 15 | 6 | 2017-2024 | 42 | 11.7 | thin |
| 锡财税法 | wuxi | 15 | 7 | 2020-2026 | 11 | 22.0 | thin (short) |
| 锡建城 | wuxi | 15 | 6 | 2020-2025 | 10 | 50.3 | floor |

35 series: 6 trendable, 26 thin, 3 floor. *Measured.* "Thin (short)" marks series whose inclusion is
high but which span fewer than eight years because departmental coverage begins in 2019-2020. Shenzhen's
thin class also mixed both kinds (深市监标, 98.6% inclusion, 6 years). The difference from Shenzhen
matters: there, many departmental series ran 10 to 20 years in the gazette; here no departmental series
reaches back before 2019 in the held set. **Wuxi's departmental tier cannot be trended at all.**

Three further government-level series exist only in citations (§1.3), so they are not in the held
inventory:

| series | what it is (from cited context) | cited k | observed maxima |
|---|---|---:|---|
| 锡政呈 | upward 请示 to the province, from 2018 | 32 | 2018: 268, 2019-2025: 50-94 |
| 锡政字 | internal handling register (地名 approvals cite it) | 47 | 2020: 1,278; 2021: 868; 2023: 234; 2025: 323 |
| 锡政办通 | office 通知 for circulation | 8 | 2011: 551; 2012: 282; 2018: 76 |

All three are floors only. 锡政字〔2020〕1278号 says the city numbered at least 1,278 items in that
register in 2020. *Measured.* There is no municipal 锡政函 or 锡政办函 series of any size in this corpus
(锡政办函: 3 cited serials, maximum 29), so the Shenzhen 函 comparison (§4.3 there) cannot be run.

### 2.3 The 规 registers: a census, in the same window

锡政规 begins in **2011** in both the held set and the citations, runs 1 to 9 a year, and sits at 100%
inclusion in 12 of 15 years. Departmental 规 registers are first seen, through citations, in the same
window: 锡交规发 2010, 锡规规发 2010, 锡人口计生规发 2011, 锡房规发 2011, 锡人社规发 2012,
锡建规发 2013, 锡卫规发 2014, 锡民规 2017. Their maximum serials are 1 to 8. 锡政办规 begins in **2024**,
later than 深府办规 (2017). *Measured.* Series whose name contains 规 but whose serials run to 83-333
(锡价规, 锡自然资规发, 锡科规, 锡卫法规) are bureau or division prefixes (规划, 法规处), not registers, and
are excluded.

**This replicates.** Small near-census registers appear in Wuxi between 2010 and 2017, inside the
2007-2019 Shenzhen window, at the same scale (single digits per year). The one difference is the
General Office register, seven years later than Shenzhen's. Because departmental held coverage starts in
2019, the departmental start years are the earliest *citing* year, an upper bound on the true start.

---

## 3. Defending the estimator on Wuxi

### 3.1 Method of moments against the maximum (measured)

Ratio N̂_mean / N̂_max across series-years with four or more distinct serials:

| sample | band | series-years | median | mean | IQR |
|---|---|---:|---:|---:|---|
| held, all eight sites | ≥ 50% | 53 | 1.000 | 1.007 | 0.98 - 1.06 |
| | 20 - 50% | 59 | 0.988 | 1.006 | 0.90 - 1.05 |
| | 10 - 20% | 50 | 1.006 | 1.015 | 0.87 - 1.19 |
| | < 10% | 46 | 0.985 | 1.016 | 0.86 - 1.14 |
| cited serials only | 20 - 50% | 6 | 1.045 | 1.012 | 0.85 - 1.13 |
| | 10 - 20% | 10 | 1.017 | 1.012 | 0.94 - 1.13 |
| | < 10% | 53 | 0.999 | 0.986 | 0.87 - 1.09 |

The same pattern as Shenzhen. The median ratio stays between 0.99 and 1.05 in every band and in both
samples. What widens as inclusion falls is the spread. *Inferred:* the error here is variance, not
bias, for the held pages and for the citations alike. By era, on the union, the ratio is 1.007
(1985-1999), 0.941 (2000-2009), 0.982 (2010-2017) and 0.987 (2018-2025) for 锡政发, and 1.055, 1.032,
0.982 for 锡政办发 over the last three eras. No era is systematically mis-read.

### 3.2 The two samples against each other (measured)

Where both the held set and the cited set have k ≥ 8 in the same series-year, N̂_max from the cited
serials alone divided by N̂_max from the held serials alone:

| series | years compared | median ratio | range |
|---|---:|---:|---|
| 锡政发 | 7 (2013-2020) | 1.02 | 0.91 - 1.43 |
| 锡政办发 | 14 (2008-2023) | 1.01 | 0.85 - 1.44 |

Two mechanisms that select documents for different reasons (online publication versus later citation)
give the same register size. The two 1.4 outliers are both 2015. For 锡政发 a provincial 批复 quotes
锡政发〔2015〕513号, a 请示 the city never published, against a held maximum of 362; for 锡政办发 a cited
329 sits against a held maximum of 232. *Inferred:* the
union is a better sample than either half, and it is what the tables below use. Held-only trends are
reported beside it and differ by under 2 points in the main window.

### 3.3 The date estimator and the order statistic (measured)

N̂_date (serial regressed on day of year, predicted at day 365) has median ratio **0.974** to N̂_max
across 147 qualifying Wuxi series-years, against 0.912 in Shenzhen. *Inferred:* less year-end bunching
in Wuxi, so N̂_date undershoots less, but it is still a lower bound and is not used below.

Order-statistic tests, P(all k pooled serials ≤ m) = (m/N)^k:

| series, years pooled | k | m | N = 100 | N = 150 | N = 200 |
|---|---:|---:|---:|---:|---:|
| 锡政发, 2020-2024 | 74 | 38 | 8.0 × 10⁻³² | 7.5 × 10⁻⁴⁵ | 4.2 × 10⁻⁵⁴ |
| 锡政办发, 2019-2025 | 251 | 108 | . | 1.6 × 10⁻³⁶ | 6.8 × 10⁻⁶⁸ |
| 锡政呈, 2019-2025 | 20 | 94 | 0.29 | 8.7 × 10⁻⁵ | 2.8 × 10⁻⁷ |

After 2019 the 锡政发 series is far below 100 a year, the office series is below 150, and the 请示
register does not reject 100 a year but rejects 150. The pre-2018 floors are hard numbers: 锡政发 maxima
are 357 to 492 in every year 2003-2009 and 190 to 513 in 2010-2017. *Measured.*

---

## 4. Results

### 4.1 锡政发, and the 2018 register split

| year | held k | held N̂_max | union k | union m | N̂_max | N̂_mean | incl % |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1985-1999 | 0-2 | . | 4-12 | 124-357 | 148-407 | 120-435 | 1.2-5.9 |
| 2000 | . | . | 4 | 340 | 424 | 335 | 0.9 |
| 2001 | 1 | 601 | 10 | 301 | 330 | 309 | 3.0 |
| 2002 | 2 | 408 | 9 | 360 | 399 | 412 | 2.3 |
| 2003 | 3 | 287 | 18 | 361 | 380 | 484 | 4.7 |
| 2004 | 5 | 409 | 15 | 363 | 386 | 365 | 3.9 |
| 2005 | 3 | 534 | 13 | 405 | 435 | 382 | 3.0 |
| 2006 | 3 | 402 | 28 | 492 | 509 | 452 | 5.5 |
| 2007 | 5 | 575 | 16 | 491 | 521 | 528 | 3.1 |
| 2008 | 6 | 347 | 21 | 357 | 373 | 380 | 5.6 |
| 2009 | 5 | 246 | 17 | 432 | 456 | 298 | 3.7 |
| 2010 | 4 | 239 | 12 | 192 | 207 | 236 | 5.8 |
| 2011 | 6 | 272 | 21 | 234 | 244 | 264 | 8.6 |
| 2012 | 2 | 407 | 13 | 272 | 292 | 276 | 4.5 |
| 2013 | 9 | 189 | 23 | 190 | 197 | 195 | 11.7 |
| 2014 | 16 | 212 | 31 | 200 | 205 | 189 | 15.1 |
| 2015 | 33 | 372 | 47 | 513 | 523 | 506 | 9.0 |
| 2016 | 28 | 280 | 41 | 272 | 278 | 277 | 14.8 |
| 2017 | 13 | 367 | 35 | 342 | 351 | 342 | 10.0 |
| **2018** | 20 | **53** | 22 | 56 | **58** | 58 | 38.2 |
| 2019 | 3 | 36 | 8 | 74 | 82 | 52 | 9.7 |
| 2020 | 10 | 41 | 16 | 38 | 39 | 44 | 40.6 |
| 2021 | 9 | 27 | 9 | 25 | 27 | 27 | 33.6 |
| 2022 | 16 | 37 | 19 | 36 | 37 | 36 | 51.5 |
| 2023 | 19 | 28 | 20 | 28 | 28 | 30 | 70.4 |
| 2024 | 9 | 27 | 10 | 25 | 27 | 19 | 37.7 |
| 2025 | 3 | 7 | 4 | 8 | 9 | 8 | 44.4 |

2015 (523) rests on that one cited 请示 serial, 513; the held maximum is 362, so 2015 is a high draw
rather than a peak. Read alone, this series falls from 351 in 2017 to 58 in 2018, an 84% drop in one year, at the highest
inclusion the series ever has (38%). That is not a decline. It is a relabelling, and it is measured.

The Jiangsu provincial site quotes the city's 请示 by number in its 批复. Every 请示 it quotes from 2002
through 2017 is numbered 锡政发 (100 distinct, 2002-2017, maxima up to 513). Every one it quotes from 2018
on is numbered **锡政呈** (32 distinct, 2018-2026). There is no overlap year. *Measured.* So before 2018 the
锡政发 register carried both downward 文件 and upward 请示, and from 2018 the 请示 have their own register.

锡政呈 in 2018 reaches at least 268 (k = 11, N̂_max 291). Added to 锡政发's 58, the 2018 register total
is about 349, against 351 in 2017. *Measured.* The split moved numbers between registers and changed
nothing in total.

Shenzhen did not split. The Guangdong-side citations of Shenzhen 请示 are numbered 深府 in 2007, 2010,
2016 and 2018, and no 深府呈 or 深府请 serial exists anywhere in the corpus. *Measured.* So **深府 is
comparable to 锡政发 + 锡政呈, not to 锡政发 alone.** Every comparison in §5 uses that combined register.

### 4.2 The combined government register, 锡政发 + 锡政呈

| year | 锡政发 N̂_max | 锡政呈 N̂_max (k) | combined N̂_max | combined N̂_mean |
|---|---:|---:|---:|---:|
| 2017 | 351 | (inside 锡政发) | 351 | 342 |
| 2018 | 58 | 291 (11) | **349** | 350 |
| 2019 | 82 | 66 (3) | **148** | 135 |
| 2020 | 39 | 112 (5) | 151 | 169 |
| 2021 | 27 | 115 (3) | 142 | 90 |
| 2022 | 37 | 114 (3) | 151 | 139 |
| 2023 | 28 | 86 (2) | 114 | 122 |
| 2024 | 27 | none cited | . | . |
| 2025 | 9 | 63 (4) | 72 | 54 |

**The real step is 2019, not 2018.** The combined register falls from about 350 to about 150 and stays
there through 2022, then 114 in 2023. The 锡政呈 component rests on k of 2 to 5, so each year is a ±30%
band, but the pooled order statistic in §3.3 caps 锡政呈 below 150 a year after 2018, so the combined
register after 2019 is below about 200 even at the generous end, against floors of 190 to 513 in every
year 2010-2017. *Measured.* 2025 is low on both components (锡政发 k = 4) and is a band.

### 4.3 锡政办发, the General Office series

| year | held k | held N̂_max | union k | N̂_max | N̂_mean | incl % |
|---|---:|---:|---:|---:|---:|---:|
| 2000-2006 | 1-3 | 88-289 | 3-12 | 143-528 | 158-312 | 1.4-4.7 |
| 2007 | 9 | 300 | 12 | 293 | 354 | 4.1 |
| 2008 | 14 | 394 | 29 | 382 | 418 | 7.6 |
| 2009 | 17 | 363 | 25 | 358 | 360 | 7.0 |
| 2010 | 4 | 359 | 15 | 336 | 427 | 4.5 |
| 2011 | 21 | 369 | 35 | 366 | 384 | 9.6 |
| 2012 | 25 | 304 | 28 | 302 | 285 | 9.3 |
| 2013 | 31 | 307 | 48 | 303 | 347 | 15.8 |
| 2014 | 18 | 194 | 28 | 211 | 169 | 13.2 |
| 2015 | 35 | 238 | 50 | 335 | 280 | 14.9 |
| 2016 | 29 | 242 | 47 | 239 | 242 | 19.7 |
| 2017 | 29 | 256 | 46 | 252 | 288 | 18.2 |
| 2018 | 33 | 161 | 53 | 159 | 145 | 33.3 |
| **2019** | 16 | 70 | 33 | **75** | 74 | 43.9 |
| 2020 | 24 | 85 | 43 | 85 | 81 | 50.6 |
| 2021 | 36 | 98 | 45 | 97 | 113 | 46.3 |
| 2022 | 43 | 107 | 55 | 109 | 118 | 50.5 |
| 2023 | 17 | 73 | 23 | 72 | 72 | 31.9 |
| 2024 | 21 | 59 | 24 | 58 | 53 | 41.1 |
| 2025 | 27 | 57 | 28 | 57 | 56 | 49.1 |
| 2026 (to 09-30) | 11 | 21 | 11 | 21 | 21 | 52.8 |

The office series sits at 300 to 390 through 2008-2013, eases to 211-335 through 2017, halves in 2018
(159) and halves again in 2019 (75). It then holds at 57 to 109. No office 请示 register (锡政办呈,
锡政办请) exists in the corpus, so this fall is not a split. *Measured.* As in Shenzhen, the collapse is
not an inclusion artefact: inclusion **rises** from 5-20% in 2008-2017 to 32-51% after, while the
estimate falls by three quarters.

### 4.4 A third and fourth jurisdiction, for context only

The county-level and district series are trendable over shorter spans (held only, N̂_max):

| series | 2012 | 2014 | 2016 | 2018 | 2019 | 2020 | 2022 | 2024 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 澄政发 (江阴市, k 18-54) | 195 | 109 | 83 | 143 | 106 | 119 | 164 | . |
| 澄政办发 (江阴市, k 31-80) | . | . | 134 (2017) | 130 | 72 | 75 | 89 | . |
| 锡府发 (锡山区, k 4-23) | 94 | 39 | 72 | 126 | 98 | 32 | 37 | 22 |
| 锡府办 (锡山区, k 6-28) | 94 | 87 | 93 | 73 | 105 | 99 | 79 | 45 |

Jiangyin's government series dips 2012-2016 and recovers to 164 by 2022: no sustained decline. Its
office series halves in 2019, as Wuxi's does. Xishan's government series falls after 2019. *Measured,*
with the caveat that each of these is one site's 信息公开 page.

---

## 5. The comparison

### 5.1 Both cities on one normalized scale

Each series indexed to its own 2010-2012 mean = 100, so city size does not drive the comparison. The
base is the first three years of the post-seam window the Shenzhen memo used, and both Wuxi series have
k ≥ 12 in each of them. Bases: Wuxi combined 248, 锡政办发
335; 深府 187, 深府办 95. Wuxi values are union N̂_max (k in parentheses); Shenzhen values are gazette
N̂_max from `wenhao-denominator.md` §4.1-4.2.

| year | Wuxi gov (锡政发+呈) | Shenzhen 深府 | Wuxi office (锡政办发) | Shenzhen 深府办 |
|---|---:|---:|---:|---:|
| 2000 | 171 (4) | 90 | 45 (7) | 113 |
| 2003 | 153 (18) | 124 | 43 (4) | 146 |
| 2006 | 205 (28) | 145 | 158 (12) | 251 |
| 2008 | 151 (21) | 154 | 114 (29) | 140 |
| 2009 | 184 (17) | 130 | 107 (25) | 143 |
| **2010** | 84 (12) | 106 | 100 (15) | 117 |
| **2011** | 99 (21) | 114 | 109 (35) | 120 |
| **2012** | 118 (13) | 80 | 90 (28) | 63 |
| 2013 | 80 (23) | 67 | 91 (48) | 34 |
| 2014 | 83 (31) | 61 | 63 (28) | 17 |
| 2015 | 211 (47) | 65 | 100 (50) | 41 |
| 2016 | 112 (41) | 58 | 71 (47) | 41 |
| 2017 | 142 (35) | 49 | 75 (46) | 25 |
| 2018 | 141 (33) | 48 | 47 (53) | 16 |
| 2019 | 60 (11) | 34 | 22 (33) | 8 |
| 2020 | 61 (21) | 52 | 25 (43) | 3 |
| 2021 | 57 (12) | 44 | 29 (45) | 5 |
| 2022 | 61 (22) | 44 | 33 (55) | 21 |
| 2023 | 46 (22) | 56 | 22 (23) | 10 |
| 2024 | . | 56 | 17 (24) | 13 |
| 2025 | 29 (8) | 28 | 17 (28) | 16 |

Rows before 2010 are bands (Wuxi k 4 to 29 at 1 to 6% inclusion); the Wuxi office rows before 2007 rest
on k ≤ 7. Pre-2000 Wuxi values are omitted from this table and summarized in §5.3.

### 5.2 Rates and levels over the overlapping window (measured)

Log-linear trend on N̂_max (N̂_mean in brackets), complete years only:

| series | 2010-2025 | 2010-2017 | 2019-2025 | mean level 2019-2024, index of 2010-12 |
|---|---:|---:|---:|---:|
| Wuxi gov, 锡政发 + 锡政呈 | **−6.8%/yr** (−8.3) | +7.6%/yr (+5.7) | −11.1%/yr (−13.2) | **57** |
| Shenzhen 深府 | **−6.0%/yr** (−6.6) | −10.7%/yr (−11.9) | −0.9%/yr (−0.1) | **48** |
| Wuxi office, 锡政办发 | **−12.6%/yr** (−13.0) | −4.9%/yr (−6.7) | −6.5%/yr (−7.3) | **25** |
| Shenzhen 深府办 | **−14.9%/yr** (−14.9) | −19.4%/yr (−19.5) | +21.1%/yr (+26.0) | **10** |
| *(naive: 锡政发 alone)* | *−19.7%/yr* | *+7.6%/yr* | *−23.1%/yr* | *(meaningless after 2018)* |

The Wuxi government level averages 2019-2023 because 2024 has no 锡政呈 citation. Held-only Wuxi
trends over 2010-2025: 锡政办发 −12.5%/yr, nearly identical to the union. The Shenzhen
2019-2025 office rate is a rebound off 3 to 5 a year and carries no weight.

### 5.3 What the pre-2010 years can and cannot say

Wuxi's government register, on the union, averages 297 a year in 1995-1999 (range 172-407, k 4 to 9)
and 421 in 2000-2009 (330-521, k 4 to 28). The observed maximum serials alone, which are hard floors,
are 357 to 492 in every year 2003-2009. Shenzhen's 深府 averages 300 and 242 over the same two periods.
*Measured.* So **Wuxi shows no 1995-2009 decline.** Its register rose into the 2000s while Shenzhen's
eased. The 1990s Wuxi figures carry ±30% bands and could not detect a modest fall; they can rule out the
2000s being smaller than the late 1990s, because the 2000s floors exceed most of the 1990s estimates.

Wuxi's office series before 2007 (k ≤ 7, 33 to 215 a year) is too thin to compare.

---

## 6. Reading

### 6.1 What is established

1. **The post-2010 decline replicates in proportion.** Over 2010-2025 Wuxi's government register falls
   −6.8%/yr against Shenzhen's −6.0%/yr, and both end the window at roughly half their 2010-2012 level
   (index 57 and 48). Both estimators agree within 1.5 points, two independent samples agree on the
   register sizes, and the order statistic rejects 150 a year for Wuxi's post-2019 请示 register and 100
   a year for its post-2019 文件 register. *Measured.*
2. **The office series declines in both cities, but only Shenzhen's collapses.** Wuxi's 锡政办发 falls
   −12.6%/yr (Shenzhen −14.9%/yr) to an index of 25, holding at 57 to 109 documents a year. Shenzhen's
   falls to an index of 10, at 3 to 24 a year. Wuxi's office still numbers more 文件 than its government
   does after 2019 (57-109 against 27-82 for 锡政发). *Measured.*
3. **The timing differs by about six years.** Shenzhen's 深府 and 深府办 fall through 2012-2017 and are
   flat after 2019. Wuxi's government register is level to rising through 2017 and its office series eases only
   slightly (−4.9%/yr); both then step down, the office in 2018 and both in 2019. Over 2010-2017 they move in opposite directions (+7.6%/yr against −10.7%/yr). *Measured.*
4. **The 2018 drop in 锡政发 is a register split, not a fall.** The upward 请示 moved to 锡政呈 in 2018;
   the combined total is unchanged that year (351 → 349). *Measured.* Any reading of 锡政发 alone across
   2018 would report an 84% one-year collapse that did not happen.
5. **The 规范性文件 registers replicate.** 锡政规 starts in 2011 and departmental 规 registers are first
   cited 2010-2017, all at 1 to 9 a year and near-full inclusion, inside the Shenzhen window. 锡政办规
   (2024) is the late exception. *Measured.*
6. **There is no 1995-2009 decline in Wuxi** on band-quality data. *Measured, as a band.*

### 6.2 Is the difference institutional or coverage?

**Not coverage.** The Wuxi years that differ most from Shenzhen, 2013-2018, are Wuxi's best-measured
years: union k 22 to 47, inclusion 9 to 38%, held and cited samples agreeing to a median 1.01-1.02.
The 2019 step happens while inclusion is rising, not falling. A coverage artefact would run the other
way. *Inferred from measured inclusion.*

**Institutional, but not visibly about 特区法规.** Two things in the data are institutional and both are
about numbering practice. One is measured: the 2018 锡政呈 split. The other is timing: three Wuxi
registers (锡政发, 锡政呈, 锡政办发), plus Jiangyin's office series, all step down in the same year, 2019.
*Inferred:* a common cause acting on a whole numbering system in one year looks like a directive, not
drift. 2019 was designated the year for reducing burdens on the grassroots (基层减负年), whose stated
targets included cutting the volume of documents; that is a plausible candidate and **this memo does not
test it.** If it is the cause, the two cities converge rather than share a trajectory: Shenzhen had
already cut by 2017 and shows no 2019 step in 深府, Wuxi had not and cut at once.

Nothing here ties Shenzhen's earlier and deeper fall to its special-zone legislative powers. That
reading would predict a Shenzhen-specific channel substituting for 文件, and the Shenzhen memo found the
law-like channel (深府规, 深府办规) too small to absorb the fall. What these data support is narrower: the
same end state, about half the 2010 government register and a quarter or less of the office register,
was reached by two cities by different routes in different years.

### 6.3 Limits

1. **n = 2, both coastal and rich.** Wuxi is ordinary in legal status, not in income. A city in the
   interior is the obvious third case.
2. **Before 2010 Wuxi rests on citations.** k of 4 to 28 at 1 to 6% inclusion. §3 shows citation
   sampling is serial-blind at the centre, but the pre-2010 rows are bands, and §5.3 is the weakest
   claim here.
3. **锡政呈 rests on 32 citations, all from one provincial site.** After 2018 its yearly k is 2 to 5.
   The combined register after 2019 is a band of roughly ±30% per year; the order statistic bounds it,
   but the yearly index values in §5.1 for Wuxi gov after 2018 are bands.
4. **Other split registers may exist.** I searched for upward and letter registers by prefix (锡政呈,
   锡政请, 锡政报, 锡政办呈, 锡政办请, 锡政函, 锡政办函). A register I did not think to search for would
   bias 锡政发 low after its creation. 锡政字 (≥1,278 in 2020) is a large internal register visible only
   from 2020 and cannot be dated or trended.
5. **2024 has no 锡政呈 citation** and is blank for the combined series. 2025 rests on 锡政发 k = 4.
   2026 is partial and excluded throughout.
6. **This measures numbered issuance, not governing,** exactly as in Shenzhen. Wuxi's departmental tier
   is held only from 2019 and cannot be trended, so a shift of work from the municipal registers to the
   bureaus is not testable here.

---

## 7. Verdict

**(a) The decline replicates, in proportion, over 2010-2025.** Wuxi's government register (锡政发 +
锡政呈) falls −6.8%/yr against 深府's −6.0%/yr and ends at index 57 against 48; Wuxi's office series falls
−12.6%/yr against 深府办's −14.9%/yr. The 规范性文件 registers appear in the same window at the same
scale. What does **not** replicate is the path: Wuxi held level through 2017 and stepped down in 2019,
Shenzhen fell through 2012-2017, and Wuxi's office series fell by three quarters, not the nine tenths
that makes 深府办 a collapse. The pre-2010 Shenzhen decline does not appear in Wuxi at all.

**Main limit:** the Wuxi government series after 2018 depends on 锡政呈, a register seen only through 32
provincial citations, so the post-2019 Wuxi level is a ±30% band bounded by an order statistic, not a
point estimate.

---

## 8. SQL and reproduction appendix

Universe and 文号 coverage, run on both files:

```sql
-- documents.db (first merge) and documents_wuxi.db (crawl file), each opened ?mode=ro
SELECT site_key, count(*), sum(document_number!=''), min(date_published), max(date_published)
FROM documents WHERE site_key='wuxi' OR site_key LIKE 'wxd_%' GROUP BY 1;
-- documents.db:      wuxi 2209 | 1761
-- documents_wuxi.db: wuxi 3865 | 2956 ; districts identical in both (jiangyin 756 | 663, xinwu 1087 | 12, ...)
```

The union is taken in Python on `(site_key, url)`: 2,158 shared `wuxi` URLs, 1,707 only in
`documents_wuxi.db`, 51 only in `documents.db`, 3,916 total.

Parse: the Shenzhen regex unchanged, after NFKC normalization and removal of spaces, then `无锡市` → `锡`
in the prefix:

```
^(.*?)[〔\[（(【]\s*(\d{4})\s*[〕\]）)】]\s*(?:第)?\s*(\d+)\s*号?\s*$
```

Per series per year, the SQLite form for the dominant 〔〕 shape (use `avg(DISTINCT ser)` as the Shenzhen
appendix notes):

```sql
WITH p AS (
  SELECT replace(substr(document_number,1,instr(document_number,'〔')-1),'无锡市','锡') AS series,
         CAST(substr(document_number,instr(document_number,'〔')+1,4) AS integer)     AS yr,
         CAST(replace(substr(document_number,instr(document_number,'〕')+1),'号','') AS integer) AS ser
  FROM documents
  WHERE site_key='wuxi' AND document_number LIKE '%〔%' AND document_number LIKE '%〕%号'
)
SELECT series, yr, count(DISTINCT ser) k, max(ser) m,
       round(max(ser)*(1.0+1.0/count(DISTINCT ser))-1,0)                              AS n_max,
       round(2.0*avg(DISTINCT ser)-1,0)                                               AS n_mean,
       round(100.0*count(DISTINCT ser)/(max(ser)*(1.0+1.0/count(DISTINCT ser))-1),1) AS incl_pct
FROM p WHERE series IN ('锡政发','锡政办发','锡政规','锡政办规')
GROUP BY series, yr ORDER BY series, yr;
```

The cited-serial pull. In `documents.db` the trigram index needs three characters, so 锡政 alone matches
nothing; query each prefix:

```sql
SELECT d.id, d.site_key, d.document_number, d.title || ' ' || coalesce(d.body_text_cn,'')
FROM doc_search s JOIN documents d ON d.id = s.rowid
WHERE doc_search MATCH '锡政发';   -- repeat for 锡政办, 锡政规, 锡政呈, 锡政函, 锡政复, 锡政字
```

and in `documents_wuxi.db` scan every row. Each text is NFKC-normalized and matched with

```
(锡政办发|锡政发|锡政办规|锡政规|锡政呈|锡政办函|锡政复|锡政字|锡政办通)\s*[〔\[（(【]\s*(\d{4})\s*[〕\]）)】]\s*第?\s*(\d+)\s*号
```

dropping a match equal to the row's own `document_number`. Rows are deduplicated on `(site_key, url)`
across the two files. Result: 1,563 citations, 132 from `js`.

The register-split test (who numbers the city's 请示):

```
请示》?\s*[（(]\s*(锡[一-鿿]{0,5})\s*[〔...〕]\s*第?\s*(\d+)\s*号
```

over `doc_search MATCH '无锡市人民政府' OR '锡政发' OR '锡政字' OR '锡政请'`, restricted to sites outside the
Wuxi family. Every hit 2002-2017 is 锡政发 and every hit 2018-2026 is 锡政呈. The Shenzhen control runs the
same pattern with `深` and finds 请示 numbered 深府 in 2007, 2010, 2016 and 2018 and no 深府呈 / 深府请.

Trends are ordinary least squares of `ln(N̂)` on year over complete years, reported as `exp(b) − 1`. The
order statistic is `(m/N)**k` on pooled `k` and `m`.

---

*All figures measured 2026-10-08 10:00-10:30 UTC against `documents.db` and `documents_wuxi.db` on the
droplet, read-only, while the nightly classifier held the lock. Every figure is from 文号 strings and
dates, which the classifier does not write, so none will move when the second merge lands except the
departmental rows in §1.1, which the merge copies rather than changes. Shenzhen figures are from
`wenhao-denominator.md` and were not re-queried.*
