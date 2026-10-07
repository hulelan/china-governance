# The Document-Record Backbone of Wang & Yang's "Policy Experimentation in China", Replicated on Our Corpus

*A read-only replication of the measurement layer of Wang and Yang, "Policy
Experimentation in China: the Political Economy of Policy Learning" (NBER w29402,
2021; JPE 2025). Run against the live `documents.db` (droplet, 2026-10-01),
`file:...?mode=ro`. Universe: 260,334 dated government documents (central,
provincial, municipal, district) and the cleaned `diffusion_events` table (24,599
central-anchored cascade edges). Every series is a share or a rate; no raw-count
trend carries an argument. SQL is in the appendix. This note supersedes and extends
the quick "Test B" in `recentralization-experimentation.md` §3, which it cites.*

*(Build note 2026-10-01: the 24,599-row figure is the post npc/explainer-fix build, before
the resolver fix. The table is rebuilt nightly and held 32,825 rows (26,565 central + 6,260
provincial) on 2026-10-01; a further resolver regression fix in progress will change it
again. Raw counts in §2 (61 tightly-linked pilots, 333 edges, 833 citing implementers) are
from the 24,599 build; shares and orderings held on spot checks. See `consistency-review.md`
H2. Universe note: npc local regulations are counted as central here, as in
`recentralization-experimentation.md`; other memos re-level or exclude them, so level shares
are within-memo only, review M7.)*

---

## 0. Scope boundary, stated up front

Wang and Yang do three things: (i) build a **document record** of policy experiments
from government text, and (ii, iii) run two causal tests on top of it using **external
data we do not hold**. This note replicates (i) in full and automatically. It does
**not** attempt (ii) or (iii), and does not fake them.

| Their finding | Needs | Can we speak to it? |
|---|---|---|
| **(1)** >80% of experiments run in positively-selected (richer) localities; ~half explained by local officials' promotion incentives | locality pre-experiment GDP per capita; prefectural-leader promotion-incentive index; minister-province career ties | **No.** We have no locality GDP series and no local-chief-to-pilot-site career linkage. `officials.db` is central CPC elites only. We give a **descriptive, coverage-confounded** echo in §4, explicitly not a test of the mechanism. |
| **(2)** triple-diff: pilot localities spend ~5% more in the policy domain during the experiment; effort absent at national rollout | county-domain-year fiscal expenditure panel | **No.** We hold no fiscal-spending data. Not attempted. |
| **(3)** the center under-corrects for selection and effort, biasing policy learning | land-revenue windfall IV; politician-turnover shocks; rollout outcomes | **No.** Requires (1) and (2) plus exogenous shocks. Not attempted. |
| **Document record** (their §3): 633 experiments / 98 ministries / 19,812 docs; central→local linkage; rollout tracing | government documents + a citation graph | **Yes.** This is exactly our `diffusion_events` machinery, automated. §1-§3 below. |

What we **add** to their 2021 hand-coded record (§5): genre, policy-domain, and
auto-matched cascade axes at a scale and recency their set lacked. What they can
do that we cannot: everything causal. The honest division of labor is that we
measure the plumbing; they measure the water pressure.

**Window truncation.** Their record runs 1980-2020. Our corpus starts ~2000 (thin
before 2005). We therefore miss the entire 1980s-1990s initiation era they document
(their Figure 2 shows <10 experiments/year then). Our series is 2000-2026 and its
early years are sparse. Treat anything before 2008 as provisional and 2026 as a
partial year.

---

## 1. Step 1: central experiment guidelines (their 633 analog)

**Definition.** A central experiment guideline is a document on a `central`
`admin_level` site whose **title** carries an experiment-designation cue
(`试点` | `试验区` | `先行先试` | `示范区`), is **not** a news/explainer genre
(`图解`/`解读`/`答记者问`/`新闻发布`/`访谈`/…), and **is** in a designating
instrument genre (`方案`/`通知`/`意见`/`决定`/`批复`/`公告`/`办法`/`规定`/`印发`/…).
Dates 2000-2026.

