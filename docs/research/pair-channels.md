# Pair Channels: What Citations, Title Re-issuance and the Renaming Layer Each See

*A methods memo on the china-governance corpus (SQLite on the droplet). All figures pulled
read-only from the live `documents.db` on 2026-10-07 with `scripts/rnd/analysis/pairs.py`, the
shared pair builder this memo introduces. It answers the open item in `fidelity-jiangsu.md` §7:
the citation path sees fewer than half of the renamed re-issuances the identity layer detects,
so the relay figures in `fidelity-provincial.md` and `diffusion-fidelity.md` are floors. This
memo puts a number on the floor. Commands and SQL are in the appendix.*

---

## 0. The question and the short answer

**Question.** The fidelity memos built their (source, parent) pairs from resolved citations plus
`title_reissue`. `doc_identity.localized_of` finds renamed re-issuances by title alone. How much
do the three channels overlap, how many pairs does each see that the others miss, and how far do
the citation-based relay and elaboration shares move when all three are pooled?

**Short answer.** On the province-to-city hop the union adds **362 pairs to 6,657** (5.4%) and
moves the Guangdong relay share from **8.9% to 9.1%** and the elaboration share from 73.0% to
72.6%. The relay count rises from 474 to 496. The floor is real and it is small. [measured]

The "fewer than half" figure is mostly a body problem, not a citation problem. 44% of the
Guangdong `localized_of` pairs on this hop have no resolved citation to the trigger, which
reproduces the Jiangsu memo's 46.5%. Restricted to sources that have a body (the only documents a
citation can be extracted from), the invisible share is **25.5%**. The citation channel sees
three in four renamed re-issuances it could see. [measured]

The larger gap is upstream of all three channels. The memos' framework gate on the parent
(`FW_GENRES` plus title cues) excludes 329 of the 643 Guangdong provincial triggers, almost all
`policy_issuance` notices printing 应急预案, 若干政策措施, 工作要点 or 重点工作任务. With the gate
off the province-to-city pair set grows from 7,019 to 10,153 and the renaming channel doubles
(319 to 630). The gate, not the channel, decides how many renamed re-issuances the memos count.
[measured]

---

## 1. The builder

`pairs.py` builds one row per (source document, parent instrument) and records every channel
that produced it. The rules are the same for every channel so the Venn compares like with like.

| rule | setting | source |
|---|---|---|
| levels | `doc_identity.admin_level_doc`, hop = parent level → source level | `corpus-lessons.md` A1 |
| parent identity | canonicalised to `instrument_id`; a citation to a mirror lands on the canonical member | A2 |
| parent is a framework instrument | `is_framework(algo_doc_type, title)`, not explainer/readout/news, not `NONISSUE_RE` | `fidelity-provincial.md` §1 |
| same province | required when the parent is sub-central; `build_diffusion_events.province_of`, site-derived | §1 |
| lag | source dated on or after parent, no cap | §1 |
| dates | Suzhou re-dated from the URL path | `fidelity-jiangsu.md` §7 |
| scoring | both bodies > 500 chars, 150k cap, character 5-grams, `ovlp_src`, relay > 0.7, mid 0.3 to 0.7 | `diffusion-fidelity.md` App. B |
| parent body | the canonical member's body, else the first named member's that clears the floor | new |

**Channels.** `citation` is a resolved `citations` edge or a `diffusion_events` row of
match_type citation. `title_reissue` is the `diffusion_events` row of that type. `localized_of`
is the `doc_identity` column. `topic_genre` is available and off by default.

**What the common rules cost each channel** (edges dropped before pairing, default hops,
framework gate on). [measured]

| channel | edges in | framework parent | lag < 0 or no date | province mismatch | other hop | same instrument | level outside C/P/M/D |
|---|---:|---:|---:|---:|---:|---:|---:|
| citation | 297k | 20,142 | 13,454 | 9,577 | 140,132 | 13,756 | 10,247 |
| title_reissue | 828 | 2 | 10 | 0 | 51 | 9 | 0 |
| localized_of | 2,592 | 491 | 530 | 163 | 17 | 0 | 0 |

Two of the `localized_of` drops are findings. 530 edges (20%) have the renamed document dated
before its trigger: the renaming detector is not date-ordered, and a city text that precedes the
same-stem provincial text is either a bottom-up case or a date error. 163 edges are `npc`
地方法规 whose site-derived province is None; the 人大 database carries no site province, so
these pairs need an issuer-derived province before they can join. Both are left as they are
here. [measured for the counts; inferred for the bottom-up reading]

---

## 2. The Venn

