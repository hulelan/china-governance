# Joint Issuance and Inter-agency Coordination: 10,304 Co-signed Policy Documents, 2005-2026

*Research-agenda Q7. Computed read-only on the droplet `documents.db` (2026-10-01) from the
`doc_issuers` table built by `scripts/rnd/classification/issuer_parser.py`. Every figure is
reproducible from the appendix queries. Evidence labels: [measured] = computed on the corpus;
[hand-checked] = manual validation; [inferred] = our reading of a measured pattern.*

---

## 0. The question and the short answer

**Question.** Is inter-agency coordination at the centre consolidating or fragmenting? The
fragmented-authority tradition reads jointly issued documents (联合发文) as the trace of
bargaining across bureaucratic lines. Two measurable quantities follow. The share of policy
documents carrying more than one signatory. The size of the signing coalition.

**Short answer.**

1. **Joint issuance at the centre is rising.** In the continuously crawled central set
   (gov.cn, NDRC, MOF, MEE) the share of policy documents with two or more signatories went from
   17% (2005-09) to 16% (2010-14), 24% (2015-19), 31% (2020-23) and 43% (2024-26). The rise is
   present inside every central site with a long series and inside every programmatic genre
   (意见, 行动方案, 决定). It is absent in routine 通知. [measured]
2. **Coalitions are larger.** Among co-signed central documents the mean coalition was 2.4
   agencies in 2010 and 3.9 in 2025. The median moved from 2 to 3 in 2023. Documents with
   five or more signatories went from 5% of joint documents (2010) to 30% (2025). A 10+ tail
   appeared after 2016 and peaked in 2021-23 (288 distinct central titles). [measured]
3. **The core cluster changed.** Until 2012 four in five co-signed central documents carried
   the Ministry of Finance and three in five were the MOF + State Taxation Administration
   dyad (tax circulars). After 2020 the hub is the NDRC (in 32% of co-signed documents, the
   lead signatory on 17%), with MIIT, SAMR and MOF as the usual partners. MOF is still present
   but no longer central. The shift survives removing the tax-circular sites. [measured]
4. **Co-signature buys breadth only at scale.** Two- or three-agency documents cascade no
   wider than single-ministry documents (2.6 vs 2.9 echoing sites; median 1 in both), which
   confirms the diffusion atlas. Coalitions of five or more are different: they are echoed
   2.5 to 3.7 times as often (13-19% vs 5%) and reach five or more sites twice as often. The
   effect is on whether a document is echoed at all, less on how far. The State Council
   masthead still buys more (20% echoed, 6.2 sites). [measured]
5. **Parser precision is high.** On a stratified hand-check of 40 documents the joint/single
   flag is right on 37 of 38 positive parses (97%), the exact coalition size on 36 of 38 (95%).
   The parser abstains on 2. [hand-checked]

Reading. The signature count is growing and the signers are many, which looks like
proliferation. But the coalitions are organised around a small set of hubs (NDRC, and the
中办/国办 pair at the top), the largest coalitions are programmatic documents that
pre-coordinate many vertical lines at once, and these cascade faster, not slower. We read this
as coordination being centralised in hubs while the number of parties each hub binds rises.
[inferred]

---

## 1. Data and frame

**Parser.** `issuer_parser.py` extracts signatories from four fields in priority order:
the 文号 agency code (lead only; the 联 token marks a joint document), the `publisher` field
(gov.cn stores the full masthead space-separated), the body header line, and the title head
("X部 Y部 Z总局关于…"). The elided form "商务部等N部门" yields `n_issuers = N` with only the
lead named. Names are folded to a canonical central registry (ministry general offices fold
into the ministry; 国务院办公厅 and 中共中央办公厅 stay distinct). Output table:
`doc_issuers(doc_id, issuers_json, n_issuers, lead_issuer, parse_source, inner_n_issuers)`.

**Coverage.** 267,844 documents parsed. 211,508 (79%) have at least one issuer. 13,370 have
two or more. The naive multi-publisher proxy the agenda cites finds 1,047. [measured]
*(Update 2026-10-01: after the 粤办 alias fix (§2f, commit `e8246b2`) the live joint count is
13,004, 13x the naive proxy; the 10,304 in the title and the frame table below moved by at most
the 396 corrected sub-national rows. Central figures are unchanged. The npc exclusion stated
above is this memo's rule; other memos count npc local regulations as central or re-level them,
so level shares are within-memo only (`consistency-review.md` M7).)*

