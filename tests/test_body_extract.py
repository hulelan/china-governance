"""Regression checks for the shared govcms body extractor (corpus-lessons A7, 2026-10-07).

Fragments are trimmed replicas of saved raw_html pages that were bodiless on the
droplet because no container matched:
  - 最高法 court.gov.cn   → div.txt_txt (the page's only "article_content" is the search box)
  - 山东 shandong.gov.cn  → div.wip_art_con, short <p> text under the div-scoring floor
  - 江苏 depts (Hanweb)   → class="zoom" / "bt-content zoom" + ContentStart/ContentEnd markers
  - 吉林商务厅 jl_swt      → <script> source inside the body div was returned as text
Also: attachment-only / video pages must stay EMPTY (not junk), and the backfill
guard must never shorten a stored body.

Run: python3 tests/test_body_extract.py   (assert-based, no pytest needed)
  or: python3 -m pytest tests/test_body_extract.py -v
"""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from crawlers.govcms import _extract_body  # noqa: E402

PARA = ("依照有关法律法规和政策规定，现将有关事项通知如下，请各单位结合实际认真贯彻执行，并于规定期限内将落实情况报送我厅。"
        "各市、县人民政府及省直有关部门要加强组织领导，明确责任分工，确保各项措施落地见效。")  # >80 chars (the extractor's floor)


def _page(inner: str) -> str:
    return ("<html><head><title>t</title></head><body><div class='header'><ul>"
            "<li><a href='/a'>首页</a></li></ul></div>" + inner +
            "<div class='footer'>版权所有</div></body></html>")


def test_spc_txt_txt():
    html = _page(
        '<form><input id="article_content" type="submit"/></form>'
        '<div class="detail"><div class="clearfix detail_mes"><li class="fl print">'
        '<a id="print_article">打印本页</a></li></div>'
        f'<div class="txt big"><div class="txt_txt"> {PARA}<br /><p>{PARA}</p></div></div></div>')
    t = _extract_body(html)
    assert PARA in t, t
    assert "首页" not in t and "打印本页" not in t, t


def test_shandong_wip_art_con_short_notice():
    html = _page(
        '<div class="wip_art_conbg"><div class="wip_art_h">公示</div>'
        '<div class="wip_art_con"><meta name="ContentStart"/>'
        '<p style="text-indent:2em;">现对拟聘用人员进行公示。公示期为5个工作日，自2026年8月14日至2026年8月20日，期间如有异议请向办公厅实名反映。</p>'
        '<p>监督电话：0531-51786568</p><p style="text-align:right">山东省人民政府办公厅</p>'
        '<meta name="ContentEnd"/></div></div>')
    t = _extract_body(html)
    assert "拟聘用人员进行公示" in t and "0531-51786568" in t, t


def test_hanweb_class_zoom_and_markers():
    html = _page(
        '<div class="main-con"><h1 class="title">标题</h1>'
        f'<div class="zoom"><meta name="ContentStart"><p>{PARA}</p><meta name="ContentEnd"></div>'
        '<div class="print-close fr"><a class="print">打印</a></div></div>')
    t = _extract_body(html)
    assert PARA in t and "打印" not in t, t
    # markers alone (no listed container) still yield the body
    html2 = _page(f'<div class="unknown-skin"><meta name="ContentStart"/><p>{PARA}</p>'
                  '<meta name="ContentEnd"/></div>')
    assert PARA in _extract_body(html2)


def test_script_source_is_not_body():
    html = _page(
        '<table><tr><td><div id="zoom"><script type="text/javascript">'
        "var file_appendix='x.pdf'; if(file_appendix!=\"\"){document.write(\"附件：*点击右键，选择“目标另存为”\");}"
        "var file_appendix1=''; var a=1; var b=2; var c=3; var d=4; var e=5; var f=6; var g=7; var h=8;"
        '</script><a href="x.pdf">吉林省商务厅2020年部门预算.pdf</a></div></td></tr></table>')
    t = _extract_body(html)
    assert "var file_appendix" not in t and "document.write" not in t, t


def test_attachment_only_and_video_pages_stay_empty():
    pdf_only = _page('<div class="zoom"><meta name="ContentStart"><p><a href="/f.pdf">'
                     '第二批公开.pdf</a></p><meta name="ContentEnd"></div>')
    assert _extract_body(pdf_only) == "", _extract_body(pdf_only)
    video = _page('<div id="zoom"><meta name="ContentStart"><meta name="ContentEnd"></div>')
    assert _extract_body(video) == ""


def test_backfill_guard_never_shortens():
    """The UPDATE predicate used by scripts/backfill_from_html.py."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE documents(id INTEGER PRIMARY KEY, body_text_cn TEXT)")
    conn.executemany("INSERT INTO documents VALUES (?,?)",
                     [(1, None), (2, ""), (3, "short"), (4, "a much longer existing body text")])
    new = "new body of medium length"
    sql = ("UPDATE documents SET body_text_cn=? WHERE id=? AND "
           "(body_text_cn IS NULL OR LENGTH(body_text_cn) < LENGTH(?))")
    for i in (1, 2, 3, 4):
        conn.execute(sql, (new, i, new))
    got = dict(conn.execute("SELECT id, body_text_cn FROM documents"))
    assert got[1] == new and got[2] == new and got[3] == new
    assert got[4] == "a much longer existing body text", got[4]


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
