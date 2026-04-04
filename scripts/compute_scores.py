"""
Compute algorithmic document scores: citation rank, document type, AI relevance.

No LLM needed — uses citation graph, regex patterns, and keyword density.

Outputs three new columns on documents:
  - citation_rank: inbound citation count, weighted by source level
  - algo_doc_type: document type from title patterns (regulation, subsidy, action_plan, etc.)
  - ai_relevance: 0.0-1.0 score for how substantially about AI/tech

Usage:
    python3 scripts/compute_scores.py              # Compute all scores
    python3 scripts/compute_scores.py --dry-run    # Preview without saving
    python3 scripts/compute_scores.py --stats      # Show score distributions
"""

import argparse
import math
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "documents.db"


# ============================================================
# Signal 1: Citation rank (PageRank-like)
# ============================================================

LEVEL_WEIGHTS = {
    "central": 3.0,
    "provincial": 2.0,
    "municipal": 1.5,
    "district": 1.0,
    "department": 1.0,
    "unknown": 0.5,
}


def compute_citation_ranks(conn) -> dict[int, float]:
    """Compute weighted inbound citation count for every document."""
    rows = conn.execute("""
        SELECT c.target_id, c.source_level, COUNT(*) as cnt
        FROM citations c
        WHERE c.target_id IS NOT NULL
        GROUP BY c.target_id, c.source_level
    """).fetchall()

    ranks = defaultdict(float)
    for target_id, source_level, cnt in rows:
        weight = LEVEL_WEIGHTS.get(source_level, 0.5)
        ranks[target_id] += cnt * weight

    return dict(ranks)


# ============================================================
# Signal 2: Algorithmic document type classifier
# ============================================================

# Ordered by specificity — first match wins
DOC_TYPE_PATTERNS = [
    # Regulations & laws
    (r"条例$", "regulation"),
    (r"办法$", "regulation"),
    (r"规定$", "regulation"),
    (r"规则$", "regulation"),
    (r"准则$", "regulation"),
    (r"细则$", "regulation"),

    # Action plans & strategies
    (r"行动计划|行动方案", "action_plan"),
    (r"实施方案|实施意见|实施细则", "action_plan"),
    (r"发展规划|发展纲要|五年规划", "strategy"),
    (r"工作方案|工作计划|工作要点", "work_plan"),

    # Policy issuance (关于印发X的通知)
    (r"关于印发.*的通知", "policy_issuance"),

    # Subsidies & funding
    (r"补贴|资助|奖励|扶持|专项资金|引导基金", "subsidy"),
    (r"公示.*名单|公示.*项目|公示.*企业", "subsidy_list"),
    (r"申报.*指南|申报.*通知|申报.*公告", "application_guide"),

    # Interpretations & explainers
    (r"解读|一图读懂|图解|政策问答", "explainer"),

    # Standards
    (r"标准$|国家标准|行业标准|团体标准", "standard"),

    # Announcements
    (r"公告$|通告$|公报$", "announcement"),
    (r"征求.*意见|意见征集|公开征求", "consultation"),

    # Administrative
    (r"会议纪要|工作报告|工作总结|述职", "administrative"),
    (r"人事|任免|任命|聘任|招聘|录用", "personnel"),
    (r"批复$|函$", "reply"),

    # Notices (catch-all for 通知)
    (r"通知$", "notice"),

    # Media/commentary
    (r"评论|社论|时评|锐评|快评|论坛|观察", "commentary"),
    (r"专访|访谈|对话", "interview"),
    (r"综述|述评|盘点|回顾", "review"),
]

COMPILED_PATTERNS = [(re.compile(p), t) for p, t in DOC_TYPE_PATTERNS]


def classify_doc_type(title: str) -> str:
    """Classify document type from title using regex patterns."""
    if not title:
        return "unknown"
    for pattern, doc_type in COMPILED_PATTERNS:
        if pattern.search(title):
            return doc_type
    return "other"


# ============================================================
# Signal 3: AI relevance score
# ============================================================

