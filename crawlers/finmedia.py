"""
Chinese financial / business / tech media crawler (one module, a site registry).

WHY THIS EXISTS. The corpus had 15 `admin_level='media'` sites and none of them
were financial press: a query for the 中国高科 corporate-governance case
(2026-10-30) returned zero, and the reason was a SOURCE gap, not a query bug.
Government sites publish the instrument and, it turns out, plenty of
ADMINISTRATIVE enforcement too. What they do not publish is investor-side and
private-law conflict. Measured 2026-11-05 against 793 financial-press rows and
317,301 government rows (docs/working/finmedia-sources.md): the press runs
5.65x on 索赔, 3.24x on 立案调查 and 1.55x on 起诉, while GOVERNMENT runs 5.9x
on 整改 (8.0% vs 1.4%), 3.5x on 行政处罚 and 11x on 约谈 — because a
行政处罚决定书 is itself a government document. So the layer this buys is the
dispute and the firm-side reaction, not "enforcement" broadly, and the first
framing of it was too strong. The test is also underpowered at n=793, where 1%
is ~8 documents; re-run it once the tier passes a few thousand rows.

The sources split into three tiers by what a NYC datacenter IP can actually get
(probed 2026-11-05 from the droplet; see `docs/working/finmedia-sources.md`):

  Tier 1 — state economic press, clean, highest policy value
    ce        中国经济网 / 经济日报 (central party economic daily)
    jjckb     经济参考报 (Xinhua's own financial paper)
    yicai     第一财经 (Shanghai state-owned)
  Tier 2 — commercial, clean
    jiemian   界面新闻
    eeo       经济观察报
    tmtpost   钛媒体
    huxiu     虎嗅网
  Tier 3 — degraded or unreachable, NOT configured here
    caixin    财新 — reachable but HARD PAYWALLED. Measured: the article <p>
              content is 8 paragraphs / 484-658 CJK chars, i.e. the lede teaser,
              not the article. Configured with paywalled=True so its rows carry
              relation='body=paywall_teaser' and no analysis mistakes a teaser
              for a body.
    thepaper  澎湃 — HTTP 403 from the droplet (WAF geo-block).
    cls       财联社 — SPA; its JSON API demands a request signature (errno
              10012 签名错误). Needs reverse-engineering, deliberately skipped.
    caict     中国信通院 — HTTP 412 (WAF). Blocked, and it is the publisher of
              《智能体发展自律公约》, so that document must come via媒体 coverage.
    stcn      证券时报 — TCP blackhole (000).

BODY EXTRACTION is one <p>-density rule, not seven hand-guessed selectors: keep
every <p> carrying >= MIN_PARA_CJK CJK characters, which drops nav/footer/promo
paragraphs without naming a container. Per-site `body_re` overrides exist for
sites where that was measured to be insufficient. Run `--probe` (writes NOTHING)
to re-measure extraction on live articles before trusting a config change — the
same pattern as `crawlers.pbc --probe`.

Dates: taken from the URL where the URL carries one (ce's tYYYYMMDD, jjckb's
/YYYYMMDD/, eeo's /YYYY/MMDD/), else from the page's own metadata. A site whose
date must be parsed from the page gets `date_re` tried against the HTML.

STRUCTURAL OUTLETS (2026-11-25, tiers 4-6). Thirteen outlets whose articles the
research briefs cited and the corpus missed, added as recurring channel crawls
rather than one-off URL ingests. All byte-checked from the droplet; the list
surface, measured volume and rejected surfaces per outlet are in the registry,
crawlers/finmedia_outlets.py.

  Tier 4 - state / party media, channel-scoped, unfiltered
    cnr       央广网: 财经原创 + 独家报道 + 科技 (index_N.html pagination)
    cctv      央视网: law / tech / economy JSONP channels whole, the general
              `china` channel through the policy title filter, + local.cctv.com
    gmw       光明网 legal / tech / economy channels (NOT the 光明日报 theory
              pages, which are crawlers/theory.py's gmrb_theory)
    bjd       北京日报 (京报网 front page + 客户端传真机)
    cqn       中国质量报 市场监管 channel (总局动态 / 政策法规 / 标准 / 反垄断)
    jschina   中国江苏网 江苏要闻
    chinanews 中新网 财经 (/cj/) + 国内 (/gn/) off the scroll pages
  Tier 5 - high-volume aggregators and trade press, FILTERED by title
    sina      新浪财经 roll API (~2,000 items/day): jjxw/china/tech paths only,
              and only titles matching POLICY_TITLE_RE
    ithome    IT之家 daily list (~250/day, a complete per-day denominator):
              POLICY_TITLE_RE titles only
    nbd       每日经济新闻 要闻 + 重磅原创 columns (unfiltered, capped)
  Tier 6 - other
    rthk      香港电台 大中華 + 財經 (admin_level 'foreign_media')
    tc609     全国数据标准化技术委员会 (admin_level 'central', as tc260)
    szhgh     红歌会网 opinion / 自媒体号 (commentary)

POLICY_TITLE_RE IS AN ALLOWLIST and is used ONLY where a feed is a general
firehose (sina, ithome, cctv `china`). CLAUDE.md prefers a denylist because an
allowlist silently drops the document type nobody anticipated; that risk is
accepted here because the alternative is ~2,500 gadget and stock items a night.
The run logs `filtered N of M` per site so the dropped share is visible, and
`--no-filter` turns it off for a measurement.

`--nightly` uses each site's own `nightly_cap` (default 150) instead of one
--max-docs for a whole tier; an explicit --max-docs still wins. `--pages N`
overrides how many pages of each paginated list / feed are walked (backfill).

Usage:
    python -m crawlers.finmedia --list-sites
    python -m crawlers.finmedia --site jiemian --probe      # measure, write nothing
    python -m crawlers.finmedia --site jiemian
    python -m crawlers.finmedia --tier 1                    # all Tier-1 sites
    python -m crawlers.finmedia                             # every configured site
    python -m crawlers.finmedia --site ce --max-docs 200
    python -m crawlers.finmedia --site jiemian --db documents_new.db
"""
import argparse
import html as H
import json
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urljoin

