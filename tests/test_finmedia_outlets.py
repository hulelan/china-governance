"""List-surface, filter and per-site parsing tests for the 2026-11-25 outlets.

Fixtures are trimmed from pages and feeds fetched from the droplet on 2026-11-25
(crawlers/finmedia_outlets.py). The cases that matter most are the ones where
the generic rule returned a clean WRONG answer on a live page: tc609's
<meta PubDate> (a regeneration stamp eight months after the article), nbd's
og:title (another article's headline inside a comment), bjd's UTC timestamp,
and the footers that the <p>-density rule stored as body text.
"""
import sys
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from crawlers import xinhua
from crawlers.finmedia import (
    CST, FEEDS, SITES, _cjk, canon, cut_html, extract_date, extract_title,
    keep_title, links_in, list_pages, parse_article, site_body,
)
from crawlers.finmedia_outlets import OUTLETS, POLICY_TITLE_RE, TICKER_RE

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ingest_urls  # noqa: E402

CN = ("国家广播电视总局近期部署开展新一轮微短剧低俗化同质化专项治理工作，治理期自11月1日起"
      "至12月底，为期两个月。这是今年以来监管部门第三次针对微短剧行业开展专项整治行动。")

# The article each outlet was added for: (site, url as cited, date it must store).
EXAMPLES = [
    ("cnr", "https://finance.cnr.cn/ycbd/20261110/t20261110_527868426.shtml", "2026-11-10"),
    ("cnr", "https://news.cnr.cn/dj/20261111/t20261111_527868869.shtml", "2026-11-11"),
    ("sina", "https://finance.sina.com.cn/jjxw/2026-11-09/doc-iniyauwe3117428.shtml", "2026-11-09"),
    ("gmw", "https://legal.gmw.cn/2026-11/10/content_39094794.htm", "2026-11-10"),
    ("cctv", "https://news.cctv.com/2026/11/20/ARTIHBHk4WuG4IqM14kzOZpb261120.shtml", "2026-11-20"),
    ("cctv", "https://local.cctv.com/2026/11/21/ARTIqbTJbHmLGQOErgdcEUkH261121.shtml", "2026-11-21"),
    ("bjd", "https://xinwen.bjd.com.cn/content/s6b03ea76e4b039a8e2f3f22d.html", None),
    ("bjd", "https://rss2.bjd.com.cn/content/s6af31d2be4b0e42f8f02bf18.html", None),
    ("cqn", "https://www.cqn.com.cn/zj/content/2026-11/13/content_9181157.htm", "2026-11-13"),
    ("ithome", "https://www.ithome.com/1/024/499.htm", None),
    ("nbd", "https://www.nbd.com.cn/articles/2026-11-20/4653473.html", "2026-11-20"),
    ("jschina", "https://jsnews.jschina.com.cn/jsyw/202611/t20261111_s6af3db09e4b03222a070f4e3.shtml",
     "2026-11-11"),
    ("rthk", "https://news.rthk.hk/rthk/ch/component/k2/1879237-20261125.htm", "2026-11-25"),
    ("tc609", "https://www.tc609.org.cn/tc609/standardweek/2026/2026_2nd.shtml", None),
    ("szhgh", "https://www.szhgh.com/Article/opinion/WeMedia/2026-11-25/418177.html", "2026-11-25"),
    ("yicai", "https://www.yicai.com/news/103445417.html", None),
]


# ---------------------------------------------------------------- registry

@pytest.mark.parametrize("site,url,date", EXAMPLES)
def test_the_cited_article_is_an_article_for_its_site(site, url, date):
    """The URL a brief cited must be one the site's own list scan would accept."""
    import re
    cfg = SITES[site]
    assert re.fullmatch(cfg["art_re"], canon(url, cfg)), canon(url, cfg)
    if date:                                   # URL-dated sites need no HTML
        assert extract_date(url, "", cfg) == date


