"""
Generic Chinese-gov "t-date" list crawler — multi-site.

Many central ministries publish policy documents in the standard gov CMS layout:
articles at `/SECTION/.../YYYYMM/tYYYYMMDD_ID.html`, listed on server-rendered
section pages as `<a href="…t-date…" title="…">` rows with a nearby date. This
is a DIFFERENT dialect from:
  - crawlers.gkmlpt  (Guangdong gkmlpt API)
  - crawlers.jpaas   (jpaas dataproxy columns)
  - crawlers.trs     (TRS <record> recordset columns under /col/)
Here the list is plain t-date anchors under human-readable section paths, and
deep pagination (`index_N.html`) is usually a broken 300–400 B stub — so page 0
(the recent policy window) is the reliable, high-value slice. `--deep` still
attempts `index_N` and stops the moment a page yields no new articles.

Each site config gives `sections`: either leaf list pages (t-date anchors) or a
landing page that links to sub-sections. `--discover` reports, per section root,
which sub-paths actually carry t-date lists (so configs stay light + verifiable).

Bodies vary by template, so `_extract_body` tries the common containers
(TRS_Editor / #zoom / .content / .article / #UCAP-CONTENT). The 政府信息公开
metadata table (发文字号/发布日期/发文机关) is parsed via gov._extract_metadata_table.

Usage:
    python -m crawlers.govcms --list-sites
    python -m crawlers.govcms --site mwr --discover     # map sub-sections
    python -m crawlers.govcms --site mwr                # crawl (page 0)
    python -m crawlers.govcms --site mwr --deep         # + index_N pagination
"""
import argparse
import html as H
import re
import time
from urllib.parse import urljoin

from crawlers.base import (
    REQUEST_DELAY, fetch, init_db, log, next_id, save_raw_html,
    show_stats, store_document, store_site,
)
from crawlers.gov import _extract_metadata_table

UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")}

