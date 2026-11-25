# Removals at deputy-national rank and above since the 18th Party Congress

*2026-11-25. Data: `data/purges/officials.json` (schema in `data/purges/README.md`). Every
corpus quote is re-verified by `scripts/rnd/purges/build_purges.py`, which exits non-zero on
a mismatch: 140 quotes across 67 documents, 0 failures on this build.*

Evidence labels used below:

- **[corpus]** a document id and a quote that is an exact substring of that document's title or body.
- **[web]** a URL found by web search, not held in the corpus. Not counted in any corpus-verified total.
- **[recalled]** general knowledge with no document behind it. Unverified.
- **[official aggregate]** a number stated by a Party, state or judicial body, quoted from a corpus document.
- **[own tally]** a count we computed over corpus rows.

## 1. The question and the answer

How many officials at deputy-national rank (副国级) or above have been removed since the
18th Party Congress (November 2012)?

**Fourteen, of whom thirteen are confirmed by at least one corpus document.** One further
case, 薄熙来, was removed and expelled in 2012 before the congress and tried after it; he is
listed separately in every count.

The fourteen are not one kind of event. By removal type:

| type | count | names | corpus-verified |
|---|---|---|---|
| (a) disciplinary or corruption case formally announced | 12 | 周永康, 徐才厚, 郭伯雄, 令计划, 苏荣, 孙政才, 李尚福, 魏凤和, 何卫东, 马兴瑞, 张又侠, 陈吉宁 | 12 of 12 |
| (b) removed from post, no reason stated | 1 | 秦刚 | 1 of 1 (the Central Committee resignation only) |
| (c) demotion | 1 | 杨晶 | 0 of 1 |
| (d) foreign or Hong Kong media only | 0 | none | n/a |
| **all types, since November 2012** | **14** | | **13 of 14** |
| flagged: removed before the congress | 1 | 薄熙来 (type a) | 1 of 1 |

Three qualifications belong with the headline.

1. **陈吉宁 is an investigation, not a finding.** Xinhua announced on 24 November 2026 that he
   is under review and investigation [corpus 900265582]. No removal, expulsion or charge is
   recorded. Without him type (a) is 11.
2. **Four of the twelve were retired when the case opened** (周永康, 徐才厚, 郭伯雄, 魏凤和).
   They count by the highest rank previously held. Eight of the twelve type (a) cases, and
   ten of the fourteen overall, were in office.
3. **Only one is 正国级**: 周永康, a former Politburo Standing Committee member. The other
   thirteen are 副国级.

By rank held at removal or highest previously held:

| rank | definition used | count | names |
|---|---|---|---|
| 正国级 | Politburo Standing Committee member | 1 | 周永康 |
| 副国级, Politburo member | incl. CMC vice-chairs who sat on the Politburo | 6 | 徐才厚, 郭伯雄, 孙政才, 何卫东, 马兴瑞, 张又侠; plus 陈吉宁 under investigation = 7 |
| 副国级, CPPCC vice-chair | | 2 | 令计划, 苏荣 |
| 副国级, State Councilor | | 4 | 杨晶, 秦刚, 李尚福, 魏凤和 |

## 2. The CMC-member tier, kept apart

Central Military Commission members who were not vice-chairs are a contested case: protocol
lists often place them with deputy-national leaders, and they are not on the Politburo. They
are recorded in their own tier and are **not** in the fourteen.

| name | post | removal type | corpus-verified |
|---|---|---|---|
| 房峰辉 | 中央军委委员、军委联合参谋部参谋长 (to 2017) | a | yes [corpus 12651498] |
| 张阳 | 中央军委委员、军委政治工作部主任; died November 2017 [recalled] | a | yes [corpus 12651498] |
| 苗华 | 中央军委委员、军委政治工作部主任 | a | **no**: web only |
| 刘振立 | 中央军委委员、军委联合参谋部参谋长 | a | yes [corpus 900148464, 900122164] |

Four people, three corpus-verified. 李尚福 and 魏凤和 were CMC members too, but each was also
a State Councilor, so they sit in the 副国级 set and are not double-counted here. A reader who
treats CMC membership as deputy-national would get 18 (14 + 4), of which 16 corpus-verified.

