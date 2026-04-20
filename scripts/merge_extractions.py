"""
Merge NPC laws and PDF-extracted body text into documents.db.

Two merge operations:
1. NPC laws (npc_full.db) → INSERT new rows (29k laws, metadata only)
2. PDF extractions (documents_pdf_extract.db) → UPDATE existing rows
   with extracted body text (replaces short stubs with full content)

Usage:
    python3 scripts/merge_extractions.py                    # Merge both
    python3 scripts/merge_extractions.py --npc-only         # NPC laws only
    python3 scripts/merge_extractions.py --pdf-only         # PDF extractions only
    python3 scripts/merge_extractions.py --dry-run          # Preview without writing
"""

import argparse
import sqlite3
import sys
from pathlib import Path

NPC_DB = "/tmp/npc_full.db"
PDF_DB = "documents_pdf_extract.db"
MAIN_DB = "documents.db"


def merge_npc(main_conn, dry_run=False):
    """Merge NPC laws into main DB. INSERT OR IGNORE by URL."""
    npc_path = Path(NPC_DB)
    if not npc_path.exists():
        print(f"  NPC DB not found: {NPC_DB}")
        return 0

    npc = sqlite3.connect(str(npc_path))

    # Get column names from main DB
    cols = [r[1] for r in main_conn.execute("PRAGMA table_info(documents)")]
    npc_cols = [r[1] for r in npc.execute("PRAGMA table_info(documents)")]

    # Use only columns that exist in both
    shared = [c for c in cols if c in npc_cols]
    placeholders = ",".join(["?"] * len(shared))
    col_list = ",".join(shared)

    # Ensure the site exists
    site_row = npc.execute("SELECT * FROM sites WHERE site_key = 'npc'").fetchone()
    if site_row and not dry_run:
        site_cols = [r[1] for r in npc.execute("PRAGMA table_info(sites)")]
        site_ph = ",".join(["?"] * len(site_cols))
        try:
            main_conn.execute(
                f"INSERT OR REPLACE INTO sites ({','.join(site_cols)}) VALUES ({site_ph})",
                site_row,
            )
        except Exception as e:
            print(f"  Warning: site insert: {e}")

    # Re-ID the NPC docs to avoid ID collisions with main DB
    max_id = main_conn.execute("SELECT MAX(id) FROM documents").fetchone()[0] or 0
    next_id = max_id + 1

    total = npc.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    print(f"  NPC laws to merge: {total}")

    if dry_run:
        # Check how many are already in main DB
        existing = 0
        for row in npc.execute("SELECT url FROM documents"):
            r = main_conn.execute("SELECT 1 FROM documents WHERE url = ?", (row[0],)).fetchone()
            if r:
                existing += 1
        print(f"  Already in main DB: {existing}")
        print(f"  Would insert: {total - existing}")
        npc.close()
        return total - existing

    inserted = 0
    skipped = 0
    id_idx = shared.index("id")

    for row in npc.execute(f"SELECT {col_list} FROM documents"):
        url_idx = shared.index("url")
        url = row[url_idx]

        # Check if URL already exists (include url != '' so SQLite uses partial index)
        existing = main_conn.execute(
            "SELECT 1 FROM documents WHERE url = ? AND url != ''", (url,)
        ).fetchone()
        if existing:
            skipped += 1
            continue

        # Assign new ID
        row_list = list(row)
        row_list[id_idx] = next_id
        next_id += 1

        try:
            main_conn.execute(
                f"INSERT INTO documents ({col_list}) VALUES ({placeholders})",
                row_list,
            )
            inserted += 1
        except sqlite3.IntegrityError:
            skipped += 1

        if inserted % 5000 == 0 and inserted > 0:
            main_conn.commit()
            print(f"    {inserted} inserted, {skipped} skipped...")

    main_conn.commit()
    print(f"  NPC merge: {inserted} inserted, {skipped} skipped")
    npc.close()
    return inserted


def merge_pdf_extractions(main_conn, dry_run=False):
    """Update existing docs with extracted body text from PDF/DOC attachments."""
    pdf_path = Path(PDF_DB)
    if not pdf_path.exists():
        print(f"  PDF extraction DB not found: {PDF_DB}")
        return 0

    pdf = sqlite3.connect(str(pdf_path))

    # Find docs where body text was actually extracted (>500 chars)
    rows = pdf.execute("""
        SELECT id, body_text_cn, site_key, title
        FROM documents
        WHERE body_text_cn IS NOT NULL AND LENGTH(body_text_cn) > 500
    """).fetchall()

    print(f"  PDF extractions to merge: {len(rows)}")

    if dry_run:
        for doc_id, body, site, title in rows[:10]:
            cur = main_conn.execute(
                "SELECT LENGTH(body_text_cn) FROM documents WHERE id = ?", (doc_id,)
            ).fetchone()
            cur_len = cur[0] if cur else 0
            print(f"    [{site}] id={doc_id}: {cur_len}ch → {len(body)}ch  {title[:50]}")
        if len(rows) > 10:
            print(f"    ... and {len(rows) - 10} more")
        pdf.close()
        return len(rows)

    updated = 0
    not_found = 0
    for doc_id, body, site, title in rows:
        # Verify the doc exists in main DB
        existing = main_conn.execute(
            "SELECT id FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
        if not existing:
            not_found += 1
            continue

        main_conn.execute(
            "UPDATE documents SET body_text_cn = ? WHERE id = ?",
            (body, doc_id),
        )
        updated += 1

    main_conn.commit()
    print(f"  PDF merge: {updated} updated, {not_found} not found in main DB")
    pdf.close()
    return updated


def main():
    parser = argparse.ArgumentParser(description="Merge NPC laws + PDF extractions")
    parser.add_argument("--npc-only", action="store_true")
    parser.add_argument("--pdf-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--db", default=MAIN_DB)
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA busy_timeout = 30000")

    do_npc = not args.pdf_only
    do_pdf = not args.npc_only

    if do_pdf:
        print("=== PDF Extraction Merge ===")
        merge_pdf_extractions(conn, dry_run=args.dry_run)

    if do_npc:
        print("=== NPC Laws Merge ===")
        merge_npc(conn, dry_run=args.dry_run)

    # Summary
    total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    npc_count = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE site_key = 'npc'"
    ).fetchone()[0]
    print(f"\nMain DB total: {total} docs ({npc_count} NPC laws)")
    conn.close()


if __name__ == "__main__":
    main()
