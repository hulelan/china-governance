# Recentralization and Policy Experimentation, Tested on the Citation Graph

*Two graph-native tests of claims from the NBER political-economy literature (see
`related-literature.md`), run read-only on the live `documents.db` (droplet, 2026-10-01).
Universe: 260,334 dated government documents (central, provincial, municipal, district) and
185,447 resolved, de-duplicated citation edges between them. Every series is a share or a rate.
No raw-count trend is used anywhere. SQL is in the appendix.*

---

## 0. The questions and the short answers

**Test A. Did the citation graph recentralize after ~2013?** Luo, Wang and Yang
(*Laboratories of Autocracy*, NBER w34219) and Fang, Li and Lu (NBER w33814) date a shift from
decentralized to centralized policymaking at about 2013, inferred from text similarity. We test
it structurally: by year, the share of sub-national citation edges that point upward, sideways
to peers, or downward.

**Short answer.** A 2013 step is visible in the upward share. Among resolved edges issued by
provincial, municipal and district documents, the upward share rises from 0.58 in 2008-2012 to
0.66 in 2013-2017 (continuous-coverage sites). The step is broad-based: it appears in 7 of the 9
continuously crawled sub-national sites. It survives both robustness sets. But it is a plateau,
not a regime change. 2013-2017 only recovers the 2005-2007 level (0.65), and the share drifts
back to 0.60 in 2018-2022 and 0.57 in 2023-2026. The two companion predictions do not hold. The
peer (horizontal, cross-jurisdiction) share is flat at 0.06-0.10 across the whole window. The
downward share (center citing a specific locality) is flat at 0.04-0.06 once coverage is
controlled. The evidence is consistent with a 2013-2017 period of heightened upward
authority-borrowing by localities. It is not evidence of a durable collapse in peer learning.

**Test B. Does the corpus show pilots being generalized upward?** Wang and Yang (*Policy
Experimentation in China*, NBER w29402 / JPE 2025) describe a pilot-then-generalize mechanism.
We detect pilot documents by title cue (试点, 试验区, 先行先试, 示范区), measure who issues them,
and test whether sub-national pilots are later cited by higher levels.

**Short answer.** Pilot titling is a small and shrinking genre: 2.2% of central, 1.9% of
provincial, 0.8% of municipal and 0.3% of district documents (pooled). It peaked in 2015-2016
(central 3.5-4.3%, provincial 3-4%) and has fallen to 1-2% since 2023. Pilots are issued
disproportionately from the top: central documents are 1.3-1.6 times over-represented among
pilot titles, municipal documents 0.4-0.7 times. The upward-absorption mechanism is nearly
invisible in the resolved graph. Of 609 locally originated provincial pilot documents, 9 are
ever cited by a central document (1.5%), against 1.0% for non-pilot provincial documents. Of 572
municipal ones, 1. What the graph does show, strongly, is the reverse flow *(terminology note
2026-10-07: "reverse flow" here means the downward direction, the reverse of absorption; the
synthesis and `bottom-up-channel.md` use "reverse flow" for the UPWARD channel)*: central pilot
designations cited downward by dozens to hundreds of local implementing documents. The
mechanism the corpus can see is designation, not absorption.

---

## 1. Data and definitions

*(**Level basis checked 2026-10-09, and the finding survives.** This memo predates
`doc_identity` and takes levels from `sites.admin_level` — which it flags itself at §1, noting the
~28k npc 地方法规 filed as central. Re-measured on the per-document level, **66,747 of 281,640
resolved edges (23.7%) have at least one endpoint reclassified** (43,047 sources, 39,109 targets),
so the check was worth running. Upward share of sub-national-source edges, all resolved edges, both
bases:*

| period | site basis | per-document basis | shift |
|---|---|---|---|
| 2008-12 | 50.8% | **47.6%** | −3.1 pt |
| 2013-17 | 68.7% | **63.7%** | −5.1 pt |
| 2018-22 | 68.1% | **61.8%** | −6.3 pt |
| 2023-26 | 69.6% | **63.2%** | −6.4 pt |

***The 2013 step survives:*** *+16.1 points on the per-document basis against +17.9 on the site
basis. Every level sits 3-6 points lower — the npc regulations were inflating the "upward" count by
being filed as central targets — but the shape of the finding is unchanged, and the horizontal share
falls 51.6% → 35.6% across the same boundary while downward stays at 0.8%.*

***One thing my check could NOT reproduce, and the limitation is mine, not this memo's.*** *The
all-edges series above shows **no reversion** by 2023-26 (63.2% against 47.6% in 2008-12), where §2.2
reports a return to 2008-12 levels. §2.2 uses the **R2 continuous-site set** — a fixed-site panel —
and I used all resolved edges, so the two are not the same measurement and the difference is most
likely the composition effect a fixed panel exists to remove (`rmb-coverage.md` §4 trap 3). **This is
not evidence against §2.2**; it is a reminder that the reversion is a fixed-panel result and should
always be quoted as one. Re-running the per-document basis **on the R2 panel** is the outstanding
check, and until it is done, `authority-invocation.md`'s disagreement with this memo — that
authority-borrowing by NAME never reverted while borrowing by CITATION did — holds only within the
R2 panel, which is how that memo should be read.)*

