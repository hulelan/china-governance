"""URL-date and host-resolution tests for scripts/ingest_urls.py.

Each date case is a real URL from a research brief (21 Oct - 4 Nov 2026), so the
suite pins the actual path shapes rather than invented ones. The negative cases
matter most: an unanchored date regex matches a CDN upload path before it matches
a publication date (measured in crawlers/finmedia.py, where it read 2024-05 off
tmtpost's image URL), so a host with no date in its path MUST return "" rather
than something plausible.
"""
import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "ingest_urls", Path(__file__).resolve().parents[1] / "scripts" / "ingest_urls.py")
iu = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(iu)


DATED = [
    ("https://www.cac.gov.cn/2026-10/23/c_1794509028407372.htm", "2026-10-23"),
    ("https://www.news.cn/info/20261022/549fd856934f4714b7e653056f995ab6/c.html", "2026-10-22"),
    ("http://politics.people.com.cn/n1/2026/1021/c1001-40819103.html", "2026-10-21"),
    ("http://www.npc.gov.cn/npc/c2/kgfb/202610/t20261022_457908.html", "2026-10-22"),
    ("https://www.chinanews.com.cn/gn/2026/10-26/10721172.shtml", "2026-10-26"),
    ("https://www.21jingji.com/article/20261022/herald/c42defbfcc9e0763b774bf07b0504755.html",
     "2026-10-22"),
    ("https://www.govinfo.gov/content/pkg/FR-2026-10-20/html/2026-21447.htm", "2026-10-20"),
    ("https://www.nytimes.com/2026/10/21/world/asia/china-exports-ai-controls.html", "2026-10-21"),
    ("https://www.reuters.com/world/beijing-is-looking-curbing-overseas-access-chinas-top-ai-"
     "models-sources-say-2026-07-07/", "2026-07-07"),
    ("https://cn.wicinternet.org/2026-11/02/content_39081991.htm", "2026-11-02"),
    ("https://www.cnfin.com/zs-lb/detail/20261102/4489723_1.html", "2026-11-02"),
    ("https://finance.eastmoney.com/a/202611063924849165.html", "2026-11-06"),
    ("https://www.chinanews.com.cn/cj/2026/11-06/10727035.shtml", "2026-11-06"),
    ("https://www.news.cn/politics/20261106/2fc9686a51e240aa8127794d28f1d4e1/c.html",
     "2026-11-06"),
    ("https://www.nda.gov.cn/sjj/swdt/sjdt/1031/20261031151459885260005_pc.html", "2026-10-31"),
    ("http://paper.people.com.cn/rmrb/pc/content/202611/03/content_30189012.html", "2026-11-03"),
    ("http://www.ce.cn/xwzx/gnsz/gdxw/202611/t20261103_3281360.shtml", "2026-11-03"),
    ("http://www.nea.gov.cn/20261030/dd2b15f04b92441aa59f839a1a3413ba/c.html", "2026-10-30"),
    ("https://www.guandian.cn/article/20261021/616219.html", "2026-10-21"),
]

UNDATED = [
    "https://www.yicai.com/news/103406781.html",
    "https://www.brecorder.com/news/40446476",
    "https://www.jiemian.com/article/15232185.html",
    "https://www.mofcom.gov.cn/xwfb/xwfyrth/art/2026/art_2f92a22be4324ec6bc566e4ccdb77436.html",
    "https://news.bloomberglaw.com/artificial-intelligence/china-plans-broad-ai-guardrails",
]


@pytest.mark.parametrize("url,want", DATED)
def test_url_date_extracted(url, want):
    assert iu.url_date(url) == want


@pytest.mark.parametrize("url", UNDATED)
def test_undated_host_returns_empty_not_a_guess(url):
    """No date in the path means "", never a plausible-looking wrong date."""
    assert iu.url_date(url) == ""


