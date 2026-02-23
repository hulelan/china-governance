"""Policy chain service — builds cross-level citation hierarchies from the citations table."""

from collections import Counter, defaultdict


TOPIC_KEYWORDS = {
    "ai": "人工智能",
    "digital": "数字经济",
    "carbon": "碳达峰",
    "housing": "住房",
    "education": "教育",
    "health": "卫生",
}


async def get_chain(db, keyword: str):
    """Build a policy chain from the citations table for a given topic keyword.

    Returns a dict with hierarchy, source docs, and stats — same shape as
    the old ai_chain.json so the template works with minimal changes.
    """
    # Source documents: docs matching the topic that have body text
    source_rows = await db.execute_fetchall(
        """SELECT d.id, d.title, d.document_number, d.site_key,
                  d.date_published, d.publisher, s.admin_level
           FROM documents d
           JOIN sites s ON s.site_key = d.site_key
           WHERE (d.title LIKE ? OR d.keywords LIKE ? OR d.abstract LIKE ?)
             AND d.body_text_cn IS NOT NULL AND LENGTH(d.body_text_cn) > 20
           ORDER BY d.date_published DESC""",
        (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%")
    )

    source_ids = [r["id"] for r in source_rows]
    if not source_ids:
        return _empty_chain(keyword)

    # Normalize admin levels
    level_map = {"department": "municipal"}

    # Build source documents by level
    source_docs_by_level = defaultdict(list)
    for r in source_rows:
        level = level_map.get(r["admin_level"], r["admin_level"]) or "unknown"
        source_docs_by_level[level].append({
            "id": r["id"],
            "title": r["title"],
            "document_number": r["document_number"],
            "site_key": r["site_key"],
            "date_published": r["date_published"],
            "publisher": r["publisher"],
            "admin_level": level,
        })

    # Get citations FROM these source documents
    placeholders = ",".join("?" * len(source_ids))
    citation_rows = await db.execute_fetchall(
        f"""SELECT c.target_ref, c.target_id, c.citation_type, c.target_level,
                   c.source_id,
                   d.title as target_title, d.site_key as target_site_key,
                   d.document_number as target_docnum, d.date_published as target_date
            FROM citations c
            LEFT JOIN documents d ON d.id = c.target_id
            WHERE c.source_id IN ({placeholders})""",
        source_ids
    )

    # Group referenced policies by target_ref, counting citations
    ref_counts = Counter()
    ref_info = {}
    for r in citation_rows:
        ref = r["target_ref"]
        ref_counts[ref] += 1
        if ref not in ref_info:
            ref_info[ref] = {
                "name": ref,
                "level": r["target_level"],
                "type": r["citation_type"],
                "in_corpus": r["target_id"] is not None,
                "corpus_match": None,
            }
            if r["target_id"]:
                ref_info[ref]["corpus_match"] = {
                    "id": r["target_id"],
                    "title": r["target_title"],
                    "document_number": r["target_docnum"],
                    "site_key": r["target_site_key"],
                    "date_published": r["target_date"],
                }

    # Build hierarchy
    referenced_policies = []
    for ref, count in ref_counts.most_common():
        info = ref_info[ref]
        info["citation_count"] = count
        referenced_policies.append(info)

    hierarchy = {}
    for level in ["central", "provincial", "municipal", "district", "unknown"]:
        hierarchy[level] = [p for p in referenced_policies if p["level"] == level]

    # Stats
    formal_count = sum(1 for r in citation_rows if r["citation_type"] == "formal")
    named_count = sum(1 for r in citation_rows if r["citation_type"] == "named")

    return {
        "topic": keyword,
        "stats": {
            "source_documents": len(source_ids),
            "formal_citations": formal_count,
            "named_citations": named_count,
            "unique_referenced_policies": len(referenced_policies),
        },
        "hierarchy": hierarchy,
        "source_documents_by_level": dict(source_docs_by_level),
    }


def _empty_chain(keyword: str):
    return {
        "topic": keyword,
        "stats": {
            "source_documents": 0,
            "formal_citations": 0,
            "named_citations": 0,
            "unique_referenced_policies": 0,
        },
        "hierarchy": {
            "central": [], "provincial": [], "municipal": [],
            "district": [], "unknown": [],
        },
        "source_documents_by_level": {},
    }


async def get_citation_stats(db):
    """Get aggregate citation flow statistics for the dashboard."""
    rows = await db.execute_fetchall(
        """SELECT source_level, target_level, COUNT(*) as cnt
           FROM citations
           GROUP BY source_level, target_level
           ORDER BY cnt DESC"""
    )
    return [dict(r) for r in rows]
