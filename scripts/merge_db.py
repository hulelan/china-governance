"""
Merge a source SQLite database into the main documents.db.

Use this when crawlers write to a separate DB (via --db flag) to avoid
lock contention with a running crawler. After crawling completes, run this
to merge the new data into the main database.

Handles:
  - Sites: merged by site_key (INSERT OR IGNORE)
  - Documents: merged by URL deduplication with ID remapping
  - Categories: merged with ID remapping
  - Raw HTML files: already on disk (crawlers write to raw_html/ regardless of DB)

Does NOT merge (regenerate these after merge):
  - citations (run: python -m analysis.citations --site <key>)
  - subsidy_items (run: python -m analysis.subsidies --site <key>)
  - document_changes (only relevant for sync operations)

Usage:
    python scripts/merge_db.py documents_new.db              # Merge into documents.db
    python scripts/merge_db.py documents_new.db --target main.db  # Custom target
    python scripts/merge_db.py documents_new.db --dry-run     # Preview without writing
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from crawlers.base import DB_PATH, init_db, log, next_id


def merge(source_path: Path, target_path: Path, dry_run: bool = False):
    """Merge source database into target database."""
    if not source_path.exists():
        log.error(f"Source database not found: {source_path}")
        return

    log.info(f"Merging {source_path} → {target_path}")

    src = sqlite3.connect(str(source_path), timeout=30)
    src.row_factory = sqlite3.Row
    tgt = init_db(target_path)
    tgt.row_factory = sqlite3.Row

    # --- Sites ---
    src_sites = src.execute("SELECT * FROM sites").fetchall()
    sites_added = 0
    for site in src_sites:
        existing = tgt.execute(
            "SELECT site_key FROM sites WHERE site_key = ?", (site["site_key"],)
        ).fetchone()
        if existing:
            log.info(f"  Site '{site['site_key']}' already exists in target, updating")
            if not dry_run:
                tgt.execute(
                    """UPDATE sites SET name=?, base_url=?, admin_level=?,
                       sid=?, tree_json=?, last_crawled=?
                       WHERE site_key=?""",
                    (site["name"], site["base_url"], site["admin_level"],
                     site["sid"], site["tree_json"], site["last_crawled"],
                     site["site_key"]),
                )
        else:
            log.info(f"  Adding site '{site['site_key']}': {site['name']}")
            if not dry_run:
                tgt.execute(
                    """INSERT INTO sites (site_key, name, base_url, admin_level,
                       sid, tree_json, last_crawled)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (site["site_key"], site["name"], site["base_url"],
                     site["admin_level"], site["sid"], site["tree_json"],
                     site["last_crawled"]),
                )
            sites_added += 1

    if not dry_run:
        tgt.commit()

    # --- Categories ---
    src_cats = src.execute("SELECT * FROM categories").fetchall()
    # Build ID mapping: old_id -> new_id
    cat_id_map = {}
    cats_added = 0
    for cat in src_cats:
        # Check if this exact category already exists
        existing = tgt.execute(
            "SELECT id FROM categories WHERE site_key = ? AND name = ? AND parent_id = ?",
            (cat["site_key"], cat["name"], cat["parent_id"]),
        ).fetchone()
        if existing:
            cat_id_map[cat["id"]] = existing["id"]
        else:
            if not dry_run:
                cursor = tgt.execute(
                    """INSERT INTO categories (site_key, name, parent_id, post_count)
                       VALUES (?, ?, ?, ?)""",
                    (cat["site_key"], cat["name"], cat["parent_id"],
                     cat["post_count"]),
                )
                cat_id_map[cat["id"]] = cursor.lastrowid
            else:
                cat_id_map[cat["id"]] = cat["id"]  # placeholder for dry run
            cats_added += 1

    if not dry_run:
        tgt.commit()

    log.info(f"  Categories: {cats_added} added, {len(src_cats) - cats_added} already existed")

    # --- Documents ---
    src_docs = src.execute("SELECT * FROM documents").fetchall()
    # Build set of existing URLs in target for fast lookup
    existing_urls = set()
    for row in tgt.execute("SELECT url FROM documents WHERE url != ''"):
        existing_urls.add(row["url"])

    docs_added = 0
    docs_skipped = 0
    for doc in src_docs:
        # Deduplicate by URL
        if doc["url"] and doc["url"] in existing_urls:
            docs_skipped += 1
            continue

        # Assign new ID in target DB
        new_id = next_id(tgt) if not dry_run else doc["id"]

        # Remap category_id if applicable
        new_cat_id = cat_id_map.get(doc["category_id"], doc["category_id"])

        if not dry_run:
            tgt.execute(
                """INSERT INTO documents (
                    id, site_key, category_id, title, document_number, identifier,
                    publisher, keywords, date_written, date_published,
                    display_publish_time, abstract, body_text_cn,
                    classify_main_name, classify_genre_name, classify_theme_name,
                    url, post_url, is_expired, is_abolished, attachments_json,
                    relation, raw_html_path, crawl_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (new_id, doc["site_key"], new_cat_id, doc["title"],
                 doc["document_number"], doc["identifier"], doc["publisher"],
                 doc["keywords"], doc["date_written"], doc["date_published"],
                 doc["display_publish_time"], doc["abstract"],
                 doc["body_text_cn"], doc["classify_main_name"],
                 doc["classify_genre_name"], doc["classify_theme_name"],
                 doc["url"], doc["post_url"], doc["is_expired"],
                 doc["is_abolished"], doc["attachments_json"],
                 doc["relation"], doc["raw_html_path"], doc["crawl_timestamp"]),
            )

        docs_added += 1
        existing_urls.add(doc["url"])

        if docs_added % 100 == 0 and not dry_run:
            tgt.commit()
            log.info(f"  Progress: {docs_added} docs merged")

    if not dry_run:
        tgt.commit()

    # --- Summary ---
    action = "Would merge" if dry_run else "Merged"
    log.info(f"\n=== Merge {'Preview' if dry_run else 'Complete'} ===")
    log.info(f"  {action} {sites_added} new sites")
    log.info(f"  {action} {cats_added} new categories")
    log.info(f"  {action} {docs_added} new documents ({docs_skipped} duplicates skipped)")

    if not dry_run:
        # Show final stats
        total = tgt.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        log.info(f"  Target DB total: {total} documents")

    src.close()
    tgt.close()


def main():
    parser = argparse.ArgumentParser(
        description="Merge a source SQLite DB into the main documents.db",
    )
    parser.add_argument(
        "source", type=str, help="Path to source database to merge from",
    )
    parser.add_argument(
        "--target", type=str, default=None,
        help="Path to target database (default: documents.db)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview merge without writing to target",
    )
    args = parser.parse_args()

    source = Path(args.source)
    target = Path(args.target) if args.target else DB_PATH

    merge(source, target, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
