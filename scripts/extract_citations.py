"""Extract and persist cross-document citations.

Scans all documents with body text, extracts formal (文号) and named (《》)
references, resolves them against the corpus, and populates the citations table.

Usage:
    python3 scripts/extract_citations.py              # Extract and save
    python3 scripts/extract_citations.py --dry-run    # Show stats without saving
    python3 scripts/extract_citations.py --force      # Drop and rebuild
"""

import argparse
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from analyze import (
    REF_PATTERN, get_admin_level,
    NAMED_REF_PATTERN, is_policy_document, classify_named_ref_level,
)

DB_PATH = Path(__file__).parent.parent / "documents.db"

# Normalize site-level "department" to "municipal" for 4-level hierarchy
LEVEL_NORMALIZE = {"department": "municipal"}


def get_source_level(doc_number: str, site_admin_level: str) -> str:
    """Determine admin level for a source document."""
    if doc_number:
        level = get_admin_level(doc_number)
        if level != "unknown":
            return level
    # Fall back to site's admin level
    return LEVEL_NORMALIZE.get(site_admin_level, site_admin_level) or "unknown"


def extract_all(conn: sqlite3.Connection, dry_run: bool = False):
    """Extract citations from all documents with body text."""
    t0 = time.time()

    # --- Build lookup tables ---

    # document_number -> doc_id (for formal ref resolution)
    docnum_to_id = {}
    for row in conn.execute(
        "SELECT id, document_number FROM documents WHERE document_number <> ''"
    ).fetchall():
        docnum_to_id[row[0 + 1]] = row[0]  # docnum -> id

    # title -> (id, site_key) for named ref resolution (only titles >= 10 chars)
    title_to_doc = {}
    for row in conn.execute(
        "SELECT id, title, site_key FROM documents WHERE LENGTH(title) >= 10"
    ).fetchall():
        title_to_doc[row[1]] = (row[0], row[2])

    # site_key -> admin_level
    site_levels = {}
    for row in conn.execute("SELECT site_key, admin_level FROM sites").fetchall():
        site_levels[row[0]] = row[1] or "unknown"

    print(f"Lookup tables: {len(docnum_to_id)} doc numbers, {len(title_to_doc)} titles, {len(site_levels)} sites")

    # --- Fetch all documents with body text ---
    docs = conn.execute(
        """SELECT id, site_key, title, document_number, body_text_cn
           FROM documents
           WHERE body_text_cn IS NOT NULL AND LENGTH(body_text_cn) > 20"""
    ).fetchall()
    print(f"Documents with body text: {len(docs)}")

    # --- Extract citations ---
    citations = []  # list of (source_id, target_ref, target_id, citation_type, source_level, target_level)
    stats = Counter()

    for doc_id, site_key, title, doc_number, body in docs:
        source_level = get_source_level(doc_number, site_levels.get(site_key, ""))

        # Formal 文号 citations
        formal_refs = REF_PATTERN.findall(body)
        seen_formal = set()
        for ref in formal_refs:
            if ref == doc_number:  # skip self-reference
                continue
            if ref in seen_formal:
                continue
            seen_formal.add(ref)

            target_id = docnum_to_id.get(ref)
            target_level = get_admin_level(ref)
            citations.append((doc_id, ref, target_id, "formal", source_level, target_level))
            stats["formal"] += 1
            if target_id:
                stats["formal_resolved"] += 1

        # Named 《》 citations
        named_refs = NAMED_REF_PATTERN.findall(body)
        seen_named = set()
        for name in named_refs:
            if not is_policy_document(name):
                continue
            if name in title or title in name:  # skip self-reference
                continue
            if name in seen_named:
                continue
            seen_named.add(name)

            # Try to resolve to corpus
            target_id = None
            for db_title, (db_id, db_site_key) in title_to_doc.items():
                if len(db_title) >= 10 and (name in db_title or db_title in name):
                    target_id = db_id
                    break

            target_level = classify_named_ref_level(name)
            citations.append((doc_id, name, target_id, "named", source_level, target_level))
            stats["named"] += 1
            if target_id:
                stats["named_resolved"] += 1

    elapsed = time.time() - t0

    # --- Report ---
    print(f"\nExtracted {len(citations)} citations in {elapsed:.1f}s:")
    print(f"  Formal (文号): {stats['formal']} ({stats['formal_resolved']} resolved)")
    print(f"  Named  (《》): {stats['named']} ({stats['named_resolved']} resolved)")
    print(f"  Total resolved: {stats['formal_resolved'] + stats['named_resolved']}/{len(citations)}")

    # Level breakdown
    level_counts = Counter()
    cross_level = 0
    for _, _, _, _, src_lvl, tgt_lvl in citations:
        level_counts[f"{src_lvl} → {tgt_lvl}"] += 1
        if src_lvl != tgt_lvl and src_lvl != "unknown" and tgt_lvl != "unknown":
            cross_level += 1

    print(f"\n  Cross-level citations: {cross_level}")
    print(f"\n  Citation flow:")
    for flow, count in sorted(level_counts.items(), key=lambda x: -x[1])[:15]:
        print(f"    {flow}: {count}")

    if dry_run:
        print("\n[DRY RUN — nothing saved]")
        return

    # --- Save ---
    conn.execute("DELETE FROM citations")  # clear before re-insert
    conn.executemany(
        """INSERT OR REPLACE INTO citations
           (source_id, target_ref, target_id, citation_type, source_level, target_level)
           VALUES (?, ?, ?, ?, ?, ?)""",
        citations,
    )
    conn.commit()
    final_count = conn.execute("SELECT COUNT(*) FROM citations").fetchone()[0]
    print(f"\nSaved {final_count} citations to database")


def main():
    parser = argparse.ArgumentParser(description="Extract and persist cross-document citations")
    parser.add_argument("--dry-run", action="store_true", help="Show stats without saving")
    parser.add_argument("--force", action="store_true", help="Drop and recreate citations table first")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = None  # use tuples for speed

    if args.force:
        conn.execute("DROP TABLE IF EXISTS citations")
        conn.executescript("""
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
        print("Rebuilt citations table")

    extract_all(conn, dry_run=args.dry_run)
    conn.close()


if __name__ == "__main__":
    main()
