# QA: the 城乡规划法 "235 lost citers" (rebuild of 2026-10-07, resolver commit 3134994)

*2026-10-07. Read-only forensics on the droplet DB (`?mode=ro`) while the nightly was
still mid-Phase-2b/2c. No writes, no rebuilds, no crawler runs, no droplet pull. No
backup download was needed (see §1.2), so this check cost nothing but a few indexed
queries.*

**Verdict up front: there is no drop. 235 of 235 is a metric mix-up. Zero citing
documents and zero citation edges were lost. The resolver change introduced no
regression on this target.**

## 0. The two numbers are different metrics

`doc_inbound` (`scripts/build_site_stats.py`) stores two columns, and the memos and the
validator use the words "inbound" and "cited" for both:

| column | definition | 12747143 yesterday | 12747143 today |
|---|---|---:|---:|
| `inbound` | `COUNT(DISTINCT source_id)`, self-cites dropped | **1,895** | **1,907** |
| `edges` | raw resolved edge rows (what `citation_rank` weights) | **2,142** | **2,158** |

The reported "2,142 → 1,907" compares yesterday's **edges** against today's **distinct
citers**. Both metrics rose. Measured:

```sql
-- today, live
SELECT COUNT(*), COUNT(DISTINCT source_id) FROM citations WHERE target_id=12747143;
-- 2158 | 1907        (self-cites: 0)
```

The 235 is an exact arithmetic identity, not a population:

```
235 = 2,142 (yesterday edges) - 1,907 (today distinct citers)
    = 247   (yesterday duplicate edges) - 12 (net new citers)
```

Duplicate edges are one document citing the law under two or more distinct `target_ref`
strings or tiers (`UNIQUE(source_id, target_ref, citation_type)` permits this). Measured
today:

| edges per citer | citers | edges |
|---:|---:|---:|
| 1 | 1,657 | 1,657 |
| 2 | 249 | 498 |
| 3 | 1 | 3 |
| **total** | **1,907** | **2,158** |

So 251 duplicate edges today, 247 yesterday. The gap the alarm measured *is* that
duplicate overhang, which has existed in every rebuild since the dual named/LLM tiers
were introduced.

### 0.1 Provenance of the "yesterday" figures (measured, not assumed)

Tonight's Phase 2c has not run (the log stops at `[13:20:56] Phase 2b: Rebuilding
doc_issuers`), so `doc_inbound` still holds last night's snapshot. Cross-check that it
is last night's and not older: `doc_inbound` has 33,433 rows; last night's
`compute_scores` printed 39,810 "documents have inbound citations". Those are different
metrics too, and they reconcile:

```sql
SELECT COUNT(DISTINCT target_id) FROM citations WHERE target_id IS NOT NULL;                       -- 40,459  = compute_scores metric
SELECT COUNT(DISTINCT target_id) FROM citations WHERE target_id IS NOT NULL AND source_id<>target_id; -- 34,034  = doc_inbound metric
```

Today the ratio is 34,034 / 40,459 = 0.8412. Applied to last night's 39,810 that
predicts 33,490 `doc_inbound` rows against the 33,433 stored, a 0.17% residual.
**[measured]** `doc_inbound` is the end-of-2026-10-06 state.

### 1.2 Why no backup was fetched

The off-droplet backups hold the previous state (`daily/documents-20261006.db.gz`,
listed at **4.50 GB** compressed, 8.29 GB raw, not the 1.9 GB remembered). It was not
needed: `doc_inbound` supplied yesterday's two scalars, and the per-document question
closes arithmetically in §2 without it. Downloading and gunzipping 12.8 GB onto a volume
with 23 GB free while the nightly held the write lock would have been real risk for no
additional fact.

## 2. Where the delta actually came from: all of it is new corpus

Net delta is **+12 citers / +16 edges**. Thirteen of the 1,907 citers carry
`crawl_timestamp` of 2026-10-07:

```sql
SELECT d.id, d.site_key, LENGTH(d.body_text_cn), substr(d.title,1,28),
       (SELECT COUNT(*) FROM citations c2 WHERE c2.source_id=d.id AND c2.target_id=12747143)
FROM documents d
WHERE d.id IN (SELECT source_id FROM citations WHERE target_id=12747143)
  AND date(d.crawl_timestamp)='2026-10-07';
