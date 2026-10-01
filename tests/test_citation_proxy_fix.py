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

from extract_citations import TitleMatcher, _norm_title, _title_cores_of_title  # noqa: E402

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


def test_accepts_one_tuple_values_like_build_diffusion_events():
    """build_diffusion_events passes {stem: (id,)} with no site_levels — must not break."""
    m = TitleMatcher({"中华人民共和国城乡规划法": (LAW_NPC,), "广东省城乡规划条例": (GD,)})
    assert m.resolve_ref("城乡规划法", 8) == LAW_NPC


def test_norm_title_folds_prc_prefix_and_brackets():
    assert _norm_title("《中华人民共和国城乡规划法》") == "城乡规划法"


# --- Round 2 (consistency-review H1): wrapper cores + genre priority + gated containment

GOV_PLAN = 12650974       # 中共中央办公厅 国务院办公厅印发《提振消费专项行动方案》 (gov, central)
XINHUA_PLAN = 12704698    # 受权发布丨… (xinhua, central)
BJ_NEWS = 900105357       # 北京发布《深化改革提振消费专项行动方案》 (bj, provincial news)
BJ_NOTICE = 12685355      # 北京市人民政府关于印发《北京市深化改革提振消费专项行动方案》的通知
ZH_NOTICE = 3824586       # 珠海市人民政府办公室关于印发珠海市提振消费专项行动方案的通知（珠府办〔2025〕6号）
EXPLAINER = 12084462      # 《提振消费专项行动方案》和“我”有啥关系？专家这样解读
GA_RULE = 11637955        # 机动车驾驶证申领和使用规定（公安部令第162号）
BJ_QA = 900111176         # 公安部交管局有关负责人就《机动车驾驶证申领和使用规定》热点问题解答
HEYUAN_NEWS = 573943      # 以头号工程的力度抓紧抓实“百千万工程” …
SZ_PERMIT = 12758835      # …关于公布半山润府三期（C区）项目《建设工程规划许可证》及总平面图的通告

TITLES2 = {
    "北京发布《深化改革提振消费专项行动方案》": (BJ_NEWS, "bj", "action_plan"),
    "中共中央办公厅 国务院办公厅印发《提振消费专项行动方案》": (GOV_PLAN, "gov", "action_plan"),
    "受权发布丨中共中央办公厅 国务院办公厅印发《提振消费专项行动方案》": (XINHUA_PLAN, "xinhua", "action_plan"),
    "北京市人民政府关于印发《北京市深化改革提振消费专项行动方案》的通知": (BJ_NOTICE, "bj", "action_plan"),
    "珠海市人民政府办公室关于印发珠海市提振消费专项行动方案的通知（珠府办〔2025〕6号）": (ZH_NOTICE, "zhuhai", "action_plan"),
    "《提振消费专项行动方案》和“我”有啥关系？专家这样解读": (EXPLAINER, "stic", "explainer"),
    "机动车驾驶证申领和使用规定（公安部令第162号）": (GA_RULE, "ga", "regulation"),
    "公安部交管局有关负责人就《机动车驾驶证申领和使用规定》热点问题解答": (BJ_QA, "bj", "other"),
    "以头号工程的力度抓紧抓实“百千万工程” 推动城乡区域协调发展 不断取得新进展新成效": (HEYUAN_NEWS, "heyuan", "other"),
    "深圳市规划和自然资源局深汕管理局关于公布半山润府三期（C区）项目《建设工程规划许可证》及总平面图的通告": (SZ_PERMIT, "sz_invest", "announcement"),
    "河南省实施《中华人民共和国城乡规划法》办法": (HENAN, "henan", "regulation"),
    "中华人民共和国城乡规划法": (LAW_NPC, "npc", "law"),
    "广东省城乡规划条例": (GD, "gd", "regulation"),
    "国务院关于印发《制造业绿色低碳发展行动方案》的通知": (1, "gov", "policy_issuance"),
}
LEVELS2 = {"npc": "central", "gov": "central", "xinhua": "central", "ga": "central",
           "stic": "central", "bj": "provincial", "gd": "provincial", "henan": "provincial",
           "heyuan": "municipal", "zhuhai": "municipal", "sz_invest": "municipal"}


