# Scoping the Shenzhen gazette (`sz_gazette`): does 31 years of one city unlock a study? (2026-10-07)

**Question.** `crawlers/sz_gazette.py` has put 11,450 documents of the 深圳市人民政府公报 into the
corpus, the longest continuous single-jurisdiction run we hold. Does that depth enable research the
corpus could not do before, or is it coverage for studies we already run?

**Scope and method.** Read-only against the live droplet DB (`file:documents.db?mode=ro`, `nice -n 19`,
no writes, no rebuilds, no pull). A body backfill was running throughout, so body coverage is a moving
target: **8,700/11,450 at 22:25 UTC, 8,950 at 22:33, 9,000 at 22:35 UTC on 2026-10-07**, finishing by
roughly 01:00. Every body-coverage figure below carries its timestamp. Metadata figures are stable.
Labels: *measured* = a query in this memo; *inferred* = my reading of a measured pattern.

---

## 1. What is actually there (measured)

| field | rows | share |
|---|---:|---:|
| documents | 11,450 | 100% |
| `publisher` (EXT_fwdw) | 11,450 | 100% |
| `classify_genre_name` (EXT_sort, gazette section) | 11,110 | 97.0% |
| `document_number` (EXT_zh) | 9,750 | 85.2% |
| `body_text_cn` | 9,000 | 78.6% *(22:35 UTC, rising)* |
| `doc_identity` row | 11,450 | 100% |
| distinct gazette issues (`keywords`) | 1,342 | |
| distinct issuers | 890 | |

```sql
SELECT count(*), sum(document_number!=''), sum(publisher!=''),
       sum(classify_genre_name!=''), sum(body_text_cn!=''),
       count(DISTINCT keywords), count(DISTINCT publisher)
FROM documents WHERE site_key='sz_gazette';
```

Per-year shape, 文号 and body coverage (abridged; full series run the query):

| year | docs | 文号 | body @22:29 | year | docs | 文号 | body @22:29 |
|---|---:|---:|---:|---|---:|---:|---:|
| 1987-1994 | 59 | 58 | 58 | 2010 | 366 | 299 | 366 |
| 1995 | 225 | 215 | 66 | 2012 | 359 | 279 | 359 |
| 1996 | 276 | 262 | 73 | 2014 | 392 | 324 | 392 |
| 1997 | 335 | 314 | 108 | 2016 | 332 | 304 | 332 |
| 1998 | 343 | 314 | 115 | 2018 | 434 | 387 | 434 |
| 1999 | 253 | 236 | 95 | 2019 | 358 | 249 | 358 |
| 2000 | 299 | 280 | 175 | 2020 | 415 | 276 | 352 |
| 2002 | 404 | 352 | 404 | 2022 | 302 | 238 | 0 |
| 2004 | 500 | 397 | 498 | 2024 | 267 | 212 | 0 |
| 2006 | 449 | 397 | 449 | 2025 | 251 | 197 | 0 |
| 2008 | 630 | 574 | 630 | 2026 (to 09-30) | 151 | 115 | 0 |

```sql
SELECT substr(date_published,1,4) yr, count(*),
       sum(document_number!=''), sum(body_text_cn!='')
FROM documents WHERE site_key='sz_gazette' GROUP BY 1 ORDER BY 1;
```

Volume is flat at roughly 250 to 500 documents a year from 1995 to 2026, with a 2008 peak (630). Issue
count per year is 40 to 59 after 1997, consistent with a semi-monthly gazette plus specials.

**Sections (top, measured).** 部门文件 4,314 (1995-2026) · 市委市政府文件 1,572 (2000-2015) ·
市政府文件 1,336 (1991-2026) · 法规规章 724 (2007-2026) · 政务动态 620 (2002-2023) · 人事任免 458
(2000-2026) · 特区法规 433 (1995-2008) · blank 340 · plus ~40 pre-2009 per-bureau sections
(市地方税务局文件 333, 市人事局文件 93, 市建设局文件 87 and so on).

