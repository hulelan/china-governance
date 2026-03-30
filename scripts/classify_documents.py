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

PROMPT = """You are classifying Chinese government and policy documents for a Western analyst research database.
Given the document below, output a JSON object with these fields:

- title_en: English translation of the title (concise, formal government style)
- summary_en: 1-2 sentence English summary of what this document does or requires
- doc_type: the type of document — see guide below
- policy_significance: how important is the UNDERLYING POLICY OR TOPIC (not this document itself) — one of [high, medium, low]
- topics: array of 1-3 English topic tags (e.g. "artificial intelligence", "housing", "environmental protection")
- policy_area: short Chinese topic label (e.g. "人工智能", "住房保障", "环境保护")
- references: array of Chinese policy names or document numbers referenced in the text (e.g. ["关于深入实施'人工智能+'行动的意见", "国发〔2025〕11号"]). Empty array if none found.

## doc_type — what IS this document?

- original_policy: The authoritative text of a policy, regulation, opinion, plan, or directive (意见, 通知, 办法, 规划, 方案, 条例, 规章, 若干措施). This is the PRIMARY source. IMPORTANT: "印发《X》的通知" (notice issuing X) IS the original — it's the government publishing X for the first time, not relaying it.
- relay_notice: A notice that FORWARDS a policy from a DIFFERENT (usually higher-level) body (转发...的通知). The key test: did the issuer write the policy, or just pass it along? If the title says "转发XX省/XX部关于...", it's a relay.
- interpretation: An official government explanation of a policy's rationale or implementation details (政策解读, 解读). Published by the issuing agency or designated experts.
- explainer: A visual or simplified summary of a policy (图解, 一图读懂, 秒懂, 速览, 政策图解). Derivative — the original policy exists separately.
- media_exclusive: Journalism that reveals non-public information or provides first-of-kind industry data (独家, exclusive reports, first disclosures of deals/products/data).
- media_coverage: General news reporting, conference recaps, event coverage, opinion pieces, or industry overviews.
- research: Academic papers, think tank reports, white papers, data reports.
- personnel: Appointment or removal notices (任免, 职务任免).
- procurement: Bidding announcements, procurement results, public name lists, license transfers.
- other: Anything that doesn't fit above (speeches, meeting minutes, event notices, photo galleries).

## policy_significance — how important is the TOPIC/POLICY being discussed?

This is about the underlying subject matter, NOT about this particular document. An infographic (图解) about an important AI policy still has HIGH policy_significance — the policy matters, even though this document is just a summary.

HIGH:
  - National-level policy frameworks or strategies (e.g., AI+ action plan, data governance, dual carbon)
  - Major regulatory changes affecting broad industries
  - Significant funding programs (billions of yuan)
  - Technology export controls, trade restrictions
  - Topics with international implications

MEDIUM:
  - Provincial or city-level implementation of national policy
  - Sector-specific regulations (single industry, limited geography)
  - Standard budgetary or fiscal matters
  - Routine regulatory updates to existing frameworks

LOW:
  - Internal administrative procedures
  - Individual personnel decisions
  - Procurement and bidding
  - Local event notices, traffic diversions, name lists
  - Topics with no broader policy implications
  - Note: a leader speech ABOUT an important topic (e.g., AI) still has the policy_significance of that topic. The doc_type (media_coverage) already captures that it's a speech, not a policy.

Document title: {title}
Document number: {doc_number}
Publisher: {publisher}
CMS category (if available): {classify_main_name}
Body excerpt (Chinese): {body_excerpt}

Output ONLY valid JSON, no explanation."""

VALID_DOC_TYPES = {
    "original_policy", "relay_notice", "interpretation", "explainer",
    "media_exclusive", "media_coverage", "research", "personnel",
    "procurement", "other",
}
VALID_SIGNIFICANCE = {"high", "medium", "low"}

# Legacy fields kept for backward compatibility
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

    # Validate and normalize new v2 fields
    if result.get("doc_type") not in VALID_DOC_TYPES:
        result["doc_type"] = "other"
    if result.get("policy_significance") not in VALID_SIGNIFICANCE:
        result["policy_significance"] = "medium"
    if not isinstance(result.get("references"), list):
        result["references"] = []
    if not isinstance(result.get("topics"), list):
        result["topics"] = []
    if not isinstance(result.get("title_en"), str):
        result["title_en"] = ""
    if not isinstance(result.get("summary_en"), str):
        result["summary_en"] = ""
    if not isinstance(result.get("policy_area"), str):
        result["policy_area"] = ""

    # Derive legacy fields from v2 for backward compatibility
    type_to_category = {
        "original_policy": "major_policy", "relay_notice": "normative",
        "interpretation": "report", "explainer": "report",
        "media_exclusive": "report", "media_coverage": "report",
        "research": "report", "personnel": "personnel",
        "procurement": "administrative",
    }
    result["category"] = type_to_category.get(result["doc_type"], "other")
    result["importance"] = result["policy_significance"]

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
        # v2 fields
        "doc_type": "TEXT DEFAULT ''",
        "policy_significance": "TEXT DEFAULT ''",
        "references_json": "TEXT DEFAULT ''",
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
            doc_type = ?,
            policy_significance = ?,
            references_json = ?,
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
            result.get("doc_type", "other"),
            result.get("policy_significance", "medium"),
            json.dumps(result.get("references", []), ensure_ascii=False),
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
                    print(f"    title_en:           {result.get('title_en', '')}")
                    print(f"    summary_en:         {result.get('summary_en', '')}")
                    print(f"    doc_type:           {result.get('doc_type', '')}")
                    print(f"    policy_significance:{result.get('policy_significance', '')}")
                    print(f"    topics:             {result.get('topics', [])}")
                    print(f"    policy_area:        {result.get('policy_area', '')}")
                    print(f"    references:         {result.get('references', [])}")
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
