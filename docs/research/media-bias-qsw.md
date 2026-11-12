# Party-owned and commercial media on one corpus: a scoped replication of Qin, Strömberg & Wu (2018)

*First pass, 2026-11-12. Pre-registration: `docs/working/prereg-qsw-media-bias.md` (written before
any outcome term was counted, with two dated notes and a time correction appended). Script:
`scripts/rnd/analysis/media_bias_qsw.py`. Evidence labels: **measured** = counted in the corpus or
read from a named source, command in the appendix; **stated** = what a source says; **inferred** =
my reading of measured patterns; **unverified** = believed, not checked here.*

## The question

Qin, Strömberg and Wu measured what Chinese newspapers print and found two products: Party
dailies carry the Party line (leaders, Xinhua copy), commercial papers carry what sells (sport,
entertainment, crime). Their surprise was the third dimension: commercial papers did **not**
carry more accountability news (corruption, disasters, accidents); they carried less. This memo
asks whether the same content gap appears among the speaker types our corpus holds for
2025-07 to 2026-11, and where the corpus can add something a newspaper archive cannot.

**Short answer (measured).** The Party-line gap replicates and is far larger than theirs: a
Party-owned media site puts Xi or 总书记 in **39.7** titles per 1,000, a commercial site in **0.3**
(site means, exact permutation p < 0.001), and relays Xinhua copy at **267** against **7** per
1,000. The bottom-line gap replicates in sign for market news (commercial **4.4x**, p = 0.019) and
for soft news (**1.7x**, p = 0.23, not significant). The accountability result does **not**
replicate as a group contrast: commercial sites carry named corruption cases at about twice the
Party-owned rate (ratio 0.47, p = 0.21) and accidents at about the same rate. But across the 15
sites the accountability measures rise **with** the Party-line measure (Spearman +0.59 to +0.69),
which is QSW's one-dimension structure: accountability content travels with general-news outlets,
and in this corpus the commercial general-news outlets are a commentary portal and a news portal
while the commercial specialist outlets carry almost none.

## The paper, and what we can and cannot replicate

**The paper (stated).** Bei Qin, David Strömberg, Yanhui Wu, "Media Bias in China", *American
Economic Review* 108(9), September 2018, 2442-76, DOI 10.1257/aer.20170947 (citation and abstract
read on aeaweb.org). **No NBER working-paper number was found**: four searches, including one
restricted to nber.org, return only NBER *conference* drafts ("Media Bias in Autocracies: Evidence
from China", Chinese Economy meeting, fall 2014, conference.nber.org/confer/2014/CEf14/; a
November 2016 draft also hosted by the Becker Friedman Institute). The design details below are
read from that **November 2016 draft** (full text), not the published version, whose abstract
describes the directory as 1981-2011.

From the 2016 draft (stated): 16 million articles of **117** general-interest newspapers (40 Party
dailies, 12 Party evenings, 65 subsidiaries), 1998-2010, WiseNews. Nine keyword categories as a
share of all articles per paper-year: **Party line** (mentions of 2,111 named leaders, articles
citing Xinhua, coverage of Xinhua's against Epoch Times' annual top-10 stories); **mass line**
(corruption cases, natural disasters, and accidents with more than 30 deaths, the last two keyed
to EM-DAT events); **bottom line** (sport, entertainment, crime). Party dailies mention leaders in
**22%** of articles, subsidiaries in **5%**; "commercial papers do not cover more sensitive
material such as corruption and disasters. In fact, they cover these topics less than Party
Dailies." The first principal component (37% of variance) loads positively on leaders, Xinhua,
corruption and disasters and negatively on Epoch stories, sport, entertainment and crime; it is
their bias index, and it predicts advertising revenue.

| | QSW | this replication |
|---|---|---|
| unit | newspaper-year, 117 papers | site, 15 media sites with at least 100 deduplicated documents |
| period | 1998-2010 | 2025-07-01 to 2026-11-12 (dense from 2026-07-26) |
| text | every article of the paper | what our crawlers reach: sections and feeds, not whole papers |
| Party-owned arm | Party dailies | state media (stdaily, xinhua, people, ce, jjckb) + party theory (qstheory) |
| commercial arm | evenings and subsidiaries | commentary (guancha, ifeng) + business press (qbitai, yicai, 36kr, elsewhere, latepost, eeo, tmtpost) |
| measures | nine keyword shares | the same three families, regexes frozen in the prereg; no Epoch Times measure |
| inference | regressions with prefecture-by-year effects | site means, exact permutation over all 5,005 labellings |

