# Wuxi: The Second Jiangsu Prefecture, and the End of B1

*A replication on the china-governance corpus (SQLite on the droplet). All figures pulled
read-only on 2026-10-08, after the Wuxi merge of 2026-10-08 (`wuxi` plus seven `wxd_*` district
sites, 4,877 documents live). Answers the question `corpus-lessons.md` B1 asked and
`fidelity-jiangsu.md` could not close: the nested central-province-city findings held on Jiangsu,
but Suzhou supplied 89% of Jiangsu's city documents and 92% of its city pairs, so Jiangsu's
agreement was one city's agreement. Wuxi is the second non-Suzhou Jiangsu prefecture at
comparable depth. This memo runs the same three measures on three city sets separately, never
pooling Jiangsu into one number, and adds a per-city control that the earlier memos could not
run. SQL and the sketch are in the appendix.*

---

## 0. The question and the short answer

**Question.** Does the Guangdong result hold on a second Jiangsu city, or was Suzhou carrying it?
Three verdicts were available: *discharged*, *Suzhou-specific*, or *still underpowered*.

**Short answer: discharged.** [measured] Wuxi supports the test at Suzhou's scale or above (397
province-to-city pairs, 195 nested central-anchor pairs, 152 full chains, against Suzhou's 551,
144 and 97), and all three findings replicate on it.

| finding | Guangdong cities | Suzhou | Wuxi |
|---|---:|---:|---:|
| province echoes before the city | 68.2% of 1,046 | 69.4% of 144 | **83.6% of 195** |
| city text closer to province than to centre | 91.6% of 3,352 | 96.9% of 97 | **94.1% of 152** |
| city-to-province median overlap (union basis) | 0.097 | 0.054 | **0.115** |
| relay share (union basis) | 9.9% | 4.3% | **5.3%** |

**And one correction that the second city makes possible.** The `fidelity-jiangsu.md` headline
difference, Jiangsu relay 3.3% against Guangdong 10.8%, is **not** a provincial fact. It is a
composition artefact of which cities each province contributes. Measured per city, the Guangdong
relay rate runs from 2.2% (广州) to 18.4% (阳江), median 8.9% over the 13 city portals with 50 or
more scored pairs. Suzhou (4.3%) and Wuxi (5.3%) both land inside that spread, at and just below
its first quartile, next to 广州 and 深圳 rather than outside the distribution. Both are large,
rich prefectures, and in Guangdong the large rich prefectures are also the ones that relay least
(广州 2.2%, 深圳 4.5%, 中山 5.6% against 阳江 18.4%, 揭阳 15.9%, 汕尾 15.4%). The province-level
comparison in the earlier memos averaged over 15 Guangdong cities of very different size and over
one Jiangsu city, so it read a city-level gradient as a provincial difference. [measured for the
spread and the ordering; inferred for size as the mechanism, since the repo holds provincial GDP
only, `data/provincial_gdp.csv`]

**The same control places Wuxi.** On province-before-city Wuxi's 83.6% is **exactly** the
Guangdong per-city median (83.6%, 13 cities with 40 or more nested pairs, range 61.7 to 90.0).
Suzhou's 69.4% sits below the Guangdong first quartile. Wuxi is the more typical city of the two.
[measured]

---

## 1. Method

Identical to `fidelity-jiangsu.md` §1 and `fidelity-provincial.md` §1, with the pair set and the
5-gram scoring taken from `scripts/rnd/analysis/pairs.py` rather than from a memo-era sketch, so
the measures are the ones those memos used.

**One operational difference, and it matters.** The nightly holds the write lock until roughly
10:00 UTC on 2026-10-09 (Phase 2, 23,710 documents to classify), so the live derived layers
predate the Wuxi merge: 8,099 documents have no `doc_identity` row, including about 4,747 of the
4,877 `wuxi`/`wxd_*` rows, only 110 of them appear in `citations`, and 58 in `diffusion_events`.
Measuring Wuxi off those tables would have measured the merge, not the city. So all three derived
layers were **recomputed read-only** into scratch files and attached beside the live DB:

| layer | how | result |
|---|---|---|
| `doc_identity` | `build_doc_identity.build(conn)` on a `?mode=ro` connection, `write()` never called | 346,955 rows, 112 s |
| `citations` | the lookup tables, `TitleMatcher` and the three tiers imported from `extract_citations`, document loop streamed instead of `fetchall()` so 640 MB of bodies fit beside the classifier | 625,227 edges, 327,629 resolved (52.40%), 756 s |
| `diffusion_events` | `build_diffusion_events`' own no-`--write` pipeline against the shim | 49,576 rows (34,952 implementing) |

Nothing was written to `documents.db`. The shim is an in-memory main database with
`documents`/`sites`/`doc_issuers`/`citations` as TEMP views over the attachments and
`doc_identity`/`diffusion_events` as real tables in main, because both builders probe
`sqlite_master` for `type='table'`. Live counts for comparison: 585,471 edges / 310,136 resolved,
45,524 events. The deltas are the 8,099 identity-less documents plus a day of crawling.

**Consistency check against the published memo.** On this fresh layer Suzhou's citation-basis
province-to-city pair set is 507 pairs / 426 scored / relay 3.5%. `fidelity-provincial.md` §2.2
reports 473 / 426 / 3.3% on the redated live DB. Same scored n, relay within 0.2 points. The
pipeline reproduces the number it should. [measured]

**City sets.** Reported separately throughout, never pooled: `gd_city` (Guangdong city portals),
`gd_dist` (Guangdong district sites, overwhelmingly Shenzhen's), `gd_dept` (the 13 Shenzhen
bureaus), `suzhou`, `suzhou_dist` (`szd_*`), `wuxi`, `wuxi_dist` (`wxd_*`), and the four shallow
other-Jiangsu portals. Level from `doc_identity.admin_level_doc`, province from
`doc_identity.province` falling back to `build_diffusion_events.province_of`, unit from the site
type, exactly as in `fidelity-jiangsu.md` §1.

---

## 2. What Wuxi actually supports

**Table 2a. Documents by city set, fresh identity layer.**

