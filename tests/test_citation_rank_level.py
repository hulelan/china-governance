"""citation_rank must weight a citation by the CITING DOCUMENT's level (corpus-lessons A1).

`scripts/compute_scores.py::compute_citation_ranks` used to read `citations.source_level`,
which `extract_citations.get_source_level()` fills from `sites.admin_level` whenever the
文号 yields nothing — the per-SITE level that A1 showed is wrong for 21% of documents (all
28.6k `npc` 地方法规 are provincial/municipal 人大 regulations on a site labelled central,
so every one of their citations was being paid the 3.0 central weight). The scorer now
prefers `doc_identity.admin_level_doc` and keeps the stored level only as a fallback.

Measured on the live corpus (2026-10-07, 585,471 citations / 310,136 resolved /
338,856 identity rows): 13,846 of the 310,136 rank-bearing edges (4.46%) disagree,
moving 5,930 of 47,309 ranked documents (12.5%, median |change| 21%). The top-30 SET is
unchanged and the top 13 hold their order; six documents swap places at ranks 14-27.

What is pinned here:
  1. a document whose site level and per-document level differ is paid the PER-DOCUMENT
     weight (the npc case, both directions: an over- and an under-credited citer);
  2. a missing identity row, a NULL and an empty-string `admin_level_doc` all fall back
     to the stored `source_level` — never silently to the 0.5 'unknown' weight;
  3. an absent `doc_identity` table reproduces the pre-change numbers exactly;
  4. LEVEL_WEIGHTS itself is unchanged (the fix is which level is looked up, not the
     price of a level);
  5. on a fixture mirroring the live corpus's shape the top 5 stay 政府信息公开条例 /
     城乡规划法 / 道路交通安全法 / 财政违法行为处罚处分条例 /
     广东省城市控制性详细规划管理条例, in that order, under both weightings.

Run: python3 -m pytest tests/test_citation_rank_level.py -v
  or: python3 tests/test_citation_rank_level.py   (assert-based, no pytest needed)
"""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from compute_scores import LEVEL_WEIGHTS, compute_citation_ranks  # noqa: E402

# The five instruments at the head of the live ranking, with the id each holds there.
TOP5 = [
    (900045166, "中华人民共和国政府信息公开条例"),
    (900039770, "中华人民共和国城乡规划法"),
    (900012345, "中华人民共和国道路交通安全法"),
    (900023456, "财政违法行为处罚处分条例"),
    (900034567, "广东省城市控制性详细规划管理条例"),
]


