"""
Ministry of Finance (财政部) crawler.

Crawls policy documents from www.mof.gov.cn. The site uses static HTML with
createPageHTML() pagination (same pattern as NDRC).

Two content types:
  - HTML articles: policy releases, news, regulation texts
  - PDF bulletins (财政文告): monthly compendiums of formal regulations

Usage:
    python -m crawlers.mof                    # Crawl all sections
    python -m crawlers.mof --section zcfb     # Crawl only policy releases
    python -m crawlers.mof --stats            # Show database stats
    python -m crawlers.mof --list-only        # List URLs without fetching
"""

import argparse
import io
import re
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin

from crawlers.base import (
    REQUEST_DELAY,
    fetch,
    init_db,
    log,
    next_id,
    save_raw_html,
    show_stats,
    store_document,
    store_site,
    USER_AGENT,
)

SITE_KEY = "mof"
SITE_CFG = {
    "name": "Ministry of Finance",
    "base_url": "https://www.mof.gov.cn",
    "admin_level": "central",
}

CST = timezone(timedelta(hours=8))

# Sections to crawl.  (path_segment, label, content_type)
SECTIONS = {
    "zcfb": {
        "name": "政策发布",
        "path": "/zhengwuxinxi/zhengcefabu/",
        "type": "html",
    },
    "czxw": {
        "name": "财政新闻",
        "path": "/zhengwuxinxi/caizhengxinwen/",
        "type": "html",
    },
    "czwg": {
        "name": "财政文告",
        "path": "/gkml/caizhengwengao/",
        # Historical archive walker (see crawl_wengao_archive). The 财政部文告
        # (gazette) is MOF's permanent, static-HTML back-catalog: year dirs
        # (2000→now) → monthly issues → INDIVIDUAL per-document .htm pages.
        # This is the only reachable route to pre-2021 MOF docs — the rolling
        # zcfb/czxw listings only keep ~20 pages (floor ~2021-11) and the
        # search.mof.gov.cn WAS backend 502s from datacenter IPs.
        "type": "wengao",
    },
}

WENGAO_PATH = "/gkml/caizhengwengao/"


def _parse_date(date_str: str) -> int:
    """Convert date string to Unix timestamp at midnight CST."""
    date_str = (
        date_str.replace("/", "-")
        .replace("年", "-")
        .replace("月", "-")
        .replace("日", "")
        .strip()
    )
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=CST)
        return int(dt.timestamp())
    except ValueError:
        return 0


# --- HTML listing/detail helpers ---

def _listing_url(base_path: str, page: int) -> str:
    """Build listing page URL."""
    base = f"https://www.mof.gov.cn{base_path}"
    if page == 0:
        return base + "index.htm"
    return base + f"index_{page}.htm"


def _get_total_pages(html: str) -> int:
    """Extract total page count from createPageHTML(N, ...) or var countPage."""
    m = re.search(r"createPageHTML\((\d+),", html)
    if m:
        return int(m.group(1))
    m = re.search(r"var\s+countPage\s*=\s*(\d+)", html)
    if m:
        return int(m.group(1))
    return 1


def _parse_listing(html: str, base_url: str) -> list[dict]:
    """Parse listing page: <li><a href="..." title='...'>Title</a><span>Date</span></li>."""
    items = []
    # MOF uses <span> for dates and sometimes single-quoted title attrs
    for m in re.finditer(
        r'<li>\s*<a\s+href="([^"]+)"[^>]*>(.*?)</a>\s*<span>(\d{4}-\d{2}-\d{2})</span>\s*</li>',
        html,
        re.DOTALL,
    ):
        href, title, date_str = m.group(1), m.group(2), m.group(3)
        title = re.sub(r"<[^>]+>", "", title).strip()
        doc_url = urljoin(base_url, href)
        items.append({"url": doc_url, "title": title, "date_str": date_str})
    # Fallback: bare date without <span> (used in some sections)
    if not items:
        for m in re.finditer(
            r'<li>\s*<a\s+href="([^"]+)"[^>]*>(.*?)</a>\s*(\d{4}-\d{2}-\d{2})\s*</li>',
            html,
            re.DOTALL,
        ):
            href, title, date_str = m.group(1), m.group(2), m.group(3)
            title = re.sub(r"<[^>]+>", "", title).strip()
            doc_url = urljoin(base_url, href)
            items.append({"url": doc_url, "title": title, "date_str": date_str})
    return items


