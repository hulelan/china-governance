"""The org-only gate must not be defeated by an agency name that ENDS in a
headline morpheme (2026-10-09).

`_ORG_ONLY_NOT`'s event/headline clause carried `(?:格|新|大|布|开|全)局$`, written for
开创新局 / 于变局中开新局. But 科技创新·局 (a Science, Technology and Innovation Bureau)
splits after 创新, so 科技创新局 matched the headline pattern, was exempted from the
org-only gate, and stayed a CONTAINMENT candidate. 深圳市科技创新局 — a bodiless stub —
therefore absorbed 7 edges whose refs were real unheld instruments merely PREFIXED by
the bureau's name.

The gate is measured, not reasoned: of all 12 corpus titles ending in 创新局, the 8
ending in 科技创新局 are agencies and the 4 ending in 创新局 otherwise are headlines.

Run: python3 -m pytest tests/test_org_name_bureau_gate.py -v
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "rnd" / "citations"))

from extract_citations import TitleMatcher, _is_org_only_title, _norm_title  # noqa: E402

# Every corpus title ending in 科技创新局 (8 rows, 4 distinct shapes) — all agencies.
BUREAUS = ["深圳市科技创新局", "市科技创新局", "区科技创新局", "科技创新局"]

# Every corpus title ending in 创新局 but NOT 科技创新局 (4) — all genuine headlines.
HEADLINES = ["牢记嘱托担使命 感恩奋进创新局", "扎根龙华投资热土，创新驱动再创新局",
             "惠州五大引擎发力推动环南昆山—罗浮山引领区农文旅体融合创新局",
             "推动江门“百千万工程”加力提速、开创新局"]

# The headline forms the clause exists for, which must keep matching.
OTHER_HEADLINES = ["于变局中开新局", "太空算力加快布局", "坚持系统观念构建新发展格局",
                   "一季度经济实现平稳开局", "以高质量审计服务全市改革发展大局"]


def test_science_tech_innovation_bureaus_are_org_only():
    """The 8 bureau titles must be org-only, so containment cannot target them."""
    for t in BUREAUS:
        assert _is_org_only_title(_norm_title(t)) is True, t


def test_create_new_chapter_headlines_are_not_org_only():
    """A bare (?<!创) would break these four — they must stay NON-org-only."""
    for t in HEADLINES:
        assert _is_org_only_title(_norm_title(t)) is False, t


def test_the_headline_clause_still_fires_for_what_it_was_written_for():
    for t in OTHER_HEADLINES:
        assert _is_org_only_title(_norm_title(t)) is False, t


def test_bureau_stub_does_not_absorb_a_prefixed_instrument_ref():
    """The live defect: 7 refs that merely BEGIN with the bureau name.

    With the bureau org-only, containment is barred and the ref stays honestly
    unresolved (a crawl-queue entry) rather than crediting a bodiless stub.
    """
    STUB, OTHER = 1351876, 999
    titles = {"深圳市科技创新局": (STUB, "municipal"),
              "深圳市人民政府办公厅关于印发某方案的通知": (OTHER, "municipal")}
    # org_only_exact=True is what the production call site passes; without it
    # self.org_only is empty and the gate is inert.
    m = TitleMatcher({_norm_title(k): v for k, v in titles.items()}, org_only_exact=True)
    assert _norm_title("深圳市科技创新局") in m.org_only, "bureau missing from org_only set"
    ref = "深圳市科技创新局2025年度深圳市重点实验室组建资助项目申请指南"
    got = m.resolve_ref(ref)
    hit = got[0] if isinstance(got, tuple) else got
    assert hit != STUB, f"bureau stub absorbed a prefixed instrument ref: {got!r}"


if __name__ == "__main__":
    for fn in list(globals().values()):
        if callable(fn) and getattr(fn, "__name__", "").startswith("test_"):
            fn(); print("ok", fn.__name__)
    print("all org-name bureau gate checks passed")
