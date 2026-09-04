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
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import nullcontext
from urllib.parse import urljoin, urlparse

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
        # Province portal. tzgg/mszx = 通知公告 + 民生资讯 (recent window). Added
        # 2026-08: /zwgk/flfg/{dfxfg,szfgz} = 地方性法规 (local statutes) + 省政府规章
        # (provincial gov rules) — primary provincial law the portal otherwise didn't
        # expose (we held 0). These are single-page t-date lists (~16-50 items each;
        # index_N.htm is a ~2KB stub, so --deep no-ops — page 0 is the whole set).
        # NOTE: the province's 闽政/闽政办 省政府文件 and dept 规范性文件 (职称/招聘/闽科规…)
        # live in the JS/search-gated 政策文件库 (/zck/, WAS5 search), NOT a t-date
        # section, so they are NOT reachable by this dialect (see Fujian backfill probe).
        "name": "Fujian Province (福建省)",
        "base_url": "http://www.fujian.gov.cn", "admin_level": "provincial",
        "sections": ["/zwgk/tzgg/", "/xwdt/mszx/",
                     "/zwgk/flfg/dfxfg/", "/zwgk/flfg/szfgz/"],
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
    "cnipa": {
        # 国家知识产权局 — /art/ dialect (/col/ index pages, art_COL_ID links inside a
        # <recordset> CDATA block). Needs base.fetch() gzip handling (CNIPA force-gzips).
        "name": "National IP Administration (国家知识产权局)",
        "base_url": "https://www.cnipa.gov.cn", "admin_level": "central",
        "sections": ["/col/col74/", "/col/col75/", "/col/col66/"],
    },
    "dangyuan": {
        # 共产党员网 (中组部) — ARTI dialect: /YYYY/MM/DD/ARTI<id>.shtml. Party policy
        # docs, laws, intra-Party regulations (党内法规). 政策文件 alone ~604 links.
        "name": "CPC Members Network (共产党员网)",
        "base_url": "https://www.12371.cn", "admin_level": "central",
        "sections": ["/special/zcwj/", "/special/falv/", "/special/dnfg/"],
    },
    "sasac": {
        # 国资委 — old CMS: article at /nNNNN/.../c<id>/content.html under n-section
        # dirs; section index pages server-render title-attributed content.html links
        # (ccontent dialect K). Central SOE regulator (chip/telecom/AI/energy giants).
        "name": "State-owned Assets Supervision & Admin Commission (国资委)",
        "base_url": "http://www.sasac.gov.cn", "admin_level": "central",
        "sections": ["/n2588035/n2588320/n2588335/index.html"],
    },
    "tc260": {
        # 全国网络安全标准化技术委员会 (网安标委) — portal CMS: /portal/article/<cat>/<id>
        # (portal dialect L). Homepage + category list pages server-render dated
        # article rows. Issues the operative AI-security/ethics national standards
        # (生成式AI安全基本要求 etc.) — the technical backbone of China AI governance.
        "name": "National Cybersecurity Standardization TC (网安标委 TC260)",
        "base_url": "https://www.tc260.org.cn", "admin_level": "central",
        # List pages carry per-row dates (homepage doesn't) → list first so the dated
        # version of each article wins the URL de-dupe; homepage last as a backstop.
        "sections": ["/portal/list/index/id/1.html", "/portal/list/index/id/2.html",
                     "/portal/list/index/id/3.html", "/"],
    },
    "cas": {
        # 中国科学院 — HQ notices/policy. Standard t-date dialect (A) with .shtml
        # (/<sec>/YYYYMM/tYYYYMMDD_ID.shtml). Scoped to www.cas.cn HQ (institute
        # subdomains excluded). Apex national research system (AI/chip/quantum).
        "name": "Chinese Academy of Sciences (中国科学院)",
        "base_url": "https://www.cas.cn", "admin_level": "central",
        "sections": ["/tz/", "/zcjd/"],
    },
    "cnao": {
        # 审计署 — same ccontent dialect (K) as SASAC: /nN/nN/.../c<id>/content.html.
        # Section index pages server-render the content.html links (dates on the
        # article page → _PUB_DATE fallback). 法律法规 + 公告 + 通知 + 审计要闻.
        "name": "National Audit Office (审计署)",
        "base_url": "https://www.audit.gov.cn", "admin_level": "central",
        "sections": ["/n6/n36/index.html", "/n5/n25/index.html",
                     "/n8/n28/index.html", "/n4/n19/index.html"],
    },
    "nsfc": {
        # 国家自然科学基金委 — nsfc dialect (M): /p1/<col>/…/<numeric-id>.html. The bare
        # column dir 403s, but each column has a SLUG-named server-rendered list page
        # (dates adjacent). Basic-research funder steering AI/chip/quantum money.
        "name": "National Natural Science Foundation (国家自然科学基金委)",
        "base_url": "https://www.nsfc.gov.cn", "admin_level": "central",
        "sections": ["/p1/3381/2824/zntg.html", "/p1/3381/2822/tzsm1.html",
                     "/p1/3381/2821/jjyw11.html", "/p1/3381/2825/zzcg11.html"],
    },
    "mem": {
        # 应急管理部 — t-date dialect A (.shtml): /<sub>/YYYYMM/tYYYYMMDD_ID.shtml.
        # 法律法规标准 sections server-render dated rows (fg/ mixes in external NPC/gov.cn
        # law links — the crawler keeps only native mem.gov.cn t-date docs).
        "name": "Ministry of Emergency Management (应急管理部)",
        "base_url": "https://www.mem.gov.cn", "admin_level": "central",
        "sections": ["/fw/flfgbz/fg/", "/fw/flfgbz/"],
    },
    "moj": {
        # 司法部 — t-date dialect A. Reachable ONLY with cookie replay of the openresty
        # CT6T/CT6TS WAF (302→self that sets a cookie) — enabled by the cookie jar added
        # to base.fetch(). Drafts data/tech administrative regs. Use news + 法律法规规章
        # (the 政务公开 notice landing is JS-rendered).
        "name": "Ministry of Justice (司法部)",
        "base_url": "http://www.moj.gov.cn", "admin_level": "central",
        "sections": ["/pub/sfbgw/flfggz/flfggzxzfg/", "/pub/sfbgw/gwxw/xwyw/index.html",
                     "/pub/sfbgw/lfyjzj/lflfyjzj/"],
    },
    # ── Round-2 central bureaus (2026-08-11) ─────────────────────────────────
    "spc": {
        # 最高人民法院 — spc dialect (N): list /fabu/gengduo/<sec-id>.html → articles
        # /fabu/xiangqing/<numid>.html (numeric section ids from the 发布 hub, not slugs).
        # Full court: 司法解释/公告/司法文件 (we previously held only the IP tribunal).
        "name": "Supreme People's Court (最高人民法院)",
        "base_url": "https://www.court.gov.cn", "admin_level": "central",
        "sections": ["/fabu/gengduo/14.html", "/fabu/gengduo/15.html", "/fabu/gengduo/16.html",
                     "/fabu/gengduo/17.html", "/fabu/gengduo/21.html", "/fabu/gengduo/108.html"],
    },
    "qstheory": {
        # 求是网 — CCP flagship theory journal. Dialect D (hex/c.html):
        # /YYYYMMDD/<hex32>/c.html. Authoritative party-line policy signal.
        "name": "Qiushi (求是网)",
        "base_url": "http://www.qstheory.cn", "admin_level": "media",
        "sections": ["/qsyw/index.htm", "/qsgdzx/index.htm", "/dt/index.htm"],
    },
    "cma": {
        # 中国气象局 — t-date dialect A. 规范性文件 + 通知公告.
        "name": "China Meteorological Administration (中国气象局)",
        "base_url": "http://www.cma.gov.cn", "admin_level": "central",
        "sections": ["/zfxxgk/gknr/wjgk/gfxwj/", "/2011zwxx/2011ztzgg/"],
    },
    "ncha": {
        # 国家文物局 — TRS-WCM /art/ dialect B (same family as cnipa). Use real section
        # col pages (col1053 is a redirect shell — avoid).
        "name": "National Cultural Heritage Administration (国家文物局)",
        "base_url": "http://www.ncha.gov.cn", "admin_level": "central",
        "sections": ["/col/col2664/index.html", "/col/col2666/index.html",
                     "/col/col2318/index.html", "/col/col2096/index.html"],
    },
    "natcm": {
        # 国家中医药管理局 — datepath dialect O: /<cat>/YYYY-MM-DD/<numid>.html. The /a/<cat>/
        # aggregator pages link to articles under per-department paths. Rich bodies.
        "name": "National Administration of TCM (国家中医药管理局)",
        "base_url": "http://www.natcm.gov.cn", "admin_level": "central",
        "sections": ["/a/zcwj/", "/a/tzgg/", "/a/zcjd/"],
    },
    "safe": {
        # 国家外汇管理局 — safe dialect P: /safe/YYYY/MMDD/<numid>.html. 政策法规 (zcfg).
        # Capital-flow / fintech policy.
        "name": "State Administration of Foreign Exchange (国家外汇管理局)",
        "base_url": "https://www.safe.gov.cn", "admin_level": "central",
        "sections": ["/safe/zcfg/index.html"],
    },
    "nfsra": {
        # 国家粮食和物资储备局 — content dialect C, but the server-rendered lists are the
        # per-year archive pages /html/<col>YYYYyear/list_zh.shtml (the column first.shtml
        # pages AJAX-load = SPA). Year archives need periodic bump.
        "name": "National Food & Strategic Reserves Admin (国家粮食和物资储备局)",
        "base_url": "http://www.lswz.gov.cn", "admin_level": "central",
        "sections": ["/html/gzdt2026year/list_zh.shtml", "/html/gzdt2025year/list_zh.shtml"],
    },
    "nia": {
        # 国家移民管理局 — ccontent dialect K: /nNNN/nNNN/c<id>/content.html. Native content
        # under the n741440/* tree (homepage links out to gov.cn).
        "name": "National Immigration Administration (国家移民管理局)",
        "base_url": "https://www.nia.gov.cn", "admin_level": "central",
        "sections": ["/n741440/n741567/index.html"],
    },
    "sfa": {
        # 国家林业和草原局 — ymd8 dialect Q: /lyj/1/<sec>/YYYYMMDD/<numid>.html. 林草政策 +
        # 政策公告 + 国务院文件. Server-rendered dated lists.
        "name": "National Forestry & Grassland Administration (国家林业和草原局)",
        "base_url": "https://www.forestry.gov.cn", "admin_level": "central",
        "sections": ["/lyj/1/lczc.html", "/lyj/1/zcgg.html", "/lyj/1/gwywj.html"],
    },
    "spb": {
        # 国家邮政局 — hexmon dialect I: /gjyzj/cNNN/cNNN/YYYYMM/<32-hex>.shtml. The list
        # page is common_list.shtml (bare column dir 404s). Under MOT.
        "name": "State Post Bureau (国家邮政局)",
        "base_url": "http://www.spb.gov.cn", "admin_level": "central",
        "sections": ["/gjyzj/c100009/c100010/common_list.shtml",
                     "/gjyzj/c100001/c100007/common_list.shtml"],
    },
    "caac": {
        # 中国民用航空局 — t-date dialect A. The homepage server-renders many t-date links
        # (section hubs are JS iframes → index_N.html lists; JGGLL=362 confirmed). Point
        # at the homepage + known index_N pages.
        "name": "Civil Aviation Administration (中国民用航空局)",
        "base_url": "http://www.caac.gov.cn", "admin_level": "central",
        "sections": ["/index.html", "/XXGK/XXGK/JGGLL/index_362.html"],
    },
    # ── Round-3 central bodies (2026-08-11) ─────────────────────────────────
    "sastind": {
        # 国防科工局 — ccontent dialect K (/nNNN/nNNN/c<id>/content.html). Defense-industry
        # + space policy. Server-rendered n-section indexes.
        "name": "State Admin for Sci-Tech & Industry for Nat'l Defense (国防科工局)",
        "base_url": "https://www.sastind.gov.cn", "admin_level": "central",
        "sections": ["/n10086200/n10086319/index.html"],
    },
    "cnsa": {
        # 国家航天局 — ccontent dialect K. Space policy (skews news; pick sections carefully).
        "name": "China National Space Administration (国家航天局)",
        "base_url": "https://www.cnsa.gov.cn", "admin_level": "central",
        "sections": ["/n6758823/n6758838/index.html"],
    },
    "saac": {
        # 国家档案局 — hexmon dialect I: /daj/<sec>/YYYYMM/<32-hex>.shtml. list.shtml/
        # <sec>.shtml section pages server-render dated rows. 行政法规库/法规标准库/信息公开.
        "name": "National Archives Administration (国家档案局)",
        "base_url": "https://www.saac.gov.cn", "admin_level": "central",
        "sections": ["/daj/xxgk/list.shtml", "/daj/tzgg/list.shtml",
                     "/daj/xzfgk/xzfgk.shtml", "/daj/fgbzk/fgbzk.shtml"],
    },
    # ── RESIDENTIAL tier (2026-08-11): datacenter-IP-blocked from the droplet but
    # reachable from a residential IP. group="residential" → EXCLUDED from the droplet
    # nightly (which can't reach them); crawled via scripts/local_crawl_merge.sh from a
    # residential machine → merged up. NOT added to daily_sync.sh's govcms loop.
    "sichuan": {  # 四川省 — schex dialect R (/cols/YYYY/M/D/<32hex>.shtml). Chengdu AI/chip hub.
        "name": "Sichuan Province (四川省)", "base_url": "https://www.sc.gov.cn",
        "admin_level": "provincial", "group": "residential",
        "sections": ["/10462/13241/list.shtml", "/10462/10464/13298/zcjd.shtml",
                     "/10462/c102914/gfxwj.shtml"],
    },
    "tianjin": {  # 天津市 — t-date dialect A. Direct-controlled municipality.
        "name": "Tianjin (天津市)", "base_url": "https://www.tj.gov.cn",
        "admin_level": "provincial", "group": "residential",
        "sections": ["/sy/tzgg/", "/zwgk/zcjd/", "/sy/jrgz/"],
    },
    "guizhou": {  # 贵州省 — t-date dialect A. Big-data hub. (szfwj/ is a redirect stub → szfl/)
        "name": "Guizhou Province (贵州省)", "base_url": "https://www.guizhou.gov.cn",
        "admin_level": "provincial", "group": "residential",
        "sections": ["/home/tzgg/", "/zwgk/zcfg/szfwj/szfl/", "/zwgk/rsxx/rsrm/"],
    },
    "hainan": {  # 海南省 — hexmon dialect I (/SECTION/YYYYMM/<32hex>.shtml). Free-trade port.
        "name": "Hainan Province (海南省)", "base_url": "https://www.hainan.gov.cn",
        "admin_level": "provincial", "group": "residential",
        "sections": ["/hainan/zfwj/szfzcwj.shtml", "/hainan/fdzdgknr/newxxgk_list.shtml"],
    },
    "xinjiang": {  # 新疆 — hexmon dialect I. Un-tagged from 'residential' 2026-09-04:
        # now droplet-reachable (200/108KB), so it joins the nightly govcms loop.
        "name": "Xinjiang (新疆维吾尔自治区)", "base_url": "https://www.xinjiang.gov.cn",
        "admin_level": "provincial",
        "sections": ["/xinjiang/zfl/zfxxgk_zhengce_list.shtml", "/xinjiang/zwgk/zw.shtml"],
    },
    # ═══ ReConnect Tier-B reachable-new sources (added 2026-09-04). Provincial/central
    #     join the nightly govcms site loop; cities carry group="city" (`--group city`).
    #     See docs/working/source-access-map.md + newcrawl-configs-*.md.
    "qinghai": {  # 青海省 — NEW dialect (U) qhsys /zwgk/system/YYYY/MM/DD/<num>.shtml.
        # HTTP ONLY (https blackholed from the droplet); /xxgk/ policy tree is 412-fenced,
        # so the reachable listings are the /zwgk/xwdt/ sections.
        "name": "Qinghai (青海省)",
        "base_url": "http://www.qinghai.gov.cn", "admin_level": "provincial",
        "sections": ["/zwgk/xwdt/tzgg/", "/zwgk/xwdt/qhyw/"],
    },
    "neac": {  # 国家民委 — NEW dialect (V) cmon /seac/c<col>/<YYYYMM>/<num>.shtml (TRS-WCM).
        "name": "State Ethnic Affairs Commission (国家民委)",
        "base_url": "https://www.neac.gov.cn", "admin_level": "central",
        "sections": ["/seac/xxgk/zcfb/index.shtml", "/seac/xxgk/zcjd/index.shtml",
                     "/seac/xxgk/tzgg/index.shtml"],
    },
    # -- City tier (existing dialects A/B/I/Q/S; group="city") --
    "baoji": {"name": "Baoji (宝鸡市)", "base_url": "https://www.baoji.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/col46/col47/", "/col46/col52/"]},
    "shannan": {"name": "Shannan (山南市)", "base_url": "https://www.shannan.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/zwgk/", "/jytadf/"]},
    "wuzhong": {"name": "Wuzhong (吴忠市)", "base_url": "https://www.wuzhong.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/sy/zcjd/"]},
    "zhangye": {"name": "Zhangye (张掖市)", "base_url": "https://www.zhangye.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/dzdt/tzgg/", "/zyszfxxgk/zfwj_5652/zcjd_8944/sjzcjd_8947/"]},
    "zhoukou": {"name": "Zhoukou (周口市)", "base_url": "https://www.zhoukou.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/sitesources/zksrmzf/page_pc/xwzx/tzgg/"]},
    "dingxi": {"name": "Dingxi (定西市)", "base_url": "https://www.dingxi.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/col/col15863/", "/col/col15887/"]},
    "weihai": {"name": "Weihai (威海市)", "base_url": "https://www.weihai.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/col/col102604/"]},
    "linxia": {"name": "Linxia Hui Prefecture (临夏回族自治州)", "base_url": "https://www.linxia.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/lxz/zwgk/fdzdgknr/lzyj/gfxwj/", "/lxz/ywdt/tzgg/"]},
    "pingliang": {"name": "Pingliang (平凉市)", "base_url": "https://www.pingliang.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/zfxxgk/fdzdgknr/lzyj/zcwj/", "/xwzx/tzgg/"]},
    "suzhou_ah": {"name": "Suzhou, Anhui (宿州市)", "base_url": "https://www.suzhou.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/col/col168035/"]},
    "yushu": {"name": "Yushu (玉树藏族自治州)", "base_url": "http://www.yushu.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/xxgk/qwfb/gsgg/"]},
    "shuozhou": {"name": "Shuozhou (朔州市)", "base_url": "http://szxxgk.shuozhou.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/szfxxgk/fdzdgknr/gzwj/gfxwj/", "/szfxxgk/fdzdgknr/gzwj/zfwj/", "/szfxxgk/fdzdgknr/zcjd/"]},
    "quanzhou": {"name": "Quanzhou (泉州市)", "base_url": "http://www.quanzhou.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/zfb/xxgk/zfxxgkzl/qzdt/qzyw/"]},
    "yuxi": {"name": "Yuxi (玉溪市)", "base_url": "http://www.yuxi.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/yxs/tzgg/", "/yxs/tzggsy/"]},
    "suihua": {"name": "Suihua (绥化市)", "base_url": "http://www.suihua.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/sh/gfxwj/zfxxgk.shtml", "/sh/zfxxgkzd/zfxxgk.shtml"]},
    "huaihua": {"name": "Huaihua (怀化市)", "base_url": "http://www.huaihua.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/huaihua/c100231/zfxxgkMultiList.shtml", "/huaihua/c100238/zfxxgkMultiList.shtml"]},
    "laiwu": {"name": "Laiwu (莱芜)", "base_url": "http://www.laiwu.gov.cn", "admin_level": "district", "group": "city", "sections": ["/col116924/index.html"]},
    "liuzhou": {"name": "Liuzhou (柳州市)", "base_url": "http://www.liuzhou.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/"]},
    "fuzhou_fj": {"name": "Fuzhou (福州市)", "base_url": "http://www.fuzhou.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/"]},
    "hanzhong": {"name": "Hanzhong (汉中市)", "base_url": "http://www.hanzhong.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/"]},
    "taizhou_js": {"name": "Taizhou (泰州市)", "base_url": "http://www.taizhou.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/"]},
    "yantai": {"name": "Yantai (烟台市)", "base_url": "http://www.yantai.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/"]},
    "shijiazhuang": {"name": "Shijiazhuang (石家庄市)", "base_url": "http://www.sjz.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/zfxxgk/columns/0f9f6cdc-69ca-4a72-bd39-66b553cc0674/index.html", "/zfxxgk/columns/6ac6458a-126e-47ce-a1eb-12930061231e/index.html", "/"]},
    "changzhi": {"name": "Changzhi (长治市)", "base_url": "https://www.changzhi.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/xxgkml/czsrmzf/zfwj_3465/", "/xxgkml/czsrmzf/zbwj_3466/", "/xxgkml/czsrmzf/zcjd/", "/xwzx/tzgg/"]},
    "huangshi": {"name": "Huangshi (黄石市)", "base_url": "https://www.huangshi.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/xxxgk/2020_zc/", "/xwdt/2020_gggs/"]},
    "liaoyuan": {"name": "Liaoyuan (辽源市)", "base_url": "https://www.liaoyuan.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/xxgk/zwxxgkfl/zfwj/", "/xxgk/"]},
    "longyan": {"name": "Longyan (龙岩市)", "base_url": "https://www.longyan.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/gk/flgk/gg/", "/gk/flgk/jd/"]},
    "ordos": {"name": "Ordos (鄂尔多斯市)", "base_url": "https://www.ordos.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/xw_127672/gsgg/", "/gk_128120/zfxxgkzl/zdgksxmlqd/"]},
    "tongliao": {"name": "Tongliao (通辽市)", "base_url": "https://www.tongliao.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/zwgk/", "/xwzx/"]},
    "yinchuan": {"name": "Yinchuan (银川市)", "base_url": "https://www.yinchuan.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/xxgk/zcwj/zcjd/ycszc/", "/xwzx/gsgg/", "/xxgk/zcwj/qtzfwj/wjlist.html"]},
    "tianmen": {"name": "Tianmen (天门市)", "base_url": "https://www.tianmen.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/zwgk/zc/tzgg/", "/zwgk/zc/zcjd/"]},
    "qianjiang": {"name": "Qianjiang (潜江市)", "base_url": "https://www.qianjiang.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/zwgk_210/zfxxgkml/zcwj_qzf/qzfgfxwj/", "/zwgk_210/zfxxgkml/zcwj_qzf/qtwj/", "/zwxx_210/gsgg/"]},
    "jiyuan": {"name": "Jiyuan (济源市)", "base_url": "https://www.jiyuan.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/zwgk/zcwjk/", "/zwgk/"]},
    "ganzhou": {"name": "Ganzhou (赣州市)", "base_url": "https://www.ganzhou.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/gzszf/c100051/2021_zwgk.shtml", "/gzszf/c100023/list.shtml", "/zwgk/zcwj/", "/zwgk/tzgg/"]},
    "hegang": {"name": "Hegang (鹤岗市)", "base_url": "https://www.hegang.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/hegang/szfgfxwj/zwgk_zc.shtml", "/hegang/tzgg/list.shtml", "/hegang/zcjd/zcjd_sec.shtml"]},
    "hebei": {  # 河北省 — hbuuid dialect S (/columns/<UUID>/YYYYMM/DD/<UUID>.html).
        "name": "Hebei Province (河北省)", "base_url": "https://www.hebei.gov.cn",
        "admin_level": "provincial", "group": "residential",
        "sections": ["/columns/49f13cc2-db03-4d0c-b4fe-2f3f659d3b6e/index.html",
                     "/columns/b4515201-74c2-4866-ba74-70199fee1a67/index.html",
                     "/columns/e4a82431-5daf-4e1f-b7ff-80a68ad951b2/index.html",
                     "/columns/259e0b1d-e98f-4d3c-bd10-b7ef867295be/index.html"],
    },
    # ── Provincial DEPARTMENT tier, round 2 (2026-08-12): Hunan/Liaoning/Shandong/Jilin.
    # All droplet-reachable (share the province IP-allowlist), existing dialects. group=dept.
    # 湖南 (dialect A t-date, HTTP only — https TLS-fails from droplet):
    "hn_fgw": {"name": "Hunan DRC (湖南发改委)", "base_url": "http://fgw.hunan.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/fgw/szfglb22/fzgglist.html", "/fgw/tayabl22/fzgglist.html", "/fgw/cztdsq/fzgglist.html"]},
    "hn_gxt": {"name": "Hunan Industry & IT Dept (湖南工信厅)", "base_url": "http://gxt.hunan.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/gxt/xxgk_71033/zcfg/gfxwj/index.html", "/gxt/xxgk_71033/zcfg/zcjd/index.html", "/gxt/xxgk_71033/gsgg01/index.html"]},
    "hn_kjt": {"name": "Hunan S&T Dept (湖南科技厅)", "base_url": "http://kjt.hunan.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/kjt/xxgk/zcfg/index.html", "/kjt/xxgk/zcfg/zcjd/index.html"]},
    "hn_czt": {"name": "Hunan Finance Dept (湖南财政厅)", "base_url": "http://czt.hunan.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/czt/xxgk/zcfg/gfxwj/index.html", "/czt/xxgk/zcfg/zcwj/index.html"]},
    "hn_swt": {"name": "Hunan Commerce Dept (湖南商务厅)", "base_url": "http://swt.hunan.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/swt/hnswt/85753/fdzdgknr/lzyj/gfxwj/xxgklbs.html", "/swt/hnswt/85753/fdzdgknr/lzyj/zcjd/xxgklbs.html"]},
    "hn_jyt": {"name": "Hunan Education Dept (湖南教育厅)", "base_url": "http://jyt.hunan.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/jyt/sjyt/xxgk/zcfg/gfxwj/index.html", "/jyt/sjyt/xxgk/zcfg/zcjd/index.html"]},
    "hn_rst": {"name": "Hunan HR & Social Security Dept (湖南人社厅)", "base_url": "http://rst.hunan.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/rst/xxgk/zcfg/index.html"]},
    "hn_zrzyt": {"name": "Hunan Natural Resources Dept (湖南自然资源厅)", "base_url": "http://zrzyt.hunan.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/zrzyt/falvfagui/list_zcdh_zcfg_st.html", "/zrzyt/zhengcejd/list_zcdh_zcfg_st.html"]},
    "hn_sthjt": {"name": "Hunan Ecology & Environment Dept (湖南生态环境厅)", "base_url": "http://sthjt.hunan.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/sthjt/xxgk/zcfg/gfxwj/list_sy3.html", "/sthjt/xxgk/tzgg/gg/index.html"]},
    # 辽宁 (dialect H tsid):
    "ln_fgw": {"name": "Liaoning DRC (辽宁发改委)", "base_url": "https://fgw.ln.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/fgw/index/tzgg/index.shtml"]},
    "ln_gxt": {"name": "Liaoning Industry & IT Dept (辽宁工信厅)", "base_url": "https://gxt.ln.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/gxt/yfxz/fgfgg/index.shtml", "/gxt/zwgk/zcjjd/index.shtml"]},
    "ln_kjt": {"name": "Liaoning S&T Dept (辽宁科技厅)", "base_url": "https://kjt.ln.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/kjt/kjgz/tzgg/index.shtml"]},
    "ln_czt": {"name": "Liaoning Finance Dept (辽宁财政厅)", "base_url": "https://czt.ln.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/czt/zwgkzdgz/czgg/gsgg/index.shtml", "/czt/zfxxgk/zc/xzgfxwj/index.shtml"]},
    "ln_swt": {"name": "Liaoning Commerce Dept (辽宁商务厅)", "base_url": "https://swt.ln.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/swt/tzgg/index.shtml"]},
    "ln_jyt": {"name": "Liaoning Education Dept (辽宁教育厅)", "base_url": "https://jyt.ln.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/jyt/gk/gsgg/index.shtml"]},
    "ln_rst": {"name": "Liaoning HR & Social Security Dept (辽宁人社厅)", "base_url": "https://rst.ln.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/rst/rdzcybw/index.shtml"]},
    "ln_sthj": {"name": "Liaoning Ecology & Environment Dept (辽宁生态环境厅)", "base_url": "https://sthj.ln.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/sthj/index/tzgg/index.shtml"]},
    # 山东 (dialect B /art/, HTTP only):
    "sd_gxt": {"name": "Shandong Industry & IT Dept (山东工信厅)", "base_url": "http://gxt.shandong.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/col/col103865/index.html", "/col/col15188/index.html"]},
    "sd_kjt": {"name": "Shandong S&T Dept (山东科技厅)", "base_url": "http://kjt.shandong.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/col/col103586/index.html"]},
    "sd_czt": {"name": "Shandong Finance Dept (山东财政厅)", "base_url": "http://czt.shandong.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/col/col10559/index.html"]},
    "sd_commerce": {"name": "Shandong Commerce Dept (山东商务厅)", "base_url": "http://commerce.shandong.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/col/col106480/index.html"]},
    "sd_edu": {"name": "Shandong Education Dept (山东教育厅)", "base_url": "http://edu.shandong.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/col/col11984/index.html"]},
    # 吉林 (dialect A t-date):
    "jl_jldrc": {"name": "Jilin DRC (吉林发改委)", "base_url": "https://jldrc.jl.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/zcfg/jlzc/", "/zcfg/jlzcjd/", "/xxgk/zcfb/"]},
    "jl_gxt": {"name": "Jilin Industry & IT Dept (吉林工信厅)", "base_url": "https://gxt.jl.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/xxgk/zcwj_200601/", "/xxgk/tzgg/", "/xxgk/zcjd/"]},
    "jl_kjt": {"name": "Jilin S&T Dept (吉林科技厅)", "base_url": "https://kjt.jl.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/xxgk/fgwj/", "/xwzx/tztg/", "/xxgk/zcjd/"]},
    "jl_czt": {"name": "Jilin Finance Dept (吉林财政厅)", "base_url": "https://czt.jl.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/xwfb/tzgg/", "/zwgk/czsj/"]},
    "jl_swt": {"name": "Jilin Commerce Dept (吉林商务厅)", "base_url": "https://swt.jl.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/zcfg/", "/tzgg/", "/zcjd/"]},
    "jl_jyt": {"name": "Jilin Education Dept (吉林教育厅)", "base_url": "https://jyt.jl.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/ggl/", "/zwgk/rsrm/"]},
    "jl_hrss": {"name": "Jilin HR & Social Security Dept (吉林人社厅)", "base_url": "https://hrss.jl.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/flfg/dfxfggz2017/", "/fwzc/bszn/"]},
    "jl_zrzy": {"name": "Jilin Natural Resources Dept (吉林自然资源厅)", "base_url": "https://zrzy.jl.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/fgwj/gfxwj/", "/zwgk/fgwj/zcjd/"]},
    "jl_sthjt": {"name": "Jilin Ecology & Environment Dept (吉林生态环境厅)", "base_url": "https://sthjt.jl.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/ywdt/tzgg/", "/zcjd/"]},
    # ── Provincial DEPARTMENT tier, round 3 (2026-08-12): Jiangsu (B), Beijing (A/numid),
    # Shanghai (T shhex). All droplet-reachable. group=dept → auto in nightly.
    # 江苏 depts (dialect B /art/):
    "js_fzggw": {"name": "Jiangsu DRC (江苏发改委)", "base_url": "https://fzggw.jiangsu.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/col/col284/index.html", "/col/col314/index.html"]},
    "js_gxt": {"name": "Jiangsu Industry & IT Dept (江苏工信厅)", "base_url": "https://gxt.jiangsu.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/col/col80179/index.html", "/col/col6278/index.html", "/col/col6281/index.html"]},
    "js_kxjst": {"name": "Jiangsu S&T Dept (江苏科技厅)", "base_url": "https://kxjst.jiangsu.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/col/col82540/index.html", "/col/col82572/index.html", "/col/col82570/index.html"]},
    "js_czt": {"name": "Jiangsu Finance Dept (江苏财政厅)", "base_url": "https://czt.jiangsu.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/col/col8511/index.html"]},
    "js_sthjt": {"name": "Jiangsu Ecology & Environment Dept (江苏生态环境厅)", "base_url": "https://sthjt.jiangsu.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/col/col83843/index.html", "/col/col83844/index.html", "/col/col83845/index.html"]},
    # 北京市 bureaus (dialect A t-date; sthjj = numid /9-digit/index.html):
    "bjb_fgw": {"name": "Beijing DRC (北京市发改委)", "base_url": "https://fgw.beijing.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/fgwzwgk/2024zcwj/", "/fgwzwgk/2024zcjd/"]},
    "bjb_jxj": {"name": "Beijing Economy & IT Bureau (北京市经信局)", "base_url": "https://jxj.beijing.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/zwgk/2024zcwj/", "/jxdt/tzgg/"]},
    "bjb_kw": {"name": "Beijing S&T Commission (北京市科委)", "base_url": "https://kw.beijing.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/zwgk/zcwj/", "/zwgk/zcjd/", "/zwgk/tzgg/"]},
    "bjb_czj": {"name": "Beijing Finance Bureau (北京市财政局)", "base_url": "https://czj.beijing.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/zwxx/2024zcwj/"]},
    "bjb_swj": {"name": "Beijing Commerce Bureau (北京市商务局)", "base_url": "https://swj.beijing.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/zwgk/2024zcwj/", "/zwgk/2024zcjd/", "/swdt/tzgg/"]},
    "bjb_rsj": {"name": "Beijing HR & Social Security Bureau (北京市人社局)", "base_url": "https://rsj.beijing.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/xxgk/2024zcwj/", "/xxgk/2024zcjd/"]},
    "bjb_ghzrzyw": {"name": "Beijing Planning & Natural Resources Commission (北京市规划自然资源委)", "base_url": "https://ghzrzyw.beijing.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/zhengwuxinxi/zcwj/qtwj/", "/zhengwuxinxi/zcfg/fl/", "/zhengwuxinxi/tzgg/"]},
    "bjb_sthjj": {"name": "Beijing Ecology & Environment Bureau (北京市生态环境局)", "base_url": "https://sthjj.beijing.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/bjhrb/index/xxgk69/zfxxgk43/fdzdgknr2/zcfb/szfgfxwj/index.html", "/bjhrb/index/xxgk69/zfxxgk43/fdzdgknr2/ywdt28/xwfb/index.html"]},
    # 上海市 bureaus (dialect T shhex /YYYYMMDD/<32hex>.html):
    "shb_fgw": {"name": "Shanghai DRC (上海市发改委)", "base_url": "https://fgw.sh.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/fgw_zcwjfl/index.html", "/fgw_gfxwj/index.html"]},
    "shb_sheitc": {"name": "Shanghai Economy & Informatization Commission (上海市经信委)", "base_url": "https://www.sheitc.sh.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/zfxxgkml/"]},
    "shb_stcsm": {"name": "Shanghai S&T Commission (上海市科委)", "base_url": "https://stcsm.sh.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/zwgk/kjzc/zcwj/kwzcxwj/", "/zwgk/kjzc/zcjd/"]},
    "shb_sww": {"name": "Shanghai Commerce Commission (上海市商务委)", "base_url": "https://sww.sh.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/zwgkgfqtzcwj/index.html"]},
    "shb_rsj": {"name": "Shanghai HR & Social Security Bureau (上海市人社局)", "base_url": "https://rsj.sh.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/tgsgg_17341/index.html", "/tmsztc_17502/index.html", "/tbmts_17501/index.html"]},
    "shb_ghzyj": {"name": "Shanghai Planning & Natural Resources Bureau (上海市规划资源局)", "base_url": "https://ghzyj.sh.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/zcwj/", "/gzdt/"]},
    # ── Dept tier round 4 (2026-08-12): additional bureaus of Jiangsu/Beijing/Shanghai.
    # 江苏 (dialect B):
    "js_nynct": {"name": "Jiangsu Agriculture & Rural Affairs Dept (江苏农业农村厅)", "base_url": "https://nynct.jiangsu.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/col/col11977/index.html", "/col/col51447/index.html"]},
    "js_jtyst": {"name": "Jiangsu Transport Dept (江苏交通运输厅)", "base_url": "https://jtyst.jiangsu.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/col/col77151/index.html", "/col/col41780/index.html", "/col/col77126/index.html"]},
    "js_wjw": {"name": "Jiangsu Health Commission (江苏卫健委)", "base_url": "https://wjw.jiangsu.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/col/col49491/index.html", "/col/col49511/index.html"]},
    "js_mzt": {"name": "Jiangsu Civil Affairs Dept (江苏民政厅)", "base_url": "https://mzt.jiangsu.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/col/col55087/index.html", "/col/col78574/index.html"]},
    "js_sft": {"name": "Jiangsu Justice Dept (江苏司法厅)", "base_url": "https://sft.jiangsu.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/col/col48525/index.html"]},
    "js_scjgj": {"name": "Jiangsu Market Regulation Bureau (江苏市场监管局)", "base_url": "https://scjgj.jiangsu.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/col/col78964/index.html", "/col/col78963/index.html"]},
    "js_ybj": {"name": "Jiangsu Healthcare Security Bureau (江苏医保局)", "base_url": "https://ybj.jiangsu.gov.cn", "admin_level": "provincial", "group": "dept", "sections": ["/col/col73935/index.html"]},
    # 北京市 (dialect A t-date; nyncj/sfj/yjj = numid 9-digit):
    "bjb_nyncj": {"name": "Beijing Agriculture & Rural Affairs Bureau (北京市农业农村局)", "base_url": "https://nyncj.beijing.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/nyj/zwgk/zcgk/zcwj3149/", "/nyj/zwgk/tzgg/"]},
    "bjb_jtw": {"name": "Beijing Transport Commission (北京市交通委)", "base_url": "https://jtw.beijing.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/xxgk/tzgg/", "/xxgk/dtxx/"]},
    "bjb_wjw": {"name": "Beijing Health Commission (北京市卫健委)", "base_url": "https://wjw.beijing.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/zwgk_20040/zcwj2024/zcwjss/", "/zwgk_20040/zcwj2022/flfg/", "/zwgk_20040/tzgg/"]},
    "bjb_sfj": {"name": "Beijing Justice Bureau (北京市司法局)", "base_url": "https://sfj.beijing.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/sfj/zwgk/2024zcwj/", "/sfj/zwgk/2024zcjd/"]},
    "bjb_whlyj": {"name": "Beijing Culture & Tourism Bureau (北京市文旅局)", "base_url": "https://whlyj.beijing.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/zwgk/2024zcwj/", "/zwgk/2024zcjd/"]},
    "bjb_scjgj": {"name": "Beijing Market Regulation Bureau (北京市市场监管局)", "base_url": "https://scjgj.beijing.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/zwxx/2024zcwj/", "/zwxx/2024zcjd/"]},
    "bjb_ybj": {"name": "Beijing Medical Insurance Bureau (北京市医保局)", "base_url": "https://ybj.beijing.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/tzgg2022/", "/swdt/2020_gzdt/"]},
    "bjb_yjj": {"name": "Beijing Emergency Management Bureau (北京市应急管理局)", "base_url": "https://yjj.beijing.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/yjj/zwgk20/zcwj91/", "/yjj/zwgk20/zcjd8/"]},
    "bjb_tjj": {"name": "Beijing Statistics Bureau (北京市统计局)", "base_url": "https://tjj.beijing.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/zwgkai/2024zcwj/", "/zwgkai/2024zcjd/"]},
    "bjb_jw": {"name": "Beijing Education Commission (北京市教委)", "base_url": "https://jw.beijing.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/xxgk/2024zcwj/", "/xxgk/2024zcjd/", "/tzgg/"]},
    "bjb_sw": {"name": "Beijing Water Authority (北京市水务局)", "base_url": "https://sw.beijing.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/zwxx/2024zcwj/", "/zwxx/2024zcjd/", "/tzgg/"]},
    # 上海市 (dialect T shhex):
    "shb_nyncw": {"name": "Shanghai Agriculture & Rural Commission (上海市农业农村委)", "base_url": "https://nyncw.sh.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/gsgg/index.html"]},
    "shb_jtw": {"name": "Shanghai Transportation Commission (上海市交通委)", "base_url": "https://jtw.sh.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/zxzfxx/index.html"]},
    "shb_swj": {"name": "Shanghai Water Authority (上海市水务局)", "base_url": "https://swj.sh.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/swj-ghjhwj/index.html", "/swj-gzdt/index.html"]},
    "shb_mzj": {"name": "Shanghai Civil Affairs Bureau (上海市民政局)", "base_url": "https://mzj.sh.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/jicxx/index.html"]},
    "shb_sfj": {"name": "Shanghai Justice Bureau (上海市司法局)", "base_url": "https://sfj.sh.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/2020zwdt_tzgg/index.html"]},
    "shb_whlyj": {"name": "Shanghai Culture & Tourism Bureau (上海市文旅局)", "base_url": "https://whlyj.sh.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/wlyw/index.html", "/cysc/index.html"]},
    "shb_scjgj": {"name": "Shanghai Market Supervision Administration (上海市市场监管局)", "base_url": "https://scjgj.sh.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/056/index.html"]},
    "shb_ybj": {"name": "Shanghai Medical Insurance Bureau (上海市医保局)", "base_url": "https://ybj.sh.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/gfxwj/index.html", "/qtwj/index.html", "/zcjd/index.html"]},
    "shb_yjj": {"name": "Shanghai Emergency Management Bureau (上海市应急管理局)", "base_url": "https://yjj.sh.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/zjyw/index.html", "/sjdt/index.html"]},
    "shb_tjj": {"name": "Shanghai Statistics Bureau (上海市统计局)", "base_url": "https://tjj.sh.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/xxgk_gw/index.html", "/gfxwj/index.html"]},
    "shb_edu": {"name": "Shanghai Education Commission (上海市教委)", "base_url": "https://edu.sh.gov.cn", "admin_level": "municipal", "group": "dept", "sections": ["/xwzx_gnxw/index.html", "/xwzx_bsxw/index.html"]},
    "nea": {
        # 国家能源局 — news uses /YYYYMMDD/<hex>/c.html; policy sections use the older
        # /YYYY-MM/DD/c_ID.htm. Both handled by the content/NEA dialects.
        # DEFERRED — PROXY-GATED (re-verified 2026-08-26): the droplet IP serves the
        # homepage (200) but 404s ALL these section pages — datacenter geo-fence. A
        # 2026-08 run confirmed 0 docs. NOT a quick win despite homepage-200: the
        # homepage/individual-article 200s are a FALSE POSITIVE; the listing pages
        # (which the crawler needs to discover articles) are geo-fenced. Do NOT wire
        # into daily_sync — it belongs in the residential-proxy bucket with NHC/MNR/etc.
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
    # --- 宁夏回族自治区 provincial departments (*.nx.gov.cn) ---
    # Same t-date dialect; sections via dept_autoconfig.py (policy-ranked, index.html
    # confirmed). gat/scjg/gzw hit transient fetch errors during autoconfig — retry
    # later. nx_sjt is 审计厅 (Audit), not a dup of 西藏 xz_sjt 水利厅.
    "nx_fzggw": {"name": "Ningxia DRC (宁夏发改委)", "base_url": "https://fzggw.nx.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zcgh/zcjd/index.html", "/zcgh/fgwwj/index.html", "/zcgh/gfxwj1/index.html"]},
    "nx_czt": {"name": "Ningxia Finance Dept (宁夏财政厅)", "base_url": "https://czt.nx.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/zfxxgkml/gfxwj/index.html", "/zwgk/zfxxgkml/zcjd/index.html", "/xwzx/tzgg/index.html"]},
    "nx_kjt": {"name": "Ningxia Science & Technology Dept (宁夏科技厅)", "base_url": "https://kjt.nx.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zcfg/gfxwj/index.html", "/zwgk/fdgk/czyjs/index.html"]},
    "nx_gxt": {"name": "Ningxia Industry & IT Dept (宁夏工信厅)", "base_url": "https://gxt.nx.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/fdzdgknr/zcfg/zcjd/index.html", "/zwgk/fdzdgknr/zcfg/flfg/index.html", "/zwgk/fdzdgknr/zcfg/gxtwj/index.html"]},
    "nx_jyt": {"name": "Ningxia Education Dept (宁夏教育厅)", "base_url": "https://jyt.nx.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/zcwj/zcjd/index.html", "/xwdt/tzgg/index.html", "/zwgk/zfxxgkml/czzj/jxgl/index.html"]},
    "nx_mca": {"name": "Ningxia Civil Affairs Dept (宁夏民政厅)", "base_url": "https://mca.nx.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/zcfg/zcwj/index.html", "/xwzx/tzgg/index.html", "/zwgk/nr/ylfw/gzxx/index.html"]},
    "nx_sft": {"name": "Ningxia Justice Dept (宁夏司法厅)", "base_url": "https://sft.nx.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xxgk/wjzx/zcwj/index.html", "/xxgk/wjzx/zcjd/index.html", "/xxgk/wjzx/sftwj/index.html"]},
    "nx_hrss": {"name": "Ningxia Human Resources & Social Security Dept (宁夏人社厅)", "base_url": "https://hrss.nx.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xxgk/zcj/zcfg/cyjy/index.html", "/xxgk/zcj/zcjd/wzjd_new/index.html", "/xxgk/zcj/flfg/index.html"]},
    "nx_zrzyt": {"name": "Ningxia Natural Resources Dept (宁夏自然资源厅)", "base_url": "https://zrzyt.nx.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/gk/fdzdgknr/tzgg/index.html", "/gk/fdzdgknr/kczygl/index.html", "/xwdt/gzdt/index.html"]},
    "nx_sthjt": {"name": "Ningxia Ecology & Environment Dept (宁夏生态环境厅)", "base_url": "https://sthjt.nx.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/zcjd/index.html", "/xwzx/gsgg/index.html", "/zfxxgk/fdzdgknr/lzyj/gfxwj/index.html"]},
    "nx_jst": {"name": "Ningxia Housing & Construction Dept (宁夏住建厅)", "base_url": "https://jst.nx.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/zcwjk/gfxwj/index.html", "/zwgk/zcwjk/flfg/index.html", "/zwfw/gsgg/index.html"]},
    "nx_jtt": {"name": "Ningxia Transport Dept (宁夏交通厅)", "base_url": "https://jtt.nx.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xwzx/tzgg/index.html", "/xwzx/jtyw/index.html", "/xwzx/zwdt/index.html"]},
    "nx_sjt": {"name": "Ningxia Audit Dept (宁夏审计厅)", "base_url": "https://sjt.nx.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/xxgkjbml/gongzuogonggao/index.html", "/sjzc/sjly/index.html"]},
    "nx_nynct": {"name": "Ningxia Agriculture & Rural Affairs Dept (宁夏农业农村厅)", "base_url": "https://nynct.nx.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/zfxxgkml/gsgg/index.html", "/zwgk/zfxxgkml/nmttz/index.html", "/xwzx/zwdt/index.html"]},
    "nx_dofcom": {"name": "Ningxia Commerce Dept (宁夏商务厅)", "base_url": "https://dofcom.nx.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_274/fdzdgknr/hygk/index.html", "/zwgk_274/fdzdgknr/rsgk/index.html", "/zwgk_274/fdzdgknr/cwgk/index.html"]},
    "nx_whhlyt": {"name": "Ningxia Culture & Tourism Dept (宁夏文旅厅)", "base_url": "https://whhlyt.nx.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/zc/zcjd/index.html", "/zwgk/zc/zxgfxwj/index.html", "/zwgk/fdzdgknr/tzgg/index.html"]},
    "nx_wsjkw": {"name": "Ningxia Health Commission (宁夏卫健委)", "base_url": "https://wsjkw.nx.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zfxxgk_279/zcfg/index.html", "/xwzx_279/gzdt_46361/index.html"]},
    "nx_ylbz": {"name": "Ningxia Healthcare Security Bureau (宁夏医保局)", "base_url": "https://ylbz.nx.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zfxxgk/fdzdgknr/tzgg/index.html", "/zfxxgk/fdzdgknr/zcfg/index.html", "/zfxxgk/fdzdgknr/zcjd/index.html"]},
    "nx_nxyjglt": {"name": "Ningxia Emergency Management Dept (宁夏应急管理厅)", "base_url": "https://nxyjglt.nx.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xxgk/fdzdgknr/flfg/index.html", "/xxgk/fdzdgknr/gfxwj/index.html", "/xxgk/fdzdgknr/zcjd/index.html"]},
    # --- 福建省 + 重庆市 provincial/municipal departments (dept_fast_config, WAF-throttled capture) ---
    "fj_mzt": {"name": "福建省民政厅", "base_url": "https://mzt.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/gk/tzgg/", "/gk/zcjd/ylfwzcjd/", "/gk/zcjd/mzzcwjjd/"]},
    "fj_mzzjt": {"name": "福建省民族与宗教事务厅", "base_url": "https://mzzjt.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xxgk/zcfg/flfg/", "/xxgk/tzgg/", "/xxgk/zcjd/bmzcwjjd/"]},
    "fj_nynct": {"name": "福建省农业农村厅", "base_url": "https://nynct.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xxgk/zcfg/flfg/", "/xxgk/tzgg/", "/xxgk/qzqd/"]},
    "fj_qb": {"name": "福建侨网", "base_url": "https://qb.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xxgk/qwdt/sjdt/", "/xxgk/qwdt/jcdt/", "/jrfj/"]},
    "fj_rst": {"name": "福建省人力资源和社会保障厅", "base_url": "https://rst.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zcjd/zcjd/bmzcwjjd/", "/zw/gsgg/", "/zw/ldjy/"]},
    "fj_scjgj": {"name": "福建省市场监督管理局(知识产权局)", "base_url": "https://scjgj.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zfxxgkzl/xxgkml/zcfg/gfxwj/", "/zw/tzgg/", "/zw/zcfg/flfggz/"]},
    "fj_sft": {"name": "福建省司法厅", "base_url": "https://sft.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/zcjd/zcjd/", "/zwgk/gggs/", "/zwgk/szyw/"]},
    "fj_sjt": {"name": "福建省审计厅", "base_url": "https://sjt.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/gsgg/tzgg/", "/zwgk/zcjd/", "/zwgk/gsgg/sjjggg/"]},
    "fj_slt": {"name": "福建省水利厅", "base_url": "https://slt.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xxgk/zcjd/zcjd/bmzcjd/", "/xxgk/zcjd/zcjd/qtzcjd/", "/xxgk/zcjd/hygq/"]},
    "fj_sthjt": {"name": "福建省生态环境厅", "base_url": "https://sthjt.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/gsgg/", "/zwgk/flfg/", "/zwgk/sthjyw/stdt/"]},
    "fj_swt": {"name": "福建省商务厅", "base_url": "https://swt.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xxgk/flfg/nmlt/", "/xxgk/tzgg/", "/xxgk/flfg/qtx/"]},
    "fj_tjj": {"name": "福建省统计局", "base_url": "https://tjj.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xxgk/fgwj/tjzfyj/gfxwj/", "/xxgk/zcjd/", "/xxgk/ztgg/"]},
    "fj_tyj": {"name": "福建省体育局", "base_url": "https://tyj.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/gsgg/", "/zwgk/zcfg/pfyd/", "/zwgk/zcjd/bmzcwjjd/"]},
    "fj_tyjrswt": {"name": "福建省退役军人事务厅", "base_url": "https://tyjrswt.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/tzgg/", "/zwgk/zcfg/", "/jdhy/zcjd/wzj/"]},
    "fj_wb": {"name": "福建省人民政府外事办公室网站", "base_url": "https://wb.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/gsgg/tgl/", "/zwgk/gzdt/zwyw/", "/zwgk/rsxx/zkzp/"]},
    "fj_wjw": {"name": "福建省卫生健康委员会", "base_url": "https://wjw.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xxgk/gsgg/tzgg/", "/xxgk/gsgg/sgs/sgsxzxk/", "/xxgk/fgwj/flfg/"]},
    "fj_wlt": {"name": "福建省文化和旅游厅", "base_url": "https://wlt.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/zcfg/gfxwj/", "/zwgk/tzgg/gztz/", "/zwgk/tzgg/gggs/"]},
    "fj_xfj": {"name": "福建省信访局", "base_url": "https://xfj.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/zcfg/", "/zwgk/tzgg/", "/zwgk/zcwj/gjxfjwj/"]},
    "fj_xxzx": {"name": "福建省经济信息中心", "base_url": "https://xxzx.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xxgk/tzgg/", "/xxgk/zxdt/", "/xxgk/szyw/"]},
    "fj_ybj": {"name": "福建省医疗保障局", "base_url": "https://ybj.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/zcjd/bmzcwjjd/", "/zwgk/zcfg/", "/zwgk/gsgg/"]},
    "fj_yjt": {"name": "福建省应急管理厅", "base_url": "https://yjt.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/tzgg/yjglt_gb/", "/zwgk/zcfg/flfggz/", "/zwgk/zcfg/zcwj_gb/"]},
    "fj_zjt": {"name": "福建省住房和城乡建设厅", "base_url": "https://zjt.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xxgk/tzgg/", "/xxgk/gzdt/bmdt/", "/xxgk/zfxxgkzl/xxgkml/dfxfgzfgzhgfxwj/qt_3796/"]},
    "fj_zrzyt": {"name": "福建省自然资源厅", "base_url": "https://zrzyt.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/zcfg/flfg/", "/zwgk/gsgg/", "/zwgk/zcfg/szfwj/"]},
    "fj_bb": {"name": "中共福建省委机构编制委员会办公室", "base_url": "https://bb.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/tzgg/", "/ggqy/", "/jgbzgl/"]},
    "fj_czt": {"name": "福建省财政厅", "base_url": "https://czt.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/tzgg/", "/zwgk/zfxxgk/fdzdgknr/gfxwj/jjqy/", "/zwgk/czxw/"]},
    "fj_fgw": {"name": "福建省发展和改革委员会", "base_url": "https://fgw.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/gsgg/", "/zwgk/xwdt/bwdt/", "/zwgk/xwdt/sxdt/"]},
    "fj_gat": {"name": "福建公安公众服务网", "base_url": "https://gat.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/zcjd/", "/zwgk/jggk/jgcs/", "/zwgk/rsxx/"]},
    "fj_gdb": {"name": "福建省国防动员办公室", "base_url": "https://gdb.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xxgk/rfgzdt/", "/xxgk/tzgs/", "/xxgk/xzxk/"]},
    "fj_gdj": {"name": "福建省广播电视局", "base_url": "https://gdj.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/gkai/tzgg/", "/gkai/zcjd/qtzcwjjd/", "/xw/sjgz/"]},
    "fj_gxt": {"name": "福建省工业和信息化厅", "base_url": "https://gxt.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/gsgg/", "/zwgk/zfxxgk/fdzdgknr/gfxwj/", "/zwgk/czzj/xmaphzjxd/"]},
    "fj_gzw": {"name": "福建省人民政府国有资产监督管理委员会", "base_url": "https://gzw.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/gzdt/gzjg/zcfg/", "/zwgk/gzdt/szyw/", "/zwgk/gzdt/gzyw/fzsgzw/"]},
    "fj_hyyyj": {"name": "福建省海洋与渔业局", "base_url": "https://hyyyj.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xxgk/tzgg/", "/xxgk/hydt/stdt/", "/xxgk/szyw/"]},
    "fj_jgswglj": {"name": "福建省机关事务管理局", "base_url": "https://jgswglj.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xwzx/ggjxw/", "/zwxx/gzdt/", "/zwxx/tpxw/ttxw/"]},
    "fj_jtyst": {"name": "福建省交通运输厅", "base_url": "https://jtyst.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/tzgg/", "/zwgk/jtyw/mtsy/", "/zwgk/zfxxgkzl/zfxxgkml/jtjsgl/"]},
    "fj_jyt": {"name": "福建省教育厅", "base_url": "https://jyt.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xxgk/zcjd/bmzcwjjd/", "/xxgk/zcjd/qtzcwjjd/", "/xxgk/zfxxgkzl/zfxxgkml/zcwj/"]},
    "fj_kjt": {"name": "福建省科学技术厅", "base_url": "https://kjt.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xxgk/tzgg/", "/xxgk/zcwj/", "/xxgk/zcjd/bmzcwjjd/"]},
    "fj_lsj": {"name": "福建省粮食和物资储备局", "base_url": "https://lsj.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xxgk/gsgg/", "/xxgk/gzdt/sxdt/", "/xxgk/gzdt/sjdt/"]},
    "fj_lyj": {"name": "福建省林业局", "base_url": "https://lyj.fujian.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/zcfg/flfg/", "/zwgk/gsgg/", "/zwgk/zcjd/bmzcwj/"]},
    "cq_cgj": {"name": "重庆市城市管理局", "base_url": "https://cgj.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_173/zfxxgkml/zcfg/xzgfxwj_396426/xzgfxwj/", "/zwxx_173/gsgg/tzgg/", "/zwgk_173/zcjd/wzjd/"]},
    "cq_czj": {"name": "重庆市财政局", "base_url": "https://czj.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_268/zfxxgkml/zcwj/qtwj/", "/zwgk_268/zfxxgkml/zcjd/bmjd/", "/zwgk_268/zfxxgkml/zcjd/zctj/"]},
    "cq_dsjj": {"name": "重庆市大数据应用发展管理局", "base_url": "https://dsjj.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_533/zcwj/zcqtwj/", "/zwgk_533/zcjd/", "/zwgk_533/zcjd/ytdd/"]},
    "cq_fzggw": {"name": "重庆市发展和改革委员会", "base_url": "https://fzggw.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/zfxxgkml/zcjd/", "/zwgk/zfxxgkml/zcwj/xzgfxwj/sfzggwxzgfxwj/", "/zwgk/zfxxgkml/zcwj/xzgfxwj/snyjxzgfxwj/"]},
    "cq_gaj": {"name": "重庆市公安局", "base_url": "https://gaj.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/zcwj/qtgw/", "/zwgk/zcjd/ytdd/", "/zwgk/zfgk/gsgg/"]},
    "cq_gbdsj": {"name": "重庆市广播电视局", "base_url": "https://gbdsj.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/zfxxgkml/zcwj/qtwj/", "/zwgk/zfxxgkml/zcjd/wzjd/", "/zwgk/zfxxgkml/zcjd/ytdd/"]},
    "cq_gxhzs": {"name": "重庆市供销合作总社", "base_url": "https://gxhzs.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_524/zfxxgkml/zcwj/zcjd/", "/zwgk_524/zfxxgkml/zcwj/", "/sy/jdtp/"]},
    "cq_gxq": {"name": "重庆高新技术产业开发区管理委员会", "base_url": "https://gxq.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/ztzl/zyzz/", "/zwxx_202/gxdt/bmjz/jzdt/", "/ggtz/"]},
    "cq_gzw": {"name": "重庆市国有资产监督管理委员会门户网站", "base_url": "https://gzw.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_191/fdzdgknr/zcwj/zcwj/", "/zwgk_191/fdzdgknr/zcjdhy/zcjd/", "/tzgg_191/"]},
    "cq_jgswj": {"name": "重庆市机关事务管理局", "base_url": "https://jgswj.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_244/zcwj/", "/zwgk_244/zcjd/", "/zwgk_244/tzgg/"]},
    "cq_jjxxw": {"name": "重庆市经济和信息化委员会", "base_url": "https://jjxxw.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_213/zcwj/qtwj/", "/zwgk_213/zcjd/tpjd/", "/zwgk_213/zcjd/zcwd/zcwdbt/"]},
    "cq_jkq": {"name": "重庆经济技术开发区", "base_url": "https://jkq.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/zcwj/", "/zwgk/zcjd/", "/zwxx/gsgg/"]},
    "cq_jrjgj": {"name": "重庆市地方金融管理局", "base_url": "https://jrjgj.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_208/zfxxgkml1/zcwj/gfxwj/", "/zwgk_208/zcjd/wz/", "/zwgk_208/fdzdgknr/zcwj/jrzc/"]},
    "cq_jtysw": {"name": "重庆市交通运输委员会", "base_url": "https://jtysw.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_240/zfxxgkml/gggs/tzgg/", "/zwgk_240/zfxxgkml/zcwj/xzgfxwj/", "/zwgk_240/zfxxgkml/zcwj/qtwj/"]},
    "cq_jw": {"name": "重庆市教育委员会", "base_url": "https://jw.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/zfxxgkml/zcjd/zcwjk/", "/zwgk/zfxxgkml/zcwj/gfxwj/", "/zwgk/zfxxgkml/zcjd/wzjd/"]},
    "cq_lyj": {"name": "重庆市林业局", "base_url": "https://lyj.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_237/zfxxgjml/zcwj/xzgfxwj/", "/zwgk_237/zfxxgjml/zcwj/qtwj/", "/zwxx_237/tzgg/"]},
    "cq_mzj": {"name": "重庆市民政局", "base_url": "https://mzj.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_218/zfxxgkml/tzgg/", "/zwgk_218/zfxxgkml/zcwj_166256/xzgfxwj1/", "/zwgk_218/zfxxgkml/zcjd/spjd/"]},
    "cq_mzzjw": {"name": "重庆市民族宗教事务委员会", "base_url": "https://mzzjw.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_188/zcjd/", "/zfxxgkml/zcwj/gfxwj/", "/zwgk_188/zfxxgkml/zcwj/gjbwgz/"]},
    "cq_nyncw": {"name": "重庆市农业农村委员会", "base_url": "https://nyncw.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/xxgk_161/zfxxgkml/zcwj/xzgfxwj/", "/xxgk_161/zfxxgkml/zcwj/qtgw/", "/zwxx_161/tzgg/"]},
    "cq_rlsbj": {"name": "重庆市人力资源和社会保障局", "base_url": "https://rlsbj.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_182/zfxxgkml/zcwj_145360/jfxzgfxwj/", "/zwgk_182/zcjd/shbz/", "/zwgk_182/zcjd/jycy/"]},
    "cq_rmfkb": {"name": "重庆市国防动员办公室", "base_url": "https://rmfkb.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_246/zcjd/", "/zwgk_246/fdzdgknr/lzyj/qtwj_40921/", "/sy_246/gsgg/"]},
    "cq_scjgj": {"name": "重庆市市场监督管理局", "base_url": "https://scjgj.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zfxxgk_225/gsgg/qtgg/", "/zfxxgk_225/zcjd/wzjd/", "/zfxxgk_225/zcwj/xzgfxwj/"]},
    "cq_sfj": {"name": "重庆市司法局", "base_url": "https://sfj.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_243/gsgg/", "/zwgk_243/zfxxgkml1/zcjd/zcjdsp/", "/zwgk_243/zfxxgkml1/zcjd/zcjdtp/"]},
    "cq_sjj": {"name": "重庆市审计局", "base_url": "https://sjj.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/gkmu/zc/xz/bbm/", "/zwgk/gkmu/zc/gjbwgz/", "/zwgk/gkmu/zc/qt/"]},
    "cq_slj": {"name": "重庆市水利局", "base_url": "https://slj.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_250/zfxxgkml/tzgg/", "/zwgk_250/zfxxgkml/zcfg/qtxx/", "/zwgk_250/zfxxgkml/zcfg/gfxwj1/"]},
    "cq_sthjj": {"name": "重庆市生态环境局", "base_url": "https://sthjj.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_249/zfxxgkml/zcwj/qtwj/", "/zwgk_249/zfxxgkml/zcjd/wzjd/", "/zwgk_249/zfxxgkml/zcjd/ytdd/"]},
    "cq_sww": {"name": "重庆市商务委员会", "base_url": "https://sww.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_247/zfxxgkml/qtfdxx/tzgg/", "/zwgk_247/zfxxgkmlrk/zcwj/xzffxwj/", "/zwgk_247/zfxxgkmlrk/zcwj/qtwj/"]},
    "cq_tjj": {"name": "重庆市统计局", "base_url": "https://tjj.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_233/fdzdgknr/tjxx/sjzl_55471/jdsj_55474/", "/zwxx_233/tzgg/", "/zwgk_233/fdzdgknr/tjxx/sjjd_55469/"]},
    "cq_tyj": {"name": "重庆市体育局", "base_url": "https://tyj.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwxx_253/tzgg/", "/zwxx_253/bmdt/", "/zwxx_253/mtzs/"]},
    "cq_tyjrswj": {"name": "重庆市退役军人事务局", "base_url": "https://tyjrswj.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_529/zfxxgkml/zcwj/gfxwj/tyjsswjzcwj/", "/zwgk_529/zcjd/tyjsswjzcjdwj/", "/zwgk_529/zfxxgkml/zcwj/qtwj/"]},
    "cq_whlyw": {"name": "重庆市文化和旅游发展委员会", "base_url": "https://whlyw.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_221/zcjd/wzjd/", "/zwgk_221/zcjd/ytdd/", "/zwgk_221/zcjd/yspjd/"]},
    "cq_ws": {"name": "重庆市万盛经济技术开发区管理委员会", "base_url": "https://ws.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_165/gsgg/", "/tzgg/", "/zwgk_165/hygq/"]},
    "cq_wsjkw": {"name": "重庆市卫生健康委员会", "base_url": "https://wsjkw.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_242/zfxxgkml/zcwj/xzgfxwj2/", "/zwgk_242/zcjd/wzjd/", "/zwgk_242/fdzdgknr/tzgg/gzgs/"]},
    "cq_xfb": {"name": "重庆市信访办公众信息网", "base_url": "https://xfb.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_219/zcjd/wzjd/", "/zwgk_219/zcjd/ytdd/", "/zwgk_219/zcjd/spjd/"]},
    "cq_yjj": {"name": "重庆市应急管理局", "base_url": "https://yjj.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_230/tzgg/", "/zwgk_230/zfxxgkml/zcwj/xzgfxwj/", "/zwgk_230/zcjd/wzjd/"]},
    "cq_ylbzj": {"name": "重庆市医疗保障局", "base_url": "https://ylbzj.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_535/zfxxgkml/zcwj_291934/gfxwj/", "/zwgk_535/zfxxgkml/zcwj_291934/qtwj222/", "/zwgk_535/zfxxgkml/zcwj_291934/fzsxwj/"]},
    "cq_zfcxjw": {"name": "重庆市住房和城乡建设委员会", "base_url": "https://zfcxjw.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_166/zfxxgkmls/zcwj/qtwj/", "/zwgk_166/zfxxgkmls/zcjd/ytdd/", "/zwgk_166/zfxxgkmls/zcjd/wzjd/"]},
    "cq_zfkawlb": {"name": "重庆市人民政府口岸和物流办公室", "base_url": "https://zfkawlb.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk/zcwj/qtwj_345067/", "/zwgk/zcjd/tpjd/", "/zwgk/fdzdgknr/zcwj/gjbwgz/"]},
    "cq_zfwb": {"name": "重庆市人民政府外事办公室", "base_url": "https://zfwb.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_162/fdzdgknr/zcwj2/fzsxwj/", "/zwgk_162/fdzdgknr/rs/", "/zwgk_162/fdzdgknr/zcwj2/xzxgfwj/"]},
    "cq_zscqj": {"name": "重庆市知识产权局", "base_url": "https://zscqj.cq.gov.cn",
        "admin_level": "provincial", "group": "dept", "sections": ["/zwgk_232/zcwj/gfxwj/", "/zwgk_232/zcjd/wzjd/", "/zwgk_232/zcjd/tpjd/"]},
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
    # --- 北京市 districts (区政府) — t-date, config-only. ---
    # 海淀 Haidian (Zhongguancun tech hub): its POLICY docs live on the zyk.bjhd.gov.cn
    # content subdomain (not www — www /zwdt/ returns stubs). Found via browser network
    # inspection; droplet reaches zyk fine, /zwdt/zcwj/ + /zwdt/zcjd/ render 70 t-date each.
    "bjd_haidian": {"name": "Beijing Haidian District (北京海淀区)", "base_url": "https://zyk.bjhd.gov.cn",
        "admin_level": "district", "group": "dept", "sections": ["/zwdt/zcwj/", "/zwdt/zcjd/"]},
    "bjd_fangshan": {"name": "Beijing Fangshan District (北京房山区)", "base_url": "https://www.bjfsh.gov.cn",
        "admin_level": "district", "group": "dept", "sections": ["/zwgk/zcjd/", "/zwgk/tzgg/"]},
    "bjd_dongcheng": {"name": "Beijing Dongcheng District (北京东城区)", "base_url": "https://www.bjdch.gov.cn",
        "admin_level": "district", "group": "dept", "sections": ["/zwgk/tzgg/", "/zwgk/zcwj2024/", "/zwgk/zcjd2024/"]},
    "bjd_fengtai": {"name": "Beijing Fengtai District (北京丰台区)", "base_url": "https://www.bjft.gov.cn",
        "admin_level": "district", "group": "dept", "sections": ["/xwdt/zwyw/", "/hdjl/zxft/"]},
    "bjd_miyun": {"name": "Beijing Miyun District (北京密云区)", "base_url": "https://www.bjmy.gov.cn",
        "admin_level": "district", "group": "dept", "sections": ["/zwgk/gsgg/", "/zwgk/zcwj/"]},
    "bjd_huairou": {"name": "Beijing Huairou District (北京怀柔区)", "base_url": "https://www.bjhr.gov.cn",
        "admin_level": "district", "group": "dept", "sections": ["/zwgk/tzgg/", "/ywdt/rdgz/"]},
    "bjd_shijingshan": {"name": "Beijing Shijingshan District (北京石景山区)", "base_url": "https://www.bjsjs.gov.cn",
        "admin_level": "district", "group": "dept", "sections": ["/gongkai/zcwjk/zcwd25/", "/gongkai/zcjd/", "/gongkai/zcwj/"]},
    # --- 北京市 districts round 2 (new article-URL dialects, config-only) ---
    # 通州 Tongzhou: tsid dialect (…/<≥12-digit id>/index.shtml; leading 8 = date).
    "bjd_tongzhou": {"name": "Beijing Tongzhou District (北京通州区)", "base_url": "https://www.bjtzh.gov.cn",
        "admin_level": "district", "group": "dept", "sections": ["/bjtz/zwgk/tzgg/", "/bjtz/zwgk/zcwj/", "/bjtz/zwgk/zcjd/"]},
    # 大兴 Daxing: numid dialect (…/<5-8 digit id>/index.html; no date in URL).
    "bjd_daxing": {"name": "Beijing Daxing District (北京大兴区)", "base_url": "https://www.bjdx.gov.cn",
        "admin_level": "district", "group": "dept", "sections": ["/bjsdxqrmzf/zwfw/tzgg/", "/bjsdxqrmzf/zwfw/zcjd/", "/bjsdxqrmzf/zwfw/zfwj67/"]},
    # 平谷 Pinggu: numid dialect (…/<5-8 digit id>/index.html; no date in URL).
    "bjd_pinggu": {"name": "Beijing Pinggu District (北京平谷区)", "base_url": "https://www.bjpg.gov.cn",
        "admin_level": "district", "group": "dept", "sections": ["/pgqrmzf/zwxx0/tzgg/", "/pgqrmzf/zwxx0/zcwj71/", "/pgqrmzf/zwxx0/zcjd30/"]},
    # 门头沟 Mentougou: hexmon dialect (…/<YYYYMM>/<32-hex>.shtml; date = YYYYMM).
    "bjd_mentougou": {"name": "Beijing Mentougou District (北京门头沟区)", "base_url": "https://www.bjmtg.gov.cn",
        "admin_level": "district", "group": "dept", "sections": ["/bjmtg/2024zcwj/zcwj.shtml", "/bjmtg/2024zcjd/common_list1585033740817.shtml"]},
    # 西城 Xicheng: pnidpv dialect (…/pnidpv<digits>.html; no date in URL).
    "bjd_xicheng": {"name": "Beijing Xicheng District (北京西城区)", "base_url": "https://www.bjxch.gov.cn",
        "admin_level": "district", "group": "dept", "sections": ["/xxgk/tzgg.html", "/xxgk/gfxwj/zfgfxwj.html", "/xxgk/zcjdw.html"]},
    # --- Other major-city districts (t-date, discovered via probe agent) ---
    "njd_gulou": {"name": "Nanjing Gulou District (南京鼓楼区)", "base_url": "http://www.njgl.gov.cn",
        "admin_level": "district", "group": "dept", "sections": ["/xxgk/"]},
    "njd_jiangning": {"name": "Nanjing Jiangning District (南京江宁区)", "base_url": "http://www.jiangning.gov.cn",
        "admin_level": "district", "group": "dept", "sections": ["/xxgk/", "/xxgk/ldzc/"]},
    "whd_jianghan": {"name": "Wuhan Jianghan District (武汉江汉区)", "base_url": "http://www.jianghan.gov.cn",
        "admin_level": "district", "group": "dept", "sections": ["/xwzx/tzgg/", "/xwzx/jhyw/"]},
    "whd_wuchang": {"name": "Wuhan Wuchang District (武汉武昌区)", "base_url": "http://www.wuchang.gov.cn",
        "admin_level": "district", "group": "dept", "sections": ["/zwgk_37/zc/gsgg/", "/zwgk_37/zc/gfxwj/"]},
    "whd_donghu": {"name": "Wuhan East Lake High-Tech Zone (武汉东湖高新区)", "base_url": "http://www.wehdz.gov.cn",
        "admin_level": "district", "group": "dept", "sections": ["/2022/ggxw_68627/ggxw_68629/", "/2022/ggxw_68627/tz_68628/"]},
    "whd_jiangan": {"name": "Wuhan Jiang'an District (武汉江岸区)", "base_url": "http://www.jiangan.gov.cn",
        "admin_level": "district", "group": "dept", "sections": ["/jaxxw/zfxxgk/zc_41333/qtzdgkwj/gsgg/"]},
    "whd_qiaokou": {"name": "Wuhan Qiaokou District (武汉硚口区)", "base_url": "http://www.qiaokou.gov.cn",
        "admin_level": "district", "group": "dept", "sections": ["/xxgk/zc/zcfg/zfwj/", "/qkxw/tzgg/"]},
    "whd_hongshan": {"name": "Wuhan Hongshan District (武汉洪山区)", "base_url": "http://www.hongshan.gov.cn",
        "admin_level": "district", "group": "dept", "sections": ["/tzgg/"]},
    "cqd_yuzhong": {"name": "Chongqing Yuzhong District (重庆渝中区)", "base_url": "http://www.cqyz.gov.cn",
        "admin_level": "district", "group": "dept", "sections": ["/zwgk_229/zcwj/qtwj/", "/zwgk_229/zcjd/mtsj/"]},
    "cqd_jiulongpo": {"name": "Chongqing Jiulongpo District (重庆九龙坡区)", "base_url": "http://www.cqjlp.gov.cn",
        "admin_level": "district", "group": "dept", "sections": ["/zwgk_251/zfxxgkml_1/gggs/", "/zwgk_251/zfxxgkml_1/hygq/", "/zwgk_251/zcwj/gfxwj/"]},
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
#  (F) ARTI: …/YYYY/MM/DD/ARTI<digits>.shtml  (共产党员网 12371.cn). Full date in path.
_ART_ARTI_RE = re.compile(
    r'<a\s+[^>]*href="([^"]*?/(\d{4})/(\d{2})/(\d{2})/ARTI\d+\.s?html?)"[^>]*>(.*?)</a>', re.S)
