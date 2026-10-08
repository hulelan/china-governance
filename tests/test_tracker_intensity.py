"""The tracker's two intensity columns (docs/research/diffusion-intensity-index.md).

Why these are two columns and not one: on 796 anchors the authority and textual
dimensions correlate at Spearman -0.085, and the sign FLIPS to +0.128 under a
stricter specification, so the residual is noise around zero. A single composite
would discard real information.

Why `authority_mean` is a mean and never a sum: summed over adopters it
correlates with `cascade_events` itself at +0.957, i.e. it would be a second copy
of the count. The tests below pin the per-adopter semantics.

Why the lengths come from `doc_len` and not from `body_text_cn`: a GROUP BY over
the body column makes SQLite build an AUTOMATIC COVERING INDEX (the 74s
get_sites pathology in CLAUDE.md). `doc_len` is ints, built in the one sequential
scan build_site_stats already pays for.
"""
import pathlib
import sqlite3
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import build_site_stats as S           # noqa: E402
from scripts import build_tracker_rollup as T       # noqa: E402

SCHEMA = """
CREATE TABLE sites(site_key TEXT PRIMARY KEY, name TEXT, admin_level TEXT);
CREATE TABLE doc_identity(doc_id INTEGER PRIMARY KEY, admin_level_doc TEXT,
    instrument_id INT, genre TEXT, lead_issuer TEXT, province TEXT);
CREATE TABLE documents(id INTEGER PRIMARY KEY, site_key TEXT, topics_algo TEXT,
    date_published TEXT, body_text_cn TEXT, document_number TEXT,
    date_written INTEGER, classify_main_name TEXT);
CREATE TABLE citations(id INTEGER PRIMARY KEY, source_id INT, target_id INT,
    target_ref TEXT, citation_type TEXT, source_level TEXT, target_level TEXT);
CREATE TABLE diffusion_events(id INTEGER PRIMARY KEY, source_id INT, anchor_id INT,
    match_type TEXT, lag_days INT, topic TEXT, source_level TEXT,
    anchor_date TEXT, source_date TEXT, anchor_title TEXT, source_title TEXT,
    anchor_level TEXT DEFAULT 'central', source_implementing INT DEFAULT 1);
INSERT INTO sites VALUES ('gov','G','central'),('gd','D','provincial'),
                         ('gz','Z','municipal'),('sz','S','district');
"""

# anchor 100 is 2,000 chars; one adopter per level at 1,000 / 2,000 / 4,000
DOCS = """
INSERT INTO documents(id,site_key,topics_algo,date_published,body_text_cn) VALUES
  (100,'gov','Energy','2024-01-01', 'a'),
  (1,  'gd', 'Energy','2024-03-04', 'b'),
  (2,  'gz', 'Energy','2024-03-05', 'c'),
  (3,  'sz', 'Energy','2024-03-06', 'd');
INSERT INTO diffusion_events
  (source_id,anchor_id,match_type,topic,source_level,anchor_date,source_date,
   anchor_title,anchor_level,source_implementing) VALUES
  (1,100,'citation','Energy','provincial','2024-01-01','2024-03-04','A','central',1),
  (2,100,'citation','Energy','municipal', '2024-01-01','2024-03-05','A','central',1),
  (3,100,'citation','Energy','district',  '2024-01-01','2024-03-06','A','central',1);
"""


def _db(td, with_len=True):
    p = pathlib.Path(td) / "t.db"
    c = sqlite3.connect(p)
    c.executescript(SCHEMA + DOCS)
    if with_len:
        c.executescript("CREATE TABLE doc_len(doc_id INTEGER PRIMARY KEY, chars INTEGER NOT NULL);"
                        "INSERT INTO doc_len VALUES (100,2000),(1,1000),(2,2000),(3,4000);")
    c.commit()
    c.close()
    return p


def _cells(p):
    c = sqlite3.connect(p)
    try:
        return {r[0]: r[1:] for r in c.execute(
            "SELECT admin_level, cascade_events, authority_mean, text_median, elab_median "
            "FROM tracker_weekly WHERE topic='Energy' AND cascade_events > 0")}
    finally:
        c.close()


