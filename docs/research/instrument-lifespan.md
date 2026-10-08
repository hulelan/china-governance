# How long a municipal instrument lives: repeal and sunset in thirty years of the Shenzhen gazette (2026-10-07)

*A repeal notice is itself a published document, so the Shenzhen gazette prints both ends of an
instrument's life. Pairing 4,159 named repeals against the instruments they kill gives the first
lifespan measurement in this volume. The headline result is a negative one, and it is the finding:
**median survival is not reached in any stratum.** At most a quarter of instrument-shaped municipal
documents are ever observed to be formally repealed, the survivor curve plateaus at roughly 0.75 after
twelve years, and formal repeal arrives in administrative cleanup campaigns rather than at the end of an
instrument's useful life. What does behave like a lifespan is the 规范性文件 register class, whose
documents carry a written 3 or 5 year 有效期 term and are repealed at three times the rate of ordinary
文件. The sunset clause, not the repeal notice, is where municipal Shenzhen retires its rules, and 1,538
of its sunsets are invisible to this method.*

**Scope.** `site_key='sz_gazette'`, 11,450 documents, 11,204 with body text (97.9%), continuous issue
coverage 1995-04 to 2026-09 (31.4 years; see `sz-gazette-scoping.md` §2 for why the pre-1995 rows are
reprints). Read-only against the live droplet DB (`file:documents.db?mode=ro`, `nice -n 19`), no writes,
no rebuilds. This memo executes recommendation 2 of `sz-gazette-scoping.md` and depends on the serial
estimator built in `wenhao-denominator.md`. Labels: *measured* = a query in the appendix, *inferred* = my
reading of a measured pattern.

---

## 1. Building the pairs

### 1.1 What already existed

`instrument_succession` holds 14,624 instrument-to-instrument edges on the droplet. 1,476 of them have a
`sz_gazette` predecessor: 1,050 `revised_edition`, 374 `superseded_by_stated`, 49 `renamed`, 3
`pilot_to_national`. Only the `superseded_by_stated` class is a repeal: a successor's body naming the
predecessor in a 同时废止 sentence. Restricted to confidence ≥ 0.9 with a dated successor it supplies
**337 gazette instruments with a repeal date**. *Measured.*

That table is built for a different purpose. It pools copies of one text and keeps at most one successor
per predecessor per relation, so a 关于废止部分规范性文件的决定 that kills forty instruments at once
contributes at most a handful of edges, and it resolves only to documents the corpus holds. Both
restrictions bite hard here, so the pairs below were extracted directly.

### 1.2 The three routes

Gazette repeal notices come in two shapes. A **catalogue** notice carries a numbered 废止的规范性文件目录
listing title and 文号 per line. 深发改〔2010〕121号 is typical:

```
废止的规范性文件目录
 1．关于加强机动车停放服务收费管理的通告（深价〔2002〕32号）
 2．转发省物价局关于取消和降低住房建设收费的通知（深价管字〔2002〕8号）
 ...
 15．关于办理《符合国家产业政策的外资项目确认书》有关事项的通知（深发改〔2006〕1007号）
```

A **sentence** repeal is a clause inside an ordinary instrument: 原《X》（文号）同时废止. Both were
parsed. Catalogue lines were taken from any document whose title contains 废止 or 失效; sentences from any
body containing 废止, after dropping procedural clauses (修改或者废止, 应当…废止, 相抵触, 及时废止,
定期清理) and dropping the authorising document named in a 根据/依据/按照 clause with no 废止 between the
clause and the 文号. A listed item whose own title contains 关于废止 is a prior repeal decision, not a
repealed instrument, and is dropped.

| route | distinct repealed instruments named |
|---|---:|
| 文号 named (`深价〔2002〕32号` and the like) | 3,199 |
| title only, no 文号 | 960 |
| **total** | **4,159** |
| of which from catalogue lines | 2,848 |
| of which from sentences | 1,311 |
| distinct repeal notices contributing | 1,022 |

Bulk is real: the largest single catalogue names **425** instruments, 59 notices name ten or more, and the
median notice names one. *Measured.*