# site_key -> config. `sections` are paths under base_url; each is either a leaf
# t-date list or a landing that links sub-sections (crawl_site follows one level).
SITES = {
    "mwr": {
        "name": "Ministry of Water Resources (水利部)",
        "base_url": "http://www.mwr.gov.cn", "admin_level": "central",
        "sections": ["/zw/zcfg/fl/", "/zw/zcfg/xzfg/", "/zw/zcfg/bmgz/",
                     "/zw/zcfg/gfxwj/", "/zw/slzx/slyw/"],
    },
    "mct": {
        "name": "Ministry of Culture & Tourism (文旅部)",
        "base_url": "http://www.mct.gov.cn", "admin_level": "central",
        "sections": ["/whzx/ggtz/"],
    },
    "nbs": {
        "name": "National Bureau of Statistics (国家统计局)",
        "base_url": "http://www.stats.gov.cn", "admin_level": "central",
        "sections": ["/xw/tjxw/tzgg/", "/sj/zxfb/"],
    },
    "mva": {
        "name": "Ministry of Veterans Affairs (退役军人事务部)",
        "base_url": "http://www.mva.gov.cn", "admin_level": "central",
        "sections": ["/gongkai/zfxxgkpt/zhengce/gfxwj/"],
    },
    "mara": {
        "name": "Ministry of Agriculture & Rural Affairs (农业农村部)",
        "base_url": "http://www.moa.gov.cn", "admin_level": "central",
        "sections": ["/gk/zcfg/"],
    },
    "mot": {
        "name": "Ministry of Transport (交通运输部)",
        "base_url": "http://www.mot.gov.cn", "admin_level": "central",
        "sections": ["/gongkai/zcjd/", "/xinwen/jiaotongyaowen/"],
    },
    "cppcc": {
        "name": "CPPCC National Committee (全国政协)",
        "base_url": "http://www.cppcc.gov.cn", "admin_level": "central",
        "sections": ["/llyj/", "/wylz/wyjy/"],
    },
    # --- provincial / municipal portals (t-date dialect) ---
    "jilin": {
        "name": "Jilin Province (吉林省)",
        "base_url": "http://www.jl.gov.cn", "admin_level": "provincial",
        "sections": ["/yaowen/", "/szyw/zwlb/"],
    },
    "fujian": {
        "name": "Fujian Province (福建省)",
        "base_url": "http://www.fujian.gov.cn", "admin_level": "provincial",
        "sections": ["/zwgk/tzgg/", "/xwdt/mszx/"],
    },
    "hunan": {
        "name": "Hunan Province (湖南省)",
        "base_url": "http://www.hunan.gov.cn", "admin_level": "provincial",
        "sections": ["/hnszf/xxgk/zfgz/", "/hnszf/xxgk/tzgg/swszf/"],
    },
    "shenyang": {
        "name": "Shenyang (沈阳市)",
        "base_url": "http://www.shenyang.gov.cn", "admin_level": "municipal",
        "sections": ["/zwgk/zwdt/szfxx/zydt/", "/zwgk/zwdt/bmdt/"],
    },
    "shandong": {
        # /art/ dialect: dataproxy.jsp returns empty; the /col/ index HTML lists
        # /art/YYYY/M/D/art_C_D.html directly. (Not jpaas — see crawlers/jpaas.py note.)
        "name": "Shandong Province (山东省)",
        "base_url": "http://www.shandong.gov.cn", "admin_level": "provincial",
        "sections": ["/col/col305145/", "/col/col305158/"],
    },
    "jinan": {
        # Hanweb CMS: news + 政策解读 columns server-render hash /art/ links; the
        # 通知公告/政府文件 columns render client-side (Hanweb datacall) — TODO those.
        "name": "Jinan (济南市)",
        "base_url": "http://www.jinan.gov.cn", "admin_level": "municipal",
        "sections": ["/col/col118736/", "/col/col121799/"],  # 政策解读 (policy)
    },
    "chinapeace": {
        # 中央政法委 — TRS content dialect: /chinapeace/c<col>/YYYY-MM/DD/content_ID.shtml.
        # Section index pages server-render ~99 links each (fully crawlable).
        "name": "Central Political & Legal Affairs Commission (中央政法委)",
        "base_url": "http://www.chinapeace.gov.cn", "admin_level": "central",
        "sections": ["/chinapeace/c100004/index.shtml", "/chinapeace/c100007/index.shtml",
                     "/chinapeace/c100008/index.shtml", "/chinapeace/c100013/index.shtml",
                     "/chinapeace/c100014/index.shtml"],
    },
    "nea": {
        # 国家能源局 — news uses /YYYYMMDD/<hex>/c.html; policy sections use the older
        # /YYYY-MM/DD/c_ID.htm. Both handled by the content/NEA dialects.
        # DEFERRED: the droplet IP serves the homepage (200) but 404s these section
        # pages — datacenter geo-fence. Configured but NOT wired into daily_sync.
        "name": "National Energy Administration (国家能源局)",
        "base_url": "http://www.nea.gov.cn", "admin_level": "central",
        "sections": ["/n/xwzx/index.htm", "/n/policy/zxwj.htm", "/n/nyflfg/index.htm",
                     "/n/politics/2015v/wj.htm", "/n/politics/2015v/zc.htm"],
    },
    "liaoning": {
        # 辽宁省 — web-idx dialect: /web/SECTION/<timestamp-id>/index.shtml. Section
        # list pages server-render the article rows; the article-id dir's leading 8
        # digits ARE the publish date (YYYYMMDD). Full provincial policy docs
        # (省政府文件: 五五 plans, policy notices), ~8k-char bodies.
        "name": "Liaoning Province (辽宁省)",
        "base_url": "https://www.ln.gov.cn", "admin_level": "provincial",
        "sections": ["/web/zwgkx/zfwj/index.shtml", "/web/zwgkx/zfwj/szfwj/index.shtml",
                     "/web/ywdt/index.shtml"],
    },
    "xizang": {
        # 西藏自治区 — plain t-date dialect (A). Section index pages server-render
        # the /YYYYMM/tYYYYMMDD_ID.html rows. High-value 政策规章 (regulations),
        # 政务要闻, 公示公告. Droplet reaches these list pages (200); a couple of
        # deeper dirs connection-reset intermittently (US->China latency, retried).
        "name": "Tibet (西藏自治区)",
        "base_url": "https://www.xizang.gov.cn", "admin_level": "provincial",
        "sections": ["/zwgk/zfxxgk/fdzdgknr/zc/gz/index.html",
                     "/xwzx_406/zwyw/index.html",
                     "/zwgk/xxfb/gsgg_428/index.html"],
    },
    "ningxia": {
        # 宁夏回族自治区 — plain t-date dialect (A). 政策 (/zwgk/zc/, incl. 规章库),
        # 政策解读 (69 rows), 通知公告. All three server-render from the droplet.
        "name": "Ningxia (宁夏回族自治区)",
        "base_url": "https://www.nx.gov.cn", "admin_level": "provincial",
        "sections": ["/zwgk/zc/", "/zwxx_11337/zcjd/", "/zwgk/tzgg/"],
    },
    # --- 西藏自治区 provincial departments (*.xizang.gov.cn) ---
    # Same t-date dialect (A) as the province; each dept's section list pages
    # server-render at <section>/index.html. Reachable from the droplet (they ride
    # the province's IP-allowlist, unlike separate city domains). Sections chosen
    # for policy value (政策法规/通知公告/公示公告 over pure news). ~28 depts expose
    # t-date on their homepage; this is the high-value policy-body batch.
    "xz_drc": {"name": "Tibet DRC (西藏发改委)", "base_url": "https://drc.xizang.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_1941/tz/index.html", "/fgdt/tz/index.html"]},
    "xz_swt": {"name": "Tibet Commerce Dept (西藏商务厅)", "base_url": "https://swt.xizang.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xwzx/swyw/index.html", "/xwzx/gsgg/index.html"]},
    "xz_zrzyt": {"name": "Tibet Natural Resources Dept (西藏自然资源厅)", "base_url": "https://zrzyt.xizang.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/gk/xxgk/zfjc/zcjd/index.html", "/gk/gsgg/index.html"]},
    "xz_jtt": {"name": "Tibet Transport Dept (西藏交通厅)", "base_url": "https://jtt.xizang.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xxgk/tzgg/index.html"]},
    "xz_sft": {"name": "Tibet Justice Dept (西藏司法厅)", "base_url": "https://sft.xizang.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xxgk/xxgkml/zcfg/index.html", "/xxgk/xxgkml/bmwj/index.html"]},
    "xz_hrss": {"name": "Tibet Human Resources & Social Security Dept (西藏人社厅)", "base_url": "https://hrss.xizang.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xwzx/tzgg/index.html", "/zcfg/shbz/index.html"]},
    "xz_wjw": {"name": "Tibet Health Commission (西藏卫健委)", "base_url": "https://wjw.xizang.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xwzx/wsjkdt/index.html"]},
    "xz_sjt": {"name": "Tibet Water Resources Dept (西藏水利厅)", "base_url": "https://sjt.xizang.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xwzx/gsgg/index.html", "/xwzx/bmkx/index.html"]},
    "xz_nynct": {"name": "Tibet Agriculture & Rural Affairs Dept (西藏农业农村厅)", "base_url": "https://nynct.xizang.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xwzx/gsgg/index.html", "/xwzx/xzsn/index.html"]},
    "xz_tjj": {"name": "Tibet Statistics Bureau (西藏统计局)", "base_url": "https://tjj.xizang.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xxgk/tjxx/tjsj/index.html", "/xwzx/gsgg/index.html"]},
    "xz_mzt": {"name": "Tibet Civil Affairs Dept (西藏民政厅)", "base_url": "https://mzt.xizang.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zxzx/dsdt/index.html"]},
    # 西藏 departments round 2 (autoconfig-generated, curated: dropped 4 驻外办事处
    # liaison offices + slt dup-水利厅 + unreachable wsb + empty-name gdj).
    "xz_gat": {"name": "Tibet Public Security Dept (西藏公安厅)", "base_url": "https://gat.xizang.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_3249/zcjd_220/index.html", "/zwgk_3249/zcfg_219/index.html", "/xwzx_3233/gsgg_205/index.html"]},
    "xz_sti": {"name": "Tibet Science & Technology Dept (西藏科技厅)", "base_url": "https://sti.xizang.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xxgk/fdzdgk/zcjd/index.html", "/xxgk/fdzdgk/tzgg/index.html", "/xxgk/zc/Laws/index.html"]},
    "xz_wlt": {"name": "Tibet Culture & Tourism Dept (西藏文旅厅)", "base_url": "https://wlt.xizang.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_69/zcfg/bmgz/index.html", "/xwzx_69/tzgg/index.html"]},
    "xz_ylbzj": {"name": "Tibet Healthcare Security Bureau (西藏医保局)", "base_url": "https://ylbzj.xizang.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/zcjd/index.html", "/zwgk/flfg/index.html", "/zwgk/zcwj/index.html"]},
    "xz_mw": {"name": "Tibet Ethnic Affairs Commission (西藏民委)", "base_url": "https://mw.xizang.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xxgk/gsgg/index.html", "/xxgk/zcjd/index.html", "/xxgk/zcfg/index.html"]},
    "xz_tzcjj": {"name": "Tibet Investment Promotion Bureau (西藏投资促进局)", "base_url": "https://tzcjj.xizang.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/tzgg/index.html", "/zwgk/zcjd/index.html"]},
    "xz_ee": {"name": "Tibet Ecology & Environment Dept (西藏生态环境厅)", "base_url": "https://ee.xizang.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xwzx/gsgg/index.html"]},
    "xz_sport": {"name": "Tibet Sports Bureau (西藏体育局)", "base_url": "https://sport.xizang.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/tzgz/index.html", "/zwgk/zwxx/index.html"]},
    "xz_tyjr": {"name": "Tibet Veterans Affairs Dept (西藏退役军人事务厅)", "base_url": "https://tyjr.xizang.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xwzx/gsgg/index.html"]},
    "qingdao": {
        # 青岛市 (副省级市, Shandong) — plain t-date dialect (A). High-value section
        # is 市政府规范性文件 (/zwgk/zdgk/fgwj/zcwj/szfgw/, ~177 rows, 100% body) plus
        # 政务要闻/公告公示 news. NOTE: the old 政策解读 index (/zwgk/xxgk/bgt/gkml/
        # zcjd/) is an ARCHIVED dead list — its article links 302→404, so it's
        # deliberately excluded (would add ~40 bodyless rows).
        "name": "Qingdao (青岛市)",
        "base_url": "https://www.qingdao.gov.cn", "admin_level": "municipal",
        "sections": ["/zwgk/zdgk/fgwj/zcwj/szfgw/", "/ywdt/zwyw/", "/ywdt/gggs/"],
    },
    # TODO: yunnan (云南) — /zwgk/* policy subtree is 403-fenced to the droplet's
    # datacenter IP; only /ywdt/ news reachable. Needs a residential IP or browser.
    # TODO: tianjin (天津) — t-date on the homepage but section list pages are
    # JS-built (Hanweb datacall, like jinan) — need browser network inspection.
    # TODO: jinan 通知公告/政府文件 columns use Hanweb client-side datacall — need
    # browser network inspection to find the list endpoint.
}

