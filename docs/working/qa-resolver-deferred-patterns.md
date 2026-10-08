# The two deferred resolver-precision patterns, measured

*2026-10-08, read-only. `consistency-review.md` H1 left two patterns open after the proxy-target
fix: "generic short titles" and "documents *about* an instrument winning containment". Both sounded
large. Measured, one is close to a non-problem and the other reduces to three title families — but
the measurement also surfaced something bigger that I deliberately do NOT report as a finding,
because it cannot be separated from a stale table until the owed rebuild runs.*

---

## 1. "Documents about an instrument winning containment" — largely already fixed

The archetype was 河南省实施《城乡规划法》办法 holding the law's 2,139 citations. The same shape
today, on 土地管理法:

| inbound | document |
|---|---|
| **665** | 中华人民共和国土地管理法 (the law) |
| 505 | 中华人民共和国土地管理法实施条例 |
| 270 | 广东省实施《中华人民共和国土地管理法》办法 |
| 11 / 4 / 3 / 3 / 2 | 上海市 / 陕西省 / 四川省 / 安徽省 / 西藏 implementing measures |

**The ordering is correct.** The law outranks its own implementing 条例, which outranks the
provincial measures, and Guangdong's 270 is plausibly real — Guangdong documents citing Guangdong's
measure. The exact-title tier is doing its job.

68,846 resolved edges point at a target whose title embeds a 《》 instrument, across 13,248 targets,
but inspection says most are **legitimate issuance wrappers**: `中共中央印发《中国共产党纪律处分条例》`
*is* that regulation's promulgating document, and `关于印发《X》的通知` is the standard vehicle. These
are what `instrument_id` exists to pool.

**One residual, and I recommend NOT fixing it.** `【疫情防控】图说：《公民防疫基本行为准则》…`
(liuzhou) holds **317 citers** — an infographic outranking the instrument it explains. But the
instrument itself is **not in the corpus**: that explainer is the only document whose title contains
公民防疫基本行为准则, so containment had exactly one candidate. Refusing explainer targets would
unresolve 317 edges without relocating them, because there is nothing to relocate them to. This is
coverage-bound, not matching-bound — the A6 lesson — so the fix is to **crawl**
公民防疫基本行为准则, not to tighten the resolver.

## 2. "Generic short titles" — reduces to three title families

Most high-inbound short titles are **mirror pooling working as designed**:
`中华人民共和国行政处罚法` is shared by 8 documents because there are 8 copies of one law.

The signature of a genuine collision is **no pooling at all** — `n_instruments == n_docs`, i.e.
every identically-titled document is its own instrument. Note that "more than one instrument_id" is
NOT the signature: `中华人民共和国政府信息公开条例` shows 22 docs / 3 instruments because the identity
layer **deliberately** separates the 2007 and 2019 editions, which is correct.

On that signature, with inbound ≥ 15: **3,904 citers across 72 winner documents and 60 titles.**
Inspecting them splits the class again:

| shape | example | verdict |
|---|---|---|
| genuinely different documents sharing a generic name | **政府工作报告** (25 docs, 283 citers), **房屋征收补偿决定书** (39 docs, 95), 国务院关于废止和修改部分行政法规的决定 (6, 126) | **real, and unresolvable in principle** |
| organization names | 省工业和信息化厅 (10 docs, 160) | **already fixed** — the `org_only_exact` gate, Prediction 1 in `prereg-next-rebuild.md`; only 211 of the 3,904 |
| copies of one text that failed to pool | 中华人民共和国道路运输条例 (5 docs), 互联网信息服务管理办法 (4) | a DIFFERENT bug — see §3 |

**Recommendation: a small denylist, not a general rule.** A reference to `政府工作报告` with no
jurisdiction qualifier is genuinely unresolvable, and resolving it to an arbitrary copy is worse than
leaving it unresolved — the same precision-over-recall trade the org-stub gate already makes.
`房屋征收补偿决定书` is the same shape (a document-instance name, not an instrument name), and
`决定书` / `通知书` / `告知书` endings generalize it. Total exposure ~660 citers, so this is a
30-minute change with a predictable sign, not a project.

## 3. What I will NOT call a finding yet

The §2 measurement surfaced something larger. Among families of identically-titled documents:

| | families | documents |
|---|---|---|
| pooled to one instrument | 3,423 | 9,052 |
| did **not** pool | **21,268** | **55,252** |

86% non-pooling looks alarming, so I split it by whether the copies are even inside the pooling
window:

| | families | documents |
|---|---|---|
| copies span **> 400 days** — edition separation, **by design** | 8,123 | 24,019 |
| copies **within 400 days** — should have pooled | **11,891** | **28,225** |

And many of those have a span of **0 days** — the same title on the same date, not pooled, with real
citation weight on one copy: 中共中央关于制定…第十五个五年规划的建议 (2 docs, span 0, **209 citers**),
国务院关于印发全面推进依法行政实施纲要的通知 (2 docs, span 0, 198), 中办印发《通知》… (3 docs, span 0,
253).

**Why this is not reported as a bug.** The live `doc_identity` is **stale relative to the current
code**: `localized_of` reads 2,014 where the pending rebuild predicts ~3,350
(`prereg-next-rebuild.md` Prediction 2), and 2,180 of the 11,891 families contain a document with no
identity row at all (crawled after the last build). Part of this is therefore staleness and part may
be a real pooling defect, and **the two are not separable until the rebuild runs.** Registering the
number now, before the rebuild, is the only way to tell which — so it is Prediction 5 there rather
than a claim here.

If it survives the rebuild it is worth real work: 28,225 documents is 8% of the corpus, and
`instrument_id` is what `citation_rank`, the diffusion anchors and the tracker's anchor-diversity
columns all pool on.
