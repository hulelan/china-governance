#!/usr/bin/env python3
"""Inspect, seed and re-queue the body-fetch ledger (`body_fetch_failures`).

WHY THIS EXISTS. Every crawler in `crawlers/` skips a document only when it is
"already stored WITH a body" (`if existing and existing[1]`), so a row that is
stored but BODILESS is re-fetched every night, forever, and the HTTP fetch is
paid before the extraction fails. `crawlers/base.py`'s body ledger lets a
crawler stop paying for a row that has already failed `BODY_MAX_ATTEMPTS` times.

That is a deliberate trade of COMPLETENESS for TIME on rows that are currently
unobtainable. The ledger is what makes the trade REVERSIBLE: no row is silently
abandoned, because every skipped row keeps an entry here naming WHY it was
skipped, so a new fetch vantage, a fixed extractor or a site that comes back can
re-queue exactly the affected class in one command.

Reason classes, and which are genuinely terminal:

    image_only       TERMINAL anywhere. The document's body IS an image
                     (一图读懂 / 图解 / 视频). No HTTP GET will ever return text;
                     the recovery path is OCR. 86.4% of the 1,636 bodiless `bj`
                     rows are this.
    pdf_only         TERMINAL anywhere for this mechanism. The payload is a
                     PDF/DOC; `scripts/extract_pdf_text.py` owns it.
    anti_bot_stub    TERMINAL FROM NYC ONLY — "not yet" from anywhere else. The
                     server answers with a refusal page (MIIT returns 42 bytes
                     of "信息模板页面配置实体不能为空" to the droplet; 3,841 of its
                     saved files are exactly that). A residential or HK vantage
                     is the fix, which is why this class is kept separate:
                         python3 scripts/body_ledger.py --requeue anti_bot_stub
                     from that vantage re-opens every one of them.
    empty_extraction "Not yet". A real page our extractor cannot parse. The fix
                     is an extractor change plus `backfill_from_html.py`, which
                     reads SAVED HTML and is NOT gated by this ledger — so this
                     class keeps recovering with no re-fetch at all.
    html_missing     "Not yet". Nothing was saved; only a re-fetch can help.
    http_error       "Not yet". The fetch failed outright; the site may be back.

Usage:
    python3 scripts/body_ledger.py --init-schema
    python3 scripts/body_ledger.py --stats
    python3 scripts/body_ledger.py --stats --site bj
    python3 scripts/body_ledger.py --seed --dry-run
    python3 scripts/body_ledger.py --seed --site bj
    python3 scripts/body_ledger.py --requeue anti_bot_stub
    python3 scripts/body_ledger.py --requeue image_only --site bj

`--seed` exists because the attempt counter can otherwise never build up for the
rows that cost the most: `beijing` is killed at 2,640/6,821 items every night,
so rows past the kill point are never even reached, let alone attempted. Seeding
turns the measurement already on disk (saved-HTML size, title shape, URL suffix)
into ledger rows in one pass with NO network. It seeds at the attempt cap only
for the classes where a re-fetch provably cannot help (image_only, pdf_only,
anti_bot_stub, empty_extraction) and at attempts=0 for `html_missing`, which
genuinely needs a re-fetch and must stay eligible.
"""
import argparse
import os
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crawlers.base import (  # noqa: E402
    BODY_GRAPHIC_TITLE,
    BODY_MAX_ATTEMPTS,
    BODY_REASONS,
    BODY_STUB_MAX_BYTES,
    BODY_TERMINAL_REASONS,
    BODY_VANTAGE_REASONS,
    ensure_body_ledger,
)

DB_PATH = ROOT / "documents.db"

# A re-fetch from this vantage provably cannot help these, so seed them capped.
SEED_CAPPED = ("image_only", "pdf_only", "anti_bot_stub", "empty_extraction")

# Sites that are bodiless BY DESIGN, so a ledger row for them is pure noise.
# `crawlers/npc.py` stores `body_text_cn: ""` with the comment "Body requires
# Chinese IP access" — it never attempts a body, so its 31,070 bodiless rows are
# not a re-fetch cost and must not be seeded (they would be 61% of the ledger).
# Override with `--include-design-bodiless` if that ever changes.
SEED_SKIP_SITES = ("npc",)

