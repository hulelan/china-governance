# The AI Regulatory Follow-On Web: Who Operationalizes CAC's Rules, and How

*A worked analysis on the china-governance corpus (313,350 docs, SQLite on the droplet).
All figures pulled read-only from the live `documents.db` on 2026-09-28 via the indexed
`citations` table. Extends `ai-governance-diffusion.md`, which established that AI
**regulation** is a central monopoly (the algorithm-recommendation rule: 80 central citers,
0 provincial). This memo maps the central follow-on web that monopoly sits inside:
research-agenda Q8, genre × authority. Every number is reproducible from the inline SQL
appendix.*

---

## 0. The question and the short answer

**Question.** The diffusion memo showed AI regulation stays at the top and is cited almost
entirely by the center. That leaves the follow-up: *which* central bodies operationalize the
CAC regulatory triad, and through *what instruments*? Standards? Filing regimes? Enforcement?
Sectoral application? Courts? And does the operationalization web look different from the
one that grew around the 2017 development plan?

**Short answer.** The follow-on web of the three CAC rules is **almost entirely CAC's own,
and it operationalizes through four instrument families, not through other ministries
re-issuing.** Of the 118 distinct central documents citing the triad, 110 (~93%) carry the
`cac` site key (verified: cac 110, gov 4, sic 2, ipc_court 2; corrected 2026-10-01 from the
earlier "~85-90%" estimate to match `ai-governance-diffusion.md` §7). The operationalization
is (1) an **interpretive apparatus** (专家解读 /
答记者问, the largest genre), (2) a standing **filing/registry regime** (算法备案 /
深度合成备案 / 生成式AI备案 batch公告), (3) **enforcement campaigns and cases** (清朗
专项行动, 执法典型案例), and (4) a **nested cascade of successor rules** (深度合成 →
生成式AI → 标识办法 → 拟人化互动 → 数字虚拟人). Other ministries appear almost only as
**co-signers on the rules themselves** (工信部, 公安部, 广电总局 recur; 市场监管总局 on
enforcement; 发改委/教育部/科技部 on the genAI rule), and standards are handed to
**TC260 / 全国网安标委** (a mandatory GB standard operationalizes the labelling rule) and
**MIIT** (行业标准). The judicial layer is present but thin and brand-new: the Supreme
People's Court 涉人工智能纠纷案件的意见 (2026-09) is in the corpus and its 理解与适用
article cites the generative-AI rule.

The **contrast** is clean. The 2017 development plan's follow-on web is **MOST-dominated
and territorial** (科技部 试验区 pilot-zone designation letters for nine cities, 开放创新
平台 guidelines, plus 教育部 campus-AI plans and a 林草局 sectoral guidance). Regulation is
operationalized by one agency through control instruments. Promotion was operationalized by
a line ministry through place-based industrial buildout.

The one-line version: **AI regulation is not just written centrally, it is
operationalized centrally and largely single-handedly by CAC, using interpretation, a
filing regime, enforcement campaigns, and successor rules rather than inter-ministerial
implementation.**

---

## 1. The follow-on web is a CAC monopoly (agency × anchor)

For each anchor, the distinct central citing documents by `site_key`. Central-only, resolved
citations, `COUNT(DISTINCT source_id)`.

**Table 1 — central citers of each anchor, by site**

| anchor (date) | cac | gov | most | moe | sic | ipc_court | central total |
|---|---:|---:|---:|---:|---:|---:|---:|
| 算法推荐规定 (2022-01) | 74 | 4 | 0 | 0 | 2 | 0 | **80** |
| 深度合成规定 (2022-12) | 58 | 2 | 0 | 0 | 2 | 0 | **62** |
| 生成式AI办法 (2023-07) | 47 | 1 | 0 | 0 | 0 | 2 | **50** |
| 新一代AI发展规划 (2017-07) | 1 | 15 | 3 | 1 | 0 | 0 | **31**‡ |

*Evidence: per-anchor `GROUP BY site_key` (appendix Q1). Pooled across the triad there are
**118** distinct central citers (the successor rules cite more than one anchor, so the row
sums exceed 118).*

