"""The publish-keyed, cross-worker page cache (web/services/pubcache.py) and the
pages rewritten on top of it (2026-11-25 speed pass).

What is pinned here, and why:

* a value written by one process is served to another (the whole point: the old
  per-process dicts made each of the 2 uvicorn workers pay every cold build);
* touching the publish stamp invalidates everything, memory layer included, and
  the stamp falls back to the DB file's mtime when it does not exist;
* the cache can never fail a request (corrupt file, unpicklable value, unwritable
  directory) and never serves an entry older than MAX_AGE;
* /lens's trigram-index path returns EXACTLY what the old six LIKE scans did,
  including for a query below the trigram floor, which must take the scan;
* the dashboard's top-cited query counts citations, not citations x documents
  sharing a 文号 (the old JOIN-then-GROUP inflated 80 citations to 5,360).
"""
import asyncio
import os
import pathlib
import pickle
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from web.services import pubcache  # noqa: E402


class _Tmp(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.td.name)
        self.stamp = self.dir / ".publish_stamp"
        self.dbfile = self.dir / "documents.db"
        self.dbfile.write_bytes(b"")
        pubcache.configure(cache_dir=self.dir / "cache", stamp=self.stamp,
                           fallback=self.dbfile, enabled=True)

    def tearDown(self):
        pubcache.configure(enabled=False)   # never leak a deleted tmp dir to later tests
        self.td.cleanup()

    def bump(self, path):
        """Advance a file's mtime unambiguously (filesystems have coarse clocks)."""
        st = path.stat() if path.exists() else None
        if st is None:
            path.write_text("x")
            st = path.stat()
        t = st.st_mtime + 10
        os.utime(path, (t, t))