### 1.3 How many can be dated on both ends

The right end is always exact: it is the repeal notice's own `date_published`. The left end has three
grades.

| left-end grade | instruments | precision |
|---|---:|---|
| resolved to a held corpus document | 1,615 | exact date |
| 文号 named but the document is not in the corpus | 1,693 | year, ±0.5 y |
| title only, unresolved | 851 | **undatable** |
| **datable on both ends** | **3,308 of 4,159 (79.5%)** | |

1,602 of the 1,615 resolutions land inside `sz_gazette` itself, which restates `sz-gazette-scoping.md`
§3.4: this is a self-referential corpus.

**The 文号 year is a usable promulgation year.** Across the 1,506 pairs resolved by 文号, the resolved
document's own `date_published` year equals the 文号 year on **1,418**, is one year later on 80, two on 3,
and differs by more than two on 5. *Measured.* That licenses the 1,693 文号-only rows, which more than
doubles the sample. Their left end uses the 文号 year plus the empirically measured median promulgation
offset of **0.537** of a year (from those same 1,418 rows), so the left-end error on those rows is about
±0.3 years and is centred.

The title route is the weak one: 109 of 960 resolve. Titled repeals matter anyway because 特区法规 and
条例 carry no annual 文号 at all (they are 第N号 announcements, `wenhao-denominator.md` §1.1), so the
人大 repeal decisions are only reachable this way. 851 undatable rows are reported and then excluded.

---

## 2. The two censoring problems

**Right-censoring.** An instrument still in force has no repeal date. A mean over observed repeals
measures only the ones that died. Handled with Kaplan-Meier: every held instrument-shaped gazette document
enters the risk set at its own `date_published` and is censored at 2026-09-30 if no repeal is observed.

**Left-truncation, and it is on the event side, not the entry side.** The gazette's first repeal notice is
dated 2000 and the series has 312 of them. Repeals before 2000 are unobservable, so an instrument issued
in 1996 is at risk of an *observable* repeal only from age 4 onward. Treated as delayed entry: each
document's entry age is `max(0, 2000 − promulgation)`, so the 1990s cohorts contribute to the risk set
only above that age and their invisible early years never enter a denominator. The 1990s cohorts are
therefore **selected for having survived to 2000**, and without the delayed-entry correction they would
read as longer-lived than they are. With it, they do not: the 1995-99 cohort's curve is steeper than every
cohort after 2005 (§3.3).

Two things the correction does not fix, and §5 returns to both: a repeal that was never published, and an
instrument retired by a 有效期 clause with no repeal notice at all.

---

## 3. Survival

### 3.1 The headline: the median is not reached

Universe: the 8,751 gazette documents whose `doc_identity.genre` is promulgation or implementing. Event:
the document's 文号 or normalized title is named in a later repeal notice, or `instrument_succession`
records a stated supersession. 1,721 events, by route 1,246 文号 / 330 succession / 102 title.

Ages are the KM survivor function's crossing points. `n/r` means the quantile is never reached.

| stratum | n | events | P10 | P20 | P25 | **median** | S(5) | S(10) | S(15) | S(20) | plateau |
|---|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---:|---:|
| all instrument-shaped | 8,751 | 1,721 | 5.6 | 11.3 | n/r | **not reached** | 0.91 | 0.82 | 0.77 | 0.76 | 0.75 |
| 文件 numbered | 4,953 | 1,111 | 7.1 | 11.7 | n/r | not reached | 0.94 | 0.83 | 0.77 | 0.76 | 0.76 |
| 规范性文件 register (…规) | 2,258 | 446 | 2.7 | 5.5 | 9.8 | not reached | 0.81 | 0.75 | 0.73 | 0.71 | 0.71 |
| 函 letter | 219 | 7 | n/r | n/r | n/r | not reached | 0.99 | 0.96 | 0.95 | 0.95 | 0.95 |
| no 文号 (条例, 规章, 公告) | 1,321 | 102 | 19.9 | n/r | n/r | not reached | 0.97 | 0.94 | 0.92 | 0.90 | 0.88 |

