"""Precompute `site_stats` — the fix for the ~74s cold `/browse` nav hang.

`get_sites` used to run `sites LEFT JOIN documents GROUP BY site_key` with
`SUM(CASE WHEN body_text_cn != '')`, which makes SQLite build a throwaway per-site
covering index that random-reads ~4GB of body-text overflow (measured 73.5s cold, no
warm-up; see docs/working/perf-diagnosis.md). An index can't help — the aggregate must
read the body column. So we precompute a tiny per-site summary table nightly and have
`get_sites` read that instead (O(sites), sub-ms).

The same pass ALSO writes `corpus_stats` — the corpus-wide totals `get_stats` needs on
EVERY page (total / with_body / with_docnum / site_count + the by-year rollup). That
live scan cost ~1.5–3s cold per worker after each nightly restart (perf-diagnosis.md
item 3: the first-click-of-the-morning case). `corpus_stats` is a key/value table:
scalar keys plus one `year:<YYYY>` row per publication year (the year is computed with
the same `strftime('%Y', date_written, 'unixepoch')` the live query uses).

The same pass ALSO writes `doc_inbound` (corpus-lessons.md B6): the RAW resolved
inbound-citation count per document, shown next to `citation_rank` wherever rank is
rendered, because the 3x-central weighting in `citation_rank` still shapes the top of
the ranking (19/30 overlap with the raw corrected top-30, citation-network-structure.md).
`inbound` = COUNT(DISTINCT source_id) over `citations` with a resolved `target_id`,
self-cites dropped (the memo's definition); `edges` = the raw resolved edge-row count
(what `citation_rank` weights). One `GROUP BY target_id` pass, ~1s for ~270k edges.
List pages LEFT JOIN this table instead of running a correlated COUNT per row.

This script is idempotent: run it once now to populate, and it's wired into
`daily_sync.sh` Phase 2c (after all writers — in particular AFTER Phase 2b's
extract_citations + compute_scores, so doc_inbound is as fresh as citation_rank —
and before the WAL checkpoint) to stay fresh.
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
CREATE TABLE IF NOT EXISTS corpus_stats (
    key   TEXT PRIMARY KEY,   -- total | with_body | with_docnum | site_count | year:<YYYY>
    value INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS doc_inbound (
    doc_id  INTEGER PRIMARY KEY,          -- documents.id (only docs with >=1 inbound)
    inbound INTEGER NOT NULL DEFAULT 0,   -- distinct citing documents, self-cites dropped
    edges   INTEGER NOT NULL DEFAULT 0    -- raw resolved edge rows (what citation_rank weights)
);
CREATE INDEX IF NOT EXISTS idx_doc_inbound_inbound ON doc_inbound(inbound);
"""


def build_doc_inbound(conn) -> tuple:
    """Rebuild doc_inbound from `citations` in one GROUP BY pass (~1s). Returns
    (rows, max_inbound). Runs inside the caller's connection; commits itself."""
    conn.execute("DELETE FROM doc_inbound")
    conn.execute(
        "INSERT INTO doc_inbound(doc_id, inbound, edges) "
        "SELECT target_id, COUNT(DISTINCT source_id), COUNT(*) "
        "FROM citations WHERE target_id IS NOT NULL AND source_id != target_id "
        "GROUP BY target_id")
    conn.commit()
    return conn.execute(
        "SELECT COUNT(*), COALESCE(MAX(inbound),0) FROM doc_inbound").fetchone()


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
        # COALESCE so a NULL body/docnum counts as empty (0), matching the old
        # get_sites CASE semantics — `NULL != ''` is NULL, not 0, in SQL.
        # The year expression mirrors web/database.py's translation of the live
        # get_stats query (EXTRACT(YEAR FROM to_timestamp(date_written))), so the
        # precomputed by-year rollup is identical to what the slow path returns.
        agg: dict[str, list] = {}
        by_year: dict[int, int] = {}
        for site_key, has_body, has_docnum, yr in conn.execute(
                "SELECT site_key, COALESCE(body_text_cn,'') != '', "
                "COALESCE(document_number,'') != '', "
                "CASE WHEN date_written > 0 THEN "
                "CAST(strftime('%Y', date_written, 'unixepoch') AS INTEGER) END "
                "FROM documents"):
            row = agg.get(site_key)
            if row is None:
                row = agg[site_key] = [0, 0, 0]
            row[0] += 1
            row[1] += has_body
            row[2] += has_docnum
            if yr is not None:
                by_year[yr] = by_year.get(yr, 0) + 1

        site_count = conn.execute("SELECT COUNT(*) FROM sites").fetchone()[0]
        totals = [sum(v[i] for v in agg.values()) for i in range(3)]

        conn.execute("DELETE FROM site_stats")
        conn.executemany(
            "INSERT INTO site_stats(site_key, doc_count, body_count, docnum_count) "
            "VALUES (?,?,?,?)",
            [(k, v[0], v[1], v[2]) for k, v in agg.items()])
        conn.execute("DELETE FROM corpus_stats")
        conn.executemany(
            "INSERT INTO corpus_stats(key, value) VALUES (?,?)",
            [("total", totals[0]), ("with_body", totals[1]),
             ("with_docnum", totals[2]), ("site_count", site_count)]
            + [(f"year:{y}", n) for y, n in sorted(by_year.items())])
        conn.commit()
        t_in = time.time()
        in_rows, in_max = build_doc_inbound(conn)
        print(f"doc_inbound built: {in_rows:,} docs with inbound, max {in_max:,}, "
              f"{time.time()-t_in:.1f}s")
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
        print("corpus_stats:")
        for r in conn.execute("SELECT key, value FROM corpus_stats ORDER BY key"):
            print(f"  {r[0]:<16}{r[1]:>10,}")
        try:
            n, mx = conn.execute(
                "SELECT COUNT(*), COALESCE(MAX(inbound),0) FROM doc_inbound").fetchone()
            print(f"doc_inbound: {n:,} docs with inbound citations, max {mx:,}")
        except sqlite3.OperationalError:
            print("doc_inbound: (table absent — run without --stats to build)")
        conn.close()
        return

    t0 = time.time()
    sites, docs = build(db_path)
    print(f"site_stats built: {sites} sites, {docs:,} docs, {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