| set | documents | body > 500 | share |
|---|---:|---:|---:|
| gd_city (15 portals) | 53,985 | 41,733 | 77.3% |
| gd_dist | 22,510 | 11,820 | 52.5% |
| gd_dept (Shenzhen bureaus) | 33,619 | 12,577 | 37.4% |
| suzhou | 4,919 | 2,635 | 53.6% |
| suzhou_dist (5 sites) | 362 | 255 | 70.4% |
| **wuxi** | **2,206** | **1,678** | **76.1%** |
| **wuxi_dist (7 sites)** | **2,603** | **2,175** | **83.6%** |
| js_other_city (南京/盐城/泰州) | 477 | 411 | 86.2% |
| js_other_dist (`njd_*`) | 626 | 286 | 45.7% |

Wuxi city is 45% of Suzhou's document count and 64% of its documents with a usable body, because
Wuxi's body coverage is 76.1% against Suzhou's 53.6%. Per document it yields **more** pairs than
Suzhou (0.180 against 0.112), so the two cities' pair sets are the same order of magnitude from
very different document counts. [measured]

**Table 2b. Per-site detail, with the levels the identity layer assigns.**

| site | documents | municipal | district | other | body > 500 | span |
|---|---:|---:|---:|---:|---:|---|
| wuxi | 2,209 | 2,200 | 6 | 3 central | 1,681 | 1993-05 to 2026-09 |
| wxd_xinwu | 1,087 | 18 | 1,008 | 34 central, 27 prov | 951 | 2015-12 to 2026-09 |
| wxd_jiangyin | 756 | 1 | 755 | | 586 | 2011-12 to 2023-10 |
| wxd_xishan | 450 | | 447 | 3 | 408 | 2012-09 to 2026-09 |
| wxd_liangxi | 209 | | 208 | 1 central | 151 | 2016-08 to 2026-07 |
| wxd_binhu | 83 | | 83 | | 75 | 2017-01 to 2026-07 |
| wxd_huishan | 47 | 22 | 25 | | 45 | 2011-10 to 2026-08 |
| wxd_yixing | 36 | 7 | 29 | | 19 | 2018-06 to 2026-08 |

Year quartiles of Wuxi city documents: Q1 2015, median 2022, Q3 2023 (Suzhou 2015 / 2018 / 2021).
Wuxi is the more recent series; Suzhou reaches further back in the middle of its distribution.

**Table 2c. Pairs Wuxi contributes.**

| measure | Wuxi city | Wuxi districts | Suzhou | Suzhou districts | GD cities |
|---|---:|---:|---:|---:|---:|
| province-to-city pairs (union) | **397** | 14 | 551 | 11 | 10,542 |
| of those scored (both bodies > 500) | **243** | 4 | 437 | 7 | 5,895 |
| city-to-district pairs (union) | | **309** | | 50 | 2,604 (GD districts) |
| of those scored | | **227** | | 22 | 1,516 |
| nested central-anchor pairs vs the province | **195** | 276 | 144 | 7 | 1,046 |
| full centre-province-city chains | **152** | 1 | 97 | 1 | 3,352 |
| confirmed central-anchor events, this set as source | 513 | 1,293 | 544 | 61 | 8,775 |

**Wuxi has enough pairs to test all three findings.** [measured] On the nested test it has 35%
more pairs than Suzhou (195 against 144) and 57% more chains (152 against 97); on fidelity it has
28% fewer scored pairs (243 against 437) but enough for a median, a band split and a lag
gradient. The `wxd_*` districts are thin against the province (14 pairs) but **not** thin against
their own city (309 pairs, 227 scored), which is a hop Jiangsu previously could not measure at
all. §7.

**Dates are trustworthy.** All 4,877 rows read `date_quality='good'` and here that is earned,
unlike Suzhou's pre-repair state. Every row carries a `/doc/YYYY/MM/DD/` URL path, and the path's
year-month disagrees with `date_published` on exactly **1** row. 文号 year agrees with the
publication year on 2,590 of the 2,761 rows that carry a 文号 (93.8%); the 171 that disagree are
the ordinary shapes, a document numbered in one year and published in January of the next
(锡政办规〔2024〕9号 published 2025-01-14) or an old instrument reposted
(锡政发〔1997〕117号 on a 2013 page). No day pile exceeds 32 documents. There is nothing here like
the Suzhou page-regeneration stamping, and no date repair is applied to any Wuxi figure in this
memo. [measured]

---

## 3. Finding 1: the province echoes before the city

Same test as `diffusion-atlas.md` §2d and `fidelity-jiangsu.md` §3: confirmed central-anchor
`diffusion_events` (match_type citation or title_reissue), keyed on (anchor, province), first
provincial-source lag against the first lag from the city set.

**Table 3a. Nested paired test.**

| set | cut | n | province first | prov median lag | sub median lag | gap median | gap IQR |
|---|---|---:|---:|---:|---:|---:|---|
| GD cities | confirmed | 1,046 | **68.2%** | 190 | 260 | 63 | −53 to 211 |
| GD cities | implementing | 951 | 72.2% | 200 | 281 | 78 | −22 to 233 |
| GD cities | anchors 2015+ | 713 | 65.9% | 191 | 263 | 64 | −57 to 203 |
| GD cities | both ≤ 365 d | 577 | 69.7% | 109 | 159 | 35 | −16 to 99 |
| Suzhou | confirmed | 144 | **69.4%** | 214 | 422 | 117 | −28 to 308 |
| Suzhou | implementing | 135 | 71.9% | 218 | 432 | 130 | −25 to 308 |
| Suzhou | anchors 2015+ | 115 | 68.7% | 230 | 430 | 93 | −44 to 274 |
| Suzhou | both ≤ 365 d | 55 | 60.0% | 133 | 189 | 29 | −44 to 93 |
| **Wuxi** | confirmed | 195 | **83.6%** | 201 | 436 | 176 | 47 to 364 |
| **Wuxi** | implementing | 180 | 85.0% | 201 | 427 | 198 | 54 to 365 |
| **Wuxi** | anchors 2015+ | 146 | 83.6% | 212 | 400 | 160 | 44 to 346 |
| **Wuxi** | both ≤ 365 d | 72 | 84.7% | 114 | 184 | 80 | 22 to 133 |
| Wuxi districts | confirmed | 276 | 63.4% | 250 | 372 | 110 | −95 to 336 |
| GD districts | confirmed | 205 | 70.7% | 160 | 371 | 161 | −26 to 546 |
| GD bureaus | confirmed | 303 | 64.0% | 219 | 377 | 100 | −96 to 406 |

