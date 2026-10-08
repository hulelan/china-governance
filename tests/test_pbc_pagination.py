"""PBOC 条法司 pagination + row parsing (crawlers/pbc.py, 2026-10-08).

The bug this locks down: `crawlers.pbc` walked ONLY page 1 of each section and its
row regex required a node-id of `\\d{15,}`, so it held 31 documents dated 2025-12 and
later. Two independent causes, and the test file covers both:

  (1) PAGINATION. The pager is an easysite/eportal article-list portlet. `index_N.html`
      404s and there is no `共N页`/`createPageHTML`; page 1 instead names its own later
      pages in `tagname="/<section>/<prefix>-<N>.html"` with a `totalpage` attribute.
      The `prefix` MUST be read from those tagnames, never rebuilt from `moduleid`:
      144957's module id is numeric and used whole (`21892` → `21892-2.html`) while
      3581332's is a 32-char uuid of which the path uses only the first 8 characters
      (`3b3662a6db7145c0…` → `3b3662a6-2.html`).

  (2) A LENGTH FLOOR ON A DERIVED STRING (CLAUDE.md's recurring bug shape). Legacy
      PBOC articles carry SHORT numeric CMS node-ids (`3591404`), not the 19-digit
      timestamp the newest ones use, so `\\d{15,}` silently refused every pre-~2025
      document — including 中国人民银行令〔2024〕第4号 — while returning a clean answer.
      The floor now lives only on the DATE fallback (`_TS_ID_MIN`), where a short id
      genuinely cannot be a timestamp, and the date itself comes from the list page.

Fixtures below are trimmed from the live pages fetched 2026-10-08. No network.

Run: python3 -m pytest tests/test_pbc_pagination.py -v
  or: python3 tests/test_pbc_pagination.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import urllib.error  # noqa: E402

from crawlers import pbc  # noqa: E402
from crawlers.pbc import (  # noqa: E402
    DEFAULT_MAX_PAGES, SECTIONS, _attachments, _body_of, _date_for, _page_url,
    _pager, _rows,
)

ORDERS = "tiaofasi/144941/144957"      # 部门规章 — numeric module id
NORMS = "tiaofasi/144941/3581332"      # 规范性文件 — uuid module id, 8-char path prefix


def _row(section, nid, title, date):
    """One list row, in the live template's shape (anchor then a hui12 date span)."""
    return (
        '<table cellspacing="0"><tbody><tr><td width="15"></td>'
        '<td height="22" align="left"><font class="newslist_style" style="margin-right:10px;">'
        f'<a href="/{section}/{nid}/index.html" onclick="void(0)" target="_blank" '
        f'title="{title}" istitle="true">{title[:20]}...</a></font>'
        f'<span class="hui12">{date}</span></td></tr></tbody></table>\n'
    )


def _pager_block(section, prefix, moduleid, cur, total):
    links = ""
    if cur > 1:
        links += (f'<a style="cursor:pointer" onclick="queryArticleByCondition(this,'
                  f"'/{section}/{prefix}-{cur - 1}.html')\" "
                  f'tagname="/{section}/{prefix}-{cur - 1}.html" class="pagingNormal">上一页</a>')
    if cur < total:
        links += (f'<a style="cursor:pointer" onclick="queryArticleByCondition(this,'
                  f"'/{section}/{prefix}-{cur + 1}.html')\" "
                  f'tagname="/{section}/{prefix}-{cur + 1}.html" class="pagingNormal">下一页</a>')
    links += (f'<a style="cursor:pointer" tagname="/{section}/{prefix}-{total}.html" '
              f'class="pagingNormal">尾页</a>')
    return (
        f'<div><table><tbody><tr><td nowrap="true">'
        f'<a tagname="[HOMEPAGE]" class="">首页</a>{links}</td>'
        f'<td class="Normal"> 总记录数:113,每页显示20条记录,当前页: '
        f'<font color="red">{cur}</font> /{total} </td></tr></tbody></table></div>\n'
        f'<input type="hidden" name="article_paging_list_hidden" moduleid="{moduleid}" '
        f'modulekey="{moduleid}" totalpage="{total}">'
    )


