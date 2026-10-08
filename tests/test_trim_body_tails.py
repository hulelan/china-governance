"""Regression checks for scripts/trim_body_tails.py (share-widget / nav tails, 2026-10-07).

Fragments are replicas of tails seen on the live corpus (suzhou, sz_invest, gov,
most, shb_stcsm, jl_gxt, gdny) and of bodies where the same words are CONTENT
(36kr "我的分享到这里", hlj "分享到了…成果", nrta's header share bar followed by
the real text). Rules under test:
  1. a tail at the END is trimmed;
  2. a marker in the middle of a body is untouched;
  3. an all-chrome body is flagged, never emptied;
  4. text before the first marker is preserved byte-for-byte;
  5. a second run is a no-op (idempotent);
  6. --dry-run writes nothing (read-only connection);
  7. --revert restores the stored body exactly.

Run: python3 tests/test_trim_body_tails.py   (assert-based, no pytest needed)
  or: python3 -m pytest tests/test_trim_body_tails.py -v
"""
import hashlib
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
os.environ["SKIP_RAW_HTML"] = "1"

import trim_body_tails as tbt  # noqa: E402
from crawlers.base import init_db  # noqa: E402

PARA = ("依照有关法律法规和政策规定，现将有关事项通知如下，请各单位结合实际认真贯彻执行，"
        "并于规定期限内将落实情况报送我厅。各市、县人民政府及省直有关部门要加强组织领导，明确责任分工。")

SUZHOU = (PARA + "\n苏州市人民政府办公室\n2018年8月6日\n（此件公开发布）\n"
          "市政府办公室关于进一步加强文物安全工作的实施意见（苏府办〔2018〕238号）.pdf\n"
          " 相关解读\r\n 扫一扫在手机打开当前页\r\n 分享到：\r\n $('#share-1').share();\r\n"
          "img#imgConac {\r\n height: 55px;\r\n}\r\n 网站导航：\r\n 中国政府网\r\n"
          " 苏州辖市（区）网站\r\n 苏州市政务网站")
SZ_INVEST = (PARA + " \n 分享到:\n 分享到:\n"
             " $('#share-1').share({ sites: ['wechat', 'weibo', 'qq', 'qzone'] });\n"
             " $('#share-2').share({ sites: ['wechat', 'weibo', 'qq', 'qzone'] });")
GOV = (PARA + "\n国务院办公厅\n2017年11月6日\n（此件公开发布）\n 扫一扫在手机打开当前页\n 解读\n"
       " 我国最新对可制造毒品的5种物质予以管制\n 国务院办公厅关于同意将溴素列入易制毒化学品品种目录的函\n"
       " 登录\n 注册")
MOST = PARA + "\n科技部人事司\n2021年3月3日\n扫一扫在手机打开当前页\n打印本页\n 相关文档\n 相关附件"
SHB = (PARA + "\r\n .xxgk_xgxx a{ color:blue;}\r\n 【相关信息】\r\n 关于印发《上海市科技创新券管理办法》的通知 \r\n"
       " 【部门解读】《上海市科技创新券管理办法》政策解读 \r\n 【打印】\r\n 【关闭】")
GDNY_ONE_LINE = ("第三十八条 本办法自2020年8月1日起施行，长期执行。 "
                 "相关链接：一图读懂《广东省农业农村厅农作物品种审定与评定办法》")
JL_GXT_ALL_CHROME = (" .bsClose span{font-size: 20px; color: #999;}\n"
                     " .bsTop{width: 220px;text-align:center}\n 分享到\xa0-\xa0微信\n <div")

MID_SHARE = (PARA + "\n 分享到：\n 微信\n" + PARA + "\n" + PARA)            # widget block mid-body
MID_36KR = PARA + "\n我们也有一个目标。\n我的分享到这里，谢谢大家！"
MID_HLJ = PARA + "也使困难群众更多地分享到了哈尔滨市经济发展的成果。"
NRTA_HEADER_SHARE = (" 【字号：大 中 小 】\r\n 分享到：\r\n国家广播电影电视总局令第55号\n"
                     "按照《国务院办公厅关于开展行政法规规章清理工作的通知》的要求，我局决定废止下列2件广播影视规章：\n"
                     "一、《电视剧管理规定》\n二、《广播电视节目出品人持证上岗暂行规定》")