@pytest.mark.parametrize("site,url,date", EXAMPLES)
def test_the_cited_host_is_mapped_and_to_the_same_site(site, url, date):
    """ingest_urls refuses an unmapped host; a host mapped to ANOTHER key would
    split one outlet across two site_keys."""
    got = ingest_urls.resolve(url)
    assert got and got[0] == site


def test_every_outlet_has_an_ontology_leaf_and_a_bounded_nightly():
    tree = yaml.safe_load((ROOT / "data" / "source_ontology.yaml").read_text())
    listed = set()

    def walk(node):
        if isinstance(node, dict):
            listed.update(node.get("site_keys") or [])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(tree)
    for key, cfg in OUTLETS.items():
        assert key in listed, f"{key}: media is explicit-only in the ontology"
        assert 0 < cfg["nightly_cap"] <= 150
        assert list_pages(cfg), f"{key} has no list surface"


def test_levels_keep_jurisdiction_off_the_media_axis():
    assert OUTLETS["rthk"]["level"] == "foreign_media"
    assert ingest_urls.resolve("https://news.rthk.hk/x")[2] == "foreign_media"
    assert OUTLETS["tc609"]["level"] == "central"          # as tc260, not 'media'
    assert all(c.get("level", "media") == "media"
               for k, c in OUTLETS.items() if k not in ("rthk", "tc609"))


def test_a_bare_run_still_means_tiers_one_and_two():
    """Thirteen new sites must not join the default all-sites run by accident."""
    assert all(c["tier"] >= 4 for c in OUTLETS.values())


@pytest.mark.parametrize("host,key", [
    ("jjckb.xinhuanet.com", "jjckb"), ("www.chinanews.com", "chinanews"),
    ("www.tmtpost.com", "tmtpost"), ("www.shanghai.gov.cn", "sh"),
    ("www.fmprc.gov.cn", "mfa"), ("aqygzj.mofcom.gov.cn", "mofcom"),
])
def test_host_aliases_resolve_to_the_site_already_crawled(host, key):
    assert ingest_urls.resolve(f"https://{host}/a/b.html")[0] == key


def test_shanghai_alias_is_not_levelled_central():
    assert ingest_urls.resolve("https://www.shanghai.gov.cn/x")[2] == "provincial"


@pytest.mark.parametrize("url,want", [
    ("https://jsnews.jschina.com.cn/jsyw/202611/t20261111_s6af3db09e4b03222a070f4e3.shtml", "2026-11-11"),
    ("https://news.rthk.hk/rthk/ch/component/k2/1879237-20261125.htm", "2026-11-25"),
    ("https://finance.sina.com.cn/jjxw/2026-11-09/doc-iniyauwe3117428.shtml", "2026-11-09"),
    ("https://www.ithome.com/1/024/499.htm", ""),               # no date in the URL
    ("https://www.tc609.org.cn/tc609/sjxw/202511/5ed01c6b1d3746f880eb80df003966cb.shtml", ""),
])
def test_ingest_url_dates_for_the_new_hosts(url, want):
    assert ingest_urls.url_date(url) == want


# ---------------------------------------------------------------- feeds

def test_cctv_jsonp_is_unwrapped():
    text = ('law({"data":{"total":500,"list":[{"brief":"x","id":"ARTI1","title":"最高法发布典型案例",'
            '"url":"https://news.cctv.com/2026/11/25/ARTIC1oUDxKjGUAUBKiDeBC5261125.shtml"}]}})')
    assert FEEDS["cctv_jsonp"](text) == [
        ("https://news.cctv.com/2026/11/25/ARTIC1oUDxKjGUAUBKiDeBC5261125.shtml", "最高法发布典型案例")]


