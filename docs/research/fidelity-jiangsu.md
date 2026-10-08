# Jiangsu Replication: The Province-as-Translation-Layer Finding on a Second Province

*A replication on the china-governance corpus (SQLite on the droplet). All figures pulled
read-only from the live `documents.db` on 2026-10-07, after the Jiangsu deepening of 2026-10-06
(13 provincial department sites `js_*`, 4 Nanjing districts `njd_*`, 5 Suzhou districts and
county-level cities `szd_*`). Answers `corpus-lessons.md` B1: the nested central-province-city
findings in `diffusion-atlas.md` §2d and `fidelity-provincial.md` rested on Guangdong. This memo
runs the same measures on Jiangsu and recomputes Guangdong on the same `doc_identity` layer so
the two sit side by side. SQL and the sketch are in the appendix.*

---

## 0. The question and the short answer

**Question.** Do the three Guangdong results hold in Jiangsu: (1) the province echoes a central
instrument before its cities; (2) cities copy the provincial text, not the central one; (3) the
city's text descends from the province in a nested chain? And how much of any difference is
coverage rather than practice?

**Short answer.** All three hold in Jiangsu, in the same direction and at the same level, on
one twenty-fifth of the data. Province-before-city: **82.1%** of 39 nested anchor-province
pairs (Guangdong 65.1% of 704 on the same layer). City-to-province fidelity: median 5-gram
containment **0.125**, relay 8.4%, mid 26.2% (Guangdong 0.109 / 10.8% / 21.3%). Chains: the city
is closer to the province than to the center in **89.9%** of 89 chains, 94.0% for the city tier
(Guangdong 92.1% / 92.8%); center-only text is 1.4% of the city document at the median
(Guangdong 0.8%). [measured]

**The differences are coverage, not practice.** Jiangsu's sub-provincial tier is 5 city portals
(one of them, Suzhou, is 89% of the documents) and 9 shallow district crawls, against Guangdong's
15 cities, 8 districts and 13 bureaus. When Guangdong is cut to a Jiangsu-sized sample (5 random
cities, 5,514 documents, 40 draws) its province-first share rises to a median 78.5% (range 71.8
to 84.8), its city median sits at 0.109 (0.082 to 0.141) and its chain share at 93.1% (85.0 to
97.3). Every Jiangsu headline number falls inside the Guangdong subsample range. [measured]

**One new object.** The renaming layer (`doc_identity.localized_of`) agrees with the citation
picture and extends it: in both provinces 80 to 82% of renamed sub-provincial re-issuances are
renamed from a provincial text, their text overlap with that text is in the mid-to-relay band
(median 0.41 to 0.58), and the citation graph sees fewer than half of them (46% Guangdong, 44%
Jiangsu). The citation-based relay counts in the provincial memo are floors. [measured] *(Re-based
2026-10-07, §7 and `pair-channels.md` §3: "fewer than half" counts metadata-only sources; among
sources with a body the citation path sees three in four (invisible 25.5% Guangdong, 23.1%
Jiangsu), so the floor is body coverage, about 5% of relays.)*

**One corpus finding.** Suzhou's `date_published` is crawl-stamped in two batches (2023-02-09,
1,989 documents; 2025-02-11, 1,727) and `date_quality` rates it `good`, because neither batch
crosses the stamping rule's threshold. The real month is in the URL path. All Jiangsu lags here
use the repaired dates. See §7. *(Superseded 2026-10-07, `5465b8e`/`247c5f7`: the piles are the
source CMS's page-regeneration stamps (`<meta PubDate>` = 页面生成时间), not our crawl day; the
1,989 / 1,727 are YEAR counts from the Appendix A query (`substr(date_published,1,4)`), the
day-pile counts were 1,860 / 1,499; the DB was redated from the article header, then 发文日期,
then URL month (3,354 rows), and the `/YYYYMM/` folder is a 2021 migration artefact for ~250
historical 规范性文件 (1991-2011 文号 years under /202105/), so the URL-only repair used here
mis-dates that subset. Live 2026-10-07: 1 and 7 Suzhou docs remain on the two dates; 1,406
Suzhou-sourced `diffusion_events`. See §9.)*

---

## 1. Method

Identical to `fidelity-provincial.md` §1 with one change: every level comes from
`doc_identity.admin_level_doc`, not `sites.admin_level`.

**Province map.** Guangdong: `gd*`, the gkmlpt cities, `sz*` (Shenzhen portals and districts), the
13 Shenzhen bureaus. Jiangsu: `js`, `jsrd`, `js_*`, `suzhou`, `nanjing`, `wuxi`, `yancheng`,
`taizhou_js`, `njd_*`, `szd_*`. Province from the site, level from the document.

**Units.** `prov` = `admin_level_doc='provincial'`. `city` / `district` / `dept` = municipal or
district-level documents on a city portal, a district site, or a Shenzhen bureau. A
municipal-level document reposted on a provincial site is neither (27 Jiangsu, 2 Guangdong).
Central or media documents hosted on local sites are excluded.

**Targets (P).** Provincial-tier framework documents: `is_framework(algo_doc_type, title)`, not
explainer, not `NONISSUE_RE`. Guangdong 3,483, Jiangsu 2,956.

**Pairs.** Resolved `citations` edge M → P, same province, M dated on or after P (`citation`);
or M's normalized title contains P's genre stem, M passes `ISSUANCE_RE`, latest same-province P
before M, verbatim mirrors and already-cited pairs dropped (`title_reissue`). Both bodies over
500 characters. Scoring: HTML and whitespace stripped, 150k cap, character 5-grams,
`ovlp_src = |grams(M) ∩ grams(P)| / |grams(M)|`. Bands relay > 0.7, mid 0.3 to 0.7, elaboration
< 0.3. Boilerplate strip: 5-grams in ≥ 2% of a random 1,000-document sample.

