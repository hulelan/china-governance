# The 文号 serial as a denominator: thirty years of Shenzhen's numbered issuance (2026-10-07)

*A 文号 serial number counts the issuing body's own documents, not ours. 深府〔1996〕362号 says the
Shenzhen municipal government numbered at least 362 documents in that series in 1996, whether or not we
hold them. So the maximum serial observed per series per year estimates total issuance independently of
our coverage. This memo builds that estimator for every 文号 series in the Shenzhen gazette, tests it two
ways, and reports what survives. The headline result: the municipal government's numbered 文件 output fell
by roughly a factor of three between 1996 and the 2020s, the General Office's numbered 文件 output
collapsed by more, and the letter (函) series did **not** rise to absorb them. The 函 story in
`sz-gazette-scoping.md` does not hold.*

Every other result in this volume is coverage-limited. It is computed on documents we happen to have
crawled, so it measures our crawl as much as the state. This one is not. That is its reason for existing.

**Scope.** `site_key='sz_gazette'`, 11,450 documents, 1987 to 2026-09-30, read-only against the live
droplet DB (`file:documents.db?mode=ro`, `nice -n 19`). All figures in this memo are from
`document_number`, `date_published`, `classify_genre_name` and `doc_identity.genre`, which are stable
fields. The two body-length tables are timestamped: a body backfill was writing throughout, at
**9,550 of 11,450 bodies at 22:53 UTC on 2026-10-07**. Labels: *measured* = a query in the appendix,
*inferred* = my reading of a measured pattern.

---

## 1. What a 文号 is, and when its serial is a denominator

A Chinese administrative document number has three parts: an issuer-and-type prefix, a year in 〔〕, and a
serial. 深府办函〔2015〕152号 is the 152nd document in the Shenzhen General Office's letter series for 2015.
The serial is assigned by the issuing office at the moment of issuance. It is sequential, it starts at 1,
and it resets each January.

That makes the serial a register readout. If we hold one document numbered 152, the office issued at least
152. Our crawl coverage affects which serials we see. It does not affect what the serials mean.

The estimator is the German tank problem. Given `k` distinct serials drawn from an unknown range 1..N with
observed maximum `m`:

    N̂_max  =  m · (1 + 1/k) − 1

This is the minimum-variance unbiased estimator **if** the observed serials are a uniform random subset of
1..N. Section 3 tests that assumption rather than asserting it.

### 1.1 Which series qualify (measured)

9,750 of 11,450 gazette documents carry a `document_number` (85.2%). Of those, **8,722 parse as
(prefix, year, serial)**. The remaining 1,028 are not year-serial 文号 at all and are excluded:

| shape | rows | why it is not a denominator |
|---|---:|---|
| 第N号 / 第九号 / 第一一七号 | 554 | 人大常委会 and 政府 announcements. Numbered continuously within a 届 (five-year term), not within a year. Chinese numerals, often no year anywhere in the field. |
| 市政府令第N号 | 364 | Mayor's orders. One continuous series since 1992 (observed range 118 to 331), not annual. Its slope measures cumulative output, not annual output, and is covered by title counts in `sz-gazette-scoping.md` §3.3 instead. |
| other (公告2019年第1号 and similar) | 109 | Per-office announcement counters, inconsistent form. |
| 总第N期 | 1 | **An issue number, not a document serial.** 总第178号 is the gazette's 178th issue. The gazette's own issue numbers live in `keywords` (1,342 distinct, 总第68期 to 总第1300期-ish) and must never be mixed into this analysis. One row leaked into `document_number`. |

Among the 8,722 parsed rows there are **481 distinct normalized series**. I checked every series with 15 or
more held documents for annual reset: in each one, the minimum serial of a later year falls below the
maximum of an earlier year, so none of them uses continuous cross-year numbering. *Measured.* No usable
series was excluded on that ground.

One bad row: `深府[1905]139号`, dated 1995-07-31, a typo for 1995. Reassigned to its `date_published` year.

---

## 2. The series inventory

81 series hold 15 or more documents and together cover 7,417 of the 8,722 parsed rows (85%). Full table.
`maxser` is the highest serial ever observed in that series. `medIncl%` is the median across years of
held ÷ N̂_max, that is, the share of the series the gazette actually printed.