**Universe.** `documents` joined to `sites`, `admin_level` in {central, provincial, municipal,
department, district}. Department sites are Shenzhen municipal bureaus and are folded into
municipal. Media and research sites are excluded. `date_published` must be at least 10
characters and the year must lie in 2000-2026. Result: 260,334 documents (central 85,113,
provincial 52,468, municipal 97,929, district 24,824). *(Note 2026-10-01: the central count
includes ~28k npc local people's-congress regulations that `sites.admin_level` files as central.
`citation-network-structure.md` §1.2 re-levels them by publisher (central 62,300 there) and
`joint-issuance.md` excludes npc; level shares are therefore comparable within a memo only.
`consistency-review.md` M7.)*

**Edges.** `citations` with `target_id IS NOT NULL`, both ends inside the universe, self-cites
dropped, de-duplicated on (source, target) across the three `citation_type`s. Result: 185,447
edges. Levels are taken from `sites.admin_level` via the document, not from the stale
`citations.source_level` / `target_level` columns (those disagree with `sites` on 29k rows).

**Direction.** Rank central=0, provincial=1, municipal=2, district=3. Upward: target rank lower
than source. Downward: target rank higher. Horizontal: same rank, split into *peer* (different
jurisdiction family, e.g. Guangzhou citing Zhongshan) and *self* (same family, e.g. a Beijing
bureau citing the Beijing municipal government). Family is the `site_key` prefix before `_`,
with the Shenzhen bureau sites mapped to `sz`.

**Normalization.** Two denominators are used throughout. *Doc-level rate*: share of documents
of a given level and year with at least one edge of the given direction. *Edge-level share*:
share of a given year's resolved edges from a given source level that point in the given
direction. The edge-level share is the primary series because it is immune to the fall in the
share of documents that carry any reference at all (see 2.3).

**Robustness sets.** (R1) *Named*: all central sites plus `gd`, `gz`, `sz`, `bj`, `sh`.
(R2) *Continuous*: sites with at least 20 dated documents in every year 2008-2025. R2 is 16
sites: central `gov`, `ndrc`, `mof`, `mofcom`, `chinatax`, `npc`; sub-national `bj`, `sh`, `gd`,
`js`, `hlj`, `gz`, `zhongshan`, `huizhou`, `jieyang`, `wuhan`. R2 is the primary control because
it is defined by the data, not by assumption. `sz` (the Shenzhen main portal, 1,131 docs) does
not meet the R2 threshold.

**Periods.** 2005-07, 2008-12, 2013-17, 2018-22, 2023-26. 2026 is a partial year (to
2026-10-01) and is thin at the sub-national level in R2; treat 2026 cells as provisional.

**Floors.** Resolution is ~52% overall. Every rate here is a floor on the true rate. Resolution
by source year is not flat: for sub-national sources it rises from 0.35 (2005) to 0.55 (2025).
That trend works *against* the declines reported below, not for them.

---

## 2. Test A: recentralization on the citation graph

### 2.1 Edge-level direction mix of sub-national citations, by period

Share of resolved edges issued by provincial, municipal and district documents. Weighted by
edge count within the period.

| set | period | n_edges | upward | peer (cross-juris.) | self (same juris.) | downward | to central |
|---|---|---|---|---|---|---|---|
| All sites | 2005-07 | 2,266 | 0.663 | 0.096 | 0.202 | 0.040 | 0.554 |
| All sites | 2008-12 | 10,808 | 0.606 | 0.069 | 0.293 | 0.031 | 0.414 |
| All sites | **2013-17** | 19,143 | **0.678** | 0.074 | 0.215 | 0.033 | 0.492 |
| All sites | 2018-22 | 38,535 | 0.622 | 0.062 | 0.288 | 0.028 | 0.468 |
| All sites | 2023-26 | 59,356 | 0.579 | 0.093 | 0.287 | 0.041 | 0.423 |
| R2 continuous | 2005-07 | 2,032 | 0.646 | 0.100 | 0.210 | 0.044 | 0.545 |
| R2 continuous | 2008-12 | 7,026 | 0.581 | 0.073 | 0.304 | 0.042 | 0.437 |
| R2 continuous | **2013-17** | 11,777 | **0.658** | 0.079 | 0.227 | 0.037 | 0.530 |
| R2 continuous | 2018-22 | 16,189 | 0.601 | 0.060 | 0.304 | 0.035 | 0.523 |
| R2 continuous | 2023-26 | 11,870 | 0.565 | 0.080 | 0.308 | 0.048 | 0.469 |
| R1 named | 2008-12 | 3,564 | 0.494 | 0.077 | 0.373 | 0.056 | 0.441 |
| R1 named | **2013-17** | 6,069 | **0.604** | 0.083 | 0.259 | 0.054 | 0.553 |
| R1 named | 2018-22 | 9,476 | 0.527 | 0.061 | 0.369 | 0.043 | 0.474 |
| R1 named | 2023-26 | 6,904 | 0.510 | 0.074 | 0.343 | 0.073 | 0.443 |

**Evidence (edge-level).** The upward share steps up by +7 to +11 points from 2008-12 to
2013-17 in all three sets, and the "to central" share steps up by +8 to +11 points. The step
then reverses: by 2023-26 the upward share is at or below its 2008-12 level in every set. The
peer share never moves outside 0.06-0.10. The downward share from sub-national sources is
negligible (0.03-0.07) and has no trend.

### 2.2 Yearly series (R2 continuous set, sub-national sources)

