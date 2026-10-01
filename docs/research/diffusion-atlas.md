# The Central-to-Local Diffusion Atlas: Lags, Breadth, and Intensity Across 2,994 Central Instruments

*A corpus-wide analysis on the china-governance corpus (SQLite on the droplet, read-only, pulled
2026-10-01). It generalizes the two worked cases (`consumption-diffusion.md`, the 以旧换新 cascade;
`ai-governance-diffusion.md`, the AI+ cascade) to every central instrument the auto-matcher in
`diffusion_events` can see. It is our replication and extension of Luo, Wang and Yang,
"Laboratories of Autocracy" (NBER w34219, 2025) and of the "Measuring policy diffusion intensity"
index (Information Processing & Management, 2025). Our edge over both is an explicit, directed,
auto-matched event table rather than inferred text similarity. Every figure is reproducible from
the appendix queries.*

---

## 0. The question and the short answer

**Question.** For every central instrument in the corpus, how fast and how widely does it echo
down the province, city and district tiers? Does the province-before-city ordering seen in the two
case studies hold corpus-wide? Which genres, topics and issuers cascade most? Has diffusion changed
across 2010-2026?

**Short answer.**

1. **Province-before-city holds corpus-wide, and it is not a coverage artifact.** For the 1,030
   central instruments that reach both a provincial unit and a prefecture city, the province echoes
   first in 75% of cases (median 114 days vs 281). Inside the same province, the provincial unit
   beats its own cities and districts in 68% of 721 anchor-province pairs (median 56 days ahead).
   Restricted to adoption-grade events (the echo is itself an implementing instrument) the ordering
   strengthens to 76% corpus-wide and 72.5% nested. It survives a 2015+ restriction and a
   365-day window. A flat scatter would give 50%. [measured]

2. **Breadth is heavy-tailed and dominated by State Council regulations; speed belongs to
   campaign instruments.** Half of all echoed anchors reach 2 or fewer sites, 92 adoption-grade
   anchors reach 10 or more. Regulations (条例) are 18% of anchors but 44% of the top-50 by breadth,
   with a slow 695-day median lag. Action plans and opinions echo in 228-341 days and score highest
   on the per-anchor intensity index. The widest adoption-grade instrument is the 2019 政府信息公开条例
   (38 sites); the fastest wide one is the 2024 以旧换新行动方案 (28 sites, 76-day median). [measured,
   coverage-bounded]

3. **Diffusion has not gotten faster or wider on a fixed panel of continuously crawled sites.** On
   22 panel sites, the median lag to the first echo was 71 days for 2008-13 anchors, 104 for
   2014-19, 98 for 2020-23 and 73 for 2024-26. Mean panel breadth within a year sits at 2.1-2.6
   sites throughout. What changed is the center's output: the State Council family issued ~157
   framework instruments a year in 2014-19 (~134 in 2008-13) and ~240 a year since 2020, and the share of them that
   gets any panel echo within a year fell from 50% (2014-19) to 22% (2020-23) and 17% (2024-26,
   censored). More instruments, each echoed less often. [measured, with a resolution caveat]

4. **The State Council masthead buys breadth; co-signatures do not.** State Council and SC General
   Office instruments average 4.5-4.9 echoing sites and reach the city tier in 54-63% of cases.
   Single-ministry instruments average 2.5 sites and reach cities 34% of the time. Joint
   multi-ministry instruments are no wider than single-ministry ones (2.2 vs 2.5). [measured]
   *(Update 2026-10-01: holds for 2-3 signers. With real coalition sizes from `doc_issuers`,
   5+ coalitions are echoed 2.5-3.7x as often and sooner, mostly on whether any unit responds;
   see `joint-issuance.md` §5c.)*

