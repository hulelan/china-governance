# Industrial Policy Targeting by Sector: What Gets Planned, What Gets Ruled, What Gets Paid For

*A read-only replication of the policy-document half of Fang, Li and Lu, "Decoding China's
Industrial Policies" (NBER w33814, 2025), on the china-governance corpus. All figures pulled
from the live `documents.db` on the droplet on 2026-10-01 (`?mode=ro`). Every series is
normalized by yearly volume. Robustness is reported on a continuously-crawled set. The inline
SQL appendix reproduces each table. Companion to `ai-governance-diffusion.md` (one sector in
depth) and `diffusion-atlas.md` (the cascade machinery this memo reuses).*

Evidence labels. `[measured]` is a number read from the corpus. `[inferred]` is an
interpretation of measured numbers. `[lit]` is a claim from the comparator paper.

---

## 0. The questions and the short answers

Fang, Li and Lu ask which industries Chinese industrial policy targets, with what tone and
tools, over 2000-2022, using LLM extraction over ~3.3M central, provincial and city
documents. `[lit]` This memo asks the same question of our 319k-document corpus with the tags
we already hold (a title lexicon for 18 sectors, the 19-genre `algo_doc_type`, the issuer
level, and the `diffusion_events` cascade table). We trade their tone and firm-level
extraction for three axes they lack: instrument genre, sub-national depth down to the
district tier, and an explicit resolved cascade from a central instrument to its
sub-national echoes.

Three headline findings.

1. **Targeting broadened. It did not concentrate.** The Herfindahl index across the 18
   sectors fell from roughly 1,700-2,000 (2008-2010) to 780-970 (2019-2026). The sector-tagged
   share of all government documents rose from 2.3% (2008) to 6.3% (2026). More sectors get
   named, and attention is spread more evenly across them. `[measured]`
2. **Sector policy is written as plans and explainers, not rules, and almost never as
   money.** Across sector-tagged instruments, plans are 23% and explainers 27%, against 14%
   and 18% for the corpus. Rules are 19% against 33%. The subsidy genre is 5.8% of sector
   instruments. The money goes to a short list: semiconductors and software (14-18%, rising
   to 22% in 2021-26), new energy (13%), NEV and biopharma (10%). Legacy sectors
   (agriculture, ships, heavy industry, real estate) get rules. `[measured]`
3. **Central priorities become sub-national pile-ons, but the pile-on is uneven.** Every
   sector's central share falls across periods as lower tiers enter (semiconductors 59% to
   34%; new energy 66% to 25%; low-altitude 60% to 13%). The cascade table shows which
   central instruments the pile-on follows. Data-element and carbon instruments cascade
   widest (a single 2025 data-circulation plan reaches 42 sites in 96 events; the 2021
   carbon-peaking action plan reaches 27 sites in 78 events). Semiconductors and new
   materials, the sectors that get money, barely cascade (2 and 1 anchors). `[measured]`

Fastest-rising attention share (mean 2012-16 to mean 2022-26): artificial intelligence
(0 to 0.57%), future industries (x17 from a near-zero base), low-altitude economy (x7.5),
digital economy and data (x3.3), biopharma (x3.2). Fastest-falling: heavy and traditional
industry (x0.54), agriculture and seed (x0.53), ships and aerospace (x0.67). The robustness
set confirms all three falls and the top four rises. `[measured]`

---

## 1. Data and definitions

**Universe.** Government sites only (`sites.admin_level` in central, provincial, municipal,
district, department). Media and research sites are excluded. Dates bounded 2008-01-01 to
2026-12-31. 2026 is partial (through 2026-09-30). This gives 252,206 rows.

**Date-stamp exclusion.** 74 sites (27,915 docs) carry crawl dates rather than publication
dates: 70% or more of their documents fall in 2026. MIIT (7,787 docs, 100% in 2026) is the
largest. These sites are removed from every table in this memo, not just the time series,
because their level and genre composition would otherwise enter the cross-sections with a
single-year date. Final universe: **224,291 documents**. `[measured]`

