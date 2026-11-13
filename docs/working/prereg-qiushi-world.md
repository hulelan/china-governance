# Pre-registration: world vocabulary in 《求是》, 2019-01 to 2026-11

*Written 2026-11-12, before any concept term was counted. Only denominators had been computed
when this was written (articles per issue and per year, Xi-authored articles per year, body
lengths, duplicate titles: `qiushi_world_series.py --phase denoms`). Any later change to a term
set, a rule or a threshold is appended below as a dated note, never edited in place.*

## Why this test exists

`global-discourse-map.md` could only do a 2025-26 cross-section because the media layer was
crawl-thin before 2025. The plenum dispute (`data/disputes/plenum.json`) compares single
documents (2009, 2024, 2025, 2026) and finds the world moving from opportunity and mission to
threat. That is four documents. 《求是》, crawled issue by issue, is a series whose denominator is
the journal: measured on the denominator pass, every year 2019-2025 has all 24 issues and
2026 has issues 1-21 with no gap, 10-24 articles per issue, and a Xi-authored article in every
issue except one in 2025.

## Population

- `site_key='qiushi'`, year from the `issue=求是YYYY/NN` field in `relation` (the cover year).
- Body `>= 200` characters (drops the 国家统计局 统计图表 rows, which have no body).
- One copy per (site, whitespace-normalized title, year), the longest body (6 dropped).
- Xi-authored: `author=习近平` exactly, or a title beginning `习近平：`. (`习近平外交思想研究中心` and
  titles beginning `习近平总书记` are NOT Xi-authored.)
- Replication: `gmrb_theory` (光明日报 theory pages) and `rmlt` (人民论坛), year from
  `date_published`. Their yearly article counts swing with the crawler (gmrb 2021 is 962 vs
  ~1,300-1,600 elsewhere; rmlt 2020 is 1,511 vs ~600-1,000), so only SHARES are compared there,
  never counts.

## Unit and terms (frozen; regexes in `scripts/rnd/analysis/qiushi_world_series.py:TERMS`)

Unit: share of articles carrying a term at least once (title + body, Python regex, so no FTS
floor). Secondary: occurrences per 100,000 body characters, because 2026 articles are shorter
(median 4,508 characters against 4,937-6,033 in earlier years) and more numerous per issue
(19.5 against 14-17), which lowers a per-article hit probability mechanically.

- **MISSION index** (any of): 人类命运共同体; 全球发展/安全/文明/治理倡议 or 三/四大全球倡议;
  全人类共同价值; 胸怀天下.
- **THREAT index** (any of): 百年(未有之)(大)变局 (catches 世界百年变局); 动荡变革期; 霸权主义;
  敢于斗争 | 善于斗争 | 斗争精神 | 伟大斗争; 总体国家安全观.
- Reported but outside the indices: bare 斗争, bare 国家安全, 全球南方, 多极化, 平等有序的(世界)多极化,
  世界眼光, 中国式现代化, 人类文明新形态, and each initiative separately.
- Variants: **M2** = MISSION without the initiatives (they did not exist before September 2021,
  so their arrival raises MISSION mechanically); **T2** = THREAT without the 斗争 family
  (百年变局, 动荡变革期, 霸权主义 only).

## Predictions

**P1 (primary, the plenum hypothesis).** The ratio THREAT share / MISSION share is higher in
2025-26 pooled than in 2019-20 pooled. Holds if the ratio rises by at least 20% (relative);
fails if it is flat (within ±20%) or falls.

**My own expectation, registered separately so a failure is not dressed up later:** I expect P1
to be at risk. Both families should rise, and MISSION gets a mechanical lift from four
initiatives launched inside the window (GDI 2021-09, GSI 2022-04, GCI 2023-03, GGI 2025-09)
while 斗争 language peaked around Xi's September 2019 Central Party School speech on 斗争. I put
P1 at roughly even odds. P1 on M2 / T2 (the ratio without the initiatives and without 斗争) is
the cleaner test and I expect it to hold more likely than not (about 60%).

**P2 (composition).** Whatever direction the indices move in all articles, the same direction
holds in non-Xi articles alone. If the movement is present only in Xi articles (24 a year), it
is a property of which speeches were chosen to lead issues, not of the journal's editorial line.

**P3 (replication).** The sign of the P1 ratio change is the same in gmrb_theory and rmlt.

**Named validity targets** (pipeline checks, each expected exactly, any miss means a dating or
matching defect, not a finding):
- N1: 全球治理倡议 is in 0 articles dated before issue 2025/17 (GGI announced 2025-09-01).
- N2: 全球文明倡议 is in 0 articles before issue 2023/06 (GCI announced 2023-03-15).
- N3: 动荡变革期 is in at most 2 articles before issue 2020/21 (the phrase enters at the
  October 2020 Fifth Plenum; an earlier stray use is possible).
- N4: 全球南方 is in fewer articles in 2019-21 combined than in 2025 alone.

## What would count as a null

P1 failing on both the full and the M2/T2 indices: the journal does not show the plenum's
mission-to-threat shift, and the plenum contrast is then a property of the 2026 Party-building
decision as a document, not of the discourse around it. That will be reported as the finding.

## Amendments

(none; no term, rule or threshold was changed after counting)

## Result (appended 2026-11-12, after counting)

- P1 holds on the primary ratio, narrowly: THREAT/MISSION 1.89 → 2.34 (+24%). It holds strongly
  on T2/M2 (1.08 → 2.25). But the THREAT share itself fell (31.9% → 28.8%); the ratio rose because
  MISSION fell (16.9% → 12.3%, mostly in 2026), and the 斗争 family fell by two thirds.
- P2 holds: same direction in non-Xi articles (1.92 → 2.34).
- P3 fails on the primary index (光明日报 −3%, 人民论坛 +2%, both flat) and holds on T2/M2
  (+28%, +26%; 《红旗文稿》 +55%).
- N1-N4 all pass.
Write-up: `docs/research/qiushi-world-vocabulary.md`.
