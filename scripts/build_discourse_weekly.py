"""Precompute `discourse_weekly`, the concept x speaker-type x ISO-week table behind
/discourse (the global-discourse tracker, docs/research/global-discourse-map.md,
"what to study next" item 3).

Same pattern as build_tracker_rollup.py: a small table rebuilt nightly in Phase 2c
so the page reads a few indexed rows instead of regex-scanning bodies.

    discourse_weekly(concept, speaker, iso_week, docs, denom)
        docs   documents of that speaker type, published that ISO week, whose
               title + body match the concept's regex.
        denom  ALL documents of that speaker type that week (with a body), so a
               rate per 1,000 is docs / denom * 1000 and a thin week is visible.
        Rows exist only where docs > 0, plus one row per (speaker, week) with
        concept = '_all' and docs = denom, so the page has the denominator for
        weeks in which a concept never appears.
    discourse_concepts(concept, label_en, family, pattern)
        the vocabulary itself (web/services/discourse_vocab.py, the one source of
        truth shared with the memo's scripts).

Rules, identical to the memo's scans:
  * speaker type from discourse_vocab.speaker(site_key, doc_identity.admin_level_doc);
    rows with no speaker type (foreign media, unlevelled) are skipped.
  * ONE COPY PER TITLE PER SPEAKER TYPE PER WEEK: a Xinhua story reposted by forty
    portals counts once per speaker type, not forty times. The kept copy is the
    lowest document id. (The memo deduped across its whole window; a weekly table
    dedups within the week, so a repost in a later week counts again there.)
    A title that normalizes to empty is never merged with another document.
  * only documents with a body (body_text_cn != ''), date_published in
    [--from, today]. Future-dated rows are ignored.
  * 观察者网 page chrome is cut off before scanning (discourse_vocab.strip_chrome:
    the "相关推荐 / 观察者头条" headline lists), and a guancha row whose body was
    ONLY chrome is dropped from numerator and denominator alike.

Cost: bodies are scanned in PYTHON from a streamed cursor (never a SQL GROUP BY
over body_text_cn; see the get_sites lesson in CLAUDE.md), each concept gated by a
literal `anchor in text` test before its regex. The write is ONE short transaction
at the end (DELETE + INSERT of a few tens of thousands of rows).

    python3 scripts/build_discourse_weekly.py [--db documents.db] [--out other.db]
    python3 scripts/build_discourse_weekly.py --since 2026-10-01   # rebuild weeks >= that week only
    python3 scripts/build_discourse_weekly.py --dry-run             # compute + print, write nothing
"""
import argparse
import re
import sqlite3
import sys
import time
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "documents.db"
sys.path.insert(0, str(ROOT))
from web.services.discourse_vocab import (  # noqa: E402
    CHROME_MIN_TEXT, CHROME_SITES, all_terms, article_chars, compiled, speaker, strip_chrome)

DATE_LO = "2018-01-01"
ALL = "_all"
_NONWORD = re.compile(r"\W")

DDL = """
CREATE TABLE IF NOT EXISTS discourse_weekly (
    concept   TEXT NOT NULL,      -- discourse_concepts.concept, or '_all' (= the denominator row)
    speaker   TEXT NOT NULL,      -- discourse_vocab.SPEAKERS
    iso_week  TEXT NOT NULL,      -- 'YYYY-Www' (ISO 8601; sorts chronologically)
    docs      INTEGER NOT NULL,   -- deduped docs of that speaker that week using the concept
    denom     INTEGER NOT NULL,   -- deduped docs of that speaker that week (all, with a body)
    PRIMARY KEY (concept, speaker, iso_week)
);
CREATE INDEX IF NOT EXISTS idx_discourse_weekly_week ON discourse_weekly(iso_week);
CREATE TABLE IF NOT EXISTS discourse_concepts (
    concept   TEXT PRIMARY KEY,
    label_en  TEXT NOT NULL,
    family    TEXT NOT NULL,
    pattern   TEXT NOT NULL
);
"""


def iso_week(d10: str):
    """'YYYY-MM-DD...' -> 'YYYY-Www', or None for an unparseable date."""
    try:
        y, w, _ = date(int(d10[0:4]), int(d10[5:7]), int(d10[8:10])).isocalendar()
    except (ValueError, TypeError, IndexError):
        return None
    return f"{y}-W{w:02d}"


def week_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def title_key(title, doc_id):
    k = _NONWORD.sub("", title or "")[:40]
    return k if k else f"#id{doc_id}"


