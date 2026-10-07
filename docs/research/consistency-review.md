# Cross-memo consistency review (2026-10-01)

*Read-only QA pass over the 15 research memos and `findings-synthesis.md` before they become
chapters. Nothing was edited and nothing was written to the DB. Live numbers below were pulled
from `file:/root/china-governance/documents.db?mode=ro` on 2026-10-01 (after commits `cd42903`,
`c979a82`, `c6dbe04`, `e8246b2`, `ebf1dc8`). Each issue names the memos, quotes the conflicting
text briefly, says which figure is current and why, and recommends annotate or correct.*

Memos read: `findings-synthesis.md`, `diffusion-atlas.md`, `recentralization-experimentation.md`,
`experimentation-wang-yang.md`, `industrial-policy-targeting.md`, `attention-campaigns.md`,
`citation-network-structure.md`, `diffusion-fidelity.md`, `fidelity-provincial.md`,
`joint-issuance.md`, `ai-governance-diffusion.md`, `ai-plus-fidelity.md`, `ai-regulatory-web.md`,
`consumption-diffusion.md`, `related-literature.md` (Outcomes table), and
`docs/working/autonomous-run-log.md`.

---

## 0. Reference numbers (live, 2026-10-01)

Use these to judge every quoted figure below.

| quantity | live value | values quoted in memos |
|---|---|---|
| documents | 319,397 | 263,573 (consumption), 313,247 (ai-gov), 313,350 (ai-reg), 319,173 / 319,208 (others) |
| citations total / resolved | 533,358 / 287,607 = **53.9%** | 445,599 / 226,464 = 50.8% (consumption); 529,073 / 276,826 = 52.3% (ai-gov); 533,278 / 279,409 = 52.4% (citation-network); "~52%" everywhere else |
| `diffusion_events` rows | **32,825** (central 26,565 = citation 19,636 + title_reissue 438 + topic_genre 6,491; provincial 6,260) | 28,880 (atlas), 24,599 (synthesis, experimentation, industrial, fidelity) |
| central confirmed events (citation + title_reissue) | **20,074** | 17,381 (atlas), 18,088 (fidelity) |
| central anchors | **3,138** | 2,994 (atlas, after its own cleaning), 2,943 (industrial), 2,336 scored (fidelity) |
| `doc_issuers` joint (n>=2) | **13,004** | 13,370 (joint-issuance, synthesis, run log; pre-粤办 fix) |
| joint share, robustness central set (gov/ndrc/mof/mee, policy genres) | 17.0 / 15.9 / 23.5 / 31.2 / **43.2** by 5-year period; **34.4** for 2020-26 pooled | 17%→43% (memo, synthesis); 17.0→34.4 (run log it. 15); 16%→32% (synthesis "verified" cut on gov/ndrc/mof/cac/mofcom) |
| joint share, all central docs any genre | 23.2 → 15.3 (2005-09 → 2024-26) | 22% → 15% (synthesis), 22.4 → 15.3 (run log) |
| CAC triad central citers (distinct) | 80 / 62 / 50; pooled 118; AI+ opinion 10 central / 6 prov / 8 muni | unchanged from both AI memos |
| 2017 AI plan central citers | **31** | 31 (ai-gov Table 3a), **20** (ai-reg Table 1) |
| top `citation_rank` | 政府信息公开条例 4,081; 道路交通安全法 3,306; 城乡规划法 3,284; 财政违法行为处罚处分条例 2,012; 广东省城乡规划条例 1,650 | matches run log it. 12 |

---

## 1. Issues ranked by severity

Severity scale. **HIGH** = a reader of the chapter would take away a wrong or unsupported claim.
**MEDIUM** = two memos disagree or a number is from a superseded build and is quoted as if
current; a careful reader would be confused. **LOW** = cosmetic or self-correcting drift.

### HIGH

**H1. The proxy-target bug is described as "FIXED at the root". It is partly fixed. Containment
proxies to instruments that have no exact-title copy in the corpus are still in `citations` and
`citation_rank`, and one new central-to-provincial mis-attribution appeared.**

- Memos: `findings-synthesis.md` Part I ("FIXED at the root (commits cd42903/c979a82)"),
  `citation-network-structure.md` §1.3 update note ("fixed at the root"), `consumption-diffusion.md`
  §1-§2, `attention-campaigns.md` §2.3 anchors, `diffusion-atlas.md` §4a.
- What the citation-network memo actually corrected: 68,880 edges (27%). Of those only 18,547
  landed on an existing corpus document; 50,333 went to virtual nodes for instruments with no
  exact-title copy. The DB fix (exact title/core wins before containment) can only repair the
  first class. Live check of three strings from the memo's own virtual-node list confirms the
  second class persists: 机动车驾驶证申领和使用规定 still resolves 686 edges to a provincial
  热点问题解答 page (the rule itself sits in the corpus as 11637955 with a `（公安部令第162号）`
  suffix and holds 2); 百千万工程 resolves 414 edges to a Guangzhou news item; 建设工程规划许可证
  resolves 258 to a Shenzhen permit notice.
- New regression found: the string 提振消费专项行动方案 (113 edges: 77 `named`, 36 `llm`) now
  resolves to **900105357, a Beijing provincial news page** "北京发布《深化改革提振消费专项行动方案》"
  (`citation_rank` 216.5). Both central copies (gov 12650974, Xinhua 12704698) now have **0**
  inbound. NDRC and MOF documents citing the central plan are recorded as citing Beijing. In
  `diffusion_events` this page is now a **provincial anchor with 7 events**, which is spurious.
  The central anchor 12650974 still carries 31 events because the auto-matcher pools by 《》 core,
  so the tracker is less affected than `citations`/`citation_rank`.
- Consequence for memos. `consumption-diffusion.md` §1 (Xinhua copy cr=200, gov copy 0) and
  Table 2a row 3 (boost-consumption 37/3/7/3/22 = 72 citers) are no longer reproducible from the
  listed ids (the four-id pool now returns 18/14/5/3 = 40). `attention-campaigns.md` uses
  `citation_rank` to pick burst anchors; its 13 quoted `cr` values were checked and are
  unchanged, but two anchor ids now hold 0 raw inbound because the inbound moved to another copy
  (12740781 → 900098379 `bjb_wjw` 83; 12651172 → 900083511 `fj_wjw` 634). The `diffusion_events`
  citer counts it quotes (e.g. 201 for 纪律处分条例) still hold.