def test_sina_roll_items_and_the_path_scope():
    """The roll is ~2,000 items a day and mostly /stock/; art_re is the scope."""
    import re
    text = ('{"result":{"status":{"code":0},"total":101132,"data":['
            '{"url":"https:\\/\\/finance.sina.com.cn\\/jjxw\\/2026-11-25\\/doc-inizyehf4228003.shtml",'
            '"title":"财政部等五部门印发《常态化帮扶资金绩效评价办法》","ctime":"1795613670"},'
            '{"url":"https:\\/\\/finance.sina.com.cn\\/stock\\/2026-11-25\\/doc-inizykpv9340191.shtml",'
            '"title":"某股午后涨停","ctime":"1795613671"}]}}')
    items = FEEDS["sina_roll"](text)
    assert len(items) == 2
    kept = [u for u, _ in items if re.fullmatch(SITES["sina"]["art_re"], u)]
    assert kept == ["https://finance.sina.com.cn/jjxw/2026-11-25/doc-inizyehf4228003.shtml"]


def test_sina_roll_with_no_data_is_an_empty_page_not_a_crash():
    assert FEEDS["sina_roll"]('{"result":{"status":{"code":0},"data":null}}') == []


def test_yicai_feed_urls_are_made_absolute():
    text = '[{"NewsID":103454367,"NewsTitle":"城投“退平台”倒计时七个月","url":"/news/103454353.html"}]'
    assert FEEDS["yicai_latest"](text) == [
        ("https://www.yicai.com/news/103454353.html", "城投“退平台”倒计时七个月")]


# ---------------------------------------------------------------- list pages

def test_ithome_daily_list_gives_titles_for_the_filter():
    html = ('<li><a class="t" href="https://www.ithome.com/1/031/894.htm" target="_blank">'
            '黑得深邃：宾利首款纯电 SUV 托卡尔新增纯黑特别版</a></li>'
            '<li><a class="t" href="https://www.ithome.com/1/032/371.htm">网警公开典型案例：'
            '一网民持续发布不实评论，已被行政处罚</a></li>')
    got = links_in(html, "https://www.ithome.com/list/2026-11-24.html", SITES["ithome"])
    assert [u for u, _ in got] == ["https://www.ithome.com/1/031/894.htm",
                                   "https://www.ithome.com/1/032/371.htm"]
    kept = [u for u, t in got if keep_title(t, SITES["ithome"], True)]
    assert kept == ["https://www.ithome.com/1/032/371.htm"]


def test_an_image_link_does_not_hide_the_headline_link():
    """Many list pages link a thumbnail first; the title comes with the second <a>."""
    html = ('<a href="/articles/2026-11-25/4658905.html"><img src="x.jpg"></a>'
            '<a href="/articles/2026-11-25/4658905.html">实控人被立案调查后，子公司回应</a>')
    got = links_in(html, "https://www.nbd.com.cn/columns/3/", SITES["nbd"])
    assert got == [("https://www.nbd.com.cn/articles/2026-11-25/4658905.html",
                    "实控人被立案调查后，子公司回应")]


def test_rss_links_outside_anchors_are_still_found():
    xml = ('<item><title>在岸人民幣創3星期新低</title>'
           '<link>https://news.rthk.hk/rthk/ch/component/k2/1879237-20261125.htm</link></item>')
    got = links_in(xml, "https://rthk.hk/rthk/news/rss/c_expressnews_cfinance.xml", SITES["rthk"])
    assert got == [("https://news.rthk.hk/rthk/ch/component/k2/1879237-20261125.htm", "")]


def test_bjd_json_link_becomes_the_reader_url_but_the_host_is_kept():
    """The Nuxt front page links content/s<id>.json; the reader page is .html.
    The two hosts are NOT mirrors (measured: the other host answers 200 with a
    ~110-byte stub), so rewriting rss2 to xinwen loses the article."""
    html = ('"https://xinwen.bjd.com.cn/content/s6adecb8be4b039a8e2f2ce63.json" '
            '<a href="//xinwen.bjd.com.cn/content/s6adecb8be4b039a8e2f2ce63.html">北京发布新政</a>')
    got = links_in(html, "https://pc.bjd.com.cn/", SITES["bjd"])
    assert got == [("https://xinwen.bjd.com.cn/content/s6adecb8be4b039a8e2f2ce63.html", "北京发布新政")]
    rss2 = "https://rss2.bjd.com.cn/content/s6af31d2be4b0e42f8f02bf18.html"
    assert canon(rss2, SITES["bjd"]) == rss2


