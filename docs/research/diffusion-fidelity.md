# Diffusion Fidelity at Corpus Scale: Localities Elaborate, Provinces Forward

*A worked analysis on the china-governance corpus (SQLite on the droplet). All figures pulled
read-only from the live `documents.db` on 2026-10-01. Extends `ai-plus-fidelity.md` (ten AI+
pairs, 87 to 98% locally authored) to the whole `diffusion_events` table. Research-agenda Q6:
when a locality implements a central instrument, does it relay the text or author its own, and
what predicts which? SQL and the 5-gram sketch are in the appendix.*

---

## 0. The question and the short answer

**Question.** `diffusion_events` holds 24,599 anchor-to-source pairs (a central anchor document
and a sub-national document that cites it, re-issues its title, or shares topic and genre).
*(Build note 2026-10-01: the 24,599 / 18,088 confirmed / 13,509 scored figures are from the
post npc/explainer-fix build, before the resolver fix. The table is rebuilt nightly and held
32,825 rows (26,565 central, of which 20,074 confirmed, plus 6,260 provincial) on 2026-10-01; a
further resolver regression fix in progress will change it again. The distribution and the
orderings are the finding; the raw pair counts are not current. See `consistency-review.md`
H2.)* For
every confirmed pair with both bodies in hand, what fraction of the local text is the central text
reproduced? Is the corpus-wide distribution bimodal, as the AI+ case was? And does the thesis from
the two case memos hold at scale: fiscal and rule-bound instruments relayed, promotional ones
elaborated?

**Short answer.** Elaboration is the norm everywhere. Across **13,509 scored pairs**, the median
local document shares **5.6%** of its character 5-grams with the central anchor. **88.3%** of pairs
sit below 0.3 (elaboration), **9.8%** in the 0.3 to 0.7 band (localized paraphrase), and only
**1.9%** above 0.7 (relay). The distribution is **not bimodal** corpus-wide. It is a decaying tail
with a small verbatim bump at 0.9 to 1.0 (78 pairs, 0.6%). The AI+ case looked bimodal because it
had two news reposts and ten plans and nothing else.

The relay cluster has one mechanism: **provincial forwarding notices** (转发). 59% of relays carry
转发 in the title, and 183 of 254 come from three portals (广东 127, 北京 30, 黑龙江 26). Strip
those and relay nearly vanishes.

**Who elaborates most: districts and departments, not provinces.** District median overlap is
0.030 with zero relays. Provincial median is 0.074 with a 3.3% relay rate. The gradient is
monotonic: province 0.074, city 0.051, department 0.031, district 0.030. The province is the
forwarding tier. The levels below it write.

*(Level basis corrected 2026-10-08. **The four-step gradient above is not reproducible as stated**,
because `department` is not a per-document level. It was a `sites.admin_level` value, and
`sites.admin_level='department'` names a **kind** of body rather than a **tier**: all 14 such sites
are **Shenzhen municipal bureaus** (公安局, 民政局, 人力资源和社会保障局, 商务局, 交通运输局,
住房和建设局, 科技创新局, 司法局, 应急管理局, 教育局, 发改委, 卫健委, 审计局, plus 中山市自然资源局),
and `doc_identity.admin_level_doc` correctly resolves **33,594 of their 33,997 documents to
`municipal`**. So the old "department 0.031" row is a subset of the city row, not a tier below it,
and the gradient has three steps, not four. `scripts/rnd/analysis/pairs.py` cannot emit a
department subset — `LEVEL_CODE` holds only central/provincial/municipal/district — which is how
this was caught.*

***The re-based gradient, measured** (35,331 scored citation-channel pairs, the same basis as the
memo, which had 13,509 — the growth is corpus and resolver, not method):*

| basis | provincial | municipal | department | district |
|---|---|---|---|---|
| **per-document (correct)** | **0.063** (n=13,204) | **0.049** (n=20,614) | — | **0.046** (n=1,513) |
| site level (the old basis), today | 0.062 | 0.053 | 0.036 | 0.044 |

*Two corrections follow, one expected and one not.*

*As expected, **merging the old department row into city pulls the city median down** (0.053 →
0.049, because the merged documents sit at 0.036), so the **province-to-city gap widens from 0.009
to 0.014** — the memo's own point, that the province is the forwarding tier, gets stronger.*

***Not expected: "districts and departments elaborate most" is wrong in emphasis.** District is
**0.046**, not the 0.030 the memo reports, and on the site basis today it is 0.044 — so the memo's
district figure was stale independently of the level question. City-to-district is therefore nearly
**flat** (0.049 vs 0.046) where the memo had a wide gap (0.051 vs 0.030). The defensible claim is
narrower: **the province-to-city step is the real one, and everything below the province is flat.**
Relatedly, "District median overlap is 0.030 with **zero relays**" reads **0.9%** relays today, low
but not zero. The gradient is still monotonic — 0.063 > 0.049 > 0.046 — so the direction of the
finding is intact; its shape is one step, not three.)*

