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
    if site_key:
        where.append("d.site_key = ?")
        params.append(site_key)
    if category:
        where.append("d.classify_main_name = ?")
        params.append(category)
    if year:
        where.append("d.date_written >= ? AND d.date_written < ?")
        import calendar
        from datetime import datetime
        start = int(datetime(int(year), 1, 1).timestamp())
        end = int(datetime(int(year) + 1, 1, 1).timestamp())
        params.extend([start, end])
    if has_docnum:
        where.append("d.document_number != ''")

    where_sql = " AND ".join(where)
    offset = (page - 1) * per_page

    total = (await db.execute_fetchall(
        f"SELECT COUNT(*) FROM documents d WHERE {where_sql}", params
    ))[0][0]

    rows = await db.execute_fetchall(
        f"""SELECT d.id, d.title, d.document_number, d.publisher,
                   d.date_written, d.date_published, d.site_key,
                   d.classify_main_name, d.body_text_cn != '' as has_body
            FROM documents d
            WHERE {where_sql}
            ORDER BY d.date_written DESC
            LIMIT ? OFFSET ?""",
        params + [per_page, offset]
    )
    return rows, total


async def get_document(db, doc_id: int):
    rows = await db.execute_fetchall(
        "SELECT * FROM documents WHERE id = ?", (doc_id,)
    )
    return rows[0] if rows else None


async def get_document_citations(db, doc_id: int):
    """Get citations made by this document and documents that cite it.

    Reads from the pre-computed citations table. Falls back to on-the-fly
    extraction if no citations exist (e.g. before extract_citations.py has run).
    """
    # Forward: what this document references
    cites_rows = await db.execute_fetchall(
        """SELECT c.target_ref, c.target_id, c.citation_type, c.target_level,
                  d.title as target_title, d.site_key as target_site_key
           FROM citations c
           LEFT JOIN documents d ON d.id = c.target_id
           WHERE c.source_id = ?
           ORDER BY c.citation_type, c.target_level""",
        (doc_id,)
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
    cited_by_rows = await db.execute_fetchall(
        """SELECT c.source_id, c.citation_type, c.source_level,
                  d.title, d.site_key, d.publisher
           FROM citations c
           JOIN documents d ON d.id = c.source_id
           WHERE c.target_id = ?
           ORDER BY c.source_level, d.date_written DESC""",
        (doc_id,)
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

    # Fallback: if citations table is empty, use legacy on-the-fly extraction
    if not cites and not cited_by:
        return await _get_document_citations_legacy(db, doc_id)

    return cites, cited_by


async def _get_document_citations_legacy(db, doc_id: int):
    """Legacy on-the-fly citation extraction (before extract_citations.py has run)."""
    doc = await get_document(db, doc_id)
    if not doc:
        return [], []

    cites = []
    body = doc["body_text_cn"] or ""
    refs = REF_PATTERN.findall(body)
    for ref in set(refs):
        resolved = await db.execute_fetchall(
            "SELECT id, title, site_key FROM documents WHERE document_number = ?",
            (ref,)
        )
        cites.append({
            "ref": ref,
            "type": "formal",
            "level": get_admin_level(ref),
            "resolved": dict(resolved[0]) if resolved else None,
        })

    cited_by = []
    doc_num = doc["document_number"]
    if doc_num:
        rows = await db.execute_fetchall(
            "SELECT id, title, site_key, publisher FROM documents "
            "WHERE body_text_cn LIKE ? AND id != ?",
            (f"%{doc_num}%", doc_id)
        )
        cited_by = [{"id": r["id"], "title": r["title"], "site_key": r["site_key"],
                      "publisher": r["publisher"], "type": "formal", "level": "unknown"}
                     for r in rows]

    return cites, cited_by


async def get_sites(db):
    rows = await db.execute_fetchall("""
        SELECT s.site_key, s.name, s.base_url, s.admin_level, s.sid,
               COUNT(d.id) as doc_count,
               SUM(CASE WHEN d.body_text_cn != '' THEN 1 ELSE 0 END) as body_count,
               SUM(CASE WHEN d.document_number != '' THEN 1 ELSE 0 END) as docnum_count
        FROM sites s
        LEFT JOIN documents d ON d.site_key = s.site_key
        GROUP BY s.site_key
        ORDER BY doc_count DESC
    """)
    return rows


async def get_categories(db):
    rows = await db.execute_fetchall("""
        SELECT classify_main_name, COUNT(*) as count
        FROM documents
        WHERE classify_main_name != ''
        GROUP BY classify_main_name
        ORDER BY count DESC
    """)
    return rows


async def get_stats(db):
    total = (await db.execute_fetchall("SELECT COUNT(*) FROM documents"))[0][0]
    with_body = (await db.execute_fetchall(
        "SELECT COUNT(*) FROM documents WHERE body_text_cn != ''"
    ))[0][0]
    with_docnum = (await db.execute_fetchall(
        "SELECT COUNT(*) FROM documents WHERE document_number != ''"
    ))[0][0]
    site_count = (await db.execute_fetchall("SELECT COUNT(*) FROM sites"))[0][0]

    # By year
    year_rows = await db.execute_fetchall("""
        SELECT CAST(strftime('%Y', date_written, 'unixepoch') AS INTEGER) as year,
               COUNT(*) as count
        FROM documents
        WHERE date_written > 0
        GROUP BY year
        HAVING year >= 2015 AND year <= 2030
        ORDER BY year
    """)

    return {
        "total": total,
        "with_body": with_body,
        "with_docnum": with_docnum,
        "site_count": site_count,
        "by_year": [dict(r) for r in year_rows],
    }


def _truncate_snippet(snippet: str, max_len: int = 150) -> str:
    """Truncate FTS snippet to max_len chars, preserving HTML mark tags."""
    if not snippet or len(snippet) <= max_len:
        return snippet or ""
    # Find a good break point near max_len
    cut = snippet[:max_len]
    # Don't cut inside a <mark> tag
    open_tag = cut.rfind("<mark>")
    close_tag = cut.rfind("</mark>")
    if open_tag > close_tag:
        # We're inside a <mark> tag, extend to close it
        end = snippet.find("</mark>", open_tag)
        if end != -1:
            cut = snippet[:end + len("</mark>")]
    return cut + "…"


async def search_documents(db, query: str, page: int = 1, per_page: int = 50):
    offset = (page - 1) * per_page
    # FTS5 search
    rows = await db.execute_fetchall(
        """SELECT d.id, d.title, d.document_number, d.publisher,
                  d.date_written, d.site_key, d.classify_main_name,
                  snippet(documents_fts, 1, '<mark>', '</mark>', '…', 16) as snippet
           FROM documents_fts
           JOIN documents d ON d.id = documents_fts.rowid
           WHERE documents_fts MATCH ?
           ORDER BY bm25(documents_fts)
           LIMIT ? OFFSET ?""",
        (query, per_page, offset)
    )
    # Truncate snippets and convert to dicts
    results = []
    for r in rows:
        d = dict(r)
        d["snippet"] = _truncate_snippet(d.get("snippet", ""))
        results.append(d)
    # Count
    count_rows = await db.execute_fetchall(
        "SELECT COUNT(*) FROM documents_fts WHERE documents_fts MATCH ?",
        (query,)
    )
    total = count_rows[0][0] if count_rows else 0
    return results, total