#  (G) numid: …/<section>/<5-8 digit id>/index.html  (北京大兴/平谷区). No date in URL.
#      Kept 5-8 digits so it can't steal web-idx/tsid (≥12-digit id dirs) — a
#      ≥12-digit contiguous id has no internal '/', so \d{5,8} can never sit right
#      before the trailing /index. Filename is index.* (t-date/art/ARTI have their
#      own filename shapes), so no clash there either.
_ART_NUMID_RE = re.compile(
    r'<a\s+[^>]*href="([^"]*?/\d{5,9}/index\.s?html?)"[^>]*>(.*?)</a>', re.S)
#  (H) tsid: …/<section>/<≥12-digit id>/index.shtml  (北京通州区). No /web/ prefix
#      (that's web-idx). Leading 8 digits of the id are YYYYMMDD when they form a
#      valid date, else no date. web-idx runs first, so its /web/ rows de-dupe ahead
#      of this (identical URL) — this only adds the non-/web/ ≥12-digit rows.
_ART_TSID_RE = re.compile(
    r'<a\s+[^>]*href="([^"]*?/(\d{12,})/index\.s?html?)"[^>]*>(.*?)</a>', re.S)
#  (I) hexmon: …/<section>/<YYYYMM>/<32-hex>.shtml  (北京门头沟区). Date = YYYYMM
#      (day unknown → -01). The 32-hex filename is unique to this dialect.
_ART_HEXMON_RE = re.compile(
    r'<a\s+[^>]*href="([^"]*?/(\d{6})/[0-9a-f]{32}\.s?html?)"[^>]*>(.*?)</a>', re.S)
