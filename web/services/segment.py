"""Chinese word segmentation for the BM25 search index.

Chinese text has no spaces between words, so a plain FTS5 `unicode61` tokenizer
treats a whole run of Han characters as ONE token and `bm25()` has nothing to
count. We fix that by segmenting text into words with **jieba** at *index* time
(builder) and at *query* time (search service), joining the words with spaces so
FTS5 sees real word tokens and `bm25()` can rank by term frequency / IDF.

This module is the single source of truth for that segmentation so the index and
the queries tokenize identically. It is imported by both
`scripts/build_search_index_seg.py` and `web/services/documents.py`.

- **Index** side uses jieba *search mode* (`cut_for_search`): it emits both the
  long compound ("人工智能") and its sub-words ("人工", "智能"), maximizing recall.
- **Query** side uses jieba *precise mode* (`lcut`): the user's intent, not
  over-expanded, so `bm25()` scores the terms the user actually typed.

jieba is imported lazily (first call loads its ~5MB dict, ~0.5s once) so importing
this module is cheap and the web app starts fast even if a request never searches.
"""
import re

_jieba = None

# Han + basic-latin-alnum: a token worth keeping in a query MATCH must contain at
# least one of these (drops pure-punctuation tokens jieba emits for 《》, spaces…).
_MEANINGFUL = re.compile(r"[一-鿿0-9A-Za-z]")
_CJK = re.compile(r"[一-鿿]")

# Max characters of body_text_cn to segment/index per doc. Avg body is ~2.3k
# chars; a few run into the millions. The lead of a government document carries
# the salient terms, and capping keeps the index small and the build bounded.
BODY_CAP = 5000


def _lazy():
    global _jieba
    if _jieba is None:
        import jieba
        jieba.setLogLevel(60)  # silence the "Building prefix dict" banner
        jieba.initialize()
        _jieba = jieba
    return _jieba


def has_cjk(s: str) -> bool:
    return bool(_CJK.search(s or ""))


def segment_index(text: str, cap: int = BODY_CAP) -> str:
    """Segment a field for INDEXING (search mode). Returns space-joined tokens."""
    if not text:
        return ""
    if cap and len(text) > cap:
        text = text[:cap]
    return " ".join(_lazy().cut_for_search(text))


def query_tokens(text: str) -> list:
    """Segment a QUERY (precise mode) → list of meaningful tokens (no punctuation)."""
    if not text:
        return []
    toks = []
    for t in _lazy().lcut(text):
        t = t.strip()
        if t and _MEANINGFUL.search(t):
            toks.append(t)
    return toks


def query_match(text: str) -> str:
    """Build an FTS5 MATCH string from a query: each token quoted, ANDed together.

    Quoting each token (a) neutralizes FTS5 operators/punctuation inside a token
    and (b) makes each an independent term. Space between quoted tokens is an
    implicit AND in FTS5, so a doc must contain every query word to match — good
    precision; the caller falls back to the trigram (substring) index on 0 hits.
    """
    parts = []
    for t in query_tokens(text):
        parts.append('"' + t.replace('"', '""') + '"')
    return " ".join(parts)
