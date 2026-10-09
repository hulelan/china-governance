"""An explicit --max-pages must override the per-section page cap.

The cap guards the NIGHTLY — the module comment says "40 pages keeps the nightly on
current material" — not deliberate operator intent, and CLAUDE.md documents the
historical backfill as "a deliberate `--max-pages 411` run". But the original
`min(max_pages, cap)` made the cap win unconditionally, so that documented command
silently did the ordinary 40-page walk: measured 2026-10-09, a --max-pages 411 run
listed 494 沟通交流 documents where 411 pages is ~8,200. It was accepted, ran, and
exited 0 — the same shape as a --hops value matching no hop and also exiting 0.

Run: python3 -m pytest tests/test_pbc_section_cap.py -v
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from crawlers.pbc import DEFAULT_MAX_PAGES, SECTIONS, section_pages  # noqa: E402

CAP = 40          # the 沟通交流 cap
UNCAPPED = None   # the two 条法司 sections walk whole


def test_default_path_keeps_the_cap():
    """Nightly behaviour must not change: the cap still bounds the walk."""
    assert section_pages(CAP, DEFAULT_MAX_PAGES, cap_applies=True) == min(DEFAULT_MAX_PAGES, CAP)
    assert section_pages(CAP, 411, cap_applies=True) == CAP


def test_explicit_max_pages_overrides_the_cap():
    """The documented backfill: --max-pages 411 must actually walk 411."""
    assert section_pages(CAP, 411, cap_applies=False) == 411


def test_an_uncapped_section_always_takes_max_pages():
    for applies in (True, False):
        assert section_pages(UNCAPPED, 411, cap_applies=applies) == 411
        assert section_pages(UNCAPPED, 7, cap_applies=applies) == 7


def test_an_explicit_value_below_the_cap_is_still_respected():
    """Overriding the cap must not silently RAISE a deliberately small request."""
    assert section_pages(CAP, 3, cap_applies=False) == 3
    assert section_pages(CAP, 3, cap_applies=True) == 3


def test_the_sections_table_still_has_exactly_one_capped_section():
    """If a second cap appears, the backfill story in CLAUDE.md needs revisiting."""
    capped = [(path, label, cap) for path, label, cap in SECTIONS if cap]
    assert len(capped) == 1, capped
    path, label, cap = capped[0]
    assert path.startswith("goutongjiaoliu"), path
    assert cap == 40, cap


if __name__ == "__main__":
    for fn in list(globals().values()):
        if callable(fn) and getattr(fn, "__name__", "").startswith("test_"):
            fn(); print("ok", fn.__name__)
    print("all pbc section-cap checks passed")
