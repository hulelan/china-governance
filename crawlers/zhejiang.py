"""
Zhejiang Province (浙江省) crawler — department subdomains.

The main provincial site (www.zj.gov.cn) is WAF-blocked from US IPs,
but department subdomains (fzggw.zj.gov.cn, kjt.zj.gov.cn, etc.) are
accessible.  All subdomains run JCMS with the same API gateway:

    /api-gateway/jpaas-publish-server/front/page/build/unit

Listing pages come in two flavours:
  1. Small sections: ALL items rendered in static HTML (no pagination div)
  2. Large sections: First page rendered in HTML, remaining pages served
     by the JCMS API.  However, from the US the API always returns page 1
     regardless of the pageNo parameter ("bulidstatic" pre-rendered mode).
     Full pagination requires a Chinese IP or the page.js client-side code
     which is blocked from overseas.

The crawler therefore grabs all items from the initial HTML page load and
the JCMS API page 1.  For sections with count > rows, only the first page
is captured (documented below as a known limitation).

URL patterns:
  Listing:  /col/col{COLUMN_ID}/index.html
  Detail:   /col/col{COL}/art/YYYY/art_{UUID}.html
            /art/YYYY/M/D/art_{COL}_{NUM}.html
  Body:     div#zoom (primary), div.content, div.TRS_Editor
  Meta:     <meta name="ArticleTitle|PubDate|ContentSource|Keywords">
            + xxgk table rows (索引号, 发布机构, 文件编号, 生成日期, etc.)

Departments crawled:
  fzggw  — 发展和改革委员会 (Development & Reform Commission)
  kjt    — 科学技术厅 (Science & Technology)
  jxt    — 教育厅 (Education)
  sft    — 司法厅 (Justice)
  sthjt  — 生态环境厅 (Ecology & Environment)
  czt    — 财政厅 (Finance)
  mzt    — 民政厅 (Civil Affairs)

Usage:
    python -m crawlers.zhejiang                        # Crawl all departments
    python -m crawlers.zhejiang --dept fzggw            # One department only
    python -m crawlers.zhejiang --dept kjt --section gfxwj  # One section
    python -m crawlers.zhejiang --stats                # Show database stats
    python -m crawlers.zhejiang --list-only             # List without bodies
    python -m crawlers.zhejiang --list-depts            # Show departments & sections
"""

import argparse
import json
import re
import time
from datetime import datetime, timedelta, timezone
from html import unescape
from urllib.parse import urljoin

from pathlib import Path

from crawlers.base import (
    REQUEST_DELAY,
    allow_ipv6,
    fetch,
    init_db,
    log,
    next_id,
    save_raw_html,
    show_stats,
    store_document,
    store_site,
)

# Zhejiang department subdomains are only reachable over IPv6 from the US.
# The default IPv4-only resolver in base.py must be bypassed for these hosts.
allow_ipv6("zj.gov.cn")

SITE_KEY = "zj"
SITE_CFG = {
    "name": "Zhejiang Province (Depts)",
    "base_url": "https://www.zj.gov.cn",
    "admin_level": "provincial",
}

CST = timezone(timedelta(hours=8))

# ---------------------------------------------------------------------------
# Department and section configuration
# ---------------------------------------------------------------------------
# Each department maps subdomain -> (display name, webId, {sections}).
# Each section maps key -> (display name, column_id, tagId, tplSetId).
#
# webId and tplSetId come from the pagination div attributes in the HTML:
#   queryData="{'webId':'3185','pageId':'...','tagId': '...', 'tplSetId': '...'}"
#
# tagId and tplSetId identify the template used to render the listing.
# They are needed for the JCMS API but can be empty for sections where
# all items are in the initial HTML (no pagination).
# ---------------------------------------------------------------------------

