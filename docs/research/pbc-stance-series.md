# The PBC Monetary Policy Committee as a Quarterly Stance Series

**Status: finding, with its full population stated.** Built 2026-10-09 from the PBC historical
backfill. Companion to `rmb-coverage.md` (which measures how much the corpus *holds* on the RMB)
and `pbc-fx-position-2026.md` (which reads one position statement closely).

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

**以我为主 ("primarily based on our own conditions") never appears.** It is widely quoted as a PBOC
formulation on policy autonomy, and it is **not committee language** — a negative result only a
complete series can establish, and one a sampled or keyword-searched approach would likely have
reported as present from a non-committee source.

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
