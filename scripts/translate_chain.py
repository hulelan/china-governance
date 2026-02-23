"""Translate AI policy chain documents to English.

Supports two backends:
  - openai:  GPT-4o-mini via OpenAI API (cheap, good quality) — default
  - ollama:  Qwen2.5 via local Ollama server (free, runs on your Mac)

Usage:
    # OpenAI (needs OPENAI_API_KEY)
    python3 scripts/translate_chain.py --dry-run
    python3 scripts/translate_chain.py --limit 5
    python3 scripts/translate_chain.py --doc-id 11839311

    # Ollama / Qwen (needs: brew install ollama && ollama pull qwen2.5:14b)
    python3 scripts/translate_chain.py --backend ollama
    python3 scripts/translate_chain.py --backend ollama --model qwen2.5:7b

    # Options
    --dry-run       Show what would be translated + cost estimate
    --limit N       Max documents to translate (default: 10)
    --doc-id ID     Translate a single document
    --backend       openai or ollama (default: openai)
    --model         Override model name
"""

import argparse
import json
import logging
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "documents.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Glossary — keeps translations consistent across all documents
# ---------------------------------------------------------------------------

GOVT_BODY_GLOSSARY = {
    # Central
    "国务院": "State Council",
    "国务院办公厅": "General Office of the State Council",
    "科技部": "Ministry of Science and Technology",
    "工业和信息化部": "Ministry of Industry and Information Technology",
    "教育部": "Ministry of Education",
    "广东省人民政府": "People's Government of Guangdong Province",
    # Shenzhen Municipal
    "深圳市人民政府": "Shenzhen Municipal People's Government",
    "深圳市人民政府办公厅": "General Office of Shenzhen Municipal People's Government",
    "深圳市科技创新局": "Shenzhen Bureau of Science, Technology and Innovation",
    "深圳市发展和改革委员会": "Shenzhen Development and Reform Commission",
    "深圳市工业和信息化局": "Shenzhen Bureau of Industry and Information Technology",
    "深圳市人力资源和社会保障局": "Shenzhen Bureau of Human Resources and Social Security",
    "深圳市市场监督管理局": "Shenzhen Market Supervision Administration",
    "深圳市教育局": "Shenzhen Bureau of Education",
    "深圳市卫生健康委员会": "Shenzhen Health Commission",
    "深圳市司法局": "Shenzhen Bureau of Justice",
    "深圳市商务局": "Shenzhen Bureau of Commerce",
    # Longhua District
    "龙华区人民政府": "Longhua District People's Government",
    "龙华区人民政府办公室": "General Office of Longhua District People's Government",
    "龙华区科技创新局": "Longhua District Bureau of Science, Technology and Innovation",
    "龙华区发展和改革局": "Longhua District Development and Reform Bureau",
    # Other Districts
    "南山区": "Nanshan District",
    "坪山区": "Pingshan District",
    "福田区": "Futian District",
    "光明区": "Guangming District",
    "罗湖区": "Luohu District",
    "宝安区": "Bao'an District",
    "龙岗区": "Longgang District",
}

POLICY_GLOSSARY = {
    # Document types
    "若干措施": "Several Measures",
    "行动方案": "Action Plan",
    "实施方案": "Implementation Plan",
    "实施意见": "Implementation Opinions",
    "实施细则": "Implementation Rules",
    "管理办法": "Administrative Measures",
    "暂行办法": "Interim Measures",
    "政策解读": "Policy Interpretation",
    # AI/tech
    "人工智能": "artificial intelligence (AI)",
    "大模型": "large model",
    "大语言模型": "large language model (LLM)",
    "算力": "computing power",
    "智算中心": "intelligent computing center",
    "具身智能": "embodied intelligence",
    "生成式人工智能": "generative AI",
    "数字经济": "digital economy",
    "应用场景": "application scenarios",
    # Industrial policy
    "新质生产力": "new quality productive forces",
    "高质量发展": "high-quality development",
    "产业集群": "industrial cluster",
    "产业链": "industrial chain",
    "揭榜挂帅": "open competition mechanism",
    "营商环境": "business environment",
    "专精特新": "specialized, refined, distinctive, and innovative (SRDI)",
    # Fiscal
    "扶持资金": "support funds",
    "奖励补贴": "incentive subsidies",
    "事后资助": "post-event subsidy",
    "一事一议": "case-by-case deliberation",
    # Places
    "粤港澳大湾区": "Guangdong-Hong Kong-Macao Greater Bay Area",
    "龙华中轴": "Longhua Central Axis",
}


