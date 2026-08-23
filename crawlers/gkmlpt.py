"""
Guangdong gkmlpt platform crawler.

Handles the 政府信息公开目录管理平台 (Government Information Disclosure Directory
Management Platform) used by all Guangdong Province government sites.

Usage:
    python -m crawlers.gkmlpt                    # Crawl all configured sites
    python -m crawlers.gkmlpt --site sz          # Crawl only main portal
    python -m crawlers.gkmlpt --list-sites       # Show configured sites
    python -m crawlers.gkmlpt --stats            # Show database stats
"""

import argparse
import json
import re
import sqlite3
import time
import urllib.parse
from datetime import datetime, timezone

import uuid

from crawlers.base import (
    REQUEST_DELAY,
    fetch,
    fetch_json,
    init_db,
    log,
    save_raw_html,
    show_stats,
    store_site,
)

# --- Configuration ---

BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
SITES_NEEDING_BROWSER_UA = {"gd"}  # site keys that need browser UA to avoid connection reset

# Guangdong province-wide gkml full-text search (JSONP). Every GD gkmlpt page's
# _CONFIG.SEARCH_JSONP_URL points here. Its index reaches OLDER documents than a
# category's public listing window: the per-category `api/all/{cat}` endpoint only
# exposes a recent slice (served count << classify.post_count, floor ~2011–2018),
# whereas this search returns matches back to ~2001. It is therefore the only
# gkmlpt-native lever for the historical backfill — see search_site_index().
# GOTCHA: the endpoint is 1-INDEXED (page=1 is the first page; page=0 returns
# {"results":[],"count":0}) and it is JSONP, so a `callback` param is REQUIRED
# (without it the server answers {"errcode":-1} "调用失败，请检查参数").
SEARCH_BASE = "http://search.gd.gov.cn/jsonp"

# Known-broken / unreliable site keys and WHY. These are still in SITES so a
# manual `--site X` can retry them if the site recovers, but a bulk run will
# just fail on them. (Consolidated from CLAUDE.md "Known Issues", June 2026 —
# keep this the single source of truth; the docs point here.)
KNOWN_BROKEN = {
    "dongguan": "endpoint unreachable (DNS/timeout/Cloudflare)",
    "foshan":   "endpoint unreachable (DNS/timeout/Cloudflare)",
    "szba":     "Bao'an endpoint unreachable (DNS/timeout/Cloudflare)",
    "shantou":  "interrupted mid-crawl — only ~49 docs; needs a clean re-run",
    "zhaoqing": "0 docs — crawl failed on SQLite lock contention; run sequentially",
    "zhanjiang":"0 docs — crawl failed on SQLite lock contention; run sequentially",
    "chaozhou": "0 docs — crawl failed on SQLite lock contention; run sequentially",
    "szyantian":"Yantian: 0 docs — failed on SQLite lock contention; run sequentially",
    "gd":       "partial (~6,169 docs) — needs browser UA + a full re-run for the whole corpus",
}