def test_chinanews_scope_is_the_finance_and_domestic_paths():
    html = ('<a href="/cj/2026/11-25/10737811.shtml">国家发改委：三峡水运新通道</a>'
            '<a href="/gn/2026/11-24/10737228.shtml">国务院常务会议</a>'
            '<a href="/sh/2026/11-25/10737806.shtml">社会新闻</a>'
            '<a href="/cul/2026/11-25/10737001.shtml">文化</a>')
    got = [u for u, _ in links_in(html, "https://www.chinanews.com.cn/scroll-news/news1.html",
                                  SITES["chinanews"])]
    assert got == ["https://www.chinanews.com.cn/cj/2026/11-25/10737811.shtml",
                   "https://www.chinanews.com.cn/gn/2026/11-24/10737228.shtml"]


def test_tc609_takes_on_site_pages_and_not_the_wechat_links():
    html = ('<a href="/tc609/sjxw/202601/206f7b12a871428db9af72e80b4e4da5.shtml">全体委员会议</a>'
            '<a href="http://mp.weixin.qq.com/s?__biz=MzkzMTU5MDA3OQ==&mid=2247508819">通知</a>'
            '<a href="/tc609/tzgg/zylist.shtml">更多</a>')
    got = [u for u, _ in links_in(html, "https://www.tc609.org.cn/tc609/index.shtml", SITES["tc609"])]
    assert got == ["https://www.tc609.org.cn/tc609/sjxw/202601/206f7b12a871428db9af72e80b4e4da5.shtml"]


def test_list_pages_expand_days_pages_and_feeds():
    today = datetime(2026, 11, 25, 14, 0, tzinfo=CST)
    ith = [u for _, u, _, _ in list_pages(SITES["ithome"], today=today)]
    assert ith == ["https://www.ithome.com/list/2026-11-25.html",
                   "https://www.ithome.com/list/2026-11-24.html"]
    assert all(f for _, _, f, _ in list_pages(SITES["ithome"], today=today))   # filtered
    assert len(list_pages(SITES["sina"])) == 40
    assert len(list_pages(SITES["sina"], pages=3)) == 3                   # --pages wins
    cnr = [u for _, u, _, _ in list_pages(SITES["cnr"])]
    assert "https://finance.cnr.cn/ycbd/index_1.html" in cnr
    # cctv: only the general `china` channel is filtered
    flt = {u.rsplit("/", 1)[1]: f for k, u, f, _ in list_pages(SITES["cctv"]) if k == "cctv_jsonp"}
    assert flt == {"law_1.jsonp": False, "tech_1.jsonp": False,
                   "economy_zixun_1.jsonp": False, "china_1.jsonp": True, "china_2.jsonp": True}


def test_tmtpost_flash_api_pages_by_offset_and_needs_its_header():
    """Without `app-version` the API answers {"result":"ok","data":{}}: a clean
    empty page. That must be an error, not zero flashes."""
    pages = [(u, h) for k, u, _, h in list_pages(SITES["tmtpost"]) if k == "tmtpost_word"]
    assert [u.split("offset=")[1].split("&")[0] for u, _ in pages][:3] == ["0", "40", "80"]
    assert all(h == {"app-version": "web1.0"} for _, h in pages)
    ok = '{"result":"ok","data":[{"guid":"8217750","title":"奥迪中国回应长春工厂产能利用率跌破10%"}]}'
    assert FEEDS["tmtpost_word"](ok) == [
        ("https://www.tmtpost.com/nictation/8217750.html", "奥迪中国回应长春工厂产能利用率跌破10%")]
    with pytest.raises(ValueError):
        FEEDS["tmtpost_word"]('{"result":"ok","data":{}}')