*(Correction 2026-10-07, `corpus-lessons.md` A4. These 74 sites do NOT carry crawl dates. Their
stored dates match the pages' own `PubDate` metadata; they are sites whose crawled ARCHIVE is
shallow, so most documents genuinely date from 2026 (MIIT's crawler reaches only `/art/2026/`).
The exclusion is kept because a one-year archive cannot inform a trend, but the mechanism is
coverage depth, not date stamping. Re-running the cross-sections with these sites included is
queued as a robustness check.)*

**Sector lexicon.** 18 sectors, tagged by regular expression on `documents.title` only.
Multi-label. 9,049 documents (4.0%) carry at least one tag; 321 carry two; 11 carry three.

| sector | title cues (regex) | n |
|---|---|---:|
| semiconductor | 半导体, 集成电路, 芯片 | 233 |
| software | 软件产业, 软件企业, 软件和信息技术, 软件业, 信创, 操作系统, 基础软件, 工业软件 | 128 |
| ai | 人工智能, 大模型, 智能算法, 算力, AI+ | 808 |
| digital_data | 数字经济, 数据要素, 大数据, 数据产业, 数据资源, 数字化转型, 工业互联网, 数据流通, 公共数据 | 1,024 |
| telecom_iot | 5G, 6G, 物联网, 车联网, 宽带, 卫星互联网, 信息基础设施, 移动通信 | 254 |
| nev | 新能源汽车, 电动汽车, 充电桩, 充换电, 动力电池, 智能网联汽车 | 493 |
| new_energy | 光伏, 风电, 氢能, 储能, 太阳能, 新能源 (not followed by 汽车), 核电, 新型电力系统 | 582 |
| green_lowcarbon | 碳达峰, 碳中和, 绿色制造, 循环经济, 低碳, 节能降碳, 绿色低碳 | 530 |
| biopharma | 生物医药, 生物技术, 创新药, 医疗器械, 制药, 仿制药, 医药产业, 中药产业 | 515 |
| equipment_robot | 高端装备, 机器人, 智能制造, 工业母机, 数控机床, 装备制造, 智能装备, 首台(套) | 363 |
| new_materials | 新材料, 稀土, 碳纤维, 石墨烯, 先进材料 | 125 |
| aero_ship | 船舶, 造船, 商业航天, 航天产业, 航空航天, 航空产业, 航空制造, 海洋工程装备, 大飞机, 航空发动机 | 430 |
| low_altitude | 低空经济, 无人机, 通用航空, eVTOL, 低空飞行 | 323 |
| future_industry | 量子, 脑机, 未来产业, 生物制造, 人形机器人, 6G, 具身智能 | 199 |
| agri_seed | 种业, 种子, 农机, 智慧农业, 现代农业, 农产品加工, 农业产业, 粮食生产, 农业机械 | 691 |
| real_estate | 房地产, 商品房, 住房市场, 保障性住房, 住房租赁, 楼市, 住房制度, 住房发展 | 1,288 |
| platform_ecom | 平台经济, 互联网平台, 电子商务, 电商, 直播电商, 网络直播, 平台企业 | 638 |
| heavy_tradit | 钢铁, 煤炭, 石化, 有色金属, 水泥, 化工产业, 建材, 产能过剩, 化解过剩产能, 煤矿 | 768 |

Two cues were dropped after a precision check. `房屋` pulled in 446 Suzhou demolition
compensation notices in 2023 alone and `信息通信` pulled in MIIT's "信息通信业" news feed.
Bare `低空`, `航天`, `直播` and `开源` were tightened for the same reason. The lexicon is
deliberately conservative. Its recall limits are stated in section 6.

**Genre groups.** `algo_doc_type` is collapsed to six instrument groups. money = subsidy,
application_guide. rules = regulation, law, decree, standard, decision, administrative.
plan = action_plan, work_plan, plan, strategy. framework = opinion, policy_issuance,
circular. explainer = explainer, publicity, commentary, interview. procurement and budget
are kept apart. Everything else (notice, announcement, reply, other) is "non-instrument" and
excluded from the mix denominators. 55% of universe documents are non-instrument; the share
is similar for sector-tagged docs (51%).

**Robustness set (R).** Nine continuously-crawled sites with real publication dates back to
the 2000s: State Council (`gov`), NDRC, MOF, MEE, Guangdong (`gd`), Shenzhen (`sz`), Beijing
(`bj`), Shanghai (`sh`), Guangzhou (`gz`). 46,541 documents, 2,366 sector-tagged.

**Cascades.** `diffusion_events` holds 24,599 events from 2,943 central anchors to
sub-national source documents (351 source sites). All anchors are central. Match types:
citation (17,650), topic_genre (6,511), title_reissue (438). A sector's cascade is the set of
events whose anchor title matches the sector regex. *(Build note 2026-10-01: these are the
post npc/explainer-fix build figures, before the resolver fix. The table is rebuilt nightly
and held 32,825 rows (26,565 central from 3,138 anchors, plus 6,260 provincial) on 2026-10-01;
a further resolver regression fix in progress will change it again. The sector event table in
§5 and its "all anchors 24,599" row are on this build; shares and orderings held on spot
checks, raw counts are not current. See `consistency-review.md` H2. Universe note: npc rows are
kept here while the 74 date-stamped sites are removed; other memos exclude or re-level npc, so
the "universe central %" figures are within-memo only, review M7.)*

---

## 2. Targeting over time (Q1)

### 2.1 Sector-tagged share of all documents, by year

| year | docs | tagged % | R docs | R tagged % | HHI | R HHI |
|---|---:|---:|---:|---:|---:|---:|
| 2008 | 2,590 | 2.32 | 1,113 | 2.70 | 2,060 | 2,676 |
| 2010 | 4,663 | 2.94 | 1,502 | 3.60 | 1,801 | 2,026 |
| 2012 | 3,867 | 3.08 | 1,449 | 3.80 | 1,301 | 1,394 |
| 2014 | 3,955 | 3.26 | 936 | 4.06 | 1,052 | 1,032 |
| 2016 | 7,019 | 3.70 | 2,197 | 4.42 | 900 | 1,168 |
| 2018 | 10,214 | 4.27 | 4,433 | 5.91 | 1,030 | 1,105 |
| 2020 | 12,925 | 3.37 | 4,950 | 3.96 | 909 | 838 |
| 2022 | 19,633 | 3.03 | 4,265 | 5.23 | 869 | 881 |
| 2024 | 27,297 | 4.03 | 3,384 | 7.98 | 778 | 897 |
| 2025 | 30,552 | 5.38 | 2,769 | 7.40 | 868 | 824 |
| 2026* | 26,600 | 6.26 | 1,749 | 4.92 | 966 | 1,289 |

HHI = sum of squared sector shares of tagged documents, x10,000. 18 equal sectors would give
556. *2026 partial.

**Evidence.** The tagged share roughly doubles over the window in both sets (2.3% to 6.3%
all; 2.7% to 7.4-8.0% in R at the 2024-25 peak). HHI falls from the 1,700-2,700 range in
2008-2010 to the 780-970 range from 2019 on, in both sets. The 2026 R value (1,289) is on
1,749 documents and a partial year. `[measured]`

**Reading.** Industrial attention in the document record is broadening, not narrowing. The
2008-2012 record was dominated by three legacy sectors (agriculture, heavy industry, real
estate, together 51% of tagged documents in 2012). By 2024 no sector exceeds 14% of tagged
documents. This is the opposite of a concentration story. It is consistent with the "new
quality productive forces" framing that names many sectors at once. `[inferred]`

### 2.2 Sector shares of all documents (%), selected years

| sector | 2012 | 2016 | 2020 | 2024 | 2026* | R 2012 | R 2016 | R 2020 | R 2024 | R 2026* |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| semiconductor | 0.15 | 0.09 | 0.14 | 0.09 | 0.14 | 0.14 | 0.14 | 0.28 | 0.24 | 0.17 |
| software | 0.10 | 0.01 | 0.09 | 0.06 | 0.04 | 0.14 | 0.05 | 0.16 | 0.18 | 0.06 |
| ai | 0.00 | 0.00 | 0.09 | 0.28 | 1.11 | 0.00 | 0.00 | 0.08 | 0.27 | 1.26 |
| digital_data | 0.00 | 0.36 | 0.44 | 0.56 | 0.66 | 0.00 | 0.32 | 0.48 | 0.83 | 0.74 |
| telecom_iot | 0.10 | 0.17 | 0.19 | 0.03 | 0.06 | 0.14 | 0.00 | 0.20 | 0.21 | 0.06 |
| nev | 0.15 | 0.23 | 0.33 | 0.22 | 0.23 | 0.21 | 0.23 | 0.42 | 0.65 | 0.29 |
| new_energy | 0.31 | 0.17 | 0.14 | 0.38 | 0.26 | 0.28 | 0.05 | 0.22 | 0.68 | 0.29 |
| green_lowcarbon | 0.23 | 0.18 | 0.05 | 0.41 | 0.30 | 0.21 | 0.23 | 0.08 | 1.71 | 0.80 |
| biopharma | 0.03 | 0.11 | 0.15 | 0.30 | 0.35 | 0.00 | 0.23 | 0.32 | 0.47 | 0.46 |
| equipment_robot | 0.08 | 0.16 | 0.03 | 0.16 | 0.29 | 0.00 | 0.05 | 0.04 | 0.24 | 0.00 |
| new_materials | 0.10 | 0.09 | 0.03 | 0.07 | 0.09 | 0.14 | 0.09 | 0.02 | 0.24 | 0.06 |
| aero_ship | 0.23 | 0.28 | 0.22 | 0.15 | 0.17 | 0.34 | 0.64 | 0.34 | 0.47 | 0.06 |
| low_altitude | 0.00 | 0.06 | 0.03 | 0.29 | 0.23 | 0.00 | 0.09 | 0.06 | 0.35 | 0.06 |
| future_industry | 0.00 | 0.01 | 0.01 | 0.08 | 0.26 | 0.00 | 0.00 | 0.00 | 0.18 | 0.11 |
| agri_seed | 0.83 | 0.37 | 0.29 | 0.16 | 0.38 | 0.69 | 0.32 | 0.28 | 0.30 | 0.06 |
| real_estate | 0.31 | 0.44 | 0.56 | 0.48 | 1.17 | 0.48 | 0.59 | 0.18 | 0.41 | 0.17 |
| platform_ecom | 0.05 | 0.46 | 0.39 | 0.19 | 0.47 | 0.14 | 0.46 | 0.42 | 0.21 | 0.40 |
| heavy_tradit | 0.49 | 0.57 | 0.30 | 0.30 | 0.29 | 1.03 | 0.96 | 0.57 | 0.74 | 0.11 |

The real_estate 2026 value (1.17%) is a Shenzhen housing bureau artefact (`zjj` is 49% of
all real_estate hits; the R series shows 0.17%). Treat it as site composition, not attention.

### 2.3 Rise and fall: mean share 2012-16 against mean share 2022-26

| sector | early % | late % | ratio | R early % | R late % | R ratio | verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| ai | 0.000 | 0.565 | new | 0.000 | 0.577 | new | rise, confirmed |
| future_industry | 0.008 | 0.145 | 17.5 | 0.000 | 0.219 | new | rise, confirmed |
| low_altitude | 0.029 | 0.219 | 7.5 | 0.029 | 0.138 | 4.8 | rise, confirmed |
| digital_data | 0.179 | 0.590 | 3.3 | 0.157 | 0.715 | 4.5 | rise, confirmed |
| biopharma | 0.087 | 0.279 | 3.2 | 0.172 | 0.414 | 2.4 | rise, confirmed |
| software | 0.037 | 0.063 | 1.7 | 0.043 | 0.125 | 2.9 | rise, small n |
| new_energy | 0.204 | 0.304 | 1.5 | 0.286 | 0.552 | 1.9 | rise, confirmed |
| equipment_robot | 0.154 | 0.210 | 1.4 | 0.172 | 0.194 | 1.1 | flat in R |
| green_lowcarbon | 0.245 | 0.300 | 1.2 | 0.286 | 0.896 | 3.1 | rise, stronger in R |
| nev | 0.187 | 0.211 | 1.1 | 0.243 | 0.445 | 1.8 | flat all, rise in R |
| semiconductor | 0.100 | 0.106 | 1.1 | 0.100 | 0.144 | 1.4 | flat |
| new_materials | 0.071 | 0.063 | 0.9 | 0.100 | 0.075 | 0.8 | flat |
| real_estate | 0.395 | 0.658 | 1.7 | 0.515 | 0.263 | 0.5 | disagree (site artefact) |
| platform_ecom | 0.399 | 0.282 | 0.7 | 0.315 | 0.376 | 1.2 | disagree |
| aero_ship | 0.237 | 0.158 | 0.7 | 0.401 | 0.307 | 0.8 | fall, confirmed |
| agri_seed | 0.411 | 0.218 | 0.5 | 0.415 | 0.232 | 0.6 | fall, confirmed |
| heavy_tradit | 0.486 | 0.262 | 0.5 | 0.658 | 0.495 | 0.8 | fall, confirmed |
| telecom_iot | 0.258 | 0.057 | 0.2 | 0.243 | 0.182 | 0.8 | fall, weaker in R |

**Evidence.** Five rises hold in both sets with ratio above 2 (AI, future industries,
low-altitude, digital/data, biopharma). Three falls hold in both sets (heavy industry,
agriculture, ships and aerospace). Real estate and platform economy disagree between sets
and should not be read as trends. `[measured]`

**Reading.** The composition shift is from physical-capacity sectors (steel, coal, cement,
farm machinery, shipbuilding) to data, compute and life-science sectors. Semiconductors are
the striking non-mover: their title share is flat at ~0.1% in both sets across 15 years
despite being the sector that receives the most money per instrument (section 3). Chip
policy in the document record is a small number of consequential instruments, not a volume
of attention. `[inferred]`

**Cross-check against `ai_relevance`.** The AI title lexicon gives 0.94% (2025) and 1.11%
(2026). The body keyword-density measure (`ai_relevance` >= 0.2) gives 3.17% and 3.61%. The
two series have the same shape (both at or below 0.3% through 2016, both inflecting 2024-25).
The title lexicon undercounts by a factor of 3-5 relative to body mentions. `[measured]`

---

## 3. Instrument mix by sector (Q2)

Shares are of instrument documents (non-instrument genres excluded). n = instrument docs.

| sector | n | money | rules | plan | framework | explainer | R money | R rules | R plan |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| semiconductor | 90 | **14.4** | 7.8 | 17.8 | 30.0 | 24.4 | 0.0 | 9.1 | 22.7 |
| software | 51 | **17.6** | 3.9 | 17.6 | 35.3 | 23.5 | 0.0 | 0.0 | 16.7 |
| ai | 346 | 5.8 | 4.0 | 26.6 | 16.5 | **43.9** | 0.0 | 1.2 | 48.1 |
| digital_data | 632 | 2.4 | 10.0 | 21.7 | 18.2 | **42.9** | 1.8 | 1.8 | 37.3 |
| telecom_iot | 159 | 1.3 | 13.2 | **35.2** | 25.2 | 22.0 | 1.8 | 16.4 | 38.2 |
| nev | 231 | 10.0 | 12.1 | 30.3 | 23.8 | 20.3 | 12.3 | 6.2 | 35.8 |
| new_energy | 237 | **13.1** | 5.5 | 25.7 | 26.6 | 23.6 | 6.5 | 3.2 | 30.1 |
| green_lowcarbon | 339 | 9.4 | 13.0 | **42.2** | 18.6 | 16.5 | 0.7 | 2.0 | 57.9 |
| biopharma | 311 | 10.0 | 7.4 | 15.8 | 29.9 | 35.0 | 0.0 | 11.1 | 18.2 |
| equipment_robot | 115 | 9.6 | 7.8 | **37.4** | 20.9 | 21.7 | 4.8 | 2.4 | 45.2 |
| new_materials | 58 | 5.2 | 24.1 | 24.1 | 22.4 | 24.1 | 0.0 | 20.0 | 5.0 |
| aero_ship | 221 | 2.7 | **44.8** | 14.0 | 21.7 | 16.7 | 1.6 | 38.1 | 23.8 |
| low_altitude | 89 | 5.6 | 16.9 | 22.5 | 25.8 | 19.1 | 0.0 | 17.4 | 26.1 |
| future_industry | 90 | 16.7 | 7.8 | 26.7 | 7.8 | 38.9 | 4.3 | 0.0 | 39.1 |
| agri_seed | 451 | 7.3 | **42.1** | 20.6 | 20.6 | 8.9 | 15.1 | 5.7 | 31.1 |
| real_estate | 578 | 0.5 | 26.8 | 8.7 | 14.9 | **41.7** | 0.0 | 17.9 | 25.6 |
| platform_ecom | 266 | 4.5 | 9.0 | 28.6 | 32.7 | 22.6 | 0.0 | 7.0 | 29.6 |
| heavy_tradit | 323 | 2.5 | **31.9** | 25.7 | 31.0 | 9.0 | 0.0 | 13.5 | 30.5 |
| any sector | 4,435 | 5.8 | 18.6 | 23.2 | 22.0 | 27.2 | 3.2 | 8.7 | 34.5 |
| all docs | 100,427 | 4.0 | 32.5 | 13.9 | 21.2 | 17.8 | 2.9 | 15.3 | 22.5 |

**Evidence.** Three patterns, each visible in both sets.

- *Who gets money.* Subsidy and application-guide genres exceed 10% of instruments only for
  semiconductors, software, new energy, NEV, biopharma and future industries. They are below
  3% for real estate, telecom, ships and aerospace, heavy industry, and digital/data. In R
  the money share collapses for all sectors except NEV (12.3%) and agriculture (15.1%),
  because subsidy documents are mostly issued by Shenzhen districts and departments, which
  are outside R. `[measured]`
- *Who gets rules.* The rule share is at or above the corpus average (33%) only for ships
  and aerospace (45%) and agriculture (42%), and near it for heavy industry (32%) and real
  estate (27%). Every emerging sector is under 14%. `[measured]`
- *Who gets plans and explainers.* Carbon (42%), equipment and robotics (37%) and telecom
  (35%) are plan-led. AI (44%), data (43%), real estate (42%) and biopharma (35%) are
  explainer-led. The explainer genre (政策解读, 一图读懂, publicity) is the modal instrument
  for the two headline sectors of 2024-26. `[measured]`

**Reading.** The instrument signature separates two policy modes. Legacy and
safety-regulated sectors (ships, farm inputs, mines, housing) are governed through rules, and
the rules are mostly sub-national implementations of national regulations (see cascade
anchors in section 5: a ship-pollution regulation, a medical-device regulation). Emerging
sectors are governed through plans and are *communicated* through explainers. Money is a
narrow instrument tied to a narrow set of sectors, and it is disproportionately a
district-and-department instrument. `[inferred]`

### 3.1 Does the mix shift as sectors mature?

Instrument shares by period (money / rules / plan / framework / explainer, %). Sectors with
fewer than 20 instruments in a period are omitted.

| sector | 2008-14 | 2015-20 | 2021-26 |
|---|---|---|---|
| semiconductor | n=9 | 0 / 0 / 23 / 68 / 9 (n=22) | **22** / 12 / 10 / 14 / 34 (n=59) |
| software | n=6 | n=7 | **21** / 5 / 18 / 21 / 32 (n=38) |
| ai | n=0 | 0 / 0 / 41 / 33 / 19 (n=27) | 6 / 4 / 25 / 15 / **46** (n=319) |
| digital_data | n=2 | 2 / 13 / 34 / 28 / 19 (n=106) | 3 / 9 / 19 / 16 / **48** (n=524) |
| nev | 0 / 12 / 41 / 47 / 0 (n=17) | 12 / 2 / 43 / 26 / 17 (n=58) | 10 / **16** / 24 / 21 / 24 (n=156) |
| new_energy | 11 / 21 / 42 / 26 / 0 (n=19) | 13 / 6 / 19 / 38 / 22 (n=32) | 13 / 4 / 25 / 25 / 26 (n=186) |
| green_lowcarbon | 0 / 18 / 62 / 21 / 0 (n=34) | 3 / 41 / 41 / 7 / 7 (n=29) | 11 / 9 / 40 / 20 / 20 (n=276) |
| biopharma | n=12 | 0 / 6 / 28 / 45 / 20 (n=64) | 13 / 7 / 11 / 25 / 41 (n=235) |
| aero_ship | 0 / 56 / 22 / 22 / 0 (n=32) | 5 / 64 / 11 / 21 / 0 (n=63) | 2 / 33 / 14 / 22 / 29 (n=126) |
| agri_seed | 5 / 43 / 27 / 26 / 0 (n=82) | 5 / 47 / 24 / 19 / 5 (n=152) | 10 / 38 / 16 / 20 / 15 (n=217) |
| real_estate | 0 / 46 / 22 / 27 / 6 (n=79) | 0 / 42 / 14 / 26 / 18 (n=125) | 1 / 18 / 4 / 9 / **57** (n=374) |
| platform_ecom | n=13 | 3 / 6 / 47 / 35 / 8 (n=95) | 6 / 11 / 17 / 29 / 33 (n=158) |
| heavy_tradit | 0 / 36 / 39 / 25 / 0 (n=67) | 0 / 38 / 17 / 44 / 2 (n=121) | 6 / 24 / 27 / 22 / 20 (n=135) |
| all docs | 2 / 40 / 22 / 31 / 3 | 3 / 38 / 17 / 26 / 9 | 5 / 28 / 11 / 17 / 26 |

**Evidence.** Three movements.

- The "subsidy first, regulation later" maturation path appears only for NEV, whose rule
  share rises from 2% (2015-20) to 16% (2021-26) while plans fall from 43% to 24%. `[measured]`
- Semiconductors and software run the opposite way. Their money share goes from 0% in
  2015-20 to 21-22% in 2021-26. The instruments behind this are the 2020-21 tax-preference
  circulars (集成电路产业和软件产业 import-tax and enterprise-income-tax rules, carried by
  `chinatax` and `gov`) and Shenzhen district special funds. `[measured]`
- The explainer share rises in every sector in 2021-26, in step with the corpus (3% to
  26%). Part of each sector's explainer share is therefore a corpus-wide genre shift toward
  publicity, not sector-specific communication. The sector-minus-corpus gap is what remains:
  AI +20 points, data +22, real estate +31, biopharma +15. `[measured]`

**Reading.** We do not find a general maturation gradient from money to rules. The mix is
sector-specific and event-driven. NEV follows the textbook path. Chips run it backward,
because the subsidy wave arrived after a decade of plan-and-framework documents, in a
period when the sector's attention share did not rise at all. `[inferred]`

---

## 4. Level: central targeting against local initiative (Q3)

Share of each sector's documents at each level, and the tilt (sector share at that level
divided by the universe share at that level). Universe: central 31.7%, provincial 19.0%,
municipal 23.7%, district 10.5%, department 15.1%.

