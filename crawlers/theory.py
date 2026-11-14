"""
Party-theory and academic venues (one module, a site registry).

WHY THIS EXISTS. The global-discourse map (docs/research/global-discourse-map.md)
sorts documents by SPEAKER TYPE, and two of its types were thin: "party theory"
held only the qstheory.cn daily feed (`qstheory`, a news-like stream that began
in late 2025) and 共产党员网, and "research" held a handful of think-tank sites.
The venues where the Party's theoretical line and the academy's reception of it
are actually argued — the journal 《求是》 itself, 《红旗文稿》, the Central Party
School's 学习时报, 光明日报's theory pages and CASS's 中国社会科学报 — were absent.

Every source here was probed from the droplet's NYC IP on 2026-11-12, body bytes
checked, not HTTP status (see the module report / CLAUDE.md "Source ACCESS map"):

  party theory (admin_level='media', ontology leaf media_party_theory)
    qiushi       《求是》 journal, issue by issue. qstheory.cn/qs/mulu.htm -> year
                 page -> issue page -> article. 2019- (the mulu lists 2019 on).
    hongqi       《红旗文稿》, same three-level layout under /hqwglist/mulu.htm. 2020-.
    studytimes   学习时报网 (中央党校报刊社). TRS section lists, 34 pages deep each
                 (~2.5 years). The e-paper host paper.cntheory.com returns HTTP 418
                 with a 0-byte body from the droplet, so the web edition it is.
    gmrb_theory  光明日报 THEORY PAGES only, from the e-paper: for each day, read the
                 page list and keep pages whose name matches THEORY_PAGE_RE
                 (理论 / 哲学 / 史学 / 光明讲坛 / 学术 ...). Two URL dialects: the
                 Founder e-paper (`nbs.D110000gmrb_NN.htm`) up to 2025-12-31 and the
                 `layout/YYYYMM/DD/node_NN.html` one from 2026-01-01.
    rmlt         人民论坛 (人民日报社) magazine archive: 《人民论坛》 and
                 《人民论坛·学术前沿》, year page -> issue page -> article.
  research (admin_level='research', ontology leaf research)
    cssn         中国社会科学网 / 中国社会科学报 (CASS). Selected subject sections:
                 区域国别学, 国家安全学, 国际观察, 政治学, 马克思主义, 哲学.
    aisixiang    爱思想 (added 2026-11-14). An aggregator: academics' journal essays,
                 officials' 求是/人民日报 pieces and lectures, reposted with the origin
                 on a closing `摘自：《社会科学》2025年第12期` line (kept in `relation` as
                 origin=). Walked by ARTICLE ID, which is sequential (/data/<id>.html,
                 185,621 on 2026-11-14, ~55 a day), so a range is a complete denominator.
                 A missing id is a soft 404: HTTP 200, a 4.9 KB 提示信息 page, no <h3>.
                 Speaker type `research` is a SITE-level label over mixed authors; a
                 per-document speaker would have to come from origin= and author=.

  NOT reachable / not configured:
    文化纵横 www.21bcr.com — TCP connect timeout (resolves to 121.196.165.91);
             wenhua.org.cn does not resolve from the droplet.
    学习时报 e-paper paper.cntheory.com — HTTP 418, 0 bytes.

DATES come from the page or the issue, never the crawl day:
  qiushi       the issue's COVER date. 《求是》 is published on the 1st and 16th, so
               issue N of year Y is month (N+1)//2, day 1 if N is odd else 16. This
               is how the journal is cited (《求是》2024年第9期 = 2024-05-01); the
               page's own `pubtime` is the web posting time and can lag by days.
               The issue tag is read from the article's own 来源：《求是》YYYY/NN.
  hongqi       the article page's `pubtime` (its issues do not follow a fixed
               calendar: 2024 第2期 is 01-29, 第3期 02-08).
  studytimes, cssn   the tYYYYMMDD stamp in the article URL (the CMS publication
               date), cross-checked against the page's own date line in tests.
  gmrb_theory  the e-paper day in the URL (the print date).
  rmlt         the /YYYY/MMDD/ path of the article URL.
  aisixiang    the page's 更新时间, i.e. the REPOST date on aisixiang. The original
               venue's issue is in origin= and is often months earlier.

IDS. Rows are written to a SEPARATE DB (`--db documents_theory_<site>.db`), and
`scripts/merge_db.py` reassigns ids on merge. Raw HTML is therefore NOT saved:
`raw_html_path` would name a file under the pre-merge id, which is exactly the
dangling-pointer bug CLAUDE.md records for mofcom. Bodies are stored directly.

Provenance in `relation`: `theory=<site>;issue=<tag>;author=<name>;page=<版名>`.

Usage:
    python -m crawlers.theory --list-sites
    python -m crawlers.theory --site qiushi --probe              # 3 articles, write NOTHING
    python -m crawlers.theory --site qiushi --db documents_theory_qiushi.db
    python -m crawlers.theory --site gmrb_theory --since 2023-01-01 --until 2023-12-31
    python -m crawlers.theory --site cssn --max-pages 15 --max-docs 3000
    python -m crawlers.theory --site qiushi --recent             # nightly: newest issues only
    python -m crawlers.theory --site aisixiang --min-id 170000 --db documents_theory_asx.db
"""
import argparse
import html as H
import json
import re
import time
from datetime import date, datetime, timedelta
from urllib.parse import urljoin

