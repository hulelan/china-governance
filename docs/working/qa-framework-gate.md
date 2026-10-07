# QA: What the Framework Gate Excludes

*Read-only hand-check, 2026-10-07, live `documents.db` on the droplet. Follows
`docs/research/pair-channels.md` §2 and §6, which found that the framework gate
(`is_framework` in `scripts/rnd/analysis/build_diffusion_events.py`: `FW_GENRES` on
`algo_doc_type` plus `FW_TITLE_RE`) withholds more pairs than any channel. Nothing was
written and no code was changed. Scripts and queries are in Appendix B.*

## 0. Short answer

The gate excludes mostly real instruments. Of 60 excluded triggers read (title plus the
first 600 characters of body), 44 are policy instruments localities implement, 14 are
procedural or administrative notices, 2 are unclear. The exclusion is right 23% of the
time. The pairs it drops under the instrument-class parents are real implementations
(17 of 20 read; 12 of those copy the parent text at `ovlp_src` 0.3 or more).

A narrow admit rule (an issuance wrapper whose core is an 应急预案, 若干措施, 工作要点,
重点工作任务 or 方案, minus housekeeping sub-kinds) admits 28 of the 44 instrument-class
parents and none of the 14 administrative ones. It adds 1,950 pairs across the four
default hops (+3.9%), 788 on the province-to-city hop, and the admitted province-to-city
pairs score higher than the current baseline (median 0.185 against 0.074, relay 13.2%
against 8.5%). The rule belongs in the identity layer, not the matcher.

## 1. Reproduction

The exact predicate is `genre in FW_GENRES or FW_TITLE_RE.search(title)` with
`genre = documents.algo_doc_type`. `pairs.parent_is_framework` adds the ABOUT-genre and
`NONISSUE_RE` tests; they change nothing on these sets (0 extra drops on Guangdong, 1 on
all provinces). [measured]

| set | distinct triggers | fail `is_framework` | source edges dropped | identity `genre` of the excluded |
|---|---:|---:|---:|---|
| A. Guangdong provincial `localized_of` triggers | 210 | 85 (40%) | **329** | promulgation 85 |
| A'. All provincial `localized_of` triggers | 345 | 107 (31%) | 360 | promulgation 107 |
| B. Central `localized_of` triggers (non-npc hosts: gov 61, chinatax 9, ndrc 5, mee 4, miit 4) | 298 | 87 (29%) | 129 | promulgation 87 |
| `title_reissue` anchors | 345 | 0 | 0 | (anchors pass the gate by construction) |

The 329 reproduces. Every excluded trigger carries `doc_identity.genre = promulgation`,
so the identity layer already sees them as instruments; only the instrument-kind test
in the matcher does not.

**Table 1b. Excluded triggers by `algo_doc_type` and title shape.** Shape = wrapper
(印发/公布/发布 present, bare 通知, or no wrapper) and the kind named in the 《》 core or
the 印发...的通知 core. [measured]

| shape | A. Guangdong (85) | B. central (87) |
|---|---:|---:|
| 印发: 应急预案 / 预案 | 27 | 1 |
| 印发: 计划 (立法工作计划, 制定规章计划, 全民健身实施计划) | 11 | 0 |
| 印发: 方案 (管控/分工/攻坚/考评/组建方案) | 9 | 5 |
| 印发: 若干(政策)措施 | 7 | 0 |
| 印发: 工作要点 | 5 | 9 |
| 印发: 重点工作任务 / 任务分工 / 工作安排 | 4 | 5 |
| 印发: 制度 / 规则 / 章程 | 4 | 0 |
| 印发: 名单 / 目录 / 清单 | 4 | 1 |
| 印发: 指南 / 规范 / 规程 | 1 | 1 |
| 印发: 工作方案 | 1 | 1 |
| 印发: other | 3 | 3 |
| 通知 (no wrapper): other | 7 | 46 |
| 通知: 指南 / 规范, 名单, 措施, 任务分工, 计划 | 2 | 14 |
| bare | 0 | 1 |
| by `algo_doc_type` | policy_issuance 72, notice 13 | notice 58, policy_issuance 25, application_guide 2, subsidy 1, other 1 |

The Guangdong set is the memo's picture: 印发 notices whose core is an emergency plan, a
measures list or a work-points list. The central set is different: more than half are
bare 通知 with no printed core (国办 directives, ministry work notices, application
calls). The two sets need different treatment.