**Province-before-city holds on Wuxi, and holds harder than on Suzhou or on the Guangdong
average.** [measured] Every Wuxi cut sits between 83.6% and 85.0%, including the 365-day window
where Suzhou falls to 60.0% on 55 pairs. Wuxi is the only one of the three sets whose gap IQR
does not cross zero: in Wuxi the city is behind the province in at least three quarters of nested
pairs, not merely in most of them.

The `fidelity-jiangsu.md` §6 lesson, that the province-first share rises as fewer cities are
watched, does not explain the Wuxi-Suzhou difference, because both are single cities measured
the same way. §6 below places both inside the Guangdong per-city distribution instead. [measured]

---

## 4. Finding 2: does the city's text descend from the province or from the centre?

For every scored province-to-city pair whose provincial document is itself a confirmed source on
a central anchor with a body over 500 characters: ovlp(M,P), ovlp(M,C), ovlp(P,C), and the
partition of the city document's 5-grams into those in both P and C, in P only, and in C only.

**Table 4a. Centre-province-city chains.**

| statistic | GD cities | Suzhou | **Wuxi** | GD districts | GD bureaus |
|---|---:|---:|---:|---:|---:|
| chains | 3,352 | 97 | **152** | 15 | 272 |
| **city closer to province than to centre** | **91.6%** | **96.9%** | **94.1%** | 93.3% | 85.3% |
| ovlp(M,P) median | 0.245 | 0.473 | 0.270 | 0.040 | 0.045 |
| ovlp(M,C) median | 0.081 | 0.135 | 0.090 | 0.016 | 0.023 |
| ovlp(P,C) median | 0.213 | 0.306 | 0.199 | 0.116 | 0.120 |
| city grams in both P and C | 0.058 | 0.108 | 0.059 | 0.011 | 0.012 |
| city grams in P only | **0.138** | 0.211 | **0.160** | 0.030 | 0.030 |
| city grams in C only | **0.009** | 0.014 | **0.014** | 0.005 | 0.007 |
| province-descended (P-only ≥ 2 × C-only) | 82.2% | 86.6% | 77.0% | 80.0% | 66.9% |
| centre-descended (C-only ≥ 2 × P-only) | 3.1% | 0.0% | 2.6% | 0.0% | 6.6% |
| locally authored (both < 0.1) | 42.9% | 32.0% | 30.9% | 100.0% | 81.6% |

**The city descends from the province in Wuxi as in Guangdong and as in Suzhou.** [measured]
Centre-only text is 1.4% of the Wuxi document at the median against 16.0% province-only, a ratio
of eleven to one. The three city sets agree to within 5 points on the headline share and the
earlier memos' 92.8% sits between Wuxi's 94.1% and Guangdong's 91.6%.

**Worked Wuxi chains.** [measured] The top of the distribution is the two-hop relay the provincial
memo described, with the centre's text arriving entirely through the provincial copy.

| C (国务院/办公厅) | P (江苏省政府/办公厅) | ovlp(P,C) | M (无锡市政府/办公室) | ovlp(M,P) | ovlp(M,C) | C-only |
|---|---|---:|---|---:|---:|---:|
| 健全重特大疾病医疗保险和救助制度的意见 (2021-11) | 实施意见 (2022-07) | 0.64 | 实施意见 (2022-12) | 0.82 | 0.55 | 0.003 |
| 打赢蓝天保卫战三年行动计划 (2018-07) | 江苏省…实施方案 (2018-10) | 0.39 | 无锡市…实施方案 (2018-12) | 0.81 | 0.36 | 0.005 |
| 强化危险废物监管和利用处置能力改革实施方案 (2021-05) | 江苏省…实施方案 (2022-01) | 0.37 | 无锡市…实施方案 (2022-08) | 0.80 | 0.33 | 0.002 |
| 深化农村公路管理养护体制改革的意见 (2019-09) | 实施方案 (2020-06) | 0.38 | 无锡市…实施方案 (2020-12) | 0.79 | 0.34 | 0.002 |
| 新污染物治理行动方案 (2022-05) | 江苏省…工作方案 (2022-12) | 0.49 | 无锡市…工作实施方案 (2023-07) | 0.76 | 0.46 | 0.013 |
| 建立健全职工基本医疗保险门诊共济保障机制的指导意见 (2021-04) | 实施意见 (2021-12) | 0.48 | 实施方案 (2022-12) | 0.75 | 0.41 | 0.002 |

Every row is the same shape: the province keeps 37 to 64% of the central text, the city keeps 75
to 82% of the province's, and what reaches the city from the centre is a subset of what the
province kept (C-only 0.002 to 0.013). This is `fidelity-provincial.md` §4.2 on a third city set.

---

## 5. Finding 3: city-to-province fidelity

**Table 5a. Province-to-city pairs, both bases.** Relay > 0.7, mid 0.3 to 0.7, elaboration < 0.3
on `ovlp_src`, the share of the city document's 5-grams present in the provincial document.

