"""Regression checks for the body-fetch ledger (`body_fetch_failures`, 2026-10-08).

MEASURED PROBLEM (docs/working/nightly-phase1-timing.md item #2; the read-only
measurement behind the numbers below is recorded in the "Body-fetch ledger"
block comment in crawlers/base.py): every crawler
skips a document only when it is "already stored WITH a body"
(`if existing and existing[1]`), so a stored-but-BODILESS row is re-fetched
every night forever and the HTTP fetch is paid before the extraction fails.
Beijing spent 760 fetches (~21 min of its 30-minute cap) per night on rows of
which 85% are 一图读懂/图解/视频 documents whose body is an image; MIIT's
3,841 saved files are 42 bytes of a CMS refusal served to the droplet's IP.

The named verification the memo demanded is that a skipped row must NOT be
silently abandoned — it must still be retried when something changes. Hence a
ledger, not a blanket skip.

Rules under test:
  1. a first-time bodiless row is NEVER skipped (no ledger row => not blocked),
  2. a row is skipped once `attempts >= BODY_MAX_ATTEMPTS`,
  3. `--retry-bodies` / `set_retry_bodies(True)` overrides (2),
  4. terminal reasons (pdf_only) are skipped even under
     `--retry-bodies`; only `body_ledger.py --requeue` reopens them,
  5. a row that finally yields a body has its ledger entry REMOVED,
  6. the table is created idempotently (init_db, ensure_body_ledger, twice),
  7. the SKIP PATH NEVER UPDATEs a `documents` row (that is the whole point of a
     side table — an UPDATE rewrites the body_text_cn overflow pages),
  8. reason classification names each measured shape correctly,
  9. `--requeue <reason>` clears exactly that class and nothing else.

Everything runs against a scratch SQLite DB in a temp dir — never documents.db —
and makes no network call.

Run: python3 -m pytest tests/test_body_ledger.py -v
  or: python3 tests/test_body_ledger.py   (assert-based, no pytest needed)
"""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

os.environ["SKIP_RAW_HTML"] = "1"

from crawlers import base  # noqa: E402


# --------------------------------------------------------------------------
# Scratch DB
# --------------------------------------------------------------------------

def _scratch_db(tmp: Path):
    """A real init_db() against a throwaway file, so the schema is the shipped one."""
    conn = base.init_db(tmp / "scratch.db")
    conn.execute(
        "INSERT INTO sites (site_key, name, base_url, admin_level) "
        "VALUES ('bj', 'Beijing', 'https://www.beijing.gov.cn', 'provincial')")
    conn.commit()
    return conn


def _add_doc(conn, doc_id, title="一图读懂《某办法》", url=None, body=""):
    conn.execute(
        """INSERT INTO documents (id, site_key, title, body_text_cn, url, crawl_timestamp)
           VALUES (?, 'bj', ?, ?, ?, '2026-10-08T00:00:00Z')""",
        (doc_id, title, body, url or f"https://www.beijing.gov.cn/d/{doc_id}.html"))
    conn.commit()
    return doc_id


# --------------------------------------------------------------------------
# 1 + 2 + 3: the attempt cap and its override
# --------------------------------------------------------------------------

def test_first_time_bodiless_row_is_not_skipped():
    with tempfile.TemporaryDirectory() as td:
        conn = _scratch_db(Path(td))
        doc_id = _add_doc(conn, 101)
        assert base.body_fetch_blocked(conn, doc_id) is False, \
            "a row that has never failed must always be fetched"
        conn.close()


def test_row_is_skipped_only_after_the_threshold():
    with tempfile.TemporaryDirectory() as td:
        conn = _scratch_db(Path(td))
        doc_id = _add_doc(conn, 102)
        seen = []
        for _ in range(base.BODY_MAX_ATTEMPTS):
            seen.append(base.body_fetch_blocked(conn, doc_id, retry=False))
            base.note_body_attempt(conn, doc_id, "bj", body="",
                                   html="<html>" + "x" * 5000 + "</html>",
                                   title="某通知", url="https://x/y.html")
            conn.commit()
        assert seen == [False] * base.BODY_MAX_ATTEMPTS, \
            f"must stay eligible for the first {base.BODY_MAX_ATTEMPTS} attempts, got {seen}"
        assert base.body_fetch_blocked(conn, doc_id, retry=False) is True, \
            "must be skipped once attempts >= BODY_MAX_ATTEMPTS"
        row = conn.execute(
            "SELECT reason, attempts, site_key, first_seen, last_seen "
            "FROM body_fetch_failures WHERE doc_id = ?", (doc_id,)).fetchone()
        assert row[0] == "empty_extraction", row
        assert row[1] == base.BODY_MAX_ATTEMPTS, row
        assert row[2] == "bj", row
        assert row[3] and row[4], "first_seen/last_seen must be stamped"
        conn.close()


