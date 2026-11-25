"""Section registry (scripts/build_section_registry.py) and the section fixes that
shipped with it.

The registry exists because "we crawl the ministry" hid "we do not crawl its press
section". So the tests pin the properties that claim depends on:

  * sections come from the crawler CODE, whatever shape a crawler declares them in;
  * a site with no section structure is listed as unknown, never dropped;
  * a site in the DB that no crawler declares is listed too;
  * a configured-but-unscheduled site is called out (mfa and nea were both this);
  * the corpus join never drags `body_text_cn` overflow pages into the scan.
"""
import asyncio
import sqlite3
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import build_section_registry as reg  # noqa: E402


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def fake_module(name, **attrs):
    m = types.ModuleType(f"crawlers.{name}")
    for k, v in attrs.items():
        setattr(m, k, v)
    return m


def by_key(site):
    return {s["section_key"]: s for s in site["sections"]}


def make_db(path, docs, sites=()):
    conn = sqlite3.connect(str(path), timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    conn.executescript("""
        CREATE TABLE sites (site_key TEXT PRIMARY KEY, name TEXT, base_url TEXT, admin_level TEXT);
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY, site_key TEXT NOT NULL, title TEXT,
            date_written INTEGER, date_published TEXT, body_text_cn TEXT,
            classify_main_name TEXT, url TEXT, crawl_timestamp TEXT);
        CREATE INDEX idx_documents_site ON documents(site_key);
        CREATE UNIQUE INDEX idx_documents_url ON documents(url) WHERE url != '';
        CREATE INDEX idx_documents_classify_main ON documents(classify_main_name);
    """)
    conn.executemany("INSERT INTO sites VALUES (?,?,?,?)", sites)
    conn.executemany(
        "INSERT INTO documents (site_key, title, date_written, date_published, body_text_cn, "
        "classify_main_name, url, crawl_timestamp) VALUES (?,?,?,?,?,?,?,?)", docs)
    conn.commit()
    return conn


# --------------------------------------------------------------------------- #
# 1. introspection: every declared shape
# --------------------------------------------------------------------------- #

def test_dict_of_dicts_with_referer_path_and_opaque_id():
    """samr shape: the page_id is opaque; the referer is the usable path."""
    m = fake_module("samr", SITE_KEY="samr",
                    SITE_CFG={"name": "SAMR", "base_url": "https://www.samr.gov.cn", "admin_level": "central"},
                    SECTIONS={"xwfbt": {"name": "新闻发布厅", "page_id": "5fb1ceb699444ed2a679754ec3cc020d",
                                        "referer": "/xw/xwfbt/index.html"}})
    s = reg.collect(modules=[m])["samr"]
    sec = by_key(s)["xwfbt"]
    assert sec["name"] == "新闻发布厅"
    assert sec["prefixes"] == [("", "/xw/xwfbt/")]
    assert s["admin_level"] == "central" and s["structure"] == "sections"


def test_id_to_name_dict_has_label_but_no_prefix():
    """shanghai shape: {'nw39220': '沪府文件'} — matchable by label only."""
    m = fake_module("shanghai", SITE_KEY="sh", SITE_CFG={"name": "Shanghai"},
                    SECTIONS={"nw39220": "沪府文件"})
    sec = by_key(reg.collect(modules=[m])["sh"])["nw39220"]
    assert sec["labels"] == ["沪府文件"] and sec["prefixes"] == []


def test_tuple_entries_and_list_of_tuples_with_cap():
    """beijing shape (name, path) and pbc shape [(path, label, cap)]."""
    bj = fake_module("beijing", SITE_KEY="bj", SITE_CFG={"name": "BJ"},
                     SECTIONS={"szfgz": ("市政府规章", "gongkai/zfxxgk/zc/gz")})
    pbc = fake_module("pbc", SITE_KEY="pbc", CFG={"name": "PBC", "admin_level": "central"},
                      SECTIONS=[("tiaofasi/144941/144957", "部门规章", None),
                                ("goutongjiaoliu/113456/113469", "沟通交流", 40)])
    sites = reg.collect(modules=[bj, pbc])
    assert by_key(sites["bj"])["szfgz"]["prefixes"] == [("", "/gongkai/zfxxgk/zc/gz/")]
    p = by_key(sites["pbc"])
    assert p["tiaofasi/144941/144957"]["cap"] is None
    assert p["goutongjiaoliu/113456/113469"]["cap"] == 40
    assert p["goutongjiaoliu/113456/113469"]["name"] == "沟通交流"
    assert sites["pbc"]["admin_level"] == "central"      # read from CFG, not only SITE_CFG


def test_registry_module_with_and_without_sections():
    """govcms shape. A site with no `sections` must surface as unknown, not vanish."""
    m = fake_module("govcms", SITES={
        "mfa": {"name": "外交部", "base_url": "https://www.mfa.gov.cn", "admin_level": "central",
                "sections": ["/zyxw/", "/fyrbt_673021/"]},
        "bjd_x": {"name": "District X", "base_url": "http://x.gov.cn", "admin_level": "district",
                  "group": "dept"},
    })
    sites = reg.collect(modules=[m])
    assert [s["config_path"] for s in sites["mfa"]["sections"]] == ["/zyxw/", "/fyrbt_673021/"]
    assert sites["bjd_x"]["structure"] == "unknown" and sites["bjd_x"]["sections"] == []
    assert sites["bjd_x"]["group"] == "dept"


def test_registry_cfg_may_carry_its_own_site_key():
    """sz_gazette shape: NFCMS_SITES values hold site_key + a nested site_cfg."""
    m = fake_module("sz_gazette", SITE_KEY="sz_gazette", NFCMS_SITES={
        "sz_gazette": {"site_key": "sz_gazette", "site_cfg": {"name": "Gazette", "admin_level": "municipal"}},
        "other": {"site_key": "szx", "site_cfg": {"name": "X", "admin_level": "district"}},
    })
    sites = reg.collect(modules=[m])
    assert set(sites) == {"sz_gazette", "szx"}
    assert sites["szx"]["admin_level"] == "district"


def test_nested_departments_carry_parent_label():
    """zhejiang shape: DEPARTMENTS -> dept -> sections; stored label is 'dept / section'."""
    m = fake_module("zhejiang", SITE_KEY="zj", SITE_CFG={"name": "ZJ"}, DEPARTMENTS={
        "fzggw": {"name": "省发改委", "domain": "fzggw.zj.gov.cn",
                  "sections": {"gfxwj": ("行政规范性文件", "1229565788", "信息列表", "x")}}})
    sec = reg.collect(modules=[m])["zj"]["sections"][0]
    assert sec["name"] == "省发改委 / 行政规范性文件"
    assert "省发改委 / 行政规范性文件" in sec["labels"]


def test_feeds_bare_lists_and_path_prefix_keys():
    """gov FEEDS (full URLs), guancha bare words, xinhua path_prefix without a slash."""
    gov = fake_module("gov", SITE_KEY="gov", SITE_CFG={"name": "State Council"}, FEEDS={
        "yaowen": {"name": "要闻", "url": "https://www.gov.cn/yaowen/liebiao/YAOWENLIEBIAO.json",
                   "refetch_bodyless": False}})
    gc = fake_module("guancha", SITE_KEY="guancha", SITE_CFG={"name": "Guancha"},
                     SECTION_PAGES=["politics", "economy"])
    xh = fake_module("xinhua", SITE_KEY="xinhua", SITE_CFG={"name": "Xinhua"},
                     SECTIONS={"tech": {"name": "科技", "path_prefix": "tech", "datasource_id": "abc"}})
    sites = reg.collect(modules=[gov, gc, xh])
    assert by_key(sites["gov"])["yaowen"]["prefixes"] == [("www.gov.cn", "/yaowen/liebiao/")]
    assert by_key(sites["gov"])["yaowen"]["cap"] is None           # a bool is not a cap
    assert by_key(sites["guancha"])["politics"]["prefixes"] == [("", "/politics/")]
    assert by_key(sites["xinhua"])["tech"]["prefixes"] == [("", "/tech/")]


def test_module_without_any_section_container_is_unknown():
    m = fake_module("36kr", SITE_KEY="36kr", SITE_CFG={"name": "36Kr", "admin_level": "media"},
                    RSS_URL="https://36kr.com/feed")
    s = reg.collect(modules=[m])["36kr"]
    assert s["structure"] == "unknown" and s["sections"] == []


@pytest.mark.parametrize("path,want", [
    ("/zw/zjwj/index.html", ("", "/zw/zjwj/")),
    ("/sjj/zwgk/zcfb/list/", ("", "/sjj/zwgk/zcfb/")),          # nda: drop the /list/ dir
    ("/policy/zxwj.htm", ("", "/policy/")),
    ("/zcfgk/c100006/listflfg.html", ("", "/zcfgk/c100006/")),
    ("tiaofasi/144941/3581332", ("", "/tiaofasi/144941/3581332/")),
    ("http://scitech.ce.cn/sy/zx/", ("scitech.ce.cn", "/sy/zx/")),
    ("http://www.ce.cn/", ("www.ce.cn", "/")),
    ("https://www.gov.cn/lianbo/fabu/TONGYONGLIEBIAODRQ.json", ("www.gov.cn", "/lianbo/fabu/")),
])
def test_norm_prefix(path, want):
    assert reg.norm_prefix(path) == want


# --------------------------------------------------------------------------- #
# 2. the nightly schedule
# --------------------------------------------------------------------------- #

SH = '''
run_crawler "gkmlpt (40+ sites)" python3 -m crawlers.gkmlpt --sync
for crawler in gov samr; do
    run_crawler "$crawler" python3 -m crawlers.$crawler
done
run_weekly 2 "sic" python3 -m crawlers.sic
for site in mwr mfa; do
    run_crawler "govcms ($site)" python3 -m crawlers.govcms --site $site
done
run_crawler "govcms (dept group)" python3 -m crawlers.govcms --group dept
run_crawler_t 600 "finmedia" \\
    python3 -m crawlers.finmedia --tier 1 --max-docs 150
run_crawler_t 900 "theory" python3 -m crawlers.theory --recent
if [ "$IS_MAC" = "true" ]; then
    for crawler in miit most; do
        run_crawler "$crawler" python3 -m crawlers.$crawler
    done
else
    run_crawler "miit" python3 -m crawlers.miit
    if [ "$(date -u +%u)" = "1" ]; then
        run_crawler_t 600 "zhejiang (weekly probe)" python3 -m crawlers.zhejiang
    else
        log "  Skipping zhejiang"
    fi
fi
log "would run python3 -m crawlers.nothing"
'''


def _site(module, key, **kw):
    d = {"module": module, "site_key": key, "group": None, "tier": None}
    d.update(kw)
    return d


def test_schedule_parser_covers_every_shape_the_script_uses():
    sched = reg.parse_schedule(SH)
    mods = {(e["module"], e["site"], e["group"], e["tier"], e["cadence"]) for e in sched}
    assert ("gov", None, None, None, "nightly") in mods            # for-loop expansion
    assert ("samr", None, None, None, "nightly") in mods
    assert ("sic", None, None, None, "weekly") in mods             # run_weekly
    assert ("govcms", "mfa", None, None, "nightly") in mods        # --site $site
    assert ("govcms", None, "dept", None, "nightly") in mods       # --group
    assert ("finmedia", None, None, "1", "nightly") in mods        # line continuation + --tier
    assert ("zhejiang", None, None, None, "weekly") in mods        # weekday `if`
    assert ("miit", None, None, None, "nightly") in mods           # droplet (else) branch
    assert not any(e["module"] == "most" for e in sched)           # Mac-only branch skipped
    assert not any(e["module"] == "nothing" for e in sched)        # a log line is not a run


def test_schedule_for_distinguishes_configured_from_scheduled():
    sched = reg.parse_schedule(SH)
    assert reg.schedule_for(_site("govcms", "mfa"), sched) == "nightly"
    # configured in the same registry, named by no --site and in no scheduled group:
    assert reg.schedule_for(_site("govcms", "nea"), sched) == "not scheduled"
    assert reg.schedule_for(_site("govcms", "fj_x", group="dept"), sched) == "nightly"
    assert reg.schedule_for(_site("finmedia", "ce", tier=1), sched) == "nightly"
    assert reg.schedule_for(_site("finmedia", "jiemian", tier=2), sched) == "not scheduled"
    assert reg.schedule_for(_site("theory", "qiushi", tier=1), sched) == "nightly"
    assert reg.schedule_for(_site("theory", "aisixiang", tier=3), sched) == "not scheduled"
    assert reg.schedule_for(_site("zhejiang", "zj"), sched) == "weekly"
    assert reg.schedule_for(_site("moe", "moe"), sched) == "not scheduled"


# --------------------------------------------------------------------------- #
# 3. the join
# --------------------------------------------------------------------------- #

TODAY = "2026-11-25"


def _fixture_sites():
    samr = fake_module("samr", SITE_KEY="samr",
                       SITE_CFG={"name": "SAMR", "base_url": "https://www.samr.gov.cn", "admin_level": "central"},
                       SECTIONS={
                           "zjwj": {"name": "总局文件", "page_id": "a" * 32, "referer": "/zw/zjwj/index.html"},
                           "zcjd": {"name": "政策解读", "page_id": "b" * 32, "referer": "/zw/zjwj/zcjd/index.html"},
                           "xwfbt": {"name": "新闻发布厅", "page_id": "c" * 32, "referer": "/xw/xwfbt/index.html"},
                       })
    kr = fake_module("36kr", SITE_KEY="36kr", SITE_CFG={"name": "36Kr", "admin_level": "media"})
    return reg.collect(modules=[samr, kr])


def _fixture_docs():
    b = "正文" * 50
    return [
        # label match (URL is elsewhere on the site, like SAMR's /cms_files/ PDFs)
        ("samr", "a", 0, "2026-11-24", b, "总局文件", "https://www.samr.gov.cn/cms_files/x.pdf", "2026-11-25T06:00"),
        # prefix match, longest prefix wins (/zw/zjwj/zcjd/ over /zw/zjwj/), no label
        ("samr", "b", 0, "2026-10-01", "", "", "https://www.samr.gov.cn/zw/zjwj/zcjd/art/2026/art_1.html", "2026-10-02T06:00"),
        # date only in date_written (seconds); 2026-01-05 CST
        ("samr", "c", 1767542400, "", b, "", "https://www.samr.gov.cn/zw/zjwj/art/2026/art_2.html", "x"),
        # matches nothing configured -> unattributed + observed family
        ("samr", "d", 0, "2026-11-20", b, "", "https://www.samr.gov.cn/ggjgs/tzgg/art/2026/art_3.html", "x"),
        # a future date is a parse artefact, not freshness
        ("samr", "e", 0, "2999-02-25", b, "总局文件", "https://www.samr.gov.cn/zw/zjwj/art/2026/art_4.html", "x"),
        ("36kr", "f", 0, "2026-08-04", b, "媒体报道", "https://36kr.com/p/1", "x"),
        ("36kr", "g", 0, "2026-08-03", b, "媒体报道", "https://36kr.com/p/2", "x"),
        # in the DB, declared by no crawler module
        ("orphan", "h", 0, "2026-11-01", b, "", "https://example.gov.cn/20261101/abc/c.html", "x"),
    ]


@pytest.fixture()
def rows(tmp_path):
    conn = make_db(tmp_path / "t.db", _fixture_docs(),
                   sites=[("orphan", "Orphan Site", "https://example.gov.cn", "central")])
    sched = reg.parse_schedule('run_crawler "samr" python3 -m crawlers.samr\n')
    out = reg.build_rows(conn, _fixture_sites(), sched, today=TODAY)
    conn.close()
    return out


def pick(rows, site, kind, name=None):
    out = [r for r in rows if r["site_key"] == site and r["kind"] == kind
           and (name is None or r["name"] == name)]
    return out


def test_label_match_and_longest_prefix(rows):
    zjwj = pick(rows, "samr", "section", "总局文件")[0]
    zcjd = pick(rows, "samr", "section", "政策解读")[0]
    assert zjwj["docs"] == 3 and zjwj["match"] == "label+prefix"
    assert zcjd["docs"] == 1 and zcjd["with_body"] == 0 and zcjd["match"] == "prefix"
    assert zcjd["staleness"] == "stale"                     # 2026-10-01 is 55 days before TODAY
    # the future-dated row is counted but cannot make the section look fresh
    assert zjwj["newest"] == "2026-11-24" and zjwj["staleness"] == "fresh"


def test_configured_section_with_nothing_held_says_so(rows):
    x = pick(rows, "samr", "section", "新闻发布厅")[0]
    assert x["docs"] == 0 and x["match"] == "none" and x["staleness"] == "no docs matched"


def test_unattributed_docs_and_observed_families(rows):
    un = pick(rows, "samr", "unattributed")[0]
    assert un["docs"] == 1
    fams = {r["name"]: r["docs"] for r in pick(rows, "samr", "observed")}
    assert fams == {"www.samr.gov.cn/ggjgs/": 1}


def test_site_without_section_structure_is_listed_explicitly(rows):
    assert pick(rows, "36kr", "site")[0]["docs"] == 2
    unk = pick(rows, "36kr", "unknown")
    assert len(unk) == 1 and "sections unknown" in unk[0]["name"]
    assert pick(rows, "36kr", "site")[0]["schedule"] == "not scheduled"
    assert pick(rows, "36kr", "site")[0]["staleness"] == "stale"
    assert {r["name"] for r in pick(rows, "36kr", "observed")} == {"36kr.com/p/"}


def test_db_site_with_no_crawler_module_is_listed(rows):
    site = pick(rows, "orphan", "site")[0]
    assert site["schedule"] == "no crawler" and site["docs"] == 1
    assert site["site_name"] == "Orphan Site" and site["admin_level"] == "central"
    # a date directory is not a section name
    assert {r["name"] for r in pick(rows, "orphan", "observed")} == {"example.gov.cn/<date>/"}


def test_site_totals_reconcile(rows):
    """Every held document is in exactly one of: a section, or the unattributed row."""
    site = pick(rows, "samr", "site")[0]
    parts = sum(r["docs"] for r in rows if r["site_key"] == "samr"
                and r["kind"] in ("section", "unattributed"))
    assert site["docs"] == parts == 5


def test_scan_never_touches_the_body_overflow(tmp_path):
    """`url` and `classify_main_name` sit after body_text_cn in the record. Selecting
    them in the table scan walks every overflow chain (213 s vs 54 s on the droplet),
    so they must come from covering indexes — and the body flag from the header."""
    conn = make_db(tmp_path / "p.db", _fixture_docs())
    for sql in (reg.URL_SQL, reg.LABEL_SQL):
        plan = " ".join(r[3] for r in conn.execute("EXPLAIN QUERY PLAN " + sql))
        assert "COVERING INDEX" in plan, (sql, plan)
    main = reg.MAIN_SCAN_SQL.lower()
    assert "url" not in main and "classify_main_name" not in main and "group by" not in main
    if reg._HAS_OCTET_LENGTH:
        assert "octet_length(body_text_cn)" in main and "body_text_cn !=" not in main
    conn.close()


def test_single_site_preview_equals_the_full_build(tmp_path):
    conn = make_db(tmp_path / "s.db", _fixture_docs())
    sites, sched = _fixture_sites(), []
    full = [r for r in reg.build_rows(conn, sites, sched, today=TODAY) if r["site_key"] == "samr"]
    one = reg.build_rows(conn, sites, sched, today=TODAY, only_site="samr")
    conn.close()
    assert full == one


def test_write_table_round_trip_and_idempotence(tmp_path, rows):
    db = tmp_path / "w.db"
    make_db(db, []).close()
    reg.write_table(db, rows, {"built_at": "t", "sites": 3})
    reg.write_table(db, rows, {"built_at": "t2", "sites": 3})        # rebuild replaces, not appends
    conn = sqlite3.connect(str(db), timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    assert conn.execute("SELECT COUNT(*) FROM section_registry").fetchone()[0] == len(rows)
    assert dict(conn.execute("SELECT k, v FROM section_registry_meta"))["built_at"] == "t2"
    got = conn.execute("SELECT docs, staleness FROM section_registry WHERE site_key='samr' "
                       "AND name='新闻发布厅'").fetchone()
    assert got == (0, "no docs matched")
    conn.close()


@pytest.mark.parametrize("dw,dp,want", [
    (0, "2026-11-15-17:10:00", "2026-11-15"),       # gov.cn's own format
    (0, "2026-10-16 16:21:58", "2026-10-16"),
    (0, "2026-7-4", "2026-07-04"),
    (1795536000, "", "2026-11-25"),                 # midnight CST = 16:00Z the day before
    (0, "", ""), (None, None, ""),
    (0, "2999-02-25", ""),                          # future -> dropped
])
def test_doc_date(dw, dp, want):
    assert reg.doc_date(dw, dp, "2026-11-27") == want


# --------------------------------------------------------------------------- #
# 4. the real repository
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def real():
    return reg.collect()


def test_every_crawler_module_imports(real):
    assert "__import_errors__" not in real, real.get("__import_errors__")


def test_real_registry_sees_the_sections_this_audit_added(real):
    assert {"xwfbt", "ggjgs_tzgg", "bzjss_zqyj"} <= set(by_key(real["samr"]))
    assert by_key(real["samr"])["xwfbt"]["prefixes"] == [("", "/xw/xwfbt/")]
    assert {"zuixin", "yaowen", "fabu"} <= set(by_key(real["gov"]))
    assert "/fyrbt_673021/" in [s["config_path"] for s in real["mfa"]["sections"]]
    assert {"xwfyrth", "ldrhd"} <= set(by_key(real["mofcom"]))
    assert {"dfdt", "mtsy", "sjdt"} <= set(by_key(real["nda"]))
    assert not any(s["config_path"].startswith("/n/") for s in real["nea"]["sections"])


def test_real_registry_keeps_sectionless_sites(real):
    unknown = [k for k, s in real.items() if s["structure"] == "unknown"]
    assert "36kr" in unknown and "sz" in unknown           # an RSS site and a gkmlpt site
    assert len(real) > 400                                 # govcms alone declares 400+


def test_real_schedule_no_configured_central_ministry_is_left_unscheduled(real):
    """mfa and nea were configured and crawled by nobody. If a central site is meant
    to be off the nightly, name it here with the reason — do not let it be silent."""
    sched = reg.parse_schedule(reg.DAILY_SYNC.read_text())
    deliberate = {
        "npc": "one-off metadata load of the national laws database",
        "cnipa": "open: configured, never scheduled (found 2026-11-25)",
        "dangyuan": "open: configured, never scheduled (found 2026-11-25)",
        "mod": "open: configured, never scheduled (found 2026-11-25)",
        "mohurd": "govmirror: gov.cn library mirror, run by hand",
        "mca": "govmirror", "mnr": "govmirror", "nhc": "govmirror",
    }
    off = {k for k, s in real.items()
           if s["admin_level"] == "central" and reg.schedule_for(s, sched) == "not scheduled"}
    assert off - set(deliberate) == set(), f"unscheduled central sites with no stated reason: {off - set(deliberate)}"
    for k in ("samr", "gov", "mfa", "nea", "mofcom", "nda"):
        assert reg.schedule_for(real[k], sched) == "nightly", k
    assert reg.schedule_for(real["moe"], sched) == "weekly"


# --------------------------------------------------------------------------- #
# 5. the crawler fixes found by the audit (pure parsers, no network)
# --------------------------------------------------------------------------- #

def test_samr_parses_both_listing_templates_and_unwraps_titles():
    from crawlers import samr
    a = ('<ul><li class="nav04Left02_content"><a href="/xw/xwfbt/art/2026/art_7aa3.html" '
         'title="市场监管总局人工智能国际标准化工作\n专题新闻发布会实录" target="_blank">x</a></li>\n'
         '<li class="nav04Left02_contenttime">2026-11-24</li></ul><div count="329"></div>')
    items, total = samr._parse_listing_html(a)
    assert total == 329 and len(items) == 1
    assert items[0]["title"] == "市场监管总局人工智能国际标准化工作专题新闻发布会实录"
    assert items[0]["url"] == "https://www.samr.gov.cn/xw/xwfbt/art/2026/art_7aa3.html"
    b = ('<div id="ajax分页"><ul><li class="content-3-left-text imgContent01new">\n'
         '<a href="/ggjgs/tzgg/art/2026/art_661a.html" title="关于开展户外广告\n导向问题专项治理的通知">关于…</a>\n'
         '<div class="contentRight01time">2026-07-09</div></li></ul></div><div count="26"></div>')
    items, total = samr._parse_listing_html(b)
    assert total == 26 and items[0]["date_str"] == "2026-07-09"
    assert items[0]["title"] == "关于开展户外广告导向问题专项治理的通知"


SH_INDEX = '''
<li><a href="/nw2407/index.html" target="_blank">沪府令</a></li>
<li><a href="/nw44931/index.html" target="_blank">沪府任文件</a></li>
<div><a href="/2026hffwj/index.html" target="_blank"><h4 class="region-type">2026年</h4></a></div>
<div><a href="/ hfbf2025/index.html" target="_blank"><h4 class="region-type">2025年</h4></a></div>
<a href="/2024hffwj/index.html">2024年</a>
'''


def test_shanghai_year_archive_does_not_start_at_an_earlier_anchor():
    """The bug: a lazy .*? under DOTALL began at the first nav tab and ran to '2026年',
    so the newest year of EVERY section resolved to /nw2407/index.html."""
    from crawlers import shanghai
    got = shanghai._parse_year_archives(SH_INDEX)
    assert got == [("2026", "https://www.shanghai.gov.cn/2026hffwj/index.html"),
                   ("2025", "https://www.shanghai.gov.cn/%20hfbf2025/index.html"),
                   ("2024", "https://www.shanghai.gov.cn/2024hffwj/index.html")]


def test_shanghai_listing_matches_the_date_span_inside_the_anchor():
    from crawlers import shanghai
    new = ('<li>\n <a href="/nw12344/20261112/1134.html" title="关于表彰的决定" target=\'_blank\'>\n'
           '关于表彰的决定   <span class="time">2026-11-12</span>\n </a>\n</li>')
    old = '<li><a href="/nw12344/20250101/9.html" title="旧版">旧版</a> <span class="time">2025-01-01</span></li>'
    assert [i["date_str"] for i in shanghai._parse_listing(new, "https://www.shanghai.gov.cn/x/")] == ["2026-11-12"]
    assert [i["title"] for i in shanghai._parse_listing(old, "https://www.shanghai.gov.cn/x/")] == ["旧版"]


def test_govcms_datasource_rows_are_bounded_unless_deep():
    from crawlers import govcms
    payload = {"datasource": (
        [{"publishUrl": "../20261125/abc/c.html", "showTitle": "<b>国家能源局公告</b>",
          "publishTime": "2026-11-25 10:00:00", "contentType": "News"},
         {"publishUrl": "http://x/", "title": "外链", "publishTime": "2026-11-24", "contentType": "Link"}]
        + [{"publishUrl": f"/2025{i:04d}/h/c.html", "title": f"t{i}", "publishTime": "2025-01-01"}
           for i in range(200)])}
    page = "http://www.nea.gov.cn/policy/zxwj.htm"
    rows = govcms._datasource_parse(payload, page)
    assert len(rows) == govcms.DATASOURCE_RECENT
    assert rows[0] == {"url": "http://www.nea.gov.cn/20261125/abc/c.html", "title": "国家能源局公告",
                       "date": "2026-11-25"}
    assert all(r["title"] != "外链" for r in rows)                # external links are not documents
    assert len(govcms._datasource_parse(payload, page, deep=True)) == 201
    assert govcms._DATASOURCE_RE.search(
        '<ul id="showData0" class="list" data="datasource:40d365c13659452aa06cdb7268d6192e">')


def test_gov_news_feeds_keep_only_gov_cn_article_pages():
    """107 of 395 要闻 rows are tv.cctv.com videos and 75 of 480 新闻发布 rows are
    mini-site index pages; neither has a body and neither belongs under site 'gov'."""
    from crawlers import gov
    ok = gov._ARTICLE_URL_RE.match
    assert ok("https://www.gov.cn/yaowen/liebiao/202611/content_7086500.htm")
    assert ok("https://www.gov.cn/lianbo/fabu/202611/content_7086301.htm")
    assert not ok("https://tv.cctv.com/2026/11/24/VIDEb21PXT3mic7y5AErc3YS261124.shtml")
    assert not ok("https://www.gov.cn/xinwen/2026zccfh/10/index.htm")
    assert gov.FEEDS["yaowen"]["articles_only"] and gov.FEEDS["fabu"]["articles_only"]
    # the policy feed is unchanged: it keeps every row and still retries bodiless ones
    assert not gov.FEEDS["zuixin"].get("articles_only") and gov.FEEDS["zuixin"]["refetch_bodyless"]
    assert gov.FEEDS["zuixin"]["name"] == "政策文件"            # the label 26k held rows carry


def test_mofcom_main_listing_parser():
    from crawlers import mofcom
    html = ('<li> <a href="/xwfb/xwfyrth/art/2026/art_67a4.html" title="商务部新闻发言人就欧盟\n答记者问" '
            'target="_blank">商务部…</a><span>[2026-11-24]</span> </li><div count="641"></div>')
    items, total = mofcom._parse_main_listing(html)
    assert total == 641
    assert items == [{"url": "https://www.mofcom.gov.cn/xwfb/xwfyrth/art/2026/art_67a4.html",
                      "title": "商务部新闻发言人就欧盟答记者问", "date_str": "2026-11-24"}]


# --------------------------------------------------------------------------- #
# 6. the known-missing file and the page's data layer
# --------------------------------------------------------------------------- #

def test_known_missing_file_is_well_formed(real):
    from web.services import sections as svc
    km = svc.load_known_missing()
    entries = [e for v in km.values() for e in v]
    assert len(entries) >= 20
    for e in entries:
        assert e["status"] in svc.STATUSES, e
        assert e["name"] and e["path"] and e["example_url"].startswith("http"), e
        assert e["found"], e
        # a gap must hang off a site we actually crawl, or it is a NEW site (report it, don't file it)
        assert e["site_key"] in real, f"{e['site_key']} is not a crawled site"
    assert any(e["site_key"] == "samr" and "新闻发布厅" in e["name"] and e["status"] == "added"
               for e in entries)


class _FakeDB:
    """The two async methods web/services/sections.py uses, over plain sqlite3."""

    def __init__(self, path):
        self.c = sqlite3.connect(str(path), timeout=30)
        self.c.execute("PRAGMA busy_timeout=30000")
        self.c.row_factory = sqlite3.Row

    async def fetch(self, q, *args):
        import re as _re
        return self.c.execute(_re.sub(r"\$\d+", "?", q), args).fetchall()


def test_admin_view_data_groups_sections_and_attaches_gaps(tmp_path, rows):
    from web.services import sections as svc
    db = tmp_path / "v.db"
    make_db(db, []).close()
    reg.write_table(db, rows, {"built_at": "2026-11-25 12:00 UTC", "sites": 3, "sections": 3,
                               "sections_stale": 1, "sections_no_docs": 1,
                               "sites_sections_unknown": 2, "sites_not_scheduled": 1})
    fdb = _FakeDB(db)
    data = asyncio.run(svc.get_sections(fdb, level="central"))
    assert data["built"] and {s["site_key"] for s in data["sites"]} == {"samr", "orphan"}
    samr = next(s for s in data["sites"] if s["site_key"] == "samr")
    assert [x["name"] for x in samr["sections"]] == ["总局文件", "政策解读", "新闻发布厅"]
    assert samr["unattributed"]["docs"] == 1 and len(samr["observed"]) == 1
    assert samr["n_empty"] == 1 and samr["n_stale"] == 1 and samr["has_issue"]
    assert any("新闻发布厅" in m["name"] for m in samr["missing"])      # from the YAML
    # media level: the sectionless site is there with its explicit marker
    media = asyncio.run(svc.get_sections(fdb, level="media"))
    assert media["sites"][0]["site_key"] == "36kr" and media["sites"][0]["unknown"] is not None
    one = asyncio.run(svc.get_sections(fdb, level="central", site="36kr"))
    assert [s["site_key"] for s in one["sites"]] == ["36kr"]           # ?site= overrides level


def test_admin_view_survives_a_db_without_the_table(tmp_path):
    from web.services import sections as svc
    db = tmp_path / "n.db"
    make_db(db, []).close()
    data = asyncio.run(svc.get_sections(_FakeDB(db), level=""))
    assert data["built"] is False
    # the gap list is still shown: it does not depend on the nightly table
    assert any(s["site_key"] == "samr" and s["missing"] for s in data["sites"])


def test_page_renders_through_the_real_route(tmp_path, rows, monkeypatch):
    """/admin/sections end to end: real router, real template, the wrapped aiosqlite DB."""
    from contextlib import asynccontextmanager
    import aiosqlite
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from web.database import SQLiteDB
    from web.routers import pages

    db = tmp_path / "page.db"
    make_db(db, []).close()
    reg.write_table(db, rows, {"built_at": "2026-11-25 12:00 UTC", "sites": 3, "sections": 3,
                               "sections_stale": 1, "sections_no_docs": 1,
                               "sites_sections_unknown": 2, "sites_not_scheduled": 1})

    async def fake_stats(_db):
        return {"total": 0, "site_count": 0}
    monkeypatch.setattr(pages, "get_stats", fake_stats)

    @asynccontextmanager
    async def lifespan(app):
        conn = await aiosqlite.connect(f"file:{db}?mode=ro", uri=True)
        conn.row_factory = aiosqlite.Row
        app.state.db = SQLiteDB(conn)
        yield
        await conn.close()

    app = FastAPI(lifespan=lifespan)
    app.include_router(pages.router)
    with TestClient(app) as client:
        r = client.get("/admin/sections")                       # default level = central
        assert r.status_code == 200
        html = r.text
        assert "Section coverage" in html and "新闻发布厅" in html
        assert "no docs matched" in html and "Known-missing sections" in html
        assert "held, but matched to no configured section" in html
        assert "36Kr" not in html                               # media is another level
        r2 = client.get("/admin/sections", params={"level": "all", "issues": 1})
        assert r2.status_code == 200 and "sections unknown" in r2.text and "no crawler" in r2.text
        assert client.get("/admin/sections", params={"site": "samr"}).status_code == 200