DEPARTMENTS = {
    "fzggw": {
        "name": "浙江省发展和改革委员会",
        "domain": "fzggw.zj.gov.cn",
        "web_id": "3185",
        "sections": {
            "gfxwj": ("行政规范性文件", "1229565788", "信息列表", "o0YcVHHq5vWtr3uiCp4SY"),
            "qtzcwj": ("本机关其他政策文件", "1599556", "信息列表", "o0YcVHHq5vWtr3uiCp4SY"),
            "spwj": ("审批文件", "1599553", "信息列表", "o0YcVHHq5vWtr3uiCp4SY"),
            "zcjd": ("政策解读", "1599554", "", ""),
            "szfgz": ("省政府规章", "1229562727", "", ""),
            "dfxfg": ("地方性法规", "1229562728", "", ""),
            "tzgg": ("通知公告", "1599544", "信息列表", "o0YcVHHq5vWtr3uiCp4SY"),
        },
    },
    "kjt": {
        "name": "浙江省科学技术厅",
        "domain": "kjt.zj.gov.cn",
        "web_id": "3387",
        "sections": {
            "gfxwj": ("行政规范性文件", "1229080140", "当前栏目list", "KhfdDWvs6oNSon8hfBpHF"),
            "sjwj": ("上级文件", "1229080136", "当前栏目list", "KhfdDWvs6oNSon8hfBpHF"),
            "szfgz": ("政府规章", "1229080135", "当前栏目list", "KhfdDWvs6oNSon8hfBpHF"),
            "qtwj": ("其他文件", "1229514320", "当前栏目list", "KhfdDWvs6oNSon8hfBpHF"),
            "zcjd": ("政策解读", "1229080168", "当前栏目list", "KhfdDWvs6oNSon8hfBpHF"),
            "tzgg": ("通知通告", "1229225203", "当前栏目list", "KhfdDWvs6oNSon8hfBpHF"),
        },
    },
    "jxt": {
        "name": "浙江省教育厅",
        "domain": "jxt.zj.gov.cn",
        "web_id": "",  # discovered at runtime from page
        "sections": {
            "gfxwj": ("行政规范性文件", "1229123402", "", ""),
            "sjwj": ("上级文件", "1229560971", "", ""),
            "zcjd": ("政策解读", "1229123409", "", ""),
            "wjtz": ("文件通知", "1229886900", "", ""),
        },
    },
    "sft": {
        "name": "浙江省司法厅",
        "domain": "sft.zj.gov.cn",
        "web_id": "",
        "sections": {
            "gfxwj": ("行政规范性文件", "1229107411", "", ""),
            "sjwj": ("上级文件", "1229557739", "", ""),
            "zcjd": ("政策解读", "1229107412", "", ""),
        },
    },
    "sthjt": {
        "name": "浙江省生态环境厅",
        "domain": "sthjt.zj.gov.cn",
        "web_id": "",
        "sections": {
            "zcwj": ("政策文件及解读", "1229263469", "", ""),
            "tzgg": ("通知公告", "1229263559", "", ""),
        },
    },
    "czt": {
        "name": "浙江省财政厅",
        "domain": "czt.zj.gov.cn",
        "web_id": "",
        "sections": {},  # sections discovered at runtime
    },
    "mzt": {
        "name": "浙江省民政厅",
        "domain": "mzt.zj.gov.cn",
        "web_id": "",
        "sections": {},  # sections discovered at runtime
    },
}


# ---------------------------------------------------------------------------
# Listing page parsing
# ---------------------------------------------------------------------------

def _listing_url(domain: str, column_id: str) -> str:
    """Build the listing page URL for a column."""
    return f"https://{domain}/col/col{column_id}/index.html"