# ---------------------------------------------------------------- title gates

@pytest.mark.parametrize("title", [
    "新一轮微短剧专项治理启动 严查AI“盗脸偷声”等乱象",                        # the sina miss
    "国行 iPad、MacBook 用上“Apple 智能”在望，相关生成式 AI 服务完成备案",     # the ithome miss
    "国家网信办：9—10月新增133款生成式人工智能服务完成备案",
    "财政部等五部门印发《常态化帮扶资金绩效评价办法》",
])
def test_the_cited_headlines_pass_the_policy_allowlist(title):
    assert POLICY_TITLE_RE.search(title)


@pytest.mark.parametrize("title", [
    "黑得深邃：宾利首款纯电 SUV 托卡尔新增纯黑特别版，全球只有 20 台",
    "HKC 神盾 27Q420B 显示器上市：QD Mini LED + Ultrafast IPS，2399 元",
    "某 AI 手机发布：搭载新一代影像传感器",                # bare "AI" must not be enough
])
def test_gadget_headlines_do_not(title):
    assert not POLICY_TITLE_RE.search(title)


def test_an_allowlist_needs_a_title_and_a_denylist_needs_a_match():
    """An untitled list item (image link, RSS) must not slip through an
    allowlist, and must not be dropped by a denylist."""
    assert keep_title("", SITES["ithome"], True) is False
    assert keep_title("", SITES["yicai"], False) is True
    assert keep_title("现货白银日内跌幅扩至3% 报39.62美元/盎司", SITES["cnr"], False) is False
    assert keep_title("城投“退平台”倒计时七个月：隐性债务化解接近尾声", SITES["yicai"], False) is True


def test_the_ticker_denylist_keeps_a_policy_headline_with_a_number_in_it():
    assert not TICKER_RE.search("国家能源局：引导“水风光+绿色算力”互补支撑")
    assert TICKER_RE.search("三大指数集体收跌 两市成交额不足万亿")


# ---------------------------------------------------------------- dates

def test_tc609_pubdate_meta_is_a_regeneration_stamp_and_is_ignored():
    """Live page: 发布时间 2026-01-07, <meta PubDate> 2026-07-09. The generic
    publishdate/META fallback would have stored July."""
    html = ('<meta name="PubDate" content="2026-07-09 15:40:17"/>'
            '<meta name="others" content="页面生成时间 2026-07-09 15:40:17" />'
            '<span class="mr">发布时间：<publishtime>2026-01-07</publishtime></span>')
    url = "https://www.tc609.org.cn/tc609/sjxw/202601/206f7b12a871428db9af72e80b4e4da5.shtml"
    assert extract_date(url, html, SITES["tc609"]) == "2026-01-07"


def test_tc609_page_with_only_a_generation_stamp_stores_no_date():
    """The 标准周 special carries 页面生成时间 and nothing else: empty, not a guess."""
    html = '<meta name="others" content="页面生成时间 2026-11-09 15:26:24" /><p>时间：2026年11月10日8:30</p>'
    url = "https://www.tc609.org.cn/tc609/standardweek/2026/2026_2nd.shtml"
    assert extract_date(url, html, SITES["tc609"]) == ""


def test_ingest_urls_does_not_fall_through_to_the_generic_meta_date(monkeypatch, tmp_path):
    """Same page through ingest_urls: META_DATE's last pattern matches
    '2026-11-09 15:26', which is the stamp. A registry site must store ''."""
    html = ('<html><head><title>2026年第二次“标准周”活动</title>'
            '<meta name="others" content="页面生成时间 2026-11-09 15:26:24" /></head>'
            f'<body><p>{CN}</p><p>{CN}</p></body></html>')
    assert ingest_urls.meta_date(html) == "2026-11-09"            # the trap is real
    monkeypatch.setattr(ingest_urls, "fetch", lambda url, headers=None: html)
    monkeypatch.setattr(ingest_urls, "save_raw_html", lambda *a, **k: "")
    monkeypatch.setattr(ingest_urls.time, "sleep", lambda s: None)
    conn = ingest_urls.init_db(tmp_path / "t.db")
    ingest_urls.ingest(conn, ["https://www.tc609.org.cn/tc609/standardweek/2026/2026_2nd.shtml"],
                       tag="t", dry_run=False, allow_new=False)
    row = conn.execute("SELECT date_published, title FROM documents").fetchone()
    assert row == ("", "2026年第二次“标准周”活动")