```

| id | site | title (trunc) | edges | new tonight? |
|---|---|---|---:|---|
| 12685288 | mee | 中华人民共和国气象法 | 1 | yes, Phase 1b body (mee +74 bodies, 87.7% → 100%) |
| 12697184 | zhongshan | 中山市…坦洲镇新中心区控制性详细规划D- | 1 | **no** (see below) |
| 900162557 | npc_dbgz | 完善制度推动残疾人事业全面发展 | 1 | yes |
| 900163156 | nanjing | 南京历史文化名城保护条例 | 1 | yes |
| 900163690 | njd_qinhuai | 洪武路街道办事处文书送达公告 | 1 | yes |
| 900163828 | njd_jiangning | 江宁区农村村民建房规划管理实施细则 | 1 | yes |
| 900163849 | njd_jiangning | 《…实施细则》政策解读 | 2 | yes |
| 900163865 | njd_jiangning | 综合行政执法局公告 | 2 | yes |
| 900163866 | njd_jiangning | 综合行政执法局公告 | 2 | yes |
| 900163870 | njd_jiangning | 综合行政执法局公告 | 1 | yes |
| 900163943 | szd_gusu | 《姑苏区国有土地上房屋征收补偿…》政策解读 | 2 | yes |
| 900163946 | szd_gusu | 《…机动车停车场管理实施细则》政策解读 | 1 | yes |
| 900164184 | szd_changshu | 《常熟市莫城街道东青村村庄规划…》 | 1 | yes |
| | | **total** | **17** | |

Eleven are above the pre-tonight id watermark, so they did not exist yesterday:

```sql
SELECT MAX(id) FROM documents WHERE id>900000000 AND date(crawl_timestamp)<'2026-10-07';  -- 900161948
SELECT COUNT(DISTINCT source_id) FROM citations
 WHERE target_id=12747143 AND source_id > 900161948;                                       -- 11
```

`12697184` is **not** new: `document_changes` records `change_type='added'` for it on
*every* day back through 2026-09-26, a known gkmlpt re-add artifact. It cited the law
yesterday. Its single edge is therefore not part of the delta.

That leaves 12 new citers carrying 16 edges (17 minus zhongshan's 1), against a net of
+12 citers and +16 edges. **The accounting closes to the exact edge, which forces
losses = 0:**

```
1,895 + 12 new - 0 lost = 1,907 distinct citers   ✓
2,142 + 16 new - 0 lost = 2,158 edges             ✓
```

Arithmetic proof that `12685288` must also be a genuine gain: if only the 11
above-watermark docs were new, the net would need losses of -1, which is impossible.
**[measured, by elimination]** It gained its body in Phase 1b and became a citer tonight.

There is no set of "source documents that cited 12747143 yesterday and do not now". It
is empty.

## 3. The three candidate mechanisms, measured

### 3.1 Short-title theft (the suspected regression): 0

The `LENGTH(title) >= 5` floor can only steal a ref if a 5-7 character title is a new
exact candidate for it. There are none in this family:

```sql
SELECT id, site_key, title, LENGTH(title),
       (SELECT COUNT(*) FROM citations c WHERE c.target_id=documents.id)
FROM documents
WHERE title IN ('城乡规划法','中华人民共和国城乡规划法','《城乡规划法》')
   OR (LENGTH(title) BETWEEN 5 AND 7 AND title LIKE '%规划法%');
```

| id | site | title | len | edges |
|---|---|---|---:|---:|
| 12685270 | mee | 中华人民共和国城乡规划法 | 12 | 0 |
| 12742122 | npc | 中华人民共和国城乡规划法 | 12 | 0 |
| 12747143 | npc | 中华人民共和国城乡规划法 | 12 | **2,158** |

No document is titled `城乡规划法` (5 chars) or anything else 5-7 chars matching
`规划法`. The floor change admitted no competitor here. This confirms, independently,
the point already established about the 9-character lookalikes.

The decisive test is forward-looking and needs no previous state: take **every** ref
string in the corpus that mentions 城乡规划法 and see where it lands.

```sql
SELECT c.target_ref, c.citation_type, COUNT(*), COUNT(DISTINCT c.source_id),
       c.target_id, substr(coalesce(t.title,'(unresolved)'),1,34)
