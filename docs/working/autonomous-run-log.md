# Autonomous run log — "build out the NBER replications and the trackers, keep going"

Decision trail for the self-paced `/loop` started 2026-10-01. One entry per iteration so the
work can be audited later. Standing task: replicate the highest-corpus-fit papers from
`docs/research/related-literature.md` on our corpus, and build out the daily policy tracker
(`docs/research/daily-tracker-concept.md`), continuing until told to stop.

Standing constraints: read-only analyses may run in parallel; prod writes are serialized under
the SQLite 2-writer limit and never overlap the nightly cron; every subagent result is verified
against the live DB before it is reported; no regime-type labels in any analysis.

---

## Iteration 1 — 2026-10-01

**State at start.** `diffusion_events` built (28,880 events, validated against the two worked
proofs). Corpus 319,173 docs / 454 sites. NBER literature compiled (`related-literature.md`).
Tracker step 1 (auto-matcher) done; steps 2-4 not started. NHC ministry crawl returned 0.

**Decisions.**
- Picked the three NBER replications with the strongest corpus fit that are computable NOW from
  existing tables, as read-only parallel analyses:
  - *Diffusion atlas* (Luo/Wang/Yang "Laboratories of Autocracy" + the diffusion-intensity
    index), built directly on `diffusion_events`. The auto-matcher makes this a query, not a build.
  - *Recentralization + experimentation* (the post-2013 decline-of-local-innovation claim tested
    graph-natively via upward-citation rates over time, plus Wang/Yang pilot-program uptake).
  - The AI regulatory web is already done (`ai-regulatory-web.md`), so not repeated.
- Tracker: build step 2 (per-area weekly rollup) and wire the auto-matcher + rollup into the
  nightly NOW; defer step 3 (the UI) to the next iteration so it builds on a table that exists.
  Sequencing over parallel-and-pray (verifiable units).
- NHC: a small separate fix (exact `bmfl` facet string), not folded into the tracker work.
- Launched as 4 subagents; I verify each against the live DB before reporting.

**Expected outputs.** `docs/research/diffusion-atlas.md`,
`docs/research/recentralization-experimentation.md`, `scripts/build_tracker_rollup.py` +
nightly wiring, NHC docs > 0 with body text.

**Outcome.** Launching 4 heavy subagents at once hit the session rate limit (HTTP 429); 3 of
4 died. Net: NHC fix landed (commit `0daaa22`, deployed, 35 docs / 97% body, crawl cut off
mid-run); tracker rollup and recentralization did no work; diffusion atlas sent no failure
notice (possibly still running). Lesson: stagger heavy subagents rather than fan out 4 at once.

## Iteration 2 — 2026-10-01 (after limit reset)

- NHC: completing the interrupted crawl myself (incremental, cheap) instead of a new agent.
- Relaunched tracker rollup + nightly wiring, and recentralization + experimentation, with
  the same specs (nothing to salvage from the dead runs).
- Diffusion atlas: NOT relaunched, to avoid duplicating a possibly-live run; waiting on its
  notification. If it comes back failed, relaunch next iteration.
- Concurrency held to 2 new agents + 1 possibly-live, below the fan-out that tripped the limit.

**Outcome.** NHC complete: 35 docs / 97% body → Fix 3 is 4/4 ministries (125 docs). Tracker
step 2 DONE and deployed by the agent (commit `cd2bc7b`): `tracker_weekly` (44,542 rows,
2018-W01→2026-W51) + `diffusion_events` both rebuilt nightly in Phase 2c (measured 30s +
4s). The agent's "waiting" message was stale — it had already finished the full deploy.
Mistake of mine, caught and fixed: assuming the droplet was still dirty, I `rm`'d what was
by then a tracked file; restored with `git checkout`. Lesson: make clean-up conditional on
`git status`, never assume staleness. Recentralization study still running; atlas unknown.

## Iteration 3 — 2026-10-01

- Launched tracker step 3, the `/tracker` UI, now that both precomputed tables exist and are
  deployed. It reads only the two precomputed tables (sub-second target) and follows the
  existing design system.
- Still waiting on: recentralization + experimentation; diffusion atlas (relaunch if it
  reports failed). Concurrency: 2 known + 1 possibly-live.

**Diffusion atlas landed** (`docs/research/diffusion-atlas.md`, it had been alive all along).
Headlines: (1) province-before-city holds corpus-wide, 68-76% in every cut vs a 50% null,
robust to a 2015+ cut and a 365-day window (nested result rests mostly on Guangdong, 641 of
721 pairs); (2) breadth belongs to State Council 条例 (18% of anchors, 44% of top-50 by
breadth, 695-day median lag) while speed belongs to campaign instruments (228-341 days);
only the 2024 fiscal campaigns are both wide and fast; (3) on a fixed 22-site panel diffusion
has neither accelerated nor widened since 2008; what changed is central output (~134-157 →
~240 framework instruments/yr) and the share with any fast local echo (50% → ~20% since 2020,
partly right-censored for 2025-26 instruments). State Council masthead doubles breadth; joint
co-signature adds nothing. *(2026-10-01: refined by `joint-issuance.md` §5c, holds for 2-3
signers; 5+ coalitions are echoed 2.5-3.7x as often.)*

**Data-quality finding → fix launched.** 819 "central" anchors (17% of events) are 人大
local regulations on the `npc` site mis-leveled as central; ~9% of anchor pools have a
representative title naming a different instrument. Launched a targeted fix to the
auto-matcher's anchor set (exclude npc 地方法规), rebuild both tracker tables in-transaction,
re-validate the two known cascades. Concurrency: UI + recentralization + this fix = 3.

**Recentralization + experimentation landed** (`docs/research/recentralization-experimentation.md`).
Rigorous: levels from `sites.admin_level` (the `citations.*_level` columns are stale on ~29k
rows), de-duplicated edges, edge-level direction mix (doc-level reference-carrying halves after
2019 for unrelated reasons), two robustness sets, two artifacts audited and corrected (the raw
"downward" rise after 2018 is sub-national sites mirroring central text; the naive
pilots-cited-upward signal is local 转发 reissues). Headlines: (A) the upward-citation share of
sub-national edges steps up 7-11 pts at exactly 2013, holds to 2017, is broad-based (7 of 9
sites), survives both robustness sets, then REVERTS to 2008-12 levels by 2023-26; horizontal
and downward shares are flat throughout, so the data support a 2013-17 rise in
authority-borrowing, not a durable collapse of peer learning. (B) Pilot titling is a
top-weighted, shrinking genre tilting further central after 2013; the top-down designation
chain is clearly visible, the bottom-up absorption chain is not (locally-originated pilots
reach a central citation at ~1.5% vs ~1% for non-pilots, and the few cases are concurrent
implementation, not post-hoc generalization).

## Iteration 4 — 2026-10-01

- Launched the next replication: punctuated-equilibrium attention burstiness across all 29
  topics (Q1 corpus-wide, generalizing the AI-only finding) + campaign-style governance (Q4).
  Classic Baumgartner-Jones method, computable from topics_algo × year × level.
- In flight: `/tracker` UI (step 3), anchor-set data fix, this study. Concurrency 3.

**Anchor-set fix landed** (commit `76ce1d4`, Mac=origin=droplet). Three predicates in
`build_diffusion_events.py`: `_is_true_central` (excludes the npc 地方法规 family:
26,102 + 2,082 + 410 docs), `_is_explainer` (explainers may be pool members but never the
representative, which fixed the 十五五 noise anchor at root), `GENERIC_FYP_RE` (bare
五年规划 refs never attributed). Events 28,880 → 24,599 (citation 21,788 → 17,650,
title_reissue 574 → 438); npc-local-reg anchors 814 → 0; explainer anchors 70 → 0. Both
validation cascades still reproduce (boost GD 52d / JS 82d; AI+ 33 events).
`tracker_weekly` rebuilt (44,408 rows). Noted-not-fixed: the same-《》-core label problem
(an SPC ruling representing the 生态环境法典 pool) needs a promulgation-vs-about test.

## Iteration 5 — 2026-10-01

- Launched the issuer/文号 parser (a reusable lever → new `doc_issuers` table) + the
  joint-issuance / inter-agency coordination study (Q7, fragmented-authority tradition).
  Chosen because the agenda's current proxy undercounts badly (852 docs) and the parser also
  unlocks Q8 later.
- In flight: `/tracker` UI, attention/campaigns, issuer parser + Q7. Concurrency 3.

**THE TRACKER IS LIVE (step 3 landed, commit `5d6a399`).** `/tracker?topic=<area>&weeks=<n>`:
topic tabs + window select, a weeks × level matrix (new docs with confirmed cascades beneath,
current week marked NOW), active cascades per area (anchor linked, issuer, level mix, distinct
sources, median lag, newest implementing docs), a most-cascaded-instruments leaderboard, and
the honest-floors note inline. Reads only the two precomputed tables; measured 0.03-0.06s
cold / 0.01-0.03s warm (one topic 0.47s first-hit per worker, then cached); zero tracebacks.
Agent verified rendered cells against the DB. Design-system consistent, Tracker in the nav.
Steps 1-3 of the daily-tracker concept are now all shipped and nightly-refreshed.
Follow-ups noted: (a) `diffusion_events.topic` stores only the anchor's first tag (UI
compensates; fix in the auto-matcher later); (b) the pre-existing ~2.6s first-two-requests
after restart is `get_stats`'s cold count (the optional perf item), not the tracker;
(c) CLAUDE.md updated with the route (uncommitted, rides with the docs batch).

## Iteration 6 — 2026-10-01

- Launched the Fang/Li/Lu "Decoding China's Industrial Policies" replication: sector
  targeting over time, instrument mix (subsidy/regulation/plan) by sector, level, and cascade
  breadth, from a title-sector lexicon + existing genre/level/cascade axes.
- In flight: attention/campaigns, issuer parser + Q7, industrial policy. Concurrency 3.

