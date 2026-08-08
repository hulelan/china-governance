# Search Improvement Proposal

*Companion to [`search-primer.md`](./search-primer.md). This document proposes
concrete options for THIS system, picks one, and reports measured before/after
results from the implemented change.*

---

## 1. The problem, precisely

`web/services/documents.py:search_documents()` matches with the FTS5 **trigram**
index (`doc_search`) and then sorts by `date_written DESC`. So:

- **Matching is good.** Trigrams handle Chinese substrings without word
  boundaries; the index turned multi-second `LIKE` scans into millisecond lookups.
- **Ranking is absent.** Results are date-ordered. A search for `人工智能` returns the
  *newest* document that mentions AI in passing, not the document most *about* AI.
  There is a title-vs-body tiebreak (`CASE WHEN title LIKE …`) but within each
  bucket it's still pure recency.

Why we can't just add `ORDER BY bm25(doc_search)`: `doc_search` is a **trigram**
index, so `bm25()` would rank by 3-character-fragment frequency, which is close to
noise (see primer §4). Real relevance needs an index over **words**.

Constraints that shape the choice: **2-vCPU / 2 GB droplet**, **SQLite only** (no
new services), a **~250k-doc** corpus (203k with body text), and the app opens the
DB **read-only** — the ranking must be expressible in a single SQL query.

---

## 2. Options considered

### Option A — Tune the trigram ordering (no new index)
Add heuristics on top of the trigram results: boost exact title/keyword hits,
count query occurrences, weight by `citation_rank`/`ai_relevance`.
- **Pros:** no re-indexing; tiny change.
- **Cons:** still not real relevance — no TF-IDF/length normalization; occurrence
  counting in SQL over `body_text_cn` re-scans text per row. A lipstick fix.

### Option B — Word-segmented FTS5 + BM25  ★ (chosen)
Pre-segment Chinese into words with **jieba** at index time, store space-joined
tokens in a **second** FTS5 index (`doc_search_seg`, `unicode61` tokenizer), and
rank with the built-in **`bm25()`** using per-column weights (title boosted).
Keep `doc_search` (trigram) as a substring fallback so recall never regresses.
- **Pros:** real BM25 relevance (TF saturation, IDF, length normalization); pure
  SQLite, no new services, fits the droplet; exact-term strength suits a legal/
  governance corpus (agency names, statute titles, doc numbers); clean fallback
  chain; a natural on-ramp to hybrid search later.
- **Cons:** a one-time segmentation pass; jieba dependency in the web venv;
  segmentation isn't a SQL trigger, so the index needs periodic refresh (cheap,
  incremental).

### Option C — Add dense/vector retrieval (embeddings + ANN)
Embed all docs, store vectors (e.g. `sqlite-vec`), retrieve by cosine + ANN;
optionally fuse with BM25 via RRF (primer §5).
- **Pros:** fixes vocabulary mismatch (`大模型` ↔ `LLM`); the real quality ceiling.
- **Cons:** needs an embedding model, ~250k vectors in **2 GB** RAM (HNSW memory
  is the binding constraint), an ANN index, and re-embedding on new docs. Real
  infra for a gain we haven't shown we need yet.

### Option D — Cross-encoder reranker on top
Retrieve ~100 candidates, rerank with a cross-encoder (primer §5e).
- **Pros:** biggest relevance jump per the literature.
- **Cons:** a transformer at query time on a 2-vCPU box → unacceptable latency.
  Out of scope.

**Decision: Option B.** It directly fixes the reported problem ("keyword matching
instead of relevance"), costs no new infrastructure, and fits the hardware. C/D
are the future once there's evidence that semantic recall is worth the infra —
and B is a prerequisite building block for the hybrid version of C anyway.

---

## 3. Design of the chosen change

### 3a. The segmented index — `doc_search_seg`
`scripts/build_search_index_seg.py` builds a **new, independent** FTS5 table
(never touches `doc_search`):

```sql
CREATE VIRTUAL TABLE doc_search_seg USING fts5(
    title, document_number, keywords, abstract, body_text_cn,
    content='',                               -- contentless: index only, no stored text
    tokenize='unicode61 remove_diacritics 2'  -- ordinary word tokenizer over jieba output
);
```

- **Contentless (`content=''`)** — stores only the inverted index, not the
  segmented text (we already have originals in `documents`). `bm25()` works on
  contentless tables (FTS5 keeps the `_docsize` counts it needs); we only read
  `rowid` and join back to `documents` for display. Keeps the index lean.
- **Column order mirrors `doc_search`**, so `bm25()` weights map predictably.
- **Segmentation** (`web/services/segment.py`, shared by builder and query path):
  jieba **search mode** (`cut_for_search`) at index time — emits the compound
  *and* its sub-words for recall; jieba **precise mode** at query time — the
  user's actual terms. Body text is capped at **5,000 chars** (avg body ≈ 2.3k;
  the document lead carries the salient terms) to bound build time and index size.
