"""Career parser + overlap builder for officials.db.

Fixtures are lines copied from the STORED `officials.baike_career_text` of real
officials (陈希 1566, 蔡奇 1795, 陈吉宁 1767, plus the worst-affected shapes found
when the old parser was measured on 2026-11-25):

  * `1979年-1982年 …`     陈希: 18 clean lines -> 1 garbled record, zero overlaps
  * `1969.04-1970.06，…`  王儒林: a comma after the range -> 31 lines, 0 records
  * `1963.09——1968.08，`  梁保华: double em-dash -> 27 lines, 1 record
  * `2022.10- …` / `2023- …`  open-ended current post -> dropped
  * `1982 － 1988 …`      张业遂: full-width dash with spaces
  * multi-post lines filed under the first body only (蔡奇 北京市委书记 hidden
    behind 中央政治局, so no overlap with 陈吉宁 in Beijing)
  * award lines parsed as posts (陈吉宁 获清华大学…一等奖)

Run: python3 -m pytest tests/test_baike_career.py -v
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from crawlers.baike_career import parse_career_text, split_date_prefix  # noqa: E402
from compute_overlaps import counts_for_overlap, find_overlaps  # noqa: E402

CHEN_XI = """1979年-1979年 福州大学化工系教师
1979年-1982年 清华大学化学与化学工程系催化动力学专业硕士研究生
1982年-1984年 清华大学校团委军体部部长、副书记
1987年-1990年 清华大学党委常委、学生工作部部长，校团委书记
1993年-2000年 清华大学党委副书记、工会主席、体委主任（其间：1997年-1998年 中央党校一年制中青年干部培训班学习；1999.07被评为研究员）
2002年-2008年 清华大学党委书记
2008年-2010年 教育部副部长、党组副书记
2010年-2011年 辽宁省委副书记
2017年-2018年 中央政治局委员、中央书记处书记，中央组织部部长，中央党校校长
2023年- 中央党校（国家行政学院）校长（院长）"""

CAI_QI = """1973-1975年 福建省永安县西洋公社插队知青
1975-1978年 福建师范大学政教系政教专业学习
1983-1987年 福建省委办公厅综合处干部、副处长
1992-1993年 福建省委党建办副主任、省委办公厅厅务会议成员
1997-1999年 福建省三明市委副书记、副市长、市长
2010-2013年 浙江省委常委、组织部部长
2013-2014年 浙江省委常委、副省长
2014-2015年 中央国家安全委员会办公室副主任
2016-2017年 北京市委副书记、代市长、市长，北京2022年冬奥会和冬残奥会组织委员会执行主席、党组副书记
2017-2017年 北京市委书记，北京2022年冬奥会和冬残奥会组织委员会主席、党组书记
2017-2022年 中央政治局委员，北京市委书记，北京2022年冬奥会和冬残奥会组织委员会主席、党组书记
2023- 中央政治局常委、中央书记处书记、中央办公厅主任、中央和国家机关工委书记"""

CHEN_JINING = """1981.09-1986.07 清华大学土木与环境工程系环境工程专业学习，获理学学士学位；
1998.03-1999.07 清华大学环境科学与工程系副主任；
1999.07-2006.02 清华大学环境科学与工程系主任；
2006.02-2007.12 清华大学副校长；
2007.12-2012.01 清华大学常务副校长（正局级）；
2012.01-2015.01 清华大学校长（副部长级）；
2015.02-2017.05 环境保护部部长、党组书记；
2017.05-2017.06 北京市委副书记，副市长、代市长、市政府党组书记、北京冬奥组委党组副书记；
2017.06-2018.01 北京市委副书记，副市长、代市长、市政府党组书记、北京冬奥组委执行主席、党组副书记；
2018.01-2022.10 北京市委副书记，市长、市政府党组书记，北京2022年冬奥会和冬残奥会组织委员会执行主席、党组副书记；
2022.10- 中共二十届中央政治局委员，上海市委书记。
2001年和2005年两次获得清华大学研究生“良师益友”奖。
2004年获清华大学教学工作优秀成果一等奖。
2005年中华人民共和国建设部华夏建设科学技术奖一等奖。"""


def _by_org(text):
    out = {}
    for r in parse_career_text(text):
        out.setdefault(r["organization"], []).append(r)
    return out


def _orgs_of(text, start_year):
    return {r["organization"]: r["position"] for r in parse_career_text(text) if r["start_year"] == start_year}


# --- defect 1: date-range shapes ------------------------------------------------

@pytest.mark.parametrize("line,expect", [
    ("1979年-1982年 清华大学", (1979, None, 1982, None, False)),
    ("1969.04-1970.06，吉林省抚松县", (1969, 4, 1970, 6, False)),
    ("1963.09——1968.08，太仓县", (1963, 9, 1968, 8, False)),
    ("1976.08--1978.04，四川省", (1976, 8, 1978, 4, False)),
    ("1989-1990年，新华通讯社", (1989, None, 1990, None, False)),
    ("1982 － 1988 外交部国际司", (1982, None, 1988, None, False)),
    ("1933年11月至1934年8月，指挥所部", (1933, 11, 1934, 8, False)),
    ("1945年9月至11月同刘伯承", (1945, 9, 1945, 11, False)),
    ("2022.10- 中共二十届", (2022, 10, None, None, True)),
    ("2023- 中央政治局常委", (2023, None, None, None, True)),
    ("2023年- 中央党校", (2023, None, None, None, True)),
    ("2003.12—，北京军区", (2003, 12, None, None, True)),
    ("2013年至今 某部", (2013, None, None, None, True)),
])
def test_date_prefix_shapes(line, expect):
    got = split_date_prefix(line)
    assert got is not None, line
    assert got[:5] == expect


def test_chen_xi_every_post_line_parses():
    recs = parse_career_text(CHEN_XI)
    lines = {r["raw_text"] for r in recs}
    assert len(lines) == 9          # 10 lines, one of them is his master's degree
    assert not any("硕士研究生" in ln for ln in lines)
    by = _by_org(CHEN_XI)
    secretary = [r for r in by["清华大学"] if r["position"] == "党委书记"]
    assert [(r["start_year"], r["end_year"]) for r in secretary] == [(2002, 2008)]
    assert by["教育部"][0]["position"] == "副部长、党组副书记"
    assert by["辽宁省委"][0]["province"] == "辽宁"


def test_parenthetical_study_does_not_leak_into_the_post():
    r = [x for x in parse_career_text(CHEN_XI) if x["start_year"] == 1993]
    assert [(x["organization"], x["position"], x["end_year"]) for x in r] == \
        [("清华大学", "党委副书记、工会主席、体委主任", 2000)]


def test_sub_unit_stays_with_its_institution():
    """学生工作部 after 清华大学党委常委 is a department of Tsinghua, not a body of its own."""
    assert set(_orgs_of(CHEN_XI, 1987)) == {"清华大学"}


def test_comma_and_double_dash_shapes_yield_records():
    recs = parse_career_text(
        "1985.07-1986.11，吉林省前郭县副县长\n"
        "1987.08-1991.04，共青团吉林省委书记、党组书记\n"
        "1975.08——1975.12，太仓县委办公室副主任；\n"
        "2013 － 2018 外交部党委书记、副部长")
    assert [(r["organization"], r["position"]) for r in recs] == [
        ("前郭县政府", "副县长"), ("共青团吉林省委", "书记、党组书记"),
        ("太仓县委办公室", "副主任"), ("外交部", "党委书记、副部长")]


# --- defect 2: one record per held post; clean org/position boundary ---------------

def test_cai_qi_multi_post_line_gives_one_record_per_body():
    posts = _orgs_of(CAI_QI, 2017)
    assert posts["中央政治局"] == "委员"
    assert posts["北京市委"] == "书记"
    assert posts["北京2022年冬奥会和冬残奥会组织委员会"] == "主席、党组书记"


def test_org_position_boundary_is_not_cut_mid_word():
    by = _by_org(CAI_QI)
    assert "中央国家安全委" not in by and "北京市" not in by and "福建省" not in by
    assert by["中央国家安全委员会"][0]["position"] == "办公室副主任"
    assert by["福建省委办公厅"][0]["position"] == "综合处干部、副处长"
    for r in parse_career_text(CAI_QI + "\n" + CHEN_JINING + "\n" + CHEN_XI):
        assert not r["position"].startswith(("员会", "委副", "委书记", "委常委")), r


def test_elided_prefix_resolves_from_the_line():
    assert _orgs_of(CAI_QI, 1997) == {"三明市委": "副书记", "三明市政府": "副市长、市长"}
    assert _orgs_of(CAI_QI, 2010) == {"浙江省委": "常委", "浙江省委组织部": "部长"}
    assert _orgs_of(CAI_QI, 2013) == {"浙江省委": "常委", "浙江省政府": "副省长"}
    assert _orgs_of(CAI_QI, 1992) == {"福建省委党建办": "副主任", "福建省委办公厅": "厅务会议成员"}


def test_province_follows_the_locality_not_the_first_word():
    r = [x for x in parse_career_text(CAI_QI) if x["organization"] == "三明市委"][0]
    assert (r["province"], r["admin_level"]) == ("福建", "municipal")


def test_ministry_enterprises_are_separate_workplaces():
    a = parse_career_text("1982.07-1984.09 兵器工业部第五五九厂科研所干部")[0]["organization"]
    b = parse_career_text("1982年5月至1986年7月兵器工业部216厂副厂长、厂长、党委委员；")[0]["organization"]
    assert a != b and a.startswith("兵器工业部") and b.startswith("兵器工业部")


# --- defect 3: awards, study, removals are not posts ------------------------------

def test_awards_and_study_are_dropped():
    recs = parse_career_text(CHEN_JINING)
    assert not any("奖" in r["raw_text"] for r in recs)
    assert not any("学习" in r["raw_text"] for r in recs)
    assert not any(r["organization"].startswith("获") for r in recs)


def test_removal_notice_is_not_an_appointment():
    assert parse_career_text("2013年3月，吴邦国同志不再担任全国人大常委会委员长职务。") == []
    assert parse_career_text("2007.04-2007.06 免去汪恕诚的水利部部长职务") == []


# --- defect 4: open-ended current post is kept ------------------------------------

def test_open_ended_post_is_kept_with_null_end():
    last = [r for r in parse_career_text(CHEN_JINING) if r["start_year"] == 2022 and r["start_month"] == 10
            and r["end_year"] is None]
    assert {(r["organization"], r["position"]) for r in last} == {("中央政治局", "委员"), ("上海市委", "书记")}
    cq = [r for r in parse_career_text(CAI_QI) if r["start_year"] == 2023]
    assert {r["organization"] for r in cq} == {"中央政治局", "中央书记处", "中央办公厅", "中央和国家机关工委"}
    assert all(r["end_year"] is None for r in cq)


def test_single_date_entry_ends_at_next_entry_capped_at_five_years():
    recs = parse_career_text("1994年，任中国人民银行行长助理；\n1996年，任中国人民银行副行长；\n2013年，任国家外汇管理局局长")
    assert [(r["start_year"], r["end_year"]) for r in recs] == [(1994, 1996), (1996, None), (2013, None)]


# --- overlaps -----------------------------------------------------------------------

def _rows(off_id, text):
    return [(off_id, r["organization"], r["position"], r["province"], r["start_year"], r["start_month"],
             r["end_year"], r["end_month"]) for r in parse_career_text(text)]


AS_OF = 2026 * 12 + 4


def test_cai_qi_and_chen_jining_overlap_in_beijing():
    found = find_overlaps(_rows(1795, CAI_QI) + _rows(1767, CHEN_JINING), AS_OF)
    bj = [f for f in found if f[2] == "北京市委"]
    assert len(bj) == 1, "consecutive rows in one body must merge into ONE overlap row"
    a, b, _org, prov, sy, ey, months = bj[0]
    assert (a, b, prov, sy, ey) == (1767, 1795, "北京", 2017, 2022)
    assert 55 <= months <= 66


def test_chen_xi_and_chen_jining_overlap_at_tsinghua():
    found = find_overlaps(_rows(1566, CHEN_XI) + _rows(1767, CHEN_JINING), AS_OF)
    th = [f for f in found if f[2] == "清华大学"]
    # 陈希 was Tsinghua party secretary 2002-2008; 陈吉宁 was there throughout
    assert any(f[4] <= 2002 and f[5] >= 2008 and f[6] >= 70 for f in th), th


def test_mass_bodies_pair_only_their_leadership():
    assert not counts_for_overlap("中央委员会", "委员")
    assert not counts_for_overlap("全国政协", "常委")
    assert counts_for_overlap("全国政协", "副主席")
    assert counts_for_overlap("中央政治局", "委员")
    assert not counts_for_overlap("陆军", "排长")
    assert not counts_for_overlap("", "部长")


def test_open_ended_post_runs_to_the_crawl_only_if_plausibly_current():
    stale = (1, "某某省委", "书记", None, 1990, 1, None, None)       # end unknown: counts 2 years
    recent = (2, "某某省委", "副书记", None, 2023, 1, None, None)
    assert find_overlaps([stale, recent], AS_OF) == []
    current = (1, "某某省委", "书记", None, 2022, 1, None, None)     # began < 5y before the crawl
    months = find_overlaps([current, recent], AS_OF)[0][6]
    assert months == AS_OF - (2023 * 12 + 1)                        # 2023.01 to the 2026.04 crawl


def test_touching_tenures_with_fuzzy_dates_are_not_an_overlap():
    """王安顺 left 北京市政府 in 2016.10; 蔡奇's row is the year-only "2016-2017年"."""
    rows = [(1, "北京市政府", "市长", "北京", 2013, 1, 2016, 10),
            (2, "北京市政府", "代市长、市长", "北京", 2016, None, 2017, None)]
    assert find_overlaps(rows, AS_OF) == []
    rows[1] = (2, "北京市政府", "副市长", "北京", 2016, 7, 2017, 5)     # month-precise: a real 3 months
    assert find_overlaps(rows, AS_OF)[0][6] == 3


