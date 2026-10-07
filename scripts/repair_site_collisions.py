#!/usr/bin/env python3
"""Repair the rows already corrupted by the cross-site id-collision upsert.

BACKGROUND (docs/working/qa-gkmlpt-sync-diff.md, commit 5d872b2)
----------------------------------------------------------------
`store_gkmlpt_document` and `base.store_document` upserted
`ON CONFLICT(id) DO UPDATE SET body_text_cn=..., raw_html_path=...` WITHOUT
checking `site_key`. gkmlpt post ids are one platform-wide namespace that also
overlaps the synthetic ids other crawlers assign, so a post appearing in a
second site's feed looked NEW to that site and overwrote the body of the row
owned by a DIFFERENT site, keeping the original `site_key`. The hole is closed
going forward (both stores now carry `WHERE documents.site_key =
excluded.site_key`). This script repairs the damage already in the corpus.

THE FOOTPRINT PREDICATE
-----------------------
`save_raw_html` (crawlers/base.py) is unconditionally
`raw_html/<site_key>/<id>.html`, for EVERY crawler. So a row whose saved HTML
sits in another site's directory is a row some other site's crawler wrote:

    raw_html_path != '' AND instr(raw_html_path, '/'||site_key||'/') = 0

261 rows corpus-wide. The predicate is on `raw_html_path`, NOT on `url` — which
matters, because `ifeng`, `sz_invest`, `mof`, `mofcom` and `stic` legitimately
span several hosts, and gkmlpt list items legitimately store outbound `url`s to
gov.cn / mp.weixin.qq.com / Xinhua. Those are URL facts and never trip this
predicate.

NOT EVERY MATCH IS CORRUPT — the url-identity exception
-------------------------------------------------------
`crawlers/gov.py` (lines 150 and 428) resolves a document id by URL first:

    SELECT id, body_text_cn FROM documents WHERE url = ? AND url != ''
    doc_id = existing[0] if existing else next_id(conn)

So when a gkmlpt district row is a pointer at a www.gov.cn article, the `gov`
crawler ADOPTS that row's id and writes the correct text for that URL, under
`raw_html/gov/<id>.html`. 21 rows are this case, and their body demonstrably
matches their title (verified by hand: `szpsq` 国务院办公厅关于印发2020年政务公开
工作要点的通知 etc.). Clearing them would destroy correct content, so they are
KEPT and only recorded. The discriminator: the clobbering directory's crawler
legitimately owns the row's `url` host (HOST_OWNER below).

The other 240 rows are true clobbers; their body is plainly another
jurisdiction's text (`heyuan` 李克强 title with a 揭阳市 body, `gov` 国务院 titles
with 深圳市 district notices, `stic` 深圳科创委预算 with a 广州市 body).

REPAIR = CLEAR, never "write a guessed body"
--------------------------------------------
The foreign body and the foreign path are deleted; `title`, `url`,
`date_published`, `document_number` and every other field are left ALONE (they
were never clobbered — the upsert only set body/path/crawl_timestamp). Clearing
is also what makes the body come BACK: crawlers key their "do we already have
this?" test on an EMPTY body (e.g. gov.py `if existing and existing[1]:
continue`), and `gkmlpt.backfill_bodies` selects `WHERE body_text_cn = ''`. So a
cleared row is re-fetched by its own owner on the next crawl. Per-row route:

  clear-by-design      `npc` (81). The national-laws crawler stores metadata
                       ONLY — crawlers/npc.py:269 `"body_text_cn": ""` with the
                       comment "Body requires Chinese IP access", and 30,989 of
                       its 31,070 rows have both body and path empty. Its native
                       state IS empty; there is no body to re-fetch from NYC.
  clear+gkmlpt-backfill gkmlpt-platform urls (31) — refilled by
                       `gkmlpt --backfill-bodies --site <k>`, whose WHERE clause
                       is `body_text_cn = '' AND url LIKE '%gkmlpt%'`.
  clear+owner-recrawl  the owning crawler reaches the url from NYC (125).
  clear-link-stub      the url host is foreign to the owner (3 `heyuan` rows
                       pointing at www.gov.cn). These are list-item stubs;
                       `backfill_bodies` deliberately skips non-gkmlpt urls, so
                       an empty body is their honest native state.
  keep                 url-identity (21) — body is correct, nothing written.

Rows whose owner cannot be reached from the droplet's NYC IP are additionally
FLAGGED (still cleared — a foreign body is worse than an empty one).

SAFETY
------
* Refuses to write while the nightly lock dir exists, unless --force.
* --dry-run opens the DB read-only (?mode=ro) and writes nothing.
* Batched commits + periodic PASSIVE checkpoint + a final TRUNCATE. An UPDATE
  that touches `body_text_cn` rewrites the row's overflow pages, so doing 261 of
  them in ONE transaction is the compute_scores.py mistake (a 5GB WAL the app's
  reader pins). See CLAUDE.md "Known Issues".
* Idempotent: clearing sets raw_html_path='', so the predicate no longer selects
  the row and a second run finds nothing to do. KEEP rows stay selected forever
  and upsert their audit row rather than duplicating it.
* Files under raw_html/ are NOT touched (the saved HTML belongs to the crawler
  that wrote it, and for the url-identity rows it is the right document).
* Every action is recorded in `collision_repairs(doc_id, old_site_dir, action,
  when)` so the repair itself is auditable and reversible-by-recrawl.

Usage:
    python3 scripts/repair_site_collisions.py --dry-run     # plan only, read-only
    python3 scripts/repair_site_collisions.py --apply       # repair
    python3 scripts/repair_site_collisions.py --apply --force   # ignore the lock
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import urllib.parse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "documents.db"
LOCK_DIR = Path("/tmp/china-governance-daily-sync.lock.d")

# The footprint. `save_raw_html` is always raw_html/<site_key>/<id>.html, so a
# path that does not contain the owner's own directory was written by another
# site's crawler.
VICTIM_WHERE = (
    "raw_html_path != '' AND instr(raw_html_path, '/' || site_key || '/') = 0"
)

# Directories whose crawler legitimately owns a url host. When the clobbering
# directory is this host's real owner, the row is a URL-identity adoption
# (crawlers/gov.py resolves ids by url) and its body is CORRECT — keep it.
HOST_OWNER = {"www.gov.cn": "gov"}

# Owners whose pages the droplet's NYC IP cannot fetch. Still cleared, but
# flagged: a cleared row will not refill until a reachable vantage runs.
UNREACHABLE = {
    "zj": "zhejiang blocked from NYC (daily_sync.sh: weekly probe, 0 new rows/11 nights)",
}
# Reachability uncertain — one archive url timed out (45s) from NYC, but the
# crawler is still scheduled. Cleared and flagged for a look.
WATCH = {
    "cq": "www.cq.gov.cn connection timed out from NYC on probe; chongqing still runs weekly",
}

# Multi-label public suffixes, so tech.ifeng.com and www.ifeng.com compare equal
# while www.gov.cn and www.heyuan.gov.cn do not.
MULTI_SUFFIX = (".gov.cn", ".com.cn", ".org.cn", ".net.cn", ".edu.cn", ".ac.cn")

ACTION_KEEP = "keep_url_identity"
BATCH = 200          # commit every N updates
CHECKPOINT_EVERY = 5  # PASSIVE checkpoint every N batches


def etld1(host: str) -> str:
    """Registrable domain, treating gov.cn & friends as public suffixes."""
    host = (host or "").lower().strip()
    if not host:
        return ""
    want = 3 if host.endswith(MULTI_SUFFIX) else 2
    parts = host.split(".")
    return ".".join(parts[-want:]) if len(parts) >= want else host


def connect(db_path: Path, read_only: bool) -> sqlite3.Connection:
    if read_only:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=30)
    else:
        conn = sqlite3.connect(str(db_path), timeout=30, isolation_level=None)
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def site_domains(conn: sqlite3.Connection) -> dict:
    return {
        sk: etld1(urllib.parse.urlparse(base or "").netloc)
        for sk, base in conn.execute("SELECT site_key, base_url FROM sites")
    }


def foreign_dir(raw_html_path: str) -> str:
    """'raw_html/zjj/123.html' -> 'zjj'."""
    parts = (raw_html_path or "").split("/")
    return parts[1] if len(parts) >= 3 else ""


def classify(row: sqlite3.Row, domains: dict) -> tuple:
    """-> (action, route, flag). action is ACTION_KEEP or a 'clear_*' verb."""
    fdir = foreign_dir(row["raw_html_path"])
    host = urllib.parse.urlparse(row["url"] or "").netloc

    if HOST_OWNER.get(host) == fdir and fdir:
        # The clobbering crawler is this url's real owner — it adopted the id by
        # url and wrote the CORRECT text. Never clear.
        return ACTION_KEEP, "keep (url-identity: body matches the url's owner)", ""

    site = row["site_key"]
    flag = UNREACHABLE.get(site) or WATCH.get(site) or ""
    if site == "npc":
        route = "clear (npc is metadata-only by design; no body exists to refetch)"
        action = "clear_by_design"
    elif "gkmlpt" in (row["url"] or ""):
        route = f"clear + gkmlpt --backfill-bodies --site {site}"
        action = "clear_gkmlpt_backfill"
    elif domains.get(site) and etld1(host) == domains[site]:
        route = f"clear + owner recrawl ({site})"
        action = "clear_owner_recrawl"
    else:
        route = "clear (list-item link stub; empty body is its native state)"
        action = "clear_link_stub"
    return action, route, flag


def ensure_audit_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS collision_repairs (
               doc_id        INTEGER PRIMARY KEY,
               old_site_dir  TEXT NOT NULL,
               action        TEXT NOT NULL,
               when_utc      TEXT NOT NULL,
               site_key      TEXT,
               old_body_len  INTEGER,
               old_path      TEXT,
               note          TEXT
           )"""
    )