def _extract_body(html: str) -> str:
    """Extract body text from div.my_conboxzw."""
    m = re.search(r'<div\s+class="my_conboxzw"[^>]*>(.*?)</div>\s*(?:<div|<script)',
                  html, re.DOTALL)
    if not m:
        # Broader fallback
        m = re.search(r'<div\s+class="my_conboxzw"[^>]*>(.*?)</div>', html, re.DOTALL)
    if not m:
        return ""
    content = m.group(1)
    content = re.sub(r"<br\s*/?\s*>", "\n", content)
    content = re.sub(r"<p[^>]*>", "\n", content)
    content = re.sub(r"</p>", "", content)
    text = re.sub(r"<[^>]+>", "", content)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n", "\n", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .strip()
    )
    return text if len(text) > 20 else ""


def _extract_doc_number(title: str) -> str:
    """Extract 文号 from title if present."""
    m = re.search(r"[（(]([^）)]*[〕\]][^）)]*号)[）)]", title)
    if m:
        return m.group(1)
    return ""


def _extract_doc_number_from_body(body_text: str) -> str:
    """Extract a MOF 文号 (财库/财预/财税〔YYYY〕N号 …) from the body head.

    Gazette article titles rarely embed the 文号 — it sits in the first lines of
    the body — so this backfills document_number for formal-citation resolution.
    """
    head = body_text[:800]
    m = re.search(
        r"(财[一-鿿]{0,3}[〔\[（(]\s*(?:19|20)\d{2}\s*[〕\]）)]\s*\d+\s*号)",
        head,
    )
    if m:
        return re.sub(r"\s+", "", m.group(1))
    return ""


def _extract_meta(html: str) -> dict:
    """Extract metadata from <meta> tags or page content."""
    meta = {}
    for name in ("ArticleTitle", "PubDate", "ContentSource", "Keywords",
                 "ColumnName", "description"):
        m = re.search(
            rf'<meta\s+name=["\']?{name}["\']?\s+content=["\']([^"\']*)["\']',
            html, re.IGNORECASE,
        )
        if m:
            meta[name] = m.group(1).strip()
    return meta


# --- PDF helpers ---

def _fetch_pdf_bytes(url: str) -> bytes:
    """Download a PDF and return raw bytes."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    resp = urllib.request.urlopen(req, timeout=30)
    return resp.read()


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from PDF using PyMuPDF (fitz)."""
    try:
        import fitz
    except ImportError:
        log.warning("PyMuPDF not installed — skipping PDF text extraction")
        return ""

    text_parts = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            text_parts.append(page.get_text())
    text = "\n".join(text_parts)
    # Clean up
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# --- Crawl logic ---

def crawl_html_section(conn, section_key: str, section: dict, fetch_bodies: bool = True):
    """Crawl an HTML listing section."""
    name = section["name"]
    path = section["path"]
    log.info(f"--- Section: {name} ({section_key}) ---")

    first_url = _listing_url(path, 0)
    try:
        html = fetch(first_url)
    except Exception as e:
        log.error(f"Failed to fetch {first_url}: {e}")
        return 0

    total_pages = _get_total_pages(html)
    log.info(f"  {total_pages} listing pages")

    all_items = _parse_listing(html, first_url)

    for page in range(1, total_pages):
        page_url = _listing_url(path, page)
        try:
            page_html = fetch(page_url)
            all_items.extend(_parse_listing(page_html, page_url))
        except Exception as e:
            log.warning(f"  Failed page {page}: {e}")
        time.sleep(REQUEST_DELAY)

    log.info(f"  Found {len(all_items)} document links")

    stored = 0
    bodies = 0
    for item in all_items:
        doc_url = item["url"]
        existing = conn.execute(
            "SELECT id, body_text_cn FROM documents WHERE url = ? AND url != ''", (doc_url,)
        ).fetchone()
        if existing and existing[1]:
            stored += 1
            continue

        doc_id = existing[0] if existing else next_id(conn)
        body_text = ""
        raw_html_path = ""
        doc_number = _extract_doc_number(item["title"])
        publisher = "财政部"
        date_published = item["date_str"]

        if fetch_bodies:
            try:
                doc_html = fetch(doc_url)
                meta = _extract_meta(doc_html)
                body_text = _extract_body(doc_html)
                publisher = meta.get("ContentSource", publisher)
                doc_number = doc_number or _extract_doc_number(
                    meta.get("ArticleTitle", "")
                )
                if meta.get("PubDate"):
                    date_published = meta["PubDate"]
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
            "publisher": publisher,
            "date_written": _parse_date(date_published),
            "date_published": date_published,
            "body_text_cn": body_text,
            "url": doc_url,
            "classify_main_name": name,
            "raw_html_path": raw_html_path,
        })
        stored += 1

        if stored % 20 == 0:
            conn.commit()
            log.info(f"  Progress: {stored}/{len(all_items)} stored, {bodies} bodies")

    conn.commit()
    log.info(f"  Done: {stored} documents stored, {bodies} bodies fetched")
    return stored