**Province-before-city.** `diffusion_events` with `anchor_level='central'` and `match_type` in
(citation, title_reissue). Key (anchor, province); first lag of the `prov` slot against the first
lag of the sub slot (city or district). Same test as the atlas §2d "nested, same province".

**Chains.** For each scored P that is itself a `diffusion_events` source on a central anchor C
with body > 500: ovlp(M,P), ovlp(M,C), ovlp(P,C) and the four-way partition of M's grams.

**Date repair.** Suzhou documents are re-dated from the `/YYYYMM/` segment of their CMS URL
(day set to 15). 4,918 re-dated, 3,661 moved by more than 60 days. Event lags for 171
Suzhou-sourced events recomputed from the anchor date; 7 events whose repaired lag was below
−30 days (mis-resolved edges) dropped. Every Guangdong figure is unaffected. *(2026-10-07: the
URL month is a migration artefact for ~250 historical Suzhou documents, see §0; the DB redate
preferred the article header and 发文日期 and used the URL month only as a last fallback. On the
redated DB the Jiangsu citation basis is 473 pairs / 426 scored, relay 3.3%, with the same 14
relays, `fidelity-provincial.md` §2.2; the shares in §4 are on this memo's URL repair.)*

**Subsample.** 40 draws of 5 Guangdong city portals (from the 13 with ≥ 100 city-level
documents), then a random 5,514 of their documents (the Jiangsu city count). Pairs, chains and
events restricted to the drawn documents; the provincial side left whole.

---

## 2. Coverage first

**Table 2a. What each province's tiers contain** (evidence: `doc_identity` × `documents`).

| tier | GD docs | GD sites | GD body > 500 | JS docs | JS sites | JS body > 500 | GD / JS |
|---|---:|---:|---:|---:|---:|---:|---:|
| provincial (portal + depts + 人大) | 11,957 | 47 | 76.2% | 6,961 | 12 | 65.6% | 1.7× |
| city portal | 42,567 | 15 | 77.0% | 5,514 | 5 | 57.0% | 7.7× |
| district | 22,468 | 8 | 52.4% | 993 | 9 | 54.9% | 22.6× |
| department (Shenzhen bureaus) | 33,502 | 13 | 37.5% | 0 | 0 | | |
| **sub-provincial total** | **98,537** | 36 | | **6,507** | 14 | | **15.1×** |
| framework targets P | 3,483 | | | 2,956 | | | 1.2× |

The provincial side is comparable (1.2× in framework targets, Jiangsu's portal reaching back to
2003). The sub-provincial side is not. Suzhou alone is 4,918 of Jiangsu's 5,514 city documents;
the other four portals (盐城 207, 南京 139, 无锡 130, 泰州 120) are first shallow crawls. The 9
district sites hold 44 to 263 documents each, all dated 2025 to 2026. Jiangsu has no bureau tier.

**Table 2b. What that does to the measurement base.**

| | GD | JS | GD / JS |
|---|---:|---:|---:|
| confirmed central events, sub-provincial source | 9,199 | 140 | 66× |
| confirmed central events, provincial source | 2,292 | 1,251 | 1.8× |
| nested anchor-province pairs | 704 | 39 | 18× |
| scored P→M pairs | 5,781 | 199 | 29× |
| full C→P→M chains | 2,220 | 89 | 25× |
| first echo of a central anchor comes from the province | 890 of 2,087 (43%) | 826 of 865 (96%) | |

In Jiangsu the province carries 90% of the confirmed events; in Guangdong the cities carry 61%.
That is the shape of the crawl, and it is the reason every Jiangsu result below must be read
against the subsample in §6, not against the Guangdong headline. Year spans after repair: Jiangsu
city documents Q1/median/Q3 2016/2020/2022, Guangdong 2017/2022/2024; the Jiangsu provincial
portal 2011/2016/2023, Guangdong 2015/2022/2025. Jiangsu is older on both sides. [measured]

---

## 3. Province-before-city

**Table 3a. Nested paired test, same province, first provincial echo vs first sub-provincial
echo** (evidence: `diffusion_events`, identity-layer levels).

| test | GD n | GD province first | JS n | JS province first |
|---|---:|---:|---:|---:|
| nested, confirmed | 704 | **65.1%** | 39 | **82.1%** |
| nested, implementing sources only | 615 | 70.9% | 31 | 83.9% |
| nested, anchors 2015+ | 480 | 62.9% | 38 | 81.6% |
| nested, both echoes ≤ 365 d | 368 | 69.3% | 13 | 61.5% |
| province vs city only | 683 | 66.5% | 36 | 80.6% |
| province vs district only | 171 | 67.8% | 4 | 4 of 4 |
| province vs Shenzhen bureau | 248 | 60.9% | | |
| Jiangsu on the stamped dates (for the record) | | | 47 | 80.9% |

Median first lags: Guangdong province 195 days, sub-unit 258, sub-unit behind by 47 (IQR −75 to
+189). Jiangsu province 213, sub-unit 572, behind by 274 (IQR +38 to +619).

**Province-before-city holds in Jiangsu, more strongly than in Guangdong.** [measured] Every cut
sits at 80 to 84% except the 365-day window (61.5% on 13 pairs). The direction is the Guangdong
direction. The level is higher, and §6 shows why: the share of anchors on which *any* city beats
the province falls as the number of cities falls. Five Guangdong cities give 78.5%. Jiangsu's
82% is what five cities look like, not a tighter hierarchy.

The Guangdong figure on this layer (65.1%) is below the atlas's 68.0%. The identity layer moves
provincial documents hosted on city sites into the province's slot and drops 人大 local
regulations from the anchor side; both shift a few pairs. Direction and band unchanged.
[measured]

The lag gap is wider in Jiangsu (274 vs 47 days behind). Two causes, both coverage. Suzhou's
portal section is 市政府文件 only, about 200 documents a year, so a city echo is more often
missing than late, and the ones present are the formal re-issuances that come at six months to a
year. And Jiangsu's provincial side reaches back to 2003 while Suzhou's series thins before 2011,
so old anchors pair a prompt provincial echo with a late city one. [inferred]

---

## 4. Does the city copy the province?

**Table 4a. City tier, province-to-city pairs** (evidence: scored pairs).

| statistic | GD cities | JS cities |
|---|---:|---:|
| pairs | 4,821 | 191 |
| median ovlp_src | **0.109** | **0.125** |
| Q1 / Q3 | 0.036 / 0.425 | 0.055 / 0.434 |
| relay / mid / elaboration | **10.8 / 21.3 / 67.9** | **8.4 / 26.2 / 65.4** |
| 转发 excluded (n) | 0.100, 9.4 / 21.6 / 69.0 (4,463) | 0.123, 8.1 / 27.2 / 64.7 (173) |
| implementing subset (n) | 0.144, 12.1 / 23.9 / 64.0 (4,264) | 0.130, 8.7 / 26.2 / 65.0 (183) |
| 转发 share of city pairs | 7.4% | 9.4% |
| Spearman rho, lag vs overlap | −0.49 | −0.51 |
| boilerplate-stripped median, all tiers | 0.074 | 0.102 |
| variance between provincial targets / between sites (impl.) | 58.7% / 4.8% | 86.5% / 2.0% |

All tiers: Guangdong 5,781 pairs, median 0.085, relay 9.1%, mid 18.5%, elaboration 72.4%.
Jiangsu 199, 0.116, 8.0%, 25.1%, 66.8%. The provincial memo's central-hop comparison row was
0.074 / 3.3% / 13.7%. Both provinces sit above it on every statistic.

**The city-tier distribution is the same shape in both provinces.** [measured] Jiangsu's median
is a point and a half higher, its relay two points lower, its mid band five points wider. All
three are inside the Guangdong 5-city subsample range (§6). The histogram is the same decaying
tail with a fat upper half: Jiangsu 45.7% of pairs below 0.1, then 16.6, 4.5, 6.0, 8.0, 6.0,
5.0, 4.0, 3.5, 0.5% per tenth; Guangdong 54.0, 11.6, 6.9, 5.0, 4.5, 4.7, 4.2, 4.4, 3.2, 1.5%.

**Districts do not copy in either province.** Jiangsu 8 district pairs, median 0.079, zero relay,
zero mid. Guangdong 374, 0.040, zero relay, 2.4% mid. The bureau row (Guangdong only) is 0.048 /
1.4%. The copying tier is the prefecture city in both. [measured, Jiangsu n=8]

### 4.1 Lag

| lag from provincial instrument | GD n | GD median | GD relay | JS n | JS median | JS relay |
|---|---:|---:|---:|---:|---:|---:|
| ≤ 30 d | 138 | 0.594 | 39.9% | 7 | 0.224 | 28.6% |
| 31 to 90 d | 384 | 0.479 | 31.2% | 20 | 0.320 | 20.0% |
| 91 to 365 d | 1,599 | 0.277 | 15.5% | 51 | 0.434 | 17.6% |
| 1 to 3 y | 1,581 | 0.076 | 5.4% | 44 | 0.083 | 2.3% |
| > 3 y | 2,079 | 0.044 | 0.9% | 77 | 0.074 | 0.0% |

Lag quartiles of city pairs: Guangdong 223 / 613 / 1,729 days, Jiangsu 181 / 565 / 1,682. On the
stamped dates Jiangsu read 1,706 / 2,583 / 4,465, which would have put 92% of its pairs in the
">3 y" row and the rho at −0.06. After repair the lag composition matches Guangdong and the
rho is −0.51 against −0.49. Lag is the dominant predictor in both provinces, same strength.
Jiangsu's peak sits at 91 to 365 days rather than inside 90; with 27 pairs under 90 days that is
not a difference to lean on. [measured]

### 4.2 Genre of the provincial instrument (implementing subset)

| P genre | GD n | GD median | GD relay | JS n | JS median | JS relay |
|---|---:|---:|---:|---:|---:|---:|
| regulation (条例/办法/规定) | 830 | 0.045 | 1.1% | 53 | 0.059 | 0.0% |
| opinion (意见) | 509 | 0.118 | 7.3% | 28 | 0.134 | 3.6% |
| policy_issuance | 593 | 0.136 | 13.8% | 24 | 0.401 | 16.7% |
| action_plan | 1,360 | 0.293 | 17.4% | 60 | 0.320 | 18.3% |
| work_plan | 210 | 0.378 | 23.8% | 6 | 0.516 | 0.0% |

Same ordering, same slope. Rules are cited and rewritten (median under 0.06, relay about 1% or
zero). 方案 are copied: a provincial action_plan is relayed by 17 to 18% of its city implementers
in both provinces and sits at a median near 0.3. [measured]

### 4.3 What the relay band is

Guangdong 527 relays: 转发 forwarding notice 103 (19.5%), verbatim mirror 5 (0.9%), **city
instrument under its own masthead 419 (79.5%)**; 413 are near-identical both ways; median lag
152 days. Jiangsu 16 relays: 转发 2, mirror 0, **own-masthead city instrument 14 (87.5%)**; 13
both ways; median lag 160 days. All 16 are Suzhou. [measured]

The Jiangsu relays are the Guangdong object: 市政府办公室关于进一步完善国有企业法人治理结构的实施意见
(0.91 of the provincial 实施意见, 178 days), 苏州市全面推行行政执法公示制度…实施方案 (0.89, 179
days), 推进政务新媒体健康有序发展的实施意见 (0.84, 63 days), 推进公共资源配置领域政府信息公开的实施意见
(0.84, 30 days), 畜禽养殖废弃物资源化利用工作考核办法（试行） (0.74), 食品安全举报奖励办法 (0.71).
A 市政府办公室 notice reproducing the 省政府办公厅 notice with 江苏省 replaced by 苏州市. Renamed
re-issuance at six months is a Suzhou practice as it is a 揭阳/阳江/江门 practice. 151 of
Jiangsu's 199 citing documents carry a 市政府办公室 masthead. [measured]

What Jiangsu cannot say: the provincial memo found the renamed re-issuance concentrated in the
smaller eastern and western Guangdong prefectures (揭阳 111 relays, 江门 88, 阳江 79; 广州 12,
深圳 6). Suzhou is a large, rich prefecture and relays 9.1% of the time, which is the Guangdong
median city (0.109) and above 广州 (2.3%). Whether city size predicts relay is open; one city
cannot test it. The four other Jiangsu portals give 15 pairs, median 0.062, no relay, which is
15 pairs. [measured, n too small]

---

## 5. The three-hop chain

**Table 5a. C→P→M chains** (evidence: chain scoring).

| statistic | GD | JS |
|---|---:|---:|
| chains (distinct C, P, M) | 2,220 | 89 |
| anchors C / provincial P / sub-provincial M | 463 / 489 / 1,697 | 67 / 62 / 76 |
| **city closer to province than to center** | **92.1%** | **89.9%** |
| city tier only (n) | 92.8% (2,012) | 94.0% (83) |
| ovlp(M,P) median [Q1, Q3] | 0.218 [0.060, 0.586] | 0.267 [0.083, 0.597] |
| ovlp(M,C) | 0.058 [0.024, 0.186] | 0.108 [0.044, 0.249] |
| ovlp(P,C) | 0.187 | 0.236 |
| city grams in both P and C (central text carried through P) | 0.041 | 0.054 |
| city grams in P only (provincial rewrite) | **0.128** | **0.144** |
| city grams in C only (central text P did not carry) | **0.008** [0.003, 0.020] | **0.014** [0.006, 0.033] |
| province-descended (P-only ≥ 2 × C-only) | 58.4% | 64.0% |
| locally authored (both < 0.1) | 35.1% | 21.3% |
| mixed | 4.7% | 12.4% |
| center-descended (C-only ≥ 2 × P-only) | 1.8% | 2.2% (2 chains) |
| chains with ovlp(M,P) > 0.7 / ovlp(M,C) > 0.7 | 375 / 16 | 13 / 1 |
| median P→M lag in chains | 307 d | 259 d |

**The city descends from the province in Jiangsu as in Guangdong.** [measured] Center-only text
is 1.4% of the city document at the median and 3.3% at the upper quartile; province-only text is
ten times that. The two center-descended Jiangsu chains are a 江宁区 land-requisition notice
against 土地管理法 (ovlp(M,C) 0.14, ovlp(M,P) 0.08) and a Suzhou 公共机构节能 十二五 规划 against
the 公共机构节能条例 (0.12 / 0.08). Both are low-overlap citations of a law, not cities reading
past their province.

Jiangsu's chains carry more central text at every position (ovlp(P,C) 0.236 vs 0.187, ovlp(M,C)
0.108 vs 0.058, both 0.054 vs 0.041) and a larger mixed share (12.4% vs 4.7%). The 省政府办公厅
texts that reach Suzhou are the ones the province itself relayed from 国务院办公厅: in the four
highest chains the province kept 46 to 82% of the central text. Whether Jiangsu's provincial
office relays the center more than Guangdong's is a C→P question this memo does not measure
(the C→P hop here is conditioned on being cited onward by a city). The pattern that matters
holds: the central text in the city document is the subset the province kept. [measured for the
chain; inferred for the C→P difference]