#  (J) pnidpv: …/pnidpv<digits>.html  (北京西城区). No date in URL. Distinct filename
#      (not index.*, not t-date/art/ARTI) so it can't clash with the others.
_ART_PNIDPV_RE = re.compile(
    r'<a\s+[^>]*href="([^"]*?/pnidpv\d+\.s?html?)"[^>]*>(.*?)</a>', re.S)
#  (K) ccontent: …/c<digits>/content.html  (国资委 SASAC old CMS). Article lives in a
#      c<id> dir; no date in the URL (date comes from the row). Filename is
#      content.html (distinct from t-date/art/index/ARTI shapes), so no clash.
_ART_CCONTENT_RE = re.compile(
    r'<a\s+[^>]*href="([^"]*?/c\d+/content\.s?html?)"[^>]*>(.*?)</a>', re.S)
#  (L) portal: /portal/article/<cat>/<id>  (网安标委 TC260 portal CMS). Id is a 32-hex
#      hash or a 14-digit timestamp; no extension, no date in the URL (date from row).
_ART_PORTAL_RE = re.compile(
    r'<a\s+[^>]*href="([^"]*?/portal/article/\d+/[0-9a-f]{8,})"[^>]*>(.*?)</a>', re.S)
#  (M) nsfc: /p1/<col>/…/<numeric-id>.html  (国家自然科学基金委). The NUMERIC filename is
#      the article (slug-named .html under /p1/ are nav/list pages, so they can't
#      match \d+\.html). List pages carry adjacent dates. Bare dirs 403; slug list ok.
_ART_NSFC_RE = re.compile(
    r'<a\s+[^>]*href="([^"]*?/p1/(?:\d+/)+\d+\.s?html?)"[^>]*>(.*?)</a>', re.S)
