"""Side-by-side comparison of deep-translator (Google free) vs DeepSeek
for translating untranslated Chinese policy-document titles.

Reads ~30 diverse untranslated titles from documents.db, runs both
translators, and prints a side-by-side table. Does NOT modify the DB.

Usage:
    python3 scripts/translate_titles_compare.py
    python3 scripts/translate_titles_compare.py --sample 40

Env: requires DEEPSEEK_API_KEY (loaded from .env automatically).
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from pathlib import Path

# Load .env so DEEPSEEK_API_KEY is available
ENV_PATH = Path(__file__).parent.parent / ".env"
if ENV_PATH.exists():
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"'))

from deep_translator import GoogleTranslator   # noqa: E402
from openai import OpenAI                       # noqa: E402

DB_PATH = Path(__file__).parent.parent / "documents.db"

# Sample N titles from each of these representative site buckets, so the
# comparison spans laws, municipal notices, media headlines, and central
# ministry releases.
SAMPLE_SITES = ["npc", "suzhou", "guancha", "mofcom", "samr", "cac", "stdaily"]
PER_SITE = 5


def _sample_titles(n_per_site: int) -> list[tuple[int, str, str]]:
    """Return [(id, site_key, title)] sampled across diverse sites."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA query_only = 1")
    rows: list[tuple[int, str, str]] = []
    for site in SAMPLE_SITES:
        cur = conn.execute(
            """SELECT id, site_key, title FROM documents
               WHERE site_key = ?
                 AND (title_en IS NULL OR title_en = '')
                 AND title IS NOT NULL AND title != ''
               ORDER BY RANDOM() LIMIT ?""",
            (site, n_per_site),
        )
        rows.extend(cur.fetchall())
    conn.close()
    return rows


def _google_translate(text: str) -> str:
    """Translate via deep-translator (Google free web endpoint)."""
    return GoogleTranslator(source="zh-CN", target="en").translate(text)


_deepseek = None
def _deepseek_client() -> OpenAI:
    global _deepseek
    if _deepseek is None:
        _deepseek = OpenAI(
            api_key=os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
        )
    return _deepseek


def _deepseek_translate(text: str) -> str:
    """Translate one title via DeepSeek chat completion. Cheap (~$0.0001)."""
    resp = _deepseek_client().chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content":
                "You translate Chinese government document titles to English. "
                "Output ONLY the English translation, nothing else. Preserve "
                "official terminology. Keep it concise."},
            {"role": "user", "content": text},
        ],
        max_tokens=200,
        temperature=0.0,
    )
    return resp.choices[0].message.content.strip()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--per-site", type=int, default=PER_SITE,
                   help=f"titles per site (default {PER_SITE})")
    p.add_argument("--json-out", default="/tmp/translation_compare.json",
                   help="write structured output here for re-viewing")
    args = p.parse_args()

    samples = _sample_titles(args.per_site)
    if not samples:
        print("No untranslated titles to sample.")
        return

    results = []
    print(f"Comparing {len(samples)} titles across {len(SAMPLE_SITES)} sites…\n")
    print("=" * 100)

    t_google = 0.0
    t_deepseek = 0.0

    for i, (doc_id, site, title) in enumerate(samples, 1):
        # Google via deep-translator
        t0 = time.time()
        try:
            g = _google_translate(title)
        except Exception as e:                  # noqa: BLE001
            g = f"[ERROR: {e}]"
        t_google += time.time() - t0

        # DeepSeek
        t0 = time.time()
        try:
            d = _deepseek_translate(title)
        except Exception as e:                  # noqa: BLE001
            d = f"[ERROR: {e}]"
        t_deepseek += time.time() - t0

        print(f"\n[{i:>2}] {site:<10} doc_id={doc_id}")
        print(f"  ZH       │ {title}")
        print(f"  Google   │ {g}")
        print(f"  DeepSeek │ {d}")

        results.append({
            "id": doc_id, "site": site, "zh": title,
            "google": g, "deepseek": d,
        })

    print("\n" + "=" * 100)
    print(f"Total runtime: Google {t_google:.1f}s, DeepSeek {t_deepseek:.1f}s")
    print(f"Per-title:     Google {t_google/len(samples):.2f}s, "
          f"DeepSeek {t_deepseek/len(samples):.2f}s")

    Path(args.json_out).write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved structured results to {args.json_out}")


if __name__ == "__main__":
    main()