# Term -> weight. Higher = more specific to AI/tech policy
AI_TERMS = {
    # Core AI
    "人工智能": 10,
    "大模型": 9,
    "生成式人工智能": 10,
    "深度学习": 8,
    "机器学习": 8,
    "自然语言处理": 8,
    "计算机视觉": 7,
    "智能体": 8,

    # Infrastructure
    "算力": 7,
    "数据中心": 7,
    "智算中心": 9,
    "GPU": 8,
    "算力券": 9,

    # Semiconductors
    "半导体": 8,
    "芯片": 7,
    "集成电路": 7,
    "光刻": 9,
    "晶圆": 8,
    "EDA": 9,

    # Autonomous systems
    "自动驾驶": 7,
    "智能网联": 7,
    "无人机": 6,
    "机器人": 5,
    "具身智能": 9,
    "人形机器人": 9,

    # Data & governance
    "算法治理": 8,
    "算法备案": 9,
    "数据要素": 6,
    "数据安全": 5,
    "网络安全": 4,
    "个人信息保护": 5,

    # Broader tech (lower weights)
    "数字经济": 4,
    "数字化转型": 3,
    "新质生产力": 3,
    "智慧城市": 3,
    "区块链": 4,
    "量子计算": 6,
    "5G": 3,
    "云计算": 4,
    "物联网": 3,
}


def compute_ai_relevance(title: str, body: str, keywords: str = "") -> float:
    """Compute AI relevance score from 0.0 to 1.0.

    Uses weighted keyword density. A passing mention scores low,
    a dedicated AI policy scores high.
    """
    text = (title or "") + " " + (body or "") + " " + (keywords or "")
    if not text.strip():
        return 0.0

    # Title matches count 3x (a doc titled "人工智能" is definitely about AI)
    title_text = (title or "") + " " + (keywords or "")

    raw_score = 0.0
    term_hits = 0
    for term, weight in AI_TERMS.items():
        body_count = (body or "").count(term)
        title_count = title_text.count(term)
        if body_count > 0 or title_count > 0:
            term_hits += 1
            # Diminishing returns: first 3 mentions count fully, then sqrt
            effective_count = min(body_count, 3) + max(0, math.sqrt(body_count - 3)) if body_count > 3 else body_count
            raw_score += weight * (effective_count + title_count * 3)

    if raw_score == 0:
        return 0.0

    # Normalize by document length (longer docs shouldn't score higher just for being long)
    doc_len = max(len(body or ""), 100)
    density = raw_score / math.sqrt(doc_len)

    # Bonus for term diversity (doc mentioning 5 AI terms > doc mentioning 1 term 5 times)
    diversity_bonus = 1.0 + (min(term_hits, 8) * 0.1)
    adjusted = density * diversity_bonus

    # Sigmoid-like normalization to 0-1 range
    # Calibrated so: passing mention (~5) ≈ 0.1, moderate (~20) ≈ 0.4, dedicated AI doc (~50+) ≈ 0.8+
    score = adjusted / (adjusted + 8.0)

    return round(min(score, 1.0), 3)


# ============================================================
# Main
# ============================================================