*Two things checked at the same time and found clean, recorded so they are not re-checked:
`diffusion_events` contains **no `media` rows at all** (only municipal 26,135 / provincial 16,575 /
district 2,814), and `pairs.py` excludes `media` by construction and already reads
`admin_level_doc` rather than `sites.admin_level`. So this memo's pair set was never contaminated
by press coverage — the trap that overstated local reach eightfold in
`ai-governance-diffusion.md` finding 2 does not reach here.)*

**The fiscal-versus-promotional thesis holds in direction and fails in magnitude.** Anchors in the
top fiscal-keyword quartile get about twice the text reuse of the bottom quartile (median 0.076 vs
0.044, Spearman rho 0.24), and the 以旧换新 re-issuances (median 0.168) borrow roughly eight times
more text than the AI+ plans (median 0.020). But neither is relay. Every one of the 17 以旧换新
re-issuances is below 0.3. Money produces **templated elaboration**, not reproduction. The
rule-bound half of the thesis is wrong outright: 条例/办法/决定 anchors are the **least** copied
genre (median 0.042, 95% elaboration). Localities cite rules as authority and write their own.

The strongest single predictor is **lag**. Pairs within 90 days of the anchor relay 9 to 10% of the
time; pairs after a year relay 0.2% of the time. Forwarding is a fast act. Late citers are authors.

---

## 1. Method

**Pairs.** `diffusion_events` rows with `match_type IN ('citation','title_reissue')` (n=18,088;
the 6,511 `topic_genre` rows are inferred, not confirmed, and are excluded). Both anchor and source
need `length(body_text_cn) > 500`. That leaves **13,509 pairs (74.7%)**: 13,253 of 17,650
citations and 256 of 438 title re-issues. They span **2,336 anchors** (all central: `gov` 1,897,
`chinatax` 122, `mof` 60, `ndrc` 50, `cac` 39; dated 2000 to 2026, bulk 2015 onward) and
**11,204 source documents** across **322 sub-national sites**. No sampling. Every qualifying pair
was scored.

**Overlap.** Bodies are HTML-stripped, whitespace-stripped, capped at 150k characters. Each body
becomes a set of character 5-grams. The headline metric is

- **`ovlp_src`** = |5-grams(source) ∩ 5-grams(anchor)| / |5-grams(source)|. The fraction of the local
  document that is central text. Verbatim repost tends to 1.0. All-local rewrite tends to 0.

