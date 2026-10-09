"""A host that accepts connections but never answers must not consume the whole run.

Measured 2026-10-09: an extraction run sat 27 minutes with 23 s of CPU, one ESTAB
socket to 202.104.121.106:80, and ZERO database writes — roughly 54 documents at the
full 30 s timeout, all against one peer. Because the work list is ordered by id, a
single host's documents are contiguous, so the run can spend hours inside one dead
host. At that rate 5,084 documents would need ~42 h and collide with the nightly.

Consecutive, not cumulative, is the design point: 8 failures in a row means the host is
down, whereas 8 scattered among successes means some files are bad.

Run: python3 -m pytest tests/test_host_breaker.py -v
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from extract_pdf_text import HOST_FAIL_LIMIT, HostBreaker  # noqa: E402

A = "http://www.szdp.gov.cn/attachment/0/1/1/1.pdf"
B = "http://www.hrss.gov.cn/attachment/0/2/2/2.pdf"


def test_a_fresh_host_is_not_tripped():
    assert HostBreaker().is_open(A) is False


def test_consecutive_failures_trip_the_host():
    b = HostBreaker()
    for _ in range(HOST_FAIL_LIMIT - 1):
        b.record(A, False)
    assert b.is_open(A) is False, "must not trip one failure early"
    b.record(A, False)
    assert b.is_open(A) is True


def test_a_success_resets_the_count():
    """A slow-but-working host must never trip."""
    b = HostBreaker()
    for _ in range(HOST_FAIL_LIMIT - 1):
        b.record(A, False)
    b.record(A, True)
    for _ in range(HOST_FAIL_LIMIT - 1):
        b.record(A, False)
    assert b.is_open(A) is False


def test_scattered_failures_never_trip():
    b = HostBreaker()
    for _ in range(HOST_FAIL_LIMIT * 3):
        b.record(A, False)
        b.record(A, True)
    assert b.is_open(A) is False


def test_hosts_are_independent():
    b = HostBreaker()
    for _ in range(HOST_FAIL_LIMIT):
        b.record(A, False)
    assert b.is_open(A) is True
    assert b.is_open(B) is False, "one dead host must not stop the others"


def test_the_breaker_reports_which_hosts_tripped():
    b = HostBreaker()
    for _ in range(HOST_FAIL_LIMIT):
        b.record(A, False)
    assert b.report() == ["www.szdp.gov.cn"], b.report()


def test_an_unparseable_url_is_ignored_not_crashed():
    b = HostBreaker()
    for bad in ("", "not a url", None):
        b.record(bad, False)
    assert b.report() == []


def test_https_and_http_of_one_host_share_a_count():
    """download_attachment retries https -> http, so both must count as one host."""
    b = HostBreaker()
    for i in range(HOST_FAIL_LIMIT):
        b.record(A if i % 2 else A.replace("http://", "https://"), False)
    assert b.is_open(A) is True


def test_the_progress_guard_survives():
    """`0 % 25 == 0` is TRUE, so the `processed and` guard is load-bearing.

    Without it the progress line fires on every row before anything is processed.
    Measured 2026-10-09: combined with a misplaced `continue` it printed 277 KB of
    identical lines and silently skipped 3,654 of 4,164 rows.
    """
    src = (ROOT / "scripts" / "extract_pdf_text.py").read_text(encoding="utf-8")
    assert "if processed and processed % 25 == 0:" in src, (
        "the zero-guard on the progress condition is gone; `0 % 25 == 0` is True")


def test_there_is_exactly_one_progress_print_site():
    """The duplication is what let the indentation bug hide.

    Three inline copies of the progress block meant an 8-space anchor
    `"        processed += 1\n"` could match as a SUBSTRING of the 12-space line
    inside the breaker block, split it, and steal its `continue` — with no single
    place to notice. One `_progress()` helper, called from each site.
    """
    src = (ROOT / "scripts" / "extract_pdf_text.py").read_text(encoding="utf-8")
    assert src.count('print(f"  Progress:') == 1, (
        "more than one progress print site; route them through _progress()")
    assert src.count("_progress()") >= 4, (
        "expected the helper plus at least three call sites")


def test_zero_modulo_is_why_the_guard_exists():
    """The arithmetic fact itself, so the reason is readable without the history."""
    assert 0 % 25 == 0
    assert not (0 and 0 % 25 == 0)


if __name__ == "__main__":
    for fn in list(globals().values()):
        if callable(fn) and getattr(fn, "__name__", "").startswith("test_"):
            fn(); print("ok", fn.__name__)
    print("all host breaker checks passed")
