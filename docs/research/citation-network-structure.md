# The Citation Network: Authority Concentration, Genre Roles, and Cross-Level Flow

*Research-agenda Q3 (authority concentration) and Q8 (genre as source vs sink), run on the
whole resolved citation graph. This is the corpus-wide counterpart of "Understanding China's
IT Policy System Through Policy Citation Networks" (Systems/MDPI 14(8):957, 2026), which was
built on 33,702 IT-policy documents and 3,150 citation links. Ours is built on 319,208
documents and 279,409 resolved links across all policy domains and four administrative tiers.
Read-only pass over the live `documents.db` on the droplet, 2026-10-01. Backbone chapter for
Part I of `findings-synthesis.md`. The time series of upward/downward citation is in
`recentralization-experimentation.md` and is not redone here.*

*Evidence labels: **[measured]** = computed from the DB in this pass; **[reading]** =
interpretation; **[caveat]** = a known weakness of the measure.*

---

## 0. Short answers

**Q3. Is authority concentrated?** Yes, heavily. **[measured]** The top 1% of nodes (2,392 of
239,187) hold 54.5% of all resolved inbound citations. The top 100 hold 17.2%. The top 10 hold
5.8%. Gini over all nodes is 0.947; over cited nodes only, 0.666. 84% of documents are never
cited at all. The figure is stable across every treatment: 61.6% on corpus documents only,
58.6% at the unpooled document level, 56.7% before the artifact corrections described in §1.
The anchors are what the agenda predicted. Of the top 100, 80 are central, 48 are State
Council or ministerial regulations (条例/办法/规定) and 27 are national laws. The three largest
are 城乡规划法 (1,841 inbound), 政府信息公开条例 (1,537) and 道路交通安全法 (1,164).
*(Re-based 2026-10-07, §8: top 1% 55.4%, Gini 0.948, never cited 83.9%, top 100 84 central and
77 laws or regulations. The claims hold.)*

**Q8. Do genres split into sources and sinks?** Yes, and the split survives an age control.
**[measured]** In the 2018-2020 issue-year band, with body text present, regulations receive
7.3 inbound citations per document and emit 1.6; opinions (意见) receive 2.9 and emit 1.1.
Notices (通知) receive 0.6 and emit 1.1; action plans 0.9 and 1.7; explainers 0.1 and 2.0;
replies 0.06 and 1.0. Laws receive 10.7 in the same band (no body control possible). 62.5% of
all edges point at a framework genre (law, regulation, opinion, strategy, decision, decree);
13.7% originate from one. The division of labor is clean. One exception: 方案/规划 strategy
documents are both cited and citing (2.5 in, 2.1 out).

**Cross-level flow.** **[measured]** 46.4% of resolved edges point upward, 49.4% stay at the
same level, 4.2% point downward. Central documents cite central documents 94% of the time.
Provincial documents cite upward 58% of the time. Municipal documents cite upward 44%, sideways
34%. District documents cite upward 45% (central 35%, provincial 10%), municipal 36%. Central
targets receive 61% of all edges while being 22% of nodes.

**Network shape.** **[measured]** The in-degree tail is power-law-like with exponent 2.2 to
2.5 for the tail above 10 to 50 citations (KS 0.05 to 0.06). About twelve hundred nodes have 20 or
more inbound; 130 have 100 or more; 3 have 1,000 or more. The most cross-topic-central
instrument is 政府信息公开条例: cited from all 29 topics, from 19 of them by ten or more distinct
documents. 行政许可法 is the most evenly spread (normalized entropy 0.83 across 24 topics).

**Artifacts.** **[measured]** 27.0% of resolved edges (68,880) were pointing at the wrong
node. The resolver maps a citation of a national law onto whichever corpus document embeds the
law's name in its title. We re-keyed those edges to the cited instrument. Every number above
is post-correction. The DB's stored `citation_rank` is not corrected and its top of table
still carries these artifacts (§1.3). *(Update 2026-10-01: superseded. The stored `citation_rank`
was recomputed after the exact-title fix (`cd42903`/`c979a82`); its top of table is now framework
law and overlaps this memo's corrected top-30 on 19/30. The containment class with no exact-title
copy in the corpus persists below the top. See the §1.3 note.)*

---

## 1. Data, definitions, and the three artifact corrections

### 1.1 Universe

**[measured]** `documents` joined to `sites`. `admin_level` in {central, provincial,
municipal, department, district}; department (Shenzhen bureaus) folded into municipal. Media
and research sites excluded. `date_published` at least 10 characters, year 2000-2026. Result:
260,334 documents (central 62,300; provincial 63,168; municipal 110,144; district 24,722).
These counts are after the `npc` re-leveling below, which is why they differ from the
`recentralization-experimentation.md` universe (central 85,113 there). *(Note 2026-10-01: each
memo handles npc local regulations differently (counted as central in recentralization, excluded
in joint-issuance, removed as anchors but kept as sources in the atlas, kept in industrial and
attention), so level shares are comparable within a memo only. `consistency-review.md` M7.)*

Edges: `citations` with `target_id IS NOT NULL`, both ends in the universe, self-cites
dropped. 255,018 edges enter the pipeline. Levels come from `sites.admin_level`, never from the
stale `citations.source_level/target_level` columns.

Resolution rate by source level **[measured]**: central 59%, provincial 48%, municipal 51%,
department 56%, district 46%. Every count in this memo is a floor on the true count.

### 1.2 Correction A: `npc` local regulations mis-leveled as central

**[measured]** The `npc` site (国家法律法规数据库) carries 31,070 documents. 28,184 are
`classify_main_name` 地方法规 or 修改、废止的决定（地方法规）: provincial and municipal
people's-congress regulations hosted on a central site. With `sites.admin_level='central'`
they inflate the central tier. We re-level them from `publisher`: 省/自治区/直辖市 人大 to
provincial (11,290 in the dated universe), everything else (市/州/县 人大) to municipal
(12,570). The remaining 2,886 `npc` documents (laws, State Council regulations, judicial
interpretations) stay central.

A second small cue: 1,047 documents whose title begins 中华人民共和国, 国务院 or 中共中央 but
which sit on a sub-national host (mirrors of central instruments) are re-leveled to central.

### 1.3 Correction B: proxy targets (the false-match artifact)

**[measured]** The uncorrected top-of-table is not framework law. It is 河南省实施《中华人民共和
国城乡规划法》办法 (1,855 inbound), a 大鹏新区 news item about 安全生产法 publicity week (663), a
CAC news item about the 网络安全法 amendment (446), a 河源 news item about 百千万工程 (456), and
省政府关于贯彻实施《行政许可法》的通知 from Jiangsu (526). Reading the `target_ref` strings
behind those edges explains it. Of the 2,139 edges into the Henan measure, 2,104 cite
中华人民共和国城乡规划法 or 城乡规划法, and 61% come from Zhongshan planning approvals. The
resolver's title-core fallback matched the law's name inside the Henan title. The law itself
is in the corpus (three copies, two on `npc`) but did not win the match.

The rule we apply: for `named` and `llm` citations, if the normalized cited string is at least
5 characters, differs from the normalized target title, is a strict substring of it, and the
target is not a carrier of the cited text (title of the form 印发/发布/公布/转发/批转《X》的通知),
the edge is re-keyed to the cited string. If a corpus document has that exact normalized title
the edge lands there. Otherwise a virtual node is created for the cited instrument.

Result **[measured]**: 68,880 edges re-keyed (27.0%); 22,011 carrier matches kept. 18,547
re-keyed edges land on an existing corpus document (the national laws recover their inbound).
50,333 land on 16,450 virtual nodes. 11,811 of those virtual nodes have a document-type suffix
(法/条例/办法/意见/纲要 and so on) and carry 32,756 edges; they are kept as nodes. The remaining
4,639 are non-document references (百千万工程 400 edges, 建设工程规划许可证 242, 省委"1310"具体部署
142) and are excluded. Virtual nodes have no body, so they have no out-degree and no date; they
are excluded from the genre out-degree tables and from the age-band tables.

**[caveat]** The rule is heuristic. The level of a virtual node is inferred from its title
(省/自治区 to provincial; 市/县/区 to municipal; 国务院/中共中央/国家 prefix or 法 suffix to
central; document-like with no place marker to central, 4,837 nodes). The genre of a virtual
node comes from its suffix. A reader who distrusts the virtual nodes can use the
"corpus nodes only" figures reported alongside; they move the headline concentration up, not
down.

