"""Titles that can never be a resolution target (docs/working/qa-resolver-deferred-patterns.md).

Distinct from the org-only gate, which bars only containment. For these, an exact
match is equally wrong, because the same title names many DIFFERENT documents --
`政府工作报告` is 25 documents with 25 distinct instrument_ids and 283 citers
landing on whichever copy sorted first. Leaving the edge unresolved is more honest
than crediting it arbitrarily, which is the trade the org gate already makes.
"""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "rnd" / "citations"))

import extract_citations as E  # noqa: E402


class Predicate(unittest.TestCase):
    def test_instance_document_endings_are_refused(self):
        for t in ("房屋征收补偿决定书",
                  "中山市人民政府国有土地上房屋征收决定书",
                  "深圳市人才园（监理）中标通知书",
                  "安全生产事故高风险区域整治挂牌督办通知书",
                  "行政处罚告知书"):
            self.assertTrue(E._is_unresolvable_instance_title(t), t)

    def test_bare_generic_title_is_refused(self):
        self.assertTrue(E._is_unresolvable_instance_title("政府工作报告"))

    def test_real_instruments_are_kept(self):
        """The endings must not catch an instrument. Chinese instruments end 意见,
        决定, 通知 -- never 意见书 / 决定书 / 通知书 -- so the `书` is load-bearing
        and these must all survive."""
        for t in ("国务院关于投资体制改革的决定",
                  "中华人民共和国行政处罚法",
                  "关于印发全面推进依法行政实施纲要的通知",
                  "国务院关于加强法治政府建设的意见",
                  "深圳市政府工作报告",          # jurisdiction-qualified: resolvable
                  "政府工作报告重点工作分工方案",  # a different document
                  "中华人民共和国民法典"):
            self.assertFalse(E._is_unresolvable_instance_title(t), t)

    def test_empty_and_none_are_safe(self):
        self.assertFalse(E._is_unresolvable_instance_title(""))
        self.assertFalse(E._is_unresolvable_instance_title(None))

    def test_unmeasured_endings_are_deliberately_excluded(self):
        """裁决书 / 意见书 / 证明书 are the same shape but hold ZERO titles in the
        corpus, so they were left out rather than added on reasoning alone. If a
        measurement later calls for them this test is the place to change."""
        for t in ("劳动争议仲裁裁决书", "法律意见书", "收入证明书"):
            self.assertFalse(E._is_unresolvable_instance_title(t), t)


class MatcherIntegration(unittest.TestCase):
    """The drop must happen before ANY tier is built, so the title is unreachable
    by exact match, by title-core and by containment alike."""

    # TitleMatcher takes (title, (doc_id, site_key, algo_doc_type)) pairs —
    # the shape its caller builds at extract_citations.py:731.
    ROWS = [
        ("政府工作报告",                 (1, "sz", "report")),
        ("政府工作报告",                 (2, "gd", "report")),
        ("房屋征收补偿决定书",           (3, "zhongshan", "other")),
        ("中华人民共和国行政处罚法",     (4, "npc", "regulation")),
    ]

    def _matcher(self, drop):
        return E.TitleMatcher(list(self.ROWS), None,
                              org_only_exact=True, drop_instance_titles=drop)

    def test_denylisted_titles_are_absent_from_every_tier(self):
        m = self._matcher(True)
        joined = " ".join(m.exact.keys()) + " " + " ".join(m.core.keys())
        self.assertNotIn("政府工作报告", joined)
        self.assertNotIn("房屋征收补偿决定书", joined)
        self.assertNotIn("政府工作报告", " ".join(m.titles))

    def test_a_real_instrument_still_resolves(self):
        m = self._matcher(True)
        got = m.resolve_ref("中华人民共和国行政处罚法", min_len=5)
        self.assertTrue(got, "the denylist must not disturb normal resolution")

    def test_the_flag_defaults_off_for_compatibility(self):
        """Older callers (tests, one-off analyses) keep today's behaviour."""
        m = self._matcher(False)
        joined = " ".join(m.exact.keys())
        self.assertIn("政府工作报告", joined)


if __name__ == "__main__":
    unittest.main(verbosity=2)
