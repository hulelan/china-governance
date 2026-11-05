"""
Chinese financial / business / tech media crawler (one module, a site registry).

WHY THIS EXISTS. The corpus had 15 `admin_level='media'` sites and none of them
were financial press: a query for the 中国高科 corporate-governance case
(2026-10-30) returned zero, and the reason was a SOURCE gap, not a query bug.
Government sites publish the instrument; they do not publish the enforcement,
the dispute, or the firm-side reaction. That implementation layer is where the
political-economy replications need evidence, so it has to be crawled.

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
from urllib.parse import urljoin

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
MIN_BODY_CJK = 80       # below this the extraction failed; record no body
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
        ],
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
        ],
        "art_re": r'https?://www\.tmtpost\.com/\d{6,}\.html',
        "date_url": None,
        "date_pats": (r'class="time"[^>]*>(\d{4})\.(\d{1,2})\.(\d{1,2})',),
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
    frag = re.sub(r'(?i)<br\s*/?>', '\n', frag)
    return re.sub(r'[ \t　]+', ' ', H.unescape(_TAGS.sub('', frag))).strip()


def extract_body(html: str) -> str:
    """Keep the <p> blocks that carry prose. One rule for every site.

    Nav links, share widgets and captions live in short <p> elements; article
    paragraphs do not. Thresholding on CJK count therefore separates them
    without naming a container, which is what lets one rule serve seven sites
    with different markup.
    """
    clean = _COMMENT.sub(' ', _STRIP.sub(' ', html))
    paras = []
    for frag in _PARA.findall(clean):
        txt = _flat(frag)
        if _cjk(txt) >= MIN_PARA_CJK:
            paras.append(txt)
    return re.sub(r'\n\s*\n+', '\n', "\n".join(paras)).strip()


def extract_title(html: str) -> str:
    for pat in (_OGTITLE, _H1, _TITLE):
        m = pat.search(html)
        if not m:
            continue
        t = _flat(m.group(1))
        # news <title> is usually "headline_section_outlet"
        t = re.split(r'[_|｜]\s*', t)[0].strip()
        if _cjk(t) >= 4:
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
            y, mo, d = m.groups()
            return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    for pat in cfg.get("date_pats", ()):
        m = re.search(pat, html)
        if m:
            y, mo, d = m.groups()
            return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    if cfg.get("date_epoch"):
        m = re.search(cfg["date_epoch"], html)
        if m:
            v = int(m.group(1))
            v = v // 1000 if v > 1e11 else v
            if 946_684_800 < v < 2_524_608_000:        # 2000-01-01 .. 2050-01-01
                return datetime.fromtimestamp(v, CST).strftime("%Y-%m-%d")
    return ""


def discover(cfg: dict, max_pages: int) -> list:
    """Collect article URLs from the site's listing sections, in order."""
    art_re = re.compile(cfg["art_re"])
    found, seen = [], set()
    for sec in cfg["sections"][:max_pages]:
        try:
            html = fetch(sec, headers=BROWSER_UA)
        except Exception as e:
            log.warning(f"  section {sec}: {e}")
            continue
        n0 = len(found)
        for m in art_re.finditer(html):
            u = m.group(0)
            if u not in seen:
                seen.add(u)
                found.append(u)
        # relative hrefs on the same host
        for m in re.finditer(r'href=["\']([^"\'#]{6,200})["\']', html):
            u = urljoin(sec, m.group(1))
            if art_re.fullmatch(u) and u not in seen:
                seen.add(u)
                found.append(u)
        log.info(f"  {sec} → +{len(found) - n0} (total {len(found)})")
        time.sleep(REQUEST_DELAY)
    return found


def crawl(conn, site_key: str, *, max_docs: int = 0, probe: bool = False,
          max_pages: int = 99, fetch_bodies: bool = True) -> int:
    cfg = SITES[site_key]
    if not probe:
        store_site(conn, site_key, {"name": cfg["name"], "base_url": cfg["base_url"],
                                    "admin_level": "media"})
    log.info(f"[{site_key}] {cfg['name']} (tier {cfg['tier']})")
    urls = discover(cfg, max_pages)
    log.info(f"[{site_key}] discovered {len(urls)} article urls")

    stored = thin = nodate = 0
    for i, url in enumerate(urls):
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
        title = extract_title(html)
        body = extract_body(html) if fetch_bodies else ""
        date_pub = extract_date(url, html, cfg)
        if not title:
            log.warning(f"  no title: {url}")
            continue
        if not date_pub:
            nodate += 1
        if fetch_bodies and _cjk(body) < MIN_BODY_CJK:
            thin += 1
            log.warning(f"  thin body ({_cjk(body)} cjk): {title[:40]}")
            body = ""
        if probe:
            print(json.dumps({"site": site_key, "url": url, "date": date_pub,
                              "title": title[:60], "body_cjk": _cjk(body),
                              "body_head": body[:90].replace("\n", " ")},
                             ensure_ascii=False))
            if i >= 2:
                break
            time.sleep(REQUEST_DELAY)
            continue

        doc_id = next_id(conn)
        rel = "body=paywall_teaser" if cfg.get("paywalled") else ""
        raw = save_raw_html(site_key, doc_id, html) if body else ""
        if store_document(conn, site_key, {
            "id": doc_id, "title": title, "date_published": date_pub,
            "body_text_cn": body, "url": url, "publisher": cfg["publisher"],
            "classify_genre_name": "news", "relation": rel, "raw_html_path": raw,
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
    ap.add_argument("--tier", type=int, choices=(1, 2, 3), help="all sites in a tier")
    ap.add_argument("--list-sites", action="store_true")
    ap.add_argument("--probe", action="store_true",
                    help="measure discovery + extraction on 3 articles, write NOTHING")
    ap.add_argument("--max-docs", type=int, default=0)
    ap.add_argument("--max-pages", type=int, default=99)
    ap.add_argument("--list-only", action="store_true", help="metadata only, no bodies")
    ap.add_argument("--db")
    args = ap.parse_args()

    if args.list_sites:
        for k, c in sorted(SITES.items(), key=lambda kv: (kv[1]["tier"], kv[0])):
            flag = " [PAYWALLED]" if c.get("paywalled") else ""
            print(f"  tier{c['tier']}  {k:9} {c['name']}{flag}")
        return

    keys = ([args.site] if args.site else
            [k for k, c in SITES.items() if c["tier"] == args.tier] if args.tier else
            [k for k, c in SITES.items() if c["tier"] in (1, 2)])
    for k in keys:
        if k not in SITES:
            log.error(f"unknown site: {k}")
            return

    conn = init_db(args.db) if args.db else init_db()
    total = 0
    for k in keys:
        total += crawl(conn, k, max_docs=args.max_docs, probe=args.probe,
                       max_pages=args.max_pages, fetch_bodies=not args.list_only)
    log.info(f"TOTAL: {total} new documents across {len(keys)} site(s)")
    if not args.probe:
        show_stats(conn)


if __name__ == "__main__":
    main()
