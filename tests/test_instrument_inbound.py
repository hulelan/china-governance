"""Pooled citation weight, and the two things the per-document table cannot do.

docs/working/undated-citation-weight.md: `doc_inbound` is per DOCUMENT, so weight
lands on whichever COPY a citing text resolved to — frequently an undated mirror —
while the dated canonical copy reads inbound 0. Corpus-wide, 22,214 of 44,364 cited
documents are undated and carry 120,361 of 270,695 citations (44.5%), so any series
joining citation weight to a date silently drops them.

Pinned here:
  * a mirror citing its OWN SIBLING is the same text citing itself and must not count
    (doc_inbound can only drop source_id = target_id, which misses this entirely)
  * dated_id prefers the CANONICAL copy, and falls back to the earliest dated copy
  * a wholly undated pool still gets a row, with date_written = 0, rather than vanishing

Run: python3 -m pytest tests/test_instrument_inbound.py -v
"""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from build_site_stats import DDL, build_doc_inbound, build_instrument_inbound  # noqa: E402

JUL2024 = 1719792000
JUL2025 = 1751328000


def _db(docs, identity, cites):
    """docs=[(id,date_written)] identity=[(id,instrument_id,role)] cites=[(src,tgt)]"""
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE documents (id INTEGER PRIMARY KEY, site_key TEXT, "
              "date_written INTEGER, body_text_cn TEXT, document_number TEXT, "
              "date_published TEXT, display_publish_time TEXT, classify_main_name TEXT)")
    c.execute("CREATE TABLE citations (id INTEGER PRIMARY KEY, source_id INTEGER, "
              "target_id INTEGER)")
    c.execute("CREATE TABLE doc_identity (doc_id INTEGER PRIMARY KEY, "
              "instrument_id INTEGER, instrument_role TEXT)")
    c.executescript(DDL)
    for did, dw in docs:
        c.execute("INSERT INTO documents (id, site_key, date_written, body_text_cn) "
                  "VALUES (?,'s',?,'')", (did, dw))
    for did, iid, role in identity:
        c.execute("INSERT INTO doc_identity VALUES (?,?,?)", (did, iid, role))
    for src, tgt in cites:
        c.execute("INSERT INTO citations (source_id, target_id) VALUES (?,?)", (src, tgt))
    c.commit()
    build_doc_inbound(c)
    return c


# One instrument (100) held as canonical 100 (dated) + mirror 101 (undated).
# Outside citers 200, 201 cite the UNDATED mirror. 102 is a third copy that cites
# its own sibling — a pool-level self-citation.
POOL_DOCS = [(100, JUL2024), (101, 0), (102, 0), (200, JUL2025), (201, JUL2025)]
POOL_IDENT = [(100, 100, "canonical"), (101, 100, "mirror"), (102, 100, "mirror"),
              (200, 200, "unique"), (201, 201, "unique")]


def test_weight_on_an_undated_mirror_is_pooled_onto_a_dated_copy():
    c = _db(POOL_DOCS, POOL_IDENT, [(200, 101), (201, 101)])
    # per-document: the dated canonical reads 0, the undated mirror holds both
    assert c.execute("SELECT COALESCE(inbound,0) FROM doc_inbound WHERE doc_id=100"
                     ).fetchone() is None or True
    mirror = c.execute("SELECT inbound FROM doc_inbound WHERE doc_id=101").fetchone()[0]
    assert mirror == 2
    assert c.execute("SELECT COUNT(*) FROM doc_inbound WHERE doc_id=100").fetchone()[0] == 0

    build_instrument_inbound(c)
    row = c.execute("SELECT inbound, edges, copies, cited_copies, dated_id, date_written "
                    "FROM instrument_inbound WHERE instrument_id=100").fetchone()
    inbound, edges, copies, cited_copies, dated_id, dw = row
    assert inbound == 2, row
    assert copies == 3, row
    assert cited_copies == 1, "only the mirror carried inbound of its own"
    assert dated_id == 100, "the dated canonical copy"
    assert dw == JUL2024, "pooled weight is now readable against a real date"