| year | n_edges | upward | peer | self | to central |
|---|---|---|---|---|---|
| 2008 | 1,046 | 0.655 | 0.073 | 0.217 | 0.471 |
| 2009 | 1,201 | 0.608 | 0.080 | 0.269 | 0.435 |
| 2010 | 1,240 | 0.610 | 0.071 | 0.282 | 0.456 |
| 2011 | 1,734 | 0.527 | 0.062 | 0.375 | 0.415 |
| 2012 | 1,805 | 0.551 | 0.081 | 0.323 | 0.426 |
| **2013** | 2,156 | **0.643** | 0.107 | 0.218 | 0.475 |
| 2014 | 1,787 | 0.637 | 0.090 | 0.233 | 0.457 |
| 2015 | 2,092 | 0.690 | 0.056 | 0.218 | 0.584 |
| 2016 | 2,988 | 0.669 | 0.072 | 0.224 | 0.570 |
| 2017 | 2,754 | 0.647 | 0.073 | 0.240 | 0.538 |
| 2018 | 3,114 | 0.617 | 0.051 | 0.287 | 0.532 |
| 2019 | 2,104 | 0.572 | 0.063 | 0.318 | 0.500 |
| 2020 | 2,989 | 0.583 | 0.068 | 0.308 | 0.524 |
| 2021 | 3,505 | 0.625 | 0.068 | 0.279 | 0.540 |
| 2022 | 4,477 | 0.595 | 0.055 | 0.327 | 0.515 |
| 2023 | 4,083 | 0.588 | 0.069 | 0.308 | 0.499 |
| 2024 | 3,924 | 0.580 | 0.060 | 0.328 | 0.476 |
| 2025 | 2,784 | 0.548 | 0.105 | 0.288 | 0.443 |
| 2026* | 1,079 | 0.466 | 0.127 | 0.287 | 0.399 |

*partial year.

**Evidence.** The inflection is at 2013 exactly: 0.551 in 2012, 0.643 in 2013. The 2011-2012
trough is the lowest point in the series. The 2013-2017 plateau (0.64-0.69) is the highest
sustained stretch. The all-sites series has the same shape (2012: 0.571, 2013: 0.675, 2015:
0.691, 2023: 0.552). The 2013 jump is mirrored by a fall in *self* citation (0.32 to 0.22),
i.e. localities switched from citing their own prior instruments to citing higher-level ones.

### 2.3 Doc-level rates, and why they are not the primary series

Share of sub-national documents with at least one resolved edge of the given kind.

| set | period | n_docs | up_rate | peer_rate | any_edge | up given any edge |
|---|---|---|---|---|---|---|
| All sites | 2008-12 | 9,792 | 0.374 | 0.068 | 0.506 | 0.740 |
| All sites | 2013-17 | 17,096 | 0.392 | 0.070 | 0.492 | 0.797 |
| All sites | 2018-22 | 42,502 | 0.296 | 0.046 | 0.401 | 0.733 |
| All sites | 2023-26 | 101,692 | 0.193 | 0.044 | 0.289 | 0.667 |
| R2 continuous | 2008-12 | 5,860 | 0.397 | 0.078 | 0.540 | 0.737 |
| R2 continuous | 2013-17 | 9,839 | 0.402 | 0.080 | 0.516 | 0.778 |
| R2 continuous | 2018-22 | 15,210 | 0.316 | 0.052 | 0.450 | 0.700 |
| R2 continuous | 2023-26 | 10,536 | 0.283 | 0.073 | 0.443 | 0.640 |

**Evidence.** Doc-level `up_rate` barely moves at 2013 (+0.5 to +2 points) and then falls
sharply after 2018. The fall is a composition effect, not a citation effect. The share of
sub-national documents carrying *any* reference (resolved or not) drops from ~0.80 (2005-2017)
to ~0.45 (2021-2026), as the crawl expanded into bureau and district tiers that publish short
notices and news items. Resolution rose over the same window. So `up_rate` falls because fewer
documents cite anything, not because citing documents cite upward less. The conditional
series (`up given any edge`) shows the 2013 rise (0.74 to 0.78-0.80) and a later decline
(0.64-0.67 by 2023-26). This is why the edge-level mix is the primary series.

### 2.4 Downward citation: the raw series is a coverage artefact

Raw central-source edge mix, all sites: downward share 0.11 (2005-07), 0.12, 0.12, 0.15,
0.21 (2023-26). Taken at face value this says the center names localities more and more.
It does not survive inspection.

**Audit.** The 15 sub-national documents most cited by central documents are, without
exception, central instruments *hosted on* sub-national sites (e.g. 《政府信息公开条例》 on a
Shanghai bureau site, 《产品质量监督抽查管理暂行办法》 on a Fujian bureau site, the 15th
Five-Year Plan outline on a Tibet department site) or title collisions ("发展和改革委员会" on an
Ordos page, 85 central citers). These are resolver matches to mirrored copies, not the center
citing a locality. 25-30% of central-to-sub-national edges have reissue-like target titles
(转发/国务院/国家/中央/图解/解读) and most of the rest are untagged mirrors of the same kind.
The share rises with the sub-national crawl, because more sites mirror more central text.

**Coverage-controlled series.** Central-source edges whose targets are either central or in the
R2 continuous sub-national sites (so the target pool is stable over time):

