"""KNOWN_LOCALITIES is seeded from geo.CITY_PROVINCE, not from the 文号 registry (2026-10-08).

docs/working/qa-wenhao-province-ambiguity.md §8. `build_doc_identity.locality_in_core`
accepts a locality prefix inside an instrument core only if the name is in
`KNOWN_LOCALITIES`, and that set WAS seeded from `issuer_parser.DOCNUM_SUBNATIONAL`. The
registry is a list of 文号 heads, not a list of localities, so it vouched for exactly the
23 cities that happen to have one — 苏州市 (via 苏府) was in, 无锡市 was not. `localized_of`
then fired on 2 Wuxi pairs against 44 Suzhou ones, an ordering impossible as a fact about
Wuxi (43.2% of its titles carry the city name vs 54.1% of Suzhou's) and plain as a fact
about a hand-maintained list: the "hand-maintained table silently bounds a measurement"
shape in CLAUDE.md.

The seed is now `geo.CITY_PROVINCE` (354 prefecture-level divisions), the same complete
table the province resolver and `jurisdiction_chain()` already read: 54 -> 381 names.

What was measured corpus-wide before shipping (two scratch rebuilds of the 346,955-doc
corpus, side by side, read-only):

  * instrument pooling moves by exactly 1 document  (1 merge, 0 splits)
  * `diffusion_events` rebuilds BYTE-IDENTICAL; `validate_cascades` 15/15 either way
  * 1,336 new `localized_of` edges (2,075 -> 3,411), 1,287 on the npc 地方法规 tier
  * adversarial: 0 of 2,149 site-resolvable newly-localized docs got another province's
    locality; 0 of 9,873 contradicted their own publisher / lead_issuer / 文号

The invariants that already cost work to establish are pinned below as well, because this
set feeds pooling: they must not move.

Run: python3 -m pytest tests/test_known_localities.py -v
  or: python3 tests/test_known_localities.py
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


# --------------------------------------------------------------------------- #
# The seed itself                                                              #
# --------------------------------------------------------------------------- #
def test_seeded_from_city_province_not_the_docnum_registry():
    """Every prefecture-level division is a known locality, not just the ~23 with 文号."""
    missing = set(geo.CITY_PROVINCE) - set(bdi.KNOWN_LOCALITIES)
    assert not missing, f"{len(missing)} prefectures absent from KNOWN_LOCALITIES: " \
                        f"{sorted(missing)[:10]}"
    assert len(bdi.KNOWN_LOCALITIES) > 300, len(bdi.KNOWN_LOCALITIES)


def test_the_docnum_registry_names_are_still_there():
    """Widening the seed must not drop what the registry contributed (provinces are
    province-shaped and also accepted by the _PROV_HEAD branch, but they were IN the set
    and the 文号 cities must stay in it)."""
    for name in ("广东省", "江苏省", "深圳市", "苏州市", "北京市", "重庆市", "新疆维吾尔自治区"):
        assert name in bdi.KNOWN_LOCALITIES, name


def test_county_level_cities_are_deliberately_absent():
    """CITY_PROVINCE holds PREFECTURE-level divisions only. That is load-bearing: the
    word-collision-prone county-level names (东方市 in Hainan, which would swallow the
    市 of 东方市场) are not in it, so they cannot be read as a locality prefix."""
    assert "东方市" not in bdi.KNOWN_LOCALITIES
    assert bdi.locality_in_core("东方市场管理办法", "") is None
    assert bdi.locality_in_core("东方市场建设管理办法", "") is None


# --------------------------------------------------------------------------- #
# The Wuxi case (the bug this fixes)                                           #
# --------------------------------------------------------------------------- #
def test_wuxi_locality_is_read_from_a_core_prefix():
    assert bdi.locality_in_core("无锡市见义勇为称号评定实施办法", "") == "无锡市"


def test_wuxi_title_localizes_like_suzhou():
    """The two cities must behave the same way; only the hand-maintained set ever
    separated them."""
    wx = bdi.localize("市政府关于印发无锡市见义勇为称号评定实施办法的通知", "wuxi")
    assert wx == ("见义勇为称号评定实施办法", "无锡市", bdi.LEVEL_RANK["municipal"]), wx
    sz = bdi.localize("苏州市户籍准入登记管理办法", "suzhou")
    assert sz == ("户籍准入登记管理办法", "苏州市", bdi.LEVEL_RANK["municipal"]), sz


def test_wuxi_joins_its_provincial_chain():
    """The flip needs jurisdiction_chain(无锡市) to name Jiangsu."""
    assert bdi.jurisdiction_chain("无锡市") == ("江苏省",)


def test_a_newly_known_city_elsewhere_in_the_country():
    """Not a Jiangsu special case: the npc 地方法规 tier is cities all over the map."""
    assert bdi.localize("百色市非物质文化遗产保护条例", "npc") == (
        "非物质文化遗产保护条例", "百色市", bdi.LEVEL_RANK["municipal"])
    assert bdi.jurisdiction_chain("百色市") == ("广西壮族自治区",)
    # 地区 / 盟 divisions resolve too (they are prefecture-level, and _LOC_FIRST matches them)
    assert bdi.locality_in_core("喀什地区公共资源交易管理办法", "") == "喀什地区"
    assert bdi.locality_in_core("锡林郭勒盟建筑施工安全管理办法", "") == "锡林郭勒盟"


# --------------------------------------------------------------------------- #
# Adversarial: a city MENTIONED in a title is not the issuer's locality        #
# --------------------------------------------------------------------------- #
def test_a_mentioned_city_does_not_capture_the_locality():
    """With 354 names the mention risk grows, so pin it: `locality_in_core` anchors at ^
    and the masthead decides, so a Guangdong / Jiangsu document that merely NAMES 无锡市
    keeps its own locality."""
    for title, site, expected in (
        ("广东省人民政府办公厅关于学习推广无锡市经验的通知", "gd", "广东省"),
        ("江苏省人民政府关于支持无锡市深化改革的若干意见", "js", "江苏省"),
    ):
        stem, loc, _ = bdi.localize(title, site)
        assert loc == expected, f"{title} -> {loc!r}, expected {expected!r}"
        assert "无锡" in stem  # the mention stays IN the stem; it was never a prefix


def test_a_forwarded_other_city_document_is_not_localized_to_the_forwarder():
    """A 转发 wrapper keeps the wrapper as its core, so the forwarding province does not
    acquire the other city's locality (and the other city does not acquire the doc)."""
    stem, loc, _ = bdi.localize("关于转发《无锡市城市管理办法》的通知", "gd")
    assert loc is None, loc


