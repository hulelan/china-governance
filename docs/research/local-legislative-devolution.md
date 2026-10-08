# Counting jurisdictions instead of documents: the 2015 Legislative Law amendment as a measurable devolution

*Findings memo, 2026-10-08. Every breadth statement in this project has been a document count —
"~14 of 34 provincial units crawled", "107 of 361 prefectures". That measures where we crawled.
The per-document `doc_identity.province` and `admin_level_doc` fields let us ask a different
question for the first time: how many distinct **jurisdictions** appear in the corpus as issuers?
The answer reframes the corpus's reach, and then hands over a dated institutional discontinuity
that the document counts had hidden. Companion to `recentralization-experimentation.md` (which
reads the central-local balance in one direction) and `corpus-lessons.md` A1 (which built the
per-document level this memo depends on).*

---

## The short version

Jurisdictional breadth is **complete**: all 31 mainland provincial-level units appear, with
339–1,939 local regulations each, spanning 1980–2026. Document breadth is not — for 21 of those
31, upwards of 75% of what we hold is a single genre from a single source.

Inside that one genre sits a clean natural experiment. The number of **distinct municipal
legislating bodies** was flat at ~43 per year from 2009 through 2015, jumped to **214 in 2016**,
and settled around 320. The 2015 amendment to the 立法法 (Legislative Law, effective 2015-03-15)
extended local legislative power from 49 designated cities to all 设区的市. The corpus recovers
the pre-amendment legal roster exactly — **79 jurisdictions, which is 49 authorized cities plus 30
autonomous prefectures** — which is why this is not a collection artifact. By 2024 municipal
regulations outnumber provincial ones, 1,285 to 813.

The amendment also *confined* new entrants to three domains (城乡建设与管理, 环境保护,
历史文化保护). That constraint is visible in the titles: new entrants legislate inside those
domains **8.8 to 15.9 percentage points more often** than contemporaneous incumbents, against an
incumbent time-trend of about +6.5 pt. The constraint binds, and it binds loosely.

---

## 1. Breadth is complete; depth is Guangdong

`doc_identity` carries a per-document `province` for 177,476 of 338,856 documents. Those resolve
to **31 distinct provincial-level units** — all four municipalities, all five autonomous regions,
and 22 of 23 provinces. The only absences are Taiwan, Hong Kong and Macau. The smallest unit
(Tianjin, 475 documents) is nowhere near a token presence.

That is a much stronger statement than the coverage audit's "~14 of 34 crawled", and it is also a
much narrower one, because of *how* the other 17 arrive:

| province | total docs w/ province | excluding the `npc` tier | share from `npc` |
|---|---|---|---|
| gd | 119,422 | 117,483 | 1.6% |
| bj | 6,637 | 6,298 | 5.1% |
| sh | 4,711 | 4,177 | 11.3% |
| js | 12,147 | 10,478 | 13.7% |
| cq | 2,763 | 2,317 | 16.1% |
| fj | 3,636 | 2,712 | 25.4% |
| hlj | 2,659 | 1,818 | 31.6% |
| … | | | |
| sc | 1,128 | 117 | 89.6% |
| jx | 735 | 29 | 96.1% |
| ha | 1,141 | 28 | 97.5% |
| tj | 475 | 19 | 96.0% |
| hi | 641 | 12 | **98.1%** |

The distribution is bimodal, and the dividing line is whether we crawled the province. Seven
provinces sit under 32% `npc`; twenty-one sit above 75%. So:

- **A 31-jurisdiction comparative panel of local legislation exists right now**, balanced in size
  (339–1,939 per province) and spanning 1980–2026. Nobody in this project has used it.