def ensure_columns(conn):
    """Add score columns if they don't exist."""
    for col, col_type in [
        ("citation_rank", "REAL DEFAULT 0"),
        ("algo_doc_type", "TEXT DEFAULT ''"),
        ("ai_relevance", "REAL DEFAULT 0"),
    ]:
        try:
            conn.execute(f"ALTER TABLE documents ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass  # Column already exists


def compute_all(conn, dry_run=False):
    print("Computing citation ranks...")
    ranks = compute_citation_ranks(conn)
    print(f"  {len(ranks)} documents have inbound citations")

    # Top cited
    top = sorted(ranks.items(), key=lambda x: -x[1])[:10]
    for doc_id, rank in top:
        row = conn.execute("SELECT title FROM documents WHERE id = ?", (doc_id,)).fetchone()
        title = row[0][:60] if row else "?"
        print(f"    {rank:.1f}  {title}")

    print("\nClassifying document types...")
    rows = conn.execute("SELECT id, title FROM documents").fetchall()
    type_counts = Counter()
    doc_types = {}
    for doc_id, title in rows:
        dt = classify_doc_type(title)
        doc_types[doc_id] = dt
        type_counts[dt] += 1

    print(f"  {len(rows)} documents classified:")
    for dt, count in type_counts.most_common():
        print(f"    {dt}: {count:,}")

    print("\nComputing AI relevance scores...")
    rows = conn.execute("SELECT id, title, body_text_cn, keywords FROM documents").fetchall()
    ai_scores = {}
    score_buckets = Counter()
    for doc_id, title, body, keywords in rows:
        score = compute_ai_relevance(title, body, keywords)
        ai_scores[doc_id] = score
        if score >= 0.5:
            score_buckets["high (>=0.5)"] += 1
        elif score >= 0.2:
            score_buckets["medium (0.2-0.5)"] += 1
        elif score > 0:
            score_buckets["low (>0)"] += 1
        else:
            score_buckets["none (0)"] += 1

    print(f"  AI relevance distribution:")
    for bucket, count in sorted(score_buckets.items()):
        print(f"    {bucket}: {count:,}")

    # Show top AI docs
    top_ai = sorted(ai_scores.items(), key=lambda x: -x[1])[:10]
    print(f"\n  Top AI-relevant documents:")
    for doc_id, score in top_ai:
        row = conn.execute("SELECT title, site_key FROM documents WHERE id = ?", (doc_id,)).fetchone()
        title = row[0][:55] if row else "?"
        site = row[1] if row else "?"
        print(f"    {score:.3f}  [{site}] {title}")

    if dry_run:
        print("\n[DRY RUN — nothing saved]")
        return

    print("\nSaving scores...")
    ensure_columns(conn)

    # Batch update
    batch = []
    for doc_id, title in conn.execute("SELECT id, title FROM documents").fetchall():
        rank = ranks.get(doc_id, 0.0)
        dt = doc_types.get(doc_id, "unknown")
        ai = ai_scores.get(doc_id, 0.0)
        batch.append((rank, dt, ai, doc_id))

    conn.executemany(
        "UPDATE documents SET citation_rank = ?, algo_doc_type = ?, ai_relevance = ? WHERE id = ?",
        batch
    )
    conn.commit()
    print(f"  Updated {len(batch):,} documents")

    # Create index for fast filtering
    conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_ai_relevance ON documents(ai_relevance)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_citation_rank ON documents(citation_rank)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_algo_doc_type ON documents(algo_doc_type)")
    conn.commit()
    print("  Indexes created")


def show_stats(conn):
    """Show current score distributions."""
    # Check if columns exist
    try:
        conn.execute("SELECT citation_rank FROM documents LIMIT 1")
    except sqlite3.OperationalError:
        print("Score columns not yet computed. Run without --stats first.")
        return

    print("=== Score distributions ===\n")

    # Citation rank
    rows = conn.execute("""
        SELECT
            SUM(CASE WHEN citation_rank >= 10 THEN 1 ELSE 0 END) as high,
            SUM(CASE WHEN citation_rank >= 3 AND citation_rank < 10 THEN 1 ELSE 0 END) as medium,
            SUM(CASE WHEN citation_rank > 0 AND citation_rank < 3 THEN 1 ELSE 0 END) as low,
            SUM(CASE WHEN citation_rank = 0 THEN 1 ELSE 0 END) as none
        FROM documents
    """).fetchone()
    print(f"Citation rank: high(>=10)={rows[0]:,} | medium(3-10)={rows[1]:,} | low(>0)={rows[2]:,} | none={rows[3]:,}")

    # Doc type
    rows = conn.execute("""
        SELECT algo_doc_type, COUNT(*) FROM documents
        GROUP BY algo_doc_type ORDER BY COUNT(*) DESC
    """).fetchall()
    print(f"\nDocument types:")
    for dt, count in rows:
        print(f"  {dt or 'unknown'}: {count:,}")

    # AI relevance
    rows = conn.execute("""
        SELECT
            SUM(CASE WHEN ai_relevance >= 0.5 THEN 1 ELSE 0 END),
            SUM(CASE WHEN ai_relevance >= 0.2 AND ai_relevance < 0.5 THEN 1 ELSE 0 END),
            SUM(CASE WHEN ai_relevance > 0 AND ai_relevance < 0.2 THEN 1 ELSE 0 END),
            SUM(CASE WHEN ai_relevance = 0 THEN 1 ELSE 0 END)
        FROM documents
    """).fetchone()
    print(f"\nAI relevance: high(>=0.5)={rows[0]:,} | medium(0.2-0.5)={rows[1]:,} | low(>0)={rows[2]:,} | none={rows[3]:,}")

    # Cross-tab: high AI + high citation
    row = conn.execute("""
        SELECT COUNT(*) FROM documents
        WHERE ai_relevance >= 0.3 AND citation_rank >= 3
    """).fetchone()
    print(f"\nHigh AI + frequently cited: {row[0]:,} docs (the most important AI policy documents)")


def main():
    parser = argparse.ArgumentParser(description="Compute document scores (no LLM)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument("--stats", action="store_true", help="Show current score distributions")
    args = parser.parse_args()

    conn = sqlite3.connect(str(DB_PATH))

    if args.stats:
        show_stats(conn)
    else:
        compute_all(conn, dry_run=args.dry_run)

    conn.close()


if __name__ == "__main__":
    main()
