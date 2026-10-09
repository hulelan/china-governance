# Attention Bursts and Campaign Governance Across 29 Topics

*Two agenda-setting tests from `research-agenda.md` (Q1 punctuated attention, Q4
campaign-style governance), run corpus-wide for the first time. Read-only pass over the
live `documents.db` on the droplet, 2026-10-01 (319,208 documents; 198,981 carry
`topics_algo`). The AI-only version of Q1 is in `ai-governance-diffusion.md` §1. This memo
generalizes it to all 29 subject topics in `data/topic_ontology.yaml`. Every series below is
a SHARE of that year's (or that level's) documents, never a raw count. The corpus grows about
70x across the window, so raw counts would manufacture trends.*

*Evidence labels: **[measured]** = computed from the DB in this pass; **[anchor]** = a datable
document found via `diffusion_events` or top `citation_rank` in the burst year; **[reading]** =
interpretation; **[caveat]** = a known weakness of the measure.*

*(Build note 2026-10-01: the `diffusion_events` citer counts in §2.3 are from the 24,599-row
build (post npc/explainer fix, before the resolver fix); the table is rebuilt nightly and held
32,825 rows on 2026-10-01, and the quoted citer counts (e.g. 201 for 纪律处分条例) still held on
a live check. The 13 `citation_rank` values quoted for anchors were checked against the
post-fix recompute and are unchanged, but two anchor ids (12740781, 12651172) now hold 0 raw
inbound because the inbound moved to another copy of the same text. A further resolver
regression fix in progress may move anchor identities again. See `consistency-review.md` H1/H2.
npc rows are kept in the level series here, so the Weather 2018 and Tourism 2010 bursts are
npc-led; other memos exclude or re-level npc, review M7.)*

---

## 0. Short answer