- Recommended edit: **correct** the synthesis Part I and the citation-network §1.3 note to say
  the exact-title class is fixed and the containment class (no exact-title copy in corpus, the
  memo's ~50k virtual-node edges) remains, so `citation_rank` still carries proxy mass below the
  top-30. **Correct** `consumption-diffusion.md` §1-§2 anchor identity for 提振消费 (annotate with
  the live state). **File a data bug** for the 提振消费 → Beijing resolution and the 7-event
  provincial anchor; it is exactly the pattern the fix targeted and it affects a cascade the
  synthesis names.

**H2. Every event-count figure is from one of three superseded `diffusion_events` builds, and
the synthesis quotes the middle one as the auto-matcher's size.**

- Memos and the build each used: `diffusion-atlas.md` = 28,880 (pre npc/explainer fix; it
  removed 819 npc anchors itself → 2,994 anchors / 23,898 events); `experimentation-wang-yang.md`,
  `industrial-policy-targeting.md`, `diffusion-fidelity.md`, `attention-campaigns.md`,
  `findings-synthesis.md` through-line = 24,599 (post npc fix, pre resolver fix);
  `fidelity-provincial.md` chains inherit the 24,599 build; `joint-issuance.md` §5 read the table
  during the resolver rebuild (run log it. 10 notes this). Live: 26,565 central + 6,260 provincial
  = 32,825.
- Exact quotes: synthesis "The auto-matcher (`diffusion_events`, 24,599 events)"; experimentation
  "the cleaned `diffusion_events` table (24,599 central-anchored cascade edges)" and "all 24,599
  anchors are central docs" (anchors and events conflated; anchors were 2,943); industrial
  "`diffusion_events` holds 24,599 events from 2,943 central anchors"; fidelity "`diffusion_events`
  holds 24,599 anchor-to-source pairs"; atlas "`diffusion_events` holds 28,880 (source, anchor)
  rows".
- Spot checks on the live table show the atlas's headline anchors moved but held shape:
  政府信息公开条例 68 confirmed sites (atlas: 68); 以旧换新 SC plan 37 sites (atlas HE table: 37);
  AI+ opinion 22 sites / 33 events (atlas: 20 sites; run log: 33 events). Shares and orderings are
  probably robust. Raw counts (17,381 confirmed, 8,410 adoption-grade, 1,030 paired anchors, 61
  tightly-linked pilots, 333 edges, 13,509 scored pairs, 2,444 chains, sector event table in
  industrial §5) are not current.
- Recommended edit: **annotate** each memo's data section with the build it used ("built on the
  N-row table of <date>; the table is rebuilt nightly and was 32,825 rows on 2026-10-01").
  **Correct** the synthesis through-line to the live central count and say the table grows
  nightly. Fix the experimentation "24,599 anchors" wording. Do not recompute unless a chapter
  quotes the raw count.

### MEDIUM

**M1. The central joint-issuance share has three headline values and the synthesis quotes two
of them in one paragraph.**

- `joint-issuance.md` §0 and §2b: 17% → 43% (robustness set gov/ndrc/mof/mee, policy genres,
  2005-09 → 2024-26). Verified live: 17.0 → 43.2.
- Run log it. 15: "central share unchanged (17.0→34.4%)". Verified: 34.4 is the same set with
  2020-26 pooled.
- Synthesis Part III: "17% ... to 43%" and, four sentences later, "the rise holds on a
  policy-genre, fixed-site denominator (16% → 32% on gov/ndrc/mof/cac/mofcom, 2005-09 → 2020-26)".
  A different site set (cac/mofcom swapped for mee) and a pooled end period. Both are true. A
  reader sees 43 and 32 for "the rise" with no bridge.
- The all-docs denominator reverses the sign (23.2 → 15.3 live; synthesis says 22 → 15). The
  synthesis annotates this. `related-literature.md` Outcomes row ("17%→43%") does not.
- Recommended edit: **correct** the synthesis to one canonical sentence (robustness set, by
  period: 17 → 16 → 24 → 31 → 43; pooled 2020-26 = 34) and keep the denominator caveat; add the
  caveat to the Outcomes row. Annotate the run log figure as the pooled variant.

**M2. Two AI memos written the same day disagree on the 2017 plan's central citers and on the
CAC share of the triad's follow-on web.**

- `ai-governance-diffusion.md` Table 3a: 新一代AI发展规划 **31** central citers.
  `ai-regulatory-web.md` Table 1: **20** (gov 15, most 3, moe 1, cac 1). Live: 31. The ai-reg
  figure is wrong or uses an undeclared filter.
- `ai-regulatory-web.md` §0 and §7: "~85-90% carry the `cac` site key". `ai-governance-diffusion.md`
  §7: "110 carry the `cac` site key (verified: cac 110, gov 4, sic 2, ipc_court 2)" = 93%. The
  ai-reg Table 1 row sums (74+58+47 = 179 over 118 distinct) cannot give a share directly, so
  "85-90%" is an estimate; 110/118 is the measured number.
- Recommended edit: **correct** ai-reg Table 1 (2017 plan row) to the live 31 with the site
  split, and replace "~85-90%" with 110/118 (93%).

**M3. Atlas "co-signature adds nothing" is stated unqualified in three places; joint-issuance
refines it, and mischaracterizes the atlas class while doing so.**

- Atlas §0.4 "The State Council masthead buys breadth; co-signatures do not"; §6 "Co-signature
  does not buy breadth"; §10 "adding co-signing ministries adds nothing". Joint-issuance §0.4
  "Co-signature buys breadth only at scale ... Coalitions of five or more ... are echoed 2.5 to
  3.7 times as often". Synthesis reconciliation: "2-3 signers add nothing (confirming the atlas),
  ministry-led 5+ coalitions are echoed 2.5-3.7x as often and sooner".
- The reconciliation is right in direction. Two corrections. (a) Joint-issuance §5c says the
  atlas's "joint ministries" class "is mostly two- and three-signer documents". Live
  `doc_issuers` on the atlas-style class (central non-SC anchors with 等N部门 in the title or
  n>=2): 2-3 signers 295, 4-9 signers 222, 10+ 68. Half, not most. The atlas pooled all sizes;
  the 等N部门 cue it used is the elided form that is typically large. (b) The synthesis says
  joint docs "cascade wider" at scale. Joint-issuance §5c says the gain is "on the extensive
  margin, whether any sub-national unit responds, more than on the intensive margin". Mean sites
  among echoed were 3.45-3.70 vs 2.86. "Echoed more often" is the finding; "wider" overstates.
- Denominator note: the atlas issuer table (§6a) is confirmed events only; joint-issuance §5
  counts all `diffusion_events` rows including topic_genre. The two breadth numbers are not on
  the same base.
- Recommended edit: **annotate** atlas §0.4, §6 and §10 with a pointer to joint-issuance §5c
  ("holds for 2-3 signers; 5+ coalitions are echoed 2.5-3.7x as often"). **Correct** joint
  §5c's "mostly two- and three-signer". **Correct** the synthesis verb to "are echoed more often
  and sooner".

**M4. Three memos still carry pre-fix text that contradicts their own update notes.**

- `citation-network-structure.md`: §1.3 carries the "since resolved" note, but §0 Artifacts still
  says "The DB's stored `citation_rank` is not corrected and its top of table still carries these
  artifacts" and §7 says "`citation_rank` is uncorrected. The DB column still ranks proxy targets
  at the top. Its top 30 overlaps the corrected inbound top 30 on 13 entries." Run log it. 12:
  overlap is now 19/30 and the top is framework law.
- `joint-issuance.md`: §2f carries the 粤办 fix note, but §6a error (1) still says "the likely
  source of the Guangdong 2010-12 bump" and §7 Next (1) still lists "Fix the 粤办 alias" as to
  do. The title and §1 still say 10,304 / 13,370 joint (live 13,004; the frame count moved by at
  most the 396 corrected sub-national rows).
- `ai-plus-fidelity.md`: §0 carries the n=12 note, but §4 still says "the relay calibration points
  ... confirm the metric saturates correctly for verbatim text, so the bimodal gap is real".
- Recommended edit: **annotate** each residual sentence with the same one-line update already
  used in the memo, or strike it. Cheap and prevents a chapter inheriting a dead caveat.

**M5. The synthesis "Status and what remains" section is stale.**

- Quote: "In progress (paused on a session rate limit, resuming after it resets): the
  citation-network/authority backbone (Part I), corpus-wide fidelity (Part II), and the issuer
  parser + joint-issuance study (Part III)." All three landed (run log it. 9-13) and are
  summarized in the same document's Parts I-III.
- Recommended edit: **correct** to "Done: all nine replications + tracker + provincial anchors.
  Open: the containment-proxy class (H1), the 提振消费 anchor regression, jurisdiction-level
  breadth recount, npc re-leveling in `sites`."

**M6. "No level gradient" (AI+) vs "monotonic level gradient" (corpus-wide) is not annotated the
way the bimodality claim was.**

- `ai-plus-fidelity.md` §3.3 "Fidelity varies by sector, not by level ... There is no
  province/city/district gradient"; `ai-governance-diffusion.md` §7 "There is no level gradient
  (a Haidian district plan elaborates as fully as a Jiangsu provincial one)".
  `diffusion-fidelity.md` §3.2: "The gradient is monotonic: province 0.074, city 0.051, department
  0.031, district 0.030"; `fidelity-provincial.md` refines it to "the copying tier is the
  prefecture city and only that tier".
- Not a contradiction (n=10 vs 13,509) but the same kind of small-n generalization that was
  annotated for bimodality. The synthesis takes the corpus-wide version and is right to.
- Recommended edit: **annotate** the two AI+ sentences: "n=10; corpus-wide a level gradient
  exists, see `diffusion-fidelity.md` §3.2 and `fidelity-provincial.md` §2.1".

**M7. "Central" is a different universe in each memo, so level shares are not comparable across
memos even though the synthesis places them side by side.**

- `recentralization-experimentation.md`: npc local regulations counted as central (central
  85,113 of 260,334). `citation-network-structure.md`: npc re-leveled by publisher (central
  62,300; it states the difference). `joint-issuance.md`: npc excluded entirely.
  `industrial-policy-targeting.md`: 74 date-stamped sites (27,915 docs, incl. all of MIIT) removed;
  npc kept. `diffusion-atlas.md`: npc anchors removed, npc as sources kept. `attention-campaigns.md`:
  government levels, npc kept (Weather 2018 and Tourism 2010 bursts are npc-led).
- Effect: industrial's "universe central % 39 / 45 / 26" and citation-network's "central 22.3% of
  nodes" and recentralization's pilot propensities are on different bases. The synthesis does not
  compare them numerically, so no claim is wrong, but a chapter that does will mislead.
- Recommended edit: **annotate** each memo's universe paragraph with its npc rule, and add one
  line to the synthesis standing caveats: "npc local regulations are handled differently per
  memo; level shares are within-memo only". Longer term: fix `sites.admin_level` for npc rows
  (atlas §8 and citation-network §1.2 both ask for this).

**M8. Upward-citation shares are quoted on two different bases without saying so.**

- `citation-network-structure.md` §4 and synthesis Part I: "upward 46.4%" (all 163,814 corrected
  edges including central→central). `recentralization-experimentation.md` §2.1 and synthesis
  Part III: "upward share rises from 0.58 to 0.66" (sub-national sources only, raw resolved edges,
  185,447 dedup). The synthesis quotes 46% and the 7-11 point step three paragraphs apart.
- Recommended edit: **annotate** the synthesis: "46% of all edges; 58-68% of sub-national-source
  edges".

### LOW

**L1. The 以旧换新 cascade has four different "median lag" values with four definitions.**
`consumption-diffusion.md` ~49 days (first title-matched re-issuance per unit, 18 units, 2024
wave); `diffusion-atlas.md` §3a 76 days (adoption-grade events, 28 sites) and §4a 79 days
(confirmed, 37 sites); synthesis and run log 38 days (Guangdong 实施方案 → 26 cities, provincial
hop). All correct. Recommended: **annotate** each with its definition when quoted together.

**L2. Resolution rate is quoted as 50.8 / 51 / 52 / 52.3 / 52.4%; live is 53.9%.** All floors.
Recommended: **annotate** as "~52-54% depending on date" or leave; the direction of every claim
is unaffected.

**L3. `related-literature.md` intro and Outcomes row say "~248k edges" / "On 248k edges".** The
citation-network memo was built on 279,409 resolved edges; live is 287,607. Recommended:
**correct** to "~280k".

**L4. Synthesis "15x the agenda's naive proxy" vs joint-issuance §1 "The naive multi-publisher
proxy the agenda cites finds 1,047"** (13,370 / 1,047 = 12.8x; run log used 852 → 15.7x).
Recommended: **correct** the synthesis to "13x" or cite the 852 figure explicitly.

**L5. `consumption-diffusion.md` appendix groups citers by `citations.source_level`.**
`recentralization-experimentation.md` §1 shows that column is stale on ~29k rows; every later
memo joins `sites.admin_level`. Trade-in core citers re-pulled via `sites`: 35 central / 13
provincial / 8 municipal / 1 department / 1 media = 58 (memo: 35/11/6/0/1 = 53). Direction
unchanged. Recommended: **annotate** Table 2a with the live split and the join used.

**L6. `ai-governance-diffusion.md` §2 "mirror gotcha" example is now resolved.** The municipal
mirror 900133026 ("cr=230") now has `citation_rank` 0 and 0 inbound; the canonical AI+ opinion
900039770 holds 54.5 / 25 as before. The labelling 答记者问 example (154 vs 4.5) still holds.
Recommended: **annotate** that the AI+ mirror case was removed by the resolver fix; keep the
curated-anchor method.

**L7. `citation-network-structure.md` and `fidelity-provincial.md` describe the same artifact
from two sides without cross-reference.** The 6,670 cross-province edges fidelity-provincial drops
as "resolver mis-targeting (ga→bj 855, szlhq→bj 302, ... fj_wjw)" are the mirror/proxy class
citation-network §1.3-§1.4 measures. Post-fix the count will differ. Recommended: **annotate**
fidelity-provincial §1 with "pre-fix count; see citation-network §1.3".

**L8. Atlas and recentralization reach compatible timings but the synthesis does not say so.**
Atlas §5: "2014-19 is the high point of local echo"; recentralization: upward-citation share
plateau 2013-17. These are the same signal seen through breadth and through direction.
Recommended: **annotate** the synthesis Part II/III with one sentence of convergence.

**L9. Experimentation §1 count 1,818 cue docs vs run log "1,834 central pilot-cue docs
all-cut".** Different date filters. Cosmetic.

**L10. `joint-issuance.md` §1 "npc ... 30,438 laws" vs citation-network §1.2 "npc 31,070
documents, 28,184 local".** Different filters. Cosmetic.

---

## 2. Scope-boundary checklist (category d)

Four standing caveats the synthesis says "every memo states": coverage bias, ~52% resolution
(counts are floors), publication is not adoption, no regime-type labels.

| memo | coverage bias | resolution floor | publication ≠ adoption | no regime labels | note |
|---|---|---|---|---|---|
| findings-synthesis | yes | yes | yes | yes | standing caveats paragraph |
| diffusion-atlas | yes | yes | yes (§9.6) | yes (§9.10) | |
| recentralization-experimentation | yes (§4.2) | yes | yes (§4.7) | **no** | has "Not causal"; add the line |
| experimentation-wang-yang | yes | yes | yes (§6.8) | **no** | has "Not causal, anywhere" |
| industrial-policy-targeting | yes (§6.5, §7) | **no** | **no** | **no** | uses `diffusion_events` lags and cascades without stating resolution; add all three |
| attention-campaigns | yes (§4) | **no** | partial (genre drift) | **no** | anchors drawn by `citation_rank`; add the resolution line |
| citation-network-structure | yes | yes | no (static; "Age" caveat instead) | **no** | add the regime line |
| diffusion-fidelity | partial (body coverage by tier; no Guangdong line) | **no** | yes ("citation is not implementation") | **no** | 322 sites, no geographic bias statement; add resolution |
| fidelity-provincial | yes (95% Guangdong) | yes | yes ("chronology, not causation") | **no** | |
| joint-issuance | yes | yes | yes ("publication date is not signing date") | **no** | |
| ai-governance-diffusion | yes | yes | yes | yes | |
| ai-plus-fidelity | yes | n/a (not citation based) | yes | yes | |
| ai-regulatory-web | yes | yes | yes | yes | |
| consumption-diffusion | yes | yes (50.8% then) | yes | **no** | |

Nine of fourteen memos omit the no-regime-labels line. None of them uses a regime label in its
text (checked: "Leninist", "authoritarian" appear only in cited paper titles and in the
`related-literature.md` bibliography). So the omission is a missing sentence, not a violation.
Recommended: **annotate** a one-line boundary into each memo's threats section (template from
`ai-regulatory-web.md` §6.6). Industrial and attention also need the resolution floor and the
publication caveat.

