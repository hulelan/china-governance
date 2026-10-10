# The PBC Monetary Policy Committee as a Quarterly Stance Series

**Status: finding, with its full population stated.** Built 2026-10-09 from the PBC historical
backfill. Companion to `rmb-coverage.md` (which measures how much the corpus *holds* on the RMB)
and `pbc-fx-position-2026.md` (which reads one position statement closely).

## 0. The literature this speaks to

**NBER w34626, "The Ins & Outs of Chinese Monetary Policy Transmission"** (Miranda-Agrippino,
Nenova & Rey, January 2026) builds a **novel indicator of the PBOC's monetary policy stance** and
estimates a policy rule for a **dual price-stability mandate — domestic inflation and the exchange
rate** — allowing for the evolution of the operating framework. Its abstract does not state how the
indicator is constructed.

**This memo tests their premise rather than replicating their estimate**, which is a different and
cheaper contribution. They assume the dual mandate; the committee's own readouts say whether it is
symmetric. §3 finds it is **not**: the exchange-rate leg is invariant across sixteen years and both
stance regimes while the domestic leg is the only thing that moves. And §2 gives their regime
changes an **external, public date** — 2010-12 and 2025-03, each preceded by one overlap quarter —
against which an econometric indicator can be checked.

Related, and consistent: **NBER w35562, "Monetary Policy in Mandarin Capitalism"** (Chang & Xiong,
July 2026) argues the regime is oriented to production rather than demand — credit sustains output
and firm balance sheets instead of generating inflation. A stance *word* that changes while the FX
frame holds fits that reading, though nothing here tests it.

## 1. The object

The corpus now holds **70 quarterly readouts** of the PBC Monetary Policy Committee
(货币政策委员会 … 季度例会), **2009-04-12 to 2026-09-24**, and **all 70 have body text**. These
became available only on 2026-10-09: the 沟通交流 section was capped at 40 pages and the documented
historical backfill did not work (`min(max_pages, cap)` made the cap always win), so the corpus held
31 PBC documents before the fix and **6,099** after.

This is an unusually clean object for a text measure. It is a **fixed institution** meeting on a
**fixed cadence** producing a **fixed genre**, so a vocabulary series over it needs no panel control:
the denominator is one readout per quarter by construction. That is rare in this corpus and is why
`panel.py` is not used here.

## 2. The stance word changed exactly twice in sixteen years

| term | readouts | span |
|---|---|---|
| **稳健** (prudent) | 57 | 2009-12 … **2025-01**, never after |
| **适度宽松** (moderately loose) | 15 | 2009-04 … 2010-09, then **2025-01 … 2026-09** |
| 灵活适度 | 14 | 2020-01 … 2025-01 |
| 精准有力 | 5 | 2022-12 … 2023-12 |
| 逆周期 (counter-cyclical) | 28 | 2011-12 … 2026-09 |
| 跨周期 (cross-cyclical) | 18 | 2020-09 … 2026-09 |
| **合理均衡** (reasonable equilibrium) | **60** | 2010-12 … 2026-09, continuous |
| **双向浮动** (two-way floating) | 33 | 2010-09 … 2026-09 |
| 超调 (overshoot) | 10 | 2023-09 … 2025-12 only |
| **以我为主** | **0** | **never** |

**Both transitions are marked by a single OVERLAP quarter carrying both words, then a clean switch.**

| transition | overlap quarter | clean switch |
|---|---|---|
| 适度宽松 → 稳健 | **2009-12** (both present) | **2010-12** |
| 稳健 → 适度宽松 | **2025-01** (both present) | **2025-03** |

The committee signals before it switches, and on this record it has done so exactly twice. The 2009-12
overlap did not stick — 2010-03, 2010-07 and 2010-09 revert to 适度宽松 alone before 2010-12 settles
on 稳健 — so the overlap marks *deliberation*, not an announced date. The 2025-01 overlap did stick.

## 3. The exchange-rate framework never changes; the stance around it does

This is the finding that matters for the RMB question, and it separates two things usually discussed
together.

**合理均衡 appears in 60 of 70 readouts, continuously from 2010-12 to 2026-09** — including straight
through the 2025 stance reversal. **双向浮动 runs 2010-09 to 2026-09.** Neither is interrupted by
either transition.

More than that: **合理均衡 first appears in 2010-12 — the very quarter the prudent stance began — and
outlived it.** The exchange-rate framework entered the committee's language with one monetary stance
and survived that stance's abandonment fifteen years later. So the stated FX objective is the stable
element and the monetary posture is the variable one, not the other way round.

**Intervention language is episodic.** 超调 ("overshoot", the vocabulary of leaning against a move)
appears in exactly 10 readouts, **2023-09 through 2025-12**, and is absent from 2026-03 onward. It
arrives and departs without reference to the stance change that happened in the middle of its run.

**以我为主 ("primarily based on our own conditions") never appears in a readout — and that is a
genre boundary inside one institution, not an absence.** Checked against the wider population rather
than banked as a negative: the phrase appears in **35 PBC documents** (and 42 on `gov`), 2010 onward,
but in **spokesperson Q&A, press conferences and governor speeches** — never in the committee's
formal quarterly readout:

> 2010-06 新闻发言人就进一步推进人民币汇率形成机制改革答记者问 — *…按照主动性、渐进性、可控性原则
> **以我为主**有序推进…*
> 2019-09 新闻发布会 — *…我们货币政策主要是服务国内经济，所以我们决定货币政策也主要是**以我为主**…*
> 2015-05 周小川 专题党课 — *…按照**以我为主**、循序渐进的方针…*

So the **autonomy claim** is made where a human speaks and takes questions, while the readout confines
itself to **objective language** (合理均衡, 双向浮动). "It never appears" would have been true and
uninteresting; "35 times in this bank's documents and zero times in its committee readouts" is a fact
about **where a claim is permitted to be made**.

**A caveat on the sibling series, recorded because it looked usable and is not.** The corpus also
holds **71 货币政策执行报告** (the bank's long quarterly Monetary Policy Report), 2009-02 to 2026-08 —
but their bodies are **announcement stubs**: median **80 characters**, maximum 2,325, and **zero of 71
above 5,000**. Only 25 carry more than 200 characters. The reports themselves are PDF attachments, so
**no text finding can rest on them**; the 以我为主 counts above come from the whole `pbc` site, not
from the reports. (The attachment-only shape is the same one `extract_pdf_text.py` addresses
elsewhere.)

## 4. What this is not

1. **Not a measure of policy, only of its stated frame.** A stance word is a label. Nothing here
   says what rates or reserves did.
2. **No panel control, deliberately** (see §1) — but that also means the measure cannot be compared
   against other issuers' series without one.
3. **Presence, not emphasis.** The series records whether a term appears in a readout, not how
   centrally. Readout length roughly doubles over the period (546 chars in 2009-04 to ~1,300-1,700
   from 2023), so later readouts have more room for any given term, which would inflate a naive
   count-based measure and is why this uses presence.
4. **The 2026 quarters are 2026-03, 2026-07 and 2026-09**, so the year is not complete.

## 5. As a tracker

The object updates quarterly by construction, and the nightly already crawls `pbc`. A tracker needs
only the 10 terms above plus the overlap rule in §2: **a quarter carrying both stance words is the
signal that the next one may switch.** That rule has fired twice in sixteen years and been right
once; a third firing is the thing to watch for.