**Test 1 (punctuated attention).** Attention is lumpy at the topic level, but not in the way
the classic pooled test expects. 20 of 29 topics have a yearly share distribution more
concentrated than a smooth trend plus sampling noise would produce (Gini p<0.05), and 23 of
29 have at least one year that sits more than 1.5x above a fitted linear trend (p<0.05).
Yet the pooled distribution of year-over-year changes is NOT fat-tailed (L-kurtosis 0.149
vs 0.123 normal; the noise-only null gives 0.181). The punctuation in this corpus is a small
number of STEP CHANGES and one-off spikes in specific topics, not a general fat-tailed
change process. Of 23 burst episodes detected mechanically, only 12 survive a
leave-one-site-out and continuously-crawled-set check. The rest are site-entry artifacts
(SAMR 2024, Suzhou 2023, a Shenzhen district's COVID notices 2022, a Shenzhen bureau 2011/16).

The three most punctuated topics after the controls: **Party** (a 2020-21 step from under
1% to 4-6% of all government documents, sustained to 2026, almost entirely sub-national),
**Health** (a one-year 2020 spike, 6% to 13%, central and provincial together, municipal a
year later), and **Credit** (a 2018 spike at all three levels in the same year, following the
2017-18 joint-incentive/joint-punishment instruments). Agriculture 2018 (central-led, the
poverty-alleviation and rural-revitalization wave) and Personnel 2009-10 (provincial first)
are the next two.

**Level timing.** With annual resolution most robust bursts are simultaneous across levels
(same calendar year). Where a lead is visible it runs both ways: central-first for Tourism
(2010 to 2012), Health (municipal lags one year), and Agriculture (central only); sub-national
first for Party (municipal and provincial 2021, central never), Personnel (Guangdong 2009,
center 2010) and Weather 2012 (provincial, after a 2011 State Council opinion that did not
itself raise the central share). The hierarchy sets the agenda in some bursts and merely
records sub-national mobilization in others.

**Test 2 (campaign-style governance).** The campaign-title share of government documents
is rising, but only at the TOP of the hierarchy. Central share 0.21% (2010-14) to 0.99%
(2020-25), provincial 0.35% to 0.79%, both confirmed on fixed site sets. Municipal share is
flat to falling: 1.09% to 0.85% overall, and 1.43% (2005-09) to 0.74% (2023-25) on a fixed
six-city Guangdong set. The campaign label has moved UP the hierarchy, not down. The center
titles 专项行动 (0.55% of central docs 2020-26); localities title 攻坚 (0.46% of municipal
docs). Provinces write 实施方案 (16% of their campaign titles), municipalities write 工作方案
and news of 开展/推进, the center writes 行动方案 and never 转发. Campaign-heavy topics are
Safety, Agriculture, Security, Commerce, Environment. Campaigns are NOT the general delivery
vehicle of attention bursts: only 3 of 30 attention bursts have a within-topic campaign
burst within a year. They are the vehicle in three specific cases: poverty alleviation 2018,
COVID 2020, and work safety 2023-24. The body-text measure tells a different story from the
title measure: documents MENTIONING a campaign term anywhere hold steady at 4-6% of
government documents for the whole window, and the 2018-20 hump in 攻坚战 mentions (0.5% to
2.9% of docs, back to 0.9% by 2026) is the clearest single campaign signature in the data.

---

## 1. Method

*(**Level basis checked 2026-10-09, and Test 2 gets STRONGER.** This memo predates `doc_identity`
and takes levels from `sites.admin_level`, which files ~28k npc 地方法规 as central. Those
regulations sit in the central **denominator** and essentially never carry a campaign title, so the
central share was being deflated. Re-measured on the per-document level, same proxy and same
periods:*

| basis | central 2010-14 | 2015-19 | 2020-26 | provincial 2020-26 | municipal 2020-26 | district 2020-26 |
|---|---|---|---|---|---|---|
| site (as published) | 0.21% | 0.87% | **1.00%** | 0.68% | 0.75% | 0.55% |
| **per-document** | 0.28% | 1.27% | **1.31%** | 0.60% | 0.67% | 0.62% |

*The denominator moves exactly as that mechanism predicts: central n falls **55,025 → 41,444** for
2020-26 as the npc regulations leave, while provincial rises 35,600 → 41,698.*

***So "the campaign label has moved UP the hierarchy, not down" holds and sharpens.*** *On the site
basis central (1.00%) was only modestly ahead of municipal (0.75%). On the per-document basis
central is **1.31% against 0.60 / 0.67 / 0.62** — roughly **twice any other level** — and the rise
across the window is 0.28 → 1.31 rather than 0.21 → 0.99. The published figures understated the
finding.)*

**Universe.** Government levels only (`sites.admin_level` in central, provincial, municipal,
district, department). Media and research sites are excluded because the question is about
bureaucratic attention. Years 2005-2025 for the statistics; 2026 (to 2026-09) reported
separately as partial. **[measured]** 2005-2025 government universe: 203,358 documents,
139,205 topic-tagged.

**Topic series.** `topics_algo` is a comma-separated multi-label list of the 29 ontology
categories (134k docs carry one label, 47k two, 8k three). A document counts once in each
of its topics. Share of topic t in year y = tagged docs carrying t / all tagged docs that
year. The denominator is tagged docs rather than all docs because the tagger covers 61-71%
of docs per year with no trend (see Table 0); using all docs as denominator changes nothing
(Spearman of Gini rankings 0.997).

**Table 0. Tagger coverage by year (government universe)** **[measured]**

| year | docs | tagged | rate |
|---|---:|---:|---:|
| 2005 | 1,428 | 1,014 | 0.71 |
| 2010 | 4,666 | 3,083 | 0.66 |
| 2015 | 5,144 | 3,406 | 0.66 |
| 2018 | 10,237 | 6,957 | 0.68 |
| 2020 | 12,987 | 9,160 | 0.71 |
| 2022 | 19,682 | 13,974 | 0.71 |
| 2024 | 27,480 | 18,423 | 0.67 |
| 2025 | 31,285 | 21,734 | 0.70 |
| 2026* | 53,242 | 32,702 | 0.61 |

**Burstiness measures per topic (21 yearly shares).** (a) Gini of the share series.
(b) Top-3 mass: the three largest yearly shares as a fraction of the sum (uniform
baseline 3/21 = 0.143). (c) Max local ratio: the largest value of share / centered
5-year rolling median (the year itself excluded). (d) Max trend residual: the largest
value of share / fitted linear-in-logit trend. Composite rank = mean rank over (a)-(d).
Excess kurtosis of year-over-year log changes is reported but not ranked on (20 points per
topic is too few).

**Smooth null.** For each topic, a weighted linear trend in logit(share) is fitted, then
400 series are simulated by drawing binomial counts from the fitted shares with the real
yearly denominators. The p-value is the fraction of simulated series whose measure meets or
exceeds the observed one. This null is "smooth growth or decline plus sampling noise."
A quadratic null was tried and rejected because it absorbs hockey-stick step changes, which
are exactly the punctuations of interest.

**Burst rule.** Year y is a burst year for topic t if share / rolling median >= 1.5, the
binomial z-score against the rolling-median share is >= 3, the topic has >= 20 docs that
year, and y is 2007-2025 (two years of left context required, so 2005-06 edge spikes are
not counted). Adjacent burst years are merged into one episode labeled by its peak.

**Site controls.** Two, because the corpus's site composition shifts by year.
(1) Leave-one-site-out (LOSO): the top contributing site for the episode is removed from
the whole series; the episode passes if a burst within one year remains. (2) Core set:
nine sites with >= 10 docs in every year 2010-2025, spanning central, Guangdong and the
Tier-1 cities: `gov`, `ndrc`, `mof`, `mofcom`, `chinatax`, `gd`, `bj`, `sh`, `gz`
(50,499 docs, 38,139 tagged, 2005-25). Shenzhen `sz` was excluded because it has fewer
than 20 docs a year before 2018. For each failed-LOSO episode the top site's own volume
ratio (its docs in the burst year / its median in the two years either side) and its own
within-site topic-share ratio were computed to separate "the site shifted attention" from
"the site's volume jumped."

**Campaign proxy.** Title contains any of 专项行动, 专项整治, 攻坚, 大会战, 集中整治,
百日行动. Share = campaign-titled docs / all docs at that level that year. Body-level
mentions were counted via the `doc_search` trigram FTS for the terms of 3+ characters
(攻坚 is two characters and cannot be matched by the trigram index; 攻坚战 and 脱贫攻坚 were
used instead).

---

## 2. Test 1: punctuated attention across 29 topics

### 2.1 Distribution of burstiness

**Table 1. Burstiness by topic, government universe, 2005-2025** **[measured]**
*(docs = tagged docs carrying the topic 2005-25; null = median of the smooth-null
simulations; p = fraction of null draws at or above observed; bursts = mechanical burst
years before site controls)*

| # | topic | docs | Gini (null) | top-3 mass (null) | max local ratio | max trend resid | p(Gini) | p(resid) | bursts |
|---:|---|---:|---|---|---:|---:|---:|---:|---|
| 1 | Party | 4,269 | 0.648 (0.610) | 0.549 (0.508) | 1.95 | 6.00 | 0.000 | 0.015 | 2016, 2023 |
| 2 | Diplomacy | 1,772 | 0.322 (0.299) | 0.325 (0.273) | 2.13 | 3.22 | 0.170 | 0.000 | 2010, 2012 |
| 3 | Credit | 808 | 0.299 (0.169) | 0.272 (0.202) | 4.14 | 2.69 | 0.000 | 0.005 | 2018 |
| 4 | Military | 1,570 | 0.277 (0.138) | 0.299 (0.208) | 2.97 | 2.18 | 0.000 | 0.003 | 2008 |
| 5 | Commerce | 4,669 | 0.225 (0.076) | 0.285 (0.179) | 1.98 | 2.91 | 0.000 | 0.000 | (edge 2005-06) |
| 6 | Awards | 1,439 | 0.424 (0.381) | 0.312 (0.329) | 1.59 | 2.12 | 0.000 | 0.000 | 2021 |
| 7 | Security | 5,687 | 0.313 (0.141) | 0.285 (0.197) | 1.87 | 1.93 | 0.000 | 0.000 | 2010 |
| 8 | Weather | 1,520 | 0.216 (0.160) | 0.234 (0.200) | 2.87 | 2.41 | 0.005 | 0.010 | 2012, 2018 |
| 9 | Health | 9,346 | 0.230 (0.102) | 0.285 (0.181) | 1.88 | 2.07 | 0.000 | 0.000 | 2020, 2022 |
| 10 | Personnel | 12,260 | 0.163 (0.064) | 0.235 (0.165) | 1.94 | 2.10 | 0.000 | 0.000 | 2009, 2010 |
| 11 | Emergency | 5,967 | 0.191 (0.136) | 0.229 (0.195) | 1.75 | 2.22 | 0.000 | 0.000 | 2008 |
| 12 | Trade | 5,618 | 0.255 (0.237) | 0.277 (0.247) | 1.78 | 1.43 | 0.013 | 0.000 | (edge 2005) |
| 13 | Welfare | 10,951 | 0.210 (0.038) | 0.231 (0.156) | 1.84 | 1.74 | 0.000 | 0.000 | 2011, 2016 |
| 14 | Tourism | 2,220 | 0.194 (0.187) | 0.213 (0.215) | 2.55 | 1.65 | 0.388 | 0.182 | 2010 |
| 15 | Veterans | 995 | 0.239 (0.189) | 0.256 (0.210) | 1.60 | 1.63 | 0.048 | 0.477 | none |
| 16 | Agriculture | 7,355 | 0.200 (0.220) | 0.226 (0.238) | 1.62 | 2.05 | 0.988 | 0.000 | 2018 |
| 17 | Infrastructure | 15,644 | 0.196 (0.041) | 0.213 (0.157) | 1.50 | 1.63 | 0.000 | 0.000 | 2023 |
| 18 | Safety | 6,706 | 0.126 (0.095) | 0.209 (0.177) | 1.71 | 1.78 | 0.010 | 0.000 | 2024 |
| 19 | Housing | 6,316 | 0.190 (0.181) | 0.233 (0.216) | 1.52 | 1.45 | 0.275 | 0.095 | 2023 |
| 20 | Finance | 22,702 | 0.181 (0.142) | 0.238 (0.200) | 1.30 | 1.36 | 0.000 | 0.000 | none |
| 21 | Government | 6,278 | 0.144 (0.125) | 0.192 (0.197) | 1.69 | 1.48 | 0.028 | 0.000 | none |
| 22 | Education | 10,130 | 0.118 (0.105) | 0.200 (0.183) | 1.56 | 1.65 | 0.107 | 0.000 | 2008 |
| 23 | Transport | 10,416 | 0.119 (0.047) | 0.197 (0.159) | 1.66 | 1.58 | 0.000 | 0.000 | 2007 |
| 24 | Environment | 8,123 | 0.119 (0.057) | 0.207 (0.170) | 1.38 | 1.68 | 0.000 | 0.000 | none |
| 25 | Tech | 11,583 | 0.158 (0.130) | 0.197 (0.194) | 1.44 | 1.37 | 0.005 | 0.007 | none |
| 26 | Legal | 9,727 | 0.140 (0.151) | 0.215 (0.203) | 1.25 | 1.18 | 0.873 | 0.497 | none |
| 27 | Sports | 1,784 | 0.131 (0.105) | 0.194 (0.179) | 1.37 | 1.61 | 0.070 | 0.152 | none |
| 28 | Energy | 3,354 | 0.128 (0.119) | 0.194 (0.197) | 1.44 | 1.39 | 0.255 | 0.025 | none |
| 29 | Culture | 4,336 | 0.044 (0.053) | 0.157 (0.165) | 1.09 | 1.14 | 0.835 | 0.830 | none |

**Distribution.** **[measured]** Gini ranges 0.044 (Culture) to 0.648 (Party), median
0.194; the null median is 0.136. Top-3 mass ranges 0.157 to 0.549, median 0.231, against a
uniform baseline of 0.143 and a null median of 0.197. Max local ratio ranges 1.09 to 4.14,
median 1.69. 20 topics beat the null on Gini, 22 on top-3 mass, 23 on max trend residual.

**Reading of the table.** **[reading]**
- The top of the ranking is small topics with a single regime change: Party (step up
  2020-21), Credit (2018 spike), Diplomacy (steady climb 2021-26 plus a 2010 spike),
  Military (2008-13 plateau then decline), Awards (step DOWN after 2013: 2.5-4.9% of docs in
  2005-13, 1.3% in 2014, under 1% from 2015, consistent with the 2013-14 curtailment of
  评比达标表彰, but
  the early-year mass comes from Guangdong city gazettes and is not site-controlled).
- Commerce and Trade rank high only because their mass sits at the 2005-06 edge (MOFCOM
  2004-05 orders) and declines after. These are not bursts in the window.
- The large, steady-state topics are the bottom third: Finance, Government, Education,
  Transport, Environment, Tech, Legal, Energy, Culture. These are the bureaucracy's routine
  output and their shares move by less than 1.7x against the local baseline in any year.
  Tech's absence from the burst list is expected: the AI burst documented in
  `ai-governance-diffusion.md` is a sub-topic of Tech and is diluted at the 29-topic grain
  (Tech 2026 is 1.54x its 2021-25 median, but 34% of it is the MIIT site, which only has 2026
  documents).
- Gini and the p-values disagree for Agriculture (Gini below null, trend residual far above):
  its series is a steady share with one 2018 spike, which the concentration measures miss
  and the trend residual catches. The two families of measures are complementary.

### 2.2 The pooled change-distribution test is negative

The Baumgartner-Jones signature is a leptokurtic pooled distribution of period-to-period
changes. **[measured]** Pooling the 20 year-over-year log changes of each topic, each
standardized within topic (n = 580): excess kurtosis 0.24, L-kurtosis 0.149 (normal 0.123).
For the 13 topics with >= 30 docs in every year (n = 260): excess kurtosis -0.07,
L-kurtosis 0.116. The smooth null with sampling noise gives an L-kurtosis of 0.181 (95th
percentile 0.225), heavier than observed, because the noise variance differs by year.
1.5% of standardized changes exceed 2.5 sd (normal 1.2%).

**[reading]** At annual resolution and 21 points per series, the aggregate change
distribution of this corpus is not fat-tailed. Punctuation here is not a general property
of the change process. It is a few topic-specific step changes and spikes, visible in the
per-topic measures of 2.1 and the episodes of 2.3. This is a weaker claim than the classic
one and it should be stated that way. A monthly series on the post-2018 corpus (where
volumes support it) would be the proper next test. **[caveat]** With 20 changes per topic,
the pooled test also has little power against moderate fat tails.

### 2.3 Burst episodes, site controls, and anchors

**Table 2. Mechanical burst episodes 2007-2025 and what they survive** **[measured]**
*(ratio = share / rolling median at peak; k = topic docs at peak; top site = largest
contributor and its share of the topic that year; vol = top site's own doc volume vs its
neighbor-year median; att = top site's own within-site topic share vs neighbors; core =
burst within one year in the 9-site core set)*

| topic | peak | ratio | k | top site | vol | att | LOSO | core | verdict |
|---|---|---:|---:|---|---:|---:|---|---|---|
| Health | 2020 | 1.88 | 1,187 | gov 44% | 1.2 | 2.4 | pass | yes | **robust** |
| Credit | 2018 | 2.42 | 95 | gov 44% | 1.8 | 3.3 | pass | yes | **robust** |
| Personnel | 2009-10 | 1.94 | 236 | gd 23% | 0.9 | 5.9 | pass | yes | **robust** |
| Emergency | 2008 | 1.75 | 103 | gov 32% | 12.0 | 1.9 | pass | yes | robust, gov 2008 batch inflates |
| Party | 2021-23 | 1.53 | 1,139 | szdp 12% | 1.5 | 1.8 | fail at 2023 | yes (2021) | **robust step**, broad-based |
| Agriculture | 2018 | 1.62 | 793 | gov 63% | 1.8 | 1.5 | fail | yes | central-led, real |
| Weather | 2018 | 1.51 | 76 | npc 36% | 1.1 | 2.2 | fail | yes | central/legislative-led |
| Weather | 2012 | 2.87 | 43 | szgm 35% | 7.3 | 1.6 | pass | no | small k; passes without szgm |
| Diplomacy | 2010 | 2.13 | 46 | gov 37% | 2.1 | 2.1 | pass | yes | small k, weak anchors |
| Tourism | 2010 | 2.06 | 36 | npc 42% | 1.8 | 2.3 | fail | no | central-led, small k |
| Awards | 2021 | 1.59 | 93 | gov 17% | 1.1 | 2.5 | pass | yes | weak (督查表扬通报) |
| Security | 2010 | 1.52 | 69 | gov 20% | 2.1 | 1.3 | pass | no | marginal |
| Transport | 2007 | 1.66 | 118 | ndrc 22% | 4.0 | 1.9 | fail | yes | weak, ndrc batch |
| Party | 2016 | 1.95 | 33 | bj 36% | 1.4 | 3.0 | fail | no | Beijing-concentrated (两学一做) |
| Diplomacy | 2012 | 1.89 | 22 | gov 55% | 1.6 | 2.9 | fail | no | thin |
| Military | 2008 | 2.97 | 36 | gov 53% | 12.0 | n/a | fail | yes* | gov 2008 archive batch; indeterminate |
| Health | 2022 | 1.85 | 1,757 | szlhq 23% | 0.9 | 11.8 | fail | no | **artifact**: one district's COVID notices |
| Welfare | 2011 | 1.84 | 259 | mzj 42% | 3.3 | 2.4 | fail | no | **artifact**: Shenzhen civil-affairs volume |
| Welfare | 2016 | 1.52 | 604 | mzj 49% | 3.4 | 1.0 | fail | no | **artifact** |
| Infrastructure | 2023 | 1.50 | 2,522 | suzhou 39% | 20.4 | 0.7 | fail | no | **artifact**: Suzhou crawl entry |
| Housing | 2023 | 1.52 | 1,326 | suzhou 34% | 20.4 | 17.2 | fail | no | **artifact** |
| Safety | 2024 | 1.71 | 1,490 | samr 38% | 20.6 | 1.7 | fail | no | **artifact**: SAMR crawl entry |
| Education | 2008 | 1.56 | 147 | moe 52% | 43.0 | 1.8 | fail | no | **artifact**: MOE batch |

\* core "replicates" Military 2008 only because `gov` is in the core set.

**[measured]** 23 episodes; 8 pass LOSO; 10 replicate in the core set within one year;
7 are site-entry artifacts by the volume test (top site's volume 3x or more above its
neighbors and the episode vanishes without it). Across the three sources of attention
bursts, the LOSO test is strict in a specific way: a burst driven by the State Council site
(`gov`) fails it even when `gov`'s own within-site attention genuinely shifted (Agriculture
2018: gov share 15.0% to 22.2%). Those are read as central-led, not as artifacts.

