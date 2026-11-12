# Pre-registration: Qin, Strömberg & Wu (2018), "Media Bias in China", on our speaker types

*Written 2026-11-12 (about 21:40 UTC), before any outcome term was counted. Computed before
writing: deduplicated denominators per site in the window (`media_bias_qsw.py --coverage`), and
the list of central accident and disaster supervision notices used to pick the timing-test events
(the event source, not the outcome). Any later change to a measure, a rule or a threshold is
appended below as a dated note, never edited in place.*

## The paper (stated)

Bei Qin, David Strömberg, Yanhui Wu, "Media Bias in China", *American Economic Review* 108(9),
2018, 2442-76, DOI 10.1257/aer.20170947. Their November 2016 draft (read in full) counts, over
16 million articles of 117 general-interest newspapers 1998-2010 (WiseNews), the share of
articles in nine keyword categories: **Party line** (mentions of 2,111 named leaders; articles
citing Xinhua; coverage of Xinhua's versus Epoch Times' top-10 stories), **mass line**
(corruption cases, disasters and accidents with more than 30 deaths), **bottom line** (sport,
entertainment, crime). Party dailies mention leaders in 22% of articles against 5% for
commercial subsidiaries, and, against the obvious expectation, commercial papers cover
corruption and disasters **less** than Party dailies, not more. The first principal component of
the nine is their bias index.

## Population

- `documents` dated 2025-07-01 to 2026-11-12 (`date_published`, ISO date), speaker type from
  `web/services/discourse_vocab.speaker(site_key, doc_identity.admin_level_doc)`.
- `strip_chrome` applied to `guancha`, and guancha pages with under 30 article characters after
  it dropped. Body at least 200 characters.
- **One copy per (site, normalized title)**, the longest body.
- Denominators (measured by `--coverage`): state media 27,849 (stdaily 19,811, xinhua 4,903,
  people 1,474, ce 1,316, jjckb 337); party theory 916 (qstheory 907, dangyuan 9); commentary
  19,075 (guancha 13,004, ifeng 6,071); business press 6,519 (qbitai 3,817, yicai 899, 36kr 473,
  elsewhere 429, latepost 408, eeo 239, tmtpost 184, huxiu 65); research 351; diplomacy 114;
  central (non-media) 14,257; sub-national 53,877.
- The new party-theory sites (qiushi, hongqi, studytimes, gmrb_theory, rmlt) and research `cssn`
  were **not yet in documents.db** at 21:20 UTC; this run proceeds without them.

## Speaker groups compared

- **Party-owned media** (QSW's Party dailies): state media + party theory sites.
- **Commercial media** (QSW's evenings and subsidiaries): business press + commentary (guancha,
  ifeng).
- Central and sub-national government documents are **reference columns**, not a treatment arm.
- **Primary statistic:** unweighted mean over sites with at least 100 deduplicated documents of
  each site's rate per 1,000 (QSW's unit is the newspaper, and stdaily alone is 71% of state
  media). Six Party-owned sites (stdaily, xinhua, people, ce, jjckb, qstheory) against nine
  commercial (qbitai, yicai, 36kr, elsewhere, latepost, eeo, tmtpost, guancha, ifeng). Exact
  permutation p over all C(15,6) = 5,005 labellings. Pooled per-type rates are secondary.

## Measures (frozen; regexes in `media_bias_qsw.py:RX`)

Counted by Python regex, so the FTS length floor does not apply. Title measures read the title
only; body measures read title + body.

| key | measure | QSW analogue |
|---|---|---|
| lead_title_xi | 习近平 or 总书记 in the title | leader mentions (the "leading with a leader" form) |
| lead_title_pbsc | any PBSC member's name or 总书记 in the title | leader mentions |
| lead_body_xi | 习近平 anywhere | leader mentions (their body form) |
| xh_relay | a Xinhua dateline (新华社…X月X日电), 来源：新华社/新华网, 新华社记者, 据新华社 | Xinhua cites (copy) |
| xh_any | 新华社 or 新华网 anywhere | Xinhua cites (their exact form) |
| corrupt_case | 涉嫌严重违纪违法, 接受…审查调查, 纪律审查和监察调查, 被查, 双开, 开除党籍, 受贿罪, 严重违纪违法问题 | corruption cases |
| accident_dead | an accident word (事故 火灾 爆炸 坍塌 车祸 矿难 …) within 60 characters of a stated death count | accidents |
| disaster_dead | a disaster word (地震 洪水 山洪 台风 泥石流 暴雨 …) within 60 characters of a death or missing count | disasters |
| market_title | market / finance word in the title (股价 A股 市值 营收 融资 IPO 上市 基金 汇率 并购 …) | (not in QSW; the economic goal of business press) |
| sport_title, ent_title, crime_title, soft | title words for sport, entertainment, crime; soft = any of the three | bottom line |

QSW's Epoch Times top-story ratio is not replicable (no overseas opposition outlet is crawled).

## Predictions (QSW's sign, then my own forecast with rough magnitude)

Primary statistic is the Party-owned / commercial ratio of site means.

