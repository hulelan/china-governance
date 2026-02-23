"""Create the citations table for persistent cross-document links.

Usage:
    python3 scripts/migrate_citations.py          # Create table
    python3 scripts/migrate_citations.py --drop    # Drop and recreate
"""

import argparse
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "documents.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    target_ref TEXT NOT NULL,
    target_id INTEGER,
    citation_type TEXT NOT NULL,
    source_level TEXT NOT NULL,
    target_level TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES documents(id),
    FOREIGN KEY (target_id) REFERENCES documents(id),
    UNIQUE(source_id, target_ref, citation_type)
);

CREATE INDEX IF NOT EXISTS idx_citations_source ON citations(source_id);
CREATE INDEX IF NOT EXISTS idx_citations_target_id ON citations(target_id);
CREATE INDEX IF NOT EXISTS idx_citations_target_ref ON citations(target_ref);
CREATE INDEX IF NOT EXISTS idx_citations_levels ON citations(source_level, target_level);
"""


def main():
    parser = argparse.ArgumentParser(description="Create citations table")
    parser.add_argument("--drop", action="store_true", help="Drop and recreate table")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)

    if args.drop:
        conn.execute("DROP TABLE IF EXISTS citations")
        print("Dropped citations table")

    conn.executescript(SCHEMA)
    conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM citations").fetchone()[0]
    print(f"Citations table ready ({count} rows)")
    conn.close()


if __name__ == "__main__":
    main()
