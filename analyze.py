"""
China Governance Document Analyzer
Cross-reference analysis, document statistics, and keyword analysis.

Usage:
    python3 analyze.py                      # Full analysis report
    python3 analyze.py --cross-refs         # Cross-reference analysis only
    python3 analyze.py --top-cited N        # Top N most-cited documents
    python3 analyze.py --keyword KEYWORD    # Search documents by keyword
"""

import argparse
import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "documents.db"

# ---------------------------------------------------------------------------
# Citation extraction patterns
# ---------------------------------------------------------------------------

# Formal 文号 references: Chinese chars + bracket + year + bracket + number + 号
REF_PATTERN = re.compile(
    r"([\u4e00-\u9fff]+[\u3014\u3008\u300a\uff08\u2018\u301a]"
    r"(?:19|20)\d{2}"
    r"[\u3015\u3009\u300b\uff09\u2019\u301b]"
    r"\d+\u53f7)"
)

# Document issuer classification based on document number prefix
# Sorted longest-first so more specific prefixes match before shorter ones
ISSUER_LEVELS = {
    # Central / State Council
    "国办公开办函": "General Office of State Council",
    "国办发明电": "General Office of State Council",
    "国办发": "General Office of State Council",
    "国办函": "General Office of State Council",
    "国发": "State Council (国务院)",
    "国函": "State Council (国务院)",
    "中办发": "CPC Central Committee Office",
    "中发": "CPC Central Committee",
    # Central ministries
    "发改": "NDRC (National)",
    "国土资厅发": "Ministry of Natural Resources",
    "国土资发": "Ministry of Natural Resources",
    "建市": "Ministry of Housing (MoHURD)",
    "建房": "Ministry of Housing (MoHURD)",
    "建科": "Ministry of Housing (MoHURD)",
    "人社部发": "Ministry of Human Resources",
    "国税发": "State Administration of Taxation",
    "财综": "Ministry of Finance",
    "财预": "Ministry of Finance",
    "财建": "Ministry of Finance",
    "环发": "Ministry of Ecology & Environment",
    "银监发": "Banking & Insurance Commission",
    "工信部联企业": "Ministry of Industry & IT",
    "水资源": "Ministry of Water Resources",
    # Guangdong province
    "粤府办": "Guangdong Provincial Office",
    "粤府函": "Guangdong Provincial Government",
    "粤府": "Guangdong Provincial Government",
    "粤办发": "Guangdong Provincial Office",
    "粤办函": "Guangdong Provincial Office",
    "粤财综": "Guangdong Finance Dept",
    "粤财金": "Guangdong Finance Dept",
    "粤价": "Guangdong Pricing Bureau",
    "粤发": "Guangdong Provincial Party Committee",
    "粤卫": "Guangdong Health Commission",
    "粤环发": "Guangdong Ecology & Environment",
    # Shenzhen municipal
    "深府办规": "Shenzhen Municipal Office (Normative)",
    "深府办函": "Shenzhen Municipal Office (Letter)",
    "深府办": "Shenzhen Municipal Office",
    "深府规": "Shenzhen Municipal (Normative)",
    "深府函": "Shenzhen Municipal (Letter)",
    "深府": "Shenzhen Municipal Government",
    "深发": "Shenzhen CPC Committee",
    "深办发": "Shenzhen CPC Committee Office",
    "深办": "Shenzhen CPC Committee Office",
    "深规土": "Shenzhen Planning & Natural Resources",
    "深建规": "Shenzhen Housing & Construction",
    "深市监规": "Shenzhen Market Supervision",
    "深前海": "Qianhai Authority",
    "深人": "Shenzhen Human Resources",
    # Shenzhen districts
    "深坪": "Pingshan District",
    "深光": "Guangming District",
    "深福": "Futian District",
    "深南": "Nanshan District",
    "深龙": "Longgang/Longhua District",
    "深宝": "Bao'an District",
    "深盐": "Yantian District",
    "深罗": "Luohu District",
    # Meta-prefixes (appearing in "依据..." = "pursuant to...")
    "依据粤府": "Guangdong Provincial Government",
    "依据国发": "State Council (国务院)",
    "依照国发": "State Council (国务院)",
}


def classify_issuer(doc_number: str) -> str:
    """Classify a document number by its issuing authority level."""
    # Sort by key length descending so more specific prefixes match first
    for prefix, label in sorted(ISSUER_LEVELS.items(), key=lambda x: -len(x[0])):
        if doc_number.startswith(prefix):
            return label
    # Try to infer from Chinese characters before the bracket
    match = re.match(r"([\u4e00-\u9fff]+)", doc_number)
    if match:
        return match.group(1)
    return "Unknown"