def test_bjd_utc_timestamp_rolls_to_the_beijing_day():
    cfg = SITES["bjd"]
    url = "https://xinwen.bjd.com.cn/content/s6af31d2be4b0e42f8f02bf18.html"
    same = '"publishTime":"2026-11-10T13:33:31.480+0000"'
    late = '"publishTime":"2026-11-10T17:30:00.000+0000"'          # 01:30 on the 11th
    assert extract_date(url, same, cfg) == "2026-11-10"
    assert extract_date(url, late, cfg) == "2026-11-11"


def test_ithome_date_comes_from_its_own_marker_with_unpadded_fields():
    html = '<span id="pubtime_baidu">2026/11/9 19:32:07</span><img src="/2019/01/02/a.jpg">'
    assert extract_date("https://www.ithome.com/1/024/499.htm", html, SITES["ithome"]) == "2026-11-09"


# ---------------------------------------------------------------- titles

def test_nbd_title_is_not_the_commented_out_og_title():
    """Every probed nbd page came back titled with ANOTHER article's headline."""
    html = ('<html><head><title>DeepSeek千亿级融资工商变更落定，腾讯、宁德时代并列最大出资方 | 每经网</title>'
            '<!-- <meta property="og:title" content="乐视20亿美元收购美最大智能电视商Vizio" /> -->'
            '</head><body></body></html>')
    assert extract_title(html, SITES["nbd"]) == "DeepSeek千亿级融资工商变更落定，腾讯、宁德时代并列最大出资方"


@pytest.mark.parametrize("site,raw,want", [
    ("cqn", "关于征求《人形机器人 信息安全要求》等2项拟立项强制性国家标准项目意见的通知-中国质量新闻网",
     "关于征求《人形机器人 信息安全要求》等2项拟立项强制性国家标准项目意见的通知"),
    ("ithome", "国行 iPad、MacBook 用上“Apple 智能”在望，相关生成式 AI 服务完成备案 - IT之家",
     "国行 iPad、MacBook 用上“Apple 智能”在望，相关生成式 AI 服务完成备案"),
    ("szhgh", "陈吉宁的坠落 - 自媒体号 - 红歌会网", "陈吉宁的坠落"),
    ("rthk", "在岸人民幣創3星期新低　跌近90點子 - RTHK", "在岸人民幣創3星期新低 跌近90點子"),
    ("tmtpost", "被红果改写的Q3财报季-钛媒体官方网站", "被红果改写的Q3财报季"),
])
def test_outlet_suffixes_are_cut_from_titles(site, raw, want):
    html = f"<html><head><title>{raw}</title></head><body></body></html>"
    assert extract_title(html, SITES[site]) == want


def test_bjd_share_page_has_no_title_tag():
    """rss2.bjd.com.cn pages carry no <title>, og:title or <h1>."""
    html = ('<html><head><meta charset="utf-8"/></head><body>'
            '<div class="title">我国算力总规模居世界第二，加快推进具身智能等领域数据标准制定</div>'
            '</body></html>')
    assert extract_title(html) == ""
    assert extract_title(html, SITES["bjd"]).startswith("我国算力总规模居世界第二")


# ---------------------------------------------------------------- bodies