def compute(conn, date_lo=DATE_LO, date_hi=None):
    """Scan [date_lo, date_hi) and return (hits Counter[(concept, speaker, week)],
    denom Counter[(speaker, week)], stats dict). Read-only."""
    date_hi = date_hi or (date.today() + timedelta(days=1)).isoformat()
    terms = compiled()
    has_identity = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='doc_identity'").fetchone()
    lvl_sql = "COALESCE(i.admin_level_doc,'')" if has_identity else "''"
    join = "LEFT JOIN doc_identity i ON i.doc_id = d.id" if has_identity else ""
    q = (f"SELECT d.id, d.site_key, substr(d.date_published,1,10), d.title, d.body_text_cn, {lvl_sql} "
         f"FROM documents d {join} "
         "WHERE d.body_text_cn != '' AND d.date_published >= ? AND d.date_published < ? "
         "ORDER BY d.id")
    hits, denom = Counter(), Counter()
    seen = set()
    st = Counter()
    cur = conn.execute(q, (date_lo, date_hi))
    while True:
        batch = cur.fetchmany(2000)
        if not batch:
            break
        for did, site, d10, title, body, lvl in batch:
            st["scanned"] += 1
            sp = speaker(site, lvl)
            if not sp:
                st["no_speaker"] += 1
                continue
            wk = iso_week(d10)
            if not wk:
                st["bad_date"] += 1
                continue
            if site in CHROME_SITES:
                stripped = strip_chrome(site, body)
                if len(stripped) != len(body):
                    st["chrome_stripped"] += 1
                    if article_chars(title, stripped) < CHROME_MIN_TEXT:
                        st["chrome_only"] += 1      # the page chrome was all we stored
                        continue
                    body = stripped
            key = (sp, wk, title_key(title, did))
            if key in seen:
                st["dup"] += 1
                continue
            seen.add(key)
            denom[(sp, wk)] += 1
            txt = (title or "") + "\n" + body
            for k, rx, anchors in terms:
                for a in anchors:
                    if a in txt:
                        if rx.search(txt):
                            hits[(k, sp, wk)] += 1
                        break
    st["kept"] = sum(denom.values())
    return hits, denom, dict(st)


def rows_from(hits, denom):
    out = [(c, sp, wk, n, denom[(sp, wk)]) for (c, sp, wk), n in hits.items()]
    out += [(ALL, sp, wk, n, n) for (sp, wk), n in denom.items()]
    return sorted(out)


def write(out_path, rows, since_week=None):
    """One short transaction: (re)create, delete the rebuilt range, insert."""
    conn = sqlite3.connect(str(out_path), timeout=30)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        conn.executescript(DDL)
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM discourse_concepts")
        conn.executemany(
            "INSERT INTO discourse_concepts(concept, label_en, family, pattern) VALUES (?,?,?,?)",
            [(k, en, fam, pat) for k, (pat, en, fam, _a) in all_terms().items()])
        if since_week:
            conn.execute("DELETE FROM discourse_weekly WHERE iso_week >= ?", (since_week,))
        else:
            conn.execute("DELETE FROM discourse_weekly")
        conn.executemany(
            "INSERT INTO discourse_weekly(concept, speaker, iso_week, docs, denom) VALUES (?,?,?,?,?)",
            rows)
        conn.commit()
        n = conn.execute("SELECT COUNT(*) FROM discourse_weekly").fetchone()[0]
        return n
    finally:
        conn.close()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(DEFAULT_DB), help="source corpus (opened read-only)")
    ap.add_argument("--out", default=None, help="write the tables here instead of --db")
    ap.add_argument("--from", dest="date_lo", default=DATE_LO, help=f"earliest date (default {DATE_LO})")
    ap.add_argument("--since", default=None,
                    help="YYYY-MM-DD: rebuild only the ISO weeks from that date's week on")
    ap.add_argument("--dry-run", action="store_true", help="compute and print; write nothing")
    a = ap.parse_args(argv)

    since_week = None
    date_lo = a.date_lo
    if a.since:
        d = date.fromisoformat(a.since)          # refuses a typo loudly
        mon = week_monday(d)
        since_week = iso_week(mon.isoformat())
        date_lo = max(date_lo, mon.isoformat())

    t0 = time.time()
    src = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    try:
        hits, denom, st = compute(src, date_lo=date_lo)
    finally:
        src.close()
    t_scan = time.time() - t0
    rows = rows_from(hits, denom)
    print(f"scanned {st.get('scanned', 0):,} docs from {date_lo}: kept {st.get('kept', 0):,} "
          f"(dup {st.get('dup', 0):,}, no speaker {st.get('no_speaker', 0):,}, "
          f"bad date {st.get('bad_date', 0):,}, chrome stripped {st.get('chrome_stripped', 0):,} "
          f"of which chrome-only {st.get('chrome_only', 0):,}) in {t_scan:.1f}s; {len(rows):,} rows "
          f"({sum(1 for r in rows if r[0] != ALL):,} concept cells)", flush=True)
    if a.dry_run:
        tot = Counter()
        for (c, _sp, _wk), n in hits.items():
            tot[c] += n
        for c, n in tot.most_common():
            print(f"  {c:<16} {n:>7,}")
        return 0
    t1 = time.time()
    n = write(a.out or a.db, rows, since_week)
    print(f"wrote {len(rows):,} rows to {a.out or a.db} "
          f"({'weeks >= ' + since_week if since_week else 'full rebuild'}); "
          f"table now {n:,} rows; write {time.time() - t1:.1f}s, total {time.time() - t0:.1f}s",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