from crawlers.finmedia_outlets import OUTLETS, POLICY_TITLE_RE, TICKER_RE
from crawlers.claims_outlets import OUTLETS as CLAIMS_OUTLETS

from crawlers.base import (
    REQUEST_DELAY, fetch, init_db, log, next_id,
    save_raw_html, show_stats, store_document, store_site,
)

BROWSER_UA = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
    "Accept-Language": "zh-CN,zh;q=0.9",
}

CST = timezone(timedelta(hours=8))

MIN_PARA_CJK = 12       # a <p> below this is nav/promo/caption, not prose
MIN_PARA_CHARS = 60     # ...unless it is long non-Chinese prose (see extract_body)
MIN_BODY_CJK = 80       # below this the extraction failed; record no body
MIN_BODY_CHARS = 400    # the non-Chinese equivalent
MIN_LINE_CHARS = 40     # fallback: a flattened line this long is a paragraph
MAX_TITLE = 300

SITES = {
    "ce": {
        "name": "China Economic Net / 中国经济网 (经济日报)",
        "base_url": "http://www.ce.cn",
        "tier": 1,
        "publisher": "经济日报·中国经济网",
        "sections": [
            "http://www.ce.cn/",
            "http://www.ce.cn/xwzx/gnsz/gdxw/",
            "http://www.ce.cn/xwzx/gnsz/szyw/",
            "http://scitech.ce.cn/sy/zx/",
            "http://finance.ce.cn/",
            "http://www.ce.cn/cysc/",
        ],
        "art_re": r'https?://[a-z0-9]+\.ce\.cn/[^"\'\s]*?/t\d{8}_\d+\.s?html',
        "date_url": r'/t(\d{4})(\d{2})(\d{2})_\d+\.s?html',
        "date_pats": (r'name="publishdate"[^>]*content="(\d{4})-(\d{2})-(\d{2})',),
    },
    "jjckb": {
        "name": "Economic Information Daily / 经济参考报 (新华社)",
        "base_url": "http://www.jjckb.cn",
        "tier": 1,
        "publisher": "新华社《经济参考报》",
        "sections": [
            "http://www.jjckb.cn/",
            "http://www.jjckb.cn/finance/",
            "http://www.jjckb.cn/industry/",
        ],
        "art_re": r'https?://www\.jjckb\.cn/\d{8}/[0-9a-f]{20,}/c\.html',
        "date_url": r'/(\d{4})(\d{2})(\d{2})/[0-9a-f]{20,}/c\.html',
        "date_pats": (r'name="publishdate"[^>]*content="(\d{4})-(\d{2})-(\d{2})',),
    },
    "yicai": {
        "name": "Yicai / 第一财经",
        "base_url": "https://www.yicai.com",
        "tier": 1,
        "publisher": "第一财经",
        "sections": [
            "https://www.yicai.com/news/",
            "https://www.yicai.com/",
            "https://m.yicai.com/",
            # The three pages above are a snapshot of ~60 links, against ~500 items
            # a day: three brief-cited articles were missed that way. getlatest is
            # the paginated stream behind them (50 a page, ~12 pages a day). Its
            # market tickers are dropped by a DENYLIST (TICKER_RE), not an allowlist.
            {"kind": "yicai_latest", "pages": 12, "name": "最新 (getlatest)",
             "url": "https://www.yicai.com/api/ajax/getlatest?page={p}&pagesize=50"},
        ],
        "title_drop": TICKER_RE,
        "nightly_cap": 400,
        # Everything after the article is a rail of OTHER articles' summaries in
        # <div class="common"><h2>…<p>…, and the share pop-up's instruction
        # line precedes it; both were being stored as body text.
        "body_cut": (r'<body\b', r'id="jb_report"|class="statement"'),
        "para_drop": r'^打开微信，点击底部的“发现”|^使用“扫一扫”即可将网页分享至朋友圈',
        "art_re": r'https?://(?:www|m)\.yicai\.com/news/\d{6,}\.html',
        "date_url": None,
        "date_pats": (r"'actime',\s*'(\d{4})-(\d{2})-(\d{2})",
                      r'"actime"\s*:\s*"(\d{4})-(\d{2})-(\d{2})'),
    },
    "jiemian": {
        "name": "Jiemian News / 界面新闻",
        "base_url": "https://www.jiemian.com",
        "tier": 2,
        "publisher": "界面新闻",
        "sections": [
            "https://www.jiemian.com/",
            "https://m.jiemian.com/",
            "https://www.jiemian.com/lists/85.html",
        ],
        "art_re": r'https?://www\.jiemian\.com/article/\d{5,}\.html',
        "date_url": None,
        "date_pats": (r'publish_?time["\']?\s*[:=]\s*["\']?(\d{4})-(\d{2})-(\d{2})',),
        "date_epoch": r'<span class="date">(\d{9,13})',
    },
    "eeo": {
        "name": "Economic Observer / 经济观察报",
        "base_url": "http://www.eeo.com.cn",
        "tier": 2,
        "publisher": "经济观察报",
        "sections": [
            "http://www.eeo.com.cn/",
            "http://www.eeo.com.cn/finance/",
            "http://www.eeo.com.cn/industry/",
        ],
        "art_re": r'https?://www\.eeo\.com\.cn/\d{4}/\d{4}/\d+\.s?html',
        "date_url": r'/(\d{4})/(\d{2})(\d{2})/\d+\.s?html',
        "date_pats": (r'(\d{4})-(\d{2})-(\d{2}) \d{2}:\d{2}',),
    },
    "tmtpost": {
        "name": "TMTPost / 钛媒体",
        "base_url": "https://www.tmtpost.com",
        "tier": 2,
        "publisher": "钛媒体",
        "sections": [
            "https://www.tmtpost.com/",
            "https://www.tmtpost.com/nictation",       # 快讯 (7x24): newest ~40 only
            # The page above is server-rendered with the newest ~40 flashes, about
            # three hours of a ~300-a-day stream; the rest loads from this API,
            # which answers `"data": {}` unless the app-version header is sent.
            # 8 pages of 40 is about a day. Market tickers go to the denylist.
            {"kind": "tmtpost_word", "pages": 8, "size": 40, "name": "快讯 (word/list API)",
             "headers": {"app-version": "web1.0"},
             "url": "https://api.tmtpost.com/v1/word/list?limit=40&offset={o}&platform=pc"},
        ],
        "title_drop": TICKER_RE,
        "nightly_cap": 200,
        "art_re": r'https?://www\.tmtpost\.com/(?:nictation/)?\d{6,}\.html',
        "min_body_cjk": 40,                             # a 快讯 is one paragraph
        # og:title is "headline-钛媒体官方网站", and the <p> pass swept up the
        # 快讯 ticker and the licence footer that follow </article>.
        "title_strip": r'\s*-\s*钛媒体官方网站$',
        "body_cut": (r'<article\b', r'</article>'),
        # A 快讯 page is another template: no <article>, the text sits bare in
        # one div and the date in .read_num. Neither marker occurs on an article
        # page, so the two templates cannot shadow each other.
        "body_re": r'(?is)<div class="word_main_detail"[^>]*>(.*?)</div>',
        "date_url": None,
        "date_pats": (r'class="time"[^>]*>(\d{4})\.(\d{1,2})\.(\d{1,2})',
                      r'class="read_num"[^>]*>\s*(\d{4})\.(\d{1,2})\.(\d{1,2})'),
    },
    "huxiu": {
        "name": "Huxiu / 虎嗅网",
        "base_url": "https://www.huxiu.com",
        "tier": 2,
        "publisher": "虎嗅网",
        "sections": [
            "https://www.huxiu.com/",
            "https://www.huxiu.com/channel/105.html",
        ],
        "art_re": r'https?://www\.huxiu\.com/article/\d{5,}\.html',
        "date_url": None,
        "date_pats": (r'article:published_time["\'][^>]*content=["\'](\d{4})-(\d{2})-(\d{2})',
                      r'class="article__time"[^>]*>(\d{4})-(\d{2})-(\d{2})'),
    },
    "caixin": {
        "name": "Caixin / 财新网 (paywalled — lede teaser only)",
        "base_url": "https://www.caixin.com",
        "tier": 3,
        "publisher": "财新网",
        "paywalled": True,
        "sections": [
            "https://www.caixin.com/",
            "https://finance.caixin.com/",
            "https://economy.caixin.com/",
        ],
        "art_re": r'https?://[a-z]+\.caixin\.com/\d{4}-\d{2}-\d{2}/\d+\.html',
        "date_url": r'/(\d{4})-(\d{2})-(\d{2})/\d+\.html',
        "date_pats": (),
    },
}

