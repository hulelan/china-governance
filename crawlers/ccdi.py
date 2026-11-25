"""
CCDI-NSC / 中央纪委国家监委网站 (www.ccdi.gov.cn): REACHABILITY PROBE ONLY.

STATUS (2026-11-25): BLOCKED. Not a crawler yet, on purpose.

Every path on www.ccdi.gov.cn, from BOTH the NYC droplet and the Mac, returns
HTTP 200 with a ~750-byte page that is not the site: a Wangsu CDN
(seccaptcha.haplat.net) slider captcha whose hidden `infoString` field
base64-decodes to {"typ": "blacklist", ...}. Measured on /, /scdc/zggb/,
/scdc/sggb/, /scdc/zggb/index_1.html, /yaowenn/, /toutiaon/, /robots.txt and
jjjcb.ccdi.gov.cn (中国纪检监察报); m.ccdi.gov.cn fails TLS (curl exit 35).
Under a status-code check this reads as "reachable" (CLAUDE.md, probe the
body, not the status). It is not, and the site serves no list page, article or
robots.txt we could parse, so no list path, pagination, date marker or
section page count could be verified from here.

We do NOT solve or route around the captcha. A crawler needs a vantage that
the CDN does not blacklist (the same residential / HK question as the MIIT
stubs and the npc bodies). Meanwhile CCDI's 审查调查 announcements are
re-published by 共产党员网 (dangyuan, already crawled) and Xinhua, which is the
available route for that content.

When a vantage exists, run `python3 -m crawlers.ccdi --probe` from it first: it
fetches the candidate sections and reports, per URL, whether the body is the
captcha shell or a real page, and writes nothing.

Usage:
    python3 -m crawlers.ccdi --probe
"""
import argparse
import base64
import json
import re
import sys

from crawlers.base import fetch, log

SITE_KEY = "ccdi"
SITE_NAME = "CCDI-NSC / 中央纪委国家监委网站"
ADMIN_LEVEL = "central"
BASE = "https://www.ccdi.gov.cn"

# Candidate list surfaces, UNVERIFIED (the site never served one). Section paths
# as commonly cited; confirm each from a vantage that sees real pages.
CANDIDATE_SECTIONS = {
    "zggb": "/scdc/zggb/",     # 审查调查 · 中管干部
    "sggb": "/scdc/sggb/",     # 审查调查 · 省管干部
    "yaowen": "/yaowenn/",     # 要闻
    "toutiao": "/toutiaon/",   # 头条 / 权威发布
}

BROWSER_UA = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
    "Accept-Language": "zh-CN,zh;q=0.9",
}

_INFO = re.compile(r'id="infoString"\s+value="([A-Za-z0-9+/=]+)"')


def block_kind(html: str):
    """None for a real page; else a short label for the block shell.

    'captcha:<typ>' when the Wangsu captcha states its type (e.g. 'blacklist'),
    'captcha' when it does not."""
    if "seccaptcha.haplat.net" not in html and "captchaPage" not in html:
        return None
    m = _INFO.search(html)
    if m:
        try:
            typ = json.loads(base64.b64decode(m.group(1))).get("typ")
            if typ:
                return f"captcha:{typ}"
        except (ValueError, json.JSONDecodeError):
            pass
    return "captcha"


def probe() -> int:
    """Fetch the candidate sections; report blocked/real per URL. Writes nothing.
    Returns the number of sections that served a real page."""
    real = 0
    for key, path in [("home", "/")] + list(CANDIDATE_SECTIONS.items()):
        url = BASE + path
        try:
            html = fetch(url, headers=BROWSER_UA)
        except Exception as e:
            print(json.dumps({"section": key, "url": url, "error": str(e)[:120]}))
            continue
        kind = block_kind(html)
        title = re.search(r"<title>([^<]*)", html)
        print(json.dumps({"section": key, "url": url, "bytes": len(html.encode()),
                          "blocked": kind, "title": title.group(1).strip() if title else ""},
                         ensure_ascii=False))
        real += kind is None
    return real


def main():
    ap = argparse.ArgumentParser(description="CCDI reachability probe (no crawl yet)")
    ap.add_argument("--probe", action="store_true", help="byte-check sections, write NOTHING")
    args = ap.parse_args()
    if not args.probe:
        log.error("ccdi is blocked by a CDN captcha (see module docstring); "
                  "only --probe is implemented")
        sys.exit(2)
    n = probe()
    log.info(f"{n} section(s) served a real page")
    sys.exit(0 if n else 1)


if __name__ == "__main__":
    main()
