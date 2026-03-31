#!/usr/bin/env python3
"""
Discover citation gaps: analyze unresolved citations to identify which external
government sources we should crawl next.

Documents in our corpus cite policies (via formal 文号 and named 《》 references)
that we don't have. By analyzing these unresolved citations, we can discover
which government bodies we're missing and prioritize new crawlers.

This is a READ-ONLY analysis script. It does not modify the database.

Usage:
    python3 scripts/discover_citation_gaps.py              # Full analysis
    python3 scripts/discover_citation_gaps.py --top 20     # Top 20 gaps
    python3 scripts/discover_citation_gaps.py --ai-only    # Only AI-related gaps
    python3 scripts/discover_citation_gaps.py --json       # JSON output
"""

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# Import issuer classification functions from analyze.py
sys.path.insert(0, str(Path(__file__).parent.parent))
from analyze import (
    ISSUER_LEVELS,
    classify_issuer,
    get_admin_level,
    classify_named_ref_level,
    REF_PATTERN,
)

DB_PATH = Path(__file__).parent.parent / "documents.db"

# ---------------------------------------------------------------------------
# Known crawled sources — maps issuing body labels to site_keys we already have.
# This lets us distinguish "we cite X but don't crawl it" from
# "we cite X and already have a crawler for it."
# ---------------------------------------------------------------------------
CRAWLED_ISSUERS = {
    # Central
    "State Council": ["gov"],
    "General Office of State Council": ["gov"],
    "NDRC (National)": ["ndrc"],
    "Ministry of Finance": ["mof"],
    "Ministry of Ecology & Environment": ["mee"],
    "Ministry of Industry & IT": ["miit"],
    "Ministry of Science and Technology": ["most"],
    "Cyberspace Administration of China": ["cac"],
    "Ministry of Commerce": ["mofcom"],
    "State Administration for Market Regulation": ["samr"],
    "National Data Administration": ["nda"],
    # Provincial
    "Guangdong Provincial Government": ["gd"],
    "Guangdong Provincial Office": ["gd"],
    "Guangdong Provincial Party Committee": ["gd"],
    "Beijing Municipality": ["bj"],
    "Shanghai Municipality": ["sh"],
    "Jiangsu Province": ["js"],
    "Zhejiang Province": ["zj"],
    "Chongqing Municipality": ["cq"],
    # Municipal
    "Shenzhen Municipal Government": ["sz"],
    "Shenzhen Municipal Office": ["sz"],
    "Shenzhen Municipal Office (Normative)": ["sz"],
    "Shenzhen Municipal Office (Letter)": ["sz"],
    "Shenzhen Municipal (Normative)": ["sz"],
    "Shenzhen Municipal (Letter)": ["sz"],
    "Shenzhen CPC Committee": ["sz"],
    "Shenzhen CPC Committee Office": ["sz"],
    "Shenzhen Planning & Natural Resources": ["sz"],
    "Shenzhen Housing & Construction": ["zjj"],
    "Shenzhen Market Supervision": ["sz"],
    "Qianhai Authority": ["sz"],
    "Shenzhen Human Resources": ["hrss"],
    # Shenzhen departments
    "Shenzhen S&T Innovation": ["stic"],
    "Shenzhen DRC": ["fgw"],
    # Shenzhen districts
    "Pingshan District": ["szpsq"],
    "Guangming District": ["szgm"],
    "Futian District": ["szft"],
    "Nanshan District": ["szns"],
    "Longgang/Longhua District": ["szlg", "szlhq"],
    "Luohu District": ["szlh"],
    "Bao'an District": ["szba"],
    "Yantian District": ["szyantian"],
}