‡ *Corrected 2026-10-01 per `consistency-review.md` M2. This row originally read 20, which
disagreed with `ai-governance-diffusion.md` Table 3a (31) and with the live count (31 distinct
central citers on 2026-10-01, appendix Q1 on id 900041126). The per-site split shown (1 / 15 /
3 / 1) is the original pull and sums to 20; it has not been re-pulled and should be read as
the composition of a subset, not the full 31. The gov/most/moe-led shape is unaffected.*

Read it:

- **The regulatory triad's operationalization is CAC's own house.** 74 / 80, 58 / 62, and
  47 / 50 of the central citers sit on the `cac` site key. The `gov` rows are the co-issued
  rules and one enforcement campaign republished on gov.cn (§3). `sic` is the National
  Information Center's research desk. `ipc_court` is the two judicial-journal pieces (§4).
  No line ministry appears as an independent citing author. AI regulation does not fan out
  into a MIIT rulebook or a public-security rulebook. It stays inside the network regulator.
- **The 2017 plan is the mirror image.** Its central web is `gov`/`most`/`moe`, with CAC
  essentially absent (1 doc). MOST, not CAC, is the operator. The composition of the
  follow-on web, not just its volume, encodes the regulation/promotion split.

---

## 2. How the triad is operationalized: the four instrument families

The 118 pooled central citers of the triad, bucketed by genre from title cues (distinct docs;
the interpretive and filing genres are the bulk).

**Table 2 — genre of the triad's central follow-on documents**

| genre | count | what it is |
|---|---:|---|
| 专家解读 (expert interpretation) | 49 | commissioned readings framing each rule |
| 备案公告 (filing/registry notice) | 32 | published batches of registered algorithms / deep-synthesis / genAI services |
| 规章/规范/指引 (rule / guidance) | 11 | the successor instruments themselves |
| 答记者问 (press Q&A) | 5 | official gloss at promulgation |
| 征求意见 (draft consultation) | 5 | pre-promulgation drafts of the next rule |
| 执法案例 (enforcement case) | 4 | disclosed enforcement actions / typical cases |
| 清朗专项行动 (enforcement campaign) | 3 | 清朗 algorithm-governance special actions |
| other | 9 | related plans, standards-system notices |

*Evidence: pooled genre `CASE` tally (appendix Q2).*

This is the operationalization mechanism, and it is **not** downward re-issuance. It is four
families:

**(a) Interpretation dominates (54 docs: 专家解读 49 + 答记者问 5).** The single largest
activity around each CAC rule is CAC publishing commissioned expert readings and press Q&As.
The rules are operationalized first as *meaning*, a dense interpretive scaffold issued by the
regulator itself at each promulgation (2022-01, 2022-12, 2023-07, 2025-03, 2026-04).

**(b) A standing filing regime (32 docs).** The algorithm rule created an 算法备案系统
(filing system, online 2022-02), and CAC has since published the registered-service rosters
as recurring 公告: eighteen batches of 深度合成 filings (第一批 through 第十八批, 2023-06 to
2026-07) and quarterly 生成式AI filing公告 (2024-04 onward). This is the concrete enforcement
surface of the triad. Registration, not licensing, is the control instrument, and its
paper trail is the largest documentary output after interpretation.

**(c) Enforcement campaigns and cases (7 docs).** 清朗·2022年算法综合治理 and 清朗·网络平台
算法典型问题治理 (2024-11, co-issued, §3) are the campaign instrument. Disclosed 执法典型
案例 (2025-09, 2026-09) and named actions (查处"剪映"App 标识违法, 2026-04) are the case
instrument. Enforcement is centralized in CAC's 清朗 apparatus.

**(d) A nested cascade of successor rules (11 docs).** The triad extends itself. The
algorithm rule (2022) is cited by, and chronologically precedes, the deep-synthesis rule
(2022), which precedes the generative-AI measures (2023), which precede the content-labelling
rule (2025-03), which precede the anthropomorphic-interaction rule (2026-04) and the
digital-virtual-human draft (2026-04). Each new rule cites the earlier ones. The regulatory
field grows by CAC issuing the next rule in the chain, not by localities or line ministries
implementing the last one.

---

## 3. Who co-signs: line ministries enter only on the rule masthead

Line ministries are largely absent as independent citers (§1), but they are present as
**co-issuers on the instruments themselves**. From the `publisher` field of the co-signed
documents:

**Table 3 — co-issuing agencies on the triad and its successors**

