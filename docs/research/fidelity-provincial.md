# Provincial Fidelity: Cities Copy Their Province, Not the Center

*A worked analysis on the china-governance corpus (SQLite on the droplet). All figures pulled
read-only from the live `documents.db` on 2026-10-01. Closes the gap flagged in
`diffusion-fidelity.md` §3.2 and §6: every anchor in `diffusion_events` is central, so the
province-to-city hop was unmeasured. This memo builds the province-to-city pairs itself, scores
them with the same character 5-gram containment, and then joins the two hops into full
central-to-province-to-city chains. SQL and the sketch are in the appendix.*

---

## 0. The question and the short answer

**Question.** When a city, district or municipal bureau implements a *provincial* instrument,
how much of the provincial text does it reuse? Is the province-to-city hop tighter than the
central-to-province hop measured in the fidelity memo? And in a nested cascade (central C,
provincial P, municipal M), does the city's text descend from the province's rewrite or straight
from the central text?

**Short answer.** The province-to-city hop is much tighter than the central-to-province hop.
Across **5,765 scored same-province pairs** (5,462 of them Guangdong), the median sub-provincial
document shares **8.7%** of its 5-grams with the provincial instrument, against 5.6% for the
central hop. The band split is **relay 9.1% / mid 18.8% / elaboration 72.2%**, against
**1.9 / 9.8 / 88.3** at the central hop. Relay is five times as common. The mid band (localized
paraphrase, provincial skeleton kept) is twice as common. [measured]

The relay mechanism is different from the central hop. At the central hop relay was a
provincial 转发 forwarding notice. At the provincial hop only 20% of relays are 转发 notices.
**75% are city instruments with the city's own name and 文号 that reproduce the provincial body
nearly verbatim**: 汕尾市残疾儿童康复救助实施办法 (0.96 of the provincial 办法), 阳江市城乡居民基本养老
保险实施办法 (0.91), 韶关市民宿管理暂行办法 (0.91). This is re-issuance by name substitution, and
it is a prefecture-city practice. Districts and Shenzhen bureaus do not do it (relay 0.2% and
1.1%). [measured]

**The three-hop finding.** 2,444 full chains exist (509 central anchors, 561 provincial
implementations, 1,907 municipal documents). In **92.8%** of them the city's text is closer to
the province than to the center. The median city document is 20.4% provincial text and 5.4%
central text. Partitioning the city's 5-grams: 3.8% are in both P and C (central text that
passed through the province), 11.7% are in P only (provincial rewrite), **0.8% are in C only**
(central text the province did not carry). The city's text descends from the province. Where it
contains central text at all, five-sixths of that text arrived via the provincial version.
**The cascade rewrites at each hop and the city reads only the hop above it.** [measured]

Validation on the 2024 以旧换新 cascade confirms it: the fidelity memo found all 17 以旧换新
re-issuances below 0.3 against the central text; against the Guangdong 实施方案 the same cities
sit at 0.50 to 0.77 (8 of 11 same-instrument pairs above 0.5). The tight cascade the consumption
memo saw is a province-to-city phenomenon. [measured]

---

## 1. Method

**Targets (P).** Provincial-tier framework documents: `sites.admin_level='provincial'` (province
portals and provincial departments), plus the Beijing and Shanghai municipal bureaus (`bjb_*`,
`shb_*`) and the Chongqing portal (`cq`), which are province-tier units. Framework = `algo_doc_type`
in the atlas `FW_GENRES` set (regulation, opinion, action_plan, strategy, plan, law, decree,
decision, work_plan) or a title cue (意见/规定/办法/规划/行动方案/实施方案/条例/纲要/决定/细则),
excluding explainers and readouts. **15,436** targets.

**Sources (M).** Sub-provincial documents: `admin_level` municipal (prefecture cities, Shenzhen
portals), district, or department (the 13 Shenzhen bureaus). **113,058** candidates. Each is
mapped to its province by site key (Guangdong: `gd*`, 16 gkmlpt cities, `sz*`, Shenzhen bureaus;
Jiangsu: `js*`, 苏州 and 7 cities, `njd_*`; Beijing: `bjd_*`; and so on).

**Pairs.** Two confirmed match types, same province only, source dated on or after target:

- `citation` (n=6,270): a resolved `citations` edge M → P. Levels come from `sites.admin_level`,
  not the stale `citations.*_level`. 6,670 cross-province edges were dropped. Inspection shows
  they are resolver noise, not real cross-province borrowing: Shenzhen bureaus "citing" Beijing
  copies of national laws (`ga`→`bj` 855, `szlhq`→`bj` 302) and Guangdong cities "citing" Fujian
  department mirrors of central texts (`fj_wjw`, `fj_yjt`). The same-province restriction removes
  them. *(Note 2026-10-01: 6,670 is a pre-fix count. These edges are the mirror/proxy class that
  `citation-network-structure.md` §1.3-§1.4 measures from the other side; the exact-title class
  was fixed in `cd42903`/`c979a82` and the count will differ on a rebuild. The chains in §4
  inherit the 24,599-row `diffusion_events` build on the C→P leg; that table held 32,825 rows on
  2026-10-01. See `consistency-review.md` H2 and L7.)*
- `title_reissue` (n=352): the source title passes the atlas issuance filter and contains the
  target's genre stem (the `《》` core or title, place prefix stripped with
  `^[一-鿿]{2,4}(省|市|自治区)`, then `genre_stem()` from `build_diffusion_events.py`, minimum 8
  characters), with the latest same-province provincial issuance before the source date taken as
  the target. Verbatim title mirrors are excluded. Pairs already matched by citation are not
  double-counted.

