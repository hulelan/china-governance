#!/usr/bin/env python3
"""Build (and auto-maintain) an FTS5 trigram full-text index over documents.

Search was a full-table scan: `_norm(body_text_cn) LIKE '%q%'` over ~240k rows,
run twice (rows + COUNT) — seconds per query. This creates an FTS5 **trigram**
index (indexed substring matching that works on Chinese, which has no word
boundaries) so search becomes an index lookup (~ms).

- External-content FTS5 (`content='documents'`) → indexes, does not duplicate the
  body text (keeps documents.db lean; the trigram index itself is ~1-2GB).
- Three triggers keep it in sync as crawlers INSERT/UPDATE/DELETE documents, so
  no nightly rebuild is needed — new docs are searchable immediately.

Run on the droplet (writes to the live documents.db):
    python3 scripts/build_search_index.py            # create + populate
    python3 scripts/build_search_index.py --rebuild  # repopulate (after schema change)
    python3 scripts/build_search_index.py --check     # show status only
"""
import argparse, sqlite3, sys, time
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "documents.db"
COLS = ("title", "document_number", "keywords", "abstract", "body_text_cn")

CREATE = f"""
CREATE VIRTUAL TABLE IF NOT EXISTS doc_search USING fts5(
    {', '.join(COLS)},
    content='documents', content_rowid='id',
    tokenize='trigram'
);
"""

TRIGGERS = f"""
CREATE TRIGGER IF NOT EXISTS documents_fts_ai AFTER INSERT ON documents BEGIN
  INSERT INTO doc_search(rowid, {', '.join(COLS)})
    VALUES (new.id, {', '.join('new.'+c for c in COLS)});
END;
CREATE TRIGGER IF NOT EXISTS documents_fts_ad AFTER DELETE ON documents BEGIN
  INSERT INTO doc_search(doc_search, rowid, {', '.join(COLS)})
    VALUES ('delete', old.id, {', '.join('old.'+c for c in COLS)});
END;
CREATE TRIGGER IF NOT EXISTS documents_fts_au AFTER UPDATE ON documents BEGIN
  INSERT INTO doc_search(doc_search, rowid, {', '.join(COLS)})
    VALUES ('delete', old.id, {', '.join('old.'+c for c in COLS)});
  INSERT INTO doc_search(rowid, {', '.join(COLS)})
    VALUES (new.id, {', '.join('new.'+c for c in COLS)});
END;
"""


def status(conn):
    have = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='doc_search'"
    ).fetchone()[0]
    docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    idx = conn.execute("SELECT COUNT(*) FROM doc_search").fetchone()[0] if have else 0
    trig = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND name LIKE 'documents_fts_%'"
    ).fetchone()[0]
    return have, docs, idx, trig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true", help="repopulate the index")
    ap.add_argument("--check", action="store_true", help="status only")
    ap.add_argument("--db", default=str(DB))
    args = ap.parse_args()

    conn = sqlite3.connect(args.db, timeout=120)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=120000")

    have, docs, idx, trig = status(conn)
    print(f"before: table={bool(have)} docs={docs:,} indexed={idx:,} triggers={trig}")
    if args.check:
        return

    t0 = time.time()
    conn.executescript(CREATE)
    conn.executescript(TRIGGERS)
    print(f"schema ready (+{time.time()-t0:.1f}s); populating trigram index "
          f"over {docs:,} docs — this takes a few minutes…")
    # 'rebuild' repopulates the whole index from the content table.
    conn.execute("INSERT INTO doc_search(doc_search) VALUES('rebuild')")
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    have, docs, idx, trig = status(conn)
    print(f"after:  indexed={idx:,} triggers={trig}  (+{time.time()-t0:.0f}s total)")
    conn.close()


if __name__ == "__main__":
    main()