def _m2():
    return TitleMatcher(TITLES2, LEVELS2)


def test_boost_consumption_resolves_to_central_promulgation_not_bj_news():
    m = _m2()
    for ref in ("提振消费专项行动方案", "《提振消费专项行动方案》"):
        got = m.resolve_ref(ref, 8)
        assert got in (GOV_PLAN, XINHUA_PLAN), f"{ref!r} -> {got}"
        assert got != BJ_NEWS


def test_wrapper_core_strips_masthead_and_news_lead():
    assert _norm_title("提振消费专项行动方案") in [
        _norm_title(c) for c, _ in _title_cores_of_title(
            "受权发布丨中共中央办公厅 国务院办公厅印发《提振消费专项行动方案》")]
    assert _norm_title("珠海市提振消费专项行动方案") in [
        _norm_title(c) for c, _ in _title_cores_of_title(
            "珠海市人民政府办公室关于印发珠海市提振消费专项行动方案的通知（珠府办〔2025〕6号）")]
    # documents ABOUT X are not X
    assert _title_cores_of_title("河南省实施《中华人民共和国城乡规划法》办法") == []
    assert _title_cores_of_title("关于贯彻落实《提振消费专项行动方案》的通知") == []
    assert _title_cores_of_title("一图看懂《北京市深化改革提振消费专项行动方案》") == []


def test_beijing_variant_still_resolves_to_its_own_notice():
    m = _m2()
    assert m.resolve_ref("北京市深化改革提振消费专项行动方案", 8) == BJ_NOTICE


def test_driving_licence_rule_not_the_qa_page():
    m = _m2()
    for ref in ("机动车驾驶证申领和使用规定", "《机动车驾驶证申领和使用规定》"):
        got = m.resolve_ref(ref, 8)
        assert got != BJ_QA, f"{ref!r} -> Q&A page"
        # the rule's own title carries a 文号 tail; wrapper-core stripping or
        # promulgation-gated containment must land on it
        assert got == GA_RULE


def test_containment_never_lands_on_news_or_permit_notice():
    m = _m2()
    assert m.resolve_ref("百千万工程", 8) is None          # unresolved beats a news proxy
    assert m.resolve_ref("建设工程规划许可证", 8) is None   # permit notice is not the instrument


def test_containment_still_fires_for_promulgation_genre():
    m = _m2()
    assert m.resolve_ref("制造业绿色低碳发展行动方案", 8) == 1


def test_city_planning_law_still_wins_with_genres():
    m = _m2()
    for ref in ("中华人民共和国城乡规划法", "城乡规划法", "《中华人民共和国城乡规划法》（2019年修正）"):
        assert m.resolve_ref(ref, 8) == LAW_NPC


def test_no_genre_info_is_not_gated():
    """build_diffusion_events passes stems with no genre: containment must keep recall."""
    m = TitleMatcher({"以头号工程的力度抓紧抓实百千万工程推动城乡区域协调发展": (HEYUAN_NEWS,)})
    assert m.resolve("百千万工程", 5) == HEYUAN_NEWS


def test_news_page_never_beats_promulgation_in_exact_tier():
    m = TitleMatcher({
        "提振消费专项行动方案": (7, "bj", "other"),                      # bare-title repost, provincial
        "国务院办公厅印发《提振消费专项行动方案》": (GOV_PLAN, "gov", "action_plan"),
        "《提振消费专项行动方案》解读": (EXPLAINER, "gov", "explainer"),
    }, LEVELS2)
    assert m.resolve_ref("提振消费专项行动方案", 8) == GOV_PLAN


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL OK")
