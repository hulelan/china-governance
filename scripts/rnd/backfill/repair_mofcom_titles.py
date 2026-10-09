"""Recover the 725 mofcom export-control titles the LISTING endpoint served as "?".

Found 2026-10-09 while building the export-control regime series. Every CJK
character in these titles is a literal ASCII 0x3f. They are NOT U+FFFD, so this is
not our `errors="replace"` decoding (that is a real but separate hazard at
crawlers/mofcom.py:403/608 and crawlers/base.py:718) — the article LISTING endpoint
serves the field that way. The ARTICLE page is clean: it carries the real title in a
JS variable that `crawlers.mofcom._extract_ec_meta` already parses, which is why the
bodies are intact (724 of 725 have a body, 0 of them mojibake).

Why it matters beyond hygiene: a mojibake title is invisible to BOTH FTS indexes,
can never be a citation target, and can never match a `title_reissue` diffusion
edge. mofcom holds 500 of the 1,071 出口管制 documents, so the ministry that owns the
export-control regime has 725 documents unreachable in every title-keyed analysis.
The documents themselves are the regime's justification record — spokesperson Q&A
naming counterparties and dates (UK sanctions, Japan dual-use controls, the
安世半导体 / Nexperia consultations with the Netherlands).

`raw_html_path` is a DANGLING POINTER for all 725 (it names raw_html/mofcom/2278.html
while that directory stores files by doc id), so there is nothing on disk to re-parse
and the URL must be re-fetched. One HTTP request per row, so this follows the
CLAUDE.md rule for loops that write rows they paid network time for:
write_with_retry, incremental commits, non-zero exit when anything was skipped.

Safety: only rows whose CURRENT title is mojibake are touched, and a replacement is
written only if it contains CJK and no 3+ run of "?".

  python3 scripts/rnd/backfill/repair_mofcom_titles.py --dry-run --limit 5
  python3 scripts/rnd/backfill/repair_mofcom_titles.py
"""
from __future__ import annotations

import argparse
import logging
import re
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from crawlers import base                                    # noqa: E402
from crawlers.mofcom import _extract_ec_meta                 # noqa: E402

log = logging.getLogger("repair_mofcom_titles")

MOJIBAKE = re.compile(r"\?{3,}")
CJK = re.compile(r"[一-鿿]")
# 'var publishTime' looks like '2026-03-02 08:45:07'
PUBTIME = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def _epoch(pub: str):
    """publishTime -> a UTC midnight epoch, or None. Date only; the clock time on
    these pages is a CMS publish stamp, not an issuance time."""
    m = PUBTIME.match(pub or "")
    if not m:
        return None
    y, mo, d = (int(x) for x in m.groups())
    if not (1990 <= y <= 2030 and 1 <= mo <= 12 and 1 <= d <= 31):
        return None
    import calendar
    return calendar.timegm((y, mo, d, 0, 0, 0, 0, 0, 0))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(ROOT / "documents.db"))
    ap.add_argument("--limit", type=int)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sleep", type=float, default=0.4, help="politeness delay per fetch")
    ap.add_argument("--commit-every", type=int, default=25)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    uri = f"file:{args.db}?mode=ro" if args.dry_run else f"file:{args.db}"
    conn = sqlite3.connect(uri, uri=True, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")

    rows = conn.execute(
        "SELECT id, url, title, COALESCE(date_written, 0) FROM documents "
        "WHERE site_key = 'mofcom' AND title LIKE '%???%' AND url != '' "
        "ORDER BY id" + (f" LIMIT {int(args.limit)}" if args.limit else "")
    ).fetchall()
    log.info("%d mojibake-titled mofcom rows to repair%s",
             len(rows), " (DRY RUN)" if args.dry_run else "")

    stats = base.WriteRetryStats()
    fixed = dated = no_title = failed = 0
    for n, (doc_id, url, old, old_date) in enumerate(rows, 1):
        try:
            html = base.fetch(url, timeout=25)
        except Exception as e:                                # noqa: BLE001
            log.warning("id=%s FETCH FAILED %s: %s", doc_id, type(e).__name__, e)
            failed += 1
            continue
        meta = _extract_ec_meta(html)
        new = (meta.get("title") or "").strip()
        if not new or MOJIBAKE.search(new) or not CJK.search(new):
            log.warning("id=%s no usable title recovered (got %r)", doc_id, new[:40])
            no_title += 1
            continue

        epoch = _epoch(meta.get("publishTime", "")) if not old_date else None
        if args.dry_run:
            log.info("id=%s\n    old=%r\n    new=%r%s", doc_id, old[:36], new[:64],
                     f"\n    date=<-{meta.get('publishTime')}" if epoch else "")
            fixed += 1
            if epoch:
                dated += 1
        else:
            if epoch:
                ok = base.write_with_retry(
                    conn, "UPDATE documents SET title=?, date_written=? WHERE id=?",
                    (new, epoch, doc_id), stats=stats, what=f"title+date id={doc_id}")
                dated += bool(ok)
            else:
                ok = base.write_with_retry(
                    conn, "UPDATE documents SET title=? WHERE id=?",
                    (new, doc_id), stats=stats, what=f"title id={doc_id}")
            fixed += bool(ok)
            if n % args.commit_every == 0:
                base.commit_with_retry(conn, stats=stats)
                log.info("  ... %d/%d (fixed %d, dated %d)", n, len(rows), fixed, dated)
        time.sleep(args.sleep)

    if not args.dry_run:
        base.commit_with_retry(conn, stats=stats)
    conn.close()

    log.info("titles recovered: %d | dates filled: %d | no title: %d | fetch failed: %d"
             " | write-skipped: %d", fixed, dated, no_title, failed, stats.skipped)
    # Non-zero if anything was lost, so a wrapper `for` loop cannot swallow it.
    return 1 if (stats.skipped or failed or no_title) else 0


if __name__ == "__main__":
    sys.exit(main())
