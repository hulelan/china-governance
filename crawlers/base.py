"""Shared crawler utilities: database, HTTP, storage."""

import json
import logging
import re
import sqlite3
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "documents.db"
RAW_HTML_DIR = Path(__file__).parent.parent / "raw_html"
REQUEST_DELAY = 0.5
USER_AGENT = "ChinaGovernanceCrawler/1.0 (Academic Research)"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# --- Database ---

def init_db(db_path: Path = None) -> sqlite3.Connection:
    if db_path is None:
        db_path = DB_PATH
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sites (
            site_key TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            base_url TEXT NOT NULL,
            admin_level TEXT,
            sid TEXT,
            tree_json TEXT,
            last_crawled TEXT
        );

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY,
            site_key TEXT NOT NULL,
            name TEXT NOT NULL,
            parent_id INTEGER,
            post_count INTEGER DEFAULT 0,
            FOREIGN KEY (site_key) REFERENCES sites(site_key)
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY,
            site_key TEXT NOT NULL,
            category_id INTEGER,
            title TEXT NOT NULL,
            document_number TEXT,
            identifier TEXT,
            publisher TEXT,
            keywords TEXT,
            date_written INTEGER,
            date_published TEXT,
            display_publish_time INTEGER,
            abstract TEXT,
            body_text_cn TEXT,
            body_text_en TEXT,
            classify_main_name TEXT,
            classify_genre_name TEXT,
            classify_theme_name TEXT,
            url TEXT,
            post_url TEXT,
            is_expired INTEGER DEFAULT 0,
            is_abolished INTEGER DEFAULT 0,
            attachments_json TEXT,
            relation TEXT,
            raw_html_path TEXT,
            crawl_timestamp TEXT NOT NULL,
            FOREIGN KEY (site_key) REFERENCES sites(site_key)
        );

        CREATE INDEX IF NOT EXISTS idx_documents_site ON documents(site_key);
        CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category_id);
        CREATE INDEX IF NOT EXISTS idx_documents_date ON documents(date_written);
        CREATE INDEX IF NOT EXISTS idx_documents_docnum ON documents(document_number);

        CREATE TABLE IF NOT EXISTS citations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            target_ref TEXT NOT NULL,
            target_id INTEGER,
            citation_type TEXT NOT NULL,
            source_level TEXT NOT NULL,
            target_level TEXT NOT NULL,
            FOREIGN KEY (source_id) REFERENCES documents(id),
            FOREIGN KEY (target_id) REFERENCES documents(id),
            UNIQUE(source_id, target_ref, citation_type)
        );

        CREATE INDEX IF NOT EXISTS idx_citations_source ON citations(source_id);
        CREATE INDEX IF NOT EXISTS idx_citations_target_id ON citations(target_id);
        CREATE INDEX IF NOT EXISTS idx_citations_target_ref ON citations(target_ref);
        CREATE INDEX IF NOT EXISTS idx_citations_levels ON citations(source_level, target_level);
    """)
    conn.commit()
    return conn


# --- HTTP ---

def fetch(url: str, timeout: int = 20, retries: int = 3, headers: dict = None) -> str:
    """Fetch a URL and return the response body as a string."""
    hdrs = {"User-Agent": USER_AGENT}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    for attempt in range(retries):
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)
            return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code in (404, 410, 550):
                raise
            if attempt < retries - 1:
                wait = 2 ** attempt
                log.warning(f"  Retry {attempt+1}/{retries} for {url}: {e}")
                time.sleep(wait)
            else:
                raise
        except (urllib.error.URLError, OSError) as e:
            if attempt < retries - 1:
                wait = 2 ** attempt
                log.warning(f"  Retry {attempt+1}/{retries} for {url}: {e}")
                time.sleep(wait)
            else:
                raise


def fetch_json(url: str, timeout: int = 20, headers: dict = None):
    """Fetch a URL and parse the response as JSON."""
    text = fetch(url, timeout, headers=headers)
    return json.loads(text)


# --- Storage ---

def store_site(conn: sqlite3.Connection, site_key: str, site_cfg: dict,
               sid: str = "", tree: list = None):
    """Insert or update site record."""
    conn.execute(
        """INSERT INTO sites (site_key, name, base_url, admin_level, sid, tree_json, last_crawled)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(site_key) DO UPDATE SET
             sid=excluded.sid, tree_json=excluded.tree_json, last_crawled=excluded.last_crawled""",
        (
            site_key,
            site_cfg["name"],
            site_cfg["base_url"],
            site_cfg.get("admin_level", ""),
            sid,
            json.dumps(tree or [], ensure_ascii=False),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()


def store_document(conn: sqlite3.Connection, site_key: str, doc: dict):
    """Insert or update a document record.

    `doc` must have at minimum: id, title.
    All other fields are optional and default to empty/zero.
    """
    conn.execute(
        """INSERT INTO documents (
            id, site_key, category_id, title, document_number, identifier,
            publisher, keywords, date_written, date_published, display_publish_time,
            abstract, body_text_cn, classify_main_name, classify_genre_name,
            classify_theme_name, url, post_url, is_expired, is_abolished,
            attachments_json, relation, raw_html_path, crawl_timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            body_text_cn=CASE WHEN excluded.body_text_cn != '' THEN excluded.body_text_cn ELSE documents.body_text_cn END,
            raw_html_path=CASE WHEN excluded.raw_html_path != '' THEN excluded.raw_html_path ELSE documents.raw_html_path END,
            crawl_timestamp=excluded.crawl_timestamp""",
        (
            doc["id"],
            site_key,
            doc.get("category_id", 0),
            doc["title"],
            doc.get("document_number", ""),
            doc.get("identifier", ""),
            doc.get("publisher", ""),
            doc.get("keywords", ""),
            doc.get("date_written", 0),
            doc.get("date_published", ""),
            doc.get("display_publish_time", 0),
            doc.get("abstract", ""),
            doc.get("body_text_cn", ""),
            doc.get("classify_main_name", ""),
            doc.get("classify_genre_name", ""),
            doc.get("classify_theme_name", ""),
            doc.get("url", ""),
            doc.get("post_url", ""),
            doc.get("is_expired", 0),
            doc.get("is_abolished", 0),
            doc.get("attachments_json", "[]"),
            doc.get("relation", ""),
            doc.get("raw_html_path", ""),
            datetime.now(timezone.utc).isoformat(),
        ),
    )


def save_raw_html(site_key: str, doc_id, html: str) -> str:
    """Save raw HTML to filesystem. Returns relative path."""
    site_dir = RAW_HTML_DIR / site_key
    site_dir.mkdir(parents=True, exist_ok=True)
    path = site_dir / f"{doc_id}.html"
    path.write_text(html, encoding="utf-8")
    return str(path.relative_to(Path(__file__).parent.parent))


def show_stats(conn: sqlite3.Connection):
    """Show database statistics."""
    print("\n=== Database Statistics ===\n")
    sites = conn.execute(
        "SELECT site_key, name, admin_level, last_crawled FROM sites ORDER BY admin_level, name"
    ).fetchall()
    if not sites:
        print("No data yet. Run a crawler first.")
        return

    for site_key, name, admin_level, last_crawled in sites:
        total = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE site_key = ?", (site_key,)
        ).fetchone()[0]
        with_body = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE site_key = ? AND body_text_cn != ''",
            (site_key,),
        ).fetchone()[0]
        print(f"[{admin_level or '?':10s}] {name}")
        print(f"  Documents: {total}, With body: {with_body}")
        if last_crawled:
            print(f"  Last crawled: {last_crawled}")
        print()

    total_all = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    print(f"Total documents across all sites: {total_all}")


def next_id(conn: sqlite3.Connection) -> int:
    """Get next available document ID (for sites without their own IDs)."""
    row = conn.execute("SELECT MAX(id) FROM documents").fetchone()
    return (row[0] or 0) + 1
