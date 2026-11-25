"""Overseas CLAIMS-ONLY sources (finmedia tier 7, crawlers/claims_outlets.py).

The core requirement is STRUCTURAL: an RFA / 大纪元 / 看中国 article about who is
"under investigation" must never be counted as a government document, whatever its
text contains. These tests pin every layer that keeps it out:

  registry   tier 7, admin_level 'foreign_media', claims_only, cap <= 30
  storage    relation 'claims=outlet_attributed' on every stored row
  ontology   leaf media_foreign_claims (claims_only: true), under `media`, so
             "exclude news" drops it; claims_only_sites() for the analysis layer
  identity   build_doc_identity treats foreign_media as a NON-ISSUER site level:
             a central organ in the title cannot re-level the document to central
             (it did before 2026-11-25), its genre is always news, and its rank is
             below every other level so it never becomes an instrument's canonical
  web        source_type='government' excludes foreign_media (it did not)
  discourse  speaker() is None, i.e. no speaker bucket, PRC media or government

Article fixtures (tests/fixtures_claims/articles.json) are trimmed from pages
fetched from the droplet on 2026-11-25: the page's title/date metadata, a nav
paragraph that must NOT be stored, the body container's first paragraphs and the
footer after its end marker.
"""
import asyncio
import json
import re
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from crawlers import finmedia  # noqa: E402
from crawlers.claims_outlets import ELITE_TITLE_RE, OUTLETS as CLAIMS  # noqa: E402
from crawlers.finmedia import (  # noqa: E402
    CLAIMS_RELATION, FEEDS, SITES, canon, extract_date, keep_title, links_in,
    list_pages, parse_article, relation_for,
)
from web.services import ontology  # noqa: E402
from web.services.discourse_vocab import SPEAKERS, speaker  # noqa: E402
import build_doc_identity as BDI  # noqa: E402

FIX = json.loads((ROOT / "tests/fixtures_claims/articles.json").read_text())
KEYS = sorted(CLAIMS)


# ------------------------------------------------------------------ registry

@pytest.mark.parametrize("k", KEYS)
def test_registry_entry_is_claims_only_foreign_media(k):
    cfg = SITES[k]
    assert cfg is CLAIMS[k]
    assert cfg["tier"] == 7
    assert cfg["level"] == "foreign_media"
    assert cfg["claims_only"] is True
    assert 1 <= cfg["nightly_cap"] <= 30
    assert cfg["sections"], k


def test_claims_keys_do_not_shadow_another_site():
    from crawlers.finmedia_outlets import OUTLETS
    other = set(OUTLETS) | {k for k, c in SITES.items() if not c.get("claims_only")}
    assert not set(CLAIMS) & set(OUTLETS)
    assert {k for k, c in SITES.items() if c.get("claims_only")} == set(CLAIMS)
    assert not (set(CLAIMS) & (other - set(CLAIMS)))


def test_a_bare_run_still_means_tiers_1_and_2():
    src = (ROOT / "crawlers/finmedia.py").read_text()
    assert 'c["tier"] in (1, 2)' in src


# ------------------------------------------------------------------ storage

@pytest.mark.parametrize("k", KEYS)
def test_every_stored_row_is_tagged_as_a_claim(k):
    assert CLAIMS_RELATION in relation_for(SITES[k]).split(";")


def test_paywalled_claims_site_carries_both_tags():
    assert relation_for(SITES["theinitium"]) == "body=paywall_teaser;" + CLAIMS_RELATION
    assert relation_for(SITES["caixin"]) == "body=paywall_teaser"    # unchanged
    assert relation_for(SITES["ce"]) == ""                           # unchanged


# ------------------------------------------------------------------ ontology

def _yaml_leaf(node_id):
    raw = yaml.safe_load((ROOT / "data/source_ontology.yaml").read_text())

    def walk(nodes):
        for n in nodes:
            if n["id"] == node_id:
                return n
            got = walk(n.get("children") or [])
            if got:
                return got
    return walk(raw["tree"])


def test_ontology_leaf_lists_exactly_the_registry():
    leaf = _yaml_leaf("media_foreign_claims")
    assert leaf["claims_only"] is True
    assert sorted(leaf["site_keys"]) == KEYS
    assert ontology.claims_only_sites() == KEYS
    assert ontology.claims_only_leaves() == ["media_foreign_claims"]


