"""Link China Law Translate posts to native corpus docs.

Each CLT post stores its original Chinese source URL in `relation` as
"cn_source=<URL>;lang_ratio=<0.0-1.0>". We match those URLs to native docs
in our corpus (normalizing http/https) and:

  1) Copy CLT's slug-derived English title onto the native doc's title_en
     (only if the native doc currently has no English title).
  2) For CLT posts whose body is mostly English (lang_ratio < 0.5),
     copy the body to the native doc's body_text_en.

Usage:
    python3 scripts/match_clt_translations.py --dry-run   # preview matches
    python3 scripts/match_clt_translations.py             # apply
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "documents.db"


def normalize_url(u: str) -> str:
    if not u:
        return ""
    u = u.strip()
    if u.startswith("https://"):
        u = u[8:]
    elif u.startswith("http://"):
        u = u[7:]
    return u.rstrip("/")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--db", default=str(DB_PATH))
    args = p.parse_args()

    conn = sqlite3.connect(args.db, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")

    # Pull all CLT docs with a source URL.
    rows = conn.execute(
        """SELECT id, title, title_en, summary_en, body_text_cn, relation
           FROM documents
           WHERE site_key = 'chinalawtranslate'
             AND relation LIKE 'cn_source=http%'"""
    ).fetchall()

    # Build {normalized_url: native_doc_id} index from non-CLT docs.
    print(f"CLT docs with source URL: {len(rows)}")
    print("Indexing native URLs…")
    url_index: dict[str, int] = {}
    cur = conn.execute(
        "SELECT id, url FROM documents WHERE site_key != 'chinalawtranslate' AND url != ''"
    )
    for native_id, native_url in cur:
        url_index[normalize_url(native_url)] = native_id
    print(f"  → {len(url_index)} native URLs indexed")

    matched = 0
    titled = 0
    bodied = 0
    samples: list[tuple[str, str]] = []

    for clt_id, clt_title, clt_title_en, clt_summary, clt_body, relation in rows:
        # parse: cn_source=URL;lang_ratio=X
        try:
            cn_part, lr_part = relation.split(";")
            cn_url = cn_part.replace("cn_source=", "")
            lang_ratio = float(lr_part.replace("lang_ratio=", ""))
        except ValueError:
            continue
        if not cn_url:
            continue

        native_id = url_index.get(normalize_url(cn_url))
        if not native_id:
            continue

        matched += 1

        # English title — write only if native has none, and only when
        # title_en is meaningful (slug-derived, not falling back to Chinese)
        en_title = clt_title_en or clt_title
        en_title_clean = (
            en_title if en_title and not any("一" <= c <= "鿿" for c in en_title) else ""
        )

        # Body — only copy when CLT post is genuinely English-heavy
        body_to_copy = clt_body if lang_ratio < 0.5 and clt_body else ""

        if not args.dry_run:
            sets, vals = [], []
            # Title
            cur_title = conn.execute(
                "SELECT title_en FROM documents WHERE id = ?", (native_id,)
            ).fetchone()[0]
            if en_title_clean and (not cur_title or cur_title == ""):
                sets.append("title_en = ?")
                vals.append(en_title_clean)
                titled += 1
            if body_to_copy:
                sets.append("body_text_en = ?")
                vals.append(body_to_copy)
                if clt_summary:
                    sets.append("summary_en = ?")
                    vals.append(clt_summary)
                bodied += 1
            if sets:
                vals.append(native_id)
                conn.execute(
                    f"UPDATE documents SET {', '.join(sets)} WHERE id = ?", vals
                )
        else:
            if en_title_clean and len(samples) < 8:
                samples.append((en_title_clean[:50], cn_url[:60]))
            if en_title_clean:
                titled += 1
            if body_to_copy:
                bodied += 1

    if not args.dry_run:
        conn.commit()

    print()
    print(f"URL-matched: {matched} CLT posts")
    print(f"  → English titles applied: {titled}")
    print(f"  → English bodies applied: {bodied}")
    if args.dry_run and samples:
        print()
        print("Sample matches (would-apply title → CN source URL):")
        for t, u in samples:
            print(f"  • {t} → {u}")


if __name__ == "__main__":
    main()