SITES.update(OUTLETS)
# Tier 7: overseas CLAIMS-ONLY sources (crawlers/claims_outlets.py). Every one is
# admin_level 'foreign_media' and claims_only, and crawl() stamps its rows.
SITES.update(CLAIMS_OUTLETS)

# NO generic date fallback on purpose. A loose pattern such as (\d{4})/(\d{1,2})/(\d{1,2})
# matches a CDN upload path long before it matches a publication date: measured
# 2026-11-05, it read "2024-05-20" off tmtpost's image URL and "2016-07-20" off
# huxiu's, i.e. it would have silently written a date two to ten YEARS wrong onto a
# current article. A wrong date is worse than a missing one, because `date_quality`
# can flag the missing one and nothing flags the wrong one. So every pattern below is
# per-site and measured against that site's live HTML; a site with no match stores an
# empty date and is counted in the run's `no-date` tally.

_STRIP = re.compile(r'(?is)<(script|style|noscript|iframe)[^>]*>.*?</\1>')
_COMMENT = re.compile(r'(?s)<!--.*?-->')
_PARA = re.compile(r'(?is)<p[^>]*>(.*?)</p>')
_TAGS = re.compile(r'(?s)<[^>]+>')
_TITLE = re.compile(r'(?is)<title[^>]*>(.*?)</title>')
_OGTITLE = re.compile(r'(?is)<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)')
_H1 = re.compile(r'(?is)<h1[^>]*>(.*?)</h1>')


