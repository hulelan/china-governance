"""Parsing tests for crawlers/theory.py, on fixture HTML cut from the live pages
(probed from the droplet 2026-11-12). Literal expected titles and dates."""
from datetime import date

from crawlers import theory as T


# ── 《求是》 / 《红旗文稿》 ──────────────────────────────────────────────

QS_NEW = """<div class="inner" style="padding-top:50px;" data="x" datatype="content">
<h1>深入挖掘人工智能驱动的生产率增长潜力</h1> <h2> </h2>
<span class="appellation"> 来源：《求是》2026/21 </span>
<span class="appellation"> 作者：杨汝岱 </span>
<span class="pubtime"> 2026-11-03 09:00:00 </span>
<div class="text"><div id="detail" class="clipboard_text"><div id="detailContent" class="highlight">
<p style="text-align: center;"><strong>深入挖掘人工智能驱动的生产率增长潜力</strong></p>
<p>&emsp;&emsp;生产率是衡量经济发展质量和效益的重要指标，在经济增长中居于基础性地位。回顾世界经济发展史，大国经济的持续繁荣，靠的不是要素投入的规模扩张，而是生产率的不断提升。</p>
<p>&emsp;&emsp;<strong>一、人工智能技术潜力不会自动转化为生产率增长</strong></p>
</div></div></div>
<div class="xl_ewm hidden-xs"><div class="text">扫描二维码分享到手机</div></div>"""

QS_OLD = """<div class="inner"> <h1> 聚焦推动高质量发展 加快发展新质生产力 </h1>
<span class="appellation"> 来源：《求是》2024/09 </span> <span class="appellation"> 作者：张来明 </span>
<span class="pubtime"> 2024-05-01 09:00:00 </span>
<div class="clipboard_text"> <div class="highlight"> <p> 2023年，习近平总书记在地方考察期间提出“新质生产力”。</p></div></div>"""

HQ = """<h1>长征的历史从未远去</h1>
<span class="appellation"> 来源：《红旗文稿》2026/20 </span>
<span class="appellation"> 作者：军事科学院军队政治工作研究院 </span>
<span class="pubtime"> 2026-10-27 09:00:00 </span>
<div class="highlight"><p>2026年10月22日，习近平总书记在纪念中国工农红军长征胜利90周年大会上发表重要讲话。</p>
<p>责任编辑：杨绍华</p></div><div class="xl_ewm"></div>"""


def test_qs_cover_date_rule():
    assert T.qs_cover_date(2024, 9) == "2024-05-01"
    assert T.qs_cover_date(2024, 10) == "2024-05-16"
    assert T.qs_cover_date(2026, 21) == "2026-11-01"
    assert T.qs_cover_date(2019, 24) == "2019-12-16"
    assert T.qs_cover_date(2019, 25) == ""          # no 25th issue: refuse, do not guess


def test_qiushi_new_template_uses_cover_date_not_pubtime():
    r = T.parse_qs_article(QS_NEW, T.SITES["qiushi"])
    assert r["title"] == "深入挖掘人工智能驱动的生产率增长潜力"
    assert r["issue"] == "2026/21"
    assert r["date"] == "2026-11-01"                # NOT the 2026-11-03 web posting
    assert r["author"] == "杨汝岱"
    assert r["body"].startswith("深入挖掘人工智能驱动的生产率增长潜力\n生产率是衡量")
    assert "扫描二维码" not in r["body"] and "<" not in r["body"]


def test_qiushi_old_template():
    r = T.parse_qs_article(QS_OLD, T.SITES["qiushi"])
    assert r["title"] == "聚焦推动高质量发展 加快发展新质生产力"
    assert r["date"] == "2024-05-01"
    assert r["issue"] == "2024/09"


def test_hongqi_uses_pubtime_and_drops_editor_line():
    r = T.parse_qs_article(HQ, T.SITES["hongqi"])
    assert r["title"] == "长征的历史从未远去"
    assert r["date"] == "2026-10-27"
    assert r["issue"] == "2026/20"
    assert "责任编辑" not in r["body"]


def test_canon_qs_matches_existing_qstheory_spelling():
    assert (T.canon_qs("https://www.qstheory.cn/20261102/abc/c.html")
            == "http://www.qstheory.cn/20261102/abc/c.html")
    assert (T.canon_qs("//www.qstheory.cn/dukan/qs/2024-05/01/c_1130136075.htm")
            == "http://www.qstheory.cn/dukan/qs/2024-05/01/c_1130136075.htm")


# ── 学习时报网 / 中国社会科学网 (TRS) ───────────────────────────────────

