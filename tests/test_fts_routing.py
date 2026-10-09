"""Both FTS indexes are blind to a different class of term, and both fail with a
clean 0 rather than an error. scripts/rnd/analysis/fts.py routes by length so an
ad-hoc query cannot pick the wrong one.

The regression these pin is not a hidden count — it is a REVERSED COMPARISON.
Measured on the live corpus 2026-10-09, a trigram-only run asking whether the
尽职免责 blame-shield belongs to lending or to funds returned 信贷 0% / 贷款 0% /
银行 0% against 创业投资 28% / 股权投资 24% / 引导基金 18%, reading as a clean "it
is about funds". Routed properly: 融资 59.8%, 银行 50.6%, 贷款 49.7%, 信贷 41.9%,
引导基金 18.4%, 耐心资本 9.5% — the opposite. The three lending terms were two
characters and every fund term was three or four; nothing else differed.
"""
import pathlib
import sqlite3
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "rnd" / "analysis"))

import fts  # noqa: E402


def _db():
    """Both indexes over the same three documents.

    doc_search is a real trigram index. doc_search_seg is unicode61 over
    PRE-SPLIT text, which is how jieba segmentation presents itself: the
    compound 跨境人民币 is stored as the tokens 跨境 and 人民币, so a phrase query
    for the compound cannot match — exactly the live behaviour.
    """
    c = sqlite3.connect(":memory:")
    c.executescript("""
        CREATE VIRTUAL TABLE doc_search USING fts5(body, tokenize='trigram');
        CREATE VIRTUAL TABLE doc_search_seg USING fts5(body, tokenize='unicode61');
    """)
    rows = [
        (1, "银行贷款与跨境人民币结算",      "银行 贷款 与 跨境 人民币 结算"),
        (2, "引导基金支持耐心资本",          "引导 基金 支持 耐心 资本"),
        (3, "商业银行信贷尽职免责办法",      "商业 银行 信贷 尽职 免责 办法"),
    ]
    for rid, raw, segd in rows:
        c.execute("INSERT INTO doc_search(rowid, body) VALUES (?,?)", (rid, raw))
        c.execute("INSERT INTO doc_search_seg(rowid, body) VALUES (?,?)", (rid, segd))
    c.commit()
    return c


class Routing(unittest.TestCase):
    def test_index_for_is_decided_by_length_alone(self):
        self.assertEqual(fts.index_for("银行"), fts.SEGMENTED)
        self.assertEqual(fts.index_for("美元"), fts.SEGMENTED)
        self.assertEqual(fts.index_for("引导基金"), fts.TRIGRAM)
        self.assertEqual(fts.index_for("耐心资本"), fts.TRIGRAM)
        with self.assertRaises(ValueError):
            fts.index_for("")

    def test_a_two_char_term_is_found_and_names_the_segmented_index(self):
        c = _db()
        ids, idx = fts.term_ids(c, "银行")
        self.assertEqual(idx, fts.SEGMENTED)
        self.assertEqual(ids, {1, 3})

    def test_the_trigram_blind_spot_is_real_in_this_fixture(self):
        """Not a hypothetical: the same 2-char term through the trigram index
        returns nothing, with no error."""
        c = _db()
        got = {r[0] for r in c.execute(
            "SELECT rowid FROM doc_search WHERE doc_search MATCH ?", ('"银行"',))}
        self.assertEqual(got, set(), "if this ever matches, the premise changed")

    def test_the_segmented_blind_spot_is_real_too(self):
        """The reverse failure: a jieba-split compound is unmatchable in seg."""
        c = _db()
        got = {r[0] for r in c.execute(
            "SELECT rowid FROM doc_search_seg WHERE doc_search_seg MATCH ?",
            ('"跨境人民币"',))}
        self.assertEqual(got, set())
        ids, idx = fts.term_ids(c, "跨境人民币")   # routed: trigram sees it
        self.assertEqual(idx, fts.TRIGRAM)
        self.assertEqual(ids, {1})

    def test_forcing_a_blind_index_raises_instead_of_returning_zero(self):
        c = _db()
        with self.assertRaises(ValueError) as cm:
            fts.term_ids(c, "银行", index=fts.TRIGRAM)
        self.assertIn("silent 0", str(cm.exception))

    def test_forcing_the_valid_index_is_allowed(self):
        c = _db()
        ids, idx = fts.term_ids(c, "引导基金", index=fts.TRIGRAM)
        self.assertEqual((ids, idx), ({2}, fts.TRIGRAM))

    def test_missing_table_says_how_to_build_it(self):
        c = sqlite3.connect(":memory:")
        with self.assertRaises(RuntimeError) as cm:
            fts.term_ids(c, "引导基金")
        self.assertIn("build_search_index", str(cm.exception))


class Comparisons(unittest.TestCase):
    def test_counts_carry_the_index_so_a_blind_zero_is_visible(self):
        c = _db()
        rows = fts.term_counts(c, ["银行", "引导基金"])
        self.assertEqual([(t, n) for t, n, _i in rows], [("银行", 2), ("引导基金", 1)])
        self.assertEqual([i for _t, _n, i in rows], [fts.SEGMENTED, fts.TRIGRAM])

    def test_cooccurrence_routes_each_context_independently(self):
        """The regression test for the reversal: a 2-char context and a 4-char
        context must both be visible in one comparison."""
        c = _db()
        got = fts.cooccurrence(c, "尽职免责", ["银行", "信贷", "引导基金"])
        by = {t: n for t, n, _s, _i in got}
        self.assertEqual(by["银行"], 1)        # doc 3, via the segmented index
        self.assertEqual(by["信贷"], 1)        # doc 3, 2-char, would have been 0
        self.assertEqual(by["引导基金"], 0)    # genuinely absent from doc 3
        idxs = {t: i for t, _n, _s, i in got}
        self.assertEqual(idxs["银行"], fts.SEGMENTED)
        self.assertEqual(idxs["引导基金"], fts.TRIGRAM)

    def test_cooccurrence_refuses_an_unmatched_base(self):
        c = _db()
        with self.assertRaises(ValueError):
            fts.cooccurrence(c, "不存在的词组", ["银行"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