from crawlers.base import (
    REQUEST_DELAY, commit_with_retry, fetch, init_db, log, next_id,
    show_stats, store_document, store_site,
)

BROWSER_UA = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
    "Accept-Language": "zh-CN,zh;q=0.9",
}

MIN_BODY_CJK = 80          # below this the extraction failed; store no body
MAX_TITLE = 300

# A 光明日报 page name that carries theory/academic content. Measured on the page
# lists: 理论 / 理论·国家社科基金 / 理论·党史 / 理论·经济 / 哲学 / 史学 / 光明讲坛 /
# 光明学术 / 光明智库 / 思想 (incl. 习近平新时代中国特色社会主义思想专刊). News pages
# (要闻, 国际新闻, 教科新闻, 文化新闻) never match.
THEORY_PAGE_RE = re.compile(r"理论|哲学|史学|光明讲坛|学术|智库|思想|马克思主义|文史")

SITES = {
    "qiushi": {
        "name": "Qiushi journal / 《求是》杂志",
        "base_url": "http://www.qstheory.cn",
        "admin_level": "media", "speaker": "party_theory", "tier": 1,
        "kind": "qs_journal", "publisher": "求是杂志社",
        "mulu": "https://www.qstheory.cn/qs/mulu.htm",
        "issue_label": "求是", "cover_date": True, "min_year": 2019,
    },
    "hongqi": {
        "name": "Red Flag Manuscript / 《红旗文稿》",
        "base_url": "http://www.qstheory.cn",
        "admin_level": "media", "speaker": "party_theory", "tier": 1,
        "kind": "qs_journal", "publisher": "求是杂志社《红旗文稿》",
        "mulu": "https://www.qstheory.cn/hqwglist/mulu.htm",
        "issue_label": "红旗文稿", "cover_date": False, "min_year": 2019,
    },
    "studytimes": {
        "name": "Study Times / 学习时报 (中央党校)",
        "base_url": "https://www.studytimes.cn",
        "admin_level": "media", "speaker": "party_theory", "tier": 1,
        "kind": "trs_list", "publisher": "学习时报",
        "list_ext": "html",
        # studytimes article URLs always sit under the listed section; requiring
        # that drops the site-footer links (联系我们 / 版权声明 / 许可证, all
        # /gyllw/2021...) that every list page carries
        "same_section": True,
        # theory sections only; 新闻头条 (xwtt) is wire copy and skipped
        "sections": ["lltt", "llsd", "llwp", "sxll", "ddjs", "mzfz", "dsgs", "jjsh",
                     "ldly", "llly", "ddsj", "kjqy", "dszx", "stwm", "whjy"],
        "title_re": r'<div class="font_36">\s*(.*?)\s*</div>',
        "body_start": r'id="detail"',
        "body_end": (r"【版权声明】", r'<div class="xian_gray'),
        "source_re": r"来源：([^&<]{2,40}?)\s*(?:&nbsp;|<)",
    },
    "gmrb_theory": {
        "name": "Guangming Daily theory pages / 光明日报·理论版",
        "base_url": "https://epaper.gmw.cn/gmrb/",
        "admin_level": "media", "speaker": "party_theory", "tier": 1,
        "kind": "gmw_epaper", "publisher": "光明日报",
        "min_date": "2019-01-01",
    },
    "rmlt": {
        "name": "People's Tribune / 人民论坛 (杂志 + 学术前沿)",
        "base_url": "https://www.rmlt.com.cn",
        "admin_level": "media", "speaker": "party_theory", "tier": 2,
        "kind": "rmlt_mag", "publisher": "人民论坛杂志社",
        "magazines": {"A": "人民论坛", "frontiers": "人民论坛·学术前沿"},
        "min_year": 2019,
    },
    "cssn": {
        "name": "Chinese Social Sciences Net / 中国社会科学网·中国社会科学报",
        "base_url": "https://www.cssn.cn",
        "admin_level": "research", "speaker": "research", "tier": 1,
        "kind": "trs_list", "publisher": "中国社会科学网",
        "list_ext": "shtml",
        "sections": [
            "qygbx", "gjaqx",                                    # 区域国别学, 国家安全学
            "gjgc/gjgc_gcld", "gjgc/gjgc_gjdt", "gjgc/hqxx",     # 国际观察
            "zzx/lltt_gjsj", "zzx/lltt_zzll", "zzx/zgzz", "zzx/zzzd", "zzx/gjzl",
            "zzx/zzx_rdjj", "zzx/zzx_bjtj",                       # 政治学
            "mkszy/mkszy_mkzyzgh", "mkszy/mkszy_mkszyjbll", "mkszy/mkszy_gwmkszyyj",
            "mkszy/mkszy_zdtj",                                   # 马克思主义
            "zx/mkszyzx", "zx/wgzx", "zx/zgzx", "zx/kjrw", "zx/zx_rdkx",   # 哲学
        ],
        "title_re": r'<h1 class="qt_article_title">\s*(.*?)\s*</h1>',
        "body_start": r"TRS_Editor",
        "body_end": (r'<div class="content_zz', r'<div class="warp_center_links',
                     r"<script"),
        "source_re": r'qt_article_source"><font>来源：</font>\s*([^<]{2,60})',
        "author_re": r'qt_article_author"><font>作者：</font>\s*([^<]{1,60})',
    },
    "aisixiang": {
        "name": "Aisixiang / 爱思想",
        "base_url": "https://www.aisixiang.com",
        "admin_level": "research", "speaker": "research", "tier": 2,
        "kind": "asx_ids", "publisher": "爱思想",
        "recent_ids": 150,          # ~3 days at ~55 ids a day
    },
}