**Analysis frame.** Policy genres only (`algo_doc_type` in regulation, notice,
policy_issuance, action_plan, opinion, decision, circular, work_plan, strategy, subsidy,
decree, standard, application_guide, law, plan, administrative). News, explainers, replies,
announcements and procurement are out. Media and research sites are out. The `npc` site is
out: its 30,438 laws are local people's congress texts filed under admin level "central" and
they are single-issuer by construction. Years 2005-2026 by `date_published`. The Shenzhen
bureau tier (admin level "department") is folded into municipal.

| level | policy docs with >=1 issuer | joint (n>=2) | joint share | mean n |
|---|---:|---:|---:|---:|
| central | 26,323 | 7,809 | 29.7% | 1.74 |
| provincial | 16,192 | 1,538 | 9.5% | 1.22 |
| municipal (+bureaus) | 26,079 | 866 | 3.3% | 1.05 |
| district | 2,915 | 91 | 3.1% | 1.04 |
| **total** | **71,509** | **10,304** | **14.4%** | |

**Normalisation.** Every trend is a share of that level's policy documents in that period,
never a raw count. The corpus grows about 70x across the window. A second, continuously
crawled set is used for robustness: central = gov, ndrc, mof, mee; provincial = gd, bj, sh;
municipal = sz, gz. Central duplicates (the same ministry text on gov.cn and the ministry
site) are collapsed by title where noted.

---

## 2. Joint-issuance share over time (Q1)

### 2a. By level and period, all sites [measured]

| level | 2005-09 | 2010-14 | 2015-19 | 2020-23 | 2024-26 |
|---|---:|---:|---:|---:|---:|
| central | 25.5% (n=2,107) | 25.0% (2,824) | 26.1% (6,797) | 32.2% (8,660) | 33.7% (5,935) |
| provincial | 0.8% (2,044) | 6.3% (2,929) | 3.1% (4,094) | 12.0% (3,672) | 22.3% (3,453) |
| municipal | 5.3% (1,515) | 2.8% (5,509) | 2.6% (5,762) | 2.8% (7,229) | 4.7% (6,064) |
| district | . | . | 1.1% (274) | 2.3% (1,386) | 4.4% (1,236) |

### 2b. Robustness set [measured]

| level | 2005-09 | 2010-14 | 2015-19 | 2020-23 | 2024-26 |
|---|---:|---:|---:|---:|---:|
| central (gov, ndrc, mof, mee) | 17.0% (948) | 15.9% (1,996) | 23.6% (5,623) | 31.2% (7,661) | 43.2% (2,748) |
| provincial (gd, bj, sh) | 1.0% (1,043) | 10.1% (1,741) | 1.3% (2,398) | 8.6% (2,002) | 12.5% (704) |
| municipal (sz, gz) | 0.0% (204) | 0.6% (522) | 0.2% (511) | 0.7% (843) | 1.0% (201) |

Central by year in the robustness set: 25.2% (2018), 26.2, 26.3, 31.3, 33.9, 35.6, 40.4,
45.1 (2025), 47.7 (2026 to date). Monotonic since 2016.

### 2c. The rise is inside sites, not between them [measured]

Joint share by period for central sites with a long series:

| site | 2005-09 | 2010-14 | 2015-19 | 2020-23 | 2024-26 |
|---|---:|---:|---:|---:|---:|
| gov.cn | 2.2 | 6.8 | 20.0 | 31.9 | 43.2 |
| ndrc | 4.1 | 8.7 | 32.6 | 39.2 | 60.5 |
| mofcom | 25.0 | 10.9 | 17.2 | 33.7 | 50.6 |
| cac | . | 6.7 | 16.8 | 29.6 | 36.6 |
| chinatax | 37.7 | 61.4 | 53.0 | 64.9 | 79.3 |
| mof | 52.3 | 54.9 | 54.5 | 29.0 | 36.5 |
| most | 12.5 | 15.7 | 51.9 | 36.6 | 16.2 |

