# The Bottom-Up Channel: Does the Center Acknowledge Local Models, and Can We See It?

*Corpus-lessons addition B2. Part 1 is a read-only pass over the live `documents.db` on the
droplet (321,230 docs, 2026-10-06). Part 2 adds the sources that would carry upward signals
(人大 建议/议案 handling, 政协 提案, 调研报告). SQL and regexes are in the appendix.*

---

## 0. The question and the short answer

**Question.** The research program's through-line (`findings-synthesis.md`) is that the published
record shows the center designating and localities echoing. The reverse flow, a local innovation
the center later absorbs, is nearly invisible. Is that absence real, or does it come from the
sources? Promulgations do not carry upward signals by construction. Two places could: the
center's own acknowledgment lexicon (典型经验, 推广…经验, 复制推广, 向全国推广, 先进经验) and the
feedback institutions (人大, 政协, research offices) that formally route local experience upward.

**Short answer.**

1. **The acknowledgment lexicon is a rising share of central promulgations.** Strict-lexicon
   phrases appear in 2-3% of central promulgations in 2008-13, 10-11% in 2015-19, and peak at
   17-19% in 2021-22, settling at 11-16% in 2023-26. Overall 3,845 of 37,022 central
   promulgations (10.4%) carry the lexicon.
2. **The lexicon is overwhelmingly exhortation, not recognition.** In about half the hits the
   window around the phrase is forward-looking ("总结推广", "及时总结经验"): the center telling
   localities to produce experience worth generalizing. Only 296 lexicon docs (7.7% of the
   lexicon set, 0.8% of central promulgations) name a locality within 40 characters of the
   phrase. Only 79 carry the acknowledgment in the title (the 国办/发改委 "关于推广…经验的通知"
   instrument), and only 33 forward or endorse a named locality's own document (国务院批转/转发
   X省…), nearly all of them pre-2016 reissues.
3. **Lexicon docs do not cite downward any more than other central docs.** Resolved
   central→sub-national citation edges are near zero for both groups: 12 of 3,845 lexicon docs
   (0.31%) and 81 of 33,177 non-lexicon docs (0.24%) have one. Most of those few are
   level-misattribution (a central text crawled on a provincial portal), not recognition. The
   center acknowledges by *naming* a place in prose, never by citing the local document.
4. **Who gets named tracks the GDP pattern already found for pilot selection.** Shanghai (80
   window mentions), Zhejiang (55), Guangdong (45), Fujian (33), Beijing (31) lead. Spearman
   (window mentions, 2015 GDP per capita) = **0.664** over 31 provinces; the richest ten take
   **62.5%** of mentions; the mention-weighted GDP percentile is **0.691** against a 0.500
   baseline. `site-selection-gdp.md` found 0.705 and 55.1% for pilot designations. Recognition
   and designation select the same places.
5. **Part 2 adds four feedback sources** (全国人大 议案建议/报告, 全国政协 提案委员会/视察调研/
   地方政协, 江苏人大, 北京人大) under `group="feedback"`; see §4 for counts and what they enable.
   广东人大, 浙江人大, 上海人大 and 国务院发展研究中心 are blocked or JS-rendered from the droplet.

**What this means for the through-line.** The upward channel *is* visible when you look for it,
but it is thin, late and asymmetric. The center's generalization language grew sharply after
2014, but 92% of it is generic instruction *(92% = lexicon docs that name no locality within the
window; the explicitly forward-looking "exhort" share is about half, §2)*. The named-recognition instrument exists (79 titles,
~300 named windows) and it rewards the same high-income coastal places the pilot machinery
selects. Nothing in the promulgation record connects a central acknowledgment to the local
document it absorbed. The finding "reverse flow nearly invisible" therefore hardens for the
*citation* record and softens for the *prose* record; the feedback sources in Part 2 are where a
document-level upward link could still appear.

---

## 1. Data and definitions

**Population.** `doc_identity.admin_level_doc='central'` and `genre IN ('promulgation',
'implementing')`: 37,022 docs, 33,733 with body text (91%). Note that `genre='implementing'` is
assigned only at provincial/municipal/district level (9,224 / 7,487 / 628), so the central set
is all `promulgation`. *(Live 2026-10-07: 37,036 central; implementing 9,162 / 6,755 / 644 after
the `localized_of` flip rule was tightened to in-chain parents, `docs/working/qa-genre-flip.md`;
the central set is unchanged in kind.)* Years from `date_published[:4]`; 338 docs undated, 1,838 pre-2005.

