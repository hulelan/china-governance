"""Service functions for document change tracking."""


async def get_recent_changes(db, limit: int = 100):
    """Get recent document changes with document details."""
    return await db.fetch(
        """SELECT dc.id, dc.document_id, dc.site_key, dc.change_type,
                  dc.field_name, dc.old_value, dc.new_value,
                  dc.detected_at, dc.sync_run_id,
                  d.title, d.document_number,
                  s.name as site_name
           FROM document_changes dc
           LEFT JOIN documents d ON d.id = dc.document_id
           LEFT JOIN sites s ON s.site_key = dc.site_key
           ORDER BY dc.detected_at DESC
           LIMIT $1""",
        limit,
    )


async def get_sync_runs(db, limit: int = 20):
    """Get summary of recent sync runs."""
    return await db.fetch(
        """SELECT sync_run_id,
                  MIN(detected_at) as started_at,
                  COUNT(*) as total_changes,
                  SUM(CASE WHEN change_type = 'added' THEN 1 ELSE 0 END) as added,
                  SUM(CASE WHEN change_type = 'modified' THEN 1 ELSE 0 END) as modified,
                  SUM(CASE WHEN change_type = 'deleted' THEN 1 ELSE 0 END) as deleted
           FROM document_changes
           GROUP BY sync_run_id
           ORDER BY MIN(detected_at) DESC
           LIMIT $1""",
        limit,
    )


async def get_change_stats(db):
    """Get overall change statistics."""
    row = await db.fetchrow(
        """SELECT COUNT(*) as total,
                  SUM(CASE WHEN change_type = 'added' THEN 1 ELSE 0 END) as added,
                  SUM(CASE WHEN change_type = 'modified' THEN 1 ELSE 0 END) as modified,
                  SUM(CASE WHEN change_type = 'deleted' THEN 1 ELSE 0 END) as deleted,
                  COUNT(DISTINCT sync_run_id) as runs
           FROM document_changes"""
    )
    if not row or not row["total"]:
        return {"total": 0, "added": 0, "modified": 0, "deleted": 0, "runs": 0}
    return {
        "total": row["total"] or 0,
        "added": row["added"] or 0,
        "modified": row["modified"] or 0,
        "deleted": row["deleted"] or 0,
        "runs": row["runs"] or 0,
    }


async def get_changes_by_site(db):
    """Get change counts grouped by site."""
    return await db.fetch(
        """SELECT dc.site_key, s.name as site_name,
                  COUNT(*) as total,
                  SUM(CASE WHEN dc.change_type = 'added' THEN 1 ELSE 0 END) as added,
                  SUM(CASE WHEN dc.change_type = 'modified' THEN 1 ELSE 0 END) as modified,
                  SUM(CASE WHEN dc.change_type = 'deleted' THEN 1 ELSE 0 END) as deleted
           FROM document_changes dc
           LEFT JOIN sites s ON s.site_key = dc.site_key
           GROUP BY dc.site_key, s.name
           ORDER BY total DESC"""
    )
