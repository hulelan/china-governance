#!/usr/bin/env python3
"""compute_topics.py — tag every document with policy TOPIC labels.

Populates a `topics_algo` column (comma-joined labels) using the algorithmic
multi-label classifier in scripts/rnd/classification/topic_typer.py, over the 29
reconnectchina.org topic categories (Energy, Health, Housing, Finance, ...). This
is a TOPIC axis, orthogonal to `algo_doc_type` (document GENRE).

Safe/idempotent, mirroring compute_scores.py:
  - adds the column if missing,
  - streams (id, title, keywords, admin_level) — no body reads,
  - passes keywords ONLY for non-media docs (media `keywords` are a noisy auto-tag
    bag that injects spurious topics),
  - diffs computed vs stored and UPDATEs only CHANGED rows,
  - batched commits + periodic PASSIVE checkpoint + final TRUNCATE so the WAL
    stays small.

Run on the droplet (writes documents.db):
    python3 scripts/compute_topics.py            # full pass (only changed rows written)
    python3 scripts/compute_topics.py --dry-run  # compute + report, write nothing
    python3 scripts/compute_topics.py --stats    # show topic distribution
Wired into daily_sync.sh Phase 2 (pure CPU, title-only → cheap incremental).
"""
import argparse
import os
import sqlite3
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "rnd", "classification"))
from topic_typer import classify  # noqa: E402

DB = os.environ.get("SQLITE_PATH", "documents.db")
CHUNK = 5000


def _ensure_column(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(documents)")}
    if "topics_algo" not in cols:
        conn.execute("ALTER TABLE documents ADD COLUMN topics_algo TEXT DEFAULT ''")
        conn.commit()


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--db", default=DB)
    args = ap.parse_args(argv)

    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA busy_timeout = 30000")

    if args.stats:
        _ensure_column(conn)
        dist = Counter()
        tagged = 0
        total = 0
        for (ta,) in conn.execute("SELECT topics_algo FROM documents"):
            total += 1
            if ta:
                tagged += 1
                for t in ta.split(","):
                    dist[t] += 1
        print(f"{tagged:,}/{total:,} docs tagged ({100*tagged/max(total,1):.1f}%)")
        for t, c in dist.most_common():
            print(f"  {t:14} {c:>8,}")
        return 0

    _ensure_column(conn)

    # Stream (id, title, keywords, admin_level). admin_level via a joined lookup
    # so media keywords can be dropped.
    cur = conn.execute(
        """SELECT d.id, d.title, COALESCE(d.keywords, ''),
                  COALESCE(s.admin_level, ''), COALESCE(d.topics_algo, '')
           FROM documents d LEFT JOIN sites s ON s.site_key = d.site_key""")

    updates = []
    changed = n = 0
    write_conn = sqlite3.connect(args.db)
    write_conn.execute("PRAGMA busy_timeout = 30000")

    def flush():
        if not updates or args.dry_run:
            updates.clear()
            return
        write_conn.executemany(
            "UPDATE documents SET topics_algo = ? WHERE id = ?", updates)
        write_conn.commit()
        write_conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
        updates.clear()

    for doc_id, title, kw, level, stored in cur:
        n += 1
        labels = classify(title, "" if level == "media" else kw)
        val = ",".join(labels)
        if val != stored:
            changed += 1
            updates.append((val, doc_id))
            if len(updates) >= CHUNK:
                flush()
    flush()
    if not args.dry_run:
        write_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    print(f"{'[dry-run] ' if args.dry_run else ''}scanned {n:,}; "
          f"{'would update' if args.dry_run else 'updated'} {changed:,} "
          f"({n - changed:,} unchanged)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