#  (N) spc: /fabu/xiangqing/<numeric-id>.html  (最高人民法院). Two-level: the list pages
#      are /fabu/gengduo/<numeric-sectionid>.html (config as sections). Distinct path,
#      so it can't clash with numid (index.html) or the others. Date from list row.
_ART_SPC_RE = re.compile(
    r'<a\s+[^>]*href="([^"]*?/fabu/xiangqing/\d+\.s?html?)"[^>]*>(.*?)</a>', re.S)
#  (O) datepath: …/<cat>/YYYY-MM-DD/<numeric-id>.html  (中医药局 NATCM). The FULL date is
#      in the path (all-dash), distinct from (C) which is /YYYY-MM/DD/content_ID.
_ART_DATEPATH_RE = re.compile(
    r'<a\s+[^>]*href="([^"]*?/(\d{4})-(\d{2})-(\d{2})/\d+\.s?html?)"[^>]*>(.*?)</a>', re.S)
#  (P) safe: /safe/YYYY/MMDD/<numeric-id>.html  (外汇局). Year dir + combined MMDD dir.
#      Anchored on /safe/ so the loose MMDD can't false-match other sites' /YYYY/NNNN/.
_ART_SAFE_RE = re.compile(
    r'<a\s+[^>]*href="([^"]*?/safe/(\d{4})/(\d{2})(\d{2})/\d+\.s?html?)"[^>]*>(.*?)</a>', re.S)
