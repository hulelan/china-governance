# The Two Faces of AI Governance: How Regulation Stays Central While Promotion Diffuses Down

*A worked analysis on the china-governance corpus (313,247 docs, SQLite on the droplet).
All figures pulled read-only from the live `documents.db` on 2026-09-28. Every number is
reproducible from `scripts/rnd/analysis/ai_governance_diffusion.py` (the SQL lever behind
this memo) or the inline queries in the appendix. Companion to `consumption-diffusion.md`,
which validated the same diffusion machinery on a fiscal campaign.*

---

## 0. The question and the short answer

**Question.** AI governance is the corpus's flagship topic and the spine of the research
program. Three things a governance study needs, asked of the AI document record: is
bureaucratic attention to AI bursty or smooth (agenda-setting); which instruments are the
field's anchors (authority); and how does AI policy move down the central to province to
city hierarchy (diffusion)?

**Short answer.** AI governance in the published record has **two distinct faces that
behave differently**, and the split is the finding.

1. **Attention is punctuated, with a sharp 2025-2026 phase change.** AI is absent from
   document *titles* before 2017, climbs slowly to a 0.30% title share by 2024, then jumps
   to **1.39% (2025) and 1.99% (2026)**. The keyword-density measure (`ai_relevance`) shows
   the same shape more strongly: ~1% of docs in 2021 to **4.82% (2025) to 8.07% (2026)**.
   The onset years line up with datable central signals (the 2017 development plan; the
   2021-2023 regulatory wave; the 2025 "AI+" action).

2. **The regulatory core is a central monopoly.** The three instruments that anchor the AI
   field by citation are all central rules, and they are cited **almost entirely by the
   center itself**. The 2022 algorithm-recommendation rule has 80 central citers and **0
   provincial**. Localities do not re-issue AI regulation; they leave it at the top.

3. **Promotion is what diffuses.** The one anchor whose sub-national citers rival its
   central citers is the 2025 State Council **"AI+" action** opinion (10 central, 6
   provincial, 8 municipal). And localities do not merely relay it. They **elaborate it into
   sector-specific "AI+X" action plans** of their own: AI+制造 (manufacturing), AI+交通
   (transport), AI+教育 (education), AI+医疗/健康 (health), AI+养老 (elder care), AI+视听
   (media). 190 "AI+" documents across 47 sites in 2025-2026.

The clean way to say it: **the center writes the rules and keeps them; localities take the
promotional program and build sectoral plans on top of it.** The single biggest caveat is
the same as every corpus result here. Coverage is uneven (Guangdong, the Tier-1
municipalities, Jiangsu, and central bodies are deep; many provinces are shallow or
datacenter-IP-blocked), so diffusion *breadth* is a floor, not a census, and the "AI+"
cascade is caught **mid-flight** at the data cutoff (its anchor is only 2025-08).

---

## 1. AI attention over time (Q1 — agenda-setting)

Normalized by yearly volume throughout, because the corpus's raw document count rises ~70x
over the window and raw counts would manufacture a trend on their own. Two independent
handles agree.

**Table 1 — yearly AI share (title lexicon and keyword density)**

| year | AI-title docs | all docs | title share | `ai_relevance`≥0.2 | density share |
|---|---:|---:|---:|---:|---:|
| 2016 | 0 | 7,163 | 0.00% | 22 | 0.31% |
| 2017 | 4 | 7,005 | 0.06% | 32 | 0.46% |
| 2019 | 19 | 9,596 | 0.20% | 60 | 0.63% |
| 2021 | 34 | 17,164 | 0.20% | 191 | 1.11% |
| 2022 | 55 | 19,911 | 0.28% | 253 | 1.27% |
| 2023 | 59 | 26,701 | 0.22% | 324 | 1.21% |
| 2024 | 84 | 27,952 | 0.30% | 451 | 1.61% |
| **2025** | **475** | 34,224 | **1.39%** | **1,649** | **4.82%** |
| **2026** | **1,774** | 89,092 | **1.99%** | **7,191** | **8.07%** |