_BINARY_SUFFIXES = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx")


def _connect(read_only: bool):
    if read_only:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=30)
        conn.execute("PRAGMA query_only=1")
    else:
        conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def cmd_stats(site: str = None):
    conn = _connect(read_only=True)
    try:
        where, params = "", []
        if site:
            where, params = " WHERE site_key = ?", [site]
        rows = conn.execute(
            f"""SELECT reason, COUNT(*), SUM(attempts >= {BODY_MAX_ATTEMPTS}),
                       MIN(first_seen), MAX(last_seen)
                FROM body_fetch_failures{where}
                GROUP BY reason ORDER BY COUNT(*) DESC""", params).fetchall()
    except sqlite3.OperationalError as e:
        print(f"body_fetch_failures not present ({e}). "
              f"Run: python3 scripts/body_ledger.py --init-schema")
        return 1
    if not rows:
        print("ledger is empty" + (f" for site={site}" if site else ""))
        return 0
    print(f"{'reason':18s} {'rows':>8s} {'capped':>8s}  {'kind':16s} "
          f"{'first_seen':20s} {'last_seen':20s}")
    for reason, n, capped, first, last in rows:
        if reason in BODY_TERMINAL_REASONS:
            kind = "terminal"
        elif reason in BODY_VANTAGE_REASONS:
            kind = "vantage-blocked"
        else:
            kind = "not yet"
        print(f"{reason:18s} {n:8,d} {capped or 0:8,d}  {kind:16s} "
              f"{(first or ''):20.19s} {(last or ''):20.19s}")
    print()
    per_site = conn.execute(
        f"""SELECT site_key, COUNT(*) FROM body_fetch_failures{where}
            GROUP BY site_key ORDER BY COUNT(*) DESC LIMIT 20""", params).fetchall()
    print("top sites:", ", ".join(f"{s}={n:,}" for s, n in per_site))
    total = conn.execute(
        f"SELECT COUNT(*) FROM body_fetch_failures{where}", params).fetchone()[0]
    print(f"TOTAL ledger rows: {total:,}")
    return 0


def _classify_from_disk(raw_path: str, title: str, url: str) -> str:
    """Classify a bodiless row from what is already on disk. No network."""
    if url and url.split("?")[0].lower().endswith(_BINARY_SUFFIXES):
        return "pdf_only"
    if not raw_path:
        return "html_missing"
    fp = ROOT / raw_path
    try:
        size = os.path.getsize(fp)
    except OSError:
        return "html_missing"
    if size <= BODY_STUB_MAX_BYTES:
        try:
            head = fp.open("r", errors="replace").read(2048).strip().lower()
        except OSError:
            head = ""
        if "<html" not in head:
            return "anti_bot_stub"
    if title and BODY_GRAPHIC_TITLE.search(title):
        return "image_only"
    return "empty_extraction"