The load-bearing caveats are the usual ones and one new one. Breadth is a floor (Guangdong supplies
641 of the 721 nested pairs). Citation resolution is 52%. The 2025-26 cascades are mid-flight. And
the new one: ~9% of auto-matched anchors carry a representative title that names a different
instrument than the one actually cited (an explainer, a ruling, a readout pooled under the cited
text's 《》 name), and 819 "central" anchors were provincial and municipal 人大 regulations stored in
the national laws database. Both are handled below, neither is fully solved.

---

## 1. Data and the signal ladder

`diffusion_events` holds 28,880 (source, anchor) rows built by `scripts/rnd/analysis/build_diffusion_events.py`:
for each sub-national document, the central instrument it implements, with a lag in days. Three
match types, strongest wins per pair. This atlas uses a strict signal ladder and reports each rung
separately. *(Build note 2026-10-01: this memo was built on the first, 28,880-row build (before
the npc/explainer fix, which this memo applied by hand below). The table is rebuilt nightly: the
post npc/explainer build held 24,599 rows, the post resolver-fix build 26,565 central rows, and
with provincial anchors added it held 32,825 rows (26,565 central + 6,260 provincial) on
2026-10-01; a further resolver regression fix in progress will change it again. Spot checks on the
live table show the headline anchors held shape (政府信息公开条例 68 confirmed sites, 以旧换新 SC
plan 37, AI+ opinion 22 sites), so shares and orderings are robust; raw counts (17,381 confirmed,
8,410 adoption-grade, 1,030 paired anchors) are not current. See `consistency-review.md` H2.
Also note that npc local regulations are removed as anchors but kept as sources here; other memos
handle npc differently, so level shares are within-memo only, review M7.)*

| rung | definition | rows (central atlas) | read as |
|---|---|---:|---|
| **adoption-grade** | citation or title_reissue AND the source document's own genre is an implementing instrument (action_plan, policy_issuance, opinion, work_plan, regulation, strategy, plan, decision, decree, subsidy) | **8,410** from 2,120 anchors, 252 sites | adoption |
| **confirmed** | citation (resolved edge or exact 《》-core) or title_reissue (localized title stem) | **17,381** (16,931 + 450) from 2,932 anchors, 341 sites | reference or adoption |
| topic_genre | same topic tag, implementing genre, within 365 days of a major campaign anchor, no stronger match | 6,517 | probable, unconfirmed |

Two cleaning steps, both applied before every table:

- **Local 人大 anchors removed.** 819 anchors (4,980 events) sit on the `npc` site with
  `admin_level=central` but are published by a provincial or municipal 人大常委会 (e.g.
  广东省突发事件应对条例, 深圳经济特区城市更新条例). They are not central instruments. They are a real
  provincial-to-municipal layer and are reported separately in §8. The central atlas is the
  remaining **2,994 anchors / 23,898 events**.
- **Dates bounded.** Anchors 2000-2026, sources 2000 to 2026-10-01 (a few documents carry
  future publication dates).

Why the ladder matters: a city 常委会 readout that "studies and implements" the 三中全会决定 is a
citation event (attention), not an adoption. The 决定 has 50 confirmed sites but drops out of the
adoption-grade top 25 entirely. The confirmed tier measures documentary attention; the
adoption-grade tier measures documentary adoption. topic_genre is reported only for counts, never
for lags, because its lag is capped at 365 days by construction and its level medians are flat
(185-193 days) for that reason alone.

The "department" source level is the 13 Shenzhen municipal bureaus (`stic`, `fgw`, `zjj`, ...),
not a tier of the hierarchy. The "provincial unit" used below pools a province's portal, its
departments, and the bureaus of the four provincial-level municipalities (`bjb_*`, `shb_*`,
`cq_*`), which are provincial-level bodies despite their `municipal` site tag.

---

## 2. Lag distributions (Q1)

### 2a. By anchor genre

Confirmed events, then adoption-grade. Lag is days from the anchor's publication to the echo's.

| anchor genre | confirmed n | median | IQR | adoption-grade n | median | IQR | % within 90d (adopt.) |
|---|---:|---:|---|---:|---:|---|---:|
| work_plan | 209 | 228 | 98-460 | 119 | 235 | 119-455 | 11.8 |
| action_plan | 1,557 | 262 | 110-579 | 830 | **228** | 106-470 | **21.9** |
| strategy | 1,322 | 352 | 124-697 | 685 | 386 | 216-649 | 10.8 |
| opinion | 4,763 | 365 | 176-706 | 2,826 | 341 | 182-656 | 8.4 |
| decision | 941 | 440 | 116-859 | 387 | 533 | 230-899 | 8.3 |
| policy_issuance | 1,831 | 525 | 231-943 | 766 | 474 | 228-864 | 6.7 |
| decree | 218 | 521 | 240-880 | 98 | 518 | 231-899 | 5.1 |
| regulation | 4,783 | **648** | 244-1052 | 2,048 | **695** | 332-1052 | 6.9 |
| law | 334 | 371 | 179-859 | 114 | 712 | 327-1092 | 6.1 |

Reading it. Campaign instruments (action plans, work plans, opinions) are the fast genres: a
fifth of action-plan adoptions land inside 90 days. Regulations and laws are the slow genres, with
a two-year median, because what cites them is the long tail of local rules that invoke them as legal
basis years later. The consumption case's 49-day median was an unusually fast action plan, in the
fastest quartile of its genre, not the typical one. [measured]

### 2b. By topic

Topic is the anchor's first `topics_algo` tag; 5,438 confirmed events (31%) have an untagged anchor.
Confirmed events, n >= 30.

| topic | n | median | IQR | % within 90d |
|---|---:|---:|---|---:|
| Party | 380 | 190 | 126-428 | 16.1 |
| Commerce | 555 | 224 | 87-465 | 25.0 |
| Trade | 247 | 257 | 131-631 | 16.2 |
| Environment | 729 | 312 | 65-745 | 28.4 |
| Agriculture | 698 | 374 | 155-773 | 14.9 |
| Infrastructure | 306 | 400 | 182-882 | 13.1 |
| Emergency | 253 | 405 | 180-841 | 14.6 |
| Transport | 372 | 429 | 166-911 | 14.8 |
| Tech | 602 | 444 | 196-859 | 11.0 |
| Health | 947 | 456 | 212-856 | 10.5 |
| Finance | 1,290 | 458 | 187-889 | 11.6 |
| Welfare | 531 | 462 | 224-721 | 8.1 |
| Education | 640 | 487 | 195-851 | 13.4 |
| Legal | 536 | 511 | 173-886 | 17.2 |
| Housing | 313 | 516 | 171-881 | 18.2 |
| Government | 1,462 | 544 | 226-998 | 9.2 |
| Safety | 525 | 570 | 208-942 | 12.2 |
| Diplomacy | 219 | 645 | 335-1101 | 2.3 |
| Security | 102 | 677 | 357-898 | 3.9 |

Party-building and commerce move fastest. Government-process, safety, diplomacy and security move
slowest, which is the regulation effect again: those topics are dominated by 条例 that get cited as
legal basis rather than campaigns that get re-issued. Tech sits in the slow half (444 days), which
matches the AI chapter's finding that AI regulation is cited, not localized. [measured; topic tagger
~64% coverage]

### 2c. By source level: the ordering

