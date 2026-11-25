"""The global-discourse weekly tracker: scripts/build_discourse_weekly.py (the table)
and web/services/discourse.py + /discourse (the page).

Literal counts on a tiny fixture corpus, including the memo's dedup rule
(one copy per title per speaker type, here per WEEK), the two regex fixes of
2026-11-12, --since, --dry-run, and a render of the page.

Run: python3 -m pytest tests/test_discourse_weekly.py -v
"""
import asyncio
import re
import sqlite3
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import build_discourse_weekly as bdw  # noqa: E402
from web.services import discourse as svc  # noqa: E402
from web.services import tracker as trk  # noqa: E402
from web.services import pubcache  # noqa: E402
from web.services.discourse_vocab import CONCEPTS, COUNTER_TERMS, all_terms, compiled, find_terms  # noqa: E402

TODAY = date(2026, 11, 12)       # Thursday of 2026-W46


# ---------------------------------------------------------------- the builder
DOCS = [
    # id, site, date, title, body, level (None = no doc_identity row)
    (1, "xinhua", "2026-11-03", "标题A", "推动全球南方合作", "media"),        # W45 state_media, hit
    (2, "people", "2026-11-04", "标题A！", "全球南方再次出现", "media"),      # same title after \W strip -> dup
    (3, "gov", "2026-11-04", "标题A", "全球南方", "central"),                 # other speaker: counts
    (4, "xinhua", "2026-11-10 08:00:00", "标题A", "全球南方", "media"),      # W46: a new week counts again
    (5, "xinhua", "2026-11-05", "标题B", "无关内容", "media"),               # denominator only
    (6, "foo", "2026-11-05", "标题E", "全球南方", None),                      # no speaker type: skipped
    (7, "xinhua", "2026-11-05", "标题C", "打破地方保护主义", "media"),       # domestic: not 保护主义
    (8, "xinhua", "2026-11-05", "标题F", "", "media"),                        # no body: excluded
    (9, "guancha", "2026-11-06", "", "打破了“现代化=西方化”的迷思", ""),      # empty title, hit
    (10, "guancha", "2026-11-06", "——", "别的内容", ""),                      # empty after \W: NOT merged with 9
    (11, "xinhua", "2099-01-05", "标题G", "全球南方", "media"),              # future: excluded
    (20, "xinhua", "2026-11-05", "标题D", "全球南方与贸易保护主义", "media"),  # kept copy = lowest id
    (21, "xinhua", "2026-11-05", "标题D", "无关", "media"),                  # dup of 20
    # 观察者网 page chrome. 40: the stored body is ONLY title + timestamp + a 相关推荐
    # headline list (the shape of 933 real rows) -> dropped from numerator AND denominator.
    (40, "guancha", "2026-11-06", "某文章",
     "某文章\n 2026-11-06 15:47:50\n -->\n 相关推荐\n 伪史论者又出新招\n 2026-11-06 13:42\n"
     " 全球南方的新议程\n 2026-11-06 11:25\n \u00a0\u00a0\u00a0观察者头条\n 查看全部\n 中等强国怎么选\n 评论 61\n", ""),
    # 41: real article text, a term ONLY in the sidebar -> in the denominator, term 0.
    (41, "guancha", "2026-11-06", "真文章",
     "真文章\n 2026-11-06 10:00:00\n 这是一篇关于国内消费的评论文章，讨论了很多具体的数据和政策问题，篇幅足够长。\n"
     " 相关推荐\n 中等强国的选择\n 2026-11-06 09:00\n", ""),
    # 42: the term in the article text itself still counts, even with chrome after it.
    (42, "guancha", "2026-11-06", "另一篇",
     "另一篇\n 2026-11-06 10:00:00\n 文章认为，中等强国正在重新评估与大国的关系，这一趋势值得关注。\n"
     " 相关推荐\n 伪史论者又出新招\n", ""),
]


def make_corpus(path, docs=DOCS):
    c = sqlite3.connect(path)
    c.executescript("""
        CREATE TABLE documents (id INTEGER PRIMARY KEY, site_key TEXT, date_published TEXT,
                                title TEXT, body_text_cn TEXT);
        CREATE TABLE doc_identity (doc_id INTEGER PRIMARY KEY, admin_level_doc TEXT);
    """)
    for did, site, d, t, b, lvl in docs:
        c.execute("INSERT INTO documents VALUES (?,?,?,?,?)", (did, site, d, t, b))
        if lvl is not None:
            c.execute("INSERT INTO doc_identity VALUES (?,?)", (did, lvl))
    c.commit()
    c.close()