def _parse_listing(html: str, base_url: str) -> list[dict]:
    """Parse a listing page and extract document links, titles, dates.

    Handles two HTML patterns used across Zhejiang department sites:

    Pattern A (fzggw-style — clearfix items):
      <li class="clearfix">
        <a class="bt-left" title="TITLE" href="URL" target="_blank">...</a>
        <span class="bt-right">YYYY-MM-DD</span>
      </li>

    Pattern B (kjt-style — simple items):
      <li>
        <a href="URL" title="TITLE" target="_blank">text</a>
        <span>YYYY-MM-DD</span>
      </li>
    """
    items = []

    # Pattern A: fzggw clearfix style
    for m in re.finditer(
        r'<li[^>]*class="clearfix"[^>]*>\s*<a[^>]*title="([^"]*)"[^>]*'
        r'href="([^"]*)"[^>]*>.*?<span[^>]*>(\d{4}-\d{2}-\d{2})</span>',
        html,
        re.DOTALL,
    ):
        title, href, date_str = m.group(1), m.group(2), m.group(3)
        doc_url = _resolve_url(base_url, href)
        items.append({
            "url": doc_url,
            "title": _clean_title(title),
            "date_str": date_str,
        })

    if items:
        return items

    # Pattern B: kjt simple li style
    for m in re.finditer(
        r'<li[^>]*>\s*<a\s+href="([^"]+)"[^>]*title="([^"]*)"[^>]*>'
        r'.*?</a>\s*<span[^>]*>(\d{4}-\d{2}-\d{2})</span>\s*</li>',
        html,
        re.DOTALL,
    ):
        href, title, date_str = m.group(1), m.group(2), m.group(3)
        doc_url = _resolve_url(base_url, href)
        items.append({
            "url": doc_url,
            "title": _clean_title(title),
            "date_str": date_str,
        })

    if items:
        return items

    # Pattern C: p.lb-list items (jxt/教育厅 style)
    #   <p class="lb-list"><a href="URL" title="TITLE" target="_blank">...</a>
    #       <span>YYYY-MM-DD</span></p>
    for m in re.finditer(
        r'<p[^>]*class="lb-list"[^>]*>\s*<a\s+href="([^"]+)"[^>]*'
        r'title="([^"]*)"[^>]*>.*?</a>\s*<span>(\d{4}-\d{2}-\d{2})</span>',
        html,
        re.DOTALL,
    ):
        href, title, date_str = m.group(1), m.group(2), m.group(3)
        doc_url = _resolve_url(base_url, href)
        items.append({
            "url": doc_url,
            "title": _clean_title(title),
            "date_str": date_str,
        })

    if items:
        return items

    # Pattern D: li with date in <b> tag (sft/司法厅 style)
    #   <li><a target="_blank" href="URL">TITLE</a><b>YYYY-MM-DD</b></li>
    for m in re.finditer(
        r'<li[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>\s*(.*?)\s*</a>\s*'
        r'<b>(\d{4}-\d{2}-\d{2})</b>',
        html,
        re.DOTALL,
    ):
        href, title_html, date_str = m.group(1), m.group(2), m.group(3)
        title = re.sub(r"<[^>]+>", "", title_html).strip()
        if not title:
            continue
        doc_url = _resolve_url(base_url, href.strip())
        items.append({
            "url": doc_url,
            "title": _clean_title(title),
            "date_str": date_str,
        })

    if items:
        return items

    # Pattern E: table rows (sthjt/生态环境厅 style)
    #   <table><tr><td><a href="URL" title="TITLE">...</a></td>
    #              <td>[YYYY-MM-DD]</td></tr></table>
    for m in re.finditer(
        r'<tr[^>]*>\s*<td[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*'
        r'title="([^"]*)"[^>]*>.*?</a>.*?</td>\s*'
        r'<td[^>]*>\s*\[?(\d{4}-\d{2}-\d{2})\]?\s*</td>',
        html,
        re.DOTALL,
    ):
        href, title, date_str = m.group(1), m.group(2), m.group(3)
        doc_url = _resolve_url(base_url, href)
        items.append({
            "url": doc_url,
            "title": _clean_title(title),
            "date_str": date_str,
        })

    if items:
        return items

    # Pattern F: generic li with title + date (last resort fallback)
    for m in re.finditer(
        r'<li[^>]*>.*?<a\s+href="([^"]+)"[^>]*title="([^"]*)"[^>]*>'
        r'.*?(\d{4}-\d{2}-\d{2}).*?</li>',
        html,
        re.DOTALL,
    ):
        href, title, date_str = m.group(1), m.group(2), m.group(3)
        doc_url = _resolve_url(base_url, href)
        items.append({
            "url": doc_url,
            "title": _clean_title(title),
            "date_str": date_str,
        })

    return items