| source unit | confirmed n | median | IQR | adoption-grade n | median | IQR | 2015+ anchors, adopt. median |
|---|---:|---:|---|---:|---:|---|---:|
| provincial unit | 9,317 | **356** | 148-747 | 4,747 | **320** | 159-667 | 309 |
| prefecture city | 5,235 | 499 | 202-920 | 3,002 | 541 | 287-918 | 493 |
| district | 1,071 | 564 | 238-993 | 251 | 641 | 364-1003 | 645 |
| Shenzhen bureaus | 1,758 | 589 | 264-1019 | 410 | 628 | 306-1037 | 573 |

The unpaired medians are monotone: province, then city, then district. Title re-issuances alone
(n=450) show the same provincial lead (338 vs 346 days) but on small numbers. [measured]

Unpaired medians can be fooled by archive depth. Guangdong cities are crawled back to 2008 and
carry the long legal-basis tail (GD city median 532 days), while most non-Guangdong cities were
added in 2026 with shallow archives and show short lags (313 days) because only recent anchors are
observable there. The paired tests below are within-anchor and are immune to this.

### 2d. Province-before-city: paired tests

For each anchor, the first provincial-unit echo versus the first city echo.

| test | anchors / pairs | province first | median lag, prov vs city | notes |
|---|---:|---:|---|---|
| corpus-wide, confirmed | 1,030 | **74.9%** | 114 vs 281 | city first 24.8%, tie 0.4% |
| corpus-wide, adoption-grade | 727 | **76.1%** | 159 vs 318 | |
| corpus-wide, adoption-grade, anchors 2015+ | 522 | 75.9% | 154 vs 309 | coverage-era control |
| corpus-wide, adoption-grade, 2015+, both echoes <= 365d | 262 | 75.6% | | right-censoring and depth control |
| corpus-wide, confirmed, both echoes <= 365d | 555 | 72.6% | 69 vs 136 | |
| province vs district, confirmed | 275 | 73.8% | | |
| city vs district, confirmed | 232 | 67.7% | | |
| **nested, same province**, confirmed | 721 | **68.0%** | sub-unit 56 days behind, IQR -41 to 215 | GD 641 pairs (67%), JS 27 (85%), BJ 12 (75%) |
| nested, same province, adoption-grade | 480 | **72.5%** | sub-unit 90 days behind | |
| nested, citation only | 698 | 68.2% | | |
| nested, title_reissue only | 19 | 68.4% | | small n |

Across anchors, the first confirmed echo of any kind comes from a provincial unit for 2,081 of
2,932 anchors (71%), a city for 536, a Shenzhen bureau for 221, a district for 94.

**Verdict: province-before-city holds corpus-wide.** [measured] Every cut sits at 68-76% against a
50% null, including the nested test that compares a province only with its own cities, and the
365-day-window test that strips the archive-depth confound. The nested figure is a Guangdong
result (641 of 721 pairs), because Guangdong is the only province with district-depth coverage; the
other eleven provinces agree in direction on small numbers (JS 23 of 27, BJ 9 of 12, FJ 6 of 6).
The 32% of nested pairs where a city moved first are real and worth a study of their own: the
Guangdong cities that beat the province are the ones to look at for bottom-up initiative.

---

## 3. Breadth: the most-cascaded instruments (Q2)

Breadth = distinct sub-national sites with a confirmed echo. A site is a portal, not a
jurisdiction: a province with 40 department portals can contribute many sites for one jurisdiction,
so provincial breadth is an upper bound in that one respect, while coverage makes every breadth a
floor in all others.

Distribution. Among 2,932 echoed anchors the median breadth is 2 sites and the 75th percentile 4.
701 anchors reach 5 or more sites, 203 reach 10, 38 reach 20, the maximum is 68. Adoption-grade:
2,120 anchors, median 2, 426 at 5+, 92 at 10+. [measured, coverage-bounded]

### 3a. Top adoption-grade instruments

| rank | anchor (date) | issuer | genre | topic | sites | prov/city/dist events | median lag |
|---:|---|---|---|---|---:|---|---:|
| 1 | 政府信息公开条例 (2019-04) | SC | regulation | Government | **38** | 43/49/25 | 601 |
| 2 | 十四五规划纲要 (2021-03) | NPC/central | strategy | | 28 | 15/61/2 | 364 |
| 3 | 推动大规模设备更新和消费品以旧换新行动方案 (2024-03) | SC | action_plan | Commerce | 28 | 19/22/1 | **76** |
| 4 | 重大行政决策程序暂行条例 (2019-04) | SC | regulation | | 26 | 21/46/1 | 993 |
| 5 | 优化营商环境条例 (2019-10) | SC | regulation | Government | 25 | 46/31/3 | 698 |
| 6 | 进一步规范行政裁量权基准制定和管理工作的意见 (2022-08) | SC GO | opinion | | 25 | 28/8/0 | 516 |
| 7 | 公平竞争审查条例 (2024-06) | SC | regulation | | 24 | 17/7/3 | 395 |
| 8 | 突发事件应急预案管理办法 (2024-02) | SC GO | policy_issuance | Emergency | 24 | 12/40/0 | 391 |
| 9 | 粮食流通管理条例 (2021-04) | SC | regulation | Agriculture | 21 | 8/19/0 | 591 |
| 10 | 土地管理法实施条例 (2021-07) | SC | regulation | | 20 | 9/17/3 | 784 |
| 11 | 建设工程质量管理条例 (2019 rev.) | SC | regulation | | 19 | 9/31/1 | 953 |
| 12 | 汽车以旧换新补贴实施细则 (2024-04) | joint (商务部等7部门) | action_plan | Commerce | 19 | 12/10/0 | **127** |
| 13 | 生态环境法典 pool (2026-08)* | central | regulation | Environment | 19 | 25/15/1 | 19 |
| 14 | 十三五规划纲要 (2016-03) | NPC/central | strategy | | 18 | 46/47/0 | 374 |
| 15 | 政府信息公开信息处理费管理办法 (2020-12) | SC GO | policy_issuance | Government | 18 | 5/11/9 | 285 |
| 16 | 规章制定程序条例 (2017 rev.) | SC | regulation | | 18 | 10/29/0 | 886 |
| 17 | 医疗保障基金使用监督管理条例 (2021-02) | SC | regulation | Health | 17 | 27/13/0 | 502 |
| 18 | 全面推进政务公开工作的意见 实施细则 (2016-11) | SC GO | action_plan | Government | 17 | 19/13/2 | 317 |
| 19 | 社会救助暂行办法 (2014-02) | SC | regulation | Welfare | 17 | 13/13/2 | 694 |
| 20 | 市场主体登记管理条例 (2021-07) | SC | regulation | | 16 | 14/12/0 | 712 |

