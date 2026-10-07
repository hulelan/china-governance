"""Regression checks for the classifier's silent-failure fix (2026-10-07).

docs/working/qa-classification-failures.md: `deepseek-v4-flash` is a reasoning
model and bills reasoning tokens against `max_tokens`, so ~a third of nightly
calls returned finish_reason="length" with EMPTY content. `classify_deepseek`
turned that into a bare `None` on three unlogged paths, `main` counted it as
`errors += 1`, and the document — left with `classified_at = ''` — was re-sent
every night forever.

Rules under test:
  1. every failure path returns a distinct reason string (per-reason tally),
  2. finish_reason="length" is retried ONCE at a doubled budget,
  3. content_risk is TERMINAL (never re-selected, even with --retry-failed),
  4. docs at >= MAX_ATTEMPTS failures are skipped,
  5. --retry-failed overrides (4) but not (3).

The API is mocked throughout — these tests never make a network call, and they
run against a scratch SQLite DB in a temp dir, never documents.db.

Run: python3 -m pytest tests/test_classify_failures.py -v
  or: python3 tests/test_classify_failures.py   (assert-based, no pytest needed)
"""
import sqlite3
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import classify_documents as cd  # noqa: E402

GOOD_JSON = (
    '{"title_en": "Test", "summary_en": "A test doc.", "doc_type": "original_policy",'
    ' "policy_significance": "high", "topics": ["artificial intelligence"],'
    ' "policy_area": "人工智能", "references": []}'
)


# --------------------------------------------------------------------------
# Mock API plumbing
# --------------------------------------------------------------------------

class _Msg:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content, finish_reason):
        self.message = _Msg(content)
        self.finish_reason = finish_reason


class _Resp:
    def __init__(self, content, finish_reason):
        self.choices = [_Choice(content, finish_reason)]


class FakeCompletions:
    """Replays a scripted list of (content, finish_reason) or Exception."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []            # recorded max_tokens per call

    def create(self, **kwargs):
        self.calls.append(kwargs)
        step = self.script.pop(0) if self.script else ("", "length")
        if isinstance(step, Exception):
            raise step
        return _Resp(*step)


class FakeClient:
    def __init__(self, script):
        self.completions = FakeCompletions(script)
        self.chat = self


def _with_client(script):
    client = FakeClient(script)
    cd._get_deepseek_client = lambda: client          # noqa: E731
    return client


DOC = {"id": 42, "title": "测试文件", "document_number": "", "publisher": "",
       "body_text_cn": "正文", "classify_main_name": ""}


# --------------------------------------------------------------------------
# 1. per-reason outcomes
# --------------------------------------------------------------------------

def test_success_returns_ok_reason():
    _with_client([(GOOD_JSON, "stop")])
    result, reason = cd.classify_deepseek(DOC, "m")
    assert reason == cd.REASON_OK, reason
    assert result["doc_type"] == "original_policy"


def test_empty_content_length_after_retry():
    """Both the 12k call and the 24k retry come back empty → empty_content_length."""
    client = _with_client([("", "length"), ("", "length")])
    result, reason = cd.classify_deepseek(DOC, "m")
    assert result is None
    assert reason == cd.REASON_EMPTY_LENGTH, reason
    assert len(client.completions.calls) == 2


def test_empty_content_other_is_distinct_and_not_retried():
    """Empty with finish_reason=stop is the concurrency-2 failure — different reason."""
    client = _with_client([("", "stop")])
    result, reason = cd.classify_deepseek(DOC, "m")
    assert result is None
    assert reason == cd.REASON_EMPTY_OTHER, reason
    assert len(client.completions.calls) == 1, "must NOT burn a doubled-budget retry"


def test_content_risk_reason():
    _with_client([Exception("Error code: 400 - Content Exists Risk")])
    result, reason = cd.classify_deepseek(DOC, "m")
    assert result is None
    assert reason == cd.REASON_CONTENT_RISK, reason
    assert cd.REASON_CONTENT_RISK in cd.TERMINAL_REASONS


def test_json_unsalvageable_reason():
    client = _with_client([("I think this document is about housing.", "stop")])
    result, reason = cd.classify_deepseek(DOC, "m")
    assert result is None
    assert reason == cd.REASON_JSON, reason
    assert len(client.completions.calls) == 1, "finish_reason=stop → no retry"


def test_http_and_timeout_reasons():
    _with_client([Exception("Error code: 502 Bad Gateway")])
    assert cd.classify_deepseek(DOC, "m")[1] == cd.REASON_HTTP
    _with_client([Exception("Request timed out.")])
    assert cd.classify_deepseek(DOC, "m")[1] == cd.REASON_TIMEOUT


def test_reason_tally_is_per_reason():
    scripts = {
        cd.REASON_OK: [(GOOD_JSON, "stop")],
        cd.REASON_EMPTY_LENGTH: [("", "length"), ("", "length")],
        cd.REASON_CONTENT_RISK: [Exception("Content Exists Risk")],
        cd.REASON_JSON: [("not json", "stop")],
    }
    tally = Counter()
    for expected, script in scripts.items():
        _with_client(script)
        _, reason = cd.classify_deepseek(DOC, "m")
        assert reason == expected, (expected, reason)
        if reason != cd.REASON_OK:
            tally[reason] += 1
    assert tally == Counter({cd.REASON_EMPTY_LENGTH: 1,
                             cd.REASON_CONTENT_RISK: 1,
                             cd.REASON_JSON: 1})
    rendered = cd._format_reasons(tally)
    for r in tally:
        assert r in rendered, rendered


# --------------------------------------------------------------------------
# 2. the length retry
# --------------------------------------------------------------------------

def test_length_retry_doubles_budget_and_recovers():
    """The memo's 8/8 recovery: empty at 12k, good JSON at the retry budget."""
    client = _with_client([("", "length"), (GOOD_JSON, "stop")])
    result, reason = cd.classify_deepseek(DOC, "m")
    assert reason == cd.REASON_OK, reason
    assert result["title_en"] == "Test"
    budgets = [c["max_tokens"] for c in client.completions.calls]
    assert budgets == [cd.MAX_TOKENS, cd.MAX_TOKENS_RETRY], budgets
    assert cd.MAX_TOKENS == 12_000 and cd.MAX_TOKENS_RETRY == 24_000


