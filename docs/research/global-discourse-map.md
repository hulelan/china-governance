# Who says what about the world: a map of China's global-discourse vocabulary

*First pass, 2026-11-12. Prompted by the 160th-anniversary Sun Yat-sen speech, whose
world passage turned out to quote the 2021 history resolution (see the Sun Yat-sen at 160
reader). Evidence labels: **measured** = counted in the corpus; **inferred** = my reading of
measured patterns; **unverified** = believed, not checked here.*

## The question

Party discourse on China's place in the world is not one voice. Contention rarely appears as
open disagreement; it appears as *which formulation a speaker picks*, *what it pairs a concept
with*, *what it defines a concept against*, and *who takes a concept up and who quietly does
not*. All four can be counted. This memo is the first map.

## Design

- **Window: 2025-07-01 to 2026-11-12, cross-section only.** The corpus's media layer is almost
  entirely 2025-26 (54,755 media documents dated 2026 against 3,357 in 2025 and a few hundred a
  year before), so any multi-year trend would measure our crawl, not the discourse. Earlier
  years are used only for lineage: where a formulation first appears.
- **Speaker types** (`scripts/rnd/analysis/global_discourse/`: `speakers.py`, `concept_scan.py`,
  `counter_terms.py`; run on the droplet, read-only): central (non-media central documents) 14,299; party
  theory (求是, 共产党员网) 924; diplomacy (外交部) 134; state media (新华, 人民, 中国经济网,
  经济参考报, 科技日报…) 28,120; commentary (观察者网, 凤凰网) 20,421; business press 6,566;
  research (社科院, 宏观院, 清华 AIIG, 科协) 373; sub-national 56,560.
- **One copy per title per speaker type**, so a Xinhua story reposted by forty portals counts
  once per speaker type, not forty times.
- **38 concepts** (regexes in `gd_scan.py`), plus 12 official counter-terms in a second pass.

**Limits.** Diplomacy (134) and research (373) are thin. Academic journals (《世界经济与政治》,
《国际问题研究》, 《文化纵横》) are not crawled; the thinker layer is essentially 观察者网. 
`doc_identity.province` is missing on most sub-national documents in the window, so the
per-province cut is not usable yet.

## Findings

### 1. A division of labour: doctrine is asserted in one place and argued in another (measured)

Rate per 1,000 documents of each speaker type:

| concept | central | party theory | diplomacy | state media | commentary | research | sub-national |
|---|---|---|---|---|---|---|---|
| 人类命运共同体 | 10.0 | 59.5 | 156.7 | 10.9 | 3.3 | 34.9 | 4.0 |
| 四大全球倡议 | 4.1 | 31.4 | 97.0 | 4.0 | 0.6 | 2.7 | 1.6 |
| 全人类共同价值 | 2.0 | 10.8 | 14.9 | 2.0 | 0.4 | 2.7 | 0.5 |
| 真正的多边主义 | 2.0 | 16.2 | 52.2 | 2.7 | 0.8 | 5.4 | 0.5 |
| 全球南方 | 6.7 | 45.5 | 209.0 | 10.0 | 12.5 | 18.8 | 2.7 |
| 中国式现代化 | 57.1 | 98.5 | 74.6 | 34.7 | 4.9 | 115.3 | 38.3 |
| 霸权主义 | 1.4 | 6.5 | 0.0 | 1.3 | 2.4 | 2.7 | 0.4 |
| 西方中心 | 0.1 | 0.0 | 0.0 | 0.1 | 1.0 | 5.4 | 0.0 |
| 历史终结 | 0.0 | 0.0 | 0.0 | 0.1 | 0.8 | 2.7 | 0.0 |
| 普世价值 | 0.0 | 1.1 | 0.0 | 0.0 | 0.8 | 0.0 | 0.0 |
| 基于规则的国际秩序 | 0.0 | 0.0 | 0.0 | 0.0 | 0.8 | 0.0 | 0.0 |
| 自主知识体系 | 2.5 | 4.3 | 0.0 | 1.6 | 1.2 | 34.9 | 0.4 |
| 国际话语权 / 话语体系 | 4.1 | 1.1 | 0.0 | 2.3 | 1.7 | 24.1 | 0.5 |