# article link dialects:
#  (A) t-date:  …/tYYYYMMDD_ID.html  (most central ministries)
#  (B) /art/:   …/art/YYYY/M/D/art_COL_ID.html  (Shandong & many /col/ provinces)
_ART_RE = re.compile(r'<a\s+[^>]*href="([^"]*?t(\d{8})_\d+\.s?html?)"[^>]*>(.*?)</a>', re.S)
# /art/ comes in two shapes: /art/YYYY/M/D/art_NUM_NUM.html (Shandong) and
# /art/YYYY/art_<hex>.html (Jinan/Hanweb). M/D are optional; art_ id is digits+_
# or a hex hash.
_ART_ART_RE = re.compile(
    r'<a\s+[^>]*href="([^"]*?/art/(\d{4})(?:/(\d{1,2})/(\d{1,2}))?/art_[0-9a-f_]+\.s?html?)"[^>]*>(.*?)</a>', re.S)
#  (C) TRS content: …/YYYY-MM/DD/content_ID.shtml OR …/c_ID.htm (中央政法委, NEA policy…)
_ART_CONTENT_RE = re.compile(
    r'<a\s+[^>]*href="([^"]*?/(\d{4})-(\d{1,2})/(\d{1,2})/(?:content|c)_\d+\.s?html?)"[^>]*>(.*?)</a>', re.S)