def get_admin_level(doc_number: str) -> str:
    """Classify document as central, provincial, municipal, or district."""
    # Strip meta-prefixes like "依据" and "依照"
    clean = doc_number
    for meta in ("依据", "依照"):
        if clean.startswith(meta):
            clean = clean[len(meta):]

    central_prefixes = [
        "国发", "国办", "国函", "中发", "中办", "发改", "国土资", "建市", "建房",
        "建科", "人社部", "国税", "财综", "财预", "财建", "环发", "银监",
        "工信部", "水资源",
    ]
    provincial_prefixes = ["粤府", "粤办", "粤财", "粤价", "粤发", "粤卫", "粤环"]
    municipal_prefixes = [
        "深府", "深发", "深办", "深市", "深人", "深规土", "深建", "深前海",
    ]
    district_prefixes = ["深坪", "深福", "深南", "深龙", "深宝", "深盐", "深光", "深罗"]

    if any(clean.startswith(p) for p in central_prefixes):
        return "central"
    elif any(clean.startswith(p) for p in provincial_prefixes):
        return "provincial"
    elif any(clean.startswith(p) for p in municipal_prefixes):
        return "municipal"
    elif any(clean.startswith(p) for p in district_prefixes):
        return "district"
    return "unknown"


# Named 《》 references (policy documents cited by name)
NAMED_REF_PATTERN = re.compile(r"《([^》]{8,100})》")

POLICY_KEYWORDS = [
    "方案", "措施", "意见", "通知", "规定", "规划", "条例", "办法",
    "纲要", "计划", "指南", "指引", "行动", "决定", "公告", "细则",
    "制度", "标准", "清单",
]

EXCLUDE_KEYWORDS = [
    "白皮书", "报告", "讲话", "文章", "演讲", "论文",
]


def is_policy_document(name: str) -> bool:
    """Check if a named reference looks like a policy document."""
    if any(k in name for k in EXCLUDE_KEYWORDS):
        return False
    return any(k in name for k in POLICY_KEYWORDS)


def classify_named_ref_level(name: str) -> str:
    """Guess the administrative level of a named 《》 reference."""
    if any(k in name for k in ["国务院", "国家", "全国", "中共中央", "教育部", "科技部",
                                 "工信部", "教育强国", "中小学"]):
        return "central"
    if any(k in name for k in ["广东省", "省"]):
        return "provincial"
    if any(k in name for k in ["深圳市"]) and not any(
        k in name for k in ["龙华", "南山", "坪山", "福田", "罗湖", "宝安", "盐田", "光明", "龙岗", "大鹏"]
    ):
        return "municipal"
    if any(k in name for k in ["龙华", "南山", "坪山", "福田", "罗湖", "宝安", "盐田", "光明", "龙岗", "大鹏"]):
        return "district"
    if "深圳" in name and "区" not in name:
        return "municipal"
    return "unknown"


def analyze_cross_references(conn: sqlite3.Connection, top_n: int = 20):
    """Analyze which documents are most frequently cited."""
    rows = conn.execute(
        "SELECT id, title, document_number, site_key, body_text_cn, publisher "
        "FROM documents WHERE body_text_cn != ''"
    ).fetchall()

    print(f"\n{'='*70}")
    print(f"CROSS-REFERENCE ANALYSIS")
    print(f"{'='*70}")
    print(f"Analyzing {len(rows)} documents with body text\n")

    # Extract all cross-references
    all_refs = []
    ref_sources = defaultdict(list)  # ref -> list of (doc_id, doc_title)

    for doc_id, title, doc_num, site_key, body, publisher in rows:
        refs = REF_PATTERN.findall(body)
        for ref in refs:
            all_refs.append(ref)
            ref_sources[ref].append((doc_id, title[:60]))

    print(f"Documents containing cross-references: "
          f"{len([r for r in rows if REF_PATTERN.search(r[4])])}/{len(rows)} "
          f"({len([r for r in rows if REF_PATTERN.search(r[4])])/len(rows)*100:.0f}%)")
    print(f"Total cross-references found: {len(all_refs)}")

    # Top cited documents
    top_cited = Counter(all_refs).most_common(top_n)
    print(f"\n--- Top {top_n} Most Cited Documents ---\n")
    for i, (ref, count) in enumerate(top_cited, 1):
        level = get_admin_level(ref)
        issuer = classify_issuer(ref)
        print(f"  {i:2d}. {ref} ({count} citations)")
        print(f"      Level: {level} | Issuer: {issuer}")
        # Show which documents cite this
        sources = ref_sources[ref][:3]
        for src_id, src_title in sources:
            print(f"      ← cited by: {src_title}")
        if len(ref_sources[ref]) > 3:
            print(f"      ... and {len(ref_sources[ref])-3} more")

    # Breakdown by administrative level
    level_counts = defaultdict(int)
    for ref in all_refs:
        level_counts[get_admin_level(ref)] += 1

    print(f"\n--- Citations by Administrative Level ---\n")
    for level, count in sorted(level_counts.items(), key=lambda x: -x[1]):
        pct = count / len(all_refs) * 100
        bar = "█" * int(pct / 2)
        print(f"  {level:12s}: {count:4d} ({pct:4.1f}%) {bar}")

    return top_cited, level_counts


