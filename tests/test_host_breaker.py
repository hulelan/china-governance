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


if __name__ == "__main__":
    for fn in list(globals().values()):
        if callable(fn) and getattr(fn, "__name__", "").startswith("test_"):
            fn(); print("ok", fn.__name__)
    print("all host breaker checks passed")
