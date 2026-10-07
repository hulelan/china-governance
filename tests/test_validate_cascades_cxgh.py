"""The 城乡规划法 validator check must measure what it says (2026-10-07).

docs/working/qa-cxgh-citer-drop.md §4.1: the single check was named `cxgh_inbound` and
printed "inbound citations" while its SQL counted `COUNT(*)` = EDGE ROWS, whereas
`doc_inbound.inbound` is `COUNT(DISTINCT source_id)` with self-cites dropped. One word
for two metrics turned a healthy +16 edges into a reported 235-citer drop. The check is
now two checks with two bands, so the duplicate-edge overhang between them is monitored
instead of invisible.

Run: python3 -m pytest tests/test_validate_cascades_cxgh.py -v
  or: python3 tests/test_validate_cascades_cxgh.py   (assert-based, no pytest needed)
"""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import validate_cascades as vc  # noqa: E402

TARGET = 4242


def _fixture(citers=1907, dupes=251, self_cites=3):
    """Synthetic `citations` with a known (edges, distinct-citer) split: `dupes` of the
    citers carry a second edge under a different target_ref, plus `self_cites` self-
    citation rows (which count as edges but must NOT count as citers)."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE citations (source_id INT, target_ref TEXT, target_id INT,"
                 " citation_type TEXT)")
    rows = [(10_000 + i, "中华人民共和国城乡规划法", TARGET, "named") for i in range(citers)]
    rows += [(10_000 + i, "《中华人民共和国城乡规划法》", TARGET, "llm") for i in range(dupes)]
    rows += [(TARGET, "中华人民共和国城乡规划法", TARGET, "named")] * self_cites
    conn.executemany("INSERT INTO citations VALUES (?,?,?,?)", rows)
    # noise on another target must not be counted
    conn.execute("INSERT INTO citations VALUES (1, '其他', 99, 'named')")
    return conn


def _run(conn):
    vc.CXGH_ID = TARGET
    r = vc.Result()
    vc.check_cxgh_citations(conn, r)
    return {line.split()[1].rstrip(":"): line for line in r.lines}, r


def _defaults():
    vc.CXGH_EDGES_MIN, vc.CXGH_EDGES_MAX = 1900, 2400
    vc.CXGH_CITERS_MIN, vc.CXGH_CITERS_MAX = 1680, 2140


def test_both_checks_exist_and_pass_on_a_healthy_fixture():
    _defaults()
    lines, r = _run(_fixture())          # 2161 edges (incl. 3 self), 1907 distinct citers
    assert set(lines) == {"cxgh_edges", "cxgh_citers"}, lines
    assert not r.failed, r.lines
    assert "2161 citation EDGE rows" in lines["cxgh_edges"]
    assert "1907 DISTINCT citing documents" in lines["cxgh_citers"]


def test_the_two_metrics_are_not_the_same_number():
    """The whole point: edges > citers by exactly the duplicate overhang."""
    _defaults()
    lines, _ = _run(_fixture(citers=1907, dupes=251, self_cites=0))
    assert "2158 citation EDGE rows" in lines["cxgh_edges"]
    assert "251 duplicate-edge overhang" in lines["cxgh_edges"]
    assert "1907 DISTINCT citing documents" in lines["cxgh_citers"]


def test_self_cites_count_as_edges_but_not_as_citers():
    _defaults()
    lines, _ = _run(_fixture(citers=100, dupes=0, self_cites=5))
    assert "105 citation EDGE rows" in lines["cxgh_edges"]
    assert "100 DISTINCT citing documents" in lines["cxgh_citers"]


def test_edges_out_of_band_fails_only_the_edges_check():
    """A matcher that steals edges (proxy-target bug) but keeps the citer set."""
    _defaults()
    _, r = _run(_fixture(citers=1850, dupes=0))     # 1850 edges < 1900, citers in band
    assert r.failed == ["cxgh_edges"], r.lines


def test_citers_out_of_band_fails_only_the_citers_check():
    """The blind spot the old single check had: edges fine, citer set collapsed into a
    few documents citing the law many times over."""
    _defaults()
    _, r = _run(_fixture(citers=1000, dupes=1000))  # 2000 edges in band, 1000 citers not
    assert r.failed == ["cxgh_citers"], r.lines


def test_set_override_works_for_both_new_thresholds():
    _defaults()
    for name in ("CXGH_EDGES_MIN", "CXGH_EDGES_MAX", "CXGH_CITERS_MIN", "CXGH_CITERS_MAX"):
        vc.apply_overrides([f"{name}=1234"])
        assert getattr(vc, name) == 1234 and isinstance(getattr(vc, name), int)
    _defaults()
    # and an override actually bites
    vc.apply_overrides(["CXGH_CITERS_MAX=1000"])
    _, r = _run(_fixture())
    assert r.failed == ["cxgh_citers"], r.lines
    _defaults()


def test_existing_bands_are_not_loosened():
    _defaults()
    assert (vc.CXGH_EDGES_MIN, vc.CXGH_EDGES_MAX) == (1900, 2400)
    assert vc.CXGH_CITERS_MIN <= 1907 <= vc.CXGH_CITERS_MAX
    assert vc.check_cxgh_citations in vc.CHECKS
    assert not hasattr(vc, "check_cxgh_inbound")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL OK")