**Issuers (top, measured).** 深圳市人民政府 2,930 · 市政府办公厅 1,163 · 市人大常委会 693 ·
市场监督管理局 443 · 法制办 298 · 地方税务局 417 (two name variants) · 人力资源和社会保障局 176 ·
前海管理局 91 (2013-2026). The issuer field tracks bureau renamings, so it is also a 30-year record of
the city's own machinery (建设局 1993-2009 then 住房和建设局 2009-2026, 规划和国土资源委员会 2010-2018
then 规划和自然资源局, 市场和质量监督管理委员会 2014-2019 then 市场监督管理局).

**Analysable text versus apparatus (measured).** `doc_identity.genre`: promulgation 6,823, implementing
1,932, other 2,524, readout 150, news 17, explainer 4. So 76.3% is instrument-shaped. Apparatus is small
and countable: 人事任免 458 section rows (411 by title), 公告/公示 951 by title, 目录 7. There is no
masthead or table-of-contents noise in the rows at all, because the crawler reads the platform's
article JSON rather than scraping issue pages. Body length (docs with a body, 22:33 UTC):

| era | with body | <200 ch | 200-999 | ≥1000 | mean |
|---|---:|---:|---:|---:|---:|
| 1987-1999 | 515 | 3 | 216 | 296 | 1,732 |
| 2000-2004 | 1,811 | 58 | 682 | 1,071 | 2,662 |
| 2005-2009 | 2,313 | 83 | 683 | 1,547 | 3,910 |
| 2010-2014 | 1,826 | 178 | 352 | 1,296 | 5,335 |
| 2015-2019 | 1,883 | 316 | 393 | 1,174 | 3,640 |

Old documents are shorter, not thinner: sampled 1987-1998 bodies carry the full 发文机关, date, 文号,
addressee and text (for example 深军转〔1987〕39号, 818 characters, complete). The 1990s mean of 1,732
characters is a real property of 1990s municipal notices, *inferred*. `date_quality` is `good` on all
11,450 rows and the gazette is 98.1% `municipal` by per-document level.

---

## 2. Correction: the run is 1995-2026, not 1987-2026 (measured)

The 59 documents dated before 1995 are not 1987-1994 gazette issues. They sit in **retrospective
compilation issues printed in 2002 and 2003**:

| doc date | gazette issue it sits in | 文号 |
|---|---|---|
| 1987-12-13 | 2003年第43期（总第359期）| 深军转〔1987〕39号 |
| 1988-09-05 | 2003年第50期（总第366期）| 深税字〔1988〕37号 |
| 1992-04-02 | 2002年第46期（总第295期）| 深渔监字〔1992〕2号 |
| 1993-02-15 | 2003年第4期（总第320期）| 深建字〔1993〕38号 |

总第359期 is a 人事 compilation, 总第366期 a 税务 compilation, 总第320期 a 建设 compilation. The
earliest *issue* folder on the platform is `zfgb/1995/gb68` (总第68期, 1995-04-30), so issues 1 to 67,
the gazette's first six years, are **not published on the site** and are not in the corpus.

```sql
SELECT substr(url, instr(url,'/zfgb/')+6, 9) pathseg, count(*), min(date_published), max(date_published)
FROM documents WHERE site_key='sz_gazette' AND url!='' GROUP BY 1 ORDER BY 1;
```

So: **continuous issue coverage 1995-04 to 2026-09, 31.4 years**, plus 59 earlier documents reprinted
later. That is still by a wide margin the deepest continuous single-jurisdiction run we hold, but the
headline should say 31 years, not 38.

**Dates are trustworthy.** `date_published` is the document's own promulgation date and it agrees with
the 文号 year on 6,920 of 7,822 parsable rows exactly, 645 more at year minus one (a December document
gazetted in January, expected), 247 older by two or more years (the compilations), 3 newer. For 1987
through 2001 the agreement is 921 same versus 9 different. One bad row found: a document dated
1991-01-15 carries 深发[1998]24号 and sits in 1999年第1期. So the NFCMS year-column irregularity
(`zfgb/1901`, `zfgb/1900`) did **not** corrupt dates; the dates come from the article records.