# Extended issuer prefix map for prefixes not in analyze.py ISSUER_LEVELS.
# These map Chinese prefixes to readable issuing body names.
EXTRA_ISSUER_PREFIXES = {
    # Other provinces
    "京政": "Beijing Municipal Government",
    "京政办": "Beijing Municipal Office",
    "京发": "Beijing Municipal Party Committee",
    "沪府": "Shanghai Municipal Government",
    "沪府办": "Shanghai Municipal Office",
    "苏政": "Jiangsu Provincial Government",
    "苏政办": "Jiangsu Provincial Office",
    "浙政": "Zhejiang Provincial Government",
    "浙政办": "Zhejiang Provincial Office",
    "渝府": "Chongqing Municipal Government",
    "渝府办": "Chongqing Municipal Office",
    "川府": "Sichuan Provincial Government",
    "川府发": "Sichuan Provincial Government",
    "川办发": "Sichuan Provincial Office",
    "鲁政": "Shandong Provincial Government",
    "鲁政办": "Shandong Provincial Office",
    "豫政": "Henan Provincial Government",
    "豫政办": "Henan Provincial Office",
    "鄂政": "Hubei Provincial Government",
    "鄂政办": "Hubei Provincial Office",
    "湘政": "Hunan Provincial Government",
    "湘政办": "Hunan Provincial Office",
    "皖政": "Anhui Provincial Government",
    "皖政办": "Anhui Provincial Office",
    "闽政": "Fujian Provincial Government",
    "闽政办": "Fujian Provincial Office",
    "赣政": "Jiangxi Provincial Government",
    "桂政": "Guangxi Government",
    "琼府": "Hainan Provincial Government",
    "云政": "Yunnan Provincial Government",
    "黔府": "Guizhou Provincial Government",
    "藏政": "Tibet Government",
    "陕政": "Shaanxi Provincial Government",
    "甘政": "Gansu Provincial Government",
    "宁政": "Ningxia Government",
    "青政": "Qinghai Provincial Government",
    "新政": "Xinjiang Government",
    "蒙政": "Inner Mongolia Government",
    "黑政": "Heilongjiang Provincial Government",
    "吉政": "Jilin Provincial Government",
    "辽政": "Liaoning Provincial Government",
    "津政": "Tianjin Municipal Government",
    # Other municipalities
    "穗府": "Guangzhou Municipal Government",
    "穗": "Guangzhou Municipal Government",
    "珠府": "Zhuhai Municipal Government",
    "珠府办": "Zhuhai Municipal Office",
    "惠府": "Huizhou Municipal Government",
    "惠府办": "Huizhou Municipal Office",
    "江府": "Jiangmen Municipal Government",
    "中府": "Zhongshan Municipal Government",
    "中府办": "Zhongshan Municipal Office",
    "汕府": "Shantou Municipal Government",
    "肇府": "Zhaoqing Municipal Government",
    "韶府": "Shaoguan Municipal Government",
    "韶市": "Shaoguan Municipal Government",
    "河府": "Heyuan Municipal Government",
    "汕尾": "Shanwei Municipal Government",
    "阳府": "Yangjiang Municipal Government",
    "湛府": "Zhanjiang Municipal Government",
    "潮府": "Chaozhou Municipal Government",
    "揭府": "Jieyang Municipal Government",
    "云府": "Yunfu Municipal Government",
    "云府办": "Yunfu Municipal Office",
    "成府": "Chengdu Municipal Government",
    "杭政": "Hangzhou Municipal Government",
    "宁政办": "Ningbo Municipal Office",
    "武政": "Wuhan Municipal Government",
    # Central ministries not in ISSUER_LEVELS
    "教育部": "Ministry of Education",
    "交通运输部": "Ministry of Transport",
    "自然资源部": "Ministry of Natural Resources",
    "住建部": "Ministry of Housing (MoHURD)",
    "科技部": "Ministry of Science and Technology",
    "商务部": "Ministry of Commerce",
    "国市监": "State Administration for Market Regulation",
    "税总": "State Administration of Taxation",
    "财政部": "Ministry of Finance",
    "国税": "State Administration of Taxation",
    "人行": "People's Bank of China",
    "银发": "People's Bank of China",
    "证监会": "China Securities Regulatory Commission",
    "证监": "China Securities Regulatory Commission",
    "国资委": "SASAC",
    # Guangdong departments not in ISSUER_LEVELS
    "粤财规": "Guangdong Finance Dept",
    "粤财社": "Guangdong Finance Dept",
    "粤人社": "Guangdong Human Resources Dept",
    "粤教基": "Guangdong Education Dept",
    "粤教": "Guangdong Education Dept",
    "粤交": "Guangdong Transport Dept",
    "粤自然资": "Guangdong Natural Resources Dept",
    "粤国土资": "Guangdong Natural Resources Dept",
    "粤建": "Guangdong Housing & Construction Dept",
    "粤司": "Guangdong Justice Dept",
    "粤市监": "Guangdong Market Supervision",
    "粤科": "Guangdong S&T Dept",
    "粤工信": "Guangdong Industry & IT Dept",
    "粤水利": "Guangdong Water Resources Dept",
    "粤农": "Guangdong Agriculture Dept",
    # Shenzhen departments not in ISSUER_LEVELS
    "深财规": "Shenzhen Finance Bureau",
    "深财": "Shenzhen Finance Bureau",
    "深科技创新规": "Shenzhen S&T Innovation Bureau",
    "深科技创新": "Shenzhen S&T Innovation Bureau",
    "深税": "Shenzhen Tax Bureau",
    "深医保": "Shenzhen Medical Insurance Bureau",
    "深交": "Shenzhen Transport Bureau",
    "深生态环境": "Shenzhen Ecology & Environment Bureau",
    "深市场监管": "Shenzhen Market Supervision Bureau",
    "深水务": "Shenzhen Water Bureau",
    "深城管": "Shenzhen Urban Management Bureau",
    "深工信": "Shenzhen Industry & IT Bureau",
    "深商务": "Shenzhen Commerce Bureau",
    "深统计": "Shenzhen Statistics Bureau",
    "深应急": "Shenzhen Emergency Management Bureau",
}

