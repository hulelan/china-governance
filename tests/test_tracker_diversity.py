"""Unit checks for the tracker's per-week site-diversity and anchor-concentration
gates (2026-10-07).

docs/research/policy-tempo.md §3: the pooled weekly cascade bursts in
`tracker_weekly` were single-portal publication batches (Guangzhou 51/83 events in
2023-W01, Shenzhen 57/66 in 2020-W11), all `date_quality='good'`, so a raw burst
can be one site's archive upload rather than policy tempo. The rollup now stores
per (topic, week, level) `n_sites` / `top_site_share` / `top_site`
(scripts/build_tracker_rollup.py: site_diversity) and the service turns them into
a `diverse` flag (web/services/tracker.py: is_diverse, row_diversity) that the
template renders as a "single-source" tag. Counts are never changed by the gate.

The complementary gate: 2026-W33 passes the site gate (75 events, 26 sites) but is
one INSTRUMENT, 生态环境法典, echoed 25 times. The rollup stores `n_anchors` /
`top_anchor_share` / `top_anchor` (anchor_diversity, anchors pooled by
doc_identity.instrument_id) and the service flags `single_instrument`
(is_single_instrument, row_instrument) — rendered as a "single-instrument" tag.

Synthetic rows only — no DB. The live check (the two known batch weeks must flag
single-source, 2026-W33 must flag single-instrument) is
`python3 scripts/build_tracker_rollup.py --dry-run` on the droplet.

Run: python3 -m pytest tests/test_tracker_diversity.py -v
  or: python3 tests/test_tracker_diversity.py
"""
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from build_tracker_rollup import anchor_diversity, site_diversity  # noqa: E402
from web.services.tracker import (  # noqa: E402
    DIVERSE_MAX_SHARE, DIVERSE_MIN_EVENTS, DIVERSE_MIN_SITES, is_diverse, row_diversity,
    SINGLE_INSTR_MIN_EVENTS, SINGLE_INSTR_MIN_SHARE, SINGLE_INSTR_MIN_TOP,
    is_single_instrument, row_instrument)


def test_site_diversity_counts_sites_and_modal_share():
    assert site_diversity(None) == (0, 0.0, "")
    assert site_diversity(Counter()) == (0, 0.0, "")
    assert site_diversity(Counter({"gz": 51, "gd": 7, "shantou": 3})) == (3, round(51 / 61, 4), "gz")
    # tie on count -> deterministic (highest key wins)
    assert site_diversity(Counter({"a": 2, "b": 2})) == (2, 0.5, "b")


def test_gate_thresholds_are_the_documented_ones():
    assert (DIVERSE_MIN_EVENTS, DIVERSE_MIN_SITES, DIVERSE_MAX_SHARE) == (3, 3, 0.5)


def test_is_diverse_none_below_burst_floor():
    # too few events to judge: not a burst, so neither diverse nor single-source
    assert is_diverse(0, 0, 0.0) is None
    assert is_diverse(2, 1, 1.0) is None
    assert is_diverse(None, 0, 0.0) is None


def test_is_diverse_known_batches_flag_and_ordinary_weeks_pass():
    # the two memo weeks (pooled 'all', 2026-10-07 numbers)
    assert is_diverse(83, 18, 0.6145) is False   # Guangzhou 51/83, 2023-W01
    assert is_diverse(66, 7, 0.8636) is False    # Shenzhen 57/66, 2020-W11
    # ordinary multi-portal weeks
    assert is_diverse(75, 26, 0.20) is True      # 2026-W33 — one-anchor, not one-site
    assert is_diverse(56, 8, 0.48) is True
    # boundaries: a majority rule (<= 0.5 passes), n_sites >= 3
    assert is_diverse(4, 3, 0.5) is True
    assert is_diverse(4, 3, 0.51) is False
    assert is_diverse(4, 2, 0.5) is False        # two-portal 50/50 is still two portals
    assert is_diverse(3, 3, 0.3334) is True


def _cell(cas, n_sites, share, top):
    return {"cas": cas, "n_sites": n_sites, "top_site_share": share, "top_site": top}


def test_row_diversity_merges_levels_by_modal_site_key():
    # Guangzhou-like week: provincial cell diverse, municipal cell a gz batch.
    cells = [_cell(20, 10, 0.35, "gd"), _cell(62, 7, 0.8226, "gz"), _cell(1, 1, 1.0, "szns")]
    r = row_diversity(cells)
    assert r["n_sites"] == 18
    assert r["top_site"] == "gz"
    assert r["top_site_share"] == round(51 / 83, 4)
    assert r["diverse"] is False


def test_row_diversity_sums_same_site_across_levels():
    # the same portal is modal at two levels: its counts add up before the share
    cells = [_cell(4, 2, 0.75, "sz"), _cell(4, 2, 0.75, "sz")]
    r = row_diversity(cells)
    assert r["n_sites"] == 4 and r["top_site"] == "sz" and r["top_site_share"] == 0.75
    assert r["diverse"] is False


