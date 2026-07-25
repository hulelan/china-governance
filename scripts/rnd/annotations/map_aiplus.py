"""Map AI-relevant corpus documents onto the AI+ taxonomy via DeepSeek.

For each medium+ AI-relevance document (ai_relevance >= threshold), ask DeepSeek
which AI+ item(s) (国发〔2025〕11号, 25 leaf items) the document substantively
advances, and record the mapping in the `aiplus_map` table. Powers the
Annotations pages (each item -> its documents).

Resumable: docs already in aiplus_map (incl. a '__none__' sentinel for docs that
map to nothing) are skipped. Concurrency 2 (DeepSeek's hard max — see
scripts/classify_documents.py).

Usage (on the droplet, where DEEPSEEK_API_KEY + documents.db live):
    set -a; source .env; set +a
    python3 scripts/rnd/annotations/map_aiplus.py --limit 40   # sample
    python3 scripts/rnd/annotations/map_aiplus.py              # full run
"""
import argparse
import json
import os
import re
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[3]
DB = ROOT / "documents.db"
TAXO = ROOT / "data" / "aiplus_taxonomy.yaml"
MODEL = "deepseek-chat"
MIN_AI = 0.3
NONE = "__none__"

_ITEMS = yaml.safe_load(TAXO.open(encoding="utf-8"))["items"]
_IDS = {it["id"] for it in _ITEMS}
_client = None
_lock = threading.Lock()


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
                         base_url="https://api.deepseek.com", max_retries=2, timeout=60.0)
    return _client


def _taxonomy_block() -> str:
    lines = []
    for it in _ITEMS:
        lines.append(f'{it["id"]} [{it["group"]}] {it["cn"]} / {it["en"]}: {it["desc"]}')
    return "\n".join(lines)


_TAXO_BLOCK = _taxonomy_block()


def _build_prompt(doc: dict) -> str:
    return (
        "You are mapping a Chinese government / policy document onto China's "
        '"AI Plus" (人工智能+) action plan (国发〔2025〕11号). Below are its 25 items.\n\n'
        f"{_TAXO_BLOCK}\n\n"
        "DOCUMENT:\n"
        f"Title (zh): {doc.get('title','')}\n"
        f"Title (en): {doc.get('title_en','')}\n"
        f"Summary: {doc.get('summary_en','')}\n\n"
        "Which item(s) does this document SUBSTANTIVELY advance, implement, or "
        "report progress on? Judge by the document's core subject, not passing "
        "mentions. Most documents map to 0-3 items. If none clearly apply, return "
        'an empty list.\n'
        'Respond ONLY with a JSON array of item ids, e.g. ["gov-social","found-compute"]. '
        "No prose."
    )


def _parse(raw: str) -> list:
    m = re.search(r"\[.*?\]", raw, re.S)
    if not m:
        return []
    try:
        arr = json.loads(m.group(0))
    except Exception:
        return []
    return [x for x in arr if isinstance(x, str) and x in _IDS]


def _map_one(doc: dict, model: str):
    client = _get_client()
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=model, temperature=0.0, max_tokens=120,
                messages=[{"role": "user", "content": _build_prompt(doc)}])
            raw = (resp.choices[0].message.content or "").strip()
            return doc["id"], _parse(raw)
        except Exception as e:
            s = str(e)
            if "429" in s or "rate" in s.lower():
                with _lock:
                    time.sleep((attempt + 1) * 5)
                continue
            if "Content Exists Risk" in s:
                return doc["id"], []
            return doc["id"], None       # error → don't mark done, retry next run
    return doc["id"], None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="cap docs this run (sample)")
    ap.add_argument("--min-ai", type=float, default=MIN_AI)
    ap.add_argument("--concurrency", type=int, default=2)
    ap.add_argument("--model", default=MODEL)
    args = ap.parse_args()

    if not os.environ.get("DEEPSEEK_API_KEY"):
        sys.exit("DEEPSEEK_API_KEY not set (source .env first)")

    conn = sqlite3.connect(str(DB), timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("CREATE TABLE IF NOT EXISTS aiplus_map "
                 "(doc_id INTEGER NOT NULL, item_id TEXT NOT NULL, "
                 "PRIMARY KEY (doc_id, item_id))")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_aiplus_map_item ON aiplus_map(item_id)")
    conn.commit()

    rows = conn.execute(
        "SELECT id, title, title_en, summary_en FROM documents "
        "WHERE ai_relevance >= ? AND id NOT IN (SELECT DISTINCT doc_id FROM aiplus_map) "
        "ORDER BY ai_relevance DESC" + (f" LIMIT {args.limit}" if args.limit else ""),
        (args.min_ai,)).fetchall()
    docs = [{"id": r[0], "title": r[1], "title_en": r[2], "summary_en": r[3]} for r in rows]
    print(f"[map] {len(docs)} docs to map (min_ai={args.min_ai}, conc={args.concurrency})", flush=True)

    done = mapped = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = [ex.submit(_map_one, d, args.model) for d in docs]
        for fut in as_completed(futs):
            doc_id, items = fut.result()
            if items is None:                 # error — skip (retried next run)
                continue
            recs = [(doc_id, it) for it in items] or [(doc_id, NONE)]
            conn.executemany("INSERT OR IGNORE INTO aiplus_map (doc_id, item_id) VALUES (?,?)", recs)
            done += 1
            mapped += len(items)
            if done % 25 == 0:
                conn.commit()
                print(f"  {done}/{len(docs)} processed · {mapped} tags", flush=True)
    conn.commit()
    print(f"[map] done: {done} processed, {mapped} tags", flush=True)
    # distribution
    dist = conn.execute("SELECT item_id, COUNT(*) c FROM aiplus_map WHERE item_id!=? "
                        "GROUP BY item_id ORDER BY c DESC", (NONE,)).fetchall()
    print("[map] tags per item:")
    for iid, c in dist:
        print(f"    {iid:16} {c}")
    conn.close()


if __name__ == "__main__":
    main()
