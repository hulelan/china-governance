"""Site registry for overseas CLAIMS-ONLY sources (tier 7, added 2026-11-25; data only).

WHAT THESE ARE. Overseas Chinese-language outlets that report on Chinese elite
politics, personnel moves and anti-corruption cases, often ahead of (or instead
of) any official announcement: who is "under investigation", who is a protégé of
whom, who is "next to fall". Their reliability is UNEVEN and differs by outlet,
from public broadcasters with editorial standards (BBC, DW, VOA, RFA, 联合早报) to
outlets affiliated with a movement in open conflict with the CCP (大纪元, 新唐人,
看中国), whose elite-politics stories frequently rest on unnamed "insiders".

So they are stored as CLAIMS ATTRIBUTED TO THE OUTLET, never as evidence of a
government act, and are kept out of every government-document count by
structure rather than by convention:

  * sites.admin_level = 'foreign_media' (OUTLETS[k]["level"]), which no
    level-split measure reads as central / sub-national / PRC media, and which
    scripts/build_doc_identity.py treats as a NON-ISSUER site level: a 文号 or an
    issuer named in the text cannot re-level the document to 'central'.
  * data/source_ontology.yaml leaf `media_foreign_claims` (claims_only: true),
    exposed as web.services.ontology.claims_only_sites(); it sits under `media`,
    so "exclude news" drops it too.
  * every stored row carries relation 'claims=outlet_attributed'
    (crawlers.finmedia.crawl, from `claims_only` below).
  * web.services.discourse_vocab.speaker() returns None for them.
  tests/test_claims_sources.py asserts each of these.

Research use: quote a claim as "<outlet> reported that ..."; never count a claim
document as an announcement. Hand- or model-extracted claims go in data/claims/
(schema in data/claims/README.md).

SCOPE. Each outlet is limited to its elite-politics / China-politics channel. Where
an outlet has a DEDICATED elite-politics channel (大纪元 大陆政治, 看中国 中南海 /
大陆时政 / 官场 / 官吏 / 内幕), the channel is taken whole. Where the only China
surface is general China news (VOA 中国, BBC 中国, DW all-Chinese RSS, RFA's
RSS, 新唐人 大陆, 早报 中国, 端 政治), list titles must match ELITE_TITLE_RE (an
allowlist; the run logs `filtered N of M`). Nightly caps are <= 30 per outlet.

Byte-checked from the droplet (NYC IP) on 2026-11-25; body bytes, not status:

    rfa         RSS 171 KB / 39,720 CJK (30 items); /mandarin/zhengzhi/ 155 KB
    voa         /p/6197.html 中国相关新闻 125 KB (26 articles); CJK is &#x entities
    bbc         /zhongwen/topics/ckr7mn6r003t/simp (中国) 200 KB, 24 article links
    dw          rss.dw.com/rdf/rss-chi-all 58 KB, 58 items (rss-chi-chi is 28 bytes)
    secretchina p16/p13/p2/p18/p17626 110-120 KB each, ~120 article links
    epochtimes  /gb/ncid277.htm 大陆政治 65 KB, 75 article links, _2 page works
    ntdtv       /gb/news/china 87 KB, 104 article links, /2 page works
    zaobao      /news/china 164 KB, 48 story links (?page=2 returns page 1)
    theinitium  /tag/politics/rss/ 207 KB, 15 items; articles are PAYWALLED

REJECTED (configured nowhere; do not re-probe without a new reason):

    boxun       博讯. boxun.com and www.boxun.com return 403 with a 5.6 KB
                Cloudflare "Just a moment..." JS challenge from the droplet, RSS
                too. Needs a browser; not crawlable by base.fetch().
    dwnews      多维. www.dwnews.com (every path, incl. /rss) 301s to
                www.hk01.com/?utm_source=dwnews: the outlet now lives inside 香港01,
                a Hong Kong mainstream outlet that is NOT a claims source (it is
                ingested by URL as site `hk01` under media_foreign).
    mingjing    明镜. www.mingjingnews.com is a 9 KB shell whose JS reads
                /rss.php?url=https://6do.world/latest.rss; 6do.world is a Discourse
                FORUM (/t/topic/<id>) whose latest items are poems and essays. No
                elite-politics list surface exists to scope to.
    rfa zhengzhi/?page=N  ignores the page parameter (identical 155,279 bytes).
"""
import re

