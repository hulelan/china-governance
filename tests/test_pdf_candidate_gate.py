"""extract_pdf_text.py's candidate gates, exercised as real SQL against fixture rows.

Both gates excluded documents the tool can actually serve, and each exclusion is a
measured population rather than a hypothetical:

  * the MARKER gate (body must say 附件 / 点击 / 下载) hid 1,100 rows whose body carries
    none of them because the body IS the attachment's filename — CLAUDE.md's seventh
    bug-shape. 揭阳市2016年市本级决算草案报告 is the worked case: body = title + a stray
    carriage return, with the identically-named PDF sitting in attachments_json.
  * `raw_html_path != ''` was needed only when the URL had to be parsed out of saved
    HTML. attachment_url_from_json needs no HTML, and raw_html_path is a dangling
    pointer for all 725 mofcom rows.
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.extract_pdf_text import candidate_where  # noqa: E402

PDF_JSON = '[{"name": "揭府办[2016]76号.pdf", "mime": "application/pdf", "url": "http://x/a.pdf"}]'
DOC_JSON = '[{"name": "x.docx", "mime": "application/msword", "url": "http://x/a.docx"}]'


def db():
    c = sqlite3.connect(":memory:")
    c.execute("""CREATE TABLE documents (
        id INTEGER PRIMARY KEY, site_key TEXT, title TEXT, body_text_cn TEXT,
        url TEXT, raw_html_path TEXT, attachments_json TEXT)""")
    rows = [
        # id, site, body, raw_html_path, attachments_json, comment
        (1, "gd", "详见附件", "raw_html/gd/1.html", PDF_JSON),       # classic: marker + html
        (2, "jieyang", "揭阳市2016年市本级决算草案报告\r", "", PDF_JSON),  # NEW: no marker, no html
        (3, "mofcom", "公告全文见附件", "", PDF_JSON),                # NEW: marker, dangling html
        (4, "gd", "请点击查看", "", DOC_JSON),                       # marker, no html, no PDF -> out
        (5, "gd", "一份普通的短通知，正文完整。", "raw_html/gd/5.html", ""),  # no marker, no PDF -> out
        (6, "gd", "详见附件" + "正文" * 300, "raw_html/gd/6.html", PDF_JSON),    # body too long -> out
        (7, "cac", "下载链接", "", PDF_JSON),                        # cac never needed html
    ]
    for i, sk, body, rhp, aj in rows:
        c.execute("INSERT INTO documents (id, site_key, title, body_text_cn, url, "
                  "raw_html_path, attachments_json) VALUES (?,?,?,?,?,?,?)",
                  (i, sk, "t%d" % i, body, "http://x/%d" % i, rhp, aj))
    return c


def selected(site=None, threshold=400):
    c = db()
    where, params = candidate_where(threshold, site)
    return {r[0] for r in c.execute(f"SELECT id FROM documents {where}", params)}


def test_a_pdf_in_attachments_json_qualifies_without_any_body_marker():
    """Row 2: body is the title plus a stray \\r — the 1,100-row population."""
    assert 2 in selected()


def test_a_dangling_raw_html_path_no_longer_excludes_a_json_served_row():
    """Row 3: mofcom's 725 rows all have a raw_html_path pointing at nothing."""
    assert 3 in selected()


def test_the_classic_marker_plus_html_row_is_still_selected():
    assert 1 in selected()


def test_a_marker_with_neither_html_nor_a_pdf_is_excluded():
    """Row 4: nothing to fetch — the URL would have to come from HTML that is absent."""
    assert 4 not in selected()


def test_a_short_body_with_no_marker_and_no_pdf_is_not_a_candidate():
    """The gate widened, it did not dissolve: row 5 has no attachment at all.

    Row 5's text avoids the WORD 附件 deliberately. The first version of this fixture
    read 没有附件标记 ("carries no 附件 marker") and therefore contained the marker,
    so the test failed on its own prose rather than on the code.
    """
    assert 5 not in selected()


def test_a_long_body_is_never_a_candidate():
    assert 6 not in selected()


def test_cac_is_exempt_from_the_html_requirement():
    assert selected(site="cac") == {7}


def test_the_site_filter_restricts_to_that_site():
    assert selected(site="jieyang") == {2}


def test_params_are_bound_not_interpolated():
    """The threshold and site are placeholders, so a site name cannot alter the SQL."""
    where, params = candidate_where(400, "x'; DROP TABLE documents; --")
    assert params == [400, "x'; DROP TABLE documents; --"]
    assert "DROP TABLE" not in where
