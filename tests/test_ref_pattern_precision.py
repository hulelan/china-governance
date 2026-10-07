"""Precision of the named-《》 reference pattern (2026-10-07).

docs/working/qa-ref-pattern-precision.md. The old pattern `《([^》]{8,100})》`
excluded only the CLOSING bracket, so a body holding an UNCLOSED 《 produced a
capture that ran through ordinary prose until the close bracket of a LATER title —
a run of body text presented as a reference name. Measured live case (doc 3414348,
江门市人民政府 批复): the capture resolved onto the 9-character masthead document
《江门市自然资源局》 instead of the law the sentence actually cites.

Rules under test:
  * a capture may contain ONE nested 《…》 (a title quoting a title) but may never
    cross an unclosed 《;
  * a prose capture (full stop / PDF table) is not a reference;
  * the head of a run whose closing 》 the body really dropped is still recovered,
    cut back to its last genre word;
  * a genuinely long instrument title is still accepted;
  * 根据《X》 still yields X.

Run: python3 -m pytest tests/test_ref_pattern_precision.py -v
  or: python3 tests/test_ref_pattern_precision.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "rnd" / "citations"))

from analyze import (  # noqa: E402
    NAMED_REF_PATTERN, is_policy_document, looks_like_body_run, recover_named_heads,
)
from extract_citations import named_ref_candidates  # noqa: E402

# The live 江门 case (citations.target_ref of doc 3414348 before the fix). The body
# opens a 《 for the 请示 title, never closes it, and the next 》 belongs to the law.
JIANGMEN_BODY = (
    "《江门市自然资源局关于报请批准江门高新区JH03-R地段控制性详细规划修改的请示"
    "（江自然资〔2025〕744号）收悉。经研究，现批复如下： 一、该规划成果符合"
    "《中华人民共和国城乡规划法》等法律法规的规定。"
)
JIANGMEN_JUNK_REF = (
    "江门市自然资源局关于报请批准江门高新区JH03-R地段控制性详细规划修改的请示"
    "（江自然资〔2025〕744号）收悉。经研究，现批复如下： 一、该规划成果符合"
    "《中华人民共和国城乡规划法"
)
# A real instrument title of 39 characters, cited 287× in the live corpus.
LONG_REAL_TITLE = "广东省自然资源厅印发关于加强和改进控制性详细规划管理若干指导意见（暂行）的通知"


def test_jiangmen_prose_run_is_not_a_reference():
    """The body-text run must not be captured at all; the law it quotes must be."""
    caps = NAMED_REF_PATTERN.findall(JIANGMEN_BODY)
    assert JIANGMEN_JUNK_REF not in caps
    assert "中华人民共和国城乡规划法" in caps
    # ...and nothing emitted for this document is a run of prose
    refs = named_ref_candidates(JIANGMEN_BODY, "江门市人民政府关于江门高新区JH03-R地段控制性详细规划修改的批复")
    assert refs == ["中华人民共和国城乡规划法"], refs


def test_old_junk_capture_is_rejected_even_if_offered():
    """Defence in depth: the sentence-swallowing capture fails the prose test."""
    assert looks_like_body_run(JIANGMEN_JUNK_REF)
    assert looks_like_body_run("A的通知（粤府办〔2007〕16号）精神，制定本实施纲要。 一、实施基础")
    # a PDF-interleaved performance table that a 《…》 span swallowed
    assert looks_like_body_run("国家重点监控企业\n37\n自动监控系统建设运行管理考核实施细则")


def test_real_titles_with_commas_and_colons_survive():
    """，；： appear in GENUINE titles, so they must not be prose markers."""
    for t in ("关于降低收费门槛，促进招商引资的决定",
              "标准化工作导则 第1部分：标准的结构和编写",
              "惠州市1：500、1：1000、1：2000矢量地形图数据采集标准",
              "国务院办公厅关于印发消防安全责任制实施办法的\n通知"):
        assert not looks_like_body_run(t), t
        assert NAMED_REF_PATTERN.findall(f"《{t}》") == [t], t


def test_long_real_instrument_title_still_accepted():
    assert len(LONG_REAL_TITLE) > 30
    assert NAMED_REF_PATTERN.findall(f"依据《{LONG_REAL_TITLE}》的要求") == [LONG_REAL_TITLE]
    assert named_ref_candidates(f"依据《{LONG_REAL_TITLE}》的要求", "某市某局公告") == [LONG_REAL_TITLE]


def test_leadin_genzhao_yields_the_title_only():
    body = "根据《广东省人民政府办公厅关于印发广东省促进汽车消费若干措施的通知》，现决定……"
    out = named_ref_candidates(body, "某市促进汽车消费实施方案")
    assert out == ["广东省人民政府办公厅关于印发广东省促进汽车消费若干措施的通知"], out


def test_nested_title_yields_both_wrapper_and_instrument():
    """A title quoting a title is captured WHOLE (the old pattern truncated it at the
    inner 》) and the quoted instrument is emitted as its own reference."""
    body = "见《市人民政府关于修改《武汉市违法用地上建筑物处置办法》施行时间的通知》。"
    out = named_ref_candidates(body, "某市政府工作报告")
    assert "市人民政府关于修改《武汉市违法用地上建筑物处置办法》施行时间的通知" in out
    assert "武汉市违法用地上建筑物处置办法" in out


def test_own_instrument_core_is_still_a_self_reference():
    """印发《X》的通知 does not cite X."""
    title = "市人民政府关于印发武汉市违法用地上建筑物处置办法的通知"
    body = "《市人民政府关于印发《武汉市违法用地上建筑物处置办法》的通知》"
    assert "武汉市违法用地上建筑物处置办法" not in named_ref_candidates(body, title)


def test_quoted_instrument_in_own_title_is_not_a_self_reference():
    """关于废止〈省实施《X》办法〉的决定 DOES cite X, even though X is inside its own
    title — the loose substring self-reference test used to swallow that edge."""
    title = "黑龙江省人民政府关于废止《黑龙江省实施〈中华人民共和国车船使用税暂行条例〉办法》的决定"
    body = ("《黑龙江省人民政府关于废止〈黑龙江省实施《中华人民共和国车船使用税暂行条例》"
            "办法〉的决定》")
    assert "中华人民共和国车船使用税暂行条例" in named_ref_candidates(body, title)


def test_unclosed_bracket_head_is_recovered_at_its_genre_word():
    """A body that really drops a 》 still yields the head title, cut back to its last
    genre word so the prose tail is dropped (live doc 2660515)."""
    body = ("《关于印发广东省实施技术标准战略“十一五”规划的通知（粤府办〔2007〕16号）"
            "精神，制定本实施纲要。 一、实施基础和环境 1989年，"
            "《中华人民共和国标准化法》")
    heads = list(recover_named_heads(body))
    assert heads and heads[0].startswith("关于印发广东省实施技术标准战略")
    assert "一、实施基础和环境" not in heads[0]
    out = named_ref_candidates(body, "珠海市技术标准战略实施纲要")
    assert any("广东省实施技术标准战略" in r for r in out), out
    assert "中华人民共和国标准化法" in out


def test_masthead_only_head_is_not_recovered():
    """The head that produced the false masthead edges has no genre word -> dropped."""
    body = "《广东省财政厅 广东省医疗保障局关于印发《广东省医疗服务能力提升资金管理实施细则》"
    assert list(recover_named_heads(body)) == []
    out = named_ref_candidates(body, "广东省财政厅关于提前下达补助资金的通知")
    assert out == ["广东省医疗服务能力提升资金管理实施细则"], out


def test_unclosed_bracket_at_end_of_body_is_harmless():
    for body in ("《", "参见《办法", "《深圳市某某管理办法", "《《", "A《B《C"):
        assert NAMED_REF_PATTERN.findall(body) == []
        assert named_ref_candidates(body, "某通知") == []


def test_is_policy_document_unchanged():
    assert is_policy_document("深圳市建设工程扬尘污染防治专项方案")
    assert not is_policy_document("广东省国民经济发展情况报告")


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    bad = 0
    for fn in fns:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except Exception:
            bad += 1
            print(f"  FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"\n{len(fns) - bad}/{len(fns)} passed")
    sys.exit(1 if bad else 0)