**Scoring.** Both bodies over 500 characters. **5,765 of 6,622 pairs (87.1%)**: citation 5,515,
title_reissue 250. By source tier: city 4,788 of 5,361 (89%), department 533 of 732 (73%),
district 444 of 529 (84%). Bodies HTML-stripped, whitespace-stripped, capped at 150k characters;
character 5-grams; `ovlp_src` = |grams(M) ∩ grams(P)| / |grams(M)|. Also `ovlp_anc`, Jaccard and a
boilerplate-stripped variant (1,633 grams present in ≥2% of a random 1,000-document sample).
Bands: relay > 0.7, mid 0.3 to 0.7, elaboration < 0.3. Identical to the fidelity memo.

**Chains.** For each scored P that is itself a `diffusion_events` source (match_type citation or
title_reissue, central anchor C with body > 500), every (C, P, M) triple. For each: `ovlp(M,P)`,
`ovlp(M,C)`, `ovlp(P,C)`, and a four-way partition of M's grams (in both P and C, P only, C
only, neither). The C→P leg is recomputed here, not read from the memo's CSV.

**Predictors.** Lag, source tier, 转发 flag, P and M `algo_doc_type`, P topic (`topics_algo`,
first tag), P fiscal density (12 money terms per 10k characters, quartiles), lengths. An
implementing subset keeps M genres action_plan, work_plan, policy_issuance, opinion, notice,
regulation, decision, strategy, subsidy (n=4,327 in Guangdong).

**Guangdong dominance.** 5,462 of 5,765 pairs (94.7%) and 2,313 of 2,444 chains (94.6%) are
Guangdong. Guangdong is the only province with portal + 16 cities + districts + bureaus all
crawled. Jiangsu has 200 pairs (苏州 and 7 cities), Beijing 56 (12 districts), Chongqing 21,
others under 10. The headline tables below are Guangdong; §2.1 reports the all-province
version. Treat every finding as a Guangdong finding that other provinces agree with on small n.

---

## 2. The distribution

**Table 2a. Histogram of `ovlp_src`, Guangdong, n=5,462** (evidence: scored CSV).

| band | n | share | fidelity memo, central hop (all levels) |
|---|---:|---:|---:|
| 0.0 to 0.1 | 2,906 | 53.2% | 67.9% |
| 0.1 to 0.2 | 637 | 11.7% | 13.4% |
| 0.2 to 0.3 | 391 | 7.2% | 7.1% |
| 0.3 to 0.4 | 272 | 5.0% | 4.6% |
| 0.4 to 0.5 | 256 | 4.7% | 2.7% |
| 0.5 to 0.6 | 264 | 4.8% | 1.5% |
| 0.6 to 0.7 | 230 | 4.2% | 1.0% |
| 0.7 to 0.8 | 236 | 4.3% | 0.7% |
| 0.8 to 0.9 | 182 | 3.3% | 0.6% |
| 0.9 to 1.0 | 88 | 1.6% | 0.6% |

Median 0.087. Mean 0.224. Quartiles 0.033 and 0.359. Boilerplate-stripped median 0.078; the
bands move by less than half a point (relay 9.0%, elaboration 72.6% corpus-wide).

**Shape.** Still a decaying tail from zero, but the tail is fat. From 0.4 upward every tenth
holds 3 to 5% of pairs, where the central hop held 0.6 to 2.7%. The upper quartile is 0.36 at
this hop against 0.14 at the central hop. A quarter of sub-provincial documents that cite or
re-issue a provincial instrument reuse more than a third of its text.

### 2.1 Side by side with the central hop

| hop | n | median | relay | mid | elab |
|---|---:|---:|---:|---:|---:|
| central → provincial (memo §3.2) | 6,809 | 0.074 | 3.3% | 13.7% | 83.0% |
| central → municipal (memo §3.2) | 4,539 | 0.051 | 0.6% | 7.8% | 91.6% |
| central → district (memo §3.2) | 801 | 0.030 | 0.0% | 1.1% | 98.9% |
| central → all (memo §2) | 13,509 | 0.056 | 1.9% | 9.8% | 88.3% |
| **province → city** (this memo, all prov.) | 4,788 | **0.115** | **10.8%** | **21.8%** | **67.5%** |
| **province → Shenzhen bureau** | 533 | 0.050 | 1.1% | 4.7% | 94.2% |
| **province → district** | 444 | 0.041 | 0.2% | 3.2% | 96.6% |
| province → all sub-provincial | 5,765 | 0.087 | 9.1% | 18.8% | 72.2% |

**Do cities copy their province more than provinces copy the center? Yes, by a wide margin.**
[measured] The province-to-city row (median 0.115, relay 10.8%) sits above the
central-to-province row (0.074, 3.3%) on every statistic. The same city that shares 5.1% of its
text with the State Council document shares 11.5% with the Guangdong document, and relays it 18
times as often (10.8% vs 0.6%).

Districts and bureaus do not follow. Against their province they look exactly as they did
against the center: median 0.04 to 0.05, relay near zero, 94 to 97% elaboration. The copying
tier is the prefecture city. One level below it, text is authored again.