# Elite politics / personnel / discipline vocabulary, for the general-China
# surfaces only. Loose on purpose: a cap of <= 30 a night bounds the cost of a
# false keep, while a false drop is a claim we never see.
ELITE_TITLE_RE = re.compile(
    r'习近平|李强|赵乐际|王沪宁|蔡奇|丁薛祥|李希|韩正|'
    r'政治局|常委|中央委员|中委|中央全会|[一二三四五六七]中全会|全会|二十大|二十一大|21大|20大|'
    r'北戴河|中南海|高层|核心|接班|继任|权斗|内斗|派系|政争|清洗|整肃|太子党|红二代|官二代|'
    r'中纪委|纪委|监委|巡视|落马|被查|被调查|接受审查|审查调查|双开|开除党籍|留置|'
    r'反腐|腐败|贪腐|贪官|受贿|行贿|判刑|获刑|死缓|无期|秦城|'
    r'免职|撤职|罢免|任免|调任|升任|出任|降级|下台|辞职|失踪|失联|缺席|露面|'
    r'人事|高官|官员|官场|书记|省长|市长|部长|主任|总理|副国级|'
    r'军委|将领|上将|中将|火箭军|国防部长|解放军|军队|政委|司令|'
    r'中共|'
    # Traditional-script forms (端传媒 and some 早报 / RFA headlines are in 繁体).
    r'習近平|趙樂際|王滬寧|蔡奇|丁薛祥|政治局|常委|中央委員|二十一大|北戴河|中南海|高層|接班|權鬥|內鬥|'
    r'派系|清洗|整肅|中紀委|紀委|監委|巡視|落馬|被查|調查|雙開|開除黨籍|留置|反腐|腐敗|貪腐|貪官|'
    r'受賄|行賄|判刑|獲刑|秦城|免職|撤職|罷免|任免|下台|失蹤|失聯|人事|高官|官員|官場|書記|省長|'
    r'市長|部長|總理|軍委|將領|上將|中將|火箭軍|解放軍|軍隊|司令'
)

_UTC_ISO = r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})'

