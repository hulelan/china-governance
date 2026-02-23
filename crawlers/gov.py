"""
State Council (国务院) crawler.

Crawls policy documents from www.gov.cn. Uses the static JSON feed at
/zhengce/zuixin/ZUIXINZHENGCE.json as the primary listing source, then
fetches individual document pages for body text and structured metadata.

Two document templates exist:
  - Template A: /zhengce/content/YYYYMM/content_NNN.htm (formal State Council docs)
    Has structured metadata table with 发文字号, 发文机关, 主题分类, etc.
  - Template B: /zhengce/YYYYMM/content_NNN.htm (general policy articles)
    Has h1#ti title, div.pages-date, but no metadata table.
  Both share #UCAP-CONTENT for body text and <meta> tags in <head>.

Usage:
    python -m crawlers.gov                  # Crawl all documents from JSON feed
    python -m crawlers.gov --stats          # Show database stats
    python -m crawlers.gov --list-only      # List document URLs without fetching bodies
"""

import argparse
import re
import time

from crawlers.base import (
    REQUEST_DELAY,
    fetch,
    fetch_json,
    init_db,
    log,
    next_id,
    save_raw_html,
    show_stats,
    store_document,
    store_site,
)

SITE_KEY = "gov"
SITE_CFG = {
    "name": "State Council",
    "base_url": "https://www.gov.cn",
    "admin_level": "central",
}

JSON_FEED_URL = "https://www.gov.cn/zhengce/zuixin/ZUIXINZHENGCE.json"


def _extract_meta(html: str) -> dict:
    """Extract structured metadata from <meta> tags."""
    meta = {}
    for name in ("manuscriptId", "firstpublishedtime", "lastmodifiedtime",
                 "keywords", "description", "author", "lanmu", "catalog"):
        m = re.search(rf'<meta\s+name=["\']?{name}["\']?\s+content=["\']([^"\']*)["\']', html, re.IGNORECASE)
        if m:
            meta[name] = m.group(1).strip()
    return meta


def _extract_metadata_table(html: str) -> dict:
    """Extract structured fields from the metadata table (Template A only).

    Parses the table with 索引号, 发文机关, 发文字号, etc.
    """
    info = {}
    # Match table rows: <td><b>LABEL：</b></td><td>VALUE</td>
    for m in re.finditer(
        r'<td[^>]*><b>([^<]+)：?\s*</b></td>\s*<td[^>]*>(.*?)</td>',
        html, re.DOTALL,
    ):
        label = m.group(1).replace('\u3000', '').strip()
        value = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        if label == '发文字号':
            info['document_number'] = value
        elif label == '发文机关':
            info['publisher'] = value
        elif label == '成文日期':
            info['date_written_str'] = value
        elif label == '发布日期':
            info['date_published_str'] = value
        elif label == '主题分类':
            info['classify_theme_name'] = value
        elif label in ('标题', '标\u3000\u3000题'):
            info['title'] = value
        elif label == '索引号' or '索' in label:
            info['identifier'] = value
    return info


def _extract_title(html: str) -> str:
    """Extract title from h1#ti or <title> tag."""
    # Template B: <h1 id="ti">
    m = re.search(r'<h1[^>]*id=["\']ti["\'][^>]*>(.*?)</h1>', html, re.DOTALL)
    if m:
        return re.sub(r'<[^>]+>', '', m.group(1)).strip()
    # Fallback: <title>
    m = re.search(r'<title>(.*?)</title>', html)
    if m:
        title = m.group(1).strip()
        # Remove suffix like "_水利_中国政府网"
        title = re.sub(r'_[^_]+_中国政府网$', '', title)
        return title
    return ""


def _extract_source(html: str) -> str:
    """Extract source from Template B's div.pages-date > span.font."""
    m = re.search(r'<span\s+class="font[^"]*">来源：([^<]+)</span>', html)
    if m:
        return m.group(1).strip()
    return ""