def _cjk(s: str) -> int:
    return sum(1 for c in s if '一' <= c <= '鿿')


def _flat(frag: str) -> str:
    """Flatten ONE element's inner HTML: tags are deleted, not separated."""
    frag = re.sub(r'(?i)<br\s*/?>', '\n', frag)
    return re.sub(r'[ \t　]+', ' ', H.unescape(_TAGS.sub('', frag))).strip()

def _lines(html: str) -> str:
    """Flatten a WHOLE document: every tag becomes a line break.

    Not _flat. _flat deletes tags, which is right inside one paragraph and wrong
    across a document - it ran the nav strings together with the first real
    paragraph as a single line, so no length filter could separate them and nav
    text landed in the body. Caught by tests/test_finmedia_extract.py.
    """
    html = re.sub(r'(?i)<br\\s*/?>', '\\n', html)
    return re.sub(r'[ \\t]+', ' ', H.unescape(_TAGS.sub('\\n', html)))


def extract_body(html: str, body_re: str = "") -> str:
    """Keep the <p> blocks that carry prose, with a long-line fallback.

    The <p>-density rule serves seven different Chinese markups, but it was
    CJK-ONLY and so could not see non-Chinese prose at all: Business Recorder has
    15 paragraphs of ~250 English characters and Zhong Lun 170 of up to 1,260,
    and both extracted to zero. A paragraph therefore qualifies on CJK count OR
    on raw length.

    Some pages put no prose in <p> whatsoever — npc.gov.cn had 2 paragraphs and
    nda.gov.cn 1, while their flattened text held 1,531 and 777 CJK in long
    lines. When the <p> pass comes back thin, fall back to those long flattened
    lines, which measurement showed ARE the body paragraphs.
    """
    clean = _COMMENT.sub(' ', _STRIP.sub(' ', html))
    if body_re:
        # A named container: the prose is whatever is inside it, <p> or not.
        m = re.search(body_re, clean)
        if m:
            inner = re.sub(r'(?i)</p>|</div>', '\n', m.group(1))
            out = [ln.strip() for ln in _flat(inner).split("\n")]
            return "\n".join(ln for ln in out if ln)
    paras = []
    for frag in _PARA.findall(clean):
        txt = _flat(frag)
        if _cjk(txt) >= MIN_PARA_CJK or len(txt) >= MIN_PARA_CHARS:
            paras.append(txt)
    body = re.sub(r'\n\s*\n+', '\n', "\n".join(paras)).strip()
    if _cjk(body) >= MIN_BODY_CJK or len(body) >= MIN_BODY_CHARS:
        return body

    flat = _lines(clean)
    lines, seen = [], set()
    for line in flat.split("\n"):
        line = line.strip()
        if len(line) < MIN_LINE_CHARS or line in seen:
            continue
        seen.add(line)
        lines.append(line)
    fallback = "\n".join(lines).strip()
    return fallback if len(fallback) > len(body) else body