def test_retry_bodies_overrides_the_cap():
    with tempfile.TemporaryDirectory() as td:
        conn = _scratch_db(Path(td))
        doc_id = _add_doc(conn, 103)
        base.record_body_failure(conn, doc_id, "bj", "empty_extraction")
        conn.execute("UPDATE body_fetch_failures SET attempts = 99 WHERE doc_id = ?",
                     (doc_id,))
        conn.commit()
        assert base.body_fetch_blocked(conn, doc_id, retry=False) is True
        assert base.body_fetch_blocked(conn, doc_id, retry=True) is False, \
            "--retry-bodies must re-open an attempt-capped row"

        # and via the process-wide flag the CLI flag sets
        before = base.RETRY_BODIES
        try:
            base.set_retry_bodies(True)
            assert base.body_fetch_blocked(conn, doc_id) is False
            base.set_retry_bodies(False)
            assert base.body_fetch_blocked(conn, doc_id) is True
        finally:
            base.set_retry_bodies(before)
        conn.close()


# --------------------------------------------------------------------------
# 4: terminal reasons
# --------------------------------------------------------------------------

def test_terminal_reasons_survive_retry_bodies():
    with tempfile.TemporaryDirectory() as td:
        conn = _scratch_db(Path(td))
        for i, reason in enumerate(base.BODY_TERMINAL_REASONS):
            doc_id = _add_doc(conn, 110 + i)
            base.record_body_failure(conn, doc_id, "bj", reason)
            conn.commit()
            # one recorded attempt only — below the cap — yet still blocked
            assert base.body_fetch_blocked(conn, doc_id, retry=True) is True, \
                f"{reason} must be terminal even with --retry-bodies"

        # a vantage-blocked reason is NOT terminal: --retry-bodies re-opens it
        doc_id = _add_doc(conn, 120)
        base.record_body_failure(conn, doc_id, "miit", "anti_bot_stub")
        conn.execute("UPDATE body_fetch_failures SET attempts = 9 WHERE doc_id = ?",
                     (doc_id,))
        conn.commit()
        assert base.body_fetch_blocked(conn, doc_id, retry=False) is True
        assert base.body_fetch_blocked(conn, doc_id, retry=True) is False, \
            "anti_bot_stub is terminal from NYC only — a new vantage must reach it"
        conn.close()


# --------------------------------------------------------------------------
# 5: success clears the ledger
# --------------------------------------------------------------------------

def test_a_body_removes_the_ledger_entry():
    with tempfile.TemporaryDirectory() as td:
        conn = _scratch_db(Path(td))
        doc_id = _add_doc(conn, 130)
        base.record_body_failure(conn, doc_id, "bj", "http_error")
        base.record_body_failure(conn, doc_id, "bj", "http_error")
        conn.commit()
        assert conn.execute("SELECT attempts FROM body_fetch_failures WHERE doc_id=?",
                            (doc_id,)).fetchone()[0] == 2

        reason = base.note_body_attempt(conn, doc_id, "bj",
                                        body="正文内容若干。", html="<html>ok</html>")
        conn.commit()
        assert reason is None, "a non-empty body is not a failure"
        assert conn.execute("SELECT COUNT(*) FROM body_fetch_failures WHERE doc_id=?",
                            (doc_id,)).fetchone()[0] == 0, \
            "a row that finally yielded a body must not keep a failure record"
        assert base.body_fetch_blocked(conn, doc_id) is False
        conn.close()


# --------------------------------------------------------------------------
# 6: idempotent creation
# --------------------------------------------------------------------------

def test_ledger_is_created_idempotently():
    with tempfile.TemporaryDirectory() as td:
        # init_db creates it
        conn = _scratch_db(Path(td))
        assert conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='body_fetch_failures'").fetchone() is not None
        # explicit ensure, twice, is a no-op
        base.ensure_body_ledger(conn)
        base.ensure_body_ledger(conn)
        conn.commit()
        conn.close()
        # a second init_db over the same file must not fail either
        conn = base.init_db(Path(td) / "scratch.db")
        base.ensure_body_ledger(conn)
        cols = [r[1] for r in conn.execute(
            "PRAGMA table_info(body_fetch_failures)")]
        assert cols == ["doc_id", "site_key", "reason", "attempts",
                        "first_seen", "last_seen"], cols
        conn.close()

    # and a connection WITHOUT the table degrades to "not blocked", never raises
    with tempfile.TemporaryDirectory() as td:
        bare = sqlite3.connect(str(Path(td) / "bare.db"))
        assert base.body_fetch_blocked(bare, 1) is False
        bare.close()