**Worked chains.** [measured]

| C (国务院办公厅) | P (江苏省政府办公厅) | ovlp(P,C) | M (苏州市政府办公室) | ovlp(M,P) | ovlp(M,C) | both | P-only | C-only |
|---|---|---:|---|---:|---:|---:|---:|---:|
| 进一步完善国有企业法人治理结构的指导意见 (2017-05) | 实施意见 | 0.82 | 实施意见 | 0.91 | 0.78 | 0.78 | 0.14 | 0.001 |
| 全面推行行政执法公示…三项制度的指导意见 (2019-01) | 实施方案 | 0.48 | 实施方案 | 0.89 | 0.48 | 0.47 | 0.42 | 0.011 |
| 推进政务新媒体健康有序发展的意见 (2018-12) | 实施意见 | 0.45 | 实施意见 | 0.84 | 0.42 | 0.41 | 0.43 | 0.008 |
| 全面推行证明事项…告知承诺制的指导意见 (2020-11) | 实施方案 | 0.46 | 实施方案 | 0.81 | 0.43 | 0.43 | 0.38 | 0.001 |
| 加快推进畜禽养殖废弃物资源化利用的意见 (2017-06) | 考核办法（试行） | 0.08 | 考核办法（试行） | 0.74 | 0.07 | 0.07 | 0.67 | 0.000 |
| 食品安全法实施条例 (2009) | 食品安全举报奖励办法 | 0.05 | 食品安全举报奖励办法 | 0.71 | 0.04 | 0.03 | 0.68 | 0.005 |

