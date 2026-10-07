"""Tests for scripts/repair_site_collisions.py — the repair of the rows already
clobbered by the cross-site id-collision upsert (docs/working/qa-gkmlpt-sync-diff.md,
docs/working/qa-collision-repair-plan.md).

What must hold:
  1. The predicate SELECTS a clobbered row (saved HTML in another site's dir)
     and does NOT select legitimately cross-HOST rows. `ifeng`, `sz_invest`,
     `mof`, `mofcom` and `stic` really do span hosts, and gkmlpt list items
     really do store outbound `url`s to gov.cn / mp.weixin.qq.com / Xinhua —
     the predicate is on `raw_html_path`, never on `url`, so none of those trip
     it. That distinction is asserted directly.
  2. The url-identity exception: `crawlers/gov.py` resolves ids by url, so a
     gkmlpt row pointing at www.gov.cn that the `gov` crawler adopted holds the
     CORRECT body under raw_html/gov/. It must be KEPT, not cleared.
  3. `clear` empties body_text_cn and raw_html_path and touches nothing else —
     not the title, not the dates, not the url or document_number.
  4. Idempotency: a second run finds nothing to clear and does not duplicate
     audit rows.
  5. The lock refusal: --apply exits 2 while the nightly lock dir exists, and
     --force overrides.

Run: python3 -m pytest tests/test_repair_site_collisions.py -v
  or: python3 tests/test_repair_site_collisions.py   (assert-based, no pytest)
"""
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from scripts.repair_site_collisions import (  # noqa: E402
    ACTION_KEEP,
    VICTIM_WHERE,
    classify,
    etld1,
    foreign_dir,
    main,
    site_domains,
)

SCRIPT = ROOT / "scripts" / "repair_site_collisions.py"

# (site_key, base_url) — the owners we seed
SITES = [
    ("npc", "https://flk.npc.gov.cn", "central"),
    ("gov", "https://www.gov.cn", "central"),
    ("zjj", "http://zjj.sz.gov.cn", "department"),
    ("stic", "http://stic.sz.gov.cn", "department"),
    ("ifeng", "https://www.ifeng.com", "media"),
    ("sz_invest", "https://fgw.sz.gov.cn", "municipal"),
    ("mofcom", "https://www.mofcom.gov.cn", "central"),
    ("mof", "https://www.mof.gov.cn", "central"),
    ("szpsq", "http://www.szpsq.gov.cn", "district"),
    ("heyuan", "http://www.heyuan.gov.cn", "municipal"),
    ("zhongshan", "http://www.zs.gov.cn", "municipal"),
    ("zj", "https://www.zj.gov.cn", "provincial"),
]