def extract_title(html: str, cfg: dict = None) -> str:
    cfg = cfg or {}
    pats = tuple(re.compile(p) for p in cfg.get("title_pats", ())) + (_OGTITLE, _H1, _TITLE)
    for pat in pats:
        m = pat.search(html)
        if not m:
            continue
        t = _flat(m.group(1))
        # news <title> is usually "headline_section_outlet"
        t = re.split(r'[_|｜]\s*', t)[0].strip()
        if cfg.get("title_strip"):
            t = re.sub(cfg["title_strip"], '', t).strip()
        # A CJK-only floor made every English page titleless: Business Recorder
        # fetched at 277 KB with a usable <title> and still returned "".
        if _cjk(t) >= 4 or len(t) >= 15:
            return t[:MAX_TITLE]
    return ""


def extract_date(url: str, html: str, cfg: dict) -> str:
    """Date from the URL when it carries one, else this site's measured markers.

    Searches the WHOLE document, not a head window: tmtpost's time span sits at
    ~byte 82k and huxiu's `article:published_time` past 20k, so a windowed search
    silently returned no date for both.
    """
    if cfg.get("date_url"):
        m = re.search(cfg["date_url"], url)
        if m:
            y, mo, d = (int(g) for g in m.groups())
            y = y + 2000 if y < 100 else y         # epochtimes /gb/26/11/23/
            return f"{y:04d}-{mo:02d}-{d:02d}"
    for pat in cfg.get("date_pats", ()):
        m = re.search(pat, html)
        if m:
            y, mo, d = m.groups()
            return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    if cfg.get("date_utc"):
        # An ISO timestamp the page states in UTC ("…T17:30:00.000+0000"): the
        # publication DAY is the Beijing one, so 17:30 UTC is the next date.
        m = re.search(cfg["date_utc"], html)
        if m:
            try:
                dt = datetime.strptime(m.group(1).replace(" ", "T"), "%Y-%m-%dT%H:%M:%S")
                return dt.replace(tzinfo=timezone.utc).astimezone(CST).strftime("%Y-%m-%d")
            except ValueError:
                pass
    if cfg.get("date_epoch"):
        m = re.search(cfg["date_epoch"], html)
        if m:
            v = int(m.group(1))
            v = v // 1000 if v > 1e11 else v
            if 946_684_800 < v < 2_524_608_000:        # 2000-01-01 .. 2050-01-01
                return datetime.fromtimestamp(v, CST).strftime("%Y-%m-%d")
    return ""


# ----------------------------------------------------------------- list feeds
# A feed is a JSON / JSONP list API. Each returns [(url, list_title)] for ONE
# page of it; the list title is what the allowlist / denylist is tested against,
# so a filtered site never pays a fetch for an item it is going to drop.

def _feed_sina_roll(text: str) -> list:
    data = json.loads(text)["result"].get("data") or []
    return [(i.get("url", ""), i.get("title", "")) for i in data]


def _feed_cctv_jsonp(text: str) -> list:
    m = re.search(r'(?s)^[^({]*\((.*)\)\s*;?\s*$', text.strip())
    data = json.loads(m.group(1) if m else text)
    return [(i.get("url", ""), i.get("title", "")) for i in data["data"]["list"]]


def _feed_yicai_latest(text: str) -> list:
    out = []
    for i in json.loads(text):
        u = i.get("url") or ""
        if u.startswith("/"):
            u = "https://www.yicai.com" + u
        out.append((u, i.get("NewsTitle") or i.get("Title") or ""))
    return out


def _feed_tmtpost_word(text: str) -> list:
    data = json.loads(text).get("data")
    if not isinstance(data, list):          # {} = the header was not accepted
        raise ValueError("tmtpost word/list returned no list (app-version header?)")
    return [(f"https://www.tmtpost.com/nictation/{i['guid']}.html", i.get("title", ""))
            for i in data if str(i.get("guid", "")).isdigit()]


def _feed_rss(text: str) -> list:
    """Generic RSS 2.0 / RDF feed: one (link, title) per <item>. Titles matter,
    because an allowlisted feed is filtered on them before any fetch."""
    out = []
    for item in re.findall(r'(?is)<item\b[^>]*>(.*?)</item>', text):
        link = re.search(r'(?is)<link>\s*(?:<!\[CDATA\[)?\s*(.*?)\s*(?:\]\]>)?\s*</link>', item)
        title = re.search(r'(?is)<title>\s*(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?\s*</title>', item)
        if link:
            out.append((H.unescape(link.group(1).strip()),
                        H.unescape(title.group(1).strip()) if title else ""))
    return out