\* The representative row is the Supreme People's Court ruling on the Code's temporal effect; the
events are citations of the Code itself (see §7 on anchor identity). The cascade is real and
remarkably fast (19-day median, 50 confirmed sites), it is the new Environmental Code being invoked
as legal basis across the country within weeks of taking effect.

Two families dominate. **Administrative-process regulations** (information disclosure, major
decision procedure, business environment, fair competition review, rule-making procedure) are the
widest instruments in the corpus. Every locality must cite them when it issues its own procedural
rules and annual reports, so they accumulate breadth over years. **Fiscal campaigns** (以旧换新 and
its subsidy rule) are the only instruments that are both wide and fast. [measured]

The all-confirmed top list adds the attention events: the 2024 三中全会决定 (50 sites, 38-day
median, nearly all 学习贯彻 readouts), the 2023 纪律处分条例 (48 sites), the 2025 十五五规划建议 (45
sites, 43 days), and the 粤港澳大湾区发展规划纲要 (24 sites). These are what the bureaucracy
*talks about* within weeks; the adoption-grade list is what it *re-legislates* within years.

### 3b. What kinds of instruments cascade widest

| genre | share of all echoed anchors | share of top-50 (confirmed) | share of top-50 (adoption-grade) |
|---|---:|---:|---:|
| regulation | 18.0% | **44%** | **44%** |
| opinion | 25.8% | 14% | 26% |
| action_plan | 11.6% | 16% | 16% |
| policy_issuance | 15.0% | 8% | 4% |
| strategy | 7.8% | 8% | 6% |
| notice / decree / work_plan | 9.0% | 0% | 0% |

By topic, the share of a topic's anchors that reach 5+ sites: Government **59.7%**, Welfare 37.3%,
Safety 33.8%, Environment 30.9%, Commerce 28.0%, Health 26.6%, Tech 23.1%, Education 21.4%,
Finance 17.8%, Transport 17.8%, Trade 14.1%, Culture 11.7%. Government-process instruments cascade
because every tier has to re-issue procedure; culture and trade instruments mostly stop at the
province. [measured]

---

## 4. A per-anchor diffusion-intensity index (Q3)

Two forms, computed on the 1,268 anchors with 3+ confirmed sites.

- **DI** (speed-breadth) = sites × 365 / median lag. Localities per lag-year.
- **HE** (hierarchical effectiveness, after the IP&M 2025 form) = Σ over echoing sites of
  w(level) × exp(-first_lag / 365), with w = 1.0 provincial unit, 0.75 Shenzhen bureau, 0.5 city,
  0.25 district. It rewards early, high-tier uptake and discounts the Guangdong district close-up.

DI is censoring-sensitive: the top DI rows are 2026 anchors whose only observable echoes are the
fast ones (a 2026-07 科技奖励决定 scores DI 1,825 from 5 sites at lag 1). HE is the better ranking.

### 4a. Top anchors by HE

| HE | anchor (date) | issuer | genre | sites | median lag |
|---:|---|---|---|---:|---:|
| 35.2 | 生态环境法典 pool (2026-08)* | central | regulation | 50 | 20 |
| 28.1 | 十五五规划建议 (2025-10) | party-state | strategy | 45 | 43 |
| 27.2 | 政府信息公开条例 (2019-04) | SC | regulation | 68 | 692 |
| 26.7 | 三中全会决定 (2024-07) | party-state | decision | 50 | 38 |
| 17.9 | 以旧换新行动方案 (2024-03) | SC | action_plan | 37 | 79 |
| 17.1 | 纪律处分条例 (2023-12) | party-state | regulation | 48 | 189 |
| 14.0 | 公平竞争审查条例 (2024-06) | SC | regulation | 53 | 428 |
| 13.7 | 民族团结进步促进法 (2026-03) | NPC | law | 34 | 182 |
| 12.8 | 汽车以旧换新补贴实施细则 (2024-04) | joint | action_plan | 22 | 128 |
| 11.6 | 严格规范涉企行政检查的意见 (2025-01) | SC GO | opinion | 26 | 237 |
| 11.4 | 法治政府建设实施纲要 pool (2021)* | central | action_plan | 30 | 464 |
| 11.3 | 十四五规划纲要 (2021-03) | central | strategy | 35 | 377 |
| 10.4 | 政府信息公开信息处理费管理办法 (2020-12) | SC GO | policy_issuance | 40 | 789 |
| 9.6 | "人工智能+"行动的意见 (2025-08) | SC | opinion | 20 | 213 |
| 8.1 | 提振消费专项行动方案 (2025-03) | party-state | action_plan | 21 | 151 |

\* pooled under the cited instrument's 《》 name; representative title differs (§7).

### 4b. Which instrument kinds score highest

Median index by anchor genre, eligible anchors:

