#!/usr/bin/env python3
"""Ingest a list of article/document URLs into the corpus, one row each.

WHY. Research briefs cite specific documents by URL. Chasing each one by hand is
the work this replaces: give it the brief's URLs and it resolves every host to a
site, fetches, extracts title/body/date, and stores the row with its provenance.
It is the lever — the next brief is one command, not another hunt.

HOST RESOLUTION IS AN EXPLICIT TABLE, NOT A MATCH. A fuzzy `root in base_url`
lookup resolved `www.gov.cn` to site keys `szpsq`, `sz` and `stic`, because
"gov.cn" is a substring of "szpsq.sz.gov.cn". That is this project's most
frequent bug shape (CLAUDE.md, "a hand-maintained table silently bounds a
measurement"): the lookup returns a clean answer for the wrong reason. So HOSTS
below maps an exact netloc to an exact site_key, and an unmapped host is a LOUD
refusal listing what was unmapped — never a guess. `--allow-new` is the explicit
opt-in that creates a site for it.

FOREIGN SOURCES GET THEIR OWN admin_level. CLAUDE.md records that `media` is its
own admin_level and that folding it into "non-central" overstated sub-national
diffusion eightfold. Foreign media would repeat that error one level out, so
non-Chinese sources are stored as admin_level='foreign_media': present as
evidence, impossible to mistake for a Chinese government or Chinese media
document in any level-split measure.

DATES come from the URL wherever the host's path carries one. These patterns are
anchored to known path shapes (`/20261103/<hex>/c.html`, `/2026-11/03/c_<id>.htm`),
which is what keeps them safe — an unanchored date regex matches a CDN upload
path first, as measured in crawlers/finmedia.py.

Usage:
    python3 scripts/ingest_urls.py --urls-file brief_urls.txt --dry-run
    python3 scripts/ingest_urls.py --urls-file brief_urls.txt
    cat urls.txt | python3 scripts/ingest_urls.py --tag "brief-2026-11-04"
    python3 scripts/ingest_urls.py --urls-file u.txt --allow-new    # create sites
    python3 scripts/ingest_urls.py --urls-file u.txt --db documents_new.db
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crawlers.base import (                                      # noqa: E402
    REQUEST_DELAY, fetch, init_db, log, next_id,
    save_raw_html, show_stats, store_document, store_site,
)
from crawlers.finmedia import (                                  # noqa: E402
    BROWSER_UA, _cjk, extract_body, extract_title, MIN_BODY_CJK,
    SITES as FIN_SITES, canon, extract_date, site_body,
)

CN_GOV, CN_MEDIA, FOREIGN = "central", "media", "foreign_media"

# netloc -> (site_key, display name, admin_level). Exact hosts only.
HOSTS = {
    # --- central government / party bodies already in the corpus ---
    "www.gov.cn":            ("gov",      "State Council / 中国政府网", CN_GOV),
    "www.cac.gov.cn":        ("cac",      "Cyberspace Administration / 国家网信办", CN_GOV),
    "www.samr.gov.cn":       ("samr",     "SAMR / 国家市场监督管理总局", CN_GOV),
    "www.mofcom.gov.cn":     ("mofcom",   "MOFCOM / 商务部", CN_GOV),
    "wap.miit.gov.cn":       ("miit",     "MIIT / 工业和信息化部", CN_GOV),
    "www.miit.gov.cn":       ("miit",     "MIIT / 工业和信息化部", CN_GOV),
    "www.npc.gov.cn":        ("npc",      "NPC / 全国人大", CN_GOV),
    "www.nea.gov.cn":        ("nea",      "National Energy Administration / 国家能源局", CN_GOV),
    "www.nda.gov.cn":        ("nda",      "National Data Administration / 国家数据局", CN_GOV),
    "www.mfa.gov.cn":        ("mfa",      "MFA / 外交部", CN_GOV),
    "www.fmprc.gov.cn":      ("mfa",      "MFA / 外交部", CN_GOV),
    "aqygzj.mofcom.gov.cn":  ("mofcom",   "MOFCOM / 商务部", CN_GOV),
    "www.tc609.org.cn":      ("tc609",    "National Data Standardization TC / 全国数据标准化技术委员会", CN_GOV),
    # --- sub-national government already in the corpus ---
    "www.shanghai.gov.cn":   ("sh",       "Shanghai Municipal Government / 上海市人民政府", "provincial"),
    "www.sasac.gov.cn":      ("sasac",    "SASAC / 国务院国资委", CN_GOV),
    "www.12371.cn":          ("dangyuan", "CPC Members Network / 共产党员网", CN_GOV),
    "www.ndrc.gov.cn":       ("ndrc",     "National Development and Reform Commission", CN_GOV),
    # 最高人民法院 press releases (court.gov.cn/fabu/xiangqing/): the Court's own
    # announcements of first-instance sentences of senior officials. Same body as
    # the existing `spc` site key, so the same key.
    "www.court.gov.cn":      ("spc",      "Supreme People's Court (最高人民法院)", CN_GOV),
    # --- Chinese state media already in the corpus ---
    "www.news.cn":           ("xinhua",   "Xinhua / 新华社", CN_MEDIA),
    "english.news.cn":       ("xinhua_en", "Xinhua English", CN_MEDIA),
    "www.xinhuanet.com":     ("xinhua",   "Xinhua / 新华网", CN_MEDIA),
    "www.qstheory.cn":       ("qstheory", "Qiushi (求是网)", CN_MEDIA),
    "lw.xinhuanet.com":      ("xinhua_lw", "Outlook Weekly / 新华社《瞭望》", CN_MEDIA),
    "politics.people.com.cn": ("people",  "People's Daily / 人民网", CN_MEDIA),
    "finance.people.com.cn": ("people",   "People's Daily / 人民网", CN_MEDIA),
    "paper.people.com.cn":   ("people_rmrb", "People's Daily print / 人民日报", CN_MEDIA),
    # --- Chinese media newly configured ---
    "www.ce.cn":             ("ce",       "China Economic Net / 中国经济网", CN_MEDIA),
    "scitech.ce.cn":         ("ce",       "China Economic Net / 中国经济网", CN_MEDIA),
    "city.ce.cn":            ("ce",       "China Economic Net / 中国经济网", CN_MEDIA),
    "finance.ce.cn":         ("ce",       "China Economic Net / 中国经济网", CN_MEDIA),
    "www.jjckb.cn":          ("jjckb",    "Economic Information Daily / 经济参考报", CN_MEDIA),
    "jjckb.xinhuanet.com":   ("jjckb",    "Economic Information Daily / 经济参考报", CN_MEDIA),
    "www.yicai.com":         ("yicai",    "Yicai / 第一财经", CN_MEDIA),
    "m.yicai.com":           ("yicai",    "Yicai / 第一财经", CN_MEDIA),
    "www.jiemian.com":       ("jiemian",  "Jiemian News / 界面新闻", CN_MEDIA),
    "m.jiemian.com":         ("jiemian",  "Jiemian News / 界面新闻", CN_MEDIA),
    "www.21jingji.com":      ("21jingji", "21st Century Business Herald / 21世纪经济报道", CN_MEDIA),
    "m.21jingji.com":        ("21jingji", "21st Century Business Herald / 21世纪经济报道", CN_MEDIA),
    "www.chinanews.com.cn":  ("chinanews", "China News Service / 中国新闻网", CN_MEDIA),
    "www.chinanews.com":     ("chinanews", "China News Service / 中国新闻网", CN_MEDIA),
    "www.tmtpost.com":       ("tmtpost",  "TMTPost / 钛媒体", CN_MEDIA),
    "www.hn.chinanews.com.cn": ("chinanews_hn", "China News Service Hunan / 中新网湖南", CN_MEDIA),
    "www.cnfin.com":         ("cnfin",    "China Financial Information / 中国金融信息网", CN_MEDIA),
    "news.qq.com":           ("qqnews",   "Tencent News / 腾讯新闻", CN_MEDIA),
    "www.guandian.cn":       ("guandian", "Guandian / 观点网 (real estate)", CN_MEDIA),
    "finance.eastmoney.com": ("eastmoney", "East Money / 东方财富网", CN_MEDIA),
    "cn.wicinternet.org":    ("wic",      "World Internet Conference / 世界互联网大会", CN_GOV),
    "www.wicinternet.org":   ("wic",      "World Internet Conference / 世界互联网大会", CN_GOV),
    # --- structural outlets (crawlers/finmedia_outlets.py, 2026-11-25) ---
    "www.cnr.cn":            ("cnr",      "China National Radio / 央广网", CN_MEDIA),
    "finance.cnr.cn":        ("cnr",      "China National Radio / 央广网", CN_MEDIA),
    "news.cnr.cn":           ("cnr",      "China National Radio / 央广网", CN_MEDIA),
    "tech.cnr.cn":           ("cnr",      "China National Radio / 央广网", CN_MEDIA),
    "news.cctv.com":         ("cctv",     "CCTV / 央视网", CN_MEDIA),
    "local.cctv.com":        ("cctv",     "CCTV / 央视网", CN_MEDIA),
    "finance.sina.com.cn":   ("sina",     "Sina Finance / 新浪财经", CN_MEDIA),
    "legal.gmw.cn":          ("gmw",      "Guangming Online / 光明网", CN_MEDIA),
    "tech.gmw.cn":           ("gmw",      "Guangming Online / 光明网", CN_MEDIA),
    "economy.gmw.cn":        ("gmw",      "Guangming Online / 光明网", CN_MEDIA),
    "xinwen.bjd.com.cn":     ("bjd",      "Beijing Daily / 北京日报", CN_MEDIA),
    "rss2.bjd.com.cn":       ("bjd",      "Beijing Daily / 北京日报", CN_MEDIA),
    "www.cqn.com.cn":        ("cqn",      "China Quality News / 中国质量报", CN_MEDIA),
    "www.ithome.com":        ("ithome",   "ITHome / IT之家", CN_MEDIA),
    "www.nbd.com.cn":        ("nbd",      "National Business Daily / 每日经济新闻", CN_MEDIA),
    "jsnews.jschina.com.cn": ("jschina",  "China Jiangsu Net / 中国江苏网", CN_MEDIA),
    "www.szhgh.com":         ("szhgh",    "Red Song Society / 红歌会网", CN_MEDIA),
    # --- purge-source URLs (data/purges/officials.json, 2026-11-25) ---
    "cn.chinadaily.com.cn":  ("chinadaily", "China Daily / 中国日报网", CN_MEDIA),
    "language.chinadaily.com.cn": ("chinadaily", "China Daily / 中国日报网", CN_MEDIA),
    "news.ifeng.com":        ("ifeng",    "Phoenix News (凤凰网)", CN_MEDIA),
    "news.sina.com.cn":      ("sina",     "Sina Finance / 新浪财经", CN_MEDIA),
    "news.sina.cn":          ("sina",     "Sina Finance / 新浪财经", CN_MEDIA),
    "www.bjnews.com.cn":     ("bjnews",   "Beijing News / 新京报", CN_MEDIA),
    "m.mp.oeeee.com":        ("oeeee",    "Southern Metropolis Daily / 南方都市报 (奥一网)", CN_MEDIA),
    "www.rmzxw.com.cn":      ("rmzxw",    "CPPCC Daily / 人民政协网 (人民政协报)", CN_MEDIA),
    "www.thepaper.cn":       ("thepaper", "The Paper (澎湃新闻)", CN_MEDIA),
    # --- foreign / English-language: separate admin_level on purpose ---
    # RTHK is Hong Kong's public broadcaster: 境外 for this corpus's purposes,
    # so it must not read as mainland media in a level-split measure.
    "news.rthk.hk":          ("rthk",     "RTHK / 香港電台", FOREIGN),
    "www.reuters.com":       ("reuters",  "Reuters", FOREIGN),
    "www.nytimes.com":       ("nytimes",  "New York Times", FOREIGN),
    "www.brecorder.com":     ("brecorder", "Business Recorder (Pakistan)", FOREIGN),
    "www.investing.com":     ("investing", "Investing.com", FOREIGN),
    "news.bloomberglaw.com": ("bloomberglaw", "Bloomberg Law", FOREIGN),
    "www.govinfo.gov":       ("govinfo",  "US GPO / Federal Register", FOREIGN),
    "en.zhonglun.com":       ("zhonglun", "Zhong Lun Law Firm (EN analysis)", FOREIGN),
    "www.chinaon.ai":        ("chinaon",  "ChinaOn.ai", FOREIGN),
    # 香港01, a Hong Kong outlet: 境外 like rthk.
    "global.hk01.com":       ("hk01",     "HK01 / 香港01", FOREIGN),
    # China Digital Times (Berkeley-founded, overseas). An AGGREGATOR that mirrors
    # PRC texts, often ones since deleted at the source: foreign_media because the
    # PUBLISHER is overseas, even when the text it carries is a PRC document. A
    # mirror is evidence that a text existed, not a PRC issuance.
    "chinadigitaltimes.net": ("cdt",      "China Digital Times / 中国数字时代", FOREIGN),
}

BASE_URL = {h: f"{urlparse('https://' + h).scheme}://{h}" for h in HOSTS}

# URL date shapes, anchored to a path form so they cannot match a CDN upload path.
URL_DATE = (
    r'/(\d{4})-(\d{2})/(\d{2})/[a-z]',                   # cac /2026-10/23/c_179…, wic /2026-11/02/content_…
    r'/(\d{4})(\d{2})(\d{2})/[0-9a-f]{20,}/c\.html',    # news.cn, nea, jjckb
    r'/(\d{4})(\d{2})(\d{2})/[0-9a-f]{20,}',            # news.cn variants
    r'/n1/(\d{4})/(\d{2})(\d{2})/c\d',                  # people.com.cn
    r'/t(\d{4})(\d{2})(\d{2})_\d+',                     # npc, ce, mfa, cnr
    r'/t(\d{4})(\d{2})(\d{2})_s[0-9a-f]+\.shtml',        # jschina
    r'/(\d{4})/(\d{2})-(\d{2})/\d+\.shtml',             # chinanews
    r'/article/(\d{4})(\d{2})(\d{2})/',                 # 21jingji, guandian
    r'/(\d{4})/(\d{2})/(\d{2})/ARTI[A-Za-z0-9]+\.shtml',  # cctv
    r'/(\d{4})-(\d{2})-(\d{2})/doc-[a-z0-9]+\.shtml',    # sina
    r'/(\d{4})-(\d{2})-(\d{2})/detail-[a-z0-9]+\.d\.html',  # news.sina.cn
    r'/(\d{4})-(\d{2})-(\d{2})/\d{8,}\.shtml',         # news.sina.com.cn (2012)
    r'/(?:articles|WeMedia|[A-Za-z]+)/(\d{4})-(\d{2})-(\d{2})/\d+\.html',  # nbd, szhgh
    r'/k2/\d+-(\d{4})(\d{2})(\d{2})\.htm',              # rthk
    r'/a/(\d{4})(\d{2})(\d{2})\d{8,}\.html',             # eastmoney /a/202611063924849165.html
    r'/detail/(\d{4})(\d{2})(\d{2})/',                  # cnfin
    r'FR-(\d{4})-(\d{2})-(\d{2})',                      # govinfo Federal Register
    r'/(\d{4})/(\d{2})/(\d{2})/',                       # nytimes
    r'-(\d{4})-(\d{2})-(\d{2})/?$',                     # reuters slug tail
    r'/content/(\d{4})(\d{2})/(\d{2})/',                # paper.people.com.cn
    r'/(\d{4})(\d{2})/(\d{2})/',                        # misc YYYYMM/DD
    r'/(\d{4})(\d{2})(\d{2})\d{6,}',                    # nda: /1031/20261031151459…
)

META_DATE = (
    r'name="publishdate"[^>]*content="(\d{4})-(\d{2})-(\d{2})',
    r'article:published_time["\'][^>]*content=["\'](\d{4})-(\d{2})-(\d{2})',
    r'"datePublished"\s*:\s*"(\d{4})-(\d{2})-(\d{2})',
    r"'actime',\s*'(\d{4})-(\d{2})-(\d{2})",
    r'class="time"[^>]*>(\d{4})\.(\d{1,2})\.(\d{1,2})',
    r'(\d{4})-(\d{2})-(\d{2})[ T]\d{2}:\d{2}',
)


def url_date(url: str) -> str:
    path = urlparse(url).path
    for pat in URL_DATE:
        m = re.search(pat, path)
        if m:
            y, mo, d = (int(g) for g in m.groups())
            if 1990 <= y <= 2035 and 1 <= mo <= 12 and 1 <= d <= 31:
                return f"{y:04d}-{mo:02d}-{d:02d}"
    return ""


def meta_date(html: str) -> str:
    for pat in META_DATE:
        m = re.search(pat, html)
        if m:
            y, mo, d = (int(g) for g in m.groups())
            if 1990 <= y <= 2035 and 1 <= mo <= 12 and 1 <= d <= 31:
                return f"{y:04d}-{mo:02d}-{d:02d}"
    return ""


# Per-site title rules for hosts outside the finmedia registry, tried BEFORE the
# generic extractor: (one-group page patterns, a prefix/suffix to cut). Each was
# measured on the live page (2026-11-25): court.gov.cn's <title> is the section
# name "权威发布 - 中华人民共和国最高人民法院" on every press release, with the
# headline in the first class="title"; rmzxw's first <h1> is the breadcrumb
# "首页>要闻要闻"; rmrbwap's <title> is "人民日报\r\n-\r\n<headline>".
TITLE_RULES = {
    # 2015 pages wrap the headline in a <span>: <div class="title"><span>…</span>
    "spc":         ((r'class="title">\s*(?:<span>)?\s*([^<]{6,200}?)\s*<',), ""),
    "rmzxw":       ((r'<title>\s*([^<]{6,200}?)\s*——人民政协网',), ""),
    "people_rmrb": ((), r'^人民日报\s*-\s*'),
}


def site_title(html: str, site_key: str, cfg) -> str:
    pats, cut = TITLE_RULES.get(site_key, ((), ""))
    for pat in pats:
        m = re.search(pat, html)
        if m and _cjk(m.group(1)) >= 4:
            return re.sub(r'\s+', ' ', m.group(1)).strip()
    t = extract_title(html, cfg)
    if cut:
        t = re.sub(cut, "", t).strip()
    return re.sub(r'\s+', ' ', t).strip() if cut else t


def iri_to_uri(url: str) -> str:
    """Percent-encode a non-ASCII path (global.hk01.com/即时中国/...): urllib
    refuses an IRI with 'ascii codec can't encode'. The row keeps the URL as
    given, so it still matches the URL a brief or dataset cites."""
    return quote(url, safe=":/?#[]@!$&'()*+,;=%~")


def read_urls(path: str | None) -> list:
    raw = Path(path).read_text() if path else sys.stdin.read()
    urls, seen = [], set()
    for line in raw.splitlines():
        line = line.strip().strip('`",\'')
        if not line.startswith(("http://", "https://")):
            continue
        if line not in seen:
            seen.add(line)
            urls.append(line)
    return urls


def resolve(url: str) -> tuple | None:
    return HOSTS.get(urlparse(url).netloc.lower())


def ingest(conn, urls: list, *, tag: str, dry_run: bool, allow_new: bool,
           date: str = "") -> dict:
    unmapped = sorted({urlparse(u).netloc.lower() for u in urls if not resolve(u)})
    if unmapped and not allow_new:
        log.error("UNMAPPED HOSTS — add them to HOSTS or pass --allow-new:")
        for h in unmapped:
            log.error(f"    {h}")
        return {"unmapped": unmapped}

    tally = {"stored": 0, "held": 0, "failed": 0, "thin": 0, "nodate": 0, "new_sites": []}
    seen_sites = set()
    for url in urls:
        got = resolve(url)
        host = urlparse(url).netloc.lower()
        if not got:
            level = FOREIGN if not host.endswith((".cn", ".com.cn")) else CN_MEDIA
            got = (re.sub(r'[^a-z0-9]+', '_', host).strip('_')[:24], host, level)
            if got[0] not in tally["new_sites"]:
                tally["new_sites"].append(got[0])
        site_key, site_name, level = got
        # A host whose site is in the finmedia registry is parsed by THAT site's
        # measured rules (title suffix, body container, date marker) and
        # deduplicated on its canonical URL; tc609's <meta PubDate> is a
        # regeneration stamp that the generic META_DATE fallback would have
        # stored as the date.
        cfg = FIN_SITES.get(site_key)
        if cfg:
            url = canon(url, cfg)

        if conn.execute("SELECT 1 FROM documents WHERE url=? AND url != ''", (url,)).fetchone():
            tally["held"] += 1
            log.info(f"  HELD   {url}")
            continue
        try:
            html = fetch(iri_to_uri(url), headers=BROWSER_UA)
        except Exception as e:
            tally["failed"] += 1
            log.warning(f"  FAIL   {url}: {str(e)[:90]}")
            continue

        title = site_title(html, site_key, cfg)
        body = site_body(html, cfg) if cfg else extract_body(html)
        # An operator-asserted --date wins: a URL date is the page's posting
        # date, which for a reposted instrument is not its promulgation date.
        # A registry site with its own date markers NEVER falls through to the
        # generic META_DATE guess: no match there means the date is unknown.
        if cfg and (cfg.get("date_pats") or cfg.get("date_url")):
            date_pub = date or extract_date(url, html, cfg) or url_date(url)
        else:
            date_pub = date or url_date(url) or meta_date(html)
        if not title:
            tally["failed"] += 1
            log.warning(f"  NOTITLE {url}")
            continue
        if _cjk(body) < MIN_BODY_CJK and len(body) < 400:
            tally["thin"] += 1
        if not date_pub:
            tally["nodate"] += 1

        if dry_run:
            print(json.dumps({"site": site_key, "level": level, "date": date_pub,
                              "cjk": _cjk(body), "chars": len(body),
                              "title": title[:62], "url": url}, ensure_ascii=False))
            continue

        # store_site's upsert rewrites sid / tree_json / last_crawled, which a
        # crawler-owned site (gkmlpt keeps its sid and tree there) must not lose to
        # a one-URL ingest: create the site only when it does not exist yet.
        if site_key not in seen_sites and not conn.execute(
                "SELECT 1 FROM sites WHERE site_key=?", (site_key,)).fetchone():
            store_site(conn, site_key, {"name": site_name,
                                        "base_url": BASE_URL.get(host, f"https://{host}"),
                                        "admin_level": level})
            seen_sites.add(site_key)
        doc_id = next_id(conn)
        raw = save_raw_html(site_key, doc_id, html)
        if store_document(conn, site_key, {
                "id": doc_id, "title": title, "date_published": date_pub,
                "body_text_cn": body, "url": url, "publisher": site_name,
                "classify_genre_name": "news",
                "relation": f"ingest=url_list;tag={tag}", "raw_html_path": raw}):
            tally["stored"] += 1
            log.info(f"  NEW    [{site_key}] {date_pub or '????-??-??'} {title[:50]}")
        if tally["stored"] and tally["stored"] % 10 == 0:
            conn.commit()
        time.sleep(REQUEST_DELAY)

    if not dry_run:
        conn.commit()
    return tally


def main():
    ap = argparse.ArgumentParser(description="Ingest a list of document URLs into the corpus")
    ap.add_argument("--urls-file", help="file of URLs, one per line (default: stdin)")
    ap.add_argument("--tag", default="url_list", help="provenance tag written to relation")
    ap.add_argument("--dry-run", action="store_true", help="fetch + extract, write NOTHING")
    ap.add_argument("--allow-new", action="store_true",
                    help="create a site for an unmapped host instead of refusing")
    ap.add_argument("--list-hosts", action="store_true")
    ap.add_argument("--date", default="",
                    help="YYYY-MM-DD to store for every URL in this run, overriding "
                         "the URL/meta date (use for an instrument reposted later)")
    ap.add_argument("--db")
    args = ap.parse_args()

    if args.list_hosts:
        for h, (k, n, lv) in sorted(HOSTS.items(), key=lambda kv: (kv[1][2], kv[1][0])):
            print(f"  {lv:13} {k:14} {h:26} {n}")
        return

    urls = read_urls(args.urls_file)
    if not urls:
        log.error("no URLs on input")
        return
    log.info(f"{len(urls)} unique URLs")
    conn = init_db(args.db) if args.db else init_db()
    if args.date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
        log.error(f"--date must be YYYY-MM-DD, got {args.date!r}")
        return
    t = ingest(conn, urls, tag=args.tag, dry_run=args.dry_run,
               allow_new=args.allow_new, date=args.date)
    log.info(f"RESULT: {json.dumps(t, ensure_ascii=False)}")
    if not args.dry_run and t.get("stored"):
        show_stats(conn)


if __name__ == "__main__":
    main()