_STRIP = re.compile(r"(?is)<(script|style|noscript|iframe)[^>]*>.*?</\1>")
_COMMENT = re.compile(r"(?s)<!--(?!/?enpcontent).*?-->")
_BLOCK = re.compile(r"(?i)</?(p|div|br|li|h[1-6]|tr|table|section)\b[^>]*>")
_TAGS = re.compile(r"(?s)<[^>]+>")


def cjk(s: str) -> int:
    return sum(1 for c in s if "一" <= c <= "鿿")


_EDITOR_LINE = re.compile(r"^[（(\[【]?\s*(?:责编|责任编辑|编辑)\s*[：:/].{0,40}$"
                          r"|^声明：本文为.{0,80}$")


def flatten(frag: str) -> str:
    """HTML fragment -> text, one line per block element, blank lines dropped.
    A trailing editor credit line (（责编：X）, 责任编辑：X) is dropped."""
    frag = _COMMENT.sub(" ", _STRIP.sub(" ", frag))
    frag = _BLOCK.sub("\n", frag)
    txt = H.unescape(_TAGS.sub("", frag)).replace("　", " ").replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in txt.split("\n")]
    lines = [ln for ln in lines if ln]
    while lines and _EDITOR_LINE.match(lines[-1]):
        lines.pop()
    return "\n".join(lines)


def clean_title(raw: str) -> str:
    t = re.sub(r"\s+", " ", H.unescape(_TAGS.sub(" ", raw))).strip()
    return t[:MAX_TITLE]


def slice_between(html: str, start: str, ends) -> str:
    m = re.search(start, html)
    if not m:
        return ""
    i = m.end()
    if not start.startswith("<"):          # matched inside a tag: skip to its end
        gt = html.find(">", i)
        i = gt + 1 if gt >= 0 else i
    j = len(html)
    for e in ends:
        k = re.compile(e).search(html, i)
        if k and k.start() < j:
            j = k.start()
            if not e.startswith("<"):      # marker inside a tag: cut at that tag
                lt = html.rfind("<", i, j)
                j = lt if lt >= 0 else j
    return html[i:j]


# ── Qiushi / 红旗文稿 ──────────────────────────────────────────────────────

# per-issue editorial digests: they restate the issue's articles, so storing them
# would double-count every argument the issue makes
SKIP_TITLES = {"本期导读", "本期重点推荐", "本期导航", "编者按"}

_QS_ISSUE_TAG = re.compile(r"来源：\s*《(求是|红旗文稿)》\s*(\d{4})\s*/\s*(\d{1,2})")
_QS_PUBTIME = re.compile(r'class="pubtime">\s*(\d{4})-(\d{2})-(\d{2})')
_QS_AUTHOR = re.compile(r'class="appellation">\s*作者：\s*([^<]{1,60}?)\s*<')
_QS_H1 = re.compile(r"(?is)<h1[^>]*>(.*?)</h1>")


def qs_cover_date(year: int, issue: int) -> str:
    """《求是》 cover date: issue N appears on the 1st (odd N) or 16th (even N)."""
    if not 1 <= issue <= 24:
        return ""
    return f"{year:04d}-{(issue + 1) // 2:02d}-{1 if issue % 2 else 16:02d}"