def test_a_mirror_citing_its_own_sibling_does_not_count():
    """The whole point: doc_inbound can only drop source_id = target_id."""
    c = _db(POOL_DOCS, POOL_IDENT, [(200, 101), (102, 101)])   # 102 is in pool 100
    assert c.execute("SELECT inbound FROM doc_inbound WHERE doc_id=101").fetchone()[0] == 2, \
        "doc_inbound counts the sibling cite — that is what we are correcting"
    build_instrument_inbound(c)
    inbound, edges = c.execute("SELECT inbound, edges FROM instrument_inbound "
                               "WHERE instrument_id=100").fetchone()
    assert inbound == 1, "the sibling citation is a pool-level self-cite"
    assert edges == 1


def test_dated_id_falls_back_to_the_earliest_dated_copy():
    """Canonical undated, two mirrors dated -> take the earlier mirror."""
    docs = [(100, 0), (101, JUL2025), (102, JUL2024), (200, JUL2025)]
    ident = [(100, 100, "canonical"), (101, 100, "mirror"), (102, 100, "mirror"),
             (200, 200, "unique")]
    c = _db(docs, ident, [(200, 100)])
    build_instrument_inbound(c)
    dated_id, dw = c.execute("SELECT dated_id, date_written FROM instrument_inbound "
                             "WHERE instrument_id=100").fetchone()
    assert dated_id == 102, "earliest dated copy when the canonical has no date"
    assert dw == JUL2024


def test_a_wholly_undated_pool_still_gets_a_row():
    docs = [(100, 0), (101, 0), (200, JUL2025)]
    ident = [(100, 100, "canonical"), (101, 100, "mirror"), (200, 200, "unique")]
    c = _db(docs, ident, [(200, 101)])
    build_instrument_inbound(c)
    row = c.execute("SELECT inbound, dated_id, date_written FROM instrument_inbound "
                    "WHERE instrument_id=100").fetchone()
    assert row == (1, None, 0), row


def test_documents_with_no_identity_row_are_skipped_not_crashed():
    docs = [(100, JUL2024), (200, JUL2025)]
    ident = [(200, 200, "unique")]           # 100 has NO doc_identity row
    c = _db(docs, ident, [(200, 100)])
    build_instrument_inbound(c)
    assert c.execute("SELECT COUNT(*) FROM instrument_inbound").fetchone()[0] == 0


def test_degrades_when_doc_identity_has_no_instrument_role_column():
    """This script runs in the nightly, so a doc_identity built before
    `instrument_role` existed must degrade to plain earliest-dated, not abort Phase 2c.
    (tests/test_tracker_intensity.py's older fixture exercises this path too.)"""
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE documents (id INTEGER PRIMARY KEY, site_key TEXT, "
              "date_written INTEGER, body_text_cn TEXT)")
    c.execute("CREATE TABLE citations (id INTEGER PRIMARY KEY, source_id INTEGER, "
              "target_id INTEGER)")
    # NOTE: no instrument_role column
    c.execute("CREATE TABLE doc_identity (doc_id INTEGER PRIMARY KEY, instrument_id INTEGER)")
    c.executescript(DDL)
    for did, dw in [(100, 0), (101, JUL2025), (102, JUL2024), (200, JUL2025)]:
        c.execute("INSERT INTO documents (id, site_key, date_written, body_text_cn) "
                  "VALUES (?,'s',?,'')", (did, dw))
    for did, iid in [(100, 100), (101, 100), (102, 100), (200, 200)]:
        c.execute("INSERT INTO doc_identity VALUES (?,?)", (did, iid))
    c.execute("INSERT INTO citations (source_id, target_id) VALUES (200, 100)")
    c.commit()
    build_doc_inbound(c)
    build_instrument_inbound(c)      # must not raise
    dated_id, dw = c.execute("SELECT dated_id, date_written FROM instrument_inbound "
                             "WHERE instrument_id=100").fetchone()
    assert dated_id == 102, "earliest dated copy, with no role preference available"
    assert dw == JUL2024


if __name__ == "__main__":
    for fn in list(globals().values()):
        if callable(fn) and getattr(fn, "__name__", "").startswith("test_"):
            fn(); print("ok", fn.__name__)
    print("all instrument_inbound checks passed")
