"""Regression checks for the write-contention class of failure (2026-10-07).

MEASURED INCIDENT. Thirteen `gkmlpt --backfill-bodies --site <k>` runs went out
while `crawlers.gov --library --deep` held the write lock. Nine died on the
per-row UPDATE with `sqlite3.OperationalError: database is locked` — AFTER the
HTTP fetch had already succeeded (`curl_cffi fallback OK (35166B)` immediately
precedes the traceback in the logs). So the expensive, non-reproducible part was
paid for and then discarded, the crash aborted the rest of the site mid-loop,
and the shell `for` loop still exited 0, hiding both facts.

`busy_timeout=30000` was ALREADY set on every connection — it was never the
missing piece. A fixed timeout cannot cover a writer that holds a transaction
for minutes (the gov library crawler commits every N docs with multi-second
fetches between rows).

Rules under test:
  1. busy_timeout is actually applied to every connection the crawler layer
     opens, including the `--db` override path.
  2. A transient lock RETRIES and then succeeds (bounded backoff).
  3. A permanently locked row is logged, counted in `skipped`, and SKIPPED —
     not fatal; the loop keeps going and later rows still land.
  4. Incremental commits mean rows written BEFORE a failure persist.
  5. The CLI exits non-zero when anything was skipped.
  6. A real (non-lock) OperationalError still propagates — it must not be
     retried away.
  7. The normal, uncontended path is unchanged (same rows, no retries).

Run: python3 -m pytest tests/test_write_contention.py -v
  or: python3 tests/test_write_contention.py   (assert-based, no pytest)
"""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

os.environ["SKIP_RAW_HTML"] = "1"

from crawlers import base  # noqa: E402
from crawlers.base import (  # noqa: E402
    WriteRetryStats,
    commit_with_retry,
    init_db,
    is_lock_error,
    write_with_retry,
)
import crawlers.gkmlpt as gkmlpt  # noqa: E402


def _scratch_db(tmpdir: str) -> Path:
    """A THROWAWAY DB — never the live corpus."""
    return Path(tmpdir) / "scratch.db"


def _seed(conn, ids, site="sz"):
    conn.execute(
        "INSERT OR IGNORE INTO sites (site_key, name, base_url, admin_level) "
        "VALUES (?, ?, ?, ?)", (site, "Scratch", "http://example.gov.cn", "municipal"))
    for i in ids:
        conn.execute(
            "INSERT INTO documents (id, site_key, title, body_text_cn, url, "
            "crawl_timestamp) VALUES (?, ?, ?, '', ?, '2026-10-07T00:00:00Z')",
            (i, site, f"标题{i}", f"http://example.gov.cn/gkmlpt/content/{i}"))
    conn.commit()


# --- 1. every crawler-layer connection sets busy_timeout --------------------

def test_busy_timeout_applied_on_every_connection():
    with tempfile.TemporaryDirectory() as td:
        # default-path signature and the --db override path both go through init_db
        conn = init_db(_scratch_db(td))
        got = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        assert got == 30000, f"init_db busy_timeout={got}, expected 30000"
        conn.close()

    # No connection in crawlers/ may be opened without a busy_timeout right after.
    import re
    offenders = []
    for py in sorted((ROOT / "crawlers").glob("*.py")):
        src = py.read_text()
        for m in re.finditer(r"sqlite3\.connect\(", src):
            tail = src[m.end():m.end() + 400]
            if "busy_timeout" not in tail and "timeout=" not in src[m.end():m.end() + 120]:
                offenders.append(f"{py.name}:{src[:m.start()].count(chr(10)) + 1}")
    assert not offenders, f"sqlite3.connect without busy_timeout: {offenders}"


def test_is_lock_error_discriminates():
    assert is_lock_error(sqlite3.OperationalError("database is locked"))
    assert is_lock_error(sqlite3.OperationalError("database is busy"))
    # A real bug must NOT look retryable.
    assert not is_lock_error(sqlite3.OperationalError("no such column: nope"))
    assert not is_lock_error(sqlite3.IntegrityError("UNIQUE constraint failed"))
    assert not is_lock_error(ValueError("locked"))


# --- 2/3/6. retry, skip, and propagate -------------------------------------

class _FlakyConn:
    """Wraps a real connection; the first `fail_n` execute()s raise 'locked'."""

    def __init__(self, conn, fail_n, exc=None):
        self._conn = conn
        self._left = fail_n
        self._exc = exc or sqlite3.OperationalError("database is locked")
        self.attempts = 0

    def execute(self, *a, **kw):
        self.attempts += 1
        if self._left > 0:
            self._left -= 1
            raise self._exc
        return self._conn.execute(*a, **kw)

    def executemany(self, *a, **kw):
        return self.execute(*a, **kw)

    def commit(self):
        return self._conn.commit()