class TestPubcache(_Tmp):
    def test_roundtrip_and_shared_through_disk(self):
        self.stamp.write_text("")
        pubcache.put("ns", ("a", 1), {"v": [1, 2]})
        self.assertEqual(pubcache.get("ns", ("a", 1)), {"v": [1, 2]})
        pubcache.clear_memory()          # another worker: nothing in memory
        self.assertEqual(pubcache.get("ns", ("a", 1)), {"v": [1, 2]})
        self.assertIs(pubcache.get("ns", ("a", 2)), pubcache.MISS)
        self.assertIs(pubcache.get("other", ("a", 1)), pubcache.MISS)

    def test_other_process_reads_it(self):
        """A real second interpreter (a second uvicorn worker) sees the entry."""
        self.stamp.write_text("")
        pubcache.put("ns", "k", [3, 4])
        code = (
            "import sys; sys.path.insert(0, %r)\n"
            "from web.services import pubcache\n"
            "pubcache.configure(cache_dir=%r, stamp=%r, fallback=%r, enabled=True)\n"
            "print(pubcache.get('ns', 'k'))\n"
        ) % (str(ROOT), str(self.dir / "cache"), str(self.stamp), str(self.dbfile))
        out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                             text=True, check=True).stdout.strip()
        self.assertEqual(out, "[3, 4]")

    def test_stamp_touch_invalidates_memory_and_disk(self):
        self.stamp.write_text("")
        pubcache.put("ns", "k", "old")
        self.assertEqual(pubcache.get("ns", "k"), "old")
        self.bump(self.stamp)
        self.assertIs(pubcache.get("ns", "k"), pubcache.MISS)
        pubcache.put("ns", "k", "new")
        self.assertEqual(pubcache.get("ns", "k"), "new")

    def test_new_generation_prunes_old_dirs(self):
        self.stamp.write_text("")
        pubcache.put("ns", "k", 1)
        old = {p.name for p in (self.dir / "cache").iterdir()}
        self.bump(self.stamp)
        pubcache.put("ns", "k", 2)
        now = {p.name for p in (self.dir / "cache").iterdir()}
        self.assertEqual(len(now), 1)
        self.assertFalse(old & now)

    def test_falls_back_to_db_mtime_without_stamp(self):
        self.assertFalse(self.stamp.exists())
        g1 = pubcache.generation()
        self.assertTrue(g1.startswith("d"))
        pubcache.put("ns", "k", "v")
        self.bump(self.dbfile)
        self.assertNotEqual(pubcache.generation(), g1)
        self.assertIs(pubcache.get("ns", "k"), pubcache.MISS)
        # creating the stamp switches the source (and so the generation)
        self.stamp.write_text("")
        self.assertTrue(pubcache.generation().startswith("s"))

    def test_max_age_expires_within_a_generation(self):
        self.stamp.write_text("")
        pubcache.put("ns", "k", "v")
        pubcache.clear_memory()
        f = next((self.dir / "cache").rglob("*.pkl"))
        old = time.time() - pubcache.MAX_AGE - 5
        os.utime(f, (old, old))
        self.assertIs(pubcache.get("ns", "k"), pubcache.MISS)

    def test_corrupt_file_is_a_miss(self):
        self.stamp.write_text("")
        pubcache.put("ns", "k", "v")
        pubcache.clear_memory()
        f = next((self.dir / "cache").rglob("*.pkl"))
        f.write_bytes(b"not a pickle")
        self.assertIs(pubcache.get("ns", "k"), pubcache.MISS)

    def test_unpicklable_value_still_served_from_memory(self):
        self.stamp.write_text("")
        val = {"rows": [sqlite3.connect(":memory:").execute("SELECT 1").fetchone()],
               "f": lambda: 1}   # a lambda cannot be pickled
        self.assertIs(pubcache.put("ns2", "k", val), val)
        self.assertIs(pubcache.get("ns2", "k"), val)
        pubcache.clear_memory()
        self.assertIs(pubcache.get("ns2", "k"), pubcache.MISS)

    def test_unwritable_dir_never_raises(self):
        self.stamp.write_text("")
        blocker = self.dir / "blocker"
        blocker.write_text("a file, not a directory")
        pubcache.configure(cache_dir=blocker / "cache")
        self.assertEqual(pubcache.put("ns", "k", 5), 5)
        self.assertEqual(pubcache.get("ns", "k"), 5)       # memory layer

    def test_memo_computes_once(self):
        self.stamp.write_text("")
        calls = []

        async def compute():
            calls.append(1)
            return "x"
        for _ in range(3):
            self.assertEqual(asyncio.run(pubcache.memo("ns", "m", compute)), "x")
        self.assertEqual(len(calls), 1)

    def test_no_stamp_and_no_db_caches_nothing(self):
        self.dbfile.unlink()
        self.assertEqual(pubcache.generation(), pubcache.NO_GEN)
        pubcache.put("ns", "k", 1)
        self.assertIs(pubcache.get("ns", "k"), pubcache.MISS)
        self.assertFalse((self.dir / "cache").exists())

    def test_disabled_is_passthrough(self):
        pubcache.configure(enabled=False)
        pubcache.put("ns", "k", 1)
        self.assertIs(pubcache.get("ns", "k"), pubcache.MISS)


# --- the pages rebuilt on the cache -----------------------------------------

SCHEMA = """
CREATE TABLE sites(site_key TEXT PRIMARY KEY, name TEXT, base_url TEXT,
                   admin_level TEXT, sid TEXT);
CREATE TABLE documents(id INTEGER PRIMARY KEY, site_key TEXT, title TEXT,
    title_en TEXT, document_number TEXT DEFAULT '', keywords TEXT DEFAULT '',
    publisher TEXT DEFAULT '', classify_main_name TEXT DEFAULT '',
    importance TEXT DEFAULT '', category TEXT DEFAULT '',
    abstract TEXT DEFAULT '', body_text_cn TEXT DEFAULT '',
    date_written INTEGER DEFAULT 0, date_published TEXT DEFAULT '',
    algo_doc_type TEXT DEFAULT '', topics_algo TEXT DEFAULT '',
    citation_rank REAL DEFAULT 0, ai_relevance REAL DEFAULT 0);
CREATE TABLE citations(id INTEGER PRIMARY KEY, source_id INT, target_id INT,
    target_ref TEXT, citation_type TEXT, source_level TEXT, target_level TEXT);
CREATE VIRTUAL TABLE doc_search USING fts5(
    title, document_number, keywords, abstract, body_text_cn,
    content='documents', content_rowid='id', tokenize='trigram');
INSERT INTO sites VALUES ('gov','State Council','', 'central',''),
                         ('gd','Guangdong','', 'provincial',''),
                         ('sz','Shenzhen','', 'municipal',''),
                         ('x','No level','', '','');
"""

