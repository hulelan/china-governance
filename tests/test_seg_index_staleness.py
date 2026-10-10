"""The segmented BM25 index must re-index a document whose BODY CHANGED.

Measured 2026-10-09: the incremental path skipped every rowid already present, so
extract_pdf_text.py moved ~3,945 documents from a ~20-character "详见附件" stub to
thousands of characters (one went 20 -> 13,726) and ALL of them kept their stub in
doc_search_seg. The trigram index is fine — it has an AFTER UPDATE trigger — but this
one is rebuilt by a script and needed its own change detection.

It matters because search_documents() tries the segmented index FIRST and falls through
only on zero hits, so a stale row ranks on text the corpus no longer holds.

Run: python3 -m pytest tests/test_seg_index_staleness.py -v
"""
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

pytest.importorskip("jieba", reason="build_search_index_seg needs jieba")
from build_search_index_seg import CREATE, STATE_DDL, stale_and_done  # noqa: E402


def _db(bodies):
    """bodies = {doc_id: body}; indexes all of them with their fingerprints."""
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE documents (id INTEGER PRIMARY KEY, title TEXT, "
              "document_number TEXT, keywords TEXT, abstract TEXT, body_text_cn TEXT)")
    c.executescript(CREATE)
    c.executescript(STATE_DDL)
    for did, body in bodies.items():
        c.execute("INSERT INTO documents VALUES (?,?,?,?,?,?)",
                  (did, f"t{did}", "", "", "", body))
        c.execute("INSERT INTO doc_search_seg(rowid, title, document_number, keywords, "
                  "abstract, body_text_cn) VALUES (?,?,?,?,?,?)",
                  (did, f"t{did}", "", "", "", body))
        c.execute("INSERT INTO doc_search_seg_state VALUES (?,?)", (did, len(body)))
    c.commit()
    return c


def test_an_unchanged_row_is_skipped():
    c = _db({1: "原文", 2: "另一篇"})
    done, n_stale = stale_and_done(c)
    assert done == {1, 2}, done
    assert n_stale == 0


def test_a_changed_body_is_re_indexed():
    """The stub-to-full-text case this exists for."""
    c = _db({1: "详见附件。", 2: "unchanged"})
    c.execute("UPDATE documents SET body_text_cn = ? WHERE id = 1",
              ("详见附件。\n\n" + "部门预算正文" * 500,))
    c.commit()
    done, n_stale = stale_and_done(c)
    assert 1 not in done, "the changed row must NOT be skipped"
    assert 2 in done
    assert n_stale == 1
    # and it must have been removed from the index so the loop re-inserts it
    left = {r[0] for r in c.execute("SELECT rowid FROM doc_search_seg")}
    assert left == {2}, left


def test_rows_indexed_before_the_state_table_are_treated_as_fresh():
    """Must not trigger a full ~1h rebuild for a corpus indexed before this existed."""
    c = _db({1: "a", 2: "b"})
    c.execute("DELETE FROM doc_search_seg_state")
    c.commit()
    done, n_stale = stale_and_done(c)
    assert done == {1, 2}, done
    assert n_stale == 0
    # their lengths are now recorded, so the NEXT change is detectable
    rec = dict(c.execute("SELECT doc_id, body_len FROM doc_search_seg_state"))
    assert rec == {1: 1, 2: 1}, rec


def test_an_empty_index_returns_nothing_to_skip():
    c = _db({})
    assert stale_and_done(c) == (set(), 0)


def test_a_same_length_edit_is_missed_and_that_is_documented():
    """Length is a cheap fingerprint, not a hash — --rebuild remains the authority."""
    c = _db({1: "原文甲"})
    c.execute("UPDATE documents SET body_text_cn = ? WHERE id = 1", ("原文乙",))
    c.commit()
    done, n_stale = stale_and_done(c)
    assert done == {1}, "a same-length edit is NOT detected, by design"
    assert n_stale == 0


if __name__ == "__main__":
    for fn in list(globals().values()):
        if callable(fn) and getattr(fn, "__name__", "").startswith("test_"):
            fn(); print("ok", fn.__name__)
    print("all seg-index staleness checks passed")