SITES = {
    # Municipal
    "sz": {
        "name": "Shenzhen Main Portal",
        "base_url": "http://www.sz.gov.cn",
        "admin_level": "municipal",
    },
    # Departments
    "zjj": {
        "name": "Housing & Construction Bureau",
        "base_url": "http://zjj.sz.gov.cn",
        "admin_level": "department",
    },
    "stic": {
        "name": "S&T Innovation Bureau",
        "base_url": "http://stic.sz.gov.cn",
        "admin_level": "department",
    },
    "fgw": {
        "name": "Development & Reform Commission",
        "base_url": "http://fgw.sz.gov.cn",
        "admin_level": "department",
    },
    "hrss": {
        "name": "Human Resources & Social Security",
        "base_url": "http://hrss.sz.gov.cn",
        "admin_level": "department",
    },
    "mzj": {
        "name": "Civil Affairs Bureau",
        "base_url": "http://mzj.sz.gov.cn",
        "admin_level": "department",
    },
    "sf": {
        "name": "Justice Bureau",
        "base_url": "http://sf.sz.gov.cn",
        "admin_level": "department",
    },
    "jtys": {
        "name": "Transport Bureau",
        "base_url": "http://jtys.sz.gov.cn",
        "admin_level": "department",
    },
    "swj": {
        "name": "Commerce Bureau",
        "base_url": "http://swj.sz.gov.cn",
        "admin_level": "department",
    },
    "wjw": {
        "name": "Health Commission",
        "base_url": "http://wjw.sz.gov.cn",
        "admin_level": "department",
    },
    "szeb": {
        "name": "Education Bureau",
        "base_url": "http://szeb.sz.gov.cn",
        "admin_level": "department",
    },
    "yjgl": {
        "name": "Emergency Management Bureau",
        "base_url": "http://yjgl.sz.gov.cn",
        "admin_level": "department",
    },
    "audit": {
        "name": "Audit Bureau",
        "base_url": "http://audit.sz.gov.cn",
        "admin_level": "department",
    },
    "ga": {
        "name": "Public Security Bureau",
        "base_url": "http://ga.sz.gov.cn",
        "admin_level": "department",
    },
    # Districts
    "szpsq": {
        "name": "Pingshan District",
        "base_url": "http://www.szpsq.gov.cn",
        "admin_level": "district",
    },
    "szgm": {
        "name": "Guangming District",
        "base_url": "http://www.szgm.gov.cn",
        "admin_level": "district",
    },
    "szns": {
        "name": "Nanshan District",
        "base_url": "http://www.szns.gov.cn",
        "admin_level": "district",
    },
    "szft": {
        "name": "Futian District",
        "base_url": "http://www.szft.gov.cn",
        "admin_level": "district",
    },
    "szlh": {
        "name": "Luohu District",
        "base_url": "http://www.szlh.gov.cn",
        "admin_level": "district",
    },
    "szlhq": {
        "name": "Longhua District",
        "base_url": "http://www.szlhq.gov.cn",
        "admin_level": "district",
    },
    # Provincial
    "gd": {  # ⚠ KNOWN_BROKEN (see registry above)
        "name": "Guangdong Province",
        "base_url": "http://www.gd.gov.cn",
        "admin_level": "provincial",
    },
    # Provincial departments (gkmlpt — SID auto-discovered; added 2026-07-15 to
    # reach the 广东省自然资源厅/人社厅 regs that dominate the missing-article
    # frontier, e.g. 广东省...控制性详细规划管理指导意见 ×287, 招聘体检细则 ×244).
    "gdnr": {
        "name": "Guangdong Natural Resources Dept (自然资源厅)",
        "base_url": "https://nr.gd.gov.cn",
        "admin_level": "provincial",
    },
    "gdhrss": {
        "name": "Guangdong Human Resources Dept (人社厅)",
        "base_url": "https://hrss.gd.gov.cn",
        "admin_level": "provincial",
    },
    "gdzjst": {
        "name": "Guangdong Housing & Construction Dept (住建厅)",
        "base_url": "https://zfcxjst.gd.gov.cn",
        "admin_level": "provincial",
    },
    # More GD provincial departments — all verified gkmlpt (SID auto-discovered,
    # 2026-07-15 batch probe). 16/20 candidates crawlable; 水利厅/市场监管局/司法厅/
    # 审计厅 need the correct domain (HTTPError on the guessed host).
    "gdedu": {"name": "Guangdong Education Dept (教育厅)", "base_url": "https://edu.gd.gov.cn", "admin_level": "provincial"},
    "gdstc": {"name": "Guangdong Science & Tech Dept (科技厅)", "base_url": "https://gdstc.gd.gov.cn", "admin_level": "provincial"},
    "gdii": {"name": "Guangdong Industry & IT Dept (工信厅)", "base_url": "https://gdii.gd.gov.cn", "admin_level": "provincial"},
    "gdga": {"name": "Guangdong Public Security Dept (公安厅)", "base_url": "https://gdga.gd.gov.cn", "admin_level": "provincial"},
    "gdmz": {"name": "Guangdong Civil Affairs Dept (民政厅)", "base_url": "https://smzt.gd.gov.cn", "admin_level": "provincial"},
    "gdczt": {"name": "Guangdong Finance Dept (财政厅)", "base_url": "https://czt.gd.gov.cn", "admin_level": "provincial"},
    "gdee": {"name": "Guangdong Ecology & Environment Dept (生态环境厅)", "base_url": "https://gdee.gd.gov.cn", "admin_level": "provincial"},
    "gdjt": {"name": "Guangdong Transport Dept (交通运输厅)", "base_url": "https://td.gd.gov.cn", "admin_level": "provincial"},
    "gdny": {"name": "Guangdong Agriculture & Rural Affairs Dept (农业农村厅)", "base_url": "https://dara.gd.gov.cn", "admin_level": "provincial"},
    "gdcom": {"name": "Guangdong Commerce Dept (商务厅)", "base_url": "https://com.gd.gov.cn", "admin_level": "provincial"},
    "gdct": {"name": "Guangdong Culture & Tourism Dept (文旅厅)", "base_url": "https://whly.gd.gov.cn", "admin_level": "provincial"},
    "gdwjw": {"name": "Guangdong Health Commission (卫健委)", "base_url": "https://wsjkw.gd.gov.cn", "admin_level": "provincial"},
    "gdyjt": {"name": "Guangdong Emergency Management Dept (应急管理厅)", "base_url": "https://yjgl.gd.gov.cn", "admin_level": "provincial"},
    "gdlyj": {"name": "Guangdong Forestry Bureau (林业局)", "base_url": "https://lyj.gd.gov.cn", "admin_level": "provincial"},
    "gdhsa": {"name": "Guangdong Healthcare Security Bureau (医保局)", "base_url": "https://hsa.gd.gov.cn", "admin_level": "provincial"},
    "gddrc": {"name": "Guangdong Development & Reform Commission (发改委)", "base_url": "https://drc.gd.gov.cn", "admin_level": "provincial"},
    "gdstats": {"name": "Guangdong Statistics Bureau (统计局)", "base_url": "https://stats.gd.gov.cn", "admin_level": "provincial"},
    # GD provincial depts still TODO (correct domain or non-gkmlpt): 水利厅/市场监管局/
    # 司法厅/审计厅. Provincial-dept batch at diminishing returns (20 added).
    # Other Guangdong municipal
    "gz": {
        "name": "Guangzhou",
        "base_url": "http://www.gz.gov.cn",
        "admin_level": "municipal",
    },
    "zhuhai": {
        "name": "Zhuhai",
        "base_url": "http://www.zhuhai.gov.cn",
        "admin_level": "municipal",
    },
    "huizhou": {
        "name": "Huizhou",
        "base_url": "http://www.huizhou.gov.cn",
        "admin_level": "municipal",
    },
    "jiangmen": {
        "name": "Jiangmen",
        "base_url": "http://www.jiangmen.gov.cn",
        "admin_level": "municipal",
    },
    "zhongshan": {
        "name": "Zhongshan",
        "base_url": "http://www.zs.gov.cn",
        "admin_level": "municipal",
    },
    "shantou": {  # ⚠ KNOWN_BROKEN (see registry above)
        "name": "Shantou",
        "base_url": "http://www.shantou.gov.cn",
        "admin_level": "municipal",
    },
    "zhaoqing": {  # ⚠ KNOWN_BROKEN (see registry above)
        "name": "Zhaoqing",
        "base_url": "http://www.zhaoqing.gov.cn",
        "admin_level": "municipal",
    },
    "shaoguan": {
        "name": "Shaoguan",
        "base_url": "http://www.sg.gov.cn",
        "admin_level": "municipal",
    },
    "heyuan": {
        "name": "Heyuan",
        "base_url": "http://www.heyuan.gov.cn",
        "admin_level": "municipal",
    },
    "shanwei": {
        "name": "Shanwei",
        "base_url": "http://www.shanwei.gov.cn",
        "admin_level": "municipal",
    },
    "yangjiang": {
        "name": "Yangjiang",
        "base_url": "http://www.yangjiang.gov.cn",
        "admin_level": "municipal",
    },
    "zhanjiang": {  # ⚠ KNOWN_BROKEN (see registry above)
        "name": "Zhanjiang",
        "base_url": "http://www.zhanjiang.gov.cn",
        "admin_level": "municipal",
    },
    "chaozhou": {  # ⚠ KNOWN_BROKEN (see registry above)
        "name": "Chaozhou",
        "base_url": "http://www.chaozhou.gov.cn",
        "admin_level": "municipal",
    },
    "jieyang": {
        "name": "Jieyang",
        "base_url": "http://www.jieyang.gov.cn",
        "admin_level": "municipal",
    },
    "yunfu": {
        "name": "Yunfu",
        "base_url": "http://www.yunfu.gov.cn",
        "admin_level": "municipal",
    },
    # More Shenzhen districts
    "szyantian": {  # ⚠ KNOWN_BROKEN (see registry above)
        "name": "Yantian District",
        "base_url": "http://www.yantian.gov.cn",
        "admin_level": "district",
    },
    "szlg": {
        "name": "Longgang District",
        "base_url": "http://www.lg.gov.cn",
        "admin_level": "district",
    },
    "szdp": {
        "name": "Dapeng New District",
        "base_url": "http://www.dpxq.gov.cn",
        "admin_level": "district",
    },
    "szba": {  # ⚠ KNOWN_BROKEN (see registry above)
        "name": "Bao'an District",
        "base_url": "http://www.baoan.gov.cn",
        "admin_level": "district",
    },
    # Remaining Guangdong municipal
    "dongguan": {  # ⚠ KNOWN_BROKEN (see registry above)
        "name": "Dongguan",
        "base_url": "http://www.dg.gov.cn",
        "admin_level": "municipal",
    },
    "foshan": {  # ⚠ KNOWN_BROKEN (see registry above)
        "name": "Foshan",
        "base_url": "http://www.foshan.gov.cn",
        "admin_level": "municipal",
    },
}