**What we cannot replicate (inferred from the design):**

1. **Market structure and circulation.** QSW's causal result is that a 2003 reform closing
   county papers changed differentiation; their mechanism runs through advertising revenue and
   competition within a prefecture. We hold no circulation, revenue or market data, and our media
   sites are national, not prefectural.
2. **Ownership variation.** Every outlet here is licensed and most are owned by state media
   groups (yicai by a Shanghai broadcaster, 36kr and the tech sites privately; guancha privately;
   ifeng by a Hong Kong group) (**unverified** ownership details, from memory). We compare speaker
   types, not ownership tiers within a market, and there is no Party evening paper in the corpus.
3. **Whole papers.** Our state-media sites are sections, and the section mix drives several
   rates (measured): `people` is entirely `opinion.people.com.cn` (人民时评, 人民锐评, 钟声 columns),
   so its Xinhua-relay rate is 4.7 per 1,000; `xinhua` is about 80% the `fortune` and `tech`
   channels (2,556 and about 2,280 of the 5,782 window rows by URL prefix), not the politics
   desk; `stdaily` is the science ministry's paper and is 71% of state-media documents.
4. **Event coverage keyed to a disaster database.** QSW key accidents to EM-DAT events with more
   than 30 deaths. Only one in-window event in our timing test reaches 28 deaths.
5. **The Epoch Times measure.** No overseas opposition outlet is crawled.

**What the corpus adds (measured below):** documents rather than newspaper pages, so the
government's own documents sit in the same table as a reference; a commentary layer (guancha);
and, in the timing test, the route by which an accident enters the government record, which is
the leader's instruction relayed as Xinhua copy.

## Design (measured where numbers are given)

- **Population.** Documents dated 2025-07-01 to 2026-11-12 (ISO `date_published`), speaker type
  from `web/services/discourse_vocab.speaker`, `strip_chrome` on guancha (1,020 chrome-only pages
  dropped), body at least 200 characters (21,881 dropped), **one copy per (site, normalized
  title)**, the longest body (4,673 duplicates dropped). **122,958 documents**: state media
  27,849; party theory 916; commentary 19,075; business press 6,519; research 351; diplomacy 114;
  central government (non-media) 14,257; sub-national government 53,877.
- **Missing sources.** The party-theory sites being merged tonight (qiushi, hongqi, studytimes,
  gmrb_theory, rmlt) and research `cssn` were **not in documents.db** at 21:20 or 21:33 UTC, so
  party theory here is `qstheory` alone (plus 9 `dangyuan` rows). `jiemian` (566 rows) stores no
  date and cannot enter a dated window.
- **Measures** (regexes frozen in `media_bias_qsw.py:RX`; Python regex, so no FTS length floor):
  Xi or 总书记 in the title; any Politburo Standing Committee name in the title; 习近平 in the body;
  a Xinhua relay (dateline 新华社…X月X日电, 来源：新华社/新华网, 新华社记者, 据新华社); any 新华社 /
  新华网; a named corruption case; an accident word within 60 characters of a death count; a
  disaster word within 60 characters of a death or missing count; market, sport, entertainment
  and crime words in the title.
- **Secondary measures added after a hand-check (prereg note 2).** The registered corruption
  regex was precise on stdaily (8 of 8 sampled hits) and guancha (6 of 8) but not on ifeng (5 of
  8; 被查实, 被查出) and was **0 of 8 on latepost**, where every hit sat in a sidebar of other
  outlets' headlines. 207 of 408 latepost bodies carry that 跟贴 sidebar, which `strip_chrome`
  does not handle (a second chrome site, found here). Lead-only variants (title + first 300
  characters, tightened 被查) are reported beside the registered ones.
- **Statistic.** Unweighted mean of per-site rates per 1,000 over sites with n >= 100, Party-owned
  (6 sites) against commercial (9 sites); exact two-sided permutation p over all C(15,6) = 5,005
  labellings. Pooled rates per speaker type are secondary.

## Results

### 1. The registered contrast (measured)