def table(path):
    c = sqlite3.connect(path)
    rows = {(r[0], r[1], r[2]): (r[3], r[4]) for r in
            c.execute("SELECT concept, speaker, iso_week, docs, denom FROM discourse_weekly")}
    c.close()
    return rows


@pytest.fixture
def built(tmp_path):
    db = tmp_path / "corpus.db"
    make_corpus(db)
    assert bdw.main(["--db", str(db)]) == 0
    return db


def test_literal_counts_and_dedup(built):
    t = table(built)
    # state_media W45: kept 1, 5, 7, 20 (2 is a title dup of 1, 21 of 20, 8 has no body)
    assert t[("_all", "state_media", "2026-W45")] == (4, 4)
    assert t[("全球南方", "state_media", "2026-W45")] == (2, 4)        # docs 1 and 20
    # a different speaker type is a different voice
    assert t[("全球南方", "central", "2026-W45")] == (1, 1)
    # the next week counts the same title again
    assert t[("全球南方", "state_media", "2026-W46")] == (1, 1)
    # empty titles are never merged; guancha 40 is chrome-only and dropped, 41 and 42 kept
    assert t[("_all", "commentary", "2026-W45")] == (4, 4)
    assert t[("现代化≠西方化", "commentary", "2026-W45")] == (1, 4)
    # sidebar-only terms count 0: 伪史论 / 全球南方 appear only in chrome (40, 42's tail)
    assert ("西方伪史", "commentary", "2026-W45") not in t
    assert ("全球南方", "commentary", "2026-W45") not in t
    # 中等强国 is in 41's sidebar (not counted) and in 42's article text (counted)
    assert t[("中等强国", "commentary", "2026-W45")] == (1, 4)
    # 地方保护主义 is domestic; 贸易保护主义 (doc 20) still counts
    assert t[("保护主义", "state_media", "2026-W45")] == (1, 4)
    # nothing else: no future week, no unspeakered site, no rows with docs = 0
    assert {k[2] for k in t} == {"2026-W45", "2026-W46"}
    assert all(v[0] > 0 for v in t.values())
    assert len(t) == 10


def test_concepts_table(built):
    c = sqlite3.connect(built)
    n, fams = c.execute("SELECT COUNT(*), COUNT(DISTINCT family) FROM discourse_concepts").fetchone()
    assert n == len(CONCEPTS) + len(COUNTER_TERMS) == 49
    assert fams == 7


def test_since_rebuilds_only_later_weeks(built):
    c = sqlite3.connect(built)
    c.execute("INSERT INTO documents VALUES (30, 'xinhua', '2026-11-11', '标题H', '全球南方')")
    c.execute("INSERT INTO doc_identity VALUES (30, 'media')")
    # a W45 doc added now must NOT appear: --since 2026-11-10 only touches W46+
    c.execute("INSERT INTO documents VALUES (31, 'xinhua', '2026-11-03', '标题I', '全球南方')")
    c.execute("INSERT INTO doc_identity VALUES (31, 'media')")
    c.commit(); c.close()
    assert bdw.main(["--db", str(built), "--since", "2026-11-10"]) == 0
    t = table(built)
    assert t[("全球南方", "state_media", "2026-W46")] == (2, 2)
    assert t[("全球南方", "state_media", "2026-W45")] == (2, 4)       # untouched


def test_dry_run_and_out_write_nothing_to_source(tmp_path):
    db, out = tmp_path / "corpus.db", tmp_path / "out.db"
    make_corpus(db)
    assert bdw.main(["--db", str(db), "--dry-run"]) == 0
    assert bdw.main(["--db", str(db), "--out", str(out)]) == 0
    c = sqlite3.connect(db)
    assert c.execute("SELECT COUNT(*) FROM sqlite_master WHERE name LIKE 'discourse%'").fetchone()[0] == 0
    assert table(out)[("_all", "state_media", "2026-W45")] == (4, 4)


