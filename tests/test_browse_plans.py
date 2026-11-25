"""/browse and /admin query plans after the 2026-11-25 click-through sweep.

Measured cold on the live corpus: /browse?category=媒体报道 2.3s, ?min_ai=0.5 1.1s,
/admin 2.7s. Each was a plan reading many `documents` (or `document_changes`) rows
to produce 50. These pin the cheaper plans: (filter, date) indexes so the page is
read in index order, an index hint for a selective AI threshold, and a covering
index for /admin's change aggregates. A plan test, not a timing test, so it holds
on a tiny fixture.
"""
import asyncio
import pathlib
import sqlite3
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import build_site_stats as S  # noqa: E402
from web.services import documents as docsvc  # noqa: E402


def _db(path):
    c = sqlite3.connect(path)
    c.executescript("""
    CREATE TABLE sites(site_key TEXT PRIMARY KEY, name TEXT, admin_level TEXT);
    CREATE TABLE documents(id INTEGER PRIMARY KEY, site_key TEXT, title TEXT,
        document_number TEXT DEFAULT '', publisher TEXT DEFAULT '', date_written INTEGER,
        date_published TEXT DEFAULT '', classify_main_name TEXT DEFAULT '',
        body_text_cn TEXT DEFAULT '', title_en TEXT DEFAULT '', importance TEXT DEFAULT '',
        category TEXT DEFAULT '', summary_en TEXT DEFAULT '', citation_rank REAL DEFAULT 0,
        algo_doc_type TEXT DEFAULT '', ai_relevance REAL DEFAULT 0,
        topics_algo TEXT DEFAULT '');
    CREATE TABLE citations(id INTEGER PRIMARY KEY, source_id INT, target_id INT,
        target_ref TEXT, citation_type TEXT, source_level TEXT, target_level TEXT);
    CREATE INDEX idx_documents_date ON documents(date_written);
    CREATE INDEX idx_documents_ai_relevance ON documents(ai_relevance);
    CREATE TABLE document_changes(id INTEGER PRIMARY KEY, document_id INT, site_key TEXT,
        change_type TEXT, field_name TEXT, old_value TEXT, new_value TEXT,
        detected_at TEXT, sync_run_id TEXT);
    INSERT INTO sites VALUES ('gov', 'G', 'central');
    """)
    rows = []
    for i in range(1, 2001):
        rows.append((i, "gov", f"t{i}", 1_600_000_000 + i * 3600,
                     "媒体报道" if i % 3 == 0 else "其他",
                     "regulation" if i % 5 == 0 else "other",
                     0.9 if i % 97 == 0 else 0.01))
    c.executemany("INSERT INTO documents(id, site_key, title, date_written, "
                  "classify_main_name, algo_doc_type, ai_relevance) VALUES (?,?,?,?,?,?,?)", rows)
    c.commit()
    c.close()


class Plans(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.path = pathlib.Path(self.td.name) / "t.db"
        _db(self.path)
        S.build(self.path)            # creates the indexes under test
        c = sqlite3.connect(self.path)
        c.execute("ANALYZE")
        c.commit()
        c.close()
        docsvc._index_cache.clear()

    def tearDown(self):
        # documents.py caches table/index existence per process; this fixture has
        # doc_inbound etc. (S.build), so do not let that leak into other tests.
        docsvc._index_cache.clear()
        docsvc._table_cache.clear()
        self.td.cleanup()

    def plan(self, sql, *a):
        c = sqlite3.connect(self.path)
        try:
            return " | ".join(r[3] for r in c.execute("EXPLAIN QUERY PLAN " + sql, a))
        finally:
            c.close()

    def test_filter_then_date_reads_in_index_order(self):
        for col, val, idx in (("classify_main_name", "媒体报道", "idx_documents_classify_date"),
                              ("algo_doc_type", "regulation", "idx_documents_doctype_date")):
            p = self.plan(f"SELECT d.id, d.title FROM documents d WHERE d.{col} = ? "
                          "ORDER BY d.date_written DESC LIMIT 50", val)
            self.assertIn(idx, p)
            self.assertNotIn("TEMP B-TREE", p)

    def test_admin_change_aggregates_are_index_only(self):
        p = self.plan("SELECT sync_run_id, MIN(detected_at), COUNT(*), "
                      "SUM(CASE WHEN change_type = 'added' THEN 1 ELSE 0 END) "
                      "FROM document_changes GROUP BY sync_run_id")
        self.assertIn("COVERING INDEX idx_doc_changes_run_cover", p)

    def run_db(self, fn):
        import aiosqlite
        from web.database import SQLiteDB

        async def go():
            conn = await aiosqlite.connect(str(self.path))
            conn.row_factory = aiosqlite.Row
            try:
                return await fn(SQLiteDB(conn))
            finally:
                await conn.close()
        return asyncio.run(go())

    def test_ai_threshold_hint_returns_the_same_page(self):
        got = self.run_db(lambda db: docsvc.get_documents(db, min_ai_relevance=0.5))
        want = sqlite3.connect(self.path).execute(
            "SELECT id FROM documents WHERE ai_relevance >= 0.5 "
            "ORDER BY date_written DESC LIMIT 50").fetchall()
        self.assertEqual([r["id"] for r in got[0]], [r[0] for r in want])
        self.assertEqual(got[1], len(want))
        old = docsvc.AI_HINT_MAX_ROWS
        docsvc.AI_HINT_MAX_ROWS = 0       # no hint: the planner's own choice
        try:
            got2 = self.run_db(lambda db: docsvc.get_documents(db, min_ai_relevance=0.5))
        finally:
            docsvc.AI_HINT_MAX_ROWS = old
        self.assertEqual([r["id"] for r in got2[0]], [r["id"] for r in got[0]])


if __name__ == "__main__":
    unittest.main()