```sql
-- date year vs 文号 year
WITH t AS (SELECT substr(date_published,1,4)+0 dy,
  CAST(substr(document_number, instr(document_number,'〔')+1, 4) AS integer) zy
  FROM documents WHERE site_key='sz_gazette' AND document_number LIKE '%〔%')
SELECT zy-dy, count(*) FROM t WHERE zy BETWEEN 1980 AND 2026 GROUP BY 1 ORDER BY 2 DESC;
```

---

## 3. What it adds that the corpus lacked

### 3.1 A genuine pre-2010 baseline. Confirmed.

| site | docs | pre-2010 | pre-2000 | note |
|---|---:|---:|---:|---|
| **sz_gazette** | 11,450 | **5,741** | **1,491** | full text |
| ifeng | 8,770 | 4,492 | 4,492 | *date field is broken, min `date_published` 2026-07-26* |
| npc | 31,070 | 3,301 | 849 | law records, metadata only, no body |
| chinatax | 5,018 | 2,049 | 463 | central |
| gd | 6,216 | 1,480 | 88 | province |
| js | 5,240 | 1,475 | 0 | province, starts 2003 |

The gazette is **54.3% of every corpus document dated 1995-1999** (1,432 of 2,637) and 23.7% of
2000-2009 (4,250 of 17,928). The rest of Shenzhen starts much later: `sz` 2010, `szdp` 2014, `szlhq`
2017, and only 352 Shenzhen documents outside the gazette predate 2014. Any Shenzhen series that
currently begins mid-2010s gains 19 years.

### 3.2 文号 continuity across decades, with a denominator. Confirmed, and this is the real find.

The 文号 series are unbroken. 深府 runs 1995-2026 (911 held in the 〔〕 style plus 1996-style ascii
brackets), 深府办 1996-2026, and because serial numbers reset annually and are dense, the **maximum
serial we hold in a year estimates the city's total numbered issuance in that series that year**. A
German-tank estimate (`N̂ = m(1+1/k)-1`) is tight where k is large:

| year | 深府 held | max serial | N̂ | 深府办 max | 深府函 max | 深府办函 max |
|---|---:|---:|---:|---:|---:|---:|
| 2001 | 52 | 186 | 189 | 110 | | 143 |
| 2005 | 72 | 220 | 222 | 179 | 127 | 127 |
| 2010 | 48 | 194 | 197 | 111 | 248 | 176 |
| 2015 | 32 | 117 | 120 | 38 | 473 | 371 |
| 2020 | 12 | 89 | 95 | 2 | 401 | 136 |
| 2024 | 8 | 88 | 98 | 9 | 262 | |

Two measured movements, from denominators rather than from our own crawl volume:
numbered 深府 issuance roughly **halves** from ~190/yr (2001) to ~95-120/yr (2015-2024); 深府办
**collapses** from ~110/yr to single digits after 2016; and 深府函 and 深府办函, the *letter* series,
**rise** over exactly the same window (深府函 127 to 473). *Inferred:* the municipal government did not
issue less, it moved from numbered 文件 to 函, a shift in instrument formality that no other part of the
corpus can see, because no other jurisdiction gives us an unbroken 30-year 文号 series.

This also measures the gazette's own selectivity: it printed 18-35% of the 深府 series in 1995-2016 and
4-14% after 2017 (*measured*), which matters for §4.

### 3.3 The genre mix of one municipal government over 31 years. Confirmed, with a caveat.

| era | 特区法规 | 法规规章 | 政府令 (title) | 部门文件 | 市政府 / 市委市政府文件 | 政务动态 | 人事任免 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1995-1999 | 136 | 0 | 47 | 50 | 544 | 0 | 0 |
| 2000-2009 | 297 | 81 | 40 | 1,157 | 1,408 | 439 | 144 |
| 2010-2019 | 0 | 373 | 113 | 2,004 | 736 | 150 | 214 |
| 2020-2026 | 0 | 270 | 45 | 1,103 | 221 | 31 | 100 |