| series | held | yrs | span | maxser | medIncl% | class |
|---|---:|---:|---|---:|---:|---|
| 深府 | 1287 | 32 | 1995-2026 | 362 | 20.9 | trendable |
| 深府办 | 1237 | 32 | 1995-2026 | 238 | 44.8 | trendable |
| 深地税发 | 334 | 16 | 1995-2012 | 955 | 3.3 | trendable |
| 深法制 | 303 | 17 | 2001-2018 | 349 | 3.0 | trendable |
| 深市监标 | 261 | 6 | 2013-2018 | 67 | 98.6 | thin |
| 深人社规 | 245 | 18 | 2009-2026 | 27 | 96.2 | floor |
| 深建规 | 205 | 20 | 2007-2026 | 18 | 92.9 | floor |
| 深办 | 199 | 21 | 1995-2015 | 85 | 22.8 | trendable |
| 深发 | 189 | 21 | 1995-2015 | 41 | 47.2 | trendable |
| 深府办函 | 165 | 17 | 2001-2024 | 371 | 6.9 | trendable |
| 深办发 | 143 | 20 | 1995-2015 | 58 | 34.3 | trendable |
| 深交规 | 126 | 19 | 2007-2026 | 13 | 100.0 | floor |
| 深市监规 | 114 | 13 | 2010-2026 | 22 | 100.0 | floor |
| 深人发 | 113 | 15 | 1992-2006 | 101 | 11.1 | trendable |
| 深财规 | 109 | 15 | 2010-2026 | 21 | 90.1 | floor |
| 深府规 | 93 | 10 | 2017-2026 | 30 | 96.6 | trendable |
| 深前海规 | 93 | 10 | 2017-2026 | 24 | 95.7 | floor |
| 深工信规 | 84 | 8 | 2019-2026 | 15 | 100.0 | floor |
| 深府函 | 81 | 16 | 2005-2026 | 473 | 1.7 | trendable |
| 深发改规 | 72 | 14 | 2008-2026 | 14 | 100.0 | floor |
| 深环 | 70 | 12 | 1998-2022 | 473 | 1.2 | thin |
| 深府办规 | 69 | 10 | 2017-2026 | 12 | 100.0 | floor |
| 深建字 | 66 | 19 | 1993-2014 | 346 | 2.3 | trendable |
| 深委 | 61 | 19 | 1995-2014 | 63 | 7.4 | trendable |
| 深规土 | 60 | 16 | 1994-2018 | 875 | 0.5 | trendable |
| 深劳社规 | 59 | 3 | 2007-2009 | 28 | 100.0 | floor |
| 深劳 | 59 | 10 | 1995-2004 | 228 | 5.1 | thin |
| 深市监标字 | 57 | 4 | 2009-2012 | 116 | 20.1 | thin |
| 深科技创新规 | 52 | 9 | 2012-2023 | 16 | 100.0 | floor |
| 深质监 | 52 | 7 | 2003-2009 | 257 | 4.0 | thin |
| 深教规 | 52 | 17 | 2007-2025 | 8 | 100.0 | floor |
| 深规划资源规 | 52 | 8 | 2019-2026 | 12 | 100.0 | floor |
| 深医保规 | 47 | 8 | 2019-2026 | 11 | 100.0 | floor |
| 深劳社 | 45 | 4 | 2004-2007 | 197 | 6.8 | thin |
| 深民规 | 45 | 15 | 2011-2026 | 7 | 100.0 | floor |
| 深司 | 45 | 9 | 1997-2019 | 287 | 1.5 | thin |
| 深商务规 | 44 | 8 | 2019-2026 | 11 | 100.0 | floor |
| 深环规 | 43 | 10 | 2008-2026 | 9 | 100.0 | floor |
| 深市质规 | 42 | 5 | 2014-2018 | 18 | 100.0 | floor |
| 深文规 | 40 | 7 | 2008-2026 | 12 | 100.0 | floor |
| 深统信通 | 39 | 6 | 1996-2001 | 113 | 4.7 | thin |
| 深市质 | 37 | 3 | 2015-2019 | 704 | 5.5 | thin |
| 深文体旅 | 36 | 9 | 2009-2017 | 789 | 1.3 | thin |
| 深地税告 | 36 | 10 | 2000-2013 | 23 | 47.1 | floor |
| 深卫健规 | 36 | 7 | 2019-2025 | 8 | 100.0 | floor |
| 深应急规 | 33 | 9 | 2016-2026 | 6 | 100.0 | floor |
| 深交 | 30 | 11 | 2001-2016 | 1035 | 0.8 | thin |
| 深卫人规 | 29 | 4 | 2010-2013 | 12 | 100.0 | floor |
| 深统规 | 29 | 16 | 2007-2023 | 5 | 100.0 | floor |
| 深工商 | 28 | 11 | 1995-2006 | 231 | 4.3 | thin |
| 深卫计规 | 27 | 5 | 2014-2018 | 8 | 100.0 | floor |
| 深经贸信息规 | 26 | 4 | 2016-2019 | 16 | 90.0 | floor |
| 深社保发 | 26 | 7 | 1997-2003 | 92 | 6.0 | thin |
| 深运 | 26 | 5 | 1996-2000 | 410 | 1.3 | thin |
| 深人环规 | 24 | 8 | 2010-2018 | 5 | 100.0 | floor |
| 深公交规 | 22 | 9 | 2008-2024 | 7 | 91.9 | floor |
| 深文体旅规 | 21 | 3 | 2010-2018 | 10 | 93.8 | floor |
| 深计生 | 21 | 8 | 1997-2005 | 73 | 3.3 | thin |
| 深质技监 | 21 | 4 | 1999-2002 | 181 | 3.2 | thin |
| 深公规 | 20 | 10 | 2011-2025 | 8 | 66.8 | floor |
| 深文 | 20 | 12 | 1998-2025 | 346 | 1.0 | thin |
| 深城管规 | 20 | 9 | 2008-2026 | 4 | 100.0 | floor |
| 深城管 | 19 | 11 | 1998-2014 | 327 | 0.0 | thin |
| 深建燃 | 19 | 8 | 1997-2014 | 37 | 10.6 | thin |
| 深人环 | 18 | 7 | 2009-2016 | 507 | 0.8 | thin |
| 深水规 | 18 | 8 | 2017-2026 | 4 | 100.0 | floor |
| 深教 | 17 | 10 | 2001-2015 | 559 | 0.9 | thin |
| 深发改 | 17 | 10 | 2005-2018 | 2105 | 0.3 | thin |
| 深科 | 17 | 7 | 1993-2002 | 145 | 3.6 | thin |
| 深技监 | 17 | 4 | 1996-1999 | 142 | 2.7 | thin |
| 深国房 | 16 | 4 | 2005-2008 | 775 | 0.5 | thin |
| 深卫规 | 16 | 3 | 2007-2009 | 7 | 100.0 | floor |
| 深规土规 | 16 | 3 | 2016-2018 | 15 | 78.7 | floor |
| 深司规 | 16 | 11 | 2010-2025 | 3 | 100.0 | floor |
| 深组通 | 16 | 3 | 2001-2003 | 48 | 16.0 | thin |
| 深府外 | 15 | 9 | 1997-2015 | 248 | 6.1 | thin |
| 深公积金规 | 15 | 7 | 2017-2026 | 3 | 100.0 | floor |
| 深税联发 | 15 | 1 | 1994-1994 | 128 | 7.9 | thin |
| 深前海 | 15 | 5 | 2013-2017 | 243 | 1.7 | thin |
| 深人规 | 15 | 3 | 2007-2009 | 7 | 100.0 | floor |