FEEDS = {"sina_roll": _feed_sina_roll, "cctv_jsonp": _feed_cctv_jsonp,
         "yicai_latest": _feed_yicai_latest, "tmtpost_word": _feed_tmtpost_word,
         "rss": _feed_rss}

_ANCHOR = re.compile(r'(?is)<a\b[^>]*?href=["\']([^"\'#]{6,300})["\'][^>]*>(.*?)</a>')


def canon(url: str, cfg: dict) -> str:
    """Canonical article URL for dedup (bjd lists one story as .json and .html)."""
    if cfg.get("url_sub"):
        url = re.sub(cfg["url_sub"][0], cfg["url_sub"][1], url)
    if cfg.get("quote_url"):
        # Opt-in per site (dw): percent-encode non-ASCII path characters, keeping
        # any existing %XX escapes, so the URL is fetchable AND one string per article.
        url = quote(url, safe=":/?#[]@!$&'()*+,;=%")
    return url


def keep_title(title: str, cfg: dict, filtered: bool) -> bool:
    """The list-title gate. An item with NO list title passes a denylist and
    fails an allowlist: an allowlist needs evidence, a denylist needs a match."""
    if cfg.get("title_drop") and title and cfg["title_drop"].search(title):
        return False
    if filtered:
        # A site may carry its own allowlist (the tier-7 claims sources use
        # claims_outlets.ELITE_TITLE_RE); otherwise the policy allowlist.
        keep = cfg.get("title_keep") or POLICY_TITLE_RE
        return bool(title) and bool(keep.search(title))
    return True


def links_in(html: str, base: str, cfg: dict) -> list:
    """[(canonical article url, anchor text)] in one list page, in page order.

    Anchors first, because they carry the title a filter needs; then a raw scan
    for URLs that sit outside any <a> (an RSS <link>, a Nuxt JSON payload).
    """
    art = re.compile(cfg["art_re"])
    out, pos = [], {}
    for href, inner in _ANCHOR.findall(html):
        u = canon(urljoin(base, H.unescape(href.strip())), cfg)
        if not art.fullmatch(u):
            continue
        txt = _flat(inner)
        if u not in pos:
            pos[u] = len(out)
            out.append((u, txt))
        elif len(txt) > len(out[pos[u]][1]):        # image link first, headline later
            out[pos[u]] = (u, txt)
    for m in re.finditer(cfg.get("link_re") or cfg["art_re"], html):
        u = canon(m.group(0), cfg)
        if art.fullmatch(u) and u not in pos:
            pos[u] = len(out)
            out.append((u, ""))
    return out


def list_pages(cfg: dict, pages: int = 0, today: datetime = None) -> list:
    """Every list surface for a site as (kind, url, filtered, headers). kind is
    'html' or a FEEDS key. `pages` > 0 overrides each surface's nightly depth.

    All of them live in cfg["sections"], told apart by shape (see the registry
    docstring): a str, a (template, n[, first]) tuple, or a feed dict.
    """
    flt = bool(cfg.get("filter"))
    today = today or datetime.now(CST)
    out = []
    for sec in cfg.get("sections", ()):
        if isinstance(sec, str):
            out.append(("html", sec, flt, None))
        elif isinstance(sec, dict):          # {p} = page number, {o} = row offset
            out += [(sec["kind"], sec["url"].format(p=p, o=(p - 1) * sec.get("size", 0)),
                     bool(sec.get("filter", flt)), sec.get("headers"))
                    for p in range(1, 1 + (pages or sec.get("pages", 1)))]
        else:
            tmpl, n = sec[0], pages or sec[1]
            first = sec[2] if len(sec) > 2 else 1
            if "{d}" in tmpl:
                out += [("html", tmpl.format(d=(today - timedelta(days=k)).strftime(cfg["daily_fmt"])),
                         flt, None) for k in range(n)]
            else:
                out += [("html", tmpl.format(p=p), flt, None) for p in range(first, first + n)]
    return out