| measure | QSW sign | my forecast |
|---|---|---|
| lead_title_xi | Party > commercial | holds, ratio at least 3 (Party ~40-80 per 1,000, commercial under 15) |
| lead_body_xi | Party > commercial | holds, ratio 2-5 |
| xh_relay | Party > commercial | holds at the site mean, ratio at least 2; but guancha alone will relay at a rate comparable to people / ce |
| xh_any | Party > commercial | holds |
| corrupt_case | Party > commercial (QSW's counter-intuitive result) | holds at the site mean only because seven of nine commercial sites are tech or VC outlets that carry almost none; **guancha will be the highest single media site**, so the commentary type exceeds state media pooled |
| accident_dead | Party > commercial (modest in QSW) | null or reversed: ratio between 0.7 and 1.5 at the site mean; guancha and ifeng at or above xinhua / people |
| disaster_dead | Party > commercial | holds weakly (ratio 1-2) |
| market_title | (no QSW sign; commercial expected higher) | commercial > Party, ratio at least 1.5 |
| soft | commercial > Party | holds, ratio at least 1.5, carried by ifeng; tech outlets low on sport and entertainment |

Reference columns (forecast only): central government highest on lead_title_xi of all
non-media types; sub-national government lowest on soft news and on accident_dead except
business press.

## Timing test

**Event rule (decided from government sources, before any media coverage was looked at).**
Accidents and disasters: every in-window event whose investigation the central government
escalated, as recorded in a central non-media document: 国务院安委会 挂牌督办, 国家防灾减灾救灾委员会
挂牌督办, or a 国务院 提级调查.

| id | event | event day | key regex (title or first 400 body chars) |
|---|---|---|---|
| A1 | 包头 包钢 pressure-vessel explosion, 5 dead, 5 missing (安委督〔2026〕1号) | 2026-01-18 | `包钢[^。]{0,40}(?:爆炸|事故)|包头[^。]{0,30}爆炸` |
| A2 | 襄阳宜城 fireworks shop 爆燃, 12 dead (安委督〔2026〕2号) | 2026-02-18 | `宜城[^。]{0,40}(?:爆燃|烟花|事故)` |
| A3 | 泉州晋江 陈埭 shoe-factory fire, 28 dead (安委函〔2026〕1号) | 2026-07-09 | `晋江[^。]{0,40}(?:火灾|鞋)|陈埭` |
| A4 | 定西渭源 flash flood, 25 dead (国防减救督〔2026〕1号) | 2026-07-26 | `渭源[^。]{0,40}(?:山洪|洪|灾)` |
| A5 | 青岛北海造船 fire, 25 dead (国务院 提级调查) | 2026-09-10 | `北海造船` |

Corruption cases: the first three distinct officials, dated 2026-07-26 onward (every media site
active), whose title announces 接受…审查调查 and carries a provincial or ministerial rank word
(省长 / 副省长 / 省委常委 / 省委书记 / 部长 / 副部长 / 中管). Event day = the earliest such
document anywhere in the corpus. Names fixed in an appended note before coverage is read.

**Outcome per event:** which speaker types carry it within [day - 3, day + 30], first-day lag per
type, and the Xinhua-relay share of the covering documents per type.

**Forecasts.** Accidents: state media and commentary both cover every event, commentary no later
than state media (lag 0-1); business press covers at most the two industrial ones (A1, A5);
the Xinhua-relay share of state-media coverage is at least 50% and of commentary coverage
20-50%. Corruption: covered by commentary and state media the same day; business press only
for a finance or SOE official; Xinhua-relay share under 30% everywhere (the source is the
中央纪委国家监委 website, not Xinhua).

## What is reported whatever happens

Every registered measure, including nulls and wrong-signed results, per type, per site, and
the primary contrast with its permutation p. Robustness: drop stdaily; drop qbitai; drop
xinhua; drop guancha; the dense window from 2026-07-26 (ifeng and jjckb both present); news
genre only.

## Appended notes

**2026-11-12, about 21:50 UTC, before --measure or --events was run.** The corruption-case rule
selects, from titles only: C1 叶建春 (江西省长), earliest document 2026-08-27; C2 刘建洋 (江苏省委常委、
组织部部长), 2026-08-31; C3 鲁昕 (教育部原副部长), 2026-09-28. Keys: `叶建春`, `刘建洋`, `鲁昕`, each
also required to co-occur with `审查调查|严重违纪违法|被查` in the title or first 400 body characters
(applied in the analysis of the event rows). Seen in passing while selecting: all three
qualifying titles are on `stdaily`; whether other types carry the same events under other titles
is the outcome and has not been looked at.

**2026-11-12, about 22:05 UTC, after the first --measure and a hand-check, before any lead
variant was counted.** A 64-row hand-check of the registered accountability measures found
`corrupt_case` precise on `stdaily` (8 of 8) and `guancha` (6 of 8) but not on `ifeng` (5 of 8:
被查实, 被查出) and **0 of 8 on `latepost`**, where every hit was in a sidebar of other outlets'
headlines (207 of 408 latepost bodies carry 跟贴 sidebar chrome, which `strip_chrome` does not
handle). Two SECONDARY variants are added; the registered measures stay primary and are reported
unchanged:
- `corrupt_lead`: the corruption regex with bare 被查 replaced by `被查(?![出实获扣封明到验])`
  and 受贿罪 by 以受贿罪, matched on the title + first 300 body characters only.
- `accident_lead`, `disaster_lead`: the registered regexes on title + first 300 body characters
  only (the article's lead, where a sidebar cannot reach).
No prediction is re-registered for them; they are reported as a precision check on the primary.

**Correction, 2026-11-12, 21:33 UTC (clock read on the droplet).** The times written in the header
and in the two notes above ("about 21:40", "21:50", "22:05") were estimated, not read, and are
too late: the droplet clock read 21:33 UTC after both notes were written. The ORDER they state is
correct and is what the registration rests on: the header before any outcome count, the first
note before `--measure` and `--events`, the second after the first `--measure` and before any lead
variant was counted. Left in place rather than edited, per the append-only rule.