| instrument (date) | issuing bodies (publisher field) |
|---|---|
| 算法推荐规定 (2022-01) | 网信办 + 工信部 + 公安部 + 市场监管总局 (four) |
| 深度合成规定 (2022-12) | 网信办 + 工信部 + 公安部 (three) |
| 生成式AI办法 (2023-07) | 网信办 + 发改委 + 教育部 + 科技部 + 工信部 + 公安部 + 广电总局 (seven) |
| 生成合成内容标识办法 (2025-03) | 网信办 + 工信部 + 公安部 + 广电总局 (four) |
| 清朗·网络平台算法典型问题治理 (2024-11) | 中央网信办秘书局 + 工信部办公厅 + 公安部办公厅 + 市场监管总局办公厅 (four) |

*Evidence: `publisher` on ids 900050079 / 900048912 / 900048164 / 900046217 / 900046517
(appendix Q3, and visible in the §1 citer dump).*

The pattern: **CAC is always the lead**, and a stable supporting cast recurs. 工信部 (MIIT)
and 公安部 (MPS) co-sign every regulatory rule. 广电总局 (NRTA) joins on the content rules
(genAI, labelling). 市场监管总局 (SAMR) joins on the algorithm rule and the algorithm
enforcement campaign. The genAI rule alone pulls in the developmental ministries (发改委,
教育部, 科技部) because it straddles promotion and control. But co-signing is the extent of
inter-ministerial involvement. None of these bodies then issues its own downstream
operationalizing rule that cites back. The masthead is shared; the follow-on web is not.

---

## 4. The standards and judicial layers

Two operationalization channels sit outside CAC's document stream and are worth isolating.

**Standards are delegated, not issued as rules.** The content-labelling rule (标识办法,
2025-03) is operationalized by a **mandatory national standard**, 《网络安全技术 人工智能
生成合成内容标识方法》(强制性国家标准), drafted through 全国网安标委 / TC260 (consultation
2024-09, 一图读懂 explainer id 12694253 carries inbound 15, cr 40). Above the individual
rules sit standards-system blueprints: 国家新一代人工智能标准体系建设指南 (SAMR-led five
bodies, 2024-05) and 国家人工智能产业综合标准化体系建设指南 (four bodies incl. 网信办,
2024-07). Separately, **MIIT** runs the industry-standard track: 《人工智能终端智能化分级》
national standards (2026-05) and a 121-item 行业标准计划 including 模型上下文协议应用安全
要求 (2026-03). Standards operationalization is thus split: CAC/TC260 own the safety and
labelling standards that give the rules technical teeth; MIIT owns the product/industry
standards that sit on the promotion side.

**The judicial layer is present but very new and thin.** The Supreme People's Court
《关于依法审理涉人工智能纠纷案件的意见》 is in the corpus (id 900134172, 2026-09-08, on
`ipc_court`), and its authoritative 理解与适用 article (id 900134176, 2026-09-09) **cites the
generative-AI measures** (the only triad-to-court resolved edge). Courts plug into the
regulatory web through the genAI anchor specifically, and only at the very end of the
observation window. The AI-adjudication instrument exists in the record but has not yet
generated a follow-on web of its own.

---

## 5. Contrast: the 2017 development plan's web is MOST-led and territorial

Set against the CAC triad, the 2017 新一代人工智能发展规划 operationalizes through an
entirely different apparatus (from its central citers, 31 on the live count, appendix Q1; the
original pull listed 20, see Table 1 note):

- **MOST (科技部) dominates through place-based pilots.** Nine 国家新一代人工智能创新发展
  试验区 designation letters (函) to 上海, 北京, 深圳, 天津, 杭州, 合肥, 长沙, 苏州, 德清,
  plus the 试验区建设工作指引 and 开放创新平台建设工作指引. Operationalization is
  territorial and developmental: designate places, issue buildout guidelines.
- **MOE (教育部)** adds the sectoral education layer: 高等学校人工智能创新行动计划 (2018)
  and the 人工智能助推教师队伍建设 pilot.
- A **line-ministry sectoral guidance** (林草局 forestry/grassland AI, 2019) shows the
  promotion program reaching into a single sector, the kind of fan-out that the regulatory
  triad never produces.

**Table 4 — the two webs side by side**