**Table 2a. Pairs by hop and channel combination** (default hops, framework gate on). A pair is
counted once, in the cell for the set of channels that produced it. [measured]

| hop | cit only | loc only | title only | cit + loc | title + loc | total | share seen by citation |
|---|---:|---:|---:|---:|---:|---:|---:|
| C→P | 17,706 | 802 | 284 | 64 | 6 | 18,862 | 94.2% |
| P→M | 6,483 | 87 | 217 | 174 | 58 | 7,019 | 94.8% |
| M→D | 953 | 6 | 0 | 3 | 0 | 962 | 99.4% |
| C→M | 23,150 | 168 | 187 | 19 | 4 | 23,528 | 98.5% |

No pair carries all three channels. `title_reissue` and `citation` never co-occur because
`diffusion_events` excludes already-cited pairs from the title path by construction; the raw
`citations` edges do not reinstate any. `title_reissue` and `localized_of` co-occur on 58
province-to-city pairs, which is 21% of the title channel on that hop.

**Table 2b. With the framework gate off** (`--no-framework`). [measured]

| hop | cit only | loc only | title only | cit + loc | title + loc | total |
|---|---:|---:|---:|---:|---:|---:|
| C→P | 22,087 | 823 | 284 | 115 | 6 | 23,315 |
| P→M | 9,301 | 241 | 222 | 331 | 58 | 10,153 |
| M→D | 1,365 | 11 | 0 | 5 | 0 | 1,381 |
| C→M | 26,667 | 188 | 193 | 33 | 4 | 27,085 |

The province-to-city renaming channel goes from 319 to 630 pairs, the citation channel from
6,657 to 9,632. The parents the gate had excluded are provincial 印发…的通知 whose core is an
emergency plan, a measures list or a work-points list: 298 `policy_issuance` and 30 `notice`
among the 329 Guangdong triggers. A city 应急预案 copying the provincial 应急预案 is the renamed
re-issuance object exactly, and neither memo could count it.

---

## 3. What the citation channel does not see

**Table 3a. `localized_of` pairs without a resolved citation to the trigger, by hop and
province** (framework gate on). "With body" restricts to sources whose `body_text_cn` clears the
500-character floor. [measured]

| hop | province | loc pairs | no citation | share | with body | no citation | share | median ovlp of invisible (n) | relay |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| P→M | gd | 293 | 129 | 44.0% | 220 | 56 | **25.5%** | 0.219 (46) | 19.6% |
| P→M | js | 26 | 16 | 61.5% | 13 | 3 | 23.1% | 0.545 (3) | 0.0% |
| P→M | all | 319 | 145 | 45.5% | 233 | 59 | 25.3% | 0.225 (49) | 18.4% |
| C→P | all | 872 | 808 | 92.7% | 92 | 30 | 32.6% | 0.252 (27) | 3.7% |
| C→M | all | 191 | 172 | 90.1% | 72 | 53 | 73.6% | 0.279 (46) | 0.0% |
| M→D | gd | 9 | 6 | 66.7% | 8 | 5 | 62.5% | 0.063 (5) | 0.0% |

With the gate off the Guangdong province-to-city row reads 582 pairs, 276 without a citation
(47.4%), 426 with a body of which 131 are invisible (30.8%), invisible median 0.303 on 113
scored, relay 19.5%.

Three readings. [measured]

1. **The unconditioned share reproduces the Jiangsu memo** (44.0% here against 46.5% there)
   and the conditioned share is 25 to 31%. Half of the apparent invisibility is sources with no
   body. A metadata-only record cannot cite anything; its absence from the citation graph says
   nothing about the resolver.
2. **The central-to-province renaming channel is an `npc` artefact.** 988 of its 1,417 triggers
   are 人大 law entries with no body, and the sources are mostly 人大 地方法规 entries with no
   body either: 92 of 872 pairs have a source body. The 92.7% figure is not a finding. Among the
   92 with a body, 30 are invisible (32.6%).
3. **The central-to-city channel is where citations are weakest** (73.6% invisible with a body,
   n=72). These are prefecture documents whose stem matches a central text directly. The Jiangsu
   memo §7 showed that in 22 of 25 such chains the city's text is closer to the provincial copy.
   The citation path misses them because the city cites the province, not the center, and the
   renaming layer attributes to the highest in-chain parent. Both channels are right about
   different things.

The invisible province-to-city pairs score lower than the Jiangsu memo's 0.408 (0.219 on 46,
0.303 on 113 with the gate off). The memo scored 257 invisible Guangdong pairs from the
unfiltered 645; the common rules keep 202 scorable of 296 (gate on) and the body floor and
canonicalisation move a few more. The relay share of the invisible set (19 to 20%) agrees with
the memo's 23%. [measured]

