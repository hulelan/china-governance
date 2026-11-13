# The world in 《求是》, 2019-2026: mission recedes, threat holds, struggle fades

*First pass, 2026-11-12. Pre-registered in `docs/working/prereg-qiushi-world.md` before any
concept was counted. Script: `scripts/rnd/analysis/qiushi_world_series.py` (run on the droplet,
read-only, against a copy of `web/services/discourse_vocab.py`). Evidence labels: **measured** =
counted in the corpus; **stated** = what a text says; **inferred** = my reading of measured
patterns; **unverified** = believed, not checked here.*

## Why this is a time series and the earlier map was not

`global-discourse-map.md` had to stay a 2025-26 cross-section, because the media layer before
2025 is a few hundred documents a year and any trend would have measured our crawler. 《求是》 is
different: the crawler walks it issue by issue, so the denominator is the journal.

**Verified first (measured).** Every year 2019-2025 holds all 24 issues, and 2026 holds issues
1-21 (through 2026-11-01) with no gap. Each issue has 10-24 articles; every issue carries an
article by 习近平 except one (2025/03). After dropping 6 duplicate titles and the body-less
国家统计局 统计图表 rows (body under 200 characters, about 25 a year):

| year | issues | articles | per issue (mean) | Xi articles | median article chars |
|---|---|---|---|---|---|
| 2019 | 24 | 341 | 14.2 | 24 | 5,602 |
| 2020 | 24 | 359 | 15.0 | 24 | 5,441 |
| 2021 | 24 | 339 | 14.1 | 24 | 5,689 |
| 2022 | 24 | 409 | 17.0 | 24 | 4,937 |
| 2023 | 24 | 413 | 17.2 | 24 | 5,200 |
| 2024 | 24 | 369 | 15.4 | 24 | 6,033 |
| 2025 | 24 | 396 | 16.5 | 23 | 5,310 |
| 2026 (1-21) | 21 | 410 | 19.5 | 21 | 4,508 |

One real change in the journal itself (measured): 2026 issues carry more and shorter articles
(19.5 per issue, median 4,508 characters), rising through the year to 22-24 per issue by
summer. It is not a crawl artifact: the site's URL scheme changed at issue 2024/24 and nothing
moves there. Because shorter articles lower the chance of any given term appearing, every share
below is checked against occurrences per 100,000 characters, which does not depend on length.
Whether the online table of contents lists every printed article is **unverified**; that it
lists the statistical-chart pages suggests it is close to complete.

Four pipeline checks were registered and all pass (measured): 全球治理倡议 appears in no
article before issue 2025/17 (first: 2025/18); 全球文明倡议 in none before 2023/06 (first:
2023/07); 动荡变革期 in 1 article before 2020/21 (2020/17, a commentator piece of 1 September
2020); 全球南方 in 0 articles 2019-21 against 30 in 2025.

## Finding 1. The pre-registered ratio rose, but not the way the plenum suggested (measured)

Share of articles using each concept (title + body), 《求是》, all authors:

