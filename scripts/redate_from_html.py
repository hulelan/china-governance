"""
Re-derive `date_published` from saved raw HTML — no network, no re-crawl.

WHY. `crawlers/govcms.py` dates an article from, in order, the list row (a 240-char
`_DATE_NEAR` lookback around the link), the URL path, and the article body. Two shapes
slipped through: (1) the list-row lookback can bleed the NEIGHBOURING row's date (江苏民政厅
mzt.jiangsu.gov.cn: 98/417 docs stored a day late), and (2) the CMS's own
`<meta name="PubDate">` stamp was missed when single-quoted (南京江宁区 jiangning.gov.cn:
`content='2026-08-07 16:47'`). govcms now treats the article's PubDate meta as authoritative
at crawl time; this script applies the same rule to documents ALREADY on disk.

RULES (conservative — a stored date is only ever replaced by a BETTER one):
  * `<meta PubDate>` present  → it wins; UPDATE when it differs from the stored date.
  * no meta, stored date EMPTY → fill from the label-anchored body scan (govcms._body_date).
  * no meta, stored date set   → leave it (the label scan is a heuristic, not an upgrade).
  * never writes an empty date; never touches rows whose raw HTML file is missing.

Usage (repo root; the DB is the droplet's documents.db):
    python3 scripts/redate_from_html.py --site js_mzt --dry-run    # report only
    python3 scripts/redate_from_html.py --site js_mzt              # write
    python3 scripts/redate_from_html.py --site a --site b           # several sites
Only `date_published` is written, in 500-row batches, busy_timeout 30s. The write is a
plain UPDATE on a short column, so unlike compute_scores' whole-row rewrites it leaves
the body overflow pages alone. Follow with `scripts/build_doc_identity.py --force` so
`doc_identity.date_quality` reflects the new dates.
"""
import argparse
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from crawlers.govcms import _body_date, _meta_date  # noqa: E402

DB_PATH = ROOT / "documents.db"


def redate(conn, site_key, dry_run=False, verbose=False):
    rows = conn.execute(
        """SELECT id, date_published, raw_html_path FROM documents
           WHERE site_key = ? AND raw_html_path IS NOT NULL AND raw_html_path != ''
           ORDER BY id""", (site_key,)).fetchall()
    stats = Counter()
    updates = []  # (new_date, id)
    shift = Counter()  # new-vs-old day delta, for the report
    for doc_id, old, raw_path in rows:
        p = ROOT / raw_path
        if not p.exists():
            stats["no_html"] += 1
            continue
        html = p.read_text(errors="replace")
        meta = _meta_date(html)
        if meta:
            if meta == old:
                stats["meta_same"] += 1
            else:
                stats["meta_fix" if old else "meta_fill"] += 1
                updates.append((meta, doc_id))
                if old and len(old) == 10 and len(meta) == 10:
                    try:
                        from datetime import date
                        d_old = date.fromisoformat(old)
                        d_new = date.fromisoformat(meta)
                        shift[(d_new - d_old).days] += 1
                    except ValueError:
                        pass
                if verbose:
                    print(f"  {doc_id} {old!r} -> {meta!r} (meta)")
            continue
        if old:
            stats["kept_no_meta"] += 1
            continue
        body = _body_date(html)
        if body:
            stats["body_fill"] += 1
            updates.append((body, doc_id))
            if verbose:
                print(f"  {doc_id} '' -> {body!r} (body label)")
        else:
            stats["still_empty"] += 1

    print(f"[{site_key}] {len(rows)} docs with raw HTML: "
          + ", ".join(f"{k}={v}" for k, v in sorted(stats.items())))
    if shift:
        print(f"  day shift of meta fixes (new - old): "
              + ", ".join(f"{d:+d}d×{n}" for d, n in sorted(shift.items())))
    if dry_run or not updates:
        print(f"  {'would update' if dry_run else 'updated'} {len(updates)} rows")
        return len(updates)
    for i in range(0, len(updates), 500):
        conn.executemany("UPDATE documents SET date_published = ? WHERE id = ?",
                         updates[i:i + 500])
        conn.commit()
    print(f"  updated {len(updates)} rows")
    return len(updates)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--site", action="append", required=True,
                    help="site_key to redate (repeatable)")
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--dry-run", action="store_true", help="report, write nothing")
    ap.add_argument("--verbose", action="store_true", help="print every change")
    args = ap.parse_args(argv)
    uri = f"file:{args.db}?mode=ro" if args.dry_run else args.db
    conn = sqlite3.connect(uri, uri=args.dry_run, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    total = 0
    for site in args.site:
        total += redate(conn, site, dry_run=args.dry_run, verbose=args.verbose)
    conn.close()
    print(f"total {'candidate' if args.dry_run else 'updated'} rows: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
