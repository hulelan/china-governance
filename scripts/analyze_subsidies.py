"""Analyze extracted subsidy data and produce aggregate statistics.

Reads from subsidy_items + documents + sites tables and outputs
structured analysis to data/subsidy_analysis.json.

Usage:
    python3 scripts/analyze_subsidies.py              # Analyze and save
    python3 scripts/analyze_subsidies.py --print      # Print to stdout only
"""

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "documents.db"
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "subsidy_analysis.json"


def analyze(conn):
    """Run all analysis queries and return structured results."""
    results = {}

    # --- Overview stats ---
    overview = {}
    row = conn.execute("""
        SELECT COUNT(DISTINCT si.document_id) as doc_count,
               COUNT(*) as item_count,
               SUM(si.amount_value) as total_wan
        FROM subsidy_items si
    """).fetchone()
    overview["documents_with_amounts"] = row["doc_count"]
    overview["total_items"] = row["item_count"]
    overview["total_amount_wan"] = row["total_wan"] or 0
    overview["total_amount_yi"] = round((row["total_wan"] or 0) / 10000, 1)

    # Total subsidy-relevant docs (including those without extractable amounts)
    title_kws = ["补贴", "扶持", "奖励", "资助", "引导基金", "专项资金", "产业资金"]
    title_conds = " OR ".join(f"d.title LIKE '%{kw}%'" for kw in title_kws)
    cat_conds = "d.classify_main_name LIKE '%专项资金信息%' OR d.classify_main_name LIKE '%财政预决算%'"
    total_docs = conn.execute(f"""
        SELECT COUNT(*) FROM documents d
        WHERE ({title_conds} OR {cat_conds})
    """).fetchone()[0]
    overview["total_subsidy_docs"] = total_docs

    with_body = conn.execute(f"""
        SELECT COUNT(*) FROM documents d
        WHERE ({title_conds} OR {cat_conds})
          AND d.body_text_cn IS NOT NULL AND LENGTH(d.body_text_cn) > 20
    """).fetchone()[0]
    overview["subsidy_docs_with_body"] = with_body

    results["overview"] = overview

    # --- By district/site ---
    rows = conn.execute("""
        SELECT s.site_key, s.name, s.admin_level,
               COUNT(DISTINCT si.document_id) as doc_count,
               COUNT(si.id) as item_count,
               SUM(si.amount_value) as total_wan,
               AVG(si.amount_value) as avg_wan,
               MAX(si.amount_value) as max_wan
        FROM subsidy_items si
        JOIN documents d ON d.id = si.document_id
        JOIN sites s ON s.site_key = d.site_key
        GROUP BY s.site_key
        ORDER BY total_wan DESC
    """).fetchall()
    results["by_district"] = [dict(r) for r in rows]

    # --- By sector ---
    rows = conn.execute("""
        SELECT si.sector,
               COUNT(DISTINCT si.document_id) as doc_count,
               COUNT(si.id) as item_count,
               SUM(si.amount_value) as total_wan,
               AVG(si.amount_value) as avg_wan
        FROM subsidy_items si
        WHERE si.sector IS NOT NULL
        GROUP BY si.sector
        ORDER BY doc_count DESC
    """).fetchall()
    results["by_sector"] = [dict(r) for r in rows]

    # --- By year ---
    rows = conn.execute("""
        SELECT SUBSTR(d.date_published, 1, 4) as year,
               COUNT(DISTINCT si.document_id) as doc_count,
               COUNT(si.id) as item_count,
               SUM(si.amount_value) as total_wan
        FROM subsidy_items si
        JOIN documents d ON d.id = si.document_id
        WHERE d.date_published IS NOT NULL AND d.date_published != ''
        GROUP BY year
        HAVING year >= '2015'
        ORDER BY year
    """).fetchall()
    results["by_year"] = [dict(r) for r in rows]

    # --- Top individual programs (largest single amounts) ---
    rows = conn.execute("""
        SELECT si.amount_value, si.amount_raw, si.amount_context, si.sector,
               d.id as doc_id, d.title, d.document_number, d.site_key,
               d.date_published, s.name as site_name
        FROM subsidy_items si
        JOIN documents d ON d.id = si.document_id
        JOIN sites s ON s.site_key = d.site_key
        ORDER BY si.amount_value DESC
        LIMIT 30
    """).fetchall()
    results["top_programs"] = [dict(r) for r in rows]

    # --- Central policy linkage ---
    # Which central directives are cited by subsidy documents?
    rows = conn.execute("""
        SELECT c.target_ref, c.target_level, c.citation_type,
               COUNT(DISTINCT c.source_id) as citing_docs,
               COUNT(DISTINCT si.document_id) as subsidy_docs_citing,
               SUM(si.amount_value) as linked_amount_wan
        FROM citations c
        JOIN subsidy_items si ON si.document_id = c.source_id
        WHERE c.target_level = 'central'
        GROUP BY c.target_ref
        ORDER BY citing_docs DESC
        LIMIT 20
    """).fetchall()
    results["central_linkage"] = [dict(r) for r in rows]

    # --- Documents with most subsidy items ---
    rows = conn.execute("""
        SELECT d.id, d.title, d.document_number, d.site_key, d.date_published,
               s.name as site_name,
               COUNT(si.id) as item_count,
               SUM(si.amount_value) as total_wan,
               GROUP_CONCAT(DISTINCT si.sector) as sectors
        FROM subsidy_items si
        JOIN documents d ON d.id = si.document_id
        JOIN sites s ON s.site_key = d.site_key
        GROUP BY d.id
        ORDER BY item_count DESC
        LIMIT 20
    """).fetchall()
    results["top_documents"] = [dict(r) for r in rows]

    return results


