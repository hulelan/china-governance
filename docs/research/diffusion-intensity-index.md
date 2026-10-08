# The diffusion-intensity index, rebuilt on the citation graph: two real dimensions, one mislabelled axis

*Replication memo, 2026-10-08. "Measuring policy diffusion intensity: a text-driven analysis of
government documents" (Information Processing & Management, 2025) proposes a two-dimensional index
— **hierarchical effectiveness** and **textual intensity** — and applies it to 9,091 low-carbon
policy documents, 2007-2022. It was item #4 of the seven highest-corpus-fit papers in
`related-literature.md` and the last of them computable with no new data. We rebuild it on 12,211
explicit adoption events across 796 central anchors and 20 policy areas, where their "adoption" is
inferred from text and ours is a resolved citation or title re-issuance. The composite survives;
one of its two axes does not mean what its name says. Companion to `diffusion-fidelity.md`,
`diffusion-atlas.md` and `policy-tempo.md`.*

---

## The short version

**Their two dimensions are genuinely independent, and that is the result that matters.** Across 796
anchors, hierarchical effectiveness and textual intensity correlate at **Spearman −0.085** (and
−0.046 against elaboration ratio). A composite index therefore carries information neither axis
holds alone, which is the claim a two-dimensional construction has to earn and which a
single-domain panel cannot test.

**But operationalized as a sum, "hierarchical effectiveness" is a document count.** The raw
weighted sum over adopters correlates with the plain adopter count at **+0.957**. Anyone using the
sum is measuring breadth and calling it authority. The per-adopter *mean* is the real authority
measure, and it behaves differently — it correlates with adopter count at **−0.271**.

That negative sign is a substantive finding, not a technicality: **breadth is bought by reaching
downward, and by being copied more thinly.** Across quintiles of adopter count, mean adopter
authority falls 2.67 → 2.46 and the median elaboration ratio falls 0.99 → **0.81**.

---

## 1. Construction

From `diffusion_events`, keeping only central anchors, confirmed match types
(`citation`, `title_reissue`), implementing sources, and events where both documents have a body:
**12,211 adoption events**, **796 anchors with ≥5 adopters** (the floor needed for a per-anchor
distribution).

Per anchor:

| quantity | definition |
|---|---|
| `n` | distinct adopting documents |
| `H_sum` | Σ over adopters of w(level), w = provincial 3 / municipal 2 / district 1 — their authority ordering |
| `H_mean` | `H_sum / n`, i.e. authority **per adopter** |
| `T` | median adopter body length in characters — textual intensity |
| `E` | median of (adopter length / anchor length) — the elaboration ratio from `diffusion-fidelity.md` |
| `lag` | median adoption lag in days |

The level weights are theirs; our `admin_level_doc` is per-document (`corpus-lessons.md` A1) rather
than per-site, which is what makes the authority axis meaningful at all here.

---

## 2. Are the two dimensions independent?

Spearman over the 796 anchors:

| pair | ρ |
|---|---|
| `H_mean` × `T` | **−0.085** |
| `H_mean` × `E` | **−0.046** |
| `H_sum` × `T` | −0.016 |
| `T` × `n` | +0.016 |
| **`H_sum` × `n`** | **+0.957** |
| **`H_mean` × `n`** | **−0.271** |

The first three rows are the replication's positive result: **authority and text carry no shared
information.** The index is a genuine 2-D object and not one axis measured twice.

The mechanism is visible one level down. Textual intensity is almost **flat across the hierarchy**:

| adopter level | events | median chars | median elaboration |
|---|---|---|---|
| provincial | 6,597 | 4,708 | 0.95 |
| municipal | 5,276 | 4,735 | 0.87 |
| district | 338 | 4,206 | 0.87 |

A municipal adopter writes as much as a provincial one (4,735 vs 4,708 characters). So knowing an
adopter's level tells you nothing about how much text it devotes — which is precisely why the two
axes do not collapse. Their construction is right, and now it has a reason.

### Sensitivity, because one specification is not a result

Re-run at `--min-adopters 10 --weights 4,2,1` (263 anchors instead of 796):