@pytest.mark.parametrize("k", KEYS)
def test_claims_site_is_news_never_government(k):
    assert ontology.site_to_type(k, "foreign_media") == "media_foreign_claims"
    assert ontology.is_under(k, "media", "foreign_media")
    for gov in ("central", "local", "research"):
        assert not ontology.is_under(k, gov, "foreign_media"), gov
    assert ontology.is_claims_only(k)


def test_exclude_news_drops_claims_sites():
    live = [{"site_key": k, "admin_level": "foreign_media"} for k in KEYS] + [
        {"site_key": "gov", "admin_level": "central"},
        {"site_key": "xinhua", "admin_level": "media"},
    ]
    kept = set(ontology.sites_excluding("media", all_site_keys=live))
    assert kept == {"gov"}


def test_ordinary_foreign_media_is_not_claims_only():
    assert not ontology.is_claims_only("rthk")
    assert ontology.site_to_type("rthk", "foreign_media") == "media_foreign"


# ------------------------------------------------------------------ identity

def test_foreign_media_is_a_non_issuer_site_level():
    assert "foreign_media" in BDI.NON_ISSUER_SITE_LEVELS
    assert "foreign_media" in BDI.LEVELS


@pytest.mark.parametrize("title", [
    "中共中央纪律检查委员会关于孟宏伟严重违纪违法案的审查报告",   # a central organ
    "国务院办公厅关于印发某方案的通知",                            # a central title cue
    "广东省人民政府关于某事项的决定",                              # a provincial cue
])
def test_a_government_cue_in_the_text_cannot_relevel_a_claim(title):
    # The premise: on an ordinary site this title IS re-levelled from its cue.
    assert BDI.level_of_title(title) in ("central", "provincial")
    doc = {"docnum": "国办发〔2026〕1号", "site": "epochtimes", "cat": "",
           "publisher": "大纪元", "title": title}
    assert BDI.derive_level(doc, "foreign_media", "中共中央纪律检查委员会") == \
        ("foreign_media", "site")


@pytest.mark.parametrize("title,algo", [
    ("国务院办公厅关于印发《某某行动方案》的通知", "policy_issuance"),
    ("受权发布丨中共中央办公厅 国务院办公厅印发《提振消费专项行动方案》", "action_plan"),
    ("某某市实施《条例》办法", "regulation"),
])
def test_a_claims_document_is_always_news(title, algo):
    assert BDI.derive_genre(title, algo, "foreign_media") == "news"


def test_foreign_media_ranks_below_every_other_level():
    others = [v for k, v in BDI.LEVEL_RANK.items() if k != "foreign_media"]
    assert BDI.LEVEL_RANK["foreign_media"] > max(others)


# ------------------------------------------------------------------ web filter

def test_government_source_type_excludes_foreign_media():
    from web.services import documents as docsvc
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "t.db"
        c = sqlite3.connect(path)
        c.executescript("""
        CREATE TABLE sites(site_key TEXT PRIMARY KEY, name TEXT, admin_level TEXT);
        CREATE TABLE documents(id INTEGER PRIMARY KEY, site_key TEXT, title TEXT,
            document_number TEXT DEFAULT '', publisher TEXT DEFAULT '', date_written INTEGER,
            date_published TEXT DEFAULT '', classify_main_name TEXT DEFAULT '',
            body_text_cn TEXT DEFAULT '', title_en TEXT DEFAULT '', importance TEXT DEFAULT '',
            category TEXT DEFAULT '', summary_en TEXT DEFAULT '', citation_rank REAL DEFAULT 0,
            algo_doc_type TEXT DEFAULT '', ai_relevance REAL DEFAULT 0,
            topics_algo TEXT DEFAULT '', url TEXT DEFAULT '');
        INSERT INTO sites VALUES ('gov','G','central'),('xinhua','X','media'),
                                 ('epochtimes','E','foreign_media');
        INSERT INTO documents(id, site_key, title, date_written) VALUES
            (1,'gov','国务院通知',1700000000),(2,'xinhua','新华社报道',1700000001),
            (3,'epochtimes','中共中央纪律检查委员会关于某某的审查报告',1700000002);
        """)
        c.commit()
        c.close()
        docsvc._index_cache.clear()
        docsvc._table_cache.clear()

        async def go(source_type):
            import aiosqlite
            from web.database import SQLiteDB
            conn = await aiosqlite.connect(str(path))
            conn.row_factory = aiosqlite.Row
            try:
                rows, _ = await docsvc.get_documents(SQLiteDB(conn), source_type=source_type)
                return sorted(r["site_key"] for r in rows)
            finally:
                await conn.close()
        try:
            assert asyncio.run(go("government")) == ["gov"]
            assert asyncio.run(go("media")) == ["epochtimes", "xinhua"]
        finally:
            docsvc._index_cache.clear()
            docsvc._table_cache.clear()