---

## 3. Synthesis traceability (category e)

Every numeric claim in `findings-synthesis.md` was traced to a memo and, where cheap, to the live
DB.

| synthesis claim | source memo | traces? | status |
|---|---|---|---|
| through-line: center designates, localities echo, reverse flow near-invisible | recentralization §3.4-3.5, experimentation §3b | yes | ok |
| "diffusion_events, 24,599 events" | build of it. 4 | yes | **stale (H2)**; live 26,565 central / 32,825 |
| top 1% hold 54.5%, Gini 0.947, 84% never cited, top-100 80 central / 75 regs+laws | citation-network §0, §2.2 (48+27=75) | yes | ok; computed on the memo's own corrected graph, not the DB |
| regs 7.3 in / 1.6 out, explainers 0.1 / 2.0; 62.5% / 13.7% | citation-network §0, §3 | yes | ok |
| up 46% / same 49% / down 4% | citation-network §4 | yes | ok; base differs from Part III (M8) |
| "FIXED at the root"; 279,409 → 287,607; 城乡规划法 2,141 | run log it. 12 | yes | **overstated (H1)** |
| province-before-city 68-76% | atlas §2d | yes | ok (pre-fix build) |
| SC 条例 breadth, 695-day median | atlas §2a | yes | ok |
| central output up ~75%, fast-echo share 50% → ~20% | atlas §5a (134→240 = +79%; 50.4→21.6/16.5) | yes | ok |
| 13,509 pairs; 88.3 / 9.8 / 1.9; relay = provincial 转发 within 90 days | fidelity §0-§3 | yes | ok (pre-fix build) |
| money ~2x reuse, never relay; 条例/办法 least copied; 意见 paraphrased | fidelity §3.3-3.4 | yes | ok |
| districts elaborate most; provinces forwarding tier | fidelity §3.2 | yes | ok; conflicts with AI+ "no gradient" (M6) |
| 6,622 pairs, 2,444 chains, 95% GD; relay 10.8 vs 3.3; 0.115 vs 0.074; 75% renamed re-issuance, 181 d; 92.8%; 0.8% C-only; districts 0.2%; 方案 half / 办法 1%; 0.50-0.77 vs 0.06-0.25 | fidelity-provincial | yes | ok |
| 6,260 provincial events / 1,126 instruments; 以旧换新 26 cities 38 d | run log it. 14 | yes | ok (live) |
| upward step 7-11 pts at 2013, reverts by 2023-26 | recentralization §2 | yes | ok |
| 1,592 pilot guidelines vs 633; cited by 833 sub-national docs; 0.4-1.2% | experimentation §1-§3 | yes | 833 is pre-fix raw-citation count; annotate |
| doc_issuers 79% / 97%; 13,370 joint; 15x proxy | joint §1, §6a | yes | 13,370 → 13,004 post-fix (M4); 15x vs 13x (L4) |
| 17% → 43%; 16% → 32%; 22% → 15% | joint §2b; main-thread verification | yes | **three values (M1)** |
| 2.4 → 3.9; 5+ from 5% to 30%; 288 mega-coalitions; MOF+税务 59%; NDRC hub | joint §3-§4 | yes | ok |
| "cascade wider only at scale ... 2.5-3.7x" | joint §5 | yes | verb overstates (M3) |
| 粤办 phantom 177 → 1; GD bump 28-33% → ~1%; 396 rows | run log it. 15 | yes | ok |
| AI: CAC monopoly self-extends; AI+ elaborated | ai-gov, ai-reg, ai-plus | yes | ok; ai-reg internal figure error (M2) |
| sector HHI fell by more than half; money in chips/new energy/NEV/biopharma | industrial §2-§3 | yes | ok |
| campaign label up the hierarchy 0.21% → 0.99% | attention §3 | yes | ok |
| Status: Parts I-III "in progress" | run log it. 9-13 | no | **stale (M5)** |
| standing caveats | all memos | partial | 9 memos lack the regime line (section 2) |

