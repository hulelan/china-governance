"""Classify documents using LLM (DeepSeek API or local Ollama).

Enriches each document with: English title, English summary, category,
topic tags, importance ranking, and Chinese policy area label.
Results are written directly to columns on the documents table.
Resumable — re-running skips already-classified docs (where classified_at != '').

Usage:
    # DeepSeek API (default — needs DEEPSEEK_API_KEY)
    python3 scripts/classify_documents.py --dry-run --limit 5
    python3 scripts/classify_documents.py --site sz --limit 100
    python3 scripts/classify_documents.py

    # Ollama (local, slower)
    python3 scripts/classify_documents.py --backend ollama --model qwen2.5:14b

    # Options
    --backend deepseek|ollama   API backend (default: deepseek)
    --model MODEL               Override model name
    --site SITE_KEY             Only classify docs from this site
    --limit N                   Max docs to process
    --dry-run                   Print results without saving
    --concurrency N             Parallel requests for DeepSeek (default: 15)
"""
import argparse
import json
import os
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "documents.db"

PROMPT = """You are classifying Chinese government documents for a Western analyst research database.
Given the document below, output a JSON object with these fields:

- title_en: English translation of the title (concise, formal government style)
- summary_en: 1-2 sentence English summary of what this document does or requires
- category: one of [major_policy, regulation, normative, budget, personnel, administrative, report, subsidy, other]
- topics: array of 1-3 English topic tags (e.g. "artificial intelligence", "housing", "environmental protection")
- importance: one of [high, medium, low] — see detailed rubric below
- policy_area: short Chinese topic label (e.g. "人工智能", "住房保障", "环境保护")

## Importance rubric (this is the most critical field):

HIGH — Documents a Western policy analyst would flag as significant:
  - New policy frameworks, action plans, development plans (行动方案, 发展规划)
    Example: "国务院办公厅关于上市公司独立董事制度改革的意见"
    Example: "深圳市人民政府办公厅关于印发深圳市扶持个体工商户高质量发展若干措施的通知"
  - Major regulatory changes (法规, 规章, 实施意见 from provincial+ level)
    Example: "关于加快发展我省服务业的实施意见"
  - Large funding allocations, subsidy programs, government guidance funds
  - Industry standards or rules with broad economic impact
  - State Council opinions (国务院意见) or central ministry directives

MEDIUM — Useful context but not headline-worthy:
  - Implementation notices that relay higher-level policy (转发...的通知)
    Example: "汕尾市人民政府转发广东省人民政府关于印发...实施意见的通知"
  - District/department-level regulatory details (管理办法, 实施细则)
    Example: "深圳市行政决策责任追究办法"
  - Budget and fiscal reports (预算, 决算)
    Example: "2022年度深圳市人民政府办公厅部门决算"
  - Normative documents with limited scope
  - Spatial planning approvals (规划批复)

LOW — Routine or procedural, minimal analytical value:
  - Personnel appointments/removals (任免)
    Example: "揭阳市人民政府关于陈洁珊同志任职的通知"
  - Meeting notices, work conferences
    Example: "市安委办召开全市安全生产治本攻坚三年行动信息系统业务培训工作会议"
  - Internal bidding results, procurement notices
    Example: "深圳市人力资源和社会保障局内部招标结果公示"
  - News-style articles about leader activities
    Example: "温湛滨调研新冠疫苗接种工作"
  - Public notices (taxi license transfers, traffic diversions, name lists)
    Example: "深圳市出租汽车营运牌照转让登记公告"

Document title: {title}
Document number: {doc_number}
Publisher: {publisher}
CMS category (if available): {classify_main_name}
Body excerpt (Chinese): {body_excerpt}

Output ONLY valid JSON, no explanation."""

VALID_CATEGORIES = {
    "major_policy", "regulation", "normative", "budget",
    "personnel", "administrative", "report", "subsidy", "other",
}
VALID_IMPORTANCE = {"high", "medium", "low"}


# ---------------------------------------------------------------------------
# DeepSeek backend (OpenAI-compatible API)
# ---------------------------------------------------------------------------

# Shared client — created once, reused across all threads
_deepseek_client = None
_rate_limit_lock = threading.Lock()


def _get_deepseek_client():
    global _deepseek_client
    if _deepseek_client is None:
        from openai import OpenAI
        _deepseek_client = OpenAI(
            api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
            base_url="https://api.deepseek.com",
            max_retries=2,
            timeout=60.0,
        )
    return _deepseek_client