**Anchors for the robust episodes.** **[anchor]** (ids are `documents.id`; "citers" are
citation-matched `diffusion_events` sources)

- **Health 2020.** Share 6.15% (2019) to 12.96% (2020), back to 7.67% (2021). Central
  6.0% to 16.0%, provincial 6.8% to 19.6% in the same year; municipal 6.3% to 7.9% (2020)
  to 10.1% (2021) to 16.4% (2022, the Longhua district COVID batch). Anchors: 2019
  国务院关于实施健康中国行动的意见 (900040513, cr 183, 14 citers), 2019
  基本医疗卫生与健康促进法 (12740781, 21 citers), 2020 中共中央 国务院关于深化医疗保障制度改革的意见
  (12760144, cr 326, 53 citers, 34 provincial 19 municipal), 2020
  医疗保障基金监管制度体系改革指导意见 (900040386, cr 101). **[reading]** The spike is the
  pandemic year, but the cited anchors are the medical-insurance reform instruments, not
  epidemic notices. Attention and authority ran on different documents.
- **Credit 2018.** 0.76% (2017) to 1.37% (2018) to 0.56% (2019). Central 1.0% to 1.5%,
  provincial 0.9% to 1.4%, municipal 0.8% to 2.0%, all in 2018. Anchors: 2017
  发改财金规〔2017〕1798号 守信联合激励和失信联合惩戒对象名单管理指导意见 (12652242, cr 24.5),
  2018 中办国办 关于进一步加强科研诚信建设的若干意见 (12694751, cr 139.5), 2018
  国家发改委办公厅 人民银行办公厅 关于对失信主体加强信用监管的通知 (900057210). **[reading]**
  A one-year spike that returned to baseline: the joint-punishment memoranda wave, which
  localities echoed in the same year and then stopped titling.