The first row is a two-hop relay: the province kept 82% of the State Council text and Suzhou kept
91% of the province's. Suzhou's 78% of central text arrived entirely through the provincial
copy (C-only 0.001). The last two rows are the opposite case: the province wrote a new 办法 that
shares 5 to 8% with the central instrument, and Suzhou copied 71 to 74% of the provincial 办法.
In neither case does central text that the province dropped reappear in the city. This is the
`fidelity-provincial.md` §4.2 rule on a second province.

**The 以旧换新 validation cannot be run in Jiangsu.** The corpus holds 1 Suzhou, 1 provincial and
2 发改委 以旧换新 documents for Jiangsu against 43 for Guangdong, because Suzhou's crawled section
yields about 200 documents a year in 2024 to 2026 and the other Jiangsu portals are shallow.
[measured]

---

## 6. The coverage control: Guangdong at Jiangsu's size

40 draws of 5 Guangdong city portals cut to 5,514 documents, the provincial side whole.

| statistic | GD full | GD 5-city draws: min / Q1 / median / Q3 / max | JS actual |
|---|---:|---|---:|
| scored city pairs | 4,821 | 341 / 514 / 594 / 661 / 942 | 191 |
| median ovlp_src | 0.109 | 0.082 / 0.100 / **0.109** / 0.120 / 0.141 | **0.125** |
| relay | 10.8% | 5.3 / 9.2 / **10.7** / 13.1 / 15.5 | **8.4%** |
| mid | 21.3% | 17.0 / 19.7 / **21.6** / 23.4 / 27.9 | **26.2%** |
| nested pairs, province vs city | 683 | 166 / 233 / 250 / 268 / 334 | 36 |
| province first | 66.5% | 71.8 / 76.5 / **78.5** / 81.0 / 84.8 | **80.6%** |
| chains | 2,012 | 145 / 219 / 257 / 282 / 413 | 83 |
| city closer to province | 92.8% | 85.0 / 91.3 / **93.1** / 94.3 / 97.3 | **94.0%** |
| province-descended | 58.4% | 54.5 / 58.4 / 61.0 / 64.6 / 69.6 | 64.0% |
| center-descended | 1.8% | 0.7 / 1.3 / 1.5 / 2.9 / 5.6 | 2.2% |

