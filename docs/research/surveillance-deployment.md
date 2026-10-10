# Regulated centrally, deployed locally: the deployment side of AI-tocracy

*The AI-tocracy causal chain (Beraja/Kao/Yang/Yuchtman, NBER w29466) is out of reach here and
`related-literature.md` measured why. What is reachable is the object the three AI memos do not
cover: the deployment programmes themselves. Two findings. **(1) On one identical measure, the
state REGULATES AI centrally and DEPLOYS it locally** — deployment vocabulary is 57–86%
sub-national government, regulation vocabulary 6–37%, two distributions that barely overlap.
**(2) Most of the deployment vocabulary is not actually growing.** Three of eight terms rise
strongly in raw counts and FALL as a share of a fixed-site panel; only 技防 (+0.67) and 人脸识别
(+0.37) genuinely rise.*

Tool: `scripts/rnd/analysis/surveillance_deployment.py`. Complements `ai-governance-diffusion.md`,
`ai-regulatory-web.md`, `ai-plus-fidelity.md`, which are all about *regulating* AI.

## 1. Why this is not a replication of w29466, and what it is instead

Their unit is a procurement contract with a value and a vendor, linked to protest events. We hold
neither: 政府采购 ∩ 视频监控 is **285** documents (2.9% of 9,664), ∩ 人脸识别 **52**, ∩ 雪亮工程
**29**, and none carry contract values or vendor names. There is no protest data at all. The
causal chain is not available and this memo does not attempt it.

What the corpus does hold is the instrument record for deployment — programmes that are nameable
and datable. That is a different object from AI regulation, and it turns out to have a different
institutional signature, which is the finding.

**This memo follows an instruction left by the note that scoped it:** *"whoever runs it starts
with the panel rather than the headline."* So the panel verdict comes first, and `thin` is
reported as an answer rather than argued past.

## 2. The panel verdict, first

21-site fixed panel, 2013–2026, ≥30 dated bodied documents per site per year. Trends are on the
panel **share**; the raw ρ is on the count.

| term | n | index | raw ρ | panel ρ | verdict |
|---|---|---|---|---|---|
| 智慧城市 | 2,494 | trigram | +0.89 | **−0.31** | **sign_flip** |
| 视频监控 | 2,254 | trigram | +0.93 | **−0.58** | **sign_flip** |
| 技防 | 992 | **segmented** | +0.94 | **+0.67** | ok |
| 社会治安防控 | 690 | trigram | +0.74 | **−0.49** | **sign_flip** |
| 人脸识别 | 603 | trigram | +0.83 | **+0.37** | ok |
| 雪亮工程 | 204 | trigram | +0.54 | +0.27 | **thin** (82 panel docs) |
| 公共安全视频 | 177 | trigram | +0.28 | −0.16 | **thin** |
| 智慧警务 | 90 | trigram | +0.71 | +0.13 | **thin** |

**Three of eight read as strongly rising and are falling.** 视频监控 at +0.93 raw is the kind of
series that would anchor a claim about expanding surveillance; on a fixed panel its share declines
at −0.58. The corpus grew; the vocabulary's share of it did not.

**What genuinely rises is narrower than the headline would be.** 技防 — the building-code term for
technical security provisioning, which appears in construction and fire-safety documents — rises
at +0.67, and 人脸识别 at +0.37. So the growth is in *specific technology* and in *routine
provisioning*, not in the programme vocabulary (智慧城市, 社会治安防控) that peaked and receded.

**技防 is 2 characters and a trigram query returns a clean 0.** It is the single largest usable
series here and it is invisible to the index an unrouted query would reach. Counts go through
`fts.py`, which reports which index answered.

**雪亮工程 stays unreported as a trend, on purpose.** Its raw shape is suggestive — 3 documents in
2017, a 2018 local burst, a level inversion by 2021, a 2022 peak, decline since — but 82 panel
documents is below the 120 floor, and the post-2022 decline has two readings the counts cannot
separate: the programme winding down, versus maturing past the stage that generates documents.

## 3. The finding: regulated centrally, deployed locally

Measured the same way on both sides — the share of documents mentioning a term that sit at each
per-**document** level (`doc_identity.admin_level_doc`), with `media` split out because it is its
own level and "non-central" is therefore not "sub-national" (CLAUDE.md).

| deployment term | n | central | sub-national gov | media |
|---|---|---|---|---|
| 雪亮工程 | 204 | 13% | **86%** | 1% |
| 社会治安防控 | 690 | 18% | **80%** | 1% |
| 智慧警务 | 90 | 11% | **79%** | 10% |
| 视频监控 | 2,254 | 17% | **79%** | 3% |
| 技防 | 992 | 16% | **78%** | 6% |
| 公共安全视频 | 177 | 24% | **76%** | 0% |
| 智慧城市 | 2,494 | 21% | **70%** | 10% |
| 人脸识别 | 603 | 23% | **57%** | 19% |

| regulation term | n | central | sub-national gov | media |
|---|---|---|---|---|
| 算法推荐 | 260 | **70%** | 6% | 25% |
| 深度合成 | 150 | **66%** | 19% | 15% |
| 算法备案 | 156 | **63%** | 19% | 18% |
| 个人信息保护 | 1,716 | **64%** | 29% | 8% |
| 数据安全 | 4,426 | 48% | 37% | 15% |
| 生成式人工智能 | 592 | 32% | 20% | **48%** |

**The two distributions barely overlap.** Deployment runs 57–86% sub-national government;
regulation runs 6–37%. The nearest pair is 人脸识别 (57%) against 数据安全 (37%), and every other
deployment term sits above every regulation term. Read as a division of labour between levels:
the rules for AI are written at the centre, and the systems are installed by provinces, cities and
districts.

That is a claim about where documents are issued, not about who decides. A sub-national
implementing notice can be the faithful relay of a central instruction — this corpus has a whole
fidelity literature on exactly that (`diffusion-fidelity.md`, `fidelity-provincial.md`). What the
asymmetry establishes is that the *instrument record* for deployment is local in a way the record
for regulation is not, which is the opposite of what the AI-regulation memos find for their object.

**One contrast worth isolating: 生成式人工智能 is 48% media**, the highest media share of any term
on either table, and higher than its central share. That vocabulary lives in news coverage more
than in instruments — consistent with CLAUDE.md's record that a central-vs-non-central cut on the
generative-AI rule reads 45% "non-central" when 44 of those 47 documents are Xinhua, People's
Daily, 36Kr and Phoenix. 人脸识别 at 19% media is the most publicly discussed deployment term,
which fits it being the one with a privacy controversy attached.

## 4. Limits

* **A term is not a programme.** 技防 appears in construction and fire-safety documents where it
  means a provisioning requirement, so its +0.67 is partly the growth of building-code text rather
  than of surveillance. The series is honest about its vocabulary; the interpretation needs care.
* **The level split says where a document was issued, not who decided.** See §3.
* **No procurement values, no vendors, no protest data**, so nothing causal. §1.
* **Three of eight terms are `thin`** and are reported with their n and no trend.
* **The term lists are mine** and live in the script, both families, so the §3 contrast can be
  re-run against different choices. `tests/test_surveillance_terms.py` pins that the two families
  are disjoint, because an overlap would quietly destroy the contrast.