def _resolve_url(base_url: str, href: str) -> str:
    """Resolve a potentially protocol-relative or relative URL.

    Zhejiang sites sometimes use protocol-relative URLs like
    //fzggw.zj.gov.cn/art/... which need https: prepended.
    """
    href = href.strip()
    if href.startswith("//"):
        return "https:" + href
    return urljoin(base_url, href)


def _clean_title(title: str) -> str:
    """Clean a document title: unescape entities, collapse whitespace."""
    title = unescape(title.strip())
    title = re.sub(r"\s+", " ", title)
    return title


def _get_pagination_info(html: str) -> dict:
    """Extract pagination metadata from the listing page HTML.

    Looks for the pagination div with attributes like:
      count="386" rows="15" pageNo="1" unitUrl="..."
      queryData="{'webId':'3185','pageId':'...','tagId':'...',...}"
    """
    info = {"count": 0, "rows": 0, "web_id": "", "tag_id": "", "tpl_set_id": ""}

    m = re.search(r'count="(\d+)"', html)
    if m:
        info["count"] = int(m.group(1))

    m = re.search(r'rows="(\d+)"', html)
    if m:
        info["rows"] = int(m.group(1))

    # Extract queryData fields
    m = re.search(r"'webId'\s*:\s*'(\d+)'", html)
    if m:
        info["web_id"] = m.group(1)

    m = re.search(r"'tagId'\s*:\s*'([^']*)'", html)
    if m:
        info["tag_id"] = m.group(1)

    m = re.search(r"'tplSetId'\s*:\s*'([^']*)'", html)
    if m:
        info["tpl_set_id"] = m.group(1)

    return info


def _fetch_api_page(domain: str, web_id: str, column_id: str,
                    tag_id: str, tpl_set_id: str, rows: int,
                    page_no: int) -> str:
    """Call the JCMS API and return the HTML fragment.

    NOTE: The 'bulidstatic' parseType means the server returns a
    pre-rendered page.  From the US, pageNo is ignored and page 1 is
    always returned.  This function is kept for completeness and will
    work correctly from a Chinese IP.
    """
    import urllib.parse

    params = {
        "webId": web_id,
        "pageId": column_id,
        "parseType": "bulidstatic",
        "pageType": "column",
        "tagId": tag_id,
        "tplSetId": tpl_set_id,
        "rows": str(rows),
        "pageNo": str(page_no),
    }
    url = (
        f"https://{domain}/api-gateway/jpaas-publish-server"
        f"/front/page/build/unit?{urllib.parse.urlencode(params)}"
    )
    raw = fetch(url)
    try:
        data = json.loads(raw, strict=False)
        if data.get("success") and "html" in data.get("data", {}):
            return data["data"]["html"]
    except (json.JSONDecodeError, KeyError):
        pass
    return ""


# ---------------------------------------------------------------------------
# Detail page extraction
# ---------------------------------------------------------------------------

def _parse_date(date_str: str) -> int:
    """Convert date string to Unix timestamp at midnight CST."""
    date_str = (
        date_str.replace("/", "-")
        .replace("年", "-")
        .replace("月", "-")
        .replace("日", "")
    )
    try:
        dt = datetime.strptime(date_str.strip(), "%Y-%m-%d").replace(tzinfo=CST)
        return int(dt.timestamp())
    except ValueError:
        return 0