| concept | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|
| n articles | 341 | 359 | 339 | 409 | 413 | 369 | 396 | 410 |
| **MISSION index** | 14.4 | 19.2 | 18.3 | 21.3 | 21.5 | 18.2 | 17.2 | **7.6** |
| 人类命运共同体 | 14.4 | 18.9 | 16.5 | 18.6 | 16.9 | 13.8 | 14.1 | 6.3 |
| any 全球…倡议 | 0.0 | 0.0 | 0.9 | 2.7 | 6.8 | 8.7 | 9.6 | 3.9 |
| 全人类共同价值 | 0.9 | 0.0 | 3.5 | 8.8 | 6.3 | 4.9 | 5.1 | 1.0 |
| 胸怀天下 | 0.3 | 0.6 | 1.8 | 5.4 | 8.2 | 2.4 | 1.8 | 0.5 |
| 世界眼光 | 0.3 | 0.3 | 2.1 | 1.5 | 4.4 | 2.4 | 2.3 | 1.5 |
| **THREAT index** | 30.5 | 33.1 | **51.6** | 42.1 | 41.6 | 32.0 | 32.3 | 25.4 |
| 百年(未有之)变局 | 13.2 | 20.6 | 32.4 | 28.9 | 22.5 | 19.5 | 23.7 | 19.0 |
| 动荡变革期 | 0.0 | 2.8 | 4.4 | 5.4 | 5.8 | 3.3 | 5.3 | 3.4 |
| 霸权主义 | 2.9 | 3.3 | 3.8 | 3.9 | 2.4 | 3.0 | **6.8** | 3.4 |
| 敢于斗争 / 斗争精神 / 伟大斗争 | 21.1 | 21.4 | **33.9** | 24.0 | 20.3 | 12.5 | 8.3 | 6.3 |
| 总体国家安全观 | 1.8 | 2.2 | 5.6 | 6.4 | 8.5 | 6.5 | 4.8 | 2.7 |
| bare 斗争 | 39.9 | 44.3 | 54.9 | 35.5 | 29.8 | 28.2 | 25.8 | 17.6 |
| bare 国家安全 | 10.0 | 11.4 | 18.9 | 15.6 | 19.1 | 16.3 | 14.1 | 13.9 |
| 全球南方 | 0.0 | 0.0 | 0.0 | 0.0 | 0.2 | 1.6 | 7.6 | 4.4 |
| 多极化 | 4.4 | 1.1 | 2.7 | 1.0 | 0.5 | 2.4 | 4.0 | 3.4 |
| 平等有序的(世界)多极化 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 2.2 | 2.8 | 0.7 |
| 中国式现代化 | 0.0 | 0.8 | 6.2 | 17.8 | 55.0 | 65.0 | 56.3 | 38.8 |
| 人类文明新形态 | 0.0 | 0.0 | 4.4 | 7.8 | 8.5 | 4.9 | 3.5 | 1.5 |

Indices as registered: MISSION = 命运共同体, any initiative, 全人类共同价值, 胸怀天下. THREAT =
百年变局, 动荡变革期, 霸权主义, the 敢于斗争 family, 总体国家安全观.

**P1, the registered test (pooled 2019-20 against 2025-26):**

| | 2019-20 (n=700) | 2025-26 (n=806) | change |
|---|---|---|---|
| THREAT share | 31.9% | 28.8% | down |
| MISSION share | 16.9% | 12.3% | down |
| THREAT / MISSION | 1.89 | 2.34 | **+24% (holds, threshold +20%)** |
| T2 (变局, 动荡变革期, 霸权主义) share | 18.1% | 24.3% | up |
| M2 (MISSION minus initiatives) share | 16.9% | 10.8% | down |
| T2 / M2 | 1.08 | 2.25 | **+108% (holds)** |

So P1 holds on both versions, narrowly on the primary. But the registered ratio hides the
mechanism, and the mechanism is not "threat rises":

- **The threat index did not rise; it peaked in 2021 and came back down** (30.5% in 2019, 51.6%
  in 2021, 25.4% in 2026). What moved the ratio is mission falling, most of all in 2026.
- **The threat index splits in two.** The world-threat terms (百年变局, 动荡变革期, 霸权主义) are
  up from 18% to 24%. The 斗争 family is down by two thirds (21% to 6%, and per 100,000
  characters 10.3 to 3.8). Pooled in one index they cancel.
- **The 2026 mission drop is length-independent.** 人类命运共同体 per 100,000 characters: 10.4
  (2019), 12.8 (2020), 14.1 (2021), 7.2 (2025), **2.6** (2026). The initiatives fall too (15.1 to
  5.0), though 2025 was inflated by the GGI launch and the 80th-anniversary issues.

*Inferred:* the plenum dispute's "world as mission becomes world as threat" is half right for the
journal. The world is still described as dangerous at the 2019-20 rate, with more of the danger
now named as hegemony and turbulence; what has thinned in 2026 is the affirmative programme.
The plenum contrast (shared-future language 2 → 0) matches 《求是》 in 2026, where 命运共同体
appears in 6% of articles against 14-19% in every earlier year.

## Finding 2. Not a composition effect: Xi's articles and everyone else's move together (measured)

| | 2019-20 | 2021-24 | 2025-26 |
|---|---|---|---|
| Xi-authored, n | 48 | 96 | 44 |
| Xi: THREAT / MISSION | 1.67 | 2.00 | 2.43 |
| Xi: T2 / M2 | 0.50 | 1.00 | 1.57 |
| other authors, n | 652 | 1,434 | 762 |
| other: THREAT / MISSION | 1.92 | 2.10 | 2.34 |
| other: T2 / M2 | 1.14 | 1.44 | 2.31 |