#  (Q) ymd8: …/YYYYMMDD/<numeric-id>.html  (林草局 SFA). 8-digit date dir + numeric file
#      (D is /YYYYMMDD/<hex>/c.html — different filename). Date validated to avoid
#      false-matching a non-date 8-digit dir.
_ART_YMD8_RE = re.compile(
    r'<a\s+[^>]*href="([^"]*?/(\d{4})(\d{2})(\d{2})/\d+\.s?html?)"[^>]*>(.*?)</a>', re.S)
#  (R) schex: …/YYYY/M/D/<32-hex>.shtml  (四川省 Sichuan). Slash-separated NON-zero-padded
#      date dirs + 32-hex filename. Distinct from D (/YYYYMMDD/hex/c.html) and O (dashes).
_ART_SCHEX_RE = re.compile(
    r'<a\s+[^>]*href="([^"]*?/(\d{4})/(\d{1,2})/(\d{1,2})/[0-9a-f]{32}\.s?html?)"[^>]*>(.*?)</a>', re.S)
#  (S) hbuuid: /columns/<colUUID>/YYYYMM/DD/<artUUID>.html  (河北省). UUID columns +
#      UUID article ids; date is YYYYMM/DD in the path.
_ART_HBUUID_RE = re.compile(
    r'<a\s+[^>]*href="([^"]*?/columns/[a-f0-9-]{36}/(\d{4})(\d{2})/(\d{2})/[a-f0-9-]{36}\.s?html?)"[^>]*>(.*?)</a>', re.S)
