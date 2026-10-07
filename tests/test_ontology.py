"""Source-type ontology: explicit yaml layer + admin_level fallback layer.

Regression under test: the hand-listed yaml rotted to 231/510 unmapped site_keys
(21k docs in "Other") as the crawler fleet grew. The fallback must place a key
from its admin_level / govcms group when the yaml is silent, the yaml must still
win when it speaks, and media must NEVER be assigned by fallback (the
"exclude news" filter must not swallow a government site).

Run: python3 tests/test_ontology.py   (assert-based, no pytest needed)
  or: python3 -m pytest tests/test_ontology.py -v
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from web.services import ontology as O  # noqa: E402


def test_explicit_wins_over_fallback():
    # cas carries admin_level='central' in the DB but is listed under research.
    assert O.site_to_type("cas", "central") == "research"
    assert O.resolve("cas", "central") == ("research", "explicit")
    # cq is 'municipal' in the DB but explicitly province-level.
    assert O.site_to_type("cq", "municipal") == "local_province"
    # stdaily is 'central' in the DB but a newspaper.
    assert O.site_to_type("stdaily", "central") == "media_state"


def test_prefix_families():
    for key in ("fj_czt", "hn_kjt", "jl_jyt", "ln_swt", "sd_gxt", "bjb_fgw", "shb_edu"):
        assert O.resolve(key, "municipal") == ("local_provincial_dept", "prefix"), key
    assert O.resolve("bjd_haidian", "district") == ("local_district", "prefix")
    assert O.resolve("cqd_yuzhong", "district") == ("local_district", "prefix")


def test_fallback_by_admin_level():
    # A brand-new prefecture city the yaml has never heard of.
    assert O.resolve("zz_newcity_2099", "municipal") == ("local_municipality", "fallback")
    assert O.resolve("newprov2099", "provincial") == ("local_province", "fallback")
    # provincial + underscore = <prov>_<dept> family member.
    assert O.resolve("newprov_dept2099", "provincial") == ("local_provincial_dept", "fallback")
    assert O.resolve("newagency2099", "central") == ("central_ministry", "fallback")
    assert O.resolve("newbureau2099", "department") == ("local_city_dept", "fallback")
    assert O.resolve("newdistrict2099", "district") == ("local_district", "fallback")
    assert O.resolve("newlab2099", "research") == ("research", "fallback")


def test_media_never_by_fallback():
    leaf, how = O.resolve("newsite_media_2099", "media")
    assert (leaf, how) == ("other", "unresolved")
    assert O.resolve("nolevel2099", None) == ("other", "unresolved")
    assert O.resolve("", None) == ("other", "unresolved")


def test_govcms_group_signal():
    # Known govcms sites resolve via group even when nothing else is passed:
    # feedback -> legislative leaves (explicit here, but the group rule must
    # agree), assoc -> research.
    assert O.site_to_type("jsrd") == "local_legislative"
    assert O.site_to_type("bjrd") == "local_legislative"
    assert O.site_to_type("npc_dbgz") == "central_legislative_judicial"
    assert O.site_to_type("amr") == "research"
    # Hypothetical unlisted feedback/assoc keys through the fallback itself.
    assert O._fallback_leaf("x", None) is None
    O._GOVCMS = dict(O._govcms_meta())
    O._GOVCMS["fake_rd"] = ("provincial", "feedback")
    O._GOVCMS["fake_cen_rd"] = ("central", "feedback")
    O._GOVCMS["fake_assoc"] = ("research", "assoc")
    try:
        assert O.resolve("fake_rd") == ("local_legislative", "fallback")
        assert O.resolve("fake_cen_rd") == ("central_legislative_judicial", "fallback")
        assert O.resolve("fake_assoc") == ("research", "fallback")
    finally:
        O._GOVCMS = None


def test_rows_register_levels_for_bare_lookups():
    rows = [{"site_key": "rowcity2099", "admin_level": "municipal"},
            {"site_key": "xinhua", "admin_level": "media"},
            ("tuplecity2099", "district")]
    under_local = O.sites_under("local", rows)
    assert "rowcity2099" in under_local and "tuplecity2099" in under_local
    assert "xinhua" not in under_local
    # Levels were registered, so a later bare-key call still resolves.
    assert O.site_to_type("rowcity2099") == "local_municipality"
    assert O.sites_excluding("media", rows) == ["rowcity2099", "tuplecity2099"]
    assert O.sites_under("media", rows) == ["xinhua"]


def test_validate_separates_fallback_from_unmapped():
    rows = [{"site_key": "gov", "admin_level": "central"},
            {"site_key": "somecity2099", "admin_level": "municipal"},
            {"site_key": "mystery2099", "admin_level": None},
            {"site_key": "newspaper2099", "admin_level": "media"}]
    r = O.validate(rows)
    assert r["explicit"] == {"gov": "central_state_council"}
    assert r["fallback"] == {"somecity2099": "local_municipality"}
    assert sorted(r["unmapped"]) == ["mystery2099", "newspaper2099"]
    assert r["total"] == 4


def test_tree_has_new_leaves():
    ids = O.node_ids()
    assert "local_legislative" in ids and "central_legislative_judicial" in ids
    assert set(O.FALLBACK_BY_LEVEL.values()) <= ids


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("all ontology tests passed")
