#!/usr/bin/env python3
"""Build a WORD-SEGMENTED FTS5 index (`doc_search_seg`) for real BM25 relevance.

The existing `doc_search` uses the **trigram** tokenizer: great for substring
matching on Chinese (no word boundaries), but `bm25()` over trigrams ranks by
3-gram frequency, which is almost noise — so search fell back to date ordering.

This builds a SECOND, independent FTS5 index whose tokens are actual Chinese
WORDS (segmented with jieba, see web/services/segment.py). Over real words,
`bm25()` becomes a proper TF-IDF-style relevance score with per-column weights
(title boosted). The two indexes coexist; the search service prefers this one and
falls back to the trigram index.

Design:
  * `content=''` (contentless) FTS5 — stores only the inverted index, not the
    segmented text (keeps it lean; we already have the originals in `documents`).
    `bm25()` works on contentless tables; rowid = documents.id joins back for display.
  * columns mirror doc_search: (title, document_number, keywords, abstract, body).
  * body is capped (segment.BODY_CAP chars) so the build is bounded and small.
  * INCREMENTAL by default: only indexes documents.id values not already present,
    so it can be re-run cheaply to pick up newly crawled docs (segmentation must
    happen in Python, so this can't be a SQL trigger like doc_search has).

Run ON the droplet (additive — creates a NEW table, never touches doc_search):
    nice -n 19 python3 scripts/build_search_index_seg.py            # build/refresh (incremental)
    python3 scripts/build_search_index_seg.py --rebuild             # drop & full rebuild
    python3 scripts/build_search_index_seg.py --check               # status only
    python3 scripts/build_search_index_seg.py --db /path/to.db      # target a copy
"""
import argparse
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from web.services.segment import segment_index  # noqa: E402

DB = ROOT / "documents.db"
COLS = ("title", "document_number", "keywords", "abstract", "body_text_cn")

CREATE = """
CREATE VIRTUAL TABLE IF NOT EXISTS doc_search_seg USING fts5(
    title, document_number, keywords, abstract, body_text_cn,
    content='',
    tokenize='unicode61 remove_diacritics 2'
);
"""


def _commit_batch(conn, ins_sql, batch, attempts=6):
    """executemany + commit, retrying on transient 'database is locked'.

    The target is the live documents.db (WAL): the web app reads it and crawlers
    may write. busy_timeout handles most contention; this adds a bounded backoff
    on top so a brief exclusive lock (e.g. another writer's checkpoint) doesn't
    abort a long build."""
    delay = 1.0
    for i in range(attempts):
        try:
            conn.executemany(ins_sql, batch)
            conn.commit()
            return
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and i < attempts - 1:
                time.sleep(delay)
                delay = min(delay * 2, 30)
                continue
            raise


def status(conn):
    have = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='doc_search_seg'"
    ).fetchone()[0]
    docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    idx = conn.execute("SELECT COUNT(*) FROM doc_search_seg").fetchone()[0] if have else 0
    return bool(have), docs, idx


def existing_rowids(conn):
    return {r[0] for r in conn.execute("SELECT rowid FROM doc_search_seg")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true", help="drop and fully rebuild")
    ap.add_argument("--check", action="store_true", help="status only")
    ap.add_argument("--batch", type=int, default=2000, help="rows per commit")
    ap.add_argument("--db", default=str(DB))
    args = ap.parse_args()

    conn = sqlite3.connect(args.db, timeout=180)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=180000")
    conn.execute("PRAGMA synchronous=NORMAL")

    have, docs, idx = status(conn)
    print(f"before: table={have} docs={docs:,} indexed={idx:,}")
    if args.check:
        return

    if args.rebuild and have:
        conn.execute("DROP TABLE doc_search_seg")
        conn.commit()
        have = False
    conn.executescript(CREATE)
    conn.commit()

    done = set() if args.rebuild else existing_rowids(conn)
    if done:
        print(f"incremental: {len(done):,} already indexed, skipping those")

    read = conn.cursor()
    read.execute(
        f"SELECT id, {', '.join(COLS)} FROM documents ORDER BY id"
    )

    ins_sql = (
        "INSERT INTO doc_search_seg(rowid, title, document_number, keywords, "
        "abstract, body_text_cn) VALUES (?,?,?,?,?,?)"
    )
    t0 = time.time()
    n = 0
    skipped = 0
    batch = []
    for row in read:
        doc_id = row[0]
        if doc_id in done:
            skipped += 1
            continue
        title, docnum, keywords, abstract, body = row[1:]
        batch.append((
            doc_id,
            segment_index(title, cap=0),        # titles are short — segment fully
            (docnum or "").strip(),             # doc numbers: keep raw (codes)
            segment_index(keywords, cap=0),
            segment_index(abstract),
            segment_index(body),
        ))
        if len(batch) >= args.batch:
            _commit_batch(conn, ins_sql, batch)
            n += len(batch)
            batch.clear()
            rate = n / max(time.time() - t0, 1e-6)
            print(f"  indexed {n:,} (+{rate:.0f}/s, {time.time()-t0:.0f}s)", flush=True)
    if batch:
        _commit_batch(conn, ins_sql, batch)
        n += len(batch)

    print(f"segmented+inserted {n:,} docs (skipped {skipped:,} already present) "
          f"in {time.time()-t0:.0f}s")
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    have, docs, idx = status(conn)
    print(f"after:  table={have} docs={docs:,} indexed={idx:,}")
    conn.close()


if __name__ == "__main__":
    main()