The positive doctrine (命运共同体, the initiatives, 全人类共同价值, 真正的多边主义) is carried by
diplomacy and party theory. Commentary barely uses it, but it is the **only** speaker that names
the rival's term, "基于规则的国际秩序", and it leads on every foil: 西方中心, 历史终结, 普世价值.
Official text answers the rival concept with its own counter-terms instead of naming it:
以联合国为核心的国际体系 (central 19, state media 40, party theory 10 documents) and
以国际法为基础的国际秩序 (18, 31, 9). Research bodies frame the field as a contest over
knowledge and discourse (自主知识体系 34.9, 国际话语权 24.1).

*Inferred:* the official register asserts, the commentary register argues. If you want to see
the argument the doctrine is answering, read 观察者网, not 人民日报.

### 2. The civilizational vocabulary is where the real contest is (measured, then inferred)

The tightest bundle in the whole map is 文明冲突 + 文明优越 (lift 194; 21 of their 40 and 23
documents co-occur). Read in context, most official uses are one fixed formula,
以文明交流超越文明隔阂，以文明互鉴超越文明冲突，以文明共存超越文明优越, whose earliest corpus
instances are a 2022 任仲平 article and the 20th Party Congress report (earlier origin
unverified). So in official text the foils are part of a formula, not a live debate.

But there are **two competing civilizational vocabularies**, and they are carried by different
speakers (measured, documents in window):

| term | state media | sub-national | central | commentary |
|---|---|---|---|---|
| 人类文明新形态 (official) | 43 | 18 | 10 | 7 |
| 文明型国家 (张维为's "civilizational state") | 1 | 0 | 0 | 28 |
| 天下文明 (谢茂松), 文明型政党 (王义桅) | 0 | 0 | 0 | 3 |

The commentary side goes further than the official line. 谢茂松's 《天下文明何以可能》 (book forum,
观察者网 900200671) calls the CPC's political system "the third great institutional creation of
Chinese civilization" that will lead China toward a 天下文明 and offer the world "a new
civilizational imagination for the next five hundred years". The research side is more guarded:
a CASS review (900160234) says China's culture going out is **not** "replacing the old Western
centrism with a new cultural centrism". *Inferred:* that sentence is a guard against the
reading the commentary side invites, and it is the clearest sign of an internal argument about
how far the civilizational claim should go.

### 3. A live internal fight: anti-Western-centrism turned on itself (measured)

伪史论, the online claim that Western antiquity was fabricated, appears in 28 commentary
documents and nowhere else. It presents itself as "打破西方中心论". The pushback is from
inside: historian 王旭东, "伪史论者常以'反西方中心主义'自居，却深陷同一思维框架" (12725981), and
闻博, "伪史论的回旋镖，最终会打到我们自己头上" (900175926), whose point is that the method has
already turned on Chinese history ("唐朝根本不存在"), to the point that 陕西省文旅厅 had to deny a
rumour that netizens were demanding Tang sites be demolished (900076707). *Inferred:* this is
a genuine boundary dispute over the anti-Western-centrism theme the official line encourages:
the establishment wants the critique of Western centrism without the epistemic nihilism.

### 4. Contested ownership of the Global South and of multipolarity (measured)

- **Global South**: diplomacy uses it at 209 per 1,000, more than any other concept. Commentary
  argues over who owns it: India positioned as a rival claimant and a "bridge" to the West whose
  Global South advocacy "更多是针对中国" (刘宗义, 900138544); the "中国挤压" (China squeeze)
  charge and the MFA's rebuttal (毛宁, via 科技日报 900065553).
- **Multipolarity**: official text attaches a qualifier, 平等有序的世界多极化 (central 27, state
  media 56, sub-national 47), written into the 15th Five-Year Plan proposal (October 2025) with
  its twin 普惠包容的经济全球化. Commentary debates the bare concept: "多极化 but not multilateral"
  (Sachs, 12727660), "the risk is bloc fragmentation, not multipolarity itself" (900124795).
  *Inferred:* the qualifier 平等有序 is the official answer to exactly that worry.
