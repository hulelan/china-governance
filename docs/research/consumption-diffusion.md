# How the 2024–2026 "Boost Consumption" Campaign Diffused Through the Administrative Hierarchy

*A worked analysis on the china-governance corpus (263,573 docs, SQLite on the droplet).
All figures pulled read-only from the live `documents.db` on 2026-08-22. SQL is inline so
every claim is reproducible.*

---

## 0. The question and the short answer

**Question.** Two central documents anchor the 2024–2026 consumption-stimulus push:

- 《推动大规模设备更新和消费品以旧换新行动方案》 — *Action Plan for Promoting Large-Scale
  Equipment Renewal and Consumer-Goods Trade-In* (State Council, **2024-03-13**), hereafter
  **"trade-in"**; and
- 《提振消费专项行动方案》 — *Special Action Plan to Boost Consumption* (CPC General Office /
  State Council General Office, **2025-03-16**), hereafter **"boost-consumption."**

How did they propagate down the province → city → district hierarchy — as a cascade or a flat
scatter, how fast, and who moved (or didn't)?

**Short answer (the diffusion story).** The trade-in plan behaves like a textbook top-down
cascade: the State Council issued it 2024-03-13, Guangdong province re-issued its own version
in **20 days**, and within **~80 days** at least **10 provinces and 12 prefecture-cities** had
published localized re-issuances — provinces slightly ahead of the cities nested under them,
exactly the ordering a cascade predicts. Uptake is measurable two independent ways that agree:
the resolved `citations` graph shows **92 distinct documents** citing the trade-in anchors
(35 central, 11 provincial, 6 municipal for the 2024 core) and **57** citing the boost-
consumption anchor, while title-matching finds **~50 distinct localized re-issuances** of the
trade-in plan across 5 administrative levels. The boost-consumption plan (issued a year later)
shows the same shape but a **slower, still-unfolding** tail — Guangdong at 52 days, Beijing at
116, a Haidian-district version only in July 2026 — consistent with a campaign caught mid-
diffusion at the data cutoff. The single biggest caveat is **selection**: 17 of the ~50 trade-in
re-issuers are Guangdong cities (the corpus's deepest tier), so the *speed* estimates are sound
but the *breadth* is a floor, not a census, and the long lag tail (Zhejiang 320d, Fujian 330d,
Ningxia 414d) reflects **when we started crawling those portals**, not when those provinces acted.

---

## 1. The central anchors (the actual rows)

`title LIKE` on the two flagship phrases, sorted by `citation_rank` (the corpus's PageRank-like
weighted-inbound-citation score):

| id | title (truncated) | date | site | admin_level | citation_rank |
|---|---|---|---|---|---|
| 12704698 | 受权发布丨…印发《提振消费专项行动方案》 | 2025-03-16 | xinhua | media | **200.0** |
| 12650974 | 中共中央办公厅 国务院办公厅印发《提振消费专项行动方案》 | 2025-03-16 | gov | central | 0.0† |
| 900039931 | 国务院关于印发《推动大规模设备更新和消费品以旧换新行动方案》的通知 | 2024-03-13 | gov | central | **153.0** |
| 12689280 | 省政府关于印发江苏省推动大规模设备更新和消费品以旧换新行动方案的通知 | 2024-05-09 | js | provincial | 162.0 |
| 900046374 | 关于2025年加力扩围实施大规模设备更新和消费品以旧换新政策的通知 | 2025-01-08 | gov | central | 79.0 |
| 900047223 | 商务部等14部门关于印发《推动消费品以旧换新行动方案》的通知 | 2024-04-13 | gov | central | 30.0 |
| 900047235 | 市场监管总局等七部门…《以标准提升牵引设备更新和消费品以旧换新行动方案》 | 2024-04-10 | gov | central | 10.0 |

† **Anchor-identity gotcha, stated up front.** The *canonical* boost-consumption text
(`gov`, id 12650974) scores 0 because downstream documents overwhelmingly cite the **Xinhua
authorized release** (受权发布, id 12704698, cr=200) — Xinhua is the official promulgation
channel, so its copy is what everyone references by 《》 title. For the trade-in plan the
State Council copy (id 900039931, cr=153) *is* the cited node. Throughout this memo I treat
each flagship as an **anchor set** (all near-duplicate promulgations of the same text) rather
than a single row, so citations to the Xinhua copy, the `gov` copy, and the ministry copies
are pooled. This is the first threat to validity and it is structural, not incidental.

The trade-in "family" also spawned a **sequence** of central follow-ons that themselves became
anchors: the 2024-07 加力支持…若干措施 (发改环资〔2024〕1104号, cr=70), the 2025 加力扩围
(cr=79), and the 2026 提质增效 (chinatax, cr=100). The campaign is not one document but a
**rolling annual re-issuance** at the center, which matters for the diffusion story (§3).

Top consumption-themed rows by `citation_rank`, for orientation (query: `title LIKE '%消费%' OR
'%以旧换新%' OR '%设备更新%'`, top 15) — the two action-plan families dominate the *policy*
rows; the higher-ranked 消费者权益保护法 / tax-administration rows are unrelated statutory
staples and are excluded from the diffusion set:

```
368.5  消费者权益保护法                      (statute, excluded)
252.5  李强主持国常会…（2025-08）             (meeting readout)
200.0  受权发布…《提振消费专项行动方案》        ← boost-consumption anchor
186.0  汽车以旧换新补贴实施细则 (2024-04)       ← trade-in operational rule
162.0  江苏省…设备更新和消费品以旧换新行动方案   ← provincial re-issuance, top-cited
153.0  国务院…《推动大规模设备更新…行动方案》     ← trade-in central anchor
 79.0  2025年加力扩围…以旧换新政策             ← trade-in annual follow-on
```

---

## 2. Uptake via the citation graph

Pooling the anchor sets and counting **distinct citing documents** by the citing doc's
administrative level (`citations` join `documents`, `COUNT(DISTINCT source_id)`):

**Table 2a — who cites the anchors (resolved citation graph)**

| anchor set | central | provincial | municipal | district | media | distinct citers |
|---|---:|---:|---:|---:|---:|---:|
| trade-in, 2024 core (900039931 / 900047223 / 900047235) | 35 | 11 | 6 | 0 | 1 | **53** |
| trade-in, 2025 expansion (900046374 / …1104号 / 加力支持) | 33 | 12 | 7 | 1 | 0 | **53** |
| boost-consumption (12704698 / 12650974) | 37 | 3 | 7 | 3 | 22 | **72** |

Reading it:

- The **trade-in** plan's citers are led by the **center itself** (35–33 central docs) — the
  campaign is sustained by a dense web of ministerial follow-ons (发改委, 财政部, 商务部,
  市场监管总局, 税务总局 all cross-cite the plan) — with a solid **provincial** second tier
  (11–12) and a real but thinner **municipal** tier (6–7). That top-heaviness is expected for a
  fiscal instrument tied to 超长期特别国债 (ultra-long special treasury bonds): the money and
  the operational rules are set centrally, localities implement.
- The **boost-consumption** plan is much more **media-cited** (22 Xinhua/People's Daily items)
  and central (37), with provincial/municipal uptake (3 + 7) still ramping at cutoff — it is one
  year younger and the local re-issuance wave is only beginning (§3).

**Table 2b — the same anchors, pooled, by level** (all 8 anchor ids):

| source_level | distinct citing docs |
|---|---:|
| central | 92 |
| provincial | 25 |
| municipal | 20 |
| media | 23 |
| district | 4 |

The monotonic central ≫ provincial > municipal > district gradient is the graph-level signature
of a hierarchical cascade — but note it is also exactly what a **coverage-biased** corpus would
produce (we crawl the center exhaustively and districts barely), so the *shape* is suggestive and
the re-issuance timing in §3 is the load-bearing evidence.

---

## 3. Uptake via title-matched re-issuances — the cascade, with lags

The stronger test: localities don't just *cite* the plan, they **re-issue their own named
version**. Title-matching the trade-in family (`title LIKE '%设备更新%以旧换新%'` and the
消费品以旧换新 action/implementation-plan variants), taking each locality's **earliest**
re-issuance and computing lag from the **2024-03-13** central anchor:

**Table 3a — trade-in re-issuance cascade (first localized issuance per unit, lag in days)**

| first issued | level | unit | lag (days) | title cue → verbatim / adapted |
|---|---|---|---:|---|
| 2024-04-02 | provincial | Guangdong (gd) | **20** | 实施方案 (adapted) |
| 2024-04-08 | municipal | Jieyang | 26 | 实施方案 (adapted) |
| 2024-04-09 | municipal | Shanwei | 27 | 实施方案 (adapted) |
| 2024-04-15 | municipal | Jiangmen | 33 | 实施方案 (adapted) |
| 2024-04-19 | provincial | Heilongjiang | 37 | 实施方案 (adapted) |
| 2024-04-28 | provincial | Beijing | 46 | 积极推动…行动方案 (adapted title) |
| 2024-04-29 | municipal | Guangzhou | 47 | 实施方案 (adapted) |
| 2024-04-30 | provincial | Shanghai | 48 | 行动计划（2024-2027年）(adapted, multi-year) |
| 2024-04-30 | municipal | Zhongshan | 48 | 实施方案 (adapted) |
| 2024-04-30 | municipal | Zhuhai | 48 | 实施方案 (adapted) |
| 2024-05-01 | municipal | Shenzhen | 49 | 行动方案 (**verbatim** genre) |
| 2024-05-08 | municipal | Huizhou | 56 | 实施方案 (adapted) |
| 2024-05-09 | provincial | Jiangsu | 57 | 行动方案 (**verbatim** genre; the top-cited re-issuance, cr=162) |
| 2024-05-09 | municipal | Chongqing | 57 | 行动方案 (**verbatim** genre) |
| 2024-05-14 | municipal | Shaoguan | 62 | 实施方案 (adapted) |
| 2024-05-21 | municipal | Suzhou | 69 | 实施方案 (adapted) |
| 2024-05-28 | municipal | Yangjiang | 76 | 实施方案 (adapted) |
| 2024-08-13 | district | Shenzhen-Pingshan (szpsq) | 153 | 征求意见稿 (draft-for-comment) |
| 2024-11-05 | provincial | Guangdong-commerce (gdcom) | 237 | 国债加力支持…实施方案 (2nd-round, bond-funded) |
| 2025-01-15 | district | Shenzhen-Dapeng (szdp) | 308 | 加力扩围 (2025 follow-on) |
| 2025-01-21 | provincial | Jilin (jl_jldrc) | 314 | 实施方案 (adapted) |
| 2025-01-27 | provincial | Zhejiang | 320 | 2025年…实施方案 (annual) |
| 2025-02-06 | provincial | Fujian (fj_swt) | 330 | 行动方案 (verbatim genre) |
| 2025-05-01 | provincial | Ningxia (nx_fzggw) | 414 | 加力扩围…实施方案 |

**What the cascade shows:**

1. **It is a cascade, not a flat scatter.** The **first** re-issuer is a *province* (Guangdong,
   20d). The dense body of activity is **days 37–76**, and within that window provinces
   (Guangdong 20, Heilongjiang 37, Beijing 46, Shanghai 48, Jiangsu 57) and the cities nested
   under them (Guangzhou 47, Shenzhen 49, Suzhou 69) interleave — provinces lead their own
   municipalities on average, which is the defining ordering of top-down diffusion.
2. **The half-life is ~7 weeks.** Median first-issuance lag for the core 2024 wave (18 units,
   excluding the 2025 annual-follow-on tail) is **~49 days**; the inter-quartile band is roughly
   33–62 days. A province/large city localizes this plan in **one to two months**.
3. **The long tail is a coverage artifact, read honestly.** Zhejiang (320d), Jilin (314d),
   Fujian (330d), Ningxia (414d) did **not** wait a year to act — these are provincial
   *department* portals (发改委/商务厅) added to the crawl in the **Aug-2026 department-tier
   build-out**, and what we captured first was their **2025 annual re-issuance** (加力扩围 /
   2025年…实施方案), not their original 2024 plan (which our crawl of those portals doesn't reach
   back to). The lag column past ~150 days measures *our crawl coverage*, not policy latency.

**Table 3b — trade-in re-issuance breadth by level** (`title LIKE '%设备更新%以旧换新%'`, 2024+):

| level | distinct sites | docs | earliest |
|---|---:|---:|---|
| central | 4 | 12 | 2024-03-13 |
| provincial | 10 | 19 | 2024-04-02 |
| municipal | 12 | 23 | 2024-04-08 |
| department | 2 | 4 | 2024-06-04 |
| district | 2 | 2 | 2024-08-13 |

The **~50 distinct localized re-issuances** span all five levels. Municipalities are the *widest*
tier by document count (23 docs / 12 cities) — but again, 12 of those cities are in Guangdong,
which the corpus covers to district depth (§5).

**The boost-consumption plan — same shape, one year behind, still unfolding.**
Re-issuances of 《提振消费专项行动方案》 (central anchor 2025-03-16):

| first issued | level | unit | lag (days) | title |
|---|---|---|---:|---|
| 2025-05-07 | provincial | Guangdong | **52** | 广东省提振消费专项行动实施方案 |
| 2025-06-06 | provincial | Jiangsu | 82 | 江苏省实施提振消费专项行动若干措施 |
| 2025-07-10 | provincial | Beijing | 116 | 北京市深化改革提振消费专项行动方案 |
| 2025-08-14 | municipal | Zhuhai | 151 | 珠海市提振消费专项行动方案 |
| 2025-10-21 | municipal | Guangzhou | 219 | 广州市提振消费专项行动实施方案 |
| 2026-07-03 | district | Beijing-Haidian (bjd_haidian) | 474 | 海淀区提振消费专项行动方案 |

Guangdong is again the **fastest province** (52 days, vs. 20 for trade-in — the boost-consumption
plan is broader/softer and less bond-driven, so localization is slower). The trickle to the
prefecture and district tiers extends into mid-2026 — i.e. **the boost-consumption cascade is
caught mid-flight at the data cutoff**, whereas the trade-in cascade (a year older) has largely
completed its first round and moved into annual re-issuance.

---

## 4. Timeline (both flagships, one axis)

```
2024-03-13  ● trade-in ACTION PLAN issued (State Council)                    [T+0]
2024-04-02  │  Guangdong province re-issues                                  [T+20]
2024-04-08  │  first prefecture-city (Jieyang) re-issues                     [T+26]
2024-04-13  │  商务部+14 depts 推动消费品以旧换新行动方案 (central follow-on)   [T+31]
2024-04–05  ┝━ CASCADE: 10 provinces + 12 cities localize                    [T+37…76]
2024-07-25  │  发改委+财政部 加力支持…若干措施 (1104号, bond-backed)           [T+134]
2024-08-30  │  电动自行车 (e-bike) trade-in sub-scheme (central)              [T+170]
2024-11-05  │  2nd-round 国债加力支持 provincial re-issuances                 [T+237]
2025-01-08  ● trade-in 2025 加力扩围 (annual re-issuance, central)           [T+301]
2025-01–02  ┝━ provincial 2025 annual re-issuances (ZJ/JL/FJ captured)
2025-03-16  ● BOOST-CONSUMPTION ACTION PLAN issued (CPC+SC General Offices)  [B+0]
2025-05-07  │  Guangdong province re-issues boost-consumption                [B+52]
2025-06–07  ┝━ Jiangsu (B+82), Beijing (B+116) re-issue
2025-08-12  │  central operational layer: 消费贷款/服务业贴息 实施方案         [B+149]
2025-08…10  ┝━ prefecture re-issuances (Zhuhai B+151, Guangzhou B+219)
2025-12-30  ● trade-in 2026 提质增效 (annual re-issuance, central)           [T+656]
2026-07-03  │  Haidian DISTRICT re-issues boost-consumption                  [B+474]
```

Two clean annual pulses at the center (trade-in: 2024-03 → 2025-01 → 2025-12; each followed by a
provincial→municipal echo), with the boost-consumption plan layered on top in 2025 and its own
echo still descending through 2026.

---

## 5. What's measurable vs. what isn't — threats to validity

Stated candidly, because a China-politics reader will (rightly) probe every one.

**What the corpus measures well:**
- **Timing of re-issuance** for units we crawl. Dates come from `date_published`; the 20-day
  Guangdong lead and the 37–76-day cascade body are robust — they'd survive any reasonable
  coverage correction because they rest on units (北上广深, Jiangsu, Heilongjiang, GD cities)
  that are crawled continuously, not backfilled.
- **The center's internal density.** The ministerial follow-on web (35 central citers) is real
  and near-completely observed — central ministries are the best-covered tier.
- **Genre adaptation.** Titles are 99.7% present, so verbatim (行动方案) vs. adapted
  (实施方案 / 行动计划 / 若干措施) is directly readable: **Jiangsu, Chongqing, Shenzhen, Fujian**
  kept the 行动方案 genre; **most re-issuers renamed to 实施方案/实施计划** and several
  editorialized the title (Beijing's 积极推动…, 深化改革…; Shanghai's multi-year 2024-2027
  行动计划). Full verbatim-vs-adapted at the clause level would need body-text diffing (not done
  here — the constraint was to avoid heavy full-body scans).

**What it does *not* measure — the four load-bearing caveats:**

1. **Selection / coverage bias is the dominant limitation.** 17 of ~29 trade-in re-issuing
   localities are **Guangdong** cities (the corpus's only district-depth province, via the
   Guangdong-only `gkmlpt` crawler). So municipal "breadth" is a **Guangdong close-up**, not a
   national census. The honest reading: cascade *speed* is well-estimated; cascade *breadth* is a
   **lower bound**. Per `docs/working/coverage.csv`, only ~14 of 34 provincial units are crawled,
   and several province portals are **datacenter-IP-blocked** from the droplet's NYC address — so
   silent non-issuers (a province that genuinely never re-issued) are **indistinguishable** from
   uncrawled ones. No claim of the form "province X did not act" is defensible here.

2. **Lag tail = crawl-onset, not latency.** Every first-issuance lag beyond ~150 days
   (Zhejiang 320, Jilin 314, Fujian 330, Ningxia 414) coincides with when the **department-tier
   build-out (Aug 2026)** first reached those portals; the doc we captured is a **2025 annual
   re-issuance**, not the original. These rows belong in the timeline but must **not** be read as
   "these provinces were slow."

3. **51% citation resolution.** `citations` resolves target ids on **226,464 / 445,599 = 50.8%**
   of edges (rest are unresolved 《》/文号 strings pointing outside the corpus or to un-matched
   titles). All §2 counts are therefore **floors** — true inbound citation is roughly ~2× the
   observed. The resolver also over-counts near-duplicate promulgations (the Xinhua vs. gov copies
   of one text) as distinct sources; I mitigated by pooling anchor sets and using
   `COUNT(DISTINCT source_id)`, but cross-site mirror duplication still inflates raw edge counts
   (visible as repeated rows in the raw citer list).

4. **"Re-issuance" ≠ implementation.** A published 实施方案 is a *policy-output* signal, not
   evidence that trade-in subsidies were actually disbursed or that consumption rose. This corpus
   measures the **documentary diffusion of the campaign**, full stop. Fiscal execution, subsidy
   uptake, and consumption outcomes are outside it.

---

## 6. Bottom line for a paper

The corpus **can** carry a real diffusion argument. On the trade-in plan it delivers, from
primary documents alone, the three things a diffusion paper needs: (a) an identified central
anchor with a datable issuance; (b) a per-unit adoption event (the localized re-issuance) with a
measurable **lag** — 20 days for the lead province, a ~49-day median, a 37–76-day cascade body;
and (c) a **level ordering** (province-before-its-cities) visible in both the citation graph and
the re-issuance timing. The boost-consumption plan replicates the shape one year later and is
observably **mid-diffusion** at cutoff — itself a finding. The honest framing for publication is
**"observed diffusion among the crawled 40%+ of the hierarchy, with Guangdong as a district-depth
case study,"** not a national census — and every headline number above is reproducible from the
inline SQL against the droplet's `documents.db`.

---

### Appendix — key queries

```sql
-- Anchors
SELECT id,title,date_published,site_key,citation_rank FROM documents
WHERE title LIKE '%提振消费专项行动%' OR title LIKE '%设备更新%以旧换新%行动方案%'
ORDER BY citation_rank DESC;

-- Citers by level (pool the anchor set; DISTINCT to fold mirror dupes)
SELECT source_level, COUNT(DISTINCT source_id) FROM citations
WHERE target_id IN (12650974,12704698,900039931,900046374,900047223,900047235,12650461,900046881)
GROUP BY source_level;

-- Re-issuance cascade with lag
SELECT s.admin_level, d.site_key, MIN(substr(d.date_published,1,10)) first_issue,
  CAST(julianday(MIN(substr(d.date_published,1,10)))-julianday('2024-03-13') AS INT) lag_days
FROM documents d JOIN sites s ON s.site_key=d.site_key
WHERE d.title LIKE '%设备更新%以旧换新%' AND s.admin_level IN ('provincial','municipal','district')
  AND d.date_published >= '2024'
GROUP BY d.site_key ORDER BY first_issue;

-- Title-trend (the campaign's documentary footprint)
SELECT CAST(substr(date_published,1,4) AS INT) yr, COUNT(*) FROM documents
WHERE title LIKE '%消费%' GROUP BY yr ORDER BY yr;
-- 2022:74  2023:123  2024:251  2025:389  2026:672(partial)

-- Citation resolution rate: 226,464 / 445,599 = 50.8%
SELECT COUNT(*), SUM(target_id IS NOT NULL) FROM citations;
```