| measure | Party-owned site mean | commercial site mean | Party / commercial | exact p |
|---|---|---|---|---|
| Xi / 总书记 in title | 39.7 | 0.3 | 133 | < 0.001 |
| PBSC member in title | 65.7 | 1.4 | 48 | 0.003 |
| 习近平 in body | 169.4 | 7.3 | 23 | < 0.001 |
| Xinhua relay | 267.4 | 7.2 | 37 | 0.001 |
| any 新华社 / 新华网 | 301.1 | 32.3 | 9.3 | 0.002 |
| named corruption case | 4.3 | 9.2 | 0.47 | 0.211 |
| corruption case, lead only (secondary) | 1.6 | 3.4 | 0.48 | 0.483 |
| accident with death toll | 1.1 | 2.0 | 0.56 | 0.661 |
| accident toll, lead only (secondary) | 0.9 | 1.1 | 0.82 | 0.952 |
| disaster with toll | 0.7 | 0.6 | 1.20 | 0.952 |
| market / finance title | 36.4 | 158.5 | 0.23 | 0.019 |
| sport title | 6.4 | 7.3 | 0.88 | 0.796 |
| entertainment title | 5.9 | 13.1 | 0.45 | 0.073 |
| crime title | 1.9 | 3.8 | 0.49 | 0.780 |
| soft news (any of the three) | 14.2 | 23.7 | 0.60 | 0.230 |

n = 6 Party-owned sites (28,748 documents) against 9 commercial (25,524). The Party-line ratios
dwarf QSW's 22% against 5% (a ratio of 4.4). *Inferred:* part of that is real and part is the
sample: the commercial arm here is mostly tech and venture outlets that would never lead with a
leader, where QSW's subsidiaries were general-interest metro papers.

### 2. Per site (measured, rate per 1,000)

| type | site | n | Xi in title | 习近平 in body | Xinhua relay | corruption | corruption, lead | accident | disaster | market title | soft |
|---|---|---|---|---|---|---|---|---|---|---|---|
| state media | stdaily | 19,811 | 28.3 | 63.9 | 105.8 | 6.8 | 4.9 | 1.4 | 1.9 | 10.7 | 19.4 |
| state media | xinhua | 4,903 | 2.0 | 41.2 | 435.2 | 2.7 | 0.8 | 0.4 | 0.6 | 24.9 | 16.1 |
| state media | people | 1,474 | 2.7 | 360.2 | 4.7 | 2.0 | 0.7 | 0.7 | 0.7 | 2.0 | 14.2 |
| state media | ce | 1,316 | 31.9 | 141.3 | 245.4 | 6.8 | 2.3 | 3.0 | 0.0 | 85.1 | 16.0 |
| state media | jjckb | 337 | 8.9 | 20.8 | 80.1 | 3.0 | 0.0 | 0.0 | 0.0 | 80.1 | 5.9 |
| party theory | qstheory | 907 | 164.3 | 389.2 | 733.2 | 4.4 | 1.1 | 1.1 | 1.1 | 15.4 | 13.2 |
| commentary | guancha | 13,004 | 2.7 | 23.7 | 14.1 | 19.9 | 11.7 | 9.6 | 5.4 | 40.0 | 53.9 |
| commentary | ifeng | 6,071 | 0.0 | 15.3 | 8.7 | 17.5 | 13.8 | 2.3 | 0.0 | 59.0 | 21.2 |
| business | qbitai | 3,817 | 0.0 | 1.6 | 0.5 | 2.4 | 0.3 | 0.0 | 0.0 | 64.2 | 19.4 |
| business | yicai | 899 | 0.0 | 15.6 | 23.4 | 7.8 | 4.4 | 3.3 | 0.0 | 159.1 | 5.6 |
| business | 36kr | 473 | 0.0 | 4.2 | 2.1 | 0.0 | 0.0 | 0.0 | 0.0 | 321.4 | 27.5 |
| business | elsewhere | 429 | 0.0 | 0.0 | 0.0 | 2.3 | 0.0 | 0.0 | 0.0 | 202.8 | 16.3 |
| business | latepost | 408 | 0.0 | 0.0 | 4.9 | 22.1 | 0.0 | 2.5 | 0.0 | 90.7 | 12.3 |
| business | eeo | 239 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 326.4 | 8.4 |
| business | tmtpost | 184 | 0.0 | 5.4 | 10.9 | 10.9 | 0.0 | 0.0 | 0.0 | 163.0 | 48.9 |