def test_length_retry_happens_at_most_once():
    client = _with_client([("", "length"), ("", "length"), (GOOD_JSON, "stop")])
    _, reason = cd.classify_deepseek(DOC, "m")
    assert reason == cd.REASON_EMPTY_LENGTH
    assert len(client.completions.calls) == 2, client.completions.calls


def test_truncated_json_at_length_is_also_retried():
    """Content that even the brace-closing salvage can't rescue → retry, not None."""
    client = _with_client([('{"title_en": "A", "x": {"y', "length"), (GOOD_JSON, "stop")])
    result, reason = cd.classify_deepseek(DOC, "m")
    assert reason == cd.REASON_OK, reason
    assert len(client.completions.calls) == 2


# --------------------------------------------------------------------------
# 3-5. selection against a scratch DB
# --------------------------------------------------------------------------

def _scratch_db(failures=()):
    """Minimal documents table + classify_failures, in a temp file."""
    tmp = Path(tempfile.mkdtemp()) / "scratch.db"
    conn = sqlite3.connect(str(tmp))
    conn.execute("""CREATE TABLE documents (
        id INTEGER PRIMARY KEY, title TEXT, document_number TEXT, publisher TEXT,
        body_text_cn TEXT, classify_main_name TEXT, site_key TEXT,
        date_written TEXT, classified_at TEXT DEFAULT '')""")
    rows = [
        (1, "fresh",     "sz", ""),                      # never attempted
        (2, "twice",     "sz", ""),                      # 2 failures
        (3, "exhausted", "sz", ""),                      # 3 failures
        (4, "risky",     "sz", ""),                      # terminal
        (5, "done",      "sz", "2026-10-01 00:00:00"),   # already classified
        (6, "othersite", "bj", ""),
    ]
    for doc_id, title, site, cat in rows:
        conn.execute("INSERT INTO documents (id, title, document_number, publisher,"
                     " body_text_cn, classify_main_name, site_key, date_written,"
                     " classified_at) VALUES (?,?,'','','','',?,'2026-10-01',?)",
                     (doc_id, title, site, cat))
    cd.ensure_failure_table(conn)
    for doc_id, reason, attempts in failures:
        conn.execute("INSERT INTO classify_failures (doc_id, reason, attempts,"
                     " first_seen, last_seen) VALUES (?,?,?,datetime('now'),datetime('now'))",
                     (doc_id, reason, attempts))
    conn.commit()
    return conn


FAILS = ((2, cd.REASON_EMPTY_LENGTH, 2),
         (3, cd.REASON_EMPTY_LENGTH, 3),
         (4, cd.REASON_CONTENT_RISK, 1))


def test_selection_skips_exhausted_and_terminal():
    conn = _scratch_db(FAILS)
    ids = {d["id"] for d in cd.select_docs(conn)}
    assert ids == {1, 2, 6}, ids          # 3 exhausted, 4 terminal, 5 classified


def test_retry_failed_overrides_attempt_cap_but_not_terminal():
    conn = _scratch_db(FAILS)
    ids = {d["id"] for d in cd.select_docs(conn, retry_failed=True)}
    assert ids == {1, 2, 3, 6}, ids       # 3 is back; 4 (content_risk) stays out


def test_selection_still_honours_site_and_limit():
    conn = _scratch_db(FAILS)
    assert {d["id"] for d in cd.select_docs(conn, site="sz")} == {1, 2}
    assert len(cd.select_docs(conn, limit=1)) == 1


def test_selection_works_before_the_table_exists():
    """Back-compat: a DB without classify_failures must still be selectable."""
    conn = _scratch_db()
    conn.execute("DROP TABLE classify_failures")
    conn.commit()
    assert not cd._has_failure_table(conn)
    assert {d["id"] for d in cd.select_docs(conn)} == {1, 2, 3, 4, 6}


def test_ensure_failure_table_is_idempotent():
    conn = _scratch_db()
    cd.ensure_failure_table(conn)
    cd.ensure_failure_table(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(classify_failures)")}
    assert cols == {"doc_id", "reason", "attempts", "first_seen", "last_seen"}, cols


def test_record_failure_increments_attempts_and_clear_removes():
    conn = _scratch_db()
    cd.record_failure(conn, 1, cd.REASON_EMPTY_LENGTH)
    cd.record_failure(conn, 1, cd.REASON_JSON)
    row = conn.execute("SELECT reason, attempts, first_seen, last_seen"
                       " FROM classify_failures WHERE doc_id=1").fetchone()
    assert row[1] == 2, row
    assert row[0] == cd.REASON_JSON, row   # latest reason wins
    assert row[2] and row[3]
    # a doc that exceeds the cap drops out of selection...
    cd.record_failure(conn, 1, cd.REASON_JSON)
    conn.commit()
    assert 1 not in {d["id"] for d in cd.select_docs(conn)}
    # ...and comes back once it finally classifies
    cd.clear_failure(conn, 1)
    conn.commit()
    assert 1 in {d["id"] for d in cd.select_docs(conn)}


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL OK")