def crawl_pdf_section(conn, section_key: str, section: dict, fetch_bodies: bool = True):
    """Crawl a PDF bulletin section — each PDF is stored as one document."""
    name = section["name"]
    path = section["path"]
    log.info(f"--- Section: {name} ({section_key}, PDF) ---")

    first_url = _listing_url(path, 0)
    try:
        html = fetch(first_url)
    except Exception as e:
        log.error(f"Failed to fetch {first_url}: {e}")
        return 0

    total_pages = _get_total_pages(html)
    log.info(f"  {total_pages} listing pages")

    # PDF listings use slightly different HTML — links go to .pdf files
    all_items = []
    for m in re.finditer(
        r'<li>\s*<a\s+href="([^"]+\.pdf)"[^>]*>(.*?)</a>\s*(\d{4}-\d{2}-\d{2})\s*</li>',
        html,
        re.DOTALL,
    ):
        href, title, date_str = m.group(1), m.group(2), m.group(3)
        title = re.sub(r"<[^>]+>", "", title).strip()
        all_items.append({
            "url": urljoin(first_url, href),
            "title": title,
            "date_str": date_str,
        })

    for page in range(1, total_pages):
        page_url = _listing_url(path, page)
        try:
            page_html = fetch(page_url)
            for m in re.finditer(
                r'<li>\s*<a\s+href="([^"]+\.pdf)"[^>]*>(.*?)</a>\s*(\d{4}-\d{2}-\d{2})\s*</li>',
                page_html,
                re.DOTALL,
            ):
                href, title, date_str = m.group(1), m.group(2), m.group(3)
                title = re.sub(r"<[^>]+>", "", title).strip()
                all_items.append({
                    "url": urljoin(page_url, href),
                    "title": title,
                    "date_str": date_str,
                })
        except Exception as e:
            log.warning(f"  Failed page {page}: {e}")
        time.sleep(REQUEST_DELAY)

    log.info(f"  Found {len(all_items)} PDF links")

    stored = 0
    for item in all_items:
        doc_url = item["url"]
        existing = conn.execute(
            "SELECT id, body_text_cn FROM documents WHERE url = ? AND url != ''", (doc_url,)
        ).fetchone()
        if existing and existing[1]:
            stored += 1
            continue

        doc_id = existing[0] if existing else next_id(conn)
        body_text = ""

        if fetch_bodies:
            try:
                log.info(f"  Downloading PDF: {item['title']}")
                pdf_bytes = _fetch_pdf_bytes(doc_url)
                body_text = _extract_pdf_text(pdf_bytes)
                if body_text:
                    log.info(f"    Extracted {len(body_text)} chars from PDF")
                else:
                    log.warning(f"    No text extracted from PDF")
            except Exception as e:
                log.warning(f"  Failed to fetch PDF {doc_url}: {e}")
            time.sleep(REQUEST_DELAY)

        store_document(conn, SITE_KEY, {
            "id": doc_id,
            "title": item["title"],
            "document_number": "",
            "publisher": "财政部",
            "date_written": _parse_date(item["date_str"]),
            "date_published": item["date_str"],
            "body_text_cn": body_text,
            "url": doc_url,
            "classify_main_name": name,
        })
        stored += 1

        if stored % 10 == 0:
            conn.commit()
            log.info(f"  Progress: {stored}/{len(all_items)}")

    conn.commit()
    log.info(f"  Done: {stored} PDF documents stored")
    return stored