- **It is metadata-only.** `crawlers/npc.py` stores `body_text_cn = ""` by design ("Body requires
  Chinese IP access"): body coverage is **0 of 31,070 rows**, in every province. The panel carries
  titles, dates, issuers and 文号 — and nothing else.
- So the corpus is really **two instruments**. One is a 31-jurisdiction title-and-date panel good
  for timing, ordering and agenda questions. The other is a ~7-province full-text apparatus good
  for fidelity and mechanism questions. **B1 in `corpus-lessons.md` — "a second deep province" —
  belongs entirely to the second instrument, and this panel does not discharge it.**

The panel is also **unbalanced in time**: not one province clears 20 regulations in every 5-year
window from 1996. Corpus-wide the series runs 781 (2000-04) → 1,152 → 2,417 → 5,835 → 9,537
(2020-24). A trend read naively off that series would be reading the next section's institutional
change as growth in legislative appetite.

---

## 2. The 2016 break is in the jurisdiction count, not the document count

Documents per year cannot distinguish "more legislators" from "the same legislators writing more".
Jurisdictions can. Both, by year, for the `npc` local-regulation tier:

| year | provincial regs | municipal regs | **distinct municipal issuers** | distinct provincial issuers |
|---|---|---|---|---|
| 2009 | 180 | 96 | 37 | 33 |
| 2010 | 465 | 269 | 50 | 36 |
| 2011 | 253 | 133 | 46 | 32 |
| 2012 | 384 | 166 | 45 | 31 |
| 2013 | 185 | 123 | 41 | 31 |
| 2014 | 301 | 136 | 43 | 35 |
| 2015 | 351 | 190 | 43 | 35 |
| **2016** | 478 | 326 | **214** | 43 |
| 2017 | 640 | 620 | 310 | 48 |
| 2018 | 919 | 731 | 304 | 45 |
| 2019 | 629 | 938 | 331 | 46 |
| 2020 | 948 | 931 | 325 | 44 |
| 2021 | 1,043 | 1,104 | 312 | 44 |
| 2022 | 910 | 875 | 313 | 51 |
| 2023 | 608 | 970 | 336 | 44 |
| 2024 | 813 | 1,285 | 432 | 58 |

Flat for seven years, then a five-fold jump in one year, and the provincial column barely moves.
The 立法法 amendment passed 2015-03-15; a city could only begin once its provincial 人大 had
designated it, which was staggered across 2015–2017 — exactly the shape of the 2016 jump and the
2017 settling.

Two measurement notes, both of which the break survives. (a) `lead_issuer` is a raw string, so
`苏州市人大` and `苏州市人民代表大会常务委员会` count twice; normalizing the 人大 suffixes gives
**79 jurisdictions pre-2016 and 362 after** (2024's raw 432 normalizes to 326). The inflation is
roughly 1.3×, constant across eras, and a factor of 4.6 does not come out of it. (b) The share
matters more than the count: municipal regulations were **~35% of local legislation for the fifteen
years 2000–2014**, then 48% (2015-19), 54% (2020-24), 60% (2025). Thin historical coverage would
suppress both levels together and leave that ratio flat.

### Why it is not a collection artifact

The rival explanation is that the database began *collecting* municipal regulations in 2016. The
pre-2016 issuer list refutes it, because it is not a subset of a large population — it is a legal
roster:

- **all 23 provincial capitals** (广州 武汉 杭州 南京 济南 长春 贵阳 郑州 银川 沈阳 西安 海口
  南宁 呼和浩特 拉萨 长沙 昆明 福州 南昌 石家庄 成都 哈尔滨 兰州);
- **all 18 较大的市**, the State Council's designated list (唐山 大同 包头 大连 鞍山 抚顺 吉林
  齐齐哈尔 青岛 无锡 淮南 洛阳 宁波 淄博 邯郸 本溪 徐州, plus 重庆 before it became a
  municipality);
- **the four SEZ cities** (深圳 汕头 厦门 珠海);
- **autonomous prefectures** (延边 黔东南 恩施 黔南 黔西南 昌吉 巴音郭楞 甘南 伊犁 红河 玉树
  海西 …), whose authority came separately under the 民族区域自治法.

A collection that happened to cover a fraction of China's cities would not reproduce the obscure
18-member 较大的市 list in full. And the normalized count lands on **79 = 49 + 30**, the authorized
cities plus the autonomous prefectures, which is the roster's own size. The corpus recovers the law
it never recorded.

---

## 3. The scope limit on new entrants is visible in the titles

The amendment did not hand new cities the incumbents' powers. It confined them to three subjects:
城乡建设与管理, 环境保护, and 历史文化保护. That is a prediction about content, testable on titles
alone — which is all this panel has.

Grouping the 362 post-2016 jurisdictions into **79 incumbents** (any pre-2016 activity) and
**283 newly authorized**, and scoring titles against the three domains:

| group | period | regs | in permitted domains (loose) | (strict) |
|---|---|---|---|---|
| incumbents | pre-2016 | 1,830 | 22.6% | 16.1% |
| incumbents | 2016+ | 4,438 | 28.8% | 22.9% |
| **newly authorized** | 2016+ | 5,650 | **44.7%** | **31.7%** |

The incumbent rows are the time trend: +6.2 pt loose, +6.8 pt strict, which is what the period's
general environmental and urban-management salience buys. The between-group gap in the same
period is the constraint: **+15.9 pt loose, +8.8 pt strict.** The loose proxy admits bare 保护 and
文化 (catching 消费者权益保护, 未成年人保护, which are *not* permitted domains), so it overstates
both groups; the strict proxy requires an unambiguous member (环境保护, 历史文化, 市容, 污染,
文物, 名城 …). The gap is robust in sign and roughly halves in size, so the honest estimate is a
**9 to 16 point** concentration.

It is a real constraint and a leaky one. Even on the loose proxy, **55% of newly-authorized cities'
regulations fall outside the three permitted domains.** Whether that is genuine scope creep, titles
that understate their own subject, or my keyword proxy missing permitted material, this panel
cannot say — the bodies are not in the corpus. It is the sharpest open question the memo leaves.

Uptake, meanwhile, is near-universal: **283 jurisdictions legislated** against roughly 250–270
newly eligible ones. (283 slightly exceeds the eligible population, which means the suffix
normalization leaves a few variants behind; the point is that essentially every city that gained
the power used it, not the third decimal.)

---

## 4. What this does to the volume's through-line

The volume's through-line has been: the center designates, localities echo, and the reverse flow is
nearly invisible (`bottom-up-channel.md`). This is not a counter-example to that — the echo
direction is unchanged — but it is a **counter-example to reading it as a one-way ratchet**. Here
the center used a national statute to *multiply* the number of bodies holding independent
rule-making authority, by a factor of about five, on a dated schedule, while simultaneously
bounding what the new holders could do with it. Both halves are measurable, and the second half
is measurable only because the first created a treated and an untreated group.

That is also the research design this panel supports best, and it needs no bodies: the 79
incumbents are a natural comparison group for the 283 entrants on any title-observable outcome —
legislative tempo, agenda composition, the order in which a subject spreads across jurisdictions,
and time-to-first-regulation on a new subject. `instrument-lifespan.md`'s revision machinery and
`instrument_succession` apply to the panel unchanged, since both read titles and dates.

---

## Limits

- **No bodies, anywhere in the panel.** 0 of 31,070 `npc` rows carry text. Everything above is
  titles, dates, issuers and 文号. Any claim about what a regulation *says* is out of reach here.
- **`admin_level_doc` is ~98% precise**, not exact (`corpus-lessons.md` A1). A 2% level error is
  far below the effects measured, but the 2024 municipal issuer count (432 raw / 326 normalized)
  is the figure most exposed to it.
- **`lead_issuer` is not a canonical registry** (A5 is still open). The jurisdiction counts are
  suffix-normalized, not registry-resolved, so treat 79 / 283 / 362 as ±5%, and the five-fold
  break as the robust quantity.
- **3,406 `npc` rows carry no province.** They are mostly national law, but the residual has not
  been audited, so no province's count should be treated as its complete legislative output.
- **The permitted-domain test is a keyword proxy on titles**, reported at two breadths precisely
  because neither is authoritative. It establishes a gap and its direction, not its true size.
- **The panel is unbalanced in time** (§1), so a pre-2000 comparison is not available at
  per-province resolution.

---

## Replication

```bash
# 31 provincial-level units, document-derived
sqlite3 "file:documents.db?mode=ro" "
  SELECT province, COUNT(*) FROM doc_identity
  WHERE province IS NOT NULL AND province!='' GROUP BY province ORDER BY 2 DESC;"

# the 2016 break: distinct municipal legislating bodies per year
sqlite3 "file:documents.db?mode=ro" "
  SELECT substr(d.date_published,1,4) AS yr,
         SUM(i.admin_level_doc='provincial'), SUM(i.admin_level_doc='municipal'),
         COUNT(DISTINCT CASE WHEN i.admin_level_doc='municipal' THEN i.lead_issuer END)
  FROM doc_identity i JOIN documents d ON d.id=i.doc_id
  WHERE d.site_key='npc' AND CAST(substr(d.date_published,1,4) AS INT) BETWEEN 2009 AND 2024
  GROUP BY yr ORDER BY yr;"
```

The incumbent/entrant split and the permitted-domain scoring are two temp views over the same
join; the exact SQL is in this memo's §3 table and reproduces in one `sqlite3` session.