def test_transient_lock_retries_then_succeeds():
    with tempfile.TemporaryDirectory() as td:
        conn = init_db(_scratch_db(td))
        _seed(conn, [1])
        flaky = _FlakyConn(conn, fail_n=2)
        stats = WriteRetryStats()
        ok = write_with_retry(flaky, "UPDATE documents SET body_text_cn=? WHERE id=?",
                              ("正文", 1), stats=stats, sleep=lambda _: None)
        assert ok is True
        assert stats.retried == 2, stats
        assert stats.written == 1 and stats.skipped == 0, stats
        conn.commit()
        assert conn.execute("SELECT body_text_cn FROM documents WHERE id=1"
                            ).fetchone()[0] == "正文"
        conn.close()


def test_permanent_lock_is_skipped_not_fatal():
    with tempfile.TemporaryDirectory() as td:
        conn = init_db(_scratch_db(td))
        _seed(conn, [1])
        flaky = _FlakyConn(conn, fail_n=999)
        stats = WriteRetryStats()
        ok = write_with_retry(flaky, "UPDATE documents SET body_text_cn=? WHERE id=?",
                              ("正文", 1), stats=stats, sleep=lambda _: None)
        assert ok is False, "a permanently locked row must return False, not raise"
        assert stats.skipped == 1 and stats.written == 0, stats
        assert stats.retried == base.LOCK_RETRY_ATTEMPTS - 1, stats
        assert flaky.attempts == base.LOCK_RETRY_ATTEMPTS, flaky.attempts
        conn.close()


def test_non_lock_error_propagates():
    with tempfile.TemporaryDirectory() as td:
        conn = init_db(_scratch_db(td))
        flaky = _FlakyConn(conn, fail_n=1,
                           exc=sqlite3.OperationalError("no such column: nope"))
        try:
            write_with_retry(flaky, "UPDATE documents SET nope=1", (),
                             sleep=lambda _: None)
        except sqlite3.OperationalError as e:
            assert "no such column" in str(e)
        else:
            raise AssertionError("a real SQL error must not be retried away")
        assert flaky.attempts == 1, "no backoff should be burned on a real bug"
        conn.close()


def test_commit_retries_then_gives_up_without_raising():
    class _FlakyCommit:
        def __init__(self, fail_n):
            self._left = fail_n
            self.calls = 0

        def commit(self):
            self.calls += 1
            if self._left > 0:
                self._left -= 1
                raise sqlite3.OperationalError("database is locked")

    c = _FlakyCommit(2)
    assert commit_with_retry(c, sleep=lambda _: None) is True
    assert c.calls == 3
    c2 = _FlakyCommit(999)
    assert commit_with_retry(c2, sleep=lambda _: None) is False
    assert c2.calls == base.LOCK_RETRY_ATTEMPTS


# --- 4/5/7. the gkmlpt backfill loop ---------------------------------------

def _run_backfill(td, ids, lock_ids=(), commit_every=2):
    """Run gkmlpt.backfill_bodies against a scratch DB with a stubbed fetch.

    `lock_ids` rows raise 'database is locked' on EVERY write attempt.
    """
    conn = init_db(_scratch_db(td))
    _seed(conn, ids)
    fetched = []

    def fake_fetch(url, headers=None):
        doc_id = int(url.rsplit("/", 1)[-1])
        fetched.append(doc_id)
        return (f"正文内容-{doc_id}", f"<html>{doc_id}</html>")

    class _LockSome:
        def __init__(self, conn):
            self._conn = conn

        def execute(self, sql, params=()):
            if (sql.lstrip().upper().startswith("UPDATE")
                    and params and params[-1] in lock_ids):
                raise sqlite3.OperationalError("database is locked")
            return self._conn.execute(sql, params)

        def commit(self):
            return self._conn.commit()

    orig_fetch, orig_save, orig_sleep = (
        gkmlpt.fetch_document_body, gkmlpt.save_raw_html, gkmlpt.time.sleep)
    orig_base_sleep = base.time.sleep
    gkmlpt.fetch_document_body = fake_fetch
    gkmlpt.save_raw_html = lambda sk, i, h: ""
    gkmlpt.time.sleep = lambda _: None
    base.time.sleep = lambda _: None       # collapse the backoff for the test
    try:
        counts = gkmlpt.backfill_bodies(_LockSome(conn), site_key="sz",
                                        delay=0, commit_every=commit_every)
    finally:
        gkmlpt.fetch_document_body, gkmlpt.save_raw_html = orig_fetch, orig_save
        gkmlpt.time.sleep, base.time.sleep = orig_sleep, orig_base_sleep
    return conn, counts, fetched