#  (D) NEA new: …/YYYYMMDD/<hex>/c.html  (国家能源局)
_ART_NEA_RE = re.compile(
    r'<a\s+[^>]*href="([^"]*?/(\d{4})(\d{2})(\d{2})/[0-9a-f]{8,}/c\.s?html?)"[^>]*>(.*?)</a>', re.S)
#  (E) web-idx: …/web/SECTION/<timestamp-id>/index.shtml  (辽宁省). The id dir is a
#      ≥12-digit timestamp whose leading 8 digits are the pub date (YYYYMMDD).
_ART_WEB_RE = re.compile(
    r'<a\s+[^>]*href="([^"]*?/web/[^"]*?/(\d{8})\d{4,}/index\.s?html?)"[^>]*>(.*?)</a>', re.S)
_ART_TITLE_ATTR = re.compile(r'title="([^"]+)"')
_DATE_NEAR = re.compile(r'(\d{4}-\d{2}-\d{2})')
_SUBDIR_RE = re.compile(r'href="([^"]*?/[a-z0-9]+/)"')
# Known tight content containers, tried first (fast path for common templates).
_BODY_CONTAINERS = [
    r'id="UCAP-CONTENT"',
    r'class="[^"]*trs_editor_view',          # TRS UEditor (mva etc.)
    r'class="[^"]*TRS_UEDITOR',
    r'class="[^"]*TRS_Editor',
    r'id="zoom"', r'id="Zoom"',
    r'class="[^"]*\bview\b[^"]*TRS',
    r'class="[^"]*xxgk[-_]?content',
    r'class="[^"]*article[-_]?(?:con|content|text)',
    r'class="[^"]*content[-_]?(?:box|main|body|text)',
]
_FOOT_CUT = re.compile(r'(相关(?:附件|链接|文件|报道)|扫一扫|打印本页|class="[^"]*(?:foot|share|xglj|fujian|print))')


