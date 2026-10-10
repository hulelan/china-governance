# Production or demand? Testing the premise of "Monetary Policy in Mandarin Capitalism"

*Chang & Xiong (NBER w35562, 2026) argue China's credit booms produce no lasting inflation
because the regime is oriented to **production**: credit sustains output and firm balance sheets
rather than final demand. The inflation half of that needs macro series we do not hold. The
premise — that credit is directed at production — is a document fact, and the corpus supports it
in a sharper form than a word count can show. **Policy purposes sort by how they are financed, in
a monotone gradient: consumption measures are fiscal (以旧换新 fiscal:credit **1.83**), aggregate
production measures are credit-financed (实体经济 **0.60**), a 3× swing.** Meanwhile on a
fixed-site panel the credit vocabulary itself is **falling** in share (信贷 ρ = −0.72) while the
demand vocabulary rises — so the orientation claim is about the *channel*, not about where
attention is going.*

Tool: `scripts/rnd/analysis/mandarin_capitalism.py`. Companion: `pbc-stance-series.md` (which
tests the premise of w34626 the same way), `consumption-diffusion.md` (the demand campaign this
memo keeps running into).

## 1. What a document corpus can and cannot say about this paper

Their object is the credit/output/inflation relationship. We hold no price index, no credit
aggregate and no firm balance sheets, so **the inflation result is out of reach** and this memo
does not attempt it. What the corpus holds is the instrument record: what policy says credit is
for, and who pays for what. That is the paper's *premise*, and a premise is worth testing on its
own because the result rests on it.

## 2. The baseline, without which the conditional numbers are meaningless

A first pass looked decisive and was not. Among documents mentioning 信贷, **61.0%** also mention
a production term against **40.8%** for a demand term. But these are long documents — a
政府工作报告 mentions everything — so the number needs a denominator:

| | share of 303,788 bodied documents |
|---|---|
| any production term | 14.5% (44,161) |
| any demand term | 11.8% (35,780) |
| **baseline tilt** P(production)/P(demand) | **1.23** |

Against that, the credit-conditional tilt is real but modest. Both families lift strongly when
credit is mentioned (production 3.4–5.9×, demand 2.7–4.5×) — credit documents are simply *more
economic* — and the **ratio** moves only from 1.23 to:

| credit term | n | production | demand | production:demand |
|---|---|---|---|---|
| 信贷 | 6,920 | 61.0% | 40.8% | 1.50 |
| 贷款 | 13,949 | 48.8% | 32.9% | 1.48 |
| 融资 | 19,411 | 53.1% | 31.3% | 1.70 |
| 再贷款 | 1,464 | 76.5% | 52.9% | 1.45 |
| 社会融资规模 | 792 | 85.2% | 43.4% | 1.96 |

**Do not use the last row as evidence.** 社会融资规模 is *officially defined* as
实体经济从金融体系获得的资金总额 — "the total funds the real economy obtains from the financial
system". Its 80% co-occurrence with 实体经济 is a tautology of the definition, not a finding about
policy. It is reported here because leaving it out silently would be worse.

So the marginal test gives the paper's premise a weak yes: 1.5 against a 1.23 baseline. That is
not much to build on, and the reason is that it asks the wrong question — "do credit documents
mention production" rather than "how is each purpose paid for".

## 3. The finding: purposes sort by financing instrument

Conditioning on the *purpose* and asking which financing vocabulary accompanies it produces a
clean monotone ordering. Credit terms: 信贷 / 贷款 / 再贷款 / 融资. Fiscal terms:
补贴 / 专项资金 / 专项债 / 财政资金 / 奖补.

| purpose | n | fiscal | credit | **fiscal:credit** |
|---|---|---|---|---|
| 以旧换新 — consumer trade-in | 1,929 | 62.5% | 34.2% | **1.83** |
| 促消费 — demand stimulus | 2,188 | 46.0% | 30.6% | **1.50** |
| 技术改造 — firm-level upgrading | 5,746 | 53.7% | 51.5% | **1.04** |
| 产能 — productive capacity | 9,283 | 30.1% | 30.8% | **0.98** |
| 实体经济 — the real economy | 7,268 | 28.7% | 48.0% | **0.60** |

