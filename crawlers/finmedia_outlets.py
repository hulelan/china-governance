"""Site registry for the structural outlets added 2026-11-25 (data only).

Imported by crawlers/finmedia.py, which merges OUTLETS into its SITES registry and
owns all the crawl logic; this file holds no behaviour, so it can be read as a
table. Every list surface below was byte-checked from the droplet (NYC IP) on
2026-11-25. Items per publication day, counted from each site's own list pages
that day (URL dates; bjd from its ObjectId timestamps):

    cnr ~45   cctv ~40 (after the `china` filter)   gmw ~40   bjd ~45
    cqn ~10   jschina ~48   chinanews ~140 (cj + gn)   nbd ~110
    sina ~110 kept of ~650   ithome ~14 kept of ~250   rthk ~55
    szhgh ~15   tc609 under 1 a week (21 on-site pages in total)

Rejected surfaces, so nobody re-probes them: finance.sina.com.cn/jjxw/ and
www.chinanews.com(.cn)/cj/ are 403 from the droplet (hence the roll API and the
scroll pages); chinanews' per-channel scroll-news/cj/<date>/news.shtml is 404 /
504; RTHK's news-archive.htm is filled by a service that returns the newest 60
items per category whatever date is asked and NOTHING for any other newsCount;
ITHome's RSS is 60 items (~4.5 h) and its tag pages are editorial (20 items in
33 h for "AI"), so the per-day list is the only complete surface.

Config keys beyond the ones finmedia.py's original seven sites use:

  sections    EVERY list surface, in one list, so scripts/build_section_registry.py
              (which reads `sections` by shape) sees all of them. An entry is:
                str                           one HTML list page
                (template, n[, first])        "{p}" = page number, n pages a
                                              night starting at `first`
                                              (default 1); or "{d}" = a CST
                                              date strftime'd with `daily_fmt`,
                                              n days back from today
                {"kind", "url", "pages",      a JSON / JSONP list API; kinds
                 "filter", "name"}            are implemented in finmedia.FEEDS
              `--pages N` walks N pages / days of each instead (backfill).
  seeds       article URLs no list page links to (a special page), re-offered
              every run and skipped once held.
  filter      True  -> a list item is kept only if its LIST title matches
              POLICY_TITLE_RE. For general firehoses only; see finmedia.py.
  link_re     what to look for in a list page when it differs from art_re
              (bjd's front page carries .json links to the same ids).
  url_sub     (pattern, repl) canonicalisation applied before art_re / dedup.
  title_pats  page-title patterns tried BEFORE the generic og:title/h1/<title>.
  title_strip a trailing " - outlet" suffix the generic splitter does not cut.
  body_cut    (start_re, end_re) on the RAW html: the article container. Without
              it a footer or related-articles rail printed in <p> is stored as
              body (finmedia.cut_html).
  para_drop   a chrome LINE to delete from the extracted body.
  min_body_cjk  per-site floor below which a body is recorded as empty.
  body_js     one-group regex for a body shipped as a JS string literal.
  date_utc    one-group regex for an ISO timestamp the page states in UTC.
  body_re     one-group regex selecting the article container, for a page
              whose prose is not in <p> and whose chrome would win the
              long-line fallback.
  level       sites.admin_level (default 'media').
  nightly_cap new documents per run under --nightly (default 150).
"""
import re