def classify_deepseek(doc: dict, model: str) -> dict | None:
    """Classify a single document via DeepSeek API."""
    client = _get_deepseek_client()
    prompt = _build_prompt(doc)

    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500,
            )
            raw = (resp.choices[0].message.content or "").strip()
            if not raw:
                # Empty response — likely content filter. Skip silently.
                return None
            return _parse_response(raw)
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "rate" in err_str.lower():
                wait = (attempt + 1) * 5
                with _rate_limit_lock:
                    print(f"  [rate-limit] doc {doc['id']}, waiting {wait}s (attempt {attempt+1}/3)", flush=True)
                time.sleep(wait)
                continue
            if "Content Exists Risk" in err_str:
                return None  # Content filter — skip
            print(f"  [warn] DeepSeek error for doc {doc['id']}: {e}", flush=True)
            return None
    print(f"  [fail] doc {doc['id']}: exhausted retries", flush=True)
    return None


# ---------------------------------------------------------------------------
# Ollama backend (local)
# ---------------------------------------------------------------------------

def classify_ollama(doc: dict, model: str) -> dict | None:
    """Classify a single document via local Ollama."""
    import requests

    prompt = _build_prompt(doc)

    try:
        resp = requests.post("http://localhost:11434/api/generate", json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 300},
        }, timeout=120)
        resp.raise_for_status()
        raw = resp.json().get("response", "").strip()
        return _parse_response(raw)
    except Exception as e:
        print(f"  [warn] Ollama error for doc {doc['id']}: {e}")
        return None


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _build_prompt(doc: dict) -> str:
    body_excerpt = doc["body_text_cn"][:1500] if doc["body_text_cn"] else "(无正文)"
    return PROMPT.format(
        title=doc["title"],
        doc_number=doc["document_number"] or "(无)",
        publisher=doc["publisher"] or "(未知)",
        classify_main_name=doc.get("classify_main_name") or "(无)",
        body_excerpt=body_excerpt,
    )


def _parse_response(raw: str) -> dict | None:
    """Extract and validate JSON from LLM response."""
    # Strip markdown code fences if present
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        # Try to salvage truncated JSON by closing braces
        for fix in [raw + '"}'  , raw + '"}', raw + ']}']:
            try:
                result = json.loads(fix)
                break
            except json.JSONDecodeError:
                continue
        else:
            return None

    # Validate and normalize
    if result.get("category") not in VALID_CATEGORIES:
        result["category"] = "other"
    if result.get("importance") not in VALID_IMPORTANCE:
        result["importance"] = "medium"
    if not isinstance(result.get("topics"), list):
        result["topics"] = []
    if not isinstance(result.get("title_en"), str):
        result["title_en"] = ""
    if not isinstance(result.get("summary_en"), str):
        result["summary_en"] = ""
    if not isinstance(result.get("policy_area"), str):
        result["policy_area"] = ""

    return result