# --------------------------------------------------------------------------
# 7: the skip path must not touch `documents`
# --------------------------------------------------------------------------

def test_skip_path_never_updates_a_documents_row():
    """The reason this is a side table: an UPDATE on `documents` rewrites the
    body_text_cn overflow pages (CLAUDE.md's compute_scores lesson)."""
    with tempfile.TemporaryDirectory() as td:
        conn = _scratch_db(Path(td))
        doc_id = _add_doc(conn, 140)
        for _ in range(base.BODY_MAX_ATTEMPTS):     # the real route to "blocked"
            base.record_body_failure(conn, doc_id, "bj", "empty_extraction")
        conn.commit()

        before = conn.execute(
            "SELECT title, body_text_cn, url, crawl_timestamp, raw_html_path "
            "FROM documents WHERE id = ?", (doc_id,)).fetchone()
        changes_before = conn.total_changes

        blocked = base.body_fetch_blocked(conn, doc_id)
        assert blocked is True

        assert conn.total_changes == changes_before, \
            "body_fetch_blocked must be READ-ONLY — it wrote to the DB"
        after = conn.execute(
            "SELECT title, body_text_cn, url, crawl_timestamp, raw_html_path "
            "FROM documents WHERE id = ?", (doc_id,)).fetchone()
        assert before == after, "the skip path must not modify the documents row"
        conn.close()


def test_beijing_skip_path_is_wired_and_writes_nothing():
    """Exercise the real crawler branch: the measured 760-fetch loop in
    `crawlers.beijing.crawl_section` must `continue` before store_document."""
    import crawlers.beijing as bj

    with tempfile.TemporaryDirectory() as td:
        conn = _scratch_db(Path(td))
        url = "https://www.beijing.gov.cn/zhengce/zcjd/202202/t1.html"
        doc_id = _add_doc(conn, 150, title="一图读懂《某实施方案》", url=url)
        for _ in range(base.BODY_MAX_ATTEMPTS):     # the real route to "blocked"
            base.record_body_failure(conn, doc_id, "bj", "image_only")
        conn.commit()

        fetched = []
        orig_fetch, orig_parse, orig_pages = bj.fetch, bj._parse_listing, bj._get_total_pages
        try:
            bj.fetch = lambda u, *a, **k: fetched.append(u) or "<html></html>"
            bj._get_total_pages = lambda html: 1
            bj._parse_listing = lambda html, u: [
                {"url": url, "title": "一图读懂《某实施方案》", "date_str": "2022-02-17"}]
            bj.REQUEST_DELAY = 0
            changes_before = conn.total_changes
            stored = bj.crawl_section(conn, "zcjd", "政策解读", fetch_bodies=True)
        finally:
            bj.fetch, bj._parse_listing, bj._get_total_pages = orig_fetch, orig_parse, orig_pages

        assert stored == 1, stored
        assert fetched == [bj._section_url("zcjd", 0)], \
            f"the blocked document's body must NOT be fetched; fetched={fetched}"
        assert conn.total_changes == changes_before, \
            "the skip path wrote to the DB"
        conn.close()


