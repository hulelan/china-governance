"""NFCMS walker (crawlers/sz_gazette.py) parsing checks, 2026-10-07.

Covers the generalization that let the gazette walker also read 大鹏新区's
规范性文件库 (`--site szdp_gfxwj`): the gazette mapping is unchanged (no
`relation`, 文号 from EXT_zh), the Dapeng mapping stores EXT_sx/EXT_type in
`relation` (chongqing's `repealed;` token for 无效) and reads the 文号 from the
body's promulgation line because the listing has none.

Run: python3 tests/test_sz_gazette_nfcms.py   (assert-based, no pytest needed)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from crawlers.sz_gazette import (  # noqa: E402
    NFCMS_SITES, article_to_doc, docnum_from_body, status_relation,
)

GAZETTE_ART = {
    "id": 9000001, "title": "深圳市人民政府关于印发《深圳市行政听证办法》的通知",
    "url": "https://www.sz.gov.cn/zfgb/2006/gb519/content/post_9000001.html",
    "date": "2006-09-01", "visible_publish_time": 1157068800,
    "EXT_zh": "深府〔2006〕150号", "EXT_fwdw": "深圳市人民政府", "EXT_sort": "市政府文件",
    "json_ext": "[]",
}
DAPENG_ART = {
    "id": 12373906, "source": "大鹏新区",
    "title": "深圳市大鹏新区综合办公室关于印发《深圳市大鹏新区科技创新和产业发展专项资金管理办法》的通知",
    "url": "https://www.dpxq.gov.cn/ztzl/gfxwjk/content/post_12373906.html",
    "date": "2025-09-11", "visible_publish_time": 1757574664,
    "json_ext": '{"EXT_sx":"有效","EXT_type":"政府规章"}',
    "EXT_sx": "有效", "EXT_type": "政府规章",
}


def test_gazette_mapping_unchanged():
    d = article_to_doc(GAZETTE_ART, {"id": 103442, "name": "2006年第49期（总第519期）"})
    assert d["document_number"] == "深府〔2006〕150号", d
    assert d["publisher"] == "深圳市人民政府"
    assert d["classify_main_name"] == "政府公报"
    assert d["classify_genre_name"] == "市政府文件"
    assert d["keywords"] == "2006年第49期（总第519期）"
    assert d["relation"] == "", d["relation"]


def test_dapeng_mapping_status_in_relation():
    cfg = NFCMS_SITES["szdp_gfxwj"]
    assert cfg["site_key"] == "szdp" and cfg["levels"] == 0
    d = article_to_doc(DAPENG_ART, {"id": 150493, "name": "规范性文件库"}, cfg)
    assert d["relation"] == "status=有效;type=政府规章", d["relation"]
    assert d["classify_main_name"] == "规范性文件库"
    assert d["classify_genre_name"] == "政府规章"
    assert d["document_number"] == ""          # listing has no 文号; comes from the body
    assert d["publisher"] == "大鹏新区"


def test_repealed_token_matches_chongqing_convention():
    rel = status_relation({"EXT_sx": "无效", "EXT_type": "其他"}, {})
    assert rel == "repealed;status=无效;type=其他", rel
    # json_ext-only fields are honoured too
    assert status_relation({}, {"EXT_sx": "有效"}) == "status=有效"
    assert status_relation({}, {}) == ""


def test_docnum_from_body():
    body = ("（2023年12月26日深鹏办规〔2023〕9号公布 根据2025年1月13日《深圳市大鹏新区管理委员会"
            "关于修订部分规范性文件的决定》修订）\n第一章 总则\n第一条 为最大限度地发挥……")
    assert docnum_from_body(body) == "深鹏办规〔2023〕9号"
    # standalone 文号 line under a notice title
    assert docnum_from_body("各有关单位：\n深府规 〔2020〕 1 号\n现印发……") == "深府规〔2020〕1号"
    assert docnum_from_body("第一条 本办法……无文号") == ""
    # a 文号 CITED in the text (replica of a live Dapeng body) is NOT the doc's own
    cited = ("各有关单位：\n《深圳市大鹏新区社会组织培育发展暂行办法》已经新区管委会同意，现印发给你们。\n"
             "大鹏新区统战和社会建设局\n2020年2月17日\n第一章 总则\n"
             "第一条 根据《关于深化社会组织管理制度改革的若干措施》（深办发〔2018〕25号），制定本办法。")
    assert docnum_from_body(cited) == "", docnum_from_body(cited)
    # only the head is scanned
    assert docnum_from_body("x\n" * 20 + "深府〔2006〕150号") == ""


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fails = 0
    for t in tests:
        try:
            t()
            print(f"ok   {t.__name__}")
        except AssertionError as e:
            fails += 1
            print(f"FAIL {t.__name__}: {str(e)[:300]}")
    print(f"{len(tests) - fails}/{len(tests)} passed")
    sys.exit(1 if fails else 0)