No synthesis claim is unsupported by a memo. Two are stale (event count, status), one is
overstated (fix at root), one is tripled (joint share), one overstates a verb (cascade wider).
Everything else traces cleanly.

---

## 4. Normalization notes a chapter editor should keep (category c, consolidated)

- Shares vs counts: every trend memo uses shares; the atlas §5 fixed panel and the joint §2b
  robustness set are the two fixed-site designs. Do not compare atlas breadth (sites) with joint
  §5 breadth (sites incl. topic_genre rows).
- Policy-genre vs all-docs: joint share flips sign (M1); campaign share and sector share are on
  all government docs; attention topic shares are on tagged docs (62-71%); industrial excludes 74
  date-stamped sites. State the denominator next to any cross-memo number.
- Title-lexicon vs body: industrial (4-8% recall), attention (1/6 recall), ai-gov (3-5x
  undercount). Comparable within a memo only.
- Level definitions: Shenzhen bureaus are "department" in atlas/industrial/attention, folded into
  municipal in recentralization/citation-network/joint. Beijing/Shanghai bureaus and `cq` are
  provincial units in atlas/fidelity-provincial, municipal in `sites`.
- Hop definitions for lag: see L1.

---

## 5. Verdict

The synthesis is **safe to build chapters on once H1, H2, M1 and M5 are corrected in the text**.
Its argument does not rest on any figure that moved: the province-before-city ordering, the
genre source/sink split, the 2013 upward step and reversal, the fidelity gradient and the
province-as-translation-layer result, the CAC monopoly, the HHI broadening and the campaign-label
climb all reproduce in direction on the live tables. What must change is the wording around the
resolver fix (partial, not root), the event-table size (nightly, three builds), the joint-share
sentence (one canonical cut), and the status paragraph. The `citation_rank`-dependent material
(attention anchors, consumption anchors, atlas HE rankings) should carry a build-date stamp and
the 提振消费 regression should be fixed before that cascade is used as a chapter example.