def _clean(t: str) -> str:
    t = re.sub(r"<[^>]+>", "", t)
    t = H.unescape(t)
    return re.sub(r"\s+", " ", t).strip()


def _region_text(region: str) -> str:
    region = _FOOT_CUT.split(region, 1)[0]
    region = re.sub(r"<br\s*/?>", "\n", region)
    region = re.sub(r"</p>", "\n", region)
    text = H.unescape(re.sub(r"<[^>]+>", "", region))
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()


def _extract_body(html: str) -> str:
    """Extract article body. Try known containers first; else fall back to the
    INNERMOST <div> carrying the most <p>-text (deepest wins on nested ties, so
    we skip wrapper divs that also contain the sidebar/nav)."""
    for pat in _BODY_CONTAINERS:
        m = re.search(pat, html)
        if m:
            t = _region_text(html[m.start():m.start() + 120_000])
            if len(t) > 80:
                return t
    # fallback: score every div by the <p>-text immediately inside it
    cands = []
    for m in re.finditer(r"<div\b[^>]*>", html):
        region = html[m.end():m.end() + 80_000]
        ptext = sum(len(re.sub(r"<[^>]+>", "", x))
                    for x in re.findall(r"<p[^>]*>(.*?)</p>", region, re.S))
        if ptext > 200:
            cands.append((ptext, m.end(), region))
    if cands:
        top = max(c[0] for c in cands)
        # among near-top scorers, the innermost (largest start offset) is the
        # actual content div, not an enclosing wrapper.
        _, _, region = max((c for c in cands if c[0] >= top * 0.9), key=lambda c: c[1])
        return _region_text(region)
    return ""


