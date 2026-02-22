"""Targeted body text backfill for AI-related documents.

Fetches body text for documents related to artificial intelligence (人工智能)
that are currently missing body text in the database.

Usage:
    python3 scripts/backfill_ai.py              # Run backfill
    python3 scripts/backfill_ai.py --dry-run    # Show what would be fetched
"""

import argparse
import logging
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path so we can import from crawler
sys.path.insert(0, str(Path(__file__).parent.parent))
from crawler import fetch_document_body, save_raw_html, DB_PATH, REQUEST_DELAY

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

QUERY = """
SELECT id, site_key, title, url, document_number
FROM documents
WHERE (
    title LIKE '%人工智能%'
    OR keywords LIKE '%人工智能%'
    OR abstract LIKE '%人工智能%'
)
AND (body_text_cn IS NULL OR body_text_cn = '' OR LENGTH(body_text_cn) < 20)
AND url IS NOT NULL AND url <> ''
ORDER BY
    (document_number IS NOT NULL AND document_number <> '') DESC,
    date_published DESC
"""


def main():
    parser = argparse.ArgumentParser(description="Backfill body text for AI-related documents")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be fetched without fetching")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(QUERY).fetchall()

    log.info(f"Found {len(rows)} AI-related documents needing body text")

    if args.dry_run:
        for doc_id, site_key, title, url, doc_num in rows:
            marker = f" [{doc_num}]" if doc_num else ""
            print(f"  {doc_id} ({site_key}){marker} {title[:60]}")
        return

    success = 0
    failed = 0
    for i, (doc_id, site_key, title, url, doc_num) in enumerate(rows):
        marker = f" [{doc_num}]" if doc_num else ""
        log.info(f"[{i+1}/{len(rows)}] Fetching {doc_id}{marker} — {title[:50]}")

        body_text, raw_html = fetch_document_body(url)
        if body_text:
            raw_html_path = save_raw_html(site_key, doc_id, raw_html) if raw_html else ""
            conn.execute(
                "UPDATE documents SET body_text_cn=?, raw_html_path=?, crawl_timestamp=? WHERE id=?",
                (body_text, raw_html_path, datetime.now(timezone.utc).isoformat(), doc_id),
            )
            success += 1
            log.info(f"  OK — {len(body_text)} chars")
        else:
            failed += 1
            log.warning(f"  FAILED — no body text extracted from {url}")

        if (i + 1) % 10 == 0:
            conn.commit()

        time.sleep(REQUEST_DELAY)

    conn.commit()
    conn.close()

    log.info(f"Done: {success} succeeded, {failed} failed out of {len(rows)} total")


if __name__ == "__main__":
    main()