# ts for 2019-06-01, 2023-03-03, 2024-12-31 (UTC)
T19, T23, T24 = 1559347200, 1677801600, 1735603200
DOCS = [
    # id, site, title, date_written, algo_doc_type, topics_algo, citation_rank, docnum
    (1, "gov", "关于人工智能发展的意见", T23, "opinion", "Tech,Industry", 50.0, "国发〔2023〕1号"),
    (2, "gd", "广东省人工智能产业行动计划", T24, "action_plan", "Tech", 9.0, "粤府〔2024〕2号"),
    (3, "sz", "深圳市人工智能条例", T19, "", "", 0.0, ""),
    (4, "sz", "深圳市住房保障办法", T23, "regulation", "Housing", 3.0, ""),
    (5, "x", "人工智能 与 数据", 0, "other", "Tech", 1.0, ""),
    (6, "orphan", "人工智能孤儿站点", T24, "other", "", 2.0, ""),      # site not in `sites`
    (7, "gov", "AI人工智能白皮书", T24, "", "Tech", 0.5, ""),
    (8, "gd", "关于住房的通知", T19, "notice", "Housing", 0.0, ""),
] + [(100 + i, "gd", f"财税文件{i}", T23, "", "", 0.0, "财税〔2018〕74号") for i in range(5)]


def _make_db(path):
    c = sqlite3.connect(path)
    c.executescript(SCHEMA)
    c.executemany(
        "INSERT INTO documents(id, site_key, title, date_written, algo_doc_type, "
        "topics_algo, citation_rank, document_number) VALUES (?,?,?,?,?,?,?,?)",
        [(d[0], d[1], d[2], d[3], d[4], d[5], d[6], d[7]) for d in DOCS])
    c.execute("INSERT INTO doc_search(doc_search) VALUES ('rebuild')")
    # 3 citations of one 文号 held by 5 documents, 1 of another
    c.executemany("INSERT INTO citations(source_id, target_ref, target_level) VALUES (?,?,?)",
                  [(1, "财税〔2018〕74号", "central")] * 3 + [(2, "国发〔2023〕1号", "central")])
    c.commit()
    c.close()


class _DBCase(_Tmp):
    def setUp(self):
        super().setUp()
        pubcache.configure(enabled=False)   # compute every time in these tests
        self.path = self.dir / "t.db"
        _make_db(self.path)

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


