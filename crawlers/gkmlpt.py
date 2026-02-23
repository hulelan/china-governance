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
import time
from datetime import datetime, timezone

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
    "gd": {
        "name": "Guangdong Province",
        "base_url": "http://www.gd.gov.cn",
        "admin_level": "provincial",
    },
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
}


# --- Site Discovery ---

def discover_site(base_url: str) -> tuple[str, list]:
    """Fetch /gkmlpt/index and extract SID and TREE from _CONFIG."""
    url = f"{base_url}/gkmlpt/index"
    log.info(f"Discovering site config: {url}")
    html = fetch(url, timeout=30)

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
    base_url: str, sid: str, cat_id: int, cat_name: str
) -> list[dict]:
    """Fetch all documents in a category via the API."""
    page = 1
    all_articles = []
    post_count = None

    while True:
        url = f"{base_url}/gkmlpt/api/all/{cat_id}?page={page}&sid={sid}"
        try:
            data = fetch_json(url)
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

    return ""


def fetch_document_body(url: str) -> tuple[str, str]:
    """Fetch a document page and extract the body text.

    Returns (body_text, raw_html).
    """
    try:
        url = url.replace("https://", "http://")
        html = fetch(url, timeout=15)
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


# --- Main Crawl Loop ---

def crawl_site(conn, site_key: str, site_cfg: dict, fetch_bodies: bool = True):
    """Crawl a single site: discover -> list -> extract -> store."""
    base_url = site_cfg["base_url"]
    log.info(f"=== Crawling {site_cfg['name']} ({base_url}) ===")

    try:
        sid, tree = discover_site(base_url)
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
        articles = crawl_category(base_url, sid, cat_id, cat_name)
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
                body_text, raw_html = fetch_document_body(article["url"])
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


def backfill_bodies(conn, site_key: str = None, policy_first: bool = False):
    """Fetch body text for documents that are missing it."""
    where = "WHERE body_text_cn = '' AND url != ''"
    params = ()
    if site_key:
        where += " AND site_key = ?"
        params = (site_key,)
    order = "ORDER BY (document_number != '') DESC, id" if policy_first else "ORDER BY id"

    rows = conn.execute(
        f"SELECT id, site_key, url FROM documents {where} {order}", params
    ).fetchall()

    log.info(f"Backfilling body text for {len(rows)} documents")
    success = 0
    for i, (doc_id, sk, url) in enumerate(rows):
        body_text, raw_html = fetch_document_body(url)
        if body_text:
            raw_html_path = save_raw_html(sk, doc_id, raw_html) if raw_html else ""
            conn.execute(
                "UPDATE documents SET body_text_cn=?, raw_html_path=?, crawl_timestamp=? WHERE id=?",
                (body_text, raw_html_path, datetime.now(timezone.utc).isoformat(), doc_id),
            )
            success += 1
        if (i + 1) % 50 == 0:
            conn.commit()
            log.info(f"  Backfill progress: {i+1}/{len(rows)} ({success} successful)")
        time.sleep(REQUEST_DELAY)

    conn.commit()
    log.info(f"Backfill complete: {success}/{len(rows)} bodies fetched")


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
    args = parser.parse_args()

    if args.list_sites:
        print("\nConfigured sites:\n")
        for key, cfg in SITES.items():
            print(f"  {key:10s} {cfg['name']:40s} {cfg['base_url']}")
        return

    conn = init_db()

    if args.stats:
        show_stats(conn)
        conn.close()
        return

    if args.backfill_bodies:
        backfill_bodies(conn, args.site, args.policy_first)
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
