"""One unreadable attachment must not abort the run.

Measured 2026-10-09: a single `ValueError: document closed or encrypted` propagated
out of extract_text_from_pdf and killed a 6,013-document run after 1,544 documents had
been enriched. The per-10 incremental commits are the only reason that work survived.
A loop that pays a network fetch per row cannot let one bad input lose every row it has
not reached yet, so a parse failure is a ROW-level outcome.

Run: python3 -m pytest tests/test_pdf_extract_resilience.py -v
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

fitz = pytest.importorskip("fitz", reason="PyMuPDF not installed")
from extract_pdf_text import extract_text_from_pdf  # noqa: E402


def _real_pdf(text="中华人民共和国预算法 实施条例 第一章 总则"):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontname="china-s", fontsize=12)
    data = doc.tobytes()
    doc.close()
    return data


def test_a_valid_pdf_still_yields_its_text():
    """The happy path must be untouched by the resilience changes."""
    out = extract_text_from_pdf(_real_pdf())
    assert "预算法" in out, repr(out[:120])


def test_garbage_with_a_pdf_header_returns_empty_not_raise():
    data = b"%PDF-1.7\n" + bytes(range(256)) * 8
    assert extract_text_from_pdf(data) == ""


def test_empty_bytes_return_empty_not_raise():
    assert extract_text_from_pdf(b"") == ""


def test_truncated_pdf_returns_empty_not_raise():
    """A download cut short mid-file is common and must not abort the run."""
    data = _real_pdf()[: len(_real_pdf()) // 3]
    assert extract_text_from_pdf(data) == ""


def test_non_pdf_bytes_return_empty_not_raise():
    assert extract_text_from_pdf(b"this is plainly not a pdf at all") == ""


def test_a_scanned_pdf_with_no_text_layer_returns_empty():
    """szdp publishes its social-assistance tables this way — 0 of 12 extracted."""
    doc = fitz.open()
    doc.new_page()          # a page with no text at all
    data = doc.tobytes()
    doc.close()
    assert extract_text_from_pdf(data) == ""


if __name__ == "__main__":
    for fn in list(globals().values()):
        if callable(fn) and getattr(fn, "__name__", "").startswith("test_"):
            fn(); print("ok", fn.__name__)
    print("all pdf resilience checks passed")
