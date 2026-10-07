"""Unit checks for the tracker's per-week site-diversity gate (2026-10-07).

docs/research/policy-tempo.md §3: the pooled weekly cascade bursts in
`tracker_weekly` were single-portal publication batches (Guangzhou 51/83 events in
2023-W01, Shenzhen 57/66 in 2020-W11), all `date_quality='good'`, so a raw burst
can be one site's archive upload rather than policy tempo. The rollup now stores
per (topic, week, level) `n_sites` / `top_site_share` / `top_site`
(scripts/build_tracker_rollup.py: site_diversity) and the service turns them into
a `diverse` flag (web/services/tracker.py: is_diverse, row_diversity) that the
template renders as a "single-source" tag. Counts are never changed by the gate.

Synthetic rows only — no DB. The live check (the two known batch weeks must flag)
is `python3 scripts/build_tracker_rollup.py --dry-run` on the droplet.

Run: python3 -m pytest tests/test_tracker_diversity.py -v
  or: python3 tests/test_tracker_diversity.py
"""
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from build_tracker_rollup import site_diversity  # noqa: E402
from web.services.tracker import (  # noqa: E402
    DIVERSE_MAX_SHARE, DIVERSE_MIN_EVENTS, DIVERSE_MIN_SITES, is_diverse, row_diversity)


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


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