**Lexicon tiers** (regex over title + body, see appendix A).

| tier | phrases | docs | share of central |
|---|---|---|---|
| strict | 典型经验, 经验推广, 推广…经验, 复制推广, 可复制可推广, 向全国推广, 学习…经验, 先进经验, 经验做法, 典型做法 | 3,845 | 10.4% |
| broad-only | 示范 or 做法 without a strict hit | +4,066 | +11.0% |
| title | strict phrase in the title | 79 | 0.21% |
| forward | 转发/批转 + a named 省/市/自治区 in the title | 33 | 0.09% |
| window-named | strict hit with a province/city name within ±40 chars | 296 | 0.80% |

`示范` and `做法` are too generic to count as acknowledgment (示范区, 示范项目, 工作做法); they are
reported as the broad tier only and not used in any finding below.

**Boilerplate.** Place-name counts strip the distribution list (`各省、自治区、直辖市…`), the
`新疆生产建设兵团` addressee, and Beijing postal addresses before scanning. Without this 新疆
appears in 52% of lexicon docs; with it, 9 window mentions.

---

## 2. Is the lexicon rising? (normalized series)

Share of central promulgations with a strict-lexicon hit, by year. `exhort` = window contains a
forward-looking phrase (总结推广, 及时总结, 形成…可复制, 探索…经验). `named` = a place name within
±40 chars of the phrase.

| year | central | strict | share | exhort | named | title | forward |
|---|---|---|---|---|---|---|---|
| 2008 | 974 | 23 | 2.4% | 12 | 1 | 0 | 4 |
| 2010 | 1,092 | 26 | 2.4% | 12 | 1 | 0 | 4 |
| 2012 | 934 | 33 | 3.5% | 6 | 4 | 0 | 7 |
| 2014 | 570 | 36 | 6.3% | 18 | 6 | 0 | 0 |
| 2015 | 890 | 90 | 10.1% | 58 | 14 | 2 | 0 |
| 2016 | 1,501 | 139 | 9.3% | 70 | 15 | 3 | 8 |
| 2017 | 931 | 103 | 11.1% | 66 | 17 | 0 | 0 |
| 2018 | 2,964 | 263 | 8.9% | 132 | 24 | 4 | 2 |
| 2019 | 2,621 | 294 | 11.2% | 154 | 24 | 6 | 0 |
| 2020 | 3,124 | 408 | 13.1% | 208 | 40 | 5 | 1 |
| 2021 | 2,978 | 510 | 17.1% | 267 | 28 | 20 | 0 |
| 2022 | 2,488 | 463 | 18.6% | 260 | 53 | 12 | 0 |
| 2023 | 2,491 | 369 | 14.8% | 187 | 24 | 10 | 0 |
| 2024 | 3,471 | 401 | 11.6% | 205 | 18 | 8 | 0 |
| 2025 | 2,118 | 346 | 16.3% | 172 | 13 | 7 | 0 |
| 2026* | 2,483 | 273 | 11.0% | 137 | 13 | 2 | 0 |

*2026 is partial (through early October) and 21% of its docs lack a body yet, so its share is
a floor (14.0% on docs with body).

**Evidence.** The share step-changes in 2014-15 (from ~3% to ~10%) and again in 2021-22 (to
~18%). The 2015 step coincides with the 自贸区 复制推广 machinery (first batch of FTZ experience
replication notices, 2015) and the 2021-22 step with the 深圳综合改革试点 and 浦东 授权事项
notices (发改委 2021-2024, see §3). The series is normalized by central volume, so the 2018 and
2020 crawl-depth jumps (central count 931→2,964) do not drive it.

**Caveat.** The lexicon share measures the center's *use of generalization language*, not the
number of local models absorbed. Roughly half the windows are exhortation. The named series
(column `named`) is flat at 13-53 per year and does not grow with the share: the center talks
about generalizing experience far more than it names whose.

---

## 3. Does the lexicon cite or name downward?

### 3a. Citation edges (resolved `citations`)

| group | docs | with any edge | with ≥1 resolved edge to prov/muni/district | share |
|---|---|---|---|---|
| strict lexicon | 3,845 | 2,953 | 12 | 0.31% |
| non-lexicon central | 33,177 | 23,410 | 81 | 0.24% |
| title instrument (79) | 79 | 60 | 0 | 0.0% |
| forward instrument (33) | 33 | 26 | 2 | 6.1% |
| window-named (296) | 296 | 233 | 3 | 1.0% |