---

## Appendix: live queries used

```sql
-- reference numbers
SELECT COUNT(*) FROM documents;                                        -- 319,397
SELECT COUNT(*), SUM(target_id IS NOT NULL) FROM citations;            -- 533,358 / 287,607
SELECT anchor_level, match_type, COUNT(*) FROM diffusion_events GROUP BY 1,2;
SELECT COUNT(DISTINCT anchor_id) FROM diffusion_events WHERE anchor_level='central';  -- 3,138
SELECT COUNT(*), SUM(n_issuers>=2) FROM doc_issuers;                   -- 267,844 / 13,004

-- citation_rank + inbound for every anchor id quoted in attention / consumption / AI memos
SELECT id, citation_rank, (SELECT COUNT(*) FROM citations c WHERE c.target_id=d.id)
FROM documents d WHERE id IN (...);

-- H1: where the boost-consumption string resolves now
SELECT target_ref, citation_type, COUNT(*) FROM citations WHERE target_id=900105357 GROUP BY 1,2;
-- 提振消费专项行动方案 named 77 / 《提振消费专项行动方案》 llm 33 / llm 3
SELECT anchor_id, anchor_level, COUNT(*) FROM diffusion_events
WHERE anchor_title LIKE '%提振消费%' GROUP BY 1;    -- 12650974 central 31; 900105357 provincial 7

-- H1: containment proxies with no exact-title copy
SELECT c.target_id, COUNT(*), t.title FROM citations c JOIN documents t ON t.id=c.target_id
WHERE c.target_ref LIKE '%机动车驾驶证申领和使用规定%' GROUP BY 1 ORDER BY 2 DESC;  -- 900111176: 686
-- same for 百千万工程 (573943: 414) and 建设工程规划许可证 (12758835: 258)

-- M1: joint share, robustness central set, policy genres
-- (period CASE on substr(date_published,1,4); site_key IN ('gov','ndrc','mof','mee');
--  algo_doc_type IN the 16-genre POLICY tuple; n_issuers>=1)
-- 17.0 / 15.9 / 23.5 / 31.2 / 43.2 ; pooled 2020-26 = 34.4 ; all-genre all-central 23.2 -> 15.3

-- M2: 2017 plan central citers by level
SELECT s.admin_level, COUNT(DISTINCT c.source_id) FROM citations c
JOIN documents d ON d.id=c.source_id JOIN sites s ON s.site_key=d.site_key
WHERE c.target_id=900041126 GROUP BY 1;                                -- central 31

-- M3: coalition size of atlas-style joint anchors
-- diffusion_events central anchors JOIN doc_issuers, non-SC lead, (title LIKE '%等%部门%' OR n>=2)
-- 1: 5 | 2-3: 295 | 4-9: 222 | 10+: 68 ; mean confirmed sites among echoed 3.15 / 5.63 / 4.11
```

---

## Applied (2026-10-01, docs-only pass)

Edits applied to the memos per the recommendations above. Nothing in the DB or code was
touched. Every original claim is kept with a dated italic update note unless the review said
"correct", in which case the text was changed and the correction noted in place.