def discover(cfg: dict, max_pages: int = 99, pages: int = 0, use_filter: bool = True) -> list:
    """Collect [(article url, list title)] from the site's list surfaces, in order."""
    art = re.compile(cfg["art_re"])
    found, seen, dropped = [], set(), 0
    for kind, url, filtered, extra in list_pages(cfg, pages)[:max_pages]:
        try:
            text = fetch(url, headers={**BROWSER_UA, **(extra or {})})
            if kind == "html":
                items = links_in(text, url, cfg)
            else:
                items = [(canon(u, cfg), _flat(t)) for u, t in FEEDS[kind](text)]
                items = [(u, t) for u, t in items if art.fullmatch(u)]
        except Exception as e:
            log.warning(f"  list {url}: {str(e)[:120]}")
            continue
        n0 = len(found)
        for u, t in items:
            if u in seen:
                continue
            seen.add(u)
            if use_filter and not keep_title(t, cfg, filtered):
                dropped += 1
                continue
            found.append((u, t))
        log.info(f"  {url[:100]} → +{len(found) - n0} (total {len(found)})")
        time.sleep(REQUEST_DELAY)
    for u in cfg.get("seeds", ()):
        if u not in seen:
            seen.add(u)
            found.append((u, ""))
    if dropped:
        log.info(f"  filtered {dropped} of {dropped + len(found)} list items by title")
    return found


def cut_html(html: str, cfg: dict) -> str:
    """The article container, by this site's `body_cut` = (start_re, end_re).

    The <p>-density rule has no notion of WHERE a paragraph sits, so a footer or
    a related-articles rail printed in <p> lands in the body: measured
    2026-11-25, yicai bodies ended with five other articles' summaries, tmtpost's
    with the 快讯 ticker, sina's with its site map. Markers are matched on the
    RAW html, before comments are stripped, because the cleanest ones ARE
    comments (`<!--enpcontent-->`). No start match means an unknown template:
    the page is returned whole rather than emptied.
    """
    if cfg.get("body_js"):
        # The body shipped as a JS string literal that a script injects into an
        # empty container (cctv's 2026 template): _STRIP would delete it whole.
        m = re.search(cfg["body_js"], html)
        if m and _cjk(m.group(1)) >= MIN_PARA_CJK:
            return "<div>" + m.group(1).replace("\\'", "'").replace('\\"', '"').replace("\\/", "/") + "</div>"
    bc = cfg.get("body_cut")
    if not bc:
        return html
    m = re.search(bc[0], html)
    if not m:
        return html
    rest = html[m.end():]
    if bc[1]:
        e = re.search(bc[1], rest)
        if e:
            rest = rest[:e.start()]
    return "<div " + rest            # the start marker usually ends mid-tag


def site_body(html: str, cfg: dict) -> str:
    """Body text by this site's rules: container cut, extraction, chrome lines."""
    body = extract_body(cut_html(html, cfg), cfg.get("body_re", ""))
    if cfg.get("para_drop"):                 # a chrome line the site prints in a <p>
        body = "\n".join(ln for ln in body.split("\n")
                         if not re.search(cfg["para_drop"], ln.strip()))
    return body


def parse_article(url: str, html: str, cfg: dict, list_title: str = "") -> dict:
    """title / body / date for one fetched article page, by this site's config."""
    title = extract_title(html, cfg) or list_title[:MAX_TITLE]
    body = site_body(html, cfg)
    floor = cfg.get("min_body_cjk", MIN_BODY_CJK)
    return {"title": title, "body": body if _cjk(body) >= floor else "",
            "body_cjk": _cjk(body), "date": extract_date(url, html, cfg)}


CLAIMS_RELATION = "claims=outlet_attributed"


def relation_for(cfg: dict) -> str:
    """The provenance tags a stored row carries. A claims_only site's rows are
    marked so any reader of `relation` can tell a claim attributed to an outlet
    from a document an issuing body published."""
    tags = []
    if cfg.get("paywalled"):
        tags.append("body=paywall_teaser")
    if cfg.get("claims_only"):
        tags.append(CLAIMS_RELATION)
    return ";".join(tags)