# Keywords in named 《》 references that suggest an issuing body
NAMED_REF_BODY_KEYWORDS = {
    # Central
    "中华人民共和国": ("central", "National Law"),
    "国务院": ("central", "State Council"),
    "国家": ("central", "National-level Body"),
    "全国人大": ("central", "National People's Congress"),
    "中共中央": ("central", "CPC Central Committee"),
    "教育部": ("central", "Ministry of Education"),
    "科技部": ("central", "Ministry of Science and Technology"),
    "工信部": ("central", "Ministry of Industry & IT"),
    "财政部": ("central", "Ministry of Finance"),
    "住房和城乡建设部": ("central", "Ministry of Housing (MoHURD)"),
    "住建部": ("central", "Ministry of Housing (MoHURD)"),
    "自然资源部": ("central", "Ministry of Natural Resources"),
    "交通运输部": ("central", "Ministry of Transport"),
    "商务部": ("central", "Ministry of Commerce"),
    # Provincial
    "广东省": ("provincial", "Guangdong Provincial Government"),
    # Municipal
    "深圳市": ("municipal", "Shenzhen Municipal Government"),
    "深圳经济特区": ("municipal", "Shenzhen Municipal Government"),
    "广州市": ("municipal", "Guangzhou Municipal Government"),
    "珠海市": ("municipal", "Zhuhai Municipal Government"),
    "惠州市": ("municipal", "Huizhou Municipal Government"),
    "佛山市": ("municipal", "Foshan Municipal Government"),
    "东莞市": ("municipal", "Dongguan Municipal Government"),
    "中山市": ("municipal", "Zhongshan Municipal Government"),
    "江门市": ("municipal", "Jiangmen Municipal Government"),
    "北京市": ("municipal", "Beijing Municipal Government"),
    "上海市": ("municipal", "Shanghai Municipal Government"),
    "重庆市": ("municipal", "Chongqing Municipal Government"),
    "武汉市": ("municipal", "Wuhan Municipal Government"),
    "成都市": ("municipal", "Chengdu Municipal Government"),
    "杭州市": ("municipal", "Hangzhou Municipal Government"),
    # District
    "龙华区": ("district", "Longhua District"),
    "南山区": ("district", "Nanshan District"),
    "福田区": ("district", "Futian District"),
    "坪山区": ("district", "Pingshan District"),
    "宝安区": ("district", "Bao'an District"),
    "龙岗区": ("district", "Longgang District"),
    "罗湖区": ("district", "Luohu District"),
    "盐田区": ("district", "Yantian District"),
    "光明区": ("district", "Guangming District"),
    "大鹏新区": ("district", "Dapeng New District"),
}