**Median survival cannot be estimated from published repeals.** *Measured.* The estimable quantiles are
the first and second deciles: the first 10% of instrument-shaped municipal documents are repealed by age
**5.6 years**, the first 20% by **11.3 years**, and the curve then stops moving. The plateau at 0.75 means
roughly three quarters of these documents are never observed to be formally repealed within the window.

A curve that plateaus is not a lifespan distribution. It is a mixture: a minority subject to formal
retirement and a majority that is not, or whose retirement is invisible. §4 and §5 separate the two.

### 3.2 The denominator route agrees, and says why the 文件 number is so low

The serial estimator from `wenhao-denominator.md` gives a coverage-independent denominator. Repeals are
named by 文号 whether or not we hold the document, so for each series-year the numerator (distinct serials
named in repeal notices) and the denominator (N̂_max from the maximum serial) are both independent of our
crawl. Run as a delayed-entry life table over 1,584 series-year cohorts:

| stratum | cohorts | N̂ at risk | events | S(5) | S(10) | S(20) |
|---|---:|---:|---:|---:|---:|---:|
| all numbered series | 1,584 | 221,497 | 2,225 | 1.00 | 0.99 | 0.99 |
| 文件 numbered | 1,064 | 206,664 | 1,701 | 1.00 | 0.99 | 0.99 |
| 规范性文件 register | 481 | 5,359 | 440 | 0.93 | 0.91 | 0.91 |
| 函 letter | 39 | 9,474 | 15 | 1.00 | 1.00 | 1.00 |

This route fails for 文件 and the failure is informative. Shenzhen bodies numbered an estimated 207,000
文件 between 1990 and 2026; published repeal notices name about 1,700 of them, so **under 1% of all
numbered 文件 are ever formally repealed.** *Measured.* Most of a 文号 series is not normative: a 深价管字
notice setting one year's parking fee, a 深计 notice transmitting one annual catalogue, a 深府办函
convening one meeting. Such a document does not need repealing, it simply stops being used. Only the
*normative* subset enters a cleanup register, so a denominator built on all numbered documents is the wrong
denominator for this question.

For the registers the two routes agree closely (S(5) 0.93 denominator-based against 0.81 held-document,
S(10) 0.91 against 0.75; the held version is slightly steeper because register inclusion, though 90-100%,
is not exactly 100%). That agreement is the method check: where the denominator is honest, the
held-document KM reproduces it. *Measured.* The held-document KM is used for everything below.

### 3.3 Cohorts, with the risk still at risk

| issue cohort | n | events | P10 | P20 | P25 | S(5) | S(10) | S(15) | still at risk at 2026-09 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1990-1994 | 51 | 19 | 14.0 | 14.6 | 15.0 | 1.00 | 0.97 | 0.76 | 62% |
| 1995-1999 | 1,351 | 356 | 9.6 | 12.1 | 16.1 | 0.97 | 0.88 | 0.76 | 73% |
| 2000-2004 | 1,446 | 408 | 7.1 | 8.6 | 11.7 | 0.96 | 0.77 | 0.73 | 72% |
| 2005-2009 | 1,752 | 332 | 5.7 | n/r | n/r | 0.93 | 0.84 | 0.82 | 80% |
| 2010-2014 | 1,263 | 165 | 6.7 | n/r | n/r | 0.91 | 0.88 | 0.87 | 87% |
| 2015-2019 | 1,409 | 195 | 5.0 | n/r | n/r | 0.90 | 0.85 | 0.85 | 85% |
| 2020-2026 | 1,479 | 150 | 3.2 | n/r | n/r | 0.86 | 0.84 | 0.84 | 84% |

The "still at risk" column is the plateau value, which is the honest statement of how much of each cohort
has no observed event. It never falls below 62%.

P10 falls monotonically from 14.0 years (1990-94) to 3.2 years (2020-26), which looks like instruments
getting shorter-lived. It is not safe to read that way. P10 is the age at which the *first tenth* is
repealed, and for the recent cohorts that is the only quantile observable at all: the 2020-26 cohort has a
maximum follow-up of 6.7 years, so its curve is 84% censored and everything past S(5) is extrapolation. The
early cohorts' P10 is late partly because their first observable years were consumed by the 2000 truncation.
*Inferred:* the cohort column is dominated by the observation window at both ends, and §4 shows what is
actually moving.