Edge mix for lexicon docs: 3,495 → central, 79 → provincial, 7 → municipal, 2 → district, 6,915
unresolved. Of the 4,176 unresolved target refs from lexicon docs, 170 (4.1%) contain a
province/city name; for non-lexicon central docs it is 957 of 36,723 (2.6%).

**Evidence.** Lexicon docs cite downward at the same near-zero rate as other central docs. The
difference (0.31% vs 0.24%) is 12 vs 81 documents and within noise. Inspection of the 12 shows
the edges are mostly artefacts: a 国办 approval letter citing the NDRC's own print of the 义乌
scheme (both central, one crawled on a provincial site), a 交通运输部 opinion resolving to a
Jiangsu 农村公路条例 by title overlap, a 民政部 notice resolving to its own implementing measures.
The two genuine cases are the 转发 instrument (国务院批转安徽省…决定; 转发北京市…报告), and these
are 1980s-2000s texts reissued on gov.cn in 2010-2018.

**Mechanism.** The center acknowledges a local model by *restating* it in its own prose (a 典型
经验 list, a 复制推广 table of 举措) and by naming the place. It does not cite the local document.
The local text is absorbed and its provenance is dropped. This is why the citation graph is
structurally blind to upward flow: downward recognition does not generate a citation edge even
when it is explicit.

### 3b. Who is named

Window mentions (a strict-lexicon phrase within ±40 chars of a place name), cities folded into
provinces. 31 provinces, 2015 GDP per capita from `data/provincial_gdp.csv`.

| province | window mentions | GDP pc 2015 (元) |
|---|---|---|
| 上海 (incl. 浦东) | 80 | 107,548 |
| 浙江 (incl. 杭州, 宁波, 义乌) | 55 | 77,274 |
| 广东 (incl. 深圳, 前海, 横琴) | 45 | 66,311 |
| 福建 (incl. 厦门) | 33 | 68,649 |
| 北京 | 31 | 111,749 |
| 四川 | 21 | 38,523 |
| 江苏 | 20 | 86,145 |
| 辽宁 | 18 | 61,365 |
| 湖北 | 18 | 49,835 |
| 湖南 | 16 | 42,834 |
| 山东 | 15 | 60,741 |
| … | | |
| 云南 | 2 | 31,134 |
| 贵州 | 1 | 28,230 |
| 宁夏 | 1 | 43,609 |
| 西藏 | 0 | 32,068 |
| 甘肃 | 0 | 27,444 |

Raw window top-10 (before folding): 上海 67, 浙江 41, 北京 31, 福建 26, 深圳 17, 湖北 16, 广东 15,
四川 14, 辽宁 14, 浦东 13. Title-instrument places (79 docs): 浙江 7, 深圳 6, 上海 5, 浦东 2,
安徽 2, 湖北 2, 四川 2, 宁波 2, 北京 2.

**Evidence.**

| test | value | baseline |
|---|---|---|
| Spearman(window mentions, GDP pc 2015), 31 provinces | **0.664** | 0 |
| mention-weighted GDP percentile | **0.691** | 0.500 |
| share of mentions going to the richest 10 provinces | **62.5%** | 32% (10/31) |
| Spearman(lexicon-doc place mentions, GDP pc) | 0.609 | |
| Spearman(non-lexicon-doc place mentions, GDP pc) | 0.600 | |

`site-selection-gdp.md` found a mean percentile of 0.705 and 55.1% to the richest ten for pilot
*designations*. Recognition is at least as concentrated as designation. The doc-level comparison
(0.609 vs 0.600) shows that central documents in general mention rich provinces more; the window
series is sharper (0.664) because it isolates the acknowledgment context.

**Caveat.** The named-recognition set is small (296 docs, ~600 window mentions). Rankings below
the top five are unstable to a handful of documents. 四川 at 21 is mostly the 2022 投资审批改革
典型经验 notice and 成都 公园城市 texts. The 12 instruments issued by 发改委 for 深圳 / 浦东 授权事项
alone account for a large share of the 广东 and 上海 window counts.

### 3c. The title instrument, by issuer