def test_row_diversity_empty_and_small_rows():
    assert row_diversity([]) == {"n_sites": 0, "top_site_share": 0.0, "top_site": "", "diverse": None}
    r = row_diversity([_cell(0, 0, 0.0, ""), _cell(2, 2, 0.5, "a")])
    assert r["diverse"] is None and r["n_sites"] == 2


# ---------------------------------------------------------------- anchor gate

def test_anchor_diversity_counts_instruments_and_modal_share():
    assert anchor_diversity(None) == (0, 0.0, 0)
    assert anchor_diversity(Counter()) == (0, 0.0, 0)
    # 2026-W33 shape: 生态环境法典 25 of 75 over 38 instruments
    c = Counter({12728107: 25, **{900000000 + i: 1 for i in range(37)}})
    c[900000000] += 13  # 75 events total
    assert anchor_diversity(c) == (38, round(25 / 75, 4), 12728107)
    # tie on count -> deterministic (highest id wins)
    assert anchor_diversity(Counter({5: 2, 9: 2})) == (2, 0.5, 9)


def test_instrument_gate_thresholds_are_the_documented_ones():
    assert (SINGLE_INSTR_MIN_EVENTS, SINGLE_INSTR_MIN_SHARE, SINGLE_INSTR_MIN_TOP) == (3, 0.3, 3)
    assert SINGLE_INSTR_MIN_EVENTS == DIVERSE_MIN_EVENTS  # same burst floor as the site gate


def test_is_single_instrument_none_below_burst_floor():
    assert is_single_instrument(0, 0, 0.0) is None
    assert is_single_instrument(2, 1, 1.0) is None
    assert is_single_instrument(None, 0, 0.0) is None


def test_is_single_instrument_known_weeks():
    # 2026-W33 (pooled 'all', 2026-10-07): 25/75 from 38 instruments -> flagged
    assert is_single_instrument(75, 38, 0.3333) is True
    # the two single-PORTAL weeks are NOT one instrument (77 and 48 instruments)
    assert is_single_instrument(83, 77, 0.0361) is False   # Guangzhou 2023-W01
    assert is_single_instrument(66, 48, 0.1212) is False   # Shenzhen 2020-W11
    # 2025-W31: 7/23 = 0.304, just over the cut -> flagged; 2019-W38: 3/10 = 0.30 -> not
    assert is_single_instrument(23, 16, 0.3043) is True
    assert is_single_instrument(10, 8, 0.3) is False
    # the floor: 3 events from 3 anchors is 0.333 but uniform — 1 event on the modal
    assert is_single_instrument(3, 3, 0.3333) is False
    assert is_single_instrument(6, 5, 0.3333) is False     # 2 on the modal
    assert is_single_instrument(5, 3, 0.6) is True         # 3 on the modal (2020-W41)
    assert is_single_instrument(9, 7, 0.3333) is True      # 3 of 9


def test_gates_are_independent():
    # a week can carry both tags, either, or neither
    assert is_diverse(66, 7, 0.8636) is False and is_single_instrument(66, 48, 0.12) is False
    assert is_diverse(75, 26, 0.20) is True and is_single_instrument(75, 38, 0.3333) is True


def _acell(cas, n_anchors, share, top):
    return {"cas": cas, "n_anchors": n_anchors, "top_anchor_share": share, "top_anchor": top}


def test_row_instrument_merges_levels_by_instrument_id():
    # W33-like: the same law is modal at the provincial and the municipal level
    cells = [_acell(30, 14, 0.5, 12728107), _acell(45, 26, 0.2222, 12728107)]
    r = row_instrument(cells)
    assert r["top_anchor"] == 12728107
    assert r["top_anchor_n"] == 25
    assert r["top_anchor_share"] == round(25 / 75, 4)
    assert r["n_anchors"] == 40  # summed: an upper bound, display only
    assert r["single_instrument"] is True


def test_row_instrument_different_modal_per_level_is_lenient_not_wrong():
    # different modal instruments per level: neither reaches the cut pooled
    cells = [_acell(10, 6, 0.4, 1), _acell(10, 6, 0.4, 2)]
    r = row_instrument(cells)
    assert r["top_anchor"] == 2 and r["top_anchor_n"] == 4 and r["top_anchor_share"] == 0.2
    assert r["single_instrument"] is False


def test_row_instrument_empty_and_small_rows():
    assert row_instrument([]) == {"n_anchors": 0, "top_anchor_share": 0.0, "top_anchor": 0,
                                  "top_anchor_n": 0, "single_instrument": None}
    r = row_instrument([_acell(0, 0, 0.0, 0), _acell(2, 1, 1.0, 7)])
    assert r["single_instrument"] is None and r["top_anchor"] == 7


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
