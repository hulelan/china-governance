"""crawlers.ccdi: the block detector must recognise the CDN captcha shell that
www.ccdi.gov.cn serves with HTTP 200 (fixture saved from the droplet 2026-11-25,
session token redacted), and must not flag an ordinary page."""
from pathlib import Path

from crawlers.ccdi import block_kind

FIX = Path(__file__).parent / "fixtures" / "ccdi"


def test_blacklist_captcha_detected():
    html = (FIX / "captcha_blacklist.html").read_text(encoding="utf-8")
    assert block_kind(html) == "captcha:blacklist"


def test_captcha_without_info_string():
    assert block_kind('<link href="https://seccaptcha.haplat.net/css/captcha.css">') == "captcha"


def test_real_page_not_flagged():
    html = "<html><head><title>中央纪委国家监委网站</title></head><body><ul><li>审查调查</li></ul></body></html>"
    assert block_kind(html) is None