def load_victims(conn: sqlite3.Connection) -> list:
    conn.row_factory = sqlite3.Row
    return conn.execute(
        f"""SELECT id, site_key, title, url, raw_html_path,
                   length(body_text_cn) AS body_len
              FROM documents
             WHERE {VICTIM_WHERE}
             ORDER BY site_key, id"""
    ).fetchall()


def print_plan(victims: list, plans: list) -> None:
    by_site = defaultdict(Counter)
    actions, flags = Counter(), {}
    for row, (action, route, flag) in zip(victims, plans):
        by_site[row["site_key"]][action] += 1
        actions[action] += 1
        if flag:
            flags[row["site_key"]] = flag

    print(f"\nFootprint: {len(victims)} rows match the collision predicate.\n")
    print(f"  {'site':<14} {'n':>4}  actions")
    for site in sorted(by_site, key=lambda s: (-sum(by_site[s].values()), s)):
        n = sum(by_site[site].values())
        detail = ", ".join(f"{a}={c}" for a, c in by_site[site].most_common())
        mark = "  ** FLAGGED" if site in flags else ""
        print(f"  {site:<14} {n:>4}  {detail}{mark}")

    print("\n  totals:")
    for action, n in actions.most_common():
        verb = "kept, nothing written" if action == ACTION_KEEP else "body+path cleared"
        print(f"    {n:>4}  {action:<24} ({verb})")
    cleared = sum(n for a, n in actions.items() if a != ACTION_KEEP)
    print(f"    {cleared:>4}  rows to clear; {actions[ACTION_KEEP]} to keep")

    if flags:
        print("\n  flagged owners (cleared, but will not refill from NYC):")
        for site, why in sorted(flags.items()):
            print(f"    {site}: {why}")

    print("\n  sample (first 20 rows):")
    print(f"  {'id':>10} {'site':<12} {'<-dir':<12} {'blen':>6}  action / title")
    for row, (action, _route, _flag) in list(zip(victims, plans))[:20]:
        title = (row["title"] or "")[:40].replace("\n", " ")
        print(
            f"  {row['id']:>10} {row['site_key']:<12} "
            f"{foreign_dir(row['raw_html_path']):<12} {row['body_len']:>6}  "
            f"{action}  {title}"
        )