def test_non_locality_lookalikes_are_still_refused():
    """The set is the only thing standing between '批发市' and a locality."""
    for core in ("批发市场管理办法", "超市食品安全管理规定", "民族地区教育发展规划",
                 "智慧城市建设方案", "城乡规划法"):
        assert bdi.locality_in_core(core, "") is None, core


# --------------------------------------------------------------------------- #
# Invariants this set feeds (pooling) — measured identical old vs wide         #
# --------------------------------------------------------------------------- #
def test_national_statutes_do_not_acquire_a_locality():
    """A statute core must keep its whole stem, or every copy of it would re-key."""
    for title in ("中华人民共和国城乡规划法", "中华人民共和国政府信息公开条例",
                  "中华人民共和国道路交通安全法"):
        stem, loc, _ = bdi.localize(title, "npc")
        assert loc is None, (title, loc)
        assert stem == bdi.instrument_key(title)


def test_guowuyuan_ling_stays_unpoolable():
    """All 29 中华人民共和国国务院令 rows are `unique`; the title is a VEHICLE, not a name,
    so it must reach no instrument key at all (CLAUDE.md's length-floor lesson)."""
    assert bdi.localize("中华人民共和国国务院令", "gov") == (None, None, None)
    assert bdi.instrument_key("中华人民共和国国务院令") is None


def test_annual_series_titles_keep_their_locality_and_stem():
    """政府工作报告 splits per year by the series rule, which keys off (stem, locality) —
    so the locality must be the government's own, for a newly-known city too."""
    stem, loc, _ = bdi.localize("无锡市人民政府工作报告", "wuxi")
    assert (stem, loc) == ("人民政府工作报告", "无锡市"), (stem, loc)


def test_self_test_still_passes():
    """The builder's own 203-case self-test (pooling, flips, localize, levels, genres)."""
    assert bdi.self_test() is True


if __name__ == "__main__":
    import traceback
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok   {name}")
            except Exception:
                fails += 1
                print(f"FAIL {name}")
                traceback.print_exc()
    sys.exit(1 if fails else 0)