| set | basis | pairs | scored | median | relay% | mid% | elab% | n relay | Q1 | Q3 | median lag |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| gd_city | citation | 10,062 | 5,671 | 0.093 | 9.7 | 19.4 | 70.9 | 549 | 0.033 | 0.377 | 505 |
| gd_city | union | 10,542 | 5,895 | 0.097 | 9.9 | 19.7 | 70.4 | 582 | 0.034 | 0.385 | 500 |
| suzhou | citation | 507 | 426 | 0.053 | 3.5 | 12.0 | 84.5 | 15 | 0.042 | 0.089 | 738 |
| suzhou | union | 551 | 437 | 0.054 | 4.3 | 12.4 | 83.3 | 19 | 0.042 | 0.100 | 738 |
| **wuxi** | citation | 385 | 240 | 0.114 | 5.0 | 18.3 | 76.7 | 12 | 0.065 | 0.272 | 446 |
| **wuxi** | union | 397 | 243 | **0.115** | **5.3** | **18.5** | 76.1 | 13 | 0.065 | 0.279 | 459 |
| gd_dist | union | 31 | 19 | 0.041 | 0.0 | 0.0 | 100.0 | 0 | | | 762 |
| gd_dept | union | 1,271 | 698 | 0.037 | 0.9 | 5.4 | 93.7 | 6 | | | 2,451 |
| suzhou_dist | union | 11 | 7 | 0.065 | 0.0 | 42.9 | 57.1 | 0 | | | 606 |
| wuxi_dist | union | 14 | 4 | 0.458 | 50.0 | 0.0 | 50.0 | 2 | | | 297 |
| js_other_city | union | 43 | 11 | 0.086 | 0.0 | 9.1 | 90.9 | 0 | | | 203 |

**Wuxi's distribution is the Guangdong city distribution, not Suzhou's.** [measured] Its median
(0.115) is above the Guangdong pooled median (0.097) and twice Suzhou's (0.054); its mid band
(18.5%) is within 1.2 points of Guangdong's (19.7%) and half again Suzhou's (12.4%). Its relay
share (5.3%) is between Suzhou's (4.3%) and Guangdong's (9.9%). Three statistics, three
positions: Wuxi is not a copy of Suzhou, and the one statistic on which the two Jiangsu cities
agree against Guangdong is the relay share, which §6 shows is a city-level and not a provincial
quantity.

The union basis moves little anywhere (Wuxi +12 pairs, +0.3 relay points; Suzhou +44 pairs, +0.8
points; Guangdong +480 pairs, +0.2 points), consistent with `pair-channels.md`: the citation-only
figures are floors by about 0.2 relay points once metadata-only sources are excluded.

**Table 5b. Cuts, union basis.**

| set | cut | pairs | scored | median | relay% |
|---|---|---:|---:|---:|---:|
| gd_city | all | 10,542 | 5,895 | 0.097 | 9.9 |
| gd_city | implementing | 9,131 | 5,298 | 0.121 | 10.9 |
| gd_city | 转发 excluded | 9,933 | 5,493 | 0.090 | 8.5 |
| gd_city | 转发 only | 609 | 402 | 0.235 | 28.1 |
| suzhou | all | 551 | 437 | 0.054 | 4.3 |
| suzhou | implementing | 332 | 221 | 0.098 | 8.6 |
| suzhou | 转发 excluded | 521 | 419 | 0.053 | 4.1 |
| **wuxi** | all | 397 | 243 | 0.115 | 5.3 |
| **wuxi** | implementing | 349 | 211 | 0.133 | 6.2 |
| **wuxi** | 转发 excluded | 390 | 239 | 0.115 | 5.0 |

Forwarding is 5.8% of Guangdong city pairs and carries 28.1% relay; it is 1.8% of Wuxi's and 5.4%
of Suzhou's. Excluding it, the three sets read 8.5 / 4.1 / 5.0. The Guangdong-Jiangsu relay gap
narrows but does not close on this cut, and on the implementing subset it narrows further
(10.9 / 8.6 / 6.2). The gap is therefore partly 转发 composition and partly genre composition, not
a single effect. [measured]

**Table 5c. Fidelity by lag, union basis.**

| lag from the provincial instrument | GD n | GD median | GD relay | SZ n | SZ median | SZ relay | WX n | WX median | WX relay |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ≤ 30 d | 152 | 0.519 | 38.2% | 10 | 0.413 | 30.0% | 8 | 0.216 | 12.5% |
| 31 to 90 d | 475 | 0.412 | 25.9% | 25 | 0.391 | 16.0% | 22 | 0.172 | 9.1% |
| 91 to 365 d | 1,829 | 0.262 | 15.6% | 57 | 0.434 | 19.3% | 83 | 0.247 | 10.8% |
| 1 to 3 y | 1,567 | 0.074 | 5.9% | 246 | 0.049 | 0.4% | 64 | 0.098 | 1.6% |
| > 3 y | 1,872 | 0.046 | 1.3% | 99 | 0.045 | 0.0% | 66 | 0.101 | 0.0% |