def apply_repairs(conn: sqlite3.Connection, victims: list, plans: list) -> tuple:
    ensure_audit_table(conn)
    now = datetime.now(timezone.utc).isoformat()
    cleared = kept = 0
    pending = 0
    batches = 0

    conn.execute("BEGIN")
    for row, (action, route, flag) in zip(victims, plans):
        # Record every decision, keep or clear, so the repair is auditable.
        conn.execute(
            """INSERT INTO collision_repairs
                   (doc_id, old_site_dir, action, when_utc, site_key,
                    old_body_len, old_path, note)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(doc_id) DO UPDATE SET
                   old_site_dir=excluded.old_site_dir,
                   action=excluded.action,
                   when_utc=excluded.when_utc,
                   old_body_len=excluded.old_body_len,
                   old_path=excluded.old_path,
                   note=excluded.note""",
            (row["id"], foreign_dir(row["raw_html_path"]), action, now,
             row["site_key"], row["body_len"], row["raw_html_path"],
             (route + (f" | FLAG: {flag}" if flag else ""))),
        )
        if action == ACTION_KEEP:
            kept += 1
        else:
            # Clear ONLY the two clobbered columns. The site_key guard makes this
            # a no-op if ownership changed under us.
            conn.execute(
                """UPDATE documents
                      SET body_text_cn = '', raw_html_path = ''
                    WHERE id = ? AND site_key = ?""",
                (row["id"], row["site_key"]),
            )
            cleared += 1
        pending += 1

        if pending >= BATCH:
            conn.execute("COMMIT")
            pending = 0
            batches += 1
            if batches % CHECKPOINT_EVERY == 0:
                conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
            conn.execute("BEGIN")

    conn.execute("COMMIT")
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    return cleared, kept


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Repair rows clobbered by the cross-site id-collision upsert"
    )
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--dry-run", action="store_true",
                    help="read-only: print the plan and a 20-row sample, write nothing")
    ap.add_argument("--apply", action="store_true", help="perform the repair")
    ap.add_argument("--force", action="store_true",
                    help="write even if the nightly lock dir exists")
    args = ap.parse_args(argv)

    if args.apply == args.dry_run:
        ap.error("pass exactly one of --dry-run or --apply")

    if args.apply and LOCK_DIR.exists() and not args.force:
        print(f"nightly lock {LOCK_DIR} exists — refusing to write (use --force)",
              file=sys.stderr)
        return 2

    db = Path(args.db)
    if not db.exists():
        print(f"no such database: {db}", file=sys.stderr)
        return 2

    conn = connect(db, read_only=args.dry_run)
    try:
        domains = site_domains(conn)
        victims = load_victims(conn)
        plans = [classify(r, domains) for r in victims]
        print_plan(victims, plans)

        if args.dry_run:
            print("\n--dry-run: read-only connection, nothing written.")
            return 0

        if not victims:
            print("\nnothing to repair (already clean — the script is idempotent).")
            ensure_audit_table(conn)
            return 0

        cleared, kept = apply_repairs(conn, victims, plans)
        print(f"\nrepaired: cleared {cleared}, kept {kept}; "
              f"{cleared + kept} rows recorded in collision_repairs.")
        print("WAL checkpointed (TRUNCATE).")
        print("\nNext: re-derive the layers that read bodies — see "
              "docs/working/qa-collision-repair-plan.md")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