def _extract_meta(html: str) -> dict:
    """Extract metadata from a detail page.

    Sources:
    1. <meta> tags (ArticleTitle, PubDate, ContentSource, Keywords)
    2. xxgk table rows (索引号, 发布机构, 文件编号, 生成日期, etc.)
    """
    meta = {}

    # Source 1: <meta> tags
    for name in ("ArticleTitle", "PubDate", "ContentSource",
                 "ColumnName", "Keywords"):
        m = re.search(
            rf'<meta\s+name="{name}"\s+content="([^"]*)"', html, re.IGNORECASE
        )
        if m:
            meta[name] = m.group(1).strip()

    # Source 2: xxgk table rows
    # Format: <td>索引号：</td><td>value</td>
    # or:     <td>索引号</td><td>value</td>
    for m in re.finditer(
        r'<td[^>]*>\s*([^<]*(?:索引号|组配分类|发布机构|生成日期|'
        r'文件编号|统一编号|有效性|发文字号|发文机关|成文日期|'
        r'发布日期|主题分类|文号)[^<]*)\s*</td>\s*<td[^>]*>\s*(.*?)\s*</td>',
        html,
        re.DOTALL,
    ):
        label = m.group(1).strip().rstrip("：:")
        value = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if not value:
            continue
        if "索引号" in label:
            meta["identifier"] = value
        elif "组配分类" in label or "主题分类" in label:
            meta["classify_theme_name"] = value
        elif "发布机构" in label or "发文机关" in label:
            meta["publisher"] = value
        elif "生成日期" in label or "成文日期" in label:
            meta["date_written_str"] = value
        elif "发布日期" in label:
            meta["date_published_str"] = value
        elif "文件编号" in label or "发文字号" in label or "文号" in label:
            meta["document_number"] = value
        elif "统一编号" in label:
            meta["unified_number"] = value
        elif "有效性" in label:
            meta["validity"] = value

    return meta


def _extract_body(html: str) -> str:
    """Extract plain text body from a document detail page.

    Tries containers in order:
    1. div#zoom (primary — used by most Zhejiang department sites)
    2. div.content (alternate layout)
    3. div.art_con
    4. div.TRS_Editor (TRS CMS fallback)
    """
    content = ""

    # Try using str.find for the primary #zoom container first
    # (avoids regex compilation issues on some Python versions)
    for start_marker, end_markers in [
        ('id="zoom"', ['</div>\n', '</div>\r', '</div> ']),
        ("id='zoom'", ['</div>\n', '</div>\r', '</div> ']),
    ]:
        idx = html.find(start_marker)
        if idx == -1:
            continue
        # Find the > that closes the opening tag
        gt = html.find(">", idx)
        if gt == -1:
            continue
        # Content starts after >
        start = gt + 1
        # Find the closing </div>
        end = len(html)
        for em in end_markers:
            pos = html.find(em, start)
            if pos != -1 and pos < end:
                end = pos
        # Also try a plain </div>
        pos = html.find("</div>", start)
        if pos != -1 and pos < end:
            end = pos
        content = html[start:end]
        break

    if not content:
        # Regex fallback for other containers
        for pattern in [
            r'<div[^>]*id=["\']zoom["\'][^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*\barticle-conter\b[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*\bcontent\b[^"]*"[^>]*>(.*?)</div>\s*(?:<div[^>]*class="[^"]*page|</div>)',
            r'<div[^>]*class="[^"]*\bart_con\b[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*\bTRS_Editor\b[^"]*"[^>]*>(.*?)</div>',
        ]:
            m = re.search(pattern, html, re.DOTALL)
            if m:
                content = m.group(1)
                break

    if not content:
        return ""

    # Convert HTML to plain text
    content = re.sub(r"<br\s*/?\s*>", "\n", content)
    content = re.sub(r"</p>", "\n", content)
    text = re.sub(r"<[^>]+>", "", content)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n", "\n", text)
    text = text.strip()
    text = unescape(text)
    text = text.replace("\xa0", " ")

    if len(text) > 20:
        return text
    return ""


def _extract_doc_number(title: str) -> str:
    """Extract document number from title parentheses if present."""
    m = re.search(r"[（(]([^）)]*[〕][^）)]*号)[）)]", title)
    if m:
        return m.group(1)
    return ""


# ---------------------------------------------------------------------------
# Crawl logic
# ---------------------------------------------------------------------------