- **Personnel 2009-10.** 8.17% (2008) to 15.10% (2009) to 14.92% (2010) to 7.41%
  (2011). Provincial 10.5% to
  25.3% in 2009 (Guangdong 54 docs, Jiangsu 51), central 4.4% to 13.6% in 2010 (gov 160),
  municipal 7.6% to 17.7% in 2010. Anchors: 2008 行政机关公务员处分条例 (900045275, cr 241,
  33 citers), 2010 国务院关于加强职业培训促进就业的意见 (900044564, cr 87, 12 citers), 2008-09
  State Council employment notices (cr 91.5, 72.5, 34). **[reading]** A post-crisis
  employment and civil-service wave in which provinces moved a year before the center's
  own document share did.
- **Party 2021-23 step.** 0.51% (2019), 1.10% (2020), 3.55% (2021), 3.92%, 6.24% (2023),
  5.33%, 4.23% (2025), 6.04% (2026). Municipal 0.2% (2019) to 2.8% (2020) to 10.4% (2021)
  to 13.4% (2024); provincial 0.4% to 3.0% (2021) to 4.9% (2024); department 0% to 6.0%
  (2022); district 1.7% (2021) to 8.0% (2023). Central stays 0.6-1.2% through 2025. Top
  sites 2021: Heyuan 86, Jieyang 69, Guangdong 43, Huizhou 41, Guangzhou 37, i.e. spread
  across Guangdong governments. Anchors in 2022-23: 中国共产党纪律处分条例 (12651172, 201
  citers: 73 municipal, 68 district, 33 provincial, 27 department), 事业单位工作人员处分规定
  (900047680, cr 37), 领导干部应知应会党内法规和国家法律清单制度 (12651244). **[reading]**
  The step begins in 2020-21 (党史学习教育, the centenary year) and does not revert. It is
  the largest and most durable punctuation in the corpus and it is a sub-national
  phenomenon: Party-topic output rose from a rounding error to roughly one in ten
  municipal documents, while the center's own share did not move. **[caveat]** Part of
  this is a shift in WHAT municipal sites publish (news of study sessions and 党建
  activity, genre `other`), not only a shift in what policy they issue. The step is real in
  the document record either way.