- `findings-synthesis.md`: through-line event count corrected to the live build with the
  three-build trail (H2); Part I "FIXED at the root" softened to the exact-title class fixed,
  containment class persists, 提振消费 regression being corrected (H1); Part III joint paragraph
  rewritten to one canonical by-period sentence with pooled 34% and the all-docs denominator
  caveat, 13,370 → 13,004, 15x → 13x, "cascade wider" → "echoed more often and sooner" (M1, M3,
  L4); 833 annotated as pre-fix (§3); L8 convergence sentence and M8 base note added to Part
  III; Status corrected to all landed + open items (M5); standing caveats: resolution ~52-54%,
  npc comparability line (M7), lag-definition line (L1).
- `citation-network-structure.md`: §0 Artifacts and §7 "citation_rank uncorrected" annotated
  as superseded (M4); §1.3 note softened to partial fix with the three persisting strings and
  the regression (H1); §1.1 npc comparability note (M7); §7 scope-boundary line (§2); appendix
  label annotated.
- `joint-issuance.md`: §1 annotated 13,370 → 13,004 live, title 10,304 moved by ≤396, npc note
  (M4, M7); §5 build/base note incl. topic_genre vs confirmed-only base (H2, M3); §5c "mostly
  two- and three-signer" corrected to 295 / 222 / 68 (M3); §6a error (1) and §7 Next (1)/(3)
  annotated done (M4); §6e scope-boundary line (§2).
- `ai-regulatory-web.md`: Table 1 2017-plan row 20 → 31 with a note that the per-site split
  is the original 20-sum pull (M2); §0 and §7 "~85-90%" → 110 of 118 (~93%); §5 "20 central
  citers" annotated.
- `ai-plus-fidelity.md`: §3.3 no-level-gradient annotated against the corpus-wide gradient (M6);
  §4 "bimodal gap is real" annotated (M4).
- `ai-governance-diffusion.md`: §2 mirror-gotcha example annotated as removed by the resolver
  fix (L6); §7 no-level-gradient annotated (M6).
- `diffusion-atlas.md`: §1 build note (28,880 first build, trail to 32,825, npc rule) (H2, M7);
  §0.4, §6 and §10 co-signature claims annotated with the joint §5c pointer and the base
  difference (M3).
- `experimentation-wang-yang.md`: header build note (H2, M7); "all 24,599 anchors" corrected to
  2,943 anchors / 24,599 events (H2); §6 scope-boundary line (§2).
- `industrial-policy-targeting.md`: §1 cascades build note covering the §5 table, npc note
  (H2, M7); §7 resolution floor, publication caveat and scope-boundary lines (§2).
- `diffusion-fidelity.md`: §0 build note (H2); §6 "no provincial anchors" annotated as
  superseded by `fidelity-provincial.md` and `c6dbe04`; coverage/resolution and scope-boundary
  lines (§2).
- `attention-campaigns.md`: header build note on `diffusion_events` and `citation_rank` anchors
  incl. the two moved anchor ids, npc note (H1, H2, M7); §4 resolution floor, publication caveat
  and scope-boundary lines (§2).
- `fidelity-provincial.md`: §1 6,670 annotated as pre-fix with the citation-network §1.3
  cross-reference and the inherited build (L7, H2); §7 scope-boundary line (§2).
- `recentralization-experimentation.md`: §1 universe npc note (M7); §4 scope-boundary line (§2).
- `consumption-diffusion.md`: §1 anchor identity annotated with the live post-fix state and the
  40-citer pool (H1); Table 2a annotated with the `sites`-join split 35/13/8/1/1 = 58 and the
  non-reproducible boost row (L5, H1); §5 resolution updated to 53.9% live (L2); scope-boundary
  line with the lag-definition note (§2, L1).
- `related-literature.md`: "~248k edges" → "~280k" in four places (L3); Outcomes citation-network
  row notes partial fix; Outcomes joint row carries the denominator caveat and "echoed more
  often" (M1, M3).
- `docs/working/autonomous-run-log.md`: it. 4 co-signature line, it. 9 13,370 / 15x line and
  it. 15 17.0→34.4 line annotated as different cuts of the canonical figures (M1, M3, L4).