# --- 财政部文告 (gazette) historical archive walker ---

def _wengao_year_dirs(index_html: str) -> list[str]:
    """From the flat gazette index, return year-directory segment names.

    Naming is inconsistent across eras (caizhengbuwengao2004, 2009niancaizheng-
    buwengao, 2010nianwengao, 2011caizhengwengao, 2012wg, wg2013, 2017wg,
    wg201901, 202001wg, wg2021 …) so we keep any `./<seg>/` link whose segment
    carries a 4-digit year and isn't a file.
    """
    dirs = []
    for seg in re.findall(r'href="\./([^"/.]+)/"', index_html):
        if re.search(r"(?:19|20)\d{2}", seg):
            dirs.append(seg)
    # de-dup, preserve order
    seen = set()
    out = []
    for d in dirs:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def _issue_urls_for_year(year_index_url: str) -> list[str]:
    """Resolve a year dir to the full set of its issue-page URLs.

    The year index JS-redirects (location.replace) to its latest issue; that
    issue page carries a sibling-issue nav (../wgYYYYNN/) listing every issue of
    the year. We collect the redirect target + all siblings.
    """
    try:
        html = fetch(year_index_url)
    except Exception as e:
        log.warning(f"  Failed year index {year_index_url}: {e}")
        return []

    m = re.search(r'location\.replace\(["\']([^"\']+)["\']', html)
    if m:
        latest_url = urljoin(year_index_url, m.group(1))
    else:
        # No redirect — the year index may itself be the issue listing.
        latest_url = year_index_url

    try:
        issue_html = fetch(latest_url)
    except Exception as e:
        log.warning(f"  Failed latest issue {latest_url}: {e}")
        return [latest_url]

    urls = {latest_url.rstrip("/") + "/"}
    for href in re.findall(r'href="(\.\.?/[^"]+/)"[^>]*id=', issue_html):
        sib = urljoin(latest_url, href)
        # Keep only sibling issue dirs (…/wgYYYYNN/ or …/caizhengbuwengaoYYYYNN/)
        if re.search(r"(?:19|20)\d{2}\d{2}/$", sib) or re.search(r"wengao\d{6}/$", sib):
            urls.add(sib)
    return sorted(urls)


def _issue_doc_links(issue_url: str, issue_html: str) -> list[dict]:
    """Extract individual-document links from one gazette issue page.

    Modern issues sometimes carry only a single compendium PDF; those are
    skipped here (no per-doc granularity) — the HTML-per-document issues (the
    vast majority, incl. all of 2000-2023) are what we want.
    """
    items = []
    for m in re.finditer(
        r'href="(\.{1,2}/[^"]*t\d{8}_\d+\.html?)"[^>]*(?:title=[\'"]([^\'"]*)[\'"])?[^>]*>([^<]*)</a>',
        issue_html,
    ):
        href, title_attr, title_txt = m.group(1), m.group(2), m.group(3)
        title = (title_attr or title_txt or "").strip()
        if not title:
            continue
        items.append({"url": urljoin(issue_url, href), "title": title})
    return items


