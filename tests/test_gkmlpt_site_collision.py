"""Regression check for the cross-site id-collision data-corruption path (2026-10).

docs/working/qa-gkmlpt-sync-diff.md: gkmlpt post ids are ONE platform-wide
namespace shared by every Guangdong site, and they overlap the synthetic ids
other crawlers assign. `sync_site` scopes its "what's new?" diff to a single
site (`WHERE site_key = ?`) while the insert upserted on the `id` PRIMARY KEY
with an unguarded `ON CONFLICT(id) DO UPDATE SET body_text_cn=...`. So a post
appearing in a second site's feed looked NEW to that site and overwrote the
body of the row owned by the FIRST site, keeping the original site_key.
Measured live: 80 collisions in a 1,692-id sample of 3 sites' list APIs, and
261 already-corrupted rows in the corpus.

Rules under test:
  1. An id owned by another site_key is NOT overwritten; the store returns
     False so the caller neither counts it nor records an "added" change.
  2. Normal same-site updates still write body_text_cn/raw_html_path.
  3. A genuinely new id for a second site still inserts.
  4. base.store_document (shared by every other crawler) has the same guard.

Run: python3 -m pytest tests/test_gkmlpt_site_collision.py -v
  or: python3 tests/test_gkmlpt_site_collision.py   (assert-based, no pytest)
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

os.environ["SKIP_RAW_HTML"] = "1"

from crawlers.base import init_db, store_document  # noqa: E402
from crawlers.gkmlpt import store_gkmlpt_document  # noqa: E402

VICTIM_ID = 12728908  # a real colliding id: owned by `npc`, served by zjj's feed
VICTIM_BODY = "原始正文：包头市人民代表大会常务委员会关于修改《包头市供水条例》的决定" * 20


def _conn():
    tmp = tempfile.mkdtemp(prefix="gkmlpt_collision_")
    conn = init_db(Path(tmp) / "scratch.db")
    for sk, name, lvl in [
        ("npc", "National Laws Database", "central"),
        ("zjj", "Housing & Construction Bureau", "department"),
        ("jieyang", "Jieyang", "municipal"),
    ]:
        conn.execute(
            "INSERT INTO sites (site_key, name, base_url, admin_level) VALUES (?,?,?,?)",
            (sk, name, f"http://{sk}.example.gov.cn", lvl),
        )
    conn.commit()
    return conn


def _seed_victim(conn):
    """A row owned by `npc`, exactly as the live corpus holds it."""
    store_document(
        conn,
        "npc",
        {
            "id": VICTIM_ID,
            "title": "包头市人民代表大会常务委员会关于修改《包头市供水条例》的决定",
            "body_text_cn": VICTIM_BODY,
            "url": "https://flk.npc.gov.cn/detail?id=bb6523f2fd16428db141717cf64a10f3",
            "raw_html_path": "raw_html/npc/12728908.html",
        },
    )
    conn.commit()


def _row(conn, doc_id):
    return conn.execute(
        "SELECT site_key, body_text_cn, raw_html_path FROM documents WHERE id = ?",
        (doc_id,),
    ).fetchone()


# --- 1. the corruption path is closed -------------------------------------

def test_cross_site_collision_does_not_clobber_body():
    conn = _conn()
    _seed_victim(conn)

    wrote = store_gkmlpt_document(
        conn,
        "zjj",
        {
            "id": VICTIM_ID,
            "title": "住房和建设局某通知",
            "url": "http://zjj.sz.gov.cn/content/post_12728908.html",
        },
        body_text="短正文" * 5,  # the 189-char garbage that replaced the law
        raw_html_path="raw_html/zjj/12728908.html",
    )

    assert wrote is False, "a foreign-owned id must report that nothing was written"
    site_key, body, path = _row(conn, VICTIM_ID)
    assert site_key == "npc"
    assert body == VICTIM_BODY, "npc's body was overwritten by zjj — the bug is back"
    assert path == "raw_html/npc/12728908.html", "raw_html_path was repointed at zjj"
    assert conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1


def test_cross_site_collision_via_base_store_document():
    """Every non-gkmlpt crawler shares base.store_document — same guard."""
    conn = _conn()
    _seed_victim(conn)

    wrote = store_document(
        conn,
        "jieyang",
        {
            "id": VICTIM_ID,
            "title": "揭阳市某文件",
            "body_text_cn": "揭阳正文",
            "url": "http://www.jieyang.gov.cn/content/post_12728908.html",
        },
    )

    assert wrote is False
    site_key, body, _ = _row(conn, VICTIM_ID)
    assert site_key == "npc"
    assert body == VICTIM_BODY


# --- 2. the normal paths still work ---------------------------------------

def test_same_site_update_still_writes():
    conn = _conn()
    store_gkmlpt_document(
        conn, "zjj",
        {"id": 999001, "title": "深圳市住房通知", "url": "http://zjj.sz.gov.cn/content/post_999001.html"},
        body_text="", raw_html_path="",
    )
    conn.commit()

    wrote = store_gkmlpt_document(
        conn, "zjj",
        {"id": 999001, "title": "深圳市住房通知", "url": "http://zjj.sz.gov.cn/content/post_999001.html"},
        body_text="补全的正文内容", raw_html_path="raw_html/zjj/999001.html",
    )
    conn.commit()

    assert wrote is True, "a same-site body backfill must still be written"
    site_key, body, path = _row(conn, 999001)
    assert (site_key, body, path) == ("zjj", "补全的正文内容", "raw_html/zjj/999001.html")


def test_same_site_update_via_base_store_document():
    conn = _conn()
    store_document(conn, "npc", {"id": 999002, "title": "某法", "body_text_cn": "", "url": "u2"})
    conn.commit()
    wrote = store_document(conn, "npc", {"id": 999002, "title": "某法", "body_text_cn": "正文", "url": "u2"})
    conn.commit()
    assert wrote is True
    assert _row(conn, 999002)[1] == "正文"


def test_genuinely_new_id_for_second_site_inserts():
    conn = _conn()
    _seed_victim(conn)
    wrote = store_gkmlpt_document(
        conn, "zjj",
        {"id": 13007479, "title": "新文件", "url": "http://zjj.sz.gov.cn/content/post_13007479.html"},
        body_text="新正文", raw_html_path="",
    )
    conn.commit()
    assert wrote is True
    assert _row(conn, 13007479)[0] == "zjj"
    assert conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 2


# --- 3. yield accounting ---------------------------------------------------

def test_sync_accounting_does_not_claim_skipped_docs():
    """`added` must count only rows actually added for this site."""
    conn = _conn()
    _seed_victim(conn)

    api_docs = {
        VICTIM_ID: {"id": VICTIM_ID, "title": "住建局条目", "url": "http://zjj.sz.gov.cn/content/post_a.html"},
        13007479: {"id": 13007479, "title": "真的新文件", "url": "http://zjj.sz.gov.cn/content/post_b.html"},
    }
    # Mirror sync_site's per-site diff + its guarded counting.
    db_ids = {r[0] for r in conn.execute(
        "SELECT id FROM documents WHERE site_key = ?", ("zjj",)).fetchall()}
    new_ids = set(api_docs) - db_ids
    assert new_ids == set(api_docs), "both look 'new' to zjj — that is the trap"

    added = collided = 0
    for doc_id in sorted(new_ids):
        if store_gkmlpt_document(conn, "zjj", api_docs[doc_id], "正文", ""):
            added += 1
        else:
            collided += 1
    conn.commit()

    assert (added, collided) == (1, 1), f"expected 1 added / 1 skipped, got {added}/{collided}"
    zjj_rows = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE site_key = 'zjj'").fetchone()[0]
    assert zjj_rows == added, "reported adds must equal rows actually gained"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