def test_beijing_records_then_skips_across_runs():
    """End-to-end through the real crawler loop.

    (a) a non-terminal failure (`empty_extraction`) builds the attempt counter
        and the row stops being fetched exactly at BODY_MAX_ATTEMPTS;
    (b) a graphic-cue failure (`image_only`) is capped like any other;
    (c) once the extractor is fixed, the body lands and the ledger entry goes.

    The record is gated on `store_document`'s return value, so a ledger entry is
    never keyed on a document another site_key owns.
    """
    import crawlers.beijing as bj

    page = "<html>" + "x" * 20000 + "</html>"

    def run(title, expect_reason, expect_fetches_before_cap):
        with tempfile.TemporaryDirectory() as td:
            conn = _scratch_db(Path(td))
            url = "https://www.beijing.gov.cn/zhengce/zcjd/202202/t2.html"
            fetched = []
            orig = (bj.fetch, bj._parse_listing, bj._get_total_pages,
                    bj._extract_body, bj._extract_meta, bj.REQUEST_DELAY)
            try:
                bj.fetch = lambda u, *a, **k: (fetched.append(u), page)[1]
                bj._get_total_pages = lambda html: 1
                bj._parse_listing = lambda html, u: [
                    {"url": url, "title": title, "date_str": "2022-02-17"}]
                bj._extract_body = lambda html: ""      # the measured failure
                bj._extract_meta = lambda html: {}
                bj.REQUEST_DELAY = 0

                for _ in range(expect_fetches_before_cap + 2):
                    bj.crawl_section(conn, "zcjd", "政策解读", fetch_bodies=True)

                rows = conn.execute(
                    "SELECT reason, attempts FROM body_fetch_failures").fetchall()
                assert rows == [(expect_reason, expect_fetches_before_cap)], rows
                body_fetches = [u for u in fetched if u == url]
                assert len(body_fetches) == expect_fetches_before_cap, \
                    f"{title}: paid {len(body_fetches)} fetches, " \
                    f"expected {expect_fetches_before_cap}"

                # the extractor is fixed; backfill/crawl now yields a body
                conn.execute("DELETE FROM body_fetch_failures")
                conn.commit()
                bj._extract_body = lambda html: "正文若干。"
                bj.crawl_section(conn, "zcjd", "政策解读", fetch_bodies=True)
                assert conn.execute(
                    "SELECT COUNT(*) FROM body_fetch_failures").fetchone()[0] == 0
                assert conn.execute(
                    "SELECT body_text_cn FROM documents WHERE url = ?",
                    (url,)).fetchone()[0] == "正文若干。"
            finally:
                (bj.fetch, bj._parse_listing, bj._get_total_pages,
                 bj._extract_body, bj._extract_meta, bj.REQUEST_DELAY) = orig
            conn.close()

    # (a) a real page our extractor cannot parse: 3 attempts, then capped
    run("关于印发某办法的通知", "empty_extraction", base.BODY_MAX_ATTEMPTS)
    # (b) an infographic: capped like any other reason (it was TERMINAL after one
    # attempt until 2026-10-08; see BODY_TERMINAL_REASONS for the measurement
    # that removed it — the cue is ambiguous on the only site where it fires).
    run("一图读懂《某实施方案》", "image_only", base.BODY_MAX_ATTEMPTS)


def test_image_only_is_capped_not_terminal():
    """A title-cue verdict must never be permanent (measured 2026-10-08).

    `image_only` is decided by a title cue, and on the only site where that cue
    fires in volume (bj: 1,268 bodiless vs 107 has-body rows carry it) the cue is
    genuinely ambiguous — Beijing publishes the infographic, the audio reading and
    the full text of one document on a single page, titled
    `一图读懂、音频解读：…关于印发《X》的通知`. Terminality bought one fetch
    instead of three, ONCE; it cost the permanent silent loss of a text-bearing
    page on a single transient extraction failure. `pdf_only` stays terminal
    because its verdict comes from the URL suffix, not from a guess.
    """
    assert "image_only" not in base.BODY_TERMINAL_REASONS
    assert "pdf_only" in base.BODY_TERMINAL_REASONS
    assert "image_only" in base.BODY_REASONS, "it keeps its name as a --requeue lever"

    with tempfile.TemporaryDirectory() as td:
        conn = _scratch_db(Path(td))
        doc_id = _add_doc(conn, 777)
        base.record_body_failure(conn, doc_id, "bj", "image_only")
        conn.commit()
        assert base.body_fetch_blocked(conn, doc_id, retry=False) is False, \
            "one graphic-cue failure must not abandon the row"
        for _ in range(base.BODY_MAX_ATTEMPTS - 1):
            base.record_body_failure(conn, doc_id, "bj", "image_only")
        conn.commit()
        assert base.body_fetch_blocked(conn, doc_id, retry=False) is True
        assert base.body_fetch_blocked(conn, doc_id, retry=True) is False, \
            "--retry-bodies must now re-open it, like any capped reason"
        conn.close()


# --------------------------------------------------------------------------
# 8: reason classification
# --------------------------------------------------------------------------

