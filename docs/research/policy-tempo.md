# Policy Tempo: Turning the Tracker's Weekly Cascade Series Into an Instrument

*Method memo, 2026-10-07. Tests `corpus-lessons.md` B7: the claim that the tracker's per-area
weekly cascade series is a "policy tempo" measurement no paper has. Read-only pass over the live
`documents.db` on the droplet (323,529 documents; `diffusion_events` 36,116 rows after the
2026-10-07 nightly rebuild; `tracker_weekly` 45,151 rows). Four descriptive instruments are
built: tempo (cascade yield per central instrument), burstiness, lead-lag between topics, and a
level decomposition of burst weeks. Every series is normalized; raw weekly counts are shown only
to locate bursts. Builds on `daily-tracker-concept.md`, `consumption-diffusion.md`,
`ai-governance-diffusion.md`, `attention-campaigns.md` and `recentralization-experimentation.md`.*

*Evidence labels: **[measured]** = computed from the DB in this pass; **[inferred]** = a derived
quantity that rests on a stated assumption; **[reading]** = interpretation; **[caveat]** = a known
weakness of the measure.*

---

## 0. Short answer

**History depth.** `tracker_weekly` holds 458 ISO weeks (2018-W01 to the current week) for 29
topics plus `all`. The `all` row has a non-zero central cascade count in 454 of those weeks.
Topics are sparser: Finance has cascades in 302 weeks, Government 242, Tech 232; Credit 58,
Weather 31, Party 8, Awards 0. Below 2018 the rollup is silent by design, but `diffusion_events`
reaches back to 2000, so the 2015-2026 series in this memo is computed from the events table
directly **[measured]**.

**Right-censoring is severe for anchor cohorts and mild for source weeks.** Of 13,081 confirmed
implementing cascades to central anchors, 2.2% arrive within 4 weeks of the anchor, 5.6% within
8, 8.8% within 12, 41% within a year, 67% within two (median lag 473 days) **[measured]**. A
central instrument's eventual cascade is therefore almost invisible for its first quarter. The
tracker counts cascades by the week the LOCAL document was published, and that count is censored
only by crawl latency: 70% of sub-national documents published since June 2026 were in the corpus
within 7 days and 86% within 28 **[measured]**. A week's cascade count is close to final after a
month; an instrument's cascade yield is not final for two years.

**Tempo.** Measured as implementing cascades arriving within 365 days per central promulgation
carrying the topic (anchor-year cohort, censoring-corrected for 2025-26), the fastest areas over
2018-2025 are **Government** (procedural and administrative rules: 0.71 cascades per instrument,
0.0136 per week), **Emergency** (0.28) and **Environment** (0.23). The slowest with a stable
denominator are **Tourism** (0.05), **Culture** (0.065) and **Agriculture** (0.067). Finance and
Tech, the two largest areas, sit at 0.07 each **[measured]**. The pooled series falls from 0.56
cascades per instrument for the 2015 cohort to about 0.10-0.20 for 2018-2025 **[measured]**, and
the drop is a denominator effect: central promulgation counts triple at 2018 when several central
sites enter the corpus, while the implementing tier does not deepen at the same rate
**[inferred]**.

**Burstiness.** Weekly cascade counts are over-dispersed everywhere (Fano factor 1.2 to 3.8
against a Poisson value of 1). The burstiest substantive topic is **Government** (detrended CV
2.88, Fano 2.86); Environment has the single largest spike (34 cascades in the week of
2026-08-10, the 生态环境法典 implementation wave). Bursts align with the two campaign windows we
can date: Commerce's weekly cascade rate is 3.4x its baseline inside 2024-03 to 2024-12, with 7 of
its 12 burst weeks inside that window; Tech's rate is 1.9x baseline inside 2025-08 to 2026-06,
with 6 of its 26 burst weeks there **[measured]**. The 2013-17 window does not stand out: the
implementing rate per 1,000 sub-national documents is 108-173 across 2011-2017 with no 2013 step
**[measured]**. The pooled `all` bursts are mostly single-site publication batches, not
cross-site tempo (Guangzhou supplied 51 of 83 cascades in the 2023-01-02 week, Shenzhen 57 of 66
in 2020-03-09) **[measured]**, which is the main caveat on any burst detector run on raw counts.

