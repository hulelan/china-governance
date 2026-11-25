"""Policy Lens services — a topic/policy dossier over the corpus.

Two modes:

* **Topic** (`get_topic_lens`): given a query string, assemble a one-page
  dossier for every document whose *title* matches it — an attention timeline
  (docs/year), a breakdown by administrative level, the top issuing sites, the
  genre mix (algo_doc_type), and the most-cited "anchor" documents on the topic.
  Everything filters on ``title LIKE '%q%'`` only — we never scan body_text_cn
  on a page request (see "Speed" below for how the matching rows are found).

* **Document** (`get_doc_lens`): given a document id, resolve its outbound
  citations (what it cites) and inbound citations (who cites it), deduped and
  with self-references removed, plus its metadata — reusing the same citation
  service the /document page uses.

Speed (2026-11-25): the topic dossier used to run SIX `title LIKE '%q%'` scans of
`documents` (~1.5s each warm, ~9s per uncached topic, and over a minute for a 2-char
term once the ~16 GB table has fallen out of the page cache: 教育 measured 64s). It
now fetches the matching rows ONCE and builds every panel in Python from that one
row set. Which single query, best first:

1. `idx_documents_lens` exists (a covering index over exactly the columns read
   here, built by scripts/build_site_stats.py): one LIKE scan of that ~60 MB index,
   ~0.5s whatever the term, warm or cold.
2. No such index, query >= 3 chars without LIKE wildcards: the trigram index's title
   column (`doc_search MATCH 'title : "q"'`) then a `title LIKE` re-check on just
   those rows, so the semantics are exactly the old ones. ~0.07s warm, but each hit
   is a random read into `documents`, so cold it costs ~1 ms per matching title.
3. Otherwise one LIKE scan of `documents` (below the trigram floor, see CLAUDE.md
   "the trigram tokenizer's 3-character minimum").

Results are cached per publish and shared across workers (services.pubcache).
"""
from collections import Counter as _Counter

from . import documents as docsvc
from . import pubcache

# Entry-point topics on the empty /lens page; scripts/warm_web_cache.py primes each
# one after the nightly publish so these clicks are always warm.
LENS_SUGGESTIONS = ["人工智能", "算力", "数据要素", "低空经济",
                    "碳中和", "住房", "医保", "养老"]

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
    """Per-year TOTAL document count (topic-independent), cached per publish.

    The corpus grows ~70x across 2013-2026, so a topic's raw docs/year mostly
    tracks that ramp. Dividing by the yearly total turns volume into a *share* —
    the honest measure of whether attention to a topic actually rose, per the
    research-agenda note. Uses date_written (unix ts), same field/clip as the
    topic timeline so numerator and denominator are comparable.
    """
    async def compute():
        rows = await db.fetch(
            """SELECT CAST(strftime('%Y', date_written, 'unixepoch') AS INTEGER) AS yr,
                      COUNT(*) AS c
               FROM documents
               WHERE date_written > 0
               GROUP BY yr HAVING yr BETWEEN 2013 AND 2035""")
        return {r["yr"]: r["c"] for r in rows}
    return await pubcache.memo("lens_totals", "v", compute)


# One row per title-matching document: everything the dossier's panels need.
_ROW_COLS = """d.id, d.date_written, d.site_key, d.algo_doc_type, d.topics_algo,
               d.citation_rank"""


_SCAN_SQL = f"SELECT {_ROW_COLS} FROM documents d WHERE d.title LIKE $1"
_FTS_SQL = f"""SELECT {_ROW_COLS} FROM doc_search s CROSS JOIN documents d
               ON d.id = s.rowid
               WHERE doc_search MATCH $1 AND d.title LIKE $2"""


_lens_index = {"has": None}


async def _lens_index_present(db) -> bool:
    """Whether idx_documents_lens exists. Checked once per process: the index only
    appears via the nightly builder, and the nightly restarts the app."""
    if _lens_index["has"] is None:
        try:
            _lens_index["has"] = bool(await db.fetchval(
                "SELECT 1 FROM sqlite_master WHERE type='index' "
                "AND name='idx_documents_lens'"))
        except Exception:
            _lens_index["has"] = False
    return _lens_index["has"]


def _like_escape_free(q: str) -> bool:
    """True when q has no LIKE wildcard, so `title LIKE '%q%'` is a plain
    substring test and the trigram index can stand in for it exactly."""
    return "%" not in q and "_" not in q


async def _matching_rows(db, q: str):
    """All documents whose title contains q, as dicts of _ROW_COLS."""
    pat = f"%{q}%"
    if await _lens_index_present(db):
        return [dict(r) for r in await db.fetch(_SCAN_SQL, pat)]
    if len(q) >= 3 and _like_escape_free(q) and await docsvc._fts_available(db):
        match = 'title : "' + q.replace('"', '""') + '"'
        try:
            # CROSS JOIN pins the FTS index as the outer loop (a plain
            # `d.id IN (subquery)` may plan as a scan of idx_documents_lens instead).
            rows = await db.fetch(_FTS_SQL, match, pat)
            return [dict(r) for r in rows]
        except Exception:
            pass   # malformed MATCH etc. -> the scan below
    rows = await db.fetch(_SCAN_SQL, pat)
    return [dict(r) for r in rows]