def test_lens_places_foreign_media_outside_every_chinese_region():
    from web.services.lens import _region_for
    assert _region_for("epochtimes", "大纪元 (Tibet 西藏 channel)", "foreign_media") == "Foreign media"


# ------------------------------------------------------------------ discourse

@pytest.mark.parametrize("k", KEYS)
@pytest.mark.parametrize("lvl", ["foreign_media", "central", "provincial", "media", None])
def test_no_speaker_bucket_for_a_claims_source(k, lvl):
    # Even if a level were ever wrong upstream, a claims site has no speaker type.
    assert speaker(k, lvl) is None


def test_foreign_media_level_has_no_speaker_on_any_site():
    assert speaker("some_new_overseas_site", "foreign_media") is None
    assert speaker("gov", "central") == "central"          # unchanged
    assert speaker("xinhua", "media") == "state_media"     # unchanged
    assert None not in SPEAKERS


# ------------------------------------------------------------------ parsing

EXPECT = {   # site -> (title, date, a sentence that must be in the body)
    "rfa": ("陈吉宁遭调查 专家：21大人事添变数", "2026-11-25", "第四名被调查的二十届政治局委员"),
    "voa": ("上海市委书记陈吉宁被调查，分析人士：最大问题可能是“忠诚度”", "2026-11-25",
            "目前正接受中央纪委的审查调查"),
    "bbc": ("中美俄“三巨头”峰会结束：涉及乌克兰、伊朗议题，发表和平宣言承诺核对话", "2026-11-19",
            "中美俄三方峰会在深圳麒麟山庄开始"),
    "dw": ("美国拟对中国等贸易伙伴加征关税 北京:“产能过剩”是伪命题", "2026-11-25",
           "提出对中国、欧盟等14个主要贸易伙伴加征新关税"),
    "secretchina": ("高调纪念孙中山“打”台湾 习近平践行“三个一”？(组图)", "2026-11-13",
                    "习近平借五中全会抛出独裁公报"),
    "epochtimes": ("中石油副总经理谢军任上被查", "2026-11-23", "谢军涉嫌严重违纪违法"),
    "zaobao": ("朱光耀：AI时代关键在谁定规则 亚洲应有紧迫感无须走欧美路径", "2026-11-25",
               "中国财政部原副部长朱光耀说"),
}


@pytest.mark.parametrize("k", sorted(EXPECT))
def test_article_parses_without_chrome(k):
    title, date, sentence = EXPECT[k]
    f = FIX[k]
    a = parse_article(f["url"], f["html"], SITES[k])
    assert a["title"] == title
    assert a["date"] == date
    assert sentence in a["body"]
    for chrome in ("订阅电子报", "下载应用程序", "版权所有", "DW中文有", "© 2026"):
        assert chrome not in a["body"], chrome


def test_epochtimes_two_digit_url_year():
    assert extract_date("https://www.epochtimes.com/gb/26/11/23/n14893785.htm", "",
                        SITES["epochtimes"]) == "2026-11-23"


def test_utc_timestamp_with_a_space_is_the_beijing_day():
    # VOA's JSON-LD: "2026-11-24 21:26:54Z" is 05:26 on the 25th in Beijing.
    cfg = {"date_utc": SITES["voa"]["date_utc"]}
    assert extract_date("https://x/a/1.html", '"datePublished":"2026-11-24 21:26:54Z"', cfg) \
        == "2026-11-25"


# ------------------------------------------------------------------ list surfaces

RFA_RSS = ("<rss><channel><title>RFA</title><link>https://rfa.org</link>"
           "<item><title><![CDATA[陈吉宁遭调查 专家：21大人事添变数]]></title>"
           "<link>https://rfa.org/mandarin/yataibaodao/2026/11/25/chen-ji-ning-under-scrutiny/</link>"
           "<content:encoded><![CDATA[<p>正文</p>]]></content:encoded></item>"
           "<item><title><![CDATA[华人大V观选  “选举证明两岸互不隶属”]]></title>"
           "<link>https://rfa.org/mandarin/yataibaodao/2026/11/24/celebrities-taiwan-election/</link></item>"
           "</channel></rss>")