Lexicon docs by lead issuer: 国务院办公厅 611, 国务院 474, 国家发展改革委 306, 教育部 206, 工业和
信息化部 187, 商务部 183, 市场监管总局 180, 农业农村部 152, 财政部 145. Against the all-central
baseline (国务院 4,662, 财政部 4,426, 国务院办公厅 3,394, 税务总局 2,906), the lexicon is
over-represented in 国办 and 发改委 and under-represented in 财政部 and 税务总局, which is what the
instrument's function predicts: generalization is coordinated by the general offices and the
reform commission, not by the fiscal regulators.

The 79 title-level instruments fall into three families:

- **自贸区 复制推广** (国务院, 2015-2025): "关于做好自由贸易试验区第N批改革试点经验复制推广工作的通知".
  Place-agnostic in the title; the batches name the originating FTZ in the body.
- **综合改革试点 授权事项** (发改委, 2021-2024): "关于推广借鉴深圳综合改革试点创新举措和典型经验的通知"
  (3 rounds), "关于推广借鉴上海浦东新区有关创新举措和经验做法的通知", "关于推广借鉴上海浦东新区、深圳、
  厦门综合改革试点创新举措和典型经验的通知" (2024). These are the clearest named upward
  acknowledgments in the corpus.
- **Sectoral 典型经验 lists** (发改委, 国家医保局, 住建部): "关于印发浙江高质量发展建设共同富裕示范区
  第N批典型经验的通知", "关于进一步推广三明医改经验…的通知", "关于印发宁波市灵活就业人员支持政策典型
  经验的通知", "关于印发浙江、安徽、湖北、四川等省深化投资项目审批制度改革…典型经验的通知".

---

## 4. Part 2: the feedback sources

**Method.** Probed from the droplet (NYC IP) on 2026-10-06 with the crawler's own `fetch()`
(curl_cffi fallback), byte-checked (HTTP 200 is unreliable for CN gov sites), section leaves
mapped with `govcms --discover`, then crawled serially (one writer) with bodies on, page 0 first
and `--deep` only after body verification. Sites are tagged `group="feedback"` in
`crawlers/govcms.py`. One small crawler change was needed: govcms Scheme-B pagination assumed
`index_N.html`; jsrd.gov.cn paginates as `index_N.shtml`, so `_pages()` now picks the extension
from page 0. (govcms.py is uncommitted on both machines by design; it is byte-identical on
both after this change.)

### 4a. What was added

| site_key | source | sections | admin_level | docs | with body | span |
|---|---|---|---|---|---|---|
| `npc_dbgz` | 全国人大 代表工作: 议案建议, 报告 | `/npc/c2/c185/c12492/`, `/npc/c2/c12435/c12491/` | central | **796** | 770 (97%) | 2022-03 → 2026-09 |
| `cppcc` (new sections) | 全国政协 提案委员会, 视察调研 (+报告展示), 地方政协 | `/jgzc/tawyh/`, `/zxgz/scdy/`, `/zxgz/scdy/bgzs/`, `/dfzx/` | central | **96** | 96 (100%) | 2024-09 → 2026-09 |
| `jsrd` | 江苏省人大: 建议办理, 视察调研, 执法检查报告, 理论研究会 成果集萃, 研究室 | `/dbyd/jybl/`, `/dbyd/scdy/`, `/zfjc/zfjcbg/`, `/llyjh/cgjc/`, `/jgzy/yjs/` | provincial | **447** | 196 (44%; 190/191 = 99% for 2023-26) | 2009-01 → 2026-09 |
| `bjrd` | 北京市人大: 代表工作, 重要发布, 理论研究 | `/zyfb/zdgz/dbgz/`, `/zyfb/`, `/xwzx/llyj/` | provincial | **88** | 78 (89%) | 2022-11 → 2026-09 |
| **total** | | | | **1,427** | **1,140 (80%)** | |

(Row counts are from `documents` after the crawl; the crawler log reported 1,434 stored, the
7-row difference is jsrd rows whose URL repeated across two list pages.)

