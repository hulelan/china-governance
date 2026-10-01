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
- **Mirror pooling.** Title-based, five-character minimum. It fixes level attribution for
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
