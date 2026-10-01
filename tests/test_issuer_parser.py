"""Regression checks for issuer_parser (docs/research/joint-issuance.md §6a).

Bug under test: the 粤办 文号 alias mapped 粤办函 to 中共广东省委办公厅 and the parser
UNIONED that docnum lead with the single `publisher` name (广东省人民政府办公厅),
manufacturing a phantom 省委办公厅+省政府办公厅 pair on ~176 gd.gov.cn letters
(the spurious Guangdong 2010-12 joint-issuance bump).

Rules: (1) 粤办函 is the government office's letter series; 粤办发 stays 两办.
(2) A sub-national 文号 never ADDS a co-signer next to one differing portal name —
it replaces it. (3) A real 两办 masthead in the title still yields the pair.

Run: python3 tests/test_issuer_parser.py   (assert-based, no pytest needed)
  or: python3 -m pytest tests/test_issuer_parser.py -v
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "rnd" / "classification"))

from issuer_parser import parse_doc, parse_docnum  # noqa: E402

GOV_OFFICE = "广东省人民政府办公厅"
PARTY_OFFICE = "中共广东省委办公厅"


def test_yueban_han_is_government_office():
    assert parse_docnum("粤办函〔2012〕109号", "provincial", "gd") == (GOV_OFFICE, False)
    assert parse_docnum("粤办发〔2016〕22号", "provincial", "gd") == (PARTY_OFFICE, False)
    assert parse_docnum("粤府办〔2020〕5号", "provincial", "gd") == (GOV_OFFICE, False)


def test_single_issuer_yueban_han_no_phantom_pair():
    # The §6a hand-check case: body signed by the government office alone.
    r = parse_doc(
        title="印发广东省人民政府有关部门与各民主党派省委会对口联系方案的通知",
        docnum="粤办函〔2012〕109号",
        publisher=GOV_OFFICE,
        body_head="粤办函〔２０１２〕１０９号印发广东省人民政府有关部门与各民主党派省委会对口联系方案的通知省政府各部门、各直属机构：",
        admin_level="provincial", site_key="gd")
    assert r["issuers"] == [GOV_OFFICE], r
    assert r["n_issuers"] == 1


def test_subnational_docnum_replaces_single_portal_publisher():
    # Reposted on a bureau portal: publisher is the posting unit, not a co-signer.
    r = parse_doc(
        title="关于开阳高速公路阳江收费站车辆通行费有关问题的复函",
        docnum="粤办函〔2011〕781号", publisher="广东省商务厅",
        body_head="粤办函〔2011〕781号 关于开阳高速公路阳江收费站车辆通行费有关问题的复函 省交通运输厅：",
        admin_level="provincial", site_key="gd")
    assert r["issuers"] == [GOV_OFFICE], r
    assert r["n_issuers"] == 1


def test_real_two_office_masthead_still_joint():
    r = parse_doc(
        title="中共广东省委办公厅 广东省人民政府办公厅印发《关于我省全面推进政务公开工作实施意见》的通知",
        docnum="粤办发〔2016〕22号",
        publisher="中共广东省委办公厅 广东省人民政府办公厅",
        body_head="中共广东省委办公厅 广东省人民政府办公厅 印发《关于我省全面推进政务公开工作实施意见》的通知 各地级以上市党委、人民政府：",
        admin_level="provincial", site_key="gd")
    assert r["issuers"] == [PARTY_OFFICE, GOV_OFFICE], r
    assert r["n_issuers"] == 2


def test_central_union_unchanged():
    # Central docnum + a differing single publisher keeps the old union behaviour.
    r = parse_doc(title="关于做好某项工作的通知", docnum="财建〔2020〕12号",
                  publisher="国家税务总局", body_head="", admin_level="central", site_key="mof")
    assert r["issuers"] == ["财政部", "税务总局"], r


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("all issuer_parser tests passed")
