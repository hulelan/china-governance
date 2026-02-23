"""Document query services."""
import re
from collections import Counter, defaultdict

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
    clean = doc_number
    for meta in ("依据", "依照"):
        if clean.startswith(meta):
            clean = clean[len(meta):]
    for level, prefixes in ADMIN_LEVEL_PREFIXES.items():
        if any(clean.startswith(p) for p in prefixes):
            return level
    return "unknown"


async def get_documents(db, site_key=None, category=None, year=None,
                        has_docnum=None, page=1, per_page=50):
    where = ["1=1"]
    params = []
    param_idx = 0

    if site_key:
        param_idx += 1
        where.append(f"d.site_key = ${param_idx}")
        params.append(site_key)
    if category:
        param_idx += 1
        where.append(f"d.classify_main_name = ${param_idx}")
        params.append(category)
    if year:
        from datetime import datetime
        start = int(datetime(int(year), 1, 1).timestamp())
        end = int(datetime(int(year) + 1, 1, 1).timestamp())
        param_idx += 1
        where.append(f"d.date_written >= ${param_idx}")
        params.append(start)
        param_idx += 1
        where.append(f"d.date_written < ${param_idx}")
        params.append(end)
    if has_docnum:
        where.append("d.document_number != ''")

    where_sql = " AND ".join(where)
    offset = (page - 1) * per_page

    total = await db.fetchval(
        f"SELECT COUNT(*) FROM documents d WHERE {where_sql}", *params
    )

    param_idx += 1
    limit_idx = param_idx
    param_idx += 1
    offset_idx = param_idx

    rows = await db.fetch(
        f"""SELECT d.id, d.title, d.document_number, d.publisher,
                   d.date_written, d.date_published, d.site_key,
                   d.classify_main_name, (COALESCE(d.body_text_cn, '') != '') as has_body
            FROM documents d
            WHERE {where_sql}
            ORDER BY d.date_written DESC
            LIMIT ${limit_idx} OFFSET ${offset_idx}""",
        *params, per_page, offset
    )
    return rows, total


async def get_document(db, doc_id: int):
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
    return await db.fetch("""
        SELECT classify_main_name, COUNT(*) as count
        FROM documents
        WHERE classify_main_name != ''
        GROUP BY classify_main_name
        ORDER BY count DESC
    """)


async def get_stats(db):
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


async def search_documents(db, query: str, page: int = 1, per_page: int = 50):
    offset = (page - 1) * per_page
    search_pattern = f"%{query}%"

    rows = await db.fetch(
        """SELECT d.id, d.title, d.document_number, d.publisher,
                  d.date_written, d.site_key, d.classify_main_name,
                  CASE
                    WHEN d.title LIKE $1 THEN d.title
                    WHEN d.abstract LIKE $1 THEN d.abstract
                    ELSE SUBSTR(d.body_text_cn, 1, 200)
                  END as snippet
           FROM documents d
           WHERE d.title LIKE $1
              OR d.document_number LIKE $1
              OR d.keywords LIKE $1
              OR d.abstract LIKE $1
              OR d.body_text_cn LIKE $1
           ORDER BY
             CASE WHEN d.title LIKE $1 THEN 0
                  WHEN d.document_number LIKE $1 THEN 1
                  WHEN d.keywords LIKE $1 THEN 2
                  ELSE 3 END,
             d.date_written DESC
           LIMIT $2 OFFSET $3""",
        search_pattern, per_page, offset
    )

    results = []
    for r in rows:
        d = dict(r)
        # Add <mark> tags around the query in the snippet
        raw = d.get("snippet") or ""
        if query and raw:
            raw = raw.replace(query, f"<mark>{query}</mark>")
        d["snippet"] = _truncate_snippet(raw)
        results.append(d)

    total = await db.fetchval(
        """SELECT COUNT(*) FROM documents d
           WHERE d.title LIKE $1
              OR d.document_number LIKE $1
              OR d.keywords LIKE $1
              OR d.abstract LIKE $1
              OR d.body_text_cn LIKE $1""",
        search_pattern
    )
    return results, total or 0