P2 holds: the direction is the same with Xi's articles removed (non-Xi articles are 94% of the
journal). The 2026 mission drop is in both: 命运共同体 in 1 of 21 Xi articles (4.8%, against 26%
in 2025) and in 6.4% of other articles (13.4% in 2025). Xi's own articles are the noisier series
(n of 21-24 a year): his 2020 articles carry the most shared-future language of any year (41.7%),
his 2021 articles the most struggle language (66.7%). With n that small, single speeches move the
year, so the Xi series is a check on direction only.

## Finding 3. The replication splits: the world-threat shift replicates, the 2026 mission drop does not (measured)

Same terms, same rules, year from `date_published`. Article counts in these two sources swing
with the crawler (光明日报 2021 is 959 against 1,272-1,621 in other years; 人民论坛 2020 is 1,511),
so only shares are compared. 《红旗文稿》 (from 2020) is added as a third check.

| source | THREAT / MISSION 2019-20 | 2025-26 | change | T2 / M2 2019-20 | 2025-26 | change |
|---|---|---|---|---|---|---|
| 《求是》 | 1.89 | 2.34 | +24% | 1.08 | 2.25 | +108% |
| 光明日报 theory pages | 1.35 | 1.31 | −3% (flat) | 0.87 | 1.11 | +28% |
| 人民论坛 | 1.30 | 1.32 | +2% (flat) | 1.00 | 1.26 | +26% |
| 《红旗文稿》 (2020 base) | 1.68 | 2.02 | +20% | 1.12 | 1.74 | +55% |

MISSION share by year (%), with n:

| source | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|
| 《求是》 | 14.4 (341) | 19.2 (359) | 18.3 (339) | 21.3 (409) | 21.5 (413) | 18.2 (369) | 17.2 (396) | 7.6 (410) |
| 光明日报 | 11.8 (1,405) | 8.6 (1,555) | 10.2 (959) | 16.7 (1,272) | 16.1 (1,333) | 10.3 (1,368) | 9.1 (1,621) | 9.2 (1,297) |
| 人民论坛 | 6.2 (613) | 11.4 (1,511) | 17.6 (1,030) | 20.2 (659) | 19.3 (587) | 14.2 (655) | 15.4 (671) | 14.0 (695) |
| 《红旗文稿》 | | 18.7 (411) | 21.2 (330) | 33.2 (298) | 30.7 (274) | 21.5 (275) | 17.3 (284) | 13.4 (238) |

THREAT share by year (%):

| source | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|
| 《求是》 | 30.5 | 33.1 | 51.6 | 42.1 | 41.6 | 32.0 | 32.3 | 25.4 |
| 光明日报 | 13.7 | 13.6 | 16.4 | 26.2 | 21.6 | 13.2 | 12.0 | 12.1 |
| 人民论坛 | 5.5 | 15.8 | 29.4 | 32.2 | 29.8 | 22.4 | 19.2 | 19.4 |
| 《红旗文稿》 | | 31.4 | 50.9 | 60.7 | 50.7 | 38.9 | 31.7 | 31.1 |

P3 **fails on the primary index** (光明日报 and 人民论坛 are flat, inside the ±20% band) and
**holds on T2 / M2** (all four sources up 26-108%). Three things replicate everywhere:

1. **A 2021-23 hump in all world vocabulary**, mission and threat alike, around the centenary
   and the 20th Party Congress, followed by a return toward 2019-20 levels.
2. **The 斗争 family falls in all four**: 敢于斗争 family 2021-22 peak to 2025-26 at roughly a
   third (《求是》 33.9 → 6.3, 《红旗文稿》 28.9 → 10.1, 人民论坛 10.6 → 3.2, 光明日报 10.6 → 2.6).
3. **全球南方 enters late and rises** in all four (at most 0.3% of articles in any source before 2023; 2025-26 at 4-9% in
   《求是》, 《红旗文稿》 and 人民论坛, 1.6-2.2% in 光明日报).

What does **not** replicate is the 2026 collapse of mission vocabulary: 人民论坛 holds at 14.0%
and 光明日报 at 9.2%, both flat on 2025; only 《红旗文稿》 (13.4%, down from 17.3%) moves with
《求是》. *Inferred:* 《红旗文稿》 is published by the 求是杂志社 (**stated** on its masthead, not checked here), so the 2026 drop belongs to one
editorial house, not to Party theory in general. 人民论坛 even carries the initiatives more in
2026 than ever (7.5%, GGI 5.6%).