---

## 4. Fidelity by channel

**Table 4a. Province-to-city hop, scored pairs by channel combination** (framework gate on).
[measured]

| channel set | pairs | scored | median ovlp_src | relay | mid | elab | n relay |
|---|---:|---:|---:|---:|---:|---:|---:|
| citation only | 6,483 | 5,733 | 0.074 | 8.2% | 16.3% | 75.6% | 470 |
| localized_of only | 87 | 31 | 0.190 | 12.9% | 16.1% | 71.0% | 4 |
| title_reissue only | 217 | 117 | 0.158 | 11.1% | 27.4% | 61.5% | 13 |
| citation + localized_of | 174 | 164 | **0.525** | **28.7%** | 54.3% | 17.1% | 47 |
| title_reissue + localized_of | 58 | 18 | 0.485 | 27.8% | 38.9% | 33.3% | 5 |
| any citation | 6,657 | 5,897 | 0.077 | 8.7% | 17.3% | 73.9% | 515 |
| **union** | **7,019** | **6,063** | **0.079** | **8.9%** | **17.6%** | **73.6%** | **537** |

The pairs two channels agree on are the renamed re-issuances: median 0.525, relay 29%, mid 54%,
five to seven times the citation-only median. The pairs only one of the weaker channels sees are
in between (0.16 to 0.19). Gate off, the localized-only row grows to 98 scored at median 0.297
and 17.3% relay, and citation + localized to 285 scored at 0.546 and 30.2%.

The other hops do not move. C→P union 0.053 / 1.8% / 9.2% against citation 0.053 / 1.8% /
9.2%. C→M 0.044 / 0.2% / 3.0% against 0.044 / 0.2% / 2.8%. M→D 0.052 / 1.1% / 9.5% against
0.052 / 1.1% / 9.6%. [measured]

---

## 5. The floor, corrected

**Table 5a. Province-to-city, Guangdong, the memo's citation basis against the union.**
[measured]

| gate | subset | pairs | scored | median | relay | mid | elab | n relay |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| on | citation (memo basis) | 5,954 | 5,297 | 0.082 | 8.9% | 18.0% | 73.0% | 474 |
| on | **union** | 6,287 | 5,458 | 0.084 | **9.1%** | 18.3% | 72.6% | **496** |
| on | city portals, citation | 5,124 | 4,671 | 0.092 | 10.0% | 19.8% | 70.2% | 468 |
| on | city portals, union | 5,436 | 4,824 | 0.095 | 10.2% | 20.0% | 69.8% | 490 |
| on | implementing, citation | 4,657 | 4,253 | 0.120 | 11.1% | 22.0% | 66.9% | 472 |
| on | implementing, union | 4,990 | 4,414 | 0.121 | 11.2% | 22.2% | 66.6% | 494 |
| off | citation | 8,521 | 6,950 | 0.083 | 9.2% | 18.4% | 72.4% | 637 |
| off | union | 9,003 | 7,180 | 0.086 | 9.4% | 18.8% | 71.8% | 672 |

Jiangsu: citation 174 scored, 0.112 / 8.0% / 24.7%; union 177, 0.115 / 7.9% / 25.4%; 14 relays
either way. Beijing is unchanged at 106 scored (its districts carry no `localized_of` pairs to
provincial-tier parents).

**The relay share is a floor by 0.2 points and the relay count by about 5%.** [measured] The
elaboration share is a ceiling by 0.4 to 0.6 points. The memo's qualitative claims (relay five
times the central hop, 方案 copied and 条例 cited, the prefecture city as the copying tier) do
not depend on the correction. The memo's count of renamed re-issuances (381) is the figure that
moves: the union adds 22 relays at the memo's gate and 35 with the gate off, and the gate itself
withholds another 163 relays (637 against 474) that are the same object under a 应急预案 or
政策措施 title.

---

## 6. Recommendation

Re-base two passages, not the memos. `fidelity-provincial.md` §2.2 (the 381 renamed
re-issuances and the 75 / 20 / 5 decomposition) should be restated on the union set from
`pairs.py`, and its §7 "absolute pair count is a floor" line should carry the measured size of
the floor (relay +0.2 points, count +5%). `fidelity-jiangsu.md` §7 should restate "the citation
graph sees fewer than half" as "sees three in four of the renamed re-issuances that have a body;
the rest are metadata-only records", and drop the implied resolver deficit. `diffusion-fidelity.md`
needs no change: the central hop union is identical to its citation basis to the first decimal.
The decision that matters more than any channel is the framework gate. Admitting
`policy_issuance` parents whose 印发 core is an 应急预案, 政策措施, 工作要点 or 工作任务 would
raise the province-to-city pair set by 45% and the renaming channel by 97%; that is a change to
the target definition in `fidelity-provincial.md` §1 and `build_diffusion_events.is_framework`,
and it should be made once, in the identity layer, with a hand-check, before any memo is re-run
on it. Until then every memo should build its pairs through `build_pairs()` so the channel flags
travel with the rows. [inferred]