## 2. Hand-check of 60 excluded triggers

Stratified by set x `algo_doc_type` x shape, proportional allocation, minimum one per
stratum, npc hosts excluded from B (no body). 32 from A, 28 from B. Classes: (a) a
policy instrument localities would implement, (b) a procedural or administrative notice,
(c) unclear. Row-level calls are in Appendix A.

| class | A. Guangdong | B. central | total | share |
|---|---:|---:|---:|---:|
| (a) instrument | 23 | 21 | **44** | 73% |
| (b) administrative | 8 | 6 | **14** | 23% |
| (c) unclear | 1 | 1 | **2** | 3% |

**Exclusion precision (share rightly excluded) = 14/60 = 23%.** [measured]

**Table 2b. Class by shape.** [measured]

| shape | (a) | (b) | (c) | reading |
|---|---:|---:|---:|---|
| 印发: 应急预案 / 预案 | 10 | 0 | 0 | always an instrument; cities issue their own 预案 from it |
| 印发: 若干(政策)措施 | 3 | 0 | 0 | always an instrument |
| 印发: 工作要点 | 5 | 0 | 0 | binding annual task lists (数字政府, 政务公开, 医改) |
| 印发: 重点工作任务 / 工作安排 | 3 | 0 | 0 | binding task lists with assignments |
| 印发: 方案 (other) | 5 | 1 | 0 | the (b) is a 党组 整改方案; the rest are 管控/分工/治理/综合/建设方案 |
| 印发: 工作方案 | 1 | 0 | 0 | 示范区建设方案 |
| 印发: 计划 | 0 | 4 | 0 | 立法工作计划 and 制定规章计划 are the issuer's own housekeeping |
| 印发: 名单 / 目录 / 清单 | 3 | 0 | 0 | 行政许可事项清单, 核准目录, 指导目录: the body orders lower governments to issue their own list |
| 印发: 指南 / 规范 / 规程 | 2 | 0 | 0 | 现场指挥官工作规范, DIP 经办管理规程: normative texts |
| 印发: 制度 / 章程 | 1 | 0 | 0 | 社会保险监督委员会章程 applies to every level |
| 印发: other | 1 | 1 | 1 | 便利化措施 (a); 验收结果公布 (b); 元旦春节工作通知 (c) |
| 通知: other (no wrapper) | 6 | 4 | 1 | mixed: 国发/国办 directives (a) beside 申报, 信息库, 外债额度 (b) |
| 通知: 指南 / 规范 / 措施 / 任务分工 | 4 | 0 | 0 | 国办发〔2023〕11号 稳就业措施, 宅基地审批, 规范性文件管理, 民间投资分工 |
| 通知: 名单 / 计划 | 0 | 3 | 0 | 申报 calls and list-compilation procedures |
| bare: 指南 | 0 | 1 | 0 | an agency's own 政府信息公开指南 |

Two kinds split cleanly. Everything printed under 印发 whose core names an 预案, 措施,
工作要点, 重点工作任务 or a non-housekeeping 方案 is an instrument (27 of 27 in the
sample). 立法/规章 计划 and 申报 calls are never one. The bare 通知 class is mixed and
cannot be separated by title shape; its (a) members are State Council and 国办 directives
(国发〔2016〕63号, 国办函〔2025〕95号) whose instrument status comes from the 文号, not the
title.

## 3. The pairs the gate drops

`pairs.build_pairs(require_framework=False)` on the four default hops, all pairs scored
with the module's 5-gram `ovlp_src` (both bodies over 500 characters), then split on
`parent_framework`. 61,934 pairs: 50,634 pass the gate, 11,300 are dropped. The gate-on
counts are a little above the memo's (P→M 7,276 against 7,019) because the nightly
rebuilt identity and citations since the memo's run. [measured]

**Table 3a. Gate-on against gate-dropped, by hop.** impl = share of sources with
`doc_identity.genre` promulgation or implementing. [measured]