#  (T) shhex: …/YYYYMMDD/<32-hex>.html  (上海市 depts). 8-digit date dir + 32-hex file
#      (distinct from D /YYYYMMDD/<hex>/c.html, I /YYYYMM/<hex>.shtml, Q /YYYYMMDD/<num>).
_ART_SHHEX_RE = re.compile(
    r'<a\s+[^>]*href="([^"]*?/(\d{4})(\d{2})(\d{2})/[0-9a-f]{32}\.s?html?)"[^>]*>(.*?)</a>', re.S)
#  (U) qhsys: …/system/YYYY/MM/DD/<numeric-id>.shtml  (青海省). Anchored on /system/ so the
#      loose date path can't false-match other sites. Distinct from R schex (32-hex file),
#      Q ymd8 (no slashes), O datepath (dashes).
_ART_QHSYS_RE = re.compile(
    r'<a\s+[^>]*href="([^"]*?/system/(\d{4})/(\d{2})/(\d{2})/\d+\.s?html?)"[^>]*>(.*?)</a>', re.S)
#  (V) cmon: …/c<col>/<YYYYMM>/<numeric-id>.shtml  (国家民委 NEAC, TRS-WCM). Column dir
#      c<digits> + YYYYMM month dir + NUMERIC file. Distinct from I hexmon (32-hex file) and
#      K ccontent (literal content.html). Row date (_DATE_NEAR) overrides the YYYYMM-01.
#      Added LAST so existing dialects win the URL de-dupe.
_ART_CMON_RE = re.compile(
    r'<a\s+[^>]*href="([^"]*?/c\d+/(\d{4})(\d{2})/\d+\.s?html?)"[^>]*>(.*?)</a>', re.S)
