"""A 文号 head can belong to two governments; the SITE breaks the tie (2026-10-08).

docs/working/qa-wenhao-province-ambiguity.md. `doc_identity.province` (A6) reads the
locality from the document's own header fields in priority order, and the 文号 agency comes
second — before the title masthead. The 文号 registry (issuer_parser.DOCNUM_SUBNATIONAL)
lists 惠府 -> 惠州市人民政府 and 惠府办 -> 惠州市人民政府办公室, but 无锡市惠山区 signs its
documents 惠府发 / 惠府办 / 惠府办规 / 惠府规发 too. So 22 `wxd_huishan` documents resolved
to `gd` (Guangdong) instead of `js`, and were then silently dropped by the same-province
gate in build_diffusion_events — missing from every Jiangsu figure in fidelity-wuxi.md.

Nothing in the 文号 can disambiguate those heads. Two fixes, both tested here:

  1. geo.DISTRICT_CITY had NONE of Wuxi's sub-divisions, so every bare-district locality
     the Wuxi portals emit resolved to None and the province HAD to come from the 文号.
     The five districts and two county-level cities are now mapped to 无锡市.
     An UNMAPPED district still returns None — never a guess off its first character.
  2. derive_province takes the site's province as an ARBITER (not a candidate): when an
     ambiguous 文号 head disagrees with the site, the 文号 candidate is dropped and the
     remaining fields decide. Unambiguous heads are untouched, so a joint 粤府函 批复 whose
     masthead names another province keeps the 文号's province.

Run: python3 -m pytest tests/test_wenhao_province_ambiguity.py -v
  or: python3 tests/test_wenhao_province_ambiguity.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "rnd" / "analysis"))
sys.path.insert(0, str(ROOT / "scripts" / "rnd" / "classification"))

import geo  # noqa: E402
import build_doc_identity as bdi  # noqa: E402

HUISHAN_TITLE = "无锡市惠山区人民政府办公室关于印发惠山区企业转贷应急资金管理办法（试行）的通知"
HUIZHOU_TITLE = "惠州市人民政府办公室关于印发2016年惠州市食品安全重点工作安排的通知"


def _doc(title, docnum, publisher=""):
    return {"title": title, "docnum": docnum, "publisher": publisher}


# --------------------------------------------------------------------------- #
# 1. the ambiguous head, arbitrated by the site                                #
# --------------------------------------------------------------------------- #
def test_huifu_on_a_wuxi_district_site_is_jiangsu():
    """惠府* + a Wuxi district site -> js. All four series the corpus actually holds."""
    for docnum in ("惠府发〔2023〕12号", "惠府办〔2026〕14号",
                   "惠府办规〔2025〕2号", "惠府规发〔2025〕1号"):
        got = bdi.derive_province(_doc(HUISHAN_TITLE, docnum), None, "js")
        assert got == "js", f"{docnum} on wxd_huishan -> {got!r}, expected 'js'"


def test_huifu_on_huizhou_is_still_guangdong():
    """The same head on 惠州's own portal must not move: no conflict, no arbitration."""
    for docnum in ("惠府办函〔2016〕12号", "惠府〔2016〕12号", "惠府办〔2016〕12号"):
        got = bdi.derive_province(_doc(HUIZHOU_TITLE, docnum), None, "gd")
        assert got == "gd", f"{docnum} on huizhou -> {got!r}, expected 'gd'"


def test_huifu_with_a_bare_title_still_resolves_on_huizhou():
    """A Huizhou doc whose title names no locality keeps the 文号 reading (gd)."""
    doc = _doc("关于印发市级储备粮管理办法的通知", "惠府办〔2016〕12号")
    assert bdi.derive_province(doc, None, "gd") == "gd"


def test_arbitration_needs_a_site_province():
    """No site province -> nothing to arbitrate against, so behaviour is unchanged."""
    doc = _doc("关于印发市级储备粮管理办法的通知", "惠府办〔2016〕12号")
    assert bdi.derive_province(doc, None, None) == "gd"
    assert bdi.derive_province(doc, None) == "gd"          # old 2-arg call still works