## Finding 4. Turning points, with dated sentences (measured; each sentence verified as a substring of `body_text_cn` by the script's assert)

- **2019: 百年变局 is already the frame.** 黄坤明, 2019/01 (900221201): "当今世界正处于百年未有之大变局".
  In 2019 the 斗争 family is about the Party's own project: 本刊编辑部, 2019/01 (900221200),
  "更好地进行伟大斗争、建设伟大工程、推进伟大事业、实现伟大梦想".
- **September 2020: 动荡变革期 enters, before the Fifth Plenum.** 本刊评论员, 2020/17, 1 Sept
  2020 (900220580): "当前，世界进入深度动荡变革期…进行具有许多新的历史特点的伟大斗争". By
  2022/03 it carries the full threat list (张宏志, 900220051): "世界进入新的动荡变革期，不稳定性不确定性显著上升，经济全球化遭遇逆流，单边主义、保护主义抬头".
- **2021: the threat peak is a struggle peak.** 51.6% of articles carry a threat term, driven by
  the 斗争 family (33.9%). Example, 赵克志, 2021/01 (900220448): "敢于斗争、善于斗争，充分发挥'刀把子'的作用，依法严厉打击境内外敌对势力渗透颠覆捣乱破坏活动".
- **January 2024: multipolarity gets its qualifier and the Global South arrives.** 王毅, 2024/02
  (900219178): "我们倡导平等有序的世界多极化和普惠包容的经济全球化" and "'全球南方'声势卓然壮大".
  The first 全球南方 article is a 新华社 piece in 2023/23 (900219237).
- **2025: hegemony named most often.** 霸权主义 in 6.8% of articles, the highest of any year (next: 3.9% in 2022). Xi,
  2025/01 (900218802): "霸权主义、强权政治、单边主义、保护主义违背时代潮流，不得人心、失道寡助".
- **January 2026: the plenum's threat sentence appears ten months early.** 祝灵君, 2026/01
  (900218375): "单边主义、保护主义抬头，霸权主义和强权政治威胁上升，大国博弈更加复杂激烈". The
  October 2026 decision reads "霸权主义和强权政治威胁上升" (`plenum.json`). The same article
  uses 斗争精神 for cadre conduct, not for the world: "缺少担当品格、斗争精神", next to "躺平" and
  "摆烂". *Inferred, from these examples only, not counted:* the remaining 斗争 uses in 2026 lean
  toward Party discipline (the 中央纪委 piece in 2026/03, 900218339: "敢于善于斗争的纪检监察铁军"),
  so even the residual struggle vocabulary has turned inward.

## What this says about the order-replacing vs regime-securing debate (inferred)

`ideology-literature-review.md` §7 sets Rolland, Doshi and Tobin (the shared-future language
describes an order-replacing ambition) against Weiss (a regime-securing one). One journal's
vocabulary cannot settle that, but two facts bear on it. First, the affirmative world programme
in the Party's flagship journal is not monotone: it peaked in 2022-23 and in 2026 sits at under
half its 2019 share, while the threat description held steady. A sustained order-replacing
project would predict the programme to grow with China's capacity, not to recede. Second, the
receding is local to the 求是 house and does not show in 人民论坛 or 光明日报, so the cleaner
reading is an editorial priority of 2026 (domestic: 十五五, self-revolution, Party discipline)
rather than an abandoned doctrine. Both facts fit the regime-securing reading somewhat better,
and neither excludes the other one.

## Limits

- **One 2026 is not a trend.** The mission drop is one partial year (21 issues) and does not
  replicate outside the 求是 house. Re-test at issue 2026/24 and again in 2027.
- **Article share is coarse.** One mention counts the same as a whole article on the theme.
  Occurrences per 100,000 characters agree in direction for every claim above.
- **Keyword indices.** 斗争 in particular is polysemous (anti-corruption, risk prevention,
  ideology, foreign pressure); the family regex cannot tell these apart, which is why it was
  reported separately.
- **人民论坛 2019** is suspiciously low on every index (6.2% / 5.5%); its 2019 crawl may hold a
  different mix of sections. The T2 / M2 replication holds with 2020 as the base as well.
- **Year in the replications is `date_published`**, not an issue cover date, and 光明日报 / 人民论坛
  counts vary with crawl depth by year; shares are robust to that only if the crawl's misses are
  unrelated to topic, which is **unverified**.

## Revisions

(none yet)
