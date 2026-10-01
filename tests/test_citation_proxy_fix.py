"""Regression check for the citation resolver's proxy-target bug (2026-10).

docs/research/citation-network-structure.md §1.3: a document citing a national law
by 《name》 used to resolve to ANY title that CONTAINS the law's name (e.g.
河南省实施《中华人民共和国城乡规划法》办法 took 2,139 inbound; the law itself took 0),
because the exact-title tier was gated on len(normalized ref) >= 8 and national
laws normalize short (城乡规划法 = 5 chars).

Rule under test: an EXACT normalized-title candidate wins over containment;
containment is only a fallback when no exact candidate exists.

Run: python3 -m pytest tests/test_citation_proxy_fix.py -v
  or: python3 tests/test_citation_proxy_fix.py   (assert-based, no pytest needed)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "rnd" / "citations"))

from extract_citations import TitleMatcher, _norm_title  # noqa: E402

LAW_NPC = 12742122
LAW_MEE = 12685270
HENAN = 12749787
GD = 12748220

TITLES = {
    "河南省实施《中华人民共和国城乡规划法》办法": (HENAN, "npc"),
    "中华人民共和国城乡规划法": (LAW_MEE, "mee"),          # bureau mirror, listed FIRST
    "中华人民共和国城乡规划法 ": (LAW_NPC, "npc"),          # central copy (trailing space)
    "广东省城乡规划条例": (GD, "npc"),
    "国务院关于印发《制造业绿色低碳发展行动方案》的通知": (1, "gov"),
}
LEVELS = {"npc": "central", "gov": "central", "mee": "central", "gd": "provincial"}


def _matcher():
    return TitleMatcher(TITLES, LEVELS)


def test_law_beats_proxy_measure():
    m = _matcher()
    for ref in ("中华人民共和国城乡规划法", "城乡规划法", "《中华人民共和国城乡规划法》"):
        got = m.resolve_ref(ref, 8)
        assert got in (LAW_NPC, LAW_MEE), f"{ref!r} -> {got}, expected the law, not Henan"
        assert got != HENAN


def test_containment_still_fires_when_no_exact_title():
    """Recall path kept: a ref with no exact-title doc still resolves by containment."""
    m = _matcher()
    assert m.resolve_ref("制造业绿色低碳发展行动方案", 8) == 1


def test_exact_core_beats_containment_on_whole_ref():
    m = _matcher()
    # 《law》 core is exact; the whole ref (with qualifier) would only match by containment.
    assert m.resolve_ref("《中华人民共和国城乡规划法》（2019年修正）", 8) in (LAW_NPC, LAW_MEE)


def test_mirror_tiebreak_is_deterministic_lowest_id_within_level():
    m = _matcher()
    # both copies are central-level here; lowest id wins deterministically
    assert m.resolve_ref("城乡规划法", 8) == min(LAW_NPC, LAW_MEE)


def test_norm_title_folds_prc_prefix_and_brackets():
    assert _norm_title("《中华人民共和国城乡规划法》") == "城乡规划法"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL OK")
