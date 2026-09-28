"""Precompute `site_stats` — the fix for the ~74s cold `/browse` nav hang.

`get_sites` used to run `sites LEFT JOIN documents GROUP BY site_key` with
`SUM(CASE WHEN body_text_cn != '')`, which makes SQLite build a throwaway per-site
covering index that random-reads ~4GB of body-text overflow (measured 73.5s cold, no
warm-up; see docs/working/perf-diagnosis.md). An index can't help — the aggregate must
read the body column. So we precompute a tiny per-site summary table nightly and have
`get_sites` read that instead (O(sites), sub-ms).

This script is idempotent: run it once now to populate, and it's wired into
`daily_sync.sh` Phase 2c (after all writers, before the WAL checkpoint) to stay fresh.
It also ensures `idx_documents_classify_main` (the categories facet + category browse
filter otherwise full-scan 313k rows — the second finding in perf-diagnosis.md).

    python3 scripts/build_site_stats.py [--db documents.db] [--stats]
"""
import argparse
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "documents.db"

DDL = """
CREATE TABLE IF NOT EXISTS site_stats (
    site_key     TEXT PRIMARY KEY,
    doc_count    INTEGER NOT NULL DEFAULT 0,
    body_count   INTEGER NOT NULL DEFAULT 0,
    docnum_count INTEGER NOT NULL DEFAULT 0
);
"""


def build(db_path: Path) -> tuple:
    conn = sqlite3.connect(str(db_path), timeout=30)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        conn.executescript(DDL)
        # The second perf fix: no index existed on classify_main_name
        # (idx_documents_category is on category_id, a different column). One-time
        # build; a no-op on later nightly runs.
        conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_classify_main "
                     "ON documents(classify_main_name)")

        # Single sequential scan. `body_text_cn != ''` returns a 0/1 the engine
        # answers from each record's length header, so no overflow page is read and
        # the body never crosses into Python — this stays on the ~seconds get_stats
        # path, not the 74s automatic-index path.
        agg: dict[str, list] = {}
        for site_key, has_body, has_docnum in conn.execute(
                "SELECT site_key, body_text_cn != '', document_number != '' "
                "FROM documents"):
            row = agg.get(site_key)
            if row is None:
                row = agg[site_key] = [0, 0, 0]
            row[0] += 1
            row[1] += has_body
            row[2] += has_docnum

        conn.execute("DELETE FROM site_stats")
        conn.executemany(
            "INSERT INTO site_stats(site_key, doc_count, body_count, docnum_count) "
            "VALUES (?,?,?,?)",
            [(k, v[0], v[1], v[2]) for k, v in agg.items()])
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        return conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(doc_count),0) FROM site_stats").fetchone()
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=str, default=str(DEFAULT_DB))
    ap.add_argument("--stats", action="store_true", help="Print current site_stats and exit")
    args = ap.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")

    if args.stats:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        for r in conn.execute("SELECT site_key, doc_count, body_count, docnum_count "
                              "FROM site_stats ORDER BY doc_count DESC LIMIT 20"):
            print(f"  {r[0]:<16}{r[1]:>8}{r[2]:>8}{r[3]:>8}")
        conn.close()
        return

    t0 = time.time()
    sites, docs = build(db_path)
    print(f"site_stats built: {sites} sites, {docs:,} docs, {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
