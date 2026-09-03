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
_totals_cache: dict = {}

# --- Region rollup (derive a province/region from a site) --------------------
# Our sites table has no region column, but site_key prefixes and the English
# site names carry the locale. Roll municipalities/districts/departments up to
# their province so the Lens can show a "By region" facet (richer than the
# central/provincial/... admin_level alone). Prefix rules win (most reliable for
# the dept/district tiers); then name-substring; else fall back by admin_level.
_REGION_PREFIX = {
    "bjd_": "Beijing", "bjb_": "Beijing",
    "shb_": "Shanghai",
    "njd_": "Jiangsu", "js_": "Jiangsu",
    "whd_": "Hubei",
    "cqd_": "Chongqing", "cq_": "Chongqing",
    "fj_": "Fujian", "xz_": "Xizang", "nx_": "Ningxia", "ln_": "Liaoning",
    "sd_": "Shandong", "hn_": "Hunan", "jl_": "Jilin", "gd_": "Guangdong",
    "sz": "Guangdong",  # Shenzhen main + its districts/bureaus (szXX, szeb, ...)
}
_REGION_NAME = {
    "beijing": "Beijing", "shanghai": "Shanghai", "tianjin": "Tianjin",
    "chongqing": "Chongqing", "guangdong": "Guangdong", "shenzhen": "Guangdong",
    "guangzhou": "Guangdong", "zhuhai": "Guangdong", "huizhou": "Guangdong",
    "jiangmen": "Guangdong", "zhongshan": "Guangdong", "shantou": "Guangdong",
    "foshan": "Guangdong", "dongguan": "Guangdong", "heyuan": "Guangdong",
    "zhaoqing": "Guangdong", "zhanjiang": "Guangdong", "maoming": "Guangdong",
    "meizhou": "Guangdong", "qingyuan": "Guangdong", "yangjiang": "Guangdong",
    "chaozhou": "Guangdong", "jieyang": "Guangdong", "shanwei": "Guangdong",
    "yunfu": "Guangdong", "shaoguan": "Guangdong",
    "jiangsu": "Jiangsu", "suzhou": "Jiangsu", "nanjing": "Jiangsu", "wuxi": "Jiangsu",
    "zhejiang": "Zhejiang", "hangzhou": "Zhejiang", "wuhan": "Hubei", "hubei": "Hubei",
    "heilongjiang": "Heilongjiang", "liaoning": "Liaoning", "shenyang": "Liaoning",
    "dalian": "Liaoning", "jilin": "Jilin", "shandong": "Shandong", "jinan": "Shandong",
    "qingdao": "Shandong", "fujian": "Fujian", "hunan": "Hunan", "hainan": "Hainan",
    "henan": "Henan", "hebei": "Hebei", "anhui": "Anhui", "jiangxi": "Jiangxi",
    "guangxi": "Guangxi", "yunnan": "Yunnan", "guizhou": "Guizhou", "sichuan": "Sichuan",
    "shaanxi": "Shaanxi", "gansu": "Gansu", "qinghai": "Qinghai", "ningxia": "Ningxia",
    "xinjiang": "Xinjiang", "xizang": "Xizang", "tibet": "Xizang", "shanxi": "Shanxi",
    "inner mongolia": "Inner Mongolia", "nmg": "Inner Mongolia", "qingdao": "Shandong",
}
# The bare-named Shenzhen department sites (no prefix/locale in the name).
_SZ_DEPTS = {"audit", "fgw", "ga", "hrss", "jtys", "mzj", "sf", "stic",
             "swj", "szeb", "wjw", "yjgl", "zjj"}


def _region_for(site_key, name, admin_level):
    sk = (site_key or "").lower()
    for pre, reg in _REGION_PREFIX.items():
        if sk.startswith(pre):
            return reg
    if sk in _SZ_DEPTS:
        return "Guangdong"
    nm = (name or "").lower()
    for kw, reg in _REGION_NAME.items():
        if kw in nm:
            return reg
    if admin_level == "central":
        return "Central"
    if admin_level == "media":
        return "National media"
    return "Other"


