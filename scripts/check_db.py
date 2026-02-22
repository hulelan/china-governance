"""Check database state and run cross-reference analysis."""
import sqlite3
import re
from collections import Counter
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "documents.db"

conn = sqlite3.connect(str(DB_PATH))

total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
with_body = conn.execute("SELECT COUNT(*) FROM documents WHERE body_text_cn != ''").fetchone()[0]
with_docnum = conn.execute("SELECT COUNT(*) FROM documents WHERE document_number != ''").fetchone()[0]

print(f"Total documents: {total}")
print(f"With body text: {with_body}")
print(f"With document number: {with_docnum}")

# Show sites
sites = conn.execute("SELECT site_key, name FROM sites").fetchall()
for key, name in sites:
    count = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE site_key = ?", (key,)
    ).fetchone()[0]
    body_count = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE site_key = ? AND body_text_cn != ''",
        (key,),
    ).fetchone()[0]
    print(f"  {name}: {count} docs ({body_count} with body)")

# Sample a document with body text
row = conn.execute(
    "SELECT title, document_number, publisher, body_text_cn "
    "FROM documents WHERE body_text_cn != '' AND document_number != '' LIMIT 1"
).fetchone()
if row:
    print(f"\nSample document:")
    print(f"  Title: {row[0][:80]}")
    print(f"  Document #: {row[1]}")
    print(f"  Publisher: {row[2]}")
    print(f"  Body (first 300 chars): {row[3][:300]}")

# Cross-reference analysis
rows = conn.execute(
    "SELECT id, body_text_cn FROM documents WHERE body_text_cn != ''"
).fetchall()

docs_with_refs = 0
all_refs = []
# Pattern: Chinese chars + bracket + year + bracket + number + 号
ref_pattern = re.compile(
    r"([\u4e00-\u9fff]+[\u3014\u3008\u300a\uff08\u2018\u301a]"
    r"(?:19|20)\d{2}"
    r"[\u3015\u3009\u300b\uff09\u2019\u301b]"
    r"\d+\u53f7)"
)

for doc_id, body in rows:
    refs = ref_pattern.findall(body)
    if refs:
        docs_with_refs += 1
        all_refs.extend(refs)

print(f"\nCross-reference analysis ({len(rows)} docs with body text):")
print(f"  Documents containing references: {docs_with_refs}/{len(rows)}")
print(f"  Total references found: {len(all_refs)}")
if all_refs:
    top = Counter(all_refs).most_common(15)
    print(f"  Top referenced documents:")
    for ref, count in top:
        print(f"    {ref}: {count} citations")

conn.close()