Lag is the dominant predictor in all three sets and the ordering is monotone in all three. Wuxi's
gradient is flatter at the short end (0.216 at 30 days against Guangdong's 0.519), on 8 pairs,
which is not a difference to lean on; its relay peak sits in the 91-to-365-day band, like
Suzhou's.

**What the relay band contains.** [measured] 13 Wuxi relays, of which **12 (92.3%) are
own-masthead city instruments** reproducing the provincial body, 1 is a 转发 notice, 0 are
verbatim mirrors; median lag **185 days**. Suzhou: 19 relays, 17 own-masthead (89.5%), 2 转发,
median lag 142 days. Guangdong (`fidelity-provincial.md`): 79.5% own-masthead, median 152 days.
The object is the same in all three.

The Wuxi head of the band:

| ovlp | lag | M (无锡) | P (江苏省) |
|---:|---:|---|---|
| 0.85 | 186 d | 市政府办公室关于加强全市农村道路交通安全工作的意见 | 省政府办公厅关于加强农村道路交通安全工作的意见 |
| 0.83 | 199 d | 市政府关于印发无锡市见义勇为称号评定实施办法的通知 | 省政府关于印发江苏省见义勇为称号评定实施办法的通知 |
| 0.82 | 161 d | 市政府办公室关于健全重特大疾病医疗保险和救助制度的实施意见 | 省政府办公厅…实施意见 |
| 0.81 | 14 d | 市政府办公室关于印发无锡市危险化学品安全综合治理实施方案的通知 | 省政府办公厅…江苏省…方案 |
| 0.81 | 64 d | 市政府关于印发无锡市打赢蓝天保卫战三年行动计划实施方案的通知 | 省政府…江苏省…实施方案 |
| 0.80 | 185 d | 市政府办公室关于印发无锡市强化危险废物监管和利用处置能力改革实施方案的通知 | 省政府办公厅…江苏省…实施方案 |

A 市政府办公室 notice reproducing the 省政府办公厅 notice with 江苏省 replaced by 无锡市, six
months later, under Wuxi's own masthead. Renamed re-issuance at half a year is a Wuxi practice as
it is a Suzhou practice and a 揭阳/阳江/江门 practice. [measured]

---

## 6. The per-city control, and what it does to the provincial claim

The earlier memos compared a province to a province. With two Jiangsu cities and fifteen
Guangdong ones, the comparison can be made city to city instead, which is the level at which the
measures are actually defined.

**Table 6a. Every city portal in Guangdong and Jiangsu, province-to-city pairs.**

| site | prov | pairs | scored | median | relay% | mid% | nested n | prov first | chains | closer to P |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| zhongshan | gd | 2,257 | 483 | 0.111 | 5.6 | 24.6 | 250 | 87.2% | 266 | 87.6% |
| jiangmen | gd | 1,253 | 779 | 0.115 | 10.4 | 18.7 | 338 | 83.1% | 422 | 92.9% |
| jieyang | gd | 1,099 | 773 | 0.088 | 15.9 | 18.2 | 280 | 81.4% | 441 | 95.0% |
| gz (广州) | gd | 877 | 578 | 0.069 | **2.2** | 16.4 | 396 | 78.3% | 324 | 83.6% |
| huizhou | gd | 866 | 628 | 0.120 | 11.8 | 21.0 | 293 | 83.6% | 331 | 96.4% |
| yangjiang | gd | 838 | 494 | 0.169 | **18.4** | 23.3 | 260 | 90.0% | 349 | 95.1% |
| sz_gazette | gd | 831 | 552 | 0.056 | 4.7 | 11.6 | 427 | 73.1% | 270 | 82.6% |
| zhuhai | gd | 695 | 507 | 0.132 | 6.5 | 26.4 | 293 | 82.9% | 300 | 94.3% |
| shanwei | gd | 661 | 403 | 0.096 | 15.4 | 20.3 | 195 | 86.2% | 231 | 93.9% |
| **suzhou** | js | 551 | 437 | 0.054 | 4.3 | 12.4 | 144 | 69.4% | 97 | 96.9% |
| shaoguan | gd | 536 | 357 | 0.097 | 9.2 | 19.3 | 181 | 85.1% | 227 | 93.4% |
| **wuxi** | js | 397 | 243 | 0.115 | 5.3 | 18.5 | 195 | 83.6% | 152 | 94.1% |
| sz (深圳) | gd | 189 | 133 | 0.102 | 4.5 | 17.3 | 111 | 88.3% | 92 | 79.3% |
| yunfu | gd | 182 | 113 | 0.099 | 8.8 | 24.8 | 72 | 87.5% | 49 | 98.0% |
| sz_invest | gd | 126 | 31 | 0.036 | 0.0 | 0.0 | 20 | 65.0% | 19 | 94.7% |
| heyuan | gd | 104 | 57 | 0.088 | 5.3 | 22.8 | 60 | 61.7% | 31 | 93.5% |
| nanjing | js | 35 | 8 | 0.101 | 0.0 | 12.5 | 14 | 85.7% | 3 | 100.0% |
| shantou | gd | 17 | 4 | 0.197 | 0.0 | 25.0 | 10 | 80.0% | 0 | |
| zhanjiang | gd | 11 | 3 | 0.034 | 0.0 | 33.3 | 6 | 100.0% | 0 | |
| yancheng | js | 6 | 2 | 0.032 | 0.0 | 0.0 | 2 | 50.0% | 0 | |
| taizhou_js | js | 2 | 1 | 0.048 | 0.0 | 0.0 | 3 | 100.0% | 0 | |

**Table 6b. Where the two Jiangsu cities sit in the Guangdong distribution.**

| statistic | GD cities (n) | min | Q1 | median | Q3 | max | Suzhou | Wuxi |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| median ovlp_src | 13 (≥ 50 scored) | 0.056 | 0.088 | 0.099 | 0.115 | 0.169 | **0.054** | **0.115** |
| relay % | 13 (≥ 50 scored) | 2.2 | 5.3 | 8.9 | 11.8 | 18.4 | **4.3** | **5.3** |
| province first % | 13 (≥ 40 nested) | 61.7 | 81.4 | 83.6 | 87.2 | 90.0 | **69.4** | **83.6** |
| closer to province % | 13 (≥ 30 chains) | 79.3 | | 93.5 | | 98.0 | **96.9** | **94.1** |

**Three readings.** [measured]

1. **Wuxi is an unremarkable Guangdong city on every measure.** Its province-first share is the
   Guangdong median to one decimal place, its median overlap is the Guangdong third quartile, its
   relay share is the Guangdong first quartile, its chain share is near the Guangdong median. If
   the three findings were a Guangdong artefact, a second Jiangsu prefecture had no reason to land
   there.

2. **The Jiangsu-Guangdong relay difference is a composition artefact.** The quantity
   `fidelity-jiangsu.md` reported as 3.3% against 10.8% has a per-city spread in Guangdong alone
   of 2.2% to 18.4%. Suzhou and Wuxi both fall inside it. Pooling 15 Guangdong cities against one
   Jiangsu city compared a Guangdong average with a draw from the low end of the same
   distribution. The honest statement is not "Jiangsu cities relay less than Guangdong cities"
   but "relay varies three- to eightfold between cities within one province, and the two Jiangsu
   cities crawled so far are both low-relay cities".

3. **The gradient runs with prefecture scale.** The Guangdong cities that relay most are 阳江
   18.4%, 揭阳 15.9%, 汕尾 15.4%, 惠州 11.8%, 江门 10.4%; the ones that relay least are 广州 2.2%,
   深圳 4.5%, 中山 5.6%. Suzhou and Wuxi are two of the largest prefecture economies in China and
   sit at 4.3% and 5.3%. This answers `fidelity-jiangsu.md` §4.3's open question in the direction
   the provincial memo guessed: capacity, not province, predicts whether a city rewrites the
   provincial text or reissues it. [measured for the ordering; inferred for scale as the
   mechanism, since no city-level GDP table is in the repo and `site-selection-gdp.md` works at
   provincial resolution]

Note what this does **not** dissolve. Province-before-city, the chain descent and the lag
gradient are stable across the per-city distribution (province-first 61.7 to 90.0 with a median
of 83.6; closer-to-province 79.3 to 98.0 with a median of 93.5). Only the relay share is strongly
city-dependent. The reframing results survive the control; the one number that looked like a
provincial difference does not. [measured]

---

## 7. A hop Jiangsu could not measure before: city to district

Wuxi's seven district sites hold 2,603 district-level documents with 83.6% body coverage, against
Suzhou's 362 and Nanjing's 626. That makes the city-to-district hop measurable in Jiangsu for the
first time.

**Table 7a. City-to-district pairs (M→D), union basis.**

| set | pairs | scored | median | relay% | mid% |
|---|---:|---:|---:|---:|---:|
| gd_dist (Shenzhen districts + new areas) | 2,604 | 1,516 | 0.045 | **1.0** | 7.0 |
| **wuxi_dist** | 309 | 227 | **0.112** | **12.8** | 15.4 |
| suzhou_dist | 50 | 22 | 0.061 | 0.0 | 18.2 |
| nanjing_dist | 19 | 3 | 0.074 | 0.0 | 0.0 |

Per Wuxi district: wxd_jiangyin 65 pairs / 46 scored / median 0.282 / relay 28.3%; wxd_xishan 74 /
60 / 0.109 / 16.7%; wxd_xinwu 88 / 52 / 0.085 / 5.8%; wxd_liangxi 36 / 27 / 0.061 / 7.4%;
wxd_binhu 30 / 26 / 0.124 / 0.0%.

**Wuxi's districts copy their city; Guangdong's districts do not.** [measured] This contradicts
`fidelity-provincial.md`'s "the copying tier is the prefecture city alone" and
`fidelity-jiangsu.md`'s "districts do not copy in either province", which rested on 8 Jiangsu
district pairs. With 227 scored pairs the Jiangsu district tier relays at 12.8%, above the
Guangdong city average.

**But it is two different objects, and the titles say which.** [measured] Of Wuxi's 29 district
relays, the 锡山/新吴 ones are 转发 at very short lags (区政府办公室转发市政府… at 6, 13, 15, 16,
46 days) and the 江阴 ones are renamed re-issuance at long lags
(《江阴市政府投资管理办法》 from 无锡市政府投资管理办法 at 209 and 587 days,
《江阴市长期护理保险制度实施方案》 at 140 days,
《江阴市深化农村公路管理养护体制改革实施方案》 at 380 days). 江阴 and 宜兴 are county-level
cities, not urban districts, and they behave like the prefecture tier one level down: own
masthead, own 文号, half a year's lag. The urban districts behave like Guangdong's: they forward
within the month or they write their own text. Guangdong's 15 district relays are the same
forwarding-and-local-rewrite mix (深圳市坪山区…应急预案管理办法 from the municipal 办法).

Mechanism, stated carefully: **the translation layer repeats at the city-to-district hop wherever
the lower unit is an independent government with its own instrument series, and does not where it
is an urban district of the same city.** [inferred, from 29 relays in one prefecture] Jiangsu's
county-level cities are the test case the Guangdong district tier, which is almost entirely
Shenzhen's urban districts, could not provide.

---

## 8. The merge is incomplete, and it does not change the verdict

The `wuxi` site key holds 2,209 rows live against 3,865 in the staging DB
`documents_wuxi.db`. **1,707 municipal rows are awaiting a second merge**, blocked by the nightly
write lock. The seven `wxd_*` district sites are complete. So the question has to be asked
whether Wuxi looks thin because it issues little that pairs, or because 44% of its municipal
documents are not yet in the live DB.

**It is neither: Wuxi is not thin.** [measured] On the nested test and on chains Wuxi already
exceeds Suzhou (195 against 144, 152 against 97). On fidelity it has 243 scored pairs against
Suzhou's 437, enough for the median, the three bands and the lag gradient that §5 reports. The
verdict in §9 does not depend on the pending rows.

**Table 8a. What the pending rows would add.**

| genre (identity layer) | live Wuxi municipal docs | live pairs | pairs per doc | pending rows | projected pairs |
|---|---:|---:|---:|---:|---:|
| promulgation | 1,525 | 246 | 0.161 | 855 | 138 |
| explainer | 35 | 3 | 0.086 | 358 | 31 |
| other | 195 | 44 | 0.226 | 332 | 75 |
| implementing | 422 | 103 | 0.244 | 115 | 28 |
| readout | 19 | 1 | 0.053 | 44 | 2 |
| news | 4 | 0 | 0.000 | 3 | 0 |
| **total** | **2,200** | **397** | **0.180** | **1,707** | **+274** |

Flat-rate projection: +308. Genre-weighted: **+274**, lower because the pending set is explainer-
and 批复-heavy (1,276 of the 1,707 are dated 2020 or 2021, and the sample reads
关于…通过交付使用竣工验收的通知, 关于…转为中共正式党员的批复, 《无锡市…办法》解读). Either
way Wuxi lands at roughly **670 to 705** province-to-city pairs after the merge, above Suzhou's
551, with about 410 to 430 of them scored. Expect the nested and chain counts to rise in
proportion (roughly 330 nested pairs, 260 chains). [inferred from the measured per-genre rates]

**What to re-check after the merge.** The relay share is the statistic most exposed, because 13
relays is a small numerator: a plausible range on the projected scored n is 4 to 8%, which stays
inside the Guangdong per-city spread either way. The median overlap and the band shares should be
stable, since the pending genre mix is less instrument-heavy than the merged one and would if
anything pull the median down toward Suzhou's. The province-first share should be stable; it is
83.6% on all three cuts with n over 70.

---

## 9. Verdict on B1

**Discharged.** [measured] The three nested findings are not a Guangdong artefact, and Suzhou was
not carrying Jiangsu.

1. **Province-before-city.** Wuxi 83.6% of 195 nested pairs, 83.6 to 85.0% on every cut with n
   over 70. Suzhou 69.4% of 144. Guangdong cities 68.2% of 1,046 pooled, with a per-city median of
   83.6% over 13 cities. Wuxi is the Guangdong median exactly.
2. **The city descends from the province.** Wuxi 94.1% of 152 chains, centre-only text 1.4% of
   the city document at the median against 16.0% province-only. Suzhou 96.9% of 97, Guangdong
   91.6% of 3,352, the published 92.8% between them.
3. **Cities copy their province.** Wuxi median 0.115, mid 18.5%, relay 5.3% (union basis);
   Guangdong 0.097 / 19.7% / 9.9%; Suzhou 0.054 / 12.4% / 4.3%. Wuxi sits at the Guangdong third
   quartile on the median and the first quartile on relay. 12 of its 13 relays are own-masthead
   市政府办公室 re-issuances of the 省政府办公厅 text at a 185-day median lag, the same object as
   Suzhou's 17 of 19 and Guangdong's 79.5%.

**The stronger claim the coordinator anticipated is available, but with the opposite sign.** Wuxi
does land near Suzhou on the relay share, and that does make the Jiangsu-Guangdong relay
difference a fact about more than one city. It is not a *provincial* fact, though. Measured per
city, both Jiangsu cities fall inside the Guangdong per-city range, near 广州 and 深圳, and the
Guangdong ordering runs from the large coastal prefectures to the small ones. The claim that
replicates is that **relay is a function of the city, and specifically of a gradient that tracks
prefecture scale, while province-before-city and chain descent are properties of the hierarchy
and hold at every city size.** [measured for the spread and the ordering; inferred for scale]

**What B1 would still want.** A third province with two or more cities of contrasting size, so
the scale gradient can be tested across provinces rather than inferred from Guangdong's spread
plus two Jiangsu points. Shandong (12 city portals already crawled) and Fujian are the cheapest
candidates: no new crawler dialect, and both already have a provincial tier.

---

## 10. Honesty

- **The derived layers are mine, not the nightly's.** `doc_identity`, `citations` and
  `diffusion_events` were rebuilt read-only into scratch files because the live ones predate the
  Wuxi merge (§1). They were built by the project's own builders, and the Suzhou check in §1
  reproduces `fidelity-provincial.md` §2.2 to within 0.2 relay points, but every number in this
  memo is from a 2026-10-08 rebuild and will differ in the third digit from the nightly's. The
  Guangdong figures here (pooled relay 9.9%, chains 91.6%) are therefore not byte-comparable with
  `fidelity-jiangsu.md`'s (10.8%, 92.1%); quote this memo's Guangdong numbers when comparing
  within this memo. Re-run the appendix after the next nightly completes.
- **Wuxi is 44% un-merged on the municipal side.** 1,707 rows pending (§8). The verdict does not
  depend on them, but the relay share (13 relays) is the statistic to re-check.
- **Wuxi city is half Suzhou's document count.** 2,206 against 4,919. It yields comparable pair
  counts only because its body coverage is 76.1% against 53.6% and its documents are more often
  instruments. A city whose portal section happens to hold mostly 市政府文件 will always look
  more hierarchical than one whose portal holds a mixed feed; `fidelity-jiangsu.md` §6 made the
  same point about Suzhou against the gkmlpt cities. The per-city control in §6 is the mitigation,
  not a cure.
- **`wxd_*` is shallow against the province and deep only against its own city.** 14
  province-to-district pairs, 4 scored. Every district claim in §7 is about the city-to-district
  hop and about 227 scored pairs in one prefecture, 29 of them relays, with the 江阴 county-city
  subset carrying most of the long-lag renaming. Do not generalize it to Jiangsu.
- **Jiangsu's district tier is still not Guangdong's.** 2,603 Wuxi plus 362 Suzhou plus 626
  Nanjing district documents against Guangdong's 22,510, and Guangdong's are almost all
  Shenzhen's urban districts, which is itself a narrow base. The two district tiers differ in
  composition (urban districts against county-level cities), which is exactly why they disagree
  in §7; neither is a sample of "districts".
- **Wuxi's dates are sound and no repair is applied.** All 4,877 rows `date_quality='good'`, one
  row where the `/doc/YYYY/MM/DD/` path disagrees with `date_published`, 文号 year agreement
  93.8%, no day pile above 32 (§2). The Suzhou figures in this memo use the live redated DB
  (`5465b8e`/`247c5f7`), not the URL-month repair `fidelity-jiangsu.md` applied, which is why
  Suzhou's lag quartiles and relay share here match `fidelity-provincial.md` §2.2 rather than that
  memo's §4.
- **`localized_of` barely fires on Wuxi, for a findable reason.** 2 Wuxi pairs carry it against 44
  Suzhou and 547 Guangdong city pairs. The cause is a title convention: 581 of 2,209 Wuxi titles
  (26%) contain no 无锡 at all (市政府办公室关于加强全市农村道路交通安全工作的意见), against 182 of
  4,919 for Suzhou (3.7%), so `build_doc_identity.localize()` cannot place the document and the
  renaming detector never proposes a trigger. The renaming channel's coverage is therefore a
  function of a portal's masthead style, which is worth logging against `pair-channels.md`: the
  union pair set is a floor by more in Wuxi than in Suzhou. The citation channel carries every
  Wuxi result (385 of 397 pairs).
- **A `derive_province` collision.** 22 `wxd_huishan` documents are coded province `gd`, because
  their 文号 is 惠府发/惠府办 (无锡市惠山区) and the agency-prefix rule reads 惠 as 惠州市,
  Guangdong. Those 22 are dropped by the same-province gate and so are missing from every Jiangsu
  figure here. Logged, not fixed (a writer).
- **The scale interpretation in §6.3 is inferred.** The per-city relay ordering is measured; that
  it tracks prefecture economic scale is read off the city names. No city-GDP table exists in the
  repo. A proper test needs one, and then it is a 20-point rank correlation, not an eyeball.
- **Scored with one worker.** The shim's main database is `:memory:`, so `pairs.py` scores on the
  live connection rather than sharding to subprocesses. Results are identical; the runs took 150
  to 250 s each.
- **Chronology, not causation; publication, not adoption.** As in every memo in this series.
  Mechanism-level claims about a document record. No regime-type labels.
- **No stored artifacts.** The scripts and scratch DBs live outside the repo on the droplet
  (`/root/scratch_wuxi/`). The appendix reproduces everything in about 20 minutes, most of it the
  citation rebuild.

---

## Appendix A. Queries

```sql
-- Wuxi family on the fresh identity layer (Table 2a/2b)
SELECT d.site_key, i.admin_level_doc, COUNT(*), SUM(length(d.body_text_cn) > 500),
       MIN(d.date_published), MAX(d.date_published)
FROM documents d JOIN doc_identity i ON i.doc_id = d.id
WHERE d.site_key = 'wuxi' OR d.site_key GLOB 'wxd_*'
GROUP BY 1, 2 ORDER BY 1, 3 DESC;
-- NB: GLOB, not LIKE 'wxd_%' — LIKE's _ is a wildcard.

-- Date audit (§2): URL path vs date_published, and 文号 year vs publication year
SELECT COUNT(*) FROM documents
WHERE (site_key = 'wuxi' OR site_key GLOB 'wxd_*')
  AND url GLOB '*/doc/[12][0-9][0-9][0-9]/[01][0-9]/*'
  AND substr(url, instr(url, '/doc/') + 5, 7) <> replace(substr(date_published, 1, 7), '-', '/');
-- 1 of 4,877
SELECT COUNT(*), SUM(ny IS NOT NULL), SUM(ny = dy), SUM(ny IS NOT NULL AND ny <> dy) FROM (
  SELECT substr(date_published, 1, 4) dy,
         CASE WHEN document_number GLOB '*〔[12][0-9][0-9][0-9]〕*'
              THEN substr(document_number, instr(document_number, '〔') + 1, 4)
              WHEN title GLOB '*〔[12][0-9][0-9][0-9]〕*'
              THEN substr(title, instr(title, '〔') + 1, 4) END ny
  FROM documents WHERE site_key = 'wuxi' OR site_key GLOB 'wxd_*');
-- 4,877 / 2,761 / 2,590 / 171

-- The pending second merge (§8): staged rows whose URL is not live
-- (immutable=1 so the reader touches neither the -wal nor the -shm of the staging DB)
ATTACH 'file:/root/china-governance/documents.db?mode=ro' AS live;   -- from documents_wuxi.db
SELECT substr(w.date_published, 1, 4), COUNT(*), SUM(length(w.body_text_cn) > 500)
FROM documents w
WHERE w.site_key = 'wuxi'
  AND w.url NOT IN (SELECT url FROM live.documents WHERE site_key = 'wuxi' AND url <> '')
GROUP BY 1;
-- 1,707 rows, 1,073 with a body; 1,276 of them dated 2020-2021

-- Why localized_of does not fire on Wuxi (§10)
SELECT CASE WHEN title LIKE '无锡市%' THEN 'starts 无锡市'
            WHEN title LIKE '市政府%' THEN 'starts 市政府'
            WHEN title LIKE '%无锡%' THEN '无锡 elsewhere' ELSE 'no 无锡' END, COUNT(*)
FROM documents WHERE site_key = 'wuxi' GROUP BY 1;
-- 866 / 581 / 400 / 362  (Suzhou: 3,629 / 182 / 116 / 992 on the 苏州 equivalents)

-- The derive_province collision (§10)
SELECT d.site_key, d.document_number, substr(d.title, 1, 40)
FROM documents d JOIN doc_identity i ON i.doc_id = d.id
WHERE d.site_key GLOB 'wxd_*' AND i.province = 'gd';
-- 22 wxd_huishan rows, 惠府发/惠府办 文号
```

## Appendix B. The sketch

```python
# 1. Rebuild the three derived layers read-only (the nightly holds the write lock).
#    s1: build_doc_identity.build(conn)      -> scratch ident.db   (112 s)
#    s2: extract_citations' tables + TitleMatcher + the three tiers, document loop
#        STREAMED (not fetchall) -> scratch cit.db  (625,227 edges, 756 s)
#    s3: build_diffusion_events.load/build_anchors/match_*/assemble -> scratch ev.db
#        (49,576 rows, 76 s); write_table() points at the scratch file, never documents.db
# 2. shim: main = :memory:; ATTACH documents.db?mode=ro, ident.db, cit.db, ev.db;
#    CREATE TEMP VIEW documents/sites/doc_issuers/citations over the attachments
#    (a persistent view may not reference another attached database, and temp objects win
#    unqualified name resolution); doc_identity and diffusion_events as real tables in main,
#    because both builders probe sqlite_master for type='table'.
# 3. pairs.build_pairs(conn, hops=("P→M","C→P","M→D"), workers=1) — union of
#    citation / title_reissue / localized_of, 5-gram ovlp_src, bands relay>0.7 / mid 0.3-0.7.
#    city set from (site, doc_identity.admin_level_doc, province_of(site)); never pooled.
# 4. Finding 1: confirmed central events keyed (anchor, province); min provincial lag vs min
#    lag from the city set; cuts implementing / anchor>=2015 / both<=365 d.
#    Per-city version: key (anchor, site) against (anchor, province).
# 5. Finding 2: for each scored P→M pair whose P is a confirmed provincial source on a central
#    anchor C with body>500, grams(M), grams(P), grams(C) -> ovlp(M,P), ovlp(M,C), ovlp(P,C)
#    and M's four-way partition. Tasks sorted by (C, P) so bodies are reused; cache cleared
#    every 1,200 entries to stay inside the droplet's RAM beside the classifier.
# 6. Projection (§8): pairs-per-document by doc_identity.genre on the live Wuxi municipal set,
#    applied to the pending set's genre mix (derive_genre on the staged titles, algo_doc_type
#    unavailable there because the staging DB is pre-scoring).
```
