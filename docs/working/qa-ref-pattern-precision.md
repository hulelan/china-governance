# QA: the named-《》 pattern capturing a run of body text as a reference name

*2026-10-07. Read-only forensics on the droplet DB (`?mode=ro`) while the A6 crawl chain
held the write lock — no writes, no rebuilds, no crawler runs, no droplet pull. Measured
on 277,117 `named` edges / 105,153 `formal` edges.*

Follow-up to `qa-cxgh-citer-drop.md`, whose last paragraph logged in passing that "the
江门市 body-fragment ref shows `REF_PATTERN` can still capture a run of body text as a
ref name".

**Verdict up front: the defect is real but it is in `NAMED_REF_PATTERN`, not
`REF_PATTERN`. It is 239 edges (0.086% of the named tier) over 196 documents. 53 of them
RESOLVE and are false edges; 186 are harmless unresolved rows. It pollutes the crawl
queue by 0.15% of distinct unresolved refs and by ZERO of the queue's top 400. The fix
makes the pattern balanced instead of truncating, which removes the false edges and — as
a side effect worth more than the fix itself — recovers 51 new correct resolutions per
3,061 on a 4,191-document sample.**

## 1. Which pattern, and the mechanism

`REF_PATTERN` (the 文号 tier) is not the culprit. Its leading `[一-鿿]+` is greedy and does
swallow prepended prose, but `canonicalize_formal_ref` already strips it: only **54 of
105,153** formal refs are still longer than 30 characters, **2** of them resolve, and
**0** contain sentence punctuation. Nothing to do there.

The culprit is `analyze.NAMED_REF_PATTERN`, which was

```python
NAMED_REF_PATTERN = re.compile(r"《([^》]{8,100})》")
```

The character class excludes only the **closing** bracket. So whenever a body holds an
**unclosed 《** — a dropped bracket in PDF/OCR text, or a literal nested title — the match
starts at that 《 and runs through ordinary prose until the next 》, which is the closing
bracket of a *different, later* title. The capture is then a sentence ending in a fragment
of a real title. The live 江门 case (`citations.source_id=3414348`):

```
《江门市自然资源局关于报请批准江门高新区JH03-R地段控制性详细规划修改的请示
 （江自然资〔2025〕744号）收悉。经研究，现批复如下： 一、该规划成果符合
 《中华人民共和国城乡规划法
```

That string was stored as a `target_ref` and **resolved** — by containment — onto the
8-character masthead document 《江门市自然资源局》 (`id=2103609`, `algo_doc_type='other'`),
instead of the law the sentence actually cites.

## 2. Class size, measured

Three shapes are decisive evidence of a prose capture. Union over the named tier:

| shape | edges | resolved (false edges) |
|---|---:|---:|
| unclosed 《 inside the capture | 192 | 51 |
| contains a full stop 。 | 20 | 3 |
| digit-alone-on-a-line twice (PDF table swallowed) | 52 | 2 |
| **union** | **239** | **53** |

239 edges over **196 source documents**, 211 distinct ref strings. 53 resolve (harmful),
**186 do not** (harmless).

### 2.1 Shapes that look like symptoms and are NOT

The candidate symptoms had to be measured before being used as guards, and most are
false leads — guarding on them would have cost real recall:

| candidate symptom | edges | resolved | verdict |
|---|---:|---:|---|
| embedded newline | 5,599 | 2,285 | **benign** — PDF line-wrapped titles (`国务院办公厅关于印发消防安全责任制实施办法的\n通知`) |
| contains ， | 335 | 92 | **benign** — genuine older titles (`关于降低收费门槛，促进招商引资的决定`) |
| contains ： | 133 | 4 | **benign** — `标准化工作导则 第1部分：标准的结构和编写`, `惠州市1：500…矢量地形图数据采集标准` |
| length > 60 | 1,265 | 628 | **benign** — real multi-issuer titles run to the 100-char cap; the top 20 longest named refs are all legitimate |
| leading 根据/按照/依据/符合/违反 | 238 | 102 | **benign** — 违反 and 贯彻落实 begin real titles (`违反行政事业性收费…行政处分暂行规定`) |