| genre | n | median sites | median lag | median DI | median HE |
|---|---:|---:|---:|---:|---:|
| action_plan | 121 | 5 | 288 | **6.8** | **2.21** |
| opinion | 451 | 5 | 322 | 6.8 | 2.20 |
| notice | 55 | 4 | 293 | 7.2 | 1.74 |
| work_plan | 22 | 4 | 237 | 6.3 | 1.66 |
| strategy | 76 | 4 | 319 | 5.6 | 1.80 |
| decision | 65 | 5 | 477 | 4.8 | 1.93 |
| law | 22 | 7.5 | 600 | 4.1 | 1.74 |
| policy_issuance | 137 | 4 | 474 | 3.6 | 1.36 |
| regulation | 244 | 5 | 710 | 3.5 | 1.41 |
| decree | 22 | 3.5 | 543 | 3.0 | 1.15 |

By topic the median HE is highest for Government (3.18), Personnel (2.35), Commerce (2.21), Safety
(2.09), Housing (2.09), Welfare (2.07), Environment (2.07), and lowest for Energy (1.13), Culture
(1.29), Transport (1.48), Emergency (1.50).

Reading it. On the per-anchor median, **campaign instruments** (action plans, opinions) score
highest: they are not the widest, but they are fast and they reach provinces early, which HE
rewards. On the extreme tail, **regulations and party-state framework texts** dominate, because
nothing else accumulates 40-70 sites. The index therefore separates two modes of diffusion that the
raw breadth list conflates: a fast provincial relay for campaigns, and a slow nationwide
accumulation for procedural law. [measured]

---

## 5. Diffusion over time (Q4)

Raw yearly counts are useless here: the number of active sub-national sites grew from 40 (2008) to
370 (2025), and the number of central framework instruments the crawl sees jumped in 2018 when
more ministries were added. Two normalizations are used. First, a **fixed panel of 22 sites** that
carry 10+ documents in every year 2012-2025 (bj, sh, cq, gd, js, hlj, gz, suzhou, wuhan, seven
Guangdong cities, Longgang district, four Shenzhen bureaus). Second, a **fixed issuer family**: the
State Council, its General Office, and party-state joint texts, which gov.cn carries consistently
for the whole window. Echoes are counted inside a 365-day window after the anchor so that every year
is measured with the same horizon.

### 5a. State Council family anchors, panel sites, 365-day window

| period | SC-family framework docs | per year | with a panel echo <= 365d | % echoed | median first lag | IQR | mean panel sites | mean adoption-grade panel sites |
|---|---:|---:|---:|---:|---:|---|---:|---:|
| 2008-13 | 802 | 134 | 265 | 33.0% | **69** | 38-161 | 2.38 | 1.62 |
| 2014-19 | 940 | 157 | 474 | **50.4%** | 106 | 38-183 | **2.90** | **2.37** |
| 2020-23 | 966 | 242 | 209 | 21.6% | 63 | 5-144 | 2.95 | 1.91 |
| 2024-26 | 629 | 229 | 104 | 16.5% | 60 | 24-123 | 2.45 | 1.37 |

(2024-26 is censored: anchors after 2025-10 have less than a 365-day window. The 2026 row alone is
8% echoed.)

### 5b. All central anchors, panel sites

| period | anchors with panel echo <= 365d | median first lag | IQR | mean panel sites | % with 3+ panel sites |
|---|---:|---:|---|---:|---:|
| 2008-13 | 331 | 71 | 38-167 | 2.27 | 33.5 |
| 2014-19 | 632 | 104 | 35-192 | 2.63 | 40.5 |
| 2020-23 | 398 | 98 | 25-188 | 2.28 | 26.9 |
| 2024-26 | 190 | 73 | 26-160 | 2.11 | 21.1 |

### 5c. First-echo lag by period and source unit (first echo per anchor per unit, <= 365d)

| period | provincial unit | city | district |
|---|---:|---:|---:|
| 2008-13 | 73 (n=297) | 134 (128) | |
| 2014-19 | 105 (606) | 196 (226) | 210 (20) |
| 2020-23 | 112 (440) | 124 (194) | 165 (76) |
| 2024-26 | 84 (381) | 57 (211) | 118 (66) |

Reading it, carefully.

- **Speed has not improved.** Conditional on echoing within a year, the lag to the first echo was
  shortest in 2008-13 (~70 days), longest in 2014-19 (~105), and back to 60-75 since 2020. There is
  no monotone acceleration. The 2020-23 first quartile of 5 days reflects a rise in same-day
  verbatim relays (转发) rather than faster localization. [measured on the panel]
- **Breadth has not widened.** Mean panel sites within a year stays in a 2.1-2.9 band for two
  decades. The 2014-19 period is the peak on every measure. [measured on the panel]
- **The center issues more and is echoed less.** SC-family framework output rose from ~134 a year
  to ~240 a year, and the share with any fast panel echo fell from half to a fifth. [measured, but
  see the caveat]
- **The city tier closed its gap in 2024-26** (57 days vs 84 for provinces, on a censored window).
  This is the first period where cities look as fast as provinces on first echo. It is driven by
  the 2024-25 fiscal campaigns (以旧换新, 提振消费) which Guangdong cities localized within weeks,
  and by censoring. Treat it as a lead to test when the window closes, not a finding.

The caveat on "echoed less." The resolver and the matcher are uniform across years, the panel sites
are continuously crawled, and the issuer family is fixed, so the drop is not a crawl artifact in
the obvious ways. But two things could depress recent resolution: recent local documents cite by
文号 more often, and 48% of all citation edges remain unresolved. The direction is probably real,
the magnitude is not pinned down. This is the point of contact with Luo, Wang and Yang's
post-2013 centralization finding: our data show rising central output with falling per-instrument
local echo after 2019, which is consistent with a center that legislates more and a periphery that
re-legislates a smaller fraction of it. We do not see the shift at 2013; on our panel 2014-19 is
the high point of local echo. [inferred]

