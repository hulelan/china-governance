"""The fixed-site panel and its sign-flip verdict.

`rmb-coverage.md` §4 trap 3: this corpus grows by ACQUISITION as well as by
publication, so a raw count series partly measures our crawl schedule. There the
美元:人民币 ratio HALVED on a fixed panel while RISING uncontrolled — a reversal of
sign, not a magnitude error. Six memos state the requirement, two hand-rolled it,
and one-vote-veto.md shipped without one and says so in its limitations.

What is pinned here:
  * panel membership is ">= min in EVERY complete year", and the trailing partial
    year never gates membership (a mid-year crawl is not a publication drought)
  * classify() orders `thin` ABOVE `sign_flip` — with too few documents, calling
    the raw series "contradicted" would be an overclaim about noise
  * _spearman averages ties, or a FLAT series reads as a trend

Run: python3 -m pytest tests/test_panel.py -v
"""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "rnd" / "analysis"))

from panel import (MIN_SERIES_DOCS, RHO_FLOOR, build_panel,  # noqa: E402
                   classify, _spearman)

# Unix timestamps for 1 July of each year, so strftime('%Y') is unambiguous.
JULY = {2013: 1372636800, 2014: 1404259200, 2015: 1435726800, 2016: 1467345600,
        2017: 1498881600, 2018: 1530432000, 2019: 1561968000, 2020: 1593561600,
        2021: 1625097600, 2022: 1656633600, 2023: 1688169600, 2024: 1719792000,
        2025: 1751328000, 2026: 1782864000}


def _db(rows):
    """rows = [(site_key, year, n_docs)] -> an in-memory documents table."""
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE documents (id INTEGER PRIMARY KEY, site_key TEXT, "
              "date_written INTEGER, body_text_cn TEXT)")
    i = 0
    for sk, yr, n in rows:
        for _ in range(n):
            i += 1
            c.execute("INSERT INTO documents VALUES (?,?,?,?)", (i, sk, JULY[yr], "body"))
    c.commit()
    return c


def test_a_site_missing_one_year_is_excluded():
    """The whole point: membership requires EVERY complete year, not an average."""
    rows = [("steady", y, 40) for y in range(2013, 2026)]
    rows += [("gappy", y, 40) for y in range(2013, 2026) if y != 2019]   # one hole
    p = build_panel(_db(rows + [("steady", 2026, 5), ("gappy", 2026, 5)]),
                    min_per_year=30, first_year=2013)
    assert p.sites == frozenset({"steady"}), p.sites
    assert p.n_candidate_sites == 2


def test_the_trailing_partial_year_does_not_gate_membership():
    """A site crawled mid-2026 must not be dropped for a short final year."""
    rows = [("s", y, 40) for y in range(2013, 2026)] + [("s", 2026, 2)]
    p = build_panel(_db(rows), min_per_year=30, first_year=2013)
    assert p.sites == frozenset({"s"})
    assert p.partial == (2026,)
    assert 2026 not in p.years
    assert p.denom[2026] == 2, "the partial year is still reported"


def test_denominator_counts_only_panel_sites():
    rows = [("in", y, 40) for y in range(2013, 2027)]
    rows += [("out", y, 1000) for y in (2025, 2026)]       # a late, huge arrival
    p = build_panel(_db(rows), min_per_year=30, first_year=2013)
    assert p.sites == frozenset({"in"})
    assert p.denom[2025] == 40, "a non-panel site must not inflate the denominator"


def test_thin_wins_over_sign_flip():
    """With too few docs both rhos are unreliable; 'contradicted' would overclaim."""
    assert classify(MIN_SERIES_DOCS - 1, +0.9, -0.9) == "thin"
    assert classify(MIN_SERIES_DOCS, +0.9, -0.9) == "sign_flip"


def test_sign_flip_needs_both_rhos_past_the_floor():
    assert classify(500, +0.9, -0.9) == "sign_flip"
    assert classify(500, +0.9, -RHO_FLOOR / 2) == "ok", "weak opposite rho is noise"
    assert classify(500, +RHO_FLOOR / 2, -0.9) == "ok"
    assert classify(500, +0.9, +0.9) == "ok", "agreeing signs are never a flip"


def test_spearman_averages_ties_so_a_flat_series_is_not_a_trend():
    assert _spearman([(1, 5), (2, 5), (3, 5), (4, 5)]) == 0.0, "exact: dx==0 short-circuits"
    assert abs(_spearman([(1, 1), (2, 2), (3, 3)]) - 1.0) < 1e-9
    assert abs(_spearman([(1, 3), (2, 2), (3, 1)]) + 1.0) < 1e-9


def test_spearman_refuses_to_trend_fewer_than_three_points():
    assert _spearman([(1, 1), (2, 99)]) == 0.0


def test_the_rmb_shape_is_classified_as_a_sign_flip():
    """Ground truth from rmb-coverage.md: raw rises, panel share halves.

    The live figures (2026-10-09, 18-site panel) are raw rho +0.555 and
    panel-share rho -0.923 on 400 panel documents.
    """
    assert classify(400, +0.555, -0.923) == "sign_flip"


def test_the_export_control_shape_is_classified_ok():
    """Also ground truth: central panel, both rhos positive, 502 panel documents."""
    assert classify(502, +0.952, +0.738) == "ok"


if __name__ == "__main__":
    for fn in list(globals().values()):
        if callable(fn) and getattr(fn, "__name__", "").startswith("test_"):
            fn(); print("ok", fn.__name__)
    print("all panel checks passed")
