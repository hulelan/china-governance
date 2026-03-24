"""Inbox service — groups documents by date for a temporal "what's new" view.

date_written values are Unix timestamps at midnight CST (UTC+8).  Each unique
value corresponds to a single calendar date, so we group directly on the
integer and convert to human-readable dates in Python.
"""
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))


def _ts_to_date(ts: int) -> str:
    """Convert a date_written timestamp to 'YYYY-MM-DD' in CST."""
    return datetime.fromtimestamp(ts, tz=CST).strftime("%Y-%m-%d")


def _group_label(date_str: str, today: str, yesterday: str) -> str:
    """Assign a human-readable group label to a date string."""
    if date_str == today:
        return "Today"
    if date_str == yesterday:
        return "Yesterday"
    return date_str


async def get_inbox_dates(db, site_key=None, admin_level=None, limit=90):
    """Document counts per date_written value, most recent first.

    Returns a list of dicts: [{date, date_ts, count, label}, ...].
    """
    where = ["d.date_written > 0"]
    params = []
    param_idx = 0

    if site_key:
        param_idx += 1
        where.append(f"d.site_key = ${param_idx}")
        params.append(site_key)
    if admin_level:
        param_idx += 1
        where.append(f"s.admin_level = ${param_idx}")
        params.append(admin_level)

    where_sql = " AND ".join(where)
    param_idx += 1
    limit_idx = param_idx

    join = "JOIN sites s ON s.site_key = d.site_key" if admin_level else ""

    rows = await db.fetch(f"""
        SELECT d.date_written, COUNT(*) as count
        FROM documents d {join}
        WHERE {where_sql}
        GROUP BY d.date_written
        ORDER BY d.date_written DESC
        LIMIT ${limit_idx}
    """, *params, limit)

    now = datetime.now(tz=CST)
    today = now.strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    results = []
    for r in rows:
        date_str = _ts_to_date(r["date_written"])
        results.append({
            "date": date_str,
            "date_ts": r["date_written"],
            "count": r["count"],
            "label": _group_label(date_str, today, yesterday),
        })
    return results


async def get_documents_for_date(db, date_ts: int, site_key=None, admin_level=None):
    """All documents for a single date_written value."""
    where = ["d.date_written = $1"]
    params = [date_ts]
    param_idx = 1

    if site_key:
        param_idx += 1
        where.append(f"d.site_key = ${param_idx}")
        params.append(site_key)
    if admin_level:
        param_idx += 1
        where.append(f"s.admin_level = ${param_idx}")
        params.append(admin_level)

    where_sql = " AND ".join(where)
    join = "JOIN sites s ON s.site_key = d.site_key" if admin_level else ""

    return await db.fetch(f"""
        SELECT d.id, d.title, d.document_number, d.publisher,
               d.date_published, d.site_key, d.classify_main_name,
               (COALESCE(d.body_text_cn, '') != '') as has_body
        FROM documents d {join}
        WHERE {where_sql}
        ORDER BY d.date_published DESC
    """, *params)
