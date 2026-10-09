# The Export-Control Regime as a Documentary Object

**Status: finding, with its panel stated.** Built 2026-10-09 with
`scripts/rnd/analysis/panel.py`. Companion to `related-literature.md`, which recorded this
as "a candidate, not a claim" because it needed a fixed-site panel. It now has one.

## 1. What this is, and what it is not

`related-literature.md` lists **NBER w31676, Exporting the Surveillance State via Trade in AI**
(Beraja, Kao, Yang, Yuchtman) as unreachable on this corpus, and the measurement behind that
verdict is blunt: **出口管制 ∩ 视频监控 = 1 document.** The paper's object is surveillance-AI
export *flows*, and the flows are simply absent from our holdings. No amount of panel discipline
recovers them.

What *is* present is the export-**control** regime itself: the statute, its implementing
instruments, its licensing machinery, and its spokesperson record. That is a different paper, and
calling it a replication of w31676 would be exactly the relabelling `consistency-review.md` exists
to catch. **This memo is the swap, stated as a swap.**

## 2. The panel, and why the obvious one is wrong

My first attempt used the project's default panel and produced a **THIN** verdict at
**n = 9**. That was a category error worth recording, because the verdict caught it before it
became a finding.

The default panel (18 sites, ≥30 docs/yr, 2013-2025) is overwhelmingly **Guangdong municipal** —
gz, huizhou, jiangmen, jieyang, shanwei, shaoguan, yangjiang, zhongshan, zhuhai — with `mof` the
only central site. Export control is a central instrument regime. Asking a sub-national panel
about it is asking the wrong body.

**A central panel back to 2013 does not exist on this corpus,** and that is worth recording for
every future central-level series:

| window | ≥30 docs/yr | ≥15 docs/yr |
|---|---|---|
| 2013- | **1** site (mof) | 2 (mof, mofcom) |
| 2016- | 3 (cac, mof, mofcom) | 4 (+most) |
| 2018- | 3 (cac, mof, mofcom) | **5** (+mee, most) |
| 2020- | 6 (+mee, most, sic) | 6 |

Central coverage is broad but shallow *per site per year* before ~2018. The 2020-start panel has
six sites and is useless here, because a panel beginning in 2020 cannot test a step at 2021. So:

> **Panel used: central documents only (`doc_identity.admin_level_doc = 'central'`), five sites
> (cac, mee, mof, mofcom, most), ≥15 dated documents per site per year, 2018-2025 complete, 2026
> partial and reported separately.** Denominator 370 (2018) rising to 969 (2025).

## 3. The series, with a built-in control

Share of panel documents mentioning each term:

| term | 2018 | 2019 | 2020 | **2021** | 2022 | 2023 | 2024 | 2025 | panel n | ρ raw | ρ share |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 出口管制 | 0.00% | 0.23% | 0.98% | **11.88%** | 4.92% | 10.96% | 9.93% | 11.25% | 502 | +0.952 | +0.738 |
| 两用物项 | 0.27% | 0.46% | 0.49% | **5.47%** | 1.64% | 4.31% | 5.25% | 6.30% | 248 | +0.976 | +0.857 |
| 出口许可 | 1.89% | 0.92% | 2.30% | **4.94%** | 1.95% | 4.03% | 4.24% | 3.41% | 207 | +0.857 | +0.619 |

All three verdicts are **OK** — raw and panel agree in sign, so the panel is confirming the raw
reading here rather than overturning it.

**The three rows together say more than any one of them, because 出口许可 is a control.** Export
*licensing* is pre-existing administrative machinery; 出口管制 and 两用物项 are the 2020 statute's
own vocabulary. The statute's terms step by roughly 12× and 11× and then hold for five years; the
pre-existing term roughly doubles. A single series could not distinguish "the law's vocabulary
entered the record" from "attention to trade restriction rose generally." The contrast can.

**It steps and holds rather than spiking and decaying.** On this corpus that is the signature of a
statute creating a permanent instrument stream, as against the campaign bursts
`attention-campaigns.md` measures, where a topic's share peaks and falls back. The 2022 dip
(11.88% → 4.92% → 10.96%) is the one irregularity and this memo does not explain it.

