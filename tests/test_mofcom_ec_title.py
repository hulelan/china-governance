"""The export-control crawler must take its title from the ARTICLE page, not the listing.

The listing endpoint serves some titles with every CJK character replaced by a
literal ASCII "?" (0x3f — NOT U+FFFD, so it is not our own errors="replace"
decoding). 725 stored rows were destroyed that way, at 113-186/yr, while the BODIES
stayed intact because they come from the clean article page. A mojibake title is
invisible to both FTS indexes, can never be a citation target and can never match a
title_reissue edge, so those rows were absent from every title-keyed analysis.

A DELISTED article is the case where falling back to the listing is right: its page
is now just the portal shell and carries no `var title` at all.

Run: python3 -m pytest tests/test_mofcom_ec_title.py -v
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from crawlers.mofcom import _best_ec_title  # noqa: E402

REAL = "商务部新闻发言人就加强两用物项对日本出口管制答记者问"
MOJIBAKE = "?" * len(REAL)


def test_article_title_wins_over_a_mojibake_listing_title():
    assert _best_ec_title({"title": REAL}, MOJIBAKE) == REAL


def test_article_title_wins_even_when_the_listing_is_fine():
    """One source of truth: don't keep two title paths that can disagree."""
    assert _best_ec_title({"title": REAL}, "某个别的标题") == REAL


def test_falls_back_when_the_page_gave_no_title():
    """A DELISTED article returns the portal shell — no var title."""
    assert _best_ec_title({}, MOJIBAKE) == MOJIBAKE
    assert _best_ec_title({"title": ""}, REAL) == REAL


def test_a_mojibake_article_title_is_refused_too():
    assert _best_ec_title({"title": MOJIBAKE}, REAL) == REAL


def test_an_ascii_only_article_title_is_refused():
    """CJK is required: 'CHINA EXPORT CONTROL INFORMATION' is the site's banner."""
    assert _best_ec_title({"title": "CHINA EXPORT CONTROL INFORMATION"}, REAL) == REAL


def test_partial_mojibake_is_refused():
    """ASCII survives the substitution, so '????PVH????' shapes must not pass."""
    assert _best_ec_title({"title": "????????PVH?????????"}, REAL) == REAL


if __name__ == "__main__":
    for fn in list(globals().values()):
        if callable(fn) and getattr(fn, "__name__", "").startswith("test_"):
            fn(); print("ok", fn.__name__)
    print("all mofcom EC title checks passed")