Five of seven rise. MOF falls after 2020 because the MOF crawl added the 财政部文告 gazette
(2000 onward), which carries single-signer budget and accounting notices. MOST falls after its
*(**Level basis checked 2026-10-09. The headline is immune; the all-central variant is not.** This
memo takes levels from `sites.admin_level`, which files ~28k npc 地方法规 as central — and
**27,052 of them carry an issuer row**, almost all single-issuer local regulations sitting in the
central denominator. Re-measured:*

| all-central, any genre | site basis | per-document basis |
|---|---|---|
| 2010-14 | 12.9% (n=8,129) | **18.8%** (n=5,686) |
| 2015-19 | 13.6% (n=17,844) | **20.5%** (n=12,180) |
| 2020-26 | 14.3% (n=42,504) | **21.8%** (n=28,799) |

| fixed-site set (gov/ndrc/mof/mee) | share |
|---|---|
| 2010-14 | 15.1% |
| 2015-19 | 19.7% |
| 2020-26 | 31.5% |

***The robustness set is unchanged by construction*** *— npc is not one of its four sites — so the
memo's headline claim rests on the basis that was never contaminated. That is this memo's own
caution paying off rather than luck: it built the fixed-site set precisely because the all-central
denominator is composition-sensitive, and the level flaw turns out to be one more instance of that.*

***The all-central variant shifts by +6 to +7.5 points at every period*** *once the npc regulations
leave the denominator. One honest limit: my reconstruction above does not reproduce this memo's own
all-central figures (it reports a fall of 23% → 15%, where both my bases rise modestly), so the
period boundaries or the joint definition must differ. I therefore claim only that **the basis
materially affects this variant and not the headline** — not that any specific published figure
moves. Reproducing §2a's exact series on the per-document basis is the outstanding check.)*

2015-19 peak. The all-central series in 2a is flatter than the robustness set because the
early years are dominated by the chinatax site (tax circulars, 38-61% joint) and the late
years add SAMR and MIIT portals (11-19% joint, 2,287 documents in 2024-26). The 2026 dip in the
all-central series (28.7% vs 40.4% in 2025) is this composition effect: gov.cn alone is 50.2%
in 2026, SAMR 10.9%. [measured]

### 2d. Genre: programmatic documents, not routine ones [measured]

Central joint share by genre:

| genre | 2005-09 | 2010-14 | 2015-19 | 2020-23 | 2024-26 |
|---|---:|---:|---:|---:|---:|
| action_plan | 9.8 | 11.0 | 30.3 | 46.6 | 54.6 |
| opinion (意见) | 6.5 | 7.8 | 23.1 | 39.9 | 49.5 |
| decision | 2.0 | 2.5 | 3.7 | 16.3 | 21.4 |
| policy_issuance (印发) | 23.2 | 26.0 | 26.1 | 33.1 | 33.9 |
| notice (通知) | 34.5 | 32.1 | 31.0 | 32.1 | 35.2 |
| regulation | 7.3 | 9.8 | 9.9 | 15.9 | 13.9 |

The routine 通知 is flat at a third. The programmatic genres went from under 10% to about half.

### 2e. The top of the hierarchy: 中办 + 国办 [measured]

On gov.cn, documents led by the State Council, its General Office, the Central Committee or
its General Office were 1.4% joint in 2015-19, 18.8% in 2020-23 and 20.5% in 2024-26. The
joint form here is almost always the 中共中央办公厅 + 国务院办公厅 pair. Ministry-led
documents on gov.cn went 27.5% to 35.1% to 48.8% over the same periods, with the mean
coalition rising 1.64 to 2.10 to 2.58.

### 2f. Sub-national

Municipal and district joint issuance is rare and flat: 0-1% in Shenzhen and Guangzhou, 3-5%
across all cities. Joint documents at this level are mostly a line bureau plus the finance
bureau (money co-signature) or the party committee plus the government (惠州 两办 texts).

The provincial series is the least trustworthy. The 2010-12 Guangdong bump (19.7%, 19.8%,
11.0%, then 0.8% in 2013) is driven by 164 documents parsed as 中共广东省委办公厅 +
广东省人民政府办公厅. The hand-check found one of these (粤办函〔2012〕109号) whose body is
signed by the government office alone; the parser unions the 粤办 docnum alias with the
publisher field. Treat that bump as unverified. *(Update 2026-10-01: verified and fixed, commit `e8246b2`. The 粤办函 alias was mapping to 省委办公厅 and a sub-national 文号 was unioning with the publisher; the phantom 省委办公厅+省政府办公厅 pair fell 177 → 1 and the Guangdong 2010/11/12 policy-genre joint share collapsed from 27.9/33.0/16.5% to 0.6/0.9/1.4%. The bump was entirely the artifact. Central figures in this memo are unchanged; 396 sub-national rows were corrected and `doc_issuers` now rebuilds nightly.)* The 2022-26 provincial rise is partly real
(Guangdong 15.1%, 10.5%, 16.6% in 2022-24 against 1-2% in 2013-21) and partly composition:
the 2024-26 period adds the provincial bureau tier (福建, 重庆, 宁夏, 西藏 departments), where
11% of "provincial" joint documents are reposts of central texts. [measured, composition-sensitive]

---

## 3. Coalition size (Q2)

### 3a. Central joint documents by year [measured]

| year | joint docs | mean n | median | p90 | share n>=5 | share n>=10 |
|---|---:|---:|---:|---:|---:|---:|
| 2005 | 136 | 2.26 | 2 | 3 | 2.9% | 0 |
| 2010 | 133 | 2.40 | 2 | 3 | 5.3% | 0 |
| 2015 | 171 | 2.33 | 2 | 3 | 3.5% | 0 |
| 2018 | 651 | 3.06 | 2 | 5 | 14.1% | 2.2% |
| 2020 | 681 | 3.72 | 2 | 7 | 23.5% | 5.3% |
| 2022 | 700 | 4.06 | 2 | 8 | 24.7% | 8.3% |
| 2023 | 637 | 4.15 | 3 | 9 | 26.7% | 9.1% |
| 2025 | 615 | 3.93 | 3 | 8 | 30.4% | 3.6% |
| 2026 | 566 | 4.08 | 3 | 8 | 32.2% | 3.5% |

Mean signatories over all central policy documents, singles included: 1.23 (2010), 1.37
(2015), 1.74 (2020), 2.14 (2023), 2.18 (2025).

Distribution among the 7,809 central joint documents: two signers 57%, three 16%, four 6%,
five to nine 16%, ten or more 4.4%.

Sub-national joint documents also grew: provincial mean 2.0 (2010-14) to 3.4 (2024-26),
municipal 2.05 to 3.11. Both tails are thin (30 and 9 documents with 10+ in 2024-26).

### 3b. The 10+ mega-coalitions [measured]

288 distinct central titles (duplicates across gov.cn and ministry sites collapsed). Three
before 2016, 10 in 2016-17, 37 in 2018-19, 173 in 2020-23, 65 in 2024-26. Mean size 13.

Lead signatories: NDRC 44, MOFCOM 44, MIIT 33, NHC 23, SAMR 20, MOE 13, MEE 12, MOT 12.
Topics (`topics_algo`): Commerce 33, Tech 19, Health 15, Education 13, Environment 11.
Genres: notice 81, opinion 70, action_plan 58, policy_issuance 55. By title form: 91 are 意见,
58 are 规划 or 方案, 34 are annual campaigns (宣传周, 科普日, 质量月), 14 are 办法 or 规则.

The largest: 国务院食安办等28部门 food-safety awareness week (annual since 2019, the ceiling at
28), 商务部等27部门 on cultural trade (2022), 国家卫生健康委 + 24 on social psychological
services (2026), 商务部等24部门 service-trade 五年规划 (2021), 交通运输部等二十三个部门和单位
on maritime search and rescue (2022), 科技部等二十二部门 research-misconduct rules (2022).

Two kinds of document sit in this tail. Annual campaign notices, where the coalition is a
roster of every body with a stake and the size is stable year to year. And programmatic
意见/方案 where a lead ministry collects the signatures of every line it needs to move. The
second kind is what grew after 2018. [inferred]

---

## 4. Recurring clusters (Q3)

Central documents with two or more named issuers, duplicates collapsed by title. Shares are of
that period's named-joint documents. [measured]

| period | named-joint docs | top agency (share) | NDRC share | top pair (share) | top triad |
|---|---:|---|---:|---|---|
| 2005-12 | 928 | MOF 79.8% | 8.6% | MOF + 税务总局 59.1% | 海关 + 税务 + MOF (63) |
| 2013-19 | 1,769 | MOF 61.6% | 22.4% | MOF + 税务总局 30.9% | 海关 + 税务 + MOF (98) |
| 2020-26 | 3,671 | MOF 36.4% | 31.7% | NDRC + MOF 12.4% | NDRC + MIIT + MOF (186) |

2020-26 top pairs after NDRC + MOF: NDRC + MIIT 10.6%, NDRC + SAMR 8.0%, MOF + 税务总局 8.0%,
MIIT + MOF 7.8%, MIIT + SAMR 7.4%, MOE + MOF 6.3%, MOFCOM + NDRC 6.2%. Top triads: NDRC + MIIT
+ MOF 186, NDRC + MIIT + SAMR 152, NDRC + SAMR + MOF 136, MOFCOM + NDRC + MIIT 131.

Lead signatory of central joint documents: MOF led 73% in 2005-12, 42% in 2013-19, 14% in
2020-26. NDRC led 1.4%, 11.7%, 17.2%. MIIT 8.5% and SAMR 4.9% in 2020-26.

**Composition control.** The MOF dominance of the early periods is partly the chinatax and mof
sites (tax circulars are always MOF + STA). Excluding both sites: 2013-19 MOF 40.9% / NDRC
29.4%; 2020-26 NDRC 33.4% / MOF 32.7%. On gov.cn alone: 2013-19 MOF 43.9% / NDRC 25.8%;
2020-26 MOF 37.1% / NDRC 30.9%, with NDRC + MOF, NDRC + MIIT and NDRC + MIIT + MOF the top
pair and triad. The direction of the shift holds under every cut. [measured]

**Reading.** The early cluster is a fiscal dyad: a tax or subsidy rule needs the ministry that
pays and the administration that collects, plus Customs for trade. The later cluster is a
development-coordination hub: the NDRC convenes, MIIT brings industry, SAMR brings market
regulation, MOF brings money. MOF's share of coalitions fell from four in five to one in three,
but it is still the single most frequent partner. The hub moved from the agency that pays to
the agency that plans. [inferred]

**Sub-national.** Provincial joint documents: finance department present in 35%, party
committee office in 21%; top pair 省委办公厅 + 省政府办公厅 (flagged above). Municipal: finance
bureau 21%, party office 22%; top pairs are 惠州 市委 + 市政府 and Shenzhen 人社局 + 财政局.
District: finance bureau 44%. Below the centre the recurring partner is the one that controls
the budget line, which is the local analogue of the early MOF role.

---

## 5. Do joint documents cascade wider? (Q4)

Anchors are central policy documents 2010-25 in the frame; echoes are `diffusion_events` rows
(citation, title re-issue and topic-genre matches). Breadth is distinct echoing sites. The
State Council family is reported separately because its masthead dominates breadth. [measured]
*(Build note 2026-10-01: this section read `diffusion_events` during the resolver rebuild (run
log it. 10), so its base is between the 24,599-row and 26,565-row central builds. The table is
rebuilt nightly and was 32,825 rows (26,565 central + 6,260 provincial) on 2026-10-01; a further
resolver regression fix will change it again. Breadth here counts all rows including topic_genre,
whereas the atlas §6a issuer table counts confirmed events only, so the two breadth numbers are
not on the same base. See `consistency-review.md` H2 and M3.)*

### 5a. Ministry-led documents by coalition size

| coalition | docs | echoed | % echoed | mean sites (echoed) | median | % with 5+ sites | % reaching a city | mean first lag (d) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 10,946 | 569 | 5.2 | 2.86 | 1 | 13.0 | 56.1 | 430 |
| 2-3 | 4,450 | 269 | 6.0 | 2.58 | 1 | 14.1 | 53.5 | 417 |
| 4-9 | 1,488 | 191 | 12.8 | 3.45 | 2 | 16.2 | 62.3 | 333 |
| 10+ | 321 | 61 | 19.0 | 3.70 | 2 | 24.6 | 62.3 | 344 |
| SC/CC single (ref.) | 4,612 | 946 | 20.5 | 6.20 | 4 | 48.4 | 72.7 | 142 |
| 中办+国办 (ref.) | 460 | 130 | 28.3 | 6.88 | 4.5 | 50.0 | 82.3 | 170 |

By exact size, mean sites among echoed: n=2 2.62, n=3 2.46, n=4 2.17, n=5 4.20, n=6 4.06,
n=7 4.07, n=8 3.64, n=9 1.88, n=10+ 3.70. The step is at five.

### 5b. Robustness

The same gradient holds genre-controlled (notice, opinion, action_plan, policy_issuance,
work_plan only: echoed 3.9 / 5.5 / 12.0 / 19.0%; sites 3.17 / 2.73 / 3.54 / 3.83), on gov.cn
alone (5.7 / 8.2 / 16.4 / 22.1%), in the dense 2018-25 window (5.0 / 6.9 / 13.6 / 19.2%) and
with duplicate titles collapsed (5.2 / 6.1 / 12.9 / 18.3%).

Within genre the gradient is steepest where it matters. Share echoed, 1 / 2-3 / 4-9 / 10+
signers: 意见 11.3 / 19.6 / 26.0 / 33.3%; 行动方案 11.9 / 16.6 / 22.7 / 33.9%; 印发 5.9 / 9.2 /
14.6 / 10.2%; 通知 under 2% throughout.

Who is in the coalition matters a little. Among echoed ministry-led joint anchors, NDRC
present 3.40 sites vs absent 2.78; SAMR present 3.77 vs 2.87; MIIT 3.07 vs 3.02; MOF 2.85 vs
3.16. By lead: MOFCOM-led joint documents average 5.1 sites, MIIT-led 4.1, NDRC-led 3.3,
MOF-led 2.6.

### 5c. What this confirms and what it refines

The atlas finding stands for the coalition it could see. Its "joint ministries" class pooled
all coalition sizes: on live `doc_issuers` the atlas-style class (central non-SC anchors with
等N部门 in the title or n>=2) is 295 documents with 2-3 signers, 222 with 4-9 and 68 with 10+,
so two- and three-signer documents are half of it, not most. The 等N部门 cue the atlas used is
the elided form, which is typically large. The two- and three-signer half is no wider than
single-ministry documents (2.58 vs 2.86 sites, median 1 in both, 14% vs 13% at five or more
sites). *(Corrected 2026-10-01 per `consistency-review.md` M3; the earlier text said the class
was "mostly two- and three-signer documents".)*

With real coalition sizes the picture splits. A second or third signature adds nothing.
A fifth signature marks a different document. Five-plus coalitions are echoed 2.5x as often
as single-ministry documents, ten-plus coalitions 3.7x as often, and they are echoed sooner
(first echo at 333-344 days vs 430). The gain is on the extensive margin, whether any
sub-national unit responds, more than on the intensive margin, how many do. They still fall
well short of the State Council masthead (20% echoed, 6.2 sites, first echo at 142 days).

Mechanism. Each co-signing ministry has a vertical line (条) of provincial and municipal
counterparts that receives the document as its own instruction. A coalition of ten opens ten
such lines. A coalition of two opens two, and the second line is usually the finance or tax
line, which does not re-issue. That is consistent with the gradient appearing at five and with
the lag shortening rather than lengthening. More signatures do not act as more veto points at
the diffusion stage, because the bargaining has already happened before publication.
[inferred]

Confound. Mega-coalitions are programmatic 意见 and 方案, and those genres cascade regardless
of signature count. The genre control keeps the gradient, but topic salience is not controlled
and could drive both the coalition size and the echo. Breadth is a floor (Guangdong supplies
most echoes). Resolution is 52%. [caveat]

---

## 6. Parser validation and caveats (Q5)

### 6a. Hand-check [hand-checked]

Stratified sample of 40 policy-genre documents: central 18 (5 single, 7 joint-named, 4
elided, 2 abstained), provincial 11, municipal 7, district 4. Read the title, 文号, publisher
field and body header for each and compared with the parse.

| measure | correct | of | precision |
|---|---:|---:|---:|
| joint vs single flag | 37 | 38 | 97.4% |
| exact coalition size | 36 | 38 | 94.7% |
| lead issuer | 37 | 38 | 97.4% |
| full name list | 35 | 38 | 92.1% |
| abstentions (n=0) | 2 | 40 | . |

Errors. (1) 粤办函〔2012〕109号: body signed 广东省人民政府办公厅 alone; the parser unions the
粤办 docnum alias (省委办公厅) with the publisher field and returns a two-office coalition.
This is the one wrong joint flag and the likely source of the Guangdong 2010-12 bump. *(Update
2026-10-01: confirmed and fixed, commit `e8246b2`; the bump was entirely this artifact, see
§2f.)* (2)
国家发展改革委等部门 (open form, no N): the parser returns n=2 as a floor; the actual coalition
is five. (3) 工信厅联科函: the 联 code gives n=2 correctly, but 国家数据局综合司 is not in the
registry so only MIIT is named. (4) One Shanghai forwarding notice (转发市住房保障房屋管理局等制订的)
has the forwarder right but misses the inner coalition. The two abstentions are a chinatax
text with no masthead in any field (actually 财政部等) and a 税务总局令 whose issuer appears
only in the body. Both are recall misses, not false positives.

### 6b. The 等N部门 elision

1,128 of the 10,319 joint documents in the frame (10.9%) are elided: `n_issuers` is N from the
title and only the lead is named. These count correctly toward share and coalition size but
drop out of pair and triad counts, which therefore under-represent the large coalitions. A
further 370 (3.6%) are the open form 等部门 and carry n=2 as a lower bound. 35 are 联-code
only. The coalition-size series is a floor on about 4% of joint documents.

### 6c. Single-signer portals

A joint document is usually published by its lead ministry, under that ministry's name. Of the
3,633 central joint documents on ministry portals (gov.cn excluded), 1,849 (51%) have a
single-agency `publisher` field and a multi-agency title or header. The parser recovers these
from the title. It cannot recover a joint document whose portal strips co-signers from the
title as well. The joint share is therefore a floor, and the floor is lower on portals with
terse titles (SAMR, MIIT) than on gov.cn. Across sites, central joint documents are 7,824 rows
and 6,866 distinct titles: 12% are the same text on gov.cn and a ministry site.

### 6d. Forwarding and reposts

2,840 documents in the frame are forwarding notices (转发/批转) with a recoverable inner
coalition; 1,021 forward a joint document (provincial 546, mean inner size 3.4). These count
as single-issuer documents for the forwarder, which is correct, and the inner coalition is
kept in `inner_n_issuers`. Separately, 11% of provincial-site joint documents and 8% of
municipal ones are central texts reposted on a bureau site. These inflate sub-national joint
shares in the bureau-tier periods.

### 6e. Other

Publication date is not signing date. 2026 is a partial year. The provincial robustness set
has a 2010-12 artifact (6a, since fixed) and a 2022+ series that is partly a crawl-composition
change. Shares at municipal and district level rest on small joint counts (91 district
documents).

Scope boundary. Coverage bias (single-agency portals and Guangdong over-represented), ~52%
citation resolution in §5 so every echo count is a floor, and publication is not adoption. The
findings are mechanism-level claims about a document record. No regime-type labels. *(Added
2026-10-01 per `consistency-review.md` §2.)*

---

## 7. Centralising coordination or proliferating signers?

Both, at different layers.

The number of parties on a central document rose. Mean coalition 2.4 to 3.9 among joint
documents, 1.2 to 2.2 across all central policy documents, with a 10+ tail that did not exist
before 2016. More agencies are bound by each programmatic text. That is proliferation of
signers.

The organisation of those signatures concentrated. One hub (NDRC) sits in a third of
coalitions and leads the most. The 中办 + 国办 pair rose from 1% to 20% of the State Council
family on gov.cn. The programmatic genres (意见, 行动方案) are where coalition growth happened,
and those are the documents that pre-commit many vertical lines at once and then cascade
faster. That is centralisation of coordination.

The fragmented-authority reading predicts that more signatories mean more clearance points
and slower, narrower implementation. The diffusion evidence runs the other way: large
coalitions are echoed more often and sooner. The bargaining cost is paid before publication.
What the signature count measures is the breadth of the pre-commitment, not the number of
vetoes after it. [inferred]

**Next.** (1) Fix the 粤办 alias so a docnum code never adds a signatory the body does not
carry, then re-run and check the 2010-12 Guangdong series. *(Done 2026-10-01, commit `e8246b2`;
see §2f. Item (3) is also done: `doc_issuers` rebuilds nightly in Phase 2b.)* (2) Register 国家数据局 and other
2023+ bodies. (3) Wire `issuer_parser.py --since-days 3` into `daily_sync.sh` Phase 2b (noted in
the parser docstring). (4) Add topic salience (citation_rank of the anchor) as a control in
5a. (5) Test the hub finding on the inner coalitions of provincial forwarding notices: which
central coalitions does Guangdong forward?

---

## Appendix: queries

All run against `file:documents.db?mode=ro`. `POLICY` is the 16-genre tuple in section 1.
`LV` folds department into municipal. `YR` is `substr(d.date_published,1,4)`.

```sql
-- Frame
FROM documents d JOIN sites s USING(site_key) JOIN doc_issuers i ON i.doc_id=d.id
WHERE s.admin_level IN ('central','provincial','municipal','district','department')
  AND d.site_key!='npc' AND d.algo_doc_type IN POLICY AND i.n_issuers>=1
  AND substr(d.date_published,1,4) BETWEEN '2005' AND '2026'

-- Q1 joint share by level x period (PER = 5 period bins on YR)
SELECT LV, PER, COUNT(*), SUM(i.n_issuers>=2),
       ROUND(100.0*SUM(i.n_issuers>=2)/COUNT(*),1) <frame> GROUP BY 1,2;
-- robustness set: add AND d.site_key IN ('gov','ndrc','mof','mee','gd','bj','sh','sz','gz')
-- within-site: GROUP BY d.site_key, PER HAVING COUNT(*)>=30
-- genre: AND s.admin_level='central' GROUP BY d.algo_doc_type, PER
-- SC/CC vs ministry on gov.cn:
--   CASE WHEN i.lead_issuer IN ('国务院','国务院办公厅','中共中央','中共中央办公厅') THEN 'SC/CC' ELSE 'ministry' END

-- Q2 coalition size (central joint docs, per year; mean/median/p90 in Python)
SELECT i.n_issuers <frame> AND s.admin_level='central' AND i.n_issuers>=2 AND YR=?;
-- mega coalitions, dedup by title
SELECT MIN(d.id), REPLACE(REPLACE(d.title,' ',''),char(10),'') t, MAX(i.n_issuers),
       MIN(YR), MIN(d.topics_algo), MIN(i.lead_issuer), MIN(d.algo_doc_type)
<frame> AND s.admin_level='central' AND i.n_issuers>=10 GROUP BY 2;

-- Q3 pairs/triads: one issuers_json per distinct title, then
-- itertools.combinations(sorted(set(json.loads(js))), 2 | 3) in Python
SELECT MIN(i.issuers_json) <frame> AND s.admin_level='central'
  AND json_array_length(i.issuers_json)>=2 AND YR BETWEEN ? AND ?
GROUP BY REPLACE(d.title,' ','');
-- controls: AND d.site_key='gov'  |  AND d.site_key NOT IN ('chinatax','mof')

-- Q4 echo aggregate (TEMP tables on the read-only connection)
CREATE TEMP TABLE ech AS
  SELECT e.anchor_id, COUNT(DISTINCT sd.site_key) sites, COUNT(*) ev,
    MAX(e.source_level IN ('municipal','district','department')) reach_city,
    MAX(e.source_level='provincial') reach_prov, MIN(e.lag_days) first_lag
  FROM diffusion_events e JOIN documents sd ON sd.id=e.source_id GROUP BY 1;
CREATE TEMP TABLE cf AS
  SELECT d.id, d.site_key, YR yr, d.algo_doc_type g, i.n_issuers n, i.lead_issuer lead,
    i.issuers_json js,
    CASE WHEN i.n_issuers=1 THEN '1' WHEN i.n_issuers<=3 THEN '2-3'
         WHEN i.n_issuers<=9 THEN '4-9' ELSE '10+' END bk,
    i.lead_issuer IN ('国务院','国务院办公厅','中共中央','中共中央办公厅') sc,
    REPLACE(REPLACE(d.title,' ',''),char(10),'') t
  <frame> AND s.admin_level='central' AND YR BETWEEN '2010' AND '2025';
SELECT bk, COUNT(*), SUM(b.sites IS NOT NULL),
  ROUND(100.0*SUM(b.sites IS NOT NULL)/COUNT(*),1), ROUND(AVG(b.sites),2),
  ROUND(100.0*SUM(b.sites>=5)/SUM(b.sites IS NOT NULL),1),
  ROUND(100.0*SUM(b.reach_city)/SUM(b.sites IS NOT NULL),1), ROUND(AVG(b.first_lag))
FROM cf LEFT JOIN ech b ON b.anchor_id=cf.id WHERE sc=0 GROUP BY 1 ORDER BY MIN(n);
-- variants: AND g IN ('notice','opinion','action_plan','policy_issuance','work_plan')
--           AND site_key='gov' | AND yr BETWEEN '2018' AND '2025'
--           AND cf.id IN (SELECT MIN(id) FROM cf GROUP BY t)

-- Q5 elision / floors
SELECT COUNT(*), SUM(json_array_length(i.issuers_json)<i.n_issuers),
       SUM(i.parse_source='docnum'),
       SUM(i.n_issuers=2 AND json_array_length(i.issuers_json)=1 AND i.parse_source!='docnum')
<frame> AND i.n_issuers>=2;
-- single-signer portals
SELECT COUNT(*), SUM(i.parse_source IN ('title','header') AND d.publisher!=''
       AND d.publisher NOT LIKE '% %' AND d.publisher NOT LIKE '%、%')
<frame> AND s.admin_level='central' AND d.site_key!='gov' AND i.n_issuers>=2;
-- reposts: lead_issuer IN issuer_parser.REGISTRY keys, on non-central sites
-- validation sample: python3 scripts/rnd/classification/issuer_parser.py --ids <40 ids>
--   ids drawn per (level, single|joint|elided|none) stratum ORDER BY ((id*2654435761+11)%1000003)
```
