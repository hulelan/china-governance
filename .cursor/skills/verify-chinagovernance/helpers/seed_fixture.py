#!/usr/bin/env python3
"""Build a tiny SQLite fixture for local chinagovernance verification.

VERIFICATION SCAFFOLDING — NOT PRODUCTION.
Never copy, rsync, or download production documents.db. This script writes a
handful of synthetic rows so uvicorn can boot with SQLITE_PATH pointed here.

Usage:
    python3 .cursor/skills/verify-chinagovernance/helpers/seed_fixture.py \\
        --out /tmp/verify-chinagovernance-$RUN_ID/fixture.db
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

CST = timezone(timedelta(hours=8))


def ts(year: int, month: int, day: int) -> int:
    return int(datetime(year, month, day, tzinfo=CST).timestamp())


SCHEMA = """
CREATE TABLE sites (
    site_key TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    base_url TEXT NOT NULL,
    admin_level TEXT,
    sid TEXT,
    tree_json TEXT,
    last_crawled TEXT
);

CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    site_key TEXT NOT NULL,
    category_id INTEGER,
    title TEXT NOT NULL,
    document_number TEXT DEFAULT '',
    identifier TEXT DEFAULT '',
    publisher TEXT DEFAULT '',
    keywords TEXT DEFAULT '',
    date_written INTEGER,
    date_published TEXT DEFAULT '',
    display_publish_time INTEGER,
    abstract TEXT DEFAULT '',
    body_text_cn TEXT DEFAULT '',
    body_text_en TEXT DEFAULT '',
    classify_main_name TEXT DEFAULT '',
    classify_genre_name TEXT DEFAULT '',
    classify_theme_name TEXT DEFAULT '',
    url TEXT DEFAULT '',
    post_url TEXT DEFAULT '',
    is_expired INTEGER DEFAULT 0,
    is_abolished INTEGER DEFAULT 0,
    attachments_json TEXT DEFAULT '',
    relation TEXT DEFAULT '',
    raw_html_path TEXT DEFAULT '',
    crawl_timestamp TEXT NOT NULL,
    title_en TEXT DEFAULT '',
    summary_en TEXT DEFAULT '',
    category TEXT DEFAULT '',
    importance TEXT DEFAULT '',
    policy_area TEXT DEFAULT '',
    topics TEXT DEFAULT '[]',
    classification_model TEXT DEFAULT '',
    classified_at TEXT DEFAULT '',
    doc_type TEXT DEFAULT '',
    policy_significance TEXT DEFAULT '',
    references_json TEXT DEFAULT '',
    citation_rank REAL DEFAULT 0,
    algo_doc_type TEXT DEFAULT '',
    ai_relevance REAL DEFAULT 0,
    FOREIGN KEY (site_key) REFERENCES sites(site_key)
);

CREATE TABLE citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    target_ref TEXT NOT NULL,
    target_id INTEGER,
    citation_type TEXT NOT NULL,
    source_level TEXT NOT NULL,
    target_level TEXT NOT NULL,
    UNIQUE(source_id, target_ref, citation_type)
);