## 3. What the record of each case looks like

For the fifteen people (fourteen plus 薄熙来) the dataset holds 59 dated events. **28 of the
59 carry corpus evidence**; the rest are [web] or [recalled]. The split is by period, not by
person:

| person | first official action | outcome | events with corpus evidence |
|---|---|---|---|
| 薄熙来 (flagged) | 2012-03 [recalled] | expelled 2012-09 [web]; life 2013 [web]; conviction listed in the SPC work report [corpus 900002129] | 2 of 6 |
| 周永康 | 2014-07-29 [web] | expelled 2014-12 [web]; life 2015-06 [web]; listed by the SPP [corpus 900003374] | 2 of 5 |
| 徐才厚 | 2014-03-15 [web] | expelled 2014-06 [web]; died 2015 [recalled] | 2 of 5 |
| 苏荣 | 2014-06 [recalled] | expelled 2015-02 [recalled]; life 2017-01 [web] | 2 of 6 |
| 令计划 | 2014-12-22 [web] | CPPCC post removed 2015-02 [corpus 900139575]; expulsion confirmed 2015-10 [corpus 12760523]; life 2016-07 [web] | 2 of 5 |
| 郭伯雄 | 2015-07-30 [corpus 900031073, a relay] | life 2016-07 [web] | 2 of 3 |
| 孙政才 | 2017-07 [corpus 900181088, a relay] | handling decision 2017-09 [corpus 900181049]; life 2018-05 [web] | 3 of 5 |
| 杨晶 | 2018-02-24 [web, fetched] | one year of Party probation, demoted to full-ministerial rank | 0 of 1 |
| 秦刚 | 2023-07-25 [web] | removed as foreign minister, then as State Councilor [web]; Central Committee resignation accepted 2024-07 [corpus 12726515] | 1 of 3 |
| 魏凤和 | 2023-09-21 [web, fetched] | expelled 2024-06 [web]; death with reprieve 2026-05-07 [corpus 900026736] | 1 of 3 |
| 李尚福 | 2023-10-24 [web] | expelled 2024-06 [web], confirmed 2024-07 [corpus 12726515]; death with reprieve 2026-05-07 [corpus 900026736] | 2 of 4 |
| 何卫东 | 2025-10-17 [web, fetched] | expelled from Party and army; named a corrupt element by the CCDI secretary [corpus 900206970] | 1 of 4 |
| 张又侠 | 2026-01-24 [web] | removed by the NPC Standing Committee 2026-08-28 [corpus 900122164]; expelled 2026-09-21 [corpus 900148464]; confirmed 2026-10-29 [corpus 900206931] | 3 of 4 |
| 马兴瑞 | 2026-04-03 [corpus 12726009] | expelled, announced 2026-07-14 [corpus 900058549]; confirmed 2026-10-29; indicted 2026-11-05 [corpus 900208786] | 4 of 4 |
| 陈吉宁 | 2026-11-24 [corpus 900265582] | under investigation | 1 of 1 |

Read down the last column: the 2026 cases are documented step by step, and the 2012 to 2025
cases are documented mostly by later texts that name them. The single most useful later text
is the 2021 historical resolution, which names eight of the cases in two sentences
[corpus 12651498: "查处周永康、薄熙来、孙政才、令计划等严重违纪违法案件"; "坚决查处郭伯雄、徐才厚、房峰辉、张阳等严重违纪违法案件并彻底肃清其流毒影响"].
The most recent is the CCDI secretary's article of 5 November 2026, which adds three
[corpus 900206970: "坚决查处周永康、薄熙来、郭伯雄、徐才厚、孙政才、马兴瑞、张又侠、何卫东、令计划等腐败分子"].

**Stated grounds, in the official wording held in the corpus.** Two registers appear.
The earlier cases are named in political terms after the fact: "政治上的野心家、阴谋家" for
周永康 and 令计划 [corpus 900220715]. The 2026 releases enumerate breaches by discipline
category. For 马兴瑞: "严重违反政治纪律和政治规矩，履行全面从严治党主体责任不力" and "大搞家族腐败"
[corpus 900058549]. For 张又侠 and 刘振立: "严重违反政治纪律和政治规矩，搞团团伙伙，对党不忠诚不老实"
and "政治问题和经济问题交织，贪腐敛财与失职渎职并存" [corpus 900148464]. 秦刚 has no stated ground:
the plenum "接受秦刚同志辞职申请" and keeps the honorific [corpus 12726515].