def test_rows_a_month_apart_are_one_tenure():
    rows = [(1, "广东省委", "常委", "广东", 2020, 5, 2022, 6), (1, "广东省委", "常委", "广东", 2022, 7, 2022, 9),
            (2, "广东省委", "副书记", "广东", 2018, 12, 2025, 9)]
    found = find_overlaps(rows, AS_OF)
    assert len(found) == 1 and found[0][4:6] == (2020, 2022)


# --- stored-HTML re-extraction ------------------------------------------------------

def test_paragraph_extraction_joins_inline_spans():
    """Baike wraps each link in its own <span>; the old reader cut the line there."""
    bs4 = pytest.importorskip("bs4")
    from crawlers.baike import _extract_career_text
    html = (
        '<div data-tag="paragraph"><span data-text="true">2011-2014 外交部新闻司司</span>'
        '<span data-text="true">长、外交部发言人</span></div>'
        '<div data-tag="paragraph"><span data-text="true">1982年07月-1983年07月，在</span>'
        '<span data-text="true"><a href="/item/x">北京大学</a></span>'
        '<span data-text="true">国际政治系任教；</span>'
        '<span class="supWrap_XpeMg"><sup>[3]</sup></span></div>'
    )
    text = _extract_career_text(bs4.BeautifulSoup(html, "html.parser"))
    assert text.split("\n") == ["2011-2014 外交部新闻司司长、外交部发言人",
                                "1982年07月-1983年07月，在北京大学国际政治系任教；"]
    recs = parse_career_text(text)
    assert [(r["organization"], r["position"]) for r in recs] == [
        ("外交部", "新闻司司长、发言人"), ("北京大学", "国际政治系任教")]