---

## 6. Issuer effects (Q5)

Issuer class is read from the anchor's title and publisher: party-state joint (中共中央 ...),
State Council (国务院), SC General Office (国务院办公厅), NPC law, joint ministries (等N部门 or
multiple mastheads), single ministry.

### 6a. Among anchors with at least one confirmed echo

| issuer | anchors | mean sites | % 5+ sites | % 10+ | median lag | median HE | % reaching a province | % reaching a city |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| party-state joint | 188 | **5.55** | 39.4 | **15.4** | 296 | 1.30 | 78.7 | **68.6** |
| State Council | 707 | 4.93 | **40.3** | 12.4 | 432 | 1.12 | 89.5 | 62.5 |
| NPC law | 57 | 4.68 | 33.3 | 12.3 | 561 | 0.91 | 84.2 | 57.9 |
| SC General Office | 497 | 4.47 | 35.2 | 7.8 | **264** | **1.59** | **94.2** | 53.5 |
| single ministry | 956 | 2.48 | 10.1 | 3.3 | 501 | 0.48 | 76.2 | 34.4 |
| joint ministries | 527 | 2.24 | 9.7 | 1.5 | 449 | 0.51 | 79.5 | 31.3 |

Adoption-grade only: State Council 4.00 mean sites (31% at 5+), SC GO 3.64 (28%), party-state 3.15
(21%), NPC law 2.98, single ministry 2.09 (8.9%), joint ministries 1.97 (6.5%). In the adoption-grade
top-50, the State Council is 48% of entries against 28% of anchors; joint ministries are 4% against
15%.

### 6b. Of all central framework instruments since 2008, how many ever echo

| issuer | framework docs 2008+ | with a confirmed echo | % |
|---|---:|---:|---:|
| SC General Office | 934 | 428 | **45.8** |
| party-state joint | 296 | 122 | 41.2 |
| State Council | 2,107 | 633 | 30.0 |
| joint ministries | 1,580 | 335 | 21.2 |
| single ministry | 4,062 | 526 | 12.9 |
| NPC law | 671 | 53 | 7.9 |

Reading it.

- **The masthead is the variable.** A State Council or General Office instrument is twice as wide
  as a ministerial one, three to four times as likely to reach 5 sites, and twice as likely to
  reach the city tier. [measured]
- **Co-signature does not buy breadth.** Joint multi-ministry instruments (商务部等14部门 and the
  like) are no wider than single-ministry ones on any measure, and slightly narrower. Issuing with
  more ministries signals coordination at the center; it does not make localities re-issue. The one
  joint instrument in the wide list (汽车以旧换新补贴实施细则) rode a State Council campaign.
  [measured] *(Update 2026-10-01: holds for 2-3 signers; 5+ coalitions are echoed 2.5-3.7x as
  often, see `joint-issuance.md` §5c. The "joint ministries" class here pooled all sizes (live
  split 295 / 222 / 68 for 2-3 / 4-9 / 10+ signers), and this table counts confirmed events only
  while joint §5 counts all rows including topic_genre, so the two are not on the same base.)*
- **The General Office is the fast channel.** SC GO instruments have the shortest median lag
  (264 days), the highest HE, and reach a provincial unit 94% of the time. The State Council proper
  is wider but slower, because its output is weighted to 条例. [measured]
- **Party-state joint texts reach cities most often** (69%), the signature of the 学习贯彻 readout
  wave: every 常委会 reports studying them. On adoption-grade events they fall to third. [measured]
- **NPC laws rarely echo** as a share (7.9%) because the NPC crawl is metadata-only and most laws
  are not implementing targets; the ones that do echo are wide (mean 4.7). [measured, coverage]

---

## 7. Comparison with Luo, Wang and Yang (Q6)

Luo, Wang and Yang build 3.7M documents, identify 115,679 distinct policies by text, and track
initiation and diffusion by similarity, finding a post-2013 shift to centralization. The IP&M
index scores diffusion as hierarchical effectiveness plus textual intensity on 9,091 low-carbon
documents. Our table is smaller (24k central-to-local events, 2,994 anchors) but each edge is
explicit and directed. The two methods see different things.

**What text similarity sees that our graph does not.**

- Implementations that neither cite nor re-use the anchor's name. Our topic_genre tier (6,517
  rows) is a crude stand-in for this and is deliberately not trusted for lags.
- The 48% of citation edges that do not resolve. Similarity needs no resolver.
- Textual fidelity. We know a city re-issued; similarity knows how much it copied. (The AI+
  fidelity memo does this by 5-gram overlap for one cascade; LWY do it at scale.)

**What our explicit graph sees that similarity does not.**

- **Dissimilar implementers.** Only 1,435 of 16,931 citation-confirmed events (8.5%) carry the
  anchor's title stem in the source title. 21% of confirmed events with topic tags on both ends link
  documents in *different* topics (2,093 of 9,991), 17% of adoption-grade ones. A local 危险废物
  rule that cites the 生态环境法典, or a procurement rule that cites 优化营商环境条例, is invisible
  to title or topic similarity and visible to us. [measured]
- **Direction and attribution.** A citation says which central text a locality was implementing
  when several central texts share vocabulary (the trade-in plan, its 商务部 follow-on, and its
  subsidy rule are three distinct anchors here with three distinct cascades). Similarity assigns by
  nearest neighbor and would merge them.
- **Reference versus adoption.** Our source-genre ladder separates a 常委会 readout citing the
  三中全会决定 from a 实施方案 re-issuing a 行动方案. Similarity scores both as "close to the
  central text."