Three classes, assigned by rule:

- **trendable** (16 series): eight or more years with three or more held documents. Only these can carry a
  time series.
- **thin** (31 series): large maximum serial but almost nothing held (inclusion under 6%). The serial is a
  valid **floor** on that year's output, so each row still says "at least this many". The series cannot be
  trended. 深发改 is the extreme case: 17 documents held against a maximum serial of 2,105, so the
  Development and Reform Commission numbered at least 2,105 documents in one year and we hold 0.3% of them.
- **floor** (34 series): small maximum serial (under 30) and near-total inclusion. These are the
  **规范性文件 registers**, created between 2007 and 2019. 深建规, 深人社规, 深市监规, 深府规, 深府办规 and
  29 more.

### 1.2 The 规 registers are a census, not a sample (measured)

The most useful incidental finding. The 规 series have median inclusion of 90 to 100%. The gazette prints
substantially **every** document in those registers. So for departmental 规范性文件, specifically, the
corpus is not sampling Shenzhen, it is holding Shenzhen whole, and no estimator is needed.

The registers are also small. 深建规 never exceeds 18 in a year, 深人社规 27, 深交规 13, 深财规 21,
深府规 30, 深府办规 12. *Inferred:* a Shenzhen bureau issues single to low-double digits of formally
registered normative documents per year. Volume in the 部门文件 gazette section is therefore not mostly
规范性文件, and a "departmental rulemaking is rising" reading cannot rest on section counts.

---

## 3. Defending the estimator

N̂_max uses only the maximum, so it discards the rest of the sample and it is downward-biased whenever the
year's highest-numbered documents are systematically absent. Inclusion in the 深府 series falls from
18 to 34% before 2017 to 5 to 13% after, so the bias question is not academic.

### 3.1 A second estimator from the whole sample

Under the same uniform-subset assumption, the sample mean carries the information too:

    N̂_mean  =  2 · mean(serials) − 1

This is the method-of-moments estimator. It is also unbiased under uniformity, it has higher variance than
N̂_max, and critically it responds to the **shape** of the sample rather than its upper tip. If the gazette
preferentially printed early-in-the-year documents, the serials would skew low, N̂_mean would exceed N̂_max,
and N̂_max would be reading low. The comparison is a bias test, not a precision gain.

Ratio N̂_mean / N̂_max across all 494 series-years with four or more held documents, grouped by inclusion
(*measured*):

| inclusion band | series-years | median ratio | mean ratio | IQR of ratio |
|---|---:|---:|---:|---|
| ≥ 50% | 247 | 1.000 | 1.006 | 1.00 – 1.00 |
| 20 – 50% | 79 | 1.010 | 1.001 | 0.93 – 1.09 |
| 10 – 20% | 36 | 1.071 | 1.089 | 0.91 – 1.21 |
| < 10% | 132 | 1.043 | 1.043 | 0.91 – 1.21 |

The two estimators agree at the centre in every band. Median ratio never leaves 1.00 to 1.07. What changes
as inclusion falls is the **spread**: the interquartile range widens from 1.00-1.00 to 0.91-1.21.

*Inferred:* the gazette's selection is close to serial-blind. Its error on these estimates is variance, not
bias, and that variance is roughly ±10 to 20% once inclusion drops below 20%. For 深府 specifically the
era-wise ratios are 0.94 (1995-2009), 1.04 (2010-2016), 0.97 (2017-2026), so no era is systematically
mis-read relative to another. That is what the trend in §4 needs.

### 3.2 A third, structurally independent estimator

Serials are assigned chronologically, so serial should be roughly linear in day-of-year. For each
series-year with six or more held documents I fit `serial = a + b · day_of_year` by least squares and
predicted at day 365:

    N̂_date  =  a + 365·b