def ensure_columns(conn):
    """Add classification columns to documents table if they don't exist."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(documents)").fetchall()}
    new_cols = {
        "summary_en": "TEXT DEFAULT ''",
        "category": "TEXT DEFAULT ''",
        "importance": "TEXT DEFAULT ''",
        "policy_area": "TEXT DEFAULT ''",
        "topics": "TEXT DEFAULT ''",
        "classification_model": "TEXT DEFAULT ''",
        "classified_at": "TEXT DEFAULT ''",
    }
    for col, typedef in new_cols.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE documents ADD COLUMN {col} {typedef}")
            print(f"  Added column: documents.{col}")
    conn.commit()


def save_result(conn, doc_id: int, result: dict, model: str):
    """Write classification result to the documents table."""
    conn.execute(
        """UPDATE documents SET
            title_en = ?,
            summary_en = ?,
            category = ?,
            importance = ?,
            policy_area = ?,
            topics = ?,
            classification_model = ?,
            classified_at = datetime('now')
        WHERE id = ?""",
        (
            result.get("title_en", ""),
            result.get("summary_en", ""),
            result.get("category", "other"),
            result.get("importance", "medium"),
            result.get("policy_area", ""),
            json.dumps(result.get("topics", []), ensure_ascii=False),
            model,
            doc_id,
        ),
    )


def main():
    parser = argparse.ArgumentParser(description="Classify documents with LLM")
    parser.add_argument("--backend", choices=["deepseek", "ollama"], default="deepseek")
    parser.add_argument("--model", help="Override model name")
    parser.add_argument("--site", help="Only classify docs from this site_key")
    parser.add_argument("--limit", type=int, help="Max docs to process")
    parser.add_argument("--dry-run", action="store_true", help="Print results without saving")
    parser.add_argument("--concurrency", type=int, default=5, help="Parallel requests (DeepSeek only)")
    args = parser.parse_args()

    # Default models per backend
    if args.model is None:
        args.model = "deepseek-chat" if args.backend == "deepseek" else "qwen2.5:14b"

    # Validate backend availability
    if args.backend == "deepseek":
        if not os.environ.get("DEEPSEEK_API_KEY"):
            print("Error: Set DEEPSEEK_API_KEY environment variable")
            print("Get one at: https://platform.deepseek.com")
            sys.exit(1)
        classify_fn = classify_deepseek
    else:
        import requests
        try:
            requests.get("http://localhost:11434/api/tags", timeout=5)
        except requests.ConnectionError:
            print("Error: Ollama is not running. Start it with: ollama serve")
            sys.exit(1)
        classify_fn = classify_ollama

    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    ensure_columns(conn)

    # Find unclassified documents (classified_at is empty or NULL)
    where = "WHERE (d.classified_at IS NULL OR d.classified_at = '')"
    params = []
    if args.site:
        where += " AND d.site_key = ?"
        params.append(args.site)

    query = f"""
        SELECT d.id, d.title, d.document_number, d.publisher,
               d.body_text_cn, d.classify_main_name
        FROM documents d {where}
        ORDER BY d.date_written DESC
    """
    if args.limit:
        query += f" LIMIT {args.limit}"

    rows = conn.execute(query, params).fetchall()
    cols = ["id", "title", "document_number", "publisher", "body_text_cn", "classify_main_name"]
    docs = [dict(zip(cols, row)) for row in rows]
    total = len(docs)

    print(f"Found {total:,} unclassified documents")
    print(f"Backend: {args.backend} | Model: {args.model}", end="")
    if args.backend == "deepseek":
        print(f" | Concurrency: {args.concurrency}")
    else:
        print()

    if total == 0:
        print("All documents already classified!")
        return

    start_time = time.time()
    success = 0
    errors = 0
    processed = 0

    if args.backend == "deepseek" and not args.dry_run:
        # Process in batches to avoid overwhelming the API
        batch_size = 200
        with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
            for batch_start in range(0, total, batch_size):
                batch = docs[batch_start:batch_start + batch_size]
                futures = {
                    executor.submit(classify_fn, doc, args.model): doc
                    for doc in batch
                }
                for future in as_completed(futures):
                    doc = futures[future]
                    processed += 1
                    result = future.result()

                    if result:
                        save_result(conn, doc["id"], result, args.model)
                        success += 1
                    else:
                        errors += 1

                # Commit after each batch
                conn.commit()
                elapsed = time.time() - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                remaining = (total - processed) / rate if rate > 0 else 0
                print(f"  Progress: {processed:,}/{total:,} ({success:,} ok, {errors:,} err) | "
                      f"{rate:.1f} docs/s | ETA: {remaining/60:.0f}m", flush=True)
    else:
        # Sequential execution (Ollama or dry-run)
        for doc in docs:
            result = classify_fn(doc, args.model)
            processed += 1

            if result:
                if args.dry_run:
                    print(f"\n  [{doc['id']}] {doc['title'][:60]}")
                    print(f"    title_en:    {result.get('title_en', '')}")
                    print(f"    summary_en:  {result.get('summary_en', '')}")
                    print(f"    category:    {result.get('category', '')}")
                    print(f"    importance:  {result.get('importance', '')}")
                    print(f"    topics:      {result.get('topics', [])}")
                    print(f"    policy_area: {result.get('policy_area', '')}")
                else:
                    save_result(conn, doc["id"], result, args.model)
                    if processed % 10 == 0:
                        conn.commit()
                success += 1
            else:
                errors += 1

            if processed % 20 == 0 and not args.dry_run:
                elapsed = time.time() - start_time
                rate = processed / elapsed
                remaining = (total - processed) / rate if rate > 0 else 0
                print(f"  Progress: {processed:,}/{total:,} ({success:,} ok, {errors:,} err) | "
                      f"{rate:.1f} docs/s | ETA: {remaining/60:.0f}m")

        if not args.dry_run:
            conn.commit()

    conn.close()
    elapsed = time.time() - start_time
    print(f"\nDone: {success:,}/{total:,} classified, {errors:,} errors in {elapsed:.0f}s")
    if success > 0 and not args.dry_run:
        est_input = success * 800
        est_output = success * 100
        cost = (est_input * 0.28 + est_output * 1.10) / 1_000_000
        print(f"Estimated cost: ~${cost:.2f}")


if __name__ == "__main__":
    main()