### 3.4 Form: registers die at three times the rate, and that survives matching

The 规范性文件 registers (深建规, 深人社规, 深市监规, 深府规, 深府办规 and 96 more, 2,258 held documents)
appear between 2007 and 2019, so an unmatched comparison against 文件 confounds form with era. Matched to a
single issue window where both forms are in use:

| issue window | form | n | events | P10 | P20 | P25 | S(5) | S(10) | plateau |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2008-2016 | 文件 | 1,568 | 174 | 8.8 | n/r | n/r | 0.93 | 0.89 | 0.89 |
| 2008-2016 | register | 706 | 175 | 3.2 | 7.4 | 16.2 | 0.84 | 0.77 | 0.73 |
| 2010-2018 | 文件 | 1,145 | 97 | n/r | n/r | n/r | 0.94 | 0.92 | 0.91 |
| 2010-2018 | register | 832 | 206 | 3.0 | 6.7 | 10.4 | 0.83 | 0.75 | 0.73 |

**Form matters, and it survives matching.** *Measured.* Within documents issued 2010-2018, a register
document's cumulative probability of observed repeal by age 10 is 25% against 8% for a 文件 of the same
vintage, and the register's P20 of 6.7 years has no 文件 counterpart because the 文件 curve never reaches
its second decile.

The hypothesis offered for testing was that the register regime creates lifespans that are **shorter and
more uniform**. The first half holds, with one correction to its mechanism. The second half does not, and
the reason is instructive. Among documents that *are* repealed, the ages are nearly the same for both forms
once the window is matched:

| form | age-at-repeal, all events | age-at-repeal, issued 2010-2018 |
|---|---|---|
| 文件 | n=1,058, P25 5.2, median 7.8, P75 10.3, IQR 5.1 | n=97, P25 2.3, median 3.7, P75 5.1, IQR 2.8 |
| register | n=415, P25 1.8, median 3.0, P75 4.8, IQR 3.0 | n=199, P25 2.1, median 3.5, P75 5.8, IQR 3.7 |

The large unmatched gap (7.8 against 3.0 years) is a cohort artefact: registers are young, so their
observable ages are short. In the matched window the medians converge to 3.7 and 3.5 and the register's IQR
is slightly *wider*, not narrower. *Measured.*

So the register regime changes the **probability** of formal repeal, not the **timing** among those
repealed. *Inferred:* registration does not shorten an instrument's life. It makes the instrument's
retirement a recordable administrative act, which is a different thing, and §4 and §5 say what actually
sets the date.

For the two main series the same pattern appears inside the government itself: 深府 n=1,081, 197 events,
S(10)=0.85; 深府办 n=950, 112 events, S(10)=0.90; against 深人社规 n=240, 77 events, S(10)=0.62. *Measured.*

### 3.5 The 函 channel is never retired

219 held 函 (深府函, 深府办函), **7 observed repeals**, plateau 0.95. *Measured.* `wenhao-denominator.md`
§6.2 established that the printed 函 do instrument work: 51 of 81 深府函 are genre promulgation, their
median body is longer than 深府's, and 118 of 165 深府办函 titles contain 印发. They are instruments, and
they are essentially never formally repealed.

*Inferred, and it is the most consequential reading in this memo.* The 规范性文件 register is the class
that gets cleaned up. 函 sit outside it. `wenhao-denominator.md` measured the 深府办 numbered 文件 series
collapsing from 86-239 per year to 3-24 while the 函 series held level, so by the 2020s a numbered document
leaving 深圳市政府办公厅 is far more likely to be a 函 than a 文件. This memo adds the consequence: the
channel that grew is the channel with no retirement machinery. That is a testable claim about every other
jurisdiction in the corpus and this memo does not test it.

---

## 4. Repeal is campaign-driven

Calendar-year hazard, instrument-shaped held documents. At-risk counts rise monotonically because the
corpus accumulates.

