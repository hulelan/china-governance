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
    --dry-run                   Print results without saving (writes NOTHING, not
                                even schema — opens the DB read-only)
    --concurrency N             Parallel DeepSeek requests (default: 2 — see warning)
    --retry-failed              Also re-send docs that have already failed >= 3
                                times (terminal content_risk docs stay excluded)
    --init-schema               Create the classify_failures table and exit

⚠️  DeepSeek concurrency: 2 is the HARD MAX. Above ~2 the API does NOT return
    429s — it silently returns EMPTY responses, so docs look "processed" but get
    no classification and you burn spend for nothing. This bit us in production;
    the nightly daily_sync.sh Phase 2 runs at concurrency 2 for this reason. Do
    not raise the default. (Previously this defaulted to 5, and the docstring
    even claimed 15 — both wrong; fixed June 2026.)

⚠️  max_tokens and reasoning tokens (docs/working/qa-classification-failures.md,
    2026-10-07). `deepseek-v4-flash` is a REASONING model and bills reasoning
    tokens against max_tokens. At max_tokens=2000 roughly a third of nightly calls
    came back finish_reason="length" with reasoning_tokens == completion_tokens ==
    2000 and EMPTY content; the measured tail needs ~7,133 reasoning + ~700 content
    tokens. Hence MAX_TOKENS=12000 plus a single retry at MAX_TOKENS_RETRY when the
    model still hits the ceiling. Every failure now carries a REASON (logged at
    WARNING, tallied in the progress line, and persisted to classify_failures) so
    the nightly log says why, and so a doc that can never succeed is not re-sent
    every night forever.