**[caveat, partly resolved]** *(Update 2026-10-01: the exact-title class of the proxy-target bug this memo found was fixed, commits `cd42903`/`c979a82`, and the stored `citation_rank` was recomputed on the corrected graph: resolved edges 279,409 → 287,607, the law 城乡规划法 recovered its 2,141 citations, and the top-30 by `citation_rank` is now framework law, overlapping this memo's corrected top-30 on 19/30. The fix is not at the root. It can only repair the 18,547 re-keyed edges that land on an existing corpus document. The containment class, the ~50k edges this memo sent to virtual nodes because the cited instrument has no exact-title copy in the corpus, persists in `citations` and `citation_rank`: on 2026-10-01 机动车驾驶证申领和使用规定 still resolves 686 edges to a provincial 热点问题解答 page, 百千万工程 414 to a Guangzhou news item, 建设工程规划许可证 258 to a Shenzhen permit notice. One regression also appeared: 提振消费专项行动方案 (113 edges) now resolves to a Beijing provincial news page whose title is the bare instrument name, and a fix is being applied. See `consistency-review.md` H1. The text below describes the pre-fix state.)* `citation_rank` in the DB was computed on the uncorrected graph. Its top 30
overlaps the corrected inbound top 30 on only 13 entries. The Henan measure, the 大鹏 news
item, the CAC news item and the Jiangsu notice are all still in `citation_rank`'s top 12 with
zero corrected inbound. Any analysis that ranks by `citation_rank` inherits this.

### 1.4 Correction C: mirror pooling and organization-name nodes

**[measured]** Nodes are pooled by normalized title (NFKC, punctuation and brackets removed,
leading 中华人民共和国 removed, trailing 国务院令第N号 removed, minimum 5 characters). 228,469
corpus nodes result from 260,334 documents; 17,640 nodes have more than one copy and 5,147
span more than one site. Pooling matters less for degree than for attribution: the resolver
already concentrates inbound on one copy, but that copy is often on the wrong host. 政府信息
公开条例 has 20 copies on 18 sites and 2,277 of its uncorrected inbound sat on `shb_fgw`, a
Shanghai bureau. The pooled node takes the level of its highest-level copy, so it is central.
Edges are de-duplicated on (source node, target node).

**[caveat]** Title pooling over-merges generic titles across jurisdictions. 政府工作报告 (6
characters) is one node with 139 inbound, pooled across every city that posts one. 市委常委会
召开会议 (298 news items across Jieyang, Heyuan and Zhongshan) is one source node. The effect
on the headline figures is small (pooled vs unpooled top-1% share: 54.5% vs 58.6%) but the
municipal top-10 contains one such over-merged node.

**[measured]** 1,233 nodes are bare organization names (广东省自然资源厅 with 461 inbound,
深圳市住房和建设局 244). These attract matches on institution names, not documents. They carry
3,449 edges and are excluded.

Final analysis graph **[measured]**: 239,187 nodes (227,376 corpus, 11,811 virtual), 163,814
edges.

---

## 2. Authority concentration (Q3)

### 2.1 Corpus-wide

**[measured]** Inbound degree over the 239,187 pooled nodes:

| Measure | Pooled, corrected | Corpus nodes only | Unpooled doc-level | Uncorrected (v1) |
|---|---|---|---|---|
| Nodes | 239,187 | 227,376 | 258,573 | 231,640 |
| Nodes with inbound ≥1 | 15.8% | 11.4% | 13.1% | 14.1% |
| Gini, all nodes | 0.947 | 0.965 | 0.960 | 0.955 |
| Gini, cited nodes | 0.666 | 0.692 | 0.692 | 0.683 |
| Share held by top 0.1% | 24.8% | 29.2% | 27.2% | 25.8% |
| **Share held by top 1%** | **54.5%** | **61.6%** | **58.6%** | **56.7%** |
| Share held by top 10 | 5.8% | 7.3% | 5.8% | 5.9% |
| Share held by top 100 | 17.2% | 21.0% | 18.3% | 18.1% |
| Share held by top 1,000 | 41.6% | 48.5% | 43.9% | n/a |
| Max inbound | 1,841 | 1,841 | 1,883 | 1,855 |

The threshold to enter the top 1% is 11 inbound citations. The median cited node has 1. The
90th percentile of cited nodes has 7. **[reading]** The concentration is not an artifact of
pooling, of the proxy correction, or of the virtual nodes. All four treatments agree within
seven points, and the corrections push the figure down, not up.

### 2.2 Who the top 1% are

**[measured]** The 2,392 nodes in the top 1%: 1,580 central, 442 provincial, 348 municipal,
22 district. Edge-weighted, central nodes hold 73.2% of top-1% inbound. By genre: regulation
860, law 287, opinion 285, policy_issuance 249, notice 214, action_plan 111, strategy 105.
Edge-weighted: regulation 42.9%, law 20.1%, opinion 7.3%, policy_issuance 7.1%, strategy 5.3%,
notice 5.2%. Framework genres (law, regulation, opinion, strategy, decision, decree) are 67% of
the top 1% by count and 78.2% by inbound mass. Issue-year quartiles of the top 1%: 2013, 2017,
2021.

The top 100: 80 central, 10 provincial, 10 municipal; 48 regulations, 27 laws, 10 strategies,
7 policy issuances. 10 of the 100 are virtual nodes.

### 2.3 Top 30 by corrected inbound

**[measured]** Level, genre and year are those of the representative copy.

*(Label 2026-10-07: this is the 2026-10-01 table, kept as published. The re-based table on the
341,313-document graph is §8.2. Neither of the two changes re-based there moves this table's
counts; corpus growth does.)*

| # | Instrument | Level | Genre | Year | Inbound |
|---|---|---|---|---|---|
| 1 | 中华人民共和国城乡规划法 | central | law | 2015 (rev.) | 1,841 |
| 2 | 中华人民共和国政府信息公开条例 | central | regulation | 2021 copy | 1,537 |
| 3 | 中华人民共和国道路交通安全法 | central | law | 2011 (rev.) | 1,164 |
| 4 | 广东省城乡规划条例 | provincial | regulation | 2012 | 969 |
| 5 | 城市、镇控制性详细规划编制审批办法 | central | regulation | 2010 | 913 |
| 6 | 财政违法行为处罚处分条例 | central | regulation | 2011 copy | 774 |
| 7 | 广东省城市控制性详细规划管理条例 | provincial | regulation | 2014 | 674 |
| 8 | 中华人民共和国安全生产法 | central | law | 2014 (rev.) | 663 |
| 9 | 中华人民共和国突发事件应对法 | central | law | 2007 | 531 |
| 10 | 中华人民共和国行政许可法 | central | law | 2003 | 522 |
| 11 | 社会团体登记管理条例 | central | regulation | 2016 | 506 |
| 12 | 中山市国土空间总体规划（2021-2035年）印发通知 | municipal | strategy | 2025 | 487 |
| 13 | 国有土地上房屋征收与补偿条例 | central | regulation | 2011 | 455 |
| 14 | 中华人民共和国土地管理法 | central | law | 2004 | 454 |
| 15 | 中华人民共和国网络安全法 | central | law | 2016 | 440 |
| 16 | 中华人民共和国食品安全法 | central | law | 2015 | 392 |
| 17 | 建设用地容积率管理办法 | central | regulation | 2012 | 368 |
| 18 | 深圳市保障性住房条例 | municipal | regulation | 2011 | 364 |
| 19 | 机动车驾驶证申领和使用规定 (virtual) | central | regulation | n/a | 351 |
| 20 | 粤港澳大湾区发展规划纲要 | central | strategy | 2019 | 331 |
| 21 | 广东省突发事件应对条例 | provincial | regulation | 2010 | 314 |
| 22 | 中华人民共和国文物保护法 | central | law | 2017 | 311 |
| 23 | 十四五规划和2035年远景目标纲要 | central | strategy | 2021 | 303 |
| 24 | 中国共产党纪律处分条例 | provincial host | regulation | 2023 | 294 |
| 25 | 中华人民共和国个人信息保护法 | central | law | 2021 | 286 |
| 26 | 重大行政决策程序暂行条例 | central | regulation | 2019 | 272 |
| 27 | 中华人民共和国出境入境管理法 | central | law | 2012 | 268 |
| 28 | 建设工程质量管理条例 | central | regulation | 2019 copy | 261 |
| 29 | 中华人民共和国外国人入境出境管理条例 | central | regulation | 2013 | 260 |
| 30 | 中华人民共和国土地管理法实施条例 | central | regulation | 2021 | 256 |

**[reading]** Twenty-two of the thirty are national laws or central (State Council or ministerial) regulations. The
provincial entries are Guangdong planning and emergency regulations. The municipal entries are
Shenzhen special-zone regulations and one Zhongshan land-use plan. This is the predicted shape:
the stock of authority is framework law and the regulations directly beneath it.

**[caveat]** Site composition drives the ordering inside the top 10. 61% of citations to
城乡规划法 come from Zhongshan, 88% of citations to 广东省城乡规划条例 come from Zhongshan, and
100% of citations to 城市、镇控制性详细规划编制审批办法 come from Zhongshan. These are planning
approvals that recite the legal basis in every notice. 82% of citations to 道路交通安全法 come
from the Shenzhen public-security site's vehicle notices. By contrast 政府信息公开条例 is cited
from 115 sites with no site above 13%, 行政许可法 from 102 sites (max 14%), 安全生产法 from 86
(max 14%). Rank 1 is a Zhongshan artifact of breadth; rank 2 is the broadest-based anchor in
the corpus. 中国共产党纪律处分条例 (rank 24) is a Party rule mirrored on a Fujian bureau site
with no central copy; its level is a hosting artifact.

### 2.4 Concentration within level

**[measured]** Target-level subgraphs (nodes of that level, edges into them):

| Target level | Nodes | Cited ≥1 | Edges in | Edges per node | Gini (cited) | Top 1% share | Top 100 share | Max |
|---|---|---|---|---|---|---|---|---|
| central | 58,090 | 27.9% | 100,389 | 1.73 | 0.718 | 48.7% | 24.9% | 1,841 |
| provincial | 57,308 | 15.0% | 30,558 | 0.53 | 0.596 | 46.3% | 24.4% | 969 |
| municipal | 101,099 | 12.1% | 31,477 | 0.31 | 0.534 | 48.1% | 21.1% | 487 |
| district | 22,690 | 3.5% | 1,844 | 0.08 | 0.468 | 65.1% | 47.2% | 51 |

Central targets receive 61.0% of all edges while being 22.3% of nodes. Municipal targets are
42.3% of nodes and receive 19.2%. District targets are 9.5% of nodes and receive 1.1%.

**[reading]** Concentration is about as steep inside each tier as across the whole (top 1%
near half in each of the three upper tiers). The tiers differ in how much authority they hold
at all, not in how it is distributed within them. A central document is eight times more likely
than a district document to be cited even once. **[caveat]** District under-citation is partly
coverage: district sites are Shenzhen, Beijing, Nanjing, Wuhan and Chongqing districts only,
and resolution for district sources is the lowest (46%).

### 2.5 Within-level anchors

**[measured]** Provincial top 5: 广东省城乡规划条例 (969), 广东省城市控制性详细规划管理条例 (674),
广东省突发事件应对条例 (314), 中国共产党纪律处分条例 (294, hosting artifact), 广东省事业单位公开
招聘人员体检实施细则（试行）(245). Municipal top 5: 中山市国土空间总体规划 notice (487), 深圳市
保障性住房条例 (364), 中山市国土空间规划技术标准与准则（2023版）(255, virtual), 深圳经济特区政府
采购条例 (209), 深圳市科技计划项目管理办法 notice (198). District top 3: a 龙华 copy of the
Guangdong 2025 事业单位招聘公告 (51), 龙岗区科技创新专项资金管理办法 (32), 坪山区服务业高质量发展
资金支持措施 (31). **[reading]** Below the provincial tier the anchors are money and permits:
funding measures, procurement rules, housing allocation, planning standards. Framework genres
dominate at the top and in the provincial tier; operational genres dominate the municipal and
district anchors.

---

## 3. Genre as source vs sink (Q8)

### 3.1 All years, corpus nodes

**[measured]** Mean inbound and outbound degree per pooled corpus node, genres with 200 or
more nodes, sorted by in/out ratio. `body` is the share of nodes with body text; out-degree
can only be observed where there is a body.

| Genre | n | mean in | mean out | P(in≥1) | P(out≥1) | body | in/out |
|---|---|---|---|---|---|---|---|
| law | 507 | 28.51 | 0.29 | 0.30 | 0.20 | 0.54 | 96 |
| regulation | 19,669 | 2.37 | 0.36 | 0.26 | 0.18 | 0.22 | 6.5 |
| opinion (意见) | 3,874 | 2.54 | 1.09 | 0.45 | 0.54 | 0.98 | 2.3 |
| strategy (规划/纲要) | 3,003 | 1.57 | 1.62 | 0.29 | 0.59 | 0.96 | 1.0 |
| policy_issuance (印发…通知) | 14,279 | 1.26 | 1.77 | 0.38 | 0.65 | 0.98 | 0.71 |
| notice (通知) | 26,367 | 0.55 | 1.03 | 0.19 | 0.49 | 0.96 | 0.54 |
| action_plan (方案) | 8,789 | 0.81 | 1.55 | 0.31 | 0.70 | 0.96 | 0.52 |
| decision (决定) | 4,534 | 0.67 | 1.46 | 0.11 | 0.48 | 0.40 | 0.46 |
| announcement (公告) | 15,706 | 0.37 | 1.10 | 0.11 | 0.55 | 0.97 | 0.34 |
| work_plan | 1,862 | 0.49 | 1.45 | 0.20 | 0.58 | 0.99 | 0.35 |
| subsidy | 3,128 | 0.18 | 0.80 | 0.07 | 0.45 | 0.96 | 0.23 |
| report | 1,612 | 0.15 | 2.23 | 0.02 | 0.73 | 0.96 | 0.07 |
| reply (批复/函) | 10,140 | 0.05 | 0.97 | 0.03 | 0.41 | 0.95 | 0.06 |
| explainer (解读) | 11,647 | 0.07 | 1.63 | 0.04 | 0.80 | 0.76 | 0.05 |
| circular | 2,287 | 0.03 | 0.77 | 0.02 | 0.40 | 0.93 | 0.05 |
| other | 74,726 | 0.04 | 0.29 | 0.01 | 0.17 | 0.92 | 0.16 |

**[caveat]** Regulation and law are mostly metadata-only `npc` records (body 22% and 54%),
so their out-degree is structurally under-observed. Their inbound is not affected. The
age-controlled table below restricts to nodes with body text so the out-degree column is
comparable across genres.

### 3.2 Age control: 2018-2020 issue years, body text present

**[measured]** Genres with 100 or more nodes.

| Genre | n | mean in | mean out | P(in≥1) | P(out≥1) | in/out |
|---|---|---|---|---|---|---|
| regulation | 664 | 7.29 | 1.58 | 0.57 | 0.71 | 4.6 |
| opinion | 772 | 2.85 | 1.07 | 0.47 | 0.55 | 2.6 |
| strategy | 226 | 2.47 | 2.05 | 0.22 | 0.68 | 1.2 |
| policy_issuance | 2,864 | 1.47 | 1.77 | 0.43 | 0.66 | 0.83 |
| notice | 4,700 | 0.62 | 1.08 | 0.21 | 0.52 | 0.58 |
| action_plan | 1,579 | 0.92 | 1.65 | 0.34 | 0.73 | 0.56 |
| announcement | 2,223 | 0.63 | 1.31 | 0.14 | 0.70 | 0.48 |
| decision | 375 | 1.12 | 3.94 | 0.25 | 0.69 | 0.29 |
| work_plan | 343 | 0.46 | 1.81 | 0.24 | 0.62 | 0.26 |
| explainer | 1,040 | 0.14 | 1.96 | 0.04 | 0.87 | 0.08 |
| reply | 1,473 | 0.06 | 0.98 | 0.04 | 0.46 | 0.07 |
| circular | 358 | 0.03 | 0.90 | 0.02 | 0.46 | 0.04 |
| report | 177 | 0.79 | 2.61 | 0.01 | 0.80 | 0.30 |

Inbound-only, same band, no body filter (so laws appear): law 10.73 (n=89), opinion 2.80,
strategy 2.44, regulation 2.06 (n=3,661, mostly bodyless `npc` local regulations),
policy_issuance 1.47, action_plan 0.90, notice 0.61.

Same table for 2010-2012 (older cohort): regulation 10.96 in / 1.33 out; opinion 1.92 / 1.20;
notice 0.59 / 0.94; strategy 1.08 / 1.78; policy_issuance 0.87 / 1.51; action_plan 0.65 /
1.74; explainer 0.06 / 1.52. And for 2023-2025 (young cohort): regulation 3.93 / 1.63; strategy
2.67 / 1.51; opinion 1.63 / 0.94; policy_issuance 0.86 / 1.89; action_plan 0.73 / 1.49; notice
0.34 / 1.28.

**[reading]** The ordering is the same in all three cohorts. Regulations sit at the top of the
inbound column in every band and their in/out ratio is above 2 in every band. Opinions are
second in every band. Notices, action plans, announcements, explainers and replies emit more
than they receive in every band. Age changes the magnitudes (a 2010-2012 regulation has had
fifteen years to accumulate citations, a 2023-2025 one two) but not the roles. The split is a
genre property, not an age property.

### 3.3 The map

**[measured]** Share of all clean edges by target genre: regulation 31.5%, law 14.8%, notice
10.9%, policy_issuance 10.9%, opinion 8.7%, action_plan 6.2%, strategy 5.1%, announcement 3.9%.
By source genre: notice 15.7%, policy_issuance 14.7%, other 10.9%, explainer 10.4%,
announcement 10.0%, action_plan 7.9%, reply 5.2%, regulation 4.2%, decision 4.0%, strategy 2.7%.
Framework genres are the target of 62.5% of edges and the source of 13.7%.

Largest genre-to-genre flows (share of all edges): policy_issuance to regulation 5.3%; notice
to notice 3.9%; other to regulation 3.7%; notice to regulation 3.6%; announcement to regulation
3.0%; explainer to regulation 2.5%; policy_issuance to policy_issuance 2.5%; reply to regulation
2.4%; policy_issuance to law 2.3%; decision to regulation 2.2%; announcement to law 2.2%.

Genre by level, 2018-2020 with body, mean in / mean out: regulation central 10.9 / 1.6,
provincial 4.1 / 1.4, municipal 5.0 / 1.6. Opinion central 3.7 / 1.0, provincial 1.1 / 1.2,
municipal 0.8 / 1.3. Policy issuance central 1.7 / 1.3, provincial 1.4 / 2.0, municipal 1.2 /
2.3, district 1.3 / 2.3. Notice central 0.8 / 1.0, provincial 0.4 / 0.9, municipal 0.3 / 1.3.
Decision central 1.6 / 3.1.

**[reading]** Three roles. **Sinks**: laws, regulations and opinions. They are cited and
rarely cite (the opinion genre does cite, but at half its inbound rate). **Sources**: notices,
printing-and-issuing notices, action plans, announcements, replies, explainers. They cite and
are rarely cited; explainers are the purest source (87% emit, 4% receive). **Both**: strategy
documents (五年规划纲要, regional outlines) and central decisions, which are cited by implementers
and themselves cite laws and prior plans. The genre pattern is the division of labor in a
document system in which authority is borrowed from a small stock of framework texts and
exercised through a large flow of operational ones. The same regulation at central level
receives twice what the same genre receives at provincial level; the genre effect and the level
effect stack.

**[caveat]** `algo_doc_type` is a title regex. 37% of the universe is `other` and the genre
of a 关于印发《X办法》的通知 is `policy_issuance` whether X is a framework measure or a
funding rule. The sink role of regulations is partly a label for "the text being issued," and
some of the printing-notice inbound is really inbound to the measure it carries (the carrier
rule in §1.3 keeps those together deliberately).

---

## 4. Cross-level flow matrix

**[measured]** Share of each source level's edges by target level, after all corrections.
n = 163,814.

| source → target | central | provincial | municipal | district |
|---|---|---|---|---|
| central (n=44,953) | 0.944 | 0.029 | 0.026 | 0.000 |
| provincial (n=43,907) | 0.579 | 0.321 | 0.099 | 0.000 |
| municipal (n=65,735) | 0.440 | 0.215 | 0.344 | 0.001 |
| district (n=9,219) | 0.346 | 0.105 | 0.360 | 0.188 |

As a share of all edges: central→central 25.9%, municipal→central 17.7%, provincial→central
15.5%, municipal→municipal 13.8%, provincial→provincial 8.6%, municipal→provincial 8.6%,
provincial→municipal 2.6%, district→municipal 2.0%, district→central 1.9%, district→district
1.1%. Direction: upward 46.4%, same level 49.4%, downward 4.2%. Of same-level edges between
corpus documents, 57.3% stay inside one jurisdiction family (a Beijing bureau citing the
Beijing government); 42.7% cross to a peer.

For comparison, the uncorrected doc-level matrix on raw `sites.admin_level` gives central
0.837 / 0.114 / 0.043 / 0.006; provincial 0.512 / 0.402 / 0.076 / 0.010; municipal 0.436 /
0.216 / 0.338 / 0.010; district 0.296 / 0.183 / 0.239 / 0.283; upward 43.3%, downward 7.2%.
The two corrections move the matrix in opposite directions. Re-leveling `npc` local
regulations moves targets out of the central column. Re-keying proxy matches moves national-law
citations from provincial proxies into the central column. Net, the upward share rises three
points and the downward share nearly halves.

What is cited when a document cites upward to central **[measured]**: regulation 28.0%, law
18.9%, notice 11.9%, opinion 11.6%, policy_issuance 8.6%, strategy 5.2%.

**[reading]** The static structure is a ladder with almost no rungs pointing down. Central
documents cite only central documents. Each lower tier splits its citations between the
center and itself, with the provincial tier the most center-facing (58%) and the municipal tier
the most self-referential (34%). Provinces are cited by municipalities (8.6% of all edges) far
more than they cite municipalities (2.6%). Districts cite their municipality (36%) about as
much as the center (35%) and the province hardly at all (10%); the district's authority
environment is its city plus national law. The 4.2% downward flow is almost entirely central
documents citing specific provincial or municipal documents in approvals and replies (央地
批复) and mirror artifacts. The time path of these shares is in
`recentralization-experimentation.md` §2.

**[caveat]** Resolution is lowest for district and provincial sources (46%, 48%). Virtual
nodes have inferred levels (§1.3). The provincial column is Guangdong-heavy because most
municipal sources are Guangdong cities citing Guangdong regulations.

---

## 5. Network shape

### 5.1 Degree distribution

**[measured]** In-degree over 239,187 nodes: mean 0.69, variance 76.5, maximum 1,841. 15.8%
of nodes have at least one inbound citation. Complementary CDF: P(≥2) 7.3%, P(≥5) 2.6%,
P(≥10) 1.14% (2,734 nodes), P(≥20) 0.51% (1,219), P(≥50) 0.15% (364), P(≥100) 0.054%
(130), P(≥200) 45 nodes, P(≥500) 11, P(≥1000) 3.

Discrete power-law MLE on the in-degree tail: exponent 2.21 for x≥10 (n=2,734, KS 0.060),
2.35 for x≥20 (n=1,219, KS 0.055), 2.45 for x≥50 (n=364, KS 0.049). The log-log CCDF slope
from 10 to 1,000 is -1.48, consistent with an exponent near 2.5. The tail above 5 is also
describable as lognormal (log-mean 2.39, log-sd 0.81); we did not run a formal likelihood
ratio test. **[reading]** The tail is heavy and scale-free-like in the range that matters (10
to 1,000 citations), with exponent between 2 and 3, so the mean is finite and the variance is
not. This is the same regime reported for legal and patent citation networks. **[caveat]** The
corpus is young at the bottom: 44,642 universe documents are dated 2026 and the mean inbound of
a 2024-2026 document is 0.14 to 0.23, against 1.4 to 2.2 for 2008-2016 documents. The tail is
made of documents that have had time to be cited. A re-run in five years will show a longer
tail with the same exponent, not a different shape.

Out-degree over corpus nodes: 36.7% have at least one outbound; P(≥5) 2.6%, P(≥10) 0.35%,
P(≥50) 59 nodes, maximum 328. Among nodes with body text the mean is 0.89 and the median 0.
**[reading]** Out-degree is bounded by how many instruments a document can recite; in-degree
is not bounded. That asymmetry is the whole shape.

### 5.2 Components and roles

**[measured]** 100,090 nodes have at least one edge. The giant weakly connected component
holds 82,935 of them (82.9% of connected nodes, 34.7% of all nodes). There are 6,824
components; the second largest has 150 nodes. Reciprocity is 1.2%. Of the connected nodes,
15,474 both cite and are cited, 22,327 are cited only (pure sinks), 67,984 cite only (pure
sources). Correlation between inbound degree and the number of topics citing a node (≥3 citing
documents per topic), among nodes with 20 or more inbound: 0.64.

### 5.3 Bridge instruments: cross-topic reach

**[measured]** For each target node, the topics (`topics_algo`, 29 subject topics) of the
documents citing it. 72% of pooled edges have a topic-tagged source. `n10` is the number of
topics from which at least ten distinct documents cite the node; `H` is the normalized entropy
of the topic distribution of citers (1 = evenly spread over all 29).

| Instrument | Level | Genre | Inbound | Topics (any) | Topics ≥3 | Topics ≥10 | H |
|---|---|---|---|---|---|---|---|
| 政府信息公开条例 | central | regulation | 1,537 | 29 | 25 | 19 | 0.60 |
| 财政违法行为处罚处分条例 | central | regulation | 774 | 27 | 26 | 18 | 0.69 |
| 行政许可法 | central | law | 522 | 24 | 21 | 17 | 0.83 |
| 道路交通安全法 | central | law | 1,164 | 23 | 21 | 15 | 0.45 |
| 城乡规划法 | central | law | 1,841 | 22 | 21 | 14 | 0.78 |
| 十四五规划和2035年远景目标纲要 | central | strategy | 303 | 24 | 23 | 13 | 0.85 |
| 安全生产法 | central | law | 663 | 25 | 24 | 12 | 0.60 |
| 粤港澳大湾区发展规划纲要 | central | strategy | 331 | 26 | 20 | 12 | 0.83 |
| 突发事件应对法 | central | law | 531 | 24 | 18 | 11 | 0.50 |
| 军人抚恤优待条例 | central | regulation | 150 | 16 | 11 | 10 | 0.65 |
| 社会团体登记管理条例 | central | regulation | 506 | 24 | 19 | 9 | 0.49 |
| 中国共产党纪律处分条例 | (prov. host) | regulation | 294 | 23 | 17 | 9 | 0.65 |
| 深圳市行政机关规范性文件管理规定 | municipal | regulation | 126 | 23 | 15 | 8 | 0.80 |
| 网络安全法 | central | law | 440 | 27 | 13 | 7 | 0.53 |
| 重大行政决策程序暂行条例 | central | regulation | 272 | 18 | 13 | 7 | 0.68 |
| 优化营商环境条例 | central | regulation | 204 | 23 | 13 | 7 | 0.69 |
| 中小企业划型标准规定 | central | regulation | 209 | 21 | 19 | 7 | 0.69 |

The most evenly spread instruments with 100 or more inbound: 标准化法实施条例 (H 0.89, 19
topics with ≥3), the three Five-Year Plan outlines (13th, 14th, 15th: H 0.84-0.85), 行政许可法
(0.83), 粤港澳大湾区发展规划纲要 (0.83), 政府采购法实施条例 (0.82), 深圳经济特区政府采购条例
(0.81), 中共中央关于进一步全面深化改革推进中国式现代化的决定 (0.80).

The narrowest instruments with 150 or more inbound: 苏州市国有土地上房屋征收与补偿暂行办法 (H
0.08, 2 topics), 深圳市科技计划项目管理办法 (0.14), 机动车驾驶证申领和使用规定 (0.21), 深圳市保障
性住房条例 (0.23), 国有土地上房屋征收与补偿条例 (0.24), 文物保护法 (0.29), the tax laws
(企业所得税法 0.32, 税收征收管理法 0.38).

Of the 50 nodes cited from five or more topics by ten or more documents each: 25 regulations,
15 laws, 6 strategies, 2 opinions, 1 decision, 1 notice; 42 central, 6 provincial, 2 municipal.

**[reading]** Two kinds of bridge. *Procedural* bridges are rules about how government acts
regardless of subject: information disclosure, administrative licensing, fiscal discipline,
major-decision procedure, normative-document management, procurement, standardization. They
are cited from every domain because every domain has to disclose, license, spend and
standardize. *Programmatic* bridges are the planning outlines (Five-Year Plans, the Greater
Bay Area outline) that every sector cites as its mandate. The single most cross-topic-central
instrument is 政府信息公开条例: cited from all 29 topics, from 19 of them by ten or more
distinct documents (1,048 of its citers are Government-topic, then Infrastructure 183, Legal
153, Tech 87, Finance 77, Health 59). 行政许可法 is the most evenly spread bridge (Transport
81, Safety 51, Government 48, Infrastructure 41, Environment 35). 财政违法行为处罚处分条例
reaches 26 topics at three or more citers because every funding measure in every sector cites
it as the sanction clause. Sectoral laws (文物保护法, the tax laws) and local operational
rules are narrow however many citations they receive. Breadth is a property of procedural and
programmatic instruments; depth alone does not confer it.

**[caveat]** `topics_algo` is a keyword tagger with 29 coarse topics and is missing on 28% of
source documents. Government is the largest topic and inflates H for procedural rules. The
Zhongshan and Shenzhen site effects (§2.3) also shape which nodes reach 10 citers per topic.

---

## 6. What a 248k-edge, all-tier graph shows that a 3,150-link, single-domain graph cannot

**[reading]**

1. **The tail can be estimated.** A power-law exponent needs thousands of nodes above the
   cut-off. We have 2,734 nodes with ten or more citations and 364 with fifty or more. A
   3,150-link graph has at most a few dozen nodes above ten. The Systems paper can report
   that citations are skewed; it cannot say the exponent is 2.2 to 2.5 or that the shape is
   stable across issue-year cohorts.
2. **Bridges are invisible inside one domain.** 政府信息公开条例, 行政许可法 and 财政违法行为
   处罚处分条例 are the spine of the network precisely because they are cited from 24 to 29
   topics. Inside an IT-only corpus they would appear as occasional out-of-domain references,
   if they appeared at all. The finding that procedural law is the main cross-sector
   connective tissue requires all domains in one graph.
3. **The level matrix needs the lower tiers.** The ladder structure (central cites central;
   each tier splits between the center and itself; districts face their city and national law,
   not their province) is a four-row matrix. PKULaw-based corpora stop at the provincial
   tier, and the Systems paper's spatio-temporal analysis is provincial. The district row and
   the municipal self-citation share are new.
4. **Genre roles need an age control and a body control.** With 664 regulations and 4,700
   notices in a single three-year band we can show the source/sink split is not an age
   artifact. With 3,150 links no band is large enough.
5. **Artifacts become measurable instead of hand-checked.** At 3,150 links a research team
   reads every edge. At 279,409 they cannot, and the result is a measured 27% proxy-match rate
   and a 23,860-document mis-leveling that would otherwise have put a Henan implementation
   measure and a district news item at the top of the authority ranking. The scale forces the
   method to be explicit about what a "resolved" edge is. That is a cost, and this memo pays
   it in §1; it is also a finding about what citation-matching at corpus scale does.
6. **The IT-domain graph is a subset of ours.** The Tech topic subgraph of this network is
   the direct replication target for the Systems paper and can be cut from the same tables
   with one filter on `topics_algo`. That is not done here.

What the smaller graph has that ours lacks: hand-verified edges, 100% resolution within its
universe, and a national coverage of provinces that our Guangdong-heavy sub-national tier does
not match.

---

## 7. Caveats, collected

- **Resolution 52%.** Every count is a floor. Resolution is 59% for central sources and 46%
  for district sources, so the upward share and the central inbound share are both
  under-stated at the bottom tiers rather than over-stated.
- **Coverage.** Sub-national sources are dominated by Guangdong cities, Shenzhen bureaus and
  districts, plus Beijing, Shanghai, Jiangsu, Suzhou, Wuhan, Chongqing. Three of the top ten
  anchors owe more than 60% of their inbound to one site. The provincial column of the flow
  matrix is largely Guangdong.
- **Age.** Mean inbound falls from about 1.5 for 2010-2016 documents to 0.14 for 2026
  documents. Section 3.2 controls for it by issue-year band; sections 2 and 5 do not and
  should be read as the state of the graph on 2026-10-01, not as a steady state.
- **SUPERSEDED 2026-10-09 — use `instrument_inbound`, not this memo's own pooling.** The
  title-based five-character minimum below is a known defect (CLAUDE.md's length-floor family):
  中华人民共和国民法典 and 中华人民共和国预算法 fold to **three** characters once 中华人民共和国 is
  stripped, so the memo's own statistics never pooled the most-cited texts in the corpus. The
  production table `instrument_inbound` (built in `scripts/build_site_stats.py`) pools via
  `doc_identity.instrument_id` with no folded-title floor, **drops pool-level self-citations** (a
  mirror citing its own sibling, 8,871 of them, which a title-pooled node cannot detect because
  `source_id != target_id` holds for every such edge), and carries the shared-文号 override added
  the same day.

  **Re-measured on that basis, and the Q3 headline is confirmed and slightly STEEPER:**

  | | this memo | instrument basis |
  |---|---|---|
  | nodes | 239,187 (incl. 11,811 virtual) | 331,152 instruments |
  | top 1% share | 54.5% pooled / **61.6%** corpus-nodes-only | **62.5%** |
  | top 100 | 17.2% | **17.4%** |
  | top 10 | — | 5.2% |
  | threshold to enter top 1% | 11 inbound | **12** |
  | median cited node | 1 | **2** |
  | Gini | 0.948 (re-based) | **0.965** |
  | never cited | 83.9% | **87.7%** |

  The comparable row is *corpus nodes only*, since the instrument basis has no virtual nodes.
  **What the floor was costing:** 民法典 holds **413 inbound across 7 copies, of which only 1
  carried weight** — six copies invisible to the memo's pooling; 预算法 512; 城乡规划法 2,081
  across 2. The concentration claim rests on exactly those top nodes, so it was understated. That
  the corrected figure moves **up** rather than down is the reassuring direction: fixing a defect
  that suppressed top-node weight should concentrate the distribution further, and it does.

- **Mirror pooling (the superseded method).** Title-based, five-character minimum. It fixes level attribution for
  mirrored central instruments and over-merges generic titles across cities (政府工作报告).
  The headline concentration moves four points between pooled and unpooled.
- **Proxy re-keying.** A heuristic applied to 27% of edges. Virtual-node level and genre are
  inferred from the cited string. Corpus-only figures are reported alongside; they are higher.
- **`citation_rank` is uncorrected.** The DB column still ranks proxy targets at the top.
  Its top 30 overlaps the corrected inbound top 30 on 13 entries. *(Update 2026-10-01:
  superseded. Recomputed after the exact-title fix; the top is now framework law, overlap
  19/30. Containment proxies without an exact-title copy in the corpus persist below the
  top. See §1.3.)*
- **Scope boundary.** Coverage bias (Guangdong over-represented at district depth, proxy-blocked
  provinces invisible), ~52% resolution so every count is a floor, and a static graph that
  records published references, not adoption. Claims are mechanism-level about a document
  record. No regime-type labels. *(Added 2026-10-01 per `consistency-review.md` §2.)*
- **Genre labels.** `algo_doc_type` is a title regex; 37% `other`. Laws and most regulations
  are metadata-only, so their out-degree is unobservable; out-degree comparisons are
  restricted to nodes with body text.
- **Topics.** `topics_algo` is a 29-topic keyword tagger present on 72% of citing documents.
- **No formal lognormal test.** The power-law exponents are MLE fits with KS distances; a
  lognormal was fitted but not compared by likelihood ratio.

---

## Appendix: SQL and procedure

All SQL run against `file:/root/china-governance/documents.db?mode=ro`.

**Extract (documents).**
```sql
SELECT d.id, d.site_key, s.admin_level, d.algo_doc_type, d.topics_algo,
       substr(d.date_published,1,10) AS date_published, d.citation_rank, d.title,
       d.publisher, d.classify_main_name,
       (d.body_text_cn IS NOT NULL AND length(d.body_text_cn)>0) AS has_body
FROM documents d LEFT JOIN sites s ON s.site_key = d.site_key;
```

**Extract (resolved edges with the cited string).**
```sql
SELECT source_id, target_id, citation_type, target_ref
FROM citations WHERE target_id IS NOT NULL;          -- 279,409 rows of 533,278
```

**Resolution by source level.**
```sql
SELECT s.admin_level, COUNT(*) total, SUM(c.target_id IS NOT NULL) resolved
FROM citations c JOIN documents d ON d.id=c.source_id JOIN sites s ON s.site_key=d.site_key
GROUP BY 1;
-- central 132,302/77,739; provincial 142,896/68,680; municipal 153,927/77,979;
-- department 52,724/29,528; district 33,104/15,264
```

**`npc` local regulations (Correction A).**
```sql
SELECT classify_main_name, COUNT(*) FROM documents WHERE site_key='npc' GROUP BY 1;
-- 地方法规 26,091; 修改、废止的决定（地方法规） 2,072; 行政法规 832; 法律 476; ...
-- re-level by publisher: '(省|自治区|北京市|上海市|天津市|重庆市)(人民代表大会|人大)' -> provincial, else municipal
```

**Proxy-target diagnosis (Correction B), example.**
```sql
SELECT c.target_ref, COUNT(*) FROM citations c
WHERE c.target_id = (SELECT id FROM documents WHERE title='河南省实施《中华人民共和国城乡规划法》办法')
GROUP BY 1 ORDER BY 2 DESC;
-- 中华人民共和国城乡规划法 1,860; 《中华人民共和国城乡规划法》 243; 城乡规划法 32; ...
SELECT id, site_key FROM documents WHERE title IN ('中华人民共和国城乡规划法','城乡规划法');
-- 3 rows (mee, npc, npc): the law is in the corpus and did not win the match
```

**Procedure (Python, pandas/networkx, on the extract).**
1. Universe filter as §1.1; `department` folded to `municipal`; `npc` re-level by publisher;
   title-cue re-level to central.
2. `canon(title)`: NFKC, lowercase, strip punctuation and brackets, strip leading
   中华人民共和国, strip trailing 国务院令第N号. Pool key = canon title if ≥5 characters else
   the document id.
3. For each resolved `named`/`llm` edge: `rk = canon(target_ref)`, `tk = canon(target
   title)`. If `len(rk) ≥ 5 and rk != tk and rk in tk` and `tk` does not match
   `(印发|发布|公布|转发|批转){rk}(的通知|的公告|的决定|的函|的令|的通告)?$`, re-key the target to
   the pool whose canon title equals `rk`, or to a virtual node `v:rk`.
4. Drop self-loops, de-duplicate on (source pool, target pool). Drop organization-name nodes
   (`^(中共)?[一-鿿]{2,14}(厅|局|委员会|办公室|部|署|院|委|政府|总队|支队|大队|中心)$`
   with no document keyword) and virtual nodes with no document-type suffix.
5. Node level = level of the highest-level copy; genre = `algo_doc_type` of that copy; year =
   its `date_published`. Virtual node level and genre inferred from the cited string.
6. In-degree, out-degree, Gini, top-k shares, per-level subgraphs, discrete power-law MLE
   (`alpha = 1 + n / sum(ln(x/(xmin-0.5)))`) with KS distance, weakly connected components,
   topic breadth per target from the citing documents' `topics_algo`.

**`citation_rank` cross-check (as stored, uncorrected at the time of the memo; recomputed on
2026-10-01, see §1.3).**
```sql
SELECT d.id, substr(d.title,1,50), s.admin_level, d.citation_rank,
       (SELECT COUNT(*) FROM citations c WHERE c.target_id=d.id) indeg
FROM documents d JOIN sites s ON s.site_key=d.site_key
ORDER BY d.citation_rank DESC LIMIT 30;
```

---

## 8. Re-base, 2026-10-07: mirror determinism and per-document weighting

*Read-only pass over the live `documents.db` on the droplet, 2026-10-07 (UTC 2026-10-08 01:30).
Graph tonight: 341,313 documents, 585,471 citation rows, 310,136 resolved (52.97%). Sections
0-7 above are the 2026-10-01 state and are kept as published.*

### 8.0 Two changes, and why they separate

Two changes went live since §0-§7 were written.

- **M, mirror determinism** (commit `b1aff31`). The resolver now picks the copy of a
  multiply-held text by its documented rule (promulgation genre, then highest level, then
  lowest id). Before, the last row scanned won. M changes WHICH document holds an edge. It does
  not change how many edges an instrument receives.
- **W, per-document weighting** (commit `a494955`, `corpus-lessons.md` A1). `citation_rank`
  now weights a citation by the citing document's `doc_identity.admin_level_doc`, not its host
  site's level. W changes how much an edge weighs. It does not move any edge.

So the two are separable. **[measured]** Three states, all on tonight's edges:

| State | Edge holders | Weights |
|---|---|---|
| PRE | pre-`b1aff31` rule, simulated | `citations.source_level` (the old scorer) |
| A1OFF | as stored tonight | `citations.source_level` |
| NEW | as stored tonight | `doc_identity.admin_level_doc` (= stored `citation_rank`) |

PRE to A1OFF is M. A1OFF to NEW is W. Sanity: the NEW recomputation equals the stored
`citation_rank` on all 341,313 documents and `doc_inbound.inbound` on every row (0
mismatches). W changes `citation_rank` on 5,930 documents, the figure the deploy reported.
13,846 of 310,136 resolved edges (4.5%) change weight class under W.

```sql
-- A1OFF (pre-a494955 scorer)
SELECT target_id, SUM(CASE source_level WHEN 'central' THEN 3.0 WHEN 'provincial' THEN 2.0
       WHEN 'municipal' THEN 1.5 WHEN 'district' THEN 1.0 WHEN 'department' THEN 1.0 ELSE 0.5 END)
FROM citations WHERE target_id IS NOT NULL GROUP BY 1;
-- edges whose weight class W changes: 13,846 of 310,136
SELECT COUNT(*), SUM(COALESCE(NULLIF(i.admin_level_doc,''), c.source_level) <> c.source_level)
FROM citations c LEFT JOIN doc_identity i ON i.doc_id = c.source_id
WHERE c.target_id IS NOT NULL;
```

**[caveat]** PRE is a simulation. For each raw title it keeps the highest-id row (the old dict
semantics), then applies the matcher's ranking, and moves each named/llm edge from its new
holder to the old one. It moves 119,292 of 261,574 named/llm edges and changes the
representative of 24,098 normalized titles. The commit measured 85,585 and 18,798 before
tonight's ingest. Part of the gap is new higher-id mirrors: the simulated old holder of
政府信息公开条例 is a newer `gov` copy (`900169731`), not the district repost `900154149` the
commit named. Read PRE as "the old rule on tonight's corpus", an approximation. It does
reproduce the commit's named old holders of 城乡规划法 (`12747143`) and 道路交通安全法
(`12749132`).

A third source of movement is neither change: corpus growth (319,208 to 341,313 documents) and
the resolver fixes since 2026-10-01 (the alias table, entity unescape, the title-index floor
lowered 8 to 5). It is the whole difference between the 10-01 column and the PRE column below.

### 8.1 The memo's own statistics (pooled, proxy-corrected)

**[measured]** The §1 procedure re-run on tonight's graph. Universe filter, `npc` re-level by
publisher, title-cue re-level, canon-title pooling, proxy re-keying, organization-name and
suffix-less virtual nodes dropped, all as in the Appendix.

| Measure | 2026-10-01 (§2.1) | 10-07 PRE | 10-07 NEW |
|---|---|---|---|
| Nodes | 239,187 | 249,461 | 249,461 |
| Edges | 163,814 | 188,085 | 189,416 |
| Never cited | 84.2% | 84.0% | 83.9% |
| Gini, all nodes | 0.947 | 0.949 | 0.948 |
| Gini, cited nodes | 0.666 | 0.680 | 0.679 |
| Share held by top 0.1% | 24.8% | 25.3% | 25.1% |
| **Share held by top 1%** | **54.5%** | **55.6%** | **55.4%** |
| Share held by top 10 | 5.8% | 5.5% | 5.5% |
| Share held by top 100 | 17.2% | 17.0% | 16.9% |
| Share held by top 1,000 | 41.6% | 42.3% | 42.0% |
| Max inbound | 1,841 | 1,895 | 1,895 |
| Top-1% entry threshold | 11 | 11 | 12 |
| Top 100: central | 80 | 84 | 84 |
| Top 100: law + regulation | 75 (27 + 48) | 78 (40 + 38) | 77 (39 + 38) |
| Central share of all inbound | 61.0% | 60.0% | 59.6% |

**[measured] Attribution.** W cannot move any row of this table. These are edge counts, not
weights. M moves no row by more than 0.4 points. Pooling by normalized title collapses the
copies of one text into one node, so which copy holds an edge mostly does not matter. The
instrument-level top 30 is identical in PRE and NEW, count for count. M does add 1,331 edges to
the graph **[inferred]**: some old holders sat outside the universe (undated, or on a non-government
host), so their edges were dropped before and are counted now. Every other move in the table
is the third source, growth and resolver fixes.

**[caveat]** This is a re-implementation from the Appendix, not the 10-01 script, which is not
in the repo. Every share row lands within 1.1 points of the 10-01 figure, so implementation drift
is probably small, but it is not measured separately. The law/regulation split (27/48 to 39/38) moved
without either change; its cause is not traced. One flaw of the memo's own method surfaced:
the pool key requires 5 characters after folding, so 预算法 and 民法典 (3 after the
中华人民共和国 strip) are never pooled. Their node key follows the holder, and M relabels them.
This is the length-floor-on-a-folded-string shape logged in CLAUDE.md.

### 8.2 Top 30 by corrected inbound, re-based

**[measured]** Same procedure as §2.3. The 10-01 rank and count are from the §2.3 table.

| # | Instrument | Level | Genre | Inbound | 10-01 |
|---|---|---|---|---|---|
| 1 | 中华人民共和国城乡规划法 | central | law | 1,895 | 1 (1,841) |
| 2 | 中华人民共和国政府信息公开条例 | central | regulation | 1,546 | 2 (1,537) |
| 3 | 中华人民共和国道路交通安全法 | central | law | 1,329 | 3 (1,164) |
| 4 | 广东省城市控制性详细规划管理条例 | provincial | regulation | 1,014 | 7 (674) |
| 5 | 广东省城乡规划条例 | provincial | regulation | 970 | 4 (969) |
| 6 | 城市、镇控制性详细规划编制审批办法 | central | regulation | 913 | 5 (913) |
| 7 | 财政违法行为处罚处分条例 | central | regulation | 891 | 6 (774) |
| 8 | 中华人民共和国安全生产法 | central | law | 667 | 8 (663) |
| 9 | 中华人民共和国行政处罚法 | central | law | 579 | new |
| 10 | 中华人民共和国政府采购法 | central | law | 571 | new |
| 11 | 中华人民共和国行政许可法 | central | law | 550 | 10 (522) |
| 12 | 中华人民共和国突发事件应对法 | central | law | 532 | 9 (531) |
| 13 | 社会团体登记管理条例 | central | regulation | 529 | 11 (506) |
| 14 | 中华人民共和国土地管理法 | central | law | 515 | 14 (454) |
| 15 | 中山市国土空间总体规划（2021-2035年）印发通知 | municipal | strategy | 487 | 12 (487) |
| 16 | 国有土地上房屋征收与补偿条例 | central | regulation | 479 | 13 (455) |
| 17 | 中华人民共和国网络安全法 | central | law | 445 | 15 (440) |
| 18 | 深圳市保障性住房条例 | municipal | regulation | 420 | 18 (364) |
| 19 | 中华人民共和国食品安全法 | central | law | 409 | 16 (392) |
| 20 | 中华人民共和国预算法 | central | law | 388 | new |
| 21 | 建设用地容积率管理办法 | central | regulation | 368 | 17 (368) |
| 22 | 中华人民共和国土地管理法实施条例 | central | regulation | 364 | 30 (256) |
| 23 | 机动车驾驶证申领和使用规定 (virtual) | central | regulation | 355 | 19 (351) |
| 24 | 粤港澳大湾区发展规划纲要 | central | strategy | 338 | 20 (331) |
| 25 | 中华人民共和国民法典 | central | law | 326 | new |
| 26 | 广东省突发事件应对条例 | provincial | regulation | 324 | 21 (314) |
| 27 | 中华人民共和国反倾销条例 | central | regulation | 317 | new |
| 28 | 建设工程质量管理条例 | central | regulation | 317 | 28 (261) |
| 29 | 中华人民共和国文物保护法 | central | law | 317 | 22 (311) |
| 30 | 中共中央印发《中国共产党纪律处分条例》 | central | regulation | 309 | 24 (294, prov. host) |

Out of the top 30: 十四五规划纲要 (10-01 rank 23), 个人信息保护法 (25), 重大行政决策程序暂行条例
(26), 出境入境管理法 (27), 外国人入境出境管理条例 (29).

**[reading]** The top three are unchanged in identity and order. 广东省控规条例 gained 340 citers
from the `data/instrument_aliases.csv` row, not from M or W. The five entrants are four national
laws with short names and one State Council regulation. **[inferred]** They most likely entered
through the 10-07 short-title resolver changes, which neither M nor W is. The Party discipline
rule is now central: a `gov` copy (中共中央印发) arrived, so the §2.3 "hosting artifact" note no
longer applies to it. Twenty-four of thirty are national laws or central regulations (counting the Party rule),
against twenty-two on 10-01.

### 8.3 The stored `citation_rank`, by state

**[measured]** Top 30 by tonight's stored `citation_rank`. `A1OFF` is the same edges at site
weights, so `ΔW` is W alone. "Raw" is `doc_inbound.inbound` and its rank. "Pre-M holder" is the
document that held the edges under the simulated old rule (blank = unchanged). Level is
`doc_identity.admin_level_doc`.

| # | id | Instrument | Host | Level | `citation_rank` | A1OFF | ΔW | Raw (rank) | Pre-M holder |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 12685154 | 政府信息公开条例 | mee | central | 4,303.5 | 4,238.0 | +65.5 | 1,852 (3) | 900169731 gov |
| 2 | 12685270 | 城乡规划法 | mee | central | 3,375.5 | 3,377.5 | -2.0 | 1,950 (2) | 12747143 npc |
| 3 | 12738161 | 道路交通安全法 | npc | central | 3,292.0 | 3,319.5 | -27.5 | 2,149 (1) | 12749132 npc |
| 4 | 12749213 | 财政违法行为处罚处分条例 | npc | central | 2,230.0 | 2,231.0 | -1.0 | 970 (6) | 900169975 gov |
| 5 | 12747468 | 广东省城市控制性详细规划管理条例 | npc | provincial | 1,738.0 | 1,738.0 | 0 | 1,022 (4) | |
| 6 | 12748220 | 广东省城乡规划条例 | npc | provincial | 1,651.5 | 1,651.5 | 0 | 977 (5) | |
| 7 | 900093336 | 城市、镇控制性详细规划编制审批办法 | gov | central | 1,522.5 | 1,522.5 | 0 | 918 (7) | |
| 8 | 12694498 | 网络安全法 | cac | central | 1,500.0 | 1,505.5 | -5.5 | 643 (11) | 900078764 nx_gxt |
| 9 | 12738564 | 行政处罚法 | npc | central | 1,423.0 | 1,420.5 | +2.5 | 761 (8) | 900098634 bjb_tjj |
| 10 | 12737824 | 安全生产法 | npc | central | 1,401.5 | 1,387.5 | +14.0 | 727 (9) | 900084147 fj_yjt |
| 11 | 12703730 | 反倾销条例 | mofcom | central | 1,367.0 | 1,365.0 | +2.0 | 338 (38) | 12751744 npc |
| 12 | 12728109 | 社会团体登记管理条例 | npc | central | 1,306.5 | 1,305.0 | +1.5 | 642 (12) | 12746562 npc |
| 13 | 12742121 | 行政许可法 | npc | central | 1,222.5 | 1,209.0 | +13.5 | 614 (15) | 900098637 bjb_tjj |
| 14 | 12752635 | 民办非企业单位登记管理暂行条例 | npc | central | 1,166.0 | 1,152.5 | +13.5 | 530 (18) | |
| 15 | 12685268 | 土地管理法 | mee | central | 1,124.5 | 1,153.0 | -28.5 | 665 (10) | 900063146 chinatax |
| 16 | 12749186 | 国有土地上房屋征收与补偿条例 | npc | central | 1,117.5 | 1,118.5 | -1.0 | 620 (13) | 900168484 gov |
| 17 | 12729148 | 食品安全法 | npc | central | 1,116.5 | 1,108.5 | +8.0 | 495 (20) | 900098390 bjb_wjw |
| 18 | 12731734 | 突发事件应对法 | npc | central | 1,091.5 | 1,094.5 | -3.0 | 619 (14) | 900083691 fj_wjw |
| 19 | 12652296 | 十四五规划和2035年远景目标纲要 | ndrc | central | 1,081.0 | 1,081.0 | 0 | 365 (34) | |
| 20 | 101629 | 广东省自然资源厅 (org name) | gd | provincial | 1,070.0 | 1,069.5 | +0.5 | 466 (23) | 4058874 gd |
| 21 | 11637955 | 机动车驾驶证申领和使用规定（公安部令第162号） | ga | municipal | 1,050.5 | 1,048.0 | +2.5 | 543 (17) | |
| 22 | 12747503 | 政府采购法 | npc | central | 1,009.5 | 1,015.0 | -5.5 | 590 (16) | |
| 23 | 12694426 | 个人信息保护法 | cac | central | 964.5 | 969.5 | -5.0 | 407 (27) | 900078779 nx_gxt |
| 24 | 12742512 | 预算法 | npc | central | 956.0 | 953.5 | +2.5 | 414 (26) | 12747502 npc |
| 25 | 12651563 | 土地管理法实施条例 | gov | central | 943.5 | 943.0 | +0.5 | 505 (19) | 900165159 gov |
| 26 | 12732495 | 货物进出口管理条例 | npc | central | 938.5 | 947.5 | -9.0 | 247 (66) | 12752161 npc |
| 27 | 900093344 | 中小企业划型标准规定 | gov | central | 926.0 | 973.5 | -47.5 | 252 (62) | |
| 28 | 12651172 | 中共中央印发《中国共产党纪律处分条例》 | gov | central | 850.5 | 844.0 | +6.5 | 483 (22) | 900164745 gov |
| 29 | 2492990 | 中山市国土空间总体规划 印发通知 | zhongshan | municipal | 819.0 | 819.0 | 0 | 490 (21) | |
| 30 | 12701750 | 对外贸易法 | mofcom | central | 818.5 | 818.5 | 0 | 286 (47) | 12745970 npc |

**[measured]** M changed the holder of 21 of these 30. It changed one value in the top 30
(土地管理法实施条例, by 3.0): otherwise the PRE ranking has the same numbers in the same order,
held by other ids. W changed the value of 24 of 30, by at most 47.5 (中小企业划型标准规定,
2.1%). It swapped ranks 14 and 15 and moved 中小企业划型标准规定 from 23 to 27; no other order
changed. The largest W corrections sit below the top 30:
工会法 248.0 to 175.0, 村民委员会组织法 250.0 to 184.0, 人民防空法 550.5 to 497.0 (about rank
81). 广东省自然资源厅 at rank 20 is a bare organization name. §1.4 drops such nodes; the stored
score does not.

**[measured]** Concentration and composition of the doc-level rankings (all 341,313 documents,
unpooled, uncorrected):

| Measure | PRE | A1OFF | NEW | moved by |
|---|---|---|---|---|
| `citation_rank` top 1% share | 59.9% | 58.1% | 58.1% | M |
| `citation_rank` Gini, all / cited | 0.963 / 0.724 | 0.961 / 0.716 | 0.961 / 0.717 | M |
| Never cited | 86.5% | 86.1% | 86.1% | M |
| `citation_rank` top 100 share | 13.8% | 13.7% | 13.8% | neither |
| Raw inbound top 1% share | 62.2% | 61.1% | 61.1% | M (W cannot) |
| Raw inbound Gini, all / cited | 0.966 / 0.707 | 0.964 / 0.704 | 0.964 / 0.704 | M |
| `citation_rank` top 100: central by document level | 78 | 78 | 79 | neither |
| `citation_rank` top 100: central by host site | 68 | 83 | 84 | **M** |
| `citation_rank` top 100: law + regulation | 69 | 70 | 69 | neither |
| Raw inbound top 100: central by document level | 72 | 75 | 75 | M |
| Raw inbound top 100: central by host site | 59 | 80 | 80 | **M** |

**[reading]** M is the change that matters for composition, and only under a host-site count.
Before M the national laws' edges sat on bureau reposts (`nx_gxt`, `bjb_tjj`, `fj_yjt`,
`fj_wjw`), so counting by host level read them as provincial or municipal. `doc_identity`
already levelled those reposts central, which is why the document-level count stayed near 78
throughout. W moved the composition by one. The 1 to 2 point fall in doc-level concentration
under M is **[inferred]** a split: the new rule can give an exact-title key and a core key of one
text to different copies, so the same citer now reaches two documents (PRE has 7,690 fewer
distinct citer-target pairs). Part of it may be the simulation itself. The pooled §8.1 figures,
which merge those copies again, do not move.

### 8.4 Does W bring the weighted ranking closer to the raw one?

The prediction: W removed an over-weighting that was a weighting artefact, so `citation_rank`
should move toward `doc_inbound.inbound`. **[measured]** It does not.

| Agreement of `citation_rank` with raw inbound | PRE | A1OFF | NEW |
|---|---|---|---|
| Top 10 overlap | 9/10 | 9/10 | 9/10 |
| Top 30 overlap | 25/30 | 25/30 | 25/30 |
| Top 100 overlap | 82/100 | 83/100 | 82/100 |
| Spearman, all 47k scored documents | 0.833 | 0.834 | 0.831 |
| Spearman, union of both top-300s | 0.765 | 0.800 | 0.799 |
| CV of weight per citer, top 300 by raw | 0.281 | 0.261 | 0.263 |
| Top 30 overlap with §8.2 pooled corrected top 30 | 21/30 | 22/30 | 22/30 |
| Top 100 overlap with §8.2 pooled corrected top 100 | 65/100 | 73/100 | 72/100 |

On 10-01 the stored ranking overlapped the memo's corrected top 30 on 19/30. That is the
comparator in the last two rows, not `doc_inbound`, which did not exist then. The path is
19 (10-01) to 21 (growth and resolver fixes) to 22 (M) to 22 (W).

**[reading]** W moved every agreement measure by a point or less, either not at all or the wrong way. Two reasons.
First, W is not a move toward equal weights. Its 13,846 reclassified edges go both directions:
4,230 municipal-to-provincial (1.5 to 2.0, up), 1,523 provincial-to-central (up), 2,224
central-to-provincial (down), 1,240 central-to-municipal (down), 762 central-to-research
(down to 0.5). Total weight falls only 0.4% (607,820 to 605,276). Second, the laws W corrected
most (工会法, 村民委员会组织法, 代表法) sit far below the top 30, where the overlap is measured.
M did more convergence than W (top-300 Spearman 0.765 to 0.800), because it put each text's
edges on one copy instead of a repost.

The five `citation_rank`-only members of the top 30 show what the remaining gap is:
反倾销条例 (raw rank 38), 十四五规划纲要 (34), 对外贸易法 (47), 中小企业划型标准规定 (62),
货物进出口管理条例 (66). Three of them carry more than 3.0 of weight per distinct citer
(反倾销条例 4.04, 货物进出口管理条例 3.80, 中小企业划型标准规定 3.67), which a single central
citation cannot pay. **[inferred]** Their excess is the edges-versus-citers overhang: one
document cites the same instrument more than once (by 文号 and by title), and `citation_rank`
counts edges while `doc_inbound.inbound` counts citers. Neither M nor W touches that. The raw-only
members are 深圳市保障性住房条例, a 龙岗 news item on 百千万工程 (a §1.3 containment proxy that
persists), 民法典, 文物保护法 and 建设工程质量管理条例.

### 8.5 Which claims survive

- **"Authority is heavily concentrated."** Survives under every treatment. Top 1% holds
  55.4% pooled and corrected, 61.1% of raw doc-level inbound, 58.1% of `citation_rank`. Gini
  0.948 to 0.964 over all nodes. 84% to 88% of documents are never cited.
- **"Of the top 100, 80 are central."** Survives as "about four in five": 84 pooled and
  corrected, 79 by `citation_rank` at document level, 75 by raw inbound. Before M a host-site
  count gave 68 and 59. Count levels by `doc_identity.admin_level_doc` or by the pooled
  node, never by the holder's host site.
- **"75 are regulations or laws."** Survives: 77 pooled. The split moved to 39 laws and 38
  regulations; not traced to either change.
- **"The three largest are 城乡规划法, 政府信息公开条例, 道路交通安全法."** Survives as a set.
  Their order depends on the metric. Pooled corrected: 城乡规划法 first. Raw doc-level:
  道路交通安全法 first (2,149 citers, but at 1.53 weight per citer, mostly Shenzhen
  public-security notices). `citation_rank`: 政府信息公开条例 first (4,303.5, 2.32 per citer,
  the broadest and most central citer base). The §2.3 reading that rank 1 by count is a
  Zhongshan artifact and 政府信息公开条例 is the broadest anchor still holds. The weighted
  ranking puts it first in all three states; W only widens its lead (+65.5).
- **"`citation_rank`'s top is framework law, 19/30 overlap."** Survives and strengthens:
  22/30, and 90 of the top 100 are `instrument_kind='framework'`. The stored score still ranks a
  bare organization name (广东省自然资源厅) at 20.
- **"W should converge the weighted ranking on the raw one."** Does not hold (§8.4).

### 8.6 Procedure

Python over the extracts below, on the droplet, `?mode=ro`, `nice -n 19`. PRE is built with
`extract_citations._norm_title`, `_genre_rank`, `_title_cores_of_title` and `_LEVEL_PREF`
imported read-only, applying the matcher's (genre, level, id) ranking to the highest-id row per
raw title.

```sql
SELECT id, title, site_key, algo_doc_type, date_published, citation_rank,
       publisher, classify_main_name FROM documents;
SELECT doc_id, admin_level_doc, genre, instrument_kind FROM doc_identity;
SELECT source_id, target_id, citation_type, source_level, target_ref
FROM citations WHERE target_id IS NOT NULL;                 -- 310,136 rows
SELECT doc_id, inbound FROM doc_inbound;                     -- 41,179 rows
-- stored ranking, the NEW column
SELECT d.id, d.title, d.site_key, i.admin_level_doc, d.citation_rank, b.inbound
FROM documents d LEFT JOIN doc_identity i ON i.doc_id = d.id
LEFT JOIN doc_inbound b ON b.doc_id = d.id
ORDER BY d.citation_rank DESC LIMIT 30;
```