_ART_TITLE_ATTR = re.compile(r'title="([^"]+)"')
_DATE_NEAR = re.compile(r'(\d{4}-\d{2}-\d{2})')
# Publish-date from the ARTICLE body, used only when the list row carried no date
# (e.g. TC260 /portal/ + the dateless numid/pnidpv/ccontent dialects). Label-anchored
# on 发布/发表/时间/日期 so it can't grab a random in-body date; fires only as a fallback.
_PUB_DATE = re.compile(r'(?:发布|发表|时间|日期)[^0-9<]{0,10}(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})')
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
    r'class="[^"]*detail[-_]?content',       # SAFE 外汇局
    r'class="[^"]*pub[-_]?det(?:ail|-content)',  # NFSRA 粮储局
    r'id="ivs_content"',                     # 上海市 depts (Article_content / ivs_content)
    r'class="[^"]*Article_content',          # 上海市 depts
    r'class="[^"]*main[-_]txt',              # 江苏省 depts (dialect B, main-txt)
]
_FOOT_CUT = re.compile(r'(相关(?:附件|链接|文件|报道)|扫一扫|打印本页|class="[^"]*(?:foot|share|xglj|fujian|print))')


def _clean(t: str) -> str:
    t = re.sub(r"<[^>]+>", "", t)
    t = H.unescape(t)
    return re.sub(r"\s+", " ", t).strip()


