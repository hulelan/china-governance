"""Push classification data to production Postgres without a full rebuild.

Adds new columns if missing, batch-updates classification fields for existing
docs, and inserts any new docs not yet in Postgres.

Usage:
    DATABASE_URL="postgresql://..." python3 scripts/sync_classifications.py
    DATABASE_URL="postgresql://..." python3 scripts/sync_classifications.py --dry-run
"""
import argparse
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

NEW_COLUMNS = [
    ("summary_en", "TEXT DEFAULT ''"),
    ("category", "TEXT DEFAULT ''"),
    ("importance", "TEXT DEFAULT ''"),
    ("policy_area", "TEXT DEFAULT ''"),
    ("topics", "TEXT DEFAULT ''"),
    ("classification_model", "TEXT DEFAULT ''"),
    ("classified_at", "TEXT DEFAULT ''"),
]

CLASSIFICATION_FIELDS = [
    "title_en", "summary_en", "category", "importance",
    "policy_area", "topics", "classification_model", "classified_at",
]


def sync(database_url: str, dry_run: bool = False):
    sqlite_conn = sqlite3.connect(str(SQLITE_PATH))
    sqlite_conn.row_factory = sqlite3.Row
    pg_conn = psycopg2.connect(database_url)
    pg_cur = pg_conn.cursor()

    # --- Step 1: Add new columns if missing ---
    print("[sync] Step 1: Checking Postgres schema...")
    pg_cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'documents'
    """)
    existing_cols = {row[0] for row in pg_cur.fetchall()}

    for col_name, col_type in NEW_COLUMNS:
        if col_name not in existing_cols:
            print(f"  Adding column: {col_name} {col_type}")
            if not dry_run:
                pg_cur.execute(f"ALTER TABLE documents ADD COLUMN {col_name} {col_type}")
    if not dry_run:
        pg_conn.commit()

    # Add indexes
    if not dry_run:
        pg_cur.execute("CREATE INDEX IF NOT EXISTS idx_documents_importance ON documents(importance)")
        pg_cur.execute("CREATE INDEX IF NOT EXISTS idx_documents_category_class ON documents(category)")
        pg_conn.commit()
    print("  Schema OK")

    # --- Step 2: Batch update classification fields ---
    print("[sync] Step 2: Updating classification fields...")
    classified = sqlite_conn.execute(f"""
        SELECT id, {', '.join(CLASSIFICATION_FIELDS)}
        FROM documents WHERE classified_at IS NOT NULL AND classified_at != ''
    """).fetchall()
    print(f"  {len(classified):,} classified docs in SQLite")

    if not dry_run and classified:
        set_clause = ", ".join(f"{f} = data.{f}" for f in CLASSIFICATION_FIELDS)
        values_cols = ", ".join(["id"] + CLASSIFICATION_FIELDS)

        # Batch update using temp table approach for speed
        pg_cur.execute("""
            CREATE TEMP TABLE _class_update (
                id INTEGER PRIMARY KEY,
                title_en TEXT, summary_en TEXT, category TEXT,
                importance TEXT, policy_area TEXT, topics TEXT,
                classification_model TEXT, classified_at TEXT
            )
        """)

        # Insert into temp table in batches
        insert_sql = f"INSERT INTO _class_update ({values_cols}) VALUES %s"
        template = "(" + ", ".join(["%s"] * (len(CLASSIFICATION_FIELDS) + 1)) + ")"
        batch_size = 1000
        for i in range(0, len(classified), batch_size):
            batch = classified[i:i + batch_size]
            psycopg2.extras.execute_values(
                pg_cur, insert_sql, [tuple(r) for r in batch],
                template=template, page_size=batch_size
            )
            print(f"  Staged {min(i + batch_size, len(classified)):,}/{len(classified):,}...", end="\r")

        # Bulk update from temp table
        print(f"\n  Applying updates...")
        pg_cur.execute(f"""
            UPDATE documents SET {set_clause}
            FROM _class_update data
            WHERE documents.id = data.id
        """)
        updated = pg_cur.rowcount
        pg_cur.execute("DROP TABLE _class_update")
        pg_conn.commit()
        print(f"  Updated {updated:,} rows")

    # --- Step 3: Sync sites/categories (before docs, so new site_keys exist) ---
    print("[sync] Step 3: Syncing sites & categories...")
    if not dry_run:
        rows = sqlite_conn.execute("SELECT * FROM sites").fetchall()
        if rows:
            cols = rows[0].keys()
            placeholders = ", ".join(["%s"] * len(cols))
            col_names = ", ".join(cols)
            pg_cur.executemany(
                f"INSERT INTO sites ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
                [tuple(r) for r in rows]
            )
        rows = sqlite_conn.execute("SELECT * FROM categories").fetchall()
        if rows:
            cols = rows[0].keys()
            placeholders = ", ".join(["%s"] * len(cols))
            col_names = ", ".join(cols)
            pg_cur.executemany(
                f"INSERT INTO categories ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
                [tuple(r) for r in rows]
            )
        pg_conn.commit()
    print("  Done")

    # --- Step 4: Insert new docs not in Postgres ---
    print("[sync] Step 4: Checking for new docs...")
    pg_cur.execute("SELECT COUNT(*) FROM documents")
    pg_count = pg_cur.fetchone()[0]
    sqlite_count = sqlite_conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    new_count = sqlite_count - pg_count
    print(f"  Postgres: {pg_count:,} | SQLite: {sqlite_count:,} | New: {new_count:,}")

    if new_count > 0 and not dry_run:
        # Get IDs already in Postgres
        pg_cur.execute("SELECT id FROM documents")
        pg_ids = {row[0] for row in pg_cur.fetchall()}

        # Use only columns that exist in Postgres (handles schema drift)
        pg_cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'documents' ORDER BY ordinal_position
        """)
        pg_cols = [row[0] for row in pg_cur.fetchall()]
        col_names = ", ".join(pg_cols)
        template = "(" + ", ".join(["%s"] * len(pg_cols)) + ")"
        insert_sql = f"INSERT INTO documents ({col_names}) VALUES %s ON CONFLICT DO NOTHING"

        # Build SELECT with only Postgres-matching columns
        select_sql = f"SELECT {col_names} FROM documents"
        cursor = sqlite_conn.execute(select_sql)

        batch = []
        inserted = 0
        for row in cursor:
            if row[0] not in pg_ids:  # row[0] = id
                batch.append(tuple(row))
                if len(batch) >= 500:
                    psycopg2.extras.execute_values(
                        pg_cur, insert_sql, batch,
                        template=template, page_size=500
                    )
                    inserted += len(batch)
                    batch = []
                    print(f"  Inserted {inserted:,} new docs...", end="\r")
        if batch:
            psycopg2.extras.execute_values(
                pg_cur, insert_sql, batch,
                template=template, page_size=500
            )
            inserted += len(batch)
        pg_conn.commit()
        print(f"  Inserted {inserted:,} new docs")

    # --- Verify ---
    print("\n[sync] Verification:")
    pg_cur.execute("SELECT COUNT(*) FROM documents")
    print(f"  documents: {pg_cur.fetchone()[0]:,}")
    pg_cur.execute("SELECT COUNT(*) FROM documents WHERE classified_at IS NOT NULL AND classified_at != ''")
    print(f"  classified: {pg_cur.fetchone()[0]:,}")
    pg_cur.execute("SELECT importance, COUNT(*) FROM documents WHERE importance != '' GROUP BY importance ORDER BY COUNT(*) DESC")
    for row in pg_cur.fetchall():
        print(f"    {row[0]}: {row[1]:,}")

    pg_cur.close()
    pg_conn.close()
    sqlite_conn.close()
    print("\n[sync] Done!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync classification data to Postgres")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("Error: Set DATABASE_URL environment variable")
        sys.exit(1)

    sync(database_url, dry_run=args.dry_run)