def test_cdn_style_path_is_not_read_as_a_date():
    """The failure mode finmedia measured: an image path is not a publish date."""
    assert iu.url_date("https://img.example.com/uploads/images/2024/05/202405132352.jpg") == ""


def test_gov_cn_resolves_to_gov_not_a_shenzhen_substring_match():
    """A fuzzy `root in base_url` lookup returned szpsq/sz/stic for www.gov.cn."""
    assert iu.resolve("https://www.gov.cn/zhengce/202610/content_7083930.htm")[0] == "gov"
    assert iu.resolve("https://www.cac.gov.cn/2026-10/23/c_1.htm")[0] == "cac"


def test_foreign_sources_get_their_own_admin_level():
    """`media` folded into non-central overstated sub-national diffusion 8x once.

    Foreign sources must not be able to repeat that one level out.
    """
    for url in ("https://www.reuters.com/x", "https://www.nytimes.com/2026/10/21/a.html",
                "https://www.brecorder.com/news/1", "https://www.govinfo.gov/x"):
        assert iu.resolve(url)[2] == "foreign_media"
    for url in ("https://www.news.cn/x", "https://www.yicai.com/news/1.html"):
        assert iu.resolve(url)[2] == "media"
    assert iu.resolve("https://www.cac.gov.cn/2026-10/23/c_1.htm")[2] == "central"


def test_unmapped_host_is_unresolved_so_the_caller_can_refuse():
    assert iu.resolve("https://totally-unknown-host.example/a") is None


def test_read_urls_dedupes_and_strips_markdown_fences():
    import io, sys
    raw = ("```\nhttps://www.news.cn/a\nhttps://www.news.cn/a\n"
           "not-a-url\n`https://www.cac.gov.cn/b`\n```\n")
    sys.stdin = io.StringIO(raw)
    try:
        got = iu.read_urls(None)
    finally:
        sys.stdin = sys.__stdin__
    assert got == ["https://www.news.cn/a", "https://www.cac.gov.cn/b"]


# --- the ingest path itself, with a fake network -----------------------------
# Added 2026-11-06 with --date. Until now every test here was a pure function,
# so the thing that actually writes a row was never exercised.

_PAGE = (
    "<html><head><title>电信设备进网管理办法</title></head><body>"
    "<p>（2001年5月10日中华人民共和国信息产业部令第11号公布。）</p>"
    "<p>第一条 为了保证公用电信网的安全畅通，加强电信设备进网管理，维护电信用户"
    "和电信业务经营者的合法权益，根据《中华人民共和国电信条例》，制定本办法。</p>"
    "<p>第二条 本办法所称电信设备是指电信终端设备、无线电通信设备和涉及网间互联"
    "的设备，连接在公用电信网末端为用户提供发送和接收信息功能。</p>"
    "</body></html>"
)
_URL = "https://www.gov.cn/zhengce/2022-08/23/content_5722718.htm"


def _ingest_one(tmp_path, monkeypatch, **kw):
    monkeypatch.setattr(iu, "fetch", lambda url, **_: _PAGE)
    conn = iu.init_db(str(tmp_path / "t.db"))
    tally = iu.ingest(conn, [_URL], tag="t", dry_run=False, allow_new=False, **kw)
    row = conn.execute(
        "SELECT date_published, title FROM documents WHERE url=?", (_URL,)
    ).fetchone()
    return tally, row


def test_date_override_is_what_lands_in_the_row(tmp_path, monkeypatch):
    """A 2001 令 reposted by gov.cn in 2022 must not be dated 2022."""
    tally, row = _ingest_one(tmp_path, monkeypatch, date="2001-05-10")
    assert tally["stored"] == 1
    assert row[0] == "2001-05-10"
    assert row[1] == "电信设备进网管理办法"


def test_without_the_override_the_url_date_still_wins(tmp_path, monkeypatch):
    """The override is opt-in: the default path is unchanged."""
    _, row = _ingest_one(tmp_path, monkeypatch)
    assert row[0] == "2022-08-23"