This does not use the maximum at all and does not assume uniform sampling in serial space. Across 289
qualifying series-years its median ratio to N̂_max is **0.912**. *Inferred:* issuance is not uniform in
time. Shenzhen bunches documents into late December (visible in the raw rows: eleven 深府〔1995〕 documents
dated 1995-12-31, serials 295 to 314), so a straight line undershoots the year-end burst. N̂_date is
therefore a **lower bound** and the direction of its error is known. It is reported alongside, not averaged
in.

### 3.3 A direct test where the sample is too small for either estimator

When `k` is 1 or 2, both estimators are noise. For those cases use the order statistic directly. If the
true annual size were N and the gazette's draws were serial-blind, then P(all k observed serials ≤ m) =
(m/N)^k. For 深府办 pooled over 2019-2026, k = 17 and the highest serial ever seen is 17 (*measured*):

| hypothesised true size | P(all 17 serials ≤ 17) |
|---|---:|
| 30 / yr | 6.4 × 10⁻⁵ |
| 50 / yr | 1.1 × 10⁻⁸ |
| 100 / yr | 8.3 × 10⁻¹⁴ |
| 150 / yr | 8.4 × 10⁻¹⁷ |

The same test on 深府 pooled over 2017-2026 (k = 69, max 91) does not reject 100/yr (p = 1.5 × 10⁻³,
marginal) and decisively rejects 150/yr (p = 1.1 × 10⁻¹⁵). So the recent 深府 level is near 90 to 110/yr
and is certainly not the 1990s level.

### 3.4 An external check that does not use the gazette at all

The other Shenzhen sites (`sz`, `szdp`, `szlg`, `szlh`, `szlhq`, `szgm`, `szns`, `sz_invest`) hold 979
parsable 深-prefixed 文号, including documents the gazette never printed. If the gazette's maxima were
badly truncated, these should routinely exceed them. They raise the maximum in **4 of 51 series-years**
(*measured*):

| series | year | gazette max | union max |
|---|---:|---:|---:|
| 深府 | 2022 | 77 | 93 |
| 深府办 | 2020 | 2 | 5 |
| 深府办 | 2021 | 4 | 6 |
| 深府办 | 2024 | 9 | 11 |

深府函 and 深府办函 are never raised in 24 shared series-years. The 深府办 corrections matter and are
included below, and they do not change its order of magnitude: a series the gazette shows at 2 to 9 is at
5 to 11 on a wider sample, not at 100.

---

## 4. Results

### 4.1 深府, the municipal government's own numbered 文件

`k` = documents held, `m` = maximum serial observed, inclusion = k / N̂_max.

| year | k | m | N̂_max | N̂_mean | N̂_date | incl % |
|---|---:|---:|---:|---:|---:|---:|
| 1995 | 57 | 316 | 321 | 406 | 301 | 17.8 |
| 1996 | 82 | 362 | **365** | 371 | 341 | 22.4 |
| 1997 | 78 | 310 | 313 | 309 | 298 | 24.9 |
| 1998 | 66 | 273 | 276 | 259 | 252 | 23.9 |
| 1999 | 52 | 220 | 223 | 216 | 207 | 23.3 |
| 2000 | 38 | 165 | 168 | 167 | 158 | 22.6 |
| 2001 | 51 | 186 | 189 | 158 | 186 | 27.0 |
| 2002 | 62 | 206 | 208 | 191 | 208 | 29.8 |
| 2003 | 76 | 231 | 233 | 228 | 227 | 32.6 |
| 2004 | 79 | 321 | 324 | 208 | 208 | 24.4 |
| 2005 | 63 | 220 | 222 | 202 | 171 | 28.3 |
| 2006 | 91 | 269 | 271 | 279 | 165 | 33.6 |
| 2007 | 62 | 271 | 274 | 243 | 213 | 22.6 |
| 2008 | 65 | 286 | 289 | 269 | 252 | 22.5 |
| 2009 | 56 | 240 | 243 | 219 | 181 | 23.0 |
| 2010 | 41 | 194 | 198 | 216 | 146 | 20.7 |
| 2011 | 43 | 210 | 214 | 211 | 145 | 20.1 |
| 2012 | 26 | 145 | 150 | 160 | 118 | 17.4 |
| 2013 | 28 | 122 | 125 | 145 | 79 | 22.3 |
| 2014 | 24 | 111 | 115 | 119 | 78 | 20.9 |
| 2015 | 25 | 117 | 121 | 115 | 74 | 20.7 |
| 2016 | 22 | 104 | 108 | 109 | 77 | 20.4 |
| 2017 | 8 | 83 | 92 | 90 | 129 | 8.7 |
| 2018 | 12 | 84 | 90 | 77 | 98 | 13.3 |
| 2019 | 4 | 52 | 64 | 74 | . | 6.2 |
| 2020 | 9 | 89 | 98 | 69 | 57 | 9.2 |
| 2021 | 9 | 76 | 83 | 95 | 49 | 10.8 |
| 2022 | 11 | 77 | 83 (93 union) | 72 | 87 | 13.3 |
| 2023 | 6 | 91 | 105 | 94 | 107 | 5.7 |
| 2024 | 5 | 88 | 105 | 113 | . | 4.8 |
| 2025 | 3 | 40 | 52 | 53 | . | 5.7 |
| 2026 (to 09-30) | 2 | 49 | 72 | 78 | . | 2.8 |