"""
import argparse
import json
import logging
import os
import sqlite3
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "documents.db"

# Output budget. See the docstring note: reasoning tokens are billed against this.
MAX_TOKENS = 12_000
MAX_TOKENS_RETRY = 24_000

# Failure reasons returned alongside a None result.
REASON_OK = "ok"
REASON_EMPTY_LENGTH = "empty_content_length"   # finish_reason=length, no content
REASON_EMPTY_OTHER = "empty_content_other"     # empty content, finish_reason!=length
REASON_CONTENT_RISK = "content_risk"           # deterministic 400 from the filter
REASON_JSON = "json_unsalvageable"             # content present, not valid JSON
REASON_HTTP = "http_error"                     # any other API/transport exception
REASON_TIMEOUT = "timeout"
REASON_RATE_LIMIT = "rate_limit_exhausted"     # 3 rate-limit retries used up

# Reasons that can NEVER succeed on a later night — not retried, even with
# --retry-failed. "Content Exists Risk" is a hard, deterministic rejection.
TERMINAL_REASONS = (REASON_CONTENT_RISK,)

# A doc that has failed this many times is skipped unless --retry-failed.
MAX_ATTEMPTS = 3

log = logging.getLogger("classify")

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


def classify_deepseek(doc: dict, model: str, max_tokens: int = MAX_TOKENS,
                      _is_length_retry: bool = False) -> tuple[dict | None, str]:
    """Classify a single document via DeepSeek API.

    Returns (result, reason). `reason` is REASON_OK on success and one of the
    REASON_* failure strings otherwise — never None, so the caller can tally and
    persist WHY a document failed instead of just counting it.

    When the model exhausts its output budget on reasoning (finish_reason ==
    "length"), the call is retried ONCE at MAX_TOKENS_RETRY. No other failure
    class gets that retry — rate limits have their own backoff loop and
    content_risk / unparseable JSON would just burn spend again.
    """
    client = _get_deepseek_client()
    prompt = _build_prompt(doc)

    def _retry_longer(why: str) -> tuple[dict | None, str] | None:
        """Single doubled-budget retry for ceiling hits. None if not applicable."""
        if _is_length_retry or max_tokens >= MAX_TOKENS_RETRY:
            return None
        log.warning("doc %s: %s at max_tokens=%d — retrying once at %d",
                    doc["id"], why, max_tokens, MAX_TOKENS_RETRY)
        return classify_deepseek(doc, model, max_tokens=MAX_TOKENS_RETRY,
                                 _is_length_retry=True)

    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=max_tokens,
            )
            choice = resp.choices[0]
            finish = getattr(choice, "finish_reason", None)
            raw = (choice.message.content or "").strip()

            if not raw:
                if finish == "length":
                    retried = _retry_longer("empty content with finish_reason=length")
                    if retried is not None:
                        return retried
                    log.warning("doc %s: empty content, finish_reason=length, "
                                "budget %d exhausted by reasoning",
                                doc["id"], max_tokens)
                    return None, REASON_EMPTY_LENGTH
                log.warning("doc %s: empty content, finish_reason=%s", doc["id"], finish)
                return None, REASON_EMPTY_OTHER

            result = _parse_response(raw)
            if result is None:
                if finish == "length":
                    retried = _retry_longer("truncated unparseable JSON (finish_reason=length)")
                    if retried is not None:
                        return retried
                log.warning("doc %s: response is not salvageable JSON (finish_reason=%s, "
                            "%d chars): %s", doc["id"], finish, len(raw), raw[:120])
                return None, REASON_JSON

            return result, REASON_OK

        except Exception as e:
            err_str = str(e)
            if "Content Exists Risk" in err_str:
                # Deterministic content-filter rejection — terminal, never retried.
                log.warning("doc %s: content filter rejection (terminal): %s",
                            doc["id"], err_str[:200])
                return None, REASON_CONTENT_RISK
            if "429" in err_str or "rate" in err_str.lower():
                wait = (attempt + 1) * 5
                with _rate_limit_lock:
                    log.warning("doc %s: rate-limited, waiting %ds (attempt %d/3)",
                                doc["id"], wait, attempt + 1)
                time.sleep(wait)
                continue
            if "timeout" in err_str.lower() or "timed out" in err_str.lower():
                log.warning("doc %s: request timeout: %s", doc["id"], err_str[:200])
                return None, REASON_TIMEOUT
            log.warning("doc %s: DeepSeek error (%s): %s",
                        doc["id"], type(e).__name__, err_str[:200])
            return None, REASON_HTTP

    log.warning("doc %s: exhausted rate-limit retries", doc["id"])
    return None, REASON_RATE_LIMIT


# ---------------------------------------------------------------------------
# Ollama backend (local)
# ---------------------------------------------------------------------------

def classify_ollama(doc: dict, model: str) -> tuple[dict | None, str]:
    """Classify a single document via local Ollama. Returns (result, reason)."""
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
        if not raw:
            log.warning("doc %s: empty Ollama response", doc["id"])
            return None, REASON_EMPTY_OTHER
        result = _parse_response(raw)
        if result is None:
            log.warning("doc %s: Ollama response is not salvageable JSON: %s",
                        doc["id"], raw[:120])
            return None, REASON_JSON
        return result, REASON_OK
    except Exception as e:
        err = str(e)
        reason = REASON_TIMEOUT if "timeout" in err.lower() or "timed out" in err.lower() else REASON_HTTP
        log.warning("doc %s: Ollama error (%s): %s", doc["id"], type(e).__name__, err[:200])
        return None, reason


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


def ensure_failure_table(conn):
    """Create the classify_failures side table if absent (idempotent).

    A side table, NOT a column on `documents`: `documents` rows are wide and an
    UPDATE rewrites the body_text_cn overflow pages (see CLAUDE.md's
    compute_scores.py lesson — touching every row once rewrote ~5GB of WAL).
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS classify_failures (
            doc_id     INTEGER PRIMARY KEY,
            reason     TEXT,
            attempts   INTEGER NOT NULL DEFAULT 0,
            first_seen TEXT,
            last_seen  TEXT
        )
    """)
    conn.commit()


def _has_failure_table(conn) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='classify_failures'"
    ).fetchone()
    return row is not None


def record_failure(conn, doc_id: int, reason: str):
    """Upsert a failure, incrementing the attempt counter."""
    conn.execute(
        """INSERT INTO classify_failures (doc_id, reason, attempts, first_seen, last_seen)
           VALUES (?, ?, 1, datetime('now'), datetime('now'))
           ON CONFLICT(doc_id) DO UPDATE SET
               reason    = excluded.reason,
               attempts  = classify_failures.attempts + 1,
               last_seen = excluded.last_seen""",
        (doc_id, reason),
    )


def clear_failure(conn, doc_id: int):
    """A doc that finally classified should not keep a failure record."""
    conn.execute("DELETE FROM classify_failures WHERE doc_id = ?", (doc_id,))


def _format_reasons(tally: Counter) -> str:
    if not tally:
        return "none"
    return " ".join(f"{r}={n:,}" for r, n in tally.most_common())


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


def select_docs(conn, site: str | None = None, limit: int | None = None,
                retry_failed: bool = False) -> list[dict]:
    """Unclassified docs, excluding ones not worth re-sending.

    Skipped: docs with >= MAX_ATTEMPTS recorded failures (unless retry_failed) and
    docs whose last failure was TERMINAL (always — they can never succeed).
    """
    where = ["(d.classified_at IS NULL OR d.classified_at = '')"]
    params: list = []
    if site:
        where.append("d.site_key = ?")
        params.append(site)

    join = ""
    if _has_failure_table(conn):
        join = "LEFT JOIN classify_failures f ON f.doc_id = d.id"
        terminal = ",".join("?" * len(TERMINAL_REASONS))
        guards = [f"f.reason NOT IN ({terminal})"]
        gparams: list = list(TERMINAL_REASONS)
        if not retry_failed:
            guards.append("f.attempts < ?")
            gparams.append(MAX_ATTEMPTS)
        where.append("(f.doc_id IS NULL OR (" + " AND ".join(guards) + "))")
        params.extend(gparams)

    query = f"""
        SELECT d.id, d.title, d.document_number, d.publisher,
               d.body_text_cn, d.classify_main_name
        FROM documents d {join}
        WHERE {' AND '.join(where)}
        ORDER BY d.date_written DESC
    """
    if limit:
        query += f" LIMIT {int(limit)}"

    cols = ["id", "title", "document_number", "publisher", "body_text_cn", "classify_main_name"]
    return [dict(zip(cols, row)) for row in conn.execute(query, params).fetchall()]


def main():
    parser = argparse.ArgumentParser(description="Classify documents with LLM")
    parser.add_argument("--backend", choices=["deepseek", "ollama"], default="deepseek")
    parser.add_argument("--model", help="Override model name")
    parser.add_argument("--site", help="Only classify docs from this site_key")
    parser.add_argument("--limit", type=int, help="Max docs to process")
    parser.add_argument("--dry-run", action="store_true", help="Print results without saving")
    parser.add_argument("--concurrency", type=int, default=2,
                        help="Parallel DeepSeek requests. 2 is the HARD MAX — "
                             "higher silently returns empty responses (not 429s). "
                             "Do not raise.")
    parser.add_argument("--retry-failed", action="store_true",
                        help=f"Also re-send docs with >= {MAX_ATTEMPTS} recorded "
                             "failures (terminal content_risk docs stay excluded)")
    parser.add_argument("--init-schema", action="store_true",
                        help="Create the classify_failures table and exit")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="  [%(levelname)s] %(message)s",
                        stream=sys.stdout)

    if args.init_schema:
        conn = sqlite3.connect(str(DB_PATH), timeout=30)
        conn.execute("PRAGMA busy_timeout=30000")
        ensure_columns(conn)
        ensure_failure_table(conn)
        conn.close()
        print("Schema ready: documents classification columns + classify_failures")
        return

    # Default models per backend
    if args.model is None:
        args.model = "deepseek-v4-flash" if args.backend == "deepseek" else "qwen2.5:14b"

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

    if args.dry_run:
        # --dry-run writes NOTHING — not even schema. Read-only handle.
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=30)
        conn.execute("PRAGMA busy_timeout=30000")
    else:
        conn = sqlite3.connect(str(DB_PATH), timeout=30)
        conn.execute("PRAGMA busy_timeout=30000")
        ensure_columns(conn)
        ensure_failure_table(conn)

    docs = select_docs(conn, site=args.site, limit=args.limit,
                       retry_failed=args.retry_failed)
    total = len(docs)

    print(f"Found {total:,} unclassified documents")
    print(f"Backend: {args.backend} | Model: {args.model}", end="")
    if args.backend == "deepseek":
        print(f" | Concurrency: {args.concurrency}")
        if args.concurrency > 2:
            print(f"⚠️  WARNING: concurrency {args.concurrency} > 2. DeepSeek silently "
                  "returns EMPTY responses above ~2 (not 429s) — docs get marked "
                  "processed with no classification. Recommend --concurrency 2.")
    else:
        print()

    if total == 0:
        print("All documents already classified!")
        return

    start_time = time.time()
    success = 0
    errors = 0
    processed = 0
    reasons: Counter = Counter()

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
                    result, reason = future.result()

                    if result:
                        save_result(conn, doc["id"], result, args.model)
                        clear_failure(conn, doc["id"])
                        success += 1
                    else:
                        record_failure(conn, doc["id"], reason)
                        reasons[reason] += 1
                        errors += 1

                # Commit after each batch
                conn.commit()
                elapsed = time.time() - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                remaining = (total - processed) / rate if rate > 0 else 0
                print(f"  Progress: {processed:,}/{total:,} ({success:,} ok, {errors:,} err) | "
                      f"{rate:.1f} docs/s | ETA: {remaining/60:.0f}m | "
                      f"reasons: {_format_reasons(reasons)}", flush=True)
    else:
        # Sequential execution (Ollama or dry-run)
        for doc in docs:
            result, reason = classify_fn(doc, args.model)
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
                    clear_failure(conn, doc["id"])
                    if processed % 10 == 0:
                        conn.commit()
                success += 1
            else:
                reasons[reason] += 1
                errors += 1
                if not args.dry_run:
                    record_failure(conn, doc["id"], reason)

            if processed % 20 == 0 and not args.dry_run:
                elapsed = time.time() - start_time
                rate = processed / elapsed
                remaining = (total - processed) / rate if rate > 0 else 0
                print(f"  Progress: {processed:,}/{total:,} ({success:,} ok, {errors:,} err) | "
                      f"{rate:.1f} docs/s | ETA: {remaining/60:.0f}m | "
                      f"reasons: {_format_reasons(reasons)}")

        if not args.dry_run:
            conn.commit()

    conn.close()
    elapsed = time.time() - start_time
    print(f"\nDone: {success:,}/{total:,} classified, {errors:,} errors in {elapsed:.0f}s")
    if errors:
        print("Failure reasons:")
        for reason, n in reasons.most_common():
            note = " (terminal — never retried)" if reason in TERMINAL_REASONS else ""
            print(f"  {reason:24s} {n:,}{note}")
        if not args.dry_run:
            print(f"  (recorded in classify_failures; docs at >= {MAX_ATTEMPTS} "
                  "attempts are skipped next run unless --retry-failed)")
    if success > 0 and not args.dry_run:
        # v4-flash is a reasoning model: output = reasoning + content. Measured
        # (qa-classification-failures.md §4): ~1,150-7,133 reasoning + ~200-700
        # content tokens; ~1,600 prompt tokens. Use midpoints.
        est_input = success * 1600
        est_output = success * 2500
        cost = (est_input * 0.28 + est_output * 1.10) / 1_000_000
        print(f"Estimated cost: ~${cost:.2f}")


if __name__ == "__main__":
    main()
