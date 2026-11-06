# 42,942 citations resolve to a document with no text

Found 2026-11-06 while assembling a single-document dossier for
工信厅信管〔2026〕42号 (《关于加强智能体终端设备进网管理的通知》). The dossier asked a
simple question — *for each instrument this 通知 cites, do we hold the text?* — and
the answer exposed two defects, one small and one large. The small one led to the
large one, which is the only reason it is worth recording.

## What prompted it

The 通知 names six instruments as its legal basis. Five were held, one was not
(《电信设备进网管理办法》, now `900210854`). Laying the five out **ordered by citation
count** made an anomaly immediate: the most-cited of them resolved to the least text.

| cited instrument | target id | target body | citers |
|---|---|---|---|
| 中华人民共和国网络安全法 | 12694498 | **2,256** | **696** |
| 中华人民共和国个人信息保护法 | 12694426 | 9,390 | 455 |
| 中华人民共和国数据安全法 | 12694435 | 5,648 | 340 |
| 中华人民共和国电信条例 | 12694530 | 11,322 | 141 |
| 中华人民共和国反电信网络诈骗法 | 12735203 | **0** | 62 |

`12694498` is the 新华社 wire release: a table of contents and the first three
articles, cut mid-第三条. The corpus also holds `12694197` at **11,047** chars (the
full statute) and `900022075` at **12,550** (China Law Translate's 2026 amended
edition). Both carry **0** citations.

## Defect 1 — a zero-width space makes a title unmatchable

`12694197`'s title is `'​中华人民共和国网络安全法'`. One **U+200B ZERO WIDTH
SPACE**, invisible in every rendering, defeats **two** normalization steps in
`scripts/rnd/citations/extract_citations.py:_norm_title`:

```python
_TITLE_STRIP = re.compile(r'[\s《》〈〉「」『』【】〔〕\[\]()（）“”‘’"\'、，,。．\.·・:：;；／/　<>]')
```

1. `\s` does not match U+200B. Python: `'​'.isspace()` is `False` (U+200B is
   category `Cf`, not `Zs`). So it survives the strip.
2. `s.startswith(_PRC_PREFIX)` is then `False`, so the `中华人民共和国` prefix is **not**
   stripped either.

Measured:

```
norm('中华人民共和国网络安全法')        -> '网络安全法'                       # the key refs match
norm('​中华人民共和国网络安全法') -> '​中华人民共和国网络安全法'    # unchanged
```

**Scope, measured over all 381,983 titles:** **559** carry an invisible character
(U+200B 523, U+200C 32, U+200D 6, U+00AD 1), spread over `bj` 133, `stdaily` 79,
`cac` 58, `guancha` 52, `bjrd` 28, `js` 25 and others. **73** are law-shaped
(法/条例/办法/规定/决定), i.e. plausible citation targets. Some sit mid-title
(`“十四五”扩大内需​战略实施方案`), which also breaks containment matching.

**What folding them would actually change — measured, not assumed.** Only **29**
documents would become a competing candidate for a key another document already
holds. Of those, exactly one changes a high-value target, and it is decided by the
documented tie-break `(genre_rank, level_rank, id)` rather than by guesswork:

* **网络安全法** — `12694197` and `12694498` are both `cac / promulgation / central`,
  so genre and level tie and the **lowest id wins**: `12694197`. The fix moves all
  696 citations onto the full text. Note it moves them onto the **2025-12-29
  amended** edition, which is a research judgment, not a bug fix.
* **劳动合同法 / 社会保险法 / 劳动法 / 就业促进法** — the full-text copies are on
  `nx_hrss` (`provincial`); the cited copies are `npc` (`central`, 0 chars). Level
  outranks, so the bodiless record keeps winning and the fix changes **nothing**
  for ~750 citations.

That last line is what turned a one-line fix into the finding below.

## Defect 2 — the tie-break has no notion of having a text

`TitleMatcher`'s mirror selection is documented as deterministic and is
`(genre_rank, level_rank, id)`: "promulgation over news, highest-level host, then
LOWEST id". **There is no body-length term.** Combined with a fact CLAUDE.md
already records — the `npc` tier is metadata-only, 0 of 31,070 rows carry text —
`npc` systematically wins the representative slot for national statutes.

**Measured over the whole corpus:** **719** normalized titles have a *cited* copy
with **no body** while a sibling copy of **≥1,000 chars** is held. Those targets
carry **42,942 citations**.

| citers | instrument | cited (bodiless) | full-text sibling held |
|---|---|---|---|
| 2,290 | 道路交通安全法 | `12738161` npc | `2985054` gdyjt 15,969ch |
| 1,138 | 行政处罚法 | `12738564` npc | `900081637` fj_scjgj 10,956ch |
| 1,068 | 财政违法行为处罚处分条例 | `12749213` npc | `900169975` gov 6,272ch |
| 953 | 安全生产法 | `12737824` npc | `900084147` fj_yjt 20,561ch |
| 800 | 行政许可法 | `12742121` npc | `900098637` bjb_tjj 11,489ch |
| 733 | 突发事件应对法 | `12731734` npc | `2576271` gdyjt 16,883ch |
| 631 | 食品安全法 | `12729148` npc | `900081632` fj_scjgj 30,903ch |
| 470 | 民法典 | `12740336` npc | `10464180` mzj **219,440ch** |

### State the consequence precisely

This is **not** a graph defect and the citation counts are not wrong. The edge
exists, and pointing a reference to 民法典 at the `npc` record of 民法典 is
arguably the *correct* identity choice. What is broken is narrower and easy to
state: **the representative chosen to carry the identity has no text, while a
text-bearing copy of the same instrument is in the corpus.**

So any analysis that follows an edge to its target's *text* gets an empty string
for ~43k edges: content-based co-citation, text similarity between citer and
cited, "what does the cited provision actually say", and any stem or fidelity
measure computed against the target body. Any analysis that only counts edges is
unaffected. Nothing currently records which kind a given memo is.

### Two possible fixes, and why the second looks right

1. **Add a body term to the tie-break** — prefer a text-bearing candidate when the
   top-ranked one has none. Small, but it changes *identity* to chase *text*, which
   is the wrong trade: it would make a 宁夏 provincial repost the canonical target
   for 社会保险法.
2. **Keep the identity, resolve the text through the pool.** `doc_identity.instrument_id`
   already pools copies of one text, and `instrument_inbound` already exists for
   exactly this reasoning in `citation-network-structure.md`. The target stays the
   `npc` record; the *text* is read from whichever copy in its pool has one. This
   separates identity from text availability instead of conflating them, and reuses
   machinery that is already built.

Option 2 is a read-path change in analysis code, not a resolver change, so it
cannot move a single edge. That is the main argument for it.

## Not shipped, on purpose

Neither fix is applied. Defect 1's one-line fold is unambiguously correct in
principle, but its only material effect is to redirect 696 citations onto a
different **edition** of 网络安全法, and which edition a 2017 citation should point at
is a research decision rather than a bug. Defect 2's fix is a change to the core
analytical layer affecting ~43k edges. Both are written up here with the
measurement so the decision can be made on evidence.

## Method note

The small defect was found by **ordering a six-row table by citation count** — not
by auditing for it, and not by any aggregate. Both the earlier proxy-target bug
(2026-10-01) and this one surfaced the same way: looking at *one document's*
citation neighbourhood closely enough to notice that the most-cited thing in it was
also the least plausible. That is an argument for building more single-document
views, which is what `docs/working/agent-terminal-dossier.md` records.