---

## 7. Honesty

- **Guangdong is 90% of the province-to-city hop** (6,287 of 7,019). Jiangsu adds 26 renaming
  pairs. Every correction above is a Guangdong correction.
- **The invisible set is small once conditioned.** 46 scored pairs at the memo's gate, 113 with
  it off. The medians (0.219, 0.303) and relay shares (19.6%, 19.5%) rest on those.
- **Canonicalisation changes which copy is scored.** The parent body is the canonical member's
  when it has one, else the first named member's. The memos scored the cited copy. Mirrors of one
  text share a body, so bands move little, but exact medians are not reproducible to the third
  decimal against the memos. The Guangdong citation basis here is 5,954 pairs and 5,297 scored
  against the Jiangsu memo's 5,781 scored on the same layer; the difference is the lag rule
  applied to the Suzhou-repaired dates, the parent-body fallback and raw edges that
  `diffusion_events` pooled differently.
- **`localized_of` is not date-ordered and not province-aware for `npc`.** 530 edges precede
  their trigger and 163 cannot be placed in a province. Both are dropped, not fixed.
- **Boilerplate sample differs.** The memos sampled 1,000 random corpus bodies; the builder takes
  a deterministic stride sample of the pair universe (a corpus-wide random sample is a full body
  scan). `ovlp_src_nb` is carried but not used above.
- **Runtime.** The default build and report run in 127 s on a quiet droplet with two workers
  (147 s for all six hops). The box has two vCPUs, so one competing CPU-bound process doubles
  it (269 s measured beside an unrelated job; 340 s when two builds overlap). Bodies are fetched
  per parent batch with the 150k cap applied in SQL; nothing is written.
- **Chronology, not causation; publication, not adoption.** As in every memo in this series.

---

## Appendix A. Commands and queries

```bash
# On the droplet (read-only). Default hops C→P, P→M, M→D, C→M; framework gate on.
python3 scripts/rnd/analysis/pairs.py --report --workers 2
python3 scripts/rnd/analysis/pairs.py --report --workers 2 --no-framework
python3 scripts/rnd/analysis/pairs.py --report --workers 2 --hops "C→P,P→M,M→D,C→M,C→D,P→D"
python3 scripts/rnd/analysis/pairs.py --csv /tmp/pairs.csv          # the pair table
python3 scripts/rnd/analysis/pairs.py --self-test                   # 17 synthetic cases
```

```python
# Library use
from pairs import build_pairs
rows = build_pairs(conn, hops=("P→M",), sources=("citation", "title_reissue", "localized_of"))
# each row: source_id, parent_id, hop, channels (set), source_/parent_ instrument_id, level, genre,
# doc_type, issuer, date, province, site, site_level, title; lag_days, forwarding,
# source_implementing, parent_framework; scored, ovlp_src, ovlp_anc, jaccard, ovlp_src_nb, band
```

```sql
-- Where the Jiangsu memo's 645 Guangdong provincial-trigger pairs go under the common rules
WITH L AS (
  SELECT s.doc_id sid, ds.date_published sd, length(ds.body_text_cn) slen,
         dt.date_published td, length(dt.body_text_cn) tlen, dt.algo_doc_type ttype, dt.title tt
  FROM doc_identity s JOIN doc_identity t ON t.doc_id = s.localized_of
  JOIN documents ds ON ds.id = s.doc_id JOIN documents dt ON dt.id = t.doc_id
  WHERE s.admin_level_doc IN ('municipal','district') AND t.admin_level_doc = 'provincial'
    AND dt.site_key GLOB 'gd*')
SELECT COUNT(*), SUM(sd < td) neg_lag,
       SUM(NOT (ttype IN ('regulation','opinion','action_plan','strategy','plan','law','decree','decision','work_plan')
                OR tt GLOB '*意见*' OR tt GLOB '*规定*' OR tt GLOB '*办法*' OR tt GLOB '*规划*'
                OR tt GLOB '*行动方案*' OR tt GLOB '*实施方案*' OR tt GLOB '*条例*' OR tt GLOB '*纲要*'
                OR tt GLOB '*决定*' OR tt GLOB '*细则*')) non_framework,
       SUM(slen > 500 AND tlen > 500) both_bodies
FROM L;
-- 643 | 59 | 329 | 422   (kept under both rules 296, of which 202 scorable)

-- Central triggers of provincial localized docs, by host site (the npc artefact)
SELECT dt.site_key, COUNT(*), SUM(length(dt.body_text_cn) > 500)
FROM doc_identity s JOIN doc_identity t ON t.doc_id = s.localized_of JOIN documents dt ON dt.id = t.doc_id
WHERE s.admin_level_doc = 'provincial' AND t.admin_level_doc = 'central' GROUP BY 1 ORDER BY 2 DESC;
-- npc 988 (2 with body), gov 365 (362), miit 10, chinatax 10, cac 10, ...

-- Non-framework provincial triggers: genre split
-- policy_issuance 298, notice 30 (应急预案, 若干政策措施, 工作要点, 重点工作任务 cores)
```