def test_reasons_name_the_measured_shapes():
    c = base.classify_body_failure
    # MIIT, measured: 42 bytes of a CMS refusal, no <html> tag
    assert c(html="信息模板页面配置实体不能为空") == "anti_bot_stub"
    assert c(html="信息实体不能为空") == "anti_bot_stub"
    # fetch raised / returned nothing
    assert c(html=None, fetch_error=RuntimeError("timeout")) == "http_error"
    assert c(html="<html>x</html>", fetch_error=OSError("boom")) == "http_error"
    assert c(html=None) == "html_missing"
    assert c(html="") == "html_missing"
    # a binary payload
    assert c(html="<html>" + "x" * 5000, url="http://x/a.pdf") == "pdf_only"
    assert c(html="<html>" + "x" * 5000, url="http://x/a.docx?v=2") == "pdf_only"
    # Beijing, measured: 85.0% of its bodiless rows
    big = "<html>" + "x" * 20000 + "</html>"
    for t in ("一图读懂《某办法》", "图解：第九批文物保护单位", "视频 | 新闻发布会",
              "文件图解——关于《X》的解读", "《某规划》一图读懂",
              "【图片解读】一图读懂科技企业孵化器认定办法",
              "《关于X的意见（试行）》政策解读（一图读懂）"):
        assert c(html=big, title=t) == "image_only", t

    # The cue MUST NOT fire on a real regulation that merely contains
    # 视频/音频/直播 in its name — all of these are genuine documents in the
    # corpus and an unanchored substring test matched every one of them
    # (measured 2026-10-08). `image_only` is no longer terminal, so this now
    # protects three wasted fetches rather than the document itself.
    for t in ("国家网信办发布《互联网直播服务管理规定》",
              "关于发布《网络视听节目音频响度技术要求和测量方法》等三项标准的通知",
              "司法部办公厅关于进一步推进海外远程视频公证工作的通知",
              "河北省通信管理局召开全省视频会议 强化汛期防汛救灾应急通信保障工作",
              "光缆行业数智化转型“一图四清单”建设成果交流会在京召开",
              "关于印发某办法的通知"):
        assert c(html=big, title=t) == "empty_extraction", \
            f"{t!r} must stay recoverable, not be terminally abandoned"
    # a short page that IS html is not a stub
    assert c(html="<html><body>短</body></html>", title="通知") == "empty_extraction"
    # every reason the table can hold is a declared one
    for r in ("anti_bot_stub", "html_missing", "http_error", "empty_extraction",
              "pdf_only", "image_only"):
        assert r in base.BODY_REASONS, r
    assert set(base.BODY_TERMINAL_REASONS) <= set(base.BODY_REASONS)
    assert set(base.BODY_VANTAGE_REASONS) <= set(base.BODY_REASONS)
    # terminal and vantage classes must not overlap: one is "never", the other
    # is "not from here"
    assert not (set(base.BODY_TERMINAL_REASONS) & set(base.BODY_VANTAGE_REASONS))


# --------------------------------------------------------------------------
# 9: --requeue is the one-command reversal
# --------------------------------------------------------------------------

def test_requeue_clears_exactly_one_reason_class():
    import body_ledger

    with tempfile.TemporaryDirectory() as td:
        conn = _scratch_db(Path(td))
        for i, (reason, site) in enumerate([
                ("anti_bot_stub", "miit"), ("anti_bot_stub", "miit"),
                ("image_only", "bj"), ("empty_extraction", "bj")]):
            doc_id = _add_doc(conn, 200 + i)
            base.record_body_failure(conn, doc_id, site, reason)
        conn.commit()
        conn.close()

        orig = body_ledger.DB_PATH
        try:
            body_ledger.DB_PATH = Path(td) / "scratch.db"
            assert body_ledger.cmd_requeue("anti_bot_stub", dry_run=True) == 0
            conn = sqlite3.connect(str(body_ledger.DB_PATH))
            assert conn.execute("SELECT COUNT(*) FROM body_fetch_failures"
                                ).fetchone()[0] == 4, "--dry-run must not delete"
            conn.close()

            assert body_ledger.cmd_requeue("anti_bot_stub") == 0
            conn = sqlite3.connect(str(body_ledger.DB_PATH))
            left = dict(conn.execute(
                "SELECT reason, COUNT(*) FROM body_fetch_failures GROUP BY reason"))
            assert left == {"image_only": 1, "empty_extraction": 1}, left
            # a re-queued row is a first-timer again
            assert base.body_fetch_blocked(conn, 200) is False
            conn.close()

            assert body_ledger.cmd_requeue("not_a_reason") == 2, \
                "an unknown reason must be refused, not silently delete nothing"
        finally:
            body_ledger.DB_PATH = orig


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS {name}")
            except AssertionError as e:
                fails += 1
                print(f"  FAIL {name}: {e}")
    print("OK" if not fails else f"{fails} FAILED")
    sys.exit(1 if fails else 0)