def test_arbitration_is_gated_on_the_ambiguous_set():
    """An UNAMBIGUOUS head keeps the 文号's province even when the masthead disagrees:
    粤府函〔2015〕170号 is a joint 闽粤 批复 issued out of the Guangdong registry."""
    doc = _doc("福建省人民政府广东省人民政府关于闽粤经济合作区发展规划的批复", "粤府函〔2015〕170号")
    assert bdi.province_of_name(bdi.masthead_of(doc["title"])) == "fj"   # masthead says fj
    assert bdi.derive_province(doc, None, "gd") == "gd"


def test_lead_issuer_still_outranks_everything():
    """The arbitration touches only the 文号 candidate; a named lead issuer wins first."""
    doc = _doc(HUISHAN_TITLE, "惠府办〔2026〕14号")
    assert bdi.derive_province(doc, "无锡市惠山区人民政府办公室", "js") == "js"
    # ...including when the issuer disagrees with the site (a repost of another province)
    assert bdi.derive_province(doc, "山东省人民政府办公厅", "js") == "sd"


def test_ambiguous_set_members_are_real_registry_keys():
    for key in bdi.AMBIGUOUS_DOCNUM_PREFIXES:
        assert key in bdi.DOCNUM_SUBNATIONAL, f"{key} is not a 文号 registry key"


def test_docnum_registry_key_matches_the_series_suffix():
    assert bdi.docnum_registry_key("惠府办规〔2025〕2号") == "惠府办"
    assert bdi.docnum_registry_key("惠府规发〔2025〕1号") == "惠府"
    assert bdi.docnum_registry_key("沪府发〔2024〕1号") == "沪府"
    assert bdi.docnum_registry_key("关于印发的通知") is None


# --------------------------------------------------------------------------- #
# 2. the geo tables: Wuxi mapped, unmapped districts still None                #
# --------------------------------------------------------------------------- #
WUXI_DIVISIONS = ["梁溪区", "锡山区", "惠山区", "滨湖区", "新吴区", "江阴市", "宜兴市"]


def test_every_wuxi_division_resolves_to_jiangsu():
    for place in WUXI_DIVISIONS:
        assert geo.province_name_of_place(place) == "江苏省", place
        assert geo.PROVINCE_CODE[geo.province_name_of_place(place)] == "js", place


def test_wuxi_divisions_have_a_jurisdiction_chain():
    """Without a chain a district document can never flip to `implementing` /
    localized_of against its own city or province."""
    for place in WUXI_DIVISIONS:
        assert bdi.jurisdiction_chain(place) == ("无锡市", "江苏省"), place


def test_unmapped_district_with_an_ambiguous_head_is_none():
    """惠城区 is 惠州's own district and 江岸区 is 武汉's; neither is in DISTRICT_CITY, and
    neither may be resolved by the 惠 / 江 heads the 文号 registry happens to use. A bare
    district absent from the table returns None — a missing entry, not a guess."""
    for place in ("惠城区", "江岸区", "锡山", "武昌区", "新吴"):
        assert geo.province_name_of_place(place) is None, place
        assert bdi.jurisdiction_chain(place) is None, place


def test_locality_of_a_huishan_masthead_is_wuxi():
    """The masthead is the field that decides once the 文号 is dropped."""
    assert bdi.province_of_name("无锡市惠山区人民政府办公室") == "js"
    assert bdi.province_of_name("无锡市惠山区人民政府") == "js"
    assert bdi.province_of_name("惠州市人民政府办公室") == "gd"


# --------------------------------------------------------------------------- #
# 3. the existing self-tests must still pass                                   #
# --------------------------------------------------------------------------- #
def test_geo_self_test_passes():
    assert geo._self_test()


def test_doc_identity_self_test_passes():
    assert bdi.self_test()


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok   {name}")
            except AssertionError as e:
                fails += 1
                print(f"FAIL {name}: {e}")
    print(f"{'FAILED' if fails else 'all passed'} ({fails} failures)")
    sys.exit(1 if fails else 0)
