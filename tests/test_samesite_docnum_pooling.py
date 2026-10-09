"""One instrument held twice on ONE site must pool when it shares a numbered 文号.

`assign_instruments` requires a sub-pool to span two distinct SITES before pooling,
which is a heuristic for "are these really one text". But that rule runs AFTER
`split_by_docnum`, so by then the members already share an explicit 文号 where one
exists — direct evidence, strictly stronger than the heuristic standing in for it.

Without the override, mofcom's main site and its export-control subdomain (one
`site_key`) held 商务部公告2026年第11号 twice as two `unique` rows, and an entity count
summed over rows read 454 where the deduplicated truth was 338.

The override MUST stay narrow. Measured 2026-10-09 before shipping:
  * 457 same-site groups / 935 documents share a NUMBERED 文号      -> pool
  * 36 groups / 73 documents share a bare TYPE marker              -> keep guarded
      (the literal string 无, 18 groups; 韶府便笺, 5 groups — three different
       试鸣防空警报的通告 on three dates)
  * 7,921 groups / 19,159 documents carry no 文号 at all            -> keep guarded
      (深圳市交通运输局行政处罚听证公告 x89, 深圳天气趋势 x31 — recurring notices with
       identical titles that are genuinely DIFFERENT documents)

Run: python3 -m pytest tests/test_samesite_docnum_pooling.py -v
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from build_doc_identity import shares_numbered_docnum  # noqa: E402


def part(*docnums, site="mofcom"):
    return [{"docnum": d, "site": site, "id": i} for i, d in enumerate(docnums, 1)]


def test_same_numbered_docnum_pools():
    assert shares_numbered_docnum(part("商务部公告2026年第11号", "商务部公告2026年第11号"))
    assert shares_numbered_docnum(part("中府〔2007〕55号", "中府〔2007〕55号", "中府〔2007〕55号"))
    assert shares_numbered_docnum(part("工信厅科函〔2026〕125号", "工信厅科函〔2026〕125号"))


def test_full_width_brackets_count():
    """江府办［2009］97号 is a real number; a half-width-only pattern missed 7 groups."""
    assert shares_numbered_docnum(part("江府办［2009］97号", "江府办［2009］97号"))


def test_ministerial_order_without_a_year_counts():
    assert shares_numbered_docnum(part("人力资源和社会保障部令第9号", "人力资源和社会保障部令第9号"))


def test_a_bare_type_marker_does_NOT_pool():
    """韶府便笺 marks a document TYPE, and three 试鸣防空警报的通告 share it."""
    assert not shares_numbered_docnum(part("韶府便笺", "韶府便笺", "韶府便笺"))


def test_the_literal_placeholder_none_does_NOT_pool():
    """Some crawler stores 无 ('none') as the document number — 18 groups."""
    assert not shares_numbered_docnum(part("无", "无"))


def test_no_docnum_does_NOT_pool():
    """Protects 19,159 documents: recurring notices with identical titles."""
    assert not shares_numbered_docnum(part("", ""))
    assert not shares_numbered_docnum(part(None, None))


def test_differing_docnums_do_NOT_pool():
    assert not shares_numbered_docnum(
        part("商务部公告2026年第11号", "商务部公告2026年第12号"))


def test_a_mixed_part_does_NOT_pool():
    """One member numbered and one blank is not evidence of a single instrument."""
    assert not shares_numbered_docnum(part("商务部公告2026年第11号", ""))


def test_a_single_member_part_is_not_special_cased_here():
    """The caller already requires len(part) >= 2; this helper only answers the
    identifier question, so a one-member part trivially 'shares' its own number and
    must not be relied on as a pooling decision."""
    assert shares_numbered_docnum(part("商务部公告2026年第11号")) is True


if __name__ == "__main__":
    for fn in list(globals().values()):
        if callable(fn) and getattr(fn, "__name__", "").startswith("test_"):
            fn(); print("ok", fn.__name__)
    print("all same-site docnum pooling checks passed")
