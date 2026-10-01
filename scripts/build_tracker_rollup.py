"""Precompute `tracker_weekly` — the per-topic / per-ISO-week / per-level rollup
behind the daily policy tracker (step 2 of docs/research/daily-tracker-concept.md).

Same pattern as `build_site_stats.py`: a small table rebuilt nightly in the clean
write-window (daily_sync.sh Phase 2c, after citations/scores/topics and the
diffusion-events auto-matcher, before the Phase 3 checkpoint) so the tracker view
reads a few indexed rows instead of scanning `documents` × `topics_algo` cold.

One row per (topic, iso_week, admin_level):
  new_docs                 docs published that ISO week at that level carrying the
                           topic (`topics_algo` is a comma-separated multi-label;
                           each tag counts once, and every doc also counts under
                           topic='all').
  cascade_events           confirmed diffusion events (match_type citation or
                           title_reissue) whose SOURCE doc was published that week
                           at that level, under every topic of the event's ANCHOR
                           (the campaign defines the topic; `diffusion_events.topic`
                           only stores the anchor's first tag) — and under 'all'.
  cascade_events_lowconf   the same for match_type topic_genre (probable, unconfirmed).

Bounded to date_published 2018-01-01..2026-12-31 — the tracker is about recent
weeks, and this keeps the table small and the rebuild a few seconds.
Idempotent: CREATE IF NOT EXISTS + DELETE + INSERT.

    python3 scripts/build_tracker_rollup.py [--db documents.db] [--stats]
"""
import argparse
import sqlite3
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "documents.db"

DATE_LO, DATE_HI = "2018-01-01", "2026-12-31"
ALL = "all"
CONFIRMED = {"citation", "title_reissue"}
LOWCONF = {"topic_genre"}

DDL = """
CREATE TABLE IF NOT EXISTS tracker_weekly (
    topic                  TEXT NOT NULL,
    iso_week               TEXT NOT NULL,   -- 'YYYY-Www' (ISO 8601 week)
    admin_level            TEXT NOT NULL,
    week_start             TEXT NOT NULL,   -- Monday of that ISO week, 'YYYY-MM-DD'
    new_docs               INTEGER NOT NULL DEFAULT 0,
    cascade_events         INTEGER NOT NULL DEFAULT 0,
    cascade_events_lowconf INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (topic, iso_week, admin_level)
);
CREATE INDEX IF NOT EXISTS idx_tracker_weekly_topic_week ON tracker_weekly(topic, iso_week);
"""


def iso_week(d10: str):
    """'YYYY-MM-DD' -> ('YYYY-Www', monday 'YYYY-MM-DD'), or None if unparseable."""
    try:
        y, m, d = int(d10[0:4]), int(d10[5:7]), int(d10[8:10])
        dt = date(y, m, d)
    except (ValueError, TypeError):
        return None
    iy, iw, iwd = dt.isocalendar()
    monday = date.fromordinal(dt.toordinal() - (iwd - 1))
    return f"{iy}-W{iw:02d}", monday.isoformat()


def split_topics(s):
    return [t for t in (s or "").split(",") if t]


def build(db_path: Path) -> tuple:
    conn = sqlite3.connect(str(db_path), timeout=30)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        conn.executescript(DDL)

        site_level = dict(conn.execute(
            "SELECT site_key, COALESCE(admin_level,'unknown') FROM sites"))
        week_cache: dict[str, tuple] = {}

        def wk(d10):
            if d10 not in week_cache:
                week_cache[d10] = iso_week(d10)
            return week_cache[d10]

        # (topic, iso_week, level) -> [new_docs, cascade, cascade_lowconf]
        agg: dict[tuple, list] = defaultdict(lambda: [0, 0, 0])
        weeks: dict[str, str] = {}  # iso_week -> week_start

        # --- new_docs: single sequential scan, small columns only (no body) ---
        # substr: date_published is mixed 'YYYY-MM-DD' / '... HH:MM[:SS]'.
        n_docs = 0
        for site_key, d10, topics in conn.execute(
                "SELECT site_key, substr(date_published,1,10), topics_algo "
                "FROM documents WHERE substr(date_published,1,10) BETWEEN ? AND ?",
                (DATE_LO, DATE_HI)):
            w = wk(d10)
            if w is None:
                continue
            iw, monday = w
            weeks[iw] = monday
            level = site_level.get(site_key, "unknown")
            n_docs += 1
            agg[(ALL, iw, level)][0] += 1
            for t in set(split_topics(topics)):
                agg[(t, iw, level)][0] += 1

        # --- cascade events: anchor's full topic set (fallback: stored topic) ---
        n_ev = 0
        for mtype, d10, level, ev_topic, anchor_topics in conn.execute(
                "SELECT e.match_type, substr(e.source_date,1,10), "
                "       COALESCE(e.source_level,'unknown'), e.topic, d.topics_algo "
                "FROM diffusion_events e LEFT JOIN documents d ON d.id = e.anchor_id "
                "WHERE substr(e.source_date,1,10) BETWEEN ? AND ?",
                (DATE_LO, DATE_HI)):
            if mtype in CONFIRMED:
                col = 1
            elif mtype in LOWCONF:
                col = 2
            else:
                continue
            w = wk(d10)
            if w is None:
                continue
            iw, monday = w
            weeks[iw] = monday
            n_ev += 1
            agg[(ALL, iw, level)][col] += 1
            topics = set(split_topics(anchor_topics)) or set(split_topics(ev_topic))
            for t in topics:
                agg[(t, iw, level)][col] += 1

        conn.execute("DELETE FROM tracker_weekly")
        conn.executemany(
            "INSERT INTO tracker_weekly(topic, iso_week, admin_level, week_start, "
            "new_docs, cascade_events, cascade_events_lowconf) VALUES (?,?,?,?,?,?,?)",
            [(t, iw, lvl, weeks[iw], v[0], v[1], v[2])
             for (t, iw, lvl), v in agg.items()])
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        rows = conn.execute("SELECT COUNT(*) FROM tracker_weekly").fetchone()[0]
        return rows, n_docs, n_ev
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=str, default=str(DEFAULT_DB))
    ap.add_argument("--stats", action="store_true",
                    help="Print the busiest recent weeks (topic='all') and exit")
    args = ap.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")

    if args.stats:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        print(f"  {'week':<9}{'level':<12}{'docs':>7}{'casc':>6}{'low':>6}")
        for r in conn.execute(
                "SELECT iso_week, admin_level, new_docs, cascade_events, "
                "cascade_events_lowconf FROM tracker_weekly WHERE topic='all' "
                "ORDER BY iso_week DESC, admin_level LIMIT 30"):
            print(f"  {r[0]:<9}{r[1]:<12}{r[2]:>7}{r[3]:>6}{r[4]:>6}")
        conn.close()
        return

    t0 = time.time()
    rows, n_docs, n_ev = build(db_path)
    print(f"tracker_weekly built: {rows:,} rows from {n_docs:,} docs + "
          f"{n_ev:,} diffusion events, {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