| period | n_edges | downward share | excl. reissue-titled targets |
|---|---|---|---|
| 2005-07 | 1,313 | 0.054 | 0.036 |
| 2008-12 | 3,393 | 0.058 | 0.042 |
| 2013-17 | 5,556 | 0.046 | 0.026 |
| 2018-22 | 15,461 | 0.055 | 0.036 |
| 2023-26 | 8,182 | 0.041 | 0.029 |

**Evidence.** Flat at 0.04-0.06, with the lowest value in 2013-17. The yearly series ranges
0.02-0.08 with no trend. Downward citation is rare and did not fall after 2013 in any
detectable way. The best reading is "no change", with a weak dip in 2013-17 that is within
year-to-year noise. Even the controlled series still contains mirrors, so the true rate at
which the center names a specific locality is lower than these numbers.

### 2.5 Is the 2013 step broad-based? Per-site check (R2 sub-national sites)

Edge-level upward share by site.

| site | 2008-12 | 2013-17 | 2018-22 | 2023-26 | step at 2013 |
|---|---|---|---|---|---|
| bj | 0.495 | 0.584 | 0.455 | 0.424 | +0.09 |
| gd | 0.534 | 0.626 | 0.579 | 0.453 | +0.09 |
| gz | 0.577 | 0.678 | 0.566 | 0.749 | +0.10 |
| hlj | 0.566 | 0.619 | 0.578 | 0.468 | +0.05 |
| js | 0.514 | 0.618 | 0.575 | 0.455 | +0.10 |
| sh | 0.374 | 0.520 | 0.539 | 0.488 | +0.15 |
| zhongshan | 0.655 | 0.782 | 0.796 | 0.662 | +0.13 |
| huizhou | 0.767 | 0.729 | 0.698 | 0.702 | -0.04 |
| jieyang | 0.802 | 0.773 | 0.742 | 0.540 | -0.03 |

(`wuhan` omitted: 2 edges in 2008-12.)

**Evidence.** 7 of 9 sites step up by 5-15 points at 2013. The two exceptions (Huizhou,
Jieyang) were already at 0.77-0.80 and had little room to rise. The step is not driven by one
site or one province. The subsequent decline (2018 onward) is also broad: 7 of 9 fall from
2013-17 to 2018-22.

### 2.6 Verdict on Test A

- **Upward citation: a 2013 inflection is visible and survives both robustness sets.** The
  edge-level upward share rises 7-11 points at 2013, holds for five years, and is broad across
  sites. Consistent with localities leaning harder on central and provincial authority after
  2013. Not proof of recentralization: the same signature would arise from a wave of central
  instruments that simply demanded local implementation (the 2013-2017 reform package), with
  no change in who initiates policy.
- **Horizontal (peer) citation: no decline.** Flat at 0.06-0.10 throughout. If "laboratories"
  learning from each other left a citation trace, that trace did not shrink after 2013. This
  is the main finding that cuts against the strong form of the claim. A caveat is that peer
  learning may be expressed by title reuse rather than citation, which this test does not
  measure.
- **Downward citation: no change.** 0.04-0.06 in the coverage-controlled series. The raw rise
  is a mirror artefact.
- **The 2013 plateau has since unwound.** By 2023-26 the upward share is back at or below the
  2008-12 level in every set. Whatever happened in 2013-2017 was not permanent in the citation
  graph.

---

## 3. Test B: policy experimentation and its uptake

### 3.1 Pilot share of documents, by level and year (title cue, all sites)

| year | central | provincial | municipal | district | all |
|---|---|---|---|---|---|
| 2008 | 0.021 | 0.013 | 0.004 | 0.000 | 0.014 |
| 2010 | 0.019 | 0.025 | 0.011 | 0.000 | 0.017 |
| 2012 | 0.023 | 0.024 | 0.016 | 0.000 | 0.021 |
| 2013 | 0.035 | 0.022 | 0.005 | 0.000 | 0.019 |
| 2014 | 0.025 | 0.021 | 0.009 | 0.020 | 0.018 |
| **2015** | 0.035 | **0.039** | 0.008 | 0.000 | **0.026** |
| **2016** | **0.043** | 0.030 | 0.013 | 0.000 | **0.029** |
| 2017 | 0.020 | 0.031 | 0.013 | 0.002 | 0.020 |
| 2018 | 0.030 | 0.032 | 0.008 | 0.000 | 0.024 |
| 2020 | 0.031 | 0.030 | 0.012 | 0.004 | 0.023 |
| 2022 | 0.032 | 0.026 | 0.004 | 0.001 | 0.014 |
| 2024 | 0.020 | 0.015 | 0.007 | 0.003 | 0.011 |
| 2025 | 0.018 | 0.012 | 0.007 | 0.005 | 0.010 |

Pooled 2005-26 by cue: central 0.022 (试点 0.015, 示范区/试验区 0.007), provincial 0.019,
municipal 0.008, district 0.003. 先行先试 is below 0.001 at every level.

**Evidence.** Pilot titling rises from ~1.5% (2005-12) to a 2015-16 peak (2.6-2.9% overall)
and then declines to ~1% by 2024-25. The R2 continuous set shows the same shape (central peak
0.041-0.047 in 2015-16; municipal 0.016-0.020 in 2010-12 falling to 0.001-0.005 in 2023-26).
The decline is not a composition effect of new tiers: it holds inside the fixed site set.

### 3.2 Who issues pilots