---

## Correction 2026-10-08: the renaming floor was a floor on a 54-name table

This memo reports its `localized_of` figures as a **coverage floor** and concludes the floor is
"real and small" (+0.2 points of relay). That conclusion measured one of our own lookup tables.

`build_doc_identity.locality_in_core` accepted a locality found in a title only if that locality
appeared in `KNOWN_LOCALITIES`, a **54-name set seeded from `_PROV_MUNI` plus the localities that
happen to have a 文号 registry head**. 苏州市 was in it, via 苏府. **无锡市 was not, because Wuxi has
no 文号 registry entry at all.** So `localize()` could not place a Wuxi title, and the renaming
channel fired on 2 Wuxi pairs against 44 Suzhou ones. Seeded instead from `geo.CITY_PROVINCE` (381
names, prefecture-level divisions only), `localized_of` goes **2,075 → 3,411 (+1,336)** with **0
edges removed, 0 retargeted and 0 pools split**, and 无锡市 goes **2 → 73** while **苏州市 stays at
83** — the cities that already worked do not move; only the invisible ones appear. Commit
`87eec6c`; the measurement is in `docs/working/qa-wenhao-province-ambiguity.md` §8. [measured]

Four things follow, and the first is the one that matters for reading this memo.

1. **The two bounds differ in kind.** A coverage floor rises when documents arrive. This one rose
   **64% with no new documents**. A number that moves when a hand-maintained list changes is not a
   bound on the corpus, so "the floor is real and it is small" was a statement about the table.
2. **No `localized_of` count computed before 2026-10-08 is comparable to one computed after**, and
   any PER-CITY figure from before that date measures which cities had a 文号 head rather than
   which cities re-issue. The Wuxi-versus-Suzhou contrast in `fidelity-wuxi.md` is in that class.
3. **The npc 地方法规 tier entered the channel for the first time**, taking **1,287 of the 1,336**
   new edges: 28.6k local 人大 instruments titled `<city>X条例` whose titles are their only locality
   evidence (a 地方法规 carries no masthead, which is exactly why the masthead fallback never
   rescued them). The sub-national-legislation share of this channel is therefore a **new series**,
   not a grown one, and should not be compared against earlier runs.
4. **The citation-basis results are untouched.** `diffusion_events` rebuilt **byte-identical**
   after the change, because its `IMPLEMENTING_IDENTITY_GENRES` covers promulgation and
   implementing alike, so the 1,336 genre flips are invisible to the matcher. `validate_cascades`
   stays 15/15 line for line. The **+0.2 point** relay figure in §2 stands as measured. [measured]

Adversarial check, since a wider list is a wider chance to mistake a mentioned city for the
issuer's: **zero misplacements** against two independent arbiters (2,149 of 2,149 agree with the
site's province; 9,873 confirm against the document's own publisher / `lead_issuer` / 文号 evidence,
0 name another province's city). Three structural reasons, each pinned in a test: the match anchors
at `^` on the core, so `广东省…关于学习推广无锡市经验的通知` keeps 广东省; a 转发 wrapper keeps the
wrapper as its core, so a forwarder never acquires the forwarded city; and `CITY_PROVINCE` holds
prefecture-level divisions ONLY, so the word-collision-prone county-level names are absent —
`东方市` (Hainan) is not in it, which is why `东方市场建设管理办法` keeps its 市. Hand-check: 30 of 30
newly-localized documents correct, 29 of 30 added edges correct; the one error
(`大同市人民代表大会常务委员会人事任免办法`) is self-government housekeeping of the class
`GENERIC_STEM_RE` already exists to exclude, and is 2 documents corpus-wide. [measured]

*Not yet live: the figures above are from read-only rebuilds. The stored table is 2,014 edges until
the next identity rebuild, which the nightly write lock is holding.*