# --- 部门规章 page 1: 19-digit timestamp node-ids (what the old code could see) ---
ORDERS_P1 = (
    '<div style="height:480px" opentype="page">'
    + _row(ORDERS, "2026052217462526593", "中国人民银行令〔2026〕第4号（中国人民银行关于修改部分规章的决定)", "2026-05-22")
    + _row(ORDERS, "2026012314163359926", "中国人民银行令〔2026〕第2号（中国人民银行残缺污损人民币兑换办法）", "2026-01-26")
    + _pager_block(ORDERS, "21892", "21892", 1, 6)
    + "</div>"
)

# --- 部门规章 page 2: SHORT legacy node-ids (what the \d{15,} floor refused) ---
ORDERS_P2 = (
    '<div style="height:480px" opentype="page">'
    + _row(ORDERS, "5414094", "中国人民银行令〔2024〕第4号（非银行支付机构监督管理条例实施细则）", "2024-07-26")
    + _row(ORDERS, "4099060", "中国人民银行令〔2020〕第5号（中国人民银行金融消费者权益保护实施办法）", "2020-09-18")
    + _row(ORDERS, "3591404", "支付结算业务代理办法（银发〔2000〕176号）", "2000-06-01")
    + _pager_block(ORDERS, "21892", "21892", 2, 6)
    + "</div>"
)

# --- 规范性文件 page 1: uuid module id, path prefix is its first 8 chars ---
NORMS_P1 = (
    '<div style="height:480px" opentype="page">'
    + _row(NORMS, "2026091114591687697", "中国人民银行公告〔2026〕第24号", "2026-09-11")
    + _pager_block(NORMS, "3b3662a6", "3b3662a6db7145c0a025d2d410570ae1", 1, 22)
    + "</div>"
)

# A page the portlet renders with its chrome and pager but no article rows.
EMPTY_PAGE = '<div style="height:480px" opentype="page">' + \
    _pager_block(ORDERS, "21892", "21892", 6, 6) + "</div>"

NO_PAGER = '<div>' + _row(ORDERS, "2026052217462526593", "中国人民银行令〔2026〕第4号", "2026-05-22") + '</div>'


# ---------------------------------------------------------------- _pager

def test_pager_numeric_prefix():
    assert _pager(ORDERS_P1, ORDERS) == ("21892", 6)


def test_pager_uuid_prefix_is_truncated_not_the_moduleid():
    prefix, total = _pager(NORMS_P1, NORMS)
    assert (prefix, total) == ("3b3662a6", 22)
    # The whole point: rebuilding the path from `moduleid` would 404.
    assert prefix != "3b3662a6db7145c0a025d2d410570ae1"


def test_pager_absent_is_single_page():
    assert _pager(NO_PAGER, ORDERS) == (None, 1)
    assert _pager("", ORDERS) == (None, 1)
    assert _pager(None, ORDERS) == (None, 1)


def test_pager_falls_back_to_last_page_link_without_totalpage_attr():
    html = ORDERS_P1.replace('totalpage="6"', 'totalpages="6"')
    assert _pager(html, ORDERS) == ("21892", 6)   # from the 尾页 tagname


def test_pager_ignores_another_sections_tagnames():
    assert _pager(NORMS_P1, ORDERS) == (None, 1)


# ---------------------------------------------------------------- _page_url

def test_page_url_page_one_is_the_section_index():
    assert _page_url(ORDERS, "21892", 1) == "http://www.pbc.gov.cn/tiaofasi/144941/144957/index.html"
    assert _page_url(ORDERS, "21892", 0) == "http://www.pbc.gov.cn/tiaofasi/144941/144957/index.html"
    # No prefix discovered → never guess a paging path.
    assert _page_url(ORDERS, None, 5) == "http://www.pbc.gov.cn/tiaofasi/144941/144957/index.html"


def test_page_url_later_pages():
    assert _page_url(ORDERS, "21892", 2) == \
        "http://www.pbc.gov.cn/tiaofasi/144941/144957/21892-2.html"
    assert _page_url(NORMS, "3b3662a6", 22) == \
        "http://www.pbc.gov.cn/tiaofasi/144941/3581332/3b3662a6-22.html"


# ---------------------------------------------------------------- _rows

def test_rows_page_one_timestamp_ids():
    rows = _rows(ORDERS_P1, ORDERS)
    assert [r[0] for r in rows] == ["2026052217462526593", "2026012314163359926"]
    assert rows[0][2] == "2026-05-22"
    # The full title comes from the title= attribute, not the "..."-truncated text.
    assert rows[0][1].endswith("决定)") and "..." not in rows[0][1]