def _trim(body):
    return tbt.trim_text(body)


# --- 1. tail at end is trimmed ------------------------------------------------

def test_tail_at_end_is_trimmed():
    for body, must_end in ((SUZHOU, "（苏府办〔2018〕238号）.pdf"),
                           (SZ_INVEST, "明确责任分工。"),
                           (GOV, "（此件公开发布）"),
                           (MOST, "2021年3月3日"),
                           (SHB, "明确责任分工。"),
                           (GDNY_ONE_LINE, "长期执行。")):
        t = _trim(body)
        assert t, f"no tail found in {body[-60:]!r}"
        kept, removed, _ = t
        assert kept.endswith(must_end), (kept[-60:], must_end)
        for junk in ("分享到", "扫一扫", "share(", "打印", "【关闭】", "相关链接", "登录"):
            assert junk not in kept[len(PARA):], (junk, kept[-80:])


def test_related_titles_leave_with_the_tail():
    # the false-reference source: 《X》 titles inside 相关信息 / 解读 lists
    kept, removed, _ = _trim(SHB)
    assert "《上海市科技创新券管理办法》" in removed and "《" not in kept
    kept, removed, _ = _trim(GOV)
    assert "易制毒化学品品种目录的函" in removed and "易制毒" not in kept


# --- 2. marker mid-body is untouched -------------------------------------------

def test_marker_mid_body_untouched():
    for body in (MID_SHARE, MID_36KR, MID_HLJ, NRTA_HEADER_SHARE):
        assert tbt.find_tail(body) is None, f"mid-body marker treated as tail: {body[-80:]!r}"


# --- 3. all-chrome is flagged, not emptied ---------------------------------------

def test_all_chrome_body_is_flagged_not_emptied():
    plan = tbt.decide(JL_GXT_ALL_CHROME, "jl_gxt", "", ROOT, allow_reextract=False)
    assert plan and plan["method"] == "flagged" and plan["new"] is None
    header_only = (" 您的位置: / 正文\r\n 来源：\r\n 发布日期：\r\n 浏览次数： 次\r\n 文章字号：大中小\r\n"
                   " 分享到：\r\n 微博\r\n 微信\r\n <div")
    plan = tbt.decide(header_only, "xjyl", "", ROOT, allow_reextract=False)
    assert plan and plan["method"] == "flagged"


def test_own_attachment_list_is_not_a_tail():
    zj = (PARA + "\n相关附件：\n附件1-浙江省建设用地土壤污染风险管控和修复名录20260212更新.docx\n"
          "附件2-移出清单20260212更新.docx")
    assert tbt.find_tail(zj) is None
    leshan = PARA + "\n相关附件:\n 附件1 代理机构报名信息登记表.doc\n 扫一扫在手机打开当前页\n 【打印本页】"
    kept, _, _ = _trim(leshan)
    assert kept.endswith("附件1 代理机构报名信息登记表.doc")


def test_ascii_attribute_leftover_is_all_chrome():
    body = (' class="view TRS_UEDITOR trs_paper_default">\n//相关政策\n'
            "document.write('相关政策');\n 分享到：\n 微信")
    plan = tbt.decide(body, "bjb_fgw", "", ROOT, allow_reextract=False)
    assert plan and plan["method"] == "flagged"


# --- 4. text before the marker is preserved byte-for-byte --------------------------

def test_prefix_preserved_byte_for_byte():
    for body in (SUZHOU, SZ_INVEST, GOV, MOST, SHB, GDNY_ONE_LINE):
        kept, removed, _ = _trim(body)
        assert body.startswith(kept)
        assert kept + removed == body                      # exactly reversible
        cut = tbt.find_tail(body)[0]
        assert kept == body[:cut].rstrip(tbt.WS)           # only trailing whitespace dropped
    # signature / date / attachment line right before the first marker are kept
    kept = _trim(SUZHOU)[0]
    assert "苏州市人民政府办公室\n2018年8月6日\n（此件公开发布）\n" in kept


# --- DB-level: idempotent, dry-run is read-only, revert ------------------------------