**Every Jiangsu headline is inside the Guangdong subsample range, and most are inside its
interquartile range.** [measured] Two things the control shows:

1. **The province-first share is a function of how many cities are watched.** Guangdong moves
   from 66.5% with 15 cities to 78.5% with 5. The test asks whether any city beat the province;
   fewer cities means fewer chances. Jiangsu's 80.6% on 5 portals (one of them substantive) is
   what the Guangdong hierarchy produces at that coverage. The honest cross-province statement is
   "province before city in two-thirds to four-fifths of pairs, depending on how many cities are
   in view", and the atlas's 68 to 76% band already spans it.

2. **The fidelity and chain statistics are stable under subsampling.** Median overlap, relay, and
   the share closer to the province barely move between 15 cities and 5, and Jiangsu lands on
   them. Those three are the findings that generalize.

Jiangsu still yields 3× fewer pairs than the smallest Guangdong draw of equal document count
(191 vs 341). Suzhou's documents are 市政府 and 市政府办公室 files only, which cite the province
less often per document than the mixed gkmlpt feeds (bureau notices, announcements, 转发) that
make up a Guangdong city portal. The pairs Jiangsu does yield are therefore more often formal
instruments, which is consistent with its wider mid band and lower 转发-driven relay. [inferred]

---

## 7. The renaming layer against the citation picture

`doc_identity.localized_of` (built 2026-10-06) marks a sub-national promulgation whose title stem
reappears on a higher text in its own jurisdictional chain, and stores that text's id. It is a
title-based detector of renamed re-issuance, independent of citations and of body text.

**Table 7a. `localized_of` on the sub-provincial tier** (evidence: `doc_identity`, `citations`,
scored pairs).

| | GD | JS |
|---|---:|---:|
| sub-provincial documents with `localized_of` | 803 | 72 |
| trigger is a provincial text | **645 (80.3%)** | **59 (81.9%)** |
| trigger is a central text | 139 (17.3%) | 13 (18.1%) |
| trigger is the district's own city | 19 | 0 |
| of the provincial-trigger docs: a resolved citation to the trigger exists | 300 (46.5%) | 26 (44.1%) |
| cites any provincial document | 422 (65.4%) | 27 (45.8%) |
| cites any central document | 309 (47.9%) | 24 (40.7%) |
| provincial-trigger docs that are also scored citation pairs: n, median, relay | 166, 0.515, 28.9% | 10, 0.576, 20.0% |
| provincial-trigger docs the citation path never sees: n, median, relay | **257, 0.408, 23.0%** | 9, 0.523, 22.2% |
| chain M documents carrying `localized_of` | 206 of 1,697 | 15 of 76 |
| of those: trigger is P or P's instrument / is C or C's instrument | 67 / 25 | 7 / 0 |

**Three things the edge says.** [measured]

1. **It agrees with the citation picture on direction.** Four of five renamed re-issuances in
   both provinces are renamed from a provincial text, one in five from a central text. That is
   the translation-layer finding read from titles alone.