| hop | subset | pairs | scored | median | relay | mid | elab | impl |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| C→P | gate-on | 18,862 | 13,038 | 0.053 | 1.8% | 9.2% | 88.9% | 63.9% |
| C→P | dropped | 4,453 | 3,648 | 0.069 | 4.2% | 13.3% | 82.4% | 53.8% |
| P→M | gate-on | 7,276 | 6,318 | 0.074 | 8.5% | 16.9% | 74.6% | 76.8% |
| P→M | dropped | 2,877 | 1,831 | 0.097 | 10.6% | 20.6% | 68.8% | 71.7% |
| M→D | gate-on | 962 | 733 | 0.052 | 1.1% | 9.5% | 89.4% | 41.8% |
| M→D | dropped | 419 | 155 | 0.039 | 6.5% | 3.2% | 90.3% | 31.5% |
| C→M | gate-on | 23,534 | 13,427 | 0.044 | 0.2% | 3.0% | 96.8% | 53.8% |
| C→M | dropped | 3,551 | 3,003 | 0.043 | 0.9% | 6.4% | 92.6% | 54.6% |

The dropped pairs are not noise relative to what the gate keeps. On the province-to-city
hop they score higher than the baseline on every measure. Channel mix of the dropped
pairs: citation 10,874, citation + localized_of 224, localized_of only 200,
title_reissue 2.

**Table 3b. Dropped province-to-city pairs by parent shape** (shapes with 30 or more
pairs). [measured]

| parent shape | pairs | scored | median | relay | mid | impl |
|---|---:|---:|---:|---:|---:|---:|
| 印发: 应急预案 | 276 | 169 | **0.349** | 20.1% | 33.7% | 94.6% |
| 印发: 重点工作任务 / 任务分工 | 57 | 43 | **0.280** | 25.6% | 23.3% | 91.2% |
| 印发: 计划 | 36 | 30 | 0.321 | 20.0% | 36.7% | 88.9% |
| 印发: 制度 / 规则 / 章程 | 58 | 52 | 0.236 | 3.8% | 36.5% | 91.4% |
| 印发: 若干(政策)措施 | 259 | 243 | 0.135 | 8.2% | 23.5% | 87.3% |
| 印发: 方案 (other) | 135 | 118 | 0.113 | 10.2% | 29.7% | 75.6% |
| 通知: other | 571 | 484 | 0.117 | 9.5% | 22.3% | 76.7% |
| 印发: 工作要点 | 91 | 79 | 0.064 | 7.6% | 11.4% | 68.1% |
| 印发: 指南 / 规范 | 84 | 42 | 0.089 | 16.7% | 14.3% | 51.2% |
| 印发: 名单 / 目录 / 清单 | 78 | 43 | 0.040 | 20.9% | 9.3% | 79.5% |
| bare: other | 720 | 80 | 0.138 | 20.0% | 22.5% | 70.6% |
| bare: 指南 / 标准 / 规范 | 245 | 245 | 0.060 | 0.4% | 0.4% | 3.7% |

**Table 3c. Dropped pairs whose parent is one of the 60 hand-checked triggers, by
class.** [measured]

| class | hop | pairs | scored | median | relay | mid | elab | impl |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| (a) | all | 316 | 255 | 0.202 | 11.0% | 32.2% | 56.9% | 79.7% |
| (a) | P→M | 167 | 127 | **0.357** | **19.7%** | 37.8% | 42.5% | 95.8% |
| (b) | all | 37 | 29 | 0.096 | 0.0% | 17.2% | 82.8% | 62.2% |
| (c) | all | 7 | 7 | 0.184 | 0.0% | 14.3% | 85.7% | 85.7% |

The pairs under instrument-class parents on the province-to-city hop look like the
"citation + localized_of" cell of the memo's Table 4a (median 0.525, relay 29%): renamed
re-issuances. The pairs under administrative parents produce no relay.

**20 dropped pairs under (a)-class parents, read.** Sorted by `ovlp_src`; at most one
per parent until the parents ran out. [measured; the real/noise call is a reading]

