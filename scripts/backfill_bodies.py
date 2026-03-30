"""Push body text from local SQLite to Postgres for docs that have it locally but not remotely.

The main sync (sqlite_to_postgres.py) uses ON CONFLICT DO NOTHING for speed,
which means docs that were initially synced without body text never get updated.
This script fills that gap with targeted UPDATEs.

Usage:
    DATABASE_URL="postgresql://..." python3 scripts/backfill_bodies.py
    DATABASE_URL="postgresql://..." python3 scripts/backfill_bodies.py --dry-run
"""
import argparse
import os
import sqlite3
import sys
from pathlib import Path

try:
    import psycopg2
except ImportError:
    print("Install psycopg2: pip install psycopg2-binary")
    sys.exit(1)

SQLITE_PATH = Path(__file__).parent.parent / "documents.db"


def backfill(database_url: str, dry_run: bool = False):
    sq = sqlite3.connect(str(SQLITE_PATH))
    pg = psycopg2.connect(database_url)
    cur = pg.cursor()

    # Find docs with empty body in Postgres
    cur.execute("SELECT id FROM documents WHERE body_text_cn = '' OR body_text_cn IS NULL")
    pg_missing = {r[0] for r in cur.fetchall()}

    if not pg_missing:
        print("[backfill] Postgres bodies are fully up to date")
        pg.close()
        sq.close()
        return 0

    # Check which ones have body text locally
    updated = 0
    batch = []
    for doc_id in pg_missing:
        row = sq.execute(
            'SELECT body_text_cn FROM documents WHERE id = ? AND body_text_cn != ""',
            (doc_id,),
        ).fetchone()
        if row:
            batch.append((row[0], doc_id))
        if len(batch) >= 100:
            if not dry_run:
                cur.executemany(
                    "UPDATE documents SET body_text_cn = %s WHERE id = %s", batch
                )
                pg.commit()
            updated += len(batch)
            print(f"  {updated:,} bodies pushed...", end="\r")
            batch = []

    if batch:
        if not dry_run:
            cur.executemany(
                "UPDATE documents SET body_text_cn = %s WHERE id = %s", batch
            )
            pg.commit()
        updated += len(batch)

    prefix = "[dry-run] " if dry_run else ""
    print(f"{prefix}[backfill] Pushed {updated:,} body texts to Postgres")

    # Verify
    if not dry_run:
        cur.execute(
            "SELECT COUNT(*) FROM documents WHERE body_text_cn != '' AND body_text_cn IS NOT NULL"
        )
        print(f"[backfill] Postgres body count: {cur.fetchone()[0]:,}")

    pg.close()
    sq.close()
    return updated


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill body text to Postgres")
    parser.add_argument("--dry-run", action="store_true", help="Count without updating")
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("Error: Set DATABASE_URL environment variable")
        sys.exit(1)

    backfill(database_url, dry_run=args.dry_run)