FROM citations c LEFT JOIN documents t ON t.id=c.target_id
WHERE c.target_ref LIKE '%城乡规划法%'
GROUP BY c.target_ref, c.citation_type, c.target_id ORDER BY COUNT(*) DESC;
```

| target_ref | type | edges | resolves to | correct? |
|---|---|---:|---|---|
| 中华人民共和国城乡规划法 | named | 1,856 | 12747143 the law | yes |
| 《中华人民共和国城乡规划法》 | llm | 246 | 12747143 | yes |
| 城乡规划法 | llm | 33 | 12747143 | yes |
| 中华人民共和国城乡规划法 | llm | 15 | 12747143 | yes |
| 山西省实施\<…城乡规划法\>办法 | named | 2 | unresolved | yes, Shanxi's measure is not held |
| 湖南省实施〈…城乡规划法〉办法 | named | 1 | 12746748 湖南省实施《…》办法 | yes |
| 《中华人民共和国城乡规划法》第四十条(第一款) | llm | 2 | 12747143 | yes |
| 城乡规划法（修订） / 《城乡规划法》 / whitespace-split variants | both | 4 | 12747143 | yes |
| 广东省实施《中华人民共和国城乡规划法》办法 | llm | 1 | 12747143 | tolerable, GD's measure is not held |
| 江门市…请示…符合《中华人民共和国城乡规划法 | named | 1 | 2770991 江门市自然资源局 | no, pre-existing body-fragment extraction artifact |
| 中华人民共和国城乡规划法（2019年修正 / 2019年） etc. | llm | 4 | unresolved | edition suffixes, pre-existing |

Sum of rows landing on 12747143 = 2,158, matching the total exactly. **Not one ref that
means the national law resolves anywhere else.** The 33 bare `城乡规划法` LLM refs, the
single most theft-exposed group under the 5-char floor, all still reach the law. The two
off-target rows are a correct provincial-measure match and a pre-existing artifact, both
unchanged tonight.

### 3.2 Entity-unescaped ref diverting to a provincial measure: 0

`山西省实施<…城乡规划法>办法` is now unescaped to `《》` and still resolves to nothing,
which is right: Shanxi's measure is not in the corpus and the commit's claim that it
does not fall onto Guangdong's holds. **[measured]** The entity fix moved no
城乡规划法 edge in either direction. Its wins (土地管理法 267, 消防法 102, 招标投标法 60)
are elsewhere, as already established.

### 3.3 Phase 1b body churn dropping a ref: 0 lost, +1 gained

Phase 1b extracted 1,425 bodies. Its net effect on this target is one *gain*
(`12685288`, mee). No citer lost a ref to a body rewrite.

### Split

| mechanism | citers | edges |
|---|---:|---:|
| short-title exact match stealing a national-law ref (**regression**) | **0** | **0** |
| entity-unescaped ref reaching a provincial measure instead (**improvement**) | **0** | **0** |
| ref no longer extracted because the body changed in Phase 1b (**corpus**) | **0** | **0** |
| new documents + Phase 1b new body, newly citing (**corpus, gain**) | **+12** | **+16** |
| metric mix-up, edges vs distinct citers (**artifact, not a population**) | 235 of 235 | |

**No part of the 235 is a regression.** Nothing attributable to commit 3134994 touched
this target at all.

## 4. The band

`validate_cascades.py:179` measures

```sql
SELECT COUNT(*) FROM citations WHERE target_id=12747143;
```

That is the **edge** metric, so the check reads **2,158** tonight, not 1,907. The band
is `[1900, 2400]`, documented as "±~12% around 2,141". 2,158 is +0.8% off that centre
and comfortably inside. The "only just clears the floor" reading came from feeding the
distinct-citer number into a band defined on edges.

**Recommendation: do not move the band.** It is correctly calibrated, it was never
approached, and re-basing it on a number produced by a metric mix-up would widen the
blind spot the check exists to cover. (Re-basing would also have been wrong in the
specific sense the check guards against: lowering a floor because a reading looked low
is exactly how a future real theft would be waved through.)

Three labelling and robustness fixes are warranted instead. All are recommendations, not
applied here.

1. **[labelling, the actual cause of this alarm]** The check is named `cxgh_inbound` and
   prints `"{n} inbound citations"` while measuring edge rows, and `doc_inbound` calls
   its distinct-citer column `inbound`. Rename the message to say edge rows including
   duplicate ref strings, or better, assert both metrics with separate bands
   (`edges` 2,142-ish and `inbound` 1,895-ish). Two bands also make the duplicate
   overhang itself a monitored quantity, which would have made this a non-event.

2. **[real fragility, higher priority than the band]** Which of the three identical-title
   mirrors receives all 2,158 edges is **not** decided by the documented
   `(genre_rank, level_rank, id)` tie-break. All three mirrors are `algo_doc_type='law'`
   / `genre='promulgation'`, and the two `npc` copies share a level, so the documented
   rule would pick the lowest id, 12742122. It does not, because the losing mirrors never
   reach `TitleMatcher`: `extract_citations.py:560-562` builds `title_to_doc[row[1]] = …`
   from an **unordered** `SELECT … FROM documents WHERE LENGTH(title) >= 5`, so the last
   row scanned silently overwrites its predecessors. Today that is rowid order and
   12747143 (highest id) wins. If a higher-id mirror of this title were ever ingested,
   the winner would flip, `validate_cascades.py`'s hard-coded `CXGH_ID=12747143` would
   read ~0, and the check would FAIL loudly on a graph that is in fact fine. Fix: add a
   deterministic `ORDER BY` to that query, or collapse mirrors through the documented
   `_rank` instead of dict overwrite. Note the 5-char floor **widened** this very query,
   so it is now scanning more title rows into the same overwrite.

3. **[coverage]** Phase 2d did not run in the 2026-10-06 nightly (`grep -c "Phase 2d"
   logs/daily-20261006-0600.log` → 0) even though `daily_sync.sh:350` defines it; the
   validator landed in the same day's commits and the 06:00 pull predated it. There is
   therefore no recorded validator reading for yesterday to compare against, which is
   part of why this needed reconstructing from `doc_inbound`. Confirm 2d fires tonight.

Two observations logged in passing, neither tonight's doing: `doc_identity` leaves
12685270 and 12742122 as `instrument_role='unique'` despite identical titles and an
identical 2019-04-23 date, so mirror pooling is missing them (the 2015 copy is correctly
a separate edition); and the 江门市 body-fragment ref at §3.1 shows `REF_PATTERN` can
still capture a run of body text as a ref name.