So: no length guard, no lead-in stripping, and only `。` from the punctuation family.

## 3. Harmless vs harmful

**Harmless (186 edges).** They cost one unresolved row each and feed
`docs/working/citation-crawl-queue.csv`, which ranks "missing documents" by inbound
demand. Pollution there is negligible — demand-ranked distinct unresolved refs:

| | junk-of-this-class |
|---|---:|
| top 100 | **0** |
| top 400 | **0** |
| top 1,000 | **0** |
| whole pile | **179 of 118,241 (0.15%)** |

A prose capture is unique by construction (it embeds a 文号, a date, a line of a table),
so its demand is 1 and it can never climb the queue. **The queue is not misdirecting
crawl effort at phantoms of this class.** Example harmless rows:
`融资性担保公司管理暂行办法（以下简称《办法`, `广东省商务厅关于审定《中韩（惠州）产业园实施方案（送审稿）`.

**Harmful (53 edges).** Each is a false edge. The pattern is consistent and worth naming:
the prose head begins with the *issuing agency's name*, and the corpus holds 8–9 character
**masthead stub documents** (`江门市自然资源局`, `广东省医疗保障局`, `深圳市住房和建设局`,
`广东省交通运输厅`, `深圳市安全教育基地`, `发展和改革委员会` — all `algo_doc_type='other'`,
all crawler artifacts), so containment lands the whole sentence on the stub. Examples:

| source | junk ref (truncated) | false target |
|---|---|---|
| 3414348 江门市人民政府…批复 | `江门市自然资源局关于…请示（江自然资〔2025〕744号）收悉。经研究…符合《中华人民共和国城乡规划` | 2103609 江门市自然资源局 |
| 4613294 / 4716086 / 4810048 广东省财政厅 | `广东省财政厅 广东省医疗保障局关于印发《广东省医疗服务…管理实施细则(2024年修订)` | 2166223 广东省医疗保障局 |
| 8342150 深圳市生态环境局龙华管理局 | `深圳市住房和建设局关于印发《深圳市建设工程扬尘污染防治专项方案` | 1351991 深圳市住房和建设局 |
| 11548969 深圳市交通运输局 | `广东省交通运输厅 广东省财政厅转发〈交通运输部 财政部关于印发《新能源城市公交车…实施细则` | 101632 广东省交通运输厅 |

## 4. What changed

### 4.1 The pattern is balanced instead of truncating (`analyze.py`)

```python
NAMED_REF_PATTERN = re.compile(r"《((?:[^《》]|《[^《》]{1,120}》){8,120})》")
```

One level of nesting is allowed, an unbalanced bracket is not. That fixes both halves of
the defect at once:

* a title that legitimately **quotes** another title (`《市人民政府关于修改《武汉市违法用地上
  建筑物处置办法》施行时间的通知》`) is now captured WHOLE; the old pattern truncated it at
  the inner 》 and resolved the fragment;
* an **unclosed** 《 can no longer start a match, because the alternation cannot produce an
  unbalanced bracket — the engine backtracks out of the stray 《 and matches the inner
  title, i.e. what the text actually cites. The 江门 sentence now yields exactly
  `中华人民共和国城乡规划法`.

The two alternation branches are disjoint on their first character, so there is nothing
ambiguous to backtrack over and matching stays linear (measured: extraction + resolution
over the sample is *faster* than before, 1.5s vs 1.7s).

### 4.2 A prose guard, `looks_like_body_run` (`analyze.py`)

Rejects a capture containing `。` (never inside an instrument title) or a
digit-alone-on-a-line-twice table signature. Deliberately **not** `，；：`, newlines or
length — §2.1 measured those in genuine titles.

### 4.3 Head recovery, `recover_named_heads` (`analyze.py`)