def qs_url_date(url: str) -> str:
    """Fallback only: the posting date in a qstheory article URL, used when the
    page carries no pubtime (3 of ~1,200 红旗文稿 articles in the backfill)."""
    m = (re.search(r"/(\d{4})-(\d{2})/(\d{2})/c_\d+\.htm", url)
         or re.search(r"/(\d{4})(\d{2})(\d{2})/[0-9a-f]{32}/c\.html", url))
    return "-".join(m.groups()) if m else ""


def canon_qs(url: str) -> str:
    """The existing `qstheory` crawler stores http://www.qstheory.cn/..., so use
    the same spelling or merge_db's URL dedup cannot see a held copy."""
    u = urljoin("https://www.qstheory.cn/", url)
    return re.sub(r"^https?://(?:www\.)?qstheory\.cn", "http://www.qstheory.cn", u)


def parse_qs_article(html: str, cfg: dict) -> dict:
    m = _QS_H1.search(html)
    title = clean_title(m.group(1)) if m else ""
    tag = _QS_ISSUE_TAG.search(html)
    issue = f"{tag.group(2)}/{int(tag.group(3)):02d}" if tag else ""
    d = ""
    if tag and cfg.get("cover_date"):
        d = qs_cover_date(int(tag.group(2)), int(tag.group(3)))
    if not d:
        p = _QS_PUBTIME.search(html)
        if p:
            d = "-".join(p.groups())
    a = _QS_AUTHOR.search(html)
    body = flatten(slice_between(html, r'class="highlight"',
                                 (r'class="xl_ewm', r"扫描二维码", r'class="fs-text')))
    return {"title": title, "date": d, "issue": issue,
            "author": a.group(1).strip() if a else "", "body": body}


def _links(html: str, base: str):
    for m in re.finditer(r'<a[^>]+href=["\']?([^"\'\s>]+)["\']?[^>]*>(.*?)</a>', html, re.S):
        yield urljoin(base, m.group(1)), clean_title(m.group(2))


def discover_qs(cfg: dict, recent: bool):
    """mulu -> year pages -> issue pages -> (article url, issue label) in order."""
    mulu = fetch(cfg["mulu"], headers=BROWSER_UA)
    years = []
    for u, txt in _links(mulu, cfg["mulu"]):
        m = re.fullmatch(r"(\d{4})年", txt)
        if m and int(m.group(1)) >= cfg["min_year"] and u not in [y for _, y in years]:
            years.append((int(m.group(1)), u))
    years.sort(reverse=True)
    if recent:          # two years, so early January still sees December's issues
        years = years[:2]
    label = cfg["issue_label"]
    for y, yu in years:
        time.sleep(REQUEST_DELAY)
        try:
            yh = fetch(yu, headers=BROWSER_UA)
        except Exception as e:
            log.warning(f"  year {y}: {e}")
            continue
        issues = []
        for u, txt in _links(yh, yu):
            m = re.search(rf"《{label}》(\d{{4}})年第(\d+)期", txt)
            if m and (int(m.group(1)), int(m.group(2)), u) not in issues:
                issues.append((int(m.group(1)), int(m.group(2)), u))
        issues.sort(reverse=True)
        if recent:
            issues = issues[:2]
        log.info(f"  {label} {y}: {len(issues)} issues")
        for iy, n, iu in issues:
            time.sleep(REQUEST_DELAY)
            try:
                ih = fetch(iu, headers=BROWSER_UA)
            except Exception as e:
                log.warning(f"  issue {iy}/{n}: {e}")
                continue
            seen = set()
            for u, txt in _links(ih, iu):
                if (len(txt) < 4 or txt in SKIP_TITLES or "网站声明" in txt or "理论资源导航" in txt
                        or "期》" in txt or not re.search(
                            r"qstheory\.cn/(?:dukan/(?:qs|hqwg)/\d{4}-\d{2}/\d{2}/c_\d+\.htm"
                            r"|\d{8}/[0-9a-f]{32}/c\.html)", u)):
                    continue
                cu = canon_qs(u)
                if cu not in seen:
                    seen.add(cu)
                    yield cu, {"issue_hint": f"{iy}/{n:02d}", "title_hint": txt}


# ── TRS section lists (学习时报网, 中国社会科学网) ─────────────────────────

# site-chrome links that every list/issue page carries (licences, contact, copyright)
FOOTER_TITLE_RE = re.compile(r"^(?:互联网新闻信息服务|网络服务出版)?许可证$|^版权声明$|^联系我们$|^关于我们$|^网站声明$|网出证|ICP备|公网安备|^\d{6,}$")

_TRS_ART = re.compile(r"/(\d{6})/t(\d{4})(\d{2})(\d{2})_\d+\.s?html$")