async def _yearly_totals(db):
    """Per-year TOTAL document count (topic-independent), cached once for an hour.

    The corpus grows ~70x across 2013-2026, so a topic's raw docs/year mostly
    tracks that ramp. Dividing by the yearly total turns volume into a *share* —
    the honest measure of whether attention to a topic actually rose, per the
    research-agenda note. Uses date_written (unix ts), same field/clip as the
    topic timeline so numerator and denominator are comparable.
    """
    hit = _totals_cache.get("v")
    now = time.time()
    if hit and now - hit["ts"] < CACHE_TTL:
        return hit["data"]
    rows = await db.fetch(
        """SELECT CAST(strftime('%Y', date_written, 'unixepoch') AS INTEGER) AS yr,
                  COUNT(*) AS c
           FROM documents
           WHERE date_written > 0
           GROUP BY yr HAVING yr BETWEEN 2013 AND 2035""")
    data = {r["yr"]: r["c"] for r in rows}
    _totals_cache["v"] = {"data": data, "ts": now}
    return data


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
    totals = await _yearly_totals(db)
    timeline = []
    for r in tl_rows:
        yr, c = r["yr"], r["c"]
        tot = totals.get(yr, 0)
        # share expressed per 1,000 documents that year (‰) — readable for the
        # small shares typical of a single topic.
        share = (1000.0 * c / tot) if tot else 0.0
        timeline.append({"year": yr, "count": c, "total": tot, "share": share})

    # Breakdown by administrative level (join sites).
    lv_rows = await db.fetch(
        """SELECT COALESCE(NULLIF(s.admin_level, ''), 'unknown') AS lvl, COUNT(*) AS c
           FROM documents d JOIN sites s ON s.site_key = d.site_key
           WHERE d.title LIKE $1
           GROUP BY lvl
           ORDER BY c DESC""", pat)
    levels = [{"level": r["lvl"], "count": r["c"]} for r in lv_rows]

    # Issuing sites (all, ordered) — feeds both the top-issuers panel and the
    # region rollup below (one query instead of two).
    site_rows = await db.fetch(
        """SELECT s.name, s.site_key,
                  COALESCE(NULLIF(s.admin_level, ''), 'unknown') AS lvl, COUNT(*) AS c
           FROM documents d JOIN sites s ON s.site_key = d.site_key
           WHERE d.title LIKE $1
           GROUP BY d.site_key
           ORDER BY c DESC""", pat)
    top_sites = [{"name": r["name"], "site_key": r["site_key"],
                  "level": r["lvl"], "count": r["c"]} for r in site_rows[:12]]

    # Region rollup (province-level; author facet is the top-issuers panel above).
    from collections import Counter as _Counter
    reg_counts = _Counter()
    for r in site_rows:
        reg_counts[_region_for(r["site_key"], r["name"], r["lvl"])] += r["c"]
    regions = [{"region": k, "count": v} for k, v in reg_counts.most_common()]

    # Topic mix (algorithmic multi-label over the 29 policy categories). The
    # topics_algo column is populated by scripts/compute_topics.py; guard against
    # it being absent (pre-backfill) so the Lens still renders.
    topics = []
    try:
        trows = await db.fetch(
            "SELECT topics_algo FROM documents WHERE title LIKE $1 AND topics_algo != ''",
            pat)
        tc = _Counter()
        for r in trows:
            for t in r["topics_algo"].split(","):
                if t:
                    tc[t] += 1
        topics = [{"topic": k, "count": v} for k, v in tc.most_common()]
    except Exception:
        topics = []

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
        "regions": regions,
        "topics": topics,
        "top_sites": top_sites,
        "genres": genres,
        "anchors": anchors,
        "timeline_max": max((t["count"] for t in timeline), default=0),
        "share_max": max((t["share"] for t in timeline), default=0.0),
        "level_max": max((l["count"] for l in levels), default=0),
        "region_max": max((r["count"] for r in regions), default=0),
        "topic_max": max((t["count"] for t in topics), default=0),
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