def crawl_section(
    conn,
    dept_key: str,
    dept_cfg: dict,
    section_key: str,
    section_name: str,
    column_id: str,
    tag_id: str,
    tpl_set_id: str,
    fetch_bodies: bool = True,
):
    """Crawl a single section of a department site."""
    domain = dept_cfg["domain"]
    dept_name = dept_cfg["name"]
    log.info(f"--- {dept_name} / {section_name} ({dept_key}/{section_key}) ---")

    listing_url = _listing_url(domain, column_id)
    try:
        html = fetch(listing_url)
    except Exception as e:
        log.error(f"Failed to fetch {listing_url}: {e}")
        return 0

    # Parse items from initial HTML
    all_items = _parse_listing(html, listing_url)

    # Check pagination
    pag = _get_pagination_info(html)
    if pag["count"] > 0 and pag["rows"] > 0:
        total_pages = (pag["count"] + pag["rows"] - 1) // pag["rows"]
        log.info(
            f"  Pagination: {pag['count']} total, {pag['rows']}/page, "
            f"{total_pages} pages"
        )
        if total_pages > 1:
            log.info(
                f"  NOTE: Only page 1 accessible from US "
                f"({pag['count'] - len(all_items)} docs on later pages "
                f"need Chinese IP)"
            )
            # Try fetching additional pages via API (will work from Chinese IP)
            api_web_id = pag.get("web_id") or dept_cfg.get("web_id", "")
            api_tag_id = pag.get("tag_id") or tag_id
            api_tpl_id = pag.get("tpl_set_id") or tpl_set_id

            if api_web_id and api_tag_id and api_tpl_id:
                existing_urls = {item["url"] for item in all_items}
                for page_no in range(2, total_pages + 1):
                    try:
                        api_html = _fetch_api_page(
                            domain, api_web_id, column_id,
                            api_tag_id, api_tpl_id,
                            pag["rows"], page_no,
                        )
                        if api_html:
                            page_items = _parse_listing(api_html, listing_url)
                            new_items = [
                                i for i in page_items
                                if i["url"] not in existing_urls
                            ]
                            if not new_items:
                                # API returned same page — stop
                                log.info(
                                    f"  API returned duplicate page at "
                                    f"pageNo={page_no}, stopping pagination"
                                )
                                break
                            all_items.extend(new_items)
                            existing_urls.update(i["url"] for i in new_items)
                    except Exception as e:
                        log.warning(f"  API page {page_no} failed: {e}")
                        break
                    time.sleep(REQUEST_DELAY)
    else:
        log.info(f"  No pagination — all items in HTML")

    log.info(f"  Found {len(all_items)} document links")

    stored = 0
    bodies = 0
    for item in all_items:
        doc_url = item["url"]

        # Skip if already stored with body text
        existing = conn.execute(
            "SELECT id, body_text_cn FROM documents WHERE url = ?", (doc_url,)
        ).fetchone()
        if existing and existing[1]:
            stored += 1
            continue

        doc_id = existing[0] if existing else next_id(conn)

        body_text = ""
        raw_html_path = ""
        doc_number = _extract_doc_number(item["title"])
        publisher = dept_name
        date_published = item["date_str"]
        date_written = _parse_date(item["date_str"])
        identifier = ""
        classify_theme = ""

        if fetch_bodies:
            try:
                doc_html = fetch(doc_url)
                meta = _extract_meta(doc_html)
                body_text = _extract_body(doc_html)

                # Merge metadata
                publisher = meta.get("publisher", meta.get("ContentSource", dept_name))
                doc_number = (
                    meta.get("document_number", "")
                    or doc_number
                    or _extract_doc_number(meta.get("ArticleTitle", ""))
                )
                identifier = meta.get("identifier", "")
                classify_theme = meta.get("classify_theme_name", "")

                if meta.get("date_written_str"):
                    date_written = _parse_date(meta["date_written_str"])
                if meta.get("PubDate"):
                    # PubDate often includes time: "2026-03-13 10:21"
                    date_published = meta["PubDate"].split()[0]
                if meta.get("date_published_str"):
                    date_published = meta["date_published_str"]

                if doc_html:
                    raw_html_path = save_raw_html(SITE_KEY, doc_id, doc_html)
                    bodies += 1
            except Exception as e:
                log.warning(f"  Failed to fetch {doc_url}: {e}")
            time.sleep(REQUEST_DELAY)

        store_document(conn, SITE_KEY, {
            "id": doc_id,
            "title": item["title"],
            "document_number": doc_number,
            "identifier": identifier,
            "publisher": publisher,
            "date_written": date_written,
            "date_published": date_published,
            "body_text_cn": body_text,
            "url": doc_url,
            "classify_main_name": f"{dept_name} / {section_name}",
            "classify_theme_name": classify_theme,
            "raw_html_path": raw_html_path,
        })
        stored += 1

        if stored % 20 == 0:
            conn.commit()
            log.info(f"  Progress: {stored}/{len(all_items)} stored, {bodies} bodies")

    conn.commit()
    log.info(f"  Done: {stored} documents stored, {bodies} bodies fetched")
    return stored