| ovlp_src | band | hop | source | parent | call |
|---:|---|---|---|---|---|
| 0.739 | relay | C→P | 黑龙江 民间投资重点工作分工 (2010-10) | 国办函〔2010〕120号 重点工作分工 | real, copy |
| 0.731 | relay | C→P | 广东医保局 DIP 经办管理规程 (2023) | 国家医保局 DIP 经办管理规程 (2021) | real, copy |
| 0.683 | mid | P→M | 江门 处置铁路行车事故应急预案 | 广东 处置铁路行车事故应急预案 | real, copy |
| 0.683 | mid | C→P | 广东 政府核准的投资项目目录 (2014年本) | 国务院 政府核准的投资项目目录 (2014年本) | real, copy |
| 0.581 | mid | P→M | 揭阳 稳定和促进就业若干政策措施 | 广东 稳定和促进就业若干政策措施 | real, copy |
| 0.549 | mid | P→M | 深圳 加强个人诚信体系建设实施方案 | 广东 个人诚信体系建设分工方案 | real |
| 0.546 | mid | P→M | 中山 大面积停电事件应急预案 (2024) | 广东 大面积停电事件应急预案 (2016) | real; 8-year lag, parent edition may be stale |
| 0.453 | mid | C→P | 重庆 优化调整稳就业政策若干措施 | 国办发〔2023〕11号 稳就业政策措施 | real |
| 0.431 | mid | P→M | 河源 三线一单 分区管控方案 | 广东 三线一单 分区管控方案 | real |
| 0.385 | mid | C→P | 黑龙江 医改2016年重点工作任务 | 国办 医改2016年重点工作任务 | real |
| 0.358 | mid | C→M | 深圳民政局 行业协会商会乱收费专项清理整治 | 民政部等 乱收费专项清理整治 | real |
| 0.326 | mid | C→P | 黑龙江 2013年食品安全重点工作安排 | 国办 2013年食品安全重点工作安排 | real |
| 0.296 | elab | P→M | 汕尾 地震应急预案 (2026) | 广东 地震应急预案 (2013) | real; parent edition stale (12.6 years) |
| 0.171 | elab | P→M | 广州 口岸营商环境便利化工作方案 | 广东 口岸营商环境便利化措施 | real, elaboration |
| 0.105 | elab | P→M | 江门 加快卫生事业发展的若干意见 | 广东 医改近期工作要点 | mention, not an implementation |
| 0.072 | elab | C→M | 汕尾 行政规范性文件管理规定 | 国办发〔2018〕37号 规范性文件管理 | real, elaboration |
| 0.053 | elab | C→M | 聊城市 (title is the city name only) | 国办 2015年政府信息公开工作要点 | noise, broken record |
| 0.053 | elab | C→M | 西安 国家知识产权保护示范区建设方案 | 国知局 示范区建设方案 | real re-issuance, low copy |
| 0.051 | elab | C→M | 深圳教育局 2023年招生入学工作通知 (lag 1d) | 教育部办公厅 2023年招生入学工作通知 | real re-issuance, low copy |
| 0.014 | elab | P→M | 广州 科技创新"十四五"规划 | 广东 促进科技创新若干政策措施 | mention, not an implementation |

**Dropped-pair precision: 17 of 20 are real implementations (85%).** 12 copy the parent
(mid or relay), 5 elaborate it, 3 are a mention or a broken record. The two stale-parent
cases are a date-edition problem the identity layer's 400-day edition rule does not reach
when the newer provincial 预案 is not in the corpus; they are the right object with the
wrong edition.

## 4. Proposed rule

**R1 (admit).** A title with an issuance wrapper (印发, 公布 or 发布) whose core (the 《》
text or the 印发...的通知 inner) matches
`应急预案|预案|若干.{0,6}措施|政策措施|强化措施|便利化措施|工作要点|重点工作|重点任务|任务分工|工作安排|方案`
and does not match `整改方案|考评|考核|组建方案|申报|评选|名单|遴选` is a framework
instrument regardless of `algo_doc_type`.

**Keep excluding.** Bare 通知 with no printed core (3,910 dropped pairs at median 0.062,
and the hand-check split 6 / 4 / 1), 立法 and 规章 计划, 名单 / 目录 / 清单, 指南 / 标准 /
规范 (median 0.048, impl 38%), 制度 / 规则 / 章程, and anything without a wrapper (bare
应急预案 titles score 0.033).

**Against the hand-check.** R1 admits 28 of the 44 (a) parents, 0 of the 14 (b), 0 of
the 2 (c). Parent precision 100%, recall 64%. The 16 (a) parents it leaves out are the
bare 通知 directives (10), the three list-type instruments, two 规范 / 规程 and one 章程.
Those need a 文号-based or body-based test, not a title cue, and are left for a second
pass. [measured]

**Table 4a. Pairs R1 admits, and what they score.** [measured]

| hop | admitted | scored | median | relay | mid | elab | impl | baseline median / relay |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| C→P | 674 | 601 | 0.081 | 5.2% | 18.8% | 76.0% | 62.6% | 0.053 / 1.8% |
| **P→M** | **788** | 622 | **0.185** | **13.2%** | 26.7% | 60.1% | 88.8% | 0.074 / 8.5% |
| M→D | 54 | 42 | 0.041 | 0.0% | 2.4% | 97.6% | 42.6% | 0.052 / 1.1% |
| C→M | 434 | 397 | 0.064 | 1.8% | 16.9% | 81.4% | 70.0% | 0.044 / 0.2% |
| all four | 1,950 | 1,662 | | | | | | +3.9% on 50,634 |
| GD P→M | 725 | 584 | 0.189 | 13.4% | 27.1% | 59.6% | 91.4% | 0.084 / 9.1% |