# id, site_key, title, url, raw_html_path, body, date_published, document_number
ROWS = [
    # --- CLOBBERED: saved HTML sits in another site's directory -------------
    (12728908, "npc", "包头市人民代表大会常务委员会关于修改《包头市供水条例》的决定",
     "https://flk.npc.gov.cn/detail?id=bb6523f2", "raw_html/zjj/12728908.html",
     "短正文" * 30, "2023-05-01", "包头市人大决定"),
    (12684793, "npc", "国务院2026年度立法工作计划",
     "https://flk.npc.gov.cn/detail?id=cc77", "raw_html/zjj/12684793.html",
     "二十七个字的垃圾正文内容替换了法律全文", "2026-01-01", ""),
    (5648687, "stic", "2017年深圳市科技创新委员会部门预算",
     "http://stic.sz.gov.cn/gkmlpt/content/5/5648/post_5648687.html",
     "raw_html/gz/5648687.html", "广州市市长温国辉就疫情防控物资保障工作调研" * 5,
     "2017-03-01", ""),
    (12724848, "zj", "浙江省科技厅某通知",
     "https://kjt.zj.gov.cn/art/2026/art_63c3.html", "raw_html/zjj/12724848.html",
     "住建局通知正文" * 10, "2026-02-01", ""),
    (553451, "heyuan", "习近平在内蒙古考察时强调",
     "https://www.gov.cn/yaowen/liebiao/202306/content_6885245.htm",
     "raw_html/jieyang/553451.html", "揭阳市党史学习教育领导小组会议" * 8,
     "2023-06-10", ""),
    (12696401, "zhongshan", "中山市某通知",
     "http://www.zs.gov.cn/gkmlpt/content/0/772/post_772794.html",
     "raw_html/zjj/12696401.html", "住建局的正文" * 10, "2026-03-01", ""),

    # --- URL-IDENTITY: gov adopted the id by url; body is CORRECT ----------
    (7846793, "szpsq", "国务院办公厅关于印发2020年政务公开工作要点的通知",
     "http://www.gov.cn/zhengce/content/2020-07/27/content_5530404.htm",
     "raw_html/gov/7846793.html",
     "国务院办公厅关于印发 2020年政务公开工作要点的通知 国办发〔2020〕17号" * 20,
     "2020-07-27", "国办发〔2020〕17号"),

    # --- LEGITIMATE, must NOT be selected ----------------------------------
    # cross-HOST url but own raw_html dir (ifeng spans tech./www.)
    (900001, "ifeng", "凤凰科技报道", "https://tech.ifeng.com/c/8s9J",
     "raw_html/ifeng/900001.html", "正文" * 50, "2026-01-02", ""),
    # sz_invest spans fgw./www.sz.gov.cn
    (900002, "sz_invest", "深圳投资推广", "https://www.sz.gov.cn/xxgk/post_1.html",
     "raw_html/sz_invest/900002.html", "正文" * 50, "2026-01-03", ""),
    # mofcom spans fms./www.
    (900003, "mofcom", "商务部公告", "https://fms.mofcom.gov.cn/art/1.html",
     "raw_html/mofcom/900003.html", "正文" * 50, "2026-01-04", ""),
    (900004, "mof", "财政部通知", "https://yss.mof.gov.cn/art/2.html",
     "raw_html/mof/900004.html", "正文" * 50, "2026-01-05", ""),
    # a gkmlpt list item whose url is an outbound link — own dir, so fine
    (900005, "zjj", "住建局转发国务院文件",
     "https://www.gov.cn/zhengce/content/2021-10/14/content_5642511.htm",
     "raw_html/zjj/900005.html", "正文" * 50, "2026-01-06", ""),
    (900006, "stic", "科创委转发微信公众号文章",
     "https://mp.weixin.qq.com/s/abcdef", "raw_html/stic/900006.html",
     "正文" * 50, "2026-01-07", ""),
    (900007, "zhongshan", "中山转发新华社报道",
     "https://www.news.cn/politics/20260101/abc/c.html",
     "raw_html/zhongshan/900007.html", "正文" * 50, "2026-01-08", ""),
    # no raw_html_path at all (npc's normal metadata-only state)
    (900008, "npc", "中华人民共和国民法典",
     "https://flk.npc.gov.cn/detail?id=minfadian", "", "", "2020-05-28", ""),
]

CLOBBERED_IDS = {12728908, 12684793, 5648687, 12724848, 553451, 12696401}
URL_IDENTITY_IDS = {7846793}
LEGIT_IDS = {900001, 900002, 900003, 900004, 900005, 900006, 900007, 900008}