**Dating, stated carefully.** 出口管制法 took effect **2020-12-01** — that is external knowledge,
not a corpus measurement. Our own copy of the statute (id 12704305, mofcom) is dated **2021-12-29**,
which is a re-publication, so *our* date must not be read as the enactment date. The documentary
step therefore *follows* the statute by months, which is what an implementation ramp looks like.

## 4. Who writes it, and what genre it is

The genre check is the one that could have killed the finding, since a step made of news coverage
is not a step in the regime.

**2021, on the central panel:** mofcom `other` 76, mofcom `promulgation` 8, cac `explainer` 2, cac
`other` 1, cac `promulgation` 1, mee `promulgation` 1 — and **news: 1 document.**

Across all 1,071 出口管制 documents the genre split is `other` 470, `news` 367, `promulgation` 194,
`readout` 20, `explainer` 12, `implementing` 8. The 367 news documents sit on **guancha (253)** and
**ifeng (73)**, media sites the panel already excludes. That is exactly why the raw series inflates
and the panel does not: per-document level is **central 638 / media 379** / municipal 20 /
provincial 17 / research 13 / district 4. In the partial 2026 column the raw count is **357**
against a panel count of **43**.

By site: **mofcom 500**, guancha 253, gov 73, ifeng 73, stdaily 19, xinhua 19. By lead issuer
where one is resolved: 商务部 96, 国务院办公厅 34, 国务院 30, 中共中央 15, 中央网信办 8,
广东省商务厅 6. (792 of the 1,071 have no resolved lead issuer, so read the issuer ranking as a
floor.) Note 美国商务部产业与安全局 appears as a lead issuer on 11 documents — the regime's record
includes the *counterparty's* instruments.

Highest-inbound anchors inside the regime: 数据安全法 (322), **出口管制法 (134)**,
**两用物项出口管制条例 (107)**, 两用物项和技术进出口许可证管理办法 2005 (42).

## 5. AI is inside the regime, not beside it

Documents mentioning each term, within the 1,071:

| 半导体 | 芯片 | 人工智能 | 算力 | 算法 |
|---|---|---|---|---|
| 217 | 202 | 192 | 73 | 48 |

So roughly a fifth of the export-control record touches AI explicitly and more touches
semiconductors. This is the honest form of the AI-export question: **AI appears as one controlled
domain inside a general technology-control regime**, not as a measurable export flow. On the
central panel 人工智能 itself runs 3.78% (2018) → 18.78% (2025), verdict OK, ρ share +0.833.

## 6. The regime's justification record, and why it was invisible

The regime's reasoning is held in MOFCOM spokesperson Q&A on `exportcontrol.mofcom.gov.cn`, a
dedicated portal we crawl. These documents name counterparties, firms and dates directly —
就英制裁中国企业答记者问, 就加强两用物项对日本出口管制答记者问, 就安世半导体相关问题答记者问,
就荷经济大臣卡雷曼斯就安世半导体问题表态答记者问, 就美方暂停实施出口管制穿透性规则答记者问.

**All of it was unreachable until 2026-10-09.** 725 mofcom documents had titles in which every CJK
character was a literal ASCII `0x3f`, served that way by the listing endpoint (the article pages are
clean, and 724 of the 725 bodies are intact and unaffected). A mojibake title is invisible to both
FTS indexes, can never be a citation target, and can never match a `title_reissue` edge, so the
ministry holding 500 of these 1,071 documents had 725 of its documents absent from every
title-keyed analysis. Recovered by `scripts/rnd/backfill/repair_mofcom_titles.py`.

This is the generalizable point, and it is not about encodings: **a corpus can hold a document and
still not have it.** Any count keyed on titles silently excluded these.

## 7. The Unreliable Entity List as a paired series

The title recovery in §6 made a sub-series legible that had been half-invisible. The corpus holds
**39 Unreliable Entity List documents spanning 2020-09-18 to 2025-11-05** — the 2020 规定 that
created the mechanism, **22 instruments** (listings, investigations, suspensions, adjustments) and
**15 spokesperson justifications**. 15 of the instrument titles name a specific firm: 洛克希德·马丁,
雷神, 波音防务, 通用原子航空系统, PVH, 因美纳 (Illumina), 斯凯迪奥 (Skydio), 护盾人工智能 (Shield AI),
萨罗尼克科技, 环太平洋防务, 特科姆, 海岸间电子, 反无人机技术.