**Lead-lag.** Across 10 topics and 90 ordered pairs at lags 1-12 weeks, 6 pairs beat a circular-
shift permutation null at p<0.05, against 4.5 expected by chance. One pair is clearly above the
null: a Tech burst leads an Education burst by 2 weeks (r=0.18 vs a null 95th percentile of 0.13;
0 of 200 permutations as large). The rest are at the chance rate. There is no general lead-lag
structure between areas in this record **[measured]**.

**Level decomposition.** Provinces supply 53% of all weekly cascades, cities 42%, districts 5%
over 2018-2026. In burst weeks the pooled mix flips to 42/54/4 because the big pooled bursts are
city batches. Within topics the province's share RISES in burst weeks for Tech (0.74 vs 0.59) and
Health (0.72 vs 0.65) and is unchanged for Finance, Government and Commerce **[measured]**. The
first implementing document of a central instrument is provincial for 67% of anchors with three or
more implementers, municipal for 31%, district for 2.5%; median lag provincial 415 days, municipal
541, district 670 **[measured]**. This is the province-before-city finding of `diffusion-atlas.md`
re-seen at weekly resolution.

**Verdict on B7.** The series is an instrument for burstiness and for level timing. It is not yet
an instrument for cross-area tempo comparison or for lead-lag, because (a) the anchor-cohort
yield is dominated by denominator composition and needs a fixed-site panel, (b) the topic tag is
the anchor's label, so a shared instrument double-counts across areas, and (c) the pooled bursts
are site batches. Two things would make it one: a per-week site-diversity gate on bursts, and a
year or two more of weeks at the current crawl cadence.

---

## 1. What a cascade event is, and what the weekly series counts

`diffusion_events` (built by `scripts/rnd/analysis/build_diffusion_events.py`) holds one row
per (sub-national document, central or provincial anchor) pair. `match_type` is `citation`
(resolved citation edge), `title_reissue` (localized reissue of the anchor's title stem) or
`topic_genre` (probable, unconfirmed). `source_implementing` is 1 when the local document's
`doc_identity.genre` is promulgation or implementing, 0 for readouts, explainers and news.
`lag_days` is the local publication date minus the anchor date. `anchor_level` is central or
provincial.

Everything in this memo uses the strict subset: `anchor_level='central'`,
`match_type IN ('citation','title_reissue')`, `source_implementing=1`, `lag_days>=0`. That is
13,081 events on 2026-10-07 (12,465 citation + 517 title_reissue in the pre-rebuild count; the
nightly added 99). Negative lags do not occur in this subset.

`tracker_weekly` (built by `scripts/build_tracker_rollup.py`) rolls these up per
(topic, ISO week, admin_level) by the week of the SOURCE document, under every topic of the
ANCHOR's `topics_algo` tags, plus a topic `all`. It is bounded to 2018-01-01 onward. The series
analysed here is rebuilt from `diffusion_events` with the same rules so that it can start in 2015
and so that one variant can use the anchor's FIRST tag only (for the lead-lag test, where
multi-label double counting would manufacture contemporaneous correlation).

**Two kinds of censoring.** The tracker's week-t count is the number of local implementing
documents published in week t that matched an anchor. It is censored by crawl latency (the
document must be crawled) and by resolution (the citation must resolve, ~52%). It is NOT censored
by lag: the anchor already exists. An anchor-cohort count (how many cascades instrument X has
produced) is censored by the lag distribution, and the lag distribution is long.

**Table 1. Lag distribution of confirmed implementing cascades (central anchors)** **[measured]**

| horizon after anchor | share of eventual events arrived |
|---|---:|
| 4 weeks | 0.022 |
| 8 weeks | 0.056 |
| 12 weeks | 0.088 |
| 26 weeks | 0.213 |
| 52 weeks | 0.414 |
| 104 weeks | 0.670 |

Median 473 days, interquartile range 212-874. By anchor year the 52-week share runs 0.27-0.50 for
2015-2024 cohorts with no trend; the 2025 cohort shows 0.78 and the 2026 cohort 1.00 because
their later arrivals have not happened yet. That is the censoring the correction in §2 removes.

**Table 2. Crawl latency of sub-national documents (source-week censoring)** **[measured]**

| universe | n | median days | p90 | within 7d | within 28d |
|---|---:|---:|---:|---:|---:|
| published 2026-01..09 | 34,206 | 4 | 128 | 0.55 | 0.69 |
| published since 2026-06, crawled since 2026-06 | 25,611 | 1 | 37 | 0.70 | 0.86 |