Pagination: NPC and CPPCC `index_N.html` (30 and 26-46 per page; NPC 议案建议 walked to the
30-page cap, 780 docs, archive continues); jsrd `index_N.shtml` (15 per page; the index lists
2009-2022 rows whose article pages return **404**: 256 dead links, zero extractor misses, so
the pre-2023 jsrd rows are metadata-only and the hollow share is the site's, not ours); bjrd
has no `index_N` (page 0 only, 18-50 rows per section). bjrd's 10 hollow rows are 常委会公告
(attachment-only notices).

**Content check (random samples).** `npc_dbgz`: "对建设全国统一大市场工作情况报告的意见和建议",
"国家发展改革委扎实办理代表委员建议提案", "从代表建议'办理'到系统施策'治理'", "2022年代表建议
'提交办'工作顺利推进圆满完成", plus the State Council's reports to the NPCSC (债务管理, 计划执行).
`jsrd` 建议办理: "省人大常委会召开发展农村集体经济重点处理代表建议督办会", "督办进一步推动我省涉外
仲裁高质量发展重点处理代表建议"; 执法检查报告: full-text reports on 就业促进法, 水污染防治法
implementation (9-13k chars). `cppcc` 地方政协: provincial CPPCC 协商议政 and 督办重点提案 stories
(陕西 新材料, 湖南 民族地区开放通道, 广西 向海经济). `bjrd` 代表工作: individual deputies' 建议
profiles ("市人大代表吴双：加强垃圾分类柔性引导").

### 4b. Skipped, with reason

| target | result from the droplet | reason |
|---|---|---|
| 国务院发展研究中心 drc.gov.cn | root returns a 109-byte shell; `Leaf.aspx?leafid=…` renders 9.9 KB GBK but article links are ASP.NET `DocView.aspx` | no govcms dialect; anti-bot shell at root. A dedicated crawler would need the ASP.NET id scheme. |
| 广东人大 rd.gd.cn | connection refused (`rd.gd.gov.cn` does not resolve) | datacenter-IP block; needs the residential vantage (`access-vantage-brief.md`) |
| 浙江人大 zjrd.gov.cn | connection fails (curl 000) | datacenter-IP block |
| 上海人大 spcsc.sh.cn | HTTP 403 | datacenter-IP block |
| 国务院研究室 | no standalone site; gov.cn carries only its 机构 page | nothing to crawl |

### 4c. First read of the new material

Phrase incidence in the 1,427 new docs (body `LIKE`, not a measurement, a feasibility check):

| site | docs | 采纳 (adopted) | 转化为 / 吸纳 | 代表建议 / 提案 | 办理 | strict lexicon |
|---|---|---|---|---|---|---|
| npc_dbgz | 796 | 84 | 176 | 245 | 198 | 4 |
| jsrd | 447 | 13 | 67 | 65 | 81 | 4 |
| bjrd | 88 | 3 | 33 | 21 | 34 | 1 |
| cppcc (new) | 96 | 1 | 32 | 96 | 12 | 3 |

**Evidence.** The upward vocabulary (采纳, 转化为政策, 建议办理) is dense here and nearly absent in
promulgations; the downward lexicon (典型经验, 复制推广) is nearly absent here. The two record types
are complementary, which is what B2 predicted: the promulgation corpus cannot see the upward
channel because the upward channel is published somewhere else.

### 4d. What deeper crawling will enable

1. **A proposal-to-policy link.** NPC 建议办理 reports name the handling ministry and often the
   resulting document ("已转化为…意见", "已纳入…规划"). Matching those named outputs against
   `documents` via `TitleMatcher` gives the first document-level upward edges in the corpus.
   This needs the NPC archive past the 30-page cap (the 议案建议 index continues to 2018 and
   earlier) and a `citation_type='feedback'` or similar so the edges are not confused with
   downward citation.
2. **A local-origin test for the 79 title instruments.** For each 推广…经验 notice, search the
   new 人大/政协 material and the provincial corpora for the same measure *before* the central
   date. Where a provincial 建议办理 or 执法检查报告 describes the practice first, the upward flow
   is dated.
3. **Provincial breadth.** Only Jiangsu and Beijing 人大 are reachable from the droplet. The
   three blocked 人大 sites (广东, 浙江, 上海) are the places §3b says the center names most.
   They are the priority targets for the residential-vantage crawl.
4. **Nightly.** `cppcc` is already in `daily_sync.sh`'s govcms loop, so its new sections stay
   current. `npc_dbgz`, `jsrd`, `bjrd` are not; adding `--group feedback` to the nightly govcms
   block is a one-line change once govcms.py is committed. `data/source_ontology.yaml` has no
   leaf for the three new keys yet (they fall through to the runtime default); add them to the
   legislative leaf alongside `npc`, `cppcc` when the ontology file is next committed.

---

## 5. Caveats

- **Lexicon ≠ absorption.** A strict hit says the center used generalization language. It does
  not say a local practice became national policy. The named-window subset is the closest proxy
  and it is 0.8% of central promulgations.
- **Body coverage.** 9% of central promulgations have no body; the 2026 share is a floor.
- **Place list.** 31 provinces plus 62 cities/zones. A locality outside the list (a county model
  such as 浙江 "枫桥经验" is caught via 浙江 only if the province is named) is missed. 三明 is not
  on the list; the 三明医改 title is caught by the lexicon but not the place count.
- **Citation levels.** `citations.target_level` follows the *site* the target was crawled from.
  A central text crawled on a provincial portal shows as a downward edge. The 12/81 counts are
  upper bounds on genuine downward citation.
- **Period.** Central volume is thin before 2008 and the gov.cn archive reissues 1980s-2000s texts
  with 2010-2018 publication dates, which is why the forward instrument clusters there.

---

## Appendix A. Regexes

```
STRICT        典型经验|经验推广|推广[^。；，、\n]{0,15}?经验|复制推广|可复制可推广|可复制、可推广|
              向全国推广|学习[^。；，、\n]{0,12}?经验|先进经验|经验做法|典型做法|做法[^。；，、\n]{0,6}?推广
BROAD         示范|做法
TITLE         推广[^《》]{0,20}?(经验|做法)|经验推广|复制推广|可复制可推广|典型经验        (title only)
FORWARD       (?:转发|批转)[^《》]{0,12}?(?:省|市|自治区)                                 (title only)
EXHORT        总结推广|及时总结|总结[^。；，、\n]{0,8}?经验|形成[^。；，、\n]{0,8}?可复制|探索[^。；，、\n]{0,8}?经验
BOILER (strip) 新疆生产建设兵团|各省、自治区、直辖市[^。\n]{0,40}|北京市[^。\n]{0,12}?(?:邮编|邮政编码|电话)|中国北京
WINDOW        text[m.start()-40 : m.end()+40] around every STRICT match, after BOILER strip
```

## Appendix B. SQL

Population (read-only, `?mode=ro`):

```sql
SELECT d.id, d.title, d.date_published, d.site_key, i.genre, i.lead_issuer, d.body_text_cn
FROM documents d JOIN doc_identity i ON i.doc_id = d.id
WHERE i.admin_level_doc = 'central' AND i.genre IN ('promulgation', 'implementing');
-- 37,022 rows; 33,733 with body
```

Citation edges from a doc set (ids loaded into `temp.ids`):

```sql
SELECT c.citation_type, c.target_level, COUNT(*) AS edges, COUNT(DISTINCT c.source_id) AS srcs
FROM citations c JOIN temp.ids t ON t.id = c.source_id
GROUP BY 1, 2;

SELECT COUNT(DISTINCT c.source_id)
FROM citations c JOIN temp.ids t ON t.id = c.source_id
WHERE c.target_id IS NOT NULL AND c.target_level IN ('provincial', 'municipal', 'district');
-- lexicon: 12 / 3,845     non-lexicon: 81 / 33,177
```

Downward targets, for inspection:

```sql
SELECT c.source_id, s.title, c.target_id, tg.title, tg.site_key, c.target_level, c.citation_type
FROM citations c JOIN temp.ids t ON t.id = c.source_id
JOIN documents s ON s.id = c.source_id JOIN documents tg ON tg.id = c.target_id
WHERE c.target_level IN ('provincial', 'municipal', 'district');
```

Genre by level (why the central set is all `promulgation`):

```sql
SELECT admin_level_doc, COUNT(*) FROM doc_identity WHERE genre = 'implementing' GROUP BY 1;
-- district 628 | municipal 7,487 | provincial 9,224
```

GDP join: `data/provincial_gdp.csv`, column `gdp_per_capita_yuan`, `year = 2015`, cities folded
to provinces before ranking. Spearman computed with midrank ties.

New-site coverage check (Part 2):

```sql
SELECT site_key, COUNT(*), SUM(body_text_cn IS NOT NULL AND length(body_text_cn) > 200),
       MIN(date_published), MAX(date_published)
FROM documents WHERE site_key IN ('npc_dbgz', 'jsrd', 'bjrd') GROUP BY 1;

SELECT COUNT(*), SUM(body_text_cn IS NOT NULL AND length(body_text_cn) > 200)
FROM documents WHERE site_key = 'cppcc'
  AND (url LIKE '%/jgzc/tawyh/%' OR url LIKE '%/zxgz/scdy/%' OR url LIKE '%/dfzx/%');
```