*(2026 is a partial year to 2026-09; its inflated denominator reflects dense crawling of
recent documents, so read the share, not the counts.)*

The shape is punctuated, not smooth. AI is a **non-topic in titles until 2017**, the year
of the State Council development plan. It then holds a low plateau through 2024 while the
regulatory instruments accumulate, and undergoes a **phase change in 2025-2026** when the
title share roughly quadruples and the density share rises ~5x in one year. This is the
documentary signature of an issue being elevated, not of a smooth response to underlying
conditions.

**Who leads.** Splitting the AI-title share by administrative level, **central bodies and
media carry the highest AI shares throughout**, and media the highest of all (5.60% of all
media docs in 2025). Sub-national levels trail and only reach the center's share in the
2025-2026 burst. The center and its media channels set AI vocabulary; localities adopt it
late. (The 2023 provincial blip and 2024 municipal spike rest on small counts and should
not be over-read.)

---

## 2. The AI anchors (Q3 — authority)

`citation_rank` (the corpus's weighted-inbound PageRank-like score) plus raw inbound degree.
The **anchor-identity gotcha** from `consumption-diffusion.md` recurs and must be handled:
the resolver scores near-duplicate promulgations (受权发布 releases, 答记者问 Q&As,
一图读懂 explainers, and list-chrome-contaminated mirrors) above the canonical text. For
example the "AI+" opinion's top-scoring row (id 900133026, cr=230) is a **municipal mirror**
whose title is scraped list chrome ("标题：…点击数：2190…"), while the canonical State
Council opinion (id 900039770) scores 54.5. So the anchors below are **hand-curated to the
canonical central instrument**, and diffusion in §3 is measured against those. *(Update
2026-10-01: the AI+ mirror case was removed by the resolver fix (`cd42903`/`c979a82`); the
mirror 900133026 now has `citation_rank` 0 and 0 inbound while the canonical 900039770 still
holds 54.5 / 25. The labelling 答记者问 example (154 vs 4.5) still stands. Keep the
curated-anchor method; the gotcha recurs elsewhere.)*

**Table 2 — the curated central AI anchors**

| id | instrument | date | citation_rank | inbound |
|---|---|---|---:|---:|
| 900050079 | 互联网信息服务算法推荐管理规定 (Algorithm-Recommendation, CAC+4) | 2022-01-04 | **324.5** | 123 |
| 900048912 | 互联网信息服务深度合成管理规定 (Deep-Synthesis, CAC) | 2022-12-11 | **271.5** | 104 |
| 900048164 | 生成式人工智能服务管理暂行办法 (Generative-AI Interim Measures, CAC+6) | 2023-07-13 | **242.0** | 130 |
| 900041126 | 国务院…新一代人工智能发展规划 (New-Gen AI Development Plan) | 2017-07-20 | 207.0 | 78 |
| 900046217 | 人工智能生成合成内容标识办法 (AI-Content Labelling) | 2025-03-15 | 4.5† | 2† |
| 900039770 | 国务院…深入实施"人工智能+"行动的意见 ("AI+" Action opinion) | 2025-08-26 | 54.5† | 25† |
| 900097234 | 关于加强科技伦理治理的意见 (S&T Ethics Governance) | 2022-08-08 | 52.5 | 26 |

† the canonical row; its mirrors/explainers carry the higher scores (labelling: 154.0 on the
答记者问 copy; "AI+": 230.0 on the municipal mirror).

The top of the distribution is **the CAC regulatory triad** (algorithm recommendation,
deep synthesis, generative AI), with the 2017 development plan as the older developmental
anchor. This is the predicted heavy-tailed shape, and its composition is the setup for §3:
the anchors that hold the most authority are **regulatory** and **central**.

---

## 3. Diffusion — the regulation/promotion split (Q2)

The core result. For each curated anchor, the count of distinct citing documents by the
**citing** document's administrative level. Resolved citations only, so every count is a
**floor** (~52% of edges resolve).

*(Final-build note, 2026-10-01: these citer counts are pre-resolver-fix. After the resolver's wrapper-core and containment-gate fixes and the auto-matcher's new `source_implementing` flag, the AI+ anchor (900039770) carries **28 implementing events and 75 mention-only references** (news reposts, meeting readouts, Xi's WAIC speech reposts) in `diffusion_events`. The implementing count matches this memo's ~30 sub-national plans; the mentions are real references but not implementations and are now kept separate. The regulatory anchors' central-dominance pattern below is unchanged in direction.)*

**Table 3a — per-anchor inbound citers by level**

| anchor | central | provincial | municipal | district | media |
|---|---:|---:|---:|---:|---:|
| 算法推荐规定 (2022) | **80** | **0** | 2 | 0 | 2 |
| 深度合成规定 (2022) | **62** | 1 | 2 | 0 | 6 |
| 生成式AI办法 (2023) | **50** | 4 | 1 | 0 | **44** |
| 新一代AI发展规划 (2017) | 31 | 5 | 3 | 1 | 2 |
| 科技伦理治理 (2022) | 10 | 5 | 0 | 0 | 4 |
| **"AI+" 行动意见 (2025)** | **10** | **6** | **8** | 0 | 1 |

Read it:

- **Regulation is centrally monopolized.** The three CAC rules are cited overwhelmingly by
  **central** documents (80, 62, 50) and barely at all by provinces or cities (the algorithm
  rule has **zero** provincial citers). AI regulation is written at the top, cross-cited by
  a dense web of central follow-ons, and **not re-issued downward**. Localities operate
  under these rules; they do not localize them.
- **The genAI rule is the media event.** The 2023 generative-AI measures draw **44 media
  citers**, by far the most of any anchor, the documentary trace of the ChatGPT-moment
  regulatory wave being heavily reported.
- **Promotion is the one that goes down.** The 2025 "AI+" action opinion is the **only**
  anchor whose sub-national citers (6 provincial + 8 municipal = 14) **exceed** its central
  citers (10). The developmental instruments (the 2017 plan, "AI+") spread sub-nationally in
  a way the regulatory instruments do not.

**Table 3b — pooled citers by level (all 7 curated anchors)**

| level | distinct citers |
|---|---:|
| central | 166 |
| media | 52 |
| provincial | 19 |
| research | 14 |
| municipal | 13 |
| department | 6 |
| district | 1 |

The pooled gradient (central 166 ≫ everything else) is even more top-heavy than the
consumption campaign's (central 92). AI governance is a **more central-concentrated** domain
than fiscal stimulus, which fits: the consumption campaign carried money and local
implementation deadlines, whereas AI regulation carries neither. Sub-national lag against
the anchors' own dates is **n=36, median 386 days, IQR 212-879** — slower and far more
dispersed than the consumption cascade's ~49-day median, consistent with citation (an act of
reference) rather than re-issuance (an act of adoption).

---

## 4. The "AI+" cascade — local elaboration, not relay (Q2b, the load-bearing test)

Citation shows *reference*; re-issuance shows *adoption*. Title-matching sub-national
documents that carry the "人工智能+" cue and an action/plan genre, earliest per site, lag
from the 2025-08-26 central opinion:

**Table 4 — first sub-national "AI+" action document per site**

| first issued | level | site | lag (days) | title cue |
|---|---|---|---:|---|
| 2025-11-27 | provincial | Beijing | 93 | "人工智能+视听"产业行动方案 |
| 2025-12-17 | municipal | Chongqing | 113 | 推动"人工智能+"行动方案 |
| 2026-01-08 | municipal | Suzhou | 135 | 加快建设"人工智能+"城市行动方案 |
| 2026-01-20 | provincial | Chongqing-edu | 147 | "人工智能+教育" (8 depts) |
| 2026-02-04 | provincial | Chongqing-transport | 162 | "人工智能+交通运输"创新 |
| 2026-02-15 | provincial | Heilongjiang | 173 | 深入实施"人工智能+"实施方案 |
| 2026-04-28 | district | Beijing-Haidian | 245 | "人工智能+养老"三年行动 |
| 2026-05-19 | provincial | Shandong | 266 | "人工智能+制造"行动方案 (2026-20xx) |
| 2026-06-08 | provincial | Jiangsu-transport | 286 | "人工智能+交通运输"行动方案 |
| 2026-06-29 | provincial | Jiangsu-industry | 307 | "人工智能+制造"实施方案 |
| 2026-07-22 | municipal | Jining | 330 | 加快推进"人工智能+"高质量… |
| 2026-09-19 | municipal | Qingdao | 389 | 更大力度实施"人工智能+"行动 |

*(Same-day/near-day rows for Zhejiang and one department portal were dropped as verbatim
reposts of the central opinion, not localized re-issuances; the `nqs` row is an 一图读懂
explainer. 17 sub-national sites carry an "AI+" action doc in total.)*

**What the cascade shows:**

1. **It is a slow, still-opening cascade.** The first genuine localization is ~3 months out
   (Beijing, 93 days), and activity builds through 2026 and is still arriving at the cutoff.
   Unlike the consumption plan, there is no dense 37-76 day body. The "AI+" program is
   **caught mid-diffusion**, which is itself a datable finding, not a gap.

2. **Localities elaborate, they do not relay.** This is the sharpest contrast with the
   consumption campaign, where cities re-issued the *same* plan (实施方案). Here localities
   issue **new sector-specific instruments**: manufacturing (山东, 江苏), transport (重庆,
   江苏), education (重庆 + 8 departments), elder care (海淀), media (北京). Across the corpus
   the "AI+X" sectoral plans number **AI+制造 20, AI+交通 14, AI+教育 8, AI+视听/文 6,
   AI+医疗/健康 5**. The center sets an umbrella direction; localities build concrete sectoral
   programs under it. In the fidelity-of-diffusion frame (agenda Q6), this is **elaboration**,
   the high-local-agency end of the spectrum, not faithful transmission.

3. **The vertical ordering is present but noisy.** Provinces (Beijing, Heilongjiang,
   Shandong, Jiangsu) and the cities/districts under them interleave, with department
   portals (industry, transport, education bureaus) carrying much of the sectoral load. The
   deepest-covered units (Chongqing, Jiangsu, Beijing) dominate the list, which is coverage,
   not necessarily leadership (§5).

---

## 5. What's measurable vs. what isn't — threats to validity

Stated candidly, because a governance reader will probe each one.

**Measured well:**
- **The attention phase change (§1).** It rests on normalized shares over continuously
  crawled tiers (central, media, Tier-1), so it survives coverage correction. The 2025-2026
  jump is real, not a crawl artifact.
- **The regulation/promotion split (§3).** The algorithm rule's 80-central-0-provincial
  profile is a structural fact of the resolved graph, and central bodies are the
  best-covered tier, so the central counts are near-complete. The *contrast* between
  regulatory and promotional anchors holds regardless of sub-national coverage, because it
  is visible in the central-citer counts alone.
- **Genre of local response (§4).** Titles are ~99.7% present, so "AI+X" sectoral
  elaboration is directly readable.

**The load-bearing caveats:**

1. **Coverage bias dominates breadth, as always.** The sub-national re-issuers cluster in
   Guangdong, the Tier-1 municipalities, Jiangsu, and Chongqing, the corpus's deepest tiers.
   A province absent from Table 4 may have acted and simply not be crawled (many province
   portals are datacenter-IP-blocked from the droplet; see `residential-proxy-options.md`).
   No claim of the form "province X did not localize AI+" is defensible. Breadth is a floor.

2. **The "AI+" cascade is mid-flight.** Its anchor is 2025-08-26 and the cutoff is
   2026-09-28, ~13 months. Every lag past ~250 days is right-censored, and the cascade is
   still opening. The lags measure *observation window*, not *latency*, past that point.

3. **52% citation resolution.** All §2-§3 citer counts are floors; true inbound citation is
   roughly ~2x observed, and unresolved edges skew toward out-of-corpus targets (older,
   internal, non-crawled). The resolver also over-counts mirror promulgations, mitigated
   here by curating canonical anchors and using `COUNT(DISTINCT source_id)`.

4. **Title-match conflates three things.** The "AI+" title cue catches verbatim reposts,
   一图读懂/答记者问 explainers, and genuine localized re-issuances. I dropped the obvious
   reposts and flagged the explainer, but the boundary is judgment, not a clean field. The
   sectoral "AI+X" plans are unambiguous local elaborations; the umbrella relays are noisier.

5. **The published face only.** This is the *documentary* diffusion of AI governance.
   Internal (内部) directives, model-approval decisions, and enforcement actions are invisible.
   The corpus measures what the bureaucracy publishes about AI, which is itself a signaling
   choice, not the full apparatus.

6. **Regime-type claims are out of scope.** The finding is about observed mechanisms, how
   the document system writes, cites, and elaborates AI policy. It does not license
   system-level characterizations.

---

## 6. Bottom line for the volume

The corpus delivers a clean, corpus-native chapter on AI governance. From primary documents
alone it shows: (a) a **punctuated attention curve** with a datable 2025-2026 phase change;
(b) a **regulatory core** (the CAC algorithm/deep-synthesis/generative-AI triad plus the
2017 plan) that holds the field's citation authority; and (c) a **structural split in how
the two faces move** — regulation is written centrally and stays central (the algorithm rule:
80 central citers, 0 provincial), while the promotional "AI+" program diffuses sub-nationally
and is **elaborated into sector-specific plans** (制造/交通/教育/养老/视听) rather than relayed.
The honest framing is "observed diffusion among the crawled tiers, with the regulation/
promotion contrast visible in the well-covered central graph and the sub-national breadth a
floor," and every headline number is reproducible from
`scripts/rnd/analysis/ai_governance_diffusion.py` against the droplet's `documents.db`.

The natural next analyses this opens: (1) **fidelity** — body-text diffing of the "AI+X"
plans against the umbrella opinion to quantify how much is local addition (agenda Q6); (2)
**the regulatory follow-on web** — mapping the central citers of the CAC rules to see who
operationalizes them; (3) **term uptake** — tracking distinctive AI-regulation vocabulary
(算法备案, 生成式, 深度合成) into sub-national titles as a second diffusion handle independent of
citation resolution.

---

## 7. Two deepenings (2026-09-28) — the mechanism behind each face

Analyses (1) and (2) above are now done, and together they turn the "two faces" observation
into a claim about **two different diffusion mechanisms**. Full memos:
`docs/research/ai-plus-fidelity.md` and `docs/research/ai-regulatory-web.md`.

**Promotion diffuses by authored elaboration, not relay** (`ai-plus-fidelity.md`). Measuring
each local "AI+" plan's character-5-gram overlap with the umbrella opinion (900039770), the
distribution appeared sharply bimodal with an empty middle (corpus-wide update 2026-10-01: that
gap was an n=12 artifact; across all 13,509 pairs the distribution is a decaying tail, 88%
elaboration, see `diffusion-fidelity.md`). Only 2 documents overlap near-verbatim,
and both are raw portal reposts of the central text, not plans. The 10 genuine local plans
share just **1.7-12.8%** of their text with the umbrella, so they are ~87-98% locally
authored. There is no level gradient (a Haidian district plan elaborates as fully as a Jiangsu
provincial one); the variation is by sector, with single-sector plans (制造/交通/教育/养老)
narrowing the most. *(Note 2026-10-01: n=10. Corpus-wide a level gradient exists, province 0.074,
city 0.051, department 0.031, district 0.030; see `diffusion-fidelity.md` §3.2 and
`fidelity-provincial.md` §2.1.)* This is the **opposite** of the consumption campaign, which propagated as
templated re-issuance of the *same* named plan because it carried money and central operational
rules. AI+ carries neither, so localities author new sector instruments with no central
counterpart. (Caveat: 5-gram overlap counts gov-notice boilerplate, so the local figures are
upper bounds; n=10, coverage-bound, cascade mid-flight.)

**Regulation self-extends inside CAC, it does not diffuse down** (`ai-regulatory-web.md`). Of
the 118 central documents citing the CAC regulatory triad, **110 carry the `cac` site key**
(verified: cac 110, gov 4, sic 2, ipc_court 2). No line ministry appears as an independent
downstream author; MIIT, MPS, NRTA, and SAMR enter only as co-signers on the rule mastheads,
and standards are delegated to TC260 (the mandatory content-labelling GB) and MIIT. Regulation
is operationalized through four CAC-internal instrument families, not downward re-issuance:
interpretation (解读/答记者问, the largest genre), a standing filing/registry regime
(算法/深度合成/生成式 备案公告), enforcement (清朗 campaigns and typical cases), and a
self-extending chain of successor rules (深度合成 → 生成式 → 标识办法 → 拟人化互动). The 2017
development plan is the mirror image, its follow-on web is MOST-led and territorial (nine
试验区 pilot zones).

**The sharpened thesis.** AI governance has two faces and each moves by its own mechanism. The
regulatory core self-extends at the center inside one agency. The promotional program
elaborates at the periphery into locally authored sector plans. Neither face behaves like the
fiscal consumption campaign's templated top-down re-issuance, and they do not behave like each
other.

---

### Appendix — key queries

```sql
-- Corpus + resolution
SELECT COUNT(*) FROM documents;                          -- 313,247
SELECT COUNT(*), SUM(target_id IS NOT NULL) FROM citations;  -- 529,073 / 276,826 = 52.3%

-- Q1 attention (normalized share, both handles)
SELECT substr(date_published,1,4) yr,
       SUM(title LIKE '%人工智能%' OR title LIKE '%大模型%' OR title LIKE '%生成式%'
           OR title LIKE '%算力%' OR title LIKE '%AIGC%' OR title LIKE '%深度合成%'
           OR title LIKE '%算法推荐%') ai_title,
       SUM(ai_relevance>=0.2) ai_rel, COUNT(*) all_docs
FROM documents WHERE date_published BETWEEN '2000-01-01' AND '2026-12-31'
GROUP BY yr ORDER BY yr;

-- Q3 anchors (curated ids; note the mirror gotcha)
SELECT id, substr(title,1,40), date_published, citation_rank,
       (SELECT COUNT(*) FROM citations c WHERE c.target_id=documents.id) indeg
FROM documents WHERE id IN
  (900050079,900048912,900048164,900041126,900046217,900039770,900097234);

-- Q2a per-anchor citers by level (the regulation/promotion split)
SELECT s.admin_level, COUNT(DISTINCT c.source_id)
FROM citations c JOIN documents d ON d.id=c.source_id JOIN sites s ON s.site_key=d.site_key
WHERE c.target_id = 900050079 GROUP BY 1;   -- 算法推荐: central 80, provincial 0

-- Q2b "AI+" re-issuance cascade with lag
SELECT s.admin_level, d.site_key, MIN(substr(d.date_published,1,10)) first_issue,
  CAST(julianday(MIN(substr(d.date_published,1,10)))-julianday('2025-08-26') AS INT) lag
FROM documents d JOIN sites s ON s.site_key=d.site_key
WHERE d.title LIKE '%人工智能+%' AND (d.title LIKE '%实施方案%' OR d.title LIKE '%行动%')
  AND s.admin_level IN ('provincial','municipal','district','department')
  AND d.date_published >= '2025-08-26'
GROUP BY d.site_key ORDER BY first_issue;
```