**Sentences.** Life imprisonment: 薄熙来, 周永康, 令计划, 郭伯雄, 苏荣, 孙政才 (all [web]).
Death with two-year reprieve, then life without commutation or parole: 魏凤和 and 李尚福
[corpus 900026736]. No trial: 徐才厚 (died), 杨晶 and 秦刚 (not prosecuted), 何卫东 and 张又侠
(referred to the military procuratorate, nothing further in the corpus), 马兴瑞 (indicted, trial
pending), 陈吉宁.

## 4. The ranks below: counts only

No official figure in the corpus separates 正部级 from 副部级. The published units are
**中管干部** (centrally managed cadres: roughly vice-ministerial rank and above, plus some
posts below it) and **省部级及以上** (provincial-ministerial rank and above). The rows below
are official aggregates quoted from corpus documents. They use different measures and
different spans, so no two rows should be added or subtracted.

| rank span | measure | period | value | source |
|---|---|---|---|---|
| 中管干部 | case opened | Nov 2012 to Oct 2017 | 440 | [corpus 900220240] |
| of which 18th CC members and alternates / CCDI members | | same | 43 / 9 | [corpus 900235641] |
| 中管干部 | case opened | Oct 2017 to Oct 2022 | 261 | [corpus 900219708], CCDI report to the 20th Congress |
| 中管干部 | case opened | Nov 2012 to Oct 2022 | 553 | [corpus 900234930] |
| 中管干部 | case opened, by year | 2023 / 2024 / 2025 | 87 / 92 / 181 | [corpus 900198060] |
| 中管干部 | investigation publicly announced | 2024 / 2025 | 58 / 65 | [corpus 12708830, 900239721] |
| 中管干部 | case opened, cumulative | Nov 2012 to end 2025 | more than 900 | [corpus 900218138] |
| 中管干部 | disciplined, cumulative | Nov 2012 to Sept 2026 | 963 | [corpus 900206970, 900204091] |
| 省部级及以上 | case opened | Dec 2012 to May 2021 | 392 | [corpus 900235653] |
| 省部级及以上 | disciplined | 2022 | 53 | [corpus 900233963] |
| 省部级及以上 | case opened / disciplined | Jan to Sept 2026 | 73 / 105 | [corpus 900200662] |
| 省部级以上 | criminal cases handled by procuratorates | 2014 | 28 | [corpus 900003374], SPP work report |
| 厅局级 | case opened | Dec 2012 to May 2021 | 22,000 | [corpus 900235653] |
| 厅局级 | disciplined | Nov 2012 to Oct 2022 | more than 25,000 | [corpus 900234930] |
| 厅局级 | case opened | 2025; Jan to Sept 2026 | 5,016; 4,203 | [corpus 900239721, 900200662] |
| 县处级 | case opened | Dec 2012 to May 2021 | more than 170,000 | [corpus 900235653] |
| 县处级 | case opened | 2025; Jan to Sept 2026 | 41,000; 34,000 | [corpus 900239721, 900200662] |
| 乡科级 | case opened | Dec 2012 to May 2021 | 616,000 | [corpus 900235653] |
| all ranks | cases opened / persons disciplined | Nov 2012 to Sept 2026 | 8.105 million / 7.922 million | [corpus 900204091] |

Three things to read off this table.

- **The fourteen are about 1.5% of the top band.** Against 963 centrally managed cadres
  disciplined by September 2026, fourteen removals at 副国级 or above are 1.5% (14 of 963),
  and the two populations are not strictly nested (杨晶 and 秦刚 may or may not be inside the
  963; the corpus does not say).
- **2025 is the peak year on the official series**: 181 cases opened against 87 and 92 in the
  two years before [official aggregate], and the nine-month figure for 2026 at
  省部级及以上 (73 opened, 105 disciplined) is on a different unit and cannot be compared directly.
- **"Cases opened" and "publicly announced" differ by a factor of nearly three in 2025**
  (181 against 65). Any tally built from announcements, ours included, measures the
  smaller quantity.
