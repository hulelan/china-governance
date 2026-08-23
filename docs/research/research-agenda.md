# Research Agenda — The Corpus as an Instrument for the Study of Chinese Governance

*Draft memo, 2026-08. Author: research-tooling pass. Scope: what questions this
document corpus can and cannot answer, framed in the institutional /
comparative-public-administration tradition (policy diffusion, central–local
dynamics, bureaucratic attention allocation, campaign-style governance,
inter-agency coordination, and signaling in policy text). This is a
questions-and-feasibility memo, not a findings report.*

---

## 0. What the instrument is

The corpus is **263,573 documents** (2000–2026) from **363 site sources**,
tagged along four axes that together make it a research instrument rather than a
document dump:

| Affordance | Field(s) | Coverage (measured 2026-08) |
|---|---|---|
| **TIME** | `date_published` | dense; ~488 docs/yr in 2000 rising to ~33k in 2025; a small tail of dirty dates (e.g. a `2999` outlier — always bound queries `BETWEEN '2000-01-01' AND '2026-12-31'`) |
| **LEVEL** | `sites.admin_level` | central 90,974 · municipal 50,582 · provincial 36,480 · department 33,764 · district 24,041 · media 26,558 · research 1,174 |
| **ISSUER** | `site_key` + `sites.name`; `publisher` (82% pop.); `document_number` (**only 25% pop.**) | site/level reliable; 文号-based issuer identity sparse |
| **CITATIONS** | `citations` (445,599 edges; **51% resolved** to a `target_id`) | 184,372 *resolved cross-level* edges — the workhorse for diffusion/authority |

Genre/content fields: `doc_type` (LLM, ~all docs — dominated by
`original_policy` 126k / `media_coverage` 83k), `algo_doc_type` (regex, 19 types
but **50% `other`**), `policy_significance` (high 45,548 / medium 111,524 / low
106,453), `ai_relevance` (0–1 density; only 530 "high", 8,602 "medium"),
`title_en` (99.98%), `body_text_cn` (82%).

**Standing limits to state in any output:**
- **Selection bias.** Only *publicly published* documents. Internal (内部) and
  classified circulars are invisible; the corpus captures the *published face* of
  the bureaucracy, which is itself a signaling choice, not the full record.
- **Uneven geography.** Guangdong (Shenzhen + 16 cities), the Tier-1 municipalities,
  and select provinces are deep; many provinces are shallow or datacenter-IP
  blocked. Cross-region comparison is confounded by coverage, not just behavior.
- **Citation resolution 51%.** Unresolved refs skew toward documents *outside* the
  corpus (older, internal, or non-crawled). Any citation metric is a **lower bound**
  and is biased toward within-corpus, recent, high-salience targets.
- **Genre coarseness.** `algo_doc_type` is 50% `other`; the LLM `doc_type` is
  cleaner but its taxonomy is broad. Fine genre questions need a genre-classifier
  pass first.
- **Recency/volume artifact.** Doc counts rise ~70× over the window. Almost every
  "attention over time" question must **normalize** (share of that year's docs, or
  a rate), never use raw counts.

---

## Tiering

- **Tier 1 — Answerable now** with existing fields and indexed queries.
- **Tier 2 — Needs the graph/genre fixes**: higher citation resolution, a genre
  classifier, or a normalized issuer/agency table.
- **Tier 3 — Aspirational**: needs data we don't yet have (internal docs, outcomes,
  personnel linkage) or methods beyond the corpus alone.

---

## TIER 1 — Answerable now

### Q1. Does policy attention move in punctuated bursts rather than smoothly? (agenda-setting / attention allocation)

**Claim.** Following the punctuated-equilibrium account of agenda-setting
(Baumgartner & Jones; Jones & Baumgartner on disproportionate information
processing), bureaucratic attention to a given issue is *lumpy*: long quiet
stretches broken by sharp bursts when an issue is elevated, not a smooth response
to underlying conditions. In the Chinese setting this maps onto the
plan/leader-signal cycle (Five-Year Plans, leadership speeches, top-level 意见).

