"""Build the AI policy chain from citation analysis.

Extracts both formal (文号) and named (《》) references from AI-related
documents, classifies them by administrative level, and outputs a
structured policy chain as JSON.

Usage:
    python3 scripts/build_ai_chain.py                # Build chain + print summary
    python3 scripts/build_ai_chain.py --json          # Output JSON to stdout
    python3 scripts/build_ai_chain.py --save          # Save to data/ai_chain.json
"""

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from analyze import (
    REF_PATTERN, classify_issuer, get_admin_level,
    NAMED_REF_PATTERN, POLICY_KEYWORDS, EXCLUDE_KEYWORDS,
    is_policy_document, classify_named_ref_level,
)

DB_PATH = Path(__file__).parent.parent / "documents.db"

AI_QUERY = """
SELECT id, site_key, title, document_number, date_published,
       body_text_cn, classify_main_name, publisher
FROM documents
WHERE (title LIKE '%人工智能%' OR keywords LIKE '%人工智能%' OR abstract LIKE '%人工智能%')
  AND body_text_cn IS NOT NULL AND LENGTH(body_text_cn) > 20
ORDER BY date_published DESC
"""


def build_chain():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(AI_QUERY).fetchall()

    # Collect all source documents (the AI docs in our corpus)
    source_docs = {}
    for doc_id, site_key, title, doc_num, date_pub, body, classify, publisher in rows:
        source_docs[doc_id] = {
            "id": doc_id,
            "site_key": site_key,
            "title": title,
            "document_number": doc_num or None,
            "date_published": date_pub,
            "classify": classify,
            "publisher": publisher,
            "admin_level": get_admin_level(doc_num) if doc_num else (
                "district" if site_key.startswith("sz") and site_key not in ("sz", "stic", "fgw", "hrss", "zjj", "swj", "mzj", "sf", "audit", "wjw", "yjgl", "szeb")
                else "municipal" if site_key == "sz"
                else "department"
            ),
        }

    # Extract all citations
    formal_citations = []  # 文号 references
    named_citations = []   # 《》 references

    for doc_id, site_key, title, doc_num, date_pub, body, classify, publisher in rows:
        # Formal citations
        refs = REF_PATTERN.findall(body)
        for ref in refs:
            # Skip self-references
            if doc_num and ref == doc_num:
                continue
            formal_citations.append({
                "source_id": doc_id,
                "source_title": title,
                "cited_ref": ref,
                "cited_level": get_admin_level(ref),
                "citation_type": "formal",
            })

        # Named citations
        named_refs = NAMED_REF_PATTERN.findall(body)
        for name in named_refs:
            if not is_policy_document(name):
                continue
            # Skip self-references
            if name in title:
                continue
            named_citations.append({
                "source_id": doc_id,
                "source_title": title,
                "cited_name": name,
                "cited_level": classify_named_ref_level(name),
                "citation_type": "named",
            })

    # Deduplicate named citations by (source_id, cited_name)
    seen = set()
    unique_named = []
    for c in named_citations:
        key = (c["source_id"], c["cited_name"])
        if key not in seen:
            seen.add(key)
            unique_named.append(c)
    named_citations = unique_named

    # Build the referenced documents list (documents cited but not necessarily in corpus)
    named_ref_counts = Counter(c["cited_name"] for c in named_citations)
    formal_ref_counts = Counter(c["cited_ref"] for c in formal_citations)

    # Try to match named references to documents in our corpus
    all_docs = conn.execute(
        "SELECT id, title, document_number, site_key, date_published FROM documents"
    ).fetchall()
    title_index = {row[1]: row for row in all_docs}

    referenced_policies = []
    for name, count in named_ref_counts.most_common():
        level = classify_named_ref_level(name)
        # Try to find in corpus
        in_corpus = None
        for db_title, db_row in title_index.items():
            if name in db_title or db_title in name:
                in_corpus = {
                    "id": db_row[0],
                    "title": db_row[1],
                    "document_number": db_row[2],
                    "site_key": db_row[3],
                    "date_published": db_row[4],
                }
                break

        referenced_policies.append({
            "name": name,
            "level": level,
            "citation_count": count,
            "in_corpus": in_corpus is not None,
            "corpus_match": in_corpus,
        })

    # Build the chain structure
    chain = {
        "topic": "Artificial Intelligence (人工智能)",
        "scope": "Shenzhen",
        "generated": str(Path(__file__).name),
        "stats": {
            "source_documents": len(source_docs),
            "formal_citations": len(formal_citations),
            "named_citations": len(named_citations),
            "unique_referenced_policies": len(referenced_policies),
        },
        "hierarchy": {
            "central": [p for p in referenced_policies if p["level"] == "central"],
            "provincial": [p for p in referenced_policies if p["level"] == "provincial"],
            "municipal": [p for p in referenced_policies if p["level"] == "municipal"],
            "district": [p for p in referenced_policies if p["level"] == "district"],
            "unknown": [p for p in referenced_policies if p["level"] == "unknown"],
        },
        "source_documents_by_level": {
            "department": [d for d in source_docs.values() if d["admin_level"] == "department"],
            "district": [d for d in source_docs.values() if d["admin_level"] == "district"],
            "municipal": [d for d in source_docs.values() if d["admin_level"] == "municipal"],
        },
        "formal_citations": formal_citations,
        "named_citations": named_citations,
    }

    conn.close()
    return chain


def print_summary(chain):
    stats = chain["stats"]
    print(f"\n=== AI Policy Chain: Shenzhen ===\n")
    print(f"Source documents analyzed: {stats['source_documents']}")
    print(f"Formal (文号) citations: {stats['formal_citations']}")
    print(f"Named (《》) policy citations: {stats['named_citations']}")
    print(f"Unique referenced policies: {stats['unique_referenced_policies']}")

    for level in ["central", "provincial", "municipal", "district"]:
        policies = chain["hierarchy"][level]
        if policies:
            print(f"\n--- {level.upper()} level ({len(policies)} policies) ---")
            for p in policies:
                corpus = " [IN CORPUS]" if p["in_corpus"] else ""
                print(f"  [{p['citation_count']}x]《{p['name']}》{corpus}")

    unknown = chain["hierarchy"]["unknown"]
    if unknown:
        print(f"\n--- UNCLASSIFIED ({len(unknown)} policies) ---")
        for p in sorted(unknown, key=lambda x: -x["citation_count"])[:10]:
            corpus = " [IN CORPUS]" if p["in_corpus"] else ""
            print(f"  [{p['citation_count']}x]《{p['name']}》{corpus}")

    # Show which source docs have formal policy doc numbers
    print(f"\n--- Source documents with 文号 (formal policy docs) ---")
    for level_name, docs in chain["source_documents_by_level"].items():
        formal = [d for d in docs if d["document_number"]]
        if formal:
            for d in formal:
                print(f"  [{d['admin_level']}] {d['document_number']} — {d['title'][:60]}")


def main():
    parser = argparse.ArgumentParser(description="Build AI policy chain")
    parser.add_argument("--json", action="store_true", help="Output JSON to stdout")
    parser.add_argument("--save", action="store_true", help="Save to data/ai_chain.json")
    args = parser.parse_args()

    chain = build_chain()

    if args.json:
        print(json.dumps(chain, ensure_ascii=False, indent=2))
    elif args.save:
        out_dir = Path(__file__).parent.parent / "data"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / "ai_chain.json"
        with open(out_path, "w") as f:
            json.dump(chain, f, ensure_ascii=False, indent=2)
        print(f"Saved to {out_path}")
        print_summary(chain)
    else:
        print_summary(chain)


if __name__ == "__main__":
    main()