def test_strip_chrome_only_touches_guancha_header_lines():
    from web.services.discourse_vocab import article_chars, strip_chrome
    body = "标题\n 2026-11-06 10:00:00\n 正文提到相关推荐这个词也不会被截断。\n 相关推荐\n 伪史论\n"
    assert strip_chrome("guancha", body) == "标题\n 2026-11-06 10:00:00\n 正文提到相关推荐这个词也不会被截断。"
    assert strip_chrome("ifeng", body) == body              # other sites untouched
    assert strip_chrome("guancha", "无侧栏的正文") == "无侧栏的正文"
    assert article_chars("标题", "标题\n 2026-11-06 10:00:00\n -->") == 0


def test_bad_since_refuses():
    with pytest.raises(ValueError):
        bdw.main(["--db", "/nonexistent.db", "--since", "2026-13-01"])


EXAMPLES = {  # one positive text per NON-literal pattern
    "四大全球倡议": "四大全球倡议", "文明互鉴": "文明交流互鉴", "现代化≠西方化": "现代化不等于西方化",
    "百年变局": "百年未有之大变局", "保护主义": "贸易保护主义", "天下体系": "天下主义",
    "脱钩断链": "小院高墙", "自主知识体系": "自主的知识体系", "国际话语权": "话语体系",
    "平等有序的(世界)多极化": "平等有序的世界多极化", "中心—外围": "中心-外围", "西方伪史": "伪史论",
}


def test_anchor_prefilter_never_hides_a_match():
    """Every term must be found on a positive example, so its literal anchor is implied."""
    terms = compiled()
    for k, (pat, *_r) in all_terms().items():
        ex = EXAMPLES.get(k) or pat
        if k not in EXAMPLES:
            assert re.escape(pat) == pat or not re.search(r"[\[\](){}?*+|\\.^$]", pat), k
        assert k in find_terms(ex, terms), (k, ex)
        assert re.search(pat, ex), (k, ex)


# ---------------------------------------------------------------- the page
def _weekly_fixture(path):
    c = sqlite3.connect(path)
    c.executescript(bdw.DDL)
    c.executemany("INSERT INTO discourse_concepts VALUES (?,?,?,?)",
                  [(k, en, fam, pat) for k, (pat, en, fam, _a) in all_terms().items()])
    rows = []
    trail = [f"2026-W{w}" for w in range(37, 45)]
    for w in trail + ["2026-W45"]:
        rows.append(("_all", "diplomacy", w, 20, 20))
        rows.append(("_all", "commentary", w, 100, 100))
        rows.append(("_all", "central", w, 100, 100))
        rows.append(("_all", "business_press", w, 10 if w != "2026-W45" else 100,
                     10 if w != "2026-W45" else 100))      # a crawl arrives in W45
    rows.append(("_all", "commentary", "2026-W20", 90, 90))
    for w in trail:
        rows.append(("全球南方", "diplomacy", w, 1, 20))      # trailing mean 1.0
        rows.append(("一带一路", "central", w, 2, 100))        # trailing mean 2.0
    rows += [
        ("全球南方", "diplomacy", "2026-W45", 6, 20),          # jump 6x
        ("一带一路", "central", "2026-W45", 3, 100),           # 3 < 2 x 2.0: not listed
        ("多极化", "commentary", "2026-W45", 2, 100),          # first ever
        ("霸权主义", "commentary", "2026-W20", 1, 90),
        ("霸权主义", "commentary", "2026-W45", 1, 100),        # first in the trailing window only
        ("一带一路", "business_press", "2026-W45", 5, 100),    # first ever, but volume-driven: sorts last
    ]
    c.executemany("INSERT INTO discourse_weekly VALUES (?,?,?,?,?)", rows)
    c.commit(); c.close()


@pytest.fixture
def page_db(tmp_path, monkeypatch):
    p = tmp_path / "weekly.db"
    _weekly_fixture(p)
    monkeypatch.setattr(svc, "recent_weeks", lambda n, today=None: trk.recent_weeks(n, TODAY))
    # The page cache is shared on disk now (web/services/pubcache.py): keep it off
    # in tests so nothing is written outside tmp_path and every call recomputes.
    pubcache.configure(cache_dir=tmp_path / "cache", stamp=tmp_path / "stamp", enabled=False)
    yield p
    pubcache.clear_memory()