- **Middle powers**: 中等强国 appears in 42 commentary documents and essentially nowhere official,
  a running response to Mark Carney's Davos 2026 claim that the rules-based order "is dead".

### 5. Provinces relay the doctrine and implement the Belt and Road (measured)

Sub-national documents use 中国式现代化 nearly as often as central ones (38.3 vs 57.1 per
1,000) but the world doctrine rarely (命运共同体 4.0, 四大全球倡议 1.6, 全人类共同价值 0.5). By
genre, sub-national uses of the doctrine are readouts and relays (四大全球倡议: 60 readout, 0
promulgation, 0 implementing; the top hits are reposted Xinhua accounts of Xi's SCO trip on
吕梁, 喀什, 通辽 portals) and Party study sessions (习近平外交思想 37 sub-national documents).
一带一路 is the exception: 100 promulgations and 45 implementing documents. *Inferred:*
provinces engage the world where it carries projects and money, and relay the ideology.

### 6. Lineage of the Sun speech's world sentence (measured; see the reader)

以世界眼光关注人类前途命运，从人类发展大潮流、世界变化大格局、中国发展大历史… first appears in
the 2021 history resolution under 坚持胸怀天下, is rarely quoted after (1 document in 2022, a
People's Daily commentary in April 2026, a 科技日报 commentary in July 2026), and is not in the
1 July 2026 Party-anniversary speech. The Sun speech keeps the sentence and drops the
resolution's reassurances (不搞零和博弈, 永远不称霸) for the named programmes.

## What this suggests to study next

1. **Close-read the two civilizational camps** (张维为 / 谢茂松 / 王义桅 against the official
   人类文明新形态 and the CASS guard), with a dated table of who says what.
2. **Add the missing venues**: 求是 back issues, 学习时报, 光明日报 理论版, 中国社会科学报, 文化纵横,
   and MFA speeches beyond 134 documents. Each widens the party-theory and research rows that
   are thin today.
3. **Turn the table into a tracker**: concept by speaker type by week, read off the nightly
   tables the way `/tracker` reads `diffusion_events`, so a new formulation's spread (or failure
   to spread) is visible as it happens.
4. **Kept / cut comparisons** for every 2026 foreign-policy speech against its source text, the
   method that found finding 6.

## Revisions

**2026-11-12, finding 3 (measured).** The count of 28 commentary documents containing 伪史论 was
inflated: 20 carry the term only in a 观察者网 "related articles" sidebar link, and 8 engage it
(12725981, 900075778, 900076707, 900145644, 900104244, 900131727, 900145583, 900175926). The
王旭东 line quoted above is that article's **title**; the stored body is page 1 of 2 and does not
contain it. The finding itself holds and is stronger than first stated: the pushback reaches the
centre. 中国社会科学报 (front-page commentator article, 2026-08-20) and 《求是》 (2026 issue 17,
2026-09-01) both classify pseudo-history as historical nihilism, while the CAC had already listed
伪史学 as false information in its December 2025 online-celebrity notice (12693814). The
Tang-sites "demolition calls" story that triggered the summer wave was itself false (denied by
陕西省文旅厅, 900076707). All Party and state pieces are held only as 观察者网 reposts. Full
evidence: the pseudo-history view of the Disputes reader.

**2026-11-12, all commentary counts (measured, scope not yet re-measured).** About 913 观察者网
documents carry a sidebar list of other headlines inside the stored body (观察者头条, timestamps,
评论 N). A plain match counts a term that appears only in that list: 中国挤压 in commentary falls
from 13 to 5 once matches in a ±150-character clutter window are dropped. Every commentary rate in
finding 1's table is therefore an upper bound until re-run with the filter; the weekly tracker
applies it. Finding 4 also needs one correction: official text does claim to **lead** the Global
South (引领, 15 titles, e.g. 外交部 900154072 团结引领全球南方联合自强); what it never does is cast
India as a rival.