def _scratch(tmp):
    db = Path(tmp) / "scratch.db"
    conn = init_db(db)
    conn.execute("INSERT OR IGNORE INTO sites (site_key, name, base_url, admin_level) "
                 "VALUES ('sz', 'Scratch', 'http://example.gov.cn', 'municipal')")
    bodies = {1: SUZHOU, 2: SZ_INVEST, 3: MID_SHARE, 4: JL_GXT_ALL_CHROME, 5: GOV, 6: MID_36KR}
    for i, b in bodies.items():
        conn.execute("INSERT INTO documents (id, site_key, title, body_text_cn, url, crawl_timestamp) "
                     "VALUES (?, 'sz', ?, ?, ?, '2026-10-07T00:00:00Z')",
                     (i, f"标题{i}", b, f"http://example.gov.cn/c/{i}"))
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    return db, bodies


def _bodies(db):
    c = sqlite3.connect(str(db), timeout=30)
    c.execute("PRAGMA busy_timeout=30000")
    out = dict(c.execute("SELECT id, body_text_cn FROM documents"))
    c.close()
    return out


def _digest(db):
    """Main file bytes + WAL size (a read-only open may create an empty -shm/-wal)."""
    wal = Path(str(db) + "-wal")
    return (hashlib.sha256(Path(db).read_bytes()).hexdigest(),
            wal.stat().st_size if wal.exists() else 0)


def test_dry_run_writes_nothing():
    with tempfile.TemporaryDirectory() as tmp:
        db, _ = _scratch(tmp)
        before = _digest(db)
        res = tbt.run(db, Path(tmp), apply=False, allow_reextract=False, sample_n=5)
        assert res["candidates"] == 4 and res["written"] == 0
        assert _digest(db) == before, "dry-run changed the DB files"
        c = sqlite3.connect(str(db), timeout=30)
        c.execute("PRAGMA busy_timeout=30000")
        assert not c.execute("SELECT 1 FROM sqlite_master WHERE name='body_tail_trims'").fetchone()
        c.close()


def test_apply_is_idempotent_and_never_empties():
    with tempfile.TemporaryDirectory() as tmp:
        db, orig = _scratch(tmp)
        r1 = tbt.run(db, Path(tmp), apply=True, allow_reextract=False, sample_n=0)
        assert r1["written"] == 3 and r1["flagged"] == 1, r1
        after1 = _bodies(db)
        assert after1[3] == orig[3] and after1[6] == orig[6]        # mid-body untouched
        assert after1[4] == orig[4]                                  # all-chrome flagged, kept
        assert all(b and b.strip() for b in after1.values())
        assert orig[1].startswith(after1[1]) and orig[5].startswith(after1[5])
        r2 = tbt.run(db, Path(tmp), apply=True, allow_reextract=False, sample_n=0)
        assert r2["written"] == 0, r2
        assert _bodies(db) == after1
        c = sqlite3.connect(str(db), timeout=30)
        c.execute("PRAGMA busy_timeout=30000")
        n_audit = c.execute("SELECT COUNT(*) FROM body_tail_trims").fetchone()[0]
        flags = c.execute("SELECT doc_id, reason FROM body_tail_flags").fetchall()
        c.close()
        assert n_audit == 3 and flags == [(4, "all_chrome")]


def test_revert_restores_exactly():
    with tempfile.TemporaryDirectory() as tmp:
        db, orig = _scratch(tmp)
        tbt.run(db, Path(tmp), apply=True, allow_reextract=False, sample_n=0)
        assert _bodies(db) != orig
        tbt.revert(db)
        assert _bodies(db) == orig


def test_lock_dir_refusal(monkeypatch=None):
    with tempfile.TemporaryDirectory() as tmp:
        lock = Path(tmp) / "lock.d"
        lock.mkdir()
        saved = tbt.LOCK_DIR
        tbt.LOCK_DIR = lock
        try:
            db, orig = _scratch(tmp)
            assert tbt.main(["--apply", "--db", str(db), "--no-reextract"]) == 2
            assert _bodies(db) == orig
        finally:
            tbt.LOCK_DIR = saved


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"{len(fns)} passed")