def parse_trs_article(html: str, url: str, cfg: dict) -> dict:
    m = re.search(cfg["title_re"], html, re.S)
    title = clean_title(m.group(1)) if m else ""
    if not title:
        t = re.search(r"(?is)<title>(.*?)</title>", html)
        if t:
            title = re.sub(r"^学习时报网_|-中国社会科学网$", "", clean_title(t.group(1)))
    u = _TRS_ART.search(url)
    d = f"{u.group(2)}-{u.group(3)}-{u.group(4)}" if u else ""
    src = re.search(cfg.get("source_re", r"$^"), html)
    au = re.search(cfg.get("author_re", r"$^"), html)
    body = flatten(slice_between(html, cfg["body_start"], cfg["body_end"]))
    return {"title": title, "date": d, "source": src.group(1).strip() if src else "",
            "author": au.group(1).strip() if au else "", "body": body}


def discover_trs(cfg: dict, max_pages: int):
    ext = cfg["list_ext"]
    host = cfg["base_url"].rstrip("/")
    seen = set()
    for sec in cfg["sections"]:
        base = f"{host}/{sec}/"
        n_pages = None
        for p in range(max_pages):
            lu = base if p == 0 else f"{base}index_{p}.{ext}"
            try:
                lh = fetch(lu, headers=BROWSER_UA)
            except Exception as e:
                log.warning(f"  list {lu}: {e}")
                break
            if n_pages is None:
                m = re.search(r"countPage\s*=\s*(\d+)", lh)
                n_pages = int(m.group(1)) if m else 1
            added = 0
            for u, txt in _links(lh, lu):
                if cfg.get("same_section") and not u.startswith(base):
                    continue
                if (u.startswith(host) and _TRS_ART.search(u) and u not in seen
                        and len(txt) >= 4 and txt not in ("[详细]", "更多")
                        and not FOOTER_TITLE_RE.search(txt)):
                    seen.add(u)
                    added += 1
                    yield u, {"section": sec, "title_hint": txt}
            time.sleep(REQUEST_DELAY)
            if p + 1 >= n_pages:
                break
        log.info(f"  section {sec}: {n_pages} list pages, total urls {len(seen)}")


# ── 光明日报 e-paper theory pages ─────────────────────────────────────────

GMW = "https://epaper.gmw.cn/gmrb/html/"
NEW_DIALECT_FROM = date(2026, 1, 1)


def gmw_index_url(d: date) -> str:
    if d >= NEW_DIALECT_FROM:
        return f"{GMW}layout/{d:%Y%m}/{d:%d}/node_01.html"
    return f"{GMW}{d:%Y-%m}/{d:%d}/nbs.D110000gmrb_01.htm"


def gmw_pages(index_html: str, d: date):
    """[(page_url, page_name)] for the day's THEORY pages."""
    out, seen = [], set()
    if d >= NEW_DIALECT_FROM:
        pat = re.compile(r'href="?(node_\d+\.html)"?[^>]*>\s*第\d+版：([^<]+)')
        base = f"{GMW}layout/{d:%Y%m}/{d:%d}/"
    else:
        pat = re.compile(r'href="?(nbs\.D110000gmrb_\d+\.htm)"?[^>]*>\s*第\d+版[：:]([^<]+)')
        base = f"{GMW}{d:%Y-%m}/{d:%d}/"
    for m in pat.finditer(index_html):
        name = m.group(2).strip()
        if m.group(1) not in seen and THEORY_PAGE_RE.search(name):
            seen.add(m.group(1))
            out.append((base + m.group(1), name))
    return out


def gmw_articles(page_html: str, page_url: str, d: date):
    if d >= NEW_DIALECT_FROM:
        pat = r'href="?((?:\.\./)+content/\d{6}/\d{2}/content_\d+\.html)'
    else:
        pat = r'href="?(nw\.D110000gmrb_\d{8}_\d+-\d+\.htm)'
    out = []
    for m in re.finditer(pat, page_html):
        u = urljoin(page_url, m.group(1))
        if u not in out:
            out.append(u)
    return out


def parse_gmw_article(html: str) -> dict:
    m = re.search(r"(?is)<h1[^>]*>(.*?)</h1>", html)
    title = clean_title(m.group(1)) if m else ""
    au = re.search(r"作者：\s*([^<]{1,60}?)\s*<", html)
    # (?<!") — the old Founder template also carries both markers inside a JS
    # string literal (content.replace("<!--enpcontent-->","")) BEFORE the body,
    # which sliced an empty body for every pre-2026 article.
    body = flatten(slice_between(html, r'(?<!")<!--enpcontent-->',
                                 (r'(?<!")<!--/enpcontent-->',)))
    return {"title": title, "author": au.group(1).strip() if au else "", "body": body}