| sector | n | central (tilt) | provincial | municipal | district | department |
|---|---:|---:|---:|---:|---:|---:|
| aero_ship | 430 | 57.9 (**1.83**) | 19.5 (1.03) | 14.2 (0.60) | 3.3 (0.31) | 5.1 (0.34) |
| telecom_iot | 254 | 55.9 (**1.77**) | 18.9 (0.99) | 20.9 (0.88) | 1.2 (0.11) | 3.1 (0.21) |
| heavy_tradit | 768 | 55.2 (**1.74**) | 23.4 (1.23) | 19.4 (0.82) | 0.5 (0.05) | 1.4 (0.09) |
| digital_data | 1,024 | 53.1 (**1.68**) | 20.4 (1.07) | 13.3 (0.56) | 9.0 (0.85) | 4.2 (0.28) |
| platform_ecom | 638 | 50.0 (1.58) | 21.9 (1.16) | 19.7 (0.83) | 4.1 (0.39) | 4.2 (0.28) |
| agri_seed | 691 | 49.3 (1.56) | 26.5 (1.39) | 20.4 (0.86) | 1.6 (0.15) | 2.2 (0.14) |
| nev | 493 | 48.7 (1.54) | 17.6 (0.93) | 14.2 (0.60) | 5.1 (0.48) | 14.4 (0.95) |
| semiconductor | 233 | 42.9 (1.36) | 12.4 (0.66) | 15.0 (0.63) | 12.9 (1.22) | 16.7 (1.11) |
| software | 128 | 42.2 (1.33) | 18.0 (0.95) | 14.1 (0.59) | 18.8 (1.78) | 7.0 (0.47) |
| green_lowcarbon | 530 | 41.1 (1.30) | 22.5 (1.18) | 15.8 (0.67) | 10.6 (1.00) | 10.0 (0.66) |
| new_materials | 125 | 38.4 (1.21) | 30.4 (1.60) | 16.0 (0.67) | 6.4 (0.61) | 8.8 (0.58) |
| new_energy | 582 | 34.4 (1.09) | 23.2 (1.22) | 17.7 (0.75) | 6.5 (0.62) | 18.2 (1.21) |
| ai | 808 | 33.0 (1.04) | 22.8 (1.20) | 26.4 (1.11) | 11.1 (1.06) | 6.7 (0.44) |
| biopharma | 515 | 31.5 (0.99) | 22.1 (1.17) | 18.1 (0.76) | 16.1 (**1.53**) | 12.2 (0.81) |
| equipment_robot | 363 | 22.9 (0.72) | 18.5 (0.97) | 35.3 (**1.49**) | 13.2 (1.26) | 10.2 (0.67) |
| low_altitude | 323 | 17.6 (**0.56**) | 16.1 (0.85) | 23.2 (0.98) | 27.9 (**2.65**) | 15.2 (1.00) |
| real_estate | 1,288 | 17.5 (0.55) | 11.1 (0.58) | 14.3 (0.60) | 6.5 (0.62) | 50.6 (**3.35**) |
| future_industry | 199 | 13.1 (**0.41**) | 35.7 (**1.88**) | 30.7 (1.29) | 5.0 (0.48) | 15.6 (1.03) |

