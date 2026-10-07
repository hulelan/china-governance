"""Mirror selection in the citation resolver must be DETERMINISTIC (2026-10-07).

docs/working/qa-cxgh-citer-drop.md §4.2: `extract_citations.extract_all` used to build
`title_to_doc[title] = ...` from an UNORDERED `SELECT ... WHERE LENGTH(title) >= 5`, so
when several documents shared a byte-identical title the LAST row scanned silently
clobbered its predecessors and only that one ever reached `TitleMatcher`. The winner was
therefore decided by scan order, not by the documented (genre_rank, level_rank, id)
tie-break: 中华人民共和国城乡规划法 is held 3× and all 2,158 edges landed on the HIGHEST
id. Ingesting a higher-id mirror would have moved them again — and made
validate_cascades' pinned CXGH_ID read ~0 on a healthy graph.

Rules under test:
  1. every copy reaches the matcher (the pair/list input form), so
  2. the representative is (genre_rank, level_rank, LOWEST id) regardless of row order,
  3. a higher-id mirror can never flip an established representative, and
  4. the dict input form still works for the other callers (build_diffusion_events).

Run: python3 -m pytest tests/test_citation_mirror_determinism.py -v
  or: python3 tests/test_citation_mirror_determinism.py   (assert-based, no pytest)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "rnd" / "citations"))

from extract_citations import TitleMatcher  # noqa: E402

LAW = "中华人民共和国城乡规划法"
MEE = 12685270      # mee mirror, central, law   (lowest id -> the representative)
NPC_A = 12742122    # npc copy, central, law
NPC_B = 12747143    # npc copy, central, law     (highest id -> the old accidental winner)
LEVELS = {"mee": "central", "npc": "central", "bj": "provincial", "shb_fgw": "municipal",
          "stic": "central"}

# the live shape: three byte-identical titles, same genre, same admin level
MIRRORS = [
    (LAW, (MEE, "mee", "law")),
    (LAW, (NPC_A, "npc", "law")),
    (LAW, (NPC_B, "npc", "law")),
]


def _ids(m):
    return [m.resolve_ref(r, 8) for r in (LAW, "城乡规划法", f"《{LAW}》")]


def test_identical_titles_pick_the_documented_representative():
    m = TitleMatcher(MIRRORS, LEVELS)
    assert _ids(m) == [MEE, MEE, MEE], _ids(m)


def test_row_order_does_not_decide():
    """Feed the same three rows in both directions: same winner, both times."""
    fwd = TitleMatcher(MIRRORS, LEVELS)
    rev = TitleMatcher(list(reversed(MIRRORS)), LEVELS)
    assert _ids(fwd) == _ids(rev) == [MEE, MEE, MEE]
    assert fwd.exact == rev.exact and fwd.core == rev.core


def test_a_higher_id_mirror_does_not_change_the_winner():
    """The regression that would have failed validate_cascades on a healthy graph."""
    before = TitleMatcher(MIRRORS, LEVELS).resolve_ref(LAW, 8)
    newcomer = MIRRORS + [(LAW, (999_999_999, "npc", "law"))]
    assert TitleMatcher(newcomer, LEVELS).resolve_ref(LAW, 8) == before == MEE
    # ... and it does not matter where in the scan the newcomer lands
    assert TitleMatcher([newcomer[-1]] + MIRRORS, LEVELS).resolve_ref(LAW, 8) == MEE


def test_level_rank_beats_id_so_a_municipal_repost_never_wins():
    """The live 政府信息公开条例 case: a district 发改委 repost (id 900154149) held all
    2,302 edges while the central mee copy held 0, because the dict clobber kept the
    last row and the level tier never got to vote."""
    title = "中华人民共和国政府信息公开条例"
    rows = [(title, (12685154, "mee", "regulation")),
            (title, (900154149, "shb_fgw", "regulation"))]   # municipal, HIGHER id
    for order in (rows, list(reversed(rows))):
        assert TitleMatcher(order, LEVELS).resolve_ref(title, 8) == 12685154


def test_genre_rank_beats_both_level_and_id():
    title = "提振消费专项行动方案"
    rows = [(f"《{title}》解读", (1, "stic", "explainer")),       # lowest id, central, news
            (title, (900_000_001, "bj", "action_plan"))]        # highest id, provincial
    for order in (rows, list(reversed(rows))):
        assert TitleMatcher(order, LEVELS).resolve_ref(title, 8) == 900_000_001


def test_dict_input_still_accepted():
    """build_diffusion_events + the older tests pass {title: value} dicts."""
    m = TitleMatcher({LAW: (NPC_B, "npc", "law"), "广东省城乡规划条例": (1, "bj", "regulation")},
                     LEVELS)
    assert m.resolve_ref(LAW, 8) == NPC_B


def test_generator_input_accepted():
    m = TitleMatcher((p for p in MIRRORS), LEVELS)
    assert m.resolve_ref(LAW, 8) == MEE


def test_losing_mirrors_add_no_new_keys_or_targets():
    """Admitting the mirrors must not change WHICH refs resolve — only to which copy."""
    one = TitleMatcher([MIRRORS[2]], LEVELS)
    all_ = TitleMatcher(MIRRORS, LEVELS)
    assert set(one.exact) == set(all_.exact)
    assert set(one.core) == set(all_.core)
    assert set(all_.exact.values()) == {MEE}


def test_extract_all_end_to_end_on_a_scratch_db():
    """The real `extract_all` path (not just TitleMatcher): three mirrors + one citer
    in a throwaway SQLite DB. The edge must land on the lowest-id copy whichever way
    the rows were inserted."""
    import sqlite3
    import tempfile

    import extract_citations as ec

    def run(order):
        with tempfile.TemporaryDirectory() as tmp:
            conn = sqlite3.connect(f"{tmp}/scratch.db")
            conn.executescript(
                "CREATE TABLE documents (id INTEGER PRIMARY KEY, title TEXT, site_key TEXT,"
                " algo_doc_type TEXT, document_number TEXT DEFAULT '', body_text_cn TEXT,"
                " references_json TEXT);"
                "CREATE TABLE sites (site_key TEXT PRIMARY KEY, admin_level TEXT);"
                "CREATE TABLE citations (id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " source_id INTEGER NOT NULL, target_ref TEXT NOT NULL, target_id INTEGER,"
                " citation_type TEXT NOT NULL, source_level TEXT NOT NULL,"
                " target_level TEXT NOT NULL, UNIQUE(source_id, target_ref, citation_type));"
            )
            conn.executemany(
                "INSERT INTO documents (id, title, site_key, algo_doc_type, document_number,"
                " body_text_cn, references_json) VALUES (?,?,?,?,'',?,'')",
                [(i, LAW, sk, "law", None) for i, sk in order]
                + [(900_200_000, "某市城乡规划管理实施细则", "bj", "regulation",
                    "根据《中华人民共和国城乡规划法》的规定，制定本细则。" * 2)],
            )
            conn.executemany("INSERT INTO sites VALUES (?,?)",
                             [("mee", "central"), ("npc", "central"), ("bj", "provincial")])
            ec.extract_all(conn)
            got = conn.execute(
                "SELECT DISTINCT target_id FROM citations WHERE target_ref LIKE '%城乡规划法%'"
            ).fetchall()
            conn.close()
            return got

    rows = [(MEE, "mee"), (NPC_A, "npc"), (NPC_B, "npc")]
    assert run(rows) == [(MEE,)]
    assert run(list(reversed(rows))) == [(MEE,)]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL OK")