- **Agriculture 2018.** 4.80% (2017) to 11.40% (2018) to 8.93% (2019), all levels;
  central 5.1% to 15.6%,
  provincial 7.4% to 9.4%, municipal 5.0% to 7.7%. Anchors: 2018 民政部 贯彻落实《中共中央
  国务院关于打赢脱贫攻坚战三年行动的指导意见》行动方案 (900057514, cr 222.5), 2018
  跨省域补充耕地国家统筹管理办法 (900040971, cr 181, 13 provincial citers), 2017
  畜禽养殖废弃物资源化利用意见 (900041162, cr 148.5, 19 citers), 2018 省级政府耕地保护责任目标考核办法
  (900041012). **[reading]** Central-led and campaign-framed (the three-year
  poverty-alleviation action). Sub-national echo is modest at this grain.
- **Emergency 2008, Weather 2012, Tourism 2010.** Emergency 2008: 地质灾害防治条例 (900045158,
  cr 220, 15 citers), 突发公共卫生事件应急条例, 重大动物疫情应急条例, the Wenchuan year, with
  provincial onset in 2007 and central in 2008. Weather 2012: provincial 0.8% to 1.8%
  following the 2011 国办 关于加强气象灾害监测预警及信息发布工作的意见 (900043504, cr 28.5, 6
  citers) and the 2012 人工影响天气意见 (900042897); the central share itself barely moved
  (0.2% to 0.8%, 9 docs). Tourism 2010: central 0.5% to 1.9% after the 2009
  国务院关于加快发展旅游业的意见 (900044659, cr 77.5, 14 citers, 11 provincial), provincial
  0.7% to 3.5% in 2012: a two-year central lead.

### 2.4 Level timing

**[measured]** Onset per level = first year in the peak +/-2 window where that level's own
share is >= 1.3x its rolling median with z >= 2 and >= 10 docs. For the 12 non-artifact
episodes:

| episode | central onset | provincial onset | municipal onset | pattern |
|---|---|---|---|---|
| Health 2020 | 2020 (2.3x) | 2020 (2.3x) | 2021 (1.4x) | central = provincial, municipal +1 |
| Credit 2018 | 2018 (2.1x) | none | 2018 (4.7x) | same year |
| Personnel 2009 | 2010 (3.1x) | 2009 (3.0x) | 2010 (2.3x) | provincial first |
| Emergency 2008 | 2008 (2.4x) | 2007 (1.9x) | none | provincial first |
| Party 2021-23 | none | 2021 (2.0x) | 2021 (1.9x) | sub-national only |
| Agriculture 2018 | 2016-18 (1.5x) | none | none | central only |
| Weather 2018 | 2017 (2.2x) | none | 2018 (2.1x) | central first |
| Weather 2012 | none | 2012 (3.5x) | none | provincial only |
| Diplomacy 2010 | 2010 (2.1x) | none | 2010 (4.0x) | same year |
| Tourism 2010 | 2010 (3.2x) | 2012 (2.2x) | none | central first, +2 |
| Awards 2021 | none | none | 2019 (2.2x) | sub-national only |
| Security 2010 | none | none | 2010 (2.2x) | sub-national only |

Tally over the 12: central first or central only 4; same year 3; sub-national first or
only 5. **[reading]** The clean hierarchical story (center bursts, then provinces, then
cities) holds for Tourism, Weather 2018, Agriculture and roughly for Health. It does not
hold for Party, Personnel, Emergency, or Weather 2012, where the sub-national share moves
first or alone. In those cases the center's datable instrument often PRECEDES the
sub-national burst (Weather: 2011 opinion, 2012 provincial burst; Personnel: 2008 条例,
2009 provincial burst) without raising the center's own output share, which is what a
one-instrument-many-implementations cascade looks like. Annual resolution cannot separate
"same year" into lead and lag; the consumption-diffusion memo's median lag of ~49 days sits
inside one calendar year.

### 2.5 2026 partial-year signals

**[measured]** Share in 2026 (to 2026-09) vs the 2021-25 median, with the top contributing
site: Diplomacy 2.62x (MIIT 27%, MFA new), Tourism 1.72x (broad, top site 8%), Agriculture
1.64x (broad, top site 7%, but the August 2026 department-tier crawl added ~40 provincial
agriculture bureaus), Commerce 1.56x (SAMR 9%), Tech 1.54x (MIIT 34%), Party 1.43x (MIIT
24%), Military 1.38x (MIIT 20%). Housing 0.66x, Infrastructure 0.59x, Welfare 0.61x (the
Shenzhen department and district sites stopped at 2026-03). **[caveat]** 2026 is dominated
by crawl composition (MIIT has only 2026 docs, the department tier is new, Shenzhen tiers
are truncated). None of these should be read as attention bursts until the year closes and
the site mix is controlled.

### 2.6 Robustness summary

**[measured]**
- Core-set ranking (9 sites) vs full ranking: Spearman 0.66 on the composite, 0.59 on
  Gini. The core top 8: Military, Credit, Party, Diplomacy, Health, Weather, Tourism,
  Awards. Six of these are in the full top 9.
- Central-only ranking vs full: 0.64; sub-national-only vs full: 0.75. Sub-national top 8:
  Party, Weather, Diplomacy, Credit, Security, Military, Tourism, Awards.
- Denominator (tagged vs all docs): Gini rank Spearman 0.997.
- Of 24 mechanical burst years, 11 replicate exactly in the core set. The core set also
  finds bursts the full universe does not (Agriculture 2016/2019, Emergency 2014/2024,
  Infrastructure 2009/2017, Military 2010/2016, Transport 2012-13), because its small
  yearly denominators (600-3,700 tagged docs) make 1.5x local ratios easy to reach. The
  core set is a check on direction, not a second census.
- The 2026 denominator is 61% tagged vs 67-71% in other years; 2026 is excluded from all
  statistics.

---

## 3. Test 2: campaign-style governance

### 3.1 Campaign-title share by year and level