def _old_lens(path, q):
    """The pre-2026-11-25 lens panels, as the six LIKE queries computed them."""
    c = sqlite3.connect(path)
    pat = f"%{q}%"
    total = c.execute("SELECT COUNT(*) FROM documents WHERE title LIKE ?", (pat,)).fetchone()[0]
    tl = c.execute("""SELECT CAST(strftime('%Y', date_written, 'unixepoch') AS INTEGER) AS yr,
                             COUNT(*) FROM documents WHERE title LIKE ? AND date_written > 0
                      GROUP BY yr HAVING yr BETWEEN 2013 AND 2035 ORDER BY yr""", (pat,)).fetchall()
    lv = c.execute("""SELECT COALESCE(NULLIF(s.admin_level, ''), 'unknown') AS lvl, COUNT(*)
                      FROM documents d JOIN sites s ON s.site_key = d.site_key
                      WHERE d.title LIKE ? GROUP BY lvl""", (pat,)).fetchall()
    st = c.execute("""SELECT d.site_key, COUNT(*) FROM documents d JOIN sites s
                      ON s.site_key = d.site_key WHERE d.title LIKE ? GROUP BY d.site_key""",
                   (pat,)).fetchall()
    gn = c.execute("""SELECT COALESCE(NULLIF(algo_doc_type, ''), '(unclassified)') AS g, COUNT(*)
                      FROM documents WHERE title LIKE ? GROUP BY g""", (pat,)).fetchall()
    an = c.execute("""SELECT d.id FROM documents d JOIN sites s ON s.site_key = d.site_key
                      WHERE d.title LIKE ? AND d.citation_rank > 0
                      ORDER BY d.citation_rank DESC LIMIT 15""", (pat,)).fetchall()
    c.close()
    return {"total": total, "timeline": dict(tl), "levels": dict(lv), "sites": dict(st),
            "genres": dict(gn), "anchors": [r[0] for r in an]}


class TestLensParity(_DBCase):
    def lens(self, q, mode):
        """mode: 'index' (idx_documents_lens present), 'fts' (trigram path), 'scan'."""
        from web.services import documents as docsvc
        from web.services import lens
        if mode == "index":
            from scripts.build_site_stats import LENS_INDEX_SQL
            c = sqlite3.connect(self.path)
            c.execute(LENS_INDEX_SQL)
            c.commit(); c.close()
        lens._lens_index["has"] = None if mode == "index" else False
        docsvc._fts_flag["has"] = mode == "fts"
        try:
            return self.run_db(lambda db: lens._build_topic_lens(db, q))
        finally:
            docsvc._fts_flag["has"] = None
            lens._lens_index["has"] = None

    def check(self, q):
        want = _old_lens(self.path, q)
        for fts in ("fts", "scan", "index"):
            got = self.lens(q, fts)
            self.assertEqual(got["total"], want["total"], (q, fts))
            self.assertEqual({t["year"]: t["count"] for t in got["timeline"]},
                             want["timeline"], (q, fts))
            self.assertEqual({l["level"]: l["count"] for l in got["levels"]},
                             want["levels"], (q, fts))
            self.assertEqual({s["site_key"]: s["count"] for s in got["top_sites"]},
                             want["sites"], (q, fts))
            self.assertEqual({g["genre"]: g["count"] for g in got["genres"]},
                             want["genres"], (q, fts))
            self.assertEqual([a["id"] for a in got["anchors"]], want["anchors"], (q, fts))

    def test_trigram_path_matches_old_scans(self):
        self.check("人工智能")       # 4 chars: FTS path; includes an orphan-site doc
        self.check("ai人工")          # mixed case ASCII: LIKE is case-insensitive
        self.check("不存在的词")      # zero hits

    def test_short_query_takes_the_scan(self):
        self.check("住房")            # 2 chars: below the trigram floor

    def test_wildcard_query_keeps_like_semantics(self):
        self.check("人工%能")         # LIKE wildcard: must not go to the index

    def test_topics_panel(self):
        got = self.lens("人工智能", "fts")
        self.assertEqual({t["topic"]: t["count"] for t in got["topics"]},
                         {"Tech": 4, "Industry": 1})   # docs 1, 2, 5, 7