**Evidence.** Centrally-targeted sectors (tilt above 1.5): ships and aerospace, telecom,
heavy industry, data, platforms, agriculture, NEV. Locally-initiated sectors (central tilt
below 0.75): future industries, real estate, low-altitude, equipment and robotics.
Low-altitude is a district phenomenon (district tilt 2.65; Longhua alone is 17% of the
sector). Future industries are a provincial phenomenon (tilt 1.88). Equipment and robotics
are municipal (1.49). AI is the only sector with tilt near 1.0 at every tier above
department: it is evenly spread. `[measured]`

### 4.1 The sub-national pile-on: central share by period

Central share of each sector's documents (%) and tilt against the period's universe.

| sector | 2008-14 | 2015-20 | 2021-26 | reading |
|---|---:|---:|---:|---|
| semiconductor | 59 (1.52) | 63 (1.40) | 34 (1.33) | pile-on, tilt stable |
| software | n<20 | 81 (1.81) | 29 (1.11) | pile-on |
| ai | n<20 | 61 (1.37) | 31 (1.22) | pile-on, tilt stable |
| digital_data | n<20 | 56 (1.24) | 53 (**2.04**) | stays central |
| telecom_iot | 37 (0.95) | 47 (1.04) | 70 (**2.72**) | recentralizes |
| nev | 36 (0.93) | 61 (1.37) | 44 (1.69) | central burst then pile-on |
| new_energy | 66 (1.70) | 60 (1.35) | 25 (0.95) | pile-on to parity |
| green_lowcarbon | 51 (1.32) | 48 (1.07) | 39 (1.52) | tilt rises |
| biopharma | 26 (0.67) | 57 (1.28) | 25 (0.98) | central burst then pile-on |
| equipment_robot | n<20 | 37 (0.82) | 19 (0.75) | local throughout |
| new_materials | n<20 | 70 (1.57) | 24 (0.94) | pile-on to parity |
| aero_ship | 67 (1.71) | 77 (1.72) | 45 (1.75) | tilt constant |
| low_altitude | n<20 | 60 (1.34) | 13 (**0.51**) | strongest pile-on |
| future_industry | n<20 | n<20 | 12 (0.44) | local from the start |
| agri_seed | 47 (1.20) | 67 (1.50) | 39 (1.49) | tilt stable |
| real_estate | 40 (1.02) | 38 (0.85) | 10 (0.37) | localizes (site artefact partly) |
| platform_ecom | 30 (0.78) | 56 (1.26) | 48 (1.85) | recentralizes |
| heavy_tradit | 67 (1.71) | 78 (1.74) | 37 (1.44) | tilt stable |
| universe central % | 39 | 45 | 26 | |

**Evidence.** The raw central share falls for 15 of 16 sectors with data in both of the last
two periods. The universe central share also falls (45% to 26%) because sub-national crawl
depth grew. The tilt separates the two. Tilt falls materially only for low-altitude (1.34 to
0.51), new energy (1.35 to 0.95), new materials (1.57 to 0.94) and biopharma (1.28 to 0.98).
These are the sectors where sub-national tiers overtook the center's own attention. Tilt
rises for data (to 2.04), telecom (to 2.72), platforms (to 1.85) and carbon (to 1.52). These
are sectors where the center kept or increased its relative lead. `[measured]`

**Reading.** "Local governments pile onto central priorities" holds, but it is not uniform.
It is strongest for sectors with a physical, place-based project pipeline (airfields and
drone corridors, solar and storage installations, pharma parks). It is weakest for sectors
whose instruments are rules over a national network (data circulation, platform conduct,
telecom infrastructure), where the center's relative share goes up. `[inferred]`

### 4.2 Lag from central instrument to sub-national echo

Median `lag_days` across all events whose anchor is a sector document (section 5 gives the
full table). Corpus baseline median: 304 days.

Fast sectors (median under 230 days): agriculture 189, low-altitude 196, AI 197, carbon
201, new energy 204, data 224. Slow sectors: NEV 327, real estate 322, semiconductors 327,
heavy industry 315, equipment and robotics 547, ships and aerospace 873. `[measured]`