def test_sina_body_stops_at_the_end_of_the_article_container():
    html = ('<html><body><div class="article" id="artibody"><!-- 行情图end -->'
            f'<p cms-style="font-L">{CN}</p><p>{CN}</p></div><!-- 原始正文end -->'
            '<div class="wx-info"><p>24小时滚动播报最新的财经资讯和视频，更多粉丝福利扫描二维码关注</p></div>'
            '<p>新浪简介|广告服务|About Sina 联系我们|招聘信息|通行证注册</p></body></html>')
    body = site_body(html, SITES["sina"])
    assert body.count(CN[:16]) == 2
    assert "二维码" not in body and "About Sina" not in body


def test_yicai_body_drops_the_share_line_and_the_related_rail():
    html = ('<html><body><p>打开微信，点击底部的“发现”， 使用“扫一扫”即可将网页分享至朋友圈。</p>'
            f'<div class="m-txt"><p>{CN}</p></div><div id="jb_report"></div>'
            '<div class="common"><h2>浑水宣布做空英伟达</h2><p>黄仁勋离任后，这本关于算力的“循环账簿”能否延续、'
            '由谁延续，将成为市场重新定价的关键。</p></div></body></html>')
    body = site_body(html, SITES["yicai"])
    assert body == CN


def test_founder_cms_comment_markers_bound_gmw_and_cqn_bodies():
    html = ('<html><body><p>请使用浏览器分享功能进行分享</p><!--enpcontent-->'
            f'<p>{CN}</p><!--/enpcontent--><div class="block1"><p>'
            '<a href="x">学习贯彻党的二十届五中全会精神 中国共产党第二十届中央委员会第五次全体会议</a></p></div>'
            '</body></html>')
    for site in ("gmw", "cqn"):
        assert site_body(html, SITES[site]) == CN


def test_an_unknown_template_is_not_emptied_by_the_cut():
    """No start marker = a template we have not seen: keep the page whole."""
    html = f"<html><body><p>{CN}</p><p>{CN}</p></body></html>"
    assert cut_html(html, SITES["sina"]) == html
    assert _cjk(site_body(html, SITES["sina"])) > 100


def test_rthk_body_is_br_separated_text_in_one_div():
    html = ('<style>.itemFullText { margin-top:20px; }</style>'
            '<div class="itemFullText">\n在岸人民幣收報6.6736兌1美元，較上日收市價跌88點子，創3星期新低。<br />\n<br />\n'
            '市場人士表示，亞太區股市下跌，避險情緒升溫，人民幣受壓。</div>'
            '<div class="itemRelated"><ul><li>相關新聞：離岸人民幣一度跌穿六算七</li></ul></div>')
    art = parse_article("https://news.rthk.hk/rthk/ch/component/k2/1879237-20261125.htm",
                        "<title>在岸人民幣創3星期新低 - RTHK</title>" + html, SITES["rthk"])
    assert art["date"] == "2026-11-25"
    assert art["body"].split("\n") == ["在岸人民幣收報6.6736兌1美元，較上日收市價跌88點子，創3星期新低。",
                                       "市場人士表示，亞太區股市下跌，避險情緒升溫，人民幣受壓。"]


def test_a_two_sentence_flash_is_a_body_only_where_the_site_says_so():
    """RTHK finance flashes and tmtpost 快讯 run 40-80 CJK; elsewhere that is a
    failed extraction and must stay empty."""
    short = "<html><head><title>某项政策今日正式发布实施</title></head><body><p>" + CN[:60] + "</p></body></html>"
    assert parse_article("https://www.tmtpost.com/nictation/8215338.html", short,
                         SITES["tmtpost"])["body"] != ""
    assert parse_article("https://www.nbd.com.cn/articles/2026-11-20/1.html", short,
                         SITES["nbd"])["body"] == ""


# ---------------------------------------------------------------- xinhua

def test_xinhua_channel_sections_exist_and_general_runs_first():
    """`general` is a homepage scrape with no archive, so a timeout must never
    be what cuts it off; the channels are paginated and can wait a night."""
    keys = list(xinhua.SECTIONS)
    assert keys[0] == "general"
    for k in ("politics", "finance", "info", "legal"):
        assert len(xinhua.SECTIONS[k]["datasource_id"]) == 32