**Count.**

- **1,818** central documents carry an experiment title cue.
- **1,592** of those are in a designating genre (our primary guideline set).
- **1,296** distinct **experiment themes** after collapsing title families
  (strip 文号, waves, years, issuer and genre boilerplate; group identical cores).

**Evidence, our count vs their 633.** Our designating-guideline count (1,592) is
~2.5x their experiment count (633), and our distinct-theme count (1,296) is ~2x.
The numbers are not comparable one-to-one and ours is **not** proof of more
experimentation. Three reasons ours runs higher: (a) **unit**: our guideline is a
document; their experiment groups many consecutive/related documents by hand into
one theme (they report 1,374 roll-out rounds across 633 experiments, i.e. ~2.2
documents per experiment, so a document-level count should run ~2x higher, which
it does). (b) **detection**: ours is title-only and will include `示范区`/`试点`
designations that are standing zone names rather than policy trials, which they
exclude by reading the text. (c) **window**: ours is 2000-2026 and catches the
2015-2024 surge they only partly see. Against those, our count is **suppressed** by
central coverage: we crawl ~60 central bodies, not the full ministerial universe
(see §1b). The right reading is that our 1,592/1,296 is the same order of magnitude
as their 633 once the document-vs-theme unit is accounted for, built by regex in
seconds rather than by hand over months.

**Evidence, per-year share (normalized by central document volume).** The guideline
*share* of all central documents rises from ~1.5-2.0% (2005-2012) to a **2016 peak
of 3.9%**, then settles at 2.3-2.8% (2018-2023) and declines to 1.5-1.7% (2024-2025).

| year | guidelines | central docs | share |
|---|---|---|---|
| 2008 | 25 | 1,317 | 0.019 |
| 2012 | 33 | 1,673 | 0.020 |
| 2013 | 37 | 1,172 | 0.032 |
| 2015 | 59 | 1,941 | 0.030 |
| **2016** | 105 | 2,704 | **0.039** |
| 2018 | 143 | 5,382 | 0.027 |
| 2020 | 159 | 5,634 | 0.028 |
| 2022 | 139 | 5,056 | 0.028 |
| 2024 | 125 | 7,208 | 0.017 |
| 2025 | 103 | 6,794 | 0.015 |

(2026 is partial and its central denominator is inflated by a crawl batch; the cell
is not interpretable.) This is the same hump Wang and Yang report (their peak 2013,
decline after), shifted ~3 years later in our title-share series and normalized so
the ~70x corpus growth cannot drive it. The post-2016 *share* decline holds even as
the raw count stays near 125-160/year, because the central corpus grew faster.

### 1b. Initiating bodies (their 98 ministries analog)

- **28 distinct central crawled sites** issue designating pilot guidelines, led by
  `gov` (State Council, 909), `chinatax` (163), `mofcom` (115), `mof` (81), `samr`
  (62), `npc` (52), `ndrc` (48), `most` (34), `miit` (26), `mee` (24).
- **319 distinct 文号 issuer prefixes** among the 1,174 guidelines that carry a
  document number, a far richer issuer count than 28. This is because one portal (`gov`)
  republishes documents from many ministries. Top prefixes: `国函` (233), `国发`
  (89), `国办发` (62), `财税` (38), `财库`/`财建` (15 each), `商资发` (13),
  `发改环资` (10), `银保监办发` (10).

**Evidence.** Our 28 crawled central bodies fall well short of their 98, a direct
coverage limit. Many ministries publish on sites we do not crawl, and the State
Council portal absorbs the rest under one `site_key`. The 文号-prefix count (319)
over-shoots their 98 in the other direction, because prefixes encode *bureau-within-
ministry* (发改环资, 发改体改, 发改振兴 are all NDRC) rather than ministry. The
truth is bracketed: **28 (site) < 98 (their ministries) < 319 (文号 bureau)**. We
can name the leading initiators correctly (State Council, tax, commerce, finance,
market regulation, NDRC) but cannot reproduce their clean 98-ministry census without
the full central crawl.