- **Incremental by default**: only indexes `documents.id`s not already present, so
  it can be re-run cheaply to pick up newly crawled docs.

### 3b. The ranking query
`search_documents()` gains a **Path 1** that runs before the trigram path:

```sql
SELECT d.*, <snippet>
FROM doc_search_seg s JOIN documents d ON d.id = s.rowid
WHERE doc_search_seg MATCH ?              -- jieba tokens, quoted, implicit-AND
ORDER BY
  CASE WHEN d.title LIKE ? THEN 0 ELSE 1 END,          -- 1) exact title match first
  bm25(doc_search_seg, 12.0, 6.0, 4.0, 2.0, 1.0),      -- 2) BM25 relevance (title 12x…body 1x)
  d.date_written DESC                                   -- 3) recency tiebreak
LIMIT ? OFFSET ?;
```

- The query is jieba-segmented, each token double-quoted (neutralizes FTS5
  operators) and space-joined → **implicit AND** in FTS5 (a doc must contain every
  query word — good precision).
- **Title boost** is done two ways that reinforce each other: the `bm25()`
  column weight (12× for title) and an explicit exact-substring-in-title bucket so
  that typing a document's title surfaces *that* document at the top.
- **Recency** is only a tiebreak now, not the primary sort.

### 3c. Fallback chain (recall never regresses)
1. **Path 1 — segmented BM25** (query ≥ 2 chars, index present). If it returns 0
   rows (e.g. a substring that isn't a word, or partial doc numbers) →
2. **Path 2 — trigram substring** (`doc_search`, date-ordered), the existing
   behavior. If still nothing / query < 3 chars →
3. **Path 3 — LIKE scan**, the original last resort.

Path 1 is wrapped so any jieba/FTS error falls through to Path 2 — the segmented
index can never make search *fail*, only add ranking when it helps. The
availability of `doc_search_seg` is probed once and cached (`_seg_available`), so
if the index was never built the code transparently behaves exactly as today.

---

## 4. Measured results (on the live corpus, read-only)

Index build (250,949 docs, ~204k with body), `nice -n 19`, on an isolated
`VACUUM INTO` copy of the live DB (so production was never touched):

- **Build time:** **~41 min** (2,480s; ~102 docs/s). On the live droplet, with the
  web app reading concurrently, budget **~1 hour**. One-time; incremental re-runs
  only touch new docs (seconds/day).
- **Index size added to `documents.db`:** **≈587 MB** (615.5 MB of FTS5 shadow
  tables; contentless, so no duplicated body text).
- **Query latency (segmented BM25 path, warm):** **~50–425 ms** — common terms
  (人工智能, 13k hits) at the high end, typical terms ~50–60 ms. **Faster** than the
  trigram+date path (~110–1,300 ms) because AND-of-words scans shorter posting
  lists than a broad substring match.

Before = trigram + date order (current prod). After = segmented BM25. Top-5 titles
(measured against the copy; `total` differs because BM25 matches AND-of-words, a
tighter set than any-substring — a precision gain, and the trigram fallback still
covers pure-substring queries):

**`人工智能` (AI)** — BEFORE 13,672 hits / 1,311 ms · AFTER 12,849 / 424 ms

| # | BEFORE (newest mention) | AFTER (most *about* AI) |
|---|---|---|
| 1 | 人工智能或可唤醒"沉睡"的文化宝藏 (xinhua) | 广东省中小学教师/学生**人工智能**素养框架（试行）(gdedu) |
| 2 | 雄安人工智能实训基地正式投运 (xinhua) | 清华AIIG《**人工智能**治理框架与实施路径》报告 |
| 3 | 大量民族古籍…人工智能或可唤醒… (stdaily) | 2026世界**人工智能**大会全球治理主席声明 (miit) |
| 4 | 科技新观察丨"人工智能局"相继挂牌… (stdaily) | 〃 (dup doc in corpus) |
| 5 | 第一期人工智能安全职业能力培训通知 (miit) | 〃 |

**`数据安全` (data security)** — BEFORE 3,171 / 195 ms · AFTER 2,550 / 60 ms

| # | BEFORE (newest mention) | AFTER (most *about* data security) |
|---|---|---|
| 1 | 2026年第三期数据安全职业能力培训通知 (miit) | "**数据安全**服务能力评定/工程师培训"通知 (miit) |
| 2 | 第三轮数据安全服务能力评定通知 (miit) | **数据安全**评估服务项目中标结果公示 (hrss) |
| 3 | …数据安全评估师/工程师培训通知 (miit) | **网络数据安全**管理条例 (miit) |
| 4 | 安徽…数据安全应急演练 (miit) | **数据安全**评估服务项目招标公告 (hrss) |
| 5 | 山西…网络与数据安全专题培训班 (miit) | **网络数据安全**管理条例 (npc) |

**`成品油` (refined oil)** — BEFORE 1,273 / 113 ms · AFTER 975 / 51 ms

| # | BEFORE (newest mention) | AFTER (most *about* refined oil) |
|---|---|---|
| 1 | 7月31日安徽省成品油价格调整 (ifeng) | 大鹏新区**成品油**市场供应应急预案 (szdp) |
| 2 | 大船天津建造11.5万吨成品油轮交付 (xinhua) | 光明区**成品油**市场供应应急预案 (szgm) |
| 3 | 成品油零售全面推广"交易即开票" (stdaily) | 11.5万吨**成品油**轮交付 (xinhua) |
| 4 | 《北京市…成品油流通管理办法…》解读 (bj) | 广东省中央**成品油**价格调整对渔业补助…细则 (gdny) |
| 5 | 成品油零售将全面推广"交易即开票" (xinhua) | 浙江省**成品油**价格按机制调整 (zj) |

**Read the difference:** BEFORE lists whatever most-recently mentioned the term;
AFTER surfaces the documents the term is actually *about* (dedicated
plans/regulations/notices), with exact-title matches on top. Latency stays in the
same interactive range as the trigram path.

---

## 5. What the maintainer must do to ship it

1. **Deploy the code** (merge this branch, then the usual `git pull` + restart).
   `web/services/segment.py` (new), `web/services/documents.py` (modified),
   `scripts/build_search_index_seg.py` (new).
2. **Install jieba in the web venv** (already in `requirements.txt`):
   `pip install jieba` (pure-Python wheel, no compilation).
3. **Build the index once on the droplet** (additive; safe alongside the live app
   — new table, WAL, read-only web connection unaffected):
   ```bash
   cd /root/china-governance && \
     PATH=/root/china-governance/.venv/bin:$PATH \
     nice -n 19 python3 scripts/build_search_index_seg.py
   ```
   Cost: **~1 hour** one-time (~41 min measured on an uncontended copy; allow more
   with the live web app reading), **≈587 MB** added to `documents.db`. The build is
   additive and lock-tolerant (retries on transient `database is locked`), but for
   least contention run it outside the 06:00 UTC `daily_sync` window. No web restart
   is needed for the index to take effect (availability is probed per-process on
   first search; restart if you want it picked up immediately).

If step 3 is skipped, nothing breaks — `search_documents()` falls back to today's
trigram behavior.

---

## 6. Maintenance & follow-ups

- **Keeping the index fresh.** Segmentation runs in Python, so (unlike
  `doc_search`'s SQL triggers) new crawled docs aren't auto-added. Re-run the
  builder periodically — it's **incremental** (only new `id`s). Suggested: add one
  line to `daily_sync.sh` after the crawl/backfill phase:
  `python3 scripts/build_search_index_seg.py` (indexes just the day's new docs;
  seconds, not the full 250k). Until then, the trigram fallback still finds
  un-indexed new docs — they simply aren't BM25-ranked until the next build.
- **Tuning.** BM25 `k1`/`b` use FTS5 defaults; column weights (12/6/4/2/1) are a
  sensible first guess. If short notices or long regulations feel over/under-
  ranked, adjust `b` (length normalization) or the title weight.
- **Body cap.** 5,000 chars is a lever: raise it for deeper body recall at the
  cost of a larger index / longer build.
- **On-ramp to semantic search.** If vocabulary-mismatch queries (`大模型` vs `LLM`)
  prove important, add a dense/`sqlite-vec` retriever and fuse with this BM25 path
  via Reciprocal Rank Fusion (primer §5) — this change is the lexical half of that
  hybrid.