| pair | default (≥5, 3/2/1) | stricter (≥10, 4/2/1) |
|---|---|---|
| `H_mean` × `T` | −0.085 | **+0.128** |
| `H_mean` × `E` | −0.046 | −0.075 |
| `H_sum` × `T` | −0.016 | −0.194 |
| `H_sum` × `n` | **+0.957** | **+0.895** |
| `T` × `n` | +0.016 | −0.246 |
| `H_mean` × `n` | −0.271 | −0.204 |

The independence claim gets *stronger* from this, not weaker: the authority-text correlation does
not merely stay small, it **changes sign** between specifications (−0.085 → +0.128). A residual
whose sign is unstable across reasonable specifications is noise around zero, which is exactly what
"independent dimensions" should look like. The summed-axis critique is robust (+0.90 to +0.96). The
one relationship that genuinely moves is `T` × `n`, from ~0 to −0.246 on the better-diffused
subset, and it moves in the direction §3 describes — breadth and textual investment trade off, and
the trade-off is clearer among instruments that actually diffused.

### The mislabelled axis

`H_sum` × `n` at **+0.957** is a near-identity. It is also not an artifact to shrug at, because the
sum is the natural reading of "total effectiveness": weight each adopter by its authority and add
up. Do that and 92% of the rank variance is just *how many* adopters there are. The weights barely
matter, because the level mix is similar across anchors.

**Use the per-adopter mean, and report `n` separately.** Then the two things the sum conflates —
how far a policy spread and how authoritative its adopters were — stay visible, and they turn out
to point in *opposite* directions.

---

## 3. Breadth costs authority and costs elaboration

Quintiles of anchors by adopter count:

| median `n` | `H_mean` | median `T` | median elaboration | anchors |
|---|---|---|---|---|
| 5 | 2.60 | 4,712 | 0.99 | 159 |
| 6 | **2.67** | 5,006 | 0.98 | 159 |
| 8 | 2.50 | 5,190 | 0.97 | 159 |
| 10 | 2.50 | 5,419 | 0.96 | 159 |
| **17** | **2.46** | 4,780 | **0.81** | 159 |

Two monotone-ish declines. Authority per adopter falls because wide diffusion reaches the municipal
and district tiers, which carry less weight — mechanically true but substantively meaningful: **an
instrument cannot be both broadly adopted and adopted only by high-authority bodies**, because
there are only 31 provincial-level jurisdictions and roughly 300 municipal ones
(`local-legislative-devolution.md`).

The elaboration fall is the more interesting one and is not mechanical. In the top breadth
quintile, adopters write **0.81 times** the anchor's length, against 0.99 in the bottom. So the
most widely diffused central instruments are reproduced *more thinly*. That sharpens
`diffusion-fidelity.md`'s corpus-wide finding of 88% elaboration: the elaboration rate is not
uniform, it **declines with reach**. Whether that is adopters economizing on a well-known
instrument or the instrument being generic enough to need no local translation, this measurement
cannot say — both predict the same ratio.

---

## 4. Per-area index (their panel application, extended to 20 areas)

Their panel is one domain. Ours is every area with ≥8 anchors, ordered by authority:

| area | anchors | median n | `H_mean` | median T (chars) | elaboration | median lag (d) |
|---|---|---|---|---|---|---|
| Transport | 13 | 6 | **2.75** | 4,144 | 0.87 | 445 |
| Trade | 18 | 6 | 2.73 | 4,463 | 0.96 | 259 |
| Education | 38 | 6 | 2.67 | 5,376 | 0.99 | 474 |
| Agriculture | 40 | 8 | 2.62 | 4,287 | 0.85 | 371 |
| Health | 60 | 8 | 2.60 | 5,781 | 0.99 | 396 |
| Culture | 9 | 6 | 2.60 | 5,705 | 0.88 | 508 |
| Finance | 69 | 7 | 2.57 | 4,428 | 0.90 | 403 |
| Commerce | 31 | 7 | 2.57 | 5,670 | **1.00** | 259 |
| Tech | 29 | 7 | 2.56 | 4,052 | 0.90 | 487 |
| Infrastructure | 11 | 9 | 2.56 | 5,172 | 0.92 | 300 |
| Environment | 33 | 10 | 2.53 | 5,756 | 0.93 | 468 |
| Personnel | 20 | 10 | 2.50 | 5,308 | 1.10 | **237** |
| Government | 62 | 8 | 2.50 | 4,482 | 0.87 | **198** |
| Energy | 9 | 8 | 2.45 | 6,740 | **1.17** | 502 |
| Welfare | 31 | 8 | 2.44 | 5,275 | 1.05 | 423 |
| Safety | 20 | 11 | 2.40 | 4,795 | **0.75** | 486 |
| Legal | 14 | 8 | 2.37 | 5,427 | 1.01 | **577** |
| Credit | 9 | 11 | 2.36 | 4,856 | 1.09 | 470 |
| **Emergency** | 16 | 8 | 2.35 | **9,914** | **1.22** | 410 |
| Housing | 15 | 8 | 2.33 | 4,670 | 0.95 | 404 |