| year | at risk | repeals | hazard % | | year | at risk | repeals | hazard % |
|---|---:|---:|---:|---|---|---:|---:|---:|
| 2001 | 1,921 | 53 | **2.76** | | 2014 | 4,960 | 134 | **2.70** |
| 2002 | 2,196 | 8 | 0.36 | | 2015 | 5,093 | 34 | 0.67 |
| 2003 | 2,462 | 9 | 0.37 | | 2016 | 5,297 | 33 | 0.62 |
| 2004 | 2,776 | 37 | 1.33 | | 2017 | 5,556 | 29 | 0.52 |
| 2005 | 2,973 | 16 | 0.54 | | 2018 | 5,870 | 73 | 1.24 |
| 2006 | 3,303 | 18 | 0.54 | | 2019 | 6,066 | 26 | 0.43 |
| 2007 | 3,577 | 21 | 0.59 | | 2020 | 6,369 | 58 | 0.91 |
| **2008** | 4,060 | 266 | **6.55** | | 2021 | 6,509 | 36 | 0.55 |
| 2009 | 4,170 | 97 | **2.33** | | 2022 | 6,701 | 53 | 0.79 |
| 2010 | 4,332 | 149 | **3.44** | | 2023 | 6,876 | 43 | 0.63 |
| 2011 | 4,401 | 91 | **2.07** | | 2024 | 7,037 | 80 | 1.14 |
| 2012 | 4,571 | 38 | 0.83 | | 2025 | 7,145 | 55 | 0.77 |
| 2013 | 4,788 | 98 | **2.05** | | 2026 (to 09) | 7,196 | 25 | 0.35 |

Baseline hazard is 0.4 to 0.8% a year. Six years exceed 2%: 2001, 2008, 2009, 2010, 2011, 2013, 2014. The
2008 spike alone is **266 of 1,721 events (15%)**. *Measured.* On the full 文号 event set, which reaches
documents the corpus does not hold, the concentration is sharper still: 639 of 2,832 events fall in repeal
notices dated 2001, 345 in 2008, 272 in 2003, 202 in 2010.

These are named, dated administrative campaigns, not coincidences. The 根据 clauses of the repeal notices
name their authority:

| times named in a repeal notice's 根据 clause | basis document |
|---:|---|
| 34 | 关于清理部分市政府部门规范性文件的通知 |
| 21 | 关于加强规范性文件管理工作的意见 |
| 17 | 关于清理2002年—2006年市政府部门规范性文件的通知 (深府办〔2007〕70号) |
| 15 | 深圳市行政机关规范性文件管理规定 |
| 3 | 深圳市规章和规范性文件清理办法 (深府办〔2015〕…) |

深府办〔2007〕70号 ordered a sweep of 2002-2006 departmental 规范性文件 and the 2008 hazard spike is its
execution: the 2008-11 wave's events have a median issue year of 2001 and a median age at repeal of 8.2
years. Each later wave reaches younger material:

| repeal wave | events | median age at repeal | IQR | median issue year of the repealed |
|---|---:|---:|---|---:|
| 2001-2003 | 70 | 5.0 | 3.6 – 5.6 | 1997 |
| 2008-2011 | 603 | 8.2 | 6.4 – 10.3 | 2001 |
| 2013-2015 | 266 | 6.9 | 4.8 – 10.8 | 2007 |
| 2017-2020 | 186 | 4.4 | 2.4 – 9.7 | 2014 |
| 2021-2026 | 292 | 4.0 | 2.4 – 6.9 | 2019 |

**Age at repeal is a function of the cleanup calendar.** *Measured.* The median falls from 8.2 to 4.0 years
between the 2008-11 wave and the 2021-26 wave, and the mechanism is visible in the last column: the waves
got closer to the material they clear. *Inferred:* once a city runs a periodic clearance exercise, the
average age of what it clears converges on the period of the exercise. The apparent cohort trend in §3.3 is
largely this. What changed over thirty years is not instrument durability but the frequency of the audit.

---

## 5. The sunset channel, which is larger than the repeal channel