2. **It agrees on text.** Where a `localized_of` pair is also a citation pair its overlap is in
   the relay-to-mid band (median 0.52 to 0.58, relay 20 to 29%), five times the general pair
   median. Where it is not a citation pair the overlap is nearly as high (0.41 to 0.52, relay 22
   to 23%). The title match finds the same object the 5-gram score finds.

3. **It extends the citation picture.** The citation path sees 46% (Guangdong) and 44% (Jiangsu)
   of the renamed re-issuances. The other half reproduce the provincial text without a resolved
   citation to it: 257 Guangdong pairs at 23% relay that `fidelity-provincial.md` never scored.
   The memo's relay rate (9.1%) and its count of renamed re-issuances (381) are floors. A
   combined pair builder (citation ∪ title_reissue ∪ localized_of) is the right next step.

**Where it disagrees, the text wins.** `localized_of` attributes a renamed document to the
*highest* in-chain parent (central before provincial). In 25 Guangdong chains it points at the
central text while the city's body is closer to the provincial copy in 22 of them (median
ovlp(M,P) 0.656 against ovlp(M,C) 0.346, C-only 0.009). A 苏州市/揭阳市 X 方案 whose stem matches
both a national and a provincial X 方案 took its words from the provincial one. The renaming
layer is an identity device and should not be read as a provenance claim; the provenance is in
§5. [measured]

**`instrument_succession`** (the A2b layer) sees the C→P hop only: 16 Guangdong and 12 Jiangsu
`renamed` rows have a provincial framework target as successor. It is not built for the P→M
hop and adds nothing here. [measured]

**Re-based on the union pair set (2026-10-07).** The "fewer than half" in point 3 counts
metadata-only sources that cannot cite anything; conditioned on a source body, the citation
path sees three in four renamed re-issuances (Guangdong province-to-city: 220 `localized_of`
pairs with a body, 56 without a resolved citation, 25.5%; Jiangsu 13 and 3, 23.1%), so the
figure measures body coverage, not a resolver deficit (`pair-channels.md` §3, re-run
2026-10-07 on the 2026-10-06 nightly's `doc_identity`, 2,592 `localized_of` rows, pre-A6
schema). On the union (citation ∪ title_reissue ∪ localized_of, `scripts/rnd/analysis/pairs.py`)
the Guangdong relay count moves from 474 to 496 (8.9% to 9.1%) and the renamed re-issuance
count from 377 to 398, while Jiangsu's 14 relays do not move, so the floor in point 3 is about
5% of relays, restated in `fidelity-provincial.md` §2.2. [measured]

---

## 8. Findings

**1. Province-before-city holds in Jiangsu.** 82.1% of 39 nested pairs, 80 to 84% under every
cut with n > 30. Guangdong on the same layer is 65.1% of 704 and 78.5% when cut to five cities.
The share is a function of how many cities are watched; the direction is not.

**2. Cities copy their province in Jiangsu.** City-tier median 0.125, relay 8.4%, mid 26.2%,
against Guangdong 0.109 / 10.8% / 21.3%, all inside the Guangdong 5-city range. Lag is the
dominant predictor at the same strength (rho −0.51 vs −0.49). Regulations are cited and
rewritten, 方案 are copied, in the same order with the same slope. Districts do not copy in
either province.

**3. Relay is renamed re-issuance in Jiangsu too.** 14 of 16 relays are 市政府办公室 instruments
reproducing the 省政府办公厅 text under Suzhou's name at a median 160 days (Guangdong 79.5% of
527, 152 days). 转发 notices are a fifth of relay in Guangdong and an eighth in Jiangsu.

**4. The city descends from the province in Jiangsu.** 89.9% of 89 chains, 94.0% of city chains,
against 92.1% / 92.8% in Guangdong. Center-only text 1.4% at the median. Central text reaches
Suzhou through the Jiangsu copy, including in the one two-hop relay (国企法人治理结构: 0.82 ×
0.91, C-only 0.001).

**5. The differences are coverage.** Jiangsu's sub-provincial tier is 1/15 of Guangdong's in
documents, 1/29 in pairs, 1/25 in chains, and one city. Wider lag gap, higher province-first
share, no 以旧换新 cascade, no bureau row: each traces to what was crawled. Nothing in Jiangsu
points to a different practice.

**6. The renaming layer corroborates and extends.** 80 to 82% of renamed sub-provincial
re-issuances are renamed from the province; their text overlap is mid-to-relay; the citation
graph sees fewer than half of them *(three in four of those with a body, §7 re-base 2026-10-07)*.
The provincial memo's relay figures are floors *(by about 5% of relays, +0.2 points)*.

**7. B1 is partly discharged.** The three nested findings now rest on two provinces. They still
rest on one city in the second province. The next deepening should be a Jiangsu prefecture that
is not Suzhou (无锡, 南通, 徐州: each portal is reachable), crawled to Suzhou's depth, so the
size-predicts-relay question in §4.3 can be asked.

---

## 9. Honesty

- **Jiangsu is one city.** Suzhou is 89% of Jiangsu's city documents and 92% of its city pairs
  (176 of 191). The four other portals contribute 15 pairs. "Jiangsu cities" means Suzhou plus
  noise. The district tier (8 pairs, 6 chains) is reported for completeness and supports nothing.