ST = """<title>学习时报网_用严明的纪律管党治党
  </title>
<div class="font_36"> 用严明的纪律管党治党 </div>
<td width="300" style="padding-top:5px;">来源：学习时报 &nbsp;&nbsp;&nbsp;&nbsp;杨明 &nbsp;&nbsp;&nbsp;&nbsp;2026-11-11 08:34 </td>
<div class="dzxmain clearfix" > <div id="detail"> <div class=TRS_Editor><div class="Custom_UnionStyle">
<p style="text-align: justify;"> 加强纪律建设是全面从严治党的治本之策。纪律严明是马克思主义政党的鲜明特质，也是我们党的光荣传统和独特优势。</p>
<p style="text-align: right;"><font size="2">（责编：常滨海）</font></p> </div></div> </div> </div>
<div class="xian_gray font_12 gray"> 【版权声明】凡来源学习时报网的内容，其版权均属中央党校报刊社所有。</div>"""

CSSN = """<h1 class="qt_article_title">停顿、加速与数字时代的资本逻辑</h1>
<div class="intro_left"> <span class="qt_published_date">2026-09-17</span>
<span class="qt_article_author"><font>作者：</font>董键铭</span>
<span class="qt_article_source"><font>来源：</font>中国社会科学网-中国社会科学报</span> </div>
<div class="content_center"> <div class=TRS_Editor><div> 当今时代，以人工智能为代表的数字技术的快速发展，在给人类社会带来前所未有的发展与变化的同时，也造成了一系列新的社会问题。</div>
<div> <b>（作者系中国社会科学院哲学研究所副研究员）</b></div></div> </div>
<div class="content_zz"> 【编辑：罗浩（报纸）王晏清（网络）】 </div>
<div class="warp_center_links clear"><ul><li><a href="https://www.cssn.cn/skgz/x.shtml">跨学科聚焦人工智能多领域应用</a></li></ul></div>"""


def test_studytimes_article():
    url = "https://www.studytimes.cn/llsd/202611/t20261111_94244.html"
    r = T.parse_trs_article(ST, url, T.SITES["studytimes"])
    assert r["title"] == "用严明的纪律管党治党"
    assert r["date"] == "2026-11-11"
    assert r["source"] == "学习时报"
    assert r["body"] == ("加强纪律建设是全面从严治党的治本之策。纪律严明是马克思主义政党的鲜明特质，"
                         "也是我们党的光荣传统和独特优势。")


def test_cssn_article_stops_before_editor_and_related_links():
    url = "https://www.cssn.cn/skgz/bwyc/202609/t20260917_6067628.shtml"
    r = T.parse_trs_article(CSSN, url, T.SITES["cssn"])
    assert r["title"] == "停顿、加速与数字时代的资本逻辑"
    assert r["date"] == "2026-09-17"
    assert r["source"] == "中国社会科学网-中国社会科学报"
    assert r["author"] == "董键铭"
    assert r["body"].endswith("（作者系中国社会科学院哲学研究所副研究员）")
    assert "编辑：罗浩" not in r["body"] and "跨学科聚焦" not in r["body"]


# ── 光明日报 e-paper ────────────────────────────────────────────────────

GMW_INDEX_OLD = """<a href=nbs.D110000gmrb_01.htm>第01版：头版</a>
<a href=nbs.D110000gmrb_11.htm>第11版：理论·国家社科基金</a>
<a href=nbs.D110000gmrb_12.htm>第12版：国际新闻</a>
<a href=nbs.D110000gmrb_09.htm>第09版：两会特刊</a>"""

GMW_INDEX_NEW = """<a href="node_04.html">第04版：综合新闻</a>
<a href="node_11.html">第11版：理论</a>
<a href="node_06.html">第06版：学习贯彻习近平新时代中国特色社会主义思想专刊</a>
<a href="node_13.html">第13版：光明文化周末·文荟</a>"""

GMW_ART_OLD = """<script>
		//content=content.replace("<!--enpcontent-->","");
		//content=content.replace("<!--/enpcontent-->","");
</script>
<h3></h3> <h1>“中”与“中和”理念的考古学阐释</h1> <h2></h2>
<div class="lai"> <span>作者：刘庆柱</span> <b>《光明日报》（ 2021年01月13日&nbsp;11版）</b></div>
<div id="articleContent"> <!--enpcontent--><P>&nbsp;&nbsp;&nbsp;&nbsp;从20世纪90年代开始，中国考古学界聚焦一些重大历史课题，如开展“中国古代文明形成”的讨论。</P><!--/enpcontent--></div>"""