# AI-related keywords for --ai-only filter
AI_KEYWORDS_CN = [
    "人工智能", "机器人", "算力", "大模型", "智能制造", "数字经济",
    "数据要素", "智算", "芯片", "半导体", "集成电路", "AI",
    "区块链", "量子", "元宇宙", "自动驾驶", "智能网联",
    "深度学习", "机器学习", "计算机视觉", "自然语言处理",
]


def classify_issuer_extended(ref: str) -> str:
    """Extended issuer classification using both analyze.py and our extra prefixes."""
    # First try analyze.py's classify_issuer
    result = classify_issuer(ref)
    if result != "Unknown" and not re.match(r'^[\u4e00-\u9fff]+$', result):
        # classify_issuer returned a known label (not just raw Chinese prefix)
        return result

    # Try our extended prefixes (longest match first)
    for prefix, label in sorted(EXTRA_ISSUER_PREFIXES.items(), key=lambda x: -len(x[0])):
        if ref.startswith(prefix):
            return label

    # If classify_issuer returned the raw Chinese prefix, use that
    if result != "Unknown":
        return result

    return "Unknown"


def infer_level_from_issuer(issuer_label: str) -> str:
    """Infer admin level from an issuer label when get_admin_level returns unknown."""
    label_lower = issuer_label.lower()
    if any(kw in label_lower for kw in [
        "state council", "ministry", "national", "cpc central",
        "people's bank", "commission", "sasac", "administration",
    ]):
        return "central"
    if any(kw in label_lower for kw in ["provincial", "province"]):
        return "provincial"
    if any(kw in label_lower for kw in ["municipal", "municipality"]):
        return "municipal"
    if any(kw in label_lower for kw in ["district"]):
        return "district"
    # Check for Guangdong dept patterns
    if "guangdong" in label_lower or "gd " in label_lower:
        return "provincial"
    if "shenzhen" in label_lower or "sz " in label_lower:
        return "municipal"
    return "unknown"


def classify_named_ref_body(name: str) -> tuple:
    """Classify a named 《》 reference by its likely issuing body.

    Returns (admin_level, body_name) or ("unknown", "Unknown").
    """
    for keyword, (level, body) in sorted(
        NAMED_REF_BODY_KEYWORDS.items(), key=lambda x: -len(x[0])
    ):
        if keyword in name:
            return level, body
    return "unknown", "Unknown"


def is_crawled_issuer(issuer_label: str) -> bool:
    """Check if we already crawl documents from this issuing body."""
    # Direct match
    if issuer_label in CRAWLED_ISSUERS:
        return True
    # Partial match (e.g., "Guangdong Finance Dept" ~ "Guangdong")
    for crawled in CRAWLED_ISSUERS:
        if crawled in issuer_label or issuer_label in crawled:
            return True
    return False