Log-linear trend on N̂_max across the 31 complete years: **−5.1% per year**, identical on N̂_mean
(−5.1%). Level: 276 to 365 in 1995-1998, 168 to 324 through 2011, 52 to 105 from 2017. *Measured.*
2026 is a partial year and is excluded from every trend.

### 4.2 深府办, the General Office's numbered 文件

| year | k | m | N̂_max | N̂_mean | N̂_date | incl % |
|---|---:|---:|---:|---:|---:|---:|
| 1995 | 23 | 83 | 86 | 97 | 82 | 26.9 |
| 1996 | 43 | 113 | 115 | 113 | 95 | 37.5 |
| 1997 | 48 | 134 | 136 | 140 | 139 | 35.3 |
| 1998 | 45 | 136 | 138 | 142 | 138 | 32.6 |
| 1999 | 34 | 132 | 135 | 140 | 122 | 25.2 |
| 2000 | 39 | 106 | 108 | 102 | 111 | 36.2 |
| 2001 | 43 | 110 | 112 | 121 | 106 | 38.5 |
| 2002 | 76 | 126 | 127 | 128 | 117 | 60.0 |
| 2003 | 67 | 138 | 139 | 130 | 143 | 48.2 |
| 2004 | 107 | 231 | 232 | 245 | 232 | 46.1 |
| 2005 | 87 | 179 | 180 | 182 | 134 | 48.3 |
| 2006 | 134 | 238 | **239** | 251 | 154 | 56.1 |
| 2007 | 107 | 185 | 186 | 192 | 166 | 57.6 |
| 2008 | 69 | 132 | 133 | 127 | 110 | 51.9 |
| 2009 | 52 | 134 | 136 | 126 | 133 | 38.4 |
| 2010 | 67 | 111 | 112 | 111 | 72 | 60.0 |
| 2011 | 51 | 113 | 114 | 123 | 88 | 44.7 |
| 2012 | 27 | 59 | 60 | 54 | 54 | 44.9 |
| 2013 | 22 | 32 | 32 | 33 | 26 | 67.8 |
| 2014 | 11 | 16 | 16 | 17 | . | 66.9 |
| 2015 | 22 | 38 | 39 | 42 | 26 | 56.8 |
| 2016 | 23 | 38 | 39 | 44 | 28 | 59.5 |
| 2017 | 7 | 22 | 24 | 21 | 11 | 29.0 |
| 2018 | 6 | 14 | 15 | 16 | 20 | 39.1 |
| 2019 | 2 | 6 | 8 | 7 | . | 25.0 |
| 2020 | 1 | 2 | 3 (5 union) | 3 | . | 33.3 |
| 2021 | 2 | 4 | 5 (6 union) | 4 | . | 40.0 |
| 2022 | 4 | 17 | 20 | 18 | . | 19.8 |
| 2023 | 4 | 9 | 10 | 12 | . | 39.0 |
| 2024 | 2 | 9 | 12 (11 union) | 14 | . | 16.0 |
| 2025 | 1 | 8 | 15 | 15 | . | 6.7 |
| 2026 (to 09-30) | 1 | 5 | 9 | 9 | . | 11.1 |

Log-linear trend: **−8.4% per year** over 1995-2026 on N̂_max, −8.5% on N̂_mean, and **−14.3% per year**
on 2010-2026 alone. This series has unusually high inclusion (median 44.8%, peaking at 68%), so the
mid-series numbers are the most reliable in this memo. The collapse after 2013 is not an inclusion
artefact: inclusion is *higher* in 2013-2016 (57 to 68%) than in 1999-2001 (25 to 39%), and the estimate
still falls from 135 to 39.

### 4.3 深府函 and 深府办函, the letter series

This is where the scoping study's reading breaks.

| year | 深府函 k | 深府函 N̂_max | 深府函 N̂_mean | 深府办函 k | 深府办函 N̂_max | 深府办函 N̂_mean |
|---|---:|---:|---:|---:|---:|---:|
| 2001 | | | | 1 | 285 | 285 |
| 2002 | | | | 1 | 243 | 243 |
| 2005 | 1 | 253 | 253 | | | |
| 2009 | | | | 1 | 253 | 253 |
| 2010 | 1 | 83 | 83 | | | |
| 2011 | | | | 2 | 254 | 281 |
| 2012 | 6 | 288 | 385 | 22 | 183 | 213 |
| 2013 | 5 | 259 | 352 | 17 | 157 | 168 |
| 2014 | 3 | 270 | 246 | 18 | 184 | 135 |
| 2015 | 5 | 366 | 299 | 13 | 163 | 158 |
| 2016 | 8 | 346 | 346 | 19 | 267 | 319 |
| 2017 | 4 | 108 | 146 | 13 | 262 | 253 |
| 2018 | 4 | 590 | 708 | 10 | 407 | 294 |
| 2019 | 6 | 463 | 457 | 13 | 308 | 363 |
| 2020 | 3 | 192 | 163 | 8 | 152 | 70 |
| 2021 | 9 | 322 | 402 | 7 | 104 | 114 |
| 2022 | 4 | 116 | 71 | 13 | 143 | 163 |
| 2023 | 4 | 304 | 200 | 5 | 103 | 93 |
| 2024 | 4 | 500 | 458 | 1 | 113 | 113 |
| 2026 (part) | 14 | 280 | 116 | | | |