# Allowlist for general firehoses (sina, ithome, cctv `china`). Three families:
# who (regulators and organs), what (instrument and enforcement words), and the
# policy topics this corpus is about. Deliberately NOT bare "AI" / "数据" /
# "标准" / "发布", which on a gadget site match most of the page. Measured
# 2026-11-25 from the droplet: keeps 28 of 502 titles over two IT之家 days
# (5.6%), 109 of the 644 jjxw/china/tech items in 40 Sina roll pages (17%), and
# 21 of ~135 on CCTV's two `china` pages. It is loose on purpose: 起诉 / 判决 let
# through a share of social-news court stories on Sina.
POLICY_TITLE_RE = re.compile(
    r'国务院|中共中央|中央|网信办|工信部|发改委|市场监管|证监会|金融监管|央行|人民银行|财政部|'
    r'商务部|国资委|数据局|科技部|外交部|司法部|公安部|教育部|能源局|海关总署|税务总局|外汇局|'
    r'人大|政协|法院|检察|国家标准|国标|强制性标准|标委会|'
    r'监管|立法|法规|条例|办法》|规定》|意见》|通知》|方案》|规划》|征求意见|政策|新规|'
    r'备案|处罚|罚款|罚单|约谈|整改|立案|通报|问责|下架|封禁|反垄断|垄断|不正当竞争|合规|'
    r'治理|专项行动|专项整治|执法|判决|起诉|诉讼|索赔|侵权|违法|违规|'
    r'出口管制|管制|关税|制裁|实体清单|反制|禁令|审查|许可|牌照|补贴|试点|国产化|自主可控|'
    r'十五五|生成式|人工智能\+|智能体|算力|数据要素|数据跨境|数据安全|个人信息|网络安全|'
    r'未成年人|算法推荐|深度合成|标识|国资|央企|国企'
)

# yicai's "latest" feed is ~500 items a day and 央广财经's 原创 list is mostly
# one-line exchange-announcement flashes; a large share of both is market tickers. A DENYLIST, not an allowlist: every pattern is a market-movement
# shape, so an unanticipated kind of article is kept by default.
TICKER_RE = re.compile(
    r'涨停|跌停|收盘|开盘|收涨|收跌|午评|早盘|午后|尾盘|盘中|盘前|盘后|高开|低开|翻红|翻绿|'
    r'拉升|跳水|走强|走弱|走高|走低|涨超|跌超|涨逾|跌逾|涨近|跌近|涨幅|跌幅|大涨|大跌|异动|'
    r'封板|炸板|连板|净流入|净流出|净买入|净卖出|龙虎榜|成交额|两市|三大指数|主力资金|'
    r'期货主力|主力合约|日内|创新高|创新低|触及|停牌|复牌|解禁|回购|增持|减持|'
    r'业绩预告|互动平台|中间价|逆回购|夜盘|现货黄金|WTI|布伦特|恒指|纳指|道指|标普'
)