def test_rows_accept_short_legacy_ids():
    """The regression: `\\d{15,}` refused every pre-2025 document."""
    rows = _rows(ORDERS_P2, ORDERS)
    assert [r[0] for r in rows] == ["5414094", "4099060", "3591404"]
    assert [r[2] for r in rows] == ["2024-07-26", "2020-09-18", "2000-06-01"]


def test_rows_keeps_the_last_row_on_a_page():
    """A tail regex that required a FOLLOWING anchor would drop the final row."""
    rows = _rows(ORDERS_P2, ORDERS)
    assert rows[-1][0] == "3591404"
    assert rows[-1][2] == "2000-06-01"


def test_rows_keeps_a_dateless_row_rather_than_dropping_it():
    html = ORDERS_P1.replace('<span class="hui12">2026-05-22</span>', "")
    rows = _rows(html, ORDERS)
    assert [r[0] for r in rows] == ["2026052217462526593", "2026012314163359926"]
    assert rows[0][2] == ""            # unknown, loudly — not absent


def test_rows_dedupes_and_scopes_to_the_section():
    assert _rows(ORDERS_P1 + ORDERS_P1, ORDERS) == _rows(ORDERS_P1, ORDERS)
    assert _rows(NORMS_P1, ORDERS) == []
    assert _rows(EMPTY_PAGE, ORDERS) == []


def test_rows_accepts_an_absolute_href():
    html = ORDERS_P1.replace(f'href="/{ORDERS}/', f'href="http://www.pbc.gov.cn/{ORDERS}/')
    assert [r[0] for r in _rows(html, ORDERS)] == \
        ["2026052217462526593", "2026012314163359926"]


# ---------------------------------------------------------------- _date_for

def test_date_for_nodeid_timestamp_still_parses():
    """The original dating trick, unchanged, as the fallback."""
    assert _date_for("2026052217462526593", "") == "2026-05-22"
    assert _date_for("2025120610050660916", "") == "2025-12-06"


def test_date_for_prefers_the_list_page_date():
    # The 19-digit id is the CMS *creation* stamp and can precede publication.
    assert _date_for("2026012314163359926", "2026-01-26") == "2026-01-26"
    assert _date_for("3591404", "2000-06-01") == "2000-06-01"


def test_date_for_short_id_with_no_list_date_is_empty_not_wrong():
    # 3591404 would read as "3591-40-4" under a blind slice.
    assert _date_for("3591404", "") == ""
    assert _date_for("5414094", "") == ""


# ---------------------------------------------------------------- _walk

class _FakeSite:
    """Serves the fixtures by URL and records what was asked for."""

    def __init__(self, pages):
        self.pages = pages          # {url: html}
        self.asked = []

    def __call__(self, url):
        self.asked.append(url)
        if url not in self.pages:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        return self.pages[url]


def _with_site(pages, fn):
    """Run `fn(fake_site)` with crawlers.pbc._get served from `pages`. No network."""
    orig_get, orig_sleep = pbc._get, pbc.time.sleep
    try:
        fake = _FakeSite(pages)
        pbc._get, pbc.time.sleep = fake, (lambda *_a, **_k: None)
        return fn(fake)
    finally:
        pbc._get, pbc.time.sleep = orig_get, orig_sleep


ORDERS_PAGES = {
    _page_url(ORDERS, None, 1): ORDERS_P1,
    _page_url(ORDERS, "21892", 2): ORDERS_P2,
}


def test_walk_reaches_page_two_ids():
    def run(fake):
        rows = pbc._walk(ORDERS, max_pages=DEFAULT_MAX_PAGES)
        ids = [r[0] for r in rows]
        # page 1 first (newest), then page 2's legacy ids
        assert ids[:2] == ["2026052217462526593", "2026012314163359926"]
        assert "3591404" in ids and "5414094" in ids
        assert len(ids) == 5
        # the oldest reachable date came off the LIST page, not a node-id
        assert min(r[2] for r in rows) == "2000-06-01"
        # it tried page 3 (totalpage=6) and took the 404 as the end
        assert _page_url(ORDERS, "21892", 3) in fake.asked
    _with_site(ORDERS_PAGES, run)