Log-linear trend over the usable years:

| series | N̂_max trend | N̂_mean trend |
|---|---:|---:|
| 深府函 | **+0.2% / yr** | **−5.2% / yr** |
| 深府办函 | **−3.6% / yr** | **−4.8% / yr** |

**There is no measurable rise in either letter series.** *Measured.* The two estimators straddle zero for
深府函 and both run negative for 深府办函, and in both series inclusion is 1 to 7%, so `k` is 1 to 14 per
year and the year-to-year scatter (116 to 590) is sampling noise, not movement.

The scoping study's "深府函 rises 127 → 473" compared the year 2005, where **k = 1** and 127 is a single
document's serial, against 2018, where k = 4 and 473 happens to be a high draw. That is a comparison of
two draw sizes, not two years of issuance. I made the claim and it does not survive its own estimator.

Two facts about the letter series do survive, and they point the other way:

1. **深府办函〔2001〕143号 exists** (2001-12-17, 深圳市人民政府办公厅关于建立深圳市减轻企业负担联席会议制度的通知).
   So the General Office numbered at least 143 letters in 2001, in a year when its 文件 series reached only
   110. The letter channel was already the larger of the two at the start of the observable window.
   深府办函〔2002〕122号 and 深府办函〔2009〕127号 say the same for those years. *Measured.*
2. The gazette's **first observed 深府函 is 2005** and 深府办函 **2001**, but at 1 to 7% inclusion the
   series' true start year is unobservable. Absence of 1990s 函 rows is evidence about the gazette's
   editorial rule, not about whether the series existed. *Measured limit.*

### 4.4 What the four series look like together

N̂_max per channel, with the 规范性文件 registers added once they appear. `k` in parentheses.

| yr | 深府 | 深府规 | 深府函 | gov Σ | 深府办 | 深府办规 | 深府办函 | office Σ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1996 | 365 (82) | . | . | 365 | 115 (43) | . | . | 115 |
| 2001 | 189 (51) | . | . | 189 | 112 (43) | . | 285 (1) | 397 |
| 2006 | 271 (91) | . | . | 271 | 239 (134) | . | . | 239 |
| 2011 | 214 (43) | . | . | 214 | 114 (51) | . | 254 (2) | 368 |
| 2016 | 108 (22) | . | 346 (8) | 453 | 39 (23) | . | 267 (19) | 306 |
| 2021 | 83 (9) | 6 (6) | 322 (9) | 412 | 5 (2) | 3 (3) | 104 (7) | 112 |
| 2024 | 105 (5) | 8 (8) | 500 (4) | 613 | 12 (2) | 3 (3) | 113 (1) | 128 |

The column sums should be read with care, because the 函 components rest on `k` of 1 to 19 and the registers
begin only in 2017. What the table does show cleanly is a **composition** change inside each channel: the
文件 component shrinks from 100% of the government channel to roughly 20%, and from 100% of the office
channel to under 10%, while the 函 component stays in the low hundreds throughout.

### 4.5 Did the 2017 规范性文件 renumbering cause the decline? No (measured)

深府规 and 深府办规 both begin in 2017, exactly where 深府 and 深府办 step down again. A new series carved
out of an old one would produce a fake decline. It did not here. 深府规 runs 5 to 30 per year and
深府办规 runs 1 to 12. 深府 fell by roughly 110 per year between 2011 and 2017 and 深府办 by roughly 90.
The registers are an order of magnitude too small to absorb that. *Measured.*

---

## 5. The 2009 seam

`sz-gazette-scoping.md` §4.2 flags an administrative seam in 2008-09: 特区法规 ends, roughly 40 per-bureau
gazette sections collapse into one 部门文件 bucket, and 1996 arrives as a single collapsed issue column.
The §3.3 section-mix series in that memo crosses that seam, so part of its slope could be an editorial
reclassification.

The 文号 denominators do not share that problem, because a 文号 series is assigned by the issuing office and
is indifferent to how the gazette files it. The seam still matters for a different reason: if the decline
sat *at* 2009, it would be suspicious. It does not.

| series | 1995-2026 trend | **2010-2026 trend** | level before 2009 | level 2010-2016 | level 2017-2026 |
|---|---:|---:|---:|---:|---:|
| 深府 | −5.1% / yr | **−5.9% / yr** | 168 – 365 | 108 – 214 | 52 – 105 |
| 深府办 | −8.4% / yr | **−14.3% / yr** | 86 – 239 | 16 – 114 | 3 – 24 |
| 深府函 | +0.2% / yr | +0.2% / yr | (k ≤ 1) | 83 – 366 | 108 – 590 |
| 深府办函 | −3.6% / yr | −3.6% / yr | (k ≤ 1) | 60 – 267 | 103 – 407 |

**What survives the 2009 cut:** both declines, at a steeper rate than over the full span. Restricted to
2010-2026, a single administrative regime with one 部门文件 bucket and no 特区法规 section, 深府 falls
−5.9%/yr and 深府办 falls −14.3%/yr. Both estimators agree to within 0.7 points. The letter series' flatness
also survives, trivially, since they are only observable after 2010 anyway.