async def _service(path, concept, weeks):
    import aiosqlite
    from web.database import SQLiteDB
    conn = await aiosqlite.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = aiosqlite.Row
    try:
        return await svc.get_discourse(SQLiteDB(conn), concept, weeks)
    finally:
        await conn.close()


def test_service_series_and_new_this_week(page_db):
    d = asyncio.run(_service(page_db, "全球南方", 12))
    assert d["concept"] == "全球南方" and d["weeks"] == 12
    w = {x["iso_week"]: x for x in d["series"]["weeks"]}
    assert d["series"]["weeks"][0]["iso_week"] == "2026-W46" and d["series"]["weeks"][0]["is_current"]
    cell = w["2026-W45"]["cells"]["diplomacy"]
    assert (cell["docs"], cell["denom"], cell["rate"], cell["thin"]) == (6, 20, 300.0, True)
    assert w["2026-W46"]["cells"]["diplomacy"]["denom"] == 0
    tot = d["series"]["totals"]["diplomacy"]                    # W35..W46 window: W37..W45 present
    assert (tot["docs"], tot["denom"]) == (14, 180)

    n = d["new"]
    assert n["ref_week"] == "2026-W45" and n["trail_from"] == "2026-W37" and n["trail_to"] == "2026-W44"
    got = {(i["concept"], i["speaker"]): i for i in n["rows"]}
    assert set(got) == {("全球南方", "diplomacy"), ("多极化", "commentary"), ("霸权主义", "commentary"),
                        ("一带一路", "business_press")}
    v = got[("一带一路", "business_press")]
    assert (v["kind"], v["volume_driven"], v["denom"], v["denom_mean"]) == ("first_ever", True, 100, 10.0)
    j = got[("全球南方", "diplomacy")]
    assert (j["kind"], j["docs"], j["trail_mean"], j["ratio"], j["volume_driven"]) == ("jump", 6, 1.0, 6.0, False)
    assert (j["rate"], j["trail_rate"], j["denom"], j["denom_mean"]) == (300.0, 50.0, 20, 20.0)
    assert got[("多极化", "commentary")]["kind"] == "first_ever"
    assert got[("霸权主义", "commentary")]["kind"] == "first_in_window"
    assert [i["kind"] for i in n["rows"]] == ["first_ever", "jump", "first_in_window", "first_ever"]
    assert n["rows"][-1]["volume_driven"] is True


def test_unknown_concept_falls_back(page_db):
    d = asyncio.run(_service(page_db, "nonsense", 999))
    assert d["concept"] == "全球南方" and d["weeks"] == trk.MAX_WEEKS


def test_page_renders(page_db, monkeypatch):
    from contextlib import asynccontextmanager
    import aiosqlite
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from web.database import SQLiteDB
    from web.routers import pages

    async def fake_stats(db):
        return {"total": 0, "site_count": 0}
    monkeypatch.setattr(pages, "get_stats", fake_stats)

    @asynccontextmanager
    async def lifespan(app):
        conn = await aiosqlite.connect(f"file:{page_db}?mode=ro", uri=True)
        conn.row_factory = aiosqlite.Row
        app.state.db = SQLiteDB(conn)
        yield
        await conn.close()

    app = FastAPI(lifespan=lifespan)
    app.include_router(pages.router)
    with TestClient(app) as client:
        r = client.get("/discourse", params={"concept": "全球南方", "weeks": 12})
        assert r.status_code == 200
        html = r.text
        assert "Discourse Tracker" in html
        assert "300.0" in html and "6/20" in html            # rate and its denominator
        assert "first ever" in html and "jump 6.0" in html
        assert "crawl-thin" in html                           # the media caveat
        assert "2026-W45" in html
        r2 = client.get("/discourse", params={"concept": "多极化"})
        assert r2.status_code == 200 and "Multipolarity" in r2.text


def test_page_without_tables(tmp_path, monkeypatch):
    p = tmp_path / "empty.db"
    sqlite3.connect(p).execute("CREATE TABLE x(a)").connection.commit()
    pubcache.configure(cache_dir=tmp_path / "cache", stamp=tmp_path / "stamp", enabled=False)
    assert asyncio.run(_service(p, "全球南方", 8)) is None
