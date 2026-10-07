# Pilot-Site Selection and Provincial GDP: a Descriptive Test of Wang & Yang's Positive-Selection Finding

*Corpus-lessons addition B4. A read-only join of a small external panel (provincial GDP per
capita, 31 units, 2000 and 2004-2025) to the corpus's central pilot-guideline record, run
against the live `documents.db` (droplet, 2026-10-06, `?mode=ro`). It tests, descriptively,
the one part of Wang and Yang's causal core that `experimentation-wang-yang.md` §0 said was
out of reach: that policy experiments are run in richer-than-median localities. Every series
is a share, a rank or a rate against a same-year cross-section. Reproduce with
`scripts/rnd/analysis/site_selection_gdp.py analyze`; the GDP file is `data/provincial_gdp.csv`
(built by the same script's `build-gdp`). SQL and the join sketch are in the appendix.*

---

## 0. What this does and does not replicate

Wang and Yang (NBER w29402 / JPE 2025) report that more than 80% of the 633 experiments in their
hand-built record were run in positively selected localities, i.e. sites with pre-experiment
GDP per capita above the national median, and that about half of that selection is explained
by local officials' promotion incentives. They then show that pilot sites spend more in the
policy domain during the trial and that the center under-corrects for both effects.

| Their claim | Tested here? | How |
|---|---|---|
| Pilot sites are richer than the median locality | **Yes, descriptively, at province level** | provinces named in the guideline text vs same-year provincial median GDP per capita |
| Richer provinces are over-selected relative to their size | **Yes, descriptively** | designations per province / population share, rank-correlated with GDP per capita |
| Selection is driven by promotion incentives | **No** | needs local-leader career data; not in this project |
| Pilot sites exert strategic fiscal effort | **No** | needs fiscal-expenditure panels; not in this project |
| The center under-corrects when scaling up | **No** | needs the two above plus exogenous shocks |

Three unit differences from their test, stated up front. (1) **Province, not prefecture or
county.** Their localities are mostly prefectures and counties. We only hold province-level
GDP, so a guideline that designates Suzhou is scored at Jiangsu's income. This compresses the
dispersion the test is looking for and should bias our result *toward* the null. (2)
**Document, not experiment.** Our unit is a central guideline document whose title carries an
experiment cue, de-duplicated on title; theirs is a hand-merged experiment. (3) **Named site,
not confirmed site.** We read sites out of the text by place name. The audit in §6 shows the
extraction is clean at the top but not perfect.

---

## 1. Data

### 1a. GDP panel (`data/provincial_gdp.csv`)

31 provincial-level units, 23 years (2000 and 2004-2025), 713 rows. Fields: GDP (亿元),
GDP per capita (元), year-end population (万人), source.

| years | source | rows |
|---|---|---|
| 2004-2007 | NBS China Statistical Yearbook 2009-2012, table 2-14 地区生产总值 (xls), per-capita derived as GDP / year-end population (yearbook 2013/2014 population tables) | 124 |
| 2008-2013 | NBS Yearbook 2013 (table 2-15) and 2014 (table 3-15) 人均地区生产总值 as published | 186 |
| 2014-2019 | **interpolated** (log-linear between 2013 and 2020, per province); population from NBS Yearbook 2021 table 2-5 | 186 |
| 2000, 2010, 2020-2025 | NBS-revised series (post 4th economic census) as tabulated on Wikipedia from NBS and provincial statistical communiqués; 2010 is overridden by the yearbook vintage | 217 |

The NBS data portal (`data.stats.gov.cn`) refuses non-mainland IPs (403, UrlACL) and the
2015-2020 yearbook editions publish their regional tables as images only, which is why
2014-2019 is interpolated. **Evidence that the interpolation is harmless for a rank test:**
restricting GDP lookups to observed years changes the headline shares by 0.1-0.5 points (§2).
**Evidence on vintage:** the 2010 cross-section exists in both the yearbook vintage and the
revised series; Spearman between them is 0.945 and the median revision is -0.4%. Province
rank in GDP per capita is stable but not frozen over the window: Spearman(2010, 2020) = 0.729,
so the test uses the guideline's own year.

### 1b. Corpus side

Central pilot guidelines are detected exactly as in `experimentation-wang-yang.md` §1: title
carries `试点|试验区|先行先试|示范区`, is not a news genre, and is in a designating genre;
`admin_level = central`; dated 2000-2026. `npc` is excluded here (its "central" rows are local
people's-congress regulations). That gives 1,539 rows, which collapse to **1,261 distinct
titles** once gov.cn mirror copies and double crawls are merged (the earliest-dated copy with
the longest body is kept; all copies' ids are retained for the citation join). 1,181 have a
body of more than 200 characters.

**Pilot sites** are extracted from title plus body by matching the 31 province names and a
curated list of about 120 city and national-new-area names mapped to their province (深圳 →
广东, 浦东 → 上海, 雄安 → 河北, 霍尔果斯 → 新疆, and so on). Three kinds of text are stripped
before matching because they name a province without designating it: `《…》` spans (titles of
cited instruments), the string 新疆生产建设兵团 (it sits in the standard distribution list of
almost every NDRC and ministry notice, and before this strip Xinjiang was the most "selected"
province in the corpus with 438 designations; after it, 36), and address or postcode lines.
A guideline naming 20 or more provinces is a national roll-call, not a selection, and is
reported separately.

Sub-national documents are mapped to provinces for the implementing-side test by `site_key`
(`SITE2PROV` in the script: 13 Shenzhen bureaus and 10 Shenzhen districts to 广东, `hlj` to
黑龙江, `cq_*` bureaus to 重庆, and so on). All 423 sub-national sites map; 28 of 31 provinces
have at least one document. 天津, 海南 and 河南 are effectively uncovered (0, 0 and 32
documents).

---

## 2. Which guidelines name sites

| measure | n | share of 1,261 |
|---|---|---|
| names at least one province in the **title** | 251 | 0.199 |
| names at least one province in title or **body** | 793 | 0.629 |
| of which **selective** (1-19 provinces) | 737 | 0.584 |
| of which national roll-call (20 or more) | 56 | 0.044 |
| names none | 468 | 0.371 |

Distribution of provinces named, selective set: one province 314, two 85, three 49, four 43,
five 38, six to ten 112, eleven to nineteen 96. The 468 that name nothing are mostly
instruments *about* a pilot regime rather than designations of sites (tax rules for 试点
enterprises, a fund-management measure for a 试点 programme, a 示范区 standard).

**Evidence, by period (selective / all guidelines):** 2000-07 11/34 (0.32), 2008-12 71/125
(0.57), 2013-17 135/216 (0.63), 2018-22 353/563 (0.63), 2023-26 167/323 (0.52). The share
that names explicit sites rose with the 2013-2022 experiment wave and has fallen since 2023,
when more pilot instruments are frameworks and lists issued without a province in the text we
hold (name lists are often PDF attachments, which the body field does not always carry).

---

## 3. Positive selection

**Method.** For each selective guideline, take the GDP per capita of each named province in
the guideline's year and the median across all 31 provinces in that year. Three metrics:
(a) *mean > median*: the pilot set's mean GDP per capita exceeds the national median (the
phrasing closest to Wang and Yang); (b) *majority above*: more than half the named provinces
are above the median; (c) *mean percentile rank*: average percentile (0-1) of the named
provinces in that year's 31-province ranking, random expectation 0.500.

Metric (a) is biased upward by the shape of the distribution: Beijing, Shanghai and Tianjin
sit far above the rest, so even a randomly drawn set has a mean above the median more often
than not. The fair baseline is simulated (20,000 draws, set sizes drawn from the observed
distribution): uniform draws give **69.6%** on (a), **40.5%** on (b), **0.500** on (c);
population-weighted draws give 72.1%, 41.6%, 0.509. Read every result against those, not
against 50%.

| set | n | (a) mean > median | (b) majority above | (c) mean percentile |
|---|---|---|---|---|
| **all selective guidelines (title + body sites)** | **737** | **0.883** | **0.776** | **0.705** |
| strong sites only (in title, or named twice or more in body) | 635 | 0.854 | 0.767 | 0.702 |
| title-named sites only (cleanest extraction) | 248 | 0.742 | 0.730 | 0.700 |
| exactly one province named | 314 | 0.755 | 0.755 | 0.736 |
| 2-5 provinces named | 215 | 0.986 | 0.758 | 0.733 |
| 6-19 provinces named | 208 | 0.971 | 0.827 | 0.631 |
| GDP from observed (non-interpolated) years only | 737 | 0.878 | 0.777 | 0.703 |
| strict 试点 cue in title | 500 | 0.910 | 0.802 | 0.713 |
| excluding 示范区 / 试验区 zone names | 472 | 0.909 | 0.794 | 0.709 |
| State Council portal (`gov`) anchors only | 467 | 0.861 | 0.756 | 0.686 |
| ministry-site anchors only | 270 | 0.922 | 0.811 | 0.739 |
| 批复 (replies to a locality's request) | 140 | 0.714 | 0.600 | 0.601 |
| non-批复 (assigned designations) | 597 | 0.923 | 0.817 | 0.729 |
| *national roll-calls (20+ provinces), for reference* | *56* | *0.964* | *0.429* | *0.515* |
| *random baseline, uniform* | | *0.696* | *0.405* | *0.500* |
| *random baseline, population-weighted* | | *0.721* | *0.416* | *0.509* |

**Evidence.** On the metric closest to Wang and Yang's phrasing, **88.3%** of the 737 selective
guidelines name a pilot set whose mean GDP per capita is above the same-year provincial median,
against their ">80%". The honest comparison is against the 70-72% a random draw would produce
on that metric, so the excess is about 16-18 points, not 38. On the two metrics that are not
skew-biased the excess is large and stable: **77.6%** of guidelines have a majority of their
named provinces above the median (baseline 41%), and the named provinces sit on average at the
**0.705** percentile of the national ranking (baseline 0.500), i.e. in the top third. The
roll-call set behaves as a control: with 20 or more provinces named it scores 0.515 on the
percentile metric, indistinguishable from random, which is what a list of everyone should do.

**Evidence, robustness.** The percentile metric is 0.70 ± 0.04 across every cut: title-only
extraction (0.700), strong sites (0.702), observed GDP years only (0.703), strict 试点 (0.713),
no zone names (0.709), `gov` anchors (0.686), ministry anchors (0.739). It does not depend on
the interpolated years, the extraction tier, the cue, or the publishing portal. The one cut
that moves it is genre: **批复** (the State Council approving something a locality asked to do)
scores 0.601 and 60% on the majority metric, against 0.729 and 82% for assigned designations.
Locality-initiated trials are closer to income-neutral; center-assigned trials are where the
selection concentrates. Wang and Yang hand-code the assigned-vs-voluntary split; the 批复 genre
is its automatic proxy, and it points the way their mechanism would predict (the center picks
sites that can deliver; localities that ask are a broader mix).

**Evidence, by period.** Percentile metric: 2000-07 0.734 (n=11), 2008-12 0.708 (71), 2013-17
**0.750** (135), 2018-22 0.665 (353), 2023-26 0.750 (167). Majority metric: 0.82, 0.79, 0.87,
0.71, 0.84. Selection is strongest in the 2013-2017 reform wave and in the current period, and
weakest in 2018-2022, when the big multi-province programmes (碳达峰 lists, 营商环境 pilots,
服务业扩大开放) spread sites across more of the income distribution. There is no sign of the
selection fading over time.

---

## 4. Which provinces are over-selected

**Method.** Count, over the 737 selective guidelines, how many times each province is named
(3,254 province-designations). Selection ratio = province's share of designations / province's
share of 2015 population. Rank-correlate with 2015 GDP per capita.

| province | designations | in title | selection ratio | GDP pc 2015 (元) |
|---|---|---|---|---|
| 上海 | 283 | 44 | **4.89** | 107,548 |
| 海南 | 97 | 11 | 4.36 | 40,332 |
| 北京 | 223 | 20 | 4.33 | 111,749 |
| 天津 | 145 | 13 | 4.28 | 100,474 |
| 宁夏 | 34 | 4 | 2.11 | 43,609 |
| 青海 | 23 | 2 | 1.69 | 40,410 |
| 西藏 | 13 | 0 | 1.67 | 32,068 |
| 重庆 | 114 | 6 | 1.58 | 50,924 |
| 福建 | 144 | 12 | 1.53 | 68,649 |
| 浙江 | 205 | 19 | 1.45 | 77,274 |
| 陕西 | 99 | 2 | 1.09 | 48,472 |
| 广东 | 289 | 33 | 1.05 | 66,311 |
| 辽宁 | 98 | 4 | 0.96 | 61,365 |
| 内蒙古 | 55 | 6 | 0.96 | 69,068 |
| 江苏 | 186 | 17 | 0.95 | 86,145 |
| 湖北 | 118 | 5 | 0.86 | 49,835 |
| 黑龙江 | 69 | 4 | 0.83 | 39,150 |
| 四川 | 150 | 7 | 0.78 | 38,523 |
| 吉林 | 44 | 5 | 0.71 | 48,404 |
| 山东 | 164 | 10 | 0.71 | 60,741 |
| 安徽 | 97 | 7 | 0.68 | 38,619 |
| 新疆 | 36 | 4 | 0.64 | 41,668 |
| 河北 | 107 | 7 | 0.62 | 41,505 |
| 江西 | 62 | 5 | 0.59 | 37,577 |
| 甘肃 | 34 | 1 | 0.57 | 27,444 |
| 广西 | 62 | 5 | 0.55 | 34,045 |
| 山西 | 44 | 5 | 0.53 | 39,064 |
| 贵州 | 43 | 1 | 0.49 | 28,230 |
| 湖南 | 73 | 5 | 0.47 | 42,834 |
| 河南 | 99 | 10 | 0.43 | 39,068 |
| 云南 | 44 | 2 | 0.40 | 31,134 |

**Evidence.** Spearman(selection ratio, GDP per capita) = **0.625** over 31 provinces;
Spearman(raw designation count, GDP per capita) = 0.690; title-only selection ratio vs GDP
per capita = 0.648. Designations track income more than they track size: Spearman(raw count,
population) is only 0.510. By GDP-per-capita tercile, the richest ten provinces take **55.1%**
of designations against 38.2% of population; the poorest ten take 19.9% against 34.7%; the
middle eleven are at parity (25.0% vs 27.1%).

**Evidence, what the ranking is made of.** The three municipality-provinces (上海, 北京, 天津)
are selected at four times their population share and are also the three richest units; they
carry much of the correlation. 海南 is the fourth, and it is the one poor unit in the top four:
the 2018-2025 free-trade-port programme and its many sector pilots make Hainan a designated
site far out of proportion to its size and its income. The small western units (宁夏, 青海,
西藏) also sit above parity, partly a small-denominator effect (one designation is a large
share of a 3-7 million population) and partly the ethnic-region and ecological pilots they
host. The two large rich provinces, 广东 (1.05) and 江苏 (0.95), are at parity: their large
populations absorb a large absolute count (289 and 186 designations, the first and fourth
highest). The large poor interior provinces (河南, 湖南, 云南, 贵州, 广西) are the clearest
under-selected group at 0.40-0.55. The picture is: a small set of rich, compact units and
Hainan are the over-selected sites; the big populous provinces are at parity whether rich or
not; the populous interior is under-selected.

---

## 5. Implementing side: who echoes central pilot instruments

**Method.** `diffusion_events` rows with `anchor_level = central` and `source_implementing = 1`
(the implementing-instrument flag from `fidelity`), lag ≥ 0, mapped source site → province.
Because raw counts are a function of crawl depth (Guangdong alone is 110,701 of the 176k
mapped sub-national documents), the rate is events per 1,000 corpus documents of that
province, and provinces are grouped by 2015 GDP-per-capita tercile.

| anchors | tercile | provinces covered | events | docs | events / 1k docs | distinct anchors | median lag |
|---|---|---|---|---|---|---|---|
| pilot guidelines only (371 events) | low | 9 | 2 | 5,905 | 0.34 | 1 | 564 d |
| | mid | 10 | 42 | 15,612 | 2.69 | 16 | 238 d |
| | high | 9 | 327 | 154,471 | 2.12 | 44 | 276 d |
| all central anchors (18,285 events) | low | 9 | 232 | 5,905 | 39.3 | 148 | 251 d |
| | mid | 10 | 2,375 | 15,612 | 152.1 | 1,120 | 267 d |
| | high | 9 | 15,678 | 154,471 | 101.5 | 2,382 | 293 d |
| continuously-crawled sites only (R2) | low | 9 | 0 | 5,905 | 0.0 | 0 | |
| | mid | 10 | 982 | 15,612 | 62.9 | 601 | 241 d |
| | high | 9 | 8,675 | 154,471 | 56.2 | 1,816 | 276 d |

Rank correlations across the 28 covered provinces: Spearman(events per 1k docs, GDP per
capita) = 0.407 for pilot anchors (0.373 excluding Guangdong), 0.356 for all anchors (0.337),
0.459 in the continuous set. Spearman(median lag, GDP per capita) = -0.462 (pilot anchors),
-0.016 (all anchors), -0.472 (continuous).

**Evidence, and the caveat that governs it.** Richer provinces echo central pilot instruments
at a higher per-document rate and with a shorter lag, and the poorest tercile barely echoes
them at all (2 events on 5,905 documents). That is the direction Wang and Yang's selection
would predict for implementation. **It is not evidence of it.** The low tercile's coverage is
nine provinces represented almost entirely by department-tier sites (西藏 bureaus, 山西 and
安徽 cities) that publish short notices and rarely carry a 文号-resolvable citation, so their
events-per-document rate is a measure of what those sites publish, not of what the province
does. The mid tercile is 黑龙江 and 重庆, two of the best-crawled non-coastal units, which is
why it outscores the high tercile on the all-anchors rate (152 vs 102 per 1k). The high
tercile is Guangdong plus four deep provincial portals. The continuous-coverage set has six
provinces and none in the low tercile. The lag correlation flips sign between anchor sets.
This section says the corpus cannot separate "richer provinces implement more" from "we crawl
richer provinces deeper and at the portal tier"; it is reported so the confound is on the
record, not as a finding.

**Evidence, designation meets implementation.** Only **30** of the 737 selective guidelines
have any mapped implementing event in `diffusion_events`. For 28 of those 30 (0.93), at least
one implementer is a province the guideline named. The named provinces we most often cannot
see implementing are 天津 (8 guidelines) and 海南 (4), both at zero corpus coverage. The
designation chain and the implementation chain agree where both are visible, and the gap
between 737 and 30 is coverage and citation resolution, not disagreement.

---

## 6. Audit of the extraction

The twelve guidelines with the most province mentions are all genuine designations: the
交通强国 pilot opinions for 浙江 (387 mentions), 江苏 (243), 广西 (149) and 重庆 (105); the 2016
State Council decision suspending regulations in the four free-trade zones (福建, 天津, 上海,
广东 at 50-53 mentions each); the Shenzhen 先行示范区 market-access measures (广东 179); the
2025 要素市场化配置 pilot approval (广东 29, 江苏 23, 浙江 20, 福建 18, 重庆 17, 湖南 16); the
2020 notice issuing the 北京, 湖南, 安徽 free-trade-zone plans and 浙江 extension. The
single-province sample is also clean: 山西 coal-industry pilot, 山西 / 新疆 / 湖北 pension
account pilots (2008 批复), 苏州工业园区 bonded-port pilot (江苏), 海南 rural-credit-cooperative
reform, 赣州 and 闽西 old-revolutionary-area 示范区 (江西, 福建), 成都 park-city 示范区 (四川).

Known residual noise. A province named once as a comparison or a cited precedent ("借鉴上海经验")
counts as a site in the all-sites tier; the strong-sites tier (title, or two or more mentions)
removes most of that and moves the headline by 1-3 points. Province names inside quoted
instrument titles are stripped, but names inside unquoted references are not. The curated
city list covers capitals, plan-listed cities, large prefectures and national new areas; a
pilot sited in a smaller prefecture or county is scored only if the province is also named,
which most guidelines do. Attachments (名单 PDFs) are outside the body field for some sites,
which is the main reason 37% of guidelines name no site.

---

## 7. Threats to validity

1. **Province-level income is the wrong grain.** Wang and Yang select at prefecture and county
   level. A pilot in a rich prefecture of a poor province is scored poor here. This biases
   toward the null; the positive result survives it.
2. **Document unit.** 1,261 de-duplicated guideline documents are not 633 experiments. Multi-wave
   programmes appear once per wave; a programme that selects the same rich sites in three waves
   counts three times. The title-only and single-province cuts are least exposed and give the
   same percentile (0.70, 0.74).
3. **Interpolated 2014-2019.** Six of 23 panel years are interpolated. Observed-years-only
   results differ by 0.1-0.5 points. Rank order is what the test uses.
4. **Vintage mixing.** 2004-2013 is yearbook vintage, 2020-2025 is the revised series. The
   2010 overlap shows Spearman 0.945 between vintages. The join is per year, so the mix never
   enters one cross-section.
5. **Mean > median is skew-biased.** Reported because it is Wang and Yang's phrasing, but the
   random baseline on it is 70-72%, not 50%. The majority and percentile metrics carry the
   argument.
6. **Extraction is text-based.** Boilerplate (the 兵团 distribution list) moved Xinjiang from
   first to twenty-second in the selection ranking; residual asides and unquoted references
   remain (§6). Title-only extraction is the clean floor and agrees.
7. **Implementing side is coverage-bound.** 28 of 31 provinces covered, most of the poor
   tercile at department tier, Guangdong 63% of mapped documents, 天津 and 海南 uncovered. §5 is
   a confound record, not a result.
8. **Selection ratio favours small units.** 宁夏, 青海, 西藏 and 海南 have small denominators. The
   tercile shares and the raw-count correlation (0.690) do not depend on that.
9. **Not causal, anywhere.** This note shows that the center names richer provinces as pilot
   sites more often than their population share and more often than chance. It cannot say
   why. Wang and Yang's incentive mechanism (promotion data) and effort finding (fiscal data)
   are untouched.
10. **Scope boundary.** Mechanism-level claims about a published document record joined to a
    public statistical series, with the grain (1), unit (2), extraction (6) and coverage (7)
    caveats above. No regime-type labels.

---

## 8. Bottom line

The corpus can now speak, descriptively, to the first of Wang and Yang's three causal
findings. Across **737** central pilot guidelines that name specific sites (de-duplicated,
2000-2026), **88.3%** name a set whose mean GDP per capita is above the same-year provincial
median, against their ">80%" and against a 70-72% random baseline on that metric. On
skew-neutral metrics the selection is unmistakable: **77.6%** of guidelines name a majority of
above-median provinces (random 41%), and the named provinces sit at the **0.705** percentile
of the national income ranking (random 0.500), stable at 0.70 ± 0.04 across every extraction
tier, cue, portal and GDP-year choice. The richest ten provinces take 55% of designations on
38% of the population; the poorest ten take 20% on 35%. The selection ratio rank-correlates
with GDP per capita at **0.625** and is driven by 上海, 北京, 天津 and 海南 at four times their
population share, with the populous interior (河南, 湖南, 云南, 贵州) at 0.4-0.5. Assigned
designations select harder than 批复 replies to locality requests (percentile 0.73 vs 0.60),
the automatic proxy for their assigned-vs-voluntary split. The implementing side points the
same way but is coverage-confounded and is recorded as such. What the corpus still cannot do
is explain the selection: the promotion-incentive mechanism, the fiscal-effort finding and the
under-correction result need data this project does not hold.

---

## Appendix: data build, SQL and join sketch

**GDP build.** `python3 scripts/rnd/analysis/site_selection_gdp.py build-gdp --nbs-dir <xls> --wiki-dir <html>`
reads the NBS yearbook tables listed in `NBS_TABLES` (editions 2009-2014 GDP windows,
2013/2014 per-capita, 2013/2014/2021 population) and the two Wikipedia pages in `WIKI_PAGES`
(NBS-revised 2000/2010/2020-2025 GDP and per-capita), takes the latest edition for each year,
derives per-capita for 2004-2007, interpolates 2014-2019, and writes `data/provincial_gdp.csv`
with a `source` column per row. The file header repeats the source URLs.

**Analysis.** `python3 scripts/rnd/analysis/site_selection_gdp.py analyze --db documents.db`
(read-only, ~9 s on the droplet; `--dump out.csv` writes the per-guideline pilot sets).

```sql
-- Central pilot guidelines (title cue + designating genre + not news; npc excluded).
-- Regexes applied in Python: pilot = 试点|试验区|先行先试|示范区;
-- news = 图解|解读|答记者问|新闻发布|访谈|媒体|吹风会|发布会|问答|一图;
-- desig = 方案|通知|意见|决定|批复|公告|办法|规定|印发|的函|工作
SELECT d.id, d.title, substr(d.date_published,1,10), d.site_key, d.body_text_cn
FROM documents d JOIN sites s ON s.site_key=d.site_key
WHERE s.admin_level='central' AND d.site_key!='npc'
  AND length(d.date_published)>=10 AND substr(d.date_published,1,4) BETWEEN '2000' AND '2026';
-- de-duplicate on title with whitespace/brackets removed; keep all copy ids for joins.

-- Site extraction (Python): strip 《…》, 新疆生产建设兵团, 地址/邮编 lines; then count the 31
-- province names (海南 with a (?!藏族) guard) + CITY2PROV names (deepest-first alternation).
-- selective = 1..19 provinces named; roll-call = 20+.

-- Join sketch (per guideline g, year y = substr(date_published,1,4)):
--   pc[p] = gdp_per_capita_yuan for (province p, nearest year to y)   -- from data/provincial_gdp.csv
--   med   = median over 31 provinces of pc[p] in that year
--   (a) mean(pc[p] for p in sites) > med
--   (b) share(pc[p] > med for p in sites) > 0.5
--   (c) mean percentile = mean over sites of rank(pc[p]) / 30
--   baselines: 20,000 random site sets, |set| drawn from the observed distribution,
--              uniform and population-weighted (2015 population).

-- Selection ratio per province:
--   desig[p] = count of selective guidelines naming p
--   ratio[p] = (desig[p] / sum desig) / (pop2015[p] / sum pop2015)
--   Spearman(ratio, pc2015) with average ranks for ties.

-- Implementing side (coverage denominator = mapped sub-national docs per province):
SELECT d.site_key, s.admin_level, count(*) FROM documents d JOIN sites s ON s.site_key=d.site_key
WHERE s.admin_level IN ('provincial','municipal','department','district')
  AND length(d.date_published)>=10 AND substr(d.date_published,1,4) BETWEEN '2000' AND '2026'
GROUP BY 1,2;                                           -- site_key -> province via SITE2PROV

SELECT de.anchor_id, de.source_id, de.lag_days, d.site_key
FROM diffusion_events de JOIN documents d ON d.id=de.source_id
WHERE de.anchor_level='central' AND de.source_implementing=1
  AND de.lag_days IS NOT NULL AND de.lag_days>=0;      -- restrict anchor_id to guideline ids for the pilot-anchor rows
-- rate = events / docs * 1000 per province; terciles on pc2015 (10/11/10);
-- R2 continuous sites = bj sh gd js hlj gz zhongshan huizhou jieyang wuhan.
```