def crawl(conn, site_key: str, *, max_docs: int = 0, probe: bool = False,
          max_pages: int = 99, fetch_bodies: bool = True, pages: int = 0,
          use_filter: bool = True, urls: list = None) -> int:
    cfg = SITES[site_key]
    if not probe:
        store_site(conn, site_key, {"name": cfg["name"], "base_url": cfg["base_url"],
                                    "admin_level": cfg.get("level", "media")})
    log.info(f"[{site_key}] {cfg['name']} (tier {cfg['tier']})")
    if urls:
        found = [(canon(u, cfg), "") for u in urls]
    else:
        found = discover(cfg, max_pages, pages, use_filter)
    log.info(f"[{site_key}] discovered {len(found)} article urls")

    stored = thin = nodate = shown = 0
    for url, list_title in found:
        if max_docs and stored >= max_docs:
            break
        if not probe and conn.execute(
                "SELECT 1 FROM documents WHERE url=? AND url != ''", (url,)).fetchone():
            continue
        try:
            html = fetch(url, headers=BROWSER_UA)
        except Exception as e:
            log.warning(f"  {url}: {e}")
            continue
        art = parse_article(url, html, cfg, list_title)
        title, date_pub = art["title"], art["date"]
        body = art["body"] if fetch_bodies else ""
        if not title:
            log.warning(f"  no title: {url}")
            continue
        if not date_pub:
            nodate += 1
        if fetch_bodies and not body:
            thin += 1
            log.warning(f"  thin body ({art['body_cjk']} cjk): {title[:40]}")
        if probe:
            print(json.dumps({"site": site_key, "url": url, "date": date_pub,
                              "title": title[:60], "body_cjk": _cjk(body),
                              "body_head": body[:90].replace("\n", " "),
                              "body_tail": body[-50:].replace("\n", " ")},
                             ensure_ascii=False))
            shown += 1
            if shown >= 3 and not urls:
                break
            time.sleep(REQUEST_DELAY)
            continue

        doc_id = next_id(conn)
        rel = relation_for(cfg)
        raw = save_raw_html(site_key, doc_id, html) if body else ""
        if store_document(conn, site_key, {
            "id": doc_id, "title": title, "date_published": date_pub,
            "body_text_cn": body, "url": url, "publisher": cfg["publisher"],
            "classify_genre_name": cfg.get("genre", "news"),
            "relation": rel, "raw_html_path": raw,
        }):
            stored += 1
        if stored and stored % 20 == 0:
            conn.commit()
            log.info(f"  [{site_key}] stored {stored}", )
        time.sleep(REQUEST_DELAY)

    if not probe:
        conn.commit()
    log.info(f"[{site_key}] done: {stored} new, {thin} thin-body, {nodate} no-date")
    return stored


def main():
    ap = argparse.ArgumentParser(description="Chinese financial/business media crawler")
    ap.add_argument("--site", help="one site key")
    ap.add_argument("--tier", type=int, choices=(1, 2, 3, 4, 5, 6, 7),
                    help="all sites in a tier (7 = overseas claims-only sources)")
    ap.add_argument("--list-sites", action="store_true")
    ap.add_argument("--probe", action="store_true",
                    help="measure discovery + extraction on 3 articles, write NOTHING")
    ap.add_argument("--url", action="append",
                    help="with --site: parse exactly this article URL instead of "
                         "discovering (repeatable; use with --probe to test one page)")
    ap.add_argument("--max-docs", type=int, default=None,
                    help="new documents per site (0 = no cap; default 0, or the "
                         "site's nightly_cap under --nightly)")
    ap.add_argument("--nightly", action="store_true",
                    help="cap each site at its own nightly_cap (default 150)")
    ap.add_argument("--pages", type=int, default=0,
                    help="walk N pages of every paginated list/feed (backfill); "
                         "default is each surface's nightly depth")
    ap.add_argument("--no-filter", action="store_true",
                    help="ignore title allow/deny lists (measurement only)")
    ap.add_argument("--max-pages", type=int, default=99)
    ap.add_argument("--list-only", action="store_true", help="metadata only, no bodies")
    ap.add_argument("--db")
    args = ap.parse_args()

    if args.list_sites:
        for k, c in sorted(SITES.items(), key=lambda kv: (kv[1]["tier"], kv[0])):
            flag = " [PAYWALLED]" if c.get("paywalled") else ""
            flag += " [title-filtered]" if c.get("filter") else ""
            flag += " [CLAIMS-ONLY]" if c.get("claims_only") else ""
            print(f"  tier{c['tier']}  {k:9} cap {c.get('nightly_cap', 150):3}  {c['name']}{flag}")
        return

    # No --site and no --tier keeps meaning tiers 1-2, as before the 2026-11-25
    # outlets: a bare run must not silently grow by thirteen sites.
    keys = ([args.site] if args.site else
            [k for k, c in SITES.items() if c["tier"] == args.tier] if args.tier else
            [k for k, c in SITES.items() if c["tier"] in (1, 2)])
    for k in keys:
        if k not in SITES:
            log.error(f"unknown site: {k}")
            return
    if args.url and not args.site:
        log.error("--url needs --site (which site's parser to use)")
        return

    conn = init_db(args.db) if args.db else init_db()
    total = 0
    for k in keys:
        cap = (args.max_docs if args.max_docs is not None else
               SITES[k].get("nightly_cap", 150) if args.nightly else 0)
        total += crawl(conn, k, max_docs=cap, probe=args.probe, pages=args.pages,
                       max_pages=args.max_pages, fetch_bodies=not args.list_only,
                       use_filter=not args.no_filter, urls=args.url)
    log.info(f"TOTAL: {total} new documents across {len(keys)} site(s)")
    if not args.probe:
        show_stats(conn)


if __name__ == "__main__":
    main()
