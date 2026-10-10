"""Invariants of the w35562 term families.

The memo's claim is a RATIO between two families, so an overlap between them would
inflate both sides silently and a term appearing in CREDIT and FISCAL at once would
destroy the §3 gradient. These are data, not logic, which is exactly why they need a
guard: a future edit adding 消费品以旧换新 to PRODUCTION would change a published
number with nothing to object.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.rnd.analysis.mandarin_capitalism import CREDIT, DEMAND, PRODUCTION  # noqa: E402


def test_the_two_purpose_families_are_disjoint():
    assert not (set(PRODUCTION) & set(DEMAND))


def test_no_purpose_term_is_also_a_credit_term():
    assert not (set(CREDIT) & (set(PRODUCTION) | set(DEMAND)))


def test_families_are_non_empty_and_have_no_duplicates():
    for fam in (CREDIT, PRODUCTION, DEMAND):
        assert fam
        assert len(set(fam)) == len(fam)


def test_equipment_renewal_is_classed_as_production_on_purpose():
    """设备更新 is the production half of 大规模设备更新和消费品以旧换新, and the memo's
    §4 qualification depends on it being counted that way. If a future edit moves it,
    that qualification has to be rewritten."""
    assert "设备更新" in PRODUCTION
    assert "以旧换新" in DEMAND
