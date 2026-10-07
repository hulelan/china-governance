"""Paging-extension detection + intertid search-API parsing for crawlers/govcms.py
(jiangsu-second-prefecture.md §2/§3, 2026-10-07).

The bug: `_pages()` chose `index_N.shtml` only when page 0 carried a t-date `.shtml`
link, so 无锡's docymd lists (/doc/YYYY/MM/DD/<id>.shtml, no t-date link, JS-built
pager) fell to `index_N.html` → 404 → --deep stopped at page 0 (130 rows held). The
widened `_page_ext` must (a) keep every t-date site's answer, (b) honour a per-site
`page_ext`, (c) read an explicit pager href, (d) fall back to the article links' own
extension. `_api_rows` parses the POST /info_open/search payload used by the 无锡
districts (list mode AD).

Run: python3 tests/test_govcms_paging.py   (assert-based, no pytest needed)
  or: python3 -m pytest tests/test_govcms_paging.py -v
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from crawlers.govcms import SITES, _api_rows, _page_ext  # noqa: E402

TDATE_HTML = '<ul><li><a href="/zw/zcfg/fl/202501/t20250102_123.html" title="法">法</a>2025-01-02</li></ul>'
TDATE_SHTML = '<ul><li><a href="/dbyd/jybl/202501/t20250102_123.shtml" title="建">建</a>2025-01-02</li></ul>'
DOCYMD = ('<ul><li><a href="/doc/2026/09/16/4831889.shtml" title="市政府办公室关于印发无锡市治理交通拥堵专项行动方案的通知">'
          '市政府办公室关于印发…</a></li><li><a href="/doc/2025/12/31/4710967.shtml" title="无锡市人民政府关于修改部分规章的决定">'
          '无锡市人民政府…</a></li></ul>')
PAGER = '<div class="page"><a href="index_2.shtml">2</a></div>'
MIXED = DOCYMD + '<a href="/doc/2026/09/16/4831890.html" title="另一个标题文件通知">另一个</a>'


def test_page_ext_tdate_unchanged():
    # The original rule, byte-for-byte: t-date .shtml → .shtml, anything else → .html.
    assert _page_ext(TDATE_HTML, "http://www.mwr.gov.cn/zw/zcfg/fl/") == ".html"
    assert _page_ext(TDATE_SHTML, "https://www.jsrd.gov.cn/dbyd/jybl/") == ".shtml"
    assert _page_ext("", "http://x.gov.cn/a/") == ".html"
    assert _page_ext(None, "http://x.gov.cn/a/") == ".html"


def test_page_ext_override_wins():
    assert _page_ext(TDATE_HTML, "http://x.gov.cn/a/", {"page_ext": ".shtml"}) == ".shtml"
    assert _page_ext(DOCYMD, "http://x.gov.cn/a/", {"page_ext": ".htm"}) == ".htm"


def test_page_ext_pager_href():
    assert _page_ext(PAGER, "http://x.gov.cn/a/index.shtml") == ".shtml"
    assert _page_ext('<a href="/a/index_3.html">3</a>', "http://x.gov.cn/a/") == ".html"
    # t-date rule still outranks a pager href (keeps existing sites identical)
    assert _page_ext(TDATE_SHTML + '<a href="index_2.html">2</a>', "http://x.gov.cn/a/") == ".shtml"


def test_page_ext_from_article_links():
    # 无锡: docymd .shtml links, no t-date link, no server-rendered pager → .shtml
    assert _page_ext(DOCYMD, "https://www.wuxi.gov.cn/zfxxgk/szfxxgkml/fgwjjjd/zfwj/szfwj/index.shtml") == ".shtml"
    # disagreeing extensions → default
    assert _page_ext(MIXED, "https://www.wuxi.gov.cn/a/index.shtml") == ".html"


def test_api_rows():
    payload = {"data": {"totalElements": 57, "totalPages": 12, "page": 1, "size": 5, "data": [
        {"title": "区政府部分副区长工作分工调整的通知", "writeTimeString": "2025-12-16",
         "url": "http://www.wxlx.gov.cn/doc/2025/12/16/4734097.shtml"},
        {"title": "相对路径 &amp; 实体", "writeTimeString": "", "url": "/doc/2016/08/22/2227518.shtml"},
        {"title": "跨站链接", "writeTimeString": "2020-01-01", "url": "http://www.wuxi.gov.cn/doc/2020/01/01/1.shtml"},
        {"title": "", "writeTimeString": "2020-01-01", "url": "/doc/2020/01/01/2.shtml"},
        {"title": "无链接", "writeTimeString": "2020-01-01", "url": ""},
    ]}}
    tp, rows = _api_rows(payload, "http://www.wxlx.gov.cn", "s")
    assert tp == 12
    assert [r["url"] for r in rows] == ["http://www.wxlx.gov.cn/doc/2025/12/16/4734097.shtml",
                                        "http://www.wxlx.gov.cn/doc/2016/08/22/2227518.shtml"]
    assert rows[0]["date"] == "2025-12-16"
    assert rows[1]["date"] == "2016-08-22"          # path-date fallback
    assert rows[1]["title"] == "相对路径 & 实体"
    assert _api_rows({}, "http://x", "s") == (0, [])
    assert _api_rows({"data": {"totalPages": "x", "data": None}}, "http://x", "s") == (0, [])


def test_site_configs():
    assert SITES["wuxi"]["page_ext"] == ".shtml" and SITES["wuxi"]["max_pages"] >= 100
    assert len(SITES["wuxi"]["sections"]) == 9
    wxd = {k: c for k, c in SITES.items() if k.startswith("wxd_")}
    assert len(wxd) == 7
    for k, c in wxd.items():
        assert c["admin_level"] == "district" and c["group"] == "dept", k
        assert c.get("sections") or c.get("api_search"), k
    assert SITES["wxd_jiangyin"]["page_start"] == 3
    # intertid CMS: index.shtml is page 1, index_1.shtml 404s → Scheme B starts at 2
    assert SITES["wuxi"]["page_start"] == 2 and SITES["wxd_yixing"]["page_start"] == 2
    assert SITES["wxd_xinwu"]["max_pages"] * 20 >= 672                    # 规范性 channel depth
    for c in wxd.values():
        if c.get("api_search"):
            assert c["api_search"]["siteId"] and c["api_search"]["channelIds"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all govcms paging tests passed")