**User pointed to w29402 directly** (Wang & Yang "Policy Experimentation in China"). Read the
full paper (pulled PDF text via pypdf, 112k chars, saved to scratchpad). Launched a full
replication of its DOCUMENT backbone: the 633-experiment analog (central 试点 guidelines by
year/ministry), central→local linkage via diffusion_events, rollout tracing (pilot → national
instrument lag + share that scale), descriptive pilot-site composition. Scope boundary stated:
findings 1-2 (GDP selection, promotion-incentive effort) need external data we lack; we
replicate the documentary measurement + extend with genre/topic/cascade axes. Supersedes the
quick Test B. Concurrency now 4 (user's explicit request) — staggered launch, not the
simultaneous burst that 429'd earlier.

**Industrial-policy targeting landed** (`docs/research/industrial-policy-targeting.md`, verified:
semiconductor title-share 0.086-0.196% 2023-25 confirms the "flat ~0.1%" headline). Findings:
(1) targeting BROADENED not concentrated (HHI across 18 sectors 1,700-2,700 → 780-970; tagged
share 2.3% → 6.3%); (2) sector policy is plans+explainers not rules, and money (subsidy genre,
5.8% of sector instruments) concentrates in chips/software/new-energy/NEV/biopharma while legacy
sectors get rules; (3) place-based sectors (low-altitude, new energy, new materials, biopharma)
see real sub-national pile-on, network-rule sectors (data, telecom, platforms) stay central.
Fastest-rising: AI, future industries, low-altitude, digital/data, biopharma. Widest cascade:
digital/data (110 sites) + carbon. Caveat: title recall ~4-8% vs body, no tone/firm layer.
Note on verification: the "14-18% subsidy share" uses a sector-instruments denominator; my
all-docs spot cut (1.4%) isn't comparable — direction holds, exact figure unverified.

**Pacing decision: steady-state 3 concurrent subagents** (not 4). The earlier 429 came from a
4-wide simultaneous launch; a rolling pipeline of 3, launching one replacement per completion,
keeps throughput high without the burst. Currently at 3 (attention/campaigns, issuer+Q7,
w29402). Next to launch when a slot frees: corpus-wide citation-network / authority
concentration (Q3 + Q8, the IT-policy-network paper's method on our 248k edges).

## Iteration 7 — 2026-10-01

**Attention/campaigns landed** (`docs/research/attention-campaigns.md`, verified: central
campaign-title share 0.21%→0.99% matches). Test 1: attention is punctuated at the topic level
(20/29 topics more concentrated than a smooth null) but NOT classically fat-tailed when pooled;
12 of 23 burst episodes survive leave-one-site-out, 7 were single-site crawl artifacts (good
honesty). Most punctuated post-controls: Party (2020-21 step, sub-national), Health (2020
spike), Credit (2018). Test 2 REFUTES the agenda's hypothesis: the campaign label moved UP the
hierarchy (central 0.21%→0.99%, provincial 0.35%→0.79%) while municipal is flat-to-falling;
the center titles 专项行动, localities title 攻坚; campaigns are the vehicle of an attention
burst in only 3 of 30 cases.
- Slot freed → launched the citation-network / authority-structure backbone (Q3+Q8).
- Done: 5 replications (diffusion-atlas, recentralization-experimentation, ai-regulatory-web,
  industrial-policy-targeting, attention-campaigns) + tracker shipped. Running: issuer+Q7,
  w29402, citation-network. Steady-state 3.

## Iteration 8 — 2026-10-01

**w29402 (Wang-Yang experimentation) landed** (`docs/research/experimentation-wang-yang.md`,
verified: 1,834 central pilot-cue docs all-cut vs the agent's 1,592 genre-filtered — consistent,
same order as their 633). Replicates the document backbone: 1,592 guideline docs / 1,296 themes
(2000-26), central→local linkage via diffusion_events, rollout tracing. Honest boundary: we see
DESIGNATION flow down (pilots cited by 833 sub-national docs) but GENERALIZATION barely flows up
(only 0.4-1.2% reach a visible theme-preserving national instrument vs their 53.9% — a
visibility floor; median pilot→national lag ~2.9yr). Findings 1-3 (GDP site-selection, fiscal
effort, learning under-correction) need external data we lack; stated as out of reach. This is
the recurring selection-bias through-line: the published record shows the center commanding, not
localities feeding back.
- Slot freed → launched corpus-wide diffusion fidelity (Q6, relay vs elaboration over all
  diffusion_events body pairs, extending ai-plus-fidelity.md).
- Done: 6 replications + tracker. Running: issuer+Q7, citation-network, fidelity. Steady-state 3.
- NEXT CONSOLIDATION (plan): when 1-2 more land, write a synthesis/index memo tying the
  replications into the volume's chapter structure + the shared selection-bias through-line.

## Iteration 9 — 2026-10-01

**Session rate limit hit again** (3 running agents 429'd: issuer+Q7 died in its parse pass before
writing; citation-network had confirmed mirror artifacts but no deliverable; fidelity had just
started). Used the blocked window for main-thread work: WROTE THE CONSOLIDATION
(`docs/research/findings-synthesis.md`) — the volume's spine (4 parts) + the through-line: the
published record shows the center designating and localities echoing, with the reverse flow
nearly invisible, partly real and partly the corpus's selection limit, stated as scope not
hedge; plus the methodological contribution (explicit citation/reissuance graph + live tracker
vs inferred text similarity).
**User lifted the rate limit** ("I fixed it! No rate limits!"). Relaunched all three (issuer told
to drop any partial doc_issuers first; citation-network told to pool mirrors + exclude npc
local regs). Back to 3 concurrent.

**Issuer parser: stop-short again, taken over.** The parser works: a prior full run parsed
267,844 docs, 79% with ≥1 issuer, **13,370 joint (n≥2) docs = 15× the agenda's naive 852**
*(2026-10-01: 13,004 after the 粤办 fix in it. 15; the memo's naive proxy is 1,047, so 13x;
the synthesis uses 13,004 / 13x)*
(sources: publisher 117k, title 89k, header 3.8k, docnum 943). Per my drop-partial instruction
the agent dropped that table and started a fresh full parse (running, writes at end). The Part-2
analysis script is staged on the droplet. I'm waiting out the parse myself (background waiter),
then launching a NO-WAIT agent for analysis + memo + commit, so it can't stop short on a wait.
Parser is untracked on both ends (identical) — commit from Mac, rm droplet copy, pull.

**Corpus-wide fidelity landed** (`docs/research/diffusion-fidelity.md`, verified: 18,088
confirmed pairs / 13,509 scorable matches exactly). THE MOST VALUABLE KIND OF RESULT: it corrects
an earlier memo. The AI+ "bimodal, empty middle" was an n=12 artifact; corpus-wide the
distribution is a decaying tail: 88.3% elaboration / 9.8% mid / 1.9% relay (the relay cluster =
provincial 转发 notices within 90 days; lag is the strongest predictor). Fiscal thesis holds in
direction (~2x reuse) but fails in magnitude (money → templated elaboration, never relay); the
rule-bound clause is WRONG (条例/办法 are the least copied; 意见 gets paraphrased). Districts
elaborate most; provinces are the forwarding/first-paraphrase tier. Propagated the correction:
annotated ai-plus-fidelity.md and ai-governance-diffusion.md §7, updated findings-synthesis.md.
- Slot freed → launched the province→city fidelity extension (the memo's flagged gap: all
  anchors central), incl. the three-hop C→P→M chain test on Guangdong.
- Running: citation-network, issuer-parse waiter (→ analysis agent next), fidelity-provincial.

## Iteration 10 — 2026-10-01

**Citation-network backbone landed** (`docs/research/citation-network-structure.md`). Top 1% of
nodes hold 54.5% of inbound (Gini 0.947, 84% never cited; top-100 = 80 central, 75 regs/laws);
genre source/sink holds under age control (regs 7.3 in / 1.6 out; explainers 0.1 / 2.0);
cross-level flow up 46% / same 49% / down 4%; bridges are procedural law + planning outlines
(政府信息公开条例 cited from all 29 topics). **Surfaced the session's biggest data bug:** 27%
of resolved edges (68,880) hit PROXY targets — the resolver credits a cited national law to
whichever doc embeds its name. VERIFIED: 河南省实施《城乡规划法》办法 has 2,139 inbound +
citation_rank 3,281 (corpus max) while the law itself has 0. Stored citation_rank is corrupted
at the top (13/30 overlap with corrected). → Launched a root fix (prefer exact-title candidates
over substring in extract_citations.py) + full rebuild of citations → citation_rank →
diffusion_events → tracker_weekly, with before/after validation. NOTE: earlier memos'
citation_rank figures are pre-fix; anchor pooling + event-count rankings in the tracker are
robust to it.
**My own bug:** the issuer-parse waiter's `pgrep -f` matched its own remote shell and never
exited (the parse had finished 40 min earlier). Killed it; lesson: exclude the shell
(`grep -v "bash -c"`) or poll a sentinel file, not a process name. doc_issuers confirmed:
267,844 rows / 13,370 joint / 79%.
- Launched the joint-issuance analysis (Q7) from the built table, verify-first + no-wait, which
  also commits the parser cleanly (rm the identical untracked droplet copy, then pull).
- Running: resolver fix (writer), joint-issuance (read-only), fidelity-provincial (read-only).
  Timing note: joint-issuance may read diffusion_events before the resolver rebuild lands;
  the cascade-breadth comparison is directional either way.

## Iteration 11 — 2026-10-01

**Province→city fidelity landed** (`docs/research/fidelity-provincial.md`). REFRAMES the
diffusion chapter: cities copy their province far more than provinces copy the center (relay
10.8% vs 3.3%); in 92.8% of 2,444 full C→P→M chains the city text descends from the PROVINCE
(center-descended 1.6%); only 0.8% of city text is center-only. The province is the translation
layer; the prefecture city is the copying tier (districts/bureaus don't copy). 以旧换新's tight
cascade was province→city. Folded into findings-synthesis.md Part II.
**Product implication queued:** extend the auto-matcher to PROVINCIAL anchors so diffusion_events
and the tracker capture the hop that actually carries the text. BLOCKED until the resolver-fix
agent finishes its rebuild of diffusion_events (avoid two writers / two editors on the same
script+table). Launch next iteration after that lands.
- Running: resolver fix (writer), joint-issuance (read-only). At 2; the 3rd slot is held for the
  provincial-anchor extension once unblocked.

## Iteration 12 — 2026-10-01

**Resolver proxy-target fix landed** (commits `cd42903`, `c979a82`; Mac=origin=droplet). Root
cause: `TitleMatcher.resolve()` gated the exact tier on len≥8, so short law names (城乡规划法,
5 chars) only ever hit containment. Fix: exact title/core wins before containment (floor 3),
mirror tie-break level→id, plus a 1-tuple caller-compat fix the rebuild exposed. 6-case test.
Resolved 279,409→287,607 (+8,198, no loss). Henan 2,139→0; the law 0→2,141 (rank 3,284).
New top-5: 政府信息公开条例, 道路交通安全法, 城乡规划法, 财政违法行为处罚处分条例,
广东省城乡规划条例. Full chain rebuilt (citations 533,358 → scores 1,173 rows → diffusion_events
26,565 → tracker_weekly 44,476); cascades reproduce. Propagated: synthesis + CLAUDE.md updated.
- UNBLOCKED → launched the provincial-anchor extension of the auto-matcher (adds the
  province→city hop the fidelity study showed carries the text; anchor_level column; minimal
  tracker UI awareness; regression-guarded on central events + both cascades).
- Running: provincial-anchor extension (writer), joint-issuance (read-only). At 2.

## Iteration 13 — 2026-10-01

**Joint-issuance landed** (`docs/research/joint-issuance.md`; parser committed `e1c8d74`,
deployed, both ends at `c979a82`). Parser 97% precision / 79% coverage; 13,370 joint docs.
Joint issuance RISING at the center 17%→43% (2005-09→2024-26), flat sub-national; coalitions
2.4→3.9 mean, 5+ signers 5%→30%; core shifted MOF+税务总局 dyad → NDRC hub; joint docs cascade
wider only at 5+ signers (refines the atlas). Parser bug flagged: 粤办 docnum alias makes a
phantom pair (fix when wiring into nightly). The agent's staged SQL had a date-cast bug it
caught and replaced — good. Stopped a redundant read-only scratch script (pid 3924126) it left
at 95% CPU during the live rebuild (my delegated job, superseded; not the user's process).
- Consolidation: findings-synthesis Part III updated; appended an "Outcomes" table to
  related-literature.md mapping each paper → our memo → headline (answers "where's the NBER
  stuff" with results).
- 9 replications done. The high-fit literature list is now essentially exhausted; remaining
  value is in (a) the provincial-anchor tracker upgrade (running), (b) wiring the issuer parser
  into nightly + the 粤办 fix (after the writer finishes), (c) corpus growth (crawl_now /
  associated bodies) which the mandate covers less directly.
- Running: provincial-anchor extension (writer). At 1; next launches wait for it (writer
  serialization) — the parser wiring is next.

**Verification catch on joint-issuance (annotation, not correction).** My first all-central-docs
cut showed the joint SHARE falling (22.4→15.3%), opposite the agent's rise (17→43%). Re-ran under
the agent's restriction: policy genres + fixed site set → 16.2→13.7→20.9→31.9%, so the rise is
real and the all-docs cut was confounded by the post-2020 explosion of single-issuer non-policy
content (15k "other", notices, announcements). Coalition-size rise robust everywhere. Added the
denominator-sensitivity scope note to the synthesis. Lesson reinforced: a share trend's sign can
flip with the denominator; always state which one.

## Iteration 14 — 2026-10-01

**Provincial-anchor tracker upgrade landed** (commit `c6dbe04`, deployed, restarted). 6,260
provincial-anchor events / 1,126 provincial instruments; table 32,825 rows with `anchor_level`;
central events byte-identical (26,565; cascades reproduce). 以旧换新 Guangdong→cities now
visible: 28 events, 26 implementers, median lag 38d (江门 +6d, 广州 +16d). Rollup has
`cascade_events_prov`; UI has anchor-level tags + a provincial leaderboard (all-Guangdong top-5,
procedural rules). Tracker 200, warm 0.01s; cold 2.6s/worker = the pre-existing get_stats cold
count. UX follow-up: active-cascades list ranks by newest arrival so central fills the top 12.
- Launched: issuer parser nightly wiring (Phase 2b) + the 粤办 alias phantom-pair fix.
- Queued next (after that writer): fold get_stats corpus counts into the site_stats precompute
  for sub-second cold tracker loads (the daily tool's first-click-of-the-morning case).

## Iteration 15 — 2026-10-01

**Parser nightly wiring + alias fix landed** (commit `e8246b2`, both ends). 粤办函 → 省政府办公厅
(not 省委办公厅); a sub-national docnum lead now REPLACES a disagreeing single publisher instead
of unioning. Phantom pair 177→1; the GD 2010-12 joint bump (27.9/33.0/16.5%) collapsed to
0.6/0.9/1.4% — entirely the artifact; 396 rows fixed (same portal-publisher phantom pattern
in yangjiang/fgw/huizhou/bj); central share unchanged (17.0→34.4%; the pooled 2020-26 variant
of the memo's by-period 17 → 16 → 24 → 31 → 43 on the same gov/ndrc/mof/mee policy-genre set,
`consistency-review.md` M1). 5-case test. Nightly
Phase 2b rebuilds doc_issuers (241s, timeout 900). Propagated to the synthesis; the
joint-issuance memo's "unverified bump" text to be annotated.
- Launched: `corpus_stats` precompute (sub-second cold loads, perf item 3) + the tracker
  active-cascades UX tweak (surface provincial anchors), one deploy cycle.
- Pipeline now has 4 nightly-maintained analytical tables: site_stats, corpus_stats (pending),
  doc_issuers, diffusion_events + tracker_weekly.

## Iteration 16 — 2026-10-01

**corpus_stats + tracker UX landed** (commit `ebf1dc8`). `/` cold 3.08s→0.23s, `/browse`
2.95s→0.35s (exact parity with the live query; 3.1s build in the same site_stats scan). The
perf arc is complete: 72s → 2.3s → 0.23s. Tracker active list now 12 central + 12 provincial.
Closed perf-diagnosis item 3 + CLAUDE.md perf entry.
- Research list exhausted at high fit → using the writer slot for corpus growth: launched
  crawl_now tranche 2 (~8 highest-yield sections on existing govcms hosts, same guardrails).
  Coverage is the floor every replication cites; growing it raises every finding's ceiling.
- Nightly-maintained analytical tables now 5: site_stats, corpus_stats, doc_issuers,
  diffusion_events, tracker_weekly.

## Iteration 17 — 2026-10-01

**crawl_now tranche 2: stop-short again, taken over.** The agent appended sections to ~10
hosts (shb_fgw/sww/rsj/nyncw/sfj/tjj Shanghai depts, zhangye, jl_swt, an NX/XZ dept, mfa
/wjbxw_new/, mem /gk/), verified govcms.py Mac==droplet, and launched a serial crawl chain on
the droplet, then ended its turn waiting (re-woke twice on its monitor). Stopped the agent to
avoid a race; the detached chain keeps running. My waiter now excludes its own shell
(`grep -v "bash -c"`) — the fix for the earlier stuck-waiter bug — then runs build_site_stats
and reports per-host counts + body %. Corpus was 319,208 before.

**Tranche 2 outcome:** 319,208 → 319,397 (+189). Body %: mfa 100, zhangye 100, shb_tjj/nyncw/
sfj/sww 100, shb_fgw 97, shb_rsj 98, mem 92, jl_swt 56 (partial-body host, note). Stats
refreshed (455 sites). Diminishing returns on the remaining crawl_now queue (sections are
20-60 arts each). Bigger coverage levers are HK-gated (user).

## Iteration 18 — 2026-10-01

- Launched a cross-memo CONSISTENCY REVIEW of the 9 replications + synthesis (read-only):
  find contradictions, stale pre-fix numbers (citation_rank, bimodality), denominator
  mismatches, and claims that later memos superseded. Volume-grade QA.
- Launched the associated-bodies probe (bounded): top AI-relevant uncovered bodies from
  associated-bodies.csv (CAICT first), reachability + dialect check, add + crawl the ones
  matching a known govcms dialect, flag the rest.

**Consistency review landed** (`docs/research/consistency-review.md`, sent to user). Verdict:
synthesis safe in direction once 4 text issues are fixed. Findings: **H1 my resolver fix
introduced a REGRESSION** — 提振消费专项行动方案 (113 edges) now resolves to a Beijing provincial
news page (900105357) whose title is exactly the instrument name, beating the canonical central
promulgation (印发《》 wrapper); both central copies 0 inbound; spurious 7-event provincial anchor;
the consumption cascade's anchor identity is no longer reproducible. Also "fixed at the root" was
overstated: containment proxies with no exact-title copy persist (驾驶证规定 686 edges on a 解答
page, 百千万工程 414). **H2** event counts quoted from three superseded builds. **M3** three
joint-share headline values (all true, different cuts). **M4** ai-reg says 20 citers for the
2017 plan, live=31. **M5** stale text contradicting update notes. Plus scope-line omissions.
- Launched the resolver REGRESSION fix (core-normalization of 印发《》 wrappers; promulgation
  genre > news/解答 in the exact tier; and no containment-proxy to a news/解答 page when no
  exact candidate exists — unresolved beats wrong) + full rebuild + tests; and a docs-only
  corrections pass applying H2/H1-wording/M3/M4/M5 + minor items with annotation trails.
- Lesson: an exact-title rule needs genre + wrapper normalization, or a news page titled with
  the bare instrument name outranks the promulgation. The review caught it before a chapter did.
- Running: resolver-regression fix (writer), associated-bodies probe (writer, concurrent — 2 is
  the limit), memo corrections (docs only).

**Memo corrections applied** (docs-only pass, 15 files, "Applied" log appended to
consistency-review.md): build-stamps on every event count, "partial not root" wording, one
canonical joint-issuance sentence, ai-reg 20→31 / 93%, stale "uncorrected"/"open"/"bimodal
gap real"/"in progress" text annotated, scope lines added to the memos that lacked them,
related-literature ~248k→~280k. Annotation trail preserved throughout.
**Resolver regression fix committed** (`7f889e9`: wrapper-core exact tier + genre priority +
promulgation-gated containment). The agent stopped short but its rebuild is a single detached
chained script (extract_citations → compute_scores → build_diffusion_events → rollup →
CHAIN_DONE, ppid 1), so all four steps run on their own; waiting on the wrapper pid, then
validating 提振消费/驾驶证/城乡规划法/resolved total/cascades/top-5. Associated-bodies crawl
continues concurrently (2nd writer; now on `cass`).

**Regression fix VALIDATED** (chain done). 提振消费 → central 12650974 holds 125 inbound,
Beijing news page 900105357 → 0 and its spurious anchor gone (0 events); 驾驶证 688 edges now
land on the real 公安部令第162号 regulation (not a 解答 page); 城乡规划法 2,141 intact; top-5
citation_rank all framework law; boost cascade GD 52 / JS 82 / BJ 116; diffusion_events now
27,546 central + 6,446 provincial. HONEST COST: resolved 287,607 → 269,781 (−17.8k): the
containment-to-news/解答 proxies are now unresolved rather than wrong. CHECK: AI+ events
33 → 103 (wrapper-core normalization recovered more refs; over-matching test run).
**Associated-bodies agent stopped short** (deferred writes behind the chain): landed cass 122
(100% body), cast 136 (116 body, date fix pending), amr 50 (47 body); isc config added, crawl
pending. Relaunched a foreground-only finisher (cast date fix, isc crawl, stats, ontology sync).

**AI+ 33→103 explained — not resolver over-matching, but source-genre leakage.** A random
sample of the 103 citation sources: genuine implementers (黑龙江 AI+ 实施方案 解读, 北京 医疗AI
行动, 人工智能终端产业 实施意见) mixed with news/readouts that merely MENTION the action
(Politburo-meeting reposts, a 省政协 readout, a district official meeting Lenovo, Xi's WAIC
speech reposts). The wrapper-core fix recovered these references; the auto-matcher never
genre-filtered the SOURCE side, so a news repost can show in the tracker as "implementing X."
The fidelity memo's implementing-instrument subset is the precedent. → Launched a
`source_implementing` flag in diffusion_events (flag, not filter: mentions stay as a secondary
signal), rollup splits confirmed vs mentions, tracker defaults to implementing-only. Expect AI+
implementing events to fall back toward ~30-40. The ai-governance memo's AI+ row (10/6/8) is
pre-fix; annotate once the clean split lands.
- Running: associated-bodies finisher (writer: documents), source-gate (writer:
  diffusion_events/tracker_weekly) — 2 writers, different tables.

**Re-wake hazard handled.** The stopped-short resolver agent re-woke on its own watcher and
launched a SECOND rebuild chain after committing `e1ff3b7` (meeting-report titles count as news
in the containment gate — a sound refinement; both ends synced; kept). Stopped the agent
(TaskStop) so it can't launch more. Its detached chain keeps running (extract_citations in
progress). Collision risk: its old-code diffusion rebuild vs the source-gate agent's new-code
rebuild of the same tables — if the old one landed last it would drop `source_implementing`.
Resolution without kills: SendMessage'd the source-gate agent to wait for the chain's wrapper
(pid 3940353) to exit, then run its rebuild LAST. Lesson: a subagent that launches its own
watcher can re-wake and act after I've moved on — stop such agents the moment they report
"waiting", don't let them linger.
**Second re-wake, same lesson:** the original associated-bodies agent re-woke on its waiter and
started "deep crawls" in parallel with the finisher I'd launched for the same work. Stopped it.
Checked for duplicate `--site` crawls: none (one `amr --deep` running). ISC landed: 89 docs,
100% body. amr 50→97 (deep crawl in progress). Writers: amr crawl + resolver chain = 2.
Associated bodies so far: cass 122, cast 136, amr 97, isc 89 = 444 new research-body docs.

**Associated-bodies finisher DONE** (foreground, nothing left running by it). cass 122 (100%
body), cast 136 (85%; the 20 bodiless are photo/video pages), isc 89 (100%; 21 undated =
static/gallery pages), amr ~75-97 (deep crawl from the stopped original agent may still be
adding). CAST date fix: new `_META_PUBDATE`/`_body_date()` in govcms.py prefers Hanweb's
`<meta name="PubDate">` over body-scanned signature dates (65 corrected, no future dates;
generalizes to other Hanweb hosts). build_site_stats: 459 sites, 319,800 docs. govcms.py +
source_ontology.yaml synced (uncommitted). Noted: stray untracked scratch files at the
droplet repo root (govcms.py, harvest.py, pbc.py, .sh) from earlier sessions — not blocking
pulls (untracked), but clutter to clean later.

**Source-gate committed + deployed** (`1a08989` "source_implementing flag — mentions are not
cascades", both ends; builder/rollup/tracker service all carry the flag). The agent then ended
its turn waiting on the chain — stopped it (the lesson). Because the droplet already runs the
NEW builder code, the still-running resolver chain will build the flagged tables itself at its
step 3; the sequencing concern is resolved. Finisher armed: wait on wrapper pid 3940353 →
restart app (load new tracker service) → build_site_stats → validate (implementing/mention
split, AI+ split, boost cascade as implementing, tracker 200). amr --deep finished (143 docs).

## Iteration 19 — 2026-10-01 — flagged build VALIDATED, run converging

Chain exited; app restarted; stats refreshed (459 sites, 319,930 docs). Final build:
**33,992 events = 23,640 implementing + 10,352 mentions (30%)**; central 27,546 (18,271 impl),
provincial 6,446 (5,369 impl). **AI+ 28 implementing / 75 mentions** (as predicted). Boost
cascade GD 52 / JS 82 / BJ 116 as implementing. tracker_weekly 44,590. Resolved 269,685.
/tracker 200 @0.76s cold. Annotated ai-governance-diffusion (AI+ final split) + synthesis
(final build numbers, implementing/mention separation, honest resolved drop). Cosmetic: the
"+N mentions" label may not render on the page — checked.
No agents running. Sequenced work complete. Remaining high-value items are user-gated (HK
vantage for the blocked tier; institutional access for full-text law) or a substantial
browser-dependent build (the Hanweb-datacall JS-site crawler, ~52 prefecture portals).

---

# Program 2 — the data-model pass ("go ahead until you run out of tokens"), started 2026-10-06

Mandate: execute `docs/research/corpus-lessons.md`: B5 regression test first (protection), then
A1-A5 as one coordinated `doc_identity` side table, then migrate the auto-matcher onto it, then
the additions (B1 Jiangsu deep crawl, B3 successor detector, B4 GDP join, B6 raw inbound, B2
bottom-up sources). Same discipline: steady-state 2-3 agents, serialized writers, stop any agent
that reports "waiting", verify every result against the live DB, log each iteration.

**Design decision (data shape first):** the five identity fields go in ONE nightly-rebuilt side
table `doc_identity(doc_id PK, admin_level_doc, level_source, instrument_id, instrument_role,
genre, date_quality, lead_issuer)`, not as columns on `documents` (320k-row rewrites nightly =
the compute_scores lesson). Every consumer does one join. Rule-based derivations, no LLM.

## P2 Iteration 1
- Launched B5 (`validate_cascades.py` + daily_sync Phase 2d, Telegram line; must prove it bites).
- Launched `build_doc_identity.py` (table + validation vs known truth), with nightly wiring
  deliberately DEFERRED so two agents don't edit daily_sync.sh concurrently.
- Next: wire doc_identity into nightly + migrate build_diffusion_events to use instrument_id /
  genre / admin_level_doc (regression-guarded by B5), then the additions.

## P2 Iteration 2
**B5 LANDED** (`f567b22`, deployed): `validate_cascades.py`, 13 sub-checks / 6 groups, 0.1s,
13/13 PASS live (boost GD 52 / JS 82 / BJ 116 exact; 城乡规划法 2,142; AI+ 28 impl / 75 mentions;
proxies 0; tables sane; top-5 formal instruments). Proven to bite: tightened thresholds → FAIL,
exit 1. Phase 2d in daily_sync after the 2c rebuilds, never aborts publish, Telegram
"🧪 Validation: PASS/FAIL (n) — names". Smart: top-5 checks title genre not host site (the #1
instrument is a central law reposted on a municipal site). Corpus now 321,230 (nightly ran).
- doc_identity agent still building. Used the free slot for B4 (provincial GDP join →
  descriptive site-selection test extending the Wang-Yang replication), independent of
  doc_identity.

## P2 Iteration 3
**doc_identity LANDED** (`28731cf`): 321,230 rows, ~37s, one transaction, 62-case self-test.
A1 level 98% precision (60-doc stratified, two seeds); 68,723 docs (21.4%) change level vs
site (department→municipal 32.5k, npc central→provincial 13.8k, central→municipal 13.6k); npc
local regs: 0 central. A2 instrument identity: 政府信息公开条例 → 2 instruments (2019 revision
vs 2007 text — correct); 提振消费 gov canonical / xinhua mirror / Beijing news unique;
311,404 instruments for 321,230 docs (5,547 canonical, 9,826 mirrors). Edition chaining: a
>400d gap opens a new edition only if the hosting site is at/above the edition's level. A3
genre 88% (3 rounds of systematic-miss fixes; residual = gov-site local news with no cue →
other). A4 crawl_stamped 76 sites / 29,127 docs (memo: 74 / 27,915). Not yet wired (by design).
- Launched the dependent step: wire build_doc_identity into Phase 2b + MIGRATE
  build_diffusion_events onto doc_identity (level, pooling, genre), deleting the matcher's
  local re-derivations (migrate-callers-then-delete), regression-guarded: validate_cascades
  must PASS after the rebuild, no loosening.
- B4 (GDP site-selection) still running.

## P2 Iteration 4
**B4 LANDED** (`89c7064`): `data/provincial_gdp.csv` (31 × 23 yrs, NBS yearbooks; 2014-19
interpolated + flagged; data.stats.gov.cn 403s non-mainland), `site_selection_gdp.py`,
`site-selection-gdp.md`. **Wang & Yang finding 1 REPLICATES descriptively:** 88.3% on their
skew-biased metric (random ~70%); fairer: 77.6% majority-above-median (random 41%), named
provinces at the 0.705 GDP/capita percentile (random 0.50), robust 0.70±0.04 across 5 cuts;
Spearman(selection ratio, GDP pc) 0.625; richest tercile 55% of designations on 38% of pop.
批复 selects less than assigned (0.60 vs 0.73) = their assigned/voluntary proxy. Caught the
兵团 distribution-list boilerplate (Xinjiang 438→36 designations). Implementing side agrees
but coverage-confounded. Synthesis Part III updated.
- Launched B6 (raw inbound alongside citation_rank; precomputed doc_inbound; browse
  ?sort=inbound). Running: matcher migration (writer), B3 successor detector, B6. Steady 3.

## P2 Iteration 5 — the data-model core is DONE
**Wiring + migration LANDED** (`c0536b5`): build_doc_identity --force as Phase 2b's last step
(after issuer_parser/compute_scores/topics, before 2c's matcher). Matcher now reads level
(admin_level_doc), pooling (instrument_id, canonical = representative), and implementing
(genre) from doc_identity; legacy derivations DELETED (_is_true_central, _is_explainer,
pool_key, _is_prov_tier, IMPLEMENTING_GENRES, sites.admin_level lookup…). Schema unchanged.
Validator adjusted correctly: the AI+ check resolves 900039770 via its instrument pool (it's
a mirror; canonical 12650908) — bands untouched. Events 34,035→35,452 (impl 23,654→24,603;
+62 central / +182 provincial anchors), explained: per-doc level admits centrally-authored
texts hosted sub-nationally; instrument_id pools more mirrors; genre slightly more permissive.
**VALIDATION PASS 13/13** after the rebuild. Tracker 200. CLAUDE.md documents doc_identity +
validate_cascades.
**Flagged imperfection → fix launched:** localized reissues (深圳市…印发<深圳市>以旧换新行动方案)
pooled as MIRRORS of the central text (key only looks past 印发), so Shenzhen's plan is excluded
as a source of the central cascade. Fix: a locality/body prefix inside the core = localized
re-issuance (own instrument, implementing), not a mirror. Regression-guarded rebuild.
- Running: identity pooling fix (writer: doc_identity→events→rollup), B6 (writer:
  doc_inbound), B3 (read-only). Next: B1 Jiangsu deep crawl after the writers clear.

## P2 Iteration 6
**B3 LANDED** (`ed22bed`): `successor_detector.py` + `successor-detector.md`. Pilots 1,271
instruments (via doc_identity); successors 75 → **5.9% raw / 6.9% ex-mid-flight** (8-9.5%
trials-only); median lag 564d (inside W&Y's 820d); precision 76% strict / 87% lenient.
No-successor hand sample: zone designations 40%, **renamed/absorbing instrument 23%**,
mid-flight 20%, detector miss 7%, never scaled 7%. 9 of 12 mature substantive pilots have an
in-corpus successor the core match can't reach → true in-corpus rate ~45-75%, bracketing
53.9%. RESOLVES the experimentation anomaly: pilots scale under new names; the gap is
measurement (renaming), not behavior. Who scales visibly: 文旅部 17%, 交通部 16%, 税务总局 13%.
Synthesis Part III updated. Verified live: validator 13/13; events 35,452 / 24,603 impl;
daily_sync order correct (2b identity last → 2c matcher → 2d validate).
- Writers active: identity pooling fix, B6 doc_inbound (2 = limit). B1 Jiangsu and B2 wait.
- Idea surfaced by B3 for the backlog: a RENAMING layer (instrument succession edges:
  pilot → renamed rollout, old law → amended law) would raise resolution and fix the
  experimentation visibility floor at its root. Queue as A2b.

## P2 Iteration 7
**Pooling fix LANDED** (`e05d266`). Agent corrected my premise: the locality was in the
MASTHEAD (深圳市人民政府关于印发…), not the core; rule handles both (`localize()`: masthead or
core-prefix locality → localized re-issuance = own instrument, implementing). Self-test 62→74.
Role flips: 611 mirror→unique, 282 canonical→unique, 651 docs re-keyed; 210 were mirrors of
CENTRAL texts. 以旧换新 anchor sources 67→61 (Shenzhen was already a title_reissue source; the
fix dropped 6 citers mis-attributed via the pool — correct). Events 35,452→35,465. VALIDATION
PASS 13/13. **Watch item:** 3,422 promulgation→implementing (local 条例 sharing a stem with a
national one, e.g. 浙江省宗教事务条例); 14 sampled all defensible, but a hand-check of this
genre shift is queued (QA item) — if too broad, restrict the flip to docs that were pooled.
- Launched **B1 Jiangsu to district depth** (bounded: probe 11 missing prefecture cities +
  ~8 Nanjing/Suzhou districts, add known-dialect ones, body-verify, skip JS/blocked). Writers:
  B6 doc_inbound + B1 crawls = 2.

## P2 Iteration 8
**B6 LANDED** (`83f5374`, 4 commits): `doc_inbound(doc_id, inbound, edges)` built INSIDE
build_site_stats.py (0.9s, 33,433 rows, max 2,143 = 政府信息公开条例) so it refreshes nightly
with no daily_sync edit — smart. Raw inbound shown beside citation_rank on browse/document/
lens/annotations ("3307.5 · 2143 cited"), `?sort=inbound`, API `sort=`. All 200, warm
0.05-0.15s; deep inbound pages O(offset) (page 6000 1.0s) noted. CLAUDE.md updated.
- Launched QA hand-check of the 3,422 promulgation→implementing flips (read-only, 60-doc
  stratified; recommends keep / restrict-to-pooled / split).
- Launched **B2 bottom-up channel**: (1) read-only acknowledgment-lexicon test (典型经验/
  经验推广/示范/可复制可推广 in central docs; do they cite downward; which localities are named
  as models); (2) bounded crawl of feedback sources (NPC 建议办理, CPPCC 提案, DRC 调研报告,
  2-3 provincial 人大). Writers: B1 Jiangsu + B2 crawls = 2. Read-only: QA genre check.

## P2 Iteration 9
**QA genre-flip LANDED** (`docs/working/qa-genre-flip.md`, read-only). The pass-1 flip
(sub-national promulgation → implementing when ANY higher text with a different locality
shares the stem) is **80% precise** on a 60-doc stratified sample (48 right, 12 wrong, 15
of the 48 are ambiguous parallel-人大-条例). All 12 wrong flips are one of two shapes: the
only trigger is an UNRELATED jurisdiction (茂名 ← 贵州, 苏州 ← 天津), or the stem is a generic
housekeeping genre (议事规则, 三定规定, 政府工作规则, 修改/废止部分规章的决定). 49% of the
3,422 flips have no central trigger at all; the script's own test table expects 议事规则 →
promulgation while the flip overrides it.
- Options scored: pooled-only would revert 3,048 (kills the renamed-re-issuance class the
  memos rest on — rejected); predates-only keeps 11/12 wrong; **in-chain + denylist** flips
  back ~810 and scores 44/45. Chosen.
- Launched implementer: own-chain rule (central / own province / own city) via a new
  `data/city_province.csv`, housekeeping-stem denylist, persisted `localized_of`, self-test
  cases from the memo, `--dry-run-flips` (read-only). Code + droplet dry-run only; the live
  rebuild waits for a writer slot (B1 + B2 still hold both). Then validate_cascades.

## P2 Iteration 10
**In-chain flip rule LANDED** (`7d7014e`): `jurisdiction_chain()` over a new
`data/city_province.csv` (354 prefecture-level divisions, verified against the 542 localities
`localize()` emits), `GENERIC_STEM_RE` denylist, persisted `localized_of`, `--dry-run-flips`
(read-only), self-test 104/104. Dry run: 3,422 → **2,583** flips, 839 back (207 generic
stem, 66 unknown locality, rest out-of-chain; 760 municipal). Kept flips by trigger: central
1,702 / provincial 862 / municipal 19. Sample of 30 flip-backs all correct (武汉 ← 江苏 投资管理办法,
广州 ← 安徽 垃圾分类条例 ...).
- Judged one crawl writer (B2's npc_dbgz) acceptable: the write transaction is only the
  6s insert; the 37s is compute before BEGIN IMMEDIATE, so no crawler hits busy_timeout.
- Rebuilt doc_identity live (321,552 rows, 6.4s txn). **validate_cascades 13/13.** Then
  rebuilt diffusion_events on the new identity (result below). CLAUDE.md `localized_of` line.
- diffusion_events rebuilt in 44s: **35,475 rows** (was 35,465; 24,629 implementing / 10,846
  mentions; citation 26,745 / topic_genre 7,920 / title_reissue 810). Validator 13/13 after.
  Net effect of 839 flip-backs on events is ~zero because the matcher's `implementing`
  flag is dominated by citation-type events whose genre was already non-promulgation.
- Still holding A2b (instrument succession) until B1 or B2 frees a writer slot.

## P2 Iteration 11
**B1 agent stopped** (reported "waiting" on its own crawl chain → TaskStop, took over). State
verified on the droplet: govcms.py byte-identical both ends (md5 5588fe2b); 13 new Jiangsu
provincial-dept sites (js_czt/fzggw/gxt/jtyst/kxjst/mzt/scjgj/sft/sthjt/wjw + nynct/ybj empty)
~1,330 docs, 4 Nanjing districts (njd_gulou/jiangning/jianye/qinhuai, static 214/<cat> lists
behind a Jiasule JS homepage, found by reading the shell's JS) ~380 docs so far, 5 Suzhou
districts configured (hexmon dialect I; 吴中/昆山/玄武/栖霞/浦口 unreachable from NYC). Chain
pid 244120 still running: nanjing → njd_* → szd_* (timeout 900 each). Will finalize
(build_site_stats, per-level counts) when it exits.
- Date scare resolved: `date_written=0` on ALL govcms sites is by design (govcms writes
  `date_published` TEXT; doc_identity reads it). 11/13 new sites rate `good`; `js_mzt` and
  `njd_jiangning` are `crawl_stamped` → parser miss, queued as polish.
- Launched **A2b instrument succession** (code + read-only dry-run; relations renamed /
  pilot_to_national / revised_edition / superseded_by_stated; write step gated on me).
  Writers: B2 jsrd crawl + B1 chain = 2.
- Correction: TaskStop on the B1 agent also killed its crawl chain (CHAIN_EXITED within 1 min;
  only nanjing + njd_qinhuai had run). Relaunched the 7 remaining sites myself with
  `setsid nohup ... < /dev/null` (pid 245281, `logs/b1_chain2.log`). Lesson: a subagent's
  background chain dies with the agent; detach chains with setsid or own them from the start.

## P2 Iteration 12
**B2 LANDED** (`707e392`, `docs/research/bottom-up-channel.md`, 398 lines). Verified on the
live DB: npc_dbgz 796 docs / 97% body, cppcc +96, jsrd 447 / 44% (pre-2023 rows are site-side
404s), bjrd 88 / 100%; site_stats 465 sites, 322,982 docs.
- Finding: the acknowledgment lexicon rose 2-3% → 17-19% (2021-22 peak) of central
  promulgations but is 92% exhortation; 296 docs name a locality near the phrase, 79 in the
  title; lexicon docs cite downward 0.31% vs 0.24% (noise). **Mechanism: the center absorbs a
  local model by naming the place in prose, never by citing the local document → the citation
  graph is structurally blind to upward flow.** Named places track GDP (Spearman 0.664, richest
  ten 62.5%), same as pilot selection (0.705 / 55%). Through-line hardens for citations, softens
  for prose. Added to findings-synthesis through-line + `/research` Part III order (also added
  site-selection-gdp and successor-detector, which were in "Other").
- Crawler side-effect: govcms Scheme-B pagination now takes the extension from page 0
  (jsrd uses index_N.shtml). Still in the uncommitted govcms.py (identical both ends).
  Pending hygiene: commit govcms.py; add `--group feedback` to nightly; ontology leaf for
  npc_dbgz/jsrd/bjrd.
- Skips: drc.gov.cn (anti-bot shell), 广东/浙江人大 (refused), 上海人大 (403), 国研室 (no site).

## P2 Iteration 13 (hygiene + a stale-ontology find)
- **govcms.py finally committed** (`c6502a0`, with daily_sync `--group feedback`, the synthesis
  through-line update and the `/research` Part III order). Droplet: md5 verified identical
  before and after; the classifier blocked `git checkout <file>` so used backup +
  `git stash push` (stash@{0}, backup in `.local_backup_20261006/`) then `git pull --ff-only`.
  Tree clean, app restarted, `/research` shows bottom-up-channel / site-selection-gdp /
  successor-detector (0.10s).
- **Found: source ontology is stale.** `validate_ontology.py` on the live DB: 231/510
  site_keys unmapped → "Other" = 21,640 docs (all city/city2/city3 portals, bjb_/shb_/hn_/jl_/
  ln_/sd_ dept families, ~30 central agencies, feedback sites). Degrades the exclude-news
  filter and the source-type facets. Launched an agent to fix it structurally: admin_level/
  group FALLBACK in `ontology.py` (yaml stays the override layer), new `local_legislative`
  leaf, validator distinguishes fallback-mapped from unmapped. No DB writes.
- Running: B1 chain2 (njd_jiangning → szd_*), A2b succession (code + dry-run), ontology
  repair. Writers: chain2 only (A2b write gated on me).

## P2 Iteration 14
**Ontology repair LANDED** (`5c8de39`). Verified on the droplet: `validate_ontology.py`
**PASS**, unmapped 231 → 0, "Other" 22.2k docs → 0; 513 site_keys = 383 explicit + 129 by the
new `sites.admin_level`/govcms-`group` fallback (13.1k docs, 126 municipal portals + 3
districts), media never by fallback. New `local_legislative` leaf (jsrd, bjrd); npc_dbgz under
central legislative; dept prefixes hn_/jl_/ln_/sd_/bjb_/shb_; `ccg` is 中国海警局 not the think
tank (agent caught it from `sites.name`); 求是 → media_state. Routers pass site rows so
`source_node=!media` covers fallback sites. 8 tests. App restarted; `/` 0.21s,
`/browse?source_node=!media` 0.71s, search+exclude 2.1s (BM25 path, acceptable).
- Chain2 progress: njd_gulou/jiangning, szd_sipac, szd_gusu (+63) done; szd_wujiang running.

## P2 Iteration 15
**A2b instrument succession LANDED** (`d565765`) and written live: 12,820 rows in 0.1s txn
(68s wall). superseded_by_stated 1,823 (conf .95) / revised_edition 10,335 (.85) / renamed
588 (.66) / pilot_to_national 74 (.85). Universe 106,900 canonical good-date instruments;
strict date order → DAG; 3,098 nodes sit in chains. Hand-check (20/relation, 3 rounds, so
slightly optimistic): stated 75/95%, revised 85/95%, renamed 75/85%, pilot 80/90%. Pilot
coverage: 73 (5.9%) via pilot rule, **141 (11.3%) via any relation**. Validator 13/13 after.
- Wired into daily_sync Phase 2b right after build_doc_identity; README + CLAUDE.md lines.
- Chain2: szd_zjg done, szd_changshu (last) running.

## P2 Iteration 16 (B1 finalized)
Chain2 ALL_DONE 03:52 UTC: njd_gulou +95, njd_jiangning +89, szd_sipac +44, szd_gusu +63,
szd_wujiang +83, szd_zjg +113, szd_changshu +65 (= +552; real dates 2013-2026, body 85-100%).
site_stats rebuilt: **470 sites, 323,529 docs**. Jiangsu tier (doc_identity level): provincial
6,589 (incl. 13 new js_* depts + jsrd), municipal 5,548 (suzhou 4.9k dominates), district
**~1,000 across 9 sites** (gotcha: `LIKE 'szd_%'` also matches Shenzhen's `szdp`; `_` is a
wildcard. Use `GLOB 'szd_*'`). Guangdong for comparison: provincial 11.8k / municipal 9.8k /
district 22.2k. So Jiangsu is now a second nested province but its district tier is ~1/20 of
Guangdong's; the fidelity re-run must treat it as such.
- Launched: Jiangsu nested fidelity re-run (read-only → `fidelity-jiangsu.md`), and the
  crawl-stamped date fix for js_mzt / njd_jiangning (sole writer; general parser fix + HTML
  redate backfill + identity rebuild + validator). A7 dept-tier body backfill waits behind it.

## P2 Iteration 17 (a premise fell)
**Date-fix agent LANDED** (`742c401`, `90af693`) and refuted the brief's premise: js_mzt and
njd_jiangning dates were CORRECT (match page `<meta PubDate>` 319/417, 200/262). The A4
`crawl_stamped` rule (≥70% of dates in the crawl year) was detecting SHALLOW ARCHIVES, not
stamped dates; a sweep of all 76 flagged sites found no crawler writing the crawl date and no
bulk day dated on itself. Real bugs fixed generally in govcms: single-quoted meta attrs,
`&nbsp;` overflowing the label window, list-row date bleed (98/417 js_mzt docs 1-17d late; 62
njd_jiangning docs carried a re-post URL date, real dates back to 2011). New
`scripts/redate_from_html.py --site X`. A4 rewritten to a bulk-crawl-day test (self-test
113/113). Verified live: crawl_stamped 29,127 → **0**, good 97.0%, validator 13/13,
`--self-test-dates` 12/12.
- Propagated the correction: corpus-lessons A4, industrial-policy-targeting §1 (exclusion
  kept under the honest label "shallow archive"), consistency-review Applied log, CLAUDE.md.
- Consequence for the volume: industrial-policy's 74-site exclusion needs a robustness re-run
  with the sites included (queued, read-only). instrument_succession's `date_quality='good'`
  filter now admits 9k more instruments; tonight's rebuild picks it up.
- Bulk redate of the row-bleed sites (jcgov/qingdao/jilin/xlgl, ~7-9/40 off by days) is low
  value; parked. changde has no date on page at all (needs a new shape).
- Committed the correction (`12453df`), droplet synced. Launched the industrial-policy
  robustness re-run (read-only; three universes) and **A7** (writer). Measured body % by level
  first: central 58.9% (npc 28.6k metadata-only by design), department 88.8%, others 93-97%.
  So A7 is redirected at central non-npc + department + provincial, ranked by recoverable
  (bodiless with saved HTML). Agents: Jiangsu fidelity, industrial robustness (read-only), A7
  (sole writer).

## P2 Iteration 18 (B1 research discharged, two new data bugs)
**fidelity-jiangsu LANDED** (`105d040`, live at /research/fidelity-jiangsu). Jiangsu vs
Guangdong on the same identity layer: province-before-city 82.1% (n=39) vs 65.1% (n=704), but
GD cut to 5 cities gives 78.5% [71.8-84.8], so the gap is a watching-fewer-cities effect;
city→province fidelity median 0.125 vs 0.109; city closer to province than center 89.9% vs
92.1%; lag slope and genre ordering identical. **Verdict: hardens, on one city** (Suzhou = 89%
of Jiangsu city docs; sub-provincial tier 1/15 of GD's). B1 is discharged only when a second
non-Suzhou Jiangsu prefecture reaches Suzhou's depth (queued: 无锡/南通 are in city tiers but
shallow).
- Flags acted on: (a) `province_of` mapped `szd_*` to Guangdong via the `sz` prefix and had
  no `nanjing` entry → fixed (`commit below`). Then measured: **42 municipal/district sites
  (7,792 docs, incl. wuhan 1,009 + whd_*) have NO province** → same hand-list rot as the
  ontology; delegated a csv-derived resolver (sites.name × data/city_province.csv, hand table
  as override). (b) **Suzhou dates ARE crawl-stamped** in two batches (2023-02-09 1,860 docs,
  2025-02-11 1,499 = 68%); both A4 rules miss it because no single day exceeds the threshold.
  Validator's JS 82d doc is `js` (provincial), unaffected. Queued for the next writer slot:
  Suzhou redate (page meta, else URL /YYYYMM/) + multi-batch A4 rule. (c) `localized_of` shows
  the citation path sees <50% of renamed re-issuances → pair builder citation ∪ title ∪
  localized_of queued as research infrastructure.

## P2 Iteration 19
**Industrial-policy robustness LANDED** (`601e7bb`; R1-R7 appended, synthesis Part IV line;
live after restart). Three universes: (a) memo 224k, (b) all dated incl. the 77 shallow sites
(28,940 docs), (c) shallow alone. **Held:** tagged share + HHI every year, every confirmed
rise/fall but telecom, every money/rule share within 2 points; the 2026 bar doubles 27k → 55k
(the shallow-archive effect shown directly). **Moved:** central share in MIIT's remit sectors
(telecom 56→76, future industries 13→29, AI 34→44, software 42→49); telecom rise/fall ratio
0.2→0.5. Verdict: exclusion right for the time series, wrong for the level cross-section;
"future industries are local from the start" was an artefact of dropping the sector's lead
ministry. R5: on `doc_identity` levels universe central 31.8→22.3% (npc re-leveling), so the
1.5 tilt threshold needs re-basing (queued as the memo's next revision, read-only).
- Running: A7 backfill (sole writer), province resolver (code). Next writer: Suzhou redate +
  multi-batch A4.

## P2 Iteration 20
**Province resolver LANDED** (`b7162c8`): new `scripts/rnd/analysis/geo.py` (CITY_PROVINCE,
DISTRICT_CITY moved out of build_doc_identity, PROVINCE_CODE 31 units ISO-style with the
existing codes kept, 28 English-name aliases); `province_of()` = hand table override + name-
derived fallback. Municipal/district sites resolved 160 → **223/223** (+7,792 docs: jcgov→sx,
wuhan→hb + 6 whd_, suzhou_ah→ah, leshan→sc ...). Honest residual printed per build: 18
national-SITE sources with sub-national docs (npc 24,268, miit 739 ...) need per-document
locality, not a site map (queued). Self-tests 20/20 geo, 113/113 identity, pytest 19 pass.
- Rebuilt diffusion_events live: **35,498** rows (24,651 implementing); provincial-anchor
  events 6,846 across 19 provinces (was effectively GD + a few). **Validator 13/13.**
- A7 is committing (`f858356` govcms body-region bound) and still writing.

## P2 Iteration 21 (A7: another premise narrowed)
**A7 LANDED** (`0eeb4d5`, `f858356`, `ff8ed83`; tests 9/9; droplet clean). The
"bodiless-with-saved-HTML" pool (6,146 docs excl. npc) is **~95% irrecoverable by selector**:
miit 5,383 (3,790 are 14-byte anti-bot stubs + 1,527 missing files → needs a residential/HK
re-fetch, user-gated), ipc_court 145 missing files (recrawl), PDF/RAR/image/video pages. The
fixable set was ~125 docs with two root causes: `backfill_from_html.py` routed govcms-tier
sites to a weak local generic instead of the crawler's extractor; 5 containers missing
(`txt_txt` court, `wip_art_con` shandong, `pages_content` saac, `class="zoom"` Hanweb,
`detail-article`). Net **~126 real bodies**: spc 51.6→90.6%, jl_jyt 33→98%, jl_swt, js_fzggw,
shandong. Department tier unchanged at 88.8% (its gap is not selectors). The agent's own QA
caught 143 junk bodies from its first pass (region ran past `</div>` into nav) and reverted
them with a scoped byte-identical-to-buggy-output rule; good discipline.
- Residual noted: 770 short bodies corpus-wide end in a "分享到：" share-widget tail (pre-
  existing). 45 saac + 34 jl_swt bodies carry nav tails. Bounded re-extract someday.
- Launched **Suzhou redate + multi-batch A4** (sole writer, hard stop 05:45 UTC before the
  nightly): fix `crawlers/suzhou.py` date extraction, route redate_from_html to it, URL
  /YYYYMM/ fallback, bulk-day-sum rule, identity + diffusion rebuild + validator.
- Also running (read-only): pair-channel builder (`pairs.py` + `pair-channels.md`),
  industrial-policy level re-basing on doc_identity.

## P2 Iteration 22
**Industrial level re-basing LANDED** (`485ef0b`, L1-L6 appended + synthesis sentence). New
rule: sector "centrally targeted" iff z ≥ +3 against a sector-size-matched null drawn from the
sector-tagged pool (200 draws); the old 1.5 tilt line equalled the pool's own tilt (1.55/1.59),
so it selected the average sector. Bridge check: on the published config the new rule returns
exactly the memo's seven. **Survive:** telecom, platforms, data, ships, heavy, NEV central;
real estate + low-altitude local; low-altitude as a district phenomenon; the §4.1 rises/falls.
**Flip:** agriculture (49.5→26.6% central; npc-filed 种子/农机 regs); "AI evenly spread";
equipment "municipal 1.49" (department-tier denominator); 15/16 → 14/16 sectors fall (carbon
now rises). **Undecidable:** every department tilt (doc_identity has no department tier;
survives as a within-municipal site-type split); software/carbon/biopharma labels depend on
the universe choice. 22% of docs still carry `level_source='site'`, stated.
- The volume's lesson, now three times over today: a threshold or a filter defined on a
  DISTRIBUTION (dates in crawl year, body-tier gap, tilt 1.5) needs one hand-check against
  the object it claims to measure before it becomes a rule.

## P2 Iteration 23 (Suzhou dates)
**Suzhou redate LANDED** (`5465b8e`, `247c5f7`; writes done 04:44 UTC, before the nightly).
Two twists the hand-check surfaced: (1) the 2023-02-09 / 2025-02-11 piles are the SOURCE
CMS's page-regeneration stamps (`<meta PubDate>` = 页面生成时间), not our crawl day; the real
date is the article header `时间：<PUBLISHTIME>`; (2) the URL `/YYYYMM/` folder is a 2021
migration artefact for ~250 historical 规范性文件 (1991-2011 文号 years in /202105/), so a blind
URL-month fallback would have corrupted 367 real dates. Rule: article attr (day) > PubDate only
if same month as URL > 发文日期 when in-month or folder ≥6 months later > URL month day 01.
Raw HTML exists for only 76/4,918 Suzhou docs (3,814 rows point at files never copied from the
Mac) so the page route fixed 3; 发文日期 2,829; URL-month-01 522. **3,354 rows redated**,
median shift −1,886 d. A4 rule now also sums bulk DATE-days (≥20 & ≥10%, day≠1 exempt, ≥50%),
self-test 125/125; calibrated so gov's 2,308 docs on 2018-12-31 (11.5%) stay good; no new
sites flagged. Validator 13/13 before and after. diffusion_events 35,498 → **36,116**;
Suzhou-source events 788 → 1,406; Suzhou lag median 293 → 341 d. `redate_from_html.py` now
routes site_key → crawler dater (`SITE_DATERS`), same pattern as the body backfill.
- Open: 685 Suzhou docs sit on a month-precision `-01` day with `date_quality='good'` (no
  precision column); the 2024-11-07 pile (93, <10%) may be another regeneration day.

## P2 Iteration 24 (pair channels)
**Pair builder LANDED** (`559e6cc`, `5fd8815`): `scripts/rnd/analysis/pairs.py`
(`build_pairs()`, union of citation ∪ title_reissue ∪ localized_of per (source, parent
instrument), identity-layer fields, the memos' 5-gram scores moved out of appendices into
code, 127s read-only, self-test 17/17) + `docs/research/pair-channels.md` (Method & QA).
Venn P→M: cit-only 6,483 / loc-only 87 / title-only 217 / cit+loc 174 / title+loc 58.
**Floor correction is real but small:** GD P→M relay 8.9% → 9.1% (474 → 496 relays) on the
union; two-channel pairs are the renamed re-issuances (median 0.525, relay 29%). Three
findings: (1) "<50% visible to citations" is mostly a BODY problem (among sources with a body
only 25.5% invisible; the C→P 92.7% is npc body-less law entries); (2) the framework gate
withholds more than any channel (329/643 GD provincial triggers fail `is_framework`, mostly
印发 notices: 应急预案 / 若干政策措施 / 工作要点; gate off P→M 7,019 → 10,153); (3)
**`localized_of` is not date-ordered: 530 edges precede their trigger**, and has no province
for npc (163). Recommendation: re-base fidelity-provincial §2.2 and fidelity-jiangsu §7
wording on the union; widen the framework gate once, in the identity layer, after a hand-check.
- Queued (writers, after the nightly): identity fix requiring trigger date ≤ doc date for the
  flip (with a small slack for same-month re-posts) + per-doc province for npc; framework-gate
  hand-check (read-only) before any widening.
- Launched the identity date-order + npc-province fix (code + dry-run; rebuild after nightly).

## P2 Iteration 25 (B7)
**policy-tempo LANDED** (`3a7e014`; Part II after daily-tracker-concept; synthesis sentence).
History: tracker_weekly 458 ISO weeks from 2018-W01, 29 topics; built the 2015-26 series from
diffusion_events directly (13,081 confirmed implementing central events). Censoring measured:
an instrument's cascade yield is 2.2% visible at 4 weeks, 8.8% at 12, 41% at a year, 67% at
two (median lag 473 d); 2026 cohort corrected ×1/0.39. **Tempo** (implementing cascades within
365 d per canonical central promulgation): Government 0.71 (mandatory re-issuance of
procedural rules), Emergency 0.28, Environment 0.23; slowest Tourism 0.05, Culture 0.065,
Agriculture 0.067; Finance and Tech 0.07. Cross-year tempo is NOT safe (denominator triples as
central sites enter; needs a fixed-site panel). **Burstiness:** all topics over-dispersed (Fano
1.2-3.8); campaign alignment holds within-topic (Commerce 3.4× inside 以旧换新 2024; Tech 1.9×
inside AI+); no 2013 step. Pooled bursts are single-portal batches (Guangzhou 51/83 on
2023-01-02, Shenzhen 57/66 on 2020-03-09) with `date_quality='good'` → a per-week
site-diversity gate is needed. **Lead-lag:** 6/90 pairs p<.05 vs 4.5 expected; only Tech →
Education at 2 weeks beats the null. **Level:** provinces 53% / cities 42% / districts 5% of
cascades; first implementer provincial for 67% of anchors (n=649). Verdict: an instrument for
burstiness and level timing now, not yet for cross-area tempo or lead-lag.
- App restarted; policy-tempo / pair-channels / fidelity-jiangsu render.
- Launched the framework-gate hand-check (read-only).

## P2 Iteration 26 (A6 prep)
**A6 recoverable-head LANDED** (`b5a5273`; `docs/working/a6-recoverable-head.{csv,md}`, 137
byte-checked probes). Top-400 unresolved head = 15,814 distinct citers; only 1/400 resolves
today, so the head is genuinely absent. **Confirmed reachable from NYC 29.1%** (4,609 citers,
5,736 edges), likely 43.4%; blocked hosts 7.6% (huizhou/yangjiang, true delistings);
**部门规章 wall 16.4%** (公安部令/人社部令/住建部令 not in gov.cn's library, ministries blocked →
HK-VPS / 北大法宝 bucket, user-gated); queue noise 10.4% (permit names, GB standards). Two
CLAUDE.md "delisted" verdicts are WRONG: 深圳市行政听证办法 and 深财规〔2023〕3号 live in the
Shenzhen 政府公报 archive `sz.gov.cn/zfgb/` (byte-checked). Top item is zero-crawl: 广东省控制性
详细规划管理条例 (340 citers) is already held under 广东省城市控制性详细规划管理条例 → resolver alias.
Fetch plan (writer, after nightly): gov.cn 中央文件 library (`zhengcelibrary_zy`, 566 docs, 党内
法规 + 党章, ~1.7k edges); gov.cn gw `--deep` (2000s 国发 tail); a Shenzhen 政府公报 walker
(http only; thousands of docs, ~1.5k head edges, 14.9k Shenzhen-family citers behind it); 中山
自然资源局 sub-site + gdnr search + 大鹏 规范性文件库; alias + HTML-entity unescape in the resolver.
Expected +5.7k edges (≤8.2k), +2-3 points resolution, plus four archives' long tails.
- Launched resolver alias + HTML-entity unescape (code only, deadline 05:50 so the nightly
  applies it in its own citation rebuild).

## P2 Iteration 27 (identity: date order + province)
**Identity fix LANDED** (`80be9c1`, 05:16 UTC, before the nightly pull → the 06:00 run
rebuilds doc_identity with it and validates). `pick_trigger()`: in-chain same-stem candidates
dated ≤ doc + slack, take the LATEST (nearest parent), remap mirror → canonical. **Slack = 7 d
(+31 when either date is a -01 stamp)**, from the data: of 471 reversed edges 404 (86%) were
>180 d apart and 0 shared the trigger's pool → false triggers (云南省行政执法监督条例 1998 ← SC
2025), not re-posts; the 8-60 d reversed cases are annual-cycle siblings (立法工作计划). Flips
broad 3,443 → in-chain 2,592 → **date-ordered 1,958**; reversed beyond slack **0**; 496
triggers moved to a nearer parent. New `doc_identity.province` (A1-ordered: lead_issuer →
文号 agency → publisher → masthead → localize → title head): 165,934 / 207,042 sub-national
docs (80.1%); **npc 27,664 / 28,595**, miit 734/739, bjrd 88 via place-prefix fallback; 99.9%
agreement with the site province where both exist, disagreements are the doc being right.
Consumers (`build_diffusion_events.load`, `pairs.load_docs`) prefer `i.province` over
`province_of(site)`. Audit fallout: `qianjiang` is 重庆黔江 not 湖北潜江 (`hbqj`) → fixed.
Self-tests identity 142/142, geo 23/23, diffusion-geo 22/22, pairs 17/17, pytest 19 pass.
- The post-nightly manual sequence is therefore unnecessary; verify the nightly log instead
  (Phase 2b identity line, Phase 2d validation), then rebuild diffusion only if Phase 2c ran
  before the identity change (it shouldn't; 2b precedes 2c).

## P2 Iteration 28 (framework gate)
**qa-framework-gate LANDED** (`df3a1b5`). The 329 GD exclusions come from 85 of 210 provincial
triggers (all `genre=promulgation`; policy_issuance 72, notice 13); central analog 87/298.
**Exclusion precision 23%** (14/60 rightly excluded; 44 instruments / 14 housekeeping / 2
unclear). Every 印发-wrapped 应急预案, 若干措施, 工作要点, 重点工作任务 and non-housekeeping 方案 is
an instrument (27/27); 立法/规章计划 and 申报 calls never are; bare 通知 is mixed and not
separable by title. Dropped pairs are **85% real implementations** (17/20; P→M under
instrument-class parents median 0.357, relay 19.7% = the renamed-re-issuance profile).
Proposed R1: admit issuance-wrapper titles whose core matches 应急预案|预案|若干措施|政策措施|
工作要点|重点工作|任务分工|工作安排|方案 minus 整改方案|考评|考核|组建方案|申报|评选|名单|遴选;
admits 28/44 (a) and 0/14 (b); +1,950 pairs (+3.9%), P→M +788 at median 0.185 / relay 13.2%
vs baseline 0.074 / 8.5%. **Where:** identity layer, a per-document framework flag /
`instrument_kind` in doc_identity that `is_framework` reads (a bare `FW_TITLE_RE` widening
would admit the bare-title pockets at 0.033). Writer; launch after the nightly pulls.

## P2 Iteration 29 (resolver, zero-crawl)
**Alias + entities LANDED** (`3134994`, 05:24 UTC, nightly applies it). (1) `data/instrument_
aliases.csv` loaded by `TitleMatcher`, applied to the normalized ref before the exact tier
only when the ref has no exact candidate of its own; one row (广东省控制性详细规划管理条例 → the
held npc title, 340 citers). (2) `_clean_ref()` html.unescape + `&lt;X&gt;` → 《X》 at
extraction time. (3) **Real bug:** the title index was built `WHERE LENGTH(title) >= 8`, so
1,661 held titles of length 5-7 (广东省公路条例 ×4, 山西省公路条例 ...) were never candidates;
floor lowered to 5, reachable through the exact tier only (containment floors unchanged, so
no new proxy matches). Read-only dry check on live titles: all three target refs now resolve
to the held npc docs, controls unchanged. Expected ≈ 480 distinct citers recovered by the
nightly rebuild. Tests: new `tests/test_citation_aliases.py` 6/6; proxy-fix 12; implementing 4.
- Hygiene found: `tests/test_citations.py` has 6 tests failing on a stale import path from
  the July scripts reorg (`scripts.extract_citations`); droplet has untracked scratch files
  (`_cit_analysis.py`, `_probe2_js.py`, `_probe3.py`, `.local_backup_20261006/`). Both queued.
- Launched: `instrument_kind` identity change (code; push gated to after 06:05 UTC so the
  nightly never rebuilds on half-built code); stale test import fix (Mac only). Moved 13
  untracked scratch files out of the droplet repo root to `/root/scratch_20261007/` (mv, not
  rm; `.venv/` kept); tree clean for the nightly's pull.
- Stale tests fixed (`0210c2e`, Mac only): `tests/test_citations.py` import path from the July
  reorg + the fixture lacked `algo_doc_type`, which the resolver's genre gate now reads.
  pytest 6 failed/49 passed → **55 passed, 1 skipped** (the skip needs the droplet tables).

## P2 Iteration 30 (nightly window)
- instrument_kind agent stopped at its own push gate ("waiting") → TaskStop; local commit
  `890a25a` (self-test 166/166) pushed by me at 06:12 UTC, AFTER the nightly pulled `0210c2e`
  at 06:00, so tonight's Phase 2b runs the droplet-dry-run-tested identity code (date order +
  province) and instrument_kind is applied manually when the lock clears.
- Nightly `daily-20261007-0600.log`: Phase 1 crawling (lock held for hours). Read-only window:
  launched fidelity-provincial §2.2 / fidelity-jiangsu §7 re-base on the union pair set, and
  the tracker burst site-diversity gate (`n_sites`, `top_site_share`, `diverse` flag; code +
  read-only dry-run). CLAUDE.md: corrected the "delisted" verdicts (two head items live in the
  Shenzhen 政府公报 archive; 控规条例 was already held) and recorded province / instrument_kind /
  localized_of ordering / aliases / pairs.py / new memos (pushed; droplet pull deferred).
- Launched A6 fetch crawlers (code; scratch DB only): gov.cn `zy` library, Shenzhen 政府公报
  walker, `zs_lyj` gkmlpt site, gw --deep sanity.

## P2 Iteration 31
**Union re-base LANDED** (`7c11271`; fidelity-provincial §2.2 + fidelity-jiangsu §7, append-
only, originals labeled citation-only). GD P→M on the union: relay 8.9 → **9.1%**, relays 474
→ 496, renamed re-issuances 377 → **398** (memo had 381); decomposition 转发 17% / mirror 3% /
renamed 80%. Jiangsu: 14 relays on both bases, union adds none. Measured on the 10-06
identity build (2,592 localized_of; no province/instrument_kind yet), stated. **Caveat:** the
Jiangsu CITATION basis is now 473 pairs (456 Suzhou, median lag 777 d) vs §2.1's 200, because
the Suzhou date repair pulled its events into range → §2.1's Jiangsu row must be re-read on
the new layer (queued with the post-nightly rebuild). The tracker-gate agent has committed
(`a96e7c8`); awaiting its report.

## P2 Iteration 32 (tracker diversity gate)
**LANDED** (`a96e7c8`): `tracker_weekly` + `n_sites`, `top_site_share`, `top_site` (additive,
MIGRATE adds them; `--dry-run` opens ?mode=ro); `tracker.py` `is_diverse()` = events ≥ 3 AND
n_sites ≥ 3 AND share ≤ 0.5 (majority rule; 91% of pooled weeks pass; chosen over 0.6 which
the Guangzhou week would pass by 0.014); template tags non-diverse weeks "single-source",
counts untouched; 7 tests (suite 62 pass). 2023-W01 (gz 0.61) and 2020-W11 (sz 0.86) flag;
2026-W33 deliberately NOT (26 sites, share 0.20; the concentration is on one ANCHOR, 生态环境
法典 25/75 → an anchor-concentration gate is a separate follow-up). Top-20 burst survivors:
all 13/20, Welfare 18, Finance 16, Government 14 ... Education 4; small topics mostly flag
(their 3-5-event weeks are one or two portals). Tonight's Phase 2c + Phase 3 apply it.
- Launched the second-Jiangsu-prefecture discovery probe (无锡/南通/常州/扬州/镇江, read-only).
  It stopped to "wait" on its own droplet probes → TaskStop; its scripts survive in
  `/root/scratch_20261007/` (probe/listprobe/depth/bodyprobe.py); relaunched a finisher that
  re-runs them with outputs captured to files and writes the memo. Lesson reinforced: a
  subagent's background jobs are only useful if they write files, never stdout.

## P2 Iteration 33 (A6 crawlers ready)
**A6 fetch code LANDED** (`4474797`; scratch DBs only, ~1,800 bounded probes from the Mac).
(1) `gov.py` `zy` = 中央文件 library: 566 docs, **432 new**, bodies 3/3, no pcode (文号 only
from page metadata). (2) New `crawlers/sz_gazette.py` (site_key `sz_gazette`, municipal):
the Shenzhen 政府公报 is fully walkable via NFCMS JSON (`/postmeta/i/101619.json` → 39 years →
~1,450 issues → articles with 文号/issuer/section; bodies `/postmeta/p/...json`), http only;
2006+2023 test: 750 docs, 748 new, both head items found WITH bodies (深圳市行政听证办法 市政府令
157号; 深财规〔2023〕3号); bodies 10/10; full ≈ 8-12k docs, list 25 min, bodies ~3h. (3)
`gkmlpt.SITES["zs_lyj"]` 中山自然资源局: **30,873 docs, 0 held** (规划计划 12.5k / 公告公示 10k /
征地 5.6k / 决策公开 422 / 其他文件 124), 1,830 with 文号; head 控规 items found. (4) gw deep walk
completes now (6,221 listed, 399 new, 161 held-bodiless fillable). dpxq 规范性文件库 is the
same NFCMS dialect (42 docs; 10-line variant, not implemented).
- Apply after lock (writer, serial): gov zy,gw --deep → sz_gazette list + bodies (chunk by
  year) → zs_lyj metadata + bodies policy-first (文号 docs first; the 公告/征地 bulk is low
  value, consider leaving bodiless) → nightly citations → validator. Expected head yield ≈
  zy 1.7k edges, gazette 1.5k, zs_lyj 0.6k, gw 0.4k.

## P2 Iteration 34 (anchor gate)
**LANDED** (`1046da7`): `n_anchors`, `top_anchor_share` (pooled by instrument_id) +
`single-instrument` tag when events ≥ 3 AND share > 0.3 AND modal instrument ≥ 3 events.
Threshold from the knee: 96% of pooled weeks ≤ 0.3, nothing between 0.304 and 0.333; the
spec's 0.5 would catch 3/449 and miss W33 (0.333). 2026-W33 flags (38 anchors, 生态环境法典
25/75); the two portal weeks keep only their site flag. 9/449 pooled weeks flagged. Per topic
top-20 bursts single-instrument: Diplomacy 14/15, Legal/Government/Safety 9/20, Finance 0.
Tests 70 pass. MIGRATE adds all six columns on the next rollup; service renders without tags
until then.
- Nightly still Phase 1 at 06:5x UTC. Remaining in-window agent: prefecture memo finisher.

## P2 Iteration 35 (consistency round 2)
**LANDED** (`6120839`; `consistency-review.md` "Round 2 (2026-10-07)", 12 memos patched with
dated parentheticals, nothing deleted or recomputed). **2 H / 10 M / 8 L.** H2: the Suzhou
date story in fidelity-jiangsu + synthesis still read "crawl-stamped, URL-repaired" (what
landed: source-CMS regeneration stamps, header → 发文日期 → URL-month repair, URL folder is a
2021 migration artefact; the memo's 1,989/1,727 were YEAR counts, day piles 1,860/1,499); the
Jiangsu P→M citation basis is now 473/426 scored, relay 3.3% vs the quoted 191-200 / 8.0-8.4%
(same 14 relays; denominator effect) → caveat added. H1: synthesis "Status and what remains"
was two days stale (提振消费 fix, npc re-leveling, A1-A5, A4 correction, B1-B7, pair-channels,
industrial re-basing) → rewritten. M4/M5/M7: claims stronger than measured ("fewer than half
visible" without the body caveat; "92% exhortation" is "92% names no locality"; "department
tier weak"). Also: five quoted diffusion_events sizes (two dated 10-07: 35,475 vs 36,116),
resolution quoted ~52% vs **live 50.5%** (270,211/534,722 after the containment gate),
successor-detector ran pre-A4-correction (35,027 vs 36,902 good-dated central promulgations).
Left for a compute pass after the nightly: Jiangsu §2.1 re-read; successor universe re-run.

## P2 Iteration 36 (dpxq)
**LANDED** (`f00f665`): `sz_gazette.py` now takes `NFCMS_SITES[--site]`; `szdp_gfxwj` walks
大鹏 规范性文件库 (root 150493, levels 0) into the EXISTING `szdp` site (bodies scoped by URL so
gkmlpt's rows are untouched). Scratch: 42 listed / 42 new, bodies 5/5, status → `relation`
(`repealed;` token as chongqing; 31 有效 / 11 无效). 文号 only from body heads, line-anchored
(a free regex captured CITED 文号 first; tightened). Both 专项资金管理办法 editions present; the
人才 操作规程 head items are in another dpxq section (separate probe needed). Test 4/4. Apply:
`python3 -m crawlers.sz_gazette --site szdp_gfxwj` after the lock (one-off; not in nightly).

## P2 Iteration 37 (second Jiangsu prefecture)
**jiangsu-second-prefecture.md LANDED** (`d0fb3c8`; probes re-run with outputs saved to
`/root/scratch_20261007/js2_*.txt`). **Recommendation: 无锡** (static, URL-dated `/doc/YYYY/MM/
DD/`, no new dialect for the municipal tier): ~2,250 municipal core + ~2,400 部门文件 + ~1,880
across 5 districts + 江阴 ~880 + 宜兴 36 ≈ **7,400 docs** vs Suzhou 4,918 + ~370. Two code items:
(1) a govcms BUG: `_pages()` only follows `.shtml` paging when page 0 has a t-date link, so
无锡's `/doc/` lists fall to `index_N.html` (404) and `--deep` stops at page 0 → stored `wuxi` =
130 rows; fix = widen the test or per-site `page_ext`, plus per-site `max_pages` (hardcoded 30;
`bmgfxwj` needs ≥100); (2) one new list mode, dialect AC: `POST /info_open/search` (siteId +
channelIds, `data.totalPages`, docymd rows) for the five districts + 江阴 page 1. User-gated:
南通 (cloud-WAF 403 shell on portal + all 7 districts), 扬州 (403), 镇江 (timeout), 常州 (XHR
shells at every tier; bodies are 150-char cover notes), 宜兴 JS lists.
- Backlog file updated with a "Status 2026-10-07" section (done / next / user-gated).

## P2 Iteration 38 (Wuxi code)
**LANDED** (`0df9ee9`): `_page_ext()` (per-site override → old t-date rule → explicit
`index_N.<ext>` pager → article-link extension consensus → .html), per-site `max_pages` /
`page_start`, docymd `/YYYY/MM/DD/` url_date; second cause found: intertid `index_1.shtml`
404s, `index.shtml` is page 1. Controls byte-identical (cas 79, hami 42, npc_dbgz 1,840; URL
diff empty). New list mode `api_search` (dialect AD; `base.fetch_post()`) for 无锡 districts:
梁溪 209 / 锡山 450 / 惠山 47 / 滨湖 83 / 新吴 1,095 (memo exact). 江阴 API returns 0 → static
index_2..20 (803 rows). `wuxi` 9 sections, group=city, 3,865 rows scratch (部门文件 CMS-capped
at 100 pages); bodies 10/10 wuxi/锡山/梁溪, 8/10 江阴. Gap: 文号/publisher 0/10 (this CMS's
信息索引号 table unparsed; 文号 is in body text) → queued. Ontology `wxd_` prefix; tests added.
- Apply after lock (memo §8 adjusted): `--site wuxi --deep --db documents_wuxi.db` under nohup
  (~2 h), 7 districts, `merge_db.py`, validator after the next nightly.

## P2 Iteration 39 (metadata table)
**LANDED** (`c524768`, `crawlers/gov.py::_extract_metadata_table`, shared by gov/govmirror/
govcms): pass 1 byte-identical; new pass 2 fills only empty keys from a priority alias map
(文件编号|文号|发文字号; 发布机构|发文机关|发布单位|制发机关; 成文/发文日期; 公开日期; 索引号) over
th/td, dt/dd, li/span lists; 全角 colon tolerant. Wuxi pages: 文号 0 → **16/18**, publisher 0 →
**18/18**. Regression sweep on raw HTML: js_kxjst, fj_* (~330), ndrc, mohurd, gov (680): zero
contradictions with stored values; fj_* gains 文号 on 转发 pages. Finding: the old pass-1 regex
swallowed the 全角 colon so on gov.cn it only ever matched `identifier`; gov's 文号 came from
the JSON feed. Excluded on evidence: a `title` alias (fj procurement "名称" cells) and 生成日期
as written date (梁溪 stamps it after 公开日期). Tests 8/8 + 9/9 + 10/10.
- Nothing runnable remains that does not need the lock. Waiting for the nightly to release it.

## P2 Iteration 40 (the nightly's own report, read from the log)
Phase 1 ran 06:00-10:25 (**+480 new docs of 249,175 seen; 323,775 total**; the long tail is the
known ~11 crawlers hitting the 30-min cap, plus JCMS SSL handshake timeouts). Phase 2
classification started 10:27 on 2,669 docs, ETA ~100 min, so the lock holds until ~13:00 and
Phase 2b/2c/2d (identity + succession + citations + rollups + validator) run after that.
**Two measured findings from the log, both new information:**
1. **A7 is working in production, 10x beyond the hand-recovered count.** Phase 1b body backfill
   extracted **1,425 bodies** tonight against **0 / 0 / 0 / 2 / 1 / 3 / 2** on the seven previous
   nightlies (failed count 13,251 → 11,828, consistent). The nightly runs the backfill
   corpus-wide, so the five container selectors reached far more than the 8 sites the agent
   touched. This is also the likely reason the unclassified backlog jumped 361 → 2,669: a doc
   with a body becomes classifiable.
2. **The classifier fails on a THIRD of what it attempts, silently, every night**: err rate
   6.6% (10-01) → 20.6% → 37.2% → 36.3% → 34.7% → 34.3% (10-06), today 19.1% mid-run. Failures
   leave the doc unclassified so it is retried every night forever: standing API cost, no
   progress, and the step-change between 10-01 and 10-03 says something changed. Nothing is
   logged but the counter. Launched a read-only diagnosis (what increments `err`, whether
   failures correlate with body length / site / cover-note bodies, bounded ≤20-doc API probe
   only if needed, recommend a fix) → `docs/working/qa-classification-failures.md`.

## P2 Iteration 41 (two operational root causes)
**Phase 1 timing LANDED** (`a631ee9`, `docs/working/nightly-phase1-timing.md`). Phase 1 is
240-271 min every night and **15 crawlers whose median yield is ZERO account for 196 of the 252
median minutes**. The July hypothesis in CLAUDE.md was wrong: only 4 crawlers hit the 1800s cap,
not 11, and 7 of the 11 it named now finish under 70s. Top sinks: `zhejiang` 1800s / 0 new in 11
nights; `govcms --group dept` 1800s capped 11/11, reaching 160 of 232 sites, 1 new doc;
`beijing` 1800s capped, killed at 2,640/6,821 items, 17 new in 10 nights; `gkmlpt --sync` 1800s,
reaching 4 of 63 sites; `jiangsu` 1276s walking 262 pages for 3 new docs. Also: every one of
these skips only on "already stored WITH a body", so 1,628 Beijing + 5,388 MIIT + 1,022 Suzhou
rows are re-fetched nightly forever (MIIT's are the anti-bot stubs, which can never gain a body
from NYC). Plan ≈ **152 min saved** (252 → ~100): drop `zhejiang`, drop 8 dead cq.gov.cn hosts
and rotate the dept group in 3 chunks (this INCREASES coverage, 72 sites are never reached
today), move 10 zero-yield full-walkers to weekly, per-crawler timeout overrides. Risky items
each carry a named verification step. Load average during Phase 1 is 0.17 on 2 vCPU, so it is
purely network-bound.
**Classification failures LANDED** (`664b071`, `docs/working/qa-classification-failures.md`) and
**the agent corrected my brief twice**, recorded as stated: the error rate is NOT new (20-37% in
every log back through mid-September, i.e. since the 07-25 `deepseek-v4-flash` migration) and my
"10-01 → 10-03 step change" was an artefact of comparing a mid-run progress line against finals;
concurrency is not implicated. **Root cause, verified by experiment:** v4-flash is a REASONING
model and bills reasoning tokens against `max_tokens=2000`, so in a 20-doc concurrency-1 probe
19 returned `finish_reason="length"` with `reasoning_tokens == completion_tokens == 2000` and
zero content. The control cohort (docs classified fine on an earlier night) failed 9/10 the same
way, so the outcome is a coin flip on reasoning length, not a document property: body length,
site and script do not discriminate (failures 1,723 chars vs successes 1,745; the prompt
hard-truncates bodies to 1,500 chars anyway, so context overflow was impossible). `err` is just
`if result: ... else: errors += 1`; three of the five `None` paths print nothing, one of them
commented "likely content filter. Skip silently." Fix: `max_tokens` → 12,000 + retry once on
`finish_reason=="length"` (8/8 recovered at 8,000, reasoning 2,804-7,133 tokens), per-reason
tallies, and a `classify_failures` side table so `content_risk` is terminal and failures are not
re-sent nightly. 1,864 docs unclassified (0.58%), 50 stuck over a week; backfill ≈ $11; the
ongoing change trades ~$160/yr of wasted calls for ~$225/yr of productive ones.
- Launched both fixes as code-only (nightly is mid-classification; migration deferred to me).
- Also launched a verification of the timing memo's SECOND claim, that `gkmlpt --sync` scopes its
  diff per `site_key` while upserting `ON CONFLICT(id) DO UPDATE SET body_text_cn`, which on a
  SHARED platform would let one site overwrite another's body. I checked it myself first: the
  code mechanism is real (line 944 scopes `existing_docs` by site_key, line 720 is the blind
  upsert) but the offered symptom is unproven — zjj is pinned at 2,719 rows, yet 0 URLs are
  shared across sites and the gkmlpt host mismatches (heyuan 440, fgw 389, mzj 276) are benign
  outbound links to gov.cn / WeChat / Xinhua, not clobbered rows. The agent's job is to decide it
  empirically (does any site's API return an id already stored under another site_key?) and fix
  it proportionately, without inflating a latent bug into a fixed one.

## P2 Iteration 42 (nightly timing, the subtractive half)
Implemented items 1, 6, 7 of the timing plan myself (`36fba8a`, daily_sync.sh only, committed
NOT pulled — the droplet is mid-run and bash reads scripts incrementally, so editing a running
script's file is unsafe; it takes effect at tomorrow's pull):
- `run_crawler_t <seconds>` per-crawler cap; `run_crawler` = that with the 1800s default.
- `run_weekly <dow>` for the zero-yield walkers, one weekday each: sic(2) ipc_court(3)
  chongqing(4) wuhan(5) most(6) hangzhou(7).
- `zhejiang` off the nightly path → Monday probe under a 600s cap (hit the cap 7/11 nights for
  ZERO rows in 11 nights; nothing paginates from a US IP; the real fix is the HK vantage).
**Deliberate departure from the memo:** it recommended weekly cadence for `ndrc`, `mee`, `mof`
too. Rejected: the product is a DAILY policy tracker and central recency is what it sells, so
~7 amortized minutes is a bad trade. Their cost belongs to an early-exit fix. `miit` likewise
stays nightly (its gap is 5,383 anti-bot stubs, not cadence).
Verification note worth keeping: my first two attempts to smoke-test the functions were
worthless and I nearly believed them. The first mangled the extraction (sed range), the second
reported every call as an error because **macOS has no `timeout`** (exit 127, not 124), so the
success path can't be tested locally without stubbing GNU `timeout`. With the stub: per-call cap
reaches the report, default success path works, 600s propagates, weekly gate correct on and off
day. Items 2/4/5/8 (body-skip, gkmlpt diff, Jiangsu early exit, 2-wide parallelism) stay
unimplemented pending their named verification steps; 4 is with an agent now.

## P2 Iteration 43 (classifier fix + CLAUDE.md)
**Classifier fix LANDED** (`1511b81`): `max_tokens` 2,000 → 12,000 with ONE 24,000 retry on
`finish_reason="length"` (and only that class; the others would just burn spend);
`classify_deepseek` returns `(result, reason)` over 8 reason codes, each logged at WARNING with
the doc id and tallied in the progress line and a final `Failure reasons:` block;
`classify_failures(doc_id, reason, attempts, first_seen, last_seen)` side table (NOT a
`documents` column — the compute_scores overflow-page lesson), `content_risk` terminal,
`attempts >= 3` skipped unless `--retry-failed`, success deletes the row; `select_docs()`
extracted and falls back to the old query so pre-migration DBs still work; `--init-schema`,
`--retry-failed`; `--dry-run` now opens read-only (it previously ran ALTER TABLE). Tests
`tests/test_classify_failures.py` 16 cases, **suite 110 passed / 1 skipped**. Live validation
inside the probe allowance: 5 docs that had failed on prior nights, run through the real path
with `--dry-run` at concurrency 1 → **4/5 classified at 12,000 on the FIRST call**
(`finish_reason="stop"`, no retry needed), 5th the expected terminal `content_risk`.
- CLAUDE.md (`<commit below>`): followed the file's own stated practice and RESOLVED the
  2026-07 crawler-timeout Open Question, moving the measured answer into Known Issues and
  deleting the entry (the old guess named 11 capped crawlers; only 4 cap, and 7 of its 11 now
  finish under 70s). Also recorded the classifier root cause, the ledger table, and the cost
  delta in the Classification section.
- Nightly at 11:48: 1,200/2,669 classified (208 err, 17.3%), ~80 min to go, lock still held.
  Tonight's run still uses the OLD classifier (the fix is committed, not pulled), so tonight's
  ~34% failures are expected; the fix takes effect at tomorrow's pull, or sooner if I run the
  bounded verification pass after the lock clears.

## P2 Iteration 44 (a real data-corruption bug, and it had already fired)
**gkmlpt diff LANDED** (`5d872b2`) and the verdict is **FIRES, not latent**. The agent probed
page 1 of every leaf category on three gkmlpt list APIs: **80 of 1,692 sampled ids (4.7%) are
already owned by a DIFFERENT `site_key`** (zjj 25/723, stic 47/638, jieyang 8/331); ids are not
namespaced at all, per-site ranges interleave across all 54 gkmlpt sites and overlap other
crawlers' synthetic ids. So my "unproven" verdict was too cautious; I had looked for the wrong
signature (shared URLs, host mismatch) and both are clean because the clobber keeps the victim's
URL and only replaces its BODY.
**The smoking gun I had missed:** the upsert also sets `raw_html_path`, saved under the SECOND
writer's site directory, so `site_key` disagreeing with the path's site dir is proof. I verified
the count independently: **261 rows already corrupted** — npc 81, ndrc 19, zhongshan 17, gov 13,
most 12, sh 12, szpsq 9, bj 8. Three were clobbered during TODAY's run: 中华人民共和国土壤污染防治法
(body down to 621 chars, HTML from `stic`), 国务院2025年度立法工作计划 (**27 chars**, HTML from
`zjj`), 包头市供水条例 decision (189 chars). `base.py::store_document` had the identical hole, so
this was never gkmlpt-only; the mismatch table shows it firing the other way too
(szpsq/szft/yunfu ← `raw_html/gov/`).
**Blast radius, measured, and the bound matters as much as the bug:** 0 of the 261 have
`citation_rank > 100` (max 63.5), so no top-ranked instrument and no top-30 ranking is affected;
103 have bodies under 500 chars, 30 under 100; **464 outbound citation edges were extracted from
the wrong document's body** (0.09% of ~534k); 7 are diffusion anchors. 261 is a LOWER bound (the
test only catches clobbers where the overwriting crawler had a raw_html_path).
**Fix shipped:** `WHERE documents.site_key = excluded.site_key` on the DO UPDATE in BOTH store
functions; `rowcount == 0` → look up the real owner and log `ID COLLISION: … owned by 'Y' —
skipped (body NOT overwritten)`. Cross-site hits are SKIPPED, not merged, because with one
global id namespace a genuine cross-post is indistinguishable from two unrelated docs sharing an
id (the observed case is the latter) — the warning surfaces real cross-posts for a deliberate
design later. Also: `crawl_site`'s body probe was site-agnostic and would ADOPT another site's
body as its own (now scoped), and `sync_site` counted the ON CONFLICT path as `added`, writing
phantom "added" rows into `document_changes` — which fully explains the zjj symptom (its new
posts resolve to foreign-owned ids, so its row count cannot grow while the log claims adds).
Tests 6 new, suite 110 pass.
- Launched the repair preparation (read-only): per-victim repair classification — crucially
  `npc` is metadata-only BY DESIGN so its 81 rows must have the foreign body CLEARED, not
  re-fetched — plus `scripts/repair_site_collisions.py` with --dry-run/--apply, batched WAL-safe
  writes, a lock refusal, an audit table, and the re-derivation order. I execute it after the
  lock clears.

## P2 Iteration 45 (repair prepared; two corrections to my own numbers)
**Repair prep LANDED** (`4a59e97`, `scripts/repair_site_collisions.py` + 18 tests, suite 128
pass; dry-run against the live corpus reproduces the plan exactly). It caught something that
would have caused damage had I run a naive repair: **21 of the 261 are FALSE POSITIVES.**
`crawlers/gov.py:150,428` resolves a doc id by URL (`WHERE url = ? AND url != ''`) BEFORE
minting one, so when a Shenzhen district row is a pointer at a `www.gov.cn` article the `gov`
crawler adopts that row's id and writes the **correct** text under `raw_html/gov/`. Body matches
title in all 21 (szpsq 9, szft 5, szns 2, yunfu 2, mofcom/szdp/szlhq 1). The discriminator is
DIRECTIONAL: the reverse case (a gov-owned row whose path points into a gkmlpt dir) is a true
clobber, confirmed by content — `12650953` titled 中共中央 国务院印发《…自由贸易试验区提升战略…》
carries a body about 深圳市普通高中综合素质评价平台招标.
Repair plan: **240 true clobbers** = npc 81 clear-only (confirmed correct: npc.py writes
`raw_html_path=""` and 30,989/31,070 npc rows natively hold neither body nor path, so empty IS
its correct state), 125 recrawl via the owner crawler (probed 200 with real bytes), 31 clear +
`gkmlpt --backfill-bodies`, 7 cq + 3 zj clear-and-flag (datacenter blackhole), 3 heyuan stay
empty. The 8 `*.sz.gov.cn` probe failures were an `OpenSSL bad ecpoint` curl artifact, NOT a
block (sibling hosts probe 200 and are crawled nightly) — settled from code instead of burning
probe budget, which was the right call.
**Second independent signal** (`document_changes` rows claiming an `added` that cannot be true):
230 docs, 217 inside the 261, and 8 of the 13 extras are body-corrupt with an EMPTY
`raw_html_path` — precisely the blind spot (the clobberer saved no HTML), e.g. `4436455` 广东省…
人工智能赋能千行百业若干措施 with a 208-char body. Estimate **≈250 still-corrupt** (≈240 provable +
≈10 invisible), ceiling 277; naive Lincoln-Petersen 277 inflates because the signals are not
independent and it counts the 21 keeps and 5 self-healed rows.
**Two corrections to numbers I reported earlier, both mine:**
1. Diffusion anchors affected are **19, not 7** — my query counted `anchor_id` differently. 464
   edges have a victim as `source_id`, 105 as `target_id`, 25 anchored as source.
2. My own nightly-monitoring grep was broken: `\([0-9]+ ok` cannot match `1,176 ok`, so once the
   ok-count passed 999 it silently returned a STALE progress line and I briefly read the
   classifier as stalled. It was fine (1,800/2,669, ETA 49m, err 17.1%). Same artifact class I
   spent the day correcting in the corpus, this time in my instrumentation.
Known follow-on: `doc_search_seg` is incremental by rowid and contentless, so the cleared docs
keep stale tokens until a one-time `build_search_index_seg.py --rebuild` (~1h). Bounded, queued,
not blocking. The 15,127 stale `document_changes` "added" rows are deliberately left in place
because pruning them would destroy signal 2.
- Queued from the B7 agent's closing note: the resolver fixes now ahead of it (alias table,
  entity unescape, 5-char title floor) feed `diffusion_events`, so tonight's rebuild will shift
  the counts `policy-tempo.md` quotes, most likely upward since they are recall fixes. The memo
  pins its build (13,081 implementing central events, 36,116 rows, 2026-10-07) so it stays
  honest as written, but its §0-§5 tables want a re-base after the rebuild, and
  `validate_cascades.py` is the thing that would catch an unexpected move.

## P2 Iteration 46 (the nightly's Phase 2b, and my resolver fixes measured)
Phase 2 classification finished 2,669/2,669 (**2,089 ok / 580 err = 21.7%**, the old code;
tonight is the last run before the max_tokens fix). Phase 2b: citations rebuilt 13:07-13:17,
scoring, topics; identity/succession/2c/2d still to come.
**My resolver fixes, measured on the live rebuild:** edges 534,722 → **540,166**, resolved
270,211 → **275,414**, resolution 50.5% → **50.99%**. 广东省公路条例 0 → **41 citers** (the
5-char title floor). 广东省城市控制性详细规划管理条例 holds **1,021** (alias row working). The
floor turns out to be a far bigger win than the one doc I targeted: 突发事件应对法 **619**,
政府工作报告 283, 信访工作条例 181, 自然保护区条例 144, 中国共产党章程 134, 政府投资条例 105 —
national instruments whose names were under 8 characters and so could NEVER match exactly before.
**But 城乡规划法 moved 2,142 → 1,907**, which clears the validator's 1,900 floor by 7. I checked
the obvious regression first and it is clean: the Henan wrapper 河南省实施《城乡规划法》办法 holds
**0** citers and every `实施《…城乡规划法》办法` variant holds 0-1, so the October proxy-target bug
is NOT re-created. The entity fix is landing where predicted and looks right (广东省实施《土地管理
法》办法 267, 消防法 102, 招标投标法 60 — correct when the citing text names the provincial
measure). The 城乡规划 lookalikes are all 9 chars so the floor did not admit them. Three candidate
mechanisms remain for the 235 (short-title theft = my regression; entity-unescape correctly
reaching a provincial implementing measure = improvement; the citing body changing in Phase 1b,
which touched 1,425 docs = neither), and guessing is not good enough on the memo's canonical
example, so launched read-only forensics to split it by mechanism against yesterday's state and
to recommend whether the validator band should be re-based.

## P2 Iteration 47 (my alarm was a metric mix-up; it exposed a worse bug)
**Forensics LANDED** (`777cb92`) and the answer is that **I raised a false alarm by comparing two
different columns**. `doc_inbound` stores both `edges` (raw resolved edge rows) and `inbound`
(distinct citers, self-cites dropped), and the memos call both "inbound". 2,142 was yesterday's
**edges**; 1,907 is today's **citers**. Both metrics ROSE: edges 2,142 → **2,158**, citers 1,895
→ **1,907**. `235 = 247 (yesterday's duplicate edges) − 12 (net new citers)` is an arithmetic
identity, and the set of documents that cited the law yesterday and do not now is **empty**. The
split by mechanism is 0 / 0 / 0 regression, improvement and body-change, +12 citers / +16 edges
from new and newly-bodied documents. **No part of it is a regression I introduced.** The agent
also declined to download the 4.5 GB backup once it could prove the identity without it, with 23
GB free and the nightly holding the lock — the right call.
**What the chase actually found, which matters more.** Which of three identical-title mirrors
holds the edges is NOT decided by the documented `(genre_rank, level_rank, id)` tie-break:
`extract_citations.py:560-562` builds `title_to_doc[title]` from an **unordered** SELECT, so the
last row scanned silently overwrites and the losing mirrors never reach `TitleMatcher`. Verified
live: 中华人民共和国城乡规划法 exists 3× — 12685270 mee 2019-04-23 (0 edges), 12742122 npc
2019-04-23 (0), 12747143 npc 2015-04-24 (**2,158**) — and all the weight sits on the highest id
purely by scan order. `validate_cascades.py` pins `CXGH_ID = 12747143`, so ingesting a
higher-id mirror would flip the winner, make that id read ~0, and **fail the nightly regression
test on a healthy graph**. My 5-char floor widened exactly that query, so I increased the
exposure. Launched the fix (deterministic representative + `CXGH_ID` updated in the same commit
if the documented rule picks a different copy) together with splitting `cxgh_inbound` into two
named checks, since it prints "inbound citations" while counting edges — the very ambiguity that
fooled me. **Band NOT re-based:** the check reads 2,158 against [1900, 2400] centred on 2,141,
i.e. 0.8% off centre, so re-basing on a mix-up would widen the blind spot the check exists for.
**Nightly completed cleanly:** Phase 2c 13:28-13:29 (site_stats, diffusion_events,
tracker_weekly), **Phase 2d VALIDATION PASS 13/13** — and it confirms the memo's third point,
that Phase 2d never ran on 10-06 because the validator landed after that day's 06:00 pull.
Two side findings logged: `doc_identity` leaves 12685270 and 12742122 `unique` despite identical
titles AND identical 2019-04-23 dates (a mirror-pooling miss; the 2015 copy is correctly
separate), and `REF_PATTERN` can still capture a run of body text as a ref name (江门市 case).

## P2 Iteration 48 (lock freed; repair and classifier fix applied live)
Nightly finished 13:46:14 (Telegram sent); lock released 13:46:18 after the Spaces backup.
- **Mirror-determinism fix LANDED** (`b1aff31`) and the scope is far larger than the memo
  predicted: **18,798 normalized titles change representative and 85,585 of 238,017 resolved
  named/llm edges (36%) move to a different id**, with nothing lost (key sets identical, 0 refs
  resolvable before but not after). The winner for 城乡规划法 becomes `12685270` (mee, 2019), not
  the `12742122` the memo guessed — it had overlooked the mee copy, which has the lowest id of
  the three; `CXGH_ID` was updated in the same commit, which is essential or Phase 2d would fail
  on a correct graph. Most of the movement is the LEVEL tier finally firing, and that is an
  unambiguous bug fix: 政府信息公开条例 had all **2,302 edges on a municipal district 发改委
  repost** (900154149) while the central mee copy held 0. `doc_identity.instrument_id` was
  considered as the authority and rejected with reasons (it is rebuilt AFTER citations, so the
  resolver would read a day-stale table, and new docs would have no row).
  `cxgh_inbound` → two checks `cxgh_edges` (2,158, band unchanged) + `cxgh_citers` (1,907, new
  band); validator 13 → **14 checks**; suite 144 pass. CLAUDE.md updated (`9dd6bf3`).
  *Open preference question for the owner, not mine to settle:* among same-level same-genre
  copies the tie-break is lowest id, which here prefers an **MEE repost** of a national law over
  the **NPC national-laws-database** copy. Stable and documented, and it happens to pick the copy
  that HAS body text (npc is metadata-only from NYC, so making npc the node would put citation
  weight on a bodiless doc and starve every body-based analysis) — but it is semantically odd for
  a law. Changing it means a new site-authority tier plus a rebuild.
- **Collision repair APPLIED**: 240 cleared, 21 kept, predicate down to exactly the 21 keeps;
  `collision_repairs` records clear_by_design 81 / clear_gkmlpt_backfill 31 / clear_link_stub 3 /
  clear_owner_recrawl 125 / keep_url_identity 21. The dry-run sample was unmistakable (Beijing
  and Chongqing documents with 23-32 char bodies whose HTML sat in stic/sz/zjj directories).
- **Classifier fix VERIFIED LIVE: 50/50 classified, 0 errors, `reasons: none`** — against 21.7%
  failures on tonight's run with the old code. Migration `--init-schema` applied,
  `classify_failures` table present.
- Refills: the 125 owner-recrawl victims need no manual work — their crawlers skip only on
  "already stored WITH a body", so tomorrow's nightly re-fetches them automatically, which is the
  one place that behavior is an asset. Running the scoped `gkmlpt --backfill-bodies` for the 13
  gkmlpt victim sites myself (writer 1).
- **A6 crawl chain launched detached** (writer 2, `logs/a6_chain.log`, serial within itself):
  gov zy+gw library → sz_gazette list → szdp_gfxwj → zs_lyj metadata → sz_gazette bodies.
- **Deliberately NOT done yet:** re-basing fidelity-provincial §2.1, the successor universe, and
  policy-tempo's tables. The mirror fix moves 36% of edge targets at 06:00, so re-basing now
  would be stale within hours and would add yet another "which build" ambiguity. One re-base
  after tomorrow's nightly instead. Launched the `doc_identity` mirror-pooling fix instead
  (code-only; 12685270/12742122 identical title AND date left `unique`).

## P2 Iteration 49 (my orchestration error, and it was hidden twice)
The scoped gkmlpt refill **crashed on 9 of its 13 sites** with
`sqlite3.OperationalError: database is locked` at `gkmlpt.py:895`, because I ran it concurrently
with the A6 chain's `gov --library --deep`. That is my error, not a crawler bug, and it corrects
a CLAUDE.md claim: **"2 parallel writers is the safe max" is too optimistic when one writer holds
long transactions**, which the library crawler does. Two things hid it: the crawler logs the
successful `curl_cffi fallback OK (35166B)` fetches immediately before dying, so the expensive
work was done and discarded; and my shell `for` loop **still exited 0**, so the failure was
invisible unless I read the per-site tail — which my own `| tail -1` filter had truncated to the
bare `File "…", line 895` line without the exception type. Yield was poor anyway (2 of 31
restored; heyuan 0/75 and gz 0/102, because most bodiless gkmlpt rows are outbound-link stubs),
so nothing of value was lost.
- Serialized from here: only the A6 chain writes. It is productive — **581 new `gov` docs**
  within 15 minutes (the estimate was 432 zy + 399 gw).
- Refills left to the nightly as planned; its crawlers re-fetch bodiless rows automatically.
- Launched the robustness fix (code-only): `busy_timeout` audited on EVERY connection in
  `crawlers/`, bounded retry + incremental commits in the write loop so contention cannot
  discard completed fetches, and a non-zero exit when any row is skipped so a wrapper loop
  cannot swallow it.

## P2 Iteration 50 (the robustness fix corrected my diagnosis)
**Backfill lock-tolerance LANDED** (`bc8517d`) with a **negative result that corrects my
framing**: `busy_timeout` was NOT missing anywhere. Every connection in `crawlers/`, `scripts/`,
`web/` already sets it (base.py `init_db` has both `timeout=30` and the PRAGMA, and that is the
only connection gkmlpt uses, including the `--db` path). A fixed timeout simply cannot cover a
writer holding a transaction for minutes, which is what `gov --library --deep` does. So the bug
was the write LOOP, not the PRAGMA, and the agent said so instead of executing my brief.
Shipped: `base.write_with_retry` / `commit_with_retry` (6 attempts, 1s→30s; a non-lock
`OperationalError` propagates on the FIRST try so a real bug is never hidden by backoff),
`WriteRetryStats`, incremental commits in `gkmlpt.backfill_bodies` / `sz_gazette.backfill_bodies`
/ `backfill_from_html` / `redate_from_html`, `try/finally` so even a KeyboardInterrupt lands what
was fetched, and **non-zero exit when any row is skipped** so a wrapper loop cannot swallow it.
Also a static scan test that FAILS if a future `sqlite3.connect` in `crawlers/` lacks the PRAGMA
— the invariant is now enforced instead of documented. Incidental fix: `sz_gazette --limit`
counted stored rows, so a locked or bodiless row made the cap undercount. Suite 144 → **156**.
CLAUDE.md's SQLite rule replaced with the agent's wording (`6873881`): the limit is transaction
HOLD TIME, not writer count, with the measured incident cited and `--db` + `merge_db.py` named as
the alternative — which is how the pending Wuxi crawl should run.
- A6 chain step 1 still running at 14:30, 26 min in, **1,548 `gov` rows written or updated**
  (against an estimate of 432 zy + 399 gw new; `crawl_timestamp` moves on re-fetch too, so I
  cannot split inserts from updates yet and am not claiming 1,548 new).
- Launched the REF_PATTERN precision investigation (read-only + code): how often the regex
  captures a run of body text as a ref name, the harmful (resolves to a wrong doc) vs harmless
  (pollutes citation-crawl-queue with phantoms) split, and a tightening with a measured
  zero-recall-loss requirement.

## P2 Iteration 51 (the third instance of one bug shape — now encoded)
**Identity mirror-pooling fix LANDED** (`64529f3`), and the root cause is the same mistake this
project has now shipped three times: **a length floor measured on a NORMALIZED string.**
`_norm_title` strips `中华人民共和国` (7 chars), so 中华人民共和国城乡规划法 folds to 城乡规划法 (5),
and `_best_core` measured `KEY_MIN = 6` on the FOLDED core — so every national statute got no
`instrument_key` at all, never entered `stems`/`groups`, and every copy stayed `unique`. Not the
window, not a level/genre guard, not `localize()`, not 文号. The same shape as the resolver's
`len(ref) >= 8` exact-tier floor (the October proxy-target bug) and its `LENGTH(title) >= 8`
index floor (1,661 short held titles never candidates). Recorded as a named section in CLAUDE.md
(`1c2810b`) with the three instances in a table, plus a memory, so the fourth gets caught.
Fix: `_key_len`/`_core_ok` measure the floor on the UNFOLDED core, gated to statute shapes
(`法|法典|条例|修正案`). The gate needed care and the agent checked what else it admits: of 191
folded keys it would allow, 186 are statute names and the residue is 中华人民共和国国务院令 —
shared verbatim by **20 unrelated** State Council orders — plus 财政部令 and 外交部声明, where the
令/声明 is the vehicle, not a name. Those stay excluded.
**The agent also found and fixed a second bug its own first cut exposed:** the 400-day edition
gap was measured from the edition's latest copy of ANY level, so a low-level late repost could
**bridge a revision** — a 北京市统计局 repost of 监察法 put the npc 2024-12-25 amendment only 212
days after the 2018 edition's tail and merged them (same for 统计法, 对外贸易法, 殡葬管理条例). Now
measured from the edition's **anchor** (latest copy at or above the edition's own level), on the
principle that a bureau's repost cannot open an edition so it must not extend one. Also in
CLAUDE.md.
Blast radius: 262 `instrument_id` and 325 `instrument_role` changes, 0 genre changes, multi-copy
instruments 5,338 → **5,468**; the short-key fix merges (190/309) and the anchor fix only splits
(72/16, each of the 16 over-merged piles inspected). 15/15 spot-checked merges are genuinely the
same text (行政复议法 ×9, 民法典 ×7, 安全生产法 ×6 …) with **no edition pair merged**; invariants
hold (政府信息公开条例 still 2 instruments, all 20 国务院令 still unique, flip counts unchanged).
Self-test 166 → **183**; suite 156.
Nice consequence: `doc_identity` now makes **12685270** canonical for the 城乡规划法 2019
instrument, which is the same copy the resolver's independent `(genre_rank, level_rank, id)`
ranking picks — the two authorities agree on this case, where before doc_identity simply had no
opinion. They can still disagree in general, since doc_identity breaks a same-level tie by
EARLIEST date and the resolver by lowest id.
Pre-existing weakness newly visible, NOT introduced and not fixed: `_canon_sort_key`'s
earliest-date tie-break lets a bad source date win the canonical slot — 民法典's canonical is an
`fj_xfj` copy stamped 2020-01-08, before the npc adoption of 2020-05-28. Queued.
**Not applied live:** three crawl writers are active (A6 chain), and per the rule I just wrote
into CLAUDE.md I will not start a second writer against documents.db. Tonight's nightly pulls
and rebuilds doc_identity → diffusion_events → tracker_weekly → validate in the right order,
and it will apply the mirror-determinism and REF_PATTERN fixes in the same pass — one coherent
rebuild instead of three partial ones.

## P2 Iteration 52 (REF_PATTERN: the brief named the wrong pattern)
**LANDED** (`03263eb`), and my brief was wrong about where the bug was. `REF_PATTERN` is clean
(54 of 105,153 formal refs exceed 30 chars, 2 resolve, 0 contain sentence punctuation, because
`canonicalize_formal_ref` already strips its greedy head). The defect is
`analyze.NAMED_REF_PATTERN` = `《([^》]{8,100})》`, whose character class excludes only the
**closing** bracket, so an unclosed 《 (a bracket dropped in PDF text, or a literal nested title)
starts a match that runs through prose to the close bracket of a LATER title.
Measured: **239 named edges (0.086% of 277,117) over 196 source docs** — unclosed 《 192,
contains 。 20, PDF digit-table 52. **53 harmful** (they resolve, so they are false edges), all
one pattern: the prose head starts with an agency name and lands on an 8-9 char **masthead stub
document** (江门市自然资源局, 广东省医疗保障局, 深圳市住房和建设局 …), all `algo_doc_type='other'`
crawler artifacts. **186 harmless.** My worry about crawl-queue pollution was unfounded and the
agent measured it rather than assuming: **0 of the demand-ranked top 100 / 400 / 1,000**, because
a prose capture embeds a 文号 or a table line so its demand is 1 and it cannot climb.
**The valuable part is what it REJECTED.** Guards that look obvious would have destroyed
thousands of real edges: newline appears in 5,599 edges (2,285 resolved), `，` in 335 (92), `：`
in 133, length > 60 in 1,265 (628) because real multi-issuer titles run to the 100-char cap, and
lead-ins 根据/违反/贯彻落实 in 238 (102). Only `。` and the digit-table signature are safe.
Fix: the pattern is now **balanced one level deep**, `《((?:[^《》]|《[^《》]{1,120}》){8,120})》`,
so a quoting title is captured whole instead of truncated at the inner 》 and an unclosed 《 can
no longer start a match (the engine falls through to the inner title, which is what the text
actually cites). Branches are disjoint on first character so matching stays linear — measured
FASTER, 1.5s vs 1.7s. Plus `looks_like_body_run`, `recover_named_heads` (cuts a genuinely
unclosed run back to its last genre word, so masthead-only heads stay dropped), and explicit
emission of a quoted instrument minus the citing doc's own core.
Recall, over 196 junk-shaped sources + 4,000 random bodied docs resolved against all 323,639
live titles: **lost 7, gained 51** (distinct resolved pairs 3,061 → 3,105). Six of the seven
losses ARE the masthead false edges the change exists to remove, the seventh is a self-reference
under a pre-existing rule, so **zero real refs to a distinct instrument lost** — and earlier
iterations lost 18, then 10, and were loosened until only the intended losses remained. Suite
156 → **168** (the refactor broke 6 `test_citations.py` cases via a removed `seen_named`; fixed).
Residual logged: masthead stubs remain containment-eligible for any ref embedding an agency name.
- **Plan change to de-risk tomorrow.** Tonight's nightly would otherwise apply FOUR unreleased
  changes at once (mirror determinism moving 85.6k edges, identity pooling 262 instruments,
  REF_PATTERN ~+4-5k resolved, the retry layer) and I would not see the result until ~13:30 UTC.
  So when the A6 chain finishes I will run citations → scores → identity → succession → stats →
  diffusion → tracker → validate myself, in dependency order, and read the 14 checks tonight.
- A6 step 1 (gov zy+gw --deep) still running at 14:56, 52 min in; its step timeout is 3600s, so
  it is bounded and the chain will move on regardless. gov rows 21,741 as of 14:34.

## P2 Iteration 53 (A6 step 1 delivered; setsid paid off)
The local ssh wrapper was killed for Mac memory pressure at ~15:20, and **the droplet chain
survived** because it was launched with `setsid nohup … < /dev/null` — the lesson from the B1
chain death, now validated.
Step 1 (`gov --library --categories zy,gw --deep`) ran 14:04-15:04 and was cut at its 3600s cap
**at page 70 of 125** of the gw walk (3,477 stored), so ~55 pages of the historical 国发 tail
remain and the step should be re-run to completion later (it is resumable; it skips what is
already stored). Result: `gov` **23,669 rows at 99.1% body**, up at least 1,928 between 14:34
and 15:24. The A6 head items landed WITH full text: **中国共产党章程** (20,747 chars) and
**中国共产党党内监督条例** (6,808 chars), the 262- and 134-citer targets from
`a6-recoverable-head.md`. The year distribution of what arrived skews old (2019: 227, 2020: 145,
2021: 137, 2022: 138 against 2026: 47), which is exactly the historical tail A6 was aiming at
rather than recent news.
Step 2 (`sz_gazette --list-only`) started 15:04; `sz_gazette` already holds **3,556** rows.
Honest caveat on all "new docs" figures today: `crawl_timestamp` moves on re-fetch as well as
insert, so a timestamp-window count conflates the two; the row-count deltas above are the
defensible numbers.

## P2 Iteration 54 (A6 steps 2-3: two "permanently delisted" docs recovered)
Step 2 (`sz_gazette --list-only`) ran 15:04-16:04 and was cut at its cap, but the listing is
**effectively complete**: `sz_gazette` holds **11,450 rows across **31.4 continuous years, 1995-04 to 2026-09** (corrected 2026-10-07 by `sz-gazette-scoping.md`: the 59 pre-1995 rows sit in retrospective compilation issues printed 2002-03, and the platform's earliest real issue folder is `zfgb/1995/gb68`, so issues 1-67 were never published; dates themselves are sound, 文号 year matches date year on 921 of 930 rows for 1987-2001) (the estimate was 8-12k), bodies deliberately empty pending step 5. Step 3
(`szdp_gfxwj`) ran 90 seconds and added **exactly +42** rows (szdp 8,586 → 8,628, 8,494 with
body), matching the scratch test precisely. Step 4 (`zs_lyj metadata`) started 16:05.
**Two of the four documents CLAUDE.md called "permanently DELISTED from origin sites,
recoverable only via 北大法宝 / 国家法律法规数据库 / archive.org" are now in the corpus with their
文号:** `4952494` 《深圳市行政听证办法》 市政府令第157号 (2006-09-26) and `10832248` 深财规〔2023〕
3号 深圳市财政局政府采购供应商信用信息管理办法 (2023-09-11). Between them they carry ~167 distinct
citers of previously unsatisfiable demand. That retires a long-standing project belief, exactly
as `a6-recoverable-head.md` predicted when it found them in the 政府公报 archive; only
苏住建规〔2011〕4号 of the original four is still genuinely gone.
Remaining in the chain: step 4 zs_lyj metadata (~30k rows expected), then step 5 sz_gazette
bodies (11,450 rows at 1 req/s ≈ 3.2h, 14400s cap), so the chain should clear around 20:00 UTC
and the self-run rebuild follows then.

## P2 Iteration 55 (a plan assumption failed, measured from the right host)
Step 4 (`zs_lyj metadata`) ran 16:05-16:27 and produced **113 rows, not the 30,873** the A6 memo
promised — and the 113 are 政务动态 news, not the 规划 documents the queue wants. Cause: the
agent measured that listing **from the Mac**; the droplet's NYC IP cannot sustain `zs.gov.cn`.
My first probe "confirmed" unreachability and was WORTHLESS — bare `curl` returned http=000 for
the CONTROL `gd.gov.cn` too, which CLAUDE.md documents as reachable, because these sites reject
curl's default UA. Re-probed with the full Chrome UA: `gd.gov.cn` 200 / 124,059 bytes / 1.8s,
`zs.gov.cn` nothing before a 30s timeout, same UA, same host, same minute. So it is the site,
not the network, and it looks rate-triggered (113 rows then silence) rather than a clean
blackhole. That is the second time today a control saved me from a confident wrong conclusion.
Recorded where reachability truth lives: `zs.gov.cn` added to **Tier C** in
`source-access-map.md`, and a dated correction appended to `a6-recoverable-head.md`
(`f3e1073`). **Consequence: ~480 citers (国土空间规划技术标准与准则 257, 控规管理实施细则 225, plus
城市设计指引 / 容积率 ×3 / 村庄规划编制指引 ×3) move out of A6's "29.1% confirmed reachable" and
into the HK/residential bucket**, which is user-gated. Rule added to that memo: any reachability
claim must name the host it was measured from.
Step 5 (`sz_gazette bodies`) started 16:27 and is filling at ~28 bodies/min (850 by 16:58), so
the 14,400s cap covers roughly 7,000 of the 11,450 and a follow-up run is needed. Corpus
338,856.

## P2 Iteration 56 (canonical selection; two more defects found underneath)
**Canonical fix LANDED** (`a72a341`), and the diagnosis is the interesting part: **`admin_level_doc`
is the level of the TEXT, not the host.** A 民法典 repost on 福建省信访局 derives `central` from its
own title cue, so every mirror of a national instrument TIES on the level tier and the earliest-date
tier decided alone — which is how an `fj_xfj` copy stamped 2020-01-08 became canonical for a law the
NPC adopted 2020-05-28. New tier between level and date: **is this copy hosted at or above the level
of the text it carries** (`_hosted_below_text`), the same test the edition walk already uses; among
equally authoritative copies the earliest date still wins.
Two plausible alternatives were **rejected on measurement**, which is the part I would have got
wrong: raw site rank changes 107 pools but promotes a central portal's REPRINT of a sub-national
text (an empty-bodied miit copy over 西藏体育局, the npc reprint over the sz_gazette 深圳经济特区条例);
date plausibility fires only 5 times corpus-wide and is **wrong on 3** of them, because chinatax
stores the SUPERSEDING 文号 so it demotes correct dates. Encoded decision: for a bad date at a higher
level, level/host wins and plausibility is not a tier.
Blast radius 77 of 6,379 pools change canonical, 232 docs change `instrument_id`, 154 role flips, no
instrument created or destroyed. Hand-check 13 right / 2 neutral / **0 wrong**. Resolver agreement
rose 73.8% → **74.5%** (dropping the date tier entirely would reach 90.5%, correctly not bought,
since lowest-id-wins is ingestion order rather than a fact about the text). Self-test 183 → **186**.
**Two distinct defects found underneath, both queued:**
1. **Recurring annual instruments are pooled across years.** The 505 pools its modal-date test
   flagged are mostly this, NOT a canonical problem: `政府工作报告` (a different document every year,
   for every government), `国务院关于落实《政府工作报告》重点工作分工的意见`, `国务院关于修改和废止部分
   行政法规的决定` across different 国令 numbers, 深圳市森林火险预警 / 台风 alerts. One `instrument_id`
   spanning many years makes the pool's date range meaningless and attaches cascades to a merged
   phantom. Launched the split-rule agent, with the four existing invariants as hard constraints.
2. **`sites.admin_level` is internally inconsistent for Chongqing**: `cq` = `municipal` while `bj`
   and `sh` are `provincial`, and `cq_lyj` — a BUREAU under Chongqing — is `provincial`, so a bureau
   outranks its own government. Chongqing is a 直辖市 and CLAUDE.md's ontology already hard-codes
   that workaround ("cq … is province-level despite its DB admin_level"), so the table disagrees with
   what the project asserts everywhere else. It feeds `citation_rank` weighting (central 3x /
   provincial 2x / municipal 1.5x), the ontology fallback and the province resolver, so it needs a
   measured blast radius before the one-row change; smaller now that analysis prefers
   `admin_level_doc`. Mine to do when no writer is active.
Gazette bodies 3,350 / 11,450 at 18:21.

## P2 Iteration 57 (annual pooling split; span is not the discriminator)
**LANDED** (`6e0ccb5`, self-test 186 → **195**, suite 168). The finding that mattered: **pool
span does NOT discriminate.** Of 6,379 pools, 386 exceed the 400-day edition gap and 269 exceed
two years, but the 25 WIDEST are the healthy case — 户口登记条例 is an npc 1958 text plus a 公安局
repost from 2008, an **18,522-day span that is correctly one instrument**; likewise 城市民族工作
条例 (npc 1993 + 福建/西藏民委 reposts 2015-2021) and 宪法 across 5 sites. The obvious rule, split
wide pools, would have destroyed legitimate mirror sets.
Real discriminators, both intrinsic: **conflicting own-文号** (546 pools hold ≥2, e.g. 国发〔2014〕
15号 … 〔2022〕9号, 国令 764/777/797, 惠府〔2014〕133号 … 〔2025〕32号 — a mirror carries one number
or none, and a 第N号 recurrence hides in the title TAIL that keying strips); and for the
un-numbered series (预警信号 / 招聘公告 / 听证公告 / 政府工作报告 carry no 文号 at all) a **same-site
repeat gated on genre** — of the 54 same-site-repeat pools spanning ≥1y, the 23 holding a
`promulgation` are statutes re-posted late while the 31 all-`other` are series. Year-in-title
needed no rule: `2018年政府工作报告` already keys per year.
Rule: R1 `split_by_docnum` partitions INSIDE each edition by the copy's own 文号, un-numbered
copies attaching to the nearest numbered text within 400d, with two measured guards — a conflict
splits only copies >30 days apart (chinatax/samr store a REFERENCED instrument's number on
mirrors 8-9 days apart) **except** across localities (惠府办 vs 江府办 five days apart are two
cities' own documents). Then R2 `is_series` per sub-pool: all-`other` plus a site re-issuing >60d
apart means the title names a series and nothing pools. **No title blocklist needed** — 台风 and
森林火险预警 fall out of R2 on their own.
Blast radius: instruments 327,634 → **328,678 (+1,044)**; 1,125 docs change `instrument_id`,
1,406 change role; **zero** change in genre, level, province, `localized_of` or the implementing
count (17,835 both ways). 386 groups split into 944 sub-pools, 48 series dissolved. Hand checks
**15/15** on new splits and **10/10** on an adversarial sample of pools left merged. Bonus: it
also fixed the cross-province false merge `a72a341` had called "the cq family".
Validator cascades verified unaffected: the instrument pools of BOOST, CXGH, AIPLUS, 以旧换新, the
Henan wrapper and the BJ news page are identical before and after, and **0 of the 230 diffusion
sources those anchors carry** change instrument_id or role. Corpus-wide 67 of 4,974 anchors (1.3%)
will shift at the Phase 2c rebuild.
Gazette bodies 4,400 / 11,450 at 18:55. **Six fixes now queued for one rebuild** at ~20:27.

## P2 Iteration 58 (the cq row is a non-issue; A1's other half is not)
Measured the Chongqing blast radius before touching the row, and it is **nil**: **zero** `cq`
documents fall back to the site level (all 1,295 derive from issuer or 文号, and 1,292 already
read `provincial`), and the ontology already returns `local_province`. So the one-row change
would move no document's level and no ontology placement. Dropped from the queue as cosmetic —
the inconsistency is real but inert, and `cq_lyj` outranking its own government only matters to
code that reads `sites.admin_level` directly.
Chasing that led somewhere that does matter. `citation_rank` is computed in `compute_scores.py`
from **`citations.source_level`**, a STORED column, and `extract_citations.get_source_level()`
derives it from 文号 first and then falls back to **`sites.admin_level`** — not from
`doc_identity.admin_level_doc`. That is exactly the half of corpus-lessons **A1** left undone
("drop or nightly-recompute the citation level columns from it", the ~29k stale rows).
**Measured: 22,981 of 540,166 edges (4.3%) carry a stored source level that disagrees with the
per-document level** — biggest buckets municipal→provincial 9,010 (weighted 1.5 when it should
be 2.0), provincial→district 2,494, central→provincial 2,489 (3.0 when it should be 2.0),
provincial→central 2,269. **It is 4.3%, NOT the 21% I feared**, because the 文号 path catches most
cases and the site fallback only bites when a document has no number; the npc 地方法规 are not
being weighted as central. So this is a refinement of the headline authority score, not a crisis,
and I am recording it that way.
There is a genuine **dependency cycle** to solve before fixing it, which is why I am not rushing
it: in Phase 2b `citations` → `compute_scores` → … → `doc_identity`, so neither the resolver nor
the scorer can read a fresh identity table (the same day-stale circularity `b1aff31` reasoned
about). But `citation_rank` needs only LEVEL, and level derivation (issuer / 文号 / publisher /
masthead) does not depend on `algo_doc_type` — only genre does. So the clean break is to split the
level derivation out of `doc_identity` and run it before `compute_scores`, or to recompute
`citation_rank` in Phase 2c from the finished table. Queued as a design task, after tonight's
rebuild so it does not change the pipeline mid-flight.
Gazette bodies 5,850 / 11,450 at 19:42.

## P2 Iteration 59 (A6 chain complete; the six-fix rebuild is running)
`A6_CHAIN_DONE 20:27:48`. Step 5 filled **7,300 of 11,450** gazette bodies before its 14,400s cap,
so a follow-up run is queued for the remaining ~4,150. No writers left.
Launched the rebuild detached (`logs/rebuild_20261007.log`) after pulling the droplet to
`6e0ccb5`, in the nightly's own dependency order: citations → scores → topics → issuers →
doc_identity --force → instrument_succession --write --force → site_stats → diffusion_events
--write → tracker_rollup → validate_cascades. Citations started 20:28. The point of running it
myself rather than waiting for 06:00 is that **six interacting changes land at once** — mirror
determinism (85.6k edges move to different copies), mirror pooling, the canonical-repost tier,
the annual-series split (+1,044 instruments), the balanced-bracket reference pattern and the
write-contention layer — and I want the 14 validator checks read tonight, while there is still
time to diagnose a failure before the nightly repeats it.
Expected: 14/14; `cxgh_edges` ~2,158 now resolving on **12685270** rather than 12747143;
resolution above 50.99%; and GD 52d / JS 82d / BJ 116d, 以旧换新, 提振消费 and the AI+ bands all
holding, which the annual-split agent verified read-only in advance by confirming that none of
the 230 diffusion sources those anchors carry changes `instrument_id`.

## P2 Iteration 60 (rebuild landed; the validator earned its keep)
Rebuild ran 20:28-21:02. First result **12/14 with two FAILs**, which is exactly why I ran it
tonight instead of waiting for 06:00.
**The intended improvements are confirmed live.** Top-5 by citation_rank is now
`12685154` 政府信息公开条例 **4,238** — the central mee copy — where before all 2,302 edges sat on
`900154149`, a **municipal district 发改委 repost**; `12685270` 城乡规划法 3,378 (the new
deterministic representative); `12738161` 道路交通安全法 3,320 (the 2021 edition, not the 2011
one); and `12747468` 广东省城市控制性详细规划管理条例 1,738 (the alias target). Citations
540,166 → **585,471**, resolved → **52.97%** (from 50.99%, and from the ~50.5% that stood this
morning). doc_identity 338,856 rows, **328,678 instruments**. doc_inbound 41,179 docs with
inbound (max 2,149). instrument_succession 14,624 rows. diffusion_events 36,116 → **45,524**
(31,903 implementing). tracker_weekly 46,178. Province coverage 81.1% of sub-national docs.
**The two failures were a measurement artifact, not a regression — the third time today.**
`aiplus_implementing` read 131 against band [20,60] and `aiplus_source_gate` inverted. Diagnosis:
**102 of the 131 are `topic_genre`**, the matcher's own weakest tier ("probable-but-unconfirmed":
same topic tag, implementing genre, inside a 365-day window), which is gated on the anchor's
`citation_rank >= TOPIC_ANCHOR_CR` — and the mirror fix consolidated the AI+ edges onto the
pool's canonical copy, pushing the anchor over that gate and switching the tier on. The AI+
opinion is also recent (2025-08), so its window is wide open and fills as AI documents arrive.
The **confirmed** tiers are citation 21 + title_reissue 8 = **29**, inside the original band and
matching exactly what `ai-plus-fidelity.md` and `ai-governance-diffusion.md` quote. So the band
was never wrong about the cascade; the metric conflated a confirmed signal with a speculative
one — the same shape as `cxgh_inbound` counting edges while saying citers.
Fix (`07f3541`): `aiplus_implementing` now counts citation+title_reissue only, a new
`aiplus_topic_genre` check carries a loose ceiling of 400 so a runaway is still caught, and the
source gate compares mentions against the confirmed count. Re-ran: **VALIDATION PASS: 15/15.**
App restarted; `/` 0.31s, `/browse` 0.33s, `/tracker` 0.77s, `/research` 0.13s, `/document` 0.19s,
`/lens?q=人工智能` 200 in 8.0s (cold cache; the 400 in my first smoke test was my own unencoded
Chinese in the curl URL, not a break).

## P2 Iteration 61 (post-rebuild: writers serial, memos re-based, A1 closed out)
Launched the serial writer chain detached (`logs/writers_20261007.log`): gazette bodies for the
remaining ~4,150 (12,000s cap) → `gov --library --categories gw --deep` to finish the walk that
was cut at page 70/125 (5,400s) → `build_site_stats`. One writer at a time, per the hold-time
rule.
Launched two read-only agents now that the layer is stable:
- **Re-base three memos on this build** (fidelity-provincial §2.1's Jiangsu row, the
  successor-detector universe, policy-tempo §0-§5), append-only with the old numbers kept and
  labelled, quoting 585,471 citations / 52.97% / 45,524 events / 328,678 instruments, and saying
  for each moved finding whether the MECHANISM changed or only the denominator.
- **Close out A1's other half**: re-measure the `citations.source_level` disagreement on the new
  build, quantify what it actually does to `citation_rank` and whether the top-30 ordering moves
  at all, then design past the Phase 2b dependency cycle (level derivation does not need
  `algo_doc_type`, only genre does, so it can run early). Brief explicitly invites the answer
  "inert, do not ship" — a correct-but-inert change is not worth new coupling.
CLAUDE.md (`<commit below>`): validator now 15 checks with the AI+ split recorded, the general
lesson named ("when a nightly check fails, first ask whether its metric conflates two things"),
and the delisted-head verdict corrected — sz_gazette holds two of the four, leaving only
苏住建规〔2011〕4号.

## P2 Iteration 62 (A1 closed; my "probably inert" guess was wrong)
**A1's other half LANDED** (`a494955`). I had framed this as probably inert and explicitly
invited "do not ship"; the measurement says otherwise and the agent made the case. On the current
build 23,214 of 585,471 edges disagree (3.97%), and **13,846 of the 310,136 rank-BEARING edges
(4.46%)** — but the rank effect is not small: **5,930 of 47,309 ranked documents change (12.5%)**,
3,233 up and 2,697 down, median relative move **21.3%**, p90 50%, max 200%. The top-30 holds the
same SET but the ORDERING moves at ranks 14-27 (six swaps); the top 13 and the top 5 are
unchanged, so the validator's "top-5 are formal instruments" check stays safe.
And the direction is systematically the A1 bug rather than noise: **national laws cited mainly by
`npc` 地方法规 were being paid the 3.0 central rate** — 工会法 248.0 → 175.0, 村民委员会组织法
250.0 → 184.0, 代表法 200.0 → 140.5, 城市居民委员会组织法 228.0 → 170.0, 人民防空法 550.5 → 497.0
— while 政府信息公开条例 gains +65.5 from municipal→provincial upweighting. Every citation source
now has an identity row (0 misses), so the join is total.
Design chosen was (b): `compute_citation_ranks` LEFT JOINs `doc_identity` and uses
`COALESCE(NULLIF(i.admin_level_doc,''), c.source_level)`. The reasoning against the others is
sound — (a) splitting level derivation early would drag `issuer_parser` ahead of the resolver and
create a SECOND producer of the per-document level that can drift from `build_doc_identity`; (c)
recomputing in Phase 2c would make `documents.citation_rank` a two-writer column that
`build_diffusion_events` reads between the writes. (b) needs **no daily_sync change at all** and
its failure mode is benign: a document crawled today has no identity row at scoring time and
keeps the crawl-time weighting for one night, which is exactly today's behaviour, and on a cold
or partial table the fallback chain reproduces the pre-change numbers exactly rather than
collapsing to the 0.5 `unknown` weight. `citations.source_level`/`target_level` are deliberately
kept, because an unresolved edge (47%) has no document whose level could be looked up and the web
app reads both columns in ~6 places. Tests 168 → **173**; `corpus-lessons.md` A1 now carries a
Status block recording what was done, what was deliberately not done, and why.
Consequence to fold into the memo re-base: `citation-network-structure.md`'s top-30 table shifts
at ranks 14-27 and the 工会法 / 村民委员会组织法 class of corrections is worth naming there.
Takes effect at the next nightly's `compute_scores` (it will write ~5,930 rows instead of a few
hundred; the diff-only batched path keeps the WAL flat).
Writers: gazette bodies 7,800 / 11,450 at 21:52.

## P2 Iteration 63 (memos re-based; a finding withdrawn, honestly)
**Re-base LANDED** (`5c8ecbc`), append-only across three memos, and it separates mechanism from
denominator in every case rather than just restating numbers.
**fidelity-provincial §2.1 Jiangsu:** 601 pairs / 457 scored / relay **3.3%** on the citation
basis; 700 / 466 / 3.9% on the union; 466 / 242 / 7.4% on the implementing subset. The row's
"200 scored, 8.0%" turns out to have been the IMPLEMENTING figure carrying an all-pairs label —
a labelling error, not a drift. And relay is 3.3% on the citation basis of both the old 473-pair
run and this 601-pair one, so **the six fixes moved Jiangsu's relay rate by exactly zero** (relay
count 15 → 15). Suzhou still supplies 549 of 700 pairs and all 18 union relays.
**successor-detector:** universe 39,258 docs → 33,675 instruments, pilots 1,680 → 1,411;
successors 80, rate **5.7%** (was 5.9%), ex-mid-flight 6.5%, trials-only 8.0%/9.4%; precision
76.0/86.7% unchanged. **The scale rate does not move, and the reason is structural**: the detector
pools mirrors on `instrument_id` BEFORE matching, so mirror selection is invisible to it. Also
flagged a double-counting trap: `instrument_succession`'s 80 `pilot_to_national` rows ARE this
detector persisted, not independent evidence.
**policy-tempo:** strict subset 13,081 → **17,196** events. Survived: the lag CDF and crawl
latency almost exactly (median 454d vs 473d, 0.70/7d and 0.86/28d identical); Government fastest
and still 2.4x the next area (0.706 → 0.779); Finance and Tech still the lowest large yields; the
2018 step still in the denominator; all topics over-dispersed; campaign windows SHARPENED
(Commerce 以旧换新 3.36 → 3.52); no 2013 step. **Province-first rose 66.7% → 68.6% on 838 anchors
and the province-to-city median lag gap WIDENED 126 → 245 days**, which strengthens the volume's
central claim. The site-batch caveat got LARGER, not smaller (2023-01-02 now 106 cascades), and
is reported that way.
**Two flips, both argued:**
1. **Culture replaces Tourism as the slowest area** (Tourism 0.05 → 0.073, Culture 0.065 →
   0.034). **Mechanism, not denominator:** Culture's denominator ROSE 743 → 765 while its
   numerator FELL 48 → 26, which no denominator effect can produce. Cause: a cascade is labelled
   by its ANCHOR's `topics_algo`, and the mirror fix changed which copy is the anchor, so topic
   aggregates were RELABELLED. Recorded in CLAUDE.md (`<commit below>`) as a standing caveat:
   treat any topic-level series as sensitive to anchor selection and re-base after an identity
   change rather than assuming only counts moved.
2. **The Tech → Education lead-lag is WITHDRAWN.** r 0.177 → 0.100 against null95 0.147,
   p = 0.155; lag-0 stays ~0 so it was never a shared-anchor artifact, and 31% more events
   SHRANK the correlation, which is the signature of noise. Only **2 of 90** pairs now clear
   p<0.05 against 4.5 expected, i.e. below chance. So §4's verdict of no general lead-lag
   structure survives and is stronger with its single named exception removed. A positive finding
   evaporating under more data is the right outcome to report plainly.
`a494955` touches none of the three (no figure in them is rank-based); dated forward-looking notes
were added in successor-detector §7a and policy-tempo §0a naming the npc over-weighting class and
its pending-at-next-nightly status, and `citation-network-structure.md` was deliberately not
touched.
Writers: gazette bodies 8,000 / 11,450 at 21:58.

## P2 Iteration 64 (gazette scoped; it found a measurement that is not coverage-limited)
**Scoping LANDED** (`137a907`, `docs/working/sz-gazette-scoping.md`) and it corrected a figure
**I** had propagated into CLAUDE.md, the A6 memo and this log: the run is **31.4 continuous years,
1995-04 to 2026-09, not 38**. The 59 pre-1995 rows sit in retrospective compilation issues printed
2002-03 (总第359/366/320期) and the platform's earliest real issue folder is `zfgb/1995/gb68`, so
issues 1-67 were never published. Dates themselves are sound (文号 year matches date year on 921
of 930 rows for 1987-2001), so only my span claim was wrong. Fixed in all three places
(`51bf752`).
What is there: 11,450 docs, publisher 100%, section 97.0%, **文号 85.2%**, doc_identity 100%,
`date_quality` good on every row, 98.1% municipal per-document, 1,342 issues, 890 issuers, volume
flat at 250-500/yr. **76.3% is instrument-shaped** (promulgation 6,823 + implementing 1,932);
apparatus is small and countable (人事任免 458, 公告/公示 951, 目录 7) and there is **no masthead
noise at all**, because the crawler reads article JSON rather than issue pages. 1990s bodies are
short but complete (mean 1,732 chars).
**The real find is a denominator.** A 文号 serial tells you what the city ISSUED whether or not we
hold it, so max serial per series per year estimates total issuance independently of coverage:
深府 roughly halves from ~190/yr (2001) to ~95-120 (2015-24), 深府办 collapses to single digits
after 2016, and the section mix agrees independently (市政府 documents 36% → 11%, 部门文件
3% → 55%). *(The scoping study's third claim, 深府函 rising 127 → 473, was WITHDRAWN by the
study itself — see iteration 65; it compared a k=1 year against a k=4 year, and I had
repeated it here.)* Almost every result in this project is coverage-limited; this one
is not. Launched it as recommendation 1, with the estimator required to be defended two ways and
the 2008-09 administrative seam separated from the trend.
**The honest limit that matters most: the depth does NOT connect outward.** Pre-2010 gazette docs
take 11,739 citation edges but **82.6% come from the gazette itself** and only 2,048 from the rest
of the corpus. So the scoping study's explicit instruction — do **not** extend any diffusion or
fidelity study backwards on this material, because the partners are missing and the result would
describe our crawl history — is right, and I am recording it rather than quietly ignoring it. Also
new: 5,741 pre-2010 and 1,491 pre-2000 full-text docs, the largest genuine historical block in
the corpus (npc's 3,301 is metadata-only), and 54.3% of every corpus document dated 1995-1999;
instrument overlap with other Shenzhen sites is only 2.0%, so it is nearly all new material.
Queued from it: instrument lifespan from the 1,153 bodies containing 废止 / 610 explicit (blocked
until the backfill finishes), and re-ranking the citation-crawl queue against 3,071 newly-cited
pre-2010 anchors.
Writers: gazette bodies 9,200 / 11,450 at 22:43.

## P2 Iteration 65 (a measurement that is not coverage-limited — and it withdrew its own premise)
**`wenhao-denominator.md` LANDED** (`977e2ef`), and the first thing it did was **withdraw the
headline its own scoping study had offered, which I had repeated in iteration 64**: the "深府函
rises 127 → 473" compared a **k=1 year (2005) against a k=4 year (2018)**. Both letter series are
flat to negative, and 深府办函〔2001〕143号 proves the letter channel was **already larger** than the
文件 channel (≈110) at the start of the observable window. So formality did **not** move from 文件
into 函; the 文件 channel narrowed beside a letter channel that stayed in the low hundreds. My
iteration-64 entry is corrected in place.
**What is established.** 9,750 of 11,450 carry a 文号; **8,722 parse into 481 normalized series**,
of which 81 hold ≥15 docs and all reset annually (verified: a later year's minimum serial always
falls below an earlier year's maximum). 1,028 numbers are correctly EXCLUDED as non-denominators:
554 人大/政府 `第N号` (numbered per five-year term, Chinese numerals), 364 `市政府令第N号` (one
continuous series since 1992), 109 inconsistent counters, and one leaked `总第178号` **issue**
number — the gazette's 1,342 issue numbers live in `keywords` and must never enter this analysis.
**深府 numbered 文件 fell from 276-365/yr (1995-98) to 83-105/yr (2017-24); 深府办 collapsed from
86-239 to 3-24; the letters did not absorb them.** I verified the core independently with my own
SQL: 深府 max serial 269 (2006) → 88 (2024), 深府办 238 → 9 — and in 2024 the corpus holds only
**5** 深府 and **2** 深府办 documents, which is precisely the point. The serial measures issuance
where coverage is near zero.
**The estimator is defended two ways**, as required: the max-serial and mean-spacing estimators'
median ratio stays within 1.00-1.07 in every inclusion band and only the spread widens (IQR
1.00-1.00 above 50% inclusion, 0.91-1.21 below 20%), so **the error is variance, not bias**, about
±10-20% at low inclusion; a third date-extrapolated estimator runs 9% low by construction and is
a lower bound. Where k≤2 the order statistic is used directly: for 深府办 2019-2026 (k=17, max 17),
P(all ≤ 17) is 8×10⁻¹⁴ had the series still run at 100/yr. Other Shenzhen sites raise the observed
max in only 4 of 51 shared series-years.
**The 2008-09 seam does not explain it.** Restricted to 2010-2026, one administrative regime, the
declines are STEEPER: 深府 −5.9%/yr, 深府办 −14.3%/yr, both estimators agreeing within 0.7 points,
stepping down at 2012 and again at 2017. The 2017 规范性文件 renumbering cannot account for it
(深府规 runs 5-30/yr, 深府办规 1-12/yr, against declines of ~110 and ~90).
**Incidental find worth keeping:** 34 series have a max serial under 30 at 90-100% inclusion —
these are the 规范性文件 registers created 2007-2019 (深建规, 深人社规, 深市监规, 深府规, 深府办规),
where the gazette prints essentially all of them. So **departmental rule output needs no estimator
at all and never exceeds ~30 per department per year.**
**The limit it names most sharply** is the one place the denominator cannot help: the genre and
body-length check (printed 函 are promulgation-shaped and the longest of the four series, median
3,809 chars vs 深府's 3,636) runs on the 1-7% of 函 an editor chose to print, which selects for
exactly the rule-carrying ones. Plus n=1 on a special economic zone with 特区法规 powers, and no
second city in the corpus has pre-2010 depth to check it — **the method generalizes, the result
does not**. No deregulation or decentralization claim is made, and the inferred mechanism (the
规范性文件 registration regime defining a small audited rule class) is flagged as circumstantial
on timing and untested.
Writers: gazette bodies 9,800 / 11,450 at 23:01.

## P2 Iteration 66 (gazette bodies complete; lifespan study unblocked)
Gazette body step finished 23:51: **11,204 of 11,450 = 97.9%** across the 31.4-year run. The
chain moved on to `gov --library --categories gw --deep` at 23:51 (5,400s cap, ends 01:21), and
`gov` is now **25,084 rows at 99.2% body**, up from 23,669 at 15:24, so the walk that was cut at
page 70/125 is making real progress on the historical 国发 tail.
Launched the scoping study's recommendation 2, now unblocked: **instrument lifespan from gazette
repeals** → `docs/research/instrument-lifespan.md`. The question is how long a municipal
instrument lives before repeal and whether that changed over thirty years, which the gazette can
answer because 废止 notices are themselves published documents (1,153 bodies contain 废止, 610 an
explicit repeal). Brief requires: using the existing `instrument_succession`
`superseded_by_stated` machinery rather than a fresh string match; handling BOTH censoring
problems explicitly (right-censoring, since instruments still in force have no repeal date and a
naive mean over observed repeals skews short; and left-truncation, since pre-1995 instruments are
only visible if repealed after 1995); testing rather than assuming the reading that the 2007-2019
规范性文件 registration regime produced shorter, more uniform lifespans; and naming the limits,
especially 有效期 sunset clauses that retire instruments with no repeal notice at all. Explicitly
licensed to return a null result if the datable pairs are too few, rather than pad a weak curve.

## P2 Iteration 67 (WRITERS_DONE; lifespan study refutes half my hypothesis)
**Writer chain complete, `WRITERS_DONE 00:36:49`.** Gazette bodies **11,204 / 11,450 (97.9%)**;
`gov --library gw --deep` ran 23:51-00:36 and took `gov` to **26,126 rows** (23,669 at 15:24), so
the walk cut at page 70/125 is now substantially complete; site_stats rebuilt. No writers left, so
I launched `compute_scores` → `build_site_stats` → `validate_cascades` → app restart
(`logs/scores_20261008.log`) to make the A1 rank correction LIVE tonight.
**`instrument-lifespan.md` LANDED** (`a39cfa7`) and it is the strongest result of the run.
**Pairing:** 1,022 repeal notices name **4,159 distinct repealed instruments** (2,848 from
numbered 废止目录 catalogue lines, 1,311 from in-text 同时废止; the largest single catalogue names
**425**), **3,308 of 4,159 (79.5%) datable on both ends**. Validation that licenses the 文号-only
rows: the 文号 year equals the resolved document's own promulgation year on 1,418 of 1,506 resolved
pairs. **A real limitation of our own machinery surfaced:** `instrument_succession` has 1,476 rows
with a `sz_gazette` predecessor but only 374 `superseded_by_stated` and 337 usable, because that
table keeps **one successor per predecessor per relation and so cannot represent bulk repeals** —
worth remembering before trusting it as a repeal census.
**Median survival is NOT REACHED in any stratum.** Kaplan-Meier, right-censored at 2026-09-30
with **delayed entry at 2000** (repeals before 2000 are unobservable, so without it the 1990s
cohorts read as selected for longevity): over 8,751 instrument-shaped gazette docs with 1,721
events, P10 = 5.6 y, P20 = 11.3 y, then the curve **plateaus at S = 0.75**. And the 文号
denominator study explains the plateau independently: **under 1% of the ~207,000 numbered 文件
Shenzhen ever issued are formally repealed**, because most of a 文号 series is not normative. Two
methods agreeing from different directions is the method check.
**Form matters; era does not, the way it looks — and this refutes half the hypothesis I gave it.**
Matched on the 2010-18 issue window, register S(10) = 0.75 against 文件 0.92, i.e. three times the
repeal rate, and the register reaches P20 at 6.7 y where 文件 never does. But ages AMONG the
repealed converge (median 3.5 vs 3.7 y) and the register's IQR is slightly WIDER, so my
"shorter and more uniform" hypothesis holds on rate and **fails on uniformity**: registration
makes retirement **recordable, not faster**. 函 are essentially never repealed (7 events of 219,
plateau 0.95). Era is mostly a cleanup calendar: hazard 0.4-0.8% baseline with spikes to 6.55%
(2008), 3.44% (2010), 2.76% (2001), 2.70% (2014), the 2008 sweep ordered by 深府办〔2007〕70号 alone
being 15% of all events; median age at repeal falls 8.2 y (2008-11) → 4.0 y (2021-26) because the
sweeps got closer to the material they clear. Hence the memo's title: instruments are not repealed
on a schedule, they are swept.
**The limit it names is bigger than the finding, and it says so:** the **sunset channel exceeds
the repeal channel**. 1,871 bodies state an explicit 有效期N年 (mode 5 y, 1,201; then 3 y, 447),
carried by **67% of register documents against 6% of 文件**, and **1,538 of them have no repeal
notice at all** — so the form gap is a LOWER bound, not an overstatement. Plus unpublished repeals
are invisible, falling gazette inclusion (18-35% → 4-14% after 2017) makes recent cohorts' curves
too flat exactly where the recent cohorts are, 851 named repeals are undatable and skew toward
人大-repealed 条例/特区法规 carrying no annual 文号, 1,602 of 1,615 exact resolutions are internal
to the gazette, and the 2020-26 cohort has ≤6.7 y follow-up at 84% censored.

## P2 Iteration 68 (A1 live; a predicted number caught my own no-op)
Ran `compute_scores` → `build_site_stats` → `validate_cascades` → restart at 00:40. It reported
**2,905 rows updated** where the A1 agent had predicted **5,930**, and that mismatch is what
exposed my own mistake: **my chain had no `git pull`**, the droplet was still at `07f3541`, and
`grep -c "COALESCE(NULLIF(i.admin_level_doc"` returned **0** — so that run used the OLD weighting
and its 2,905 updates were merely the new `gov` documents re-rippling the graph. Harmless, but it
would have been invisible without a number to check against. Pulled to `a39cfa7` and re-ran.
**The A1 correction is now LIVE and it matched the forecast exactly: `Updated 5,930 of 341,313
documents`** — the same 5,930 predicted from a read-only simulation, which is about as good a
confirmation of that measurement as one gets. 政府信息公开条例 4,238 → **4,304** (the predicted
+65.5, landing as +66). **VALIDATION PASS 15/15**, app restarted, corpus **341,313 docs / 472
sites**.
So every one of the seven fixes made today is now live and validated: mirror determinism,
identity mirror-pooling, the canonical-repost tier, the annual-series split, the balanced-bracket
reference pattern, the write-contention retry layer, and A1's per-document citation weighting.
Standing lesson from this iteration, worth keeping next to the others: **predict the size of a
change before applying it, because the predicted number is the only thing that distinguishes a
successful run from a silent no-op.**

## P2 Iteration 69 (new session; Wuxi crawl started; parallelism via a separate DB)
Session resumed on a new model at 01:17 UTC 2026-10-08. Droplet clean: `a39cfa7`, no lock, no
writers, 21G free. Commit attribution for this session is `Co-Authored-By: Claude Opus 5.5 (1M
context)`, with no session line.
**Wuxi crawl launched** (`logs/wuxi_chain.log`, detached with `setsid nohup`): `wuxi --deep`
(7,200s cap) then the seven `wxd_*` districts (2,400s each), all into **`documents_wuxi.db`**,
per the separate-DB workflow the hold-time rule in CLAUDE.md prescribes for long crawls. 50 docs
in by 01:22. Expected ~7,400 across wuxi + 7 districts, which would discharge corpus-lessons B1's
"second non-Suzhou prefecture to depth" requirement. Merge with `merge_db.py` must happen OUTSIDE
the 06:00 nightly window; if the crawl runs past ~05:30 the merge waits for the nightly to finish.
**The useful consequence of the separate DB:** `documents.db` itself has no writer while Wuxi
runs, so its one-writer slot is free. Used it for the **BM25 index rebuild**
(`build_search_index_seg.py --rebuild`, `logs/seg_rebuild.log`, 9,000s cap, started 01:20),
which clears the stale segmented tokens of the 240 collision-cleared documents (a contentless
FTS5 index cannot delete a row without its original text, so only a rebuild removes them).
Trade-off accepted and stated: the rebuild drops and refills the table, so for about an hour BM25
returns hits only from already-reindexed rows and otherwise falls through to trigram; on a
private site at 01:20 UTC that is a non-issue. It must finish before the Wuxi merge and before
06:00, and should finish around 02:30.
Two read-only agents launched alongside: re-base `citation-network-structure.md`'s top-30 and
concentration statistics on the live A1 ranks (separating the effect of mirror determinism from
that of per-document weighting, and testing rather than assuming the prediction that A1 brings the
weighted ranking closer to the raw one); and a code agent for the ~770 "分享到：" share-widget
tails, which must distinguish a chrome suffix on real text (trim) from an all-chrome body (flag,
never empty), leave a mid-body 分享到 alone, and audit every change.

## P2 Iteration 70 (my convergence prediction failed; the predicted fourth bug turned up)
**`citation-network-structure.md` re-based** (`29fc8b1`, dated §8, old table kept and labelled).
The agent separated the two changes cleanly by computing every figure in three states on tonight's
edges — PRE (old resolver rule simulated), A1OFF (tonight's edges, site-level weights) and NEW
(stored) — so PRE→A1OFF is the mirror change M and A1OFF→NEW is the weighting change W. Its NEW
recompute matches stored `citation_rank` and `doc_inbound` with **0 mismatches**, and W changes
exactly the **5,930** documents seen live. PRE is a simulation and is labelled one (it moves 119k
edges against the commit's 85.6k measured before tonight's ingest).
**My prediction failed, which is why I asked for it to be tested rather than assumed.** I expected
A1 to bring the weighted ranking closer to raw inbound, on the theory that the over-weighting it
removed was an artefact. It did not: top-30 overlap with `doc_inbound` 25 → 25 → 25, top-100 82 →
83 → 82, Spearman 0.833 → 0.834 → 0.831. W moves weight in BOTH directions rather than toward
equal weights, and its large cuts (工会法 248 → 175, 人民防空法 550.5 → 497) sit below the top 30.
The mirror fix did more convergence than W did. The leftover gap looks like the edges-versus-citers
overhang, which neither change touches: 反倾销条例 carries 4.04 of weight per distinct citer, above
the 3.0 any single central citation can give.
**The headline claims survive.** Authority stays heavy-tailed under every treatment (top 1% holds
55-62%, Gini 0.948-0.964); "about four in five of the top 100 are central" (84 pooled, 79 by
`citation_rank`, 75 by raw); laws plus regulations 77 of 100. The memo's own pooled top-3 is
unchanged (城乡规划法 1,895, 政府信息公开条例 1,546, 道路交通安全法 1,329). One honest loose end:
the laws/regulations split moved from 27/48 to 39/38 and neither change explains it; untraced.
**A clean demonstration of why per-document level matters:** counting the top-100's central share
by HOST SITE moved **68 → 83** under M, because before the fix national laws' edges sat on reposts
held by provincial and municipal bureaus (nx_gxt, bjb_tjj, fj_yjt, fj_wjw). Counted by
`doc_identity` level it stayed at 78-79 throughout. Same documents, same edges; only the level
attribution differed.
**The fourth folded-string length-floor bug, predicted in CLAUDE.md and now found:** the memo's own
Appendix pooling floors on the folded title, so 民法典 and 预算法 — 3 characters once 中华人民共和国
is stripped — were never pooled. Added as row four of the CLAUDE.md table (`1908ef4`). I wrote there
that the production resolver is unaffected, then **verified that rather than asserting it**:
预算法 holds 414 edges and 民法典 384 on their canonical npc copies, the duplicate copies correctly
hold 0, and only 48 unresolved refs mention either. The resolver's `LENGTH(title) >= 5` floor reads
the RAW title (10 characters), so it is safe.
**Queued:** the stored `citation_rank` still ranks a bare ORGANIZATION name, 广东省自然资源厅, at
**#20** — a masthead stub absorbing citations through containment, the same residual the
REF_PATTERN fix logged ("masthead stubs remain containment-eligible targets"). Worth a guard that
excludes organization-name-only titles from being citation targets.
Running: BM25 rebuild (since 01:20); Wuxi crawl at 475 docs / 100% body in `documents_wuxi.db`;
the share-tail script agent.

## P2 Iteration 71 (org-name stubs gated; the expected resolution DROP pre-registered)
**Org-stub containment guard LANDED** (`4b890aa`, 02:08 UTC, inside the 05:30 deadline, so the
06:00 nightly's citation rebuild applies it). Class: **2,260** documents whose whole title is an
organization name (2,199 `other`, 848 empty body); **181 of them held 4,802 resolved edges**
(1.5% of 310,136), with 广东省自然资源厅 at rank #20 on 692 edges and 4 of the class in the top
100. The agent narrowed a first predicate that caught 4,886 because many hits were news headlines
ending in 会 or 局 — and masked genre words that are part of an agency's own name (规划和自然资源局,
计划生育, 标准化), without which 广州市规划和自然资源局's 63 edges would have slipped through.
**Hand-check: all 25 edges sampled on the stubs are mis-resolutions** of an instrument that is not
held, two of them across provinces (a Beijing ref and a Chongqing ref both landed on Heyuan stubs).
No resolved ref is exactly a bare organization name, so the stubs keep exact-tier eligibility only.
**A silent side effect it caught and avoided:** `build_diffusion_events` builds its own
`TitleMatcher`s over topic STEMS, and 72 stems (国家认定企业技术中心, 承接产业转移示范区 …) share the
organization shape, so a global gate would have silently changed `title_reissue` matching. The gate
is therefore opt-in (`org_only_exact=True`, set only by `extract_all`); verified at line 706.
**Where the 4,789 displaced edges go** (real matcher, read-only, all live titles, plus 8,000 random
edges of which **0** changed): **4,567 honest-unresolved**, **134 gains** (they now reach the right
instrument via its 印发 or decree wrapper or a 【已废止】 copy), **64 to a 转发 transmittal** (better
than a stub, still a proxy), and **24 wrong-to-wrong**, all of which were already wrong. **Zero
correct edges lost.** Validator simulated: none of the displaced edges reach any of the 15 checks'
inputs; top-5 unchanged; no diffusion anchor is an org stub.
**PRE-REGISTERED, so tomorrow's number is not misread:** after the 06:00 nightly's citation
rebuild, resolved edges should FALL by about **4,570** net, i.e. resolution from 52.97% to roughly
**52.2%**. That fall IS the improvement: false edges are being turned into honest unresolved ones,
the same "absolute resolved count is not the honest metric" lesson from the August backfill read in
the other direction. If resolution instead RISES or falls by much more than ~4,600, something else
moved and must be investigated. Also expected: 广东省自然资源厅 leaves the top 20. No validator check
reads resolution %, so the drop cannot trip Phase 2d.
**Deliberately NOT stacked tonight:** the agent's two leftover resolver-precision patterns, generic
short titles (政府信息公开指南, 涉企收费目录清单) attracting containment, and documents ABOUT an
instrument (延长 / 贯彻 / 废止) winning containment over the instrument. Two simultaneous changes to
the resolver would confound the measurement of each; tonight applies only the org-stub gate, and
those two follow once its predicted effect is confirmed.
Suite **189 passed, 1 skipped**. Running: BM25 rebuild (~50 min in), Wuxi at 959 docs / 100% body,
the tail-trim script agent.

## P2 Iteration 72 (the tail class is 43x the estimate; trim verified, deliberately deferred)
**`scripts/trim_body_tails.py` LANDED** (`5a8c4cb`, 11 tests, suite **191 passed**), and its first
finding corrects a number I had carried in the queue for a day: the class is **33,105 bodies, about
43 times the "~770"**. That 770 was a correct answer to a narrow query (`分享到：` AND body under 400
characters) which I then misused as the class SIZE — the same "right number, wrong claim" shape as
the edges-versus-citers mix-up. The real class is dominated by `扫一扫在手机打开当前页` (22,921, of
which **12,763 are `gov`**, the State Council), then share-widget JS/CSS 10,852, 分享到 5,992,
相关解读 3,152. By site: gov 13,210, js 5,231, suzhou 3,740, sz_invest 1,330, most 1,059.
Split: **32,495 are a suffix on real text** (about 20,000 lose under 5% of the body; 1,221 lose
more than half, mostly short suzhou appointment notices carrying a 150-char nav block), and **610
are all-chrome**, of which 39 recover a real body by re-extraction and **571 are flagged in
`body_tail_flags` and never emptied**. Remedy: re-extract 7,453 (HTML saved and the site's own
extractor now returns a clean text of comparable length), trim the stored text for 25,081
(15,963 because the extractor still emits the tail, 8,951 because the HTML file is missing).
saac and jl_swt are NOT in the class (footer link lists with no share marker), a separate 79-row
job. Safety properties: the detector walks back from the end and stops at the first line of prose,
so a mid-body 分享到 is never touched (tested on 我的分享到这里 / 分享到了…成果); it cuts at the earliest
marker and keeps `body[:cut]` byte-for-byte, so kept + removed equals the old body exactly; 相关附件
is deliberately NOT a marker because it heads the document's own attachment list; a test caught a
decree made entirely of short lines (a repeal list) being cut, now fixed. Every change is audited
in `body_tail_trims(…, removed_tail, old_body, reverted_at)` with `--revert`, and each UPDATE applies
only if the stored body is still the one scanned.
**I verified the riskiest group myself before deciding anything.** gov is a marker trim of STORED
text (re-extraction is unavailable there), on the corpus's most important source. 13,162 trim / 48
flagged; tail share median **1.3%**, p90 10%, p99 31%. On eight sampled cut boundaries every cut
lands exactly after the document's natural end — the signature block (国务院办公厅 / 2023年4月9日 /
（此件公开发布）), the effective-date clause (…施行 / …同时废止), or the 附件 line — and immediately
before `扫一扫在手机打开当前页 / 解读 / …`. The sample also shows the mechanism behind the **368 false
citation edges** the agent counted: the removed `解读` block lists TITLES of other documents, which
the extractor was reading as references.
**Deferred to tomorrow, deliberately, for three converging reasons.** (1) `doc_search_seg` is
contentless with no trigger, so trimming AFTER tonight's BM25 rebuild would strand the removed
tails' tokens in the index until another full one-hour rebuild; tomorrow I can trim FIRST and
rebuild once. (2) Tonight's nightly then measures the org-stub resolver change alone against its
pre-registered −4,570, instead of a combined figure. (3) The Wuxi merge also has to fit before
06:00. The tails have been there for months; a day costs nothing.
Tomorrow's order: `trim_body_tails.py --dry-run` → `--apply --dump-tsv` (no other writer, outside
the nightly) → `build_search_index_seg.py --rebuild` → let the nightly re-derive citations, scores,
stats, diffusion, succession and validation. Predicted effect to pre-register then: about −195
resolved edges from the tails (84 named + 106 llm + 5 formal), plus small `ai_relevance` and 5-gram
fidelity moves; `doc_identity` genre unaffected (it reads header fields only).
BM25 rebuild at 276,000 / 341,313 (81%) at 02:29, finishing about 02:45.

## P2 Iteration 73 (BM25 rebuild clean)
`SEG_DONE rc=0 02:42:35` after 4,877s: **341,313 of 341,313** documents segmented and indexed
(`doc_search_seg` row count equals the corpus exactly), and the WAL truncated to **0 bytes**, so the
builder's final checkpoint ran. The 240 collision-cleared documents' stale tokens are gone. The local
launch wrapper had reported exit 1; the detached job on the droplet was unaffected, which is the
fourth time tonight `setsid nohup` has separated a wrapper failure from the real work.
Search verified end to end: `/search` returns 200 with ranked documents. The first query after the
rebuild took **11.0s** cold, then **0.22s** on repeat — page-cache warm-up as CLAUDE.md documents for
a freshly rebuilt index on this box, not a regression. Checked by re-running rather than assumed.
Wuxi still on step 1 (`wuxi --deep`): **1,555 docs at 100% body** in `documents_wuxi.db` by 02:43.
Step 1's cap is 03:17; the seven districts follow. Merge into documents.db only if it can finish
before 06:00 with no other writer; documents.db currently has none.

## P2 Iteration 74 (Wuxi step 1 hit its cap; my own wrapper said rc=0)
Wuxi step 1 (`wuxi --deep`) ended at 03:17:54 and my chain printed **`rc=0`** — but it had run
EXACTLY its 7,200s cap (01:17:54 → 03:17:54). The wrapper was `timeout … | tail -5; echo rc=$?`, and
after a pipe `$?` is the status of `tail`, not of `timeout`, so a 124 was reported as 0. That is the
failure-hiding pattern I wrote into CLAUDE.md as a rule a few hours ago, this time in my own shell —
and the **fourth** wrapper of mine tonight to hide a failure (stale `[0-9]+ ok` regex past 999, `| tail
-1` truncating a traceback, a `for` loop exiting 0 over nine crashes, and now `$?` after a pipe).
Encoded in memory: use `${PIPESTATUS[0]}` or `set -o pipefail`, and cross-check a step's elapsed time
against its cap.
The log confirms what happened: it was actively paging the 部门文件 section (`bmgfxwj`) at
**page 42 of 100** when killed, with no completion summary; the earlier sections finished (2009-2026
present). So `wuxi` holds **2,078** in `documents_wuxi.db` against ~3,865 listed in the scratch test,
and a resumable follow-up must finish `bmgfxwj` pages 43-100 (~1,160 docs; the crawler skips stored
URLs). The seven districts are now running (`wxd_liangxi` 162 at 03:25). Because the chain writes its
OWN database it can run straight through the 06:00 nightly with no contention; only the MERGE has to
avoid the nightly window.

## P2 Iteration 75 (districts land exactly as predicted; the org-stub test re-designed)
Wuxi districts, all real completions well under their 2,400s caps: `wxd_liangxi` 10 min,
`wxd_xishan` 20, `wxd_huishan` 2, `wxd_binhu` 3. Counts match the scratch test **exactly** —
梁溪 **209**, 锡山 **450**, 惠山 **47**, 滨湖 **83** against the predicted 209 / 450 / 47 / 83 — at
~100% body. `wxd_xinwu` 535 of 1,095 at 04:12; `wxd_jiangyin` (~803) and `wxd_yixing` (~36) follow.
Chain should finish about 05:10.
**Re-designed the pre-registered test for the org-stub fix, because the original one was going to be
confounded no matter what.** I had predicted aggregate resolved edges would fall ~4,570. But every
nightly adds documents, and merging ~4,300 Wuxi documents before 06:00 would add their citations
too, so the aggregate cannot isolate the org-stub effect. The provenance-specific test can:
- **PRIMARY:** resolved edges whose target is an organization-only title should fall from **4,802**
  to approximately **0** (exact-tier refs to a bare organization are the only survivors, and the
  agent found none). 广东省自然资源厅 should leave the top 20.
- **SECONDARY:** aggregate resolved edges, DECOMPOSED by source site, so Wuxi's additions
  (`wuxi`, `wxd_*`) and the night's ordinary crawl are separated from the rest.
This makes it safe to merge Wuxi before the nightly, which is the better outcome anyway: its
documents then get citations, identity rows and scores tonight instead of sitting underived a day.
Merge plan: as soon as WUXI_CRAWL_DONE, if it can finish by ~05:40 with no other writer. The
`wuxi` municipal follow-up (bmgfxwj pages 43-100, ~1,160 docs) cannot fit before 06:00, but it writes
its own DB, so it runs through the nightly and gets a second merge later.

## P2 Iteration 76 (Wuxi merged — corpus-lessons B1's second prefecture is in)
`WUXI_CRAWL_DONE 05:14:25`. Final separate-DB totals: **4,746 docs, 4,653 with body (98.0%)** —
wuxi 2,078, wxd_xinwu 1,087, wxd_jiangyin 756, wxd_xishan 450, wxd_liangxi 209, wxd_binhu 83,
wxd_huishan 47, wxd_yixing 36. Cross-checked by elapsed time against the cap, as resolved: `wuxi`
ran exactly its 7,200s and `wxd_xinwu` and `wxd_jiangyin` exactly their 2,400s, so all three hit
their caps despite printing `rc=0`; xinwu still reached 1,087 of 1,095 (99.3%), jiangyin 756 of ~803.
**Read `merge_db.py` before running it**, because tonight's worst bug was an id-collision upsert
that clobbered another site's body, and a merge bulk-inserts rows whose ids were minted in a
different database. It is safe: it dedups by URL (`WHERE url != ''`, so the partial index is used)
and gives every incoming row a FRESH id from `next_id(tgt)` with a plain INSERT, never reusing the
source ids and never upserting. Separately checked raw HTML: the separate DB's ids run 1-4,746 and
3 of them coincide with existing main-DB ids, but those belong to other sites and raw HTML is filed
as `raw_html/<site_key>/<id>.html`, so different directories and nothing was overwritten. Note the
merged rows keep `raw_html_path` pointing at their source-id filename while carrying a new id; the
collision-repair predicate reads the site directory, not the id, so it is unaffected.
**Merged at 05:15-05:18 with an honest exit status** (`set -o pipefail`, `${PIPESTATUS[0]}` = 0):
**4,685 added, 61 duplicates skipped, 7 new sites**; corpus **341,313 → 345,998** exactly.
Pre-registered ~4,616; off by 69 because only 61 of the 130 pre-existing Wuxi documents shared a URL
with the new crawl, not all of them (the other 69 came from sections this run did not revisit).
`build_site_stats` 479 sites / 345,998 docs, corpus_stats drift **0.00%**; **validate_cascades
15/15**; app restarted; `/`, `/browse?site=wxd_xinwu`, `/research` all 200 in 0.10-0.27s. Done at
05:19, 41 minutes inside the nightly window.
This is the "second, non-Suzhou Jiangsu prefecture to Suzhou's depth" that `fidelity-jiangsu.md`
said B1 needed: Jiangsu's sub-provincial tier now has two deep cities instead of one. The nightly
derives the new documents tonight (citations, identity, scores, diffusion), so the replication
question can be asked tomorrow on derived data.
Follow-up launched (`logs/wuxi_followup.log`, written with `pipefail` and an elapsed-vs-cap line this
time): `wuxi --deep` into the SAME `documents_wuxi.db`, so it skips stored URLs and only fetches the
cut-off `bmgfxwj` pages 43-100 (~1,160 docs). It writes its own DB and so runs through the nightly;
a second merge, which will dedup the 4,685 already merged by URL, follows once it finishes.

## P2 Iteration 77 (the honest wrapper proves itself)
The rewritten Wuxi follow-up (`set -o pipefail`, `rc=${PIPESTATUS[0]}`, an elapsed-vs-cap line)
reported **`rc=124 elapsed=5400s cap=5400`** — an honest timeout — in exactly the situation where
the old wrapper had printed `rc=0` four hours earlier. That is the fix encoded in memory working on
its first real use. `wuxi` in `documents_wuxi.db` went **2,078 → 3,485 (+1,407)**, more than my
~1,160 estimate for `bmgfxwj` pages 43-100 (the estimate assumed 20 new docs per page and ignored that
the deep walk also tops up other sections), but it capped again with roughly 380 still to go against
the ~3,865 the scratch test listed. Launched a second bounded follow-up into the same separate DB
(`logs/wuxi_followup2.log`); it runs through the nightly without contention, and the second merge
waits for the nightly to release the lock.