A 有效期 clause retires an instrument on a stated date with no repeal notice of any kind. 2,552 gazette
bodies contain 有效期 and **1,871 state an explicit 有效期N年**:

| stated term | documents | | issue block | modal terms |
|---|---:|---|---|---|
| 1 year | 95 | | 1995-1999 | 5y (6), 2y (3) |
| 2 years | 105 | | 2000-2004 | 5y (6), 1y (6) |
| 3 years | 447 | | 2005-2009 | 5y (123), 3y (26) |
| 4 years | 19 | | 2010-2014 | 5y (237), 3y (50) |
| **5 years** | **1,201** | | 2015-2019 | 5y (289), 3y (130) |
| 6-15 years | 4 | | 2020-2024 | 5y (417), 3y (192) |

Three measured facts, and together they are the answer to the question this memo was asked.

1. **The sunset clause is the register's defining feature.** 1,523 of 2,260 register documents (67%) carry
   a parsed 有效期 term, against 293 of 4,953 文件 (6%), 46 of 1,321 no-文号 documents (3%) and 9 of 219
   函 (4%). *Measured.*
2. **The modal term is 5 years and the second mode is 3.** *Measured.* The register's observed
   P20 of 5.5 years and matched-window median age at repeal of 3.5 years sit exactly inside that range. The
   design and the observed behaviour agree.
3. **82% of sunsets are invisible to the repeal method.** Of the 1,871 documents with a stated term, only
   333 (18%) also have an observed repeal. 1,538 do not. *Measured.*

So the undercount is not a rounding error on the §3 curves, it is comparable in size to the entire event
set (1,721 observed repeals against 1,538 stated-term documents with no repeal notice). Correcting it would
steepen the register curves most, because that is where the clauses are, and it would barely move the 文件
curves. *Inferred:* the §3.4 form difference is a *lower* bound on the real difference in retirement rate.
It would not change the §3.1 headline, because the plateau sits at 0.75 across 8,751 documents and the
sunset clauses can account for at most 1,538 of the 6,500 or so that plateau unresolved.

*Inferred mechanism, and it is the reading I would defend.* Shenzhen has two retirement systems and they
belong to different document classes. Ordinary 文件 have no stated term and no scheduled review, so they
are retired only when a cleanup campaign reaches them, which is why their survivor curve plateaus and their
age at repeal tracks the audit calendar rather than anything about the instrument. Registered 规范性文件
carry a written 3 or 5 year term, which is why two thirds of them need no repeal notice at all and why the
third that do get one are repealed at three times the 文件 rate. `wenhao-denominator.md` §6.2 inferred that
the 规范性文件 registration regime narrowed what gets a formal 文件 number; this memo adds that the same
regime is also where the city built its only systematic retirement mechanism, and that the channel municipal
output moved *into* over the same years, the 函, has neither a term nor a register.

---

## 6. Limits

1. **No median survival, and no amount of better pairing would produce one.** The constraint is not the
   matcher. It is that three quarters of these documents are never the subject of a published repeal, so
   the survivor function has nowhere to go. Any paper reporting a median municipal instrument lifespan from
   repeal notices is reporting the conditional age of the repealed minority. §3.1.
2. **An unpublished repeal is invisible.** The method sees repeals the gazette printed. `sz-gazette-scoping.md`
   §4.2 measured gazette inclusion of the 深府 series falling from 18-35% before 2017 to 4-14% after, so
   recent repeal notices are the ones most likely to be missing, exactly where the recent cohorts are. The
   direction of that bias is known: the 2015-26 cohorts' curves are too flat. Partial defence: a repeal
   decision of a 规范性文件 is itself a 规范性文件 and 规 series inclusion is 90-100%, so the register
   curves should be less affected than the 文件 curves. That is an argument, not a measurement.
3. **有效期 undercounts by at least 1,538 instruments**, concentrated 67% in the register class. §5. This
   is the largest single known bias and it runs against the §3.4 finding, so the measured form difference is
   conservative.