def discover_gmw(since: date, until: date):
    d = until
    while d >= since:
        try:
            ih = fetch(gmw_index_url(d), headers=BROWSER_UA)
        except Exception as e:
            log.warning(f"  {d}: {e}")
            ih = ""
        if "该日无报纸" in ih or not ih:
            d -= timedelta(days=1)
            time.sleep(REQUEST_DELAY)
            continue
        for pu, name in gmw_pages(ih, d):
            time.sleep(REQUEST_DELAY)
            try:
                ph = fetch(pu, headers=BROWSER_UA)
            except Exception as e:
                log.warning(f"  page {pu}: {e}")
                continue
            for au in gmw_articles(ph, pu, d):
                yield au, {"date": d.isoformat(), "page": name}
        d -= timedelta(days=1)
        time.sleep(REQUEST_DELAY)


# ── 人民论坛 magazines ────────────────────────────────────────────────────

_RMLT_ART = re.compile(r"https?://(?:www\.)?rmlt\.com\.cn/(\d{4})/(\d{2})(\d{2})/\d+\.shtml$")


def parse_rmlt_article(html: str, url: str) -> dict:
    m = re.search(r'(?is)<h1 class="article-title">(.*?)</h1>', html) or \
        re.search(r"(?is)<h1[^>]*>(.*?)</h1>", html)
    title = clean_title(m.group(1)) if m else ""
    u = _RMLT_ART.search(url)
    d = f"{u.group(1)}-{u.group(2)}-{u.group(3)}" if u else ""
    au = re.search(r'class="editors">\s*([^<]{1,60}?)\s*<', html)
    src = re.search(r'class="source">\s*(?:<a[^>]*>)?\s*([^<]{2,60}?)\s*<', html)
    body = flatten(slice_between(html, r'class="article-content[ "]',
                                 (r"<!-- @end 文章内容", r'<div class="editor">')))
    return {"title": title, "date": d, "author": au.group(1).strip() if au else "",
            "source": src.group(1).strip() if src else "", "body": body}


def discover_rmlt(cfg: dict, recent: bool):
    seen = set()
    this_year = date.today().year
    for mag, label in cfg["magazines"].items():
        years = ([this_year, this_year - 1] if recent
                 else range(this_year, cfg["min_year"] - 1, -1))
        for y in years:
            yu = f"{cfg['base_url']}/magazine/{mag}/{y}/"
            try:
                yh = fetch(yu, headers=BROWSER_UA)
            except Exception as e:
                log.warning(f"  {yu}: {e}")
                continue
            issues = []
            for u, txt in _links(yh, yu):
                if re.search(rf"/magazine/{mag}/{y}/\d+/$", u) and u not in issues:
                    issues.append(u)
            # issue ids are sequential; newest first
            issues.sort(key=lambda u: int(u.rstrip("/").split("/")[-1]), reverse=True)
            if recent:
                issues = issues[:3]
            log.info(f"  {label} {y}: {len(issues)} issues")
            for iu in issues:
                time.sleep(REQUEST_DELAY)
                try:
                    ih = fetch(iu, headers=BROWSER_UA)
                except Exception as e:
                    log.warning(f"  issue {iu}: {e}")
                    continue
                for u, txt in _links(ih, iu):
                    u = u.replace("http://", "https://")
                    m = _RMLT_ART.search(u)
                    # an issue's articles are posted in its year (or January of
                    # the next); anything else is footer chrome such as the
                    # 2015 licence page
                    if (m and int(m.group(1)) in (y, y + 1) and u not in seen
                            and len(txt) >= 4 and not FOOTER_TITLE_RE.search(txt)):
                        seen.add(u)
                        yield u, {"magazine": label, "issue": iu.rstrip("/").split("/")[-1]}


# ── 爱思想 ─────────────────────────────────────────────────────────────────

_ASX_ID = re.compile(r"/data/(\d+)\.html")
_ASX_H3 = re.compile(r"(?is)<h3>(.*?)</h3>")
_ASX_TIME = re.compile(r"更新时间：\s*(\d{4}-\d{2}-\d{2})")
_ASX_AUTHOR = re.compile(r"●\s*<strong>([^<]{1,40})</strong>")
_ASX_TOPIC = re.compile(r'href="/zhuanti/\d+\.html"><u>([^<]{1,30})</u>')
# the closing origin line: 摘自/转自：《江淮论坛》2026年第3期, or a party paper's masthead
# line 《 人民日报 》（ 2026年06月18日 09 版）. Many reposts carry neither.
_ASX_ORIGIN = re.compile(r"^(?:(?:摘自|转自|原载|来源|本文原载于?)[：:]\s*(.{2,120})"
                         r"|(《\s*[^》]{2,20}?\s*》\s*[（(][^）)]{4,30}[）)]))$", re.M)
_DIV = re.compile(r"(?i)<(/?)div\b")


def div_inner(html: str, start: str) -> str:
    """Inner HTML of the first <div> whose opening tag matches `start`, cut at its
    MATCHING close by depth count. A marker after the div (本文责编) would also
    sweep in the 进入专栏 / 进入专题 block that sits between them."""
    m = re.search(start, html)
    if not m:
        return ""
    i = html.find(">", m.end()) + 1
    depth = 1
    for d in _DIV.finditer(html, i):
        depth += -1 if d.group(1) else 1
        if depth == 0:
            return html[i:d.start()]
    return html[i:]