def crawl_department(
    conn,
    dept_key: str,
    section_filter: str = None,
    fetch_bodies: bool = True,
):
    """Crawl all (or one) section of a department."""
    dept_cfg = DEPARTMENTS[dept_key]
    if not dept_cfg["sections"]:
        log.warning(f"No sections configured for {dept_key} — skipping")
        return 0

    total = 0
    for sec_key, (sec_name, col_id, tag_id, tpl_set_id) in dept_cfg["sections"].items():
        if section_filter and sec_key != section_filter:
            continue
        total += crawl_section(
            conn, dept_key, dept_cfg,
            sec_key, sec_name, col_id, tag_id, tpl_set_id,
            fetch_bodies=fetch_bodies,
        )
        time.sleep(REQUEST_DELAY)

    return total


def crawl_all(
    conn,
    dept_filter: str = None,
    section_filter: str = None,
    fetch_bodies: bool = True,
):
    """Crawl all departments (or a filtered subset)."""
    store_site(conn, SITE_KEY, SITE_CFG)
    total = 0

    depts = [dept_filter] if dept_filter else list(DEPARTMENTS.keys())
    for dept_key in depts:
        if dept_key not in DEPARTMENTS:
            log.error(f"Unknown department: {dept_key}")
            continue
        dept = DEPARTMENTS[dept_key]
        if not dept["sections"]:
            log.info(f"Skipping {dept_key} ({dept['name']}) — no sections configured")
            continue
        log.info(f"=== Department: {dept['name']} ({dept_key}) ===")
        total += crawl_department(conn, dept_key, section_filter, fetch_bodies)
        time.sleep(REQUEST_DELAY)

    log.info(f"=== Zhejiang total: {total} documents ===")


def list_departments():
    """Print all configured departments and their sections."""
    print("\nZhejiang Province — Department Crawler Configuration\n")
    for dept_key, dept in DEPARTMENTS.items():
        print(f"  {dept_key:8s}  {dept['name']}  ({dept['domain']})")
        if dept["sections"]:
            for sec_key, (sec_name, col_id, _, _) in dept["sections"].items():
                print(f"            {sec_key:8s}  {sec_name}  (col{col_id})")
        else:
            print(f"            (no sections configured)")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Zhejiang Province Department Crawler"
    )
    parser.add_argument(
        "--dept",
        choices=list(DEPARTMENTS.keys()),
        help="Crawl only this department",
    )
    parser.add_argument(
        "--section",
        type=str,
        help="Crawl only this section (requires --dept)",
    )
    parser.add_argument("--stats", action="store_true", help="Show database stats")
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="List document URLs without fetching bodies",
    )
    parser.add_argument(
        "--list-depts",
        action="store_true",
        help="Show all departments and sections",
    )
    parser.add_argument(
        "--db", type=str, help="Path to SQLite database (default: documents.db)",
    )
    args = parser.parse_args()

    if args.list_depts:
        list_departments()
        return

    conn = init_db(Path(args.db) if args.db else None)

    if args.stats:
        show_stats(conn)
        conn.close()
        return

    if args.section and not args.dept:
        parser.error("--section requires --dept")

    crawl_all(
        conn,
        dept_filter=args.dept,
        section_filter=args.section,
        fetch_bodies=not args.list_only,
    )
    show_stats(conn)
    conn.close()


if __name__ == "__main__":
    main()