def crawl_wengao_archive(conn, section: dict, fetch_bodies: bool = True,
                         max_docs: int = 0):
    """Walk the 财政部文告 historical archive: year → issue → per-document .htm.

    This backfills pre-2021 MOF documents (heavily cited 财库/财预/财税/财会/财建 …
    通知) that the rolling zcfb/czxw listings no longer surface.
    """
    name = section["name"]
    log.info(f"--- Section: {name} (czwg, gazette archive) ---")

    index_url = urljoin(SITE_CFG["base_url"], WENGAO_PATH) + "index.htm"
    try:
        index_html = fetch(index_url)
    except Exception as e:
        log.error(f"Failed to fetch gazette index {index_url}: {e}")
        return 0

    year_dirs = _wengao_year_dirs(index_html)
    log.info(f"  {len(year_dirs)} year directories: {', '.join(year_dirs)}")

    # Collect all issue URLs across all years (newest years first).
    issue_urls = []
    for seg in year_dirs:
        year_index = urljoin(index_url, f"./{seg}/") + "index.htm"
        issues = _issue_urls_for_year(year_index)
        issue_urls.extend(issues)
        time.sleep(REQUEST_DELAY)
    log.info(f"  {len(issue_urls)} gazette issues discovered")

    # Gather per-document links from every issue.
    all_items = []
    seen_urls = set()
    for issue_url in issue_urls:
        if max_docs and len(all_items) >= max_docs:
            break
        try:
            issue_html = fetch(issue_url)
        except Exception as e:
            log.warning(f"  Failed issue {issue_url}: {e}")
            continue
        for item in _issue_doc_links(issue_url, issue_html):
            if item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])
            all_items.append(item)
        time.sleep(REQUEST_DELAY)

    if max_docs:
        all_items = all_items[:max_docs]
    log.info(f"  Found {len(all_items)} archive document links")

    stored = 0
    bodies = 0
    skipped = 0
    for item in all_items:
        doc_url = item["url"]
        existing = conn.execute(
            "SELECT id, body_text_cn FROM documents WHERE url = ? AND url != ''",
            (doc_url,),
        ).fetchone()
        if existing and existing[1]:
            skipped += 1
            continue

        doc_id = existing[0] if existing else next_id(conn)
        body_text = ""
        raw_html_path = ""
        doc_number = _extract_doc_number(item["title"])
        publisher = "财政部"
        date_published = ""

        if fetch_bodies:
            try:
                doc_html = fetch(doc_url)
                meta = _extract_meta(doc_html)
                body_text = _extract_body(doc_html)
                doc_number = (
                    doc_number
                    or _extract_doc_number(meta.get("ArticleTitle", ""))
                    or _extract_doc_number_from_body(body_text)
                )
                if meta.get("PubDate"):
                    date_published = meta["PubDate"][:10]
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
            "publisher": publisher,
            "date_written": _parse_date(date_published),
            "date_published": date_published,
            "body_text_cn": body_text,
            "url": doc_url,
            "classify_main_name": name,
            "raw_html_path": raw_html_path,
        })
        stored += 1

        if stored % 20 == 0:
            conn.commit()
            log.info(f"  Progress: {stored}/{len(all_items)} stored, "
                     f"{bodies} bodies, {skipped} skipped")

    conn.commit()
    log.info(f"  Done: {stored} stored, {bodies} bodies, {skipped} already existed")
    return stored


def crawl_all(conn, sections: dict = None, fetch_bodies: bool = True,
              max_docs: int = 0):
    """Crawl all (or specified) MOF sections."""
    if sections is None:
        sections = SECTIONS

    store_site(conn, SITE_KEY, SITE_CFG)
    total = 0
    for key, section in sections.items():
        if section["type"] == "wengao":
            total += crawl_wengao_archive(conn, section, fetch_bodies, max_docs)
        elif section["type"] == "pdf":
            total += crawl_pdf_section(conn, key, section, fetch_bodies)
        else:
            total += crawl_html_section(conn, key, section, fetch_bodies)
        time.sleep(REQUEST_DELAY)

    log.info(f"=== MOF total: {total} documents ===")


def main():
    parser = argparse.ArgumentParser(description="MOF Policy Crawler")
    parser.add_argument("--section", choices=list(SECTIONS.keys()),
                        help="Crawl only this section")
    parser.add_argument("--stats", action="store_true", help="Show database stats")
    parser.add_argument("--list-only", action="store_true",
                        help="List URLs without fetching bodies")
    parser.add_argument("--db", type=str,
                        help="Path to SQLite database (default: documents.db)")
    parser.add_argument("--max-docs", type=int, default=0,
                        help="Cap docs fetched from the czwg gazette archive "
                             "(0=all; for bounded validation runs)")
    args = parser.parse_args()

    conn = init_db(Path(args.db) if args.db else None)

    if args.stats:
        show_stats(conn)
        conn.close()
        return

    sections = {args.section: SECTIONS[args.section]} if args.section else None
    crawl_all(conn, sections, fetch_bodies=not args.list_only,
              max_docs=args.max_docs)
    show_stats(conn)
    conn.close()


if __name__ == "__main__":
    main()