Share of pilot-titled documents by level, against that level's share of all documents.
Propensity = ratio of the two.

| period | central | provincial | municipal | district |
|---|---|---|---|---|
| 2008-12 | 0.49 of pilots / prop. **1.15** | 0.29 / **1.36** | 0.22 / 0.62 | 0.00 / 0.00 |
| 2013-17 | 0.51 / **1.40** | 0.34 / **1.29** | 0.15 / 0.43 | 0.01 / 0.14 |
| 2018-22 | 0.60 / **1.57** | 0.24 / **1.42** | 0.16 / 0.42 | 0.01 / 0.06 |
| 2023-26 | 0.41 / **1.52** | 0.26 / **1.30** | 0.29 / 0.70 | 0.06 / 0.42 |

**Evidence.** Pilots are a top-weighted genre. Central and provincial documents are
over-represented among pilot titles in every period, municipal and district documents
under-represented. The central propensity rises from 1.15 (2008-12) to 1.40 (2013-17) and
1.57 (2018-22). The municipal propensity falls from 0.62 to 0.42-0.43 over the same two
periods. This is the one place in Test B where a 2013 shift appears: after 2013, pilot
titling tilts further toward the center. The 2023-26 partial recovery at municipal and
district level comes with the bureau/district tier expansion and should be read with care.

### 3.3 Designation: do sub-national pilots cite a higher-level pilot?

Among sub-national pilot documents, share that cite (resolved) a *higher-level* pilot
document, and the same share conditional on citing anything at all.

| level | period | n | cites higher-level pilot | given any citation | 国家 in title |
|---|---|---|---|---|---|
| provincial | 2008-12 | 83 | 0.25 | 0.57 | 0.12 |
| provincial | 2013-17 | 210 | 0.33 | 0.58 | 0.12 |
| provincial | 2018-22 | 314 | 0.35 | 0.57 | 0.28 |
| provincial | 2023-26 | 341 | 0.10 | 0.25 | 0.16 |
| municipal | 2008-12 | 61 | 0.20 | 0.38 | 0.16 |
| municipal | 2013-17 | 90 | 0.21 | 0.40 | 0.11 |
| municipal | 2018-22 | 208 | 0.20 | 0.50 | 0.19 |
| municipal | 2023-26 | 381 | 0.11 | 0.29 | 0.11 |

**Evidence.** When a provincial pilot document cites anything, more than half the time
(2008-2022) it cites a higher-level pilot instrument. This is the designation chain: the
locality's pilot is the local leg of a central pilot programme. The strongest anchors are
central: 《关于支持深圳建设中国特色社会主义先行示范区的意见》 (127 distinct sub-national citers),
《深化医疗服务价格改革试点方案》 (90), 《国务院关于开展营商环境创新试点工作的意见》 (22),
the Shanghai and Guangdong 自贸试验区 总体方案 (16 each). The 2023-26 drop in this share tracks
the general drop in resolved outbound citation and is partly censoring (recent central pilots
not yet in the corpus or not yet resolved), so it should not be read as a change in behaviour.

### 3.4 Absorption: are sub-national pilots cited upward later?

**Naive version.** Share of sub-national documents cited later (lag >= 0) by a strictly
higher-level document, pilot vs non-pilot, same level and period.

| level | period | n_pilot | pilot uptake | n_non | non-pilot uptake | pilot within 3y | non-pilot within 3y |
|---|---|---|---|---|---|---|---|
| provincial | 2008-12 | 83 | 0.000 | 3,605 | 0.014 | 0.000 | 0.006 |
| provincial | 2013-17 | 210 | 0.033 | 6,873 | 0.020 | 0.024 | 0.013 |
| provincial | 2018-22 | 314 | 0.006 | 11,161 | 0.022 | 0.006 | 0.018 |
| provincial | 2023-26 | 341 | 0.015 | 26,835 | 0.007 | 0.015 | 0.007 |
| municipal | 2008-12 | 61 | 0.016 | 5,835 | 0.012 | 0.000 | 0.005 |
| municipal | 2013-17 | 90 | 0.011 | 8,974 | 0.016 | 0.011 | 0.010 |
| municipal | 2018-22 | 208 | 0.029 | 25,304 | 0.006 | 0.019 | 0.004 |
| municipal | 2023-26 | 381 | 0.005 | 55,983 | 0.006 | 0.003 | 0.005 |

**Audit of the naive version.** The sub-national pilot documents with the most higher-level
citers are reissues of central documents: a Beijing 图解 of the State Council's 2030 可持续发展
议程创新示范区 notice (22 higher-level citers, 38 central), a Shanwei 转发 of a State Council
营改增 notice, a Guangdong 转发 of the 药品上市许可持有人制度试点方案. The resolver matched the
local copy of a central title. These are not local pilots absorbed by the center.

**Local-origin version.** Restrict both pilot and non-pilot documents to titles without a
reissue cue (转发, 国务院, 国家, 中央, 中共, 印发…部/委/总局, 图解, 解读). 51-81% of sub-national
pilot titles pass this filter.

| level | n local-origin pilots | cited by any higher level | cited by central | n local-origin non-pilot | any higher | central |
|---|---|---|---|---|---|---|
| provincial | 609 | 9 (0.015) | 9 (0.015) | 41,039 | 0.010 | 0.010 |
| municipal | 572 | 8 (0.014) | 1 (0.002) | 90,139 | 0.006 | 0.002 |
| district | 67 | 0 (0.000) | 0 | 23,097 | 0.003 | 0.000 |