def test_walk_stops_at_the_max_pages_bound():
    def run(fake):
        rows = pbc._walk(ORDERS, max_pages=1)
        assert [r[0] for r in rows] == ["2026052217462526593", "2026012314163359926"]
        assert fake.asked == [_page_url(ORDERS, None, 1)]
    _with_site(ORDERS_PAGES, run)

    def run2(fake):
        rows = pbc._walk(ORDERS, max_pages=2)
        assert len(rows) == 5
        # bounded: it must NOT ask for page 3 even though totalpage says 6
        assert _page_url(ORDERS, "21892", 3) not in fake.asked
    _with_site(ORDERS_PAGES, run2)


def test_walk_stops_cleanly_on_a_404():
    def run(fake):
        rows = pbc._walk(ORDERS, max_pages=DEFAULT_MAX_PAGES)
        assert [r[0] for r in rows] == ["2026052217462526593", "2026012314163359926"]
        assert fake.asked[-1] == _page_url(ORDERS, "21892", 2)
    _with_site({_page_url(ORDERS, None, 1): ORDERS_P1}, run)


def test_walk_stops_cleanly_on_an_empty_page():
    pages = dict(ORDERS_PAGES)
    pages[_page_url(ORDERS, "21892", 3)] = EMPTY_PAGE
    pages[_page_url(ORDERS, "21892", 4)] = ORDERS_P2   # would be reachable past the stop

    def run(fake):
        rows = pbc._walk(ORDERS, max_pages=DEFAULT_MAX_PAGES)
        assert len(rows) == 5                          # stopped at the empty page 3
        assert _page_url(ORDERS, "21892", 4) not in fake.asked
    _with_site(pages, run)


def test_walk_stops_on_a_page_that_repeats_the_previous_rows():
    """A pager that silently clamps to the last page must not loop forever."""
    pages = {_page_url(ORDERS, None, 1): ORDERS_P1}
    for n in range(2, 8):
        pages[_page_url(ORDERS, "21892", n)] = ORDERS_P1   # same rows every time

    def run(fake):
        rows = pbc._walk(ORDERS, max_pages=DEFAULT_MAX_PAGES)
        assert len(rows) == 2
        assert len(fake.asked) == 2
    _with_site(pages, run)


def test_walk_does_not_page_a_section_with_no_pager():
    def run(fake):
        rows = pbc._walk(ORDERS, max_pages=DEFAULT_MAX_PAGES)
        assert len(rows) == 1
        assert fake.asked == [_page_url(ORDERS, None, 1)]
    _with_site({_page_url(ORDERS, None, 1): NO_PAGER}, run)


def test_walk_survives_a_non_404_page_error():
    def boom(url):
        if url == _page_url(ORDERS, None, 1):
            return ORDERS_P1
        raise urllib.error.URLError("connection reset")

    orig_get, orig_sleep = pbc._get, pbc.time.sleep
    try:
        pbc._get, pbc.time.sleep = boom, (lambda *_a, **_k: None)
        rows = pbc._walk(ORDERS, max_pages=DEFAULT_MAX_PAGES)
        assert len(rows) == 2          # kept page 1 rather than raising
    finally:
        pbc._get, pbc.time.sleep = orig_get, orig_sleep


# ------------------------------------------------- _body_of / _attachments
#
# PBOC published most pre-2020 documents as a PDF. The article page's `id="zoom"`
# then holds ONE anchor whose link text is the document's own title + ".pdf", so a
# naive extraction yields a "body" that reads like prose, counts as "already stored
# WITH a body" (nothing ever revisits it), and carries none of the 附件/点击/下载
# markers `scripts/extract_pdf_text.py` selects on. 360 of the 541 live documents
# are this shape. Trimmed from /tiaofasi/144941/144957/3591089/ (1993-01-14).

ATTACHMENT_ARTICLE = (
    '<div id="zoom"> \n'
    '<p><a href="/tiaofasi/144941/144957/3591089/2018073111141136708.pdf">'
    '中国人民银行关于执行《储蓄管理条例》的若干规定（银发〔1993〕7号）.pdf</a></p>\n'
    '<p></p><p></p>\n</div>'
)

INLINE_ARTICLE = (
    '<div id="zoom">'
    + "".join(f"<p>第{n}条 中国人民银行依照本办法对支付机构实施监督管理，有关事项规定如下。</p>"
              for n in range(1, 8))
    + '</div>'
)