def build_glossary_section(cn_text: str) -> str:
    """Build a glossary of terms that actually appear in this document."""
    relevant = {}
    for glossary in [GOVT_BODY_GLOSSARY, POLICY_GLOSSARY]:
        for cn, en in glossary.items():
            if cn in cn_text:
                relevant[cn] = en
    if not relevant:
        return ""
    lines = ["\nMANDATORY TERMINOLOGY (use these exact translations):"]
    for cn, en in relevant.items():
        lines.append(f"  {cn} → {en}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_BASE = """You are a professional translator specializing in Chinese government policy documents.

TARGET AUDIENCE: Western policy analysts who need accurate, readable translations.

APPROACH:
- Produce faithful, professional English preserving the document's legal/policy meaning
- Preserve document structure: article numbers (第X条), chapter headings (第X章), section breaks
- Maintain the formal register — do not casualize the tone
- Where a Chinese term has no clean English equivalent, translate it and append the Chinese in parentheses on FIRST occurrence only
- Preserve document numbers (文号) EXACTLY as written, e.g., 深龙华府办规〔2024〕20号 — do NOT translate them

Return a JSON object with these fields:
- "title_en": the translated document title
- "body_en": the full translated body text

Output ONLY valid JSON. No markdown formatting, no commentary."""


def build_system_prompt(cn_text: str) -> str:
    """Build the full system prompt with document-specific glossary."""
    return SYSTEM_PROMPT_BASE + build_glossary_section(cn_text)


# ---------------------------------------------------------------------------
# Translation backends
# ---------------------------------------------------------------------------

def translate_openai(title: str, body: str, model: str) -> dict:
    """Translate via OpenAI API (GPT-4o-mini by default)."""
    from openai import OpenAI
    client = OpenAI()

    full_text = title + "\n" + body
    system_prompt = build_system_prompt(full_text)
    max_tokens = min(max(2000, int(len(body) * 2.5)), 16000)

    source = f"标题: {title}\n\n正文:\n{body}"

    resp = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Translate this Chinese government document:\n\n{source}"},
        ],
        response_format={"type": "json_object"},
    )
    text = resp.choices[0].message.content.strip()
    return _parse_json_response(text, title)


def translate_ollama(title: str, body: str, model: str) -> dict:
    """Translate via local Ollama server (Qwen2.5 by default)."""
    import urllib.request

    full_text = title + "\n" + body
    system_prompt = build_system_prompt(full_text)
    max_tokens = min(max(2000, int(len(body) * 2.5)), 16000)

    source = f"标题: {title}\n\n正文:\n{body}"

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Translate this Chinese government document:\n\n{source}"},
        ],
        "stream": False,
        "format": "json",
        "options": {"num_predict": max_tokens},
    }).encode()

    req = urllib.request.Request(
        "http://localhost:11434/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        result = json.loads(resp.read())

    text = result["message"]["content"].strip()
    return _parse_json_response(text, title)


def _parse_json_response(text: str, original_title: str) -> dict:
    """Parse JSON from LLM response, with fallback."""
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        result = json.loads(text)
        return {
            "title_en": result.get("title_en", ""),
            "body_en": result.get("body_en", text),
        }
    except json.JSONDecodeError:
        log.warning("  JSON parse failed, using raw text as body_en")
        return {"title_en": "", "body_en": text}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_translation(doc_id, cn_body, en_body, doc_num) -> list[str]:
    """Quick automated checks on a translation."""
    warnings = []
    if not en_body:
        return ["EMPTY translation"]

    # Length ratio: English should be 1.0x-5.0x the Chinese char count
    ratio = len(en_body) / max(len(cn_body), 1)
    if ratio < 0.8:
        warnings.append(f"SHORT: EN/CN ratio={ratio:.2f} (possible truncation)")
    if ratio > 6.0:
        warnings.append(f"LONG: EN/CN ratio={ratio:.2f} (possible hallucination)")

    # Document number preserved
    if doc_num and doc_num not in en_body:
        warnings.append(f"MISSING 文号: {doc_num}")

    # Untranslated Chinese runs (>15 consecutive CJK chars in the English)
    cn_runs = re.findall(r"[\u4e00-\u9fff]{15,}", en_body)
    for run in cn_runs:
        warnings.append(f"UNTRANSLATED: ...{run[:25]}...")

    # Key proper nouns
    if "龙华" in cn_body and "Longhua" not in en_body:
        warnings.append("MISSING: 龙华/Longhua")
    if "深圳" in cn_body and "Shenzhen" not in en_body:
        warnings.append("MISSING: 深圳/Shenzhen")

    return warnings


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

PRIORITY_QUERY = """
SELECT id, title, body_text_cn, document_number, site_key
FROM documents
WHERE (title LIKE '%人工智能%' OR keywords LIKE '%人工智能%' OR abstract LIKE '%人工智能%')
  AND body_text_cn IS NOT NULL AND LENGTH(body_text_cn) > 20
  AND (body_text_en IS NULL OR body_text_en = '')
ORDER BY
    (document_number IS NOT NULL AND document_number <> '') DESC,
    LENGTH(body_text_cn) DESC
"""


def main():
    parser = argparse.ArgumentParser(description="Translate AI chain documents")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--doc-id", type=int, help="Translate a single document")
    parser.add_argument("--limit", type=int, default=10, help="Max documents to translate")
    parser.add_argument(
        "--backend", choices=["openai", "ollama"], default="openai",
        help="Translation backend (default: openai)",
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help="Model name (default: gpt-4o-mini for openai, qwen2.5:14b for ollama)",
    )
    args = parser.parse_args()

    # Resolve model
    if args.model:
        model = args.model
    elif args.backend == "ollama":
        model = "qwen2.5:14b"
    else:
        model = "gpt-4o-mini"

    # Check prerequisites
    if args.backend == "openai" and not args.dry_run:
        if not os.environ.get("OPENAI_API_KEY"):
            print("Error: OPENAI_API_KEY environment variable required")
            print("  export OPENAI_API_KEY=sk-...")
            sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    if args.doc_id:
        rows = conn.execute(
            "SELECT id, title, body_text_cn, document_number, site_key FROM documents WHERE id = ?",
            (args.doc_id,),
        ).fetchall()
    else:
        rows = conn.execute(PRIORITY_QUERY).fetchall()

    rows = rows[:args.limit]
    log.info(f"Found {len(rows)} documents to translate via {args.backend} ({model})")

    if args.dry_run:
        for row in rows:
            chars = len(row["body_text_cn"]) if row["body_text_cn"] else 0
            marker = f" [{row['document_number']}]" if row["document_number"] else ""
            print(f"  {row['id']} ({row['site_key']}){marker} {chars} chars — {row['title'][:60]}")
        total_chars = sum(len(r["body_text_cn"]) for r in rows if r["body_text_cn"])
        if args.backend == "openai":
            est_cost = total_chars * 0.75 / 1_000_000  # rough GPT-4o-mini estimate
            print(f"\nEstimated: ~{total_chars:,} chars, ~${est_cost:.3f} (GPT-4o-mini)")
        else:
            print(f"\nEstimated: ~{total_chars:,} chars, free (local Ollama)")
        return

    # Pick the translate function
    translate_fn = translate_ollama if args.backend == "ollama" else translate_openai

    success = 0
    qa_warnings = []

    for i, row in enumerate(rows):
        doc_id = row["id"]
        title = row["title"]
        body = row["body_text_cn"]
        doc_num = row["document_number"]
        marker = f" [{doc_num}]" if doc_num else ""
        log.info(f"[{i+1}/{len(rows)}] Translating {doc_id}{marker} — {title[:50]}")

        try:
            result = translate_fn(title, body, model)
            title_en = result["title_en"]
            body_en = result["body_en"]

            # Validate
            warnings = validate_translation(doc_id, body, body_en, doc_num)
            if warnings:
                for w in warnings:
                    log.warning(f"  QA: {w}")
                qa_warnings.append((doc_id, title[:40], warnings))

            # Save
            conn.execute(
                "UPDATE documents SET title_en = ?, body_text_en = ? WHERE id = ?",
                (title_en, body_en, doc_id),
            )
            conn.commit()
            success += 1
            log.info(f"  OK — {len(body_en)} chars EN, title: {title_en[:60]}")

        except Exception as e:
            log.error(f"  FAILED: {e}")

        # Rate limit for API, no delay needed for local
        if args.backend == "openai":
            time.sleep(0.3)

    log.info(f"Done: {success}/{len(rows)} translated")

    if qa_warnings:
        log.info(f"\nQA warnings for {len(qa_warnings)} documents:")
        for doc_id, title, warnings in qa_warnings:
            log.info(f"  {doc_id} — {title}")
            for w in warnings:
                log.info(f"    - {w}")

    conn.close()


if __name__ == "__main__":
    main()