The balanced pattern refuses to start at a stray 《, which loses the reference when a body
*genuinely* drops a 》 (doc 2660515: `《关于印发广东省实施技术标准战略“十一五”规划的通知
（粤府办〔2007〕16号）精神，制定本实施纲要。 一、… 1989年，《中华人民共和国标准化法》` — the
law matches, the 通知 does not). So the greedy pattern is kept for exactly one purpose:
take the head of such a run, cut it back to its **last genre word** (reusing
`POLICY_KEYWORDS`, the module's existing notion of title shape) and keep it only if what
remains still passes the prose guard. The same two gates reject the masthead-only heads
that produced the false edges above (`广东省财政厅 广东省医疗保障局关于印发` → no genre word →
dropped), so recovery adds titles back without adding prose back.

### 4.4 Nested instruments are emitted explicitly (`extract_citations.py`)

A capture that quotes another instrument cites **both** documents. The old truncating
pattern reached the quoted one only by accident; now that the wrapper is captured whole,
the quoted title has to be emitted as its own reference or those edges disappear. Any
quoted title that is the citing document's **own instrument core** (`印发《X》的通知` does
not cite X) is excluded via the existing `_title_cores_of_title`. Nested titles therefore
carry a *precise* self-reference test and are exempt from the loose
`name in title or title in name` test, which they routinely trip:
`黑龙江省人民政府关于废止《黑龙江省实施〈中华人民共和国车船使用税暂行条例〉办法》的决定` contains
the national regulation in its own title and still cites it.

Candidate construction moved out of `extract_all`'s loop into
`named_ref_candidates(body, title)` so it is testable.

## 5. Recall measurement

Read-only, in memory, no DB writes. Sample = **all 196 documents carrying a junk-shaped
named edge + 4,000 random documents with a body** (4,191 total), resolved through a
`TitleMatcher` built over all 323,639 title rows of the live corpus. "Resolved pair" =
distinct (source, target).

| | named edges | resolved | distinct resolved pairs |
|---|---:|---:|---:|
| before (git HEAD) | 8,343 | 3,332 | 3,061 |
| after (patched) | 8,381 | 3,418 | **3,105** |

**LOST = 7, GAINED = 51.** Every one of the 7 is accounted for:

* **6 are the false edges this change exists to remove** — the masthead stubs of §3
  (2103609, 2166223 ×3, 1351991, 101632). Where the correct target is held it was gained
  in the same pass: the three 广东省财政厅 documents now resolve to **4485330**, the actual
  `广东省财政厅 广东省医疗保障局关于印发《…管理实施细则（2024年修订）》`.
* **1 is a self-reference** by the module's own pre-existing rule: 10386642 is
  `深圳市住房和建设局 深圳市司法局关于公开征求《深圳市保障性住房规划建设管理办法（征求意见稿）》…`
  and the recovered head is `深圳市保障性住房规划建设管理办法`, which appears in its own title.
  The old code escaped `name in title` only because the capture was junk.

**Recall loss on real refs to a distinct instrument: 0.** Earlier iterations that did not
carry §4.3 and §4.4 lost 18 and then 10 pairs respectively; they were loosened until the
only remaining losses were the intended ones.

## 6. Residual, not fixed here

The 8–9 character **masthead stub documents** (`江门市自然资源局`, `广东省医疗保障局`, …) are
still eligible containment targets: they carry `algo_doc_type='other'`, so
`TitleMatcher._containment_ok`'s promulgation gate treats them as "no information" and
lets them through. This class of edge is now unreachable *from prose captures*, but any
ref that embeds an agency name can still land on one. Candidate follow-ups: exclude
`_MASTHEAD_PRE`-shaped titles from the containment tier, or stop ingesting these stubs.

**A citations rebuild is required to realise any of this** — the fix changes extraction,
not the stored table. The nightly Phase 2b rebuild will apply it; expect ~53 false edges
removed, ~0.1% more named edges, and a modest rise in resolved edges (the 51:3,061 sample
ratio projects to roughly +4–5k corpus-wide, which should be verified against the
`validate_cascades.py` bands rather than assumed).