def print_report(results):
    """Print a human-readable summary."""
    ov = results["overview"]
    print("=" * 60)
    print("SUBSIDY ANALYSIS REPORT")
    print("=" * 60)
    print(f"\nTotal subsidy-relevant documents: {ov['total_subsidy_docs']:,}")
    print(f"  With body text: {ov['subsidy_docs_with_body']:,}")
    print(f"  With extractable amounts: {ov['documents_with_amounts']:,}")
    print(f"Total amount items: {ov['total_items']:,}")
    print(f"Total identified value: {ov['total_amount_wan']:,.0f} 万元 ({ov['total_amount_yi']:.1f} 亿元)")

    print(f"\n--- BY DISTRICT/SITE (top 10) ---")
    for r in results["by_district"][:10]:
        print(f"  {r['name']}: {r['doc_count']} docs, {r['total_wan']:,.0f} 万元 ({r['total_wan']/10000:.1f}亿)")

    print(f"\n--- BY SECTOR (top 15) ---")
    for r in results["by_sector"][:15]:
        print(f"  {r['sector']}: {r['doc_count']} docs, {r['total_wan']:,.0f} 万元")

    print(f"\n--- BY YEAR ---")
    for r in results["by_year"]:
        if r["year"] and r["total_wan"]:
            print(f"  {r['year']}: {r['doc_count']} docs, {r['total_wan']:,.0f} 万元")

    print(f"\n--- TOP CENTRAL POLICIES LINKED TO SUBSIDIES ---")
    for r in results["central_linkage"][:10]:
        print(f"  {r['target_ref']}: cited by {r['citing_docs']} subsidy docs")

    print(f"\n--- TOP DOCUMENTS BY SUBSIDY ITEMS ---")
    for r in results["top_documents"][:10]:
        sectors = r["sectors"] or "unspecified"
        print(f"  [{r['site_key']}] {r['title'][:50]}... ({r['item_count']} items, {r['total_wan']:,.0f} 万元)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze extracted subsidy data")
    parser.add_argument("--print", action="store_true", help="Print to stdout only (no file output)")
    args = parser.parse_args()

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")

    try:
        conn.execute("SELECT 1 FROM subsidy_items LIMIT 1")
    except sqlite3.OperationalError:
        print("Error: subsidy_items table not found. Run extract_subsidy_data.py first.")
        sys.exit(1)

    results = analyze(conn)
    print_report(results)

    if not args.print:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        print(f"\nSaved to {OUTPUT_PATH}")

    conn.close()
