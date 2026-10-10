"""`_is_timeout`: the predicate that decides whether to pay a SECOND fetch.

extract_pdf_text's http fallback exists for ONE reason, recorded in CLAUDE.md: Shenzhen
government hosts serve certificates OpenSSL cannot parse (`SSL: BAD_ECPOINT`, very
likely SM2). A timeout is not a TLS failure, so retrying over http after one pays a
second full timeout for a cause that cannot apply.

Measured 2026-10-10: a dead row cost 2 x 30 s, so HostBreaker needed 8 x 60 s = EIGHT
MINUTES to retire each unresponsive host, and a 57-minute run enriched 160 of 800
documents while cycling through several of them. The sign that it was cycling rather
than stuck: 43 s of CPU, a frozen WAL, and an ESTABLISHED socket whose fd timestamp kept
advancing.

Getting this predicate wrong in EITHER direction is costly, so both are pinned: a true
TLS error must still retry (that is the fallback's whole purpose), and a timeout must
not.
"""
import socket
import ssl
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.extract_pdf_text import _is_timeout  # noqa: E402


def test_a_bare_read_timeout_is_a_timeout():
    """urllib surfaces a read timeout as socket.timeout, an alias of TimeoutError."""
    assert _is_timeout(socket.timeout("timed out")) is True


def test_a_connect_timeout_wrapped_in_urlerror_is_a_timeout():
    """A connect timeout arrives as URLError whose .reason is the timeout itself."""
    assert _is_timeout(URLError(socket.timeout("timed out"))) is True


def test_the_sm2_certificate_error_is_NOT_a_timeout():
    """`SSL: BAD_ECPOINT` is exactly what the http fallback was written for."""
    assert _is_timeout(ssl.SSLError(1, "[SSL: BAD_ECPOINT] bad ecpoint")) is False


def test_an_ssl_error_wrapped_in_urlerror_is_NOT_a_timeout():
    assert _is_timeout(URLError(ssl.SSLError(1, "[SSL: BAD_ECPOINT] bad ecpoint"))) is False


def test_a_connection_refused_is_not_a_timeout():
    """Refused is instant and cheap; the fallback may legitimately help."""
    assert _is_timeout(URLError(ConnectionRefusedError(111, "Connection refused"))) is False


def test_an_http_error_is_not_a_timeout():
    assert _is_timeout(HTTPError("http://x", 404, "Not Found", {}, None)) is False


def test_an_unrelated_exception_is_not_a_timeout():
    assert _is_timeout(ValueError("nonsense")) is False


def test_none_is_handled():
    assert _is_timeout(None) is False


def test_a_self_referential_reason_cannot_loop_forever():
    """URLError.reason pointing at itself must terminate, not hang the crawler."""
    e = URLError("x")
    e.reason = e
    assert _is_timeout(e) is False


def test_an_ssl_timeout_prefers_the_ssl_answer():
    """ssl.SSLError wins over TimeoutError when a class is somehow both: the fallback
    exists for TLS, so when TLS is implicated we still want the retry."""
    class Both(ssl.SSLError, TimeoutError):
        pass
    assert _is_timeout(Both("ambiguous")) is False