**All-province version.** Guangdong 5,462 pairs: median 0.087, relay 9.3%, mid 18.7%, elab
72.0%. Jiangsu 200: median 0.112, relay 8.0%, mid 25.0%, elab 67.0%. Beijing 56 (districts only):
median 0.038, relay 0%, mid 7.1%, elab 92.9%. Chongqing 21: 0.083, 0%, 19%, 81%. Jiangsu agrees
with Guangdong in level and shape; Beijing agrees with the district row. The all-province split
(9.1 / 18.8 / 72.2) is within half a point of the Guangdong split because Guangdong is 95% of
it. [measured, Guangdong-dominated]

### 2.2 What the relay band is

506 Guangdong relays. 401 are near-identical both ways (`ovlp_anc` > 0.7). Decomposed by the
source title:

| kind | n | share | both-ways | median lag | mechanism |
|---|---:|---:|---:|---:|---|
| 转发 forwarding notice | 102 | 20% | 97% | 38 d | 转发省府办公厅印发…的通知, the memo's relay type |
| verbatim mirror (provincial title in source title) | 23 | 5% | 78% | 165 d | a bureau or district portal reposting the provincial text |
| **renamed re-issuance** | **381** | **75%** | 75% | 181 d | 汕尾市…实施办法 reproducing 广东省…实施办法 |

The renamed re-issuance is the new object. It is a city instrument, carrying the city's name and
usually a city 文号, whose body is the provincial body with 广东省 replaced by the city name and
the odd paragraph dropped. Genre: 212 action_plan, 61 policy_issuance, 51 work_plan, 18 notice,
15 strategy, 12 opinion, 4 regulation. It is concentrated in the smaller prefecture cities:
揭阳 81, 阳江 74, 江门 53, 惠州 43, 汕尾 38, 韶关 29, 中山 22, 珠海 22. 广州 6, 深圳 3.

Excluding 转发 and mirror rows leaves 5,009 Guangdong pairs with median 0.079, relay 7.6%, mid
18.5%, elaboration 73.9%. The relay rate without any forwarding notice at all is still four
times the central hop's rate with them. At the central hop, stripping 转发 made relay nearly
vanish. Here it does not. [measured]