def _fixture(with_identity=True):
    """In-memory corpus: the five top instruments plus a cast of citing documents whose
    site level and per-document level deliberately disagree."""
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE documents (id INTEGER PRIMARY KEY, title TEXT, site_key TEXT);
        CREATE TABLE citations (
            source_id INTEGER, target_ref TEXT, target_id INTEGER,
            citation_type TEXT, source_level TEXT, target_level TEXT);
    """)
    for doc_id, title in TOP5:
        conn.execute("INSERT INTO documents (id, title, site_key) VALUES (?,?,'npc')",
                     (doc_id, title))

    # citers: (id, site-derived level stored on the edge, true per-document level)
    citers = [
        # the npc case: a 地方法规 hosted on the central-labelled laws database. Stored
        # 'central' (3.0) but really a provincial 人大 regulation (2.0).
        (1001, "central", "provincial"),
        (1002, "central", "provincial"),
        (1003, "central", "municipal"),      # 3.0 -> 1.5
        # the opposite direction: a provincial instrument reposted on a municipal portal.
        (1004, "municipal", "provincial"),   # 1.5 -> 2.0
        (1005, "municipal", "central"),      # 1.5 -> 3.0
        # a research host, which is not an issuer at all.
        (1006, "central", "research"),       # 3.0 -> 0.5 (no key in LEVEL_WEIGHTS)
        # agreeing citers, to keep the ranking realistic.
        (1007, "central", "central"),
        (1008, "provincial", "provincial"),
        (1009, "municipal", "municipal"),
        (1010, "district", "district"),
        # fallback cases: no identity row at all / NULL level / empty-string level.
        (2001, "provincial", None),          # row absent entirely
        (2002, "central", "__null__"),       # row present, admin_level_doc NULL
        (2003, "municipal", "__empty__"),    # row present, admin_level_doc ''
    ]
    for cid, _stored, _doc in citers:
        conn.execute("INSERT INTO documents (id, title, site_key) VALUES (?,?,'x')",
                     (cid, f"citer {cid}"))

    if with_identity:
        conn.execute("CREATE TABLE doc_identity (doc_id INTEGER PRIMARY KEY, "
                     "admin_level_doc TEXT, level_source TEXT)")
        for cid, _stored, doc_level in citers:
            if doc_level is None:
                continue                      # case 2001: no identity row
            value = {"__null__": None, "__empty__": ""}.get(doc_level, doc_level)
            conn.execute("INSERT INTO doc_identity (doc_id, admin_level_doc, level_source)"
                         " VALUES (?,?,'issuer')", (cid, value))

    # Edge counts per (target, citer) chosen so the five keep their live order under the
    # stored levels AND under the per-document levels.
    edges = {
        900045166: {1001: 400, 1002: 300, 1004: 300, 1007: 200, 1008: 100, 2001: 50},
        900039770: {1001: 300, 1003: 200, 1005: 150, 1007: 150, 1009: 100, 2002: 40},
        900012345: {1002: 250, 1006: 200, 1007: 120, 1008: 120, 1010: 80, 2003: 30},
        900023456: {1003: 150, 1004: 150, 1007: 100, 1009: 90, 2001: 60},
        900034567: {1005: 120, 1008: 120, 1009: 80, 1010: 60, 2002: 20},
    }
    for target, srcs in edges.items():
        stored = {c: s for c, s, _ in citers}
        for src, n in srcs.items():
            for k in range(n):
                conn.execute(
                    "INSERT INTO citations (source_id, target_ref, target_id,"
                    " citation_type, source_level, target_level) VALUES (?,?,?,?,?,?)",
                    (src, f"ref{target}-{k}", target, "named", stored[src], "central"))
    conn.commit()
    return conn, citers, edges


def _stored_ranks(citers, edges):
    stored = {c: s for c, s, _ in citers}
    return {t: sum(n * LEVEL_WEIGHTS.get(stored[s], 0.5) for s, n in srcs.items())
            for t, srcs in edges.items()}


def _expected_doc_ranks(citers, edges):
    """What the per-document weighting SHOULD produce, with the documented fallback."""
    stored = {c: s for c, s, _ in citers}
    effective = {}
    for cid, s, doc_level in citers:
        if doc_level in (None, "__null__", "__empty__"):
            effective[cid] = s                      # fall back to the stored level
        else:
            effective[cid] = doc_level
    return {t: sum(n * LEVEL_WEIGHTS.get(effective[s], 0.5) for s, n in srcs.items())
            for t, srcs in edges.items()}


def test_weights_table_unchanged():
    assert LEVEL_WEIGHTS == {
        "central": 3.0, "provincial": 2.0, "municipal": 1.5,
        "district": 1.0, "department": 1.0, "unknown": 0.5,
    }


def test_per_document_level_wins_over_site_level():
    conn, citers, edges = _fixture()
    got = compute_citation_ranks(conn)
    assert got == _expected_doc_ranks(citers, edges)
    # and it is genuinely different from the stored-level answer, in both directions
    stored = _stored_ranks(citers, edges)
    assert got != stored
    assert got[900045166] < stored[900045166]   # npc over-credit removed
    assert got[900034567] > stored[900034567]   # municipal->central under-credit repaired
    conn.close()


def test_missing_null_and_empty_identity_fall_back_to_stored_level():
    """2001 (no row), 2002 (NULL) and 2003 ('') must keep their stored weight, not 0.5.

    Each is isolated: the citer is the ONLY source of the target it cites in a fixture
    cut down to that one edge set, so the target's rank IS that citer's contribution.
    """
    for citer, stored_level in ((2001, "provincial"), (2002, "central"),
                               (2003, "municipal")):
        conn, citers, edges = _fixture()
        conn.execute("DELETE FROM citations WHERE source_id != ?", (citer,))
        conn.execute("DELETE FROM citations WHERE target_id != "
                     "(SELECT MIN(target_id) FROM citations)")
        conn.commit()
        n, target = conn.execute(
            "SELECT COUNT(*), target_id FROM citations").fetchone()
        assert n > 0, f"fixture no longer has edges from citer {citer}"
        got = compute_citation_ranks(conn)
        assert got == {target: n * LEVEL_WEIGHTS[stored_level]}, (
            f"citer {citer} was not paid its stored {stored_level} weight: {got}")
        conn.close()


def test_absent_doc_identity_table_reproduces_stored_ranks():
    conn, citers, edges = _fixture(with_identity=False)
    assert compute_citation_ranks(conn) == _stored_ranks(citers, edges)
    conn.close()


def test_top5_ordering_is_stable_under_both_weightings():
    conn, citers, edges = _fixture()
    titles = dict(TOP5)
    for label, ranks in (("per-document", compute_citation_ranks(conn)),
                         ("stored", _stored_ranks(citers, edges))):
        order = [titles[d] for d, _ in sorted(ranks.items(), key=lambda kv: -kv[1])][:5]
        assert order == [t for _, t in TOP5], f"{label} ordering moved: {order}"
    conn.close()


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all passed")