The second row is the steady-state nightly cadence. A week's cascade count is about 70% complete
after one week and 86% after four. Site-entry backfills (the first row's p90 of 128 days) add
events to old weeks long after the fact, which is why a burst detector on archived weeks must
control for site composition (§3).

---

## 2. Tempo: cascade yield per central instrument, 2015-2026

**Definition.** For anchors issued in year Y, tempo(Y) = implementing cascades arriving within
365 days of the anchor / central promulgations issued in Y. The denominator is independent of the
matcher: it is every `doc_identity` row with `admin_level_doc='central'`, `genre='promulgation'`
and `instrument_role IN ('canonical','unique')` (mirrors excluded), with `date_published` in Y.
Per topic, both numerator and denominator are restricted to documents carrying the topic in
`topics_algo` (anchor tags for the numerator). Dividing by 52 gives cascades per week per
instrument, the quantity B7 named. The normalization is what keeps a busier center from reading
as faster localities.

**Censoring correction** **[inferred]**. For a cohort whose instruments have had E days of
exposure (E<365), the visible share is F(E)/F(365) where F is the empirical lag CDF of Table 1.
Averaged over issue dates in the year, this is 0.97 for 2025 and 0.39 for 2026; 1.00 for all
earlier cohorts. Corrected yield = raw yield / visible share. The assumption is that the lag
distribution of recent cohorts matches the pooled one; Table 1's by-year row says the 52-week
share varies 0.27-0.50 across cohorts, so the 2026 correction carries about +/-30% uncertainty.

**Table 3. Pooled tempo by anchor cohort** **[measured]**

| cohort | central promulgations | anchors with >=1 event | events within 365d | raw yield | visible share | corrected yield | per week |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2015 | 800 | 120 | 446 | 0.557 | 1.00 | 0.557 | 0.0107 |
| 2016 | 1,409 | 138 | 478 | 0.339 | 1.00 | 0.339 | 0.0065 |
| 2017 | 850 | 121 | 348 | 0.409 | 1.00 | 0.409 | 0.0079 |
| 2018 | 2,690 | 100 | 278 | 0.103 | 1.00 | 0.103 | 0.0020 |
| 2019 | 2,322 | 101 | 378 | 0.163 | 1.00 | 0.163 | 0.0031 |
| 2020 | 2,617 | 88 | 275 | 0.105 | 1.00 | 0.105 | 0.0020 |
| 2021 | 2,321 | 165 | 431 | 0.186 | 1.00 | 0.186 | 0.0036 |
| 2022 | 1,922 | 109 | 268 | 0.139 | 1.00 | 0.139 | 0.0027 |
| 2023 | 1,890 | 73 | 176 | 0.093 | 1.00 | 0.093 | 0.0018 |
| 2024 | 2,985 | 124 | 501 | 0.168 | 1.00 | 0.168 | 0.0032 |
| 2025 | 1,595 | 110 | 339 | 0.213 | 0.97 | 0.218 | 0.0042 |
| 2026 | 2,050 | 99 | 297 | 0.145 | 0.39 | 0.371 | 0.0071 |

**Reading** **[reading]**. The 2015-17 cohorts yield 0.34-0.56 cascades per instrument; 2018-2025
yield 0.09-0.22. The step at 2018 is in the denominator (800-1,409 to 2,690 central promulgations)
not the numerator (events per year are flat at 270-500). Several central ministry sites enter
the corpus with 2018-onward archives, so the set of "central instruments" widens to include many
bureau-level notices that never cascade. The numerator depends on which implementing sites are
crawled and is roughly flat because the same Guangdong-heavy implementing tier is watched
throughout. A fixed-site panel on both sides (the `recentralization-experimentation.md` R2
construction) is required before any year-on-year tempo statement. Within 2018-2025 the series is
flat-to-rising (0.10 to 0.21), and 2024-2026 are the three highest post-2018 cohorts. The corrected
2026 value of 0.37 is the single number most likely to move: it rests on 39% visibility.

**Table 4. Tempo by topic, 2018-2025 cohorts pooled (denominator >= 300 central promulgations)**
**[measured]**

| topic | central promulgations | events within 365d (corrected) | yield per instrument | per week |
|---|---:|---:|---:|---:|
| Government | 411 | 290 | 0.706 | 0.0136 |
| Emergency | 320 | 89 | 0.278 | 0.0054 |
| Environment | 645 | 145 | 0.225 | 0.0043 |
| Commerce | 972 | 200 | 0.206 | 0.0040 |
| Personnel | 683 | 101 | 0.148 | 0.0028 |
| Welfare | 979 | 139 | 0.142 | 0.0027 |
| Health | 1,616 | 166 | 0.102 | 0.0020 |
| Legal | 1,121 | 112 | 0.099 | 0.0019 |
| Infrastructure | 934 | 82 | 0.088 | 0.0017 |
| Trade | 1,171 | 100 | 0.085 | 0.0016 |
| Safety | 1,003 | 84 | 0.084 | 0.0016 |
| Education | 1,235 | 98 | 0.079 | 0.0015 |
| Energy | 640 | 49 | 0.077 | 0.0015 |
| Tech | 1,779 | 132 | 0.074 | 0.0014 |
| Finance | 3,438 | 245 | 0.071 | 0.0014 |
| Transport | 1,327 | 94 | 0.071 | 0.0014 |
| Security | 427 | 30 | 0.071 | 0.0014 |
| Housing | 573 | 40 | 0.070 | 0.0013 |
| Agriculture | 1,548 | 104 | 0.067 | 0.0013 |
| Culture | 743 | 48 | 0.065 | 0.0012 |
| Tourism | 376 | 19 | 0.051 | 0.0010 |

Below the floor: Veterans (83 promulgations, 0.65), Diplomacy (114, 0.39), Credit (144, 0.14),
Sports (203, 0.025), Party (64, 0.03), Weather (66, 0.11). These are quoted for completeness and
not ranked.

**Reading** **[reading]**. Government leads by a factor of 2.5 over the next area. Its anchors are
procedural rules every jurisdiction must re-issue (政府信息公开条例, 行政规范性文件管理, 一件事一次办,
行政许可 adjustments). The high yield is a count of mandatory re-issuance, not of policy attention;
the two are different things and the instrument does not separate them. Emergency and Environment
are next because their anchors are framework laws with named local-implementation duties
(突发事件应对法, the 2026 生态环境法典). Finance and Tech, the areas with the most documents, have
the LOWEST yields among the large topics: many central notices, few that any locality re-issues.
Tech's within-year 2025 and 2026 cohorts (0.17 and 0.21) are the highest Tech has posted since
2016, consistent with the AI+ wave in `ai-plus-fidelity.md`. Commerce's 2024 cohort (0.54) is the
以旧换新 cascade and is the highest single topic-year value among the large topics.

**What tempo cannot see** **[caveat]**. It counts published implementing documents that cite or
re-title a central instrument. It does not see implementation that is unpublished, that cites
only the provincial relay (the province→city hop of `fidelity-provincial.md` lands in the
provincial-anchor column, excluded here), or whose citation did not resolve (~48% of edges). The
denominator counts every canonical central promulgation, including the many that carry no
implementation duty; a per-instrument "is this the kind of text that gets re-issued" filter
would raise every yield and change the ranking toward areas that issue few but binding texts.

---

## 3. Burstiness

**Series.** Weekly implementing cascades by source week, 2018-01-01 to 2026-09-28 (457 full weeks,
current partial week dropped), per topic under the anchor's full tag set (as the tracker counts).
Three statistics per topic: the Fano factor (variance/mean; 1 under Poisson), the coefficient of
variation of the raw series, and the CV of the series divided by its centered 53-week rolling mean
(detrended, so a slow rise does not read as bursts). A burst week is one at or above mean + 2 SD
and at least 3 events.

**Table 5. Burstiness by topic (mean >= 0.5 cascades/week)** **[measured]**

| topic | mean/week | Fano | CV raw | CV detrended | burst weeks | largest week |
|---|---:|---:|---:|---:|---:|---|
| all | 18.00 | 6.70 | 0.61 | 0.56 | 21 | 2023-01-02 (83) |
| Government | 1.43 | 2.86 | 1.41 | 2.88 | 20 | 2020-03-09 (15) |
| Finance | 1.59 | 1.88 | 1.09 | 1.15 | 20 | 2023-12-25 (10) |
| Environment | 1.19 | 3.84 | 1.80 | 1.30 | 8 | 2026-08-10 (34) |
| Health | 1.17 | 2.05 | 1.33 | 1.22 | 20 | 2021-12-27 (12) |
| Tech | 1.00 | 2.07 | 1.44 | 1.33 | 26 | 2026-08-03 (9) |
| Welfare | 0.96 | 1.44 | 1.23 | 1.23 | 18 | 2019-12-30 (8) |
| Agriculture | 0.80 | 1.47 | 1.36 | 1.41 | 38 | 2026-09-14 (7) |
| Legal | 0.77 | 2.07 | 1.64 | 1.75 | 18 | 2026-01-19 (10) |
| Safety | 0.77 | 1.58 | 1.44 | 1.48 | 36 | 2021-04-26 (5) |
| Education | 0.76 | 1.92 | 1.59 | 1.50 | 15 | 2026-09-21 (11) |
| Commerce | 0.70 | 2.45 | 1.87 | 1.49 | 12 | 2024-05-06 (16) |
| Infrastructure | 0.59 | 2.18 | 1.92 | 1.91 | 27 | 2022-04-25 (10) |
| Emergency | 0.58 | 2.48 | 2.07 | 1.97 | 32 | 2026-08-10 (11) |
| Personnel | 0.56 | 1.56 | 1.66 | 1.71 | 23 | 2020-03-09 (5) |
| Transport | 0.51 | 2.06 | 2.02 | 1.97 | 13 | 2023-01-02 (12) |

Sparse topics (mean under 0.5/week) have detrended CVs of 2.4-4.7 (Diplomacy 4.67, Veterans 3.87,
Military 3.70) because a series of mostly zeros is bursty by construction; they are not ranked.

**Reading** **[reading]**. Every topic is over-dispersed. Government is the burstiest area with a
real volume: its cascades arrive in waves when a procedural rule is re-issued across many
jurisdictions in the same fortnight (2020-03-09: 政府信息公开条例 re-issuances; 2020-12-28 and
2021-10-25 similar). Environment's Fano of 3.84 is one event: 34 cascades of the 生态环境法典 in
the week of 2026-08-10, 25 of them from one Shanxi prefecture (lvliang) and the national laws
database. Commerce's bursts are the 以旧换新 weeks of April-May 2024.

**Table 6. Campaign-window alignment** **[measured]**

| topic | window | burst weeks inside / total | cascade rate inside / outside | ratio |
|---|---|---:|---:|---:|
| Commerce | 以旧换新 2024-03..2024-12 | 7 / 12 | 1.91 / 0.57 per week | 3.36 |
| Commerce | AI+ 2025-08..2026-06 | 1 / 12 | 0.57 / 0.72 | 0.80 |
| Tech | AI+ 2025-08..2026-06 | 6 / 26 | 1.76 / 0.91 | 1.92 |
| Tech | 以旧换新 2024-03..2024-12 | 1 / 26 | 0.93 / 1.01 | 0.92 |
| Finance | 以旧换新 2024-03..2024-12 | 4 / 20 | 2.29 / 1.51 | 1.51 |
| Government | either window | 0 / 20 | 0.31 and 0.04 vs 1.56 | 0.20, 0.03 |
| all | 以旧换新 | 2 / 21 | 18.1 / 18.0 | 1.01 |
| all | AI+ | 1 / 21 | 19.7 / 17.8 | 1.11 |

Normalized per 1,000 sub-national new documents, Commerce runs 4.35 inside the 以旧换新 window vs
1.65 outside; Tech 3.30 inside the AI+ window vs 2.75 outside; `all` is LOWER inside both windows
(41 and 37 vs 52-54) because the sub-national document flow grows faster than cascades.

**Reading** **[reading]**. The two campaigns are visible in their own topic's series and nowhere
else. 以旧换新 is the sharper of the two (3.4x) because it was a single State Council 方案 with a
dated local-plan requirement, re-issued by 26 Guangdong cities within weeks. AI+ is broader and
slower (1.9x), consistent with the "authored elaboration" pattern in `ai-plus-fidelity.md`. The
pooled `all` series does not see either campaign: they are too small against the ~18 cascades per
week baseline. Government's cascades fall to near zero inside both windows, which is a denominator
artifact of the Government tag (8 to 13 central promulgations carried the tag in 2025-26 against
30 in 2024), not a tempo change.

**The 2013-17 window.** `tracker_weekly` does not reach it. From `diffusion_events` directly, the
implementing rate per 1,000 sub-national documents by source year is: 2011 152, 2012 141, 2013
108, 2014 115, 2015 150, 2016 173, 2017 144, 2018 112, then a monotone fall to 28 in 2026
**[measured]**. There is no 2013 step. The series is dominated by the growth of the sub-national
denominator (2,903 documents in 2011; 38,754 in 2026) as sites and news genres enter, which is
the same confound `recentralization-experimentation.md` handled with a continuous-coverage panel.
The recentralization finding there was a change in the upward SHARE of citations; the tempo of
confirmed implementing cascades, as counted here, does not carry that signal at annual resolution.

**The site-batch caveat** **[caveat]**. The largest pooled burst weeks are single-site publication
batches: 2023-01-02 (83 cascades; Guangzhou 51), 2020-03-09 (66; Shenzhen 57), 2026-08-10 (75;
lvliang 15 + npc 14 on one law). All carry `date_quality='good'`, so these are real publication
dates, but one portal posting its year-start or quarter-start batch on a Monday is not a
cross-jurisdiction tempo event. The topic-level bursts in Table 6 are cross-site (the 2024-05-06
Commerce week has Guangzhou 33 of about 50 but also Huizhou, Jiangsu, Xi'an, Chongqing). Any
production burst detector should require events from at least k distinct sites in the week.

---

## 4. Lead-lag between topics

**Design.** Ten topics with at least 150 cascades under the anchor's FIRST tag (Government,
Emergency, Environment, Commerce, Welfare, Health, Legal, Safety, Education, Tech). First-tag
series only, so no event is counted under two topics and lag-0 correlation is not manufactured by
shared anchors. Each series is detrended (ratio to its centered 53-week rolling mean) and
z-scored. For each ordered pair (A leads B) the cross-correlation at lags 1-12 weeks is computed
and the best lag kept. The null is 200 circular shifts of B by 20 to 437 weeks, taking the maximum
over the same 12 lags each time, so the null already accounts for picking the best lag. p is the
share of null maxima at or above the observed best.

**Table 7. Pairs with p < 0.05 (of 90 tested; 4.5 expected by chance)** **[measured]**

| leads | lags | best lag (weeks) | r at best lag | r at lag 0 | null 95th pct | p |
|---|---|---:|---:|---:|---:|---:|
| Tech | Education | 2 | 0.177 | -0.009 | 0.129 | 0.000 |
| Education | Safety | 12 | 0.123 | 0.037 | 0.118 | 0.020 |
| Legal | Emergency | 8 | 0.132 | 0.077 | 0.113 | 0.025 |
| Legal | Environment | 7 | 0.122 | 0.077 | 0.112 | 0.030 |
| Education | Environment | 8 | 0.124 | 0.024 | 0.122 | 0.040 |
| Environment | Welfare | 2 | 0.112 | 0.062 | 0.104 | 0.040 |

**Reading** **[reading]**. Six significant pairs against 4.5 expected is the chance rate. Five of
the six sit just above their null 95th percentile and would not survive any correction for 90
tests. One pair is clearly above the null: Tech leads Education by two weeks, with no lag-0
correlation at all (r=-0.01), so it is not a shared-anchor artifact. The content is plausible,
AI-in-education 方案 following AI+ 方案 by a fortnight in 2025-26 (the Education series' largest
week is 2026-09-21, two weeks after Tech's 2026-08-03 to 2026-09-07 run), but one pair in 90 is a
lead to follow, not a finding. The record has no general lead-lag structure between policy areas at
weekly resolution: bursts are topic-local responses to a topic-specific central instrument.

**What lead-lag cannot see** **[caveat]**. 457 weeks at ~1 event per week per topic is a short,
sparse series; r of 0.18 is about the ceiling detectable. Topic tags are anchor tags, so an
instrument spanning two areas appears under whichever tag is first in `topics_algo`. Cascades to
provincial anchors (the hop that carries text) are excluded.

---

## 5. Level decomposition: who moves first

**Long-run shares** **[measured]**. Of weekly central-anchor cascades 2018-2026, provinces supply
53.3%, cities 42.1%, districts 4.6%. (`source_level` is the site's level; the per-document
`admin_level_doc` would move a few npc rows but not the shares.)

**Table 8. Level mix in burst weeks vs long run** **[measured]**

| topic | burst weeks | burst-week share prov / muni / dist | long-run share prov / muni / dist |
|---|---:|---|---|
| all | 21 | 0.42 / 0.54 / 0.04 | 0.53 / 0.42 / 0.05 |
| Finance | 20 | 0.62 / 0.32 / 0.06 | 0.61 / 0.32 / 0.07 |
| Government | 20 | 0.50 / 0.49 / 0.01 | 0.51 / 0.44 / 0.05 |
| Commerce | 12 | 0.52 / 0.48 / 0.00 | 0.54 / 0.43 / 0.03 |
| Tech | 26 | 0.74 / 0.19 / 0.06 | 0.59 / 0.33 / 0.08 |
| Health | 20 | 0.72 / 0.27 / 0.01 | 0.65 / 0.34 / 0.01 |
| Environment | 8 | 0.45 / 0.50 / 0.05 | 0.56 / 0.41 / 0.03 |

**First mover per instrument** **[measured]**. For 649 central anchors issued 2018 or later with at
least three implementing events, the earliest implementing document is provincial for 66.7%,
municipal for 30.8%, district for 2.5%. Median lag of all implementing events: provincial 415 days
(n=3,125), municipal 541 (n=2,563), district 670 (n=287).

**Reading** **[reading]**. The province moves first by instrument, two to one, and provincial
documents arrive about four months before municipal ones. In burst weeks the province's share
rises for the campaign-shaped areas (Tech +15 points, Health +7) and is flat for the procedural and
fiscal areas (Government, Finance, Commerce). The pooled `all` flip toward cities is the site-batch
effect of §3: the biggest pooled weeks are Guangzhou and Shenzhen batches. Within a burst week the
earliest-dated document is municipal or district in 20 of 21 pooled burst weeks, but that measures
which portal posts on Monday, not who acts first; ties on the week's first day are common and the
measure is not reliable at day resolution.

This is `diffusion-atlas.md` §2 (province before city in 68-76% of nested pairs) and
`fidelity-jiangsu.md` (82%) re-seen from the weekly series, and the three agree.

---

## 6. What the instrument can and cannot see

- **Published face only.** A cascade is a published local document that cites or re-titles a
  central text. Implementation that is not published, or is published without a citation, is
  invisible. Publication date is not adoption date.
- **Right-censoring.** A week's count is ~70% complete after one week and ~86% after four (Table
  2); an instrument's cascade yield is 9% complete at 12 weeks and 41% at a year (Table 1). The
  tracker should show recent weeks as floors and should never report a per-instrument yield for an
  anchor under two years old without the correction in §2.
- **Topic tags are the anchor's tags.** `diffusion_events.topic` stores the anchor's first tag;
  the rollup uses the anchor's full tag set. Both label the cascade by what the center called it,
  not by what the locality did. ~36% of documents have no tag at all.
- **Denominator composition.** Central promulgation counts triple at 2018 as sites enter. No
  cross-year tempo statement is safe without a fixed-site panel on both the anchor and the
  implementing side.
- **Site batches.** The pooled weekly series is driven by single-portal publication batches.
  Topic-level series are better behaved. A site-diversity gate (events from >= k sites) is the
  one change that would make the burst detector usable in production.
- **Resolution and coverage.** ~52% of citation edges resolve; the implementing tier is
  Guangdong-heavy plus Jiangsu, Beijing, Shanghai, Chongqing, Wuhan, Suzhou. Every count is a
  floor and "who moved" is a floor.
- **Provincial anchors excluded.** The province→city hop (`cascade_events_prov`, 1,797 events
  since 2018) is where text actually travels. It is not in any series here and should be the next
  layer.
- **Scope.** Mechanism-level statements about a document record. No regime-type labels.

---

## 7. Appendix: reproduction

One read-only Python pass over `file:documents.db?mode=ro` on the droplet (about 4 minutes, pure
Python, seed 7; the lead-lag permutation is the slow part). The SQL for the core aggregates:

```sql
-- History depth: weeks with non-zero central cascades per topic (tracker_weekly)
SELECT topic,
       COUNT(DISTINCT CASE WHEN cascade_events > 0 THEN iso_week END) AS weeks_nonzero,
       SUM(cascade_events) AS cascades,
       MIN(CASE WHEN cascade_events > 0 THEN iso_week END) AS first_wk,
       MAX(CASE WHEN cascade_events > 0 THEN iso_week END) AS last_wk
FROM tracker_weekly
WHERE week_start <= date('now')
GROUP BY topic ORDER BY cascades DESC;

-- The strict event subset used throughout
-- (central anchors, confirmed match, implementing source, non-negative lag)
SELECT e.anchor_id, e.source_id, substr(e.anchor_date,1,10), substr(e.source_date,1,10),
       e.lag_days, e.source_level, e.topic, d.topics_algo
FROM diffusion_events e LEFT JOIN documents d ON d.id = e.anchor_id
WHERE e.anchor_level = 'central' AND e.source_implementing = 1
  AND e.match_type IN ('citation','title_reissue') AND e.lag_days >= 0;

-- Lag CDF (Table 1): share arrived within h days
SELECT AVG(lag_days <= 28), AVG(lag_days <= 56), AVG(lag_days <= 84),
       AVG(lag_days <= 182), AVG(lag_days <= 365), AVG(lag_days <= 730)
FROM diffusion_events
WHERE anchor_level = 'central' AND source_implementing = 1
  AND match_type IN ('citation','title_reissue') AND lag_days >= 0;

-- Crawl latency (Table 2, steady-state row)
SELECT julianday(substr(d.crawl_timestamp,1,10)) - julianday(substr(d.date_published,1,10)) AS lat
FROM documents d JOIN sites s ON s.site_key = d.site_key
WHERE s.admin_level IN ('provincial','municipal','district')
  AND d.date_published >= '2026-06-01' AND d.crawl_timestamp >= '2026-06-01';

-- Tempo denominator (Table 3/4): canonical central promulgations per year (and per topic
-- after exploding topics_algo on commas, as in attention-campaigns.md Appendix)
SELECT substr(d.date_published,1,4) AS yr, COUNT(*)
FROM documents d JOIN doc_identity i ON i.doc_id = d.id
WHERE i.admin_level_doc = 'central' AND i.genre = 'promulgation'
  AND i.instrument_role IN ('canonical','unique')
  AND yr BETWEEN '2015' AND '2026'
GROUP BY yr;

-- Tempo numerator: events within 365 days by anchor year
SELECT substr(anchor_date,1,4) AS yr, COUNT(*), COUNT(DISTINCT anchor_id)
FROM diffusion_events
WHERE anchor_level = 'central' AND source_implementing = 1
  AND match_type IN ('citation','title_reissue')
  AND lag_days BETWEEN 0 AND 365 AND yr BETWEEN '2015' AND '2026'
GROUP BY yr;
-- corrected yield = numerator / denominator / visible_share(yr),
-- visible_share = mean over issue weeks of F(min(365, today - issue_date)) / F(365)

-- Weekly series by source week and level (the series behind Tables 5-8); the
-- Python pass splits d.topics_algo of the ANCHOR and counts the event once per tag
SELECT strftime('%Y-%W', substr(e.source_date,1,10)) AS wk, e.source_level, COUNT(*)
FROM diffusion_events e
WHERE e.anchor_level = 'central' AND e.source_implementing = 1
  AND e.match_type IN ('citation','title_reissue') AND e.lag_days >= 0
  AND e.source_date >= '2018-01-01'
GROUP BY wk, e.source_level;

-- Site composition of one burst week (the site-batch check in §3)
SELECT d.site_key, i.date_quality, COUNT(*)
FROM diffusion_events e JOIN documents d ON d.id = e.source_id
LEFT JOIN doc_identity i ON i.doc_id = d.id
WHERE e.anchor_level = 'central' AND e.source_implementing = 1
  AND e.match_type IN ('citation','title_reissue')
  AND substr(e.source_date,1,10) BETWEEN '2023-01-02' AND '2023-01-08'
GROUP BY 1, 2 ORDER BY 3 DESC;

-- First mover per anchor (§5): level of the earliest implementing event
WITH ev AS (
  SELECT anchor_id, source_level, lag_days,
         ROW_NUMBER() OVER (PARTITION BY anchor_id ORDER BY lag_days, source_id) AS rn,
         COUNT(*) OVER (PARTITION BY anchor_id) AS n
  FROM diffusion_events
  WHERE anchor_level = 'central' AND source_implementing = 1
    AND match_type IN ('citation','title_reissue') AND lag_days >= 0
    AND anchor_date >= '2018-01-01')
SELECT source_level, COUNT(*) FROM ev WHERE rn = 1 AND n >= 3 GROUP BY 1;
```

Statistics computed offline in Python: Fano = population variance / mean; CV = population SD /
mean; detrending = ratio to a centered 53-week rolling mean; burst week = count >= mean + 2 SD and
>= 3; cross-correlation on z-scored detrended series with a 200-draw circular-shift null (shift
between 20 and n-20 weeks, maximum over lags 1-12 per draw).