The gazette shifts from publishing the city government's own documents (36% of the 1995-1999 era) to
publishing its departments' (55% of 2020-2026). That is the same direction as the 文号 denominators in
§3.2, from two independent measurements, which is why I believe it is substantive and not only an
editorial rule change. The caveat is in §4: the section *labels* themselves changed (特区法规 ends 2008,
法规规章 begins 2007).

### 3.4 Does the depth connect to the citation graph? Partly. This is the weakest leg.

| target era | edges in | distinct targets | distinct citing docs |
|---|---:|---:|---:|
| <2000 | 1,418 | 538 | 647 |
| 2000-2009 | 10,321 | 2,533 | 3,103 |
| 2010-2019 | 6,945 | 1,814 | 2,602 |
| 2020+ | 2,878 | 453 | 1,957 |

```sql
SELECT count(*), count(DISTINCT c.target_id), count(DISTINCT c.source_id)
FROM citations c JOIN documents d ON d.id=c.target_id
WHERE d.site_key='sz_gazette' AND d.date_published<'2010';
```

Pre-2010 gazette documents receive **11,739 edges across 3,071 targets**, so the old layer is cited, not
isolated. But **9,691 of those edges (82.6%) come from the gazette itself** and only 2,048 from the rest
of the corpus (`sz` 405, `sf` 363, `szdp` 122, `mzj` 109, `gov` 46). The gazette also emits 38,678 edges
from 5,372 documents. Top pre-2010 targets are recognisable Shenzhen anchors: 深圳市行政执法主体公告管理
规定 (2003, 284 citers), 深圳市城市规划标准与准则 (2004, 147), 深圳市行政听证办法 (2006, 113, one of the
two documents CLAUDE.md had recorded as delisted).

*Inferred:* the gazette is a largely self-referential citation universe. That is excellent for tracing
one city's instrument lineage over 30 years and poor for cross-level diffusion work, where the pre-2010
layer has almost nothing above it to connect to, because the corpus's central and provincial depth also
starts later.

### 3.5 It is new material, not a re-mirror. Confirmed.

231 of the gazette's 11,425 `instrument_id`s (2.0%) are shared with any other Shenzhen site
(`sz`, `szdp`, `szlg`, `szlh`, `szlhq`, `szgm`, `szns`). Within the gazette only 14 instruments pool more
than one document. The ingest is almost entirely additive.

---

## 4. Honest limits

1. **One city, and the least representative one.** A special economic zone with 特区法规 powers no
   ordinary prefecture has (433 documents in a section that exists nowhere else in the corpus). Anything
   measured here describes Shenzhen, not "a Chinese municipality". Every §3 finding is n=1 at the
   jurisdiction level and cannot be externally validated inside this corpus, because no second city has
   pre-2010 depth.
2. **Inclusion rules changed, and the change points are visible.** 特区法规 stops in 2008 and 法规规章
   starts in 2007; roughly 40 per-bureau sections (市人事局文件, 市建设局文件 …) all end in 2008-2009 and
   are replaced by one 部门文件 bucket; 政务动态 runs only 2002-2023; 市委市政府文件 only 2000-2015. So
   the §3.3 genre series has an administrative seam at 2008-2009 that would masquerade as a trend if read
   naively. Selectivity moved too: the share of the 深府 series printed falls from 18-35% to 4-14% after
   2017 (§3.2), so **recent gazette volume understates recent issuance** and any "municipal output is
   falling" reading taken from row counts alone would be wrong. The 文号 denominator is the defence
   against this, and it is the reason the §3.2 design works and a row-count design does not.
3. **The 1990s have structural holes.** Issues 1-67 (1989 to early 1995) are absent from the platform.
   1996 arrives as a single collapsed column (`1996/gb19`, 207 documents, one issue id covering
   1995-12-26 to 1996-12-25), so per-issue analysis is impossible for that year. 1995-1999 body coverage
   was still filling at the measurement time (515 of 1,491 at 22:33 UTC) and must be re-checked after the
   writer finishes before any text work on the 1990s.
4. **Dates are fine, the compilations are the only trap.** §2. Filter `date_published < '1995'` out of
   any time series, or attribute those 59 documents to their 2002-2003 gazette issue when the question is
   about publication rather than promulgation.