OUTLETS = {
    # ------------------------------------------------------------ tier 4
    "cnr": {
        "name": "China National Radio / 央广网",
        "base_url": "https://www.cnr.cn",
        "tier": 4,
        "publisher": "央广网",
        "sections": [
            "https://finance.cnr.cn/ycbd/",
            "https://news.cnr.cn/dj/",
            "https://finance.cnr.cn/",
            "https://tech.cnr.cn/",
            # 10 rows a page; index_1.html is page 2.
            ("https://finance.cnr.cn/ycbd/index_{p}.html", 2),
            ("https://news.cnr.cn/dj/index_{p}.html", 2),
        ],
        "art_re": r'https?://[a-z]+\.cnr\.cn/[A-Za-z0-9/]*?\d{8}/t\d{8}_\d+\.shtml',
        "date_url": r'/t(\d{4})(\d{2})(\d{2})_\d+\.shtml',
        "date_pats": (),
        "title_drop": TICKER_RE,
        "para_drop": r'不尊重原创的行为我们将追究责任',
        "nightly_cap": 80,
    },
    "cctv": {
        "name": "CCTV / 央视网",
        "base_url": "https://news.cctv.com",
        "tier": 4,
        "publisher": "央视网",
        "sections": [
            "https://local.cctv.com/",
            # ~80 items a page, 7 pages (500 items) per channel; one page of
            # law is about 8 days, so one page a night is ample.
            {"kind": "cctv_jsonp", "pages": 1, "name": "法治",
             "url": "https://news.cctv.com/2019/07/gaiban/cmsdatainterface/page/law_{p}.jsonp"},
            {"kind": "cctv_jsonp", "pages": 1, "name": "科技",
             "url": "https://news.cctv.com/2019/07/gaiban/cmsdatainterface/page/tech_{p}.jsonp"},
            {"kind": "cctv_jsonp", "pages": 1, "name": "经济",
             "url": "https://news.cctv.com/2019/07/gaiban/cmsdatainterface/page/economy_zixun_{p}.jsonp"},
            # the general domestic channel: weather, accidents, sport. Filtered.
            {"kind": "cctv_jsonp", "pages": 2, "filter": True, "name": "国内 (title-filtered)",
             "url": "https://news.cctv.com/2019/07/gaiban/cmsdatainterface/page/china_{p}.jsonp"},
        ],
        "art_re": (r'https?://(?:news|local)\.cctv\.com/\d{4}/\d{2}/\d{2}/'
                   r'ARTI[A-Za-z0-9]+\.shtml'),
        "date_url": r'/(\d{4})/(\d{2})/(\d{2})/ARTI',
        "date_pats": (),
        # Two live templates. The 2026 one leaves #content_area EMPTY and ships
        # the text as `var contentdate = '<p>…</p>'` for a script to inject (the
        # cited 网信办备案 article extracted to 0 characters); the older one
        # server-renders it inside #content_area.
        "body_js": r"(?s)var contentdate\s*=\s*'(.*?)'\s*;?\s*\n",
        "body_cut": (r'id="content_area"', r'<div class="(?:bottom_ind01|zebian)"'),
        "nightly_cap": 150,
    },
    "gmw": {
        "name": "Guangming Online / 光明网 (法治·科技·经济频道)",
        "base_url": "https://www.gmw.cn",
        "tier": 4,
        "publisher": "光明网",
        "sections": [
            "https://legal.gmw.cn/",
            "https://legal.gmw.cn/node_9015.htm",
            "https://tech.gmw.cn/",
            "https://economy.gmw.cn/",
        ],
        "art_re": r'https?://(?:legal|tech|economy)\.gmw\.cn/\d{4}-\d{2}/\d{2}/content_\d+\.htm',
        "date_url": r'/(\d{4})-(\d{2})/(\d{2})/content_\d+\.htm',
        "date_pats": (),
        "para_drop": r'^请使用浏览器分享功能进行分享$',
        "body_cut": (r'<!--enpcontent-->', r'<!--/enpcontent-->'),
        "nightly_cap": 80,
    },
    "bjd": {
        "name": "Beijing Daily / 北京日报 (京报网)",
        "base_url": "https://www.bjd.com.cn",
        "tier": 4,
        "publisher": "北京日报",
        "sections": [
            "https://pc.bjd.com.cn/",
            "https://xinwen.bjd.com.cn/redian_std/chuanzhenji",
        ],
        # The Nuxt front page links each story as content/s<id>.json; the reader
        # page is the same id with .html ON THE SAME HOST. The two hosts are NOT
        # mirrors: an xinwen id on rss2 (and the reverse) returns HTTP 200 with a
        # ~110-byte stub, so the host is never rewritten. rss2 carries shared /
        # 北京号 items and is reached when a list links it or a brief cites it.
        "link_re": (r'(?:https?:)?//(?:xinwen|rss2)\.bjd\.com\.cn/content/'
                    r's[0-9a-f]{24}\.(?:html|json)'),
        "url_sub": (r'^(?:https?:)?//(xinwen|rss2)\.bjd\.com\.cn/content/(s[0-9a-f]{24})\.\w+$',
                    r'https://\1.bjd.com.cn/content/\2.html'),
        "art_re": r'https://(?:xinwen|rss2)\.bjd\.com\.cn/content/s[0-9a-f]{24}\.html',
        "date_url": None,
        "date_pats": (),
        # "publishTime":"2026-11-10T13:33:31.480+0000" is UTC.
        "date_utc": r'"publishTime":"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})[.\d]*\+0000',
        "title_pats": (r'<div class="title">\s*([^<]{4,200})',),
        "para_drop": r'北京日报仅提供信息发布平台',
        "nightly_cap": 80,
    },
    "cqn": {
        "name": "China Quality News / 中国质量报 (中国质量新闻网)",
        "base_url": "https://www.cqn.com.cn",
        "tier": 4,
        "publisher": "中国质量报",
        "sections": [
            # NOT the /zj/ landing page: its slider is county-bureau activity
            # blurbs (~90 characters each) from the 中国质量报 local pages.
            "https://www.cqn.com.cn/zj/node_20006.htm",    # 总局动态
            "https://www.cqn.com.cn/zj/node_20164.htm",    # 政策法规
            "https://www.cqn.com.cn/zj/node_20166.htm",    # 标准天地
            "https://www.cqn.com.cn/zj/node_25742.htm",    # 反垄断
            "https://www.cqn.com.cn/zj/node_25784.htm",    # 知识产权
        ],
        "art_re": (r'https?://www\.cqn\.com\.cn/[a-z]+/content/'
                   r'\d{4}-\d{2}/\d{2}/content_\d+\.htm'),
        "date_url": r'/content/(\d{4})-(\d{2})/(\d{2})/content_\d+\.htm',
        "date_pats": (),
        "title_strip": r'\s*-\s*中国质量新闻网$',
        "body_cut": (r'<!--enpcontent-->', r'<!--/enpcontent-->'),
        "nightly_cap": 60,
    },
    "jschina": {
        "name": "China Jiangsu Net / 中国江苏网 (江苏要闻)",
        "base_url": "https://jsnews.jschina.com.cn",
        "tier": 4,
        "publisher": "中国江苏网",
        "sections": ["https://jsnews.jschina.com.cn/jsyw/"],
        "art_re": (r'https?://jsnews\.jschina\.com\.cn/jsyw/\d{6}/'
                   r't\d{8}_s?[0-9a-f]+\.shtml'),
        "date_url": r'/t(\d{4})(\d{2})(\d{2})_s?[0-9a-f]+\.shtml',
        "date_pats": (),
        "nightly_cap": 60,
    },
    "chinanews": {
        "name": "China News Service / 中国新闻网",
        "base_url": "https://www.chinanews.com.cn",
        "tier": 4,
        "publisher": "中国新闻网",
        # /cj/ itself is 403 from the droplet; the scroll pages and /finance/
        # carry the same stories. Channel scoping is the PATH: 财经 and 国内.
        # ~100 items a scroll page across ALL channels, ~47% of them cj/gn, ~140
        # cj/gn items a day: five pages is a day and a half.
        "sections": ["https://www.chinanews.com.cn/finance/",
                     ("https://www.chinanews.com.cn/scroll-news/news{p}.html", 5)],
        "art_re": r'https?://www\.chinanews\.com\.cn/(?:cj|gn)/\d{4}/\d{2}-\d{2}/\d+\.shtml',
        "date_url": r'/(\d{4})/(\d{2})-(\d{2})/\d+\.shtml',
        "date_pats": (),
        # without it every body ended with the right rail's photo headlines
        "body_cut": (r'<!--正文start-->', r'<div class="adEditor"|<!--正文end-->'),
        "nightly_cap": 150,
    },
    # ------------------------------------------------------------ tier 5
    "sina": {
        "name": "Sina Finance / 新浪财经",
        "base_url": "https://finance.sina.com.cn",
        "tier": 5,
        "publisher": "新浪财经",
        # pageid=155&lid=1686 is the finance roll: 50 items per ~30 min. 40 pages
        # is about a day. The channel index pages themselves are 403.
        "sections": [{"kind": "sina_roll", "pages": 40, "filter": True,
                      "name": "财经滚动 (title-filtered)",
                      "url": ("https://feed.mix.sina.com.cn/api/roll/get"
                              "?pageid=155&lid=1686&num=50&page={p}")}],
        "art_re": (r'https?://finance\.sina\.com\.cn/(?:jjxw|china|tech)/'
                   r'\d{4}-\d{2}-\d{2}/doc-[a-z0-9]+\.shtml'),
        "date_url": r'/(\d{4})-(\d{2})-(\d{2})/doc-[a-z0-9]+\.shtml',
        "date_pats": (),
        "body_cut": (r'id="artibody"', r'<!--\s*原始正文end|<!--\s*正文 end'),
        "nightly_cap": 120,
    },
    "ithome": {
        "name": "ITHome / IT之家",
        "base_url": "https://www.ithome.com",
        "tier": 5,
        "publisher": "IT之家",
        # One page per calendar day listing every item: a complete denominator.
        "sections": [("https://www.ithome.com/list/{d}.html", 2)],
        "daily_fmt": "%Y-%m-%d",
        "filter": True,
        "art_re": r'https?://www\.ithome\.com/\d/\d{3}/\d{3}\.htm',
        "date_url": None,
        "date_pats": (r'id="pubtime_baidu">(\d{4})/(\d{1,2})/(\d{1,2})',),
        "title_strip": r'\s*-\s*IT之家$',
        "body_cut": (r'id="paragraph"',
                     r'id="(?:fls|lns|fi)"|class="(?:related_post|newserror|newsReward|shareto)'),
        "nightly_cap": 60,
    },
    "nbd": {
        "name": "National Business Daily / 每日经济新闻",
        "base_url": "https://www.nbd.com.cn",
        "tier": 5,
        "publisher": "每日经济新闻",
        "sections": ["https://www.nbd.com.cn/columns/332/",             # 重磅原创
                     ("https://www.nbd.com.cn/columns/3/page/{p}/", 2)],  # 要闻
        "art_re": r'https?://www\.nbd\.com\.cn/articles/\d{4}-\d{2}-\d{2}/\d+\.html',
        "date_url": r'/articles/(\d{4})-(\d{2})-(\d{2})/\d+\.html',
        "date_pats": (),
        # og:title sits inside a commented-out block carrying ANOTHER article's
        # headline; every probed page came back titled with it.
        "title_pats": (r'(?s)<title>\s*([^<|]{4,200}?)\s*\|',),
        "body_cut": (r'class="g-articl-text"',
                     r'class="(?:u-editor|articleCopyright|u-tips|u-er|u-aticle-tag)"'
                     r'|<!--编辑-->|<!-- copyright -->|<!--评论-->'),
        "para_drop": r'未经许可禁止转载、摘编、复制及镜像',
        "nightly_cap": 130,
    },
    # ------------------------------------------------------------ tier 6
    "rthk": {
        "name": "RTHK / 香港電台 (大中華·財經)",
        "base_url": "https://news.rthk.hk",
        "tier": 6,
        "level": "foreign_media",
        "publisher": "香港電台",
        # cat=2 大中華 (~10/day), cat=5 財經 (~38/day). The service returns the
        # newest 60 and nothing at all for any other newsCount; archive_date is
        # ignored. The two RSS feeds (20 items) are a backstop only.
        "sections": [
            ("https://news.rthk.hk/rthk/webpageCache/services/loadModNewsShowSp2List.php"
             "?lang=zh-TW&cat=2&newsCount=60&dayShiftMode=1&archive_date="),
            ("https://news.rthk.hk/rthk/webpageCache/services/loadModNewsShowSp2List.php"
             "?lang=zh-TW&cat=5&newsCount=60&dayShiftMode=1&archive_date="),
            "https://rthk.hk/rthk/news/rss/c_expressnews_greaterchina.xml",
            "https://rthk.hk/rthk/news/rss/c_expressnews_cfinance.xml",
        ],
        "art_re": r'https?://news\.rthk\.hk/rthk/ch/component/k2/\d+-\d{8}\.htm',
        "date_url": r'/k2/\d+-(\d{4})(\d{2})(\d{2})\.htm',
        "date_pats": (),
        "title_strip": r'\s*-\s*RTHK$',
        "body_re": r'(?is)<div class="itemFullText">(.*?)</div>',
        "min_body_cjk": 40,          # a 財經 flash is two sentences
        "nightly_cap": 100,
    },
    "tc609": {
        "name": "National Data Standardization TC / 全国数据标准化技术委员会 (TC609)",
        "base_url": "https://www.tc609.org.cn",
        "tier": 6,
        # A standards committee under 国家数据局, not a publication. 'central'
        # follows the one precedent in the corpus, tc260 (网安标委).
        "level": "central",
        "genre": "",
        "publisher": "全国数据标准化技术委员会",
        "sections": [
            "https://www.tc609.org.cn/tc609/index.shtml",
            "https://www.tc609.org.cn/tc609/tzgg/zylist.shtml",
            "https://www.tc609.org.cn/tc609/sjxw/zylist.shtml",
            "https://www.tc609.org.cn/tc609/gzzdt/zylist.shtml",
            "https://www.tc609.org.cn/tc609/szyw/zylist.shtml",
            "https://www.tc609.org.cn/tc609/zdwj/zylist.shtml",
            "https://www.tc609.org.cn/tc609/wjzn/zycglist.shtml",
            "https://www.tc609.org.cn/tc609/hydt/hydtList.shtml",
            "https://www.tc609.org.cn/tc609/hygd/list.shtml",
            "https://www.tc609.org.cn/tc609/zjjd/list.shtml",
            "https://www.tc609.org.cn/tc609/gjhz/list.shtml",
        ],
        # Most of the committee's items link OUT to mp.weixin.qq.com, which is
        # not crawled; only the on-site pages are taken. The 标准周 special is
        # linked from no list page, hence a seed.
        "seeds": ["https://www.tc609.org.cn/tc609/standardweek/2026/2026_2nd.shtml"],
        "art_re": (r'https?://www\.tc609\.org\.cn/tc609/(?:[a-z]+/\d{6}/[0-9a-f]{32}'
                   r'|standardweek/\d{4}/\w+)\.shtml'),
        "date_url": None,
        # ONLY the page's own 发布时间. <meta name="PubDate"> and the
        # 页面生成时间 stamp are the CMS regeneration time: an article published
        # 2025-11-13 carries PubDate 2026-04-17. A page without 发布时间 (the 标准周
        # special) stores an empty date.
        "date_pats": (r'<publishtime>\s*(\d{4})-(\d{2})-(\d{2})',),
        "para_drop": (r'版权所有|^地址：北京市东城区安定门东大街1号|^提示：请使用本单位'
                      r'|^\d{4}-\d{2}-\d{2}$'),
        "nightly_cap": 30,
    },
    "szhgh": {
        "name": "Red Song Society / 红歌会网 (评论·自媒体号)",
        "base_url": "https://www.szhgh.com",
        "tier": 6,
        "publisher": "红歌会网",
        "genre": "commentary",
        "sections": ["https://www.szhgh.com/Article/opinion/WeMedia/",
                     "https://www.szhgh.com/Article/opinion/",
                     ("https://www.szhgh.com/Article/opinion/WeMedia/index_{p}.html", 1, 2)],
        "art_re": (r'https?://www\.szhgh\.com/Article/opinion/[A-Za-z]+/'
                   r'\d{4}-\d{2}-\d{2}/\d+\.html'),
        "date_url": r'/(\d{4})-(\d{2})-(\d{2})/\d+\.html',
        "date_pats": (),
        "title_strip": r'(?:\s+-\s+[^-]{2,12})?\s+-\s+红歌会网$',
        "body_cut": (r'<article id="content"', r'</article>|<!-- 文末横幅 -->'),
        "nightly_cap": 40,
    },
}