def _year_of(ts):
    """strftime('%Y', ts, 'unixepoch') for a positive unix timestamp."""
    import datetime as _dt
    try:
        return _dt.datetime.fromtimestamp(int(ts), _dt.timezone.utc).year
    except (OverflowError, OSError, ValueError, TypeError):
        return None


async def get_topic_lens(db, q: str):
    """Build the topic dossier for query ``q``. Returns None for an empty query."""
    q = (q or "").strip()
    if not q:
        return None
    return await pubcache.memo("lens_topic", q, lambda: _build_topic_lens(db, q))


async def _build_topic_lens(db, q: str):
    rows = await _matching_rows(db, q)
    total = len(rows)

    # Site metadata (name, level) from the cached site list, not a JOIN per panel.
    site_meta = {s["site_key"]: s for s in await docsvc.get_sites(db)}

    def lvl_of(sk):
        s = site_meta.get(sk)
        return (s["admin_level"] if s and s["admin_level"] else "unknown")

    # Attention timeline — documents per year (date_written is a unix ts).
    yc = _Counter()
    for r in rows:
        dw = r["date_written"]
        if dw and dw > 0:
            yr = _year_of(dw)
            if yr is not None and 2013 <= yr <= 2035:
                yc[yr] += 1
    totals = await _yearly_totals(db)
    timeline = []
    for yr in sorted(yc):
        c = yc[yr]
        tot = totals.get(yr, 0)
        # share expressed per 1,000 documents that year (‰) — readable for the
        # small shares typical of a single topic.
        share = (1000.0 * c / tot) if tot else 0.0
        timeline.append({"year": yr, "count": c, "total": tot, "share": share})

    # Only documents whose site is in `sites` count in the site/level panels
    # (the old queries were INNER JOINs on sites).
    joined = [r for r in rows if r["site_key"] in site_meta]

    lc = _Counter(lvl_of(r["site_key"]) for r in joined)
    levels = [{"level": k, "count": v} for k, v in lc.most_common()]

    # Issuing sites (all, ordered) — feeds both the top-issuers panel and the
    # region rollup below.
    sc = _Counter(r["site_key"] for r in joined)
    site_rows = [{"name": site_meta[k]["name"], "site_key": k, "lvl": lvl_of(k), "c": v}
                 for k, v in sc.most_common()]
    top_sites = [{"name": r["name"], "site_key": r["site_key"],
                  "level": r["lvl"], "count": r["c"]} for r in site_rows[:12]]

    # Region rollup (province-level; author facet is the top-issuers panel above).
    reg_counts = _Counter()
    for r in site_rows:
        reg_counts[_region_for(r["site_key"], r["name"], r["lvl"])] += r["c"]
    regions = [{"region": k, "count": v} for k, v in reg_counts.most_common()]

    # Topic mix (algorithmic multi-label over the 29 policy categories).
    tc = _Counter()
    for r in rows:
        for t in (r.get("topics_algo") or "").split(","):
            if t:
                tc[t] += 1
    topics = [{"topic": k, "count": v} for k, v in tc.most_common()]

    # Genre mix (algorithmic doc type).
    gc = _Counter((r["algo_doc_type"] or "(unclassified)") for r in rows)
    genres = [{"genre": k, "count": v} for k, v in gc.most_common(12)]

    # Citation neighborhood — the most-cited documents on the topic.
    # `inbound` = raw distinct citing docs (doc_inbound, precomputed) next to the
    # weighted rank — corpus-lessons B6. 0 if the builder hasn't run yet.
    cand = sorted((r for r in joined if (r["citation_rank"] or 0) > 0),
                  key=lambda r: -(r["citation_rank"] or 0))[:15]
    anchors = []
    if cand:
        join_inbound, inbound_expr = await docsvc.inbound_join(db)
        anchor_rows = await db.fetch(
            f"""SELECT d.id, d.title, d.title_en, d.document_number, d.date_published,
                      d.citation_rank, d.ai_relevance, {inbound_expr} AS inbound,
                      COALESCE(NULLIF(s.admin_level, ''), 'unknown') AS lvl, s.name AS site_name
               FROM documents d JOIN sites s ON s.site_key = d.site_key {join_inbound}
               WHERE d.id = ANY($1::int[])
               ORDER BY d.citation_rank DESC""", [r["id"] for r in cand])
        anchors = [dict(r) for r in anchor_rows]

    return {
        "q": q,
        "total": total,
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
    """Return metadata + deduped inbound/outbound citations for one document.

    Not cached: it is two indexed lookups (~3 ms measured), and caching it would
    write every viewed document's full body into the shared cache."""
    doc = await docsvc.get_document(db, doc_id)
    if not doc:
        return None
    cites, cited_by = await docsvc.get_document_citations(db, doc_id)

    data = {
        "doc": doc,
        "cites": _dedupe_cites(cites, doc_id),
        "cited_by": _dedupe_cited_by(cited_by, doc_id),
        # Raw inbound (distinct citers, self dropped) — one lookup's worth of rows we
        # already hold; shown beside citation_rank (corpus-lessons B6).
        "inbound": docsvc.count_distinct_citers(cited_by, doc_id),
    }
    return data