DW_RDF = ('<rdf:RDF><item rdf:about="https://www.dw.com/zh/特朗普称必要时愿赦免黄仁勋/a-80044285'
          '?maca=chi-rss-chi-all-1127-rdf"><title>特朗普称必要时愿赦免黄仁勋</title>'
          '<link>https://www.dw.com/zh/特朗普称必要时愿赦免黄仁勋/a-80044285?maca=chi-rss-chi-all-1127-rdf</link>'
          '</item><item><title>涉嫌严重违纪违法 上海市委书记陈吉宁被立案调查</title>'
          '<link>https://www.dw.com/zh/涉嫌严重违纪违法-上海市委书记陈吉宁被立案调查/a-80034033'
          '?maca=chi-rss-chi-all-1127-rdf</link></item></rdf:RDF>')


def _feed_items(k, text):
    cfg = SITES[k]
    art = re.compile(cfg["art_re"])
    items = [(canon(u, cfg), t) for u, t in FEEDS["rss"](text)]
    return [(u, t) for u, t in items if art.fullmatch(u)]


def test_rfa_feed_links_move_to_www_and_filter_on_title():
    items = _feed_items("rfa", RFA_RSS)
    assert [u for u, _ in items] == [
        "https://www.rfa.org/mandarin/yataibaodao/2026/11/25/chen-ji-ning-under-scrutiny/",
        "https://www.rfa.org/mandarin/yataibaodao/2026/11/24/celebrities-taiwan-election/"]
    kept = [t for _, t in items if keep_title(t, SITES["rfa"], True)]
    assert kept == ["陈吉宁遭调查 专家：21大人事添变数"]


def test_dw_feed_urls_are_percent_encoded_and_untracked():
    items = _feed_items("dw", DW_RDF)
    assert len(items) == 2
    for u, _ in items:
        assert u.isascii() and "maca=" not in u
    assert items[1][0].endswith("/a-80034033")
    kept = [t for _, t in items if keep_title(t, SITES["dw"], True)]
    assert kept == ["涉嫌严重违纪违法 上海市委书记陈吉宁被立案调查"]


def test_dw_quoting_is_idempotent():
    cfg = SITES["dw"]
    once = canon("https://www.dw.com/zh/德语媒体/a-1", cfg)
    assert canon(once, cfg) == once


def test_dedicated_channels_are_unfiltered_general_ones_filtered():
    flagged = {k: {f for _, _, f, _ in list_pages(SITES[k])} for k in KEYS}
    for k in ("secretchina", "epochtimes"):
        assert flagged[k] == {False}, k
    for k in ("voa", "bbc", "dw", "ntdtv", "zaobao", "theinitium"):
        assert flagged[k] == {True}, k
    assert flagged["rfa"] == {False, True}     # zhengzhi channel whole, RSS filtered


def test_filtered_sites_use_the_elite_allowlist_not_the_policy_one():
    for k in KEYS:
        if any(f for _, _, f, _ in list_pages(SITES[k])):
            assert SITES[k].get("title_keep") is ELITE_TITLE_RE, k
    assert ELITE_TITLE_RE.search("中石油副总经理谢军任上被查")
    assert ELITE_TITLE_RE.search("黃仁勳落馬")            # traditional script
    assert not ELITE_TITLE_RE.search("“黑五”来了 德国人疯狂购物还是谨慎消费？")


def test_secretchina_list_page_links():
    html = ('<li><a href="/news/gb/2026/11/25/1107927.html">秦城监狱为陈吉宁扩建 习近平过河拆桥(组图)'
            '</a> -26/11/25</li><li><a href="/news/gb/p16.html">中南海</a></li>'
            '<li><a href="https://search.secretchina.com/news/gb/tag/x">习近平</a></li>')
    got = links_in(html, "https://www.secretchina.com/news/gb/p16.html", SITES["secretchina"])
    assert got == [("https://www.secretchina.com/news/gb/2026/11/25/1107927.html",
                    "秦城监狱为陈吉宁扩建 习近平过河拆桥(组图)")]