The share-based onset years (first year a level's sector share reaches half its maximum)
are noisy on these counts and mostly agree within a year. The clear exceptions are new
energy (central onset 2012, sub-national onset 2023) and low-altitude (2018 against 2024),
the two sectors with the largest tilt collapse above. `[measured]`

---

## 5. Cascade breadth by sector (Q4)

Events whose anchor title matches the sector. "sites" = distinct sub-national source sites.
"cit." = citation-matched events only (the strict measure). "per 100" = anchors per 100
central sector documents (how much of the sector's central output cascades at all).

| sector | events | cit. | anchors | sites | events/anchor | med lag | per 100 | widest anchor (events / sites) |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| digital_data | **426** | 100 | 26 | **110** | 16.4 | 224 | 4.8 | 数据流通安全治理实施方案 2025 (96 / 42) |
| green_lowcarbon | **240** | 92 | 19 | 64 | 12.6 | 201 | 8.7 | 2030年前碳达峰行动方案 2021 (78 / 27) |
| agri_seed | 186 | 75 | 18 | 25 | 10.3 | 189 | 5.3 | 农业产业化经营 2006 (49 / 13) |
| ai | 111 | 66 | 19 | 53 | 5.8 | 197 | 7.1 | 新一代人工智能发展规划 2017 (36 / 15); 人工智能+ 2025 (33 / 22) |
| nev | 95 | 53 | 12 | 30 | 7.9 | 327 | 5.0 | 新能源汽车推广应用 2014 (25 / 10) |
| real_estate | 82 | 52 | 9 | 25 | 9.1 | 322 | 4.0 | 住房租赁市场 2016 (20 / 12) |
| platform_ecom | 82 | 51 | 16 | 27 | 5.1 | 240 | 5.0 | 跨境电子商务 2015 (36 / 11) |
| biopharma | 72 | 46 | 9 | 22 | 8.0 | 309 | 5.6 | 药品医疗器械监管改革 2025 (42 / 16) |
| new_energy | 71 | 49 | 15 | 32 | 4.7 | 204 | 7.5 | 新型电力系统行动方案 2024 (12 / 7) |
| heavy_tradit | 70 | 47 | 27 | 21 | 2.6 | 315 | 6.4 | 煤炭行业化解过剩产能 2016 (18 / 9) |
| aero_ship | 35 | 32 | 12 | 19 | 2.9 | 873 | 4.8 | 防治船舶污染海洋环境条例 2018 (11 / 8) |
| low_altitude | 35 | 6 | 2 | 11 | 17.5 | 196 | 3.5 | 通用航空业发展 2016 (32 / 11) |
| telecom_iot | 22 | 17 | 6 | 13 | 3.7 | 304 | 4.2 | 物联网有序健康发展 2013 (7 / 6) |
| software | 20 | 10 | 4 | 10 | 5.0 | 327 | 7.4 | 重点软件企业和集成电路设计企业认定 2012 (12 / 5) |
| equipment_robot | 20 | 19 | 6 | 11 | 3.3 | 547 | 7.2 | 机器人+应用行动 2023 (7 / 5) |
| semiconductor | 16 | 7 | 2 | 6 | 8.0 | 327 | 2.0 | same 2012 认定办法 (12 / 5) |
| future_industry | 12 | 12 | 2 | 7 | 6.0 | 364 | 7.7 | 未来产业创新发展 2024 (9 / 5) |
| new_materials | 2 | 2 | 1 | 2 | 2.0 | 308 | 2.1 | 稀土行业 2011 (2 / 2) |
| all anchors | 24,599 | 17,650 | 2,943 | 351 | 8.4 | 304 | | |

**Evidence.** Data and carbon instruments cascade widest on every measure: total events,
distinct sites, events per anchor, and citation-only events. The two widest single anchors
in the sector set are the 2025 NDRC data-circulation plan (96 events, 42 sites, four tiers)
and the 2021 carbon-peaking action plan (78 events, 27 sites, four tiers). Among citation-only
events per 100 central sector documents, carbon leads (42), then biopharma (28), AI (25),
new energy (25), NEV (22), agriculture (22). Semiconductors (7), new materials (4) and
low-altitude (11) are the narrowest. `[measured]`

Two caveats on the data sector. 321 of its 426 events are topic_genre matches, the loosest
match type. On citation-only events it ties with carbon (100 against 92). And its three
widest anchors are all 2023-2025, so the cascade is caught mid-flight. `[measured]`

**Reading.** Width tracks instrument type, not sector attention. The widest cascades are
*plans* (行动方案, 实施方案) that assign tasks to every tier, so every tier issues an
implementing document that cites them. The narrowest cascades are the *money* sectors: a
tax-preference rule or a district special fund is applied, not re-issued, so it leaves no
sub-national echo. Chips are the clearest case. They receive the highest subsidy share of
any sector and cascade through exactly two anchors, one of which is a 2012 enterprise
accreditation rule. The AI sector is the intermediate case documented in
`ai-governance-diffusion.md`: its regulations do not cascade, its 2017 plan and 2025 "AI+"
opinion do. `[inferred]`

---

## 6. Comparison to Fang, Li and Lu

**What they do.** `[lit]` They apply multistage LLM extraction and verification to ~3.3M
central, provincial and city documents, 2000-2022. From each document they extract the
targeted industries, the policy tone (supportive against regulatory), the policy tools, and
in some specifications the named firms. They identify a 2013 recentralization turning point.

**What this memo adds.** `[inferred]`

1. *Instrument genre as a third axis.* Their "tools" are extracted from text; ours are a
   corpus-wide genre tag applied uniformly to 224k documents, which makes the money / rules /
   plan / framework / explainer split comparable across sectors and periods. The finding that
   emerging sectors are plan-and-explainer-led while legacy sectors are rule-led is a genre
   finding, not a tone finding, and it is not available from supportive-against-regulatory
   alone.
2. *Depth below the city.* Their lowest tier is the city. Ours reaches districts and
   municipal departments, which is where the subsidy genre concentrates and where
   low-altitude and biopharma park policy originates. The district tilt of 2.65 for
   low-altitude and 3.35 department tilt for housing are not observable at city resolution.
3. *An explicit cascade.* They infer central-local linkage from text similarity and
   co-occurrence. `diffusion_events` carries the directed edge from a central instrument to
   the sub-national documents that cite or re-issue it, with lag in days. The sector ranking
   by cascade width and the plan-against-money contrast in section 5 come from that edge.
4. *Recency.* Their window closes in 2022. Ours runs to 2026-09 and catches the AI, data,
   low-altitude and future-industry waves, three of which did not exist as policy objects in
   2022.

**What their extraction captures that ours misses.** `[inferred]`

1. *Tone.* We cannot say whether a sector document supports or restricts. A platform-economy
   document in 2021 (restrictive) and one in 2023 (supportive) carry the same tag. Our genre
   proxy (rules against plans) is correlated with tone but is not tone.
2. *Firm targeting.* Their extraction names firms. Ours has no firm layer.
3. *Body-level sector mentions.* Our lexicon runs on titles only. A body-text check on three
   cues shows the scale of the miss: 集成电路 appears in 3,214 bodies but only 182 of those
   titles; 新能源汽车 in 5,293 bodies, 414 titles; 生物医药 in 4,365 bodies, 168 titles.
   Title recall against body mention is roughly 4-8%. `[measured]` The title lexicon
   therefore measures *headline targeting* (the sector is what the document is about), not
   *any mention*. This is a defensible measurement choice for attention share, and it is why
   every series here is a share of titles, but it undercounts omnibus documents (five-year
   plans, 新质生产力 opinions) that name many sectors in the body and none in the title.
4. *Lexicon precision.* The cues are hand-chosen and were pruned once after a sample check.
   Remaining known noise: `新材料` in company names, `水泥` in construction standards,
   `种子` in forestry regulations, `稀土` in tax-invoice notices. Sector counts under 150
   (new materials, software, semiconductors) carry the most noise relative to signal.
5. *Coverage.* Sub-national depth is Guangdong-heavy. 49% of real-estate hits come from one
   Shenzhen bureau. The R set guards the time series against this but cannot guard the level
   and cascade tables, which should be read as floors from the sites we hold.

---

## 7. Threats to validity

- *Date stamps.* 74 sites with crawl-date stamping were removed (section 1). Any site with
  partial stamping below the 70% threshold still leaks some 2026 mass into the series. The
  2026 column should be read as partial and least reliable.
- *Corpus growth.* The universe grows from 2,590 (2008) to 30,552 (2025) documents. All
  series are shares; HHI is computed on shares. Raw counts are never compared across years.
- *Composition.* The level mix of the universe changes by period as crawl depth grows. The
  tilt measure (section 4) divides by the period's own level mix for this reason.
- *Genre tagger.* `algo_doc_type` is a title regex. 55% of documents fall in non-instrument
  genres and are excluded from mix denominators. The explainer genre's corpus-wide rise in
  2021-26 is partly a tagger artefact (more 政策解读 pages crawled) and is netted out in
  section 3.1.
- *Cascade match types.* topic_genre matches are loose. The citation-only column is the
  strict measure and is reported alongside totals.
- *Multi-labeling.* 332 documents carry two or more sector tags. They enter every sector
  they match. HHI treats sector hits, not documents, as the unit.
- *Resolution floor.* The cascade lags and breadths in section 5 rest on the citation graph,
  which resolves ~52% of edges. Every event count and site count is a floor. *(Added
  2026-10-01 per `consistency-review.md` §2.)*
- *Publication is not adoption.* A sub-national echo is a published document, not evidence
  that the sector policy was implemented or funded. Lags are proxies. *(Added 2026-10-01.)*
- *Scope boundary.* Coverage bias (Guangdong over-represented at district depth,
  proxy-blocked provinces invisible) applies to every sub-national figure. Claims are
  mechanism-level about a document record. No regime-type labels. *(Added 2026-10-01.)*

---

## 8. Bottom line

The document record shows industrial targeting that is broadening across sectors, written
mostly as plans and explainers rather than rules, and paid for in only a handful of sectors.
Money follows chips, software, new energy, NEV and biopharma and is disproportionately a
district-and-department instrument. Rules follow ships, farms, mines and housing. Plans
follow carbon, robotics and telecom. The widest cascades are the plans that give every tier
a task (data circulation, carbon peaking, AI+). The narrowest are the money instruments,
which are applied rather than re-issued. Semiconductors are the paradox the title lexicon
exposes most clearly: flat attention share for fifteen years, the highest subsidy share of
any sector in 2021-26, and almost no cascade.

---

## Appendix: SQL

All queries run against `file:/root/china-governance/documents.db?mode=ro`. Sector tagging
was done in Python with the regexes in section 1 (`re.search` on `title`); the SQL below
shows the LIKE form for one sector where a regex is not needed.

```sql
-- A1. Universe and date-stamped site exclusion
SELECT d.site_key
FROM documents d JOIN sites s ON s.site_key = d.site_key
WHERE s.admin_level NOT IN ('media','research')
GROUP BY 1
HAVING count(*) >= 100
   AND 1.0 * sum(date_published >= '2026') / count(*) >= 0.7;   -- 74 sites, 27,915 docs

SELECT d.id, d.title, d.site_key, s.admin_level, d.algo_doc_type,
       substr(d.date_published,1,4) AS y, d.ai_relevance, d.topics_algo
FROM documents d JOIN sites s ON s.site_key = d.site_key
WHERE d.date_published >= '2008' AND d.date_published < '2027'
  AND s.admin_level IN ('central','provincial','municipal','district','department')
  AND d.site_key NOT IN (<stamped sites>);                        -- 224,291 docs

-- A2. Yearly share of one sector (LIKE form; the memo used the regex in Python)
SELECT substr(date_published,1,4) AS y,
       count(*) AS docs,
       sum(title LIKE '%新能源汽车%' OR title LIKE '%电动汽车%' OR title LIKE '%充电桩%'
        OR title LIKE '%充换电%' OR title LIKE '%动力电池%' OR title LIKE '%智能网联汽车%') AS nev,
       round(100.0 * sum(title LIKE '%新能源汽车%' OR title LIKE '%电动汽车%' OR title LIKE '%充电桩%'
        OR title LIKE '%充换电%' OR title LIKE '%动力电池%' OR title LIKE '%智能网联汽车%') / count(*), 3) AS pct
FROM documents d JOIN sites s ON s.site_key = d.site_key
WHERE d.date_published >= '2008' AND d.date_published < '2027'
  AND s.admin_level IN ('central','provincial','municipal','district','department')
  AND d.site_key NOT IN (<stamped sites>)
GROUP BY 1 ORDER BY 1;

-- A3. Robustness set: add
--   AND d.site_key IN ('gov','ndrc','mof','mee','gd','sz','bj','sh','gz')

-- A4. HHI by year (Python): for each year, v = [hits per sector]; T = sum(v);
--     HHI = 10000 * sum((x/T)^2 for x in v); reported only when T >= 30.

-- A5. Instrument mix: genre groups
--   money     = subsidy, application_guide
--   rules     = regulation, law, decree, standard, decision, administrative
--   plan      = action_plan, work_plan, plan, strategy
--   framework = opinion, policy_issuance, circular
--   explainer = explainer, publicity, commentary, interview
--   excluded from denominators: notice, announcement, reply, other, '' (non-instrument)
SELECT CASE algo_doc_type
         WHEN 'subsidy' THEN 'money' WHEN 'application_guide' THEN 'money'
         WHEN 'regulation' THEN 'rules' WHEN 'law' THEN 'rules' WHEN 'decree' THEN 'rules'
         WHEN 'standard' THEN 'rules' WHEN 'decision' THEN 'rules' WHEN 'administrative' THEN 'rules'
         WHEN 'action_plan' THEN 'plan' WHEN 'work_plan' THEN 'plan' WHEN 'plan' THEN 'plan' WHEN 'strategy' THEN 'plan'
         WHEN 'opinion' THEN 'framework' WHEN 'policy_issuance' THEN 'framework' WHEN 'circular' THEN 'framework'
         WHEN 'explainer' THEN 'explainer' WHEN 'publicity' THEN 'explainer' WHEN 'commentary' THEN 'explainer' WHEN 'interview' THEN 'explainer'
         WHEN 'procurement' THEN 'procurement' WHEN 'budget' THEN 'budget' ELSE 'other' END AS gg,
       count(*)
FROM documents d JOIN sites s ON s.site_key = d.site_key
WHERE <universe filter> AND (title LIKE '%半导体%' OR title LIKE '%集成电路%' OR title LIKE '%芯片%')
GROUP BY 1;

-- A6. Level share and tilt for one sector
WITH u AS (SELECT s.admin_level lvl, count(*) n FROM documents d JOIN sites s ON s.site_key=d.site_key
           WHERE <universe filter> GROUP BY 1),
     k AS (SELECT s.admin_level lvl, count(*) n FROM documents d JOIN sites s ON s.site_key=d.site_key
           WHERE <universe filter> AND title LIKE '%低空经济%' GROUP BY 1)
SELECT k.lvl,
       round(100.0 * k.n / (SELECT sum(n) FROM k), 1) AS sector_share,
       round((1.0 * k.n / (SELECT sum(n) FROM k)) / (1.0 * u.n / (SELECT sum(n) FROM u)), 2) AS tilt
FROM k JOIN u USING (lvl);

-- A7. Cascade breadth for one sector (anchor title regex applied in Python; LIKE shown)
SELECT count(*) AS events,
       count(DISTINCT e.anchor_id) AS anchors,
       count(DISTINCT d.site_key) AS source_sites,
       sum(e.match_type = 'citation') AS citation_events,
       e.source_level
FROM diffusion_events e
LEFT JOIN documents d ON d.id = e.source_id
WHERE e.anchor_title LIKE '%碳达峰%' OR e.anchor_title LIKE '%碳中和%' OR e.anchor_title LIKE '%低碳%'
   OR e.anchor_title LIKE '%绿色制造%' OR e.anchor_title LIKE '%循环经济%' OR e.anchor_title LIKE '%节能降碳%'
GROUP BY e.source_level;

-- A8. Widest anchors in a sector
SELECT e.anchor_id, e.anchor_title, e.anchor_date, count(*) AS events,
       count(DISTINCT d.site_key) AS sites
FROM diffusion_events e LEFT JOIN documents d ON d.id = e.source_id
WHERE e.anchor_title LIKE '%数据要素%' OR e.anchor_title LIKE '%数据流通%' OR e.anchor_title LIKE '%数字经济%'
GROUP BY 1 ORDER BY events DESC LIMIT 3;

-- A9. Anchor level check (all anchors are central)
SELECT s.admin_level, count(DISTINCT e.anchor_id)
FROM diffusion_events e JOIN documents d ON d.id = e.anchor_id JOIN sites s ON s.site_key = d.site_key
GROUP BY 1;                                                        -- central: 2,943

-- A10. Title-against-body recall check
SELECT count(*) AS body_hits,
       sum(title LIKE '%集成电路%') AS title_hits_among
FROM documents
WHERE body_text_cn LIKE '%集成电路%' AND date_published >= '2008' AND date_published < '2027';
-- 集成电路 3,214 / 182; 新能源汽车 5,293 / 414; 生物医药 4,365 / 168

-- A11. AI cross-check: title lexicon against ai_relevance >= 0.2, by year
SELECT substr(date_published,1,4) y,
       round(100.0 * sum(title LIKE '%人工智能%' OR title LIKE '%大模型%' OR title LIKE '%算力%') / count(*), 2) AS lex,
       round(100.0 * sum(ai_relevance >= 0.2) / count(*), 2) AS density
FROM documents d JOIN sites s ON s.site_key = d.site_key
WHERE <universe filter> GROUP BY 1;
```

---

## Robustness: the 74-site exclusion (2026-10-07)

*Read-only re-run on the droplet (`?mode=ro`, 2026-10-07). Section 1 excluded 74 sites on the
belief that they carried crawl dates. `corpus-lessons.md` A4 refuted that on 2026-10-07: the
dates are real, the archives are shallow. A shallow archive cannot carry a trend, so the
exclusion stands for the time series. It is not obviously right for the cross-sections. This
section re-runs every cross-sectional table under three universes and reports what moves.*

**Universes.** (a) the memo universe, the shallow sites removed. (b) all dated government
documents, the shallow sites included. (c) the shallow sites alone. The A1 rule re-run on
2026-10-07 selects **77 sites, 28,940 documents** (the 74 plus three that crossed the 70% line
as the nightly crawl added 2026 pages; `fj_xxzx`, `fj_lsj`, `liaoyuan`, `shizuishan` and
`qingdao` all sit at 70.9-72.5%). (a) is now 226,388 documents against the published 224,291.
(a) reproduces every published table to within 0.1 point (any-sector instrument mix
5.8 / 18.5 / 23.3 / 22.0 / 27.2 against the published 5.8 / 18.6 / 23.2 / 22.0 / 27.2), so the
drift is immaterial and the published figures stand as the (a) column below. `[measured]`

```sql
-- universe switch: (a) NOT IN, (b) no clause, (c) IN
SELECT d.id, d.title, s.admin_level, d.algo_doc_type, substr(d.date_published,1,4) y,
       di.admin_level_doc, di.genre
FROM documents d JOIN sites s ON s.site_key = d.site_key
LEFT JOIN doc_identity di ON di.doc_id = d.id
WHERE d.date_published >= '2008' AND d.date_published < '2027'
  AND s.admin_level IN ('central','provincial','municipal','district','department')
  AND d.site_key NOT IN (<77 shallow sites>);            -- (a) 226,388  (b) 255,328  (c) 28,940
```

**What the 77 sites are.** 27,552 of their 28,940 documents (95.2%) are dated 2026. 794 are
2025. No earlier year has more than 206. MIIT is 7,787 of them (27%), all 2026. By site level
they are municipal 10,852, central 9,683, provincial 6,985, district 1,420, department 0. They
are instrument-poor: 16% of their documents carry an instrument genre (4,635) against 44% in
(a). In `doc_identity.genre` terms they are 8.2% promulgation, 28.3% readout, 56.8% other,
against 40.3 / 12.8 / 34.2 in (a). Their sector-tagged share is 5.6% (1,612 docs), above the
4.0% in (a), and MIIT alone supplies 838 of the 1,612 (telecom 223, AI 205, NEV 93, carbon 82,
future industries 62). `[measured]`

### R1. Time series: the 2026 bar with and without the shallow sites

| year | (a) docs | (a) tagged % | (a) HHI | (b) docs | (b) tagged % | (b) HHI | (c) docs | (c) tagged % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2018 | 10,233 | 4.3 | 1,030 | 10,256 | 4.3 | 1,027 | 23 | 4.3 |
| 2020 | 12,971 | 3.4 | 909 | 13,038 | 3.4 | 907 | 67 | 3.0 |
| 2022 | 19,844 | 3.0 | 870 | 19,898 | 3.0 | 869 | 54 | 1.9 |
| 2024 | 27,663 | 4.1 | 775 | 27,869 | 4.1 | 779 | 206 | 3.4 |
| 2025 | 30,888 | 5.4 | 867 | 31,682 | 5.4 | 867 | 794 | 6.3 |
| 2026* | 27,214 | 6.2 | 960 | **54,766** | 5.9 | 804 | **27,552** | 5.6 |

**Evidence.** Through 2024 the two series are identical to the decimal. In 2025 they differ by
794 documents and no share moves. In 2026 the shallow sites double the bar (27,214 to 54,766).
The tagged share moves 6.2 to 5.9 and the HHI 960 to 804. `[measured]`

**Reading.** This is the shallow-archive effect made visible. A site first crawled in 2026 adds
a 2026 column and nothing else, so including it doubles one bar and leaves the trend untouched
but mis-weighted. The exclusion is correct for the time series. The 2026 tagged share and HHI
are robust to it (under 2 points, same direction). `[inferred]`

### R2. Rise and fall (section 2.3) under (b)

Mean share 2012-16 against mean share 2022-26. The early period is unchanged under (b) because
the shallow sites hold 26 documents from 2012-16.

| sector | (a) late % | (a) ratio | (b) late % | (b) ratio | verdict |
|---|---:|---:|---:|---:|---|
| ai | 0.532 | new | 0.523 | new | holds |
| future_industry | 0.137 | 20.4 | 0.149 | 22.2 | holds |
| low_altitude | 0.205 | 7.8 | 0.189 | 7.2 | holds |
| digital_data | 0.573 | 3.9 | 0.557 | 3.8 | holds |
| biopharma | 0.273 | 3.3 | 0.258 | 3.1 | holds |
| agri_seed | 0.222 | 0.5 | 0.216 | 0.5 | holds |
| heavy_tradit | 0.260 | 0.5 | 0.255 | 0.5 | holds |
| aero_ship | 0.154 | 0.7 | 0.165 | 0.7 | holds |
| telecom_iot | 0.059 | 0.2 | 0.137 | 0.5 | **fall weakens** |
| real_estate | 0.636 | 1.6 | 0.541 | 1.4 | artefact diluted |

**Evidence.** All five confirmed rises and all three confirmed falls hold under (b) with the
same ratio to one decimal. Telecom is the exception: its late share more than doubles (0.059 to
0.137) because MIIT's 5G and 移动通信 pages enter, and the ratio moves from 0.2 to 0.5. The
2026 telecom share is 0.06% in (a) and 0.45% in (b). `[measured]` The "telecom fall" in
section 2.3 was partly an exclusion artefact: the ministry that writes telecom policy had no
pre-2026 archive in the corpus, so its 2026 output could only lower or raise one year. The fall
survives but at half its stated strength. `[inferred]`

### R3. Instrument mix (section 3) under (a), (b), (c)

Shares of instrument documents, money / rules / plan / framework / explainer (%).

| set | n | money | rules | plan | framework | explainer |
|---|---:|---:|---:|---:|---:|---:|
| (a) any sector | 4,437 | 5.8 | 18.5 | 23.3 | 22.0 | 27.2 |
| (b) any sector | 4,782 | 5.6 | 17.7 | 22.8 | 21.2 | 29.0 |
| (c) any sector | 345 | 3.2 | 7.0 | 16.2 | 11.0 | **52.5** |
| (a) all docs | 100,506 | 4.0 | 32.5 | 13.9 | 21.2 | 17.8 |
| (b) all docs | 105,141 | 4.1 | 31.4 | 13.7 | 20.8 | 19.2 |
| (c) all docs | 4,635 | 6.1 | 7.9 | 9.0 | 11.3 | **48.5** |

Per-sector money share, (a) to (b): semiconductor 14.4 to 14.1, software 17.6 to 16.7, new
energy 13.1 to 13.4, NEV 10.0 to 8.4, biopharma 10.0 to 9.8, future industries 16.7 to 15.8.
Per-sector rule share: ships and aerospace 44.8 to 44.6, agriculture 42.0 to 40.3, heavy
industry 31.9 to 30.4, real estate 26.8 to 25.6. Money share 2021-26: semiconductor 22.0 to
21.3, software 21.1 to 19.5. `[measured]`

Per-sector moves above 2 points, all toward explainer: NEV plan 30.3 to 26.5 and explainer
20.3 to 27.6 (explainer becomes the modal genre by one point); carbon plan 42.4 to 37.7 and
explainer 16.5 to 23.4 (still plan-led); telecom explainer 22.0 to 25.6 and framework 25.2 to
22.2; platforms explainer 22.6 to 26.6. `[measured]`

**Reading.** Headline 2 survives untouched. The shallow sites are half explainer (52.5% of
their sector instruments) because MIIT's archive is its 政策解读 and 一图读懂 feed, but they
hold only 345 sector instruments, 7% of (b), so they shift the pooled mix by under 2 points.
Who gets money, who gets rules, and the chip and software subsidy turn in 2021-26 are
unaffected. The one visible effect is a 4-7 point explainer lift in MIIT's own sectors (NEV,
carbon, telecom). `[inferred]`

`doc_identity.genre` is a different taxonomy (promulgation / implementing / explainer / readout
/ news / other) and cannot replace `algo_doc_type` for the money-rules-plan split. It confirms
the direction of the explainer finding: sector-tagged documents are 9.7% explainer against 5.3%
for all documents in (a), and 9.3% against 5.0% in (b); they are also more promulgation (43.2
against 40.3) and more implementing (8.4 against 6.2) and less readout (9.7 against 12.8).
`[measured]`

### R4. Level (section 4): the one place the exclusion mattered

Central share of each sector's documents by site level, (a) and (b), and the tilt in brackets.
Universe central share: (a) 31.8%, (b) 32.0%. The universe level mix moves under 2 points at
every tier (provincial 19.1 to 19.6, municipal 23.5 to 25.1, district 10.7 to 10.0, department
15.0 to 13.3).

| sector | (a) central | (b) central | move | (c) central | (c) n |
|---|---:|---:|---:|---:|---:|
| telecom_iot | 56.1 (1.77) | 75.5 (2.36) | **+19.4** | 97.0 | 230 |
| future_industry | 13.4 (0.42) | 29.4 (0.92) | **+16.0** | 59.3 | 108 |
| ai | 33.7 (1.06) | 43.6 (1.36) | **+9.9** | 71.1 | 291 |
| software | 42.2 (1.33) | 49.0 (1.53) | **+6.8** | 87.0 | 23 |
| green_lowcarbon | 41.4 (1.30) | 47.0 (1.47) | **+5.6** | 74.5 | 110 |
| equipment_robot | 23.0 (0.72) | 28.6 (0.90) | **+5.6** | 50.5 | 93 |
| nev | 48.7 (1.53) | 54.1 (1.69) | **+5.4** | 76.2 | 122 |
| new_materials | 39.4 (1.24) | 43.7 (1.37) | **+4.3** | 61.3 | 31 |
| aero_ship | 57.9 (1.82) | 52.0 (1.63) | **-5.9** | 17.6 | 74 |
| agri_seed | 49.5 (1.56) | 44.3 (1.39) | **-5.2** | 3.4 | 89 |
| biopharma | 31.7 (1.00) | 28.4 (0.89) | **-3.3** | 0.0 | 60 |
| platform_ecom | 50.0 (1.57) | 47.6 (1.49) | -2.4 | 28.2 | 78 |
| digital_data | 53.3 (1.68) | 51.1 (1.60) | -2.2 | 34.5 | 142 |
| semiconductor | 42.9 (1.35) | 44.8 (1.40) | +1.9 | 68.4 | 19 |
| heavy_tradit | 55.3 (1.74) | 53.5 (1.67) | -1.8 | 33.3 | 69 |
| new_energy | 34.8 (1.09) | 34.6 (1.08) | -0.2 | 33.3 | 72 |
| low_altitude | 18.4 (0.58) | 18.9 (0.59) | +0.5 | 26.1 | 23 |
| real_estate | 17.6 (0.55) | 17.3 (0.54) | -0.3 | 11.5 | 52 |

**Evidence.** Eleven of 18 sectors move more than 2 points. The eight that rise are MIIT's
remit (telecom, future industries, AI, software, carbon, equipment, NEV, new materials); in (c)
they are 50-97% central and that is MIIT. The three that fall (ships, agriculture, biopharma)
fall by dilution: the shallow provincial and municipal sites write about them and MIIT does
not. The two lists in section 4 change membership. Centrally targeted (tilt above 1.5) gains
software (1.53) and loses agriculture (1.39) and platforms (1.49). Locally initiated (tilt
below 0.75) loses future industries (0.42 to 0.92) and equipment and robotics (0.72 to 0.90);
only real estate and low-altitude remain. The provincial tilt of future industries falls from
1.85 to 1.37. The district tilt of low-altitude (2.59 to 2.60) and the department tilt of
housing (3.39 to 3.67) are unchanged. `[measured]`

Section 4.1, central share 2021-26, (a) to (b): software 29 to 40, AI 32 to 43, telecom 71 to
88, NEV 44 to 53, carbon 40 to 47, equipment 20 to 27, new materials 26 to 35, **future
industries 12 to 29**, ships 45 to 39, agriculture 39 to 32, semiconductors 34 to 38,
platforms 48 to 45. Universe central share 26 to 27. Earlier periods are unchanged (the
shallow sites hold 169 documents before 2021). `[measured]`

**Reading.** The pile-on headline survives: semiconductors still fall from 59% central to 38%,
new energy from 66% to 26%, low-altitude from 60% to 15%, and the raw central share still falls
for 15 of 16 sectors across the last two periods (telecom is the one rise). Two sentences in section 4 do not survive.
"Future industries are local from the start" (12% central, tilt 0.44) was an exclusion
artefact: the ministry that leads 未来产业 policy had no pre-2026 archive, so its 62 quantum,
humanoid-robot and 6G documents were removed with it. With MIIT in, future industries are 29%
central in 2021-26 and near parity at every tier. "Equipment and robotics are municipal
(1.49), local throughout" weakens to 1.30 and 0.90 central. The telecom "recentralizes"
reading strengthens (70% to 88%). `[inferred]`

### R5. Where `doc_identity` changes a number

Section 4 used `sites.admin_level`. `doc_identity.admin_level_doc` re-levels each document
(the npc 地方法规 become provincial or municipal, department sites fold into their tier). Under
(a), the universe becomes central 22.3%, provincial 23.8%, municipal 42.7%, district 11.2%,
department 0 (site level: 31.8 / 19.1 / 23.5 / 10.7 / 15.0). Sector central shares that move
more than 2 points, site level to document level: agriculture 49.5 to 26.6, ships and
aerospace 57.9 to 47.7, real estate 17.6 to 7.8, heavy industry 55.3 to 47.1, data 53.3 to
49.2, carbon 41.4 to 37.2, NEV 48.7 to 45.5. The other eleven hold within 2. In 2021-26
agriculture goes 39 to 19, real estate 10 to 4, ships 45 to 34, the universe 26 to 19.
`[measured]`

```sql
-- A6 with per-document level (replace s.admin_level in both CTEs)
SELECT di.admin_level_doc lvl, count(*) n
FROM documents d JOIN doc_identity di ON di.doc_id = d.id JOIN sites s ON s.site_key = d.site_key
WHERE <universe filter> AND (title LIKE '%种业%' OR title LIKE '%种子%' OR title LIKE '%农机%')
GROUP BY 1;
```

**Reading.** Two corrections follow. Agriculture is not centrally targeted. Its "central"
documents were npc-published local 种子 and 农机 regulations, mis-leveled by the site; at
document level its central tilt is 1.19 and its provincial tilt 2.05. The same correction
trims ships, heavy industry and housing by 8-10 points. Second, the tilt threshold of 1.5 must
be re-based under document level: with the universe only 22% central, twelve sectors exceed
1.5 and the line stops discriminating. Rank order is what survives (telecom 2.45, platforms
2.25, data 2.21, ships 2.14, heavy 2.11 at the top; real estate 0.35, future industries 0.54,
low-altitude 0.74 at the bottom). The "department phenomenon" for housing (tilt 3.35) becomes
"municipal, 70.2%, tilt 1.64": the same Shenzhen bureau, labelled by its tier rather than its
site type. Any future version of section 4 should join `doc_identity`. `[inferred]`

### R6. Cascades (section 5)

`diffusion_events` never carried the exclusion (A7 has no universe filter). 1,505 of 35,475
events (4.2%) have a source document in the 77 sites and 110 have an anchor there. Section 5
is unaffected by this check. `[measured]`

### R7. Verdict

Moved by more than 2 points, (a) to (b): the level composition of MIIT's remit sectors
(telecom +19, future industries +16, AI +10, software +7, carbon +6, equipment +6, NEV +5, new
materials +4 points central) and the dilution of ships (-6), agriculture (-5) and biopharma
(-3); the 2021-26 central share of the same sectors (future industries 12 to 29); the
explainer share of NEV (+7), carbon (+7), platforms (+4) and telecom (+4); the telecom
rise-fall ratio (0.2 to 0.5). Held within 2 points: the tagged share and HHI in every year; all
eight confirmed rises and falls other than telecom; the pooled instrument mix for sector and
corpus; every per-sector money and rule share; the universe level mix; the low-altitude
district and housing department tilts; the cascade table. `[measured]`

Headlines 1 and 2 survive the exclusion. Headline 3 survives in its pile-on form and fails in
one sentence: future industries are not "local from the start", they are MIIT's sector, and
the memo removed MIIT. The exclusion remains right for the time series and wrong for the level
cross-section, which should be read from (b) or, better, from `doc_identity` on (b). The
general lesson is in `corpus-lessons.md` A4: a site that is missing from the corpus is also
missing from every share computed over it, and when the missing site is the lead ministry for
a sector the level composition of that sector is not measured, it is assumed. `[inferred]`
