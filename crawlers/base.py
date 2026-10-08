"""Shared crawler utilities: database, HTTP, storage.

Every crawler imports from here (fetch, init_db, next_id, save_raw_html, ...).
The cross-cutting gotchas below apply when writing or debugging ANY crawler —
they used to live scattered across SKILL.md / docs runbooks; consolidated here
(June 2026) so the rules sit next to the code they govern.

Crawler-authoring gotchas:
  • --section is single-valued: `--section A --section B` silently keeps only B
    (argparse `choices=` overwrites). Run one section per invocation.
  • Duplicate docs across machines: next_id() = MAX(id)+1 is computed locally, so
    two hosts assign different ids to the same URL. The partial UNIQUE index on
    `url` (WHERE url != '') + IntegrityError-skip on insert is what prevents dupes
    — don't remove it.
  • Partial-index gotcha: `idx_documents_url` is `WHERE url != ''`. SQLite won't
    use it unless the query ALSO says `AND url != ''`. Include that predicate or
    expect a full table scan.
  • Body extraction returns 0 → the CSS/id selector doesn't match this site's
    HTML. Verify with repr() of the RAW bytes from fetch(), never a WebFetch/AI
    summary (they mis-report <div> vs <p>, span-wrapped dates, etc.).
  • Regex hangs on big pages → re.DOTALL with `.*?` backtracks O(n²). Slice the
    target container out first, then run patterns on the smaller substring.
  • Old .gov.cn TLS: Python's ssl may reject the handshake (BAD_ECPOINT / rc=35).
    Shell out to `curl -sk` as a fallback (see sz_invest.py for the pattern).
  • Pagination is usually 0-indexed static HTML: page 0 = index.html, page 1 =
    index_1.html, ...  Normalize dates to YYYY-MM-DD — site formats vary.
"""

import json
import logging
import os
import re
import socket
import sqlite3
import time
import urllib.request
import urllib.error
import urllib.parse
import http.cookiejar
from datetime import datetime, timezone
from pathlib import Path

# Optional: curl_cffi gives a real Chrome TLS/JA3 fingerprint, which defeats the
# fingerprint-based WAFs (Knownsec/创宇盾) that 418-block urllib's ClientHello
# (e.g. ccg.gov.cn, and the "curl works / urllib fails" sites: 成都/南通/白银/阜阳).
# It's a FALLBACK only (see fetch()); absent (e.g. on the Mac) the code degrades to
# the urllib path unchanged.
try:
    from curl_cffi import requests as _cffi_requests
except ImportError:
    _cffi_requests = None

# Force IPv4 — many .gov.cn sites are unreachable over IPv6 from overseas servers.
# Exception: some sites (e.g., *.zj.gov.cn) are IPv6-only from the US and need
# the original getaddrinfo.  Crawlers that need IPv6 can call allow_ipv6().
_orig_getaddrinfo = socket.getaddrinfo

# Hosts that should bypass the IPv4 restriction (checked by suffix).
_IPV6_HOSTS: set[str] = set()

def _smart_getaddrinfo(host, port, family=0, *args, **kwargs):
    # If the host matches an IPv6-allowed suffix, use the original resolver
    if isinstance(host, str):
        for suffix in _IPV6_HOSTS:
            if host == suffix or host.endswith("." + suffix):
                return _orig_getaddrinfo(host, port, family, *args, **kwargs)
    return _orig_getaddrinfo(host, port, socket.AF_INET, *args, **kwargs)

socket.getaddrinfo = _smart_getaddrinfo


def allow_ipv6(*hosts: str):
    """Allow IPv6 resolution for the given host suffixes.

    Example: allow_ipv6("zj.gov.cn") lets *.zj.gov.cn resolve via IPv6.
    """
    _IPV6_HOSTS.update(hosts)

DB_PATH = Path(__file__).parent.parent / "documents.db"
RAW_HTML_DIR = Path(__file__).parent.parent / "raw_html"
REQUEST_DELAY = 0.5
USER_AGENT = "ChinaGovernanceCrawler/1.0 (Academic Research)"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# --- Database ---