class TrackerIntensity(unittest.TestCase):
    def test_authority_mean_is_per_adopter_not_a_sum(self):
        with tempfile.TemporaryDirectory() as td:
            p = _db(td)
            T.build(p)
            d = _cells(p)
            for lvl, w in (("provincial", 3.0), ("municipal", 2.0), ("district", 1.0)):
                self.assertEqual(d[lvl][0], 1, lvl)
                self.assertAlmostEqual(d[lvl][1], w, msg=f"{lvl} must carry its own weight")

    def test_text_and_elaboration_come_from_doc_len(self):
        with tempfile.TemporaryDirectory() as td:
            p = _db(td)
            T.build(p)
            d = _cells(p)
            self.assertEqual((d["provincial"][2], d["municipal"][2], d["district"][2]),
                             (1000, 2000, 4000))
            for lvl, e in (("provincial", 0.5), ("municipal", 1.0), ("district", 2.0)):
                self.assertAlmostEqual(d[lvl][3], e, msg=lvl)

    def test_degrades_cleanly_without_doc_len(self):
        """A DB that has not run build_site_stats yet must still roll up: the
        counts and the authority axis never depend on doc_len."""
        with tempfile.TemporaryDirectory() as td:
            p = _db(td, with_len=False)
            T.build(p)
            d = _cells(p)
            self.assertEqual(d["provincial"][0], 1)
            self.assertAlmostEqual(d["provincial"][1], 3.0)
            self.assertEqual(d["provincial"][2], 0)
            self.assertAlmostEqual(d["provincial"][3], 0.0)

    def test_migrate_adds_the_columns_to_an_existing_table(self):
        """MIGRATE must bring an old tracker_weekly up to the new shape."""
        with tempfile.TemporaryDirectory() as td:
            p = _db(td)
            c = sqlite3.connect(p)
            c.executescript("""
                CREATE TABLE tracker_weekly(
                  topic TEXT NOT NULL, iso_week TEXT NOT NULL,
                  admin_level TEXT NOT NULL, week_start TEXT NOT NULL,
                  new_docs INTEGER NOT NULL DEFAULT 0,
                  cascade_events INTEGER NOT NULL DEFAULT 0,
                  cascade_events_lowconf INTEGER NOT NULL DEFAULT 0,
                  PRIMARY KEY (topic, iso_week, admin_level));""")
            c.commit()
            c.close()
            T.build(p)
            c = sqlite3.connect(p)
            cols = {r[1] for r in c.execute("PRAGMA table_info(tracker_weekly)")}
            c.close()
            for col in ("authority_mean", "text_median", "elab_median"):
                self.assertIn(col, cols)

    def test_median_helper(self):
        self.assertEqual(T._median([]), 0)
        self.assertEqual(T._median([5]), 5)
        self.assertEqual(T._median([1, 3]), 2)
        self.assertEqual(T._median([3, 1, 2]), 2)


class DocLen(unittest.TestCase):
    def test_build_site_stats_writes_character_counts(self):
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "s.db"
            c = sqlite3.connect(p)
            c.executescript(SCHEMA)
            c.executescript("""
                INSERT INTO documents(id,site_key,body_text_cn,document_number,date_written)
                VALUES (1,'gov','hello world','X1',1700000000),
                       (2,'gov','','',1700000000),
                       (3,'gov',NULL,NULL,0),
                       (4,'gov','abcde','X2',1700000000);""")
            c.commit()
            c.close()
            S.build(p)
            c = sqlite3.connect(p)
            got = dict(c.execute("SELECT doc_id, chars FROM doc_len"))
            c.close()
            self.assertEqual(got, {1: 11, 2: 0, 3: 0, 4: 5},
                             "NULL and '' must both be 0, not NULL")

    def test_rebuild_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "s.db"
            c = sqlite3.connect(p)
            c.executescript(SCHEMA)
            c.executescript("INSERT INTO documents(id,site_key,body_text_cn,date_written) "
                            "VALUES (1,'gov','abc',1700000000);")
            c.commit()
            c.close()
            S.build(p)
            S.build(p)
            c = sqlite3.connect(p)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM doc_len").fetchone()[0], 1)
            c.close()

    def test_length_query_plan_stays_a_bare_scan(self):
        """The whole design rests on this: adding LENGTH(body_text_cn) must NOT
        make SQLite build an automatic covering index. Measured on the live
        corpus at 7.3s for 346,955 bodies vs 2.2s without; the 74s get_sites
        pathology was the GROUP BY, not the body read."""
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "s.db"
            c = sqlite3.connect(p)
            c.executescript(SCHEMA)
            plan = "\n".join(str(r) for r in c.execute(
                "EXPLAIN QUERY PLAN SELECT id, site_key, "
                "LENGTH(COALESCE(body_text_cn,'')) FROM documents"))
            c.close()
            self.assertNotIn("AUTOMATIC COVERING INDEX", plan, plan)
            self.assertIn("SCAN documents", plan, plan)


if __name__ == "__main__":
    unittest.main(verbosity=2)