**Table 3. Campaign-titled docs as a share of that level's documents** **[measured]**
*(government levels; district and department tiers are Shenzhen-dominated and enter the
record at scale only from 2019)*

| year | all gov | central | provincial | municipal | district | department | core-9 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2008 | 0.89% (23/2,598) | 0.84% | 0.94% | 1.18% | 0/38 | 0/118 | 1.11% |
| 2010 | 1.01% (47/4,666) | 0.10% | 0.46% | 2.33% | 0/20 | 0/142 | 0.18% |
| 2012 | 0.26% (10/3,872) | 0.12% | 0.41% | 0.40% | 0/101 | 0/129 | 0.24% |
| 2014 | 0.40% (16/3,957) | 0.60% | 0.21% | 0.48% | 0/101 | 0/299 | 0.18% |
| 2016 | 1.00% (70/7,023) | 0.78% | 2.19% | 0.49% | 0/208 | 0/618 | 1.34% |
| 2018 | 0.87% (89/10,237) | 1.21% | 0.49% | 0.88% | 0/501 | 0/738 | 1.27% |
| 2020 | 0.84% (109/12,987) | 1.26% | 0.43% | 0.87% | 0/480 | 0.23% | 1.19% |
| 2022 | 0.76% (150/19,682) | 0.75% | 1.05% | 1.21% | 0.04% | 0.46% | 0.90% |
| 2024 | 0.95% (262/27,480) | 1.15% | 0.90% | 0.83% | 1.00% | 0.82% | 1.37% |
| 2025 | 0.79% (247/31,285) | 0.82% | 0.82% | 0.98% | 0.61% | 0.65% | 1.38% |
| 2026* | 0.78% (417/53,242) | 1.05% | 0.48% | 0.89% | 0.35% | 0.32% | 0.53% |

Period means and trend 2010-2025 (Spearman of share on year; log-linear slope):

| level | 2010-14 | 2015-19 | 2020-25 | Spearman | slope/yr |
|---|---:|---:|---:|---:|---:|
| all gov | 0.51% | 0.72% | 0.78% | +0.29 | +4.5% |
| central | 0.21% | 0.88% | 0.99% | +0.71 | +17.6% |
| provincial | 0.35% | 0.89% | 0.79% | +0.66 | +6.8% |
| municipal | 1.09% | 0.62% | 0.85% | +0.06 | -0.3% |
| department (SZ) | 0.00% | 0.03% | 0.56% | +0.99 | n/a |
| core-9 | 0.19% | 1.07% | 1.14% | +0.75 | +19.1% |

### 3.2 Is the campaign share rising? At the top, yes. At the municipal level, no.

**[measured]** Fixed-site sets, to remove site-entry effects:

| site set | 2005-09 | 2010-14 | 2015-19 | 2020-22 | 2023-25 |
|---|---:|---:|---:|---:|---:|
| State Council (`gov`) | 1.66% (n=785) | 0.21% | 1.66% | 1.64% | 1.62% |
| NDRC+MOF+MOFCOM+Tax | 0.00% | 0.10% | 0.30% | 0.64% | 0.72% |
| CAC | n/a | 10.5% (n=76) | 3.04% | 4.80% | 4.99% |
| GD+BJ+SH provincial | 1.30% | 0.16% | 0.79% | 0.89% | 1.15% |
| 6 GD cities (珠海 江门 揭阳 中山 惠州 广州) | 1.43% | 1.18% | 0.65% | 0.58% | 0.74% |
| 8 Shenzhen bureaus | 0.00% | 0.00% | 0.03% | 0.29% | 0.71% |

**[reading]** The central rise is real but is a step, not a slope: the State Council
site jumps from 0.2% to 1.7% between the 2010-14 and 2015-19 periods and stays there. The
line ministries rise steadily from nothing to 0.7%. CAC is the campaign ministry of the
record (one in twenty of its documents is a titled campaign: the 清朗 series, 剑网, IPv6
and algorithm drives). The provincial fixed set rises from 0.16% to 1.15%. The municipal
fixed set FALLS from 1.4% to 0.7%: in 2005-2010 Guangdong city gazettes were full of
食品药品专项整治 and 环保专项行动 work plans; by 2020-25 those cities title fewer campaigns than
the center does. The Shenzhen bureau rise from zero is partly genre: their early documents
are catalog items (notices, regulations), their later documents are news of 开展…专项行动.
**[caveat]** This genre shift also inflates the recent municipal and district shares.

### 3.3 Who runs campaigns: central design, provincial implementation plans, local execution news

**[measured]** Term mix by level, 2020-26, share of that level's docs:

| level | 专项行动 | 专项整治 | 攻坚 | 集中整治 | 大会战 | 百日行动 |
|---|---:|---:|---:|---:|---:|---:|
| central | 0.55% | 0.18% | 0.24% | 0.03% | 0.00% | 0.01% |
| provincial | 0.20% | 0.11% | 0.33% | 0.01% | 0.00% | 0.02% |
| municipal | 0.16% | 0.13% | 0.46% | 0.08% | 0.04% | 0.02% |
| district | 0.17% | 0.14% | 0.20% | 0.03% | 0.00% | 0.00% |
| department | 0.18% | 0.17% | 0.18% | 0.01% | 0.00% | 0.01% |

Framing words inside campaign titles, 2010-26:

| level | n | 转发 | 实施方案 | 工作方案 | 行动方案 |
|---|---:|---:|---:|---:|---:|
| central | 708 | 0% | 3% | 3% | 9% |
| provincial | 324 | 5% | 16% | 5% | 10% |
| municipal | 534 | 6% | 7% | 8% | 7% |
| district | 125 | 0% | 8% | 5% | 13% |
| department | 160 | 0% | 1% | 2% | 4% |

Central campaign-titled docs by site, 2016-26: gov 279, cac 117, samr 102, miit 90 (2026
only), ndrc 13, chinatax 12, mot 11. By year the center's campaign output peaks in 2018-20
(gov 50, 45, 46: 脱贫攻坚, 污染防治攻坚战, 长江保护修复攻坚战 action plans) and again in 2024
(SAMR 40: 百日攻坚 inspections, 涉企收费 drives; NDRC 6: sectoral 节能降碳专项行动计划).