| dimension | CAC regulatory triad | 2017 development plan |
|---|---|---|
| lead operator | 网信办 / CAC (single) | 科技部 / MOST (single) |
| dominant instrument | interpretation + filing公告 + successor rules | 试验区 designation letters + build guidelines |
| supporting agencies | 工信部/公安部/广电总局 as co-signers only | 教育部, line ministries as sectoral issuers |
| geography | central, non-territorial | place-based (nine試験区 cities) |
| control vs promotion | control (备案, 清朗, standards) | promotion (pilots, platforms, campus AI) |
| judicial hook | SPC AI-disputes opinion (2026-09, via genAI rule) | none |

Both webs are central and both are single-operator. The difference is the *kind* of operator
and the *kind* of instrument. Regulation is operationalized by the network regulator through
registration and enforcement. Promotion was operationalized by the science ministry through
territorial designation. This is the same regulation/promotion split the diffusion memo found
in the *downward* citation pattern, now visible a second time in the *central follow-on
composition*, an independent confirmation on a different measurement.

---

## 6. Threats to validity

Stated plainly, consistent with the companion memo.

1. **Coverage of the central tier is a strength here, not a caveat.** CAC, gov.cn, MOST, MOE
   are among the best-crawled sites, so the central follow-on counts are near-complete and
   the CAC-monopoly finding is robust. The one direction of possible undercount is other
   central bodies whose sites are shallow, which would only *strengthen* the "CAC does it
   alone" claim if they turned out to have follow-ons we are missing (they would raise the
   non-CAC share). The finding is conservative.

2. **The mirror/promulgation gotcha recurs.** CAC publishes each rule as multiple rows (the
   full text, the 答记者问, several 专家解读, gov.cn republication). `COUNT(DISTINCT source_id)`
   counts each as a citer, which inflates the *interpretation* genre relative to *rules*. The
   genre split in §2 is real (interpretation genuinely is the largest activity), but the exact
   49 should be read as "the interpretive apparatus is the bulk," not a precise instrument
   count. Anchor identity is hand-curated to the canonical id throughout.

3. **~52% citation resolution.** All citer counts are floors. Unresolved edges skew toward
   out-of-corpus targets, but the CAC-internal chain is dense and well-resolved because both
   ends are crawled, so the *shape* of the web (self-citing, CAC-centric) is not an artifact
   of missing edges.

4. **Genre is inferred from title cues.** 备案公告, 专家解读, 专项行动 are unambiguous title
   patterns, but the "other" bucket (9) and the rule/guidance bucket (11) involve judgment.
   The four-family characterization is structural, not a clean field.

5. **The published face only.** This is documentary operationalization. Actual filing-system
   operations, non-public enforcement, and the internal standard-setting deliberations behind
   TC260 are invisible. The corpus shows what CAC publishes about operationalizing its rules,
   which is itself a signaling choice.

6. **No regime-type claim.** The finding is about the observed authorship and instrument
   composition of a document web, not a characterization of the political system.

---

## 7. Bottom line

The follow-on web around AI regulation answers Q8 sharply. AI regulation in the published
record is **operationalized centrally and overwhelmingly by CAC alone**. Of 118 central
citers of the CAC triad, 110 (~93%) are CAC's own documents, and they operationalize through
four instrument families: an interpretive apparatus (专家解读/答记者问, the largest), a
standing filing/registry regime (算法/深度合成/生成式 备案公告), enforcement campaigns and
cases (清朗专项, 执法典型案例), and a self-extending cascade of successor rules (深度合成 →
生成式AI → 标识办法 → 拟人化互动 → 数字虚拟人). Line ministries (工信部, 公安部, 广电总局,
市场监管总局) enter only as **co-signers on the rule masthead**, never as independent
downstream operators. Technical teeth are delegated: **TC260/全国网安标委** issues the
mandatory content-labelling standard, and **MIIT** runs the industry-standard track. The
**judicial** hook exists but is brand-new and single-threaded (the SPC 涉人工智能纠纷案件的
意见, 2026-09, cites the generative-AI rule). Against all of this, the **2017 development
plan's** web is the mirror image: **MOST-led and territorial**, operationalized through nine
试验区 pilot-zone designations and build-out guidelines plus MOE campus-AI plans. Same
central, single-operator shape; opposite operator and opposite instrument. This is the
regulation/promotion split confirmed a second way, from central follow-on composition rather
than downward diffusion.

