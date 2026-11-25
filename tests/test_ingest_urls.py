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


# --- purge-source hosts (data/purges/officials.json, 2026-11-25) -------------

PURGE_HOSTS = {
    "https://chinadigitaltimes.net/chinese/543552.html": ("cdt", "foreign_media"),
    "https://global.hk01.com/x/60307375/y": ("hk01", "foreign_media"),
    "https://cn.chinadaily.com.cn/a/202601/24/WS697478f6a310942cc499ca5d.html": ("chinadaily", "media"),
    "https://language.chinadaily.com.cn/2013-09/23/content_16986237.htm": ("chinadaily", "media"),
    "https://m.mp.oeeee.com/a/BAAFRD0000202411281029486.html": ("oeeee", "media"),
    "https://news.ifeng.com/c/7fZtSUsPh8Z": ("ifeng", "media"),
    "https://news.sina.cn/2024-06-27/detail-incaemyn6936185.d.html": ("sina", "media"),
    "https://news.sina.com.cn/c/2019-02-21/doc-ihqfskcp7300935.shtml": ("sina", "media"),
    "https://www.bjnews.com.cn/detail/155145467314597.html": ("bjnews", "media"),
    "https://www.court.gov.cn/fabu/xiangqing/14688.html": ("spc", "central"),
    "https://www.rmzxw.com.cn/sy/yw/2014/06/30/345859.shtml": ("rmzxw", "media"),
    "https://www.thepaper.cn/newsDetail_forward_2534652": ("thepaper", "media"),
}


@pytest.mark.parametrize("url,want", PURGE_HOSTS.items())
def test_purge_source_hosts_resolve(url, want):
    got = iu.resolve(url)
    assert (got[0], got[2]) == want


@pytest.mark.parametrize("url,want", [
    ("https://news.sina.cn/2024-06-27/detail-incaemyn6936185.d.html", "2024-06-27"),
    ("https://news.sina.com.cn/o/2012-09-29/051925279306.shtml", "2012-09-29"),
    ("https://www.rmzxw.com.cn/sy/yw/2014/10/23/396884.shtml", "2014-10-23"),
    ("https://language.chinadaily.com.cn/2013-09/23/content_16986237.htm", "2013-09-23"),
    ("https://cn.chinadaily.com.cn/a/202601/24/WS697478f6a310942cc499ca5d.html", "2026-01-24"),
])
def test_purge_source_url_dates(url, want):
    assert iu.url_date(url) == want


def test_every_purge_site_key_has_an_ontology_leaf():
    """Media is explicit-only in the ontology, so a new media key with no leaf
    would be UNRESOLVED and fall out of the exclude-news filter."""
    import yaml
    tree = yaml.safe_load((Path(__file__).resolve().parents[1] / "data" /
                           "source_ontology.yaml").read_text())["tree"]
    keys = set()

    def walk(n):
        keys.update(n.get("site_keys") or [])
        for c in n.get("children") or []:
            walk(c)
    for n in tree:
        walk(n)
    for key, _lvl in PURGE_HOSTS.values():
        assert key in keys, key


def test_site_title_rules_measured_on_live_pages():
    spc = ('<title>权威发布 - 中华人民共和国最高人民法院</title><div class="title">'
           '第十八届中央政治局原委员、重庆市委原书记孙政才受贿案一审公开宣判</div>'
           '<div class="title">相关报道</div>')
    assert iu.site_title(spc, "spc", None).startswith("第十八届中央政治局原委员")
    spc15 = ('<title>权威发布 - 中华人民共和国最高人民法院</title>'
             '<div class="title"><span>周永康一审被判处无期徒刑</span></div>')
    assert iu.site_title(spc15, "spc", None) == "周永康一审被判处无期徒刑"
    rm = '<title>中共中央决定给予徐才厚开除党籍处分——人民政协网</title><h1>首页>要闻要闻</h1>'
    assert iu.site_title(rm, "rmzxw", None) == "中共中央决定给予徐才厚开除党籍处分"
    wap = "<title>人民日报\r\n-\r\n中央军委原委员、原国务委员兼国防部长李尚福受到开除党籍处分</title>"
    assert iu.site_title(wap, "people_rmrb", None) == "中央军委原委员、原国务委员兼国防部长李尚福受到开除党籍处分"


def test_iri_path_is_percent_encoded_for_fetch_only():
    u = "https://global.hk01.com/即时中国/60307375/何卫东等8人被罢免全国人大代表职务"
    enc = iu.iri_to_uri(u)
    assert enc.isascii() and enc.startswith("https://global.hk01.com/%E5%8D%B3")
    assert iu.iri_to_uri("https://www.news.cn/a/b.html?x=1&y=2") == "https://www.news.cn/a/b.html?x=1&y=2"


def test_ingest_does_not_clobber_an_existing_sites_row(tmp_path, monkeypatch):
    """store_site's upsert rewrites sid/tree_json; a one-URL ingest into a
    crawler-owned site must leave them alone."""
    monkeypatch.setattr(iu, "fetch", lambda url, **_: _PAGE)
    conn = iu.init_db(str(tmp_path / "t.db"))
    conn.execute("INSERT INTO sites (site_key, name, base_url, admin_level, sid, tree_json) "
                 "VALUES ('gov','State Council','https://www.gov.cn','central','S1','[1]')")
    conn.commit()
    iu.ingest(conn, [_URL], tag="t", dry_run=False, allow_new=False)
    assert conn.execute(
        "SELECT sid, tree_json FROM sites WHERE site_key='gov'").fetchone() == ("S1", "[1]")
