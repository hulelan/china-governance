"""Export the citation network as CSV for visualization."""
import csv
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

DB_PATH = Path(__file__).parent / "documents.db"

REF_PATTERN = re.compile(
    r"([\u4e00-\u9fff]+[\u3014\u3008\u300a\uff08\u2018\u301a]"
    r"(?:19|20)\d{2}"
    r"[\u3015\u3009\u300b\uff09\u2019\u301b]"
    r"\d+\u53f7)"
)

conn = sqlite3.connect(str(DB_PATH))

# Get site names
site_names = dict(conn.execute("SELECT site_key, name FROM sites").fetchall())

# Build lookup of known documents
known_docs = {}
for doc_num, title, site_key in conn.execute(
    "SELECT document_number, title, site_key FROM documents WHERE document_number != ''"
).fetchall():
    known_docs[doc_num] = (title, site_key)

# Get all cross-references with source info
rows = conn.execute(
    "SELECT id, title, document_number, site_key, body_text_cn, publisher "
    "FROM documents WHERE body_text_cn != ''"
).fetchall()

# Export edges: source_doc -> cited_doc
output_path = Path(__file__).parent / "citation_edges.csv"
with open(output_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([
        "source_id", "source_title", "source_docnum", "source_site",
        "source_publisher", "cited_docnum", "cited_title", "cited_site",
        "cited_in_corpus"
    ])
    edge_count = 0
    for doc_id, title, doc_num, site_key, body, publisher in rows:
        refs = REF_PATTERN.findall(body)
        for ref in refs:
            cited_title = ""
            cited_site = ""
            in_corpus = False
            if ref in known_docs:
                cited_title, cited_site = known_docs[ref]
                in_corpus = True
            writer.writerow([
                doc_id, title, doc_num, site_key, publisher,
                ref, cited_title, cited_site, in_corpus
            ])
            edge_count += 1

print(f"Exported {edge_count} citation edges to {output_path}")

# Export nodes: all documents
nodes_path = Path(__file__).parent / "document_nodes.csv"
with open(nodes_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([
        "id", "title", "document_number", "site_key", "site_name",
        "publisher", "date_published", "has_body_text",
        "classify_main", "classify_genre", "classify_theme"
    ])
    for row in conn.execute(
        "SELECT id, title, document_number, site_key, publisher, "
        "date_published, body_text_cn != '', "
        "classify_main_name, classify_genre_name, classify_theme_name "
        "FROM documents"
    ).fetchall():
        doc_id, title, doc_num, site_key, publisher, date_pub, has_body, cm, cg, ct = row
        writer.writerow([
            doc_id, title, doc_num, site_key,
            site_names.get(site_key, site_key),
            publisher, date_pub, has_body, cm, cg, ct
        ])

total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
print(f"Exported {total} document nodes to {nodes_path}")

conn.close()