def parse_asx_article(html: str) -> dict:
    h3 = _ASX_H3.search(html)
    if not h3:
        return {"gone": True, "title": "", "date": "", "body": "", "author": ""}
    title = clean_title(h3.group(1))
    authors = _ASX_AUTHOR.findall(html)
    # the <h3> is "作者：题目"; store the title the source venue printed
    head, sep, rest = title.partition("：")
    if sep and authors and len(head) <= 30 and all(a.strip() in head for a in authors):
        title = rest.strip()
    d = _ASX_TIME.search(html)
    body = flatten(div_inner(html, r'class="article-content"'))
    origin = [re.sub(r"\s+", "", a or b) for a, b in _ASX_ORIGIN.findall(body)]
    return {"title": title, "date": d.group(1) if d else "", "body": body,
            "author": " ".join(a.strip() for a in authors),
            "origin": origin[-1].strip() if origin else "",
            "topics": list(dict.fromkeys(_ASX_TOPIC.findall(html)))}   # printed twice


def discover_asx(cfg: dict, args):
    """Article ids newest first. --recent walks cfg['recent_ids'] below the newest
    id on the home page; --min-id / --max-id bound a backfill."""
    base = cfg["base_url"]
    hi = args.max_id
    if not hi:
        ids = [int(x) for x in _ASX_ID.findall(fetch(base + "/", headers=BROWSER_UA))]
        if not ids:
            raise RuntimeError("aisixiang: no /data/<id>.html links on the home page")
        hi = max(ids)
    lo = args.min_id if (args.min_id and not args.recent) else hi - cfg["recent_ids"]
    log.info(f"  aisixiang ids {hi} down to {lo}")
    for i in range(hi, lo - 1, -1):
        yield f"{base}/data/{i}.html", {}


# ── driver ────────────────────────────────────────────────────────────────

def parse(site_key: str, cfg: dict, url: str, html: str, hint: dict) -> dict:
    kind = cfg["kind"]
    if kind == "qs_journal":
        r = parse_qs_article(html, cfg)
        if not r["issue"]:
            r["issue"] = hint.get("issue_hint", "")
            if cfg.get("cover_date") and r["issue"]:
                y, n = r["issue"].split("/")
                r["date"] = qs_cover_date(int(y), int(n)) or r["date"]
        r["relation"] = f"issue={cfg['issue_label']}{r['issue']}"
        r["publisher"] = cfg["publisher"]
    elif kind == "trs_list":
        r = parse_trs_article(html, url, cfg)
        r["relation"] = f"section={hint.get('section', '')}"
        r["publisher"] = r.get("source") or cfg["publisher"]
    elif kind == "gmw_epaper":
        r = parse_gmw_article(html)
        r["date"] = hint["date"]
        r["relation"] = f"page={hint['page']}"
        r["publisher"] = cfg["publisher"]
    elif kind == "rmlt_mag":
        r = parse_rmlt_article(html, url)
        r["relation"] = f"magazine={hint['magazine']};issue={hint['issue']}"
        r["publisher"] = hint["magazine"] if not r.get("source") else r["source"]
    elif kind == "asx_ids":
        r = parse_asx_article(html)
        r["relation"] = f"origin={r.get('origin', '')}"
        if r.get("topics"):
            r["relation"] += ";topics=" + "/".join(r["topics"])[:80]
        r["publisher"] = cfg["publisher"]
    else:
        raise ValueError(kind)
    if not r["title"]:
        r["title"] = hint.get("title_hint", "")
    if not r["date"] and kind == "qs_journal":
        r["date"] = qs_url_date(url)
    rel = f"theory={site_key};" + r["relation"]
    if r.get("author"):
        rel += f";author={r['author'][:60]}"
    r["relation"] = rel
    return r


def discover(site_key: str, cfg: dict, args):
    kind = cfg["kind"]
    if kind == "qs_journal":
        return discover_qs(cfg, args.recent)
    if kind == "trs_list":
        return discover_trs(cfg, 2 if args.recent else args.max_pages)
    if kind == "gmw_epaper":
        until = date.fromisoformat(args.until) if args.until else date.today()
        since = (until - timedelta(days=3) if args.recent else
                 date.fromisoformat(args.since or cfg["min_date"]))
        return discover_gmw(since, until)
    if kind == "rmlt_mag":
        return discover_rmlt(cfg, args.recent)
    if kind == "asx_ids":
        return discover_asx(cfg, args)
    raise ValueError(kind)