The ordering is the result, and it is the ordering the mechanism predicts: **demand measures are
financed from the budget; production measures are financed with credit.** The swing is 3×, it is
monotone across five purposes with no inversion, and the two ends are the purest cases — a
consumer trade-in subsidy at one end, the aggregate "real economy" at the other. 补贴 alone
accompanies 48% of 以旧换新 documents against 12% of 实体经济 documents.

This is a stronger version of w35562's premise than the paper's own framing needs. It is not that
policy talks about production more; it is that the *credit* channel and the *demand* channel are
institutionally separate, with different money behind them. Credit booms would then not transmit
to consumer demand because the instruments that reach consumers are not credit instruments.

## 4. And yet the attention is moving the other way

On the 21-site fixed panel (2013–2026, ≥30 dated bodied docs/yr), trends on the panel *share*:

| term | raw ρ | panel ρ | verdict |
|---|---|---|---|
| 信贷 | +0.80 | **−0.72** | **sign_flip** — raw is composition-driven |
| 产能 | +0.58 | **−0.77** | **sign_flip** |
| 实体经济 | +0.97 | +0.80 | ok |
| 以旧换新 | +0.83 | +0.72 | ok |
| 设备更新 | +0.88 | +0.70 | ok |
| 内需 | +0.76 | +0.44 | ok |
| 消费 | +0.92 | +0.24 | ok |

Two of these would have been reported as rising from the raw counts and are **falling** as a share
of a fixed panel's output: the credit vocabulary and the capacity vocabulary. What genuinely rises
is 实体经济 and the 2024 campaign pair.

So the paper's claim should be read as structural, about the channel, not as a claim that
production is where policy attention is heading. Attention has moved toward demand; the financing
architecture in §3 has not followed it.

**One qualification on the campaign pair.** 以旧换新 and 设备更新 are the two halves of one
instrument (大规模**设备更新**和消费品**以旧换新**), so their joint rise is partly one object
counted twice. They co-occur in **35.1%** of 以旧换新 documents and 31.2% of 设备更新 ones —
substantial, but not the near-identity the shared title implies. Two thirds of the consumption-side
documents do not mention the equipment-renewal half, i.e. localities implement the halves
separately. Read as support for the paper's reading, it is partial: the central instrument pairs
demand relief with capital-goods renewal, and the sub-national record splits them again.

## 5. Limits, stated

* **Co-occurrence in a document is not a financing fact.** A 通知 can mention 补贴 and 贷款 without
  either being its instrument. The gradient is robust to that only because the *ordering* across
  five purposes is what carries the claim, not any single share.
* **The inflation result is untestable here**, and so is anything about firm balance sheets.
* **The term lists are mine**, chosen concrete over abstract (an abstract term like 高质量发展
  appears on both sides of the divide and would blur it). They are in the script, not buried.
* **Every 2-character term here — 消费, 内需, 产能, 信贷, 贷款 — is invisible to the trigram
  index** and would have returned a clean, silent 0. The counts route through
  `scripts/rnd/analysis/fts.py`, which reports which index answered. Without it this memo's
  headline comparison would have been reversed, which is exactly the failure CLAUDE.md records.
* **The panel is a general-purpose one**, not a finance panel. A PBC/MOF/NDRC-only panel would be
  the better instrument for §4 and is the obvious next step.

## 6. Where this leaves the replication

w35562 is listed at fit **B** in `related-literature.md` because its result needs macro data. That
remains true. What this memo adds is that the premise it rests on is visible, directional and
sharper than a word count: the separation of credit from demand is in the financing vocabulary,
monotone across purposes, and it did not weaken when attention turned to consumption.