**Operationalize.** Pick an issue lexicon (e.g. AI: `ai_relevance` plus title
terms 人工智能/大模型/算力; or environment, data governance, etc.). Build the yearly
*share* series — issue docs ÷ all docs that year — and test for
kurtosis/burstiness vs. a smooth baseline.

```sql
SELECT substr(date_published,1,4) yr,
       SUM(ai_relevance>=0.2)                       AS ai_docs,
       COUNT(*)                                     AS all_docs,
       1.0*SUM(ai_relevance>=0.2)/COUNT(*)          AS share
FROM documents
WHERE date_published BETWEEN '2012-01-01' AND '2026-08-31'
GROUP BY yr ORDER BY yr;
```

**Feasibility.** High. TIME × content lexicon is exactly what the corpus is built
for. **Threats:** (a) the ~70× volume ramp — must use *share*, not counts;
(b) `ai_relevance` is title+body keyword density, so it tracks *vocabulary*
adoption, which itself diffuses — a burst may be lexical fashion, not attention;
(c) crawl coverage changes year to year. Mitigate by holding the denominator to
comparable site sets. **Positive finding:** high kurtosis / a few years carrying
most of the issue's mass, with burst onsets coinciding with datable top-level
signals (a plan, a Politburo study session).

### Q2. Do policies diffuse *downward* through the administrative hierarchy with a measurable lag? (vertical policy diffusion)

**Claim.** A central instrument is echoed by provinces, then municipalities, then
districts, on a lag — the classic top-down transmission of the "关于印发…的通知 →
转发 → 贯彻落实" chain. Diffusion is *hierarchical and sequenced*, not simultaneous.

**Operationalize.** Two complementary handles. (i) **Reissue by title**: 3,983
titles already appear under >1 `site_key`; track the level sequence of first
appearance. (ii) **Resolved citations across levels**: 30,671 municipal→provincial
and 16,870 provincial→central resolved edges. For a target central doc, get the
level and date of every citing doc and measure the lag distribution.

```sql
-- lag from a central target to its sub-national citers
SELECT s.admin_level AS citer_level,
       julianday(d.date_published) - julianday(t.date_published) AS lag_days
FROM citations c
JOIN documents d ON d.id = c.source_id
JOIN documents t ON t.id = c.target_id
JOIN sites s     ON s.site_key = d.site_key
WHERE c.target_id IS NOT NULL AND t.site_key IN (SELECT site_key FROM sites WHERE admin_level='central')
  AND d.date_published > t.date_published;
```