The decline is also not concentrated at any one year. 深府 steps down at 1999-2000 (223 → 168), recovers
through 2008, then falls again at 2012 (214 → 150) and again at 2017 (108 → 92). 深府办 is flat to rising
until 2006 then falls monotonically. *Inferred:* these are two separate episodes, one around 2012 and one
around 2017, not one break.

---

## 6. Reading

### 6.1 What is established

1. **Shenzhen's municipal government issues roughly a third as many numbered 文件 as it did in the late
   1990s.** 深府 N̂ falls from 276-365 (1995-1998) to 83-105 (2017-2024). Two estimators agree, a third runs
   9% low by construction, the order statistic rejects 150/yr for the recent period, and documents from
   other Shenzhen sites raise the maximum in 1 of 10 shared years and only by 16. *Measured.*
2. **The General Office's numbered 文件 series has nearly stopped.** 深府办 N̂ falls from 86-239 to 3-24.
   Its inclusion is the highest in the corpus (median 45%), so this is the best-sampled series here, and
   the order statistic puts the probability of a surviving 100/yr series at 8 × 10⁻¹⁴. *Measured.*
3. **The letter series did not rise.** Flat to slightly negative on both estimators, and 深府办函 was
   already at ≥143 in 2001 against a 文件 series at ~110. *Measured.*
4. **Departmental 规范性文件 output is small and fully observed.** The 规 registers are near-census and
   never exceed 30 per department per year. *Measured.*

### 6.2 What that is, and what it is not

The three movements together describe a **change in instrument form inside one municipal government**: the
numbered 文件 channel shrank while the 函 channel held roughly level, so by the 2020s a document leaving
深圳市政府办公厅 with a number on it is far more likely to be a 函 than a 文件.

That is not deregulation, and it is not decentralization. Three reasons to resist both readings:

- **函 here are not thin correspondence.** Among the gazette's printed letters, `doc_identity.genre` is
  promulgation on 51 of 81 深府函 and 88 of 165 深府办函, and the title verbs are the same as the 文件
  series: 118 of 165 深府办函 titles contain 印发, against 423 of 1,237 深府办. Body length, measured on
  the 9,550-of-11,450 bodies present at **22:53 UTC on 2026-10-07**, for 2012-2019 where coverage is
  complete: 深府 median 3,636 characters, 深府办 3,317, 深府函 3,809, 深府办函 3,790. The letters are the
  longest of the four. *Measured.* So the instruments did not get thinner when the form changed.
- **But that genre test is run on a 1 to 7% sample, selected by an editor.** The gazette prints a letter
  only when the letter is worth printing, which selects for exactly the rule-carrying 函 that look like
  文件. I can state that the printed 函 do instrument work. I cannot state that the series as a whole does.
  This is the one place in the memo where the denominator does not rescue me, and it is a real limit.
- **Total output is not measured.** Each series is measured. The sum of series is not, because 函 estimates
  rest on k of 1 to 19 and because series come and go (深办, 深发, 深办发 all end in 2015). "Shenzhen issues
  less" is not supported. "Shenzhen's 深府 and 深府办 series carry less" is.

*Inferred mechanism.* The plausible reading is a narrowing of what gets a formal 文件 number. The
规范性文件 registration regime arrives in stages (深建规 2007, 深财规 and 深市监规 2010, 深府规 and
深府办规 2017) and creates a small, audited, numbered class of documents that *are* rules. Everything that
is not a rule has correspondingly less reason to carry a 文件 number and can travel as a 函. On that
reading the shrinking 深府办 series is a consequence of the rule class being defined, not of the government
doing less. The evidence for this is the timing and the census property of the registers. It is
circumstantial and this memo does not test it.

### 6.3 Limits

1. **n = 1 at the jurisdiction level, and it is the least ordinary jurisdiction.** Shenzhen is a special
   economic zone with 特区法规 powers no ordinary prefecture has. Nothing here generalizes to "a Chinese
   municipality", and no second city in this corpus has the pre-2010 depth to check it. The method
   generalizes; the result does not.
2. **The estimator needs serial-blind selection and I have only tested it, not proven it.** §3.1 shows the
   two estimators agree at the centre in every inclusion band, which rules out a *monotone* serial bias.
   It would not catch a selection rule correlated with something that happens to correlate with serial.
3. **The weakest numbers are the recent 深府 years and every 函 year.** k of 2 to 5 means ±20% at best. The
   per-year values in §4.1 after 2019 and all of §4.3 should be read as bands, not points.
4. **2026 is partial** (to 09-30) and excluded from all trends. Documents dated December are gazetted the
   following January, so complete years are complete, but 2026 is not.
5. **The pre-1995 rows are reprints.** 59 documents dated 1987-1994 sit in retrospective compilation issues
   printed in 2002-2003 (`sz-gazette-scoping.md` §2). They are in the series inventory, where they are
   legitimate serial observations, and excluded from nothing else because no trend starts before 1995.
6. **This measures numbered issuance, not governing.** A city can govern through unnumbered instruments,
   through 会议纪要, through the party committee, or through the districts. The 深委 series (61 held, median
   inclusion 7%, ends 2014) is in the inventory and far too thin to trend, and the district 文号 series
   (深龙府规, 深光府规, 深南府规 and so on, visible in the other-site pool) are a separate study.