Three readings (inferred). First, **product differentiation exists inside the Party-owned arm**,
as QSW found inside markets: the economic papers ce and jjckb title market news at 80-85 per
1,000, people's opinion columns at 2. Second, **latepost's corruption rate of 22.1 is entirely a
sidebar artifact**: lead-only it is 0.0. Third, **the accountability content of the commercial arm
is two sites**: guancha and ifeng carry 236 of the commercial arm's 241 lead-only corruption hits (98%);
ifeng's are mostly local 纪委 notices from its Anhui channel (sampled: 黄山区, 舒城县, 合肥 cases).

### 3. Pooled by speaker type, with government as reference (measured, per 1,000)

| measure | state media (27,849) | party theory (916) | commentary (19,075) | business (6,519) | central gov (14,257) | sub-national gov (53,877) |
|---|---|---|---|---|---|---|
| Xi / 总书记 in title | 22.3 | 165.9 | 1.8 | 0.0 | 53.7 | 32.4 |
| 习近平 in body | 78.7 | 393.0 | 21.0 | 3.7 | 244.4 | 192.5 |
| Xinhua relay | 164.7 | 731.4 | 12.4 | 4.3 | 70.6 | 39.1 |
| named corruption case | 5.8 | 4.4 | 19.1 | 4.4 | 7.5 | 3.9 |
| corruption, lead only | 3.8 | 1.1 | 12.4 | 0.8 | 2.8 | 0.5 |
| accident with death toll | 1.3 | 1.1 | 7.3 | 0.6 | 0.4 | 0.3 |
| disaster with toll | 1.5 | 1.1 | 3.7 | 0.0 | 0.4 | 0.2 |
| market / finance title | 17.1 | 15.3 | 46.0 | 119.7 | 15.9 | 9.6 |
| soft news | 18.2 | 13.1 | 43.5 | 18.6 | 10.9 | 20.0 |

Diplomacy (mfa, 114) puts Xi in 140 titles per 1,000 and 习近平 in 728 bodies per 1,000; research
(351) 25.6 and 222. *Inferred:* the government's own documents sit **between** state media and
party theory on the Party line: a government document carries 习近平 in its body two to three
times as often as a state-media document does. The mouthpiece is the government, more than the
newspaper. Sub-national government's soft-news rate (20.0) is the highest of any government type
because of sport titles (15.9 per 1,000), plausibly the 2025 National Games held in Guangdong
(**unverified** as the cause).

### 4. Does the structure lie on one dimension? (measured, exploratory, not registered)

Spearman correlation across the 15 media sites between the rate of 习近平 in the body and each
other measure: Xi in title +0.88, any 新华社 +0.56, **corruption (lead) +0.59, accident (lead)
+0.68, disaster (lead) +0.69**, crime title +0.62, sport title +0.36, entertainment title
**-0.51**, market title **-0.78**. QSW's first component loaded corruption and disasters with the
Party line and soft news against it; here corruption and disasters again rank with the Party line
and market and entertainment against it, but crime and sport switch sides. *Inferred:* the
dimension that organises this corpus is general news against specialist commercial content, and
the accountability measures belong to general news. That is why the group contrast in section 1
(which puts guancha and ifeng in the commercial arm) and the rank structure point in opposite
directions without contradicting each other.

### 5. Robustness (measured; site-mean ratio Party-owned / commercial)

| variant | Xi in title | 习近平 body | Xinhua relay | corruption | accident | disaster | market | soft |
|---|---|---|---|---|---|---|---|---|
| registered | 133 | 23.2 | 37.2 | 0.47 | 0.56 | 1.20 | 0.23 | 0.60 |
| drop stdaily | 140 | 26.1 | 41.7 | 0.41 | 0.53 | 0.80 | 0.26 | 0.55 |
| drop qbitai | 118 | 21.1 | 33.4 | 0.43 | 0.50 | 1.07 | 0.21 | 0.58 |
| drop xinhua | 158 | 26.7 | 32.6 | 0.50 | 0.63 | 1.24 | 0.24 | 0.58 |
| drop guancha | (commercial 0) | 32.2 | 42.4 | 0.55 | 1.09 | (commercial 0) | 0.21 | 0.71 |

The dense window (2026-07-26 on, every site present) and the news genre alone reproduce the
pooled pattern (commentary 17.8 and 19.6 corruption per 1,000 against state media 6.4 and 6.6).
Excluding the two Xinhua-owned sites, the Xinhua-relay rate is 107 per 1,000 in state media, 731 in
party theory, 12 in commentary, 4 in business press. Among accountability documents on non-Xinhua
sites, the Xinhua-relay share is 13.6% of corruption documents in state media (n = 147) and 2.2%
in commentary (n = 365); 42.4% of accident documents in state media (n = 33) and 5.8% in
commentary (n = 139).