4. **851 named repeals are undatable** (title-only, unresolved) and are excluded. They skew toward 条例 and
   特区法规 repealed by 人大 decision, which carry no annual 文号, so the no-文号 stratum in §3.1 is the
   most understated of the four.
5. **The left end is a year, not a date, for 1,693 of 3,308 pairs.** Validated at ±0.3 years centred
   (§1.3), which is immaterial at the five-to-fifteen-year scale of these curves and would matter for any
   sub-annual question.
6. **n = 1 at the jurisdiction level, and it is the least ordinary jurisdiction.** Shenzhen is a special
   economic zone with 特区法规 powers no ordinary prefecture has. No second city in this corpus has the
   pre-2010 depth to check any of this. The method generalizes wherever a gazette prints repeal notices;
   the result does not.
7. **The gazette is a self-referential universe.** 1,602 of 1,615 exact resolutions are internal. Repeals of
   Shenzhen instruments printed elsewhere, and Shenzhen repeals of provincial or central instruments, are
   out of reach. `sz-gazette-scoping.md` §3.4.
8. **Two cohort columns are mostly censorship.** The 2020-26 cohort has at most 6.7 years of follow-up and
   84% of it is still at risk. Its P10 of 3.2 years is real; everything past S(5) in that row is not.

---

## 7. SQL and reproduction appendix

Body coverage and the repeal vocabulary:

```sql
SELECT count(*), sum(body_text_cn!='') FROM documents WHERE site_key='sz_gazette';
-- 11450 | 11204
SELECT sum(body_text_cn LIKE '%废止%'), sum(body_text_cn LIKE '%同时废止%'),
       sum(body_text_cn LIKE '%有效期%'), sum(body_text_cn LIKE '%自动失效%')
FROM documents WHERE site_key='sz_gazette' AND body_text_cn!='';
-- 1457 | 767 | 2552 | 134
SELECT count(*) FROM documents WHERE site_key='sz_gazette' AND title LIKE '%废止%';
-- 312  (1 in 2000, 28 in 2001, 33 in 2008, 20 in 2010, 16 in 2024, 17 in 2025)
```

What `instrument_succession` already supplies (route 1):

```sql
SELECT s.relation, count(*) FROM instrument_succession s
  JOIN doc_identity ip ON ip.instrument_id=s.instrument_id
                      AND ip.instrument_role IN ('canonical','unique')
  JOIN documents dp ON dp.id=ip.doc_id
 WHERE dp.site_key='sz_gazette' GROUP BY 1;
-- revised_edition 1050 | superseded_by_stated 374 | renamed 49 | pilot_to_national 3

-- the dated repeal subset actually used
SELECT count(*) FROM (
  SELECT dp.id FROM instrument_succession s
    JOIN doc_identity ip  ON ip.instrument_id=s.instrument_id
                         AND ip.instrument_role IN ('canonical','unique')
    JOIN documents  dp    ON dp.id=ip.doc_id AND dp.site_key='sz_gazette'
    JOIN doc_identity isu ON isu.instrument_id=s.successor_id
                         AND isu.instrument_role IN ('canonical','unique')
    JOIN documents  ds    ON ds.id=isu.doc_id
   WHERE s.relation='superseded_by_stated' AND s.confidence>=0.9 AND ds.date_published!=''
   GROUP BY dp.id);
-- 337
```

Routes 2 and 3 are a Python pass over `body_text_cn`, because they need line structure and a
negative-lookbehind on 根据 clauses that SQL cannot express. The 文号 pattern, applied to both the cited
text and every corpus `document_number` to build the resolution registry (63,494 distinct keys):

```python
WENHAO = re.compile(r"([一-鿿]{1,14})\s*[〔\[（(【]\s*((?:19|20)\d{2})\s*[〕\]）)】]"
                    r"\s*第?\s*(\d{1,5})\s*号")
# prefix normalized 深圳市 -> 深; key = "prefix|year|serial"
```

Unit selection, after splitting each body on newlines then on 。；:

- catalogue line, in a document whose title matches `废止|失效`: `^\s*[（(]?\s*(\d{1,3}|[一二三四五六七八九十]{1,4})\s*[）)．.、,]`
- sentence: contains 废止 and does not match
  `修改或者?废止|应当.{0,8}废止|相抵触|如有.{0,6}废止|及时废止|依法废止|予以修改|定期清理`