**Evidence.** Upward uptake of locally originated pilot documents is 1.4-1.5% at provincial
and municipal level, against 0.6-1.0% for non-pilot documents of the same level. The pilot
excess is +0.5 to +0.8 points on a base of 9 and 8 documents. That is not a detectable
mechanism. Peer uptake (cited later by a same-level document in another jurisdiction) shows
no pilot excess either: provincial 0.014-0.025 vs 0.009-0.030; municipal 0.000-0.013 vs
0.003-0.014.

**What the 9 provincial cases are.** The top local-origin pilots with central citers are
Jiangsu's 中国制造2025 苏南城市群试点示范 implementation opinion (8 central citers, lags 3-171
days, citers are MIIT/CAC/MOF news and a funds-management measure) and two Shanghai 自贸试验区
制度型开放 implementation plans (5 central citers each, lags 97-147 days, citers are MOF/tax/
MOFCOM announcements on the same programme). These are concurrent implementation of a central
programme, with central and local documents citing a shared anchor within months. They are not
a local trial generalized after the fact.

**Lag.** For the few upward edges to pilot targets (37 in 2013-17, 13 in 2018-22, 16 in
2023-26), the median lag falls from 1,331 days (2013-17) to 173 days (2018-22) and 144 days
(2023-26). Non-pilot upward edges show the same compression (1,747 to 818 to 205 days). The
compression is right-censoring (recent targets have had less time to be cited) plus the
corpus's growing recency, not a pilot-specific effect.

**Central citation of sub-national pilots vs baseline.** Among central-to-sub-national edges
(all sites, raw), the share whose target is a pilot document is 0.0-0.06 by year, against a
pilot share of 0.01-0.016 among sub-national documents. No enrichment beyond noise.

### 3.5 Verdict on Test B

- **Pilot titling is a top-weighted and shrinking genre.** Central and provincial documents
  carry pilot titles 1.3-1.6 times more often than their share of the corpus; municipal 0.4-0.7
  times. The 2015-16 peak and subsequent decline hold inside the fixed-site set.
- **After 2013 pilots tilt further toward the center** (central propensity 1.15 to 1.40 to
  1.57). This is the Test B counterpart of the Test A upward step and points the same way.
- **The designation chain is clearly visible.** Half or more of citing provincial pilots cite a
  higher-level pilot instrument. The strongest pilot anchors in the graph are central
  designations cited downward by 16-127 local documents.
- **The absorption chain is not visible.** Locally originated pilots are cited upward at
  1.4-1.5%, within a point of non-pilots, on single-digit counts. The handful of real cases
  are concurrent implementation of a central programme, not post-hoc generalization.
- This is a null on the *citation* channel only. Wang and Yang's generalization is a policy
  event (a national rollout), which may never cite the local trial by document. The corpus
  cannot see generalization that is expressed as a new central instrument without a
  reference. The right next test is title-term propagation (the local pilot's distinctive
  terms appearing in later central titles), which is outside this note.

---

## 4. Threats to validity

1. **Resolution is ~52% and not flat.** Sub-national resolution rises from 0.35 (2005) to
   0.55 (2025). All rates are floors. The upward step at 2013 coincides with resolution rising
   from 0.45 (2012) to 0.49 (2013); a 4-point resolution change cannot produce a 9-point share
   change unless the newly resolved edges are overwhelmingly upward, which is possible but
   would itself be a form of the same finding (more resolvable, i.e. more formal, upward
   references).
2. **Coverage ramp (~70x).** Handled by using shares only, by the R1/R2 robustness sets, and by
   the coverage-controlled downward series. R2 is still not coverage-flat within site (e.g.
   `gov` 2008-12 vs 2013-17 volumes differ by 1.5x, `bj` by 6x).
3. **Mirror and collision artefacts.** Central text hosted on sub-national sites inflates
   "downward" edges and "upward uptake of pilots". Both were audited and corrected (2.4, 3.4).
   The reissue-cue filter is a title heuristic and will miss untagged mirrors; the corrected
   rates are therefore still upper bounds on the genuine rates.
4. **Genre composition.** The share of sub-national documents carrying any reference halves
   after 2019 as bureau and district tiers enter. Edge-level mixes are robust to this; doc-level
   rates are not (2.3).
5. **Pilot detection is title-only.** Documents that are pilots in substance but not in title
   are missed. 示范区 also catches non-experimental zone designations. The cue set is the one
   specified for this test; the 试点-only series (appendix query B6) has the same shape.
6. **Censoring.** Upward uptake and lags for 2018+ targets are right-censored. The 3-year
   window series is the comparable one and shows the same null.
7. **Publication date is not adoption date.** Lags are proxies.
8. **2026 is partial** and sub-nationally thin in R2.
9. **Not causal.** A 2013 rise in upward citation is equally consistent with a surge of central
   instruments that required local implementing documents. The graph records the structure of
   references, not where initiative lay.
10. **Scope boundary.** Mechanism-level claims about a published document record, with the
    coverage bias (2), the resolution floor (1) and the publication caveat (7) above. No
    regime-type labels. *(Added 2026-10-01 per `consistency-review.md` §2.)*

---

## 5. Bottom line

