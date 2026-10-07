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

PER-SITE EXTRACTORS (the A7 pattern from backfill_from_html.py: site_key -> crawler module).
`SITE_DATERS` routes a site to its crawler's own page-date function when the generic govcms
PubDate rule is WRONG for that CMS. First member — `suzhou` (crawlers.suzhou.page_date):
Suzhou's `<meta PubDate>` is the page-REGENERATION time (2023-02-09 / 2025-02-11 on 68% of the
site), so the govcms rule would re-apply the stamp. Suzhou rules:
  * page date (article-attr 时间 PUBLISHTIME, or a PubDate meta agreeing with the URL month)
    wins when present and different from the stored date;
  * no page date (raw HTML missing on the droplet for 3,820/4,918 Suzhou docs — the files
    were never copied from the Mac) → URL `/YYYYMM/` fallback, day 01, MONTH precision —
    applied ONLY when the stored date is NOT already inside the URL month (a stored date
    inside the URL month is day-precision and consistent; the 1st would be a downgrade).
The per-site line reports page_fix / url_fix / kept_in_url_month / no_html counts.

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

# site_key -> (module, page-date function name, url-month function name). The function
# takes (html, url) and returns (YYYY-MM-DD, source) with source in {'attr','meta','url',''}.
SITE_DATERS = {
    "suzhou": ("crawlers.suzhou", "page_date", "url_month"),
}


def _day_shift(shift, old, new):
    if old and len(old) == 10 and len(new) == 10:
        try:
            from datetime import date
            shift[(date.fromisoformat(new) - date.fromisoformat(old)).days] += 1
        except ValueError:
            pass


def redate_site_dater(conn, site_key, dry_run=False, verbose=False):
    """Per-site route: the crawler's own page_date(html, url), URL-month fallback when the
    page is absent/dateless AND the stored date is outside the URL month. Walks ALL docs of
    the site (not only those with raw HTML) because the URL fallback needs no file."""
    import importlib
    mod_name, fn_name, um_name = SITE_DATERS[site_key]
    mod = importlib.import_module(mod_name)
    page_date, url_month = getattr(mod, fn_name), getattr(mod, um_name)
    rows = conn.execute(
        """SELECT id, date_published, raw_html_path, url FROM documents
           WHERE site_key = ? ORDER BY id""", (site_key,)).fetchall()
    stats = Counter()
    updates = []
    shift = Counter()
    for doc_id, old, raw_path, url in rows:
        old = old or ""
        html = ""
        if raw_path:
            p = ROOT / raw_path
            if p.exists():
                html = p.read_text(errors="replace")
            else:
                stats["no_html"] += 1
        new, src = page_date(html, url) if html else ("", "")
        if new and src != "url":
            if new == old:
                stats["page_same"] += 1
            else:
                stats["page_fix" if old else "page_fill"] += 1
                updates.append((new, doc_id))
                _day_shift(shift, old, new)
                if verbose:
                    print(f"  {doc_id} {old!r} -> {new!r} ({src})")
            continue
        um = url_month(url)
        if not um:
            stats["no_url_month"] += 1
            continue
        if old[:7] == um:
            stats["kept_in_url_month"] += 1
            continue
        new = f"{um}-01"
        stats["url_fix" if old else "url_fill"] += 1
        updates.append((new, doc_id))
        _day_shift(shift, old, new)
        if verbose:
            print(f"  {doc_id} {old!r} -> {new!r} (url month)")
    print(f"[{site_key}] {len(rows)} docs (site dater {mod_name}.{fn_name}): "
          + ", ".join(f"{k}={v}" for k, v in sorted(stats.items())))
    if shift:
        big = sum(n for d, n in shift.items() if abs(d) > 60)
        print(f"  {sum(shift.values())} shifted; {big} by >60 days; "
              f"median shift {sorted(d for d, n in shift.items() for _ in range(n))[sum(shift.values()) // 2]:+d}d")
    return _apply(conn, updates, dry_run)


def _apply(conn, updates, dry_run):
    if dry_run or not updates:
        print(f"  {'would update' if dry_run else 'updated'} {len(updates)} rows")
        return len(updates)
    for i in range(0, len(updates), 500):
        conn.executemany("UPDATE documents SET date_published = ? WHERE id = ?",
                         updates[i:i + 500])
        conn.commit()
    print(f"  updated {len(updates)} rows")
    return len(updates)


def redate(conn, site_key, dry_run=False, verbose=False):
    if site_key in SITE_DATERS:
        return redate_site_dater(conn, site_key, dry_run, verbose)
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
    return _apply(conn, updates, dry_run)


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