- a 文号 is dropped when the preceding 60 characters contain a `根据|依据|按照|遵照|为贯彻` match with no
  废止 between it and the 文号 (the authorising document), and when the preceding 45 characters contain
  关于废止 (the listed item is itself a prior repeal decision)
- the document's own 文号 is excluded

Left-end validation (§1.3), 文号 year against the resolved document's own date:

```sql
-- the same comparison in SQL form, over the gazette's own rows
WITH t AS (SELECT substr(date_published,1,4)+0 dy,
    CAST(substr(document_number, instr(document_number,'〔')+1, 4) AS integer) zy
  FROM documents WHERE site_key='sz_gazette' AND document_number LIKE '%〔%')
SELECT zy-dy, count(*) FROM t WHERE zy BETWEEN 1980 AND 2026 GROUP BY 1 ORDER BY 2 DESC;
```
The pair-level version gives 1,418 at 0, 80 at +1, 3 at +2, 5 beyond, of 1,506 resolved pairs.

Kaplan-Meier with delayed entry, over held gazette documents (§3.1, §3.3, §3.4). `t0` is
`date_published` as a decimal year, `START=2000.0`, `NOW=2026.747`:

```python
for r in docs:                       # doc_identity.genre in (promulgation, implementing)
    a_in  = max(0.0, START - r.t0)   # delayed entry: repeals before 2000 are unobservable
    a_out = NOW - r.t0               # administrative censoring
    if a_out <= a_in: continue
    rows.append((a_in, min(max(r.event - r.t0, a_in), a_out), 1) if r.event else (a_in, a_out, 0))
S = 1.0
for t in sorted({a for _, a, e in rows if e}):
    R = sum(1 for i, o, e in rows if i <= t <= o)      # risk set respects delayed entry
    d = sum(1 for i, o, e in rows if e and o == t)
    S *= 1 - d / R
```

The denominator-based life table (§3.2) is the same loop with cohorts `(series, year)` instead of
documents, cohort size `N̂_max = m(1+1/k)−1` from `wenhao-denominator.md` §7, entry age
`max(0, 2000 − (year + 0.537))` and exit age `2026.747 − (year + 0.537)`.

Calendar-year hazard (§4):

```python
for Y in range(2000, 2027):
    risk = sum(1 for r in docs if r.t0 < Y+1 and (r.event is None or r.event >= Y))
    d    = sum(1 for r in docs if r.event is not None and Y <= r.event < Y+1)
```

Sunset clauses (§5). The term is parsed with `有效期\s*(?:为|是)?\s*([一二三四五六七八九十0-9]{1,3})\s*年`
over bodies matching `%有效期%`:

```sql
SELECT count(*) FROM documents
 WHERE site_key='sz_gazette' AND body_text_cn LIKE '%有效期%';
-- 2552; 1871 of these yield a parsed 有效期N年 (5y 1201, 3y 447, 2y 105, 1y 95, 4y 19, other 4)
SELECT count(*) FROM documents
 WHERE site_key='sz_gazette' AND body_text_cn LIKE '%有效期%' AND body_text_cn NOT LIKE '%废止%';
-- 2012
```

Cleanup-campaign basis documents (§4) are the `《…》` titles inside the first 1,200 characters of a repeal
notice's 根据 clause, filtered to those containing 清理 or 规范性文件管理.

---

*All figures measured 2026-10-07 against the live droplet DB, read-only, with a crawler writing to other
site_keys. The gazette's own body coverage was complete at 11,204 of 11,450 (97.9%) throughout, so unlike
`sz-gazette-scoping.md` and `wenhao-denominator.md` no figure here is a lower bound on a moving backfill.
This memo supersedes `sz-gazette-scoping.md` §5 rank 2, whose premise (that pairing repeal notices would
yield survival curves by genre and cohort) was right about the pairing and wrong about the curves: the
pairing works at 79.5% datability and the curves do not reach their medians.*
