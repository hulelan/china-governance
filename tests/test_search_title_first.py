"""The title-first shortcut for the BM25 search path (web/services/documents.py
`_search_seg_title_first`, 2026-11-25).

The full ranked query orders every match by (title contains the query, bm25, date
DESC). The shortcut scores only the title matches, which is exact as long as the
requested page lies inside them. These tests compare it row for row with the full
query, including bm25 ties (mirror copies score identically) broken by date and
NULL dates, and pin that it declines (returns None) when the page would reach past
the title matches, for wildcard queries, and for case-folding queries where its
stand-ins differ from LIKE.

The segmented index is filled with hand-segmented text, so jieba is not needed.
"""
import asyncio
import pathlib
import sqlite3
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from web.services import documents as docsvc  # noqa: E402

SCHEMA = """
CREATE TABLE documents(id INTEGER PRIMARY KEY, site_key TEXT, title TEXT,
    title_en TEXT DEFAULT '', document_number TEXT DEFAULT '', keywords TEXT DEFAULT '',
    abstract TEXT DEFAULT '', body_text_cn TEXT DEFAULT '', publisher TEXT DEFAULT '',
    classify_main_name TEXT DEFAULT '', importance TEXT DEFAULT '', category TEXT DEFAULT '',
    date_written INTEGER, algo_doc_type TEXT DEFAULT '', topics_algo TEXT DEFAULT '',
    citation_rank REAL DEFAULT 0);
CREATE INDEX idx_documents_lens ON documents(title, site_key, date_written,
    algo_doc_type, topics_algo, citation_rank);
CREATE VIRTUAL TABLE doc_search USING fts5(
    title, document_number, keywords, abstract, body_text_cn,
    content='documents', content_rowid='id', tokenize='trigram');
CREATE VIRTUAL TABLE doc_search_seg USING fts5(
    title, document_number, keywords, abstract, body_text_cn,
    content='', tokenize='unicode61 remove_diacritics 2');
"""


def _make(path, n_title, n_body):
    """n_title docs with 数据安全 in the title (several exact mirrors, i.e. bm25 ties,
    with distinct and NULL dates) and n_body docs with it only in the body."""
    c = sqlite3.connect(path)
    c.executescript(SCHEMA)
    rows = []
    i = 0
    for k in range(n_title):
        i += 1
        mirror = k % 4 == 0                      # every 4th is a byte-identical mirror
        title = "关于数据安全的通知" if mirror else f"关于数据安全的通知第{k}号"
        body = "数据安全 " * (1 + (0 if mirror else k % 5))
        date = None if k % 7 == 0 else 1_600_000_000 + k * 86400
        rows.append((i, title, body, date,
                     "关于 数据 安全 数据安全 的 通知" + ("" if mirror else f" 第 {k} 号"),
                     " ".join(["数据 安全 数据安全"] * (1 + (0 if mirror else k % 5)))))
    for k in range(n_body):
        i += 1
        rows.append((i, f"其他文件{k}", "数据安全 " * 50, 1_700_000_000 + k,
                     f"其他 文件 {k}", " ".join(["数据 安全 数据安全"] * 50)))
    for r in rows:
        c.execute("INSERT INTO documents(id, site_key, title, body_text_cn, date_written) "
                  "VALUES (?, 'gov', ?, ?, ?)", r[:4])
        c.execute("INSERT INTO doc_search_seg(rowid, title, body_text_cn) VALUES (?,?,?)",
                  (r[0], r[4], r[5]))
    c.execute("INSERT INTO doc_search(doc_search) VALUES ('rebuild')")
    c.commit()
    c.close()


class TitleFirst(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.path = pathlib.Path(self.td.name) / "t.db"
        docsvc._fts_flag["has"] = True
        docsvc._index_cache.clear()

    def tearDown(self):
        docsvc._fts_flag["has"] = None
        docsvc._index_cache.clear()
        self.td.cleanup()

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

    def both(self, q, match, per_page, offset):
        pat = f"%{q}%"
        fast = self.run_db(lambda db: docsvc._search_seg_title_first(
            db, match, q, pat, per_page, offset))
        full = self.run_db(lambda db: docsvc._search_seg_bm25(
            db, match, "", [], "", [], 2, pat, per_page, offset))
        return fast, full

    def ids(self, rows):
        return [r["id"] for r in rows]

    def test_identical_page_including_ties_and_null_dates(self):
        _make(self.path, n_title=120, n_body=300)
        for per_page, offset in ((50, 0), (50, 50), (20, 100), (7, 13)):
            fast, full = self.both("数据安全", '"数据安全"', per_page, offset)
            self.assertIsNotNone(fast, (per_page, offset))
            self.assertEqual(self.ids(fast[0]), self.ids(full[0]), (per_page, offset))
            self.assertEqual(fast[1], full[1])
            self.assertEqual([dict(r) for r in fast[0]], [dict(r) for r in full[0]])

    def test_two_char_query_uses_the_covering_index(self):
        _make(self.path, n_title=80, n_body=50)
        fast, full = self.both("安全", '"安全"', 50, 0)
        self.assertIsNotNone(fast)
        self.assertEqual(self.ids(fast[0]), self.ids(full[0]))

    def test_declines_when_page_reaches_past_title_matches(self):
        _make(self.path, n_title=30, n_body=100)
        fast, full = self.both("数据安全", '"数据安全"', 50, 0)
        self.assertIsNone(fast)               # caller runs the full query instead
        self.assertEqual(len(full[0]), 50)

    def test_declines_on_wildcards_and_non_ascii_case(self):
        _make(self.path, n_title=80, n_body=10)
        for q in ("数据%全", "数据_全", "ＡＩ数据"):
            fast, _ = self.both(q, '"数据安全"', 10, 0)
            self.assertIsNone(fast, q)


if __name__ == "__main__":
    unittest.main()