---

## 7. SQL and reproduction appendix

Gazette universe and 文号 coverage:

```sql
SELECT count(*), sum(document_number!=''), sum(body_text_cn!='')
FROM documents WHERE site_key='sz_gazette';
-- 11450 | 9750 | 9550   (body at 22:53 UTC 2026-10-07, a backfill was writing)
```

The parse. SQLite can do it for the dominant 〔〕 form; the analysis used a Python regex
`^(.*?)[〔\[（(【]\s*(\d{4})\s*[〕\]）)】]\s*(?:第)?\s*(\d+)\s*号?\s*$` to catch the 1996-era ascii-bracket
variant too, then normalized `深圳市` to `深` in the prefix:

```sql
-- per series per year: held, max serial, German-tank estimate, inclusion
WITH p AS (
  SELECT replace(substr(document_number, 1, instr(document_number,'〔')-1),'深圳市','深') AS series,
         CAST(substr(document_number, instr(document_number,'〔')+1, 4) AS integer)      AS yr,
         CAST(replace(substr(document_number, instr(document_number,'〕')+1), '号','') AS integer) AS ser
  FROM documents
  WHERE site_key='sz_gazette' AND document_number LIKE '%〔%' AND document_number LIKE '%〕%号'
)
SELECT series, yr, count(DISTINCT ser) k, max(ser) m,
       round(max(ser)*(1.0+1.0/count(DISTINCT ser))-1, 0)                         AS n_max,
       round(2.0*avg(ser)-1, 0)                                                   AS n_mean,
       round(100.0*count(DISTINCT ser)/(max(ser)*(1.0+1.0/count(DISTINCT ser))-1), 1) AS incl_pct
FROM p WHERE yr BETWEEN 1990 AND 2026
GROUP BY series, yr ORDER BY series, yr;
```

Series inventory (first/last year, span, maximum serial ever, years held):

```sql
WITH p AS ( /* as above */ )
SELECT series, count(*) held, count(DISTINCT yr) yrs, min(yr), max(yr), max(ser) maxser
FROM p GROUP BY series HAVING held >= 15 ORDER BY held DESC;
```

The non-annual shapes that must be excluded:

```sql
SELECT CASE
         WHEN document_number LIKE '%令第%'  THEN 'mayor order (continuous)'
         WHEN document_number LIKE '总第%'
           OR document_number LIKE '%（总第%' THEN 'ISSUE number, not a doc serial'
         WHEN document_number LIKE '第%号' AND document_number NOT LIKE '%〔%'
                                            THEN 'announcement 第N号 (per-term)'
         ELSE 'other' END shape,
       count(*)
FROM documents
WHERE site_key='sz_gazette' AND document_number!=''
  AND NOT (document_number LIKE '%〔%' AND document_number LIKE '%〕%号')
GROUP BY 1 ORDER BY 2 DESC;
-- 554 announcement | 364 mayor order | 109 other | 1 issue number
```

The external check (other Shenzhen sites raise the maximum in 4 of 51 shared series-years):

```sql
SELECT site_key, date_published, document_number
FROM documents
WHERE site_key IN ('sz','szdp','szlg','szlh','szlhq','szgm','szns','sz_invest')
  AND document_number LIKE '%深%';
-- 984 rows, 979 parse; max-serial comparison done in Python
```

Genre and body length by series:

```sql
SELECT substr(d.document_number,1,instr(d.document_number,'〔')-1) series,
       i.genre, count(*), round(avg(length(d.body_text_cn))) mean_len
FROM documents d JOIN doc_identity i ON i.doc_id=d.id
WHERE d.site_key='sz_gazette'
  AND substr(d.document_number,1,instr(d.document_number,'〔')-1)
      IN ('深府','深府办','深府函','深府办函')
  AND d.body_text_cn!='' AND substr(d.date_published,1,4) BETWEEN '2012' AND '2019'
GROUP BY 1,2 ORDER BY 1, 3 DESC;
```

The order-statistic test is one line of arithmetic, `(m/N)**k`, on the pooled `k` and `m` from the first
query.

One difference between the SQL above and the numbers in §3 and §4: the analysis computed N̂_mean over the
**distinct** serials in a series-year, while `avg(ser)` in SQL averages over rows. They differ wherever a
series-year holds duplicate serials, which happens in 146 of 1,618 series-years (one 文号 covering two rows,
for example 深府〔2006〕268号 appearing twice). Across the 494 series-years used in §3.1 the median absolute
difference is **0** and the worst case in a thin series is 191; among the four main series the worst case is
深府 2008 (269 distinct, 244 by rows) and every other year differs by 3 or less. Use the distinct form, as
the Python did, when reproducing: `2.0*avg(DISTINCT ser)-1`.

---

*All figures measured 2026-10-07 22:47-22:54 UTC against the live droplet DB, read-only, while a body
backfill was writing. The two body-length figures carry their timestamp and are lower bounds; every other
figure is from stable metadata and will not move. This memo corrects `sz-gazette-scoping.md` §3.2: the
深府 decline and the 深府办 collapse are confirmed and are steeper than reported, and the 深府函 rise is
withdrawn.*
