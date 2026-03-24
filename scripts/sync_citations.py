"""Sync just the citations table from local SQLite to production Postgres.

Faster than a full --drop migration when only citations have changed.
Deletes all existing citations in Postgres and re-inserts from SQLite.

Usage:
    DATABASE_URL="postgresql://..." python3 scripts/sync_citations.py
"""
import os
import sqlite3
import sys
from pathlib import Path

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("Install psycopg2: pip install psycopg2-binary")
    sys.exit(1)

SQLITE_PATH = Path(__file__).parent.parent / "documents.db"


def sync_citations(database_url: str):
    sqlite_conn = sqlite3.connect(str(SQLITE_PATH))
    pg_conn = psycopg2.connect(database_url)
    pg_cur = pg_conn.cursor()

    # Count existing
    pg_cur.execute("SELECT COUNT(*) FROM citations")
    old_count = pg_cur.fetchone()[0]
    print(f"[sync] Postgres has {old_count:,} citations (will be replaced)")

    # Delete old citations
    pg_cur.execute("DELETE FROM citations")
    pg_conn.commit()
    print("[sync] Deleted old citations")

    # Read new citations from SQLite
    rows = sqlite_conn.execute(
        "SELECT source_id, target_ref, target_id, citation_type, source_level, target_level FROM citations"
    ).fetchall()
    print(f"[sync] SQLite has {len(rows):,} citations to insert")

    if rows:
        insert_sql = (
            "INSERT INTO citations (source_id, target_ref, target_id, citation_type, source_level, target_level) "
            "VALUES %s ON CONFLICT DO NOTHING"
        )
        template = "(%s, %s, %s, %s, %s, %s)"
        batch_size = 5000
        total = 0
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            psycopg2.extras.execute_values(
                pg_cur, insert_sql, [tuple(r) for r in batch],
                template=template, page_size=batch_size
            )
            pg_conn.commit()
            total += len(batch)
            print(f"  {total:,} citations...", end="\r")
        print(f"  {total:,} citations inserted")

    # Verify
    pg_cur.execute("SELECT COUNT(*) FROM citations")
    new_count = pg_cur.fetchone()[0]
    print(f"\n[sync] Done: {old_count:,} → {new_count:,} citations")

    pg_cur.close()
    pg_conn.close()
    sqlite_conn.close()


if __name__ == "__main__":
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("Error: Set DATABASE_URL environment variable")
        sys.exit(1)
    sync_citations(database_url)