def analyze_categories(conn: sqlite3.Connection):
    """Show document counts by category."""
    print(f"\n{'='*70}")
    print(f"DOCUMENT CATEGORIES")
    print(f"{'='*70}\n")

    rows = conn.execute(
        "SELECT classify_main_name, classify_genre_name, classify_theme_name, COUNT(*) "
        "FROM documents "
        "GROUP BY classify_main_name "
        "ORDER BY COUNT(*) DESC"
    ).fetchall()

    for main, genre, theme, count in rows[:20]:
        if main:
            print(f"  {main}: {count}")


def analyze_timeline(conn: sqlite3.Connection):
    """Show document publication timeline."""
    print(f"\n{'='*70}")
    print(f"PUBLICATION TIMELINE")
    print(f"{'='*70}\n")

    rows = conn.execute(
        "SELECT date_written, COUNT(*) "
        "FROM documents "
        "WHERE date_written > 0 "
        "GROUP BY strftime('%Y', date_written, 'unixepoch') "
        "ORDER BY date_written"
    ).fetchall()

    # Recount by year
    year_counts = defaultdict(int)
    all_rows = conn.execute(
        "SELECT date_written FROM documents WHERE date_written > 0"
    ).fetchall()
    for (ts,) in all_rows:
        try:
            year = datetime.fromtimestamp(ts).year
            if 2015 <= year <= 2030:
                year_counts[year] += 1
        except (ValueError, OSError):
            pass

    for year in sorted(year_counts.keys()):
        count = year_counts[year]
        bar = "█" * (count // 10)
        print(f"  {year}: {count:5d} {bar}")


def search_documents(conn: sqlite3.Connection, keyword: str):
    """Search documents by keyword in title or body text."""
    print(f"\n{'='*70}")
    print(f"SEARCH: '{keyword}'")
    print(f"{'='*70}\n")

    rows = conn.execute(
        "SELECT id, title, document_number, publisher, date_published, site_key "
        "FROM documents "
        "WHERE title LIKE ? OR body_text_cn LIKE ? OR keywords LIKE ? "
        "ORDER BY date_written DESC "
        "LIMIT 20",
        (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"),
    ).fetchall()

    print(f"Found {len(rows)} results (showing up to 20)\n")
    for doc_id, title, doc_num, publisher, date_pub, site_key in rows:
        doc_str = f" [{doc_num}]" if doc_num else ""
        print(f"  {title[:70]}{doc_str}")
        print(f"    Publisher: {publisher} | Date: {date_pub} | Site: {site_key}")
        print()


def resolve_citations(conn: sqlite3.Connection, top_n: int = 30):
    """Match cited document numbers against documents in our corpus."""
    # Build lookup: document_number -> (title, site_key, publisher)
    known_docs = {}
    for doc_num, title, site_key, publisher in conn.execute(
        "SELECT document_number, title, site_key, publisher "
        "FROM documents WHERE document_number != ''"
    ).fetchall():
        known_docs[doc_num] = (title, site_key, publisher)

    # Get all citations
    rows = conn.execute(
        "SELECT body_text_cn FROM documents WHERE body_text_cn != ''"
    ).fetchall()
    all_refs = []
    for (body,) in rows:
        all_refs.extend(REF_PATTERN.findall(body))

    ref_counts = Counter(all_refs)

    print(f"\n{'='*70}")
    print(f"CITATION RESOLUTION — Matching citations to corpus")
    print(f"{'='*70}")
    print(f"Total unique citations: {len(ref_counts)}")
    print(f"Documents with 文号 in corpus: {len(known_docs)}\n")

    resolved = 0
    print("--- Top Citations Resolved to Known Documents ---\n")
    for ref, count in ref_counts.most_common(top_n):
        if ref in known_docs:
            title, site_key, publisher = known_docs[ref]
            resolved += 1
            print(f"  {ref} ({count} citations) → FOUND")
            print(f"    Title: {title[:70]}")
            print(f"    Site: {site_key} | Publisher: {publisher}")

    total_resolved = sum(1 for ref in ref_counts if ref in known_docs)
    print(f"\n--- Resolution Rate ---")
    print(f"  Unique citations resolved: {total_resolved}/{len(ref_counts)} "
          f"({total_resolved/len(ref_counts)*100:.0f}%)")
    print(f"  (Remaining are external documents not in our Shenzhen corpus)")


def analyze_citation_network(conn: sqlite3.Connection):
    """Analyze the citation network: which sites/departments cite which levels."""
    rows = conn.execute(
        "SELECT id, title, site_key, body_text_cn, publisher "
        "FROM documents WHERE body_text_cn != ''"
    ).fetchall()

    print(f"\n{'='*70}")
    print(f"CITATION NETWORK ANALYSIS")
    print(f"{'='*70}")
    print(f"Analyzing citation patterns across {len(rows)} documents\n")

    # Build: site_key -> {admin_level -> count}
    site_names = dict(conn.execute("SELECT site_key, name FROM sites").fetchall())
    site_cites_level = defaultdict(lambda: defaultdict(int))
    site_total_refs = defaultdict(int)

    for doc_id, title, site_key, body, publisher in rows:
        refs = REF_PATTERN.findall(body)
        for ref in refs:
            level = get_admin_level(ref)
            site_cites_level[site_key][level] += 1
            site_total_refs[site_key] += 1

    print("--- Which levels does each site cite? ---\n")
    print(f"  {'Site':<35s} {'Central':>8s} {'Provincial':>11s} {'Municipal':>10s} {'District':>9s} {'Unknown':>8s} {'Total':>6s}")
    print(f"  {'-'*35} {'-'*8} {'-'*11} {'-'*10} {'-'*9} {'-'*8} {'-'*6}")
    for site_key in sorted(site_cites_level.keys(), key=lambda k: -site_total_refs[k]):
        name = site_names.get(site_key, site_key)[:35]
        levels = site_cites_level[site_key]
        total = site_total_refs[site_key]
        print(f"  {name:<35s} {levels['central']:>8d} {levels['provincial']:>11d} "
              f"{levels['municipal']:>10d} {levels['district']:>9d} {levels['unknown']:>8d} {total:>6d}")

    # Top central documents cited by local departments
    print(f"\n--- Top Central Government Documents Cited by Local Departments ---\n")
    central_refs = defaultdict(list)
    for doc_id, title, site_key, body, publisher in rows:
        refs = REF_PATTERN.findall(body)
        for ref in refs:
            if get_admin_level(ref) == "central":
                central_refs[ref].append((site_key, title[:50]))

    for ref, sources in sorted(central_refs.items(), key=lambda x: -len(x[1]))[:15]:
        issuer = classify_issuer(ref)
        sites_citing = set(s[0] for s in sources)
        print(f"  {ref} ({len(sources)} citations from {len(sites_citing)} sites)")
        print(f"    Issuer: {issuer}")
        for sk in sorted(sites_citing):
            print(f"    - {site_names.get(sk, sk)}")


def full_report(conn: sqlite3.Connection):
    """Generate a full analysis report."""
    # Basic stats
    total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    with_body = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE body_text_cn != ''"
    ).fetchone()[0]
    with_docnum = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE document_number != ''"
    ).fetchone()[0]

    print(f"\n{'='*70}")
    print(f"CHINA GOVERNANCE DOCUMENT CORPUS — ANALYSIS REPORT")
    print(f"{'='*70}")
    print(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"\n--- Corpus Statistics ---\n")
    print(f"  Total documents: {total}")
    print(f"  With body text: {with_body}")
    print(f"  With document number (文号): {with_docnum}")

    # Per-site stats
    sites = conn.execute("SELECT site_key, name FROM sites").fetchall()
    print(f"\n--- By Site ---\n")
    for key, name in sites:
        count = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE site_key = ?", (key,)
        ).fetchone()[0]
        bodies = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE site_key = ? AND body_text_cn != ''",
            (key,),
        ).fetchone()[0]
        print(f"  {name}: {count} docs ({bodies} with body text)")

    # Category breakdown
    analyze_categories(conn)

    # Timeline
    analyze_timeline(conn)

    # Cross-references (only if we have body text)
    if with_body > 0:
        analyze_cross_references(conn)
        analyze_citation_network(conn)


def main():
    parser = argparse.ArgumentParser(description="China Governance Document Analyzer")
    parser.add_argument("--cross-refs", action="store_true", help="Cross-reference analysis")
    parser.add_argument("--top-cited", type=int, default=20, help="Number of top-cited docs to show")
    parser.add_argument("--keyword", type=str, help="Search by keyword")
    parser.add_argument("--network", action="store_true", help="Citation network analysis")
    parser.add_argument("--resolve", action="store_true", help="Resolve citations to corpus documents")
    args = parser.parse_args()

    conn = sqlite3.connect(str(DB_PATH))

    if args.keyword:
        search_documents(conn, args.keyword)
    elif args.cross_refs:
        analyze_cross_references(conn, args.top_cited)
    elif args.network:
        analyze_citation_network(conn)
    elif args.resolve:
        resolve_citations(conn, args.top_cited)
    else:
        full_report(conn)

    conn.close()


if __name__ == "__main__":
    main()