def _extract_body(html: str) -> str:
    """Extract body text from #UCAP-CONTENT."""
    m = re.search(r'id=["\']UCAP-CONTENT["\'][^>]*>(.*?)</div>\s*(?:</div>|</table>)',
                  html, re.DOTALL)
    if not m:
        return ""
    content = m.group(1)
    # Replace <br> and <p> boundaries with newlines
    content = re.sub(r'<br\s*/?\s*>', '\n', content)
    content = re.sub(r'</p>', '\n', content)
    # Strip HTML tags
    text = re.sub(r'<[^>]+>', '', content)
    # Clean whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n', text)
    text = text.strip()
    # Unescape HTML entities
    text = text.replace("&nbsp;", " ").replace("&lt;", "<")
    text = text.replace("&gt;", ">").replace("&amp;", "&")
    if len(text) > 20:
        return text
    return ""


def fetch_document_list() -> list[dict]:
    """Fetch the JSON feed and return document entries."""
    log.info(f"Fetching document list from {JSON_FEED_URL}")
    data = fetch_json(JSON_FEED_URL)
    log.info(f"  Found {len(data)} documents in JSON feed")
    return data


def crawl_all(conn, fetch_bodies: bool = True):
    """Crawl all documents from the JSON feed."""
    store_site(conn, SITE_KEY, SITE_CFG)

    entries = fetch_document_list()
    stored = 0
    bodies = 0

    for entry in entries:
        doc_url = entry.get("URL", "")
        title = entry.get("TITLE", "")
        date_published = entry.get("DOCRELPUBTIME", "")

        if not doc_url or not title:
            continue

        # Check if already stored with body text
        existing = conn.execute(
            "SELECT id, body_text_cn FROM documents WHERE url = ?", (doc_url,)
        ).fetchone()
        if existing and existing[1]:
            stored += 1
            continue

        doc_id = existing[0] if existing else next_id(conn)

        body_text = ""
        raw_html_path = ""
        doc_number = ""
        publisher = ""
        identifier = ""
        classify_theme = ""
        keywords = ""

        if fetch_bodies:
            try:
                doc_html = fetch(doc_url)

                # Extract from <meta> tags
                meta = _extract_meta(doc_html)
                keywords = meta.get("keywords", "")
                if meta.get("firstpublishedtime"):
                    date_published = meta["firstpublishedtime"].replace("-", "-")

                # Try Template A metadata table
                table_info = _extract_metadata_table(doc_html)
                doc_number = table_info.get("document_number", "")
                publisher = table_info.get("publisher", "")
                identifier = table_info.get("identifier", "")
                classify_theme = table_info.get("classify_theme_name", "")
                if table_info.get("title"):
                    title = table_info["title"]

                # Template B fallback for publisher
                if not publisher:
                    publisher = _extract_source(doc_html)

                # Title fallback
                if not title or len(title) < 5:
                    extracted_title = _extract_title(doc_html)
                    if extracted_title:
                        title = extracted_title

                # Body text
                body_text = _extract_body(doc_html)

                if doc_html:
                    raw_html_path = save_raw_html(SITE_KEY, doc_id, doc_html)
                    bodies += 1
            except Exception as e:
                log.warning(f"  Failed to fetch {doc_url}: {e}")
            time.sleep(REQUEST_DELAY)

        store_document(conn, SITE_KEY, {
            "id": doc_id,
            "title": title,
            "document_number": doc_number,
            "identifier": identifier,
            "publisher": publisher,
            "keywords": keywords,
            "date_published": date_published,
            "body_text_cn": body_text,
            "url": doc_url,
            "classify_theme_name": classify_theme,
            "classify_main_name": "政策文件",
            "raw_html_path": raw_html_path,
        })
        stored += 1

        if stored % 20 == 0:
            conn.commit()
            log.info(f"  Progress: {stored}/{len(entries)} stored, {bodies} bodies")

    conn.commit()
    log.info(f"=== State Council total: {stored} documents, {bodies} bodies ===")


def main():
    parser = argparse.ArgumentParser(description="State Council Policy Crawler")
    parser.add_argument("--stats", action="store_true", help="Show database stats")
    parser.add_argument("--list-only", action="store_true",
                        help="List document URLs without fetching bodies")
    args = parser.parse_args()

    conn = init_db()

    if args.stats:
        show_stats(conn)
        conn.close()
        return

    crawl_all(conn, fetch_bodies=not args.list_only)
    show_stats(conn)
    conn.close()


if __name__ == "__main__":
    main()