def run_analysis(conn: sqlite3.Connection, top_n: int = 30,
                 ai_only: bool = False, output_json: bool = False):
    """Main analysis: find and rank unresolved citation gaps."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ----- Stats overview -----
    total_citations = conn.execute("SELECT COUNT(*) FROM citations").fetchone()[0]
    resolved = conn.execute(
        "SELECT COUNT(*) FROM citations WHERE target_id IS NOT NULL"
    ).fetchone()[0]
    unresolved = conn.execute(
        "SELECT COUNT(*) FROM citations WHERE target_id IS NULL"
    ).fetchone()[0]
    unresolved_formal = conn.execute(
        "SELECT COUNT(*) FROM citations WHERE target_id IS NULL AND citation_type = 'formal'"
    ).fetchone()[0]
    unresolved_named = conn.execute(
        "SELECT COUNT(*) FROM citations WHERE target_id IS NULL AND citation_type = 'named'"
    ).fetchone()[0]
    unresolved_llm = conn.execute(
        "SELECT COUNT(*) FROM citations WHERE target_id IS NULL AND citation_type = 'llm'"
    ).fetchone()[0]
    total_docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]

    # ----- Fetch unresolved citations -----
    # For formal refs: get target_ref, source_id, citation_type
    # For AI-only: also join to source document to check topics/title
    if ai_only:
        rows = conn.execute("""
            SELECT c.target_ref, c.citation_type, c.source_level, c.target_level,
                   d.title, d.topics, d.title_en
            FROM citations c
            JOIN documents d ON c.source_id = d.id
            WHERE c.target_id IS NULL
        """).fetchall()
    else:
        rows = conn.execute("""
            SELECT c.target_ref, c.citation_type, c.source_level, c.target_level,
                   '', '', ''
            FROM citations c
            WHERE c.target_id IS NULL
        """).fetchall()

    # ----- Apply AI filter if requested -----
    if ai_only:
        filtered = []
        for ref, ctype, slvl, tlvl, title, topics, title_en in rows:
            # Check if the source document or the cited reference relates to AI
            searchable = f"{title} {topics or ''} {title_en or ''} {ref}"
            if any(kw in searchable for kw in AI_KEYWORDS_CN):
                filtered.append((ref, ctype, slvl, tlvl, title, topics, title_en))
        rows = filtered

    # ----- Classify each unresolved citation by issuing body -----
    # Group by (issuer_label, admin_level)
    issuer_counts = defaultdict(int)          # issuer_label -> count
    issuer_level = {}                         # issuer_label -> admin_level
    issuer_samples = defaultdict(list)        # issuer_label -> sample refs
    issuer_types = defaultdict(lambda: defaultdict(int))  # issuer -> {formal: N, named: N}

    level_counts = defaultdict(int)           # admin_level -> count

    for ref, ctype, slvl, tlvl, *extra in rows:
        if ctype == "formal":
            issuer = classify_issuer_extended(ref)
            level = get_admin_level(ref) if tlvl == "unknown" else tlvl
            # If get_admin_level doesn't know this prefix, infer from issuer label
            if level == "unknown" and issuer != "Unknown":
                level = infer_level_from_issuer(issuer)
        elif ctype in ("named", "llm"):
            level, issuer = classify_named_ref_body(ref)
            if issuer == "Unknown":
                # Try to use the target_level from the citations table
                level = tlvl if tlvl != "unknown" else "unknown"
                issuer = f"Unknown ({level})" if level != "unknown" else "Unknown"
        else:
            issuer = "Unknown"
            level = tlvl

        issuer_counts[issuer] += 1
        issuer_level[issuer] = level
        issuer_types[issuer][ctype] += 1
        level_counts[level] += 1

        # Keep sample refs (up to 5)
        if len(issuer_samples[issuer]) < 5:
            issuer_samples[issuer].append(ref)

    # ----- Rank by citation count -----
    ranked = sorted(issuer_counts.items(), key=lambda x: -x[1])

    # ----- Cross-reference with our crawler list -----
    gaps = []       # (issuer, count, level, is_crawled, samples, type_breakdown)
    for issuer, count in ranked:
        level = issuer_level.get(issuer, "unknown")
        crawled = is_crawled_issuer(issuer)
        samples = issuer_samples[issuer]
        type_bd = dict(issuer_types[issuer])
        gaps.append({
            "issuer": issuer,
            "count": count,
            "level": level,
            "crawled": crawled,
            "samples": samples,
            "types": type_bd,
        })

    # ----- Also compute top individual unresolved refs -----
    ref_counter = Counter()
    for ref, ctype, slvl, tlvl, *extra in rows:
        ref_counter[ref] += 1
    top_refs = ref_counter.most_common(top_n)

    # ----- JSON output -----
    if output_json:
        output = {
            "generated": now,
            "ai_only": ai_only,
            "stats": {
                "total_citations": total_citations,
                "resolved": resolved,
                "unresolved": unresolved,
                "unresolved_formal": unresolved_formal,
                "unresolved_named": unresolved_named,
                "unresolved_llm": unresolved_llm,
                "total_documents": total_docs,
                "filtered_unresolved": len(rows) if ai_only else unresolved,
            },
            "gaps_by_issuer": gaps[:top_n],
            "top_unresolved_refs": [
                {"ref": ref, "count": cnt} for ref, cnt in top_refs
            ],
            "by_level": dict(level_counts),
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    # ----- Human-readable report -----
    filter_label = " (AI-related only)" if ai_only else ""
    print(f"\n{'=' * 78}")
    print(f"  CITATION GAP ANALYSIS{filter_label}")
    print(f"  Generated: {now}")
    print(f"{'=' * 78}")

    print(f"\n--- Corpus Overview ---\n")
    print(f"  Total documents in corpus:    {total_docs:>8,}")
    print(f"  Total citations:              {total_citations:>8,}")
    print(f"  Resolved (in corpus):         {resolved:>8,}  "
          f"({resolved * 100 / max(total_citations, 1):.1f}%)")
    print(f"  Unresolved (NOT in corpus):   {unresolved:>8,}  "
          f"({unresolved * 100 / max(total_citations, 1):.1f}%)")
    print(f"    - formal (文号):            {unresolved_formal:>8,}")
    print(f"    - named (《》):              {unresolved_named:>8,}")
    if unresolved_llm:
        print(f"    - llm-extracted:            {unresolved_llm:>8,}")

    if ai_only:
        print(f"\n  After AI filter:              {len(rows):>8,} unresolved citations")

    # --- By admin level ---
    print(f"\n--- Unresolved Citations by Target Admin Level ---\n")
    for level in ["central", "provincial", "municipal", "district", "unknown"]:
        cnt = level_counts.get(level, 0)
        total_unres = len(rows) if ai_only else unresolved
        pct = cnt * 100 / max(total_unres, 1)
        bar = "#" * int(pct / 2)
        print(f"  {level:12s}  {cnt:>7,}  ({pct:5.1f}%)  {bar}")

    # --- Gap analysis: bodies we DON'T crawl ---
    not_crawled = [g for g in gaps if not g["crawled"] and g["issuer"] != "Unknown"]
    already_crawled = [g for g in gaps if g["crawled"]]

    print(f"\n{'=' * 78}")
    print(f"  PRIORITY GAPS: Sources Cited but NOT Crawled (top {top_n})")
    print(f"{'=' * 78}\n")

    if not_crawled:
        print(f"  {'#':>3}  {'Issuing Body':<42} {'Level':<12} {'Citations':>10}")
        print(f"  {'---':>3}  {'-' * 42} {'-' * 12} {'-' * 10}")
        for i, g in enumerate(not_crawled[:top_n], 1):
            print(f"  {i:3d}  {g['issuer']:<42} {g['level']:<12} {g['count']:>10,}")
            # Show citation type breakdown
            type_parts = []
            for t in ["formal", "named", "llm"]:
                if g["types"].get(t, 0) > 0:
                    type_parts.append(f"{t}: {g['types'][t]:,}")
            if type_parts:
                print(f"       Types: {', '.join(type_parts)}")
            # Show sample refs
            for s in g["samples"][:3]:
                display = s if len(s) <= 65 else s[:62] + "..."
                print(f"       e.g. {display}")
            print()
    else:
        print("  (no uncrawled issuers found in unresolved citations)\n")

    # --- Bodies we DO crawl but still have gaps ---
    crawled_with_gaps = [g for g in already_crawled if g["count"] >= 10]
    if crawled_with_gaps:
        print(f"\n--- Sources We Crawl But Still Have Unresolved Refs ---\n")
        print(f"  These may indicate incomplete crawls or department sub-sites.\n")
        print(f"  {'Issuing Body':<42} {'Level':<12} {'Unresolved':>10}")
        print(f"  {'-' * 42} {'-' * 12} {'-' * 10}")
        for g in crawled_with_gaps[:15]:
            print(f"  {g['issuer']:<42} {g['level']:<12} {g['count']:>10,}")

    # --- Top individual unresolved references ---
    print(f"\n{'=' * 78}")
    print(f"  TOP {top_n} MOST-CITED UNRESOLVED REFERENCES")
    print(f"{'=' * 78}\n")

    print(f"  {'#':>3}  {'Citations':>8}  {'Reference'}")
    print(f"  {'---':>3}  {'-' * 8}  {'-' * 60}")
    for i, (ref, cnt) in enumerate(top_refs, 1):
        display = ref if len(ref) <= 60 else ref[:57] + "..."
        print(f"  {i:3d}  {cnt:>8,}  {display}")

    # --- Summary recommendations ---
    print(f"\n{'=' * 78}")
    print(f"  RECOMMENDATIONS")
    print(f"{'=' * 78}\n")

    # Group uncrawled gaps by level
    level_groups = defaultdict(list)
    for g in not_crawled:
        if g["issuer"] != "Unknown" and not g["issuer"].startswith("Unknown ("):
            level_groups[g["level"]].append(g)

    for level in ["central", "provincial", "municipal", "district"]:
        group = level_groups.get(level, [])
        if not group:
            continue
        total_citations_in_group = sum(g["count"] for g in group)
        print(f"  {level.upper()} ({len(group)} bodies, {total_citations_in_group:,} citations):")
        for g in group[:5]:
            print(f"    - {g['issuer']}: {g['count']:,} citations")
        if len(group) > 5:
            print(f"    ... and {len(group) - 5} more")
        print()

    unknowns = [g for g in gaps if g["issuer"] == "Unknown" or g["issuer"].startswith("Unknown (")]
    unknown_total = sum(g["count"] for g in unknowns)
    if unknown_total:
        print(f"  UNCLASSIFIED: {unknown_total:,} citations could not be mapped to a known body.")
        print(f"  These may require manual inspection of the raw 文号 prefixes.\n")

    # Show raw prefix distribution for unknowns
    prefix_counts = Counter()
    for ref, ctype, slvl, tlvl, *extra in rows:
        if ctype == "formal":
            issuer = classify_issuer_extended(ref)
            if issuer == "Unknown":
                # Extract the Chinese prefix
                m = re.match(r"([\u4e00-\u9fff]+)", ref)
                if m:
                    prefix_counts[m.group(1)] += 1

    if prefix_counts:
        print(f"  Top unclassified 文号 prefixes:")
        for prefix, cnt in prefix_counts.most_common(15):
            print(f"    {prefix}: {cnt:,} citations")
        print()

    print(f"{'=' * 78}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Discover citation gaps: which sources should we crawl next?"
    )
    parser.add_argument(
        "--top", type=int, default=30,
        help="Number of top gaps to show (default: 30)"
    )
    parser.add_argument(
        "--ai-only", action="store_true",
        help="Only show gaps related to AI/technology policy"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output results as JSON"
    )
    parser.add_argument(
        "--db", type=str, default=None,
        help="Path to database (default: documents.db)"
    )
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else DB_PATH
    if not db_path.exists():
        print(f"Error: database not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    # Open read-only
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)

    # Check that citations table exists and has data
    try:
        count = conn.execute("SELECT COUNT(*) FROM citations").fetchone()[0]
    except sqlite3.OperationalError:
        print("Error: citations table not found. Run extract_citations.py first.",
              file=sys.stderr)
        sys.exit(1)

    if count == 0:
        print("No citations in database. Run extract_citations.py first.",
              file=sys.stderr)
        sys.exit(1)

    run_analysis(conn, top_n=args.top, ai_only=args.ai_only, output_json=args.json)
    conn.close()


if __name__ == "__main__":
    main()