- **Elaboration.** The AI+ cascade (20 sites, HE 9.6) consists of local sector plans sharing 2-13%
  of text with the umbrella opinion. Similarity would score them as unrelated. Citation catches them.
- **Timing at the day.** Lags here are publication-date differences on dated primary documents, not
  annual panels.

**Where the two methods must be combined.** Our anchor identity problem is exactly where similarity
helps. The matcher pools promulgations by their 《》 core, and 260 of 2,932 anchors (8.9%) ended up
with a representative title that names another instrument: the SPC ruling standing in for the
生态环境法典, a 一图读懂 standing in for 质量强国建设纲要, a CAC implementation opinion standing in
for the 法治政府建设实施纲要, a MOST study-session readout standing in for 中央八项规定. Five of the
top-50 anchors by breadth are of this kind. The cascades are real; the labels are not. One 2026
anchor (a 十五五 sectoral-plan explainer with 24 sites at lag 0-7) is pure resolver noise from
generic "十五五规划" references and should be read as an artifact. A similarity check between a
pool's representative and its members would catch both. [artifact, flagged]

On their substantive finding: our panel shows the center's framework output rising and the share
echoed falling after 2019 (§5), which is compatible with centralization. We do not see a 2013
break; 2014-19 is our peak of local echo. Our data cannot adjudicate "bottom-up innovation no longer
rewarded" because we measure downward echo, not upward initiation. The 32% of nested pairs where a
Guangdong city preceded its province is the place to look.

---

## 8. The provincial-to-municipal layer (bonus, excluded from the central atlas)

The 819 local 人大 anchors removed in §1 form a second diffusion layer with its own shape: 4,980
confirmed events, median breadth 1, median lag 607 days. The widest are provincial implementing
regulations for national laws and provincial codes cited by their own cities: 四川省大气污染防治法
实施办法 (21 sites), 上海市殡葬管理条例 revision (20), 深圳市人防法实施办法 revision (20), 新疆水污染
防治法实施办法 (18), 广东省社会信用条例 (17), 河南省城乡规划法实施办法 (17), 广东省防汛防旱防风条例
(15). This is the layer where the Luo-Wang-Yang question of provincial laboratories could be tested
directly, provided the `npc` rows are re-tagged with their true issuer level. [measured, mis-tagged
at source]

---

## 9. Threats to validity

1. **Coverage bias bounds breadth and the nested test.** 341 sites appear in confirmed events but
   Guangdong supplies 641 of 721 nested pairs. No claim of the form "province X did not act" is
   supported. Breadth is a floor. The province-before-city ordering is robust in direction across
   the 11 other provinces but on single-digit pairs each.
2. **52% citation resolution.** All counts are floors. Unresolved edges skew to 文号-only references
   and out-of-corpus targets. The §5 "echoed less" trend could be partly a resolution trend.
3. **Mid-flight cascades.** Anchors after 2025-10 have less than a year of observation. The DI
   index over-ranks them; the §5 2024-26 row is censored; the "cities caught up" lead is untested.
4. **Anchor identity.** ~9% of representative titles name a different instrument than the one
   cited; one top anchor is resolver noise. Breadth and lag for those pools are correct, the labels
   are not.
5. **Sites are portals, not jurisdictions.** A province's department portals count separately, so
   provincial-unit breadth is inflated for Fujian, Ningxia, Tibet, Chongqing, Beijing and Shanghai.
   A jurisdiction-level recount is a straightforward next step.
6. **Publication is not adoption, and citation is not implementation.** The adoption-grade tier is
   the closest the documentary record gets. Fiscal execution and enforcement are outside it.
7. **Topic is the anchor's first tag only**; 31% of events have an untagged anchor; the tagger is
   ~64% coverage. Topic tables are indicative.
8. **The "department" level is the Shenzhen bureau tier**, not a national tier, and the
   `provincial unit` pools provincial-level municipal bureaus. Both are stated, neither is ideal.
9. **topic_genre lags are capped by construction** and are not comparable to confirmed lags.
10. **Mechanism-level claims only.** Nothing here licenses system-level characterizations.

---

## 10. Bottom line for the volume

The corpus delivers a corpus-wide diffusion atlas from primary documents alone. Three things hold at
scale that the case studies could only show once. The hierarchy orders the cascade (province before
city in 68-76% of paired comparisons, including within the same province). Genre sets the clock
(campaign instruments echo in 7-11 months, regulations in two years, with the fiscal campaigns the
only instruments that are both wide and fast). And the masthead sets the reach (State Council
instruments are twice as wide as ministerial ones; adding co-signing ministries adds nothing, which
holds for 2-3 signers while 5+ coalitions are echoed 2.5-3.7x as often, `joint-issuance.md` §5c). On a
fixed panel, diffusion has not accelerated or widened since 2008; what has changed is the volume of
central instruments, more of which now go without a fast local echo.

Natural next steps: a jurisdiction-level breadth recount; re-tagging the `npc` local regulations
to open the provincial-to-municipal layer; a similarity check on anchor pools to fix the label
artifact; and a study of the 229 nested pairs where a city preceded its province.

---

### Appendix: key queries

All run read-only against `file:/root/china-governance/documents.db?mode=ro`. The paired and
nested tests, the panel, the index and the issuer classifier were computed in Python over the result
of the first query (loader sketched after the SQL).

