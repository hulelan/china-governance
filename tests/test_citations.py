"""Tests for citation extraction and chain building.

Red/green TDD: these tests define the behavior we WANT.
Run with: python3 -m pytest tests/test_citations.py -v
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from analyze import REF_PATTERN, NAMED_REF_PATTERN, is_policy_document


# ---------------------------------------------------------------------------
# Fixtures: in-memory DB with test documents
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    """Create an in-memory SQLite DB with test documents and citations."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.executescript("""
        CREATE TABLE sites (
            site_key TEXT PRIMARY KEY, name TEXT, base_url TEXT, admin_level TEXT
        );
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY, site_key TEXT, title TEXT NOT NULL,
            document_number TEXT DEFAULT '', body_text_cn TEXT DEFAULT '',
            url TEXT DEFAULT '', keywords TEXT DEFAULT '', abstract TEXT DEFAULT '',
            references_json TEXT DEFAULT '', date_published TEXT DEFAULT '',
            publisher TEXT DEFAULT '', classified_at TEXT DEFAULT '',
            title_en TEXT DEFAULT '', summary_en TEXT DEFAULT '',
            category TEXT DEFAULT '', importance TEXT DEFAULT '',
            policy_area TEXT DEFAULT '', topics TEXT DEFAULT '',
            classify_main_name TEXT DEFAULT '', body_text_en TEXT DEFAULT '',
            doc_type TEXT DEFAULT '', policy_significance TEXT DEFAULT ''
        );
        CREATE TABLE citations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER, target_ref TEXT, target_id INTEGER,
            citation_type TEXT, source_level TEXT, target_level TEXT,
            UNIQUE(source_id, target_ref, citation_type)
        );

        -- Sites
        INSERT INTO sites VALUES ('gov', 'State Council', 'http://gov.cn', 'central');
        INSERT INTO sites VALUES ('gd', 'Guangdong', 'http://gd.gov.cn', 'provincial');
        INSERT INTO sites VALUES ('sz', 'Shenzhen', 'http://sz.gov.cn', 'municipal');
        INSERT INTO sites VALUES ('latepost', 'LatePost', 'http://163.com', 'media');

        -- Central AI policy (the original)
        INSERT INTO documents (id, site_key, title, document_number, body_text_cn, url)
        VALUES (1, 'gov', '国务院关于深入实施"人工智能+"行动的意见', '国发〔2025〕11号',
                '各省、自治区、直辖市人民政府...推动人工智能赋能千行百业...', 'http://gov.cn/ai');

        -- Provincial implementation (cites central policy via 文号)
        INSERT INTO documents (id, site_key, title, document_number, body_text_cn, url)
        VALUES (2, 'gd', '广东省人民政府关于贯彻落实国务院人工智能+意见的实施方案', '粤府〔2025〕30号',
                '根据《国务院关于深入实施"人工智能+"行动的意见》（国发〔2025〕11号）...制定本方案...', 'http://gd.gov.cn/ai');

        -- Municipal implementation (cites provincial via named ref)
        INSERT INTO documents (id, site_key, title, document_number, body_text_cn, url)
        VALUES (3, 'sz', '深圳市推动人工智能高质量发展行动方案', '深府〔2025〕15号',
                '根据《广东省人民政府关于贯彻落实国务院人工智能+意见的实施方案》...打造AI先锋城市...', 'http://sz.gov.cn/ai');

        -- Media article (NO formal refs, but references_json has the policy name)
        INSERT INTO documents (id, site_key, title, body_text_cn, url, references_json)
        VALUES (4, 'latepost', '晚点独家丨国务院AI+意见出台后各地方案梳理',
                '国务院发布人工智能+行动意见后，广东、深圳等地纷纷出台落实方案...',
                'http://163.com/latepost/ai',
                '["国务院关于深入实施\\"人工智能+\\"行动的意见", "广东省人民政府关于贯彻落实国务院人工智能+意见的实施方案"]');

        -- Explainer (图解) of the central policy
        INSERT INTO documents (id, site_key, title, body_text_cn, url, references_json)
        VALUES (5, 'gov', '一图读懂《国务院关于深入实施"人工智能+"行动的意见》',
                '图解要点：一、总体目标...二、重点任务...三、保障措施...',
                'http://gov.cn/ai-explainer',
                '["国务院关于深入实施\\"人工智能+\\"行动的意见"]');

        -- Unrelated doc (should NOT appear in AI chain)
        INSERT INTO documents (id, site_key, title, body_text_cn, url)
        VALUES (6, 'sz', '深圳市出租汽车营运牌照转让登记公告', '关于出租汽车牌照...', 'http://sz.gov.cn/taxi');
    """)
    return conn


# ---------------------------------------------------------------------------
# Test 1: Regex citation extraction catches formal refs
# ---------------------------------------------------------------------------

def test_regex_extracts_formal_ref():
    """The regex should find 国发〔2025〕11号 in body text."""
    body = '根据《国务院关于深入实施"人工智能+"行动的意见》（国发〔2025〕11号）...'
    refs = REF_PATTERN.findall(body)
    assert '国发〔2025〕11号' in refs


def test_regex_extracts_named_ref():
    """The regex should find 《named references》 in body text."""
    body = '根据《广东省人民政府关于贯彻落实国务院人工智能+意见的实施方案》...'
    refs = NAMED_REF_PATTERN.findall(body)
    assert any('广东省' in r for r in refs)


# ---------------------------------------------------------------------------
# Test 2: references_json creates citations (THE KEY NEW FEATURE)
# ---------------------------------------------------------------------------

def test_references_json_creates_citations(db):
    """LLM-extracted references_json should be converted into citations."""
    from scripts.extract_citations import extract_all
    extract_all(db)

    # The media article (id=4) has references_json with 2 policy names
    media_cites = db.execute(
        "SELECT target_ref, citation_type FROM citations WHERE source_id = 4"
    ).fetchall()

    assert len(media_cites) >= 1, "Media article should have at least 1 citation from references_json"

    # Check citation type is 'llm' (not 'formal' or 'named')
    llm_cites = [c for c in media_cites if c[1] == 'llm']
    assert len(llm_cites) >= 1, "references_json citations should have type 'llm'"


def test_references_json_resolves_to_corpus(db):
    """references_json refs should resolve to matching documents in corpus."""
    from scripts.extract_citations import extract_all
    extract_all(db)

    # The media article references "国务院关于深入实施"人工智能+"行动的意见"
    # which matches doc id=1 by title
    resolved = db.execute(
        "SELECT target_id FROM citations WHERE source_id = 4 AND target_id IS NOT NULL"
    ).fetchall()

    assert len(resolved) >= 1, "At least one references_json ref should resolve to a corpus document"


# ---------------------------------------------------------------------------
# Test 3: Media articles have citations (currently 0!)
# ---------------------------------------------------------------------------

def test_media_articles_get_citations(db):
    """After extraction, media articles should have citations via references_json."""
    from scripts.extract_citations import extract_all
    extract_all(db)

    media_cite_count = db.execute(
        "SELECT COUNT(*) FROM citations WHERE source_id = 4"
    ).fetchone()[0]

    assert media_cite_count > 0, "Media articles with references_json should have citations"


# ---------------------------------------------------------------------------
# Test 4: Bidirectional chain (THE OTHER KEY FEATURE)
# ---------------------------------------------------------------------------

def test_chain_includes_inbound_citations(db):
    """The AI chain should include docs that CITE AI policies, not just those matching the keyword."""
    from scripts.extract_citations import extract_all
    extract_all(db)

    # Simulate chain query: find all docs connected to "人工智能"
    # Step 1: Source docs matching keyword
    keyword_docs = db.execute(
        "SELECT id FROM documents WHERE title LIKE '%人工智能%'"
    ).fetchall()
    keyword_ids = {r[0] for r in keyword_docs}

    # Step 2: Outbound — policies cited BY keyword docs
    outbound = db.execute(
        "SELECT DISTINCT target_id FROM citations WHERE source_id IN ({}) AND target_id IS NOT NULL".format(
            ','.join(str(i) for i in keyword_ids)
        )
    ).fetchall()
    outbound_ids = {r[0] for r in outbound}

    # Step 3: Inbound — docs that CITE keyword docs
    inbound = db.execute(
        "SELECT DISTINCT source_id FROM citations WHERE target_id IN ({})".format(
            ','.join(str(i) for i in keyword_ids)
        )
    ).fetchall()
    inbound_ids = {r[0] for r in inbound}

    # The media article (id=4) cites the central AI policy (id=1)
    # It should appear in the inbound set
    all_chain_ids = keyword_ids | outbound_ids | inbound_ids

    assert 4 in all_chain_ids, "Media article citing AI policy should be in the chain (via inbound)"
    assert 6 not in all_chain_ids, "Unrelated taxi doc should NOT be in the chain"


def test_chain_shows_policy_cascade(db):
    """The chain should show central → provincial → municipal cascade."""
    from scripts.extract_citations import extract_all
    extract_all(db)

    # Doc 2 (provincial) cites doc 1 (central) via formal ref
    # Doc 3 (municipal) cites doc 2 (provincial) via named ref
    cascade = db.execute("""
        SELECT c1.source_id as mid, c1.target_id as top, c2.source_id as bottom
        FROM citations c1
        JOIN citations c2 ON c2.target_id = c1.source_id
        WHERE c1.target_id = 1
    """).fetchall()

    # We should see: municipal(3) → provincial(2) → central(1)
    assert any(r[2] == 3 and r[0] == 2 and r[1] == 1 for r in cascade), \
        "Should detect central→provincial→municipal cascade"


# ---------------------------------------------------------------------------
# Test 5: Explainer links to original policy
# ---------------------------------------------------------------------------

def test_explainer_links_to_original(db):
    """An explainer (图解) should have a citation to the original policy via references_json."""
    from scripts.extract_citations import extract_all
    extract_all(db)

    explainer_cites = db.execute(
        "SELECT target_ref, target_id FROM citations WHERE source_id = 5"
    ).fetchall()

    assert len(explainer_cites) >= 1, "Explainer should cite the original policy"
    # Should resolve to doc 1 (the original AI policy)
    resolved_ids = [c[1] for c in explainer_cites if c[1] is not None]
    assert 1 in resolved_ids, "Explainer's reference should resolve to the original policy doc"