OUTLETS = {
    "rfa": {
        "name": "Radio Free Asia Mandarin / 自由亚洲电台 普通话",
        "base_url": "https://www.rfa.org/mandarin/",
        "tier": 7,
        "level": "foreign_media",
        "claims_only": True,
        "publisher": "自由亚洲电台",
        # <p>-density alone swept up the header nav (its regex also matches <path>/<picture>).
        "body_cut": (r'<article class="b-article-body"', r'</article>'),
        "sections": [
            "https://www.rfa.org/mandarin/zhengzhi/",
            # The whole-service feed, so titled and allowlisted. Its <link>s are on
            # the bare rfa.org host; url_sub puts them on www so dedup holds.
            {"kind": "rss", "url": "https://www.rfa.org/arc/outboundfeeds/mandarin/rss/",
             "pages": 1, "filter": True, "name": "普通话 RSS (title-filtered)"},
        ],
        "url_sub": (r'^https?://rfa\.org/', 'https://www.rfa.org/'),
        "title_keep": ELITE_TITLE_RE,      # for the RSS section only
        "art_re": r'https://www\.rfa\.org/mandarin/[a-z-]+(?:/[a-z-]+)?/\d{4}/\d{2}/\d{2}/[A-Za-z0-9-]+/',
        "date_url": r'/(\d{4})/(\d{2})/(\d{2})/[A-Za-z0-9-]+/$',
        "date_pats": (),
        "nightly_cap": 30,
    },
    "voa": {
        "name": "Voice of America Chinese / 美国之音中文网",
        "base_url": "https://www.voachinese.com",
        "tier": 7,
        "level": "foreign_media",
        "claims_only": True,
        "publisher": "美国之音",
        # 中国相关新闻: mostly US-China relations, so title-filtered.
        "sections": ["https://www.voachinese.com/p/6197.html"],
        "filter": True,
        "title_keep": ELITE_TITLE_RE,
        "art_re": r'https://www\.voachinese\.com/a/[A-Za-z0-9-]+(?:/\d+)?\.html',
        "date_url": None,
        # The page states Beijing time with its offset: datetime="2026-11-25T05:26:54&#x2B;08:00".
        "date_pats": (r'pubdate="pubdate" datetime="(\d{4})-(\d{2})-(\d{2})T',),
        "date_utc": _UTC_ISO,
        "nightly_cap": 30,
    },
    "bbc": {
        "name": "BBC News Chinese / BBC中文",
        "base_url": "https://www.bbc.com/zhongwen/simp",
        "tier": 7,
        "level": "foreign_media",
        "claims_only": True,
        "publisher": "BBC中文",
        "body_cut": (r'<main\b', r'</main>'),
        "para_drop": r'^© \d{4} BBC|^图像来源|^图像加注文字',
        "sections": ["https://www.bbc.com/zhongwen/topics/ckr7mn6r003t/simp"],   # 中国
        "filter": True,
        "title_keep": ELITE_TITLE_RE,
        "art_re": r'https://www\.bbc\.com/zhongwen/articles/[a-z0-9]{10,}/simp',
        "date_url": None,
        "date_pats": (),
        "date_utc": _UTC_ISO,
        "title_strip": r'\s*-\s*BBC News 中文$',
        "nightly_cap": 30,
    },
    "dw": {
        "name": "Deutsche Welle Chinese / 德国之声中文网",
        "base_url": "https://www.dw.com/zh/",
        "tier": 7,
        "level": "foreign_media",
        "claims_only": True,
        "publisher": "德国之声",
        "body_cut": (r'data-tracking-name="rich-text"', r'<footer\b'),
        "para_drop": r'^DW中文有|德国之声版权声明|supports HTML5 video|文中评论及分析仅代表',
        # DW has no China-politics feed (rss-chi-chi is empty), so the all-Chinese
        # RSS through the allowlist.
        "sections": [{"kind": "rss", "url": "https://rss.dw.com/rdf/rss-chi-all",
                      "pages": 1, "filter": True, "name": "中文 RSS (title-filtered)"}],
        "title_keep": ELITE_TITLE_RE,
        "url_sub": (r'\?maca=[^"\'\s<]*$', ''),
        # Article paths are raw Chinese (/zh/<标题>/a-80049070); base.fetch needs
        # them percent-encoded, and the encoded form is the stored, deduped URL.
        "quote_url": True,
        "art_re": r'https://www\.dw\.com/zh/[^\s"\'<>?]+/a-\d+',
        "date_url": None,
        "date_pats": (),
        "date_utc": _UTC_ISO,
        "title_strip": r'\s*[–-]\s*DW\s*[–-].*$',
        "nightly_cap": 30,
    },
    "secretchina": {
        "name": "Kanzhongguo / 看中国 (secretchina)",
        "base_url": "https://www.secretchina.com/news/gb/",
        "tier": 7,
        "level": "foreign_media",
        "claims_only": True,
        "publisher": "看中国",
        "body_cut": (r'class="article_right"', r'来源:看中国|本文短网址|版权所有，任何形式转载'),
        "para_drop": r'禁止建立鏡像網站|严禁建立镜像网站|^\(?图片来源|（圖片來源',
        # Dedicated elite-politics channels, taken whole: 中南海, 大陆时政, 官场,
        # 官吏, 内幕.
        "sections": [
            "https://www.secretchina.com/news/gb/p16.html",
            "https://www.secretchina.com/news/gb/p13.html",
            "https://www.secretchina.com/news/gb/p2.html",
            "https://www.secretchina.com/news/gb/p18.html",
            "https://www.secretchina.com/news/gb/p17626.html",
        ],
        "art_re": r'https://www\.secretchina\.com/news/gb/\d{4}/\d{2}/\d{2}/\d+\.html',
        "date_url": r'/gb/(\d{4})/(\d{2})/(\d{2})/\d+\.html',
        "date_pats": (),
        # og:title is "headline (组图)  -  channel - column [- ...]": 1 to 4 tails.
        "title_strip": r'\s+-\s+.*$',
        "nightly_cap": 30,
    },
    "epochtimes": {
        "name": "The Epoch Times Chinese / 大纪元 (大陆政治)",
        "base_url": "https://www.epochtimes.com/gb/",
        "tier": 7,
        "level": "foreign_media",
        "claims_only": True,
        "publisher": "大纪元",
        "body_cut": (r'class="post_content"', r'<p>责任编辑|class="mt-6 space-y-2'),
        "sections": ["https://www.epochtimes.com/gb/ncid277.htm",            # 大陆政治
                     ("https://www.epochtimes.com/gb/ncid277_{p}.htm", 1, 2)],
        # The URL year is TWO digits (/gb/26/11/23/); extract_date widens it.
        "art_re": r'https://www\.epochtimes\.com/gb/\d{2}/\d{1,2}/\d{1,2}/n\d+\.htm',
        "date_url": r'/gb/(\d{2})/(\d{1,2})/(\d{1,2})/n\d+\.htm',
        "date_pats": (),
        "title_strip": r'\s*\|\s*大纪元.*$',
        "nightly_cap": 30,
    },
    "ntdtv": {
        "name": "New Tang Dynasty TV / 新唐人电视台 (大陆)",
        "base_url": "https://www.ntdtv.com/gb/",
        "tier": 7,
        "level": "foreign_media",
        "claims_only": True,
        "publisher": "新唐人",
        "sections": ["https://www.ntdtv.com/gb/news/china",
                     ("https://www.ntdtv.com/gb/news/china/{p}", 1, 2)],
        "filter": True,
        "title_keep": ELITE_TITLE_RE,
        "art_re": r'https://www\.ntdtv\.com/gb/\d{4}/\d{2}/\d{2}/a\d+\.html',
        "date_url": r'/gb/(\d{4})/(\d{2})/(\d{2})/a\d+\.html',
        "date_pats": (),
        "title_strip": r'\s*\|\s*新唐人.*$',
        "nightly_cap": 30,
    },
    "zaobao": {
        "name": "Lianhe Zaobao / 联合早报 (中国)",
        "base_url": "https://www.zaobao.com.sg/news/china",
        "tier": 7,
        "level": "foreign_media",
        "claims_only": True,
        "publisher": "联合早报",
        "body_cut": (r'<div class="articleBody', r'id="article-widgets"'),
        "sections": ["https://www.zaobao.com.sg/news/china"],
        "filter": True,
        "title_keep": ELITE_TITLE_RE,
        "art_re": r'https://www\.zaobao\.com\.sg/news/china/story\d{8}-\d+',
        "date_url": r'/story(\d{4})(\d{2})(\d{2})-\d+',
        "date_pats": (),
        "title_strip": r'\s*\|\s*联合早报.*$',
        "nightly_cap": 30,
    },
    "theinitium": {
        "name": "Initium Media / 端传媒 (政治; paywalled, teaser only)",
        "base_url": "https://theinitium.com",
        "tier": 7,
        "level": "foreign_media",
        "claims_only": True,
        "paywalled": True,
        "publisher": "端传媒",
        "body_cut": (r'class="ghost-content', r'class="gh-post-upgrade-cta|class="mb-10 pt-6'),
        # Ghost CMS: tag pages render client-side, but each tag has an RSS feed.
        "sections": [{"kind": "rss", "url": "https://theinitium.com/tag/politics/rss/",
                      "pages": 1, "filter": True, "name": "政治 tag RSS (title-filtered)"}],
        "title_keep": ELITE_TITLE_RE,
        "art_re": r'https://theinitium\.com/\d{8}-[a-z0-9-]+/',
        "date_url": r'\.com/(\d{4})(\d{2})(\d{2})-',
        "date_pats": (),
        "title_strip": r'\s*[|｜]\s*端傳媒.*$',
        "min_body_cjk": 40,
        "nightly_cap": 20,
    },
}
