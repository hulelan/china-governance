# A Primer on Search: From Substring Matching to Relevance Ranking

*Written for this project (a 250k-document Chinese-government corpus in SQLite),
but the concepts are general. Assumes you know what a database is and can read a
SQL query, but nothing about information retrieval. Sources are linked inline and
collected at the end.*

---

## 0. The problem in one sentence

Our search "just does keyword matching instead of relevance": it finds every
document that contains your words, then sorts them **by date**. If you search
`人工智能` (artificial intelligence), you get the *newest* document that mentions
AI anywhere in its body — not the *most-about-AI* document. This primer explains
why that happens and what "relevance" actually means, mechanically.

There are two distinct jobs a search engine does, and it's worth separating them
from the start:

1. **Matching** — *which* documents contain the query? (a set)
2. **Ranking** — in *what order* should we show them? (a sort)

Our current system does (1) well and skips (2) entirely. Everything below builds
toward doing (2) properly.

---

## 1. How matching works: the inverted index

The naive way to find documents containing "人工智能" is to scan every document and
check — `WHERE body LIKE '%人工智能%'`. That's a **full table scan**: at 250k rows it
reads the whole corpus every query (this repo measured ~6.5 seconds per search
before indexing). It doesn't scale.

The fix, used by every real search engine (Lucene/Elasticsearch, Postgres FTS,
SQLite FTS5), is the **inverted index**. Instead of a list of documents each
containing words, you pre-compute the transpose: a dictionary from each *word* to
the list of documents that contain it. That per-word list is called a **posting
list**.

```
"人工智能"  → [doc 12, doc 88, doc 5023, ...]   (a posting list)
"数据"      → [doc 3, doc 12, doc 5023, ...]
```