**Re-based on the union pair set (2026-10-07).** The table above and the 381 are citation-only
(resolved citations plus `title_reissue`, 5,462 scored Guangdong pairs). `pair-channels.md`
pooled citation ∪ title_reissue ∪ localized_of in `scripts/rnd/analysis/pairs.py`. Re-run
read-only on the droplet with `nice -n 19 python3 scripts/rnd/analysis/pairs.py --report --csv
pairs_union.csv --workers 2` (166 s, two workers, beside the nightly crawl). Identity build
measured on: the 2026-10-06 nightly's `doc_identity`, 2,592 `localized_of` rows (`SELECT
COUNT(*) FROM doc_identity WHERE localized_of IS NOT NULL`), pre-A6 schema with no `province`
or `instrument_kind` column, so the `localized_of` trigger is not date-ordered (530 negative-lag
edges dropped by the lag rule) and the framework gate is the old `algo_doc_type` + title-cue
gate. The date-ordered A6 build (1,958 rows) was not yet on the droplet. Guangdong
province-to-city at the memo's gate: citation basis 5,954 pairs, 5,297 scored, 474 relays
(8.9% relay, 18.0% mid, 73.0% elaboration); union 6,287 pairs, 5,458 scored, 496 relays (9.1%,
18.3%, 72.6%). Decomposition of the relays by the table's rule (转发 in the source title; the
parent's title core inside the source title; the rest), citation basis then union: 转发 81 then
82 (17%, 98% both-ways, median lag 44 d), mirror 16 then 16 (3%, 75%, 172 d), **renamed
re-issuance 377 then 398** (80%, 75% both-ways, 184 d). The union adds 21 renamed re-issuances
and one 转发 notice: 13 seen by `title_reissue` alone, 5 by `title_reissue` + `localized_of`, 4
by `localized_of` alone. Genre of the 398: action_plan 217, policy_issuance 70, work_plan 54,
strategy 18, notice 17, opinion 10, decision 4, regulation 4. Cities: 揭阳 86, 阳江 74, 江门 54,
惠州 46, 汕尾 42, 珠海 26, 韶关 25, 中山 21, 云浮 7, 广州 6. Excluding 转发 and mirror rows: citation
4,872 scored, median 0.075, relay 7.7%, mid 17.8%, elaboration 74.5%; union 5,028 scored, 0.077,
7.9%, 18.0%, 74.0%. The split reads 80 / 17 / 3 on both bases against the table's 75 / 20 / 5;
that gap is the pair-set reconstruction and the mirror rule (`pair-channels.md` §7), not the
union. Jiangsu province-to-city: 14 relays on both bases (12 renamed, 2 转发, all Suzhou), the
union adds none. One caveat on the Jiangsu citation basis: it is 473 pairs, 426 scored, relay
3.3% here, not the 200 scored, 8.0% in §2.1; the builder's province derivation and the Suzhou
date rule changed between the runs (`b7162c8`, `5465b8e`) and 456 of the 473 pairs are Suzhou
at a median lag of 777 days. That shift sits in the citation basis, not in the union, and is
logged here, not resolved. Net: the relay share is a floor by 0.2 points, the relay count by
about 5%, and the renamed re-issuance count by 21. The gate is the larger lever (637 against
474 relays with it off, `pair-channels.md` §5). [measured]

### 2.3 What the mid band is

1,022 Guangdong pairs. Typical rows: 中山 turning the provincial 森林防火工作责任制 into a 中山市…
实施办法, 阳江 turning the provincial 自然资源统一确权登记 方案 into its own 实施方案, 中山 turning
the provincial 推动非户籍人口在城市落户 方案 into a city 实施方案. Section structure and most
boilerplate are kept; targets, named agencies and local figures are swapped. This is the
localized paraphrase the memo found to be "the modal form of provincial implementation of a
central 意见". At the provincial hop it is the modal form of city implementation of a provincial
方案, and it is twice as common.

---

## 3. Predictors (Guangdong)

All tables: n, median `ovlp_src`, relay share, mid share, elaboration share.

### 3.1 Match type

| match_type | n | median | relay | mid | elab |
|---|---:|---:|---:|---:|---:|
| citation | 5,222 | 0.085 | 9.4% | 17.9% | 72.7% |
| title_reissue | 240 | 0.250 | 6.2% | 36.7% | 57.1% |

Title re-issuance has a median three times the citation median and a mid band twice as wide. 28%
of title re-issues are 机构编制 (三定) 规定 for city bureaus matching a provincial 三定 template,
which inflate the figure; excluding them, median 0.126 (n=172). Small n and a noisier matcher
than the citation path; treat as supporting evidence only. [measured, small n]

### 3.2 Tier, with and without forwarding

| source tier | n | median | relay | mid | elab | 转发 share |
|---|---:|---:|---:|---:|---:|---:|
| prefecture city | 4,569 | 0.116 | 10.9% | 21.7% | 67.4% | 7.7% |
| Shenzhen bureau | 533 | 0.050 | 1.1% | 4.7% | 94.2% | 2.1% |
| district | 360 | 0.039 | 0.3% | 1.7% | 98.1% | 0.0% |
| city, 转发 excluded | 4,215 | 0.106 | 9.5% | 22.1% | 68.4% | |
| city, implementing subset | 4,109 | 0.145 | 12.0% | 23.9% | 64.0% | 8.5% |
| district, implementing subset | 65 | 0.066 | 1.5% | 7.7% | 90.8% | |

The city row survives every cut. Within implementing instruments a city reuses a median 14.5% of
the provincial text and relays 12% of the time. Districts and bureaus stay below 7% median and
2% relay under the same cut.

**Site composition (cities, n ≥ 40).** 阳江 393 pairs, median 0.184, relay 19.6%; 江门 694,
0.147, 12.5% (转发 in 18.4% of titles); 珠海 480, 0.145, 5.6%; 惠州 544, 0.128, 12.5%; 深圳 118,
0.123, 4.2%; 中山 409, 0.120, 5.9%; 汕尾 308, 0.114, 17.2%; 韶关 297, 0.107, 10.4%; 揭阳 667,
0.096, 16.0%; 云浮 78, 0.081, 7.7%; 广州 507, 0.075, 2.4%. The two largest cities (广州, 深圳)
relay least and sit at the bottom of the median range. The eastern and western prefectures
(揭阳, 汕尾, 阳江, 江门, 惠州) relay 12 to 20%. Districts and bureaus: 大鹏 129 pairs 0.034, 龙华
102 0.048, 龙岗 45 0.036, 卫健委 57 0.033, 民政局 74 0.069, all with 0 to 3% relay. [measured]

### 3.3 Lag

| lag from provincial instrument | n | median | relay | mid | elab | 转发 share |
|---|---:|---:|---:|---:|---:|---:|
| ≤ 30 days | 129 | 0.612 | 43.4% | 24.0% | 32.6% | 40.3% |
| 31 to 90 days | 371 | 0.481 | 31.8% | 29.4% | 38.8% | 18.3% |
| 91 to 365 days | 1,519 | 0.287 | 15.8% | 33.1% | 51.1% | 5.7% |
| 1 to 3 years | 1,419 | 0.078 | 5.2% | 16.0% | 78.8% | 4.5% |
| > 3 years | 2,024 | 0.044 | 0.9% | 7.5% | 91.6% | 4.7% |

Spearman rho (lag vs overlap) = **−0.50** (all provinces −0.47), against −0.28 at the central hop.
Lag is the dominant predictor and it is stronger here. A city document issued within a year of
the provincial instrument has a median overlap of 0.29 and relays or paraphrases it half the
time. After three years the citing document is a new instrument with the old one as authority.
Median lag by band: elaboration 967 days, mid 252, relay 148. The renamed re-issuances in §2.2
have median lag 181 days, so the fast relay (38 days) is the 转发 notice and the half-year relay
is the renamed instrument. [measured]

### 3.4 Genre of the provincial instrument (implementing subset, n=4,327)

| P genre | n | median | relay | mid | elab |
|---|---:|---:|---:|---:|---:|
| regulation (条例/办法/规定) | 804 | 0.045 | 1.0% | 8.6% | 90.4% |
| decision | 50 | 0.063 | 8.0% | 10.0% | 82.0% |
| strategy | 264 | 0.068 | 12.1% | 13.6% | 74.2% |
| opinion (意见) | 506 | 0.119 | 7.5% | 23.3% | 69.2% |
| notice | 692 | 0.139 | 9.7% | 22.5% | 67.8% |
| policy_issuance | 448 | 0.199 | 14.7% | 28.6% | 56.7% |
| action_plan | 1,318 | 0.297 | 17.9% | 31.8% | 50.3% |
| work_plan | 200 | 0.403 | 24.0% | 35.0% | 41.0% |

Same ordering as the central hop, steeper slope. Rules are cited as authority and rewritten
(90% elaboration, the same 90 to 94% the memo found). 方案 are copied: a provincial action_plan
is reproduced or paraphrased by half its city implementers, and a provincial work_plan by 59%.
By source genre the same holds: city action_plan median 0.299 (relay 16.9%, mid 32.9%), work_plan
0.207, opinion 0.140, regulation 0.101, policy_issuance 0.072, announcement 0.051 with zero relay.
The 方案-to-方案 pair is the carrier of text at this hop. [measured]

### 3.5 Money

Provincial fiscal density quartile (money terms per 10k characters), all Guangdong pairs:

| quartile | n | median | relay | mid | elab |
|---|---:|---:|---:|---:|---:|
| q1 (no money terms) | 1,366 | 0.052 | 5.6% | 14.1% | 80.3% |
| q2 | 1,365 | 0.069 | 8.7% | 16.4% | 74.9% |
| q3 | 1,365 | 0.124 | 12.2% | 22.4% | 65.3% |
| q4 (highest) | 1,366 | 0.130 | 10.5% | 21.9% | 67.6% |

Spearman rho = 0.21 (memo: 0.24). Within the implementing subset: q1 0.064, q2 0.146, q3 0.202,
q4 0.185. The money effect is the same size as at the central hop. It doubles the median and
adds about five points of relay. It is not what separates this hop from the central one; lag and
genre are. [measured]

### 3.6 Topic (implementing subset, n ≥ 30)

Most copied: Personnel 139 pairs, median 0.287; Security 39, 0.258; Commerce 60, 0.257; Health
209, 0.229; Welfare 220, 0.204; Agriculture 331, 0.196; Education 162, 0.189. Least: Emergency
213, 0.028; Weather 81, 0.031; Tech 70, 0.070; Legal 105, 0.099; Energy 44, 0.102; Government
276, 0.106. Health and welfare are relayed 14 to 15% of the time. Agriculture and welfare
were the most templated topics at the central hop too; health and personnel join them here.
Technology stays in the lower half at both hops, consistent with the AI+ memo. [measured]

### 3.7 Length and where the variance lives

Provincial instruments of 10k to 20k characters are the most copied (median 0.182, relay 18.3%);
those under 2k the least (0.041). Source documents of 5k to 10k characters have the highest relay
(14.2%); sources over 20k have median 0.008 (the denominator swamps any shared passage).

In the implementing subset, **60% of the variance in overlap is between provincial targets and
5% is between source sites** (memo: 53% and 14%). The instrument explains even more here, and
the locality less. Among 549 targets with at least three scored sources, 63.4% have no relay and
0.7% are all-relay; the rest are mixed. The same provincial 方案 is relayed by one city and
rewritten by another. [measured]

---

## 4. The three-hop chain

### 4.1 Count and composition

**2,444 full chains** (distinct C, P, M triples): 509 central anchors, 561 provincial
implementations, 1,907 sub-provincial documents, 680 distinct C→P legs, 2,076 distinct P→M
pairs. Guangdong 2,313, Jiangsu 110, Beijing 10, Fujian 4, Chongqing 3, Heilongjiang 2, Ningxia 2.
Source tier: city 2,221, Shenzhen bureau 143, district 80. Both legs are overwhelmingly citation
edges (C→P 2,407 citation / 37 title_reissue; P→M 2,395 / 49). Median lags: C→P 255 days, P→M
365 days, end to end 765 days. [measured]

### 4.2 Does the city descend from the province or the center?

| statistic, all 2,444 chains | median | Q1 | Q3 |
|---|---:|---:|---:|
| ovlp(M, P): share of city text that is provincial text | **0.204** | 0.057 | 0.575 |
| ovlp(M, C): share of city text that is central text | **0.054** | 0.022 | 0.177 |
| ovlp(P, C): share of provincial text that is central text | 0.174 | 0.054 | 0.336 |
| city grams in both P and C (central text carried through P) | 0.038 | 0.012 | 0.143 |
| city grams in P only (provincial rewrite) | **0.117** | 0.038 | 0.363 |
| city grams in C only (central text P did not carry) | **0.008** | 0.002 | 0.020 |
| city grams in neither (local authorship) | 0.765 | 0.400 | 0.930 |

**The city is closer to the province than to the center in 92.8% of chains** (92.1% with
boilerplate stripped). Four patterns, by the P-only vs C-only partition:

| pattern | rule | share |
|---|---|---:|
| province-descended | P-only ≥ 2 × C-only | **57.0%** |
| locally authored | ovlp(M,P) < 0.1 and ovlp(M,C) < 0.1 | 36.6% |
| mixed | neither dominates | 4.8% |
| center-descended | C-only ≥ 2 × P-only | **1.6%** |

[measured] The city's borrowed text is the province's text. Its share of central text (0.054) is
almost entirely the subset the province also kept (0.038 of 0.046 traceable to C; 83% at the
medians). Central text that the province dropped does not reappear in the city document: C-only
is 0.8% at the median and 2.0% at the upper quartile. Cities do not read past their province.

**Pass-through.** In the 768 chains where the province itself kept more than 30% of the central
text, the city holds 17.7% of its grams in both P and C and 10.5% in P only. In the 1,676 chains
where the province rewrote (ovlp(P,C) ≤ 0.3), the city holds 2.2% in both and 12.1% in P only.
Central text reaches the city only when the province carried it; when it does, roughly 55% of what
the city takes from the province is central text. The pattern split by the province's own
fidelity: when the province relayed the center (114 chains), the city is province-descended in
67.5% and center-descended in 3.5%; when the province elaborated (1,676), province-descended
54.3%, center-descended 1.1%. There is no case where the province's rewriting pushes cities to
go to the source. [measured]

**Relay across two hops is rare.** 392 chains have ovlp(M,P) > 0.7; 18 have ovlp(M,C) > 0.7; 15
have both. Of the 114 chains whose province relayed the center, 26 see the city relay the
province, 16 see the city relay the center. Verbatim text survives two hops in under 1% of chains.

**By tier.** City: ovlp(M,P) 0.236, ovlp(M,C) 0.060, P-only 0.140. Shenzhen bureau: 0.050, 0.025,
0.030. District: 0.050, 0.017, 0.026. 转发 notices as M (168 chains): ovlp(M,P) 0.496, ovlp(M,C)
0.092, P-only 0.201; a city forwarding notice forwards the provincial version, which has already
rewritten the center.

**The 1.6% center-descended cases.** 39 chains. Half are mirrors (a Shenzhen bureau reposting
the State Council 中期财政规划 text, ovlp(M,C) = 1.0, while the matched P is the Guangdong
实施意见). The rest are a real minority pattern: 慢性病中长期规划 (2017–2025), where the
province relayed the central 规划 (ovlp(P,C) 0.72) and 阳江, 江门, 中山 drew on the central text
directly (ovlp(M,C) 0.55 to 0.80 with C-only 0.35 to 0.47), as did the 十三五 结核病防治规划 and
the 困境儿童保障 意见 in 阳江. These are national health plans with mandatory structure and
numbered targets. They are the exception that shows the rule.

---

## 5. Validation: the 2024 以旧换新 cascade

**Province-to-city pairs.** 15 pairs on Guangdong provincial instruments with 以旧换新 in the
title. 13 are city implementations; 2 are the 2025 省政府工作报告 reposted by the emergency bureau,
which cites without implementing (0.005). The 11 same-instrument implementation pairs:

| provincial instrument | city | lag | ovlp(M,P) | memo: same city vs central |
|---|---|---:|---:|---:|
| 推动消费品以旧换新行动方案 (办公厅) | 惠州 行动方案 | 25 d | **0.771** | ≤ 0.25 |
| 以标准提升牵引设备更新和消费品以旧换新行动方案 | 韶关 行动方案 | 31 d | **0.770** | |
| 推动消费品以旧换新行动方案 | 揭阳 行动方案 | 95 d | 0.616 | |
| 用好超长期特别国债资金加力支持消费品以旧换新实施方案 | 韶关 实施方案 | 5 d | 0.612 | |
| 加力支持…实施方案 | 汕尾 行动方案 | 8 d | 0.598 | |
| 以标准提升…行动方案 | 阳江 实施方案 | 45 d | 0.585 | |
| 推动消费品以旧换新行动方案 | 中山 工作方案 | 38 d | 0.517 | |
| 推动大规模设备更新和消费品以旧换新实施方案 (省政府) | 惠州 实施方案 | 25 d | 0.504 | |
| 推动大规模设备更新…实施方案 | 中山 实施方案 | 17 d | 0.272 | |
| 推动消费品以旧换新行动方案 | 韶关 以旧换新及促进消费行动方案 | 31 d | 0.242 | |
| 以标准提升…行动方案 | 惠州 以标准提升…行动方案 | 25 d | 0.175 | 0.031 |

Median 0.585. 8 of 11 above 0.5, 2 above 0.7. The fidelity memo put every one of these cities at
0.06 to 0.25 against the central text and the Guangdong 实施方案 at 0.284, the highest point. The
reading it offered ("cities draft under the provincial 实施方案") is confirmed: the cities drafted
under the provincial 方案 by copying half to three-quarters of it. 惠州's 以标准提升 plan, the
memo's lowest case at 0.031 against the center, is also the lowest here at 0.175; that one city
plan was authored. [measured]

**Chains.** 28 以旧换新 chains. Taking 惠州 推动消费品以旧换新行动方案 against the two central
anchors: against the State Council 行动方案 (ovlp(P,C) 0.065), the city holds 0.771 provincial text,
0.059 central, 0.714 P-only, 0.003 C-only. Against the 商务部等14部门 行动方案 (ovlp(P,C) 0.291),
the city holds 0.265 central text, of which 0.261 is in both P and C and 0.004 in C only. The
central text in 惠州's plan is exactly the central text Guangdong kept. 韶关's 加力支持 实施方案
holds 0.61 of the provincial 实施方案 and 0.02 to 0.06 of each of the three central 细则 behind
it, C-only 0.002 to 0.005. The nested cascade passed money rules from the center through a
provincial rewrite to a city copy of the rewrite. [measured]

---

## 6. Findings

**1. The province-to-city hop is the tight one.** Median 0.115 for cities, relay 10.8%, mid
21.8%, against 0.074 / 3.3% / 13.7% for the central-to-province hop. Cities copy their province
more than provinces copy the center, by every statistic, and the gap holds with forwarding
notices removed (relay 9.5%) and within implementing instruments (12.0%).

**2. Relay at this hop is re-issuance by name substitution, not forwarding.** 75% of Guangdong
relays are city instruments under their own title and 文号 reproducing the provincial body; 20%
are 转发 notices. The renamed re-issuance is a prefecture-city practice (揭阳, 阳江, 江门, 惠州,
汕尾 lead; 广州 and 深圳 barely do it), issued about six months after the provincial instrument,
and concentrated in action_plan and work_plan genres.

**3. The copying tier is the prefecture city and only that tier.** Districts (0.041, 0.2% relay)
and Shenzhen bureaus (0.050, 1.1%) treat the provincial text as they treated the central text:
as authority to cite, not text to reuse. The fidelity memo's monotonic level gradient was a
central-anchor artifact in one respect: the city is not a weak copier of the center, it is a
strong copier of the province. The district really does author.

**4. The city descends from the province, not the center.** In 2,444 full chains the city is
closer to the province in 92.8%; 57% are province-descended against 1.6% center-descended.
Central text reaches the city only through the provincial version (C-only 0.8% at the median).
The cascade rewrites at each hop and each tier reads only the tier above. Verbatim text survives
both hops in under 1% of chains.

**5. Lag and genre predict; money and locality do not add much.** Lag rho −0.50 (central hop
−0.28); a city document within 90 days of the provincial 方案 has a median overlap near 0.5.
Provincial work_plan and action_plan are copied by half their implementers, regulations by 1%.
Fiscal density has the same modest effect as at the central hop (rho 0.21). 60% of the variance
is between provincial instruments, 5% between cities.

**6. The consumption cascade is confirmed as a province-to-city phenomenon.** The 以旧换新
cities sit at 0.50 to 0.77 against the Guangdong 方案 after sitting at 0.06 to 0.25 against the
center. "Tight cascade" and "elaboration" were both right; they described different hops.

---

## 7. Honesty

- **Guangdong is 95% of the data.** The all-province figures are Guangdong figures. Jiangsu (200
  pairs) agrees in level and shape; Beijing (56, districts only) agrees with the district row.
  Fujian, Chongqing, Heilongjiang, Ningxia, Tibet contribute under 25 pairs each. No other
  province has the portal + cities + districts + bureaus coverage that produces nested pairs.
  Whether the eastern/western Guangdong prefectures' re-issuance habit is general to Chinese
  prefecture cities or a Guangdong practice cannot be settled from this corpus.
- **Resolution is ~52%.** Pairs come from resolved citation edges. Unresolved edges (coverage
  gaps, see CLAUDE.md) are not sampled at random: a city citing a provincial document the corpus
  lacks is invisible. The absolute pair count is a floor. Nothing here suggests the missing pairs
  differ in fidelity, but it is not tested.
- **Body coverage.** 87.1% of pairs were scored. The department tier (Shenzhen bureaus) is again
  the gap at 73%. Attachment-only documents (cover note in `body_text_cn`, plan in a PDF) pass
  the 500-character floor in some cases and score as elaboration when they should not score.
- **Boilerplate upper bound.** Shared notice chrome inflates overlap. The 2%-frequency strip moves
  the median from 0.087 to 0.078 and the bands by under half a point. Rarer formulaic passages
  still count. All overlaps are upper bounds on substantive reuse. At this hop the inflation is
  larger in absolute terms than at the central hop because provincial and city notices share
  more chrome (省政府办公厅 / 市政府办公室 formulas).
- **Title re-issuance is the weaker matcher.** 250 pairs, 28% of them 三定 规定 templates. The
  citation path (5,515 pairs) carries every headline result on its own; the title path is
  reported for completeness and its medians should not be quoted alone.
- **Cross-province edges were dropped as noise.** 6,670 edges. Inspection found them dominated by
  resolver mis-targeting (a national law resolved to a Beijing or Fujian copy). Real
  cross-province borrowing, if it exists, is excluded along with the noise.
- **Chains inherit `diffusion_events` on the C→P leg.** That table's anchor pooling and
  explainer-exclusion rules (atlas §7) apply. The C→P overlap was recomputed, not read from the
  memo's CSV, so the 680 legs here have median 0.181, higher than the memo's 0.074 for provincial
  sources, because a provincial document that is itself cited onward by cities is an
  implementation instrument, not a mere citer.
- **Citation is not implementation.** Reports, announcements and explainers cite provincial
  instruments without implementing them. The implementing subset (n=4,327) holds every ordering.
  Genre labels are regex (`algo_doc_type`).
- **Chronology, not causation.** Lag ordering and text containment together say the city text
  came after and from the provincial text. They do not say the city would have written
  differently had the province not issued, nor anything about implementation on the ground.
- **Scope boundary.** Coverage bias (95% Guangdong), ~52% resolution so every pair count is a
  floor, and publication is not adoption. Mechanism-level claims about a document record. No
  regime-type labels. *(Added 2026-10-01 per `consistency-review.md` §2.)*
- **No stored artifacts.** The scoring script and the two result CSVs live in the session
  scratchpad, not the repo. The appendix reproduces them from the live DB in about 90 seconds.

---

## Appendix A. Queries

```sql
-- Provincial-tier framework targets (15,436)
SELECT d.id, d.site_key, d.title, substr(d.date_published,1,10), d.algo_doc_type, length(d.body_text_cn)
FROM documents d JOIN sites s ON s.site_key = d.site_key
WHERE (s.admin_level = 'provincial' OR d.site_key = 'cq'
       OR d.site_key LIKE 'bjb\_%' ESCAPE '\' OR d.site_key LIKE 'shb\_%' ESCAPE '\')
  AND (d.algo_doc_type IN ('regulation','opinion','action_plan','strategy','plan','law','decree','decision','work_plan')
       OR d.title REGEXP '(意见|规定|办法|规划|行动方案|实施方案|条例|纲要|决定|细则)')
  AND d.algo_doc_type <> 'explainer';
-- (the Python side also drops titles matching NONISSUE_RE from build_diffusion_events.py)

-- Sub-provincial -> provincial resolved edges (levels from sites, not citations.*_level)
SELECT c.source_id, c.target_id, c.citation_type, ss.admin_level, s.site_key, t.site_key
FROM citations c
JOIN documents s ON s.id = c.source_id JOIN documents t ON t.id = c.target_id
JOIN sites ss ON ss.site_key = s.site_key JOIN sites st ON st.site_key = t.site_key
WHERE c.target_id IS NOT NULL
  AND ss.admin_level IN ('municipal','district','department')
  AND st.admin_level = 'provincial';
-- 26,208 edges; same-province + target is framework + source dated on/after target -> 6,270

-- Cross-province edges (dropped; dominated by resolver mis-targeting)
SELECT s.site_key, t.site_key, COUNT(*) n FROM citations c
JOIN documents s ON s.id=c.source_id JOIN documents t ON t.id=c.target_id
JOIN sites ss ON ss.site_key=s.site_key JOIN sites st ON st.site_key=t.site_key
WHERE st.admin_level='provincial' AND ss.admin_level IN ('municipal','district','department')
GROUP BY 1,2 ORDER BY n DESC;
-- ga->bj 855, szlhq->bj 302, yangjiang->fj_wjw 170, shaoguan->fj_wjw 161, ...

-- Central -> provincial leg for chains (P must be a scored target)
SELECT e.source_id AS p_id, e.anchor_id AS c_id, e.match_type, e.lag_days
FROM diffusion_events e JOIN documents a ON a.id = e.anchor_id
WHERE e.match_type IN ('citation','title_reissue') AND length(a.body_text_cn) > 500;
-- joined in Python to the P->M pairs: 2,444 chains, 561 P, 509 C

-- Coverage denominators (pairs -> scored)
-- citation: city 5,068->4,570  dept 697->513  district 505->432
-- title_reissue: city 293->218  dept 35->20  district 24->12
```

## Appendix B. The 5-gram sketch and the pair builder

```python
import re, sqlite3, sys
sys.path += ["scripts/rnd/citations", "scripts/rnd/analysis"]
from extract_citations import TitleMatcher, _norm_title
from build_diffusion_events import genre_stem, is_framework, inner_core, ISSUANCE_RE, NONISSUE_RE
N = 5
TAG, WS = re.compile(r"<[^>]+>"), re.compile(r"\s+")
norm  = lambda t: WS.sub("", TAG.sub("", t or ""))[:150_000]
grams = lambda t: {t[i:i+N] for i in range(len(t) - N + 1)}
PLACE = re.compile(r"^[一-鿿]{2,4}(省|市|自治区|回族自治区|维吾尔自治区|壮族自治区)")
c = sqlite3.connect("file:documents.db?mode=ro", uri=True)

# prov_of(site_key): gd = gd* | 16 gkmlpt cities | sz* | 13 Shenzhen bureaus; js = js* | suzhou.. | njd_*;
#                    bj = bj | bjb_* | bjd_*; cq = cq | cq_* | cqd_*; ... (one dict per province)
# unit_of: 'prov' if admin_level=='provincial' or site in {cq} or bjb_/shb_; else city|district|dept

# citation pairs: resolved edge M->P, P framework (is_framework + not explainer), same prov_of, lag >= 0
# title_reissue: stem = genre_stem(PLACE.sub("", _norm_title(inner_core(P.title) or P.title))), len >= 8
#   matcher = TitleMatcher({stem: (first_id,)}); for M passing ISSUANCE_RE and not NONISSUE_RE:
#   hit = matcher.resolve(_norm_title(M.title), 8); require stem in M.ntitle (stem-inside-title only),
#   take latest same-province P dated before M; drop if P.ntitle in M.ntitle (mirror) or already cited.

BOILER = {...}   # 5-grams in >= 2% of a random 1,000-doc sample (1,633 grams)
for P, members in pairs_by_target.items():          # P grams built once per target
    A = grams(norm(body(P))); A_nb = A - BOILER
    for M in members:
        S = grams(norm(body(M))); inter = len(S & A)
        ovlp_src = inter / len(S); ovlp_anc = inter / len(A)
        ovlp_src_nb = len((S - BOILER) & A_nb) / len(S - BOILER)
# 5,765 pairs in 62 s on the droplet.

# chains: for P with C in diffusion_events (citation/title_reissue), Cg = grams(body(C)):
#   ovlp_m_p = |S&Pg|/|S|; ovlp_m_c = |S&Cg|/|S|; ovlp_p_c = |Pg&Cg|/|Pg|
#   both = |S&Pg&Cg|/|S|; p_only = (|S&Pg| - both)/|S|; c_only = (|S&Cg| - both)/|S|
# 2,444 chains in 20 s. Pattern: province-descended if p_only >= 2*c_only; center-descended if the reverse;
# local if ovlp_m_p < 0.1 and ovlp_m_c < 0.1; else mixed.
```

Predictor tables are pandas group-bys over the pair CSV. Spearman rho is Pearson on ranks.
Fiscal quartiles are rank-based on money terms per 10k provincial characters. Variance shares
are var(group means) / var(total) over the implementing subset.