def _list_articles(page_html: str, page_url: str) -> list:
    """Extract [{url,title,date}] from a section list page. Handles both article
    URL dialects (t-date and /art/); date comes from the row if present, else the
    URL itself (tYYYYMMDD or /art/YYYY/M/D/)."""
    matches = []
    for m in _ART_RE.finditer(page_html):
        ymd = m.group(2)
        matches.append((m, m.group(1), m.group(3), f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}"))
    for m in _ART_ART_RE.finditer(page_html):
        y, mo, d = m.group(2), m.group(3), m.group(4)
        url_date = f"{y}-{int(mo):02d}-{int(d):02d}" if mo and d else f"{y}-01-01"
        matches.append((m, m.group(1), m.group(5), url_date))
    for m in _ART_CONTENT_RE.finditer(page_html):
        y, mo, d = m.group(2), m.group(3), m.group(4)
        matches.append((m, m.group(1), m.group(5), f"{y}-{int(mo):02d}-{int(d):02d}"))
    for m in _ART_NEA_RE.finditer(page_html):
        y, mo, d = m.group(2), m.group(3), m.group(4)
        matches.append((m, m.group(1), m.group(5), f"{y}-{mo}-{d}"))
    for m in _ART_WEB_RE.finditer(page_html):
        ymd = m.group(2)
        matches.append((m, m.group(1), m.group(3), f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}"))
    out, seen = [], set()
    for m, href, inner, url_date in matches:
        url = urljoin(page_url, H.unescape(href))
        if url in seen:
            continue
        seen.add(url)
        ta = _ART_TITLE_ATTR.search(m.group(0))
        title = _clean(ta.group(1) if ta else inner)
        if not title:
            continue
        row = page_html[max(0, m.start() - 240):m.end() + 60]
        dm = _DATE_NEAR.search(row)
        out.append({"url": url, "title": title, "date": dm.group(1) if dm else url_date})
    return out


def _discover_sections(base: str, root: str, max_sub: int = 15) -> list:
    """Return sub-paths carrying t-date lists. A leaf (root itself lists articles)
    returns immediately; a landing expands into its OWN children only (not nav)."""
    root_abs = urljoin(base, root)
    try:
        h = fetch(root_abs, headers=UA)
    except Exception as e:
        log.warning(f"  discover {root}: {e}")
        return []
    if _list_articles(h, root_abs):        # leaf: done, don't fan out into nav
        return [root]
    hits = []                              # landing: probe its child sections only
    children = sorted({urljoin(root_abs, s) for s in _SUBDIR_RE.findall(h)})
    for u in children:
        if not u.startswith(root_abs) or u.rstrip("/") == root_abs.rstrip("/"):
            continue
        try:
            if _list_articles(fetch(u, headers=UA), u):
                hits.append(u[len(base):])
        except Exception:
            pass
        if len(hits) >= max_sub:
            break
        time.sleep(0.2)
    return hits


def _pages(base: str, section: str, deep: bool, max_pages: int):
    """Yield (url, html) for a section: page 0, then index_N if --deep."""
    first = urljoin(base, section)
    try:
        yield first, fetch(first, headers=UA)
    except Exception as e:
        log.warning(f"  {section}: {e}")
        return
    if not deep:
        return
    for n in range(1, max_pages + 1):
        u = urljoin(first, f"index_{n}.html")
        try:
            html = fetch(u, headers=UA)
        except Exception:
            return
        if len(html) < 600 or not _list_articles(html, u):  # broken stub → stop
            return
        yield u, html
        time.sleep(REQUEST_DELAY)


def crawl_site(conn, site_key, cfg, fetch_bodies=True, deep=False, max_pages=30):
    base = cfg["base_url"].rstrip("/")
    store_site(conn, site_key, cfg)
    # expand landing sections into leaf list pages
    sections = []
    for root in cfg["sections"]:
        leaves = _discover_sections(base, root)
        sections.extend(leaves or [root])
    sections = list(dict.fromkeys(sections))
    log.info(f"[{site_key}] {len(sections)} leaf sections")
    stored = 0
    for section in sections:
        for page_url, html in _pages(base, section, deep, max_pages):
            arts = _list_articles(html, page_url)
            new = 0
            for it in arts:
                if conn.execute("SELECT 1 FROM documents WHERE url=? AND url != ''",
                                (it["url"],)).fetchone():
                    continue
                new += 1
                doc_id = next_id(conn)
                body, raw, meta = "", "", {}
                if fetch_bodies:
                    try:
                        dh = fetch(it["url"], headers=UA)
                        body = _extract_body(dh)
                        meta = _extract_metadata_table(dh)
                        raw = save_raw_html(site_key, doc_id, dh)
                    except Exception as e:
                        log.warning(f"    body {it['url']}: {e}")
                    time.sleep(REQUEST_DELAY)
                store_document(conn, site_key, {
                    "id": doc_id, "title": meta.get("title") or it["title"],
                    "document_number": meta.get("document_number", ""),
                    "publisher": meta.get("publisher", ""),
                    "date_published": it["date"],
                    "identifier": meta.get("identifier", ""),
                    "classify_theme_name": meta.get("classify_theme_name", ""),
                    "body_text_cn": body, "url": it["url"],
                    "classify_main_name": section, "raw_html_path": raw,
                    "admin_level": cfg["admin_level"],
                })
                stored += 1
                if stored % 20 == 0:      # commit periodically so a long section
                    conn.commit()         # (e.g. MOT's ~477) is resumable, not lost
            conn.commit()
            log.info(f"  {section} [{page_url.split('/')[-1]}]: +{new}")
            if not deep:
                break
    log.info(f"[{site_key}] done: {stored} new docs")
    return stored


def main():
    ap = argparse.ArgumentParser(description="Generic gov t-date list crawler")
    ap.add_argument("--site")
    ap.add_argument("--group", help="crawl every site tagged with this group (e.g. 'dept')")
    ap.add_argument("--list-sites", action="store_true")
    ap.add_argument("--discover", action="store_true", help="map sub-sections, don't crawl")
    ap.add_argument("--list-only", action="store_true", help="metadata only, skip bodies")
    ap.add_argument("--deep", action="store_true", help="attempt index_N pagination")
    ap.add_argument("--db")
    args = ap.parse_args()

    if args.list_sites:
        for k, c in SITES.items():
            grp = f" [{c['group']}]" if c.get("group") else ""
            print(f"  {k:12} {c['name']}  {c['base_url']}{grp}")
        return
    if args.group:
        # crawl all sites tagged with this group, sequentially, into one DB.
        keys = [k for k, c in SITES.items() if c.get("group") == args.group]
        if not keys:
            print(f"No sites tagged group={args.group!r}")
            return
        conn = init_db(args.db) if args.db else init_db()
        for k in keys:
            print(f"\n=== [{args.group}] {k}: {SITES[k]['name']} ===")
            try:
                crawl_site(conn, k, SITES[k], fetch_bodies=not args.list_only, deep=args.deep)
            except Exception as e:  # one dept failing must not abort the group
                print(f"  {k}: FAILED {type(e).__name__}: {e}")
        show_stats(conn)
        return
    if not args.site or args.site not in SITES:
        print("Specify --site KEY (see --list-sites)")
        return
    cfg = SITES[args.site]
    base = cfg["base_url"].rstrip("/")
    if args.discover:
        for root in cfg["sections"]:
            print(f"{root} ->", _discover_sections(base, root))
        return
    conn = init_db(args.db) if args.db else init_db()
    crawl_site(conn, args.site, cfg, fetch_bodies=not args.list_only, deep=args.deep)
    show_stats(conn)


if __name__ == "__main__":
    main()