### 6. Timing test (measured)

Events chosen from central government records before any coverage was read: every in-window
accident or disaster whose investigation the centre escalated (国务院安委会 or 国家防灾减灾救灾委员会
挂牌督办, or a 国务院 提级调查), and the first three ranked officials announced under 审查调查 from
2026-07-26. Coverage = a deduplicated document naming the event in its title or first 400
characters within [day - 3, day + 30].

| event | state media | party theory | commentary | business | central gov | sub-national gov |
|---|---|---|---|---|---|---|
| A1 包钢 explosion, 2026-01-18, 5 dead and 5 missing at notice (10 in the final report) | - | - | 2 docs, lag 3, relay 0% | - | 1, lag 1 | - |
| A2 宜城 fireworks, 2026-02-18, 12 dead | - | - | - | - | (lost, see below) | - |
| A3 晋江 shoe-factory fire, 2026-07-09, 28 dead | 6 docs / 2 sites, lag 0, relay 50% | - | 5, lag 0, relay 20% | - | 1, lag 1, relay 100% | 20 docs / 11 sites, lag 1, relay 15% |
| A4 渭源 flash flood, 2026-07-26, 25 dead | 4 / 2, lag 0, relay 25% | - | 2, lag 0, relay 0% | - | 1, lag 7 | - |
| A5 青岛北海造船 fire, 2026-09-10, 25 dead | 4 / 1, lag 0, relay 75% | 2, lag 0, relay 50% | 5 / 2, lag 0, relay 20% | - | 6 / 5, lag 0, relay 67% | 28 / 17, lag 1, relay 32% |
| C1 叶建春 (江西省长), 2026-08-27 | 1, lag 0 | - | 1, lag 0 | - | - | - |
| C2 刘建洋 (江苏组织部长), 2026-08-31 | 1, lag 0 | - | - | - | - | - |
| C3 鲁昕 (教育部原副部长), 2026-09-28 | 1, lag 0 | - | - | - | - | - |

What it shows (measured, then inferred):

- **No business-press site covered any of the eight events**, and neither did `xinhua` or
  `ifeng` (one ifeng page names the 北海 fire in passing, a 重庆 economy meeting). Where state media
  and commentary both covered an event, both did so on day 0; commentary was never later.
- **State-media coverage of accidents is half Xinhua copy** (7 of 14 documents), commentary's one
  in seven (2 of 14). Corruption coverage is never a Xinhua relay (0 of 4): the announcements are
  中央纪委国家监委 releases carried directly.
- **The government side enters through the leader.** Of the 48 sub-national and 9 central
  documents covering the accidents, 17 and 4 carry 习近平, 总书记 or 重要指示 in the title, mostly
  the verbatim Xinhua item "习近平对…火灾事故作出重要指示", reposted by 8 sub-national sites on day 1
  for A5. Commentary framed 1 of its 14 accident documents that way. *Inferred:* for the
  government record an accident is an occasion for the instruction; for commentary it is an
  event with a death toll. That is QSW's Party-line dimension observed on a single event.
- **The early events are a coverage test, not a media test.** stdaily enters the corpus on
  2026-04-04 and ifeng on 2026-07-26, and guancha holds only 288 rows between 2026-01-15 and
  2026-03-20, so A1 and A2 cannot discriminate. A2 is absent even from the government side
  because its 应急管理部 notice shares a **truncated title** (`重大生产安全事故查处挂牌督办通知书（安委督〔202...`)
  with A1's, and one-copy-per-title kept A1's longer body: a dedup collision on a crawler that
  cuts titles at about 25 characters.
- **The three corruption cases** were selected by a title rule, and all three qualifying titles
  were on stdaily; only C1 appears anywhere else (guancha, same day). Three events cannot carry a
  timing claim.

## Verdict against the pre-registration