```sql
-- Event table profile
SELECT match_type, COUNT(*), MIN(lag_days), MAX(lag_days) FROM diffusion_events GROUP BY 1;
-- citation 21788 (0..1500) | title_reissue 574 (1..1492) | topic_genre 6518 (1..365)

-- Loader: events joined to anchor and source documents (the base of every table)
SELECT e.source_id, e.anchor_id, e.match_type, e.lag_days, e.topic, e.source_level,
       e.anchor_date, e.source_date, e.anchor_title, e.source_title,
       a.algo_doc_type a_genre, a.citation_rank a_cr, a.site_key a_site, a.publisher a_pub,
       s.site_key s_site, s.algo_doc_type s_genre, s.topics_algo s_topics
FROM diffusion_events e
JOIN documents a ON a.id = e.anchor_id
JOIN documents s ON s.id = e.source_id
WHERE e.anchor_date BETWEEN '2000-01-01' AND '2026-12-31'
  AND e.source_date BETWEEN '2000-01-01' AND '2026-10-01';

-- Local-NPC contamination (anchors that are provincial/municipal 人大 regulations on the npc site)
SELECT COUNT(DISTINCT e.anchor_id), COUNT(*)
FROM diffusion_events e JOIN documents d ON d.id = e.anchor_id
WHERE (d.publisher LIKE '%人民代表大会%' OR d.publisher LIKE '%人大常%')
  AND d.publisher NOT LIKE '全国%';
-- 819 anchors / 4,980 events (excluded from the central atlas, reported in §8)

-- Lag by source level, confirmed, central anchors only
SELECT e.source_level, COUNT(*), /* median via Python; SQLite has no percentile */ AVG(e.lag_days)
FROM diffusion_events e JOIN documents d ON d.id = e.anchor_id
WHERE e.match_type IN ('citation','title_reissue')
  AND NOT ((d.publisher LIKE '%人民代表大会%' OR d.publisher LIKE '%人大常%') AND d.publisher NOT LIKE '全国%')
GROUP BY 1;

-- Breadth per anchor (confirmed) with genre and topic; the §3 list
SELECT e.anchor_id, e.anchor_date, d.algo_doc_type, e.topic, d.publisher,
       COUNT(DISTINCT s.site_key) sites,
       SUM(e.match_type='citation') cit, SUM(e.match_type='title_reissue') reissue,
       substr(e.anchor_title,1,60)
FROM diffusion_events e JOIN documents d ON d.id = e.anchor_id JOIN documents s ON s.id = e.source_id
WHERE e.match_type IN ('citation','title_reissue')
GROUP BY e.anchor_id ORDER BY sites DESC LIMIT 30;

-- Adoption-grade restriction: add
--   AND s.algo_doc_type IN ('action_plan','policy_issuance','work_plan','opinion','regulation',
--                           'strategy','plan','decision','decree','subsidy')

-- Fixed panel of continuously crawled sub-national sites (>=10 docs every year 2012-2025)
SELECT d.site_key, substr(d.date_published,1,4) y, COUNT(*)
FROM documents d JOIN sites s ON s.site_key = d.site_key
WHERE s.admin_level IN ('provincial','municipal','district','department')
  AND d.date_published BETWEEN '2010' AND '2027'
GROUP BY 1,2;
-- panel (22): bj cq ga gd gz hlj hrss huizhou jiangmen jieyang js mzj sh shanwei shaoguan
--             suzhou swj szlg wuhan yangjiang zhongshan zhuhai

-- Central framework candidates per year (denominator for "% that echo")
SELECT substr(a.date_published,1,4), COUNT(*)
FROM documents a JOIN sites s ON s.site_key = a.site_key
WHERE s.admin_level='central' AND a.date_published BETWEEN '2008' AND '2026-10-01'
  AND a.algo_doc_type IN ('regulation','opinion','action_plan','strategy','plan','law','decree','decision','work_plan')
  AND NOT ((a.publisher LIKE '%人民代表大会%' OR a.publisher LIKE '%人大常%') AND a.publisher NOT LIKE '全国%')
GROUP BY 1;

-- Anchor-identity spot check (why §7 flags pooled representatives)
SELECT e.lag_days, e.source_title,
       (SELECT group_concat(DISTINCT c.target_ref) FROM citations c
         WHERE c.source_id = e.source_id AND c.target_ref LIKE '%《%') refs
FROM diffusion_events e WHERE e.anchor_id = 900094275 ORDER BY e.lag_days LIMIT 5;
-- sources cite 《中华人民共和国生态环境法典》; the representative row is the SPC ruling

-- Title-overlap test for §7 (what title similarity would catch): Python, per confirmed event,
-- strip genre suffixes from the anchor's 《》-core and test substring in source_title.
-- citation: 1,435 / 16,931 overlap; title_reissue: 387 / 450 overlap.
```

Python sketch for the paired tests (run over the loader rows):

```python
# unit(site): 'prov_unit' if admin_level=='provincial' or site in {cq} or site startswith bjb_/shb_/cq_
#             else 'city' | 'district' | 'dept' (Shenzhen bureaus)
# PROV[site]: province key for nesting (gd: gd*, sz*, the 16 gkmlpt cities; js: js*, suzhou, njd_*; ...)
first = {}                      # anchor -> {unit: min lag}
for e in confirmed: first.setdefault(e.anchor, {}).setdefault(e.unit, 1e9); first[e.anchor][e.unit] = min(...)
pairs = [(v['prov_unit'], v['city']) for v in first.values() if {'prov_unit','city'} <= v.keys()]
province_first = sum(p < c for p, c in pairs) / len(pairs)          # 0.749 (n=1030)
# nested: key by (anchor, PROV[site]) with slots prov_unit vs sub (city or district) -> 0.680 (n=721)
# HE index: sum(w[unit(s)] * exp(-first_lag_s/365)) over echoing sites, w = {prov 1, dept .75, city .5, district .25}
```