def cmd_seed(site: str = None, dry_run: bool = False, attempts: int = None,
             limit: int = 0, include_design_bodiless: bool = False):
    attempts = BODY_MAX_ATTEMPTS if attempts is None else attempts
    conn = _connect(read_only=dry_run)
    if not dry_run:
        ensure_body_ledger(conn)
    q = """SELECT id, site_key, COALESCE(raw_html_path, ''), title,
                  COALESCE(url, '')
           FROM documents
           WHERE (body_text_cn IS NULL OR LENGTH(body_text_cn) = 0)"""
    params = []
    if site:
        q += " AND site_key = ?"
        params.append(site)
    elif not include_design_bodiless and SEED_SKIP_SITES:
        q += f" AND site_key NOT IN ({','.join('?' * len(SEED_SKIP_SITES))})"
        params.extend(SEED_SKIP_SITES)
        print(f"(skipping bodiless-by-design sites: "
              f"{', '.join(SEED_SKIP_SITES)} — pass --include-design-bodiless "
              f"to seed them anyway)")
    q += " ORDER BY site_key, id"
    if limit:
        q += f" LIMIT {int(limit)}"

    tally, seeded = Counter(), Counter()
    n = 0
    for doc_id, site_key, raw_path, title, url in conn.execute(q, params):
        reason = _classify_from_disk(raw_path, title or "", url)
        tally[reason] += 1
        att = attempts if reason in SEED_CAPPED else 0
        if dry_run:
            continue
        conn.execute(
            """INSERT INTO body_fetch_failures
                   (doc_id, site_key, reason, attempts, first_seen, last_seen)
               VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
               ON CONFLICT(doc_id) DO UPDATE SET
                   reason   = excluded.reason,
                   site_key = excluded.site_key,
                   attempts = MAX(body_fetch_failures.attempts, excluded.attempts),
                   last_seen = excluded.last_seen""",
            (doc_id, site_key, reason, att))
        seeded[reason] += 1
        n += 1
        if n % 5000 == 0:
            conn.commit()
            print(f"  …{n:,} seeded")
    if not dry_run:
        conn.commit()
    print(("DRY RUN — would seed" if dry_run else "seeded") + ":")
    for reason, c in tally.most_common():
        capped = "capped" if reason in SEED_CAPPED else f"attempts=0 (stays eligible)"
        print(f"  {reason:18s} {c:7,d}  {capped}")
    print(f"  {'TOTAL':18s} {sum(tally.values()):7,d}")
    return 0


def cmd_requeue(reason: str, site: str = None, dry_run: bool = False):
    if reason != "all" and reason not in BODY_REASONS:
        print(f"unknown reason {reason!r}; expected one of "
              f"{', '.join(BODY_REASONS)} (or 'all')")
        return 2
    conn = _connect(read_only=dry_run)
    where, params = [], []
    if reason != "all":
        where.append("reason = ?")
        params.append(reason)
    if site:
        where.append("site_key = ?")
        params.append(site)
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    n = conn.execute(
        f"SELECT COUNT(*) FROM body_fetch_failures{clause}", params).fetchone()[0]
    if dry_run:
        print(f"DRY RUN — would re-queue {n:,} rows (reason={reason}, "
              f"site={site or 'all'})")
        return 0
    conn.execute(f"DELETE FROM body_fetch_failures{clause}", params)
    conn.commit()
    print(f"re-queued {n:,} rows (reason={reason}, site={site or 'all'}) — the "
          f"next crawl of those sites will fetch their bodies again")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="Inspect / seed / re-queue the body-fetch ledger",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    ap.add_argument("--init-schema", action="store_true",
                    help="Create body_fetch_failures and exit")
    ap.add_argument("--stats", action="store_true",
                    help="Counts by reason and by site")
    ap.add_argument("--seed", action="store_true",
                    help="Classify today's bodiless rows from saved HTML (no "
                         "network) and write ledger rows")
    ap.add_argument("--requeue", metavar="REASON",
                    help=f"Delete ledger rows of this reason so they are "
                         f"retried as first-timers. One of "
                         f"{', '.join(BODY_REASONS)}, or 'all'")
    ap.add_argument("--site", help="Restrict to one site_key")
    ap.add_argument("--seed-attempts", type=int, default=None,
                    help=f"Attempts to seed capped classes with "
                         f"(default {BODY_MAX_ATTEMPTS})")
    ap.add_argument("--limit", type=int, default=0, help="Cap rows scanned by --seed")
    ap.add_argument("--include-design-bodiless", action="store_true",
                    help=f"Also seed sites that are bodiless by design "
                         f"({', '.join(SEED_SKIP_SITES)})")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print what would change; opens the DB read-only")
    args = ap.parse_args()

    if args.init_schema:
        conn = _connect(read_only=False)
        ensure_body_ledger(conn)
        conn.commit()
        conn.close()
        print("Schema ready: body_fetch_failures (+ reason/site indexes)")
        return 0
    if args.seed:
        return cmd_seed(args.site, args.dry_run, args.seed_attempts, args.limit,
                        args.include_design_bodiless)
    if args.requeue:
        return cmd_requeue(args.requeue, args.site, args.dry_run)
    return cmd_stats(args.site)      # --stats is the default action


if __name__ == "__main__":
    sys.exit(main())
