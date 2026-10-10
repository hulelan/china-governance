"""The deployment/regulation term families underpin a CONTRAST, so overlap would destroy it.

surveillance-deployment.md's finding is that deployment vocabulary sits 57-86% sub-national
while regulation vocabulary sits 6-37%. A term appearing in both families would be counted
on both sides of that comparison, pulling the two distributions toward each other — the
one way this finding can silently weaken.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.rnd.analysis.surveillance_deployment import DEPLOY, LEVELS, REGULATE  # noqa: E402


def test_the_two_families_are_disjoint():
    assert not (set(DEPLOY) & set(REGULATE))


def test_neither_family_has_duplicates():
    for fam in (DEPLOY, REGULATE):
        assert len(set(fam)) == len(fam)
        assert fam


def test_media_is_its_own_level_and_not_folded_into_sub_national():
    """CLAUDE.md: `media` is an admin_level, so "non-central" is NOT "sub-national".
    Folding it in would read Xinhua coverage as local deployment — and 生成式人工智能
    is 48% media, so the error would be large exactly where it matters."""
    assert LEVELS["media"] == ("media",)
    assert "media" not in LEVELS["sub-national gov"]
    assert "central" not in LEVELS["sub-national gov"]


def test_the_sub_national_group_covers_every_non_central_government_level():
    assert set(LEVELS["sub-national gov"]) == {
        "provincial", "municipal", "district", "department"}