### 1c. Distinct experiment themes

Collapsing the 1,592 guidelines to normalized title cores yields **1,296 themes**.
The largest families are exactly the recognizable multi-wave programmes: 自由贸易
经验复制推广 (9 docs), 粤港澳大湾区 律师执业资质 (5), 要素市场化配置 (4), 营商环境
创新 (4), 浦东新区综合改革 (4), 长三角一体化 国土空间 (4). Most themes (≈1,000)
are singletons, consistent with title-only detection splitting what a human coder
would merge. This is a floor on merging, not a census of experiments.

---

## 2. Step 2: linkage to local implementation (their core hand-linkage)

**Method.** For each central guideline (anchor), its implementing sub-national
documents are the `diffusion_events` rows with `anchor_id = guideline` and
`match_type IN (citation, title_reissue)`, the tight-linkage channel the prompt
specifies. `diffusion_events` was central-anchored by construction (all 2,943
anchors behind the 24,599 events were central docs; the earlier wording "24,599
anchors" conflated events with anchors, corrected 2026-10-01), so it *is* the
automated central→local linkage. Since commit `c6dbe04` the table also carries
provincial anchors under an `anchor_level` column; this memo uses the central
rows only.

**Evidence, tight linkage (`diffusion_events`, citation + reissue).**

- **61** of our designating guidelines have at least one linked sub-national
  implementer in the cleaned table; **333** implementation edges.
- Per anchor: **median 2** distinct implementing localities, mean 2.8, max 22.
- Implementer level mix: provincial 151, municipal 140, district 42 edges.
- Implementation lag (anchor→local, ≥0): **median 416 days**, p25 179, p75 677.

**Evidence, broader cross-check (raw `citations` table, any citation type).** The
cleaned `diffusion_events` is a conservative subset. Querying the raw graph for
sub-national documents citing a designating pilot anchor directly:

- **265** distinct pilot anchors are cited by at least one sub-national document
  (vs 61 in the cleaned table).
- **833** distinct sub-national citing documents; **1,528** edges.
- Edge level mix: provincial 1,004, municipal 323, department 132, district 69.

So the linkage exists at meaningful scale for roughly **17%** of designating
guidelines (265/1,592) and is dominated by provincial implementers citing central
designations. The gap between 61 (cleaned) and 265 (raw) is the price of the
cleaning: `diffusion_events` drops topic-only and low-confidence matches, so it
under-counts the true linkage. Both numbers are floors because citation resolution
sits at ~52% overall (see §6). Wang and Yang hand-linked every local action plan to
its central guideline; we recover the linkage automatically for the subset that
leaves a resolvable citation, which is a minority but a structurally clean one. The
**416-day median implementation lag** is the automated analog of their roll-out
schedule, and sits comfortably inside their reported ~2.25-year average experiment
duration.

---

## 3. Step 3: rollout tracing, did the experiment scale?

Two proxies, because "national rollout" is a policy event that the corpus sees only
partially.

### 3a. Breadth of local uptake (well-grounded)

Of the 61 tightly-linked anchors, **31 (51%)** have implementers spanning **two or
more calendar years**, the citation-graph analog of Wang and Yang's multi-wave
roll-out (they find ~2.9 rounds per experiment). The median anchor reaches 2
localities and the broadest reaches 22. This is the one rollout signal the corpus
measures cleanly: a central designation picked up by widening sets of localities
over successive years.

### 3b. Pilot-to-national generalization (brittle; reported as a floor)

**Method.** For each pilot theme, search later central documents (any central site,
date > first pilot) whose title contains the same theme core but carries **no** pilot
cue. Three nested genres:

| generalization proxy | themes reaching | share | median lag | (years) |
|---|---|---|---|---|
| any later central non-pilot same-theme doc | 16 / 1,296 | **0.012** | 738 d | 2.0 |
| a settled national instrument (`办法`/`条例`/`全面推开`/`全面实施`…) | 5 / 1,296 | **0.004** | 1,070 d | 2.9 |
| explicit generalization vocabulary (`全面推开`/`复制推广`…) | 1 / 1,296 | 0.001 | 1,058 d | 2.9 |

**Evidence.** The share of pilot themes we can see reach a national instrument is
**0.4%-1.2%**, a floor, not an estimate, far below Wang and Yang's 53.9%
success rate. The clean cases are real and recognizable: 县级公立医院综合改革试点
→ 《全面推开县级公立医院综合改革的实施意见》 (lag 1,058 days); 无废城市建设试点 →
无废城市建设条例 (1,892 days, at the Shanghai level); 电信普遍服务补助资金管理
试点办法 → the de-piloted 《电信普遍服务补助资金管理办法》 (1,173 days). The
**median pilot-to-national lag is 1,070 days (~2.9 years)** on the settled-instrument
proxy, 738 days (~2.0 years) on the loose one. Both are inside their 2.25-year average
duration, which is reassuring on the lag even as the *level* is unrecoverable. *(2026-10-06,
`successor-detector.md`: a scored detector on `doc_identity` finds successors for 75 of 1,271
pilot instruments, 5.9% / 6.9% ex-mid-flight, median lag 564 d, precision 76-87%; the 0.4-1.2%
here was a detection floor of the title-family method by about an order of magnitude, and the
hand sample says most of the remaining gap is renaming, not failure to scale.)*

**Why the level is a floor, not a finding.** Three reasons the corpus cannot see
most generalizations: (a) a national instrument routinely **renames** the policy and
drops the pilot theme string, so a title-family match misses it; (b) generalization
is often a policy *event* carried by a document that **does not cite or re-title** the
trial; (c) the national instrument may sit on a central site we do not crawl, or its
citation may be unresolved. The corpus sees **designation flowing down** far better
than **generalization flowing up or out**. This is the identical asymmetry found in
`recentralization-experimentation.md` §3.4-3.5. We report 0.4-1.2% as the share of
experiments whose national rollout is *visible as a titled, theme-preserving central
instrument*, and state plainly that the true rollout rate is higher and unmeasurable
here.

---

## 4. Step 4: pilot-site composition (descriptive only, coverage-confounded)

**Method.** Rank localities by the number of distinct pilot guidelines they
implement (raw `citations`, sub-national citers of designating anchors).

| site | level | distinct pilots implemented |
|---|---|---|
| gd (Guangdong) | provincial | 83 |
| bj (Beijing) | provincial | 75 |
| sh (Shanghai) | provincial | 43 |
| js (Jiangsu) | provincial | 34 |
| gz (Guangzhou) | municipal | 29 |
| hlj (Heilongjiang) | provincial | 26 |
| sz (Shenzhen) | municipal | 16 |
| zhuhai | municipal | 14 |
| jiangmen / huizhou / cq | municipal | 12 |

**Evidence, and the caveat that governs it.** Pilot implementation concentrates in
the wealthy eastern coast: Guangdong, Beijing, Shanghai, Jiangsu, Guangzhou,
and Shenzhen lead. On its face this *echoes* Wang and Yang's positive-selection finding
(their experiments cluster in developed, coastal, capital localities). **It is not
a test of it.** Our ranking is almost perfectly confounded by **crawl coverage**:
Guangdong, Beijing, Shanghai, Jiangsu, and the Guangdong cities are precisely our
most deeply crawled sub-national sites (the `gkmlpt` Guangdong fleet plus Tier-1
provinces), so they *mechanically* have more documents, more resolvable citations,
and therefore more detected implementations. A locality we crawl shallowly cannot
rank high no matter how many pilots it ran. We cannot separate "hosts more pilots"
from "we see more of its documents" without the locality GDP series and a
coverage-balanced crawl, neither of which we have. This section is descriptive
color, not evidence for finding (1).

---

## 5. Step 5: what the corpus adds to their 2021 record

Our automated record carries axes their hand-coded set did not, at full corpus
scale and to 2026.

**Genre axis** (`algo_doc_type` of the 1,592 designating guidelines): notice 642,
policy_issuance 252, reply (批复) 249, announcement 87, opinion 67, decision 64,
action_plan 60, work_plan 44, regulation 15, standard 14. The large `reply` (批复)
share is distinctive: a big fraction of central pilot designations are State Council
*replies* approving a locality's request to run a trial, which is itself evidence on
the assigned-vs-voluntary split Wang and Yang hand-code (批复 implies a locality
asked). We can measure that split by genre regex; they read each document.

**Policy-domain axis** (`diffusion_events.topic` on pilot cascades): Government 47,
Finance 31, Health 31, Welfare 17, Agriculture 9, Trade 7, Culture 5, Commerce 3.
This is the automated analog of their Table 1 Panel B (experiments by policy domain),
recomputable nightly as the corpus grows.

**Cascade axis.** The `diffusion_events` auto-matcher reconstructs the central→local
cascade for any anchor on demand, across the whole corpus, with lags. It is the live
version of their hand-linkage, extended past their 2020 cutoff into the 2021-2026
programmes (碳达峰试点, 要素市场化配置, 无废城市, 全域土地综合整治) they could not see.

**What they have that we never will.** The causal core: selection on locality GDP,
the promotion-incentive index, the triple-diff on fiscal effort, the land-revenue and
turnover IVs, the 74-85% deflating coefficient on scaled-up policy effects. Those
require external panels on local economies and local careers. Our contribution is the
measurement backbone at scale and in near-real-time; theirs is the identification.

---

## 6. Threats to validity

1. **2000-start truncation.** We miss 1980-1999 entirely and are thin to 2007. Their
   initiation hump begins in the 1990s; ours begins mid-stream.
2. **Title-only detection.** Pilots that are experimental in substance but not in
   title are missed; `示范区` also catches standing zone names. Our 1,592 is both
   over-inclusive (zone names) and under-inclusive (untitled trials).
3. **~52% citation resolution, not flat.** Every linkage and rollout rate is a floor.
   Sub-national resolution rises from 0.35 (2005) to 0.55 (2025), which works against
   any decline we report, not for it.
4. **Central coverage.** ~60 central bodies crawled, not the full ministerial
   universe; the 28-site issuer count understates breadth, and some national rollout
   instruments sit on uncrawled sites (§3b floor).
5. **Coverage-confounded site composition.** §4 ranks our best-crawled localities,
   not necessarily the most-piloted ones. Not causal.
6. **Rollout detection is brittle.** Title-family matching misses renamed or
   uncited generalizations; the 0.4-1.2% rollout share is a visibility floor, far
   below the true rate.
7. **Unit mismatch vs their 633.** Our guideline is a document; their experiment is
   a hand-merged theme. We report both the document count (1,592) and a normalized
   theme count (1,296); neither is their exact unit.
8. **Publication date ≠ adoption date.** Lags are proxies.
9. **Not causal, anywhere.** Nothing here speaks to findings (1), (2), or (3). This
   note is the measurement backbone only.
10. **Scope boundary.** Mechanism-level claims about a published document record,
    with the coverage bias (4, 5), the resolution floor (3) and the publication
    caveat (8) above. No regime-type labels. *(Added 2026-10-01 per
    `consistency-review.md` §2.)*

---

## 7. Bottom line

The documentary backbone of Wang and Yang replicates cleanly and automatically. We
recover **1,592 central experiment-guideline documents (1,296 distinct themes),
2000-2026**, against their 633 hand-merged experiments 1980-2020, the same order of
magnitude once the document-vs-theme unit and the later window are accounted for. The
guideline *share* of central output peaks in 2016 (3.9%) and declines after, echoing
their hump. The central→local linkage their hand-coders built by hand is reproduced
by `diffusion_events`: 265 guidelines are cited by 833 sub-national implementers, a
**median 416-day** implementation lag, provincial implementers dominating. Rollout is
the hard part: **51%** of tightly-linked pilots show multi-year widening local uptake,
but only **0.4-1.2%** reach a *visible, theme-preserving national instrument* (a
floor, far under their 53.9%), at a **median ~1,070-day (≈2.9-year) pilot-to-national
lag** that sits inside their 2.25-year average duration. The corpus sees designation
flowing down far better than generalization flowing up *(2026-10-06: 5.9% / 6.9% with the
successor detector, and positive site selection replicated descriptively at province grain in
`site-selection-gdp.md`; the three causal findings remain out of reach)*. We can speak to the
**document record and the central→local cascade**; we **cannot** speak to their three
causal findings: positive site selection (needs locality GDP), strategic fiscal
effort (needs fiscal panels), or under-correction in policy learning (needs both plus
shocks), because the required external data is not in this project.

---

## Appendix: SQL and method

All queries ran against `file:/root/china-governance/documents.db?mode=ro` via two
scratchpad Python scripts (`wy_analysis.py`, `wy_rollout.py`; not committed). Regexes:
`is_pilot = 试点|试验区|先行先试|示范区`; `news = 图解|解读|答记者问|新闻发布|访谈|…`;
`desig = 方案|通知|意见|决定|批复|公告|办法|规定|印发|的函|工作`;
`natgenre = 办法|条例|规定|全面推开|全面实施|全面推广|复制推广`. `norm_core()` strips
`《》`, 文号 (`〔…〕…号`), `第N批`, year ranges, issuer/genre boilerplate, and pilot
cues, leaving the policy theme (kept if ≥4 chars). `fam(site_key)` is the prefix
before `_`.

```sql
-- Universe (260,334 docs): central/provincial/municipal/department/district, 2000-2026
SELECT d.id,d.title,d.date_published,d.site_key,d.document_number,d.algo_doc_type,s.admin_level
FROM documents d JOIN sites s ON s.site_key=d.site_key
WHERE length(d.date_published)>=10 AND substr(d.date_published,1,4) BETWEEN '2000' AND '2026'
  AND s.admin_level IN ('central','provincial','municipal','department','district');

-- STEP 1: central experiment guidelines (is_pilot & desig & NOT news), by year / site / 文号
--   counts and theme-collapse done in Python (norm_core); share = guidelines / central docs per year.

-- STEP 2 tight linkage: implementers of a designating pilot anchor (diffusion_events)
SELECT de.anchor_id, de.source_id, de.match_type, de.lag_days, de.source_level, de.topic
FROM diffusion_events de
WHERE de.match_type IN ('citation','title_reissue') AND de.anchor_id IN (<designating pilot ids>);

-- STEP 2 cross-check: raw-citations linkage to designating pilot anchors
WITH exp(id) AS (VALUES <designating pilot ids>)
SELECT count(*) edges, count(DISTINCT c.target_id) anchors_cited, count(DISTINCT c.source_id) citers
FROM citations c JOIN documents sd ON sd.id=c.source_id JOIN sites ss ON ss.site_key=sd.site_key
WHERE c.target_id IN (SELECT id FROM exp)
  AND ss.admin_level IN ('provincial','municipal','department','district');

-- STEP 3b rollout: for each pilot theme, earliest later central non-pilot doc containing the
--   theme core; nested by genre (any / natgenre / genvocab). Lag = that date - first pilot date.
--   (theme matching + lag in Python over the central doc list.)

-- STEP 3a / multi-wave: anchors whose implementer source years span >=2 calendar years.

-- STEP 4 site composition (coverage-confounded): distinct pilot anchors implemented per site
WITH exp(id) AS (VALUES <designating pilot ids>)
SELECT sd.site_key, ss.admin_level, count(DISTINCT c.target_id) n_pilots
FROM citations c JOIN documents sd ON sd.id=c.source_id JOIN sites ss ON ss.site_key=sd.site_key
WHERE c.target_id IN (SELECT id FROM exp)
  AND ss.admin_level IN ('provincial','municipal','department','district')
GROUP BY sd.site_key ORDER BY n_pilots DESC;

-- STEP 5 axes: algo_doc_type of designating pilots; diffusion_events.topic of pilot cascade edges.
```
