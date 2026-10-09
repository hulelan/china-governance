"""extract_pdf_text.py must find an attachment URL without saved raw HTML.

Measured 2026-10-09: the script located attachment URLs only by PARSING SAVED RAW
HTML, and the raw-HTML mirror begins 2026-06-08 (the droplet migration), so anything
crawled earlier was skipped forever. 7,802 documents have a body under 400 chars
saying 详见附件 / 文件下载链接; 6,731 carry attachments_json; 6,013 name a PDF; ZERO had
been enriched. The url was in the database the whole time.

Reachability was checked before this was written: the stored https:// url fails on 5
of 6 sampled Shenzhen hosts with `SSL: BAD_ECPOINT` (OpenSSL cannot parse their
elliptic-curve certificates, very likely SM2), and forcing http:// succeeded on 8 of
8 with valid %PDF- magic. download_attachment already retries https -> http.

Run: python3 -m pytest tests/test_attachment_json_fallback.py -v
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from extract_pdf_text import attachment_url_from_json  # noqa: E402

PDF = {"id": 24103, "name": "揭府办[2016]76号 (1).pdf", "type": "file",
       "mime": "application/pdf", "size": "0",
       "url": "http://www.jieyang.gov.cn/attachment/0/24/24103/204269.pdf"}
XLS = {"id": 23713, "name": "揭阳中介服务事项项目清理表（第一批）.xls", "type": "file",
       "mime": "application/vnd.ms-excel", "size": "0",
       "url": "http://www.jieyang.gov.cn/attachment/0/23/23713/202468.xls"}
RAR = {"id": 23538, "name": "32号主动公开.part01.rar", "type": "file",
       "mime": "application/x-rar", "size": "0",
       "url": "http://www.jieyang.gov.cn/attachment/0/23/23538/202456.rar"}


def test_finds_a_pdf_url():
    got = attachment_url_from_json(json.dumps([PDF]))
    assert got == (PDF["url"], ".pdf"), got


def test_prefers_a_pdf_over_an_office_format():
    """A document with both should yield the PDF — fitz reads it, textutil may not."""
    got = attachment_url_from_json(json.dumps([XLS, PDF]))
    assert got[0] == PDF["url"], got


def test_falls_back_to_an_office_format_when_no_pdf():
    got = attachment_url_from_json(json.dumps([XLS]))
    assert got == (XLS["url"], ".xls"), got


def test_ignores_an_unreadable_archive():
    """.rar is not in ATTACH_EXTS — returning it would waste a download."""
    assert attachment_url_from_json(json.dumps([RAR])) is None


def test_empty_and_malformed_inputs_return_none():
    for bad in ("", "[]", "null", None, "not json at all", "{"):
        assert attachment_url_from_json(bad) is None, bad


def test_a_bare_object_not_in_a_list_still_works():
    assert attachment_url_from_json(json.dumps(PDF)) == (PDF["url"], ".pdf")


def test_an_entry_with_no_url_is_skipped_not_crashed():
    got = attachment_url_from_json(json.dumps([{"name": "x.pdf", "mime": "application/pdf"},
                                               PDF]))
    assert got[0] == PDF["url"], got


def test_non_dict_entries_are_skipped():
    assert attachment_url_from_json(json.dumps(["just a string", PDF]))[0] == PDF["url"]


if __name__ == "__main__":
    for fn in list(globals().values()):
        if callable(fn) and getattr(fn, "__name__", "").startswith("test_"):
            fn(); print("ok", fn.__name__)
    print("all attachment-json fallback checks passed")