5. **No `--sync` discipline proven yet.** The run ends 2026-09-30 and the crawler is new; whether it
   stays current nightly is not something this study tested.

---

## 5. Recommendation

The main value is **not** better coverage for existing studies. The existing studies are
diffusion/central-local studies and they need 2014-2026 breadth across jurisdictions, which this does not
add (§3.4: the pre-2010 layer has almost no cross-level partners). The value is one study the corpus
could not previously attempt, plus two cheaper uses.

**Rank 1. "Thirty years of one city's 文号": the formality shift in municipal instruments.** *Recommended.*
- *Question.* Did Shenzhen's municipal government reduce its formal rulemaking, or re-route it, between
  1995 and 2026?
- *Method.* Parse every 文号 into (prefix, year, serial). Per series per year take held count and max
  serial, and estimate the true annual series size (German tank). Produce three aligned series: numbered
  government output (深府, 深府办), letter output (深府函, 深府办函), and department 规范性文件 output
  (深建规, 深人社规, 深财规, 深市监规 and 30 more). Cross-check against the §3.3 section mix, with the
  2008-09 seam marked. Validate the denominator on 2010-2026 against the `sz` and `szdp` sites, where we
  hold documents the gazette did not print.
- *Figure.* One panel, 1995-2026, three stacked estimated-issuance bands (government numbered, government
  letters, department rules), with gazette inclusion rate as a thin line beneath so the reader sees the
  selection separately from the trend.
- *What it adds to `findings-synthesis.md`.* A new kind of claim. Every current finding is about *flow
  between* levels measured on documents we happen to hold. This one measures *a government's total
  output* against a serial-number denominator, so it is the first result in the volume that is not
  coverage-limited. It supports Part I (authority and genre) with a 30-year instrument-formality series,
  and it gives the recentralization chapter a municipal-side reading: formality moved from 文件 to 函 and
  from the government to its departments over exactly the 2013-2017 window where the upward-citation
  share steps up.
- *Cost.* Low. 文号 parsing plus five aggregates, no LLM, no crawling, one afternoon. It needs no body
  text, so it is not blocked on the backfill.

**Rank 2. Instrument lifespan and supersession in one jurisdiction.** *Conditional.*
- *Question.* How long does a municipal instrument live, and has that changed?
- *Basis.* 1,153 bodies contain 废止 and 610 contain an explicit 同时废止/予以废止, with 2,464 carrying
  有效期/试行 (*measured, as of the 22:35 UTC body state*). The gazette prints the repeal notice and the
  instrument it repeals, so promulgation-to-repeal pairs are extractable within one site, over 31 years.
- *Figure.* Survival curves by genre and by promulgation cohort (1995-2004, 2005-2014, 2015-2026).
- *Cost.* Medium, and it is **blocked until the body backfill finishes** and the 1990s bodies are present.
  Pair extraction needs a named-instrument matcher inside bodies; `TitleMatcher` can do it but the pairs
  need hand validation. Two to three days.
- *Why rank 2.* Genuinely new, but it answers a question `findings-synthesis.md` does not currently ask,
  so it is an addition rather than a strengthening.

**Rank 3. Use it as infrastructure: the Shenzhen anchor set and the queue.** *Do this regardless, it is
not a study.*
- 3,071 pre-2010 gazette documents now have inbound citations, and the A6 audit already found 10 of 11
  probed "missing" Shenzhen instruments here. Re-rank `citation-crawl-queue.csv` after this ingest and
  retire the Shenzhen rows it resolves. Cost: hours. Value: raises absolute resolved citations and removes
  false demand from the queue, which is a measurement-quality gain for every existing study rather than a
  new one.

**What I would not do.** Do not extend any diffusion or fidelity study backwards using this. The partners
are missing (§3.4) and the result would be a story about our crawl history.

---

*All figures measured 2026-10-07 22:25-22:36 UTC against the live droplet DB, read-only, while a body
backfill was writing. Body-derived counts are lower bounds and should be re-measured after it finishes.*