**[reading]** The vocabulary is layered. The center says 专项行动 and issues 行动方案 and
通知; it never relays. Provinces say 攻坚 and write 实施方案 (one in six of their campaign
titles), the documentary form of "implementing the central campaign here." Municipalities
say 攻坚 most of all (污染防治攻坚战, 工业转型升级攻坚战 in 2015, 创文攻坚, 治本攻坚三年行动 in
2024) and publish 工作方案 and news of 开展/推进/动员会. The 2016 provincial spike (2.19%, 41
docs) is one national campaign relayed: the April 2016 互联网金融风险专项整治 implementation
plans of Beijing and Shanghai plus Heilongjiang's mirror of the 15-ministry sector plans.
This is the hypothesis in the agenda (campaigns as a sub-national execution device even
when framed centrally) in its documentary form. But the share data do not show localities
doing MORE of this over time. They show the center titling more campaigns itself.

### 3.4 Campaign-heavy topics

**[measured]** Campaign-titled docs as a share of docs carrying the topic:

| topic | 2010-19 | 2020-26 | topic | 2010-19 | 2020-26 |
|---|---:|---:|---|---:|---:|
| Safety | 2.12% | 2.58% | Health | 0.68% | 0.82% |
| Agriculture | 2.07% | 2.33% | Transport | 0.58% | 0.78% |
| Security | 1.24% | 1.91% | Education | 0.47% | 0.68% |
| Commerce | 1.82% | 1.49% | Welfare | 0.87% | 0.68% |
| Environment | 1.40% | 1.46% | Party | 0.00% | 0.54% |
| Energy | 0.69% | 1.33% | Finance | 0.59% | 0.36% |
| Legal | 0.74% | 0.88% | Trade | 0.00% | 0.28% |
| Tech | 1.57% | 0.84% | Credit | 0.36% | 0.15% |
| Tourism | 0.55% | 0.82% | Diplomacy | 0.41% | 0.00% |

**[reading]** Campaigns live in enforcement and mobilization domains: work safety, rural
and poverty work, public security, market order, pollution. They are nearly absent from
rule-heavy and external domains (Credit, Trade, Finance, Diplomacy). Tech is the one domain
where campaign framing FELL (1.57% to 0.84%) as its volume grew: the AI wave is framed as
plans and 意见, not as 专项行动, with the exception of the 2025 "AI+" 行动.

### 3.5 Are campaigns the delivery vehicle of attention bursts? Mostly no.

**[measured]**
- For the 19 mechanical attention-burst years from 2010 on, the within-topic campaign
  share is above the topic's 2010-25 median in 7 (chance is about 50%).
- Campaign-share bursts per topic (same rolling-median rule, >= 5 campaign docs) fall within
  one year of an attention burst in only 3 of 30 cases.
- Campaign bursts cluster in topics with NO attention burst: Environment (2018, 2022,
  2024), Legal (2010, 2022, 2026), Finance (2016, 2019), Security (2014, 2019, 2020, 2025),
  Commerce (2016, 2019, 2021, 2025).
- The three cases where the campaign IS the burst's vehicle: Agriculture 2018 (23
  campaign docs, 2.9% vs 1.9% median, the 脱贫攻坚 action), Health 2020 (13 docs, 1.1% vs
  0.5%), Safety 2023-24 (58 docs, 3.9% vs 1.7%, the 安全生产治本攻坚三年行动 of 2024-26, which
  is also visible in the district titles).

**[reading]** Attention bursts in this corpus are mostly carried by regulatory and planning
instruments (条例, 意见, 决定) and by sub-national news output, not by titled campaigns.
Campaigns are a steady enforcement rhythm inside a few domains, with their own cycle that is
largely orthogonal to agenda-level attention. The exceptions are the large national
mobilizations (poverty, pandemic, work safety), where the campaign and the attention burst
are the same event.

### 3.6 The proxy, and what the body text says instead

**[measured]** Documents mentioning a campaign term ANYWHERE (title, abstract or body, via
FTS; 攻坚 counted as 攻坚战 because the trigram index needs three characters):

| year | 专项行动 any / title | 攻坚战 any / title-攻坚 | all terms any-share | title-share |
|---|---:|---:|---:|---:|
| 2010 | 79 / 22 | 12 / 0 | 6.0% | 1.01% |
| 2014 | 94 / 10 | 8 / 1 | 5.1% | 0.40% |
| 2016 | 163 / 23 | 90 / 7 | 5.4% | 1.00% |
| 2018 | 271 / 24 | 277 / 42 | 5.1% | 0.87% |
| 2020 | 240 / 21 | 346 / 54 | 4.2% | 0.84% |
| 2022 | 563 / 45 | 482 / 59 | 5.8% | 0.76% |
| 2024 | 608 / 99 | 321 / 101 | 4.1% | 0.95% |
| 2025 | 808 / 105 | 333 / 78 | 4.8% | 0.79% |
| 2026* | 1,325 / 151 | 467 / 162 | 5.2% | 0.78% |

攻坚战 mention share of government docs: 0.1-0.5% (2005-15), 1.3% (2016), 1.1% (2017),
2.7% (2018), 2.9% (2019), 2.7% (2020), 2.2% (2021), 2.5% (2022), 1.6% (2023), 1.2% (2024),
1.1% (2025), 0.9% (2026). 脱贫攻坚 mentions: 59 (2016), 93, 213, 268, 435 (2020), 464
(2021), 288, 196, 123, 126, 292.

**[reading]**
- The title proxy captures roughly one in six documents that mention a campaign (title
  share ~0.8% vs any-mention ~5%). The ratio is stable, so the title series is a usable
  index of relative change but a poor count.
- By the any-mention measure, campaign vocabulary is a CONSTANT ~4-6% of government
  documents across the whole window. There is no secular rise in campaign talk, only in
  campaign TITLING at the center.
- The one clear hump is 攻坚战 2018-2022: the "three tough battles" (三大攻坚战: poverty,
  pollution, financial risk) announced at the 19th Party Congress in October 2017 and the
  December 2017 Central Economic Work Conference. Mentions triple in 2018, peak in 2019-20,
  and fall away after the February 2021 declaration that poverty alleviation was complete.
  That is a datable central signal followed by a corpus-wide body-text response within a
  year, which is the pattern Test 1 was looking for and the title measure cannot see.
- Genre of campaign-titled docs vs all docs: `other` 48% vs 42%, `action_plan` 18% vs 3%,
  `notice` 15% vs 9%, `work_plan` 5% vs 0.6%. Half of campaign-titled docs are news-like
  items. **[caveat]** The proxy therefore over-counts routine "we held a meeting on the
  campaign" items at the municipal and district levels and under-counts the body-only
  campaigns that the 攻坚战 series reveals.

---

## 4. Caveats

- **Coverage is the first-order confound.** The site mix changes every year. The
  unfiltered burst detector found 23 episodes; 7 are a single site entering or dumping an
  archive (SAMR 2024, Suzhou 2023, MOE 2008, Shenzhen civil affairs 2011/16, Longhua
  district 2022) and 2-3 more are a State Council archive batch (2008, 2010). Nothing in
  this memo should be cited without the Table 2 verdict column.