- One inconsistency is left standing: a Qiushi article gives 414 中管干部 cases to the end of
  2019 [corpus 900220715], below the 440 reported for 2012 to 2017. The corpus does not
  reconcile them. Both are in the data file; neither is used above.

**A proxy for 正部级: Central Committee full members expelled** [own tally from plenum
communiques; full or alternate status resolved by exact name match against the two 20th CC
name lists, corpus 900207119 and 900207120].

| plenum | date | expelled | full members | alternates | evidence |
|---|---|---|---|---|---|
| 18th CC, 4th | 2014-10 | 6 | not resolvable | not resolvable | [web] |
| 18th CC, 5th | 2015-10 | 10 | not resolvable | not resolvable | [corpus 12760523] |
| 18th CC, 6th | 2016-10 | 4 | not resolvable | not resolvable | [web], non-official mirror |
| 18th CC, 7th | 2017-10 | list not retrieved | | | not in corpus |
| 19th CC, all | | not retrieved | | | not in corpus |
| 20th CC, 3rd | 2024-07 | 3 (李尚福, 李玉超, 孙金明) | 2 | 1 | [corpus 12726515] |
| 20th CC, 4th | 2025-10 | 14 | 10 | 4 | [web, fetched]; names matched against corpus lists |
| 20th CC, 5th | 2026-10 | 33, plus 李云泽 removed from Party posts | 24 | 9 | [corpus 900206931] |

For the 20th Central Committee: **26 of 205 full members (205 is the size of the body [recalled]) expelled on corpus evidence
(12.7%), 36 of 205 (17.6%) when the web-sourced Fourth Plenum is included**, plus 秦刚's
accepted resignation. Alternates: 10 corpus-verified, 14 including the web. The Fifth Plenum
alone confirmed 33 expulsions, more than the 18th CC's 4th, 5th and 6th plenums together (20).
Central Committee membership is a proxy: most full members hold 正部级 or the military
equivalent, some hold higher rank, and many 正部级 officials are not members. The 18th CC
rows cannot be split because the corpus holds no 18th CC name list.

**Our own tally of announcements held** [own tally, `tally_announcements.py`]: 12 distinct
subjects of the standard CCDI headline "…接受中央纪委国家监委…审查调查", all dated 2026, none
earlier. The official figure for the first nine months of 2026 is 73 cases opened at
省部级及以上. The tally describes the crawl. It is reported only to show the size of the gap.

## 5. Successors, and what changed afterwards

Successors are recorded per vacated post in the data file. Four of the fifteen vacated no
post (retired). Of the rest:

| removed | post | successor | date | evidence |
|---|---|---|---|---|
| 薄熙来 | 重庆市委书记 | 张德江 | 2012-03 | [recalled] |
| 令计划 | 中央统战部部长 | 孙春兰 | 2014-12 [recalled] | in post in 2015 [corpus 900139575] |
| 孙政才 | 重庆市委书记 | 陈敏尔 | 2017-07 | [recalled] |
| 杨晶 | 国务委员兼国务院秘书长 | 肖捷 | 2018-03 [recalled] | in post 2018-07 [corpus 900040861] |
| 秦刚 | 外交部部长 | 王毅 | 2023-07-25 | [web] |
| 李尚福 | 国防部部长 | 董军 | 2023-12 | [recalled] |
| 何卫东 | 中央军委副主席 | 张升民 | 2025-10-23 | [web, fetched]; in post [corpus 900214415] |
| 张又侠 | Politburo seat | 张升民 | 2026-10-29 | [corpus 900206931: "全会增选张升民为中央政治局委员"] |
| 马兴瑞 | 中央农村工作领导小组副组长 | none named | | 0 corpus documents after April 2026 name another deputy head |
| 陈吉宁 | 上海市委书记 | none named | | one day after the announcement |

Seats left unfilled as far as the corpus shows: the State Councilor seats of 秦刚 and 李尚福,
李尚福's CMC seat, and a second CMC vice-chair after 张又侠.