R1 takes 788 of the 2,877 province-to-city pairs the gate drops and keeps the
high-fidelity part: the pairs it still excludes score 0.079 / 9.3%, the baseline's level.
Expected admitted relays on P→M: about 82 (13.2% of 622 scored), about 78 of them in
Guangdong. Against the memo's "gate off" figure (relays 474 to 637, +163), R1 recovers
roughly half the relays for a quarter of the pairs. Expected precision of the admitted
pairs, from the 20 read and Table 3c: 80 to 85% real implementations, 40% of scored
pairs at `ovlp_src` 0.3 or more against 25% in the baseline. Channel mix of the admitted
P→M pairs: citation 539, localized_of only 135, both 114.

Two parents dominate the admitted central hops and deserve a look before any memo is
re-run on the new set: 国家医保局等八部门 印发《...》 (88 C→P pairs at median 0.065) and
国务院 南沙总体方案 (48 C→M pairs at 0.040). Both are instruments; their cascades are
mentions, which the implementing flag already separates.

**Where to implement.** In the identity layer. `build_doc_identity.py` already computes
the wrapper and the core (`is_issuance_frame`, `title_core`, `_institutional_wrapper`),
and corpus-lessons A3 says the kind of text a document is belongs there. The minimal
change is a per-document column (for example `doc_identity.framework` 0/1, or an
`instrument_kind` label) built by R1 OR the current `FW_GENRES` / `FW_TITLE_RE` test, and
`is_framework` in `build_diffusion_events.py` reading that column with the present logic
as the fallback when the column is absent. Both consumers (`build_diffusion_events`,
`pairs.py`) then see one definition, the nightly rebuild carries it, and
`validate_cascades.py` can pin it (the three known cascades are unaffected: R1 adds
anchors and removes none). A one-line widening of `FW_TITLE_RE` is not the right fix:
that regex has no wrapper context, so adding 预案 or 方案 to it would also admit the
bare-title pockets (62 pairs at 0.033) and the 考评 / 组建 / 整改 方案 housekeeping.

## 5. Honesty

- Sixty titles and 600 characters each is one reader's call. The (a)/(b) split is clean
  for the printed-core shapes and genuinely uncertain for bare 通知; a second reader on
  the 11 bare 通知 rows would move the precision figure by a few points either way.
- The dropped-pair reading is 20 pairs under (a)-class parents, one per parent. It says
  the admitted pairs are mostly real; it does not measure the pairs R1 still excludes.
- `ovlp_src` needs a parent body. Several Guangdong 应急预案 carry only the cover note in
  `body_text_cn` with the plan as an attachment (4199084, 4297280; 4419971 防汛 scores
  0 of 15 pairs), so Table 3b under-scores the 预案 shape.
- The baseline moved since the memo (P→M 7,019 to 7,276) because identity and citations
  rebuild nightly. All comparisons here are within one run.
- R1 was written after reading the sample, then tested on the same sample. Parent
  precision 100% on 60 is an in-sample figure; Table 4a (all 1,950 admitted pairs) is the
  out-of-sample check and it holds.

## Appendix A. The 60-row hand-check

Set A = Guangdong provincial triggers, B = central triggers. n_src = `localized_of`
sources pointing at the trigger. R1 = admitted by the proposed rule.

