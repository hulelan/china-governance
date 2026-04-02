"""Migrate data from local SQLite database to PostgreSQL.

Usage:
    # Set DATABASE_URL to your Railway Postgres connection string
    export DATABASE_URL="postgresql://user:pass@host:port/dbname"

    # Incremental sync (default) — only inserts new docs, skips existing
    python3 scripts/sqlite_to_postgres.py

    # Rebuild from scratch (drops all tables first) — slow, use sparingly
    python3 scripts/sqlite_to_postgres.py --drop
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

SCHEMA = """
-- Enable trigram extension for ILIKE search performance
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS sites (
    site_key TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    base_url TEXT NOT NULL,
    admin_level TEXT,
    sid TEXT,
    tree_json TEXT,
    last_crawled TEXT
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY,
    site_key TEXT NOT NULL,
    name TEXT NOT NULL,
    parent_id INTEGER,
    post_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    site_key TEXT NOT NULL,
    category_id INTEGER,
    title TEXT NOT NULL,
    document_number TEXT DEFAULT '',
    identifier TEXT,
    publisher TEXT,
    keywords TEXT,
    date_written INTEGER,
    date_published TEXT,
    display_publish_time INTEGER,
    abstract TEXT,
    body_text_cn TEXT,
    body_text_en TEXT,
    classify_main_name TEXT,
    classify_genre_name TEXT,
    classify_theme_name TEXT,
    url TEXT,
    post_url TEXT,
    is_expired INTEGER DEFAULT 0,
    is_abolished INTEGER DEFAULT 0,
    attachments_json TEXT,
    relation TEXT,
    raw_html_path TEXT,
    crawl_timestamp TEXT NOT NULL,
    raw_html_sha256 TEXT DEFAULT '',
    title_en TEXT DEFAULT '',
    summary_en TEXT DEFAULT '',
    category TEXT DEFAULT '',
    importance TEXT DEFAULT '',
    policy_area TEXT DEFAULT '',
    topics TEXT DEFAULT '',
    classification_model TEXT DEFAULT '',
    classified_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS citations (
    id SERIAL PRIMARY KEY,
    source_id INTEGER NOT NULL,
    target_ref TEXT NOT NULL,
    target_id INTEGER,
    citation_type TEXT NOT NULL,
    source_level TEXT NOT NULL,
    target_level TEXT NOT NULL,
    UNIQUE(source_id, target_ref, citation_type)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_documents_site_key ON documents(site_key);
CREATE INDEX IF NOT EXISTS idx_documents_date_written ON documents(date_written);
CREATE INDEX IF NOT EXISTS idx_documents_document_number ON documents(document_number);
CREATE INDEX IF NOT EXISTS idx_documents_category_id ON documents(category_id);
CREATE INDEX IF NOT EXISTS idx_citations_source_id ON citations(source_id);
CREATE INDEX IF NOT EXISTS idx_citations_target_id ON citations(target_id);
CREATE INDEX IF NOT EXISTS idx_categories_site_key ON categories(site_key);
CREATE INDEX IF NOT EXISTS idx_documents_importance ON documents(importance);
CREATE INDEX IF NOT EXISTS idx_documents_category_class ON documents(category);

-- Trigram indexes for ILIKE search performance
CREATE INDEX IF NOT EXISTS idx_documents_title_trgm ON documents USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_documents_body_trgm ON documents USING gin (body_text_cn gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_documents_keywords_trgm ON documents USING gin (keywords gin_trgm_ops);

CREATE TABLE IF NOT EXISTS subsidy_items (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL,
    amount_value REAL,
    amount_raw TEXT,
    amount_context TEXT,
    sector TEXT,
    FOREIGN KEY (document_id) REFERENCES documents(id)
);

CREATE INDEX IF NOT EXISTS idx_subsidy_items_doc ON subsidy_items(document_id);
CREATE INDEX IF NOT EXISTS idx_subsidy_items_sector ON subsidy_items(sector);

CREATE TABLE IF NOT EXISTS document_changes (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL,
    site_key TEXT NOT NULL,
    change_type TEXT NOT NULL,
    field_name TEXT,
    old_value TEXT,
    new_value TEXT,
    detected_at TEXT NOT NULL,
    sync_run_id TEXT,
    FOREIGN KEY (document_id) REFERENCES documents(id)
);

CREATE INDEX IF NOT EXISTS idx_doc_changes_doc ON document_changes(document_id);
CREATE INDEX IF NOT EXISTS idx_doc_changes_type ON document_changes(change_type);
CREATE INDEX IF NOT EXISTS idx_doc_changes_detected ON document_changes(detected_at);
CREATE INDEX IF NOT EXISTS idx_doc_changes_run ON document_changes(sync_run_id);
"""

DROP_SCHEMA = """
DROP TABLE IF EXISTS document_changes CASCADE;
DROP TABLE IF EXISTS subsidy_items CASCADE;
DROP TABLE IF EXISTS citations CASCADE;
DROP TABLE IF EXISTS documents CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS sites CASCADE;
"""


def migrate(database_url: str, drop: bool = False):
    # Connect to both databases
    sqlite_conn = sqlite3.connect(str(SQLITE_PATH))
    sqlite_conn.row_factory = sqlite3.Row
    pg_conn = psycopg2.connect(database_url)
    pg_cur = pg_conn.cursor()

    if drop:
        print("[migrate] Dropping existing tables...")
        pg_cur.execute(DROP_SCHEMA)
        pg_conn.commit()

    print("[migrate] Creating schema...")
    pg_cur.execute(SCHEMA)
    pg_conn.commit()

    # URL uniqueness index — created separately because existing dups must be
    # cleaned up first (the main schema would fail atomically otherwise).
    try:
        pg_cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_url "
            "ON documents(url) WHERE url != ''"
        )
        pg_conn.commit()
    except Exception:
        pg_conn.rollback()
        print("[migrate] Deduplicating URLs before creating unique index...")
        # Identify duplicate IDs to remove (keep row with most body text, or lowest id)
        dup_ids_query = """
            SELECT d.id FROM documents d
            INNER JOIN (
                SELECT url, MAX(LENGTH(COALESCE(body_text_cn, ''))) AS max_len
                FROM documents WHERE url != '' GROUP BY url HAVING COUNT(*) > 1
            ) dups ON d.url = dups.url
            WHERE LENGTH(COALESCE(d.body_text_cn, '')) < dups.max_len
               OR (LENGTH(COALESCE(d.body_text_cn, '')) = dups.max_len
                   AND d.id NOT IN (
                       SELECT MIN(id) FROM documents WHERE url != '' GROUP BY url
                   ))
        """
        # Clean up child tables first (FK constraints)
        for child_table, col in [("document_changes", "document_id"),
                                  ("subsidy_items", "document_id"),
                                  ("citations", "source_id")]:
            pg_cur.execute(f"DELETE FROM {child_table} WHERE {col} IN ({dup_ids_query})")
            if pg_cur.rowcount:
                print(f"  Removed {pg_cur.rowcount} orphaned rows from {child_table}")
        pg_cur.execute(f"DELETE FROM documents WHERE id IN ({dup_ids_query})")
        removed = pg_cur.rowcount
        print(f"  Removed {removed} duplicate documents from Postgres")
        pg_cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_url "
            "ON documents(url) WHERE url != ''"
        )
        pg_conn.commit()

    if not drop:
        # Ensure Postgres has all columns that SQLite has (handles schema drift)
        pg_cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'documents'
        """)
        pg_cols = {row[0] for row in pg_cur.fetchall()}
        sqlite_cols = sqlite_conn.execute("PRAGMA table_info(documents)").fetchall()
        for col_info in sqlite_cols:
            col_name = col_info[1]
            if col_name not in pg_cols:
                col_type = col_info[2] or "TEXT"
                default = f" DEFAULT {col_info[4]}" if col_info[4] is not None else " DEFAULT ''"
                print(f"  Adding missing column to Postgres: {col_name} {col_type}{default}")
                pg_cur.execute(f"ALTER TABLE documents ADD COLUMN {col_name} {col_type}{default}")
        pg_conn.commit()

    # --- Sites ---
    print("[migrate] Migrating sites...")
    rows = sqlite_conn.execute("SELECT * FROM sites").fetchall()
    if rows:
        cols = rows[0].keys()
        placeholders = ", ".join(["%s"] * len(cols))
        col_names = ", ".join(cols)
        pg_cur.executemany(
            f"INSERT INTO sites ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
            [tuple(r) for r in rows]
        )
        pg_conn.commit()
        print(f"  {len(rows)} sites")

    # --- Categories ---
    print("[migrate] Migrating categories...")
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
        print(f"  {len(rows):,} categories")

    # --- Documents (batch for speed) ---
    # Only sync docs newer than what Postgres already has (true incremental)
    pg_cur.execute("SELECT MAX(id) FROM documents")
    pg_max_id = pg_cur.fetchone()[0] or 0
    local_count = sqlite_conn.execute("SELECT COUNT(*) FROM documents WHERE id > ?", (pg_max_id,)).fetchone()[0]
    print(f"[migrate] Migrating documents... (Postgres has up to id={pg_max_id:,}, {local_count:,} new)")
    cursor = sqlite_conn.execute("SELECT * FROM documents WHERE id > ? ORDER BY id", (pg_max_id,))
    cols = [desc[0] for desc in cursor.description]
    col_names = ", ".join(cols)
    # Use execute_values for much faster bulk inserts (multi-row VALUES)
    template = "(" + ", ".join(["%s"] * len(cols)) + ")"
    insert_sql = f"INSERT INTO documents ({col_names}) VALUES %s ON CONFLICT DO NOTHING"

    batch_size = 500
    total = 0
    while True:
        batch = cursor.fetchmany(batch_size)
        if not batch:
            break
        psycopg2.extras.execute_values(
            pg_cur, insert_sql, [tuple(r) for r in batch],
            template=template, page_size=batch_size
        )
        pg_conn.commit()
        total += len(batch)
        print(f"  {total:,} documents...", end="\r")
    print(f"  {total:,} documents")

    # --- Citations ---
    pg_cur.execute("SELECT COUNT(*) FROM citations")
    pg_citation_count = pg_cur.fetchone()[0] or 0
    local_citation_count = sqlite_conn.execute("SELECT COUNT(*) FROM citations").fetchone()[0]
    new_citations = local_citation_count - pg_citation_count
    print(f"[migrate] Migrating citations... (Postgres has {pg_citation_count:,}, ~{new_citations:,} new)")
    rows = sqlite_conn.execute(
        "SELECT source_id, target_ref, target_id, citation_type, source_level, target_level FROM citations"
    ).fetchall()
    if rows:
        insert_sql = (
            "INSERT INTO citations (source_id, target_ref, target_id, citation_type, source_level, target_level) "
            "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING"
        )
        batch_size = 2000
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            pg_cur.executemany(insert_sql, [tuple(r) for r in batch])
            pg_conn.commit()
        print(f"  {len(rows):,} citations")

    # --- Subsidy Items ---
    try:
        sqlite_conn.execute("SELECT 1 FROM subsidy_items LIMIT 1")
        has_subsidy = True
    except sqlite3.OperationalError:
        has_subsidy = False

    if has_subsidy:
        print("[migrate] Migrating subsidy_items...")
        rows = sqlite_conn.execute(
            "SELECT document_id, amount_value, amount_raw, amount_context, sector FROM subsidy_items"
        ).fetchall()
        if rows:
            insert_sql = (
                "INSERT INTO subsidy_items (document_id, amount_value, amount_raw, amount_context, sector) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING"
            )
            batch_size = 2000
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                pg_cur.executemany(insert_sql, [tuple(r) for r in batch])
                pg_conn.commit()
            print(f"  {len(rows):,} subsidy items")
    else:
        print("[migrate] No subsidy_items table in SQLite (skipping)")

    # --- Document Changes ---
    try:
        sqlite_conn.execute("SELECT 1 FROM document_changes LIMIT 1")
        has_changes = True
    except sqlite3.OperationalError:
        has_changes = False

    if has_changes:
        print("[migrate] Migrating document_changes...")
        rows = sqlite_conn.execute(
            """SELECT dc.document_id, dc.site_key, dc.change_type, dc.field_name,
                      dc.old_value, dc.new_value, dc.detected_at, dc.sync_run_id
               FROM document_changes dc
               JOIN documents d ON d.id = dc.document_id"""
        ).fetchall()
        if rows:
            insert_sql = (
                "INSERT INTO document_changes (document_id, site_key, change_type, field_name, old_value, new_value, detected_at, sync_run_id) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING"
            )
            batch_size = 2000
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                pg_cur.executemany(insert_sql, [tuple(r) for r in batch])
                pg_conn.commit()
            print(f"  {len(rows):,} document changes")
    else:
        print("[migrate] No document_changes table in SQLite (skipping)")

    # --- Verify ---
    print("\n[migrate] Verification:")
    for table in ["sites", "categories", "documents", "citations", "subsidy_items", "document_changes"]:
        pg_cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = pg_cur.fetchone()[0]
        print(f"  {table}: {count:,} rows")

    pg_cur.close()
    pg_conn.close()
    sqlite_conn.close()
    print("\n[migrate] Done!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate SQLite to PostgreSQL")
    parser.add_argument("--drop", action="store_true", help="Drop and recreate tables")
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("Error: Set DATABASE_URL environment variable")
        print("Example: export DATABASE_URL='postgresql://user:pass@host:port/railway'")
        sys.exit(1)

    migrate(database_url, drop=args.drop)