def crawl(conn, site_key: str, args) -> int:
    cfg = SITES[site_key]
    if not args.probe:
        store_site(conn, site_key, {"name": cfg["name"], "base_url": cfg["base_url"],
                                    "admin_level": cfg["admin_level"]})
    log.info(f"[{site_key}] {cfg['name']}")
    stored = seen = thin = nodate = failed = skipped = gone = 0
    t0 = time.time()
    for url, hint in discover(site_key, cfg, args):
        if args.max_docs and stored >= args.max_docs:
            break
        if args.max_minutes and time.time() - t0 > args.max_minutes * 60:
            log.info(f"[{site_key}] --max-minutes {args.max_minutes} reached")
            break
        seen += 1
        if not args.probe and conn.execute(
                "SELECT 1 FROM documents WHERE url=? AND url != ''", (url,)).fetchone():
            skipped += 1
            continue
        try:
            html = fetch(url, headers=BROWSER_UA)
        except Exception as e:
            failed += 1
            log.warning(f"  {url}: {e}")
            continue
        r = parse(site_key, cfg, url, html, hint)
        if r.get("gone"):              # a deleted id, not a parse failure
            gone += 1
            continue
        if not r["title"]:
            failed += 1
            log.warning(f"  no title: {url}")
            continue
        if not r["date"]:
            nodate += 1
        body = r["body"]
        if cjk(body) < MIN_BODY_CJK:
            thin += 1
            body = ""
        if args.probe:
            print(json.dumps({"site": site_key, "url": url, "date": r["date"],
                              "title": r["title"][:60], "rel": r["relation"][:80],
                              "publisher": r["publisher"], "body_cjk": cjk(body),
                              "body_head": body[:80].replace("\n", " "),
                              "body_tail": body[-60:].replace("\n", " ")},
                             ensure_ascii=False))
            if seen >= args.probe_n:
                break
            time.sleep(REQUEST_DELAY)
            continue
        if store_document(conn, site_key, {
            "id": next_id(conn), "title": r["title"], "date_published": r["date"],
            "body_text_cn": body, "url": url, "publisher": r["publisher"][:100],
            "classify_genre_name": "theory", "relation": r["relation"],
        }):
            stored += 1
        # commit per row: the separate DB has one writer, and a short transaction
        # never holds the lock across a network fetch (CLAUDE.md, hold time).
        commit_with_retry(conn)
        if stored and stored % 50 == 0:
            log.info(f"  [{site_key}] stored {stored} (seen {seen}, thin {thin})")
        time.sleep(REQUEST_DELAY)
    log.info(f"[{site_key}] done: {stored} new, {skipped} held, {thin} thin-body, "
             f"{nodate} no-date, {failed} failed, {gone} gone, {seen} seen")
    return stored


def main():
    ap = argparse.ArgumentParser(description="Party-theory and academic venues crawler")
    ap.add_argument("--site", help="one site key")
    ap.add_argument("--tier", type=int, choices=(1, 2))
    ap.add_argument("--list-sites", action="store_true")
    ap.add_argument("--probe", action="store_true",
                    help="discover + parse a few articles, write NOTHING")
    ap.add_argument("--probe-n", type=int, default=3)
    ap.add_argument("--recent", action="store_true",
                    help="nightly mode: newest issues / first list pages / last 3 days")
    ap.add_argument("--max-docs", type=int, default=0)
    ap.add_argument("--max-pages", type=int, default=34,
                    help="list pages per TRS section (studytimes/cssn)")
    ap.add_argument("--max-minutes", type=float, default=0)
    ap.add_argument("--since", help="gmrb_theory: earliest day (YYYY-MM-DD)")
    ap.add_argument("--until", help="gmrb_theory: latest day (YYYY-MM-DD)")
    ap.add_argument("--min-id", type=int, default=0, help="aisixiang: lowest article id")
    ap.add_argument("--max-id", type=int, default=0,
                    help="aisixiang: highest article id (default: newest on the home page)")
    ap.add_argument("--db")
    args = ap.parse_args()

    if args.list_sites:
        for k, c in sorted(SITES.items(), key=lambda kv: (kv[1]["tier"], kv[0])):
            print(f"  tier{c['tier']}  {k:12} {c['admin_level']:8} {c['speaker']:12} {c['name']}")
        return
    keys = ([args.site] if args.site else
            [k for k, c in SITES.items() if c["tier"] == args.tier] if args.tier else
            list(SITES))
    for k in keys:
        if k not in SITES:
            ap.error(f"unknown site: {k}")
    for d in (args.since, args.until):
        if d:
            datetime.strptime(d, "%Y-%m-%d")      # refuse a typo loudly
    conn = init_db(args.db) if args.db else init_db()
    total = sum(crawl(conn, k, args) for k in keys)
    log.info(f"TOTAL: {total} new documents across {len(keys)} site(s)")
    if not args.probe:
        show_stats(conn)


if __name__ == "__main__":
    main()