def _valid_ymd(s: str) -> bool:
    """True if s is 8 digits forming a plausible YYYYMMDD (1900-2099, mm 01-12,
    dd 01-31). Used by the tsid dialect where the id's leading 8 digits are a
    pub date only some of the time."""
    if len(s) != 8 or not s.isdigit():
        return False
    y, mo, d = int(s[:4]), int(s[4:6]), int(s[6:8])
    return 1900 <= y <= 2099 and 1 <= mo <= 12 and 1 <= d <= 31


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
    for m in _ART_ARTI_RE.finditer(page_html):
        y, mo, d = m.group(2), m.group(3), m.group(4)
        matches.append((m, m.group(1), m.group(5), f"{y}-{mo}-{d}"))
    # --- new dialects (after the existing ones so those win the de-dupe) ---
    for m in _ART_NUMID_RE.finditer(page_html):        # (G) numid: no date in URL
        matches.append((m, m.group(1), m.group(2), ""))
    for m in _ART_TSID_RE.finditer(page_html):         # (H) tsid: leading-8 may be date
        ymd = m.group(2)[:8]
        date_str = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}" if _valid_ymd(ymd) else ""
        matches.append((m, m.group(1), m.group(3), date_str))
    for m in _ART_HEXMON_RE.finditer(page_html):       # (I) hexmon: YYYYMM dir → -01
        ym = m.group(2)
        mo = int(ym[4:6])
        date_str = f"{ym[:4]}-{ym[4:6]}-01" if 1 <= mo <= 12 else ""
        matches.append((m, m.group(1), m.group(3), date_str))
    for m in _ART_PNIDPV_RE.finditer(page_html):       # (J) pnidpv: no date in URL
        matches.append((m, m.group(1), m.group(2), ""))
    for m in _ART_CCONTENT_RE.finditer(page_html):     # (K) ccontent (SASAC): no date in URL
        matches.append((m, m.group(1), m.group(2), ""))
    for m in _ART_PORTAL_RE.finditer(page_html):       # (L) portal (TC260): no date in URL
        matches.append((m, m.group(1), m.group(2), ""))
    for m in _ART_NSFC_RE.finditer(page_html):         # (M) nsfc: date from row (_DATE_NEAR)
        matches.append((m, m.group(1), m.group(2), ""))
    for m in _ART_SPC_RE.finditer(page_html):          # (N) spc: date from row
        matches.append((m, m.group(1), m.group(2), ""))
    for m in _ART_DATEPATH_RE.finditer(page_html):     # (O) datepath: full date in path
        y, mo, d = m.group(2), m.group(3), m.group(4)
        matches.append((m, m.group(1), m.group(5), f"{y}-{mo}-{d}"))
    for m in _ART_SAFE_RE.finditer(page_html):         # (P) safe: YYYY/MMDD in path
        y, mo, d = m.group(2), m.group(3), m.group(4)
        date_str = f"{y}-{mo}-{d}" if 1 <= int(mo) <= 12 and 1 <= int(d) <= 31 else ""
        matches.append((m, m.group(1), m.group(5), date_str))
    for m in _ART_YMD8_RE.finditer(page_html):         # (Q) ymd8 (SFA): validated YYYYMMDD dir
        y, mo, d = m.group(2), m.group(3), m.group(4)
        date_str = f"{y}-{mo}-{d}" if 2000 <= int(y) <= 2099 and 1 <= int(mo) <= 12 and 1 <= int(d) <= 31 else ""
        matches.append((m, m.group(1), m.group(5), date_str))
    for m in _ART_SCHEX_RE.finditer(page_html):        # (R) schex (Sichuan): YYYY/M/D in path
        y, mo, d = m.group(2), m.group(3), m.group(4)
        matches.append((m, m.group(1), m.group(5), f"{y}-{int(mo):02d}-{int(d):02d}"))
    for m in _ART_HBUUID_RE.finditer(page_html):       # (S) hbuuid (Hebei): YYYYMM/DD in path
        y, mo, d = m.group(2), m.group(3), m.group(4)
        matches.append((m, m.group(1), m.group(5), f"{y}-{mo}-{d}"))
    for m in _ART_SHHEX_RE.finditer(page_html):        # (T) shhex (Shanghai): YYYYMMDD in path
        y, mo, d = m.group(2), m.group(3), m.group(4)
        date_str = f"{y}-{mo}-{d}" if 1 <= int(mo) <= 12 and 1 <= int(d) <= 31 else ""
        matches.append((m, m.group(1), m.group(5), date_str))
    for m in _ART_QHSYS_RE.finditer(page_html):        # (U) qhsys (Qinghai): full date in /system/ path
        y, mo, d = m.group(2), m.group(3), m.group(4)
        matches.append((m, m.group(1), m.group(5), f"{y}-{mo}-{d}"))
    for m in _ART_CMON_RE.finditer(page_html):         # (V) cmon (NEAC): YYYYMM dir → -01, row date wins
        ym4, mo = m.group(2), m.group(3)
        date_str = f"{ym4}-{mo}-01" if 1 <= int(mo) <= 12 else ""
        matches.append((m, m.group(1), m.group(4), date_str))
    out, seen = [], set()
    page_host = urlparse(page_url).netloc
    for m, href, inner, url_date in matches:
        url = urljoin(page_url, H.unescape(href))
        if url in seen:
            continue
        seen.add(url)
        # Quality guards: keep only this site's own articles. Cross-host links are
        # nav (e.g. SASAC's "国务院部门网站" → gov.cn); a residual /../ means urljoin
        # couldn't normalize a protocol-relative ../.. href (→ 400s, e.g. CAS).
        if urlparse(url).netloc != page_host or "/../" in url:
            continue
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


def crawl_site(conn, site_key, cfg, fetch_bodies=True, deep=False, max_pages=30,
               write_lock=None):
    # write_lock: optional threading.Lock shared across parallel --group workers.
    # It guards ONLY the quick id-allocate + insert + commit critical section, so
    # the slow body fetches stay parallel while next_id()/store_document() are
    # serialized — preventing both "database is locked" AND the next_id() race
    # (MAX(id)+1 collisions that ON CONFLICT(id) would silently merge = data loss).
    wlock = write_lock if write_lock is not None else nullcontext()
    base = cfg["base_url"].rstrip("/")
    with wlock:
        store_site(conn, site_key, cfg)
        conn.commit()
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
                # SLOW body fetch happens OUTSIDE the write lock (raw HTML is saved
                # under a temp name keyed by url hash, renamed to the real doc_id
                # inside the lock once the id is known).
                body, dh, meta = "", None, {}
                if fetch_bodies:
                    try:
                        dh = fetch(it["url"], headers=UA)
                        body = _extract_body(dh)
                        meta = _extract_metadata_table(dh)
                        if not it["date"]:            # list row had no date → try body
                            pdm = _PUB_DATE.search(dh)
                            if pdm:
                                it["date"] = f"{pdm.group(1)}-{int(pdm.group(2)):02d}-{int(pdm.group(3)):02d}"
                    except Exception as e:
                        log.warning(f"    body {it['url']}: {e}")
                    time.sleep(REQUEST_DELAY)
                # SHORT critical section: allocate id, persist raw, insert, commit.
                with wlock:
                    doc_id = next_id(conn)
                    raw = save_raw_html(site_key, doc_id, dh) if dh is not None else ""
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
                    conn.commit()  # commit inside the lock: no txn stays open across
                    stored += 1    # the next fetch, so a second worker never blocks
            log.info(f"  {section} [{page_url.split('/')[-1]}]: +{new}")
            if not deep:
                break
    log.info(f"[{site_key}] done: {stored} new docs")
    return stored


def main():
    ap = argparse.ArgumentParser(description="Generic gov t-date list crawler")
    ap.add_argument("--site")
    ap.add_argument("--group", help="crawl every site tagged with this group (e.g. 'dept')")
    ap.add_argument("--workers", type=int, default=4, help="parallel workers for --group (writes serialized by a shared lock, so this only parallelizes the network fetches — safe to raise)")
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
        # crawl all sites tagged with this group, in parallel, into one DB.
        keys = [k for k, c in SITES.items() if c.get("group") == args.group]
        if not keys:
            print(f"No sites tagged group={args.group!r}")
            return

        # One shared lock guards the id-allocate+insert+commit critical section
        # across all workers, so the slow body fetches run in parallel while writes
        # are serialized (no lock contention, no next_id() race). Each worker still
        # gets its OWN connection (sqlite3 conns aren't thread-safe to share).
        write_lock = threading.Lock()

        def _one(k):
            conn = init_db(args.db) if args.db else init_db()
            conn.execute("PRAGMA busy_timeout=60000")
            try:
                crawl_site(conn, k, SITES[k], fetch_bodies=not args.list_only,
                           deep=args.deep, write_lock=write_lock)
                return (k, "ok")
            except Exception as e:  # one dept failing must not abort the group
                return (k, f"FAILED {type(e).__name__}: {e}")
            finally:
                conn.close()

        workers = max(1, args.workers)
        print(f"[{args.group}] crawling {len(keys)} sites with {workers} workers")
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(_one, k): k for k in keys}
            for fut in as_completed(futs):
                k, status = fut.result()
                print(f"  [{args.group}] {k}: {status}")
        show_stats(init_db(args.db) if args.db else init_db())
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