def test_gmw_index_dialects_keep_only_theory_pages():
    old = T.gmw_pages(GMW_INDEX_OLD, date(2021, 1, 13))
    assert old == [("https://epaper.gmw.cn/gmrb/html/2021-01/13/nbs.D110000gmrb_11.htm",
                    "理论·国家社科基金")]
    new = T.gmw_pages(GMW_INDEX_NEW, date(2026, 11, 13))
    assert [n for _, n in new] == ["理论", "学习贯彻习近平新时代中国特色社会主义思想专刊"]
    assert new[0][0] == "https://epaper.gmw.cn/gmrb/html/layout/202611/13/node_11.html"
    assert T.gmw_index_url(date(2025, 12, 31)).endswith("2025-12/31/nbs.D110000gmrb_01.htm")
    assert T.gmw_index_url(date(2026, 1, 1)).endswith("layout/202601/01/node_01.html")


def test_gmw_article_links_both_dialects():
    page_old = ('<Area href="nw.D110000gmrb_20210113_1-11.htm"><a href=nw.D110000gmrb_20210113_1-11.htm>x</a>'
                '<a href=nw.D110000gmrb_20210113_2-11.htm>y</a>')
    assert T.gmw_articles(page_old, "https://epaper.gmw.cn/gmrb/html/2021-01/13/nbs.D110000gmrb_11.htm",
                          date(2021, 1, 13)) == [
        "https://epaper.gmw.cn/gmrb/html/2021-01/13/nw.D110000gmrb_20210113_1-11.htm",
        "https://epaper.gmw.cn/gmrb/html/2021-01/13/nw.D110000gmrb_20210113_2-11.htm"]
    page_new = '<a href="../../../content/202611/13/content_30137.html">'
    assert T.gmw_articles(page_new, "https://epaper.gmw.cn/gmrb/html/layout/202611/13/node_11.html",
                          date(2026, 11, 13)) == [
        "https://epaper.gmw.cn/gmrb/html/content/202611/13/content_30137.html"]


def test_gmw_old_article_skips_markers_inside_js_string():
    r = T.parse_gmw_article(GMW_ART_OLD)
    assert r["title"] == "“中”与“中和”理念的考古学阐释"
    assert r["author"] == "刘庆柱"
    assert r["body"].startswith("从20世纪90年代开始，中国考古学界")


# ── 人民论坛 ───────────────────────────────────────────────────────────

RMLT = """<h1 class="article-title">增强宏观政策取向一致性和有效性</h1>
<div class="article-infos ov"> <span class="date">2026-10-14 10:24</span> 来源：
<span class="source"> <a href="http://www.ce.cn/x.shtml" target="_blank">中国经济网-《经济日报》</a> </span>
作者： <span class="editors">张友国</span> </div>
<div class="article-content fontSizeSmall BSHARE_POP"> <p>有效的宏观政策、精准的宏观调控，是护航我国经济行稳致远的重要手段。习近平总书记明确提出，注重各方面政策协调。</p>
<p>声明：本文为人民论坛杂志社原创内容，任何单位或个人转载请回复本微信号获得授权。</p>
</div><!-- @end 文章内容 --> <div class="editor"> <span>[责任编辑：银冰瑶]</span> </div>"""


def test_rmlt_article():
    r = T.parse_rmlt_article(RMLT, "https://www.rmlt.com.cn/2026/1014/756963.shtml")
    assert r["title"] == "增强宏观政策取向一致性和有效性"
    assert r["date"] == "2026-10-14"
    assert r["author"] == "张友国"
    assert r["source"] == "中国经济网-《经济日报》"
    assert r["body"] == "有效的宏观政策、精准的宏观调控，是护航我国经济行稳致远的重要手段。习近平总书记明确提出，注重各方面政策协调。"


def test_footer_titles_are_rejected():
    for t in ("互联网新闻信息服务许可证", "网络服务出版许可证", "联系我们", "版权声明", "10120170047", "(署)网出证(京)字第323号"):
        assert T.FOOTER_TITLE_RE.search(t), t
    for t in ("用严明的纪律管党治党", "国际关系学和区域国别学的融合与创新", "AI时代公众信任心态的生成机制"):
        assert not T.FOOTER_TITLE_RE.search(t), t


def test_qs_url_date_fallback():
    assert T.qs_url_date("http://www.qstheory.cn/dukan/hqwg/2024-07/27/c_1130185879.htm") == "2024-07-27"
    assert T.qs_url_date("http://www.qstheory.cn/20261027/5d2bc062bcd8450da3d987f974e75dd4/c.html") == "2026-10-27"
    assert T.qs_url_date("http://www.qstheory.cn/qs/mulu.htm") == ""


# ── 爱思想 ─────────────────────────────────────────────────────────────────