def init_db(db_path: Path = None) -> sqlite3.Connection:
    if db_path is None:
        db_path = DB_PATH
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sites (
            site_key TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            base_url TEXT NOT NULL,
            admin_level TEXT,
            sid TEXT,
            tree_json TEXT,
            last_crawled TEXT
        );

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY,
            site_key TEXT NOT NULL,
            name TEXT NOT NULL,
            parent_id INTEGER,
            post_count INTEGER DEFAULT 0,
            FOREIGN KEY (site_key) REFERENCES sites(site_key)
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY,
            site_key TEXT NOT NULL,
            category_id INTEGER,
            title TEXT NOT NULL,
            document_number TEXT,
            identifier TEXT,
            publisher TEXT,
            keywords TEXT,
            date_written INTEGER,
            date_published TEXT,
            display_publish_time INTEGER,
            abstract TEXT,
            body_text_cn TEXT,
            body_text_en TEXT,
            classify_main_name TEXT,
            classify_genre_name TEXT,
            classify_theme_name TEXT,
            url TEXT,
            post_url TEXT,
            is_expired INTEGER DEFAULT 0,
            is_abolished INTEGER DEFAULT 0,
            attachments_json TEXT,
            relation TEXT,
            raw_html_path TEXT,
            crawl_timestamp TEXT NOT NULL,
            FOREIGN KEY (site_key) REFERENCES sites(site_key)
        );

        CREATE INDEX IF NOT EXISTS idx_documents_site ON documents(site_key);
        CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category_id);
        CREATE INDEX IF NOT EXISTS idx_documents_date ON documents(date_written);
        CREATE INDEX IF NOT EXISTS idx_documents_docnum ON documents(document_number);

        CREATE TABLE IF NOT EXISTS citations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            target_ref TEXT NOT NULL,
            target_id INTEGER,
            citation_type TEXT NOT NULL,
            source_level TEXT NOT NULL,
            target_level TEXT NOT NULL,
            FOREIGN KEY (source_id) REFERENCES documents(id),
            FOREIGN KEY (target_id) REFERENCES documents(id),
            UNIQUE(source_id, target_ref, citation_type)
        );

        CREATE INDEX IF NOT EXISTS idx_citations_source ON citations(source_id);
        CREATE INDEX IF NOT EXISTS idx_citations_target_id ON citations(target_id);
        CREATE INDEX IF NOT EXISTS idx_citations_target_ref ON citations(target_ref);
        CREATE INDEX IF NOT EXISTS idx_citations_levels ON citations(source_level, target_level);

        CREATE TABLE IF NOT EXISTS subsidy_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            amount_value REAL,
            amount_raw TEXT,
            amount_context TEXT,
            sector TEXT,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        );

        CREATE INDEX IF NOT EXISTS idx_subsidy_items_doc ON subsidy_items(document_id);
        CREATE INDEX IF NOT EXISTS idx_subsidy_items_sector ON subsidy_items(sector);

        CREATE TABLE IF NOT EXISTS document_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            site_key TEXT NOT NULL,
            change_type TEXT NOT NULL,
            field_name TEXT,
            old_value TEXT,
            new_value TEXT,
            detected_at TEXT NOT NULL,
            sync_run_id TEXT,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        );

        CREATE INDEX IF NOT EXISTS idx_doc_changes_doc ON document_changes(document_id);
        CREATE INDEX IF NOT EXISTS idx_doc_changes_type ON document_changes(change_type);
        CREATE INDEX IF NOT EXISTS idx_doc_changes_detected ON document_changes(detected_at);
        CREATE INDEX IF NOT EXISTS idx_doc_changes_run ON document_changes(sync_run_id);

        -- Body-fetch ledger. See the "Body-fetch ledger" block below for why it
        -- is a SIDE TABLE and not a column on `documents`.
        CREATE TABLE IF NOT EXISTS body_fetch_failures (
            doc_id     INTEGER PRIMARY KEY,
            site_key   TEXT NOT NULL DEFAULT '',
            reason     TEXT NOT NULL DEFAULT '',
            attempts   INTEGER NOT NULL DEFAULT 0,
            first_seen TEXT,
            last_seen  TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_body_fail_reason ON body_fetch_failures(reason);
        CREATE INDEX IF NOT EXISTS idx_body_fail_site ON body_fetch_failures(site_key);
    """)

    # URL uniqueness index — created separately because existing dups must be
    # cleaned up first (executescript would fail atomically).
    try:
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_url "
            "ON documents(url) WHERE url != ''"
        )
    except sqlite3.IntegrityError:
        # Duplicate URLs exist — remove them, keeping the row with the most body text.
        # Temporarily disable FK checks so child rows (citations etc.) don't block.
        log.info("Deduplicating URLs before creating unique index...")
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("""
            DELETE FROM documents WHERE id IN (
                SELECT d.id FROM documents d
                INNER JOIN (
                    SELECT url, MAX(LENGTH(COALESCE(body_text_cn, ''))) AS max_len
                    FROM documents WHERE url != '' GROUP BY url HAVING COUNT(*) > 1
                ) dups ON d.url = dups.url
                WHERE LENGTH(COALESCE(d.body_text_cn, '')) < dups.max_len
                   OR (LENGTH(COALESCE(d.body_text_cn, '')) = dups.max_len
                       AND d.id NOT IN (
                           SELECT MIN(id) FROM documents WHERE url != '' GROUP BY url
                       ))
            )
        """)
        removed = conn.execute("SELECT changes()").fetchone()[0]
        log.info(f"  Removed {removed} duplicate documents")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_url "
            "ON documents(url) WHERE url != ''"
        )
        conn.execute("PRAGMA foreign_keys=ON")

    conn.commit()
    return conn


# --- Write contention (SQLITE_BUSY / "database is locked") ---
#
# `busy_timeout` is set on every connection (above), but it is NOT sufficient on
# its own: it only waits out a lock, and the nightly/ad-hoc writers here hold
# transactions far longer than any fixed timeout (a crawler commits every 20-50
# docs with multi-second HTTP fetches between rows, so one batch can hold the
# write lock for minutes). Measured 2026-10-07: nine of thirteen
# `gkmlpt --backfill-bodies` runs died on the per-row UPDATE with "database is
# locked" while `crawlers.gov --library --deep` was writing — AFTER paying for the
# HTTP fetch. The fetches are the expensive, non-reproducible part, so a write
# loop that throws them away on one busy lock is the bug.
#
# Rule for any loop that writes rows it paid network time to obtain:
#   1. per-row write through `write_with_retry` (bounded backoff, then SKIP),
#   2. incremental `commit_with_retry` so earlier rows survive a later failure,
#   3. report `WriteRetryStats` and exit non-zero when anything was skipped.

LOCK_RETRY_ATTEMPTS = 6          # 1 try + 5 retries
LOCK_RETRY_BASE_DELAY = 1.0      # seconds; doubles each retry
LOCK_RETRY_MAX_DELAY = 30.0


class WriteRetryStats:
    """Mutable counters a write loop accumulates and its caller reports."""

    __slots__ = ("written", "retried", "skipped")

    def __init__(self):
        self.written = 0   # writes that landed
        self.retried = 0   # retry attempts spent (not rows)
        self.skipped = 0   # writes abandoned after exhausting attempts

    def __repr__(self):
        return (f"WriteRetryStats(written={self.written}, "
                f"retried={self.retried}, skipped={self.skipped})")

    def as_dict(self):
        return {"written": self.written, "retried": self.retried,
                "skipped": self.skipped}


def is_lock_error(exc: BaseException) -> bool:
    """True for SQLite's transient contention errors only.

    A real bug (no such column, UNIQUE constraint, malformed statement) must NOT
    be retried away — it would just burn the backoff and hide the cause.
    """
    if not isinstance(exc, sqlite3.OperationalError):
        return False
    msg = str(exc).lower()
    return "database is locked" in msg or "database is busy" in msg or "locked" in msg


def _retry_on_lock(fn, *, what: str, attempts: int, base_delay: float,
                   max_delay: float, stats: "WriteRetryStats | None",
                   sleep=None):
    """Run fn(), retrying transient lock errors with bounded exponential backoff.

    Returns (ok, result). ok=False means every attempt hit a lock error; the
    caller logs and skips that row rather than aborting the run. Non-lock
    errors propagate immediately.
    """
    sleep = sleep or time.sleep
    delay = base_delay
    for i in range(attempts):
        try:
            return True, fn()
        except sqlite3.OperationalError as e:
            if not is_lock_error(e):
                raise
            if i == attempts - 1:
                log.error(f"  DB locked, giving up after {attempts} attempts "
                          f"({what}): {e} — SKIPPING this row")
                if stats is not None:
                    stats.skipped += 1
                return False, None
            if stats is not None:
                stats.retried += 1
            log.warning(f"  DB locked ({what}), retry {i + 1}/{attempts - 1} "
                        f"in {delay:.0f}s: {e}")
            sleep(delay)
            delay = min(delay * 2, max_delay)
    return False, None  # unreachable


def write_with_retry(conn, sql: str, params=(), *, stats: WriteRetryStats = None,
                     what: str = "write", many: bool = False,
                     attempts: int = LOCK_RETRY_ATTEMPTS,
                     base_delay: float = LOCK_RETRY_BASE_DELAY,
                     max_delay: float = LOCK_RETRY_MAX_DELAY, sleep=None) -> bool:
    """One write, retried on SQLITE_BUSY. True = written, False = skipped.

    `stats.written` is incremented on success and `stats.skipped` on give-up, so
    a caller can report (and exit non-zero on) partial failure.
    """
    runner = conn.executemany if many else conn.execute
    ok, _ = _retry_on_lock(lambda: runner(sql, params), what=what,
                           attempts=attempts, base_delay=base_delay,
                           max_delay=max_delay, stats=stats, sleep=sleep)
    if ok and stats is not None:
        stats.written += 1
    return ok


def commit_with_retry(conn, *, stats: WriteRetryStats = None,
                      what: str = "commit",
                      attempts: int = LOCK_RETRY_ATTEMPTS,
                      base_delay: float = LOCK_RETRY_BASE_DELAY,
                      max_delay: float = LOCK_RETRY_MAX_DELAY,
                      sleep=None) -> bool:
    """Commit, retried on SQLITE_BUSY. True = committed.

    False leaves the transaction OPEN with its rows still pending — the next
    batch commit can still land them, so a failed commit is not counted as
    skipped rows here; the caller decides at the end of the loop.
    """
    ok, _ = _retry_on_lock(conn.commit, what=what, attempts=attempts,
                           base_delay=base_delay, max_delay=max_delay,
                           stats=None, sleep=sleep)
    if not ok:
        log.error(f"  commit failed after {attempts} attempts ({what}); "
                  f"rows remain pending in the open transaction")
    return ok


# --- Body-fetch ledger (`body_fetch_failures`) ---
#
# WHAT THIS TRADES AWAY, SAID PLAINLY: every crawler here skips a document only
# when it is "already stored WITH a body" (`if existing and existing[1]`), so a
# row that is stored but bodiless is re-fetched EVERY NIGHT, FOREVER, and the
# HTTP fetch is paid before the extraction fails. This ledger lets a crawler
# stop paying for a row that has already failed `BODY_MAX_ATTEMPTS` times. That
# is a deliberate trade of completeness for time on rows that are currently
# unobtainable — and the ledger IS what makes the trade reversible: nothing is
# silently abandoned, because every skipped row keeps a row here naming WHY, so
# a new fetch vantage, a fixed extractor or a site that comes back can re-queue
# exactly the affected class in one command
# (`python3 scripts/body_ledger.py --requeue anti_bot_stub`).
#
# Measured 2026-10-08 on 15 nightly manifests (Sep 24 - Oct 8), read-only:
#   - 1,552 bodiless rows gained a body over 14 nights, but only 12 of them on
#     the first retry and 23 within three. 1,348 landed in ONE event on Oct 7,
#     which was Phase 1b (`backfill_from_html.py`) re-extracting SAVED HTML
#     after the extractor commits 0eeb4d5/ff8ed83/f858356 — not a crawler
#     re-fetch. Phase 1b reads `raw_html_path` directly and is NOT gated by this
#     ledger, so extractor-fix recoveries keep working untouched.
#   - `bj`: 1,636 bodiless, of which 1,391 (85.0%) are titled 一图读懂 / 图解 /
#     视频 by the anchored cue below (1,418, 86.7%, by a bare substring test) —
#     documents whose body is an IMAGE. Beijing spent 760 fetches (~21 min) per
#     night re-downloading infographics that have no text to extract.
#   - `miit`: 5,395 bodiless; 3,841 of its saved files are 42 bytes of
#     "信息模板页面配置实体不能为空" (the CMS refusing a datacenter IP) and 1,527
#     have no saved HTML at all.
#
# WHICH REASONS ARE GENUINELY TERMINAL:
#   image_only / pdf_only  — terminal FOR THIS MECHANISM anywhere, not just from
#       NYC: there is no text body to fetch. The recovery path is OCR or
#       `scripts/extract_pdf_text.py`, never another HTTP GET. Hence
#       BODY_TERMINAL_REASONS: not even `--retry-bodies` re-sends these; only an
#       explicit `--requeue` does.
#   anti_bot_stub          — terminal FROM NYC ONLY ("not yet" everywhere else).
#       The server answers, with a refusal page. A residential or HK vantage is
#       the fix, which is why this reason is kept distinct and re-queueable.
#   html_missing / http_error — "not yet". The fetch failed outright; the site
#       may come back. Attempt-capped, overridable with `--retry-bodies`.
#   empty_extraction       — "not yet". The HTML is a real page our extractor
#       cannot parse. Fixed by an extractor change plus Phase 1b, which does not
#       need the crawler to re-fetch anything.
#
# It is a SIDE TABLE, never a column on `documents`: `documents` rows are wide
# and an UPDATE rewrites the `body_text_cn` overflow pages (CLAUDE.md's
# compute_scores lesson — touching every row once rewrote ~5GB of WAL). The skip
# path must therefore never touch `documents` at all.

BODY_MAX_ATTEMPTS = 3

# No HTTP GET can ever produce a text body for these, from any vantage, so ONE
# recorded failure is enough: they are skipped immediately and not even
# `--retry-bodies` re-sends them. Only `body_ledger.py --requeue` does, which is
# why the classification of `image_only` is anchored and hand-checked below.
BODY_TERMINAL_REASONS = ("image_only", "pdf_only")

# Reachable from a different vantage; kept distinct so it can be re-queued.
BODY_VANTAGE_REASONS = ("anti_bot_stub",)

BODY_REASONS = ("anti_bot_stub", "html_missing", "http_error",
                "empty_extraction", "pdf_only", "image_only")

# Measured: MIIT's refusal page is 42 bytes. A real article page is >2KB; the
# smallest genuine saved page in the corpus's bodiless set is ~2KB. 512 leaves
# an order of magnitude of headroom under that and an order above the refusals.
BODY_STUB_MAX_BYTES = 512

# Titles whose document body is an image or a video, so no text exists to extract.
#
# ANCHORED on purpose, and hand-checked (2026-10-08) rather than taken on faith,
# because `image_only` is TERMINAL after a single failure. A bare substring test
# for 视频|音频|直播 matched real regulations — 《互联网直播服务管理规定》,
# 《网络视听节目音频响度技术要求…》, 司法部…海外远程视频公证 — any of which a
# transient extraction failure would then have abandoned permanently. Requiring
# the cue at the title's head/tail or before a delimiter costs almost nothing in
# recall and removes that class of false terminal:
#   bj bodiless   broad 1,418/1,636 (86.7%)  ->  anchored 1,391 (85.0%)
#   gov has-body  broad 10 matches           ->  anchored 0
#   miit has-body broad 15                   ->  anchored 2 (both真 一图读懂)
# 图表 is dropped entirely: too generic to anchor safely.
_BODY_GRAPHIC_CUE = r"一图读懂|一图看懂|一图了解|图解|图说|漫画"
BODY_GRAPHIC_TITLE = re.compile(
    r"^\s*[【\[（(]?\s*(?:" + _BODY_GRAPHIC_CUE
    + r"|一图|动漫|动画|短视频|微视频|视频|音频|直播|H5)"      # head of title
    r"|(?:" + _BODY_GRAPHIC_CUE + r")\s*[:：丨|《]"              # cue + delimiter
    r"|(?:" + _BODY_GRAPHIC_CUE + r")\s*[）)】\]]?\s*$"         # tail of title
    r"|文件图解|政策图解|图片解读|一图读懂"                        # unambiguous anywhere
)

_BODY_BINARY_SUFFIXES = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx")

# Global override, so the nightly can flip it for every crawler in one place:
#   RETRY_BODIES=1 ./scripts/daily_sync.sh
# Per-crawler it is the `--retry-bodies` flag (see add_body_ledger_args).
RETRY_BODIES = bool(os.environ.get("RETRY_BODIES"))


def set_retry_bodies(flag: bool) -> None:
    """Turn the attempt cap off for this process (the `--retry-bodies` flag)."""
    global RETRY_BODIES
    RETRY_BODIES = bool(flag)


def add_body_ledger_args(parser) -> None:
    """Add `--retry-bodies` to a crawler's argparse parser."""
    parser.add_argument(
        "--retry-bodies", action="store_true",
        help=f"Re-fetch bodies for rows with >= {BODY_MAX_ATTEMPTS} recorded "
             f"failures in body_fetch_failures (terminal "
             f"{'/'.join(BODY_TERMINAL_REASONS)} rows still need "
             f"`scripts/body_ledger.py --requeue`)")


def apply_body_ledger_args(args) -> None:
    """Honour `--retry-bodies` if the parser defined it."""
    if getattr(args, "retry_bodies", False):
        set_retry_bodies(True)
        log.info("  --retry-bodies: the body_fetch_failures attempt cap is OFF")


def ensure_body_ledger(conn) -> None:
    """Create `body_fetch_failures` if absent (idempotent).

    `init_db` already does this, so crawlers never need to call it; scripts that
    open the DB themselves do.
    """
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS body_fetch_failures (
            doc_id     INTEGER PRIMARY KEY,
            site_key   TEXT NOT NULL DEFAULT '',
            reason     TEXT NOT NULL DEFAULT '',
            attempts   INTEGER NOT NULL DEFAULT 0,
            first_seen TEXT,
            last_seen  TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_body_fail_reason ON body_fetch_failures(reason);
        CREATE INDEX IF NOT EXISTS idx_body_fail_site ON body_fetch_failures(site_key);
    """)


def _body_ledger_row(conn, doc_id):
    """(reason, attempts) or None. Returns None if the table does not exist.

    Deliberately NOT cached per connection: an `id(conn)` cache is wrong because
    CPython reuses ids after a connection is closed, which made a fresh
    connection inherit a stale "table is missing" verdict (caught by
    tests/test_body_ledger.py). The lookup is a primary-key hit, so paying it
    every time is cheaper than being wrong.
    """
    try:
        return conn.execute(
            "SELECT reason, attempts FROM body_fetch_failures WHERE doc_id = ?",
            (doc_id,),
        ).fetchone()
    except sqlite3.OperationalError as e:
        if "no such table" not in str(e).lower():
            raise
        return None


def body_fetch_blocked(conn, doc_id, *, retry: bool = None) -> bool:
    """True if this bodiless row has failed enough times to stop re-fetching it.

    READ-ONLY: callers use this in place of giving up on `existing[1]`, and must
    `continue` WITHOUT writing to `documents` (see the block comment above).
    """
    if doc_id is None:
        return False
    row = _body_ledger_row(conn, doc_id)
    if row is None:
        return False                      # never failed before — always try it
    reason, attempts = row[0] or "", row[1] or 0
    if reason in BODY_TERMINAL_REASONS:
        return True                       # only an explicit --requeue reopens these
    if RETRY_BODIES if retry is None else retry:
        return False
    return attempts >= BODY_MAX_ATTEMPTS


def classify_body_failure(*, body: str = "", html: str = None, title: str = "",
                          url: str = "", fetch_error=None) -> str:
    """Name the reason a body fetch produced nothing. See BODY_REASONS."""
    if fetch_error is not None:
        return "http_error"
    if not html:
        return "html_missing"
    stripped = html.strip()
    if len(stripped.encode("utf-8", "replace")) <= BODY_STUB_MAX_BYTES \
            and "<html" not in stripped[:2048].lower():
        return "anti_bot_stub"
    if url and url.split("?")[0].lower().endswith(_BODY_BINARY_SUFFIXES):
        return "pdf_only"
    if title and BODY_GRAPHIC_TITLE.search(title):
        return "image_only"
    return "empty_extraction"


def record_body_failure(conn, doc_id, site_key: str, reason: str, *,
                        stats: WriteRetryStats = None) -> None:
    """Upsert a ledger row, incrementing the attempt counter."""
    write_with_retry(
        conn,
        """INSERT INTO body_fetch_failures
               (doc_id, site_key, reason, attempts, first_seen, last_seen)
           VALUES (?, ?, ?, 1, datetime('now'), datetime('now'))
           ON CONFLICT(doc_id) DO UPDATE SET
               reason    = excluded.reason,
               site_key  = excluded.site_key,
               attempts  = body_fetch_failures.attempts + 1,
               last_seen = excluded.last_seen""",
        (doc_id, site_key, reason),
        stats=stats, what=f"body_fetch_failures upsert doc {doc_id}",
    )


def clear_body_failure(conn, doc_id, *, stats: WriteRetryStats = None) -> None:
    """A row that finally yielded a body must not keep a failure record."""
    write_with_retry(conn, "DELETE FROM body_fetch_failures WHERE doc_id = ?",
                     (doc_id,), stats=stats,
                     what=f"body_fetch_failures clear doc {doc_id}")


def note_body_attempt(conn, doc_id, site_key: str, *, body: str = "",
                      html: str = None, title: str = "", url: str = "",
                      fetch_error=None, stats: WriteRetryStats = None):
    """Record the outcome of ONE body-fetch attempt. Returns the reason, or None.

    Success (a non-empty body) deletes any ledger row, so a site that comes back
    is clean again. Failure upserts the row with a classified reason.
    """
    if doc_id is None:
        return None
    if body and body.strip():
        if _body_ledger_row(conn, doc_id) is not None:
            clear_body_failure(conn, doc_id, stats=stats)
        return None
    reason = classify_body_failure(body=body, html=html, title=title, url=url,
                                   fetch_error=fetch_error)
    record_body_failure(conn, doc_id, site_key, reason, stats=stats)
    return reason


# --- HTTP ---

# Permissive TLS context: many CN gov servers use legacy ciphers / curves / renego
# that modern OpenSSL rejects (SSLV3_ALERT_HANDSHAKE_FAILURE, BAD_ECPOINT). We only
# READ public pages, so relaxing cipher security level + cert checks is safe here and
# unblocks servers like Shandong/Hunan. Built once, reused by fetch/fetch_json.
import ssl as _ssl

def _permissive_ssl_ctx():
    ctx = _ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = _ssl.CERT_NONE
    try:
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")   # allow legacy ciphers
    except _ssl.SSLError:
        pass
    ctx.options |= getattr(_ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)  # legacy renegotiation
    return ctx

_SSL_CTX = _permissive_ssl_ctx()


def _standard_ssl_ctx():
    # Modern ciphers, but no cert verification (gov certs are often self-signed/expired).
    ctx = _ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = _ssl.CERT_NONE
    return ctx

_STD_CTX = _standard_ssl_ctx()


def _build_opener(ctx):
    # Per-call cookie jar: some gov WAFs (openresty CT6T/CT6TS) answer the first request
    # with a 302→self that SETS a cookie and require it replayed on the redirect; without
    # a cookie processor urllib loops until it errors. Empty jar = no-op for cookieless
    # sites. CRAWL_PROXY (if set) routes via a residential/CN proxy for blocked sites.
    handlers = [urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())]
    if ctx is not None:
        handlers.append(urllib.request.HTTPSHandler(context=ctx))
    proxy = os.environ.get("CRAWL_PROXY")
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    return urllib.request.build_opener(*handlers)


def _decode(resp, raw):
    # Some gov servers (e.g. CNIPA) force-gzip even when no Accept-Encoding was sent.
    enc = (resp.headers.get("Content-Encoding") or "").lower()
    if enc == "gzip" or raw[:2] == b"\x1f\x8b":
        import gzip
        try:
            raw = gzip.decompress(raw)
        except Exception:
            pass
    elif enc == "deflate":
        import zlib
        try:
            raw = zlib.decompress(raw)
        except Exception:
            try:
                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
            except Exception:
                pass
    return raw.decode("utf-8", errors="replace")


def _fetch_impersonate(url: str, timeout: int, headers: dict = None) -> str | None:
    """Fallback fetch with a real Chrome TLS fingerprint (curl_cffi).

    Defeats fingerprint WAFs that block urllib's ClientHello. Returns the body on a
    200, else None (so the caller re-raises the original urllib error). Honors
    CRAWL_PROXY too, so this doubles as the fingerprint+proxy path for a HK/CN vantage.
    Returns None (not an error) when curl_cffi isn't installed.
    """
    if _cffi_requests is None:
        return None
    hdrs = {"User-Agent": USER_AGENT}
    if headers:
        hdrs.update(headers)
    kwargs = {"headers": hdrs, "timeout": timeout, "impersonate": "chrome124",
              "verify": False}
    proxy = os.environ.get("CRAWL_PROXY")
    if proxy:
        kwargs["proxies"] = {"http": proxy, "https": proxy}
    try:
        resp = _cffi_requests.get(url, **kwargs)
        if resp.status_code == 200 and resp.text:
            log.info(f"  curl_cffi fallback OK ({len(resp.text)}B) for {url}")
            return resp.text
    except Exception as e:
        log.warning(f"  curl_cffi fallback failed for {url}: {str(e)[:80]}")
    return None


def fetch(url: str, timeout: int = 20, retries: int = 3, headers: dict = None) -> str:
    """Fetch a URL and return the response body as a string.

    urllib first (unchanged path below). On a non-dead failure — a 418/blocked
    ClientHello, a connection error, or all-TLS-contexts-failed — retry ONCE with a
    Chrome-impersonated fetch (_fetch_impersonate) before giving up. Genuinely dead
    URLs (404/410/550) are NOT retried that way. This keeps the fast urllib path the
    default and only pays the curl_cffi cost when a site actually blocks us.
    """
    try:
        return _fetch_urllib(url, timeout, retries, headers)
    except urllib.error.HTTPError as e:
        if e.code in (404, 410, 550):
            raise  # genuinely dead — impersonation won't help
        last_err = e
    except (urllib.error.URLError, OSError) as e:
        last_err = e
    impersonated = _fetch_impersonate(url, timeout, headers)
    if impersonated is not None:
        return impersonated
    raise last_err


def _fetch_urllib(url: str, timeout: int = 20, retries: int = 3, headers: dict = None,
                  data: bytes = None) -> str:
    """Fetch a URL and return the response body as a string.

    Tries a STANDARD TLS context first — it's fast and works for many modern gov sites
    that HANG under the permissive legacy context (SECLEVEL=1 + legacy renegotiation);
    that permissive context is used only as a FALLBACK on an SSL handshake error (old
    sites that genuinely need it error out quickly rather than hang). Non-TLS failures
    (timeouts, HTTP errors) just retry within the current context — no fallback — so a
    dead URL isn't tried twice. `data` (bytes) turns the request into a POST.
    """
    hdrs = {"User-Agent": USER_AGENT}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs)
    contexts = [_STD_CTX, _SSL_CTX] if url.startswith("https") else [None]
    for ctx in contexts:
        opener = _build_opener(ctx)
        for attempt in range(retries):
            try:
                resp = opener.open(req, timeout=timeout)
                return _decode(resp, resp.read())
            except _ssl.SSLError:
                break  # TLS failed with this context → try the next (permissive) one
            except urllib.error.HTTPError as e:
                if e.code in (404, 410, 550):
                    raise
                if attempt < retries - 1:
                    log.warning(f"  Retry {attempt+1}/{retries} for {url}: {e}")
                    time.sleep(2 ** attempt)
                else:
                    raise
            except (urllib.error.URLError, OSError) as e:
                if isinstance(getattr(e, "reason", None), _ssl.SSLError):
                    break  # URLError wrapping an SSLError → try the next context
                if attempt < retries - 1:
                    log.warning(f"  Retry {attempt+1}/{retries} for {url}: {e}")
                    time.sleep(2 ** attempt)
                else:
                    raise
    raise urllib.error.URLError(f"all TLS contexts failed for {url}")


def fetch_json(url: str, timeout: int = 20, headers: dict = None):
    """Fetch a URL and parse the response as JSON."""
    text = fetch(url, timeout, headers=headers)
    return json.loads(text)


def fetch_post(url: str, form: dict, timeout: int = 20, retries: int = 3, headers: dict = None) -> str:
    """POST an application/x-www-form-urlencoded form and return the body as a string.

    Plain urllib (same TLS-context fallback + gzip handling as fetch()); no curl_cffi
    fallback — the list APIs that need this (intertid /info_open/search on the 无锡
    district portals, govcms dialect AC) answer an unimpersonated POST with no cookie.
    """
    data = urllib.parse.urlencode(form).encode("utf-8")
    hdrs = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest"}
    if headers:
        hdrs.update(headers)
    return _fetch_urllib(url, timeout, retries, hdrs, data=data)


# --- Storage ---

def store_site(conn: sqlite3.Connection, site_key: str, site_cfg: dict,
               sid: str = "", tree: list = None):
    """Insert or update site record."""
    conn.execute(
        """INSERT INTO sites (site_key, name, base_url, admin_level, sid, tree_json, last_crawled)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(site_key) DO UPDATE SET
             sid=excluded.sid, tree_json=excluded.tree_json, last_crawled=excluded.last_crawled""",
        (
            site_key,
            site_cfg["name"],
            site_cfg["base_url"],
            site_cfg.get("admin_level", ""),
            sid,
            json.dumps(tree or [], ensure_ascii=False),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()


def store_document(conn: sqlite3.Connection, site_key: str, doc: dict):
    """Insert or update a document record.

    `doc` must have at minimum: id, title.
    All other fields are optional and default to empty/zero.
    Uses ON CONFLICT(id) for id-based dedup, then catches URL uniqueness
    violations to prevent duplicates when crawling from multiple machines.

    Returns True only if a row for THIS site_key was written. Document ids are
    NOT namespaced per site (gkmlpt's platform-wide post ids and the synthetic
    ids other crawlers assign share one overlapping range), so the DO UPDATE is
    guarded on site_key: an id already owned by a different site is SKIPPED
    with a loud warning rather than having its body overwritten. See
    docs/working/qa-gkmlpt-sync-diff.md.
    """
    import sqlite3 as _sqlite3
    try:
        cur = conn.execute(
            """INSERT INTO documents (
                id, site_key, category_id, title, document_number, identifier,
                publisher, keywords, date_written, date_published, display_publish_time,
                abstract, body_text_cn, classify_main_name, classify_genre_name,
                classify_theme_name, url, post_url, is_expired, is_abolished,
                attachments_json, relation, raw_html_path, crawl_timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                body_text_cn=CASE WHEN excluded.body_text_cn != '' THEN excluded.body_text_cn ELSE documents.body_text_cn END,
                raw_html_path=CASE WHEN excluded.raw_html_path != '' THEN excluded.raw_html_path ELSE documents.raw_html_path END,
                crawl_timestamp=excluded.crawl_timestamp
            WHERE documents.site_key = excluded.site_key""",
        (
            doc["id"],
            site_key,
            doc.get("category_id", 0),
            doc["title"],
            doc.get("document_number", ""),
            doc.get("identifier", ""),
            doc.get("publisher", ""),
            doc.get("keywords", ""),
            doc.get("date_written", 0),
            doc.get("date_published", ""),
            doc.get("display_publish_time", 0),
            doc.get("abstract", ""),
            doc.get("body_text_cn", ""),
            doc.get("classify_main_name", ""),
            doc.get("classify_genre_name", ""),
            doc.get("classify_theme_name", ""),
            doc.get("url", ""),
            doc.get("post_url", ""),
            doc.get("is_expired", 0),
            doc.get("is_abolished", 0),
            doc.get("attachments_json", "[]"),
            doc.get("relation", ""),
            doc.get("raw_html_path", ""),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
        if cur.rowcount == 0:
            owner = conn.execute(
                "SELECT site_key FROM documents WHERE id = ?", (doc["id"],)
            ).fetchone()
            log.warning(
                f"  ID COLLISION: doc {doc['id']} ({str(doc.get('title', ''))[:40]}) "
                f"requested by site '{site_key}' is already owned by "
                f"'{owner[0] if owner else '?'}' — skipped (body NOT overwritten)"
            )
            return False
        return True
    except _sqlite3.IntegrityError:
        # URL already exists (duplicate from another machine) — skip silently
        return False


def save_raw_html(site_key: str, doc_id, html: str) -> str:
    """Save raw HTML to filesystem. Returns relative path."""
    if os.environ.get("SKIP_RAW_HTML"):
        return ""
    site_dir = RAW_HTML_DIR / site_key
    site_dir.mkdir(parents=True, exist_ok=True)
    path = site_dir / f"{doc_id}.html"
    path.write_text(html, encoding="utf-8")
    return str(path.relative_to(Path(__file__).parent.parent))


def show_stats(conn: sqlite3.Connection):
    """Show database statistics."""
    print("\n=== Database Statistics ===\n")
    sites = conn.execute(
        "SELECT site_key, name, admin_level, last_crawled FROM sites ORDER BY admin_level, name"
    ).fetchall()
    if not sites:
        print("No data yet. Run a crawler first.")
        return

    for site_key, name, admin_level, last_crawled in sites:
        total = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE site_key = ?", (site_key,)
        ).fetchone()[0]
        with_body = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE site_key = ? AND body_text_cn != ''",
            (site_key,),
        ).fetchone()[0]
        print(f"[{admin_level or '?':10s}] {name}")
        print(f"  Documents: {total}, With body: {with_body}")
        if last_crawled:
            print(f"  Last crawled: {last_crawled}")
        print()

    total_all = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    print(f"Total documents across all sites: {total_all}")


def next_id(conn: sqlite3.Connection) -> int:
    """Get next available document ID (for sites without their own IDs)."""
    row = conn.execute("SELECT MAX(id) FROM documents").fetchone()
    return (row[0] or 0) + 1