- **Topic tagger coverage is 62% overall** and 61-71% by year with no trend. The denominator
  is tagged docs, so untagged docs are assumed topic-neutral. The tagger is regex over title
  (and keywords), precision-biased; small topics (Credit 808 docs, Veterans 995) sit near the
  >= 20-docs floor in early years.
- **Annual resolution.** 21 points per series. Lead/lag inside a year is invisible. The
  pooled kurtosis test has little power at this length.
- **Genre drift.** Municipal, district and department sites publish more news-style items
  over time. Party's step and the Shenzhen bureaus' campaign rise are partly this.
- **Sub-national tiers are Guangdong-heavy.** Municipal = mostly Guangdong cities plus
  Suzhou, Wuhan, Chongqing; district and department = Shenzhen. "Municipal" findings are
  "Guangdong city" findings unless stated.
- **2026 is partial and compositionally unusual** (MIIT, department tier, truncated
  Shenzhen tiers) and is excluded from every statistic.
- **Title-lexicon proxy** for campaigns: ~1/6 recall against any-mention; news-item
  over-counting; the two-character 攻坚 cannot be FTS-matched.
- **Anchors are evidence of co-occurrence, not causation.** `diffusion_events` citers and
  `citation_rank` identify the highest-authority central instrument in or just before the
  burst year; they do not prove the burst followed from it.
- **Resolution floor.** Anchors and citer counts rest on the citation graph, which resolves
  ~52% of edges, so every citer count is a floor and `citation_rank` ranks only the resolved
  part. *(Added 2026-10-01 per `consistency-review.md` §2.)*
- **Publication is not adoption.** A burst in document share is a burst in published
  attention, not in implementation or spending. *(Added 2026-10-01.)*
- **Scope boundary.** Mechanism-level claims about a document record, with the coverage
  confound above. No regime-type labels. *(Added 2026-10-01.)*

---

## 5. Appendix: reproduction

All aggregation was one read-only Python pass over `file:documents.db?mode=ro` (the script
streams `id, site_key, substr(date_published,1,4), title, topics_algo, algo_doc_type,
citation_rank` for 2005-2026 and splits `topics_algo` on commas); statistics were computed
offline in pure Python (Gini, L-moments, binomial simulation with 400 draws per topic,
seed 7). The SQL equivalents of the core aggregates:

```sql
-- Government universe, docs and tagged docs per year (Table 0 denominators)
SELECT substr(d.date_published,1,4) yr,
       COUNT(*) docs,
       SUM(d.topics_algo IS NOT NULL AND d.topics_algo != '') tagged
FROM documents d JOIN sites s ON s.site_key = d.site_key
WHERE s.admin_level IN ('central','provincial','municipal','district','department')
  AND d.date_published >= '2005' AND d.date_published < '2027'
GROUP BY yr ORDER BY yr;

-- Topic share per year (explode the comma list; SQLite recursive CTE)
WITH RECURSIVE split(id, yr, lvl, topic, rest) AS (
  SELECT d.id, substr(d.date_published,1,4), s.admin_level, '', d.topics_algo || ','
  FROM documents d JOIN sites s ON s.site_key = d.site_key
  WHERE d.topics_algo != '' AND d.date_published >= '2005' AND d.date_published < '2027'
    AND s.admin_level IN ('central','provincial','municipal','district','department')
  UNION ALL
  SELECT id, yr, lvl, substr(rest, 1, instr(rest, ',') - 1), substr(rest, instr(rest, ',') + 1)
  FROM split WHERE rest != ''
)
SELECT yr, lvl, topic, COUNT(*) k
FROM split WHERE topic != ''
GROUP BY yr, lvl, topic;
-- share = k / tagged(yr, lvl) from the first query restricted to that level

-- Campaign-title share by year and level (Table 3)
SELECT substr(d.date_published,1,4) yr, s.admin_level,
       SUM(d.title LIKE '%专项行动%' OR d.title LIKE '%专项整治%' OR d.title LIKE '%攻坚%'
        OR d.title LIKE '%大会战%' OR d.title LIKE '%集中整治%' OR d.title LIKE '%百日行动%') camp,
       COUNT(*) docs
FROM documents d JOIN sites s ON s.site_key = d.site_key
WHERE d.date_published >= '2005' AND d.date_published < '2027'
  AND s.admin_level IN ('central','provincial','municipal','district','department')
GROUP BY yr, s.admin_level ORDER BY yr;

-- Any-field campaign mentions via the trigram FTS (terms of >= 3 chars only)
SELECT substr(d.date_published,1,4) yr, s.admin_level, COUNT(*)
FROM doc_search f JOIN documents d ON d.id = f.rowid JOIN sites s ON s.site_key = d.site_key
WHERE doc_search MATCH '攻坚战'
  AND d.date_published >= '2005' AND d.date_published < '2027'
GROUP BY yr, s.admin_level;

-- Anchors in a burst year: citation-matched diffusion events by topic and anchor year
SELECT anchor_id, anchor_title, substr(anchor_date,1,4) ay, source_level, COUNT(DISTINCT source_id) n
FROM diffusion_events
WHERE match_type = 'citation' AND topic = 'Health' AND ay IN ('2019','2020')
GROUP BY anchor_id, source_level ORDER BY n DESC;

-- Top citation_rank central docs carrying a topic in a year
SELECT d.id, d.title, d.citation_rank, d.site_key
FROM documents d JOIN sites s ON s.site_key = d.site_key
WHERE s.admin_level = 'central' AND d.date_published LIKE '2018%'
  AND (',' || d.topics_algo || ',') LIKE '%,Credit,%'
ORDER BY d.citation_rank DESC LIMIT 5;

-- Site composition of a topic-year (the LOSO input)
SELECT d.site_key, s.admin_level, COUNT(*) n
FROM documents d JOIN sites s ON s.site_key = d.site_key
WHERE d.date_published LIKE '2024%' AND (',' || d.topics_algo || ',') LIKE '%,Safety,%'
  AND s.admin_level IN ('central','provincial','municipal','district','department')
GROUP BY d.site_key ORDER BY n DESC LIMIT 5;
```

Burst rule, in words: share_y / median(share_{y-2}, share_{y-1}, share_{y+1}, share_{y+2})
>= 1.5 and (k_y - n_y p0) / sqrt(n_y p0 (1 - p0)) >= 3 with p0 the rolling-median share, and
k_y >= 20, for y in 2007..2025. Core set: `gov ndrc mof mofcom chinatax gd bj sh gz`.