Also recorded: `ovlp_anc` (same intersection over the anchor's grams), Jaccard, and
**`ovlp_src_nb`**, which drops a boilerplate set first. Boilerplate = the 1,684 5-grams present in
at least 2% of a random 1,000-document sample (现印发给你们, 认真贯彻落实, 各市人民政府, dates and
文号 fragments). Anchor grams are computed once per anchor; sources are scored in a single pass
(13,509 pairs in 105 s on the droplet).

**Bands.** Relay > 0.7. Mid 0.3 to 0.7. Elaboration < 0.3. Same cut points as the AI+ memo.

**Predictors.** `match_type`, `source_level`, `topic` (from `diffusion_events`), anchor and source
`algo_doc_type` (regex genre), lag, anchor fan-out, lengths, and a fiscal proxy: count of
money terms per 10k characters in the anchor body (补贴, 专项资金, 财政资金, 资金支持, 奖励, 国债,
补助, 税收优惠, 减免, 资助, 经费, 奖补), cut into quartiles. A **transfer flag** marks sources whose
title contains 转发. An **implementing-instrument subset** (n=8,076) keeps only sources whose genre
is action_plan, work_plan, policy_issuance, opinion, notice, regulation, decision, strategy or
subsidy. It drops explainers, news, reports and announcements, which cite without implementing.

---

## 2. The distribution

**Table 2a. Histogram of `ovlp_src`, all 13,509 pairs** (evidence: scored CSV).

| band | n | share |
|---|---:|---:|
| 0.0 to 0.1 | 9,166 | 67.9% |
| 0.1 to 0.2 | 1,812 | 13.4% |
| 0.2 to 0.3 | 954 | 7.1% |
| 0.3 to 0.4 | 625 | 4.6% |
| 0.4 to 0.5 | 365 | 2.7% |
| 0.5 to 0.6 | 203 | 1.5% |
| 0.6 to 0.7 | 130 | 1.0% |
| 0.7 to 0.8 | 98 | 0.7% |
| 0.8 to 0.9 | 78 | 0.6% |
| 0.9 to 1.0 | 78 | 0.6% |

Median 0.056. Mean 0.121. Quartiles 0.026 and 0.140. Within the bottom band, 6,310 pairs (47% of
all) are below 0.05.

**The split: relay 1.9% (254), mid 9.8% (1,323), elaboration 88.3% (11,932).**

**Shape.** Monotonic decay from zero, with a flat floor from 0.7 and a faint bump at 0.9 to 1.0.
That bump is the verbatim-repost cluster the AI+ memo saw. It exists. It is 0.6% of the corpus.
There is no empty middle: the 0.3 to 0.7 band holds 1,323 pairs, ten times the relay band. The AI+
memo's "wide empty middle" was a feature of a 12-document set, not of diffusion in general.

**Boilerplate check.** With the boilerplate set removed, the median falls from 0.056 to 0.048 and
the bands barely move (relay 1.9%, elaboration 88.6%). Common notice chrome inflates overlap by
roughly one percentage point at the median. Phrases shared by fewer than 2% of documents still
count, so all figures remain upper bounds on substantive reuse.

**What the mid band is.** 71% provincial, and 53% of its sources are `action_plan` genre. Typical
rows: 黑龙江 re-issuing the central 水资源刚性约束制度考核办法 as a provincial 考核办法 (0.42), 北京
turning the State Council 商业健康保险若干意见 into a 实施意见 (0.57), 中山 turning 体育产业若干意见
into a 实施意见 (0.32). These keep the central section structure and swap in local content. This is
localized paraphrase. It is the modal form of provincial implementation of a central 意见.

**What the relay band is.** 254 pairs. Median source-to-anchor length ratio 1.07. 202 of 254 are
near-identical both ways (`ovlp_anc` > 0.7 too). 150 carry 转发 in the source title: 广东省人民政府转发
国务院关于..., 黑龙江省人民政府转发..., 江门 转发省府办公厅转发国务院办公厅转发.... The rest are
department-portal full-text reposts and news items reproducing a central text (e.g. 福建国资委
"首次出台！中办、国办印发重要意见（全文+专家解读）", 0.84). Relay is a publishing act, not an
implementing act.

---

## 3. Predictors

All tables: n, median `ovlp_src`, relay share (> 0.7), elaboration share (< 0.3).

### 3.1 Match type

| match_type | n | median | relay | elab |
|---|---:|---:|---:|---:|
| citation | 13,253 | 0.056 | 1.8% | 88.4% |
| title_reissue | 256 | 0.057 | 5.9% | 84.4% |

Title re-issuance triples the relay rate but the median is identical. A locality that reuses the
central title still writes 94% of its own text in the typical case.

### 3.2 Administrative level

| source_level | n | median | relay | elab | 转发 share |
|---|---:|---:|---:|---:|---:|
| provincial | 6,809 | 0.074 | 3.3% | 83.0% | 7.5% |
| municipal | 4,539 | 0.051 | 0.6% | 91.6% | 3.7% |
| department | 1,360 | 0.031 | 0.3% | 97.7% | 0.8% |
| district | 801 | 0.030 | 0.0% | 98.9% | 1.0% |

*(This table is on **site** levels. `department` is not a per-document level — all 14 such sites are
Shenzhen municipal bureaus — so on the correct basis its row merges into `municipal` and the table
has three rows, not four. Re-measured 2026-10-08 on 35,331 scored citation pairs: **provincial
0.063 (n=13,204), municipal 0.049 (n=20,614), district 0.046 (n=1,513)**, district relay 0.9% rather
than 0.0%. See the correction under §"Who elaborates most" above.)*

**Provinces reuse the most central text, districts the least.** The gradient survives every
robustness cut. Excluding 转发 pairs: province 0.072, district 0.030. Excluding the three
heavy-forwarding portals (gd, bj, hlj): province 0.063, district 0.030. Restricting to implementing
instruments: province 0.096 (relay 4.6%, elaboration 77%), city 0.052, department 0.043, district
0.027 (zero relay, 98.5% elaboration).

Two mechanisms, both visible in the data. First, **forwarding is a provincial genre.** 7.5% of
provincial pairs are 转发 notices against 1% at district level, and 广东 alone forwards in 24% of its
pairs. Second, **the province is the first paraphraser.** Its 实施意见 keeps the central skeleton
(the mid band is 71% provincial). Levels below it are two steps from the central text and write
under the provincial instrument, not the central one.

**Caveat that matters.** Every anchor in `diffusion_events` is central. There are no
province-to-city pairs. A district's 0.03 overlap with the State Council text says it does not
copy Beijing. It does not say whether it copies its province. That measurement needs
province-anchored pairs and is the natural next step.

**Site composition.** Relay rate among provincial portals with n ≥ 100: 广东 11.2%, 黑龙江 4.4%,
北京 2.3%, 广东医保局 1.5%, 江苏 0.5%, 上海 0.1%, 山东 0.0%. 上海 cites with 转发 in 17% of titles
but relays in 0.1%, so its forwarding notices carry a rewritten body. Forwarding style is a portal
practice, not a level constant. Among cities (n ≥ 100) no site exceeds 1.7% relay.

### 3.3 Anchor genre

Implementing-instrument subset (n=8,076), anchor `algo_doc_type`:

| anchor genre | n | median | relay | elab |
|---|---:|---:|---:|---:|
| regulation (条例/办法/规定) | 1,462 | 0.037 | 1.0% | 94.3% |
| decision | 502 | 0.047 | 2.2% | 88.8% |
| policy_issuance | 825 | 0.049 | 2.8% | 82.2% |
| strategy | 493 | 0.073 | 3.0% | 86.4% |
| action_plan | 852 | 0.095 | 2.3% | 82.0% |
| notice | 358 | 0.097 | 6.1% | 76.8% |
| work_plan | 121 | 0.097 | 2.5% | 75.2% |
| opinion (意见) | 3,252 | 0.109 | 3.4% | 77.9% |

**Rules are cited, opinions are paraphrased.** A 条例 or 办法 is referenced as the legal basis for a
locally drafted instrument (江门市重大行政决策程序规定 against the central 暂行条例: 0.31, and that is
a high case). An 意见 is the genre that becomes a provincial 实施意见 with the skeleton intact. The
ordering is the reverse of the thesis that rule-bound instruments get relayed. Rule-bound anchors
also have the largest fan-out (statutes cited by dozens of unrelated documents), which pulls their
median down; the implementing-subset restriction above already removes the mere-reference citers
and the ordering holds.

### 3.4 Money

Anchor fiscal density quartile (money terms per 10k chars; quartile edges 0, 2.4, 7.8), all pairs:

| quartile | n | median | relay | elab |
|---|---:|---:|---:|---:|
| q1 (no money terms) | 3,378 | 0.044 | 1.7% | 91.4% |
| q2 | 3,377 | 0.041 | 1.2% | 92.3% |
| q3 | 3,377 | 0.070 | 2.2% | 86.1% |
| q4 (highest) | 3,377 | 0.076 | 2.4% | 83.5% |

Spearman rho (fiscal density vs overlap) = 0.24 across all pairs, 0.21 in the implementing subset.
Within implementing instruments the medians are 0.051 (q1) and 0.089 (q4). Excluding 转发 pairs the
relay rate is about 1% in every quartile, so money does not drive relay at all; it drives the
median up.

A three-way instrument class makes the comparison direct (implementing subset):

| instrument class | n | median | relay | mid | elab |
|---|---:|---:|---:|---:|---:|
| money-carrying (top fiscal quartile) | 2,078 | 0.107 | 3.4% | 18.6% | 78.0% |
| promotional (意见/方案, bottom-half fiscal) | 1,627 | 0.078 | 3.0% | 14.1% | 83.0% |
| rule-bound (条例/办法/决定) | 1,964 | 0.039 | 1.3% | 5.8% | 92.9% |

The class-by-level cut shows the same order at every tier (money-carrying provincial 0.145,
municipal 0.084; promotional provincial 0.102, municipal 0.059).

**Verdict on the thesis.** Fiscal instruments do get more text reuse than promotional ones. The
effect is a shift from a 0.08 median to a 0.11 median and a four-point move in the mid band. It is
not a shift into relay. The two case memos described a difference in kind (re-issuance vs
authored elaboration). At scale it is a difference in degree within elaboration. The rule-bound
clause of the thesis is wrong: rules are the least reproduced class.

### 3.5 Topic

Implementing subset, topics with n ≥ 100, extremes:

| topic | n | median | relay | elab |
|---|---:|---:|---:|---:|
| Agriculture | 407 | 0.178 | 4.7% | 70.8% |
| Welfare | 322 | 0.108 | 1.9% | 83.5% |
| Health | 484 | 0.095 | 2.1% | 74.2% |
| Culture | 101 | 0.084 | 2.0% | 81.2% |
| ... | | | | |
| Housing | 195 | 0.048 | 2.1% | 89.7% |
| Transport | 211 | 0.042 | 3.8% | 87.2% |
| Energy | 103 | 0.041 | 4.9% | 92.2% |
| Emergency | 150 | 0.036 | 3.3% | 84.7% |

Across all pairs, Party (n=366) and Diplomacy (n=210) have zero relays and 100% elaboration;
nothing in those topics is reproduced. Agriculture is the most templated topic in the corpus: a
quarter of its implementing pairs sit in the mid band. Rural-policy 意见 cascade with the central
section structure preserved. Technology (Tech, n=265 implementing) sits at 0.058, in the lower
half, consistent with the AI+ finding.

### 3.6 Lag, fan-out, length

| lag from anchor | n | median | relay | elab |
|---|---:|---:|---:|---:|
| ≤ 30 days | 646 | 0.113 | 8.7% | 75.2% |
| 31 to 90 days | 1,070 | 0.090 | 10.1% | 78.6% |
| 91 to 365 days | 4,293 | 0.076 | 1.6% | 81.9% |
| 1 to 3 years | 5,049 | 0.046 | 0.2% | 93.6% |
| > 3 years | 2,398 | 0.040 | 0.2% | 97.1% |

Lag is the strongest continuous predictor (rho −0.28 all pairs, −0.34 implementing). Relay is
concentrated in the first quarter after promulgation. After a year, the citing document is almost
always a new instrument that mentions an old anchor.

Anchor fan-out: anchors with more than 30 scored citers have median 0.041 and 0.3% relay; anchors
with 1 to 10 citers have medians near 0.07 and 3 to 5% relay (rho −0.16). Heavily cited anchors
are statutes and framework 意见 referenced by many unrelated documents.

Source length: sources over 20k characters have median 0.008 (the denominator swamps any shared
passage); sources of 5k to 10k have the highest relay rate (3.3%), which is the size of a typical
forwarded 意见.

### 3.7 Where the variance lives

Among the 1,219 anchors with at least three scored sources, **none** is all-relay, **86.5%** have
no relay at all, and 13.5% are mixed. In the implementing subset, 53% of the variance in overlap is
between anchors and 14% is between source sites. **What instrument is being implemented explains
more than which locality is implementing it.** For anchors with at least five implementing
sources (n=537), the median inter-quartile spread of overlap within an anchor is 0.085, so
localities implementing the same instrument do cluster.

---

## 4. Validation against the two case memos

**以旧换新 (fiscal, `consumption-diffusion.md`).** 119 scored pairs on anchors containing 以旧换新.
The 17 title re-issuances run from 0.031 (惠州 标准提升 plan) to 0.284 (广东省 实施方案), median
0.168. Zero relay. All 17 below 0.3. Guangdong's cities sit at 0.06 to 0.25. The province is the
highest point, which fits the two-step reading: cities draft under the provincial 实施方案. The
102 citation pairs have median 0.059. The consumption memo's "re-issuance cascade" is, in text
terms, elaboration with roughly one-sixth of the body borrowed, not reproduction.

**提振消费.** 9 title re-issuances, median 0.062; 20 citations, median 0.020. All elaboration.

**人工智能+ (promotional, `ai-plus-fidelity.md`).** 37 scored pairs. The genuine local plans land
where the memo put them: 苏州 0.128, 重庆 0.083, 黑龙江 0.070, 济宁 0.030, 海淀 养老 0.021, 江苏交通
0.017. The 8 title re-issuances have median 0.020 and the 11 implementing citations median 0.026.
Two pairs relay (0.81, 0.95), and both are news reposts of central text (江苏科技厅 "人工智能产业迎
重磅利好！", 西藏文旅厅 repost of the 8-department AI+消费 release), the same pattern as the memo's
two Zhejiang and Jiangsu reposts.

**Reading the two together.** 以旧换新 re-issuances (median 0.168) borrow about eight times more
text than AI+ re-issuances (median 0.020). That is the thesis in direction. Both sit inside the
elaboration band. That is the thesis failing in magnitude. The right description is a continuum of
templating with fiscal instruments higher on it, not two regimes of diffusion.

---

## 5. Findings

**1. Elaboration is the corpus-wide norm.** 88% of confirmed diffusion pairs share under 30% of
their text with the central anchor; the median shares 5.6%. The high-local-agency reading from the
AI+ memo generalizes. The bimodality does not.

**2. Relay is a publishing act by provinces, concentrated in a few portals.** 1.9% of pairs, 59%
of them 转发 notices, 72% from 广东, 北京 and 黑龙江. It happens within 90 days of promulgation and
almost never after a year.

**3. The level gradient runs the other way from the naive expectation.** Provinces reuse the most
central text (median 0.074, relay 3.3%); districts the least (0.030, zero relay). The province
forwards and paraphrases; the city and district author. Since all anchors here are central, the
district figure is overlap with the central text only; overlap with the provincial instrument is
unmeasured and probably higher.

**4. Money raises templating, not relay.** Top fiscal-quartile anchors get about double the
median reuse of the bottom quartile and 以旧换新 re-issues borrow about eight times the text of AI+
plans, but every fiscal re-issuance observed is still below 0.3. The money-relayed clause of the
thesis fails; the money-more-templated clause holds.

**5. Rules are the least copied genre.** 条例/办法/决定 anchors have median 0.037 to 0.047 and 89 to
94% elaboration. Localities cite a rule as authority and draft their own. 意见 is the genre that
gets paraphrased into a 实施意见 (median 0.109, 19% mid band).

**6. The instrument explains more than the locality.** 53% of overlap variance is between anchors,
14% between source sites. Agriculture and welfare cascade with the skeleton kept; party,
diplomacy, energy and emergency instruments are rewritten from scratch.

---

## 6. Honesty

- **Coverage.** 74.7% of confirmed pairs could be scored. The department tier is the gap: only 60%
  of department-level sources have a body over 500 characters (1,599 of 2,672), against 90 to 96%
  for the other tiers. Department fidelity (median 0.031) rests on the better-crawled 60%.
  *(2026-10-07: 88.8% of department-site documents have SOME body; the 60% is the over-500-
  character share. The A7 backfill found the gap is short notices and attachments, not
  extraction, `corpus-lessons.md` A7 correction.)*
- **Attachments.** Many implementation plans are PDF or DOC attachments under a short cover notice.
  Where only the cover note is in `body_text_cn` the overlap is meaningless in either direction. The
  500-character floor removes the worst cases, not all of them.
- **Boilerplate.** Shared notice chrome inflates overlap. The 2%-frequency boilerplate strip moves
  the median by about 0.01, so the inflation at the median is small, but rarer formulaic passages
  still count. All overlap figures are upper bounds on substantive reuse.
- **Citation is not implementation.** A citation pair includes explainers, news, reports and
  announcements that reference an anchor without implementing it. The implementing-instrument
  subset (n=8,076) addresses this and every headline ordering holds within it. The genre labels
  are regex (`algo_doc_type`), with about a third of the corpus still typed `other`.
- **All anchors are central.** `diffusion_events` has no provincial anchors. Every level is
  measured against the central text only. The province-to-city step, which is where the
  consumption memo found the tightest cascade, is not measured here. *(Update 2026-10-01: the
  province-to-city step is now measured in `fidelity-provincial.md`, and since commit `c6dbe04`
  `diffusion_events` carries provincial anchors under `anchor_level`; this memo's figures use
  the central rows only.)*
- **Coverage and resolution.** The 322 source sites are Guangdong-heavy at the city and district
  tiers and proxy-blocked provinces are invisible, so the level medians are within-corpus, not
  national. Pairs come from the citation graph, which resolves ~52% of edges, so every pair
  count is a floor. *(Added 2026-10-01 per `consistency-review.md` §2.)*
- **Scope boundary.** Mechanism-level claims about a published document record. No regime-type
  labels. *(Added 2026-10-01.)*
- **The fiscal proxy is keyword density.** It separates 补贴/资金-heavy anchors from the rest and
  nothing finer. It does not read the amount of money or whether the locality receives any.
- **Normalization.** Bodies capped at 150k characters; whitespace and tags stripped; no
  punctuation folding. A locality that reproduces a central passage with different punctuation
  scores lower than it should. The relay calibration points (verbatim reposts at 0.97 to 1.0)
  confirm the metric saturates when text is actually copied.
- **Documentary face only.** Overlap measures published text. It says nothing about whether a
  low-overlap local plan changes more or less on the ground than a high-overlap one.

---

## Appendix A. Queries

```sql
-- Confirmed pairs with both bodies (n=13,509 of 18,088)
SELECT e.anchor_id, e.source_id, e.match_type, e.lag_days, e.topic, e.source_level,
       a.site_key AS a_site, sa.admin_level AS a_level, a.algo_doc_type AS a_genre, a.title AS a_title,
       s.site_key AS s_site, s.algo_doc_type AS s_genre, s.title AS s_title
FROM diffusion_events e
JOIN documents a ON a.id = e.anchor_id
JOIN documents s ON s.id = e.source_id
LEFT JOIN sites sa ON sa.site_key = a.site_key
WHERE e.match_type IN ('citation','title_reissue')
  AND length(a.body_text_cn) > 500 AND length(s.body_text_cn) > 500
ORDER BY e.anchor_id;

-- Coverage denominator
SELECT e.match_type, COUNT(*) total,
       SUM(length(a.body_text_cn)>500 AND length(s.body_text_cn)>500) scored
FROM diffusion_events e
JOIN documents a ON a.id=e.anchor_id JOIN documents s ON s.id=e.source_id
WHERE e.match_type IN ('citation','title_reissue') GROUP BY 1;
-- citation 17650 -> 13253 ; title_reissue 438 -> 256

-- Source-side body coverage by level (department tier is the gap)
SELECT source_level, COUNT(*), SUM(length(s.body_text_cn)>500)
FROM diffusion_events e JOIN documents s ON s.id=e.source_id
WHERE e.match_type IN ('citation','title_reissue') GROUP BY 1;
-- department 2672/1599 ; district 1075/975 ; municipal 5813/5552 ; provincial 8528/8152

-- Anchor fiscal proxy (per anchor, Python counts the 12 money terms in body_text_cn)
SELECT anchor_id, COUNT(*) FROM diffusion_events
WHERE match_type IN ('citation','title_reissue') GROUP BY 1;   -- 2,880 anchors (2,336 scored)
```

## Appendix B. The 5-gram sketch

```python
import re, sqlite3
N = 5
TAG, WS = re.compile(r"<[^>]+>"), re.compile(r"\s+")
norm  = lambda t: WS.sub("", TAG.sub("", t or ""))[:150_000]
grams = lambda t: {t[i:i+N] for i in range(len(t) - N + 1)}

c = sqlite3.connect("file:documents.db?mode=ro", uri=True)

# boilerplate: 5-grams in >= 2% of a random 1,000-doc sample (1,684 grams)
from collections import Counter
df = Counter()
for (i,) in c.execute("SELECT id FROM documents WHERE length(body_text_cn)>500 ORDER BY random() LIMIT 1000"):
    df.update(grams(norm(c.execute("SELECT body_text_cn FROM documents WHERE id=?", (i,)).fetchone()[0])))
BOILER = {g for g, n in df.items() if n >= 20}

# pairs ordered by anchor so each anchor's gram set is built once
A = None; cur = None
for anchor_id, source_id, *meta in c.execute(PAIRS_SQL):
    if anchor_id != cur:
        cur = anchor_id
        A = grams(norm(body(anchor_id))); A_nb = A - BOILER
    S = grams(norm(body(source_id))); S_nb = S - BOILER
    inter = len(S & A)
    ovlp_src    = inter / len(S)                 # relay -> 1, elaboration -> 0
    ovlp_anc    = inter / len(A)
    jaccard     = inter / (len(S) + len(A) - inter)
    ovlp_src_nb = len(S_nb & A_nb) / len(S_nb)   # boilerplate-stripped variant
# 13,509 pairs, 105 s on the droplet. Bands: relay > 0.7, mid 0.3-0.7, elaboration < 0.3.
```

Predictor tables were produced with pandas group-bys over the resulting CSV. Spearman rho is
Pearson on ranks. Fiscal quartiles are rank-based on money terms per 10k anchor characters.