| # | set | id | algo_doc_type | shape | n_src | class | R1 | title | note |
|---|---|---|---|---|---:|---|---|---|---|
| 1 | A | 4016742 | notice | 印发:清单 | 11 | a | no | 广东省人民政府关于公布广东省行政许可事项清单（2022年版）的通知 | body orders cities and counties to compile and publish their own list |
| 2 | A | 145674 | notice | 通知:other | 2 | c | no | 广东省人民政府办公厅关于做好优化建设工程防雷许可有关工作的通知 | relays a State Council 决定 with tasks; not a framework text |
| 3 | A | 145904 | notice | 印发:other | 1 | b | no | 广东省人民政府办公厅关于公布第八批火灾隐患重点地区整治工作检查验收结果和挂牌督办第九批火灾隐患重点地区的通知 | publishes inspection results and names supervised areas |
| 4 | A | 141703 | notice | 通知:other | 3 | b | no | 广东省人民政府办公厅关于明确企业情况综合负责部门等事项的通知 | assigns an internal lead department |
| 5 | A | 1054700 | notice | 印发:若干措施 | 1 | a | yes | 广东省人民政府印发关于进一步促进科技创新若干政策措施的通知 | 粤府〔2019〕1号, full measures text |
| 6 | A | 4440297 | notice | 通知:计划 | 1 | b | no | 广东省科学技术厅关于组织申报2024年度广东省重点领域研发计划“海洋科技”重大专项旗舰项目的通知 | 申报 call |
| 7 | A | 142604 | policy_issuance | 印发:工作方案 | 1 | b | no | 广东省人民政府关于印发《广东省人民政府党组党的群众路线教育实践活动整改方案》的通知 | the government's own 党组 rectification plan |
| 8 | A | 3166422 | policy_issuance | 印发:方案 | 10 | a | yes | 广东省人民政府关于印发广东省“三线一单”生态环境分区管控方案的通知 | binding zoning scheme for all cities |
| 9 | A | 2169964 | policy_issuance | 印发:other | 1 | a | yes | 广东省人民政府关于印发广东省优化口岸营商环境促进跨境贸易便利化措施的通知 | implements 国发〔2018〕37号 |
| 10 | A | 145311 | policy_issuance | 印发:应急预案 | 12 | a | yes | 广东省人民政府关于印发广东省大面积停电事件应急预案的通知 | |
| 11 | A | 3148410 | policy_issuance | 印发:重点工作任务 | 2 | a | yes | 广东省人民政府关于印发广东省深化“放管服”改革优化营商环境近期重点工作任务的通知 | binding task list |
| 12 | A | 2903650 | policy_issuance | 印发:若干措施 | 8 | a | yes | 广东省人民政府关于印发广东省进一步稳定和促进就业若干政策措施的通知 | |
| 13 | A | 3184636 | policy_issuance | 印发:应急预案 | 4 | a | yes | 广东省人民政府关于印发广东省重污染天气应急预案的通知 | |
| 14 | A | 146234 | policy_issuance | 印发:若干措施 | 1 | a | yes | 广东省人民政府关于印发广东省降低制造业企业成本支持实体经济发展若干政策措施的通知 | |
| 15 | A | 4701868 | policy_issuance | 印发:计划 | 2 | b | no | 广东省人民政府办公厅关于印发《广东省人民政府2025年度立法工作计划》的通知 | issuer's own legislation plan |
| 16 | A | 141465 | policy_issuance | 印发:章程 | 1 | a | no | 广东省人民政府办公厅关于印发《广东省社会保险监督委员会章程（试行）》的通知 | applies to every 监委会 in the province |
| 17 | A | 145435 | policy_issuance | 印发:目录 | 3 | a | no | 广东省人民政府办公厅关于印发《广东省社区（村）一门一网式政务服务自然人事项指导目录（试行）》的通知 | cities ordered to issue a local 目录 by year end |
| 18 | A | 144572 | policy_issuance | 印发:规范 | 1 | a | no | 广东省人民政府办公厅关于印发《广东省突发事件现场指挥官工作规范（试行）》的通知 | normative text |
| 19 | A | 2284752 | policy_issuance | 印发:工作要点 | 1 | a | yes | 广东省人民政府办公厅关于印发广东省“数字政府”改革建设2019年工作要点的通知 | tasks for cities |
| 20 | A | 4199084 | policy_issuance | 印发:应急预案 | 2 | a | yes | 广东省人民政府办公厅关于印发广东省交通基础设施建设工程事故应急预案的通知 | body is the cover note; plan is an attachment |
| 21 | A | 2386967 | policy_issuance | 印发:计划 | 1 | b | no | 广东省人民政府办公厅关于印发广东省人民政府2019年制定规章计划的通知 | housekeeping |
| 22 | A | 3337706 | policy_issuance | 印发:计划 | 1 | b | no | 广东省人民政府办公厅关于印发广东省人民政府2021年制定规章计划的通知 | housekeeping |
| 23 | A | 3963660 | policy_issuance | 印发:计划 | 1 | b | no | 广东省人民政府办公厅关于印发广东省人民政府2022年度制定规章计划的通知 | housekeeping |
| 24 | A | 146200 | policy_issuance | 印发:方案 | 3 | a | yes | 广东省人民政府办公厅关于印发广东省加强个人诚信体系建设分工方案的通知 | implements 国办发〔2016〕98号 |
| 25 | A | 142169 | policy_issuance | 印发:应急预案 | 10 | a | yes | 广东省人民政府办公厅关于印发广东省地震应急预案的通知 | |
| 26 | A | 142653 | policy_issuance | 印发:应急预案 | 4 | a | yes | 广东省人民政府办公厅关于印发广东省处置铁路行车事故应急预案的通知 | |
| 27 | A | 146205 | policy_issuance | 印发:方案 | 2 | a | yes | 广东省人民政府办公厅关于印发广东省大气污染防治强化措施及分工方案的通知 | |
| 28 | A | 146532 | policy_issuance | 印发:预案 | 5 | a | yes | 广东省人民政府办公厅关于印发广东省政府性债务风险应急处置预案的通知 | |
| 29 | A | 141804 | policy_issuance | 印发:应急预案 | 16 | a | yes | 广东省人民政府办公厅关于印发广东省森林火灾应急预案的通知 | |
| 30 | A | 143210 | policy_issuance | 印发:工作要点 | 5 | a | yes | 广东省人民政府办公厅关于印发广东省深化医药卫生体制改革近期工作要点的通知 | |
| 31 | A | 141797 | policy_issuance | 印发:应急预案 | 1 | a | yes | 广东省人民政府办公厅关于印发广东省石油供应中断应急预案的通知 | |
| 32 | A | 4297280 | policy_issuance | 印发:应急预案 | 8 | a | yes | 广东省人民政府办公厅关于印发广东省突发重大动物疫情应急预案的通知 | body is the cover note |
| 33 | B | 900048982 | application_guide | 通知:目录 | 1 | b | no | 关于组织开展2022年智慧健康养老产品及服务推广目录申报工作的通知 | 申报 call |
| 34 | B | 900077269 | application_guide | 通知:other | 1 | b | no | 工业和信息化部办公厅关于开展2026年科技型企业孵化器申报工作的通知 | 申报 call |
| 35 | B | 12650413 | notice | 通知:清单 | 1 | b | no | 关于做好2025年享受税收优惠政策的集成电路企业或项目、软件企业清单制定工作的通知 | list-compilation procedure |
| 36 | B | 12650819 | notice | 通知:other | 1 | b | no | 关于境内外资银行申请2021年度中长期外债规模的通知 | annual quota application |
| 37 | B | 900147106 | notice | 通知:other | 3 | b | no | 关于组织建立信息通信业“走出去”企业信息库的通知 | database building; no body |
| 38 | B | 900053746 | notice | 通知:规范 | 1 | a | no | 农业农村部 自然资源部关于规范农村宅基地审批管理的通知 | normative directive |
| 39 | B | 12702577 | notice | 通知:other | 1 | a | no | 国务院关于做好自由贸易试验区新一批改革试点经验复制推广工作的通知 | 国发〔2016〕63号; provinces must implement |
| 40 | B | 900042338 | notice | 印发:目录 | 2 | a | no | 国务院关于发布政府核准的投资项目目录（2014年本）的通知 | provinces issue their own catalogue by design |
| 41 | B | 900042693 | notice | 通知:other | 1 | a | no | 国务院关于开展第一次全国地理国情普查的通知 | 国发〔2013〕9号; tasks for provinces |
| 42 | B | 12651263 | notice | 通知:措施 | 7 | a | no | 国务院办公厅关于优化调整稳就业政策措施全力促发展惠民生的通知 | 国办发〔2023〕11号 |
| 43 | B | 12685168 | notice | 通知:规范 | 1 | a | no | 国务院办公厅关于加强行政规范性文件制定和监督管理工作的通知 | 国办发〔2018〕37号, normative |
| 44 | B | 12650899 | notice | 通知:other | 2 | a | no | 国务院办公厅关于进一步加强旅游市场综合监管的通知 | 国办函〔2025〕95号; tasks for local governments |
| 45 | B | 900044589 | notice | 通知:任务分工 | 1 | a | no | 国务院办公厅关于鼓励和引导民间投资健康发展重点工作分工的通知 | 国办函〔2010〕120号 |
| 46 | B | 900048329 | notice | 通知:other | 1 | a | no | 教育部办公厅关于做好2023年普通中小学招生入学工作的通知 | binding annual directive; provinces re-issue |
| 47 | B | 900050894 | notice | 通知:other | 2 | a | no | 民政部 国家发展改革委 市场监管总局关于开展行业协会商会乱收费专项清理整治工作的通知 | campaign directive with targets and schedule |
| 48 | B | 900140148 | other | bare:指南 | 6 | b | no | 政府信息公开指南 | an agency's own guide |
| 49 | B | 12651478 | policy_issuance | 印发:other | 1 | c | no | 中共中央办公厅 国务院办公厅印发《关于做好2022年元旦春节期间有关工作的通知》 | routine holiday work notice; provinces mirror it |
| 50 | B | 900042680 | policy_issuance | 印发:工作安排 | 1 | a | yes | 国务院办公厅关于印发2013年食品安全重点工作安排的通知 | |
| 51 | B | 900042244 | policy_issuance | 印发:工作要点 | 1 | a | yes | 国务院办公厅关于印发2015年政府信息公开工作要点的通知 | |
| 52 | B | 8718725 | policy_issuance | 印发:工作要点 | 3 | a | yes | 国务院办公厅关于印发2021年政务公开工作要点的通知 | szns mirror of 国办发〔2021〕12号 |
| 53 | B | 12684954 | policy_issuance | 印发:工作要点 | 2 | a | yes | 国务院办公厅关于印发2022年政务公开工作要点的通知 | |
| 54 | B | 900041339 | policy_issuance | 印发:方案 | 1 | a | yes | 国务院办公厅关于印发危险化学品安全综合治理方案的通知 | |
| 55 | B | 900041928 | policy_issuance | 印发:重点工作任务 | 1 | a | yes | 国务院办公厅关于印发深化医药卫生体制改革2016年重点工作任务的通知 | |
| 56 | B | 900063221 | policy_issuance | 印发:方案 | 1 | a | yes | 国务院办公厅关于印发降低社会保险费率综合方案的通知 | |
| 57 | B | 900050766 | policy_issuance | 印发:规程 | 1 | a | no | 国家医疗保障局办公室关于印发按病种分值付费（DIP）医疗保障经办管理规程（试行）的通知 | normative; Guangdong copied it at 0.731 |
| 58 | B | 900049471 | policy_issuance | 印发:工作方案 | 1 | a | yes | 国家知识产权局关于印发《国家知识产权保护示范区建设方案》的通知 | |
| 59 | B | 900047205 | policy_issuance | 印发:应急预案 | 1 | a | yes | 市场监管总局关于印发特种设备突发事件应急预案的通知 | |
| 60 | B | 900063263 | subsidy | 通知:other | 2 | a | no | 财政部税务总局退役军人部关于进一步扶持自主就业退役士兵创业就业有关税收政策的通知 | provinces set limits within the range |