-- Marker so doctor refuses a production DB.
CREATE TABLE _verify_scaffold (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

SITES = [
    ("gov", "State Council", "https://www.gov.cn", "central"),
    ("gd", "Guangdong", "https://www.gd.gov.cn", "provincial"),
    ("sz", "Shenzhen", "https://www.sz.gov.cn", "municipal"),
    ("xinhua", "Xinhua", "https://www.news.cn", "media"),
]

# Seeded titles/ids are the Search and Lens fixtures. Keep in sync with
# helpers/drive-search.sh and features/search.md.
DOCS = [
    {
        "id": 1,
        "site_key": "gov",
        "title": '国务院关于深入实施"人工智能+"行动的意见',
        "document_number": "国发〔2025〕11号",
        "publisher": "国务院",
        "date_written": ts(2025, 8, 26),
        "date_published": "2025-08-26",
        "body_text_cn": (
            "各省、自治区、直辖市人民政府，国务院各部委、各直属机构："
            "为深入实施人工智能+行动，推动人工智能赋能千行百业，现提出如下意见。"
            "一、总体要求。二、重点任务。三、保障措施。"
        ),
        "abstract": "中央层面推进人工智能+行动的意见。",
        "url": "https://www.gov.cn/verify/ai-plus",
        "title_en": 'Opinions on Deepening the "AI+" Action',
        "summary_en": "State Council opinions on implementing the AI+ action nationwide.",
        "category": "science_tech",
        "importance": "high",
        "classify_main_name": "科技",
        "citation_rank": 6.0,
        "algo_doc_type": "policy_issuance",
        "ai_relevance": 0.82,
        "keywords": "人工智能,人工智能+",
    },
    {
        "id": 2,
        "site_key": "gd",
        "title": "广东省人民政府关于贯彻落实国务院人工智能+意见的实施方案",
        "document_number": "粤府〔2025〕30号",
        "publisher": "广东省人民政府",
        "date_written": ts(2025, 9, 15),
        "date_published": "2025-09-15",
        "body_text_cn": (
            "根据《国务院关于深入实施“人工智能+”行动的意见》（国发〔2025〕11号），"
            "结合我省实际，制定本实施方案。加快建设人工智能产业集群。"
        ),
        "abstract": "广东落实中央人工智能+意见。",
        "url": "https://www.gd.gov.cn/verify/ai-plus",
        "title_en": "Guangdong Implementation Plan for the State Council AI+ Opinions",
        "summary_en": "Provincial cascade of the central AI+ opinions.",
        "category": "science_tech",
        "importance": "high",
        "classify_main_name": "科技",
        "citation_rank": 3.0,
        "algo_doc_type": "action_plan",
        "ai_relevance": 0.71,
        "keywords": "人工智能",
    },
    {
        "id": 3,
        "site_key": "sz",
        "title": "深圳市推动人工智能高质量发展行动方案",
        "document_number": "深府〔2025〕15号",
        "publisher": "深圳市人民政府",
        "date_written": ts(2025, 10, 8),
        "date_published": "2025-10-08",
        "body_text_cn": (
            "根据《广东省人民政府关于贯彻落实国务院人工智能+意见的实施方案》，"
            "打造人工智能先锋城市。支持大模型与算力设施建设。"
        ),
        "abstract": "深圳人工智能行动方案。",
        "url": "https://www.sz.gov.cn/verify/ai",
        "title_en": "Shenzhen Action Plan for High-Quality AI Development",
        "summary_en": "Municipal AI action plan citing the provincial scheme.",
        "category": "science_tech",
        "importance": "medium",
        "classify_main_name": "科技",
        "citation_rank": 1.5,
        "algo_doc_type": "action_plan",
        "ai_relevance": 0.64,
        "keywords": "人工智能,算力",
    },
    {
        "id": 4,
        "site_key": "xinhua",
        "title": "新华时评：以人工智能赋能高质量发展",
        "document_number": "",
        "publisher": "新华社",
        "date_written": ts(2025, 8, 28),
        "date_published": "2025-08-28",
        "body_text_cn": "评论指出，人工智能+行动将推动产业升级。",
        "abstract": "媒体评论。",
        "url": "https://www.news.cn/verify/ai-comment",
        "title_en": "Xinhua commentary: AI for high-quality development",
        "summary_en": "State media commentary on the AI+ action.",
        "category": "commentary",
        "importance": "low",
        "classify_main_name": "评论",
        "citation_rank": 0,
        "algo_doc_type": "commentary",
        "ai_relevance": 0.4,
        "keywords": "人工智能",
    },
    {
        "id": 5,
        "site_key": "gov",
        "title": "国务院关于进一步加强住房保障工作的意见",
        "document_number": "国发〔2024〕8号",
        "publisher": "国务院",
        "date_written": ts(2024, 3, 12),
        "date_published": "2024-03-12",
        "body_text_cn": "为加强住房保障，完善保障性住房供给，现提出如下意见。",
        "abstract": "住房保障政策，不含科技产业条款。",
        "url": "https://www.gov.cn/verify/housing",
        "title_en": "Opinions on Strengthening Housing Security",
        "summary_en": "Housing security opinions — negative control for AI search.",
        "category": "housing",
        "importance": "high",
        "classify_main_name": "住房",
        "citation_rank": 0,
        "algo_doc_type": "policy_issuance",
        "ai_relevance": 0.0,
        "keywords": "住房保障",
    },
    {
        "id": 6,
        "site_key": "gd",
        "title": "广东省石油储备管理办法",
        "document_number": "粤府〔2026〕4号",
        "publisher": "广东省人民政府",
        "date_written": ts(2026, 3, 2),
        "date_published": "2026-03-02",
        "body_text_cn": "为规范石油储备管理，保障能源供应安全，制定本办法。战略石油储备实行分级管理。",
        "abstract": "石油储备管理。",
        "url": "https://www.gd.gov.cn/verify/oil-reserve",
        "title_en": "Guangdong Measures for Petroleum Reserve Administration",
        "summary_en": "Provincial petroleum reserve rules — oil collection fixture.",
        "category": "energy",
        "importance": "medium",
        "classify_main_name": "能源",
        "citation_rank": 0,
        "algo_doc_type": "regulation",
        "ai_relevance": 0.0,
        "keywords": "石油,储备",
    },
]

CITES = [
    (2, "国发〔2025〕11号", 1, "formal", "provincial", "central"),
    (3, "粤府〔2025〕30号", 2, "formal", "municipal", "provincial"),
    (3, "国发〔2025〕11号", 1, "formal", "municipal", "central"),
]


def seed(out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    conn = sqlite3.connect(str(out))
    conn.executescript(SCHEMA)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.executemany(
        "INSERT INTO sites (site_key, name, base_url, admin_level) VALUES (?,?,?,?)",
        SITES,
    )
    cols = [
        "id", "site_key", "title", "document_number", "publisher", "keywords",
        "date_written", "date_published", "abstract", "body_text_cn", "url",
        "crawl_timestamp", "title_en", "summary_en", "category", "importance",
        "classify_main_name", "citation_rank", "algo_doc_type", "ai_relevance",
    ]
    for doc in DOCS:
        row = {**doc, "crawl_timestamp": now}
        conn.execute(
            f"INSERT INTO documents ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            [row[c] for c in cols],
        )
    conn.executemany(
        "INSERT INTO citations (source_id, target_ref, target_id, citation_type, source_level, target_level) "
        "VALUES (?,?,?,?,?,?)",
        CITES,
    )
    conn.executemany(
        "INSERT INTO _verify_scaffold (key, value) VALUES (?,?)",
        [
            ("kind", "VERIFICATION_SCAFFOLDING_NOT_PRODUCTION"),
            ("source", "seed_fixture.py"),
            ("doc_count", str(len(DOCS))),
            ("search_query", "人工智能"),
            ("search_hit_ids", "1,2,3,4"),
            ("search_miss_id", "5"),
        ],
    )
    conn.commit()
    conn.close()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True, help="Path to write the fixture SQLite file")
    args = p.parse_args()
    seed(Path(args.out))
    print(f"seeded fixture {args.out} ({len(DOCS)} docs) VERIFICATION_SCAFFOLDING_NOT_PRODUCTION")


if __name__ == "__main__":
    main()