Not applied: no data bug was filed and no numbers were recomputed (the review's H1 "file a data
bug" and the 提振消费 fix are the resolver agent's work, in progress); the `ai-regulatory-web.md`
Table 1 per-site split for the 2017 plan was not re-pulled (would need a DB read); L9 and L10
(cosmetic count differences) were left as is.

## Applied (2026-10-07, A4 correction)

- The "74 date-stamped sites" premise shared by `industrial-policy-targeting.md` §1,
  `corpus-lessons.md` A4 and `doc_identity.date_quality` was tested and failed: stored dates
  match page `PubDate` metadata on the flagged sites; the rule was detecting shallow archives.
  Both memos carry a dated correction; the identity rule was rewritten (bulk-crawl-day test),
  `crawl_stamped` is now 0 docs; the industrial exclusion is kept under its corrected label
  (archive depth). Lesson for the review method: a flag derived from a date DISTRIBUTION needs
  one hand-check against the page before it becomes a filter.

## Round 2 (2026-10-07)

*Same method as round 1, run over the six memos added or revised on 2026-10-06/07
(`fidelity-jiangsu.md`, `bottom-up-channel.md`, `pair-channels.md`, `policy-tempo.md`,
`site-selection-gdp.md`, `successor-detector.md`), the appended sections of
`industrial-policy-targeting.md` (R1-R7, L1-L6) and `fidelity-provincial.md` §2.2, the dated
updates in `findings-synthesis.md`, and the `corpus-lessons.md` A4 correction. Read-only; the
droplet DB was opened `?mode=ro` under `nice -n 19` while the nightly held the lock. Nothing was
recomputed and no number was deleted; fixes are dated parentheticals.*

### 0. Which identity build the live DB holds (2026-10-07 06:52 UTC)

Droplet HEAD `0210c2e` (the date-ordered `localized_of` + `province` code `80be9c1` is pulled
but Phase 2b has not run today; `instrument_kind` `890a25a` was pushed after the pull).
`doc_identity` columns: `doc_id admin_level_doc level_source instrument_id instrument_role genre
date_quality lead_issuer localized_of`, **no `province`, no `instrument_kind`**.
`SELECT COUNT(*) FROM doc_identity WHERE localized_of IS NOT NULL` = **2,592** (the 2026-10-06
build; the date-ordered 1,958 is not live yet). `date_quality`: good 313,981 / missing 9,548 /
crawl_stamped absent. So every memo that says "measured on the 2026-10-06 build, 2,592 rows,
pre-A6 schema" is describing the build that is still live.

Spot checks (10), live vs memo:

| quantity | live | memo | status |
|---|---|---|---|
| documents | 323,529 | 323,529 (policy-tempo); 321,230 (bottom-up, 10-06) | ok, dated |
| `diffusion_events` rows | 36,116 | 36,116 (policy-tempo); 35,475 (industrial R6); 33,992 (synthesis "final 10-01") | ok with scope notes (M1) |
| strict implementing central subset | 13,081 | 13,081 (policy-tempo) | ok |
| `tracker_weekly` rows | 45,151 | 45,151 | ok |
| citations total / resolved | 534,722 / 270,211 = 50.5% | 269,685 (synthesis); "~52%" in 3 new memos; "52-54%" synthesis caveat | **stale (M3)** |
| bottom-up central population | 37,036 | 37,022 | ok (+14 nightly drift) |
| `genre='implementing'` by level | 9,162 / 6,755 / 644 | 9,224 / 7,487 / 628 (bottom-up §1) | build drift, annotated (L4) |
| successor universe, central promulgation good-dated | 36,902 | 35,027 | **pre-A4-correction build (M6)** |
| Suzhou docs on 2023-02-09 / 2025-02-11; on day 01 | 1 / 7; 685 | 1,989 / 1,727 (jiangsu, as day counts); 685 (run log) | redate landed; memo's counts are year counts (M2) |
| Suzhou-sourced events | 1,406 | 1,406 (run log it. 23); 171 affected lags (jiangsu, pre-redate) | ok |

### 1. Findings

**HIGH**

**H1. `findings-synthesis.md` "Status and what remains" was two days stale.** It still listed the
提振消费 regression as "fix in progress" (closed by the 33,992-event build the same memo describes
two sections earlier), npc re-leveling in `sites` as open (landed as `doc_identity.admin_level_doc`,
not in `sites`), and none of the identity layer, A4 correction, Suzhou redate, B1-B7 memos,
`pair-channels.md`, or the industrial re-basing. **Corrected** with a dated status paragraph that
also records what is committed but not yet in the live identity build.

**H2. The Suzhou date story is told three ways and the synthesis carries the first.**
`fidelity-jiangsu.md` §0/§9 and the synthesis Part II update: "crawl-stamped in two batches that
the A4 rule does not catch; re-dated from the URL path; 171 affected lags". What landed
(`5465b8e`/`247c5f7`, run log it. 23): the piles are the source CMS's page-regeneration stamps,
not our crawl day; the A4 rule now sums bulk date-days; the DB was redated article-header →
发文日期 → URL month (3,354 rows); and the `/YYYYMM/` folder is a 2021 migration artefact for ~250
historical 规范性文件, so the memo's URL-only repair mis-dates that subset. Downstream, the Jiangsu
province-to-city citation basis on the redated DB is **473 pairs / 426 scored, relay 3.3%**
(`fidelity-provincial.md` §2.2) against the **191-200 / 8.0-8.4%** the synthesis quotes from
`fidelity-jiangsu.md` §4 and `fidelity-provincial.md` §2.1. The 14 relays are identical on both
bases, so the share fell because the repair pulled hundreds of long-lag Suzhou pairs into range
(456 of 473 are Suzhou, median lag 777 d), a denominator effect, not a different Suzhou practice.
**Annotated** in the synthesis, `fidelity-jiangsu.md` §0/§1/§9 and `fidelity-provincial.md` §7;
the §2.1 Jiangsu row re-read stays queued (needs a run, not an edit).

**MEDIUM**

**M1. `diffusion_events` now has five quoted sizes.** 32,825 (10-01 annotations), 33,992
(synthesis "final 10-01"), 35,475 (industrial R6, "2026-10-07"), 36,116 (policy-tempo,
"2026-10-07"), 35,465 / 35,498 (run log). R6 and policy-tempo are both dated 10-07 but are
different builds (the 10-06 nightly vs after the Suzhou redate). **Annotated** the trail in the
synthesis and R6.

**M2. `fidelity-jiangsu.md` labels year counts as day counts.** "1,989 documents carry
2023-02-09 and 1,727 carry 2025-02-11" come from the Appendix A query, which groups by
`substr(date_published,1,4)`; the day piles were 1,860 / 1,499 (run log it. 18). Also "3,661
moved by more than 60 days" (memo, URL repair) vs 3,354 redated (DB). **Annotated** in §0 and §9.

**M3. Resolution rate.** Synthesis standing caveat "~52-54%" and `fidelity-jiangsu.md`,
`policy-tempo.md`, `successor-detector.md` "~52%"; the synthesis's own update paragraph gives
269,685 resolved (50.6%) and live is 50.5%. The containment gate lowered the rate by un-resolving
wrong proxies, so the lower figure is the honest one. **Annotated** the synthesis caveat; the three
new memos' "~52%" left in place (direction unaffected, the synthesis note covers them).

**M4. "The citation graph sees fewer than half" survived in three places without the body
caveat** (synthesis Part II update, `fidelity-jiangsu.md` §0 and §8 finding 6) after
`pair-channels.md` §3 and the §7 re-base showed it counts metadata-only sources; conditioned on a
body the invisible share is 25.5% / 23.1%. **Annotated** all three.

**M5. "92% of it is exhortation" (synthesis) is stronger than the memo's measurement.**
`bottom-up-channel.md` §2 measures the forward-looking "exhort" window at about half of hits;
92% is the share that names no locality. The memo's own §0 summary ("92% generic instruction")
invited the slip. **Annotated** both.

**M6. `successor-detector.md` ran on the pre-A4-correction identity build.** Its universe
(35,027 central promulgations with `date_quality='good'`) excluded the ~29k docs then flagged
`crawl_stamped`; live the same filter admits 36,902 (+1,875, almost all 2026 and so mid-flight).
Not re-run. **Annotated** §1.

**M7. "Department tier is the weak tier" is a conflation.** `corpus-lessons.md` A7 ("department
tier at 60% vs 84%"), `diffusion-fidelity.md` §6, `fidelity-provincial.md` §7 (73%), and
`fidelity-jiangsu.md` Table 2a (37.5%) all measure the share with a body OVER 500 characters;
the A7 backfill measured 88.8% of bureau documents with SOME body and found "its gap is not
selectors" (short notices, attachments). The recoverable-body gap is MIIT (anti-bot stubs).
**Annotated** A7 and both fidelity bullets.

**M8. The 1.5 tilt reading and the department tilts survive in `industrial-policy-targeting.md`
§4, §4.1, §6 and §7 without a pointer** to R4-R5 / L1-L6, which replace the 1.5 line with a pool
z-rule, flip agriculture / "AI evenly spread" / "equipment municipal 1.49", and declare every
department tilt undecidable at document level. The §7 "Date stamps" bullet still says
"crawl-date stamping", and the §1 build note still says "74 date-stamped sites" (the 10-07 re-run
selects 77 / 28,940). **Annotated** each in place.

**M9. `related-literature.md` Outcomes rows for Wang/Yang, Fang/Li/Lu and fidelity predate the
B-series memos** (no 5.9% / 6.9%, no site selection, no Jiangsu, no level re-basing); and
`experimentation-wang-yang.md` §3b and bottom line still present 0.4-1.2% with no pointer to the
successor detector. **Annotated** both.

**M10. `corpus-lessons.md` Part B reads as seven open asks** though each now has a memo, and its
B2 line repeats "reverse flow nearly invisible" without the prose/citation split. **Annotated**
with a dated status paragraph.

**LOW**

**L1. Jiangsu province-to-city pair counts.** 200 (provincial §2.1), 199 / 191 (jiangsu §4,
all tiers / city), 174 / 177 scored (pair-channels §5, citation / union), 473 / 426 (provincial
§2.2 re-base). Each is labelled with its layer and date; the 473 is H2's case. No edit beyond H2.

**L2. Guangdong renamed re-issuances 381 → 377 → 398** (provincial §2.2 original / citation
basis on `pairs.py` / union), quoted as 381 in `pair-channels.md` §5 and `fidelity-jiangsu.md` §7
point 3, 377 → 398 in §7's re-base. All three state the basis. No edit.

**L3. Central-share figures under site vs document level.** 31.7 / 31.8 (site, §4 / R4), 22.3
(document, R5 / L1), 39 / 45 / 26 by period (site, §4.1), 27 / 30 / 19 (document, L5). All in one
memo and labelled; the synthesis quotes none. Covered by M8's pointers.

**L4. Build drift in `bottom-up-channel.md` §1** (implementing 9,224 / 7,487 / 628 → live 9,162
/ 6,755 / 644 after the genre-flip tightening). Annotated.

**L5. Three pilot universes:** 1,592 docs / 1,296 themes (experimentation, `sites.admin_level`),
1,539 rows / 1,261 titles (site-selection, npc excluded), 1,490 docs / 1,271 instruments
(successor, `doc_identity`). Each memo states its rule. No edit.

**L6. "Reverse flow" means downward in `recentralization-experimentation.md` §1 and upward in
the synthesis and `bottom-up-channel.md`.** Annotated the recentralization sentence.

**L7. Round 1's own §4 note "industrial excludes 74 date-stamped sites" and the M7 universe
line are now stale wording**; left as the record of round 1, superseded by the A4 Applied entry
and this round.

**L8. `localized_of` 2,592 vs 1,958** is consistently scoped everywhere it appears (provincial
§2.2, jiangsu §7, pair-channels §1, CLAUDE.md) and the live DB confirms 2,592. No edit.

### 2. Synthesis traceability, new claims only

| synthesis claim | memo | traces? |
|---|---|---|
| lexicon 2-3% → 17-19% peak; 296 (0.8%); 79 titles; 0.31% vs 0.24%; Spearman 0.664; 62.5%; 1,427 feedback docs | bottom-up §0-§4 | yes; "92% exhortation" overstated (M5) |
| 458 weeks; 67% province-first; 3.4x / 1.9x; 9% at 12 weeks, 41% at a year; 1 of 90 pairs | policy-tempo §0, §4-§5 | yes (8.8% rounded; "1 of 90" is the memo's reading of 6 at p<.05 vs 4.5 expected) |
| Jiangsu 82.1% of 39; GD 65.1% / 78.5%; 0.125 / 8.4% / 26.2%; rho −0.51 / −0.49; 14 of 16 at 160 d; 89.9% / 94.0%; 1.4%; 1/15, 1/29; 80-82% | fidelity-jiangsu §0, §3-§8 | yes; "fewer than half" (M4) and the Suzhou story (H2) annotated |
| 77.6% of 737; random 41%; 0.705; 0.625; 55% on 38%; 批复 0.60 vs 0.73 | site-selection §3-§4 | yes |
| 5.9% / 6.9%; 8-9.5% trials; 564 d; 76-87%; 40 / 23 / 20 / 7%; 9 of 12 | successor §0-§4 | yes |
| 74 shallow-archive sites; HHI within 2 pts; MIIT sectors +5-19 central; agriculture flips; AI withdrawn | industrial R1-R7, L3-L6 | yes; 77 sites on the re-run, new materials +4 (annotated) |

No new synthesis claim is unsupported. One is overstated (M5), one is stale (H1), one carries a
superseded corpus story (H2).

### Applied (2026-10-07, docs-only)

- `findings-synthesis.md`: "92% exhortation" tightened (M5); `diffusion_events` build trail to
  36,116 (M1); "fewer than half" body caveat (M4); Suzhou story superseded + Jiangsu 473 / 3.3%
  caveat (H2); 74 → 77 sites note (M8); resolution 50.5% live (M3); dated status paragraph (H1).
- `fidelity-jiangsu.md`: §0 body caveat (M4); §0 and §9 Suzhou correction incl. year-vs-day counts
  and the URL-folder artefact (H2, M2); §1 date-repair note with the 473 / 3.3% basis (H2); §8
  finding 6 (M4).
- `corpus-lessons.md`: "date-stamped site drops" sic note; A7 correction (M7); Part B status
  paragraph incl. the B2 prose/citation split (M10).
- `industrial-policy-targeting.md`: §1 build note (77 sites, L1-L6 pointer); §4 re-basing pointer;
  §4.1 L5 pointer; §6 department-tilt note; §7 date-stamps correction; R6 build scope (M1, M8).
- `diffusion-fidelity.md` §6 and `fidelity-provincial.md` §7: body-coverage conflation (M7);
  `fidelity-provincial.md` §7 Jiangsu 200 → 473 pointer (H2).
- `related-literature.md`: Wang/Yang, fidelity and Fang/Li/Lu rows carry the B-series results (M9).
- `experimentation-wang-yang.md` §3b and bottom line: successor / site-selection pointers (M9).
- `recentralization-experimentation.md` §1: "reverse flow" terminology note (L6).
- `successor-detector.md` §1: pre-A4-correction build note (M6).
- `bottom-up-channel.md`: §0 "92%" clarified (M5); §1 live counts (L4).

Not applied: no re-run of the Jiangsu §2.1 row or the successor universe (both need a compute
pass, queued); the three new memos' "~52%" left as is; round 1's stale wording (L7) left as the
record; `docs/working/*` (untracked) untouched; CLAUDE.md, `daily_sync.sh` and code untouched.
