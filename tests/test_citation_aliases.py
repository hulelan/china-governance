"""Zero-crawl resolver recoveries (2026-10, docs/working/a6-recoverable-head.md).

(1) ALIAS: 广东省控制性详细规划管理条例 (340 distinct citers) is held as
    广东省城市控制性详细规划管理条例 — a one-word difference neither the exact tier nor
    containment can bridge. data/instrument_aliases.csv maps cited_as -> canonical_title,
    applied to the normalized ref BEFORE exact matching.
(2) HTML ENTITIES: refs extracted as 广东省实施&lt;…土地管理法&gt;办法 never matched the
    stored 《》 title. _clean_ref unescapes and turns <X> into 《X》.
(3) SHORT TITLES: 广东省公路条例 (7 chars) was excluded from the title index by the
    LENGTH(title) >= 8 floor (now 5); it is reachable through the exact tier only.

Run: python3 -m pytest tests/test_citation_aliases.py -v
  or: python3 tests/test_citation_aliases.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "rnd" / "citations"))

from extract_citations import (  # noqa: E402
    TitleMatcher, _clean_ref, _norm_title, load_aliases, ALIASES_PATH,
)

GD_KZXGH = 12747468   # 广东省城市控制性详细规划管理条例 (npc)
JX_KZXGH = 12755055   # 江西省城市和镇控制性详细规划管理条例 (npc) — must stay unaffected
GD_LAND = 501         # 广东省实施《中华人民共和国土地管理法》办法
GD_ROAD = 12733132    # 广东省公路条例 (7 chars)
GD_PLAN = 12748220    # 广东省城乡规划条例

TITLES = {
    "广东省城市控制性详细规划管理条例": (GD_KZXGH, "npc", "regulation"),
    "江西省城市和镇控制性详细规划管理条例": (JX_KZXGH, "npc", "regulation"),
    "广东省实施《中华人民共和国土地管理法》办法": (GD_LAND, "gd", "regulation"),
    "广东省公路条例": (GD_ROAD, "npc", "regulation"),
    "广东省城乡规划条例": (GD_PLAN, "npc", "regulation"),
}
LEVELS = {"npc": "central", "gd": "provincial"}
ALIASES = {_norm_title("广东省控制性详细规划管理条例"): _norm_title("广东省城市控制性详细规划管理条例")}


def _m(aliases=ALIASES):
    return TitleMatcher(TITLES, LEVELS, aliases=aliases)


def test_alias_resolves_to_held_doc():
    m = _m()
    for ref in ("广东省控制性详细规划管理条例", "《广东省控制性详细规划管理条例》"):
        assert m.resolve_ref(ref, 8) == GD_KZXGH, ref


def test_without_alias_the_ref_is_unresolved():
    """The alias is the ONLY path: shows the table is load-bearing, not redundant."""
    assert _m(aliases={}).resolve_ref("广东省控制性详细规划管理条例", 8) is None


def test_alias_csv_is_loaded_by_default_and_contains_the_gd_row():
    assert ALIASES_PATH.exists()
    table = load_aliases()
    assert table.get(_norm_title("广东省控制性详细规划管理条例")) == \
        _norm_title("广东省城市控制性详细规划管理条例")
    assert TitleMatcher(TITLES, LEVELS).resolve_ref("广东省控制性详细规划管理条例", 8) == GD_KZXGH


def test_unrelated_titles_unaffected_by_alias():
    m = _m()
    assert m.resolve_ref("江西省城市和镇控制性详细规划管理条例", 8) == JX_KZXGH
    assert m.resolve_ref("广东省城乡规划条例", 8) == GD_PLAN
    assert m.resolve_ref("广东省城市控制性详细规划管理条例", 8) == GD_KZXGH


def test_entity_encoded_ref_resolves():
    m = _m()
    ref = "广东省实施&lt;中华人民共和国土地管理法&gt;办法"
    assert _clean_ref(ref) == "广东省实施《中华人民共和国土地管理法》办法"
    assert m.resolve_ref(ref, 8) == GD_LAND
    assert m.resolve_ref(_clean_ref(ref), 8) == GD_LAND
    # &amp; and a ref with no entities are left alone
    assert _clean_ref("A&amp;B") == "A&B"
    assert _clean_ref("广东省公路条例") == "广东省公路条例"


def test_short_title_reachable_via_exact_tier_only():
    m = _m()
    assert m.resolve_ref("广东省公路条例", 8) == GD_ROAD
    assert m.resolve_ref("《广东省公路条例》", 8) == GD_ROAD
    # a different province's 公路条例 must NOT fall onto Guangdong's by containment
    assert m.resolve_ref("山西省公路条例", 8) is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL OK")
