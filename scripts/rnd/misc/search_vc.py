"""Search corpus for venture capital related content."""
import sqlite3

conn = sqlite3.connect("documents.db")

# Key Chinese terms for venture capital / VC
terms = {
    "创业投资": "venture capital (formal)",
    "风险投资": "venture/risk capital",
    "创投": "VC (abbreviation)",
    "风投": "VC (colloquial)",
    "政府引导基金": "government guidance fund",
    "股权投资": "equity investment",
    "天使投资": "angel investment",
    "基金": "fund (broad)",
}

print("=== Venture Capital in the Corpus ===\n")

for term, eng in terms.items():
    # Search titles
    title_count = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE title LIKE ?", (f"%{term}%",)
    ).fetchone()[0]
    # Search body text
    body_count = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE body_text_cn LIKE ?", (f"%{term}%",)
    ).fetchone()[0]
    if title_count > 0 or body_count > 0:
        print(f"  {term} ({eng})")
        print(f"    In titles: {title_count}, In body text: {body_count}")

# Show actual documents with VC-specific terms in title
print("\n\n=== Documents with VC terms in title ===\n")
vc_terms = ["创业投资", "风险投资", "创投", "风投", "政府引导基金", "天使投资"]
for term in vc_terms:
    rows = conn.execute(
        """SELECT d.id, d.title, d.document_number, d.site_key, s.name, s.admin_level,
                  CASE WHEN d.body_text_cn IS NOT NULL AND d.body_text_cn != '' THEN 'yes' ELSE 'no' END as has_body
           FROM documents d
           JOIN sites s ON s.site_key = d.site_key
           WHERE d.title LIKE ?
           ORDER BY d.date_written DESC
           LIMIT 15""",
        (f"%{term}%",)
    ).fetchall()
    if rows:
        print(f"\n--- {term} ---")
        for doc_id, title, docnum, sk, site_name, level, has_body in rows:
            docnum_str = f" [{docnum}]" if docnum else ""
            print(f"  [{level:10s}] {title[:70]}{docnum_str}")
            print(f"              site={site_name}, id={doc_id}, body={has_body}")

# Show some with 股权投资 in title (equity investment, closely related)
rows = conn.execute(
    """SELECT d.id, d.title, d.document_number, s.name, s.admin_level
       FROM documents d JOIN sites s ON s.site_key = d.site_key
       WHERE d.title LIKE '%股权投资%'
       ORDER BY d.date_written DESC LIMIT 10"""
).fetchall()
if rows:
    print(f"\n--- 股权投资 (equity investment) ---")
    for doc_id, title, docnum, site_name, level in rows:
        docnum_str = f" [{docnum}]" if docnum else ""
        print(f"  [{level:10s}] {title[:70]}{docnum_str}")