def test_normal_path_unchanged():
    with tempfile.TemporaryDirectory() as td:
        conn, counts, fetched = _run_backfill(td, [1, 2, 3, 4, 5])
        assert fetched == [1, 2, 3, 4, 5]
        assert counts == {"candidates": 5, "fetched": 5, "no_body": 0,
                          "written": 5, "retried": 0, "skipped": 0}, counts
        bodies = dict(conn.execute(
            "SELECT id, body_text_cn FROM documents ORDER BY id").fetchall())
        assert bodies == {i: f"正文内容-{i}" for i in range(1, 6)}, bodies
        conn.close()


def test_locked_row_is_skipped_and_the_rest_of_the_loop_still_runs():
    with tempfile.TemporaryDirectory() as td:
        conn, counts, fetched = _run_backfill(td, [1, 2, 3, 4, 5], lock_ids={3})
        # The whole site was still walked — the old code aborted at id=3.
        assert fetched == [1, 2, 3, 4, 5], fetched
        assert counts["skipped"] == 1, counts
        assert counts["written"] == 4, counts
        assert counts["retried"] == base.LOCK_RETRY_ATTEMPTS - 1, counts
        got = dict(conn.execute(
            "SELECT id, body_text_cn FROM documents ORDER BY id").fetchall())
        # Rows before AND after the locked one persist (incremental commits).
        assert got[1] and got[2] and got[4] and got[5], got
        assert got[3] == "", "the locked row must be left untouched, not corrupted"
        conn.close()


def test_rows_before_a_hard_failure_persist():
    """A mid-loop crash must keep what was already fetched and written."""
    with tempfile.TemporaryDirectory() as td:
        conn = init_db(_scratch_db(td))
        _seed(conn, [1, 2, 3, 4, 5, 6])

        def fake_fetch(url, headers=None):
            doc_id = int(url.rsplit("/", 1)[-1])
            if doc_id == 5:
                raise RuntimeError("boom — unexpected mid-loop failure")
            return (f"正文内容-{doc_id}", "")

        orig_fetch, orig_save, orig_sleep = (
            gkmlpt.fetch_document_body, gkmlpt.save_raw_html, gkmlpt.time.sleep)
        gkmlpt.fetch_document_body = fake_fetch
        gkmlpt.save_raw_html = lambda sk, i, h: ""
        gkmlpt.time.sleep = lambda _: None
        try:
            gkmlpt.backfill_bodies(conn, site_key="sz", delay=0, commit_every=100)
        except RuntimeError:
            pass
        else:
            raise AssertionError("the unexpected error should still propagate")
        finally:
            gkmlpt.fetch_document_body, gkmlpt.save_raw_html = orig_fetch, orig_save
            gkmlpt.time.sleep = orig_sleep

        # Re-open the file: only COMMITTED rows are visible. commit_every=100 was
        # never reached, so this proves the `finally` commit landed rows 1-4.
        conn.close()
        check = sqlite3.connect(str(_scratch_db(td)))
        got = dict(check.execute(
            "SELECT id, body_text_cn FROM documents ORDER BY id").fetchall())
        assert all(got[i] == f"正文内容-{i}" for i in (1, 2, 3, 4)), got
        assert got[5] == "" and got[6] == "", got
        check.close()


def test_cli_exits_nonzero_when_rows_were_skipped():
    with tempfile.TemporaryDirectory() as td:
        db = _scratch_db(td)
        conn = init_db(db)
        _seed(conn, [1, 2])
        conn.close()

        def fake_fetch(url, headers=None):
            return ("正文", "")

        orig_fetch, orig_save, orig_sleep = (
            gkmlpt.fetch_document_body, gkmlpt.save_raw_html, gkmlpt.time.sleep)
        orig_backfill = gkmlpt.backfill_bodies
        orig_argv = sys.argv
        gkmlpt.fetch_document_body = fake_fetch
        gkmlpt.save_raw_html = lambda sk, i, h: ""
        gkmlpt.time.sleep = lambda _: None
        try:
            sys.argv = ["gkmlpt", "--backfill-bodies", "--site", "sz", "--db", str(db)]

            gkmlpt.backfill_bodies = lambda *a, **kw: {
                "candidates": 2, "fetched": 2, "no_body": 0,
                "written": 1, "retried": 5, "skipped": 1}
            assert gkmlpt.main() == 1, "skipped rows must make the CLI exit non-zero"

            gkmlpt.backfill_bodies = lambda *a, **kw: {
                "candidates": 2, "fetched": 2, "no_body": 0,
                "written": 2, "retried": 0, "skipped": 0}
            assert gkmlpt.main() == 0, "a clean run must still exit 0"
        finally:
            gkmlpt.fetch_document_body, gkmlpt.save_raw_html = orig_fetch, orig_save
            gkmlpt.time.sleep = orig_sleep
            gkmlpt.backfill_bodies = orig_backfill
            sys.argv = orig_argv


