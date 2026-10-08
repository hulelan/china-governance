"""Regression check: organization-name-only "masthead stub" titles are exact-only targets.

Measured 2026-10-07 on the live corpus: 2,260 crawled documents whose whole title is an
agency name (广东省自然资源厅, 深圳市住房和建设局, 江门市自然资源局 …) held 4,802 resolved
citation edges — 广东省自然资源厅 alone 692, ranking #20 by citation_rank — because
containment tier (a) ("a stored title is a substring of the cited name") let any ref that
EMBEDS the agency name land on the stub when the real instrument is not held. A hand-check
found every sampled edge a mis-resolution; zero resolved refs equalled a bare org name.

Rule under test (TitleMatcher(org_only_exact=True), which extract_all uses):
  * an org-name-only title is never a CONTAINMENT candidate,
  * it remains an EXACT-tier candidate,
  * real instruments whose titles contain an agency name resolve as before,
  * a title that names a body but is an instrument (成立…委员会) is not gated,
  * the default (off) leaves build_diffusion_events' stem matchers untouched.

Run: python3 -m pytest tests/test_org_only_containment.py -v
  or: python3 tests/test_org_only_containment.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "rnd" / "citations"))

from extract_citations import TitleMatcher, _is_org_only_title, _norm_title  # noqa: E402

STUB_GD_NR = 101629         # 广东省自然资源厅 (gd masthead stub, 'other', empty body)
STUB_GZ_PNR = 6467013       # 广州市规划和自然资源局 (genre word inside the agency name)
STUB_CDC = 1000001          # 深圳市疾病预防控制中心 (中心-suffix public institution)
NOTICE_LYD = 2000001        # the real 留用地 notice, held
SZ_DECREE = 4953518         # 深圳市人民政府令（第232号）深圳市前海深港现代服务业合作区管理局暂行办法
STUB_QH = 1345640           # 深圳市前海深港现代服务业合作区管理局 (stub)
SZ_JZ = 4985437             # 成立深圳市减灾委员会 (a decision, genre 'reply')
SZ_JZ_STUB = 3000001        # 深圳市减灾委员会 (a bare org stub)

TITLES = [
    ("广东省自然资源厅", (STUB_GD_NR, "gd", "other")),
    ("广州市规划和自然资源局", (STUB_GZ_PNR, "gz", "other")),
    ("深圳市疾病预防控制中心", (STUB_CDC, "sz", "other")),
    ("深圳市前海深港现代服务业合作区管理局", (STUB_QH, "sz", "other")),
    ("深圳市人民政府令（第232号）深圳市前海深港现代服务业合作区管理局暂行办法",
     (SZ_DECREE, "sz", "regulation")),
    ("广东省自然资源厅关于推进征收农村集体土地留用地高效开发利用的通知",
     (NOTICE_LYD, "gd", "notice")),
    ("成立深圳市减灾委员会", (SZ_JZ, "sz", "reply")),
]
LEVELS = {"gd": "provincial", "gz": "municipal", "sz": "municipal"}


def _m(gate=True):
    return TitleMatcher(TITLES, LEVELS, aliases={}, org_only_exact=gate)


def test_ref_embedding_agency_name_does_not_land_on_org_stub():
    m = _m()
    for ref in (
        "广东省自然资源厅印发关于加强和改进控制性详细规划管理若干指导意见（暂行）的通知",
        "《广东省自然资源厅关于印发〈某某办法〉的通知》（粤自然资规字〔2021〕9号）",
        "广州市住房和城乡建设局 广州市规划和自然资源局关于印发广州市地下管线工程竣工信息入库工作指引的通知",
        "深圳市疾病预防控制中心关于开展2025年度病媒生物监测工作的通知",
    ):
        assert m.resolve_ref(ref, 8) is None, ref


def test_gate_off_reproduces_the_old_false_edge():
    """Documents the defect: without the gate the stub absorbs the ref."""
    m = _m(gate=False)
    ref = "广东省自然资源厅印发关于加强和改进控制性详细规划管理若干指导意见（暂行）的通知"
    assert m.resolve_ref(ref, 8) == STUB_GD_NR


def test_exact_bare_organization_ref_still_resolves():
    m = _m()
    assert m.resolve_ref("广东省自然资源厅", 8) == STUB_GD_NR
    assert m.resolve_ref("《广州市规划和自然资源局》", 8) == STUB_GZ_PNR


def test_real_instrument_containing_agency_name_resolves_normally():
    m = _m()
    # held instrument whose title embeds the agency name: exact
    assert m.resolve_ref("《广东省自然资源厅关于推进征收农村集体土地留用地高效开发利用的通知》"
                         "（粤自然资规字〔2020〕4号）", 8) == NOTICE_LYD
    # the ref names an instrument held under a decree wrapper: containment now reaches it
    # instead of stopping at the longer org-only substring
    assert m.resolve_ref("深圳市前海深港现代服务业合作区管理局暂行办法", 8) == SZ_DECREE


def test_org_name_that_is_an_instrument_title_is_not_gated():
    assert not _is_org_only_title(_norm_title("成立深圳市减灾委员会"))
    m = _m()
    assert m.resolve_ref("关于成立深圳市减灾委员会的通知", 8) == SZ_JZ


def test_predicate_shape():
    yes = ("广东省自然资源厅", "深圳市住房和建设局", "区人民政府办公室", "广州市规划和自然资源局",
           "国家标准化管理委员会", "深圳市疾病预防控制中心",
           "对外贸易经济合作部、海关总署、国家质量监督检验检疫总局")
    no = ("广东省城乡规划条例", "深圳市国土空间总体规划", "成立深圳市减灾委员会",
          "我市召开党外人士情况通报会", "广东省自然资源厅关于印发某办法的通知",
          "首都功能核心区控制性详细规划发布 一张蓝图绘就首善之区",
          "坚持创新发展 再造北京产业新格局", "中华人民共和国城乡规划法")
    for t in yes:
        assert _is_org_only_title(_norm_title(t)), t
    for t in no:
        assert not _is_org_only_title(_norm_title(t)), t


def test_default_off_keeps_stem_matchers_unchanged():
    """build_diffusion_events builds TitleMatcher({stem: (id,)}) without the flag;
    org-shaped STEMS (国家认定企业技术中心) must keep their containment behaviour."""
    m = TitleMatcher({"国家认定企业技术中心": (7,)}, aliases={})
    assert m.org_only == frozenset()
    assert m.resolve("广东省关于做好国家认定企业技术中心复核评价工作的通知", 8) == 7


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    bad = 0
    for fn in fns:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except Exception:
            bad += 1
            print(f"  FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"\n{len(fns) - bad}/{len(fns)} passed")
    sys.exit(1 if bad else 0)