INLINE_PLUS_ATTACHMENT = INLINE_ARTICLE.replace(
    "</div>",
    '<p><a href="/tiaofasi/144941/144957/5414094/20240726.pdf">附表.pdf</a></p></div>')


def test_body_of_labels_an_attachment_only_article():
    body = _body_of(ATTACHMENT_ARTICLE)
    assert body.startswith("附件：")
    assert "储蓄管理条例" in body
    # the whole point: extract_pdf_text.py's selection must now see it
    assert any(k in body for k in ("附件", "点击", "下载"))


def test_body_of_leaves_a_real_inline_body_alone():
    body = _body_of(INLINE_ARTICLE)
    assert not body.startswith("附件：")
    assert len(body) > 200
    # a long real body with an attachment beside it is still not an attachment stub
    assert not _body_of(INLINE_PLUS_ATTACHMENT).startswith("附件：")


def test_body_of_does_not_double_label():
    already = '<div id="zoom"><p>附件：<a href="/a/b/c.pdf">办法.pdf</a></p></div>'
    assert _body_of(already).count("附件") == 1


def test_body_of_without_zoom_is_empty():
    assert _body_of("<html><body>no zoom here</body></html>") == ""


def test_attachments_are_absolute_and_deduped():
    assert _attachments(ATTACHMENT_ARTICLE) == [
        "http://www.pbc.gov.cn/tiaofasi/144941/144957/3591089/2018073111141136708.pdf"]
    doubled = ATTACHMENT_ARTICLE.replace("</div>", ATTACHMENT_ARTICLE[ATTACHMENT_ARTICLE.find("<p><a"):])
    assert len(_attachments(doubled)) == 1


def test_attachments_empty_for_an_inline_article():
    assert _attachments(INLINE_ARTICLE) == []


# ---------------------------------------------------------------- config shape

def test_sections_shape_is_still_one_entry_per_section():
    """(path, label, per-section page cap or None). The cap was added 2026-10-08
    with 沟通交流, which is 411 pages against the document sections' <= 22."""
    assert [s for s, _l, _c in SECTIONS][:2] == [NORMS, ORDERS]
    assert all(isinstance(s, str) and isinstance(l, str)
               and (c is None or isinstance(c, int)) for s, l, c in SECTIONS)
    # the two 条法司 document sections are walked WHOLE — no cap of their own
    assert [c for s, _l, c in SECTIONS if s in (NORMS, ORDERS)] == [None, None]
    assert DEFAULT_MAX_PAGES >= 22      # both document sections fit under the bound


def test_routine_diplomacy_titles_are_skipped_but_instruments_are_not():
    """A DENYLIST, not an allowlist: an allowlist would silently drop the next
    document type nobody anticipated, which is how the 2026-10-08 exchange-rate
    position statement would have been missed. Measured 81% kept over 4 pages."""
    from crawlers.pbc import _SKIP_TITLE_RE as R
    for t in ("中国人民银行行长潘功胜会见欧盟驻华大使范恺珀",
              "中国人民银行召开外资金融机构座谈会",
              "中国人民银行副行长宣昌能会见贝宝全球执行副总裁艾伦",
              "中国人民银行行长潘功胜会见巴西财政部部长杜里甘"):
        assert R.search(t), t
    for t in ("中国人民银行关于人民币汇率的政策立场",
              "中国人民银行货币政策委员会召开2026年第三季度例会",
              "财政部 中国人民银行 金融监管总局关于实施居民购房贷款贴息政策的通知",
              "中国人民银行等八部门联合印发《关于金融支持服务业扩能提质的指导意见》",
              "2026年8月金融统计数据报告",
              "中国人民银行调整完善若干货币政策工具",
              "中老跨境数字支付互联互通正式启动",
              "中国人民银行行长潘功胜在香港货币与固定收益峰会上的致辞"):
        assert not R.search(t), t


def test_communications_section_is_capped():
    """411 pages of mostly communications: the nightly takes recent material and a
    historical backfill is a deliberate --max-pages run."""
    caps = {s: c for s, _l, c in SECTIONS}
    comm = [s for s in caps if s.startswith("goutongjiaoliu")]
    assert comm, "the communications section should be configured"
    assert caps[comm[0]] and caps[comm[0]] <= 60, caps


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            passed += 1
            print(f"  ok {name}")
    print(f"{passed} passed")