- **Suzhou's dates are crawl-stamped and `date_quality` missed it.** 1,989 documents carry
  2023-02-09 and 1,727 carry 2025-02-11; 3,661 of 4,918 move by more than 60 days when re-dated
  from the URL path, and the 文号 years confirm the URL (2,118 of 3,716 文号-bearing documents
  disagree with the stamped year). The A4 rule, including the 2026-10-07 tightening to
  "≥ 50% dated on the crawl day", does not fire because the stamping is split across two crawl
  days (40% and 35%). `diffusion_events.lag_days` is wrong for Suzhou-sourced events (171 of them)
  and `validate_cascades.py`'s "JS 82d" should be checked for Suzhou dependence. [measured for
  the stamping; inferred for the validator] Fix: a `crawl_stamped` test that sums the top two
  crawl-day shares, and a URL-path date fallback in the Suzhou crawler. *(Done 2026-10-07 with
  two corrections to this bullet: the stamps are the source CMS's regeneration dates, not crawl
  stamps, and the 1,989 / 1,727 are year counts (day piles 1,860 / 1,499); the A4 rule now sums
  bulk date-days; `crawlers/suzhou.py` reads the article header first and the URL month last
  because the folder is a migration artefact for ~250 historical documents; 3,354 rows redated;
  the validator's JS 82d anchor is a `js` provincial document and was unaffected; 685 Suzhou
  docs now sit on a month-precision day 01 and still read `good`.)*
- **The repair is a month, not a day.** URL dates are year-month with the day set to 15. Lags are
  accurate to ±15 days; the ≤ 30 day band (7 pairs) is unreliable at the edges. No Guangdong
  figure uses a repaired date.
- **Guangdong on this layer differs from the memos.** 65.1% not 68.0% for the nested test; 5,781
  not 5,765 pairs; 2,220 not 2,444 chains (the chain table was rebuilt with the containment gate
  and the identity-layer pooling since 2026-10-01). Direction and bands are unchanged; quote this
  memo's Guangdong numbers when comparing with Jiangsu and the originals when citing the originals.
- **Title re-issuance in Jiangsu is 7 pairs.** The citation path carries every Jiangsu result.
- **Resolution is ~52% and lower in Jiangsu.** Suzhou documents yield 3× fewer pairs per document
  than Guangdong portals. Part of that is content mix (§6), part may be the resolver seeing
  江苏省 文号 less well than 粤 文号; not tested.
- **Boilerplate upper bound.** The 2% strip moves the Jiangsu median from 0.116 to 0.102 and
  Guangdong's from 0.085 to 0.074; bands move under a point. 省政府办公厅 / 市政府办公室 formulas
  inflate both equally.
- **One builder bug found, not fixed here.** `build_diffusion_events.province_of` resolves
  `szd_*` (Suzhou districts) to Guangdong through the `("sz", "gd")` prefix rule. It affects
  same-province gating for provincial anchors on 367 district documents. This memo uses its own
  map. Logged for the nightly builder.
- **Chronology, not causation; publication, not adoption.** As in every memo in this series.
  Mechanism-level claims about a document record. No regime-type labels.
- **No stored artifacts.** The script and result JSONs live in the session scratchpad. The
  appendix reproduces them from the live DB in about 90 seconds.

---

## Appendix A. Queries

```sql
-- Tiers on the identity layer (Table 2a); province from site_key, level from doc_identity
SELECT i.admin_level_doc, COUNT(*), SUM(length(d.body_text_cn) > 500)
FROM documents d JOIN doc_identity i ON i.doc_id = d.id
WHERE d.site_key IN ('js','jsrd','suzhou','nanjing','wuxi','yancheng','taizhou_js')
   OR d.site_key GLOB 'js_*' OR d.site_key GLOB 'njd_*' OR d.site_key GLOB 'szd_*'
GROUP BY 1;
-- NB: LIKE 'szd_%' also matches Shenzhen's szdp (8,576 docs); use GLOB.

-- Confirmed central events for the nested test (levels re-read from doc_identity in Python)
SELECT e.source_id, e.anchor_id, e.match_type, e.lag_days, e.anchor_date, e.source_implementing
FROM diffusion_events e
WHERE e.anchor_level = 'central' AND e.match_type IN ('citation','title_reissue');

-- Suzhou stamping: stamped year vs 文号 year
WITH x AS (
  SELECT substr(date_published,1,4) dy,
         CASE WHEN title GLOB '*〔[12][0-9][0-9][0-9]〕*'
              THEN substr(title, instr(title,'〔')+1, 4) END ny
  FROM documents WHERE site_key = 'suzhou')
SELECT dy, COUNT(*), SUM(ny IS NOT NULL), SUM(ny = dy), SUM(ny IS NOT NULL AND ny <> dy)
FROM x GROUP BY dy;
-- 2023: 1,989 docs, 1,499 with 文号, 78 same year, 1,421 different; 2025: 1,727 / 796 / 99 / 697

-- Suzhou real month is in the URL: /szsrmzf/<section>/YYYYMM/<hash>.shtml
SELECT substr(url, instr(url, '/20') + 1, 6), COUNT(*) FROM documents
WHERE site_key = 'suzhou' AND url GLOB '*/20[0-9][0-9][01][0-9]/*' GROUP BY 1;

-- Sub-provincial -> provincial resolved edges (then same province + framework P + M >= P in Python)
SELECT c.source_id, c.target_id FROM citations c WHERE c.target_id IS NOT NULL;
-- GD 5,544 + JS 192 citation pairs survive; 349 title_reissue pairs added; 5,980 scored

-- Central -> provincial leg for chains
SELECT e.source_id p, e.anchor_id c FROM diffusion_events e JOIN documents a ON a.id = e.anchor_id
WHERE e.anchor_level = 'central' AND e.match_type IN ('citation','title_reissue')
  AND length(a.body_text_cn) > 500;

-- Renaming layer (Table 7a)
SELECT i.admin_level_doc, t.admin_level_doc trigger_level, COUNT(*)
FROM doc_identity i JOIN documents d ON d.id = i.doc_id
JOIN doc_identity t ON t.doc_id = i.localized_of
WHERE i.localized_of IS NOT NULL AND i.admin_level_doc IN ('municipal','district')
  AND (d.site_key GLOB 'js*' OR d.site_key IN ('suzhou','nanjing','wuxi','yancheng','taizhou_js')
       OR d.site_key GLOB 'njd_*' OR d.site_key GLOB 'szd_*')
GROUP BY 1, 2;

-- A2b layer, C->P renamed rows with a provincial framework target as successor
SELECT relation, COUNT(*) FROM instrument_succession WHERE successor_id IN (<P ids>) GROUP BY 1;
```