## Appendix B. Method

Both scripts ran on the droplet against `file:documents.db?mode=ro`, outside the repo
(`/tmp/qa_fw/`), and imported `is_framework`, `build_pairs`, `load_docs` from the live
code so the predicates are the code's own.

```
# step 1: triggers failing the gate, counts by algo_doc_type x shape, 60-row stratified sample
SELECT t.doc_id, dt.algo_doc_type, dt.title, COUNT(*) FROM doc_identity s
JOIN doc_identity t ON t.doc_id = s.localized_of
JOIN documents ds ON ds.id = s.doc_id JOIN documents dt ON dt.id = t.doc_id
WHERE s.admin_level_doc IN ('municipal','district') AND t.admin_level_doc = 'provincial'
  AND dt.site_key GLOB 'gd*' GROUP BY t.doc_id;            -- then is_framework() in Python
# central: s.admin_level_doc IN ('provincial','municipal','district') AND t.admin_level_doc = 'central'

# step 3: the dropped pairs, scored
rows = build_pairs(conn, hops=DEFAULT_HOPS, require_framework=False, score=True, workers=2)
dropped = [r for r in rows if not r["parent_framework"]]   # 11,300 of 61,934; 185 s on a quiet box
```

Shape = wrapper (印发|公布|发布 present; else 通知; else bare) plus the first matching kind
in the 《》 core or the 印发...的通知 inner, in the order 应急预案, 预案, 若干措施/政策措施,
工作要点, 重点工作/任务分工/工作任务/工作安排, 工作方案/专项方案, 计划, 名单/目录/清单,
指南/指引/标准/规范/规程, 制度/规则/章程/准则, 方案.