**Feasibility.** High (this is the corpus's flagship use). **Threats:** 51%
resolution biases toward within-corpus targets; provinces with thin coverage
under-contribute citers, so lags are *right-censored* and *missing-not-at-random*;
publication date ≠ adoption date. **Positive finding:** a monotone level ordering
in median lag (province before municipality before district) and a right-skewed
lag distribution with a mode at weeks–months after the central doc.

### Q3. Is authority in the document network concentrated in a small set of "anchor" instruments? (citation-based authority)

**Claim.** As in legal-citation networks, a few foundational instruments
(framework laws, top-level 意见) accumulate disproportionate inbound citations and
act as anchors the rest of the corpus orients around; authority is heavy-tailed.

**Operationalize.** `citation_rank` (already a weighted-inbound PageRank-like
score) plus raw inbound degree. Inspect the top of the distribution and its level
composition. Grounding check already run: the top of `citation_rank` is exactly
foundational law — 政府信息公开条例 (3552), 网络安全法 (1354), and provincial
*implementation measures* of national laws — which is the predicted shape.

```sql
SELECT d.id, substr(d.title,1,50) t, s.admin_level, d.citation_rank,
       (SELECT COUNT(*) FROM citations c WHERE c.target_id=d.id) indeg
FROM documents d JOIN sites s ON s.site_key=d.site_key
ORDER BY d.citation_rank DESC LIMIT 50;
```

**Feasibility.** High; `citation_rank` and `idx_citations_target_id` exist.
**Threats:** resolution bias again inflates within-corpus, recent, national
targets; `citation_rank`'s level weights (central 3× etc.) are a modeling choice —
report raw degree alongside. **Positive finding:** a Gini/Pareto tail where <1% of
docs hold a large share of resolved inbound edges, concentrated at central level.

### Q4. Is campaign-style ("运动式") governance rising, and is it a central or a local instrument? (campaign governance)

**Claim.** Campaign-style governance — time-bound, target-driven 专项行动 /
专项整治 / 攻坚战 mobilizations — is a persistent tool that ebbs and flows with
political tempo (the literature on campaigns, targets, and "high-pressure"
enforcement). Hypothesis: campaigns are increasingly a *local* execution device
even when framed centrally.

**Operationalize.** Title lexicon (专项行动/专项整治/攻坚/大会战) × year × level.
Measured now: 1,658 such titles, rising 6 (2012) → 275 (2026). Cross with
`admin_level` to see who runs them.

```sql
SELECT substr(date_published,1,4) yr, s.admin_level, COUNT(*) c
FROM documents d JOIN sites s ON s.site_key=d.site_key
WHERE (d.title LIKE '%专项行动%' OR d.title LIKE '%专项整治%' OR d.title LIKE '%攻坚%')
  AND date_published BETWEEN '2012-01-01' AND '2026-08-31'
GROUP BY yr, s.admin_level ORDER BY yr;
```

**Feasibility.** High for the title-lexicon proxy. **Threats:** title keywords
under-count campaigns announced in body only, and over-count routine notices that
merely mention a campaign; normalize by yearly volume before claiming a "rise."
**Positive finding:** rising *share* (not just count) of campaign-titled docs,
with the sub-national share growing relative to central over time, and bursts
aligning with known national drives.

### Q5. Do documents cite *upward* to borrow authority far more than they cite *downward*? (legitimation / authority-borrowing)

**Claim.** Sub-national documents invoke higher-level instruments to legitimate
local action ("依据…精神"), so the citation graph is strongly *up-directed*;
downward citation (center naming a specific locality) is rare and marks either
models to emulate or targets of correction.

**Operationalize.** Directly from the resolved-edge level matrix (already
computed): municipal→provincial 30,671, provincial→central 16,870, municipal→central
16,688, versus central→provincial 1,267, municipal→district 370. Compute an
up:down ratio per source level.

```sql
SELECT source_level, target_level, COUNT(*) c
FROM citations WHERE target_id IS NOT NULL
GROUP BY 1,2 ORDER BY c DESC;
```

**Feasibility.** High — no new work, the matrix is in hand. **Threats:** "unknown"
target_level dominates unresolved edges and could hide downward citations to
out-of-corpus local docs; still, *among resolved edges* the asymmetry is stark.
**Positive finding:** up:down ratios well above 1 at every sub-national level, and
the rare downward citations concentrating on named model localities.

---

## TIER 2 — Needs the graph / genre fixes

### Q6. Which policy relays are *faithful transmission* vs. *local elaboration*? (fidelity of diffusion)

**Claim.** Central-local research distinguishes localities that merely *relay*
(转发, near-verbatim) from those that *reformulate* (add local targets, money,
enforcement). The mix reveals local agency within a hierarchical system.

**Operationalize.** For reissued titles / relay chains, compare `body_text_cn`
length and n-gram overlap between the source and the relaying doc. Low added text
= faithful relay; large local additions = elaboration. Needs a body-similarity
pass over relay pairs (identify pairs via the 3,983 shared titles + resolved
citation edges), then a length-ratio / Jaccard measure.

**Feasibility.** Medium — requires a **targeted** pairwise body comparison (avoid a
full-corpus O(n²) scan; restrict to relay candidate pairs only). 82% body coverage
helps but the 18% missing bodies drop pairs. **Threats:** boilerplate inflates
overlap; OCR/extraction noise; a doc can elaborate in an *attachment* (`attachments_json`)
not the body. **Positive finding:** a bimodal distribution — a "relay" cluster near
verbatim and an "elaboration" cluster with substantial local text — and systematic
variation by locality wealth/level.

### Q7. Is inter-agency coordination fragmenting or consolidating over time? (fragmented authoritarianism / joint issuance)

**Claim.** Following the fragmented-authority tradition (Lieberthal & Oksenberg)
and its updates, cross-agency *jointly issued* documents (联合发文) index
coordination; their share and the size of issuing coalitions track whether the
system is centralizing coordination or proliferating veto players.

**Operationalize.** Joint issuance appears as multiple issuers in `publisher` or as
multiple agency codes in `document_number` (the 文号). Both are currently weak:
`document_number` is only 25% populated and a naive multi-publisher proxy finds
just 852 docs. Needs a **文号/issuer parser** that extracts agency lists from
document_number and the body header, plus a normalized agency table.

```sql
-- crude current proxy (undercounts badly — motivates the parser)
SELECT COUNT(*) FROM documents
WHERE publisher LIKE '%、%' OR publisher LIKE '%等%';   -- 852
```

**Feasibility.** Medium-low until the parser exists; the raw signal is buried in
body headers, not a clean field. **Threats:** the corpus over-represents single
-agency web portals; joint documents may be published by only one of their signers,
undercounting coalitions. **Positive finding:** a measurable time trend in mean
coalition size and in the joint-issuance share, with recognizable recurring
agency clusters (e.g. 发改委+财政部+工信部).

### Q8. Do genres carry different *authority signatures*? (genre × citation behavior)

**Claim.** Instrument type conditions citation behavior: framework 意见/规定 are
*cited* (authority sinks); implementing 通知/方案 *cite* (authority sources);
explainer/interpretation genres bridge. Genre structure ≈ the division of labor in
the document system.

**Operationalize.** Cross `doc_type`/`algo_doc_type` with in-degree and out-degree
from `citations`. The LLM `doc_type` is usable now, but `algo_doc_type` is 50%
`other`, so a cleaner **genre classifier** sharpens this.

```sql
SELECT d.algo_doc_type,
       AVG((SELECT COUNT(*) FROM citations c WHERE c.target_id=d.id)) avg_in,
       AVG((SELECT COUNT(*) FROM citations c WHERE c.source_id=d.id)) avg_out
FROM documents d
WHERE d.algo_doc_type!='' GROUP BY 1 ORDER BY avg_in DESC;
```

**Feasibility.** Medium — runnable now with caveats; better after a genre pass.
Avoid per-row correlated subqueries at scale — pre-aggregate in/out degree into a
temp table. **Threats:** genre labels are noisy; in/out degree confounded by age
(older docs accrue more inbound). Control for document age. **Positive finding:**
framework genres show high in / low out; implementing genres the reverse — a clean
source/sink separation by genre.

### Q9. Does the corpus show central *signaling* that local documents then amplify? (signaling / echo)

**Claim.** Blame/credit and priority signaling in policy text: when the center
issues a strongly-worded priority document, sub-national echo (citation + lexical
uptake) spikes; the *speed and breadth* of echo measures how loud the signal was.

**Operationalize.** For a set of high-`policy_significance` central docs, measure
(a) inbound resolved citations over the following 24 months and (b) diffusion of
the doc's distinctive terms into sub-national titles. Combine Q2's lag machinery
with a term-uptake series.

**Feasibility.** Medium — needs reliable target dates and better resolution for the
echo count; term-uptake needs a per-doc keyphrase extraction. **Threats:**
significance is LLM-assigned (circular if the model keys on the same cues); echo
undercounted by resolution gaps. **Positive finding:** high-significance central
docs show significantly larger and faster echo than matched low-significance
controls of the same genre and year.

---

## TIER 3 — Aspirational

### Q10. Does *published* policy attention track real-world problems, or substitute for action? (symbolic vs. substantive policy)

**Claim.** The published record may respond to political salience rather than
underlying conditions — a symbolic-politics hypothesis. Testing it requires linking
document series to *external outcome data* (pollution readings, economic
indicators, enforcement statistics) the corpus does not contain.

**Operationalize.** Join issue-attention series (Q1) to exogenous outcome panels by
region-year; test whether attention leads, lags, or is orthogonal to conditions.
**Feasibility.** Aspirational — needs external datasets + a clean region key on
documents (only partially recoverable from `site_key`). **Threats:** ecological
inference, coverage bias in which regions are crawled. **Positive finding:**
attention that tracks political calendar/central signals *better* than it tracks
measured local conditions.

### Q11. Do personnel turnover and career incentives shape document output? (cadre-incentive linkage)

**Claim.** The target-and-tournament view of cadre incentives predicts bursts of
signaling documents around leadership transitions and evaluation cycles. There is a
separate `officials.db` (2,181 officials, career records) that could, in principle,
be joined to locality document output.

**Operationalize.** Align locality/agency document time series with the tenure
windows of their leaders from `officials.db`; look for output spikes at
tenure start / pre-promotion windows. **Feasibility.** Aspirational — the two DBs
lack a shared institution key; `officials.db` is a static April-2026 snapshot of
*central* elites, not local chiefs. **Threats:** severe linkage and coverage gaps.
**Positive finding:** systematic document-output spikes timed to leader tenure
milestones within an institution.

### Q12. Can we detect *quiet policy abandonment* — instruments that stop being cited or are superseded? (policy termination)

**Claim.** Policy termination is understudied because it is rarely announced;
instruments fade (citation death) or are silently superseded. The `is_expired` /
`is_abolished` flags plus a citation-decay measure could surface fade-outs.

**Operationalize.** Track, per anchor instrument, the time series of inbound
citations; flag anchors whose inbound rate collapses after a successor with an
overlapping title/文号 appears. **Feasibility.** Aspirational-to-medium — needs both
higher resolution and a supersession detector; `is_abolished` is sparsely
populated. **Threats:** citation death is confounded by crawl recency (old citers
under-collected). **Positive finding:** identifiable supersession pairs where the
predecessor's inbound citations decay as the successor's rise, without an explicit
abolition notice.

---

## Cross-cutting methodological notes

1. **Always normalize by yearly volume.** The 70× ramp (2000→2025) makes raw
   counts meaningless for trend claims.
2. **Report resolved-only citation metrics as lower bounds**, and check whether a
   result survives restricting to the well-covered site set (Guangdong + Tier-1 +
   central), which has less coverage bias.
3. **Publication date is not adoption date.** For lag work, treat it as an
   upper-bounded proxy and inspect `date_written` where present.
4. **Prefer indexed access paths.** `idx_documents_site`, `idx_citations_target_id`,
   `idx_documents_date`, `idx_documents_citation_rank` are present; avoid full
   `body_text_cn` scans (heavy on the 2-vCPU droplet) — restrict body work to
   pre-filtered candidate sets.
5. **Two feasibility unlocks would move the most questions from Tier 2 to Tier 1:**
   (a) raising citation resolution above ~51% (better title/文号 matching, already
   improving per the coverage tracker), and (b) a clean **genre + issuer/agency**
   classifier to replace 50%-`other` `algo_doc_type` and the 25%-populated 文号.

*Framing note: throughout, describe institutions and observed behavior — attention,
diffusion, citation, coordination — not regime type. The corpus speaks to
mechanisms of how the bureaucracy publishes, echoes, and cites; it does not license
system-level characterizations.*
