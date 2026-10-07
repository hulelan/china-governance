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
promulgations in 2008-13 to a 17-19% peak in 2021-22, but 92% of it is exhortation; only 296 docs
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
now left unresolved rather than credited to a wrong target.)* The memos quote three earlier builds (28,880;
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
graph sees fewer than half of them, so the provincial memo's relay counts are floors. Verdict:
hardens, on one city; B1 is discharged only when a second Jiangsu prefecture is crawled to
Suzhou's depth. Corpus finding on the way: Suzhou's `date_published` is crawl-stamped in two
batches (2023-02-09, 2025-02-11) that the A4 rule does not catch; the memo re-dates from the URL
path and flags the 171 affected `diffusion_events` lags.)*

### Part III. Central-local dynamics
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
  that restores the 74 shallow-archive sites (incl. MIIT) leaves the HHI, rise-fall and
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

Done: all nine replications (diffusion atlas, recentralization/experimentation, the Wang/Yang
experimentation backbone, AI governance in three memos, industrial-policy targeting,
attention/campaigns, the citation-network/authority backbone, corpus-wide fidelity, the issuer
parser + joint-issuance study), plus the tracker and provincial anchors. The tracker is shipped
and nightly-refreshed. Open: the containment-proxy class of the resolver bug (H1 above), the
提振消费 anchor regression (fix in progress), a jurisdiction-level breadth recount, and npc
re-leveling in `sites`. *(Corrected 2026-10-01 per `consistency-review.md` M5; the earlier text
listed Parts I-III as "in progress".)*

Standing caveats that apply to every chapter: coverage bias (proxy-blocked provinces invisible,
Guangdong over-represented at district depth), ~52-54% citation resolution depending on date
(all counts are floors), publication date is not adoption date, title-lexicon recall is a
fraction of body mention, and the selection boundary above. Mechanism-level throughout, no
regime-type labels. Two cross-memo comparability notes (added 2026-10-01, `consistency-review.md`
M7 and L1): npc local regulations are handled differently per memo (counted as central in
recentralization, re-leveled by publisher in citation-network, excluded in joint-issuance,
removed as anchors but kept as sources in the atlas), so level shares are within-memo only; and
the 以旧换新 "median lag" has four definitions (consumption ~49 days, first title-matched
re-issuance per unit; atlas 76 / 79 days, adoption-grade / confirmed events; this memo's 38
days, the Guangdong 实施方案 to 26 cities provincial hop), all correct on their own base.
