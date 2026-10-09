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
CREATE TABLE IF NOT EXISTS doc_len (
    doc_id INTEGER PRIMARY KEY,
    chars  INTEGER NOT NULL          -- LENGTH(body_text_cn), 0 when absent
);
CREATE TABLE IF NOT EXISTS doc_inbound (
    doc_id  INTEGER PRIMARY KEY,          -- documents.id (only docs with >=1 inbound)
    inbound INTEGER NOT NULL DEFAULT 0,   -- distinct citing documents, self-cites dropped
    edges   INTEGER NOT NULL DEFAULT 0    -- raw resolved edge rows (what citation_rank weights)
);
CREATE INDEX IF NOT EXISTS idx_doc_inbound_inbound ON doc_inbound(inbound);
CREATE TABLE IF NOT EXISTS instrument_inbound (
    instrument_id INTEGER PRIMARY KEY,        -- doc_identity.instrument_id
    inbound       INTEGER NOT NULL DEFAULT 0, -- distinct citing docs OUTSIDE the pool
    edges         INTEGER NOT NULL DEFAULT 0,
    copies        INTEGER NOT NULL DEFAULT 0, -- documents in the pool
    cited_copies  INTEGER NOT NULL DEFAULT 0, -- copies carrying >=1 inbound of their own
    dated_id      INTEGER,                    -- a copy that HAS a date (canonical preferred)
    date_written  INTEGER NOT NULL DEFAULT 0  -- that copy's date; 0 = the whole pool is undated
);
CREATE INDEX IF NOT EXISTS idx_instrument_inbound_inbound ON instrument_inbound(inbound);
"""


def build_instrument_inbound(conn) -> tuple:
    """Roll citation weight up to `doc_identity.instrument_id`.

    Why (docs/working/undated-citation-weight.md): `doc_inbound` is per DOCUMENT, so
    weight lands on whichever COPY the citing text resolved to — frequently an undated
    mirror — while the dated canonical copy reads inbound 0. Corpus-wide that is 22,214
    of 44,364 cited documents and 120,361 of 270,695 citations (44.5%) sitting on rows
    with no date, so any series joining citation weight to a date silently drops them.
    Pooling recovers the part that needs NO date inference: a dated copy already exists
    in the same instrument for 2,201 of those documents / 26,443 citations.

    Two things this table does that the per-document one cannot:

    1. **Pool-level self-citation.** A mirror citing its own sibling is the same text
       citing itself. `doc_inbound` drops only `source_id = target_id`; here a citation
       is dropped when the SOURCE is in the same instrument pool as the target.
    2. **Carries a usable date.** `dated_id` / `date_written` name a copy that has one,
       preferring the canonical copy and otherwise the earliest-dated copy, so an
       analysis can read pooled weight against a real date.

    Additive: nothing reads it until it opts in, and `doc_inbound` keeps its meaning.
    Returns (rows, pooled_with_date, pooled_without_date).
    """
    conn.execute("DELETE FROM instrument_inbound")
    # Edge aggregation, excluding citations whose source is in the target's own pool.
    conn.execute("""
        INSERT INTO instrument_inbound(instrument_id, inbound, edges)
        SELECT ti.instrument_id, COUNT(DISTINCT c.source_id), COUNT(*)
        FROM citations c
        JOIN doc_identity ti ON ti.doc_id = c.target_id
        LEFT JOIN doc_identity si ON si.doc_id = c.source_id
        WHERE c.target_id IS NOT NULL
          AND ti.instrument_id IS NOT NULL
          AND (si.instrument_id IS NULL OR si.instrument_id != ti.instrument_id)
        GROUP BY ti.instrument_id""")

    # Pool size and how many copies carry inbound of their own.
    conn.execute("""
        UPDATE instrument_inbound SET
          copies = (SELECT COUNT(*) FROM doc_identity i
                    WHERE i.instrument_id = instrument_inbound.instrument_id),
          cited_copies = (SELECT COUNT(*) FROM doc_identity i
                          JOIN doc_inbound b ON b.doc_id = i.doc_id
                          WHERE i.instrument_id = instrument_inbound.instrument_id
                            AND b.inbound > 0)""")

    # A copy that has a date: the canonical one if dated, else the earliest dated copy.
    # `instrument_role` is feature-detected rather than assumed — this script runs in the
    # nightly, so a doc_identity built before that column existed must degrade (to plain
    # earliest-dated) instead of aborting Phase 2c.
    has_role = any(r[1] == "instrument_role"
                   for r in conn.execute("PRAGMA table_info(doc_identity)"))
    role_first = ("CASE WHEN i.instrument_role = 'canonical' THEN 0 ELSE 1 END, "
                  if has_role else "")
    conn.execute(f"""
        UPDATE instrument_inbound SET
          dated_id = (
            SELECT i.doc_id FROM doc_identity i JOIN documents d ON d.id = i.doc_id
            WHERE i.instrument_id = instrument_inbound.instrument_id AND d.date_written > 0
            ORDER BY {role_first}d.date_written
            LIMIT 1)""")
    conn.execute("""
        UPDATE instrument_inbound SET
          date_written = COALESCE(
            (SELECT d.date_written FROM documents d WHERE d.id = instrument_inbound.dated_id), 0)""")
    conn.commit()

    rows = conn.execute("SELECT COUNT(*) FROM instrument_inbound").fetchone()[0]
    with_date = conn.execute(
        "SELECT COUNT(*) FROM instrument_inbound WHERE date_written > 0").fetchone()[0]
    return rows, with_date, rows - with_date


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
        # `LENGTH(body_text_cn)` DOES read the overflow pages, unlike the `!= ''`
        # predicate above -- but measured 2026-10-08 on the live corpus that is
        # 7.3s for all 346,955 bodies (2.2s without it), because the plan stays a
        # bare `SCAN documents`. The 74s get_sites pathology was never "reading
        # bodies": it was the AUTOMATIC COVERING INDEX SQLite builds for a
        # `LEFT JOIN sites ... GROUP BY site_key` with the body inside the
        # aggregate (verified with EXPLAIN QUERY PLAN). This loop aggregates in
        # PYTHON, so no such index is built and a per-document length is ~5s.
        # Keep it that way: do not move this aggregation into SQL.
        agg: dict[str, list] = {}
        by_year: dict[int, int] = {}
        lens: list[tuple] = []
        for doc_id, site_key, has_body, has_docnum, yr, chars in conn.execute(
                "SELECT id, site_key, COALESCE(body_text_cn,'') != '', "
                "COALESCE(document_number,'') != '', "
                "CASE WHEN date_written > 0 THEN "
                "CAST(strftime('%Y', date_written, 'unixepoch') AS INTEGER) END, "
                "LENGTH(COALESCE(body_text_cn,'')) "
                "FROM documents"):
            row = agg.get(site_key)
            if row is None:
                row = agg[site_key] = [0, 0, 0]
            row[0] += 1
            row[1] += has_body
            row[2] += has_docnum
            if yr is not None:
                by_year[yr] = by_year.get(yr, 0) + 1
            lens.append((doc_id, chars or 0))

        site_count = conn.execute("SELECT COUNT(*) FROM sites").fetchone()[0]
        totals = [sum(v[i] for v in agg.values()) for i in range(3)]

        conn.execute("DELETE FROM site_stats")
        conn.executemany(
            "INSERT INTO site_stats(site_key, doc_count, body_count, docnum_count) "
            "VALUES (?,?,?,?)",
            [(k, v[0], v[1], v[2]) for k, v in agg.items()])
        # doc_len: a narrow side table, never a `documents` column -- an UPDATE on
        # `documents` rewrites the whole record including the body overflow pages
        # (the compute_scores lesson in CLAUDE.md). 347k rows of (int, int) is ~5MB.
        conn.execute("DELETE FROM doc_len")
        conn.executemany("INSERT INTO doc_len(doc_id, chars) VALUES (?,?)", lens)
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

        # Pooled citation weight, which needs doc_inbound above AND doc_identity.
        # Skipped (not failed) when doc_identity has not been built yet, so a fresh
        # DB can still run this script before Phase 2b exists.
        if conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
                        "AND name='doc_identity'").fetchone()[0]:
            t_ii = time.time()
            ii_rows, ii_dated, ii_undated = build_instrument_inbound(conn)
            print(f"instrument_inbound built: {ii_rows:,} instruments "
                  f"({ii_dated:,} with a dated copy, {ii_undated:,} wholly undated), "
                  f"{time.time()-t_ii:.1f}s")
        else:
            print("instrument_inbound: SKIPPED (doc_identity not built yet)")

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