# --- Site Discovery ---

def discover_site(base_url: str, headers: dict = None) -> tuple[str, list]:
    """Fetch /gkmlpt/index and extract SID and TREE from _CONFIG."""
    url = f"{base_url}/gkmlpt/index"
    log.info(f"Discovering site config: {url}")
    html = fetch(url, timeout=30, headers=headers)

    # Extract SID
    sid_match = re.search(r"SID:\s*'(\d+)'", html)
    if not sid_match:
        raise ValueError(f"Could not find SID in {url}")
    sid = sid_match.group(1)

    # Extract TREE
    config_match = re.search(r"window\._CONFIG\s*=\s*\{", html)
    if not config_match:
        raise ValueError(f"Could not find _CONFIG in {url}")

    start = config_match.start() + len("window._CONFIG = ")
    depth = 0
    i = start
    while i < len(html):
        if html[i] == "{":
            depth += 1
        elif html[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    config_str = html[start : i + 1]

    tree_match = re.search(
        r"TREE:\s*(\[.*?\])\s*,\s*SERVICE_AREA_ID", config_str, re.DOTALL
    )
    if not tree_match:
        raise ValueError(f"Could not find TREE in _CONFIG from {url}")

    tree = json.loads(tree_match.group(1))
    log.info(f"  SID={sid}, {len(tree)} top-level categories")
    return sid, tree


def get_leaf_categories(tree: list) -> list[tuple[int, str]]:
    """Extract leaf category IDs (no jump_url, no children) from the tree."""
    leaves = []
    for node in tree:
        if node.get("jump_url"):
            continue
        if node.get("children"):
            child_leaves = get_leaf_categories(node["children"])
            if child_leaves:
                leaves.extend(child_leaves)
            else:
                leaves.append((node["id"], node["name"]))
        else:
            leaves.append((node["id"], node["name"]))
    return leaves


# --- Listing Discovery ---

def crawl_category(
    base_url: str, sid: str, cat_id: int, cat_name: str, headers: dict = None
) -> list[dict]:
    """Fetch all documents in a category via the API."""
    page = 1
    all_articles = []
    post_count = None

    while True:
        url = f"{base_url}/gkmlpt/api/all/{cat_id}?page={page}&sid={sid}"
        try:
            data = fetch_json(url, headers=headers)
        except (json.JSONDecodeError, ValueError):
            break
        except Exception as e:
            log.warning(f"  API error for category {cat_id} page {page}: {e}")
            break

        if post_count is None:
            post_count = data.get("classify", {}).get("post_count", 0)
            log.info(f"  [{cat_id}] {cat_name}: {post_count} documents")

        articles = data.get("articles", [])
        if not articles:
            break

        all_articles.extend(articles)

        if len(all_articles) >= post_count:
            break

        page += 1
        time.sleep(REQUEST_DELAY)

    return all_articles


# --- Historical Search Backfill (search.gd.gov.cn) ---

def _fetch_jsonp(url: str, headers: dict = None, timeout: int = 25) -> dict:
    """Fetch a JSONP endpoint and return the unwrapped JSON payload.

    The response looks like `cb({...})`; strip the callback wrapper before parsing.
    """
    txt = fetch(url, timeout=timeout, headers=headers).strip()
    m = re.match(r"^[A-Za-z_$][\w$]*\((.*)\)\s*;?\s*$", txt, re.DOTALL)
    payload = m.group(1) if m else txt
    return json.loads(payload)


def _normalize_search_article(r: dict) -> dict:
    """Map a search.gd.gov.cn result object onto the gkmlpt article schema that
    store_gkmlpt_document() expects (field names differ from api/all/{cat})."""
    def _int(x):
        try:
            return int(x)
        except (TypeError, ValueError):
            return 0

    # date_published: search uses `pub_time` (YYYY-MM-DD); the per-category feed
    # stores "YYYY-MM-DD 00:00:00" — match that so both sources look identical.
    pub = (r.get("pub_time") or "").strip()
    created_at = f"{pub} 00:00:00" if re.match(r"^\d{4}-\d{2}-\d{2}$", pub) else ""

    # `attachment` arrives as a JSON *string* here; store_gkmlpt_document json.dumps()
    # it, so decode to a list first to avoid double-encoding.
    att = r.get("attachment", [])
    if isinstance(att, str):
        try:
            att = json.loads(att)
        except Exception:
            att = []

    title = re.sub(r"</?em>", "", r.get("title", "") or "")  # strip highlight tags
    return {
        "id": _int(r.get("id")),
        "title": title,
        "document_number": r.get("document_number", "") or "",
        "identifier": r.get("identifier", "") or "",
        "publisher": r.get("publisher", "") or "",
        "keywords": r.get("keywords", "") or "",
        "date": _int(r.get("date")),
        "created_at": created_at,
        "display_publish_time": _int(r.get("display_publish_time")),
        "abstract": r.get("abstract", "") or "",
        "classify_main": _int(r.get("classify_main")),
        "classify_main_name": r.get("classify_main_name", "") or "",
        "classify_genre_name": r.get("classify_genre_name", "") or "",
        "classify_theme_name": r.get("classify_theme_name", "") or "",
        "url": (r.get("url", "") or "").strip(),
        "post_url": r.get("post_url", "") or "",
        "is_expired": _int(r.get("is_expired")),
        "is_abolished": _int(r.get("is_abolished")),
        "attachment": att,
        "relation": "",
    }


def search_site_index(sid: str, keyword: str, headers: dict = None,
                      max_pages: int = 10, pagesize: int = 20, position: str = ""):
    """Yield normalized gkml article dicts for `keyword`, scoped to one site's SID.

    Uses the Guangdong-wide search (SEARCH_BASE), whose index reaches historical
    documents the per-category `api/all` listing has since dropped from its window.
    `position="title"` restricts matching to titles (still fuzzy/OR-ranked); ""
    searches full text. Only gkml content-page results are yielded.
    """
    seen = set()
    for page in range(1, max_pages + 1):  # 1-indexed — page 0 is always empty
        params = {
            "page": page, "pagesize": pagesize, "isgkml": 1,
            "text": keyword, "order": 0,
            "including_url_doc": 1, "including_attach_doc": 1,
            "classify_main_name": "", "classify_mains": "",
            "classify_mains_excluded": "", "position": position,
            "callback": "cb",
        }
        url = f"{SEARCH_BASE}/site/{sid}?{urllib.parse.urlencode(params)}"
        try:
            data = _fetch_jsonp(url, headers=headers)
        except Exception as e:
            log.warning(f"  search error p{page} '{keyword}': {e}")
            break

        results = data.get("results") or []
        if not results:
            break

        for r in results:
            if str(r.get("isgkml")) != "1":
                continue
            if "/gkmlpt/content/" not in (r.get("url") or ""):
                continue
            art = _normalize_search_article(r)
            if not art["id"] or art["id"] in seen:
                continue
            seen.add(art["id"])
            yield art

        if len(results) < pagesize:
            break
        time.sleep(REQUEST_DELAY)


def search_backfill(conn, site_key: str, site_cfg: dict, keywords: list[str],
                    max_pages: int = 10, position: str = "", fetch_bodies: bool = True):
    """Recover historical gkml docs via search.gd.gov.cn for a set of keywords.

    For each keyword, search the site's index, skip docs already in the DB (by id
    or url), fetch body text, and store. Follows the same store/body-fetch path as
    crawl_site so recovered docs are indistinguishable from category-crawled ones.
    """
    base_url = site_cfg["base_url"]
    ua_headers = {"User-Agent": BROWSER_UA, "Referer": base_url.rstrip("/") + "/"}

    # Reuse the stored SID if we've crawled this site before; else discover it.
    row = conn.execute("SELECT sid FROM sites WHERE site_key = ?", (site_key,)).fetchone()
    sid = row[0] if row and row[0] else None
    if not sid:
        try:
            disc_headers = ua_headers if site_key in SITES_NEEDING_BROWSER_UA else None
            sid, tree = discover_site(base_url, headers=disc_headers)
            store_site(conn, site_key, site_cfg, sid, tree)
        except Exception as e:
            log.error(f"Cannot resolve SID for {site_key}: {e}")
            return None

    log.info(f"=== Search-backfill {site_cfg['name']} (sid={sid}) — "
             f"{len(keywords)} keyword(s), pos='{position or 'fulltext'}' ===")

    added = skipped = bodies = 0
    for kw in keywords:
        kw = kw.strip()
        if not kw:
            continue
        n_kw = 0
        for art in search_site_index(sid, kw, headers=ua_headers,
                                     max_pages=max_pages, position=position):
            exists = conn.execute(
                "SELECT 1 FROM documents WHERE id = ? OR (url = ? AND url != '') LIMIT 1",
                (art["id"], art["url"]),
            ).fetchone()
            if exists:
                skipped += 1
                continue

            body_text = raw_html_path = ""
            if fetch_bodies and art["url"]:
                body_text, raw_html = fetch_document_body(art["url"], headers=ua_headers)
                if raw_html:
                    raw_html_path = save_raw_html(site_key, art["id"], raw_html)
                    bodies += 1
                time.sleep(REQUEST_DELAY)

            if store_gkmlpt_document(conn, site_key, art, body_text, raw_html_path):
                added += 1
                n_kw += 1
                if added % 25 == 0:
                    conn.commit()
        log.info(f"  '{kw}': +{n_kw} new")

    conn.commit()
    log.info(f"=== Search-backfill done: {site_cfg['name']} — {added} new "
             f"({bodies} bodies, {skipped} already had) ===")
    return {"added": added, "bodies": bodies, "skipped": skipped}


# --- Content Extraction ---

def extract_body_text(html: str) -> str:
    """Extract the body text from a gkmlpt content page HTML.

    Uses the _CONFIG.DETAIL.content field (JSON-embedded HTML).
    """
    match = re.search(r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"', html)
    if match:
        content = match.group(1)
        content = content.replace("\\u003C", "<").replace("\\u003E", ">")
        content = content.replace("\\u0022", '"').replace("\\u0026", "&")
        content = content.replace('\\"', '"')
        content = content.replace("\\n", " ").replace("\\t", " ")

        def _unescape_unicode(m):
            try:
                return chr(int(m.group(1), 16))
            except ValueError:
                return m.group(0)

        content = re.sub(r"\\u([0-9a-fA-F]{4})", _unescape_unicode, content)
        text = re.sub(r"<[^>]+>", "", content)
        text = re.sub(r"\s+", " ", text).strip()
        text = text.replace("&nbsp;", " ").replace("&lt;", "<")
        text = text.replace("&gt;", ">").replace("&amp;", "&")
        if len(text) > 20:
            return text

    # Fallback: Nanshan /xxgk/ pages (NFCMS template)
    m = re.search(r'<div\s+class="tyxxy_main">(.*?)<div\s+class="tyxxy_fj">', html, re.DOTALL)
    if not m:
        m = re.search(r'<div\s+class="tyxxy_main">(.*?)</div>\s*</div>', html, re.DOTALL)
    if m:
        text = re.sub(r"<[^>]+>", "", m.group(1))
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > 20:
            return text

    # Fallback: Shenzhen gazette pages
    m = re.search(r'<div\s+class="news_cont_d_wrap">(.*?)</div>\s*</div>', html, re.DOTALL)
    if m:
        text = re.sub(r"<[^>]+>", "", m.group(1))
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > 20:
            return text

    return ""


def fetch_document_body(url: str, headers: dict = None) -> tuple[str, str]:
    """Fetch a document page and extract the body text.

    Returns (body_text, raw_html).
    """
    try:
        url = url.replace("https://", "http://")
        html = fetch(url, timeout=15, headers=headers)
        body = extract_body_text(html)
        return body, html
    except Exception as e:
        log.warning(f"  Failed to fetch {url}: {e}")
        return "", ""


# --- Storage ---

def store_categories(conn, site_key: str, tree: list, parent_id: int = 0):
    """Insert category records from the tree."""
    for node in tree:
        conn.execute(
            """INSERT OR IGNORE INTO categories (id, site_key, name, parent_id, post_count)
               VALUES (?, ?, ?, ?, ?)""",
            (node["id"], site_key, node["name"], parent_id, node.get("post_count", 0)),
        )
        if node.get("children"):
            store_categories(conn, site_key, node["children"], node["id"])
    conn.commit()


def store_gkmlpt_document(conn, site_key: str, article: dict, body_text: str, raw_html_path: str):
    """Insert or update a document record from gkmlpt API data."""
    try:
        conn.execute(
        """INSERT INTO documents (
            id, site_key, category_id, title, document_number, identifier,
            publisher, keywords, date_written, date_published, display_publish_time,
            abstract, body_text_cn, classify_main_name, classify_genre_name,
            classify_theme_name, url, post_url, is_expired, is_abolished,
            attachments_json, relation, raw_html_path, crawl_timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            body_text_cn=excluded.body_text_cn,
            raw_html_path=excluded.raw_html_path,
            crawl_timestamp=excluded.crawl_timestamp""",
        (
            article["id"],
            site_key,
            article.get("classify_main"),
            article["title"],
            article.get("document_number", ""),
            article.get("identifier", ""),
            article.get("publisher", ""),
            article.get("keywords", ""),
            article.get("date", 0),
            article.get("created_at", ""),
            article.get("display_publish_time", 0),
            article.get("abstract", ""),
            body_text,
            article.get("classify_main_name", ""),
            article.get("classify_genre_name", ""),
            article.get("classify_theme_name", ""),
            article.get("url", ""),
            article.get("post_url", ""),
            article.get("is_expired", 0),
            article.get("is_abolished", 0),
            json.dumps(article.get("attachment", []), ensure_ascii=False),
            article.get("relation", ""),
            raw_html_path,
            datetime.now(timezone.utc).isoformat(),
        ),
        )
        return True
    except sqlite3.IntegrityError:
        # Same article URL already stored under a different gkmlpt id
        # (cross-post / re-index across category feeds). We already have the
        # doc — skip rather than abort the whole multi-site sweep. Mirrors
        # base.store_document's designed "IntegrityError-skip on insert".
        # Return False so the caller skips _record_change too (its FK to
        # documents(id) would fail for a doc that was never inserted).
        return False


# --- Main Crawl Loop ---

def crawl_site(conn, site_key: str, site_cfg: dict, fetch_bodies: bool = True):
    """Crawl a single site: discover -> list -> extract -> store."""
    base_url = site_cfg["base_url"]
    ua_headers = {"User-Agent": BROWSER_UA} if site_key in SITES_NEEDING_BROWSER_UA else None
    log.info(f"=== Crawling {site_cfg['name']} ({base_url}) ===")

    try:
        sid, tree = discover_site(base_url, headers=ua_headers)
    except Exception as e:
        log.error(f"Failed to discover site {site_key}: {e}")
        return

    store_site(conn, site_key, site_cfg, sid, tree)
    store_categories(conn, site_key, tree)

    leaves = get_leaf_categories(tree)
    log.info(f"Found {len(leaves)} leaf categories")

    total_docs = 0
    total_bodies = 0
    for cat_id, cat_name in leaves:
        articles = crawl_category(base_url, sid, cat_id, cat_name, headers=ua_headers)
        time.sleep(REQUEST_DELAY)

        for article in articles:
            body_text = ""
            raw_html_path = ""

            existing = conn.execute(
                "SELECT body_text_cn FROM documents WHERE id = ?",
                (article["id"],),
            ).fetchone()
            if existing and existing[0]:
                store_gkmlpt_document(conn, site_key, article, existing[0], "")
                total_docs += 1
                continue

            if fetch_bodies and article.get("url"):
                ua_headers = {"User-Agent": BROWSER_UA} if site_key in SITES_NEEDING_BROWSER_UA else None
                body_text, raw_html = fetch_document_body(article["url"], headers=ua_headers)
                if raw_html:
                    raw_html_path = save_raw_html(site_key, article["id"], raw_html)
                    total_bodies += 1
                time.sleep(REQUEST_DELAY)

            store_gkmlpt_document(conn, site_key, article, body_text, raw_html_path)
            total_docs += 1

            if total_docs % 50 == 0:
                conn.commit()
                log.info(f"  Progress: {total_docs} docs stored, {total_bodies} bodies fetched")

    conn.commit()
    log.info(f"=== Done: {site_cfg['name']} — {total_docs} documents, {total_bodies} bodies ===")


def backfill_bodies(conn, site_key: str = None, policy_first: bool = False, delay: float = REQUEST_DELAY):
    """Fetch body text for documents that are missing it.

    Only processes gkmlpt-compatible URLs (content/post_ pages).
    Skips external URLs (WeChat, Xinhua, CCTV, etc.) and non-gkmlpt sites.
    """
    where = ("WHERE body_text_cn = '' AND url != '' "
             "AND site_key NOT IN ('ndrc', 'gov') "
             "AND url LIKE '%gkmlpt%'")
    params = ()
    if site_key:
        where += " AND site_key = ?"
        params = (site_key,)
    order = "ORDER BY (document_number != '') DESC, id" if policy_first else "ORDER BY id"

    rows = conn.execute(
        f"SELECT id, site_key, url FROM documents {where} {order}", params
    ).fetchall()

    log.info(f"Backfilling body text for {len(rows)} documents (delay={delay}s)")

    # Show per-site breakdown
    site_counts = {}
    for _, sk, _ in rows:
        site_counts[sk] = site_counts.get(sk, 0) + 1
    for sk, cnt in sorted(site_counts.items(), key=lambda x: -x[1]):
        log.info(f"  {sk}: {cnt} docs need body text")

    start_time = time.time()
    success = 0
    for i, (doc_id, sk, url) in enumerate(rows):
        ua_headers = {"User-Agent": BROWSER_UA} if sk in SITES_NEEDING_BROWSER_UA else None
        body_text, raw_html = fetch_document_body(url, headers=ua_headers)
        if body_text:
            # Sanitize surrogates that crash SQLite's UTF-8 codec
            body_text = body_text.encode("utf-8", errors="replace").decode("utf-8")
            raw_html_path = save_raw_html(sk, doc_id, raw_html) if raw_html else ""
            conn.execute(
                "UPDATE documents SET body_text_cn=?, raw_html_path=?, crawl_timestamp=? WHERE id=?",
                (body_text, raw_html_path, datetime.now(timezone.utc).isoformat(), doc_id),
            )
            success += 1
        if (i + 1) % 20 == 0:
            conn.commit()
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed
            remaining = (len(rows) - i - 1) / rate if rate > 0 else 0
            log.info(f"  Backfill: {i+1}/{len(rows)} ({success} ok) | "
                     f"{rate:.1f} docs/s | ETA: {remaining/60:.0f}m")
        time.sleep(delay)

    conn.commit()
    log.info(f"Backfill complete: {success}/{len(rows)} bodies fetched")


# --- Incremental Sync ---

# Fields to compare for change detection (API field name → DB column name)
SYNC_COMPARE_FIELDS = {
    "title": "title",
    "document_number": "document_number",
    "publisher": "publisher",
    "abstract": "abstract",
    "is_expired": "is_expired",
    "is_abolished": "is_abolished",
    "keywords": "keywords",
    "url": "url",
}


def _record_change(conn, doc_id: int, site_key: str, change_type: str,
                   field_name: str, old_value: str, new_value: str,
                   sync_run_id: str):
    """Record a single change in the document_changes table."""
    conn.execute(
        """INSERT INTO document_changes
           (document_id, site_key, change_type, field_name, old_value, new_value, detected_at, sync_run_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (doc_id, site_key, change_type, field_name,
         str(old_value) if old_value is not None else "",
         str(new_value) if new_value is not None else "",
         datetime.now(timezone.utc).isoformat(), sync_run_id),
    )


def sync_site(conn, site_key: str, site_cfg: dict):
    """Incremental sync: detect new, changed, and deleted documents.

    - NEW documents are inserted (with body text fetched).
    - CHANGED documents are recorded in document_changes; originals are NOT modified.
    - DELETED documents (in API but not in listing anymore) are recorded; NOT removed from DB.
    """
    base_url = site_cfg["base_url"]
    ua_headers = {"User-Agent": BROWSER_UA} if site_key in SITES_NEEDING_BROWSER_UA else None
    sync_run_id = f"{site_key}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    log.info(f"=== Sync {site_cfg['name']} ({base_url}) [run: {sync_run_id}] ===")

    # Step 1: Discover site structure (cheap)
    try:
        sid, tree = discover_site(base_url, headers=ua_headers)
    except Exception as e:
        log.error(f"Failed to discover site {site_key}: {e}")
        return

    store_site(conn, site_key, site_cfg, sid, tree)
    store_categories(conn, site_key, tree)

    # Step 2: Enumerate all listings from API (cheap — metadata only)
    leaves = get_leaf_categories(tree)
    log.info(f"Found {len(leaves)} leaf categories — fetching listings...")

    api_docs = {}  # id → article dict
    for cat_id, cat_name in leaves:
        articles = crawl_category(base_url, sid, cat_id, cat_name, headers=ua_headers)
        for article in articles:
            api_docs[article["id"]] = article
        time.sleep(REQUEST_DELAY)

    log.info(f"API returned {len(api_docs)} documents")

    # Step 3: Load all existing docs for this site from DB
    existing_rows = conn.execute(
        """SELECT id, title, document_number, publisher, abstract,
                  is_expired, is_abolished, keywords, url
           FROM documents WHERE site_key = ?""",
        (site_key,),
    ).fetchall()

    existing_docs = {}
    for row in existing_rows:
        existing_docs[row[0]] = {
            "title": row[1] or "",
            "document_number": row[2] or "",
            "publisher": row[3] or "",
            "abstract": row[4] or "",
            "is_expired": row[5] or 0,
            "is_abolished": row[6] or 0,
            "keywords": row[7] or "",
            "url": row[8] or "",
        }

    api_ids = set(api_docs.keys())
    db_ids = set(existing_docs.keys())

    new_ids = api_ids - db_ids
    deleted_ids = db_ids - api_ids
    common_ids = api_ids & db_ids

    log.info(f"Diff: {len(new_ids)} new, {len(deleted_ids)} deleted, {len(common_ids)} existing")

    # Step 4: Process NEW documents — insert with body text
    added = 0
    for doc_id in sorted(new_ids):
        article = api_docs[doc_id]
        body_text = ""
        raw_html_path = ""

        if article.get("url"):
            ua_headers = {"User-Agent": BROWSER_UA} if site_key in SITES_NEEDING_BROWSER_UA else None
            body_text, raw_html = fetch_document_body(article["url"], headers=ua_headers)
            if raw_html:
                raw_html_path = save_raw_html(site_key, article["id"], raw_html)
            time.sleep(REQUEST_DELAY)

        if store_gkmlpt_document(conn, site_key, article, body_text, raw_html_path):
            _record_change(conn, doc_id, site_key, "added", None, None, None, sync_run_id)
            added += 1

        if added % 20 == 0:
            conn.commit()
            log.info(f"  Added {added}/{len(new_ids)} new documents")

    if new_ids:
        conn.commit()
        log.info(f"  Added {added} new documents total")

    # Step 5: Detect CHANGES in existing documents
    changed_docs = 0
    total_field_changes = 0
    for doc_id in common_ids:
        article = api_docs[doc_id]
        db_doc = existing_docs[doc_id]
        doc_changes = []

        for api_field, db_field in SYNC_COMPARE_FIELDS.items():
            api_val = article.get(api_field, "")
            if api_val is None:
                api_val = ""
            db_val = db_doc.get(db_field, "")
            if db_val is None:
                db_val = ""

            # Normalize for comparison
            api_str = str(api_val).strip()
            db_str = str(db_val).strip()

            if api_str != db_str:
                doc_changes.append((db_field, db_str, api_str))

        if doc_changes:
            changed_docs += 1
            for field_name, old_val, new_val in doc_changes:
                _record_change(conn, doc_id, site_key, "modified",
                               field_name, old_val, new_val, sync_run_id)
                total_field_changes += 1

    if changed_docs:
        conn.commit()
        log.info(f"  {changed_docs} documents changed ({total_field_changes} field changes)")

    # Step 6: Record DELETED documents (not in API anymore)
    for doc_id in deleted_ids:
        db_doc = existing_docs[doc_id]
        _record_change(conn, doc_id, site_key, "deleted",
                       None, db_doc.get("title", ""), None, sync_run_id)

    if deleted_ids:
        conn.commit()
        log.info(f"  {len(deleted_ids)} documents no longer in API (marked as deleted)")

    # Summary
    log.info(f"=== Sync complete: {site_cfg['name']} ===")
    log.info(f"  Run ID: {sync_run_id}")
    log.info(f"  New: {added} | Changed: {changed_docs} | Deleted: {len(deleted_ids)} | Unchanged: {len(common_ids) - changed_docs}")

    return {
        "run_id": sync_run_id,
        "new": added,
        "changed": changed_docs,
        "deleted": len(deleted_ids),
        "unchanged": len(common_ids) - changed_docs,
    }


# --- CLI ---

def main():
    parser = argparse.ArgumentParser(description="gkmlpt Platform Crawler (Guangdong)")
    parser.add_argument("--site", help="Crawl only this site key (e.g., 'sz', 'gd')")
    parser.add_argument("--list-sites", action="store_true", help="List configured sites")
    parser.add_argument("--stats", action="store_true", help="Show database stats")
    parser.add_argument("--metadata-only", action="store_true",
                        help="Only fetch metadata from API, skip body text extraction")
    parser.add_argument("--backfill-bodies", action="store_true",
                        help="Fetch body text for documents that are missing it")
    parser.add_argument("--policy-first", action="store_true",
                        help="With --backfill-bodies, prioritize docs with 文号")
    parser.add_argument("--backfill-delay", type=float, default=0.5,
                        help="Delay between requests during backfill (default: 0.5s)")
    parser.add_argument("--sync", action="store_true",
                        help="Incremental sync: detect new/changed/deleted docs without overwriting")
    parser.add_argument("--show-changes", action="store_true",
                        help="Show recent document changes from sync runs")
    parser.add_argument("--search", metavar="KEYWORDS",
                        help="Historical backfill: comma-separated keywords to search via "
                             "search.gd.gov.cn (reaches docs older than the category window). "
                             "Requires --site. e.g. --search '行政听证,政府采购供应商信用'")
    parser.add_argument("--search-pages", type=int, default=10,
                        help="Max search result pages per keyword (default: 10, pagesize 20)")
    parser.add_argument("--search-title", action="store_true",
                        help="Restrict search matching to titles (position=title) instead of full text")
    parser.add_argument("--db", metavar="PATH",
                        help="Write to this SQLite file instead of the default documents.db "
                             "(use a THROWAWAY temp DB for testing — never the live corpus)")
    args = parser.parse_args()

    if args.list_sites:
        print("\nConfigured sites:\n")
        for key, cfg in SITES.items():
            print(f"  {key:10s} {cfg['name']:40s} {cfg['base_url']}")
        return

    from pathlib import Path
    conn = init_db(Path(args.db) if args.db else None)

    if args.stats:
        show_stats(conn)
        conn.close()
        return

    if args.show_changes:
        try:
            rows = conn.execute(
                """SELECT dc.sync_run_id, dc.change_type, COUNT(*) as cnt,
                          MIN(dc.detected_at) as first_detected
                   FROM document_changes dc
                   GROUP BY dc.sync_run_id, dc.change_type
                   ORDER BY first_detected DESC
                   LIMIT 50"""
            ).fetchall()
        except Exception:
            print("No document_changes table yet. Run --sync first.")
            conn.close()
            return

        if not rows:
            print("No changes recorded yet. Run --sync to detect changes.")
        else:
            print("\n=== Recent Sync Changes ===\n")
            current_run = None
            for run_id, change_type, cnt, detected_at in rows:
                if run_id != current_run:
                    if current_run is not None:
                        print()
                    print(f"Run: {run_id}  ({detected_at})")
                    current_run = run_id
                print(f"  {change_type:10s}: {cnt}")

            # Show most recent field-level changes
            field_rows = conn.execute(
                """SELECT dc.document_id, d.title, dc.field_name, dc.old_value, dc.new_value, dc.detected_at
                   FROM document_changes dc
                   LEFT JOIN documents d ON d.id = dc.document_id
                   WHERE dc.change_type = 'modified'
                   ORDER BY dc.detected_at DESC
                   LIMIT 20"""
            ).fetchall()
            if field_rows:
                print(f"\n--- Recent Field Changes ---\n")
                for doc_id, title, field, old_val, new_val, detected in field_rows:
                    title_short = (title or "")[:50]
                    old_short = (old_val or "")[:40]
                    new_short = (new_val or "")[:40]
                    print(f"  [{doc_id}] {title_short}")
                    print(f"    {field}: \"{old_short}\" → \"{new_short}\"")
        conn.close()
        return

    if args.backfill_bodies:
        backfill_bodies(conn, args.site, args.policy_first, delay=args.backfill_delay)
        show_stats(conn)
        conn.close()
        return

    if args.search:
        if not args.site or args.site not in SITES:
            print("--search requires a valid --site (e.g. --site sz). Use --list-sites.")
            conn.close()
            return
        keywords = [k for k in args.search.split(",") if k.strip()]
        fetch_bodies = not args.metadata_only
        position = "title" if args.search_title else ""
        search_backfill(conn, args.site, SITES[args.site], keywords,
                        max_pages=args.search_pages, position=position,
                        fetch_bodies=fetch_bodies)
        show_stats(conn)
        conn.close()
        return

    if args.sync:
        results = []
        if args.site:
            if args.site not in SITES:
                print(f"Unknown site: {args.site}. Use --list-sites to see options.")
                return
            result = sync_site(conn, args.site, SITES[args.site])
            if result:
                results.append(result)
        else:
            for sk, cfg in SITES.items():
                result = sync_site(conn, sk, cfg)
                if result:
                    results.append(result)

        # Print summary
        if results:
            total_new = sum(r["new"] for r in results)
            total_changed = sum(r["changed"] for r in results)
            total_deleted = sum(r["deleted"] for r in results)
            total_unchanged = sum(r["unchanged"] for r in results)
            print(f"\n=== Sync Summary ===")
            print(f"  Sites synced: {len(results)}")
            print(f"  New documents: {total_new}")
            print(f"  Changed documents: {total_changed}")
            print(f"  Deleted documents: {total_deleted}")
            print(f"  Unchanged: {total_unchanged}")

        show_stats(conn)
        conn.close()
        return

    fetch_bodies = not args.metadata_only

    if args.site:
        if args.site not in SITES:
            print(f"Unknown site: {args.site}. Use --list-sites to see options.")
            return
        crawl_site(conn, args.site, SITES[args.site], fetch_bodies)
    else:
        for site_key, site_cfg in SITES.items():
            crawl_site(conn, site_key, site_cfg, fetch_bodies)

    show_stats(conn)
    conn.close()


if __name__ == "__main__":
    main()
