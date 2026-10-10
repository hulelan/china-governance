"""The 三公经费 table parser: its accounting validator and its four known traps.

Every assertion here is a row the parser must accept or reject for a stated reason, and
each rejection case is a bug this parser actually shipped (see the module docstring and
docs/working/sangong-dataset.md):

  * a full-body offset used as a slice offset  -> returned ZERO rows
  * a 年度 column parsed as money              -> 因公出国 at 76% of the total, p90 2022.00
  * no scale bound                             -> accepted 3,439,824.70万元
  * the last balancing 购置/运行 pair, not the first -> swapped the two
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.rnd.analysis.sangong_table import parse, MAX_WANYUAN  # noqa: E402

# The hand-verified row: 深圳市人力资源和社会保障局 2019 年度部门决算, doc 8147994.
# 181.76 + 57.06 + 23.17 = 261.99, inside TOL of the published 262.00.
HRSS = """深圳市人力资源和社会保障局2019年度部门决算
公开07表
"三公"经费支出决算表
单位：万元
"三公"经费合计 262.00 因公出国（境）费 181.76 公务用车购置及运行费 57.06 公务接待费 23.17
"""


def test_hand_verified_row_parses_to_its_published_figures():
    rows, err = parse(HRSS)
    assert err is None
    assert len(rows) == 1
    assert rows[0]["total"] == 262.00
    assert rows[0]["out"] == 181.76
    assert rows[0]["car"] == 57.06
    assert rows[0]["host"] == 23.17


def test_identity_holds_on_every_accepted_row():
    rows, _ = parse(HRSS)
    r = rows[0]
    assert abs(r["total"] - (r["out"] + r["car"] + r["host"])) <= 0.05


def test_split_absent_when_only_the_combined_car_label_appears():
    """公务用车购置及运行费 is one figure; inventing a split from it would be wrong."""
    rows, _ = parse(HRSS)
    assert rows[0]["buy"] is None and rows[0]["run"] is None


SPLIT = """"三公"经费合计 100.00
因公出国（境）费 20.00
公务用车购置及运行费 50.00
公务用车购置费 30.00
公务用车运行维护费 20.00
公务接待费 30.00
"""


def test_car_split_balances_and_keeps_buy_and_run_the_right_way_round():
    rows, err = parse(SPLIT)
    assert err is None
    r = rows[0]
    assert r["car"] == 50.00
    # The `buy` label matches inside 公务用车购置及运行费, so its candidate list starts
    # with 50.00 and several pairs sum to 50. Only the first balancing pair has
    # 购置=30 / 运行=20; taking the last gave (20, 30).
    assert (r["buy"], r["run"]) == (30.00, 20.00)
    assert abs(r["car"] - (r["buy"] + r["run"])) <= 0.05


YEAR_COLUMN = """"三公"经费支出表
年度 2022 2021
"三公"经费合计 2022
因公出国（境）费 2022
公务用车购置及运行费 0
公务接待费 0
"""


def test_a_year_is_never_money():
    """2022 = 2022 + 0 + 0 balances perfectly. The year exclusion is what rejects it.

    This is not hypothetical: the run before the exclusion reported 因公出国 at 76% of
    the total with a p90 of exactly 2022.00.
    """
    rows, err = parse(YEAR_COLUMN)
    assert rows is None, rows
    assert err == "no_balancing_row"


def test_a_decimal_in_the_year_range_is_still_money():
    """The exclusion is for BARE integers only — 2022.00万元 is a plausible total."""
    body = ('"三公"经费合计 2022.00 因公出国（境）费 1000.00 '
            '公务用车购置及运行费 1000.00 公务接待费 22.00')
    rows, err = parse(body)
    assert err is None
    assert rows[0]["total"] == 2022.00


def test_scale_bound_rejects_an_implausible_total():
    """0+0+0 and x+0+0 both balance, so the identities alone do not bound scale."""
    big = MAX_WANYUAN * 10
    body = (f'"三公"经费合计 {big}.70 因公出国（境）费 {big}.70 '
            f'公务用车购置及运行费 0.00 公务接待费 0.00')
    rows, err = parse(body)
    assert rows is None
    assert err == "no_balancing_row"


LAYOUT_C = """部门"三公"经费决算表 总计 因公出国（境）费 公务接待费 公务用车购置及运行费
本级 "三公"经费合计 300.00 因公出国（境）费 100.00 公务用车购置及运行费 150.00 公务接待费 50.00
宝安分局 "三公"经费合计 60.00 因公出国（境）费 10.00 公务用车购置及运行费 40.00 公务接待费 10.00
罗湖分局 "三公"经费合计 24.00 因公出国（境）费 4.00 公务用车购置及运行费 16.00 公务接待费 4.00
"""


def test_layout_c_yields_one_row_per_sub_unit():
    """One document, many units — parse() returns a LIST for this reason."""
    rows, err = parse(LAYOUT_C)
    assert err is None
    assert len(rows) == 3
    assert [r["total"] for r in rows] == [300.00, 60.00, 24.00]
    for r in rows:
        assert abs(r["total"] - (r["out"] + r["car"] + r["host"])) <= 0.05


def test_identical_rows_are_deduplicated():
    """A 预算表 and 决算表 printing the same figures is one observation, not two."""
    rows, err = parse(HRSS + "\n" + HRSS)
    assert err is None
    assert len(rows) == 1


def test_an_anchor_far_into_the_body_still_parses():
    """Regression: `mt.end()` is a FULL-BODY offset. Used as a slice index into a
    900-char segment it looks past the end for every anchor beyond ~900, which is why
    the first label-anchored version returned zero rows on a real corpus."""
    rows, err = parse("无关的叙述文字。" * 400 + HRSS)
    assert err is None, err
    assert rows[0]["total"] == 262.00


def test_no_anchor_is_distinguished_from_no_balancing_row():
    assert parse("一份完全无关的通知。") == (None, "no_anchor")
    assert parse("") == (None, "no_anchor")
    assert parse('"三公"经费合计 100.00 因公出国（境）费 1.00 '
                 '公务用车购置及运行费 1.00 公务接待费 1.00')[1] == "no_balancing_row"