**Timing against institutional change.** We listed eight institutional changes between 2014
and 2024 (the 2014 law-based governance decision, the 2015 military reform launch, the 2016
theatre commands, the 2016 supervision-commission pilot, the 2018 and 2023 Party and state
reform plans, the 2019 political-legal work regulations, the 2024 Information Support Force)
and asked one question: does at least one fall in the 24 months after a person's first
official action?

- Of the 11 people whose 24-month window has closed, **10 have at least one listed change in
  the window (91%)**. The exception is 薄熙来.
- **The base rate is 77%**: of the 145 months from November 2012 to November 2024, 111 are
  followed by at least one listed change within 24 months.
- With a base rate of 0.766, ten or more hits in eleven independent draws has a probability
  of about 0.23. The draws are not independent either: five of the eleven first actions fall
  between March 2014 and July 2015 and share the same windows.

So the pattern "a fall is followed by a reorganisation" is **not distinguishable from the
background frequency of reorganisation** on this list. A stricter reading, counting only a
change in the system the person belonged to, gives 5 of 11 (徐才厚 and 郭伯雄 with the
military reform, 周永康 with the 2014 legal-system decision, 李尚福 and 魏凤和 with the 2024
force restructuring), and we have no same-system base rate to set against it. The list of
eight is hand-selected, which is the hand-maintained-table problem this project has met
before: both figures describe the list. No causal claim is made or supported.

## 6. Co-presence ties with named people

The user named 刘国中, 马兴瑞, 李希, 何立峰, 蔡奇, 黄坤明, 朱忠明, 李政, 陈杰, and three
romanised names (Hu Qing, Rong Li, Wei Xiaodong). A tie below means two people held posts in
the same body at the same time, or appear in the same official list. It is a co-presence
fact. It says nothing about personal relationship, patronage or alignment.

| removed | named person | body and period | kind | evidence |
|---|---|---|---|---|
| 马兴瑞 | 李希 | 广东省, governor and Party secretary, 2017 to 2021 [recalled dates] | same leadership team | [corpus 164698]; 58 documents name both |
| 陈吉宁 | 蔡奇 | 北京市, mayor and Party secretary, 2017 to 2022 [recalled dates] | same leadership team | [corpus 900110206]; 63 documents name both |
| 陈吉宁 | 朱忠明 | 上海市, Party secretary and acting mayor, 2026 | same leadership team | [corpus 900136712]; 19 documents |
| 陈吉宁 | 陈杰 | 上海市, Party secretary and vice mayor, 2025 | same municipal government | [corpus 12695617]; 7 documents |
| 陈吉宁 | 李政 | unknown | co-mentioned in 8 documents, never in one sentence | identity unresolved |
| 张又侠 | 李希, 蔡奇, 黄坤明 | 19th Politburo, 2017 to 2022 | same central body | officials.db overlaps; [corpus 900094526] |
| 马兴瑞, 何卫东, 张又侠, 陈吉宁 | 刘国中, 何立峰, 黄坤明 | 20th Politburo; listed together on the NPC rostrum, March 2023 | same central body, shown by a seating list | [corpus 539350] |
| 马兴瑞, 何卫东, 张又侠, 陈吉宁 | 李希, 蔡奇 | 20th Politburo (the two named are on its Standing Committee) | same central body | [recalled]; no corpus sentence lists the body |
| 秦刚, 李尚福 | 刘国中, 何立峰 | State Council formed March 2023 | same body, shown by a seating list | [corpus 540795] |
| 魏凤和 | 何立峰 | State Council planning meeting, May 2020 | same meeting | [corpus 7577202] |
| 周永康, 薄熙来, 徐才厚, 郭伯雄, 令计划, 苏荣, 孙政才, 杨晶 | any of the named | | none found | 0 or 1 documents per pair |

Reading notes:

- **Unresolved:** Hu Qing, Rong Li and Wei Xiaodong match no row in officials.db and came
  without characters, so they were not searched. 朱忠明 and 李政 are not in officials.db;
  朱忠明 is identified by the corpus, 李政 is not. officials.db has a 陈杰 (20th CC) whose
  identity with the Shanghai vice mayor is not confirmed.
- **officials.db is thin here.** Its overlaps table returned one set of rows for 15 x 9 pairs
  (张又侠 with three Politburo colleagues, and truncated to 2017 to 2018). 徐才厚, 郭伯雄 and
  何立峰 have no career records at all. The parser is being repaired in another job; ties are
  certainly missing, and "none found" for the eight older cases is not a finding of no tie.