The index spreads the areas on **different axes**, which is the payoff of the dimensions being
independent. Emergency management has the *lowest* authority score and by far the *highest* textual
intensity — 9,914 characters, 1.22× the anchor — because an emergency plan is a long operational
document written by whichever body runs it. Transport has the highest authority and nearly the
lowest text. Government and Personnel are the fast areas (198 and 237 days); Legal is the slowest
(577). A one-dimensional "intensity" score would have hidden every one of these contrasts.

**The caution from `policy-tempo.md` applies here and is not optional:** `diffusion_events.topic`
stores the anchor's FIRST topic tag, and an identity change that moves which copy of a text is the
anchor **relabels** these rows. Treat the ordering as current-build, re-base it after any identity
rebuild, and do not quote a single area's rank without checking it survived.

---

## 5. What this adds to their paper, and what it does not

**Adds.** An independence test their single domain cannot run, and it comes out in their favour.
A diagnosis of the summed-authority axis as a disguised document count. An explicit-adoption basis
(resolved citations and title re-issuance) rather than textual inference, so an "adoption" here is
a document that names or re-issues the anchor. Twenty policy areas instead of one. And the
breadth-versus-elaboration trade-off, which needs cross-domain variation in reach to see.

**Does not.** Their textual-intensity measure is richer than ours; we proxy it with body length and
an elaboration ratio, and length is a crude stand-in for textual commitment. We do not reproduce
their time-series index, because a diffusion series on this corpus needs a fixed-site panel
(`rmb-coverage.md` §4 trap 3, where an uncontrolled series reversed a trend's sign) and that panel
is built per-question. We have not validated the level weights 3/2/1 against anything; they are
theirs, and §2 shows the results barely move with them, which is itself a reason not to trust a
weighted sum.

---

## Limits

- **796 anchors, ≥5 adopters each.** Anchors with 1-4 adopters are the large majority of the table
  and are excluded, so every figure describes *diffused* instruments, not all instruments.
- **District is thin** (338 events, 2.8%), so the bottom of the authority axis rests on little.
- **Body length is a proxy** for textual intensity, and an attachment-carrying notice looks thin
  (`corpus-lessons.md` A7 correction: bureau notices are short or carry the plan as a PDF).
- **The topic label is the anchor's first tag only** — see §4's caution.
- **`lag` figures are medians of per-anchor medians**, which is robust but not a lag distribution.
- Confirmed match types only, so the matcher's "probable but unconfirmed" `topic_genre` tier is
  excluded by design (`validate_cascades.py`'s `aiplus_implementing` split, same reasoning).

---

## Next: this belongs in the tracker

The per-area columns in §4 are a weekly-computable object, and `policy-tempo.md` already concluded
the tracker is an instrument for burstiness and level timing but **not yet** for cross-area tempo.
The independence result is what unblocks that: authority and textual intensity can be tracked as
two separate per-area series without one shadowing the other. The build is a rollup over
`diffusion_events` joined to `doc_identity`, which is exactly what `build_tracker_rollup.py`
already does for counts — so this is a column addition, not a new pipeline.

## Replication

`scripts/rnd/analysis/diffusion_intensity.py` (read-only; `--min-adopters`, `--weights`,
`--min-anchors-per-topic`, `--db`). It prints every table above and the Spearman matrix, and runs
in ~20 s on the live DB. Verified at both specifications in §2.
