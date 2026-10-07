"""Regression checks for the shared metadata-header extractor (2026-10-07).

`crawlers.gov._extract_metadata_table` is used by gov / govmirror / govcms. Commit
0df9ee9's report found 文号 + publisher at 0/10 on the 无锡 intertid CMS (and the
wxd_* districts) because the parser only knew gov.cn's Template A
`<td><b>LABEL：</b></td><td>VALUE</td>` rows. The generic pass added here walks
th/td cells, dt/dd and li/span lists with a label→field alias map.

Fixtures are trimmed replicas of pages fetched 2026-10-07:
  - 无锡市政府 www.wuxi.gov.cn/doc/2026/09/18/4833205.shtml (comment-wrapped values)
  - 锡山区   www.jsxishan.gov.cn/doc/2026/08/20/4820950.shtml (plain `<td class="t">`)
  - 江阴市   www.jiangyin.gov.cn/doc/2023/04/13/1131050.shtml (`<td class="title">`)
  - 梁溪区   www.wxlx.gov.cn/doc/2025/12/16/4734097.shtml  ("—  —" placeholder 文号)
The Template A fixture pins the OLD output so existing sites stay byte-identical.

Run: python3 tests/test_metadata_table.py   (assert-based, no pytest needed)
  or: python3 -m pytest tests/test_metadata_table.py -v
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from crawlers.gov import _extract_metadata_table  # noqa: E402


_TEMPLATE_A = (
    '<table><tr><td><b>索　引　号</b></td><td>000014349/2024-00012</td></tr>'
    '<tr><td><b>主题分类</b></td><td>工业、交通\\其他</td></tr>'
    '<tr><td><b>发文机关</b></td><td>国务院办公厅</td></tr>'
    '<tr><td><b>成文日期</b></td><td>2024年01月05日</td></tr>'
    '<tr><td><b>标　　题</b></td><td>国务院办公厅关于XX的意见</td></tr>'
    '<tr><td><b>发文字号</b></td><td>国办发〔2024〕1号</td></tr>'
    '<tr><td><b>发布日期</b></td><td>2024年01月10日</td></tr></table>'
)


def test_template_a_unchanged():
    # gov.cn Template A with colon-free labels — the pre-2026-10-07 parser's full
    # output (incl. title), pinned byte-for-byte.
    got = _extract_metadata_table(_TEMPLATE_A)
    assert got == {
        "identifier": "000014349/2024-00012",
        "classify_theme_name": "工业、交通\\其他",
        "publisher": "国务院办公厅",
        "date_written_str": "2024年01月05日",
        "title": "国务院办公厅关于XX的意见",
        "document_number": "国办发〔2024〕1号",
        "date_published_str": "2024年01月10日",
    }, got


def test_template_a_colon_labels():
    # The live gov.cn pages write <b>发文字号：</b>; the old regex `([^<]+)：?` swallowed
    # the colon so ONLY identifier ('索' in label) ever matched — gov's stored 文号 and
    # publisher came from the JSON feed. The generic pass now recovers them (verified
    # 658/659 文号 identical to the feed on droplet raw HTML); title is deliberately
    # NOT taken from the generic pass.
    html = _TEMPLATE_A.replace("</b></td>", "：</b></td>")
    got = _extract_metadata_table(html)
    assert got["identifier"] == "000014349/2024-00012", got
    assert got["document_number"] == "国办发〔2024〕1号", got
    assert got["publisher"] == "国务院办公厅", got
    assert got["classify_theme_name"] == "工业、交通\\其他", got
    assert "title" not in got, got


def test_wuxi_municipal_comment_wrapped_cells():
    html = (
        '<div class="table01"><table><tr>'
        '<td class="t" width="14%">信息索引号</td><td width="30%"><!--<$[SYH]>-->014006438/2026-03652<!--<$[SYH]>--></td>'
        '<td class="t">生成日期</td><td><!--<$[SCRQ]>-->2026-09-12<!--<$[SCRQ]>--></td>'
        '<td class="t">公开日期</td><td><!--<$[FBRQ]>-->2026-09-18<!--<$[FBRQ]>--></td></tr>'
        '<tr><td class="t" width="14%">文件编号</td><td><!--<$[WJBH]>-->政府令187号<!--<$[WJBH]>--></td>'
        '<td class="t">效力状况</td><td colspan="3"><!--<$[XLZK]>-->有效<!--<$[XLZK]>--></td></tr>'
        '<tr><td class="t">发布机构</td><td><!--<$[FBJG]>-->无锡市人民政府<!--<$[FBJG]>--></td>'
        '<!--<td class="t">附件下载</td><td colspan="3">—&nbsp;&nbsp;—</td>--></tr>'
        '<tr><td class="t">公开方式</td><td>主动公开</td></tr></table></div>'
    )
    got = _extract_metadata_table(html)
    assert got["document_number"] == "政府令187号", got
    assert got["publisher"] == "无锡市人民政府", got
    assert got["identifier"] == "014006438/2026-03652", got
    assert got["date_published_str"] == "2026-09-18", got
    assert "date_written_str" not in got, got  # 生成日期 is an index stamp, not 成文
    assert "有效" not in got.values() and "主动公开" not in got.values(), got


def test_xishan_district_plain_cells_and_fawenriqi():
    html = (
        '<table width="100%" border="1"><tbody><tr>'
        '<td width="15%" class="t">信息索引号</td><td>014034703/2026-00839</td>'
        '<td width="10%" class="t">发文日期</td><td width="20%">2026-08-20</td>'
        '<td width="10%" class="t">公开日期</td><td width="15%">2026-08-20</td></tr>'
        '<tr><td class="t">文件编号</td><td>锡府发〔2026〕7号</td>'
        '<td class="t">效力状况</td><td colspan="3">有效</td></tr>'
        '<tr><td class="t">发布机构</td><td>无锡市锡山区人民政府办公室</td>'
        '<td class="t">文件下载</td><td \n colspan="3"\n style="x">'
        '<a href="/f.pdf">锡府发〔2026〕7号.pdf</a></td></tr></tbody></table>'
    )
    got = _extract_metadata_table(html)
    assert got["document_number"] == "锡府发〔2026〕7号", got
    assert got["publisher"] == "无锡市锡山区人民政府办公室", got
    assert got["date_written_str"] == "2026-08-20", got


def test_jiangyin_title_class_cells():
    html = (
        '<table cellpadding="0" class="art_xxgktab">\n\t<tr>\n\t\t<td class="title">信息索引号</td>'
        '\n\t\t<td>01404053X/2023-00861</td>\n\t\t<td class="title">生成日期</td>\n\t\t<td>2023-02-24</td>'
        '\n\t\t<td class="title">公开日期</td>\n\t\t<td>2023-03-17</td>\n\t</tr>\n\t<tr>'
        '\n\t\t<td class="title">文件编号</td>\n\t\t<td>澄政发〔2023〕10号</td>'
        '\n\t\t<td class="title">公开时限</td>\n\t\t<td>长期公开</td>'
        '\n\t\t<td class="title">发布机构</td>\n\t\t<td >江阴市人民政府办公室</td>\n\t</tr></table>'
    )
    got = _extract_metadata_table(html)
    assert got["document_number"] == "澄政发〔2023〕10号", got
    assert got["publisher"] == "江阴市人民政府办公室", got
    assert got["identifier"] == "01404053X/2023-00861", got


def test_placeholder_docnum_stays_empty():
    html = (
        '<table><tr><td class="t">文件编号</td><td><!--<$[WJBH]>-->—&nbsp;&nbsp;—<!--<$[WJBH]>--></td>'
        '<td class="t">发布机构</td><td><!--<$[FBJG]>-->区政府办公室<!--<$[FBJG]>--></td></tr></table>'
    )
    got = _extract_metadata_table(html)
    assert "document_number" not in got, got
    assert got["publisher"] == "区政府办公室", got


def test_th_td_dt_dd_and_li_span_lists_with_fullwidth_colons():
    html = (
        '<table><tr><th>发文字号：</th><td>粤府〔2025〕3号</td></tr>'
        '<tr><th> 制发机关 : </th><td>广东省人民政府</td></tr></table>'
    )
    got = _extract_metadata_table(html)
    assert got == {"document_number": "粤府〔2025〕3号", "publisher": "广东省人民政府"}, got

    html = '<dl><dt>文号</dt><dd>闽政〔2024〕9号</dd><dt>发布单位：</dt><dd>福建省人民政府</dd><dt>公开方式</dt><dd>主动公开</dd></dl>'
    got = _extract_metadata_table(html)
    assert got == {"document_number": "闽政〔2024〕9号", "publisher": "福建省人民政府"}, got

    html = ('<ul class="xxgk"><li><span>发文字号</span>：苏科〔2025〕12号</li>'
            '<li><span class="lab">发布机构：</span><span>江苏省科学技术厅</span></li>'
            '<li><span>成文日期</span>2025-03-01</li></ul>')
    got = _extract_metadata_table(html)
    assert got == {"document_number": "苏科〔2025〕12号", "publisher": "江苏省科学技术厅",
                   "date_written_str": "2025-03-01"}, got


def test_alias_priority_and_no_override():
    # 发文字号 (rank 0) beats 文号 (rank 2) regardless of order; pass-1 value is kept.
    html = ('<table><tr><td>文号</td><td>B</td></tr><tr><td>发文字号</td><td>A</td></tr></table>')
    assert _extract_metadata_table(html)["document_number"] == "A"
    html = ('<table><tr><td><b>发文字号：</b></td><td>OLD</td></tr>'
            '<tr><td class="t">文件编号</td><td>NEW</td></tr></table>')
    assert _extract_metadata_table(html)["document_number"] == "OLD"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fails = 0
    for t in tests:
        try:
            t()
            print(f"ok   {t.__name__}")
        except AssertionError as e:
            fails += 1
            print(f"FAIL {t.__name__}: {str(e)[:300]}")
    print(f"{len(tests) - fails}/{len(tests)} passed")
    sys.exit(1 if fails else 0)