## Appendix B. The sketch

```python
# Same pipeline as fidelity-provincial.md Appendix B, with these changes:
# 1. prov_of(site): js = js|jsrd|js_*|suzhou|nanjing|wuxi|yancheng|taizhou_js|njd_*|szd_*;
#    gd = gd*|sz*|gkmlpt cities|13 Shenzhen bureaus. unit from doc_identity.admin_level_doc:
#    'prov' if provincial; else city|district|dept by site type; municipal docs on provincial
#    sites and central/media docs on local sites -> excluded.
# 2. Suzhou date repair: m = re.search(r"/((?:19|20)\d\d)(0[1-9]|1[0-2])/", url);
#    date = date(y, m, 15); event lag = (date - anchor_date).days; drop lag < -30.
# 3. nested(events, sub_units): key (anchor_id, prov) -> {prov: min lag, sub: min lag};
#    province_first = mean(prov < sub). Cuts: implementing-only, anchor >= 2015, both <= 365.
# 4. Pairs + 5-gram scoring + chains exactly as the provincial memo (N=5, 150k cap, 500 floor,
#    BOILER = grams in >= 20 of a random 1,000 bodies). 5,980 pairs + 2,309 chains in 54 s.
# 5. localized_of: trigger level from doc_identity; "cites trigger" = EXISTS citations edge;
#    localized-only pairs scored with the same ovlp_src; chain agreement by id or instrument_id.
# 6. Subsample: 40 x (5 of 13 GD city portals with >= 100 city-level docs; random 5,514 docs);
#    pairs/chains/events filtered to the kept M ids; report min/Q1/median/Q3/max.
```

---

*(Verdict appended 2026-10-08, `fidelity-wuxi.md`: **B1 is discharged.** Wuxi was merged (`wuxi`
plus seven `wxd_*` sites, 4,877 documents) and is the second non-Suzhou Jiangsu prefecture at
comparable depth: 397 province-to-city pairs (243 scored), 195 nested central-anchor pairs, 152
full chains, against Suzhou's 551 / 144 / 97, so on two of the three measures Wuxi is the larger
sample. All three findings replicate on it, reported separately and never pooled into a Jiangsu
number: province-before-city **83.6% of 195** (Suzhou 69.4% of 144, Guangdong cities 68.2% of
1,046 pooled), city closer to the province than to the centre **94.1% of 152** (Suzhou 96.9%,
Guangdong 91.6%, centre-only text 1.4% of the Wuxi document at the median against 16.0%
province-only), city fidelity median **0.115** / relay **5.3%** / mid **18.5%** on the union basis
(Suzhou 0.054 / 4.3% / 12.4%, Guangdong 0.097 / 9.9% / 19.7%), with 12 of Wuxi's 13 relays
own-masthead 市政府办公室 re-issuances of the 省政府办公厅 text at a 185-day median lag, the same
object as §4.3's. **One correction to this memo's headline.** The Jiangsu relay rate of 3.3%
against Guangdong's 10.8% is not a provincial fact. Measured per CITY, Guangdong's own relay rate
runs 2.2% (广州) to 18.4% (阳江), median 8.9% over the 13 portals with 50 or more scored pairs, and
both Jiangsu cities fall inside that spread at and just below its first quartile, beside 广州 and
深圳; the Guangdong ordering runs from the large coastal prefectures to the small ones, so §4.3's
open question ("whether city size predicts relay is open; one city cannot test it") resolves in
favour of city capacity rather than province [inferred for scale, measured for the ordering].
Province-before-city (per-city range 61.7 to 90.0, median 83.6, Wuxi exactly on it) and chain
descent (79.3 to 98.0, median 93.5) are stable across that distribution, so only the relay number
was a composition artefact of pooling 15 Guangdong cities against one Jiangsu city. Three further
notes: Wuxi's dates need no repair (all 4,877 `date_quality='good'`, one row where the
`/doc/YYYY/MM/DD/` path disagrees with `date_published`, 文号-year agreement 93.8%); the `wxd_*`
tier makes the city-to-district hop measurable in Jiangsu for the first time and **contradicts**
§8's "districts do not copy in either province" (309 pairs, 227 scored, median 0.112, relay 12.8%
against Guangdong districts' 1.0%), though the titles split it into 转发 by urban districts within
the month and renamed re-issuance by the county-level cities 江阴/宜兴 at 140 to 587 days; and
1,707 Wuxi municipal rows are still awaiting a second merge (blocked by the nightly write lock),
which the per-genre rates project at +274 pairs, so the verdict does not depend on them. The Wuxi
memo rebuilt `doc_identity`, `citations` and `diffusion_events` read-only because the live ones
predate the merge, and its Suzhou citation basis (507 pairs / 426 scored / relay 3.5%) reproduces
`fidelity-provincial.md` §2.2's 473 / 426 / 3.3%.)*