# --- the other exposed body/date backfill loops -----------------------------

def test_redate_apply_skips_a_locked_batch_and_keeps_going():
    """scripts/redate_from_html._apply: one locked batch must not lose the rest."""
    import scripts.redate_from_html as redate_mod

    with tempfile.TemporaryDirectory() as td:
        conn = init_db(_scratch_db(td))
        _seed(conn, [1, 2, 3])
        locked = {2}

        class _LockSome:
            def executemany(self, sql, seq):
                seq = list(seq)
                if any(i in locked for _, i in seq):
                    raise sqlite3.OperationalError("database is locked")
                return conn.executemany(sql, seq)

            def commit(self):
                return conn.commit()

        orig_sleep = base.time.sleep
        base.time.sleep = lambda _: None
        wstats = WriteRetryStats()
        try:
            # batch size is 500, so force 3 batches by patching the slice width
            done = 0
            for one in ([("2020-01-01", 1)], [("2020-01-02", 2)], [("2020-01-03", 3)]):
                done += redate_mod._apply(_LockSome(), one, False, wstats)
        finally:
            base.time.sleep = orig_sleep
        assert done == 2, done
        assert wstats.skipped == 1, wstats
        got = dict(conn.execute(
            "SELECT id, date_published FROM documents ORDER BY id").fetchall())
        assert got[1] == "2020-01-01" and got[3] == "2020-01-03", got
        conn.close()


def test_backfill_from_html_skips_locked_rows_and_reports():
    """scripts/backfill_from_html: a locked row is counted, not fatal."""
    import scripts.backfill_from_html as bfh

    with tempfile.TemporaryDirectory() as td:
        db = _scratch_db(td)
        conn = init_db(db)
        raw = Path(td) / "raw"
        raw.mkdir()
        body = "正文" * 60
        for i in (1, 2, 3):
            f = raw / f"{i}.html"
            f.write_text('<html><body><div class="TRS_Editor"><p>'
                         f'{body}{i}</p></div></body></html>')
        conn.execute(
            "INSERT OR IGNORE INTO sites (site_key, name, base_url, admin_level) "
            "VALUES ('zz_scratch', 'Scratch', 'http://example.gov.cn', 'municipal')")
        for i in (1, 2, 3):
            conn.execute(
                "INSERT INTO documents (id, site_key, title, body_text_cn, url, "
                "raw_html_path, crawl_timestamp) VALUES (?, 'zz_scratch', ?, '', ?, ?, 'x')",
                (i, f"标题{i}", f"http://example.gov.cn/c/{i}", f"raw/{i}.html"))
        conn.commit()
        conn.close()

        orig_db, orig_root, orig_sleep = bfh.DB_PATH, bfh.ROOT, base.time.sleep
        bfh.DB_PATH, bfh.ROOT = db, Path(td)
        base.time.sleep = lambda _: None
        real_connect = sqlite3.connect

        def patched_connect(*a, **kw):
            c = real_connect(*a, **kw)

            class _LockSome:
                def execute(self, sql, params=()):
                    if (sql.lstrip().upper().startswith("UPDATE")
                            and len(params) == 3 and params[1] == 2):
                        raise sqlite3.OperationalError("database is locked")
                    return c.execute(sql, params)

                def executemany(self, *x, **y):
                    return c.executemany(*x, **y)

                def commit(self):
                    return c.commit()

                def close(self):
                    return c.close()

                @property
                def total_changes(self):
                    return c.total_changes
            return _LockSome()

        try:
            sqlite3.connect = patched_connect
            counts = bfh.backfill(sites=["zz_scratch"])
        finally:
            sqlite3.connect = real_connect
            bfh.DB_PATH, bfh.ROOT = orig_db, orig_root
            base.time.sleep = orig_sleep

        assert counts["skipped"] == 1, counts
        assert counts["written"] == 2, counts
        check = real_connect(str(db))
        got = dict(check.execute(
            "SELECT id, body_text_cn FROM documents ORDER BY id").fetchall())
        assert got[1] and got[3] and got[2] == "", got
        check.close()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(fns)} checks passed")
