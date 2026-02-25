"""Extract structured subsidy data from document body text.

Scans subsidy-relevant documents and extracts:
- Yuan amounts (万元, 亿元) with surrounding context
- Sector/industry keywords
- Stores in subsidy_items table for aggregation

Usage:
    python3 scripts/extract_subsidy_data.py              # Extract and save
    python3 scripts/extract_subsidy_data.py --dry-run    # Show stats without saving
    python3 scripts/extract_subsidy_data.py --force      # Drop and rebuild
"""

import argparse
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "documents.db"

# --- Subsidy document identification ---

SUBSIDY_TITLE_KEYWORDS = [
    "补贴", "扶持", "奖励", "资助", "引导基金", "专项资金", "产业资金",
    "支持措施", "扶持措施", "奖励办法", "资助办法", "若干措施",
    "促进.*发展", "贴息",
]

SUBSIDY_CATEGORY_KEYWORDS = [
    "专项资金信息", "财政预决算", "其他资金信息",
]

# --- Amount extraction ---

# Matches amounts like: 500万元, 3000万元, 1亿元, 2.5亿元, 0.5万元
AMOUNT_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(万元|亿元)"
)

# Captures surrounding context (up to 80 chars before, 40 after)
AMOUNT_CONTEXT_PATTERN = re.compile(
    r"([^。；\n]{0,80})(\d+(?:\.\d+)?)\s*(万元|亿元)([^。；\n]{0,40})"
)

# --- Sector/industry keywords ---

SECTOR_KEYWORDS = [
    "人工智能", "集成电路", "半导体", "芯片",
    "新能源", "新能源汽车", "光伏", "储能",
    "生物医药", "生命健康", "医疗器械",
    "数字经济", "数字化", "信息技术", "软件",
    "智能制造", "机器人", "高端装备",
    "新材料", "先进材料",
    "海洋经济", "海洋产业",
    "航空航天", "低空经济", "无人机",
    "5G", "量子", "区块链",
    "文化创意", "文化产业",
    "金融科技", "现代服务业",
    "绿色低碳", "节能环保",
    "现代农业",
    "总部经济",
]

# Compile sector patterns for efficiency
SECTOR_PATTERNS = [(kw, re.compile(re.escape(kw))) for kw in SECTOR_KEYWORDS]


def find_subsidy_documents(conn):
    """Find all documents that are likely about subsidies/funding."""
    title_conditions = " OR ".join(
        f"d.title LIKE '%{kw}%'" for kw in SUBSIDY_TITLE_KEYWORDS
    )
    cat_conditions = " OR ".join(
        f"d.classify_main_name LIKE '%{kw}%'" for kw in SUBSIDY_CATEGORY_KEYWORDS
    )

    query = f"""
        SELECT d.id, d.title, d.document_number, d.site_key,
               d.date_published, d.publisher, d.body_text_cn,
               d.classify_main_name, s.admin_level, s.name as site_name
        FROM documents d
        JOIN sites s ON s.site_key = d.site_key
        WHERE ({title_conditions} OR {cat_conditions})
          AND d.body_text_cn IS NOT NULL AND LENGTH(d.body_text_cn) > 20
        ORDER BY d.date_published DESC
    """
    return conn.execute(query).fetchall()


def extract_amounts(body_text):
    """Extract all yuan amounts from body text with context."""
    items = []
    for m in AMOUNT_CONTEXT_PATTERN.finditer(body_text):
        pre_context, number_str, unit, post_context = m.groups()
        value = float(number_str)

        # Normalize to 万元
        if unit == "亿元":
            value_wan = value * 10000
        else:
            value_wan = value

        # Skip trivially small amounts (likely noise) and absurdly large ones
        if value_wan < 0.5 or value_wan > 10000000:
            continue

        context = f"{pre_context.strip()}{number_str}{unit}{post_context.strip()}"

        items.append({
            "amount_value": value_wan,
            "amount_raw": f"{number_str}{unit}",
            "amount_context": context[:200],
        })
    return items


def extract_sectors(body_text):
    """Find which sector keywords appear in the document."""
    found = []
    for kw, pattern in SECTOR_PATTERNS:
        if pattern.search(body_text):
            found.append(kw)
    return found


def create_table(conn):
    """Create the subsidy_items table."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS subsidy_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            amount_value REAL,
            amount_raw TEXT,
            amount_context TEXT,
            sector TEXT,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_subsidy_items_doc ON subsidy_items(document_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_subsidy_items_sector ON subsidy_items(sector)")
    conn.commit()


def extract_all(conn, dry_run=False):
    """Main extraction loop."""
    docs = find_subsidy_documents(conn)
    print(f"Found {len(docs)} subsidy-relevant documents with body text")

    all_items = []
    docs_with_amounts = 0
    sector_counts = Counter()
    amount_stats = {"total_wan": 0, "count": 0}

    for doc in docs:
        doc_id = doc["id"]
        body = doc["body_text_cn"]

        # Extract amounts
        amounts = extract_amounts(body)

        # Extract sectors
        sectors = extract_sectors(body)
        for s in sectors:
            sector_counts[s] += 1

        if amounts:
            docs_with_amounts += 1

        # Create items: one per amount × sector combination
        # If no specific sector matched, still record the amount with sector=NULL
        if amounts:
            if sectors:
                for amt in amounts:
                    for sector in sectors:
                        all_items.append({
                            "document_id": doc_id,
                            "sector": sector,
                            **amt,
                        })
            else:
                for amt in amounts:
                    all_items.append({
                        "document_id": doc_id,
                        "sector": None,
                        **amt,
                    })

            for amt in amounts:
                amount_stats["total_wan"] += amt["amount_value"]
                amount_stats["count"] += 1

    # Report
    print(f"\n--- Extraction Results ---")
    print(f"Documents with amounts: {docs_with_amounts} / {len(docs)}")
    print(f"Total amount items: {amount_stats['count']}")
    print(f"Total value: {amount_stats['total_wan']:,.0f} 万元 ({amount_stats['total_wan'] / 10000:,.1f} 亿元)")
    print(f"Subsidy items (amount × sector): {len(all_items)}")
    print(f"\nTop sectors by document count:")
    for sector, count in sector_counts.most_common(15):
        print(f"  {sector}: {count} docs")

    if not dry_run and all_items:
        create_table(conn)
        conn.execute("DELETE FROM subsidy_items")
        conn.executemany(
            "INSERT INTO subsidy_items (document_id, amount_value, amount_raw, amount_context, sector) "
            "VALUES (?, ?, ?, ?, ?)",
            [(i["document_id"], i["amount_value"], i["amount_raw"],
              i["amount_context"], i["sector"]) for i in all_items]
        )
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM subsidy_items").fetchone()[0]
        print(f"\nSaved {count:,} subsidy items to database")

    return all_items


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract subsidy data from documents")
    parser.add_argument("--dry-run", action="store_true", help="Show stats without saving")
    parser.add_argument("--force", action="store_true", help="Drop and rebuild subsidy_items")
    args = parser.parse_args()

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")

    if args.force:
        conn.execute("DROP TABLE IF EXISTS subsidy_items")
        conn.commit()

    extract_all(conn, dry_run=args.dry_run)
    conn.close()