- **A list of cases is not a tie.** Nine of the removed share a sentence with 马兴瑞 in the
  CCDI secretary's list of corrupt elements. That is excluded.
- Most of the 2022 to 2026 ties are membership of the same top body, which every member
  shares with every other. The two that go beyond it are the provincial pairings: 马兴瑞 with
  李希 in Guangdong and 陈吉宁 with 蔡奇 in Beijing.

## 7. Cross-check against officials.db

All 19 people (15 plus the 4 CMC-tier) are present in `officials`. None is missing. The flags
are consistent with the ranks used here: `is_psc=1` only for 周永康; `is_politburo=1` for
周永康, 薄熙来, 徐才厚, 郭伯雄, 孙政才, 何卫东, 张又侠, 马兴瑞, 陈吉宁; 0 for the CPPCC vice-chairs,
State Councilors and CMC members, as expected. All 47 names in the 18th-5th, 20th-3rd and
20th-5th plenum lists are present too. What is missing is content, not rows: 0 career records
for 徐才厚 and 郭伯雄, 1 for 秦刚, 3 for 杨晶. officials.db does not distinguish full from
alternate Central Committee members.

## 8. What the corpus cannot show

- **The CCDI's own record.** No ccdi.gov.cn document is in the corpus: 0 URLs, no site key.
  This is the main gap. Every CCDI release held is a reprint, and before 2026 almost none
  were caught.
- **The contemporaneous record of 2012 to 2025.** For the eleven people removed in those years
  plus 薄熙来, 30 of 50 events (60%) have no corpus document. The first-action dates, the
  expulsion texts with their enumerated grounds, and all six life sentences rest on [web] or
  [recalled]. 26 URLs are listed in `web_urls_to_ingest`; 5 were opened and read, 21 come
  from search summaries and should be checked when ingested.
- **杨晶 and 苗华 entirely, and 苏荣's announcements.** No corpus document covers the first
  two cases. For 苏荣 the search found only non-official relays, so the 2014 and 2015 dates
  carry no URL.
- **Plenum communiques.** 18th CC 4th, 6th and 7th and all 19th CC expulsion paragraphs are
  absent; the 20th CC 4th is held only as rows with empty bodies. The Central Committee count
  for the 18th and 19th terms therefore cannot be made from the corpus.
- **Rank below 副国级 for individuals.** Official aggregates do not split 正部级 from 副部级,
  and we did not classify individuals. The Central Committee proxy is the nearest substitute.
- **Type (d).** The corpus holds no foreign or Hong Kong reporting on unconfirmed cases, so an
  empty cell means "none recorded", not "none exist". The same applies to senior figures who
  have simply stopped appearing: absence from the corpus is not evidence of anything.
- **Anything about why.** The official texts give stated grounds. They are quoted as stated.
  Whether a case is about corruption, politics or both is not something this record settles,
  and the 2026 releases themselves describe "政治问题和经济问题交织".
- **Whether sentences were appealed, and what happened to the military referrals** of 何卫东,
  张又侠 and 刘振立.

## 9. Method notes

- Candidate names came from a prior list treated as hypotheses, then a systematic pass:
  every sentence in the 4,970 documents containing a disciplinary term (开除党籍, 严重违纪,
  立案审查, 审查调查, and nine others) that also contains a rank phrase (中央政治局委员,
  国务委员, 全国政协副主席, 全国人大常委会副委员长, 中央军委副主席, 国务院副总理 and their 原
  forms). That pass surfaced 陈吉宁 and no other new name. It cannot surface a case the corpus
  holds no announcement of.
- Two-character names (秦刚, 苏荣, 杨晶, 苗华, 张阳, 李希, 蔡奇) went through the segmented
  index and title LIKE, per `scripts/rnd/analysis/fts.py`; namesakes were removed by hand.
- Quotes are exact substrings with no normalisation. A quote that needs whitespace folding to
  match is rejected by the verifier and by `tests/test_purges_verifier.py`.
- Web search results were summarised by the search tool; `fetched: false` in the data marks
  the 21 URLs whose text we did not open.
