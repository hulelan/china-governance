"""Subsidy analysis services for the web app."""


async def get_subsidy_stats(db):
    """Get aggregate subsidy statistics."""
    row = await db.fetchrow("""
        SELECT COUNT(DISTINCT si.document_id) as doc_count,
               COUNT(*) as item_count,
               COALESCE(SUM(si.amount_value), 0) as total_wan
        FROM subsidy_items si
    """)
    return {
        "documents_with_amounts": row["doc_count"],
        "total_items": row["item_count"],
        "total_amount_wan": row["total_wan"],
        "total_amount_yi": round(row["total_wan"] / 10000, 1) if row["total_wan"] else 0,
    }


async def get_subsidy_by_district(db):
    """Subsidy data grouped by district/site."""
    rows = await db.fetch("""
        SELECT s.site_key, s.name, s.admin_level,
               COUNT(DISTINCT si.document_id) as doc_count,
               COUNT(si.id) as item_count,
               COALESCE(SUM(si.amount_value), 0) as total_wan,
               COALESCE(MAX(si.amount_value), 0) as max_wan
        FROM subsidy_items si
        JOIN documents d ON d.id = si.document_id
        JOIN sites s ON s.site_key = d.site_key
        GROUP BY s.site_key, s.name, s.admin_level
        ORDER BY total_wan DESC
    """)
    return [dict(r) for r in rows]


async def get_subsidy_by_sector(db):
    """Subsidy data grouped by sector keyword."""
    rows = await db.fetch("""
        SELECT si.sector,
               COUNT(DISTINCT si.document_id) as doc_count,
               COUNT(si.id) as item_count,
               COALESCE(SUM(si.amount_value), 0) as total_wan
        FROM subsidy_items si
        WHERE si.sector IS NOT NULL
        GROUP BY si.sector
        ORDER BY doc_count DESC
    """)
    return [dict(r) for r in rows]


async def get_subsidy_timeline(db):
    """Subsidy activity by year."""
    rows = await db.fetch("""
        SELECT SUBSTR(d.date_published, 1, 4) as year,
               COUNT(DISTINCT si.document_id) as doc_count,
               COUNT(si.id) as item_count,
               COALESCE(SUM(si.amount_value), 0) as total_wan
        FROM subsidy_items si
        JOIN documents d ON d.id = si.document_id
        WHERE d.date_published IS NOT NULL AND d.date_published != ''
        GROUP BY SUBSTR(d.date_published, 1, 4)
        HAVING SUBSTR(d.date_published, 1, 4) >= '2015'
        ORDER BY SUBSTR(d.date_published, 1, 4)
    """)
    return [dict(r) for r in rows]


async def get_top_subsidy_programs(db, limit=20):
    """Largest individual subsidy amounts."""
    rows = await db.fetch(f"""
        SELECT si.amount_value, si.amount_raw, si.amount_context, si.sector,
               d.id as doc_id, d.title, d.document_number, d.site_key,
               d.date_published, s.name as site_name
        FROM subsidy_items si
        JOIN documents d ON d.id = si.document_id
        JOIN sites s ON s.site_key = d.site_key
        ORDER BY si.amount_value DESC
        LIMIT {limit}
    """)
    return [dict(r) for r in rows]


async def get_top_subsidy_documents(db, limit=20):
    """Documents with the most subsidy line items."""
    rows = await db.fetch(f"""
        SELECT d.id, d.title, d.document_number, d.site_key, d.date_published,
               s.name as site_name,
               COUNT(si.id) as item_count,
               COALESCE(SUM(si.amount_value), 0) as total_wan
        FROM subsidy_items si
        JOIN documents d ON d.id = si.document_id
        JOIN sites s ON s.site_key = d.site_key
        GROUP BY d.id, d.title, d.document_number, d.site_key, d.date_published, s.name
        ORDER BY item_count DESC
        LIMIT {limit}
    """)
    return [dict(r) for r in rows]


async def get_central_subsidy_linkage(db, limit=15):
    """Central directives most cited by subsidy documents."""
    rows = await db.fetch(f"""
        SELECT c.target_ref, c.target_level, c.citation_type,
               COUNT(DISTINCT c.source_id) as citing_docs
        FROM citations c
        WHERE c.target_level = 'central'
          AND c.source_id IN (SELECT DISTINCT document_id FROM subsidy_items)
        GROUP BY c.target_ref, c.target_level, c.citation_type
        ORDER BY citing_docs DESC
        LIMIT {limit}
    """)
    return [dict(r) for r in rows]