def test_xinhua_explicit_max_new_beats_the_nightly_default():
    assert xinhua.section_cap(None) == xinhua.MAX_NEW_PER_SECTION
    assert xinhua.section_cap(0) == 0                 # the backfill: no cap
    assert xinhua.section_cap(1000) == 1000           # not min(1000, default)


def test_cctv_body_shipped_as_a_js_string_is_recovered():
    """The cited 国家网信办 备案 article: #content_area is empty in the HTML and
    the text is a JS literal, so stripping <script> left 0 characters."""
    para = ("据国家网信办11月20日公告，促进生成式人工智能服务创新发展和规范应用，网信部门会同有关部门"
            "按照《生成式人工智能服务管理暂行办法》要求，持续开展生成式人工智能服务备案工作。")
    html = ("<html><head><title>国家网信办：9—10月新增133款生成式人工智能服务完成备案_新闻频道_央视网(cctv.com)"
            "</title></head><body><script>\n\t\tvar contentdate  = '<p><strong>央视网消息：</strong>"
            + para + "</p><p>" + para + "</p>'\n\t\t</script>"
            '<div class="content_area" id="content_area">\n</div>'
            '<div class="bottom_ind01"><div class="zebian"><span>编辑：及玥</span></div></div>'
            "</body></html>")
    art = parse_article("https://news.cctv.com/2026/11/20/ARTIHBHk4WuG4IqM14kzOZpb261120.shtml",
                        html, SITES["cctv"])
    assert art["title"] == "国家网信办：9—10月新增133款生成式人工智能服务完成备案"
    assert art["body"].count("持续开展生成式人工智能服务备案工作") == 2
    assert "编辑：及玥" not in art["body"]


def test_cctv_server_rendered_template_still_uses_the_container():
    html = ('<html><body><div class="content_area" id="content_area"><p>' + CN + "</p><p>" + CN
            + '</p></div><div class="bottom_ind01"><div class="zebian"><span>编辑：某某 责任编辑：某某某，'
            '本文版权归央视网所有，未经授权不得转载。</span></div></div></body></html>')
    body = site_body(html, SITES["cctv"])
    assert body.count(CN[:16]) == 2 and "责任编辑" not in body


def test_tmtpost_flash_template_has_its_own_container_and_date():
    """/nictation/ pages have no <article>: the first run stored the licence
    footer as the body and no date."""
    html = ('<html><head><meta property="og:title" content="创业板指涨逾4%，上涨个股近5000只"></head><body>'
            '<h3>创业板指涨逾4%，上涨个股近5000只</h3><div class="read_num" data-v-e9>2026.11.24 09:38 </div>'
            '<div class="word_main_detail" data-v-e9>钛媒体App 11月24日，指数走强，创业板指拉升涨逾4%，沪指涨1.13%，'
            '深成指涨2.47%。算力硬件、半导体芯片、机器人等方向涨幅居前，沪深京三市上涨个股近5000只。</div>'
            '<p>违法和不良信息：010-53519786 举报邮箱：jubao@tmtpost.com 网上有害信息举报专区</p>'
            '<p>广播电视节目制作经营许可证：(京 ) 字第 33215号 增值电信业务经营许可证</p></body></html>')
    art = parse_article("https://www.tmtpost.com/nictation/8215338.html", html, SITES["tmtpost"])
    assert art["date"] == "2026-11-24"
    assert art["body"].startswith("钛媒体App 11月24日") and "许可证" not in art["body"]


def test_chinanews_body_stops_before_the_photo_rail():
    html = ('<html><body><!--正文start--><div class="left_zw"><p>' + CN + '</p></div>'
            '<div class="adEditor">【编辑:某某】</div><div class="right_ph_wrapper">'
            '<p>辽宁锦州：话里带着“问号”，生活里都是热</p><p>云南保山匠人巧手刻出南红新图景</p></div>'
            '</body></html>')
    assert site_body(html, SITES["chinanews"]) == CN