ASX = """<div class="show_text"><div style="padding: 30px 10px 20px 10px">
          <h3>郑功成：“十五五”时期的社会保障改革：问题清单与制度优化</h3>
          <div class="info">选择字号：<a href="#">大</a>
            &nbsp; 本文共阅读 25665 次 更新时间：2026-05-11 00:22
          </div></div>
        <div class="about"><div style="padding: 0px 20px"><p align="right">进入专题：
                  <a href="/zhuanti/795.html"><u>十五五</u></a>&nbsp;
                  <a href="/zhuanti/841.html"><u>社会保障</u></a>&nbsp;</p>
            <div>●
                <strong>郑功成</strong>
                  (<a href="/thinktank/ZhengGongcheng.html"><u>进入专栏</u></a>)</div></div>
          <div style="padding: 25px"><div id="content"><div id="content2">
                <div class="article-content">
<p>摘要：健全的社会保障体系是国家现代化的“标配”，中国式现代化更需要通过高质量的社会保障制度促进社会平等、走向共同富裕。</p>
<div class="note"><p>第一，实现了社会保障制度整体转型。</p></div>
<p> </p>
<p>郑功成，中国人民大学中国社会保障研究中心教授</p>
<p>摘自：《社会科学》2025年第12期</p>
                </div></div>
            进入 <a href="/thinktank/ZhengGongcheng.html">郑功成</a> 的专栏 进入专题：十五五
            <p>本文责编：<u>SuperAdmin</u></br>发信站：爱思想（https://www.aisixiang.com）"""

ASX_GONE = """<html><head><title>提示信息_爱思想</title></head>
<body><div class="tips">该文章不存在或已被删除</div></body></html>"""


def test_asx_article():
    r = T.parse_asx_article(ASX)
    assert r["title"] == "“十五五”时期的社会保障改革：问题清单与制度优化"
    assert r["author"] == "郑功成"
    assert r["date"] == "2026-05-11"
    assert r["origin"] == "《社会科学》2025年第12期"
    assert r["topics"] == ["十五五", "社会保障"]
    assert r["body"].startswith("摘要：健全的社会保障体系")
    assert "第一，实现了社会保障制度整体转型。" in r["body"]   # a nested div does not end the body
    assert r["body"].endswith("摘自：《社会科学》2025年第12期")
    assert "进入专题" not in r["body"] and "本文责编" not in r["body"]


def test_asx_origin_shapes():
    for line, want in [("转自：《江淮论坛》2026年第3期", "《江淮论坛》2026年第3期"),
                       ("《 人民日报 》（ 2026年06月18日 09 版）", "《人民日报》（2026年06月18日09版）")]:
        html = ASX.replace("<p>摘自：《社会科学》2025年第12期</p>", f"<p>{line}</p>")
        assert T.parse_asx_article(html)["origin"] == want
    html = ASX.replace("<p>摘自：《社会科学》2025年第12期</p>", "")
    assert T.parse_asx_article(html)["origin"] == ""


def test_asx_topics_printed_twice_are_kept_once():
    html = ASX + '<a href="/zhuanti/795.html"><u>十五五</u></a>'
    assert T.parse_asx_article(html)["topics"] == ["十五五", "社会保障"]


def test_asx_soft_404_is_gone_not_failed():
    r = T.parse_asx_article(ASX_GONE)
    assert r["gone"] is True and r["title"] == ""


def test_asx_title_keeps_colon_when_prefix_is_not_the_author():
    html = ASX.replace("<strong>郑功成</strong>", "<strong>张三</strong>")
    assert T.parse_asx_article(html)["title"].startswith("郑功成：")


def test_fetch_paced_waits_out_a_429_and_retries_the_same_url(monkeypatch):
    import urllib.error
    calls, slept = [], []

    def fake_fetch(url, headers=None, retries=3):
        calls.append((url, retries))
        if len(calls) == 1:
            raise urllib.error.HTTPError(url, 429, "Too Many Requests", None, None)
        return "<h3>ok</h3>"
    monkeypatch.setattr(T, "fetch", fake_fetch)
    monkeypatch.setattr(T.time, "sleep", slept.append)
    cfg = T.SITES["aisixiang"]
    assert T.fetch_paced("https://x/data/1.html", cfg) == "<h3>ok</h3>"
    assert calls == [("https://x/data/1.html", 1)] * 2      # one quick try each, same URL
    assert slept == [90]


def test_fetch_paced_does_not_cool_down_a_404(monkeypatch):
    import urllib.error
    import pytest

    def fake_fetch(url, headers=None, retries=3):
        raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
    monkeypatch.setattr(T, "fetch", fake_fetch)
    monkeypatch.setattr(T.time, "sleep", lambda s: pytest.fail("slept on a 404"))
    with pytest.raises(urllib.error.HTTPError):
        T.fetch_paced("https://x/data/1.html", T.SITES["aisixiang"])