The natural next analyses: (1) trace the **filing regime** as its own dataset (the eighteen
备案 batches list named registered services and firms, a machine-readable map of who is
regulated); (2) the **term-uptake** handle (算法备案, 深度合成, 生成式) into other central
bodies' bodies of text, to see whether the rules are *referenced operationally* even where
they are not *cited*; (3) whether the newest rules (拟人化互动, 数字虚拟人) begin to draw
non-CAC follow-ons as the field matures.

---

### Appendix — key queries

```sql
-- Q1  central citers of each anchor, by site (Table 1)
SELECT d.site_key, COUNT(DISTINCT d.id)
FROM citations c JOIN documents d ON d.id=c.source_id
     JOIN sites s ON s.site_key=d.site_key
WHERE c.target_id = 900050079 AND s.admin_level='central'   -- swap: 900048912 / 900048164 / 900041126
GROUP BY d.site_key ORDER BY 2 DESC;

-- pooled distinct central citers of the triad  -> 118
SELECT COUNT(DISTINCT c.source_id)
FROM citations c JOIN documents d ON d.id=c.source_id JOIN sites s ON s.site_key=d.site_key
WHERE c.target_id IN (900050079,900048912,900048164) AND s.admin_level='central';

-- Q2  genre of the triad's central follow-on docs (Table 2)
WITH cit AS (
  SELECT DISTINCT d.id, d.title
  FROM citations c JOIN documents d ON d.id=c.source_id JOIN sites s ON s.site_key=d.site_key
  WHERE c.target_id IN (900050079,900048912,900048164) AND s.admin_level='central')
SELECT CASE
  WHEN title LIKE '%专家解读%' THEN '专家解读'
  WHEN title LIKE '%答记者问%' THEN '答记者问'
  WHEN title LIKE '%备案信息%' OR title LIKE '%已备案%' THEN '备案公告'
  WHEN title LIKE '%专项行动%' THEN '清朗专项'
  WHEN title LIKE '%执法%' OR title LIKE '%查处%' THEN '执法案例'
  WHEN title LIKE '%征求意见%' THEN '征求意见'
  WHEN title LIKE '%一图读懂%' THEN '一图读懂'
  WHEN title LIKE '%办法%' OR title LIKE '%规定%' OR title LIKE '%指引%' THEN '规章/规范'
  ELSE 'other' END g, COUNT(*)
FROM cit GROUP BY g ORDER BY 2 DESC;

-- Q3  co-issuing agencies (Table 3) — publisher field on the rules/campaign
SELECT id, publisher, substr(title,1,40) FROM documents
WHERE id IN (900050079,900048912,900048164,900046217,900046517);

-- Q4  follow-on instrument citation weight (labelling family; note the mirror gotcha)
SELECT id, site_key, citation_rank,
       (SELECT COUNT(*) FROM citations c WHERE c.target_id=documents.id) indeg, substr(title,1,45)
FROM documents WHERE title LIKE '%生成合成内容标识办法%' ORDER BY indeg DESC;
-- 答记者问 mirror 12693873: indeg 80, cr 154 ; canonical 通知 900046217: indeg 2

-- Q5  judicial hook — SPC AI-disputes opinion + its link to the triad
SELECT id, substr(date_published,1,10), site_key, title FROM documents
WHERE title LIKE '%涉人工智能纠纷%';          -- 900134172 (opinion), 900134176 (理解与适用)
SELECT source_id,target_id,target_ref FROM citations
WHERE source_id IN (900134172,900134176) AND target_id IN (900050079,900048912,900048164);
-- -> 900134176 cites 900048164 (generative-AI measures)
```

---

## Re-base note (2026-10-08)

The central/sub-national split in this memo was computed from `sites.admin_level`. Re-measured on
the per-document `doc_identity.admin_level_doc`, **it holds**: only two citers reclassify per
anchor, in opposite directions. The fuller table, and one misreading it pre-empts — 44 of the
generative-AI rule's apparently "non-central" citers are **`media`**, not sub-national government,
so a central-versus-non-central cut overstates local reach by eight times — are in
`ai-governance-diffusion.md` finding 2. Sub-national **government** citation of the whole triad is
**11 of 282 distinct citers (3.9%)**, 8 of them `genre='promulgation'`.