class TestLensQueryPlans(_DBCase):
    """The two lens paths must keep their cheap plans once idx_documents_lens exists:
    the short-query scan reads the covering INDEX (not the ~16 GB table), and the
    trigram path stays driven by the FTS index rather than scanning that index."""

    def plans(self):
        from scripts.build_site_stats import LENS_INDEX_SQL
        from web.database import _pg_to_sqlite
        from web.services import lens
        c = sqlite3.connect(self.path)
        c.execute(LENS_INDEX_SQL)
        c.execute("ANALYZE")
        out = {}
        for name, sql, args in (("scan", lens._SCAN_SQL, ("%住房%",)),
                                ("fts", lens._FTS_SQL, ('title : "人工智能"', "%人工智能%"))):
            q, a = _pg_to_sqlite(sql, args)
            out[name] = " | ".join(r[3] for r in c.execute("EXPLAIN QUERY PLAN " + q, a))
        c.close()
        return out

    def test_short_query_scans_the_covering_index(self):
        self.assertIn("COVERING INDEX idx_documents_lens", self.plans()["scan"])

    def test_fts_path_is_driven_by_the_fts_index(self):
        plan = self.plans()["fts"]
        self.assertTrue(plan.startswith("SCAN s VIRTUAL TABLE"), plan)
        self.assertNotIn("idx_documents_lens", plan)

    def test_index_columns_cover_the_lens_row(self):
        from scripts.build_site_stats import LENS_INDEX_SQL
        from web.services import lens
        cols = {c.strip().split(".")[-1] for c in lens._ROW_COLS.split(",")} - {"id"}
        idx = LENS_INDEX_SQL[LENS_INDEX_SQL.index("(") + 1:LENS_INDEX_SQL.rindex(")")]
        self.assertLessEqual(cols, {c.strip() for c in idx.split(",")})


class TestDashboardTopCited(_DBCase):
    def test_counts_citations_not_fanout(self):
        from web.routers.pages import _TOP_CITED_SQL
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        rows = {r["docnum"]: r for r in c.execute(_TOP_CITED_SQL)}
        self.assertEqual(rows["财税〔2018〕74号"]["count"], 3)       # not 3 x 5
        self.assertEqual(rows["财税〔2018〕74号"]["resolved_id"], 100)  # lowest id
        self.assertEqual(rows["国发〔2023〕1号"]["count"], 1)
        self.assertEqual(rows["国发〔2023〕1号"]["resolved_id"], 1)


class TestSearchStaysLive(_DBCase):
    def test_new_document_invalidates_cached_search(self):
        """Search is cached for repeats, but a newly stored document must show up
        at once (the trigram index is trigger-maintained), so the key carries
        MAX(documents.id)."""
        from web.services import documents as docsvc
        self.stamp.write_text("")
        pubcache.configure(enabled=True)
        docsvc._seg_flag["has"], docsvc._fts_flag["has"] = False, True
        try:
            run = lambda: self.run_db(lambda db: docsvc.search_documents(db, "人工智能"))
            _, n1 = run()
            calls = []
            orig = docsvc._search_documents

            async def spy(*a, **k):
                calls.append(1)
                return await orig(*a, **k)
            docsvc._search_documents = spy
            try:
                _, n2 = run()                        # repeat: served from cache
                self.assertEqual((n2, len(calls)), (n1, 0))
                c = sqlite3.connect(self.path)
                c.execute("INSERT INTO documents(id, site_key, title) VALUES (999, 'gov', '人工智能新规')")
                c.execute("INSERT INTO doc_search(rowid, title) VALUES (999, '人工智能新规')")
                c.commit(); c.close()
                _, n3 = run()
                self.assertEqual((n3, len(calls)), (n1 + 1, 1))
            finally:
                docsvc._search_documents = orig
        finally:
            docsvc._seg_flag["has"] = docsvc._fts_flag["has"] = None


class TestTrackerKeyCarriesDate(_Tmp):
    def test_page_key_is_dated(self):
        """tracker/discourse windows come from date.today(), so a cache made before
        midnight must not answer after it."""
        from datetime import date
        from web.services import tracker
        self.stamp.write_text("")
        tracker._store("k", "v")
        self.assertEqual(pubcache.get("tracker", (date.today().isoformat(), "k")), "v")
        self.assertIs(pubcache.get("tracker", ("1999-01-01", "k")), pubcache.MISS)


if __name__ == "__main__":
    unittest.main()