The citation graph shows a 2013 inflection in one direction only. Localities cited upward more
from 2013 to 2017, broadly across sites, and the result holds in a continuous-coverage set.
Peer citation did not fall and downward citation did not change. The upward plateau unwound
after 2018. Pilot titling peaked in 2015-16, tilted toward the center after 2013, and the
upward absorption of local pilots is not detectable by citation; what the graph records is
central designation flowing down. The evidence is consistent with a mid-2010s increase in
authority-borrowing and in central framing of experimentation. It does not establish that
bottom-up innovation stopped, because the graph channel for that (peer citation, upward
absorption) was already thin before 2013 and did not thin further.

---

## Appendix: SQL

All queries ran against `file:/root/china-governance/documents.db?mode=ro`. Temp tables only.
`is_pilot(title)` is a Python regex `试点|试验区|先行先试|示范区`; `is_reissue(title)` is
`转发|国务院|国家|中央|中共|印发.*(部|委|总局|总署)|图解|解读`; `fam(site_key)` is the prefix
before `_`. Scripts: `recentral.py` and `followup.py` (session scratchpad, not committed).

```sql
-- Universe
CREATE TEMP TABLE docs AS
SELECT d.id, CAST(substr(d.date_published,1,4) AS INT) y, substr(d.date_published,1,10) dt,
       CASE s.admin_level WHEN 'central' THEN 0 WHEN 'provincial' THEN 1
            WHEN 'municipal' THEN 2 WHEN 'department' THEN 2 WHEN 'district' THEN 3 END rk,
       d.site_key,
       CASE WHEN s.admin_level='department' THEN 'sz' ELSE fam(d.site_key) END fam,
       is_pilot(d.title) pilot, is_reissue(d.title) reissue,
       CASE WHEN d.site_key IN ('bj','chinatax','gd','gov','gz','hlj','huizhou','jieyang','js',
                                'mof','mofcom','ndrc','npc','sh','wuhan','zhongshan') THEN 1 ELSE 0 END cont
FROM documents d JOIN sites s USING(site_key)
WHERE length(d.date_published)>=10 AND substr(d.date_published,1,4) BETWEEN '2000' AND '2026'
  AND s.admin_level IN ('central','provincial','municipal','department','district');

-- Continuous-coverage site set (R2)
SELECT site_key FROM (SELECT site_key, y, count(*) n FROM docs
                      WHERE y BETWEEN 2008 AND 2025 GROUP BY 1,2 HAVING n>=20)
GROUP BY site_key HAVING count(*)=18;

-- Resolved, de-duplicated edges
CREATE TEMP TABLE e AS
SELECT DISTINCT c.source_id sid, c.target_id tid, s.y sy, t.y ty, s.rk srk, t.rk trk,
       s.fam sfam, t.fam tfam, s.site_key ssite, t.site_key tsite,
       julianday(s.dt)-julianday(t.dt) lag, t.pilot tpilot, t.reissue treissue,
       s.cont scont, t.cont tcont
FROM citations c JOIN docs s ON s.id=c.source_id JOIN docs t ON t.id=c.target_id
WHERE c.target_id IS NOT NULL AND c.source_id<>c.target_id;

-- A: edge-level direction mix, sub-national sources (add AND scont=1 for R2)
SELECT sy, count(*) n,
       1.0*sum(trk<srk)/count(*)                 up_share,
       1.0*sum(trk=srk AND sfam<>tfam)/count(*)  peer_share,
       1.0*sum(trk=srk AND sfam=tfam)/count(*)   self_share,
       1.0*sum(trk>srk)/count(*)                 down_share,
       1.0*sum(trk=0)/count(*)                   to_central_share
FROM e WHERE srk>0 AND sy BETWEEN 2005 AND 2026 GROUP BY sy;

-- A: doc-level rates, sub-national
WITH up AS (SELECT DISTINCT sid FROM e WHERE trk<srk),
     pe AS (SELECT DISTINCT sid FROM e WHERE trk=srk AND srk>0 AND sfam<>tfam),
     an AS (SELECT DISTINCT sid FROM e)
SELECT y, count(*) n,
       1.0*sum(id IN (SELECT sid FROM up))/count(*) up_rate,
       1.0*sum(id IN (SELECT sid FROM pe))/count(*) peer_rate,
       1.0*sum(id IN (SELECT sid FROM an))/count(*) any_edge_rate,
       1.0*sum(id IN (SELECT sid FROM up))/NULLIF(sum(id IN (SELECT sid FROM an)),0) up_given_any
FROM docs WHERE rk>0 AND y BETWEEN 2005 AND 2026 GROUP BY y;

-- A: coverage-controlled downward share (central sources, stable target pool)
SELECT sy, count(*) n, 1.0*sum(trk>0)/count(*) down_share,
       1.0*sum(trk>0 AND treissue=0)/(count(*)-sum(trk>0 AND treissue=1)) down_excl_reissue
FROM e WHERE srk=0 AND scont=1 AND (trk=0 OR tcont=1) AND sy BETWEEN 2005 AND 2026 GROUP BY sy;

-- A: audit of what central->sub-national edges point at
SELECT tid, d.title, ty, tsite, count(DISTINCT sid) n
FROM e JOIN documents d ON d.id=e.tid WHERE srk=0 AND trk>0
GROUP BY tid ORDER BY n DESC LIMIT 15;

-- A: per-site up share by period (R2 sub-national)
SELECT ssite,
  1.0*sum(sy BETWEEN 2008 AND 2012 AND trk<srk)/NULLIF(sum(sy BETWEEN 2008 AND 2012),0) up_0812,
  1.0*sum(sy BETWEEN 2013 AND 2017 AND trk<srk)/NULLIF(sum(sy BETWEEN 2013 AND 2017),0) up_1317,
  1.0*sum(sy BETWEEN 2018 AND 2022 AND trk<srk)/NULLIF(sum(sy BETWEEN 2018 AND 2022),0) up_1822,
  1.0*sum(sy BETWEEN 2023 AND 2026 AND trk<srk)/NULLIF(sum(sy BETWEEN 2023 AND 2026),0) up_2326
FROM e WHERE srk>0 AND scont=1 GROUP BY ssite;

-- Resolution and any-reference share by source year (uses unresolved rows too)
SELECT s.y, count(*) n_refs, 1.0*sum(c.target_id IS NOT NULL)/count(*) resolved_share,
       1.0*count(DISTINCT c.source_id)/(SELECT count(*) FROM docs d2 WHERE d2.rk>0 AND d2.y=s.y) docs_with_any_ref
FROM citations c JOIN docs s ON s.id=c.source_id WHERE s.rk>0 GROUP BY s.y;

-- B1: pilot share by year and level
SELECT y,
  1.0*sum(pilot AND rk=0)/NULLIF(sum(rk=0),0) central,
  1.0*sum(pilot AND rk=1)/NULLIF(sum(rk=1),0) provincial,
  1.0*sum(pilot AND rk=2)/NULLIF(sum(rk=2),0) municipal,
  1.0*sum(pilot AND rk=3)/NULLIF(sum(rk=3),0) district
FROM docs WHERE y BETWEEN 2005 AND 2026 GROUP BY y;

-- B2: issuing level propensity (share of pilots / share of all docs), by period
WITH p AS (SELECT CASE WHEN y<2008 THEN '2005-07' WHEN y<2013 THEN '2008-12' WHEN y<2018 THEN '2013-17'
                       WHEN y<2023 THEN '2018-22' ELSE '2023-26' END per, * FROM docs WHERE y BETWEEN 2005 AND 2026)
SELECT per, rk, sum(pilot) n_pilot,
  (1.0*sum(pilot)/(SELECT sum(pilot) FROM p p2 WHERE p2.per=p.per)) /
  (1.0*count(*)/(SELECT count(*) FROM p p2 WHERE p2.per=p.per)) propensity
FROM p GROUP BY 1,2;

-- B3: designation (sub-national pilot cites a higher-level pilot)
WITH hp AS (SELECT DISTINCT sid FROM e WHERE trk<srk AND tpilot=1),
     an AS (SELECT DISTINCT sid FROM e)
SELECT rk, y, count(*) n,
  1.0*sum(id IN (SELECT sid FROM hp))/count(*) cites_higher_pilot,
  1.0*sum(id IN (SELECT sid FROM hp))/NULLIF(sum(id IN (SELECT sid FROM an)),0) given_any
FROM docs WHERE rk>0 AND pilot=1 AND y BETWEEN 2005 AND 2026 GROUP BY 1,2;

-- B4: upward uptake, local-origin pilot vs non-pilot (drop reissue=0 for the naive version)
WITH upin AS (SELECT DISTINCT tid FROM e WHERE srk<trk AND lag>=0),
     cin  AS (SELECT DISTINCT tid FROM e WHERE srk=0 AND trk>0 AND lag>=0),
     up3  AS (SELECT DISTINCT tid FROM e WHERE srk<trk AND lag BETWEEN 0 AND 1095)
SELECT rk, sum(pilot) n_pilot,
  1.0*sum(pilot AND id IN (SELECT tid FROM upin))/NULLIF(sum(pilot),0)          pilot_up,
  1.0*sum(pilot AND id IN (SELECT tid FROM cin))/NULLIF(sum(pilot),0)           pilot_central,
  1.0*sum((NOT pilot) AND id IN (SELECT tid FROM upin))/NULLIF(sum(NOT pilot),0) non_up,
  1.0*sum((NOT pilot) AND id IN (SELECT tid FROM cin))/NULLIF(sum(NOT pilot),0)  non_central
FROM docs WHERE rk>0 AND reissue=0 AND y BETWEEN 2005 AND 2026 GROUP BY rk;

-- B5: lag of upward edges to pilot targets (median computed in Python)
SELECT ty, lag FROM e WHERE srk<trk AND lag>=0 AND tpilot=1;

-- B6: pilot-target share of central->sub-national edges vs baseline
SELECT sy, count(*) n, 1.0*sum(tpilot)/count(*) pilot_target_share,
  (SELECT 1.0*sum(pilot)/count(*) FROM docs d WHERE d.rk>0 AND d.y BETWEEN 2005 AND e.sy) baseline
FROM e WHERE srk=0 AND trk>0 AND lag>=0 AND sy BETWEEN 2005 AND 2026 GROUP BY sy;

-- B8: central pilot anchors by distinct sub-national citers
SELECT tid, d.title, ty, count(DISTINCT sid) n
FROM e JOIN documents d ON d.id=e.tid WHERE srk>0 AND trk=0 AND tpilot=1
GROUP BY tid ORDER BY n DESC LIMIT 10;
```
