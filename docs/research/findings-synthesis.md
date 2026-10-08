# The corpus as an instrument: a synthesis of the replications, and the volume's spine

*Synthesis memo, 2026-10-01. Ties the first wave of replications and the live tracker into one
argument and a chapter structure. Each section links the memo that carries the full result and
the NBER / political-science paper it replicates or extends. Read `related-literature.md` for
the paper list and corpus-fit ratings; this is the "what we found and how it fits" layer above
the individual studies.*

---

## The through-line

One finding recurs across every diffusion and central-local study, independently derived each
time: **the published documentary record shows the center designating and localities echoing,
and shows very little of the reverse flow.** Downward designation and upward authority-borrowing
are dense and measurable; genuine bottom-up generalization (a local innovation the center later
absorbs) is nearly invisible.

This is partly a real institutional feature and partly the corpus's defining limit. The upward
and internal channels that the experimentation literature relies on (internal reporting, cadre
evaluation, 内部 circulars, personnel moves) are not in a corpus of *published* documents. So the
honest central claim of the volume is scoped precisely: **the corpus measures the published face
of the bureaucracy, command and echo, with high fidelity, and is appropriately silent on the
internal upward channels.** Every memo states this boundary rather than papering over it. Stated
this way it is a strength, not a hedge, it is a clear account of what this instrument can and
cannot see.

*(Update 2026-10-06, `bottom-up-channel.md`: we then hunted the upward channel deliberately.
The center's acknowledgment lexicon (典型经验 / 复制推广 / 向全国推广) rose from 2-3% of central
promulgations in 2008-13 to a 17-19% peak in 2021-22, but 92% of it is exhortation *(precisely:
92% of lexicon docs name no locality near the phrase; the explicitly forward-looking "exhort"
share is about half of hits, `bottom-up-channel.md` §2; wording tightened 2026-10-07,
`consistency-review.md` round 2)*; only 296 docs
(0.8%) name a locality near the phrase and only 79 carry recognition in the title. Lexicon docs
cite downward no more than other central docs (0.31% vs 0.24%). The center absorbs a local model
by restating it in prose and naming the place, never by citing the local document, so the
citation graph is structurally blind to upward flow. Who gets named tracks pilot selection:
Spearman with GDP per capita 0.664, richest ten provinces take 62.5%. The through-line therefore
hardens for the citation record and softens for the prose record. Four feedback sources (全国人大
议案建议, 全国政协 提案, 江苏人大, 北京人大; 1,427 docs) are now in the corpus under
`group="feedback"` as the place a document-level upward link could still appear.)*

The second recurring result is methodological. Two 2025 NBER papers (Luo/Wang/Yang; Fang/Li/Lu)
chose the same object (millions of Chinese policy documents) and inferred relationships from text
similarity. Our edge is an **explicit, resolved citation-and-reissuance graph** plus
department-level issuers and nightly recency. The auto-matcher (`diffusion_events`; 32,825
events as of the 2026-10-01 builds, 26,565 central-anchored plus 6,260 provincial) turns the
hand-built cascade tables of the case studies into a corpus-wide, self-updating measurement.
The table is rebuilt nightly, so the count grows. *(Final 2026-10-01 build, after the
resolver regression fix and the containment gate: 33,992 events, of which 23,640 are
implementing instruments and 10,352 are mention-only references, now separated by a
`source_implementing` flag because a locality's news repost is a reference, not an
implementation; the tracker and both leaderboards default to implementing-only. Resolved
citations 269,685, down from 287,607, because containment proxies to news and 解答 pages are
now left unresolved rather than credited to a wrong target.)* *(Build trail since, 2026-10-07:
35,465 / 35,475 on the 2026-10-06 nightly, 35,498 after the province resolver `b7162c8`, **36,116**
after the Suzhou redate `5465b8e`, the figure `policy-tempo.md` and the live table carry;
`industrial-policy-targeting.md` R6 quotes 35,475 from the earlier build of the same day.)* The memos quote three earlier builds (28,880;
24,599; 26,565 central) and a further resolver regression fix in progress will move it again;
see `consistency-review.md` H2 for which build each memo used. That is the volume's
methodological contribution.

---

## The chapter structure

### Part I. How the document system is structured
- **Authority and genre** (`citation-network-structure.md`, Q3+Q8; the IT-policy-citation-
  network method on 248k edges vs their 3,150). Authority is heavy-tailed: the top 1% of nodes
  hold 54.5% of resolved inbound citations (Gini 0.947; 84% of documents are never cited); of
  the top 100, 80 are central and 75 are regulations or laws. The genre source/sink split holds
  and survives age control: regulations receive 7.3 / emit 1.6, explainers 0.1 / 2.0; 62.5% of
  edges target a framework genre, 13.7% originate from one. Cross-level flow: up 46%, same-level
  49%, down 4%; districts face their city and the center, not their province. The bridges that
  tie all 29 topics together are procedural law and planning outlines (政府信息公开条例 is cited
  from every topic), not sectoral law. It also found the resolver's proxy-target bug (27% of
  edges credited to a document that merely embeds a cited law's name). The exact-title class
  of that bug was fixed (commits `cd42903`/`c979a82`): a length gate had skipped the
  exact-match tier for short law names, so containment won; exact title/core matches now take
  priority. Resolved edges rose 279,409 → 287,607 with no loss; the law 城乡规划法 recovered its
  2,141 citations from the Henan implementing measure; the top-30 by `citation_rank` is now
  framework laws. The fix is partial, not root. Containment proxies to instruments that have no
  exact-title copy in the corpus (the memo's ~50k virtual-node edges, e.g. 机动车驾驶证申领和使用
  规定 still resolving 686 edges to a provincial 解答 page) persist in `citations` and
  `citation_rank`, so proxy mass remains below the top-30. The fix also introduced one
  regression: 提振消费专项行动方案 now resolves to a Beijing news page, and that is being
  corrected (`consistency-review.md` H1). `citation_rank` figures quoted in memos written before
  this fix are pre-fix and shifted at the top. *(Wording corrected 2026-10-01 per
  `consistency-review.md` H1; the earlier text said "FIXED at the root".)*