Now a query for `人工智能` is a dictionary lookup, not a scan — you jump straight to
the posting list. A multi-word query intersects (AND) or unions (OR) a few short
posting lists instead of touching the whole corpus. This is why the index turned
6.5-second scans into millisecond lookups. The inverted index is "one of the most
widely used techniques in information retrieval… a word-oriented mechanism that
indexes all distinct words in the collection, pointing each word to a list of
documents in which it appears" ([Spice AI on BM25/inverted
indexes](https://spice.ai/learn/bm25-full-text-search)).

**Key consequence:** the index stores *words*. So the definition of "a word" —
**tokenization** — determines what you can find and how you can rank. This is the
crux of our whole problem, so it gets its own section.

---

## 2. Tokenization, and why Chinese breaks the usual assumptions

**Tokenization** is the step that chops text into the terms you index. In English
it's deceptively easy: split on spaces and punctuation. `"data security policy"` →
`["data", "security", "policy"]`. Each token is a meaningful unit, and the index
maps each to its posting list.

Chinese has **no spaces between words**. `数据安全政策` ("data security policy") is
five characters with no delimiters. A space-splitting tokenizer sees one big
token, or — depending on the tokenizer — one token *per document* because the
whole Han run never breaks. Either way the inverted index is useless: you can't
look up `数据安全` if the only indexed token is the entire paragraph.

There are three common ways out, and this project has now used two of them:

### 2a. Trigram tokenization (what we have today)

A **trigram** tokenizer ignores the idea of "words" and indexes every sliding
window of 3 characters. `数据安全政策` becomes the tokens `数据安`, `据安全`, `安全政`,
`全政策`. A search for `数据安全` is turned into *its* trigrams (`数据安`, `据安全`,
`安全政`… actually `数据安`,`据安全`) and matched as a substring. This is exactly what
SQLite FTS5's `tokenize='trigram'` does, and it's why our search can match
arbitrary Chinese substrings without knowing word boundaries.

Trigrams are great for **matching**. The problem is **ranking** (section 4): a
trigram index counts 3-character fragments, not words, so any frequency-based
relevance score is computed over fragments and is close to meaningless. As one
practitioner puts it, SQLite FTS5 with the default word tokenizer "won't tokenize
Chinese" and people reach for bigram/trigram or a real segmenter to fix it
([dev.to](https://dev.to/foxck016077/sqlite-fts5-wont-tokenize-chinese-heres-the-7-line-bigram-fix-that-did-4fcc)).

### 2b. Word segmentation (what we're adding)

The other route is to actually **segment** Chinese into words before indexing, so
the index stores real words again — just like English. A segmenter like
[**jieba**](https://github.com/fxsjy/jieba) uses a dictionary plus a statistical
model: it builds a directed acyclic graph of all possible word splits and picks
the most probable one, with a Hidden Markov Model to guess words not in its
dictionary. `数据安全政策` → `数据 / 安全 / 政策` (or `数据安全 / 政策`). You then join the
words with spaces and feed *that* to an ordinary word tokenizer (`unicode61` in
FTS5). Now the index holds `数据`, `安全`, `政策` as tokens — and, crucially, term
frequencies over **words**, which is what relevance ranking needs.

The tradeoff: segmentation can be *wrong* at boundaries, and query and index must
segment consistently or they won't match. jieba mitigates this with a "search
mode" (`cut_for_search`) that emits both the long compound and its sub-words,
widening recall.

### 2c. Stemming/lemmatization (mostly N/A for Chinese)

In English you also normalize inflections — `running`/`ran`/`runs` → `run` — via
**stemming** or **lemmatization**, so a query for one form finds the others. This
matters far less in Chinese, which doesn't inflect words this way, so we mostly
skip it. (The analogous Chinese issue is segmentation granularity, above.)

**Takeaway:** trigram = "match any substring, but you can't rank." Segmentation =
"match words, and now you *can* rank." We keep the first and add the second.

---

## 3. What "relevance" means, intuitively

Before the formulas, the intuition. Given a query, a good ranking pushes up
documents where the query terms are **important**, and pushes down documents where
they're **incidental**. Three signals capture most of it:

1. **Term Frequency (TF):** a document that says "人工智能" 20 times is probably more
   about AI than one that says it once. More occurrences → more relevant… but with
   **diminishing returns** (the 20th mention adds little over the 5th).
2. **Inverse Document Frequency (IDF):** a term that appears in *almost every*
   document (e.g. `政策`, "policy", in a policy corpus) barely discriminates, so
   matching it should count for little. A **rare** term (`具身智能`, "embodied
   intelligence") is highly discriminating, so matching it should count for a lot.
   IDF = "how surprising is this term?" Rarer = higher weight.
3. **Document length:** a term appearing 5 times in a 100-word notice is a stronger
   signal than 5 times in a 50,000-word regulation. Long documents accumulate term
   hits just by being long, so we **normalize** for length.

Every classical ranking function is some combination of these three. The famous
ones are **TF-IDF** and **BM25**.

---

## 4. TF-IDF and BM25 (the workhorses)

### TF-IDF

**TF-IDF** scores a document for a query by summing, over each query term,
`TF × IDF`: how often the term appears here, times how rare it is in the corpus.
It's the classic baseline and is "a way to find important terms from a document
relative to the collection" ([Spice AI](https://spice.ai/learn/bm25-full-text-search)).

Its two weaknesses map exactly onto intuition points (1) and (3) above:

- Raw (or log) TF **keeps growing** with more occurrences — no saturation, so a
  keyword-stuffed document can dominate.
- It has **no built-in length normalization**.

### BM25 — the modern default

**BM25** ("Best Match 25") is the refinement that fixes both, and it is "the
default choice for document ranking" today ([Spice
AI](https://spice.ai/learn/bm25-full-text-search); [Medium/MLWorks
comparison](https://medium.com/mlworks/why-bm25-algorithm-over-tf-idf-67bc009d20de)).
Its two key improvements:

1. **Term-frequency saturation.** BM25 runs TF through a saturating curve
   controlled by a parameter `k1`: the first few occurrences matter a lot, then
   additional ones add diminishing relevance — which "better reflects how humans
   judge relevance."
2. **Tunable length normalization.** A parameter `b` controls how strongly to
   penalize long documents relative to the average document length, so a term is
   worth more in a short notice than buried in a giant regulation.

The rough shape of the formula (you do **not** need to implement this — SQLite
gives it to you) is, summed over query terms *t*:

```
score(doc, query) = Σ_t   IDF(t)  ×   f(t,doc) · (k1 + 1)
                                    ─────────────────────────────────────
                                    f(t,doc) + k1 · (1 − b + b · |doc|/avgdl)
```

where `f(t,doc)` is the term's frequency in the doc, `|doc|` its length, `avgdl`
the average length, and `IDF(t)` the rarity weight. Bigger score = more relevant.
The important thing is that all three intuitions — TF (saturating), IDF, and
length — are baked in.

**Why our trigram index can't do this well:** BM25's inputs are *word*
frequencies. Over a trigram index, `f(t,doc)` is the frequency of a 3-character
fragment and `IDF` is the rarity of a fragment. Fragments correlate loosely with
words but carry far less signal (common characters like `的`, `工`, `国` inflate or
deflate scores arbitrarily). BM25 over trigrams technically runs but ranks little
better than noise — which is why the pragmatic fix is a **word-segmented** index
that lets BM25 see real terms. This is the standard jieba-preprocess-then-BM25
recipe ([search results survey](https://dev.to/foxck016077/sqlite-fts5-wont-tokenize-chinese-heres-the-7-line-bigram-fix-that-did-4fcc)).

### BM25 in SQLite specifically

SQLite's FTS5 module ships a built-in `bm25()` auxiliary function. You order by it,
and you can pass **per-column weights** so a hit in the title counts more than a
hit in the body ([SQLite FTS5 docs](https://www.sqlite.org/fts5.html)):

```sql
SELECT * FROM email WHERE email MATCH ? ORDER BY bm25(email, 10.0, 5.0);
-- weight 10 for column 1 (e.g. title), 5 for column 2, default 1.0 for the rest
```

FTS5 multiplies BM25 by −1 so **lower = better**, and it maintains a hidden
`_docsize` table (the per-column token counts BM25 needs for length
normalization). This works even for a *contentless* index (`content=''`, which
stores the inverted index but not the original text) — perfect for us, since we
already have the originals in `documents` and only need the index for ranking.

**This is the whole basis of the change this project is making:** segment with
jieba → index words in FTS5 (`unicode61`) → `ORDER BY bm25(...)`. Real relevance,
no new infrastructure, runs inside the existing SQLite file.

---

## 5. Beyond keywords: semantic search (embeddings, ANN, hybrid)

BM25 is a **lexical** (exact-term) method: it matches the words you typed. It has
a real blind spot — **vocabulary mismatch**. If a document says `大模型` ("large
model") and you search `LLM`, or it says `生成式人工智能` and you search `AIGC`, BM25
sees no shared term and misses it. The modern toolkit adds **semantic** methods to
cover that gap. You likely don't need these yet, but you should know the map.

### 5a. Dense retrieval (embeddings)

An **embedding model** (a neural net) maps a piece of text to a vector of a few
hundred numbers such that *texts with similar meaning land near each other* in
that vector space — regardless of shared words. You embed every document once,
embed the query at search time, and retrieve the documents whose vectors are
closest (cosine similarity). This is **dense retrieval**: it "handles conceptual
and paraphrase queries" that lexical search misses ([GoPenAI on hybrid
search](https://blog.gopenai.com/hybrid-search-in-rag-dense-sparse-bm25-splade-reciprocal-rank-fusion-and-when-to-use-which-fafe4fd6156e)).

The costs: you need a model to produce embeddings (compute + memory), you must
store 250k vectors, and comparing a query against all of them is expensive unless
you use…

### 5b. Approximate Nearest Neighbor (ANN) indexes

Exhaustively comparing a query vector to all 250k document vectors ("brute-force
KNN") is doable but slow. **ANN** indexes — **HNSW** (a navigable small-world
graph) and **IVF** (inverted file: cluster vectors, search only nearby clusters) —
trade a little accuracy for large speedups, making vector search sub-linear.
They're what powers vector databases (FAISS, and SQLite extensions like
`sqlite-vec`). On a 2-vCPU / 2 GB droplet, HNSW's memory footprint for 250k
vectors is the main constraint to watch.

### 5c. Learned sparse (SPLADE) — a middle ground

**SPLADE** is a clever hybrid-in-one: a BERT-style model produces a **sparse**
vector over the whole vocabulary, effectively doing automatic **query/document
expansion** (it adds related terms — so `大模型` can light up `LLM`) while still
living in an inverted-index world. The catch is that it "requires running a
transformer at inference time, which adds ~100–300 ms latency" ([GoPenAI](https://blog.gopenai.com/hybrid-search-in-rag-dense-sparse-bm25-splade-reciprocal-rank-fusion-and-when-to-use-which-fafe4fd6156e)).
Heavier than we want right now.

### 5d. Hybrid search + fusion

You rarely choose lexical *or* semantic — the state of the art **fuses** them.
"BM25 excels at exact-match queries — product codes, named entities, rare
technical terms — but cannot handle semantic paraphrase; dense retrieval excels at
semantic similarity" ([GoPenAI](https://blog.gopenai.com/hybrid-search-in-rag-dense-sparse-bm25-splade-reciprocal-rank-fusion-and-when-to-use-which-fafe4fd6156e)).
For a legal/governance corpus full of exact terms — document numbers, agency
names, statute titles — BM25's exact-match strength is especially valuable, which
is a reason to nail it first.

To combine two ranked lists whose scores aren't on the same scale, the standard
trick is **Reciprocal Rank Fusion (RRF)**: score each document by `Σ 1/(k + rank)`
across the lists, using only *ranks*, not raw scores. It's "simple yet effective…
without requiring score calibration," and on at least one benchmark RRF (NDCG
0.707) beat both BM25 alone (0.698) and pure vector KNN (0.695) ([GoPenAI](https://blog.gopenai.com/hybrid-search-in-rag-dense-sparse-bm25-splade-reciprocal-rank-fusion-and-when-to-use-which-fafe4fd6156e); [digitalapplied reference](https://www.digitalapplied.com/blog/hybrid-search-bm25-vector-reranking-reference-2026)).

### 5e. Rerankers (cross-encoders)

The retrieval methods above are **bi-encoders**: query and document are encoded
*separately* (fast, because documents are pre-encoded). A **cross-encoder**
reranker instead reads the query and one candidate document *together* and outputs
a precise relevance score — much more accurate, but far too slow to run over the
whole corpus. So it's used as a **second stage**: retrieve ~50–100 candidates
cheaply (BM25/hybrid), then rerank just those with the cross-encoder. Practitioner
reports put the gains at MRR ~0.41 (BM25) → ~0.67 (hybrid) → ~0.80+ (with a
cross-encoder reranker) ([AppScale](https://appscale.blog/en/blog/hybrid-search-and-reranking-production-rag-bm25-dense-cross-encoder-2026)).
The cost is latency and a model to run.

---

## 6. How do you know if search got better? (evaluation)

"Relevance" needs a yardstick or you're guessing. The standard metrics compare a
ranking against human judgments of which results are relevant:

- **Precision@k / Recall@k** — of the top *k* results, how many are relevant; and
  of all relevant docs, how many did we surface.
- **MRR** (Mean Reciprocal Rank) — how high up the *first* relevant result is
  (good for "I want the one right document" queries).
- **NDCG** (Normalized Discounted Cumulative Gain) — rewards putting the most
  relevant results highest, with graded relevance and a discount for lower ranks.
  This is the one you'll see quoted in the hybrid-search benchmarks above.

For a project our size, you don't need a formal test collection to start. A dozen
representative queries with an eyeballed "are the top-5 obviously on-topic?" check
(exactly the before/after in this project's search proposal) catches the big wins.
Build a small labeled set later if you want to tune `k1`/`b` or justify adding
vectors.

---

## 7. The map, and where we are on it

| Approach | Matches on | Ranks by | Infra cost | Our use |
|---|---|---|---|---|
| `LIKE '%q%'` scan | substring | nothing (date) | none | last-resort fallback |
| FTS5 **trigram** | substring | (bm25 over fragments — weak) | index in SQLite | **current**; kept as recall net |
| FTS5 **word + BM25** | words (jieba) | **BM25** relevance | index in SQLite | **the upgrade** |
| + Dense/ANN | meaning | vector similarity | model + vector index | future |
| + Hybrid (RRF) | words *and* meaning | fused ranks | both indexes | future |
| + Cross-encoder rerank | words+meaning, jointly | model score on top-k | model at query time | future |

The single highest-leverage step for us is the third row: keep the trigram index
for matching Chinese substrings, add a **word-segmented FTS5 column and rank by
`bm25()`**. It's pure SQLite (no new services, no GPU, fits the 2-vCPU/2 GB
droplet), it directly fixes the reported problem ("keyword matching instead of
relevance"), and it leaves a clean on-ramp to hybrid/semantic search later if
vocabulary-mismatch queries prove worth the added infrastructure. The concrete
design, tradeoffs, and measured before/after are in
[`search-proposal.md`](./search-proposal.md).

---

## Sources

- [What is BM25 Full-Text Search? Ranking Explained — Spice AI](https://spice.ai/learn/bm25-full-text-search) — inverted index, TF-IDF → BM25, saturation & length normalization.
- [BM25 vs TF-IDF: Which Ranks Text Better and Why? — MLWorks/Medium](https://medium.com/mlworks/why-bm25-algorithm-over-tf-idf-67bc009d20de) — why BM25 supersedes TF-IDF.
- [SQLite FTS5 Extension — official docs](https://www.sqlite.org/fts5.html) — `bm25()`, per-column weights, contentless tables, `_docsize`, query syntax (implicit AND).
- [SQLite FTS5 won't tokenize Chinese — the bigram fix — dev.to](https://dev.to/foxck016077/sqlite-fts5-wont-tokenize-chinese-heres-the-7-line-bigram-fix-that-did-4fcc) — Chinese tokenization problem; jieba/n-gram remedies.
- [jieba — Chinese text segmentation (GitHub)](https://github.com/fxsjy/jieba) — dictionary + HMM segmenter; precise vs search modes.
- [Hybrid Search in RAG: Dense + Sparse (BM25/SPLADE), RRF — GoPenAI](https://blog.gopenai.com/hybrid-search-in-rag-dense-sparse-bm25-splade-reciprocal-rank-fusion-and-when-to-use-which-fafe4fd6156e) — dense vs sparse tradeoffs, SPLADE, RRF.
- [Hybrid Search: BM25, Vector & Reranking Reference 2026 — digitalapplied](https://www.digitalapplied.com/blog/hybrid-search-bm25-vector-reranking-reference-2026) — RRF vs BM25 vs KNN benchmark numbers.
- [Hybrid Search and Re-ranking in Production RAG 2026 — AppScale](https://appscale.blog/en/blog/hybrid-search-and-reranking-production-rag-bm25-dense-cross-encoder-2026) — cross-encoder rerankers, cascade retrieval, MRR gains.
