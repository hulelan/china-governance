"""Document query services.

Provides async functions for querying the documents, sites, and categories
tables.  Used by both the HTML page routes and the JSON API.
"""
import re
from datetime import datetime, timezone, timedelta
from collections import Counter, defaultdict

CST = timezone(timedelta(hours=8))

# Chinese brackets/quotes that users commonly omit when typing search queries
_CN_PUNCT_CHARS = '\u201c\u201d\u2018\u2019\u300a\u300b\uff08\uff09\u3010\u3011\u3014\u3015'
_CN_PUNCT_RE = re.compile(f'[{re.escape(_CN_PUNCT_CHARS)}]')


def _strip_cn_punct(text: str) -> str:
    """Strip Chinese quotation marks and brackets for normalized search."""
    return _CN_PUNCT_RE.sub('', text)


def _norm(col: str) -> str:
    """Wrap a column with regexp_replace to strip Chinese punctuation.

    Returns Postgres SQL; _pg_to_sqlite converts it for SQLite.
    """
    return f"regexp_replace({col}, '[{_CN_PUNCT_CHARS}]', '', 'g')"


def date_str_to_timestamp(date_str: str) -> int:
    """Convert 'YYYY-MM-DD' to Unix timestamp at midnight CST (UTC+8).

    This matches how date_written is stored in the database — each value
    represents midnight China Standard Time for that date.
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=CST)
    return int(dt.timestamp())

# Reuse patterns from analyze.py
REF_PATTERN = re.compile(
    r"([\u4e00-\u9fff]+[\u3014\u3008\u300a\uff08\u2018\u301a]"
    r"(?:19|20)\d{2}"
    r"[\u3015\u3009\u300b\uff09\u2019\u301b]"
    r"\d+\u53f7)"
)

ADMIN_LEVEL_PREFIXES = {
    "central": [
        "国发", "国办", "国函", "中发", "中办", "发改", "国土资", "建市", "建房",
        "建科", "人社部", "国税", "财综", "财预", "财建", "环发", "银监",
        "工信部", "水资源",
    ],
    "provincial": ["粤府", "粤办", "粤财", "粤价", "粤发", "粤卫", "粤环"],
    "municipal": ["深府", "深发", "深办", "深市", "深人", "深规土", "深建", "深前海"],
    "district": ["深坪", "深福", "深南", "深龙", "深宝", "深盐", "深光", "深罗"],
}


def get_admin_level(doc_number: str) -> str:
    """Classify a document number into an administrative level based on its prefix.

    Returns one of: 'central', 'provincial', 'municipal', 'district', 'unknown'.
    """
    clean = doc_number
    for meta in ("依据", "依照"):
        if clean.startswith(meta):
            clean = clean[len(meta):]
    for level, prefixes in ADMIN_LEVEL_PREFIXES.items():
        if any(clean.startswith(p) for p in prefixes):
            return level
    return "unknown"


async def get_documents(db, site_key=None, category=None, year=None,
                        has_docnum=None, page=1, per_page=50,
                        date_start=None, date_end=None,
                        importance=None, source_type=None):
    """Paginated document listing with optional filters. Returns (rows, total).

    date_start/date_end are Unix timestamps (ints). When provided they
    take precedence over the year filter.
    source_type: 'government' excludes media, 'media' shows only media.
    """
    where = ["1=1"]
    params = []
    param_idx = 0
    # Join with sites needed when filtering by source_type
    join_sites = ""
    if source_type == "government":
        join_sites = "JOIN sites s ON s.site_key = d.site_key"
        where.append("s.admin_level != 'media'")
    elif source_type == "media":
        join_sites = "JOIN sites s ON s.site_key = d.site_key"
        where.append("s.admin_level = 'media'")

    if site_key:
        param_idx += 1
        where.append(f"d.site_key = ${param_idx}")
        params.append(site_key)
    if category:
        param_idx += 1
        where.append(f"d.classify_main_name = ${param_idx}")
        params.append(category)
    if date_start is not None:
        param_idx += 1
        where.append(f"d.date_written >= ${param_idx}")
        params.append(date_start)
        if date_end is not None:
            param_idx += 1
            where.append(f"d.date_written < ${param_idx}")
            params.append(date_end)
    elif year:
        start = date_str_to_timestamp(f"{int(year)}-01-01")
        end = date_str_to_timestamp(f"{int(year) + 1}-01-01")
        param_idx += 1
        where.append(f"d.date_written >= ${param_idx}")
        params.append(start)
        param_idx += 1
        where.append(f"d.date_written < ${param_idx}")
        params.append(end)
    if has_docnum:
        where.append("d.document_number != ''")
    if importance:
        param_idx += 1
        where.append(f"d.importance = ${param_idx}")
        params.append(importance)

    where_sql = " AND ".join(where)
    offset = (page - 1) * per_page

    total = await db.fetchval(
        f"SELECT COUNT(*) FROM documents d {join_sites} WHERE {where_sql}", *params
    )

    param_idx += 1
    limit_idx = param_idx
    param_idx += 1
    offset_idx = param_idx

    rows = await db.fetch(
        f"""SELECT d.id, d.title, d.document_number, d.publisher,
                   d.date_written, d.date_published, d.site_key,
                   d.classify_main_name, (COALESCE(d.body_text_cn, '') != '') as has_body,
                   d.title_en, d.importance, d.category, d.summary_en
            FROM documents d {join_sites}
            WHERE {where_sql}
            ORDER BY d.date_written DESC
            LIMIT ${limit_idx} OFFSET ${offset_idx}""",
        *params, per_page, offset
    )
    return rows, total


async def get_document(db, doc_id: int):
    """Fetch a single document by ID, or None if not found."""
    return await db.fetchrow(
        "SELECT * FROM documents WHERE id = $1", doc_id
    )


async def get_document_citations(db, doc_id: int):
    """Get citations made by this document and documents that cite it."""
    # Forward: what this document references
    cites_rows = await db.fetch(
        """SELECT c.target_ref, c.target_id, c.citation_type, c.target_level,
                  d.title as target_title, d.site_key as target_site_key
           FROM citations c
           LEFT JOIN documents d ON d.id = c.target_id
           WHERE c.source_id = $1
           ORDER BY c.citation_type, c.target_level""",
        doc_id
    )

    cites = []
    for row in cites_rows:
        cite = {
            "ref": row["target_ref"],
            "type": row["citation_type"],
            "level": row["target_level"],
            "resolved": None,
        }
        if row["target_id"]:
            cite["resolved"] = {
                "id": row["target_id"],
                "title": row["target_title"],
                "site_key": row["target_site_key"],
            }
        cites.append(cite)

    # Reverse: what references this document
    cited_by_rows = await db.fetch(
        """SELECT c.source_id, c.citation_type, c.source_level,
                  d.title, d.site_key, d.publisher
           FROM citations c
           JOIN documents d ON d.id = c.source_id
           WHERE c.target_id = $1
           ORDER BY c.source_level, d.date_written DESC""",
        doc_id
    )

    cited_by = []
    for row in cited_by_rows:
        cited_by.append({
            "id": row["source_id"],
            "title": row["title"],
            "site_key": row["site_key"],
            "publisher": row["publisher"],
            "type": row["citation_type"],
            "level": row["source_level"],
        })

    return cites, cited_by


async def get_sites(db):
    """All sites with aggregate doc counts, body-text coverage, and doc-number counts."""
    return await db.fetch("""
        SELECT s.site_key, s.name, s.base_url, s.admin_level, s.sid,
               COUNT(d.id) as doc_count,
               SUM(CASE WHEN d.body_text_cn != '' THEN 1 ELSE 0 END) as body_count,
               SUM(CASE WHEN d.document_number != '' THEN 1 ELSE 0 END) as docnum_count
        FROM sites s
        LEFT JOIN documents d ON d.site_key = s.site_key
        GROUP BY s.site_key, s.name, s.base_url, s.admin_level, s.sid
        ORDER BY doc_count DESC
    """)


async def get_categories(db):
    """Distinct classify_main_name values with document counts, ordered by frequency."""
    return await db.fetch("""
        SELECT classify_main_name, COUNT(*) as count
        FROM documents
        WHERE classify_main_name != ''
        GROUP BY classify_main_name
        ORDER BY count DESC
    """)


async def get_stats(db):
    """Corpus-wide statistics: total documents, body-text and doc-number coverage, and year breakdown."""
    total = await db.fetchval("SELECT COUNT(*) FROM documents")
    with_body = await db.fetchval(
        "SELECT COUNT(*) FROM documents WHERE body_text_cn != ''"
    )
    with_docnum = await db.fetchval(
        "SELECT COUNT(*) FROM documents WHERE document_number != ''"
    )
    site_count = await db.fetchval("SELECT COUNT(*) FROM sites")

    # By year
    year_rows = await db.fetch("""
        SELECT yr as year, COUNT(*) as count
        FROM (
            SELECT EXTRACT(YEAR FROM to_timestamp(date_written))::int as yr
            FROM documents
            WHERE date_written > 0
        ) sub
        WHERE yr >= 2015 AND yr <= 2030
        GROUP BY yr
        ORDER BY yr
    """)

    return {
        "total": total,
        "with_body": with_body,
        "with_docnum": with_docnum,
        "site_count": site_count,
        "by_year": [dict(r) for r in year_rows],
    }


def _truncate_snippet(snippet: str, max_len: int = 150) -> str:
    """Truncate search snippet to max_len chars, preserving HTML mark tags."""
    if not snippet or len(snippet) <= max_len:
        return snippet or ""
    cut = snippet[:max_len]
    open_tag = cut.rfind("<mark>")
    close_tag = cut.rfind("</mark>")
    if open_tag > close_tag:
        end = snippet.find("</mark>", open_tag)
        if end != -1:
            cut = snippet[:end + len("</mark>")]
    return cut + "…"


async def search_documents(db, query: str, page: int = 1, per_page: int = 50,
                           date_start: int = None, date_end: int = None):
    """LIKE-based search across title, doc number, keywords, abstract, and body. Returns (results, total)."""
    offset = (page - 1) * per_page
    clean_query = _strip_cn_punct(query)
    search_pattern = f"%{clean_query}%"

    # Normalized column expressions (strip Chinese quotes/brackets for fuzzy matching)
    nt = _norm('d.title')
    nk = _norm('d.keywords')
    na = _norm('d.abstract')
    nb = _norm('d.body_text_cn')

    date_clause = ""
    date_params = []
    next_idx = 2  # $1 is search_pattern
    if date_start is not None:
        date_clause += f" AND d.date_written >= ${next_idx}"
        date_params.append(date_start)
        next_idx += 1
    if date_end is not None:
        date_clause += f" AND d.date_written < ${next_idx}"
        date_params.append(date_end)
        next_idx += 1

    limit_idx = next_idx
    offset_idx = next_idx + 1

    rows = await db.fetch(
        f"""SELECT d.id, d.title, d.document_number, d.publisher,
                  d.date_written, d.site_key, d.classify_main_name,
                  d.title_en, d.importance, d.category,
                  CASE
                    WHEN {nt} LIKE $1 THEN d.title
                    WHEN {na} LIKE $1 THEN d.abstract
                    ELSE SUBSTR(d.body_text_cn, 1, 200)
                  END as snippet
           FROM documents d
           WHERE ({nt} LIKE $1
              OR d.document_number LIKE $1
              OR {nk} LIKE $1
              OR {na} LIKE $1
              OR {nb} LIKE $1)
              {date_clause}
           ORDER BY
             CASE WHEN {nt} LIKE $1 THEN 0
                  WHEN d.document_number LIKE $1 THEN 1
                  WHEN {nk} LIKE $1 THEN 2
                  ELSE 3 END,
             d.date_written DESC
           LIMIT ${limit_idx} OFFSET ${offset_idx}""",
        search_pattern, *date_params, per_page, offset
    )

    results = []
    for r in rows:
        d = dict(r)
        raw = d.get("snippet") or ""
        if raw:
            if query in raw:
                raw = raw.replace(query, f"<mark>{query}</mark>")
            elif clean_query in raw:
                raw = raw.replace(clean_query, f"<mark>{clean_query}</mark>")
        d["snippet"] = _truncate_snippet(raw)
        results.append(d)

    total = await db.fetchval(
        f"""SELECT COUNT(*) FROM documents d
           WHERE ({nt} LIKE $1
              OR d.document_number LIKE $1
              OR {nk} LIKE $1
              OR {na} LIKE $1
              OR {nb} LIKE $1)
              {date_clause}""",
        search_pattern, *date_params
    )
    return results, total or 0


async def get_citation_neighborhood(db, doc_id: int):
    """Return nodes + edges for the 1-hop citation graph around a document.

    Used by the mini network graph on the document detail page.
    Returns the same {nodes, edges} shape as /api/v1/network.
    """
    doc = await db.fetchrow(
        "SELECT id, title, document_number, site_key FROM documents WHERE id = $1",
        doc_id,
    )
    if not doc:
        return {"nodes": [], "edges": []}

    # Forward citations (this doc cites)
    fwd = await db.fetch(
        """SELECT c.target_ref, c.target_id, c.target_level,
                  d.title as target_title, d.site_key as target_site
           FROM citations c
           LEFT JOIN documents d ON d.id = c.target_id
           WHERE c.source_id = $1""",
        doc_id,
    )
    # Reverse citations (docs that cite this one)
    rev = await db.fetch(
        """SELECT c.source_id, c.source_level,
                  d.title as source_title, d.document_number as source_docnum,
                  d.site_key as source_site
           FROM citations c
           JOIN documents d ON d.id = c.source_id
           WHERE c.target_id = $1""",
        doc_id,
    )

    nodes_map = {}
    edges = []

    # Center node
    center_label = doc["document_number"] or f"doc-{doc_id}"
    center_level = get_admin_level(doc["document_number"]) if doc["document_number"] else "unknown"
    nodes_map[center_label] = {
        "id": center_label, "label": center_label,
        "title": doc["title"], "level": center_level,
        "citations": len(rev), "doc_id": doc["id"], "center": True,
    }

    # Forward refs
    for r in fwd:
        ref = r["target_ref"]
        if ref not in nodes_map:
            nodes_map[ref] = {
                "id": ref, "label": ref,
                "title": r["target_title"] or "",
                "level": r["target_level"] or "unknown",
                "citations": 0, "doc_id": r["target_id"], "center": False,
            }
        edges.append({"source": center_label, "target": ref})

    # Reverse refs
    for r in rev:
        label = r["source_docnum"] or f"doc-{r['source_id']}"
        if label not in nodes_map:
            nodes_map[label] = {
                "id": label, "label": label,
                "title": r["source_title"] or "",
                "level": r["source_level"] or "unknown",
                "citations": 0, "doc_id": r["source_id"], "center": False,
            }
        edges.append({"source": label, "target": center_label})

    return {"nodes": list(nodes_map.values()), "edges": edges}