**The instrument and its justification are near-simultaneous.** Pairing each instrument to its
nearest later justification within 21 days: **17 of 22 pair, median lag 0 days, maximum 8**, and
**12 of 17 (71%) are same-day or next-day**.

| listing date | lag (d) | firms listed |
|---|---|---|
| 2024-05-19 | 7 | 通用原子航空系统 +3, 波音防务 |
| 2024-09-23 | 6 | PVH (investigation opened) |
| 2025-01-01 | 1 | 洛克希德·马丁导弹与火控 +10 |
| 2025-01-13 | 0 | 海岸间电子 +7 |
| 2025-02-03 | 8 | PVH, 因美纳 |
| 2025-04-03 | 0 | 斯凯迪奥 +11 |
| 2025-04-08 | 0 | 护盾人工智能 +6 |
| 2025-09-24 | 1 | 萨罗尼克科技 +3 |
| 2025-10-08 | 0 | 反无人机技术 + 外国实体 |

**The lag appears to tighten** — 6-7 days on the 2024 actions, 0-1 on most of 2025 — but this memo
does **not** call that a finding. n is 17, one 2025 action still lags 8 days, and 5 instruments have
no justification within 21 days at all. It is recorded as a shape to re-measure, not a trend.

What is solid is the simultaneity itself: on this record the regime does not announce a listing and
explain it later. The explanation ships with the instrument, which is a different communicative
posture from the campaign documents in `attention-campaigns.md`, where an instrument is followed by
a stream of 解读 over weeks.

**A correction to the §6 framing, measured rather than assumed.** I first read the delisted pages as
documents the portal had removed and we alone retained. That is **too strong**. Checking each
recovered row against same-window documents shows we already hold the same instruments under full
descriptive titles from a different crawl path, with **exact 文号 agreement** — 商务部公告2025年第1号,
第18号, 第21号, 第22号, 不可靠实体清单工作机制公告〔2025〕7号 and 〔2025〕8号 all have a
fully-titled twin. So no instrument was rescued from oblivion. What the recovery bought is narrower
and still real: 13 rows that were unsearchable now carry their 文号, which makes them findable and
links them to their twin by document number — the key `doc_identity.instrument_id` pools on. The
bodies differ substantially between twin and recovered row (20-char shingle overlap 0.02-0.47), so
they are variant texts of one instrument rather than byte copies, and which text is fuller is not
established here.

## 8. Limitations

1. **166 of the 1,071 documents (15.5%) have `date_written = 0`** and are therefore absent from
   every series in §3, concentrated on `gov` (73) and including **两用物项出口管制条例**,
   **稀土管理条例** and **商用密码管理条例**. *(Cause corrected 2026-10-09,
   `docs/working/undated-citation-weight.md`: I first wrote that the regime's second anchor
   instrument "cannot appear in its own time series". The instrument IS dated — its npc canonical
   copy carries 2024-09-29 — and `instrument_id` pools all five copies correctly. The real defect
   is that **`doc_inbound` is computed per DOCUMENT**, so the 107 citations landed on an UNDATED gov
   mirror while the dated canonical reads inbound 0. The weight and the date both exist, never on
   the same row. This is corpus-wide, not local to this regime: **22,214 of 44,364 cited documents
   are undated and carry 120,361 of 270,695 citations — 44.5% of all citation weight.** 2,201 docs
   / 26,443 citations are recoverable by rolling `doc_inbound` up to `instrument_id`, with no date
   inference at all. `redate_from_html.py` is NOT the tool for this: the raw-HTML mirror begins
   2026-06-08, the droplet-migration date, so nothing crawled earlier has saved HTML to re-parse.)*
2. **Five sites is a small panel.** It is the largest one this corpus supports for a central series
   with a pre-2021 baseline, which is a statement about our coverage, not about China.
3. **The 2022 dip is unexplained.**
4. **Lexical presence is not aboutness.** A document mentioning 出口管制 may merely cite it. The
   genre and issuer cuts in §4 bound this but do not remove it; 19.8% of the 1,071 carry an
   instrument word (公告/令/通知/决定/办法/条例/清单/目录) in the title.
5. **No causal claim.** This is a description of a documentary record, not an estimate of the
   regime's effect on trade.