| registered prediction | result |
|---|---|
| QSW: Xi in title, Party > commercial; mine: ratio at least 3, Party 40-80, commercial under 15 | **held** (39.7 against 0.3, p < 0.001); Party just below my range |
| QSW: 习近平 in body Party > commercial; mine: ratio 2-5 | sign **held**; magnitude far above (23x) |
| QSW: Xinhua relay Party > commercial; mine: ratio at least 2, guancha comparable to people / ce | ratio **held** (37x); guancha (14.1) above people (4.7, opinion columns) but far below ce (245): **wrong** on the substantive comparison |
| QSW: any Xinhua Party > commercial | **held** (9.3x) |
| QSW: corruption Party > commercial | **did not hold**: ratio 0.47 (p 0.21), 0.48 lead-only |
| mine: corruption holds at the site mean; guancha the top media site; commentary > state media pooled | site-mean **wrong**; top site was latepost (artifact) registered and ifeng lead-only, so **wrong**; commentary > state media pooled **held** (19.1 against 5.8) |
| QSW: accidents Party > commercial | **did not hold** (0.56, p 0.66) |
| mine: accident ratio 0.7-1.5; guancha and ifeng at or above xinhua / people | ratio **missed** registered (0.56), within range lead-only (0.82); site ordering **held** |
| QSW: disasters Party > commercial; mine: ratio 1-2 | sign held at 1.20 but **null** (p 0.95) |
| mine: market commercial > Party, at least 1.5x | **held** (4.4x, p 0.019) |
| QSW: soft commercial > Party; mine: at least 1.5x, carried by ifeng | ratio **held** (1.7x) but not significant (p 0.23); carried by **guancha**, not ifeng: **wrong** on the carrier |
| mine: central gov highest non-media type on Xi in title | held against sub-national and research, **not** against diplomacy (140) |
| mine: sub-national lowest on soft news | **wrong** (20.0, above state media and central) |
| mine: sub-national lowest on accidents except business press | **held**, and lower than business press too |
| timing: state media and commentary cover every accident, commentary no later | **held** for A3-A5; A1-A2 untestable (coverage) |
| timing: business press covers at most A1, A5 | held (covered none) |
| timing: Xinhua share of accident coverage at least 50% state media, 20-50% commentary | **held** for state media (50%); **missed** for commentary (14%) |
| timing: corruption covered same day by commentary and state media; relay under 30% | relay **held** (0%); same-day pair only for C1; C2 and C3 stdaily only |

## Caveats

- **Sections, not papers.** Every Party-owned rate is a rate for the sections we crawl, and three
  of the five state-media sites are dominated by one section (people opinion, xinhua fortune/tech,
  stdaily science). A different crawl of the same outlets would move every number.
- **The commercial arm is mostly specialist.** Seven of nine commercial sites are tech or venture
  outlets. QSW's commercial papers were general-interest metro dailies; our nearest analogues are
  guancha and ifeng, and they are where the accountability content is.
- **Rates per document, not per article page.** One copy per title per site means a story run in
  three updates counts up to three times if its title changed.
- **Measure validity.** Corruption by registered regex: 19 of 32 sampled hits on four sites were
  cases; the lead-only variant removes the sidebar artifact but still counts 被查处 in commentary
  about past cases. Accidents include foreign events (a Florida plane crash, an Indian fire) and
  later investigation reports, which QSW's EM-DAT keying excluded.
- **Party theory is one site.** The five theory journals being merged tonight were absent;
  re-running `--measure` after the merge is the cheap follow-up.
- **No inference to bias in QSW's sense.** We have no advertising or circulation data, so we
  cannot say any content mix serves readers or the Party; we can only say the mixes differ.

## Appendix: reproduce

```bash
# droplet, read-only; scripts staged in /tmp/qsw (discourse_vocab.py copied from local main,
# because the droplet checkout predates it)
cd /tmp/qsw
PY=/root/china-governance/.venv/bin/python3
$PY -u media_bias_qsw.py --db /root/china-governance/documents.db --vocab-dir /tmp/qsw --coverage
$PY -u media_bias_qsw.py --db /root/china-governance/documents.db --vocab-dir /tmp/qsw \
    --measure --out /tmp/qsw/flags.tsv                 # 122,958 rows, about 10 s
$PY -u media_bias_qsw.py --db /root/china-governance/documents.db --vocab-dir /tmp/qsw \
    --events --event-list /tmp/qsw/events_list.tsv --out /tmp/qsw/events.tsv
# anywhere, from the flags files
python3 scripts/rnd/analysis/media_bias_qsw.py --analyze --flags flags.tsv          # sections 1-3, 5
python3 scripts/rnd/analysis/media_bias_qsw.py --analyze-events --flags events.tsv  # section 6
```

The event list (`events_list.tsv`, tab-separated name, day, regex) is the table in the prereg's
timing section plus its first appended note. Section 4's correlations were computed from
`flags.tsv` by a one-off rank correlation over the 15 sites listed in section 2.