def _db() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="collision_repair_"))
    path = tmp / "scratch.db"
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE sites (
        site_key TEXT PRIMARY KEY, name TEXT, base_url TEXT, admin_level TEXT)""")
    conn.execute("""CREATE TABLE documents (
        id INTEGER PRIMARY KEY, site_key TEXT, title TEXT, url TEXT,
        raw_html_path TEXT, body_text_cn TEXT, date_published TEXT,
        document_number TEXT, crawl_timestamp TEXT)""")
    conn.executemany(
        "INSERT INTO sites (site_key, name, base_url, admin_level) VALUES (?,?,?,?)",
        [(sk, sk, base, lvl) for sk, base, lvl in SITES])
    conn.executemany(
        """INSERT INTO documents (id, site_key, title, url, raw_html_path,
               body_text_cn, date_published, document_number, crawl_timestamp)
           VALUES (?,?,?,?,?,?,?,?,'2026-10-07T06:05:00+00:00')""", ROWS)
    conn.commit()
    conn.close()
    return path


def _selected(path: Path) -> set:
    conn = sqlite3.connect(path)
    ids = {r[0] for r in conn.execute(
        f"SELECT id FROM documents WHERE {VICTIM_WHERE}")}
    conn.close()
    return ids


def _run(path: Path, *args, lock: Path = None) -> subprocess.CompletedProcess:
    argv = [sys.executable, str(SCRIPT), "--db", str(path), *args]
    return subprocess.run(argv, capture_output=True, text=True, cwd=str(ROOT))


# --- 1. the predicate selects exactly the clobbered rows -------------------

def test_predicate_selects_clobbered_rows():
    path = _db()
    sel = _selected(path)
    missing = CLOBBERED_IDS - sel
    assert not missing, f"predicate missed clobbered rows: {missing}"


def test_predicate_ignores_legitimately_cross_host_rows():
    """ifeng / sz_invest / mof / mofcom span hosts, and gkmlpt list items store
    outbound urls to gov.cn / weixin / Xinhua. The predicate is on
    raw_html_path, not url, so none of them may be selected."""
    path = _db()
    sel = _selected(path)
    wrong = LEGIT_IDS & sel
    assert not wrong, (
        f"predicate wrongly selected legitimate cross-host rows: {wrong} — "
        "it must test raw_html_path, never url")


def test_predicate_selects_only_clobbered_plus_url_identity():
    path = _db()
    assert _selected(path) == CLOBBERED_IDS | URL_IDENTITY_IDS


def test_url_is_irrelevant_to_the_predicate():
    """Same row, same own-dir path, every kind of foreign url — never selected."""
    path = _db()
    conn = sqlite3.connect(path)
    for i, url in enumerate([
        "https://www.gov.cn/zhengce/content/x.htm",
        "https://mp.weixin.qq.com/s/xyz",
        "https://www.news.cn/politics/c.html",
        "https://tech.ifeng.com/c/abc",
    ]):
        conn.execute(
            """INSERT INTO documents (id, site_key, title, url, raw_html_path,
                   body_text_cn) VALUES (?,?,?,?,?,?)""",
            (910000 + i, "zjj", "t", url, f"raw_html/zjj/{910000+i}.html", "b"))
    conn.commit()
    conn.close()
    assert not (set(range(910000, 910004)) & _selected(path))


# --- 2. the url-identity exception ----------------------------------------

def test_url_identity_row_is_kept_not_cleared():
    path = _db()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    domains = site_domains(conn)
    row = conn.execute(
        "SELECT id, site_key, title, url, raw_html_path, "
        "length(body_text_cn) AS body_len FROM documents WHERE id = 7846793"
    ).fetchone()
    conn.close()
    action, _route, _flag = classify(row, domains)
    assert action == ACTION_KEEP, (
        "a gov-adopted www.gov.cn row holds the CORRECT body — clearing it "
        "would destroy content")


def test_url_identity_body_survives_apply():
    path = _db()
    before = sqlite3.connect(path).execute(
        "SELECT body_text_cn, raw_html_path FROM documents WHERE id = 7846793"
    ).fetchone()
    r = _run(path, "--apply", "--force")
    assert r.returncode == 0, r.stderr
    after = sqlite3.connect(path).execute(
        "SELECT body_text_cn, raw_html_path FROM documents WHERE id = 7846793"
    ).fetchone()
    assert after == before, "url-identity row must be untouched"


def test_clobber_in_the_other_direction_is_classified_clear():
    """A row OWNED by `gov` whose path points into a gkmlpt dir is a true
    clobber (szeb does not own gov.cn urls) — not a url-identity keep."""
    path = _db()
    conn = sqlite3.connect(path)
    conn.execute(
        """INSERT INTO documents (id, site_key, title, url, raw_html_path,
               body_text_cn) VALUES (?,?,?,?,?,?)""",
        (12650953, "gov", "中共中央 国务院印发《关于实施自由贸易试验区提升战略的意见》",
         "https://www.gov.cn/zhengce/202504/content_7020179.htm",
         "raw_html/szeb/12650953.html", "为提升我市普通高中综合素质评价信息管理平台" * 5))
    conn.commit()
    conn.row_factory = sqlite3.Row
    domains = site_domains(conn)
    row = conn.execute(
        "SELECT id, site_key, title, url, raw_html_path, "
        "length(body_text_cn) AS body_len FROM documents WHERE id = 12650953"
    ).fetchone()
    conn.close()
    action, _route, _flag = classify(row, domains)
    assert action != ACTION_KEEP, "gov-owned row clobbered by szeb must be cleared"


# --- 3. clear empties body+path and nothing else ---------------------------

def test_clear_empties_body_and_path_only():
    path = _db()
    cols = ("title", "url", "date_published", "document_number", "site_key")
    conn = sqlite3.connect(path)
    before = {
        i: conn.execute(
            f"SELECT {','.join(cols)} FROM documents WHERE id = ?", (i,)).fetchone()
        for i in CLOBBERED_IDS}
    conn.close()

    r = _run(path, "--apply", "--force")
    assert r.returncode == 0, r.stderr

    conn = sqlite3.connect(path)
    for i in CLOBBERED_IDS:
        body, rpath = conn.execute(
            "SELECT body_text_cn, raw_html_path FROM documents WHERE id = ?",
            (i,)).fetchone()
        assert body == "", f"{i}: body not cleared"
        assert rpath == "", f"{i}: raw_html_path not cleared"
        after = conn.execute(
            f"SELECT {','.join(cols)} FROM documents WHERE id = ?", (i,)).fetchone()
        assert after == before[i], (
            f"{i}: repair altered {cols} — it must only clear body and path")
    conn.close()


def test_legitimate_rows_untouched_by_apply():
    path = _db()
    conn = sqlite3.connect(path)
    before = {i: conn.execute(
        "SELECT body_text_cn, raw_html_path FROM documents WHERE id = ?", (i,)
    ).fetchone() for i in LEGIT_IDS}
    conn.close()
    assert _run(path, "--apply", "--force").returncode == 0
    conn = sqlite3.connect(path)
    for i in LEGIT_IDS:
        assert conn.execute(
            "SELECT body_text_cn, raw_html_path FROM documents WHERE id = ?", (i,)
        ).fetchone() == before[i], f"{i} was modified but is legitimate"
    conn.close()


def test_audit_table_records_every_decision():
    path = _db()
    assert _run(path, "--apply", "--force").returncode == 0
    conn = sqlite3.connect(path)
    rows = dict(conn.execute("SELECT doc_id, action FROM collision_repairs"))
    conn.close()
    assert set(rows) == CLOBBERED_IDS | URL_IDENTITY_IDS
    assert rows[7846793] == ACTION_KEEP
    assert rows[12728908] == "clear_by_design", "npc -> clear-by-design"
    assert rows[12696401] == "clear_gkmlpt_backfill"
    assert rows[5648687] == "clear_gkmlpt_backfill"
    assert rows[553451] == "clear_link_stub", "heyuan gov.cn stub stays empty"
    conn = sqlite3.connect(path)
    dirs = dict(conn.execute("SELECT doc_id, old_site_dir FROM collision_repairs"))
    conn.close()
    assert dirs[12728908] == "zjj"
    assert dirs[553451] == "jieyang"


# --- 4. idempotency --------------------------------------------------------

def test_idempotent_second_run():
    path = _db()
    assert _run(path, "--apply", "--force").returncode == 0
    conn = sqlite3.connect(path)
    snap1 = conn.execute(
        "SELECT id, body_text_cn, raw_html_path FROM documents ORDER BY id"
    ).fetchall()
    n1 = conn.execute("SELECT COUNT(*) FROM collision_repairs").fetchone()[0]
    conn.close()

    r2 = _run(path, "--apply", "--force")
    assert r2.returncode == 0, r2.stderr
    conn = sqlite3.connect(path)
    snap2 = conn.execute(
        "SELECT id, body_text_cn, raw_html_path FROM documents ORDER BY id"
    ).fetchall()
    n2 = conn.execute("SELECT COUNT(*) FROM collision_repairs").fetchone()[0]
    conn.close()

    assert snap1 == snap2, "a second run changed documents — not idempotent"
    assert n1 == n2, f"audit rows duplicated on re-run: {n1} -> {n2}"


def test_cleared_rows_no_longer_match_predicate():
    path = _db()
    assert _run(path, "--apply", "--force").returncode == 0
    # only the kept url-identity row still matches
    assert _selected(path) == URL_IDENTITY_IDS


def test_dry_run_writes_nothing():
    path = _db()
    conn = sqlite3.connect(path)
    snap = conn.execute(
        "SELECT id, body_text_cn, raw_html_path FROM documents ORDER BY id"
    ).fetchall()
    conn.close()
    r = _run(path, "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "dry-run" in r.stdout
    conn = sqlite3.connect(path)
    assert conn.execute(
        "SELECT id, body_text_cn, raw_html_path FROM documents ORDER BY id"
    ).fetchall() == snap, "--dry-run modified the database"
    tables = {t[0] for t in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert "collision_repairs" not in tables, "--dry-run created a table"


# --- 5. the lock refusal ---------------------------------------------------

def test_apply_refuses_while_nightly_lock_exists():
    import scripts.repair_site_collisions as mod
    path = _db()
    lock = Path(tempfile.mkdtemp(prefix="fake_lock_")) / "daily-sync.lock.d"
    lock.mkdir()
    real = mod.LOCK_DIR
    try:
        mod.LOCK_DIR = lock
        assert mod.main(["--db", str(path), "--apply"]) == 2, (
            "must refuse to write while the nightly holds the lock")
        conn = sqlite3.connect(path)
        tables = {t[0] for t in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        assert "collision_repairs" not in tables, "refusal still wrote"
        # --force overrides
        assert mod.main(["--db", str(path), "--apply", "--force"]) == 0
    finally:
        mod.LOCK_DIR = real


def test_dry_run_allowed_while_locked():
    import scripts.repair_site_collisions as mod
    path = _db()
    lock = Path(tempfile.mkdtemp(prefix="fake_lock_")) / "daily-sync.lock.d"
    lock.mkdir()
    real = mod.LOCK_DIR
    try:
        mod.LOCK_DIR = lock
        assert mod.main(["--db", str(path), "--dry-run"]) == 0, (
            "--dry-run is read-only and must work during the nightly")
    finally:
        mod.LOCK_DIR = real


def test_requires_exactly_one_mode():
    path = _db()
    assert _run(path).returncode != 0, "no mode must be an error"
    assert _run(path, "--dry-run", "--apply").returncode != 0


# --- helpers ---------------------------------------------------------------

def test_etld1_multi_label_suffixes():
    assert etld1("tech.ifeng.com") == etld1("www.ifeng.com") == "ifeng.com"
    assert etld1("fms.mofcom.gov.cn") == etld1("www.mofcom.gov.cn") == "mofcom.gov.cn"
    assert etld1("kj.zs.gov.cn") == etld1("www.zs.gov.cn") == "zs.gov.cn"
    # gov.cn is a public suffix: the State Council is NOT the same owner as Heyuan
    assert etld1("www.gov.cn") != etld1("www.heyuan.gov.cn")


def test_foreign_dir_parsing():
    assert foreign_dir("raw_html/zjj/12728908.html") == "zjj"
    assert foreign_dir("") == ""


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  ok  {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
