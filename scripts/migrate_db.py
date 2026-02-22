"""Database migration: add FTS5 search index and hash column."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "documents.db"

def migrate():
    conn = sqlite3.connect(str(DB_PATH))

    # Add SHA-256 hash column
    try:
        conn.execute("ALTER TABLE documents ADD COLUMN raw_html_sha256 TEXT DEFAULT ''")
        print("Added raw_html_sha256 column")
    except sqlite3.OperationalError:
        print("raw_html_sha256 column already exists")

    # Create FTS5 virtual table
    conn.execute("DROP TABLE IF EXISTS documents_fts")
    conn.execute("""
        CREATE VIRTUAL TABLE documents_fts USING fts5(
            title, body_text_cn, document_number, keywords, publisher,
            content=documents, content_rowid=id,
            tokenize='unicode61'
        )
    """)
    print("Created FTS5 virtual table")

    # Populate FTS5 from existing data
    conn.execute("""
        INSERT INTO documents_fts(rowid, title, body_text_cn, document_number, keywords, publisher)
        SELECT id, title, COALESCE(body_text_cn, ''), COALESCE(document_number, ''),
               COALESCE(keywords, ''), COALESCE(publisher, '')
        FROM documents
    """)
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM documents_fts").fetchone()[0]
    print(f"Indexed {count} documents in FTS5")

    # Create triggers to keep FTS5 in sync
    conn.executescript("""
        CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
            INSERT INTO documents_fts(rowid, title, body_text_cn, document_number, keywords, publisher)
            VALUES (new.id, new.title, COALESCE(new.body_text_cn, ''), COALESCE(new.document_number, ''),
                    COALESCE(new.keywords, ''), COALESCE(new.publisher, ''));
        END;

        CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
            INSERT INTO documents_fts(documents_fts, rowid, title, body_text_cn, document_number, keywords, publisher)
            VALUES ('delete', old.id, old.title, COALESCE(old.body_text_cn, ''), COALESCE(old.document_number, ''),
                    COALESCE(old.keywords, ''), COALESCE(old.publisher, ''));
            INSERT INTO documents_fts(rowid, title, body_text_cn, document_number, keywords, publisher)
            VALUES (new.id, new.title, COALESCE(new.body_text_cn, ''), COALESCE(new.document_number, ''),
                    COALESCE(new.keywords, ''), COALESCE(new.publisher, ''));
        END;

        CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
            INSERT INTO documents_fts(documents_fts, rowid, title, body_text_cn, document_number, keywords, publisher)
            VALUES ('delete', old.id, old.title, COALESCE(old.body_text_cn, ''), COALESCE(old.document_number, ''),
                    COALESCE(old.keywords, ''), COALESCE(old.publisher, ''));
        END;
    """)
    print("Created FTS5 sync triggers")

    conn.close()
    print("Migration complete")

if __name__ == "__main__":
    migrate()