### Part II. How policy moves
- **The diffusion atlas** (`diffusion-atlas.md`; Luo/Wang/Yang "Laboratories of Autocracy",
  NBER w34219, and the diffusion-intensity index). Province-before-city holds corpus-wide
  (68-76% vs a 50% null, robust to cuts, resting mostly on Guangdong's district depth). Breadth
  belongs to State Council 条例 (slow, 695-day median), speed to campaign instruments; only the
  2024 fiscal campaigns were both. On a fixed 22-site panel diffusion has not accelerated since
  2008, what changed is central output (up ~75%) and the shrinking share of it that gets a fast
  local echo (50% to ~20%, partly right-censored).
- **Fidelity: relay vs elaboration** (`diffusion-fidelity.md`, corpus-wide, 13,509 pairs;
  `ai-plus-fidelity.md` for AI+, Q6). Localities overwhelmingly AUTHOR rather than relay: 88.3%
  elaboration, 9.8% mid, 1.9% relay, a decaying tail, not bimodal (the AI+ memo's empty middle
  was an n=12 artifact, now annotated). The 1.9% relay cluster is provincial 转发 forwarding
  notices within 90 days; lag is the strongest predictor. Money raises text reuse ~2x but never
  produces relay (all 以旧换新 re-issuances are templated elaboration), and the rule-bound clause
  of the earlier thesis is wrong: 条例/办法 are the LEAST copied genre, 意见 is what gets
  paraphrased into a 实施意见. Districts elaborate most; provinces are the forwarding and
  first-paraphrase tier.
- **The province as translation layer** (`fidelity-provincial.md`, 6,622 province→city pairs,
  2,444 full center→province→city chains, 95% Guangdong). This reframes the chapter. Cities copy
  their PROVINCE far more than provinces copy the center (relay 10.8% vs 3.3%; median overlap
  0.115 vs 0.074), and it is not forwarding: 75% of relays are city instruments under their own
  title and 文号 reproducing the provincial body (median lag 181 days). In 92.8% of full chains
  the city's text descends from the province, not the center; only 0.8% of a city document's
  text is center-only. Central language reaches cities through the provincial rewrite, and
  verbatim text survives both hops in under 1% of chains. The copying tier is the prefecture
  city alone: districts (0.2% relay) and Shenzhen bureaus do not copy the province. Provincial
  方案 are copied by half their implementers, 办法/条例 by 1%. The 以旧换新 "tight cascade" was a
  province→city phenomenon (Guangdong cities at 0.50-0.77 vs the Guangdong 方案, 0.06-0.25 vs
  the central text). The tracker was upgraded accordingly (commit `c6dbe04`): the auto-matcher
  now admits provincial anchors (6,260 events across 1,126 provincial instruments, `anchor_level`
  column, central events byte-identical), so `/tracker` shows the province→city hop, e.g. the
  以旧换新 Guangdong 实施方案 reaching 26 cities at a 38-day median lag, with a provincial
  most-cascaded leaderboard (top: Guangdong's procedural rules, 行政规范性文件管理规定 at 20
  localities).
- **The live tracker** (`daily-tracker-concept.md`; shipped at `/tracker`). The retrospective
  diffusion method turned into a nightly instrument: per implementation area, this week's new
  documents by level and the active cascades, sub-second because it reads two precomputed tables.
  *(2026-10-07, `policy-tempo.md`: the weekly series now holds 458 weeks and is an instrument
  for burstiness and level timing (provinces move first for 67% of instruments; 以旧换新 lifts
  Commerce cascades 3.4x, AI+ lifts Tech 1.9x) but not yet for cross-area tempo or lead-lag, since
  cascade yield per central instrument is 9% visible at 12 weeks and 41% at a year, the pooled
  bursts are single-portal batches, and only 1 of 90 topic pairs beats a permutation null.)*

*(Update 2026-10-07, `fidelity-jiangsu.md`: the three nested findings above were replicated on
Jiangsu after its deepening (13 provincial departments, 9 Nanjing and Suzhou districts), with
Guangdong recomputed on the same `doc_identity` layer. All three hold in direction and level.
Province-before-city 82.1% of 39 nested pairs (Guangdong 65.1% of 704 on this layer; 78.5% when
Guangdong is cut to five cities, because the share rises as fewer cities are watched). City
fidelity to the province: median 0.125, relay 8.4%, mid 26.2% (Guangdong 0.109 / 10.8% / 21.3%),
same lag slope (rho −0.51 vs −0.49), same genre ordering, 14 of 16 relays are 市政府办公室
re-issuances of the 省政府办公厅 text under Suzhou's name at a 160-day median. Chains: the city is
closer to the province in 89.9% of 89 (city tier 94.0%; Guangdong 92.1% / 92.8%), center-only text
1.4% at the median. Every Jiangsu number sits inside the range of 40 Jiangsu-sized Guangdong
subsamples, so the differences are coverage: Jiangsu's sub-provincial tier is 1/15 of Guangdong's
in documents, 1/29 in pairs, and is one city (Suzhou is 92% of its pairs). The renaming layer
(`localized_of`) corroborates from titles alone: 80 to 82% of renamed sub-provincial re-issuances
in both provinces are renamed from a provincial text, at mid-to-relay overlap, and the citation
graph sees fewer than half of them *(2026-10-07 re-base, `pair-channels.md` §3: the "fewer than
half" counts metadata-only sources that cannot cite; conditioned on a source body the citation
path sees three in four, invisible 25.5% Guangdong / 23.1% Jiangsu, so the floor is body
coverage, about 5% of relays, +0.2 relay points)*, so the provincial memo's relay counts are floors. Verdict:
hardens, on one city; B1 is discharged only when a second Jiangsu prefecture is crawled to
Suzhou's depth. Corpus finding on the way: Suzhou's `date_published` is crawl-stamped in two
batches (2023-02-09, 2025-02-11) that the A4 rule does not catch; the memo re-dates from the URL
path and flags the 171 affected `diffusion_events` lags.)* *(Superseded 2026-10-07, commits
`5465b8e`/`247c5f7`: the two piles were the source CMS's page-regeneration stamps, not our crawl
day; the DB was redated from the article header / 发文日期 / URL month (3,354 rows, median shift
−1,886 d; live 2026-10-07: 1 and 7 Suzhou docs remain on those two dates, 685 sit on a
month-precision day 01), the A4 rule now sums bulk date-days, and the `/YYYYMM/` folder is a 2021
migration artefact for ~250 historical 规范性文件, so the memo's URL-path repair mis-dates that
subset. On the redated DB the Jiangsu province-to-city CITATION basis is 473 pairs / 426 scored
with relay 3.3%, not the 191-200 / 8.0-8.4% quoted above; the 14 relays are the same on both
bases, so the share moved because the repair pulled hundreds of long-lag Suzhou pairs into range
(`fidelity-provincial.md` §2.2, logged not resolved; re-read queued). Suzhou-sourced events are
1,406 on the live table, up from 788.)*

*(Update 2026-10-08, `fidelity-wuxi.md`: **B1 is discharged** on Wuxi, the second non-Suzhou
Jiangsu prefecture (4,877 documents, 397 province-to-city pairs, 195 nested pairs, 152 chains,
larger than Suzhou's sample on two of the three measures) which replicates all three nested
findings separately from Suzhou (province-before-city 83.6% of 195 against Suzhou 69.4% of 144
and Guangdong cities 68.2% of 1,046; city closer to the province 94.1% of 152 against 96.9% and
91.6%; median overlap 0.115 / relay 5.3% / mid 18.5% against 0.054 / 4.3% / 12.4% and 0.097 /
9.9% / 19.7%) while correcting the one number that looked provincial, since per CITY the
Guangdong relay rate itself runs 2.2% (广州) to 18.4% (阳江) with a median of 8.9% and both
Jiangsu cities fall inside that spread near 广州 and 深圳, so relay tracks prefecture capacity
[inferred] and not province, whereas province-before-city (per-city 61.7 to 90.0, median 83.6,
Wuxi exactly on it) and chain descent (79.3 to 98.0, median 93.5) are stable across it.)*

### Part III. Central-local dynamics
- **Devolution is measurable, and the ratchet runs both ways**
  (`local-legislative-devolution.md`, 2026-10-08). Counting *jurisdictions* rather than documents
  — the question `doc_identity.province` + `admin_level_doc` made askable — distinct **municipal**
  legislating bodies were flat at ~43/yr across 2009-15, jumped to **214 in 2016**, and settled
  near 320, while provincial issuers barely moved. The cause is the 2015 立法法 amendment
  (effective 2015-03-15), which extended local legislative power from 49 designated cities to all
  设区的市. Not a collection artifact: the pre-2016 issuer set is the legal roster itself — all 23
  provincial capitals, all 18 of the 较大的市 list, the 4 SEZ cities, the autonomous prefectures —
  and suffix-normalized it lands on **79 = 49 + 30**, the roster's own size. The municipal *share*
  also breaks (≈35% flat 2000-14, then 48 / 54 / 60%), which thin historical coverage cannot
  produce. The amendment's three-domain confinement (城乡建设与管理 / 环境保护 / 历史文化保护) then
  shows in the titles: 283 new entrants legislate inside those domains **9-16 pt** more than the
  79 incumbents in the same period, against an incumbent time-trend of ≈+6.5 pt. **This does not
  contradict the through-line — the echo direction is unchanged — but it refutes reading it as a
  one-way ratchet.** The center multiplied the number of bodies holding independent rule-making
  authority about fivefold on a dated schedule while bounding what they could do with it. Breadth
  footnote from the same memo: all 31 mainland provincial-level units appear in the corpus, but for
  21 of them ≥75% of what we hold is this one metadata-only genre, so the panel is a second
  instrument (titles and dates, 0 of 31,070 rows with a body) and does **not** discharge B1.
- **Recentralization and experimentation** (`recentralization-experimentation.md`;
  Luo/Wang/Yang recentralization claim and Wang/Yang pilots, NBER w29402). The upward-citation
  share of sub-national edges steps up 7-11 points at exactly 2013, holds through 2017, then
  reverts to 2008-12 levels by 2023-26; horizontal and downward shares are flat throughout. So a
  2013-17 rise in authority-borrowing, not a durable collapse of peer learning. The atlas sees
  the same window from the breadth side: 2014-19 is its high point of local echo (atlas §5), and
  the recentralization memo's 2013-17 upward plateau is the same signal read through direction.
  Base note: the 0.58 to 0.66 upward share here is on sub-national-source edges only (185,447
  dedup); Part I's "up 46%" is on all 163,814 corrected edges including central-to-central
  (`consistency-review.md` M8).
- **Policy experimentation** (`experimentation-wang-yang.md`; Wang/Yang w29402, full replication
  of the document backbone). 1,592 central pilot-guideline documents (vs their 633 hand-merged
  experiments), linked to local implementation and traced for rollout. Designation flows down
  (pilots cited by 833 sub-national docs; a pre-resolver-fix raw-citation count) but
  generalization barely flows up (0.4-1.2% reach a visible national instrument, a visibility
  floor). Their causal findings (fiscal effort, learning bias) need external data we do not
  hold, stated as out of reach. *(Update 2026-10-06: the site-selection finding is now
  replicated descriptively at province grain, `site-selection-gdp.md`, via a provincial GDP
  join (31 units × 23 years from NBS yearbooks; 2014-19 interpolated and flagged). 77.6% of
  the 737 selective pilot guidelines name a majority-above-median pilot set (random draw 41%);
  named provinces sit at the 0.705 GDP-per-capita percentile (random 0.50), robust across five
  cuts; Spearman(selection ratio, GDP/capita) 0.625; the richest tercile takes 55% of
  designations on 38% of population. 批复 (locality-requested) designations select less than
  assigned ones (0.60 vs 0.73 percentile), an automatic proxy for their assigned-vs-voluntary
  split. Province grain biases toward the null; the promotion-incentive mechanism remains
  untestable.)* *(Update 2026-10-06, `successor-detector.md`: the pilots-that-scale anomaly
  is mostly measurement. A scored successor detector (core similarity + topic + generalization
  cue + issuer + citation, 76-87% precision) lifts the rate from ~1% to 5.9% raw / 6.9%
  ex-mid-flight (8-9.5% on 试点 trials only), median lag 564 days, inside W&Y's 820-day mean.
  Hand-classifying the pilots with no successor: 40% are zone designations that "scale" as
  more zones, 23% scaled under a RENAMED or absorbing instrument (海南自贸试验区 → 自贸港方案,
  刑事速裁试点 → the 2018 刑诉法 amendment), 20% are mid-flight, 7% never scaled. Of 12 mature
  substantive pilots, 9 have an in-corpus successor the core match cannot reach, bracketing
  their 53.9%. The finding is not that pilots fail to scale; it is that they scale under new
  names, which no title-based method sees without a renaming layer.)*
- **Inter-agency coordination** (`joint-issuance.md`, Q7; fragmented-authority tradition).
  Built on a new 文号/issuer parser (`doc_issuers`, 79% coverage, 97% precision) that finds
  13,004 jointly-issued documents (13,370 before the 粤办 fix below), 13x the agenda's naive
  proxy of 1,047. Joint issuance is RISING at the center. The canonical sentence: on the
  robustness central set (gov/ndrc/mof/mee, policy genres), the share of central policy
  documents with two or more signatories went 17% (2005-09), 16% (2010-14), 24% (2015-19), 31%
  (2020-23), 43% (2024-26); pooled 2020-26 it is 34% (live 2026-10-01: 17.0 / 15.9 / 23.5 /
  31.2 / 43.2; pooled 34.4). The rise is present inside gov.cn, NDRC, MOFCOM and CAC
  individually and inside 意见/行动方案, while routine 通知 is flat; sub-national joint
  issuance is rare and flat. Coalitions are growing (mean 2.4 to 3.9 signers; 5+ signers from 5%
  to 30% of joint docs; 288 distinct 10+ mega-coalitions). The co-signing core shifted from an
  MOF + 税务总局 fiscal dyad (59% of joint docs 2005-12) to an NDRC hub (NDRC+MOF, NDRC+MIIT,
  NDRC+SAMR). Joint docs are echoed more often and sooner only at scale: 2-3 signers add nothing
  (confirming the atlas), ministry-led 5+ coalitions are echoed 2.5-3.7x as often and sooner
  (13-19% vs 5%), and the gain is on whether any sub-national unit responds more than on how
  many do (joint §5c). So coordination is centralizing into larger, NDRC-anchored coalitions
  rather than fragmenting into more signers. Denominator caveat (verified 2026-10-01): on an
  all-central-docs, any-genre denominator the share FALLS (23% → 15%, live 23.2 → 15.3) because
  single-issuer non-policy content (news, explainers, 15k "other") exploded after 2020. The
  coalition-size rise (2.3 → 3.7) is robust under every denominator. Caveat: single-agency
  portals over-represented. *(Edited 2026-10-01 per `consistency-review.md` M1/M3/L4: the
  earlier text quoted 13,370 / 15x, "17% to 43%" and a second cut "16% → 32% on
  gov/ndrc/mof/cac/mofcom, 2005-09 → 2020-26" in the same paragraph, and said joint docs
  "cascade wider"; the 16 → 32 figure was a different site set with a pooled end period, the
  run log's 17.0 → 34.4 is the pooled variant of the canonical cut, and all three are true.)*
  The 粤办 docnum-alias
  parser bug was confirmed and fixed (commit `e8246b2`): the phantom 省委办公厅+省政府办公厅
  pair fell 177 → 1 and the Guangdong 2010-12 provincial bump (28-33%) collapsed to ~1%, it was
  entirely the artifact; 396 rows corrected, central figures unchanged. The parser now rebuilds
  `doc_issuers` nightly (Phase 2b).

### Part IV. What is being governed
- **AI governance** (the spine chapter: `ai-governance-diffusion.md` + `ai-plus-fidelity.md` +
  `ai-regulatory-web.md`; the AI-tocracy line and Sheehan's three CAC rules). Two faces, two
  mechanisms: regulation is a CAC monopoly that self-extends at the center; the promotional "AI+"
  program diffuses sub-nationally and is elaborated into locally authored sector plans.
- **Industrial policy** (`industrial-policy-targeting.md`; Fang/Li/Lu "Decoding China's
  Industrial Policies", NBER w33814). Targeting broadened not concentrated (sector HHI fell by
  more than half); money is a narrow instrument concentrated in chips, new energy, NEV and
  biopharma while legacy sectors get rules; place-based sectors see real sub-national pile-on,
  network-rule sectors (data, telecom, platforms) stay central. A 2026-10-07 robustness check
  that restores the 74 shallow-archive sites (incl. MIIT; the same rule re-run on 2026-10-07
  selects 77 sites / 28,940 docs, the memo's universe (b)) leaves the HHI, rise-fall and
  instrument-mix findings within 2 points but moves the level composition of MIIT's own sectors
  by 5-19 points central, so "future industries are local from the start" is withdrawn.
  Re-basing the level analysis on `doc_identity.admin_level_doc` (same date) replaces the 1.5
  tilt line, which at document level selects the average sector, with a z >= 3 test against a
  sector-size-matched pool null: telecom, platforms, data, heavy industry, ships and NEV stay
  centrally targeted, real estate, low-altitude and equipment stay local, agriculture flips from
  central to local (its "central" documents were npc-filed local regulations), and "AI is evenly
  spread" is withdrawn.
- **Attention and campaigns** (`attention-campaigns.md`; Baumgartner-Jones punctuated
  equilibrium, Q1+Q4). Attention is punctuated at the topic level (Party 2020-21, Health 2020,
  Credit 2018) but not classically fat-tailed when pooled. The campaign label moved UP the
  hierarchy (central 0.21% to 0.99%) while municipal is flat-to-falling, the opposite of the
  standard "campaigns devolve to local execution" expectation.

---

## Status and what remains

*(Status 2026-10-08, rewritten against the live droplet DB and the git log rather than from
memory. Every claim below carries the date it was verified. The 2026-10-01 and 2026-10-07
versions of this list are in git history and are not reproduced here, because both had gone
stale in the same way, described at the end of this section.)*

**Done.** All nine replications (diffusion atlas, recentralization/experimentation, the Wang/Yang
experimentation backbone, AI governance in three memos, industrial-policy targeting,
attention/campaigns, the citation-network/authority backbone, corpus-wide fidelity, the issuer
parser plus joint-issuance study), the tracker (shipped, nightly-refreshed), the provincial anchor
class, the per-document identity layer A1-A7, and the B-series memos B1 through B7.

**Live figures, verified 2026-10-08 on the droplet.** Corpus **346,955** documents across **479**
sites. Citation resolution **52.97%**, **310,136** resolved of **585,471** edges. `doc_identity`
**338,856** rows carrying all eleven columns. `instrument_succession` 14,624 rows.
`diffusion_events` 45,524 rows, `tracker_weekly` 46,178. `validate_cascades.py` passes **15 of 15**
on this build. Tonight's nightly is in Phase 2 and holds the write lock until roughly 10:00 UTC on
2026-10-09, so everything that needs a writer is deferred, not forgotten. [measured]

### Two results, not housekeeping

**1. The corpus now holds a 31.4-year single-jurisdiction run.** `crawlers/sz_gazette.py` walks the
Shenzhen 政府公报 archive and brought in **11,450** documents, 11,204 with body text (97.9%), with
**continuous issue coverage 1995-04 to 2026-09** (`sz-gazette-scoping.md` §2 corrected an earlier
38-year claim: the 59 pre-1995 rows sit in retrospective compilation issues printed 2002-03, and the
platform's earliest real issue folder is `zfgb/1995/gb68`, so issues 1 to 67 were never published).
This is the deepest run the corpus has for one jurisdiction, and it changes what the volume can
claim: a within-jurisdiction time series over three decades does not depend on cross-site coverage,
so it is not vulnerable to the coverage bias that caveats every cross-sectional chapter. It has
already paid for itself twice, in `instrument-lifespan.md` (median instrument survival is not
reached in any stratum; at most a quarter of instrument-shaped municipal documents are ever formally
repealed and the survivor curve plateaus near 0.75 after twelve years, while the 规范性文件 register
class with a written 3 or 5 year 有效期 term is repealed at three times the rate of ordinary 文件,
so municipal Shenzhen retires rules by sunset clause and not by repeal notice) and in the
denominator work below. n=1, and it is a special economic zone. [measured]

**2. The 文号 serial read as a denominator is the volume's first measurement that is not
coverage-limited.** `wenhao-denominator.md` reads the document serial as a *register count* rather
than as a document we hold, so the maximum serial observed per series per year estimates total
numbered issuance whether or not the gazette printed it. That breaks the dependence on what we
crawled, which is the standing limit on every other chapter here. `wenhao-denominator-wuxi.md`
(2026-10-08) then ran the same estimators on Wuxi, an ordinary Jiangsu prefecture, and the verdict
is **replication in proportion but not in path**: over 2010-2025 Wuxi's government register (锡政发
plus the 锡政呈 请示 register split out of it in 2018, which otherwise reads as a false 84%
one-year collapse) falls -6.8%/yr against 深府's -6.0%/yr on the same window, and its office series
-12.6%/yr against 深府办's -14.9%/yr, with 规范性文件 registers appearing in the same window at the
same scale; but Wuxi held level through 2017 and stepped down in 2019 where Shenzhen fell through
2012-2017, its office series fell by three quarters rather than collapsing, and the pre-2010
Shenzhen decline does not appear in Wuxi at all. So the narrowing of the formal-document channel is
not a Shenzhen artefact, while its timing is local. n=2. [measured]

### Closed since the 2026-10-07 status

- **A second Jiangsu prefecture at Suzhou's depth: in the corpus, with one merge outstanding.**
  Wuxi was crawled into a separate DB to `wuxi_rows_after=3865` and merged on 2026-10-08 at
  05:15-05:18 (4,685 rows added, 61 duplicates skipped, 7 new sites; corpus 341,313 to 345,998
  exactly, against a pre-registered ~4,616). Live 2026-10-08: `wuxi` 2,209 plus seven `wxd_*`
  district sites 2,668, **4,877** together. **A second merge of about 1,707 remaining `wuxi` rows
  is still pending**, blocked by the nightly write lock, so this item is closed as "the prefecture
  is in the corpus" and not as "the merge is finished". B1 itself is discharged only when
  `fidelity-wuxi.md` reports; that study is in flight. [measured 2026-10-08]
- **The date-ordered `localized_of` and the `province` / `instrument_kind` columns are in the
  droplet's identity build.** Verified 2026-10-08: `doc_identity` has all eleven columns;
  `province` is populated on 177,476 rows; `instrument_kind` splits framework 99,174 /
  housekeeping 13,876 / other 225,806. One correction to the committing memo: the date-ordered
  `localized_of` is **2,014** rows on the live build, not the 1,958 the commit message quoted. The
  droplet build is the authority. [measured 2026-10-08]
- **The framework-gate widening that `instrument_kind` carries is in force.** This was the one
  item worth re-checking rather than assuming, because the code and the data landed separately.
  `build_diffusion_events.is_framework` returns `kind == "framework"` when the column is present
  and falls back to the old regex only when it is absent (commit `890a25a`, A7); the hand-check in
  `docs/working/qa-framework-gate.md` had found that old regex 23% precise. The column is present
  on the droplet, so the fallback is dead and the widened gate is what built the live 45,524-row
  `diffusion_events`. [measured 2026-10-08]
- **The §2.1 Jiangsu row re-read on the redated DB** (commit `5c8ecbc`, 2026-10-07). Verdict: the
  row's 8.0% relay was the implementing figure wearing an all-pairs label. The relay *share* is
  3.3% on the citation basis of both the old 473-pair run and the new 601-pair one, so the identity
  and citation fixes moved it by zero; the implementing subset recovers 7.4% against the row's
  8.0%. Denominator, not mechanism. [measured]
- **The A6 recoverable head crawl**, with one target reclassified rather than crawled. Landed:
  the Shenzhen 政府公报 (11,450, above), the gov.cn 中央文件 library (`zhengcelibrary_zy`, 566
  listed, 432 new) and the gov historical tail, and 大鹏新区's 规范性文件库 under `szdp` (8,628 on
  that site key). Two of the four "delisted" head items were recovered with zero new crawling of
  their own: 深圳市行政听证办法 (id 4952494) and 深财规〔2023〕3号 (id 10832248) both sit in the
  gazette, and 广东省控规条例 was already held under its full title and is resolved by a row in
  `data/instrument_aliases.csv`. Only 苏住建规〔2011〕4号 is genuinely gone. **Not closed as
  planned: 中山 `zs_lyj`.** Commit `f3e1073` records that zs.gov.cn is Tier C from the NYC vantage
  and that the A6 listing had been measured from the Mac; the site holds 113 documents from that
  Mac run and the rest is user-gated on a residential vantage. [measured 2026-10-08]

### Open now

Each item was re-verified on 2026-10-08 unless noted.

- **MIIT bodies.** 5,607 of 7,864 `miit` documents have no usable body on the live DB (the memos
  quote 5,383 bodiless, of which 3,790 are 14-byte anti-bot stubs and 1,527 are missing files; the
  live count is higher because the nightly keeps re-fetching them). Needs a residential or HK fetch
  vantage, not a selector fix, and they can never gain a body from NYC.
- **The jurisdiction-level breadth recount.** Open since 2026-10-01 and still not done. The
  per-document level distribution is available (`doc_identity`: municipal 122,625, provincial
  68,300, central 67,439, media 50,985, district 27,800, research 1,707), but the recount asked for
  is of *jurisdictions covered*, not documents, and no one has run it.
- **The 部门规章 wall and the other datacenter-blocked tiers.** About 16% of the top-400 unresolved
  citation head is ministerial 令 that is not in gov.cn's library and whose ministries block the
  droplet; `huizhou` and `yangjiang` remain hard-blocked from the DigitalOcean IP. Reaching these
  needs HK or 北大法宝, which is a vantage decision and not a crawler one.
- **The Hanweb-datacall JS portals**, roughly 52 prefecture portals including 济南 and 郑州. Needs
  browser network inspection to find the data call, as 海淀 did.
- **The body-tail trim.** 33,105 bodies carry share, print and navigation chrome that the
  never-shorten guard froze in place. The trim is scripted and verified on `gov` (commit
  `5a8c4cb`) and deliberately ordered trim-then-BM25-once, but it is a writer, so it waits for the
  lock. Deferred, not blocked on knowledge.
- **Two deferred resolver-precision patterns**: generic short titles (政府信息公开指南,
  涉企收费目录清单) attracting containment, and documents *about* an instrument (延长 / 贯彻 /
  废止) winning containment over the instrument itself. Held back on purpose. Two simultaneous
  resolver changes would confound the measurement of each, so these follow once the org-stub gate's
  pre-registered effect below is read.
- **The org-stub gate's effect: PRE-REGISTERED, NOT YET OBSERVED.** See the next section.
- **`sites.admin_level` still carries the site level.** npc re-leveling landed as
  `doc_identity.admin_level_doc` only, so any new analysis must join the identity table rather than
  `sites`.
- **`diffusion_events.topic` stores only the anchor's first topic tag.** The tracker service
  compensates with a cached anchor-to-topics map, and the consequence measured 2026-10-07 is that
  every topic-labelled aggregate shifts by relabelling when anchor selection changes. Treat any
  topic-level series as sensitive to anchor selection.

### Landed since the 2026-10-07 status and missing from it

**Seven correctness fixes to the identity and citation layer.** [measured]

1. **Mirror determinism** (`b1aff31`). Mirror selection is deterministic (lowest id on a date tie)
   instead of "the last row scanned wins". 85.6k resolved edges moved to a different copy of the
   same text and the representative of about 18.8k titles changed. This changes *which* document
   holds an edge, not how many an instrument receives, so it relabels aggregates without moving
   denominators.
2. **Statute mirror pooling** (`64529f3`). `_best_core`'s `KEY_MIN = 6` floor was measured on the
   *folded* core, so every national statute was refused an `instrument_key` and no copies pooled.
   This is the fourth instance of the folded-string length-floor bug shape, and it was found by
   looking for it on purpose.
3. **The canonical-repost tier** (`a72a341`). A repost cannot be an instrument's canonical copy;
   the date tier had been deciding alone.
4. **The annual-series split** (`6e0ccb5`). A title a government re-issues every year is not one
   instrument. 15 of 15 on new splits, 10 of 10 on an adversarial sample of pools left merged.
5. **The balanced-bracket reference pattern** (`03263eb`). A 《》 capture must not cross an
   unclosed bracket.
6. **The write-contention retry layer** (`bc8517d`). A busy write lock must cost one row, not the
   whole run. Nine of thirteen `--backfill-bodies` runs had been dying on their UPDATE *after*
   paying for the fetch; the lesson recorded alongside it is that the SQLite limit is transaction
   hold time, not writer count.
7. **A1's per-document citation weighting** (`a494955`). A citation is worth the citing
   *document's* level, not its host site's. 23,214 of 585,471 edges disagree (3.97%) and 13,846 of
   the 310,136 rank-bearing edges (4.46%), but the rank effect is not small: 5,930 of 47,309 ranked
   documents move (12.5%), median relative move 21.3%. The direction is systematically the bug:
   national laws cited mainly by npc 地方法规 had been paid the 3.0 central rate. This is in the
   stored `citation_rank` now.

**The cross-site body-clobbering bug and its repair.** `5d872b2` closed the hole (both stores now
guard `DO UPDATE` on `site_key`) and `4a59e97` repaired the damage. 261 rows had their saved HTML
sitting in another site's directory, which the `raw_html/<site_key>/<id>.html` invariant makes proof
of a clobber. 21 of the 261 were *not* corrupt, because `crawlers/gov.py` resolves a doc id by url
before minting one and so legitimately adopts a row's id when a Shenzhen district row points at a
www.gov.cn article; clearing those would have destroyed correct content. **240 rows repaired, 21
kept and recorded.** [measured]

**The silent classifier failure, and its fix measured in production.** A third of all DeepSeek
classification calls had been failing since the 2026-07-25 `deepseek-v4-flash` migration, in every
nightly log back through mid-September, because v4-flash is a reasoning model that bills reasoning
tokens against `max_tokens` and the budget was 2,000. The code read empty content as a content
filter and skipped it silently, leaving `classified_at = ''` so the document was re-sent every
night forever. `1511b81` raises the budget to 12,000 with one 24,000 retry on
`finish_reason="length"`, names every failure reason, and persists failures to a
`classify_failures` side table. **Measured in tonight's production run: 4,400 consecutive documents
classified with 0 errors**, against the roughly 34% failure rate it replaced. [measured 2026-10-08]

**Phase 1 timing.** `36fba8a` adds per-crawler timeouts and moves the measured zero-yield walkers
to a weekly cadence, after a measurement found Phase 1 spending 240-271 minutes to add ~250
documents with 15 zero-yield crawlers accounting for 196 of 252 median minutes. Phase 1 now
finishes about **41 minutes earlier** than the mean of the previous four nights, and the gate is
confirmed live in the nightly. [measured]

**The org-stub containment gate, with a pre-registered prediction that is NOT yet observed.**
`4b890aa` makes organization-name-only titles exact-match-only targets, because the containment
tier let any reference that merely *embeds* an agency name land on a masthead stub when the real
instrument is not held (`广东省自然资源厅` had reached #20 by `citation_rank`). Where the 4,789
displaced edges go was measured against all live titles: **4,567 become honest-unresolved, 134 are
gains** (they now reach the right instrument through its 印发 or decree wrapper or a 【已废止】
copy), 64 land on a 转发 transmittal (better than a stub, still a proxy), and 24 are wrong-to-wrong
and were already wrong. **Zero correct edges lost.** **PRE-REGISTERED:** when tonight's Phase 2b
citation rebuild runs, resolved edges should **fall by about 4,570 net, taking resolution from
52.97% to roughly 52.2%**, and 广东省自然资源厅 should leave the top 20. That fall *is* the
improvement: false edges become honest unresolved ones, which is the August backfill's "the
absolute resolved count, not the %, is the honest metric" lesson read in the other direction. If
resolution instead rises, or falls by much more than ~4,600, something else moved and must be
investigated. **This has not happened yet.** The classifier has not reached Phase 2b, so the
52.97% above is the pre-gate number and the prediction is still a prediction. [pre-registered]

**The validator is now 15 checks**, and both splits exist for the same reason. `9dd6bf3` split the
城乡规划法 check into `cxgh_edges` (edge rows, what `citation_rank` weights) and `cxgh_citers`
(distinct citing documents, self-cites dropped), because the single check printed "inbound
citations" while counting edges and that ambiguity produced a false alarm. `07f3541` split the AI+
check the same way into `aiplus_implementing` (the confirmed citation and title_reissue tiers) and
`aiplus_topic_genre` (the probable-but-unconfirmed ceiling), after a 131-event "failure" on a build
where the cascade had not changed. The general lesson, now three times over: **when a nightly check
fails, first ask whether its metric conflates two things.** [measured]

**New memos.** `wenhao-denominator.md` and `wenhao-denominator-wuxi.md` (the denominator result
above), `instrument-lifespan.md` (repeal and sunset over thirty years of the Shenzhen gazette), and
`docs/working/sz-gazette-scoping.md` (the scoping that corrected the 38-year claim to 31.4 years and
withdrew its own §3.2 函 rise). `pair-channels.md` was already named in the 2026-10-07 status and is
listed here only so the set is complete.

### How this section goes stale

This section is edited by whoever finishes a piece of work, so it drifts within a day of heavy
change: nobody who closes an item is the person who wrote its entry. The previous version was
committed 2026-10-07 at 03:00 and was accurate then; five of the six items on its "Open now" list
closed over the next twenty-four hours, and two days of work landed that it never mentioned. It has
now gone stale that way twice in two days. The fix is a format change, not more diligence. **Any
claim of the form "open" or "landed" carries the date it was verified**, as every line above does,
so a reader can see how old a claim is instead of having to trust it. And the section is
**re-checked against the git log and the live DB rather than from memory**, which is how five
"open" items were found closed in minutes here.

Standing caveats that apply to every chapter: coverage bias (proxy-blocked provinces invisible,
Guangdong over-represented at district depth), ~52-54% citation resolution depending on date
*(50.5% live 2026-10-07, 270,211 of 534,722, after the containment gate un-resolved wrong proxies;
the lower rate is the more honest one and every "~52%" in the memos is now a ceiling on the rate
and a floor on the counts)*
*(Corrected 2026-10-08: 52.97% live, 310,136 of 585,471. The 50.5% was measured before the
Wuxi merge and the 2026-10-07 identity and citation rebuild; the org-stub gate's pre-registered
fall to about 52.2% has not run yet, so neither number is the settled one.)*
(all counts are floors), publication date is not adoption date, title-lexicon recall is a
fraction of body mention, and the selection boundary above. Mechanism-level throughout, no
regime-type labels. Two cross-memo comparability notes (added 2026-10-01, `consistency-review.md`
M7 and L1): npc local regulations are handled differently per memo (counted as central in
recentralization, re-leveled by publisher in citation-network, excluded in joint-issuance,
removed as anchors but kept as sources in the atlas), so level shares are within-memo only; and
the 以旧换新 "median lag" has four definitions (consumption ~49 days, first title-matched
re-issuance per unit; atlas 76 / 79 days, adoption-grade / confirmed events; this memo's 38
days, the Guangdong 实施方案 to 26 cities provincial hop), all correct on their own base.

*(2026-10-07) The volume now has one measurement that is not coverage-limited. `wenhao-denominator.md`
reads the 文号 serial as a register count rather than a document we hold, so the maximum serial observed
per series per year estimates Shenzhen's total numbered issuance whether or not the gazette printed it:
the municipal government's own numbered 文件 series (深府) falls from 276-365 a year in 1995-1998 to
83-105 in 2017-2024 (-5.9%/yr even when cut to the single post-2009 administrative regime), the General
Office's series (深府办) collapses from 86-239 to 3-24, the 规范性文件 registers created 2007-2019 are too
small to account for either, and the letter series do **not** rise to absorb them (深府函 +0.2%/yr by
max-serial and -5.2%/yr by method-of-moments), which withdraws the 函 rise asserted in
`sz-gazette-scoping.md` §3.2. So the formal-document channel narrowed beside a letter channel that was
already larger than it in 2001; that is a change in instrument form, not evidence of less governing, and
it is n=1 on a special economic zone.*

*(2026-10-08) `wenhao-denominator-wuxi.md` runs the same 文号 estimators on Wuxi, an ordinary Jiangsu prefecture, and the verdict is (a), replication in proportion but not in path: over 2010-2025 Wuxi's government register (锡政发 plus the 锡政呈 请示 register split out of it in 2018, which otherwise reads as a false 84% one-year collapse) falls −6.8%/yr against 深府's −6.0%/yr and its office series −12.6%/yr against 深府办's −14.9%/yr, with 规范性文件 registers appearing in the same window at the same scale, but Wuxi held level through 2017 and stepped down in 2019 where Shenzhen fell through 2012-2017, its office series fell by three quarters rather than collapsing, and the pre-2010 Shenzhen decline does not appear in Wuxi at all.*
