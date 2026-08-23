"""Policy Lens services — a topic/policy dossier over the corpus.

Two modes:

* **Topic** (`get_topic_lens`): given a query string, assemble a one-page
  dossier for every document whose *title* matches it — an attention timeline
  (docs/year), a breakdown by administrative level, the top issuing sites, the
  genre mix (algo_doc_type), and the most-cited "anchor" documents on the topic.
  All queries filter on ``title LIKE '%q%'`` only — we never scan body_text_cn
  on a page request, and every query completes in well under a second on the
  live corpus (~0.8s for the timeline scan, faster for the rest).

* **Document** (`get_doc_lens`): given a document id, resolve its outbound
  citations (what it cites) and inbound citations (who cites it), deduped and
  with self-references removed, plus its metadata — reusing the same citation
  service the /document page uses.

Results are cached in-process for an hour, mirroring /dashboard and /chain.
"""
import time

from . import documents as docsvc

CACHE_TTL = 3600  # seconds
_topic_cache: dict = {}
_doc_cache: dict = {}


async def get_topic_lens(db, q: str):
    """Build the topic dossier for query ``q``. Returns None for an empty query."""
    q = (q or "").strip()
    if not q:
        return None

    now = time.time()
    hit = _topic_cache.get(q)
    if hit and now - hit["ts"] < CACHE_TTL:
        return hit["data"]

    pat = f"%{q}%"

    total = await db.fetchval(
        "SELECT COUNT(*) FROM documents WHERE title LIKE $1", pat)

    # Attention timeline — documents per year (date_written is a unix ts).
    tl_rows = await db.fetch(
        """SELECT CAST(strftime('%Y', date_written, 'unixepoch') AS INTEGER) AS yr,
                  COUNT(*) AS c
           FROM documents
           WHERE title LIKE $1 AND date_written > 0
           GROUP BY yr
           HAVING yr BETWEEN 2013 AND 2035
           ORDER BY yr""", pat)
    timeline = [{"year": r["yr"], "count": r["c"]} for r in tl_rows]

    # Breakdown by administrative level (join sites).
    lv_rows = await db.fetch(
        """SELECT COALESCE(NULLIF(s.admin_level, ''), 'unknown') AS lvl, COUNT(*) AS c
           FROM documents d JOIN sites s ON s.site_key = d.site_key
           WHERE d.title LIKE $1
           GROUP BY lvl
           ORDER BY c DESC""", pat)
    levels = [{"level": r["lvl"], "count": r["c"]} for r in lv_rows]

    # Top issuing sites.
    site_rows = await db.fetch(
        """SELECT s.name, s.site_key,
                  COALESCE(NULLIF(s.admin_level, ''), 'unknown') AS lvl, COUNT(*) AS c
           FROM documents d JOIN sites s ON s.site_key = d.site_key
           WHERE d.title LIKE $1
           GROUP BY d.site_key
           ORDER BY c DESC
           LIMIT 12""", pat)
    top_sites = [{"name": r["name"], "site_key": r["site_key"],
                  "level": r["lvl"], "count": r["c"]} for r in site_rows]

    # Genre mix (algorithmic doc type).
    genre_rows = await db.fetch(
        """SELECT COALESCE(NULLIF(algo_doc_type, ''), '(unclassified)') AS g, COUNT(*) AS c
           FROM documents
           WHERE title LIKE $1
           GROUP BY g
           ORDER BY c DESC
           LIMIT 12""", pat)
    genres = [{"genre": r["g"], "count": r["c"]} for r in genre_rows]

    # Citation neighborhood — the most-cited documents on the topic.
    anchor_rows = await db.fetch(
        """SELECT d.id, d.title, d.title_en, d.document_number, d.date_published,
                  d.citation_rank, d.ai_relevance,
                  COALESCE(NULLIF(s.admin_level, ''), 'unknown') AS lvl, s.name AS site_name
           FROM documents d JOIN sites s ON s.site_key = d.site_key
           WHERE d.title LIKE $1 AND d.citation_rank > 0
           ORDER BY d.citation_rank DESC
           LIMIT 15""", pat)
    anchors = [dict(r) for r in anchor_rows]

    data = {
        "q": q,
        "total": total or 0,
        "timeline": timeline,
        "levels": levels,
        "top_sites": top_sites,
        "genres": genres,
        "anchors": anchors,
        "timeline_max": max((t["count"] for t in timeline), default=0),
        "level_max": max((l["count"] for l in levels), default=0),
        "site_max": max((s["count"] for s in top_sites), default=0),
        "genre_max": max((g["count"] for g in genres), default=0),
    }
    _topic_cache[q] = {"data": data, "ts": now}
    return data


def _dedupe_cites(cites, self_id):
    """Collapse outbound citation rows to one per resolved target / ref, drop self."""
    seen, out = set(), []
    for c in cites:
        rid = c["resolved"]["id"] if c.get("resolved") else None
        if rid is not None and rid == self_id:
            continue
        key = ("id", rid) if rid is not None else ("ref", c["ref"])
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def _dedupe_cited_by(cited_by, self_id):
    """Collapse inbound citation rows to one per source document, drop self."""
    seen, out = set(), []
    for cb in cited_by:
        if cb["id"] == self_id or cb["id"] in seen:
            continue
        seen.add(cb["id"])
        out.append(cb)
    return out


async def get_doc_lens(db, doc_id: int):
    """Return metadata + deduped inbound/outbound citations for one document."""
    now = time.time()
    hit = _doc_cache.get(doc_id)
    if hit and now - hit["ts"] < CACHE_TTL:
        return hit["data"]

    doc = await docsvc.get_document(db, doc_id)
    if not doc:
        return None
    cites, cited_by = await docsvc.get_document_citations(db, doc_id)

    data = {
        "doc": doc,
        "cites": _dedupe_cites(cites, doc_id),
        "cited_by": _dedupe_cited_by(cited_by, doc_id),
    }
    _doc_cache[doc_id] = {"data": data, "ts": now}
    return data
